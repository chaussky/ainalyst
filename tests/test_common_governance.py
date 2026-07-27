"""Shared reader layer for the 3.3 governance section (B3-2).

Every consumer of the governance plan lives in another chapter — 5.3/5.4/5.5 load in
the `lifecycle` phase and chapter 3 loads in BASE_SERVER — so they read ONLY through
these helpers, never by importing planning_mcp.

The tests here pin the two rules that broke B3-3 and B3-1: a stored value is guarded
for TYPE *and* for VALUE, and a coercion never invents keys.

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""
import unittest

from skills.common import (
    GOVERNANCE_TEMPLATES,
    PRIORITIZATION_TECHNIQUES,
    governance_section,
    planned_decision_makers,
    is_planned_decision_maker,
    planned_approval_timing,
    planned_approval_process,
    planned_escalation_path,
    planned_prioritization,
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
        self.assertEqual(source, "declared in 3.3")

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
        self.assertEqual(source, "declared in 3.3")

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
        self.assertEqual(source, "declared in 3.3")

    def test_undeclared_falls_back_to_the_criticality_template(self):
        text, source = planned_approval_process(_plan(project_criticality="Low"))
        self.assertEqual(text, GOVERNANCE_TEMPLATES["Low"]["approval"])
        self.assertEqual(source, "from the Low template")

    def test_a_declared_value_identical_to_the_template_is_still_declared(self):
        """B3-1 finding 5: a lookalike CONDITION drifts from the record it imitates.
        The source comes from the `declared` list, never from comparing values — a BA
        who states wording identical to the template still stated it."""
        _text, source = planned_approval_process(
            _plan(project_criticality="High",
                  approval_process=GOVERNANCE_TEMPLATES["High"]["approval"],
                  declared=["approval_process"]))
        self.assertEqual(source, "declared in 3.3")

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
        self.assertEqual(source, "from the Low template")

    def test_a_corrupt_declared_list_does_not_crash_the_reader(self):
        text, source = planned_approval_process(
            _plan(project_criticality="Low", approval_process="Board", declared="oops"))
        self.assertEqual(text, GOVERNANCE_TEMPLATES["Low"]["approval"])
        self.assertEqual(source, "from the Low template")

    def test_escalation_follows_the_same_rule(self):
        text, source = planned_escalation_path(_plan(project_criticality="Medium"))
        self.assertEqual(text, GOVERNANCE_TEMPLATES["Medium"]["escalation"])
        self.assertEqual(source, "from the Medium template")

    def test_escalation_can_be_declared(self):
        text, source = planned_escalation_path(
            _plan(project_criticality="Medium", escalation_path="BA → CRO → Board",
                  declared=["escalation_path"]))
        self.assertEqual(text, "BA → CRO → Board")
        self.assertEqual(source, "declared in 3.3")

    def test_the_two_fields_do_not_share_a_declared_marker(self):
        """Declaring the escalation path must not relabel the approval process."""
        _text, source = planned_approval_process(
            _plan(project_criticality="High", approval_process="Board sign-off",
                  declared=["escalation_path"]))
        self.assertEqual(source, "from the High template")


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


if __name__ == "__main__":
    unittest.main()
