"""
tests/test_solution_scope_node_type.py — 6.4's scope node stops colliding with the
BABOK requirement class.

The literal `solution` carried TWO meanings in the same `type` field:

  (a) the BABOK requirement CLASS of the 5.1 vocabulary
      (business | stakeholder | solution | transition), which is how
      `init_traceability_repo`, the Confluence import and the shared test fixtures
      label ordinary FR/NFR requirements;
  (b) the SOLUTION SCOPE node 6.4 pushes (SOL-001, ADR-082).

Because meaning (a) is a real requirement, `solution` could never be added to the
non-requirement role set — doing so dropped real requirements out of the coverage
matrix. So meaning (b) was counted as a requirement EVERYWHERE: 7.1's coverage
matrix, 5.2's health audit, 5.3's MoSCoW session (a stakeholder was asked to vote
on the project's scope) and 5.1's "needs a test case" rule.

The node also carried a SECOND colliding literal: `status="approved"`, meaning "the
scope is settled", read by 7.2 as 5.5's "the stakeholders signed" — so the
verification report claimed "Approved in 5.5: 1" on a project where 5.5 had never
run.

Resolution (ADR-082 revised): 6.4 writes `type="solution_scope"`, `status="defined"`.
`solution` goes back to meaning only the requirement class.
"""

import json
import os
import sys
import unittest
from datetime import date
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import setup_mocks, BaseMCPTest, data_file

setup_mocks()

from skills.common import (SOLUTION_SCOPE_NODE_TYPE, ANALYSIS_NODE_TYPES,
                           NON_REQUIREMENT_NODE_TYPES)
import skills.requirements_traceability_mcp as t51
import skills.requirements_verify_mcp as t72


def _graph_with_scope_node():
    """A repository holding a 6.4 scope node next to a real `solution`-class
    requirement — the two populations the literal used to merge."""
    return {
        "project": "collide",
        "formality_level": "Standard",
        "requirements": [
            {"id": "BG-001", "type": "business_goal", "title": "Decide within 24 hours",
             "version": "1.0", "status": "confirmed"},
            # A REAL requirement carrying the BABOK class — must stay a requirement.
            {"id": "FR-001", "type": "solution", "title": "Pre-fill from CRM",
             "version": "1.0", "status": "draft"},
            # 6.4's scope node — must NOT be a requirement.
            {"id": "SOL-001", "type": SOLUTION_SCOPE_NODE_TYPE,
             "title": "Solution Scope — collide", "version": "1.0", "status": "defined"},
        ],
        "links": [
            {"from": "FR-001", "to": "BG-001", "relation": "satisfies"},
            {"from": "SOL-001", "to": "BG-001", "relation": "satisfies"},
        ],
    }


class TestSharedVocabularySeparatesTheTwoMeanings(unittest.TestCase):

    def test_scope_node_type_is_a_non_requirement(self):
        self.assertIn(SOLUTION_SCOPE_NODE_TYPE, NON_REQUIREMENT_NODE_TYPES)

    def test_the_babok_requirement_class_is_still_a_requirement(self):
        """The whole reason the collision could not be resolved by a skip-set."""
        self.assertNotIn("solution", NON_REQUIREMENT_NODE_TYPES)

    def test_the_two_literals_are_distinct(self):
        self.assertNotEqual(SOLUTION_SCOPE_NODE_TYPE, "solution")

    def test_scope_node_is_an_analysis_artifact(self):
        """It lives in the graph for traceability, like a risk or a change request."""
        self.assertIn(SOLUTION_SCOPE_NODE_TYPE, ANALYSIS_NODE_TYPES)


class TestCoverageAuditTreatsTheScopeNodeAsAnArtifact(unittest.TestCase):

    def setUp(self):
        self.repo = _graph_with_scope_node()
        self._orig = t51._load_repo
        t51._load_repo = lambda project_name: self.repo

    def tearDown(self):
        t51._load_repo = self._orig

    def _row(self, out, req_id):
        for line in out.splitlines():
            if f"`{req_id}`" in line and line.startswith("|"):
                return line
        return ""

    def test_scope_node_is_not_asked_for_a_test_case(self):
        """The rule `req_type in ("solution", "transition")` demanded a test case
        from the project's SCOPE — a test case cannot verify a scope."""
        out = t51.check_coverage("collide")
        self.assertNotIn(
            "no test", self._row(out, "SOL-001"),
            "the 6.4 scope node was told to produce a test case",
        )

    def test_scope_node_is_not_asked_for_an_implementation(self):
        """Nothing implements the scope: it is itself what satisfies the objectives."""
        out = t51.check_coverage("collide")
        self.assertNotIn("no implementation", self._row(out, "SOL-001"))

    def test_a_real_solution_class_requirement_is_still_asked_for_a_test(self):
        """The guard against over-correcting: the rule must keep working for the
        requirement class it was written for."""
        out = t51.check_coverage("collide")
        self.assertIn("FR-001", out)

    def test_scope_node_anchored_by_satisfies_is_not_an_orphan(self):
        out = t51.check_coverage("collide")
        orphan_section = out.split("## 🔴")[1].split("##")[0] if "## 🔴" in out else ""
        self.assertNotIn("SOL-001", orphan_section)


class TestVerificationReportStopsMisreadingTheScopeStatus(unittest.TestCase):
    """`status="approved"` on the scope node meant "scope settled"; 7.2 read it as
    5.5's "stakeholders signed" and reported an approval that never happened."""

    def setUp(self):
        self.repo = _graph_with_scope_node()
        self._orig = t72._load_repo
        t72._load_repo = lambda project_name: self.repo

    def tearDown(self):
        t72._load_repo = self._orig

    def test_scope_node_is_not_counted_as_approved_in_55(self):
        """This fixture has no approval records at all, so the honest answer is
        "5.5 has not run" (see tests/test_common_approval.py) — what matters here is
        that the scope node is not counted as an approval."""
        out = t72.get_verification_report("collide")
        approved_line = [l for l in out.splitlines() if "Согласовано в 5.5" in l][0]
        self.assertNotIn(
            "| 1 |", approved_line,
            "the report credited 5.5 with approving the 6.4 scope node",
        )

    def test_scope_node_is_not_counted_as_a_requirement(self):
        out = t72.get_verification_report("collide")
        self.assertNotIn("SOL-001", out)


class TestSixFourWritesTheNewLiterals(BaseMCPTest):
    """Verified against the real producer, not a fixture — the literal has to change
    where it is WRITTEN, or every consumer fix is cosmetic."""

    def _run_push(self):
        from tests.test_ch6_64 import _setup_full_pipeline, _load_strategy, PROJECT
        from skills.change_strategy_mcp import (save_change_strategy, _save_strategy,
                                                _safe, DATA_DIR)
        _setup_full_pipeline()
        repo = {
            "project_id": PROJECT,
            "requirements": [{"id": "BG-001", "type": "business_goal", "title": "NPS"}],
            "links": [],
        }
        repo_path = data_file(_safe(PROJECT), "traceability_repo.json")
        with open(repo_path, "w", encoding="utf-8") as f:
            json.dump(repo, f)
        strategy = _load_strategy()
        strategy["imported_context"]["business_goals"] = [
            {"id": "BG-001", "title": "NPS", "source_project": PROJECT}
        ]
        _save_strategy(strategy, PROJECT)
        with patch("skills.change_strategy_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅"
            save_change_strategy(project_id=PROJECT, push_to_traceability=True)
        with open(repo_path, encoding="utf-8") as f:
            return json.load(f)

    def test_node_type_is_solution_scope(self):
        updated = self._run_push()
        sol = [r for r in updated["requirements"] if r["id"] == "SOL-001"][0]
        self.assertEqual(sol["type"], SOLUTION_SCOPE_NODE_TYPE)

    def test_status_does_not_claim_stakeholder_approval(self):
        updated = self._run_push()
        sol = [r for r in updated["requirements"] if r["id"] == "SOL-001"][0]
        self.assertNotEqual(
            sol["status"], "approved",
            "`approved` is 5.5's outcome literal — 6.4 cannot approve on behalf of "
            "stakeholders who never saw the package",
        )


class TestMigrationOfGraphsAlreadyWritten(BaseMCPTest):
    """Graphs written before the rename carry the old literals. The migration must
    rename the SCOPE node and leave requirement-class nodes untouched."""

    def _write_repo(self, requirements):
        path = os.path.join("governance_plans", "data", "legacy_traceability_repo.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"project": "legacy", "requirements": requirements, "links": []}, f)
        return path

    def test_scope_node_is_migrated(self):
        from migrate_solution_scope import migrate_repo_file
        path = self._write_repo([
            {"id": "SOL-001", "type": "solution", "title": "Solution Scope — legacy",
             "version": "1.0", "status": "approved"},
        ])
        stats = migrate_repo_file(path)
        self.assertEqual(stats["migrated"], 1)
        with open(path, encoding="utf-8") as f:
            node = json.load(f)["requirements"][0]
        self.assertEqual(node["type"], SOLUTION_SCOPE_NODE_TYPE)
        self.assertNotEqual(node["status"], "approved")

    def test_requirement_class_nodes_are_left_alone(self):
        """The migration must not touch the population it cannot distinguish by
        literal alone — real requirements also carry `type: solution`."""
        from migrate_solution_scope import migrate_repo_file
        path = self._write_repo([
            {"id": "FR-001", "type": "solution", "title": "Pre-fill from CRM",
             "version": "1.0", "status": "approved"},
        ])
        stats = migrate_repo_file(path)
        self.assertEqual(stats["migrated"], 0)
        with open(path, encoding="utf-8") as f:
            node = json.load(f)["requirements"][0]
        self.assertEqual(node["type"], "solution")
        self.assertEqual(node["status"], "approved")

    def test_migration_is_idempotent(self):
        from migrate_solution_scope import migrate_repo_file
        path = self._write_repo([
            {"id": "SOL-001", "type": "solution", "title": "Solution Scope — legacy",
             "version": "1.0", "status": "approved"},
        ])
        migrate_repo_file(path)
        stats = migrate_repo_file(path)
        self.assertEqual(stats["migrated"], 0)

    def test_a_status_the_analyst_changed_is_preserved(self):
        """Only the colliding literal is rewritten. If the BA moved the scope node
        to some other status, that is their record, not ours to overwrite."""
        from migrate_solution_scope import migrate_repo_file
        path = self._write_repo([
            {"id": "SOL-001", "type": "solution", "title": "Solution Scope — legacy",
             "version": "1.0", "status": "deprecated"},
        ])
        migrate_repo_file(path)
        with open(path, encoding="utf-8") as f:
            node = json.load(f)["requirements"][0]
        self.assertEqual(node["type"], SOLUTION_SCOPE_NODE_TYPE)
        self.assertEqual(node["status"], "deprecated")


if __name__ == "__main__":
    unittest.main()
