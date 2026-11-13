"""R1k - safe read-only recovery of a possibly incomplete R1j post intent.

Pure filesystem research-only prototype: NO GitHub POST, no credential access,
no deletion/unlink/truncation/repair. All outcomes disallow automatic re-POST.
Neither process-local O_EXCL nor a single-workstation journal proves distributed
single-writer custody or durability across power loss / storage-controller caches.
"""
from __future__ import annotations

import json
from pathlib import Path
import stat
from typing import Any

from r1j_reconcile import Intent, validate_intent, EvidenceError

MAX_JOURNAL_BYTES = 16_384
EXPECTED_FIELDS = {
    "schema", "safety_state", "repo", "pr_number", "head_sha", "base_sha",
    "app_id", "check_name", "external_id", "no_repost"
}


def verdict(status: str, reason: str) -> dict[str, Any]:
    return {
        "verdict": status,
        "reason": reason,
        "automatic_post_allowed": False,
        "repeat_post_allowed": False,
        "record_deleted": False,
        "production_trust": "NO_GO",
    }


def recover_existing_intent(path: Path, expected: Intent) -> dict[str, Any]:
    """Safe restart behavior even for absent/empty/partially written journal.

    Important: absent journal does NOT prove that some other host did not POST.
    This function never confers write authorization, even on a valid record.
    """
    try:
        validate_intent(expected)
    except EvidenceError:
        return verdict("HOLD", "INVALID_INTENT")
    try:
        st = path.lstat()
    except FileNotFoundError:
        return verdict("UNKNOWN_HOLD", "NO_JOURNAL_CANNOT_PROVE_NO_POST")
    except OSError:
        return verdict("UNKNOWN_HOLD", "JOURNAL_STAT_UNAVAILABLE")

    if not stat.S_ISREG(st.st_mode):
        return verdict("CONFLICT_HOLD", "JOURNAL_NOT_REGULAR_FILE")
    if st.st_nlink != 1:
        return verdict("CONFLICT_HOLD", "JOURNAL_HAS_MULTIPLE_LINKS")
    if st.st_size <= 0 or st.st_size > MAX_JOURNAL_BYTES:
        return verdict("UNKNOWN_HOLD", "JOURNAL_EMPTY_OR_OVERSIZED")

    try:
        with path.open("rb") as fd:
            payload = fd.read(MAX_JOURNAL_BYTES + 1)
        if len(payload) > MAX_JOURNAL_BYTES:
            return verdict("UNKNOWN_HOLD", "JOURNAL_OVERSIZED")
        value = json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return verdict("UNKNOWN_HOLD", "JOURNAL_TORN_OR_UNREADABLE")
    if type(value) is not dict or set(value) != EXPECTED_FIELDS:
        return verdict("CONFLICT_HOLD", "JOURNAL_SCHEMA_MISMATCH")

    desired = {
        "schema": "r1j-post-intent-v1",
        "safety_state": "POST_MAY_HAVE_OCCURRED_NEVER_BLINDLY_RESEND",
        "repo": expected.repo,
        "pr_number": expected.pr_number,
        "head_sha": expected.head_sha,
        "base_sha": expected.base_sha,
        "app_id": expected.app_id,
        "check_name": expected.name,
        "external_id": expected.external_id,
        "no_repost": True,
    }
    for field, expected_value in desired.items():
        if type(value[field]) is not type(expected_value) or value[field] != expected_value:
            return verdict("CONFLICT_HOLD", "JOURNAL_IDENTITY_MISMATCH:" + field)
    return verdict("RECOVERED_POST_OUTCOME_UNKNOWN_HOLD",
                   "EXCLUSIVE_INTENT_EXISTS_MUST_RECONCILE_READ_ONLY")
