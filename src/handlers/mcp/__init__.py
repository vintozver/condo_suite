"""Stateless, JSON-only MCP Streamable HTTP transport."""

import base64
import email.utils
import http.client
import importlib
import json
import math
import re
from urllib.parse import urlsplit

from wsgiref.headers import Headers

from ..api.common import ApiError, BaseHandler, config
from ...util.handler import Handler as RequestHandler


VERSIONS = ('2025-03-26', '2025-06-18')
OID = {'type': 'string', 'pattern': '^[0-9a-fA-F]{24}$'}
VIN = {'type': 'string', 'pattern': '^[0-9A-HJ-NPR-Z]{17}$'}
TEXT = {'type': 'string', 'minLength': 1}
PRECONDITION = {'type': 'string', 'minLength': 1,
                'description': 'HTTP date from the candidate result lastModified.'}


def tool(name, description, module, method='GET', route=None, properties=None,
         required=(), body='json'):
    return {
        'name': name, 'description': description,
        'inputSchema': {'type': 'object', 'properties': properties or {},
                        'required': list(required), 'additionalProperties': False},
        'module': module, 'method': method, 'route': route or {}, 'body': body,
    }


TOOLS = [
    tool('parking_search', 'Search parking events (maximum 500).',
         'parking_event_search', properties={
             'VIN': VIN, 'tag': TEXT, 'reason': TEXT,
             'limit': {'type': 'integer', 'minimum': 1, 'maximum': 500}}),
    tool('parking_view', 'View a parking event and history.', 'parking_event',
         route={'action': 'view', 'oid': '$oid'}, properties={'oid': OID},
         required=('oid',)),
    tool('parking_comment', 'Append a comment to parking event history.',
         'parking_event_comment', 'POST', {'oid': '$oid'},
         {'oid': OID, 'description': TEXT}, ('oid', 'description')),
    tool('parking_file', 'Download an event attachment as base64.', 'parking_event',
         route={'action': 'file', 'oid': '$oid', 'file_oid': '$file_oid'},
         properties={'oid': OID, 'file_oid': OID}, required=('oid', 'file_oid'),
         body='file'),
    tool('parking_description_candidate', 'Select a parking description update candidate.',
         'parking_event', route={'action': 'candidate'}),
    tool('parking_description_update', 'Update a candidate description with concurrency protection.',
         'parking_event', 'POST', {'action': 'description', 'oid': '$oid'},
         {'oid': OID, 'description': {'type': 'string'},
          'if_unmodified_since': PRECONDITION},
         ('oid', 'description', 'if_unmodified_since'), 'text'),
    tool('vehicle_search', 'Search vehicles by VIN or tag (maximum 500).', 'vehicle',
         properties={'VIN': VIN, 'tag': TEXT}),
    tool('vehicle_description_candidate', 'Select a vehicle description update candidate.',
         'vehicle', route={'action': 'candidate'}),
    tool('vehicle_description_update', 'Update a candidate vehicle description with concurrency protection.',
         'vehicle', 'POST', {'vin': '$VIN'},
         {'VIN': VIN, 'description': {'type': 'string'},
          'if_unmodified_since': PRECONDITION},
         ('VIN', 'description', 'if_unmodified_since'), 'text'),
    tool('case_view', 'View a case and history.', 'case', route={'oid': '$oid'},
         properties={'oid': OID}, required=('oid',)),
    tool('case_create', 'Create an open case.', 'case', 'POST',
         properties={'title': TEXT}, required=('title',)),
    tool('case_status', 'Update case status.', 'case', 'PATCH',
         {'oid': '$oid', 'action': 'status'},
         {'oid': OID, 'status': {'type': 'string',
                               'enum': ['open', 'progress', 'resolved', 'closed']}},
         ('oid', 'status')),
    tool('case_comment', 'Append a case comment with an optional attachment id.',
         'case', 'POST', {'oid': '$oid', 'action': 'comment'},
         {'oid': OID, 'comment': TEXT, 'file_id': OID}, ('oid', 'comment')),
    tool('case_link', 'Queue linking two different cases (requires a Celery worker).',
         'case', 'POST', {'oid': '$oid', 'linked_oid': '$linked_oid', 'action': 'link'},
         {'oid': OID, 'linked_oid': OID, 'comment': TEXT},
         ('oid', 'linked_oid', 'comment')),
]


class InvalidParams(Exception):
    pass


def normalized_origin(value):
    if (not isinstance(value, str) or not value or
            any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value) or
            any(char in value for char in ('*', '\\', '%', '?', '#'))):
        raise ValueError('Invalid origin')
    origin = urlsplit(value)
    if (origin.scheme not in ('http', 'https') or not origin.hostname or
            origin.username is not None or origin.password is not None or
            origin.path or origin.query or origin.fragment or
            origin.netloc.endswith(':')):
        raise ValueError('Invalid origin')
    port = origin.port
    return (origin.scheme, origin.hostname.lower(),
            port if port is not None else (443 if origin.scheme == 'https' else 80))


def same_origin(req):
    origins = req.request_headers.get_all('Origin') or []
    if not origins:
        return True
    if len(origins) != 1:
        return False
    try:
        allowed = config.mcp_allowed_origins
        if not isinstance(allowed, list):
            return False
        allowed = {normalized_origin(value) for value in allowed}
        origin = normalized_origin(origins[0])
        target = normalized_origin(
            req.scheme + '://' + req.request_headers.get('Host', ''))
        return origin in allowed and origin == target
    except (ValueError, TypeError):
        return False


def reject_constant(value):
    raise ValueError('Invalid JSON constant')


def finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Invalid JSON number')
    return result


def validate(arguments, schema):
    if not isinstance(arguments, dict):
        raise InvalidParams()
    if set(arguments) - set(schema['properties']) or set(schema['required']) - set(arguments):
        raise InvalidParams()
    for key, value in arguments.items():
        rule = schema['properties'][key]
        if rule['type'] == 'string':
            if not isinstance(value, str):
                raise InvalidParams()
            if len(value) < rule.get('minLength', 0):
                raise InvalidParams()
            if 'pattern' in rule and re.fullmatch(rule['pattern'], value) is None:
                raise InvalidParams()
        elif type(value) is not int or not rule['minimum'] <= value <= rule['maximum']:
            raise InvalidParams()
        if 'enum' in rule and value not in rule['enum']:
            raise InvalidParams()
    if 'if_unmodified_since' in arguments:
        try:
            parsed = email.utils.parsedate_to_datetime(arguments['if_unmodified_since'])
            if parsed is None:
                raise ValueError()
        except (TypeError, ValueError, OverflowError):
            raise InvalidParams()
    if 'linked_oid' in arguments and arguments['oid'].lower() == arguments['linked_oid'].lower():
        raise InvalidParams()


class ApiRequest:
    """A fresh request/response buffer; never shares the MCP body or headers."""

    def __init__(self, method, body, headers):
        self.method = method
        self.query_string = ''
        self.request_body = body
        self.request_headers = Headers(headers)
        self.requestHeaders = self.request_headers
        self.status = 200
        self.headers = Headers([])
        self.parts = []

    def setResponseCode(self, status, reason=None):
        self.status = status

    def setHeader(self, name, value):
        self.headers[name] = value

    def write(self, value):
        self.parts.append(value.encode('utf-8') if isinstance(value, str) else value)


class Handler(BaseHandler):
    __init__ = RequestHandler.__init__

    def _reply(self, status, value=None):
        self.req.setResponseCode(status, http.client.responses[status])
        self.req.setHeader('Cache-Control', 'no-store')
        if value is not None:
            self.req.setHeader('Content-Type', 'application/json')
            self.req.write(json.dumps(value, ensure_ascii=True, allow_nan=False))

    def _rpc_error(self, request_id, code, message):
        self._reply(200, {'jsonrpc': '2.0', 'id': request_id,
                          'error': {'code': code, 'message': message}})

    def _call_tool(self, params, authentication):
        if (set(params) - {'name', 'arguments'} or
                not isinstance(params.get('name'), str)):
            raise InvalidParams()
        definition = next((item for item in TOOLS if item['name'] == params['name']), None)
        if definition is None:
            raise InvalidParams()
        arguments = params.get('arguments', {})
        validate(arguments, definition['inputSchema'])
        route = {key: arguments[value[1:]] if value.startswith('$') else value
                 for key, value in definition['route'].items()}
        route_keys = {value[1:] for value in definition['route'].values()
                      if value.startswith('$')}
        payload = {key: value for key, value in arguments.items()
                   if key not in route_keys and key != 'if_unmodified_since'}
        headers = [('Content-Type', 'application/json')]
        if definition['body'] == 'text':
            body = arguments['description'].encode('utf-8')
            headers = [('Content-Type', 'text/plain'),
                       ('If-Unmodified-Since', arguments['if_unmodified_since'])]
        else:
            body = json.dumps(payload).encode('utf-8')
        request = ApiRequest(definition['method'], body, headers)
        module = importlib.import_module('..api.' + definition['module'], __package__)
        # This override is local to the delegated instance, not a token or global patch.
        # API handlers must remain CGI-independent: parsing here would consume text/binary bodies.
        delegated = module.Handler.__new__(module.Handler)
        RequestHandler.__init__(delegated, request)
        delegated._authenticate = lambda: (authentication[0], authentication[1], payload)
        delegated(**route)
        raw = b''.join(request.parts)
        if request.status >= 400:
            result = {'status': request.status, 'error': 'Operation failed'}
            try:
                result['error'] = json.loads(raw)['error']
            except (ValueError, KeyError, TypeError):
                pass
            return {'content': [{'type': 'text', 'text': json.dumps(result)}], 'isError': True}
        if definition['body'] == 'file':
            result = {'mimeType': request.headers.get('Content-Type', 'application/octet-stream'),
                      'base64': base64.b64encode(raw).decode('ascii')}
        else:
            result = json.loads(raw)
        result = {'status': request.status, 'data': result}
        if request.headers.get('Last-Modified'):
            result['lastModified'] = request.headers['Last-Modified']
        return {'content': [{'type': 'text', 'text': json.dumps(result)}], 'isError': False}

    def __call__(self):
        try:
            authentication = self._authenticate()
        except ApiError as error:
            if error.status == 401:
                self.req.setHeader('WWW-Authenticate', 'Bearer')
            return self._reply(error.status, {'error': error.message})
        except Exception:
            return self._reply(500, {'error': 'Internal server error'})
        if not same_origin(self.req):
            return self._reply(403, {'error': 'Origin not allowed'})
        if self.req.method != 'POST':
            self.req.setHeader('Allow', 'POST')
            return self._reply(405, {'error': 'POST required'})
        headers = self.req.request_headers
        if headers.get('Content-Type', '').split(';', 1)[0].strip().lower() != 'application/json':
            return self._reply(415, {'error': 'Content-Type must be application/json'})
        accepts = {item.split(';', 1)[0].strip().lower()
                   for item in headers.get('Accept', '').split(',')}
        if not {'application/json', 'text/event-stream'} <= accepts:
            return self._reply(406, {'error': 'Accept must include application/json and text/event-stream'})
        version = headers.get('MCP-Protocol-Version')
        if version is not None and version not in VERSIONS:
            return self._reply(400, {'error': 'Unsupported MCP protocol version'})
        try:
            message = json.loads(self.req.request_body, parse_constant=reject_constant,
                                 parse_float=finite_float)
        except (ValueError, UnicodeDecodeError, TypeError, RecursionError):
            return self._rpc_error(None, -32700, 'Parse error')
        if (not isinstance(message, dict) or message.get('jsonrpc') != '2.0' or
                not isinstance(message.get('method'), str) or
                set(message) - {'jsonrpc', 'id', 'method', 'params'} or
                ('id' in message and type(message['id']) not in (str, int))):
            return self._rpc_error(None, -32600, 'Invalid Request')
        # Notifications have no response and never invoke mutating request methods.
        if 'id' not in message:
            return self._reply(202)
        request_id = message['id']
        method = message['method']
        params = message.get('params', {})
        try:
            if not isinstance(params, dict):
                raise InvalidParams()
            params = params.copy()
            if '_meta' in params:
                metadata = params.pop('_meta')
                if not isinstance(metadata, dict):
                    raise InvalidParams()
                if ('progressToken' in metadata and
                        type(metadata['progressToken']) not in (str, int, float)):
                    raise InvalidParams()
            if method == 'initialize':
                if (set(params) - {'protocolVersion', 'capabilities', 'clientInfo'} or
                        not isinstance(params.get('protocolVersion'), str) or
                        not isinstance(params.get('capabilities'), dict) or
                        not isinstance(params.get('clientInfo'), dict) or
                        not all(isinstance(params['clientInfo'].get(key), str)
                                for key in ('name', 'version'))):
                    raise InvalidParams()
                requested = params['protocolVersion']
                result = {'protocolVersion': requested if requested in VERSIONS else VERSIONS[-1],
                          'capabilities': {'tools': {'listChanged': False}},
                          'serverInfo': {'name': 'condo-suite', 'version': '0.1.0'}}
            elif method == 'ping':
                if params:
                    raise InvalidParams()
                result = {}
            elif method == 'tools/list':
                if set(params) - {'cursor'} or ('cursor' in params and params['cursor'] is not None):
                    raise InvalidParams()
                result = {'tools': [{key: item[key] for key in ('name', 'description', 'inputSchema')}
                                    for item in TOOLS]}
            elif method == 'tools/call':
                result = self._call_tool(params, authentication)
            else:
                return self._rpc_error(request_id, -32601, 'Method not found')
        except (InvalidParams, UnicodeEncodeError):
            return self._rpc_error(request_id, -32602, 'Invalid params')
        except Exception:
            return self._rpc_error(request_id, -32603, 'Internal error')
        return self._reply(200, {'jsonrpc': '2.0', 'id': request_id, 'result': result})
