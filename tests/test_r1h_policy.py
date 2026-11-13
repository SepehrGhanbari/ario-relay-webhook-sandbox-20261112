"""R1h research-only policy probes. All signatures, repos and logs mocked."""
import copy
import unittest

from r1h_policy import review_receipt

REPO = "SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a"
HEAD = "a" * 40
BASE = "b" * 40
EVALUATOR = "c" * 40
RUNNER = "d" * 64
SUITE = "e" * 64
LOG = "f" * 64


def fixture():
    pr = {
        "number": 17, "state": "open", "merged": False, "draft": False,
        "head": {"sha": HEAD, "repo": {"full_name": REPO}},
        "base": {"sha": BASE, "ref": "experiment/r1d-required-app-rule-20261113",
                 "repo": {"full_name": REPO}},
    }
    policy = {
        "repo": REPO, "pr_number": 17, "head_sha": HEAD, "base_sha": BASE,
        "base_ref": "experiment/r1d-required-app-rule-20261113",
        "nonce": "trusted-single-use-receipt-17", "evaluator_sha": EVALUATOR,
        "runner_digest": RUNNER, "suite_sha256": SUITE,
        "required_tests": ("ledger", "parser", "workflow"),
        "signer_key_id": "protected-lab-test-key",
    }
    receipt = {
        "schema": "r1h-attestation-v1",
        "repo": REPO, "pr_number": 17, "head_sha": HEAD, "base_sha": BASE,
        "base_ref": "experiment/r1d-required-app-rule-20261113",
        "nonce": "trusted-single-use-receipt-17", "evaluator_sha": EVALUATOR,
        "runner_digest": RUNNER, "suite_sha256": SUITE,
        "log_sha256": LOG, "exit_code": 0,
        "tests": [{"id": x, "result": "passed"} for x in ("ledger", "parser", "workflow")],
    }
    return pr, {"receipt": receipt, "signature": {
        "key_id": "protected-lab-test-key", "value": "MOCK_SIGNATURE_NO_REAL_CRYPTO"
    }}, policy


class OfflineEvidencePolicyTests(unittest.TestCase):
    def run_policy(self, tweak=None, verifier=None):
        pr, envelope, policy = fixture()
        if tweak:
            tweak(pr, envelope, policy)
        return review_receipt(current_pr=pr, envelope=envelope,
                              protected_policy=policy,
                              verify_detached=verifier if verifier is not None
                              else (lambda key, payload, sig: True))

    def assert_hold(self, tweak, expected):
        result = self.run_policy(tweak)
        self.assertEqual(result["decision"], "HOLD")
        self.assertEqual(result["reason"], expected)
        self.assertFalse(result["merge_authorized"])
        self.assertFalse(result["check_run_published"])

    def test_01_good_claims_are_reviewable_only(self):
        result = self.run_policy()
        self.assertEqual(result["decision"], "EVIDENCE_REVIEWABLE")
        self.assertEqual(result["head_sha"], HEAD)
        self.assertFalse(result["merge_authorized"])
        self.assertFalse(result["check_run_published"])

    def test_02_bad_signature(self):
        result = self.run_policy(verifier=lambda *args: False)
        self.assertEqual((result["decision"], result["reason"]),
                         ("HOLD", "SIGNATURE_NOT_VERIFIED"))

    def test_03_integer_signature_answer_not_true_boolean(self):
        result = self.run_policy(verifier=lambda *args: 1)
        self.assertEqual(result["reason"], "SIGNATURE_NOT_VERIFIED")

    def test_04_missing_verifier(self):
        pr, envelope, policy = fixture()
        result = review_receipt(current_pr=pr, envelope=envelope,
                                protected_policy=policy, verify_detached=None)
        self.assertEqual(result["reason"], "NO_SIGNATURE_VERIFIER")

    def test_05_stale_head(self):
        self.assert_hold(lambda p,e,q: p["head"].update(sha="1"*40), "HEAD_BASE_DRIFT")

    def test_06_stale_base(self):
        self.assert_hold(lambda p,e,q: p["base"].update(sha="2"*40), "HEAD_BASE_DRIFT")

    def test_07_missing_required_test(self):
        self.assert_hold(lambda p,e,q: e["receipt"]["tests"].pop(), "REQUIRED_TEST_SET")

    def test_08_skipped_required_test(self):
        self.assert_hold(lambda p,e,q: e["receipt"]["tests"][0].update(result="skipped"),
                         "TEST_NOT_PASS")

    def test_09_neutral_required_test(self):
        self.assert_hold(lambda p,e,q: e["receipt"]["tests"][0].update(result="neutral"),
                         "TEST_NOT_PASS")

    def test_10_failed_required_test(self):
        self.assert_hold(lambda p,e,q: e["receipt"]["tests"][0].update(result="failed"),
                         "TEST_NOT_PASS")

    def test_11_zero_tests(self):
        self.assert_hold(lambda p,e,q: e["receipt"].update(tests=[]), "NO_TESTS")

    def test_12_duplicate_test(self):
        def tweak(p,e,q):
            e["receipt"]["tests"][1]["id"] = "ledger"
        self.assert_hold(tweak, "DUPLICATE_TEST_ID")

    def test_13_unpinned_evaluator(self):
        self.assert_hold(lambda p,e,q: e["receipt"].update(evaluator_sha="1"*40),
                         "EVALUATOR_PIN")

    def test_14_unpinned_runner(self):
        self.assert_hold(lambda p,e,q: e["receipt"].update(runner_digest="2"*64),
                         "RUNNER_PIN")

    def test_15_wrong_test_suite(self):
        self.assert_hold(lambda p,e,q: e["receipt"].update(suite_sha256="3"*64),
                         "SUITE_PIN")

    def test_16_missing_log_digest(self):
        self.assert_hold(lambda p,e,q: e["receipt"].update(log_sha256="NONE"),
                         "LOG_DIGEST")

    def test_17_cross_repo_attestation(self):
        self.assert_hold(lambda p,e,q: e["receipt"].update(repo="other/project"),
                         "REPOSITORY")

    def test_18_wrong_signer(self):
        self.assert_hold(lambda p,e,q: e["signature"].update(key_id="impostor"),
                         "SIGNER_ID")

    def test_19_wrong_nonce(self):
        self.assert_hold(lambda p,e,q: e["receipt"].update(nonce="replayed"),
                         "NONCE")

    def test_20_draft_is_not_positive(self):
        self.assert_hold(lambda p,e,q: p.update(draft=True), "PR_NOT_READY")

    def test_21_closed_pr(self):
        self.assert_hold(lambda p,e,q: p.update(state="closed"), "PR_NOT_READY")

    def test_22_boolean_exit_code_not_zero_int(self):
        self.assert_hold(lambda p,e,q: e["receipt"].update(exit_code=False),
                         "EXIT_NOT_ZERO")

    def test_23_extra_envelope_field(self):
        self.assert_hold(lambda p,e,q: e.update(fake_override=True),
                         "ENVELOPE_SHAPE")

    def test_24_extra_receipt_field(self):
        self.assert_hold(lambda p,e,q: e["receipt"].update(success=True),
                         "RECEIPT_FIELDS")

    def test_25_invalid_head_format(self):
        self.assert_hold(lambda p,e,q: e["receipt"].update(head_sha="Z"*40),
                         "HEAD_BASE_DRIFT")

    def test_26_base_ref_renamed(self):
        self.assert_hold(lambda p,e,q: p["base"].update(ref="main"),
                         "BASE_REF")

    def test_27_extra_test_result_field(self):
        self.assert_hold(lambda p,e,q: e["receipt"]["tests"][0].update(skipped=False),
                         "TEST_SHAPE")

    def test_28_signature_is_over_the_whole_claims_receipt(self):
        def verify(key, message, signature):
            self.assertIn(b'"head_sha":"'+HEAD.encode()+b'"', message)
            self.assertIn(b'"tests"', message)
            self.assertNotIn(b'MOCK_SIGNATURE_NO_REAL_CRYPTO', message)
            return True
        result = self.run_policy(verifier=verify)
        self.assertEqual(result["decision"], "EVIDENCE_REVIEWABLE")


if __name__ == "__main__":
    unittest.main()
