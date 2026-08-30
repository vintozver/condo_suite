# -*- coding: utf-8 -*-


from ...util.handler import Handler as _Handler, HandlerError as _HandlerError
import http.client
from ...util import handler


class HandlerError(_HandlerError):
    pass


class Handler(_Handler):
    def __call__(self, address, code=http.client.FOUND, message=http.client.responses[http.client.FOUND]):
        self.req.setResponseCode(code, message)
        self.req.setHeader('Location', address)
        self.req.setHeader('Content-Type', 'text/plain; charset=utf-8')
        self.req.write('Перенаправление на <a href="%(address)s">%(address)s</a>' % {'address': address})
