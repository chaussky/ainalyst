"""tests/test_ch3_governance_planning.py — BABOK 3.3 merge + elements .1 / .4 (B3-2).

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import setup_mocks, BaseMCPTest

setup_mocks()

from skills.common import GOVERNANCE_TEMPLATES
from skills.planning_mcp import plan_ba_governance, save_ba_plan, _plan_path

PROJECT = "gov_merge"


def _section(project_id=PROJECT) -> dict:
    with open(_plan_path(project_id), encoding="utf-8") as f:
        return json.load(f)["governance"]


def _report_text(project_id=PROJECT) -> str:
    """The BA Plan markdown, captured from the writer.

    save_ba_plan RETURNS a status message, not the report — asserting on its return
    value proves nothing about the rendered document, and one such assertion passed
    vacuously when this file was first written. save_artifact is mocked suite-wide
    (ADR-068), so the markdown is read from the call. Task 9 exercises the real writer.
    """
    with patch("skills.planning_mcp.save_artifact") as mock_sa:
        mock_sa.return_value = "\n\n✅ Artifact saved: `x.md`"
        save_ba_plan(project_id)
        return mock_sa.call_args[0][0] if mock_sa.call_args else ""


class TestRequiredData(BaseMCPTest):
    """criticality and decision_makers stop being required PARAMETERS (merge would
    otherwise force the BA to retype them on every refinement) but stay required
    DATA: without them every template default silently falls to Medium and both
    cross-checks go permanently quiet."""

    def test_first_call_without_criticality_is_refused_and_says_which(self):
        result = plan_ba_governance(PROJECT, decision_makers_json='["CFO"]')
        self.assertIn("❌", result)
        self.assertIn("project_criticality", result)

    def test_first_call_without_decision_makers_is_refused_and_says_which(self):
        result = plan_ba_governance(PROJECT, "High")
        self.assertIn("❌", result)
        self.assertIn("decision_makers", result)

    def test_clearing_the_list_on_a_first_call_is_refused_for_the_required_reason(self):
        """Distinct from an unparseable list: "[]" now means CLEAR, so the refusal has
        to come from the "required" gate rather than from list validation."""
        result = plan_ba_governance(PROJECT, "High", "[]")
        self.assertIn("❌", result)
        self.assertIn("decision_makers", result)

    def test_an_unparseable_list_still_reports_the_parameter(self):
        result = plan_ba_governance(PROJECT, "High", "not-json")
        self.assertIn("❌", result)
        self.assertIn("decision_makers_json", result)


class TestMerge(BaseMCPTest):

    def test_a_re_run_keeps_everything_the_ba_typed(self):
        """B3-1's worst defect: every parameter optional + replace = a silent wipe."""
        plan_ba_governance(PROJECT, "High", '["CFO", "Head of Risk"]',
                           approval_sla_days=5, escalation_path="BA → CRO → Board",
                           ba_notes="agreed at the kickoff")
        plan_ba_governance(PROJECT, review_cycle="Monthly")
        section = _section()
        self.assertEqual(section["project_criticality"], "High")
        self.assertEqual(section["decision_makers"], ["CFO", "Head of Risk"])
        self.assertEqual(section["approval_sla_days"], 5)
        self.assertEqual(section["escalation_path"], "BA → CRO → Board")
        self.assertEqual(section["ba_notes"], "agreed at the kickoff")
        self.assertEqual(section["review_cycle"], "Monthly")

    def test_the_kept_line_names_every_preserved_field(self):
        """B3-3 finding 9: an incomplete "Kept" line is worse than none — it exists so
        the BA does not have to open the JSON."""
        plan_ba_governance(PROJECT, "High", '["CFO"]',
                           approval_sla_days=5, escalation_path="BA → CRO",
                           approval_timing_note="to the CAB", ba_notes="kickoff")
        result = plan_ba_governance(PROJECT, review_cycle="Monthly").lower()
        for expected in ("criticality", "decision makers", "approval sla",
                         "escalation", "approval timing note", "notes"):
            self.assertIn(expected, result, f"{expected} missing from the Kept line")

    def test_clearing_text_returns_the_field_to_the_template(self):
        plan_ba_governance(PROJECT, "High", '["CFO"]', escalation_path="BA → CRO")
        plan_ba_governance(PROJECT, escalation_path="-")
        section = _section()
        self.assertNotIn("escalation_path", section.get("declared", []))
        self.assertEqual(section["escalation_path"],
                         GOVERNANCE_TEMPLATES["High"]["escalation"])

    def test_clearing_the_sla_and_the_note(self):
        plan_ba_governance(PROJECT, "High", '["CFO"]',
                           approval_sla_days=5, approval_timing_note="to the CAB")
        plan_ba_governance(PROJECT, approval_sla_days=0, approval_timing_note="-")
        section = _section()
        self.assertEqual(section["approval_sla_days"], 0)
        self.assertEqual(section["approval_timing_note"], "")

    def test_the_default_is_not_the_clearing_value(self):
        """B3-1 corollary: when "not passed" and "clear it" are the same input, the
        field becomes unclearable by anything."""
        plan_ba_governance(PROJECT, "High", '["CFO"]', approval_sla_days=5)
        plan_ba_governance(PROJECT, review_cycle="Monthly")
        self.assertEqual(_section()["approval_sla_days"], 5)

    def test_the_list_is_replaced_not_appended(self):
        plan_ba_governance(PROJECT, "High", '["CFO", "Head of Risk"]')
        plan_ba_governance(PROJECT, decision_makers_json='["CRO"]')
        self.assertEqual(_section()["decision_makers"], ["CRO"])

    def test_the_defined_on_date_survives_a_re_run(self):
        plan_ba_governance(PROJECT, "High", '["CFO"]')
        first = _section()["defined_on"]
        plan_ba_governance(PROJECT, review_cycle="Monthly")
        self.assertEqual(_section()["defined_on"], first)


class TestDeclaredVersusTemplate(BaseMCPTest):

    def test_an_undeclared_field_follows_a_criticality_change(self):
        """Machine content must be regenerated when what it was generated for
        changes (B3-1 finding 3)."""
        plan_ba_governance(PROJECT, "High", '["CFO"]')
        self.assertEqual(_section()["escalation_path"],
                         GOVERNANCE_TEMPLATES["High"]["escalation"])
        plan_ba_governance(PROJECT, "Low")
        self.assertEqual(_section()["escalation_path"],
                         GOVERNANCE_TEMPLATES["Low"]["escalation"])

    def test_a_declared_field_survives_a_criticality_change(self):
        """...and the BA's own words must NOT be regenerated — the exception to the
        same rule."""
        plan_ba_governance(PROJECT, "High", '["CFO"]', escalation_path="BA → CRO → Board")
        plan_ba_governance(PROJECT, "Low")
        self.assertEqual(_section()["escalation_path"], "BA → CRO → Board")
        self.assertEqual(_section()["review_cycle"],
                         GOVERNANCE_TEMPLATES["Low"]["review_cycle"])

    def test_declaring_one_field_does_not_mark_the_others(self):
        plan_ba_governance(PROJECT, "High", '["CFO"]', approval_process="Board signs")
        self.assertEqual(_section()["declared"], ["approval_process"])

    def test_a_declared_value_identical_to_the_template_is_recorded_as_declared(self):
        plan_ba_governance(PROJECT, "High", '["CFO"]',
                           review_cycle=GOVERNANCE_TEMPLATES["High"]["review_cycle"])
        self.assertIn("review_cycle", _section()["declared"])

    def test_change_control_keeps_working_as_before(self):
        plan_ba_governance(PROJECT, "High", '["CFO"]',
                           change_control_process="Two-person rule")
        self.assertEqual(_section()["change_control"], "Two-person rule")
        self.assertIn("change_control", _section()["declared"])


class TestValidationAndDamage(BaseMCPTest):

    def test_sla_out_of_range_is_a_readable_error(self):
        plan_ba_governance(PROJECT, "High", '["CFO"]')
        for bad in (-2, 400):
            result = plan_ba_governance(PROJECT, approval_sla_days=bad)
            self.assertIn("❌", result)
            self.assertIn("approval_sla_days", result)

    def test_an_out_of_range_sla_does_not_corrupt_the_stored_value(self):
        plan_ba_governance(PROJECT, "High", '["CFO"]', approval_sla_days=5)
        plan_ba_governance(PROJECT, approval_sla_days=400)
        self.assertEqual(_section()["approval_sla_days"], 5)

    def test_a_damaged_section_can_be_replanned_not_crashed(self):
        """The writer is the only tool that can repair the section, so it must
        survive every shape that is valid JSON."""
        plan_ba_governance(PROJECT, "High", '["CFO"]')
        path = _plan_path(PROJECT)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["governance"] = {"decision_makers": "CFO", "declared": "oops",
                              "project_criticality": "High",
                              "approval_sla_days": "soon",
                              "prioritization": "later"}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        result = plan_ba_governance(PROJECT, decision_makers_json='["PO"]')
        self.assertIn("✅", result)
        self.assertEqual(_section()["decision_makers"], ["PO"])


class TestReport(BaseMCPTest):

    def test_the_report_labels_the_source_of_every_process_field(self):
        """Pre-existing defect: `approval_process` came from the template and could
        not be changed, while `decision_makers` was the BA's real list — two literals
        answering ONE question, side by side in a delivered document."""
        plan_ba_governance(PROJECT, "High", '["CFO", "Head of Risk"]')
        report = _report_text()
        self.assertIn("CFO, Head of Risk", report)
        self.assertIn("from the High template", report)

    def test_a_declared_process_is_labelled_as_declared(self):
        plan_ba_governance(PROJECT, "High", '["CFO"]',
                           approval_process="CFO signs, Board is informed")
        report = _report_text()
        self.assertIn("CFO signs, Board is informed", report)
        self.assertIn("declared in 3.3", report)

    def test_the_sla_reaches_the_report(self):
        plan_ba_governance(PROJECT, "High", '["CFO"]', approval_sla_days=5,
                           approval_timing_note="to the monthly CAB")
        report = _report_text()
        self.assertIn("5 business days", report)
        self.assertIn("to the monthly CAB", report)

    def test_no_sla_row_when_none_is_planned(self):
        plan_ba_governance(PROJECT, "High", '["CFO"]')
        report = _report_text()
        self.assertIn("3.3 Governance", report)      # the section IS rendered...
        self.assertNotIn("business days", report)    # ...it just has no SLA row

    def test_a_string_where_a_list_belongs_does_not_render_per_character(self):
        plan_ba_governance(PROJECT, "High", '["CFO"]')
        path = _plan_path(PROJECT)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["governance"]["decision_makers"] = "CFO"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        report = _report_text()
        self.assertIn("3.3 Governance", report)      # the section IS rendered...
        self.assertNotIn("C, F, O", report)          # ...without the invented entries


class TestPrioritizationApproach(BaseMCPTest):
    """BABOK 3.3 element .3 — technique / participants / criteria.

    The three parts are independent: the plan may declare any subset, and clearing
    one must never silently discard another the BA typed in a different call.
    """

    def setUp(self):
        super().setUp()
        plan_ba_governance(PROJECT, "High", '["CFO"]')

    def _damage(self, block):
        """Put a hand-edited prioritization block on disk.

        The BA Plan renderer reads the STORED block, not `planned_prioritization`, so
        the reader's vocabulary and type guards do not protect the delivered document.
        """
        path = _plan_path(PROJECT)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["governance"]["prioritization"] = block
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    # --- storage -------------------------------------------------------------

    def test_all_three_fields_are_stored(self):
        plan_ba_governance(PROJECT, prioritization_technique="WSJF",
                           prioritization_participants_json='["PO", "Head of Risk"]',
                           prioritization_criteria_json='["cost", "risk"]')
        block = _section()["prioritization"]
        self.assertEqual(block["technique"], "WSJF")
        self.assertEqual(block["participants"], ["PO", "Head of Risk"])
        self.assertEqual(block["criteria"], ["cost", "risk"])

    def test_the_three_fields_are_independent(self):
        plan_ba_governance(PROJECT, prioritization_technique="WSJF",
                           prioritization_participants_json='["PO"]',
                           prioritization_criteria_json='["cost"]')
        plan_ba_governance(PROJECT, prioritization_technique="None")
        block = _section()["prioritization"]
        self.assertEqual(block["technique"], "")
        self.assertEqual(block["participants"], ["PO"])
        self.assertEqual(block["criteria"], ["cost"])

    def test_clearing_the_participants_leaves_the_technique_and_criteria(self):
        """The other direction of the same rule — one shared branch would pass the
        test above and still wipe two fields here."""
        plan_ba_governance(PROJECT, prioritization_technique="WSJF",
                           prioritization_participants_json='["PO"]',
                           prioritization_criteria_json='["cost"]')
        plan_ba_governance(PROJECT, prioritization_participants_json="[]")
        block = _section()["prioritization"]
        self.assertEqual(block["participants"], [])
        self.assertEqual(block["technique"], "WSJF")
        self.assertEqual(block["criteria"], ["cost"])

    def test_a_re_run_keeps_the_block(self):
        plan_ba_governance(PROJECT, prioritization_technique="MoSCoW",
                           prioritization_criteria_json='["value"]')
        plan_ba_governance(PROJECT, review_cycle="Monthly")
        block = _section()["prioritization"]
        self.assertEqual(block["technique"], "MoSCoW")
        self.assertEqual(block["criteria"], ["value"])

    def test_the_kept_line_names_the_prioritization_fields(self):
        """B3-3 finding 9 again: the Kept line exists so the BA does not open the
        JSON, so it has to be complete for the new fields too."""
        plan_ba_governance(PROJECT, prioritization_technique="WSJF",
                           prioritization_participants_json='["PO"]',
                           prioritization_criteria_json='["cost"]')
        result = plan_ba_governance(PROJECT, review_cycle="Monthly").lower()
        for expected in ("prioritization technique", "prioritization participants",
                         "prioritization criteria"):
            self.assertIn(expected, result, f"{expected} missing from the Kept line")

    # --- validation ----------------------------------------------------------

    def test_an_unparseable_participants_list_reports_the_parameter(self):
        result = plan_ba_governance(PROJECT, prioritization_participants_json="not-json")
        self.assertIn("❌", result)
        self.assertIn("prioritization_participants_json", result)

    def test_an_unparseable_criteria_list_reports_the_parameter(self):
        result = plan_ba_governance(PROJECT, prioritization_criteria_json="{}")
        self.assertIn("❌", result)
        self.assertIn("prioritization_criteria_json", result)

    def test_a_hand_edited_block_is_repaired_on_the_next_run(self):
        """The writer is the only tool that can overwrite the section, so it must
        survive — and clean — every shape that is valid JSON."""
        self._damage({"technique": "Gut feel", "participants": "PO", "criteria": 7})
        result = plan_ba_governance(PROJECT, review_cycle="Monthly")
        self.assertIn("✅", result)
        self.assertEqual(_section()["prioritization"],
                         {"technique": "", "participants": [], "criteria": []})

    # --- the tool's own status line ------------------------------------------

    def test_the_status_line_names_every_planned_part(self):
        result = plan_ba_governance(
            PROJECT, prioritization_technique="WSJF",
            prioritization_participants_json='["PO", "Head of Risk"]',
            prioritization_criteria_json='["cost", "risk"]')
        self.assertIn("WSJF", result)
        self.assertIn("PO, Head of Risk", result)
        self.assertIn("cost, risk", result)

    def test_criteria_alone_are_reported_back(self):
        """A ✅ over content the BA cannot see recorded is how dropped input goes
        unnoticed; any subset the plan accepts has to be echoed."""
        result = plan_ba_governance(PROJECT, prioritization_criteria_json='["cost", "risk"]')
        self.assertIn("cost, risk", result)

    def test_no_prioritization_row_when_none_is_planned(self):
        result = plan_ba_governance(PROJECT, review_cycle="Monthly")
        self.assertIn("Governance plan recorded", result)   # the status IS rendered...
        self.assertNotIn("Prioritization:", result)         # ...with no .3 row

    # --- the BA Plan report ---------------------------------------------------

    def test_the_report_renders_the_block_only_when_planned(self):
        report_without = _report_text()
        self.assertIn("3.3 Governance", report_without)              # section IS there...
        self.assertNotIn("Prioritization approach", report_without)  # ...without the block
        plan_ba_governance(PROJECT, prioritization_technique="WSJF",
                           prioritization_participants_json='["PO", "Head of Risk"]',
                           prioritization_criteria_json='["cost", "risk"]')
        report = _report_text()
        self.assertIn("Prioritization approach", report)
        self.assertIn("WSJF", report)
        self.assertIn("PO, Head of Risk", report)
        self.assertIn("cost, risk", report)

    def test_a_string_where_the_participants_belong_does_not_render_per_character(self):
        """The `decision_makers` defect one level deeper: the renderer joins the
        participants, so `"participants": "PO"` would print two planned scorers,
        P and O, inside a delivered document."""
        self._damage({"technique": "WSJF", "participants": "PO", "criteria": ["cost"]})
        report = _report_text()
        self.assertIn("Prioritization approach", report)   # the block IS rendered...
        self.assertNotIn("P, O", report)                   # ...without invented scorers

    def test_a_technique_outside_the_vocabulary_is_not_rendered_as_planned(self):
        """`planned_prioritization` drops an unknown technique for the 5.3 cross-check,
        but the report reads the stored block directly — the same value has to be
        dropped where it is stored, or the two disagree in a delivered document."""
        self._damage({"technique": "Gut feel", "criteria": ["cost"]})
        report = _report_text()
        self.assertIn("Prioritization approach", report)   # the block IS rendered...
        self.assertNotIn("Gut feel", report)               # ...without the junk technique


class TestPlansWrittenBeforeThisFeature(BaseMCPTest):
    """`declared` is NEW. Every other test in this file seeds state by calling the
    CURRENT writer, which always writes the key — so none of them can construct the
    one shape that exists on every real project that planned 3.3 before this branch.

    Found by two independent branch reviewers. The class is general: when a merge
    starts deciding what to keep from a NEW bookkeeping key, absent-key is not the
    same state as empty-key, and only the old writer can produce absent.
    """

    LEGACY_TEXT = ("All CRs go to the Basel III Compliance Board within 48h; no "
                   "change ships without a written regulator impact note.")

    def _write_legacy(self, **overrides):
        """A governance section exactly as the PRE-FEATURE writer stored it."""
        section = {
            "project_criticality": "High",
            "decision_makers": ["Sponsor", "PO"],
            "change_control": self.LEGACY_TEXT,
            "approval_process": "Two-key sign-off: CRO and Head of Compliance.",
            "review_cycle": "Fortnightly, minuted.",
            "escalation_path": "BA → CRO → Board Risk Committee",
            "defined_on": "2026-05-01",
        }
        section.update(overrides)
        path = _plan_path(PROJECT)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"project_id": PROJECT, "governance": section}, f)

    def test_a_legacy_plan_keeps_its_text_when_a_new_field_is_added(self):
        """The whole point of the feature is to make the BA re-run 3.3 and add a
        technique. On a pre-feature plan that re-run replaced the analyst's own
        regulator-facing process with template boilerplate, answered ✅, and attributed
        the replacement to the template."""
        self._write_legacy()
        result = plan_ba_governance(PROJECT, prioritization_technique="MoSCoW")
        self.assertEqual(_section()["change_control"], self.LEGACY_TEXT)
        self.assertIn("Fortnightly, minuted.", result)
        self.assertIn("BA → CRO → Board Risk Committee", result)

    def test_a_legacy_value_of_unknown_origin_is_not_called_declared(self):
        """Keeping it is right; crediting the analyst for it is not. The value's origin
        is genuinely unknown — the old writer stored the template and a BA's own text
        in the same field with nothing to tell them apart."""
        self._write_legacy()
        plan_ba_governance(PROJECT, prioritization_technique="MoSCoW")
        report = _report_text()
        self.assertIn(self.LEGACY_TEXT, report)
        self.assertNotIn("declared in 3.3 | ", report.split("Change control")[1][:60])

    def test_an_empty_declared_list_still_means_nothing_was_declared(self):
        """The counterpart: `declared: []` is a POSITIVE statement by the current
        writer that the BA declared nothing, so the template must be regenerated when
        the criticality changes. Absent-key and empty-list must not collapse."""
        self._write_legacy(declared=[])
        plan_ba_governance(PROJECT, "Low")
        self.assertEqual(_section()["change_control"],
                         GOVERNANCE_TEMPLATES["Low"]["change_control"])


class TestClearingTheDecisionMakers(BaseMCPTest):

    def test_clearing_an_existing_list_says_what_is_actually_wrong(self):
        """`"[]"` clears a list everywhere else in 3.3/3.4, and the docstring says so.
        Refusing here is right — an empty list would switch the 5.4/5.5 cross-checks off
        silently — but the refusal claimed 3.3 had never been planned, which on an
        already-planned project is false and sends the BA hunting for a missing file."""
        plan_ba_governance(PROJECT, "High", '["CFO", "Head of Risk"]')
        result = plan_ba_governance(PROJECT, decision_makers_json='[]')
        self.assertIn("❌", result)
        self.assertNotIn("the first time 3.3 is planned", result)
        self.assertIn("CFO, Head of Risk", result)          # what is planned right now
        # And it really did refuse: the stored list is untouched.
        self.assertEqual(_section()["decision_makers"], ["CFO", "Head of Risk"])

    def test_the_first_time_message_still_names_the_first_time(self):
        result = plan_ba_governance(PROJECT, "High", decision_makers_json='[]')
        self.assertIn("the first time 3.3 is planned", result)


class TestDeclaredMarkerCannotOutliveItsValue(BaseMCPTest):

    def test_a_dropped_field_loses_its_declared_marker(self):
        """The shape guard deletes a non-string `escalation_path`, but the marker
        naming it survived — the next run wrote the TEMPLATE and the reader then
        reported it as `declared in 3.3`. A generated default attributed to the
        analyst, in the CR Decision Record an auditor reads."""
        plan_ba_governance(PROJECT, "High", '["CFO", "Head of Risk"]',
                           escalation_path="BA → CRO → Board")
        path = _plan_path(PROJECT)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["governance"]["escalation_path"] = {"oops": True}      # hand-edited
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        result = plan_ba_governance(PROJECT, review_cycle="Monthly")
        self.assertIn(GOVERNANCE_TEMPLATES["High"]["escalation"], result)
        self.assertNotIn("Board", result)                  # the damaged value is gone
        self.assertNotIn("escalation_path", _section().get("declared", []))
        # And the reader must agree with the plan about who authored it.
        from skills.common import planned_escalation_path
        with open(path, encoding="utf-8") as f:
            _text, source = planned_escalation_path(json.load(f))
        self.assertNotIn("declared", source)


class TestCriticalityIsGuardedByValue(BaseMCPTest):
    """The neighbours guard for VALUE — the traceability level and the technique both
    do, each with a comment explaining why. The criticality was left type-guarded only,
    in the very section where the Source column was added."""

    def _hand_edit_criticality(self, value):
        plan_ba_governance(PROJECT, "High", '["CFO", "Head of Risk"]')
        path = _plan_path(PROJECT)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["governance"]["project_criticality"] = value
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def test_the_report_does_not_cite_a_template_that_does_not_exist(self):
        self._hand_edit_criticality("Catastrophic")
        report = _report_text()
        self.assertIn("3.3 Governance", report)            # the section IS rendered
        self.assertNotIn("from the Catastrophic template", report)

    def test_a_lower_cased_criticality_does_not_cite_an_empty_template(self):
        """`"high"` is an ordinary hand edit. It silently disabled the readers, and the
        Source column then read "from the high template"."""
        self._hand_edit_criticality("high")
        report = _report_text()
        self.assertIn("3.3 Governance", report)
        self.assertNotIn("from the high template", report)
        self.assertNotIn("from the  template", report)


if __name__ == "__main__":
    unittest.main()
