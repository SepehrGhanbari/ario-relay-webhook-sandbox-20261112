# F12 — Post-observation local evidence downgrade (Ava research candidate, 2026-11-19)

## Scope and provenance
- Input: F11 standalone review archive, originally built from pinned Trae F10 bundle.
- This is a **new Ava candidate**, not an original Trae source commit.
- Input F11 file: `F11_original_f7_coordinator.py`, SHA-256: `9aeaadfd6da5c50bbfedb30a8219a845cf0d7a7447ba46f2155d18a580b41eba`.
- Candidate F12: `f7_coordinator.py`, SHA-256: `33ee3a8b2e9527506aeb637d8b5326f5cc09ebdf199bf99fa77026c2d9582a51`.
- F12 standalone contract tests: `test_f12_live_observation_integrity.py`, SHA-256: `a8f71094e5ddc5591faba8cf4cfef287cd7d4ebb6e4cdef25973b9944d78d3c8`.
- Diff: `F12_Coordinator_Evidence_Fix.patch` applies byte-identically to original F11.

## Reviewer findings and response
1. **Delete evidence after event:** original inspect continued returning `LOCAL_EVIDENCE_RECORDED`. F12 keeps raw events as **immutable history**, but separately returns `observation_status=UNKNOWN_LOCAL_EVIDENCE_NOT_REVALIDATED` after journal deletion/corruption. Existing valid evidence yields `CURRENT_LOCAL_READBACK_MATCH_NOT_INDEPENDENT` only at read time.
2. **Truncate index after read before commit:** F12 samples index bytes before and after `EvidenceJournal.read()`, and again immediately before INSERT. Deterministic injected truncation after `read()` is rejected. **Not atomic across filesystem and SQLite**: there is still a TOCTOU gap after the last check and possible subsequent modification.
3. **Change SQLite `consumptions.evidence_root`:** F12 duplicates the original consumed root as a SHA-256 binding in a separate SQLite table inserted in the same F10 consumption transaction. Changing only one column is rejected. **Changing BOTH same-owner DB values can still fool it**, explicitly demonstrated by a passing negative-limit test. Hashes within the same owner-controlled DB are not independent proof.
4. **Historical events:** raw `events` is deliberately returned unchanged for audit but marked `events_are_historical_not_proof=True`. No old event is silently treated as a current receipt.

## New versioned schema
SQLite `DB_VERSION=9`, new `root_bindings` and `observation_snapshots`. No automatic migration of v8 DB; reopening a v8 DB refuses with `COORDINATOR_SCHEMA_VERSION_MISMATCH`. The F12 bundle is a lab artifact and is not a production migration plan. A separate owner-approved versioned migration would be required before use beyond the sandbox.

## Red/green execution (local Linux, CPython 3.13)
- On exact F11 source plus F12 test module: **9 tests; 3 failures, 6 errors**. Some errors reflect missing F12 API/status; the two key independent behavioral failures are truncation during read and single-column root substitution acceptance.
- F12 source + old and new unittest modules: **162 tests run, OK**; older F11 and F10 tests retained.
- `git apply --check` plus actual application to original F11 and bytewise compare with candidate: **PASS**.
- `merge_authorization=NOT_GRANTED`, no network, no native merge, no signer or credential use. Windows **NOT_RUN**.

## Hard limits
- This is **current local readback**, not true independence, cryptographic integrity against owner, independent receipt, rollback resistance or multi-host consensus.
- There is **no single transaction spanning journal files and SQLite**; a racing writer can still change journal files after the last validation and before SQLite commit or after a readback.
- Same-owner attacker who can edit both tables, or fork/restore database and files, can fabricate a consistent view.
- The state `CURRENT_LOCAL_READBACK_MATCH_NOT_INDEPENDENT` must **never be treated as merge authorization or an independent witness**.
- Need focused adversarial follow-up on multi-process, Windows, copied DBs, same-owner substitution and true protected custody.

`RESEARCH_ONLY / DRAFT / P0_HOLD / PRODUCTION=NO_GO / TRUST_ACTIVATION=NO_GO`
