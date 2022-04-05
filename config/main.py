# -*- coding: utf-8 -*-

import config

basedir = config.basedir

try:
    path_prefix = config.parser.get('main', 'path_prefix')
except config.configparser.NoOptionError:
    path_prefix = '/'
except config.configparser.NoSectionError:
    path_prefix = '/'

product_name = 'Parking Enforcement'
product_description = 'Aspen Grove Condominiums parking enforcement. Kent, WA, USA. All rights reserved.'

timezone = 'Europe/Minsk'

log_dir = 'logs'

