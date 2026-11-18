# F10 — Independent code-and-execution audit (Ava, 2026-11-18)

## Provenance and scope

- Artifact: user-supplied `f10_review_bundle.zip`.
- **ZIP SHA-256:** `40a859b5c1544fed3aed6b8f8d6fb52e4a42438f5b33750a3915a5f37c5c1129` (exactly matches Trae's declared value).
- 25 ZIP members in one top-level folder; all 24 entries in `MANIFEST.sha256` independently checked, with **zero mismatches**. Zip-path and symlink entry checks passed; no unexpected external path was extracted.
- All four principal F10 source/test hashes matched README and Trae's prior report: `src/f7_coordinator.py` `52e3dd46bfa5b01f6f69c7f380769512446c716e524903a81cde0aa1b3da967e`; `src/r2a0.py` `8578432fc42598c293929fa7930732bf8260c3736d71c5640daf60317998c479`; `src/tests/test_f10_atomic_single_use.py` `1183549aa1f970dc1960ca34356c327fb2ba8856d0c46c7a215ac9b94e3c2c4c`; `src/f10_authority_reuse_red_probe.py` `9403e34c0bc2dd8361ce5dc691b441ab385da14b6f22daf8e247da004e2c225b`.
- Base F9 Git *blob* identities checked independently against the exact provided `baseline_f9/` bytes: `r2a0.py=5f6972fd5eb3d2d762079968501b5a2df227cdcc`; `f7_coordinator.py=40791854d15a3554a89a51d4f25def0ab642f6fb`.
- **Patch roundtrip:** reversing `report/evidence/F10_fix.diff` from candidate source yielded the exact baseline F9 byte files; reapplying it returned the exact bundled F10 implementation bytes (and the edited tests). `git apply --check` passed in both directions. This is a consistency check, **not** independent custody or a signed original commit.

## Execution performed (independently, Linux CPython 3.13.5)

Command: `env -u GH_TOKEN -u GITHUB_TOKEN -u GH_WEBHOOK_SECRET -u ARIO_R2A0_DISPOSABLE_MERGE_ACK PYTHONDONTWRITEBYTECODE=1 python run_f10_review.py --mode both`.

**RED against the pre-F10 code:** 9 contract tests run; **5 failures + 2 errors + 2 passes**, and the external probe returned `VERIFIED_DOUBLE_USE_OF_DB_CHECKABLE_AUTHORITY`, `accepted_roots=2`, `network=NOT_USED`. The 7 nonpassing tests include missing-API errors on the old baseline, so the **actual double-use probe** is necessary independent evidence; do not present all 7 as behavioral counterexamples.

**GREEN against F10 candidate:** `Ran 146 tests ... OK` (21.073 seconds). External probe returned `SINGLE_USE_ENFORCED`, `accepted_roots=1`, `network=NOT_USED`. Wrapper returned exit 0 and reported `red=PASS green=PASS`. This is independent execution of candidate-authored tests and falsifier; it is not independent admission authority.

**Additional Ava-authored independent probes** (not part of Trae bundle) passed:
1. Two separate evidence roots with one shared claimed intent: first direct public sink append records once; second raises exactly `AUTHORITY_ALREADY_CONSUMED`; shared SQLite contains one `consumptions` row.
2. An existing DB downgraded to schema version 7 fails closed with `COORDINATOR_SCHEMA_VERSION_MISMATCH`; no migration or silent new DB.
3. **New documented gap (see below):** `record_local_observation(intent,marker,root_label)` inserts `LOCAL_EVIDENCE_RECORDED` after a durable `CLAIMED` even if no journal write occurred and no `consumptions` row exists. Reproduced with a fresh independent DB and no evidence root.

## Code review and residual findings

**F10 central invariant: PASS within bounded scope.** `consume_intent_authority` rechecks durable claim and unique consumption in one `BEGIN IMMEDIATE` transaction; committing the one-time consumption *before* writing to the local evidence journal stops a second supported write. A crash in the gap is conservatively HOLD with no takeover. Supporting evidence includes direct independent probe, candidate race/crash tests, and actual source review.

**P1 / SOURCE-VERIFIED provenance limitation (new):** `f7_coordinator.py:143–160`, `SharedCoordinator.record_local_observation`, checks marker/root label and `CLAIMED` event count, but does **not** require a matching `consumptions` row, actual journal record or independently checked receipt. A caller can create the audit phase `LOCAL_EVIDENCE_RECORDED` after only `claim()`. It is **not** a bypass of F10's supported sink single-use invariant; it is a potential *false provenance / misleading audit-state* path if consumers interpret the event as evidence of a real journal append. Proposed minimal follow-up: document this event as an **unverified reporter observation** unless a separate verifiable evidence binding is introduced; add a negative test for claim-only observation, and only later require independently grounded evidence before promoting it to an admitted assertion. Keep existing historical phases immutable.

**Known unsolved, honestly stated:** copied/forked/rolled-back SQLite DB can duplicate authority; same-owner interpreter can invoke `_append_merge_intent_raw`; no cryptographic token, protected OS boundary, independent witness or multi-host consensus. Native GitHub merge-time R2a-0 scenarios `Sc1`, `Sc2`, `Sk`, `Sn`, `Sc3`, `Sc4`, `Se1` remain `NOT_RUN`. No production key, Ruleset, signer or trust enabled.

**Platform coverage:** Linux CPython **3.13.5**, not Trae's original 3.14.8. **Windows NOT_RUN**, no false inference from Windows-aware test code. Also, the legacy reviewer-owned `f8_review_red_test.py` lives outside `src/tests/` and intentionally fails when run via whole-directory pytest; successful `unittest discover -s tests -t tests` does **not** mean all arbitrary test files are green.

## Verdict

`SOURCE_BYTES_MATCH / LOCAL_RED_GREEN_REPRODUCED / SUPPORTED_SINGLE_USE_BOUNDED_PASS / P1_UNVERIFIED_LOCAL_OBSERVATION / WINDOWS_NOT_RUN / NATIVE_GITHUB_NOT_RUN / DRAFT / P0_HOLD / PRODUCTION=NO_GO / TRUST_ACTIVATION=NO_GO`

No PR merge, network API write, real key operation, protected rule modification or production deployment was performed.