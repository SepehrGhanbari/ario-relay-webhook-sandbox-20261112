"""R1l actual local network / SQLite / crash tests, no GitHub secrets or POSTs.

A loopback-only coordinator process serves multiple clients running in distinct
working directories ("simulated hosts"). This does NOT demonstrate a deployed
cross-host authenticated network service or distributed database quorum.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

from r1l_atomic_coordinator import (
    APP_ID, BASE, EXTERNAL_ID, HEAD, NAME, REPO, Store, fixed_intent,
)
from r1l_network_client import call_once

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "r1l_atomic_coordinator.py"
CLIENT = ROOT / "r1l_network_client.py"


def unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class R1lTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="r1l-coordinator-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.db = self.dir / "shared-coordinator.sqlite3"
        Store.bootstrap(self.db)
        self.proc = None
        self.url = None

    def stop_server(self):
        if self.proc is not None:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=5)
            self.proc = None

    def start_server(self, fault="none", path=None):
        self.stop_server()
        port = unused_port()
        self.url = "http://127.0.0.1:" + str(port)
        args = [sys.executable, "-u", "-B", str(SERVICE),
                "--db", str(path or self.db), "--port", str(port),
                "--fault", fault]
        self.proc = subprocess.Popen(args, cwd=ROOT,
                                     stdin=subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
        self.addCleanup(self.stop_server)
        deadline = time.monotonic() + 6.5
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                return False
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.15):
                    return True
            except OSError:
                time.sleep(0.025)
        return False

    def reserve(self, evidence="a"*64):
        return call_once(self.url, fixed_intent(evidence))

    def status(self):
        return call_once(self.url, None)

    def assert_hold(self, result):
        self.assertIs(result["can_publish"], False)
        self.assertIs(result["repeat_post_allowed"], False)
        self.assertIs(result["github_check_emitted"], False)
        self.assertEqual(result["production_trust"], "NO_GO")

    def test_01_one_client_creates_transactional_claim_without_post_rights(self):
        self.assertTrue(self.start_server())
        out = self.reserve()
        self.assertEqual(out["verdict"], "CREATED_HOLD")
        self.assertTrue(out["created"])
        self.assert_hold(out)
        s = self.status()
        self.assertEqual((s["verdict"], s["claim_count"]), ("CLAIMED_UNKNOWN_HOLD", 1))
        self.assert_hold(s)

    def test_02_same_intent_twice_never_recreates(self):
        self.assertTrue(self.start_server())
        a, b = self.reserve(), self.reserve()
        self.assertEqual(a["verdict"], "CREATED_HOLD")
        self.assertEqual(b["verdict"], "ALREADY_HELD")
        self.assertFalse(b["created"])
        self.assertEqual(self.status()["claim_count"], 1)

    def test_03_eight_separate_client_processes_share_one_atomic_coordinator(self):
        self.assertTrue(self.start_server())
        go = self.dir / "barrier"
        children = []
        for n in range(8):
            host_dir = self.dir / ("host-" + str(n))
            host_dir.mkdir()
            command = [sys.executable, "-B", str(CLIENT),
                       "--url", self.url, "--barrier", str(go)]
            children.append(subprocess.Popen(command, cwd=host_dir,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        try:
            time.sleep(0.3)
            go.write_text("release\n")
            responses = []
            for p in children:
                out, err = p.communicate(timeout=25)
                self.assertEqual(p.returncode, 0, err)
                responses.append(json.loads(out))
            verdicts = [x["verdict"] for x in responses]
            self.assertEqual(verdicts.count("CREATED_HOLD"), 1, verdicts)
            self.assertEqual(verdicts.count("ALREADY_HELD"), 7, verdicts)
            self.assertEqual(self.status()["claim_count"], 1)
            for v in responses:
                self.assert_hold(v)
        finally:
            for p in children:
                if p.poll() is None:
                    p.kill()
                if p.stdout:
                    p.stdout.close()
                if p.stderr:
                    p.stderr.close()
                p.wait(timeout=5)

    def test_04_independent_host_directories_no_longer_get_independent_claims(self):
        # R1k's negative control: different local dirs both claimed; NOW they
        # both contact the SAME coordinator and only one request is created.
        self.assertTrue(self.start_server())
        first = self.dir / "remote-host-A"
        second = self.dir / "remote-host-B"
        first.mkdir()
        second.mkdir()
        codes = []
        for host in (first, second):
            result = subprocess.run([sys.executable, "-B", str(CLIENT),
                                     "--url", self.url], cwd=host,
                                    capture_output=True, text=True, timeout=12)
            self.assertEqual(result.returncode, 0, result.stderr)
            codes.append(json.loads(result.stdout)["verdict"])
        self.assertEqual(codes, ["CREATED_HOLD", "ALREADY_HELD"])
        self.assertEqual(self.status()["claim_count"], 1)

    def test_05_network_service_unavailable_must_hold_not_local_fallback(self):
        port = unused_port()
        self.url = "http://127.0.0.1:" + str(port)
        out = self.reserve()
        self.assertEqual(out["verdict"], "UNKNOWN_HOLD")
        self.assert_hold(out)
        status = self.status()
        self.assertEqual(status["verdict"], "UNKNOWN_HOLD")
        self.assert_hold(status)
        self.assertEqual(Store(self.db).status()["claim_count"], 0)

    def test_06_db_write_lock_returns_hold_not_duplicate(self):
        self.assertTrue(self.start_server())
        conn = sqlite3.connect(self.db, isolation_level=None, timeout=0.2)
        try:
            conn.execute("BEGIN IMMEDIATE")
            out = self.reserve()
            self.assertEqual(out["verdict"], "UNKNOWN_HOLD")
            self.assert_hold(out)
        finally:
            conn.execute("ROLLBACK")
            conn.close()
        self.assertEqual(self.status()["verdict"], "ABSENT_HOLD")
        self.assertEqual(Store(self.db).status()["claim_count"], 0)

    def test_07_crash_after_sql_commit_before_http_response(self):
        self.assertTrue(self.start_server("crash_after_commit_once"))
        out = self.reserve()
        self.assertEqual(out["verdict"], "UNKNOWN_HOLD")
        self.assert_hold(out)
        self.proc.wait(timeout=8)
        self.assertEqual(self.proc.returncode, 91)
        self.assertEqual(Store(self.db).status()["verdict"], "CLAIMED_UNKNOWN_HOLD")
        self.assertTrue(self.start_server())
        saved = self.status()
        self.assertEqual((saved["verdict"], saved["claim_count"]),
                         ("CLAIMED_UNKNOWN_HOLD", 1))
        # An explicitly attempted duplicate is REFUSED as a new reservation.
        duplicate = self.reserve()
        self.assertEqual(duplicate["verdict"], "ALREADY_HELD")
        self.assert_hold(duplicate)
        self.assertEqual(self.status()["claim_count"], 1)

    def test_08_lost_reply_after_commit_is_unknown_but_reconcilable_readonly(self):
        self.assertTrue(self.start_server("drop_reply_after_commit_once"))
        uncertain = self.reserve()
        self.assertEqual(uncertain["verdict"], "UNKNOWN_HOLD")
        self.assert_hold(uncertain)
        # No new POST: only read back coordinator state.
        readback = self.status()
        self.assertEqual((readback["verdict"], readback["claim_count"]),
                         ("CLAIMED_UNKNOWN_HOLD", 1))
        self.assert_hold(readback)

    def test_09_restart_server_after_clean_shutdown_preserves_claim(self):
        self.assertTrue(self.start_server())
        self.assertEqual(self.reserve()["verdict"], "CREATED_HOLD")
        self.stop_server()
        self.assertTrue(self.start_server())
        self.assertEqual(self.status()["claim_count"], 1)
        self.assertEqual(self.reserve()["verdict"], "ALREADY_HELD")

    def test_10_corrupt_database_rejects_boot_without_silent_reset(self):
        self.stop_server()
        self.db.write_bytes(b"not a valid SQLite database")
        self.assertFalse(self.start_server())
        out = self.reserve()
        self.assertEqual(out["verdict"], "UNKNOWN_HOLD")
        self.assert_hold(out)

    def test_11_missing_database_rejects_boot_without_silent_rebootstrap(self):
        self.stop_server()
        self.db.unlink()
        self.assertFalse(self.start_server())
        out = self.reserve()
        self.assertEqual(out["verdict"], "UNKNOWN_HOLD")
        self.assert_hold(out)

    def test_12_second_bootstrap_refuses_existing_state(self):
        self.assertTrue(self.start_server())
        self.assertEqual(self.reserve()["verdict"], "CREATED_HOLD")
        self.stop_server()
        with self.assertRaises(FileExistsError):
            Store.bootstrap(self.db)
        self.assertEqual(Store(self.db).status()["claim_count"], 1)

    def test_13_different_signed_evidence_for_existing_scope_is_conflict(self):
        self.assertTrue(self.start_server())
        self.assertEqual(self.reserve("a"*64)["verdict"], "CREATED_HOLD")
        conflict = self.reserve("b"*64)
        self.assertEqual(conflict["verdict"], "CONFLICT_HOLD")
        self.assert_hold(conflict)
        self.assertEqual(self.status()["claim_count"], 1)

    def test_14_unexpected_repo_is_rejected_before_writes(self):
        self.assertTrue(self.start_server())
        value = fixed_intent()
        value["repo"] = "SepehrGhanbari/Ario"
        result = call_once(self.url, value)
        self.assertEqual(result["verdict"], "HOLD")
        self.assert_hold(result)
        self.assertEqual(self.status()["claim_count"], 0)

    def test_15_unexpected_app_id_rejected(self):
        self.assertTrue(self.start_server())
        value = fixed_intent()
        value["app_id"] = 15368
        result = call_once(self.url, value)
        self.assertEqual(result["verdict"], "HOLD")
        self.assert_hold(result)
        self.assertEqual(self.status()["claim_count"], 0)

    def test_16_boolean_pr_number_rejected(self):
        self.assertTrue(self.start_server())
        value = fixed_intent()
        value["pr_number"] = True
        result = call_once(self.url, value)
        self.assertEqual(result["verdict"], "HOLD")
        self.assert_hold(result)
        self.assertEqual(self.status()["claim_count"], 0)

    def test_17_non_loopback_network_is_disallowed(self):
        bad = call_once("http://192.0.2.10:4444", fixed_intent())
        self.assertEqual(bad["verdict"], "HOLD")
        self.assert_hold(bad)

    def test_18_absent_record_is_not_permission_to_publish(self):
        self.assertTrue(self.start_server())
        result = self.status()
        self.assertEqual(result["verdict"], "ABSENT_HOLD")
        self.assertEqual(result["claim_count"], 0)
        self.assert_hold(result)

    def test_19_repeated_recovery_does_not_expire_or_reissue_claim(self):
        self.assertTrue(self.start_server())
        self.assertEqual(self.reserve()["verdict"], "CREATED_HOLD")
        for _ in range(5):
            self.assertEqual(self.status()["verdict"], "CLAIMED_UNKNOWN_HOLD")
            self.assertEqual(self.status()["claim_count"], 1)
        self.assertEqual(self.reserve()["verdict"], "ALREADY_HELD")

    def test_20_all_results_explicitly_refuse_github_publish(self):
        self.assertTrue(self.start_server())
        results = [self.status(), self.reserve(), self.reserve(),
                   self.reserve("b"*64)]
        for v in results:
            self.assert_hold(v)
        self.assertEqual(self.status()["claim_count"], 1)


if __name__ == "__main__":
    unittest.main()
