# -*- coding: utf-8 -*-

import sys
import os
import traceback
import re
import http.client

from util.logger import Logger
import config

import util.handler
import collections
from functools import reduce


class Handler(util.handler.Handler):
    ROUTE_MAP = [
        {'regex': re.compile(r'^/$'), 'handler': 'handlers.web.index'},
        {'regex': re.compile(r'^/static(/.*)$'), 'handler': 'handlers.web.static', 'params': {'path': lambda rex: rex.group(1)}},
        {'regex': re.compile(r'^/\bparking\b'), 'map': [
            {'regex': re.compile(r'^/?$'), 'handler': 'handlers.web.parking_menu'},
            {'regex': re.compile(r'^/event/?$'), 'handler': 'handlers.web.parking_event_search'},
            {'regex': re.compile(r'^/event/new/?$'), 'handler': 'handlers.web.parking_event_new'},
            {'regex': re.compile(r'^/event/view/([0123456789abcdef]+)/?$'), 'handler': 'handlers.web.parking_event_view', 'params': {'oid': lambda rex: rex.group(1)}},
            {'regex': re.compile(r'^/event/view/([0123456789abcdef]+)/file/([0123456789abcdef]+)/?$'), 'handler': 'handlers.web.parking_event_file', 'params': {
                'doc_oid': lambda rex: rex.group(1), 'file_oid': lambda rex: rex.group(2)
            }},
            {'regex': re.compile(r'^/event/amend/([0123456789abcdef]+)/?$'), 'handler': 'handlers.web.parking_event_amend', 'params': {'oid': lambda rex: rex.group(1)}},
            {'regex': re.compile(r'^/event/helper/autocomplete/VIN/?$'), 'handler': 'handlers.web.parking_event_helpers', 'params': {'action': ('autocomplete', 'VIN')}},
            {'regex': re.compile(r'^/event/helper/autocomplete/tag/?$'), 'handler': 'handlers.web.parking_event_helpers', 'params': {'action': ('autocomplete', 'tag')}},
        ]},
        {'regex': re.compile(r'^/\blink\b'), 'map': [
            {'regex': re.compile(r'^/?$'), 'handler': 'handlers.web.link'},
        ]},
        {'regex': re.compile(r'^/\btransaction\b'), 'map': [
            {'regex': re.compile(r'^/?$'), 'handler': 'handlers.web.transaction.list'},
            {'regex': re.compile(r'^/view/([0123456789abcdef]+)/?$'), 'handler': 'handlers.web.transaction.view', 'params': {'id_transaction': lambda rex: rex.group(1)}},
            {'regex': re.compile(r'^/commit/([0123456789abcdef]+)/?$'), 'handler': 'handlers.web.transaction.action', 'params': {'id_txn': lambda rex: rex.group(1), 'action': 'commit'}},
            {'regex': re.compile(r'^/cancel/([0123456789abcdef]+)/?$'), 'handler': 'handlers.web.transaction.action', 'params': {'id_txn': lambda rex: rex.group(1), 'action': 'cancel'}},
            {'regex': re.compile(r'^/recover/([0123456789abcdef]+)/?$'), 'handler': 'handlers.web.transaction.action', 'params': {'id_txn': lambda rex: rex.group(1), 'action': 'recover'}},
        ]},
        {'regex': re.compile(r'^/\bauth\b'), 'map': [
            {'regex': re.compile(r'^/?$'), 'handler': 'handlers.ext.redirect', 'params': {'address': '/auth/user'}},
            {'regex': re.compile(r'^/user/?$'), 'handler': 'handlers.web.auth_user'},
            {'regex': re.compile(r'^/agent/?$'), 'handler': 'handlers.web.auth_agent'},
            {'regex': re.compile(r'^/info/?$'), 'handler': 'handlers.web.auth_info'},  # JSON handler
            {'regex': re.compile(r'^/ext/ssl/?$'), 'handler': 'handlers.web.auth_ext.ssl'},
            {'regex': re.compile(r'^/ext/google/?$'), 'handler': 'handlers.web.auth_ext.google'},
        ]},
        {'regex': re.compile(r'^/\buser\b'), 'map': [
            {'regex': re.compile(r'^/?$'), 'handler': 'handlers.web.user_view'},
            {'regex': re.compile(r'^/new/?$'), 'handler': 'handlers.web.user_new'},
            {'regex': re.compile(r'^/view/([0123456789abcdef]+)/?$'), 'handler': 'handlers.web.user_view', 'params': {'id_user': lambda rex: rex.group(1)}},
            {'regex': re.compile(r'^/del/([0123456789abcdef]+)/?$'), 'handler': 'handlers.web.user_del', 'params': {'id_user': lambda rex: rex.group(1)}},
            {'regex': re.compile(r'^/update/([0123456789abcdef]+)/?$'), 'handler': 'handlers.web.user_update', 'params': {'id_user': lambda rex: rex.group(1)}},  # JSON handler
            {'regex': re.compile(r'^/helper/autocomplete/search/?$'), 'handler': 'handlers.web.user_helpers', 'params': {'action': ('autocomplete', 'search')}},  # JSON handler
            {'regex': re.compile(r'^/helper/autocomplete/search/agent/?$'), 'handler': 'handlers.web.user_helpers', 'params': {'action': ('autocomplete', 'search', 'agent')}},  # JSON handler
        ]},
        {'regex': re.compile(r'^/\bagent\b'), 'map': [
            {'regex': re.compile(r'^/?$'), 'handler': 'handlers.ext.redirect', 'params': {'address': '/agent/edit'}},
            {'regex': re.compile(r'^/edit/?$'), 'handler': 'handlers.web.agent_edit'},
            {'regex': re.compile(r'^/switch/([0123456789abcdef]+)/?$'), 'handler': 'handlers.web.agent_switch', 'params': {'id_agent': lambda rex: rex.group(1)}},
            {'regex': re.compile(r'^/switch/([0123456789abcdef]+)/([\w ]+)/?$'), 'handler': 'handlers.web.agent_switch', 'params': {'id_agent': lambda rex: rex.group(1), 'position': lambda rex: rex.group(2)}},
            {'regex': re.compile(r'^/discard/?$'), 'handler': 'handlers.web.agent_switch', 'params': {'id_agent': None}},
        ]},
    ]

    @classmethod
    def handle_map(cls, route_map, path):
        for route_item in route_map:
            regex = route_item['regex']
            match = regex.match(path)
            if match is not None:
                if 'map' in route_item:
                    result = cls.handle_map(route_item['map'], regex.sub('', path, 1))
                    if result is not None:
                        return result
                else:
                    params = dict()
                    for param_key, param_value in route_item.get('params', {}).items():
                        if isinstance(param_value, collections.Callable):
                            params[param_key] = param_value(match)
                        else:
                            params[param_key] = param_value
                    return route_item['handler'], params

    def view_notfound(self, err):
        import handlers.web.skeleton as mod_tmpl
        try:
            content = mod_tmpl.TemplateFactory(self.req, 'error_notfound').render({'description': err})
        except mod_tmpl.TemplateError:
            raise HandlerError('Template error')
        self.req.setResponseCode(http.client.NOT_FOUND, http.client.responses[http.client.NOT_FOUND])
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)

    def view_error(self, err_type, err_value, err_tb):
        tb = reduce(
            lambda line_up, line_down: line_up + '\n' + line_down,
            ['%s: %s' % (item[0], item[1]) for item in traceback.extract_tb(err_tb)]
        )
        import handlers.web.skeleton as mod_tmpl
        try:
            content = mod_tmpl.TemplateFactory(self.req, 'error_internal').render({'err_type': err_type, 'err_value': err_value, 'err_tb': tb})
            self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        except mod_tmpl.TemplateError:
            content = '''\
При обработке запроса произошла ошибка\n
Тип ошибки: %s\n
Значение ошибки: %s\n
Информация для разработчика:\n%s\
''' % (err_type, err_value, tb)
            self.req.setHeader('Content-Type', 'text/plain; charset=utf-8')
        self.req.setResponseCode(http.client.INTERNAL_SERVER_ERROR, http.client.responses[http.client.INTERNAL_SERVER_ERROR])
        self.req.write(content)

    def __call__(self):
        try:
            if self.req.method == 'MAIL':
                import handlers.mail
                try:
                    return handlers.mail.Handler(self.req)()
                except handlers.mail.HandlerError as err:
                    raise HandlerError('Error in mail handler', err)

            localpath = os.path.normpath(os.path.join('/', os.path.relpath(self.req.path, config.main.path_prefix)))
            module = self.handle_map(self.ROUTE_MAP, localpath)
            if module is None:
                return self.view_notfound('No handler found')
            module_name, module_params = module

            __import__(module_name)

            module_handler = sys.modules[module_name].Handler(self.req)
            return module_handler(**module_params)
        except:
            err_type, err_value, err_tb = sys.exc_info()
            Logger(self.req).traceback(err_type, err_value, err_tb)
            return self.view_error(err_type, err_value, err_tb)


class HandlerError(util.handler.HandlerError):
    pass
