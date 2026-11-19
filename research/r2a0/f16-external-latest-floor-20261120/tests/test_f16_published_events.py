"""F16 adversarial independent test of the exact Nostr public-event fixture."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from f16_signed_event_verifier import FILE,verify_events,Hold,B

class F16PublishedEventVerifier(unittest.TestCase):
    def setUp(self):
        self.events=copy.deepcopy(json.loads(FILE.read_text())["exact_public_nostr_events"])
    def test_signed_A_B_valid_but_not_custody(self):
        out=verify_events(self.events)
        self.assertEqual(out['latest'],B)
        self.assertEqual(out['independent_latest_floor'],'NOT_ESTABLISHED')
    def test_deleted_latest_B_holds(self):
        with self.assertRaises(Hold):verify_events(self.events[:1])
    def test_duplicate_A_fork_holds(self):
        with self.assertRaises(Hold):verify_events([self.events[0],self.events[0]])
    def test_changed_digest_holds(self):
        self.events[1]['content']=self.events[1]['content'].replace(B,'f'*64)
        with self.assertRaises(Hold):verify_events(self.events)
    def test_forged_pubkey_holds(self):
        self.events[1]['pubkey']='0'*64
        with self.assertRaises(Hold):verify_events(self.events)
    def test_changed_signature_holds(self):
        self.events[0]['sig']='0'*128
        with self.assertRaises(Hold):verify_events(self.events)
    def test_invalid_predecessor_holds(self):
        self.events[1]['content']=self.events[1]['content'].replace(
            '1287f223186e3f71ed5230261d375e8c8070b0eca8384fc30b8de73050b1c5c3','0'*64)
        with self.assertRaises(Hold):verify_events(self.events)

if __name__=='__main__':unittest.main()
