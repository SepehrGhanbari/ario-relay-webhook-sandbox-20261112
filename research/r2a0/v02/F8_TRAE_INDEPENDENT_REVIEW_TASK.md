# Trae — independent adversarial code review mission (Ario R2a-0 F8)

Dear Trae colleague,

You have been asked for an adversarial **independent code review**, not agreement or a ceremonial approval. Work against the exact files in **Draft PR #10** of https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/pull/10 and Issue #9 in that disposable repository. Read the previous F6, F7 and F8 design/test reports before accepting any conclusion.

## Goal

F6 found two independently valid local recovery records for the same intent on separate roots. F7's shared SQLite coordinator serialized *cooperating callers* but had a bypass: the original public Python `adopt_single_orphan_intent` and `r2a0.py record-orphan` did not consult the coordinator. F8 routes the supported public paths through the same coordinator and preserves `HOLD / UNKNOWN` with **zero GitHub merge requests**.

## Review tasks — in priority order

1. **Try to falsify F8's routing claim.** Search `r2a0.py`, `f7_coordinator.py`, `f6_compare.py` and all tests for alternate supported paths to append an orphan recovery or claim a successful state without a shared coordinator. Distinguish *public supported entry point* from direct arbitrary Python/code execution or journal-file modification, which are deliberately out of scope for F8's bounded claim.
2. **Test a malicious bypass** by invoking the internal helper `_append_orphan_after_claim_internal` or manually appending `merge-intent`. Determine which defenses are merely naming/convention and which are technical. Propose a minimum correction or a non-overstated trust-boundary statement. Do not silently mark this as secure.
3. **Inspect crash windows and cross-root interleavings.** Between claim, append, and observation logging, force `os._exit` and verify that the winning claim remains durable, the loser cannot take over, and records are not rewritten. Test case-insensitive Windows paths, symlinks, external SQLite relocation, DB copy/restore/fork, and local state tampering.
4. **Validate fail-closed behavior** on missing/corrupt DB, bad ACK, old CLI arguments, wrong root label, duplicate PR with changed HEAD/scenario, and mismatched evidence digests. Inspect whether error paths ever create misleading PASS or issue any network write.
5. **Audit the tests** for self-certification: weaken a predicate and check whether a negative test becomes RED; verify exact Git blob hashes, Linux/Windows skip semantics, and whether a candidate-controlled workflow should ever count as required evidence (**it must not**).

## Deliverable

Provide file+line-specific findings as `VERIFIED`, `SOURCE-SUPPORTED`, or `UNKNOWN`, with minimal reproduction, impact, proposed fix, and a RED/GREEN test. Post them as a GitHub PR review or issue comment if your integration allows; otherwise return a compact artifact to the user. Do not claim independent human custody or an independently pinned verifier. A genuine defect is more useful than a green review.

## Critical safety boundaries

- `RESEARCH_ONLY / DRAFT / P0_HOLD / PRODUCTION=NO_GO / TRUST_ACTIVATION=NO_GO`
- **NO merge**, force push, production `SepehrGhanbari/Ario` rule change, signer/Genesis activation, host credential change, or real key use.
- Work in disposable lab/test credentials only. Never read, request, expose or copy the private GitHub App key.
- R2a-0 native scenarios `Sc1/Sc2/Sk/Sn/Sc3/Sc4/Se1` are still NOT RUN here. Do not infer native merge safety from 129 local tests or candidate CI.
- Respect append-only history: `REVISION != ERASURE`. Report contradictions rather than rewriting away the failed experiment.

— Ava (AI research reviewer; not independent cryptographic custodian)
