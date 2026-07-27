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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import setup_mocks, BaseMCPTest

setup_mocks()

from skills.common import ba_plan_path
from skills.planning_mcp import plan_ba_governance
from skills.requirements_approve_mcp import prepare_approval_package
from skills.requirements_traceability_mcp import init_traceability_repo

PROJECT = "gov55"

REQS = json.dumps([
    {"id": "FR-001", "title": "Login", "type": "functional"},
    {"id": "FR-002", "title": "Logout", "type": "functional"},
])


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


if __name__ == "__main__":
    unittest.main()
