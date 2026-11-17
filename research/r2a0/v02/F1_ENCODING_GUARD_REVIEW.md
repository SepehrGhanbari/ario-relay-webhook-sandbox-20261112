# R2a-0 v0.3 — F1 encoded branch readback guard (research fix)

**Date:** 2026-11-17  
**Status:** SOURCE FIX + LOCAL TESTS ONLY / DRAFT / HOLD.  
**Affected PR:** [#10](https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/pull/10).

## Verified defect
`snapshot()` constructs `GET /repos/<lab>/rules/branches/experiment%2Fr2a0-...`, but `gh_api()` rejected **all** `%2f` sequences. This made a normal isolated-branch Ruleset snapshot fail *before contacting GitHub*. It was **not covered by the earlier 50 tests**, which mocked the snapshot fetch or only tested rejection of invalid paths.

A separate strictness concern: `%252F` (double-encoded slash) was **not** rejected by the earlier simple denylist, although whether GitHub would decode it is *untested*. Classify as INPUT-GUARD WEAKNESS, **not** as a demonstrated production traversal exploit.

## Reproduction (offline)
- Baseline 50/50 PASS at original HEAD `3681642ac47a2ca9e1b3a8f0aaff671e28cc189e`.
- Added 4 targeted tests *before* source fix: `Ran 54 tests / FAILED (failures=2, errors=3)`; independent error arose from a malformed mock in the newly added test and was corrected before GREEN.
- Direct original-code observation: `gh_api('repos/<lab>/rules/branches/experiment%2Fr2a0-test')` raises `ValueError: GitHub API path outside approved lab repository`.
- After minimal scope fix and test correction: **54/54 PASS (local CPython 3.13/Linux)**.
- Source SHA256: `854586f49c8d367618c8879a2f63bb1623defcac5b308d03bb169151e6a2b463`
- Test SHA256: `6f886aaedbe4f186dbe8628a05ebe5ad40ef8c2a41f4d3adea2cd07048069047`
- Git blob source: `6983e6d6b7df283e736680bb94b2f0632e532b09`
- Git blob tests: `7879f786c623508fb7f8634acfe7368fbf8a8f82`.

## Precise fix
1. Allow encoded slash **only** in the exact read-only `rules/branches/experiment%2Fr2a0-<flat suffix>` endpoint.
2. Reject `%25` double-encoding, `%2e` dot-encoding, dot-dot traversal, backslashes, and unrelated encoded-slash paths.
3. Verify the PR's base ref is a flat `experiment/r2a0-<suffix>` in both snapshot and guarded merge logic.
4. Add four tests for positive rules readback, snapshot integration, malicious encoded paths and nonlab base rejection.

## Limits and admission
The test mocks `subprocess.run` and REST results. **No live GitHub ruleset readback or native Sc1–Sc4/Sk/Se1 behavior was demonstrated**. No external App publisher or independently custodied witness is operational here.

The tests are written by the same candidate author, and green candidate-authored CI cannot act as independent approval. External review is still required.

`RESEARCH_ONLY / LIVE_R2A0_NOT_RUN / NO_PRODUCTION_WRITE / P0_HOLD`
