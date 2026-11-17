# R2a-0 F4 v0.5 — Local evidence and immutable source IDs

Date: 2026-11-17. Result: **87/87 PASS (local Python 3.13/Linux)**; not independent or live native GitHub R2a-0 enforcement.

## Negative-control results

- Existing v0.4 source (blob `07ec86a70f9f9b36874627d85d32938989c78932`) with v0.5 tests: **87 tests; 20 errors**, because the new recovery operations are not implemented in the old source.
- v0.5 source + tests: **87 tests, OK**.
- Explicit real subprocess `os._exit(73)` after durable merge-intent marker; after restart `verify` remains HOLD until operator deliberately records provenance.
- Further local controls: corrupted/two orphan markers, incomplete journal claims, multiple prior intents, unknown GET, head drift, `merged=true` without attribution, stale/nonexistent marker, and ACK enforcement before any write.

## GitHub source exact-byte comparison

| File | SHA-256 | Git blob SHA-1 |
|---|---|---|
| `research/r2a0/v02/r2a0.py` | `58b8be40099d0fbb82bad91b322160e9d619b0e08c656ab5261b9576e85c88d9` | `1a919b5e2969b50633257b670d922e8d2d7b6d5e` |
| `research/r2a0/v02/tests/test_r2a0.py` | `3dcc3b8e1064dfae570f097bd05e1f0247f6ee13eb0e3ab7a5b4dfe9cb55d5d5` | `be97203ac8d5b54ff9aef33c06372e10837863ef` |
| `research/r2a0/v02/F4_SAFE_HOLD_RECOVERY_REVIEW.md` | `82cd61b07d72ddd0d5815a57b63548b62c0fa4df343f2ec13efe1fee4d41b19a` | `a4bb6277e5dc3b1c769f7e07314cacb5125696ce` |

**Not established:** new GitHub CI results for this HEAD; any live `Sc1/Sc2/Sk/Sn/Sc3/Sc4/Se1`; independently owned custody; completeness of webhook history; exactly-once native merge/check effects. Existing required-check policy in Ario main is unchanged.

## Disposition

`RESEARCH_ONLY / DRAFT / P0_HOLD / LIVE_R2A0_NOT_RUN / PRODUCTION=NO_GO / TRUST_ACTIVATION=NO_GO`.

**Review request:** try to falsify evidence-preservation and no-blind-retry properties with a minimal counterexample, naming file/line/test. The main failure risk is cross-process or cross-directory concurrency, not covered by the local single-writer claim.
