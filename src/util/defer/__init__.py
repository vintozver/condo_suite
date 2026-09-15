# -*- coding: utf-8 -*-

import ssl
import urllib.parse

import celery
import celery.loaders.app

from ... import config
from . import json_ex as _json_ex  # noqa: F401  (registers the 'json-ex' task serializer)


class Loader(celery.loaders.app.AppLoader):
    def read_configuration(self, fail_silently=True):
        self.configured = True
        return {
            'imports': (
                'condo_suite.util.defer',
                'condo_suite.handlers.defer',
                'condo_suite.handlers.defer.case',
                'condo_suite.handlers.defer.mail',
            ),
            'task_serializer': 'json-ex',
            'accept_content': ['json', 'yaml', 'json-ex'],
            'enable_utc': True,
            'worker_disable_rate_limits': True,  # required for gevent backend: https://github.com/celery/celery/issues/425
            'broker_url': 'amqps://%(host)s/%(vhost)s' % {
                'host': config.rabbit['host'],
                'vhost': urllib.parse.quote(config.rabbit.get('vhost', '/'), safe=''),
            },
            'broker_use_ssl': {
                'cert_reqs': ssl.CERT_REQUIRED,
                'ca_certs': config.rabbit['ssl_ca'],
                'certfile': config.rabbit['ssl_cert'],
                'keyfile': config.rabbit['ssl_key'],
            },
        }


class App(celery.Celery):
    loader_cls = '%s.%s' % (Loader.__module__, Loader.__qualname__)


the_app = App('condo_suite')
Task = the_app.Task

__all__ = ['the_app', 'Task']
