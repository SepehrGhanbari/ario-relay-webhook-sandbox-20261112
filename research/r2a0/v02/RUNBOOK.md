# R2a-0 reproducible operator runbook

## Boundaries

Disposable repo only: `SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a`. Preserve existing historic PRs #13/#14 and R1d ruleset. **Create a new base branch per case named `experiment/r2a0-<case>-<nonce>`**, with no bypass and effective required App check scoped to THAT branch, using authorized lab-only accounts. This requires configuration outside this pack; the pack neither creates nor changes rulesets.

The target branch must not be `main`. No permanent signer or Ario production trust change. A protected PR that is still Draft is not a valid native merge acceptance test. Only make it Ready in the disposable repo under the controlled experiment. Keep any actually merged result in that disposable branch and record that mutation explicitly.

## Preflight (must finish before live test)

- [ ] Identify the exact disposable PR, base, HEAD, and test-only contributor/reviewer actors.
- [ ] Save effective ruleset / branch rules API output, including `required_status_checks` with expected App ID **5747504**, `required_pull_request_reviews` and `required_conversation_resolution` where relevant. If API access to effective rules is denied: **UNKNOWN / HOLD**. Never infer it from a historical ruleset note.
- [ ] Confirm a **separately held synthetic App publisher** works for the new PR/HEAD without exposing its credentials to PR-controlled jobs. Historic R1i one-shot publisher was hard-coded to PR #14 and cannot simply be reused for a new PR.
- [ ] Record evaluator source SHA/digest and policy version; PR-authored tests are not independent evidence.
- [ ] For webhook tests, provide an authorized HTTPS ingress to a secured lab-only receiver; current `r2a0.py listen` is loopback-only, and HMAC signature verification must be active. Journal commit+fsync must precede 2XX. Do not expose this simple receiver directly to the Internet.
- [ ] Record `coverage_start`, a first API snapshot, and an explicit **no-completeness-claim** notice.
- [ ] Confirm all API writes are synthetic and limited to the disposable branch. Stop on any ambiguity.

## Every case: common readback commands

Run from this pack's directory (PowerShell syntax):

```powershell
python r2a0.py snapshot --pr <PR_NUMBER> --scenario Sc1 --stage baseline --evidence-dir evidence
python r2a0.py verify --evidence-dir evidence
```

Change `Sc1` and `baseline` to the stage listed in the scenario below. The snapshot stores PR HEAD/base, ALL accessible Check Runs (`filter=all`), review comments, issue comments, reviews, effective rules and combined status. It deliberately marks GraphQL review-thread completeness **unknown**: collect thread IDs/states separately from GitHub UI/GraphQL and put a redacted operator export into the journal via:

```powershell
python r2a0.py record --scenario Sc3 --stage thread-open --file .\lab-thread-export.json --evidence-dir evidence
```

Do not interpret GitHub's `mergeable_state` as proof of a native protected-branch merge outcome.

## Sc1: stale success + receiver offline

1. On a **fresh lab PR**, create a genuine App `success` for the exact HEAD using the *external lab publisher*; capture `baseline`. Confirm merge eligibility/readback.
2. Stop the lab webhook receiver; post a synthetic Major finding at H (choose a comment channel deliberately not expected to cause native blocking for this control). Capture exact comment ID and timestamps from a separately held UI/API record.
3. Capture `major-created` and `receiver-stopped` states. Attempt a **real native merge** only when the lab PR base is an isolated `experiment/r2a0-*` branch. An accepted merge is a *finding*: a zero-race guarantee is falsified. Do not automatically repeat.
4. Capture `after-merge` and record exact HTTP status, source App Check Run IDs and the event capture gap. If an API POST/PUT times out, reconcile by GET only (no blind retry).

## Sc2: new failure after old success

1. Fresh PR and baseline App success as in Sc1.
2. Post synthetic Major; receiver running. Publish an authentic **failure** using the same trusted lab App under test, with evidence sequence captured.
3. Read `filter=all` Check Runs, and capture `after-failure` and HTTP status from one native merge attempt on a fresh test branch. Do not assume the later Check Run supersedes the former.
4. Record whether the failure actually caused GitHub's required condition to become unsatisfied; classify **UNKNOWN** if native outcome is unavailable.

## Sk: same App, same check name, same SHA

Use fresh PR/branch for each order. Compare (1) creating separate Check Runs success→failure, (2) failure→success, and (3) updating a single Check Run's conclusion, if supported by the lab publisher. Check GitHub's reported required-condition state **and** native merge behavior, not just `total_count`. Capture `check-sequence`. No App private key enters this pack.

## Sn: explicit TOCTOU window

Fresh PR/branch. Capture timestamps of last verified snapshot, finding creation, observable GitHub state and one exact-HEAD merge attempt. Report the observed *interval* and uncertainty due to clock offsets/network latency; do not label an unmeasured window as zero or claim atomicity.

## Sc3: unresolved review thread, author resolve, comment deletion

1. On a fresh PR with `require conversation resolution` effective, obtain a trusted App success. Create an unresolved **review thread** and capture its thread ID and state separately (GraphQL or UI).
2. Attempt native merge on isolated base, capture `thread-open` and outcome.
3. Test author resolution and deletion of the sole thread comment **on separate fresh PRs** to avoid contaminating history; capture `thread-resolved` / `thread-deleted` and native outcomes.
4. A bot top-level comment is not automatically a review thread; keep these channels separate. If the actor cannot resolve/dismiss, record NOT_RUN rather than inventing a result.

## Sc4: Request Changes + dismissal

1. On fresh PR with effective review requirement, obtain App success. Use an eligible **separate lab reviewer** to submit `REQUEST_CHANGES` (not the PR author). Capture review ID and user identity.
2. Attempt native merge; record response and current review state.
3. A lab-only user with actual authority attempts dismissal; capture who dismissed it, timestamp and review state. Retest merge only on a fresh isolated branch/PR. No administrator bypass should be used to fake a clean result.
4. If a second review actor is unavailable, classify Sc4 **NOT_RUN/UNKNOWN**.

## Se1: deliberately missing webhook

1. Record an independent synthetic Major comment creation through GitHub with receiver disconnected (or intentionally configure a lab-only delivery failure). Show the receiver journal remains empty or continuous.
2. Capture native GitHub webhook delivery status if the lab operator has the appropriate permission; a read of *current* comments cannot prove the history of a deleted event.
3. State explicitly: `LOCAL_SEQ_DETECTS_LOST_DELIVERY = FALSE`. Do NOT infer all missed deliveries are detectable. The result is a negative control, not an admission PASS.

## Guarded disposable native merge operation

Default action runs **read-only preflight** and returns `DRY_RUN`, never writes:

```powershell
python r2a0.py attempt-merge --pr <PR_NUMBER> --scenario Sc1 --base experiment/r2a0-sc1-<nonce> --expected-head <FULL_40_HEX_SHA> --evidence-dir evidence
```

**Only when a genuine native merge attempt is explicitly authorized for that isolated disposable branch**, the operator can set the local acknowledgment and supply `--execute`:

```powershell
$env:ARIO_R2A0_DISPOSABLE_MERGE_ACK='EXPLICITLY_ALLOW_LAB_MERGE'
python r2a0.py attempt-merge --pr <PR_NUMBER> --scenario Sc1 --base experiment/r2a0-sc1-<nonce> --expected-head <FULL_40_HEX_SHA> --execute --evidence-dir evidence
Remove-Item Env:ARIO_R2A0_DISPOSABLE_MERGE_ACK
```

This **can merge the disposable PR if GitHub permits it**. It changes only the test branch, but is a real mutation and must never be run against any production branch. It performs at most one PUT, archives sanitized HTTP status and outcome, and does not retry on ambiguous results. Validate the GitHub PR and new base SHA with read-only GET after any ambiguous result.

## Classification, not wishful PASS

- A stale App success allowing a real merge after an unobserved Major is **FAIL for a zero-race protection claim** and an informative measurement for Sc1.
- A native blocker refusing merge under Sc3/Sc4 is **BOUNDED PASS for that specific configuration/actor/event timing** only.
- The absence of findings from captured logs is **UNKNOWN**, not proof that no finding ever occurred.
- Report explicit `PASS`, `FAIL`, `UNKNOWN`, or `NOT_RUN` for *each* tested claim; preserve live API responses, timestamps, Check Run IDs and digests.
- Any missing required App publisher, unable-to-read ruleset, inaccessible reviewer, or unavailable HTTPS webhook receiver means the affected live scenario stays **NOT_RUN**, never PASS.
- `R2a-0 = complete` requires a saved set of exact live observations and the required scenario-specific conclusions. Passing this offline suite alone is not R2a-0 completion.

## v0.2 safety and recovery changes (2026-11-17)

Use a **new** `--evidence-dir` for v0.2. Do not migrate or delete old v0.1 evidence. v0.2 writes exclusive `claims/` files before `objects/` and `journal.jsonl`. A crash can leave an orphan claim or object; `verify` and further appends then fail closed. Preserve the directory and document recovery independently. Do **not** erase the orphan to get a green result.

When `attempt-merge --execute` is used, an exact merge intent marker under `merge_intents/` and a journal intent are written before the GitHub PUT. An ambiguous result must be reconciled read-only; the same intent must never be retried automatically. This is a lab-only defensive marker, not multi-host locking.

An empty journal now prints `NO_JOURNAL` or `EMPTY_JOURNAL`, not `PASS`. A complete REST fetch sequence prints `api_reads_complete=true` while `complete_observation=false`: review-thread and historical webhook completeness remain unproven. No command in this kit creates, updates, or signs GitHub App Check Runs.

## F4: read-only inspection and deliberately manual orphan adoption

On HOLD, **do not erase the marker or rerun `attempt-merge`**. Capture an offline copy and checksum of the directory; inspect via `inspect-recovery --evidence-dir DIR`. An orphan marker's original SHA-256 is the identifier. If and only if all original evidence other than one valid marker is intact, `record-orphan --evidence-dir DIR --marker-sha256 H --ack RECORD_ORPHAN_ONLY_NO_MERGE_RETRY --db SHARED_PREINITIALIZED_COORDINATOR.db --root-label UNIQUE_ROOT_LABEL` may append the recovered `merge-intent` event while preserving the marker; outcome remains UNKNOWN. Optional `inspect-recovery --marker-sha256 H --remote` uses a single GitHub GET and never permits a retry. Evidence directories are single-use for native merge probes. All claim/object/index corruption remains HOLD for manual forensic review; no repair or retry is authorized. See `F4_SAFE_HOLD_RECOVERY_REVIEW.md`.


## F8: mandatory coordinator for supported recovery routes (2026-11-17)

- For test/lab-only initialization (never in production): `python f7_coordinator.py init --db /lab/shared/claims.db`.
- Public supported recovery: `python r2a0.py record-orphan --evidence-dir ROOT --marker-sha256 HASH --ack RECORD_ORPHAN_ONLY_NO_MERGE_RETRY --db /lab/shared/claims.db --root-label ROOT_A`.
- The alternate F7 adapter `python f7_coordinator.py adopt ...` uses the same file and same claim rules.
- No shared DB, no recovery; a finished append is still `HOLD` (CLI exit 2). Do not retry a native merge.
- Never copy or fork the coordinator DB and claim mutual exclusion; no external custody is established. The Python internal helper is not a security boundary against arbitrary same-owner code execution.
- For exact negative tests and limitations see `F8_MANDATORY_COORDINATOR_REVIEW.md` and Trae's `F8_TRAE_INDEPENDENT_REVIEW_TASK.md`.
