# R2a-0 v0.2 local verification — 2026-11-17

**Status:** `50/50 PASS`, CPython 3.13, Linux (single runtime); no native GitHub R2a-0 execution.

Evidence covers one real subprocess exit (`os._exit(73)` after durable claim), concurrent child-process append attempt, loopback HMAC and rejected malformed evidence. It does **not** establish stable power-loss durability, independent custody, or GitHub required-check behavior.

## SHA-256 of local artifact bytes

- `r2a0.py`: `e26515125e04de35dd6261e8a33a2c2e0d09ee859c3a2e0e1e7b17982a87d706`
- `tests/test_r2a0.py`: `1bb3535b2924b9c13b4075aa028bdcb161aa15ce46bb14392acec971cfef3b05`
- `LOCAL_UNIT_RESULTS.txt`: `55f6c5a8e59d71279b25a934a9612b099f743b8912800b29dd00e0780bcba69a`

Original v0.1 package is preserved. No keys or production configuration touched.
