"""R1h OFFLINE EVIDENCE CONTRACT — research-only, never a Check publisher.

This policy validates *claimed* test evidence against a separately held policy.
Signature verification must be supplied by an independently controlled verifier.
An acceptable record is only REVIEWABLE, never merge permission or a Check success.
This module has no networking, no key handling, and no GitHub-write capability.
"""
from __future__ import annotations

import json
import re
from typing import Callable


class EvidenceHold(Exception):
    """Refuse evidence lacking the exact pre-registered trust binding."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise EvidenceHold(reason)


def is_sha(value: object, length: int) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{" + str(length) + r"}", value) is not None


def review_receipt(
    *,
    current_pr: dict,
    envelope: dict,
    protected_policy: dict,
    verify_detached: Callable[[str, bytes, str], bool],
) -> dict:
    """Offline, deterministic admission for *review* of alleged positive evidence.

    A real deployment MUST independently protect policy, nonce, evaluator image,
    signature verification, executor, raw test logs and the publisher credential.
    In tests, verify_detached is mocked and therefore proves no real custody.
    """
    try:
        require(type(current_pr) is dict and type(envelope) is dict, "BAD_INPUT")
        require(type(protected_policy) is dict, "UNTRUSTED_POLICY")
        require(callable(verify_detached), "NO_SIGNATURE_VERIFIER")
        require(set(envelope) == {"receipt", "signature"}, "ENVELOPE_SHAPE")
        receipt = envelope["receipt"]
        signature = envelope["signature"]
        require(type(receipt) is dict and type(signature) is dict, "RECEIPT_SHAPE")
        require(set(receipt) == {
            "schema", "repo", "pr_number", "head_sha", "base_sha",
            "base_ref", "nonce", "evaluator_sha", "runner_digest",
            "suite_sha256", "log_sha256", "exit_code", "tests"
        }, "RECEIPT_FIELDS")
        require(set(signature) == {"key_id", "value"}, "SIGNATURE_FIELDS")
        require(receipt["schema"] == "r1h-attestation-v1", "SCHEMA")
        require(type(current_pr.get("number")) is int and
                type(receipt["pr_number"]) is int and
                current_pr["number"] == receipt["pr_number"] ==
                protected_policy.get("pr_number"), "PR_NUMBER")
        require(receipt["repo"] == protected_policy.get("repo") and
                (current_pr.get("base") or {}).get("repo", {}).get("full_name") ==
                protected_policy.get("repo") and
                (current_pr.get("head") or {}).get("repo", {}).get("full_name") ==
                protected_policy.get("repo"), "REPOSITORY")
        require(current_pr.get("state") == "open" and
                current_pr.get("merged") is False and
                current_pr.get("draft") is False, "PR_NOT_READY")
        require(is_sha(receipt["head_sha"], 40) and
                is_sha(receipt["base_sha"], 40) and
                receipt["head_sha"] == (current_pr.get("head") or {}).get("sha") ==
                protected_policy.get("head_sha") and
                receipt["base_sha"] == (current_pr.get("base") or {}).get("sha") ==
                protected_policy.get("base_sha"), "HEAD_BASE_DRIFT")
        require(receipt["base_ref"] == (current_pr.get("base") or {}).get("ref") ==
                protected_policy.get("base_ref"), "BASE_REF")
        require(type(receipt["nonce"]) is str and receipt["nonce"] and
                receipt["nonce"] == protected_policy.get("nonce"), "NONCE")
        require(is_sha(receipt["evaluator_sha"], 40) and
                receipt["evaluator_sha"] == protected_policy.get("evaluator_sha"), "EVALUATOR_PIN")
        require(is_sha(receipt["runner_digest"], 64) and
                receipt["runner_digest"] == protected_policy.get("runner_digest"), "RUNNER_PIN")
        require(is_sha(receipt["suite_sha256"], 64) and
                receipt["suite_sha256"] == protected_policy.get("suite_sha256"), "SUITE_PIN")
        require(is_sha(receipt["log_sha256"], 64), "LOG_DIGEST")
        require(type(receipt["exit_code"]) is int and
                receipt["exit_code"] == 0, "EXIT_NOT_ZERO")
        tests = receipt["tests"]
        required_tests = protected_policy.get("required_tests")
        require(type(tests) is list and len(tests) > 0 and
                type(required_tests) is tuple and len(required_tests) > 0, "NO_TESTS")
        require(all(type(t) is dict and set(t) == {"id", "result"} and
                    type(t["id"]) is str and type(t["result"]) is str for t in tests),
                "TEST_SHAPE")
        ids = [t["id"] for t in tests]
        require(len(ids) == len(set(ids)), "DUPLICATE_TEST_ID")
        require(set(ids) == set(required_tests) and len(ids) == len(required_tests),
                "REQUIRED_TEST_SET")
        require(all(t["result"] == "passed" for t in tests), "TEST_NOT_PASS")
        require(type(signature["key_id"]) is str and
                signature["key_id"] == protected_policy.get("signer_key_id") and
                type(signature["value"]) is str and
                len(signature["value"]) > 0, "SIGNER_ID")
        # No claim or flag from the receipt itself can bypass this check.
        signed_bytes = json.dumps(receipt, sort_keys=True, separators=(",", ":"),
                                  ensure_ascii=False).encode("utf-8")
        require(verify_detached(signature["key_id"], signed_bytes,
                                signature["value"]) is True, "SIGNATURE_NOT_VERIFIED")
        return {"decision": "EVIDENCE_REVIEWABLE", "head_sha": receipt["head_sha"],
                "reason": "SIGNED_CLAIMS_MATCH_PRE_REGISTERED_POLICY",
                "merge_authorized": False, "check_run_published": False}
    except (EvidenceHold, KeyError, ValueError, TypeError, AttributeError) as exc:
        reason = str(exc) if isinstance(exc, EvidenceHold) else "MALFORMED_EVIDENCE"
        return {"decision": "HOLD", "reason": reason,
                "merge_authorized": False, "check_run_published": False}
