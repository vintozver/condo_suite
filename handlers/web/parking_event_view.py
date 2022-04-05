# -*- coding: utf-8 -*-

import http.client

import handlers.web.skeleton as mod_tmpl
import modules.mongo as mod_mongo
from modules.mongo.parking_event import Document as ParkingEventDocument
import handlers.web.decorator as deco
import handlers.ext.paramed_cgi


class HandlerError(handlers.ext.paramed_cgi.HandlerError):
    pass


class Handler(handlers.ext.paramed_cgi.Handler):
    @deco.session.Session()
    @deco.session.SessionUser()
    @deco.session.SessionAgent()
    @deco.auth.AuthRequired(render='html')
    def __call__(self, oid):
        session_user = self.req.context.session_user
        if session_user is None:
            raise deco.auth.SecurityError('No user authenticated')

        session_agent = self.req.context.session_agent
        if session_agent is None:
            raise deco.auth.SecurityError('No agent selected')

        perm = 'parking.event/view'
        if not session_user.rbac_has_permission(perm):
            raise deco.auth.SecurityError('Permission required', perm)

        doc = ParkingEventDocument.objects(id=mod_mongo.bson.objectid.ObjectId(oid)).get()
        if doc is None:
            raise HandlerError('Item not found', id_doc)

        tmpl_data = dict()
        tmpl_data['oid'] = doc.id
        tmpl_data['dt'] = doc.id.generation_time
        tmpl_data['reason'] = doc.reason
        tmpl_data['VIN'] = doc.vehicle.id
        tmpl_data['tag'] = doc.vehicle.tag
        tmpl_data['remarks'] = doc.remarks
        tmpl_data['history'] = list({
            'oid': str(history_item.id) if history_item.length else None,
            'dt': history_item.id.generation_time,
            'description': history_item.description
        } for history_item in doc.history)

        content = mod_tmpl.TemplateFactory(self.req, 'parking_event_view').render(tmpl_data)
        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)
