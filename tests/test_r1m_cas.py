"""R1m bounded CAS semantics, identity checks, response-loss and no retry.

Unit tests only use mocks: they prove local code behavior, not GitHub platform
atomicity. The real two-VM test is in the R1m sandbox GitHub Actions workflow.
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import r1m_github_ref_cas as m
from r1m_ref_audit import audit_outcomes


SHA = "a" * 40
CFG = {"run_id": "43499999999", "run_attempt": "1", "sha": SHA,
       "role": "linux"}


def env():
    return {
        "GITHUB_REPOSITORY": m.REPO,
        "GITHUB_REF": "refs/heads/" + m.BRANCH,
        "GITHUB_EVENT_NAME": "push", "R1M_ROLE": "linux",
        "GITHUB_RUN_ID": CFG["run_id"], "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": SHA, "R1M_GITHUB_TOKEN": "FAKE_TOKEN_NOT_SECRET_12345678",
        "GITHUB_OUTPUT": "output_file.txt",
    }


class R1mPureTests(unittest.TestCase):
    def test_01_correct_lab_env(self):
        self.assertEqual(m.verify_environment(env())["sha"], SHA)

    def test_02_reject_production_repo(self):
        v = env()
        v["GITHUB_REPOSITORY"] = "SepehrGhanbari/Ario"
        with self.assertRaisesRegex(RuntimeError, "REPO_SCOPE"):
            m.verify_environment(v)

    def test_03_reject_main_branch(self):
        v = env()
        v["GITHUB_REF"] = "refs/heads/main"
        with self.assertRaisesRegex(RuntimeError, "BRANCH_SCOPE"):
            m.verify_environment(v)

    def test_04_reject_pr_event(self):
        v = env()
        v["GITHUB_EVENT_NAME"] = "pull_request"
        with self.assertRaisesRegex(RuntimeError, "EVENT_SCOPE"):
            m.verify_environment(v)

    def test_05_reject_fake_role(self):
        v = env()
        v["R1M_ROLE"] = "third"
        with self.assertRaisesRegex(RuntimeError, "ROLE_SCOPE"):
            m.verify_environment(v)

    def test_06_reject_invalid_head(self):
        v = env()
        v["GITHUB_SHA"] = "Z" * 40
        with self.assertRaisesRegex(RuntimeError, "INVALID_COMMIT_SHA"):
            m.verify_environment(v)

    def test_07_refs_per_run_phase_role_are_disjoint(self):
        names = {m.ref_name(CFG, phase, "ready", role)
                 for phase in m.PHASES for role in m.ROLES}
        names.update(m.ref_name(CFG, phase, "claim") for phase in m.PHASES)
        self.assertEqual(len(names), 6)
        self.assertTrue(all(name.startswith("r1m-lab-") for name in names))

    def test_08_ready_barrier_checks_other_role(self):
        mine = m.ref_name(CFG, "baseline", "ready", "linux")
        other = m.ref_name(CFG, "baseline", "ready", "windows")
        calls = []
        def fake_post(ref, sha, token):
            calls.append(("POST", ref))
            return 201, {"ref": "refs/tags/" + mine, "object": {"sha": SHA}}
        def fake_read(ref, sha, token, attempts=m.READ_BUDGET):
            calls.append(("GET", ref))
            return ref in (mine, other)
        with patch.object(m, "create_ref", side_effect=fake_post), \
             patch.object(m, "read_existing", side_effect=fake_read):
            m.ready_phase(CFG, "baseline", "not-real")
        self.assertEqual([verb for verb, _ in calls].count("POST"), 1)
        self.assertIn(("GET", other), calls)

    def test_09_winner_201_readback(self):
        claim = m.ref_name(CFG, "baseline", "claim")
        with patch.object(m, "create_ref", return_value=(
                201, {"ref": "refs/tags/" + claim, "object": {"sha": SHA}})), \
             patch.object(m, "read_existing", return_value=True):
            out = m.attempt_phase(CFG, "baseline", "fake")
        self.assertEqual(out["outcome"], "CREATED")
        self.assertFalse(out["repost_attempted"])
        self.assertFalse(out["can_publish"])

    def test_10_loser_422_requires_live_get(self):
        with patch.object(m, "create_ref", return_value=(422, {})) as post, \
             patch.object(m, "read_existing", return_value=True):
            out = m.attempt_phase(CFG, "baseline", "fake")
        self.assertEqual(post.call_count, 1)
        self.assertEqual(out["outcome"], "EXISTING_AFTER_422")
        self.assertFalse(out["repost_attempted"])

    def test_11_422_without_ref_must_hold(self):
        with patch.object(m, "create_ref", return_value=(422, {})) as post, \
             patch.object(m, "read_existing", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "POST_422_WITHOUT_MATCHING"):
                m.attempt_phase(CFG, "baseline", "fake")
        self.assertEqual(post.call_count, 1)

    def test_12_response_503_must_not_retry(self):
        with patch.object(m, "create_ref", return_value=(503, {})) as post:
            with self.assertRaisesRegex(RuntimeError, "AMBIGUOUS_POST_OUTCOME"):
                m.attempt_phase(CFG, "baseline", "fake")
        self.assertEqual(post.call_count, 1)

    def test_13_post_lost_response_requires_readback(self):
        with patch.object(m, "create_ref", return_value=(201, {})) as post, \
             patch.object(m, "read_existing", return_value=True) as get:
            out = m.attempt_phase(CFG, "lostreply", "fake")
        self.assertEqual(out["outcome"], "OBSERVED_AFTER_SIMULATED_LOST_REPLY")
        self.assertEqual(post.call_count, 1)
        self.assertEqual(get.call_count, 1)
        self.assertFalse(out["repost_attempted"])

    def test_14_post_lost_response_no_ref_must_hold(self):
        with patch.object(m, "create_ref", return_value=(None, {})) as post, \
             patch.object(m, "read_existing", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "AMBIGUOUS_OUTCOME_NOT_VISIBLE"):
                m.attempt_phase(CFG, "lostreply", "fake")
        self.assertEqual(post.call_count, 1)

    def test_15_wrong_sha_post_response_holds(self):
        claim = m.ref_name(CFG, "baseline", "claim")
        with patch.object(m, "create_ref", return_value=(201, {
                "ref": "refs/tags/" + claim, "object": {"sha": "b"*40}})):
            with self.assertRaisesRegex(RuntimeError, "POST_201_BODY_CONFLICT"):
                m.attempt_phase(CFG, "baseline", "fake")

    def test_16_invalid_ref_role_fails_pre_post(self):
        with self.assertRaisesRegex(RuntimeError, "READY_ROLE"):
            m.ref_name(CFG, "baseline", "ready", "production")

    def test_17_audit_requires_one_created_one_conflict(self):
        audit_outcomes({"baseline": "CREATED",
                        "lostreply": "OBSERVED_AFTER_SIMULATED_LOST_REPLY"},
                       {"baseline": "EXISTING_AFTER_422", "lostreply": "CREATED"})

    def test_18_audit_rejects_two_created(self):
        with self.assertRaisesRegex(RuntimeError, "NO_UNIQUE_CREATE_OBSERVED"):
            audit_outcomes({"baseline": "CREATED",
                            "lostreply": "OBSERVED_AFTER_SIMULATED_LOST_REPLY"},
                           {"baseline": "CREATED", "lostreply": "CREATED"})

    def test_19_audit_rejects_no_winner(self):
        with self.assertRaisesRegex(RuntimeError, "NO_UNIQUE_CREATE_OBSERVED"):
            audit_outcomes({"baseline": "EXISTING_AFTER_422",
                            "lostreply": "OBSERVED_AFTER_SIMULATED_LOST_REPLY"},
                           {"baseline": "EXISTING_AFTER_422", "lostreply": "CREATED"})

    def test_20_audit_rejects_missing_loss_reconciliation(self):
        with self.assertRaisesRegex(RuntimeError, "LOST_REPLY_EVIDENCE_MISSING"):
            audit_outcomes({"baseline": "CREATED", "lostreply": "UNKNOWN_HOLD"},
                           {"baseline": "EXISTING_AFTER_422", "lostreply": "CREATED"})

    def test_21_run_outputs_have_no_check_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "output.txt"
            out.touch()
            m.emit_outputs(out, {"baseline": {"outcome": "CREATED"},
                                "lostreply": {"outcome": "OBSERVED_AFTER_SIMULATED_LOST_REPLY"}})
            data = out.read_text()
            self.assertIn("baseline_result=CREATED", data)
            self.assertNotIn("checks:write", data)
            self.assertNotIn("Bearer ", data)


if __name__ == "__main__":
    unittest.main()
