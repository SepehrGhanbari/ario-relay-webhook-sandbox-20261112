#!/usr/bin/env python3
"""F6 read-only comparison of two *explicitly supplied* independent R2a-0 journals.

The comparator does not claim historical completeness, consensus, shared-lock
semantics, independent key custody, or any permission to retry a merge.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from r2a0 import EvidenceJournal, inspect_merge_recovery


def _inspect(path: Path) -> dict:
    if path.is_symlink() or not path.is_dir():
        raise ValueError('MISSING_OR_SYMLINK_ROOT')
    journal = EvidenceJournal(path)
    rows = journal.read()  # Per-root chain, objects, claims, marker verification.
    if not rows:
        raise ValueError('EMPTY_OR_UNINITIALIZED_JOURNAL')
    rec = inspect_merge_recovery(journal)
    return {
        'rows': len(rows),
        'last_hash': rows[-1]['record_hash'],
        'intents': {item['marker_sha256']: item for item in rec['intents']},
        'root_identity': (path.stat().st_dev, path.stat().st_ino),
        'device': path.stat().st_dev,
    }


def compare(left: Path, right: Path) -> dict:
    """Always HOLD/UNKNOWN; never treat two observed roots as the whole world."""
    roots = [Path(left), Path(right)]
    try:
        if roots[0].is_symlink() or roots[1].is_symlink():
            raise ValueError('SYMLINK_ROOT')
        if not all(x.is_dir() for x in roots):
            raise ValueError('MISSING_ROOT')
        if os.path.samefile(*roots):
            raise ValueError('SAME_ROOT_TWICE')
        a, b = (_inspect(path) for path in roots)
        if a['root_identity'] == b['root_identity']:
            raise ValueError('SAME_ROOT_IDENTITY')
        common = sorted(set(a['intents']) & set(b['intents']))
        conflicts = []
        for h in common:
            ia, ib = a['intents'][h], b['intents'][h]
            conflicts.append({
                'marker_sha256': h,
                'left_stage': ia['journal_stage'],
                'right_stage': ib['journal_stage'],
                'same_intent_bytes': ia['intent'] == ib['intent'],
            })
        return {
            'status': 'HOLD_DUPLICATE_INTENT_ACROSS_ROOTS' if common else 'UNKNOWN_NO_DUPLICATE_IN_TWO_OBSERVED_ROOTS',
            'observed_roots': 2,
            'distinct_filesystem_devices': a['device'] != b['device'],
            'left': {'records': a['rows'], 'last_hash': a['last_hash'], 'merge_intent_count': len(a['intents'])},
            'right': {'records': b['rows'], 'last_hash': b['last_hash'], 'merge_intent_count': len(b['intents'])},
            'same_intent_markers': conflicts,
            'potential_backup_copy': bool(common),  # same intent alone is NOT proof of independent writers
            'root_set_completeness': 'UNKNOWN',
            'independent_custody': 'NOT_ESTABLISHED',
            'remote_merge_retry': 'FORBIDDEN',
            'merge_authorization': 'NOT_GRANTED',
        }
    except (ValueError, OSError) as exc:
        return {
            'status': 'HOLD_ROOT_INSPECTION_FAILED',
            'error': str(exc),
            'observed_roots': 2,
            'root_set_completeness': 'UNKNOWN',
            'independent_custody': 'NOT_ESTABLISHED',
            'remote_merge_retry': 'FORBIDDEN',
            'merge_authorization': 'NOT_GRANTED',
        }


def main() -> int:
    p = argparse.ArgumentParser(description='Read-only comparison of two R2a-0 journals; never authorizes merging.')
    p.add_argument('left', type=Path)
    p.add_argument('right', type=Path)
    args = p.parse_args()
    result = compare(args.left, args.right)
    print(json.dumps(result, sort_keys=True))
    return 2 if result['status'].startswith('HOLD') else 3  # NO EXIT 0: no authoritative success


if __name__ == '__main__':
    raise SystemExit(main())
