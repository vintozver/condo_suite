# -*- coding: utf-8 -*-

import http.client

from ...handlers.ext.paramed_cgi import Handler as _Handler
from ...handlers.web import skeleton as mod_tmpl
from ...handlers.web import decorator as deco
from ...modules import mongo as mod_mongo
from ...modules.mongo.case import Case
from ...modules.mongo.security import Ref as SecurityRef
from ...modules.mongo.user import UserRef
from ...modules.mongo.agent import AgentRef


class Handler(_Handler):
    def _ref(self):
        user, agent = self.req.context.session_user, self.req.context.session_agent
        return SecurityRef(user=UserRef(id=user.id, name=user.name),
                           agent=AgentRef(id=agent.id, name=agent.name, position=agent.position))

    @deco.session.Session()
    @deco.session.SessionUser()
    @deco.session.SessionAgent()
    @deco.auth.AuthRequired(render='html')
    def __call__(self):
        user = self.req.context.session_user
        if not user.rbac_has_permission('case/create'):
            raise deco.auth.SecurityError('Permission required', 'case/create')
        if self.req.method == 'POST':
            title = self.cgi_params.param_post('title')
            if not title:
                raise ValueError('title must be set')
            doc = Case(id=mod_mongo.bson.ObjectId(), title=title, creator=self._ref())
            doc.save()
            from ...handlers.ext import redirect
            return redirect.Handler(self.req)('/case/view/%s' % doc.id)
        content = mod_tmpl.TemplateFactory(self.req, 'case_new').render({})
        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)
