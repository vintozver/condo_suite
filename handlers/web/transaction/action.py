# -*- coding: utf-8 -*-

import http.client
import json
import handlers.web.decorator as deco
import handlers.ext.paramed_cgi
import modules.mongo as mod_mongo
import modules.mongo.transaction as mod_mongo_transaction
import handlers.defer
import util.defer as util_defer


class HandlerError(handlers.ext.paramed_cgi.HandlerError):
    pass


class Handler(handlers.ext.paramed_cgi.Handler):
    def render_forbidden(self):
        self.req.setResponseCode(http.client.FORBIDDEN, http.client.responses[http.client.FORBIDDEN])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'text/plain')
        self.req.write('You are not authorized to perform this action')

    def render_txn(self, txn):
        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'application/json')
        self.req.write(json.dumps({
            'type': txn.type,
            'state': txn.state,
            'last_mod': txn.last_mod.isoformat(),
        }))

    @deco.session.Session()
    @deco.session.SessionUser()
    def __call__(self, id_txn, action):
        oid_txn = mod_mongo.bson.ObjectId(id_txn)
        txn = mod_mongo_transaction.Transaction.objects(id=oid_txn).get()
        if txn is None:
            raise HandlerError('Transaction not found', id_txn)

        # Check if authenticated
        session_user = self.req.context.session_user
        if session_user is None:
            return self.render_forbidden()

        if action in ('commit', 'cancel', 'recover'):
            util_defer.the_app.send_task('handlers.defer.TransactionProcessor', kwargs={
                'id_txn': oid_txn,
                'action': action,
            })
            return self.render_txn(txn)
        else:
            raise HandlerError('Unknown action', action)
