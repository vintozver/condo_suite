#!/bin/sh
set -eu

# Generate the private key. Keep credential.key secret.
openssl genpkey -algorithm RSA -out credential.key -pkeyopt rsa_keygen_bits:2048

# Create a self-signed certificate accepted by the user keyset.
openssl req -new -x509 -key credential.key -out credential.crt \
    -days 365 -subj "/CN=credential"

# Alternatively, extract a public key and add credential.pub to the keyset.
openssl pkey -in credential.key -pubout -out credential.pub
