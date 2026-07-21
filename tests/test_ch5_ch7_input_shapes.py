"""
tests/test_ch5_ch7_input_shapes.py — chapters 5 and 7 must answer wrong-shaped input
with an error string, not an exception.

The sibling of tests/test_ch4_input_shapes.py, written for the same reason and after
the same discovery: the JSON in these parameters is written by an LLM, so the WRONG
SHAPE IS AN ORDINARY SCENARIO, not an exotic one. Validating that the input PARSES is
not validating that it FITS — every one of these tools checked `json.loads` succeeded
and then immediately used the elements as objects.

An exception escaping an MCP tool is a protocol error: the analyst sees a stack trace
instead of the ❌ line every neighbouring tool returns, and the session is left in an
unclear state. Chapters 3 and 4 were swept for this (CH3-A/B, CH4-A) and given the
shared `parse_json_*` validators; chapters 5 and 7 were not.

The second half covers stored-file corruption. Every `_load_repo` in these chapters
called `json.load` bare, so a damaged repository turned every downstream tool into a
protocol error too. The correct behaviour already existed one module away, in
`common.load_stakeholder_registry`.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import setup_mocks, BaseMCPTest

setup_mocks()

import skills.common as common
import skills.requirements_traceability_mcp as t51
import skills.requirements_prioritize_mcp as t53
import skills.requirements_approve_mcp as t55
import skills.requirements_verify_mcp as t72

PID = "shapes"


class TestWrongShapeReturnsAnErrorNotAnException(BaseMCPTest):
    """A list of STRINGS where a list of OBJECTS is expected — the single most likely
    mistake, because the neighbouring parameters legitimately take bare strings."""

    def _seed_repo(self):
        t51.init_traceability_repo(
            PID, "Standard",
            '[{"id": "FR-001", "type": "functional", "title": "X"}]')

    def test_51_init_traceability_repo(self):
        result = t51.init_traceability_repo(PID, "Standard", '["FR-001", "FR-002"]')
        self.assertIn("❌", result)

    def test_53_add_stakeholder_scores(self):
        self._seed_repo()
        t53.start_prioritization_session(PID, "S1", "MoSCoW")
        result = t53.add_stakeholder_scores(PID, "S1", "sh1", "High", '["FR-001"]')
        self.assertIn("❌", result)

    def test_55_record_approval_decision(self):
        self._seed_repo()
        t55.prepare_approval_package(
            project_name=PID, package_id="PKG-1", package_title="T",
            req_ids_json='["FR-001"]', approach="formal", audience="sponsor")
        result = t55.record_approval_decision(
            project_name=PID, package_id="PKG-1", stakeholder_name="Ivan",
            stakeholder_raci="accountable", decision="approved",
            req_decisions_json='["FR-001"]')
        self.assertIn("❌", result)

    def test_a_bare_object_where_a_list_is_expected(self):
        result = t51.init_traceability_repo(
            PID, "Standard", '{"id": "FR-001", "type": "functional"}')
        self.assertIn("❌", result)

    def test_the_correct_shape_still_works(self):
        """The guard against a validator that rejects everything."""
        result = t51.init_traceability_repo(
            PID, "Standard",
            '[{"id": "FR-001", "type": "functional", "title": "Valid"}]')
        self.assertNotIn("❌", result)


class TestCorruptStoredFileDegradesGracefully(BaseMCPTest):
    """A damaged repository must not turn a read-only report into a protocol error.
    The reference implementation is common.load_stakeholder_registry."""

    def _corrupt_repo(self):
        t51.init_traceability_repo(
            PID, "Standard",
            '[{"id": "FR-001", "type": "functional", "title": "X"}]')
        path = common.data_path(
            PID, f"{common.normalize_project_id(PID)}_traceability_repo.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{ this is not valid json")

    def test_51_check_coverage(self):
        self._corrupt_repo()
        result = t51.check_coverage(PID)
        self.assertIn("❌", result)

    def test_51_export_traceability_matrix(self):
        self._corrupt_repo()
        result = t51.export_traceability_matrix(PID)
        self.assertIn("❌", result)

    def test_72_get_verification_report(self):
        self._corrupt_repo()
        result = t72.get_verification_report(PID)
        self.assertIn("❌", result)

    def test_the_message_names_the_file_so_the_analyst_can_act(self):
        """"Something went wrong" is not actionable; the path is."""
        self._corrupt_repo()
        result = t51.check_coverage(PID)
        self.assertIn("traceability_repo.json", result)

    def test_a_healthy_repository_is_unaffected(self):
        t51.init_traceability_repo(
            PID, "Standard",
            '[{"id": "FR-001", "type": "functional", "title": "X"}]')
        self.assertNotIn("❌", t51.check_coverage(PID))


if __name__ == "__main__":
    unittest.main()
