from .common import ApiError, BaseHandler
from ....modules.mongo.vehicle import Document as VehicleDocument
import http.client


class Handler(BaseHandler):
    def __call__(self):
        def operation():
            user, agent, payload = self._authenticate()
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
