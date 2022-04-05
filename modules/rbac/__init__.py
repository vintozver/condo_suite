# -*- coding: utf-8 -*-

# = RBAC =
# The objective is to be able to check if ROLE is allowed to access RESOURCE to perform an ACTION
#
# == Technical info ==
# (RESOURCE, ACTION) == PERMISSION
# ROLE is assigned to USER;  1 x USER has [0, inf) x ROLE
# PERMISSION is assigned to ROLE;  1 x ROLE has [0, inf) x PERMISSION
# PERMISSION: {"resource": "document", "action": "view"}


import typing


# List of permissions and roles available
permissions = list()  # type: typing.List
roles = list()  # type: typing.List
roles_by_uuid = dict()  # type: typing.Mapping
roles_by_name = dict()  # type: typing.Mapping


def preload_roles(l_roles=roles, l_roles_by_uuid=roles_by_uuid, l_roles_by_name=roles_by_name):
    """
    This function preloads roles/permissions from the database. If roles/permissions collections are changed, the process must be restarted to take the effect
    :param l_roles: (will be modified) object to save list of loaded roles. Must be list instance
    :param l_roles_by_uuid: (will be modified) object to save mapping uuid->role of loaded roles. Must be dict instance.
    :param l_roles_by_name: (will be modified) object to save mapping name->role of loaded roles. Must be dict instance.
    :return: None
    """

    # clear objects from old data
    del l_roles[:]
    l_roles_by_uuid.clear()
    l_roles_by_name.clear()

    import config
    import modules.mongo as mod_mongo
    from collections import OrderedDict
    with mod_mongo.DbSessionController() as db_session:
        for role_doc in db_session[config.db_mongo.name]['rbac.role'].with_options(mod_mongo.bson.codec_options.CodecOptions(document_class=OrderedDict)).find({}).sort([('sort_order', mod_mongo.pymongo.ASCENDING)]):
            role_id = role_doc['_id'].as_uuid(uuid_representation=mod_mongo.bson.binary.UuidRepresentation.PYTHON_LEGACY)
            role_name = role_doc['name']
            role_permissions = role_doc['permissions']
            role_obj = {'uuid': role_id, 'name': role_name, 'type': role_doc.get('type'), 'permissions': role_permissions}

            # fill objects with new data
            l_roles.append(role_obj)
            l_roles_by_uuid[role_id] = role_obj
            l_roles_by_name[role_name] = role_obj


preload_roles()


__all__ = ['permissions', 'roles', 'roles_by_uuid', 'roles_by_name', 'preload_roles']
