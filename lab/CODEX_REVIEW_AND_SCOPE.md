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

No `secrets.*`, `GH_TOKEN`, `GITHUB_TOKEN`, `HF_TOKEN`,
App private key, CODEOWNER approval, privileged API scope or CI Check
publisher token is passed to the test process. Checkout does not
persist credentials. `contents:read` is the only workflow permission.
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
