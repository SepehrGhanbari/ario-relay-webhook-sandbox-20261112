"""F11: coordinator observation must not claim evidence without F10 consumption AND local journal readback."""
import unittest
from test_f10_atomic_single_use import _NoNetwork
from test_f7_coordinator import INTENT
import f7_coordinator as f7
import r2a0

class TestF11Observation(_NoNetwork):
    def observe(self):
        return self.coord.record_local_observation(INTENT,self.marker,"SAME_LABEL")
    def events(self):
        return self.coord.inspect(INTENT["repo"],INTENT["pr"])["events"]
    def test_claim_only_denied(self):
        with self.assertRaises(ValueError):self.observe()
        self.assertEqual(self.events(),["CLAIMED"])
    def test_consumed_but_no_journal_denied(self):
        f7.consume_intent_authority(self._authority(),self.raw,str(self.a))
        with self.assertRaises(ValueError):self.observe()
        self.assertEqual(self.events(),["CLAIMED","AUTHORITY_CONSUMED"])
    def test_private_raw_write_without_consumption_denied(self):
        r2a0.EvidenceJournal(self.a)._append_merge_intent_raw(self.raw)
        with self.assertRaises(ValueError):self.observe()
        self.assertEqual(self.events(),["CLAIMED"])
    def test_mismatched_consumed_evidence_root_denied(self):
        f7.consume_intent_authority(self._authority(),self.raw,str(self.b))
        r2a0.EvidenceJournal(self.a)._append_merge_intent_raw(self.raw)
        with self.assertRaises(ValueError):self.observe()
        self.assertEqual(self.events(),["CLAIMED","AUTHORITY_CONSUMED"])
    def test_tampered_journal_denied(self):
        r2a0.EvidenceJournal(self.a).append('merge-intent','local',self.raw,merge_intent_authority=self._authority())
        next((self.a/'objects').glob('*')).write_bytes(b'corrupt')
        with self.assertRaises(ValueError):self.observe()
        self.assertEqual(self.events(),["CLAIMED","AUTHORITY_CONSUMED"])
    def test_valid_consumed_intent_local_readback_records_but_not_admission(self):
        r2a0.EvidenceJournal(self.a).append('merge-intent','local',self.raw,merge_intent_authority=self._authority())
        self.observe()
        state=self.coord.inspect(INTENT["repo"],INTENT["pr"])
        self.assertEqual(state['events'],['CLAIMED','AUTHORITY_CONSUMED','LOCAL_EVIDENCE_RECORDED'])
        self.assertEqual(state['merge_authorization'],'NOT_GRANTED')
        self.assertEqual(state['independent_custody'],'NOT_ESTABLISHED')
    def test_second_observation_denied(self):
        r2a0.EvidenceJournal(self.a).append('merge-intent','local',self.raw,merge_intent_authority=self._authority())
        self.observe()
        with self.assertRaises(ValueError):self.observe()
