#!/usr/bin/env python3
"""F13 falsifier: coherent same-owner publisher substitution vs retained verifier floor."""
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent/'tests'))
from test_f7_coordinator import INTENT, fixture
import r2a0, f7_coordinator as f7, f13_verifier_floor as f13

with tempfile.TemporaryDirectory() as t:
    root=Path(t); a=root/'publisher_A';b=root/'publisher_B'
    db=root/'publisher_claims.sqlite'; verifier=root/'verifier_floor';verifier.mkdir()
    coordinator=f7.SharedCoordinator.initialize(db)
    marker=fixture(a,origin='a'); raw=r2a0.canonical(INTENT)
    assert coordinator.claim(INTENT,marker,'SAME_LABEL')['claim_recorded']
    authority=f7.mint_intent_authority(coordinator,INTENT,marker,'SAME_LABEL')
    r2a0.EvidenceJournal(a).append('merge-intent','local',raw,merge_intent_authority=authority)
    coordinator.record_local_observation(INTENT,marker,'SAME_LABEL')
    floor=f13.VerifierFloor(verifier)
    pinned=floor.pin(db,INTENT['repo'],INTENT['pr'])
    shutil.copytree(a,b)
    replacement=r2a0.digest(str(b).encode())
    with sqlite3.connect(db) as sql:
        sql.execute('UPDATE consumptions SET evidence_root=?',(str(b),))
        sql.execute('UPDATE root_bindings SET evidence_root_sha256=?',(replacement,))
        sql.execute('UPDATE observation_snapshots SET evidence_root_sha256=?',(replacement,))
    publisher=coordinator.inspect(INTENT['repo'],INTENT['pr'])
    check=floor.check(db,INTENT['repo'],INTENT['pr'])
    result={"F12_publisher_local_status":publisher['observation_status'],
            "F13_retained_floor_status":check['reason'],
            "F13_merge_authorization":check['merge_authorization'],
            "independent_custody":check['independent_custody'],
            "pin_persisted":pinned.get('pinned') is True,
            "network":"NOT_USED", "production":"NO_GO"}
    assert result['F12_publisher_local_status']=='CURRENT_LOCAL_READBACK_MATCH_NOT_INDEPENDENT'
    assert result['F13_retained_floor_status']=='PUBLISHER_DIFFERS_FROM_RETAINED_CHECKPOINT'
    print(json.dumps(result,sort_keys=True))
