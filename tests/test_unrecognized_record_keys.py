"""
tests/test_unrecognized_record_keys.py

A record whose keys the tool does not recognise used to render as em-dashes in the
DELIVERED document while the tool answered success. Three sites, all found by reading
the artifacts of one end-to-end run rather than by checking for an error string:

    3.5 -> BA Plan          **Metrics:**  - :  → < 10% per sprint
    4.4 -> Comm Schedule    - [—] **—**: —        (header said "Triggered: 0")
    6.2 -> Goal card        ### 1. —     plus a FALSE SMART note, "metric '?' has
                            no baseline", derived from data it had failed to read

The JSON for these parameters is written by an LLM, so a plausible-but-wrong key
spelling is an ordinary case. 4.2 `_parse_session_risks` already settled the policy for
this class: accept the reasonable spellings, and if the caller supplied records but not
one of them carried the key field, say so instead of answering "saved". Dropping the
content silently and still reporting success is the worst of the three outcomes,
because the analyst believes it was recorded.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.conftest import setup_mocks

setup_mocks()

from skills.common import pick_field
import skills.planning_mcp as p3
import skills.elicitation_communicate_mcp as p44
import skills.future_state_mcp as c62


class TestPickField(unittest.TestCase):

    def test_returns_the_first_non_empty_spelling(self):
        self.assertEqual(pick_field({"metric": "x"}, "name", "metric"), "x")

    def test_empty_string_is_not_a_value(self):
        self.assertEqual(pick_field({"name": "", "metric": "x"}, "name", "metric"), "x")

    def test_missing_everywhere_gives_empty(self):
        self.assertEqual(pick_field({"other": "x"}, "name", "metric"), "")


class TestPerformanceMetrics(unittest.TestCase):
    """3.5 documents {name, baseline, target}; `metric` is the obvious near-miss."""

    def setUp(self):
        self._load, self._save = p3._load_plan, p3._save_plan
        self.plan = {"project_id": "p"}
        p3._load_plan = lambda project_id: self.plan
        p3._save_plan = lambda plan, project_id: None

    def tearDown(self):
        p3._load_plan, p3._save_plan = self._load, self._save

    def test_a_near_miss_spelling_is_accepted(self):
        out = p3.evaluate_ba_performance("p", metrics_json=json.dumps([
            {"metric": "Requirements volatility", "target": "< 10% per sprint"}]))
        self.assertIn("Requirements volatility", out)
        self.assertNotIn("• : ", out)

    def test_records_with_no_recognisable_name_are_refused(self):
        out = p3.evaluate_ba_performance("p", metrics_json=json.dumps([
            {"kpi_identifier": "x", "goal": "y"}]))
        self.assertTrue(out.startswith("❌"), out[:120])
        self.assertIn("name", out)


class TestTriggeredEvents(unittest.TestCase):
    """4.4 documents {event_type, description, date}.

    This tool RETURNS the save_artifact result, not the document, so the assertions
    capture what was handed to the writer.
    """

    def setUp(self):
        self.captured = []
        self._orig = p44.save_artifact
        p44.save_artifact = lambda content, **kw: self.captured.append(content) or "saved"

    def tearDown(self):
        p44.save_artifact = self._orig

    def test_a_near_miss_spelling_is_accepted(self):
        p44.check_communication_schedule(
            "p", "10.08.2026",
            stakeholders_json=json.dumps([
                {"role": "Sponsor", "influence": "High", "comm_frequency": "Weekly",
                 "last_communication_date": "01.08.2026"}]),
            communication_log_json="[]",
            triggered_events_json=json.dumps([
                {"event": "Model validation scheduled", "date": "05.08.2026"}]))
        document = "".join(self.captured)
        self.assertIn("Model validation scheduled", document)
        self.assertNotIn("[—] **—**", document)

    def test_records_with_nothing_recognisable_are_refused(self):
        out = p44.check_communication_schedule(
            "p", "10.08.2026",
            stakeholders_json=json.dumps([{"role": "Sponsor", "influence": "High"}]),
            communication_log_json="[]",
            triggered_events_json=json.dumps([{"what_happened": "something"}]))
        self.assertTrue(out.startswith("❌"), out[:120])


class TestGoalObjectives(unittest.TestCase):
    """6.2 documents {title, metric, baseline, target, deadline}."""

    def setUp(self):
        self._lg, self._sg = c62._load_goals, c62._save_goals
        self._lr = c62._load_repo
        self.goals = {"project_id": "p", "goals": []}
        c62._load_goals = lambda project_id: self.goals
        c62._save_goals = lambda data: None
        c62._load_repo = lambda project_id: None

    def tearDown(self):
        c62._load_goals, c62._save_goals = self._lg, self._sg
        c62._load_repo = self._lr

    def test_objective_as_a_name_spelling_is_accepted(self):
        out = c62.define_goals_and_objectives(
            "p", "Decide applications within 24 hours",
            "From submission to a communicated decision.",
            objectives_json=json.dumps([
                {"objective": "Median decision time", "metric": "hours",
                 "baseline": "144", "target": "24", "deadline": "31.12.2026"}]))
        self.assertIn("Median decision time", out)
        self.assertNotIn("### 1. —", out)

    def test_no_false_smart_note_about_a_metric_it_could_not_read(self):
        out = c62.define_goals_and_objectives(
            "p", "Decide applications within 24 hours",
            "From submission to a communicated decision.",
            objectives_json=json.dumps([
                {"objective": "Median decision time", "metric": "hours",
                 "baseline": "144", "target": "24", "deadline": "31.12.2026"}]))
        self.assertNotIn("'?'", out)
        self.assertNotIn("has no baseline", out)

    def test_records_with_no_recognisable_name_are_refused(self):
        out = c62.define_goals_and_objectives(
            "p", "Decide applications within 24 hours",
            "From submission to a communicated decision.",
            objectives_json=json.dumps([{"how_we_measure": "hours"}]))
        self.assertTrue(out.startswith("❌"), out[:120])


if __name__ == "__main__":
    unittest.main()


class TestCommunicationScheduleVocabularies(unittest.TestCase):
    """Two independent vocabulary gaps in one tool, both producing confident falsehoods.

    3.2 assigns comm_frequency from QUADRANT_STRATEGIES (Weekly / At milestones /
    Bi-weekly / Monthly / Quarterly); the checker knew exactly one of those values.
    And log_communication records the 4.4 audience archetype ("Business Sponsor") while
    the stakeholder map carries job titles, so an exact-string join could never match.
    """

    def setUp(self):
        self.captured = []
        self._orig = p44.save_artifact
        p44.save_artifact = lambda content, **kw: self.captured.append(content) or "saved"

    def tearDown(self):
        p44.save_artifact = self._orig

    def _run(self, stakeholders, log="[]"):
        p44.check_communication_schedule(
            "p", "10.08.2026",
            stakeholders_json=json.dumps(stakeholders),
            communication_log_json=log,
            triggered_events_json="[]")
        return "".join(self.captured)

    def test_a_monthly_cadence_from_3_2_is_evaluated(self):
        doc = self._run([{"role": "Subjects rep", "influence": "Medium",
                          "comm_frequency": "Monthly",
                          "last_communication_date": "01.01.2026"}])
        self.assertNotIn("Все коммуникации идут по плану", doc)
        self.assertIn("Subjects rep", doc)

    def test_at_milestones_matches_at_milestone(self):
        doc = self._run([{"role": "Sponsor", "influence": "High",
                          "comm_frequency": "At milestones"}])
        self.assertNotIn("unrecognised", doc.lower())

    def test_an_unknown_cadence_does_not_produce_a_clean_bill_of_health(self):
        doc = self._run([{"role": "Sponsor", "influence": "High",
                          "comm_frequency": "Whenever he asks"}])
        self.assertNotIn("Все коммуникации идут по плану", doc)
        self.assertIn("Whenever he asks", doc)

    def test_a_logged_communication_is_matched_by_the_audience_archetype(self):
        doc = self._run(
            [{"name": "Marina Volkova", "role": "Business Sponsor", "influence": "High",
              "comm_frequency": "Weekly"}],
            log=json.dumps([{"audience_role": "Business Sponsor",
                             "communication_date": "09.08.2026"}]))
        self.assertNotIn("Коммуникаций пока не записано", doc)

    def test_a_logged_communication_is_matched_by_name(self):
        doc = self._run(
            [{"name": "Marina Volkova", "role": "Head of Retail Lending",
              "influence": "High", "comm_frequency": "Weekly"}],
            log=json.dumps([{"audience_role": "Marina Volkova",
                             "communication_date": "09.08.2026"}]))
        self.assertNotIn("Коммуникаций пока не записано", doc)
