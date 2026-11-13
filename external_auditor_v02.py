"""R1b independent-of-PR runner: READ ONLY, RESEARCH/HOLD, NOT A CHECK PRODUCER.

This Python program is stored outside the untrusted GitHub PR repository on an
authorized workstation. It never imports, checks out or executes PR-supplied code.
It reads public GitHub REST data over HTTPS. There is NO separate authenticated
GitHub App, check publication, review-deletion ledger or merge authority.
"""
import hashlib
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE = "https://api.github.com"
REPO = "SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a"
PR_NUMBER = 9
PINNED_PR_HEAD = "d9c889ec3d14f2b3de1317ed2d70d70dca00b328"
PINNED_BASE = "be7c16d964872f88ddb9029f2677c49a7cd745ba"
EXPECTED_BLOBS = {
    "trusted_gate_v0/verifier.py": "7b640da2ed5e2699a8001cc1ea2e0b9622ca9c46",
    "trusted_gate_v0/tests/test_adversarial.py": "815674fed45226c74ed7580b6d3c6163ee8ddbc4",
    "trusted_gate_v0/README.md": "059899a3da814991e75749f9b96376b2ad776897",
}
EXPECTED_PRODUCER = None  # NO authenticated external check publisher is installed.


def get_json(path):
    request = urllib.request.Request(
        BASE + path,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Ario-R1b-off-PR-audit/0.1",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=18) as response:
        return json.load(response)


def inspect():
    evidence = {
        "source": "workstation-outside-PR",
        "repo": REPO,
        "pr": PR_NUMBER,
        "expected_head": PINNED_PR_HEAD,
        "expected_base": PINNED_BASE,
        "access": "GitHub-public-REST-read-only-HTTPS",
        "check_producer": "NOT_INSTALLED",
        "no_pr_code_executed": True,
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "checks": {},
    }
    failures = []

    def check(key, good, detail=None):
        evidence["checks"][key] = {"ok": bool(good)}
        if detail is not None:
            evidence["checks"][key]["detail"] = detail
        if not good:
            failures.append(key)

    try:
        pr_before = get_json(f"/repos/{REPO}/pulls/{PR_NUMBER}")
        head = pr_before.get("head") or {}
        base = pr_before.get("base") or {}
        check("exact_pr_head", head.get("sha") == PINNED_PR_HEAD, head.get("sha"))
        check("exact_pr_base", base.get("sha") == PINNED_BASE, base.get("sha"))
        check("pr_is_open", pr_before.get("state") == "open", pr_before.get("state"))
        check("pr_is_not_draft", pr_before.get("draft") is False, pr_before.get("draft"))
        check("head_from_expected_repo",
              (head.get("repo") or {}).get("full_name") == REPO)
        tree = get_json(f"/repos/{REPO}/git/trees/{PINNED_PR_HEAD}?recursive=1")
        files = {x["path"]: x["sha"] for x in tree.get("tree", [])
                 if x.get("type") == "blob"}
        check("source_tree_complete", tree.get("truncated") is False)
        for path, digest in EXPECTED_BLOBS.items():
            check("archived_blob:" + path, files.get(path) == digest,
                  {"expected": digest, "observed": files.get(path)})
        all_paths = get_json(f"/repos/{REPO}/pulls/{PR_NUMBER}/files?per_page=100")
        names = sorted(x.get("filename") for x in all_paths)
        check("no_unexpected_PR_paths",
              bool(names) and all(p == "experiments/r1b/README.md"
                                  or p in EXPECTED_BLOBS for p in names),
              names)
        pr_after = get_json(f"/repos/{REPO}/pulls/{PR_NUMBER}")
        check("fresh_state_unchanged",
              (pr_before.get("head", {}).get("sha"),
               pr_before.get("base", {}).get("sha"),
               pr_before.get("state"),
               pr_before.get("draft")) ==
              (pr_after.get("head", {}).get("sha"),
               pr_after.get("base", {}).get("sha"),
               pr_after.get("state"),
               pr_after.get("draft")))
    except Exception as exc:
        check("readback_error", False, type(exc).__name__ + ": " + str(exc)[:200])

    # This fails closed regardless of what a PR-controlled check claims.
    # Even if the PR becomes non-draft, a real independent authenticated
    # check producer and publication are required for any enforcement claim.
    check("separate_authenticated_producer", EXPECTED_PRODUCER is not None)
    evidence["verdict"] = "HOLD"
    evidence["failed_controls"] = failures
    evidence["interpretation"] = (
        "External read-only live audit; not an independently authenticated "
        "CI check, GitHub merge gate, or owner authorization."
    )
    code = pathlib.Path(__file__).read_bytes()
    evidence["executor_source_sha256"] = hashlib.sha256(code).hexdigest()
    return evidence


def main():
    if len(sys.argv) > 1:
        raise SystemExit("No arguments permitted; pinned read-only research audit")
    result = inspect()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if result["verdict"] == "HOLD" else 0


if __name__ == "__main__":
    sys.exit(main())
