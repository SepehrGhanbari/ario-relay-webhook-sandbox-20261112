# F7 — Shared local serialization prototype after F6 split-brain

Date: 2026-11-17  
Status: **RESEARCH_ONLY / DRAFT / P0_HOLD / PRODUCTION=NO_GO / TRUST_ACTIVATION=NO_GO**  
Target: disposable Ario R2a-0 evidence laboratory; **no GitHub merge, App Check publication, or production configuration changes**.

## Why F7 exists

F6 demonstrated that two roots on different filesystem mounts can both durably append *the same orphan merge-intent evidence* with locally valid hash chains. F5's `O_EXCL` protects one local journal; it is **not** a global lock. An offline comparator detected the fork, but it could not prevent two local admissions.

F7 prototypes a **single shared serialization point** for *recording evidence only*. It is not a source of approval for the GitHub merge API, a trust activation, independent signer custody, or a network quorum.

## Exact implementation

New `f7_coordinator.py` uses Python standard-library SQLite with a **preinitialized shared database file** and `BEGIN IMMEDIATE` for cross-process write serialization. A unique constraint on `(repository, PR number)` admits at most one `CLAIMED` row across compliant participants, even if HEAD SHA, base ref or scenario changes. This deliberately sacrifices availability in favor of fail-closed behavior. Uncertain/duplicate attempts return HOLD and never acquire a lease or get a silent timeout takeover.

Sequence of the *optional adapter* `adopt_with_shared_coordinator`:

1. Require explicit ACK `RECORD_ORPHAN_ONLY_NO_MERGE_RETRY` and verify exactly one intact orphan marker in the requested local root.
2. Validate marker's canonical bytes, repo allowlist, PR number, SHA, experiment-only base and scenario.
3. Atomically insert a **single** coordinator claim and an `events: CLAIMED` entry in one SQLite transaction. If coordinator is absent, invalid, busy or conflicting, refuse progress; never auto-create it.
4. Only after the durable shared claim, invoke the existing local evidence-only orphan adoption. If that succeeds, insert an additional `LOCAL_EVIDENCE_RECORDED` event in the coordinator. Both statuses remain HOLD / `remote_merge_retry=FORBIDDEN`.
5. If a crash or exception occurs **after** shared claim but before/during local journaling or second coordination write, retain the global claim indefinitely; do not silently retry, reassign, delete or retroactively fill evidence. This can cause a permanent HOLD requiring separately governed reconciliation.

This is a **one-file, one-host coordination experiment**, not distributed consensus. SQLite durability beyond a normal process crash, filesystem/VM failure, administrative DB replacement and network filesystem locking are not established. Database rows are logically insert-only via this prototype but are **not externally immutable** or independently custodied.

## Falsification results and negative controls

- F7a: **two OS processes** with separate evidence roots contest one shared SQLite database. Exactly one returns `LOCAL_RECOVERY_RECORDED_GLOBAL_CLAIM_HELD_NO_MERGE_RETRY`; the other returns `GLOBAL_INTENT_ALREADY_CLAIMED`; neither sends a GitHub request. The losing root retains its orphan evidence and remains HOLD.
- F7b: hard `os._exit(73)` after the coordinator claim and before local evidence append leaves `CLAIMED` persisted. Another participant cannot take over; both roots are still locally incomplete.
- F7c: hard `os._exit(78)` *before SQLite transaction commit* rolls the candidate row back; another worker may claim. This test only validates that transaction's pre-commit crash behavior on the lab filesystem.
- F7d: changed HEAD, scenario or base for the *same PR* cannot obtain a new claim.
- F7e: absent/empty/corrupt/locked or symlinked coordinator, invalid ACK or marker: no local adoption, HOLD.
- F7f: **two independent coordinator DB files** can both grant the same PR. The original F6 comparison detects the resulting duplicated marker. This demonstrates why using different 'shared' DBs or restored DB backups **does not solve split-brain**.
- F7g: the **legacy, ungated** `r2a0.adopt_single_orphan_intent()` still permits a second root to record the same intent *without consulting F7*. This is an intentional blocking negative control, **not fixed** by this prototype.
- F7h: simulated loss of the second coordinator write leaves one local journal complete but the global claim in `CLAIMED` only; duplicate local/global action still cannot be assumed safe.
- F7i: no state, even `LOCAL_EVIDENCE_RECORDED`, reports GitHub merge authorization.

`python -m unittest discover -s tests -p 'test*.py' -q` on CPython 3.13.5 Linux: **120 tests / 120 PASS** (98 prior F6 tests + 22 F7 tests). Cross-platform GitHub Actions results must be checked on the eventual exact PR HEAD. On Windows, tests specifically requiring `/dev/shm` are expected to skip; do not report them as Windows filesystem tests.

**No real GitHub Sc1/Sc2/Sk/Sn/Sc3/Sc4/Se1 experiment has run.** No independent human/operator custody exists. F7 still lacks a verified production enforcement integration.

## Blocking design limits and next narrow action

1. **UNGATED LEGACY PATH:** The existing `record-orphan` CLI and code path are not bound to the F7 coordinator. Until all mutation writers use one *verified* authority, F7 does **not** establish global uniqueness. Do not merge or activate.
2. **SINGLE POINT OF HOLD:** A coordinator unavailable after claiming leaves an indefinite, intentionally unresolved reservation. An operator cannot automatically reassign it; recovery must preserve both coordinator and local evidence and require a separately reviewed decision.
3. **SAME OWNER / UNVERIFIED CUSTODY:** This DB and the roots are controlled by the same actor. A database copy, rollback, compromised host or alternate coordinator can fork. A local SQLite unique index is not a distributed lock or a separate cryptographic witness.
4. **NO MERGE-TIME GATE:** The actual GitHub native merge race and review-thread behavior remain untested. This F7 module intentionally never publishes a Check Run or calls GitHub.

The smallest next review should challenge: mandatory routing for all recovery paths, real process crash windows around both coordinator commits, coordinator DB backup/rollback and identity binding, Windows file-lock behavior, and fail-closed recovery after `CLAIMED` without `LOCAL_EVIDENCE_RECORDED`. Keep F7 in the research lab until an independent reviewer verifies these specific claims.

## Source and evidence inventory

- `research/r2a0/v02/f7_coordinator.py`: SQLite coordinator and evidence-only opt-in adapter.
- `research/r2a0/v02/tests/test_f7_coordinator.py`: subprocess/SQLite fault and bypass tests.
- `research/r2a0/v02/F7_SHARED_COORDINATOR_REVIEW.md`: this decision and limitations.
- `research/r2a0/v02/F7_LOCAL_TEST_RECORD.md`: byte hashes and local runner details.

DRAFT / DO NOT MERGE. No edits to `SepehrGhanbari/Ario`, #133/#151, permanent keys, signer, Genesis, trust activation, or production rulesets.
