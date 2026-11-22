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
import xml.etree.ElementTree as ET

SOURCE_HEAD = "14f9da37673b04f7fce90b720a94c27144c15667"
SOURCE_TREE = "d5a04b86b08dae838c0ddc80d5b1d02a0d467343"
OLD_HEAD = "beb971ecdad229e153e50d1516db1d8aeca61c59"
OLD_VALIDATOR_BLOB = "614e6317af90b02058ac9c9c59eac8c7ea450fde"
NEW_VALIDATOR_BLOB = "8e2dd9f2607cbc944c2e1f550cf2bd7679a96211"
OLD_RAW_URL = ("https://raw.githubusercontent.com/SepehrGhanbari/Ario/"
               + OLD_HEAD + "/implementation/research/guard_v2_manual_report.py")

def blob_id(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


EXPECTED_71_IDS_SHA256 = "230ed51efa79e71a4c8ccf066fc323dc3125ce835d8d03088afa415f98813573"
EXPECTED_42_RED_IDS_SHA256 = "aa76a48cd48c2b96c6b7febd6b1d69a98a4649a74a646a7f9b0842e40f3d22f3"
EXACT_ASSERTION_LABELS = frozenset({
    "linked_pr_ci_observed_but_no_merge_permission",
    "pr_head_changed_between_reads",
    "failed_pr_run_never_counts_as_success",
    "same_sha_push_success_cannot_mask_failed_pr",
    "incomplete_ci_page_fails_closed",
    "comment_deleted_between_snapshots",
    "stable_review_samples_not_attestation",
    "preexisting_tamper_is_not_detectable_by_dual_sampling",
    "read_only_query_templates_only",
    "completed_manual_read_still_hold",
    "manual_report_refuses_merge_claim",
    "manual_report_refuses_identity_drift",
    "manual_report_refuses_inconsistent_sample",
    "manual_report_never_accepts_authority_true",
})


def git_measure(impl: Path) -> dict:
    """Bind claimed identity to supplied Git repo; no independent attestation."""
    def git(*args):
        p = subprocess.run(["git", "-C", str(impl), *args],
                           capture_output=True, text=True, timeout=20, check=False)
        if p.returncode:
            raise AssertionError("INVALID_GIT_WORKTREE: " + p.stderr[-250:])
        return p.stdout.strip()
    root = Path(git("rev-parse", "--show-toplevel")).resolve()
    if impl.resolve() != (root / "implementation").resolve():
        raise AssertionError("WRONG_IMPLEMENTATION_ROOT")
    source = git("rev-parse", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    if source != SOURCE_HEAD or tree != SOURCE_TREE:
        raise AssertionError("SOURCE_IDENTITY_OR_TREE_DRIFT")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise AssertionError("TRACKED_SOURCE_CHANGED")
    return {"head": source, "tree": tree, "identity": "LOCAL_GIT_OBJECT_ONLY"}


def junit(path: Path) -> dict:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if len(suites) != 1:
        raise AssertionError("JUNIT_SINGLE_SUITE_REQUIRED")
    suite = suites[0]
    cases = list(suite.findall("testcase"))
    ids, failed, errors, skipped = [], [], [], []
    for t in cases:
        a = t.get("classname")
        b = t.get("name")
        if not a or not b:
            raise AssertionError("JUNIT_ID_MISSING")
        name = a + "::" + b
        ids.append(name)
        if t.find("failure") is not None:
            failed.append(name)
        if t.find("error") is not None:
            errors.append(name)
        if t.find("skipped") is not None:
            skipped.append(name)
    if len(set(ids)) != len(ids):
        raise AssertionError("DUPLICATE_TEST_ID")
    for label, actual in (("tests", ids), ("failures", failed),
                          ("errors", errors), ("skipped", skipped)):
        if int(suite.get(label, "-1")) != len(actual):
            raise AssertionError("JUNIT_DECLARED_COUNT_MISMATCH_" + label)
    def digest(values):
        return hashlib.sha256(("\n".join(sorted(values)) + "\n").encode("utf-8")).hexdigest()
    return {"ids": set(ids), "failed_ids": set(failed),
            "cases": len(ids), "failed": len(failed),
            "errors": len(errors), "skipped": len(skipped),
            "ids_sha256": digest(ids), "red_sha256": digest(failed)}


def upstream_junit_check(path: Path) -> dict:
    x = junit(path)
    if x["cases"] != 197 or x["failed"] or x["errors"] or x["skipped"]:
        raise AssertionError("UPSTREAM_COLLECTION_NOT_EXACTLY_197_PASSES")
    return {"passed": 197, "fail": 0, "skip": 0, "error": 0}


def validate_report(path: Path, run_id: str, attempt: str) -> dict:
    z = json.loads(path.read_text(encoding="utf-8"))
    if (not run_id.isdecimal() or not attempt.isdecimal()
            or z.get("run_id") != run_id or z.get("run_attempt") != attempt
            or z.get("source_head") != SOURCE_HEAD or z.get("source_tree") != SOURCE_TREE
            or z.get("outcome") != "PASS_LAB_WITH_UPSTREAM_HOLDS"
            or z.get("upstream_cases", {}).get("passed") != 197
            or z.get("synthetic", {}).get("count") != 14
            or z.get("mutation_test", {}).get("case_digest") != EXPECTED_71_IDS_SHA256
            or z.get("mutation_test", {}).get("red_digest") != EXPECTED_42_RED_IDS_SHA256):
        raise AssertionError("STALE_OR_INCOMPLETE_SUCCESS_REPORT")
    return z


def falsify_harness() -> None:
    """Prove standalone fake repo, short JUnit and stale report are rejected."""
    with tempfile.TemporaryDirectory() as folder:
        p = Path(folder)
        (p / "implementation").mkdir()
        try:
            git_measure(p / "implementation")
        except (AssertionError, OSError):
            pass
        else:
            raise AssertionError("FAKE_SOURCE_ACCEPTED")
        xml = p / "partial.xml"
        xml.write_text('<testsuite tests="1" failures="0" errors="0" skipped="0">'
                       '<testcase classname="a" name="x"/></testsuite>', encoding="utf-8")
        try:
            upstream_junit_check(xml)
        except AssertionError:
            pass
        else:
            raise AssertionError("TRUNCATED_TEST_COLLECTION_ACCEPTED")
        old = p / "report.json"
        old.write_text(json.dumps({"run_id": "1", "run_attempt": "1",
                                  "outcome": "PASS_LAB_WITH_UPSTREAM_HOLDS",
                                  "source_head": SOURCE_HEAD, "source_tree": SOURCE_TREE}))
        try:
            validate_report(old, "1", "2")
        except AssertionError:
            pass
        else:
            raise AssertionError("OLD_ATTEMPT_REPORT_ACCEPTED")

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
    with tempfile.TemporaryDirectory(prefix="guard-v2-exact-red-green-") as d:
        red_xml, green_xml = Path(d) / "red.xml", Path(d) / "green.xml"
        try:
            target.write_bytes(legacy)
            red = subprocess.run(cmd + ["--junitxml", str(red_xml)],
                                 cwd=str(impl), env=env, capture_output=True,
                                 text=True, timeout=120, check=False)
        finally:
            target.write_bytes(original)
        if blob_id(target.read_bytes()) != NEW_VALIDATOR_BLOB:
            raise AssertionError("VALIDATOR_RESTORE_MISMATCH")
        green = subprocess.run(cmd + ["--junitxml", str(green_xml)],
                               cwd=str(impl), env=env, capture_output=True,
                               text=True, timeout=120, check=False)
        red_cases, green_cases = junit(red_xml), junit(green_xml)
    if (red.returncode != 1 or green.returncode != 0
            or red_cases["cases"] != 71 or green_cases["cases"] != 71
            or red_cases["failed"] != 42 or green_cases["failed"] != 0
            or red_cases["errors"] or green_cases["errors"]
            or red_cases["skipped"] or green_cases["skipped"]
            or red_cases["ids"] != green_cases["ids"]):
        raise AssertionError("RED_GREEN_COVERAGE_OR_OUTCOME_MISMATCH")
    print("CANDIDATE_IDS_FOR_INDEPENDENT_PIN_REVIEW " + json.dumps({
        "all_71_ids_sha256": green_cases["ids_sha256"],
        "exact_42_red_failure_ids_sha256": red_cases["red_sha256"],
        "collection_size": green_cases["cases"],
        "red_failed": red_cases["failed"],
    }, sort_keys=True))
    if (green_cases["ids_sha256"] != EXPECTED_71_IDS_SHA256
            or red_cases["red_sha256"] != EXPECTED_42_RED_IDS_SHA256):
        raise AssertionError("UNRATIFIED_EXACT_TEST_ID_SET")
    return {"outcome": "RED_TO_GREEN_IDENTICAL_CASE_SET",
            "red_exit": red.returncode, "green_exit": green.returncode,
            "red_summary": red.stdout.strip().splitlines()[-1],
            "green_summary": green.stdout.strip().splitlines()[-1],
            "case_digest": green_cases["ids_sha256"],
            "red_digest": red_cases["red_sha256"],
            "expected_failures": 42, "full_cases": 71,
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

    if set(verdicts) != EXACT_ASSERTION_LABELS:
        raise AssertionError("SYNTHETIC_GROUPS_SHORTENED_OR_DRIFTED")
    return {"count": len(verdicts), "scenarios": verdicts,
            "disposition": "SYNTHETIC_HOLD_ONLY",
            "fixture_reuse": True, "independent_designs": "NOT_ESTABLISHED"}

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


def upstream_holds() -> dict:
    from test_ario_repo_self_audit import Fake as FakeCi, call as ci_call
    from test_guard_v2_trusted_manual import FakeRest, SOURCE_SHA
    from test_guard_v2_review_graph import FakeGraphQL, HEAD
    from research import guard_v2_trusted_manual as manual
    from research import guard_v2_manual_report as validator
    fake = FakeCi()
    queued = copy.deepcopy(fake.runs["workflow_runs"][0])
    queued.update(id=101, status="queued", conclusion=None)
    fake.runs["workflow_runs"].append(queued)
    fake.runs["total_count"] = 2
    observation = ci_call(fake)
    stale_green = observation.get("required_check_observation") == "REPORTED_SUCCESS_BY_LINKED_PR_RUN"
    completed = manual.observe(295, HEAD, rest_reader=FakeRest(),
                                graph_reader=FakeGraphQL(), source_sha=SOURCE_SHA)
    completed.pop("review_graph_reason", None)
    with tempfile.TemporaryDirectory() as d:
        report_path = Path(d) / "missing_field.json"
        report_path.write_text(json.dumps(completed, ensure_ascii=True), encoding="utf-8")
        missing_success_field_accepted = validator.main(
            [str(report_path), "295", HEAD, SOURCE_SHA, "0"]) == 0
    return {
        "old_linked_green_new_same_head_queued": {
            "reproduced": stale_green, "status": "UPSTREAM_HOLD_NOT_FIXED"},
        "missing_success_review_graph_reason": {
            "reproduced": missing_success_field_accepted, "status": "UPSTREAM_HOLD_NOT_FIXED"},
        "last_sample_race": "UNKNOWN_NOT_ATOMIC",
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--implementation")
    ap.add_argument("--output")
    ap.add_argument("--upstream-junit")
    ap.add_argument("--verify-report", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        falsify_harness()
        print('HARNESS_FAIL_CLOSED_CONTROLS_3_PASS')
        return 0
    run_id, attempt = os.environ.get("GITHUB_RUN_ID", ""), os.environ.get("GITHUB_RUN_ATTEMPT", "")
    if not run_id.isdecimal() or not attempt.isdecimal() or not args.output:
        raise SystemExit("GITHUB_RUN_OR_OUTPUT_REQUIRED")
    out = Path(args.output)
    if args.verify_report:
        print(json.dumps(validate_report(out, run_id, attempt), sort_keys=True))
        return 0
    if not args.implementation or not args.upstream_junit:
        raise SystemExit("IMPLEMENTATION_AND_JUNIT_REQUIRED")
    impl = Path(args.implementation).resolve(strict=True)
    identity = git_measure(impl)
    upstream = upstream_junit_check(Path(args.upstream_junit))
    report = {
        "schema": "ARIO-GUARD-V2-ISOLATED-CLOUD-LAB-0.2",
        "source_head": identity["head"], "source_tree": identity["tree"],
        "local_git_object_identity_only": True,
        "run_id": run_id, "run_attempt": attempt,
        "sandbox_only": True, "has_real_signer": False, "has_real_key": False,
        "has_merge_authority": False, "has_trust_authority": False,
        "outcome": "UNASSESSED", "upstream_cases": upstream,
    }
    report["synthetic"] = synthetic_scenarios(impl)
    report["upstream_holds"] = upstream_holds()
    report["mutation_test"] = red_green(impl)
    report["public_read_only"] = live_probe(impl)
    report["outcome"] = "PASS_LAB_WITH_UPSTREAM_HOLDS"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as f:
        f.write(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=True) + "\n")
    validate_report(out, run_id, attempt)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
