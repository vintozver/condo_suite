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

## Parking events API

The signed API provides parking event search, event/history view, file download,
and comments:

```text
GET  /api/parking/event
GET  /api/parking/event/{event-id}
GET  /api/parking/event/{event-id}/file/{file-id}
POST /api/parking/event/{event-id}
```

JWTs must be signed with a private key whose public key or certificate is in the
user's signing keyset. Include `user_id`, `kid`, `dt`, `agent_id`, and
`agent_position` in the JWT header. Request parameters are supplied directly in
the JWT payload. See `examples/openssl.sh` for key generation and
`examples/parking_api.py` for a complete client.
