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
from ....modules.mongo.parking_event import HistoryItem
from ....modules.mongo.security import Ref as SecurityRef
from ....modules.mongo.user import UserRef, UserDocument
from ....handlers.ext.paramed_cgi import Handler as _Handler, HandlerError as _HandlerError


class HandlerError(_HandlerError):
    pass


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class Handler(_Handler):
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
        if not isinstance(header, dict):
            raise ApiError(http.client.UNAUTHORIZED, 'Invalid token')
        uid, kid, dt, algorithm = (header.get(name) for name in ('uid', 'kid', 'dt', 'alg'))
        if not uid or not kid or not dt or not algorithm:
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
            user = UserDocument.objects(id=mod_mongo.bson.objectid.ObjectId(str(uid))).first()
        except (TypeError, ValueError):
            user = None
        if user is None:
            raise ApiError(http.client.UNAUTHORIZED, 'Unknown user')
        key = next((item for item in user.keyset if item.id == kid), None)
        if key is None or bool(key.pub) == bool(key.crt) or algorithm not in self.JWT_ALGORITHMS:
            raise ApiError(http.client.UNAUTHORIZED, 'Unknown signing key')
        try:
            public_key = serialization.load_der_public_key(key.pub) if key.pub else x509.load_der_x509_certificate(key.crt).public_key()
            payload = jwt.decode(token[7:], public_key, algorithms=[algorithm], options={'verify_aud': False})
        except (ValueError, TypeError, jwt.InvalidTokenError):
            raise ApiError(http.client.UNAUTHORIZED, 'Invalid signature')
        return user, payload

    @staticmethod
    def _body(payload):
        body = payload.get('body', payload)
        return body if isinstance(body, dict) else {}

    @staticmethod
    def _event(doc):
        return {
            'oid': str(doc.id),
            'dt': doc.id.generation_time.isoformat(),
            'reason': doc.reason,
            'vehicle': {'VIN': doc.vehicle.id, 'tag': doc.vehicle.tag},
            'remarks': doc.remarks,
            'history': [
                {'oid': str(item.id) if item.length else None, 'dt': item.id.generation_time.isoformat(),
                 'description': item.description, 'content_type': item.content_type, 'length': item.length}
                for item in doc.history
            ],
        }

    def _get_doc(self, oid):
        try:
            doc = ParkingEventDocument.objects(id=mod_mongo.bson.objectid.ObjectId(oid)).first()
        except (TypeError, ValueError):
            doc = None
        if doc is None:
            raise ApiError(http.client.NOT_FOUND, 'Event not found')
        return doc

    def __call__(self, action, oid=None, file_oid=None):
        try:
            user, payload = self._authenticate()
            body = self._body(payload)
            if action == 'event' and oid is not None:
                action = 'comment' if self.req.method == 'POST' else 'view'
            if action == 'search':
                if not user.rbac_has_permission('parking.event/view'):
                    raise ApiError(http.client.FORBIDDEN, 'Permission required')
                query = ParkingEventDocument.objects()
                if body.get('VIN'):
                    query = query.filter(vehicle__id=body['VIN'])
                if body.get('tag'):
                    query = query.filter(vehicle__tag=body['tag'])
                if body.get('reason'):
                    query = query.filter(reason=body['reason'])
                limit = min(max(int(body.get('limit', 100)), 1), 500)
                self._json({'events': [self._event(doc) for doc in query.order_by('-_id')[:limit]]})
                return

            doc = self._get_doc(oid)
            if action == 'view':
                if not user.rbac_has_permission('parking.event/view'):
                    raise ApiError(http.client.FORBIDDEN, 'Permission required')
                self._json(self._event(doc))
            elif action == 'file':
                if not user.rbac_has_permission('parking.event/view'):
                    raise ApiError(http.client.FORBIDDEN, 'Permission required')
                try:
                    file_id = mod_mongo.bson.objectid.ObjectId(file_oid)
                except (TypeError, ValueError):
                    raise ApiError(http.client.NOT_FOUND, 'File not found')
                if not any(item.id == file_id and item.length for item in doc.history):
                    raise ApiError(http.client.NOT_FOUND, 'File not found')
                with mod_mongo.DbSessionController() as db_session:
                    attachment = mod_mongo.gridfs.GridFS(db_session[config.name], 'parking_event.history').get(
                        file_id)
                    self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
                    self.req.setHeader('Content-Type', attachment.content_type)
                    self.req.write(attachment.read())
            elif action == 'comment':
                if not user.rbac_has_permission('parking.event/comment'):
                    raise ApiError(http.client.FORBIDDEN, 'Permission required')
                description = body.get('description')
                if not isinstance(description, str) or not description:
                    raise ApiError(http.client.BAD_REQUEST, 'description must be set')
                item = HistoryItem(id=mod_mongo.bson.objectid.ObjectId(), description=description, creator=SecurityRef(user=UserRef(id=user.id, name=user.name)))
                with mod_mongo.DbSessionController() as db_session:
                    db_session[config.name]['parking_event'].update_one({'_id': doc.id}, {'$push': {'history': item.to_mongo()}})
                self._json({'event': str(doc.id), 'history': str(item.id)}, http.client.CREATED)
            else:
                raise ApiError(http.client.NOT_FOUND, 'Unknown API action')
        except ApiError as err:
            self._error(err.status, err.message)
        except (ValueError, TypeError):
            self._error(http.client.BAD_REQUEST, 'Invalid request')
