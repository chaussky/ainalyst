"""
tests/test_ch4_43.py — Tests for Chapter 4.3: Confirm Elicitation Results
MCP file: skills/elicitation_confirm_mcp.py
Tools: run_consistency_check, save_confirmed_elicitation_result

Strategy: BaseMCPTest (tmpdir + chdir), setup_mocks() before imports,
save_artifact is patched via patch() per ADR-068.
"""

import json
import os
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tests.conftest import setup_mocks, BaseMCPTest
setup_mocks()

import skills.elicitation_confirm_mcp as mod43


# ---------------------------------------------------------------------------
# Helper data
# ---------------------------------------------------------------------------

SOURCE_ARTIFACTS = [
    {"path": "governance_plans/reports/4_2_crm_interview.md",
     "stakeholder_role": "Sales Manager",
     "session_date": "2025-03-17"},
    {"path": "governance_plans/reports/4_2_crm_it_director.md",
     "stakeholder_role": "IT Director",
     "session_date": "2025-03-18"},
]

ISSUE_HIGH = {
    "criterion": "Unambiguity",
    "severity": "Critical",
    "description": "FR-001 can be interpreted as real-time synchronization or batch",
    "affected_requirement": "FR-001",
    "recommendation": "Clarify with the IT Director: real-time or batch processing?",
    "source_artifact": "governance_plans/reports/4_2_crm_interview.md",
}

ISSUE_LOW = {
    "criterion": "Completeness",
    "severity": "Minor",
    "description": "NFR-001 contains no metrics for load testing",
    "affected_requirement": "NFR-001",
    "recommendation": "Add a load condition (for example: 100 concurrent users)",
    "source_artifact": "governance_plans/reports/4_2_crm_it_director.md",
}

CONFIRMED_REQUIREMENTS = {
    "functional": [
        {"id": "FR-001",
         "statement": "Integration with 1C v8.3 via REST API (batch, every 15 minutes)",
         "acceptance_criteria": "Data is synchronized without errors within 15 minutes"},
        {"id": "FR-002",
         "statement": "Email notification to the customer when the request status changes",
         "acceptance_criteria": "The email arrives within 5 minutes of the status change"},
    ],
    "non_functional": [
        {"id": "NFR-001",
         "statement": "System response time no more than 2 seconds at 100 concurrent users",
         "acceptance_criteria": "The load test shows P95 < 2s"},
    ],
    "constraints": ["Budget — up to 3 million rubles", "Launch — by 2025-06-01"],
    "business_rules": ["Requests are processed in order of arrival"],
}


# ---------------------------------------------------------------------------
# run_consistency_check
# ---------------------------------------------------------------------------

class TestRunConsistencyCheck(BaseMCPTest):
    """Tests for 4.3: run_consistency_check."""

    def _call(self, **overrides):
        defaults = {
            "project_name": "crm_upgrade",
            "source_artifacts_json": json.dumps(SOURCE_ARTIFACTS),
            "issues_json": json.dumps([]),
            "readiness_status": "Ready for Analysis",
            "readiness_rationale": "All requirements are unambiguous and complete",
            "needs_clarification": False,
            "clarification_questions_json": json.dumps([]),
            "ba_decision": "Hand off to current-state analysis (6.1)",
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_confirm_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod43.run_consistency_check(**kwargs)

    # --- happy path across all readiness statuses ---

    def test_status_ready_no_issues(self):
        """Status: Ready for Analysis, no issues."""
        result = self._call(
            readiness_status="Ready for Analysis",
            issues_json=json.dumps([]),
            needs_clarification=False,
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_status_conditional_with_low_issues(self):
        """Status: Conditionally Ready, Minor-severity issues."""
        result = self._call(
            readiness_status="Conditionally Ready",
            readiness_rationale="Minor issues — don't block the analysis",
            issues_json=json.dumps([ISSUE_LOW]),
            needs_clarification=False,
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_status_needs_rework_high_issues(self):
        """Status: Needs Rework, Critical-severity issues with questions."""
        result = self._call(
            readiness_status="Needs Rework",
            readiness_rationale="Critical ambiguity in FR-001",
            issues_json=json.dumps([ISSUE_HIGH]),
            needs_clarification=True,
            clarification_questions_json=json.dumps([
                {
                    "stakeholder_role": "IT Director",
                    "issue_id": "ISS-001",
                    "question": "FR-001: real-time synchronization or batch every 15 minutes?",
                }
            ]),
            ba_decision="Clarify with the IT Director by 2025-03-20",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_multiple_issues_mixed_severity(self):
        """Several issues of different severity."""
        result = self._call(
            readiness_status="Conditionally Ready",
            issues_json=json.dumps([ISSUE_HIGH, ISSUE_LOW]),
            needs_clarification=True,
            clarification_questions_json=json.dumps([
                {"stakeholder_role": "IT Director", "issue_id": "ISS-001",
                 "question": "Real-time or batch?"}
            ]),
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_single_artifact(self):
        """Only one data source."""
        result = self._call(
            source_artifacts_json=json.dumps([SOURCE_ARTIFACTS[0]])
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_no_clarification_questions_when_not_needed(self):
        """needs_clarification=False, empty questions list."""
        result = self._call(
            needs_clarification=False,
            clarification_questions_json=json.dumps([]),
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_save_artifact_called(self):
        """save_artifact is called exactly once."""
        with patch("skills.elicitation_confirm_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            mod43.run_consistency_check(
                project_name="crm_upgrade",
                source_artifacts_json=json.dumps(SOURCE_ARTIFACTS),
                issues_json=json.dumps([]),
                readiness_status="Ready for Analysis",
                readiness_rationale="OK",
                needs_clarification=False,
                clarification_questions_json=json.dumps([]),
                ba_decision="Hand off to 6.1",
            )
            mock_sa.assert_called_once()

    # --- error cases ---

    def test_invalid_artifacts_json(self):
        """Invalid artifacts JSON → error."""
        result = self._call(source_artifacts_json="{bad json}")
        self.assertIn("❌", result)

    def test_invalid_issues_json(self):
        """Invalid issues JSON → error."""
        result = self._call(issues_json="not a list")
        self.assertIn("❌", result)

    def test_invalid_questions_json(self):
        """Invalid questions JSON → error."""
        result = self._call(
            needs_clarification=True,
            clarification_questions_json="{bad}",
        )
        self.assertIn("❌", result)

    def test_returns_string(self):
        """Always returns a string."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# save_confirmed_elicitation_result
# ---------------------------------------------------------------------------

class TestSaveConfirmedElicitationResult(BaseMCPTest):
    """Tests for 4.3: save_confirmed_elicitation_result."""

    def _call(self, **overrides):
        defaults = {
            "project_name": "crm_upgrade",
            "stakeholder_role": "Sales Manager",
            "consistency_check_path": "governance_plans/reports/4_3_consistency_crm_upgrade.md",
            "confirmed_requirements_json": json.dumps(CONFIRMED_REQUIREMENTS),
            "resolved_issues_json": json.dumps([
                {"issue_id": "ISS-001", "resolution": "Clarified: batch every 15 minutes"}
            ]),
            "open_issues_json": json.dumps([]),
            "final_readiness": "Ready for Analysis",
            "next_tasks": "Hand off to 6.1 — current-state analysis",
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_confirm_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod43.save_confirmed_elicitation_result(**kwargs)

    # --- happy path ---

    def test_fully_confirmed(self):
        """All requirements confirmed, no open issues."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_conditional_readiness(self):
        """Status: Conditionally Ready — there are open issues."""
        result = self._call(
            final_readiness="Conditionally Ready",
            open_issues_json=json.dumps([
                {"issue_id": "ISS-002",
                 "description": "NFR metrics not confirmed by a load test",
                 "owner": "IT Director",
                 "deadline": "2025-03-25"}
            ]),
            next_tasks="Wait for NFR-001 confirmation from IT; then 6.1",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_no_resolved_issues(self):
        """No resolved issues (there were no issues to begin with)."""
        result = self._call(resolved_issues_json=json.dumps([]))
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_requirements_with_only_functional(self):
        """Only functional requirements."""
        only_functional = {
            "functional": CONFIRMED_REQUIREMENTS["functional"],
            "non_functional": [],
            "constraints": [],
            "business_rules": [],
        }
        result = self._call(confirmed_requirements_json=json.dumps(only_functional))
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_different_stakeholder_roles(self):
        """Different stakeholder roles."""
        for role in ["IT Director", "Architect", "End User"]:
            result = self._call(stakeholder_role=role)
            self.assertIsInstance(result, str)
            self.assertNotIn("❌", result)

    def test_save_artifact_called(self):
        """save_artifact is called exactly once."""
        with patch("skills.elicitation_confirm_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            mod43.save_confirmed_elicitation_result(
                project_name="crm_upgrade",
                stakeholder_role="Manager",
                consistency_check_path="governance_plans/reports/check.md",
                confirmed_requirements_json=json.dumps(CONFIRMED_REQUIREMENTS),
                resolved_issues_json=json.dumps([]),
                open_issues_json=json.dumps([]),
                final_readiness="Ready for Analysis",
                next_tasks="→ 6.1",
            )
            mock_sa.assert_called_once()

    # --- error cases ---

    def test_invalid_requirements_json(self):
        """Invalid requirements JSON → error."""
        result = self._call(confirmed_requirements_json="{bad}")
        self.assertIn("❌", result)

    def test_invalid_resolved_json(self):
        """Invalid resolved-issues JSON → error."""
        result = self._call(resolved_issues_json="not json")
        self.assertIn("❌", result)

    def test_invalid_open_issues_json(self):
        """Invalid open-issues JSON → error."""
        result = self._call(open_issues_json="{bad}")
        self.assertIn("❌", result)

    def test_returns_string(self):
        """Always returns a string."""
        self.assertIsInstance(self._call(), str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
