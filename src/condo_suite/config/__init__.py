# -*- coding: utf-8 -*-

import os
import os.path
import sys

import yaml


basedir = os.path.join(os.getcwd(), 'run')

try:
    with open(os.path.join(basedir, 'config.yaml'), encoding='utf-8') as config_file:
        settings = yaml.safe_load(config_file) or {}
except FileNotFoundError:
    settings = {}


def _import_sub():
    def inject(module_path):
        try:
            module_name = 'condo_suite.%s' % module_path
            __import__(module_name)
        except ImportError:
            return
        mod = sys.modules[module_name]
        partition_name = module_name.rsplit('.', 1)[-1]
        if partition_name in globals():
            globals()[partition_name].__dict__.update(mod.__dict__)
        else:
            globals()[partition_name] = mod

    partitions = ['config.main', 'config.db_mongo', 'config.google']
    for partition in partitions:
        inject(partition)

_import_sub()


__all__ = ['basedir', 'settings']
