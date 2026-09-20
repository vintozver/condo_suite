# -*- coding: utf-8 -*-


from .. import mongo as mod_mongo
from .security import Ref as SecurityRef


class DescriptionUpdate(mod_mongo.mongoengine.EmbeddedDocument):
    dt = mod_mongo.mongoengine.DateTimeField(required=True)
    by = mod_mongo.mongoengine.EmbeddedDocumentField(SecurityRef, required=True)
    history_version = mod_mongo.mongoengine.StringField(required=True)


# document stored in the database
class Document(mod_mongo.mongoengine.Document):
    meta = {'db_alias': mod_mongo.mongoengine_alias, 'collection': 'vehicle', 'strict': False}

    # _id represents the VIN (vehicle identification number)
    id = mod_mongo.mongoengine.StringField(regex=r'^[0-9A-HJ-NPR-Z]{17}$', db_field='_id', required=True)
    # tag, license plate, attached decal; for example C012345 WA
    tag = mod_mongo.mongoengine.StringField(max_length=20)
    description = mod_mongo.mongoengine.StringField()
    description_upd = mod_mongo.mongoengine.EmbeddedDocumentField(DescriptionUpdate)


# link to the vehicle in other collections
# vehicle tag may change, so the ultimate identification is always VIN
class Ref(mod_mongo.mongoengine.EmbeddedDocument):
    # _id represents the VIN (vehicle identification number)
    id = mod_mongo.mongoengine.StringField(regex=r'^[0-9A-HJ-NPR-Z]{17}$', db_field='_id', required=True)
    # tag, license plate, attached decal; for example C012345 WA
    tag = mod_mongo.mongoengine.StringField(max_length=20)
