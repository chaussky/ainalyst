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

    # --- living-document (read-merge) behavior ---

    def _call_capture(self, **overrides):
        """Call the tool and return (result_string, rendered_md_content)."""
        defaults = {
            "project_name": "crm_upgrade",
            "session_source": "Interview 2025-03-17",
            "new_stakeholders_json": self.NEW_STAKEHOLDERS_VALID,
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_conduct_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            result = mod42.update_stakeholder_registry(**kwargs)
            md = mock_sa.call_args.args[0] if mock_sa.call_args else ""
        return result, md

    def _load_registry(self, project_name="crm_upgrade"):
        from skills.common import data_path, normalize_project_id
        path = data_path(project_name, f"{normalize_project_id(project_name)}_stakeholder_registry.json")
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_registry_accumulates_across_calls(self):
        """The registry is a living document: a later call's report shows people
        added in earlier calls, not only the current batch."""
        self._call_capture(new_stakeholders_json=json.dumps(
            [{"name": "Alice Stone", "role": "CFO", "attitude": "Neutral"}]))
        _result, md = self._call_capture(new_stakeholders_json=json.dumps(
            [{"name": "Bob Reeves", "role": "CTO", "attitude": "Champion"}]))
        self.assertIn("Alice Stone", md, "earlier stakeholder must persist in the registry")
        self.assertIn("Bob Reeves", md, "current stakeholder must be present")

    def test_existing_stakeholder_updated_not_duplicated(self):
        """Re-submitting the same person updates in place (partial, non-empty fields)
        instead of creating a duplicate; untouched fields are preserved."""
        self._call_capture(new_stakeholders_json=json.dumps(
            [{"name": "Carol Diaz", "role": "PM", "attitude": "Neutral", "department": "Ops"}]))
        self._call_capture(new_stakeholders_json=json.dumps(
            [{"name": "Carol Diaz", "role": "PM", "attitude": "Champion"}]))
        reg = self._load_registry()
        carols = [s for s in reg["stakeholders"] if s.get("name") == "Carol Diaz"]
        self.assertEqual(len(carols), 1, "must not duplicate the same person")
        self.assertEqual(carols[0]["attitude"], "Champion", "non-empty field must be updated")
        self.assertEqual(carols[0].get("department"), "Ops", "untouched field must be preserved")

    def test_merge_by_role_when_name_empty(self):
        """When name is empty, identity falls back to role."""
        self._call_capture(new_stakeholders_json=json.dumps(
            [{"name": "", "role": "Head of Legal", "attitude": "Neutral"}]))
        self._call_capture(new_stakeholders_json=json.dumps(
            [{"name": "", "role": "Head of Legal", "attitude": "Blocker"}]))
        reg = self._load_registry()
        legal = [s for s in reg["stakeholders"] if s.get("role") == "Head of Legal"]
        self.assertEqual(len(legal), 1, "same role with empty name must merge")
        self.assertEqual(legal[0]["attitude"], "Blocker")

    def test_duplicate_role_warning_for_new_person(self):
        """Adding a NEW person whose role matches a DIFFERENT existing stakeholder
        surfaces a soft duplicate warning referencing the existing one."""
        self._call_capture(new_stakeholders_json=json.dumps(
            [{"name": "Dave Ruiz", "role": "Backend Developer"}]))
        _result, md = self._call_capture(new_stakeholders_json=json.dumps(
            [{"name": "Erin Park", "role": "Backend Developer"}]))
        self.assertIn("Possibly the same person", md)
        self.assertIn("Dave Ruiz", md)




# ---------------------------------------------------------------------------
# A3 — 4.2 emits the structured JSON that 6.3 import_risks_from_context reads
# ---------------------------------------------------------------------------

class TestSessionRisksJson(BaseMCPTest):

    PID = "crm_upgrade"

    def _call(self, **overrides):
        kwargs = {**PROCESS_BASE, **overrides}
        with patch("skills.elicitation_conduct_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod42.process_elicitation_results(**kwargs)

    def _json(self):
        path = mod42._elicitation_results_path(self.PID)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_risks_are_written_under_the_key_63_reads(self):
        self._call(risks_json=json.dumps(
            [{"description": "The legacy API may not survive the load"}]))
        data = self._json()
        self.assertIsNotNone(data)
        self.assertEqual(len(data["risks_mentioned"]), 1)
        self.assertEqual(data["risks_mentioned"][0]["description"],
                         "The legacy API may not survive the load")

    def test_bare_string_is_normalised_to_an_object(self):
        self._call(risks_json=json.dumps(["Vendor lock-in"]))
        self.assertEqual(self._json()["risks_mentioned"][0]["description"],
                         "Vendor lock-in")

    def test_stakeholder_defaults_to_the_session_role(self):
        self._call(risks_json=json.dumps([{"description": "Budget may be cut"}]))
        self.assertEqual(self._json()["risks_mentioned"][0]["stakeholder"],
                         PROCESS_BASE["stakeholder_role"])

    def test_explicit_stakeholder_wins(self):
        self._call(risks_json=json.dumps(
            [{"description": "Budget may be cut", "stakeholder": "CFO"}]))
        self.assertEqual(self._json()["risks_mentioned"][0]["stakeholder"], "CFO")

    def test_two_sessions_accumulate(self):
        self._call(session_date="01.03.2026", stakeholder_role="CTO",
                   risks_json=json.dumps([{"description": "Risk one"}]))
        self._call(session_date="02.03.2026", stakeholder_role="CFO",
                   risks_json=json.dumps([{"description": "Risk two"}]))
        data = self._json()
        self.assertEqual(len(data["sessions"]), 2)
        descriptions = {r["description"] for r in data["risks_mentioned"]}
        self.assertEqual(descriptions, {"Risk one", "Risk two"})

    def test_rerunning_a_session_replaces_its_slice(self):
        """Idempotency — the push-duplication bug recurred in 6.3 and 6.4."""
        self._call(session_date="01.03.2026", stakeholder_role="CTO",
                   risks_json=json.dumps([{"description": "Risk one"}]))
        self._call(session_date="01.03.2026", stakeholder_role="CTO",
                   risks_json=json.dumps([{"description": "Risk one, reworded"}]))
        data = self._json()
        self.assertEqual(len(data["sessions"]), 1)
        self.assertEqual(len(data["risks_mentioned"]), 1)
        self.assertEqual(data["risks_mentioned"][0]["description"], "Risk one, reworded")

    def test_no_risks_writes_no_file(self):
        self._call()
        self.assertIsNone(self._json())

    def test_empty_risks_leaves_an_existing_file_untouched(self):
        """Absence means 'nothing supplied this time', never 'delete what was recorded'."""
        self._call(session_date="01.03.2026", stakeholder_role="CTO",
                   risks_json=json.dumps([{"description": "Risk one"}]))
        self._call(session_date="01.03.2026", stakeholder_role="CTO", risks_json="[]")
        data = self._json()
        self.assertEqual(len(data["risks_mentioned"]), 1)
        self.assertEqual(data["risks_mentioned"][0]["description"], "Risk one")

    def test_malformed_risks_json_returns_an_error_and_does_not_raise(self):
        result = self._call(risks_json='[123]')
        self.assertIn("❌", result)
        self.assertIsNone(self._json())

    def test_markdown_report_shows_the_risks(self):
        """Otherwise the .md and the .json describe the same session differently."""
        with patch("skills.elicitation_conduct_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            mod42.process_elicitation_results(
                **{**PROCESS_BASE,
                   "risks_json": json.dumps([{"description": "Vendor lock-in"}])})
        content = mock_sa.call_args[0][0]
        self.assertIn("Vendor lock-in", content)

    def test_alternative_field_spellings_are_accepted(self):
        """6.3 accepts `risk`/`source` on read, so 4.2 accepts them on write. The
        tolerance is deliberate and was previously unpinned."""
        self._call(risks_json=json.dumps([{"risk": "Alt spelling", "source": "CFO"}]))
        risks = self._json()["risks_mentioned"]
        self.assertEqual(risks[0]["description"], "Alt spelling")
        self.assertEqual(risks[0]["stakeholder"], "CFO")

    def test_items_without_any_description_key_are_rejected(self):
        """The wrong-FIELD-NAME case — this repo's most repeated defect class. Dropping
        them silently while answering '✅ saved' is the worst outcome: the BA believes
        the risks were recorded and 6.3 later finds nothing."""
        result = self._call(risks_json=json.dumps([{"notes": "wrong key"}]))
        self.assertIn("❌", result)
        self.assertIn("description", result)

    def test_corrupt_stored_file_does_not_crash_the_tool(self):
        """The loader validated the container but iterated its elements, so a stored
        file holding a string raised — and the Markdown report was lost with it,
        because the JSON is written first."""
        path = mod42._elicitation_results_path(self.PID)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        for blob in ({"sessions": ["oops"]},
                     {"sessions": [{"session_date": "x", "stakeholder_role": "y",
                                    "session_type": "Interview",
                                    "risks_mentioned": "oops"}]}):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(blob, f)
            result = self._call(risks_json=json.dumps([{"description": "New risk"}]))
            self.assertNotIn("❌", result)

    def test_a_hand_written_legacy_file_is_not_destroyed(self):
        """A file with a top-level risks_mentioned and no sessions is what a BA would
        write while the producer did not exist. The project rule is 'never delete
        data', so those risks are migrated, not overwritten."""
        path = mod42._elicitation_results_path(self.PID)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"risks_mentioned": [
                {"description": "Hand written risk", "stakeholder": "BA"}]}, f)

        self._call(risks_json=json.dumps([{"description": "New risk"}]))

        descriptions = [r.get("description") for r in self._json()["risks_mentioned"]]
        self.assertIn("Hand written risk", descriptions)
        self.assertIn("New risk", descriptions)

if __name__ == "__main__":
    unittest.main(verbosity=2)
