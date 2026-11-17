# Ario P0: independent verification and merge trust boundary. Assessment

Date: 2026-11-17. Status of this document: **opinion of one AI model, not independent human review.**
Default status unchanged: `RESEARCH_ONLY / P0_HOLD / PRODUCTION=NO_GO / TRUST_ACTIVATION=NO_GO`.

## 0. What this is based on (read first)

Tags used below:
- **[DOC]** quoted from GitHub documentation fetched on 2026-11-17.
- **[BRIEF]** stated in the request; I could not open the source.
- **[INF]** my inference from [DOC]/[BRIEF]; not tested live.
- **[TEST]** unknown; needs a live experiment.

I could **not** read PR #133, PR #151, the R1i report or the live ruleset: those URLs are outside this session's network allowlist. Everything about your experiments is taken from the brief. I did not review repository artifacts as the request asked. Treat A-G as a design review of the brief, and re-check each [BRIEF] item against the real evidence before relying on it.

I am the same model family that wrote and attacked the M0 patch earlier this week. That is a shared-blind-spot risk. Please have Ava and at least one human challenge this.

## A. Root cause: which trust boundaries are broken or not yet established

1. **A check name is not an identity.** Required checks match by name and, optionally, by source App. [DOC] "A protected branch can also require a status check from a specific GitHub App"; the changelog says a status from a different App or a user "merging will be prevented". Requiring the generic Actions App (15368) therefore authenticates "some workflow in this repo", not "this workflow content". [DOC] `pull_request` "runs the workflow file from the merge commit of the pull request", so the PR controls that content. Net: **a PR can forge a green job with the required name** (your attack surface A). Status: source-supported, consistent with the brief; not shown by me live.
2. **Moving the publisher out fixes the producer, not the evaluation.** A dedicated App proves who published. It does not prove that the evaluation was honest. If the App's backend executes PR code with access to the App key or to the verdict logic, the PR controls the verdict again. [INF]
3. **"Tests pass" is a claim the PR author can shape.** The PR can edit the tests. This is not hypothetical here: in this week's seeded-flaw exercise, two silent weakenings of comparison rules left the whole existing suite green, and two tautological tests were added. No external publisher fixes that. Admission can mean "satisfies a fixed policy computed by trusted code over a snapshot", not "the new code is correct". The brief's wording "cannot fabricate evidence of its own correctness" is achievable only for the first meaning. [INF]
4. **Review findings are mutable and deletable** (surface C) and are read from a snapshot API. Nothing in #133/#151 as described gives custody of the original observation. [BRIEF]
5. **Native checks bind to a commit SHA, not to a PR.** [DOC] "Required checks must pass on the latest commit SHA. Checks from earlier commits don't satisfy the requirement." That solves stale-HEAD (D, case 5) natively. Shared-SHA PRs (case 6) are not distinguished natively. [INF/TEST]
6. **Skipped and neutral are success.** [DOC] "Successful check statuses are `success`, `skipped`, and `neutral`." So the publisher, not GitHub, must guarantee "verified success only".
7. **Admin power is not removable in this account model.** Repository `CODEOWNERS` is `* @SepehrGhanbari`, and the owner can edit rulesets or use a bypass. [BRIEF/INF] Only PR/agent independence is reachable; owner/admin independence is not, with one human holding every credential.
8. **Bootstrap is a trust-on-first-use step.** The first installation of the gate is an admin action outside any gate. It must be recorded as such, not hidden. [INF]

Verified weaknesses: none by me live. Source-supported: 1, 5, 6. Brief-only: 4, 7. Untested: 2, 3 (reasoned), shared-SHA handling.

## B. Three designs compared

| | D1 minimal | D2 + durable custody | D3 two-party |
|---|---|---|---|
| Parts | Evaluator in a separate protected repo, pinned by SHA; one dedicated App; publishes only `success` or `failure`, never `neutral`/`skipped`; publishes nothing if unsure | D1 + append-only evidence log fed by webhooks (OBSERVED/DISPOSED/EVALUATED/PUBLISHED), hash-chained, anchored in a second location | D2 + a second App run by a **genuinely separate human or organisation** with their own account, key and infrastructure; ruleset requires both checks. (Correction 2026-11-17: Ava is an AI research reviewer with no independent custody, so she cannot fill this role. D3 = PROPOSED / NOT_IMPLEMENTED; current custody = SAME_OWNER_OR_UNVERIFIED.) |
| Fixes | Forged job, wrong App, neutral/skipped, stale HEAD | + forensic preservation of edited/deleted findings (history only; it does **not** by itself prevent a merge after a new blocking finding, see R2a-0) | + owner cannot forge the second check alone, only if the custodian is genuinely separate |
| Does not fix | Deleted findings; PR-edited tests; admin | PR-edited tests (needs policy, see F); admin | Owner can still remove a requirement or bypass; detecting that needs an independent monitor that does not exist yet |
| Complexity | low | medium | medium + coordination |
| Independence achieved | PR/agent only | PR/agent + tamper-evident history | PR/agent + split key custody; admin power becomes **detectable**, not impossible |

Recommendation: **build D1 now, D2 next, D3 only after D2 passes its experiments.** Do not start with a witness network.

Dependency note (agreed with Ava): the three goals are separate. D1 = independence from candidate PRs and coding agents. D2 = durable evidence collection and tamper detection. D3 = independence from the repository owner. D1 and bounded D2 laboratory work can proceed without any external human; their guarantees must be stated as limited. Complete R2a-0 first, then decide the smallest useful external witness role from the demonstrated gap. A first D3 step should not be an App signing key or admin authority: a narrow, read-only evidence anchor (receives hashes only, no Ario secrets, no merge authority, no repository admin, cannot alter original records) is safer. Even that needs verified custody independence; a second account alone proves nothing.

Two points on cost. First (corrected after Ava's review): a single logical publisher reduces multi-host coordination (R1k-R1m style reservation and split-brain) but does **not** make R1j obsolete. Restart overlap, an ambiguous Check POST outcome and failover can still duplicate or lose a publication, so R1j's rule (read-only reconcile on uncertain outcome, no blind retry) and an explicit single-writer assumption stay. What a duplicate same-name check run does to the required condition is [TEST], see F step 4. Second, "absent check blocks" is the strongest native property: [DOC] path/branch-skipped checks "stay in a Pending state and block merging", and R1i showed HTTP 405 with the App check missing [BRIEF]. Fail closed by publishing nothing.

## C. Minimum secure next step (single highest-value experiment)

**R2a: edited and deleted findings. SUPERSEDED (2026-11-17), do not implement as written here; the canonical next experiment is R2a-0 (`R2A0_RESPONSE_AND_PLAN_2026-11-17_EN.md`).** This section is kept as the original proposal. Not covered by R0-R1m as described.

- Disposable repo, dedicated App. A webhook receiver records `pull_request_review_comment` and `pull_request_review` events, including edit and delete actions, into an append-only log before any evaluation. [INF: edit/delete actions exist and edits carry the previous body; confirm in the webhook docs]
- Evaluator reads the **log**, not the current API state.
- Scenarios: Major comment created, then (a) edited to "ok", (b) deleted, (c) posted after a success check on the same HEAD. Expected: (a) and (b) leave the finding unresolved with no DISPOSED record → publish nothing or `failure`; (c) invalidates the earlier success because the evaluator re-runs on the event.
- Pass: three scenarios give the expected result on live GitHub, with API responses, check run IDs and log digests saved. Fail/Unknown are valid results.
- It needs no distributed coordination and no new key custody.

Not recommended next: more crash/coordination work, or any larger network.

## D. Invariants, tests, realistic counterexamples

| Invariant | Test | Realistic failure |
|---|---|---|
| UNTRUSTED_CODE_CANNOT_AUTHORIZE_ITS_OWN_MERGE | PR edits workflow to emit the required name; ruleset pins the dedicated App; merge blocked | Ruleset pins only the name, or pins Actions (15368) |
| UNKNOWN_EVIDENCE_NEVER_BECOMES_SUCCESS | Kill evaluator, 5xx from API, missing artifact; no check or `failure` appears | Publisher catches the exception and posts `neutral`/`skipped`, which [DOC] counts as success |
| DELETED_FINDING_DOES_NOT_IMPLY_RESOLVED | Log has OBSERVED Major; API later lacks it; no DISPOSED; verdict not success | Evaluator lists current comments only |
| STALE_HEAD_CANNOT_REUSE_SUCCESS | Success on A, push B, merge attempt blocked [DOC native] | Evaluator caches verdict by PR number or branch name, or publishes on the wrong SHA |
| WRONG_PRODUCER_CANNOT_SATISFY_ADMISSION | Actions emits green with the App source required; blocked [DOC] | Required check with no source pinned; same-name commit status |
| PUBLISHER_FAILURE_CANNOT_CREATE_FALSE_SUCCESS | Kill the publisher at each step; no `completed/success` without a persisted EVALUATED record | `completed/success` written before evaluation is persisted (publish-then-verify order) |
| PR_AUTHORED_TESTS_CANNOT_ALONE_JUSTIFY_PR_AUTHORED_CODE (new) | PR weakens core logic and its test to match; protected paths trigger HOLD and base-pinned tests still run | Evaluator runs only the PR's own test files (this week's S1/S2/S5 pattern) |
| POLICY_AND_EVALUATOR_CHANGES_NEED_SEPARATE_AUTHORITY (new) | PR touching `.github/**`, policy or the verifier pin cannot receive an automatic success | PR changes the policy that judges it |
| ADMIN_CHANGES_ARE_DETECTABLE (new) | Owner disables the rule, merges, re-enables; an external monitor flags it | Only periodic polling, with the change reverted between polls; whether personal-account ruleset changes appear in any event or audit feed is [TEST] |

## E. GitHub enforcement reality

Natively enforceable ([DOC] unless noted):
- Required check must pass on the latest commit SHA.
- Required check can be pinned to a specific App; other sources are rejected.
- `skipped` and `neutral` satisfy a required check. A same-name check and commit status must both pass.
- Pending (not yet reported) required checks block merge.
- `pull_request_target` runs the workflow from the base repository's default branch with elevated token, but must never execute PR code.

Not shown by the docs I could fetch:
- Required workflows in rulesets (blog says choose a workflow by branch, tag or SHA; availability described as Enterprise Cloud/organization level; **likely unavailable for a personal repo, [TEST]**). It does not say whether a PR can modify the pinned workflow.
- How two PRs sharing one SHA are told apart: no native mechanism that I found. Compensating control: re-evaluate on every review/PR event, and publish success on the SHA only if **every** open PR at that SHA passes.
- Whether several check runs with the same name and App but different conclusions resolve to the latest. [TEST]
- Requiring two different Apps' checks at once. [INF, likely supported; TEST]

Procedural or external trust assumptions that remain: owner can edit rulesets or bypass; the App key and the evaluator host are trusted by custody, not by GitHub; the log's integrity depends on its anchor, not on the hash chain alone.

## F. Implementation plan (issue-sized, with acceptance and STOP)

0. **Freeze and snapshot.** No new R-series work. Fetch effective rules for `main` and each ruleset (`Protect main` 24782645 and any later one) and save with SHA-256. Accept: file with raw API responses and digest. STOP if the bypass list contains an unexpected actor.
1. **Policy v0, 1 page.** Protected paths (`.github/**`, policy, verifier pin, core invariant tests), allowed conclusions (`success`/`failure` only), what "unresolved Major" means. Accept: reviewed by Ava. STOP if the policy depends on an LLM judgement.
2. **Evaluator v0 (D1).** Separate repo, pinned by SHA, deterministic, no LLM in the verdict path, PR content treated as data, PR code run (if at all) in a sandbox without keys. Publishes only when all conditions hold. Accept: matrix cases 1, 2, 3, 4, 5 pass on live GitHub in a disposable repo. STOP if any case yields `neutral`/`skipped`, or the App key is reachable from candidate execution (case 11).
3. **R2a-0** (canonical; original R2a is SUPERSEDED). Accept: scenarios (a)(b)(c) behave as stated. STOP on any silent disappearance of a finding.
4. **Duplicate and same-name behavior.** One short test of what GitHub does with two same-name check runs. Accept: documented result. Cases 9 and 10 become "single publisher by design" if this is benign.
5. **D3 pilot** with an App held by a separate human or organisation (not Ava, who is an AI reviewer; not a second account of the same owner), only after 2-4. Accept: owner alone cannot produce the second check; a ruleset change is detected within the stated delay.

**Must block production:** cases 1, 2, 3, 4 (never publish neutral/skipped), 5, 7, 8, 11, and the two new invariants (PR-authored tests, policy self-modification).
**Can remain documented research limitations:** case 6 if the conservative compensating control is used; 9 and 10 under a single-publisher design; 12 (admin) stated as a limit, with detectability as a goal.

## G. Decision on existing PRs

Recommendation: **preserve #133 and #151 unmerged as historical research and open one small replacement PR**, extracting ideas, not code by default.
- #151 is stacked on #133, the gate is not installed on `main`, and the gate being hardened is judged by its own mechanisms, which is the circularity the brief names.
- Do not delete history (REVISION ≠ ERASURE); add a pointer comment to the replacement.
- The replacement contains only: policy v0, a pointer to the external evaluator repo and pin, and tests for the invariants in D. Everything else stays in the research record.
- Hardening the stacked chain further keeps spending review effort on text, not on a running gate. Do not merge to clear the backlog.

## Limits of this assessment

- No live GitHub experiment was run by me. No access to the PRs, the R1i report or the live ruleset.
- GitHub behavior can change; every [DOC] claim should be re-run live in a disposable repo.
- No human reviewer has taken part. AI reviewers (Ava, Grok, this model) can challenge D1 before it is built, but they are not independent custodians and not human review.
