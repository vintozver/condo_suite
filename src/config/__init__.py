# -*- coding: utf-8 -*-

import yaml
import urllib.parse

try:
    with open('config.yaml', encoding='utf-8') as config_file:
        settings = yaml.safe_load(config_file) or {}
except FileNotFoundError:
    settings = {}

mongodb_uri = settings.get('mongodb_uri', 'mongodb://localhost/parking-enforcement')
name = urllib.parse.urlparse(mongodb_uri).path.lstrip('/') or 'parking-enforcement'
google = settings.get('google', {})
google_client_id = google.get('client_id')
google_client_secret = google.get('client_secret')
google_redirect_uri = google.get('redirect_uri')
google_javascript_origin = google.get('javascript_origin')

__all__ = ['settings', 'mongodb_uri', 'name', 'google']
