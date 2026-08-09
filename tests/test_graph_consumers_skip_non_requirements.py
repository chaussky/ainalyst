"""
tests/test_graph_consumers_skip_non_requirements.py

Three consumers select "the requirements" out of the 5.1 graph by STATUS alone, so every
node another chapter wrote is swept in. On a real end-to-end project this asked business
goals for an owner and a MoSCoW vote, ran the requirement-quality checklist over risks,
and reported an approval nobody granted — because 6.4 writes its solution-scope node with
`status: approved`, meaning "the scope is settled", while 5.5 reads that same literal as
"the stakeholders signed it off".

Selection must be by ROLE (is this a requirement?) and not by status alone.

See tests/test_graph_node_vocabulary.py for the shared vocabulary and the note on why
`solution` is deliberately still counted as a requirement.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.conftest import setup_mocks, BaseMCPTest

setup_mocks()

import skills.requirements_verify_mcp as v72
import skills.requirements_prioritize_mcp as p53
import skills.requirements_maintain_mcp as m52
import skills.requirements_validate_mcp as v73
import skills.requirements_architecture_mcp as a74
import skills.design_options_mcp as d75
import skills.requirements_traceability_mcp as t51

FOREIGN = ["BN-001", "BG-001", "RK-001", "CR-001", "SOL-001"]


def mixed_repo():
    return {
        "project": "mixed",
        "formality_level": "Standard",
        "requirements": [
            {"id": "FR-001", "type": "functional", "title": "Pre-fill from CRM",
             "version": "1.0", "status": "draft", "owner": "Anna"},
            {"id": "BN-001", "type": "business_need", "title": "Cut the decision cycle",
             "version": "1.0", "status": "confirmed"},
            {"id": "BG-001", "type": "business_goal", "title": "Decide within 24 hours",
             "version": "1.0", "status": "confirmed"},
            {"id": "RK-001", "type": "risk", "title": "Regulator may reject the model",
             "version": "1.0", "status": "identified"},
            {"id": "CR-001", "type": "change_request", "title": "Support self-employed",
             "version": "1.0", "status": "open"},
            {"id": "SOL-001", "type": "solution_scope", "title": "Solution Scope — mixed",
             "version": "1.0", "status": "defined"},
        ],
        "links": [],
        "history": [],
    }


class TestVerificationSkipsNonRequirements(unittest.TestCase):

    def setUp(self):
        self.repo = mixed_repo()
        self._orig = v72._load_repo
        v72._load_repo = lambda project_id: self.repo

    def tearDown(self):
        v72._load_repo = self._orig

    def test_quality_check_ignores_other_chapters_nodes(self):
        out = v72.check_req_quality("mixed")
        for node_id in FOREIGN:
            self.assertNotIn(
                node_id, out,
                f"{node_id} is not a requirement — the 7.2 quality checklist "
                f"(atomicity, testability, priority, owner) does not apply to it",
            )

    def test_verification_report_counts_only_requirements(self):
        out = v72.get_verification_report("mixed")
        self.assertIn("| Всего активных требований | 1 |", out)


class TestPrioritizationSkipsNonRequirements(unittest.TestCase):

    def setUp(self):
        self.repo = mixed_repo()
        self._orig_repo = p53._load_repo
        self._orig_prio = p53._load_prio
        self._orig_save = p53._save_prio
        p53._load_repo = lambda project_name: self.repo
        p53._load_prio = lambda project_name: {"project": "mixed", "sessions": []}
        p53._save_prio = lambda data, project_name=None: None

    def tearDown(self):
        p53._load_repo = self._orig_repo
        p53._load_prio = self._orig_prio
        p53._save_prio = self._orig_save

    def test_a_risk_is_not_offered_for_a_moscow_vote(self):
        out = p53.start_prioritization_session("mixed", "Release 1", "MoSCoW")
        for node_id in FOREIGN:
            self.assertNotIn(
                node_id, out,
                f"{node_id} was offered for prioritisation — a stakeholder cannot "
                f"vote Must/Should/Could on a risk or an objective",
            )


class TestHealthAuditSkipsNonRequirements(unittest.TestCase):

    def setUp(self):
        self.repo = mixed_repo()
        self._orig = m52._load_repo
        m52._load_repo = lambda project_name: self.repo

    def tearDown(self):
        m52._load_repo = self._orig

    def test_health_audit_does_not_demand_an_owner_for_an_objective(self):
        out = m52.check_requirements_health("mixed")
        for node_id in FOREIGN:
            self.assertNotIn(
                node_id, out,
                f"{node_id} appeared in the requirements health audit",
            )


class TestValidationReportSkipsNonRequirements(unittest.TestCase):
    """7.3 kept its own truncated non-requirement set (goals + test), written before
    `risk` / `change_request` / `solution_scope` existed. On a live project 8 real
    requirements became "Total: 13, validated 30.8%", risks were reported as "reqs
    without traceability to business objectives", and the Ready-for-7.5 gate failed —
    while `check_business_alignment` one screen up answered the same question
    correctly. The shared vocabulary lives in common.NON_REQUIREMENT_NODE_TYPES."""

    def setUp(self):
        self.repo = mixed_repo()
        self._orig_repo = v73._load_repo
        self._orig_ctx = v73._load_context
        self._orig_assum = v73._load_assumptions
        v73._load_repo = lambda project_id: self.repo
        v73._load_context = lambda project_id: {
            "business_goals": [{"id": "BG-001", "title": "Decide within 24 hours"}],
        }
        v73._load_assumptions = lambda project_id: {"assumptions": {}}

    def tearDown(self):
        v73._load_repo = self._orig_repo
        v73._load_context = self._orig_ctx
        v73._load_assumptions = self._orig_assum

    def test_report_counts_only_requirements(self):
        out = v73.get_validation_report("mixed")
        self.assertIn("| Всего активных требований | 1 |", out)

    def test_foreign_nodes_are_not_traceability_orphans(self):
        out = v73.get_validation_report("mixed")
        for node_id in ["RK-001", "CR-001", "SOL-001"]:
            self.assertNotIn(
                node_id, out,
                f"{node_id} is not a requirement — it must not be reported as a "
                f"requirement without traceability to business objectives",
            )


class TestArchitectureSkipsNonRequirements(BaseMCPTest):
    """7.4's SKIP_TYPES had the same truncated set: risks, CRs and the 6.4 scope node
    counted as "active requirements", could never appear in any viewpoint, and
    diluted "Covered by viewpoints %" (30.8% on a live project whose real coverage
    was 8/8). The same number lands in the signed architecture snapshot.

    BaseMCPTest (tmp cwd) because analyze_requirements_architecture WRITES its
    architecture.json — a plain TestCase left a `mixed` project in the real
    working tree on every run."""

    def setUp(self):
        super().setUp()
        self.repo = mixed_repo()
        self._orig = a74._load_repo
        a74._load_repo = lambda project_id: self.repo

    def tearDown(self):
        a74._load_repo = self._orig
        super().tearDown()

    def test_total_active_counts_only_requirements(self):
        import re
        out = a74.analyze_requirements_architecture("mixed")
        # The label dropped the word "active" in re-review N-5 — it announced a status
        # filter the line never had. The claim under test is the COUNT: of a graph
        # holding goals, risks and a scope node, exactly one entry is a requirement.
        self.assertTrue(
            re.search(r"Всего требований:\*\*\s*1\b", out),
            f"Expected exactly 1 requirement, got:\n{out[:600]}",
        )


class TestAllocateSkipsNonRequirements(unittest.TestCase):
    """7.5's hand-written skip set {business, test, change_request} predates the 6.1/
    6.2/6.3/6.4 node types: goals, needs, risks and the scope node landed in the
    "Requirements without priority" table and the BA was asked to assign business
    goal BG-001 to v1/v2/out_of_scope ("Without priority: 16" on a live project)."""

    OPTIONS = {
        "project_id": "mixed", "change_strategy_ref": "",
        "options": [{"option_id": "OPT-001", "title": "Build", "approach": "build",
                     "components": [], "improvement_opportunities": [],
                     "effectiveness_measures": []}],
        "allocation": {}, "created": "2026-07-22", "updated": "2026-07-22",
    }

    def setUp(self):
        self.repo = mixed_repo()
        self._orig_repo = d75._load_repo
        self._orig_do = d75._load_design_options
        self._orig_save = d75._save_design_options
        d75._load_repo = lambda project_id: self.repo
        d75._load_design_options = lambda project_id: dict(self.OPTIONS)
        d75._save_design_options = lambda data: None

    def tearDown(self):
        d75._load_repo = self._orig_repo
        d75._load_design_options = self._orig_do
        d75._save_design_options = self._orig_save

    def test_goals_and_risks_are_not_offered_for_release_allocation(self):
        out = d75.allocate_requirements("mixed", option_id="OPT-001", auto_suggest=True)
        for node_id in FOREIGN:
            self.assertNotIn(
                node_id, out,
                f"{node_id} is not a requirement — the BA must not be asked to "
                f"assign it to a release version",
            )


class TestReuseSkipsNonRequirements(unittest.TestCase):
    """5.2 `check_requirements_health` filters by role, but its neighbour
    `find_reusable_requirements` iterated every node: on a live project the reuse
    report offered a change request as a confirmed candidate (its 5.4 status literal
    is `approved`) and every risk and goal as potential candidates."""

    def setUp(self):
        self.repo = mixed_repo()
        self._orig = m52._load_repo
        m52._load_repo = lambda project_name: self.repo

    def tearDown(self):
        m52._load_repo = self._orig

    def test_foreign_nodes_are_not_reuse_candidates(self):
        out = m52.find_reusable_requirements("mixed")
        for node_id in FOREIGN:
            self.assertNotIn(
                node_id, out,
                f"{node_id} is not a requirement — it cannot be offered for reuse",
            )


class TestApprovedMatrixExcludesAnalysisNodes(unittest.TestCase):
    """5.4 writes status="approved" on the CR node meaning "the change request was
    accepted"; the approved-filter fallback in the 5.1 matrix caught that literal, so
    an accepted CR appeared in the approved-requirements matrix — a document that
    goes into the 5.5 signing package. One literal, two meanings, the ADR-082 class
    in a second field."""

    def setUp(self):
        self.repo = {
            "project": "mixed", "formality_level": "Standard",
            "requirements": [
                {"id": "FR-001", "type": "functional", "title": "Pre-fill from CRM",
                 "version": "1.0", "status": "approved"},
                {"id": "CR-001", "type": "change_request", "title": "Support self-employed",
                 "version": "1.0", "status": "approved"},
                {"id": "SOL-001", "type": "solution_scope", "title": "Solution Scope — mixed",
                 "version": "1.0", "status": "approved"},
            ],
            "links": [],
            "history": [],
        }
        self._orig = t51._load_repo
        t51._load_repo = lambda project_name: self.repo

    def tearDown(self):
        t51._load_repo = self._orig

    def test_cr_and_scope_not_in_approved_matrix(self):
        out = t51.export_traceability_matrix("mixed", filter_status="approved")
        self.assertIn("FR-001", out)
        self.assertNotIn(
            "CR-001", out,
            "an accepted CR is not an approved requirement — 5.4's status literal "
            "must not pass the approved filter",
        )
        self.assertNotIn("SOL-001", out)


if __name__ == "__main__":
    unittest.main()
