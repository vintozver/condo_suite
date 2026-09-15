# -*- coding: utf-8 -*-

import ssl
import urllib.parse

import celery
import celery.loaders.app

from ... import config
from . import json_ex as _json_ex  # noqa: F401  (registers the 'json-ex' task serializer)

_root_package = __name__.split('.', 1)[0]


class Loader(celery.loaders.app.AppLoader):
    def read_configuration(self, fail_silently=True):
        self.configured = True
        return {
            'imports': tuple(
                '%s.%s' % (_root_package, module) for module in (
                    'util.defer',
                    'handlers.defer',
                    'handlers.defer.case',
                    'handlers.defer.mail',
                )
            ),
            'task_serializer': 'json-ex',
            'accept_content': ['json', 'yaml', 'json-ex'],
            'enable_utc': True,
            'worker_disable_rate_limits': True,  # required for gevent backend: https://github.com/celery/celery/issues/425
            'broker_url': 'amqps://%(host)s/%(vhost)s' % {
                'host': config.rabbit['host'],
                'vhost': urllib.parse.quote(config.rabbit.get('vhost', '/'), safe=''),
            },
            'broker_login_method': 'EXTERNAL',
            'broker_use_ssl': {
                'cert_reqs': ssl.CERT_REQUIRED,
                'ca_certs': config.rabbit['ssl_ca'],
                'certfile': config.rabbit['ssl_cert'],
                'keyfile': config.rabbit['ssl_key'],
            },
        }


class App(celery.Celery):
    loader_cls = '%s.%s' % (Loader.__module__, Loader.__qualname__)


the_app = App()
Task = the_app.Task

__all__ = ['the_app', 'Task']
