"""R1k disposable subprocess crash/concurrency fixture — LOCAL FILE ONLY.

This process never imports GitHub API helpers, creates a Check or uses any key.
It creates a claim marker and then terminates in controlled modes to model
process failure. It is a research tool, never deploy as a credentialed worker.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import time

from r1j_reconcile import APP_ID, CHECK_NAME, REPO, Intent, EvidenceError, exclusive_post_intent

HEAD = "508a6abfacf534fa01a4b97210c35b35ca965c86"
BASE = "be7c16d964872f88ddb9029f2677c49a7cd745ba"
EXT = "R1I-LAB-ONLY:PR14:" + HEAD + ":RUN43484108692"


def fixed_intent() -> Intent:
    return Intent(repo=REPO, pr_number=14, head_sha=HEAD, base_sha=BASE,
                  name=CHECK_NAME, app_id=APP_ID, external_id=EXT,
                  conclusion="success")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    ap.add_argument("--mode", choices=("normal", "die_after_claim", "die_mid_write"),
                    default="normal")
    ap.add_argument("--barrier", default=None)
    args = ap.parse_args()
    path = Path(args.path)
    if args.barrier:
        deadline = time.monotonic() + 12
        while not Path(args.barrier).exists():
            if time.monotonic() >= deadline:
                print("BARRIER_TIMEOUT", flush=True)
                return 27
            time.sleep(0.005)

    if args.mode == "die_mid_write":
        # Artificial fault exactly after the exclusive create. No POST is possible.
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            print("JOURNAL_EXISTS_NO_REPOST", flush=True)
            return 20
        # A partial record survives as a tombstone. Exit is intentionally
        # unclean without finally closing the OS descriptor or flushing.
        os.write(fd, b'{"schema":"r1j-post-intent-v1","safety_state":')
        os._exit(74)

    try:
        exclusive_post_intent(path, fixed_intent())
    except EvidenceError as exc:
        if str(exc) == "JOURNAL_EXISTS_NO_REPOST":
            print("JOURNAL_EXISTS_NO_REPOST", flush=True)
            return 20
        print("HOLD:" + str(exc), flush=True)
        return 21
    if args.mode == "die_after_claim":
        os._exit(73)
    print("CLAIMED_NO_POST", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
