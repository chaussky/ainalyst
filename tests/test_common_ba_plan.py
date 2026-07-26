"""tests/test_common_ba_plan.py — shared reader for the 3.4 Information Management plan.

These helpers are what makes B3-3 a real wiring rather than a document: chapters 4 and 5
read the chapter-3 plan through them without importing the chapter-3 MCP module.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import setup_mocks, BaseMCPTest

setup_mocks()

from skills.common import (
    ATTRIBUTE_PRESETS,
    PLANNABLE_ATTRIBUTES,
    ba_plan_path,
    info_management_section,
    load_ba_plan,
    planned_abstraction_level,
    planned_attribute_set,
    planned_reuse,
)

PROJECT = "b33_reader"


def _write_plan(project_id: str, info_mgmt: dict):
    path = ba_plan_path(project_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"project": project_id, "information_management": info_mgmt}, f)
    return path


class TestBaPlanReader(BaseMCPTest):

    # --- absence and damage are different answers --------------------------

    def test_missing_plan_returns_none_without_a_note(self):
        plan, note = load_ba_plan("no_such_project_at_all")
        self.assertIsNone(plan)
        self.assertEqual(note, "")

    def test_corrupt_plan_returns_none_WITH_a_note(self):
        """A damaged chapter-3 file must not kill chapters 4 and 5 — it must
        degrade to 'no plan' and SAY SO."""
        path = ba_plan_path(PROJECT)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("{not json")
        plan, note = load_ba_plan(PROJECT)
        self.assertIsNone(plan)
        self.assertIn("⚠️", note)
        # NOT "3.4": this reader now also serves 5.5 (the 3.1 timing form) and 4.1
        # (the 3.1 work period), and naming 3.4 made the 5.5 refusal contradict its
        # own first sentence. The note must name the file, not one of its sections.
        self.assertIn("chapter-3 BA plan", note)
        self.assertNotIn("3.4", note)

    def test_path_matches_the_producer(self):
        """The consumer must compute the SAME path the chapter-3 writer uses."""
        from skills.planning_mcp import _plan_path
        self.assertEqual(ba_plan_path(PROJECT), _plan_path(PROJECT))

    # --- abstraction levels: archetype OR job title ------------------------

    def test_abstraction_level_matches_archetype(self):
        _write_plan(PROJECT, {"abstraction_levels": [
            {"audience": "Business Sponsor", "level": "Summary", "note": "value only"}]})
        plan, _ = load_ba_plan(PROJECT)
        row = planned_abstraction_level(plan, "Business Sponsor", "")
        self.assertEqual(row["level"], "Summary")

    def test_abstraction_level_matches_job_title_when_archetype_misses(self):
        """4.4 knows the archetype; the registry knows the job title. Matching on
        one key only could not succeed by construction."""
        _write_plan(PROJECT, {"abstraction_levels": [
            {"audience": "Head of Retail Lending", "level": "Detailed", "note": ""}]})
        plan, _ = load_ba_plan(PROJECT)
        row = planned_abstraction_level(plan, "Manager", "head of retail lending")
        self.assertEqual(row["level"], "Detailed")

    def test_abstraction_level_absent_returns_none(self):
        _write_plan(PROJECT, {"abstraction_levels": [
            {"audience": "Developer", "level": "Detailed"}]})
        plan, _ = load_ba_plan(PROJECT)
        self.assertIsNone(planned_abstraction_level(plan, "Tester", ""))

    # --- attribute presets: ONE resolver, no stored expansion --------------

    def test_preset_standard_resolves_to_the_skill_md_set(self):
        _write_plan(PROJECT, {"attributes": {"preset": "Standard", "additional": []}})
        plan, _ = load_ba_plan(PROJECT)
        attrs, label = planned_attribute_set(plan)
        self.assertEqual(attrs, ATTRIBUTE_PRESETS["Standard"])
        self.assertIn("Standard", label)

    def test_additional_attributes_extend_the_preset_without_duplicates(self):
        _write_plan(PROJECT, {"attributes": {
            "preset": "Minimum", "additional": ["complexity", "status"]}})
        plan, _ = load_ba_plan(PROJECT)
        attrs, _ = planned_attribute_set(plan)
        self.assertEqual(attrs.count("status"), 1)
        self.assertIn("complexity", attrs)

    def test_no_attribute_plan_returns_none(self):
        _write_plan(PROJECT, {"storage_tools": ["Jira"]})
        plan, _ = load_ba_plan(PROJECT)
        self.assertIsNone(planned_attribute_set(plan))

    def test_last_reviewed_is_in_no_preset(self):
        """It is set by the platform on every update, so a preset containing it would
        flag every requirement that simply has not been edited yet."""
        for preset in ATTRIBUTE_PRESETS.values():
            self.assertNotIn("last_reviewed", preset)
        self.assertIn("last_reviewed", PLANNABLE_ATTRIBUTES)

    # --- reuse -------------------------------------------------------------

    def test_planned_reuse_returns_the_three_fields(self):
        _write_plan(PROJECT, {"reuse": {"target_scope": "program",
                                        "repository": "REQ-LIB space",
                                        "categories": ["regulatory"]}})
        plan, _ = load_ba_plan(PROJECT)
        reuse = planned_reuse(plan)
        self.assertEqual(reuse["target_scope"], "program")
        self.assertEqual(reuse["repository"], "REQ-LIB space")

    def test_planned_reuse_absent_returns_none(self):
        _write_plan(PROJECT, {"storage_tools": ["Jira"]})
        plan, _ = load_ba_plan(PROJECT)
        self.assertIsNone(planned_reuse(plan))

    # --- shape guards: the file is written by an LLM-driven tool ------------

    def test_non_dict_rows_are_skipped_not_crashed(self):
        _write_plan(PROJECT, {"abstraction_levels": ["Business Sponsor"],
                              "attributes": {"preset": "Minimum", "additional": [7]}})
        plan, _ = load_ba_plan(PROJECT)
        self.assertIsNone(planned_abstraction_level(plan, "Business Sponsor", ""))
        attrs, _ = planned_attribute_set(plan)
        self.assertEqual(attrs, ATTRIBUTE_PRESETS["Minimum"])

    def test_string_categories_are_not_iterated_as_characters(self):
        """A string where a list was meant is an ORDINARY LLM mistake. Iterating it
        yielded ['r','e','g','u','l','a','t','o','r','y'] — invented data a consumer
        would then render as real planned categories. Silent degradation is tolerable
        only when the tool says LESS, never when it makes something up."""
        _write_plan(PROJECT, {"reuse": {"target_scope": "program",
                                        "repository": "REQ-LIB",
                                        "categories": "regulatory"}})
        plan, _ = load_ba_plan(PROJECT)
        self.assertEqual(planned_reuse(plan)["categories"], [])

    def test_non_list_categories_do_not_crash(self):
        _write_plan(PROJECT, {"reuse": {"target_scope": "program", "categories": 1}})
        plan, _ = load_ba_plan(PROJECT)
        self.assertEqual(planned_reuse(plan)["categories"], [])

    def test_non_string_preset_does_not_crash(self):
        """`ATTRIBUTE_PRESETS.get(preset)` with a list raises 'unhashable type'."""
        _write_plan(PROJECT, {"attributes": {"preset": ["Standard"], "additional": []}})
        plan, _ = load_ba_plan(PROJECT)
        self.assertIsNone(planned_attribute_set(plan))

    def test_non_list_additional_does_not_crash(self):
        _write_plan(PROJECT, {"attributes": {"preset": "Minimum", "additional": "owner"}})
        plan, _ = load_ba_plan(PROJECT)
        attrs, _ = planned_attribute_set(plan)
        self.assertEqual(attrs, ATTRIBUTE_PRESETS["Minimum"])

    def test_non_dict_information_management_section(self):
        path = ba_plan_path(PROJECT)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"project": PROJECT, "information_management": ["oops"]}, f)
        plan, _ = load_ba_plan(PROJECT)
        self.assertEqual(info_management_section(plan), {})

    def test_helpers_accept_none_plan(self):
        self.assertEqual(info_management_section(None), {})
        self.assertIsNone(planned_abstraction_level(None, "Manager"))
        self.assertIsNone(planned_reuse(None))
        self.assertIsNone(planned_attribute_set(None))


if __name__ == "__main__":
    unittest.main()
