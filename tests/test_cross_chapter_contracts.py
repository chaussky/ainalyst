"""
tests/test_cross_chapter_contracts.py

Four seams where a consumer and a producer disagreed, each found by running one project
end to end rather than by testing a chapter against its own fixtures.

  1. 5.1 `init_traceability_repo` REPLACED an existing entry instead of merging it, so
     re-running it with a node 6.1/6.2 had registered destroyed the node's `type` — the
     one field every other chapter's traversal depends on.
  2. 6.4 could not read the flat surrogate 7.5 writes to the SAME filename, so working
     in the `design` phase first left three of the five 6.4 tools raising KeyError.
  3. 6.3 computed each risk's zone — the decision that honours the analyst's tolerance
     and the mandatory-avoid list — into a COPY, so no consumer could ever read it.
  4. 6.2 stores the potential value under `value_summary`; 6.3 read `summary`, so the
     sponsor recommendation never mentioned the value the analyst had assessed.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.conftest import setup_mocks

setup_mocks()

import skills.requirements_traceability_mcp as t51
import skills.change_strategy_mcp as c64
import skills.risk_assessment_mcp as c63


class TestInitDoesNotClobberForeignNodeTypes(unittest.TestCase):

    def setUp(self):
        self.repo = {
            "project": "p", "formality_level": "Standard",
            "requirements": [
                {"id": "BN-001", "type": "business_need", "title": "Cut the cycle",
                 "version": "1.0", "status": "confirmed", "source_artifact": "6.1"},
            ],
            "links": [], "history": [],
        }
        self._load, self._save = t51._load_repo, t51._save_repo
        t51._load_repo = lambda project_name: self.repo
        t51._save_repo = lambda repo: "path"

    def tearDown(self):
        t51._load_repo, t51._save_repo = self._load, self._save

    def test_relisting_a_6_1_node_keeps_its_type_and_status(self):
        t51.init_traceability_repo("p", "Standard", json.dumps([
            {"id": "BN-001", "title": "Cut the cycle"}]))
        node = self.repo["requirements"][0]
        self.assertEqual(node["type"], "business_need",
                         "the node type other chapters filter on was destroyed")
        self.assertEqual(node["status"], "confirmed")

    def test_an_explicit_type_still_wins(self):
        t51.init_traceability_repo("p", "Standard", json.dumps([
            {"id": "BN-001", "title": "Cut the cycle", "type": "business"}]))
        self.assertEqual(self.repo["requirements"][0]["type"], "business")


class TestChangeStrategyToleratesTheSurrogate(unittest.TestCase):
    """7.5 knows how to refuse to clobber 6.4's format; 6.4 must read 7.5's."""

    SURROGATE = {
        "project_id": "p", "change_type": "technology", "scope": "Retail origination",
        "constraints": "Validation gate", "timeline": "9 months", "notes": "",
        "created": "2026-07-21", "updated": "2026-07-21",
    }

    def setUp(self):
        self._load = c64._load_strategy
        c64._load_strategy = lambda project_id: dict(self.SURROGATE)

    def tearDown(self):
        c64._load_strategy = self._load

    def test_loader_supplies_the_keys_the_chapter_indexes(self):
        data = c64._load_strategy("p")
        normalized = c64._normalize_strategy(data, "p")
        for key in ("change_strategy", "solution_scope", "transition_states"):
            self.assertIn(key, normalized)

    def test_the_surrogate_fields_are_not_thrown_away(self):
        normalized = c64._normalize_strategy(dict(self.SURROGATE), "p")
        self.assertEqual(normalized["change_type"], "technology")


class TestRiskZoneIsPersisted(unittest.TestCase):

    def setUp(self):
        self.assessment = {
            "project_id": "p",
            "risks": [
                {"risk_id": "RK-001", "category": "regulatory", "description": "d",
                 "likelihood": 2, "impact": 3, "risk_score": 6,
                 "response_strategy": "mitigate", "status": "identified"},
            ],
            "risk_tolerance": {"max_acceptable_score": 12,
                               "mandatory_avoid_categories": ["regulatory"]},
            "scope": {}, "risk_matrix": {},
        }
        self._load, self._save = c63._load_assessment, c63._save_assessment
        c63._load_assessment = lambda project_id: self.assessment
        c63._save_assessment = lambda data, project_id: None

    def tearDown(self):
        c63._load_assessment, c63._save_assessment = self._load, self._save

    def test_the_matrix_decision_reaches_the_stored_risk(self):
        c63.run_risk_matrix("p")
        risk = self.assessment["risks"][0]
        self.assertIn("zone", risk,
                      "the zone lived only in the matrix copy, so every consumer fell "
                      "back to the raw score and lost the tolerance decision")

    def test_the_mandatory_avoid_override_survives(self):
        """score 6 is below the threshold of 12, but the category is mandatory-avoid."""
        c63.run_risk_matrix("p")
        self.assertEqual(self.assessment["risks"][0]["zone"], "high")


if __name__ == "__main__":
    unittest.main()
