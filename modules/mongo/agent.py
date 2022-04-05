# -*- coding: utf-8 -*-


import modules.mongo as mod_mongo
import modules.mongo.address as mod_mongo_address


class AgentDocument(mod_mongo.mongoengine.Document):
    meta = {'db_alias': mod_mongo.mongoengine_alias, 'collection': 'agent', 'strict': False}

    name = mod_mongo.mongoengine.StringField(max_length=128, required=True)
    address = mod_mongo_address.AddressField(default=mod_mongo_address.Address)

    # if this field is set to true or IsoDate(), the agent is considered closed and no longer in use
    closed = mod_mongo.mongoengine.DynamicField(default=False)


class AgentRef(mod_mongo.mongoengine.EmbeddedDocument):
    id = mod_mongo.mongoengine.ObjectIdField(db_field='_id', required=True)
    name = mod_mongo.mongoengine.StringField(max_length=128)
    position = mod_mongo.mongoengine.StringField(max_length=128)
