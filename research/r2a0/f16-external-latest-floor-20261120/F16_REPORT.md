# F16 — independently hosted synthetic latest-reference research

**RESEARCH_ONLY / DRAFT / P0_HOLD / PRODUCTION=NO_GO / TRUST_ACTIVATION=NO_GO**

## Grounded prior evidence
The research baseline is [F15 Draft PR #18](https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/pull/18), including genuine Sigstore Rekor v2 signed inclusion proofs and separate witness cosignature for synthetic F15 record B. F15 Rekor indices: A=206573201; B=206575059. F16 is an **additive** experiment; no merge or production change.

## F16 — measured results

### 1. Local high-water contract (NOT independent)
A synthetic simulator was tested on **Linux Python 3.13.5**: a predeclared four-event manifest, SQLite `BEGIN IMMEDIATE`, monotonic checkpoint sequence, previous digest, source-range hashes and complete-source decision. **21/21 tests PASS**, including rollback, fork, incomplete source, unsubmitted event, substitute/renumbered event, concurrent writers, restart, invalid authority and a deliberately preserved DB-copy bypass.

The constructor and outputs explicitly state `independent_custody: NOT_ESTABLISHED`. A same-owner SQLite clone can produce two accepted histories; an attacker who controls the predeclared source can suppress events before the declaration; a future event never submitted is not provably visible absent an independently acquired source high-water and deadline. A direct same-owner DB edit remains possible. Do **not** promote the simulator to custody proof.

### 2. Actual outside publication and readback
Two **synthetic**, disposable-key, NIP-01 signed kind-1 records were published to three public Nostr relay hosts:
- `wss://nos.lol`
- `wss://relay.primal.net`
- `wss://relay.nostr.net`

For each host, `OK(id,true,"")` was returned for both A and B; a second connection returned both events, filtered by signed **author public key** and `#t` topic. A **later fresh separate execution**, without original publisher files or B receipt, re-queried the three hosts using only the pinned public author key: **3/3 returned both signed records**. This demonstrates *observed externally hosted discoverability*, not durability guarantees.

Pinned public synthetic author: `a83270bc0068711429fd7fde8c4d93157eb700495b4017a23a49eafbe95d5659`.

A signed Nostr event ID: `4ba8f0d8fb895c4158668240148562bd190aa585780e5d8ba7635dedbb9a5427`, SHA256 of F15 A: `1287f223186e3f71ed5230261d375e8c8070b0eca8384fc30b8de73050b1c5c3`.

B signed event ID: `3296d8309bb478b56778b7651da0cec1e84b05db9aaf474f55e8a6c80d239a4c`, SHA256 of F15 B: `cf7ad5df590b7b905faefe4bc0ae1e25a20c556887d56179592ddcaa7bfe9a63`, refers to F15 A SHA256.

The private scalar used to author **synthetic-only** events was not retained or uploaded. This pubkey is a **test identity**, not enrolled as an actual Ario signer identity or trusted root. The Nostr relay ACKs are **not operator-signed retention receipts** and the relays do not enforce a monotonic per-Ario policy or guarantee indefinite storage. Separate domain names do not alone prove noncollusion or distinct underlying administrators.

### 3. Tests
Full self-contained F16 local bundle (retained outside this PR): **30/30 tests PASS** (21 source/floor, 9 NIP-01 signature/rollback/duplication/fork checks). The archive has SHA-256 `519f851c45c97711618f80dc4b0db7dbfe399c22de1607818c9e650123904b61`; source `f16_floor.py` SHA-256 `8552bdb6ab59c57682dbb1692bb5f457a5a8483d0796b9b3872e40cb7516a5c6`; source `f16_public_relay_verify.py` SHA-256 `e17ddd6944965843442cc0e11b446d17bc2c5acf3e57d503a3a53dd0c47abea9`. **The full source archive has not yet been committed here; do not claim that GitHub CI independently ran the entire candidate suite.** The `signed_events.json` file below preserves exact issued public notes for independent verification.

## F16 attack matrix

| Attack | Observed / bounded outcome | Unresolved boundary |
|---|---|---|
| Publisher deletes locally held newer B | 3/3 external relays returned B by author key even with no local B file in fresh reader | Relay deletion or selective suppression still possible |
| Publisher rolls back B → A | Auditor who knows pinned author and queries successful relays sees B; SQLite simulator with retained floor B refuses A | A verifier that skips remote query can miss B |
| Two forks at same checkpoint sequence | Simulator `BEGIN IMMEDIATE` refuses local second branch; signed-event contract test holds on duplicate sequence | Copied SQLite file, independent relays with split views, malicious operator remain |
| Event omitted from a precommitted four-event stream | Simulator checks prior manifest sequence/hash and refuses missing/substituted item | No independently held original event stream → omission before enrollment is invisible |
| New checkpoint never submitted | Simulator labels incomplete source `HOLD_SOURCE_INCOMPLETE` only if source count previously declared | Liveness/ingestion completeness cannot be inferred from silence |

## What has NOT been achieved
- **No independently administered enrollment and no separate custody of the Ario-specific monotonic latest floor with a verified operator signature.**
- No verified unforgeable custodian ACK, external admission policy, retention SLA, third-party high-water/rollback rejection, bound source-of-truth completeness, or per-identity monitoring of withheld events.
- Nostr relays do not substitute for Rekor's signed Merkle log or Rekor tree witness; Rekor's witness does not learn the latest *Ario stream* checkpoint.
- No live Ario producer, permanent signer keys, Ario governance merge, protected ruleset, Windows native run, or trust activation.

## Minimum next external acceptance gate
An enrolled independent operator must: separately pin project stream identity and signer/public source root; enforce gap-free monotonic checkpoint seq/prev and independent source high-water; durably retain `(stream,seq,hash,prev,range,source_digest)`; sign an operator-owned receipt binding exact bytes, previous receipt, issuer and retention horizon; expose readback/latest through a channel not controlled by publisher; preserve refusal and revocation evidence; and reject forks/rollback. **A public relay accepting self-signed events does not satisfy this**. This gate remains `P0_HOLD`.

**VERDICT:** `LOCAL_FLOOR_CONTRACT_BOUNDED_PASS / THREE_EXTERNAL_RELAYS_RETAINED_SYNTHETIC_A_AND_B_AT_READBACK / INDEPENDENT_ARIO_LATEST_FLOOR_NOT_ESTABLISHED / NO_MERGE`.
