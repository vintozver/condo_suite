#!/usr/bin/env python3
"""Small client for the signed parking event API."""

import argparse
import json
import sys
import time
import urllib.request

import jwt


def request(args, method, path, body=None, output=None):
    claims = {'body': body or {}}
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
        data = json.dumps(claims).encode('utf-8')
    req = urllib.request.Request(
        args.base_url.rstrip('/') + path,
        data=data,
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
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
    elif args.command == 'view':
        body, path = {}, '/api/parking/event/' + args.event_id
    elif args.command == 'file':
        body, path = {}, '/api/parking/event/%s/file/%s' % (args.event_id, args.file_id)
    else:
        body, path = {'description': args.description}, '/api/parking/event/' + args.event_id
    request(args, args.method, path, body, getattr(args, 'output', None))


if __name__ == '__main__':
    main()
