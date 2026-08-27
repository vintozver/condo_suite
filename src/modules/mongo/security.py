# -*- coding: utf-8 -*-

from .. import mongo as mod_mongo
from .agent import AgentRef
from .user import UserRef


class Ref(mod_mongo.mongoengine.DynamicEmbeddedDocument):
    agent = mod_mongo.mongoengine.EmbeddedDocumentField(AgentRef)
    user = mod_mongo.mongoengine.EmbeddedDocumentField(UserRef)
