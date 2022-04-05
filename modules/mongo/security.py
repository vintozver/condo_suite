# -*- coding: utf-8 -*-

import modules.mongo as mod_mongo
from modules.mongo.agent import AgentRef
from modules.mongo.user import UserRef


class Ref(mod_mongo.mongoengine.DynamicEmbeddedDocument):
    agent = mod_mongo.mongoengine.EmbeddedDocumentField(AgentRef)
    user = mod_mongo.mongoengine.EmbeddedDocumentField(UserRef)
