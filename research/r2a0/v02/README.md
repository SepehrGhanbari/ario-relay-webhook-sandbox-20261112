# Ario R2a-0 — bounded experiment execution pack

**Version:** 2026-11-17, offline hardened candidate v0.2  
**Status:** `LOCAL_TOOL_TESTS_ONLY / LIVE_R2A0_NOT_RUN / P0_HOLD`  
**Source of design:** Claude's canonical `R2A0_RESPONSE_AND_PLAN_2026-11-17_EN.md`; previous R2a is **SUPERSEDED / DO NOT IMPLEMENT**.

This pack is a **lab evidence collector and guarded merge probe**, not an independent verification gate, a GitHub App publisher, or a proof that checks cannot be forged. It does not create Pull Requests, rulesets, webhook deliveries, CodeRabbit reviews, or App Check Runs. Lab App credentials are never requested or stored here.

## Files

- `r2a0.py` — bounded GitHub readback using the local authenticated GitHub CLI; HMAC webhook receiver on **loopback**; append-only local byte journal; guarded opt-in **disposable** merge attempt, and journal verification.
- `tests/test_r2a0.py` — offline unittest suite, with mocked API and loopback HTTP (no real GitHub mutations).
- `RUNBOOK.md` — how to run Sc1, Sc2, Sk, Sn, Sc3, Sc4, Se1 and what each proves.
- `CHANGELOG_V02.md` — exact v0.2 changes and unclosed safety gaps.
- `EVIDENCE_TEMPLATE.json` — blank case report with explicit UNKNOWN defaults.
- `SOURCE_INDEX.md` — exact previous lab evidence and canonical plan references.

## Safety invariants

1. Every GitHub API path must reference **only** `SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a`.
2. No API writes except a `PUT` to that disposable repo's exact PR merge endpoint, and only after multiple additional safeguards.
3. A merge attempt requires a PR whose **base branch** starts with `experiment/r2a0-`, exact full HEAD SHA, non-draft open PR, explicit `--execute` **and** local environment acknowledgment.
4. All other operations are read-only or local evidence writes.
5. No real Ario signer key, no permanent key, no production ruleset, no actual `main` modifications.
6. Failures and missing data are UNKNOWN/HOLD, not GREEN.
7. All Check Run sources must be examined; `gh api` responses do **not** prove producer independence by themselves.

## Requirements

Python 3.10+ standard library. For live readback, install/authenticate `gh` locally (`gh auth status`). **Do not paste tokens into chat, files, or terminal logs.** The `gh` CLI uses its own existing local credentials. To run lab App scenarios, an independently arranged **synthetic** App publisher must already be available outside candidate PR execution.

## Start (no network write)

```powershell
python -m unittest discover -s tests -v
python r2a0.py verify --evidence-dir evidence
python r2a0.py snapshot --pr 14 --scenario Sc1 --stage baseline --evidence-dir evidence
```

The historical PR #14 is DRAFT and has the *old* R1d experiment base, so it is for **readback only**. For merge experiments create a **fresh** PR targeting a new branch `experiment/r2a0-<case>-<nonce>` in the **disposable** repo, never `main` or the preserved R1d branch.

**v0.2 requires a new evidence directory**, not direct reuse of a v0.1 journal. Orphan claims/objects on a crash block new writes until independent recovery review.

The CLI uses *append-only local* evidence, not a WORM ledger. Its tail can be truncated without detection absent an external anchor. It is a single-process receiver (not cross-process locking); crash recovery, power loss, and distributed exact-once are NOT established. Never present these records as independent custody.

The receiver binds only to `127.0.0.1`. It accepts GitHub-compatible HMAC payloads, but **GitHub cannot deliver directly to a private loopback address**; a separately authorized HTTPS ingress/tunnel would be needed for live webhook tests. Until then, use it for loopback HMAC tests and classify webhook coverage as **NOT TESTED LIVE**.

Refer to the runbook for the guarded native merge attempt and capture procedure.

## F4 safe recovery (2026-11-17)

Use `python r2a0.py inspect-recovery --evidence-dir DIR` for an evidence-preserving HOLD report. For **one valid orphan merge marker only**, `record-orphan --evidence-dir DIR --marker-sha256 H --ack RECORD_ORPHAN_ONLY_NO_MERGE_RETRY` explicitly appends the missing observation but never retries the native merge. `inspect-recovery --remote --marker-sha256 H` performs only a scoped GET and does not establish who merged. A recovered journal is **not** merge authorization; see `F4_SAFE_HOLD_RECOVERY_REVIEW.md`.
