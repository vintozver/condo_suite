# -*- coding: utf-8 -*-

from ...handlers.ext.paramed_cgi import Handler as _Handler, HandlerError as _HandlerError
import http.client

from ... import config as config
from ...handlers.web import skeleton as mod_tmpl
from ...modules.mongo.vehicle import Document as VehicleDocument
from ...modules.mongo.parking_event import Document as ParkingEventDocument
from ...handlers.web import decorator as deco


class HandlerError(_HandlerError):
    pass


class Handler(_Handler):
    @staticmethod
    def _description_upd(value):
        if not value:
            return None
        parts = []
        if value.by and value.by.user and value.by.user.name:
            parts.append(value.by.user.name)
        if value.by and value.by.agent and value.by.agent.name:
            agent = value.by.agent.name
            if value.by.agent.position:
                agent = '%s (%s)' % (agent, value.by.agent.position)
            parts.append(agent)
        return {'dt': value.dt, 'by': ' / '.join(parts)}

    @deco.session.Session()
    @deco.session.SessionUser()
    @deco.session.SessionAgent()
    @deco.auth.AuthRequired(render='html')
    def __call__(self, vin: str):
        session_user = self.req.context.session_user
        if session_user is None:
            raise deco.auth.SecurityError('No user authenticated')

        session_agent = self.req.context.session_agent
        if session_agent is None:
            raise deco.auth.SecurityError('No agent selected')

        perm = 'vehicle/view'
        if not session_user.rbac_has_permission(perm):
            raise deco.auth.SecurityError('Permission required', perm)

        perm = 'parking.event/view'
        if not session_user.rbac_has_permission(perm):
            raise deco.auth.SecurityError('Permission required', perm)

        doc = VehicleDocument.objects(id=vin).get()
        if doc is None:
            raise HandlerError('Item not found', vin)

        parking_event_list = list()
        for parking_event in ParkingEventDocument.objects(__raw__={'vehicle._id': vin}).order_by('-_id')[:100]:
            parking_event_item = dict()
            parking_event_item['oid'] = str(parking_event.id)
            parking_event_item['dt'] = parking_event.id.generation_time.astimezone(config.timezone)
            parking_event_item['reason'] = str(parking_event.reason)
            parking_event_item['tag'] = str(parking_event.vehicle.tag)
            parking_event_item['remarks'] = str(parking_event.remarks)
            parking_event_list.append(parking_event_item)
            del parking_event_item

        tmpl_data = dict()
        tmpl_data['VIN'] = vin
        tmpl_data['tag'] = doc.tag
        tmpl_data['description'] = doc.description
        tmpl_data['description_upd'] = self._description_upd(doc.description_upd)
        tmpl_data['parking_event_list'] = parking_event_list

        content = mod_tmpl.TemplateFactory(self.req, 'vehicle_view').render(tmpl_data)
        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)
