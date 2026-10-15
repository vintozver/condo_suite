# -*- coding: utf-8 -*-

from ...util.context import AutoRefContextItem
from collections import OrderedDict
import bson
import gridfs
import pymongo
import pymongo.errors
import mongoengine
from ... import config as config


class DbSessionController(AutoRefContextItem):
    def new(self):
        return pymongo.MongoClient(
            config.mongodb_uri,
            document_class=OrderedDict, tz_aware=True, uuidRepresentation='pythonLegacy')

    def delete(self):
        pass


mongoengine_alias = object()
mongoengine.register_connection(
    mongoengine_alias,
    host=config.mongodb_uri,
    document_class=OrderedDict,
    tz_aware=True,
    uuidRepresentation='pythonLegacy')


__all__ = ['bson', 'pymongo', 'gridfs', 'DbSessionController', 'mongoengine', 'mongoengine_alias']
