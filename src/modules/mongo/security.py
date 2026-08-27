# -*- coding: utf-8 -*-

import condo_suite.modules.mongo as mod_mongo
from condo_suite.modules.mongo.agent import AgentRef
from condo_suite.modules.mongo.user import UserRef


class Ref(mod_mongo.mongoengine.DynamicEmbeddedDocument):
    agent = mod_mongo.mongoengine.EmbeddedDocumentField(AgentRef)
    user = mod_mongo.mongoengine.EmbeddedDocumentField(UserRef)
