# -*- coding: utf-8 -*-

import urllib.parse

import condo_suite.config as config

mongodb_uri = config.settings.get('mongodb_uri', 'mongodb://localhost/parking-enforcement')
name = urllib.parse.urlparse(mongodb_uri).path.lstrip('/') or 'parking-enforcement'
