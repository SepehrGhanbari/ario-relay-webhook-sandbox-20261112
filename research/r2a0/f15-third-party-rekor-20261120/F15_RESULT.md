# F15 — third-party-administered log evidence, exact observations

Status: `RESEARCH_ONLY / DRAFT / P0_HOLD / PRODUCTION=NO_GO / TRUST_ACTIVATION=NO_GO`.

## Source-backed design
Sigstore Rekor v2 is an externally operated signature transparency log supporting hashedrekord entries, inclusion proofs and signed Merkle checkpoints. Its checkpoint response may contain third-party cosignatures; this experiment **did not verify cosignature trust roots**. The official documentation also states that Rekor v2 is **not a full attestation storage service**: publishers must retain their complete attestation data.

## Observed real publication
- Submitted synthetic v1 `A_OLD` digest, signed with a transient P-256 key, to Rekor v2 public endpoint; response included `logIndex=206573201` and a Merkle proof and signed checkpoint. Stored raw JSON in `v1/rekor_response.json`.
- Submitted synthetic v2 `B_NEW` digest, referring to v1 SHA-256, using a second transient P-256 key; response included `logIndex=206575059` and proof/checkpoint. Stored raw JSON in `v2/rekor_response.json`.
- Discarded the private keys; only payloads, signatures, DER public keys and exact responses are archived.
- Both submissions were on the public Rekor shard `https://log2025-1.rekor.sigstore.dev`, operated outside Ario's GitHub administrative authority.

## Independent tests after publication
- A new independent read-only execution fetched v1 and v2 by documented C2SP tiled GET paths, HTTP 200, and extracted **256/256 valid entries** in each tile. The entries at offsets **145** and **211** respectively matched the exact payload SHA-256 of v1 and v2.
- Separately verified **for both**: RFC6962 Merkle path to the checkpoint root (`true`), checkpoint Ed25519 signature against Sigstore `root-signing` public key snapshot (`true`), and payload digest binding (`true`). OpenSSL reported `Signature Verified Successfully` for checkpoint note. The Sigstore public root snapshot was fetched from its GitHub repository, **NOT TUF-verified**.
- Identified the first prototype verifier's byte-escaping error; corrected it and reran; only the corrected run is counted.
- Simulated local deletion/rollback concept: external readback did not use locally retained publisher response file. If the verifier is preconfigured with index/digest B, it can retrieve it despite a local publisher-only rollback. That condition is **not** a proof of an automatically independently pinned latest floor.
- Neither the external operator's storage deletion API nor malicious operator behavior was exercised.

## Key limitations to retain visibly

1. **Unknown-latest:** if a publisher deletes **all** local pointers to v2 and no external observer pinned the latest index, an auditor may not know v2 ever existed without monitoring the entire log. Rekor's v2 read API has no general artifact-hash search service.
2. **Unverified TUF metadata:** public root-signing GitHub source is a useful separate published root, but trusted TUF update verification has NOT been performed.
3. **No independent persistent latest-floor custodian**, no proof of complete upstream ingestion or out-of-band trust activation.
4. **One external log operator**, not Byzantine consensus. Signed log snapshots and actual retention are stronger than two local folders but don't prove the operator cannot equivocate.
5. **No code/private signer/personal memory** sent to the service; payloads contain only synthetic identifiers and hashes. No live merge, owner key, genesis or protected rule changed.

**Verdict: `EXTERNAL_REKOR_TWO_ENTRIES_PUBLISHED / EXTERNAL_READBACK_PASS / CRYPTOGRAPHIC_INCLUSION_CHECK_PASS / EXTERNAL_LATEST_FLOOR_NOT_ESTABLISHED / P0_HOLD / PRODUCTION=NO_GO`.**
