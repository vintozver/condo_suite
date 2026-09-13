from .common import ApiError
from .parking_common import ParkingHandler, ParkingEventDocument
import http.client

class Handler(ParkingHandler):
    def __call__(self):
        def operation():
            user, agent, payload = self._authenticate()
            if not user.rbac_has_permission('parking.event/view'):
                raise ApiError(http.client.FORBIDDEN, 'Permission required')
            body = payload
            query = ParkingEventDocument.objects()
            if body.get('VIN'): query = query.filter(vehicle__id=body['VIN'])
            if body.get('tag'): query = query.filter(vehicle__tag=body['tag'])
            if body.get('reason'): query = query.filter(reason=body['reason'])
            limit = min(max(int(body.get('limit', 100)), 1), 500)
            self._json({'events': [self._event(doc) for doc in query.order_by('-_id')[:limit]]})
        return self._run(operation)
