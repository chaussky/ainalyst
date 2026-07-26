"""tests/test_ch5_52_info_mgmt_plan.py — 5.2 consumes the 3.4 plan (B3-3)."""

import json
import os
import sys
import unittest
from datetime import date

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


# `added` is relative to today on purpose: a literal date made the staleness check fire
# once the fixture aged past 30 days, so an unrelated 🟡 row appeared and the tests that
# count action-list entries would have gone red on a calendar date, not on a code change.
_FRESH = str(date.today())

BARE_REQ = {"id": "FR-001", "type": "functional", "title": "Login",
            "status": "confirmed", "version": "1.0", "added": _FRESH}


class TestHealthUsesThePlannedAttributeSet(BaseMCPTest):

    def test_without_a_plan_the_report_is_unchanged(self):
        """The single strongest guarantee of this feature: no plan, no drift.

        Compared as a SNAPSHOT, not by a handful of substrings: the previous version
        asserted three strings and would have passed with arbitrary new lines added,
        which is exactly what it exists to forbid. The expected text is written out in
        full, so any addition to a plan-less report fails here first.
        """
        _write_repo(PROJECT, [dict(BARE_REQ)])
        result = check_requirements_health(PROJECT)
        expected = "\n".join([
            f"<!-- BABOK 5.2 — Health Audit | Project: {PROJECT} | {date.today()} -->",
            "",
            "# 🏥 Requirements registry health audit",
            "",
            f"**Project:** {PROJECT}  ",
            "**Filter:** type=all, status=active  ",
            f"**Date:** {date.today()}",
            "",
            "## Summary",
            "",
            "| Status | Count | % |",
            "|--------|--------|---|",
            "| 🟢 Healthy | 0 | 0% |",
            "| 🟡 Need attention | 1 | 100% |",
            "| 🔴 Critical | 0 | 0% |",
            "| **Total active** | **1** | 100% |",
            "",
            "## 🟡 Need attention",
            "",
            "| ID | Type | Title | v | Owner | Issue |",
            "|----|-----|----------|---|----------|----------|",
            "| `FR-001` | functional | Login | 1.0 | — | 🟡 No owner |",
            "",
            "---",
            "",
            "## Recommended actions",
            "",
            "1. 🟡 **1 without an owner** — assign an owner via `update_requirement`.",
        ])
        self.assertTrue(result.startswith(expected),
                        f"plan-less report drifted:\n{result[:len(expected) + 200]}")

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
        """Asserted on the ISSUE LINE, not on the whole report: `complexity` and
        `reuse_scope` also appear in the "Audited attributes" header whenever a Full
        preset is selected, so asserting their mere presence stayed green even with
        gap detection disabled entirely."""
        _write_repo(PROJECT, [dict(BARE_REQ, owner="PO", source="Interview")])
        _write_plan(PROJECT, {"attributes": {"preset": "Full", "additional": []}})
        result = check_requirements_health(PROJECT)
        self.assertIn(
            "Attributes not filled in: priority, stability, reuse_candidate, "
            "reuse_scope, complexity", result)

    def test_healthy_block_does_not_claim_an_owner_it_never_checked(self):
        """Was: "N requirement(s) in good shape — current, have an owner, stable."
        printed unconditionally. Under a Minimum preset the owner is never examined,
        so a requirement with no owner landed in 🟢 and the document asserted it had
        one. A confident false claim inside the same page that chose not to look."""
        _write_repo(PROJECT, [dict(BARE_REQ, source="Interview 21.03")])
        _write_plan(PROJECT, {"attributes": {"preset": "Minimum", "additional": []}})
        result = check_requirements_health(PROJECT)
        self.assertIn("🟢 Healthy requirements", result)
        self.assertNotIn("have an owner", result)

    def test_healthy_block_wording_is_untouched_without_a_plan(self):
        _write_repo(PROJECT, [dict(BARE_REQ, owner="PO")])
        result = check_requirements_health(PROJECT)
        self.assertIn("current, have an owner, stable", result)

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

    def test_action_list_is_numbered_from_one(self):
        """Was: the numbers were hardcoded 1/2/3, so a report with no critical
        findings opened its action list at "2." — a delivered document missing its
        own first step."""
        _write_repo(PROJECT, [dict(BARE_REQ)])
        result = check_requirements_health(PROJECT)
        actions = result.split("Recommended actions")[1]
        self.assertIn("1. 🟡", actions)
        self.assertNotIn("2. 🟡", actions)

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
        self.assertIn("**Target reuse scope:** division", result)
        self.assertIn("3.4 plan", result)

    def test_explicit_scope_always_wins_over_the_plan(self):
        """Silently overriding an explicit BA input is worse than having no feature —
        the reason the governance wiring was refused in an earlier pass."""
        _write_repo(PROJECT, [dict(REUSABLE)])
        _write_plan(PROJECT, {"reuse": {"target_scope": "division",
                                        "repository": "", "categories": []}})
        result = find_reusable_requirements(PROJECT, min_reuse_scope="initiative")
        self.assertIn("**Target reuse scope:** initiative", result)
        self.assertNotIn("3.4 plan", result)

    def test_without_a_plan_the_default_is_still_initiative(self):
        _write_repo(PROJECT, [dict(REUSABLE)])
        result = find_reusable_requirements(PROJECT)
        self.assertIn("**Target reuse scope:** initiative", result)
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

    # An UNTAGGED requirement — the commonest shape in a live project, and the one the
    # scope bonus silently punished. Deliberately NOT flagged `reuse_candidate`: a
    # flagged one enters the confirmed list unconditionally, so it could never fail
    # for the reason these tests name.
    UNTAGGED = {"id": "SR-001", "type": "solution", "title": "Nightly settlement job",
                "status": "draft", "version": "1.0", "added": _FRESH}

    def test_a_wider_planned_scope_does_not_drop_a_requirement(self):
        """The seam between two of this branch's own fixes. Planning a WIDER reuse
        ambition made the report show FEWER candidates: the scope point is added to
        the same score that decides whether a requirement is listed at all, and an
        untagged requirement counts as `initiative`, so it lost the point and fell
        under the threshold. Reproduced: with no plan the requirement was listed, and
        with `target_scope: program` the report said "No suitable candidates" — while
        its own header claimed the scope "does not exclude"."""
        _write_repo(PROJECT, [dict(self.UNTAGGED)])
        without_plan = find_reusable_requirements(PROJECT)
        self.assertIn("SR-001", without_plan)

        _write_plan(PROJECT, {"reuse": {"target_scope": "program",
                                        "repository": "", "categories": []}})
        with_plan = find_reusable_requirements(PROJECT)
        self.assertIn("SR-001", with_plan)
        self.assertNotIn("No suitable candidates", with_plan)

    def test_a_wider_planned_scope_does_not_demote_between_sections(self):
        """Same defect one threshold up: a confirmed candidate must not slide into the
        potential list because the project raised its reuse ambition."""
        _write_repo(PROJECT, [dict(self.UNTAGGED, status="approved")])
        _write_plan(PROJECT, {"reuse": {"target_scope": "division",
                                        "repository": "", "categories": []}})
        result = find_reusable_requirements(PROJECT)
        self.assertIn("## ✅ Confirmed candidates", result)
        confirmed = result.split("## ✅ Confirmed candidates")[1].split("\n## ")[0]
        self.assertIn("SR-001", confirmed)

    def test_the_report_does_not_present_the_scope_as_a_filter(self):
        """The header said "Minimum scope: division" while a candidate with scope
        `initiative` sat in the confirmed list two lines below."""
        _write_repo(PROJECT, [dict(REUSABLE, reuse_scope="initiative")])
        _write_plan(PROJECT, {"reuse": {"target_scope": "division",
                                        "repository": "", "categories": []}})
        result = find_reusable_requirements(PROJECT)
        self.assertNotIn("Minimum scope", result)
        self.assertIn("raises the ranking", result)
        self.assertIn("BR-001", result)

    def test_the_scope_bonus_still_shows_up_in_the_score(self):
        """"Raises the ranking" must remain TRUE, not become vacuous: a requirement at
        or above the target scores one point more than the same requirement below it."""
        _write_repo(PROJECT, [dict(self.UNTAGGED, id="SR-002", reuse_scope="enterprise")])
        _write_plan(PROJECT, {"reuse": {"target_scope": "division",
                                        "repository": "", "categories": []}})
        at_target = find_reusable_requirements(PROJECT)
        _write_repo(PROJECT, [dict(self.UNTAGGED, id="SR-002", reuse_scope="initiative")])
        below_target = find_reusable_requirements(PROJECT)
        self.assertNotEqual(
            [ln for ln in at_target.splitlines() if "SR-002" in ln],
            [ln for ln in below_target.splitlines() if "SR-002" in ln])

    def test_empty_result_advice_does_not_offer_a_scope_that_filters_nothing(self):
        """"Lowering min_reuse_scope" cannot change an empty result once the scope no
        longer decides membership. Advice that cannot work is worse than no advice."""
        _write_repo(PROJECT, [])
        result = find_reusable_requirements(PROJECT)
        self.assertIn("No suitable candidates", result)
        self.assertNotIn("Lowering min_reuse_scope", result)

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
        self.assertIn("**Target reuse scope:** initiative", result)


if __name__ == "__main__":
    unittest.main()
