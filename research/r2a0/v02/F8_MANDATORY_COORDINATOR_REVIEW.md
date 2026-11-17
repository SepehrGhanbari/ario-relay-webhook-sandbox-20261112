# F8 — Require a shared coordinator for all SUPPORTED orphan-recovery entry points

**Date:** 2026-11-17. **Status:** `RESEARCH_ONLY / DRAFT / P0_HOLD / LIVE_R2A0_NOT_RUN / PRODUCTION=NO_GO / TRUST_ACTIVATION=NO_GO`.

## Claim scope

**Demonstrated locally, bounded:** both public Python `r2a0.adopt_single_orphan_intent(...)` and CLI `r2a0.py record-orphan` require an explicitly supplied, preinitialized shared `f7_coordinator.SharedCoordinator`; F7's `adopt` CLI uses the same claim path. With one shared SQLite file, second public writer is refused, and no path makes a GitHub merge/Check call or returns admission success. CLI recovery returns exit 2 (`HOLD`) even when it successfully appends provenance. All existing history is kept, without automatically removing orphan or failed-claim evidence.

**NOT demonstrated:** isolation against arbitrary Python code or the same-owner admin, complete exclusion across copied/forked SQLite databases, untrusted hosts, independent custody, live GitHub ruleset behavior, a native merge-prevention guarantee, or proper D3 governance.

## Source fault — F7 (RED)

- `r2a0.adopt_single_orphan_intent(journal, marker, ack=ACK)` recorded orphan evidence with no SQLite claim.
- `python r2a0.py record-orphan ... --ack ACK` could reach that same helper without a coordinator.
- This made the F7 shared-coordinator adapter **optional**. A separately controlled root could still record the same marker, as F6's historical falsifier documented.
- Prior candidate CI passing was not evidence against this bypass.

## Minimal F8 patch (GREEN)

1. Rename the old append logic to `_append_orphan_after_claim_internal` and mark it test/internal only. It preserves F4's original validation and append semantics.
2. Public `adopt_single_orphan_intent` requires both a `SharedCoordinator` object and a `root_label`; without them it rejects before any local or remote write. All supported calls delegate to `f7_coordinator.adopt_with_shared_coordinator`.
3. Public `record-orphan` CLI requires `--db EXISTING_DB --root-label LABEL`, uses the same public Python route, and returns process code **2 / HOLD** even if local provenance was appended.
4. `f7_coordinator.adopt_with_shared_coordinator` invokes the internal append only *after* a durable shared claim. It never releases the shared claim automatically after crash or uncertain outcome.
5. The F4/F5/F6 historic tests explicitly invoke the renamed **private test fixture**, not the supported public path. Their earlier observations remain historical; those tests **must not** be cited as proving all local Python pathways are guarded.

## Local counterexample / RED→GREEN

Seven new F8 tests initially yielded **3 failures + 4 errors** on unmodified F7, with an old CLI exit 0 and public calls writing without coordination. After F8, the tests pass; one additional real two-process, two-public-CLI case makes **8 F8 tests**. Full discovery: **129/129 PASS** on the local Python 3.13/Linux runtime (candidate-authored, not independently witnessed).

Focus checks:
- Public call without DB refuses with `COORDINATOR_REQUIRED_FOR_RECOVERY` and preserves every local byte.
- Old CLI without the required DB/label exits non-zero, creates no file, and does not claim anything.
- Public Python API with shared DB records once; second distinct root returns `GLOBAL_INTENT_ALREADY_CLAIMED`.
- Two separate Python CLI processes race through a single DB, exactly one records local evidence and the other remains orphan-HOLD.
- Nonexistent DB is never auto-created. Missing/bad ACK is rejected. Both CLI paths never produce success/admission.

## STOP and remaining known P0 boundaries

- `_append_orphan_after_claim_internal` and `EvidenceJournal.append` are Python-accessible in a same-user interpreter. Renaming a function `_private` does **not** create a security boundary. An adversarial agent with arbitrary host file/code execution can bypass the router; a separate protected policy/executor is required for an enforceable guarantee. **DO NOT CLAIM `UNBYPASSABLE`**.
- Forking a SQLite coordinator into two files can still produce two locally valid claims. No cross-host consensus, external anchor or independent custody is established.
- A stale or failed coordinator DB forces HOLD; no takeover, repair, automatic lease expiry or blind retry.
- No real R2a-0 `Sc1 / Sc2 / Sk / Sn / Sc3 / Sc4 / Se1` native GitHub merge experiment was conducted.
- External review has not been completed just because candidate-authored tests pass.

**Next separate research choice:** protective boundary for the coordinator and for `merge-intent` journal writes (separate process/OS identity and immutable verifier policy); pair this with a live disposable native merge-race experiment. Do not deploy into Ario main from this patch.
