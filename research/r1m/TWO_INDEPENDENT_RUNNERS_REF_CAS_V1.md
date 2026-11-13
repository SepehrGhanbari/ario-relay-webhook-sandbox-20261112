# R1m — Real separate Linux/Windows GitHub-hosted runners, shared Git-ref create race

**Date:** 2026-11-13. **Status:** independent-host *execution* PASS within GitHub service lab; independent *custody / distributed consensus / permanent governance* remain **HOLD / NO_GO**.

## The problem (from R1k/R1l)

- R1k found that two independent local O_EXCL files could both reserve the same intent.
- R1l verified transactions in a single SQLite local store and two local HTTP servers sharing it, but independently initialized SQLite stores both reserved an identical intent (split-brain).
- R1m tests a real provider-hosted shared namespace rather than a common localhost SQLite file, using **two separate GitHub-hosted virtual machines** running different operating systems.

## Lab architecture

- **Target only:** `SepehrGhanbari/ario-relay-webhook-sandbox-20261112`, disposable branch `experiment/r1m-independent-hosts-github-ref-cas-20261113`.
- Two real GitHub Actions jobs, one Ubuntu 24.04 and one Windows 2025, each receive a separate short-lived job `GITHUB_TOKEN` with only `contents:write` explicitly granted in **this disposable repo**. This is repository-wide Contents write and NOT a ref-prefix-scoped security credential; the job source is owner-controlled.
- Each job creates an append-only **lab tag ref** to signal readiness, waits to read the other job's readiness ref, then attempts **one** `POST /repos/{repo}/git/refs` for an exactly identical per-run/per-commit claim ref (Git object SHA pinned to the source checkout).
- GitHub documents that creating refs returns **201 on creation** and **422 on validation errors or spam**. **A 422 alone does not prove that the ref already existed.** This experiment independently issues GET and checks exact ref name, SHA and object type before labeling the losing client `EXISTING_AFTER_422`. See https://docs.github.com/en/rest/git/refs.
- A second phase repeats the contest. The Linux worker deliberately discards its POST response at the application level (not a literal packet drop or network partition) and performs **GET only** to reconcile whether the target ref exists. It never resends POST. The Windows worker likewise attempts only one POST.
- A third audit job, with **contents:read only**, requires one observed `CREATED` and one observed `EXISTING_AFTER_422` in the baseline phase, then re-reads all **six** ready/claim refs at the exact SHA and checks the second phase.
- No Check Run, protected Ario Ruleset, production branch, GitHub App signing key or permanent governance credential was used. All six refs are test tags in the sandbox only.

## Evidence: first genuine two-host live run

[Hosted run 43498295064](https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/actions/runs/43498295064), source SHA `d5eecfed0cd09b5503e863bee22736b1385cd6d0`, three separate jobs, each `completed/success`:

| Job / environment | Actual observation |
| --- | --- |
| Ubuntu, job `132137081354` | 21/21 offline tests PASS; baseline **`CREATED`** (HTTP 201 + exact ref GET); second-phase **`OBSERVED_AFTER_SIMULATED_LOST_REPLY`**, with no POST retry |
| Windows, job `132137081005` | 21/21 offline tests PASS; baseline **`EXISTING_AFTER_422`** (HTTP 422 + exact matching ref GET); second-phase **`EXISTING_AFTER_422`** |
| Independent read-only audit, job `132137276378` | `R1M_LINUX_WINDOWS_TWO_JOB_AUDIT=PASS`; `R1M_BASELINE_ONE_CREATE_ONE_CONFLICT=PASS`; `R1M_ALL_SIX_REF_READBACK=PASS`; `R1M_LOST_REPLY_SIMULATED_RECONCILED=PASS`. All three jobs completed success. |

Archived run outputs (30-day action-artifact retention, not eternal independent custody):
- [Linux evidence artifact #14073560250](https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/actions/runs/43498295064/artifacts/14073560250)
- [Windows evidence artifact #14071184550](https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/actions/runs/43498295064/artifacts/14071184550)
- [Independent job audit artifact #14071209649](https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/actions/runs/43498295064/artifacts/14071209649)

Manual, separate authenticated GitHub API GET confirmed all six refs and their exact target SHA:

```text
refs/tags/r1m-lab-43498295064-a1-d5eecfed0cd0-baseline-ready-linux
refs/tags/r1m-lab-43498295064-a1-d5eecfed0cd0-baseline-ready-windows
refs/tags/r1m-lab-43498295064-a1-d5eecfed0cd0-baseline-claim
refs/tags/r1m-lab-43498295064-a1-d5eecfed0cd0-lostreply-ready-linux
refs/tags/r1m-lab-43498295064-a1-d5eecfed0cd0-lostreply-ready-windows
refs/tags/r1m-lab-43498295064-a1-d5eecfed0cd0-lostreply-claim
```

All six resolve to exact Git commit `d5eecfed0cd09b5503e863bee22736b1385cd6d0`.

## Threat model and limits

**Supported by this run:** In one real two-VM contest with separate OS runners and tokens, the GitHub-provided create-ref operation produced exactly one new shared ref for each test claim; the competing runner observed the existing ref. A simulated discarded response could be reconciled by read-only GET without another POST.

**Not established:**
1. A GitHub ref is **not** a verified independently operated database quorum, consensus transcript or provider-internal linearizability proof. A 201+422+GET field observation is bounded evidence, not a universal consistency guarantee.
2. A `contents:write` token is broad; an authorized repo actor could potentially move/delete/reforge unprotected tags. This is not immutable or independently retained evidence. No protected tag Ruleset was installed.
3. Linux and Windows jobs are distinct GitHub-hosted VMs, but **both are GitHub-managed and owner-controlled**; they are not two independently governed organizations or an independently credentialed Ario participant.
4. Discarding one HTTP response was simulated in the application after an actual POST response had been received. It is not a real network partition, remote power loss, provider outage, cross-region consensus failover, or external disaster recovery.
5. The tag ref is a **reservation experiment only**, not idempotency for GitHub `POST /check-runs` side effects. It does not authenticate the external evaluator, signed receipt, issuer custody, revocation, or end-to-end correct merge authority.
6. Evidence objects on GitHub are not proof of permanent retention, anti-deletion or independence from the operator. Research releases must be preserved in further immutable/off-site archive with governed keys.
7. No single job has `checks:write`, and the script has no Check POST code, so successful coordination is not a green security permission.

## Research conclusions, registration rules and next falsifiers

- **R1m bounded cross-host shared-ref creation:** PASS at run `43498295064`.
- **True independently controlled multi-host coordination, malicious administrator/owner, tag mutation, actual partition and credential custody:** NOT PROVEN / P0 HOLD.
- **Any permanent issuer, two-party Ario signing, #151 activation or production rule change:** NO_GO.

Further work needs an independently protected single-writer service with strongly authenticated clients (mTLS or equivalent), a durable consensus-backed/transactional store or immutable provider-backed CAS with anti-rewrite controls, signed receipts, independent credential custody, real network interruption/failover probes and a non-operator auditor. A representative false-positive for global uniqueness or a successful replay after revoked credentials is a falsifier; record it rather than reinterpreting failure as success.

**No production changes:** GitHub production `SepehrGhanbari/Ario` main, #133/#151 and active main Rulesets are out of scope; sandbox test tags only. Leave all research PRs Draft/HOLD.
