# -*- coding: utf-8 -*-

from .. import util
from collections import OrderedDict
import bson
import gridfs
import pymongo
import pymongo.errors
import mongoengine
from ..util import context
from .. import config as config


class DbSessionController(util.context.AutoRefContextItem):
    def new(self):
        return pymongo.MongoClient(
            config.mongodb_uri,
            document_class=OrderedDict, tz_aware=True, uuidRepresentation='pythonLegacy')

    def delete(self):
        pass


mongoengine_alias = object()
mongoengine_connection_kwargs = dict()
mongoengine_connection_kwargs['document_class'] = OrderedDict
mongoengine_connection_kwargs['tz_aware'] = True
mongoengine.register_connection(
    mongoengine_alias,
    host=config.mongodb_uri,
    **mongoengine_connection_kwargs)


__all__ = ['bson', 'pymongo', 'gridfs', 'DbSessionController', 'mongoengine', 'mongoengine_alias']
