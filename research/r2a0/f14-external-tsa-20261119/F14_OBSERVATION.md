# F14 — external TSA observation, reproducible limits

Recorded as an additive research artifact on top of F13 Draft PR #16, not as a modification of the F13 implementation.

## Experiment

1. Used the original user-provided F13 source and tests locally to create a synthetic F12 observed-intent state and call `VerifierFloor.pin()` and `VerifierFloor.check()`. The observed F13 checkpoint digest was `ec1cfd6312109fafd06185df45a587c565bd7d2de94f951855e1ca63b79d4531` and the locally pinned checkpoint file SHA256 was `01f7d887bb2900db176aa682ef0146b9b802b93d53f606cf1c435093089cb9fc`. These come from a disposable publisher path; that original raw pin is not itself included here. **Do not represent its mere hash as evidence of actual F13 source authenticity.**
2. Created the separately retained synthetic commitment file `F14_SYNTHETIC_ANCHOR_PAYLOAD.json` containing only those hashes, a synthetic repository name/PR identifier, RESEARCH_ONLY label and no private content.
3. Generated an RFC3161 timestamp query with OpenSSL SHA256 and requested a real response from `https://freetsa.org/tsr` using a cloud browser shell with `Content-Type: application/timestamp-query`.
4. The FreeTSA endpoint returned a DER TimeStampResp; `openssl ts -verify -in <response> -queryfile <query> -CAfile <provider-root>` returned **`Verification: OK`** in the cloud execution. An earlier test request against the raw F13 checkpoint digest also returned `Verification: OK` but that first receipt is not retained here; this artifact includes the **second, reproducible exact payload and matching signed receipt**.
5. The returned verifiable receipt and FreeTSA provider root certificate are stored as exact binary Git blobs alongside the matching query and payload in this PR.

## Grounded values

- Exact synthetic commitment SHA-256: `e7e6b9e4abdde1cfa8afdd219c326eaf995f2f740da4f2a01bdc15f756eba6ca`
- Signed timestamp response SHA-256: `a4ee6416ea3444875f6a7820a1057364ef45f2a04482597831b42b037881a79c`
- Provider-reported UTC timestamp: **2026-11-19 21:10:00 Z**
- FreeTSA timestamp serial: **0x0A3C7046**
- OpenSSL result: **Verification: OK**, backed by provider-supplied CA; this does **not** by itself establish an externally trusted TSA identity certificate.
- Private keys exchanged or handled: **none**. GitHub native merge called: **no**.
- Local shell direct network was unavailable; actual TSA call succeeded from separate cloud browser execution.

## Security boundary

- This is a cryptographically checkable **timestamp on opaque bytes** from a service not administered by Ario's publisher. This **is a real external signature**, unlike F13's two local directories.
- This does **not** establish independent persistent storage of a verifier floor, harden local SQLite, prove rollback/fork/revocation detection end to end, or establish main Ario governance admission. The timestamped content is a synthetic *commitment report*, not independently attested runtime state.
- The FreeTSA CA file came from the same operator website. No independently pinned trusted certificate chain, third-party audit or SLA is established.
- Source/test candidate remains authored/reviewed inside project. Production gate untouched.

**Verdict: `EXTERNAL_TSA_RESPONSE_OBSERVED_AND_PROVIDER_CHAIN_VERIFIED / INDEPENDENT_PERSISTENT_CUSTODY_NOT_ESTABLISHED / NATIVE_MERGE_NOT_RUN / WINDOWS_NOT_RUN / DRAFT / P0_HOLD / PRODUCTION=NO_GO`**.
