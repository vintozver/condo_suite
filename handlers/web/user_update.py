# -*- coding: utf-8 -*-

import uuid
import json
import http.client

import config

import modules.mongo as mod_mongo
import modules.mongo.user as mod_mongo_user
import modules.mongo.agent as mod_mongo_agent
import modules.rbac as mod_rbac
import handlers.web.decorator as deco
import util.handler


class HandlerError(util.handler.HandlerError):
    pass


class Handler(util.handler.Handler):
    @classmethod
    def process_info_set(cls, user, args):
        query_set = dict()
        if 'name' in args:
            query_set['name'] = args['name']
        if 'email' in args:
            query_set['email'] = args['email']

        if query_set:
            with mod_mongo.DbSessionController() as db_session:
                db_session[config.db_mongo.name]['users'].update_one({'_id': user.id}, {'$set': query_set})

    @classmethod
    def process_ssl_crt_args(cls, args):
        serial = args['serial']
        if not serial or not isinstance(serial, str):
            raise HandlerError('Parameter error', 'serial')
        subject_dn = args['subject_dn']
        if not subject_dn or not isinstance(subject_dn, str):
            raise HandlerError('Parameter error', 'subject_dn')
        issuer_dn = args['issuer_dn']
        if not issuer_dn or not isinstance(issuer_dn, str):
            raise HandlerError('Parameter error', 'issuer_dn')
        return serial, subject_dn, issuer_dn

    @classmethod
    def process_ssl_crt_add(cls, user, args):
        serial, subject_dn, issuer_dn = cls.process_ssl_crt_args(args)
        with mod_mongo.DbSessionController() as db_session:
            db_session[config.db_mongo.name]['users'].update_one({'_id': user.id}, {'$push': {'ssl_crt': {
                'serial': serial, 'subject_dn': subject_dn, 'issuer_dn': issuer_dn,
            }}})

    @classmethod
    def process_ssl_crt_remove(cls, user, args):
        serial, subject_dn, issuer_dn = cls.process_ssl_crt_args(args)
        with mod_mongo.DbSessionController() as db_session:
            db_session[config.db_mongo.name]['users'].update_one({'_id': user.id}, {'$pull': {'ssl_crt': {
                'serial': serial, 'subject_dn': subject_dn, 'issuer_dn': issuer_dn,
            }}}, multi=True)

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
            user = db_session[config.db_mongo.name]['users'].find_one({'_id': user.id, 'agents._id': agent_id})
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
            db_session[config.db_mongo.name]['users'].update_one({'_id': user.id},
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
            db_session[config.db_mongo.name]['users'].update_one(
                {'_id': user.id}, {'$pull': {'agents': {'_id': agent_id}}},
                multi=True
            )

    @classmethod
    def process_user_agent_update(cls, user, args):
        agent_id, agent_position = cls.process_agent_args(args)
        with mod_mongo.DbSessionController() as db_session:
            agent = db_session[config.db_mongo.name]['users'].update_one(
                {'_id': user.id, 'agents._id': agent_id},
                {'$set': {'agents.$.position': agent_position}},
                multi=True)
            return agent

    @classmethod
    def process_role_add(cls, user, role):
        # this handler takes the responsibility of adding the role. Security checks must be performed by caller
        with mod_mongo.DbSessionController() as db_session:
            db_session[config.db_mongo.name]['users'].update_one({'_id': user.id}, {'$push': {'rbac.roles': {
                '_id': role['uuid'], 'name': role.get('name'),
            }}})

    @classmethod
    def process_role_remove(cls, user, role):
        # this handler takes the responsibility of removing the role. Security checks must be performed by caller
        with mod_mongo.DbSessionController() as db_session:
            db_session[config.db_mongo.name]['users'].update_one({'_id': user.id}, {'$pull': {'rbac.roles': {
                '_id': role['uuid']
            }}}, multi=True)

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
        elif operation == 'ssl_crt/add':
            perm = 'user.ssl_crt/add'
            if not session_user.rbac_has_permission(perm):
                raise deco.auth.SecurityError('Permission required', perm)
            self.process_ssl_crt_add(user, args)
        elif operation == 'ssl_crt/remove':
            perm = 'user.ssl_crt/remove'
            if not session_user.rbac_has_permission(perm):
                raise deco.auth.SecurityError('Permission required', perm)
            self.process_ssl_crt_remove(user, args)
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
