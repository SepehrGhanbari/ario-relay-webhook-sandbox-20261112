# Source and scope

## Canonical local input documents (provided 2026-11-17)

- `R2A0_RESPONSE_AND_PLAN_2026-11-17_EN (1).md` — **CANONICAL** R2a-0; preflight and scenarios Sc1/Sc2/Sk/Sn/Sc3/Sc4/Se1.
- `R2A_EXPERIMENT_PLAN_2026-11-17_EN (2).md` — superseded design, historical only.
- `ARIO_P0_MERGE_TRUST_ASSESSMENT_2026-11-17_EN (2).md` — design comparison D1/D2/D3; not a live code audit.

## Existing direct GitHub lab evidence, re-read 2026-11-17

- R1i final report, immutable source: https://github.com/SepehrGhanbari/ario-relay-webhook-sandbox-20261112/blob/157ba9a131deab67f188675c06bdd81dd775e1f7/evidence/r1i/2026-11-13/R1I_FINAL_LAB_REPORT.md
- Lab target PR #14: https://github.com/SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a/pull/14 — still OPEN/DRAFT at HEAD `1c55dad097fc5544c8b36bc02ebb6eeb74c8a6e8` (2026-11-17 readback).
- Lab target PR #13: https://github.com/SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a/pull/13 — still OPEN/DRAFT at HEAD `ffd54a8b8ab95236ebade9fc2e30de7f5981aa23` (2026-11-17 readback).
- Lab App ID in R1i: `5747504`. Required context historically `ario-r1d-lab-app-gate`. Do **not** assume current effective protection from that old report. Re-fetch rules before using any new experiment branch.

## External API behavior that still needs native experimental confirmation

- https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks
- https://docs.github.com/en/webhooks/using-webhooks/best-practices-for-using-webhooks
- https://docs.github.com/en/rest/checks/runs
- https://docs.github.com/en/rest/pulls/pulls

Nothing in this pack claims successful execution of R2a-0 or changes Ario production governance.
