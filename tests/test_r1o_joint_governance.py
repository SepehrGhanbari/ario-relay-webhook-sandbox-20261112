"""R1o mocked-verifier experiments only. No permanent key or live signer.

Fixtures use opaque strings and test-only True-returning verification callbacks.
Passing here is NOT cryptographic proof of independent Ario custody.
"""
from dataclasses import replace
import unittest

from r1o_joint_governance import (
    RootPolicy, Request, Vote, Decision, canonical_request_digest, evaluate
)

F = "1" * 64
A = "2" * 64
P = "3" * 64
HEAD = "a" * 40
NEW = "b" * 40


def root(phase="JOINT", **changes):
    x = RootPolicy(phase=phase, version=1, founder_key_id=F,
                   ario_key_id=A, policy_digest=P)
    return replace(x, **changes)


def request(phase="JOINT", action="governance_change", **changes):
    x = Request(repo="SepehrGhanbari/Ario", phase=phase, version=1,
                action=action, policy_digest=P, old_head=HEAD,
                proposed_head=NEW, change_digest="4"*64,
                evidence_digest="5"*64, evidence_result="PASS",
                ledger_anchor="6"*64)
    return replace(x, **changes)


def votes(req, roles=("founder", "ario")):
    return tuple(Vote(role=role, key_id=F if role == "founder" else A,
                      signed_request_digest=canonical_request_digest(req),
                      opaque_signature="MOCK_SIGNED_" + role.upper())
                 for role in roles)


def verifier(key, digest, signature):
    return key in (F, A) and digest and signature.startswith("MOCK_SIGNED_")


def checks(**changes):
    kw = {
        "verify_signature": verifier,
        "verify_evidence": lambda req: True,
        "verify_current_state": lambda req: True,
        "verify_ledger_anchor": lambda req: True,
        "verify_independent_custody": lambda policy: True,
    }
    kw.update(changes)
    return kw


class R1oGovernanceTests(unittest.TestCase):
    def assert_no_authority(self, result):
        self.assertFalse(result.can_merge)
        self.assertFalse(result.can_publish)
        self.assertFalse(result.can_activate_trust)
        self.assertFalse(result.can_rotate_key)
        self.assertFalse(result.delegation_activated)
        self.assertEqual(result.production_trust, "NO_GO")

    def test_01_joint_two_distinct_mock_votes_and_receipt_eligible_only(self):
        r = request()
        result = evaluate(root(), r, votes(r), **checks())
        self.assertEqual(result.verdict, "ELIGIBLE_FOR_EXTERNAL_REVIEW")
        self.assertTrue(result.eligible_for_external_review)
        self.assert_no_authority(result)

    def test_02_founder_alone_cannot_change_governance_in_joint(self):
        r = request()
        out = evaluate(root(), r, votes(r, ("founder",)), **checks())
        self.assertEqual(out.reason, "JOINT_TWO_DISTINCT_ROLES_REQUIRED")
        self.assert_no_authority(out)

    def test_03_ario_alone_cannot_change_governance_in_joint(self):
        r = request()
        out = evaluate(root(), r, votes(r, ("ario",)), **checks())
        self.assertEqual(out.reason, "JOINT_TWO_DISTINCT_ROLES_REQUIRED")
        self.assert_no_authority(out)

    def test_04_two_founder_votes_not_two_roles(self):
        r = request()
        out = evaluate(root(), r, votes(r, ("founder", "founder")), **checks())
        self.assertEqual(out.reason, "DUPLICATE_ROLE_VOTE")
        self.assert_no_authority(out)

    def test_05_two_votes_with_same_key_fail_even_if_roles_different(self):
        r = request()
        a, b = votes(r)
        out = evaluate(root(), r, (a, replace(b, key_id=F)), **checks())
        self.assertIn(out.reason, ("SAME_KEY_FOR_MULTIPLE_VOTES", "VOTE_KEY_OR_PROOF_MISMATCH"))
        self.assert_no_authority(out)

    def test_06_root_same_key_for_founder_ario_rejected(self):
        r = request()
        out = evaluate(root(ario_key_id=F), r, votes(r), **checks())
        self.assertEqual(out.reason, "ROOT_POLICY_INVALID")
        self.assert_no_authority(out)

    def test_07_ava_role_does_not_become_signer(self):
        r = request()
        a = Vote("ava", A, canonical_request_digest(r), "MOCK_SIGNED_AVA")
        out = evaluate(root(), r, (a,), **checks())
        self.assertEqual(out.reason, "NON_GOVERNANCE_ACTOR")
        self.assert_no_authority(out)

    def test_08_missing_evidence_verifier_is_hold(self):
        r = request()
        out = evaluate(root(), r, votes(r), **checks(verify_evidence=None))
        self.assertEqual(out.reason, "INDEPENDENT_VERIFICATION_NOT_CONFIGURED")
        self.assert_no_authority(out)

    def test_09_fake_true_in_evidence_status_does_not_equal_pass(self):
        r = request(evidence_result="UNKNOWN")
        out = evaluate(root(), r, votes(r), **checks())
        self.assertEqual(out.reason, "EVIDENCE_NOT_PASS_UNKNOWN")
        self.assert_no_authority(out)

    def test_10_fail_evidence_is_hold(self):
        r = request(evidence_result="FAIL")
        out = evaluate(root(), r, votes(r), **checks())
        self.assertEqual(out.reason, "EVIDENCE_NOT_PASS_FAIL")

    def test_11_incomplete_evidence_is_hold(self):
        r = request(evidence_result="INCOMPLETE")
        out = evaluate(root(), r, votes(r), **checks())
        self.assertEqual(out.reason, "EVIDENCE_NOT_PASS_INCOMPLETE")

    def test_12_claimed_pass_but_evidence_verifier_rejects(self):
        r = request()
        out = evaluate(root(), r, votes(r),
                       **checks(verify_evidence=lambda req: False))
        self.assertEqual(out.reason, "EVIDENCE_UNKNOWN_OR_FAILED")
        self.assert_no_authority(out)

    def test_13_current_sha_changed_is_hold(self):
        r = request()
        out = evaluate(root(), r, votes(r),
                       **checks(verify_current_state=lambda req: False))
        self.assertEqual(out.reason, "PR_OR_POLICY_CHANGED")
        self.assert_no_authority(out)

    def test_14_ledger_anchor_unverified_is_hold(self):
        r = request()
        out = evaluate(root(), r, votes(r),
                       **checks(verify_ledger_anchor=lambda req: False))
        self.assertEqual(out.reason, "AUDIT_LEDGER_NOT_VERIFIED")
        self.assert_no_authority(out)

    def test_15_independent_custody_unverified_is_hold(self):
        r = request()
        out = evaluate(root(), r, votes(r),
                       **checks(verify_independent_custody=lambda root: False))
        self.assertEqual(out.reason, "INDEPENDENT_CUSTODY_NOT_VERIFIED")
        self.assert_no_authority(out)

    def test_16_signature_verifier_absent_is_hold(self):
        r = request()
        out = evaluate(root(), r, votes(r), **checks(verify_signature=None))
        self.assertEqual(out.reason, "NO_INDEPENDENT_SIGNATURE_VERIFIER")
        self.assert_no_authority(out)

    def test_17_signature_verifier_rejects_is_hold(self):
        r = request()
        out = evaluate(root(), r, votes(r),
                       **checks(verify_signature=lambda *args: False))
        self.assertEqual(out.reason, "SIGNATURE_INVALID_OR_UNKNOWN")
        self.assert_no_authority(out)

    def test_18_signature_verifier_raises_unknown_hold(self):
        r = request()
        def broken(*args):
            raise RuntimeError("unreachable")
        out = evaluate(root(), r, votes(r),
                       **checks(verify_signature=broken))
        self.assertEqual(out.verdict, "UNKNOWN_HOLD")
        self.assertEqual(out.reason, "SIGNATURE_VERIFICATION_UNAVAILABLE")
        self.assert_no_authority(out)

    def test_19_evidence_verifier_exception_unknown_hold(self):
        r = request()
        def broken(_):
            raise TimeoutError("no response")
        out = evaluate(root(), r, votes(r),
                       **checks(verify_evidence=broken))
        self.assertEqual(out.verdict, "UNKNOWN_HOLD")
        self.assert_no_authority(out)

    def test_20_replayed_signature_for_changed_request_fails(self):
        before = request()
        after = replace(before, change_digest="f"*64)
        out = evaluate(root(), after, votes(before), **checks())
        self.assertEqual(out.reason, "VOTE_SIGNED_ANOTHER_REQUEST")
        self.assert_no_authority(out)

    def test_21_signature_for_old_head_replayed_on_new_head_fails(self):
        before = request()
        after = replace(before, old_head="d"*40)
        out = evaluate(root(), after, votes(before), **checks())
        self.assertEqual(out.reason, "VOTE_SIGNED_ANOTHER_REQUEST")
        self.assert_no_authority(out)

    def test_22_policy_version_mismatch_is_hold(self):
        r = request(version=2)
        out = evaluate(root(), r, votes(r), **checks())
        self.assertEqual(out.reason, "REQUEST_SCOPE_OR_POLICY_MISMATCH")

    def test_23_policy_hash_mismatch_is_hold(self):
        r = request(policy_digest="e"*64)
        out = evaluate(root(), r, votes(r), **checks())
        self.assertEqual(out.reason, "REQUEST_SCOPE_OR_POLICY_MISMATCH")

    def test_24_malicious_production_repo_switch_rejected(self):
        r = request(repo="attacker/Ario")
        out = evaluate(root(), r, votes(r), **checks())
        self.assertEqual(out.reason, "REQUEST_SCOPE_OR_POLICY_MISMATCH")

    def test_25_foundation_founder_routine_review_only(self):
        p = root("FOUNDATION")
        r = request("FOUNDATION", "routine_change")
        out = evaluate(p, r, votes(r, ("founder",)), **checks())
        self.assertEqual(out.verdict, "ELIGIBLE_FOR_EXTERNAL_REVIEW")
        self.assert_no_authority(out)

    def test_26_foundation_governance_change_not_activated(self):
        p = root("FOUNDATION")
        r = request("FOUNDATION", "governance_change")
        out = evaluate(p, r, votes(r, ("founder", "ario")), **checks())
        self.assertEqual(out.reason, "PHASE_OR_OPERATION_NOT_AUTHORIZED")
        self.assert_no_authority(out)

    def test_27_joint_routine_can_receive_either_role_with_evidence(self):
        r = request(action="routine_change")
        for who in ("founder", "ario"):
            with self.subTest(who=who):
                out = evaluate(root(), r, votes(r, (who,)), **checks())
                self.assertEqual(out.verdict, "ELIGIBLE_FOR_EXTERNAL_REVIEW")
                self.assert_no_authority(out)

    def test_28_joint_delegation_precommit_needs_both(self):
        r = request(action="delegation_precommit")
        one = evaluate(root(), r, votes(r, ("founder",)), **checks())
        both = evaluate(root(), r, votes(r), **checks())
        self.assertEqual(one.reason, "JOINT_TWO_DISTINCT_ROLES_REQUIRED")
        self.assertEqual(both.verdict, "ELIGIBLE_FOR_EXTERNAL_REVIEW")
        self.assert_no_authority(both)

    def test_29_delegation_activate_always_hold_even_with_both(self):
        r = request(action="delegation_activate")
        out = evaluate(root(), r, votes(r), **checks())
        self.assertEqual(out.reason, "PHASE_OR_OPERATION_NOT_AUTHORIZED")
        self.assert_no_authority(out)

    def test_30_key_rotation_never_enabled_by_mock_signatures(self):
        r = request(action="key_rotation")
        out = evaluate(root(), r, votes(r), **checks())
        self.assertEqual(out.reason, "PHASE_OR_OPERATION_NOT_AUTHORIZED")
        self.assert_no_authority(out)

    def test_31_ario_continuity_has_no_perpetual_founder_veto_for_routine(self):
        p = root("ARIO_CONTINUITY")
        r = request("ARIO_CONTINUITY", "routine_change")
        out = evaluate(p, r, votes(r, ("ario",)), **checks())
        self.assertEqual(out.verdict, "ELIGIBLE_FOR_EXTERNAL_REVIEW")
        self.assert_no_authority(out)

    def test_32_ario_continuity_blocks_founder_routine_vote(self):
        p = root("ARIO_CONTINUITY")
        r = request("ARIO_CONTINUITY", "routine_change")
        out = evaluate(p, r, votes(r, ("founder",)), **checks())
        self.assertEqual(out.reason, "ROLE_NOT_ALLOWED_FOR_THIS_PHASE")
        self.assert_no_authority(out)

    def test_33_ario_continuity_structural_requires_future_independent_gate(self):
        p = root("ARIO_CONTINUITY")
        r = request("ARIO_CONTINUITY", "governance_change")
        out = evaluate(p, r, votes(r, ("ario",)), **checks())
        self.assertEqual(out.reason, "PHASE_OR_OPERATION_NOT_AUTHORIZED")
        self.assert_no_authority(out)

    def test_34_any_one_valid_signature_can_request_pause_only(self):
        for who in ("founder", "ario"):
            r = request(action="emergency_pause", evidence_result="UNKNOWN")
            out = evaluate(root(), r, votes(r, (who,)),
                           verify_signature=verifier)
            self.assertEqual(out.verdict, "PAUSE_REQUEST_FOR_EXTERNAL_REVIEW")
            self.assert_no_authority(out)

    def test_35_pause_without_signer_is_hold(self):
        r = request(action="emergency_pause")
        out = evaluate(root(), r, (), verify_signature=verifier)
        self.assertEqual(out.reason, "PAUSE_REQUIRES_ONE_VALID_SIGNATURE")
        self.assert_no_authority(out)

    def test_36_pause_with_two_signers_is_hold_in_this_contract(self):
        r = request(action="emergency_pause")
        out = evaluate(root(), r, votes(r), verify_signature=verifier)
        self.assertEqual(out.reason, "PAUSE_REQUIRES_ONE_VALID_SIGNATURE")
        self.assert_no_authority(out)

    def test_37_boolean_as_version_not_accepted(self):
        r = request(version=True)
        out = evaluate(root(), r, votes(r), **checks())
        self.assertEqual(out.reason, "REQUEST_SCOPE_OR_POLICY_MISMATCH")
        self.assert_no_authority(out)

    def test_38_truthy_verifier_non_bool_not_accepted(self):
        r = request()
        out = evaluate(root(), r, votes(r), **checks(
            verify_evidence=lambda req: 1
        ))
        self.assertEqual(out.reason, "EVIDENCE_UNKNOWN_OR_FAILED")
        self.assert_no_authority(out)

    def test_39_lost_ario_key_requires_hold_not_founder_override(self):
        r = request()
        out = evaluate(root(), r, votes(r, ("founder",)), **checks())
        self.assertEqual(out.reason, "JOINT_TWO_DISTINCT_ROLES_REQUIRED")
        self.assert_no_authority(out)

    def test_40_no_callback_or_votes_never_approve(self):
        r = request()
        out = evaluate(root(), r, ())
        self.assertEqual(out.reason, "NO_INDEPENDENT_SIGNATURE_VERIFIER")
        self.assert_no_authority(out)

    def test_41_attacker_cannot_construct_decision_with_publish_true(self):
        with self.assertRaises(ValueError):
            Decision("FAKE_ALLOW", "fake", can_publish=True)

    def test_42_mocked_all_pass_cannot_construct_live_transfer(self):
        r = request(action="delegation_precommit")
        out = evaluate(root(), r, votes(r), **checks())
        self.assertTrue(out.eligible_for_external_review)
        self.assertFalse(out.delegation_activated)
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
