# -*- coding: utf-8 -*-

import condo_suite.config as config

google_settings = config.settings.get('google', {})
client_id = google_settings.get('client_id')
client_secret = google_settings.get('client_secret')
redirect_uri = google_settings.get('redirect_uri')
javascript_origin = google_settings.get('javascript_origin')
