"""
tests/test_ch7_72_preserves_approval.py

`status` is one field shared by four chapters (7.1 draft -> 7.2 verified -> 5.5
pending_approval/approved -> 7.3 validated), so whoever writes last wins. B2 and B2-bis
already fixed one direction of this: verification is read from the DURABLE
`req_verified` history record, never from the mutable status.

The mirror was still open. Re-verifying a requirement that 5.5 had baselined printed
"verified (was: approved)" and overwrote the approval, with no warning — and unlike
verification, approval has no durable predicate to fall back on, so the fact was simply
gone. The traceability matrix filtered by `approved` then lost it.

Since verification no longer depends on the status field, there is nothing to gain by
overwriting a stronger one. Record the verification in history and leave the approval
standing.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.conftest import setup_mocks

setup_mocks()

import skills.requirements_verify_mcp as v72
from skills.common import has_passed_verification


def repo_with(status):
    return {
        "project": "p",
        "requirements": [
            {"id": "FR-001", "type": "functional", "title": "Pre-fill from CRM",
             "version": "1.0", "status": status},
        ],
        "links": [], "history": [],
    }


class TestVerificationPreservesApproval(unittest.TestCase):

    def _run(self, status):
        self.repo = repo_with(status)
        orig_load, orig_save = v72._load_repo, v72._save_repo
        orig_issues = v72._load_issues
        v72._load_repo = lambda project_id: self.repo
        v72._save_repo = lambda repo: None
        v72._load_issues = lambda project_id: {
            "project": "p", "issues": {}, "stats": {"open": 0, "closed": 0, "total": 0}}
        try:
            return v72.mark_req_verified("p", json.dumps(["FR-001"]))
        finally:
            v72._load_repo, v72._save_repo = orig_load, orig_save
            v72._load_issues = orig_issues

    def test_an_approved_requirement_keeps_its_status(self):
        self._run("approved")
        self.assertEqual(
            self.repo["requirements"][0]["status"], "approved",
            "7.2 overwrote the approval 5.5 recorded — and approval has no durable "
            "predicate to recover it from",
        )

    def test_the_verification_is_still_recorded_durably(self):
        self._run("approved")
        self.assertTrue(
            has_passed_verification(self.repo, "FR-001"),
            "the verification must still be recorded, just not by clobbering the status",
        )

    def test_the_analyst_is_told_the_status_was_left_alone(self):
        out = self._run("approved")
        self.assertIn("FR-001", out)
        self.assertIn("approved", out.lower())

    def test_a_draft_still_becomes_verified(self):
        self._run("draft")
        self.assertEqual(self.repo["requirements"][0]["status"], "verified")

    def test_pending_approval_is_not_a_stronger_status(self):
        """5.5 sets pending_approval on every requirement when a package opens; that is
        process state, not an outcome, so verification may still advance it."""
        self._run("pending_approval")
        self.assertEqual(self.repo["requirements"][0]["status"], "verified")


if __name__ == "__main__":
    unittest.main()
