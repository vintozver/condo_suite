# -*- coding: utf-8 -*-

from ...handlers.ext.paramed_cgi import Handler as _Handler, HandlerError as _HandlerError

import io
from ... import config as config
from ...modules import mongo as mod_mongo
from ...modules.mongo.parking_event import Document as ParkingEventDocument
from ...modules.mongo.parking_event import HistoryItem as ParkingEventHistoryItem
from ...handlers.web import decorator as deco


class HandlerError(_HandlerError):
    pass


class Handler(_Handler):
    def execute(self, oid: mod_mongo.bson.objectid.ObjectId,
                description: str, stream: io.BytesIO, content_type: str):
        with mod_mongo.DbSessionController() as db_session:
            attachment_oid = mod_mongo.bson.objectid.ObjectId()

            if stream is not None and content_type is not None:
                history_file = mod_mongo.gridfs.GridFS(
                    db_session[config.name],
                    ParkingEventDocument._meta['collection'] + '.history'
                ).new_file(
                    _id=attachment_oid, content_type=content_type)
                history_file.write(stream.read())
                history_file.close()
            else:
                history_file = None

            with db_session.start_session() as session:
                def append_history(active_session):
                    history_item = ParkingEventHistoryItem(
                        id=mod_mongo.bson.objectid.ObjectId(),
                        description=description)
                    if history_file is not None:
                        history_item.file_id = attachment_oid
                        history_item.content_type = history_file.content_type
                        history_item.length = history_file.length
                    result = db_session[config.name][
                        ParkingEventDocument._meta['collection']].update_one(
                            {'_id': oid},
                            {'$push': {'history': history_item.to_mongo()}},
                            session=active_session)
                    if not result.matched_count:
                        raise HandlerError('Doc not found', oid)
                    return history_item.id
                history_id = session.with_transaction(append_history)

        return history_id

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

            from ...handlers.ext import redirect
            try:
                return redirect.Handler(self.req)('/parking/event/view/%s' % oid)
            except redirect.HandlerError:
                raise HandlerError('Redirect error')
        else:
            raise HandlerError('Method unsupported')
