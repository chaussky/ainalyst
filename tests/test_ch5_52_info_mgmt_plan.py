"""tests/test_ch5_52_info_mgmt_plan.py — 5.2 consumes the 3.4 plan (B3-3)."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import setup_mocks, BaseMCPTest

setup_mocks()

from skills.common import ba_plan_path
from skills.requirements_maintain_mcp import check_requirements_health, _repo_path

PROJECT = "b33_health"


def _write_plan(project_id: str, info_mgmt: dict):
    path = ba_plan_path(project_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"project": project_id, "information_management": info_mgmt}, f)


def _write_repo(project_id: str, requirements: list):
    path = _repo_path(project_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"project": project_id, "requirements": requirements, "links": []}, f)


BARE_REQ = {"id": "FR-001", "type": "functional", "title": "Login",
            "status": "confirmed", "version": "1.0", "added": "2026-07-20"}


class TestHealthUsesThePlannedAttributeSet(BaseMCPTest):

    def test_without_a_plan_the_report_is_unchanged(self):
        """The single strongest guarantee of this feature: no plan, no drift.
        Not one new line either — the header names the audited set only when a
        plan actually selected one."""
        _write_repo(PROJECT, [dict(BARE_REQ)])
        result = check_requirements_health(PROJECT)
        self.assertIn("🟡 No owner", result)
        self.assertIn("without an owner", result)      # legacy advice wording
        self.assertNotIn("Audited attributes", result)

    def test_minimum_preset_stops_demanding_an_owner(self):
        """Asserted on the DEMAND, not on the word: the 🟡 table header and the
        healthy-block sentence both contain "owner" in any report, so
        assertNotIn("owner") would fail for a reason that has nothing to do
        with this feature."""
        _write_repo(PROJECT, [dict(BARE_REQ, source="Interview 21.03")])
        _write_plan(PROJECT, {"attributes": {"preset": "Minimum", "additional": []}})
        result = check_requirements_health(PROJECT)
        self.assertNotIn("No owner", result)
        self.assertNotIn("without an owner", result)
        self.assertNotIn("Attributes not filled in", result)
        self.assertIn("preset Minimum", result)

    def test_full_preset_flags_attributes_nobody_checked_before(self):
        _write_repo(PROJECT, [dict(BARE_REQ, owner="PO", source="Interview")])
        _write_plan(PROJECT, {"attributes": {"preset": "Full", "additional": []}})
        result = check_requirements_health(PROJECT)
        self.assertIn("complexity", result)
        self.assertIn("reuse_scope", result)

    def test_missing_attributes_are_one_line_not_one_line_each(self):
        """A Full preset on a bare requirement must not push the real 🔴 rows out of
        the report with nine separate lines."""
        _write_repo(PROJECT, [dict(BARE_REQ)])
        _write_plan(PROJECT, {"attributes": {"preset": "Full", "additional": []}})
        result = check_requirements_health(PROJECT)
        self.assertEqual(result.count("Attributes not filled in"), 1)

    def test_reuse_candidate_false_counts_as_filled_in(self):
        """False is a legitimate answer — "not a reuse candidate" is not a gap.
        Asserted on the gap line, not on the attribute name: the header lists
        every audited attribute, `reuse_candidate` among them."""
        _write_repo(PROJECT, [dict(BARE_REQ, owner="PO", source="Interview",
                                   priority="High", stability="Stable",
                                   reuse_candidate=False)])
        _write_plan(PROJECT, {"attributes": {"preset": "Standard", "additional": []}})
        result = check_requirements_health(PROJECT)
        self.assertNotIn("Attributes not filled in", result)

    def test_advice_block_names_the_unfilled_attributes(self):
        """Was going to be: 🟡 rows in the table and NOTHING in "Recommended
        actions", because the counter there looks for the substring "owner".
        A document that flags requirements and then advises nothing about
        them contradicts itself."""
        _write_repo(PROJECT, [dict(BARE_REQ, owner="PO", source="Interview",
                                   priority="High", stability="Stable",
                                   reuse_candidate=True)])
        _write_plan(PROJECT, {"attributes": {"preset": "Full", "additional": []}})
        result = check_requirements_health(PROJECT)
        self.assertIn("unfilled attributes", result)
        self.assertIn("complexity", result.split("Recommended actions")[1])

    def test_report_names_the_audited_set_and_its_source(self):
        _write_repo(PROJECT, [dict(BARE_REQ)])
        _write_plan(PROJECT, {"attributes": {"preset": "Standard", "additional": []}})
        result = check_requirements_health(PROJECT)
        self.assertIn("Audited attributes", result)
        self.assertIn("3.4 plan", result)

    def test_corrupt_plan_degrades_to_default_and_warns(self):
        """A damaged chapter-3 file must not kill a chapter-5 tool."""
        _write_repo(PROJECT, [dict(BARE_REQ)])
        path = ba_plan_path(PROJECT)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("{broken")
        result = check_requirements_health(PROJECT)
        self.assertIn("⚠️", result)
        self.assertIn("🟡 No owner", result)


from skills.requirements_maintain_mcp import find_reusable_requirements

REUSABLE = {"id": "BR-001", "type": "business", "title": "KYC check",
            "status": "approved", "version": "1.0", "added": "2026-07-20",
            "reuse_candidate": True, "reuse_scope": "enterprise", "owner": "PO"}


class TestReuseUsesThePlannedScope(BaseMCPTest):

    def test_planned_scope_becomes_the_default(self):
        _write_repo(PROJECT, [dict(REUSABLE)])
        _write_plan(PROJECT, {"reuse": {"target_scope": "division",
                                        "repository": "", "categories": []}})
        result = find_reusable_requirements(PROJECT)
        self.assertIn("**Minimum scope:** division", result)
        self.assertIn("3.4 plan", result)

    def test_explicit_scope_always_wins_over_the_plan(self):
        """Silently overriding an explicit BA input is worse than having no feature —
        the reason the governance wiring was refused in an earlier pass."""
        _write_repo(PROJECT, [dict(REUSABLE)])
        _write_plan(PROJECT, {"reuse": {"target_scope": "division",
                                        "repository": "", "categories": []}})
        result = find_reusable_requirements(PROJECT, min_reuse_scope="initiative")
        self.assertIn("**Minimum scope:** initiative", result)
        self.assertNotIn("3.4 plan", result)

    def test_without_a_plan_the_default_is_still_initiative(self):
        _write_repo(PROJECT, [dict(REUSABLE)])
        result = find_reusable_requirements(PROJECT)
        self.assertIn("**Minimum scope:** initiative", result)
        self.assertNotIn("3.4 plan", result)

    def test_planned_repository_is_named_instead_of_generic_advice(self):
        _write_repo(PROJECT, [dict(REUSABLE)])
        _write_plan(PROJECT, {"reuse": {"target_scope": "", "repository": "REQ-LIB space",
                                        "categories": []}})
        result = find_reusable_requirements(PROJECT)
        self.assertIn("REQ-LIB space", result)

    def test_planned_categories_are_rendered_as_a_checklist(self):
        _write_repo(PROJECT, [dict(REUSABLE)])
        _write_plan(PROJECT, {"reuse": {"target_scope": "", "repository": "",
                                        "categories": ["regulatory", "business rules"]}})
        result = find_reusable_requirements(PROJECT)
        self.assertIn("regulatory", result)
        self.assertIn("business rules", result)

    def test_empty_result_advice_names_the_planned_repository(self):
        _write_repo(PROJECT, [])
        _write_plan(PROJECT, {"reuse": {"target_scope": "", "repository": "REQ-LIB space",
                                        "categories": []}})
        result = find_reusable_requirements(PROJECT)
        self.assertIn("REQ-LIB space", result)

    def test_corrupt_plan_does_not_kill_the_reuse_search(self):
        _write_repo(PROJECT, [dict(REUSABLE)])
        path = ba_plan_path(PROJECT)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("{broken")
        result = find_reusable_requirements(PROJECT)
        self.assertIn("⚠️", result)
        self.assertIn("**Minimum scope:** initiative", result)


if __name__ == "__main__":
    unittest.main()
