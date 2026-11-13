# R1f — Required Check conclusion semantics and fail-only publisher guard

**Research-only / HOLD / NO MERGE AUTHORITY.** 2026-11-13.

## Newly confirmed platform limitation

GitHub's official required-status-check troubleshooting guide explicitly states that successful required check conclusions include **success, skipped, neutral**:
https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks

The expected-source `integration_id` requirement binds check publisher identity, **not** an unambiguous proof that a test suite ran or passed. An accepted skipped/neutral from the expected App is therefore a real design risk, even though our earlier experiments demonstrated that same-name checks from the *wrong* App are rejected.

## Scope of this change

Only disposable publisher sandbox Draft PR #2. No production repository, ruleset, real App installation, secret, or merge is changed.

`publisher.py` retains **failure-only** semantics. New `enforce_failure_only_payload()` validates the outbound check payload before auth/token acquisition or any POST. It rejects conclusions `neutral`, `skipped`, `success`, non-completed status, wrong head SHA, wrong check name, wrong external identity binding, and missing explicit HOLD output title.

`tests/test_publisher.py` gains eight negative controls (#24-#31) that tamper with proposed payloads and assert **HOLD with only one GET and zero POST**. These tests use mocked callers; CI is not an independent verifier, and ordinary GitHub Actions green is not App 5747504 check evidence.

## Evidence and limits

- R1d: disposable PR #11, wrong App 15368's same-name success => GitHub HTTP 405 expected-App rejection.
- R1e: disposable PR #12, wrong App 15368's same-name skipped => GitHub HTTP 405 expected-App rejection.
- R1f: offline guard prevents this prototype publisher from submitting `neutral/skipped/success` even if a payload factory is accidentally modified. The trusted App's own `neutral/skipped` conclusion is **not** yet tested live.
- No independent test-evaluation success path exists here. No cryptographically protected attestation of actual test execution, immutable independent auditor deployment, atomic merge-authority proof, or real stale-HEAD acceptance/rejection is established.

## Acceptance contract for a future distinct positive-control service

1. The service runs trusted, pinned evaluator code outside any target PR and requires actual test/attestation evidence.
2. The service must never publish `neutral` or `skipped` under the required-check name; any unknown/error => `completed/failure` or no positive check.
3. It must check exact repo, PR, head and base SHA at issuance; revalidate immediately before publish and preserve an auditable immutable execution record. GitHub strict up-to-date rules remain required.
4. Any `success` must be contingent on that verified evidence and independent custody; neither a PR-owned workflow nor a manually posted same-name success is enough.
5. Test failure cases and race cases on disposable protected branches before any proposal to change Ario main governance.
6. Preserve #133 and #151 as HOLD and keep permanent signer/trust NO_GO.

This document does not assert the vulnerability is exploitable in production; it records GitHub semantics and fail-closed controls for the experimental prototype.
