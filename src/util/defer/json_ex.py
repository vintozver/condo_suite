# -*- coding: utf-8 -*-

import collections.abc
import json

import bson.json_util
import kombu.serialization


def json_encode_default(o):
    return bson.json_util.default(o)


def json_decode_object_hook(value):
    if isinstance(value, collections.abc.Mapping):
        try:
            return bson.json_util.object_hook(value)
        except TypeError:
            return value
    elif isinstance(value, str):
        return value
    elif isinstance(value, collections.abc.Sequence):
        return [json_decode_object_hook(value_item) for value_item in value]
    else:
        return value


def json_decode_object_pairs_hook(obj):
    dobj = collections.OrderedDict()
    for (key, value) in obj:
        dobj[key] = json_decode_object_hook(value)
    return dobj


def json_ex_dumps(obj):
    return json.dumps(obj, default=json_encode_default)


def json_ex_loads(representation):
    return json.loads(representation, object_pairs_hook=json_decode_object_pairs_hook)


kombu.serialization.register(
    'json-ex', json_ex_dumps, json_ex_loads, content_type='application/json-ex', content_encoding='utf-8',
)

__all__ = ['json_ex_dumps', 'json_ex_loads']
