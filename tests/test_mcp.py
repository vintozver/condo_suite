import base64
import datetime
import io
import json
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from condo_suite.modules import mongo

with patch.object(mongo, 'DbSessionController') as controller:
    database = controller.return_value.__enter__.return_value.__getitem__.return_value
    database.__getitem__.return_value.find.return_value.sort.return_value = []
    from condo_suite.handlers import mcp
    from condo_suite.handlers.api import common, vehicle, parking_event, parking_event_comment
    # These tests execute case handlers, not worker registration or broker setup.
    with patch('celery.Celery.register_task'):
        from condo_suite.handlers.api import case
    from condo_suite.handlers.web import Handler as Router
    from condo_suite.util.web.request import Request, RequestProcessor


VIN = '1HGCM82633A004352'
OID = '0123456789abcdef01234567'
AGENT_ID = 'abcdef0123456789abcdef01'


class MCPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public = cls.key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)

    def setUp(self):
        self.agent = SimpleNamespace(id=mongo.bson.ObjectId(AGENT_ID),
                                     name='Agent', position='Manager')
        self.user = Mock(id=mongo.bson.ObjectId(OID), name='User')
        self.user.keyset = [SimpleNamespace(id='key-1', pub=self.public, crt=None)]
        self.user.agents = [self.agent]
        self.user.rbac_has_permission.return_value = True
        self.users = patch.object(common, 'UserDocument').start()
        self.users.objects.return_value.first.return_value = self.user
        self.addCleanup(patch.stopall)

    def token(self, overrides=None, payload=None, key=None, algorithm='RS256'):
        headers = dict(user_id=OID, kid='key-1', dt=time.time(), agent_id=AGENT_ID,
                       agent_position='Manager')
        headers.update(overrides or {})
        with patch('jwt.api_jws.PyJWS._validate_headers'):
            return jwt.encode(payload or {}, key or self.key, algorithm=algorithm, headers=headers)

    def request(self, message=None, method='POST', headers=None, token=None, raw=None):
        default = {'Host': 'condo.example', 'Authorization': 'Bearer ' + (token or self.token()),
                   'Content-Type': 'application/json',
                   'Accept': 'application/json, text/event-stream'}
        default.update(headers or {})
        body = raw if raw is not None else json.dumps(
            message or {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}).encode()
        env = {'REQUEST_METHOD': method, 'PATH_INFO': '/mcp/',
               'wsgi.url_scheme': 'https', 'wsgi.input': io.BytesIO(body)}
        for key, value in default.items():
            if value is not None:
                env['CONTENT_TYPE' if key == 'Content-Type' else
                    'HTTP_' + key.upper().replace('-', '_')] = value.encode()
        if 'CONTENT_TYPE' in env:
            env['CONTENT_TYPE'] = env['CONTENT_TYPE'].decode()
        return Request(env)

    def invoke(self, message=None, **kwargs):
        req = self.request(message, **kwargs)
        mcp.Handler(req)()
        raw = b''.join(req.response_body)
        return req, json.loads(raw) if raw else None

    def rpc(self, method, params=None):
        return {'jsonrpc': '2.0', 'id': 'request-1', 'method': method,
                'params': params or {}}

    def call(self, name, arguments=None, **kwargs):
        return self.invoke(self.rpc('tools/call', {'name': name,
                                                 'arguments': arguments or {}}), **kwargs)

    def test_route_and_wsgi(self):
        for path in ('/mcp/', '/mcp'):
            self.assertEqual(Router.handle_map(Router.ROUTE_MAP, path), ('mcp', {}))
        req = self.request()
        responder = Mock()
        body = b''.join(RequestProcessor(Router, req=req).process({}, responder))
        self.assertEqual(json.loads(body)['result'], {})
        self.assertEqual(responder.call_args.args[0], '200 OK')

    def test_initialize_versions_and_fallback(self):
        for version, expected in [('2025-03-26', '2025-03-26'),
                                  ('2025-06-18', '2025-06-18'), ('future', '2025-06-18')]:
            req, value = self.invoke(self.rpc('initialize', {
                'protocolVersion': version, 'capabilities': {},
                'clientInfo': {'name': 'test', 'version': '1'}}))
            self.assertEqual(req.status_code, 200)
            self.assertEqual(value['result']['protocolVersion'], expected)
            self.assertNotIn('Mcp-Session-Id', req.response_headers)
        req, _ = self.invoke(headers={'MCP-Protocol-Version': 'unknown'})
        self.assertEqual(req.status_code, 400)

    def test_notifications_are_empty_and_do_not_execute(self):
        for method in ('notifications/initialized', 'unknown', 'tools/call'):
            with patch.object(mcp.Handler, '_call_tool') as delegated:
                req, value = self.invoke({'jsonrpc': '2.0', 'method': method,
                                          'params': {'name': 'case_create'}})
            self.assertEqual(req.status_code, 202)
            self.assertIsNone(value)
            delegated.assert_not_called()

    def test_envelope_and_protocol_errors(self):
        for raw, code in [(b'{', -32700), (b'null', -32600), (b'[]', -32600),
                          (b'\xff', -32700),
                          (b'{"jsonrpc":"2.0","id":true,"method":"ping"}', -32600),
                          (b'{"jsonrpc":"2.0","id":1e999,"method":"ping"}', -32700),
                          (b'{"jsonrpc":"2.0","id":1,"method":"ping","params":{"x":NaN}}', -32700)]:
            _, value = self.invoke(raw=raw)
            self.assertEqual(value['error']['code'], code)
        _, value = self.invoke(self.rpc('unknown'))
        self.assertEqual(value['error']['code'], -32601)
        _, value = self.invoke(self.rpc('ping', {'x': 1}))
        self.assertEqual(value['error']['code'], -32602)
        _, value = self.invoke({'jsonrpc': '2.0', 'id': 1, 'method': 'ping', 'params': []})
        self.assertEqual(value['error']['code'], -32602)

    def test_standard_request_metadata(self):
        for method in ('ping', 'tools/list'):
            _, value = self.invoke(self.rpc(method, {'_meta': {'progressToken': 'progress-1'}}))
            self.assertIn('result', value)
        with patch.object(vehicle, 'VehicleDocument') as documents:
            documents.objects.return_value.order_by.return_value.__getitem__.return_value = []
            _, value = self.invoke(self.rpc('tools/call', {
                'name': 'vehicle_search', 'arguments': {},
                '_meta': {'progressToken': 1, 'client.example/trace': 'test'}}))
        self.assertIn('result', value)
        for metadata in (None, [], {'progressToken': True}):
            _, value = self.invoke(self.rpc('ping', {'_meta': metadata}))
            self.assertEqual(value['error']['code'], -32602)

    def test_http_negotiation_and_auth_on_all_methods(self):
        for method in ('GET', 'DELETE', 'OPTIONS', 'HEAD'):
            req, _ = self.invoke(method=method)
            self.assertEqual(req.status_code, 405)
            self.assertEqual(req.response_headers['Allow'], 'POST')
            req, _ = self.invoke(method=method, headers={'Authorization': None})
            self.assertEqual(req.status_code, 401)
            self.assertEqual(req.response_headers['WWW-Authenticate'], 'Bearer')
        for headers, expected in [({'Content-Type': 'text/plain'}, 415),
                                  ({'Accept': 'application/json'}, 406),
                                  ({'Accept': None}, 406)]:
            req, _ = self.invoke(headers=headers)
            self.assertEqual(req.status_code, expected)
        req, _ = self.invoke(raw=b'{', headers={'Authorization': None})
        self.assertEqual(req.status_code, 401)

    def test_origin(self):
        for origin, status in [(None, 200), ('https://condo.example', 200),
                               ('https://CONDO.example:443', 200),
                               ('http://condo.example', 403), ('https://evil.example', 403),
                               ('null', 403), ('https://condo.example/path', 403),
                               ('https://user@condo.example', 403),
                               ('https://condo.example:invalid', 403)]:
            req, _ = self.invoke(headers={'Origin': origin})
            self.assertEqual(req.status_code, status, origin)
        req, _ = self.invoke(headers={'Origin': 'https://condo.example',
                                     'Host': 'condo.example:8443'})
        self.assertEqual(req.status_code, 403)
        req = self.request(headers={'Origin': 'http://condo.example'})
        req.scheme = 'http'
        mcp.Handler(req)()
        self.assertEqual(req.status_code, 200)
        req = self.request(headers={'Origin': 'https://condo.example'})
        req.request_headers.add_header('Origin', 'https://condo.example')
        mcp.Handler(req)()
        self.assertEqual(req.status_code, 403)

    def test_real_auth_invalid_expired_and_header_types(self):
        for overrides in [{'dt': time.time() - 301}, {'dt': time.time() + 301},
                          {'dt': float('nan')}, {'dt': float('inf')}, {'dt': True},
                          {'dt': []}, {'dt': 'nan'}, {'dt': 'not-date'},
                          {'dt': 10 ** 1000}, {'user_id': 'invalid'}, {'agent_id': 'invalid'},
                          {'kid': []}, {'agent_position': {}}, {'user_id': 1}]:
            req, _ = self.invoke(token=self.token(overrides))
            self.assertEqual(req.status_code, 401, overrides)
        req, _ = self.invoke(token=self.token(key=self.other_key))
        self.assertEqual(req.status_code, 401)
        req, _ = self.invoke(token=jwt.encode({}, '', algorithm='none', headers={
            'user_id': OID, 'kid': 'key-1', 'dt': time.time(),
            'agent_id': AGENT_ID, 'agent_position': 'Manager'}))
        self.assertEqual(req.status_code, 401)
        req, _ = self.invoke(token='not-a-token')
        self.assertEqual(req.status_code, 401)
        req, _ = self.invoke(token=jwt.encode({}, b'test-only-hmac-key', algorithm='HS256', headers={
            'user_id': OID, 'kid': 'key-1', 'dt': time.time(),
            'agent_id': AGENT_ID, 'agent_position': 'Manager'}))
        self.assertEqual(req.status_code, 401)
        req, _ = self.invoke(token=self.token({'agent_position': 'Other'}))
        self.assertEqual(req.status_code, 403)
        req, _ = self.invoke(headers={'Authorization': 'bEaReR ' + self.token()})
        self.assertEqual(req.status_code, 200)

    def test_certificate_auth(self):
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'test')])
        now = datetime.datetime.now(datetime.timezone.utc)
        certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                       .public_key(self.key.public_key()).serial_number(1)
                       .not_valid_before(now - datetime.timedelta(days=1))
                       .not_valid_after(now + datetime.timedelta(days=1))
                       .sign(self.key, hashes.SHA256()))
        self.user.keyset = [SimpleNamespace(
            id='key-1', pub=None, crt=certificate.public_bytes(serialization.Encoding.DER))]
        req, _ = self.invoke()
        self.assertEqual(req.status_code, 200)
        self.user.keyset[0].pub = self.public
        req, _ = self.invoke()
        self.assertEqual(req.status_code, 401)

    def test_tools_and_schema_validation(self):
        _, value = self.invoke(self.rpc('tools/list'))
        names = {item['name'] for item in value['result']['tools']}
        self.assertIn('parking_file', names)
        self.assertIn('case_link', names)
        self.assertTrue(all(item['inputSchema']['additionalProperties'] is False
                            for item in value['result']['tools']))
        for name, arguments in [
                ('missing', {}), ('parking_view', {}), ('parking_view', {'oid': 'invalid'}),
                ('vehicle_search', {'VIN': 'I' * 17}), ('vehicle_search', {'tag': 3}),
                ('vehicle_search', {'unexpected': True}), ('parking_search', {'limit': True}),
                ('parking_search', {'limit': 501}), ('case_status', {'oid': OID, 'status': 'bad'}),
                ('vehicle_description_update', {'VIN': VIN, 'description': 'text',
                                                'if_unmodified_since': 'bad'}),
                ('case_link', {'oid': OID, 'linked_oid': OID.upper(), 'comment': 'link'})]:
            _, value = self.call(name, arguments)
            self.assertEqual(value['error']['code'], -32602, (name, arguments))

    def test_search_claims_and_body_isolation(self):
        claims = {'VIN': '2' * 17, 'tag': 'claim-tag', 'description': 'claim text'}
        with patch.object(vehicle, 'VehicleDocument') as documents:
            query = documents.objects.return_value
            query.filter.return_value = query
            query.order_by.return_value.__getitem__.return_value = []
            req, value = self.call('vehicle_search', {'VIN': VIN}, token=self.token(payload=claims))
        self.assertEqual(req.status_code, 200)
        query.filter.assert_called_once_with(id=VIN)
        self.assertFalse(value['result']['isError'])
        with patch.object(case, 'Case') as documents:
            _, value = self.call('case_create', {'title': 'argument title'},
                                 token=self.token(payload={'title': 'claim title'}))
        self.assertEqual(documents.call_args.kwargs['title'], 'argument title')
        self.assertEqual(documents.call_args.kwargs['creator'].user.id, self.user.id)
        self.assertFalse(value['result']['isError'])

    def test_rbac_and_safe_internal_failure(self):
        self.user.rbac_has_permission.return_value = False
        with patch.object(vehicle, 'VehicleDocument') as documents:
            _, value = self.call('vehicle_search')
        documents.objects.assert_not_called()
        self.user.rbac_has_permission.assert_called_with('vehicle/view')
        self.assertTrue(value['result']['isError'])
        self.assertEqual(json.loads(value['result']['content'][0]['text'])['status'], 403)
        self.user.rbac_has_permission.return_value = True
        with patch.object(vehicle, 'VehicleDocument') as documents:
            documents.objects.side_effect = RuntimeError('secret database credentials')
            _, value = self.call('vehicle_search')
        self.assertEqual(value['error']['code'], -32603)
        self.assertNotIn('secret', json.dumps(value))

    def test_description_adapter_and_file(self):
        date = 'Wed, 01 Jul 2026 12:30:00 GMT'
        def describe(handler, vin=None, action=None):
            self.assertEqual(vin, VIN)
            self.assertEqual(handler.req.method, 'POST')
            self.assertEqual(handler.req.request_body, b'argument description')
            self.assertEqual(handler.req.request_headers['If-Unmodified-Since'], date)
            self.assertNotIn('Authorization', handler.req.request_headers)
            user, agent, payload = handler._authenticate()
            self.assertIs(user, self.user)
            self.assertIs(agent, self.agent)
            self.assertEqual(payload, {'description': 'argument description'})
            handler.req.setHeader('Last-Modified', date)
            handler._json({'description': 'updated'})
        with patch.object(vehicle.Handler, '__call__', describe):
            _, value = self.call('vehicle_description_update', {
                'VIN': VIN, 'description': 'argument description', 'if_unmodified_since': date},
                token=self.token(payload={'description': 'claim description'}))
        result = json.loads(value['result']['content'][0]['text'])
        self.assertEqual(result['lastModified'], date)
        def download(handler, **kwargs):
            handler.req.setHeader('Content-Type', 'application/pdf')
            handler.req.write(b'%PDF-binary')
        with patch.object(parking_event.Handler, '__call__', download):
            _, value = self.call('parking_file', {'oid': OID, 'file_oid': AGENT_ID})
        data = json.loads(value['result']['content'][0]['text'])['data']
        self.assertEqual(base64.b64decode(data['base64']), b'%PDF-binary')

    def test_comment_uses_direct_authenticated_handler(self):
        def comment(handler, oid):
            self.assertEqual(oid, OID)
            user, agent, payload = handler._authenticate()
            self.assertIs(user, self.user)
            self.assertEqual(payload, {'description': 'argument comment'})
            handler._json({'history': AGENT_ID}, 201)
        with patch.object(parking_event_comment.Handler, '__call__', comment):
            _, value = self.call('parking_comment', {'oid': OID, 'description': 'argument comment'},
                                 token=self.token(payload={'description': 'claim comment'}))
        self.assertFalse(value['result']['isError'])

    def test_existing_vehicle_concurrency_precondition(self):
        with patch.object(mongo, 'DbSessionController') as controller:
            collection = controller.return_value.__enter__.return_value.__getitem__.return_value.__getitem__.return_value
            collection.find_one.return_value = {
                '_id': VIN, 'last_parking_event_description_upd': datetime.datetime(
                    2026, 7, 2, tzinfo=datetime.timezone.utc)}
            _, value = self.call('vehicle_description_update', {
                'VIN': VIN, 'description': 'new description',
                'if_unmodified_since': 'Wed, 01 Jul 2026 12:30:00 GMT'})
        collection.find_one_and_update.assert_not_called()
        self.assertTrue(value['result']['isError'])
        error = json.loads(value['result']['content'][0]['text'])
        self.assertEqual(error['status'], 412)


if __name__ == '__main__':
    unittest.main()
