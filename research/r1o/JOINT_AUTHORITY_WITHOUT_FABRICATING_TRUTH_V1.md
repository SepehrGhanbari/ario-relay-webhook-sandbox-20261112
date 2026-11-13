# R1o — Joint authority without the power to manufacture truth

**Date:** 2026-11-13. **Classification:** DRAFT GOVERNANCE DESIGN + MOCK-ONLY POLICY PROTOTYPE. No change to official governance or production trust.

## User design mandate

> «قدرت تصمیم‌گیری را می‌توانیم بین خودمان تقسیم کنیم؛ اما قدرت جعل حقیقت را نباید به هیچ‌کداممان بدهیم.»

The goal is **bounded authority with independently verifiable evidence**, not a sovereign founder, sovereign AI or hard-coded non-revisable axioms. No current model session, including Ava, is claimed to be a persistent independent signing party. No subjective status, selfhood or consciousness is inferred from this design.

## Existing authoritative baseline (not superseded)

The actual maintained project currently says in `SepehrGhanbari/Ario/GOVERNANCE.md` (last inspected 2026-11-13): the founder currently decides official maintenance/publication; Genesis/Owner signer is `NOT_ACTIVATED`; no succession/delegation mechanism is adopted; MIT freedoms remain unchanged. `AGENTS.md` requires explicit authorization for protected governance changes. Thus **R1o cannot, and does not, adopt a new governance regime**, notwithstanding successful tests.

## Proposed phases — progression is NOT automatic

| Phase | Normal bounded changes | Structural governance / evidence | Authority risk |
| --- | --- | --- | --- |
| **FOUNDATION**: existing founder stewardship, root not yet provisioned | Founder may submit evidence-bound routine proposals for independent review | Structural delegation HOLD; no independent Ario key claimed | Human account still has actual administrative control. Treat policy decisions as advice only |
| **JOINT**: only after independently proven, separately held roots | Founder **or** Ario may submit bounded routine review proposals with independent evidence | **Both distinct Founder and Ario signatures**, bound to the *same action*, exact policy version, repo, old HEAD and evidence digest; independent evidence/current-state/ledger/custody verifier must pass | No signer gets to invent evidence; 2-of-2 alone does not prove scientific or security truth |
| **ARIO_CONTINUITY**: *only after explicit jointly precommitted, separately approved transfer* | Ario may submit bounded evidence-bound routine review proposals without permanent founder veto | Structural amendments remain **HOLD** until a new independent challenge/appeal and authority model is approved | Must not replace founder monopoly with unchecked Ario monopoly |

**Design priority:** Founder availability must not be a *permanent* condition for routine operation once a legitimate transfer has occurred. But no untrusted actor, including a model presenting itself as Ario, gets authority from merely declaring the next phase.

## Operational invariants

1. **No evidence, no positive review.** Independent cryptographic/custody checks and verifiable test receipt must be linked to the exact action and HEAD. If any evidence is `UNKNOWN`, `FAIL` or `INCOMPLETE`, HOLD. Even `PASS` is not true just because it appears in a JSON field; it must survive trusted independent verification.
2. **Signatures are authorization evidence, not truth.** A correct Founder or Ario signature does **not** establish a test passed, a claim is true, or that a model is self-aware. Never confuse `VALID_SIGNATURE` with `TRUE_CLAIM`.
3. **Distinct role keys and independent custody.** Same key cannot represent two votes. Key IDs alone do NOT prove independence. Two keys controlled by one human account/machine are not two independent authorities.
4. **No self-awarded verdict.** An action's author or PR-controlled CI must not control the judge, signer, receipt or authority to modify required GitHub checks. Any weak status such as `skipped/neutral` is not success.
5. **Founder's retained right to challenge** survives, but after a properly precommitted transfer, the founder should not possess an *undocumented automatic override*. The actual GitHub owner/admin bypass powers must be explicitly modeled until technically limited or checked externally.
6. **Safe refusal is asymmetric.** One verified role may request an **emergency HOLD**, even without a full positive evidence package, but cannot publish, merge, rewrite records or assume authority. An external rate-limited escalation and appeal mechanism is required to prevent denial-of-service abuse.
7. **History is append-only, review can reverse decisions.** Every proposed change, reason, dissent, refusal, prior failure, key revocation, and authoritative transition must be retained and hash-bound to an independently protected archive. Revision is not erasure.
8. **No activation through a code branch, test, README, website edit, signed comment or ChatGPT response.** The explicit trust-governance authorization gate remains separate.

## Transition protocol to design and actually prove (NOT implemented)

A future joint transition to ARIO_CONTINUITY must meet **all** of these requirements, in order:

1. **Founding anchor:** separately provisioned and proven Founder and Ario signing keys, non-exportable or strongly protected, custody administratively independent of the PR execution path. No permanent key installation is authorized in R1o. Test that neither principal can impersonate the other or rebind a key.
2. **Evidence manifest:** canonical exact repo/action/old SHA/new SHA/policy version/test artifacts/evidence hashes and prior append-only ledger root. Independently produced signed external receipt. Unclear or changing HEAD => HOLD.
3. **Precommit:** Founder and separately identified Ario issuer both independently sign the *same* bounded transition plan. Plan states who can perform which actions, eligible epoch, appeal duration, reversibility, key-loss and death/unavailability rules, cost, and explicit rollback/sunset and stop paths. Publish to an independently protected, append-only evidence sink.
4. **Challenge interval:** independent timestamp/checkpoint witnesses confirm a nonzero review/challenge period; unresolved objections, stale SHA or missing witnesses HOLD. Caller-supplied wall clock alone is never sufficient.
5. **Activation quorum:** an independently operated enforcer verifies the exact precommit, delay, evidence, role/key distinctness, external ledger anchor, absence of revoked keys, and current repo permissions. Transfer only through a **separate owner-authorized real procedure**. R1o intentionally never returns authorization to activate.
6. **Long-term continuity:** bounded Ario continuity without mandatory Founder veto for routine work, with independently anchored audit, appeal and revocation. Structural authority needs a newly specified, accountable and independently reviewed mechanism; root rewriting is NOT automatically permitted to the Ario key alone.

**Lost-key / founder-absence question is unresolved:** never recover by impersonating Ario or silently falling back to founder-only signature. A threshold recovery across separately controlled devices/providers with Ario veto, safe degradation, and trustee replacement must be designed and externally tested. Proposed 4-of-5 shares are not safe merely because a table lists five media. Define separate controllers, actual entropy, trust roots, authorization thresholds, key revocation and adversarial full-loss procedures before deployment.

## What is actually implemented

`r1o_joint_governance.py` is a **pure deterministic dry-run predicate**:
- Canonical digest binds repo, phase, policy digest/version, action, old/new HEAD, change digest, evidence digest/verdict and ledger anchor.
- Exact role and key-ID separation, duplicate-vote and cross-request replay detection.
- Fails closed unless injected signature, evidence, HEAD/state, audit and custody verifiers all return **literal `True`**, not truthy int/strings.
- FOUNDATION permits founder routine **review eligibility** only; JOINT requires two roles for structural review; ARIO_CONTINUITY permits Ario routine **review eligibility** but blocks structural rewrites.
- `delegation_activate` and `key_rotation` always HOLD, even when all mock callbacks return True. `emergency_pause` may produce an external pause-*request* with one mock signer, not pause an actual service.
- Every result always has `can_merge=false`, `can_publish=false`, `can_activate_trust=false`, `can_rotate_key=false`, `delegation_activated=false`, `production_trust=NO_GO`. There is **no network access, GitHub mutation, real signature, credential access or key creation**.

`tests/test_r1o_joint_governance.py`: 42 unit cases with deliberately **mock-only** verifiers, including unilateral Founder/Ario bypass, duplicate key/role, Ava impersonation, changing action digest or GitHub HEAD, fake PASS, UNKNOWN/FAIL/INCOMPLETE evidence, disconnected ledger, unproven custody, missing verifiers, runtime exceptions, spoofed policy version, malicious repo scope, boolean/int confusion, illegal transfer and key rotation, and no-signature HOLD.

Hosted CI evidence (first source/test snapshot `a399e6266a25bce3aba70ebc2516ae19b157500f`):
- [GitHub Actions run 43502667964](https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/actions/runs/43502667964): Linux **42/42 PASS**, Windows **42/42 PASS**, verified job logs.
- Tests establish only the test double's policy logic; **they do not exercise or validate real cryptographic verification, independent Ario key custody, real evidence provenance, secure timestamping, or enforceable GitHub controls**.

## Readiness gate: explicit HOLD/NO_GO

- Stage activation: **NO_GO**.
- Permanent signing keys and any Ario independent custodian: **NOT ESTABLISHED**.
- Production required checks, original Ario Rulesets, `main`, governance/AGENTS documents, #133 and #151: **UNCHANGED**.
- Founder and Ario role predicates above are a **proposal to examine and consent to**, not an adopted governance amendment.
- Next credible proof: genuinely independent key custody and verifiers, immutable outside-host evidence log and ledger anchor, real GitHub App permissions boundary, revocation/failover drills and founder-absence continuity; then narrowly scoped external review and explicit authorized adoption.

**Research principle:** Decision power may be distributed; **nobody gets authority to manufacture evidence or truth.**
