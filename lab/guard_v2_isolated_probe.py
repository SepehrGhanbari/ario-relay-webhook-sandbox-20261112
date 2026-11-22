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


EXPECTED_197_IDS_SHA256 = "b41e2aa5ebc5056993e9efa1678725db09a51ecf33498372e81e4c247bb2e929"
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


def git_clean(root: Path) -> None:
    """Reject tracked edits, untracked files AND Git-ignored executable input."""
    p = subprocess.run(["git", "-C", str(root), "status", "--porcelain=v1",
                        "--untracked-files=all", "--ignored=matching"],
                       capture_output=True, text=True, timeout=20, check=False)
    if p.returncode:
        raise AssertionError("GIT_STATUS_FAILED")
    if p.stdout.strip():
        raise AssertionError("UNTRACKED_IGNORED_OR_MODIFIED_SOURCE: " + p.stdout[:500])


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
    git_clean(root)
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
    if (x["cases"] != 197 or x["failed"] or x["errors"] or x["skipped"]
            or x["ids_sha256"] != EXPECTED_197_IDS_SHA256):
        print("OBSERVED_197_CASE_ID_SHA256 " + x["ids_sha256"])
        raise AssertionError("UPSTREAM_197_CASE_IDENTITY_OR_OUTCOME_MISMATCH")
    return {"passed": 197, "fail": 0, "skip": 0, "error": 0,
            "ids_sha256": x["ids_sha256"], "case_ids": sorted(x["ids"])}


def case_digest(values: list[str]) -> str:
    return hashlib.sha256(("\n".join(sorted(values)) + "\n").encode("utf-8")).hexdigest()


def exact_keys(value: object, keys: set[str], label: str) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise AssertionError("REPORT_KEY_SET_" + label)
    return value


def valid_example(upstream: dict, run_id: str, attempt: str) -> dict:
    """Entirely valid fixture for independent negative controls."""
    return {
        "schema": "ARIO-GUARD-V2-ISOLATED-CLOUD-LAB-0.2",
        "source_head": SOURCE_HEAD, "source_tree": SOURCE_TREE,
        "local_git_object_identity_only": True,
        "run_id": run_id, "run_attempt": attempt,
        "sandbox_only": True, "has_real_signer": False, "has_real_key": False,
        "has_merge_authority": False, "has_trust_authority": False,
        "outcome": "PASS_LAB_WITH_UPSTREAM_HOLDS", "upstream_cases": upstream,
        "synthetic": {
            "count": 14, "scenarios": {x: "PASS" for x in EXACT_ASSERTION_LABELS},
            "disposition": "SYNTHETIC_HOLD_ONLY", "fixture_reuse": True,
            "independent_designs": "NOT_ESTABLISHED",
        },
        "upstream_holds": {
            "old_linked_green_new_same_head_queued":
                {"reproduced": True, "status": "UPSTREAM_HOLD_NOT_FIXED"},
            "missing_success_review_graph_reason":
                {"reproduced": True, "status": "UPSTREAM_HOLD_NOT_FIXED"},
            "last_sample_race": "UNKNOWN_NOT_ATOMIC",
        },
        "mutation_test": {
            "outcome": "RED_TO_GREEN_IDENTICAL_CASE_SET",
            "red_exit": 1, "green_exit": 0,
            "red_summary": "42 failed, 29 passed in 0.10s",
            "green_summary": "71 passed in 0.10s",
            "case_digest": EXPECTED_71_IDS_SHA256,
            "red_digest": EXPECTED_42_RED_IDS_SHA256,
            "expected_failures": 42, "full_cases": 71,
            "legacy_blob": OLD_VALIDATOR_BLOB,
            "current_blob": NEW_VALIDATOR_BLOB,
        },
        "public_read_only": {
            "status": "UNKNOWN", "authority": "NONE",
            "reason": "TEST_OFFLINE_UNATTESTED",
            "note": "Only a synthetic read",
            "execution_attestation": "NOT_ESTABLISHED",
        },
    }


def validate_report(path: Path, run_id: str, attempt: str) -> dict:
    """Full, closed-schema validation; no authority from a passing lab."""
    raw = path.read_bytes()
    if not raw or len(raw) > 65536:
        raise AssertionError("REPORT_EMPTY_OR_OVERSIZED")
    def no_duplicate_keys(pairs):
        out = {}
        for key, val in pairs:
            if key in out:
                raise AssertionError("DUPLICATE_REPORT_KEY")
            out[key] = val
        return out
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicate_keys)
    v = exact_keys(value, {
        "schema", "source_head", "source_tree", "local_git_object_identity_only",
        "run_id", "run_attempt", "sandbox_only", "has_real_signer",
        "has_real_key", "has_merge_authority", "has_trust_authority",
        "outcome", "upstream_cases", "synthetic", "upstream_holds",
        "mutation_test", "public_read_only"
    }, "TOP")
    if (type(run_id) is not str or not run_id.isascii() or not run_id.isdecimal()
            or type(attempt) is not str or not attempt.isascii() or not attempt.isdecimal()
            or v["run_id"] != run_id or v["run_attempt"] != attempt
            or v["schema"] != "ARIO-GUARD-V2-ISOLATED-CLOUD-LAB-0.2"
            or v["source_head"] != SOURCE_HEAD or v["source_tree"] != SOURCE_TREE
            or v["local_git_object_identity_only"] is not True
            or v["sandbox_only"] is not True
            or v["outcome"] != "PASS_LAB_WITH_UPSTREAM_HOLDS"
            or any(v[k] is not False for k in (
                "has_real_signer", "has_real_key",
                "has_merge_authority", "has_trust_authority"))):
        raise AssertionError("INVALID_REPORT_CONTEXT_OR_AUTHORITY")

    u = exact_keys(v["upstream_cases"], {
        "passed", "fail", "skip", "error", "ids_sha256", "case_ids"
    }, "197")
    ids = u["case_ids"]
    if (any(type(u[k]) is not int for k in ("passed", "fail", "skip", "error"))
            or [u["passed"], u["fail"], u["skip"], u["error"]] != [197, 0, 0, 0]
            or type(ids) is not list or len(ids) != 197
            or any(type(x) is not str or not x for x in ids)
            or len(set(ids)) != 197 or ids != sorted(ids)
            or u["ids_sha256"] != EXPECTED_197_IDS_SHA256
            or case_digest(ids) != EXPECTED_197_IDS_SHA256):
        raise AssertionError("INVALID_197_TEST_IDENTITIES")

    synth = exact_keys(v["synthetic"], {
        "count", "scenarios", "disposition", "fixture_reuse", "independent_designs"
    }, "SYNTHETIC")
    outcomes = exact_keys(synth["scenarios"], set(EXACT_ASSERTION_LABELS), "14")
    if (type(synth["count"]) is not int or synth["count"] != 14
            or any(x != "PASS" for x in outcomes.values())
            or synth["disposition"] != "SYNTHETIC_HOLD_ONLY"
            or synth["fixture_reuse"] is not True
            or synth["independent_designs"] != "NOT_ESTABLISHED"):
        raise AssertionError("INVALID_14_SYNTHETIC_RESULTS")

    held = exact_keys(v["upstream_holds"], {
        "old_linked_green_new_same_head_queued",
        "missing_success_review_graph_reason", "last_sample_race"
    }, "UPSTREAM_HOLD")
    for key in ("old_linked_green_new_same_head_queued",
                "missing_success_review_graph_reason"):
        h = exact_keys(held[key], {"reproduced", "status"}, "HOLD_REPRO")
        if h["reproduced"] is not True or h["status"] != "UPSTREAM_HOLD_NOT_FIXED":
            raise AssertionError("UPSTREAM_ISSUE_NOT_REPRODUCED")
    if held["last_sample_race"] != "UNKNOWN_NOT_ATOMIC":
        raise AssertionError("UNKNOWN_RACE_FALSELY_RESOLVED")

    mut = exact_keys(v["mutation_test"], {
        "outcome", "red_exit", "green_exit", "red_summary", "green_summary",
        "case_digest", "red_digest", "expected_failures", "full_cases",
        "legacy_blob", "current_blob"
    }, "RED_GREEN")
    if (mut["outcome"] != "RED_TO_GREEN_IDENTICAL_CASE_SET"
            or any(type(mut[k]) is not int for k in (
                "red_exit", "green_exit", "expected_failures", "full_cases"))
            or [mut["red_exit"], mut["green_exit"],
                mut["expected_failures"], mut["full_cases"]] != [1, 0, 42, 71]
            or mut["case_digest"] != EXPECTED_71_IDS_SHA256
            or mut["red_digest"] != EXPECTED_42_RED_IDS_SHA256
            or mut["legacy_blob"] != OLD_VALIDATOR_BLOB
            or mut["current_blob"] != NEW_VALIDATOR_BLOB
            or type(mut["red_summary"]) is not str
            or not mut["red_summary"].startswith("42 failed, 29 passed ")
            or type(mut["green_summary"]) is not str
            or not mut["green_summary"].startswith("71 passed ")):
        raise AssertionError("INVALID_MUTATION_RESULT")

    live = v["public_read_only"]
    if (type(live) is not dict
            or not set(live).issubset({
                "status", "authority", "reason", "note", "execution_attestation",
                "required_check_observation", "source_delivery"
            })
            or not {"status", "authority", "reason", "note"}.issubset(live)
            or live["status"] != "UNKNOWN" or live["authority"] != "NONE"
            or type(live["reason"]) is not str or not live["reason"]
            or type(live["note"]) is not str or not live["note"]
            or live.get("execution_attestation", "NOT_ESTABLISHED") != "NOT_ESTABLISHED"):
        raise AssertionError("INVALID_LIVE_UNATTESTED_RESULT")
    return v


def falsify_harness(source_xml: Path) -> dict:
    """Valid fixture first; mutate only one property per negative control."""
    upstream = upstream_junit_check(source_xml)
    checks = 0
    with tempfile.TemporaryDirectory(prefix="guard-harness-controls-") as temp:
        root = Path(temp)
        (root / "implementation").mkdir()
        try:
            git_measure(root / "implementation")
        except (AssertionError, OSError):
            checks += 1
        else:
            raise AssertionError("FAKE_SOURCE_DIR_PASSED")

        # A self-contained Git repository with a TRACKED .gitignore:
        # tests must catch both unexpected untracked and ignored input.
        g = root / "git-fixture"
        subprocess.run(["git", "init", "-q", str(g)], check=True)
        (g / ".gitignore").write_text("pytest.ini\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(g), "add", ".gitignore"], check=True)
        subprocess.run(["git", "-C", str(g), "-c", "user.name=ArioLab",
                        "-c", "user.email=ario-lab@example.invalid",
                        "commit", "-q", "-m", "fixture"], check=True)
        git_clean(g)
        for path, content in (("conftest.py", "def pytest_sessionstart(s): pass\n"),
                              ("pytest.ini", "[pytest]\n")):
            f = g / path
            f.write_text(content, encoding="utf-8")
            try:
                git_clean(g)
            except AssertionError:
                checks += 1
            else:
                raise AssertionError("UNTRACKED_OR_IGNORED_FILE_ACCEPTED_" + path)
            f.unlink()
        git_clean(g)

        tree = ET.parse(source_xml)
        case = tree.getroot().find(".//testcase")
        if case is None:
            raise AssertionError("NO_JUNIT_CASE_FOR_SUBSTITUTION")
        case.set("name", case.get("name", "") + "_SUBSTITUTED")
        swap = root / "same-count.xml"
        tree.write(swap, encoding="utf-8", xml_declaration=True)
        try:
            upstream_junit_check(swap)
        except AssertionError:
            checks += 1
        else:
            raise AssertionError("SAME_COUNT_SWAPPED_ID_ACCEPTED")

        few = root / "short.xml"
        few.write_text('<testsuite tests="1" failures="0" errors="0" skipped="0">'
                       '<testcase classname="x" name="one"/></testsuite>',
                       encoding="utf-8")
        try:
            upstream_junit_check(few)
        except AssertionError:
            checks += 1
        else:
            raise AssertionError("SHORT_COLLECTION_ACCEPTED")

        baseline = valid_example(upstream, "7", "1")
        report = root / "sample.json"
        def assert_result(value, expected_run="7", expected_attempt="1",
                          must_pass=False):
            report.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
            try:
                validate_report(report, expected_run, expected_attempt)
            except (AssertionError, ValueError, TypeError, KeyError):
                if must_pass:
                    raise
                return
            if not must_pass:
                raise AssertionError("CORRUPTED_OR_STALE_REPORT_PASSED")
        assert_result(baseline, must_pass=True)
        checks += 1
        assert_result(baseline, expected_attempt="2")
        assert_result(baseline, expected_run="8")
        checks += 2

        for problem in ("schema", "authority", "synthetic", "upstream",
                        "case_ids", "race", "digest", "extra_key"):
            bad = copy.deepcopy(baseline)
            if problem == "schema":
                bad["schema"] = "FAKE_SCHEMA"
            elif problem == "authority":
                bad["has_merge_authority"] = True
            elif problem == "synthetic":
                bad["synthetic"]["scenarios"][sorted(EXACT_ASSERTION_LABELS)[0]] = "FAIL"
            elif problem == "upstream":
                bad["upstream_holds"]["old_linked_green_new_same_head_queued"]["reproduced"] = False
            elif problem == "case_ids":
                bad["upstream_cases"]["case_ids"][0] += "_SWAPPED"
                bad["upstream_cases"]["case_ids"].sort()
            elif problem == "race":
                bad["upstream_holds"]["last_sample_race"] = "COMPLETE"
            elif problem == "digest":
                bad["mutation_test"]["red_digest"] = "0" * 64
            else:
                bad["approved"] = True
            assert_result(bad)
            checks += 1
    return {"falsification_assertions": checks, "result": "PASS_NEGATIVE_CONTROLS"}


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
    ap.add_argument("--verify-source", action="store_true")
    args = ap.parse_args()
    if args.verify_source:
        if not args.implementation:
            raise SystemExit("IMPLEMENTATION_REQUIRED_BEFORE_TESTS")
        print(json.dumps(git_measure(Path(args.implementation).resolve(strict=True)),
                         sort_keys=True))
        return 0
    if args.self_test:
        if not args.upstream_junit:
            raise SystemExit("REAL_SOURCE_JUNIT_REQUIRED_FOR_SELF_TEST")
        controls = falsify_harness(Path(args.upstream_junit))
        print("HARNESS_NEGATIVE_CONTROLS " + json.dumps(controls, sort_keys=True))
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
    git_measure(impl)  # restored exact pinned tree and no rogue/ignored files
    report["public_read_only"] = live_probe(impl)
    report["outcome"] = "PASS_LAB_WITH_UPSTREAM_HOLDS"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as f:
        f.write(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=True) + "\n")
    validate_report(out, run_id, attempt)
    print("EXACT_197_CASE_ID_SHA256 " + report["upstream_cases"]["ids_sha256"])
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
