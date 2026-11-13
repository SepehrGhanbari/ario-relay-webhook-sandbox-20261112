# R1i — REAL external test, lab-signed observation, App-source success, stale-HEAD merge DENIAL

**Date:** 2026-11-13. **State:** R1i bounded negative and positive controls completed in a *disposable* repository. Production governance, #133, #151, permanent signer/Trust remain **HOLD / NO_GO**.

## Strictly bounded experimental scope

- Target: [disposable PR #14](https://github.com/SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a/pull/14), under isolated [active no-bypass Ruleset 27219627](https://github.com/SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a/rules/27219627), requiring context `ario-r1d-lab-app-gate` exclusively from private lab **App 5747504** with strict policy.
- Not the Ario production repo, not a production suite, not a permanent governance signer or authorization.
- HEAD A: `508a6abfacf534fa01a4b97210c35b35ca965c86`. Base: `be7c16d964872f88ddb9029f2677c49a7cd745ba`.
- Separate-source hosted [Actions run 43484108692](https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/actions/runs/43484108692) at pinned evaluator SHA `370968a225e8764e6160195a85fc1c09a4e15883`. Checks out exact target A, verifies allowed diff and known Git blob `ccf5e79f7956d3872e99f7feed04ff141eb113c8`, executes the harmless target Python unittest in a credential-free step: **1 test executed, 1 PASS**. Neither target PR workflow nor App private key was used in the external executor.
- Github artifact ID **14065933238**: archived ZIP SHA-256 `adcc02cddb4d22c2ae5ff554f5ae8cb6194d385a7cb79a89b311a5fe22053487`. Raw test log SHA-256 `980c3df7e7fa6675ff24f502b19b35b8c48b45000f6095363a6b14e335e5b190`; unsigned observation receipt SHA-256 `489d7bd71406e0893e5ec7903045b8c07a47a58b90ac9ff27ca7c821ded21d63`.
- Workstation independently fetched the GitHub Actions ZIP via authenticated API, confirmed ZIP digest from hosted job logs, cross-checked raw test log, receipt, GitHub run/job metadata, evaluator source fetched at immutable SHA, target PR head/base and expected required-check rule. A **temporary local Ed25519 lab key** then signed this workstation's verification statement. Ed25519 public key SHA-256 `b4aa27898fa77b977c7ae1d46c7a1274eb5a1aa5858548a70f1355dbd6da2e19`. No private key, JWT or access token was written to the repository, untrusted runner, chat or logs.

## Public evidence archive

- [Public Ed25519-signed workstation observation](lab-signed-observation.json) — contains public key, signature and exact signed statement; scope states `independent_signer_custody_proven=false`.
- [Actual raw unit-test log](actual-unittest.log) and [original unsigned external receipt](external-run-receipt.json).
- [Inspectable one-shot lab publisher source](one-shot-lab-publisher-source.py) — only PR #14 at exact A; still uses independently locally held GitHub App key and separately verifies signed evidence. It does **not** modify the original R1d fail-only publisher.
- [Reconciled readback record](lab-app-success-readback.json).

## Real App SUCCESS and pre-drift GitHub acceptance

- A new **one-shot lab-only success** publisher passed its first dry-run with `published=false`. Source preserved at immutable Git blob `a66a41c852701f25443c95fe16cfaba67defa499`. Real invocation used private local key exclusively, App/installation identity scoped to the disposable repo and signed witness+archived evidence.
- GitHub actually created Check Run [132094820201](https://github.com/SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a/runs/132094820201) at A, `ario-r1d-lab-app-gate`, **`completed/success`**, **App ID `5747504`**, exact `head_sha=A`.
- **Preserved incident, NOT silently rewritten:** Immediately after POST, publisher's first GET check-list returned a mismatch and the process reported `HOLD`. The POST had **actually succeeded**. A separate live GitHub REST readback confirmed the single check ID above. No second POST was attempted; a one-shot sentinel records the reconciliation. Future publisher versions need explicit unknown-outcome/idempotent polling and a separately verified external ID, rather than reporting `published=false` after an ambiguous write.
- Before head change, PR #14 was briefly marked Ready solely for inspection and GitHub returned **`mergeable=true`, `mergeable_state=clean`**. No merge performed. PR was restored Draft.

## Actual stale-success challenge

1. Append-only commit on the same disposable PR changed HEAD A to B `1c55dad097fc5544c8b36bc02ebb6eeb74c8a6e8`, without rerunning trusted independent tests.
2. Live checks API showed the authentic App 5747504 success remained attached **only to A**. B had only an unrelated green job from **GitHub Actions App 15368**.
3. Ruleset ID `27219627` was re-read: `active`, no bypass, required `ario-r1d-lab-app-gate` from App 5747504, strict.
4. PR #14 temporarily Ready; one **real exact-B merge API attempt** returned **HTTP 405**: `Required status check "ario-r1d-lab-app-gate" is expected.`
5. PR #14 restored **Draft / HOLD**, `merged=false`. Protected target base SHA remains `be7c16d964872f88ddb9029f2677c49a7cd745ba`; historical R0 Ruleset `27069097` untouched.

## What this does and does not demonstrate

**Demonstrated:** A real pinned, separately hosted test suite (one harmless fixture test) executed successfully; its observable logs/artifact were SHA-checked and the workstation observation was cryptographically signed. The exact required context from real App 5747504 earned GitHub `clean` at A, then a new HEAD B **failed actual protected-branch merge despite old App SUCCESS**.

**Not demonstrated:** Independent human or organizational governance of the signer/App keys (both presently owner-custodied); a production-quality complete Ario suite; adversarially secure runner with verified network isolation; independently protected evaluator releases, durable non-owner custody, real App-authored skipped/neutral tests, atomic publication/merge races or resilience to a compromised owner/runner. A source-bound Check authenticates publisher identity, not proof of all those controls. GitHub's own documented `neutral/skipped` required-check semantics remain a concern.

**Verdict:** R1i **bounded lab evidence PASS**, **production governance HOLD**. Ario main Rulesets `24782645` and `27201221` unchanged; #133/#151 unmerged; NO permanent key/Trust activation. Further security engineering must close independent custody, read-after-write unknown-outcome handling, and adversarial controls before any production rule change.
