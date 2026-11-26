# -*- coding: utf-8 -*-

import datetime
import email.utils
import http.client
import json
import math
import time

import jwt
from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization

from ... import config
from ...modules import mongo as mod_mongo
from ...modules.mongo.user import UserDocument
from ...handlers.ext.paramed_cgi import Handler as _Handler, HandlerError as _HandlerError


class HandlerError(_HandlerError):
    pass


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class BaseHandler(_Handler):
    TOKEN_MAX_AGE = 300
    JWT_ALGORITHMS = ('RS256', 'RS384', 'RS512', 'PS256', 'PS384', 'PS512', 'ES256', 'ES384', 'ES512', 'EdDSA')

    def _error(self, status, message):
        self.req.setResponseCode(status, http.client.responses[status])
        self.req.setHeader('Content-Type', 'application/json')
        self.req.write(json.dumps({'error': message}))

    def _json(self, value, status=http.client.OK):
        self.req.setResponseCode(status, http.client.responses[status])
        self.req.setHeader('Cache-Control', 'no-store')
        self.req.setHeader('Content-Type', 'application/json; charset=utf-8')
        self.req.write(json.dumps(value, default=str))

    @staticmethod
    def _http_datetime(value):
        if value.tzinfo is None:
            value = value.replace(tzinfo=datetime.timezone.utc)
        return email.utils.format_datetime(
            value.astimezone(datetime.timezone.utc).replace(microsecond=0),
            usegmt=True)

    def _if_unmodified_since(self):
        value = self.req.request_headers.get('If-Unmodified-Since')
        if not value:
            raise ApiError(
                http.client.PRECONDITION_REQUIRED,
                'If-Unmodified-Since header is required')
        try:
            value = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            value = None
        if value is None:
            raise ApiError(
                http.client.BAD_REQUEST,
                'Invalid If-Unmodified-Since header')
        if value.tzinfo is None:
            value = value.replace(tzinfo=datetime.timezone.utc)
        return value.astimezone(datetime.timezone.utc).replace(microsecond=0)

    def _authenticate(self):
        token = self.req.request_headers.get('Authorization', '')
        parts = token.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            raise ApiError(http.client.UNAUTHORIZED, 'Authorization required')
        token = parts[1]
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError:
            raise ApiError(http.client.UNAUTHORIZED, 'Invalid token')
        user_id, key_id, dt, algorithm = (header.get(name) for name in ('user_id', 'kid', 'dt', 'alg'))
        agent_id, agent_position = header.get('agent_id'), header.get('agent_position')
        if (not all(isinstance(value, str) and value for value in
                    (user_id, key_id, algorithm, agent_id)) or
                not isinstance(agent_position, str) or
                isinstance(dt, bool) or not isinstance(dt, (int, float, str))):
            raise ApiError(http.client.UNAUTHORIZED, 'Token header is incomplete')
        try:
            token_time = float(dt)
        except (TypeError, ValueError, OverflowError):
            try:
                token_time = datetime.datetime.fromisoformat(str(dt).replace('Z', '+00:00')).timestamp()
            except (TypeError, ValueError, OverflowError, OSError):
                raise ApiError(http.client.UNAUTHORIZED, 'Invalid token datetime')
        if not math.isfinite(token_time):
            raise ApiError(http.client.UNAUTHORIZED, 'Invalid token datetime')
        if abs(time.time() - token_time) > self.TOKEN_MAX_AGE:
            raise ApiError(http.client.UNAUTHORIZED, 'Token has expired')
        try:
            user = UserDocument.objects(id=mod_mongo.bson.objectid.ObjectId(str(user_id))).first()
        except (TypeError, ValueError, mod_mongo.bson.errors.InvalidId):
            user = None
        if user is None:
            raise ApiError(http.client.UNAUTHORIZED, 'Unknown user')
        key = next((item for item in user.keyset if item.id == key_id), None)
        if key is None or bool(key.pub) == bool(key.crt) or algorithm not in self.JWT_ALGORITHMS:
            raise ApiError(http.client.UNAUTHORIZED, 'Unknown signing key')
        try:
            public_key = serialization.load_der_public_key(key.pub) if key.pub else x509.load_der_x509_certificate(key.crt).public_key()
            payload = jwt.decode(token, public_key, algorithms=[algorithm], options={'verify_aud': False})
        except (ValueError, TypeError, jwt.PyJWTError, UnsupportedAlgorithm):
            raise ApiError(http.client.UNAUTHORIZED, 'Invalid signature')
        try:
            requested_agent_id = mod_mongo.bson.objectid.ObjectId(str(agent_id))
        except (TypeError, ValueError, mod_mongo.bson.errors.InvalidId):
            raise ApiError(http.client.UNAUTHORIZED, 'Invalid agent')
        agent = next((item for item in user.agents if item.id == requested_agent_id and item.position == agent_position), None)
        if agent is None:
            raise ApiError(http.client.FORBIDDEN, 'Agent is not assigned to user')
        return user, agent, payload

    def _run(self, operation):
        try:
            return operation()
        except ApiError as err:
            self._error(err.status, err.message)
        except (ValueError, TypeError):
            self._error(http.client.BAD_REQUEST, 'Invalid request')
