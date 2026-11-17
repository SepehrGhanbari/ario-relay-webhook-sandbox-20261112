# R2a-0 v0.6 local regression record

- Date: 2026-11-17
- Platform: Linux, Python 3.13.5
- Scope: F5 same-host, cross-process orphan recovery
- Executed: `python -m unittest discover -s tests -p 'test*.py' -q`
- Result: **90 tests passed**
- Additional: 20 paired process races passed (10 F5a + 10 F5b repeats)
- Source: **unchanged** v0.5 `r2a0.py`
- Not executed: native GitHub merge/check experiments, independent custody, power cut, multi-host
- Verdict: `LOCAL_RACE_TEST_PASS / LIVE_R2A0_NOT_RUN / P0_HOLD / PRODUCTION_NO_GO`
