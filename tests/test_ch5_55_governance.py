"""tests/test_ch5_55_governance.py — Seam A: the 3.3 governance plan reaches the two
5.5 documents (B3-2).

`prepare_approval_package` RETURNS the rendered package (verified by probing it, not
by trusting the docstring — the sibling `save_ba_plan` returns a status message
instead, and asserting on that passed vacuously earlier in this feature).

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

from skills.common import ba_plan_path
from skills.planning_mcp import plan_ba_governance
from skills.requirements_approve_mcp import (
    prepare_approval_package, record_approval_decision,
    create_requirements_baseline)
from skills.requirements_traceability_mcp import init_traceability_repo

PROJECT = "gov55"

REQS = json.dumps([
    {"id": "FR-001", "title": "Login", "type": "functional"},
    {"id": "FR-002", "title": "Logout", "type": "functional"},
])


def _record_text(*args, **kwargs) -> str:
    """The Approval Record markdown, captured from the writer.

    `create_requirements_baseline` returns a SUMMARY — its own docstring says "the
    return value is not it". The record goes to save_artifact, which conftest mocks
    suite-wide. This is the third tool in this feature whose return value is not the
    delivered document, and the rule is not uniform (prepare_approval_package DOES
    return its package), so it is verified per tool rather than assumed.
    """
    with patch("skills.requirements_approve_mcp.save_artifact") as mock_sa:
        mock_sa.return_value = "\n\n✅ Artifact saved: `x.md`"
        summary = create_requirements_baseline(*args, **kwargs)
        record = mock_sa.call_args[0][0] if mock_sa.call_args else ""
    return record, summary


class GovernanceInThePackageTest(BaseMCPTest):

    def setUp(self):
        super().setUp()
        init_traceability_repo(PROJECT, "Standard", REQS)

    def _prepare(self, package_id="APKG-001", approach="predictive", **kw):
        return prepare_approval_package(
            PROJECT, package_id, "Auth", '["FR-001", "FR-002"]',
            approach=approach, **kw)

    # --- no plan: the tool says LESS, it does not conclude --------------------

    def test_without_a_plan_the_dead_pointer_is_gone_and_nothing_replaces_it(self):
        """Silent degradation is allowed only if the tool says LESS. A dash in a
        signed document is a conclusion the BA never supplied."""
        result = self._prepare()
        self.assertIn("Instructions for stakeholders", result)   # the block IS rendered
        self.assertNotIn("per the project's governance plan", result)
        self.assertNotIn("Response deadline", result)
        self.assertNotIn("Approval authority", result)

    def test_the_tool_never_refuses_for_a_missing_plan(self):
        """It works without a plan today; refusing would be a regression for every
        existing project. This differs from B3-1's `approach`, which was ALREADY a
        required parameter, so refusing there took away nothing that worked."""
        result = self._prepare()
        self.assertIn("Approval Package: Auth", result)
        self.assertNotIn("❌", result)

    # --- the deadline --------------------------------------------------------

    def test_the_planned_sla_is_printed_with_its_source(self):
        plan_ba_governance(PROJECT, "High", '["CFO", "Head of Risk"]',
                           approval_sla_days=5)
        result = self._prepare()
        self.assertIn("5 business days", result)
        self.assertIn("3.3 governance plan", result)

    def test_the_sla_is_printed_on_the_agile_branch_too(self):
        """`approval_sla_days` answers "the timing for the approvals" regardless of
        ceremony — a sprint package has a response window as well."""
        plan_ba_governance(PROJECT, "High", '["CFO"]', approval_sla_days=3)
        result = self._prepare(approach="agile", sprint_number="7")
        self.assertIn("Sprint Planning", result)      # it IS the agile block...
        self.assertIn("3 business days", result)      # ...and it carries the deadline

    def test_the_event_note_is_printed_verbatim(self):
        plan_ba_governance(PROJECT, "High", '["CFO"]',
                           approval_timing_note="to the monthly CAB")
        self.assertIn("to the monthly CAB", self._prepare())

    def test_the_sla_and_the_note_are_both_printed(self):
        plan_ba_governance(PROJECT, "High", '["CFO"]', approval_sla_days=5,
                           approval_timing_note="to the monthly CAB")
        result = self._prepare()
        self.assertIn("5 business days", result)
        self.assertIn("to the monthly CAB", result)

    def test_a_cleared_sla_removes_the_sentence_again(self):
        plan_ba_governance(PROJECT, "High", '["CFO"]', approval_sla_days=5)
        plan_ba_governance(PROJECT, approval_sla_days=0)
        result = self._prepare()
        self.assertIn("Instructions for stakeholders", result)
        self.assertNotIn("Response deadline", result)

    # --- the approvers -------------------------------------------------------

    def test_the_approvers_are_named(self):
        plan_ba_governance(PROJECT, "High", '["CFO", "Head of Risk"]')
        result = self._prepare()
        self.assertIn("Approval authority", result)
        self.assertIn("CFO, Head of Risk", result)
        self.assertIn("from the High template", result)

    def test_a_declared_process_is_labelled_as_the_bas(self):
        plan_ba_governance(PROJECT, "High", '["CFO"]',
                           approval_process="CFO signs; Board informed")
        result = self._prepare()
        self.assertIn("CFO signs; Board informed", result)
        self.assertIn("declared in 3.3", result)

    def test_the_authority_block_appears_on_the_agile_branch_too(self):
        plan_ba_governance(PROJECT, "High", '["CFO"]')
        result = self._prepare(approach="agile")
        self.assertIn("Approval authority", result)

    # --- damaged plan --------------------------------------------------------

    def test_a_damaged_plan_warns_and_continues(self):
        plan_ba_governance(PROJECT, "High", '["CFO"]', approval_sla_days=5)
        with open(ba_plan_path(PROJECT), "w", encoding="utf-8") as f:
            f.write("{ not json")
        result = self._prepare()
        self.assertIn("Approval Package: Auth", result)
        self.assertNotIn("5 business days", result)
        self.assertIn("could not be read", result)

    def test_a_governance_section_of_the_wrong_shape_does_not_crash(self):
        plan_ba_governance(PROJECT, "High", '["CFO"]')
        path = ba_plan_path(PROJECT)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["governance"] = "oops"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        result = self._prepare()
        self.assertIn("Approval Package: Auth", result)
        self.assertNotIn("Approval authority", result)

    def test_a_null_governance_section_does_not_crash(self):
        """Chapter 3 loads in EVERY phase, so an AttributeError here is a protocol
        error in every session (B3-1 finding 9)."""
        plan_ba_governance(PROJECT, "High", '["CFO"]')
        path = ba_plan_path(PROJECT)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["governance"] = None
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        self.assertIn("Approval Package: Auth", self._prepare())


class AuthorityCrossCheckTest(BaseMCPTest):
    """BABOK 3.3 .1 — is the person recording a decision one of the planned
    approvers? The check must never touch the RACI it reads."""

    def setUp(self):
        super().setUp()
        init_traceability_repo(PROJECT, "Standard", REQS)
        plan_ba_governance(PROJECT, "High", '["CFO", "Head of Risk"]')
        prepare_approval_package(PROJECT, "APKG-001", "Auth",
                                 '["FR-001", "FR-002"]', approach="predictive")

    def _record(self, name, raci, decision="approved", **kw):
        return record_approval_decision(PROJECT, "APKG-001", name, raci, decision, **kw)

    def test_an_unplanned_accountable_is_flagged_by_name(self):
        result = self._record("Marketing Lead", "accountable")
        self.assertIn("⚠️", result)
        self.assertIn("Marketing Lead", result)
        self.assertIn("CFO, Head of Risk", result)

    def test_a_planned_accountable_is_not_flagged(self):
        self.assertNotIn("not among the planned",
                         self._record("CFO", "accountable"))

    def test_a_planned_responsible_is_not_flagged(self):
        self.assertNotIn("not among the planned",
                         self._record("Head of Risk", "responsible"))

    def test_the_match_is_case_and_space_insensitive(self):
        self.assertNotIn("not among the planned",
                         self._record("  head of   RISK ", "responsible"))

    def test_a_consulted_stakeholder_is_never_flagged(self):
        """THE HEART OF THIS FEATURE. A reviewer is legitimately not a decision
        maker; the EXPLICIT raci is the GUARD for the cross-check, not its victim.
        Warning here would re-create the conflict that got B3-2 declined the first
        time round — raci decides whether a rejection HARD BLOCKS the baseline, so
        it is read, never derived."""
        result = self._record("Marketing Lead", "consulted")
        self.assertIn("Marketing Lead", result)          # the decision IS recorded...
        self.assertNotIn("not among the planned", result)  # ...silently

    def test_the_cross_check_does_not_demote_an_ar_rejection(self):
        """The hard block must survive the cross-check untouched."""
        self._record("Marketing Lead", "accountable", decision="rejected",
                     rejection_reason="out of scope")
        _record, summary = _record_text(PROJECT, "APKG-001", "v1.0", "CFO")
        self.assertIn("❌", summary)
        self.assertIn("NOT lifted by `force`", summary)

    def test_nothing_is_flagged_when_no_authority_is_planned(self):
        os.remove(ba_plan_path(PROJECT))
        result = self._record("Anyone", "accountable")
        self.assertIn("Anyone", result)
        self.assertNotIn("not among the planned", result)


class ApprovalRecordGovernanceTest(BaseMCPTest):

    def setUp(self):
        super().setUp()
        init_traceability_repo(PROJECT, "Standard", REQS)
        plan_ba_governance(PROJECT, "High", '["CFO", "Head of Risk"]')
        prepare_approval_package(PROJECT, "APKG-001", "Auth",
                                 '["FR-001", "FR-002"]', approach="predictive")

    def test_the_record_names_who_responded_and_who_did_not(self):
        record_approval_decision(PROJECT, "APKG-001", "CFO", "accountable", "approved")
        record, _summary = _record_text(PROJECT, "APKG-001", "v1.0", "CFO")
        self.assertIn("Planned approval authority", record)
        self.assertIn("CFO, Head of Risk", record)
        self.assertIn("No decision recorded from: Head of Risk", record)

    def test_the_record_says_so_when_every_authority_responded(self):
        record_approval_decision(PROJECT, "APKG-001", "CFO", "accountable", "approved")
        record_approval_decision(PROJECT, "APKG-001", "Head of Risk",
                                 "responsible", "approved")
        record, _summary = _record_text(PROJECT, "APKG-001", "v1.0", "CFO")
        self.assertIn("Planned approval authority", record)
        self.assertNotIn("No decision recorded from", record)

    def test_an_unplanned_responder_does_not_count_as_a_planned_one(self):
        """The `silent` list alone cannot prove this — it is computed by matching the
        PLANNED names against the responders, so it reads the same whether or not the
        responder list was filtered. Mutation testing showed exactly that: dropping
        the filter left this test green. The "Responded" line is the evidence."""
        record_approval_decision(PROJECT, "APKG-001", "Marketing Lead",
                                 "accountable", "approved")
        record, _summary = _record_text(PROJECT, "APKG-001", "v1.0", "CFO", force=True)
        self.assertIn("**Responded:** nobody.", record)
        self.assertIn("No decision recorded from: CFO, Head of Risk", record)

    def test_the_block_is_absent_without_a_plan(self):
        record_approval_decision(PROJECT, "APKG-001", "CFO", "accountable", "approved")
        os.remove(ba_plan_path(PROJECT))
        record, _summary = _record_text(PROJECT, "APKG-001", "v1.0", "CFO")
        self.assertIn("Approval Record", record)      # the record IS rendered...
        self.assertNotIn("Planned approval authority", record)   # ...without the block


if __name__ == "__main__":
    unittest.main()
