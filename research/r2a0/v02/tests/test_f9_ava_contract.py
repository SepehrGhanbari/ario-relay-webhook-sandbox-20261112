"""F9 Ava reconstruction: supported-path authority only. Never contact GitHub."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import r2a0
import f7_coordinator as f7

INTENT = {'repo':r2a0.LAB_REPO,'pr':52,'head':'a'*40,'base':'experiment/r2a0-f9','scenario':'Sc1'}
ACK_ENV = {'ARIO_R2A0_DISPOSABLE_MERGE_ACK':'EXPLICITLY_ALLOW_LAB_MERGE'}

class TestF9Authority(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.db=self.base/'coordinator'/'claims.sqlite'
        self.coord=f7.SharedCoordinator.initialize(self.db)
        self.a=self.base/'A'; self.b=self.base/'B'
        self.raw=r2a0.canonical(INTENT)
        self.marker=r2a0.digest(self.raw)

    def args(self,root,db=None,label=None):
        args=['attempt-merge','--pr',str(INTENT['pr']),'--scenario','Sc1','--base',INTENT['base'],
              '--expected-head',INTENT['head'],'--evidence-dir',str(root),'--execute']
        if db is not None:args+=['--db',str(db)]
        if label is not None:args+=['--root-label',label]
        return args

    def test_missing_coordinator_refuses_before_marker_journal_network(self):
        with patch.dict(os.environ, ACK_ENV), patch.object(r2a0,'authorized_merge',side_effect=AssertionError('NO_NETWORK')):
            self.assertEqual(r2a0.main(self.args(self.a)),2)
        self.assertFalse((self.a/'merge_intents').exists())
        self.assertFalse(self.coord.inspect(INTENT['repo'],INTENT['pr'])['claim_exists'])

    def test_two_roots_one_shared_coordinator_only_first_calls_mocked_merge(self):
        with patch.dict(os.environ, ACK_ENV), patch.object(r2a0,'authorized_merge',return_value={'_request_ok':False,'_error':'MOCKED'}) as merge:
            first=r2a0.main(self.args(self.a,self.db,'A'))
            second=r2a0.main(self.args(self.b,self.db,'B'))
        self.assertEqual(first,0)
        self.assertEqual(second,2)
        merge.assert_called_once()
        self.assertEqual(len(list((self.a/'merge_intents').glob('*.json'))),1)
        self.assertFalse((self.b/'merge_intents').exists())
        self.assertEqual(len([r for r in r2a0.EvidenceJournal(self.a).read() if r['event']=='merge-intent']),1)

    def test_generic_public_sink_must_not_self_authorize(self):
        r2a0.write_once(self.a/'merge_intents'/(self.marker+'.json'),self.raw)
        with self.assertRaises(PermissionError):
            r2a0.EvidenceJournal(self.a).append('merge-intent','local',self.raw)
        self.assertEqual(r2a0.inspect_merge_recovery(r2a0.EvidenceJournal(self.a))['journal_integrity'],'HOLD_ORPHAN_INTENT')

    def test_forged_authority_rejected(self):
        r2a0.write_once(self.a/'merge_intents'/(self.marker+'.json'),self.raw)
        with self.assertRaises((PermissionError,ValueError,TypeError,AttributeError)):
            r2a0.EvidenceJournal(self.a).append('merge-intent','local',self.raw,merge_intent_authority=object())

    def test_missing_db_refuses_without_creating(self):
        missing=self.base/'missing.sqlite'
        with patch.dict(os.environ, ACK_ENV), patch.object(r2a0,'authorized_merge',side_effect=AssertionError('NO_NETWORK')):
            self.assertEqual(r2a0.main(self.args(self.a,missing,'A')),2)
        self.assertFalse(missing.exists())
        self.assertFalse((self.a/'merge_intents').exists())

    def test_crash_after_claim_before_marker_keeps_claim_holds(self):
        with patch.dict(os.environ, ACK_ENV), patch.object(r2a0,'write_once',side_effect=OSError('INJECTED_LOCAL_CRASH')), patch.object(r2a0,'authorized_merge',side_effect=AssertionError('NO_NETWORK')):
            self.assertEqual(r2a0.main(self.args(self.a,self.db,'A')),2)
        self.assertTrue(self.coord.inspect(INTENT['repo'],INTENT['pr'])['claim_exists'])
        self.assertFalse((self.a/'merge_intents').exists())
        with patch.dict(os.environ, ACK_ENV), patch.object(r2a0,'authorized_merge',side_effect=AssertionError('NO_NETWORK')):
            self.assertEqual(r2a0.main(self.args(self.b,self.db,'B')),2)
        self.assertFalse((self.b/'merge_intents').exists())

    def test_existing_manual_evidence_unaffected(self):
        j=r2a0.EvidenceJournal(self.a)
        j.append('manual','operator-supplied',b'hello')
        self.assertEqual(j.read()[0]['event'],'manual')

if __name__ == '__main__':unittest.main()
