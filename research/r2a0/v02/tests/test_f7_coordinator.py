"""F7: local cross-root shared serialization; never exercise live GitHub.

Tests deliberately contrast a single coordinator file with two separate files.
They do not establish remote/network consensus, independent human custody,
or enforcement against use of the legacy ungated CLI.
"""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import r2a0
import f7_coordinator as f7
from f6_compare import compare

INTENT = {
    'repo': r2a0.LAB_REPO, 'pr': 37,
    'head': 'a' * 40, 'base': 'experiment/r2a0-f7', 'scenario': 'Sc1',
}


def fixture(root, intent=INTENT, origin='first'):
    root.mkdir(parents=True, exist_ok=True)
    journal = r2a0.EvidenceJournal(root)
    journal.append('manual', 'operator-supplied', r2a0.canonical({'origin':origin}), {'origin':origin})
    raw = r2a0.canonical(intent)
    r2a0.write_once(root / 'merge_intents' / (r2a0.digest(raw) + '.json'), raw)
    return r2a0.digest(raw)


def tree_hash(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


WORKER = r'''
import json,os,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import f7_coordinator as f7
import r2a0
root,db,marker,label,ready,go=map(str,sys.argv[2:8])
Path(ready).write_text('ready')
end=time.monotonic()+20
while not Path(go).exists() and time.monotonic()<end: time.sleep(.002)
if not Path(go).exists(): sys.exit(8)
try:
  result=f7.adopt_with_shared_coordinator(r2a0.EvidenceJournal(Path(root)),f7.SharedCoordinator(Path(db)),marker,root_label=label,ack=f7.ACK)
  print(json.dumps(result,sort_keys=True))
except Exception as e:
  print(json.dumps({'status':'HOLD','reason':type(e).__name__,'message':str(e)}))
'''


class TestSharedCoordinator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.one = self.base / 'writer_a'
        self.two = self.base / 'writer_b'
        self.db = self.base / 'authority' / 'claims.db'
        self.coord = f7.SharedCoordinator.initialize(self.db)

    def _two_fixtures(self):
        marker = fixture(self.one, origin='A')
        self.assertEqual(marker, fixture(self.two, origin='B'))
        return marker

    def test_one_root_claims_and_second_is_hold(self):
        marker=self._two_fixtures()
        with patch.object(r2a0,'gh_api',side_effect=AssertionError('NO_REMOTE')):
            a=f7.adopt_with_shared_coordinator(r2a0.EvidenceJournal(self.one),self.coord,marker,root_label='diskA',ack=f7.ACK)
            b=f7.adopt_with_shared_coordinator(r2a0.EvidenceJournal(self.two),self.coord,marker,root_label='diskB',ack=f7.ACK)
        self.assertEqual(a['reason'],'LOCAL_RECOVERY_RECORDED_GLOBAL_CLAIM_HELD_NO_MERGE_RETRY')
        self.assertEqual(b['reason'],'GLOBAL_INTENT_ALREADY_CLAIMED')
        self.assertEqual(len(r2a0.EvidenceJournal(self.one).read()),2)
        self.assertEqual(r2a0.inspect_merge_recovery(r2a0.EvidenceJournal(self.two))['journal_integrity'],'HOLD_ORPHAN_INTENT')
        self.assertEqual(self.coord.inspect(INTENT['repo'],INTENT['pr'])['events'],
                         ['CLAIMED','LOCAL_EVIDENCE_RECORDED','REFUSED_DUPLICATE'])
        self.assertEqual(compare(self.one,self.two)['status'],'HOLD_ROOT_INSPECTION_FAILED')

    def test_two_separate_os_processes_race_for_one_db(self):
        marker=self._two_fixtures()
        go=self.base/'GO'
        ready=[self.base/f'READY{i}' for i in range(2)]
        module_dir=str(Path(f7.__file__).resolve().parent)
        ps=[]
        try:
            for i,(root,label) in enumerate(((self.one,'diskA'),(self.two,'diskB'))):
                ps.append(subprocess.Popen([sys.executable,'-c',WORKER,module_dir,str(root),str(self.db),marker,
                                            label,str(ready[i]),str(go)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True))
            deadline=time.monotonic()+20
            while not all(x.exists() for x in ready) and time.monotonic()<deadline: time.sleep(.003)
            self.assertTrue(all(x.exists() for x in ready))
            go.write_text('GO')
            results=[]
            for p in ps:
                stdout,stderr=p.communicate(timeout=25)
                self.assertEqual(p.returncode,0,(stdout,stderr))
                results.append(json.loads(stdout))
            self.assertEqual(sum(x['reason']=='LOCAL_RECOVERY_RECORDED_GLOBAL_CLAIM_HELD_NO_MERGE_RETRY' for x in results),1)
            self.assertEqual(sum(x['reason']=='GLOBAL_INTENT_ALREADY_CLAIMED' for x in results),1)
            self.assertEqual(sum(len(r2a0.EvidenceJournal(root).read())==2
                                 for root in (self.one,self.two) if not self._has_orphan(root)),1)
            self.assertEqual(self.coord.inspect(INTENT['repo'],INTENT['pr'])['events'].count('CLAIMED'),1)
        finally:
            for p in ps:
                if p.poll() is None: p.kill()
                p.communicate()

    @staticmethod
    def _has_orphan(root):
        return r2a0.inspect_merge_recovery(r2a0.EvidenceJournal(root))['journal_integrity']=='HOLD_ORPHAN_INTENT'

    def test_crash_after_grant_keeps_claim_and_orphan(self):
        marker=self._two_fixtures()
        module_dir=str(Path(f7.__file__).resolve().parent)
        script='''import sys,os
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import f7_coordinator as f7,r2a0
f7.adopt_with_shared_coordinator(r2a0.EvidenceJournal(Path(sys.argv[2])), f7.SharedCoordinator(Path(sys.argv[3])),sys.argv[4],root_label='crashed',ack=f7.ACK,after_claim=lambda:os._exit(73))'''
        p=subprocess.run([sys.executable,'-c',script,module_dir,str(self.one),str(self.db),marker],capture_output=True,text=True,timeout=20)
        self.assertEqual(p.returncode,73,p.stderr)
        self.assertEqual(self.coord.inspect(INTENT['repo'],37)['events'],['CLAIMED'])
        with patch.object(r2a0,'gh_api',side_effect=AssertionError('NO_REMOTE')):
            b=f7.adopt_with_shared_coordinator(r2a0.EvidenceJournal(self.two),self.coord,marker,root_label='diskB',ack=f7.ACK)
        self.assertEqual(b['reason'],'GLOBAL_INTENT_ALREADY_CLAIMED')
        self.assertEqual(self._has_orphan(self.one),True)
        self.assertEqual(self._has_orphan(self.two),True)

    def test_uncommitted_sqlite_write_rolls_back_on_hard_crash(self):
        module_dir=str(Path(f7.__file__).resolve().parent)
        script='''import sqlite3,os,sys
c=sqlite3.connect(sys.argv[1],isolation_level=None)
c.execute('BEGIN IMMEDIATE')
c.execute('INSERT INTO claims VALUES(?,?,?,?)',(sys.argv[2],37,'a'*64,'crashed'))
os._exit(78)'''
        p=subprocess.run([sys.executable,'-c',script,str(self.db),INTENT['repo']],capture_output=True,text=True,timeout=20)
        self.assertEqual(p.returncode,78)
        marker=fixture(self.one)
        result=f7.adopt_with_shared_coordinator(r2a0.EvidenceJournal(self.one),self.coord,marker,root_label='writer',ack=f7.ACK)
        self.assertEqual(result['reason'],'LOCAL_RECOVERY_RECORDED_GLOBAL_CLAIM_HELD_NO_MERGE_RETRY')

    def test_must_not_autocreate_a_missing_coordinator(self):
        marker=fixture(self.one)
        missing=f7.SharedCoordinator(self.base/'absent'/'coord.db')
        before=tree_hash(self.one)
        with self.assertRaises(ValueError):
            f7.adopt_with_shared_coordinator(r2a0.EvidenceJournal(self.one),missing,marker,root_label='A',ack=f7.ACK)
        self.assertEqual(tree_hash(self.one),before)
        self.assertFalse(missing.filename.exists())

    def test_same_pr_changed_head_and_scenario_remain_refused(self):
        m=fixture(self.one)
        self.coord.claim(INTENT,m,'A')
        for kw in (dict(head='b'*40),dict(scenario='Sk'),dict(base='experiment/r2a0-newbase')):
            other=dict(INTENT,**kw)
            result=self.coord.claim(other,r2a0.digest(r2a0.canonical(other)),'B')
            self.assertEqual(result['reason'],'GLOBAL_INTENT_ALREADY_CLAIMED')
            self.assertFalse(result['same_marker'])

    def test_invalid_marker_cannot_poison_global_claim(self):
        bad=dict(INTENT,repo='SepehrGhanbari/Ario')
        with self.assertRaises(ValueError):self.coord.claim(bad,r2a0.digest(r2a0.canonical(bad)),'A')
        with self.assertRaises(ValueError):self.coord.claim(INTENT,'a'*64,'A')
        with self.assertRaises(ValueError):self.coord.claim(INTENT,r2a0.digest(r2a0.canonical(INTENT)),'../BAD')
        self.assertFalse(self.coord.inspect(INTENT['repo'],37)['claim_exists'])

    def test_bad_ack_does_not_claim(self):
        marker=fixture(self.one)
        with self.assertRaises(PermissionError):
            f7.adopt_with_shared_coordinator(r2a0.EvidenceJournal(self.one),self.coord,marker,root_label='A',ack='INVALID')
        self.assertFalse(self.coord.inspect(INTENT['repo'],37)['claim_exists'])

    def test_invalid_local_orphan_does_not_consume_global_claim(self):
        marker=fixture(self.one)
        (self.one/'merge_intents'/(marker+'.json')).write_text('corrupt')
        with self.assertRaises(ValueError):
            f7.adopt_with_shared_coordinator(r2a0.EvidenceJournal(self.one),self.coord,marker,root_label='A',ack=f7.ACK)
        self.assertFalse(self.coord.inspect(INTENT['repo'],37)['claim_exists'])

    def test_missing_or_bad_database_schema_fails_closed(self):
        marker=fixture(self.one)
        self.db.write_bytes(b'not-a-sqlite-database')
        with self.assertRaises((ValueError,sqlite3.DatabaseError)):
            f7.adopt_with_shared_coordinator(r2a0.EvidenceJournal(self.one),self.coord,marker,root_label='A',ack=f7.ACK)
        self.assertTrue(self._has_orphan(self.one))

    def test_lock_contention_does_not_admit(self):
        marker=fixture(self.one)
        lock=sqlite3.connect(self.db,isolation_level=None)
        lock.execute('BEGIN EXCLUSIVE')
        try:
            with self.assertRaises(ValueError):
                f7.adopt_with_shared_coordinator(r2a0.EvidenceJournal(self.one),self.coord,marker,root_label='A',ack=f7.ACK)
        finally:
            lock.rollback(); lock.close()
        self.assertTrue(self._has_orphan(self.one))

    def test_two_separate_coordinator_dbs_both_admit_expected_limit(self):
        marker=self._two_fixtures()
        other=f7.SharedCoordinator.initialize(self.base/'authority2'/'claims.db')
        r1=f7.adopt_with_shared_coordinator(r2a0.EvidenceJournal(self.one),self.coord,marker,root_label='A',ack=f7.ACK)
        r2=f7.adopt_with_shared_coordinator(r2a0.EvidenceJournal(self.two),other,marker,root_label='B',ack=f7.ACK)
        self.assertEqual(r1['reason'],r2['reason'])
        self.assertEqual(compare(self.one,self.two)['status'],'HOLD_DUPLICATE_INTENT_ACROSS_ROOTS')

    def test_initialization_does_not_overwrite(self):
        before=self.db.read_bytes()
        with self.assertRaises(FileExistsError):f7.SharedCoordinator.initialize(self.db)
        self.assertEqual(self.db.read_bytes(),before)

    def test_interruption_before_local_record_keeps_global_claim(self):
        marker=fixture(self.one)
        def interrupt():raise RuntimeError('injected after-claim crash-equivalent')
        with self.assertRaisesRegex(RuntimeError,'injected'):
            f7.adopt_with_shared_coordinator(r2a0.EvidenceJournal(self.one),self.coord,marker,root_label='A',ack=f7.ACK,after_claim=interrupt)
        self.assertTrue(self._has_orphan(self.one))
        self.assertEqual(self.coord.inspect(INTENT['repo'],37)['events'],['CLAIMED'])
        result=self.coord.claim(INTENT,marker,'B')
        self.assertEqual(result['reason'],'GLOBAL_INTENT_ALREADY_CLAIMED')

    def test_commit_of_local_record_but_failure_to_observe_keeps_claim(self):
        marker=fixture(self.one)
        with patch.object(self.coord,'record_local_observation',side_effect=RuntimeError('injected outcome unknown')):
            with self.assertRaisesRegex(RuntimeError,'injected'):
                f7.adopt_with_shared_coordinator(r2a0.EvidenceJournal(self.one),self.coord,marker,root_label='A',ack=f7.ACK)
        self.assertEqual(len(r2a0.EvidenceJournal(self.one).read()),2)
        self.assertEqual(self.coord.inspect(INTENT['repo'],37)['events'],['CLAIMED'])
        self.assertEqual(self.coord.claim(INTENT,marker,'A')['reason'],'GLOBAL_INTENT_ALREADY_CLAIMED')

    def test_one_distinct_pr_can_use_one_shared_coordinator(self):
        marker=fixture(self.one)
        first=f7.adopt_with_shared_coordinator(r2a0.EvidenceJournal(self.one),self.coord,marker,root_label='A',ack=f7.ACK)
        self.assertEqual(first['status'],'HOLD')
        new=dict(INTENT,pr=38,head='b'*40)
        marker2=fixture(self.two,new,origin='other-pr')
        second=f7.adopt_with_shared_coordinator(r2a0.EvidenceJournal(self.two),self.coord,marker2,root_label='B',ack=f7.ACK)
        self.assertEqual(second['reason'],'LOCAL_RECOVERY_RECORDED_GLOBAL_CLAIM_HELD_NO_MERGE_RETRY')
        self.assertEqual(self.coord.inspect(INTENT['repo'],38)['events'],['CLAIMED','LOCAL_EVIDENCE_RECORDED'])

    def test_legacy_ungated_recording_still_bypasses_coordinator(self):
        """Negative integration control: F7 is NOT mandatory in the old runtime."""
        marker=self._two_fixtures()
        first=f7.adopt_with_shared_coordinator(r2a0.EvidenceJournal(self.one),self.coord,marker,
                                              root_label='A',ack=f7.ACK)
        self.assertEqual(first['status'],'HOLD')
        legacy=r2a0.adopt_single_orphan_intent(r2a0.EvidenceJournal(self.two),marker,ack=f7.ACK)
        self.assertEqual(legacy['action'],'APPENDED_RECOVERY_EVIDENCE_ONLY')
        self.assertEqual(compare(self.one,self.two)['status'],'HOLD_DUPLICATE_INTENT_ACROSS_ROOTS')

    def test_explicit_ack_required_by_python_api(self):
        marker=fixture(self.one)
        with self.assertRaises(TypeError):
            f7.adopt_with_shared_coordinator(r2a0.EvidenceJournal(self.one),self.coord,marker,root_label='A')
        self.assertFalse(self.coord.inspect(INTENT['repo'],37)['claim_exists'])

    def test_incomplete_coordinator_initialization_does_not_self_repair(self):
        marker=fixture(self.one)
        damaged=self.base/'incomplete.db'
        damaged.write_bytes(b'')
        with self.assertRaises(ValueError):
            f7.adopt_with_shared_coordinator(r2a0.EvidenceJournal(self.one),f7.SharedCoordinator(damaged),marker,
                                             root_label='A',ack=f7.ACK)
        self.assertEqual(damaged.read_bytes(),b'')
        self.assertTrue(self._has_orphan(self.one))

    def test_symlink_coordinator_path_is_hold(self):
        marker=fixture(self.one)
        alias=self.base/'alias.db'
        try: alias.symlink_to(self.db)
        except (OSError,NotImplementedError): self.skipTest('symlink unavailable')
        with self.assertRaises(ValueError):
            f7.adopt_with_shared_coordinator(r2a0.EvidenceJournal(self.one),f7.SharedCoordinator(alias),marker,
                                             root_label='A',ack=f7.ACK)
        self.assertTrue(self._has_orphan(self.one))

    def test_all_coordinator_outcomes_disallow_merge_and_retry(self):
        marker=fixture(self.one)
        cases=[self.coord.claim(INTENT,marker,'A'),self.coord.claim(INTENT,marker,'B'),self.coord.inspect(INTENT['repo'],37)]
        for c in cases:
            self.assertEqual(c['merge_authorization'],'NOT_GRANTED')
            self.assertEqual(c['remote_merge_retry'],'FORBIDDEN')
            self.assertEqual(c['status'],'HOLD')

    @unittest.skipUnless(os.name=='posix' and Path('/dev/shm').is_dir(),'no distinct mount fixture')
    def test_two_separate_mounts_share_one_coordinator_and_one_wins(self):
        with tempfile.TemporaryDirectory(dir='/dev/shm') as d:
            other=Path(d)
            if other.stat().st_dev==self.one.parent.stat().st_dev:
                self.skipTest('not distinct mount')
            marker=fixture(self.one)
            fixture(other,origin='tmpfs')
            a=f7.adopt_with_shared_coordinator(r2a0.EvidenceJournal(self.one),self.coord,marker,root_label='A',ack=f7.ACK)
            b=f7.adopt_with_shared_coordinator(r2a0.EvidenceJournal(other),self.coord,marker,root_label='B',ack=f7.ACK)
            self.assertEqual(a['reason'],'LOCAL_RECOVERY_RECORDED_GLOBAL_CLAIM_HELD_NO_MERGE_RETRY')
            self.assertEqual(b['reason'],'GLOBAL_INTENT_ALREADY_CLAIMED')
            self.assertNotEqual(other.stat().st_dev,self.one.stat().st_dev)

if __name__=='__main__': unittest.main()
