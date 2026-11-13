"""R1i SINGLE-SHA LAB SUCCESS CHECK. Never production. Dry-run by default.

This is a NEW isolated positive-control publisher; it does not modify the
original pinned failure-only R1d publisher. It requires an independently hosted
real test, locally verified SHA-pinned artifact, Ed25519-signed workstation
statement, matching archived public record, and exact current PR SHA.
No neutral/skipped path, no generic caller-provided target, no production repo.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
import publisher as r1d

LAB = Path.home() / "Documents" / "Ario_R1d_App_Lab_20261113"
OUT = LAB / "r1i_evidence"
SIGNED_PATH = OUT / "r1i-signed-observation.json"
ZPATH = OUT / "r1i-gh-artifact-14065933238.zip"
SENTINEL = OUT / "r1i-published-lab-success-readback.json"
APP_KEY = Path(os.environ["LOCALAPPDATA"]) / "ArioR1dLabSecrets" / "ario-r1d-check-producer-lab-20261.private-key.pem"
REPO = "SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a"
HOST = "SepehrGhanbari/ario-relay-webhook-sandbox-20261112"
HEAD = "508a6abfacf534fa01a4b97210c35b35ca965c86"
BASE = "be7c16d964872f88ddb9029f2677c49a7cd745ba"
CHECK_NAME = "ario-r1d-lab-app-gate"
EXPECTED_SIGNER_FINGERPRINT = "b4aa27898fa77b977c7ae1d46c7a1274eb5a1aa5858548a70f1355dbd6da2e19"
EVALUATOR_SHA = "370968a225e8764e6160195a85fc1c09a4e15883"
RUN_ID = 43484108692
ARTIFACT_ID = 14065933238
ARTIFACT_HASH = "adcc02cddb4d22c2ae5ff554f5ae8cb6194d385a7cb79a89b311a5fe22053487"
R1D_PUBLISHER_BLOB = "838bbe9bfc87e4f76491ea79b3725ad637f774e5"
PUBLIC_EVIDENCE_COMMIT = "7015d8291dd31ce2422243c3a8ad56490034c6f1"
PUBLIC_EVIDENCE_PATH = "evidence/r1i/2026-11-13/lab-signed-observation.json"


class LabHold(Exception):
    pass


def require(value: bool, reason: str) -> None:
    if not value:
        raise LabHold(reason)


def canonical(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def pr_preflight() -> dict:
    pr = r1d.api("GET", f"/repos/{REPO}/pulls/14")
    require(pr.get("state") == "open" and pr.get("merged") is False and
            pr.get("draft") is True and pr.get("number") == 14, "NOT_DRAFT_EXACT_PR14")
    require((pr.get("head") or {}).get("sha") == HEAD and
            (pr.get("base") or {}).get("sha") == BASE and
            (pr.get("base") or {}).get("ref") ==
            "experiment/r1d-required-app-rule-20261113", "PR_HEAD_OR_BASE_CHANGED")
    require((pr.get("head") or {}).get("repo", {}).get("full_name") == REPO and
            (pr.get("base") or {}).get("repo", {}).get("full_name") == REPO,
            "PR_REPO_CHANGED")
    return pr


def get_expected_rule() -> dict:
    rule = r1d.api("GET", f"/repos/{REPO}/rulesets/27219627")
    rc = [r.get("parameters") for r in rule.get("rules", []) if
          r.get("type") == "required_status_checks"]
    require(rule.get("enforcement") == "active" and
            rule.get("conditions", {}).get("ref_name", {}).get("include") ==
            ["refs/heads/experiment/r1d-required-app-rule-20261113"] and
            len(rc) == 1 and rc[0]["strict_required_status_checks_policy"] is True and
            rc[0]["required_status_checks"] ==
            [{"context": CHECK_NAME, "integration_id": 5747504}],
            "REQUIRED_LAB_RULE_CHANGED")
    # Unauthenticated Ruleset API omits bypass_actors. The operator MUST independently
    # check no-bypass via authenticated GitHub before invoking --publish-lab-success.
    return rule


def verify_public_signed_evidence() -> dict:
    require(SIGNED_PATH.is_file() and ZPATH.is_file(), "LOCAL_PUBLIC_EVIDENCE_MISSING")
    require(not SENTINEL.exists(), "ALREADY_PUBLISHED_NO_REPLAY")
    signed = json.loads(SIGNED_PATH.read_text(encoding="utf-8"))
    public_raw = base64.b64decode(signed["public_key_base64"], validate=True)
    require(sha(public_raw) == EXPECTED_SIGNER_FINGERPRINT ==
            signed.get("public_key_sha256"), "SIGNER_FINGERPRINT_MISMATCH")
    require(signed.get("signature_algorithm") == "Ed25519", "SIGNATURE_ALGORITHM")
    signature = base64.b64decode(signed["signature_base64"], validate=True)
    statement = signed.get("statement")
    require(type(statement) is dict, "SIGNED_STATEMENT_MISSING")
    try:
        Ed25519PublicKey.from_public_bytes(public_raw).verify(signature, canonical(statement))
    except Exception as e:
        raise LabHold("INVALID_DETACHED_ED25519_SIGNATURE") from None
    require(statement.get("schema") == "r1i-lab-operator-attestation-v1" and
            statement.get("scope") == "disposable-only-no-production-governance",
            "STATEMENT_SCOPE")
    require(statement.get("target_repo") == REPO and
            statement.get("pr_number") == 14 and
            statement.get("head_sha") == HEAD and
            statement.get("base_sha") == BASE and
            statement.get("evaluator_commit_sha") == EVALUATOR_SHA and
            statement.get("external_run_id") == RUN_ID and
            statement.get("artifact_id") == ARTIFACT_ID, "STATEMENT_IDENTITY")
    require(statement.get("independent_signer_custody_proven") is False and
            statement.get("production_merge_authorized") is False and
            statement.get("permanent_governance_trust_authorized") is False and
            statement.get("lab_only_check_success_allowed_for_stale_head_test") is True,
            "STATEMENT_SCOPE_FLAGS")
    require(statement.get("test_count") == 1 and
            statement.get("executed_tests_result") == "passed", "STATEMENT_TESTS")
    require(statement.get("artifact_zip_sha256") == ARTIFACT_HASH ==
            sha(ZPATH.read_bytes()), "ARTIFACT_DIGEST")
    with zipfile.ZipFile(ZPATH) as archive:
        require(sorted(archive.namelist()) == ["actual_unittest.log", "receipt.json"],
                "ARTIFACT_FILES")
        log = archive.read("actual_unittest.log")
        raw = archive.read("receipt.json")
    require(sha(log) == statement.get("actual_unit_test_log_sha256") and
            sha(raw) == statement.get("unsigned_receipt_sha256"),
            "LOG_OR_RECEIPT_DIGEST")
    receipt = json.loads(raw)
    require(receipt.get("test_exit_code") == 0 and
            receipt.get("head_sha") == HEAD and
            receipt.get("base_sha") == BASE and
            receipt.get("evaluator_commit_sha") == EVALUATOR_SHA and
            receipt.get("tests") == [{"id": "fixture.reference", "result": "passed", "count": 1}],
            "RAW_TEST_EVIDENCE")
    remote = r1d.api("GET",
        f"/repos/{HOST}/contents/{PUBLIC_EVIDENCE_PATH}?ref={PUBLIC_EVIDENCE_COMMIT}")
    require(remote.get("encoding") == "base64", "PUBLIC_SIGNED_ARCHIVE_MISSING")
    archived = json.loads(base64.b64decode(remote["content"]))
    require(archived == signed, "PUBLIC_RECORD_MISMATCH")
    return statement


def external_run_preflight() -> None:
    run = r1d.api("GET", f"/repos/{HOST}/actions/runs/{RUN_ID}")
    require(run.get("head_sha") == EVALUATOR_SHA and
            run.get("status") == "completed" and run.get("conclusion") == "success",
            "HOSTED_EVALUATOR_RUN_NOT_PASS")
    require(run.get("head_branch") == "experiment/r1i-external-evaluator-20261113" and
            run.get("event") == "push", "HOSTED_RUN_EVENT_NOT_PINNED")
    jobs = r1d.api("GET", f"/repos/{HOST}/actions/runs/{RUN_ID}/jobs")
    observed = [j for j in jobs.get("jobs", []) if
                j.get("name") == "r1i-external-actual-unit-test-not-trust-gate"]
    require(len(observed) == 1 and observed[0].get("conclusion") == "success",
            "HOSTED_RUN_JOB_NOT_PASS")


def verify_no_old_app_success() -> None:
    checks = r1d.api("GET", f"/repos/{REPO}/commits/{HEAD}/check-runs")
    unexpected = [r for r in checks.get("check_runs", []) if
                  r.get("name") == CHECK_NAME and
                  (r.get("app") or {}).get("id") == 5747504]
    require(not unexpected, "EXISTING_TRUSTED_APP_CHECK_DO_NOT_DUPLICATE")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish-lab-success", action="store_true", default=False)
    args = ap.parse_args(argv)

    try:
        raw_source = (LAB / "publisher.py").read_bytes()
        require(git_blob(raw_source) == R1D_PUBLISHER_BLOB, "PINNED_R1D_LIBRARY_CHANGED")
        statement = verify_public_signed_evidence()
        external_run_preflight()
        get_expected_rule()
        pr = pr_preflight()
        verify_no_old_app_success()
        if not args.publish_lab_success:
            print(json.dumps({"phase": "DRY_RUN", "verdict": "REVIEW_READY_ONLY",
                              "published": False, "head": HEAD, "external_run": RUN_ID,
                              "signed_evidence_fingerprint": EXPECTED_SIGNER_FINGERPRINT,
                              "independent_custody_proven": False,
                              "production_trust": "NO_GO"}, sort_keys=True))
            return 0

        require(APP_KEY.is_file() and not APP_KEY.is_symlink(), "LAB_APP_KEY_UNAVAILABLE")
        token = r1d.get_installation_token("5747504", "181664284", str(APP_KEY), r1d.api)
        # Last read before publication: exact HEAD, base and PR metadata.
        newest = pr_preflight()
        require(newest.get("updated_at") == pr.get("updated_at"),
                "PR_METADATA_CHANGED_DURING_EVALUATION")
        get_expected_rule()
        verify_no_old_app_success()

        payload = {
            "name": CHECK_NAME, "head_sha": HEAD,
            "status": "completed", "conclusion": "success",
            "external_id": f"R1I-LAB-ONLY:PR14:{HEAD}:RUN{RUN_ID}",
            "details_url": f"https://github.com/{HOST}/actions/runs/{RUN_ID}",
            "output": {
                "title": "R1i LAB PASS: 1 real pinned external fixture test",
                "summary": (
                    "DISPOSABLE research control ONLY, NOT governance approval. "
                    f"External repo Actions run {RUN_ID}, exact evaluator {EVALUATOR_SHA}, "
                    "one pinned real unittest passed. Public Ed25519 operator-signed "
                    f"evidence: https://github.com/{HOST}/blob/{PUBLIC_EVIDENCE_COMMIT}/"
                    f"{PUBLIC_EVIDENCE_PATH}. Operator controls the lab signer/App; "
                    "independent governance credential custody is NOT proven."
                )
            }
        }
        require(payload["status"] == "completed" and payload["conclusion"] == "success" and
                payload["head_sha"] == HEAD, "UNEXPECTED_PUBLISH_PAYLOAD")
        sent = r1d.api("POST", f"/repos/{REPO}/check-runs", token=token, payload=payload)
        require(sent.get("head_sha") == HEAD and sent.get("name") == CHECK_NAME and
                sent.get("status") == "completed" and sent.get("conclusion") == "success" and
                (sent.get("app") or {}).get("id") == 5747504, "POST_RESPONSE_NOT_EXPECTED")
        check_id = sent.get("id")
        require(type(check_id) is int, "CHECK_ID_MISSING")
        checks = r1d.api("GET", f"/repos/{REPO}/commits/{HEAD}/check-runs")
        matching = [c for c in checks.get("check_runs", []) if c.get("id") == check_id and
                    c.get("name") == CHECK_NAME and c.get("conclusion") == "success" and
                    (c.get("app") or {}).get("id") == 5747504]
        require(len(matching) == 1, "CHECK_RUN_READBACK_MISMATCH")
        receipt = {"scope": "LAB_ONLY", "check_run_id": check_id, "head_sha": HEAD,
                   "app_id": 5747504, "conclusion": "success",
                   "signed_evidence_key_sha256": EXPECTED_SIGNER_FINGERPRINT,
                   "external_run_id": RUN_ID, "production_governance_approved": False}
        SENTINEL.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n",
                            encoding="utf-8")
        print(json.dumps({"phase": "LIVE_LAB_ONLY", "published": True,
                          "check_run_id": check_id, "head_sha": HEAD,
                          "app_id": 5747504, "production_trust": "NO_GO"},
                         sort_keys=True))
        return 0
    except (LabHold, r1d.GateHold, ValueError, KeyError, OSError) as exc:
        reason = str(exc) if isinstance(exc, (LabHold, r1d.GateHold)) else type(exc).__name__
        print(json.dumps({"verdict": "HOLD", "reason": reason, "published": False}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
