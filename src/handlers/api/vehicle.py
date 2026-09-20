from .common import ApiError, BaseHandler, config, mod_mongo
from ...modules.mongo.agent import AgentRef
from ...modules.mongo.security import Ref as SecurityRef
from ...modules.mongo.user import UserRef
from ...modules.mongo.vehicle import Document as VehicleDocument
from ...modules.mongo.vehicle import DescriptionUpdate
import datetime
import http.client
import secrets


class Handler(BaseHandler):
    @staticmethod
    def _description_upd(value):
        if value is None:
            return None
        by = value.by
        return {
            'dt': value.dt.isoformat(),
            'by': {
                'user': {'id': str(by.user.id), 'name': by.user.name} if by and by.user else None,
                'agent': {
                    'id': str(by.agent.id), 'name': by.agent.name, 'position': by.agent.position
                } if by and by.agent else None,
            },
        }

    @classmethod
    def _vehicle(cls, vehicle):
        return {
            'VIN': vehicle.id,
            'tag': vehicle.tag,
            'description': vehicle.description,
            'description_upd': cls._description_upd(vehicle.description_upd),
        }

    @staticmethod
    def _source_version(event_id, history_id, updated):
        return '%s:%s:%s' % (event_id, history_id or '', updated.isoformat())

    @staticmethod
    def _etag(value):
        return '"%s"' % value

    @staticmethod
    def _if_match(value):
        if not value:
            raise ApiError(http.client.PRECONDITION_REQUIRED, 'If-Match header is required')
        value = value.strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        parts = value.split(':', 2)
        try:
            event_id = mod_mongo.bson.objectid.ObjectId(parts[0])
            history_id = (
                mod_mongo.bson.objectid.ObjectId(parts[1])
                if parts[1] else None)
            updated = datetime.datetime.fromisoformat(parts[2])
        except (IndexError, TypeError, ValueError):
            raise ApiError(http.client.BAD_REQUEST, 'Invalid If-Match header')
        return event_id, history_id, updated

    def __call__(self, vin=None, action=None):
        def operation():
            user, agent, payload = self._authenticate()
            if not user.rbac_has_permission('vehicle/view'):
                raise ApiError(http.client.FORBIDDEN, 'Permission required')
            if self.req.method == 'POST':
                if self.req.request_headers.get('Content-Type', '').split(';', 1)[0].strip().lower() != 'text/plain':
                    raise ApiError(http.client.BAD_REQUEST, 'Content-Type must be text/plain')
                event_id, history_id, expected_source_updated = self._if_match(
                    self.req.request_headers.get('If-Match'))
                with mod_mongo.DbSessionController() as db:
                    vehicle_collection = db[config.name][
                        VehicleDocument._meta['collection']]
                    vehicle_state = vehicle_collection.find_one(
                        {'_id': vin},
                        {
                            '_id': True,
                            'last_parking_event_id': True,
                            'last_parking_event_history_id': True,
                            'last_parking_event_description_upd': True,
                        })
                    if vehicle_state is None:
                        raise ApiError(http.client.NOT_FOUND, 'Vehicle not found')
                    if (vehicle_state.get('last_parking_event_id') != event_id or
                            vehicle_state.get(
                                'last_parking_event_history_id') != history_id):
                        raise ApiError(
                            http.client.PRECONDITION_FAILED,
                            'Parking events were modified')
                    source_updated = vehicle_state.get(
                        'last_parking_event_description_upd')
                    if source_updated != expected_source_updated:
                        raise ApiError(
                            http.client.PRECONDITION_FAILED,
                            'Parking event descriptions were modified')
                    description_upd = DescriptionUpdate(
                        dt=datetime.datetime.now(datetime.timezone.utc),
                        by=SecurityRef(
                            user=UserRef(id=user.id, name=user.name),
                            agent=AgentRef(
                                id=agent.id, name=agent.name,
                                position=agent.position)))
                    vehicle_data = vehicle_collection.find_one_and_update(
                        {
                            '_id': vin,
                            'last_parking_event_id': event_id,
                            'last_parking_event_history_id': history_id,
                            'last_parking_event_description_upd': source_updated,
                            '$or': [
                                {'description_upd.dt': {'$exists': False}},
                                {'description_upd.dt': {'$lt': source_updated}},
                            ],
                        },
                        {'$set': {
                            'description': self.req.request_body.decode('utf-8'),
                            'description_upd': description_upd.to_mongo(),
                        }},
                        return_document=mod_mongo.pymongo.ReturnDocument.AFTER)
                    if vehicle_data is None:
                        raise ApiError(
                            http.client.PRECONDITION_FAILED,
                            'Vehicle description was already updated')
                vehicle = VehicleDocument._from_son(vehicle_data)
                source_version = self._source_version(
                    event_id, history_id, source_updated)
                self.req.setHeader('ETag', self._etag(source_version))
                self._json(self._vehicle(vehicle))
                return
            if action == 'candidate':
                candidates = []
                for vehicle in VehicleDocument.objects(
                        last_parking_event_description_upd__exists=True,
                        last_parking_event_id__exists=True).only(
                            'id', 'tag', 'description', 'description_upd',
                            'last_parking_event_id',
                            'last_parking_event_history_id',
                            'last_parking_event_description_upd'):
                    update = vehicle.description_upd
                    updated = update.dt if update else None
                    if updated and updated.tzinfo is None:
                        updated = updated.replace(tzinfo=datetime.timezone.utc)
                    source_updated = vehicle.last_parking_event_description_upd
                    if source_updated.tzinfo is None:
                        source_updated = source_updated.replace(
                            tzinfo=datetime.timezone.utc)
                    if updated is None or updated < source_updated:
                        candidates.append((
                            vehicle, self._source_version(
                                vehicle.last_parking_event_id,
                                vehicle.last_parking_event_history_id,
                                source_updated)))
                if not candidates:
                    raise ApiError(http.client.NOT_FOUND, 'No update candidate')
                vehicle, source_version = secrets.choice(candidates)
                self.req.setHeader('ETag', self._etag(source_version))
                result = self._vehicle(vehicle)
                result['last_parking_event_id'] = str(
                    vehicle.last_parking_event_id)
                result['last_parking_event_history_id'] = (
                    str(vehicle.last_parking_event_history_id)
                    if vehicle.last_parking_event_history_id else None)
                self._json(result)
                return
            query = VehicleDocument.objects()
            if payload.get('VIN'):
                query = query.filter(id=payload['VIN'])
            if payload.get('tag'):
                query = query.filter(tag=payload['tag'])
            self._json({'vehicles': [
                self._vehicle(doc)
                for doc in query.order_by('id')[:500]
            ]})
        return self._run(operation)
