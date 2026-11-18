# F10 — Atomic, durable single-use of a merge-intent authority (Trae fix report)

**Task (source):** `ario-relay-webhook-sandbox-20261112` issue #11, comment `6959203116`
("Trae next task"):

> Compare with your local original F9 patch (not yet shared); try this counterexample
> on your own code. If present, provide F10 red/green fix requiring durable, atomic
> single-use recording at supported sink, with crash and same-label concurrent-root
> tests. Preserve DB fork, OS/same-owner and no-independent-custody limits.
> No live merge, no production rules, no key handling.

| Field | Value |
|---|---|
| Repo (local lab) | `/workspace/relay-sandbox` |
| Branch | `fix/f10-atomic-single-use-authority` |
| Base commit (pinned F9 HEAD) | `31dd5dc9d8e1bf18fe0fc4f4e803198ad3484c07` |
| Python | 3.14.8 · pytest 9.1.1 |
| Status flags | `DRAFT / CHANGES_REQUIRED / P0_HOLD / PRODUCTION=NO_GO` |
| Merge / push | **NONE** (local research branch only) |
| Network / keys / production | **NONE USED / NONE HANDLED** |

---

## 1. Finding (VERIFIED, reproduced locally)

The F9 fix made the public merge-intent sink require an evidence-bound
`MergeIntentAuthority`. But `verify_intent_authority` is a **read-only re-check**.
Nothing recorded that an authority had been *used*, and nothing bound its use to a
single evidence root. Therefore **one authority could be accepted by two independent
evidence roots**, before any `LOCAL_EVIDENCE_RECORDED` event — i.e. the public sink
was not one-time-use.

This is the counterexample the task asked to re-test on my own F9 code:
`same DB-checkable authority re-used at the public sink with SAME_LABEL across two
evidence roots`.

### 1.1 RED reproduction (on pinned F9 HEAD `31dd5dc`)

Command (F10 source temporarily set aside, i.e. worktree == F9 HEAD for the sink):

```
python f10_authority_reuse_red_probe.py
```

Result (`f10/evidence/F10_RED_on_pinned_f9_head.log`):

```json
{"accepted_roots": 2, "coordinator_events": ["CLAIMED"],
 "finding": "VERIFIED_DOUBLE_USE_OF_DB_CHECKABLE_AUTHORITY",
 "global_single_use": "NOT_ESTABLISHED",
 "network": "NOT_USED", "remote_merge_api": "NOT_CALLED",
 "outcomes": [{"accepted": true, "recorded": true, "root": "A"},
              {"accepted": true, "recorded": true, "root": "B"}]}
```

Both roots accepted the same authority and each wrote a `merge-intent` row
(`coordinator_events` shows only `CLAIMED`). The F10 contract tests are also RED at
that commit (`7 failed, 2 passed`), including the two decisive ones:

- `test_one_authority_consumed_once_two_roots_second_refused` → `AssertionError:
  PermissionError not raised` (the second root is *not* refused).
- `test_same_label_two_processes_race_only_one_consumes` → `AssertionError: 2 != 1`
  (both concurrent roots win).

---

## 2. Fix (durable, atomic, one-time consumption)

Two files changed, plus a new contract test module and the RED probe.

### 2.1 `research/r2a0/v02/f7_coordinator.py`

- `DB_VERSION 7 → 8`; new **`consumptions`** table `(repo, pr)` PK with
  `marker, root_label, evidence_root, consumed_utc`; `_connect` schema check now
  requires `{claims, events, consumptions}`.
- Refactor `_read_claim` → `_read_claim_row(db, …)` so the same read can run inside a
  write transaction.
- New **`consume_intent_authority(authority, intent_bytes, evidence_root)`**:
  - validates the authority type, re-validates the intent bytes, checks `marker` and
    `(repo, pr)` binding;
  - opens the shared DB, runs a **single `BEGIN IMMEDIATE`** transaction:
    - re-checks the claim row is durable (`AUTHORITY_NOT_DURABLE` otherwise — with an
      explicit `row is None` guard, see 2.3);
    - if a `consumptions` row for `(repo, pr)` already exists → audit
      `REFUSED_AUTHORITY_REUSE`, commit, raise
      `PermissionError("AUTHORITY_ALREADY_CONSUMED")`;
    - else insert the one-time reservation (bound to marker + `evidence_root`),
      audit `AUTHORITY_CONSUMED`, commit;
  - returns `_hold("AUTHORITY_CONSUMED_LOCAL_WRITE_PENDING", consumed=True, …)`
    **before any journal write**;
  - wraps `sqlite3.Error` as `COORDINATOR_UNAVAILABLE_OR_CORRUPT` (fail-closed).

### 2.2 `research/r2a0/v02/r2a0.py`

`EvidenceJournal.append_merge_intent` now performs, in order:

```python
verify_intent_authority(authority, data)                  # fail-fast, read-only pre-check
consume_intent_authority(authority, data, str(self.root)) # durable atomic one-time reservation
return self._append_merge_intent_raw(data, meta)
```

The reservation is committed **before** `_append_merge_intent_raw`, so the crash
window is consume → (journal write), never the reverse. `_append_merge_intent_raw`
remains the documented private raw writer (see §5).

### 2.3 Incidental hardening (found while writing the test)

`verify_intent_authority` / `consume_intent_authority` called `tuple(row)` without a
`None` guard, so a forged authority pointing at a claim-less DB raised
`TypeError: 'NoneType' object is not iterable` instead of a clean refusal. Both now
guard `row is None` and raise `PermissionError("AUTHORITY_NOT_DURABLE")`.

---

## 3. GREEN evidence (on the fix)

Candidate suite (adds the F10 module; 137 → 146 tests):

```
python -m pytest -q tests/
146 passed, 18 subtests passed
```

New module `tests/test_f10_atomic_single_use.py` (9 tests, all pass):

| Test | Assertion |
|---|---|
| `test_one_authority_consumed_once_two_roots_second_refused` | 1st root records; 2nd root refused `AUTHORITY_ALREADY_CONSUMED`; consumption bound to the winning root; events `CLAIMED, AUTHORITY_CONSUMED, REFUSED_AUTHORITY_REUSE` |
| `test_fresh_authority_for_same_claim_is_still_refused` | re-minting the authority does not reset one-time use |
| `test_forged_or_mismatched_authority_is_rejected_before_any_consumption` | `AUTHORITY_NOT_DURABLE` / `INVALID_MERGE_INTENT_AUTHORITY`; consumes nothing |
| `test_all_outcomes_refuse_merge_and_claim_no_custody` | every outcome is HOLD; `merge_authorization=NOT_GRANTED`, `remote_merge_retry=FORBIDDEN`, `independent_custody=NOT_ESTABLISHED`, `multi_host_consensus=NOT_ESTABLISHED` |
| `test_consumption_is_atomic_no_row_leaks_on_refusal` | refusal inserts no second consumption row |
| `test_hard_crash_after_consume_before_journal_leaves_hold_no_takeover` | subprocess `os._exit(99)` after consume: durable `AUTHORITY_CONSUMED`, **no journal row**, root is `HOLD_ORPHAN_INTENT`, fresh authority refused (no auto-takeover) |
| `test_same_label_two_processes_race_only_one_consumes` | two OS processes, **same label**, one shared DB → exactly one accepted, one `AUTHORITY_ALREADY_CONSUMED`; one consumption row |
| `test_db_fork_resets_consumption_disclosed_limit` | **preserved limit** (see §5) |
| `test_same_owner_raw_writer_still_bypasses_disclosed_limit` | **preserved limit** (see §5) |

RED probe now closed (`f10/evidence/F10_GREEN_all_tests.log`):

```json
{"accepted_roots": 1, "coordinator_events": ["CLAIMED", "AUTHORITY_CONSUMED", "REFUSED_AUTHORITY_REUSE"],
 "finding": "SINGLE_USE_ENFORCED", "global_single_use": "ENFORCED_AT_SUPPORTED_SINK",
 "network": "NOT_USED", "remote_merge_api": "NOT_CALLED",
 "outcomes": [{"accepted": true, "recorded": true, "root": "A"},
              {"accepted": false, "refused": "AUTHORITY_ALREADY_CONSUMED", "root": "B"}]}
```

Whole directory (incl. the reviewer-owned RED artifact, expected to stay RED):

```
python -m pytest -q
2 failed, 146 passed, 18 subtests passed
```

The 2 failures are `f8_review_red_test.py` (reviewer-owned; `not in tests/`, must be
run explicitly; they `pytest.fail` by design and are not part of the candidate suite).

Three existing contract assertions were updated to the new audit order (adding the
`AUTHORITY_CONSUMED` phase), because the coordinated adopt path now consumes between
`CLAIMED` and `LOCAL_EVIDENCE_RECORDED`:
`tests/test_f7_coordinator.py` L88/L239/L250 and
`tests/test_f9_coordinated_intent_paths.py` L99.

---

## 4. Crash & concurrency semantics

- **Order is consume-then-write.** A hard crash after the consumption commit but
  before the journal write leaves the intent **CONSUMED with no journal row** →
  `HOLD_ORPHAN_INTENT`, and any retry (fresh authority included) is refused
  `AUTHORITY_ALREADY_CONSUMED`. There is **no automatic takeover/retry** and the
  reservation is never rolled back or transferred (verified by subprocess `os._exit`).
- **Same-label concurrency.** Two OS processes racing with the *same* label against one
  shared SQLite file serialize on `BEGIN IMMEDIATE`; exactly one inserts the
  reservation, the other observes it and is refused. Exactly one
  `AUTHORITY_CONSUMED` event and one consumption row result.

---

## 5. Preserved limits (NOT fixed — disclosed, and encoded as tests)

These are **deliberately preserved** so the boundary is never overstated:

1. **DB fork/copy resets consumption.** Copying/restoring the coordinator DB before a
   consumption yields a copy where the same claim is unconsumed; the fix is per
   database file only. (Encoded by `test_db_fork_resets_consumption_disclosed_limit`.)
2. **Same-owner raw writer bypass.** `EvidenceJournal._append_merge_intent_raw` is a
   documented private primitive that records a merge-intent with no authority check.
   A same-owner interpreter can call it. Not a supported entry point.
   (Encoded by `test_same_owner_raw_writer_still_bypasses_disclosed_limit`.)
3. **No cryptographic token, no OS boundary, no independent custody, no multi-host
   consensus.** Enforcement is on **one** shared SQLite file, in-process, under
   supported Python entry points only. All outcomes continue to report
   `merge_authorization=NOT_GRANTED`, `remote_merge_retry=FORBIDDEN`,
   `independent_custody=NOT_ESTABLISHED`, `multi_host_consensus=NOT_ESTABLISHED`.

---

## 6. Exact commands & artifacts

Environment: Python 3.14.8, pytest 9.1.1, Linux.

```bash
# RED on pinned F9 HEAD (worktree == 31dd5dc for the sink):
python f10_authority_reuse_red_probe.py            # -> VERIFIED_DOUBLE_USE..., accepted_roots=2
python -m pytest -q tests/test_f10_atomic_single_use.py   # -> 7 failed, 2 passed

# GREEN on the fix:
python -m pytest -q tests/                         # -> 146 passed, 18 subtests passed
python -m pytest -v tests/test_f10_atomic_single_use.py   # -> 9 passed
python f10_authority_reuse_red_probe.py            # -> SINGLE_USE_ENFORCED, accepted_roots=1
```

Evidence (`research/r2a0/v02/f10/evidence/`):

- `F10_RED_on_pinned_f9_head.log` — RED (fix set aside).
- `F10_GREEN_all_tests.log` — GREEN suite + per-test + probe JSON.
- `F10_FULL_DIR_summary.log` — whole-dir run incl. reviewer RED.
- `F10_fix.diff` — tracked source/test diff (`git diff`).

### SHA-256 of changed/added artifacts (fix applied)

| File | sha256 |
|---|---|
| `research/r2a0/v02/f7_coordinator.py` | `52e3dd46bfa5b01f6f69c7f380769512446c716e524903a81cde0aa1b3da967e` |
| `research/r2a0/v02/r2a0.py` | `8578432fc42598c293929fa7930732bf8260c3736d71c5640daf60317998c479` |
| `research/r2a0/v02/tests/test_f10_atomic_single_use.py` | `1183549aa1f970dc1960ca34356c327fb2ba8856d0c46c7a215ac9b94e3c2c4c` |
| `research/r2a0/v02/f10_authority_reuse_red_probe.py` | `9403e34c0bc2dd8361ce5dc691b441ab385da14b6f22daf8e247da004e2c225b` |

---

## 7. Residual risk / what this is NOT

- This does **not** make the merge path production-safe, does not merge, does not add
  production rules, and handles no keys.
- It fixes exactly **one** verified defect: *no durable, atomic, one-time use of a
  merge-intent authority at the supported sink*. Combined with the preserved limits in
  §5, the intended property holds only for supported entry points against one shared
  SQLite file.
- A same-owner interpreter, a copied DB, a different DB, or a different host can still
  double-use. A protected policy / external evaluator remains necessary for stronger
  guarantees.

**Status: `DRAFT / CHANGES_REQUIRED / P0_HOLD / PRODUCTION=NO_GO` — no merge.**