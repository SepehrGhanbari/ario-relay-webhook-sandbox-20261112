"""F8 contract tests: public recovery entry points must require shared coordination.

Research only: this does NOT defend against arbitrary Python execution,
DB forking, owners, hosts or missing genuine independent custody.
"""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import r2a0
import f7_coordinator as f7
from test_f7_coordinator import fixture, INTENT, tree_hash

class TestF8MandatoryPublicEntry(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.a=self.base/'rootA'
        self.b=self.base/'rootB'
        self.db=self.base/'authority'/'claims.sqlite'
        self.coord=f7.SharedCoordinator.initialize(self.db)
        self.marker=fixture(self.a, origin='a')

    def test_f8_public_api_without_coordinator_denied_no_write(self):
        before=tree_hash(self.a)
        with patch.object(r2a0,'gh_api',side_effect=AssertionError('no network')):
            with self.assertRaisesRegex(PermissionError,'COORDINATOR_REQUIRED'):
                r2a0.adopt_single_orphan_intent(r2a0.EvidenceJournal(self.a),self.marker,ack=f7.ACK)
        self.assertEqual(tree_hash(self.a),before)
        self.assertFalse(self.coord.inspect(INTENT['repo'],INTENT['pr'])['claim_exists'])

    def test_f8_public_api_with_coordinator_records_only_once(self):
        fixture(self.b, origin='b')
        with patch.object(r2a0,'gh_api',side_effect=AssertionError('no network')):
            first=r2a0.adopt_single_orphan_intent(r2a0.EvidenceJournal(self.a), self.marker,ack=f7.ACK,
                                                coordinator=self.coord,root_label='A')
            second=r2a0.adopt_single_orphan_intent(r2a0.EvidenceJournal(self.b), self.marker,ack=f7.ACK,
                                                 coordinator=self.coord,root_label='B')
        self.assertEqual(first['reason'],'LOCAL_RECOVERY_RECORDED_GLOBAL_CLAIM_HELD_NO_MERGE_RETRY')
        self.assertEqual(second['reason'],'GLOBAL_INTENT_ALREADY_CLAIMED')
        self.assertEqual(len(r2a0.EvidenceJournal(self.a).read()),2)
        self.assertEqual(r2a0.inspect_merge_recovery(r2a0.EvidenceJournal(self.b))['journal_integrity'],'HOLD_ORPHAN_INTENT')

    def test_f8_missing_coordinator_db_holds_without_creating(self):
        missing=self.base/'missing'/'authority.sqlite'
        with self.assertRaises(ValueError):
            r2a0.adopt_single_orphan_intent(r2a0.EvidenceJournal(self.a),self.marker,ack=f7.ACK,
                                            coordinator=f7.SharedCoordinator(missing),root_label='A')
        self.assertFalse(missing.exists())
        self.assertEqual(r2a0.inspect_merge_recovery(r2a0.EvidenceJournal(self.a))['journal_integrity'],'HOLD_ORPHAN_INTENT')

    def test_f8_old_cli_without_db_refuses_without_writing(self):
        before=tree_hash(self.a)
        proc=subprocess.run([sys.executable,str(Path(r2a0.__file__).resolve()),'record-orphan',
                             '--evidence-dir',str(self.a),'--marker-sha256',self.marker,'--ack',f7.ACK],
                            capture_output=True,text=True,timeout=15)
        self.assertNotEqual(proc.returncode,0)
        self.assertEqual(tree_hash(self.a),before)
        self.assertFalse(self.coord.inspect(INTENT['repo'],INTENT['pr'])['claim_exists'])

    def test_f8_public_cli_and_f7_cli_share_single_authority(self):
        fixture(self.b,origin='b')
        c1=subprocess.run([sys.executable,str(Path(r2a0.__file__).resolve()),'record-orphan',
            '--evidence-dir',str(self.a),'--marker-sha256',self.marker,'--ack',f7.ACK,
            '--db',str(self.db),'--root-label','A'],capture_output=True,text=True,timeout=15)
        self.assertEqual(c1.returncode,2, (c1.stdout,c1.stderr)) # recovery status is HOLD, never a PASS
        self.assertEqual(json.loads(c1.stdout)['reason'],'LOCAL_RECOVERY_RECORDED_GLOBAL_CLAIM_HELD_NO_MERGE_RETRY')
        c2=subprocess.run([sys.executable,str(Path(f7.__file__).resolve()),'adopt',
            '--evidence-dir',str(self.b),'--marker',self.marker,'--ack',f7.ACK,
            '--db',str(self.db),'--root-label','B'],capture_output=True,text=True,timeout=15)
        self.assertEqual(c2.returncode,2,(c2.stdout,c2.stderr))
        self.assertEqual(json.loads(c2.stdout)['reason'],'GLOBAL_INTENT_ALREADY_CLAIMED')
        self.assertEqual(len(r2a0.EvidenceJournal(self.a).read()),2)
        self.assertEqual(r2a0.inspect_merge_recovery(r2a0.EvidenceJournal(self.b))['journal_integrity'],'HOLD_ORPHAN_INTENT')

    def test_f8_two_public_cli_processes_race_one_authority(self):
        """Independent CLI processes, not direct F7 adapter calls."""
        import time
        fixture(self.b,origin='b')
        gate=self.base/'go'
        workers=[]
        script=r"""
import json,sys,time
from pathlib import Path
import r2a0
root,db,marker,label,ready,go=sys.argv[1:7]
Path(ready).write_text('READY')
stop=time.monotonic()+12
while not Path(go).exists() and time.monotonic()<stop:time.sleep(.003)
if not Path(go).exists():raise SystemExit(9)
r2a0.main(['record-orphan','--evidence-dir',root,'--marker-sha256',marker,
    '--ack','RECORD_ORPHAN_ONLY_NO_MERGE_RETRY','--db',db,'--root-label',label])
"""
        gofiles=[self.base/'one.ready',self.base/'two.ready']
        env=dict(os.environ,PYTHONPATH=str(Path(r2a0.__file__).resolve().parent))
        try:
            for root,label,ready in ((self.a,'A',gofiles[0]),(self.b,'B',gofiles[1])):
                workers.append(subprocess.Popen([sys.executable,'-c',script,str(root),str(self.db),self.marker,label,
                    str(ready),str(gate)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env))
            stop=__import__('time').monotonic()+12
            while not all(q.exists() for q in gofiles):
                self.assertLess(__import__('time').monotonic(),stop)
                __import__('time').sleep(.01)
            gate.write_text('GO')
            values=[]
            for worker in workers:
                out,err=worker.communicate(timeout=15)
                self.assertEqual(worker.returncode,0,(out,err))
                values.append(json.loads(out))
            reasons={v['reason'] for v in values}
            self.assertEqual(reasons,{'LOCAL_RECOVERY_RECORDED_GLOBAL_CLAIM_HELD_NO_MERGE_RETRY',
                                      'GLOBAL_INTENT_ALREADY_CLAIMED'})
            # Exactly one root has a complete recorded recovery; other stays orphan-HOLD.
            inspection=[r2a0.inspect_merge_recovery(r2a0.EvidenceJournal(r)) for r in (self.a,self.b)]
            self.assertEqual(sum(x['journal_integrity']=='PASS' for x in inspection),1)
            self.assertEqual(sum(x['journal_integrity']=='HOLD_ORPHAN_INTENT' for x in inspection),1)
        finally:
            for worker in workers:
                if worker.poll() is None:worker.kill()
                worker.communicate()

    def test_f8_ack_rejects_even_with_coordinator(self):
        before=tree_hash(self.a)
        with self.assertRaises(PermissionError):
            r2a0.adopt_single_orphan_intent(r2a0.EvidenceJournal(self.a),self.marker,ack='BAD',
                                            coordinator=self.coord,root_label='A')
        self.assertEqual(tree_hash(self.a),before)
        self.assertFalse(self.coord.inspect(INTENT['repo'],INTENT['pr'])['claim_exists'])

    def test_f8_no_fake_public_module_authority_via_legacy_cli(self):
        # Repetition and new HEAD/scenario must never authorize remote PUT.
        with patch.object(r2a0,'authorized_merge',side_effect=AssertionError('PUT called')):
            with self.assertRaises(PermissionError):
                r2a0.adopt_single_orphan_intent(r2a0.EvidenceJournal(self.a),self.marker,ack=f7.ACK)

if __name__=='__main__': unittest.main()
