from .common import ApiError, BaseHandler, mod_mongo
from ....modules.mongo.parking_event import Document as ParkingEventDocument


class ParkingHandler(BaseHandler):
    @staticmethod
    def _event(doc):
        return {'oid': str(doc.id), 'dt': doc.id.generation_time.isoformat(), 'reason': doc.reason,
                'vehicle': {'VIN': doc.vehicle.id, 'tag': doc.vehicle.tag}, 'remarks': doc.remarks,
                'history': [{'oid': str(item.id) if item.length else None, 'dt': item.id.generation_time.isoformat(),
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
