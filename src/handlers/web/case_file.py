# -*- coding: utf-8 -*-

import http.client

from ... import config
from ...handlers.ext.paramed_cgi import Handler as _Handler
from ...handlers.web import decorator as deco
from ...modules import mongo as mod_mongo
from ...modules.mongo.case import Case


class Handler(_Handler):
    @deco.session.Session()
    @deco.session.SessionUser()
    @deco.session.SessionAgent()
    @deco.auth.AuthRequired(render='html')
    def __call__(self, doc_oid: str, file_oid: str):
        session_user = self.req.context.session_user
        if not session_user.rbac_has_permission('case/view'):
            raise deco.auth.SecurityError('Permission required', 'case/view')

        doc_id = mod_mongo.bson.ObjectId(doc_oid)
        attachment_id = mod_mongo.bson.ObjectId(file_oid)
        doc = Case.objects(id=doc_id).only('history').first()
        if doc is None:
            raise ValueError('Case not found')
        if not any(item.file_id == attachment_id for item in doc.history):
            raise ValueError('File not found')

        with mod_mongo.DbSessionController() as db_session:
            attachment_file = mod_mongo.gridfs.GridFS(db_session[config.name], 'case.history').get(attachment_id)

        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', attachment_file.content_type)
        self.req.setHeader('Content-Disposition', 'attachment')
        self.req.write(attachment_file.read())
