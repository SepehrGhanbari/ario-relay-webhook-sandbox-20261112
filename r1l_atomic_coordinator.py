"""R1l local loopback-only shared coordinator; RESEARCH / NO PRODUCTION TRUST.

One server owns a SQLite WAL database with a UNIQUE claim transaction.
Many client processes (with separate local filesystems) use the SAME server.
No GitHub API, no Check publication, no token/keys, no authorization endpoint.

This service never grants permission for an external Check POST. It only
atomically records one frozen lab intent; uncertain outcomes always HOLD.

Security boundary: single SQLite host/filesystem; NOT a networked DB quorum,
not authenticated between hosts, not a globally linearizable deployment.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import sys
import threading

REPO = "SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a"
PR = 14
HEAD = "1c55dad097fc5544c8b36bc02ebb6eeb74c8a6e8"
BASE = "be7c16d964872f88ddb9029f2677c49a7cd745ba"
APP_ID = 5747504
NAME = "ario-r1d-lab-app-gate"
EXTERNAL_ID = "R1L-RESEARCH-PR14-HEAD-" + HEAD
DEPLOYMENT = "R1L-TEST-ONLY-NOT-TRUSTED-20261113"
EXPECTED_FIELDS = {"schema", "repo", "pr_number", "head_sha", "base_sha",
                   "app_id", "check_name", "external_id", "evidence_sha256"}
MAX_BODY_BYTES = 4096


def answer(verdict: str, reason: str, *, created: bool = False,
           count: int | None = None) -> dict:
    d = {"verdict": verdict, "reason": reason, "created": created,
         "can_publish": False, "repeat_post_allowed": False,
         "github_check_emitted": False, "production_trust": "NO_GO"}
    if count is not None:
        d["claim_count"] = count
    return d


def valid_intent(value: object) -> bool:
    return (
        type(value) is dict and set(value) == EXPECTED_FIELDS and
        value["schema"] == "r1l-local-coordinator-v1" and
        value["repo"] == REPO and type(value["pr_number"]) is int and
        value["pr_number"] == PR and value["head_sha"] == HEAD and
        value["base_sha"] == BASE and type(value["app_id"]) is int and
        value["app_id"] == APP_ID and value["check_name"] == NAME and
        value["external_id"] == EXTERNAL_ID and
        type(value["evidence_sha256"]) is str and
        re.fullmatch(r"[0-9a-f]{64}", value["evidence_sha256"]) is not None
    )


def fixed_intent(evidence: str = "a" * 64) -> dict:
    return {
        "schema": "r1l-local-coordinator-v1", "repo": REPO,
        "pr_number": PR, "head_sha": HEAD, "base_sha": BASE,
        "app_id": APP_ID, "check_name": NAME, "external_id": EXTERNAL_ID,
        "evidence_sha256": evidence,
    }


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)

    def _conn(self):
        # Metadata check below fails if the DB was removed or recreated.
        conn = sqlite3.connect(str(self.path), timeout=0.2, isolation_level=None)
        conn.execute("PRAGMA busy_timeout=200")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    @classmethod
    def bootstrap(cls, path: Path) -> None:
        """A SEPARATE one-time, manual lab operation, never automatic recovery."""
        path = Path(path)
        if not path.parent.is_dir() or path.is_symlink():
            raise RuntimeError("INVALID_DB_PARENT_OR_SYMLINK")
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        try:
            with sqlite3.connect(str(path)) as db:
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("PRAGMA synchronous=FULL")
                db.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                db.execute("INSERT INTO metadata VALUES ('deployment', ?)", (DEPLOYMENT,))
                db.execute("""CREATE TABLE claims (
                    repo TEXT NOT NULL, app_id INTEGER NOT NULL,
                    check_name TEXT NOT NULL, pr_number INTEGER NOT NULL,
                    head_sha TEXT NOT NULL, base_sha TEXT NOT NULL,
                    external_id TEXT NOT NULL, evidence_sha256 TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state='CLAIMED_UNKNOWN'),
                    PRIMARY KEY (repo, app_id, check_name, pr_number, head_sha),
                    UNIQUE (repo, app_id, check_name, external_id)
                )""")
                db.commit()
        except BaseException:
            # Keep a failed bootstrap file as a tombstone: never silently reset.
            raise

    @staticmethod
    def _validate_db(db) -> None:
        record = db.execute("SELECT value FROM metadata WHERE key='deployment'").fetchone()
        if record != (DEPLOYMENT,):
            raise RuntimeError("DB_DEPLOYMENT_IDENTITY_MISMATCH")

    def verify_existing(self) -> None:
        if not self.path.is_file() or self.path.is_symlink():
            raise RuntimeError("DB_MISSING_OR_SYMLINK_NO_AUTOMATIC_BOOTSTRAP")
        with self._conn() as db:
            self._validate_db(db)
            ok = db.execute("PRAGMA integrity_check").fetchone()
            if ok != ("ok",):
                raise RuntimeError("DB_INTEGRITY_FAILURE")
            # Validate schema present without inserting or deleting claims.
            db.execute("SELECT 1 FROM claims LIMIT 1").fetchone()

    def reserve(self, intent: dict) -> dict:
        if not valid_intent(intent):
            return answer("HOLD", "SCOPE_OR_SCHEMA_INVALID")
        try:
            # Each incoming request uses a separate connection, even threads.
            db = self._conn()
            try:
                self._validate_db(db)
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("""SELECT base_sha, external_id, evidence_sha256
                    FROM claims WHERE repo=? AND app_id=? AND check_name=?
                        AND pr_number=? AND head_sha=?""",
                    (REPO, APP_ID, NAME, PR, HEAD)).fetchone()
                if row is not None:
                    db.execute("COMMIT")
                    if row == (BASE, EXTERNAL_ID, intent["evidence_sha256"]):
                        return answer("ALREADY_HELD", "DURABLE_CLAIM_EXISTS", count=1)
                    return answer("CONFLICT_HOLD", "SCOPE_ALREADY_CLAIMED_DIFFERENT_EVIDENCE",
                                  count=1)
                db.execute("""INSERT INTO claims
                    (repo, app_id, check_name, pr_number, head_sha, base_sha,
                     external_id, evidence_sha256, state)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'CLAIMED_UNKNOWN')""",
                    (REPO, APP_ID, NAME, PR, HEAD, BASE, EXTERNAL_ID, intent["evidence_sha256"]))
                db.execute("COMMIT")
                return answer("CREATED_HOLD", "DURABLE_INTENT_CREATED_NOT_PUBLISH_AUTHORITY",
                              created=True, count=1)
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
            finally:
                db.close()
        except (sqlite3.Error, OSError, RuntimeError):
            return answer("UNKNOWN_HOLD", "DB_TRANSACTION_UNAVAILABLE")

    def status(self) -> dict:
        try:
            db = self._conn()
            try:
                self._validate_db(db)
                rows = db.execute("""SELECT base_sha, external_id, evidence_sha256, state
                    FROM claims WHERE repo=? AND app_id=? AND check_name=?
                        AND pr_number=? AND head_sha=?""",
                    (REPO, APP_ID, NAME, PR, HEAD)).fetchall()
                if len(rows) == 0:
                    return answer("ABSENT_HOLD", "NO_CLAIM_CANNOT_PROVE_NO_PRIOR_POST",
                                  count=0)
                if len(rows) != 1 or rows[0][0] != BASE or rows[0][1] != EXTERNAL_ID or \
                        rows[0][3] != "CLAIMED_UNKNOWN":
                    return answer("CONFLICT_HOLD", "STORED_CLAIM_INCONSISTENT")
                return answer("CLAIMED_UNKNOWN_HOLD", "READ_ONLY_RECOVERY", count=1)
            finally:
                db.close()
        except (sqlite3.Error, OSError, RuntimeError):
            return answer("UNKNOWN_HOLD", "DB_READ_UNAVAILABLE")


class LabServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, store, fault):
        super().__init__(address, handler)
        self.store = store
        self.fault = fault
        self._fault_used = False
        self._fault_guard = threading.Lock()

    def take_fault(self) -> str | None:
        with self._fault_guard:
            if self._fault_used:
                return None
            self._fault_used = True
            return self.fault


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def respond(self, code, value):
        data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path != "/status":
            return self.respond(404, answer("HOLD", "UNKNOWN_ENDPOINT"))
        state = self.server.store.status()
        return self.respond(200 if state["verdict"] != "UNKNOWN_HOLD" else 503, state)

    def do_POST(self):
        if self.path != "/reserve":
            return self.respond(404, answer("HOLD", "UNKNOWN_ENDPOINT"))
        try:
            n = int(self.headers.get("Content-Length", "-1"))
            if n < 1 or n > MAX_BODY_BYTES:
                return self.respond(400, answer("HOLD", "BODY_SIZE_INVALID"))
            raw = self.rfile.read(n)
            intent = json.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError, json.JSONDecodeError):
            return self.respond(400, answer("HOLD", "JSON_INVALID"))
        if not valid_intent(intent):
            return self.respond(400, answer("HOLD", "SCOPE_OR_SCHEMA_INVALID"))
        result = self.server.store.reserve(intent)
        if result["verdict"] == "CREATED_HOLD":
            fault = self.server.take_fault()
            if fault == "crash_after_commit_once":
                # Test-only abrupt server death AFTER SQLite COMMIT, BEFORE reply.
                os._exit(91)
            if fault == "drop_reply_after_commit_once":
                try:
                    self.connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                self.connection.close()
                return
        code = 503 if result["verdict"] == "UNKNOWN_HOLD" else 200
        return self.respond(code, result)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--bootstrap-only", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--fault", choices=(
        "none", "crash_after_commit_once", "drop_reply_after_commit_once"), default="none")
    args = parser.parse_args(argv)
    if args.bootstrap_only:
        Store.bootstrap(Path(args.db))
        print("R1L_EXPLICIT_BOOTSTRAP_ONLY", flush=True)
        return 0
    store = Store(Path(args.db))
    store.verify_existing()  # never quietly create empty new coordinator
    with LabServer(("127.0.0.1", args.port), Handler, store, args.fault) as server:
        print("R1L_READY_PORT=" + str(server.server_port), flush=True)
        server.serve_forever(poll_interval=0.1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
