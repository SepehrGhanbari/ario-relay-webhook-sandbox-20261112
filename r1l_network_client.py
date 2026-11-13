"""R1l external disposable client: one network attempt, never Check POST.

Supports only lab coordinator /reserve and GET /status; no credentials and no
GitHub APIs. Network timeout/reply loss is UNKNOWN_HOLD, not a resend request.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from r1l_atomic_coordinator import fixed_intent, answer


def call_once(base_url: str, intent: dict | None = None, timeout: float = 1.5) -> dict:
    if not (base_url.startswith("http://127.0.0.1:") or
            base_url.startswith("http://localhost:")):
        return answer("HOLD", "NON_LOOPBACK_SERVICE_FORBIDDEN")
    path = "/reserve" if intent is not None else "/status"
    body = json.dumps(intent, sort_keys=True).encode("utf-8") if intent is not None else None
    request = Request(base_url + path, data=body,
                      headers={"Content-Type": "application/json"},
                      method="POST" if intent is not None else "GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            out = json.load(response)
    except HTTPError as err:
        try:
            out = json.loads(err.read(4096))
        except (ValueError, OSError):
            return answer("UNKNOWN_HOLD", "HTTP_ERROR_NO_TRUSTED_BODY")
    except (OSError, URLError, ValueError, TimeoutError):
        return answer("UNKNOWN_HOLD", "NETWORK_REPLY_OR_SERVICE_UNAVAILABLE")
    if type(out) is not dict or out.get("can_publish") is not False or \
            out.get("repeat_post_allowed") is not False or \
            out.get("github_check_emitted") is not False:
        return answer("UNKNOWN_HOLD", "RESPONSE_UNTRUSTED")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--evidence", default="a" * 64)
    ap.add_argument("--barrier", default=None)
    ap.add_argument("--status-only", action="store_true")
    args = ap.parse_args()
    if args.barrier:
        deadline = time.monotonic() + 12
        while not Path(args.barrier).exists():
            if time.monotonic() >= deadline:
                print(json.dumps(answer("UNKNOWN_HOLD", "BARRIER_NOT_RELEASED")))
                return 0
            time.sleep(0.004)
    result = call_once(args.url, None if args.status_only else fixed_intent(args.evidence))
    print(json.dumps(result, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
