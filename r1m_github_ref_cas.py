"""R1m disposable cross-runner CAS probe via GitHub's CREATE git reference API.

REAL independent GitHub-hosted Windows and Linux jobs coordinate through ONE
GitHub repository git-ref namespace, never through their local files.

This is a research experiment, NOT a production distributed lock, independent
key custodian, trusted attestation, or Check publisher.

The only permitted writes create append-only test tags in a named DISPOSABLE
repo. No delete, ref update, App Check POST, GitHub key handling, or production
repo API path is implemented. GITHUB_TOKEN is confined to the sandbox job but
still has repository-wide Contents:write scope during the workflow.

The response-loss phase intentionally discards an HTTP POST result in one
runner: application fault injection, not a claim of real network packet loss.
No POST is retried after an ambiguous response.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request

REPO = "SepehrGhanbari/ario-relay-webhook-sandbox-20261112"
BRANCH = "experiment/r1m-independent-hosts-github-ref-cas-20261113"
API = "https://api.github.com"
ROLES = ("linux", "windows")
PHASES = ("baseline", "lostreply")
READY_BUDGET = 100  # ~100 seconds, GETs only
READ_BUDGET = 8     # bounded GET polling after a write


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError("R1M_HOLD:" + reason)


def clean_num(value: str) -> bool:
    return type(value) is str and re.fullmatch(r"[1-9][0-9]{0,14}", value) is not None


def verify_environment(env: dict) -> dict:
    """Do not accept an event/ref/repository outside the bounded lab scope."""
    require(env.get("GITHUB_REPOSITORY") == REPO, "REPO_SCOPE")
    require(env.get("GITHUB_REF") == "refs/heads/" + BRANCH, "BRANCH_SCOPE")
    require(env.get("GITHUB_EVENT_NAME") == "push", "EVENT_SCOPE")
    require(env.get("R1M_ROLE") in ROLES, "ROLE_SCOPE")
    require(clean_num(env.get("GITHUB_RUN_ID", "")), "RUN_ID")
    require(clean_num(env.get("GITHUB_RUN_ATTEMPT", "")), "RUN_ATTEMPT")
    sha = env.get("GITHUB_SHA")
    require(type(sha) is str and
            re.fullmatch(r"[a-f0-9]{40}", sha) is not None, "INVALID_COMMIT_SHA")
    require(type(env.get("R1M_GITHUB_TOKEN")) is str and
            len(env["R1M_GITHUB_TOKEN"]) >= 20, "NO_LAB_TOKEN")
    require(type(env.get("GITHUB_OUTPUT")) is str and
            len(env["GITHUB_OUTPUT"]) > 0, "NO_GITHUB_OUTPUT")
    return {
        "role": env["R1M_ROLE"], "run_id": env["GITHUB_RUN_ID"],
        "run_attempt": env["GITHUB_RUN_ATTEMPT"], "sha": sha,
    }


def ref_name(settings: dict, phase: str, kind: str, role: str | None = None) -> str:
    """All refs are namespaced by a job run and source SHA in the sandbox."""
    require(phase in PHASES and kind in ("ready", "claim"), "REF_KIND")
    if kind == "ready":
        require(role in ROLES, "READY_ROLE")
    else:
        require(role is None, "CLAIM_NO_ROLE_SUFFIX")
    suffix = "-ready-" + role if kind == "ready" else "-claim"
    return ("r1m-lab-" + settings["run_id"] + "-a" +
            settings["run_attempt"] + "-" + settings["sha"][:12] + "-" +
            phase + suffix)


def call(method: str, resource: str, token: str, data: dict | None = None):
    """Only the fixed sandbox Git refs endpoints are reachable through this API."""
    require(resource == f"/repos/{REPO}/git/refs" or
            resource.startswith(f"/repos/{REPO}/git/ref/tags/r1m-lab-"),
            "UNSAFE_ENDPOINT")
    require(method in ("POST", "GET"), "UNSAFE_METHOD")
    require((method == "POST") == (resource == f"/repos/{REPO}/git/refs"),
            "UNEXPECTED_METHOD_FOR_ENDPOINT")
    if method == "POST":
        require(type(data) is dict and set(data) == {"ref", "sha"} and
                type(data["ref"]) is str and
                data["ref"].startswith("refs/tags/r1m-lab-") and
                re.fullmatch(r"[a-f0-9]{40}", data["sha"]) is not None,
                "POST_DATA_OUT_OF_SCOPE")
    payload = json.dumps(data, separators=(",", ":"), sort_keys=True).encode() if data else None
    req = urllib.request.Request(
        API + resource, data=payload, method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Ario-R1m-Disposable-Independent-Host-CAS-20261113",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json"
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=14) as response:
            return response.status, json.loads(response.read(40_000))
    except urllib.error.HTTPError as exc:
        # Don't echo response body or any header. For a 422, independent GET
        # must confirm a matching ref; validation failure alone proves nothing.
        return exc.code, {}
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return None, {}


def read_existing(ref: str, sha: str, token: str, attempts: int = READ_BUDGET) -> bool:
    """Only conclude the target ref exists after exact ref+commit SHA readback."""
    path = f"/repos/{REPO}/git/ref/tags/" + ref
    for i in range(attempts):
        status, value = call("GET", path, token)
        if status == 200:
            require(type(value) is dict and
                    value.get("ref") == "refs/tags/" + ref and
                    (value.get("object") or {}).get("sha") == sha and
                    (value.get("object") or {}).get("type") == "commit",
                    "REMOTE_REF_IDENTITY_CONFLICT")
            return True
        if status != 404:
            raise RuntimeError("R1M_HOLD:REF_READ_UNKNOWN_" + str(status))
        if i < attempts - 1:
            time.sleep(0.45)
    return False


def create_ref(ref: str, sha: str, token: str):
    return call("POST", f"/repos/{REPO}/git/refs", token,
                {"ref": "refs/tags/" + ref, "sha": sha})


def ready_phase(settings: dict, phase: str, token: str) -> None:
    mine = ref_name(settings, phase, "ready", settings["role"])
    other = ref_name(settings, phase, "ready",
                     "windows" if settings["role"] == "linux" else "linux")
    status, data = create_ref(mine, settings["sha"], token)
    require(status == 201, "READY_REF_POST_NOT_201_" + str(status))
    require((data.get("object") or {}).get("sha") == settings["sha"] and
            data.get("ref") == "refs/tags/" + mine, "READY_REF_POST_MISMATCH")
    require(read_existing(mine, settings["sha"], token), "OWN_READY_REF_NOT_VISIBLE")

    for i in range(READY_BUDGET):
        if read_existing(other, settings["sha"], token, attempts=1):
            return
        time.sleep(1.0)
    raise RuntimeError("R1M_HOLD:OTHER_RUNNER_NEVER_BECAME_READY")


def attempt_phase(settings: dict, phase: str, token: str) -> dict:
    """Exactly ONE POST of this phase claim by this runner; never retry POST."""
    claim = ref_name(settings, phase, "claim")
    drop_response = phase == "lostreply" and settings["role"] == "linux"
    response_status, response_data = create_ref(claim, settings["sha"], token)
    if drop_response:
        # Simulated application-level disappearance of response, deliberately
        # not a genuine network partition: do NOT inspect returned status/body.
        observed_status = "SIMULATED_RESPONSE_DISCARDED"
        creation_role = "UNKNOWN_FROM_LOCAL_RESPONSE"
        match_found = read_existing(claim, settings["sha"], token)
        require(match_found, "AMBIGUOUS_OUTCOME_NOT_VISIBLE_HOLD")
        verdict = "OBSERVED_AFTER_SIMULATED_LOST_REPLY"
    elif response_status == 201:
        observed_status = "HTTP_201"
        creation_role = "CREATED"
        require((response_data.get("object") or {}).get("sha") == settings["sha"] and
                response_data.get("ref") == "refs/tags/" + claim, "POST_201_BODY_CONFLICT")
        require(read_existing(claim, settings["sha"], token), "CREATED_REF_NOT_VISIBLE")
        verdict = "CREATED"
    elif response_status == 422:
        observed_status = "HTTP_422"
        creation_role = "EXISTING_AFTER_CONFLICT"
        require(read_existing(claim, settings["sha"], token),
                "POST_422_WITHOUT_MATCHING_EXISTING_REF")
        verdict = "EXISTING_AFTER_422"
    else:
        # Even if a POST may have taken effect, refuse to infer no action,
        # and do not resend. A read-only GET could be used as separate triage.
        observed_status = "HTTP_UNKNOWN_" + str(response_status)
        creation_role = "UNKNOWN_HOLD"
        raise RuntimeError("R1M_HOLD:AMBIGUOUS_POST_OUTCOME_" + observed_status)
    return {
        "phase": phase, "claim_ref": "refs/tags/" + claim,
        "post_response_observed": observed_status, "outcome": verdict,
        "local_create_observed": creation_role,
        "remote_exact_sha_readback": True,
        "repost_attempted": False, "check_post_attempted": False,
        "can_publish": False, "production_trust": "NO_GO",
    }


def emit_outputs(path: Path, result: dict) -> None:
    require(path.exists(), "RUNNER_OUTPUT_FILE_MISSING")
    with path.open("a", encoding="utf-8") as out:
        out.write("baseline_result=" + result["baseline"]["outcome"] + "\n")
        out.write("lostreply_result=" + result["lostreply"]["outcome"] + "\n")


def main():
    settings = verify_environment(os.environ)
    token = os.environ["R1M_GITHUB_TOKEN"]
    results = {}
    for phase in PHASES:
        ready_phase(settings, phase, token)
        results[phase] = attempt_phase(settings, phase, token)

    report = {
        "schema": "r1m-two-independent-runners-shared-github-ref-v1",
        "runner_role": settings["role"],
        "github_runner_os": os.environ.get("RUNNER_OS", "UNKNOWN"),
        "github_runner_name": os.environ.get("RUNNER_NAME", "UNKNOWN"),
        "run_id": settings["run_id"], "run_attempt": settings["run_attempt"],
        "source_head_sha": settings["sha"], "target_repo": REPO,
        "results": results, "no_check_published": True,
        "no_production_repo_access": True, "independent_credential_custody_proven": False,
        "provider_consensus_internals_proven": False,
        "production_trust": "NO_GO",
    }
    folder = Path("r1m-evidence")
    folder.mkdir(exist_ok=True)
    (folder / (settings["role"] + ".json")).write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    emit_outputs(Path(os.environ["GITHUB_OUTPUT"]), results)
    print("R1M_HOST_ROLE=" + settings["role"])
    print("R1M_BASELINE_RESULT=" + results["baseline"]["outcome"])
    print("R1M_LOSTREPLY_RESULT=" + results["lostreply"]["outcome"])
    print("R1M_NO_CHECK_POST=1")
    print("R1M_PRODUCTION_TRUST=NO_GO")


if __name__ == "__main__":
    main()
