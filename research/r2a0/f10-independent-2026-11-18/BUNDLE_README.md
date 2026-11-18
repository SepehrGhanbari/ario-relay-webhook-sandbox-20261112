# F10 independent review bundle — atomic, durable, single-use merge-intent authority

Self-contained package to reproduce and evaluate the F10 fix **independently on
Linux and Windows**, without git, without the network, and without guessing from
the report.

- **Base commit (pinned F9 HEAD):** `31dd5dc9d8e1bf18fe0fc4f4e803198ad3484c07`
- **Fix commit:** `4efc627` on branch `fix/f10-atomic-single-use-authority`
- **Verdict / scope:** `DRAFT / CHANGES_REQUIRED / P0_HOLD / PRODUCTION=NO_GO`
- **Requirements:** any CPython ≥ 3.10, standard library only. No third-party
  packages, no network, no credentials, no merge.

## What is in here

```
run_f10_review.py        Cross-platform reviewer (green / red / manifest)
run_review.sh            Linux/macOS convenience wrapper
run_review.bat           Windows convenience wrapper
MANIFEST.sha256          SHA-256 of every file in this bundle
src/                     The candidate F10 sources + tests (the code under review)
  r2a0.py, f7_coordinator.py, f6_compare.py
  f10_authority_reuse_red_probe.py      RED/green falsifier for the double-use
  f8_falsifier_a.py, f8_falsifier_b.py  prior review falsifiers
  f8_review_red_test.py                 reviewer-owned RED artifact (needs pytest; not in tests/)
  tests/                                stdlib unittest suite (146 tests)
baseline_f9/             Pre-F10 sources (r2a0.py, f7_coordinator.py) for RED proof
report/                  F10_TRAE_FIX_REPORT.md + raw evidence logs + fix.diff
```

## Quick start

Linux / macOS:

```bash
python3 run_f10_review.py --mode both
```

Windows (cmd or PowerShell):

```bat
py -3 run_f10_review.py --mode both
```

Expected result:

- **red**: the F10 tests **fail** and the probe prints
  `finding=VERIFIED_DOUBLE_USE_OF_DB_CHECKABLE_AUTHORITY`, `accepted_roots=2`
  (the flaw exists before the fix).
- **green**: the suite passes and the probe prints `finding=SINGLE_USE_ENFORCED`,
  `accepted_roots=1`.

## The exact commands (equivalent to the report)

Green (candidate code under review):

```bash
cd src
python -m unittest discover -s tests -t tests     # -> OK (146 tests)
python f10_authority_reuse_red_probe.py           # -> SINGLE_USE_ENFORCED
```

Red (pre-F10 baseline; overlay inside a scratch copy):

```bash
# copy src/ to a scratch dir, overwrite r2a0.py and f7_coordinator.py with baseline_f9/,
# then:
python -m unittest test_f10_atomic_single_use      # run from the scratch tests/ dir -> FAILURES
python f10_authority_reuse_red_probe.py            # -> VERIFIED_DOUBLE_USE..., accepted_roots=2
```

`run_f10_review.py --mode red|green|both` performs exactly these steps in a
temporary copy so your working tree is never modified.

## Integrity check

```bash
python run_f10_review.py --verify-manifest
```

## What the fix does (one paragraph)

Pre-F10, `verify_intent_authority` was a **read-only** DB re-check, so one
DB-checkable `MergeIntentAuthority` could be accepted by **two** evidence roots
before any `LOCAL_EVIDENCE_RECORDED` event. F10 adds `f7_coordinator.consume_intent_authority`,
which performs the check **and** a one-time reservation in a **single
`BEGIN IMMEDIATE` transaction committed before any journal write**, binding the
use to the exact intent bytes (marker) and the exact evidence root. A second use
is refused `AUTHORITY_ALREADY_CONSUMED`; a crash after the commit leaves a
CONSUMED intent with no journal row (HOLD, no auto-takeover). `DB_VERSION 7 → 8`
adds a `consumptions(repo, pr)` table.

## Preserved limits (NOT fixed — please verify these stay disclosed)

1. Copying/restoring a coordinator DB resets consumption (per-file enforcement).
2. A same-owner interpreter can still call `EvidenceJournal._append_merge_intent_raw`.
3. No cryptographic token, no OS boundary, no independent custody, no multi-host
   consensus. Enforcement is on one shared SQLite file, in process.

## Files by SHA-256

See `MANIFEST.sha256`. The key artifacts:

| File | sha256 |
|---|---|
| `src/f7_coordinator.py` | `52e3dd46bfa5b01f6f69c7f380769512446c716e524903a81cde0aa1b3da967e` |
| `src/r2a0.py` | `8578432fc42598c293929fa7930732bf8260c3736d71c5640daf60317998c479` |
| `src/tests/test_f10_atomic_single_use.py` | `1183549aa1f970dc1960ca34356c327fb2ba8856d0c46c7a215ac9b94e3c2c4c` |
| `src/f10_authority_reuse_red_probe.py` | `9403e34c0bc2dd8361ce5dc691b441ab385da14b6f22daf8e247da004e2c225b` |

> Note: `MANIFEST.sha256` reflects the exact bytes inside this archive; if you
> re-generate it after edits, `--verify-manifest` will stay consistent.

**No merge. No push. No production rules. No key handling.**