# F15 — independent witness cosignature audit

**This supplements F15's public Rekor records; it does not grant merge or trust authority.**

Evidence source: `v2/rekor_response.json`, original Rekor B entry index **206575059** and exact signed checkpoint (tree size 206575061). Checkpoint origin `log2025-1.rekor.sigstore.dev`.

**Verified independently** in a separate cloud execution:
- Witness line: `— witness.stagemole.eu ...` in the *actual* B checkpoint.
- Public verifier key separately published by the **witness operator** at <https://witness.stagemole.eu/about>:
  `witness.stagemole.eu+67f7aea0+BEqSG3yu9YrmcM3BHvQYTxwFj3uSWakQepafafpUqklv`.
- Detached 76-byte cosignature/v1: 4-byte key hint, 8-byte big-endian timestamp, 64-byte Ed25519 signature.
- Key hint `67f7aea0` matched the independently published key; constructed message `cosignature/v1\ntime 1795123486\n` followed by the exact checkpoint note body, including its terminating newline, as specified by C2SP.
- Verified with OpenSSL `pkeyutl -verify -rawin`: **`Signature Verified Successfully`**.
- Witness-signed timestamp: **2026-11-19 21:24:46 UTC**.
- A mutation of the signed checkpoint content must fail; see `f15_witness_verify.py --tamper`.

This is meaningful: the outside witness's distinct private signing key co-signed the **external Rekor checkpoint**, and per the C2SP witness protocol the witness is intended to maintain its own latest observed *log tree head*. It is NOT a separate custodian for **Ario's latest claimed event digest or all event records**, and does not authenticate the Ario publisher's original runtime.

External verification still depends on the witness operator's published key, which was obtained directly from its website; **a broader independent public-key governance audit was not performed**.

`F15_EXTERNAL_LOG_CHECKPOINT_WITNESSED / INDEPENDENT_REKOR_LOG_WITNESS_VERIFIED / INDEPENDENT_ARIO_LATEST_FLOOR_NOT_ESTABLISHED / P0_HOLD / PRODUCTION=NO_GO`.
