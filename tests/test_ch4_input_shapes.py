"""tests/test_ch4_input_shapes.py — regression tests for the Chapter 4 audit (2026-07-20).

Every Chapter 4 tool takes structured input as a JSON string written by an LLM, so a
wrong SHAPE (a list of strings where objects are expected, an object where a list is)
is a routine failure mode. Before the fix, ELEVEN call sites across all five modules
raised AttributeError/TypeError out of the tool instead of returning a readable
"❌ ..." string — an exception escaping an MCP tool surfaces as a protocol error the
BA cannot act on.

Found by the E2E pass, not by the 88 pre-existing Ch4 unit tests, which only ever fed
well-formed input.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import setup_mocks, BaseMCPTest

setup_mocks()

import skills.elicitation_mcp as e41
import skills.elicitation_conduct_mcp as e42
import skills.elicitation_confirm_mcp as e43
import skills.elicitation_communicate_mcp as e44
import skills.elicitation_collaborate_mcp as e45

PID = "shape_check"


class Ch4ShapeMixin:
    def assert_rejected(self, result, field):
        """The tool must return a readable error naming the offending parameter."""
        self.assertIsInstance(result, str, "tool did not return a string")
        self.assertIn("❌", result)
        self.assertIn(field, result)


class TestElicitationPrepShapes(BaseMCPTest, Ch4ShapeMixin):
    """4.1 — save_elicitation_plan, create_google_form."""

    def _plan(self, **kw):
        defaults = dict(
            project_name=PID, goals="g",
            stakeholders_json='[{"name": "Jane Doe", "role": "Sponsor"}]',
            technique="Interview", technique_rationale="r",
            questions_or_agenda="q", expected_outcomes="o")
        return e41.save_elicitation_plan(**{**defaults, **kw})

    def test_stakeholders_as_strings_rejected(self):
        self.assert_rejected(self._plan(stakeholders_json='["Jane Doe"]'), "stakeholders_json")

    def test_stakeholders_as_object_rejected(self):
        self.assert_rejected(self._plan(stakeholders_json='{"name": "Jane"}'), "stakeholders_json")

    def test_stakeholders_required(self):
        self.assert_rejected(self._plan(stakeholders_json=""), "stakeholders_json")

    def test_valid_stakeholders_accepted(self):
        self.assertIn("✅", self._plan())

    def test_google_form_questions_as_object_rejected(self):
        result = e41.create_google_form(title="t", description="d",
                                        questions_json='{"text": "Q1"}')
        self.assert_rejected(result, "questions_json")

    def test_google_form_questions_as_strings_rejected(self):
        result = e41.create_google_form(title="t", description="d",
                                        questions_json='["Q1", "Q2"]')
        self.assert_rejected(result, "questions_json")


class TestElicitationConductShapes(BaseMCPTest, Ch4ShapeMixin):
    """4.2 — process/compare/CR/registry."""

    def _process(self, **kw):
        defaults = dict(
            project_name=PID, session_date="12.03.2026", stakeholder_role="Head of Sales",
            session_type="Interview", stakeholder_profile_json='{"influence": "High"}',
            pains_json='[{"title": "p"}]', requirements_json='{"functional": ["FR-001"]}',
            gaps_and_signals="", ba_recommendations="",
            maturity_level="Medium", maturity_notes="")
        return e42.process_elicitation_results(**{**defaults, **kw})

    def test_pains_as_strings_rejected(self):
        self.assert_rejected(self._process(pains_json='["a pain"]'), "pains_json")

    def test_profile_as_list_rejected(self):
        self.assert_rejected(self._process(stakeholder_profile_json='["High"]'),
                             "stakeholder_profile_json")

    def test_requirements_as_list_rejected(self):
        self.assert_rejected(self._process(requirements_json='["FR-001"]'), "requirements_json")

    def test_valid_process_accepted(self):
        self.assertIn("✅", self._process())

    def test_registry_as_strings_rejected(self):
        result = e42.compare_elicitation_results(
            project_name=PID, sessions_summary="s", contradictions="c",
            requirements_registry_json='["FR-001"]', political_map="p", follow_up_plan="f")
        self.assert_rejected(result, "requirements_registry_json")

    def test_cr_artifacts_as_strings_rejected(self):
        result = e42.save_cr_elicitation_analysis(
            project_name=PID, cr_description="cr", affected_artifacts_json='["FR-001"]',
            outdated_data="", follow_up_questions="", scope_assessment="",
            workshop_needed=False)
        self.assert_rejected(result, "affected_artifacts_json")

    def test_new_stakeholders_as_strings_rejected(self):
        result = e42.update_stakeholder_registry(
            project_name=PID, session_source="s", new_stakeholders_json='["Jane Doe"]')
        self.assert_rejected(result, "new_stakeholders_json")


class TestElicitationConfirmShapes(BaseMCPTest, Ch4ShapeMixin):
    """4.3 — the producer whose artifact 7.1 consumes."""

    def _check(self, **kw):
        defaults = dict(
            project_name=PID, source_artifacts_json='[{"path": "p"}]',
            issues_json='[{"issue_id": "ISS-001", "criterion": "Completeness"}]',
            readiness_status="Needs Rework", readiness_rationale="r",
            needs_clarification=False, clarification_questions_json="[]", ba_decision="d")
        return e43.run_consistency_check(**{**defaults, **kw})

    def test_issues_as_strings_rejected(self):
        self.assert_rejected(self._check(issues_json='["ISS-001"]'), "issues_json")

    def test_source_artifacts_as_strings_rejected(self):
        self.assert_rejected(self._check(source_artifacts_json='["path.md"]'),
                             "source_artifacts_json")

    def test_clarification_questions_as_strings_rejected(self):
        self.assert_rejected(self._check(clarification_questions_json='["why?"]'),
                             "clarification_questions_json")

    def test_valid_check_accepted(self):
        self.assertNotIn("❌", self._check())

    def _confirm(self, **kw):
        defaults = dict(
            project_name=PID, stakeholder_role="Head of Sales", consistency_check_path="p",
            confirmed_requirements_json='{"functional": [{"id": "FR-001"}]}',
            resolved_issues_json="[]", open_issues_json="[]",
            final_readiness="Conditionally Ready", next_tasks="n")
        return e43.save_confirmed_elicitation_result(**{**defaults, **kw})

    def test_confirmed_requirements_as_list_rejected(self):
        self.assert_rejected(self._confirm(confirmed_requirements_json='["FR-001"]'),
                             "confirmed_requirements_json")

    def test_open_issues_as_strings_rejected(self):
        self.assert_rejected(self._confirm(open_issues_json='["ISS-002"]'), "open_issues_json")

    def test_valid_confirm_accepted(self):
        self.assertNotIn("❌", self._confirm())


class TestElicitationCommunicateShapes(BaseMCPTest, Ch4ShapeMixin):
    """4.4 — package / log / schedule."""

    def test_key_messages_as_strings_rejected(self):
        result = e44.prepare_communication_package(
            project_name=PID, source_artifact_path="p", audience_role="Developer",
            audience_profile_json='{"attitude": "Neutral"}', adapted_content="c",
            key_messages_json='["a message"]', recommended_format="Email",
            recommended_channel="ch", open_questions="", ba_notes="")
        self.assert_rejected(result, "key_messages_json")

    def test_audience_profile_as_list_rejected(self):
        result = e44.prepare_communication_package(
            project_name=PID, source_artifact_path="p", audience_role="Developer",
            audience_profile_json='["Neutral"]', adapted_content="c",
            key_messages_json='[{"message": "m"}]', recommended_format="Email",
            recommended_channel="ch", open_questions="", ba_notes="")
        self.assert_rejected(result, "audience_profile_json")

    def test_log_participants_as_strings_rejected(self):
        result = e44.log_communication(
            project_name=PID, communication_package_path="p", audience_role="Developer",
            communication_date="20.03.2026", channel_used="Email",
            participants_json='["Alex Kim"]', understanding_status="No Response",
            feedback_summary="", action_items_json="[]", needs_followup=False,
            followup_deadline="")
        self.assert_rejected(result, "participants_json")

    def test_schedule_stakeholders_as_strings_rejected(self):
        result = e44.check_communication_schedule(
            project_name=PID, today_date="01.04.2026", stakeholders_json='["Sponsor"]',
            communication_log_json="[]", triggered_events_json="[]")
        self.assert_rejected(result, "stakeholders_json")

    def test_schedule_log_as_strings_rejected(self):
        result = e44.check_communication_schedule(
            project_name=PID, today_date="01.04.2026",
            stakeholders_json='[{"role": "Sponsor"}]',
            communication_log_json='["Developer"]', triggered_events_json="[]")
        self.assert_rejected(result, "communication_log_json")


class TestElicitationCollaborateShapes(BaseMCPTest, Ch4ShapeMixin):
    """4.5 — decision log / meeting notes."""

    def _decision(self, **kw):
        defaults = dict(
            project_name=PID, decision_date="28.03.2026", decision_statement="s",
            context="c", alternatives_json='[{"option": "o"}]', decision_maker="m",
            participants_json='[{"name": "Mark Lee"}]', decision_type="Other",
            affected_artifacts_json="[]", rationale="r", risks="")
        return e45.log_decision(**{**defaults, **kw})

    def test_decision_participants_as_strings_rejected(self):
        self.assert_rejected(self._decision(participants_json='["Mark Lee"]'),
                             "participants_json")

    def test_alternatives_as_strings_rejected(self):
        self.assert_rejected(self._decision(alternatives_json='["Keep 1M"]'),
                             "alternatives_json")

    def test_valid_decision_accepted(self):
        self.assertNotIn("❌", self._decision())

    def _notes(self, **kw):
        defaults = dict(
            project_name=PID, meeting_date="28.03.2026", meeting_type="Workshop",
            participants_json='[{"name": "Jane Doe"}]', agenda_json="[]",
            discussion_summary="d", decisions_json="[]", action_items_json="[]",
            open_questions="", risks_identified="", next_meeting="")
        return e45.save_meeting_notes(**{**defaults, **kw})

    def test_notes_participants_as_strings_rejected(self):
        self.assert_rejected(self._notes(participants_json='["Jane Doe"]'), "participants_json")

    def test_action_items_as_strings_rejected(self):
        self.assert_rejected(self._notes(action_items_json='["Update FR-002"]'),
                             "action_items_json")

    def test_valid_notes_accepted(self):
        self.assertNotIn("❌", self._notes())


class TestSharedValidators(unittest.TestCase):
    """The helpers themselves — one implementation shared by Ch3 and Ch4 so sibling
    tools cannot drift apart (the drift already seen in the 5.5 gate)."""

    def setUp(self):
        from skills.common import (
            parse_json_list, parse_json_str_list, parse_json_dict_list, parse_json_dict)
        self.p_list = parse_json_list
        self.p_str = parse_json_str_list
        self.p_dicts = parse_json_dict_list
        self.p_dict = parse_json_dict

    def test_malformed_json_reports_the_field(self):
        _, err = self.p_dicts("{oops", "my_field")
        self.assertIn("my_field", err)
        self.assertIn("❌", err)

    def test_optional_empty_is_not_an_error(self):
        value, err = self.p_dicts("", "my_field")
        self.assertEqual((value, err), ([], ""))

    def test_required_empty_is_an_error(self):
        _, err = self.p_dicts("", "my_field", required=True)
        self.assertIn("my_field", err)

    def test_required_rejects_empty_array(self):
        _, err = self.p_dicts("[]", "my_field", required=True)
        self.assertIn("non-empty", err)

    def test_dict_list_rejects_non_objects(self):
        _, err = self.p_dicts('[{"a": 1}, "oops"]', "my_field")
        self.assertIn("objects", err)
        self.assertIn("str", err)

    def test_str_list_rejects_non_strings(self):
        _, err = self.p_str('["ok", {"a": 1}]', "my_field")
        self.assertIn("strings", err)

    def test_dict_rejects_a_list(self):
        _, err = self.p_dict('["a"]', "my_field")
        self.assertIn("JSON object", err)

    def test_plain_list_accepts_mixed_items(self):
        value, err = self.p_list('["a", {"b": 1}]', "my_field")
        self.assertEqual(err, "")
        self.assertEqual(len(value), 2)

    def test_valid_shapes_pass_through(self):
        self.assertEqual(self.p_dicts('[{"a": 1}]', "f"), ([{"a": 1}], ""))
        self.assertEqual(self.p_dict('{"a": 1}', "f"), ({"a": 1}, ""))
        self.assertEqual(self.p_str('["a"]', "f"), (["a"], ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
