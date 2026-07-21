"""
tests/test_common_approval.py — a durable approval predicate, symmetric with the
verification one.

THE PROBLEM. `status` is ONE field written by four chapters:

    7.1 draft -> 7.2 verified -> 5.5 pending_approval/approved -> 7.3 validated

so the last writer wins and any consumer asking "was this approved?" by reading
`status` gets the answer only until some other chapter moves the requirement on.
Verification already has a durable answer (`has_passed_verification`, reading the
`req_verified` record 7.2 appends to repo["history"]). Approval had none.

WHY THE OBVIOUS SOURCES DO NOT WORK.
  * `node["history"]` — 5.5 appends there, but only when the status actually
    CHANGES. A requirement approved while already sitting in `approved` writes
    nothing, so the record is lossy by construction.
  * `repo["history"]` — symmetric with verification, but it would be a SECOND copy
    of decisions that already live, in full, somewhere else.

WHERE THE EVIDENCE ACTUALLY IS. 5.5 has written `{project}_approval_history.json`
all along: every package, every stakeholder, every per-requirement decision and the
RACI it was cast under. Nothing was ever lost — the predicate simply never read it.
So the outcome is RECOMPUTED from the decisions themselves, and no migration is
needed: the file exists for every project that has ever run 5.5.

THREE STATES, following the B2-bis precedent. A project with no approval history at
all is `unknown`, not `not_submitted`: telling a BA "this was not approved" about a
project whose records predate the feature is a lie, and the same distinction was
already needed for verification.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import setup_mocks, BaseMCPTest

setup_mocks()

from skills.common import (approval_outcome, has_been_approved,
                           compute_approval_outcome, normalize_project_id,
                           APPROVAL_OUTCOME_UNKNOWN, APPROVAL_OUTCOME_NOT_SUBMITTED)

PID = "approvals"


def _package(decisions, req_ids=("FR-001",)):
    """A package record shaped exactly as 5.5 writes it."""
    return {
        "package_id": "PKG-001",
        "req_ids": list(req_ids),
        "created_date": "2026-07-01",
        "stakeholder_decisions": decisions,
        "baseline_version": None,
        "status": "open",
    }


def _sh(raci, decision, req_id="FR-001", condition_closed=False):
    return {
        "raci": raci,
        "req_decisions": [
            {"req_id": req_id, "decision": decision,
             "condition_closed": condition_closed},
        ],
    }


class TestTheFoldIsSharedNotCopied(unittest.TestCase):
    """5.5's `_compute_req_status` and the shared predicate must be the SAME code.

    Two copies of one decision rule is the defect class that already bit 5.5 once —
    the dashboard verdict and the baseline gate drifted apart and a package the
    dashboard called "Not ready" baselined cleanly.
    """

    def test_five_five_delegates_to_the_shared_fold(self):
        import skills.requirements_approve_mcp as t55
        pkg = _package({"Ivan": _sh("accountable", "approved")})
        self.assertEqual(t55._compute_req_status("FR-001", pkg),
                         compute_approval_outcome(pkg, "FR-001"))

    def test_an_accountable_yes_approves(self):
        self.assertEqual(
            compute_approval_outcome(_package({"Ivan": _sh("accountable", "approved")}),
                                     "FR-001"),
            "approved")

    def test_an_accountable_rejection_wins(self):
        pkg = _package({"Ivan": _sh("accountable", "approved"),
                        "Olga": _sh("responsible", "rejected")})
        self.assertEqual(compute_approval_outcome(pkg, "FR-001"), "rejected")

    def test_everyone_abstaining_is_not_an_approval(self):
        """B3: an approval record with no approver."""
        pkg = _package({"Ivan": _sh("accountable", "abstained")})
        self.assertEqual(compute_approval_outcome(pkg, "FR-001"), "pending_approval")


class TestApprovalOutcomeReadsTheDurableFile(BaseMCPTest):

    def _write_history(self, packages):
        safe = normalize_project_id(PID)
        path = os.path.join("governance_plans", "data", safe,
                            f"{safe}_approval_history.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"project": PID, "packages": packages, "baselines": []}, f)

    def test_no_history_file_at_all_is_unknown(self):
        """A legacy project. Answering `not approved` would be an assertion the
        records cannot support."""
        self.assertEqual(approval_outcome(PID, "FR-001"), APPROVAL_OUTCOME_UNKNOWN)
        self.assertFalse(has_been_approved(PID, "FR-001"))

    def test_a_requirement_in_no_package_is_not_submitted(self):
        """Distinct from `unknown`: here the records DO exist and simply do not
        cover this requirement."""
        self._write_history({"PKG-001": _package(
            {"Ivan": _sh("accountable", "approved", req_id="FR-999")},
            req_ids=["FR-999"])})
        self.assertEqual(approval_outcome(PID, "FR-001"),
                         APPROVAL_OUTCOME_NOT_SUBMITTED)
        self.assertFalse(has_been_approved(PID, "FR-001"))

    def test_an_approved_requirement_is_approved(self):
        self._write_history({"PKG-001": _package(
            {"Ivan": _sh("accountable", "approved")})})
        self.assertEqual(approval_outcome(PID, "FR-001"), "approved")
        self.assertTrue(has_been_approved(PID, "FR-001"))

    def test_the_verdict_survives_a_later_status_overwrite(self):
        """THE POINT OF THE WHOLE EXERCISE. 7.3 moves an approved requirement to
        `validated`; the node's status no longer says `approved`, and every consumer
        reading the status silently loses the approval."""
        self._write_history({"PKG-001": _package(
            {"Ivan": _sh("accountable", "approved")})})
        safe = normalize_project_id(PID)
        repo_path = os.path.join("governance_plans", "data", safe,
                                 f"{safe}_traceability_repo.json")
        with open(repo_path, "w", encoding="utf-8") as f:
            json.dump({"project": PID, "links": [], "requirements": [
                {"id": "FR-001", "type": "functional", "title": "X",
                 "status": "validated"}]}, f)
        self.assertTrue(
            has_been_approved(PID, "FR-001"),
            "the approval survived only in the node status, which 7.3 overwrote",
        )

    def test_a_rejected_requirement_is_not_approved(self):
        self._write_history({"PKG-001": _package(
            {"Ivan": _sh("accountable", "rejected")})})
        self.assertEqual(approval_outcome(PID, "FR-001"), "rejected")
        self.assertFalse(has_been_approved(PID, "FR-001"))

    def test_a_conditional_approval_is_not_folded_into_approved(self):
        """An open condition is not a signature. Callers that want to treat it as
        one must say so explicitly."""
        self._write_history({"PKG-001": _package(
            {"Ivan": _sh("accountable", "conditional")})})
        self.assertEqual(approval_outcome(PID, "FR-001"), "conditional_approved")
        self.assertFalse(has_been_approved(PID, "FR-001"))

    def test_the_latest_package_decides(self):
        """A requirement re-submitted after a rejection is governed by the newer
        round, not by whichever package happens to be first in the file."""
        old = _package({"Ivan": _sh("accountable", "rejected")})
        old["package_id"], old["created_date"] = "PKG-001", "2026-07-01"
        new = _package({"Ivan": _sh("accountable", "approved")})
        new["package_id"], new["created_date"] = "PKG-002", "2026-07-15"
        self._write_history({"PKG-001": old, "PKG-002": new})
        self.assertEqual(approval_outcome(PID, "FR-001"), "approved")

    def test_a_corrupt_history_file_reports_unknown_and_does_not_crash(self):
        """Same graceful-degradation contract as load_stakeholder_registry: a
        damaged file must not turn a report into a protocol error."""
        safe = normalize_project_id(PID)
        path = os.path.join("governance_plans", "data", safe,
                            f"{safe}_approval_history.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("{ this is not json")
        self.assertEqual(approval_outcome(PID, "FR-001"), APPROVAL_OUTCOME_UNKNOWN)


class TestConsumersStopJudgingByTheMutableStatus(BaseMCPTest):
    """The consumers that asked "was this approved?" and read `status` to find out.

    Each is set up in the state that used to lose the answer: 5.5 approved the
    requirement, then 7.3 validated it and overwrote the status.
    """

    def setUp(self):
        super().setUp()
        safe = normalize_project_id(PID)
        base = os.path.join("governance_plans", "data", safe)
        os.makedirs(base, exist_ok=True)
        with open(os.path.join(base, f"{safe}_approval_history.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"project": PID, "baselines": [], "packages": {
                "PKG-001": _package({"Ivan": _sh("accountable", "approved")})}}, f)
        with open(os.path.join(base, f"{safe}_traceability_repo.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"project": PID, "links": [], "history": [], "requirements": [
                {"id": "FR-001", "type": "functional", "title": "Pre-fill from CRM",
                 "version": "1.0", "status": "validated"},
                {"id": "FR-002", "type": "functional", "title": "Export the log",
                 "version": "1.0", "status": "draft"},
            ]}, f)

    def test_72_report_still_counts_the_approval_after_73_validated_it(self):
        import skills.requirements_verify_mcp as t72
        out = t72.get_verification_report(PID)
        self.assertIn("| ✅ Approved in 5.5 | 1 |", out)

    def test_51_matrix_does_not_drop_an_approved_requirement(self):
        """This document goes into the approval package a stakeholder signs."""
        import skills.requirements_traceability_mcp as t51
        out = t51.export_traceability_matrix(PID, filter_status="approved")
        self.assertIn("FR-001", out)
        self.assertNotIn("FR-002", out)

    def test_52_reuse_scoring_still_credits_the_approval(self):
        import skills.requirements_maintain_mcp as t52
        out = t52.find_reusable_requirements(PID)
        self.assertIn("Approved in 5.5", out)


class TestVerificationReportIsHonestWhenThereAreNoRecords(BaseMCPTest):

    def test_no_approval_history_reports_unknown_not_zero(self):
        """"0 approved" and "5.5 has not run" are different statements, and only
        one of them is supported by a project with no approval records."""
        import skills.requirements_verify_mcp as t72
        safe = normalize_project_id(PID)
        base = os.path.join("governance_plans", "data", safe)
        os.makedirs(base, exist_ok=True)
        with open(os.path.join(base, f"{safe}_traceability_repo.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"project": PID, "links": [], "history": [], "requirements": [
                {"id": "FR-001", "type": "functional", "title": "X",
                 "version": "1.0", "status": "draft"}]}, f)
        out = t72.get_verification_report(PID)
        self.assertIn("5.5 has not run", out)


if __name__ == "__main__":
    unittest.main()
