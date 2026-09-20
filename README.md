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
description as `text/plain` with the candidate ETag in an `If-Match` header.
The update fails with `412 Precondition Failed` if event history changed or
another worker already updated the description.

The vehicle candidate endpoint selects a random vehicle with a parking event
description newer than the vehicle description. Vehicle descriptions use the
same `text/plain` and `If-Match` workflow, failing if the source event
or history identifiers changed or another worker completed the candidate.
Vehicles keep their latest parking event and history identifiers updated in
the same transaction as those records. Both update APIs record their UTC
timestamp and authenticated user/agent in `description_upd`.
