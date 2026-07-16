"""
tests/test_ch4_42.py — Tests for Chapter 4.2: Conduct Elicitation
MCP file: skills/elicitation_conduct_mcp.py
Tools: process_elicitation_results, compare_elicitation_results,
       save_cr_elicitation_analysis, update_stakeholder_registry

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

import skills.elicitation_conduct_mcp as mod42


# ---------------------------------------------------------------------------
# Helper data
# ---------------------------------------------------------------------------

STAKEHOLDER_PROFILE_VALID = {
    "name": "Ivan Petrov",
    "role": "Sales Manager",
    "influence": "High",
    "interest": "High",
    "key_expectations": "Automation of request processing",
    "key_concerns": "Implementation complexity for users",
    "related_stakeholders": ["Sales Director"],
}

PAINS_VALID = [
    {
        "title": "Slow request processing",
        "description": "Manual processing takes 2–3 hours",
        "frequency": "Daily",
        "business_impact": "Customer churn due to delays",
        "quote": "We lose up to 20% of customers because of slow responses",
    },
    {
        "title": "No single customer database",
        "description": "Data is in Excel and in the managers' heads",
        "frequency": "Constantly",
        "business_impact": "Duplicated work",
        "quote": "",
    },
]

REQUIREMENTS_VALID = {
    "functional": [
        {"id": "FR-001", "statement": "Integration with 1C to synchronize orders", "priority": "High"},
        {"id": "FR-002", "statement": "Automatic notifications to customers", "priority": "Medium"},
    ],
    "non_functional": [
        {"id": "NFR-001", "statement": "Response time no more than 2 seconds", "priority": "High"},
    ],
    "constraints": ["Project budget — up to 3 million rubles"],
    "business_rules": ["Requests are processed in order of arrival"],
}

PROCESS_BASE = dict(
    project_name="crm_upgrade",
    session_date="2025-03-17",
    stakeholder_role="Sales Manager",
    session_type="Interview",
    stakeholder_profile_json=json.dumps(STAKEHOLDER_PROFILE_VALID),
    pains_json=json.dumps(PAINS_VALID),
    requirements_json=json.dumps(REQUIREMENTS_VALID),
    gaps_and_signals="Didn't clarify the 1C version; unclear who administers the system",
    ba_recommendations="Run a technical interview with the IT Director",
    maturity_level="Medium",
    maturity_notes="Understands the business well, but not the technical details",
)


# ---------------------------------------------------------------------------
# process_elicitation_results
# ---------------------------------------------------------------------------

class TestProcessElicitationResults(BaseMCPTest):
    """Tests for 4.2: process_elicitation_results."""

    def _call(self, **overrides):
        kwargs = {**PROCESS_BASE, **overrides}
        with patch("skills.elicitation_conduct_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod42.process_elicitation_results(**kwargs)

    # --- happy path across all session types ---

    def test_session_type_interview(self):
        """Session type: Interview."""
        result = self._call(session_type="Interview")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_session_type_workshop(self):
        """Session type: Workshop."""
        result = self._call(session_type="Workshop")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_session_type_questionnaire(self):
        """Session type: Survey."""
        result = self._call(session_type="Survey")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_session_type_observation(self):
        """Session type: Observation."""
        result = self._call(session_type="Observation")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_session_type_document_analysis(self):
        """Session type: Document Analysis."""
        result = self._call(session_type="Document Analysis")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- maturity levels ---

    def test_maturity_low(self):
        """Maturity level: Low."""
        result = self._call(maturity_level="Low", maturity_notes="Doesn't understand IT")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_maturity_good(self):
        """Maturity level: Good."""
        result = self._call(maturity_level="Good")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_maturity_high(self):
        """Maturity level: High."""
        result = self._call(maturity_level="High")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- edge cases ---

    def test_empty_pains(self):
        """No pains — must not crash."""
        result = self._call(pains_json=json.dumps([]))
        self.assertIsInstance(result, str)

    def test_empty_requirements(self):
        """Empty requirements — must not crash."""
        empty_reqs = {"functional": [], "non_functional": [], "constraints": [], "business_rules": []}
        result = self._call(requirements_json=json.dumps(empty_reqs))
        self.assertIsInstance(result, str)

    def test_empty_gaps(self):
        """No gaps in the data."""
        result = self._call(gaps_and_signals="")
        self.assertIsInstance(result, str)

    def test_save_artifact_called(self):
        """save_artifact is called on a successful run."""
        with patch("skills.elicitation_conduct_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            mod42.process_elicitation_results(**PROCESS_BASE)
            mock_sa.assert_called_once()

    # --- error cases ---

    def test_invalid_profile_json(self):
        """Invalid stakeholder profile JSON → error."""
        result = self._call(stakeholder_profile_json="{bad json}")
        self.assertIn("❌", result)

    def test_invalid_pains_json(self):
        """Invalid pains JSON → error."""
        result = self._call(pains_json="not a list")
        self.assertIn("❌", result)

    def test_invalid_requirements_json(self):
        """Invalid requirements JSON → error."""
        result = self._call(requirements_json="{bad}")
        self.assertIn("❌", result)

    def test_returns_string(self):
        """Always returns a string."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# compare_elicitation_results
# ---------------------------------------------------------------------------

class TestCompareElicitationResults(BaseMCPTest):
    """Tests for 4.2: compare_elicitation_results."""

    SESSIONS_SUMMARY = "Session 1 (Manager): integration with 1C is needed. Session 2 (IT Director): 1C v8.3, API constraint."
    REQS_REGISTRY = json.dumps([
        {"id": "BR-001", "statement": "Reduce request processing time", "source": "Sales Manager"},
        {"id": "FR-001", "statement": "Integration with 1C v8.3", "source": "IT Director"},
    ])

    def _call(self, **overrides):
        defaults = {
            "project_name": "crm_upgrade",
            "sessions_summary": self.SESSIONS_SUMMARY,
            "contradictions": "The manager wants integration right away, IT says 1C v7 doesn't support REST",
            "requirements_registry_json": self.REQS_REGISTRY,
            "political_map": "Manager — Champion, IT Director — Neutral (cautious)",
            "follow_up_plan": "A technical workshop with IT and the 1C vendor",
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_conduct_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod42.compare_elicitation_results(**kwargs)

    def test_basic_comparison(self):
        """A basic comparison of two sessions."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_no_contradictions(self):
        """No contradictions — an edge case."""
        result = self._call(contradictions="")
        self.assertIsInstance(result, str)

    def test_empty_requirements_registry(self):
        """Empty requirements registry."""
        result = self._call(requirements_registry_json=json.dumps([]))
        self.assertIsInstance(result, str)

    def test_invalid_requirements_json(self):
        """Invalid registry JSON → error."""
        result = self._call(requirements_registry_json="{bad}")
        self.assertIn("❌", result)

    def test_returns_string(self):
        """Always returns a string."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# save_cr_elicitation_analysis
# ---------------------------------------------------------------------------

class TestSaveCrElicitationAnalysis(BaseMCPTest):
    """Tests for 4.2: save_cr_elicitation_analysis."""

    AFFECTED_ARTIFACTS = json.dumps([
        {"artifact": "FR-001", "type": "FR", "affected": True, "change_type": "Update"},
        {"artifact": "NFR-001", "type": "NFR", "affected": False, "change_type": ""},
    ])

    def _call(self, **overrides):
        defaults = {
            "project_name": "crm_upgrade",
            "cr_description": "Add a sales analytics module with dashboards",
            "affected_artifacts_json": self.AFFECTED_ARTIFACTS,
            "outdated_data": "The reporting requirements section (FR-009–FR-011) is outdated",
            "follow_up_questions": "What dashboard format? Which KPIs are needed?",
            "scope_assessment": "Medium scope — 4–5 new requirements, 2 weeks",
            "workshop_needed": False,
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_conduct_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod42.save_cr_elicitation_analysis(**kwargs)

    def test_basic_cr(self):
        """A basic CR without a workshop."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_cr_with_workshop(self):
        """The CR requires a workshop."""
        result = self._call(
            workshop_needed=True,
            workshop_notes="Need to bring IT + business together to align the requirements",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_no_affected_artifacts(self):
        """No affected artifacts."""
        result = self._call(affected_artifacts_json=json.dumps([]))
        self.assertIsInstance(result, str)

    def test_invalid_affected_json(self):
        """Invalid artifacts JSON → error."""
        result = self._call(affected_artifacts_json="{bad}")
        self.assertIn("❌", result)

    def test_empty_follow_up(self):
        """No follow-up questions."""
        result = self._call(follow_up_questions="")
        self.assertIsInstance(result, str)

    def test_returns_string(self):
        """Always returns a string."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# update_stakeholder_registry
# ---------------------------------------------------------------------------

class TestUpdateStakeholderRegistry(BaseMCPTest):
    """Tests for 4.2: update_stakeholder_registry."""

    NEW_STAKEHOLDERS_VALID = json.dumps([
        {
            "name": "Petr Vasilyev",
            "role": "Architect",
            "influence": "High",
            "interest": "Medium",
            "attitude": "Neutral",
            "contact": "petr@company.com",
            "comm_frequency": "Bi-weekly",
            "comm_triggers": ["Technical decision", "Architecture review"],
        }
    ])

    def _call(self, **overrides):
        defaults = {
            "project_name": "crm_upgrade",
            "session_source": "Interview with the IT Director 2025-03-17",
            "new_stakeholders_json": self.NEW_STAKEHOLDERS_VALID,
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_conduct_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod42.update_stakeholder_registry(**kwargs)

    def test_add_single_stakeholder(self):
        """Adding one new stakeholder."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_add_multiple_stakeholders(self):
        """Adding several stakeholders at once."""
        result = self._call(
            new_stakeholders_json=json.dumps([
                {
                    "name": "Anya",
                    "role": "QA Lead",
                    "influence": "Low",
                    "interest": "High",
                    "attitude": "Champion",
                    "contact": "anya@company.com",
                    "comm_frequency": "Weekly",
                    "comm_triggers": ["Release"],
                },
                {
                    "name": "Boris",
                    "role": "DevOps",
                    "influence": "Low",
                    "interest": "Low",
                    "attitude": "Neutral",
                    "contact": "boris@company.com",
                    "comm_frequency": "Monthly",
                    "comm_triggers": [],
                },
            ])
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_blocker_attitude(self):
        """A stakeholder with attitude=Blocker."""
        result = self._call(
            new_stakeholders_json=json.dumps([{
                "name": "Skeptic",
                "role": "CFO",
                "influence": "High",
                "interest": "Low",
                "attitude": "Blocker",
                "contact": "",
                "comm_frequency": "Monthly",
                "comm_triggers": ["Budget review"],
            }])
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_empty_stakeholders_list(self):
        """An empty list — no new stakeholders."""
        result = self._call(new_stakeholders_json=json.dumps([]))
        self.assertIsInstance(result, str)

    def test_invalid_stakeholders_json(self):
        """Invalid JSON → error."""
        result = self._call(new_stakeholders_json="{bad json}")
        self.assertIn("❌", result)

    def test_returns_string(self):
        """Always returns a string."""
        self.assertIsInstance(self._call(), str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
