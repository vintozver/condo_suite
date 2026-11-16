import base64
from datetime import datetime
import re
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlencode, urlsplit
from wsgiref.headers import Headers
from zoneinfo import ZoneInfo
import zlib

from condo_suite.modules import mongo

# RBAC preloads roles at import time; these unit tests do not need a database.
with patch.object(mongo, 'DbSessionController') as controller:
    database = controller.return_value.__enter__.return_value.__getitem__.return_value
    database.__getitem__.return_value.find.return_value.sort.return_value = []
    from condo_suite.handlers.web import Handler as Router
    from condo_suite.handlers.web import parking_notice

from condo_suite.modules.templates.filesystem import TemplateFactory
from condo_suite.handlers.web.parking_notice_pdf import generate_notice


VIN = '1HGCM82633A004352'
LOCAL_TIME = datetime(2026, 7, 1, 12, 30, tzinfo=ZoneInfo('America/New_York'))


def pdf_streams(pdf):
    streams = []
    for match in re.finditer(rb'<<(.*?)>>\s*stream\r?\n(.*?)endstream', pdf, re.S):
        metadata, data = match.groups()
        if b'ASCII85Decode' in metadata:
            data = base64.a85decode(data.strip(), adobe=True)
        if b'FlateDecode' in metadata:
            data = zlib.decompress(data)
        streams.append(data)
    return b'\n'.join(streams)


class NoticePDFTests(unittest.TestCase):
    def generate(self, events, reason='Fire lane'):
        return generate_notice('Condo & Suite', VIN, 'ABC123', reason, LOCAL_TIME, events)

    def assert_notice_page(self, pdf):
        self.assertTrue(pdf.startswith(b'%PDF-'))
        self.assertRegex(pdf, rb'/MediaBox\s*\[\s*0 0 288 432\s*\]')
        self.assertEqual(len(re.findall(rb'/Type /Page\b', pdf)), 1)

    def test_notice_content_and_local_time(self):
        pdf = self.generate([])
        self.assert_notice_page(pdf)
        self.assertIn(b'/Title (Parking Notice)', pdf)
        content = pdf_streams(pdf)
        self.assertNotIn(b'Parking Violation', content)
        for value in (b'Parking Notice', b'Condo & Suite', VIN.encode(), b'ABC123',
                      b'Fire lane', b'2026-07-01 12:30:00 EDT -0400', b'No parking events.'):
            self.assertIn(value, content)

    def test_twenty_events_and_long_text_fit_one_page(self):
        events = [{
            'dt': LOCAL_TIME, 'tag': 'row-%s' % index,
            'reason': 'Obstruction ' * 10, 'remarks': 'Long remarks ' * 30,
        } for index in range(21)]
        pdf = self.generate(events)
        self.assert_notice_page(pdf)
        content = pdf_streams(pdf)
        self.assertIn(b'row-19', content)
        self.assertNotIn(b'row-20', content)
        for label in (b'DT', b'Tag', b'Reason', b'Remarks', b'EDT'):
            self.assertIn(label, content)

    def test_markup_is_literal_text(self):
        pdf = self.generate([], '<img src="https://invalid.example/picture"/> & <b>text</b>')
        self.assert_notice_page(pdf)
        content = pdf_streams(pdf)
        self.assertIn(b'img src=', content)
        self.assertIn(b'(/b) Tj', content)


class NoticeHandlerTests(unittest.TestCase):
    def request(self, method='GET', values=None):
        encoded = urlencode(values or {})
        req = Mock()
        req.method = method
        req.query_string = encoded if method == 'GET' else ''
        req.request_body = encoded.encode() if method == 'POST' else b''
        req.requestHeaders = Headers([('Content-Type', 'application/x-www-form-urlencoded')])
        req.request_headers = req.requestHeaders
        req.context = SimpleNamespace(session_user=Mock(), session_agent=Mock())
        return req

    def call(self, req):
        method = parking_notice.Handler.__dict__['__call__']
        while hasattr(method, 'method'):
            method = method.method
        return method(parking_notice.Handler(req))

    def test_route_and_uri_prefill(self):
        self.assertEqual(Router.handle_map(Router.ROUTE_MAP, '/parking/notice'),
                         ('web.parking_notice', {}))
        values = {'vin': VIN, 'tag': 'A&B 1', 'reason': '<other> & fire'}
        req = self.request(values=values)
        with patch.object(parking_notice.mod_tmpl, 'TemplateFactory') as factory:
            self.call(req)
        self.assertEqual(factory.return_value.render.call_args.args[0],
                         dict(values, error=None))
        req.setHeader.assert_any_call('Cache-Control', 'private, no-store')

    def test_post_fetches_latest_twenty_for_vin_and_returns_pdf(self):
        req = self.request('POST', {'vin': VIN, 'tag': 'ABC123', 'reason': 'Fire lane'})
        event = SimpleNamespace(
            id=SimpleNamespace(generation_time=LOCAL_TIME),
            vehicle=SimpleNamespace(tag='OLDTAG'), reason='other', remarks='Historical remarks')
        with patch.object(parking_notice, 'ParkingEventDocument') as document, \
                patch.object(parking_notice, 'generate_notice', return_value=b'%PDF-test') as generate, \
                patch.object(parking_notice.config, 'timezone', LOCAL_TIME.tzinfo), \
                patch.object(parking_notice.config, 'business_name', 'Test Business'):
            query = document.objects.return_value.order_by.return_value
            query.__getitem__.return_value = [event]
            self.call(req)
        document.objects.assert_called_once_with(__raw__={'vehicle._id': VIN})
        document.objects.return_value.order_by.assert_called_once_with('-id')
        query.__getitem__.assert_called_once_with(slice(None, 20))
        args = generate.call_args.args
        self.assertEqual(args[:4], ('Test Business', VIN, 'ABC123', 'Fire lane'))
        self.assertEqual(args[4].tzinfo, LOCAL_TIME.tzinfo)
        self.assertEqual(args[5][0]['tag'], 'OLDTAG')
        self.assertEqual(args[5][0]['remarks'], 'Historical remarks')
        req.setHeader.assert_any_call('Content-Type', 'application/pdf')
        self.assertFalse(any(
            call.args[0].lower() == 'content-disposition'
            for call in req.setHeader.call_args_list))
        req.write.assert_called_once_with(b'%PDF-test')

    def test_invalid_input_never_queries_database(self):
        for values in ({}, {'vin': 'invalid', 'tag': 'X', 'reason': 'other'},
                       {'vin': VIN, 'tag': 'X' * 21, 'reason': 'other'},
                       {'vin': VIN, 'tag': 'X', 'reason': 'R' * 501}):
            with self.subTest(values=values):
                req = self.request('POST', values)
                with patch.object(parking_notice.mod_tmpl, 'TemplateFactory'), \
                        patch.object(parking_notice, 'ParkingEventDocument') as document:
                    self.call(req)
                req.setResponseCode.assert_called_once_with(400, 'Bad Request')
                document.objects.assert_not_called()

    def test_requires_user_agent_and_event_view_permission(self):
        for missing in ('session_user', 'session_agent', 'permission'):
            req = self.request()
            if missing == 'permission':
                req.context.session_user.rbac_has_permission.return_value = False
            else:
                setattr(req.context, missing, None)
            with self.subTest(missing=missing), \
                    patch.object(parking_notice, 'ParkingEventDocument') as document:
                with self.assertRaises(parking_notice.deco.auth.SecurityError):
                    self.call(req)
                document.objects.assert_not_called()

    def test_unsupported_method(self):
        req = self.request('DELETE')
        self.call(req)
        req.setResponseCode.assert_called_once_with(405, 'Method Not Allowed')
        req.setHeader.assert_any_call('Allow', 'GET, POST')


class NoticeTemplateTests(unittest.TestCase):
    def test_form_escapes_uri_values(self):
        html = TemplateFactory('parking_notice').render({
            'vin': VIN, 'tag': '"><script>alert(1)</script>',
            'reason': '</textarea><script>alert(1)</script>', 'error': None,
        })
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('&lt;/textarea&gt;', html)
        self.assertIn('Generate PDF', html)

    def test_vehicle_and_event_links_encode_parameters(self):
        from html import unescape
        values = {'VIN': VIN, 'tag': 'A&B 1', 'reason': 'fire & obstruction',
                  'history': [], 'parking_event_list': []}
        for name in ('vehicle_view', 'parking_event_view'):
            with self.subTest(template=name):
                html = TemplateFactory(name).render(values)
                link = re.search(r'href="([^"]*/parking/notice[^"]*)"', html).group(1)
                query = parse_qs(urlsplit(unescape(link)).query, keep_blank_values=True)
                self.assertEqual(query['vin'], [VIN])
                self.assertEqual(query['tag'], ['A&B 1'])
                self.assertEqual(query['reason'], [values['reason'] if name == 'parking_event_view' else ''])


if __name__ == '__main__':
    unittest.main()
