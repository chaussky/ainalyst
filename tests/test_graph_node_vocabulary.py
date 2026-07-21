"""
tests/test_graph_node_vocabulary.py — every graph consumer must know every node type.

The 5.1 repository is written by NINE producers. 5.1 itself contributes the BABOK
classification (business / stakeholder / solution / transition / test / component),
6.1 adds `business_need`, 6.2 `business_goal`, 6.3 `risk`, 5.4 `change_request`, and
7.1 the eight specification types. Relations grew the same way: 6.3 writes `threatens`
and 5.4 writes `modifies`, neither of which 5.1's own vocabulary mentions.

Consumers that hard-code the subset they knew about when they were written do not fail
loudly — they misclassify. An end-to-end run over a graph built by six producers showed
six of them doing exactly that: the traceability matrix rendered 2 of 15 requirements
under a header claiming 15, the coverage audit told the analyst to freeze risks as
unjustified orphans, impact analysis printed a count its own tables did not contain,
and 7.2 / 5.3 / 5.2 asked business goals for owners, priorities and MoSCoW votes.

These tests pin the behaviour on a graph containing EVERY node type and EVERY relation
a producer really writes — the fixture other suites do not build.

Note on `solution`: it is deliberately NOT a non-requirement type. The literal is both
6.4's solution-scope node type and the BABOK requirement CLASS the 5.1 vocabulary and
the Confluence import assign to ordinary requirements. Between over-counting one scope
node and dropping real requirements, only the second is a lie about coverage.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.conftest import setup_mocks

setup_mocks()

from skills.common import (BUSINESS_NODE_TYPES, ANALYSIS_NODE_TYPES,
                           NON_REQUIREMENT_NODE_TYPES)
import skills.requirements_traceability_mcp as t51


def full_graph():
    """A repository holding every node type and every relation a producer writes."""
    return {
        "project": "vocab",
        "formality_level": "Standard",
        "requirements": [
            {"id": "BR-001", "type": "business", "title": "Decide loans faster",
             "version": "1.0", "status": "confirmed"},
            {"id": "BN-001", "type": "business_need", "title": "Cut the decision cycle",
             "version": "1.0", "status": "confirmed"},
            {"id": "BG-001", "type": "business_goal", "title": "Decide within 24 hours",
             "version": "1.0", "status": "confirmed"},
            {"id": "FR-001", "type": "functional", "title": "Pre-fill from CRM",
             "version": "1.0", "status": "draft"},
            {"id": "NFR-001", "type": "non_functional", "title": "Decision within 30s",
             "version": "1.0", "status": "draft"},
            {"id": "US-001", "type": "user_story", "title": "Officer sees the reason code",
             "version": "1.0", "status": "draft"},
            {"id": "UC-001", "type": "use_case", "title": "Submit an application",
             "version": "1.0", "status": "draft"},
            {"id": "RK-001", "type": "risk", "title": "Regulator may reject the model",
             "version": "1.0", "status": "identified"},
            {"id": "CR-001", "type": "change_request", "title": "Support self-employed",
             "version": "1.0", "status": "open"},
            {"id": "SOL-001", "type": "solution", "title": "Solution Scope — vocab",
             "version": "1.0", "status": "approved"},
        ],
        "links": [
            {"from": "BG-001", "to": "BN-001", "relation": "derives"},
            {"from": "FR-001", "to": "BG-001", "relation": "satisfies"},
            {"from": "NFR-001", "to": "BG-001", "relation": "satisfies"},
            {"from": "US-001", "to": "BG-001", "relation": "satisfies"},
            {"from": "UC-001", "to": "BG-001", "relation": "satisfies"},
            {"from": "SOL-001", "to": "BG-001", "relation": "satisfies"},
            {"from": "RK-001", "to": "BG-001", "relation": "threatens"},
            {"from": "CR-001", "to": "FR-001", "relation": "modifies"},
        ],
    }


class TestSharedVocabulary(unittest.TestCase):

    def test_analysis_types_cover_the_producers_that_are_not_requirements(self):
        self.assertEqual(ANALYSIS_NODE_TYPES, {"risk", "change_request"})

    def test_solution_is_not_treated_as_a_non_requirement(self):
        """One literal, two meanings — excluding it would drop real requirements."""
        self.assertNotIn("solution", NON_REQUIREMENT_NODE_TYPES)

    def test_non_requirement_set_is_the_union(self):
        self.assertEqual(
            NON_REQUIREMENT_NODE_TYPES,
            BUSINESS_NODE_TYPES | ANALYSIS_NODE_TYPES | {"test"},
        )


class TestTraceabilityMatrixRendersEveryNode(unittest.TestCase):
    """The matrix goes into the 5.5 approval package — a stakeholder signs it."""

    def setUp(self):
        self.repo = full_graph()
        self._orig = t51._load_repo
        t51._load_repo = lambda project_name: self.repo

    def tearDown(self):
        t51._load_repo = self._orig

    def test_every_node_appears_in_the_requirements_section(self):
        out = t51.export_traceability_matrix("vocab")
        body = out.split("## Traceability links")[0]
        for node in self.repo["requirements"]:
            self.assertIn(
                node["id"], body,
                f"{node['id']} (type={node['type']}) is missing from the rendered "
                f"requirements section — the header still counts it",
            )

    def test_header_count_matches_the_rows_rendered(self):
        out = t51.export_traceability_matrix("vocab")
        body = out.split("## Traceability links")[0]
        rendered = sum(1 for n in self.repo["requirements"] if n["id"] in body)
        self.assertIn(f"**Total requirements:** {rendered}", out)


class TestCoverageAuditClassifiesForeignNodes(unittest.TestCase):

    def setUp(self):
        self.repo = full_graph()
        self._orig = t51._load_repo
        t51._load_repo = lambda project_name: self.repo

    def tearDown(self):
        t51._load_repo = self._orig

    def test_a_risk_justified_by_threatens_is_not_an_orphan(self):
        out = t51.check_coverage("vocab")
        orphan_section = out.split("## 🔴")[1].split("##")[0] if "## 🔴" in out else ""
        self.assertNotIn(
            "RK-001", orphan_section,
            "a risk linked by `threatens` was reported as an unjustified orphan",
        )

    def test_a_change_request_justified_by_modifies_is_not_an_orphan(self):
        out = t51.check_coverage("vocab")
        orphan_section = out.split("## 🔴")[1].split("##")[0] if "## 🔴" in out else ""
        self.assertNotIn("CR-001", orphan_section)


class TestImpactAnalysisCountMatchesItsTables(unittest.TestCase):

    def setUp(self):
        self.repo = full_graph()
        self._orig = t51._load_repo
        t51._load_repo = lambda project_name: self.repo

    def tearDown(self):
        t51._load_repo = self._orig

    def test_reported_total_equals_the_rows_the_reader_can_see(self):
        out = t51.run_impact_analysis("vocab", "FR-001", "Add self-employed handling")
        import re
        m = re.search(r"Result: \*\*(\d+)\*\* artifacts affected", out)
        self.assertIsNotNone(m, "impact analysis did not report a total")
        claimed = int(m.group(1))
        listed = len(re.findall(r"^\| `[A-Z]+-\d+`", out, flags=re.M))
        self.assertEqual(
            claimed, listed,
            f"impact analysis claims {claimed} affected artifacts but renders {listed} "
            f"rows — anything reached over a relation it does not group by is dropped",
        )

    def test_a_node_reached_over_threatens_is_shown(self):
        out = t51.run_impact_analysis("vocab", "BG-001", "Retarget to 18 hours")
        self.assertIn(
            "RK-001", out,
            "the risk threatening the changed objective is exactly what impact "
            "analysis exists to surface",
        )


if __name__ == "__main__":
    unittest.main()


class TestImpactDoesNotExpandThroughObjectives(unittest.TestCase):
    """Objectives are hubs: 7.1 links every requirement to the ones it serves, so
    expanding past one walks back down to every sibling."""

    def setUp(self):
        self.repo = full_graph()
        self.repo["requirements"].append(
            {"id": "FR-777", "type": "functional", "title": "An unrelated sibling",
             "version": "1.0", "status": "draft"})
        self.repo["links"].append(
            {"from": "FR-777", "to": "BG-001", "relation": "satisfies"})
        self._orig = t51._load_repo
        t51._load_repo = lambda project_name: self.repo

    def tearDown(self):
        t51._load_repo = self._orig

    def test_a_sibling_sharing_an_objective_is_not_reported_as_impacted(self):
        out = t51.run_impact_analysis("vocab", "FR-001", "Change the CRM mapping")
        self.assertIn("BG-001", out, "the objective itself is worth flagging")
        self.assertNotIn(
            "FR-777", out,
            "FR-777 only shares an objective with the changed requirement — that is "
            "not an impact, and counting it inflates the 5.4 score",
        )
