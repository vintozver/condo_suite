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
timezone: UTC
google:
  client_id: ""
  client_secret: ""
  redirect_uri: ""
  javascript_origin: ""
```

MongoDB connection details are supplied through `mongodb_uri`; separate host,
port, username, password, and database settings are no longer supported.
