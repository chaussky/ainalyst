"""
tests/test_ch3_ch4.py — Tests for Chapters 3 and 4

Strategy: mocks are installed via conftest.setup_mocks().
Modules are imported afterwards — FastMCP and pydantic are mocked.
save_artifact is mocked → the functions return the real content.

Chapter 3 is tested via planning_mcp.py directly (like all other chapters).
planning.py was removed — all logic lives in planning_mcp.py and common.py.
"""

import json
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tests.conftest import setup_mocks, BaseMCPTest
setup_mocks()

# Chapter 3 — test the MCP server directly (like all other chapters)
import skills.planning_mcp as mod3

# Chapter 4 — import after setup_mocks
import skills.elicitation_mcp as mod41
import skills.elicitation_conduct_mcp as mod42
import skills.elicitation_confirm_mcp as mod43
import skills.elicitation_communicate_mcp as mod44
import skills.elicitation_collaborate_mcp as mod45


# ---------------------------------------------------------------------------
# Chapter 3 — Planning (tested via planning_mcp.py)
# ---------------------------------------------------------------------------

class TestPlanning(BaseMCPTest):

    def test_ba_approach_agile(self):
        """High change frequency + low uncertainty → Agile."""
        result = mod3.suggest_ba_approach(
            project_id="test_project",
            change_frequency="High",
            uncertainty="Low",
            regulatory_need=False,
        )
        self.assertIsInstance(result, str)
        self.assertIn("Agile", result)

    def test_ba_approach_predictive_regulatory(self):
        """Regulatory project with low uncertainty → regulatory override."""
        result = mod3.suggest_ba_approach(
            project_id="test_project",
            change_frequency="Low",
            uncertainty="Low",
            regulatory_need=True,
        )
        self.assertIsInstance(result, str)
        # regulatory override changes Predictive → Hybrid or keeps Predictive
        # the main thing — it doesn't crash and returns a string
        self.assertGreater(len(result), 0)

    def test_ba_approach_returns_string(self):
        """suggest_ba_approach always returns a string."""
        result = mod3.suggest_ba_approach(
            project_id="test_project",
            change_frequency="Low",
            uncertainty="Low",
        )
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_classify_stakeholder_key_player(self):
        """High influence + High interest → Key Players."""
        from skills.planning_mcp import _classify_stakeholder
        zone, strategy, freq = _classify_stakeholder("High", "High")
        self.assertEqual(zone, "Key Players")

    def test_classify_stakeholder_context_setters(self):
        """High influence + Low interest → Context Setters."""
        from skills.planning_mcp import _classify_stakeholder
        zone, strategy, freq = _classify_stakeholder("High", "Low")
        self.assertEqual(zone, "Context Setters")

    def test_classify_stakeholder_subjects(self):
        """Low influence + High interest → Subjects."""
        from skills.planning_mcp import _classify_stakeholder
        zone, strategy, freq = _classify_stakeholder("Low", "High")
        self.assertEqual(zone, "Subjects")

    def test_classify_stakeholder_crowd(self):
        """Low influence + Low interest → Crowd."""
        from skills.planning_mcp import _classify_stakeholder
        zone, strategy, freq = _classify_stakeholder("Low", "Low")
        self.assertEqual(zone, "Crowd")

    def test_stakeholder_plan_valid_json(self):
        """Valid JSON → the plan contains the stakeholder names."""
        stakeholders = [
            {"name": "Ivan Ivanov", "role": "Director", "influence": "High", "interest": "High", "attitude": "Champion"},
            {"name": "Petr Petrov", "role": "User", "influence": "Low", "interest": "Low", "attitude": "Neutral"},
        ]
        result = mod3.plan_stakeholder_engagement(
            project_id="test_project",
            stakeholders_json=json.dumps(stakeholders),
        )
        self.assertIn("Ivan Ivanov", result)
        self.assertIn("Petr Petrov", result)

    def test_stakeholder_plan_invalid_json(self):
        """Invalid JSON → error message."""
        result = mod3.plan_stakeholder_engagement(
            project_id="test_project",
            stakeholders_json="not a json {{{",
        )
        self.assertIn("❌", result)

    def test_stakeholder_plan_empty_list(self):
        """Empty list → warning without crashing."""
        result = mod3.plan_stakeholder_engagement(
            project_id="test_project",
            stakeholders_json="[]",
        )
        self.assertIsInstance(result, str)


# ---------------------------------------------------------------------------
# Helper class for Chapter 4 tests
# ---------------------------------------------------------------------------

class BaseCh4Test(BaseMCPTest):
    """
    Base class for Chapter 4 tests.
    Chapter 4 MCP tools call save_artifact() — mocked to "✅ Saved".
    The tests check that:
    1. The function doesn't crash on valid input
    2. The function returns an error message on invalid input
    """
    def assertSucceeds(self, result: str):
        """The function ran successfully (didn't return ❌)."""
        self.assertIsInstance(result, str)
        self.assertNotIn("❌ Error parsing", result)
        self.assertNotIn("Traceback", result)

    def assertFails(self, result: str):
        """The function returned an error."""
        self.assertIn("❌", result)


# ---------------------------------------------------------------------------
# Chapter 4.1 — Prepare for Elicitation
# ---------------------------------------------------------------------------

class TestElicitationPrep(BaseCh4Test):

    def test_save_plan_basic(self):
        """A basic elicitation plan raises no errors."""
        result = mod41.save_elicitation_plan(
            project_name="CRM Project",
            goals="Elicit integration requirements",
            stakeholders_json=json.dumps([
                {"name": "Ivan", "role": "Manager", "key_questions": ["What is needed?"]}
            ]),
            technique="Interview",
            technique_rationale="Better for deep understanding",
            questions_or_agenda="1. Which processes to automate?\n2. Which integrations are needed?",
            expected_outcomes="A list of CRM requirements",
        )
        self.assertSucceeds(result)

    def test_save_plan_invalid_json(self):
        """Invalid stakeholders JSON → error message."""
        result = mod41.save_elicitation_plan(
            project_name="Test",
            goals="Goal",
            stakeholders_json="{invalid}",
            technique="Interview",
            technique_rationale="",
            questions_or_agenda="",
            expected_outcomes="",
        )
        self.assertFails(result)


# ---------------------------------------------------------------------------
# Chapter 4.2 — Conduct Elicitation
# ---------------------------------------------------------------------------

class TestElicitationConduct(BaseCh4Test):

    def test_process_results_basic(self):
        """Basic session results are processed without errors."""
        result = mod42.process_elicitation_results(
            project_name="CRM Project",
            session_date="2025-03-17",
            stakeholder_role="Sales Manager",
            session_type="Interview",
            stakeholder_profile_json=json.dumps({
                "name": "Ivan", "role": "Manager",
                "influence": "High", "interest": "High",
                "key_expectations": "Request automation",
                "key_concerns": "Implementation complexity",
                "related_stakeholders": [],
            }),
            pains_json=json.dumps([{
                "title": "Requests take too long to process",
                "description": "Manual processing takes 2 hours",
                "frequency": "Daily",
                "business_impact": "Customer churn",
                "quote": "We lose money every day",
            }]),
            requirements_json=json.dumps({
                "functional": [{"id": "FR-001", "statement": "Integration with 1C", "priority": "High"}],
                "non_functional": [],
                "constraints": [],
                "business_rules": [],
            }),
            gaps_and_signals="Didn't clarify the 1C version",
            ba_recommendations="Need to clarify the technical details",
            maturity_level="Medium",
            maturity_notes="Understands the business, but not IT",
        )
        self.assertSucceeds(result)

    def test_save_cr_analysis(self):
        """CR analysis is saved without errors."""
        result = mod42.save_cr_elicitation_analysis(
            project_name="CRM Project",
            cr_description="Add an analytics module",
            affected_artifacts_json=json.dumps([
                {"artifact": "FR-001", "type": "FR", "affected": True, "change_type": "Update"}
            ]),
            outdated_data="The old reporting requirements are outdated",
            follow_up_questions="What report format is needed?",
            scope_assessment="Medium scope — 3-4 new requirements",
            workshop_needed=False,
        )
        self.assertSucceeds(result)

    def test_update_stakeholder_registry(self):
        """Updating the stakeholder registry raises no errors."""
        result = mod42.update_stakeholder_registry(
            project_name="CRM Project",
            session_source="Interview with the Sales Manager 2025-03-17",
            new_stakeholders_json=json.dumps([
                {
                    "name": "Anna Smirnova",
                    "role": "Sales Director",
                    "influence": "High",
                    "interest": "High",
                    "attitude": "Champion",
                    "contact": "anna@company.com",
                    "comm_frequency": "Weekly",
                    "comm_triggers": ["Major decisions"],
                }
            ]),
        )
        self.assertSucceeds(result)

    def test_process_results_invalid_json(self):
        """Invalid JSON → error."""
        result = mod42.process_elicitation_results(
            project_name="Test",
            session_date="2025-03-17",
            stakeholder_role="Test",
            session_type="Interview",
            stakeholder_profile_json="{bad json}",
            pains_json="[]",
            requirements_json="[]",
            gaps_and_signals="",
            ba_recommendations="",
            maturity_level="Medium",
            maturity_notes="",
        )
        self.assertFails(result)


# ---------------------------------------------------------------------------
# Chapter 4.3 — Confirm Elicitation Results
# ---------------------------------------------------------------------------

class TestElicitationConfirm(BaseCh4Test):

    def test_run_consistency_check_no_issues(self):
        """A check with no issues — doesn't crash."""
        result = mod43.run_consistency_check(
            project_name="CRM Project",
            source_artifacts_json=json.dumps([
                {"path": "governance_plans/4_2_test.md",
                 "stakeholder_role": "Manager", "session_date": "2025-03-17"}
            ]),
            issues_json=json.dumps([]),
            readiness_status="Ready for analysis",
            readiness_rationale="All criteria are met",
            needs_clarification=False,
            clarification_questions_json=json.dumps([]),
            ba_decision="Hand off to 6.x",
        )
        self.assertSucceeds(result)

    def test_run_consistency_check_with_issues(self):
        """A check with issues — doesn't crash."""
        issues = [{
            "criterion": "Unambiguity",
            "severity": "High",
            "description": "FR-001 can be interpreted two ways",
            "affected_requirement": "FR-001",
            "recommendation": "Clarify the wording",
            "source_artifact": "governance_plans/4_2_test.md",
        }]
        result = mod43.run_consistency_check(
            project_name="CRM Project",
            source_artifacts_json=json.dumps([
                {"path": "governance_plans/4_2_test.md",
                 "stakeholder_role": "Manager", "session_date": "2025-03-17"}
            ]),
            issues_json=json.dumps(issues),
            readiness_status="Needs rework",
            readiness_rationale="Critical issues",
            needs_clarification=True,
            clarification_questions_json=json.dumps([
                {"stakeholder_role": "Manager", "issue_id": "ISS-001",
                 "question": "What exactly is meant in FR-001?"}
            ]),
            ba_decision="Clarify with the stakeholder",
        )
        self.assertSucceeds(result)

    def test_save_confirmed_result(self):
        """The final artifact is saved without errors."""
        reqs = {
            "functional": [
                {"id": "FR-001", "statement": "Integration with 1C",
                 "acceptance_criteria": "Data is synchronized"}
            ],
            "non_functional": [],
            "constraints": ["Budget up to 500k"],
            "business_rules": [],
        }
        result = mod43.save_confirmed_elicitation_result(
            project_name="CRM Project",
            stakeholder_role="Sales Manager",
            consistency_check_path="governance_plans/4_3_check.md",
            confirmed_requirements_json=json.dumps(reqs),
            resolved_issues_json=json.dumps([]),
            open_issues_json=json.dumps([]),
            final_readiness="Ready for analysis",
            next_tasks="Hand off to 6.1",
        )
        self.assertSucceeds(result)


# ---------------------------------------------------------------------------
# Chapter 4.4 — Communicate Business Analysis Information
# ---------------------------------------------------------------------------

class TestElicitationCommunicate(BaseCh4Test):

    def test_prepare_package_business(self):
        result = mod44.prepare_communication_package(
            project_name="CRM Project",
            source_artifact_path="governance_plans/4_3_confirmed.md",
            audience_role="Business sponsor",
            audience_profile_json=json.dumps({
                "name": "Ivan Ivanov", "role": "Director",
                "influence": "High", "interest": "High"
            }),
            adapted_content="The CRM requirements are approved. Integration with 1C is planned.",
            key_messages_json=json.dumps([
                {"message": "The project is on track", "why_it_matters": "The budget is fine"}
            ]),
            recommended_format="Brief summary",
            recommended_channel="Email",
            open_questions="",
            ba_notes="",
        )
        self.assertSucceeds(result)

    def test_prepare_package_developer(self):
        result = mod44.prepare_communication_package(
            project_name="CRM Project",
            source_artifact_path="governance_plans/4_3_confirmed.md",
            audience_role="Developer",
            audience_profile_json=json.dumps({
                "name": "Petr", "role": "Backend Developer",
                "influence": "Low", "interest": "High"
            }),
            adapted_content="FR-001: REST API integration with 1C v8.3",
            key_messages_json=json.dumps([
                {"message": "REST API", "why_it_matters": "A modern standard"}
            ]),
            recommended_format="Technical description",
            recommended_channel="Confluence / document",
            open_questions="Which version of 1C?",
            ba_notes="",
        )
        self.assertSucceeds(result)

    def test_log_communication(self):
        """The communication event is logged without errors."""
        result = mod44.log_communication(
            project_name="CRM Project",
            communication_package_path="governance_plans/4_4_package.md",
            audience_role="Business sponsor",
            communication_date="2025-03-17",
            channel_used="Email",
            participants_json=json.dumps([{"name": "Ivan Ivanov", "role": "Director"}]),
            understanding_status="Understood and agrees",
            feedback_summary="Approved the requirements",
            action_items_json=json.dumps([
                {"task": "Sign the minutes", "owner": "Ivan", "due": "2025-03-20"}
            ]),
            needs_followup=False,
            followup_deadline="",
        )
        self.assertSucceeds(result)

    def test_check_communication_schedule(self):
        """The communication schedule is checked without errors."""
        stakeholders = [
            {
                "name": "Ivan Ivanov",
                "role": "Director",
                "influence": "High",
                "comm_frequency": "Weekly",
                "comm_triggers": ["Major decision", "Milestone"],
            }
        ]
        comm_log = [
            {
                "stakeholder_name": "Ivan Ivanov",
                "date": "2025-03-01",
                "channel": "Email",
                "needs_followup": False,
            }
        ]
        result = mod44.check_communication_schedule(
            project_name="CRM Project",
            today_date="2025-03-17",
            stakeholders_json=json.dumps(stakeholders),
            communication_log_json=json.dumps(comm_log),
            triggered_events_json=json.dumps([
                {"event_type": "Milestone", "description": "Requirements approved"}
            ]),
        )
        self.assertSucceeds(result)


# ---------------------------------------------------------------------------
# Chapter 4.5 — Manage Stakeholder Collaboration
# ---------------------------------------------------------------------------

class TestElicitationCollaborate(BaseCh4Test):

    def test_log_decision(self):
        result = mod45.log_decision(
            project_name="CRM Project",
            decision_date="2025-03-17",
            decision_statement="Use REST API for the integration with 1C",
            context="We need to choose the integration protocol",
            alternatives_json=json.dumps([
                {"option": "SOAP", "reason_rejected": "An outdated standard"}
            ]),
            decision_maker="Architect",
            participants_json=json.dumps([
                {"name": "Architect", "position": "For REST"},
                {"name": "BA", "position": "Neutral"},
            ]),
            decision_type="Architectural",
            affected_artifacts_json=json.dumps([
                {"artifact": "FR-005", "impact": "The API description must be updated"},
            ]),
            rationale="REST is more modern and better documented",
            risks="Validation is needed on the 1C side",
        )
        self.assertSucceeds(result)

    def test_save_meeting_notes(self):
        result = mod45.save_meeting_notes(
            project_name="CRM Project",
            meeting_date="2025-03-17",
            meeting_type="Workshop",
            participants_json=json.dumps([
                {"name": "Ivan", "position": "Sponsor"},
                {"name": "Anna", "position": "BA"},
            ]),
            agenda_json=json.dumps([
                {"item": "Review of FR-001–FR-010", "owner": "Anna"},
                {"item": "Integration questions", "owner": "Ivan"},
            ]),
            discussion_summary="Requirements approved with comments",
            decisions_json=json.dumps([
                {"decision": "Clarify FR-007 before the next meeting", "decision_maker": "BA"}
            ]),
            action_items_json=json.dumps([
                {"task": "Clarify FR-007", "owner": "Anna", "due": "2025-03-20"}
            ]),
            open_questions="Which version of 1C?",
            risks_identified="Tech lead unavailability",
            next_meeting="2025-03-24",
        )
        self.assertSucceeds(result)

    def test_update_engagement_status(self):
        """The change in engagement is recorded without errors."""
        result = mod45.update_engagement_status(
            project_name="CRM Project",
            stakeholder_role="Sales Director",
            change_date="2025-03-17",
            attitude_before="Champion",
            attitude_after="Neutral",
            engagement_level_before="Active",
            engagement_level_after="Passive",
            signal_observed="Stopped responding, missed 2 meetings",
            probable_cause="Internal changes in the department",
            ba_action_taken="Scheduled a one-on-one meeting",
            ba_action_planned="Find out the reason for the change in position",
            escalation_needed=False,
            escalation_to="",
        )
        self.assertSucceeds(result)


class TestPlanSeedsRegistryEndToEnd(BaseMCPTest):
    """A2 seam, exercised through the REAL producers of all three chapters rather than
    against the producer's own reader.

    The unit tests assert via `load_stakeholder_registry` — i.e. the writer reading its
    own file — which structurally cannot catch the class of defect that produced finding
    7.4-A, where the consumer had the filename, the container key and the field name all
    wrong at once. This test goes 3.2 → 4.2 → 3.2 re-run → 7.4.
    """

    P = "seam_e2e"

    def _plan(self, stakeholders):
        return mod3.plan_stakeholder_engagement(
            project_id=self.P, stakeholders_json=json.dumps(stakeholders))

    def _registry(self):
        from skills.common import stakeholder_registry_path
        with open(stakeholder_registry_path(self.P), encoding="utf-8") as f:
            return json.load(f)

    def _person(self, name):
        return next((s for s in self._registry()["stakeholders"]
                     if s.get("name", "").lower() == name.lower()), None)

    def test_seam_survives_a_rerun_after_elicitation(self):
        # 3.2 — the BA states no attitude for Jane, so 'Neutral' is an ASSUMPTION
        self._plan([
            {"name": "Jane", "role": "CFO", "influence": "High", "interest": "High"},
            {"name": "John", "role": "PO", "influence": "High", "interest": "Low",
             "attitude": "Champion"},
        ])
        self.assertIsNotNone(self._person("Jane"), "3.2 must seed the living registry")
        self.assertEqual(self._person("Jane")["attitude"], "Neutral",
                         "the assumed default applies on creation")

        # 4.2 — an interview establishes what she actually is
        mod42.update_stakeholder_registry(
            project_name=self.P, session_source="Interview with Jane, 2026-03-15",
            new_stakeholders_json=json.dumps([
                {"name": "Jane", "role": "CFO", "attitude": "Blocker",
                 "coverage_status": "Elicited", "department": "Finance"},
            ]))
        self.assertEqual(self._person("Jane")["attitude"], "Blocker")

        # 3.2 re-run, again stating no attitude
        self._plan([
            {"name": "Jane", "role": "CFO", "influence": "Medium", "interest": "High"},
        ])
        jane = self._person("Jane")
        self.assertEqual(jane["attitude"], "Blocker",
                         "an ASSUMED default must never overwrite an elicited attitude")
        self.assertEqual(jane["coverage_status"], "Elicited",
                         "elicitation progress must survive a planning re-run")
        self.assertEqual(jane["department"], "Finance",
                         "fields only 4.2 knows about must survive")
        self.assertEqual(jane["influence"], "Medium",
                         "a genuinely restated source field must still update")
        self.assertIsNotNone(self._person("John"),
                             "someone dropped from the plan is not deleted from the registry")

    def test_74_reads_the_registry_32_seeded(self):
        """The consumer contract, verified against the real consumer — not asserted
        against the producer's own reader."""
        import skills.requirements_architecture_mcp as mod74
        self._plan([{"name": "Jane", "role": "CFO", "influence": "High",
                     "interest": "High"}])
        path = mod74._stakeholders_path(self.P)
        self.assertTrue(os.path.exists(path),
                        f"7.4 looks for {path}, which 3.2 must have written")
        with open(path, encoding="utf-8") as f:
            names = [s.get("name") for s in json.load(f).get("stakeholders", [])]
        self.assertIn("Jane", names, "container key and field name must match 7.4's reader")

    def test_wrong_shaped_stakeholders_json_is_rejected_not_crashed(self):
        """This JSON is written by an LLM: a list of strings is an ordinary case, and an
        unhandled exception from an MCP tool is a protocol error (class CH3-A / CH4-A)."""
        for payload in ('["Jane", "John"]',
                        '[{"name": "A", "influence": "High", "interest": "High"}, "John"]'):
            result = mod3.plan_stakeholder_engagement(
                project_id=self.P, stakeholders_json=payload)
            self.assertIn("❌", result, f"payload {payload} must return a readable error")


if __name__ == "__main__":
    unittest.main(verbosity=2)
