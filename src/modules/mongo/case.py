# -*- coding: utf-8 -*-

import datetime

from .. import mongo as mod_mongo
from .security import Ref as SecurityRef


class HistoryItem(mod_mongo.mongoengine.EmbeddedDocument):
    meta = {'strict': False}

    dt = mod_mongo.mongoengine.DateTimeField(
        default=lambda: datetime.datetime.now(datetime.timezone.utc), required=True)
    comment = mod_mongo.mongoengine.StringField(required=True)
    file_id = mod_mongo.mongoengine.ObjectIdField()
    linked_case_id = mod_mongo.mongoengine.ObjectIdField()
    creator = mod_mongo.mongoengine.EmbeddedDocumentField(SecurityRef)


class Case(mod_mongo.mongoengine.Document):
    meta = {'db_alias': mod_mongo.mongoengine_alias, 'collection': 'case', 'strict': False}

    title = mod_mongo.mongoengine.StringField(required=True)
    status = mod_mongo.mongoengine.StringField(
        required=True, default='open', choices=('open', 'progress', 'resolved', 'closed'))
    history = mod_mongo.mongoengine.EmbeddedDocumentListField(HistoryItem, default=list)
    pending_txns = mod_mongo.mongoengine.ListField(
        mod_mongo.mongoengine.ObjectIdField(), default=list)
    creator = mod_mongo.mongoengine.EmbeddedDocumentField(SecurityRef)
