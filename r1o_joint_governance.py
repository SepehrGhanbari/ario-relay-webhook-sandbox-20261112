"""R1o - DRY-RUN founder/Ario governance policy predicate, never an authority.

No private keys, GitHub Check POSTs, write endpoints, actual signatures,
succession activation or real trust roots. Verification callbacks are injected;
mock verifiers in tests are NOT real independent attestation.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
import re
from typing import Callable

REPO = "SepehrGhanbari/Ario"
PHASES = frozenset(("FOUNDATION", "JOINT", "ARIO_CONTINUITY"))
ACTIONS = frozenset(("routine_change", "governance_change",
                     "delegation_precommit", "delegation_activate",
                     "key_rotation", "emergency_pause"))
HEX64 = re.compile(r"[a-f0-9]{64}\Z")
HEX40 = re.compile(r"[a-f0-9]{40}\Z")
OPAQUE = re.compile(r"[a-zA-Z0-9._:-]{8,96}\Z")


@dataclass(frozen=True)
class RootPolicy:
    phase: str
    version: int
    founder_key_id: str
    ario_key_id: str
    policy_digest: str


@dataclass(frozen=True)
class Request:
    repo: str
    phase: str
    version: int
    action: str
    policy_digest: str
    old_head: str
    proposed_head: str
    change_digest: str
    evidence_digest: str
    evidence_result: str
    ledger_anchor: str


@dataclass(frozen=True)
class Vote:
    role: str
    key_id: str
    signed_request_digest: str
    opaque_signature: str


@dataclass(frozen=True)
class Decision:
    verdict: str
    reason: str
    eligible_for_external_review: bool = False
    can_merge: bool = False
    can_publish: bool = False
    can_activate_trust: bool = False
    can_rotate_key: bool = False
    delegation_activated: bool = False
    production_trust: str = "NO_GO"

    def __post_init__(self):
        if (self.can_merge or self.can_publish or self.can_activate_trust or
                self.can_rotate_key or self.delegation_activated):
            raise ValueError("R1O_HAS_NO_OPERATIONAL_AUTHORITY")


def hold(reason: str, kind: str = "HOLD") -> Decision:
    return Decision(verdict=kind, reason=reason)


def matches(value: object, regex: re.Pattern) -> bool:
    return type(value) is str and regex.fullmatch(value) is not None


def valid_policy(root: object) -> bool:
    return (
        type(root) is RootPolicy and root.phase in PHASES and
        type(root.version) is int and root.version >= 1 and
        matches(root.policy_digest, HEX64) and
        matches(root.founder_key_id, HEX64) and
        matches(root.ario_key_id, HEX64) and
        root.founder_key_id != root.ario_key_id
    )


def valid_request(root: RootPolicy, req: object) -> bool:
    return (
        type(req) is Request and req.repo == REPO and
        req.phase == root.phase and
        type(req.version) is int and req.version == root.version and
        req.action in ACTIONS and
        req.policy_digest == root.policy_digest and
        matches(req.old_head, HEX40) and
        matches(req.proposed_head, HEX40) and
        matches(req.change_digest, HEX64) and
        matches(req.evidence_digest, HEX64) and
        matches(req.ledger_anchor, HEX64) and
        type(req.evidence_result) is str and
        req.evidence_result in ("PASS", "FAIL", "UNKNOWN", "INCOMPLETE")
    )


def canonical_request_digest(req: Request) -> str:
    return hashlib.sha256(
        json.dumps(asdict(req), sort_keys=True, separators=(",", ":"),
                   ensure_ascii=True).encode("ascii")
    ).hexdigest()


def allowed_roles(root: RootPolicy, req: Request):
    """Return (allowed roles, require both) or None if the operation is HOLD."""
    if req.action in ("delegation_activate", "key_rotation"):
        # No time-lock, independent ledger or custody succession mechanism yet.
        return None
    if root.phase == "FOUNDATION":
        return (("founder",), False) if req.action == "routine_change" else None
    if root.phase == "JOINT":
        if req.action in ("governance_change", "delegation_precommit"):
            return (("founder", "ario"), True)
        if req.action == "routine_change":
            return (("founder", "ario"), False)
    if root.phase == "ARIO_CONTINUITY":
        if req.action == "routine_change":
            return (("ario",), False)
        # No perpetual founder veto, but no unreviewed Ario sovereign amendment.
        return None
    return None


def evaluate(
    root: RootPolicy,
    req: Request,
    votes: tuple[Vote, ...],
    *,
    verify_signature: Callable[[str, str, str], bool] | None = None,
    verify_evidence: Callable[[Request], bool] | None = None,
    verify_current_state: Callable[[Request], bool] | None = None,
    verify_ledger_anchor: Callable[[Request], bool] | None = None,
    verify_independent_custody: Callable[[RootPolicy], bool] | None = None,
) -> Decision:
    """Advisory check only; no source of trust in this function or its callers."""
    if not valid_policy(root):
        return hold("ROOT_POLICY_INVALID")
    if not valid_request(root, req):
        return hold("REQUEST_SCOPE_OR_POLICY_MISMATCH")
    if type(votes) is not tuple or len(votes) > 2 or any(type(v) is not Vote for v in votes):
        return hold("VOTE_FORMAT_INVALID")
    if any(v.role not in ("founder", "ario") for v in votes):
        return hold("NON_GOVERNANCE_ACTOR")
    if len({v.role for v in votes}) != len(votes):
        return hold("DUPLICATE_ROLE_VOTE")
    if len({v.key_id for v in votes}) != len(votes):
        return hold("SAME_KEY_FOR_MULTIPLE_VOTES")

    digest = canonical_request_digest(req)
    for v in votes:
        expected_key = root.founder_key_id if v.role == "founder" else root.ario_key_id
        if (not matches(v.key_id, HEX64) or v.key_id != expected_key or
                not matches(v.signed_request_digest, HEX64) or
                not (type(v.opaque_signature) is str and
                     OPAQUE.fullmatch(v.opaque_signature) is not None)):
            return hold("VOTE_KEY_OR_PROOF_MISMATCH")
        if v.signed_request_digest != digest:
            return hold("VOTE_SIGNED_ANOTHER_REQUEST")

    if verify_signature is None:
        return hold("NO_INDEPENDENT_SIGNATURE_VERIFIER")
    for v in votes:
        try:
            verified = verify_signature(v.key_id, digest, v.opaque_signature)
        except Exception:
            return hold("SIGNATURE_VERIFICATION_UNAVAILABLE", "UNKNOWN_HOLD")
        if verified is not True:
            return hold("SIGNATURE_INVALID_OR_UNKNOWN")

    if req.action == "emergency_pause":
        if len(votes) != 1:
            return hold("PAUSE_REQUIRES_ONE_VALID_SIGNATURE")
        # This requests HOLD; does not actually pause an external service.
        return Decision("PAUSE_REQUEST_FOR_EXTERNAL_REVIEW",
                        "ONE_VALID_ROLE_REQUESTS_HOLD_ONLY")

    roles = allowed_roles(root, req)
    if roles is None:
        return hold("PHASE_OR_OPERATION_NOT_AUTHORIZED")
    allowed, require_both = roles
    present = {v.role for v in votes}
    if require_both and present != set(allowed):
        return hold("JOINT_TWO_DISTINCT_ROLES_REQUIRED")
    if not present or not present.issubset(set(allowed)):
        return hold("ROLE_NOT_ALLOWED_FOR_THIS_PHASE")

    if (verify_evidence is None or verify_current_state is None or
            verify_ledger_anchor is None or verify_independent_custody is None):
        return hold("INDEPENDENT_VERIFICATION_NOT_CONFIGURED")
    if req.evidence_result != "PASS":
        return hold("EVIDENCE_NOT_PASS_" + req.evidence_result)
    for reason, callback, argument in (
        ("EVIDENCE_UNKNOWN_OR_FAILED", verify_evidence, req),
        ("PR_OR_POLICY_CHANGED", verify_current_state, req),
        ("AUDIT_LEDGER_NOT_VERIFIED", verify_ledger_anchor, req),
        ("INDEPENDENT_CUSTODY_NOT_VERIFIED", verify_independent_custody, root),
    ):
        try:
            ok = callback(argument)
        except Exception:
            return hold(reason, "UNKNOWN_HOLD")
        if ok is not True:
            return hold(reason)

    # Even all mock/real callbacks passing never grant merge/sign/release.
    return Decision("ELIGIBLE_FOR_EXTERNAL_REVIEW",
                    "PREDICATE_ONLY_NOT_OPERATIONAL_AUTHORITY",
                    eligible_for_external_review=True)
