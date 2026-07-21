"""
tests/test_graph_contracts.py — the shared graph's field-level contracts.

Four defects with one shape: a field written by several chapters, where each chapter
used the spelling that suited it and no consumer knew about the others. Unlike a
crash, none of these fails — they produce a document that is quietly wrong, and three
of the four surface in documents a stakeholder signs.

  * the LINK DATE is written under three different keys;
  * `rationale` is required at Full formality but one producer never writes it;
  * `priority` carries two different scales;
  * an edge is written to a target that need not exist.
"""

import json
import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import setup_mocks, BaseMCPTest

setup_mocks()

from skills.common import (LINK_DATE_KEYS, link_date, MUST_PRIORITIES,
                           VALID_PRIORITIES, normalize_project_id)
import skills.requirements_traceability_mcp as t51
import skills.requirements_maintain_mcp as t52
import skills.requirements_approve_mcp as t55

PID = "contracts"


class TestTheLinkDateIsReadWhoeverWroteIt(unittest.TestCase):
    """5.1/6.2/6.3/6.4 write `added`, 5.4 writes `added_date`, 7.1 writes `created`.
    The matrix read only `added`, so every edge created by change assessment or by
    specification rendered a dash in the Date column of the signed document."""

    def test_all_three_spellings_are_known(self):
        self.assertEqual(set(LINK_DATE_KEYS), {"added", "added_date", "created"})

    def test_each_spelling_resolves(self):
        for key in LINK_DATE_KEYS:
            self.assertEqual(link_date({key: "2026-07-21"}), "2026-07-21", key)

    def test_a_link_with_no_date_reports_a_dash(self):
        self.assertEqual(link_date({}), "—")


class TestMatrixRendersDatesFromEveryProducer(BaseMCPTest):

    def _repo_with_mixed_links(self):
        safe = normalize_project_id(PID)
        base = os.path.join("governance_plans", "data", safe)
        os.makedirs(base, exist_ok=True)
        with open(os.path.join(base, f"{safe}_traceability_repo.json"), "w",
                  encoding="utf-8") as f:
            json.dump({
                "project": PID, "formality_level": "Full", "history": [],
                "requirements": [
                    {"id": "BG-001", "type": "business_goal", "title": "Goal",
                     "version": "1.0", "status": "confirmed"},
                    {"id": "FR-001", "type": "functional", "title": "Req",
                     "version": "1.0", "status": "draft"},
                    {"id": "CR-001", "type": "change_request", "title": "CR",
                     "version": "1.0", "status": "open"},
                ],
                "links": [
                    # as 7.1 writes it
                    {"from": "FR-001", "to": "BG-001", "relation": "satisfies",
                     "created": "2026-07-01"},
                    # as 5.4 writes it
                    {"from": "CR-001", "to": "FR-001", "relation": "modifies",
                     "added_date": "2026-07-02"},
                ],
            }, f)

    def test_dates_from_other_producers_are_not_dashes(self):
        self._repo_with_mixed_links()
        out = t51.export_traceability_matrix(PID)
        link_rows = [l for l in out.splitlines()
                     if l.startswith("|") and ("satisfies" in l or "modifies" in l)]
        self.assertTrue(link_rows, "no link rows rendered at all")
        for row in link_rows:
            # The DATE is the last column; the rationale column may legitimately be
            # empty for hand-written legacy edges, so check only the one under test.
            date_cell = row.rstrip().rstrip("|").rsplit("|", 1)[-1].strip()
            self.assertNotEqual(
                date_cell, "—",
                f"a link carries a date the matrix could not read: {row}")


class TestSpecificationWritesARationale(BaseMCPTest):
    """At Full formality the repository declares `rationale` REQUIRED, and the matrix
    renders it. 7.1's satisfies edges carried no rationale key at all, so a regulated
    project got a dash in the column its formality level exists to fill."""

    def test_71_satisfies_edge_carries_a_rationale(self):
        import skills.requirements_spec_mcp as t71
        t51.init_traceability_repo(
            PID, "Full",
            json.dumps([{"id": "BG-001", "type": "business_goal", "title": "Goal"}]))
        t71.create_functional_requirement(
            project_id=PID, req_id="FR-001", req_type="functional",
            title="Pre-fill from CRM",
            description="The system SHALL pre-fill the application from CRM.",
            rationale="Cuts the officer's data entry.",
            business_goal_ids_json='["BG-001"]')
        safe = normalize_project_id(PID)
        with open(os.path.join("governance_plans", "data", safe,
                               f"{safe}_traceability_repo.json"), encoding="utf-8") as f:
            repo = json.load(f)
        edges = [l for l in repo["links"] if l["relation"] == "satisfies"]
        self.assertTrue(edges, "7.1 wrote no satisfies edge")
        for e in edges:
            self.assertTrue(e.get("rationale"),
                            f"edge without a rationale at Full formality: {e}")


class TestPriorityIsOneVocabulary(BaseMCPTest):
    """7.1 writes High/Medium/Low, 5.3 writes MoSCoW, and 5.2 validated nothing."""

    def test_must_priorities_span_both_scales(self):
        self.assertEqual(MUST_PRIORITIES, {"Must", "High"})

    def test_valid_priorities_cover_both_scales(self):
        for p in ("Must", "Should", "Could", "Won't", "High", "Medium", "Low"):
            self.assertIn(p, VALID_PRIORITIES)

    def test_52_rejects_a_priority_from_no_scale(self):
        t51.init_traceability_repo(
            PID, "Standard",
            json.dumps([{"id": "FR-001", "type": "functional", "title": "X"}]))
        result = t52.update_requirement(
            PID, "FR-001", change_reason="Re-prioritised", new_priority="Urgent")
        self.assertIn("❌", result)

    def test_52_accepts_both_scales(self):
        t51.init_traceability_repo(
            PID, "Standard",
            json.dumps([{"id": "FR-001", "type": "functional", "title": "X"}]))
        for value in ("Must", "High"):
            self.assertNotIn("❌", t52.update_requirement(
                PID, "FR-001", change_reason="Re-prioritised", new_priority=value))

    def test_55_flags_a_rejected_high_priority_requirement(self):
        """The "rejecting a critically important requirement" warning fired only for
        MoSCoW `Must`, so it never fired on a project that specified in 7.1 and never
        ran 5.3 — precisely the project least likely to catch it another way."""
        t51.init_traceability_repo(
            PID, "Standard",
            json.dumps([{"id": "FR-001", "type": "functional", "title": "X",
                         "priority": "High"}]))
        t55.prepare_approval_package(
            project_name=PID, package_id="PKG-1", package_title="T",
            req_ids_json='["FR-001"]', approach="formal", audience="sponsor")
        out = t55.record_approval_decision(
            project_name=PID, package_id="PKG-1", stakeholder_name="Ivan",
            stakeholder_raci="accountable", decision="rejected",
            rejection_reason="Out of budget",
            req_decisions_json=json.dumps(
                [{"req_id": "FR-001", "decision": "rejected"}]))
        self.assertIn("🔴", out)


class TestNoEdgeToANodeThatDoesNotExist(BaseMCPTest):
    """6.3 and 6.4 check the target exists before writing an edge; 6.2 did not, so a
    mistyped id produced a dangling edge — and the coverage audit then counted the
    objective as justified, because having an outgoing edge is what it checks."""

    def test_62_does_not_write_an_edge_to_a_missing_need(self):
        import skills.future_state_mcp as t62
        t51.init_traceability_repo(PID, "Standard", json.dumps(
            [{"id": "BN-001", "type": "business_need", "title": "A real need"}]))
        t62.define_goals_and_objectives(
            project_id=PID, goal_title="Decide within 24 hours",
            description="Cut the decision cycle to one day.",
            objectives_json=json.dumps([{"title": "Decision cycle", "metric": "hours",
                                        "baseline": "48", "target": "24",
                                        "deadline": "2026-12-31"}]),
            linked_business_needs='["BN-404"]',
            register_in_traceability=True)
        safe = normalize_project_id(PID)
        with open(os.path.join("governance_plans", "data", safe,
                               f"{safe}_traceability_repo.json"), encoding="utf-8") as f:
            repo = json.load(f)
        ids = {r["id"] for r in repo["requirements"]}
        for link in repo["links"]:
            self.assertIn(
                link["to"], ids,
                f"dangling edge to {link['to']}, which is not a node in the graph")

    def test_62_tells_the_analyst_the_link_was_skipped(self):
        """Silently dropping the link would trade one wrong answer for another."""
        import skills.future_state_mcp as t62
        t51.init_traceability_repo(PID, "Standard", json.dumps(
            [{"id": "BN-001", "type": "business_need", "title": "A real need"}]))
        out = t62.define_goals_and_objectives(
            project_id=PID, goal_title="Decide within 24 hours",
            description="Cut the decision cycle to one day.",
            objectives_json=json.dumps([{"title": "Decision cycle", "metric": "hours",
                                        "baseline": "48", "target": "24",
                                        "deadline": "2026-12-31"}]),
            linked_business_needs='["BN-404"]',
            register_in_traceability=True)
        self.assertIn("BN-404", out)


class TestZeroLinksIsExplained(BaseMCPTest):
    """A push reporting "+0 links" without saying why reads as success. The zero
    always has a cause — every target was filtered out by the existence check."""

    def test_63_explains_why_no_links_were_written(self):
        import skills.risk_assessment_mcp as t63
        t51.init_traceability_repo(PID, "Standard", json.dumps(
            [{"id": "BG-001", "type": "business_goal", "title": "A real goal"}]))
        t63.add_risk(project_id=PID, category="regulatory", source="change",
                     description="Regulator may reject the model",
                     likelihood=4, impact=5, response_strategy="mitigate",
                     mitigation_plan="Engage the regulator early",
                     linked_bg="BG-404")
        t63.run_risk_matrix(PID)
        t63.generate_recommendation(PID)
        out = t63.save_risk_assessment(PID, push_to_traceability=True)
        self.assertIn("BG-404", out,
                      "the report did not name the target that could not be linked")


if __name__ == "__main__":
    unittest.main()
