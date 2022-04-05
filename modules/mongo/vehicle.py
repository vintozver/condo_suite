# -*- coding: utf-8 -*-


import modules.mongo as mod_mongo


# document stored in the database
class Document(mod_mongo.mongoengine.Document):
    meta = {'db_alias': mod_mongo.mongoengine_alias, 'collection': 'vehicle', 'strict': False}

    # _id represents the VIN (vehicle identification number)
    id = mod_mongo.mongoengine.StringField(regex=r'^[0-9A-HJ-NPR-Z]{17}$', db_field='_id', required=True)
    # tag, license plate, attached decal; for example C012345 WA
    tag = mod_mongo.mongoengine.StringField(max_length=20)
    description = mod_mongo.mongoengine.StringField(max_length=128)


# link to the vehicle in other collections
# vehicle tag may change, so the ultimate identification is always VIN
class Ref(mod_mongo.mongoengine.EmbeddedDocument):
    # _id represents the VIN (vehicle identification number)
    id = mod_mongo.mongoengine.StringField(regex=r'^[0-9A-HJ-NPR-Z]{17}$', db_field='_id', required=True)
    # tag, license plate, attached decal; for example C012345 WA
    tag = mod_mongo.mongoengine.StringField(max_length=20)
