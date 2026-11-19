# F15 — Independent replay from committed GitHub bytes and external Rekor, 2026-11-20

**Status:** `RESEARCH_ONLY / DRAFT / P0_HOLD / PRODUCTION=NO_GO / TRUST_ACTIVATION=NO_GO`.

## Source under test
- F15 published GitHub source HEAD: `df1fd0a91c7f11b6793acae77c53ce70fecfdfcf` (this record was appended in a later evidence-only commit).
- Original synthetic record A: index `206573201`, payload digest `1287f223186e3f71ed5230261d375e8c8070b0eca8384fc30b8de73050b1c5c3`.
- Superseding synthetic record B: index `206575059`, payload digest `cf7ad5df590b7b905faefe4bc0ae1e25a20c556887d56179592ddcaa7bfe9a63`.

## Independent, observed test executions

### 1. Fresh environment reads the exact repository files
A separate cloud shell retrieved all **14/14 F15 files** directly from `raw.githubusercontent.com` at the pinned source HEAD. No original publisher runtime was reused. `openssl` was available.

### 2. Offline cryptographic verification
`python3 f15_verify.py offline` → **exit 0**, for both A and B:

- payload digest matches logged hashedrekord canonical entry;
- original ephemeral ECDSA artifact signature verifies;
- RFC6962 Merkle inclusion path recomputes the exact root of each checkpoint;
- Rekor checkpoint Ed25519 signature verifies against the public key in the **Sigstore root-signing GitHub snapshot**;
- B explicitly refers to A and has a higher index;
- reviewer floor file matches B, **but that floor remains within publisher custody**.

Provider root SHA-256 was checked against its public key; the **TUF chain was not independently verified**.

### 3. Synthetic negative controls
`python3 -m unittest discover -s tests -v` → **12 tests, all pass** (exit 0):

- changed local payload;
- changed Merkle sibling proof;
- changed checkpoint origin/signature;
- swapped disposable public key;
- absent latest B receipt;
- local floor rollback to A;
- falsified latest B digest;
- absent root snapshot;
- invalid expected SHA;
- valid chained version, standard tile addresses and offline/no-network mode.

### 4. Real remote readback after local deletion
In a **fresh, separate cloud environment**, the exact GitHub verifier and synthetic local B payload were downloaded. Local B payload was then **deleted**, and no publisher-local B receipt was present. With only known B index/digest, executed:

```sh
python3 f15_verify.py recover 206575059 cf7ad5df590b7b905faefe4bc0ae1e25a20c556887d56179592ddcaa7bfe9a63
```

**Observed**: `exit=0`, `status=REMOTE_ENTRY_RETRIEVED`, digest exactly equals B; public Rekor tile URL:
`https://log2025-1.rekor.sigstore.dev/api/v2/tile/entries/x806/933`.

### 5. Conditional rollback detection
Simulation: local publisher claims A is newest, while independent auditor retains B's index and hash. Public retrieval returns B. **`ROLLBACK_DETECTED`** because A digest != B digest. This result is **conditional** on a previously retained B pointer.

## What this does NOT prove

- It did **not** delete an entry from the provider's infrastructure or test a malicious log administrator.
- External record retention was observed at readback time only; indefinite service durability is not proven.
- The local `reviewer_floor.json` is not kept by a genuinely separate floor custodian; a complete attacker-controlled rollback of *all pointers* could still hide B.
- The official Sigstore `trusted_root.json` snapshot was read from a GitHub repository and its full TUF authentication chain was **not** replayed.
- A valid log record says only a self-signed synthetic digest was included. It does **not** establish that Ario correctly recorded all events or that the merge gate is live.
- Signed checkpoint third-party witness cosignatures may be present but were **not** validated as an independent quorum.

**Verdict:** `EXTERNAL_LOG_APPEND_AND_READBACK_VERIFIED / BOUNDED_LOCAL_DELETE_RECOVERY_PASS / CONDITIONAL_ROLLBACK_DETECTION_PASS / INDEPENDENT_LATEST_FLOOR_NOT_ESTABLISHED / P0_HOLD / PRODUCTION=NO_GO`.
