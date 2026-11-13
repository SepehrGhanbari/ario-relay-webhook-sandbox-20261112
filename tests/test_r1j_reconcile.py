"""R1j mock-only adversarial tests. Never issues GitHub writes or reads secrets."""
from dataclasses import replace
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from r1j_reconcile import (
    APP_ID, CHECK_NAME, REPO, EvidenceError, Intent, exclusive_post_intent,
    reconcile
)

HEAD = "508a6abfacf534fa01a4b97210c35b35ca965c86"
BASE = "be7c16d964872f88ddb9029f2677c49a7cd745ba"
EXT = "R1I-LAB-ONLY:PR14:" + HEAD + ":RUN43484108692"


def intent(**kwargs):
    data = dict(repo=REPO, pr_number=14, head_sha=HEAD, base_sha=BASE,
                name=CHECK_NAME, app_id=APP_ID, external_id=EXT,
                conclusion="success", returned_check_id=None)
    data.update(kwargs)
    return Intent(**data)


def pr(**updates):
    result = {
        "number": 14, "state": "open", "merged": False, "draft": True,
        "head": {"sha": HEAD, "repo": {"full_name": REPO}},
        "base": {"sha": BASE, "repo": {"full_name": REPO},
                 "ref": "experiment/r1d-required-app-rule-20261113"}
    }
    result.update(updates)
    return result


def check(**updates):
    result = {
        "id": 132094820201, "name": CHECK_NAME, "head_sha": HEAD,
        "status": "completed", "conclusion": "success", "app": {"id": APP_ID},
        "external_id": EXT
    }
    result.update(updates)
    return result


class FakeAPI:
    def __init__(self, pages=None, prs=None, direct=None, fail_first=False):
        self.pages = pages or [[check()]]
        self.prs = prs or [pr()]
        self.direct = direct
        self.fail_first = fail_first
        self.calls = []
        self.scans = 0
        self.pr_reads = 0

    def __call__(self, method, url, **kwargs):
        self.calls.append((method, url))
        if method != "GET":
            raise AssertionError("WRITE_ATTEMPTED")
        if self.fail_first:
            self.fail_first = False
            raise ConnectionError("GitHub temporarily unavailable")
        if "/pulls/" in url:
            value = self.prs[min(self.pr_reads, len(self.prs)-1)]
            self.pr_reads += 1
            return copy.deepcopy(value)
        if "/check-runs/" in url:
            if self.direct is None:
                raise ConnectionError("individual check temporarily unavailable")
            return copy.deepcopy(self.direct)
        if "?filter=all&check_name=" in url:
            assert "&per_page=100&page=" in url
            page = int(url.rsplit("page=", 1)[1])
            if page != 1:
                response = self.pages[min(self.scans, len(self.pages)-1)]
            else:
                response = self.pages[min(self.scans, len(self.pages)-1)]
                self.scans += 1
            if isinstance(response, dict):
                return copy.deepcopy(response)
            return {"total_count": len(response), "check_runs": copy.deepcopy(response)}
        raise AssertionError("UNEXPECTED_ENDPOINT:" + url)


class R1jNoRepostReconciliationTests(unittest.TestCase):
    def guard(self, api, expected="CONFIRMED_EXISTING_CHECK", **kwargs):
        out = reconcile(api, intent(**kwargs), observations=3)
        self.assertEqual(out["verdict"], expected)
        self.assertIs(out["repeat_post_allowed"], False)
        self.assertEqual(out["production_trust"], "NO_GO")
        self.assertTrue(all(method == "GET" for method, _ in api.calls))
        if expected != "CONFIRMED_EXISTING_CHECK":
            self.assertIsNone(out["published"])
        return out

    def test_01_found_existing_success_by_app_and_sha(self):
        out = self.guard(FakeAPI())
        self.assertEqual(out["check_run_id"], 132094820201)

    def test_02_first_list_empty_then_visible_without_post(self):
        api = FakeAPI(pages=[[], [check()]])
        out = self.guard(api)
        self.assertTrue(api.scans >= 2)
        self.assertEqual(out["check_run_id"], 132094820201)

    def test_03_no_result_is_unknown_not_not_published(self):
        self.guard(FakeAPI(pages=[[]]), "UNKNOWN_POST_OUTCOME_HOLD")

    def test_04_exact_returned_id_is_checked(self):
        self.guard(FakeAPI(direct=check()), returned_check_id=132094820201)

    def test_05_direct_check_before_list_is_not_sufficient(self):
        api = FakeAPI(pages=[[]], direct=check())
        self.guard(api, "UNKNOWN_POST_OUTCOME_HOLD", returned_check_id=132094820201)

    def test_06_duplicate_external_ids_hold(self):
        api = FakeAPI(pages=[[check(), check(id=132094820202)]])
        self.guard(api, "CONFLICT_HOLD")

    def test_07_wrong_app_same_external_id_hold(self):
        self.guard(FakeAPI(pages=[[check(app={"id": 15368})]]), "CONFLICT_HOLD")

    def test_08_neutral_same_external_id_hold(self):
        self.guard(FakeAPI(pages=[[check(conclusion="neutral")]]), "CONFLICT_HOLD")

    def test_09_skipped_same_external_id_hold(self):
        self.guard(FakeAPI(pages=[[check(conclusion="skipped")]]), "CONFLICT_HOLD")

    def test_10_old_head_same_external_id_hold(self):
        self.guard(FakeAPI(pages=[[check(head_sha="a"*40)]]), "CONFLICT_HOLD")

    def test_11_wrong_check_name_same_external_id_hold(self):
        self.guard(FakeAPI(pages=[[check(name="forged")]]), "CONFLICT_HOLD")

    def test_12_wrong_external_id_is_not_ours(self):
        self.guard(FakeAPI(pages=[[check(external_id="fake")]]),
                   "UNKNOWN_POST_OUTCOME_HOLD")

    def test_13_post_id_disagrees_with_list_hold(self):
        self.guard(FakeAPI(direct=check(), pages=[[check(id=99999)]]),
                   "CONFLICT_HOLD", returned_check_id=132094820201)

    def test_14_direct_wrong_id_or_conclusion_hold(self):
        self.guard(FakeAPI(direct=check(conclusion="failure")),
                   "CONFLICT_HOLD", returned_check_id=132094820201)

    def test_15_first_pr_read_network_failure_then_success(self):
        self.guard(FakeAPI(fail_first=True))

    def test_16_head_moved_after_post_hold(self):
        changed = pr(head={"sha": "f"*40, "repo": {"full_name": REPO}})
        self.guard(FakeAPI(prs=[changed]), "STALE_PR_HOLD")

    def test_17_base_moved_after_post_hold(self):
        changed = pr(base={"sha": "f"*40, "repo": {"full_name": REPO}})
        self.guard(FakeAPI(prs=[changed]), "STALE_PR_HOLD")

    def test_18_cross_repo_pr_hold(self):
        changed = pr(head={"sha": HEAD, "repo": {"full_name": "attacker/fork"}})
        self.guard(FakeAPI(prs=[changed]), "CONFLICT_HOLD")

    def test_19_malformed_check_page_inconclusive(self):
        self.guard(FakeAPI(pages=[{"total_count": 1, "check_runs": "bad"}]),
                   "UNKNOWN_POST_OUTCOME_HOLD")

    def test_20_paginated_list_finds_later_page(self):
        unrelated = [check(id=i+10, external_id="unrelated-"+str(i)) for i in range(100)]
        class PagedFake(FakeAPI):
            def __call__(self, method, url, **kw):
                if "&page=1" in url:
                    self.calls.append((method,url))
                    return {"total_count": 101, "check_runs": copy.deepcopy(unrelated)}
                if "&page=2" in url:
                    self.calls.append((method,url))
                    return {"total_count": 101, "check_runs": [check()]}
                return super().__call__(method,url,**kw)
        self.guard(PagedFake())

    def test_21_unexhaustive_list_over_limit_is_unknown(self):
        class TooMany(FakeAPI):
            def __call__(self, method, url, **kw):
                if "page=" in url:
                    self.calls.append((method,url))
                    page = int(url.rsplit("page=",1)[1])
                    return {"total_count": 600, "check_runs": [
                        check(id=page*100+i+100000,
                              external_id="other-"+str(page)+"-"+str(i))
                        for i in range(100)
                    ]}
                return super().__call__(method,url,**kw)
        self.guard(TooMany(), "UNKNOWN_POST_OUTCOME_HOLD")

    def test_22_boolean_id_must_not_pass(self):
        self.guard(FakeAPI(pages=[[check(id=True)]]), "CONFLICT_HOLD")

    def test_23_invalid_context_does_not_call_api(self):
        api = FakeAPI()
        self.guard(api, "HOLD", name="fake")
        self.assertEqual(api.calls, [])

    def test_24_invalid_external_id_does_not_call_api(self):
        api = FakeAPI()
        self.guard(api, "HOLD", external_id="fake")
        self.assertEqual(api.calls, [])

    def test_25_invalid_observation_budget_is_hold(self):
        api = FakeAPI()
        out = reconcile(api, intent(), observations=0)
        self.assertEqual(out["verdict"], "HOLD")
        self.assertEqual(api.calls, [])

    def test_26_journal_exclusive_and_durable(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "no-repost.json"
            exclusive_post_intent(path, intent())
            record = json.loads(path.read_text())
            self.assertTrue(record["no_repost"])
            self.assertEqual(record["head_sha"], HEAD)
            with self.assertRaisesRegex(EvidenceError, "JOURNAL_EXISTS_NO_REPOST"):
                exclusive_post_intent(path, intent())
            self.assertEqual(json.loads(path.read_text()), record)

    def test_27_journal_missing_parent_hold(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "missing" / "intent.json"
            with self.assertRaisesRegex(EvidenceError, "JOURNAL_DIRECTORY_MISSING"):
                exclusive_post_intent(path, intent())

    def test_28_journal_invalid_scope_no_write(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "intent.json"
            with self.assertRaisesRegex(EvidenceError, "REPO_OUT_OF_SCOPE"):
                exclusive_post_intent(path, intent(repo="SepehrGhanbari/Ario"))
            self.assertFalse(path.exists())

    def test_29_found_wrong_status_is_conflict(self):
        self.guard(FakeAPI(pages=[[check(status="in_progress")]]), "CONFLICT_HOLD")

    def test_30_reconcile_does_not_require_known_post_id(self):
        # A transport exception AFTER the actual POST may leave no check ID;
        # external-id matching can still discover it without resubmission.
        api = FakeAPI()
        out = self.guard(api)
        self.assertEqual(out["check_run_id"], 132094820201)


if __name__ == "__main__":
    unittest.main()
