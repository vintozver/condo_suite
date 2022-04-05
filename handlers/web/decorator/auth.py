# -*- coding: utf-8 -*-



import types
import urllib.request, urllib.parse, urllib.error
import http.client
import modules.mongo.user as mod_mongo_user


class AuthRequired(object):
    class Wrapper(object):
        def __init__(self, method, render='html'):
            self.method = method
            self.render = render

        def __get__(self, instance, owner):
            def wrapper(*args, **kwargs):
                # assertion checks for bound methods
                if instance is None:
                    raise AssertionError('This decorator allows only bound methods')
                # assertion checks for additional request presence requirements
                try:
                    instance.req
                except AttributeError:
                    raise AssertionError('Session decorator allows only bound methods, bound to objects with \'req\' attribute')
                try:
                    return self.method(*args, **kwargs)
                except SecurityError as err:
                    return self.view_security(instance.req, err)

            return types.MethodType(wrapper, instance)

        def __call__(self, instance, *args, **kwargs):
            return self.__get__(instance, type(instance))(*args, **kwargs)

        def view_security(self, req, err):
            tmpl_args = {'err': err, 'auth_url': '/auth/user?return_url=%s' % urllib.parse.quote_plus(req.uri)}
            import handlers.web.skeleton as mod_tmpl
            content = mod_tmpl.TemplateFactory(req, 'security').render(tmpl_args)
            req.setResponseCode(http.client.FORBIDDEN, 'Insufficient Permissions')
            req.setHeader('Cache-Control', 'public, no-cache')
            req.setHeader('Content-Type', 'text/html; charset=utf-8')
            req.write(content)

    def __init__(self, render='html'):
        self.render = render

    def __call__(self, method):
        return self.Wrapper(method, self.render)


class SecurityError(Exception):
    pass


def rbac_has_permission(session_user, permission):
    # Permission denied to anonymous
    if session_user is None:
        raise SecurityError('User is not logged in')
    # create a data model object if another object is passed.
    # in case of non data model object, it must support ``__getitem__()`` and have valid ``rbac`` item
    if not isinstance(session_user, mod_mongo_user.UserDocument):
        raise RuntimeError('session_user must be instance of modules.mongo.user.UserDocument')

    return session_user.rbac_has_permission(permission)

__all__= ['AuthRequired', 'SecurityError', 'rbac_has_permission']
