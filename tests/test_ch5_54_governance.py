"""tests/test_ch5_54_governance.py — Seam B: the 3.3 governance plan reaches the 5.4
CR audit trail (B3-2).

`resolve_cr` RETURNS a short status summary; the CR Decision Record goes to
`save_artifact`, which conftest mocks suite-wide. Verified by probing the tool before
a single assertion was written — the fourth tool in this feature whose return value is
not its delivered document, and the rule is not uniform in this codebase
(`prepare_approval_package` DOES return its package).

Two traps this file deliberately avoids, both live in the current output:
  - `resolve_cr` already prints "⚠️ Update the requirements' content ..." on every
    Approved CR, so `assertIn("⚠️", output)` holds with the whole feature deleted.
  - It already prints `**Decided by:** <name>` twice, so asserting the decider's name
    proves nothing about the cross-check. The assertions below name the WARNING text
    and the planned list instead.

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

from skills.common import ba_plan_path, data_path, stakeholder_registry_path
from skills.planning_mcp import plan_ba_governance
from skills.requirements_assess_changes_mcp import (
    open_cr, run_cr_impact, score_cr, resolve_cr)
from skills.requirements_traceability_mcp import init_traceability_repo

PROJECT = "gov54"

REQS = json.dumps([
    {"id": "FR-001", "title": "Login", "type": "functional"},
])

# Two planned authorities everywhere the join is under test: `', '.join(["CFO"])` is
# indistinguishable from the raw string "CFO", so a one-element fixture cannot tell a
# rendered list from a rendered scalar.
TWO_DECIDERS = '["CFO", "Head of Risk"]'
BOTH = "CFO, Head of Risk"


class CRGovernanceBase(BaseMCPTest):
    """A scored CR-001, ready for `resolve_cr`."""

    REGISTRY = [
        {"name": "Alice Chen", "role": "CFO"},
        {"name": "Dana Cole", "role": "Head of Risk"},
        {"name": "Mark Feld", "role": "Marketing Lead"},
    ]

    def setUp(self):
        super().setUp()
        init_traceability_repo(PROJECT, "Standard", REQS)
        open_cr(PROJECT, "CR-001", "Add SSO", "Customer asked for SSO", "Sales",
                "new_requirement", "standard", '["FR-001"]')
        run_cr_impact(PROJECT, "CR-001")
        score_cr(PROJECT, "CR-001", "High", "Medium")
        # A real project has a registry: 3.2 seeds it, 4.2 maintains it, and it is
        # what lets a `decided_by` NAME match a planned ROLE. Without one the check
        # reports that it cannot tell and stays silent (`NoRegistryTest`).
        self._seed_registry(self.REGISTRY)

    def _seed_registry(self, rows):
        path = stakeholder_registry_path(PROJECT)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"project": PROJECT, "stakeholders": rows}, f)

    def _resolve(self, decision="Approved", decided_by="CFO", rationale="agreed",
                 **kwargs):
        """(record, output) — the CR Decision Record, and the tool's return value."""
        with patch("skills.requirements_assess_changes_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "\n\n✅ Artifact saved: `x.md`"
            output = resolve_cr(PROJECT, "CR-001", decision, decided_by, rationale,
                                **kwargs)
            record = mock_sa.call_args[0][0] if mock_sa.call_args else ""
        return record, output

    def _write_plan(self, governance):
        path = ba_plan_path(PROJECT)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"project_id": PROJECT, "governance": governance}, f)


# ---------------------------------------------------------------------------
# B1 — the step-4 block names the planned authorities
#
# NOTE: the sentence lives in `score_cr`, not in `run_cr_impact` (which points at
# score_cr and says nothing about a decision). See the ledger finding for Task 6.
# ---------------------------------------------------------------------------

class StepFourNamesTheAuthoritiesTest(CRGovernanceBase):

    def test_the_step_four_block_names_the_planned_decision_makers(self):
        plan_ba_governance(PROJECT, "High", TWO_DECIDERS)
        result = score_cr(PROJECT, "CR-001", "High", "Medium")
        self.assertIn(BOTH, result)

    def test_without_a_plan_the_wording_is_unchanged(self):
        """Both branches contain "authorized stakeholder", so asserting THAT proves
        nothing about which one ran. The parenthetical exists only in the no-plan
        branch, and the "names:" clause only in the planned one."""
        result = score_cr(PROJECT, "CR-001", "High", "Medium")
        self.assertIn("(from governance 3.3)", result)
        self.assertNotIn("the 3.3 governance plan names", result)

    def test_a_damaged_plan_leaves_the_block_intact(self):
        plan_ba_governance(PROJECT, "High", TWO_DECIDERS)
        with open(ba_plan_path(PROJECT), "w", encoding="utf-8") as f:
            f.write("{ not json")
        result = score_cr(PROJECT, "CR-001", "High", "Medium")
        self.assertIn("Next step — Step 4", result)
        self.assertIn("(from governance 3.3)", result)


# ---------------------------------------------------------------------------
# B2 — the `decided_by` cross-check, in the output AND in the record
# ---------------------------------------------------------------------------

class DecidedByCrossCheckTest(CRGovernanceBase):

    def test_an_unplanned_decider_is_flagged_in_the_tool_output(self):
        plan_ba_governance(PROJECT, "High", TWO_DECIDERS)
        _record, output = self._resolve(decided_by="Marketing Lead")
        self.assertIn("not among the planned decision makers", output)
        self.assertIn(BOTH, output)

    def test_an_unplanned_decider_is_flagged_in_the_decision_record(self):
        plan_ba_governance(PROJECT, "High", TWO_DECIDERS)
        record, _output = self._resolve(decided_by="Marketing Lead")
        self.assertIn("## Governance (3.3)", record)
        self.assertIn(f"**Planned decision authority:** {BOTH}", record)
        self.assertIn("is not among them", record)

    def test_the_record_does_not_say_the_planned_authority_decided(self):
        """FOUND BY THE LIVE RUN, by reading the rendered record rather than grepping it.

        The warning sat directly under `**Planned decision authority:** A, B` and read
        "... is not among them — recorded as decided by them regardless". The pronoun
        resolves to the PLANNED authorities, so the sentence states the opposite of the
        fact: the decision was recorded as made by the unplanned person. In an audit
        document that is not a wording nit — the header three lines up says
        `**Decided by:** Marketing Lead`, and the two contradict each other.
        """
        plan_ba_governance(PROJECT, "High", TWO_DECIDERS)
        record, _output = self._resolve(decided_by="Marketing Lead")
        self.assertIn("is not among them", record)          # the flag still fires
        self.assertNotIn("decided by them", record)
        # The record must name WHO it credits, and it is the person, not the plan.
        self.assertIn("`Marketing Lead`", record)

    def test_a_planned_decider_is_not_flagged(self):
        """The match normalises BOTH sides through the one shared matcher — a producer
        that validates raw casing next to a consumer that matches normalised makes
        confident false claims in a signed document."""
        plan_ba_governance(PROJECT, "High", TWO_DECIDERS)
        record, output = self._resolve(decided_by="  head of   RISK ")
        # Positive companion: the block WAS rendered, so the two assertNotIns below
        # cannot be satisfied by an empty string.
        self.assertIn("## Governance (3.3)", record)
        self.assertIn(BOTH, record)
        self.assertNotIn("is not among them", record)
        self.assertNotIn("not among the planned decision makers", output)

    def test_decided_by_is_never_rewritten(self):
        plan_ba_governance(PROJECT, "High", TWO_DECIDERS)
        self._resolve(decided_by="Marketing Lead")
        path = data_path(PROJECT, f"{PROJECT}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            repo = json.load(f)
        cr = next(n for n in repo["requirements"] if n["id"] == "CR-001")
        self.assertEqual(cr["decision"]["decided_by"], "Marketing Lead")
        resolved = [h for h in repo["history"] if h.get("action") == "cr_resolved"]
        self.assertEqual([h["decided_by"] for h in resolved], ["Marketing Lead"])


# ---------------------------------------------------------------------------
# B3 — the escalation path in the record, offered on Deferred / Rejected
# ---------------------------------------------------------------------------

class EscalationPathTest(CRGovernanceBase):

    def test_a_declared_escalation_path_is_labelled_as_declared(self):
        plan_ba_governance(PROJECT, "High", TWO_DECIDERS,
                           escalation_path="BA → CRO → Board")
        record, _output = self._resolve()
        self.assertIn("**Escalation path:** BA → CRO → Board", record)
        self.assertIn("declared in 3.3", record)

    def test_a_template_escalation_path_is_labelled_as_the_template(self):
        """The source label is read from the plan, never hardcoded: a document that
        calls a generated default "declared" attributes a decision to a person who
        never made it."""
        plan_ba_governance(PROJECT, "High", TWO_DECIDERS)
        record, _output = self._resolve()
        self.assertIn("**Escalation path:** BA → PM → Steering Committee", record)
        self.assertIn("from the High template", record)
        self.assertNotIn("declared in 3.3", record)

    def test_a_deferred_cr_offers_the_escalation_path_in_the_output(self):
        plan_ba_governance(PROJECT, "High", TWO_DECIDERS,
                           escalation_path="BA → CRO → Board")
        _record, output = self._resolve(decision="Deferred", rationale="next quarter")
        self.assertIn("escalation path", output)
        self.assertIn("BA → CRO → Board", output)

    def test_a_rejected_cr_offers_the_escalation_path_in_the_output(self):
        plan_ba_governance(PROJECT, "High", TWO_DECIDERS,
                           escalation_path="BA → CRO → Board")
        _record, output = self._resolve(decision="Rejected", rationale="out of scope")
        self.assertIn("escalation path", output)
        self.assertIn("BA → CRO → Board", output)

    def test_an_approved_cr_records_the_escalation_but_does_not_offer_it(self):
        """Escalation is the next step only where the requester lost. Offering it on
        an Approved CR is noise on the one output the BA reads every time."""
        plan_ba_governance(PROJECT, "High", TWO_DECIDERS,
                           escalation_path="BA → CRO → Board")
        record, output = self._resolve()
        self.assertIn("BA → CRO → Board", record)
        self.assertNotIn("BA → CRO → Board", output)
        self.assertNotIn("escalation path", output)


# ---------------------------------------------------------------------------
# B4 — no plan, and plans of the wrong shape. Chapter 3 loads in EVERY phase, so an
# AttributeError here is a protocol error in every session, not a 5.4 bug.
# ---------------------------------------------------------------------------

class NoPlanAndDamagedPlanTest(CRGovernanceBase):

    def test_without_a_plan_nothing_is_added_anywhere(self):
        record, output = self._resolve(decision="Deferred", decided_by="Marketing Lead",
                                       rationale="next quarter")
        self.assertIn("# CR Decision Record: CR-001", record)   # the record rendered
        self.assertNotIn("Governance (3.3)", record)
        self.assertNotIn("Escalation path", record)
        self.assertIn("CR CR-001 — Deferred", output)           # the output rendered
        self.assertNotIn("escalation path", output)
        self.assertNotIn("not among the planned decision makers", output)

    def test_a_governance_section_of_the_wrong_type_does_not_raise(self):
        for bad in (None, "oops", ["CFO"], 7):
            with self.subTest(governance=bad):
                self._write_plan(bad)
                record, output = self._resolve(decided_by="Marketing Lead")
                self.assertIn("# CR Decision Record: CR-001", record)
                self.assertIn("CR CR-001 — Approved", output)
                self.assertNotIn("Governance (3.3)", record)

    def test_a_bare_string_where_the_deciders_belong_is_not_rendered_per_character(self):
        """B3-3 finding 1 at this seam: `', '.join("CFO")` is "C, F, O" — three
        invented authorities in a document that goes into the audit trail."""
        self._write_plan({"project_criticality": "High", "decision_makers": "CFO"})
        record, _output = self._resolve(decided_by="Marketing Lead")
        self.assertIn("# CR Decision Record: CR-001", record)
        self.assertNotIn("C, F, O", record)
        self.assertNotIn("Planned decision authority", record)

    def test_a_damaged_plan_does_not_crash_the_tool(self):
        plan_ba_governance(PROJECT, "High", TWO_DECIDERS)
        with open(ba_plan_path(PROJECT), "w", encoding="utf-8") as f:
            f.write("{ not json")
        record, output = self._resolve()
        self.assertIn("# CR Decision Record: CR-001", record)
        self.assertIn("CR CR-001 — Approved", output)
        self.assertNotIn("Governance (3.3)", record)


class RegistryBridgeTest(CRGovernanceBase):
    """3.3 plans ROLES; `decided_by` is normally a PERSON. Both branch reviewers found
    this: without a bridge the CR Decision Record reported the actual CFO as deciding
    outside their authority."""

    def test_a_person_deciding_under_their_planned_role_is_not_flagged(self):
        plan_ba_governance(PROJECT, "High", TWO_DECIDERS)
        record, output = self._resolve(decided_by="Alice Chen")
        self.assertIn("## Governance (3.3)", record)      # the block IS rendered...
        self.assertNotIn("is not among them", record)     # ...without an accusation
        self.assertNotIn("not among the planned decision makers", output)

    def test_a_person_outside_every_planned_role_is_still_flagged(self):
        plan_ba_governance(PROJECT, "High", TWO_DECIDERS)
        record, _output = self._resolve(decided_by="Mark Feld")
        self.assertIn("is not among them", record)


class NoRegistryTest(BaseMCPTest):
    """With no registry, a planned ROLE and a typed NAME cannot be compared. The audit
    record must not print that guess as a governance breach."""

    def setUp(self):
        super().setUp()
        init_traceability_repo(PROJECT, "Standard", REQS)
        open_cr(PROJECT, "CR-001", "Add SSO", "Customer asked for SSO", "Sales",
                "new_requirement", "standard", '["FR-001"]')
        run_cr_impact(PROJECT, "CR-001")
        score_cr(PROJECT, "CR-001", "High", "Medium")

    def test_an_unmatched_decider_is_not_accused(self):
        plan_ba_governance(PROJECT, "High", TWO_DECIDERS)
        with patch("skills.requirements_assess_changes_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = ""
            output = resolve_cr(PROJECT, "CR-001", "Approved", "Alice Chen", "agreed")
            record = mock_sa.call_args[0][0]
        self.assertIn("## Governance (3.3)", record)
        self.assertNotIn("is not among them", record)
        self.assertNotIn("not among the planned decision makers", output)

    def test_an_exact_role_match_still_fires_without_a_registry(self):
        """The bridge only ADDS matches — a BA typing the planned role is unaffected."""
        plan_ba_governance(PROJECT, "High", TWO_DECIDERS)
        with patch("skills.requirements_assess_changes_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = ""
            resolve_cr(PROJECT, "CR-001", "Approved", "CFO", "agreed")
            record = mock_sa.call_args[0][0]
        self.assertIn(f"**Planned decision authority:** {BOTH}", record)
        self.assertNotIn("is not among them", record)


class DamagedPlanIsReportedTest(CRGovernanceBase):
    """`load_ba_plan`'s contract says the caller must SHOW the warning. A corrupt plan
    silently disabling every cross-check leaves an audit trail identical to a project
    that never planned governance."""

    def test_the_tool_says_the_plan_could_not_be_read(self):
        plan_ba_governance(PROJECT, "High", TWO_DECIDERS)
        with open(ba_plan_path(PROJECT), "w", encoding="utf-8") as f:
            f.write("{ not json")
        _record, output = self._resolve(decided_by="Mark Feld")
        self.assertIn("прочитать его не удалось", output)

    def test_the_decision_record_itself_stays_a_statement_about_the_cr(self):
        """The warning belongs in the reply, not in the signed record — that document
        is about the change request, not about the platform's file system."""
        plan_ba_governance(PROJECT, "High", TWO_DECIDERS)
        with open(ba_plan_path(PROJECT), "w", encoding="utf-8") as f:
            f.write("{ not json")
        record, _output = self._resolve(decided_by="Mark Feld")
        self.assertIn("# CR Decision Record", record)
        self.assertNotIn("прочитать его не удалось", record)


if __name__ == "__main__":
    unittest.main()
