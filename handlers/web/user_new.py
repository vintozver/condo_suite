# -*- coding: utf-8 -*-

import json
import http.client

import config

import modules.mongo as mod_mongo
import handlers.web.decorator as deco
import util.handler


class HandlerError(util.handler.HandlerError):
    pass


class Handler(util.handler.Handler):
    @classmethod
    def process_user_create(cls, user_name):
        user = mod_mongo.bson.son.SON()
        user['name'] = user_name
        with mod_mongo.DbSessionController() as db_session:
            return db_session[config.db_mongo.name]['users'].insert_one(user).inserted_id

    @deco.request_parser.RequestBodyParser()
    @deco.session.Session()
    @deco.session.SessionUser()
    @deco.auth.AuthRequired(render='json')
    def __call__(self):
        json_req = self.req.context.request_body_parser.as_json()

        session_user = self.req.context.session_user
        if session_user is None:
            raise deco.auth.SecurityError('No user authenticated')

        perm = "user/create"
        if not session_user.rbac_has_permission(perm):
            raise deco.auth.SecurityError('Permission required', perm)
        user_name = json_req.get('name')
        if not user_name:
            raise HandlerError('user name is empty string')

        user_id = self.process_user_create(user_name)
        result = {'id': str(user_id)}

        self.req.setResponseCode(http.client.CREATED, http.client.responses[http.client.CREATED])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'application/json; charset=utf-8')
        self.req.write(json.dumps(result))
