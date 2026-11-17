# F3 — R2a-0 merge-intent/journal crash-window custody (v0.4)

**Date:** 2026-11-17. **Status:** VERIFIED LOCAL / PATCHED / CANDIDATE-REVIEW ONLY.

**Scope:** Disposable R2a-0 evidence tool, not Ario production, GitHub Rulesets, or a signer. **Live GitHub R2a-0 scenarios NOT RUN.** No independently held witness key. DRAFT / P0_HOLD / PRODUCTION=NO_GO.

## Verified defect on v0.3

`attempt-merge --execute` reserves an exact-intent file in `merge_intents/<sha256>.json` before appending the corresponding `merge-intent` record to `journal.jsonl`.

A real child process exited using `os._exit(79)` immediately after the durable marker was written, leaving the earlier valid journal untouched. **On the v0.3 source**, the `verify` CLI exited **0** and reported `journal_integrity=PASS`, even though the merge-intent marker was present and had no journal record. This is a false *whole-workflow integrity* signal: a journal hash chain alone did not audit the separate merge-intent store. No remote merge operation was attempted.

### Local RED observations (before fix)

New tests against original v0.3 source: **64 tests, 7 FAILED**, 1 new positive test passed; regression examples:

- Crash after durable intent marker but before journal append: `verify` incorrectly PASS.
- Orphan marker followed by unrelated `journal.append`: appended successfully instead of HOLD.
- Deleting/tampering a marker after successful journal append: `read()` did not detect it.
- Mismatched marker name or a journal merge-intent record without matching marker: not detected.

### Minimal v0.4 fix

`EvidenceJournal.read()` now verifies the **entire `merge_intents/` surface** along with per-sequence claims and payloads:

1. Exact marker filename is SHA-256 of its canonical UTF-8 JSON bytes; bounded size and strict schema.
2. Intent must refer to the known disposable repo, a positive PR, a full SHA, an isolated `experiment/r2a0-*` base branch, and a known test scenario.
3. Each durable merge-intent marker must correspond byte-for-byte to exactly one `merge-intent` journal record, and each journal record must have its marker.
4. **Only while appending that exact `merge-intent` record**, an unmatched marker is temporarily accepted as a *pending reservation*; ordinary reads and appends reject it. An invalid or second pending marker remains a HOLD.
5. Symlinked marker directories/files, invalid canonical JSON, missing/modified markers, and duplicate committed intent references refuse progression.

After patch, the same regression suite plus three additional crash/webhook/symlink tests gives **67/67 PASS** on local CPython 3.13 (Linux). The post-intent child `os._exit(81)` fixture leaves a paired marker+record; an attempted reservation of the identical intent refuses a second write. A genuine webhook delivered while an orphan intent exists receives HTTP **503**, not **202** (lost delivery remains possible; see below).

## Important limitations and unproven properties

- **No independent custody:** a local operator with disk access can manipulate more than one store; a hash chain without an external anchor is not anti-tamper custody.
- **Process crash, not power failure:** `fsync()` is used, but hardware power-loss durability (especially Windows) is NOT established.
- **No multi-host consensus:** single-logical-writer assumption persists; tests do not prove distributed exactly-once.
- **No native GitHub check/merge-race evidence:** Sc1, Sc2, Sk, Sn, Sc3, Sc4, Se1 remain NOT RUN.
- **Webhook completeness not guaranteed:** fail-closed 503 after an orphan may still lose a webhook delivery; local `seq` cannot detect never-delivered events.
- **Red→green is local verification only:** even hosted CI on this PR is candidate-authored advisory CI, not an independent check or admission authority.
- **Denial-of-service tradeoff:** incomplete reservations intentionally HOLD subsequent evidence capture; recovery requires separately documented, evidence-preserving process, not automatic deletion.

## Decisions for reviewers

- Inspect the pending-marker exception in `EvidenceJournal.append`, direct `read`/`verify`, and the `attempt-merge` ordering.
- Challenge races across different process instances, Windows reparse points, directory renaming and post-`read` mutation.
- Report minimal falsifying inputs and specific lines before proposing a production gate.

**Decision:** source patch ready for review on Draft PR #10 only. `RESEARCH_ONLY / P0_HOLD / LIVE_R2A0_NOT_RUN / TRUST_ACTIVATION=NO_GO`.
