# F6 — Two independent evidence roots can both accept the same merge-intent recovery

Date: 2026-11-17  
Status: **FALSIFIER REPRODUCED IN LOCAL TESTS / DRAFT / P0_HOLD**  
Boundary: `RESEARCH_ONLY / LIVE_R2A0_NOT_RUN / PRODUCTION=NO_GO / TRUST_ACTIVATION=NO_GO`

## Scope and exact version

- Tested the unchanged R2a-0 F5/v0.6 runtime, `research/r2a0/v02/r2a0.py` (Git blob SHA-1 `1a919b5e2969b50633257b670d922e8d2d7b6d5e`), and unchanged 90-case existing suite (blob `fe6d6ce694a47249f36c04fb4bf20a0a29c87e3d`).
- Added only **read-only** `f6_compare.py` and `tests/test_f6_split_brain.py`. No modifications to the merge/recovery implementation, GitHub App, Rulesets, or live merge targets.
- Platform: CPython 3.13.5, Linux, one container host. Two separate journal directories; one under the ordinary overlay filesystem, another under `/dev/shm` tmpfs with different `st_dev` values. **These are different filesystem mounts, not independently administered physical disks or machines.**
- Worker processes have `r2a0.gh_api` patched to raise if called and possess no App key, token, or permission to perform a native merge. A shared `GO` file is used *only to coordinate the test start*, not as a recovery lock or source of authority.

## Experiment F6a: two honest local approvals for one logical intent

Each root receives an independently written, valid prior journal entry with different payload contents (origin A vs B) and an **identical canonical marker**:

`{"base":"experiment/r2a0-f6","head":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","pr":22,"repo":"SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a","scenario":"Sc1"}`

Two independent Python OS processes wait at the same rendezvous then invoke `adopt_single_orphan_intent` on their own root. **Both return** `APPENDED_RECOVERY_EVIDENCE_ONLY`; each local `EvidenceJournal.read()` verifies two records; each local `inspect_merge_recovery()` still reports **HOLD** and `remote_merge_retry=FORBIDDEN`. Because the original evidence histories differ, the final hash-chain heads differ too. The local `O_EXCL` slot claims correctly protect each individual filesystem; they provide **no cross-root mutual exclusion**.

This demonstrates **dual local adoption**, not two GitHub merge attempts or a bypass of the native merge gate. No network mutation was attempted.

## F6b: detecting, not resolving, the fork

A new **read-only** comparator accepts exactly two operator-supplied root paths, validates both complete local chains, marker objects and claims, and compares marker hashes. It reports:

- Same marker on both roots: `HOLD_DUPLICATE_INTENT_ACROSS_ROOTS`.
- Different markers: `UNKNOWN_NO_DUPLICATE_IN_TWO_OBSERVED_ROOTS` (**not PASS**; additional roots and missing history are unknown).
- Corrupt, incomplete, missing or aliased roots: `HOLD_ROOT_INSPECTION_FAILED`.
- On every outcome: `root_set_completeness=UNKNOWN`, `independent_custody=NOT_ESTABLISHED`, `remote_merge_retry=FORBIDDEN`, `merge_authorization=NOT_GRANTED`.

The tool does **not** choose a winning chain, rewrite history, delete partial claims, submit or retry a merge request, assume a synchronized clock, or provide a global lock. A **copied backup** of one valid root can also produce two identical markers; the comparator reports HOLD conservatively but **cannot infer two independent writers from the duplicate alone**. The synchronized F6a subprocess control is what supplies evidence of independently created local records in this particular test.

## Tests and observed results

- Existing F5: **90** tests.
- New F6: **8** tests (two-process dual adoption; byte-for-byte nonmutation during inspection; distinct intents remain UNKNOWN; corrupted or missing root HOLD; orphan root HOLD; symlink/same root HOLD; copied backup HOLD; two distinct filesystem mounts dual adoption).
- Full suite: **98/98 PASS**, CPython 3.13.5 on Linux.
- Additional stress: **10 more two-process pairs on different filesystem mounts: 10/10 PASS**, no skipped mount test.
- `test_two_distinct_filesystem_mounts_can_adopt_the_same_intent` explicitly checks distinct `st_dev`; on a platform without a writable `/dev/shm` mount it is skipped. Windows CI remains advisory and cannot prove separate-mount behavior.

Run: `python -m unittest discover -s tests -p 'test*.py' -q`

## Source SHA-256

- `r2a0.py` (unchanged): `58b8be40099d0fbb82bad91b322160e9d619b0e08c656ab5261b9576e85c88d9`
- `tests/test_r2a0.py` (unchanged): `def13603fcc1f4822ec06318f74c65821faddbb5e69810359ab67c9b33ca76ae`
- `f6_compare.py`: `2cae332b99d2db6a59eb6021c7fb3fc08294bdd6db621c05750dcbccb9b5cc8c`
- `tests/test_f6_split_brain.py`: `67964eb19206d6767f3089f46ffd6930fb1051602fd6399238ffb4927ac78f15`

## Engineering decision and open questions

**F6: FAIL for any claim that existing local O_EXCL establishes global uniqueness across storage roots. PASS for reproduction of the expected limitation and conservative read-only detection.**

Before allowing more than one independently writing evidence root to influence a real admission decision, define one shared serialization/admission authority (or an explicitly specified distributed protocol) that all writers actually consult. If it is unavailable, the policy must HOLD. The comparison tool is forensic only; it is not a replacement for transaction ordering or independent custody. Do not create a witness network or promote D3 merely because two roots can diverge.

**Still NOT RUN:** live R2a-0 Sc1/Sc2/Sk/Sn/Sc3/Sc4/Se1 against GitHub; actual independent human custody; network partitions/fencing; real power loss; production gate activation. Keep PR #10 DRAFT/UNMERGED and all original Ario rulesets, signer, keys and trust untouched.
