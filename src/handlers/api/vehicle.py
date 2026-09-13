from .common import ApiError, BaseHandler
from ....modules.mongo.vehicle import Document as VehicleDocument
import http.client


class Handler(BaseHandler):
    def __call__(self, vin=None):
        def operation():
            user, agent, payload = self._authenticate()
            if self.req.method == 'POST':
                if self.req.request_headers.get('Content-Type', '').split(';', 1)[0].strip().lower() != 'text/plain':
                    raise ApiError(http.client.BAD_REQUEST, 'Content-Type must be text/plain')
                vehicle = VehicleDocument.objects(id=vin).first()
                if vehicle is None:
                    raise ApiError(http.client.NOT_FOUND, 'Vehicle not found')
                description = self.req.request_body.decode('utf-8')
                vehicle.description = description + '\n\nUpdated by: %s, %s' % (user.name, agent.name)
                vehicle.save()
                self._json({'VIN': vehicle.id, 'description': vehicle.description})
                return
            query = VehicleDocument.objects()
            if payload.get('VIN'):
                query = query.filter(id=payload['VIN'])
            if payload.get('tag'):
                query = query.filter(tag=payload['tag'])
            self._json({'vehicles': [
                {'VIN': doc.id, 'tag': doc.tag, 'description': doc.description}
                for doc in query.order_by('id')[:500]
            ]})
        return self._run(operation)
