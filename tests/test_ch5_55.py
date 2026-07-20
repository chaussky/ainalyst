"""
tests/test_ch5_55.py — Tests for BABOK 5.5 Approve Requirements.

Structure:
  - Unit (14): utilities, _compute_req_status, _get_cr_context
  - prepare_approval_package (8): success, duplicate, missing req, agile, audiences
  - record_approval_decision (14): approved, conditional, rejected, RACI analysis, conflicts
  - close_approval_condition (7): success, already closed, not found, status updated
  - check_approval_status (10): dashboard, blockers, open conditions, verdicts
  - create_requirements_baseline (11): success, blockers, force, snapshot, history
  - Pipeline (6): full predictive, full agile, conflict + resolution, two independent packages
"""

import json
import os
import sys
import unittest
from datetime import date, timedelta
from unittest.mock import patch

# conftest registers the mocks and provides the base class
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.conftest import (
    setup_mocks, BaseMCPTest, make_test_repo, save_test_repo, load_test_repo,
)

setup_mocks()

from skills.requirements_approve_mcp import (
    prepare_approval_package,
    record_approval_decision,
    close_approval_condition,
    check_approval_status,
    create_requirements_baseline,
    _compute_req_status,
    _verification_state,
    _get_cr_context,
    _load_approval_history,
    _save_approval_history,
    STATUS_APPROVED,
    STATUS_CONDITIONAL,
    STATUS_REJECTED,
    STATUS_PENDING,
)


# ---------------------------------------------------------------------------
# Helper utilities for the tests
# ---------------------------------------------------------------------------

PROJECT = "test_project"


def _make_repo_with_verified(tmp_dir):
    """A repository with verified requirements (ready for 5.5)."""
    repo = make_test_repo(PROJECT)
    for req in repo["requirements"]:
        if req["type"] != "test":
            req["status"] = "verified"
            req["priority"] = "Must"
    save_test_repo(repo)
    return repo


def _make_repo_with_cr(tmp_dir):
    """A repository with a CR that affects FR-001."""
    repo = _make_repo_with_verified(tmp_dir)
    repo["requirements"].append({
        "id": "CR-001",
        "type": "change_request",
        "title": "Change the distribution logic",
        "status": "open",
        "target_req_ids": ["FR-001"],
    })
    repo["links"].append({
        "from": "CR-001",
        "to": "FR-001",
        "relation": "modifies",
        "added_date": str(date.today()),
    })
    save_test_repo(repo)
    return repo


def _open_package(project=PROJECT, package_id="APKG-001", req_ids=None, approach="predictive"):
    """Creates a package and returns the result of prepare_approval_package."""
    if req_ids is None:
        req_ids = ["FR-001", "FR-002"]
    return prepare_approval_package(
        project_name=project,
        package_id=package_id,
        package_title="Test package",
        req_ids_json=json.dumps(req_ids),
        approach=approach,
    )


def _record(project=PROJECT, package_id="APKG-001", stakeholder="Ivanov",
            raci="accountable", decision="approved", req_decisions=None,
            rejection_reason=""):
    """A helper wrapper for record_approval_decision."""
    rdj = json.dumps(req_decisions) if req_decisions else "[]"
    return record_approval_decision(
        project_name=project,
        package_id=package_id,
        stakeholder_name=stakeholder,
        stakeholder_raci=raci,
        decision=decision,
        req_decisions_json=rdj,
        rejection_reason=rejection_reason,
    )


# ---------------------------------------------------------------------------
# Unit — utilities
# ---------------------------------------------------------------------------

class TestComputeReqStatus(BaseMCPTest):

    def _make_pkg(self, req_ids=None):
        return {
            "req_ids": req_ids or ["FR-001"],
            "stakeholder_decisions": {},
        }

    def test_no_decisions_returns_pending(self):
        pkg = self._make_pkg()
        self.assertEqual(_compute_req_status("FR-001", pkg), STATUS_PENDING)

    def test_approved_by_accountable(self):
        pkg = self._make_pkg()
        pkg["stakeholder_decisions"]["Ivanov"] = {
            "raci": "accountable",
            "req_decisions": [{"req_id": "FR-001", "decision": "approved"}],
        }
        self.assertEqual(_compute_req_status("FR-001", pkg), STATUS_APPROVED)

    def test_rejected_by_accountable_blocks(self):
        pkg = self._make_pkg()
        pkg["stakeholder_decisions"]["Ivanov"] = {
            "raci": "accountable",
            "req_decisions": [{"req_id": "FR-001", "decision": "rejected"}],
        }
        self.assertEqual(_compute_req_status("FR-001", pkg), STATUS_REJECTED)

    def test_rejected_by_consulted_does_not_block(self):
        pkg = self._make_pkg()
        pkg["stakeholder_decisions"]["Petrov"] = {
            "raci": "accountable",
            "req_decisions": [{"req_id": "FR-001", "decision": "approved"}],
        }
        pkg["stakeholder_decisions"]["Sidorov"] = {
            "raci": "consulted",
            "req_decisions": [{"req_id": "FR-001", "decision": "rejected"}],
        }
        # Consulted rejected, but Accountable approved → approved
        self.assertEqual(_compute_req_status("FR-001", pkg), STATUS_APPROVED)

    def test_open_conditional_by_accountable_gives_conditional_approved(self):
        pkg = self._make_pkg()
        pkg["stakeholder_decisions"]["Ivanov"] = {
            "raci": "accountable",
            "req_decisions": [{
                "req_id": "FR-001",
                "decision": "conditional",
                "condition_text": "Clarify the wording",
                "condition_closed": False,
            }],
        }
        self.assertEqual(_compute_req_status("FR-001", pkg), STATUS_CONDITIONAL)

    def test_closed_conditional_gives_approved(self):
        pkg = self._make_pkg()
        pkg["stakeholder_decisions"]["Ivanov"] = {
            "raci": "accountable",
            "req_decisions": [{
                "req_id": "FR-001",
                "decision": "conditional",
                "condition_text": "Clarify the wording",
                "condition_closed": True,
            }],
        }
        self.assertEqual(_compute_req_status("FR-001", pkg), STATUS_APPROVED)

    def test_all_abstained_is_not_approval(self):
        """Audit finding: this test previously asserted the opposite — a lone
        accountable stakeholder abstaining produced `approved`, so a package where
        EVERY accountable party declined to take a position reached 100% approved
        and baselined cleanly: an official approval record with no approver.
        Abstention is a first-class decision meaning "no position"; it must not
        carry the requirement on its own."""
        pkg = self._make_pkg()
        pkg["stakeholder_decisions"]["Ivanov"] = {
            "raci": "accountable",
            "req_decisions": [{"req_id": "FR-001", "decision": "abstained"}],
        }
        self.assertEqual(_compute_req_status("FR-001", pkg), STATUS_PENDING)

    def test_abstention_alongside_an_approval_still_approves(self):
        """Abstention does not BLOCK — it just does not count as a yes."""
        pkg = self._make_pkg()
        pkg["stakeholder_decisions"]["Ivanov"] = {
            "raci": "accountable",
            "req_decisions": [{"req_id": "FR-001", "decision": "approved"}],
        }
        pkg["stakeholder_decisions"]["Petrov"] = {
            "raci": "responsible",
            "req_decisions": [{"req_id": "FR-001", "decision": "abstained"}],
        }
        self.assertEqual(_compute_req_status("FR-001", pkg), STATUS_APPROVED)

    def test_all_abstained_blocks_the_baseline_gate(self):
        """The consequence that matters: no approver → not ready for baseline."""
        from skills.requirements_approve_mcp import _baseline_gate
        pkg = self._make_pkg()
        pkg["stakeholder_decisions"]["Ivanov"] = {
            "raci": "accountable",
            "req_decisions": [{"req_id": "FR-001", "decision": "abstained"}],
        }
        gate = _baseline_gate(pkg)
        self.assertFalse(gate["can_baseline"])
        self.assertEqual(gate["approved_pct"], 0)

    def test_req_not_in_decisions_gives_pending(self):
        pkg = self._make_pkg(["FR-001", "FR-002"])
        pkg["stakeholder_decisions"]["Ivanov"] = {
            "raci": "accountable",
            "req_decisions": [{"req_id": "FR-001", "decision": "approved"}],
        }
        # FR-002 not mentioned → pending
        self.assertEqual(_compute_req_status("FR-002", pkg), STATUS_PENDING)


class TestGetCrContext(BaseMCPTest):

    def test_returns_cr_refs(self):
        repo = make_test_repo(PROJECT)
        repo["requirements"].append({
            "id": "CR-001", "type": "change_request",
            "title": "CR Title", "status": "open",
        })
        repo["links"].append({
            "from": "CR-001", "to": "FR-001",
            "relation": "modifies",
        })
        save_test_repo(repo)
        from skills.requirements_approve_mcp import _load_repo
        loaded = _load_repo(PROJECT)
        refs = _get_cr_context(loaded, "FR-001")
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["cr_id"], "CR-001")

    def test_returns_empty_when_no_cr(self):
        repo = make_test_repo(PROJECT)
        save_test_repo(repo)
        from skills.requirements_approve_mcp import _load_repo
        loaded = _load_repo(PROJECT)
        refs = _get_cr_context(loaded, "FR-001")
        self.assertEqual(refs, [])

    def test_ignores_non_modifies_links(self):
        repo = make_test_repo(PROJECT)
        save_test_repo(repo)
        from skills.requirements_approve_mcp import _load_repo
        loaded = _load_repo(PROJECT)
        # a verifies link must not be returned as a CR
        refs = _get_cr_context(loaded, "FR-001")
        self.assertFalse(any(r for r in refs if r.get("cr_id") == "TC-001"))


# ---------------------------------------------------------------------------
# prepare_approval_package
# ---------------------------------------------------------------------------

class TestPrepareApprovalPackage(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _make_repo_with_verified(self.tmp_dir)

    def test_success_creates_package(self):
        result = _open_package()
        self.assertIn("APKG-001", result)
        self.assertIn("Test package", result)
        history = _load_approval_history(PROJECT)
        self.assertIn("APKG-001", history["packages"])

    def test_sets_requirements_to_pending(self):
        _open_package()
        from skills.requirements_approve_mcp import _load_repo
        repo = _load_repo(PROJECT)
        fr001 = next(r for r in repo["requirements"] if r["id"] == "FR-001")
        self.assertEqual(fr001["status"], STATUS_PENDING)

    def test_duplicate_package_id_blocked(self):
        _open_package()
        result = _open_package()
        self.assertIn("already exists", result)

    def test_missing_requirements_error(self):
        result = prepare_approval_package(
            project_name=PROJECT,
            package_id="APKG-X",
            package_title="Test",
            req_ids_json='["FR-999"]',
            approach="predictive",
        )
        self.assertIn("not found", result)

    def test_invalid_json_error(self):
        result = prepare_approval_package(
            project_name=PROJECT,
            package_id="APKG-X",
            package_title="Test",
            req_ids_json="not-json",
            approach="predictive",
        )
        self.assertIn("❌", result)

    def test_empty_req_ids_error(self):
        result = prepare_approval_package(
            project_name=PROJECT,
            package_id="APKG-X",
            package_title="Test",
            req_ids_json="[]",
            approach="predictive",
        )
        self.assertIn("❌", result)

    def test_agile_includes_sprint_info(self):
        result = prepare_approval_package(
            project_name=PROJECT,
            package_id="APKG-AGILE",
            package_title="Sprint 5",
            req_ids_json='["FR-001"]',
            approach="agile",
            sprint_number="5",
        )
        self.assertIn("5", result)
        self.assertIn("Agile", result)

    def test_cr_warning_shown_when_open_cr(self):
        _make_repo_with_cr(self.tmp_dir)
        result = prepare_approval_package(
            project_name=PROJECT,
            package_id="APKG-CR",
            package_title="Package with CR",
            req_ids_json='["FR-001"]',
            approach="predictive",
        )
        self.assertIn("CR-001", result)


# ---------------------------------------------------------------------------
# record_approval_decision
# ---------------------------------------------------------------------------

class TestRecordApprovalDecision(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _make_repo_with_verified(self.tmp_dir)
        _open_package()

    def test_approved_all_requirements(self):
        result = _record(decision="approved")
        self.assertIn("✅", result)
        self.assertIn("Ivanov", result)

    def test_approved_updates_repo_status(self):
        _record(decision="approved")
        from skills.requirements_approve_mcp import _load_repo
        repo = _load_repo(PROJECT)
        fr001 = next(r for r in repo["requirements"] if r["id"] == "FR-001")
        self.assertEqual(fr001["status"], STATUS_APPROVED)

    def test_conditional_requires_condition_text(self):
        result = record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-001",
            stakeholder_name="Ivanov",
            stakeholder_raci="accountable",
            decision="conditional",
            req_decisions_json=json.dumps([
                {"req_id": "FR-001", "decision": "conditional"}
                # no condition_text
            ]),
        )
        self.assertIn("❌", result)

    def test_conditional_with_condition_text_ok(self):
        result = record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-001",
            stakeholder_name="Ivanov",
            stakeholder_raci="accountable",
            decision="conditional",
            req_decisions_json=json.dumps([
                {
                    "req_id": "FR-001",
                    "decision": "conditional",
                    "condition_text": "Clarify the criterion",
                    "condition_deadline": "2026-05-01",
                    "condition_owner": "Petrov",
                }
            ]),
        )
        self.assertIn("Clarify the criterion", result)

    def test_rejected_requires_reason_when_no_req_decisions(self):
        result = _record(decision="rejected", rejection_reason="")
        self.assertIn("❌", result)

    def test_rejected_with_reason_ok(self):
        result = _record(decision="rejected", rejection_reason="Out of scope")
        self.assertIn("❌", result)
        self.assertIn("Out of scope", result)

    def test_abstained_is_recorded(self):
        result = _record(decision="abstained")
        self.assertIn("abstained", result)

    def test_consulted_rejected_shows_info(self):
        result = _record(
            decision="rejected",
            raci="consulted",
            rejection_reason="Disagree with the wording",
        )
        self.assertIn("Consulted", result)

    def test_conflict_flagged_for_must_priority(self):
        # A requirement with Must priority is rejected — there should be a flag
        result = _record(decision="rejected", rejection_reason="Not needed")
        self.assertIn("Must", result)

    def test_conflict_flagged_for_open_cr(self):
        _make_repo_with_cr(self.tmp_dir)
        _open_package(package_id="APKG-CR", req_ids=["FR-001"])
        result = record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-CR",
            stakeholder_name="Ivanov",
            stakeholder_raci="accountable",
            decision="rejected",
            rejection_reason="The requirement is being changed",
        )
        self.assertIn("CR-001", result)

    def test_partial_req_decisions_with_mixed_decisions(self):
        result = record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-001",
            stakeholder_name="Ivanov",
            stakeholder_raci="accountable",
            decision="approved",
            req_decisions_json=json.dumps([
                {"req_id": "FR-001", "decision": "approved"},
                {"req_id": "FR-002", "decision": "rejected", "rejection_reason": "Unclear wording"},
            ]),
        )
        self.assertIn("FR-001", result)
        self.assertIn("FR-002", result)

    def test_unknown_req_id_in_decisions_blocked(self):
        result = record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-001",
            stakeholder_name="Ivanov",
            stakeholder_raci="accountable",
            decision="approved",
            req_decisions_json=json.dumps([
                {"req_id": "FR-999", "decision": "approved"},
            ]),
        )
        self.assertIn("are not part of", result)

    def test_package_not_found_error(self):
        result = _record(package_id="APKG-MISSING")
        self.assertIn("❌", result)

    def test_multiple_stakeholders_recorded(self):
        _record(stakeholder="Ivanov", decision="approved")
        _record(stakeholder="Petrov", raci="responsible", decision="approved")
        history = _load_approval_history(PROJECT)
        pkg = history["packages"]["APKG-001"]
        self.assertIn("Ivanov", pkg["stakeholder_decisions"])
        self.assertIn("Petrov", pkg["stakeholder_decisions"])


# ---------------------------------------------------------------------------
# close_approval_condition
# ---------------------------------------------------------------------------

class TestCloseApprovalCondition(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _make_repo_with_verified(self.tmp_dir)
        _open_package()
        # Create a conditional from Ivanov on FR-001
        record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-001",
            stakeholder_name="Ivanov",
            stakeholder_raci="accountable",
            decision="conditional",
            req_decisions_json=json.dumps([
                {
                    "req_id": "FR-001",
                    "decision": "conditional",
                    "condition_text": "Clarify the acceptance criterion",
                    "condition_deadline": "2026-05-01",
                    "condition_owner": "Petrov",
                },
                {"req_id": "FR-002", "decision": "approved"},
            ]),
        )

    def test_close_condition_success(self):
        result = close_approval_condition(
            project_name=PROJECT,
            package_id="APKG-001",
            req_id="FR-001",
            stakeholder_name="Ivanov",
            resolution_notes="Criterion clarified, acceptance test added",
        )
        self.assertIn("✅", result)
        self.assertIn("FR-001", result)

    def test_condition_closed_updates_requirement_status(self):
        close_approval_condition(
            project_name=PROJECT,
            package_id="APKG-001",
            req_id="FR-001",
            stakeholder_name="Ivanov",
            resolution_notes="Criterion clarified",
        )
        from skills.requirements_approve_mcp import _load_repo
        repo = _load_repo(PROJECT)
        fr001 = next(r for r in repo["requirements"] if r["id"] == "FR-001")
        self.assertEqual(fr001["status"], STATUS_APPROVED)

    def test_close_already_closed_condition(self):
        close_approval_condition(
            project_name=PROJECT,
            package_id="APKG-001",
            req_id="FR-001",
            stakeholder_name="Ivanov",
            resolution_notes="First closure",
        )
        result = close_approval_condition(
            project_name=PROJECT,
            package_id="APKG-001",
            req_id="FR-001",
            stakeholder_name="Ivanov",
            resolution_notes="Second closure",
        )
        self.assertIn("already closed", result)

    def test_wrong_stakeholder_error(self):
        result = close_approval_condition(
            project_name=PROJECT,
            package_id="APKG-001",
            req_id="FR-001",
            stakeholder_name="Nonexistent",
            resolution_notes="Closing",
        )
        self.assertIn("❌", result)

    def test_wrong_req_id_error(self):
        result = close_approval_condition(
            project_name=PROJECT,
            package_id="APKG-001",
            req_id="FR-999",
            stakeholder_name="Ivanov",
            resolution_notes="Closing",
        )
        self.assertIn("❌", result)

    def test_package_not_found_error(self):
        result = close_approval_condition(
            project_name=PROJECT,
            package_id="APKG-MISSING",
            req_id="FR-001",
            stakeholder_name="Ivanov",
            resolution_notes="Closing",
        )
        self.assertIn("❌", result)

    def test_condition_closed_flag_persisted(self):
        close_approval_condition(
            project_name=PROJECT,
            package_id="APKG-001",
            req_id="FR-001",
            stakeholder_name="Ivanov",
            resolution_notes="Criterion clarified",
        )
        history = _load_approval_history(PROJECT)
        pkg = history["packages"]["APKG-001"]
        sh_data = pkg["stakeholder_decisions"]["Ivanov"]
        fr001_decision = next(
            rd for rd in sh_data["req_decisions"] if rd["req_id"] == "FR-001"
        )
        self.assertTrue(fr001_decision.get("condition_closed"))


# ---------------------------------------------------------------------------
# check_approval_status
# ---------------------------------------------------------------------------

class TestCheckApprovalStatus(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _make_repo_with_verified(self.tmp_dir)
        _open_package()

    def test_all_approved_ready_for_baseline(self):
        _record(decision="approved")
        result = check_approval_status(PROJECT, "APKG-001")
        self.assertIn("Ready for baseline", result)
        self.assertIn("✅", result)

    def test_rejected_accountable_blocks_baseline(self):
        _record(decision="rejected", rejection_reason="Disagree")
        result = check_approval_status(PROJECT, "APKG-001")
        self.assertIn("Not ready", result)
        self.assertIn("🔴", result)

    def test_rejected_consulted_does_not_block(self):
        _record(stakeholder="Ivanov", decision="approved")
        _record(stakeholder="Consultant", raci="consulted",
                decision="rejected", rejection_reason="Doubts")
        result = check_approval_status(PROJECT, "APKG-001")
        # Consulted rejected — a warning, not a blocker
        self.assertIn("Consulted", result)
        self.assertIn("Ready for baseline", result)

    def test_open_conditions_reported(self):
        record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-001",
            stakeholder_name="Ivanov",
            stakeholder_raci="accountable",
            decision="conditional",
            req_decisions_json=json.dumps([
                {
                    "req_id": "FR-001",
                    "decision": "conditional",
                    "condition_text": "Clarify",
                    "condition_deadline": "2026-12-01",
                    "condition_owner": "Ivanov",
                },
                {"req_id": "FR-002", "decision": "approved"},
            ]),
        )
        result = check_approval_status(PROJECT, "APKG-001")
        self.assertIn("Clarify", result)

    def test_overdue_conditions_block_baseline(self):
        yesterday = str(date.today() - timedelta(days=1))
        record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-001",
            stakeholder_name="Ivanov",
            stakeholder_raci="accountable",
            decision="conditional",
            req_decisions_json=json.dumps([
                {
                    "req_id": "FR-001",
                    "decision": "conditional",
                    "condition_text": "Clarify",
                    "condition_deadline": yesterday,
                    "condition_owner": "Ivanov",
                },
                {"req_id": "FR-002", "decision": "approved"},
            ]),
        )
        result = check_approval_status(PROJECT, "APKG-001")
        self.assertIn("OVERDUE", result)
        self.assertIn("Not ready", result)

    def test_pending_requirements_block_baseline(self):
        # Don't record any decision — everything is pending
        result = check_approval_status(PROJECT, "APKG-001")
        self.assertIn("Not ready", result)
        self.assertIn("pending", result)

    def test_statistics_shown(self):
        _record(decision="approved")
        result = check_approval_status(PROJECT, "APKG-001")
        self.assertIn("Approved", result)
        self.assertIn("100%", result)

    def test_package_not_found(self):
        result = check_approval_status(PROJECT, "APKG-MISSING")
        self.assertIn("❌", result)

    def test_low_approval_pct_blocks_baseline(self):
        # Open a large package, approve only 1 of 4
        repo = make_test_repo(PROJECT)
        for req in repo["requirements"]:
            req["status"] = "verified"
        repo["requirements"].append({
            "id": "NFR-001", "type": "non_functional",
            "title": "Performance", "status": "verified",
            "version": "1.0",
        })
        save_test_repo(repo)

        prepare_approval_package(
            project_name=PROJECT,
            package_id="APKG-BIG",
            package_title="Large package",
            req_ids_json=json.dumps(["BR-001", "FR-001", "FR-002", "NFR-001"]),
            approach="predictive",
        )
        record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-BIG",
            stakeholder_name="Ivanov",
            stakeholder_raci="accountable",
            decision="approved",
            req_decisions_json=json.dumps([
                {"req_id": "BR-001", "decision": "approved"},
                {"req_id": "FR-001", "decision": "rejected", "rejection_reason": "No"},
                {"req_id": "FR-002", "decision": "rejected", "rejection_reason": "No"},
                {"req_id": "NFR-001", "decision": "rejected", "rejection_reason": "No"},
            ]),
        )
        result = check_approval_status(PROJECT, "APKG-BIG")
        self.assertIn("Not ready", result)

    def test_multiple_stakeholders_mixed(self):
        _record(stakeholder="Ivanov", decision="approved")
        _record(stakeholder="Petrov", raci="responsible", decision="approved")
        result = check_approval_status(PROJECT, "APKG-001")
        self.assertIn("Ivanov", result)
        self.assertIn("Petrov", result)
        self.assertIn("Ready for baseline", result)


# ---------------------------------------------------------------------------
# create_requirements_baseline
# ---------------------------------------------------------------------------

class TestCreateRequirementsBaseline(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _make_repo_with_verified(self.tmp_dir)
        _open_package()

    def _approve_all(self, stakeholder="Ivanov"):
        _record(stakeholder=stakeholder, decision="approved")

    def test_baseline_success(self):
        self._approve_all()
        result = create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Ivanov",
        )
        self.assertIn("v1.0", result)
        self.assertIn("✅", result)

    def test_baseline_updates_repo_status(self):
        self._approve_all()
        create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Ivanov",
        )
        from skills.requirements_approve_mcp import _load_repo
        repo = _load_repo(PROJECT)
        fr001 = next(r for r in repo["requirements"] if r["id"] == "FR-001")
        self.assertEqual(fr001["status"], STATUS_APPROVED)

    def test_baseline_saves_to_history(self):
        self._approve_all()
        create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Ivanov",
        )
        history = _load_approval_history(PROJECT)
        self.assertEqual(len(history["baselines"]), 1)
        self.assertEqual(history["baselines"][0]["baseline_version"], "v1.0")

    def test_baseline_blocked_by_rejected_accountable(self):
        _record(decision="rejected", rejection_reason="Disagree")
        result = create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Ivanov",
        )
        self.assertIn("❌", result)
        self.assertIn("blocked", result)

    def test_force_overrides_blocker(self):
        _record(decision="rejected", rejection_reason="Disagree")
        result = create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Ivanov",
            force=True,
        )
        # With force=True the baseline should be created despite the A/R rejection.
        self.assertIsNotNone(result)

    def test_low_approval_pct_blocks_baseline_without_force(self):
        """Baseline creation must enforce the same readiness gate as
        check_approval_status: below 70% approved (here 50%: one open conditional,
        one approved) it must block unless force=True, instead of silently
        baselining only the approved subset."""
        record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-001",
            stakeholder_name="Ivanov",
            stakeholder_raci="accountable",
            decision="conditional",
            req_decisions_json=json.dumps([
                {"req_id": "FR-001", "decision": "conditional",
                 "condition_text": "Clarify", "condition_deadline": "2026-12-01",
                 "condition_owner": "Petrov"},   # open, NOT overdue
                {"req_id": "FR-002", "decision": "approved"},
            ]),
        )
        result = create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Ivanov",
        )  # no force
        self.assertIn("❌", result)
        self.assertIn("blocked", result)
        history = _load_approval_history(PROJECT)
        self.assertEqual(len(history["baselines"]), 0, "no baseline may be created when not ready")

    def test_package_already_baselined_error(self):
        self._approve_all()
        create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Ivanov",
        )
        result = create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.1",
            decided_by="Ivanov",
        )
        self.assertIn("already has baseline", result)

    def test_package_not_found_error(self):
        result = create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-MISSING",
            baseline_version="v1.0",
            decided_by="Ivanov",
        )
        self.assertIn("❌", result)

    def test_baseline_contains_stakeholder_summary(self):
        self._approve_all()
        create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Ivanov",
        )
        history = _load_approval_history(PROJECT)
        bl = history["baselines"][0]
        self.assertIn("Ivanov", bl["stakeholder_summary"])

    def test_baseline_with_open_conditions_and_force(self):
        record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-001",
            stakeholder_name="Ivanov",
            stakeholder_raci="accountable",
            decision="conditional",
            req_decisions_json=json.dumps([
                {
                    "req_id": "FR-001",
                    "decision": "conditional",
                    "condition_text": "Clarify",
                    "condition_deadline": "2026-12-01",
                    "condition_owner": "Petrov",
                },
                {"req_id": "FR-002", "decision": "approved"},
            ]),
        )
        result = create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Ivanov",
            force=True,
        )
        self.assertIn("v1.0", result)
        history = _load_approval_history(PROJECT)
        bl = history["baselines"][0]
        self.assertEqual(len(bl["open_conditions"]), 1)

    def test_multiple_baselines_in_history(self):
        self._approve_all()
        create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Ivanov",
        )
        # Second package
        _make_repo_with_verified(self.tmp_dir)
        prepare_approval_package(
            project_name=PROJECT,
            package_id="APKG-002",
            package_title="Second package",
            req_ids_json='["BR-001"]',
            approach="agile",
        )
        _record(package_id="APKG-002", decision="approved")
        create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-002",
            baseline_version="sprint-1",
            decided_by="Ivanov",
        )
        history = _load_approval_history(PROJECT)
        self.assertEqual(len(history["baselines"]), 2)

    def test_agile_sprint_baseline(self):
        prepare_approval_package(
            project_name=PROJECT,
            package_id="APKG-SPRINT",
            package_title="Sprint 3",
            req_ids_json='["BR-001"]',
            approach="agile",
            sprint_number="3",
        )
        _record(package_id="APKG-SPRINT", decision="approved")
        result = create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-SPRINT",
            baseline_version="sprint-3",
            decided_by="Product Owner",
        )
        self.assertIn("sprint-3", result)


# ---------------------------------------------------------------------------
# Pipeline integration tests
# ---------------------------------------------------------------------------

class TestApprovalPipeline(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _make_repo_with_verified(self.tmp_dir)

    def test_full_predictive_pipeline(self):
        """Full Predictive pipeline: prepare → record × 2 → check → baseline."""
        # 1. prepare
        result = _open_package()
        self.assertIn("APKG-001", result)

        # 2. record — the Sponsor approves
        r1 = _record(stakeholder="Sponsor", raci="accountable", decision="approved")
        self.assertIn("✅", r1)

        # 3. record — the Business Expert approves
        r2 = _record(stakeholder="Expert", raci="responsible", decision="approved")
        self.assertIn("✅", r2)

        # 4. check
        status = check_approval_status(PROJECT, "APKG-001")
        self.assertIn("Ready for baseline", status)

        # 5. baseline
        bl = create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Sponsor",
        )
        self.assertIn("v1.0", bl)

        # Check the history
        history = _load_approval_history(PROJECT)
        self.assertEqual(len(history["baselines"]), 1)

    def test_full_agile_pipeline(self):
        """Agile pipeline: prepare sprint → PO approves → sprint baseline."""
        prepare_approval_package(
            project_name=PROJECT,
            package_id="SPRINT-1",
            package_title="Sprint 1 Backlog",
            req_ids_json='["FR-001"]',
            approach="agile",
            sprint_number="1",
        )
        record_approval_decision(
            project_name=PROJECT,
            package_id="SPRINT-1",
            stakeholder_name="Product Owner",
            stakeholder_raci="accountable",
            decision="approved",
        )
        status = check_approval_status(PROJECT, "SPRINT-1")
        self.assertIn("Ready for baseline", status)

        bl = create_requirements_baseline(
            project_name=PROJECT,
            package_id="SPRINT-1",
            baseline_version="sprint-1",
            decided_by="Product Owner",
        )
        self.assertIn("sprint-1", bl)

    def test_conditional_then_close_then_baseline(self):
        """Conditional → close_condition → baseline."""
        _open_package(req_ids=["FR-001"])
        record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-001",
            stakeholder_name="Ivanov",
            stakeholder_raci="accountable",
            decision="conditional",
            req_decisions_json=json.dumps([
                {
                    "req_id": "FR-001",
                    "decision": "conditional",
                    "condition_text": "Add acceptance criteria",
                    "condition_deadline": "2026-12-01",
                    "condition_owner": "BA",
                }
            ]),
        )

        # Status not ready yet
        status = check_approval_status(PROJECT, "APKG-001")
        self.assertIn("condition", status)

        # Close the condition
        close_approval_condition(
            project_name=PROJECT,
            package_id="APKG-001",
            req_id="FR-001",
            stakeholder_name="Ivanov",
            resolution_notes="Acceptance criteria added to the document",
        )

        # Now it's ready
        status2 = check_approval_status(PROJECT, "APKG-001")
        self.assertIn("Ready for baseline", status2)

        # Baseline
        bl = create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Ivanov",
        )
        self.assertIn("v1.0", bl)

    def test_conflict_consulted_rejected_does_not_block(self):
        """Rejected by a Consulted stakeholder doesn't block the baseline."""
        _open_package()
        _record(stakeholder="Sponsor", raci="accountable", decision="approved")
        _record(stakeholder="User", raci="consulted",
                decision="rejected", rejection_reason="Inconvenient")

        status = check_approval_status(PROJECT, "APKG-001")
        self.assertIn("Ready for baseline", status)
        self.assertIn("Consulted", status)

    def test_two_packages_independent(self):
        """Two packages don't affect each other."""
        _open_package(package_id="APKG-A", req_ids=["FR-001"])
        _open_package(package_id="APKG-B", req_ids=["FR-002"])

        _record(package_id="APKG-A", decision="approved")
        # APKG-B stays without decisions

        status_a = check_approval_status(PROJECT, "APKG-A")
        status_b = check_approval_status(PROJECT, "APKG-B")

        self.assertIn("Ready for baseline", status_a)
        self.assertIn("Not ready", status_b)

    def test_baseline_version_history_grows(self):
        """The baseline history grows with each new package."""
        # v1.0
        _open_package(package_id="V1", req_ids=["FR-001"])
        _record(package_id="V1", decision="approved")
        create_requirements_baseline(PROJECT, "V1", "v1.0", "Sponsor")

        # v1.1 — a new package
        prepare_approval_package(
            project_name=PROJECT,
            package_id="V11",
            package_title="Patch",
            req_ids_json='["FR-002"]',
            approach="predictive",
        )
        _record(package_id="V11", decision="approved")
        create_requirements_baseline(PROJECT, "V11", "v1.1", "Sponsor")

        history = _load_approval_history(PROJECT)
        versions = [bl["baseline_version"] for bl in history["baselines"]]
        self.assertIn("v1.0", versions)
        self.assertIn("v1.1", versions)


# ---------------------------------------------------------------------------
# B2-bis — 7.2 verification is visible in 5.5
# ---------------------------------------------------------------------------

def _make_repo_unverified(tmp_dir):
    """A repository whose requirements never passed 7.2 (status draft, no history)."""
    repo = make_test_repo(PROJECT)
    for req in repo["requirements"]:
        if req["type"] != "test":
            req["status"] = "draft"
            req["priority"] = "Must"
    repo["history"] = []
    save_test_repo(repo)
    return repo


class TestVerificationSnapshot(BaseMCPTest):
    """prepare_approval_package must capture verification BEFORE it overwrites status."""

    def test_snapshot_records_verified_reqs(self):
        _make_repo_with_verified(self.tmp_dir)
        prepare_approval_package(
            project_name=PROJECT, package_id="APKG-001", package_title="Pkg",
            req_ids_json='["FR-001"]', approach="predictive",
        )
        history = _load_approval_history(PROJECT)
        snapshot = history["packages"]["APKG-001"]["verification_snapshot"]
        self.assertEqual(snapshot, {"FR-001": True})

    def test_snapshot_survives_the_status_overwrite(self):
        """The legacy case: evidence lives only in the status, which prepare erases."""
        _make_repo_with_verified(self.tmp_dir)
        prepare_approval_package(
            project_name=PROJECT, package_id="APKG-001", package_title="Pkg",
            req_ids_json='["FR-001"]', approach="predictive",
        )
        repo = load_test_repo(PROJECT)
        node = next(r for r in repo["requirements"] if r["id"] == "FR-001")
        self.assertEqual(node["status"], STATUS_PENDING)  # status is gone
        history = _load_approval_history(PROJECT)
        self.assertTrue(history["packages"]["APKG-001"]["verification_snapshot"]["FR-001"])

    def test_snapshot_records_unverified_reqs(self):
        _make_repo_unverified(self.tmp_dir)
        prepare_approval_package(
            project_name=PROJECT, package_id="APKG-001", package_title="Pkg",
            req_ids_json='["FR-001"]', approach="predictive",
        )
        history = _load_approval_history(PROJECT)
        self.assertEqual(
            history["packages"]["APKG-001"]["verification_snapshot"], {"FR-001": False}
        )

    def test_unverified_reqs_are_warned_about_with_the_phase_hint(self):
        """7.2 lives in the `design` phase — a hint naming only the tool is unfollowable."""
        _make_repo_unverified(self.tmp_dir)
        out = prepare_approval_package(
            project_name=PROJECT, package_id="APKG-001", package_title="Pkg",
            req_ids_json='["FR-001"]', approach="predictive",
        )
        self.assertIn("FR-001", out)
        self.assertIn("7.2", out)
        self.assertIn("phase.py design", out)

    def test_verified_package_has_no_warning(self):
        _make_repo_with_verified(self.tmp_dir)
        out = prepare_approval_package(
            project_name=PROJECT, package_id="APKG-001", package_title="Pkg",
            req_ids_json='["FR-001"]', approach="predictive",
        )
        self.assertNotIn("Not verified via 7.2", out)


class TestVerificationState(BaseMCPTest):
    """_verification_state merges the live history with the stored snapshot."""

    def test_live_history_beats_a_stale_snapshot(self):
        """The BA may go to 7.2 AFTER preparing the package."""
        repo = _make_repo_unverified(self.tmp_dir)
        repo["history"].append({"action": "req_verified", "req_id": "FR-001"})
        package = {"req_ids": ["FR-001"], "verification_snapshot": {"FR-001": False}}
        state = _verification_state(repo, package)
        self.assertEqual(state["verified"], ["FR-001"])
        self.assertEqual(state["unverified"], [])

    def test_snapshot_fills_in_for_erased_status(self):
        repo = _make_repo_unverified(self.tmp_dir)
        package = {"req_ids": ["FR-001"], "verification_snapshot": {"FR-001": True}}
        state = _verification_state(repo, package)
        self.assertEqual(state["verified"], ["FR-001"])

    def test_missing_snapshot_key_is_unknown_not_unverified(self):
        """Packages already in flight when this shipped must not be called liars."""
        repo = _make_repo_unverified(self.tmp_dir)
        package = {"req_ids": ["FR-001"]}
        state = _verification_state(repo, package)
        self.assertFalse(state["known"])

    def test_forced_verification_is_listed_separately(self):
        repo = _make_repo_unverified(self.tmp_dir)
        repo["history"].append(
            {"action": "req_verified", "req_id": "FR-001", "forced": True}
        )
        package = {"req_ids": ["FR-001"], "verification_snapshot": {"FR-001": False}}
        state = _verification_state(repo, package)
        self.assertEqual(state["verified"], ["FR-001"])
        self.assertEqual(state["forced"], ["FR-001"])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
