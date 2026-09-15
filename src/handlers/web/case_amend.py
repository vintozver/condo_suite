# -*- coding: utf-8 -*-

import datetime
import http.client

from ...handlers.ext.paramed_cgi import Handler as _Handler
from ...handlers.web import decorator as deco
from ...modules import mongo as mod_mongo
from ... import config
from ...modules.mongo.case import Case, HistoryItem
from ...modules.mongo.security import Ref as SecurityRef
from ...modules.mongo.user import UserRef
from ...modules.mongo.agent import AgentRef
from ...handlers.defer import case as defer_case


class Handler(_Handler):
    def _ref(self):
        user, agent = self.req.context.session_user, self.req.context.session_agent
        return SecurityRef(user=UserRef(id=user.id, name=user.name),
                           agent=AgentRef(id=agent.id, name=agent.name, position=agent.position))

    @deco.session.Session()
    @deco.session.SessionUser()
    @deco.session.SessionAgent()
    @deco.auth.AuthRequired(render='html')
    def __call__(self, oid):
        user = self.req.context.session_user
        doc = Case.objects(id=mod_mongo.bson.ObjectId(oid)).first()
        if doc is None:
            raise ValueError('Case not found')
        action = self.cgi_params.param_post('action')
        if action == 'status':
            if not user.rbac_has_permission('case/status'):
                raise deco.auth.SecurityError('Permission required', 'case/status')
            status = self.cgi_params.param_post('status')
            if status not in ('open', 'progress', 'resolved', 'closed'):
                raise ValueError('Invalid status')
            doc.update(set__status=status)
        elif action == 'link':
            if not user.rbac_has_permission('case/link'):
                raise deco.auth.SecurityError('Permission required', 'case/link')
            case_ids = [doc.id] + [
                mod_mongo.bson.ObjectId(value)
                for value in self.cgi_params.paramlist_post('linked_case')]
            if len(case_ids) < 2 or len(set(case_ids)) != len(case_ids):
                raise ValueError('At least two different cases are required')
            if Case.objects(id__in=case_ids).count() != len(case_ids):
                raise ValueError('Invalid linked case')
            comment = self.cgi_params.param_post('comment')
            defer_case.case_link(case_ids, comment)
        else:
            if not user.rbac_has_permission('case/comment'):
                raise deco.auth.SecurityError('Permission required', 'case/comment')
            comment = self.cgi_params.param_post('comment')
            attachment = None
            try:
                attachment = self.cgi_params.file('attachment')
                if not attachment.filename:
                    attachment = None
            except self.cgi_params.NotFoundError:
                pass
            file_id = None
            if attachment is not None:
                file_id = mod_mongo.bson.ObjectId()
                with mod_mongo.DbSessionController() as db_session:
                    uploaded = mod_mongo.gridfs.GridFS(db_session[config.name], 'case.history').new_file(
                        _id=file_id, content_type=attachment.headers.get('Content-Type', 'application/octet-stream'))
                    uploaded.write(attachment.file.read())
                    uploaded.close()
            doc.update(push__history=HistoryItem(dt=datetime.datetime.now(datetime.timezone.utc), comment=comment,
                                                 file_id=file_id, creator=self._ref()))
        from ...handlers.ext import redirect
        return redirect.Handler(self.req)('/case/view/%s' % oid)
