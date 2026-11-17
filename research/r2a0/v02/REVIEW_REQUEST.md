# R2a-0 v0.2 — review request (code is present in this PR)

**Status:** REVIEW ONLY / DRAFT / HOLD. No production Ario changes. **Do not merge to main as a security gate.**

## Why this PR exists

Previously only a ZIP and text-only issue existed, so reviewers might never inspect the actual source. This PR contains the Python tool, complete tests, canonical plan, historical superseded proposal, runbook, source map, evidence template and a *non-required* Linux/Windows candidate CI workflow.

Review the exact source rather than interpreting the reported 50/50 offline tests as native GitHub security evidence.

## Exact local byte SHA-256 (CPython 3.13/Linux, 2026-11-17)
- `r2a0.py`: `e26515125e04de35dd6261e8a33a2c2e0d09ee859c3a2e0e1e7b17982a87d706`
- `tests/test_r2a0.py`: `1bb3535b2924b9c13b4075aa028bdcb161aa15ce46bb14392acec971cfef3b05`
- Local log `LOCAL_UNIT_RESULTS.txt`: `55f6c5a8e59d71279b25a934a9612b099f743b8912800b29dd00e0780bcba69a`
- **50/50 local PASS** is a prior operator-run claim; run the tests independently, inspect full logs, and do not treat this PR's own workflow as a trust boundary.

## Scope / verified limits
- This tool DOES NOT implement a GitHub App publisher, verifier with protected authority, independent evidence custody, production-ready webhook ingress, or a GitHub ruleset.
- `snapshot()` leaves GraphQL review threads and historical delivery coverage UNKNOWN.
- `listen` is loopback only; no live GitHub webhook deliveries have been received in this lab version.
- `attempt-merge` is dry-run unless explicit flags/ack are passed, and permits only the allowlisted disposable repo and `experiment/r2a0-*` branch.
- Journal hash-chain alone is neither immutable nor independently anchored. Local concurrency tests are not network/power-loss/distributed tests.
- Sc1, Sc2, Sk, Sn, Sc3, Sc4, Se1 have **NOT** run against native GitHub in this v0.2 submission.

## Independent-review questions (please answer with file/line evidence)
1. Can `gh_api` or `authorized_merge` act outside the disposable repo/branch under adversarial input, changing HEAD/base, CLI failure, or ambiguous response?
2. Does the journal fail closed on torn records, orphan claims/payloads, collisions, symlink races, malformed JSON and duplicate delivery? Can it silently lose or rewrite evidence after crash or power loss?
3. Are resource limits, truncation, disk full, Unicode and Python 3.10–3.14 differences safe? Test fresh counterexamples, not just happy-path regressions.
4. Can a forged/modified webhook or unexpected review event be mistaken for a complete evidence history or an authorized disposition?
5. What does the code *not* observe (GraphQL review threads, dismissed review status, missing webhook deliveries, shared SHA)?
6. Can a post-success Major still slip through before a new App result? Please do not claim prevention from forensic replay.
7. Are candidate-generated tests and Actions protected from PR self-modification? (Expected: NO; candidate CI is only advisory.)

Preserve `RED/UNKNOWN/HOLD` cases, proposed fixes and new tests. Do not submit an APPROVE review on evidence of test success alone.

## Next live test
Run R2a-0 on fresh disposable case branches with no bypass; ensure the lab App check is required **from the correct App** and independently re-read effective rules. Capture exact App Check IDs, HTTP merge responses, timestamps, review/comment/thread actions, webhook IDs, source hashes and bounded limitations. No production key or ruleset changes.

Links: [tracking Issue #9](https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/issues/9) · [R1i bounded evidence](https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/blob/157ba9a131deab67f188675c06bdd81dd775e1f7/evidence/r1i/2026-11-13/R1I_FINAL_LAB_REPORT.md).

`RESEARCH_ONLY / LIVE_R2A0_NOT_RUN / P0_HOLD / PRODUCTION=NO_GO / TRUST_ACTIVATION=NO_GO`
