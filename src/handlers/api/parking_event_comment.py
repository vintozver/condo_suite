from .common import ApiError, config, mod_mongo
from .parking_common import ParkingHandler
from ...modules.mongo.parking_event import HistoryItem
from ...modules.mongo.parking_event import Document as ParkingEventDocument
from ...modules.mongo.parking_event import next_history_update
from ...modules.mongo.security import Ref as SecurityRef
from ...modules.mongo.user import UserRef
from ...modules.mongo.agent import AgentRef
import http.client


class Handler(ParkingHandler):
    def __call__(self, oid):
        def operation():
            user, agent, payload = self._authenticate()
            if not user.rbac_has_permission('parking.event/comment'):
                raise ApiError(http.client.FORBIDDEN, 'Permission required')
            doc = self._get_doc(oid)
            description = payload.get('description')
            if not isinstance(description, str) or not description:
                raise ApiError(http.client.BAD_REQUEST, 'description must be set')
            item = HistoryItem(id=mod_mongo.bson.objectid.ObjectId(), description=description,
                creator=SecurityRef(user=UserRef(id=user.id, name=user.name),
                                    agent=AgentRef(id=agent.id, name=agent.name, position=agent.position)))
            with mod_mongo.DbSessionController() as db_session, \
                    db_session.start_session() as session:
                def append_history(active_session):
                    collection = db_session[config.name][
                        ParkingEventDocument._meta['collection']]
                    current = collection.find_one(
                        {'_id': doc.id},
                        {'history_upd': True, 'history._id': True},
                        session=active_session)
                    if current is None:
                        raise ApiError(http.client.NOT_FOUND, 'Event not found')
                    previous_updated = current.get('history_upd')
                    if previous_updated is None and current.get('history'):
                        previous_updated = current['history'][-1][
                            '_id'].generation_time
                    result = collection.update_one(
                        {'_id': doc.id},
                        {
                            '$push': {'history': item.to_mongo()},
                            '$set': {'history_upd': next_history_update(
                                previous_updated)},
                        },
                        session=active_session)
                    if not result.matched_count:
                        raise ApiError(http.client.NOT_FOUND, 'Event not found')
                session.with_transaction(append_history)
            self._json({'event': str(doc.id), 'history': str(item.id)}, http.client.CREATED)
        return self._run(operation)
