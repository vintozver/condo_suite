# -*- coding: utf-8 -*-

import http.client

from ...handlers.ext.paramed_cgi import Handler as _Handler
from ...handlers.web import skeleton as mod_tmpl
from ...handlers.web import decorator as deco
from ...modules import mongo as mod_mongo
from ...modules.mongo.case import Case


class Handler(_Handler):
    @deco.session.Session()
    @deco.session.SessionUser()
    @deco.session.SessionAgent()
    @deco.auth.AuthRequired(render='html')
    def __call__(self, oid):
        user = self.req.context.session_user
        if not user.rbac_has_permission('case/view'):
            raise deco.auth.SecurityError('Permission required', 'case/view')
        doc = Case.objects(id=mod_mongo.bson.ObjectId(oid)).first()
        if doc is None:
            raise ValueError('Case not found')
        content = mod_tmpl.TemplateFactory(self.req, 'case_view').render({
            'oid': str(doc.id), 'title': doc.title, 'status': doc.status,
            'history': doc.history,
        })
        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)
