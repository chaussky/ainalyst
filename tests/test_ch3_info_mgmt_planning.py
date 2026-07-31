"""tests/test_ch3_info_mgmt_planning.py — BABOK 3.4 elements .2 / .4 / .6 (B3-3)."""

import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import setup_mocks, BaseMCPTest

setup_mocks()

from skills.planning_mcp import (
    plan_ba_governance, plan_information_management, save_ba_plan, _plan_path)

PROJECT = "b33_writer"


def _section(project_id=PROJECT) -> dict:
    with open(_plan_path(project_id), encoding="utf-8") as f:
        return json.load(f)["information_management"]


class TestAbstractionLevels(BaseMCPTest):

    def test_levels_are_stored(self):
        result = plan_information_management(
            PROJECT, '["Confluence"]',
            abstraction_levels_json=json.dumps([
                {"audience": "Business Sponsor", "level": "Summary", "note": "value only"}]))
        self.assertIn("✅", result)
        rows = _section()["abstraction_levels"]
        self.assertEqual(rows[0]["level"], "Summary")

    def test_unknown_level_is_refused_with_the_allowed_values(self):
        result = plan_information_management(
            PROJECT, '["Confluence"]',
            abstraction_levels_json='[{"audience": "Manager", "level": "Verbose"}]')
        self.assertIn("❌", result)
        self.assertIn("Summary", result)

    def test_row_without_audience_is_refused_by_index(self):
        """Two rows, the SECOND one broken: with a single row the assertion could not
        tell real index tracking from a hardcoded "row 1"."""
        result = plan_information_management(
            PROJECT, '["Confluence"]',
            abstraction_levels_json=json.dumps([
                {"audience": "Manager", "level": "Summary"},
                {"level": "Summary"}]))
        self.assertIn("❌", result)
        self.assertIn("row 2", result)

    def test_archetype_recognition_is_case_insensitive(self):
        """The consumer matches through `reg_norm`, so "business sponsor" DOES resolve
        as the archetype. Warning the BA that it "will match only by job title" is a
        confident false claim."""
        result = plan_information_management(
            PROJECT, '["Confluence"]',
            abstraction_levels_json='[{"audience": "business sponsor", "level": "Summary"}]')
        self.assertIn("✅", result)
        self.assertNotIn("job title", result)

    def test_duplicate_warning_is_the_only_warning_for_two_archetype_rows(self):
        """Was: the lowercase second row ALSO tripped the "not an archetype" warning,
        so asserting merely that some ⚠️ appeared could not tell which fired — the
        test would have passed with duplicate detection deleted."""
        result = plan_information_management(
            PROJECT, '["Confluence"]',
            abstraction_levels_json=json.dumps([
                {"audience": "Manager", "level": "Summary"},
                {"audience": "manager", "level": "Detailed"}]))
        self.assertIn("appears twice", result)
        self.assertNotIn("job title", result)

    def test_job_title_audience_is_accepted_with_a_warning(self):
        """A row may name a job title instead of one of the 4.4 archetypes — that is
        legal (the consumer matches on either), but the BA should know it will only
        match by job title."""
        result = plan_information_management(
            PROJECT, '["Confluence"]',
            abstraction_levels_json='[{"audience": "Head of Retail Lending", "level": "Detailed"}]')
        self.assertIn("✅", result)
        self.assertIn("⚠️", result)

    def test_duplicate_audience_keeps_the_last_and_warns(self):
        result = plan_information_management(
            PROJECT, '["Confluence"]',
            abstraction_levels_json=json.dumps([
                {"audience": "Manager", "level": "Summary"},
                {"audience": "manager", "level": "Detailed"}]))
        self.assertIn("⚠️", result)
        rows = _section()["abstraction_levels"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["level"], "Detailed")

    def test_shape_that_is_not_a_list_of_objects_is_refused(self):
        result = plan_information_management(
            PROJECT, '["Confluence"]', abstraction_levels_json='["Manager"]')
        self.assertIn("❌", result)
        self.assertIn("abstraction_levels_json", result)


class TestReusePlanning(BaseMCPTest):

    def test_reuse_fields_are_stored(self):
        plan_information_management(
            PROJECT, '["Confluence"]',
            reuse_target_scope="program",
            reuse_repository="Confluence space REQ-LIB",
            reuse_categories_json='["regulatory", "business rules"]')
        reuse = _section()["reuse"]
        self.assertEqual(reuse["target_scope"], "program")
        self.assertEqual(reuse["repository"], "Confluence space REQ-LIB")
        self.assertIn("regulatory", reuse["categories"])

    def test_unlisted_category_is_accepted_with_a_warning(self):
        """BABOK's list is open — an unlisted category must not be refused."""
        result = plan_information_management(
            PROJECT, '["Confluence"]', reuse_categories_json='["screen layouts"]')
        self.assertIn("✅", result)
        self.assertIn("⚠️", result)
        self.assertIn("screen layouts", _section()["reuse"]["categories"])


class TestAttributeVocabulary(BaseMCPTest):

    def test_preset_is_stored_and_echoed_expanded(self):
        result = plan_information_management(
            PROJECT, '["Confluence"]', attributes_preset="Standard")
        self.assertEqual(_section()["attributes"]["preset"], "Standard")
        self.assertIn("owner", result)

    def test_expansion_is_not_stored(self):
        """Only preset + additional are stored; one resolver expands them.

        Asserted on the stored KEYS, not on the absence of a name no code writes —
        that version of the test could not have failed.
        """
        plan_information_management(PROJECT, '["Confluence"]', attributes_preset="Full")
        self.assertEqual(set(_section()["attributes"]), {"preset", "additional"})
        self.assertEqual(_section()["attributes"]["additional"], [])

    def test_attribute_outside_the_platform_model_is_refused_by_name(self):
        result = plan_information_management(
            PROJECT, '["Confluence"]',
            attributes_preset="Minimum", additional_attributes_json='["urgency"]')
        self.assertIn("❌", result)
        self.assertIn("urgency", result)
        self.assertIn("owner", result)   # the allowed list is shown


class TestMergeOnRerun(BaseMCPTest):

    def test_rerun_keeps_the_new_rich_fields(self):
        plan_information_management(
            PROJECT, '["Confluence"]', attributes_preset="Standard",
            abstraction_levels_json='[{"audience": "Manager", "level": "Summary"}]')
        plan_information_management(PROJECT, '["Confluence", "Jira"]')
        section = _section()
        self.assertEqual(section["attributes"]["preset"], "Standard")
        self.assertEqual(len(section["abstraction_levels"]), 1)

    def test_rerun_keeps_the_PRE_EXISTING_fields_too(self):
        """Was: a re-run to add one storage tool silently reset traceability_level to
        Medium and artifact_types to [] — and the delivered BA Plan then showed
        values the BA never chose."""
        plan_information_management(
            PROJECT, '["Confluence"]', traceability_level="High",
            artifact_types_json='["BRD"]', access_rules="BA edits, PO reads")
        plan_information_management(PROJECT, '["Confluence", "Jira"]')
        section = _section()
        self.assertEqual(section["traceability_level"], "High")
        self.assertEqual(section["artifact_types"], ["BRD"])
        self.assertEqual(section["access_rules"], "BA edits, PO reads")

    def test_rerun_reports_what_it_kept(self):
        plan_information_management(PROJECT, '["Confluence"]', attributes_preset="Full")
        result = plan_information_management(PROJECT, '["Confluence", "Jira"]')
        self.assertIn("kept", result.lower())

    def test_explicit_clearing_works(self):
        plan_information_management(
            PROJECT, '["Confluence"]', artifact_types_json='["BRD"]',
            attributes_preset="Full", reuse_repository="REQ-LIB")
        plan_information_management(
            PROJECT, artifact_types_json="[]", attributes_preset="None",
            reuse_repository="-")
        section = _section()
        self.assertEqual(section["artifact_types"], [])
        self.assertEqual(section["attributes"]["preset"], "")
        self.assertEqual(section["reuse"]["repository"], "")

    def test_storage_tools_may_be_omitted_on_a_rerun(self):
        plan_information_management(PROJECT, '["Confluence"]')
        result = plan_information_management(PROJECT, traceability_level="High")
        self.assertIn("✅", result)
        self.assertEqual(_section()["storage_tools"], ["Confluence"])

    def test_first_call_without_storage_tools_is_refused(self):
        result = plan_information_management("b33_fresh", traceability_level="High")
        self.assertIn("❌", result)
        self.assertFalse(os.path.exists(_plan_path("b33_fresh")))

    def test_kept_line_names_every_field_it_actually_kept(self):
        """A status line the BA is meant to trust instead of opening the JSON must not
        under-report: access_rules, ba_notes and the additional attributes were all
        silently preserved without ever being named."""
        plan_information_management(
            PROJECT, '["Confluence"]', access_rules="BA edits, PO reads",
            ba_notes="agreed at the kickoff",
            attributes_preset="Minimum", additional_attributes_json='["complexity"]')
        result = plan_information_management(PROJECT, '["Confluence", "Jira"]')
        self.assertIn("access rules", result)
        self.assertIn("BA notes", result)
        self.assertIn("additional attributes", result)

    def test_clearing_access_rules_restores_the_documented_default(self):
        """`-` clears every other text field to empty, but this one has a standing
        default, and an empty Access line in a delivered document is worse than the
        default. Documented rather than left as an inconsistency."""
        plan_information_management(PROJECT, '["Confluence"]', access_rules="PO edits")
        plan_information_management(PROJECT, access_rules="-")
        self.assertEqual(_section()["access_rules"], "BA edits, others read")

    def test_a_section_of_the_wrong_shape_does_not_kill_the_tool(self):
        """Introduced by merge semantics: the writer never read the previous section
        before, and the reader's guard did not extend to it. A file that is valid JSON
        with a list where the section should be raised AttributeError — and chapter 3
        is the only place that could overwrite the bad section, so the BA had no way
        out of it in the product."""
        path = _plan_path("b33_wrongshape")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"project": "b33_wrongshape", "information_management": ["oops"]}, f)
        result = plan_information_management("b33_wrongshape", '["Confluence"]')
        self.assertIn("✅", result)
        self.assertEqual(_section("b33_wrongshape")["storage_tools"], ["Confluence"])

    def test_wrong_shape_NESTED_values_do_not_kill_the_tool_either(self):
        """The first guard stopped at the section itself. One level down every merge
        branch still called .get()/[] on whatever was stored, so the dead end survived:
        3.4 is the only tool that can overwrite a damaged section, and it was the tool
        that died. `storage_tools` as a bare string was worse than a crash — it was
        ACCEPTED and echoed one entry per character."""
        broken_sections = (
            {"storage_tools": ["Jira"], "reuse": "oops"},
            {"storage_tools": ["Jira"], "reuse": ["oops"]},
            {"storage_tools": ["Jira"], "attributes": "oops"},
            {"storage_tools": ["Jira"], "abstraction_levels": ["oops"]},
            {"storage_tools": ["Jira"], "traceability_level": ["High"]},
            {"storage_tools": "Confluence"},
        )
        for i, section in enumerate(broken_sections):
            pid = f"b33_nested{i}"
            with self.subTest(section=section):
                path = _plan_path(pid)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"project": pid, "information_management": section}, f)
                result = plan_information_management(pid, '["Confluence"]')
                self.assertIn("✅", result)
                self.assertNotIn("C, o, n", result)
                self.assertEqual(_section(pid)["storage_tools"], ["Confluence"])
                with patch("skills.planning_mcp.save_artifact") as mock_sa:
                    mock_sa.return_value = "ok"
                    self.assertNotIn("❌", save_ba_plan(pid))

    def test_report_survives_a_section_of_the_wrong_shape(self):
        """Pre-existing sibling of the above, in the renderer."""
        path = _plan_path("b33_wrongshape2")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"project": "b33_wrongshape2", "ba_approach": {"techniques": []},
                       "information_management": "oops"}, f)
        with patch("skills.planning_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "\n\n✅ Artifact saved: `x.md`"
            result = save_ba_plan("b33_wrongshape2")
        self.assertNotIn("Traceback", result)

    def test_storage_tools_cannot_be_cleared(self):
        """A 3.4 plan with no place to store anything is not an empty field — it is
        an unfinished task."""
        plan_information_management(PROJECT, '["Confluence"]')
        result = plan_information_management(PROJECT, storage_tools_json="[]")
        self.assertIn("❌", result)
        self.assertEqual(_section()["storage_tools"], ["Confluence"])


def _report_text(project_id=PROJECT) -> str:
    """The BA Plan markdown, captured from the writer.

    save_artifact is mocked suite-wide (ADR-068), so the report never reaches disk in
    unit tests — it is read from the call instead. Task 8 exercises the real writer.
    """
    with patch("skills.planning_mcp.save_artifact") as mock_sa:
        mock_sa.return_value = "\n\n✅ Artifact saved: `x.md`"
        save_ba_plan(project_id)
        return mock_sa.call_args[0][0] if mock_sa.call_args else ""


class TestReportRendersThePlannedElements(BaseMCPTest):

    def test_report_shows_all_three_new_blocks(self):
        plan_information_management(
            PROJECT, '["Confluence"]',
            abstraction_levels_json=json.dumps([
                {"audience": "Manager", "level": "Summary", "note": "traffic lights"}]),
            reuse_target_scope="program", reuse_repository="REQ-LIB",
            reuse_categories_json='["regulatory"]',
            attributes_preset="Standard")
        text = _report_text()
        self.assertIn("Manager", text)
        self.assertIn("Summary", text)
        self.assertIn("traffic lights", text)
        self.assertIn("REQ-LIB", text)
        self.assertIn("regulatory", text)
        self.assertIn("Standard", text)
        self.assertIn("owner", text)          # the preset is expanded for the reader

    def test_report_omits_blocks_that_were_never_planned(self):
        """No empty tables in a delivered document."""
        plan_information_management("b33_bare", '["Jira"]')
        text = _report_text("b33_bare")
        self.assertIn("3.4 Information Management", text)
        self.assertNotIn("Level of detail per audience", text)
        self.assertNotIn("Requirements reuse", text)
        self.assertNotIn("Requirements attributes", text)

    def test_module_header_no_longer_claims_the_plan_has_no_readers(self):
        """The header said "read back by this module only". After B3-3 that is a lie
        in the opposite direction — the class this programme keeps fixing."""
        import skills.planning_mcp as pm
        self.assertNotIn("read back by this module only", pm.__doc__)
        self.assertIn("4.4", pm.__doc__)
        self.assertIn("5.2", pm.__doc__)


class TestVocabulariesStayInSync(BaseMCPTest):
    """Chapter 3 cannot import chapter 4 (different phases), so it copies the audience
    vocabulary. A copy that drifts is a join that stops matching — silently. Same for
    the Literal parameters, which cannot be built from a runtime tuple."""

    def test_audience_archetypes_match_the_4_4_literal(self):
        import typing
        from skills.planning_mcp import _AUDIENCE_ARCHETYPES
        from skills.elicitation_communicate_mcp import prepare_communication_package
        hints = typing.get_type_hints(prepare_communication_package)
        self.assertEqual(set(_AUDIENCE_ARCHETYPES),
                         set(typing.get_args(hints["audience_role"])))

    def test_literal_parameters_match_the_shared_constants(self):
        import typing
        from skills.common import ATTRIBUTE_PRESETS, REUSE_SCOPES
        hints = typing.get_type_hints(plan_information_management)
        scope_values = set(typing.get_args(hints["reuse_target_scope"])) - {"", "None"}
        preset_values = set(typing.get_args(hints["attributes_preset"])) - {"", "None"}
        self.assertEqual(scope_values, set(REUSE_SCOPES))
        self.assertEqual(preset_values, set(ATTRIBUTE_PRESETS))


class TestTraceabilitySeededFromCriticality(BaseMCPTest):
    """Seam D — BABOK Figure 3.3.1's 3.3 -> 3.4 arrow, made real (B3-2).

    `plan_information_management` RETURNS a status message (probed). The traceability
    line reads `  Traceability:      <level> — <description>`, so every assertion below
    names that whole prefix: a bare `assertIn("High", ...)` would be satisfied by any
    other occurrence of the word, and `_TRACEABILITY_LEVELS["High"]` does not contain
    it at all.
    """

    SEEDED = "seeded from the 3.3 criticality"

    def test_the_criticality_seeds_the_level_when_none_is_stated(self):
        plan_ba_governance("seed1", "High", '["CFO"]')
        result = plan_information_management("seed1", '["Confluence"]')
        self.assertIn("Traceability:      High", result)
        self.assertIn(f"{self.SEEDED}: High", result)
        self.assertEqual(_section("seed1")["traceability_level"], "High")

    def test_a_medium_criticality_seeds_medium_and_still_shows_the_source(self):
        """Medium is also the hardcoded default, so only the source label can tell the
        BA whether the value came from the 3.3 plan or from nowhere."""
        plan_ba_governance("seed_m", "Medium", '["PO"]')
        result = plan_information_management("seed_m", '["Confluence"]')
        self.assertIn("Traceability:      Medium", result)
        self.assertIn(f"{self.SEEDED}: Medium", result)

    def test_without_a_governance_plan_the_default_is_unchanged(self):
        result = plan_information_management("seed2", '["Confluence"]')
        self.assertIn("Traceability:      Medium", result)
        self.assertNotIn(self.SEEDED, result)

    def test_a_stated_level_is_never_overridden(self):
        plan_ba_governance("seed3", "High", '["CFO"]')
        plan_information_management("seed3", '["Confluence"]', traceability_level="Low")
        result = plan_information_management("seed3", access_rules="BA edits")
        self.assertIn("Traceability:      Low", result)
        self.assertNotIn("High", result)
        self.assertNotIn(self.SEEDED, result)

    def test_the_level_stated_in_the_same_call_wins_over_the_criticality(self):
        plan_ba_governance("seed3b", "High", '["CFO"]')
        result = plan_information_management("seed3b", '["Confluence"]',
                                             traceability_level="Low")
        self.assertIn("Traceability:      Low", result)
        self.assertNotIn(self.SEEDED, result)

    def test_the_seed_is_insert_only_across_a_criticality_change(self):
        """A2's `insert_defaults` lesson: a re-run must never roll a stored value back.
        The criticality moves Low -> High AFTER the level was seeded Low; the seeded
        value is now a stored decision like any other and stays."""
        plan_ba_governance("seed4", "Low", '["Lead BA"]')
        plan_information_management("seed4", '["Confluence"]')          # seeded Low
        plan_ba_governance("seed4", "High")
        result = plan_information_management("seed4", access_rules="BA edits")
        self.assertIn("Traceability:      Low", result)
        self.assertIn("traceability level", result)                     # the Kept line
        self.assertNotIn(self.SEEDED, result)

    def test_a_governance_section_of_the_wrong_type_does_not_raise(self):
        """Chapter 3 loads in EVERY phase, so an AttributeError here is a protocol
        error in every session."""
        for i, bad in enumerate((None, "oops", ["High"], 7)):
            pid = f"seed_bad{i}"
            with self.subTest(governance=bad):
                path = _plan_path(pid)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"project_id": pid, "governance": bad}, f)
                result = plan_information_management(pid, '["Confluence"]')
                self.assertIn("✅", result)
                self.assertIn("Traceability:      Medium", result)
                self.assertNotIn(self.SEEDED, result)

    def test_a_criticality_outside_the_vocabulary_does_not_seed(self):
        """Guarded for VALUE, not only for type: a hand-edited "Catastrophic" must not
        reach `_TRACEABILITY_LEVELS.get()` and silently become the Medium wording under
        its own name."""
        path = _plan_path("seed_junk")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"project_id": "seed_junk",
                       "governance": {"project_criticality": "Catastrophic"}}, f)
        result = plan_information_management("seed_junk", '["Confluence"]')
        self.assertIn("Traceability:      Medium", result)
        self.assertNotIn("Catastrophic", result)
        self.assertNotIn(self.SEEDED, result)

    def test_a_hand_edited_stored_level_falls_back_to_the_seed(self):
        """A stored level is guarded for value too. `Bogus` used to be echoed as the
        level while the DESCRIPTION silently fell back to Medium's — a delivered plan
        naming a traceability level the platform does not have."""
        plan_ba_governance("seed5", "High", '["CFO"]')
        plan_information_management("seed5", '["Confluence"]', traceability_level="Low")
        path = _plan_path("seed5")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["information_management"]["traceability_level"] = "Bogus"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        result = plan_information_management("seed5", access_rules="BA edits")
        self.assertIn("Traceability:      High", result)
        self.assertNotIn("Bogus", result)


if __name__ == "__main__":
    unittest.main()
