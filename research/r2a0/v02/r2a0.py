#!/usr/bin/env python3
"""R2a-0 bounded laboratory evidence tooling (stdlib only, no App secret handling).

No operation may target the production Ario repository.
All remote mutations are disabled by default and restricted to a disposable
repository and an isolated experiment/r2a0-* base branch.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
from datetime import datetime, timezone
from urllib.parse import quote

LAB_REPO = "SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a"
PRODUCTION_REPO = "SepehrGhanbari/Ario"
CHECK_NAME = "ario-r1d-lab-app-gate"
APP_ID = 5747504
BASE_PREFIX = "experiment/r2a0-"
MAX_WEBHOOK = 2 * 1024 * 1024
SHA_RE = re.compile(r"[a-f0-9]{40}\Z")
SCENARIOS = ("Sc1", "Sc2", "Sk", "Sn", "Sc3", "Sc4", "Se1")
STAGES = ("baseline", "major-created", "receiver-stopped", "after-failure", "check-sequence", "late-comment", "thread-open", "thread-resolved", "thread-deleted", "changes-requested", "review-dismissed", "delivery-suppressed", "before-merge", "after-merge", "manual")


def canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def ensure_lab(repo: str) -> None:
    if repo != LAB_REPO:
        raise ValueError(f"Refusing non-allowlisted repository: {repo!r}")


def ensure_scenario(s: str) -> None:
    if s not in SCENARIOS:
        raise ValueError(f"Unknown R2a-0 scenario: {s!r}")


def ensure_sha(sha: str) -> None:
    if not SHA_RE.fullmatch(sha):
        raise ValueError("Expected exactly one full lowercase 40-hex HEAD SHA")


def write_once(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError("SYMLINK_EVIDENCE_PATH")
    with path.open("xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    # Directory durability on POSIX where supported; Windows cannot guarantee power-loss durability.
    if os.name == "posix":
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def strict_json_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError("DUPLICATE_JSON_FIELD")
        result[k] = v
    return result


class EvidenceJournal:
    """Single-logical-writer, fail-closed evidence journal; NOT independent custody.

    A durable per-sequence O_EXCL claim prevents two processes from both
    acknowledging the same slot. Any torn/orphaned claim or payload blocks all
    further appends until a separate, evidence-preserving recovery decision.
    """

    REQUIRED = frozenset({"seq", "received_utc", "event", "source", "meta",
                          "payload_path", "payload_sha256", "prev_hash", "record_hash"})

    def __init__(self, root: Path):
        self.root = root
        self.lock = threading.Lock()
        self.index = root / "journal.jsonl"

    def _safe_root(self) -> None:
        if self.root.is_symlink() or self.index.is_symlink():
            raise ValueError("SYMLINK_EVIDENCE_ROOT_OR_INDEX")
        for sub in ("objects", "claims"):
            if (self.root / sub).is_symlink():
                raise ValueError("SYMLINK_EVIDENCE_SUBDIRECTORY")

    def read(self) -> list[dict]:
        self._safe_root()
        if not self.index.exists():
            for sub in ("objects", "claims"):
                if (self.root / sub).exists() and any((self.root / sub).iterdir()):
                    raise ValueError("ORPHAN_EVIDENCE_WITHOUT_INDEX")
            return []

        original = self.index.read_bytes()
        if original and not original.endswith(b"\n"):
            raise ValueError("TORN_JOURNAL_LINE_NO_NEWLINE")
        records = []
        previous = "0" * 64
        expected_objects: set[str] = set()
        expected_claims: set[str] = set()
        for line_number, line in enumerate(original.splitlines(), 1):
            try:
                record = json.loads(line, object_pairs_hook=strict_json_object)
                if not isinstance(record, dict) or set(record) != self.REQUIRED:
                    raise ValueError("JOURNAL_SCHEMA_MISMATCH")
                advertised = record["record_hash"]
                if not isinstance(advertised, str) or len(advertised) != 64:
                    raise ValueError("INVALID_RECORD_HASH")
                unsigned = {k: v for k, v in record.items() if k != "record_hash"}
                actual = digest(canonical(unsigned))
                if (advertised != actual or record.get("prev_hash") != previous or
                    type(record.get("seq")) is not int or record["seq"] != line_number):
                    raise ValueError("HASH_OR_SEQUENCE_MISMATCH")
                h = record["payload_sha256"]
                if not isinstance(h, str) or not re.fullmatch(r"[a-f0-9]{64}", h):
                    raise ValueError("BAD_PAYLOAD_HASH")
                rel = f"objects/{line_number:06d}-{h}.bin"
                if record["payload_path"] != rel:
                    raise ValueError("UNEXPECTED_PAYLOAD_PATH")
                object_path = self.root / rel
                if object_path.is_symlink() or not object_path.is_file() or digest(object_path.read_bytes()) != h:
                    raise ValueError("MISSING_OR_MODIFIED_PAYLOAD")
                claim_name = f"{line_number:06d}.json"
                claim_path = self.root / "claims" / claim_name
                claim = {"seq": line_number, "prev_hash": previous,
                         "payload_sha256": h, "record_hash": advertised}
                if claim_path.is_symlink() or not claim_path.is_file() or claim_path.read_bytes() != canonical(claim):
                    raise ValueError("MISSING_OR_MODIFIED_CLAIM")
                expected_objects.add(object_path.name)
                expected_claims.add(claim_name)
                records.append(record)
                previous = advertised
            except Exception as e:
                raise ValueError(f"Journal corrupt at line {line_number}: {e}") from e
        for sub, expected in (("objects", expected_objects), ("claims", expected_claims)):
            d = self.root / sub
            actual = {item.name for item in d.iterdir()} if d.exists() else set()
            if actual != expected:
                raise ValueError(f"ORPHAN_OR_MISSING_{sub.upper()}")
        return records

    def append(self, event: str, source: str, data: bytes, meta: dict | None = None) -> dict:
        if len(data) > MAX_WEBHOOK * 4:
            raise ValueError("Evidence payload too large")
        with self.lock:
            prior = self.read()
            seq = len(prior) + 1
            h = digest(data)
            rel = Path("objects") / f"{seq:06d}-{h}.bin"
            previous = prior[-1]["record_hash"] if prior else "0" * 64
            item = {"seq": seq, "received_utc": utc_now(), "event": event,
                    "source": source, "meta": meta or {}, "payload_path": rel.as_posix(),
                    "payload_sha256": h, "prev_hash": previous}
            item["record_hash"] = digest(canonical(item))
            claim = {"seq": seq, "prev_hash": previous, "payload_sha256": h,
                     "record_hash": item["record_hash"]}
            # First create a durable unique intent. Competing processes and
            # restarts after an incomplete write MUST NOT retry this slot.
            write_once(self.root / "claims" / f"{seq:06d}.json", canonical(claim))
            write_once(self.root / rel, data)
            self.root.mkdir(parents=True, exist_ok=True)
            is_new_index = not self.index.exists()
            with self.index.open("ab") as f:
                f.write(canonical(item) + b"\n")
                f.flush()
                os.fsync(f.fileno())
            if is_new_index and os.name == "posix":
                fd = os.open(self.root, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            return item


def parse_gh_response(raw: bytes, returncode: int, method: str) -> dict:
    """Retain HTTP status and JSON, never persist response headers or CLI stderr."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {"_request_ok": False, "_error": "NON_UTF8_RESPONSE", "_unknown_outcome": method != "GET"}
    # gh api -i includes headers; GitHub may use either CRLF or LF line breaks.
    text = text.replace("\r\n", "\n")
    blocks = text.split("\n\n")
    first = blocks[0].splitlines()[0] if blocks else ""
    match = re.fullmatch(r"HTTP/\S+\s+(\d{3})(?:\s+.*)?", first)
    if match is None:
        return {"_request_ok": False, "_error": "HTTP_STATUS_MISSING", "_unknown_outcome": method != "GET"}
    code = int(match.group(1))
    # We never archive raw headers (authorization/cookies can appear in proxies).
    body = "\n\n".join(blocks[1:])
    try:
        value = json.loads(body) if body.strip() else None
    except ValueError:
        return {"_request_ok": False, "_http_status": code, "_error": "NON_JSON_RESPONSE",
                "_unknown_outcome": method != "GET" and (code < 400 or code >= 500 or code in (408, 429))}
    ok = 200 <= code < 300 and returncode == 0
    result = {"_request_ok": ok, "_http_status": code}
    if ok:
        result["_data"] = value
    else:
        result["_error"] = "HTTP_NON_2XX_OR_CLI_FAILURE"
        result["_message"] = value.get("message", "")[:300] if isinstance(value, dict) else ""
        result["_unknown_outcome"] = method != "GET" and (code >= 500 or code in (408, 429) or (200 <= code < 300))
    return result


def gh_api(path: str, *, method: str = "GET", payload: dict | None = None) -> dict:
    """Uses local gh authorization only. Never prints tokens or sends secrets elsewhere."""
    if not path.startswith("repos/" + LAB_REPO + "/") or any(
        suspicious in path.lower() for suspicious in ("..", "%2e", "\\", "//", "%2f")
    ):
        raise ValueError("GitHub API path outside approved lab repository")
    if method not in ("GET", "PUT"):
        raise ValueError("This lab only supports GET or guarded merge PUT")
    if method == "PUT" and not re.fullmatch(r"repos/" + re.escape(LAB_REPO) + r"/pulls/[1-9][0-9]*/merge", path):
        raise ValueError("Only disposable PR merge API writes are supported")
    cmd = ["gh", "api", "-i", "--method", method, "-H", "Accept: application/vnd.github+json", path]
    stdin = None
    if payload is not None:
        cmd.extend(["--input", "-"])
        stdin = canonical(payload)
    try:
        cp = subprocess.run(cmd, input=stdin, capture_output=True, timeout=25, check=False)
    except FileNotFoundError as e:
        raise RuntimeError("GitHub CLI (gh) is missing") from e
    except subprocess.TimeoutExpired:
        return {"_request_ok": False, "_unknown_outcome": method != "GET", "_error": "GH_TIMEOUT"}
    return parse_gh_response(cp.stdout, cp.returncode, method)


def paged(path: str, key: str | None = None, max_pages: int = 10) -> dict:
    items = []
    for page in range(1, max_pages + 1):
        sep = "&" if "?" in path else "?"
        r = gh_api(path + sep + f"per_page=100&page={page}")
        if not r["_request_ok"]:
            return {"_complete": False, "_error": r["_error"], "_items": items}
        data = r["_data"]
        cur = data.get(key) if key and isinstance(data, dict) else data
        if not isinstance(cur, list):
            return {"_complete": False, "_error": "PAGINATION_SHAPE", "_items": items}
        items.extend(cur)
        if len(cur) < 100:
            return {"_complete": True, "_items": items}
    return {"_complete": False, "_error": "PAGE_CAP", "_items": items}


def snapshot(repo: str, pr_number: int) -> dict:
    ensure_lab(repo)
    if pr_number < 1:
        raise ValueError("Invalid PR number")
    base = f"repos/{repo}"
    pr = gh_api(f"{base}/pulls/{pr_number}")
    if not pr["_request_ok"]:
        return {"snapshot_complete": False, "reason": "PR_LOOKUP_FAILED", "pr": pr, "repo": repo, "number": pr_number}
    p = pr["_data"]
    if p.get("base", {}).get("repo", {}).get("full_name") != LAB_REPO:
        raise ValueError("PR base repository is outside the lab")
    head = p["head"]["sha"]
    ensure_sha(head)
    base_ref = p["base"]["ref"]
    data = {
        "snapshot_utc": utc_now(), "repo": repo, "number": pr_number,
        "head_sha": head, "base_sha": p["base"]["sha"], "base_ref": base_ref,
        "draft": p["draft"], "merged": p["merged"], "mergeable": p.get("mergeable"),
        "mergeable_state": p.get("mergeable_state"),
        "pr_author": p["user"]["login"],
        "checks": paged(f"{base}/commits/{head}/check-runs?filter=all", "check_runs"),
        "statuses": gh_api(f"{base}/commits/{head}/status"),
        "reviews": paged(f"{base}/pulls/{pr_number}/reviews"),
        "review_comments": paged(f"{base}/pulls/{pr_number}/comments"),
        "issue_comments": paged(f"{base}/issues/{pr_number}/comments"),
        "effective_rules": gh_api(f"{base}/rules/branches/{quote(base_ref, safe='')}"),
        "review_threads": {"_complete": False, "_error": "GRAPHQL_THREADS_NOT_COLLECTED"},
        "historical_webhook_coverage": "UNKNOWN",
    }
    data["api_reads_complete"] = all(
        data[k].get("_complete") if k in ("checks", "reviews", "review_comments", "issue_comments")
        else data[k].get("_request_ok")
        for k in ("checks", "statuses", "reviews", "review_comments", "issue_comments", "effective_rules")
    )
    # Successful REST fetches do NOT include GraphQL review threads, event
    # history, or a trusted snapshot of all unreceived deliveries.
    data["complete_observation"] = False
    data["observation_limit"] = "GRAPHQL_THREADS_AND_WEBHOOK_HISTORY_UNVERIFIED"
    return data


def authorized_merge(repo: str, pr_number: int, expected_head: str, base_ref: str, *, execute: bool = False) -> dict:
    ensure_lab(repo)
    ensure_sha(expected_head)
    if not base_ref.startswith(BASE_PREFIX) or base_ref == "main" or pr_number < 1:
        raise ValueError("Only an experiment/r2a0-* base branch may be tested")
    current = gh_api(f"repos/{repo}/pulls/{pr_number}")
    if not current["_request_ok"]:
        return {"status": "UNKNOWN", "reason": "PR_PREFLIGHT_UNAVAILABLE"}
    p = current["_data"]
    if (p["head"]["sha"] != expected_head or p["base"]["ref"] != base_ref or
        p["base"]["repo"]["full_name"] != LAB_REPO or p["draft"] or p["merged"] or p["state"] != "open"):
        return {"status": "HOLD", "reason": "PR_PRECONDITION_MISMATCH"}
    if not execute:
        return {"status": "DRY_RUN", "reason": "NO_WRITE_PERFORMED", "head": expected_head, "base": base_ref}
    if os.environ.get("ARIO_R2A0_DISPOSABLE_MERGE_ACK") != "EXPLICITLY_ALLOW_LAB_MERGE":
        raise PermissionError("Set ARIO_R2A0_DISPOSABLE_MERGE_ACK=EXPLICITLY_ALLOW_LAB_MERGE explicitly")
    response = gh_api(f"repos/{repo}/pulls/{pr_number}/merge", method="PUT", payload={"sha": expected_head, "merge_method": "squash"})
    # Never retry ambiguous PUT outcomes.
    return {"status": "MERGE_API_RETURNED", "response": response, "reconciliation_required": not response["_request_ok"]}


def verify_webhook(secret: bytes, signature: str | None, payload: bytes) -> bool:
    if not secret or not signature or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def make_server(journal: EvidenceJournal, secret: bytes, listen: str, port: int) -> HTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # Avoid dumping payloads/secrets into terminal logs.

        def do_POST(self):
            if self.path != "/github-webhook":
                self.send_error(404)
                return
            try:
                n = int(self.headers.get("Content-Length", "-1"))
                if not (0 <= n <= MAX_WEBHOOK):
                    self.send_error(413)
                    return
                body = self.rfile.read(n)
                if len(body) != n or not verify_webhook(secret, self.headers.get("X-Hub-Signature-256"), body):
                    self.send_error(401)
                    return
                try:
                    parsed = json.loads(body)
                except (ValueError, UnicodeDecodeError):
                    self.send_error(422)
                    return
                if not isinstance(parsed, dict) or parsed.get("repository", {}).get("full_name") != LAB_REPO:
                    self.send_error(403)  # Never store a non-lab event.
                    return
                meta = {
                    "delivery_id": self.headers.get("X-GitHub-Delivery", ""),
                    "github_event": self.headers.get("X-GitHub-Event", ""),
                    "signature_verified": True,
                    "content_type": self.headers.get("Content-Type", ""),
                }
                # Append and fsync before 2XX. No parsing of candidate-controlled payload needed.
                item = journal.append("webhook", "github-hmac256", body, meta)
                self.send_response(202)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(canonical({"record_seq": item["seq"]}))
            except Exception:
                self.send_error(503)  # Fail closed; no claimed successful capture.
    return HTTPServer((listen, port), Handler)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="R2a-0 lab: read-only snapshots and append-only local evidence")
    sub = ap.add_subparsers(dest="command", required=True)
    s = sub.add_parser("snapshot", help="Read and journal a snapshot of a disposable PR")
    s.add_argument("--pr", type=int, required=True)
    s.add_argument("--scenario", choices=SCENARIOS, required=True)
    s.add_argument("--stage", choices=STAGES, required=True)
    s.add_argument("--evidence-dir", type=Path, default=Path("evidence"))
    v = sub.add_parser("verify", help="Verify journal hash chain and payload bytes")
    v.add_argument("--evidence-dir", type=Path, default=Path("evidence"))
    a = sub.add_parser("attempt-merge", help="DRY-RUN by default; actual merge needs two explicit approvals")
    a.add_argument("--pr", type=int, required=True)
    a.add_argument("--scenario", choices=SCENARIOS, required=True)
    a.add_argument("--base", required=True)
    a.add_argument("--expected-head", required=True)
    a.add_argument("--execute", action="store_true")
    a.add_argument("--evidence-dir", type=Path, default=Path("evidence"))
    w = sub.add_parser("listen", help="127.0.0.1 lab-only HMAC receiver; requires GH_WEBHOOK_SECRET")
    w.add_argument("--listen", default="127.0.0.1")
    w.add_argument("--port", type=int, default=8765)
    w.add_argument("--evidence-dir", type=Path, default=Path("evidence"))
    p = sub.add_parser("record", help="Append manual test metadata, NEVER a fabricated PASS")
    p.add_argument("--scenario", choices=SCENARIOS, required=True)
    p.add_argument("--stage", choices=STAGES, required=True)
    p.add_argument("--file", type=Path, required=True)
    p.add_argument("--evidence-dir", type=Path, default=Path("evidence"))
    args = ap.parse_args(argv)
    try:
        if args.command == "verify":
            rows = EvidenceJournal(args.evidence_dir).read()
            integrity = "PASS" if rows else ("EMPTY_JOURNAL" if EvidenceJournal(args.evidence_dir).index.exists() else "NO_JOURNAL")
            print(json.dumps({"journal_integrity": integrity, "records": len(rows), "last_hash": rows[-1]["record_hash"] if rows else None, "historical_completeness": "UNKNOWN", "independent_custody": "NOT_ESTABLISHED"}))
        elif args.command == "snapshot":
            result = snapshot(LAB_REPO, args.pr)
            rec = EvidenceJournal(args.evidence_dir).append("snapshot", "gh-api", canonical(result), {"scenario": args.scenario, "stage": args.stage, "pr": args.pr})
            print(json.dumps({"api_reads_complete": result.get("api_reads_complete", False), "complete_observation": False, "journal_seq": rec["seq"], "journal_hash": rec["record_hash"], "native_merge_result": "NOT_TESTED"}))
        elif args.command == "record":
            result = EvidenceJournal(args.evidence_dir).append("manual", "operator-supplied", args.file.read_bytes(), {"scenario": args.scenario, "stage": args.stage, "authority": "UNVERIFIED"})
            print(json.dumps({"journal_seq": result["seq"], "record_hash": result["record_hash"], "claim": "NOT_VERIFIED"}))
        elif args.command == "attempt-merge":
            journal = EvidenceJournal(args.evidence_dir)
            if args.execute:
                # Reserve exact intent and durably record it BEFORE the native
                # API call. Restart cannot blindly repeat an uncertain merge.
                ensure_lab(LAB_REPO)
                ensure_sha(args.expected_head)
                if not args.base.startswith(BASE_PREFIX) or args.pr < 1:
                    raise ValueError("OUT_OF_SCOPE_MERGE_INTENT")
                intent = {"repo": LAB_REPO, "pr": args.pr, "head": args.expected_head,
                          "base": args.base, "scenario": args.scenario}
                name = digest(canonical(intent)) + ".json"
                write_once(journal.root / "merge_intents" / name, canonical(intent))
                journal.append("merge-intent", "local", canonical(intent),
                               {"scenario": args.scenario, "pr": args.pr})
            response = authorized_merge(LAB_REPO, args.pr, args.expected_head, args.base, execute=args.execute)
            item = journal.append("merge-attempt", "gh-api", canonical(response), {"scenario": args.scenario, "pr": args.pr, "expected_head": args.expected_head, "base": args.base, "execute": args.execute})
            print(json.dumps({"result": response, "journal_seq": item["seq"]}))
        elif args.command == "listen":
            secret = os.environ.get("GH_WEBHOOK_SECRET", "").encode("utf-8")
            if len(secret) < 16:
                raise ValueError("GH_WEBHOOK_SECRET must be provided in the local environment and >=16 bytes")
            if args.listen not in ("127.0.0.1", "::1", "localhost"):
                raise ValueError("Receiver must bind loopback for this lab prototype")
            srv = make_server(EvidenceJournal(args.evidence_dir), secret, args.listen, args.port)
            print(json.dumps({"server": "started", "listen": args.listen, "port": args.port, "scope": "LOOPBACK_ONLY"}), flush=True)
            try:
                srv.serve_forever()
            finally:
                srv.server_close()
        return 0
    except (ValueError, PermissionError, OSError, RuntimeError) as e:
        print(json.dumps({"status": "HOLD", "error": str(e)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
