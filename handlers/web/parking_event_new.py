# -*- coding: utf-8 -*-

import datetime
import http.client
import json
import pycountry

import handlers.web.skeleton as mod_tmpl
import modules.mongo as mod_mongo
from modules.mongo.user import UserRef
from modules.mongo.agent import AgentRef
from modules.mongo.security import Ref as SecurityRef
from modules.mongo.vehicle import Document as VehicleDocument
from modules.mongo.vehicle import Ref as VehicleRef
from modules.mongo.parking_event import Document as ParkingEventDocument
from modules.mongo.parking_event import HistoryItem as ParkingEventHistoryItem
import handlers.web.decorator as deco
import handlers.ext.paramed_cgi

_vehicle_doc_class = VehicleDocument
_vehicle_doc_database =  mod_mongo.mongoengine.connection.get_db(_vehicle_doc_class._meta['db_alias']).name
_vehicle_doc_collection = _vehicle_doc_class._meta['collection']

class HandlerError(handlers.ext.paramed_cgi.HandlerError):
    pass


class Handler(handlers.ext.paramed_cgi.Handler):
    def get_ref(self) -> SecurityRef:
        session_agent = self.req.context.session_agent
        session_user = self.req.context.session_user

        return SecurityRef(
            agent=AgentRef(
                id=session_agent.id,
                name=session_agent.name,
                position=self.req.context.session.get('agent_position') or '',
            ),
            user=UserRef(
                id=session_user.id,
                name=session_user.name,
            ),
        )

    def execute(self) -> mod_mongo.bson.ObjectId:
        try:
            param_reason = self.cgi_params.param_post('reason')
            if not param_reason:
                raise self.cgi_params.NotFoundError()
        except self.cgi_params.NotFoundError:
            raise HandlerError('reason must be set')

        try:
            param_vin = self.cgi_params.param_post('VIN')
            if not param_vin:
                raise self.cgi_params.NotFoundError()
        except self.cgi_params.NotFoundError:
            raise HandlerError('VIN must be set')

        try:
            param_tag = self.cgi_params.param_post('tag')
            if not param_tag:
                raise self.cgi_params.NotFoundError()
        except self.cgi_params.NotFoundError:
            raise HandlerError('tag must be set')

        try:
            param_remarks = self.cgi_params.param_post('remarks')
        except self.cgi_params.NotFoundError:
            param_remarks = None

        vehicle_ref = VehicleRef()
        vehicle_ref.id = param_vin
        vehicle_ref.tag = param_tag
        doc = ParkingEventDocument()
        doc.id = mod_mongo.bson.objectid.ObjectId()
        doc.vehicle = vehicle_ref
        doc.reason = param_reason
        if param_remarks is not None:
            doc.remarks = param_remarks
        doc.creator = self.get_ref()
        doc.save()

        with mod_mongo.DbSessionController() as db_session:
            try:
                db_session[_vehicle_doc_database][_vehicle_doc_collection].update_one(
                    {'_id': param_vin},
                    {'$set': {'tag': param_tag}},
                    True
                )
            except mod_mongo.pymongo.errors.DuplicateKeyError:
                pass

        return doc.id

    @deco.session.Session()
    @deco.session.SessionUser()
    @deco.session.SessionAgent()
    @deco.auth.AuthRequired(render='html')
    def __call__(self):
        session_user = self.req.context.session_user
        if session_user is None:
            raise deco.auth.SecurityError('No current user selected')

        session_agent = self.req.context.session_agent
        if session_agent is None:
            raise deco.auth.SecurityError('No current agent selected')

        perm = 'parking.event/create'
        if not session_user.rbac_has_permission(perm):
            raise deco.auth.SecurityError('Permission required', perm)

        if self.req.method == 'POST':
            doc_oid = self.execute()

            import handlers.ext.redirect
            try:
                return handlers.ext.redirect.Handler(self.req)('/parking/event/view/%s' % str(doc_oid))
            except handlers.ext.redirect.HandlerError:
                raise HandlerError('Redirect error')

        tmpl_args = dict()
        content = mod_tmpl.TemplateFactory(self.req, 'parking_event_new').render(tmpl_args)
        self.req.setResponseCode(http.HTTPStatus.OK.value, http.HTTPStatus.OK.phrase)
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)
