# -*- coding: utf-8 -*-

import pycountry
import modules.mongo as mod_mongo


class Address(mod_mongo.mongoengine.EmbeddedDocument):
    meta = {'strict': False}

    street = mod_mongo.mongoengine.StringField(max_length=256, required=True)
    city = mod_mongo.mongoengine.StringField(max_length=128, required=True)
    postal_code = mod_mongo.mongoengine.StringField(max_length=16)
    country = mod_mongo.mongoengine.StringField(max_length=2, required=True)

    def __bool__(self):
        return bool(self.street) or bool(self.city) or bool(self.postal_code) or bool(self.country)

    def __str__(self):
        self_country = self.country
        if self_country:
            try:
                self_country = pycountry.countries.get(alpha2=self_country).name
            except KeyError:
                self_country = '<country unknown>'
        else:
            self_country = '<country not set>'
        return '{}\n{}\n{} {}'.format(
            self.street or '', self.city or '',
            self.postal_code or '', self_country
        )


class AddressField(mod_mongo.mongoengine.DynamicField):
    """Defines the address field (subdocument with fallback to the string value)."""

    def to_mongo(self, value, **kwargs):
        if isinstance(value, (mod_mongo.mongoengine.Document, mod_mongo.mongoengine.EmbeddedDocument)):
            return value.to_mongo()
        elif isinstance(value, str):
            return value
        elif value is None:
            return None
        else:
            raise ValueError('Field value is unexpected', value)

    def to_python(self, value):
        if isinstance(value, dict):
            return Address._from_son(value)
        else:
            return super(AddressField, self).to_python(value)
