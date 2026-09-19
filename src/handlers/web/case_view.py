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
        link_ids = [item.link for item in doc.history if item.link]
        linked_titles = {
            linked_doc.id: linked_doc.title
            for linked_doc in Case.objects(id__in=link_ids).only('id', 'title')
        } if link_ids else {}
        history = [{
            'dt': item.dt,
            'comment': item.comment,
            'file_id': str(item.file_id) if item.file_id else None,
            'link': {
                'oid': str(item.link),
                'title': linked_titles.get(item.link, str(item.link)),
            } if item.link else None,
            'by': self._creator(item.creator),
        } for item in doc.history]
        content = mod_tmpl.TemplateFactory(self.req, 'case_view').render({
            'oid': str(doc.id), 'title': doc.title, 'status': doc.status,
            'history': history,
        })
        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)

    @staticmethod
    def _creator(creator):
        if not creator:
            return ''
        parts = []
        if creator.user and creator.user.name:
            parts.append(creator.user.name)
        if creator.agent and creator.agent.name:
            agent = creator.agent.name
            if creator.agent.position:
                agent = '%s (%s)' % (agent, creator.agent.position)
            parts.append(agent)
        return ' / '.join(parts)
