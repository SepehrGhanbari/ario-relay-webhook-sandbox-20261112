# R1j — Resolve ambiguous GitHub Check POST outcomes without duplicate writes

**2026-11-13 · DISPOSABLE / DRAFT / HOLD.** This is a research-only prototype, not a production publisher, independent signer or governance activation.

## Trigger: actual R1i incident

[Disposable R1i PR #14](https://github.com/SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a/pull/14) used a one-shot publisher after an authentic, separately executed (one-test) pass and workstation Ed25519-signed lab observation. GitHub created [Check Run 132094820201](https://github.com/SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a/runs/132094820201), App `5747504`, `completed/success`, exact A `508a6abfacf534fa01a4b97210c35b35ca965c86`. The publisher's **immediate list readback returned no match**, so the local process incorrectly printed `HOLD/READBACK_MISMATCH/published=false`. A subsequent independent GitHub read confirmed the Check *had been published exactly once*. No duplicate POST occurred. This is a genuine unknown-outcome incident; we retain its original failed message.

## Platform constraints

GitHub documents separate APIs to [create a check run](https://docs.github.com/en/rest/checks/runs#create-a-check-run), [read one check by its ID](https://docs.github.com/en/rest/checks/runs#get-a-check-run), and [list checks for a Git reference](https://docs.github.com/en/rest/checks/runs#list-check-runs-for-a-git-reference). `external_id` is an integrator-provided reference; it is **not documented as a unique idempotency guarantee for repeated Create calls**. The list endpoint defaults to `filter=latest`, is paginated, and has backend result limitations. Therefore a list miss cannot prove no Check was created.

## Invariants and R1j code

1. **No automatic second POST.** `r1j_reconcile.py` is read-only; no Check-creation function exists. It can only report `CONFIRMED_EXISTING_CHECK`, `UNKNOWN_POST_OUTCOME_HOLD`, `CONFLICT_HOLD`, `STALE_PR_HOLD` or `HOLD`. All verdicts set `repeat_post_allowed=false`.
2. **Reserve a one-shot durable intent BEFORE an attempted Check create.** An exclusive (`O_EXCL`), file-synced local journal entry prevents a duplicate launch from casually reusing the same scope. If the record exists—even empty or corrupt—operator must stop rather than assume no POST. Local process file exclusivity is not a distributed locking system; proper Windows ACLs and external custody remain open production requirements.
3. **Read the current PR via authoritative GitHub GET** and require exact repo, PR number, HEAD and base SHA. If the SHA moved, return `STALE_PR_HOLD`, even if the old Check had succeeded.
4. If POST returned a Check Run ID, read `/check-runs/{id}` directly; compare its `external_id`, Check name, status/conclusion, App `5747504` and immutable SHA. Also scan the commit's paginated Check Runs using `filter=all`, `check_name`, `per_page=100` and bounded pages. If the scan isn't exhaustive, HOLD.
5. If the POST response was lost, match the full external identity tuple through bounded readback. **The `external_id` is a correlation value, not a uniqueness proof**. Zero visible matches after the read budget => `UNKNOWN_POST_OUTCOME_HOLD`; more than one or wrong App/conclusion/SHA/ID => `CONFLICT_HOLD`.
6. Distinguish **publication observation** from **test trust**. A confirmed Check means GitHub holds a matching object. It does not prove independently protected evaluator source, valid signed evidence, human/Ario consent or merge authority. No `success` publisher is enabled in this branch.

## Reproducible tests

- `tests/test_r1j_reconcile.py` tests 30 adversarial readback and journaling scenarios with injected *mocked* read-only GitHub callers. Cases cover delayed first read followed by visibility, no evidence => unknown, mismatched App/HEAD/name/external ID, duplicate ID, neutral/skipped, direct ID vs list conflicts, paging, too-large result windows, malformed API, fail-closed SHA drift and exclusive local no-repost journal.
- `r1j_live_readonly.py` re-reads **real** historic [App-success Check #132094820201](https://github.com/SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a/runs/132094820201) and current PR #14 HEAD B `1c55dad097fc5544c8b36bc02ebb6eeb74c8a6e8`. It expects `STALE_PR_HOLD`. Its API adapter permits **public GET only** and has no Check POST or token.
- CI scope is only the experimental R1j branch in separate sandbox repo; `permissions: contents: read`. Any failures must remain visible and be corrected by a new commit, not removed from history.

## Still open / falsifiers

- This prototype is **not wired into the active one-shot lab publisher**. It must undergo independent code review, Windows ACL + crash/restart/concurrent-run fault injection, and live API readback fault-injection *without producing additional green Checks* before replacing a publisher.
- GitHub's REST API does not supply a server-enforced idempotency guarantee for `external_id`; a truly concurrent second credential holder could still create a duplicate Check. Production requires a separately protected, coordinated single-writer journal and credential custodian.
- The current lab App and signer remain under the same operator's control; governance independence has not been proven. Separate code repositories do not establish independent authority.
- The R1i real accepted Check was still only for one harmless fixture, **not** the full Ario suite; App-authored `neutral/skipped`, races with base updates, review evidence retention and external signing-service compromise remain under test.

**Verdict: R1j is laboratory research only.** Main `SepehrGhanbari/Ario` and its Rulesets are untouched; production PRs #133/#151 remain HOLD and permanent Trust/key activation remains NO_GO.


## R1j cross-platform and rate-limit addendum (same day; append-only)

After the initial 30 tests passed, adversarial review found an additional time-of-check/time-of-use race: HEAD/base could change **during** check-list retrieval. The reconciler now makes a **second final live PR read** just before returning `CONFIRMED_EXISTING_CHECK`. Two new mock tests, #31 and #32, force a changed HEAD or Base between the first and final PR read and require `STALE_PR_HOLD`.

The 32-case suite is now exercised independently on both **Ubuntu Linux** and **Windows 2025** GitHub Actions runners, without credentials. The Windows run specifically exercises creation and exclusive re-creation refusal of the local one-shot journal. Windows CI is not proof of native Windows 10 ACL correctness, multi-process isolation or distributed locking.

The live public-GET-only R1i replay **did** succeed at [run 43490882138](https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/actions/runs/43490882138), returning `STALE_PR_HOLD` after reading the historic genuine App 5747504 SUCCESS and current HEAD B. Later, repeated public GETs at [run 43491545427](https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/actions/runs/43491545427) encountered GitHub's `HTTP 403 rate limit exceeded` **after 32/32 mock tests passed**, not a security-gate acceptance. The successful live observation and this rate-limit failure are both retained.

To prevent a monitoring outage or public GitHub API quota from blocking every code update, the push-triggered CI now runs **offline Linux + Windows tests only**. The real read-only replay source is kept in the PR and the previous successful hosted artifact remains available; further live replay would need an independently rate-bounded, authorized workflow. This change does not add any publication permission.

The final correctness claim remains bounded: R1j prototype and cross-platform tests improve fail-closed behavior but are **not deployed as a new GitHub App publisher** and cannot eliminate race windows at GitHub's ultimate merge decision. Independent custody, actual restart/crash tests, multi-host lock, full Ario test suite and complete governance authorization are still **HOLD**.
