# -*- coding: utf-8 -*-

import datetime
import http.client
import json
import pycountry
import config
import handlers.web.skeleton as mod_tmpl
import modules.mongo as mod_mongo
import handlers.web.decorator as deco
import util.handler


class HandlerError(util.handler.HandlerError):
    pass


class Handler(util.handler.Handler):
    @deco.session.Session()
    @deco.session.SessionUser()
    @deco.auth.AuthRequired(render='html')
    def view(self):
        session_user = self.req.context.session_user
        if session_user is None:
            raise deco.auth.SecurityError('No user authenticated')

        # Check permissions
        perm = 'agent/view'
        if not session_user.rbac_has_permission(perm):
            raise deco.auth.SecurityError('Permission required', perm)

        def query_agent_list():
            with mod_mongo.DbSessionController() as db_session:
                for db_doc in db_session[config.db_mongo.name]['agent'].find({'closed': {'$exists': False}}):
                    yield {'id': str(db_doc['_id']), 'name': db_doc.get('name')}

        content = mod_tmpl.TemplateFactory(self.req, 'agent_edit').render({
            'agent_list': list(query_agent_list()),
            'country_list': [{'code': country.alpha_2, 'name': country.name} for country in pycountry.countries],
            'perm_create': session_user.rbac_has_permission('agent/create'),
            'perm_update': session_user.rbac_has_permission('agent/update'),
            'perm_close': session_user.rbac_has_permission('agent/close'),
        })
        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)

    @deco.request_parser.RequestBodyParser()
    @deco.session.Session()
    @deco.session.SessionUser()
    @deco.auth.AuthRequired(render='json')
    def update(self):
        json_req = self.req.context.request_body_parser.as_json()

        session_user = self.req.context.session_user
        if session_user is None:
            raise deco.auth.SecurityError('No user authenticated')

        operation = json_req['op']
        args = json_req['args']
        result = dict()
        if operation == 'create':
            perm = 'agent/create'
            if not session_user.rbac_has_permission(perm):
                raise deco.auth.SecurityError('Permission required', perm)
            name = args.get('name')
            if not name:
                raise HandlerError('Parameter is mandatory', name)
            id_agent = self.process_create(name, args.get('address'))
            result['id'] = str(id_agent)
        elif operation == 'close':
            perm = 'agent/close'
            if not session_user.rbac_has_permission(perm):
                raise deco.auth.SecurityError('Permission required', perm)
            closed = self.process_close(mod_mongo.bson.objectid.ObjectId(args['id']))
            result['closed'] = closed
        elif operation == 'update':
            perm = 'agent/update'
            if not session_user.rbac_has_permission(perm):
                raise deco.auth.SecurityError('Permission required', perm)
            name = args.get('name')
            if not name:
                raise HandlerError('Parameter is mandatory', name)
            result['updated'] = self.process_update(mod_mongo.bson.objectid.ObjectId(args['id']), name, args.get('address'))
        elif operation == 'get':
            perm = 'agent/view'
            if not session_user.rbac_has_permission(perm):
                raise deco.auth.SecurityError('Permission required', perm)
            agent = self.process_get(mod_mongo.bson.objectid.ObjectId(args['id']))
            result['id'] = str(agent['_id'])
            result['name'] = agent.get('name')
            result['address'] = agent.get('address')
        else:
            raise HandlerError('Operation is not supported', operation)

        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'application/json; charset=utf-8')
        self.req.write(json.dumps(result))

    @classmethod
    def process_create(cls, name, address):
        agent = mod_mongo.bson.son.SON()
        agent['name'] = name
        if address:
            agent_address = mod_mongo.bson.son.SON()
            agent_address['street'] = address['street']
            agent_address['city'] = address['city']
            agent_address['postal_code'] = address['postal_code']
            agent_address['country'] = address['country']
            agent['address'] = agent_address
            del agent_address
        with mod_mongo.DbSessionController() as db_session:
            return db_session[config.db_mongo.name]['agent'].insert_one(agent).inserted_id

    @classmethod
    def process_update(cls, id_agent, name, address):
        agent = mod_mongo.bson.son.SON()
        agent['name'] = name
        if address:
            agent_address = mod_mongo.bson.son.SON()
            agent_address['street'] = address['street']
            agent_address['city'] = address['city']
            agent_address['postal_code'] = address['postal_code']
            agent_address['country'] = address['country']
            agent['address'] = agent_address
            del agent_address
        with mod_mongo.DbSessionController() as db_session:
            return db_session[config.db_mongo.name]['agent'].update_one({'_id': id_agent}, {'$set': agent}).modified_count > 0

    @classmethod
    def process_close(cls, id_agent):
        with mod_mongo.DbSessionController() as db_session:
            return bool(db_session[config.db_mongo.name]['agent'].update_one({'_id': id_agent, 'closed': {'$exists': False}}, {'$set': {'closed': datetime.datetime.utcnow()}}).modified_count)

    @classmethod
    def process_get(cls, id_agent):
        with mod_mongo.DbSessionController() as db_session:
            agent = db_session[config.db_mongo.name]['agent'].find_one({'_id': id_agent, 'closed': {'$exists': False}})
            if agent is None:
                raise HandlerError('Agent not found', id_agent)
            return agent

    def __call__(self):
        req_method = self.req.method
        if req_method == 'GET':
            return self.view()
        elif req_method == 'POST':
            return self.update()
        else:
            raise HandlerError('Method is not supported', req_method)
