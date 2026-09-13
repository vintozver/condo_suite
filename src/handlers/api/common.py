# -*- coding: utf-8 -*-

import datetime
import http.client
import json
import time

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import serialization

from .... import config
from ....modules import mongo as mod_mongo
from ....modules.mongo.parking_event import Document as ParkingEventDocument
from ....modules.mongo.user import UserDocument
from ....handlers.ext.paramed_cgi import Handler as _Handler, HandlerError as _HandlerError


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

    def _authenticate(self):
        token = self.req.request_headers.get('Authorization', '')
        if not token.startswith('Bearer '):
            raise ApiError(http.client.UNAUTHORIZED, 'Authorization required')
        try:
            header = jwt.get_unverified_header(token[7:])
        except jwt.InvalidTokenError:
            raise ApiError(http.client.UNAUTHORIZED, 'Invalid token')
        user_id, key_id, dt, algorithm = (header.get(name) for name in ('user_id', 'kid', 'dt', 'alg'))
        agent_id, agent_position = header.get('agent_id'), header.get('agent_position')
        if not user_id or not key_id or not dt or not algorithm or not agent_id or agent_position is None:
            raise ApiError(http.client.UNAUTHORIZED, 'Token header is incomplete')
        try:
            token_time = float(dt)
        except (TypeError, ValueError):
            try:
                token_time = datetime.datetime.fromisoformat(str(dt).replace('Z', '+00:00')).timestamp()
            except (TypeError, ValueError):
                raise ApiError(http.client.UNAUTHORIZED, 'Invalid token datetime')
        if abs(time.time() - token_time) > self.TOKEN_MAX_AGE:
            raise ApiError(http.client.UNAUTHORIZED, 'Token has expired')
        try:
            user = UserDocument.objects(id=mod_mongo.bson.objectid.ObjectId(str(user_id))).first()
        except (TypeError, ValueError):
            user = None
        if user is None:
            raise ApiError(http.client.UNAUTHORIZED, 'Unknown user')
        key = next((item for item in user.keyset if item.id == key_id), None)
        if key is None or bool(key.pub) == bool(key.crt) or algorithm not in self.JWT_ALGORITHMS:
            raise ApiError(http.client.UNAUTHORIZED, 'Unknown signing key')
        try:
            public_key = serialization.load_der_public_key(key.pub) if key.pub else x509.load_der_x509_certificate(key.crt).public_key()
            payload = jwt.decode(token[7:], public_key, algorithms=[algorithm], options={'verify_aud': False})
        except (ValueError, TypeError, jwt.InvalidTokenError):
            raise ApiError(http.client.UNAUTHORIZED, 'Invalid signature')
        try:
            requested_agent_id = mod_mongo.bson.objectid.ObjectId(str(agent_id))
        except (TypeError, ValueError):
            raise ApiError(http.client.UNAUTHORIZED, 'Invalid agent')
        agent = next((item for item in user.agents if item.id == requested_agent_id and item.position == agent_position), None)
        if agent is None:
            raise ApiError(http.client.FORBIDDEN, 'Agent is not assigned to user')
        return user, agent, payload

    @staticmethod
    def _body(payload):
        body = payload.get('body', payload)
        return body if isinstance(body, dict) else {}

    @staticmethod
    def _event(doc):
        return {'oid': str(doc.id), 'dt': doc.id.generation_time.isoformat(), 'reason': doc.reason,
                'vehicle': {'VIN': doc.vehicle.id, 'tag': doc.vehicle.tag}, 'remarks': doc.remarks,
                'history': [{'oid': str(item.id) if item.length else None, 'dt': item.id.generation_time.isoformat(),
                             'description': item.description, 'content_type': item.content_type, 'length': item.length}
                            for item in doc.history]}

    @staticmethod
    def _get_doc(oid):
        try:
            doc = ParkingEventDocument.objects(id=mod_mongo.bson.objectid.ObjectId(oid)).first()
        except (TypeError, ValueError):
            doc = None
        if doc is None:
            raise ApiError(http.client.NOT_FOUND, 'Event not found')
        return doc

    def _run(self, operation):
        try:
            return operation()
        except ApiError as err:
            self._error(err.status, err.message)
        except (ValueError, TypeError):
            self._error(http.client.BAD_REQUEST, 'Invalid request')
