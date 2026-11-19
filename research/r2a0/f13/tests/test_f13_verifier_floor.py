"""F13: falsification-oriented local checkpoint retention, no merge authority."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_f10_atomic_single_use import _NoNetwork
from test_f7_coordinator import INTENT
import f13_verifier_floor as f13
import f7_coordinator as f7
import r2a0


class TestF13VerifierFloor(_NoNetwork):
    def setUp(self):
        super().setUp()
        self.floor_dir=self.base/'separately-retained-by-verifier'
        self.floor_dir.mkdir()
        self.floor=f13.VerifierFloor(self.floor_dir)

    def _observed(self):
        r2a0.EvidenceJournal(self.a).append('merge-intent','local',self.raw,merge_intent_authority=self._authority())
        self.coord.record_local_observation(INTENT,self.marker,'SAME_LABEL')

    def test_missing_floor_cannot_be_read_as_authority(self):
        self._observed()
        self.assertEqual(self.floor.check(self.db,INTENT['repo'],INTENT['pr'])['reason'],'VERIFIER_FLOOR_MISSING_OR_UNSAFE')

    def test_pin_and_fresh_check_preserve_no_authority(self):
        self._observed()
        pin=self.floor.pin(self.db,INTENT['repo'],INTENT['pr'])
        self.assertTrue(pin['pinned'])
        out=self.floor.check(self.db,INTENT['repo'],INTENT['pr'])
        self.assertTrue(out['matched'])
        self.assertEqual(out['merge_authorization'],'NOT_GRANTED')
        self.assertEqual(out['independent_custody'],'NOT_ESTABLISHED')

    def test_missing_publisher_evidence_fails_and_pin_remains(self):
        self._observed()
        self.floor.pin(self.db,INTENT['repo'],INTENT['pr'])
        (self.a/'journal.jsonl').unlink()
        self.assertEqual(self.floor.check(self.db,INTENT['repo'],INTENT['pr'])['reason'],'VERIFIER_OR_PUBLISHER_UNREADABLE')
        self.assertEqual(len(list(self.floor_dir.glob('*.json'))),1)

    def test_retained_floor_detects_publisher_rollback_to_pre_observation(self):
        # Baseline publisher DB from just after CLAIMED, before consumption.
        import shutil
        before=self.base/'before.sqlite'
        with sqlite3.connect(self.db) as s, sqlite3.connect(before) as d:
            s.backup(d)
        self._observed()
        self.floor.pin(self.db,INTENT['repo'],INTENT['pr'])
        # Same-owner restores publisher DB while separately-retained floor survives.
        with sqlite3.connect(before) as s, sqlite3.connect(self.db) as d:
            s.backup(d)
        self.assertEqual(self.floor.check(self.db,INTENT['repo'],INTENT['pr'])['reason'],'VERIFIER_OR_PUBLISHER_UNREADABLE')
        self.assertEqual(len(list(self.floor_dir.glob('*.json'))),1)

    def test_coherent_publisher_root_move_looks_valid_locally_but_floor_rejects(self):
        """Key falsifier: F12 alone MATCHes coherent DB+root substitution.

        The separately retained F13 pin detects it ONLY while the second
        floor remains unchanged. This is not resistance to a full same-owner
        compromise of the publisher *and* verifier stores.
        """
        import shutil
        self._observed()
        self.floor.pin(self.db,INTENT['repo'],INTENT['pr'])
        shutil.rmtree(self.b)
        shutil.copytree(self.a,self.b)
        new_sha=r2a0.digest(str(self.b).encode('utf-8'))
        with sqlite3.connect(self.db) as db:
            db.execute('UPDATE consumptions SET evidence_root=?',(str(self.b),))
            db.execute('UPDATE root_bindings SET evidence_root_sha256=?',(new_sha,))
            db.execute('UPDATE observation_snapshots SET evidence_root_sha256=?',(new_sha,))
        self.assertEqual(self.coord.inspect(INTENT['repo'],INTENT['pr'])['observation_status'],
                         'CURRENT_LOCAL_READBACK_MATCH_NOT_INDEPENDENT')
        self.assertEqual(self.floor.check(self.db,INTENT['repo'],INTENT['pr'])['reason'],
                         'PUBLISHER_DIFFERS_FROM_RETAINED_CHECKPOINT')

    def test_source_changes_after_pin_write_is_hold_not_success(self):
        self._observed()
        def destroy():
            (self.a/'journal.jsonl').unlink()
        result=self.floor.pin(self.db,INTENT['repo'],INTENT['pr'],after_pin=destroy)
        self.assertEqual(result['reason'],'PUBLISHER_CHANGED_DURING_PIN_PIN_RETAINED')
        self.assertEqual(len(list(self.floor_dir.glob('*.json'))),1)
        self.assertEqual(self.floor.check(self.db,INTENT['repo'],INTENT['pr'])['status'],'HOLD')

    def test_same_subject_cannot_overwrite_floor(self):
        self._observed()
        self.floor.pin(self.db,INTENT['repo'],INTENT['pr'])
        self.assertEqual(self.floor.pin(self.db,INTENT['repo'],INTENT['pr'])['reason'],'VERIFIER_FLOOR_ALREADY_PINNED')

    def test_tampered_floor_is_not_claimed_valid(self):
        self._observed()
        self.floor.pin(self.db,INTENT['repo'],INTENT['pr'])
        p=next(self.floor_dir.glob('*.json'))
        p.write_bytes(p.read_bytes()+b'X')
        self.assertEqual(self.floor.check(self.db,INTENT['repo'],INTENT['pr'])['status'],'HOLD')
        self.assertNotEqual(self.floor.check(self.db,INTENT['repo'],INTENT['pr']).get('matched'),True)

    def test_verifier_floor_directory_symlink_rejected(self):
        self._observed()
        sym=self.base/'alias'
        try:
            sym.symlink_to(self.floor_dir,target_is_directory=True)
        except (OSError,NotImplementedError):
            self.skipTest('symlinks unavailable')
        with self.assertRaises(ValueError):
            f13.VerifierFloor(sym).pin(self.db,INTENT['repo'],INTENT['pr'])

    def test_malformed_publisher_state_does_not_create_floor(self):
        with self.assertRaises(ValueError):
            self.floor.pin(self.db,INTENT['repo'],INTENT['pr'])
        self.assertEqual(list(self.floor_dir.glob('*')),[])

    def test_two_process_pins_one_subject_only_one_success(self):
        self._observed()
        code='''import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import f13_verifier_floor as f13
r=f13.VerifierFloor(Path(sys.argv[2])).pin(Path(sys.argv[3]),sys.argv[4],int(sys.argv[5]))
print(json.dumps(r))'''
        cmd=[sys.executable,'-c',code,str(Path(__file__).resolve().parents[1]),str(self.floor_dir),str(self.db),INTENT['repo'],str(INTENT['pr'])]
        a=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        b=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        x,e=a.communicate(timeout=20);y,f=b.communicate(timeout=20)
        self.assertEqual(a.returncode,0,e);self.assertEqual(b.returncode,0,f)
        self.assertEqual(sum(bool(json.loads(z).get('pinned')) for z in (x,y)),1)
        self.assertEqual(len(list(self.floor_dir.glob('*.json'))),1)

    def test_unavailable_floor_directory_fails_closed(self):
        self._observed()
        with self.assertRaises(ValueError):
            f13.VerifierFloor(self.base/'absent').pin(self.db,INTENT['repo'],INTENT['pr'])

    def test_crash_after_exclusive_floor_creation_is_hold_not_repin(self):
        self._observed()
        code = """import os,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,sys.argv[1])
import f13_verifier_floor as f13
with patch.object(f13.os,'fdopen',side_effect=lambda *a,**k: os._exit(97)):
 f13.VerifierFloor(Path(sys.argv[2])).pin(Path(sys.argv[3]),sys.argv[4],int(sys.argv[5]))"""
        run=subprocess.run([sys.executable,'-c',code,str(Path(__file__).resolve().parents[1]),str(self.floor_dir),str(self.db),INTENT['repo'],str(INTENT['pr'])],capture_output=True,text=True,timeout=20)
        self.assertEqual(run.returncode,97,run.stderr)
        self.assertEqual(len(list(self.floor_dir.glob('*.json'))),1)
        self.assertEqual(self.floor.check(self.db,INTENT['repo'],INTENT['pr'])['status'],'HOLD')
        self.assertEqual(self.floor.pin(self.db,INTENT['repo'],INTENT['pr'])['reason'],'VERIFIER_FLOOR_ALREADY_PINNED')

    def test_same_owner_mutability_explicit_limit(self):
        self._observed()
        self.floor.pin(self.db,INTENT['repo'],INTENT['pr'])
        # An owner who can DELETE the pin can erase the verification floor.
        next(self.floor_dir.glob('*.json')).unlink()
        self.assertEqual(self.floor.check(self.db,INTENT['repo'],INTENT['pr'])['reason'],'VERIFIER_FLOOR_MISSING_OR_UNSAFE')
        self.assertEqual(self.floor.check(self.db,INTENT['repo'],INTENT['pr'])['independent_custody'],'NOT_ESTABLISHED')
