# -*- coding: utf-8 -*-

import datetime
import modules.mongo as mod_mongo


class Transaction(mod_mongo.mongoengine.Document):
    meta = {'db_alias': mod_mongo.mongoengine_alias, 'collection': 'transaction', 'strict': False}

    type = mod_mongo.mongoengine.StringField(max_length=64, required=True)
    state = mod_mongo.mongoengine.StringField(max_length=64, required=True, default='initial', choices=(
        'initial', 'pending', 'applied', 'completed', 'cancelling', 'cancelled'
    ))
    last_mod = mod_mongo.mongoengine.DateTimeField(default=datetime.datetime.utcnow)
    options = mod_mongo.mongoengine.DynamicField()
