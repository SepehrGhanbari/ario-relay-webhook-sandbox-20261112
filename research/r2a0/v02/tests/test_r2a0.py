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


class TestV03MergeIntentPreflight(unittest.TestCase):
    def test_invalid_base_is_rejected_before_journal_side_effects(self):
        with tempfile.TemporaryDirectory() as d:
            args = ["attempt-merge", "--pr", "12", "--scenario", "Sc1", "--base", "experiment/r2a0-../main",
                    "--expected-head", "a"*40, "--execute", "--evidence-dir", d]
            with patch.object(r2a0, "gh_api") as api:
                result = r2a0.main(args)
            self.assertEqual(result, 2)
            api.assert_not_called()
            self.assertFalse(any(Path(d).iterdir()), "Invalid branch must not reserve or poison journal state")

    def test_valid_base_scope_check_accepts_flat_fixture(self):
        r2a0.ensure_lab_base_ref("experiment/r2a0-control")
        for name in ("experiment/r2a0-../main", "experiment/r2a0-control/extra", "experiment/r2a0-", "main"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                r2a0.ensure_lab_base_ref(name)


class TestV04MergeIntentCrashCustody(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.journal = r2a0.EvidenceJournal(self.root)
        self.intent = {
            "repo": r2a0.LAB_REPO, "pr": 22, "head": "a" * 40,
            "base": "experiment/r2a0-crash", "scenario": "Sc1"
        }
        self.raw = r2a0.canonical(self.intent)
        self.marker = self.root / "merge_intents" / (r2a0.digest(self.raw) + ".json")

    def tearDown(self):
        self.temp.cleanup()

    def _reserve(self):
        r2a0.write_once(self.marker, self.raw)

    def test_crash_between_merge_reservation_and_journal_must_halt_verify(self):
        self.journal.append("manual", "fixture", b"older healthy evidence")
        script = """import os,sys
from pathlib import Path
import r2a0
raw = bytes.fromhex(sys.argv[2])
r2a0.write_once(Path(sys.argv[1]) / 'merge_intents' / (r2a0.digest(raw) + '.json'), raw)
os._exit(79)
"""
        env = dict(os.environ, PYTHONPATH=str(Path(r2a0.__file__).parent))
        killed = __import__("subprocess").run(
            [sys.executable, "-c", script, str(self.root), self.raw.hex()],
            env=env, capture_output=True, timeout=10)
        self.assertEqual(killed.returncode, 79)
        result = __import__("subprocess").run(
            [sys.executable, str(Path(r2a0.__file__)), "verify", "--evidence-dir", str(self.root)],
            env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("ORPHAN_MERGE_INTENT", result.stderr)

    def test_orphan_marker_refuses_new_journal_append(self):
        self._reserve()
        with self.assertRaisesRegex(ValueError, "ORPHAN_MERGE_INTENT"):
            self.journal.append("manual", "other", b"bad continuation")

    def test_valid_marker_and_matching_ledger_record_read_ok(self):
        self._reserve()
        self.journal.append("merge-intent", "local", self.raw, {"scenario": "Sc1"})
        self.assertEqual(len(self.journal.read()), 1)
        self.journal.append("merge-attempt", "gh-api", b"unknown")
        self.assertEqual(len(self.journal.read()), 2)

    def test_missing_marker_after_commit_holds(self):
        self._reserve()
        self.journal.append("merge-intent", "local", self.raw)
        self.marker.unlink()
        with self.assertRaisesRegex(ValueError, "MISSING_OR_MODIFIED_MERGE_INTENT"):
            self.journal.read()

    def test_tampered_marker_after_commit_holds(self):
        self._reserve()
        self.journal.append("merge-intent", "local", self.raw)
        self.marker.write_bytes(self.raw + b" ")
        with self.assertRaisesRegex(ValueError, "INVALID_MERGE_INTENT_MARKER"):
            self.journal.read()

    def test_bad_marker_name_and_bytes_hold(self):
        self.marker.parent.mkdir(exist_ok=True)
        self.marker.with_name("bad.json").write_bytes(self.raw)
        with self.assertRaisesRegex(ValueError, "INVALID_MERGE_INTENT_MARKER"):
            self.journal.read()

    def test_merge_intent_record_without_marker_is_forbidden(self):
        with self.assertRaisesRegex(ValueError, "MISSING_PENDING_MERGE_INTENT"):
            self.journal.append("merge-intent", "local", self.raw)

    def test_missing_marker_directory_after_commit_holds(self):
        self._reserve()
        self.journal.append("merge-intent", "local", self.raw)
        self.marker.unlink()
        self.marker.parent.rmdir()
        with self.assertRaisesRegex(ValueError, "MISSING_OR_MODIFIED_MERGE_INTENT"):
            self.journal.read()

class TestV04MergeIntentCrashMatrix(unittest.TestCase):
    def test_crash_after_committed_intent_before_network_never_reserves_twice(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            code = '''import os,sys
from pathlib import Path
import r2a0
intent={"repo":r2a0.LAB_REPO,"pr":22,"head":"a"*40,"base":"experiment/r2a0-crash","scenario":"Sc1"}
raw=r2a0.canonical(intent)
r2a0.write_once(Path(sys.argv[1])/'merge_intents'/(r2a0.digest(raw)+'.json'),raw)
r2a0.EvidenceJournal(Path(sys.argv[1])).append('merge-intent','local',raw)
os._exit(81)
'''
            env = dict(os.environ, PYTHONPATH=str(Path(r2a0.__file__).parent))
            child = subprocess.run([sys.executable, '-c', code, directory], env=env,
                                   capture_output=True, timeout=10)
            self.assertEqual(child.returncode, 81)
            root = Path(directory)
            j = r2a0.EvidenceJournal(root)
            self.assertEqual([r['event'] for r in j.read()], ['merge-intent'])
            raw = (next((root/'merge_intents').iterdir())).read_bytes()
            with self.assertRaises(FileExistsError):
                r2a0.write_once(root/'merge_intents'/(r2a0.digest(raw)+'.json'),raw)
            self.assertEqual(len(j.read()), 1)

    def test_receiving_webhook_while_orphan_intent_exists_is_not_202(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            secret=b'test-only-secret-key-32-bytes-long!'
            j=r2a0.EvidenceJournal(root)
            intent={"repo":r2a0.LAB_REPO,"pr":22,"head":"a"*40,
                    "base":"experiment/r2a0-crash","scenario":"Sc1"}
            raw=r2a0.canonical(intent)
            r2a0.write_once(root/'merge_intents'/(r2a0.digest(raw)+'.json'),raw)
            srv=r2a0.make_server(j,secret,'127.0.0.1',0)
            t=threading.Thread(target=srv.serve_forever,daemon=True)
            t.start()
            try:
                body=json.dumps({'repository':{'full_name':r2a0.LAB_REPO},'action':'created'}).encode()
                sig='sha256='+hmac.new(secret,body,hashlib.sha256).hexdigest()
                conn=HTTPConnection('127.0.0.1',srv.server_address[1],timeout=2)
                conn.request('POST','/github-webhook',body,{'X-Hub-Signature-256':sig})
                response=conn.getresponse(); response.read(); conn.close()
                self.assertEqual(response.status,503)
            finally:
                srv.shutdown();srv.server_close();t.join(timeout=2)

    def test_root_symlinked_merge_marker_directory_denied(self):
        if not hasattr(os,'symlink'):
            self.skipTest('no symlink support')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); outside=root/'outside';outside.mkdir()
            try:
                (root/'merge_intents').symlink_to(outside,target_is_directory=True)
            except (OSError,NotImplementedError):
                self.skipTest('no symlink permissions')
            with self.assertRaisesRegex(ValueError,'SYMLINK_EVIDENCE_SUBDIRECTORY'):
                r2a0.EvidenceJournal(root).read()


class TestRecoveryV05(unittest.TestCase):
    """F4: recovery must preserve uncertainty and never retry GitHub merge."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.j = r2a0.EvidenceJournal(self.root)
        self.intent = {"repo": r2a0.LAB_REPO, "pr": 22,
                       "head": "a" * 40, "base": "experiment/r2a0-crash",
                       "scenario": "Sc1"}
        self.raw = r2a0.canonical(self.intent)
        self.marker_hash = r2a0.digest(self.raw)
        self.marker = self.root / "merge_intents" / (self.marker_hash + ".json")

    def tearDown(self):
        self.tmp.cleanup()

    def orphan(self):
        r2a0.write_once(self.marker, self.raw)

    def recorded(self):
        self.orphan()
        self.j.append("merge-intent", "local", self.raw)

    def test_orphan_inspection_holds_and_reads_only(self):
        self.j.append("manual", "fixture", b"old valid event")
        self.orphan()
        before = {p.relative_to(self.root).as_posix(): p.read_bytes()
                  for p in self.root.rglob("*") if p.is_file()}
        with patch.object(r2a0, "gh_api") as gh:
            result = r2a0.inspect_merge_recovery(self.j)
            gh.assert_not_called()
        self.assertEqual(result["journal_integrity"], "HOLD_ORPHAN_INTENT")
        self.assertEqual(result["intents"][0]["journal_stage"], "ORPHAN_MARKER_NOT_JOURNALED")
        self.assertEqual(result["remote_merge_retry"], "FORBIDDEN")
        after = {p.relative_to(self.root).as_posix(): p.read_bytes()
                 for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        with self.assertRaisesRegex(ValueError, "ORPHAN_MERGE_INTENT"):
            self.j.read()

    def test_adoption_requires_ack_and_preserves_old_evidence(self):
        prior = self.j.append("manual", "fixture", b"immutable")
        self.orphan()
        with self.assertRaises(PermissionError):
            r2a0.adopt_single_orphan_intent(self.j, self.marker_hash, ack="")
        with patch.object(r2a0, "gh_api") as gh:
            result = r2a0.adopt_single_orphan_intent(
                self.j, self.marker_hash, ack="RECORD_ORPHAN_ONLY_NO_MERGE_RETRY")
            gh.assert_not_called()
        self.assertEqual(result["status"], "HOLD_OUTCOME_UNKNOWN")
        rows = self.j.read()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], prior)
        self.assertEqual(rows[-1]["meta"]["recovery"], "ORPHAN_MARKER_RECORDED_AFTER_CRASH")
        self.assertEqual(rows[-1]["meta"]["remote_effect"], "UNKNOWN")
        self.assertEqual(self.marker.read_bytes(), self.raw)
        report = r2a0.inspect_merge_recovery(self.j)
        self.assertEqual(report["intents"][0]["journal_stage"], "INTENT_RECORDED_OUTCOME_UNKNOWN")
        self.assertEqual(report["remote_merge_retry"], "FORBIDDEN")

    def test_adoption_twice_never_duplicates(self):
        self.orphan()
        ack = "RECORD_ORPHAN_ONLY_NO_MERGE_RETRY"
        r2a0.adopt_single_orphan_intent(self.j, self.marker_hash, ack=ack)
        with self.assertRaisesRegex(ValueError, "NOT_A_SINGLE_SAFE_TO_RECORD_ORPHAN"):
            r2a0.adopt_single_orphan_intent(self.j, self.marker_hash, ack=ack)
        self.assertEqual(len(self.j.read()), 1)

    def test_unrelated_orphan_claim_blocks_recovery(self):
        self.orphan()
        r2a0.write_once(self.root / "claims" / "000001.json", b"incomplete")
        with self.assertRaises(ValueError):
            r2a0.inspect_merge_recovery(self.j)
        with self.assertRaises(ValueError):
            r2a0.adopt_single_orphan_intent(self.j, self.marker_hash,
                                           ack="RECORD_ORPHAN_ONLY_NO_MERGE_RETRY")

    def test_two_orphans_never_adopted(self):
        self.orphan()
        second = dict(self.intent, pr=23)
        raw = r2a0.canonical(second)
        r2a0.write_once(self.root / "merge_intents" / (r2a0.digest(raw) + ".json"), raw)
        with self.assertRaisesRegex(ValueError, "AMBIGUOUS_OR_UNRECOVERABLE_MERGE_INTENT"):
            r2a0.inspect_merge_recovery(self.j)
        with self.assertRaises(ValueError):
            r2a0.adopt_single_orphan_intent(self.j, self.marker_hash,
                                           ack="RECORD_ORPHAN_ONLY_NO_MERGE_RETRY")

    def test_corrupt_marker_never_recorded(self):
        self.orphan()
        self.marker.write_bytes(b"{}")
        with self.assertRaises(ValueError):
            r2a0.inspect_merge_recovery(self.j)
        with self.assertRaises(ValueError):
            r2a0.adopt_single_orphan_intent(self.j, self.marker_hash,
                                           ack="RECORD_ORPHAN_ONLY_NO_MERGE_RETRY")
        self.assertFalse(self.j.index.exists())

    def test_wrong_hash_never_records(self):
        self.orphan()
        with self.assertRaisesRegex(ValueError, "NOT_A_SINGLE_SAFE_TO_RECORD_ORPHAN"):
            r2a0.adopt_single_orphan_intent(self.j, "0"*64,
                                           ack="RECORD_ORPHAN_ONLY_NO_MERGE_RETRY")
        self.assertFalse(self.j.index.exists())

    def test_committed_intent_without_response_holds(self):
        self.recorded()
        with patch.object(r2a0, "gh_api") as gh:
            result = r2a0.inspect_merge_recovery(self.j)
            gh.assert_not_called()
        self.assertEqual(result["journal_integrity"], "PASS")
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["intents"][0]["journal_stage"], "INTENT_RECORDED_OUTCOME_UNKNOWN")

    def test_ambiguous_response_still_holds(self):
        self.recorded()
        self.j.append("merge-attempt", "gh-api",
                      r2a0.canonical({"status":"MERGE_API_RETURNED", "response":{"_request_ok":False, "_unknown_outcome":True}}),
                      {"pr":22,"scenario":"Sc1","expected_head":"a"*40,"base":"experiment/r2a0-crash","execute":True})
        report = r2a0.inspect_merge_recovery(self.j)
        self.assertEqual(report["intents"][0]["journal_stage"], "RESPONSE_RECORDED_NOT_PROOF_OF_MERGE")
        self.assertEqual(report["status"], "HOLD")

    def _remote(self, merged=False, state="open", head=None, base=None, repo=None):
        return {"_request_ok":True,"_data":{
            "head":{"sha":head or "a"*40},
            "base":{"ref":base or "experiment/r2a0-crash", "repo":{"full_name":repo or r2a0.LAB_REPO}},
            "merged":merged,"state":state,"merge_commit_sha":"b"*40}}

    def test_remote_get_observes_unmerged_but_never_allows_retry(self):
        self.recorded()
        with patch.object(r2a0, "gh_api", return_value=self._remote()) as gh:
            report = r2a0.inspect_merge_recovery(self.j, marker_sha256=self.marker_hash, remote=True)
        self.assertEqual(gh.call_count, 1)
        self.assertEqual(gh.call_args.kwargs["method"], "GET")
        self.assertEqual(report["intents"][0]["remote"]["observation"], "OPEN_UNMERGED_AT_READ_TIME")
        self.assertFalse(report["intents"][0]["remote"]["can_retry"])

    def test_remote_get_merge_true_does_not_claim_attribution(self):
        self.recorded()
        with patch.object(r2a0, "gh_api", return_value=self._remote(merged=True,state="closed")) as gh:
            report = r2a0.inspect_merge_recovery(self.j, remote=True)
        self.assertEqual(gh.call_args.kwargs["method"], "GET")
        self.assertEqual(report["intents"][0]["remote"]["observation"], "MERGED_OBSERVED_ATTRIBUTION_UNKNOWN")
        self.assertEqual(report["status"], "HOLD")

    def test_remote_head_drift_blocks_inference(self):
        self.recorded()
        with patch.object(r2a0, "gh_api", return_value=self._remote(head="c"*40)):
            report = r2a0.inspect_merge_recovery(self.j, remote=True)
        self.assertEqual(report["intents"][0]["remote"]["observation"], "REMOTE_TARGET_DRIFT_HOLD")

    def test_remote_read_error_unknown(self):
        self.recorded()
        with patch.object(r2a0, "gh_api", return_value={"_request_ok":False,"_http_status":503}):
            report = r2a0.inspect_merge_recovery(self.j, remote=True)
        self.assertEqual(report["intents"][0]["remote"]["observation"], "REMOTE_GET_UNKNOWN")

    def test_multiple_intents_require_explicit_remote_selection(self):
        self.recorded()
        new = dict(self.intent,pr=23)
        raw=r2a0.canonical(new)
        r2a0.write_once(self.root / "merge_intents" / (r2a0.digest(raw)+".json"), raw)
        self.j.append("merge-intent","local",raw)
        with patch.object(r2a0, "gh_api") as gh:
            with self.assertRaisesRegex(ValueError,"REMOTE_INSPECTION_REQUIRES_SINGLE_INTENT"):
                r2a0.inspect_merge_recovery(self.j, remote=True)
            gh.assert_not_called()

    def test_ack_checked_before_reservation_no_writes(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(r2a0,"authorized_merge") as merge:
            ret = r2a0.main(["attempt-merge", "--pr","22", "--scenario","Sc1", "--base","experiment/r2a0-crash",
                             "--expected-head","a"*40,"--execute","--evidence-dir",str(self.root)])
            self.assertEqual(ret,2)
            merge.assert_not_called()
        self.assertFalse(any(self.root.iterdir()))

    def test_live_remote_flag_never_writes_journal(self):
        self.recorded()
        before = self.j.index.read_bytes()
        with patch.object(r2a0,"gh_api",return_value=self._remote()) as gh:
            r2a0.inspect_merge_recovery(self.j, remote=True)
            gh.assert_called_once()
        self.assertEqual(self.j.index.read_bytes(),before)

    def test_crash_subprocess_marker_adoption_preserves_claim(self):
        # Real subprocess death between durable reservation and journal.
        import subprocess as sp
        fixture = """import sys, pathlib\nfrom pathlib import Path\nsys.path.insert(0, sys.argv[2])\nimport r2a0\nintent={"repo":r2a0.LAB_REPO,"pr":22,"head":"a"*40,"base":"experiment/r2a0-crash","scenario":"Sc1"}\nraw=r2a0.canonical(intent)\nr2a0.write_once(Path(sys.argv[1])/"merge_intents"/(r2a0.digest(raw)+".json"),raw)\nimport os;os._exit(73)"""
        cp=sp.run([sys.executable,"-c",fixture,str(self.root),str(Path(r2a0.__file__).parent)],
                  stdout=sp.PIPE,stderr=sp.PIPE,timeout=10)
        self.assertEqual(cp.returncode,73)
        with self.assertRaisesRegex(ValueError,"ORPHAN_MERGE_INTENT"):
            self.j.read()
        result=r2a0.inspect_merge_recovery(self.j)
        self.assertEqual(result["intents"][0]["journal_stage"],"ORPHAN_MARKER_NOT_JOURNALED")
        with patch.object(r2a0,"gh_api") as gh:
            adopt=r2a0.adopt_single_orphan_intent(self.j,self.marker_hash,
                      ack="RECORD_ORPHAN_ONLY_NO_MERGE_RETRY")
            gh.assert_not_called()
        self.assertEqual(adopt["status"],"HOLD_OUTCOME_UNKNOWN")
        self.assertEqual(len(self.j.read()),1)

class TestRecoveryCliGuardsV05(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.intent={"repo":r2a0.LAB_REPO,"pr":22,"head":"a"*40,"base":"experiment/r2a0-crash","scenario":"Sc1"}
        self.raw=r2a0.canonical(self.intent)
        self.j=r2a0.EvidenceJournal(self.root)
    def tearDown(self):
        self.tmp.cleanup()

    def test_no_blind_retry_even_if_scenario_changes(self):
        raw=self.raw
        r2a0.write_once(self.root/"merge_intents"/(r2a0.digest(raw)+".json"),raw)
        self.j.append("merge-intent","local",raw)
        with patch.dict(os.environ,{"ARIO_R2A0_DISPOSABLE_MERGE_ACK":"EXPLICITLY_ALLOW_LAB_MERGE"}),patch.object(r2a0,"authorized_merge") as merge:
            ret=r2a0.main(["attempt-merge","--pr","22","--scenario","Sc2","--base","experiment/r2a0-crash","--expected-head","a"*40,"--execute","--evidence-dir",str(self.root)])
            self.assertEqual(ret,2)
            merge.assert_not_called()
        self.assertEqual(len(self.j.read()),1)
        self.assertEqual(len(list((self.root/"merge_intents").iterdir())),1)

    def test_verify_integrity_pass_is_not_merge_authority(self):
        import contextlib,io
        raw=self.raw
        r2a0.write_once(self.root/"merge_intents"/(r2a0.digest(raw)+".json"),raw)
        self.j.append("merge-intent","local",raw)
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(r2a0.main(["verify","--evidence-dir",str(self.root)]),0)
        result=json.loads(output.getvalue())
        self.assertEqual(result["journal_integrity"],"PASS")
        self.assertEqual(result["merge_intent_safety"],"HOLD_REQUIRES_RECONCILIATION")
        self.assertEqual(result["native_merge_authority"],"NOT_GRANTED")

    def test_record_orphan_crash_after_claim_blocks_everything(self):
        intent=self.raw
        h=r2a0.digest(intent)
        r2a0.write_once(self.root/"merge_intents"/(h+".json"),intent)
        original=r2a0.write_once
        def crash_after_claim(path,data):
            original(path,data)
            if Path(path).parent.name == "claims":
                raise OSError("injected process interruption")
        with patch.object(r2a0,"write_once",side_effect=crash_after_claim),patch.object(r2a0,"gh_api") as gh:
            with self.assertRaises(OSError):
                r2a0.adopt_single_orphan_intent(self.j,h,ack="RECORD_ORPHAN_ONLY_NO_MERGE_RETRY")
            gh.assert_not_called()
        with self.assertRaises(ValueError):
            r2a0.inspect_merge_recovery(self.j)
        self.assertTrue(any((self.root/"claims").iterdir()))

class TestRecoveryTwoRealProcessesV06(unittest.TestCase):
    """Same-host independent OS processes, not independent custodians/hosts."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "evidence"
        self.root.mkdir()
        self.gate = Path(self.tmp.name) / "gate"
        self.gate.mkdir()
        self.j = r2a0.EvidenceJournal(self.root)
        self.original = self.j.append("manual", "fixture", b"immutable history")
        self.intent = {"repo": r2a0.LAB_REPO, "pr": 22, "head": "a"*40,
                       "base": "experiment/r2a0-crash", "scenario": "Sc1"}
        self.raw = r2a0.canonical(self.intent)
        self.marker_hash = r2a0.digest(self.raw)
        self.marker = self.root / "merge_intents" / (self.marker_hash + ".json")
        r2a0.write_once(self.marker, self.raw)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _worker_script():
        # Event is synchronized AFTER both processes have independently passed
        # orphan preflight, immediately BEFORE durable journal append.
        return r'''
import json, os, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[4])
import r2a0
root=Path(sys.argv[1]); marker_hash=sys.argv[2]
worker=sys.argv[3]; gate=Path(sys.argv[5]); crash=sys.argv[6]=='crash'

def fail_if_network(*a, **kw):
    raise AssertionError('RECOVERY_MUST_NEVER_CALL_GITHUB')
r2a0.gh_api=fail_if_network
orig_append=r2a0.EvidenceJournal.append
orig_write=r2a0.write_once

def wait_append(self,event,source,data,meta=None):
    if event=='merge-intent':
        orig_write(gate/(worker+'.ready'),b'PASSED_ORPHAN_PREFLIGHT')
        until=time.monotonic()+8
        while not (gate/'GO').exists():
            if time.monotonic()>until: raise TimeoutError('BARRIER_TIMEOUT')
            time.sleep(.005)
    return orig_append(self,event,source,data,meta)

def abort_after_claim(path,data):
    orig_write(path,data)
    if Path(path).parent.name=='claims':
        os._exit(73)
r2a0.EvidenceJournal.append=wait_append
if crash:
    r2a0.write_once=abort_after_claim
try:
    result=r2a0.adopt_single_orphan_intent(r2a0.EvidenceJournal(root),marker_hash,
        ack='RECORD_ORPHAN_ONLY_NO_MERGE_RETRY')
    print(json.dumps({'worker':worker,'outcome':'RECORDED','result':result}),flush=True)
except Exception as e:
    print(json.dumps({'worker':worker,'outcome':'HOLD','exception':type(e).__name__,
                      'message':str(e)}),flush=True)
'''

    def _race(self, *, crash=False):
        import subprocess as sp
        script=self._worker_script()
        processes=[]
        for worker in ('w1','w2'):
            args=[sys.executable,'-c',script,str(self.root),self.marker_hash,worker,
                  str(Path(r2a0.__file__).parent),str(self.gate),
                  'crash' if crash else 'normal']
            # Explicit approval env must NEVER turn recovery into a merge attempt.
            env=dict(os.environ,ARIO_R2A0_DISPOSABLE_MERGE_ACK='EXPLICITLY_ALLOW_LAB_MERGE')
            processes.append(sp.Popen(args,stdout=sp.PIPE,stderr=sp.PIPE,env=env))
        try:
            deadline=time.monotonic()+10
            while not all((self.gate/(w+'.ready')).exists() for w in ('w1','w2')):
                if time.monotonic()>deadline:
                    raise AssertionError('BOTH_CONTENDERS_DID_NOT_REACH_BARRIER')
                if any(p.poll() is not None for p in processes):
                    raise AssertionError('CONTENDER_EXITED_BEFORE_RACE')
                time.sleep(.005)
            r2a0.write_once(self.gate/'GO',b'start')
            return [(p.returncode, json.loads(stdout.strip()) if stdout.strip() else None,
                     stderr.decode('utf-8',errors='replace')[:1000])
                    for p in processes
                    for stdout,stderr in [p.communicate(timeout=12)] ]
        finally:
            for p in processes:
                if p.poll() is None:
                    p.kill();p.wait(timeout=3)

    def test_two_processes_same_orphan_at_most_one_recovery_record(self):
        results=self._race()
        self.assertTrue(all(rc==0 for rc,_,_ in results),results)
        self.assertEqual(sum(o['outcome']=='RECORDED' for _,o,_ in results),1,results)
        self.assertEqual(sum(o['outcome']=='HOLD' for _,o,_ in results),1,results)
        rows=self.j.read()
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0],self.original)
        self.assertEqual(rows[1]['event'],'merge-intent')
        self.assertEqual(rows[1]['meta']['remote_put_retried'],False)
        report=r2a0.inspect_merge_recovery(self.j)
        self.assertEqual(report['status'],'HOLD')
        self.assertEqual(report['remote_merge_retry'],'FORBIDDEN')
        self.assertEqual(report['intents'][0]['journal_stage'],'INTENT_RECORDED_OUTCOME_UNKNOWN')
        self.assertEqual(len(list((self.root/'merge_intents').glob('*.json'))),1)

    def test_two_processes_one_crashes_after_claim_both_fail_closed(self):
        results=self._race(crash=True)
        self.assertEqual(sum(rc==73 for rc,_,_ in results),1,results)
        self.assertEqual(sum(o is not None and o['outcome']=='HOLD' for _,o,_ in results),1,results)
        with self.assertRaises(ValueError):
            self.j.read()
        with self.assertRaises(ValueError):
            r2a0.inspect_merge_recovery(self.j)
        self.assertTrue((self.root/'merge_intents'/(self.marker_hash+'.json')).exists())
        self.assertTrue((self.root/'claims'/'000002.json').exists())
        self.assertEqual(len(self.j.index.read_bytes().splitlines()),1)
        self.assertEqual(r2a0.canonical(self.original), self.j.index.read_bytes().strip())

    def test_parallel_readers_cannot_grant_retry_or_modify_evidence(self):
        import subprocess as sp
        before={p.relative_to(self.root).as_posix():p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}
        cmd=[sys.executable,str(Path(r2a0.__file__)), 'inspect-recovery',
             '--evidence-dir',str(self.root)]
        a=sp.Popen(cmd,stdout=sp.PIPE,stderr=sp.PIPE)
        b=sp.Popen(cmd,stdout=sp.PIPE,stderr=sp.PIPE)
        results=[]
        for proc in (a,b):
            out,err=proc.communicate(timeout=10)
            self.assertEqual(proc.returncode,0,err.decode())
            data=json.loads(out)
            self.assertEqual(data['remote_merge_retry'],'FORBIDDEN')
            self.assertEqual(data['journal_integrity'],'HOLD_ORPHAN_INTENT')
            self.assertEqual(data['merge_authorization'],'NOT_GRANTED')
            results.append(data)
        after={p.relative_to(self.root).as_posix():p.read_bytes()
               for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before,after)
        self.assertEqual(results[0]['intents'],results[1]['intents'])
