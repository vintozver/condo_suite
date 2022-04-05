# -*- coding: utf-8 -*-

import collections
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
    @deco.session.Session()
    @deco.session.SessionUser()
    @deco.session.SessionAgent()
    def autocomplete_filter(self):
        session_user = self.req.context.session_user
        if session_user is None:
            raise deco.auth.SecurityError('Permission required', None)

        session_agent = self.req.context.session_agent
        if session_agent is None:
            raise deco.auth.SecurityError('Permission required', None)

        return {}

    def autocomplete_vin(self, token):
        regex = re.compile('.*%s.*' % re.escape(token), re.IGNORECASE)
        match_query = {'_id': {'$regex': regex}}
        match_query.update(self.autocomplete_filter())
        with mod_mongo.DbSessionController() as db_session:
            db_documents = db_session[config.db_mongo.name]['vehicle'].aggregate([
                {'$match': match_query},
            ])

        for db_document in db_documents:
            yield {'VIN': db_document.get('_id'), 'tag': db_document.get('tag')}

    def autocomplete_tag(self, token):
        regex = re.compile('.*%s.*' % re.escape(token), re.IGNORECASE)
        match_query = {'tag': {'$regex': regex}}
        match_query.update(self.autocomplete_filter())
        with mod_mongo.DbSessionController() as db_session:
            db_documents = db_session[config.db_mongo.name]['vehicle'].aggregate([
                {'$match': match_query},
            ])

        for db_document in db_documents:
            yield {'VIN': db_document.get('_id'), 'tag': db_document.get('tag')}

    @deco.auth.AuthRequired(render='json')
    def __call__(self, action, **kwargs):
        action_0 = action[0]
        if action_0 == 'autocomplete':
            try:
                token = self.cgi_params.param_get('token')
                if not token:
                    raise self.cgi_params.NotFoundError()
            except self.cgi_params.NotFoundError:
                token = ''

            action_1 = action[1]
            if action_1 == 'VIN':
                if len(token) > 3:
                    response = list(self.autocomplete_vin(token))
                else:
                    response = []
            elif action_1 == 'tag':
                if len(token) > 2:
                    response = list(self.autocomplete_tag(token))
                else:
                    response = []
            else:
                raise HandlerError('Unknown action', action)
        else:
            raise HandlerError('Unknown action', action)

        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'application/json')
        self.req.write(json.dumps(response))
