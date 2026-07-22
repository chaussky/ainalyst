"""
tests/test_ch4_44.py — Tests for Chapter 4.4: Communicate Business Analysis Information
MCP file: skills/elicitation_communicate_mcp.py
Tools: prepare_communication_package, log_communication, check_communication_schedule

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

import skills.elicitation_communicate_mcp as mod44


# ---------------------------------------------------------------------------
# Helper data
# ---------------------------------------------------------------------------

AUDIENCE_BUSINESS = json.dumps({
    "name": "Ivan Ivanov",
    "role": "Sales Director",
    "influence": "High",
    "interest": "High",
    "preferred_detail_level": "Executive summary",
    "preferred_format": "Email + Presentation",
})

AUDIENCE_DEVELOPER = json.dumps({
    "name": "Petr Sidorov",
    "role": "Backend Developer",
    "influence": "Low",
    "interest": "High",
    "preferred_detail_level": "Full technical specification",
    "preferred_format": "Confluence + Jira",
})

AUDIENCE_ARCHITECT = json.dumps({
    "name": "Sergey Krasnov",
    "role": "Architect",
    "influence": "High",
    "interest": "Medium",
    "preferred_detail_level": "Architectural decisions and constraints",
    "preferred_format": "Confluence",
})

KEY_MESSAGES = json.dumps([
    {
        "message": "Integration with 1C agreed — REST API, batch every 15 min",
        "why_it_matters": "A key technical decision of the project",
    },
    {
        "message": "Launch is planned for 2025-06-01",
        "why_it_matters": "The deadline is not shifting",
    },
])

COMM_PACKAGE_PATH = "governance_plans/reports/4_4_package_crm_upgrade.md"


# ---------------------------------------------------------------------------
# prepare_communication_package
# ---------------------------------------------------------------------------

class TestPrepareCommunicationPackage(BaseMCPTest):
    """Tests for 4.4: prepare_communication_package."""

    def _call(self, **overrides):
        defaults = {
            "project_name": "crm_upgrade",
            "source_artifact_path": "governance_plans/reports/4_3_confirmed_crm_upgrade.md",
            "audience_role": "Business Sponsor",
            "audience_profile_json": AUDIENCE_BUSINESS,
            "adapted_content": "The CRM requirements are approved. Integration with 1C agreed. Launch 2025-06-01.",
            "key_messages_json": KEY_MESSAGES,
            "recommended_format": "Formal Document",
            "recommended_channel": "Email",
            "open_questions": "",
            "ba_notes": "",
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_communicate_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod44.prepare_communication_package(**kwargs)

    # --- happy path across all audiences ---

    def test_audience_business(self):
        """Audience: Business Sponsor."""
        result = self._call(
            audience_role="Business Sponsor",
            audience_profile_json=AUDIENCE_BUSINESS,
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_audience_manager(self):
        """Audience: Manager."""
        result = self._call(
            audience_role="Manager",
            audience_profile_json=AUDIENCE_BUSINESS,
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_audience_developer(self):
        """Audience: Developer."""
        result = self._call(
            audience_role="Developer",
            audience_profile_json=AUDIENCE_DEVELOPER,
            adapted_content="FR-001: REST API /orders/sync, batch every 15 minutes. Endpoint: POST /api/v1/1c/sync",
            recommended_format="Informal Document",
            recommended_channel="Confluence / Document",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_audience_architect(self):
        """Audience: Architect / Tech Lead."""
        result = self._call(
            audience_role="Architect / Tech Lead",
            audience_profile_json=AUDIENCE_ARCHITECT,
            adapted_content="Integration via REST API. Constraint: 1C v8.3+. Batch every 15 min.",
            recommended_format="Formal Document",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_audience_tester(self):
        """Audience: Tester."""
        result = self._call(
            audience_role="Tester",
            adapted_content="FR-001 AC: synchronization without errors within 15 min. NFR-001 AC: P95 < 2s at 100 users.",
            recommended_format="Formal Document",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- happy path across all formats ---

    def test_format_presentation(self):
        """Format: Presentation."""
        result = self._call(recommended_format="Presentation")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_format_email(self):
        """Format: Email."""
        result = self._call(recommended_format="Email")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_format_one_on_one(self):
        """Format: 1-on-1 Meeting."""
        result = self._call(recommended_format="1-on-1 Meeting")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_format_group_meeting(self):
        """Format: Group Meeting."""
        result = self._call(recommended_format="Group Meeting")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- edge cases ---

    def test_with_open_questions(self):
        """There are open questions."""
        result = self._call(
            open_questions="Should NFRs be included in the Executive Summary for the director?",
            ba_notes="The director is technically savvy — NFRs can be mentioned briefly",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_empty_key_messages(self):
        """No key messages."""
        result = self._call(key_messages_json=json.dumps([]))
        self.assertIsInstance(result, str)

    def test_save_artifact_called(self):
        """save_artifact is called exactly once."""
        with patch("skills.elicitation_communicate_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            mod44.prepare_communication_package(
                project_name="crm_upgrade",
                source_artifact_path="governance_plans/reports/4_3.md",
                audience_role="Business Sponsor",
                audience_profile_json=AUDIENCE_BUSINESS,
                adapted_content="Requirements summary",
                key_messages_json=KEY_MESSAGES,
                recommended_format="Email",
                recommended_channel="Email",
                open_questions="",
                ba_notes="",
            )
            mock_sa.assert_called_once()

    # --- error cases ---

    def test_invalid_audience_profile_json(self):
        """Invalid profile JSON → error."""
        result = self._call(audience_profile_json="{bad json}")
        self.assertIn("❌", result)

    def test_invalid_key_messages_json(self):
        """Invalid key-messages JSON → error."""
        result = self._call(key_messages_json="not json")
        self.assertIn("❌", result)

    def test_returns_string(self):
        """Always returns a string."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# log_communication
# ---------------------------------------------------------------------------

class TestLogCommunication(BaseMCPTest):
    """Tests for 4.4: log_communication."""

    PARTICIPANTS = json.dumps([
        {"name": "Ivan Ivanov", "role": "Sales Director"},
        {"name": "Anna BA", "role": "Business Analyst"},
    ])

    ACTION_ITEMS = json.dumps([
        {"task": "Sign the requirements minutes", "owner": "Ivan Ivanov", "due": "2025-03-20"},
    ])

    def _call(self, **overrides):
        defaults = {
            "project_name": "crm_upgrade",
            "communication_package_path": COMM_PACKAGE_PATH,
            "audience_role": "Business Sponsor",
            "communication_date": "2025-03-19",
            "channel_used": "Email",
            "participants_json": self.PARTICIPANTS,
            "understanding_status": "Understood and Agreed",
            "feedback_summary": "Approved the requirements, asked to clarify the deployment timeline",
            "action_items_json": self.ACTION_ITEMS,
            "needs_followup": False,
            "followup_deadline": "",
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_communicate_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod44.log_communication(**kwargs)

    # --- happy path across all channels ---

    def test_channel_email(self):
        """Channel: Email."""
        result = self._call(channel_used="Email")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_channel_one_on_one(self):
        """Channel: 1-on-1 Meeting."""
        result = self._call(channel_used="1-on-1 Meeting")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_channel_group_meeting(self):
        """Channel: Group Meeting."""
        result = self._call(channel_used="Group Meeting")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_channel_messenger(self):
        """Channel: Messenger."""
        result = self._call(channel_used="Messenger")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_channel_confluence(self):
        """Channel: Confluence / Document."""
        result = self._call(channel_used="Confluence / Document")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_channel_other(self):
        """Channel: Other."""
        result = self._call(channel_used="Other")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- happy path across all understanding statuses ---

    def test_status_understood_agreed(self):
        result = self._call(understanding_status="Understood and Agreed")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_status_partial(self):
        result = self._call(understanding_status="Partially Understood")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_status_not_understood(self):
        """Status: Not Understood → followup needed."""
        result = self._call(
            understanding_status="Not Understood — Needs Repeat",
            needs_followup=True,
            followup_deadline="2025-03-22",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_status_no_response(self):
        result = self._call(
            understanding_status="No Response",
            needs_followup=True,
            followup_deadline="2025-03-21",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_status_disagreed(self):
        """Status: Disagreed — escalation."""
        result = self._call(
            understanding_status="Disagreed",
            feedback_summary="Thinks integration with 1C is not needed — manual entry is enough",
            needs_followup=True,
            followup_deadline="2025-03-20",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- edge cases ---

    def test_empty_action_items(self):
        """No action items."""
        result = self._call(action_items_json=json.dumps([]))
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_followup_needed_with_deadline(self):
        """needs_followup=True with a deadline."""
        result = self._call(needs_followup=True, followup_deadline="2025-03-25")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- error cases ---

    def test_invalid_participants_json(self):
        result = self._call(participants_json="{bad}")
        self.assertIn("❌", result)

    def test_invalid_action_items_json(self):
        result = self._call(action_items_json="not json")
        self.assertIn("❌", result)

    def test_returns_string(self):
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# check_communication_schedule
# ---------------------------------------------------------------------------

class TestCheckCommunicationSchedule(BaseMCPTest):
    """Tests for 4.4: check_communication_schedule."""

    STAKEHOLDERS = [
        {
            "name": "Ivan Ivanov",
            "role": "Sales Director",
            "influence": "High",
            "comm_frequency": "Weekly",
            "comm_triggers": ["Major decision", "Milestone", "Risk identified"],
        },
        {
            "name": "Petr Sidorov",
            "role": "Backend Developer",
            "influence": "Low",
            "comm_frequency": "Bi-weekly",
            "comm_triggers": ["Technical decision"],
        },
    ]

    COMM_LOG = [
        {
            "stakeholder_name": "Ivan Ivanov",
            "date": "2025-03-10",
            "channel": "Email",
            "needs_followup": False,
        },
        {
            "stakeholder_name": "Petr Sidorov",
            "date": "2025-03-15",
            "channel": "Confluence / Document",
            "needs_followup": False,
        },
    ]

    def _call(self, **overrides):
        defaults = {
            "project_name": "crm_upgrade",
            "today_date": "2025-03-19",
            "stakeholders_json": json.dumps(self.STAKEHOLDERS),
            "communication_log_json": json.dumps(self.COMM_LOG),
            "triggered_events_json": json.dumps([]),
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_communicate_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod44.check_communication_schedule(**kwargs)

    def test_no_triggered_events(self):
        """A scheduled check with no trigger events."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_with_milestone_trigger(self):
        """There is a trigger event: Milestone."""
        result = self._call(
            triggered_events_json=json.dumps([
                {"event_type": "Milestone", "description": "Requirements approved and signed"}
            ])
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_with_risk_trigger(self):
        """There is a trigger event: Risk identified."""
        result = self._call(
            triggered_events_json=json.dumps([
                {"event_type": "Risk identified",
                 "description": "The 1C vendor announced an API change in v8.4"}
            ])
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_multiple_triggers(self):
        """Several trigger events."""
        result = self._call(
            triggered_events_json=json.dumps([
                {"event_type": "Milestone", "description": "Requirements approved"},
                {"event_type": "Major decision", "description": "Integration architecture chosen"},
            ])
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_empty_comm_log(self):
        """No communication history (a new project)."""
        result = self._call(communication_log_json=json.dumps([]))
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_single_stakeholder(self):
        """Only one stakeholder."""
        result = self._call(
            stakeholders_json=json.dumps([self.STAKEHOLDERS[0]])
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- error cases ---

    def test_invalid_stakeholders_json(self):
        result = self._call(stakeholders_json="{bad}")
        self.assertIn("❌", result)

    def test_invalid_comm_log_json(self):
        result = self._call(communication_log_json="not json")
        self.assertIn("❌", result)

    def test_invalid_events_json(self):
        result = self._call(triggered_events_json="{bad}")
        self.assertIn("❌", result)

    def test_returns_string(self):
        self.assertIsInstance(self._call(), str)

    def test_urgent_queue_ordered_by_influence_high_first(self):
        """The urgent (overdue) queue must be ordered by influence: High before
        Medium before Low. Regression for the label-string sort bug that ranked
        'Medium' > 'Low' > 'High' alphabetically, burying High-influence
        stakeholders at the bottom of the queue."""
        stakeholders = [
            {"role": "Low Dev", "influence": "Low",
             "comm_frequency": "Weekly", "last_communication_date": "01.03.2025"},
            {"role": "High Sponsor", "influence": "High",
             "comm_frequency": "Weekly", "last_communication_date": "01.03.2025"},
            {"role": "Medium Manager", "influence": "Medium",
             "comm_frequency": "Weekly", "last_communication_date": "01.03.2025"},
        ]
        with patch("skills.elicitation_communicate_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            mod44.check_communication_schedule(
                project_name="crm_upgrade",
                today_date="20.03.2025",  # all three ~19 days overdue on a Weekly (7d) cadence
                stakeholders_json=json.dumps(stakeholders),
                communication_log_json=json.dumps([]),
                triggered_events_json=json.dumps([]),
            )
            content = mock_sa.call_args.args[0]

        # All three must be present in the urgent section.
        pos_high = content.find("High Sponsor")
        pos_medium = content.find("Medium Manager")
        pos_low = content.find("Low Dev")
        self.assertNotEqual(pos_high, -1, "High-influence stakeholder missing from report")
        self.assertNotEqual(pos_medium, -1, "Medium-influence stakeholder missing from report")
        self.assertNotEqual(pos_low, -1, "Low-influence stakeholder missing from report")
        self.assertLess(pos_high, pos_medium, "High influence must appear before Medium")
        self.assertLess(pos_medium, pos_low, "Medium influence must appear before Low")

    def test_empty_or_missing_cadence_is_reported_not_silently_on_track(self):
        """A stakeholder whose comm_frequency is empty or absent has no cadence
        on record — nobody chose "On Request" for them. Excluding them silently
        and then printing the unqualified "All Communications Are on Track" is a
        confident claim about people the check never evaluated: the same class
        as the unknown-cadence fix, one sub-case over (empty vs unrecognised).
        The registry 4.2 maintains deliberately carries no comm_frequency, so a
        caller building this input from the registry hits this on every card."""
        stakeholders = [
            {"role": "Claims Adjuster", "influence": "Medium", "comm_frequency": ""},
            {"role": "Actuary", "influence": "Low"},  # key absent entirely
        ]
        with patch("skills.elicitation_communicate_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            mod44.check_communication_schedule(
                project_name="crm_upgrade",
                today_date="20.03.2025",
                stakeholders_json=json.dumps(stakeholders),
                communication_log_json=json.dumps([]),
                triggered_events_json=json.dumps([]),
            )
            content = mock_sa.call_args.args[0]
        self.assertNotIn("All Communications Are on Track", content)
        self.assertIn("no communication cadence", content)
        self.assertIn("Claims Adjuster", content)
        self.assertIn("Actuary", content)

    def test_explicit_on_request_cadence_still_clean(self):
        """An EXPLICIT "On Request" is the analyst's choice of a trigger-only
        cadence — excluding it from the overdue check is correct semantics, not
        degradation, so the clean verdict must survive."""
        stakeholders = [
            {"role": "Sponsor", "influence": "High", "comm_frequency": "On Request"},
        ]
        with patch("skills.elicitation_communicate_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            mod44.check_communication_schedule(
                project_name="crm_upgrade",
                today_date="20.03.2025",
                stakeholders_json=json.dumps(stakeholders),
                communication_log_json=json.dumps([]),
                triggered_events_json=json.dumps([]),
            )
            content = mock_sa.call_args.args[0]
        self.assertIn("All Communications Are on Track", content)
        self.assertNotIn("no communication cadence", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
