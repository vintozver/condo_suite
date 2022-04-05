# -*- coding: utf-8 -*-

import os

import io
import http.client
import config
import handlers.web.skeleton as mod_tmpl
import modules.mongo as mod_mongo
from modules.mongo.parking_event import Document as ParkingEventDocument
from modules.mongo.parking_event import HistoryItem as ParkingEventHistoryItem
import handlers.web.decorator as deco
import handlers.ext.paramed_cgi


class HandlerError(handlers.ext.paramed_cgi.HandlerError):
    pass


class Handler(handlers.ext.paramed_cgi.Handler):
    def execute(self, oid: mod_mongo.bson.objectid.ObjectId, description: str, stream: io.BytesIO, content_type: str):
        with mod_mongo.DbSessionController() as db_session:
            attachment_oid = mod_mongo.bson.objectid.ObjectId()

            if stream is not None and content_type is not None:
                history_file = mod_mongo.gridfs.GridFS(db_session[config.db_mongo.name], 'parking_event.history').new_file(_id=attachment_oid, content_type=content_type)
                history_file.write(stream.read())
                history_file.close()
            else:
                history_file = None

            history_item = ParkingEventHistoryItem()
            history_item.id = attachment_oid
            if history_file is not None:
                history_item.content_type = history_file.content_type
                history_item.length = history_file.length
            history_item.description = description
            
            db_session[config.db_mongo.name]['parking_event'].update_one({'_id': oid}, {'$push': {'history': history_item.to_mongo()}})

        return attachment_oid

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

        perm = 'parking.event/comment'
        if not session_user.rbac_has_permission(perm):
            raise deco.auth.SecurityError('Permission required', perm)

        doc = ParkingEventDocument.objects(id=mod_mongo.bson.objectid.ObjectId(oid)).get()
        if doc is None:
            raise HandlerError('Doc not found', oid)

        if self.req.method == 'POST':
            try:
                description = self.cgi_params.param_post('description')
            except self.cgi_params.NotFoundError:
                description = None

            try:
                attachment = self.cgi_params.file('attachment')
                if not attachment.filename:
                    raise self.cgi_params.NotFoundError()
                attachment = attachment.file
                if not attachment:
                    raise self.cgi_params.NotFoundError()
            except self.cgi_params.NotFoundError:
                attachment = None

            if attachment is not None:
                attachment_stream = io.BytesIO(attachment.read())

                import imghdr
                attachment_imgtype = imghdr.what('', attachment_stream.read(256))
                if not attachment_imgtype:
                    HandlerError('Unrecognized attachment image')
                attachment_stream.seek(0)
                content_type = 'image/%s' % attachment_imgtype
                del attachment_imgtype
            else:
                attachment_stream = None
                content_type = None

            self.execute(doc.id, description, attachment_stream, content_type)

            import handlers.ext.redirect
            try:
                return handlers.ext.redirect.Handler(self.req)('/parking/event/view/%s' % oid)
            except handlers.ext.redirect.HandlerError:
                raise HandlerError('Redirect error')
        else:
            raise HandlerError('Method unsupported')

