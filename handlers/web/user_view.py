# -*- coding: utf-8 -*-

import datetime
import http.client

import config

import handlers.web.skeleton as mod_tmpl
import modules.rbac as mod_rbac
import modules.mongo as mod_mongo
import modules.mongo.user as mod_mongo_user
import handlers.web.decorator as deco
import handlers.ext.paramed_cgi


class HandlerError(handlers.ext.paramed_cgi.HandlerError):
    pass


class Handler(handlers.ext.paramed_cgi.Handler):
    @deco.session.Session()
    @deco.session.SessionUser()
    def search(self):
        tmpl_data = dict()
        session_user = self.req.context.session_user
        tmpl_data['perm_user_create'] = False
        if session_user:
            tmpl_data['perm_user_create'] = session_user.rbac_has_permission('user/create')
        content = mod_tmpl.TemplateFactory(self.req, 'user.search').render(tmpl_data)
        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)

    @deco.session.Session()
    @deco.session.SessionUser()
    @deco.auth.AuthRequired(render='html')
    def view(self, id_user):
        oid_user = mod_mongo.bson.objectid.ObjectId(id_user)
        user = mod_mongo_user.UserDocument.objects(id=oid_user).first()
        if user is None:
            raise HandlerError('Database document not found', oid_user)

        session_user = self.req.context.session_user
        if session_user is None:
            raise deco.auth.SecurityError('No user authenticated')

        user_rbac_role_set = {role.id for role in user.rbac.roles}

        tmpl_data = dict()
        tmpl_data['user'] = user
        tmpl_data['ssl_crt_list'] = [
            {'serial': crt.serial, 'subject_dn': crt.subject_dn, 'issuer_dn': crt.issuer_dn}
            for crt in user.ssl_crt
        ]

        user_agent_list = [
            {
                'agent_id': str(agent.id),
                'agent_name': agent.name or '',
                'agent_position': agent.position or '',
            } for agent in user.agents
        ]

        tmpl_data['user_agent_list'] = user_agent_list

        tmpl_data['perm_edit'] = session_user.rbac_has_permission('user.info/edit')
        tmpl_data['perm_ssl_crt_add'] = session_user.rbac_has_permission('user.ssl_crt/add')
        tmpl_data['perm_ssl_crt_remove'] = session_user.rbac_has_permission('user.ssl_crt/remove')
        tmpl_data['perm_agent_add'] = session_user.rbac_has_permission('user.agent/add')
        tmpl_data['perm_agent_remove'] = session_user.rbac_has_permission('user.agent/remove')
        tmpl_data['perm_agent_update'] = session_user.rbac_has_permission('user.agent/update')
        tmpl_data['perm_role_regular_add'] = session_user.rbac_has_permission('user.role(regular)/add')
        tmpl_data['perm_role_regular_remove'] = session_user.rbac_has_permission('user.role(regular)/remove')
        # admin role management cannot be performed for the user itself. They must be managed by someone else
        tmpl_data['myself'] = session_user.id == user.id
        tmpl_data['perm_role_admin_add'] = session_user.rbac_has_permission('user.role(admin)/add')
        tmpl_data['perm_role_admin_remove'] = session_user.rbac_has_permission('user.role(admin)/remove')

        tmpl_data['roles'] = [(role, (role['uuid'] in user_rbac_role_set)) for role in mod_rbac.roles]
        tmpl_data['role_matrix'] = dict((role['uuid'].hex, {'name': role.get('name'), 'type': role.get('type')}) for role in mod_rbac.roles)
        tmpl_data['role_list'] = [{'id': role['uuid'].hex, 'name': role.get('name'), 'type': role.get('type'), 'active': role['uuid'] in user_rbac_role_set} for role in mod_rbac.roles]

        content = mod_tmpl.TemplateFactory(self.req, 'user.view').render(tmpl_data)
        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)

    @deco.session.Session()
    @deco.session.SessionUser()
    @deco.auth.AuthRequired(render='html')
    def __call__(self, id_user=None):
        session_user = self.req.context.session_user
        if session_user is None:
            raise deco.auth.SecurityError('No user authenticated')

        perm = 'user/view'
        if not session_user.rbac_has_permission(perm):
            raise deco.auth.SecurityError('Permission required', perm)

        if id_user is None:
            return self.search()
        else:
            return self.view(id_user)
