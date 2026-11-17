#!/usr/bin/env python3
"""F7 research-only shared SQLite serialization for local orphan-evidence recording.

This is not an App publisher, merge approval, security boundary against the
owner, independent custody, a network service, or multi-host consensus.

F8: the supported r2a0 public API and CLI now REQUIRE this coordinator.
Private Python internals can still be invoked by code running with the same
owner privileges; this is NOT an OS/cryptographic trust boundary. All writers
must use the SAME database. A copy/restore can fork authority.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys

from r2a0 import (
    EvidenceJournal, _merge_intent_entries, _append_orphan_after_claim_internal,
    canonical, digest,
)

ACK = "RECORD_ORPHAN_ONLY_NO_MERGE_RETRY"
DB_VERSION = 7
SHA256 = re.compile(r"[a-f0-9]{64}\Z")


def _hold(reason: str, **extra: object) -> dict:
    return {
        "status": "HOLD", "reason": reason,
        "merge_authorization": "NOT_GRANTED", "remote_merge_retry": "FORBIDDEN",
        "independent_custody": "NOT_ESTABLISHED", "multi_host_consensus": "NOT_ESTABLISHED",
        **extra,
    }


class SharedCoordinator:
    """One preinitialized SQLite file, atomic unique PR claim, no automatic leases."""

    def __init__(self, filename: Path):
        self.filename = Path(filename)

    def _safe_file(self) -> None:
        # Do not create the DB, follow a symlink, or silently repair an absent DB.
        if (self.filename.is_symlink() or self.filename.parent.is_symlink()
                or not self.filename.is_file()):
            raise ValueError("COORDINATOR_MISSING_OR_SYMLINK")
        # Windows can resolve legitimate absolute paths to a different spelling
        # (volume/junction/case normalization). Do not compare Path.resolve()
        # string equality against Path.absolute(); reject *actual* symlink
        # components and explicit parent traversal instead.
        if ".." in self.filename.parts or any(part.is_symlink() for part in (self.filename, *self.filename.parents)):
            raise ValueError("COORDINATOR_PATH_ALIAS_OR_SYMLINK")
        if self.filename.stat().st_size == 0:
            raise ValueError("COORDINATOR_UNINITIALIZED")

    @classmethod
    def initialize(cls, filename: Path) -> "SharedCoordinator":
        """Explicitly create a new, empty *lab-only* DB. Never overwrite."""
        filename = Path(filename)
        if ".." in filename.parts or any(part.is_symlink() for part in (filename, *filename.parents)):
            raise ValueError("SYMLINK_COORDINATOR_DIRECTORY")
        filename.parent.mkdir(parents=True, exist_ok=True)
        # The exclusive creation is a one-time marker; an interrupted setup HOLDS.
        fd = os.open(filename, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        coord = cls(filename)
        try:
            with closing(sqlite3.connect(filename, timeout=1.0, isolation_level=None)) as db:
                db.execute("PRAGMA synchronous=FULL")
                db.execute("PRAGMA journal_mode=DELETE")
                db.execute("BEGIN IMMEDIATE")
                db.execute("CREATE TABLE claims (repo TEXT NOT NULL, pr INTEGER NOT NULL, marker TEXT NOT NULL, root_label TEXT NOT NULL, PRIMARY KEY (repo,pr))")
                db.execute("CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, repo TEXT NOT NULL, pr INTEGER NOT NULL, marker TEXT NOT NULL, phase TEXT NOT NULL, root_label TEXT NOT NULL)")
                db.execute(f"PRAGMA user_version={DB_VERSION}")
                db.commit()
        except Exception:
            # Preserve the interrupted DB file as evidence: never unlink here.
            raise
        return coord

    def _connect(self) -> sqlite3.Connection:
        self._safe_file()
        # mode=rw explicitly refuses database creation. URI is quoted via as_uri.
        uri = self.filename.resolve(strict=True).as_uri() + "?mode=rw"
        db = sqlite3.connect(uri, uri=True, timeout=0.5, isolation_level=None)
        try:
            db.execute("PRAGMA busy_timeout=500")
            db.execute("PRAGMA synchronous=FULL")
            if db.execute("PRAGMA user_version").fetchone()[0] != DB_VERSION:
                raise ValueError("COORDINATOR_SCHEMA_VERSION_MISMATCH")
            objects = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"claims", "events"}.issubset(objects):
                raise ValueError("COORDINATOR_SCHEMA_INCOMPLETE")
            return db
        except Exception:
            db.close()
            raise

    def claim(self, intent: dict, marker: str, root_label: str) -> dict:
        """Permit *one* local observation for repo+PR; never permit a merge.

        Retry with same marker is also HOLD. Changing HEAD/scenario cannot create
        a new permit for the same repo+PR; this is intentionally conservative.
        """
        if not isinstance(root_label, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,50}", root_label):
            raise ValueError("INVALID_ROOT_LABEL")
        if not isinstance(marker, str) or not SHA256.fullmatch(marker):
            raise ValueError("INVALID_MARKER_SHA256")
        EvidenceJournal._validated_merge_intent(canonical(intent))
        if digest(canonical(intent)) != marker:
            raise ValueError("MARKER_INTENT_MISMATCH")
        try:
            with closing(self._connect()) as db:
                db.execute("BEGIN IMMEDIATE")
                existing = db.execute("SELECT marker, root_label FROM claims WHERE repo=? AND pr=?", (intent['repo'], intent['pr'])).fetchone()
                if existing:
                    # Still audit the refused attempt. No re-grant / no lease expiry.
                    db.execute("INSERT INTO events(repo,pr,marker,phase,root_label) VALUES(?,?,?,?,?)", (
                        intent['repo'], intent['pr'], marker, "REFUSED_DUPLICATE", root_label))
                    db.commit()
                    return _hold("GLOBAL_INTENT_ALREADY_CLAIMED", existing_marker=existing[0],
                                 same_marker=existing[0] == marker)
                db.execute("INSERT INTO claims(repo,pr,marker,root_label) VALUES(?,?,?,?)", (
                    intent['repo'], intent['pr'], marker, root_label))
                db.execute("INSERT INTO events(repo,pr,marker,phase,root_label) VALUES(?,?,?,?,?)", (
                    intent['repo'], intent['pr'], marker, "CLAIMED", root_label))
                db.commit()
                return _hold("GLOBAL_CLAIM_DURABLY_RECORDED_LOCAL_RESULT_UNKNOWN",
                             claim_recorded=True, marker=marker)
        except sqlite3.Error as exc:
            raise ValueError("COORDINATOR_UNAVAILABLE_OR_CORRUPT") from exc

    def record_local_observation(self, intent: dict, marker: str, root_label: str) -> None:
        """Append a second fact after local evidence append; no state overwrite."""
        try:
            with closing(self._connect()) as db:
                db.execute("BEGIN IMMEDIATE")
                stored = db.execute("SELECT marker, root_label FROM claims WHERE repo=? AND pr=?", (
                    intent['repo'], intent['pr'])).fetchone()
                if stored != (marker, root_label):
                    raise ValueError("GLOBAL_CLAIM_OWNER_OR_MARKER_MISMATCH")
                phases = [row[0] for row in db.execute("SELECT phase FROM events WHERE repo=? AND pr=? AND marker=? AND root_label=?", (
                    intent['repo'], intent['pr'], marker, root_label))]
                if phases.count("CLAIMED") != 1 or "LOCAL_EVIDENCE_RECORDED" in phases:
                    raise ValueError("GLOBAL_CLAIM_PHASE_INCONSISTENT")
                db.execute("INSERT INTO events(repo,pr,marker,phase,root_label) VALUES(?,?,?,?,?)", (
                    intent['repo'], intent['pr'], marker, "LOCAL_EVIDENCE_RECORDED", root_label))
                db.commit()
        except sqlite3.Error as exc:
            raise ValueError("COORDINATOR_UNAVAILABLE_OR_CORRUPT") from exc

    def inspect(self, repo: str, pr: int) -> dict:
        # Read-only by contract at the API level (SQLite may create transient lock files).
        try:
            with closing(self._connect()) as db:
                row = db.execute("SELECT marker, root_label FROM claims WHERE repo=? AND pr=?", (repo, pr)).fetchone()
                events = db.execute("SELECT phase FROM events WHERE repo=? AND pr=? ORDER BY id", (repo, pr)).fetchall()
                return _hold("GLOBAL_STATE_OBSERVED_NOT_ADMISSION", claim_exists=row is not None,
                             marker=row[0] if row else None, events=[x[0] for x in events])
        except sqlite3.Error as exc:
            raise ValueError("COORDINATOR_UNAVAILABLE_OR_CORRUPT") from exc


def adopt_with_shared_coordinator(journal: EvidenceJournal, coordinator: SharedCoordinator,
                                  marker: str, *, root_label: str, ack: str,
                                  after_claim=None) -> dict:
    """Mandatory ordering for this *adapter only*: local preflight → global claim → append.

    A crash at any point after grant keeps it claimed, with no expiry and no
    automatic takeover. Supported public API/CLI now require this adapter.
    Private internals and hostile same-owner code are NOT security-isolated.
    """
    if ack != ACK:
        raise PermissionError("EXPLICIT_RECOVERY_ACK_REQUIRED")
    entries, _, integrity = _merge_intent_entries(journal)
    if integrity != "HOLD_ORPHAN_INTENT" or len(entries) != 1:
        raise ValueError("NOT_A_SINGLE_SAFE_TO_RECORD_ORPHAN")
    chosen = entries[0]
    if chosen['marker_sha256'] != marker or chosen['journal_stage'] != "ORPHAN_MARKER_NOT_JOURNALED":
        raise ValueError("MARKER_NOT_THE_ONLY_ORPHAN")
    result = coordinator.claim(chosen['intent'], marker, root_label)
    if not result.get("claim_recorded"):
        return result
    if after_claim is not None:
        after_claim()  # Fault injection in local tests only; can hard-crash.
    try:
        local = _append_orphan_after_claim_internal(journal, marker, ack=ack)
    except Exception:
        # Persistent global claim is never undone or transferred automatically.
        raise
    coordinator.record_local_observation(chosen['intent'], marker, root_label)
    return _hold("LOCAL_RECOVERY_RECORDED_GLOBAL_CLAIM_HELD_NO_MERGE_RETRY",
                 journal_record_seq=local['record_seq'], journal_record_hash=local['record_hash'],
                 marker=marker)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="F7 lab-only shared SQLite ordering; never publishes GitHub checks or merges.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    setup = sub.add_parser("init", help="Explicitly create a new shared lab DB; never overwrite")
    setup.add_argument('--db', type=Path, required=True)
    adopt = sub.add_parser("adopt", help="Opt-in coordinated, evidence-only orphan adoption")
    adopt.add_argument('--db', type=Path, required=True)
    adopt.add_argument('--evidence-dir', type=Path, required=True)
    adopt.add_argument('--marker', required=True)
    adopt.add_argument('--root-label', required=True)
    adopt.add_argument('--ack', required=True)
    view = sub.add_parser("inspect", help="Observe the single DB; never authorizes merging")
    view.add_argument('--db', type=Path, required=True)
    view.add_argument('--pr', type=int, required=True)
    args = parser.parse_args(argv)
    try:
        if args.cmd == 'init':
            SharedCoordinator.initialize(args.db)
            result = _hold("LAB_COORDINATOR_INITIALIZED_NO_ADMISSION")
        elif args.cmd == 'adopt':
            result = adopt_with_shared_coordinator(EvidenceJournal(args.evidence_dir), SharedCoordinator(args.db), args.marker,
                                                   root_label=args.root_label, ack=args.ack)
        else:
            result = SharedCoordinator(args.db).inspect('SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a', args.pr)
        print(json.dumps(result, sort_keys=True))
        return 0 if args.cmd == 'init' else 2  # All other exits are HOLD.
    except (ValueError, PermissionError, OSError, sqlite3.Error) as exc:
        print(json.dumps(_hold("COORDINATOR_OR_EVIDENCE_HOLD", error=str(exc)), sort_keys=True))
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
