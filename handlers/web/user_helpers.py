# -*- coding: utf-8 -*-

import http.client
import json
import re

import config
import modules.mongo as mod_mongo
import handlers.web.decorator as deco
import handlers.ext.paramed_cgi


class HandlerError(handlers.ext.paramed_cgi.HandlerError):
    pass


class Handler(handlers.ext.paramed_cgi.Handler):
    def autocomplete_search(self, token):
        regex = re.compile('.*%s.*' % re.escape(token), re.IGNORECASE)
        with mod_mongo.DbSessionController() as db_session:
            db_documents = db_session[config.db_mongo.name]['users'].find({'name': {'$regex': regex}})

        result = list()
        for db_document in db_documents:
            result_item = {'id': str(db_document['_id']), 'name': db_document.get('name'), 'email': db_document.get('email')}
            result.append(result_item)
        return result

    def autocomplete_search_agent(self, token, user_id):
        regex = re.compile('.*%s.*' % re.escape(token), re.IGNORECASE)
        user_id = mod_mongo.bson.objectid.ObjectId(user_id)
        with mod_mongo.DbSessionController() as db_session:
            db_documents = db_session[config.db_mongo.name]['agent'].find({'name': {'$regex': regex}, 'closed': {'$exists': False}})

            result = list()
            for db_document in db_documents:
                agent_id = mod_mongo.bson.objectid.ObjectId(db_document['_id'])

                db_user = db_session[config.db_mongo.name]['users'].find_one({'_id': user_id}, {'agents': {'$elemMatch': {'_id': agent_id}}})

                position = ''
                if 'agents' in db_user and db_user['agents']:
                    position = db_user['agents'][0].get('position') or ''

                result_item = {
                    'id': str(db_document['_id']),
                    'name': db_document.get('name', ''),
                    'position': position
                }
                result.append(result_item)
            return result

    @deco.session.Session()
    @deco.session.SessionUser()
    @deco.auth.AuthRequired(render='json')
    def __call__(self, action, **kwargs):
        session_user = self.req.context.session_user
        if session_user is None:
            raise deco.auth.SecurityError('No user authenticated')

        if action == ('autocomplete', 'search'):
            perm = 'user/view'
            if not session_user.rbac_has_permission(perm):
                raise deco.auth.SecurityError('Permission required', perm)

            try:
                token = self.cgi_params.param_get('token')
                if not token:
                    raise self.cgi_params.NotFoundError()
            except self.cgi_params.NotFoundError:
                token = ''

            response = self.autocomplete_search(token)
        elif action == ('autocomplete', 'search', 'agent'):
            perm = 'user/view'
            if not session_user.rbac_has_permission(perm):
                raise deco.auth.SecurityError('Permission required', perm)

            try:
                token = self.cgi_params.param_get('token')
                if not token:
                    raise self.cgi_params.NotFoundError()
            except self.cgi_params.NotFoundError:
                token = ''

            try:
                user_id = self.cgi_params.param_get('user_id')
                if not user_id:
                    raise self.cgi_params.NotFoundError()
            except self.cgi_params.NotFoundError:
                user_id = ''

            response = self.autocomplete_search_agent(token, user_id)
        else:
            raise HandlerError('Unknown action', action)

        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'application/json')
        self.req.write(json.dumps(response))
