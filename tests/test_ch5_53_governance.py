"""tests/test_ch5_53_governance.py — Seam C: the 3.3 prioritization approach (element
.3) reaches the 5.3 session, the scorers and the delivered report (B3-2).

PROBED BEFORE A SINGLE ASSERTION WAS WRITTEN (T4-1: a tool's return value is not
necessarily its delivered document, and the rule is not uniform in this codebase):
  - `start_prioritization_session` RETURNS the session document.
  - `add_stakeholder_scores` RETURNS a short status message.
  - `save_prioritization_result` builds `content`, hands it to `save_artifact` and
    returns `content + saved` — so the return value contains the delivered report
    verbatim. (`resolve_cr` and `save_ba_plan`, both in this feature, do NOT.)

Traps in the CURRENT output that this file deliberately avoids:
  - the 5.3 session header already prints `**Method:** MoSCoW` and the result report
    prints `**Method:** MoSCoW`, so `assertIn("MoSCoW", ...)` proves nothing about a
    cross-check. Every assertion below names the WARNING or the RECONCILIATION
    wording, or a phrase that contains both values at once.
  - `', '.join(["PO"])` is indistinguishable from the raw string "PO", so every
    fixture whose join is under test carries TWO entries.

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import setup_mocks, BaseMCPTest

setup_mocks()

from skills.common import ba_plan_path, stakeholder_registry_path
from skills.planning_mcp import plan_ba_governance
from skills.requirements_prioritize_mcp import (
    start_prioritization_session, add_stakeholder_scores, run_aggregation,
    save_prioritization_result)
from skills.requirements_traceability_mcp import init_traceability_repo

PROJECT = "gov53"

REQS = json.dumps([
    {"id": "FR-001", "title": "Login", "type": "functional"},
    {"id": "FR-002", "title": "Logout", "type": "functional"},
])

TWO_PARTICIPANTS = '["Product Owner", "Head of Risk"]'
BOTH = "Product Owner, Head of Risk"

MOSCOW_SCORES = ('[{"req_id": "FR-001", "score": "Must"}, '
                 '{"req_id": "FR-002", "score": "Should"}]')


class PrioritizationGovernanceBase(BaseMCPTest):
    """A 5.1 repository with two requirements, ready for a 5.3 session.

    A stakeholder registry is seeded too, because a real project has one: 3.2 seeds it
    and 4.2 maintains it, and it is what bridges a planned ROLE to a typed NAME. With
    no registry at all the cross-check reports that it cannot tell (PARTY_UNBRIDGEABLE)
    and stays silent — `NoRegistryTest` below covers that deliberately.
    """

    REGISTRY = [
        {"name": "Priya Nair", "role": "Product Owner"},
        {"name": "Dana Cole", "role": "Head of Risk"},
        {"name": "Mark Feld", "role": "Marketing Lead"},
        {"name": "Sam Doyle", "role": "Lead Architect"},
    ]

    def setUp(self):
        super().setUp()
        # THREE arguments: `formality_level` is required and SECOND.
        init_traceability_repo(PROJECT, "Standard", REQS)
        self._seed_registry(self.REGISTRY)

    def _seed_registry(self, rows):
        path = stakeholder_registry_path(PROJECT)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"project": PROJECT, "stakeholders": rows}, f)

    def _write_plan(self, governance):
        """Write a ba_plan.json by hand — for shapes `plan_ba_governance` cannot produce."""
        path = ba_plan_path(PROJECT)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"project_id": PROJECT, "governance": governance}, f)

    def _finalised_report(self, scorer="Product Owner"):
        """The delivered 5.3 result report."""
        start_prioritization_session(PROJECT, "S1", "MoSCoW")
        add_stakeholder_scores(PROJECT, "S1", scorer, "High", MOSCOW_SCORES)
        run_aggregation(PROJECT, "S1")
        return save_prioritization_result(PROJECT, "S1")


# ---------------------------------------------------------------------------
# C1 — start_prioritization_session cross-checks the technique
# ---------------------------------------------------------------------------

class TechniqueCrossCheckTest(PrioritizationGovernanceBase):

    def test_a_technique_mismatch_is_flagged_with_both_values(self):
        """The planned technique is WSJF and the session is MoSCoW, so "WSJF" can only
        have come from the cross-check — "MoSCoW" is in the header either way."""
        plan_ba_governance(PROJECT, "High", '["PO"]', prioritization_technique="WSJF")
        result = start_prioritization_session(PROJECT, "S1", "MoSCoW")
        self.assertIn("uses **MoSCoW**, but 3.3 plans the technique **WSJF**", result)
        self.assertIn("⚠️", result)

    def test_the_method_is_never_overridden_by_the_plan(self):
        """`method` selects the whole aggregation algorithm. A plan that silently
        switched it would change every priority the session produces."""
        plan_ba_governance(PROJECT, "High", '["PO"]', prioritization_technique="WSJF")
        result = start_prioritization_session(PROJECT, "S1", "MoSCoW")
        self.assertIn("**Method:** MoSCoW", result)
        # WSJF sessions print a "**Scale:**" line and a BV/TC/RR/JS table; a MoSCoW
        # session must not have switched to either.
        self.assertNotIn("**Scale:**", result)
        self.assertNotIn("BV=?", result)

    def test_a_matching_technique_is_not_flagged(self):
        plan_ba_governance(PROJECT, "High", '["PO"]', prioritization_technique="WSJF")
        result = start_prioritization_session(PROJECT, "S1", "WSJF")
        self.assertIn("# Prioritization session: S1", result)      # it rendered
        self.assertNotIn("but 3.3 plans the technique", result)

    def test_no_planned_technique_means_no_message(self):
        plan_ba_governance(PROJECT, "High", '["PO"]')
        result = start_prioritization_session(PROJECT, "S1", "MoSCoW")
        self.assertIn("# Prioritization session: S1", result)
        self.assertNotIn("but 3.3 plans the technique", result)

    def test_without_a_plan_the_session_is_unchanged(self):
        result = start_prioritization_session(PROJECT, "S1", "MoSCoW")
        self.assertIn("# Prioritization session: S1", result)
        self.assertNotIn("3.3", result)

    def test_a_governance_section_of_the_wrong_type_does_not_raise(self):
        """Chapter 3 loads in EVERY phase — an AttributeError here is a protocol error
        in every session, not a 5.3 bug."""
        for i, bad in enumerate((None, "oops", ["WSJF"], 7)):
            with self.subTest(governance=bad):
                self._write_plan(bad)
                result = start_prioritization_session(PROJECT, f"S{i}", "MoSCoW")
                self.assertIn(f"# Prioritization session: S{i}", result)
                self.assertNotIn("but 3.3 plans the technique", result)

    def test_a_hand_edited_technique_outside_the_vocabulary_is_not_flagged(self):
        """Junk from a hand-edited plan must not be rendered as "the planned
        technique" — the value exists only to be compared with 5.3's `method`."""
        self._write_plan({"project_criticality": "High",
                          "prioritization": {"technique": "Gut feel"}})
        result = start_prioritization_session(PROJECT, "S1", "MoSCoW")
        self.assertIn("# Prioritization session: S1", result)
        self.assertNotIn("Gut feel", result)
        self.assertNotIn("but 3.3 plans the technique", result)


# ---------------------------------------------------------------------------
# C2 — add_stakeholder_scores cross-checks the scorer. Never blocks.
# ---------------------------------------------------------------------------

class ParticipantCrossCheckTest(PrioritizationGovernanceBase):

    def _score(self, who):
        start_prioritization_session(PROJECT, "S1", "MoSCoW")
        return add_stakeholder_scores(PROJECT, "S1", who, "High", MOSCOW_SCORES)

    def test_an_unplanned_scorer_is_flagged_and_the_scores_are_still_recorded(self):
        plan_ba_governance(PROJECT, "High", '["PO"]',
                           prioritization_participants_json=TWO_PARTICIPANTS)
        result = self._score("Marketing Lead")
        self.assertIn("is not among the participants planned in 3.3", result)
        self.assertIn(BOTH, result)
        self.assertIn("✅ Scores for stakeholder", result)          # not a refusal
        self.assertIn("**Requirements scored:** 2", result)

    def test_a_planned_scorer_is_not_flagged_and_the_match_is_normalised(self):
        """One matcher, normalised on both sides: a producer that validates raw casing
        next to a consumer that matches normalised makes confident false claims."""
        plan_ba_governance(PROJECT, "High", '["PO"]',
                           prioritization_participants_json=TWO_PARTICIPANTS)
        result = self._score("  head of   RISK ")
        self.assertIn("✅ Scores for stakeholder", result)
        self.assertNotIn("is not among the participants planned in 3.3", result)

    def test_no_planned_participants_means_no_message(self):
        plan_ba_governance(PROJECT, "High", '["PO"]', prioritization_technique="WSJF")
        result = self._score("Marketing Lead")
        self.assertIn("✅ Scores for stakeholder", result)
        self.assertNotIn("is not among the participants planned in 3.3", result)

    def test_without_a_plan_nothing_is_added(self):
        result = self._score("Marketing Lead")
        self.assertIn("✅ Scores for stakeholder", result)
        self.assertNotIn("3.3", result)

    def test_the_stakeholder_influence_is_untouched(self):
        """`stakeholder_influence` weights the aggregation. It is out of scope for
        this seam and must not be derived from the plan."""
        plan_ba_governance(PROJECT, "High", '["PO"]',
                           prioritization_participants_json=TWO_PARTICIPANTS)
        self._score("Marketing Lead")
        path = os.path.join("governance_plans", "data", PROJECT,
                            f"{PROJECT}_prioritization.json")
        with open(path, encoding="utf-8") as f:
            session = json.load(f)["sessions"][0]
        self.assertEqual(session["stakeholder_influence"], {"Marketing Lead": "High"})

    def test_a_governance_section_of_the_wrong_type_does_not_raise(self):
        for bad in (None, "oops", ["Product Owner"], 7):
            with self.subTest(governance=bad):
                self._write_plan(bad)
                start_prioritization_session(PROJECT, "S_bad", "MoSCoW")
                result = add_stakeholder_scores(PROJECT, "S_bad", "Marketing Lead",
                                                "High", MOSCOW_SCORES)
                self.assertIn("✅ Scores for stakeholder", result)
                self.assertNotIn("is not among the participants planned in 3.3", result)

    def test_a_bare_string_where_the_participants_belong_is_not_split_per_character(self):
        """B3-3 finding 1 at this seam: `', '.join("PO")` is "P, O" — two invented
        planned scorers in the message the BA acts on."""
        self._write_plan({"project_criticality": "High",
                          "prioritization": {"participants": "Product Owner"}})
        result = self._score("Marketing Lead")
        self.assertIn("✅ Scores for stakeholder", result)
        self.assertNotIn("P, r, o", result)
        self.assertNotIn("is not among the participants planned in 3.3", result)


# ---------------------------------------------------------------------------
# C3 — the delivered report reconciles the planned approach with what happened
# ---------------------------------------------------------------------------

class ReportReconcilesParticipationTest(PrioritizationGovernanceBase):

    def _plan_everything(self, technique="MoSCoW"):
        plan_ba_governance(PROJECT, "High", '["PO"]',
                           prioritization_technique=technique,
                           prioritization_participants_json=TWO_PARTICIPANTS,
                           prioritization_criteria_json='["cost", "risk"]')

    def test_the_report_reconciles_participation(self):
        self._plan_everything()
        start_prioritization_session(PROJECT, "S1", "MoSCoW")
        add_stakeholder_scores(PROJECT, "S1", "Product Owner", "High", MOSCOW_SCORES)
        add_stakeholder_scores(PROJECT, "S1", "Lead Architect", "Medium", MOSCOW_SCORES)
        run_aggregation(PROJECT, "S1")
        report = save_prioritization_result(PROJECT, "S1")
        self.assertIn("## Planned approach (3.3)", report)
        self.assertIn("**Technique:** MoSCoW planned — MoSCoW used ✅", report)
        self.assertIn("**Criteria:** cost, risk", report)
        self.assertIn("1 of 2 planned participants scored", report)
        self.assertIn("Did not score: Head of Risk", report)
        self.assertIn("Scored without being planned: Lead Architect", report)

    def test_a_technique_mismatch_is_reconciled_not_hidden(self):
        """The header prints `**Method:** MoSCoW` already, so the whole claim lives in
        the "WSJF planned — MoSCoW used ⚠️" phrase."""
        self._plan_everything(technique="WSJF")
        report = self._finalised_report()
        self.assertIn("**Technique:** WSJF planned — MoSCoW used ⚠️", report)

    def test_full_participation_says_so_and_lists_nobody(self):
        self._plan_everything()
        start_prioritization_session(PROJECT, "S1", "MoSCoW")
        add_stakeholder_scores(PROJECT, "S1", "Product Owner", "High", MOSCOW_SCORES)
        add_stakeholder_scores(PROJECT, "S1", "head of risk", "High", MOSCOW_SCORES)
        run_aggregation(PROJECT, "S1")
        report = save_prioritization_result(PROJECT, "S1")
        self.assertIn("2 of 2 planned participants scored", report)
        self.assertNotIn("Did not score:", report)
        self.assertNotIn("Scored without being planned:", report)

    def test_criteria_alone_still_render_the_block(self):
        """The three parts of element .3 are independent: a plan that names only the
        criteria is a legitimate plan, and the report must not swallow it."""
        plan_ba_governance(PROJECT, "High", '["PO"]',
                           prioritization_criteria_json='["cost", "risk"]')
        report = self._finalised_report()
        self.assertIn("## Planned approach (3.3)", report)
        self.assertIn("**Criteria:** cost, risk", report)
        self.assertIn("**Technique:** not planned in 3.3", report)
        self.assertNotIn("planned participants scored", report)

    def test_the_block_is_absent_without_a_plan(self):
        report = self._finalised_report()
        self.assertIn("# Prioritization results: S1", report)       # it rendered
        self.assertNotIn("Planned approach (3.3)", report)
        self.assertNotIn("planned participants scored", report)

    def test_the_block_is_absent_when_nothing_of_element_3_is_planned(self):
        plan_ba_governance(PROJECT, "High", '["CFO", "Head of Risk"]')
        report = self._finalised_report()
        self.assertIn("# Prioritization results: S1", report)
        self.assertNotIn("Planned approach (3.3)", report)

    def test_a_governance_section_of_the_wrong_type_does_not_raise(self):
        for bad in (None, "oops", ["Product Owner"], 7):
            with self.subTest(governance=bad):
                self._write_plan(bad)
                report = self._finalised_report()
                self.assertIn("# Prioritization results: S1", report)
                self.assertNotIn("Planned approach (3.3)", report)
                # A fresh session for the next iteration of the loop.
                os.remove(os.path.join("governance_plans", "data", PROJECT,
                                       f"{PROJECT}_prioritization.json"))

    def test_a_bare_string_where_the_participants_belong_is_not_split_per_character(self):
        self._write_plan({"project_criticality": "High",
                          "prioritization": {"technique": "MoSCoW",
                                             "participants": "Product Owner"}})
        report = self._finalised_report()
        self.assertIn("## Planned approach (3.3)", report)          # it rendered
        self.assertNotIn("P, r, o", report)
        self.assertNotIn("planned participants scored", report)

    def test_the_scored_ids_and_priorities_are_unaffected(self):
        """The seam adds a paragraph. It must not change a single priority — that is
        what `method` and `stakeholder_influence` decide, and neither is derived."""
        self._plan_everything(technique="WSJF")
        report = self._finalised_report()
        self.assertIn("**Requirements updated:** 2", report)
        self.assertIn("### 🔴 Must (1)", report)
        self.assertIn("### 🟠 Should (1)", report)

    def test_the_typo_warning_still_lands_in_the_header(self):
        """The report inserts the "scored id matches no repository node" warning at a
        FIXED index in `lines`. A block added above it would push the header down and
        the warning would land inside that block instead."""
        self._plan_everything()
        start_prioritization_session(PROJECT, "S1", "MoSCoW")
        add_stakeholder_scores(PROJECT, "S1", "Product Owner", "High",
                               '[{"req_id": "FR-01", "score": "Must"}]')
        run_aggregation(PROJECT, "S1")
        report = save_prioritization_result(PROJECT, "S1")
        lines = report.splitlines()
        header_end = lines.index("**Requirements updated:** 0")
        warning = next(i for i, l in enumerate(lines) if "match no repository node" in l)
        self.assertEqual(warning, header_end + 1)


class RegistryBridgeTest(PrioritizationGovernanceBase):
    """3.3 plans ROLES; `stakeholder_id` is normally a PERSON. Both branch reviewers
    found this independently: an unbridged comparison warned on 100% of scorers on a
    correctly-planned project and wrote "0 of 2 planned participants scored" into the
    signed report while both of them had scored."""

    def _plan_roles(self):
        plan_ba_governance(PROJECT, "High", '["PO"]',
                           prioritization_technique="MoSCoW",
                           prioritization_participants_json=TWO_PARTICIPANTS)

    def test_a_person_scoring_under_their_planned_role_is_not_flagged(self):
        self._plan_roles()
        start_prioritization_session(PROJECT, "S1", "MoSCoW")
        result = add_stakeholder_scores(PROJECT, "S1", "Priya Nair", "High",
                                        MOSCOW_SCORES)
        self.assertIn("✅ Scores for stakeholder", result)
        self.assertNotIn("is not among the participants planned in 3.3", result)

    def test_the_report_counts_people_against_their_planned_roles(self):
        self._plan_roles()
        start_prioritization_session(PROJECT, "S1", "MoSCoW")
        add_stakeholder_scores(PROJECT, "S1", "Priya Nair", "High", MOSCOW_SCORES)
        add_stakeholder_scores(PROJECT, "S1", "Dana Cole", "High", MOSCOW_SCORES)
        run_aggregation(PROJECT, "S1")
        report = save_prioritization_result(PROJECT, "S1")
        self.assertIn("2 of 2 planned participants scored", report)
        self.assertNotIn("Did not score:", report)
        self.assertNotIn("Scored without being planned:", report)

    def test_a_person_whose_role_is_not_planned_is_still_reported(self):
        """The bridge must not blunt the check — it only removes false accusations."""
        self._plan_roles()
        start_prioritization_session(PROJECT, "S1", "MoSCoW")
        result = add_stakeholder_scores(PROJECT, "S1", "Mark Feld", "Medium",
                                        MOSCOW_SCORES)
        self.assertIn("is not among the participants planned in 3.3", result)


class NoRegistryTest(BaseMCPTest):
    """With nothing tying roles to names, a non-match means the two labels cannot be
    compared. Saying "not among the planned participants" would be a guess printed as
    a finding — so the check says nothing at all."""

    def setUp(self):
        super().setUp()
        init_traceability_repo(PROJECT, "Standard", REQS)

    def test_an_unmatched_scorer_is_not_accused_without_a_registry(self):
        plan_ba_governance(PROJECT, "High", '["PO"]',
                           prioritization_participants_json=TWO_PARTICIPANTS)
        start_prioritization_session(PROJECT, "S1", "MoSCoW")
        result = add_stakeholder_scores(PROJECT, "S1", "Priya Nair", "High",
                                        MOSCOW_SCORES)
        self.assertIn("✅ Scores for stakeholder", result)
        self.assertNotIn("is not among the participants planned in 3.3", result)

    def test_an_exact_role_match_still_works_without_a_registry(self):
        """The bridge only ADDS matches: a BA who types the planned role gets the same
        answer they always did, with no registry in the project."""
        plan_ba_governance(PROJECT, "High", '["PO"]',
                           prioritization_technique="MoSCoW",
                           prioritization_participants_json=TWO_PARTICIPANTS)
        start_prioritization_session(PROJECT, "S1", "MoSCoW")
        add_stakeholder_scores(PROJECT, "S1", "Product Owner", "High", MOSCOW_SCORES)
        run_aggregation(PROJECT, "S1")
        report = save_prioritization_result(PROJECT, "S1")
        self.assertIn("1 of 2 planned participants scored", report)
        self.assertIn("Did not score: Head of Risk", report)


if __name__ == "__main__":
    unittest.main()
