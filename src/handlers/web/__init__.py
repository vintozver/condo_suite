# -*- coding: utf-8 -*-

import collections.abc
from functools import reduce
import importlib
import http.client
import re
import sys
import traceback

from ...util.handler import Handler as _Handler, HandlerError as _HandlerError
from ...util.logger import Logger


class Handler(_Handler):
    ROUTE_MAP = [
        {'regex': re.compile(r'^/$'), 'handler': 'web.index'},
        {'regex': re.compile(r'^/static(/.*)$'), 'handler': 'web.static', 'params': {'path': lambda rex: rex.group(1)}},
        {'regex': re.compile(r'^/\bvehicle\b'), 'map': [
            {'regex': re.compile(r'^/?$'), 'handler': 'web.vehicle_menu'},
            {'regex': re.compile(r'^/view/([0-9A-HJ-NPR-Z]{17})/?$'), 'handler': 'web.vehicle_view', 'params': {'vin': lambda rex: rex.group(1)}},
        ]},
        {'regex': re.compile(r'^/\bparking\b'), 'map': [
            {'regex': re.compile(r'^/?$'), 'handler': 'web.parking_menu'},
            {'regex': re.compile(r'^/vehicle/visitor/?$'), 'handler': 'web.parking_vehicle_visitor'},
            {'regex': re.compile(r'^/event/?$'), 'handler': 'web.parking_event_search'},
            {'regex': re.compile(r'^/event/new/?$'), 'handler': 'web.parking_event_new'},
            {'regex': re.compile(r'^/event/view/([0123456789abcdef]+)/?$'), 'handler': 'web.parking_event_view', 'params': {'oid': lambda rex: rex.group(1)}},
            {'regex': re.compile(r'^/event/view/([0123456789abcdef]+)/file/([0123456789abcdef]+)/?$'), 'handler': 'web.parking_event_file', 'params': {
                'doc_oid': lambda rex: rex.group(1), 'file_oid': lambda rex: rex.group(2)
            }},
            {'regex': re.compile(r'^/event/amend/([0123456789abcdef]+)/?$'), 'handler': 'web.parking_event_amend', 'params': {'oid': lambda rex: rex.group(1)}},
            {'regex': re.compile(r'^/event/helper/autocomplete/VIN/?$'), 'handler': 'web.parking_event_helpers', 'params': {'action': ('autocomplete', 'VIN')}},
            {'regex': re.compile(r'^/event/helper/autocomplete/tag/?$'), 'handler': 'web.parking_event_helpers', 'params': {'action': ('autocomplete', 'tag')}},
        ]},
        {'regex': re.compile(r'^/\bcase\b'), 'map': [
            {'regex': re.compile(r'^/?$'), 'handler': 'web.case_search'},
            {'regex': re.compile(r'^/new/?$'), 'handler': 'web.case_new'},
            {'regex': re.compile(r'^/view/([0123456789abcdefABCDEF]+)/?$'), 'handler': 'web.case_view', 'params': {'oid': lambda rex: rex.group(1)}},
            {'regex': re.compile(r'^/view/([0123456789abcdefABCDEF]+)/file/([0123456789abcdefABCDEF]+)/?$'), 'handler': 'web.case_file', 'params': {
                'doc_oid': lambda rex: rex.group(1), 'file_oid': lambda rex: rex.group(2)
            }},
            {'regex': re.compile(r'^/amend/([0123456789abcdefABCDEF]+)/?$'), 'handler': 'web.case_amend', 'params': {'oid': lambda rex: rex.group(1)}},
        ]},
        {'regex': re.compile(r'^/\bapi\b'), 'map': [
            {'regex': re.compile(r'^/search/parking_event_description_candidate/?$'), 'handler': 'api.parking_event', 'params': {'action': 'candidate'}},
            {'regex': re.compile(r'^/search/vehicle_description_candidate/?$'), 'handler': 'api.vehicle', 'params': {'action': 'candidate'}},
            {'regex': re.compile(r'^/vehicle/([0-9A-HJ-NPR-Z]{17})/description/?$'), 'handler': 'api.vehicle', 'params': {'vin': lambda rex: rex.group(1)}},
            {'regex': re.compile(r'^/vehicle/?$'), 'handler': 'api.vehicle'},
            {'regex': re.compile(r'^/parking/event/?$'), 'handler': 'api.parking_event_search'},
            {'regex': re.compile(r'^/parking/event/([0123456789abcdefABCDEF]+)/description/?$'), 'handler': 'api.parking_event', 'params': {'action': 'description', 'oid': lambda rex: rex.group(1)}},
            {'regex': re.compile(r'^/parking/event/([0123456789abcdefABCDEF]+)/file/([0123456789abcdefABCDEF]+)/?$'), 'handler': 'api.parking_event', 'params': {'action': 'file', 'oid': lambda rex: rex.group(1), 'file_oid': lambda rex: rex.group(2)}},
            {'regex': re.compile(r'^/parking/event/([0123456789abcdefABCDEF]+)/?$'), 'handler': 'api.parking_event', 'params': {'action': 'view', 'oid': lambda rex: rex.group(1)}},
            {'regex': re.compile(r'^/case/?$'), 'handler': 'api.case'},
            {'regex': re.compile(r'^/case/([0123456789abcdefABCDEF]+)/?$'), 'handler': 'api.case', 'params': {'oid': lambda rex: rex.group(1)}},
            {'regex': re.compile(r'^/case/([0123456789abcdefABCDEF]+)/status/?$'), 'handler': 'api.case', 'params': {'action': 'status', 'oid': lambda rex: rex.group(1)}},
            {'regex': re.compile(r'^/case/([0123456789abcdefABCDEF]+)/comment/?$'), 'handler': 'api.case', 'params': {'action': 'comment', 'oid': lambda rex: rex.group(1)}},
            {'regex': re.compile(r'^/case/([0123456789abcdefABCDEF]+)/link/?$'), 'handler': 'api.case', 'params': {'action': 'link', 'oid': lambda rex: rex.group(1)}},
            {'regex': re.compile(r'^/case/([0123456789abcdefABCDEF]+)/link/([0123456789abcdefABCDEF]+)/?$'), 'handler': 'api.case', 'params': {'action': 'link', 'oid': lambda rex: rex.group(1), 'linked_oid': lambda rex: rex.group(2)}},
        ]},
        {'regex': re.compile(r'^/\blink\b'), 'map': [
            {'regex': re.compile(r'^/?$'), 'handler': 'web.link'},
        ]},
        {'regex': re.compile(r'^/\btransaction\b'), 'map': [
            {'regex': re.compile(r'^/?$'), 'handler': 'web.transaction.list'},
            {'regex': re.compile(r'^/view/([0123456789abcdef]+)/?$'), 'handler': 'web.transaction.view', 'params': {'id_transaction': lambda rex: rex.group(1)}},
            {'regex': re.compile(r'^/commit/([0123456789abcdef]+)/?$'), 'handler': 'web.transaction.action', 'params': {'id_txn': lambda rex: rex.group(1), 'action': 'commit'}},
            {'regex': re.compile(r'^/cancel/([0123456789abcdef]+)/?$'), 'handler': 'web.transaction.action', 'params': {'id_txn': lambda rex: rex.group(1), 'action': 'cancel'}},
            {'regex': re.compile(r'^/recover/([0123456789abcdef]+)/?$'), 'handler': 'web.transaction.action', 'params': {'id_txn': lambda rex: rex.group(1), 'action': 'recover'}},
        ]},
        {'regex': re.compile(r'^/\bauth\b'), 'map': [
            {'regex': re.compile(r'^/?$'), 'handler': 'ext.redirect', 'params': {'address': '/auth/user'}},
            {'regex': re.compile(r'^/user/?$'), 'handler': 'web.auth_user'},
            {'regex': re.compile(r'^/agent/?$'), 'handler': 'web.auth_agent'},
            {'regex': re.compile(r'^/info/?$'), 'handler': 'web.auth_info'},  # JSON handler
            {'regex': re.compile(r'^/ext/fido2/?$'), 'handler': 'web.auth_ext.fido2'},
            {'regex': re.compile(r'^/ext/google/?$'), 'handler': 'web.auth_ext.google'},
        ]},
        {'regex': re.compile(r'^/\buser\b'), 'map': [
            {'regex': re.compile(r'^/?$'), 'handler': 'web.user_view'},
            {'regex': re.compile(r'^/new/?$'), 'handler': 'web.user_new'},
            {'regex': re.compile(r'^/view/([0123456789abcdef]+)/?$'), 'handler': 'web.user_view', 'params': {'id_user': lambda rex: rex.group(1)}},
            {'regex': re.compile(r'^/del/([0123456789abcdef]+)/?$'), 'handler': 'web.user_del', 'params': {'id_user': lambda rex: rex.group(1)}},
            {'regex': re.compile(r'^/update/([0123456789abcdef]+)/?$'), 'handler': 'web.user_update', 'params': {'id_user': lambda rex: rex.group(1)}},  # JSON handler
            {'regex': re.compile(r'^/helper/autocomplete/search/?$'), 'handler': 'web.user_helpers', 'params': {'action': ('autocomplete', 'search')}},  # JSON handler
            {'regex': re.compile(r'^/helper/autocomplete/search/agent/?$'), 'handler': 'web.user_helpers', 'params': {'action': ('autocomplete', 'search', 'agent')}},  # JSON handler
        ]},
        {'regex': re.compile(r'^/\bagent\b'), 'map': [
            {'regex': re.compile(r'^/?$'), 'handler': 'ext.redirect', 'params': {'address': '/agent/edit'}},
            {'regex': re.compile(r'^/edit/?$'), 'handler': 'web.agent_edit'},
            {'regex': re.compile(r'^/switch/([0123456789abcdef]+)/?$'), 'handler': 'web.agent_switch', 'params': {'id_agent': lambda rex: rex.group(1)}},
            {'regex': re.compile(r'^/switch/([0123456789abcdef]+)/([\w ]+)/?$'), 'handler': 'web.agent_switch', 'params': {'id_agent': lambda rex: rex.group(1), 'position': lambda rex: rex.group(2)}},
            {'regex': re.compile(r'^/discard/?$'), 'handler': 'web.agent_switch', 'params': {'id_agent': None}},
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
                        if isinstance(param_value, collections.abc.Callable):
                            params[param_key] = param_value(match)
                        else:
                            params[param_key] = param_value
                    return route_item['handler'], params

    def view_notfound(self, err):
        from . import skeleton as mod_tmpl
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
        from . import skeleton as mod_tmpl
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
                from .. import mail as _mail
                try:
                    return _mail.Handler(self.req)()
                except _mail.HandlerError as err:
                    raise HandlerError('Error in mail handler', err)

            module = self.handle_map(self.ROUTE_MAP, self.req.path)
            if module is None:
                return self.view_notfound('No handler found')
            module_name, module_params = module

            module = importlib.import_module('..' + module_name, package=__package__)
            module_handler = module.Handler(self.req)
            return module_handler(**module_params)
        except:
            err_type, err_value, err_tb = sys.exc_info()
            Logger(self.req).traceback(err_type, err_value, err_tb)
            return self.view_error(err_type, err_value, err_tb)


class HandlerError(_HandlerError):
    pass
