#!/usr/bin/env python3
"""Independent no-token GitHub-runner probe against the exact Ario PR #295 source.

Everything operates in disposable runner space. Negative controls are synthetic.
NEVER a trusted witness, check publisher, merge authority, signer or real key holder.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request

SOURCE_HEAD = "14f9da37673b04f7fce90b720a94c27144c15667"
SOURCE_TREE = "d5a04b86b08dae838c0ddc80d5b1d02a0d467343"
OLD_HEAD = "beb971ecdad229e153e50d1516db1d8aeca61c59"
OLD_VALIDATOR_BLOB = "614e6317af90b02058ac9c9c59eac8c7ea450fde"
NEW_VALIDATOR_BLOB = "8e2dd9f2607cbc944c2e1f550cf2bd7679a96211"
OLD_RAW_URL = ("https://raw.githubusercontent.com/SepehrGhanbari/Ario/"
               + OLD_HEAD + "/implementation/research/guard_v2_manual_report.py")

def blob_id(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()

def red_green(impl: Path) -> dict:
    """Run actual new tests on the pinned OLD validator (RED), then CURRENT (GREEN)."""
    target = impl / "research" / "guard_v2_manual_report.py"
    original = target.read_bytes()
    if blob_id(original) != NEW_VALIDATOR_BLOB:
        raise AssertionError("CURRENT_VALIDATOR_BLOB_DRIFT")
    req = urllib.request.Request(OLD_RAW_URL, headers={"User-Agent": "Ario-Cloud-Guard-Lab"})
    with urllib.request.urlopen(req, timeout=25) as response:
        legacy = response.read(100001)
    if len(legacy) > 100000 or blob_id(legacy) != OLD_VALIDATOR_BLOB:
        raise AssertionError("OLD_VALIDATOR_BLOB_MISMATCH")
    cmd = [sys.executable, "-B", "-m", "pytest", "-p", "no:cacheprovider",
           "-q", "tests/test_guard_v2_r21a_red_green.py"]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    for name in ("GITHUB_TOKEN", "GH_TOKEN", "ARIO_GITHUB_READ_TOKEN",
                 "ARIO_TRUSTED_READ_TOKEN", "HF_TOKEN"):
        env.pop(name, None)
    try:
        target.write_bytes(legacy)
        red = subprocess.run(cmd, cwd=str(impl), env=env, capture_output=True,
                             text=True, timeout=120, check=False)
    finally:
        target.write_bytes(original)
    if blob_id(target.read_bytes()) != NEW_VALIDATOR_BLOB:
        raise AssertionError("VALIDATOR_RESTORE_MISMATCH")
    green = subprocess.run(cmd, cwd=str(impl), env=env, capture_output=True,
                           text=True, timeout=120, check=False)
    if red.returncode != 1 or "failed" not in red.stdout.lower():
        raise AssertionError("NEGATIVE_CONTROL_MUST_FAIL: " + red.stdout[-900:])
    if green.returncode != 0 or "passed" not in green.stdout.lower():
        raise AssertionError("FIXED_VALIDATOR_MUST_PASS: " + green.stdout[-900:])
    return {"outcome": "RED_THEN_GREEN",
            "red_exit": red.returncode, "green_exit": green.returncode,
            "red_summary": red.stdout.strip().splitlines()[-1],
            "green_summary": green.stdout.strip().splitlines()[-1],
            "legacy_blob": OLD_VALIDATOR_BLOB, "current_blob": NEW_VALIDATOR_BLOB}

def synthetic_scenarios(impl: Path) -> dict:
    sys.path.insert(0, str(impl))
    sys.path.insert(0, str(impl / "tests"))
    from test_ario_repo_self_audit import Fake as FakeCi, call as ci_call
    from test_guard_v2_review_graph import FakeGraphQL, original, pin
    from test_guard_v2_trusted_manual import FakeRest, SOURCE_SHA
    from research import guard_v2_review_graph as graph
    from research import guard_v2_trusted_manual as manual
    from research import guard_v2_manual_report as validator

    verdicts: dict[str, str] = {}
    def check(label: str, condition: bool) -> None:
        if not condition:
            raise AssertionError("SYNTHETIC_CASE_FAILED: " + label)
        verdicts[label] = "PASS"

    ci = ci_call(FakeCi())
    check("linked_pr_ci_observed_but_no_merge_permission",
          ci.get("required_check_observation") == "REPORTED_SUCCESS_BY_LINKED_PR_RUN"
          and ci.get("status") == "UNKNOWN" and ci.get("merge_authorized") is False)

    changed = FakeCi()
    changed.next_pr = copy.deepcopy(changed.pr)
    changed.next_pr["head"]["sha"] = "f" * 40
    ci = ci_call(changed)
    check("pr_head_changed_between_reads",
          ci.get("reason") == "PR_CHANGED_BETWEEN_SAMPLES"
          and ci.get("required_check_observation") == "NOT_CONFIRMED")

    failed = FakeCi()
    failed.runs["workflow_runs"][0]["conclusion"] = "failure"
    ci = ci_call(failed)
    check("failed_pr_run_never_counts_as_success",
          ci.get("required_check_observation") == "NOT_CONFIRMED")

    push = FakeCi()
    push.checks["check_runs"][0]["details_url"] = (
        "https://github.com/SepehrGhanbari/Ario/actions/runs/200/job/1")
    push.checks["check_runs"].append({
        "id": 3, "name": "m0-regression", "head_sha": push.pr["head"]["sha"],
        "status": "completed", "conclusion": "failure", "app": {"id": 15368},
        "details_url": "https://github.com/SepehrGhanbari/Ario/actions/runs/100/job/3",
    })
    push.checks["total_count"] = 3
    push.runs["workflow_runs"][0]["conclusion"] = "failure"
    ci = ci_call(push)
    check("same_sha_push_success_cannot_mask_failed_pr",
          ci.get("required_check_observation") == "NOT_CONFIRMED")

    truncated = FakeCi()
    truncated.checks["total_count"] += 1
    ci = ci_call(truncated)
    check("incomplete_ci_page_fails_closed",
          ci.get("reason") == "CHECKS_INCOMPLETE"
          and ci.get("required_check_observation") == "NOT_CONFIRMED")

    a = original()
    b = copy.deepcopy(a)
    b["comments"].clear()
    review = graph.compare_twice(pin(), FakeGraphQL(a, b))
    check("comment_deleted_between_snapshots",
          review.get("reason") == "REVIEW_GRAPH_CHANGED_BETWEEN_SAMPLES"
          and review.get("merge_authorized") is False)

    graph_reader = FakeGraphQL()
    stable = graph.compare_twice(pin(), graph_reader)
    check("stable_review_samples_not_attestation",
          stable.get("sample_status") == "SAMPLED_STABLE_UNATTESTED"
          and stable.get("independent_custody") == "NOT_ESTABLISHED"
          and stable.get("merge_authorized") is False)
    tampered = copy.deepcopy(a)
    tampered["comments"][0]["body"] = "synthetic pre-sampling forgery"
    look = graph.compare_twice(pin(), FakeGraphQL(tampered, tampered))
    check("preexisting_tamper_is_not_detectable_by_dual_sampling",
          look.get("sample_status") == "SAMPLED_STABLE_UNATTESTED"
          and look.get("independent_custody") == "NOT_ESTABLISHED")
    check("read_only_query_templates_only", all(
        query.startswith("query ArioReviewEvidence")
        and "mutation" not in query.lower() for query in graph.QUERIES.values()))

    graph_head = pin()["head_sha"]
    complete = manual.observe(295, graph_head, rest_reader=FakeRest(),
                              graph_reader=FakeGraphQL(), source_sha=SOURCE_SHA)
    with tempfile.TemporaryDirectory(prefix="ario-guard-v2-test-") as d:
        output = Path(d) / "report.json"
        def validate(payload: dict, exit_code: int) -> int:
            output.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
            return validator.main([str(output), "295", graph_head, SOURCE_SHA,
                                   str(exit_code)])
        check("completed_manual_read_still_hold",
              complete.get("disposition") == "HOLD"
              and complete.get("status") == "UNKNOWN"
              and complete.get("merge_authorized") is False
              and validate(complete, 0) == 0)
        injected = dict(complete, reason="OK_TO_MERGE")
        check("manual_report_refuses_merge_claim",
              validate(injected, 0) == 2)
        mismatch = copy.deepcopy(complete)
        mismatch["live_identity"]["head_sha"] = "e" * 40
        check("manual_report_refuses_identity_drift",
              validate(mismatch, 0) == 2)
        partial = copy.deepcopy(complete)
        partial["second_digest"] = "0" * 64
        check("manual_report_refuses_inconsistent_sample",
              validate(partial, 0) == 2)
        fake_auth = dict(complete, merge_authorized=True)
        check("manual_report_never_accepts_authority_true",
              validate(fake_auth, 0) == 2)

    return {"count": len(verdicts), "scenarios": verdicts,
            "disposition": "SYNTHETIC_HOLD_ONLY"}

def live_probe(impl: Path) -> dict:
    """Only unauthenticated public API GETs, optional/advisory; never gate on rate limits."""
    from ario_repo_self_audit import GitHubReadOnly, observe
    try:
        x = observe(295, SOURCE_HEAD, reader=GitHubReadOnly(token=None))
        if x.get("status") != "UNKNOWN" or x.get("merge_authorized") is not False:
            raise AssertionError("LIVE_READ_CLAIMED_AUTHORITY")
        return {"status": x.get("status"), "reason": x.get("reason"),
                "required_check_observation": x.get("required_check_observation"),
                "source_delivery": x.get("source_delivery"),
                "execution_attestation": x.get("execution_attestation"),
                "authority": "NONE",
                "note": "Unauthenticated public GET, not independent attestation"}
    except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
        return {"status": "UNKNOWN", "reason": type(exc).__name__,
                "authority": "NONE",
                "note": "Unauthenticated optional read unavailable; no positive claim"}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--implementation", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    impl = Path(args.implementation).resolve()
    if (not (impl / "research" / "guard_v2_manual_report.py").is_file()
            or not (impl / "tests" / "test_ario_repo_self_audit.py").is_file()):
        raise SystemExit("MISSING_PINNED_ARIO_SOURCE")
    report = {
        "schema": "ARIO-GUARD-V2-ISOLATED-CLOUD-LAB-0.1",
        "source_head": SOURCE_HEAD, "source_tree": SOURCE_TREE,
        "sandbox_only": True, "has_real_signer": False, "has_real_key": False,
        "has_merge_authority": False, "has_trust_authority": False,
        "outcome": "HOLD_UNTIL_ASSERTIONS_COMPLETE",
    }
    report["synthetic"] = synthetic_scenarios(impl)
    report["mutation_test"] = red_green(impl)
    report["public_read_only"] = live_probe(impl)
    report["outcome"] = "PASS_SYNTHETIC_ONLY"
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
                   encoding="utf-8")
    print(json.dumps(report, sort_keys=True, ensure_ascii=True))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as f:
            f.write("## Ario Guard V2 isolated cloud rehearsal\n\n")
            f.write("**PASS_SYNTHETIC_ONLY — NO TRUST / NO MERGE / NO SIGNER**\n\n")
            f.write(f"- Source HEAD: \`{SOURCE_HEAD}\`\n")
            f.write(f"- Synthetic scenarios: {report['synthetic']['count']} passed\n")
            f.write(f"- Mutation: {report['mutation_test']['red_summary']} → "
                    f"{report['mutation_test']['green_summary']}\n")
            f.write("- Live anonymous public read: "
                    f"{report['public_read_only'].get('reason')} (UNKNOWN/HOLD)\n")
            f.write("- No protected-main manual workflow was installed or exercised.\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
