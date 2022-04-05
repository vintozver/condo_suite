# -*- coding: utf-8 -*-

import http.client
import config
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
    def __call__(self, doc_oid: str, file_oid: str):
        session_user = self.req.context.session_user
        if session_user is None:
            raise deco.auth.SecurityError('No user authenticated')

        session_agent = self.req.context.session_agent
        if session_agent is None:
            raise deco.auth.SecurityError('No agent selected')

        perm = 'parking.event/view'
        if not session_user.rbac_has_permission(perm):
            raise deco.auth.SecurityError('Permission required', perm)

        doc = ParkingEventDocument.objects(id=mod_mongo.bson.objectid.ObjectId(doc_oid)).get()
        if doc is None:
            raise HandlerError('Doc not found', id_doc)

        with mod_mongo.DbSessionController() as db_session:
            attachment_file = mod_mongo.gridfs.GridFS(db_session[config.db_mongo.name], 'parking_event.history').get(mod_mongo.bson.objectid.ObjectId(file_oid))

        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', attachment_file.content_type)
        self.req.write(attachment_file.read())
