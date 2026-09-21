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

    def __call__(self, vin=None, action=None):
        def operation():
            user, agent, payload = self._authenticate()
            if not user.rbac_has_permission('vehicle/view'):
                raise ApiError(http.client.FORBIDDEN, 'Permission required')
            if self.req.method == 'POST':
                if self.req.request_headers.get('Content-Type', '').split(';', 1)[0].strip().lower() != 'text/plain':
                    raise ApiError(http.client.BAD_REQUEST, 'Content-Type must be text/plain')
                expected_source_updated = self._if_unmodified_since()
                with mod_mongo.DbSessionController() as db:
                    vehicle_collection = db[config.name][
                        VehicleDocument._meta['collection']]
                    vehicle_state = vehicle_collection.find_one(
                        {'_id': vin},
                        {
                            '_id': True,
                            'last_parking_event_description_upd': True,
                        })
                    if vehicle_state is None:
                        raise ApiError(http.client.NOT_FOUND, 'Vehicle not found')
                    source_updated = vehicle_state.get(
                        'last_parking_event_description_upd')
                    comparable_source_updated = source_updated
                    if comparable_source_updated and comparable_source_updated.tzinfo is None:
                        comparable_source_updated = comparable_source_updated.replace(
                            tzinfo=datetime.timezone.utc)
                    if (comparable_source_updated is None or
                            comparable_source_updated.replace(microsecond=0) >
                            expected_source_updated):
                        raise ApiError(
                            http.client.PRECONDITION_FAILED,
                            'Parking event descriptions were modified')
                    updated = datetime.datetime.now(
                        datetime.timezone.utc).replace(microsecond=0)
                    if updated < source_updated:
                        updated = source_updated
                    description_upd = DescriptionUpdate(
                        dt=updated,
                        by=SecurityRef(
                            user=UserRef(id=user.id, name=user.name),
                            agent=AgentRef(
                                id=agent.id, name=agent.name,
                                position=agent.position)))
                    vehicle_data = vehicle_collection.find_one_and_update(
                        {
                            '_id': vin,
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
                self.req.setHeader(
                    'Last-Modified',
                    self._http_datetime(vehicle.description_upd.dt))
                self._json(self._vehicle(vehicle))
                return
            if action == 'candidate':
                candidates = []
                for vehicle in VehicleDocument.objects(
                        last_parking_event_description_upd__exists=True).only(
                            'id', 'tag', 'description', 'description_upd',
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
                        candidates.append((vehicle, source_updated))
                if not candidates:
                    raise ApiError(http.client.NOT_FOUND, 'No update candidate')
                vehicle, source_updated = secrets.choice(candidates)
                self.req.setHeader(
                    'Last-Modified', self._http_datetime(source_updated))
                result = self._vehicle(vehicle)
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
