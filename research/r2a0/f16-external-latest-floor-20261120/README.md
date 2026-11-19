# F16 synthetic latest-floor experiment — archived public evidence

Read [F16_REPORT.md](F16_REPORT.md) for scope, exact results and blockers.

- [Signed synthetic A/B events](signed_events.json) are original public NIP-01 records (Schnorr signatures), **not** receipts signed by external relay operators. Query hosts `wss://nos.lol`, `wss://relay.primal.net`, `wss://relay.nostr.net` by author `a83270bc0068711429fd7fde8c4d93157eb700495b4017a23a49eafbe95d5659`, kind 1, tag `#t=ario-f16-20261120-research`.
- The full **30-test** Linux self-contained Python bundle was prepared locally and its file hashes are in the report. It has not yet been uploaded to this PR, so hosted GitHub CI on the exact tested bundle is **NOT_RUN**. Independent reviewers should not mistake this repository snapshot for a full implementation tree.
- Existing authoritative upstream test-source and cryptographic evidence: [F15 PR #18](https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/pull/18).
- No live GitHub merger, main Ario trust activation, owner keys, or production rules were touched.

`RESEARCH_ONLY / DRAFT / P0_HOLD / PRODUCTION=NO_GO / INDEPENDENT_LATEST_CUSTODY_NOT_ESTABLISHED`
