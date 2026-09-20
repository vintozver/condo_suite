#!/usr/bin/env python3
"""Small client for the signed parking event API."""

import argparse
import json
import sys
import time
import urllib.request

import jwt


def request(args, method, path, body=None, output=None, headers=None, claims=None):
    claims = body or {} if claims is None else claims
    headers = {
        'alg': args.algorithm,
        'typ': 'JWT',
        'user_id': args.user_id,
        'kid': args.key_id,
        'dt': str(time.time()),
        'agent_id': args.agent_id,
        'agent_position': args.agent_position,
    }
    token = jwt.encode(claims, open(args.key, 'rb').read(), algorithm=args.algorithm, headers=headers)
    data = None
    if body is not None and method != 'GET':
        data = body.encode('utf-8') if isinstance(body, str) else json.dumps(body).encode('utf-8')
    request_headers = {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json',
    }
    request_headers.update(headers or {})
    req = urllib.request.Request(
        args.base_url.rstrip('/') + path,
        data=data,
        headers=request_headers,
        method=method,
    )
    with urllib.request.urlopen(req) as response:
        result = response.read()
    if output:
        with open(output, 'wb') as stream:
            stream.write(result)
    elif result:
        try:
            print(json.dumps(json.loads(result), indent=2))
        except ValueError:
            sys.stdout.buffer.write(result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', required=True, help='Server URL, for example https://condo.example')
    parser.add_argument('--key', required=True, help='PEM private key')
    parser.add_argument('--algorithm', default='RS256')
    parser.add_argument('--user-id', required=True)
    parser.add_argument('--key-id', required=True)
    parser.add_argument('--agent-id', required=True)
    parser.add_argument('--agent-position', required=True)
    subparsers = parser.add_subparsers(dest='command', required=True)

    search = subparsers.add_parser('search')
    search.add_argument('--vin')
    search.add_argument('--tag')
    search.add_argument('--reason')
    search.set_defaults(method='GET', path='/api/parking/event')

    vehicle = subparsers.add_parser('vehicle')
    vehicle.add_argument('--vin')
    vehicle.add_argument('--tag')
    vehicle.set_defaults(method='GET', path='/api/vehicle/')

    event_candidate = subparsers.add_parser('event-candidate')
    event_candidate.set_defaults(
        method='GET', path='/api/search/parking_event_description_candidate')

    event_describe = subparsers.add_parser('event-describe')
    event_describe.add_argument('event_id')
    event_describe.add_argument('history_version')
    event_describe.add_argument('description')
    event_describe.set_defaults(method='POST')

    vehicle_candidate = subparsers.add_parser('vehicle-candidate')
    vehicle_candidate.set_defaults(
        method='GET', path='/api/search/vehicle_description_candidate')

    vehicle_describe = subparsers.add_parser('vehicle-describe')
    vehicle_describe.add_argument('vin')
    vehicle_describe.add_argument('event_version')
    vehicle_describe.add_argument('description')
    vehicle_describe.set_defaults(method='POST')

    view = subparsers.add_parser('view')
    view.add_argument('event_id')
    view.set_defaults(method='GET')

    file_parser = subparsers.add_parser('file')
    file_parser.add_argument('event_id')
    file_parser.add_argument('file_id')
    file_parser.add_argument('-o', '--output', required=True)
    file_parser.set_defaults(method='GET')

    comment = subparsers.add_parser('comment')
    comment.add_argument('event_id')
    comment.add_argument('description')
    comment.set_defaults(method='POST')

    args = parser.parse_args()
    if args.command == 'search':
        body = {key: value for key, value in
                (('VIN', args.vin), ('tag', args.tag), ('reason', args.reason)) if value}
        path = args.path
    elif args.command == 'vehicle':
        body = {key: value for key, value in (('VIN', args.vin), ('tag', args.tag)) if value}
        path = args.path
    elif args.command in ('event-candidate', 'vehicle-candidate'):
        body, path = {}, args.path
    elif args.command == 'event-describe':
        body = args.description
        path = '/api/parking/event/%s/description' % args.event_id
    elif args.command == 'vehicle-describe':
        body = args.description
        path = '/api/vehicle/%s/description' % args.vin
    elif args.command == 'view':
        body, path = {}, '/api/parking/event/' + args.event_id
    elif args.command == 'file':
        body, path = {}, '/api/parking/event/%s/file/%s' % (args.event_id, args.file_id)
    else:
        body, path = {'description': args.description}, '/api/parking/event/' + args.event_id
    headers = None
    if args.command in ('event-describe', 'vehicle-describe'):
        version = (
            args.history_version if args.command == 'event-describe'
            else args.event_version)
        headers = {
            'Content-Type': 'text/plain',
            'If-Match': '"%s"' % version,
        }
    claims = {} if args.command in ('event-describe', 'vehicle-describe') else None
    request(
        args, args.method, path, body, getattr(args, 'output', None), headers,
        claims)


if __name__ == '__main__':
    main()
