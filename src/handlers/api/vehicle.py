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
    def _event_descriptions(db, vin=None):
        query = {'vehicle._id': vin} if vin else {'vehicle._id': {'$exists': True}}
        query['description_upd.dt'] = {'$exists': True}
        projection = {'vehicle._id': True, 'description_upd.dt': True}
        updates = {}
        for event in db[config.name]['parking_event'].find(query, projection):
            event_vin = event.get('vehicle', {}).get('_id')
            updated = event.get('description_upd', {}).get('dt')
            if not event_vin or updated is None:
                continue
            updates.setdefault(event_vin, []).append((event['_id'], updated))
        return {
            event_vin: {
                'version': hashlib.sha256('\n'.join(sorted(
                    '%s:%s' % (event_id, updated.isoformat())
                    for event_id, updated in values)).encode('ascii')).hexdigest(),
                'updated': max(updated for event_id, updated in values),
            }
            for event_vin, values in updates.items()
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
                    event_state = self._event_descriptions(db, vin).get(vin)
                    if event_state is None or event_state['version'] != expected_version:
                        raise ApiError(
                            http.client.PRECONDITION_FAILED,
                            'Parking event descriptions were modified')
                    description_upd = DescriptionUpdate(
                        dt=datetime.datetime.now(datetime.timezone.utc),
                        by=SecurityRef(
                            user=UserRef(id=user.id, name=user.name),
                            agent=AgentRef(
                                id=agent.id, name=agent.name, position=agent.position)),
                        event_version=expected_version)
                    vehicle_data = db[config.name]['vehicle'].find_one_and_update(
                        {
                            '_id': vin,
                            '$or': [
                                {'description_upd.event_version': {'$exists': False}},
                                {'description_upd.event_version': {
                                    '$ne': event_state['version']}},
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
                self.req.setHeader('ETag', self._etag(expected_version))
                self._json(self._vehicle(vehicle))
                return
            if action == 'candidate':
                with mod_mongo.DbSessionController() as db:
                    event_descriptions = self._event_descriptions(db)
                candidates = []
                for vehicle in VehicleDocument.objects(
                        id__in=list(event_descriptions)).only(
                            'id', 'tag', 'description', 'description_upd'):
                    event_state = event_descriptions[vehicle.id]
                    update = vehicle.description_upd
                    updated = update.dt if update else None
                    if updated and updated.tzinfo is None:
                        updated = updated.replace(tzinfo=datetime.timezone.utc)
                    if updated is None or updated < event_state['updated']:
                        candidates.append((vehicle, event_state['version']))
                if not candidates:
                    raise ApiError(http.client.NOT_FOUND, 'No update candidate')
                vehicle, event_version = secrets.choice(candidates)
                self.req.setHeader('ETag', self._etag(event_version))
                result = self._vehicle(vehicle)
                result['event_version'] = event_version
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
