"""R1d experimental GitHub App failure-check publisher. No prod permissions.

Runs ONLY on a trusted operator machine outside target PR code. App private key
is read from a local path, never printed, uploaded, written to repository or logs.
This prototype intentionally CANNOT publish a success or approve a merge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

API = 'https://api.github.com'
TARGET_REPO = 'SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a'
CHECK_NAME = 'ario-r1d-lab-app-gate'
SHA_LENGTH = 40
ALLOWED_PRS = {9, 10}  # current isolated negative fixtures, not production PRs


class GateHold(Exception):
    """Fail-closed: do not publish without exact fixture identity."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise GateHold(reason)


def api(method: str, path: str, *, token: str | None = None, payload: dict | None = None) -> dict:
    """GitHub HTTPS REST. Never return or log tokens on failed requests."""
    require(path.startswith('/') and '\n' not in path, 'INVALID_API_PATH')
    headers = {
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'Ario-R1d-Disposable-Check-Publisher/0.1',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    if token is not None:
        headers['Authorization'] = 'Bearer ' + token
    body = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode() if payload is not None else None
    req = urllib.request.Request(API + path, headers=headers, data=body, method=method)
    if body is not None:
        req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            obj = json.loads(response.read(500_000))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
        # Do not render the server body; it could contain unexpected private information.
        raise GateHold('GITHUB_API_UNAVAILABLE_' + type(error).__name__) from None
    require(isinstance(obj, dict), 'INVALID_API_RESPONSE')
    return obj


def preflight(pr: dict, number: int, expected_head: str, expected_base: str) -> None:
    """All values from HTTPS public GitHub REST, never PR-controlled workflow text."""
    require(type(number) is int and number in ALLOWED_PRS, 'PR_OUT_OF_SCOPE')
    require(len(expected_head) == SHA_LENGTH and all(c in '0123456789abcdef' for c in expected_head), 'INVALID_HEAD_SHA')
    require(len(expected_base) == SHA_LENGTH and all(c in '0123456789abcdef' for c in expected_base), 'INVALID_BASE_SHA')
    require(pr.get('number') == number, 'PR_NUMBER_CHANGED')
    require(pr.get('state') == 'open', 'PR_NOT_OPEN')
    require(pr.get('merged') is False, 'PR_MERGED')
    head, base = pr.get('head') or {}, pr.get('base') or {}
    require(head.get('sha') == expected_head and base.get('sha') == expected_base, 'HEAD_OR_BASE_DRIFT')
    require(base.get('ref') == 'main', 'UNEXPECTED_TARGET_BRANCH')
    require((head.get('repo') or {}).get('full_name') == TARGET_REPO, 'UNTRUSTED_HEAD_REPOSITORY')
    require((base.get('repo') or {}).get('full_name') == TARGET_REPO, 'UNTRUSTED_BASE_REPOSITORY')


def failure_payload(number: int, head: str, base: str) -> dict:
    """Only FAILURE supported; no success path or neutral/skipped ambiguity."""
    return {
        'name': CHECK_NAME,
        'head_sha': head,
        'status': 'completed',
        'conclusion': 'failure',
        'external_id': f'R1D-LAB-HOLD:PR-{number}:{head}:{base}',
        'output': {
            'title': 'HOLD — experimental R1d, NOT merge authority',
            'summary': (
                'Disposable lab negative check. No independent production evaluator, '
                'durable review-deletion custody or atomic merge decision is proven. '
                'Do not interpret GitHub Actions success or this publication as owner approval.'
            ),
        },
    }



def enforce_failure_only_payload(payload: dict, number: int, head: str, base: str) -> None:
    """Defense in depth: never send a green/neutral/skipped lab check.

    This is not merge authorization or evidence of independent verification.
    It guards against a future accidental change to failure_payload().
    """
    require(type(payload) is dict, 'PUBLISH_PAYLOAD_NOT_OBJECT')
    require(payload.get('name') == CHECK_NAME, 'PUBLISH_CHECK_NAME_MISMATCH')
    require(payload.get('head_sha') == head, 'PUBLISH_SHA_MISMATCH')
    require(payload.get('status') == 'completed', 'PUBLISH_STATUS_NOT_COMPLETED')
    require(payload.get('conclusion') == 'failure', 'PUBLISH_NOT_FAILURE')
    expected_id = f'R1D-LAB-HOLD:PR-{number}:{head}:{base}'
    require(payload.get('external_id') == expected_id, 'PUBLISH_EVIDENCE_BINDING_MISMATCH')
    output = payload.get('output')
    require(type(output) is dict and type(output.get('title')) is str and
            output['title'].startswith('HOLD'), 'PUBLISH_HOLD_TITLE_MISSING')


def signed_jwt(app_id: str, private_key: bytes, now: int) -> str:
    """RS256 JWT with short expiry. PyJWT/cryptography imported only in live mode."""
    require(app_id.isdecimal() and int(app_id) > 0, 'INVALID_APP_ID')
    require(private_key.startswith(b'-----BEGIN ') and len(private_key) > 500, 'INVALID_PRIVATE_KEY')
    try:
        import jwt
        result = jwt.encode({'iat': now - 60, 'exp': now + 480, 'iss': app_id}, private_key, algorithm='RS256')
    except (ImportError, ValueError, TypeError):
        raise GateHold('JWT_LIBRARY_OR_KEY_UNAVAILABLE') from None
    require(isinstance(result, str), 'INVALID_JWT')
    return result


def get_installation_token(app_id: str, installation_id: str, key_path: str, caller) -> str:
    require(installation_id.isdecimal() and int(installation_id) > 0, 'INVALID_INSTALLATION_ID')
    key = Path(key_path)
    require(key.is_file() and not key.is_symlink(), 'PRIVATE_KEY_NOT_LOCAL_FILE')
    require(key.stat().st_size < 20_000, 'PRIVATE_KEY_TOO_LARGE')
    jwt_token = signed_jwt(app_id, key.read_bytes(), int(time.time()))
    identity = caller('GET', '/app', token=jwt_token)
    require(identity.get('id') == int(app_id), 'APP_IDENTITY_MISMATCH')
    installation = caller('GET', '/app/installations/' + installation_id, token=jwt_token)
    require(installation.get('id') == int(installation_id), 'INSTALLATION_IDENTITY_MISMATCH')
    require((installation.get('account') or {}).get('login') == 'SepehrGhanbari', 'INSTALLATION_OWNER_MISMATCH')
    require(installation.get('repository_selection') == 'selected', 'INSTALLATION_NOT_REPO_SCOPED')
    granted = installation.get('permissions') or {}
    require(granted.get('checks') == 'write', 'INSTALLATION_CHECK_PERMISSION_MISSING')
    require(granted.get('administration') in (None, 'read'), 'UNSAFE_ADMINISTRATION_PERMISSION')
    issued = caller('POST', '/app/installations/' + installation_id + '/access_tokens', token=jwt_token,
                    payload={'repositories': [TARGET_REPO.split('/')[1]], 'permissions': {'checks': 'write'}})
    token = issued.get('token')
    require(isinstance(token, str) and len(token) > 20, 'INSTALLATION_TOKEN_MISSING')
    perms = issued.get('permissions') or {}
    require(perms.get('checks') == 'write', 'TOKEN_CHECK_PERMISSION_MISSING')
    return token


def execute(*, number: int, head: str, base: str, live: bool, caller=api,
            config: dict | None = None) -> dict:
    """Read current exact PR twice. Dry-run is the safe default."""
    config = config or {}
    pr = caller('GET', f'/repos/{TARGET_REPO}/pulls/{number}')
    preflight(pr, number, head, base)
    payload = failure_payload(number, head, base)
    enforce_failure_only_payload(payload, number, head, base)
    latest = caller('GET', f'/repos/{TARGET_REPO}/pulls/{number}')
    preflight(latest, number, head, base)
    require((pr.get('updated_at'), pr.get('draft'), pr.get('state')) ==
            (latest.get('updated_at'), latest.get('draft'), latest.get('state')),
            'MUTABLE_PR_CHANGED_DURING_AUDIT')
    if not live:
        return {'mode': 'DRY_RUN', 'verdict': 'HOLD', 'repo': TARGET_REPO,
                'pr': number, 'head': head, 'payload': payload, 'published': False}
    require(config.get('repo') == TARGET_REPO, 'LIVE_REPO_NOT_EXPLICITLY_APPROVED')
    token = get_installation_token(config.get('app_id', ''), config.get('installation_id', ''),
                                   config.get('key_path', ''), caller)
    # Another preflight before publishing; still not atomic with a subsequent merge.
    newest = caller('GET', f'/repos/{TARGET_REPO}/pulls/{number}')
    preflight(newest, number, head, base)
    require(newest.get('updated_at') == latest.get('updated_at'), 'PR_CHANGED_BEFORE_CHECK_PUBLISH')
    posted = caller('POST', f'/repos/{TARGET_REPO}/check-runs', token=token, payload=payload)
    require(posted.get('head_sha') == head and posted.get('name') == CHECK_NAME and
            posted.get('status') == 'completed' and posted.get('conclusion') == 'failure',
            'PUBLISHED_CHECK_MISMATCH')
    require((posted.get('app') or {}).get('id') == int(config['app_id']),
            'CHECK_PRODUCER_ID_MISMATCH')
    # No success token, JWT or key is output from this function.
    return {'mode': 'LIVE_FAILURE_ONLY', 'verdict': 'HOLD', 'repo': TARGET_REPO,
            'pr': number, 'head': head, 'published': True,
            'check_run_id': posted.get('id'), 'check_app_id': (posted.get('app') or {}).get('id')}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='R1d disposable FAIL-ONLY GitHub App check publisher')
    parser.add_argument('--pr', required=True, type=int)
    parser.add_argument('--head', required=True)
    parser.add_argument('--base', required=True)
    parser.add_argument('--publish-failure', action='store_true', default=False)
    args = parser.parse_args(argv)
    config = {
        'repo': os.getenv('ARIO_R1D_TARGET_REPO', ''),
        'app_id': os.getenv('ARIO_R1D_APP_ID', ''),
        'installation_id': os.getenv('ARIO_R1D_INSTALLATION_ID', ''),
        'key_path': os.getenv('ARIO_R1D_PRIVATE_KEY_PATH', ''),
    }
    try:
        result = execute(number=args.pr, head=args.head, base=args.base,
                         live=args.publish_failure, config=config)
        print(json.dumps(result, sort_keys=True))
        return 2  # HOLD ALWAYS exits nonzero, even in dry-run. No green-on-HOLD path.
    except (GateHold, OSError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, GateHold) else type(exc).__name__
        print(json.dumps({'verdict': 'HOLD', 'reason': reason, 'published': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
