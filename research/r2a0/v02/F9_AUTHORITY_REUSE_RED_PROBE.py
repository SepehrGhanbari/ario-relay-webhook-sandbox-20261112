#!/usr/bin/env python3
"""F9-RED: demonstrate same-owner reuse of one DB-checkable authority.

Local research-only falsifier. It never uses GitHub CLI, real credentials,
production repositories, privileged operations, or any network transport.
A successful *reproduction* means the intended global-single-use property
is NOT established. Keep DRAFT / P0_HOLD.
"""
import tempfile
from pathlib import Path

import r2a0
import f7_coordinator as f7


def reproduce():
    intent = {"repo": r2a0.LAB_REPO, "pr": 76, "head": "a" * 40,
              "base": "experiment/r2a0-f9", "scenario": "Sc1"}
    raw = r2a0.canonical(intent)
    marker = r2a0.digest(raw)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        coordinator = f7.SharedCoordinator.initialize(root / "shared.sqlite")
        claim = coordinator.claim(intent, marker, "SAME_LABEL")
        authority = f7.mint_intent_authority(coordinator, intent, marker, "SAME_LABEL")
        outcomes = []
        for label in ("A", "B"):
            evidence_root = root / label
            r2a0.write_once(evidence_root / "merge_intents" / (marker + ".json"), raw)
            journal = r2a0.EvidenceJournal(evidence_root)
            journal.append("merge-intent", "local", raw, merge_intent_authority=authority)
            outcomes.append({"root": label, "recorded": len(journal.read()) == 1})
        recorded = sum(bool(row["recorded"]) for row in outcomes)
        phases = coordinator.inspect(intent["repo"], intent["pr"])["events"]
        assert claim.get("claim_recorded")
        assert recorded == 2 and phases == ["CLAIMED"], (outcomes, phases)
        return {
            "finding": "VERIFIED_DOUBLE_USE_OF_DB_CHECKABLE_AUTHORITY",
            "outcomes": outcomes,
            "coordinator_events": phases,
            "remote_merge_api": "NOT_CALLED",
            "global_single_use": "NOT_ESTABLISHED",
        }


if __name__ == "__main__":
    import json
    print(json.dumps(reproduce(), sort_keys=True))
