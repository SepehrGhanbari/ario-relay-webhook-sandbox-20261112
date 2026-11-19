#!/bin/sh
set -eu
cd "$(dirname "$0")"
command -v openssl >/dev/null 2>&1 || { echo "OPENSSL_NOT_AVAILABLE"; exit 2; }
openssl ts -verify -in freetsa_timestamp_response.tsr -queryfile freetsa_timestamp_request.tsq -CAfile freetsa_ca.pem
openssl ts -verify -in freetsa_timestamp_response.tsr -data F14_SYNTHETIC_ANCHOR_PAYLOAD.json -CAfile freetsa_ca.pem
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
cp F14_SYNTHETIC_ANCHOR_PAYLOAD.json "$tmp"
printf ' ' >>"$tmp"
if openssl ts -verify -in freetsa_timestamp_response.tsr -data "$tmp" -CAfile freetsa_ca.pem >/dev/null 2>&1; then
  echo "FAIL: tampered payload unexpectedly verified"
  exit 3
fi
echo "PASS: original query and payload verified; tampered payload rejected"
