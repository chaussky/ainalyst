"""4.1 reads the planned work period and cross-checks the technique (B3-1).

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from skills.common import ba_plan_path
from skills.elicitation_mcp import save_elicitation_plan

PROJECT = "b31_ch41"
STAKEHOLDERS = json.dumps([
    {"name": "Jane Doe", "role": "Process Owner", "influence": "High",
     "interest": "High", "what_to_learn": "Pain points"}])


def _seed_plan(section=None, techniques=None, approach_label="Adaptive (Agile)"):
    path = ba_plan_path(PROJECT)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    plan = {"project_id": PROJECT,
            "ba_approach": {"recommended_approach": approach_label,
                            "techniques": techniques if techniques is not None else []}}
    if section is not None:
        plan["ba_activities"] = section
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f)


class TestPlannedPeriod(unittest.TestCase):

    def setUp(self):
        self._cwd = os.getcwd()
        self._tmp = tempfile.mkdtemp()
        os.chdir(self._tmp)
        # `save_artifact` is mocked suite-wide (ADR-068 — see
        # tests/test_ch3_ba_activities.py::TestReport and every tests/test_ch4_4* /
        # tests/test_ch5_5* file), so `save_elicitation_plan` never actually writes a
        # file to disk here. The plan's original helper globbed the report directory
        # for a real .md file, which the suite-wide mock never produces. Captured
        # from the call instead, matching the established pattern — this changes
        # only how the rendered text is retrieved, not any assertion below.
        patcher = patch("skills.elicitation_mcp.save_artifact")
        self._mock_save_artifact = patcher.start()
        self._mock_save_artifact.return_value = ""
        self.addCleanup(patcher.stop)

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _artefact_text(self):
        self.assertTrue(self._mock_save_artifact.call_args,
                         "the elicitation plan was not written")
        return self._mock_save_artifact.call_args[0][0]

    def _save(self, technique="Workshop"):
        return save_elicitation_plan(
            project_name=PROJECT, goals="Learn the process",
            stakeholders_json=STAKEHOLDERS, technique=technique,
            technique_rationale="Fastest way to align", questions_or_agenda="1. Scope",
            expected_outcomes="Agreed scope")

    def test_the_period_covering_41_is_named_with_its_effort(self):
        _seed_plan({"timing_form": "iterations", "periods": [
            {"name": "Iteration 1", "tasks": ["4.1"], "effort": "High",
             "when": "Aug 2026", "deliverables": []}]})
        self._save()
        text = self._artefact_text()
        self.assertIn("Iteration 1", text)
        # "High" alone is printed by the stakeholder table (influence / interest), so
        # it cannot tell the effort column from that.
        self.assertIn("planned effort: High", text)
        self.assertIn("Aug 2026", text)

    def test_a_generated_skeleton_is_not_presented_as_the_bas_own_plan(self):
        """The 3.1b section marks a machine-made skeleton `generated`, and the BA plan
        report says so. A consumer that cannot see the flag states invented periods and
        efforts as planned facts — silent degradation that concludes instead of saying
        less."""
        _seed_plan({"timing_form": "iterations", "generated": True, "periods": [
            {"name": "Iteration 1", "tasks": ["4"], "effort": "High", "when": "",
             "deliverables": []}]})
        self._save()
        text = self._artefact_text()
        self.assertIn("Iteration 1", text)
        self.assertIn("generated", text.lower())

    def test_a_period_the_ba_typed_carries_no_generated_notice(self):
        _seed_plan({"timing_form": "iterations", "generated": False, "periods": [
            {"name": "Iteration 1", "tasks": ["4"], "effort": "High", "when": "",
             "deliverables": []}]})
        self._save()
        self.assertNotIn("generated", self._artefact_text().lower())

    def test_a_chapter_wide_period_covers_41(self):
        _seed_plan({"timing_form": "phases", "periods": [
            {"name": "Stage 1 — Discovery", "tasks": ["4"], "effort": "Medium",
             "when": "", "deliverables": []}]})
        self._save()
        self.assertIn("Stage 1 — Discovery", self._artefact_text())

    def test_a_plan_that_does_not_cover_41_says_nothing_about_a_period(self):
        _seed_plan({"timing_form": "phases", "periods": [
            {"name": "Stage 2", "tasks": ["7.1"], "effort": "High", "when": "",
             "deliverables": []}]})
        self._save()
        self.assertNotIn("Этап 2", self._artefact_text())

    def test_no_plan_at_all_changes_nothing(self):
        out = self._save()
        self.assertIn("✅", out)
        self.assertNotIn("Planned work period", self._artefact_text())

    def test_the_block_keeps_the_documents_own_spacing(self):
        """Every other separator in this artefact is followed by a blank line. This is
        a delivered document, so the inserted block must not glue `---` to the next
        heading."""
        _seed_plan({"timing_form": "phases", "periods": [
            {"name": "Stage 1", "tasks": ["4"], "effort": "High", "when": "",
             "deliverables": []}]})
        self._save()
        self.assertIn("---\n\n## Elicitation Goals", self._artefact_text())

    def test_an_unreadable_plan_warns_in_the_tool_output(self):
        path = ba_plan_path(PROJECT)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("{not json")
        out = self._save()
        self.assertIn("⚠️", out)


class TestTechniqueCrossCheck(unittest.TestCase):

    def setUp(self):
        self._cwd = os.getcwd()
        self._tmp = tempfile.mkdtemp()
        os.chdir(self._tmp)
        patcher = patch("skills.elicitation_mcp.save_artifact")
        self._mock_save_artifact = patcher.start()
        self._mock_save_artifact.return_value = ""
        self.addCleanup(patcher.stop)

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _artefact_text(self):
        self.assertTrue(self._mock_save_artifact.call_args,
                         "the elicitation plan was not written")
        return self._mock_save_artifact.call_args[0][0]

    def _save(self, technique):
        return save_elicitation_plan(
            project_name=PROJECT, goals="G", stakeholders_json=STAKEHOLDERS,
            technique=technique, technique_rationale="R",
            questions_or_agenda="1. Q", expected_outcomes="O")

    def test_a_planned_technique_is_confirmed(self):
        _seed_plan(techniques=["Workshops", "Prototyping", "Risk Analysis"])
        self._save("Workshop")
        text = self._artefact_text()
        # The sentence, not the emoji: a bare "✅" would match anything the artefact
        # might print for an unrelated reason later.
        self.assertIn("is among the techniques 3.1 recommended", text)
        self.assertIn("Workshop, Prototyping", text)   # only the intersection is listed

    def test_a_departure_is_named_without_blocking(self):
        _seed_plan(techniques=["Document Analysis", "Interviews", "Prototyping"])
        out = self._save("Benchmarking")
        self.assertIn("✅", out)                      # the plan is still saved
        text = self._artefact_text()
        self.assertIn("3.1 recommended", text)
        self.assertIn("Document Analysis", text)
        self.assertIn("Not a blocker", text)

    def test_plural_and_singular_names_are_the_same_technique(self):
        _seed_plan(techniques=["Interviews"])
        self._save("Interview")
        self.assertIn("is among the techniques 3.1 recommended", self._artefact_text())

    def test_an_agile_plan_says_there_is_nothing_to_cross_check(self):
        """APPROACH_MATRIX gives Backlog Management / User Stories / Retrospectives for
        every adaptive cell — NONE is an elicitation technique. Comparing outside the
        intersection would flag every agile project, which is how the 4.4 join failed
        by construction."""
        _seed_plan(techniques=["Backlog Management", "User Stories", "Retrospectives"])
        self._save("Workshop")
        text = self._artefact_text()
        self.assertNotIn("⚠️", text)
        self.assertIn("no elicitation techniques", text)
        self.assertIn("Backlog Management", text)

    def test_a_techniques_field_of_the_wrong_shape_is_ignored_quietly(self):
        _seed_plan(techniques="Workshops")
        out = self._save("Workshop")
        self.assertIn("✅", out)


if __name__ == "__main__":
    unittest.main()
