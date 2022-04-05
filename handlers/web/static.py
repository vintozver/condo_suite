# -*- coding: utf-8 -*-

import pkg_resources
import os.path
import http.client


import handlers.ext.paramed_cgi


class HandlerError(handlers.ext.paramed_cgi.HandlerError):
    pass


class Handler(handlers.ext.paramed_cgi.Handler):
    def view_notfound(self, err):
        import handlers.web.skeleton as mod_tmpl
        try:
            content = mod_tmpl.TemplateFactory(self.req, 'error_notfound').render({'description': err})
        except mod_tmpl.TemplateError:
            raise HandlerError('Template error')
        self.req.setResponseCode(http.client.NOT_FOUND, http.client.responses[http.client.NOT_FOUND])
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)

    def __call__(self, path):
        if path.find('/') != 0:
            raise HandlerError('Попытка взлома! Допускается только полный путь к документу')
        rel_path = path[1:]
        base_path = os.path.normpath(pkg_resources.resource_filename(__name__, '../../run/static'))
        file_path = os.path.normpath(os.path.join(base_path, rel_path))
        if os.path.commonprefix((base_path, file_path)) != base_path:
            raise HandlerError('Попытка взлома! Путь не находится в базовом каталоге статики')

        import handlers.ext.static as mod
        try:
            return mod.Handler(self.req)(path=file_path)
        except mod.NotFoundError as err:
            return self.view_notfound(err.args[0])
        except mod.HandlerError as err:
            raise HandlerError('Error in dependent handler', err)
