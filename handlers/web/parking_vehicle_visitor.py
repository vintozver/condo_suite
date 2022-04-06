# -*- coding: utf-8 -*-

import datetime
import dateutil.relativedelta
import http.client
from collections import OrderedDict

import config
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

        d_today = datetime.datetime.now(datetime.timezone.utc).astimezone(config.main.timezone).date()
        d_begin = d_today + dateutil.relativedelta.relativedelta(day=1)
        d_end = d_today + dateutil.relativedelta.relativedelta(day=1, months=1)
        dt_begin = datetime.datetime(d_begin.year, d_begin.month, d_begin.day, tzinfo=config.main.timezone).astimezone(datetime.timezone.utc)
        dt_end = datetime.datetime(d_end.year, d_end.month, d_end.day, tzinfo=config.main.timezone).astimezone(datetime.timezone.utc)

        visitor_aggregate_map = dict()
        parking_event_list = ParkingEventDocument.objects(__raw__={
            'reason': 'visitor',
            '_id': {'$gte': mod_mongo.bson.objectid.ObjectId.from_datetime(dt_begin), '$lt': mod_mongo.bson.objectid.ObjectId.from_datetime(dt_end)}
        })
        for parking_event in parking_event_list:
            parking_event_d = parking_event.id.generation_time.astimezone(config.main.timezone).date()
            parking_event_vin = parking_event.vehicle.id
            visitor_aggregate_map.setdefault(parking_event_vin, {})
            visitor_aggregate_map[parking_event_vin].setdefault(parking_event_d, 0)
            visitor_aggregate_map[parking_event_vin][parking_event_d] += 1

        visitor_aggregate_tuples = list(visitor_aggregate_map.items())
        visitor_aggregate_tuples.sort(key=lambda item: len(item[1]), reverse=True)
        visitor_aggregate_map = OrderedDict(visitor_aggregate_tuples)

        content = mod_tmpl.TemplateFactory(self.req, 'parking_vehicle_visitor').render({'visitor_aggregate_map': visitor_aggregate_map})
        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)
