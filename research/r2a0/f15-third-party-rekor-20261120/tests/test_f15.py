"""F15 independent-source contract checks. All cases offline, synthetic only."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import f15_verify as f15

class F15VerifierTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for f in ["reviewer_floor.json", "trusted_root_source_snapshot.json"]:
            shutil.copyfile(ROOT / f, self.root / f)
        for d in ["v1", "v2"]:
            shutil.copytree(ROOT / d, self.root / d)
        self.prev = f15.BUNDLE_ROOT
        f15.BUNDLE_ROOT = self.root
        self.addCleanup(setattr, f15, "BUNDLE_ROOT", self.prev)

    def test_real_proofs_and_log_signature_verify_offline(self):
        with patch.object(f15.urllib.request, "urlopen", side_effect=AssertionError("NO_NETWORK")):
            got = f15.verify_pair()
        self.assertEqual(got["status"], "BOUNDED_PASS")
        self.assertEqual(got["v2"]["checkpoint_signature"], "PASS")
        self.assertFalse(got["trusted_root_tuf_verified"])

    def test_local_payload_tampering_rejected(self):
        with (self.root / "v2/payload.json").open("ab") as out:
            out.write(b"X")
        with self.assertRaises(f15.Hold):
            f15.verify_pair()

    def test_signed_merkle_path_tampering_rejected(self):
        p = self.root / "v2/rekor_response.json"
        j = json.loads(p.read_text())
        j["inclusionProof"]["hashes"][0] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
        p.write_text(json.dumps(j))
        with self.assertRaises(f15.Hold):
            f15.verify_pair()

    def test_log_checkpoint_signature_tampering_rejected(self):
        p = self.root / "v2/rekor_response.json"
        j = json.loads(p.read_text())
        note = j["inclusionProof"]["checkpoint"]["envelope"]
        j["inclusionProof"]["checkpoint"]["envelope"] = note.replace(
            "log2025-1.rekor.sigstore.dev", "faked-log.invalid", 1)
        p.write_text(json.dumps(j))
        with self.assertRaises(f15.Hold):
            f15.verify_pair()

    def test_signer_key_swap_rejected(self):
        (self.root / "v2/signer-public.der").write_bytes((self.root / "v1/signer-public.der").read_bytes())
        with self.assertRaises(f15.Hold):
            f15.verify_pair()

    def test_missing_local_newest_does_not_become_pass(self):
        (self.root / "v2/rekor_response.json").unlink()
        with self.assertRaises(FileNotFoundError):
            f15.verify_pair()

    def test_rollback_to_old_local_floor_is_rejected(self):
        p = self.root / "reviewer_floor.json"
        floor = json.loads(p.read_text())
        floor["newest_external_log_index"] = 206573201
        p.write_text(json.dumps(floor))
        with self.assertRaises(f15.Hold):
            f15.verify_pair()

    def test_false_latest_digest_is_rejected(self):
        p = self.root / "reviewer_floor.json"
        floor = json.loads(p.read_text())
        floor["newest_commitment_sha256"] = "0" * 64
        p.write_text(json.dumps(floor))
        with self.assertRaises(f15.Hold):
            f15.verify_pair()

    def test_v2_must_link_the_pinned_v1(self):
        data = json.loads((self.root / "v2/payload.json").read_bytes())
        self.assertEqual(data["previous_commitment_sha256"],
                         f15.sha((self.root / "v1/payload.json").read_bytes()).hex())

    def test_tile_path_from_real_remote_probe(self):
        self.assertEqual(f15.tile_path(206575059), "/api/v2/tile/entries/x806/933")
        self.assertEqual(f15.tile_path(206573201), "/api/v2/tile/entries/x806/926")

    def test_missing_trusted_root_holds(self):
        (self.root / "trusted_root_source_snapshot.json").unlink()
        with self.assertRaises(FileNotFoundError):
            f15.verify_pair()

    def test_bad_expected_digest_holds_before_network(self):
        with self.assertRaises(f15.Hold):
            f15.recover_online(206575059, "not-a-valid-sha")

if __name__ == "__main__":
    unittest.main()
