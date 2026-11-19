#!/usr/bin/env python3
"""F15 external log verification. Research-only; no merge/trust actions.

Offline mode validates recorded Rekor V2 Merkle inclusion against an Ed25519
checkpoint signature using the provided Sigstore public key snapshot.
This snapshot is from public root-signing GitHub, NOT TUF-verified here.
Online recovery reads a public Rekor tile by known index and expected digest.
"""
import base64
import hashlib
import json
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

LOG_URL = "https://log2025-1.rekor.sigstore.dev"
BUNDLE_ROOT = Path(__file__).resolve().parent

class Hold(Exception):
    pass

def require(ok, label):
    if not ok:
        raise Hold(label)

def b64(s):
    return base64.b64decode(s, validate=True)

def sha(x):
    return hashlib.sha256(x).digest()

def read_json(p):
    return json.loads(Path(p).read_bytes())

def openssl(args):
    try:
        p = subprocess.run(["openssl"] + args, capture_output=True, check=False, timeout=20)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        raise Hold("OPENSSL_UNAVAILABLE") from e
    require(p.returncode == 0, "SIGNATURE_VERIFICATION_FAILED")
    return p.stdout

def check_single(label, trust):
    folder = BUNDLE_ROOT / label
    payload = (folder / "payload.json").read_bytes()
    rec = read_json(folder / "rekor_response.json")
    body_bytes = b64(rec["canonicalizedBody"])
    body = json.loads(body_bytes)
    require(body.get("kind") == "hashedrekord" and body.get("apiVersion") == "0.0.2", "UNSUPPORTED_ENTRY_FORMAT")
    entry = body["spec"]["hashedRekordV002"]
    require(entry["data"]["algorithm"] == "SHA2_256", "WRONG_HASH_ALGORITHM")
    require(b64(entry["data"]["digest"]) == sha(payload), "PAYLOAD_DIGEST_MISMATCH")
    pub = b64(entry["signature"]["verifier"]["publicKey"]["rawBytes"])
    sig = b64(entry["signature"]["content"])
    require(entry["signature"]["verifier"]["keyDetails"] == "PKIX_ECDSA_P256_SHA_256", "UNSUPPORTED_SIGNER")
    require(pub == (folder / "signer-public.der").read_bytes(), "SIGNER_KEY_CHANGED")
    require(sig == (folder / "artifact-signature.der").read_bytes(), "ARTIFACT_SIGNATURE_CHANGED")

    log_key = next((x for x in trust["tlogs"] if x.get("baseUrl") == LOG_URL), None)
    require(log_key is not None and log_key["publicKey"]["keyDetails"] == "PKIX_ED25519", "UNPINNED_LOG_KEY")
    require(rec["logId"]["keyId"] == log_key["logId"]["keyId"], "LOG_KEY_ID_MISMATCH")

    proof = rec["inclusionProof"]
    size, index = int(proof["treeSize"]), int(rec["logIndex"])
    require(size > index >= 0, "INVALID_LOG_SIZE_OR_INDEX")
    note = proof["checkpoint"]["envelope"]
    parts = note.split("\n\n— ")
    require(len(parts) >= 2, "INVALID_SIGNED_CHECKPOINT")
    signed_note = parts[0] + "\n"
    lines = signed_note.splitlines()
    require(len(lines) == 3, "INVALID_CHECKPOINT_BODY")
    require(lines[0] == LOG_URL.removeprefix("https://"), "WRONG_LOG_ORIGIN")
    require(int(lines[1]) == size and b64(lines[2]) == b64(proof["rootHash"]), "CHECKPOINT_ROOT_MISMATCH")
    signline = next((x for x in note.splitlines() if x.startswith("— " + lines[0] + " ")), "")
    require(bool(signline), "LOG_SIGNATURE_MISSING")
    signed = b64(signline.split()[-1])
    require(len(signed) == 68, "LOG_SIGNATURE_LENGTH")
    leaf_hash = sha(bytes([0]) + body_bytes)
    fn, sn = index, size - 1
    for sibling_b64 in proof["hashes"]:
        sibling = b64(sibling_b64)
        require(len(sibling) == 32, "PROOF_HASH_LENGTH")
        if fn & 1 or fn == sn:
            leaf_hash = sha(bytes([1]) + sibling + leaf_hash)
            while fn % 2 == 0 and fn != 0:
                fn //= 2
                sn //= 2
        else:
            leaf_hash = sha(bytes([1]) + leaf_hash + sibling)
        fn //= 2
        sn //= 2
    require(leaf_hash == b64(proof["rootHash"]), "MERKLE_INCLUSION_FAILED")

    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        (d / "logkey.der").write_bytes(b64(log_key["publicKey"]["rawBytes"]))
        (d / "signer.der").write_bytes(pub)
        (d / "signer.sig").write_bytes(sig)
        (d / "log.sig").write_bytes(signed[4:])
        (d / "note.txt").write_bytes(signed_note.encode())
        (d / "payload.bin").write_bytes(payload)
        openssl(["pkey", "-pubin", "-inform", "DER", "-in", str(d / "logkey.der"), "-out", str(d / "logkey.pem")])
        openssl(["pkeyutl", "-verify", "-pubin", "-inkey", str(d / "logkey.pem"), "-rawin", "-in", str(d / "note.txt"), "-sigfile", str(d / "log.sig")])
        openssl(["pkey", "-pubin", "-inform", "DER", "-in", str(d / "signer.der"), "-out", str(d / "signer.pem")])
        openssl(["dgst", "-sha256", "-verify", str(d / "signer.pem"), "-signature", str(d / "signer.sig"), str(d / "payload.bin")])
    return {"label":label,"index":index,"digest":sha(payload).hex(),"payload":json.loads(payload),"tree_size":size,"merkle":"PASS","checkpoint_signature":"PASS","artifact_signature":"PASS"}

def verify_pair():
    trust = read_json(BUNDLE_ROOT / "trusted_root_source_snapshot.json")
    a = check_single("v1", trust)
    b = check_single("v2", trust)
    require(a["payload"]["study"] == b["payload"]["study"] == "ARIO_F15_SYNTHETIC_THIRD_PARTY_CUSTODY", "WRONG_STUDY")
    require(a["payload"]["run_id"] == b["payload"]["run_id"], "RUN_ID_MISMATCH")
    require(a["payload"]["seq"] == 1 and b["payload"]["seq"] == 2, "SEQUENCE_MISMATCH")
    require(b["payload"]["previous_commitment_sha256"] == a["digest"], "HISTORY_CHAIN_BROKEN")
    require(b["index"] > a["index"], "LOG_INDEX_ROLLBACK")
    floor = read_json(BUNDLE_ROOT / "reviewer_floor.json")
    require(int(floor["newest_external_log_index"]) == b["index"], "FLOOR_INDEX_ROLLBACK")
    require(floor["newest_commitment_sha256"] == b["digest"], "FLOOR_DIGEST_ROLLBACK")
    return {"status":"BOUNDED_PASS","v1":{k:v for k,v in a.items() if k!="payload"},"v2":{k:v for k,v in b.items() if k!="payload"},"independent_floor_custody":"NOT_ESTABLISHED","trusted_root_tuf_verified":False}

def tile_path(index):
    n = index // 256
    groups = []
    while True:
        groups.insert(0, str(n % 1000).zfill(3))
        n //= 1000
        if not n:
            break
    return "/api/v2/tile/entries/" + "/".join(("x" + group if i < len(groups) - 1 else group) for i, group in enumerate(groups))

def recover_online(index, expected_sha256):
    require(len(expected_sha256) == 64 and all(c in "0123456789abcdef" for c in expected_sha256), "INVALID_EXPECTED_SHA")
    url = LOG_URL + tile_path(index)
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            raw = response.read(1024 * 1024 + 1)
    except Exception as exc:
        raise Hold("REMOTE_READ_UNAVAILABLE") from exc
    require(len(raw) <= 1024 * 1024, "REMOTE_TILE_TOO_LARGE")
    offset = 0
    entries = []
    while offset < len(raw):
        require(offset + 2 <= len(raw), "TRUNCATED_TILE")
        size = int.from_bytes(raw[offset:offset+2], "big")
        offset += 2
        require(offset + size <= len(raw), "TRUNCATED_ENTRY")
        entries.append(json.loads(raw[offset:offset+size]))
        offset += size
    target = index % 256
    require(target < len(entries), "ENTRY_NOT_FOUND")
    result = entries[target]
    require(result["kind"] == "hashedrekord" and result["apiVersion"] == "0.0.2", "WRONG_REMOTE_FORMAT")
    got = b64(result["spec"]["hashedRekordV002"]["data"]["digest"]).hex()
    require(got == expected_sha256, "REMOTE_RECORD_CHANGED_OR_WRONG_INDEX")
    return {"status":"REMOTE_ENTRY_RETRIEVED","log_index":index,"digest":got,"tile":url,"note":"Retrieval alone is not an inclusion proof or proof of completeness"}

def main():
    try:
        if len(sys.argv) == 1 or sys.argv[1] == "offline":
            result = verify_pair()
        elif len(sys.argv) == 4 and sys.argv[1] == "recover":
            result = recover_online(int(sys.argv[2]), sys.argv[3])
        else:
            print("Usage: python f15_verify.py offline | recover INDEX SHA256",file=sys.stderr)
            return 2
        print(json.dumps(result,sort_keys=True))
        return 0
    except (Hold, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status":"HOLD","reason":str(exc) or type(exc).__name__},sort_keys=True))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
