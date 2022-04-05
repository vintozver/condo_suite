# -*- coding: utf-8 -*-


import http.client
import util.handler


class HandlerError(util.handler.HandlerError):
    pass


class Handler(util.handler.Handler):
    def __call__(self, address, code=http.client.FOUND, message=http.client.responses[http.client.FOUND]):
        self.req.setResponseCode(code, message)
        self.req.setHeader('Location', address)
        self.req.setHeader('Content-Type', 'text/plain; charset=utf-8')
        self.req.write('Перенаправление на <a href="%(address)s">%(address)s</a>' % {'address': address})
