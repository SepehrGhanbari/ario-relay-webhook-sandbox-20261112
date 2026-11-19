#!/usr/bin/env python3
"""Read-only verification of an independent witness's cosignature on F15 Rekor B.

Uses a pinned verifier key independently published by the witness operator:
https://witness.stagemole.eu/about
This only verifies the witnessed REKOR tree checkpoint, not Ario event intake.
"""
import base64
import datetime
import json
import subprocess
import sys
import tempfile
from pathlib import Path

WITNESS_NAME = "witness.stagemole.eu"
WITNESS_VKEY = "witness.stagemole.eu+67f7aea0+BEqSG3yu9YrmcM3BHvQYTxwFj3uSWakQepafafpUqklv"
F15 = Path(__file__).resolve().parent

def verify(note, *, tamper=False):
    parts = note.split("\n\n— ")
    if len(parts) < 2:
        raise ValueError("MISSING_SIGNED_NOTE")
    signed_note = (parts[0] + "\n").encode()
    lines = signed_note.splitlines()
    if len(lines) != 3 or lines[0] != b"log2025-1.rekor.sigstore.dev":
        raise ValueError("WRONG_ORIGIN")
    witness_line = next((x for x in note.splitlines() if x.startswith("— " + WITNESS_NAME + " ")), None)
    if not witness_line:
        raise ValueError("WITNESS_SIGNATURE_MISSING")
    signature = base64.b64decode(witness_line.split()[-1], validate=True)
    name, id_hex, key64 = WITNESS_VKEY.split("+", 2)
    raw_key = base64.b64decode(key64, validate=True)
    if name != WITNESS_NAME or len(raw_key) != 33 or raw_key[0] != 4:
        raise ValueError("INVALID_PINNED_WITNESS_KEY")
    if len(signature) != 76 or signature[:4].hex() != id_hex:
        raise ValueError("WITNESS_KEY_HINT_MISMATCH")
    timestamp = int.from_bytes(signature[4:12], "big")
    message = b"cosignature/v1\ntime " + str(timestamp).encode() + b"\n" + signed_note
    if tamper:
        message += b"NOT_THE_ORIGINAL_CHECKPOINT"
    pub_der = bytes.fromhex("302a300506032b6570032100") + raw_key[1:]
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        (d / "pub.der").write_bytes(pub_der)
        (d / "message").write_bytes(message)
        (d / "signature").write_bytes(signature[12:])
        c = subprocess.run(["openssl", "pkey", "-pubin", "-inform", "DER", "-in", str(d / "pub.der"), "-out", str(d / "pub.pem")], capture_output=True, timeout=20)
        if c.returncode:
            raise ValueError("OPENSSL_KEY_IMPORT_FAILED")
        v = subprocess.run(["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(d / "pub.pem"), "-rawin", "-in", str(d / "message"), "-sigfile", str(d / "signature")], capture_output=True, timeout=20)
        if v.returncode:
            raise ValueError("WITNESS_SIGNATURE_REJECTED")
    return {"status": "WITNESS_SIGNATURE_VERIFIED", "witness": name, "timestamp_utc": datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).isoformat(), "role": "LOG_TREE_CHECKPOINT_WITNESS_ONLY", "independent_ario_latest_floor": "NOT_ESTABLISHED"}

def main():
    note = json.loads((F15 / "v2" / "rekor_response.json").read_text())["inclusionProof"]["checkpoint"]["envelope"]
    tamper = len(sys.argv) == 2 and sys.argv[1] == "--tamper"
    try:
        result = verify(note, tamper=tamper)
        if tamper:
            print(json.dumps({"status":"FAIL","reason":"tampering unexpectedly accepted"}))
            return 1
        print(json.dumps(result,sort_keys=True))
        return 0
    except ValueError as e:
        if tamper:
            print(json.dumps({"status":"EXPECTED_TAMPER_REJECTED","reason":str(e)}))
            return 0
        print(json.dumps({"status":"HOLD","reason":str(e)}))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
