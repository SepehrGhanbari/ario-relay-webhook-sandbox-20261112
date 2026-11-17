# R2a-0 F2 — no disk mutation for invalid merge arguments

**Date:** 2026-11-17  
**Classification:** VERIFIED LOCAL CONTROL-FLOW DEFECT; no production or remote merge tested.

## Red counterexample
At the CLI `attempt-merge --execute` entry point, the program formerly guarded `--base` using only `startsWith("experiment/r2a0-")`. A malformed but prefix-matching base such as `experiment/r2a0-../main` would **persist** a local `merge_intents/*.json` reservation and journal events, and only later be rejected by the stricter `authorized_merge()` check. Thus out-of-contract input mutated local state even though no GitHub API write was reached.

This is **not** evidence of an unauthorized GitHub merge. The stronger downstream guard prevented the remote API call; the problem was inconsistent validation order and polluted local evidence state.

## Negative-first reproduction
Added `TestV03MergeIntentPreflight.test_invalid_base_is_rejected_before_journal_side_effects` prior to the fix. Original test run: **56 tests / 1 failing** (invalid-branch request left files behind). Followed by the minimal patch below and repeated tests: **56/56 PASS on local Linux CPython 3.13**.

## Source change
The CLI now invokes `ensure_lab_base_ref(args.base)` **before** writing any merge intent; the PR number remains explicitly validated. The same strict rule is used at snapshot and downstream merge layers.

- Source SHA256 `c1e1d811f524bef51fcbe190044e01f854661af195845d2c5936e94d072d06d8`; Git blob `480e3aa0bdd48e97030d9620277ffdcbc05eb651`
- Tests SHA256 `584203eb669fbf8ea95ddd25be0e8aae32c185b304d95c1b73805ce6bba70f01`; Git blob `2b6ab14385b30c6051682005321e5af89e626074`

## Limits and follow-up audit questions
No live GitHub native R2a-0 scenarios or trusted App publisher tests have run. The `merge_intents` files are outside the hash-chain index's normal object/claim inventory. This mismatch merits separate review for crash recovery and complete verification; **not fixed or claimed proven in F2**.

Candidate tests are self-authored; external review remains outstanding. `RESEARCH_ONLY / DRAFT_HOLD / LIVE_R2A0_NOT_RUN`
