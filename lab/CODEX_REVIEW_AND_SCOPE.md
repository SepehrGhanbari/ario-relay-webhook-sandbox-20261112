# Ario Guard V2 — isolated GitHub-hosted rehearsal, 2026-11-22

**RESEARCH_ONLY / NO_TRUST / NO_SIGNER / NO_KEYS / NO_MAIN_MERGE / NO_PRODUCTION.**

## Why separate from Ario

This is a dedicated branch inside the existing user-owned **sandbox** repository.
The existing sandbox `main` and the production Ario repository are unchanged.
A push to this named sandbox branch triggers a GitHub-hosted Linux runner,
not the user's PC. The runner retrieves public Ario code at exact pinned
PR #295 SHA `14f9da37673b04f7fce90b720a94c27144c15667`
and Git tree `d5a04b86b08dae838c0ddc80d5b1d02a0d467343`.
If that branch is moved, the SHA check fails before running any Ario Python.

Checkout and setup-python receive a scoped, masked GitHub Actions token internally;
checkout removes its persisted authorization header before Ario Python runs.
No custom PAT, secret or writable token is passed to Ario Python. This does
not mean zero authenticated GitHub reads in the entire job.
The optional live probe does **unauthenticated public GET only** and
reports `UNKNOWN` whether it succeeds or fails.

## What is falsified here

- A completed matched PR run is a **reported observation**, not merge authority.
- A failed PR job cannot be masked by a green same-SHA push check.
- PR HEAD changes, incomplete check pages and deleted review comments between
  two synthetic samples cannot produce an authorized decision.
- A stable but fabricated-before-first-read review graph is **not**
  detected by two sampling passes: independent custody remains unavailable.
- The report validator rejects injected approval strings, identity drift,
  digest inconsistency and `merge_authorized=true`.
- The pinned pre-Patch-A validator is reintroduced **only inside runner scratch**;
  the current adversarial test must fail (RED), then the exact new validator
  is restored and the same test must pass (GREEN). The old and new Git
  blob IDs are verified before mutation.
- Existing source tests for the real #295 modules run again on GitHub-hosted
  Python without local user hardware.

## Critical limitations

This is *not* proof of immutable GitHub history, authenticated reviewer identity,
external witness independence, protected-main execution, or atomic final
observation-and-merge. The sandbox `main` is **not protected**; deliberately
no token is given to a PR checkout. The protected-main-only manual workflow in
Draft PR #295 is **not installed or exercised here**. Published Ario
`main`, Draft PR #295, Patch B PRs #320/#322/#324, signers, rulesets and
historical evidence are not changed.

## Codex independent review handoff

Please independently review **only** the sandbox research branch,
without editing `SepehrGhanbari/Ario` or any `main` branch:

1. Audit the workflow for privileges, branch triggers, action pinning,
   secrets propagation, credentials persistence and dangerous write endpoints.
2. Read the exact #295 Git SHA/tree pin and assess TOCTOU/supply-chain failures.
3. Verify the synthetic cases are meaningful: negative test must genuinely
   fail against the pinned *old* validator and pass against the *new* one;
   do not count expected RED as a genuine CI failure.
4. Challenge false-green situations: same-SHA push/PR mismatch, changed HEAD,
   deleted GraphQL comments, missing pages, forged diagnosis and mutable
   state before the first observation.
5. Examine which tests genuinely run versus claimed; classify
   **PASS / FAIL / UNKNOWN** per invariant with GitHub run/job/log links.
6. Report any unsafe code paths as draft review comments; **do not**
   merge, activate Trust, create a required Check, supply a GitHub token
   or publish new historical authority claims.

All results are source-bound synthetic research; the exact output should
remain `PASS_SYNTHETIC_ONLY` or fail-closed, never `AUTHORIZED`.


## Codex audit follow-up v0.2

Exact JUnit identity and expected 42 failure IDs require a reviewed SHA-256 pin; the first run with the NOT_YET_PINNED sentinel MUST fail closed and print candidate digests for independent review. After freezing IDs, rerun from this same sandbox-only branch. Main Ario and all secrets remain untouched.

The source is independently checked against the local actual Git SHA/tree in the harness (local object identity only). Previous stale report display is removed in favor of per-run-attempt exclusive report and success-only display. The original 14 groups reuse upstream fixtures and MUST NOT be represented as 14 independent mechanisms. Remaining upstream weaknesses in #295 are recorded as HOLD, not fixed by the sandbox harness. Pinned Node20 actions still emit deprecation warnings; transitive dependency closure remains mutable.


## Codex v0.2 second review: v0.3 exact-evidence-gate amendments

This revision specifically addresses the remaining three **sandbox harness**
verification gaps identified at head e78c7a7:

1. Pin ALL 197 upstream pytest IDs, not only their count, to the independently
   recomputed SHA-256 b41e2aa5ebc5056993e9efa1678725db09a51ecf33498372e81e4c247bb2e929.
   Publish sorted case IDs in the run-attempt report. A same-count ID replacement
   is a deliberate failing negative control.
2. Verify the WHOLE closed report schema (run/attempt, complete upstream
   identities and outcomes, full 14 PASS labels, both reproduced upstream
   HOLD statuses, mutation ID hashes and results, source SHA/tree and false
   authority, optional anonymous result still UNKNOWN). Negative controls
   mutate an otherwise fully valid report so the claimed dimension is actually
   responsible for rejection.
3. Verify Git object identity and reject tracked, untracked AND Git-ignored
   input files BEFORE the first upstream test; retest after validator mutation.
   Isolate pytest from auto-loaded external plugins and user site packages.
   Synthetic controls specifically introduce untracked conftest.py and
   Git-ignored pytest.ini inside an independent temporary Git repository.

These checks establish only **repository-local Git object consistency**.
Moving runner image, Python patch level, PyPI transitive dependencies,
action Node20->Node24 warnings, GitHub provider custody and all real-world
Trust/signer authority remain outside the proven boundary. The known
older-green-with-new-queued and missing-review-graph-reason findings still
exist in primary Ario #295 and are NOT modified by this sandbox experiment.


## Independent Codex v0.3 review — v0.4 final lab-shape tightening

Codex independently confirmed the real v0.3 run and all 197 original
JUnit case IDs, 71 validator case IDs, 42 RED failure IDs, 14 fixture-derived
checks and 16 prior harness controls. It identified THREE narrower potential
false-green paths; none affected the recorded v0.3 run.

- JUnit parsing is now closed to nested results or unexpected XML wrappers:
  one optional testsuites root containing one testsuite only; no nested
  testsuite/testcase, unexpected outcome or multiple outcomes per case.
  Falsification controls inject nested test suites, hidden nested test cases,
  and an unexpected XML wrapper; each must be rejected.
- The live diagnostic has TWO distinct closed shapes: an anonymous successful
  public read (all source_delivery, required_check_observation and
  execution_attestation fields mandatory, with exact safe values), or an
  unavailable anonymous read (only its four allowed fields). A missing
  success attestation, false status, wrong source delivery, omitted check
  result or false success under the unavailable shape is rejected.
  RED/GREEN summary lines must full-match the known pytest count/time
  syntax, not merely start with the right counts.
- The harness requires an exact 29-name fixed inventory, not just a
  printed number. Each original or new positive/negative case is named,
  run and compared to REQUIRED_HARNESS_CONTROLS. Deleting one fails the
  self-test. Both a valid available and an unavailable diagnostic are tested.

This is only a test-harness improvement on the same separate experimental
branch and Draft PR #20; it DOES NOT repair upstream Ario #295's two known
bugs, source custody, CI freshness after the last read, GitHub Actions
provider provenance, Node20-to-24 warnings, dependency locking or
protected-main manual execution. Neither repository main nor any key,
signer or Trust authority may be altered by this experiment.
