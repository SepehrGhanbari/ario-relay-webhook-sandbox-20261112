# Ario R2a-0 laboratory kit — v0.2 hardening record

**Date:** 2026-11-17  
**Scope:** local evidence tooling only; **no** live GitHub R2a-0 Sc1/Sc2/Sk/Sn/Sc3/Sc4/Se1 execution.  
**Verdict:** `LOCAL_TESTS_PASS / LIVE_NOT_RUN / P0_HOLD / NO_PRODUCTION_AUTHORITY`

## Verified local changes relative to v0.1

1. Added durable, exclusive `claims/000001.json`-style per-sequence reservations before payload and index writes; a competing process cannot *simultaneously* claim the same slot. This **does not** give distributed exactly-once event processing or trusted evidence custody.
2. Journal reads now reject mismatched claim, missing/orphaned objects, missing journal with surviving claims, torn lines, duplicate JSON members, altered payload paths, symlinks and incorrect payload hashes. On ambiguous crash state, further writes HOLD; no automatic repair or history erasure.
3. A real child process calls `os._exit(73)` after durable claim creation. A fresh process observes orphaned claim and refuses to continue writing. This is **process crash**, not physical power loss.
4. GitHub PUT responses now classify a 2xx HTTP result with CLI failure or unparseable body as `unknown outcome`, not a clean refusal. A known HTTP 405 remains a negative response. No blind retries were added.
5. `attempt-merge --execute` now writes a persistent, unique local intent marker and a journal record before the guarded remote PUT. A repeated identical intent fails, even if the first result is unknown. No live PUT was performed by this change.
6. API snapshots expose `api_reads_complete` separately from `complete_observation=false`, because GraphQL review threads and missed webhook history are not included.
7. Empty or absent journal verification is explicitly `EMPTY_JOURNAL` or `NO_JOURNAL`, not `PASS`.
8. Added 15 adversarial unit tests (including crash, concurrent processes, malformed/forged evidence). Existing tests preserved with one assertion updated to the stronger fail-closed behavior.

## Important open hazards

- This is single-local-filesystem evidence, not WORM or independently anchored custody. A malicious local administrator can rewrite an unanchored tail and all corresponding claims.
- R2a-0 native GitHub merge races and review blockers remain **NOT EXECUTED**. No App Check publishing capability or public webhook ingress exists in the kit.
- A missing webhook is not detectable from a local sequence number. API polling also cannot reconstruct all deleted historical content.
- Cross-OS Windows, physical crash/fsync guarantees, multi-host failures, and repeated delivery semantic deduplication are not established.
- Updating an old v0.1 evidence directory in place is intentionally unsupported: v0.2 requires claim records. Preserve v0.1 evidence and start a separate v0.2 directory.
- No permission to change `SepehrGhanbari/Ario`, any production Ruleset, Genesis or signing key.

## Native experiment prerequisite

Run Sc1/Sc3/Sc4 only in disposable isolated **new** PRs on `experiment/r2a0-*` base branches after verifying current effective ruleset and App provenance. Never reuse old R1i PR #14 as an active merge target. All outcomes must be classified separately as OBSERVED/TESTED/UNKNOWN; no default PASS.
