"""Offline negative controls. Never contacts GitHub or generates a real token."""
from dataclasses import replace
from contextlib import redirect_stdout, redirect_stderr
import io
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from publisher import (API, TARGET_REPO, CHECK_NAME, GateHold, execute,
                       failure_payload, preflight, get_installation_token)

HEAD = 'a' * 40
BASE = 'b' * 40


def pr(**updates):
    obj = {'number': 10, 'state': 'open', 'merged': False, 'draft': False,
           'updated_at': '2026-11-13T16:00:00Z',
           'head': {'sha': HEAD, 'repo': {'full_name': TARGET_REPO}},
           'base': {'sha': BASE, 'ref': 'main', 'repo': {'full_name': TARGET_REPO}}}
    obj.update(updates)
    return obj


class Caller:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if not self.responses:
            raise AssertionError('Unexpected network call')
        return self.responses.pop(0)


class PublisherTests(unittest.TestCase):
    def test_01_failure_check_only(self):
        value = failure_payload(10, HEAD, BASE)
        self.assertEqual((value['status'], value['conclusion']), ('completed', 'failure'))
        self.assertEqual(value['name'], CHECK_NAME)

    def test_02_dry_run_no_write(self):
        client = Caller([pr(), pr()])
        result = execute(number=10, head=HEAD, base=BASE, live=False, caller=client)
        self.assertEqual(result['verdict'], 'HOLD')
        self.assertFalse(result['published'])
        self.assertEqual([x[0] for x in client.calls], ['GET', 'GET'])

    def test_03_wrong_sha_fail_closed(self):
        client = Caller([pr()])
        with self.assertRaisesRegex(GateHold, 'HEAD_OR_BASE_DRIFT'):
            execute(number=10, head='c'*40, base=BASE, live=False, caller=client)
        self.assertEqual(len(client.calls), 1)

    def test_04_modified_base_rejected(self):
        with self.assertRaisesRegex(GateHold, 'HEAD_OR_BASE_DRIFT'):
            preflight(pr(), 10, HEAD, 'f'*40)

    def test_05_unauthorized_pr_rejected(self):
        with self.assertRaisesRegex(GateHold, 'PR_OUT_OF_SCOPE'):
            preflight(pr(number=151), 151, HEAD, BASE)

    def test_06_cross_repo_head_rejected(self):
        changed = pr(head={'sha': HEAD, 'repo': {'full_name': 'attacker/fork'}})
        with self.assertRaisesRegex(GateHold, 'UNTRUSTED_HEAD_REPOSITORY'):
            preflight(changed, 10, HEAD, BASE)

    def test_07_merged_pr_rejected(self):
        with self.assertRaisesRegex(GateHold, 'PR_NOT_OPEN'):
            preflight(pr(state='closed', merged=True), 10, HEAD, BASE)

    def test_08_missing_base_repo_rejected(self):
        changed = pr(base={'sha': BASE, 'ref': 'main', 'repo': None})
        with self.assertRaisesRegex(GateHold, 'UNTRUSTED_BASE_REPOSITORY'):
            preflight(changed, 10, HEAD, BASE)

    def test_09_mutable_metadata_change_rejected(self):
        client = Caller([pr(), pr(updated_at='2026-11-13T17:00:00Z')])
        with self.assertRaisesRegex(GateHold, 'MUTABLE_PR_CHANGED_DURING_AUDIT'):
            execute(number=10, head=HEAD, base=BASE, live=False, caller=client)

    def test_10_no_credential_means_no_publish(self):
        client = Caller([pr(), pr()])
        with self.assertRaisesRegex(GateHold, 'LIVE_REPO_NOT_EXPLICITLY_APPROVED'):
            execute(number=10, head=HEAD, base=BASE, live=True, caller=client)
        self.assertEqual([x[0] for x in client.calls], ['GET', 'GET'])

    def test_11_installation_id_rejects_invalid(self):
        with self.assertRaisesRegex(GateHold, 'INVALID_INSTALLATION_ID'):
            get_installation_token('123', '', 'nowhere', lambda *a, **k: None)

    def test_12_noncanonical_sha_rejected(self):
        with self.assertRaisesRegex(GateHold, 'INVALID_HEAD_SHA'):
            preflight(pr(), 10, 'Z'*40, BASE)

    def test_13_spoofed_succeeded_status_is_irrelevant(self):
        changed = pr(claimed_check='success', claimed_workflow='exit 0')
        client = Caller([changed, changed])
        result = execute(number=10, head=HEAD, base=BASE, live=False, caller=client)
        self.assertEqual(result['payload']['conclusion'], 'failure')

    def test_14_no_success_mode_in_cli(self):
        from publisher import main
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
            main(['--approve', '--pr', '10', '--head', HEAD, '--base', BASE])
        self.assertEqual(cm.exception.code, 2)

    def test_15_draft_pr_still_holds(self):
        value = pr(draft=True)
        client = Caller([value, value])
        result = execute(number=10, head=HEAD, base=BASE, live=False, caller=client)
        self.assertEqual((result['verdict'], result['payload']['conclusion']), ('HOLD', 'failure'))

    def test_16_app_installation_selected_and_identity_checked(self):
        with TemporaryDirectory() as directory:
            key = Path(directory) / 'unused-lab-test.pem'
            key.write_bytes(b'NO_REAL_KEY')
            client = Caller([
                {'id': 4321},
                {'id': 777, 'account': {'login': 'SepehrGhanbari'},
                 'repository_selection': 'selected', 'permissions': {'checks': 'write'}},
                {'token': 'fake_test_token_long_enough_for_mocking_1234',
                 'permissions': {'checks': 'write'}}
            ])
            with patch('publisher.signed_jwt', return_value='MOCKED_JWT_NOT_REAL'):
                token = get_installation_token('4321', '777', str(key), client)
            self.assertTrue(token.startswith('fake_test_token'))
            self.assertEqual([x[0] for x in client.calls], ['GET', 'GET', 'POST'])
            self.assertEqual(client.calls[-1][2]['payload']['repositories'],
                             [TARGET_REPO.split('/')[1]])
            self.assertEqual(client.calls[-1][2]['payload']['permissions'],
                             {'checks': 'write'})

    def test_17_wrong_installation_repo_scope_rejected(self):
        with TemporaryDirectory() as directory:
            key = Path(directory) / 'unused-lab-test.pem'
            key.write_bytes(b'NO_REAL_KEY')
            client = Caller([
                {'id': 4321},
                {'id': 777, 'account': {'login': 'SepehrGhanbari'},
                 'repository_selection': 'all', 'permissions': {'checks': 'write'}},
            ])
            with patch('publisher.signed_jwt', return_value='MOCKED_JWT_NOT_REAL'):
                with self.assertRaisesRegex(GateHold, 'INSTALLATION_NOT_REPO_SCOPED'):
                    get_installation_token('4321', '777', str(key), client)
            self.assertEqual([x[0] for x in client.calls], ['GET', 'GET'])

    def test_18_wrong_app_identity_rejected(self):
        with TemporaryDirectory() as directory:
            key = Path(directory) / 'unused-lab-test.pem'
            key.write_bytes(b'NO_REAL_KEY')
            client = Caller([{'id': 9999}])
            with patch('publisher.signed_jwt', return_value='MOCKED_JWT_NOT_REAL'):
                with self.assertRaisesRegex(GateHold, 'APP_IDENTITY_MISMATCH'):
                    get_installation_token('4321', '777', str(key), client)
            self.assertEqual(len(client.calls), 1)

    def test_19_dry_run_hold_has_nonzero_process_exit(self):
        from publisher import main
        with patch('publisher.execute', return_value={'mode': 'DRY_RUN',
                                                       'verdict': 'HOLD', 'published': False}):
            with redirect_stdout(io.StringIO()):
                result = main(['--pr', '10', '--head', HEAD, '--base', BASE])
        self.assertEqual(result, 2)

    def test_20_live_fail_only_has_nonzero_process_exit(self):
        from publisher import main
        with patch('publisher.execute', return_value={'mode': 'LIVE_FAILURE_ONLY',
                                                       'verdict': 'HOLD', 'published': True}):
            with redirect_stdout(io.StringIO()):
                result = main(['--pr', '10', '--head', HEAD, '--base', BASE,
                               '--publish-failure'])
        self.assertEqual(result, 2)



class R1eRaceTests(unittest.TestCase):
    """Mock-only HEAD/base drift controls; no live check or trusted key."""

    def test_21_head_changes_on_final_pre_publish_read(self):
        drift = pr(head={'sha': 'c'*40, 'repo': {'full_name': TARGET_REPO}})
        client = Caller([pr(), pr(), drift])
        with patch('publisher.get_installation_token', return_value='MOCK_TOKEN'):
            with self.assertRaisesRegex(GateHold, 'HEAD_OR_BASE_DRIFT'):
                execute(number=10, head=HEAD, base=BASE, live=True,
                        caller=client, config={'repo': TARGET_REPO})
        self.assertEqual([method for method, _, _ in client.calls],
                         ['GET', 'GET', 'GET'])

    def test_22_base_changes_on_final_pre_publish_read(self):
        drift = pr(base={'sha': 'd'*40, 'ref': 'main',
                         'repo': {'full_name': TARGET_REPO}})
        client = Caller([pr(), pr(), drift])
        with patch('publisher.get_installation_token', return_value='MOCK_TOKEN'):
            with self.assertRaisesRegex(GateHold, 'HEAD_OR_BASE_DRIFT'):
                execute(number=10, head=HEAD, base=BASE, live=True,
                        caller=client, config={'repo': TARGET_REPO})
        self.assertEqual([method for method, _, _ in client.calls],
                         ['GET', 'GET', 'GET'])

    def test_23_metadata_changes_on_final_pre_publish_read(self):
        drift = pr(updated_at='2026-11-13T19:00:00Z')
        client = Caller([pr(), pr(), drift])
        with patch('publisher.get_installation_token', return_value='MOCK_TOKEN'):
            with self.assertRaisesRegex(GateHold, 'PR_CHANGED_BEFORE_CHECK_PUBLISH'):
                execute(number=10, head=HEAD, base=BASE, live=True,
                        caller=client, config={'repo': TARGET_REPO})
        self.assertEqual([method for method, _, _ in client.calls],
                         ['GET', 'GET', 'GET'])


class R1fPayloadGuardTests(unittest.TestCase):
    """Regression: a malformed payload must HOLD before any token/POST."""

    def reject(self, field: str, value, reason: str):
        payload = failure_payload(10, HEAD, BASE)
        if field == 'output':
            payload['output'] = value
        else:
            payload[field] = value
        client = Caller([pr()])
        with patch('publisher.failure_payload', return_value=payload):
            with self.assertRaisesRegex(GateHold, reason):
                execute(number=10, head=HEAD, base=BASE, live=True,
                        caller=client, config={'repo': TARGET_REPO})
        self.assertEqual([method for method, _, _ in client.calls], ['GET'])

    def test_24_neutral_must_hold(self):
        self.reject('conclusion', 'neutral', 'PUBLISH_NOT_FAILURE')

    def test_25_skipped_must_hold(self):
        self.reject('conclusion', 'skipped', 'PUBLISH_NOT_FAILURE')

    def test_26_success_must_hold(self):
        self.reject('conclusion', 'success', 'PUBLISH_NOT_FAILURE')

    def test_27_wrong_head_must_hold(self):
        self.reject('head_sha', 'c'*40, 'PUBLISH_SHA_MISMATCH')

    def test_28_wrong_external_id_must_hold(self):
        self.reject('external_id', 'R1D-LAB-HOLD:forged', 'PUBLISH_EVIDENCE_BINDING_MISMATCH')

    def test_29_missing_hold_title_must_hold(self):
        self.reject('output', {'title': 'Approval'}, 'PUBLISH_HOLD_TITLE_MISSING')

    def test_30_wrong_check_name_must_hold(self):
        self.reject('name', 'made-up-check', 'PUBLISH_CHECK_NAME_MISMATCH')

    def test_31_noncompleted_must_hold(self):
        self.reject('status', 'queued', 'PUBLISH_STATUS_NOT_COMPLETED')


if __name__ == '__main__':
    unittest.main()
