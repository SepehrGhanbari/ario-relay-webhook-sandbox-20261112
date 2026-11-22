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
import re
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


REQUIRED_HARNESS_CONTROLS = frozenset({
    "fake_source_directory",
    "untracked_conftest",
    "ignored_pytest_ini",
    "same_count_swapped_junit_id",
    "short_junit_collection",
    "baseline_valid_report",
    "stale_run_attempt",
    "stale_run_id",
    "changed_report_schema",
    "false_merge_authority",
    "failed_synthetic_assertion",
    "missing_reproduced_upstream_hold",
    "mutated_197_case_ids",
    "false_race_clearance",
    "mutated_42_failure_digest",
    "unexpected_report_authority_key",
    "nested_junit_extra_suite",
    "nested_junit_extra_testcase_outcome",
    "unexpected_junit_root_wrapper",
    "successful_live_read_complete_baseline",
    "unavailable_live_read_complete_baseline",
    "successful_live_read_missing_attestation",
    "successful_live_read_invalid_observation",
    "successful_live_read_invalid_delivery",
    "successful_live_read_missing_check_result",
    "unavailable_live_read_with_positive_observation",
    "red_summary_suffix_forgery",
    "green_summary_suffix_forgery",
    "red_summary_wrong_exact_count",
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
    """Reject hidden nested JUnit results instead of counting only visible direct cases."""
    root = ET.parse(path).getroot()
    if root.tag == "testsuite":
        suite = root
    elif root.tag == "testsuites":
        children = list(root)
        if len(children) != 1 or children[0].tag != "testsuite":
            raise AssertionError("JUNIT_UNEXPECTED_WRAPPER_OR_NESTED_SUITE")
        suite = children[0]
    else:
        raise AssertionError("JUNIT_UNEXPECTED_ROOT")
    ids, failures, errors, skipped = [], [], [], []
    for item in suite:
        if item.tag == "properties":
            if any(p.tag != "property" or len(p) for p in item):
                raise AssertionError("JUNIT_NESTED_SUITE_PROPERTIES")
            continue
        if item.tag in ("system-out", "system-err"):
            if len(item):
                raise AssertionError("JUNIT_NESTED_TESTCASE_IN_SUITE_OUTPUT")
            continue
        if item.tag != "testcase":
            raise AssertionError("JUNIT_UNEXPECTED_SUITE_CHILD")
        a, b = item.get("classname"), item.get("name")
        if not a or not b:
            raise AssertionError("JUNIT_CASE_ID_MISSING")
        identifier = a + "::" + b
        ids.append(identifier)
        seen_outcomes = []
        for child in item:
            if child.tag in ("failure", "error", "skipped"):
                if len(child):
                    raise AssertionError("JUNIT_NESTED_OUTCOME_CONTENT")
                seen_outcomes.append(child.tag)
            elif child.tag in ("system-out", "system-err"):
                if len(child):
                    raise AssertionError("JUNIT_CASE_OUTPUT_CONTAINS_RESULTS")
            elif child.tag == "properties":
                if any(p.tag != "property" or len(p) for p in child):
                    raise AssertionError("JUNIT_INVALID_CASE_PROPERTIES")
            else:
                raise AssertionError("JUNIT_UNEXPECTED_NESTED_TESTCASE_OR_SUITE")
        if len(seen_outcomes) > 1:
            raise AssertionError("JUNIT_MULTIPLE_OUTCOMES_PER_CASE")
        if seen_outcomes:
            {"failure": failures, "error": errors, "skipped": skipped}[seen_outcomes[0]].append(identifier)
    if len(set(ids)) != len(ids):
        raise AssertionError("DUPLICATE_TEST_ID")
    for key, observed in (("tests", ids), ("failures", failures),
                          ("errors", errors), ("skipped", skipped)):
        try:
            expected = int(suite.get(key, "-1"))
        except ValueError as exc:
            raise AssertionError("JUNIT_COUNTER_MALFORMED_" + key) from exc
        if expected != len(observed):
            raise AssertionError("JUNIT_COUNT_MISMATCH_" + key)
    def digest(items):
        return hashlib.sha256(("\n".join(sorted(items)) + "\n").encode("utf-8")).hexdigest()
    return {"ids": set(ids), "failed_ids": set(failures),
            "cases": len(ids), "failed": len(failures), "errors": len(errors),
            "skipped": len(skipped), "ids_sha256": digest(ids),
            "red_sha256": digest(failures)}


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
            "reason": "OSError",
            "note": "Unauthenticated optional read unavailable; no positive claim",
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
            or re.fullmatch(r"42 failed, 29 passed in [0-9]+(?:\.[0-9]+)?s",
                            mut["red_summary"]) is None
            or type(mut["green_summary"]) is not str
            or re.fullmatch(r"71 passed in [0-9]+(?:\.[0-9]+)?s",
                            mut["green_summary"]) is None):
        raise AssertionError("INVALID_MUTATION_RESULT")

    live = v["public_read_only"]
    if type(live) is not dict or live.get("status") != "UNKNOWN":
        raise AssertionError("LIVE_DIAGNOSTIC_NOT_UNKNOWN")
    success_keys = {"status", "authority", "reason", "note",
                    "execution_attestation", "required_check_observation",
                    "source_delivery"}
    unavailable_keys = {"status", "authority", "reason", "note"}
    if set(live) == success_keys:
        if (live["authority"] != "NONE"
                or live["execution_attestation"] != "NOT_ESTABLISHED"
                or live["source_delivery"] != "GITHUB_API_RESPONSE_UNATTESTED"
                or live["required_check_observation"] not in (
                    "REPORTED_SUCCESS_BY_LINKED_PR_RUN", "NOT_CONFIRMED")
                or live["reason"] != "NON_AUTHORITATIVE_GITHUB_METADATA_READBACK"
                or live["note"] !=
                    "Unauthenticated public GET, not independent attestation"):
            raise AssertionError("UNEXPECTED_LIVE_SUCCESS_SHAPE_OR_VALUES")
    elif set(live) == unavailable_keys:
        if (live["authority"] != "NONE"
                or type(live["reason"]) is not str
                or live["reason"] not in (
                    "OSError", "TimeoutError", "RuntimeError", "ValueError",
                    "HTTPError", "URLError", "ConnectionError")
                or live["note"] !=
                    "Unauthenticated optional read unavailable; no positive claim"):
            raise AssertionError("UNEXPECTED_LIVE_UNAVAILABLE_SHAPE_OR_VALUES")
    else:
        raise AssertionError("LIVE_REPORT_HAS_MISSING_OR_EXTRA_FIELDS")
    return v


def falsify_harness(source_xml: Path) -> dict:
    """Require a fixed inventory of falsifiable controls, not just a count."""
    upstream = upstream_junit_check(source_xml)
    passed = set()

    def accept(label, func):
        func()
        if label in passed:
            raise AssertionError("DUPLICATE_HARNESS_CONTROL_" + label)
        passed.add(label)

    def reject(label, func):
        try:
            func()
        except (AssertionError, ValueError, TypeError, KeyError, ET.ParseError):
            if label in passed:
                raise AssertionError("DUPLICATE_HARNESS_CONTROL_" + label)
            passed.add(label)
        else:
            raise AssertionError("FALSE_GREEN_HARNESS_CONTROL_" + label)

    with tempfile.TemporaryDirectory(prefix="guard-v2-harness-") as folder:
        root = Path(folder)
        (root / "implementation").mkdir()
        reject("fake_source_directory", lambda: git_measure(root / "implementation"))
        g = root / "git-fixture"
        subprocess.run(["git", "init", "-q", str(g)], check=True)
        (g / ".gitignore").write_text("pytest.ini\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(g), "add", ".gitignore"], check=True)
        subprocess.run(["git", "-C", str(g), "-c", "user.name=ArioLab",
                        "-c", "user.email=ario-lab@example.invalid",
                        "commit", "-q", "-m", "fixture"], check=True)
        git_clean(g)
        for label, filename, content in (
            ("untracked_conftest", "conftest.py", "def pytest_sessionstart(s): pass\n"),
            ("ignored_pytest_ini", "pytest.ini", "[pytest]\n")
        ):
            candidate = g / filename
            candidate.write_text(content, encoding="utf-8")
            try:
                reject(label, lambda: git_clean(g))
            finally:
                candidate.unlink()
        git_clean(g)

        def write_junit(name, root_node):
            path = root / name
            ET.ElementTree(root_node).write(path, encoding="utf-8", xml_declaration=True)
            return path

        tree = ET.parse(source_xml)
        altered = copy.deepcopy(tree.getroot())
        first = altered.find(".//testcase")
        if first is None:
            raise AssertionError("NO_JUNIT_TESTCASES_TO_MUTATE")
        first.set("name", first.get("name", "") + "_SUBSTITUTED")
        reject("same_count_swapped_junit_id",
               lambda: upstream_junit_check(write_junit("swapped.xml", altered)))
        short = root / "short.xml"
        short.write_text('<testsuite tests="1" failures="0" errors="0" skipped="0">'
                         '<testcase classname="x" name="one"/></testsuite>',
                         encoding="utf-8")
        reject("short_junit_collection", lambda: upstream_junit_check(short))

        nested = copy.deepcopy(tree.getroot())
        parent_suite = nested if nested.tag == "testsuite" else nested.find("testsuite")
        if parent_suite is None:
            raise AssertionError("MISSING_UPSTREAM_JUNIT_SUITE")
        rogue_suite = ET.SubElement(parent_suite, "testsuite", {
            "tests": "1", "failures": "1", "errors": "0", "skipped": "0"
        })
        fake_case = ET.SubElement(rogue_suite, "testcase", {
            "classname": "unobserved", "name": "hidden_result"
        })
        ET.SubElement(fake_case, "failure", {"message": "hidden"})
        reject("nested_junit_extra_suite",
               lambda: upstream_junit_check(write_junit("nested-suite.xml", nested)))

        nested_case = copy.deepcopy(tree.getroot())
        first_case = nested_case.find(".//testcase")
        if first_case is None:
            raise AssertionError("MISSING_UPSTREAM_JUNIT_CASE")
        rogue_case = ET.SubElement(first_case, "testcase", {
            "classname": "unobserved", "name": "nested_error"
        })
        ET.SubElement(rogue_case, "error", {"message": "nested"})
        reject("nested_junit_extra_testcase_outcome",
               lambda: upstream_junit_check(write_junit("nested-case.xml", nested_case)))
        wrapper = ET.Element("unknown_junit_wrapper")
        wrapper.append(copy.deepcopy(tree.getroot()))
        reject("unexpected_junit_root_wrapper",
               lambda: upstream_junit_check(write_junit("bad-root.xml", wrapper)))

        sample = valid_example(upstream, "7", "1")
        report_path = root / "report.json"
        def verify_doc(payload, run="7", attempt="1"):
            report_path.write_text(json.dumps(payload, sort_keys=True),
                                   encoding="utf-8")
            return validate_report(report_path, run, attempt)
        accept("baseline_valid_report", lambda: verify_doc(sample))
        reject("stale_run_attempt", lambda: verify_doc(sample, attempt="2"))
        reject("stale_run_id", lambda: verify_doc(sample, run="8"))
        for label, mutation in (
            ("changed_report_schema", "schema"),
            ("false_merge_authority", "authority"),
            ("failed_synthetic_assertion", "synthetic"),
            ("missing_reproduced_upstream_hold", "hold"),
            ("mutated_197_case_ids", "case_ids"),
            ("false_race_clearance", "race"),
            ("mutated_42_failure_digest", "digest"),
            ("unexpected_report_authority_key", "extra_key"),
        ):
            value = copy.deepcopy(sample)
            if mutation == "schema":
                value["schema"] = "FAKE_SCHEMA"
            elif mutation == "authority":
                value["has_merge_authority"] = True
            elif mutation == "synthetic":
                value["synthetic"]["scenarios"][sorted(EXACT_ASSERTION_LABELS)[0]] = "FAIL"
            elif mutation == "hold":
                value["upstream_holds"]["old_linked_green_new_same_head_queued"]["reproduced"] = False
            elif mutation == "case_ids":
                value["upstream_cases"]["case_ids"][0] += "_SWAPPED"
                value["upstream_cases"]["case_ids"].sort()
            elif mutation == "race":
                value["upstream_holds"]["last_sample_race"] = "COMPLETE"
            elif mutation == "digest":
                value["mutation_test"]["red_digest"] = "0" * 64
            else:
                value["approved"] = True
            reject(label, lambda v=value: verify_doc(v))

        success = {
            "status": "UNKNOWN", "authority": "NONE",
            "reason": "NON_AUTHORITATIVE_GITHUB_METADATA_READBACK",
            "required_check_observation": "REPORTED_SUCCESS_BY_LINKED_PR_RUN",
            "source_delivery": "GITHUB_API_RESPONSE_UNATTESTED",
            "execution_attestation": "NOT_ESTABLISHED",
            "note": "Unauthenticated public GET, not independent attestation",
        }
        good_success = copy.deepcopy(sample)
        good_success["public_read_only"] = copy.deepcopy(success)
        accept("successful_live_read_complete_baseline",
               lambda: verify_doc(good_success))
        accept("unavailable_live_read_complete_baseline",
               lambda: verify_doc(sample))
        for label, change in (
            ("successful_live_read_missing_attestation", "attestation"),
            ("successful_live_read_invalid_observation", "observation"),
            ("successful_live_read_invalid_delivery", "delivery"),
            ("successful_live_read_missing_check_result", "missing_check"),
        ):
            candidate = copy.deepcopy(good_success)
            live = candidate["public_read_only"]
            if change == "attestation":
                live.pop("execution_attestation")
            elif change == "observation":
                live["required_check_observation"] = "AUTHORIZED"
            elif change == "delivery":
                live["source_delivery"] = "VERIFIED_BY_PUBLISHER"
            else:
                live.pop("required_check_observation")
            reject(label, lambda v=candidate: verify_doc(v))
        unavailable = copy.deepcopy(sample)
        unavailable["public_read_only"]["required_check_observation"] = (
            "REPORTED_SUCCESS_BY_LINKED_PR_RUN"
        )
        reject("unavailable_live_read_with_positive_observation",
               lambda: verify_doc(unavailable))

        for label, change in (
            ("red_summary_suffix_forgery", "red_suffix"),
            ("green_summary_suffix_forgery", "green_suffix"),
            ("red_summary_wrong_exact_count", "red_wrong"),
        ):
            value = copy.deepcopy(sample)
            if change == "red_suffix":
                value["mutation_test"]["red_summary"] += " APPROVED"
            elif change == "green_suffix":
                value["mutation_test"]["green_summary"] += "\n1 failed"
            else:
                value["mutation_test"]["red_summary"] = "42 failed, 29 passed in N/A"
            reject(label, lambda v=value: verify_doc(v))

    if passed != REQUIRED_HARNESS_CONTROLS:
        raise AssertionError("HARNESS_REQUIRED_CONTROL_INVENTORY_MISMATCH: "
                             + repr(sorted(REQUIRED_HARNESS_CONTROLS - passed)))
    return {"falsification_assertions": len(passed),
            "control_ids": sorted(passed),
            "status": "PASS_FIXED_CONTROL_INVENTORY"}


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
        if (controls["falsification_assertions"] != len(REQUIRED_HARNESS_CONTROLS)
                or controls["control_ids"] != sorted(REQUIRED_HARNESS_CONTROLS)):
            raise AssertionError("HARNESS_FIXED_INVENTORY_NOT_ENFORCED")
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
