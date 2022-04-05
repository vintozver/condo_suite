# -*- coding: utf-8 -*-

import http.client
import json

import handlers.web.decorator as deco
import handlers.ext.paramed_cgi


class HandlerError(handlers.ext.paramed_cgi.HandlerError):
    pass


class Handler(handlers.ext.paramed_cgi.Handler):
    @deco.session.Session()
    @deco.session.SessionUser()
    @deco.session.SessionAgent()
    def __call__(self):
        response = dict()

        context = self.req.context
        session_user = context.session_user
        if session_user is not None:
            response['user'] = {'id': str(session_user.id), 'name': session_user.name}
        else:
            response['user'] = {}
        session_agent = context.session_agent
        if session_agent is not None:
            response['agent'] = {'id': str(session_agent.id), 'name': session_agent.name}
        else:
            response['agent'] = {}

        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'application/json')
        self.req.write(json.dumps(response))
