"""
tests/test_ch4_41.py — Tests for Chapter 4.1: Prepare for Elicitation
MCP file: skills/elicitation_mcp.py
Tools: save_elicitation_plan, create_google_form, get_form_responses

Strategy: BaseMCPTest (tmpdir + chdir), setup_mocks() before imports,
save_artifact is patched via patch() per ADR-068.
"""

import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tests.conftest import setup_mocks, BaseMCPTest
setup_mocks()

import skills.elicitation_mcp as mod41


# ---------------------------------------------------------------------------
# Helper data
# ---------------------------------------------------------------------------

STAKEHOLDERS_VALID = json.dumps([
    {
        "name": "Ivan Petrov",
        "role": "Sales Manager",
        "key_questions": ["Which processes to automate?", "Which KPIs?"],
    },
    {
        "name": "Anna Smirnova",
        "role": "IT Director",
        "key_questions": ["Which integrations?", "Which security constraints?"],
    },
])

PLAN_BASE = dict(
    project_name="crm_upgrade",
    goals="Elicit requirements for sales automation",
    stakeholders_json=STAKEHOLDERS_VALID,
    technique="Interview",
    technique_rationale="Deep understanding of stakeholder pains",
    questions_or_agenda="1. Current processes?\n2. What hinders the work?\n3. Expectations from the system?",
    expected_outcomes="A list of functional requirements and pains",
)


# ---------------------------------------------------------------------------
# save_elicitation_plan
# ---------------------------------------------------------------------------

class TestSaveElicitationPlan(BaseMCPTest):
    """Tests for the 4.1 tool: save_elicitation_plan."""

    def _call(self, **overrides):
        kwargs = {**PLAN_BASE, **overrides}
        with patch("skills.elicitation_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod41.save_elicitation_plan(**kwargs)

    # --- happy path across all techniques ---

    def test_technique_interview(self):
        """Interview technique — basic scenario."""
        result = self._call(technique="Interview")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_technique_workshop(self):
        """Workshop technique."""
        result = self._call(
            technique="Workshop",
            technique_rationale="Alignment between departments is needed",
            questions_or_agenda="09:00 Introduction\n09:30 AS-IS analysis\n10:30 TO-BE",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_technique_questionnaire(self):
        """Survey technique."""
        result = self._call(
            technique="Survey",
            technique_rationale="Many participants, scale is needed",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_technique_brainstorm(self):
        """Brainstorming technique."""
        result = self._call(technique="Brainstorming")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_technique_document_analysis(self):
        """Document Analysis technique."""
        result = self._call(technique="Document Analysis")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_technique_observation(self):
        """Observation technique."""
        result = self._call(technique="Observation")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_technique_prototyping(self):
        """Prototyping technique."""
        result = self._call(technique="Prototyping")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_technique_focus_group(self):
        """Focus Group technique."""
        result = self._call(technique="Focus Group")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_technique_benchmarking(self):
        """Benchmarking technique."""
        result = self._call(technique="Benchmarking")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- edge cases ---

    def test_single_stakeholder(self):
        """A single stakeholder — an edge case."""
        result = self._call(
            stakeholders_json=json.dumps([
                {"name": "Director", "role": "CEO", "key_questions": ["Why the project?"]}
            ])
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_empty_questions_or_agenda(self):
        """Empty agenda — must not crash."""
        result = self._call(questions_or_agenda="")
        self.assertIsInstance(result, str)

    def test_empty_expected_outcomes(self):
        """Empty expected outcomes — must not crash."""
        result = self._call(expected_outcomes="")
        self.assertIsInstance(result, str)

    def test_different_project_names(self):
        """Different project_name values don't cause collisions."""
        result1 = self._call(project_name="project_alpha")
        result2 = self._call(project_name="project_beta")
        self.assertNotIn("❌", result1)
        self.assertNotIn("❌", result2)

    # --- error cases ---

    def test_invalid_json_stakeholders(self):
        """Invalid stakeholders JSON → error."""
        result = self._call(stakeholders_json="{bad json}")
        self.assertIn("❌", result)

    def test_empty_json_stakeholders(self):
        """Empty string instead of JSON → error."""
        result = self._call(stakeholders_json="")
        self.assertIn("❌", result)

    def test_stakeholders_not_a_list(self):
        """A JSON object instead of a list → error."""
        result = self._call(stakeholders_json=json.dumps({"name": "Ivan"}))
        self.assertIn("❌", result)

    def test_save_artifact_called(self):
        """save_artifact is called exactly once."""
        with patch("skills.elicitation_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            mod41.save_elicitation_plan(**PLAN_BASE)
            mock_sa.assert_called_once()

    def test_returns_string(self):
        """The function always returns a string."""
        result = self._call()
        self.assertIsInstance(result, str)


# ---------------------------------------------------------------------------
# create_google_form
# ---------------------------------------------------------------------------

class TestCreateGoogleForm(BaseMCPTest):
    """Tests for the 4.1 tool: create_google_form."""

    QUESTIONS_VALID = json.dumps([
        {
            "question": "Which processes most often cause delays?",
            "type": "paragraph",
            "required": True,
        },
        {
            "question": "How satisfied are you with the current system? (1–5)",
            "type": "scale",
            "required": True,
        },
        {
            "question": "What functionality would you like to see?",
            "type": "multiple_choice",
            "options": ["Reports", "Integrations", "Automation"],
            "required": False,
        },
    ])

    def _call(self, **overrides):
        defaults = {
            "title": "Survey: CRM requirements",
            "description": "Help us understand your needs",
            "questions_json": self.QUESTIONS_VALID,
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod41.create_google_form(**kwargs)

    def test_basic_form(self):
        """A basic form is created without errors."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_single_question(self):
        """A form with a single question."""
        result = self._call(
            questions_json=json.dumps([
                {"question": "What to improve?", "type": "paragraph", "required": True}
            ])
        )
        self.assertIsInstance(result, str)

    def test_returns_string(self):
        """Always returns a string."""
        self.assertIsInstance(self._call(), str)

    def test_invalid_questions_json(self):
        """Invalid questions JSON → error."""
        result = self._call(questions_json="{invalid}")
        self.assertIn("❌", result)

    def test_empty_title(self):
        """An empty title — must not crash with an exception."""
        result = self._call(title="")
        self.assertIsInstance(result, str)


# ---------------------------------------------------------------------------
# get_form_responses
# ---------------------------------------------------------------------------

class TestGetFormResponses(BaseMCPTest):
    """Tests for the 4.1 tool: get_form_responses."""

    def _call(self, form_id="form_12345", export_format="summary"):
        with patch("skills.elicitation_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod41.get_form_responses(
                form_id=form_id,
                export_format=export_format,
            )

    def test_summary_format(self):
        """summary format."""
        result = self._call(export_format="summary")
        self.assertIsInstance(result, str)

    def test_full_format(self):
        """full format."""
        result = self._call(export_format="full")
        self.assertIsInstance(result, str)

    def test_csv_format(self):
        """csv format."""
        result = self._call(export_format="csv")
        self.assertIsInstance(result, str)

    def test_empty_form_id(self):
        """An empty form_id — the function must not crash with an exception."""
        result = self._call(form_id="")
        self.assertIsInstance(result, str)

    def test_returns_string(self):
        """Always returns a string."""
        self.assertIsInstance(self._call(), str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
