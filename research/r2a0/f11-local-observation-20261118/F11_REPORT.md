# F11 — Local evidence observation must not certify itself

Status: `RESEARCH_ONLY / DRAFT / P0_HOLD / PRODUCTION=NO_GO / TRUST_ACTIVATION=NO_GO`

## Pinned provenance
Ava-authored **F11 research candidate**, based on original user-uploaded Trae F10 bundle `f10_review_bundle.zip` (SHA-256 `40a859b5c1544fed3aed6b8f8d6fb52e4a42438f5b33750a3915a5f37c5c1129`). Original F10 `src/f7_coordinator.py` SHA-256 `52e3dd46bfa5b01f6f69c7f380769512446c716e524903a81cde0aa1b3da967e`. Patched coordinator SHA-256 `9aeaadfd6da5c50bbfedb30a8219a845cf0d7a7447ba46f2155d18a580b41eba`.

This candidate does not rewrite Trae's F10 Git history or silently merge it with [Ava's separate F9 reconstruction PR #12](https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/pull/12). The historical F10 review archive is [Draft PR #13](https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/pull/13).

## VERIFIED baseline defect, bounded fix
F10 `SharedCoordinator.record_local_observation` could emit the phase `LOCAL_EVIDENCE_RECORDED` with a durable CLAIM alone. Neither an F10 consumption nor an actual matching journal row was checked. Trae's F10 single-use fix does not itself close this separate observation overclaim.

F11 reads the matching consumption row from the SQLite coordinator and re-checks the full local journal via `EvidenceJournal.read()` before emitting that phase. It must see exactly one matching canonical merge-intent and intact hash-chain/marker custody. Missing, corrupt or mismatched evidence leads to HOLD; there is no auto-recovery, history deletion or merge retry.

## Real bounded local experiments
- Original F10 + seven new F11 contract tests: **7 run / 5 failures / 2 passes** (RED). Claim-only, consumed-without-journal, raw-writer without consumption, root mismatch and corrupted journal were accepted before the patch.
- F11 candidate + full existing F10 unittest suite + seven tests: **153/153 PASS** on Linux CPython 3.13.5.
- `unittest discover -s tests -t tests` is the suite whose count is claimed; intentionally RED adversarial fixtures outside `tests/` are NOT reclassified as passing.

## Remaining limits
This is an extra **local readback check**, not an external witness, cryptographic proof, OS isolation or durable assurance after future tampering/rollback. A same-owner process can edit journal/DB or call raw internals. Historical `LOCAL_EVIDENCE_RECORDED` events remain under old contract and are NOT retroactively proven. Native GitHub R2a-0 Sc1/Sc2/Sk/Sn/Sc3/Sc4/Se1 and Windows are NOT RUN. Do not install governance, merge, touch real keys or change production rulesets.

Review focus: readback→commit TOCTOU, path aliases, malformed consumption, stale historical semantics, separate host custody. Supply line-specific counterexamples. Keep DRAFT/HOLD.

Files:
- `F11.patch` is the exact unified diff against F10 `src/f7_coordinator.py`.
- `test_f11_observation.py` runs with the 146 original F10 tests.
- Local evidence ZIP is downloadable in the source conversation and not yet incorporated in this GitHub PR.
