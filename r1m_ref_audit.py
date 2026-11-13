"""R1m auditor: compare independent job outputs and read committed sandbox refs.

The auditor has only contents:read, never writes. This verifies what GitHub's
publicly observable ref namespace actually contains, not provider consensus
internals, independently held publisher keys or production safety.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re

from r1m_github_ref_cas import (
    REPO, BRANCH, PHASES, ROLES, call, read_existing, ref_name, require
)


def audit_outcomes(left: dict, right: dict) -> None:
    require(left["baseline"] in ("CREATED", "EXISTING_AFTER_422") and
            right["baseline"] in ("CREATED", "EXISTING_AFTER_422"), "BAD_BASELINE_OUTCOME")
    require(sorted([left["baseline"], right["baseline"]]) ==
            ["CREATED", "EXISTING_AFTER_422"], "NO_UNIQUE_CREATE_OBSERVED")
    require(left["lostreply"] == "OBSERVED_AFTER_SIMULATED_LOST_REPLY",
            "LOST_REPLY_EVIDENCE_MISSING")
    require(right["lostreply"] in ("CREATED", "EXISTING_AFTER_422"),
            "WIN_SECOND_PHASE_OUTCOME_BAD")


def main() -> None:
    env = os.environ
    require(env.get("GITHUB_REPOSITORY") == REPO and
            env.get("GITHUB_REF") == "refs/heads/" + BRANCH and
            env.get("GITHUB_EVENT_NAME") == "push", "AUDITOR_CONTEXT")
    sha = env.get("GITHUB_SHA")
    require(type(sha) is str and re.fullmatch(r"[0-9a-f]{40}", sha) is not None,
            "AUDITOR_SHA")
    run_id = env.get("GITHUB_RUN_ID")
    attempt = env.get("GITHUB_RUN_ATTEMPT")
    require(type(run_id) is str and re.fullmatch(r"[0-9]{6,15}", run_id) is not None
            and type(attempt) is str and re.fullmatch(r"[1-9][0-9]*", attempt) is not None,
            "AUDITOR_RUN_ID")
    token = env.get("R1M_GITHUB_TOKEN")
    require(type(token) is str and len(token) > 20, "AUDITOR_TOKEN")
    left = {
        "baseline": env.get("R1M_LINUX_BASELINE"),
        "lostreply": env.get("R1M_LINUX_LOST")
    }
    right = {
        "baseline": env.get("R1M_WINDOWS_BASELINE"),
        "lostreply": env.get("R1M_WINDOWS_LOST")
    }
    audit_outcomes(left, right)
    info = {"run_id": run_id, "run_attempt": attempt, "sha": sha}
    references = []
    for phase in PHASES:
        for role in ROLES:
            ref = ref_name(info, phase, "ready", role)
            require(read_existing(ref, sha, token), "READY_REF_MISSING_" + ref)
            references.append("refs/tags/" + ref)
        claim = ref_name(info, phase, "claim")
        require(read_existing(claim, sha, token), "CLAIM_REF_MISSING_" + claim)
        references.append("refs/tags/" + claim)

    report = {
        "schema": "r1m-cross-runner-audit-v1",
        "source_repo": REPO, "source_sha": sha,
        "run_id": run_id, "run_attempt": attempt,
        "linux_baseline": left["baseline"],
        "windows_baseline": right["baseline"],
        "linux_lost_reply_simulated": left["lostreply"],
        "windows_lost_reply": right["lostreply"],
        "ready_and_claim_refs_verified": references,
        "linux_windows_separate_jobs": True,
        "claim_created_count_baseline": 1,
        "claim_conflict_verified_count_baseline": 1,
        "lost_reply_repost_attempted": False,
        "no_github_check_post": True,
        "no_permanent_credential_or_governance_claim": True,
        "source_token_custody_independent": False,
        "globally_linearizable_db_proven": False,
        "github_git_refs_consensus_internals_proven": False,
        "production_trust": "NO_GO",
        "verdict": "BOUNDED_CROSS_RUNNER_REF_CAS_PASS"
    }
    dest = Path("r1m-evidence")
    dest.mkdir(exist_ok=True)
    (dest / "auditor.json").write_text(json.dumps(report, sort_keys=True, indent=2)+"\n",
                                       encoding="utf-8")
    print("R1M_LINUX_WINDOWS_TWO_JOB_AUDIT=PASS")
    print("R1M_BASELINE_ONE_CREATE_ONE_CONFLICT=PASS")
    print("R1M_ALL_SIX_REF_READBACK=PASS")
    print("R1M_LOST_REPLY_SIMULATED_RECONCILED=PASS")
    print("R1M_NO_CHECK_POST=1")
    print("R1M_PRODUCTION_TRUST=NO_GO")


if __name__ == "__main__":
    main()
