# -*- coding: utf-8 -*-

import http.client
import email.utils

import config

import handlers.web.skeleton as mod_tmpl
import modules.rbac as mod_rbac
import modules.mongo as mod_mongo
import handlers.web.decorator as deco
import handlers.ext.paramed_cgi


class HandlerError(handlers.ext.paramed_cgi.HandlerError):
    pass


class Handler(handlers.ext.paramed_cgi.Handler):
    def view(self, mailbox):
        def msgs_query():
            def case_addr(value):
                if isinstance(value, str):
                    return value, value
                else:
                    return value.get('name'), value.get('email')

            with mod_mongo.DbSessionController() as db_session:
                for db_doc in db_session[config.db_mongo.name]['mailbox.%s' % mailbox].find({}, sort=[('_id', mod_mongo.pymongo.DESCENDING)], limit=100):
                    msg = dict()
                    msg['_id'] = db_doc['_id']
                    value = db_doc.get('date')
                    if value is not None:
                        msg['date'] = value
                    value = db_doc.get('from', {})
                    if value:
                        msg['from'] = case_addr(value)
                    value = db_doc.get('to', {})
                    if value:
                        msg['to'] = case_addr(value)
                    value = db_doc.get('subject')
                    if value:
                        msg['subject'] = value

                    yield msg

        tmpl_data = dict()
        tmpl_data['mailbox'] = mailbox
        tmpl_data['msgs'] = list(msgs_query())

        content = mod_tmpl.TemplateFactory(self.req, 'mailbox.view').render(tmpl_data)
        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)

    @deco.session.Session()
    @deco.session.SessionUser()
    @deco.auth.AuthRequired(render='html')
    def __call__(self, mailbox, action='view'):
        if mailbox not in config.mail.known_mailboxes:
            raise HandlerError('Mailbox is not known', mailbox)

        session_user = self.req.context.session_user
        if session_user is None:
            raise deco.auth.SecurityError('No current user selected')

        if not session_user.rbac_has_permission('mailbox/view') and not session_user.rbac_has_permission('mailbox.%s/view' % mailbox):
            raise deco.auth.SecurityError('Permission required', None)

        if action == 'view':
            self.view(mailbox)
        else:
            raise HandlerError('Undefined action', action)
