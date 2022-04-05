# -*- coding: utf-8 -*-


import modules.mongo as mod_mongo
from  modules.mongo.vehicle import Ref as VehicleRef
from modules.mongo.security import Ref as SecurityRef


class HistoryItem(mod_mongo.mongoengine.EmbeddedDocument):
    meta = {'strict': False}

    id = mod_mongo.mongoengine.ObjectIdField(db_field='_id', required=True)
    content_type = mod_mongo.mongoengine.StringField(default='application/octet-stream')
    length = mod_mongo.mongoengine.LongField(default=0)
    description = mod_mongo.mongoengine.StringField()
    creator = mod_mongo.mongoengine.EmbeddedDocumentField(SecurityRef)


# document stored in the database
class Document(mod_mongo.mongoengine.Document):
    meta = {'db_alias': mod_mongo.mongoengine_alias, 'collection': 'parking_event', 'strict': False}

    vehicle = mod_mongo.mongoengine.EmbeddedDocumentField(VehicleRef)
    reason = mod_mongo.mongoengine.StringField(max_length=32, default='other', choices=('other', 'visitor', 'disabled_illegal', 'fire', 'obstruction'))
    remarks = mod_mongo.mongoengine.StringField()
    history = mod_mongo.mongoengine.EmbeddedDocumentListField(HistoryItem, default=list)
    creator = mod_mongo.mongoengine.EmbeddedDocumentField(SecurityRef)
