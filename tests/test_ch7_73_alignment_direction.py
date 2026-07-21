"""
tests/test_ch7_73_alignment_direction.py

7.3 exists to answer one question: do these requirements actually solve the business
problem? It answered it by walking the traceability graph in BOTH directions over ANY
relation, which reduces "traces to objective BG-001" to "sits in the same connected
component as BG-001".

On a real project a data-warehouse export requirement whose only link was
`depends -> RK-001` (a risk, which in turn `threatens -> BG-001`) was reported as
aligned to BOTH business objectives, and the report read "100% aligned, 0 orphans".

The canonical direction is `from` = child/realizer, `to` = parent/objective, and the
relations that mean "serves" are `derives` and `satisfies`. 5.4 `_has_br_path` already
walks it that way; this pins 7.3 to the same rule.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.conftest import setup_mocks

setup_mocks()

import skills.requirements_validate_mcp as v73


def graph():
    return {
        "project": "align",
        "requirements": [
            {"id": "BG-001", "type": "business_goal", "title": "Decide within 24 hours",
             "status": "confirmed"},
            {"id": "BG-002", "type": "business_goal", "title": "Cut manual underwriting",
             "status": "confirmed"},
            {"id": "FR-001", "type": "functional", "title": "Pre-fill from CRM",
             "status": "verified"},
            {"id": "RK-001", "type": "risk", "title": "Regulator may reject the model",
             "status": "identified"},
            # Only link: depends -> a risk. Serves no objective.
            {"id": "FR-099", "type": "functional",
             "title": "Export portfolio statistics to the warehouse", "status": "verified"},
        ],
        "links": [
            {"from": "FR-001", "to": "BG-001", "relation": "satisfies"},
            {"from": "RK-001", "to": "BG-001", "relation": "threatens"},
            {"from": "FR-099", "to": "RK-001", "relation": "depends"},
        ],
    }


class TestAlignmentTraversalDirection(unittest.TestCase):

    def test_a_requirement_serving_an_objective_is_found(self):
        reached = v73._bfs_to_business(graph(), "FR-001")
        self.assertEqual([n["id"] for n in reached], ["BG-001"])

    def test_traversal_does_not_run_backwards_through_a_risk(self):
        reached = v73._bfs_to_business(graph(), "FR-099")
        self.assertEqual(
            reached, [],
            "FR-099 only depends on a risk that threatens BG-001 — depending on a "
            "risk is not serving the objective the risk endangers",
        )

    def test_traversal_does_not_descend_from_an_objective_to_its_siblings(self):
        """Reaching an objective must stop there: continuing down finds every other
        requirement that serves it, and each of those is not an objective of the first."""
        g = graph()
        g["links"].append({"from": "FR-098", "to": "BG-001", "relation": "satisfies"})
        g["requirements"].append(
            {"id": "FR-098", "type": "functional", "title": "Sibling", "status": "verified"})
        reached = [n["id"] for n in v73._bfs_to_business(g, "FR-001")]
        self.assertEqual(reached, ["BG-001"])


class TestAlignmentReportReflectsIt(unittest.TestCase):

    def setUp(self):
        self.repo = graph()
        self._orig_repo = v73._load_repo
        self._orig_ctx = v73._load_context
        v73._load_repo = lambda project_id: self.repo
        v73._load_context = lambda project_id: {
            "business_goals": [{"id": "BG-001", "title": "Decide within 24 hours"},
                               {"id": "BG-002", "title": "Cut manual underwriting"}],
        }

    def tearDown(self):
        v73._load_repo = self._orig_repo
        v73._load_context = self._orig_ctx

    def test_the_unaligned_requirement_is_reported_as_an_orphan(self):
        out = v73.check_business_alignment("align")
        self.assertNotIn("100.0%", out.split("## Summary")[1][:400],
                         "the report claimed every requirement is aligned")
        self.assertIn("FR-099", out)


if __name__ == "__main__":
    unittest.main()
