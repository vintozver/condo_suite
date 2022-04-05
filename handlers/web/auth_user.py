# -*- coding: utf-8 -*-

import http.client
import urllib.request, urllib.parse, urllib.error
import json
import modules.rbac as mod_rbac
import handlers.web.skeleton as mod_tmpl
import handlers.web.decorator as deco
import handlers.ext.paramed_cgi


class HandlerError(handlers.ext.paramed_cgi.HandlerError):
    pass


class Handler(handlers.ext.paramed_cgi.Handler):
    @deco.session.Session()
    @deco.session.SessionUser()
    def __call__(self):
        session_user = self.req.context.session_user

        tmpl_args = dict()
        if session_user is not None:
            tmpl_args['authenticated'] = True
            tmpl_args['user'] = session_user
            tmpl_args['ssl_crt_list'] = [
                {'serial': crt.serial, 'subject_dn': crt.subject_dn, 'issuer_dn': crt.issuer_dn}
                for crt in session_user.ssl_crt
            ]
            user_rbac_role_set = {role.id for role in session_user.rbac.roles}
            tmpl_args['roles'] = [(role, (role['uuid'] in user_rbac_role_set)) for role in mod_rbac.roles]

            tmpl_args['google_email_list'] = session_user.ext.google.email
        else:
            tmpl_args['authenticated'] = False

        try:
            return_url = self.cgi_params.param_get('return_url')
            if not return_url:
                raise self.cgi_params.NotFoundError()
        except self.cgi_params.NotFoundError:
            return_url = None
        if return_url:
            tmpl_args['return_url'] = return_url

        if return_url:
            google_auth_url = '/auth/ext/google?state=%s' % urllib.parse.quote_plus(json.dumps({'return_url': return_url}))
        else:
            google_auth_url = '/auth/ext/google'
        tmpl_args['google_auth_url'] = google_auth_url
        tmpl_args['ssl_auth_url'] = '/auth/ext/ssl'

        content = mod_tmpl.TemplateFactory(self.req, 'auth_user').render(tmpl_args)
        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)
