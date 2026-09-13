# -*- coding: utf-8 -*-

import datetime

from .. import mongo as mod_mongo
from .security import Ref as SecurityRef


class HistoryItem(mod_mongo.mongoengine.EmbeddedDocument):
    meta = {'strict': False}

    dt = mod_mongo.mongoengine.DateTimeField(default=datetime.datetime.utcnow, required=True)
    comment = mod_mongo.mongoengine.StringField(required=True)
    file_id = mod_mongo.mongoengine.ObjectIdField()
    linked_case_id = mod_mongo.mongoengine.ObjectIdField()
    creator = mod_mongo.mongoengine.EmbeddedDocumentField(SecurityRef)


class TxnRef(mod_mongo.mongoengine.EmbeddedDocument):
    meta = {'strict': False}

    id = mod_mongo.mongoengine.ObjectIdField(required=True)
    type = mod_mongo.mongoengine.StringField(required=True)
    state = mod_mongo.mongoengine.StringField(default='pending', required=True)


class Case(mod_mongo.mongoengine.Document):
    meta = {'db_alias': mod_mongo.mongoengine_alias, 'collection': 'case', 'strict': False}

    title = mod_mongo.mongoengine.StringField(required=True)
    status = mod_mongo.mongoengine.StringField(
        required=True, default='open', choices=('open', 'progress', 'resolved', 'closed'))
    history = mod_mongo.mongoengine.EmbeddedDocumentListField(HistoryItem, default=list)
    transactions = mod_mongo.mongoengine.EmbeddedDocumentListField(TxnRef, default=list)
    creator = mod_mongo.mongoengine.EmbeddedDocumentField(SecurityRef)


Document = Case
