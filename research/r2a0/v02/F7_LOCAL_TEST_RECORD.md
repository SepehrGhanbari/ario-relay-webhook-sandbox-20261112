# F7 exact-byte local record

Python: 3.13.5
Platform: Linux-6.18.57-x86_64-with-glibc2.41

Local full-suite command: `python -m unittest discover -s tests -p "test*.py" -q`
Local full suite: **121/121 PASS** (98 baseline + 23 F7), 2026-11-17.
Live GitHub native experiment: **NOT RUN**.
GitHub-hosted CI: **initial Windows failure reproduced; corrected run must be checked on exact PR HEAD**.

## SHA-256 of local files

- `f7_coordinator.py`: `236af148293dde1ea3b004cb37c361b04eaba3ccbe0a9e269cc9483051a9b710` (12507 bytes)
- `tests/test_f7_coordinator.py`: `f026f678d06111fbc63758a79a7e6b7271386c6fd4a9442b393cdbd3fde7b3ce` (17164 bytes)
- `F7_SHARED_COORDINATOR_REVIEW.md`: `12ed2b3f293c0a6d48cb7413f240dd248b273a6fe31b43fef538285cbdd08f2f` (7371 bytes)

Evidence boundaries: same-host SQLite single-file serialization; no independent custody, no multi-host/fencing proof, no power-cut durability proof, no mandatory legacy CLI gating, no native merge enforcement.
Result: **HOLD / RESEARCH_ONLY / PRODUCTION=NO_GO**.
