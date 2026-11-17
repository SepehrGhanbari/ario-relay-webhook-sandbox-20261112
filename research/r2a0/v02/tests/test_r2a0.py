"""Mock-only tests; these do NOT show GitHub merge enforcement."""
import hashlib
import hmac
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import r2a0


class TestSafety(unittest.TestCase):
    def test_production_repo_rejected(self):
        with self.assertRaises(ValueError):
            r2a0.ensure_lab("SepehrGhanbari/Ario")

    def test_other_repo_rejected(self):
        with self.assertRaises(ValueError):
            r2a0.ensure_lab("SepehrGhanbari/other-test")

    def test_lab_repo_allowed(self):
        r2a0.ensure_lab(r2a0.LAB_REPO)

    def test_scenario_typo_rejected(self):
        with self.assertRaises(ValueError):
            r2a0.ensure_scenario("Sc5")

    def test_sha_required_full(self):
        for value in ("a"*7, "A"*40, "z"*40, "b"*39):
            with self.subTest(value=value), self.assertRaises(ValueError):
                r2a0.ensure_sha(value)
        r2a0.ensure_sha("a"*40)

    def test_production_api_path_rejected_before_subprocess(self):
        with patch.object(r2a0.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                r2a0.gh_api("repos/SepehrGhanbari/Ario/pulls/1")
            run.assert_not_called()

    def test_production_merge_rejected_before_api(self):
        with patch.object(r2a0, "gh_api") as api:
            with self.assertRaises(ValueError):
                r2a0.authorized_merge("SepehrGhanbari/Ario", 1, "a"*40, "experiment/r2a0-a")
            api.assert_not_called()

    def test_main_merge_rejected_before_api(self):
        with patch.object(r2a0, "gh_api") as api:
            with self.assertRaises(ValueError):
                r2a0.authorized_merge(r2a0.LAB_REPO, 1, "a"*40, "main")
            api.assert_not_called()

    def test_other_lab_branch_rejected_before_api(self):
        with patch.object(r2a0, "gh_api") as api:
            with self.assertRaises(ValueError):
                r2a0.authorized_merge(r2a0.LAB_REPO, 1, "a"*40, "experiment/r1d-required-app-rule")
            api.assert_not_called()

    def _pr_data(self, base="experiment/r2a0-test", head="a"*40, draft=False):
        return {"_request_ok": True, "_data": {"head": {"sha": head},
            "base": {"ref": base, "repo": {"full_name": r2a0.LAB_REPO}},
            "draft": draft, "merged": False, "state": "open"}}

    def test_dry_run_does_not_write(self):
        with patch.object(r2a0, "gh_api", return_value=self._pr_data()) as api:
            result = r2a0.authorized_merge(r2a0.LAB_REPO, 9, "a"*40, "experiment/r2a0-test")
            self.assertEqual(result["status"], "DRY_RUN")
            self.assertEqual(api.call_count, 1)

    def test_wrong_head_holds(self):
        with patch.object(r2a0, "gh_api", return_value=self._pr_data(head="b"*40)) as api:
            result = r2a0.authorized_merge(r2a0.LAB_REPO, 9, "a"*40, "experiment/r2a0-test", execute=True)
            self.assertEqual(result["status"], "HOLD")
            self.assertEqual(api.call_count, 1)

    def test_draft_holds(self):
        with patch.object(r2a0, "gh_api", return_value=self._pr_data(draft=True)) as api:
            result = r2a0.authorized_merge(r2a0.LAB_REPO, 9, "a"*40, "experiment/r2a0-test", execute=True)
            self.assertEqual(result["status"], "HOLD")
            self.assertEqual(api.call_count, 1)

    def test_missing_explicit_lab_merge_ack_denies(self):
        with patch.object(r2a0, "gh_api", return_value=self._pr_data()) as api, patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(PermissionError):
                r2a0.authorized_merge(r2a0.LAB_REPO, 9, "a"*40, "experiment/r2a0-test", execute=True)
            self.assertEqual(api.call_count, 1)

    def test_approved_merge_one_write_and_uncertain_response(self):
        with patch.object(r2a0, "gh_api", side_effect=[self._pr_data(), {"_request_ok": False, "_unknown_outcome": True}]) as api, patch.dict(os.environ, {"ARIO_R2A0_DISPOSABLE_MERGE_ACK":"EXPLICITLY_ALLOW_LAB_MERGE"}):
            result = r2a0.authorized_merge(r2a0.LAB_REPO, 9, "a"*40, "experiment/r2a0-test", execute=True)
            self.assertTrue(result["reconciliation_required"])
            self.assertEqual(api.call_count, 2)
            self.assertEqual(api.call_args.kwargs.get("method"), "PUT")


class TestJournal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.j = r2a0.EvidenceJournal(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_append_and_verify(self):
        a = self.j.append("manual", "operator", b"first")
        b = self.j.append("manual", "operator", b"second")
        self.assertEqual(a["seq"], 1)
        self.assertEqual(b["seq"], 2)
        self.assertEqual(b["prev_hash"], a["record_hash"])
        self.assertEqual(len(self.j.read()), 2)

    def test_truncated_history_detected_when_next_hash_present(self):
        self.j.append("manual", "operator", b"first")
        self.j.append("manual", "operator", b"second")
        data = self.j.index.read_bytes().splitlines()
        self.j.index.write_bytes(data[1] + b"\n")
        with self.assertRaises(ValueError):
            self.j.read()

    def test_payload_tamper_detected(self):
        self.j.append("manual", "operator", b"first")
        self.j.read()
        path = next((self.root / "objects").iterdir())
        path.write_bytes(b"forged")
        with self.assertRaises(ValueError):
            self.j.read()

    def test_record_hash_tamper_detected(self):
        self.j.append("manual", "operator", b"first")
        self.j.index.write_bytes(self.j.index.read_bytes().replace(b"prev_hash", b"some_hash"))
        with self.assertRaises(ValueError):
            self.j.read()

    def test_empty_history_not_proof_of_zero_findings(self):
        self.assertEqual(self.j.read(), [])
        # No code path may infer NO_MAJOR_EVER_POSTED from an empty journal.

    def test_repeated_delivery_retained_not_claimed_deduplicated(self):
        a = self.j.append("webhook", "github", b"same")
        b = self.j.append("webhook", "github", b"same")
        self.assertNotEqual(a["record_hash"], b["record_hash"])
        self.assertEqual(len(self.j.read()), 2)

    def test_corrupted_orphan_payload_blocks_reuse_of_seq(self):
        a = self.j.append("manual", "operator", b"first")
        self.j.index.unlink()
        with self.assertRaisesRegex(ValueError, "ORPHAN_EVIDENCE"):
            self.j.append("manual", "operator", b"first")


class TestWebhook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.j = r2a0.EvidenceJournal(Path(self.tmp.name))
        self.secret = b"temporary-lab-test-secret-not-production"
        self.server = r2a0.make_server(self.j, self.secret, "127.0.0.1", 0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def post(self, payload, signature=None, event="issue_comment"):
        con = HTTPConnection("127.0.0.1", self.port, timeout=2)
        headers = {"Content-Length": str(len(payload)), "X-GitHub-Event": event,
                   "X-GitHub-Delivery": "test-delivery-1"}
        if signature:
            headers["X-Hub-Signature-256"] = signature
        con.request("POST", "/github-webhook", body=payload, headers=headers)
        resp = con.getresponse()
        code = resp.status
        resp.read()
        con.close()
        return code

    def sig(self, payload):
        return "sha256=" + hmac.new(self.secret, payload, hashlib.sha256).hexdigest()

    def test_bad_signature_never_acknowledged(self):
        b = json.dumps({"repository": {"full_name": r2a0.LAB_REPO}}).encode()
        self.assertEqual(self.post(b, "sha256="+"0"*64), 401)
        self.assertEqual(self.j.read(), [])

    def test_good_signature_ack_after_append(self):
        b = json.dumps({"repository": {"full_name": r2a0.LAB_REPO}, "action": "created", "comment": {"body": "SEVERITY: MAJOR"}}).encode()
        self.assertEqual(self.post(b, self.sig(b)), 202)
        rows = self.j.read()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["meta"]["signature_verified"], True)
        self.assertEqual((self.j.root / rows[0]["payload_path"]).read_bytes(), b)

    def test_non_lab_event_rejected(self):
        b = json.dumps({"repository": {"full_name": "SepehrGhanbari/Ario"}}).encode()
        self.assertEqual(self.post(b, self.sig(b)), 403)
        self.assertEqual(self.j.read(), [])

    def test_invalid_json_rejected(self):
        b = b"not-json"
        self.assertEqual(self.post(b, self.sig(b)), 422)
        self.assertEqual(self.j.read(), [])

    def test_journal_fsync_failure_prevents_2xx(self):
        b = json.dumps({"repository": {"full_name": r2a0.LAB_REPO}}).encode()
        with patch.object(self.j, "append", side_effect=OSError("injected fsync failure")):
            self.assertEqual(self.post(b, self.sig(b)), 503)
        self.assertEqual(self.j.read(), [])


class TestGithubPagination(unittest.TestCase):
    def test_complete_single_page(self):
        with patch.object(r2a0, "gh_api", return_value={"_request_ok":True, "_data":{"check_runs":[{"id":1}]}}):
            self.assertTrue(r2a0.paged("repos/"+r2a0.LAB_REPO+"/commits/x/check-runs", "check_runs")["_complete"])

    def test_failed_read_never_complete(self):
        with patch.object(r2a0, "gh_api", return_value={"_request_ok":False, "_error":"GH_API_FAILED"}):
            self.assertFalse(r2a0.paged("repos/"+r2a0.LAB_REPO+"/pulls/1/reviews")["_complete"])

    def test_page_cap_marks_unknown(self):
        with patch.object(r2a0, "gh_api", return_value={"_request_ok":True, "_data":[{}]*100}):
            self.assertFalse(r2a0.paged("repos/"+r2a0.LAB_REPO+"/pulls/1/reviews", max_pages=2)["_complete"])


if __name__ == "__main__":
    unittest.main()

class TestGhStatusParser(unittest.TestCase):
    def test_success_status_and_json(self):
        v = r2a0.parse_gh_response(b'HTTP/2 200 OK\r\nContent-Type: application/json\r\n\r\n{"n":1}', 0, "GET")
        self.assertTrue(v["_request_ok"])
        self.assertEqual(v["_data"]["n"], 1)

    def test_http_405_known_rejection(self):
        v = r2a0.parse_gh_response(b'HTTP/2 405 Method Not Allowed\n\n{"message":"Required status check expected"}', 1, "PUT")
        self.assertFalse(v["_request_ok"])
        self.assertEqual(v["_http_status"], 405)
        self.assertFalse(v["_unknown_outcome"])

    def test_timeout_or_5xx_unknown_write(self):
        v = r2a0.parse_gh_response(b'HTTP/2 503 Service Unavailable\n\n{"message":"unavailable"}', 1, "PUT")
        self.assertTrue(v["_unknown_outcome"])

    def test_no_status_never_claims_success(self):
        v = r2a0.parse_gh_response(b'{"merged":true}', 0, "PUT")
        self.assertFalse(v["_request_ok"])
        self.assertTrue(v["_unknown_outcome"])

class TestApiScope(unittest.TestCase):
    def test_put_other_endpoint_rejected(self):
        with self.assertRaises(ValueError):
            r2a0.gh_api(f"repos/{r2a0.LAB_REPO}/contents/policy", method="PUT", payload={})

    def test_path_traversal_rejected(self):
        for suffix in ("../Ario/pulls/1", "..%2FArio/pulls/1", "foo//bar", "foo%2e%2e/bar"):
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                r2a0.gh_api(f"repos/{r2a0.LAB_REPO}/{suffix}")

class TestV02FailClosedJournal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.j = r2a0.EvidenceJournal(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_orphan_claim_after_crash_blocks_all_further_appends(self):
        (self.root / "claims").mkdir()
        (self.root / "claims" / "000001.json").write_bytes(b"partial")
        with self.assertRaisesRegex(ValueError, "ORPHAN_EVIDENCE_WITHOUT_INDEX"):
            self.j.append("manual", "user", b"new")

    def test_orphan_object_after_committed_entry_is_detected(self):
        self.j.append("manual", "user", b"good")
        (self.root / "objects" / "000002-orphan.bin").write_bytes(b"orphan")
        with self.assertRaisesRegex(ValueError, "ORPHAN_OR_MISSING_OBJECTS"):
            self.j.read()

    def test_unterminated_jsonl_record_is_not_accepted(self):
        self.j.append("manual", "user", b"good")
        original = self.j.index.read_bytes()
        self.j.index.write_bytes(original.rstrip(b"\n"))
        with self.assertRaisesRegex(ValueError, "TORN_JOURNAL_LINE"):
            self.j.read()

    def test_duplicate_json_fields_fail_closed(self):
        self.j.append("manual", "user", b"good")
        original = self.j.index.read_bytes()
        # Even if JSON parsers usually accept identical duplicate keys, we do not.
        self.j.index.write_bytes(original.replace(b'"event":', b'"event":"manual","event":'))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_FIELD"):
            self.j.read()

    def test_forged_path_rejected_despite_recomputed_chain(self):
        row = self.j.append("manual", "user", b"good")
        forged = dict(row)
        forged["payload_path"] = "../../other.bin"
        forged.pop("record_hash")
        forged["record_hash"] = r2a0.digest(r2a0.canonical(forged))
        self.j.index.write_bytes(r2a0.canonical(forged) + b"\n")
        # Actual content and claim are intact; strict path still fails.
        with self.assertRaisesRegex(ValueError, "UNEXPECTED_PAYLOAD_PATH"):
            self.j.read()

    def test_competing_processes_claim_same_seq_only_once(self):
        import multiprocessing
        # Two isolated processes race against the same empty disk state.
        # A writer can win; second may either HOLD or append a *new* valid seq.
        # Never silently produce an invalid or duplicated sequence.
        ctx = multiprocessing.get_context("spawn")
        gate = ctx.Event()
        queue = ctx.Queue()
        processes = [ctx.Process(target=_process_append, args=(str(self.root), gate, queue)) for _ in range(2)]
        for p in processes: p.start()
        gate.set()
        results = [queue.get(timeout=5) for _ in processes]
        for p in processes:
            p.join(timeout=5)
            self.assertEqual(p.exitcode, 0)
        rows = self.j.read()
        self.assertEqual(len(rows), sum(x == "ACK" for x in results))
        self.assertEqual([r["seq"] for r in rows], list(range(1, len(rows)+1)))

    def test_incomplete_claim_from_simulated_crash_in_readable_journal_holds(self):
        self.j.append("manual", "user", b"one")
        (self.root / "claims" / "000002.json").write_bytes(b"claim but no journal")
        with self.assertRaisesRegex(ValueError, "ORPHAN_OR_MISSING_CLAIMS"):
            self.j.read()

    def test_symlink_payload_rejected(self):
        if not hasattr(os, "symlink"):
            self.skipTest("no symlink support")
        a = self.j.append("manual", "user", b"one")
        original = self.root / a["payload_path"]
        outside = self.root / "untouched"
        outside.write_bytes(b"one")
        original.unlink()
        try:
            os.symlink(outside, original)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        with self.assertRaisesRegex(ValueError, "MISSING_OR_MODIFIED_PAYLOAD"):
            self.j.read()


def _process_append(root, gate, queue):
    gate.wait(timeout=4)
    try:
        r2a0.EvidenceJournal(Path(root)).append("manual", "other-process", b"same")
        queue.put("ACK")
    except (ValueError, FileExistsError, OSError):
        queue.put("HOLD")


class TestV02HttpUnknownWrites(unittest.TestCase):
    def test_cli_failed_after_successful_http_write_is_unknown(self):
        response = r2a0.parse_gh_response(b'HTTP/2 200 OK\r\n\r\n{"merged":true}', 1, "PUT")
        self.assertFalse(response["_request_ok"])
        self.assertTrue(response["_unknown_outcome"])

    def test_malformed_success_body_is_unknown(self):
        response = r2a0.parse_gh_response(b'HTTP/2 200 OK\n\nnot json', 0, "PUT")
        self.assertFalse(response["_request_ok"])
        self.assertTrue(response["_unknown_outcome"])

    def test_known_405_rejection_is_not_unknown(self):
        response = r2a0.parse_gh_response(b'HTTP/2 405 Method Not Allowed\n\n{"message":"blocked"}', 1, "PUT")
        self.assertFalse(response["_request_ok"])
        self.assertFalse(response["_unknown_outcome"])


class TestV02SnapshotCoverage(unittest.TestCase):
    def test_complete_rest_snapshots_cannot_claim_complete_historical_review(self):
        repo = r2a0.LAB_REPO
        pr = {"head":{"sha":"a"*40},"base":{"ref":"experiment/r2a0-test","sha":"b"*40,"repo":{"full_name":repo}},
              "draft":True,"merged":False,"mergeable":False,"mergeable_state":"draft","user":{"login":"tester"}}
        def fake_api(path):
            if path.endswith("/pulls/7"):
                return {"_request_ok": True, "_data": pr}
            return {"_request_ok": True, "_data": {}}
        with patch.object(r2a0, "gh_api", side_effect=fake_api), patch.object(r2a0,"paged",return_value={"_complete":True,"_items":[]}):
            snap=r2a0.snapshot(repo, 7)
        self.assertTrue(snap["api_reads_complete"])
        self.assertFalse(snap["complete_observation"])
        self.assertEqual(snap["historical_webhook_coverage"], "UNKNOWN")


class TestV02RealProcessCrash(unittest.TestCase):
    def test_real_process_exit_after_durable_claim_requires_recovery(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            # Child exits abruptly *after* the durable O_EXCL claim, not by
            # raising an exception or cleanly closing the journal.
            code = """import os, sys
from pathlib import Path
import r2a0
orig = r2a0.write_once
def crash_after_claim(path, data):
    orig(path, data)
    if path.parent.name == 'claims':
        os._exit(73)
r2a0.write_once = crash_after_claim
r2a0.EvidenceJournal(Path(sys.argv[1])).append('manual', 'crash-fixture', b'x')
"""
            env = dict(os.environ)
            env["PYTHONPATH"] = str(Path(r2a0.__file__).parent)
            proc = subprocess.run([sys.executable, "-c", code, directory], env=env,
                                  capture_output=True, timeout=10)
            self.assertEqual(proc.returncode, 73)
            journal = r2a0.EvidenceJournal(Path(directory))
            with self.assertRaisesRegex(ValueError, "ORPHAN_EVIDENCE_WITHOUT_INDEX"):
                journal.read()
            with self.assertRaisesRegex(ValueError, "ORPHAN_EVIDENCE_WITHOUT_INDEX"):
                journal.append('manual', 'restart-fixture', b'y')

    def test_actual_success_path_can_be_read_by_separate_process(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            j=r2a0.EvidenceJournal(Path(directory))
            j.append('manual', 'writer', b'hello')
            proc=subprocess.run([sys.executable, str(Path(r2a0.__file__)), 'verify',
                                 '--evidence-dir', directory], capture_output=True,
                                 text=True, timeout=10)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report=json.loads(proc.stdout)
            self.assertEqual(report['records'],1)
            self.assertEqual(report['historical_completeness'],'UNKNOWN')


class TestV02EmptyJournalHonesty(unittest.TestCase):
    def test_absent_journal_does_not_report_integrity_pass(self):
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            proc = subprocess.run([sys.executable, str(Path(r2a0.__file__)), "verify", "--evidence-dir", d],
                                  capture_output=True, text=True, timeout=5)
            self.assertEqual(proc.returncode, 0)
            obj = json.loads(proc.stdout)
            self.assertEqual(obj["journal_integrity"], "NO_JOURNAL")
            self.assertEqual(obj["historical_completeness"], "UNKNOWN")


class TestV03RulesBranchPath(unittest.TestCase):
    def test_rules_url_for_isolated_branch_reaches_gh_cli(self):
        repo = r2a0.LAB_REPO
        target = f"repos/{repo}/rules/branches/experiment%2Fr2a0-test"
        from subprocess import CompletedProcess
        with patch.object(r2a0.subprocess, "run", return_value=CompletedProcess(args=[], returncode=0, stdout=b'HTTP/2 200 OK\n\n[]', stderr=b'')) as call:
            result = r2a0.gh_api(target)
        self.assertTrue(result["_request_ok"])
        self.assertEqual(call.call_args.args[0][-1], target)

    def test_snapshot_rules_request_uses_encoded_isolated_branch(self):
        repo = r2a0.LAB_REPO
        fixture = {"head": {"sha": "a"*40}, "base": {"ref": "experiment/r2a0-test", "sha":"b"*40, "repo":{"full_name":repo}},
                   "draft":True, "merged":False, "mergeable":False, "mergeable_state":"draft", "user":{"login":"tester"}}
        original_gh_api = r2a0.gh_api
        def fake_api(path, **kwargs):
            if path.endswith("/pulls/14"):
                return {"_request_ok":True, "_data":fixture}
            if "/rules/branches/" in path:
                # Preserve a real parser/guard test rather than making a mocked call always pass.
                from subprocess import CompletedProcess
                with patch.object(r2a0.subprocess, "run", return_value=CompletedProcess(args=[], returncode=0, stdout=b'HTTP/2 200 OK\n\n[]', stderr=b'')):
                    return original_gh_api(path)
            return {"_request_ok":True, "_data":{}}
        with patch.object(r2a0, "gh_api", side_effect=fake_api), patch.object(r2a0, "paged", return_value={"_complete":True, "_items":[]}):
            result = r2a0.snapshot(repo, 14)
        self.assertTrue(result["effective_rules"]["_request_ok"])

    def test_encoded_slash_still_rejected_in_other_api_paths(self):
        repo = r2a0.LAB_REPO
        for part in ("pulls/experiment%2F4", "contents/test%2Ffoo", "rules/branches/experiment%2Fnot-r2a0-test", "rules/branches/experiment%2Fr2a0-test%2Fmain", "rules/branches/experiment%252Fr2a0-test", "rules/branches/experiment%2Fr2a0-.."):
            with self.subTest(part=part), patch.object(r2a0.subprocess, "run") as run, self.assertRaises(ValueError):
                r2a0.gh_api(f"repos/{repo}/{part}")
            run.assert_not_called()

    def test_nonlab_ref_in_snapshot_denied(self):
        repo=r2a0.LAB_REPO
        fixture={"head":{"sha":"a"*40}, "base":{"ref":"main","sha":"b"*40,"repo":{"full_name":repo}},"draft":True,"merged":False,"mergeable":False,"mergeable_state":"draft","user":{"login":"tester"}}
        with patch.object(r2a0,"gh_api",return_value={"_request_ok":True,"_data":fixture}), self.assertRaises(ValueError):
            r2a0.snapshot(repo,14)
