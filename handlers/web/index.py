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
    @deco.session.SessionUser()
    def __call__(self):
        session_user = self.req.context.session_user
        if session_user is not None:
            global_log = session_user.rbac_has_permission('log.global/view')
        else:
            global_log = False

        tmpl_args = dict()
        if global_log:
            with mod_mongo.DbSessionController() as db_session:
                eventlog_items = db_session[config.db_mongo.name]['eventlog'].find({'type': 'action'}, sort=(('dt', mod_mongo.pymongo.DESCENDING),), limit=10)
                tmpl_args['eventlog_items'] = [item for item in eventlog_items]
                tmpl_args['eventlog_size'] = 10

        content = mod_tmpl.TemplateFactory(self.req, 'index').render(tmpl_args)
        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)
