# -*- coding: utf-8 -*-

import datetime
import http.client
import json

from .common import ApiError, BaseHandler, config, mod_mongo
from ....modules.mongo.case import Case
from ....modules.mongo.case import HistoryItem
from ....modules.mongo.security import Ref as SecurityRef
from ....modules.mongo.user import UserRef
from ....modules.mongo.agent import AgentRef
from ....handlers.defer import case as defer_case


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
                'link': str(item.link) if item.link else None,
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
                doc = Case(
                    id=mod_mongo.bson.ObjectId(), title=title, status='open',
                    creator=SecurityRef(user=UserRef(id=user.id, name=user.name),
                                        agent=AgentRef(id=agent.id, name=agent.name, position=agent.position)))
                doc.save()
                self._json({'case': str(doc.id)}, http.client.CREATED)
                return

            case_id = self._oid(oid)
            doc = Case.objects(id=case_id).first()
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
                item = HistoryItem(dt=datetime.datetime.now(datetime.timezone.utc), comment=comment, file_id=file_id,
                                   creator=SecurityRef(user=UserRef(id=user.id, name=user.name),
                                                       agent=AgentRef(id=agent.id, name=agent.name,
                                                                      position=agent.position)))
                doc.update(push__history=item)
                self._json({'case': str(doc.id)}, http.client.CREATED)
            elif self.req.method == 'POST' and action == 'link':
                if not user.rbac_has_permission('case/link'):
                    raise ApiError(http.client.FORBIDDEN, 'Permission required')
                raw_case_ids = body.get('case_ids')
                if raw_case_ids is None:
                    if linked_oid is None:
                        raise ApiError(http.client.BAD_REQUEST, 'case_ids must be set')
                    raw_case_ids = [case_id, self._oid(linked_oid)]
                if not isinstance(raw_case_ids, list):
                    raise ApiError(http.client.BAD_REQUEST, 'case_ids must be a list')
                try:
                    case_ids = [self._oid(value) for value in raw_case_ids]
                except (TypeError, ValueError):
                    raise ApiError(http.client.BAD_REQUEST, 'Invalid case id')
                if case_id not in case_ids or len(case_ids) < 2 or len(set(case_ids)) != len(case_ids):
                    raise ApiError(http.client.BAD_REQUEST, 'At least two different cases are required')
                if Case.objects(id__in=case_ids).count() != len(case_ids):
                    raise ApiError(http.client.NOT_FOUND, 'Linked case not found')
                comment = body.get('comment')
                if not isinstance(comment, str) or not comment:
                    raise ApiError(http.client.BAD_REQUEST, 'comment must be set')
                creator = SecurityRef(user=UserRef(id=user.id, name=user.name),
                                      agent=AgentRef(id=agent.id, name=agent.name, position=agent.position))
                id_txn = defer_case.link(case_ids, comment, creator)
                self._json({'transaction': str(id_txn)}, http.client.ACCEPTED)
            else:
                raise ApiError(http.client.NOT_FOUND, 'Unknown case operation')
        return self._run(operation)
