"""R1j: fail-closed GitHub Check POST-outcome reconciliation (OFFLINE LAB).

This is NOT an active publisher or independent security approval. A Check create
POST may succeed before the caller receives a response. No "retry POST" API is
provided here. Read-only reconciliation never equates a missing first list
response with a failed publish and never returns a new-POST authorization.

GitHub's check-run external_id is an external reference, NOT a server-enforced
unique idempotency key. We require an exclusive local intent journal to avoid
accidental replays and then inspect the *actual* GitHub App, SHA, ID, conclusion,
external ID and current PR. Search pagination uses filter=all, not latest.

All network activity is injected through caller in unit tests; no credentials,
imports from PR-controlled code, or GitHub writes are included.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Callable
from urllib.parse import quote

REPO = "SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a"
APP_ID = 5747504
CHECK_NAME = "ario-r1d-lab-app-gate"
MAX_PAGES = 5  # fail closed rather than assume exhaustive scan beyond 500
MAX_OBSERVATIONS = 4


class EvidenceError(Exception):
    """Malformed or incomplete API response; do not conclude publication failed."""


@dataclass(frozen=True)
class Intent:
    repo: str
    pr_number: int
    head_sha: str
    base_sha: str
    name: str
    app_id: int
    external_id: str
    conclusion: str
    returned_check_id: int | None = None


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise EvidenceError(reason)


def validate_intent(i: Intent) -> None:
    require(i.repo == REPO, "REPO_OUT_OF_SCOPE")
    require(type(i.pr_number) is int and i.pr_number >= 1, "PR_NUMBER")
    require(type(i.head_sha) is str and re.fullmatch(r"[0-9a-f]{40}", i.head_sha) is not None,
            "HEAD_FORMAT")
    require(type(i.base_sha) is str and re.fullmatch(r"[0-9a-f]{40}", i.base_sha) is not None,
            "BASE_FORMAT")
    require(i.name == CHECK_NAME and type(i.app_id) is int and i.app_id == APP_ID,
            "APP_OR_NAME")
    require(i.conclusion == "success", "NON_POSITIVE_CONTROL")
    require(type(i.external_id) is str and
            re.fullmatch(r"R1I-LAB-ONLY:PR14:[0-9a-f]{40}:RUN[0-9]+", i.external_id)
            is not None and
            i.external_id.split(":")[2] == i.head_sha and i.pr_number == 14,
            "EXTERNAL_ID_NOT_BOUND")
    require(i.returned_check_id is None or
            (type(i.returned_check_id) is int and i.returned_check_id > 0),
            "INVALID_CHECK_ID")


def exclusive_post_intent(path: Path, intent: Intent) -> None:
    """Persist a no-repost marker BEFORE any Check POST, never truncate/reuse.

    This demo only writes a local journal. Its file permissions on Windows must
    additionally be protected by OS ACLs before production consideration.
    """
    validate_intent(intent)
    require(path.parent.is_dir(), "JOURNAL_DIRECTORY_MISSING")
    require(not path.is_symlink(), "JOURNAL_SYMLINK")
    data = {
        "schema": "r1j-post-intent-v1",
        "safety_state": "POST_MAY_HAVE_OCCURRED_NEVER_BLINDLY_RESEND",
        "repo": intent.repo,
        "pr_number": intent.pr_number,
        "head_sha": intent.head_sha,
        "base_sha": intent.base_sha,
        "app_id": intent.app_id,
        "check_name": intent.name,
        "external_id": intent.external_id,
        "no_repost": True
    }
    payload = (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode()
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise EvidenceError("JOURNAL_EXISTS_NO_REPOST") from None
    with os.fdopen(fd, "wb") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())


def validate_current_pr(pr: object, intent: Intent) -> None:
    require(type(pr) is dict, "PR_RESPONSE")
    require(type(pr.get("number")) is int and pr["number"] == intent.pr_number and
            pr.get("state") == "open" and pr.get("merged") is False, "PR_STATE")
    head = pr.get("head") or {}
    base = pr.get("base") or {}
    require(type(head) is dict and type(base) is dict, "PR_REFS")
    require(head.get("sha") == intent.head_sha and base.get("sha") == intent.base_sha,
            "STALE_PR_HEAD_OR_BASE")
    require((head.get("repo") or {}).get("full_name") == REPO and
            (base.get("repo") or {}).get("full_name") == REPO, "PR_REPO")


def candidate_state(run: dict, i: Intent) -> str:
    """Treat a matching external ID from any wrong App/HEAD as CONFLICT."""
    if run.get("external_id") != i.external_id:
        return "UNRELATED"
    if type(run.get("id")) is not int or run["id"] <= 0:
        return "CONFLICT"
    if (run.get("name") != i.name or run.get("head_sha") != i.head_sha or
            run.get("status") != "completed" or run.get("conclusion") != i.conclusion or
            (run.get("app") or {}).get("id") != i.app_id):
        return "CONFLICT"
    if i.returned_check_id is not None and run["id"] != i.returned_check_id:
        return "CONFLICT"
    return "VALID"


def scan_all_matching(caller: Callable, i: Intent) -> tuple[list[dict], bool]:
    candidates = []
    name = quote(i.name, safe="")
    for page in range(1, MAX_PAGES + 1):
        url = (f"/repos/{REPO}/commits/{i.head_sha}/check-runs"
               f"?filter=all&check_name={name}&per_page=100&page={page}")
        response = caller("GET", url)
        require(type(response) is dict and
                type(response.get("total_count")) is int and response["total_count"] >= 0 and
                type(response.get("check_runs")) is list, "CHECK_PAGE_SHAPE")
        count = response["total_count"]
        runs = response["check_runs"]
        require(len(runs) <= 100 and len(runs) <= count, "CHECK_PAGE_COUNT")
        require(all(type(r) is dict for r in runs), "CHECK_RUN_SHAPE")
        candidates.extend([r for r in runs if r.get("external_id") == i.external_id])
        if count <= 100 * page:
            return candidates, True
    return candidates, False


def outcome(state: str, reason: str, check_id: int | None = None) -> dict:
    answer = {
        "verdict": state,
        "reason": reason,
        "repeat_post_allowed": False,
        "production_trust": "NO_GO",
        "published": True if state == "CONFIRMED_EXISTING_CHECK" else None,
    }
    if check_id is not None:
        answer["check_run_id"] = check_id
    return answer


def reconcile(caller: Callable, intent: Intent, observations: int = 3) -> dict:
    """Pure read-only inspection; transient absences/errors never trigger POST.

    An observed, valid Check is evidence that a POST succeeded, not proof of
    independent credential custody or of a safe production governance rule.
    """
    try:
        validate_intent(intent)
    except EvidenceError as exc:
        return outcome("HOLD", str(exc))
    if type(observations) is not int or not (1 <= observations <= MAX_OBSERVATIONS):
        return outcome("HOLD", "OBSERVATION_BUDGET")
    last_unknown = "NO_OBSERVABLE_CHECK"
    for _ in range(observations):
        try:
            pr = caller("GET", f"/repos/{REPO}/pulls/{intent.pr_number}")
            validate_current_pr(pr, intent)
        except EvidenceError as exc:
            if str(exc) == "STALE_PR_HEAD_OR_BASE":
                return outcome("STALE_PR_HOLD", str(exc))
            if str(exc) in ("PR_STATE", "PR_REPO", "PR_REFS"):
                return outcome("CONFLICT_HOLD", str(exc))
            last_unknown = str(exc)
            continue
        except Exception:
            last_unknown = "PR_READ_UNKNOWN"
            continue

        try:
            # If the POST yielded an ID, query that exact resource FIRST; it may
            # become visible before the list-of-checks endpoint catches up.
            direct = None
            if intent.returned_check_id is not None:
                direct = caller("GET", f"/repos/{REPO}/check-runs/{intent.returned_check_id}")
                require(type(direct) is dict, "CHECK_ID_READ_SHAPE")
                state = candidate_state(direct, intent)
                require(state != "CONFLICT" and state != "UNRELATED",
                        "CHECK_ID_CONFLICT")
            found, complete = scan_all_matching(caller, intent)
            if not complete:
                last_unknown = "CHECK_LIST_NOT_EXHAUSTIVE"
                continue
            if len(found) > 1:
                return outcome("CONFLICT_HOLD", "DUPLICATE_EXTERNAL_ID_CHECKS")
            if len(found) == 1:
                c = found[0]
                if candidate_state(c, intent) != "VALID":
                    return outcome("CONFLICT_HOLD", "CHECK_IDENTITY_MISMATCH")
                if direct is not None and c.get("id") != direct.get("id"):
                    return outcome("CONFLICT_HOLD", "CHECK_ID_LIST_CONFLICT")
                # An older Check can be valid even after the PR has moved.
                # Re-read PR immediately before returning confirmation.
                latest_pr = caller("GET", f"/repos/{REPO}/pulls/{intent.pr_number}")
                validate_current_pr(latest_pr, intent)
                return outcome("CONFIRMED_EXISTING_CHECK", "EXACT_APP_SHA_EXTERNAL_ID",
                               c["id"])
            last_unknown = "NO_CHECK_VISIBLE_YET"
        except EvidenceError as exc:
            # A definite contradictory direct check must not silently heal.
            if str(exc) in ("CHECK_ID_CONFLICT",):
                return outcome("CONFLICT_HOLD", str(exc))
            if str(exc) == "STALE_PR_HEAD_OR_BASE":
                return outcome("STALE_PR_HOLD", str(exc))
            if str(exc) in ("PR_STATE", "PR_REPO", "PR_REFS"):
                return outcome("CONFLICT_HOLD", str(exc))
            last_unknown = str(exc)
        except Exception:
            last_unknown = "GITHUB_READ_UNKNOWN"

    return outcome("UNKNOWN_POST_OUTCOME_HOLD", last_unknown)
