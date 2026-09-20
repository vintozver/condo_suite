# -*- coding: utf-8 -*-


from .. import mongo as mod_mongo
from .vehicle import Ref as VehicleRef
from .security import Ref as SecurityRef


class HistoryItem(mod_mongo.mongoengine.EmbeddedDocument):
    meta = {'strict': False}

    id = mod_mongo.mongoengine.ObjectIdField(db_field='_id', required=True)
    content_type = mod_mongo.mongoengine.StringField(default='application/octet-stream')
    length = mod_mongo.mongoengine.LongField(default=0)
    description = mod_mongo.mongoengine.StringField()
    creator = mod_mongo.mongoengine.EmbeddedDocumentField(SecurityRef)


class DescriptionUpdate(mod_mongo.mongoengine.EmbeddedDocument):
    meta = {'strict': False}

    dt = mod_mongo.mongoengine.DateTimeField(required=True)
    by = mod_mongo.mongoengine.EmbeddedDocumentField(SecurityRef, required=True)


# document stored in the database
class Document(mod_mongo.mongoengine.Document):
    meta = {'db_alias': mod_mongo.mongoengine_alias, 'collection': 'parking_event', 'strict': False}

    vehicle = mod_mongo.mongoengine.EmbeddedDocumentField(VehicleRef)
    reason = mod_mongo.mongoengine.StringField(max_length=32, default='other', choices=('other', 'visitor', 'disabled_illegal', 'fire', 'obstruction'))
    remarks = mod_mongo.mongoengine.StringField()
    history = mod_mongo.mongoengine.EmbeddedDocumentListField(HistoryItem, default=list)
    description = mod_mongo.mongoengine.StringField()
    description_upd = mod_mongo.mongoengine.EmbeddedDocumentField(DescriptionUpdate)
    creator = mod_mongo.mongoengine.EmbeddedDocumentField(SecurityRef)


def update_vehicle_markers(database, vin, event_id=None, history_id=None,
                           tag=None, session=None):
    from .vehicle import Document as VehicleDocument

    update = {}
    if event_id is not None:
        update.setdefault('$max', {})['last_parking_event_id'] = event_id
    if history_id is not None:
        update.setdefault('$max', {})[
            'last_parking_event_history_id'] = history_id
    if tag is not None:
        update.setdefault('$set', {})['tag'] = tag
    return database[VehicleDocument._meta['collection']].update_one(
        {'_id': vin}, update, upsert=True, session=session)
