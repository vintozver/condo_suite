# -*- coding: utf-8 -*-

import pytz
import condo_suite.config as config

product_name = 'Parking Enforcement'
product_description = 'Aspen Grove Condominiums parking enforcement. Kent, WA, USA. All rights reserved.'
timezone = pytz.timezone('US/Pacific')

__all__ = ['product_name', 'product_description', 'timezone']
