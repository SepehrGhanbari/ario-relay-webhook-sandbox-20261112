# R2a-0 F4 — Evidence-preserving HOLD recovery and GET-only reconciliation

Date: 2026-11-17. Scope: disposable R2a-0 lab. Baseline: `RESEARCH_ONLY / P0_HOLD / LIVE_R2A0_NOT_RUN / PRODUCTION=NO_GO / TRUST_ACTIVATION=NO_GO`.

## Threat and goal

After a crash, the disk can contain a durable `merge_intents/<digest>.json` marker but no matching `merge-intent` event in the hash-chained journal. Alternatively, the journal can contain the intent without a `merge-attempt` response, or a response can represent an ambiguous write outcome. None proves whether GitHub received a `PUT /merge`.

The goal is **evidence-preserving recovery**, not reauthorization and not a retry mechanism. F3 already detected these states as HOLD. F4 adds a bounded way to inspect them and, for one intact orphan marker only, append a provenance-labelled recovery event without rewriting old bytes or contacting GitHub.

## Implemented behavior

1. **`inspect-recovery` is locally read-only.** It validates original index, payloads, claims, and markers. It allows inspection of exactly one valid orphan marker via a temporary pending-marker verification mode but does not classify a damaged journal as an orphan. Invalid marker, two orphans, orphan claim/object, torn line, or hash mismatch => HOLD / command failure; never silent repair.
2. **`inspect-recovery --remote --marker-sha256 H` performs only a GitHub GET**, scoped to the allowlisted disposable repository and PR. Results are limited to `OPEN_UNMERGED_AT_READ_TIME`, `MERGED_OBSERVED_ATTRIBUTION_UNKNOWN`, `REMOTE_TARGET_DRIFT_HOLD`, or `REMOTE_*_UNKNOWN`. Neither `merged=true` nor `merged=false` proves who performed a merge or whether a previous PUT was sent. The remote observation does not alter the journal, does not authorize a merge, and can never generate a PUT.
3. **`record-orphan --marker-sha256 H --ack RECORD_ORPHAN_ONLY_NO_MERGE_RETRY`** is the only permitted recovery mutation. It requires exactly one valid orphan marker, no unrelated corrupt files, and exact SHA-256 matching. It appends `merge-intent` with metadata `ORPHAN_MARKER_RECORDED_AFTER_CRASH` and `remote_effect=UNKNOWN`; the original marker, earlier records, payloads and claims are preserved. It never calls `gh_api` and remains `HOLD_OUTCOME_UNKNOWN`. Repeated invocation refuses the already adopted marker.
4. **A disposable merge invocation requires ACK before any local reservation** and refuses all new `--execute` intents in an evidence directory that already contains an intent, even one with a different `scenario` (no scenario alias bypass). Use separate evidence directories for different intentional lab probes.
5. **`verify` now differentiates journal integrity from merge authority.** A valid index may show `PASS`, but it also returns `merge_intent_safety=HOLD_REQUIRES_RECONCILIATION` and `native_merge_authority=NOT_GRANTED` when an intent exists.

## Minimal operator sequence (no production repo)

```bash
python r2a0.py inspect-recovery --evidence-dir /path/to/disposable-evidence
# If exactly one intact orphan marker is detected, choose its printed marker_sha256:
python r2a0.py record-orphan --evidence-dir /path/to/disposable-evidence --marker-sha256 <64-hex> --ack RECORD_ORPHAN_ONLY_NO_MERGE_RETRY
# Review only. If gh is configured to an authorized disposable test account:
python r2a0.py inspect-recovery --evidence-dir /path/to/disposable-evidence --marker-sha256 <64-hex> --remote
```

**Do not** run `attempt-merge` to resolve HOLD; never delete/rename orphan files, truncate journal, reset the hash chain, switch scenario or HEAD to bypass the lock, or blindly repeat any API write. Even an unmerged PR seen via GET may reflect pending operations or a prior refused write. Prefer an independent operator's read-only review and explicitly new scenario/branch after disposition.

## Negative evidence and validation

- Existing F3 real process crash marker survived.
- F4 tests exercise read-only inspection (no bytes changed), orphan adoption with explicit ACK, duplicate adoption refused, multiple/corrupt markers refused, unrelated orphan claim blocks repair, captured ambiguous response stays HOLD, GET-only remote true/false/drift/5xx, selection of a single intent, ACK before reservation, recovery interruption after claim, and changing `scenario` cannot trigger a second merge.
- All tests are standard-library mock/offline or local process crash tests. Hosted Windows/Linux checks (if subsequently reported) are PR-authored candidate tests, not independent controls.

## Limits / explicit UNKNOWNs

- **No live GitHub R2a-0 merge-race case has been executed.** This does not establish whether native checks revoke old `success`, whether GitHub review-thread dismissal blocks merge, or whether delivery is complete.
- Local hash-chain and file locks are under the same owner. No independent key holder, independent infrastructure, or tamper-proof archive is established.
- A subprocess may crash after GET or PUT; this mechanism cannot prove absence of a remote side effect. A GET's result is a point-in-time observation, not a causal receipt.
- R1j unknown-POST idempotent reconciliation for App Check publication remains separate. Do not describe this GET-only **merge** observation as proof of Check Run publication exactly-once.
- The CLI preflight is not an atomic multi-process/global lock across multiple evidence roots or hosts; executable permissions and operator discipline are still assumptions. This is a bounded lab result.
- An orphan **claim or payload**, a malformed marker, torn index, multiple uncommitted markers, or conflicting data remains HOLD; no automatic reconstruction.
- This prototype intentionally does not use GitHub App signing keys or publish trusted Checks; no production settings or keys may be touched.

## Verdict

`LOCAL_RECOVERY_PATH_PASS / REMOTE_EFFECT_UNKNOWN / LIVE_R2A0_NOT_RUN / P0_HOLD / PRODUCTION=NO_GO`.
