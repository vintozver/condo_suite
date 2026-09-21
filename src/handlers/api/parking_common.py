from .common import ApiError, BaseHandler, mod_mongo
from ...modules.mongo.parking_event import Document as ParkingEventDocument


class ParkingHandler(BaseHandler):
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
    def _event(doc):
        return {'oid': str(doc.id), 'dt': doc.id.generation_time.isoformat(), 'reason': doc.reason,
                'vehicle': {'VIN': doc.vehicle.id, 'tag': doc.vehicle.tag}, 'remarks': doc.remarks,
                'description': doc.description,
                'description_upd': ParkingHandler._description_upd(doc.description_upd),
                'history': [{'oid': str(item.file_id or item.id) if item.length else None, 'dt': item.id.generation_time.isoformat(),
                             'description': item.description, 'content_type': item.content_type, 'length': item.length}
                            for item in doc.history]}

    @staticmethod
    def _get_doc(oid):
        try:
            doc = ParkingEventDocument.objects(id=mod_mongo.bson.objectid.ObjectId(oid)).first()
        except (TypeError, ValueError):
            doc = None
        if doc is None:
            raise ApiError(404, 'Event not found')
        return doc
