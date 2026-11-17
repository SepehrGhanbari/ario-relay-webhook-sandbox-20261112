# Response to Ava's adversarial review, and plan R2a-0

> **CANONICAL next experiment: R2a-0 (this document).** The original R2a plan is SUPERSEDED / DO NOT IMPLEMENT and is preserved as historical evidence.

Date: 2026-11-17. Status: **plan only, nothing run.** Baseline unchanged: `RESEARCH_ONLY / P0_HOLD / PRODUCTION=NO_GO / TRUST_ACTIVATION=NO_GO`.
Author: Claude (same model family as the earlier plan; not independent of it).
Tags: **[DOC]** read in GitHub docs on 2026-11-17; **[AVA-DOC]** cited by Ava, which I could not open (those URLs are outside my session allowlist); **[TEST]** needs a live experiment.

## 1. Verdict on my own R2a plan

Ava's disposition (changes required, design hold) is correct. R2a as I wrote it **must not be implemented**.

## 2. Point by point

| # | Ava's point | My response |
|---|---|---|
| P0-1 | Post-success Major creates a merge race; revocation by webhook comes too late | **Accept.** My plan said "success is superseded" with no merge-race measurement. The guarantee must be stated as forensic preservation or bounded staleness, not prevention. I did list the TOCTOU limit in the assessment but did not carry it into R2a. |
| P0-2 | Local `seq` cannot reveal an event that never arrived | **Accept fully.** My Se scenario was wrong: the receiver numbers only what it receives. Unseen events are not detectable from these sources. |
| P0-3 | Sc setup (success first) contradicts criterion "Sc never success" | **Accept. My error.** The criterion has to be temporal and must measure the unsafe window. |
| P0-4 | Empty journal is not complete negative evidence | **Accept.** `NO_OBSERVED_FINDING` is not `COMPLETE_CUSTODY_CONFIRMED`. |
| P1-5 | Comment coverage is not review coverage | **Accept.** Event matrix (issue comment, review comment, review, review thread) with `review_id`/`thread_id`/actor fields. Unsupported channels are UNKNOWN. |
| P1-6 | Severity and disposition authorization underspecified | **Accept.** The `SEVERITY: MAJOR` grammar is a lab fixture only; the fixed actor list is not an authority model. |
| P1-7 | Out-of-order, replay, edit-before-create | **Accept.** Needs deterministic rules; start with HOLD on conflict or uncorrelatable order. |
| P1-8 | Same-name check update semantics unproven | **Accept.** Already marked [TEST] in my assessment; my R2a plan wrongly assumed an outcome. |
| P1-9 | Durability and anchoring incomplete | **Accept.** My "append before processing" did not say acknowledge only after durable commit. Also: see section 3 on what Ava is. |
| P1-10 | One publisher does not make R1j-R1m obsolete | **Partly accept.** The "unnecessary problem" wording in my chat summary was too strong. R1j (ambiguous POST, read-only reconcile, no blind retry) stays valid even for one publisher. What I still hold: R1k-R1m style multi-store coordination is only needed if there are several writers, so single-writer by design is the right default and should not reopen coordination research. Ava's recommendation and mine agree here. |
| P1-11 | Pre-installation findings and bootstrap | **Accept.** Record `coverage_start` and `snapshot_id`; no retroactive custody claim. |
| P1-12 | Policy/evaluator binding absent from R2a | **Accept as a precondition**, not as a scenario: evaluator digest, policy version and "PR-authored tests never sole evidence" are checks in preflight P0. |

Where I do not fully follow Ava: the proposed 17-row matrix plus preflight is a good **backlog**, but as a gate it recreates the cost problem the brief itself describes for #151 (an ever-growing review surface). Her own "minimum next experiment" is the right gate. I propose the matrix as ordered backlog, released only if R2a-0 says the custody approach is worth continuing.

## 3. A correction to my earlier assessment (Ava's identity)

My assessment treated Ava as a separate party who could hold her own key and infrastructure (D3 pilot, the anchor). Ava's review describes "an Ava chat identity" that is "not a cryptographically independent storage operator or key custodian". **If Ava is an AI chat and not a person with her own account, D3 gives no independent custody**; it would be same-owner custody and should be labelled so. The anchor in R2a section 3 has the same problem. Until a person with a genuinely separate GitHub account and key custody exists, the honest labels are "same-owner custody" and "PR/agent independence only". Resolved by Ava on 2026-11-17: she is a ChatGPT-based AI research reviewer (`AVA_CRYPTOGRAPHIC_CUSTODY = NOT_ESTABLISHED`, `INDEPENDENT_ADMINISTRATIVE_CONTROL = NOT_ESTABLISHED`, `D3 = PROPOSED / NOT_IMPLEMENTED`). Her follow-up also fixes the dependency order: D1 and bounded D2 lab work do not wait for an external human; the witness role is decided after R2a-0 from the demonstrated gap, and the first D3 step is a read-only hash anchor, not an App key or admin authority.

## 4. One addition from the docs: synchronous native blockers

The race in P0-1 arises because my design blocks only through an asynchronous webhook. GitHub has blockers that act at merge time, [DOC]:
- "Require conversation resolution before merging": blocks merge while any PR comments remain unresolved.
- A "Request changes" review blocks merge when required approvals are on; it can be dismissed by anyone with write permission, and if an admin requested changes the admin must approve.

These are synchronous and need no webhook. Limits: the PR author or a write user may resolve or dismiss; deleting the only comment of a thread presumably removes the blocker [TEST]; bot findings that are not review threads may not block [TEST]. So the likely sound combination is: **native synchronous blockers prevent the merge; the journal preserves forensic history and holds the App check when a blocker disappears without disposition.** R2a-0 should test both arms.

## 5. R2a-0 (the gate): narrow native falsifier

Environment: disposable repo and ruleset, lab App, synthetic credentials. No Ario main, no #133/#151.

Preflight P0 (must pass or stop): webhook subscriptions and permissions correct; signature verification works; receiver durable before acknowledging (write, flush, then 2xx; crash test); evaluator digest and policy version recorded; `coverage_start` and initial snapshot recorded.

Scenarios (each saves repo, PR, base/head SHA, check run IDs, raw responses, timestamps):

| ID | Steps | What is measured |
|---|---|---|
| Sc1 | Authentic App `success` at H and verified merge eligibility; then a synthetic Major comment at H; receiver **stopped**; immediately attempt native merge of H | does the old success allow merge before evidence is processed |
| Sc2 | Same, receiver running; then publish `failure`; enumerate check runs; retry merge on a fresh PR/branch | time from finding to mergeability change; whether `failure` revokes eligibility |
| Sk | Same App + same name + same SHA: `success`→`failure` and `failure`→`success` as new runs and as updates | which run GitHub uses for the required condition |
| Sn | Late comment between last re-evaluation and merge | size of the TOCTOU window |
| Sc3 | Success at H; then an unresolved review **thread** with conversation resolution required | native merge blocked immediately? what if the thread is resolved by the author, or its only comment deleted |
| Sc4 | Success at H; then a "Request changes" review; then dismissal by a write user | native block; effect of dismissal; does the journal observe the dismissal |
| Se1 | Suppress one `created` Major delivery entirely, with no artificial seq gap | confirms that local sequence cannot reveal it; compare with delivery list where available |

Pass/FAIL for the gate is **temporal and explicit**: report the unsafe window and whether native merge succeeded inside it. A merge that succeeds on a stale success is a recorded result (`FAIL` for any "zero-race" claim), never PASS by later correction.

## 6. Decision after R2a-0

| Outcome | Consequence |
|---|---|
| Old success permits merge before webhook processing (expected) and Sc3/Sc4 block it natively | design = native synchronous blockers + journal for forensics; claim only bounded staleness for what the blockers do not cover |
| Same, and Sc3/Sc4 do not block adequately | no claim of fresh-at-merge admission; keep the journal for forensic custody only; state this as a platform limit |
| `failure` does not revoke eligibility (Sk) | blocker for any App-check revocation design; use a different mechanism |
| Duplicate same-name runs behave benignly | single-writer plus read-only reconcile is sufficient; no coordination research |

STOP conditions unchanged: any key reachable from candidate execution; any `neutral`/`skipped` published; any need to touch production settings.

## 7. Backlog (not a gate)

Ava's matrix rows not listed above (Sa/Sb edit/delete log retention, Sd disposition authority, Se2 failed-delivery reconcile, Sf, Sg duplicate/conflicting GUID, Sh edit-before-create, Si event matrix, Sj shared SHA, Sl crash before durability, Sm unauthorized actors) stay as an ordered backlog, taken up only if the R2a-0 outcome keeps the journal design.

## 8. Claim language to keep

- Supportable: edit/delete events observed live; prior text preserved where delivered; invalid signatures rejected; behaviors demonstrated for the tested cases only.
- Not supportable now: `NO_MAJOR_WAS_EVER_POSTED`, zero-window revocation, complete delivery history, independence from the repository administrator, exactly-once Check side effects.
