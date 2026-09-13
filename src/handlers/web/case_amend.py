# -*- coding: utf-8 -*-

import datetime
import http.client

from ...handlers.ext.paramed_cgi import Handler as _Handler
from ...handlers.web import decorator as deco
from ...modules import mongo as mod_mongo
from ... import config
from ...modules.mongo.case import Case, HistoryItem, TxnRef
from ...modules.mongo.transaction import Transaction
from ...modules.mongo.security import Ref as SecurityRef
from ...modules.mongo.user import UserRef
from ...modules.mongo.agent import AgentRef


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
            other_id = mod_mongo.bson.ObjectId(self.cgi_params.param_post('linked_case'))
            other = Case.objects(id=other_id).first()
            if other is None or other.id == doc.id:
                raise ValueError('Invalid linked case')
            comment = self.cgi_params.param_post('comment')
            txn = Transaction(type='case_link', options={
                'case': doc.id, 'linked_case': other.id, 'comment': comment})
            txn.save()
            ref = TxnRef(id=txn.id, type='case_link')
            with mod_mongo.DbSessionController() as db_session:
                collection = db_session[config.name]['case']
                collection.update_one({'_id': doc.id}, {'$push': {'transactions': ref.to_mongo()}})
                collection.update_one({'_id': other.id}, {'$push': {'transactions': ref.to_mongo()}})
            from ...util.defer import the_app
            the_app.send_task('handlers.defer.TransactionProcessor', kwargs={'id_txn': txn.id})
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
            doc.update(push__history=HistoryItem(dt=datetime.datetime.utcnow(), comment=comment,
                                                 file_id=file_id, creator=self._ref()))
        from ...handlers.ext import redirect
        return redirect.Handler(self.req)('/case/view/%s' % oid)
