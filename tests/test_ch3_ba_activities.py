"""3.1 elements .3 (BA Activities) and .4 (Timing) — the writer (B3-1).

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from skills.common import ba_plan_path
from skills.planning_mcp import (
    plan_ba_activities,
    suggest_ba_approach,
)

PROJECT = "b31_writer"


def _read_plan(project_id=PROJECT):
    with open(ba_plan_path(project_id), "r", encoding="utf-8") as f:
        return json.load(f)


class _TempCwd(unittest.TestCase):

    def setUp(self):
        self._cwd = os.getcwd()
        self._tmp = tempfile.mkdtemp()
        os.chdir(self._tmp)

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestFormDerivation(_TempCwd):

    def test_adaptive_derives_iterations_and_names_the_source(self):
        suggest_ba_approach(PROJECT, "High", "High")          # -> Adaptive (Agile)
        out = plan_ba_activities(PROJECT)
        section = _read_plan()["ba_activities"]
        self.assertEqual(section["timing_form"], "iterations")
        self.assertIn("derived from Adaptive (Agile)", section["form_source"])
        # NOT assertIn("iterations", out): the "form not set" warning also names
        # `timing_form="iterations"`, so that assertion would pass with the
        # derivation entirely broken.
        self.assertIn("derived from Adaptive (Agile)", out)

    def test_predictive_derives_phases(self):
        suggest_ba_approach(PROJECT, "Low", "Low")            # -> Predictive (Waterfall)
        plan_ba_activities(PROJECT)
        self.assertEqual(_read_plan()["ba_activities"]["timing_form"], "phases")

    def test_plain_hybrid_asks_instead_of_guessing_and_writes_nothing(self):
        suggest_ba_approach(PROJECT, "Medium", "Medium")      # -> Hybrid
        out = plan_ba_activities(PROJECT)
        self.assertIn("⚠️", out)
        self.assertIn("timing_form", out)
        self.assertNotIn("ba_activities", _read_plan())

    def test_no_31_at_all_asks_and_writes_nothing(self):
        out = plan_ba_activities(PROJECT)
        self.assertIn("⚠️", out)
        self.assertFalse(os.path.exists(ba_plan_path(PROJECT)))

    def test_declared_form_wins_over_the_approach_and_the_conflict_is_named(self):
        suggest_ba_approach(PROJECT, "High", "High")          # -> Adaptive (Agile)
        out = plan_ba_activities(PROJECT, timing_form="phases")
        section = _read_plan()["ba_activities"]
        self.assertEqual(section["timing_form"], "phases")
        self.assertIn("declared by the BA", section["form_source"])
        # "Adaptive (Agile)" alone would also appear in `form_source` if the
        # declaration had been ignored — assert the conflict sentence itself.
        self.assertIn("Stored what you declared", out)
        self.assertIn("Adaptive (Agile)", out)
        self.assertIn("⚠️", out)


class TestSkeleton(_TempCwd):

    def test_iterations_skeleton_is_generated_and_marked(self):
        suggest_ba_approach(PROJECT, "High", "High")
        out = plan_ba_activities(PROJECT)
        section = _read_plan()["ba_activities"]
        self.assertTrue(section["generated"])
        self.assertGreaterEqual(len(section["periods"]), 2)
        self.assertTrue(all(p["name"].startswith("Iteration") for p in section["periods"]))
        self.assertIn("generated", out.lower())

    def test_phases_skeleton_uses_stage_not_the_word_phase(self):
        """"Phase" is taken: `python phase.py` switches the platform's session phase."""
        suggest_ba_approach(PROJECT, "Low", "Low")
        plan_ba_activities(PROJECT)
        names = [p["name"] for p in _read_plan()["ba_activities"]["periods"]]
        self.assertTrue(all(n.startswith("Stage") for n in names), names)
        self.assertFalse([n for n in names if "phase" in n.lower()])

    def test_declared_periods_replace_the_skeleton(self):
        suggest_ba_approach(PROJECT, "High", "High")
        plan_ba_activities(PROJECT, periods_json=json.dumps([
            {"name": "Iteration A", "tasks": ["4.1"], "effort": "High"}]))
        section = _read_plan()["ba_activities"]
        self.assertFalse(section["generated"])
        self.assertEqual([p["name"] for p in section["periods"]], ["Iteration A"])

    def test_periods_without_a_resolvable_form_are_still_stored_with_a_warning(self):
        """Refusing would throw away work the BA already typed."""
        suggest_ba_approach(PROJECT, "Medium", "Medium")      # -> Hybrid
        out = plan_ba_activities(PROJECT, periods_json=json.dumps([
            {"name": "Wave 1", "tasks": ["4"], "effort": "High"}]))
        section = _read_plan()["ba_activities"]
        self.assertEqual(section["timing_form"], "")
        self.assertEqual(section["periods"][0]["name"], "Wave 1")
        self.assertIn("⚠️", out)
        self.assertIn("5.5", out)          # the consequence is named


class TestInputShapes(_TempCwd):

    def setUp(self):
        super().setUp()
        suggest_ba_approach(PROJECT, "High", "High")

    def test_a_bare_string_where_periods_are_expected_returns_a_readable_error(self):
        out = plan_ba_activities(PROJECT, periods_json='"Iteration 1"')
        self.assertIn("❌", out)
        self.assertNotIn("ba_activities", _read_plan())

    def test_a_list_of_strings_where_objects_are_expected(self):
        out = plan_ba_activities(PROJECT, periods_json='["Iteration 1"]')
        self.assertIn("❌", out)

    def test_unknown_task_ids_are_named_but_do_not_block(self):
        out = plan_ba_activities(PROJECT, periods_json=json.dumps([
            {"name": "It 1", "tasks": ["4.1", "8.1", "elicitation"]}]))
        self.assertIn("8.1", out)
        self.assertIn("elicitation", out)
        stored = _read_plan()["ba_activities"]["periods"][0]["tasks"]
        self.assertEqual(stored, ["4.1"])

    def test_tasks_as_a_bare_string_is_accepted_as_one_ref(self):
        plan_ba_activities(PROJECT, periods_json=json.dumps([
            {"name": "It 1", "tasks": "4.1"}]))
        self.assertEqual(_read_plan()["ba_activities"]["periods"][0]["tasks"], ["4.1"])

    def test_an_off_scale_effort_is_kept_and_named(self):
        out = plan_ba_activities(PROJECT, periods_json=json.dumps([
            {"name": "It 1", "tasks": ["4.1"], "effort": "Heroic"}]))
        # The period line prints the effort anyway, so "Heroic" alone cannot tell a
        # warning from silence.
        self.assertIn("outside the Low/Medium/High scale", out)
        self.assertIn("Heroic", out)
        self.assertEqual(_read_plan()["ba_activities"]["periods"][0]["effort"], "Heroic")

    def test_constraints_are_stored_and_counted(self):
        out = plan_ba_activities(PROJECT, timing_constraints_json=json.dumps(
            ["regulatory deadline 2026-12-31", "vendor available from September"]))
        self.assertEqual(
            len(_read_plan()["ba_activities"]["timing_constraints"]), 2)
        self.assertIn("2", out)

    def test_a_damaged_previous_section_does_not_kill_the_only_tool_that_can_fix_it(self):
        path = ba_plan_path(PROJECT)
        plan = _read_plan()
        plan["ba_activities"] = {"periods": "oops"}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(plan, f)
        out = plan_ba_activities(PROJECT)
        self.assertNotIn("❌", out)
        self.assertIsInstance(_read_plan()["ba_activities"]["periods"], list)


class TestStatusLine(_TempCwd):

    def test_the_message_names_every_stored_part(self):
        """An incomplete status line is worse than none — it exists to spare the BA
        from opening the JSON."""
        suggest_ba_approach(PROJECT, "High", "High")
        out = plan_ba_activities(
            PROJECT,
            periods_json=json.dumps([{"name": "It 1", "tasks": ["4.1", "5.3"],
                                      "deliverables": ["Backlog"], "effort": "High",
                                      "when": "Aug 2026"}]),
            timing_constraints_json=json.dumps(["regulatory deadline"]),
            ba_notes="agreed with the sponsor")
        # "4.1" on its own also appears in the "what now reads this" block, so the
        # task list is asserted as the rendered joined string, not as loose ids.
        self.assertIn("tasks: 4.1, 5.3", out)
        for expected in ("It 1", "Backlog", "High", "Aug 2026",
                         "regulatory deadline", "agreed with the sponsor"):
            self.assertIn(expected, out, expected)

    def test_the_message_names_both_readers(self):
        suggest_ba_approach(PROJECT, "High", "High")
        out = plan_ba_activities(PROJECT)
        self.assertIn("5.5", out)
        self.assertIn("4.1", out)


class TestRerun(_TempCwd):

    def test_a_rerun_replaces_the_section_like_the_other_31_35_tools(self):
        suggest_ba_approach(PROJECT, "High", "High")
        plan_ba_activities(PROJECT, periods_json=json.dumps([
            {"name": "It 1", "tasks": ["4.1"]}]))
        plan_ba_activities(PROJECT, periods_json=json.dumps([
            {"name": "It 2", "tasks": ["5.3"]}]))
        names = [p["name"] for p in _read_plan()["ba_activities"]["periods"]]
        self.assertEqual(names, ["It 2"])

    def test_a_rerun_does_not_touch_the_other_sections(self):
        suggest_ba_approach(PROJECT, "High", "High")
        plan_ba_activities(PROJECT)
        plan = _read_plan()
        self.assertIn("Agile", plan["ba_approach"]["recommended_approach"])


class TestReport(_TempCwd):

    def setUp(self):
        super().setUp()
        # `save_artifact` is mocked suite-wide (ADR-068 — see
        # tests/test_ch3_info_mgmt_planning.py::_report_text and every tests/test_ch4_4*
        # / tests/test_ch5_5* file), so `save_ba_plan` never actually writes a file to
        # disk here. The plan's original helper globbed the report directory for a
        # real .md file, which the suite-wide mock never produces. Captured from the
        # call instead, matching the established pattern — this changes only how the
        # rendered text is retrieved, not any assertion below.
        patcher = patch("skills.planning_mcp.save_artifact")
        self._mock_save_artifact = patcher.start()
        self._mock_save_artifact.return_value = "\n\n✅ Artifact saved: `x.md`"
        self.addCleanup(patcher.stop)

    def _report_text(self, project_id=PROJECT):
        self.assertTrue(self._mock_save_artifact.call_args,
                         "the BA plan report was not written")
        return self._mock_save_artifact.call_args[0][0]

    def test_the_section_renders_the_periods_as_a_table(self):
        from skills.planning_mcp import save_ba_plan
        suggest_ba_approach(PROJECT, "High", "High")
        plan_ba_activities(PROJECT, periods_json=json.dumps([
            {"name": "Iteration 1", "tasks": ["4.1", "5.3"],
             "deliverables": ["Backlog"], "effort": "High", "when": "Aug 2026"}]),
            timing_constraints_json=json.dumps(["regulatory deadline 2026-12-31"]),
            ba_notes="agreed with the sponsor")
        save_ba_plan(PROJECT)
        text = self._report_text()
        self.assertIn("## 3.1b BA Activities and Timing", text)
        # The whole row, not loose cells: "High" is printed by the 3.1 table above
        # (change frequency / uncertainty), so a loose assertion could not tell the
        # effort column from that. The row also pins the COLUMN ORDER.
        self.assertIn("| Iteration 1 | 4.1, 5.3 | Backlog | High | Aug 2026 |", text)
        for expected in ("iterations", "regulatory deadline 2026-12-31",
                         "agreed with the sponsor"):
            self.assertIn(expected, text, expected)

    def test_a_generated_skeleton_says_so_in_the_deliverable(self):
        from skills.planning_mcp import save_ba_plan
        suggest_ba_approach(PROJECT, "High", "High")
        plan_ba_activities(PROJECT)
        save_ba_plan(PROJECT)
        self.assertIn("Generated from the approach", self._report_text())

    def test_declared_periods_carry_no_generated_notice(self):
        from skills.planning_mcp import save_ba_plan
        suggest_ba_approach(PROJECT, "High", "High")
        plan_ba_activities(PROJECT, periods_json=json.dumps([
            {"name": "Iteration A", "tasks": ["4.1"]}]))
        save_ba_plan(PROJECT)
        self.assertNotIn("Generated from the approach", self._report_text())

    def test_a_plan_holding_only_this_section_is_not_refused_as_empty(self):
        """The same gate mismatch that once refused a plan holding only 3.5."""
        from skills.planning_mcp import save_ba_plan
        path = ba_plan_path(PROJECT)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"project_id": PROJECT, "ba_activities": {
                "timing_form": "phases", "form_source": "declared by the BA",
                "generated": False, "periods": [{"name": "Stage 1", "tasks": ["4"],
                "deliverables": [], "effort": "High", "when": ""}],
                "timing_constraints": [], "ba_notes": "", "planned_on": "2026-07-26"}}, f)
        out = save_ba_plan(PROJECT)
        self.assertNotIn("plan is empty", out)
        self.assertIn("Stage 1", self._report_text())

    def test_a_damaged_section_does_not_take_the_whole_report_down(self):
        from skills.planning_mcp import save_ba_plan
        suggest_ba_approach(PROJECT, "Low", "Low")
        plan = _read_plan()
        plan["ba_activities"] = {"periods": "oops", "timing_form": ["phases"]}
        with open(ba_plan_path(PROJECT), "w", encoding="utf-8") as f:
            json.dump(plan, f)
        out = save_ba_plan(PROJECT)
        self.assertNotIn("❌", out)
        self.assertIn("3.1 Business Analysis Approach", self._report_text())

    def test_a_damaged_section_renders_no_stub_heading_at_all(self):
        """`_sane_activities_section` always supplies `periods` / `timing_constraints`,
        so the coerced dict stays truthy even when nothing usable survived. Rendering
        on truthiness alone put an empty "3.1b" heading with "(not set)" into a
        DELIVERED document — the dashes-in-a-deliverable class."""
        from skills.planning_mcp import save_ba_plan
        suggest_ba_approach(PROJECT, "Low", "Low")
        plan = _read_plan()
        plan["ba_activities"] = {"periods": "oops", "timing_form": ["phases"]}
        with open(ba_plan_path(PROJECT), "w", encoding="utf-8") as f:
            json.dump(plan, f)
        save_ba_plan(PROJECT)
        self.assertNotIn("3.1b BA Activities and Timing", self._report_text())

    def test_an_empty_section_does_not_make_an_otherwise_empty_plan_reportable(self):
        from skills.planning_mcp import save_ba_plan
        path = ba_plan_path(PROJECT)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"project_id": PROJECT, "ba_activities": {}}, f)
        out = save_ba_plan(PROJECT)
        self.assertIn("plan is empty", out)

    def test_31_points_at_the_new_optional_step(self):
        out = suggest_ba_approach(PROJECT, "High", "High")
        self.assertIn("plan_ba_activities", out)


if __name__ == "__main__":
    unittest.main()
