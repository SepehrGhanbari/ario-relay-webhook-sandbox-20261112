# Ario R2a-0 F13 — Retained verifier floor falsification (19 Nov 2026)

**Status:** `RESEARCH_ONLY / DRAFT / P0_HOLD / PRODUCTION=NO_GO / TRUST_ACTIVATION=NO_GO`.

**Exact F13 sources and tests**, independently executed on Linux CPython 3.13, are published in this directory:
- [f13_verifier_floor.py](f13_verifier_floor.py) — Git blob `538c32ee6241c867ed2734089acbcbfa23561870`
- [tests/test_f13_verifier_floor.py](tests/test_f13_verifier_floor.py) — blob `fe7ed94de1645b20b8967efc403e82e91c9b0052`
- [f13_coherent_substitution_probe.py](f13_coherent_substitution_probe.py) — blob `1b232152534758ba71c4d14b874d3c175bd9c362`

This branch is **stacked on F12 Draft PR #15**. F13 was actually executed on **Ava's exact F12 standalone source**, combined with the original Trae F10 tests, F11 and F12 tests. Those full dependency files are in the separately retained conversation review ZIP; **this GitHub folder alone is not a complete standalone checkout**, and no GitHub Actions or Windows F13 run is claimed. No production code is changed.

## Independently reproduced falsifier

1. Create an F12 claim, consume it, record a valid local journal, and save a verifier pin in a **different directory**.
2. Copy the valid evidence root A to B and coherently edit **three columns of the publisher's same-owner SQLite DB**: `consumptions.evidence_root`, `root_bindings.evidence_root_sha256` and `observation_snapshots.evidence_root_sha256`.
3. F12's publisher-side `inspect()` still returns `CURRENT_LOCAL_READBACK_MATCH_NOT_INDEPENDENT`.
4. The independently retained **local simulator** floor returns `PUBLISHER_DIFFERS_FROM_RETAINED_CHECKPOINT`, while `merge_authorization=NOT_GRANTED`.

**Actual probe output**:
```json
{"F12_publisher_local_status": "CURRENT_LOCAL_READBACK_MATCH_NOT_INDEPENDENT", "F13_merge_authorization": "NOT_GRANTED", "F13_retained_floor_status": "PUBLISHER_DIFFERS_FROM_RETAINED_CHECKPOINT", "independent_custody": "NOT_ESTABLISHED", "network": "NOT_USED", "pin_persisted": true, "production": "NO_GO"}
```

**Local tests:** prior 162 + F13's 14 = **176/176 PASS**, including simulated two-process same-subject contention, abrupt crash after exclusive pin-file creation, no automatic re-pin of an empty/torn file, rollback while floor survives, changed source during pin, missing/unsafe directory, symlink, tamper and no-evidence refusals. CPython 3.13 / Linux only; candidate-authored suite, not external authorization.

The archived review bundle ZIP SHA-256 is `4884cfa4e04fd99dcc7541838a77ebce473b9cc8fbc989ef9c7faf77ee413f02` and contains all F13 source dependencies + 176-test suite and logs. It is available from the owner conversation artifact, not represented here as a GitHub attachment.

## Deliberately unproven

- **Not an independent custodian.** Second directory/process runs with the **same owner identity**. Full owner control of publisher and verifier storage, or rollback of both together, can defeat the pin. There is **no cryptographic signature, nonextractable key, trusted timestamp or global consensus**.
- **Not atomic across publisher SQLite, journal filesystem and verifier floor.** No check can guarantee that evidence remains unchanged after the last read; a power-loss durability test has not run.
- **Not a trust or merge gate.** The `hold()` result always reports `merge_authorization=NOT_GRANTED`, `independent_custody=NOT_ESTABLISHED`, `native_merge=NOT_RUN`. No production or native GitHub live experiments.
- **No Windows run yet.** No cross-platform guarantee inferred from Linux.
- **No new privileged authority**: F12's `DB_VERSION=9` remains untouched, this is an additive researcher-owned module only.

## Review focus

Please try: mutate publisher+verifier together; race immediately after the post-write recheck; replace floor directory by symlink/junction; crash before/after fsync; stale checkpoint after full rollback; Windows SQLite/NTFS differences; distinguish recorded history from independent durable receipt. Ask for exact source + counterexample; do **not** recommend merge based solely on 176 green tests.

**Next gate:** genuinely external/separately administered checkpoint custody and a read-only verifier with an independently retained floor; requires separate owner approval before publishing externally or creating live secrets.

**Nothing merged or activated.** Original F8–F12 PRs, Ario `main`, protected settings, signer, Genesis and trust remain unchanged.
