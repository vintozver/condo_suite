from .common import ApiError, BaseHandler, config, mod_mongo
from ...modules.mongo.agent import AgentRef
from ...modules.mongo.security import Ref as SecurityRef
from ...modules.mongo.user import UserRef
from ...modules.mongo.vehicle import Document as VehicleDocument
from ...modules.mongo.vehicle import DescriptionUpdate
import datetime
import hashlib
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
    def _history_versions(db, vin=None):
        query = {'vehicle._id': vin} if vin else {'vehicle._id': {'$exists': True}}
        projection = {'vehicle._id': True, 'history._id': True}
        versions = {}
        updated = {}
        for event in db[config.name]['parking_event'].find(query, projection):
            event_vin = event.get('vehicle', {}).get('_id')
            if not event_vin:
                continue
            ids = [event['_id']]
            ids.extend(item['_id'] for item in event.get('history', []) if item.get('_id'))
            versions.setdefault(event_vin, []).extend(str(value) for value in ids)
            newest = max(value.generation_time for value in ids)
            updated[event_vin] = max(updated.get(event_vin, newest), newest)
        return {
            value_vin: {
                'version': hashlib.sha256(
                    '\n'.join(sorted(values)).encode('ascii')).hexdigest(),
                'updated': updated[value_vin],
            }
            for value_vin, values in versions.items()
        }

    @staticmethod
    def _etag(value):
        return '"%s"' % value

    @staticmethod
    def _if_match(value):
        if not value:
            raise ApiError(http.client.PRECONDITION_REQUIRED, 'If-Match header is required')
        value = value.strip()
        if len(value) == 66 and value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        if len(value) != 64 or any(char not in '0123456789abcdef' for char in value):
            raise ApiError(http.client.BAD_REQUEST, 'Invalid If-Match header')
        return value

    def __call__(self, vin=None, action=None):
        def operation():
            user, agent, payload = self._authenticate()
            if self.req.method == 'POST':
                if self.req.request_headers.get('Content-Type', '').split(';', 1)[0].strip().lower() != 'text/plain':
                    raise ApiError(http.client.BAD_REQUEST, 'Content-Type must be text/plain')
                expected_version = self._if_match(
                    self.req.request_headers.get('If-Match'))
                with mod_mongo.DbSessionController() as db:
                    if db[config.name]['vehicle'].find_one(
                            {'_id': vin}, {'_id': True}) is None:
                        raise ApiError(http.client.NOT_FOUND, 'Vehicle not found')
                    history = self._history_versions(db, vin).get(vin)
                    if history is None or history['version'] != expected_version:
                        raise ApiError(
                            http.client.PRECONDITION_FAILED,
                            'Parking event history was modified')
                    description_upd = DescriptionUpdate(
                        dt=datetime.datetime.now(datetime.timezone.utc),
                        by=SecurityRef(
                            user=UserRef(id=user.id, name=user.name),
                            agent=AgentRef(
                                id=agent.id, name=agent.name, position=agent.position)),
                        history_version=expected_version)
                    vehicle_data = db[config.name]['vehicle'].find_one_and_update(
                        {
                            '_id': vin,
                            '$or': [
                                {'description_upd.history_version': {'$exists': False}},
                                {'description_upd.history_version': {'$ne': expected_version}},
                            ],
                        },
                        {'$set': {
                            'description': self.req.request_body.decode('utf-8'),
                            'description_upd': description_upd.to_mongo(),
                        }},
                        return_document=mod_mongo.pymongo.ReturnDocument.AFTER)
                    if vehicle_data is None:
                        if db[config.name]['vehicle'].find_one({'_id': vin}, {'_id': True}) is None:
                            raise ApiError(http.client.NOT_FOUND, 'Vehicle not found')
                        raise ApiError(
                            http.client.PRECONDITION_FAILED,
                            'Vehicle description was already updated')
                    current_history = self._history_versions(db, vin).get(vin)
                if current_history is None or current_history['version'] != expected_version:
                    raise ApiError(
                        http.client.PRECONDITION_FAILED,
                        'Parking event history was modified')
                vehicle = VehicleDocument._from_son(vehicle_data)
                self.req.setHeader('ETag', self._etag(expected_version))
                self._json(self._vehicle(vehicle))
                return
            if action == 'candidate':
                with mod_mongo.DbSessionController() as db:
                    histories = self._history_versions(db)
                candidates = []
                for vehicle in VehicleDocument.objects(
                        id__in=list(histories)).only(
                            'id', 'tag', 'description', 'description_upd'):
                    history = histories[vehicle.id]
                    update = vehicle.description_upd
                    update_dt = update.dt if update else None
                    if update_dt and update_dt.tzinfo is None:
                        update_dt = update_dt.replace(tzinfo=datetime.timezone.utc)
                    if (not update or
                            update.history_version != history['version'] or
                            update_dt < history['updated']):
                        candidates.append((vehicle, history['version']))
                if not candidates:
                    raise ApiError(http.client.NOT_FOUND, 'No update candidate')
                vehicle, history_version = secrets.choice(candidates)
                self.req.setHeader('ETag', self._etag(history_version))
                result = self._vehicle(vehicle)
                result['history_version'] = history_version
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
