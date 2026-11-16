# -*- coding: utf-8 -*-

from datetime import datetime
import http.client
import re

from ... import config
from ...handlers.ext.paramed_cgi import Handler as _Handler
from ...handlers.web import decorator as deco
from ...handlers.web import skeleton as mod_tmpl
from ...modules.mongo.parking_event import Document as ParkingEventDocument
from .parking_notice_pdf import generate_notice


class Handler(_Handler):
    @deco.session.Session()
    @deco.session.SessionUser()
    @deco.session.SessionAgent()
    @deco.auth.AuthRequired(render='html')
    def __call__(self):
        session_user = self.req.context.session_user
        if session_user is None:
            raise deco.auth.SecurityError('No user authenticated')
        if self.req.context.session_agent is None:
            raise deco.auth.SecurityError('No agent selected')
        perm = 'parking.event/view'
        if not session_user.rbac_has_permission(perm):
            raise deco.auth.SecurityError('Permission required', perm)

        self.req.setHeader('Cache-Control', 'private, no-store')
        if self.req.method not in ('GET', 'POST'):
            self.req.setResponseCode(405, 'Method Not Allowed')
            self.req.setHeader('Allow', 'GET, POST')
            return

        param = self.cgi_params.param_post if self.req.method == 'POST' else self.cgi_params.param_get
        values = {}
        for name in ('vin', 'tag', 'reason'):
            try:
                values[name] = param(name) or ''
            except self.cgi_params.NotFoundError:
                values[name] = ''
        values['vin'] = values['vin'].strip().upper()
        values['tag'] = values['tag'].strip()
        values['reason'] = values['reason'].strip()

        error = None
        if self.req.method == 'POST':
            if not re.fullmatch(r'[0-9A-HJ-NPR-Z]{17}', values['vin']):
                error = 'Enter a valid 17-character VIN.'
            elif not values['tag'] or len(values['tag']) > 20:
                error = 'Enter a tag of 1 to 20 characters.'
            elif not values['reason'] or len(values['reason']) > 500:
                error = 'Enter a reason of 1 to 500 characters.'
            else:
                events = [{
                    'dt': event.id.generation_time.astimezone(config.timezone),
                    'tag': event.vehicle.tag,
                    'reason': event.reason,
                    'remarks': event.remarks,
                } for event in ParkingEventDocument.objects(
                    __raw__={'vehicle._id': values['vin']}).order_by('-id')[:20]]
                content = generate_notice(
                    config.business_name, values['vin'], values['tag'], values['reason'],
                    datetime.now(config.timezone), events)
                self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
                self.req.setHeader('Content-Type', 'application/pdf')
                self.req.setHeader('Content-Disposition', 'attachment; filename="parking-notice.pdf"')
                self.req.write(content)
                return

        values['error'] = error
        content = mod_tmpl.TemplateFactory(self.req, 'parking_notice').render(values)
        status = http.client.BAD_REQUEST if error else http.client.OK
        self.req.setResponseCode(status, http.client.responses[status])
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)
