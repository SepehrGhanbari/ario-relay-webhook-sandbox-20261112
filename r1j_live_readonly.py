"""R1j live *read-only* replay of R1i stale-success observation.

Uses only public GitHub API GET requests and the R1j safe reconciliation
implementation. NO Check POST, GitHub token, signer, or ruleset mutation.
The historical A has a real App success; current disposable PR #14 is HEAD B,
so the expected verdict is STALE_PR_HOLD and never new-post authorization.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import urllib.request

from r1j_reconcile import APP_ID, CHECK_NAME, REPO, Intent, reconcile

A = "508a6abfacf534fa01a4b97210c35b35ca965c86"
B = "1c55dad097fc5544c8b36bc02ebb6eeb74c8a6e8"
BASE = "be7c16d964872f88ddb9029f2677c49a7cd745ba"
CHECK_ID = 132094820201
EXT = "R1I-LAB-ONLY:PR14:" + A + ":RUN43484108692"


def api(method, path):
    if method != "GET" or not path.startswith("/repos/" + REPO + "/"):
        raise RuntimeError("R1J_READONLY_API_SCOPE_VIOLATION")
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers={"User-Agent": "Ario-R1j-ReadOnly-Historical-Replay",
                 "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def main():
    direct = api("GET", f"/repos/{REPO}/check-runs/{CHECK_ID}")
    if not (direct.get("id") == CHECK_ID and direct.get("name") == CHECK_NAME and
            direct.get("external_id") == EXT and direct.get("head_sha") == A and
            direct.get("conclusion") == "success" and direct.get("status") == "completed" and
            (direct.get("app") or {}).get("id") == APP_ID):
        raise RuntimeError("R1I_HISTORIC_APP_SUCCESS_MISMATCH")

    pr = api("GET", f"/repos/{REPO}/pulls/14")
    if not (pr.get("draft") is True and pr.get("merged") is False and
            pr["head"]["sha"] == B and pr["base"]["sha"] == BASE):
        raise RuntimeError("HISTORICAL_DISPOSABLE_PR_NOT_IN_EXPECTED_HOLD")
    latest_checks = api("GET", f"/repos/{REPO}/commits/{B}/check-runs?filter=all&per_page=100")
    if any(c.get("name") == CHECK_NAME and (c.get("app") or {}).get("id") == APP_ID
           for c in latest_checks.get("check_runs", [])):
        raise RuntimeError("TRUSTED_APP_CHECK_UNEXPECTED_ON_NEW_SHA")
    expected = Intent(
        repo=REPO, pr_number=14, head_sha=A, base_sha=BASE,
        name=CHECK_NAME, app_id=APP_ID, external_id=EXT,
        conclusion="success", returned_check_id=CHECK_ID
    )
    decision = reconcile(api, expected, observations=1)
    if (decision.get("verdict") != "STALE_PR_HOLD" or
            decision.get("repeat_post_allowed") is not False or
            decision.get("published") is not None):
        raise RuntimeError("FAIL_CLOSED_REAL_REPLAY_MISMATCH")

    report = {
        "schema": "r1j-live-readonly-replay-v1",
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "target_repo": REPO, "pr": 14, "head_A": A, "head_B": B, "base": BASE,
        "historic_check_id": CHECK_ID, "historic_check_app": APP_ID,
        "historic_check_conclusion": "success",
        "new_head_trusted_check_present": False,
        "reconciler_verdict": decision["verdict"],
        "no_repost_allowed": True, "published_new_check": False,
        "permissions_used": "PUBLIC_GITHUB_GET_ONLY",
        "production_governance_trust": "NO_GO",
        "note": "This validates stale-head HOLD only, not new-post unknown-outcome recovery."
    }
    Path("r1j-evidence").mkdir(exist_ok=True)
    Path("r1j-evidence/readonly-replay.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
