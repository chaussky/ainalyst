"""
tests/test_ch4_45.py — Tests for Chapter 4.5: Manage Stakeholder Collaboration
MCP file: skills/elicitation_collaborate_mcp.py
Tools: log_decision, save_meeting_notes, update_engagement_status

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

import skills.elicitation_collaborate_mcp as mod45


# ---------------------------------------------------------------------------
# Helper data
# ---------------------------------------------------------------------------

ALTERNATIVES_SOAP_VS_REST = json.dumps([
    {
        "option": "SOAP",
        "reason_rejected": "An outdated standard, no support in modern client libraries",
    },
    {
        "option": "GraphQL",
        "reason_rejected": "Overkill for the task; 1C v8.3 doesn't support it natively",
    },
])

PARTICIPANTS_TECH = json.dumps([
    {"name": "Sergey Krasnov", "position": "Proposed REST API"},
    {"name": "Petr Sidorov", "position": "Confirmed feasibility"},
    {"name": "Anna BA", "position": "Recorded the decision"},
])

PARTICIPANTS_WORKSHOP = json.dumps([
    {"name": "Ivan Ivanov", "position": "Business representative"},
    {"name": "Anna BA", "position": "Facilitator"},
    {"name": "Petr Sidorov", "position": "Developer"},
    {"name": "Sergey Krasnov", "position": "Architect"},
])

AGENDA_WORKSHOP = json.dumps([
    {"item": "Review of requirements FR-001–FR-010", "owner": "Anna BA"},
    {"item": "1C integration questions", "owner": "Sergey Krasnov"},
    {"item": "MVP prioritization", "owner": "Ivan Ivanov"},
])

DECISIONS_WORKSHOP = json.dumps([
    {
        "decision": "REST API via /api/v1/1c/sync, batch every 15 minutes",
        "decision_maker": "Sergey Krasnov",
    },
    {
        "decision": "Move FR-007 out of MVP scope, implement in v2.0",
        "decision_maker": "Ivan Ivanov",
    },
])

ACTION_ITEMS_WORKSHOP = json.dumps([
    {"task": "Update FR-007 — mark as out of MVP scope", "owner": "Anna BA", "due": "2025-03-21"},
    {"task": "Prepare Swagger for the 1C integration", "owner": "Petr Sidorov", "due": "2025-03-28"},
])


# ---------------------------------------------------------------------------
# log_decision
# ---------------------------------------------------------------------------

class TestLogDecision(BaseMCPTest):
    """Tests for 4.5: log_decision."""

    def _call(self, **overrides):
        defaults = {
            "project_name": "crm_upgrade",
            "decision_date": "2025-03-19",
            "decision_statement": "Use REST API for the integration with 1C v8.3",
            "context": "We need to choose the integration protocol with the corporate ERP",
            "alternatives_json": ALTERNATIVES_SOAP_VS_REST,
            "decision_maker": "Architect Sergey Krasnov",
            "participants_json": PARTICIPANTS_TECH,
            "decision_type": "Architectural",
            "affected_artifacts_json": json.dumps([
                {"artifact": "FR-001", "impact": "Update the wording — add REST API"},
                {"artifact": "NFR-002", "impact": "Add API security requirements"},
            ]),
            "rationale": "REST is better documented, supported by modern libraries, feasible on 1C v8.3+",
            "risks": "Compatibility with the specific 1C version must be validated on the vendor's side",
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_collaborate_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod45.log_decision(**kwargs)

    # --- happy path across all decision types ---

    def test_type_requirement(self):
        """Decision type: Requirement."""
        result = self._call(
            decision_type="Requirement",
            decision_statement="FR-007 is moved out of MVP scope",
            rationale="Not critical for launch",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_type_priority(self):
        """Decision type: Priority."""
        result = self._call(
            decision_type="Priority",
            decision_statement="FR-001 — Must Have, FR-007 — Could Have",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_type_architectural(self):
        """Decision type: Architectural."""
        result = self._call(decision_type="Architectural")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_type_process(self):
        """Decision type: Process."""
        result = self._call(
            decision_type="Process",
            decision_statement="Approve requirements at weekly meetings",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_type_scope(self):
        """Decision type: Scope."""
        result = self._call(
            decision_type="Scope",
            decision_statement="The analytics module is moved to v2.0",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_type_other(self):
        """Decision type: Other."""
        result = self._call(decision_type="Other")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- edge cases ---

    def test_no_alternatives(self):
        """There were no alternatives — the only option."""
        result = self._call(
            alternatives_json=json.dumps([]),
            rationale="The only technically available option",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_no_affected_artifacts(self):
        """The decision doesn't affect artifacts directly."""
        result = self._call(affected_artifacts_json=json.dumps([]))
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_no_risks(self):
        """No risks."""
        result = self._call(risks="")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_single_participant(self):
        """Only one participant (a sole decision)."""
        result = self._call(
            participants_json=json.dumps([
                {"name": "Director", "position": "Made the decision alone"}
            ])
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_save_artifact_called(self):
        """save_artifact is called exactly once."""
        with patch("skills.elicitation_collaborate_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            mod45.log_decision(
                project_name="crm_upgrade",
                decision_date="2025-03-19",
                decision_statement="REST API",
                context="Protocol choice",
                alternatives_json=ALTERNATIVES_SOAP_VS_REST,
                decision_maker="Architect",
                participants_json=PARTICIPANTS_TECH,
                decision_type="Architectural",
                affected_artifacts_json=json.dumps([]),
                rationale="The best choice",
                risks="",
            )
            mock_sa.assert_called_once()

    # --- error cases ---

    def test_invalid_alternatives_json(self):
        result = self._call(alternatives_json="{bad}")
        self.assertIn("❌", result)

    def test_invalid_participants_json(self):
        result = self._call(participants_json="{bad json}")
        self.assertIn("❌", result)

    def test_invalid_affected_artifacts_json(self):
        result = self._call(affected_artifacts_json="not json")
        self.assertIn("❌", result)

    def test_returns_string(self):
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# save_meeting_notes
# ---------------------------------------------------------------------------

class TestSaveMeetingNotes(BaseMCPTest):
    """Tests for 4.5: save_meeting_notes."""

    def _call(self, **overrides):
        defaults = {
            "project_name": "crm_upgrade",
            "meeting_date": "2025-03-19",
            "meeting_type": "Workshop",
            "participants_json": PARTICIPANTS_WORKSHOP,
            "agenda_json": AGENDA_WORKSHOP,
            "discussion_summary": "Reviewed FR-001–FR-010. Agreed on REST API. Moved FR-007 to v2.0.",
            "decisions_json": DECISIONS_WORKSHOP,
            "action_items_json": ACTION_ITEMS_WORKSHOP,
            "open_questions": "Does the API need OAuth authorization, or is an API key enough?",
            "risks_identified": "The 1C vendor hasn't confirmed compatibility — a delay risk",
            "next_meeting": "2025-03-26",
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_collaborate_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod45.save_meeting_notes(**kwargs)

    # --- happy path across all meeting types ---

    def test_type_interview(self):
        """Meeting type: Interview."""
        result = self._call(meeting_type="Interview")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_type_workshop(self):
        """Meeting type: Workshop."""
        result = self._call(meeting_type="Workshop")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_type_status_meeting(self):
        """Meeting type: Status Meeting."""
        result = self._call(
            meeting_type="Status Meeting",
            discussion_summary="Discussed progress: 70% of requirements collected",
            decisions_json=json.dumps([]),
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_type_facilitation(self):
        """Meeting type: Facilitation Session."""
        result = self._call(meeting_type="Facilitation Session")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_type_one_on_one(self):
        """Meeting type: 1-on-1 Meeting."""
        result = self._call(
            meeting_type="1-on-1 Meeting",
            participants_json=json.dumps([
                {"name": "Ivan Ivanov", "position": "Director"},
                {"name": "Anna BA", "position": "Analyst"},
            ]),
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_type_presentation(self):
        """Meeting type: Presentation."""
        result = self._call(
            meeting_type="Presentation",
            discussion_summary="Presented the requirements to the sponsor. Approved.",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_type_other(self):
        """Meeting type: Other."""
        result = self._call(meeting_type="Other")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- edge cases ---

    def test_no_decisions(self):
        """A meeting without decisions (discussion only)."""
        result = self._call(decisions_json=json.dumps([]))
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_no_action_items(self):
        """No action items after the meeting."""
        result = self._call(action_items_json=json.dumps([]))
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_no_open_questions(self):
        """All questions are closed."""
        result = self._call(open_questions="")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_no_next_meeting(self):
        """No next meeting."""
        result = self._call(next_meeting="")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_no_risks(self):
        """No identified risks."""
        result = self._call(risks_identified="")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_save_artifact_called(self):
        """save_artifact is called exactly once."""
        with patch("skills.elicitation_collaborate_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            mod45.save_meeting_notes(
                project_name="crm_upgrade",
                meeting_date="2025-03-19",
                meeting_type="Workshop",
                participants_json=PARTICIPANTS_WORKSHOP,
                agenda_json=AGENDA_WORKSHOP,
                discussion_summary="Requirements discussion",
                decisions_json=DECISIONS_WORKSHOP,
                action_items_json=ACTION_ITEMS_WORKSHOP,
                open_questions="",
                risks_identified="",
                next_meeting="",
            )
            mock_sa.assert_called_once()

    # --- error cases ---

    def test_invalid_participants_json(self):
        result = self._call(participants_json="{bad}")
        self.assertIn("❌", result)

    def test_invalid_agenda_json(self):
        result = self._call(agenda_json="not json")
        self.assertIn("❌", result)

    def test_invalid_decisions_json(self):
        result = self._call(decisions_json="{bad}")
        self.assertIn("❌", result)

    def test_invalid_action_items_json(self):
        result = self._call(action_items_json="not json")
        self.assertIn("❌", result)

    def test_returns_string(self):
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# update_engagement_status
# ---------------------------------------------------------------------------

class TestUpdateEngagementStatus(BaseMCPTest):
    """Tests for 4.5: update_engagement_status."""

    def _call(self, **overrides):
        defaults = {
            "project_name": "crm_upgrade",
            "stakeholder_role": "Sales Director",
            "change_date": "2025-03-19",
            "attitude_before": "Champion",
            "attitude_after": "Neutral",
            "engagement_level_before": "Active",
            "engagement_level_after": "Passive",
            "signal_observed": "Missed two status meetings, hasn't answered emails for 5 days",
            "probable_cause": "A suspected reorganization in his department",
            "ba_action_taken": "Messaged him directly, scheduled a 1-on-1 meeting",
            "ba_action_planned": "Find out the reason for the change in position, escalation may be needed",
            "escalation_needed": False,
            "escalation_to": "",
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_collaborate_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod45.update_engagement_status(**kwargs)

    # --- happy path — all attitude transition combinations ---

    def test_champion_to_neutral(self):
        """Champion → Neutral."""
        result = self._call(attitude_before="Champion", attitude_after="Neutral")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_champion_to_blocker(self):
        """Champion → Blocker (a critical transition)."""
        result = self._call(
            attitude_before="Champion",
            attitude_after="Blocker",
            signal_observed="Publicly voiced disagreement at the board meeting",
            escalation_needed=True,
            escalation_to="PM → Steering Committee",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_neutral_to_champion(self):
        """Neutral → Champion (a positive transition)."""
        result = self._call(
            attitude_before="Neutral",
            attitude_after="Champion",
            engagement_level_before="Passive",
            engagement_level_after="Active",
            signal_observed="Started actively suggesting improvements, brought in additional stakeholders",
            ba_action_taken="Engaged in a detailed discussion of the dashboard requirements",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_neutral_to_blocker(self):
        """Neutral → Blocker."""
        result = self._call(
            attitude_before="Neutral",
            attitude_after="Blocker",
            escalation_needed=True,
            escalation_to="PM",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_blocker_to_neutral(self):
        """Blocker → Neutral (the situation improves)."""
        result = self._call(
            attitude_before="Blocker",
            attitude_after="Neutral",
            signal_observed="After a meeting with the PM, agreed to a compromise",
            ba_action_taken="Organized a meeting between the PM and the stakeholder",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_blocker_to_champion(self):
        """Blocker → Champion (the best outcome)."""
        result = self._call(
            attitude_before="Blocker",
            attitude_after="Champion",
            signal_observed="After the prototype demo, became an active supporter",
            ba_action_planned="Involve as a key tester in UAT",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- engagement level transitions ---

    def test_passive_to_active(self):
        """Passive → Active."""
        result = self._call(
            engagement_level_before="Passive",
            engagement_level_after="Active",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_absent_to_passive(self):
        """Absent → Passive."""
        result = self._call(
            engagement_level_before="Absent",
            engagement_level_after="Passive",
            signal_observed="Showed up at a meeting for the first time",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_active_to_absent(self):
        """Active → Absent (an alarming signal)."""
        result = self._call(
            engagement_level_before="Active",
            engagement_level_after="Absent",
            escalation_needed=True,
            escalation_to="PM",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- escalation scenarios ---

    def test_escalation_needed_with_target(self):
        """Escalation needed — a target is specified."""
        result = self._call(
            escalation_needed=True,
            escalation_to="PM → Steering Committee",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_no_escalation(self):
        """No escalation needed."""
        result = self._call(escalation_needed=False, escalation_to="")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_save_artifact_called(self):
        """save_artifact is called exactly once."""
        with patch("skills.elicitation_collaborate_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            mod45.update_engagement_status(
                project_name="crm_upgrade",
                stakeholder_role="Director",
                change_date="2025-03-19",
                attitude_before="Champion",
                attitude_after="Neutral",
                engagement_level_before="Active",
                engagement_level_after="Passive",
                signal_observed="Stopped responding",
                probable_cause="Unknown",
                ba_action_taken="Messaged",
                ba_action_planned="Meeting",
                escalation_needed=False,
                escalation_to="",
            )
            mock_sa.assert_called_once()

    def test_returns_string(self):
        self.assertIsInstance(self._call(), str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
