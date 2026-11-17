# F7 exact-byte local record

Python: 3.13.5
Platform: Linux-6.18.57-x86_64-with-glibc2.41

Local full-suite command: `python -m unittest discover -s tests -p "test*.py" -q`
Local full suite: **120/120 PASS** (98 baseline + 22 F7), 2026-11-17.
Live GitHub native experiment: **NOT RUN**.
GitHub-hosted CI: **NOT YET CHECKED** at this record creation.

## SHA-256 of local files

- `f7_coordinator.py`: `fb458837ca587dc248c861f7efc11e14ea63af6a95fec4db829681ad44eb4c8e` (12109 bytes)
- `tests/test_f7_coordinator.py`: `f582571677960c833483406cd4bed8ae8130597083cf8242367647237ac45121` (16730 bytes)
- `F7_SHARED_COORDINATOR_REVIEW.md`: `8575daa632cd6b6b989846576ed5563389299e601f2dca5cbe0fbe743a57eded` (7012 bytes)

Evidence boundaries: same-host SQLite single-file serialization; no independent custody, no multi-host/fencing proof, no power-cut durability proof, no mandatory legacy CLI gating, no native merge enforcement.
Result: **HOLD / RESEARCH_ONLY / PRODUCTION=NO_GO**.
