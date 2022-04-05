# -*- coding: utf-8 -*-

import modules.mongo as mod_mongo
import handlers.web.decorator as deco
import handlers.ext.paramed_cgi


class HandlerError(handlers.ext.paramed_cgi.HandlerError):
    pass


class Handler(handlers.ext.paramed_cgi.Handler):
    @deco.session.Session()
    @deco.session.SessionUser()
    def __call__(self, id_agent, position=None):
        id_agent = mod_mongo.bson.objectid.ObjectId(id_agent)

        session = self.req.context.session
        session_user = self.req.context.session_user
        if session_user is None:
            raise HandlerError('User is not authenticated. Cannot switch agents.')
        if id_agent in [agent.id for agent in session_user.agents]:
            session['id_agent'] = id_agent
            session['agent_position'] = position or None
            session.save()
        else:
            raise HandlerError('User does not have requested agent allowed')

        import handlers.ext.redirect as redirector
        try:
            return redirector.Handler(self.req)('/auth')
        except redirector.HandlerError as err:
            raise HandlerError('Error in handler', err)
