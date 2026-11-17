"""F6 falsifier: independent roots have no shared exclusion authority.

All remote mutation is forbidden. These are laboratory observations, not
live GitHub merge attempts or proof of two physical storage devices.
"""
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import r2a0
from f6_compare import compare

INTENT = {
    'repo': r2a0.LAB_REPO,
    'pr': 22,
    'head': 'a' * 40,
    'base': 'experiment/r2a0-f6',
    'scenario': 'Sc1',
}


def write_fixture(root: Path, label: str, intent: dict = INTENT) -> str:
    root.mkdir(parents=True, exist_ok=True)
    journal = r2a0.EvidenceJournal(root)
    journal.append('manual', 'operator-supplied', r2a0.canonical({'origin': label}), {'label': label})
    raw = r2a0.canonical(intent)
    r2a0.write_once(root / 'merge_intents' / (r2a0.digest(raw) + '.json'), raw)
    return r2a0.digest(raw)


def snapshot(root: Path) -> dict:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


WORKER = r'''
import json, os, sys, time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
import r2a0
root, marker, ready, go = map(Path, sys.argv[2:6])
ready.write_text('ready')
deadline=time.monotonic()+15
while not go.exists() and time.monotonic()<deadline: time.sleep(.003)
if not go.exists(): sys.exit(8)
with patch.object(r2a0, 'gh_api', side_effect=AssertionError('NO_REMOTE_CALL_ALLOWED')):
    try:
        result=r2a0.adopt_single_orphan_intent(r2a0.EvidenceJournal(root), str(marker), ack='RECORD_ORPHAN_ONLY_NO_MERGE_RETRY')
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({'status':'HOLD','error':str(e)}))
        sys.exit(2)
'''


class TestF6SeparateRoots(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.left = self.base / 'left'
        self.right = self.base / 'right'

    def race(self, left, right):
        raw = r2a0.canonical(INTENT)
        marker = r2a0.digest(raw)
        module_dir = str(Path(r2a0.__file__).resolve().parent)
        go = self.base / 'GO'
        ready = [self.base / f'READY-{i}' for i in range(2)]
        proc = [subprocess.Popen([sys.executable, '-c', WORKER, module_dir, str(root), marker,
                                  str(ready[i]), str(go)], stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
                for i, root in enumerate((left, right))]
        try:
            deadline = time.monotonic()+15
            while not all(p.exists() for p in ready) and time.monotonic()<deadline:
                time.sleep(.005)
            self.assertTrue(all(p.exists() for p in ready), 'worker rendezvous timeout')
            go.write_text('GO')
            results=[]
            for p in proc:
                stdout, stderr = p.communicate(timeout=20)
                self.assertEqual(p.returncode, 0, (stdout, stderr))
                results.append(json.loads(stdout))
            return results
        finally:
            for p in proc:
                if p.poll() is None: p.kill()
                p.communicate()

    def test_two_processes_accept_same_intent_in_separate_roots(self):
        left_marker = write_fixture(self.left, 'disk-A')
        right_marker = write_fixture(self.right, 'disk-B')
        self.assertEqual(left_marker, right_marker)
        result = self.race(self.left, self.right)
        self.assertEqual([x['action'] for x in result], ['APPENDED_RECOVERY_EVIDENCE_ONLY'] * 2)
        for root in (self.left, self.right):
            j=r2a0.EvidenceJournal(root)
            self.assertEqual(len(j.read()), 2)
            state=r2a0.inspect_merge_recovery(j)
            self.assertEqual(state['status'], 'HOLD')
            self.assertEqual(state['remote_merge_retry'], 'FORBIDDEN')
        comparison=compare(self.left,self.right)
        self.assertEqual(comparison['status'],'HOLD_DUPLICATE_INTENT_ACROSS_ROOTS')
        self.assertEqual(comparison['same_intent_markers'][0]['marker_sha256'],left_marker)
        self.assertNotEqual(comparison['left']['last_hash'],comparison['right']['last_hash'])

    def test_read_only_comparison_no_mutations_and_no_success_status(self):
        write_fixture(self.left, 'disk-A')
        write_fixture(self.right, 'disk-B')
        self.race(self.left,self.right)
        before=(snapshot(self.left),snapshot(self.right))
        with patch.object(r2a0,'gh_api', side_effect=AssertionError('remote call')):
            r=compare(self.left,self.right)
        self.assertEqual(r['remote_merge_retry'],'FORBIDDEN')
        self.assertEqual(r['merge_authorization'],'NOT_GRANTED')
        self.assertEqual((snapshot(self.left),snapshot(self.right)),before)

    def test_distinct_nonoverlapping_intents_are_unknown_not_global_pass(self):
        write_fixture(self.left,'left-only')
        different=dict(INTENT, head='b'*40)
        write_fixture(self.right,'right-only',different)
        left_marker=r2a0.digest(r2a0.canonical(INTENT))
        right_marker=r2a0.digest(r2a0.canonical(different))
        for root,marker in ((self.left,left_marker),(self.right,right_marker)):
            r2a0.adopt_single_orphan_intent(r2a0.EvidenceJournal(root),marker,ack='RECORD_ORPHAN_ONLY_NO_MERGE_RETRY')
        c=compare(self.left,self.right)
        self.assertEqual(c['status'],'UNKNOWN_NO_DUPLICATE_IN_TWO_OBSERVED_ROOTS')
        self.assertEqual(c['root_set_completeness'],'UNKNOWN')

    def test_corrupt_or_missing_root_refuses_comparison(self):
        write_fixture(self.left,'left')
        write_fixture(self.right,'right')
        r2a0.adopt_single_orphan_intent(r2a0.EvidenceJournal(self.left),r2a0.digest(r2a0.canonical(INTENT)),ack='RECORD_ORPHAN_ONLY_NO_MERGE_RETRY')
        r2a0.adopt_single_orphan_intent(r2a0.EvidenceJournal(self.right),r2a0.digest(r2a0.canonical(INTENT)),ack='RECORD_ORPHAN_ONLY_NO_MERGE_RETRY')
        (self.right / 'journal.jsonl').write_bytes(b'tampered\n')
        self.assertEqual(compare(self.left,self.right)['status'],'HOLD_ROOT_INSPECTION_FAILED')
        self.assertEqual(compare(self.left,self.base / 'missing')['status'],'HOLD_ROOT_INSPECTION_FAILED')

    def test_orphan_on_one_side_forces_hold_without_repairs(self):
        write_fixture(self.left,'left')
        write_fixture(self.right,'right')
        r2a0.adopt_single_orphan_intent(r2a0.EvidenceJournal(self.left),r2a0.digest(r2a0.canonical(INTENT)),ack='RECORD_ORPHAN_ONLY_NO_MERGE_RETRY')
        before=(snapshot(self.left),snapshot(self.right))
        report=compare(self.left,self.right)
        self.assertEqual(report['status'],'HOLD_ROOT_INSPECTION_FAILED')
        self.assertEqual((snapshot(self.left),snapshot(self.right)),before)

    def test_cloned_backup_can_look_like_duplicate_intent(self):
        write_fixture(self.left,'one-origin')
        r2a0.adopt_single_orphan_intent(r2a0.EvidenceJournal(self.left),r2a0.digest(r2a0.canonical(INTENT)),ack='RECORD_ORPHAN_ONLY_NO_MERGE_RETRY')
        shutil.copytree(self.left,self.right)
        report=compare(self.left,self.right)
        self.assertEqual(report['status'],'HOLD_DUPLICATE_INTENT_ACROSS_ROOTS')
        self.assertTrue(report['potential_backup_copy'])
        self.assertEqual(report['left']['last_hash'],report['right']['last_hash'])
        self.assertFalse(report['merge_authorization']=='GRANTED')

    def test_same_root_or_symlink_cannot_pretend_independence(self):
        write_fixture(self.left,'left')
        self.assertEqual(compare(self.left,self.left)['status'],'HOLD_ROOT_INSPECTION_FAILED')
        link=self.base / 'link'
        try: link.symlink_to(self.left, target_is_directory=True)
        except (OSError, NotImplementedError): self.skipTest('symlinks unavailable')
        self.assertEqual(compare(self.left,link)['status'],'HOLD_ROOT_INSPECTION_FAILED')

    @unittest.skipUnless(os.name == 'posix' and Path('/dev/shm').is_dir(), 'distinct filesystem fixture unavailable')
    def test_two_distinct_filesystem_mounts_can_adopt_the_same_intent(self):
        with tempfile.TemporaryDirectory(dir='/dev/shm') as other:
            external=Path(other)
            if external.stat().st_dev == self.left.parent.stat().st_dev:
                self.skipTest('not distinct st_dev')
            write_fixture(self.left,'overlay-root')
            write_fixture(external,'tmpfs-root')
            res=self.race(self.left,external)
            self.assertEqual([r['action'] for r in res],['APPENDED_RECOVERY_EVIDENCE_ONLY']*2)
            c=compare(self.left,external)
            self.assertEqual(c['status'],'HOLD_DUPLICATE_INTENT_ACROSS_ROOTS')
            self.assertTrue(c['distinct_filesystem_devices'])


if __name__ == '__main__':
    unittest.main()
