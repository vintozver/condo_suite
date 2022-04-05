# -*- coding: utf-8 -*-

import config

try:
    try:
        client_id = config.parser.get('google', 'client_id')
    except config.configparser.NoOptionError:
        client_id = None
    try:
        client_secret = config.parser.get('google', 'client_secret')
    except config.configparser.NoOptionError:
        client_secret = None
    try:
        redirect_uri = config.parser.get('google', 'redirect_uri')
    except config.configparser.NoOptionError:
        redirect_uri = None
    try:
        javascript_origin = config.parser.get('google', 'javascript_origin')
    except config.configparser.NoOptionError:
        javascript_origin = None
except config.configparser.NoSectionError:
    client_id = None
    client_secret = None
    redirect_uri = None
    javascript_origin = None
