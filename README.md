Condominium management suite

## Build

Build a wheel with pip:

```sh
python -m pip wheel .
```

The Python package is located under `src`.
Static resources and templates are included in the wheel as package data, so
building the wheel replaces the Makefile's packaging step.

## Configuration

Create `run/config.yaml`:

```yaml
mongodb_uri: mongodb://localhost/parking-enforcement
business_name: Condo Suite
timezone: UTC
google:
  client_id: ""
  client_secret: ""
  redirect_uri: ""
  javascript_origin: ""
```

MongoDB connection details are supplied through `mongodb_uri`; separate host,
port, username, password, and database settings are no longer supported.
Description worker updates use MongoDB transactions, so `mongodb_uri` must
connect to a replica set or sharded cluster.

## Background tasks (Celery)

Deferred/background work (`handlers.defer.*`) runs on Celery, backed by a
RabbitMQ broker over AMQPS with mutual TLS (x509 client certificate)
authentication instead of a login/password. Add a `rabbit` section to
`run/config.yaml`:

```yaml
rabbit:
  host: rabbit.internal
  vhost: /condo_suite
  ssl_cert: /etc/condo_suite/rabbit-client.crt
  ssl_key: /etc/condo_suite/rabbit-client.key
  ssl_ca: /etc/condo_suite/rabbit-ca.crt
```

`vhost` defaults to `/` when omitted; `ssl_cert`, `ssl_key`, and `ssl_ca` are
required. The Celery application is exposed as `condo_suite.util.defer.the_app`
and can be used to start a worker, e.g.:

```sh
celery -A condo_suite.util.defer worker
```

## Parking events API

The signed API provides parking event search, event/history view, file download,
and comments:

```text
GET  /api/parking/event
GET  /api/parking/event/{event-id}
GET  /api/parking/event/{event-id}/file/{file-id}
POST /api/parking/event/{event-id}
POST /api/parking/event/{event-id}/description
GET  /api/vehicle/
POST /api/vehicle/{VIN}/description
GET  /api/search/parking_event_description_candidate
GET  /api/search/vehicle_description_candidate
```

JWTs must be signed with a private key whose public key or certificate is in the
user's signing keyset. Include `user_id`, `kid`, `dt`, `agent_id`, and
`agent_position` in the JWT header. Request parameters are supplied directly in
the JWT payload. See `examples/openssl.sh` for key generation and
`examples/parking_api.py` for a complete client.

The parking event candidate endpoint selects a random event whose description
has not been updated since its latest history item. Post the generated
description as `text/plain` with the candidate `Last-Modified` value in an
`If-Unmodified-Since` header. The update fails with `412 Precondition Failed`
if event history changed or another worker already updated the description.

The vehicle candidate endpoint selects a random vehicle with a parking event
description newer than the vehicle description. Vehicle descriptions use the
same `text/plain` and `If-Unmodified-Since` workflow, failing if a source
parking event description changed or another worker completed the candidate.
Both update APIs record their UTC timestamp and authenticated user/agent in
`description_upd`.

## MCP server

The canonical endpoint is `/mcp/` (`/mcp` also works). It implements stateless
Streamable HTTP with JSON responses, protocol versions `2025-03-26` and
`2025-06-18`, and no sessions or SSE stream. POST JSON-RPC messages with
`Content-Type: application/json` and
`Accept: application/json, text/event-stream`. GET and other unsupported
methods return 405 after authentication. Batch requests are unsupported.

**Every request**, including `initialize`, `tools/list`, notifications, and
unsupported HTTP methods, requires the `Authorization` header with the
`Bearer` scheme followed by your signed JWT.
Use TLS; bearer tokens grant access to anyone holding them. Sign using an
asymmetric algorithm supported by the API (for example RS256) and a private
key whose DER public key **or** DER certificate is registered in the user's
keyset. The JWT header must contain `user_id`, `kid`, `dt` (Unix timestamp or
ISO datetime), `agent_id`, and `agent_position`; the agent must belong to that
user. Tokens are accepted only within 300 seconds of `dt`; refresh them before
expiry. Unsigned tokens and symmetric signatures are not accepted.

Unlike the legacy API, **MCP tool arguments belong in `params.arguments`, not
the JWT payload**. The payload can be `{}`. For example, generate the token
using PyJWT and your registered private key:

```python
import time
import jwt

with open("/path/to/private-key.pem", "rb") as key:
    token = jwt.encode({}, key.read(), algorithm="RS256", headers={
        "user_id": "YOUR_USER_OBJECT_ID", "kid": "YOUR_REGISTERED_KEY_ID",
        "dt": time.time(), "agent_id": "YOUR_AGENT_OBJECT_ID",
        "agent_position": "YOUR_ASSIGNED_POSITION",
    })
```

Send `initialize` with `protocolVersion`, `capabilities: {}`, and
`clientInfo: {"name": "your-client", "version": "1"}`, then
`notifications/initialized` (HTTP 202, empty body). Use
`MCP-Protocol-Version: 2025-06-18` on subsequent requests. An example tool call:

```json
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"parking_search","arguments":{"VIN":"1HGCM82633A004352","limit":20}}}
```

`tools/list` advertises schemas for parking search/view/comment/file and
description candidates/updates; vehicle search and description
candidates/updates; and case view/create/status/comment/link operations.
All operations reuse API authorization and update logic with the authenticated
user/agent. Tool results contain JSON text with `status`, `data`, and optional
`lastModified`; failures use `isError: true`. File data is base64 with a MIME
type. Description updates require `if_unmodified_since` copied exactly from
the candidate's `lastModified`; stale updates return an operation error with
status 412. Case linking queues the existing Celery transaction.

Browser requests with an `Origin` header must match the request's scheme and
Host (otherwise 403); machine clients may omit Origin. No wildcard CORS is
enabled. Configure trusted ingress to enforce allowed Host names and set the
WSGI URL scheme correctly when terminating TLS. Forwarded headers are not
trusted by the MCP endpoint.

## Parking notices

Vehicle and parking event views include a **Create parking notice PDF** link.
The `/parking/notice` page accepts `vin`, `tag`, and `reason` query parameters
to prefill an editable form. **Generate PDF** returns a single 4×6-inch
parking notice with the configured business name, the entered
details, generation time, and the vehicle's latest 20 parking events
(date/time, observed tag, reason, and remarks). All times use the configured
`timezone`. An authenticated user with a selected agent and
`parking.event/view` permission is required; generation does not create or
modify parking events.
