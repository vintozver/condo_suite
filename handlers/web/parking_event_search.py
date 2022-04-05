# -*- coding: utf-8 -*-

import http.client

import config
import handlers.web.skeleton as mod_tmpl
from modules.mongo.parking_event import Document as ParkingEventDocument
import handlers.web.decorator as deco
import handlers.ext.paramed_cgi


class HandlerError(handlers.ext.paramed_cgi.HandlerError):
    pass


class Handler(handlers.ext.paramed_cgi.Handler):
    PAGE_SIZE = 100

    @deco.session.Session()
    @deco.session.SessionUser()
    @deco.session.SessionAgent()
    @deco.auth.AuthRequired(render='html')
    def __call__(self):
        session_user = self.req.context.session_user
        if session_user is None:
            raise deco.auth.SecurityError('No user authenticated')

        session_agent = self.req.context.session_agent
        if session_agent is None:
            raise deco.auth.SecurityError('No agent selected')

        perm = 'parking.event/view'
        if not session_user.rbac_has_permission(perm):
            raise deco.auth.SecurityError('Permission required', perm)

        results = list()

        docs = ParkingEventDocument.objects().order_by('-_id')[:500]
        for doc in docs:
            doc_data = dict()
            doc_data['oid'] = str(doc.id)
            doc_data['dt'] = doc.id.generation_time.astimezone(config.main.timezone)
            doc_data['reason'] = str(doc.reason)
            doc_data['VIN'] = str(doc.vehicle.id)
            doc_data['tag'] = str(doc.vehicle.tag)
            results.append(doc_data)
            del doc_data

        content = mod_tmpl.TemplateFactory(self.req, 'parking_event_search').render({'results': results})
        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)
