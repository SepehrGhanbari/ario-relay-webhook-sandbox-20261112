"""R1k real subprocess tests: crash, restart, contention on the SAME host.

ZERO GitHub API calls, credentials, App publication, or production mutation.
These tests intentionally do not claim cross-machine/disk-power-loss safety.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from r1j_reconcile import APP_ID, CHECK_NAME, REPO, Intent, exclusive_post_intent
from r1k_recovery import recover_existing_intent

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "r1k_journal_worker.py"
HEAD = "508a6abfacf534fa01a4b97210c35b35ca965c86"
BASE = "be7c16d964872f88ddb9029f2677c49a7cd745ba"
EXT = "R1I-LAB-ONLY:PR14:" + HEAD + ":RUN43484108692"


def expected():
    return Intent(repo=REPO, pr_number=14, head_sha=HEAD,
                  base_sha=BASE, name=CHECK_NAME, app_id=APP_ID,
                  external_id=EXT, conclusion="success")


def worker(path: Path, mode: str = "normal", barrier: Path | None = None):
    cmd = [sys.executable, "-B", str(WORKER), "--path", str(path),
           "--mode", mode]
    if barrier is not None:
        cmd.extend(["--barrier", str(barrier)])
    return cmd


def run_worker(path: Path, mode: str = "normal") -> subprocess.CompletedProcess:
    return subprocess.run(worker(path, mode), cwd=ROOT,
                          capture_output=True, text=True, timeout=20,
                          check=False)


class R1kFaults(unittest.TestCase):
    def assert_hold(self, report):
        self.assertFalse(report["automatic_post_allowed"])
        self.assertFalse(report["repeat_post_allowed"])
        self.assertFalse(report["record_deleted"])
        self.assertEqual(report["production_trust"], "NO_GO")

    def test_01_nonexistent_marker_is_unknown_not_write_permission(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent.json"
            report = recover_existing_intent(path, expected())
            self.assertEqual(report["verdict"], "UNKNOWN_HOLD")
            self.assertEqual(report["reason"], "NO_JOURNAL_CANNOT_PROVE_NO_POST")
            self.assert_hold(report)
            self.assertFalse(path.exists())

    def test_02_valid_marker_survives_separate_process_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent.json"
            first = run_worker(path)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn("CLAIMED_NO_POST", first.stdout)
            before = path.read_bytes()
            second = run_worker(path)
            self.assertEqual(second.returncode, 20, second.stderr)
            self.assertIn("JOURNAL_EXISTS_NO_REPOST", second.stdout)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(recover_existing_intent(path, expected())["verdict"],
                             "RECOVERED_POST_OUTCOME_UNKNOWN_HOLD")

    def test_03_hard_crash_after_claim_preserves_no_repost_tombstone(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent.json"
            proc = run_worker(path, "die_after_claim")
            self.assertEqual(proc.returncode, 73, proc.stderr)
            before = path.read_bytes()
            self.assertGreater(len(before), 150)
            report = recover_existing_intent(path, expected())
            self.assertEqual(report["verdict"], "RECOVERED_POST_OUTCOME_UNKNOWN_HOLD")
            self.assert_hold(report)
            restart = run_worker(path)
            self.assertEqual(restart.returncode, 20, restart.stderr)
            self.assertEqual(before, path.read_bytes())

    def test_04_crash_mid_write_keeps_partial_tombstone_and_never_reposts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent.json"
            proc = run_worker(path, "die_mid_write")
            self.assertEqual(proc.returncode, 74, proc.stderr)
            payload = path.read_bytes()
            self.assertGreater(len(payload), 5)
            self.assertLess(len(payload), 100)
            report = recover_existing_intent(path, expected())
            self.assertEqual(report["verdict"], "UNKNOWN_HOLD")
            self.assertEqual(report["reason"], "JOURNAL_TORN_OR_UNREADABLE")
            self.assert_hold(report)
            restart = run_worker(path)
            self.assertEqual(restart.returncode, 20, restart.stderr)
            self.assertEqual(payload, path.read_bytes())

    def test_05_eight_processes_race_for_one_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent.json"
            go = Path(directory) / "start.flag"
            children = [subprocess.Popen(worker(path, barrier=go), cwd=ROOT,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                        for _ in range(8)]
            try:
                time.sleep(0.4)
                go.write_text("start\n")
                results = [p.communicate(timeout=25) for p in children]
                codes = [p.returncode for p in children]
                self.assertEqual(codes.count(0), 1, list(zip(codes, results)))
                self.assertEqual(codes.count(20), 7, list(zip(codes, results)))
                self.assertEqual(sum("CLAIMED_NO_POST" in stdout
                                     for stdout, _ in results), 1)
                report = recover_existing_intent(path, expected())
                self.assertEqual(report["verdict"], "RECOVERED_POST_OUTCOME_UNKNOWN_HOLD")
                self.assert_hold(report)
            finally:
                for p in children:
                    if p.poll() is None:
                        p.kill()
                    if p.stdout:
                        p.stdout.close()
                    if p.stderr:
                        p.stderr.close()
                    p.wait(timeout=10)

    def test_06_empty_file_from_crash_never_confers_recovery_permission(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent.json"
            path.touch()
            report = recover_existing_intent(path, expected())
            self.assertEqual(report["reason"], "JOURNAL_EMPTY_OR_OVERSIZED")
            self.assert_hold(report)
            self.assertEqual(run_worker(path).returncode, 20)

    def test_07_garbled_utf8_remains_hold(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent.json"
            path.write_bytes(b"\xff\xfe\x80")
            report = recover_existing_intent(path, expected())
            self.assertEqual(report["reason"], "JOURNAL_TORN_OR_UNREADABLE")
            self.assert_hold(report)

    def test_08_oversized_file_remains_hold(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent.json"
            path.write_bytes(b"x" * 16385)
            report = recover_existing_intent(path, expected())
            self.assertEqual(report["reason"], "JOURNAL_EMPTY_OR_OVERSIZED")
            self.assert_hold(report)

    def test_09_wrong_sha_in_existing_valid_journal_is_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent.json"
            exclusive_post_intent(path, expected())
            obj = json.loads(path.read_text())
            obj["head_sha"] = "f" * 40
            path.write_text(json.dumps(obj))
            report = recover_existing_intent(path, expected())
            self.assertEqual(report["verdict"], "CONFLICT_HOLD")
            self.assertEqual(report["reason"], "JOURNAL_IDENTITY_MISMATCH:head_sha")
            self.assert_hold(report)

    def test_10_no_repost_boolean_forgery_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent.json"
            exclusive_post_intent(path, expected())
            obj = json.loads(path.read_text())
            obj["no_repost"] = 1
            path.write_text(json.dumps(obj))
            report = recover_existing_intent(path, expected())
            self.assertEqual(report["reason"], "JOURNAL_IDENTITY_MISMATCH:no_repost")
            self.assert_hold(report)

    def test_11_schema_injection_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent.json"
            exclusive_post_intent(path, expected())
            obj = json.loads(path.read_text())
            obj["go_ahead"] = True
            path.write_text(json.dumps(obj))
            report = recover_existing_intent(path, expected())
            self.assertEqual(report["reason"], "JOURNAL_SCHEMA_MISMATCH")
            self.assert_hold(report)

    def test_12_existing_directory_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent.json"
            path.mkdir()
            report = recover_existing_intent(path, expected())
            self.assertEqual(report["reason"], "JOURNAL_NOT_REGULAR_FILE")
            self.assert_hold(report)

    def test_13_wrong_app_id_in_journal_holds(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent.json"
            exclusive_post_intent(path, expected())
            obj = json.loads(path.read_text())
            obj["app_id"] = 15368
            path.write_text(json.dumps(obj))
            report = recover_existing_intent(path, expected())
            self.assertEqual(report["reason"], "JOURNAL_IDENTITY_MISMATCH:app_id")
            self.assert_hold(report)

    def test_14_mismatched_external_id_holds(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent.json"
            exclusive_post_intent(path, expected())
            obj = json.loads(path.read_text())
            obj["external_id"] = "fake-run"
            path.write_text(json.dumps(obj))
            report = recover_existing_intent(path, expected())
            self.assertEqual(report["reason"], "JOURNAL_IDENTITY_MISMATCH:external_id")
            self.assert_hold(report)

    def test_15_wrong_intent_never_approves_post(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent.json"
            exclusive_post_intent(path, expected())
            wrong = Intent(repo="SepehrGhanbari/Ario", pr_number=14,
                           head_sha=HEAD, base_sha=BASE, name=CHECK_NAME, app_id=APP_ID,
                           external_id=EXT, conclusion="success")
            report = recover_existing_intent(path, wrong)
            self.assertEqual(report["verdict"], "HOLD")
            self.assertEqual(report["reason"], "INVALID_INTENT")
            self.assert_hold(report)

    def test_16_symlink_is_rejected_when_os_allows(self):
        with tempfile.TemporaryDirectory() as directory:
            real = Path(directory) / "real"
            real.write_text("do not change\n")
            pointer = Path(directory) / "intent.json"
            try:
                pointer.symlink_to(real)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks require OS permissions on this runner")
            report = recover_existing_intent(pointer, expected())
            self.assertEqual(report["reason"], "JOURNAL_NOT_REGULAR_FILE")
            self.assert_hold(report)
            self.assertEqual(real.read_text(), "do not change\n")

    def test_17_two_hardlinked_names_are_not_valid_journal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent.json"
            alias = Path(directory) / "alias"
            exclusive_post_intent(path, expected())
            try:
                os.link(path, alias)
            except OSError:
                self.skipTest("Hardlinks unsupported on this runner")
            report = recover_existing_intent(path, expected())
            self.assertEqual(report["reason"], "JOURNAL_HAS_MULTIPLE_LINKS")
            self.assert_hold(report)

    def test_18_three_restart_attempts_keep_original_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent.json"
            self.assertEqual(run_worker(path).returncode, 0)
            original = path.read_bytes()
            for _ in range(3):
                self.assertEqual(run_worker(path).returncode, 20)
                self.assertEqual(path.read_bytes(), original)
                self.assert_hold(recover_existing_intent(path, expected()))

    def test_19_two_disjoint_host_journals_both_claim_proves_no_global_lock(self):
        """Adversarial negative result: local O_EXCL cannot prevent multi-host duplicates.

        DO NOT publish a Check in this probe. Both records are only local intents.
        """
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "hostA"
            second = Path(directory) / "hostB"
            first.mkdir()
            second.mkdir()
            a = run_worker(first / "intent.json")
            b = run_worker(second / "intent.json")
            self.assertEqual((a.returncode, b.returncode), (0, 0))
            for path in (first / "intent.json", second / "intent.json"):
                report = recover_existing_intent(path, expected())
                self.assertEqual(report["verdict"], "RECOVERED_POST_OUTCOME_UNKNOWN_HOLD")
                self.assert_hold(report)
            # This is a documented *failure* of cross-host mutual exclusion,
            # not evidence that two GitHub Check POSTs actually took place.

    def test_20_torn_marker_blocks_multiple_simultaneous_restarters(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent.json"
            crash = run_worker(path, "die_mid_write")
            self.assertEqual(crash.returncode, 74)
            original = path.read_bytes()
            go = Path(directory) / "go"
            children = [subprocess.Popen(worker(path, barrier=go), cwd=ROOT,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                        for _ in range(6)]
            try:
                time.sleep(0.3)
                go.write_text("go\n")
                results = [p.communicate(timeout=25) for p in children]
                self.assertTrue(all(p.returncode == 20 for p in children),
                                list(zip([p.returncode for p in children], results)))
                self.assertEqual(path.read_bytes(), original)
                self.assertEqual(recover_existing_intent(path, expected())["verdict"],
                                 "UNKNOWN_HOLD")
            finally:
                for p in children:
                    if p.poll() is None:
                        p.kill()
                    if p.stdout:
                        p.stdout.close()
                    if p.stderr:
                        p.stderr.close()
                    p.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
