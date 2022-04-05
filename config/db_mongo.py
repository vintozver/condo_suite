# -*- coding: utf-8 -*-

import config

try:
    try:
        host = config.parser.get('db_mongo', 'host')
    except config.configparser.NoOptionError:
        host = 'localhost'
    try:
        port = config.parser.getint('db_mongo', 'port')
    except config.configparser.NoOptionError:
        port = 27017
    try:
        user = config.parser.get('db_mongo', 'user')
    except config.configparser.NoOptionError:
        user = None
    try:
        password = config.parser.get('db_mongo', 'password')
    except config.configparser.NoOptionError:
        password = None
    try:
        name = config.parser.get('db_mongo', 'name')
    except config.configparser.NoOptionError:
        name = 'parking-enforcement'
except config.configparser.NoSectionError:
    host = 'localhost'
    port = 27017
    user = None
    password = None
    name = 'parking-enforcement'
