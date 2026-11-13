"""R1i external real-test observer. Separate repo, no publisher key or GitHub write.

This pinned disposable fixture executes ONE actual harmless test at an exact
target HEAD after verifying the exact Git blob and allowed diff. Its unsigned
receipt is only a witness, NOT by itself a trusted attestation or approval.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.request

REPO = "SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a"
HEAD = "508a6abfacf534fa01a4b97210c35b35ca965c86"
BASE = "be7c16d964872f88ddb9029f2677c49a7cd745ba"
PR = 14
BRANCH = "experiment/r1d-required-app-rule-20261113"
EXPECTED_DIFF = ["experiments/r1i/CLEAN_POSITIVE_FIXTURE_DO_NOT_MERGE.md"]
EXPECTED_TEST_BLOB = "ccf5e79f7956d3872e99f7feed04ff141eb113c8"
TEST_PATH = "tests/test_reference.py"
OUTPUT = Path("evidence")


def sh(*args: str, cwd: Path | None = None) -> str:
    run = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=90,
                         check=False)
    if run.returncode != 0:
        raise RuntimeError("COMMAND_FAILED:" + args[0] + ":" + str(run.returncode))
    return run.stdout.strip()


def pr_snapshot() -> dict:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/pulls/{PR}",
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "Ario-R1i-NoSecret-External-Observer"})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)


def preflight(p: dict) -> None:
    assert type(p.get("number")) is int and p["number"] == PR, "WRONG_PR"
    assert p.get("state") == "open" and p.get("merged") is False, "CLOSED_OR_MERGED"
    assert p.get("draft") is True, "UNEXPECTED_REVIEW_STATE"
    assert p["head"]["sha"] == HEAD and p["base"]["sha"] == BASE, "SHA_DRIFT"
    assert p["base"]["ref"] == BRANCH, "UNEXPECTED_TARGET_BRANCH"
    assert p["head"]["repo"]["full_name"] == REPO, "WRONG_HEAD_REPO"
    assert p["base"]["repo"]["full_name"] == REPO, "WRONG_BASE_REPO"


def main() -> None:
    OUTPUT.mkdir(exist_ok=True)
    before = pr_snapshot()
    preflight(before)
    with tempfile.TemporaryDirectory(prefix="r1i-target-") as tmp:
        root = Path(tmp) / "target"
        sh("git", "clone", "--quiet", "--no-checkout", f"https://github.com/{REPO}.git",
           str(root))
        sh("git", "checkout", "--quiet", "--detach", HEAD, cwd=root)
        assert sh("git", "rev-parse", "HEAD", cwd=root) == HEAD, "WRONG_CHECKOUT"
        assert sh("git", "rev-parse", "--verify", BASE + "^{commit}", cwd=root) == BASE, "BASE_MISSING"
        paths = sh("git", "diff", "--name-only", BASE, HEAD, cwd=root).splitlines()
        assert paths == EXPECTED_DIFF, "UNEXPECTED_DIFF_PATHS"
        blob = sh("git", "hash-object", TEST_PATH, cwd=root)
        assert blob == EXPECTED_TEST_BLOB, "UNTRUSTED_TEST_BLOB"

        # A real Python unittest execution of the exact known harmless target test.
        # This workflow does NOT run arbitrary PR workflows or supply any API secret.
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8",
               "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
               "HOME": tmp}
        cmd = [sys.executable, "-I", "-B", "-m", "unittest", "discover",
               "-s", "tests", "-p", "test_reference.py", "-v"]
        actual = subprocess.run(cmd, cwd=root, env=env, text=True,
                                capture_output=True, timeout=30, check=False)
        full_log = "$ python3 -I -B -m unittest discover -s tests -p test_reference.py -v\n"
        full_log += actual.stdout + actual.stderr
        (OUTPUT / "actual_unittest.log").write_text(full_log, encoding="utf-8")
        assert actual.returncode == 0, "REAL_TEST_RUN_FAILED"
        assert re.search(r"Ran 1 test in ", full_log), "UNEXPECTED_TEST_COUNT"
        assert re.search(r"(?m)^OK\s*$", full_log), "MISSING_PASS_EVIDENCE"
        after = pr_snapshot()
        preflight(after)
        assert after["head"]["sha"] == before["head"]["sha"], "PR_DRIFT"
        assert after["base"]["sha"] == before["base"]["sha"], "BASE_DRIFT"
        log_hash = hashlib.sha256(full_log.encode("utf-8")).hexdigest()
        source_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        result = {
            "schema": "r1i-external-observation-v1",
            "target_repo": REPO, "pr_number": PR,
            "head_sha": HEAD, "base_sha": BASE, "base_ref": BRANCH,
            "evaluator_repository": os.environ.get("GITHUB_REPOSITORY", "UNKNOWN"),
            "evaluator_commit_sha": os.environ.get("GITHUB_SHA", "UNKNOWN"),
            "workflow_run_id": os.environ.get("GITHUB_RUN_ID", "UNKNOWN"),
            "tested_blob_sha": blob, "evaluator_source_sha256": source_sha,
            "changed_paths": paths, "test_exit_code": actual.returncode,
            "test_log_sha256": log_hash,
            "tests": [{"id": "fixture.reference", "result": "passed", "count": 1}],
            "signature_status": "UNSIGNED_EXTERNAL_OBSERVATION",
            "check_published": False, "merge_authorized": False
        }
        (OUTPUT / "receipt.json").write_text(
            json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n",
            encoding="utf-8")
        print("R1I_INDEPENDENT_SOURCE_TEST_EXECUTED=1")
        print("R1I_REAL_UNITTEST_PASSED=1")
        print("R1I_TARGET_SHA=" + HEAD)
        print("R1I_EVALUATOR_SHA=" + result["evaluator_commit_sha"])
        print("R1I_LOG_SHA256=" + log_hash)
        print("R1I_OBSERVATION_UNSIGNED=1")
        print("R1I_NO_CHECK_PUBLISHED=1")


if __name__ == "__main__":
    main()
