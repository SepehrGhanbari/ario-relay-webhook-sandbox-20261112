# F15 — third-party-operated transparency log retention, rollback/deletion falsifier

**RESEARCH_ONLY / DRAFT / P0_HOLD / PRODUCTION=NO_GO / TRUST_ACTIVATION=NO_GO**

This F15 experiment builds on [F14 Draft PR #17](https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/pull/17) and its synthetic F13 commitment. It **does not** change Ario production or GitHub merge rules.

## Real, separate operator

**Sigstore public-good Rekor v2** operates at `https://log2025-1.rekor.sigstore.dev` (vendor-managed, not controlled by the Ario project). We sent **two synthetic digest-only HashedRekord v0.0.2 records** with separate disposable P-256 signing keys. Only the public keys and signatures were archived; private keys were not published or retained.

| Record | Rekor log index | Payload SHA-256 | Purpose |
|---|---:|---|---|
| v1 / A | 206573201 | `1287f223186e3f71ed5230261d375e8c8070b0eca8384fc30b8de73050b1c5c3` | Original synthetic checkpoint |
| v2 / B | 206575059 | `cf7ad5df590b7b905faefe4bc0ae1e25a20c556887d56179592ddcaa7bfe9a63` | Superseding checkpoint, references v1 digest |

`v1/` and `v2/` contain exact synthetic JSON payload, original Rekor signed-entry response and inclusion proof, disposable signer **public** key and detached signature. The response stores a Rekor-signed checkpoint. `trusted_root_source_snapshot.json` is an immutable snapshot from the **Sigstore root-signing GitHub repo**, Git blob `effb0a19e6a0b3f69b3f0a2c72b5c2a02a0ddeea`. **Its TUF distribution signatures were NOT independently checked** in this exercise.

## Reproduce the results without credentials

Requires Python 3.10+ and OpenSSL on PATH.

```sh
cd research/r2a0/f15-third-party-rekor-20261120
python3 f15_verify.py offline
python3 -m unittest discover -s tests -v
# Optional: read **the external operator's own tile**, independent of locally saved entry:
python3 f15_verify.py recover 206575059 cf7ad5df590b7b905faefe4bc0ae1e25a20c556887d56179592ddcaa7bfe9a63
```

Offline verification checks **Rekor's signed checkpoint**, RFC6962 Merkle inclusion proof, SHA256 payload binding, disposable artifact signatures and the linked v1→v2 sequence. Online recovery downloads the **public Rekor tile** containing entry B and checks its digest at the original log index.

The independent online readbacks returned HTTP 200 for both:
- [v1 entry bundle](https://log2025-1.rekor.sigstore.dev/api/v2/tile/entries/x806/926), offset 145
- [v2 entry bundle](https://log2025-1.rekor.sigstore.dev/api/v2/tile/entries/x806/933), offset 211

Tiled entry bundles are binary, containing 256 length-prefixed entry JSON records. `recover` parses them in read-only mode.

## What the rollback / deletion exercise means

1. Persist v1, then v2 at **external indices** above.
2. Simulate **publisher-local deletion of B** or rollback of its local pointer to v1. The public Rekor tile still exposes B at its known index, independently of the publisher's folder.
3. A verifier with an **already pinned v2 floor** can detect a local pointer claiming v1 is the latest. A verifier whose floor is also deleted/rolled back may **not even know** to query v2. External log inclusion alone does not prove that nobody hid newer entries.
4. Do not attempt to delete or damage the third-party Sigstore service. This experiment tests **publisher-local deletion**, not operator-side forced deletion, malicious service admins, suppression of unknown entries, complete-fork resistance or guarantees about indefinite archival.

**What remains NOT ESTABLISHED:** a fully separately administered durable **latest-floor custodian**, independent trust in TUF root metadata, audited log consistency across time and multiple origins, complete event intake, or any GitHub merge/Ario trust activation.

## Provenance & tests

- [F15_RESULT.md](F15_RESULT.md) — exact observations and stop rules
- [f15_verify.py](f15_verify.py) — read-only verifier, no signer/merge routines
- [tests/test_f15.py](tests/test_f15.py) — regression and adversarial cases
- [reviewer_floor.json](reviewer_floor.json) — this **is not itself externally controlled**; an audit precondition only

**Do not merge** until real independent-floor custody and policy decisions are separately approved.
