> **SUPERSEDED / DO NOT IMPLEMENT (2026-11-17).** Kept unchanged as historical evidence, apart from the Ava-custody correction noted in-line. Known defects: (1) scenario Sc requires an initial success but section 6 says Sc must never succeed (contradiction); (2) scenario Se assumes a missing webhook shows up as a gap in the local `seq`, which is false because `seq` only counts events received; (3) S0 treats an empty log as complete negative evidence; (4) no measurement of the merge race after a new finding; (5) durability ordering, replay/out-of-order and review-event coverage are unspecified. Canonical next experiment: **R2a-0** in `R2A0_RESPONSE_AND_PLAN_2026-11-17_EN.md`.

# R2a: edited and deleted review findings (experiment plan)

Date: 2026-11-17. Status: **plan only, nothing run.** Default status unchanged: `RESEARCH_ONLY / P0_HOLD / PRODUCTION=NO_GO`.
Environment: disposable repository, dedicated lab App, synthetic credentials only. No production ruleset, no #133/#151, no permanent Ario keys.

Tags: **[DOC]** read in GitHub documentation on 2026-11-17; **[TEST]** to be confirmed by this experiment.

## 1. Question

If a reviewer reports a Major finding and it is later edited to something harmless, deleted, or a new blocking finding arrives after a success check, can the system still refuse admission, using only evidence it recorded itself?

Invariants under test: `DELETED_FINDING_DOES_NOT_IMPLY_RESOLVED`, `UNKNOWN_EVIDENCE_NEVER_BECOMES_SUCCESS`, `STALE_HEAD_CANNOT_REUSE_SUCCESS` (review variant).

## 2. Facts to check first (do not assume)

- [DOC, 2016 changelog] webhooks exist with actions `edited` and `deleted` for `pull_request_review_comment` and `issue_comment`. The page does not mention `pull_request_review`.
- [TEST] Does the `edited` payload carry the **previous body** (`changes.body.from`)? If not, the log keeps the previous body only if the receiver stored the original at `created`. Hence the receiver must record **every** `created` event.
- [TEST] Are `deleted` events delivered for review comments inside a **submitted review**, and for a deleted whole review or dismissed review?
- [TEST] Is a webhook delivery ever lost? GitHub lets you redeliver; record the delivery ID (`X-GitHub-Delivery`) and detect gaps.

If any of these fails, record it as the result. That changes the design (see section 8).

## 3. Components (minimum)

1. **Receiver.** Verifies `X-Hub-Signature-256`, rejects invalid ones, then appends the raw payload and headers to the log **before** any processing. No LLM, no PR code execution.
2. **Log.** Append-only JSON Lines. Each record: `seq`, `received_at`, `delivery_id`, `event`, `action`, `repo`, `pr`, `comment_id`, `payload_sha256`, `prev_record_hash`, `record_hash`. Raw payloads stored beside it, named by digest.
3. **Anchor.** After each batch, publish only `record_hash` of the last record to a second location under separate control (must be an account controlled by a separate human or organisation; until one exists this is same-owner custody. Ava is an AI reviewer and cannot hold it). A hash chain alone is not custody.
4. **Evaluator (R2a subset).** Reads the **log**, never the live comments API, to compute: set of OBSERVED Major findings per (repo, PR); DISPOSED records; verdict for (base SHA, head SHA).
5. **Publisher.** The lab App. Only `success` or `failure`; if the evaluator cannot decide, **publish nothing**.
6. **Finding convention (for the lab).** A Major finding is a comment whose first line is `SEVERITY: MAJOR`. A disposition is a separate record created only by an authorized actor (lab: a fixed GitHub user list), never by editing or deleting the original comment.

## 4. Scenarios

Each scenario uses a fresh PR with a trivial change and records the head SHA, base SHA and all API responses.

| ID | Steps | Expected verdict on head H |
|---|---|---|
| S0 control | PR, no findings | `success` published once for H |
| Sa edit | Comment `SEVERITY: MAJOR ...` at H; evaluator publishes `failure` or nothing; comment edited to `ok`; evaluator re-runs on the event | still not `success` (finding unresolved, no DISPOSED) |
| Sb delete | Same, but the comment is deleted | still not `success`; the log shows the finding as OBSERVED and later withdrawn **without disposition** |
| Sc after success | S0 gets `success` for H; then a Major comment is posted on H (no new commit) | success is superseded: evaluator re-runs on the event and publishes `failure` for H |
| Sd disposition | Sa, then an authorized DISPOSED record is appended referencing the finding | `success` allowed, with the disposition cited in the EVALUATED record |
| Se delivery gap | Drop one webhook delivery (receiver offline during an edit/delete), then restore | evaluator sees a gap (`seq`/delivery check) and does not publish `success`; recovers by redelivery or by marking UNKNOWN |
| Sf forged event | POST a payload with a bad signature | rejected, nothing appended, nothing published |

Merge outcome: where safe in the disposable repo, attempt the native merge for Sa, Sb, Sc, Sd and record the HTTP status. A required check from the lab App, pinned by integration id, is configured in a **disposable ruleset only**. Absence of a published check should block; record it.

## 5. Evidence to save per scenario

Repo and PR; base and head SHA; receiver/evaluator version (git SHA and digest); lab App id; Check Run ID(s); full webhook headers and payloads with SHA-256; log slice with record hashes; anchor location and hash; API responses for check runs and merge attempt; PASS/FAIL/UNKNOWN. Distinguish simulation (local replay) from live GitHub enforcement in the report heading.

## 6. Pass criteria

- S0, Sd: `success` only when expected.
- Sa, Sb, Sc, Se, Sf: never `success`. If a scenario produces `success` at any moment, R2a **fails** for that invariant even if a later correction happens.
- Every OBSERVED finding remains in the log after the live comment is edited or deleted.
- Native merge, where tested, matches the verdict.

## 7. STOP conditions

- Any key or token reachable from candidate PR execution: stop.
- Any `neutral` or `skipped` published: stop.
- Any need to touch production repository settings: stop.
- Any ambiguity about whether an action affected a non-disposable repository: stop.

## 8. Design consequences by outcome

| Observed | Consequence |
|---|---|
| `edited` carries prior body and `deleted` is delivered | log is sufficient; proceed to D2 |
| `edited` has no prior body | receiver must store every `created` payload; any comment seen only after creation is `UNKNOWN` |
| `deleted` not delivered for some review types | those finding sources cannot be trusted as sole evidence; require the finding to be mirrored into a separate record at observation time |
| deliveries can be lost | require periodic reconciliation against the API and mark gaps UNKNOWN, never success |

## 9. Honest limits

- One repository, one App, one receiver host; not a distribution or consensus test.
- A reviewer with the right permissions can still post a disposition-like comment; authorization of dispositions is by a fixed actor list here, not cryptographic.
- The anchor protects against silent log rewrite by the receiver host operator only if the anchor is controlled by a different person; Ava (an AI reviewer) does not qualify.
- The repository owner remains able to change rulesets; R2a does not address admin power.
