# F12 — local observation readback, not a trusted receipt

**Status: RESEARCH_ONLY / DRAFT / P0_HOLD / PRODUCTION=NO_GO / TRUST_ACTIVATION=NO_GO.**

New Ava-authored research candidate from the owner-supplied original F11 review bundle, NOT a Trae historical commit and NOT the Ario production tree.

## Contents
- `F12.patch` exact-byte F11→F12 local source change, SHA-256 `5ad0cf1f9b45af9449c3b0d13a4bd7d512aebb6c772b6e30161f2c16b8cea117`.
- `tests/test_f12_live_observation_integrity.py` exact-byte nine-case tests, SHA-256 `a8f71094e5ddc5591faba8cf4cfef287cd7d4ebb6e4cdef25973b9944d78d3c8`.
- `F12_REVIEW_REPORT.md` author/reviewer report and limitations.

To replay, extract the original F11 review bundle (the nested F10 `src/`), put original F11 `f7_coordinator.py` in `src/`, apply `F12.patch` from that directory, copy the new test module to `src/tests/`, then run `python -m unittest discover -s tests -t tests -q`.

Baseline original F11 coordinator SHA-256: `9aeaadfd6da5c50bbfedb30a8219a845cf0d7a7447ba46f2155d18a580b41eba`.
After patch SHA-256: `33ee3a8b2e9527506aeb637d8b5326f5cc09ebdf199bf99fa77026c2d9582a51`.

Linux CPython 3.13: new tests against F11 RED (3 failures, 6 errors; some reflect missing new API); on F12 **162/162 PASS**, with original F10/F11 tests retained. `git apply --check` and bytewise patch application passed. Full local evidence bundle `Ario_F12_Independent_Review_2026-11-19.zip` is held in the conversation only, **not** published in this GitHub PR. GitHub-hosted CI and Windows have **not yet been checked**.

Observations on `inspect` are local and at-read-time only, not immutable. DB schema v9 refuses old v8 state, with **no migration**. A second owner-controlled DB table detects single-column drift but not coordinated tampering of both tables. After-read deletion and full DB rollback remain out of scope. Filesystem and SQLite aren't one atomic transaction. No native merge, signer or trust operation permitted.

Do not merge this draft, or claim independent authority from candidate-authored green tests.
