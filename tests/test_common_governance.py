"""Shared reader layer for the 3.3 governance section (B3-2).

Every consumer of the governance plan lives in another chapter — 5.3/5.4/5.5 load in
the `lifecycle` phase and chapter 3 loads in BASE_SERVER — so they read ONLY through
these helpers, never by importing planning_mcp.

The tests here pin the two rules that broke B3-3 and B3-1: a stored value is guarded
for TYPE *and* for VALUE, and a coercion never invents keys.

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import setup_mocks, BaseMCPTest

setup_mocks()

from skills.common import (
    stakeholder_registry_path,
    GOVERNANCE_TEMPLATES,
    PRIORITIZATION_TECHNIQUES,
    governance_section,
    planned_decision_makers,
    is_planned_decision_maker,
    planned_approval_timing,
    planned_approval_process,
    planned_escalation_path,
    planned_prioritization,
    party_aliases,
    planned_party_status,
    PARTY_PLANNED,
    PARTY_UNPLANNED,
    PARTY_UNBRIDGEABLE,
)


def _plan(**governance):
    return {"project_id": "p", "governance": governance}


class TestGovernanceSection(unittest.TestCase):
    def test_non_dict_plan_gives_empty_section(self):
        for bad in (None, "oops", [], 7):
            self.assertEqual(governance_section(bad), {})

    def test_non_dict_section_gives_empty_section(self):
        for bad in (None, "oops", [], 7):
            self.assertEqual(governance_section({"governance": bad}), {})

    def test_coercion_does_not_invent_keys(self):
        """B3-1 finding 2: a coercion that supplies missing keys is permanently truthy,
        so "was anything actually planned?" stops being answerable."""
        self.assertEqual(governance_section(_plan()), {})
        self.assertNotIn("decision_makers",
                         governance_section(_plan(project_criticality="High")))


class TestDecisionMakers(unittest.TestCase):
    def test_reads_the_list(self):
        self.assertEqual(
            planned_decision_makers(_plan(decision_makers=["CFO", "Head of Risk"])),
            ["CFO", "Head of Risk"])

    def test_a_bare_string_is_dropped_not_iterated(self):
        """B3-3 finding 1: `or []` normalises falsiness, not type — "CFO" would become
        three planned authorities C, F, O in a delivered document."""
        self.assertEqual(planned_decision_makers(_plan(decision_makers="CFO")), [])

    def test_non_string_entries_are_dropped(self):
        self.assertEqual(
            planned_decision_makers(_plan(decision_makers=["CFO", 7, None, "  ", "PO"])),
            ["CFO", "PO"])

    def test_match_is_normalised_on_both_sides(self):
        """B3-3 finding 3: producer and consumer must normalise with ONE function."""
        plan = _plan(decision_makers=["Head of Risk"])
        self.assertTrue(is_planned_decision_maker(plan, "  head of   risk "))
        self.assertFalse(is_planned_decision_maker(plan, "Head of Retail"))

    def test_no_plan_means_no_match_and_no_crash(self):
        self.assertFalse(is_planned_decision_maker(None, "CFO"))
        self.assertFalse(is_planned_decision_maker(_plan(), "CFO"))
        self.assertFalse(is_planned_decision_maker(_plan(decision_makers=["CFO"]), ""))


class TestApprovalTiming(unittest.TestCase):
    def test_declared_days_and_note(self):
        days, note, source = planned_approval_timing(
            _plan(approval_sla_days=5, approval_timing_note="to the monthly CAB"))
        self.assertEqual(days, 5)
        self.assertEqual(note, "to the monthly CAB")
        self.assertEqual(source, "заявлено в 3.3")

    def test_nothing_planned_returns_no_source(self):
        days, note, source = planned_approval_timing(_plan(project_criticality="High"))
        self.assertIsNone(days)
        self.assertEqual(note, "")
        self.assertEqual(source, "")

    def test_days_of_the_wrong_type_or_range_are_dropped(self):
        """A guard that type-checks but does not value-check passes junk from stored
        JSON straight into a signed document (B3-1 finding 6)."""
        for bad in ("5", -3, 400, None, [5], 5.5):
            days, _, _ = planned_approval_timing(_plan(approval_sla_days=bad))
            self.assertIsNone(days, f"{bad!r} must not survive")

    def test_true_is_not_a_one_day_sla(self):
        """`bool` is an `int` in Python: without the explicit bool check, a stored
        `true` becomes a one-business-day deadline on the approval package."""
        days, _, _ = planned_approval_timing(_plan(approval_sla_days=True))
        self.assertIsNone(days)

    def test_zero_days_is_not_a_deadline(self):
        days, _, source = planned_approval_timing(_plan(approval_sla_days=0))
        self.assertIsNone(days)
        self.assertEqual(source, "")

    def test_a_note_alone_is_enough_to_have_a_source(self):
        days, note, source = planned_approval_timing(
            _plan(approval_timing_note="to the monthly CAB"))
        self.assertIsNone(days)
        self.assertEqual(source, "заявлено в 3.3")

    def test_a_non_string_note_is_dropped(self):
        _, note, source = planned_approval_timing(_plan(approval_timing_note=["CAB"]))
        self.assertEqual(note, "")
        self.assertEqual(source, "")


class TestApprovalProcessAndEscalation(unittest.TestCase):
    def test_declared_wins_over_template(self):
        text, source = planned_approval_process(
            _plan(project_criticality="High",
                  approval_process="Board sign-off",
                  declared=["approval_process"]))
        self.assertEqual(text, "Board sign-off")
        self.assertEqual(source, "заявлено в 3.3")

    def test_undeclared_falls_back_to_the_criticality_template(self):
        text, source = planned_approval_process(_plan(project_criticality="Low"))
        self.assertEqual(text, GOVERNANCE_TEMPLATES["Low"]["approval"])
        self.assertEqual(source, "из шаблона Low")

    def test_a_declared_value_identical_to_the_template_is_still_declared(self):
        """B3-1 finding 5: a lookalike CONDITION drifts from the record it imitates.
        The source comes from the `declared` list, never from comparing values — a BA
        who states wording identical to the template still stated it."""
        _text, source = planned_approval_process(
            _plan(project_criticality="High",
                  approval_process=GOVERNANCE_TEMPLATES["High"]["approval"],
                  declared=["approval_process"]))
        self.assertEqual(source, "заявлено в 3.3")

    def test_unknown_criticality_yields_no_template_and_no_source(self):
        text, source = planned_approval_process(_plan(project_criticality="Catastrophic"))
        self.assertEqual(text, "")
        self.assertEqual(source, "")

    def test_a_declared_marker_with_no_value_falls_back_to_the_template(self):
        """Being listed in `declared` is not the same as holding a usable value."""
        text, source = planned_approval_process(
            _plan(project_criticality="Low", approval_process="",
                  declared=["approval_process"]))
        self.assertEqual(text, GOVERNANCE_TEMPLATES["Low"]["approval"])
        self.assertEqual(source, "из шаблона Low")

    def test_a_corrupt_declared_list_does_not_crash_the_reader(self):
        text, source = planned_approval_process(
            _plan(project_criticality="Low", approval_process="Board", declared="oops"))
        self.assertEqual(text, GOVERNANCE_TEMPLATES["Low"]["approval"])
        self.assertEqual(source, "из шаблона Low")

    def test_escalation_follows_the_same_rule(self):
        text, source = planned_escalation_path(_plan(project_criticality="Medium"))
        self.assertEqual(text, GOVERNANCE_TEMPLATES["Medium"]["escalation"])
        self.assertEqual(source, "из шаблона Medium")

    def test_escalation_can_be_declared(self):
        text, source = planned_escalation_path(
            _plan(project_criticality="Medium", escalation_path="BA → CRO → Board",
                  declared=["escalation_path"]))
        self.assertEqual(text, "BA → CRO → Board")
        self.assertEqual(source, "заявлено в 3.3")

    def test_the_two_fields_do_not_share_a_declared_marker(self):
        """Declaring the escalation path must not relabel the approval process."""
        _text, source = planned_approval_process(
            _plan(project_criticality="High", approval_process="Board sign-off",
                  declared=["escalation_path"]))
        self.assertEqual(source, "из шаблона High")


class TestPlannedPrioritization(unittest.TestCase):
    def test_reads_all_three_fields(self):
        result = planned_prioritization(_plan(prioritization={
            "technique": "WSJF",
            "participants": ["PO", "Head of Risk"],
            "criteria": ["cost", "risk"],
        }))
        self.assertEqual(result["technique"], "WSJF")
        self.assertEqual(result["participants"], ["PO", "Head of Risk"])
        self.assertEqual(result["criteria"], ["cost", "risk"])

    def test_an_unknown_technique_is_dropped(self):
        """The value exists to be compared with 5.3's `method`; rendering an
        unrecognised string as "the planned technique" would present junk from a
        hand-edited file as a plan."""
        result = planned_prioritization(_plan(prioritization={"technique": "Gut feel"}))
        self.assertEqual(result["technique"], "")

    def test_string_lists_are_dropped_not_iterated(self):
        result = planned_prioritization(_plan(prioritization={
            "participants": "PO", "criteria": "cost"}))
        self.assertEqual(result["participants"], [])
        self.assertEqual(result["criteria"], [])

    def test_non_dict_prioritization_is_empty(self):
        for bad in (None, "oops", ["WSJF"], 7):
            result = planned_prioritization(_plan(prioritization=bad))
            self.assertEqual(result,
                             {"technique": "", "participants": [], "criteria": []})


class TestVocabulary(unittest.TestCase):
    def test_techniques_match_the_53_method_literal(self):
        """Chapter 3 cannot import chapter 5 (different phases), so the vocabulary is a
        copy. This test is what keeps the copy honest — the same device that pins
        _AUDIENCE_ARCHETYPES to 4.4's audience_role."""
        import typing
        from skills.requirements_prioritize_mcp import start_prioritization_session
        hints = typing.get_type_hints(start_prioritization_session)
        self.assertEqual(set(PRIORITIZATION_TECHNIQUES),
                         set(typing.get_args(hints["method"])))


class TestTheRegistryBridgesRoleAndName(BaseMCPTest):
    """3.3 plans ROLES; 5.3/5.4/5.5 are called with whatever the BA typed, usually a
    person. Both branch reviewers found this independently: the join could not succeed
    by construction, and its failure was rendered as an authority exception in signed
    documents.
    """

    PROJECT = "bridge"
    PLANNED = ["Sponsor", "Product Owner"]

    def _registry(self, people):
        path = stakeholder_registry_path(self.PROJECT)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"project": self.PROJECT, "stakeholders": people}, f)

    def test_a_person_is_matched_to_their_planned_role(self):
        self._registry([{"name": "John Smith", "role": "Product Owner"}])
        self.assertEqual(
            planned_party_status(self.PROJECT, self.PLANNED, "John Smith"),
            PARTY_PLANNED)

    def test_the_bridge_works_in_the_other_direction_too(self):
        """The plan may name a person and the tool be called with a role."""
        self._registry([{"name": "John Smith", "role": "Product Owner"}])
        self.assertEqual(
            planned_party_status(self.PROJECT, ["John Smith"], "Product Owner"),
            PARTY_PLANNED)

    def test_a_person_whose_role_is_not_planned_is_still_reported(self):
        self._registry([{"name": "Mark Feld", "role": "Scheduling Lead"}])
        self.assertEqual(
            planned_party_status(self.PROJECT, self.PLANNED, "Mark Feld"),
            PARTY_UNPLANNED)

    def test_without_a_registry_the_check_reports_that_it_cannot_tell(self):
        """The decisive case. With nothing tying a role to a name, a non-match means
        the two labels are incomparable — saying "lacks authority" would be a guess
        stated as a fact in an audit document."""
        self.assertEqual(
            planned_party_status(self.PROJECT, self.PLANNED, "John Smith"),
            PARTY_UNBRIDGEABLE)

    def test_an_exact_role_match_needs_no_registry(self):
        """A BA who types the role still gets a real answer with no registry at all —
        the bridge only ever ADDS matches."""
        self.assertEqual(
            planned_party_status(self.PROJECT, self.PLANNED, "  product   OWNER "),
            PARTY_PLANNED)

    def test_no_plan_means_no_finding(self):
        self.assertEqual(planned_party_status(self.PROJECT, [], "anyone"),
                         PARTY_PLANNED)

    def test_a_damaged_registry_does_not_raise(self):
        path = stakeholder_registry_path(self.PROJECT)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("{ not json")
        self.assertEqual(
            planned_party_status(self.PROJECT, self.PLANNED, "John Smith"),
            PARTY_UNBRIDGEABLE)

    def test_registry_rows_of_the_wrong_shape_are_skipped(self):
        self._registry(["oops", 7, None, {"name": "John Smith",
                                          "role": "Product Owner"}])
        self.assertEqual(party_aliases(self.PROJECT, "John Smith"),
                         {"john smith", "product owner"})

    def test_is_planned_decision_maker_uses_the_bridge_when_given_a_project(self):
        self._registry([{"name": "John Smith", "role": "Product Owner"}])
        plan = _plan(decision_makers=self.PLANNED)
        self.assertTrue(is_planned_decision_maker(plan, "John Smith", self.PROJECT))
        # ...and without a project_id it is the old exact match, unchanged.
        self.assertFalse(is_planned_decision_maker(plan, "John Smith"))
        self.assertTrue(is_planned_decision_maker(plan, "Product Owner"))


class TestCarriedOverReachesTheReaders(BaseMCPTest):
    """FOUND BY THE FIX-WAVE RE-REVIEW. The carried-over state was taught to the WRITER
    and to the BA Plan renderer, and not to the three readers 5.4 and 5.5 actually
    print from — so one project had two delivered documents naming different escalation
    paths, and the CR record's was a string the plan file does not contain."""

    def _legacy_plan(self):
        return {"project_id": "p", "governance": {
            "project_criticality": "High",
            "decision_makers": ["Sponsor"],
            "escalation_path": "BA → CRO → Board Risk Committee",
            "approval_process": "Two-key sign-off: CRO and Head of Compliance.",
            "declared": [],
            "carried_over": ["escalation_path", "approval_process"],
        }}

    def test_a_carried_over_escalation_path_is_read_not_regenerated(self):
        text, source = planned_escalation_path(self._legacy_plan())
        self.assertEqual(text, "BA → CRO → Board Risk Committee")
        self.assertNotIn("declared", source)          # not credited to the BA...
        self.assertNotIn("шаблон", source)          # ...and not blamed on a template

    def test_a_carried_over_approval_process_is_read_not_regenerated(self):
        text, source = planned_approval_process(self._legacy_plan())
        self.assertEqual(text, "Two-key sign-off: CRO and Head of Compliance.")
        self.assertIn("перенесено", source)

    def test_declared_still_wins_over_carried_over(self):
        plan = self._legacy_plan()
        plan["governance"]["declared"] = ["escalation_path"]
        _text, source = planned_escalation_path(plan)
        self.assertEqual(source, "заявлено в 3.3")

    def test_a_carried_over_marker_without_a_value_falls_back_to_the_template(self):
        plan = self._legacy_plan()
        del plan["governance"]["escalation_path"]
        text, source = planned_escalation_path(plan)
        self.assertEqual(text, GOVERNANCE_TEMPLATES["High"]["escalation"])
        self.assertIn("шаблон", source)


if __name__ == "__main__":
    unittest.main()
