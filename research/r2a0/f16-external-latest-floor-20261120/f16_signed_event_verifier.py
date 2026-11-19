#!/usr/bin/env python3
"""F16 offline verifier for exact public Nostr A/B, research only.

Validates Schnorr BIP340 event signatures and source sequence; relay ACKs
are NOT independent custodian signatures or durable retention guarantees.
"""
import hashlib
import json
import pathlib

P=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G=(55066263022277343669578718895168534326250603453777594175500187360389116729240,
   32670510020758816978083085130507043184471273380659243275938904335757337482424)
AUTHOR="a83270bc0068711429fd7fde8c4d93157eb700495b4017a23a49eafbe95d5659"
A="1287f223186e3f71ed5230261d375e8c8070b0eca8384fc30b8de73050b1c5c3"
B="cf7ad5df590b7b905faefe4bc0ae1e25a20c556887d56179592ddcaa7bfe9a63"
FILE=pathlib.Path(__file__).with_name("signed_events.json")

class Hold(Exception):
    pass

def h(x):return hashlib.sha256(x).digest()
def th(tag,msg):
    t=h(tag.encode())
    return h(t+t+msg)
def add(a,b):
    if a is None:return b
    if b is None:return a
    x,y=a;xx,yy=b
    if x==xx:
        if y!=yy or y==0:return None
        v=(3*x*x*pow(2*y,-1,P))%P
    else:v=((yy-y)*pow(xx-x,-1,P))%P
    rx=(v*v-x-xx)%P
    return rx,(v*(x-rx)-y)%P
def mul(k,q=G):
    o=None
    while k:
        if k&1:o=add(o,q)
        q=add(q,q)
        k>>=1
    return o
def schnorr(pub_hex,msg,sig_hex):
    try:
        pub=bytes.fromhex(pub_hex)
        sig=bytes.fromhex(sig_hex)
        if len(pub)!=32 or len(sig)!=64 or len(msg)!=32:return False
        x=int.from_bytes(pub,'big')
        r=int.from_bytes(sig[:32],'big');s=int.from_bytes(sig[32:],'big')
        if x>=P or r>=P or s>=N:return False
        y=pow((pow(x,3,P)+7)%P,(P+1)//4,P)
        if (y*y-pow(x,3,P)-7)%P:return False
        if y&1:y=P-y
        e=int.from_bytes(th('BIP0340/challenge',sig[:32]+pub+msg),'big')%N
        R=add(mul(s),mul(N-e,(x,y)))
        return R is not None and not (R[1]&1) and R[0]==r
    except (ValueError,TypeError):return False

def verify_events(events):
    if len(events)!=2:raise Hold("MISSING_OR_DUPLICATE_HISTORY")
    series=[]
    for ev in events:
        try:
            if ev["pubkey"]!=AUTHOR or ev["kind"]!=1 or ["t","ario-f16-20261120-research"] not in ev["tags"]:
                raise Hold("WRONG_PUBLISHER_OR_STREAM")
            serial=json.dumps([0,ev["pubkey"],ev["created_at"],ev["kind"],ev["tags"],ev["content"]],separators=(',',':'),ensure_ascii=False).encode()
            msg=h(serial)
            if ev["id"]!=msg.hex():raise Hold("EVENT_ID_CHANGED")
            if not schnorr(ev["pubkey"],msg,ev["sig"]):raise Hold("BIP340_SIGNATURE_INVALID")
            content=json.loads(ev["content"])
            if content.get("study")!="ARIO_F16_PUBLIC_DISCOVERY_ONLY" or content.get("production")!="NO_GO":
                raise Hold("WRONG_RESEARCH_SCOPE")
            series.append((content,ev))
        except (KeyError,ValueError,TypeError) as err:raise Hold("MALFORMED_NOSTR_EVENT") from err
    series.sort(key=lambda x:x[0]["seq"])
    x,y=(series[0][0],series[1][0])
    if (x["seq"],y["seq"])!=(1,2):raise Hold("FORK_OR_NONCONTIGUOUS_SEQUENCE")
    if x["commitment_sha256"]!=A or y["commitment_sha256"]!=B:raise Hold("REKOR_DIGEST_SUBSTITUTED")
    if x["prev_sha256"]!="0"*64 or y["prev_sha256"]!=A:raise Hold("BROKEN_PREVIOUS_LINK")
    if series[1][1]["created_at"]<series[0][1]["created_at"]:raise Hold("TIMESTAMP_ROLLBACK")
    return {"status":"SIGNED_SYNTHETIC_A_B_VERIFIED","latest":B,
            "outside_operator_retention_contract":"NOT_ESTABLISHED",
            "independent_latest_floor":"NOT_ESTABLISHED",
            "merge_authorization":"NOT_GRANTED"}

def main():
    try:
        records=json.loads(FILE.read_text())["exact_public_nostr_events"]
        print(json.dumps(verify_events(records),sort_keys=True))
        return 0
    except (Hold,OSError,KeyError,ValueError) as e:
        print(json.dumps({"status":"HOLD","reason":str(e),"merge_authorization":"NOT_GRANTED"}))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
