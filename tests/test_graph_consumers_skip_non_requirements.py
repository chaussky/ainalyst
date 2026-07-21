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
from tests.conftest import setup_mocks

setup_mocks()

import skills.requirements_verify_mcp as v72
import skills.requirements_prioritize_mcp as p53
import skills.requirements_maintain_mcp as m52

FOREIGN = ["BN-001", "BG-001", "RK-001", "CR-001"]


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
        self.assertIn("| Total active reqs | 1 |", out)


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


if __name__ == "__main__":
    unittest.main()
