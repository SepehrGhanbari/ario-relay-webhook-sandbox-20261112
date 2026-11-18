# F10 research archive — decision and verification index

**State:** `RESEARCH_ONLY / DRAFT / P0_HOLD / PRODUCTION=NO_GO / TRUST_ACTIVATION=NO_GO`

**Purpose:** make F10 findings and code-diff permanently discoverable in a GitHub DRAFT PR. This is **evidence preservation, not software adoption, independent approval, merge authority or a production fix**.

## Source lineages: do not conflate

- Trae original **local** F9 parent: `31dd5dc9d8e1bf18fe0fc4f4e803198ad3484c07` (not a published GitHub commit).
- Trae local F10 fix: `4efc627` on its own lab branch (not a published GitHub commit).
- Ava [Draft PR #12](https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/pull/12) is a **separate F9 reconstruction** with different bytes. Do not apply the attached F10 patch to #12 or imply byte identity.
- The separate, original user-supplied `f10_review_bundle.zip` is SHA-256 `40a859b5c1544fed3aed6b8f8d6fb52e4a42438f5b33750a3915a5f37c5c1129` (25 members). The binary ZIP itself **is not stored in this GitHub PR**; an exact upload and checksum should be independently verified if published separately. GitHub's text audit and patch are preserved here.

## What is archived in this PR

- [INDEPENDENT_AUDIT.md](INDEPENDENT_AUDIT.md): Ava independent Linux run and source audit, explicit scope and counterexample.
- [TRAE_F10_FIX_REPORT.md](TRAE_F10_FIX_REPORT.md): Trae original engineering report, RED/GREEN outcomes and test inventory.
- [F10_fix.diff](F10_fix.diff): actual Trae F10 source/test *delta*, whose preimage is **Trae's F9**, not Ava's F9.
- [BUNDLE_README.md](BUNDLE_README.md): original self-contained bundle's README with hashes, expected tests, commands.
- This file: gate status, source identities, decision priorities and precise limitations.

## Independent facts established (Linux CPython 3.13.5)

- All **24/24 manifest entries** inside original delivered ZIP matched; archive SHA-256 matched Trae's stated hash.
- Before F10: one valid `MergeIntentAuthority` accepted in **two local roots** against the same shared SQLite DB, demonstrating double-use.
- After F10: the same bounded scenario accepted in **one local root**; the other was refused. `unittest` reported **146 tests OK**; the runner completed red+green.
- Reverse/forward application of `F10_fix.diff` against exact provided F9/F10 program bytes succeeded locally. This is **content correspondence**, not third-party notarization of Trae's Git commits.
- Supplemental independent probes: second public-sink use rejected with `AUTHORITY_ALREADY_CONSUMED` and one consumption row; old SQLite schema 7 rejected.
- Candidate RED tests returned `5 failures + 2 errors + 2 passes`: the observed double-use probe is the substantive counterexample; missing-API errors in old F9 should not be overstated.
- The whole-directory arbitrary `pytest` run includes deliberately failing historical reviewer RED artifacts outside the canonical `tests/` suite. **146 OK only applies to the intended test suite, not every .py file in the tree.**

## New P1 gap — not an F10 double-use bypass

`SharedCoordinator.record_local_observation` can append the audit event `LOCAL_EVIDENCE_RECORDED` with only a matching claim; it does **not** verify a journal append or a consumption record. The independent reproduction recorded that phase with **zero journal/consumption evidence**. Accordingly: audit event `LOCAL_EVIDENCE_RECORDED` is a *reported observation*, **not an independently validated persisted receipt**. Future fix should keep historical events immutable, require a bound independently checked receipt for any stronger claim, and preserve existing UNKNOWN/HOLD semantics.

## Nonclaims / stop rules

- Windows F10 execution **NOT_RUN**.
- Live GitHub native R2a-0 Sc1/Sc2/Sk/Sn/Sc3/Sc4/Se1 **NOT_RUN**.
- No evidence of DB rollback/fork resistance, global single-use, independent key custody, OS-level isolation, protected evaluation, or production merge protection.
- `_append_merge_intent_raw` same-owner bypass remains; candidate-authored tests/CI are not independent acceptance evidence.
- No main merge, rule change, signer/key/Genesis/trust activation, or production execution.
- **Do not merge this preservation PR as a shortcut for F10 adoption.**

Next: independent Windows test, bounded P1 event-provenance test and a separate trusted-merge-time gate experiment. Only a separately reviewed versioned implementation proposal could seek admission.
