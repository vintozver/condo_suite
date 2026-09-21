# -*- coding: utf-8 -*-


import datetime

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
    history_upd = mod_mongo.mongoengine.DateTimeField()
    description = mod_mongo.mongoengine.StringField()
    description_upd = mod_mongo.mongoengine.EmbeddedDocumentField(DescriptionUpdate)
    creator = mod_mongo.mongoengine.EmbeddedDocumentField(SecurityRef)


def next_history_update(previous=None):
    updated = datetime.datetime.now(
        datetime.timezone.utc).replace(microsecond=0)
    if previous is not None:
        if previous.tzinfo is None:
            previous = previous.replace(tzinfo=datetime.timezone.utc)
        if updated <= previous:
            updated = previous + datetime.timedelta(seconds=1)
    return updated
