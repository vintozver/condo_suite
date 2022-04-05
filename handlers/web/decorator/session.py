# -*- coding: utf-8 -*-

import types
import util.context
import modules.session as mod_session
import modules.mongo.user as mod_mongo_user
import modules.mongo.agent as mod_mongo_agent


class SessionController(util.context.AutoRefContextItem):
    def __init__(self, req):
        super(SessionController, self).__init__()
        self.req = req

    def new(self):
        return mod_session.MongoDbSession(self.session_cookie_reader, self.session_cookie_writer)

    def delete(self):
        pass

    def session_cookie_reader(self):
        return self.req.getCookie('sid', True, True)

    def session_cookie_writer(self, value):
        self.req.addCookie('sid', value, expires=None, domain=None, path='/', secure=False)


class Session(object):
    class Wrapper(object):
        def __init__(self, method, require=True):
            self.method = method
            self.require = require

        def __get__(self, instance, owner):
            def wrapper(*args, **kwargs):
                # assertion checks for bound methods
                if instance is None:
                    raise AssertionError('Session decorator allows only bound methods')
                # assertion checks for additional request presence requirements
                try:
                    instance.req
                except AttributeError:
                    raise AssertionError('Session decorator allows only bound methods, bound to objects with \'req\' attribute')
                instance.req.context.ref('session', lambda: SessionController(instance.req))
                try:
                    return self.method(*args, **kwargs)
                finally:
                    instance.req.context.unref('session')

            return types.MethodType(wrapper, instance)

        def __call__(self, instance, *args, **kwargs):
            return self.__get__(instance, type(instance))(*args, **kwargs)

    def __init__(self, require=True):
        self.require = require

    def __call__(self, method):
        return self.Wrapper(method, self.require)


class SessionUserController(util.context.AutoRefContextItem):
    def __init__(self, req):
        super(SessionUserController, self).__init__()
        self.req = req

    def new(self):
        id_user = self.req.context.session.get('id_user')
        if id_user is None:
            # Try authenticating user by SSL certificate if it's provided by user
            import handlers.web.auth_ext.ssl as handler_ssl
            try:
                if handler_ssl.Handler(self.req).check():
                    id_user = self.req.context.session.get('id_user')
                else:
                    return None
            except handler_ssl.HandlerError:
                return None

        user = mod_mongo_user.UserDocument.objects(id=id_user).first()
        if user is None:
            raise RuntimeError('User not found', id_user)
        return user

    def delete(self):
        pass


class SessionUser(object):
    class Wrapper(object):
        def __init__(self, method):  # decorator params declared here
            self.method = method

        def __get__(self, instance, owner):
            def wrapper(*args, **kwargs):
                # assertion checks for bound methods
                if instance is None:
                    raise AssertionError('Session decorator allows only bound methods')
                # assertion checks for additional request presence requirements
                try:
                    instance.req
                except AttributeError:
                    raise AssertionError('Session decorator allows only bound methods, bound to objects with \'req\' attribute')
                instance.req.context.ref('session_user', lambda: SessionUserController(instance.req))
                try:
                    return self.method(*args, **kwargs)
                finally:
                    instance.req.context.unref('session_user')

            return types.MethodType(wrapper, instance)

        def __call__(self, instance, *args, **kwargs):
            return self.__get__(instance, type(instance))(*args, **kwargs)

    def __init__(self):  # decorator parameters pass-through
        pass

    def __call__(self, method):
        return self.Wrapper(method)


class SessionAgentController(util.context.AutoRefContextItem):
    def __init__(self, req):
        super(SessionAgentController, self).__init__()
        self.req = req

    def new(self):
        id_agent = self.req.context.session.get('id_agent')
        if id_agent is None:
            import handlers.web.auth_agent as handler_agent
            try:
                if handler_agent.Handler(self.req).check():
                    id_agent = self.req.context.session.get('id_agent')
                else:
                    return None
            except handler_agent.HandlerError as err_agent:
                return None

        agent = mod_mongo_agent.AgentDocument.objects(id=id_agent).first()
        if agent is None:
            raise RuntimeError('Agent not found', id_agent)
        return agent

    def delete(self):
        pass


class SessionAgent(object):
    class Wrapper(object):
        def __init__(self, method):  # decorator params declared here
            self.method = method

        def __get__(self, instance, owner):
            def wrapper(*args, **kwargs):
                # assertion checks for bound methods
                if instance is None:
                    raise AssertionError('Session decorator allows only bound methods')
                # assertion checks for additional request presence requirements
                try:
                    instance.req
                except AttributeError:
                    raise AssertionError('Session decorator allows only bound methods, bound to objects with \'req\' attribute')
                instance.req.context.ref('session_agent', lambda: SessionAgentController(instance.req))
                try:
                    return self.method(*args, **kwargs)
                finally:
                    instance.req.context.unref('session_agent')

            return types.MethodType(wrapper, instance)

        def __call__(self, instance, *args, **kwargs):
            return self.__get__(instance, type(instance))(*args, **kwargs)

    def __init__(self):  # decorator parameters pass-through
        pass

    def __call__(self, method):
        return self.Wrapper(method)


__all__ = ['Session', 'SessionUser', 'SessionAgent']
