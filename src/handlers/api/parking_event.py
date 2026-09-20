from .common import ApiError, mod_mongo, config
from .parking_common import ParkingHandler
from ...modules.mongo.agent import AgentRef
from ...modules.mongo.parking_event import Document as ParkingEventDocument
from ...modules.mongo.parking_event import DescriptionUpdate
from ...modules.mongo.parking_event import update_vehicle_markers
from ...modules.mongo.security import Ref as SecurityRef
from ...modules.mongo.user import UserRef
from ...modules.mongo.vehicle import Document as VehicleDocument
import datetime
import http.client
import secrets

class Handler(ParkingHandler):
    @staticmethod
    def _etag(value):
        return '"%s"' % value

    @staticmethod
    def _if_match(value):
        if not value:
            raise ApiError(http.client.PRECONDITION_REQUIRED, 'If-Match header is required')
        value = value.strip()
        if len(value) == 26 and value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        try:
            return mod_mongo.bson.objectid.ObjectId(value)
        except (TypeError, ValueError):
            raise ApiError(http.client.BAD_REQUEST, 'Invalid If-Match header')

    def __call__(self, action, oid=None, file_oid=None):
        if self.req.method == 'POST' and action == 'view':
            from .parking_event_comment import Handler as CommentHandler
            return CommentHandler(self.req)(oid)
        def operation():
            user, agent, payload = self._authenticate()
            if action == 'candidate':
                if not user.rbac_has_permission('parking.event/view'):
                    raise ApiError(http.client.FORBIDDEN, 'Permission required')
                candidates = []
                for doc in self._get_candidates():
                    last_history = doc.history[-1]
                    updated = doc.description_upd.dt if doc.description_upd else None
                    if updated and updated.tzinfo is None:
                        updated = updated.replace(tzinfo=datetime.timezone.utc)
                    if updated is None or updated < last_history.id.generation_time:
                        candidates.append((doc, last_history.id))
                if not candidates:
                    raise ApiError(http.client.NOT_FOUND, 'No update candidate')
                doc, last_history_id = secrets.choice(candidates)
                self.req.setHeader('ETag', self._etag(last_history_id))
                result = self._event(doc)
                result['last_history_id'] = str(last_history_id)
                self._json(result)
                return
            if action == 'description':
                if self.req.method != 'POST':
                    raise ApiError(http.client.METHOD_NOT_ALLOWED, 'POST required')
                if not user.rbac_has_permission('parking.event/comment'):
                    raise ApiError(http.client.FORBIDDEN, 'Permission required')
                if self.req.request_headers.get('Content-Type', '').split(';', 1)[0].strip().lower() != 'text/plain':
                    raise ApiError(http.client.BAD_REQUEST, 'Content-Type must be text/plain')
                last_history_id = self._if_match(
                    self.req.request_headers.get('If-Match'))
                doc = self._get_doc(oid)
                if not doc.history or doc.history[-1].id != last_history_id:
                    raise ApiError(
                        http.client.PRECONDITION_FAILED,
                        'Parking event history was modified')
                with mod_mongo.DbSessionController() as db, db.start_session() as session:
                    def update_description(active_session):
                        description_upd = DescriptionUpdate(
                            dt=datetime.datetime.now(datetime.timezone.utc),
                            by=SecurityRef(
                                user=UserRef(id=user.id, name=user.name),
                                agent=AgentRef(
                                    id=agent.id, name=agent.name,
                                    position=agent.position)))
                        event_data = db[config.name][
                            ParkingEventDocument._meta['collection']].find_one_and_update(
                            {
                                '_id': doc.id,
                                'history': {'$size': len(doc.history)},
                                'history.%d._id' % (
                                    len(doc.history) - 1): last_history_id,
                                '$or': [
                                    {'description_upd.dt': {'$exists': False}},
                                    {'description_upd.dt': {
                                        '$lt': last_history_id.generation_time}},
                                ],
                            },
                            {'$set': {
                                'description': self.req.request_body.decode('utf-8'),
                                'description_upd': description_upd.to_mongo(),
                            }},
                            return_document=mod_mongo.pymongo.ReturnDocument.AFTER,
                            session=active_session)
                        if event_data is None:
                            raise ApiError(
                                http.client.PRECONDITION_FAILED,
                                'Parking event history was modified or description was already updated')
                        update_vehicle_markers(
                            db[config.name], doc.vehicle.id,
                            event_id=doc.id, history_id=last_history_id,
                            session=active_session)
                        db[config.name][
                            VehicleDocument._meta['collection']].update_one(
                                {'_id': doc.vehicle.id},
                                {'$max': {
                                    'last_parking_event_description_upd':
                                        description_upd.dt}},
                                session=active_session)
                        return event_data
                    event_data = session.with_transaction(update_description)
                self.req.setHeader('ETag', self._etag(last_history_id))
                self._json(self._event(type(doc)._from_son(event_data)))
                return
            doc = self._get_doc(oid)
            if action == 'view':
                if not user.rbac_has_permission('parking.event/view'): raise ApiError(http.client.FORBIDDEN, 'Permission required')
                self._json(self._event(doc))
            elif action == 'file':
                if not user.rbac_has_permission('parking.event/view'): raise ApiError(http.client.FORBIDDEN, 'Permission required')
                file_id = mod_mongo.bson.objectid.ObjectId(file_oid)
                if not any(item.id == file_id and item.length for item in doc.history): raise ApiError(http.client.NOT_FOUND, 'File not found')
                with mod_mongo.DbSessionController() as db_session:
                    attachment = mod_mongo.gridfs.GridFS(
                        db_session[config.name],
                        ParkingEventDocument._meta['collection'] + '.history'
                    ).get(file_id)
                    self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
                    self.req.setHeader('Content-Type', attachment.content_type)
                    self.req.write(attachment.read())
            else: raise ApiError(http.client.NOT_FOUND, 'Unknown API action')
        return self._run(operation)

    def _get_candidates(self):
        return ParkingEventDocument.objects(history__0__exists=True).only(
            'vehicle', 'reason', 'remarks', 'history', 'description',
            'description_upd')
