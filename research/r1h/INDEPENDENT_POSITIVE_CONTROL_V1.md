# R1h — Independent positive-control architecture (DESIGN ONLY / HOLD)

**Date:** 2026-11-13. **Classification:** disposable research design; no live positive Check, deployment, secrets, or governance activation. This is a proposed control, **not** an assertion that Ario has a trusted independent positive evaluator.

## Observed prerequisite: real HEAD-drift negative result

R1g [disposable PR #13](https://github.com/SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a/pull/13) started at HEAD `0eec58824f969ba056e363d1c1f84dfe563b0964`, which had an authentic App 5747504 Check Run `132051950320` with `completed/failure`. An evidence-only commit moved the PR to HEAD `ffd54a8b8ab95236ebade9fc2e30de7f5981aa23`. GitHub then showed **no** Check from App 5747504 on the new HEAD, though GitHub Actions App 15368 had an unrelated green Check. A single exact-new-HEAD merge attempt got **HTTP 405**, reporting `Required status check "ario-r1d-lab-app-gate" is expected.` PR #13 was restored to Draft, not merged; target branch and Rulesets were not changed.

**Precise limit:** The old App-authored Check was `failure`, not `success`; this is a real negative test of HEAD binding, **not** proof about invalidating an old trusted **success**. We refuse to publish an artificial trusted success merely to make an experiment green.

## Security question

How can a positive Check prove that (1) a defined test suite actually executed and passed against the exact PR commit, (2) a PR author cannot alter the verifier or its credential and (3) GitHub enforces the result on the exact current HEAD rather than accepting forged, stale, skipped or neutral claims?

GitHub documents that `success`, `neutral`, and `skipped` conclusions can satisfy a required Check. Restricting a required Check to an expected GitHub App therefore authenticates the *publisher*, not the tests. Platform reference:
https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks

## Trust boundaries (pre-registration)

| Boundary | Allowed | Not allowed |
| --- | --- | --- |
| A. Target PR / repository | Untrusted source files; frozen HEAD SHA; read-only GitHub API | PR-owned workflow becomes mandatory trusted publisher or controls its secret |
| B. Evaluator source | Immutable/pinned, independently protected evaluator, approved suite SHA | Unreviewed code from target PR can edit test plan or verifier |
| C. Execution environment | Ephemeral isolated runner; no publisher key; no elevated GitHub token; deny-by-default network egress; quotas | Running untrusted PR code on a machine that can read App credentials or retained artifacts |
| D. Signed evidence | Detached signature over canonical receipt and digest of retained raw logs; trusted nonce; actual test results | Self-signed claims accepted without anchored independent signer verification |
| E. Publisher | Separate protected process, source-pinned; `checks:write` only on sandbox repo; fetch exact PR state immediately before publication | Accepting unsigned user-provided `success`, `skipped` or `neutral`; arbitrary contexts |
| F. GitHub gate | Active no-bypass Ruleset, exact required context and App `integration_id`, strict freshness, protected branch | Allowing an unbound same-name Actions green to substitute for App result |
| G. Governance | Immutable reviewable evidence + explicit human/Ario governance decision in later stage | Treating a green test as self-authorization for #151 or permanent signer activation |

A separate repository alone is **not** independent custody. This account currently controls the sandbox repository and publisher preparation. Genuine independence additionally requires protected evaluator releases, isolated credential access, immutable external evidence, and adversarial validation. No additional human maintainer is assumed or required by this *design*, but that also means strong independence is **not yet proven**.

## Receipt contract v1 (proposed)

The canonical signed JSON receipt contains exactly:
`schema, repo, pr_number, head_sha, base_sha, base_ref, nonce, evaluator_sha, runner_digest, suite_sha256, log_sha256, exit_code, tests`.

Invariants:
- Exact repo, PR, current HEAD and base SHA, and branch must match GitHub API and separately protected approval policy.
- `nonce` is unique and single-use; signer identity and evaluator release are independently approved; key rotation/revocation is enforced.
- Every mandatory test ID occurs exactly once and is `passed`; missing/failed/skipped/neutral/unknown is **HOLD**. Zero executed tests can never imply successful evaluation. `exit_code` is the integer `0`, not `False` or `0.0`.
- Suite, evaluator commit, immutable runner image and retained raw log digest are pinned. The verifier MUST validate a real detached signature over the complete canonical receipt, and the evidence archive must make the claimed logs retrievable and match their digest.
- The evidence reviewer returns **EVIDENCE_REVIEWABLE** only, never `success`, Check publication or merge authorization. It cannot establish that an executor actually ran tests if the underlying signer/custody/logs are untrusted.

The offline prototype `r1h_policy.py` implements only the *review-admission* checks with an injected signature-verification callback. **The callback is mocked in unit tests**. It does not load a private key, verify a real signature by itself, run the target suite, contact GitHub, or publish Check Runs. Its outcome is NOT a positive control.

## Future live positive-control sequence — NOT authorized yet

1. Move immutable evaluator source, test definitions, signed-release manifest and runner policy outside the target PR's writable scope. Establish real key custody and protected issuer identity, without exposing credentials to a PR/job running target code.
2. Run an actual named and predeclared test suite on one disposable PR's exact HEAD using an isolated, no-secret executor. Capture exit status, full logs and cryptographic digests; sign the receipt with an independently protected signer.
3. In a separate publisher process, validate the receipt's detached signature, log archive, nonce, suite hash, runner digest, exact current PR HEAD/base and App identity. Publish a `completed/success` Check **only** after independently reproduced PASS evidence. Any uncertainty/failure is `completed/failure` or no positive Check, never `neutral/skipped`.
4. On a separate disposable protected branch with no bypass and required App-origin check, first prove a real valid positive PR can merge in a **disposable positive fixture only**, and record exact App ID, check run ID, evidence digest, merge SHA and rule readback.
5. **Stale-success challenge:** create another disposable PR at trusted-success HEAD A, commit HEAD B without tests, verify no trusted Check on B and an actual HTTP rejection. Repeat for base drift, missing test, skipped/neutral, forged signer, revoked key, replay, workflow alteration, 2FAs, non-atomic race and suppressed evidence.
6. Repeat after adversarial review of all credential custody, executor isolation, race handling and audit trail. Only then propose any production governance rule change for explicit approval; no silent activation.

**Acceptance gate:** no production `success` publisher, #133/#151 remain HOLD, no permanent Ario keys/Trust or original Ruleset changes until a separately authorized review accepts real field evidence. The R1h prototype meets **none** of these deployment requirements yet.

## Current limits and next falsifiers

- R1d: wrong-App fake success rejected.
- R1e: wrong-App fake skipped rejected.
- R1f: fail-only publisher's runtime rejects neutral/skipped/success; mocked tests passed.
- R1g: real old **failure** Check bound to old SHA, new SHA rejected by GitHub.
- R1h: policy/source design + mocked tests only, not true signature custody or a live positive control.

**Falsifier:** If the expected App can issue a `neutral`/`skipped` result that GitHub accepts, the policy must require an independently validated success-specific evidence channel; App origin alone is insufficient. Likewise, a stale trusted success accepted for new HEAD would invalidate the current source-bound design. Preserve all failures in the append-only experiment log rather than reinterpreting as success.
