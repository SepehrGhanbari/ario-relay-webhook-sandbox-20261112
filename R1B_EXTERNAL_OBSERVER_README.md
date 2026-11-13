# R1b outside-PR hosted GitHub observation — DO NOT MERGE

This **experiment branch** is in a DIFFERENT GitHub repository from [untrusted target PR #9](https://github.com/SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a/pull/9), to prevent that PR from directly changing the observer workflow or code. It preserves the sandbox's `main` untouched. The GitHub Actions job reads public GitHub REST API without executing PR-supplied code, checks a frozen source SHA, and fails with nonzero exit when it sees `HOLD`.

The source is copied byte-for-byte from the previously executed workstation external auditor, exact Git blob `9a03e9b11945c8273950b731a102a496ac555381` and SHA-256 `1a293c6b5d14521cdc26d03bea15f0ba81dd21d6ba3642b5ac4f7dc2382f6d5d`. It pins the target PR head `d9c889ec3d14f2b3de1317ed2d70d70dca00b328` and base `be7c16d964872f88ddb9029f2677c49a7cd745ba`.

**Expected observed outcome:** job result FAILURE with `verdict=HOLD`; this is a *successful negative control*, not a successful check or merge authorization. The target PR is Draft and no authenticated independently administered Check producer exists. Do not change exit code or suppress failures to make the CI appear green.

**Hard limits:** GitHub Actions checks in both repositories use the same GitHub Actions App identity. Running in a separate repository is **not** an independent App-bound publisher for a protected target repo. There is no external GitHub App private-key custody, installed publisher, stable required check, deletion-proof issue event journal, or atomic review evidence/merge. This workflow is read-only and grants only `contents: read`. Do not merge this research into any `main`, install Rulesets, or move #133/#151 from HOLD based on these tests.
