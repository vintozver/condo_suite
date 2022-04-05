# -*- coding: utf-8 -*-

import http.client

import config

import handlers.web.skeleton as mod_tmpl
import modules.mongo as mod_mongo
import handlers.web.decorator as deco
import handlers.ext.paramed_cgi


class HandlerError(handlers.ext.paramed_cgi.HandlerError):
    pass


class Handler(handlers.ext.paramed_cgi.Handler):
    @deco.session.Session()
    def check(self):
        session = self.req.context.session
        # already authenticated. Do nothing
        if session.get('id_user') is not None:
            return False
        # no valid trusted client certificate is provided
        if self.req.getHeader('X-SSL-Client-Verify') != '1':
            return False

        client_crt_serial = self.req.getHeader('X-SSL-Client-Serial')
        client_crt_s_dn = self.req.getHeader('X-SSL-Client-Subject-DN')
        client_crt_i_dn = self.req.getHeader('X-SSL-Client-Issuer-DN')
        # mandatory fields of trusted client certificate are missing
        if not client_crt_serial or not client_crt_s_dn or not client_crt_i_dn:
            return False

        with mod_mongo.DbSessionController() as db_session:
            user_obj = db_session[config.db_mongo.name]['users'].find_one({
                'ssl_crt': {'$elemMatch': {
                    'serial': client_crt_serial,
                    'subject_dn': client_crt_s_dn,
                    'issuer_dn': client_crt_i_dn,
                }},
            }, {'_id': True})
        if user_obj:
            # corresponding user is found in the database
            session['id_user'] = user_obj['_id']
            try:
                del session['id_agent']
            except KeyError:
                pass
            session.save()
            return True
        else:
            # no corresponding user is found in the database
            return False

    def __call__(self):
        tmpl_args = dict()
        if self.req.getHeader('X-SSL-Client-Verify') == '1':
            tmpl_args['serial'] = self.req.getHeader('X-SSL-Client-Serial')
            tmpl_args['subject_dn'] = self.req.getHeader('X-SSL-Client-Subject-DN')
            tmpl_args['issuer_dn'] = self.req.getHeader('X-SSL-Client-Issuer-DN')

        content = content = mod_tmpl.TemplateFactory(self.req, 'auth_ext.ssl').render(tmpl_args)
        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)
