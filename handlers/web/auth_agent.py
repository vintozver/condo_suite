# -*- coding: utf-8 -*-

import http.client

import handlers.web.skeleton as mod_tmpl
import modules.mongo.agent as mod_mongo_agent
import handlers.web.decorator as deco
import handlers.ext.paramed_cgi


class HandlerError(handlers.ext.paramed_cgi.HandlerError):
    pass


class Handler(handlers.ext.paramed_cgi.Handler):
    @deco.session.Session()
    @deco.session.SessionUser()
    def check(self):
        session = self.req.context.session
        session_user = self.req.context.session_user
        # if user is not logged in or if it's logged in and agent selection is set - do nothing
        if session_user is None or 'id_agent' in session:
            return False
        # Current logged in user has not selected agent yet. If the user has the only agent assigned, select the agent automatically
        agents = session_user.agents
        if len(agents) == 1:
            session['id_agent'] = agents[0].id
            session['agent_position'] = agents[0].position
        else:
            # save "no selection" indication
            session['id_agent'] = None
            session['agent_position'] = None
        session.save()
        return True

    @deco.session.Session()
    @deco.session.SessionUser()
    @deco.session.SessionAgent()
    def view(self):
        session_user = self.req.context.session_user
        session_agent = self.req.context.session_agent

        if session_user is not None:
            agent_list = session_user.agents
        else:
            agent_list = list()

        content = content = mod_tmpl.TemplateFactory(self.req, 'auth_agent').render({'agent_list': agent_list, 'current_user': session_user, 'current_agent': session_agent})
        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)

    def __call__(self):
        self.check()
        return self.view()
