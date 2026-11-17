# F6 local execution — recorded results (2026-11-17)

- Platform: Linux container, CPython 3.13.5, two test worker OS processes; separate `/tmp` and `/dev/shm` mounts in the distinct-device case.
- Command: `python -m unittest discover -s tests -p 'test*.py' -q`
- Outcome: `Ran 98 tests in 14.556s` / `OK`.
- Additional command: ten repetitions of `TestF6SeparateRoots.test_two_distinct_filesystem_mounts_can_adopt_the_same_intent`.
- Outcome: `Ran 10 tests in 8.714s` / `OK`; `CROSS_MOUNT_STRESS {run: 10, failures: 0, errors: 0, skipped: 0}`.
- Baseline unchanged: `r2a0.py` SHA-256 `58b8be40099d0fbb82bad91b322160e9d619b0e08c656ab5261b9576e85c88d9`.
- New read-only comparator: SHA-256 `2cae332b99d2db6a59eb6021c7fb3fc08294bdd6db621c05750dcbccb9b5cc8c`.
- New F6 tests: SHA-256 `67964eb19206d6767f3089f46ffd6930fb1051602fd6399238ffb4927ac78f15`.
- Not measured: two physical disks, two hosts, independent administrators, live native GitHub checks or merges.

**This record is candidate-authored local test evidence; not independent verification or an admission PASS.**
