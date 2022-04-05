# -*- coding: utf-8 -*-

import typing
import sys
import json
import http
import modules.mongo as mod_mongo
import modules.mongo.transaction as mod_mongo_transaction
import modules.mongo.agent as mod_mongo_agent
import modules.mongo.user as mod_mongo_user
import handlers.web.decorator as deco
import handlers.ext.paramed_cgi


class HandlerError(handlers.ext.paramed_cgi.HandlerError):
    pass


class BadRequestError(HandlerError):
    pass


class NoPermissionError(HandlerError):
    pass


class ViewHandler(object):
    def __init__(self, txn: mod_mongo_transaction.Transaction):
        self.txn = txn  # type: mod_mongo_transaction.Transaction

    def check_permissions(self, agent: mod_mongo_agent.AgentDocument, user: mod_mongo_user.UserDocument) -> bool:
        raise NotImplementedError()

    def render_form(self, req) -> str:
        raise NotImplementedError()

    def render_object(self) -> typing.Any:
        raise NotImplementedError()


class Handler(handlers.ext.paramed_cgi.Handler):
    @deco.session.Session()
    @deco.session.SessionUser()
    @deco.session.SessionAgent()
    @deco.auth.AuthRequired(render='html')
    def __call__(self, id_transaction):
        # Request transaction object
        txn = mod_mongo_transaction.Transaction.objects(id=mod_mongo.bson.objectid.ObjectId(id_transaction)).get()
        if txn is None:
            raise HandlerError('Transaction not found', id_transaction)

        # Check permissions
        session_agent = self.req.context.session_agent
        if session_agent is None:
            raise deco.auth.SecurityError('No agent authenticated')

        # Check permissions
        session_user = self.req.context.session_user
        if session_user is None:
            raise deco.auth.SecurityError('No user authenticated')

        admin_view = session_user.rbac_has_permission('admin.transaction.view')

        # Import module based on transaction type
        if not txn.type:
            raise HandlerError('Transaction type is not set', id_transaction)
        mod_view_type = 'handlers.web.transaction.view_%s' % txn.type
        try:
            __import__(mod_view_type)
        except ImportError:
            raise HandlerError('Transaction type is unknown', txn.type)
        mod_view_type = sys.modules[mod_view_type]
        mod_view_obj = mod_view_type.ViewHandler(txn)

        # Process based on transaction type.
        # If admin_view is set - authorized user is admin,
        # otherwise - checks must be performed if current user can view the transaction
        # Basically, creator or related to it person may view the transaction
        if not admin_view:
            if not mod_view_obj.check_permissions(session_agent, session_user):
                if self.req.request_headers.get('Content-Type') == 'application/json':
                    self.req.setResponseCode(http.HTTPStatus.FORBIDDEN.value, http.HTTPStatus.FORBIDDEN.phrase)
                    self.req.setHeader('Cache-Control', 'public, no-cache')
                    self.req.setHeader('Content-Type', 'text/plain')
                    return b'You are not authorized to view this item',
                else:
                    raise deco.auth.SecurityError('You are not authorized to view this item')
        try:
            if self.req.request_headers.get('Content-Type') == 'application/json':
                content = json.dumps(mod_view_obj.render_object()).encode('utf-8')
                self.req.setResponseCode(http.HTTPStatus.OK.value, http.HTTPStatus.OK.phrase)
                self.req.setHeader('Cache-Control', 'public, no-cache')
                self.req.setHeader('Content-Type', 'application/json')
                return content,
            else:
                content = mod_view_obj.render_form(self.req).encode('utf-8')
                self.req.setResponseCode(http.HTTPStatus.OK.value, http.HTTPStatus.OK.phrase)
                self.req.setHeader('Cache-Control', 'public, no-cache')
                self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
                return content,
        except NotImplementedError:
            self.req.setResponseCode(http.HTTPStatus.NOT_IMPLEMENTED.value, http.HTTPStatus.NOT_IMPLEMENTED.phrase)
            self.req.setHeader('Cache-Control', 'public, no-cache')
            self.req.setHeader('Content-Type', 'text/plain')
            return b'Could not process this request because the handler is not implemented',
