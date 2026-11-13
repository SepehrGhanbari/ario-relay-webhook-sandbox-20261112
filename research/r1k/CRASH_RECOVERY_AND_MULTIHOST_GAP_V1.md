# R1k — Real process failure, recovery, concurrent writers, and the multi-host negative control

**2026-11-13 · disposable security research · HOLD / NO_GO.** Derived from the R1j prototype at SHA `4cfd7a3b70a5575e4ba29651396c7e4e2d3d5512`. This PR contains no App token/key, no GitHub Check POST, and no production trust activation.

## Research questions, preregistered dispositions

1. If the process crashes **after** creating a durable local no-repost marker, does a restarted process refuse to create that marker again?
2. If the process dies **mid-write**, does a partial marker survive as an irrevocable local HOLD instead of being overwritten/recreated?
3. When eight separate interpreter processes contend for **the same file**, does exactly one win and seven receive `JOURNAL_EXISTS_NO_REPOST`?
4. Can six restarted processes racing after a torn marker all remain blocked?
5. **Negative control:** If two machines have separate journal directories and no shared coordinator, can each independently claim its own marker? *Expected: YES. This is a security limitation, not an acceptable production state.*

## What was actually executed

- `r1k_journal_worker.py`: standalone unprivileged process fixture. It can reserve a local file with R1j's `O_CREAT|O_EXCL`/flush/`fsync` routine, immediately terminate with `os._exit(73)`, or write a partial file after an exclusive create then `os._exit(74)`. There is no networking or Check publication code in this worker.
- `r1k_recovery.py`: read-only restart gate. Missing, empty, malformed, overlarge, symlinked, multiply linked, wrong issuer/HEAD, or otherwise contradictory markers return `UNKNOWN_HOLD` or `CONFLICT_HOLD`. A completely valid marker returns `RECOVERED_POST_OUTCOME_UNKNOWN_HOLD`, **not** permission to retry publication. Every return has `automatic_post_allowed=false`, `repeat_post_allowed=false`.
- `tests/test_r1k_faults.py`: **20** new tests, including actual subprocess termination, restart attempts, eight-process contention, six-process recovery race, and two separate journal roots both succeeding as a deliberately observed negative result.
- Existing R1j suite contributes **32** tests, making **52** per platform.

## Live hosted test evidence — no secrets

[GitHub Actions run 43493994944](https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/actions/runs/43493994944), exact tested HEAD `8b6a298376dcf749247f519637e8dd969afc796c`:

| Runner | Actual tests | Job result |
| --- | --- | --- |
| Ubuntu 24.04 | 52/52, `Ran 52 tests in 1.570s` | PASS |
| Windows 2025 | 52/52, `Ran 52 tests in 1.808s` | PASS |

The execution covers real **process abnormal exits**, not a simulated physical power cut, corrupted filesystem, network partition, or loss of a database quorum. It ran in GitHub-hosted isolated runners; this does not verify the local Windows 10 machine's App-key ACLs.

## Central finding: single-host lock is NOT multi-host idempotency

The two-disjoint-host test deliberately creates two independent filesystem journal roots and runs the identical claim operation against each. **Both succeed**. An identical file name and external ID on two hosts is **not** an atomically unique global claim. If both holders could access the App key, they could both attempt `POST /check-runs` (no real POST was made in this test). A GitHub `external_id` is not documented as a create-idempotency key.

This is an unresolved, explicit **P0 block for distributed positive Check publishing**. Reinterpreting the mock suite as proof of cross-host exclusivity would conceal a real negative result.

## Suggested next trust boundary (NOT DEPLOYED)

A dedicated, independently protected coordination service should be the sole owner of GitHub App installation-token minting and Check publishing. The PR evaluator can submit *signed, independently verifiable* test receipts but cannot publish Checks.

Proposed journal table/transaction:

```text
verified_receipt_id      stable external evidence digest
scope                    exact repo + required check + APP ID
pr_number, head_sha, base_sha
publisher_intent_key     UNIQUE (repo, app_id, check_name, external_id)
state                    CLAIMED_UNKNOWN -> OBSERVED_MATCH | HOLD_CONFLICT | HOLD_STALE
actual_github_check_id   nullable; never invented
artifact_digests         immutable reference to retained raw logs
```

- Use a truly **linearizable** conditional creation / unique constraint in one durable protected database; if the coordinator is unreachable, all publishers **HOLD**. The database must enforce exclusive writer rights and signed, immutable audit events, with off-host, independently controlled custody.
- **Create intent before POST** in a committed transaction; a process crash after the intent cannot lead to blind repeat POST. On ambiguous outcomes, only the R1j-style GET correlation can move to `OBSERVED_MATCH`. If absent, remain `CLAIMED_UNKNOWN` until separately governed remediation; no automatic second POST.
- Publisher credential is held only in the separate guarded service, never inside GitHub Actions, PR source, local test workers or this research repo.
- A compromised operator / root account / DB administrator may still override local-only controls. Independent governance authority and separate custody/attestation remain necessary.
- Avoid production authority changes until real DB concurrency/failover/crash tests, source-pinned evaluator, signatures, key revocation, and adversarial reviewer approval have passed.

## Remaining falsifiers and implementation limits

- Hard power loss and filesystem/cache flush guarantees not tested; `fsync` in one process only.
- Windows symlink and hardlink correctness tested only as runner permissions permit; local Windows 10 secrets/ACLs not inspected.
- Separate directories on two hosts prove the **absence** of a global atomic lock, not an exploit against an already protected production service.
- R1j reconciliation's network reads remain bounded and can return unknown; GitHub check listing is not a trusted transaction commit.
- App 5747504 and temporary Ed25519 lab signer remain operator-custodied. This is not the permanent two-party Ario governance-key arrangement.
- Full Ario production regression suite, App-sourced neutral/skipped threat and base/HEAD races during real merge remain open.

**Verdict:** Single-host R1k abnormal-exit/contest controls **PASS** within tested bounds; **distributed coordination negative-control demonstrates NO global exclusion**. New distributed publisher deployment = **HOLD**. Production Ario `main`, #133/#151, production Rulesets and permanent key/Trust = **NO_GO**.
