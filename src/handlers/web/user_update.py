# -*- coding: utf-8 -*-

from ...util.handler import Handler as _Handler, HandlerError as _HandlerError
import uuid
import json
import http.client
import base64
import binascii

from cryptography import exceptions as cryptography_exceptions
from cryptography import x509 as cryptography_x509
from cryptography.hazmat.primitives import serialization as cryptography_serialization

from ... import config as config

from ...modules import mongo as mod_mongo
from ...modules.mongo import user as mod_mongo_user
from ...modules.mongo import agent as mod_mongo_agent
from ...modules import rbac as mod_rbac
from ...handlers.web import decorator as deco
from ...util import handler


class HandlerError(_HandlerError):
    pass


class Handler(_Handler):
    @classmethod
    def process_info_set(cls, user, args):
        query_set = dict()
        if 'name' in args:
            query_set['name'] = args['name']
        if 'email' in args:
            query_set['email'] = args['email']

        if query_set:
            with mod_mongo.DbSessionController() as db_session:
                db_session[config.name]['users'].update_one({'_id': user.id}, {'$set': query_set})

    @classmethod
    def process_fido2_credential_id(cls, args):
        credential_id = args.get('id')
        if not credential_id or not isinstance(credential_id, str):
            raise HandlerError('Parameter error', 'id')
        try:
            return base64.urlsafe_b64decode(credential_id + '=' * (-len(credential_id) % 4))
        except (ValueError, binascii.Error):
            raise HandlerError('Parameter error', 'id')

    @classmethod
    def process_fido2_remove(cls, user, args):
        credential_id = cls.process_fido2_credential_id(args)
        with mod_mongo.DbSessionController() as db_session:
            db_session[config.name]['users'].update_one(
                {'_id': user.id},
                {'$pull': {'fido2_credentials': {'id': credential_id}}},
            )

    @classmethod
    def process_fido2_rename(cls, user, args):
        credential_id = cls.process_fido2_credential_id(args)
        name = args.get('name')
        if not isinstance(name, str):
            raise HandlerError('Parameter error', 'name')
        name = name.strip()
        if not name or len(name) > 128:
            raise HandlerError('Parameter error', 'name')
        with mod_mongo.DbSessionController() as db_session:
            db_session[config.name]['users'].update_one(
                {'_id': user.id, 'fido2_credentials.id': credential_id},
                {'$set': {'fido2_credentials.$.name': name}},
            )

    @classmethod
    def process_keyset_add(cls, user, args):
        key_id = args.get('id')
        if not isinstance(key_id, str) or not key_id or len(key_id) > 128:
            raise HandlerError('Parameter error', 'id')
        if any(item.id == key_id for item in user.keyset):
            raise HandlerError('A signing key with this id already exists', key_id)

        values = {}
        for field in ('pub', 'crt'):
            value = args.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            if not isinstance(value, str):
                raise HandlerError('Parameter error', field)
            values[field] = value
        if len(values) != 1:
            raise HandlerError('Exactly one of the public key or the certificate is required')

        item = {'id': key_id}
        if 'pub' in values:
            try:
                public_key = cryptography_serialization.load_pem_public_key(values['pub'].encode('ascii'))
            except (ValueError, TypeError, UnicodeEncodeError, cryptography_exceptions.UnsupportedAlgorithm):
                raise HandlerError('Parameter error', 'pub')
            item['pub'] = public_key.public_bytes(
                encoding=cryptography_serialization.Encoding.DER,
                format=cryptography_serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        else:
            try:
                certificate = cryptography_x509.load_pem_x509_certificate(values['crt'].encode('ascii'))
            except (ValueError, TypeError, UnicodeEncodeError, cryptography_exceptions.UnsupportedAlgorithm):
                raise HandlerError('Parameter error', 'crt')
            item['crt'] = certificate.public_bytes(encoding=cryptography_serialization.Encoding.DER)

        with mod_mongo.DbSessionController() as db_session:
            db_session[config.name]['users'].update_one(
                {'_id': user.id},
                {'$push': {'keyset': mod_mongo.bson.son.SON(item)}},
            )

    @classmethod
    def process_keyset_remove(cls, user, args):
        key_id = args.get('id')
        if not isinstance(key_id, str) or not key_id:
            raise HandlerError('Parameter error', 'id')
        with mod_mongo.DbSessionController() as db_session:
            db_session[config.name]['users'].update_one(
                {'_id': user.id}, {'$pull': {'keyset': {'id': key_id}}}
            )

    @classmethod
    def process_agent_args(cls, args):
        agent_id = args['agent_id']
        if not agent_id or not isinstance(agent_id, str):
            raise HandlerError('Parameter error', 'agent_id')
        agent_position = args['agent_position']
        if not agent_position or not isinstance(agent_position, str):
            agent_position = ''
        return mod_mongo.bson.objectid.ObjectId(agent_id), agent_position

    @classmethod
    def process_user_agent_get(cls, user, args):
        agent_id, agent_position = cls.process_agent_args(args)
        with mod_mongo.DbSessionController() as db_session:
            user = db_session[config.name]['users'].find_one({'_id': user.id, 'agents._id': agent_id})
            return {
                'name': user['agents'][0].get('name', ''),
                'position': user['agents'][0].get('position', ''),
            }

    @classmethod
    def process_user_agent_add(cls, user, args):
        agent_id, agent_position = cls.process_agent_args(args)
        agent = mod_mongo_agent.AgentDocument.objects(id=agent_id).get()
        if agent is None:
            raise HandlerError('Agent not found', agent_id)
        with mod_mongo.DbSessionController() as db_session:
            db_session[config.name]['users'].update_one({'_id': user.id},
                {'$push': {
                    'agents': mod_mongo.bson.son.SON({
                        '_id': agent.id,
                        'name': agent.name,
                        'position': agent_position
                    })
                }}
            )

    @classmethod
    def process_user_agent_remove(cls, user, args):
        agent_id, agent_position = cls.process_agent_args(args)
        with mod_mongo.DbSessionController() as db_session:
            db_session[config.name]['users'].update_one(
                {'_id': user.id}, {'$pull': {'agents': {'_id': agent_id}}}
            )

    @classmethod
    def process_user_agent_update(cls, user, args):
        agent_id, agent_position = cls.process_agent_args(args)
        with mod_mongo.DbSessionController() as db_session:
            agent = db_session[config.name]['users'].update_one(
                {'_id': user.id, 'agents._id': agent_id},
                {'$set': {'agents.$.position': agent_position}})
            return agent

    @classmethod
    def process_role_add(cls, user, role):
        # this handler takes the responsibility of adding the role. Security checks must be performed by caller
        with mod_mongo.DbSessionController() as db_session:
            db_session[config.name]['users'].update_one({'_id': user.id}, {'$push': {'rbac.roles': {
                '_id': role['uuid'], 'name': role.get('name'),
            }}})

    @classmethod
    def process_role_remove(cls, user, role):
        # this handler takes the responsibility of removing the role. Security checks must be performed by caller
        with mod_mongo.DbSessionController() as db_session:
            db_session[config.name]['users'].update_one({'_id': user.id}, {'$pull': {'rbac.roles': {
                '_id': role['uuid']
            }}})

    @deco.request_parser.RequestBodyParser()
    @deco.session.Session()
    @deco.session.SessionUser()
    @deco.auth.AuthRequired(render='json')
    def __call__(self, id_user):
        json_req = self.req.context.request_body_parser.as_json()

        session_user = self.req.context.session_user
        if session_user is None:
            raise deco.auth.SecurityError('No user authenticated')

        user = mod_mongo_user.UserDocument.objects(id=mod_mongo.bson.objectid.ObjectId(id_user)).get()
        if user is None:
            raise HandlerError('User not found', id_user)

        operation = json_req['op']
        args = json_req['args']
        result = {}
        if operation == 'info/set':
            perm = 'user.info/edit'
            if not session_user.rbac_has_permission(perm):
                raise deco.auth.SecurityError('Permission required', perm)
            self.process_info_set(user, args)
        elif operation == 'fido2/remove':
            if user.id == session_user.id:
                # users always manage their own credentials, an explicit confirmation is required
                if args.get('confirm') is not True:
                    raise HandlerError('Confirmation required to remove your own FIDO2 credential')
            else:
                perm = 'user.fido2/remove'
                if not session_user.rbac_has_permission(perm):
                    raise deco.auth.SecurityError('Permission required', perm)
            self.process_fido2_remove(user, args)
        elif operation == 'fido2/rename':
            # FIDO2 credentials can be renamed by their owner only
            if user.id != session_user.id:
                raise deco.auth.SecurityError('FIDO2 credentials can be renamed by their owner only')
            self.process_fido2_rename(user, args)
        elif operation == 'keyset/add':
            perm = 'user.keyset/add'
            if not session_user.rbac_has_permission(perm):
                raise deco.auth.SecurityError('Permission required', perm)
            self.process_keyset_add(user, args)
        elif operation == 'keyset/remove':
            perm = 'user.keyset/remove'
            if not session_user.rbac_has_permission(perm):
                raise deco.auth.SecurityError('Permission required', perm)
            self.process_keyset_remove(user, args)
        elif operation == 'agent/get':
            # if update action is allowed than we have to be able to get exists agent data from users collection
            perm = 'user.agent/update'
            if not session_user.rbac_has_permission(perm):
                raise deco.auth.SecurityError('Permission required', perm)
            result = self.process_user_agent_get(user, args)
        elif operation == 'agent/add':
            perm = 'user.agent/add'
            if not session_user.rbac_has_permission(perm):
                raise deco.auth.SecurityError('Permission required', perm)
            self.process_user_agent_add(user, args)
        elif operation == 'agent/remove':
            perm = 'user.agent/remove'
            if not session_user.rbac_has_permission(perm):
                raise deco.auth.SecurityError('Permission required', perm)
            self.process_user_agent_remove(user, args)
        elif operation == 'agent/update':
            perm = 'user.agent/update'
            if not session_user.rbac_has_permission(perm):
                raise deco.auth.SecurityError('Permission required', perm)
            self.process_user_agent_update(user, args)
        elif operation == 'role/add':
            role = mod_rbac.roles_by_uuid[uuid.UUID(args['id_role'])]
            if role.get('type') == 'admin':
                if user.id == session_user.id:
                    raise deco.auth.SecurityError('Administrative role management is forbidden for logged in user itself')
                perm = 'user.role(admin)/add'
            else:
                perm = 'user.role(regular)/add'
            if not session_user.rbac_has_permission(perm):
                raise deco.auth.SecurityError('Permission required', perm)
            self.process_role_add(user, role)
        elif operation == 'role/remove':
            role = mod_rbac.roles_by_uuid[uuid.UUID(args['id_role'])]
            if role.get('type') == 'admin':
                if user.id == session_user.id:
                    raise deco.auth.SecurityError('Administrative role management is forbidden for logged in user itself')
                perm = 'user.role(admin)/remove'
            else:
                perm = 'user.role(regular)/remove'
            if not session_user.rbac_has_permission(perm):
                raise deco.auth.SecurityError('Permission required', perm)
            self.process_role_remove(user, role)
        else:
            raise HandlerError('Operation is not supported', operation)

        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'application/json; charset=utf-8')
        self.req.write(json.dumps(result))
