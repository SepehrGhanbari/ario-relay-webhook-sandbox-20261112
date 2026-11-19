"""F12 test contract: historical event != currently readable receipt.

Scope: one shared owner-writable SQLite and local evidence root. Same-owner
replacement of both bindings and journal is OUT OF SECURITY SCOPE. Never merge.
"""
from pathlib import Path
import shutil
import sqlite3
from unittest.mock import patch
from test_f10_atomic_single_use import _NoNetwork
from test_f7_coordinator import INTENT
import f7_coordinator as f7
import r2a0


class TestF12LiveObservation(_NoNetwork):
    def _append(self):
        journal = r2a0.EvidenceJournal(self.a)
        journal.append('merge-intent', 'local', self.raw, merge_intent_authority=self._authority())
        return journal

    def _observe(self):
        return self.coord.record_local_observation(INTENT, self.marker, 'SAME_LABEL')

    def _inspect(self):
        return self.coord.inspect(INTENT['repo'], INTENT['pr'])

    def test_valid_local_snapshot_is_explicitly_not_independent(self):
        self._append()
        self._observe()
        state = self._inspect()
        self.assertEqual(state['observation_status'], 'CURRENT_LOCAL_READBACK_MATCH_NOT_INDEPENDENT')
        self.assertTrue(state['events_are_historical_not_proof'])
        self.assertFalse(state['claim_exists'] is False)
        self.assertEqual(state['merge_authorization'], 'NOT_GRANTED')
        self.assertEqual(state['independent_custody'], 'NOT_ESTABLISHED')

    def test_post_commit_evidence_deletion_downgrades_and_preserves_history(self):
        self._append()
        self._observe()
        (self.a / 'journal.jsonl').unlink()
        shutil.rmtree(self.a / 'objects')
        state = self._inspect()
        self.assertIn('LOCAL_EVIDENCE_RECORDED', state['events'])
        self.assertEqual(state['observation_status'], 'UNKNOWN_LOCAL_EVIDENCE_NOT_REVALIDATED')
        self.assertTrue(state['events_are_historical_not_proof'])
        self.assertEqual(state['merge_authorization'], 'NOT_GRANTED')

    def test_post_commit_payload_corruption_downgrades(self):
        self._append()
        self._observe()
        next((self.a / 'objects').glob('*.bin')).write_bytes(b'corrupt')
        self.assertEqual(self._inspect()['observation_status'], 'UNKNOWN_LOCAL_EVIDENCE_NOT_REVALIDATED')

    def test_after_read_during_record_truncation_denied_without_phase(self):
        self._append()
        orig = r2a0.EvidenceJournal.read
        def adversarial_read(journal, *a, **kw):
            records = orig(journal, *a, **kw)
            journal.index.write_bytes(b'')
            return records
        with patch.object(r2a0.EvidenceJournal, 'read', adversarial_read):
            with self.assertRaises(ValueError):
                self._observe()
        self.assertNotIn('LOCAL_EVIDENCE_RECORDED', self._inspect()['events'])

    def test_modified_single_column_root_refused_and_downgraded(self):
        self._append()
        # Copy valid evidence bytes to a separate root; changing one column
        # must not move the claimed evidence root.
        shutil.rmtree(self.b)
        shutil.copytree(self.a, self.b)
        with sqlite3.connect(self.db) as db:
            db.execute('UPDATE consumptions SET evidence_root=?', (str(self.b),))
        with self.assertRaises(ValueError):
            self._observe()
        self.assertNotIn('LOCAL_EVIDENCE_RECORDED', self._inspect()['events'])

    def test_modified_root_after_commit_not_considered_verified(self):
        self._append()
        self._observe()
        shutil.rmtree(self.b)
        shutil.copytree(self.a, self.b)
        with sqlite3.connect(self.db) as db:
            db.execute('UPDATE consumptions SET evidence_root=?', (str(self.b),))
        self.assertEqual(self._inspect()['observation_status'], 'UNKNOWN_LOCAL_EVIDENCE_NOT_REVALIDATED')

    def test_v8_schema_not_silently_migrated(self):
        with sqlite3.connect(self.db) as db:
            db.execute('PRAGMA user_version=8')
        with self.assertRaisesRegex(ValueError, 'COORDINATOR_SCHEMA_VERSION_MISMATCH'):
            self._inspect()

    def test_raw_events_without_observation_remain_unverified(self):
        self._append()
        self.assertEqual(self._inspect()['observation_status'], 'NOT_RECORDED')
        self.assertEqual(self._inspect()['merge_authorization'], 'NOT_GRANTED')

    def test_mutated_both_database_binding_and_files_same_owner_unresolved(self):
        """Not a security claim: same owner can replace BOTH SQLite values."""
        self._append()
        shutil.rmtree(self.b)
        shutil.copytree(self.a, self.b)
        with sqlite3.connect(self.db) as db:
            db.execute('UPDATE consumptions SET evidence_root=?', (str(self.b),))
            db.execute('UPDATE root_bindings SET evidence_root_sha256=?', (r2a0.digest(str(self.b).encode()),))
        self._observe()  # intentionally demonstrates lack of independent custody
        self.assertEqual(self._inspect()['observation_status'], 'CURRENT_LOCAL_READBACK_MATCH_NOT_INDEPENDENT')
        self.assertEqual(self._inspect()['independent_custody'], 'NOT_ESTABLISHED')
