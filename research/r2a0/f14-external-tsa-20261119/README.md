# F14: independently operated timestamping of a synthetic F13 checkpoint (RFC 3161)

**Status: RESEARCH_ONLY / DRAFT / P0_HOLD / PRODUCTION=NO_GO / TRUST_ACTIVATION=NO_GO.**

This experiment submitted **only a synthetic checkpoint payload's SHA-256** to an external time-stamping authority (FreeTSA). No private memories, actual Ario signer keys, permanent credentials, production rulesets, or live GitHub merge were used.

## Files and provenance

- `F14_SYNTHETIC_ANCHOR_PAYLOAD.json` — exact synthetic payload; SHA-256 `e7e6b9e4abdde1cfa8afdd219c326eaf995f2f740da4f2a01bdc15f756eba6ca`
- `freetsa_timestamp_request.tsq` — DER RFC3161 time-stamp query (embedded payload digest)
- `freetsa_timestamp_response.tsr` — raw DER signed timestamp response; SHA-256 `a4ee6416ea3444875f6a7820a1057364ef45f2a04482597831b42b037881a79c`
- `freetsa_ca.pem` — provider root certificate retrieved from FreeTSA at verification time. This cert is **provider supplied**, not independently validated as a trusted identity by a separate root-of-trust.
- `F14_OBSERVATION.md` — actual test results, scope and limitations
- `verify_f14.sh` — read-only positive/negative check with OpenSSL (requires `openssl`); never issues a new timestamp or sends a network request

## Verify without contacting the original publisher

From this directory:

```sh
openssl ts -verify -in freetsa_timestamp_response.tsr -queryfile freetsa_timestamp_request.tsq -CAfile freetsa_ca.pem
openssl ts -verify -in freetsa_timestamp_response.tsr -data F14_SYNTHETIC_ANCHOR_PAYLOAD.json -CAfile freetsa_ca.pem
sha256sum F14_SYNTHETIC_ANCHOR_PAYLOAD.json freetsa_timestamp_response.tsr
sh verify_f14.sh
```

The signed timestamp proves only that an external TSA **signed a time assertion for this digest**. It does **not** prove the digest came from correct Ario behavior; not all of F13 is externally attested; it does not prove persistent append-only witness custody. Provider certificate trust must be separately assessed. Source F13 is an independent existing [Draft PR #16](https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/pull/16) and remains UNMERGED.

**Unresolved F14 core requirement:** genuinely separate *persistent* checkpoint custodian with independently held verifier floor, rollback/fork/revocation audit and trustworthy verifier certificate pin: **NOT_ESTABLISHED**. Do not promote this TSA-only observation to admission or merge authorization.
