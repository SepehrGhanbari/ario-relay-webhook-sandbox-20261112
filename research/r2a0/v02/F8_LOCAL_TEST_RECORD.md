# F8 — local evidence record (not native GitHub enforcement)

Date: 2026-11-17

Baseline F7 unchanged: 121/121 PASS on Python 3.13/Linux.
F8 test-first RED on original F7: see `F8_RED_ON_F7_LOG.txt` (candidate tests deliberately fail).
F8 full local final: 129/129 PASS, including eight F8 tests and real two-OS-process public CLI race.

Command: `python -m unittest discover -s tests -p 'test*.py' -q`

**Evidence caveat:** candidate-authored tests are not independent merge certification. Shared SQLite does not establish distributed consensus. Private helper remains callable with same-user Python code.

| File | SHA-256 | Bytes | Git blob SHA-1 |
|---|---|---:|---|
| `r2a0.py` | `e20ab20fcfdeef8b865187bf17fb98b7ac6e76e28273f59597f34e154e392319` | 39754 | `da9db71de7577fa9d67eaf08dd6e32e8cd200e2a` |
| `f7_coordinator.py` | `0234bfdb9fecc0aef8627159dfd2a19e2b9a6f600f834b5832f546484600da97` | 12590 | `a128dae7eca09ae445246018b156fc10237f8ee1` |
| `tests/test_r2a0.py` | `9922ec0594dae385e21ada7e889391e71dd7222942ef6b68ab0e7d7f10828f8e` | 51724 | `34a1503e64f5032997308cc6e2d3aca68bb57197` |
| `tests/test_f6_split_brain.py` | `818722bb1dc3a2ed1aeca7ccc759d0a3eb6ede2390a2491d21f358fe9d871d79` | 9116 | `17ffb56ffa5ce67915cfb062d8488aee69ad02e4` |
| `tests/test_f7_coordinator.py` | `97788ef867f404031a14a8d8a9637e931e10a49580d0774ff7a2e1b6f7ec41b5` | 17300 | `2f26f5dbcf0b74c60361630035fe79c034c9a0c9` |
| `tests/test_f8_required_coordinator.py` | `af67329e7228f3e71b03ee3334d272bda2f716b35fef01b8eef82061a46ee7ef` | 8004 | `7db33b2200befa063f23ec3eaf193eb83b6a12ae` |
| `RUNBOOK.md` | `5d99fb699edc127f3ee3aaf1236b2093c80c7aa70fbb931821325fad124e1ef1` | 12136 | `8c600f8f9967f5d25d2f8b94127c9a40c60c2b82` |
| `README.md` | `c962f18748cb790df57e6c65dc26e318d124fa73f01d615e4616aa60f6e13582` | 5007 | `9fe10763269c69e37855d7b187761386eea9b58e` |
| `F8_MANDATORY_COORDINATOR_REVIEW.md` | `e6cabce9aecd63925e5a0ca207a5d61f1963d8495863ad745389fee40b5f5948` | 4804 | `e575f7d666664de5fe8dfcb7956915dacdc66197` |
| `F8_TRAE_INDEPENDENT_REVIEW_TASK.md` | `436d5c30d080defadeadf9b763ab1a27c1df6e853032ad6b1ac6b0c8d2c7d62e` | 3712 | `481c8486d17bd417471fbbecd85556098ed60036` |

No production or native GitHub merge tests were run. `DRAFT/P0_HOLD/PRODUCTION=NO_GO`.
