from .common import ApiError, BaseHandler
from ...modules.mongo.agent import AgentRef
from ...modules.mongo.security import Ref as SecurityRef
from ...modules.mongo.user import UserRef
from ...modules.mongo.vehicle import Document as VehicleDocument
from ...modules.mongo.vehicle import DescriptionUpdate
import datetime
import email.utils
import http.client


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

    @staticmethod
    def _if_unmodified_since(value):
        if not value:
            return None
        try:
            parsed = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            raise ApiError(http.client.BAD_REQUEST, 'Invalid If-Unmodified-Since header')
        if parsed is None:
            raise ApiError(http.client.BAD_REQUEST, 'Invalid If-Unmodified-Since header')
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.timezone.utc)
        return parsed

    def __call__(self, vin=None):
        def operation():
            user, agent, payload = self._authenticate()
            if self.req.method == 'POST':
                if self.req.request_headers.get('Content-Type', '').split(';', 1)[0].strip().lower() != 'text/plain':
                    raise ApiError(http.client.BAD_REQUEST, 'Content-Type must be text/plain')
                vehicle = VehicleDocument.objects(id=vin).first()
                if vehicle is None:
                    raise ApiError(http.client.NOT_FOUND, 'Vehicle not found')
                if vehicle.description_upd:
                    since = self._if_unmodified_since(
                        self.req.request_headers.get('If-Unmodified-Since'))
                    updated = vehicle.description_upd.dt
                    if updated.tzinfo is None:
                        updated = updated.replace(tzinfo=datetime.timezone.utc)
                    if since and updated.replace(microsecond=0) > since:
                        raise ApiError(http.client.PRECONDITION_FAILED, 'Vehicle was modified')
                description = self.req.request_body.decode('utf-8')
                vehicle.description = description
                vehicle.description_upd = DescriptionUpdate(
                    dt=datetime.datetime.now(datetime.timezone.utc),
                    by=SecurityRef(
                        user=UserRef(id=user.id, name=user.name),
                        agent=AgentRef(id=agent.id, name=agent.name, position=agent.position)))
                vehicle.save()
                self.req.setHeader(
                    'Last-Modified',
                    email.utils.format_datetime(vehicle.description_upd.dt, usegmt=True))
                self._json({
                    'VIN': vehicle.id,
                    'description': vehicle.description,
                    'description_upd': self._description_upd(vehicle.description_upd),
                })
                return
            query = VehicleDocument.objects()
            if payload.get('VIN'):
                query = query.filter(id=payload['VIN'])
            if payload.get('tag'):
                query = query.filter(tag=payload['tag'])
            self._json({'vehicles': [
                {
                    'VIN': doc.id,
                    'tag': doc.tag,
                    'description': doc.description,
                    'description_upd': self._description_upd(doc.description_upd),
                }
                for doc in query.order_by('id')[:500]
            ]})
        return self._run(operation)
