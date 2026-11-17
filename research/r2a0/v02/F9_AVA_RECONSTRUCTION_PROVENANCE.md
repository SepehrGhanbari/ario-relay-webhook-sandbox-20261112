# F9 — Ava independent reconstruction (research only; DRAFT / HOLD)

**This is not Trae's original F9_fix.patch or either of Trae's local commit IDs.** The owner was unable to download Trae's complete patch and supplied an incomplete visual diff, together with Trae's report and PR body. Ava independently reconstructed the same *scoped contract goals* from the pinned F8 sources and re-executed local tests. Do not conflate the respective authors or test results.

## Exact base and provenance
- F8 base HEAD: `d84dfb1687c428dddb3bd1d4fe801b9d2159778c` on `research/r2a0-source-review-v02-20261117`.
- F8 Git blobs matched the original archived exact bytes: `r2a0.py=da9db71de7577fa9d67eaf08dd6e32e8cd200e2a`, `f7_coordinator.py=a128dae7eca09ae445246018b156fc10237f8ee1`.
- Reconstructed code Git blobs: `r2a0.py=a36b2c51fd4e97351bdc7fc0cf1f0585a676ede5`, `f7_coordinator.py=1aafe316b3c421348f2114d31c8cb4715bf00098`.
- Updated historical fixture test blob: `tests/test_r2a0.py=01baf3bfe7f18734b62250fabc10996938c76232`.
- New contract test blob: `tests/test_f9_ava_contract.py=615430928aa905a7d5e2f23d0966611dc252a6cf`.

## Actual local runs on Python 3.13 / Linux
- New F9 contract tests against **unpatched F8**: **5 FAILED, 2 PASSED** (some failures arise from missing post-F9 argparse flags, not by themselves proof of a security exploit).
- Ava reconstruction, whole suite: `PYTHONPATH=. python -m pytest -q tests/` => **136 PASSED, 18 subtests passed**.
- `git apply --check` of Ava's separately generated F9 patch against archived F8: **PASS**.
- No native GitHub API merge operation occurred. Offline F9 tests mock `authorized_merge`, with assertions for zero remote writes on refused claims.

## Changes and supported acceptance boundary
1. `r2a0.py attempt-merge --execute` now requires an existing `--db` and stable `--root-label`; durable claim is taken before local marker/journal creation or the mocked GitHub merge API path. Duplicate claim is HOLD with no new marker or network action.
2. The public `EvidenceJournal.append("merge-intent","local", ...)` now requires `merge_intent_authority`, re-checked from the named SQLite DB. A valid hash chain **is not** authority.
3. Legacy test fixtures using the raw internal primitive are updated to name `_append_merge_intent_raw` explicitly; their historical crash/fault coverage is preserved, not deleted.

## Known limitations — no security approval
- `_append_merge_intent_raw` remains reachable to **same-owner Python code**; arbitrary interpreter execution, DB modification or file manipulation is out of the current supported-contract boundary.
- Reusable, noncryptographic `MergeIntentAuthority` is **not atomic single-use at the sink**; if the same owner reuses the same root label across independent roots before a local observation, a replay/race may remain. No D1/D3 independent custody is asserted.
- Fork/copy of SQLite DB defeats global uniqueness; no network consensus, distinct OS ownership or nonrollbackable anchor exists.
- Crash after claim leaves HOLD, not auto-recovery or authorization; no blind merge retry.
- **Windows: NOT YET VERIFIED; live R2a-0 Sc1/Sc2/Sk/Sn/Sc3/Sc4/Se1: NOT RUN.** Candidate-controlled CI can test mechanics but cannot self-certify GitHub merge safety.
- Trae's separately reported local `137 passed, 18 subtests` and commits `63a008a` / `31dd5dc` have **not** been independently reproduced, published or substituted here.

**Do not merge or change rulesets, permanent keys, production signer, Genesis, trust state or Ario main.** `RESEARCH_ONLY / DRAFT / P0_HOLD / PRODUCTION=NO_GO / TRUST_ACTIVATION=NO_GO`
