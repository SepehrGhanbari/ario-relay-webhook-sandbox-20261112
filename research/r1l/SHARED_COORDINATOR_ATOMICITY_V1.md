# R1l — Atomic shared coordinator: real network clients, database faults and fail-closed restart

**2026-11-13 — DISPOSABLE LAB / HOLD / NO PRODUCTION CHECK PERMISSION**

## Purpose and boundary

R1k proved a concrete design failure: two independent host-local `O_EXCL` journals can both reserve the same publication intent. R1l explores a strictly scoped **shared transactional reservation service**, without enabling any GitHub App publishing.

This branch adds:
- `r1l_atomic_coordinator.py`: a single loopback-only HTTP coordinator, SQLite WAL database, `synchronous=FULL`, atomic `BEGIN IMMEDIATE` + UNIQUE constraints for exact repo/App/Check/PR/HEAD and `external_id`.
- `r1l_network_client.py`: credential-free one-attempt client. Ambiguous HTTP failures do not automatically retry; `GET /status` permits non-mutating recovery observations.
- `tests/test_r1l_coordinator.py`: **22** new real subprocess and localhost-HTTP tests, plus **32** inherited R1j mock cases and **20** inherited R1k process-fault cases = **74 per platform**.

**Critical:** the service never issues or signs GitHub Checks, never handles App keys, never returns `can_publish=true`, and never grants repeat publication rights. Even successful `CREATED_HOLD` means only a durable shared reservation was created; publication itself remains forbidden.

## Measured experiments

| Experiment | Actual observed result | Interpretation |
| --- | --- | --- |
| Eight separate clients in eight separate directories, one server + one SQLite store | One `CREATED_HOLD`, seven `ALREADY_HELD`, one DB claim | Atomic local database coordination, not actual distinct network hosts |
| Two separately running HTTP server processes using SAME SQLite database file | One `CREATED_HOLD`, one `ALREADY_HELD` | Shared-file SQLite transactions serialize on that one host/filesystem |
| Two separately running HTTP servers with DISTINCT SQLite DB files | Both `CREATED_HOLD` | **Split-brain FAIL**: no global uniqueness between replicas; production P0 |
| Server unavailable / network failure | `UNKNOWN_HOLD`, no local fallback | No claim of network resiliency |
| SQLite `BEGIN IMMEDIATE` held by another database writer | `UNKNOWN_HOLD` (503), no inserted claim | DB lock prevents a new transaction; no emergency bypass |
| Hard server exit via `os._exit(91)` AFTER COMMIT but BEFORE HTTP response | Client `UNKNOWN_HOLD`; fresh process sees old claim, duplicate response `ALREADY_HELD` | Crash/restart safety on tested filesystem only; client must not blind-retry |
| Server intentionally drops reply AFTER COMMIT without exiting | Client `UNKNOWN_HOLD`; read-only GET sees `CLAIMED_UNKNOWN_HOLD` | Ambiguous response cannot be treated as uncommitted |
| Clean server restart | Exactly one claim persists | DB durability under normal process restart |
| Missing DB file or damaged primary SQLite file header | Server refuses startup; no automatic bootstrap/reset | Fail-closed physical DB identity check, not comprehensive corruption proof |
| Second bootstrap on existing file | Refused by `O_EXCL` | Prevents normal accidental fresh DB initialization |
| Same logical claim, different evidence digest | `CONFLICT_HOLD`; original retained | Fail closed on scope collisions |
| Wrong repo/App/PR type or public non-loopback address | Rejected without claim | Hard-coded lab scope; no remote deployment |

Every API response has `can_publish=false`, `repeat_post_allowed=false`, `github_check_emitted=false`, and `production_trust=NO_GO`.

## Hosted evidence and prior failures preserved

- First [run 43495645452](https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/actions/runs/43495645452) failed: corruption probe exposed SQLite WAL recovery despite an invalid primary header, and Windows cleanup encountered locked files.
- Source was corrected to **explicitly close SQLite connections** and require exact SQLite primary-file magic header on startup. A subsequent [run 43496027575](https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/actions/runs/43496027575) passed **20/20 on Linux and 20/20 on Windows**.
- Two new dual-server experiments were then appended, and the CI workflow expanded to include inherited R1j/R1k regressions.
- **Final tested code snapshot before this documentation commit:** SHA `3758f0444a4895b991e4886209b338361b695cef`.
- [Final cross-platform run 43496358068](https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/actions/runs/43496358068) completed **success**; Ubuntu `Ran 74 tests ... OK`; Windows `Ran 74 tests ... OK`. Both dual-server scenarios were executed in both runners.

## Scope of the claim

The tests are real process and HTTP operations, real SQLite file locks, and real server termination/restart. However, all server and client processes still ran **within each one GitHub-hosted runner**, over `127.0.0.1`. Client working directories emulate separate host-local journals but are NOT a demonstration of multi-machine networking, authenticated requests, a geographically redundant consensus store or an independent publisher.

SQLite WAL supports transactional contention in a single local filesystem; using independent SQLite copies or untested network filesystems does **not** establish global serializability. The successful dual-server shared-file case does not justify deploying two independent physical SQLite primaries.

The code has no server authorization, TLS, public-facing binding, credential vault, App-token minting, signed-receipt validation at ingress, durable external audit service, rate limiting, quorum/failover, or production-only conditional issuer identity. These omissions are deliberate to prevent a research prototype from acquiring authority.

The input fixture is pinned to **one disposable PR #14 / head B**. The stored evidence SHA-256 is syntactically validated, not verified against independent signed raw-test evidence here. `CREATED_HOLD` means a reservation only, not "the tests passed" or "publish success".

## Next necessary independent controls (NOT DONE)

1. Independently provisioned single credential-holding publisher separate from untrusted PR code and execution; authenticated mutual-TLS client/producer identities, revocation, rate limits, immutable release and append-only audit.
2. Replace this same-host SQLite-only coordinator with a **separately protected linearizable service/consensus or durable transactional store** with real single-writer authority, a strong disaster-recovery story and conflict-of-interest safeguards.
3. Introduce real isolated-machine partitions, concurrent submissions via two network hosts, coordinator outage/crash after commit, failover and corrupted datastore recovery. Demand `HOLD` on uncertainty and no automatic duplicate POST.
4. Bind verifiable test evidence, current PR HEAD/base and no `neutral/skipped` conclusion at the actual credential-holding publishing boundary. Audit the provenance of the issuer and independently review the entire trust chain.
5. Keep every previous negative observation and failing CI run; do not recast green unit tests as activation permission.

**Research verdict:** R1l local shared-coordinator transaction proof and fault injection **PASS within lab bounds**; globally independent service **NOT PROVEN**; two independent databases **FAIL** global uniqueness. Production Ario Rulesets, main, #133/#151, permanent key/Trust remain **HOLD / NO_GO**.
