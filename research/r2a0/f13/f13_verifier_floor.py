#!/usr/bin/env python3
"""F13: local simulator of a separately retained verifier floor.

RESEARCH ONLY. A second directory/process is NOT independent custody. No
network, keys, native merges or promotion to trust/production is implemented.
The floor only lets a verifier reject a changed/rolled-back publisher state
*if* its own earlier pin survives intact outside publisher control.
"""
from __future__ import annotations

from contextlib import closing
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Callable

import f7_coordinator as f7
from r2a0 import canonical, digest

_SHA = re.compile(r"[a-f0-9]{64}\Z")


def hold(reason: str, **extra: object) -> dict:
    return {"status": "HOLD", "reason": reason, "merge_authorization": "NOT_GRANTED",
            "independent_custody": "NOT_ESTABLISHED", "native_merge": "NOT_RUN", **extra}


def capture(authority_db: Path, repo: str, pr: int) -> dict:
    """Capture a bounded snapshot of F12 publisher state, never authorize it."""
    coord = f7.SharedCoordinator(Path(authority_db))
    view = coord.inspect(repo, pr)
    if view.get("observation_status") != "CURRENT_LOCAL_READBACK_MATCH_NOT_INDEPENDENT":
        raise ValueError("PUBLISHER_NOT_CURRENTLY_REVALIDATED")
    with closing(coord._connect(readonly=True)) as db:
        claim = db.execute("SELECT marker,root_label FROM claims WHERE repo=? AND pr=?", (repo,pr)).fetchone()
        consumed = db.execute("SELECT marker,root_label,evidence_root FROM consumptions WHERE repo=? AND pr=?", (repo,pr)).fetchone()
        snapshot = db.execute("SELECT marker,root_label,evidence_root_sha256,journal_sha256,record_hash FROM observation_snapshots WHERE repo=? AND pr=?", (repo,pr)).fetchone()
        root = db.execute("SELECT marker,evidence_root_sha256 FROM root_bindings WHERE repo=? AND pr=?", (repo,pr)).fetchone()
    if not claim or not consumed or not snapshot or not root:
        raise ValueError("PUBLISHER_EVIDENCE_INCOMPLETE")
    if claim != consumed[:2] or claim != snapshot[:2] or root != (claim[0],snapshot[2]):
        raise ValueError("PUBLISHER_SOURCE_BINDING_MISMATCH")
    if not (_SHA.fullmatch(snapshot[3]) and _SHA.fullmatch(snapshot[4])):
        raise ValueError("PUBLISHER_SOURCE_HASH_INVALID")
    return {"version": 1, "repo": repo, "pr": pr, "marker": claim[0],
            "root_label": claim[1], "evidence_root_sha256": snapshot[2],
            "journal_sha256": snapshot[3], "record_hash": snapshot[4],
            "observation": "LOCAL_READBACK_MATCH_NOT_INDEPENDENT"}


class VerifierFloor:
    """One-time, separately retained *simulated* floor per repo/PR.

    The lab owner can delete/rewrite this file and forge both publisher/floor:
    neither append-only protection nor independent administration is established.
    """
    def __init__(self, directory: Path):
        self.directory = Path(directory)

    def _path(self, repo: str, pr: int) -> Path:
        if not isinstance(repo,str) or not repo or not isinstance(pr,int) or pr < 1:
            raise ValueError("INVALID_FLOOR_SUBJECT")
        # Hash subject: no path traversal or arbitrary filenames from repo strings.
        return self.directory / (digest(canonical({"repo":repo,"pr":pr})) + ".json")

    def _check_directory(self):
        if not self.directory.is_dir() or ".." in self.directory.parts or any(p.is_symlink() for p in (self.directory,*self.directory.parents)):
            raise ValueError("VERIFIER_FLOOR_DIRECTORY_UNAVAILABLE_OR_SYMLINK")

    def pin(self, authority_db: Path, repo: str, pr: int, *, after_pin: Callable[[],None] | None = None) -> dict:
        """Durably pin only a current F12 readback, then recheck source.

        An injected after_pin hook exists solely for deterministic crash/race lab
        experiments. A changed source produces HOLD and leaves the floor pinned.
        """
        self._check_directory()
        path = self._path(repo,pr)
        before = capture(authority_db,repo,pr)
        body = {"schema":1,"subject":{"repo":repo,"pr":pr},"publisher":before,
                "checkpoint_sha256":digest(canonical(before))}
        contents = canonical(body)
        if path.is_symlink():
            raise ValueError("VERIFIER_FLOOR_SYMLINK")
        try:
            fd = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        except FileExistsError:
            return hold("VERIFIER_FLOOR_ALREADY_PINNED")
        with os.fdopen(fd,"wb") as out:
            out.write(contents)
            out.flush()
            os.fsync(out.fileno())
        if os.name == "posix":
            directory_fd = os.open(self.directory,os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        # Fail closed on post-write changes; preserve original floor on disk.
        if after_pin is not None:
            after_pin()
        try:
            after = capture(authority_db,repo,pr)
        except (ValueError,OSError,sqlite3.Error):
            return hold("PUBLISHER_CHANGED_DURING_PIN_PIN_RETAINED")
        if after != before:
            return hold("PUBLISHER_CHANGED_DURING_PIN_PIN_RETAINED")
        return hold("CHECKPOINT_PINNED_FOR_FORENSIC_COMPARISON_ONLY",
                    checkpoint_sha256=body["checkpoint_sha256"], pinned=True)

    def check(self, authority_db: Path, repo: str, pr: int) -> dict:
        self._check_directory()
        path = self._path(repo,pr)
        if not path.is_file() or path.is_symlink():
            return hold("VERIFIER_FLOOR_MISSING_OR_UNSAFE")
        try:
            raw = path.read_bytes()
            body = json.loads(raw)
            if (canonical(body) != raw or body["schema"] != 1 or
                body["subject"] != {"repo":repo,"pr":pr} or
                digest(canonical(body["publisher"])) != body["checkpoint_sha256"]):
                return hold("VERIFIER_FLOOR_TAMPERED_OR_MALFORMED")
            current = capture(authority_db,repo,pr)
        except (ValueError,KeyError,TypeError,OSError,sqlite3.Error,UnicodeDecodeError):
            return hold("VERIFIER_OR_PUBLISHER_UNREADABLE")
        if current != body["publisher"]:
            return hold("PUBLISHER_DIFFERS_FROM_RETAINED_CHECKPOINT",
                        retained_checkpoint=body["checkpoint_sha256"])
        return hold("CURRENT_MATCH_TO_RETAINED_LOCAL_CHECKPOINT_NOT_INDEPENDENT",
                    checkpoint_sha256=body["checkpoint_sha256"], matched=True)
