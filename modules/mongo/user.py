# -*- coding: utf-8 -*-

import re


import modules.mongo as mod_mongo
import modules.rbac as mod_rbac


class SslCrtDocument(mod_mongo.mongoengine.EmbeddedDocument):
    serial = mod_mongo.mongoengine.StringField(max_length=128, required=True)
    subject_dn = mod_mongo.mongoengine.StringField(max_length=256, required=True)
    issuer_dn = mod_mongo.mongoengine.StringField(max_length=256, required=True)


class GoogleExtDocument(mod_mongo.mongoengine.EmbeddedDocument):
    email = mod_mongo.mongoengine.ListField(mod_mongo.mongoengine.StringField(required=True, max_length=64), default=list)


class ExtDocument(mod_mongo.mongoengine.EmbeddedDocument):
    google = mod_mongo.mongoengine.EmbeddedDocumentField(GoogleExtDocument, default=GoogleExtDocument)


class AgentDocument(mod_mongo.mongoengine.EmbeddedDocument):
    id = mod_mongo.mongoengine.ObjectIdField(db_field='_id')
    name = mod_mongo.mongoengine.StringField(max_length=128)
    position = mod_mongo.mongoengine.StringField(max_length=128)


class RoleDocument(mod_mongo.mongoengine.EmbeddedDocument):
    id = mod_mongo.mongoengine.UUIDField(db_field='_id')
    name = mod_mongo.mongoengine.StringField(max_length=128)


class RbacDocument(mod_mongo.mongoengine.EmbeddedDocument):
    roles = mod_mongo.mongoengine.EmbeddedDocumentListField(RoleDocument, default=list)


class UserDocument(mod_mongo.mongoengine.Document):
    meta = {'db_alias': mod_mongo.mongoengine_alias, 'collection': 'users', 'strict': False}

    # basic info
    name = mod_mongo.mongoengine.StringField(max_length=128)
    email = mod_mongo.mongoengine.StringField(max_length=64)
    # SSL certificate list
    ssl_crt = mod_mongo.mongoengine.EmbeddedDocumentListField(SslCrtDocument, default=list)
    # External modules
    ext = mod_mongo.mongoengine.EmbeddedDocumentField(ExtDocument, default=ExtDocument)
    # linked agents
    agents = mod_mongo.mongoengine.EmbeddedDocumentListField(AgentDocument, default=list)
    # global RBAC
    rbac = mod_mongo.mongoengine.EmbeddedDocumentField(RbacDocument, default=RbacDocument)

    # additional methods

    def rbac_has_permission(self, permission):
        """
        Check permission for the user by searching assigned roles. Exact match is checked.
        This method requires object created with a projection `{'rbac': True}` or loaded from database similar way.


        :param permission: requested permission
        :return: True if access is granted, False if access is denied
        """

        for role in self.rbac_roles():
            if permission in role['permissions']:
                return True

        return False

    def rbac_regex_permission(self, permission_regex):
        """
        Check permission for the user by searching assigned roles. Checks are performed by regexing the permissions with the provided template.
        This method requires object created with a projection `{'rbac': True}` or loaded from database similar way.


        :param permission_regex: requested permission regex. If it's not regex object, RegEx compilation will be performed.
        :return: True if access is granted, False if access is denied
        """

        permission_regex = re.compile(permission_regex)

        for role in self.rbac_roles():
            for role_permission in role['permissions']:
                if permission_regex.match(role_permission):
                    return True

        return False

    def rbac_roles(self):
        """
        Get list of RBAC roles assigned to the user
        This method requires object created with a projection `{'rbac': True}` or loaded from database similar way.

        :return: list of dictionary objects, each with `uuid`, `name` fields, and `permissions` field as a list of permissions assigned to the role
        """
        return list(self._rbac_roles())

    def _rbac_roles(self):
        """Helper for `rbac_roles` method"""
        for role in self.rbac.roles:
            if role.id in mod_rbac.roles_by_uuid:
                yield mod_rbac.roles_by_uuid[role.id]


class UserRef(mod_mongo.mongoengine.EmbeddedDocument):
    id = mod_mongo.mongoengine.ObjectIdField(db_field='_id', required=True)
    name = mod_mongo.mongoengine.StringField(max_length=128)
