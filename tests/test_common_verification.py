"""
tests/test_common_verification.py — the shared "passed 7.2 verification" predicate.

Verification is a FACT recorded in repo["history"], not a snapshot of `status`:
`status` is one field shared across chapters, and 5.5 overwrites it on the way to
`approved`. These tests pin that distinction.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.conftest import setup_mocks

setup_mocks()

from skills.common import has_passed_verification, was_verification_forced


def _repo(requirements=None, history=None):
    return {
        "project": "test_project",
        "requirements": requirements or [],
        "links": [],
        "history": history or [],
    }


class TestHasPassedVerification(unittest.TestCase):

    def test_history_entry_counts_as_verified(self):
        repo = _repo(
            requirements=[{"id": "FR-001", "status": "pending_approval"}],
            history=[{"action": "req_verified", "req_id": "FR-001"}],
        )
        self.assertTrue(has_passed_verification(repo, "FR-001"))

    def test_verified_status_counts_for_legacy_repos(self):
        """A repo predating the history record still proves it via the status."""
        repo = _repo(requirements=[{"id": "FR-001", "status": "verified"}])
        self.assertTrue(has_passed_verification(repo, "FR-001"))

    def test_forced_verification_still_counts_as_verified(self):
        """force=true is a RECORDED BA decision (B1), not an absence of one."""
        repo = _repo(
            requirements=[{"id": "FR-001", "status": "verified"}],
            history=[{"action": "req_verified", "req_id": "FR-001",
                      "forced": True, "overridden_blockers": ["VI-001"]}],
        )
        self.assertTrue(has_passed_verification(repo, "FR-001"))

    def test_never_verified_is_false(self):
        repo = _repo(requirements=[{"id": "FR-001", "status": "draft"}])
        self.assertFalse(has_passed_verification(repo, "FR-001"))

    def test_history_of_another_req_does_not_leak(self):
        repo = _repo(
            requirements=[{"id": "FR-001", "status": "draft"},
                          {"id": "FR-002", "status": "draft"}],
            history=[{"action": "req_verified", "req_id": "FR-002"}],
        )
        self.assertFalse(has_passed_verification(repo, "FR-001"))

    def test_other_history_actions_do_not_count(self):
        repo = _repo(
            requirements=[{"id": "FR-001", "status": "draft"}],
            history=[{"action": "baselined", "req_id": "FR-001"}],
        )
        self.assertFalse(has_passed_verification(repo, "FR-001"))

    def test_verified_then_approved_is_still_verified(self):
        """The B2 case: 5.5 overwrote the status, the fact survives in history."""
        repo = _repo(
            requirements=[{"id": "FR-001", "status": "approved"}],
            history=[{"action": "req_verified", "req_id": "FR-001"}],
        )
        self.assertTrue(has_passed_verification(repo, "FR-001"))

    def test_missing_history_key_does_not_crash(self):
        repo = {"project": "p", "requirements": [{"id": "FR-001", "status": "verified"}]}
        self.assertTrue(has_passed_verification(repo, "FR-001"))


class TestWasVerificationForced(unittest.TestCase):

    def test_forced_entry_is_reported(self):
        repo = _repo(history=[{"action": "req_verified", "req_id": "FR-001", "forced": True}])
        self.assertTrue(was_verification_forced(repo, "FR-001"))

    def test_clean_entry_is_not_forced(self):
        repo = _repo(history=[{"action": "req_verified", "req_id": "FR-001"}])
        self.assertFalse(was_verification_forced(repo, "FR-001"))

    def test_legacy_status_only_is_not_forced(self):
        repo = _repo(requirements=[{"id": "FR-001", "status": "verified"}])
        self.assertFalse(was_verification_forced(repo, "FR-001"))


if __name__ == "__main__":
    unittest.main()
