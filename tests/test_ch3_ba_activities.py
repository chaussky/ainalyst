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
        self.assertIn("выведено из подхода Adaptive (Agile)", section["form_source"])
        # NOT assertIn("iterations", out): the "form not set" warning also names
        # `timing_form="iterations"`, so that assertion would pass with the
        # derivation entirely broken.
        self.assertIn("выведено из подхода Adaptive (Agile)", out)

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
        self.assertIn("заявлено БА", section["form_source"])
        # "Adaptive (Agile)" alone would also appear in `form_source` if the
        # declaration had been ignored — assert the conflict sentence itself.
        self.assertIn("Сохранено то, что вы заявили", out)
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
        self.assertIn("енерировано", out.lower())

    def test_phases_skeleton_uses_stage_not_the_word_phase(self):
        """"Phase" is taken: `python phase.py` switches the platform's session phase."""
        suggest_ba_approach(PROJECT, "Low", "Low")
        plan_ba_activities(PROJECT)
        names = [p["name"] for p in _read_plan()["ba_activities"]["periods"]]
        self.assertTrue(all(n.startswith("Этап") for n in names), names)
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
        self.assertIn("вне шкалы Low/Medium/High", out)
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
        out = plan_ba_activities(PROJECT)   # skeleton covers chapter 4 and has a form
        self.assertIn("5.5", out)
        self.assertIn("4.1", out)

    def test_the_footer_uses_the_consumers_own_matching_rule(self):
        """4.1 asks for the task `4.1`, so a period tagged only 4.2/4.3 answers
        nothing — the footer must not promise output the consumer will not produce.
        Two sides of one join have to normalise and match identically."""
        suggest_ba_approach(PROJECT, "High", "High")
        out = plan_ba_activities(PROJECT, periods_json=json.dumps([
            {"name": "Wave 1", "tasks": ["4.2", "4.3"]}]))
        self.assertNotIn("names the period that covers elicitation", out)

    def test_the_footer_does_not_promise_a_reader_that_will_stay_silent(self):
        """Printed unconditionally, the block contradicted the warning three lines
        above it: no timing form means 5.5 will NOT take the methodology, and a plan
        covering no chapter-4 task means 4.1 prints nothing."""
        suggest_ba_approach(PROJECT, "Medium", "Medium")       # -> Hybrid, no form
        out = plan_ba_activities(PROJECT, periods_json=json.dumps([
            {"name": "Wave 1", "tasks": ["7.1"]}]))
        self.assertNotIn("takes the methodology from the timing form", out)
        self.assertNotIn("names the period that covers elicitation", out)


class TestRerun(_TempCwd):

    def test_declared_periods_replace_the_previous_ones(self):
        suggest_ba_approach(PROJECT, "High", "High")
        plan_ba_activities(PROJECT, periods_json=json.dumps([
            {"name": "It 1", "tasks": ["4.1"]}]))
        plan_ba_activities(PROJECT, periods_json=json.dumps([
            {"name": "It 2", "tasks": ["5.3"]}]))
        names = [p["name"] for p in _read_plan()["ba_activities"]["periods"]]
        self.assertEqual(names, ["It 2"])

    def test_a_bare_rerun_keeps_everything_the_ba_typed(self):
        """Every parameter here is optional, so "empty" must mean KEEP, not WIPE —
        the tool's own message invites a re-run ("edit and re-run to make them
        yours"), and its sibling plan_information_management already merges. A wipe
        would also break the project rule that data is never deleted."""
        suggest_ba_approach(PROJECT, "High", "High")
        plan_ba_activities(
            PROJECT,
            periods_json=json.dumps([{"name": "Sprint 1", "tasks": ["4.1"],
                                      "effort": "High"}]),
            timing_constraints_json=json.dumps(["regulatory deadline 2026-12-31"]),
            ba_notes="agreed with the sponsor")
        out = plan_ba_activities(PROJECT)
        section = _read_plan()["ba_activities"]
        self.assertEqual([p["name"] for p in section["periods"]], ["Sprint 1"])
        self.assertEqual(section["timing_constraints"], ["regulatory deadline 2026-12-31"])
        self.assertEqual(section["ba_notes"], "agreed with the sponsor")
        # The status line must name EVERYTHING that survived, or it is worse than
        # absent — it exists to spare the BA from opening the JSON.
        self.assertIn("Сохранено из прежнего плана", out)
        for kept in ("форму привязки ко времени (iterations)", "периодов: 1",
                     "ограничений по срокам: 1", "заметки БА"):
            self.assertIn(kept, out, kept)

    def test_a_bare_rerun_does_not_revert_a_declared_form_to_the_derived_one(self):
        """That value is printed on the package that goes out for signature."""
        suggest_ba_approach(PROJECT, "High", "High")          # -> Adaptive (Agile)
        plan_ba_activities(PROJECT, timing_form="phases")
        plan_ba_activities(PROJECT)
        section = _read_plan()["ba_activities"]
        self.assertEqual(section["timing_form"], "phases")
        self.assertIn("заявлено БА", section["form_source"])

    def test_a_bare_rerun_does_not_regenerate_over_a_stored_skeleton(self):
        suggest_ba_approach(PROJECT, "High", "High")
        plan_ba_activities(PROJECT)                            # skeleton
        plan_ba_activities(PROJECT, periods_json=json.dumps([
            {"name": "Mine", "tasks": ["4.1"]}]))              # the BA takes it over
        plan_ba_activities(PROJECT)                            # a bare re-run
        section = _read_plan()["ba_activities"]
        self.assertEqual([p["name"] for p in section["periods"]], ["Mine"])
        self.assertFalse(section["generated"])

    def test_a_kept_skeleton_is_regenerated_when_the_form_changes(self):
        """Keeping periods protects the BA's work — but a skeleton is 100% machine
        output built FOR a form. Carrying it across a form change delivered a `phases`
        plan tabulating `Iteration 1/2`, under a "Kept from the previous plan" line
        claiming preserved BA work."""
        suggest_ba_approach(PROJECT, "High", "High")           # -> Adaptive
        plan_ba_activities(PROJECT)                            # iterations skeleton
        out = plan_ba_activities(PROJECT, timing_form="phases")
        section = _read_plan()["ba_activities"]
        self.assertEqual(section["timing_form"], "phases")
        self.assertTrue(all(p["name"].startswith("Этап") for p in section["periods"]),
                        [p["name"] for p in section["periods"]])
        self.assertNotIn("period(s)", out.split("Сохранено из прежнего плана")[-1]
                         if "Сохранено из прежнего плана" in out else "")
        self.assertIn("перегенерировано", out.lower())

    def test_periods_the_ba_typed_survive_a_form_change(self):
        suggest_ba_approach(PROJECT, "High", "High")
        plan_ba_activities(PROJECT, periods_json=json.dumps([
            {"name": "Mine", "tasks": ["4.1"]}]))
        plan_ba_activities(PROJECT, timing_form="phases")
        section = _read_plan()["ba_activities"]
        self.assertEqual([p["name"] for p in section["periods"]], ["Mine"])

    def test_an_explicit_empty_list_clears_the_way_the_sibling_tool_documents(self):
        """3.4 teaches `"[]"` to clear a list and `"-"` to clear a text field. With
        `"[]"` as the DEFAULT here, "not passed" and "clear it" were the same string,
        so the constraints could never be cleared by any input at all."""
        suggest_ba_approach(PROJECT, "High", "High")
        plan_ba_activities(PROJECT, timing_constraints_json=json.dumps(["freeze"]))
        plan_ba_activities(PROJECT)                            # not passed -> keeps
        self.assertEqual(_read_plan()["ba_activities"]["timing_constraints"], ["freeze"])
        plan_ba_activities(PROJECT, timing_constraints_json="[]")   # explicit clear
        self.assertEqual(_read_plan()["ba_activities"]["timing_constraints"], [])

    def test_an_explicit_empty_period_list_returns_to_the_skeleton(self):
        suggest_ba_approach(PROJECT, "High", "High")
        plan_ba_activities(PROJECT, periods_json=json.dumps([
            {"name": "Mine", "tasks": ["4.1"]}]))
        plan_ba_activities(PROJECT, periods_json="[]")
        section = _read_plan()["ba_activities"]
        self.assertTrue(section["generated"])
        self.assertTrue(all(p["name"].startswith("Iteration") for p in section["periods"]))

    def test_a_stored_form_outside_the_vocabulary_is_dropped_not_carried_forward(self):
        """The merge is the first path that takes a form from stored JSON instead of
        the validated Literal. `sprints` survived, silenced the "form is not set"
        warning, and made the footer promise a reader that then refuses."""
        suggest_ba_approach(PROJECT, "High", "High")
        plan_ba_activities(PROJECT)
        plan = _read_plan()
        plan["ba_activities"]["timing_form"] = "sprints"
        with open(ba_plan_path(PROJECT), "w", encoding="utf-8") as f:
            json.dump(plan, f)
        out = plan_ba_activities(PROJECT)
        self.assertEqual(_read_plan()["ba_activities"]["timing_form"], "iterations")
        self.assertNotIn("sprints", out)

    def test_a_dash_clears_the_notes_the_way_the_rest_of_the_module_does(self):
        suggest_ba_approach(PROJECT, "High", "High")
        plan_ba_activities(PROJECT, ba_notes="agreed with the sponsor")
        plan_ba_activities(PROJECT, ba_notes="-")
        self.assertEqual(_read_plan()["ba_activities"]["ba_notes"], "")

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
        self.assertIn("## 3.1b Работы БА и их сроки", text)
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
        self.assertIn("Сгенерировано из подхода", self._report_text())

    def test_declared_periods_carry_no_generated_notice(self):
        from skills.planning_mcp import save_ba_plan
        suggest_ba_approach(PROJECT, "High", "High")
        plan_ba_activities(PROJECT, periods_json=json.dumps([
            {"name": "Iteration A", "tasks": ["4.1"]}]))
        save_ba_plan(PROJECT)
        self.assertNotIn("Сгенерировано из подхода", self._report_text())

    def test_a_plan_holding_only_this_section_is_not_refused_as_empty(self):
        """The same gate mismatch that once refused a plan holding only 3.5."""
        from skills.planning_mcp import save_ba_plan
        path = ba_plan_path(PROJECT)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"project_id": PROJECT, "ba_activities": {
                "timing_form": "phases", "form_source": "заявлено БА",
                "generated": False, "periods": [{"name": "Stage 1", "tasks": ["4"],
                "deliverables": [], "effort": "High", "when": ""}],
                "timing_constraints": [], "ba_notes": "", "planned_on": "2026-07-26"}}, f)
        out = save_ba_plan(PROJECT)
        self.assertNotIn("план пуст", out)
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
        self.assertIn("3.1 Подход к бизнес-анализу", self._report_text())

    def test_a_non_dict_ba_approach_does_not_crash_the_report(self):
        """The drift note reads `approach` from INSIDE the `if activities:` branch, so
        the container guard that covers every other approach.get() does not reach it.
        planning_mcp loads in every phase — an AttributeError here is a protocol error
        in every session, not a ❌ line."""
        from skills.planning_mcp import save_ba_plan
        path = ba_plan_path(PROJECT)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        for broken in (None, "", []):
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"project_id": PROJECT, "ba_approach": broken,
                           "ba_activities": {"timing_form": "phases",
                                             "form_source": "выведено из подхода Adaptive (Agile)",
                                             "periods": [{"name": "Stage 1",
                                                          "tasks": ["4"]}]}}, f)
            out = save_ba_plan(PROJECT)
            self.assertNotIn("❌", out, repr(broken))
            self.assertIn("Stage 1", self._report_text())

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
        self.assertIn("план пуст", out)

    def test_a_derived_form_left_behind_by_a_31_rerun_is_flagged(self):
        """Found by reading the rendered report, not by an assertion: the stored
        source stays true forever, so after a 3.1 re-run two ADJACENT sections of one
        delivered document disagree — 3.1 recommends Hybrid while 3.1b says the form
        was derived from Adaptive (Agile), and nothing tells the BA to re-run."""
        from skills.planning_mcp import save_ba_plan
        suggest_ba_approach(PROJECT, "High", "High")          # -> Adaptive (Agile)
        plan_ba_activities(PROJECT)
        suggest_ba_approach(PROJECT, "Low", "Low")            # -> Predictive (Waterfall)
        save_ba_plan(PROJECT)
        text = self._report_text()
        self.assertIn("Adaptive (Agile)", text)               # where it came from
        self.assertIn("больше не", text)
        # The advice must stay executable. A bare re-run KEEPS the recorded form (that
        # is the anti-wipe rule), so pointing at a bare `plan_ba_activities` would be
        # an orphaned signpost — the class a previous feature shipped for one commit.
        self.assertIn("с явным `timing_form`", text)

    def test_a_declared_form_is_not_flagged_when_the_approach_changes(self):
        """The BA said it; the approach is not evidence about it either way."""
        from skills.planning_mcp import save_ba_plan
        suggest_ba_approach(PROJECT, "High", "High")
        plan_ba_activities(PROJECT, timing_form="phases")
        suggest_ba_approach(PROJECT, "Low", "Low")
        save_ba_plan(PROJECT)
        self.assertNotIn("больше не", self._report_text())

    def test_an_unchanged_approach_is_not_flagged(self):
        from skills.planning_mcp import save_ba_plan
        suggest_ba_approach(PROJECT, "High", "High")
        plan_ba_activities(PROJECT)
        save_ba_plan(PROJECT)
        self.assertNotIn("больше не", self._report_text())

    def test_31_points_at_the_new_optional_step(self):
        out = suggest_ba_approach(PROJECT, "High", "High")
        self.assertIn("plan_ba_activities", out)


if __name__ == "__main__":
    unittest.main()
