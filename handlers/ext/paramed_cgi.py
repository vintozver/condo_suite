# -*- coding: utf-8 -*-


import handlers.web.decorator
import util.handler


class Params(object):
    class NotFoundError(Exception):
        pass

    def __init__(self, req):
        self.query_string = handlers.web.decorator.request_parser.QueryString(req)
        if req.method == 'POST':
            content_type = req.requestHeaders.get('Content-Type')
            if content_type == 'application/json' or content_type == 'text/json':
                self.form = handlers.web.decorator.request_parser.RequestBodyParserImpl(req).as_json()
            else:
                self.form = handlers.web.decorator.request_parser.RequestBodyParserImpl(req).as_form()
        else:
            self.form = None

    def param_get(self, name):
        try:
            return self.query_string.param(name)
        except self.query_string.NotFoundError:
            raise self.NotFoundError

    def paramlist_get(self, name):
        try:
            return self.query_string.paramlist(name)
        except self.query_string.NotFoundError:
            raise self.NotFoundError

    def param_post(self, name):
        if self.form is not None:
            try:
                return self.form.param(name)
            except self.form.NotFoundError:
                raise self.NotFoundError
        else:
            raise self.NotFoundError

    def paramlist_post(self, name):
        if self.form is not None:
            try:
                return self.form.paramlist(name)
            except self.form.NotFoundError:
                raise self.NotFoundError
        else:
            raise self.NotFoundError

    def file(self, name):
        if self.form is not None:
            try:
                return self.form.file(name)
            except self.form.NotFoundError:
                raise self.NotFoundError
        else:
            raise self.NotFoundError

    def filelist(self, name):
        if self.form is not None:
            try:
                return self.form.filelist(name)
            except self.form.NotFoundError:
                raise self.NotFoundError
        else:
            raise self.NotFoundError


class HandlerError(util.handler.HandlerError):
    pass


class Handler(util.handler.Handler):
    def __init__(self, req):
        super(Handler, self).__init__(req)

        self.cgi_params = Params(req)
