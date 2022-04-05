#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import uuid
import sys

import config
import modules.mongo as mod_mongo

embedded_roles = [
    # Global log group
    {
        'uuid': uuid.UUID('d5ba84d44b6f417fb2f38835f60cffc2'), 'name': 'View global log', 'sort_order': 1,
        'permissions': ['log.global/view']
    },
    {
        'uuid': uuid.UUID('710c347619d04025a6d1c5bb0fbbbef5'), 'name': 'Clear global log', 'sort_order': 2,
        'permissions': ['log.global/clear']
    },
    # Transaction group. Transaction initiator always has view permission in order to make stuff work
    {
        'uuid': uuid.UUID('2fdf93cf09e64dfabc8d2e583822ae0a'), 'name': 'Transaction view', 'sort_order': 3,
        'permissions': ['transaction/view', 'transaction.view', 'admin.transaction.view']
    },
    # User
    {
        'uuid': uuid.UUID('ff9d46d000184a3a9455ff5aad31f304'), 'name': 'User information view', 'sort_order': 11,
        'permissions': ['user/view']
    },
    {
        'uuid': uuid.UUID('e7cd126d774d4da9ab82504e17fa9578'), 'name': 'User information edit', 'sort_order': 12,
        'permissions': ['user.info/edit']
    },
    {
        'uuid': uuid.UUID('c74c27f13bab4130807d67b4902ffa05'),
        'name': 'User SSL certificate management',
        'sort_order': 20,
        'permissions': ['user.ssl_crt/add', 'user.ssl_crt/remove']
    },
    {
        'uuid': uuid.UUID('26a4af63f943477898eb9d6e9f4755ef'), 'name': 'User agent management', 'sort_order': 21,
        'permissions': ['user.agent/add', 'user.agent/remove', 'user.agent/update']
    },
    {
        'uuid': uuid.UUID('274188d5ad8b47ecb9e4dbd4a87583c7'),
        'name': 'User role management (grant/revoke any role including this)', 'type': 'admin', 'sort_order': 22,
        'permissions': [
            'user.role(regular)/add', 'user.role(regular)/remove', 'user.role(admin)/add', 'user.role(admin)/remove',
        ]
    },
    {
        'uuid': uuid.UUID('d8fa8a477e37451fbebd2519b3ba8a87'),
        'name': 'User regular role management (grant/revoke any role other than admin role)',
        'type': 'admin',
        'sort_order': 23,
        'permissions': [
            'user.role(regular)/add', 'user.role(regular)/remove',
        ]
    },
    {
        'uuid': uuid.UUID('e9c0cfe079254f9698e424b6d81579d6'),
        'name': 'User admin role management (grant/revoke admin roles only)',
        'type': 'admin',
        'sort_order': 24,
        'permissions': [
            'user.role(admin)/add', 'user.role(admin)/remove',
        ]
    },
    {
        'uuid': uuid.UUID('4c48bc46a53f4f8dacebbb33f7606d6b'), 'name': 'User create', 'sort_order': 4002,
        'permissions': ['user/create']
    },
    # Agent
    {
        'uuid': uuid.UUID('3d47228f0c4941ea826ecab0b8163e23'), 'name': 'Agent info view', 'sort_order': 4006,
        'permissions': ['agent/view']
    },
    {
        'uuid': uuid.UUID('45a74563f641426b97f23c2c3b92e519'), 'name': 'Agent info update', 'sort_order': 4007,
        'permissions': [
            'agent/update', 'agent.address/create', 'agent.address/update', 'agent.address/delete',
        ]
    },
    {
        'uuid': uuid.UUID('d640125f76474d92bcbefd2b3f2e1ff2'), 'name': 'Agent create', 'sort_order': 4008,
        'permissions': ['agent/create']
    },
    {
        'uuid': uuid.UUID('e02e2b5c6ef742a9afbf6fe9d784e1b1'), 'name': 'Agent close', 'sort_order': 4009,
        'permissions': ['agent/close']
    },
    # Parking event
    {
        'uuid': uuid.UUID('c1655e5148b9481fbf2669d60a78138b'),
        'name': 'Create parking event, append parking event history',
        'sort_order': 1001,
        'permissions': [
            'parking.event/create', 'parking.event/comment'
        ]
    },
    {
        'uuid': uuid.UUID('d6a545b991ca4dc0a25ef2196e02c34a'),
        'name': 'View parking event',
        'sort_order': 1002,
        'permissions': [
            'parking.event/view'
        ]
    },
]

permission_regex = re.compile('^(\\w+)(\\(((\\w+)=)?\\w+\\))*(\\.(\\w+)(\\(((\\w+)=)?(\\w+)\\))*)*(/(\\w+))?$')


def validate_permission(perm):
    return permission_regex.match(perm) is not None


def deploy():
    import datetime
    dt = datetime.datetime.utcnow()

    with mod_mongo.DbSessionController() as db_session:
        role_collection = db_session[config.db_mongo.name]['rbac.role']
        for role in embedded_roles:
            role_doc = mod_mongo.bson.son.SON()
            role_doc['_id'] = role['uuid']  # this will be serialized to bson type binary subtype UUID
            role_doc['name'] = role['name']
            if 'type' in role:
                role_doc['type'] = role['type']
            role_doc['sort_order'] = role.get('sort_order', 0)
            role_doc['permissions'] = role.get('permissions', [])
            for role_doc_permission in role_doc['permissions']:
                if not validate_permission(role_doc_permission):
                    raise RuntimeError('Permission does not match the regex', role_doc_permission)
            role_doc['updated'] = dt
            role_collection.replace_one({'_id': role_doc['_id']}, role_doc, True)

        # Remove old records which were not updated
        role_collection.remove({'updated': {'$lt': dt}}, True)


if __name__ == '__main__':
    sys.stdout.write('Performing RBAC deployment ... ')
    deploy()
    sys.stdout.write('done.\n')
