# F5 — Two real processes racing to record one uncertain recovery

Date: 2026-11-17  
Status: **LOCAL EXPERIMENT ONLY / PASS IN TESTED SCOPE / NO LIVE GITHUB MERGE**  
Baseline: `RESEARCH_ONLY / DRAFT / P0_HOLD / PRODUCTION=NO_GO / TRUST_ACTIVATION=NO_GO`

## Why this test exists

F4 introduced an explicit orphan-intent recovery action. A `threading.Lock` is process-local and cannot coordinate two interpreters. The journal also uses a durable `O_EXCL` per-sequence claim. We must falsify the assumption that two recovery processes racing on the same on-disk evidence could both record an accepted recovery or silently continue after a crash. A successful single-process retry test would **not** establish this.

## Exact tested scope

- Source: existing F4/v0.5 `r2a0.py`, **unchanged** in this v0.6 test-only change.
- Test file: `tests/test_r2a0.py`, new `TestRecoveryTwoRealProcessesV06` cases.
- Platform: CPython 3.13 / Linux, two *independent OS Python processes* launched with `subprocess.Popen`; same machine, same filesystem, same owner.
- Shared fixture: valid old journal record, one well-formed `merge_intents/<sha256>.json` marker not yet committed to the journal.
- Rendezvous: each process independently passes orphan preflight, then writes its own `*.ready` flag **just before** `EvidenceJournal.append`. Parent releases both simultaneously using durable `GO` marker. Worker processes have a mocked `gh_api` that raises on any call and even receive the `ARIO_R2A0_DISPOSABLE_MERGE_ACK` value; recovery must still never call GitHub.
- No non-test GitHub API access, no App private key, no ruleset updates, no production interaction.

## F5a — Two simultaneous adoptions

**Observed:** Exactly one process returned `APPENDED_RECOVERY_EVIDENCE_ONLY`; the other returned explicit `HOLD`. The verified journal has exactly one additional `merge-intent` record, retains the original record and marker, and the recovery inspector reports `INTENT_RECORDED_OUTCOME_UNKNOWN` with `remote_merge_retry=FORBIDDEN`.

**Interpretation:** At most one journal append was accepted in the tested same-filesystem race. This is not independently controlled custody and is not a distributed consensus or exactly-once network-effects result.

## F5b — Crash winner after durable claim

Both processes reach the same pre-append barrier. The process that successfully creates the exclusive `claims/000002.json` file terminates via real `os._exit(73)` before storing the object or index record; the competing process returns `HOLD`. The old one-line index and original record remain unchanged; the marker and orphan claim remain present. `EvidenceJournal.read()` and `inspect_merge_recovery()` both refuse integrity PASS.

**Interpretation:** In this injected window, the system **stops**, preserves the partial claim, and does not turn a crash into an authorized second append. There is deliberately no automated repair, claim deletion, or PUT retry.

## F5c — Two independent read-only inspections

Two separate processes execute the `inspect-recovery` CLI in parallel on the same orphaned evidence. Both report `HOLD_ORPHAN_INTENT`, `merge_authorization=NOT_GRANTED` and `remote_merge_retry=FORBIDDEN`. Byte-level snapshots of all evidence files before and after are identical.

## Execution summary

- Existing F4/v0.5 tests: **87/87 PASS** locally.
- New cases F5a/F5b/F5c: **3/3 PASS** locally.
- Full v0.6 suite: **90/90 PASS** locally.
- Additional stress: **10 synchronized pairs = 20 process-race runs PASS** (F5a+F5b repeated 10 times).
- No live native GitHub Sc1/Sc2/Sk/Sn/Sc3/Sc4/Se1 executions in this experiment.

Run locally:

```bash
python -m unittest discover -s tests -p 'test*.py' -q
python -m unittest discover -s tests -p 'test*.py' -k TestRecoveryTwoRealProcessesV06 -v
```

## Claims we do NOT make

- Multi-host, multi-filesystem, Windows semantics, real power-loss durability, separate admin/key custody, independent human review, or end-to-end exactly-once GitHub Check or merge side effects.
- The recovery routine can never access a network under arbitrary runtime compromise; the test mocks `gh_api` only, and static code review remains necessary.
- A successful test against candidate-authored tests constitutes independent admission evidence.

## Next falsifiers

1. Hosted Linux **and Windows** execution of the exact PR HEAD (advisory CI, not independent evidence).
2. Crash after index append while second process is already waiting, and malicious replacement of the marker during recovery (HOLD invariants).
3. Two *different* evidence directories or machines sharing one logical intent: local O_EXCL is **not a global lock**. Do not claim this is solved.
4. Native R2a-0 review/merge race cases require dedicated test App and disposable ruleset; still **NOT RUN**.

**Decision:** Keep Draft PR open for adversarial review. Do not merge or activate production trust.
