# -*- coding: utf-8 -*-

import http.client

import config
import handlers.web.skeleton as mod_tmpl
import handlers.web.decorator as deco
import handlers.ext.paramed_cgi
import modules.mongo.transaction as mod_mongo_transaction


class HandlerError(handlers.ext.paramed_cgi.HandlerError):
    pass


class Handler(handlers.ext.paramed_cgi.Handler):
    @deco.session.Session()
    @deco.auth.AuthRequired(render='html')
    def __call__(self):
        def yield_complete():
            for txn in mod_mongo_transaction.Transaction.objects(__raw__={'state': {'$in': ['completed', 'cancelled']}}).order_by('-id')[:100]:
                yield {
                    'id': str(txn.id),
                    'type': str(txn.type),
                    'created': txn.id.generation_time.astimezone(config.main.timezone),
                    'last_mod': txn.last_mod,
                    'state': txn.state,
                }

        def yield_incomplete():
            for txn in mod_mongo_transaction.Transaction.objects(__raw__={'state': {'$nin': ['completed', 'cancelled']}}).order_by('-id')[:100]:
                yield {
                    'id': str(txn.id),
                    'type': str(txn.type),
                    'created': txn.id.generation_time.astimezone(config.main.timezone),
                    'last_mod': txn.last_mod,
                    'state': txn.state,
                }

        content = mod_tmpl.TemplateFactory(self.req, 'transaction.__list__').render({
            'txns_complete': list(yield_complete()),
            'txns_incomplete': list(yield_incomplete()),
        })
        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)
