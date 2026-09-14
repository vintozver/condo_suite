# -*- coding: utf-8 -*-

import http.client

from ...handlers.ext.paramed_cgi import Handler as _Handler
from ...handlers.web import skeleton as mod_tmpl
from ...handlers.web import decorator as deco
from ...modules.mongo.case import Case


class Handler(_Handler):
    @deco.session.Session()
    @deco.session.SessionUser()
    @deco.session.SessionAgent()
    @deco.auth.AuthRequired(render='html')
    def __call__(self):
        user = self.req.context.session_user
        if not user.rbac_has_permission('case/view'):
            raise deco.auth.SecurityError('Permission required', 'case/view')
        results = [{
            'oid': str(doc.id), 'title': doc.title, 'status': doc.status,
            'dt': doc.id.generation_time,
        } for doc in Case.objects().order_by('-_id')[:500]]
        content = mod_tmpl.TemplateFactory(self.req, 'case_search').render({'results': results})
        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)
