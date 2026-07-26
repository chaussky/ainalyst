"""Shared reader for the 3.1 BA activities / timing plan (B3-1).

Covers the vocabulary, the normalisation both sides must share, and the two
readers chapters 4 and 5 use.

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
import shutil
import tempfile
import unittest

from skills.common import (
    EFFORT_LEVELS,
    PLATFORM_CHAPTERS,
    PLATFORM_TASKS,
    TIMING_FORMS,
    activities_section,
    approach_to_timing_form,
    ba_plan_path,
    load_ba_plan,
    normalize_task_ref,
    planned_timing_form,
    planned_work_period,
)

PROJECT = "b31_shared"


def _write_plan(project_id, section, approach=None):
    path = ba_plan_path(project_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    plan = {"project_id": project_id}
    if section is not None:
        plan["ba_activities"] = section
    if approach is not None:
        plan["ba_approach"] = approach
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f)
    return path


class TestVocabulary(unittest.TestCase):

    def test_all_25_platform_tasks_are_listed(self):
        self.assertEqual(len(PLATFORM_TASKS), 25)
        for task in ("3.1", "4.5", "5.5", "6.4", "7.6"):
            self.assertIn(task, PLATFORM_TASKS)
        # Chapter 8 is outside the release perimeter — no 8.x may appear.
        self.assertFalse([t for t in PLATFORM_TASKS if t.startswith("8")])

    def test_chapters_and_forms(self):
        self.assertEqual(PLATFORM_CHAPTERS, ("3", "4", "5", "6", "7"))
        self.assertEqual(TIMING_FORMS, ("phases", "iterations"))
        self.assertEqual(EFFORT_LEVELS, ("Low", "Medium", "High"))


class TestNormalizeTaskRef(unittest.TestCase):

    def test_canonical_forms_pass_through(self):
        self.assertEqual(normalize_task_ref("4.1"), "4.1")
        self.assertEqual(normalize_task_ref("4"), "4")

    def test_the_shapes_an_llm_writes(self):
        for raw in ("4.1.", " 4.1 ", "Task 4.1", "task 4.1"):
            self.assertEqual(normalize_task_ref(raw), "4.1", raw)
        for raw in ("Ch4", "ch 4", "Chapter 4", "chapter 4"):
            self.assertEqual(normalize_task_ref(raw), "4", raw)

    def test_unknown_and_wrong_types_return_empty(self):
        for raw in ("8.1", "9", "elicitation", "", None, 4.1, ["4.1"], {"t": "4.1"}):
            self.assertEqual(normalize_task_ref(raw), "")


class TestApproachToTimingForm(unittest.TestCase):

    def test_the_three_labels_that_resolve(self):
        self.assertEqual(approach_to_timing_form("Predictive (Waterfall)"), "phases")
        self.assertEqual(approach_to_timing_form("Adaptive (Agile)"), "iterations")
        self.assertEqual(
            approach_to_timing_form("Hybrid (Agile + compliance gates)"), "iterations")

    def test_plain_hybrid_does_not_resolve(self):
        """Guessing here would put a made-up methodology on a document that is signed."""
        self.assertEqual(approach_to_timing_form("Hybrid"), "")
        self.assertEqual(
            approach_to_timing_form("Hybrid (with strengthened governance)"), "")

    def test_wrong_types_do_not_raise(self):
        for raw in (None, 5, ["Hybrid"]):
            self.assertEqual(approach_to_timing_form(raw), "")


class TestSectionGuard(unittest.TestCase):

    def test_non_dict_plan_or_section(self):
        self.assertEqual(activities_section(None), {})
        self.assertEqual(activities_section("oops"), {})
        self.assertEqual(activities_section({"ba_activities": "oops"}), {})

    def test_periods_of_the_wrong_shape_are_dropped_not_iterated(self):
        section = activities_section({"ba_activities": {"periods": "Iteration 1"}})
        self.assertEqual(section.get("periods"), [])
        section = activities_section({"ba_activities": {"periods": ["x", {"name": "P"}]}})
        self.assertEqual(section["periods"], [{"name": "P"}])


class TestReaders(unittest.TestCase):

    def setUp(self):
        self._cwd = os.getcwd()
        self._tmp = tempfile.mkdtemp()
        os.chdir(self._tmp)

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_timing_form_is_read_from_the_section(self):
        _write_plan(PROJECT, {"timing_form": "iterations"})
        plan, note = load_ba_plan(PROJECT)
        self.assertEqual(note, "")
        self.assertEqual(planned_timing_form(plan), "iterations")

    def test_empty_or_unknown_timing_form_reads_as_nothing_planned(self):
        for stored in ("", "sprints", None, 5):
            _write_plan(PROJECT, {"timing_form": stored})
            plan, _ = load_ba_plan(PROJECT)
            self.assertIsNone(planned_timing_form(plan), stored)

    def test_exact_task_id_matches_its_period(self):
        _write_plan(PROJECT, {"periods": [
            {"name": "Iteration 1", "tasks": ["4.1"], "effort": "High"},
            {"name": "Iteration 2", "tasks": ["7.1"], "effort": "Low"},
        ]})
        plan, _ = load_ba_plan(PROJECT)
        period = planned_work_period(plan, "4.1")
        self.assertEqual(period["name"], "Iteration 1")
        self.assertEqual(period["effort"], "High")

    def test_chapter_shorthand_covers_its_task(self):
        _write_plan(PROJECT, {"periods": [{"name": "Stage 1", "tasks": ["4"]}]})
        plan, _ = load_ba_plan(PROJECT)
        period = planned_work_period(plan, "4.1")
        # Assert the match before indexing: dropping the shorthand branch should
        # read as a failed lookup, not as a TypeError on None.
        self.assertIsNotNone(period, "a chapter-wide period must cover its task")
        self.assertEqual(period["name"], "Stage 1")

    def test_a_task_does_NOT_cover_its_whole_chapter(self):
        """Asymmetry is deliberate: a chapter is all of its tasks, a task is not."""
        _write_plan(PROJECT, {"periods": [{"name": "Stage 1", "tasks": ["4.1"]}]})
        plan, _ = load_ba_plan(PROJECT)
        self.assertIsNone(planned_work_period(plan, "4"))

    def test_tasks_stored_as_a_bare_string_is_one_entry_not_one_per_character(self):
        _write_plan(PROJECT, {"periods": [{"name": "Stage 1", "tasks": "4.1"}]})
        plan, _ = load_ba_plan(PROJECT)
        self.assertEqual(planned_work_period(plan, "4.1")["name"], "Stage 1")
        # "4" is a character of "4.1"; treating the string as a sequence would match it.
        self.assertIsNone(planned_work_period(plan, "4"))

    def test_the_returned_record_always_carries_all_five_keys_as_safe_types(self):
        """4.1 INDEXES this record, so a missing key is a protocol error, not a ❌."""
        _write_plan(PROJECT, {"periods": [{"tasks": ["5.3"]}]})
        plan, _ = load_ba_plan(PROJECT)
        period = planned_work_period(plan, "5.3")
        self.assertEqual(
            sorted(period), ["deliverables", "effort", "name", "tasks", "when"])
        self.assertIsInstance(period["name"], str)
        self.assertIsInstance(period["effort"], str)
        self.assertIsInstance(period["when"], str)
        self.assertEqual(period["deliverables"], [])

    def test_no_plan_and_unreadable_plan_are_different_answers(self):
        plan, note = load_ba_plan("b31_never_planned")
        self.assertIsNone(plan)
        self.assertEqual(note, "")
        self.assertIsNone(planned_work_period(plan, "4.1"))
        path = ba_plan_path(PROJECT)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("{not json")
        plan, note = load_ba_plan(PROJECT)
        self.assertIsNone(plan)
        self.assertIn("⚠️", note)


if __name__ == "__main__":
    unittest.main()
