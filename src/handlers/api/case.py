# -*- coding: utf-8 -*-

import datetime
import http.client
import json

from .common import ApiError, BaseHandler, config, mod_mongo
from ....modules.mongo.case import Document as CaseDocument
from ....modules.mongo.case import HistoryItem, TxnRef
from ....modules.mongo.security import Ref as SecurityRef
from ....modules.mongo.user import UserRef
from ....modules.mongo.agent import AgentRef
from ....modules.mongo.transaction import Transaction


class Handler(BaseHandler):
    def _body(self):
        if not self.req.request_body:
            return {}
        try:
            value = json.loads(self.req.request_body.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            raise ApiError(http.client.BAD_REQUEST, 'Invalid JSON body')
        if not isinstance(value, dict):
            raise ApiError(http.client.BAD_REQUEST, 'JSON body must be an object')
        return value

    @staticmethod
    def _case(doc):
        return {
            'id': str(doc.id),
            'title': doc.title,
            'status': doc.status,
            'history': [{
                'dt': item.dt.isoformat(),
                'comment': item.comment,
                'file_id': str(item.file_id) if item.file_id else None,
                'linked_case_id': str(item.linked_case_id) if item.linked_case_id else None,
            } for item in doc.history],
        }

    @staticmethod
    def _oid(value):
        try:
            return mod_mongo.bson.ObjectId(str(value))
        except (TypeError, ValueError):
            raise ApiError(http.client.BAD_REQUEST, 'Invalid case id')

    def __call__(self, oid=None, action=None, linked_oid=None):
        def operation():
            user, agent, payload = self._authenticate()
            body = self._body()
            if self.req.method == 'POST' and oid is None:
                if not user.rbac_has_permission('case/create'):
                    raise ApiError(http.client.FORBIDDEN, 'Permission required')
                title = body.get('title')
                if not isinstance(title, str) or not title:
                    raise ApiError(http.client.BAD_REQUEST, 'title must be set')
                doc = CaseDocument(
                    id=mod_mongo.bson.ObjectId(), title=title, status='open',
                    creator=SecurityRef(user=UserRef(id=user.id, name=user.name),
                                        agent=AgentRef(id=agent.id, name=agent.name, position=agent.position)))
                doc.save()
                self._json({'case': str(doc.id)}, http.client.CREATED)
                return

            case_id = self._oid(oid)
            doc = CaseDocument.objects(id=case_id).first()
            if doc is None:
                raise ApiError(http.client.NOT_FOUND, 'Case not found')
            if self.req.method == 'GET' and action is None:
                if not user.rbac_has_permission('case/view'):
                    raise ApiError(http.client.FORBIDDEN, 'Permission required')
                self._json({'case': self._case(doc)})
            elif self.req.method == 'PATCH' and action == 'status':
                if not user.rbac_has_permission('case/status'):
                    raise ApiError(http.client.FORBIDDEN, 'Permission required')
                status = body.get('status')
                if status not in ('open', 'progress', 'resolved', 'closed'):
                    raise ApiError(http.client.BAD_REQUEST, 'Invalid status')
                doc.update(set__status=status)
                self._json({'case': str(doc.id), 'status': status})
            elif self.req.method == 'POST' and action == 'comment':
                if not user.rbac_has_permission('case/comment'):
                    raise ApiError(http.client.FORBIDDEN, 'Permission required')
                comment = body.get('comment')
                if not isinstance(comment, str) or not comment:
                    raise ApiError(http.client.BAD_REQUEST, 'comment must be set')
                file_id = self._oid(body['file_id']) if body.get('file_id') else None
                item = HistoryItem(dt=datetime.datetime.utcnow(), comment=comment, file_id=file_id,
                                   creator=SecurityRef(user=UserRef(id=user.id, name=user.name),
                                                       agent=AgentRef(id=agent.id, name=agent.name,
                                                                      position=agent.position)))
                doc.update(push__history=item)
                self._json({'case': str(doc.id)}, http.client.CREATED)
            elif self.req.method == 'POST' and action == 'link':
                if not user.rbac_has_permission('case/link'):
                    raise ApiError(http.client.FORBIDDEN, 'Permission required')
                other_id = self._oid(linked_oid)
                if other_id == case_id or CaseDocument.objects(id=other_id).first() is None:
                    raise ApiError(http.client.NOT_FOUND, 'Linked case not found')
                comment = body.get('comment')
                if not isinstance(comment, str) or not comment:
                    raise ApiError(http.client.BAD_REQUEST, 'comment must be set')
                txn = Transaction(type='case_link', options={
                    'case': case_id, 'linked_case': other_id, 'comment': comment})
                txn.save()
                ref = TxnRef(id=txn.id, type='case_link')
                with mod_mongo.DbSessionController() as db_session:
                    collection = db_session[config.name]['case']
                    collection.update_one({'_id': case_id}, {'$push': {'transactions': ref.to_mongo()}})
                    collection.update_one({'_id': other_id}, {'$push': {'transactions': ref.to_mongo()}})
                from ...util.defer import the_app
                the_app.send_task('handlers.defer.TransactionProcessor', kwargs={'id_txn': txn.id})
                self._json({'transaction': str(txn.id)}, http.client.ACCEPTED)
            else:
                raise ApiError(http.client.NOT_FOUND, 'Unknown case operation')
        return self._run(operation)
