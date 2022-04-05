# -*- coding: utf-8 -*-

import util.handler
import handlers.web.decorator as deco
import modules.templates.filesystem as mod_tmpl_fs


class HandlerError(util.handler.HandlerError):
    pass


class Handler(util.handler.Handler):
    @deco.session.Session()
    @deco.session.SessionUser()
    @deco.session.SessionAgent()
    def tmpl_params(self):
        tmpl_params = dict()
        session_user = self.req.context.session_user
        if session_user is not None:
            tmpl_params['menu_render_parking'] = session_user.rbac_regex_permission('^parking(\\(((\\w+)=)?\\w+\\))*(\\.(\\w+)(\\(((\\w+)=)?(\\w+)\\))*)*/(\\w+)$')
            tmpl_params['menu_render_admin'] = True

            session_user_name = session_user.name
            if session_user_name:
                tmpl_params['menu_user_name'] = session_user_name

        session_agent = self.req.context.session_agent
        if session_agent is not None:
            session_agent_name = session_agent.name
            if session_agent_name:
                tmpl_params['menu_agent_name'] = session_agent_name

        session_agent_position = self.req.context.session.get('agent_position')
        if session_agent_position is not None:
            tmpl_params['menu_agent_position'] = session_agent_position

        return tmpl_params


def TemplateFactory(req, name):
    try:
        tmpl_params = Handler(req).tmpl_params()
    except HandlerError as err:
        raise mod_tmpl_fs.TemplateError('Error retrieving skeleton params', err)
    return mod_tmpl_fs.TemplateFactory(name, globals=tmpl_params)


TemplateError = mod_tmpl_fs.TemplateError


__all__ = ['TemplateFactory', 'TemplateError']
