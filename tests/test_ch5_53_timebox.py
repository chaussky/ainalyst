"""
tests/test_ch5_53_timebox.py — BABOK 5.3, fourth prioritisation method:
Time Boxing / Budgeting (BABOK 10.33.3 .3).

Second fixture, not a rewritten one: `make_test_repo` in conftest is a minimal
legacy graph with two requirement nodes and no priorities. Time boxing needs a
population with differing value labels and enough items to overflow a box, so
this file builds its own repo. tests/test_ch5_53.py stays untouched as the
regression net for MoSCoW / WSJF / ImpactEffort.
"""

import json
import os
import sys
import unittest
from datetime import date
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tests.conftest import setup_mocks, BaseMCPTest, save_test_repo
setup_mocks()

import skills.requirements_prioritize_mcp as mod53

PROJECT = "timebox_test"
SESSION = "Sprint 7"


def make_timebox_repo(project=PROJECT):
    """Five requirement-class nodes with differing stored priorities.

    FR-005 deliberately carries the 7.1 scale (`High`) rather than a MoSCoW label:
    `priority` is written by two producers and the graph fallback has to normalise
    both.
    """
    def node(rid, title, priority=None):
        n = {
            "id": rid,
            "type": "solution",
            "title": title,
            "version": "1.0",
            "status": "confirmed",
            "added": str(date.today()),
        }
        if priority is not None:
            n["priority"] = priority
        return n

    return {
        "project": project,
        "formality_level": "Standard",
        "created": str(date.today()),
        "updated": str(date.today()),
        "requirements": [
            node("FR-001", "Bulk upload", "Must"),
            node("FR-002", "Status notifications", "Should"),
            node("FR-003", "Export to CSV", "Could"),
            node("FR-004", "Audit log", None),
            node("FR-005", "Role management", "High"),
        ],
        "links": [],
        "history": [],
    }


def setup_timebox_repo(project=PROJECT):
    repo = make_timebox_repo(project)
    save_test_repo(repo)
    return repo


def start_timebox(project=PROJECT, session=SESSION, capacity=20,
                  capacity_unit="story points", method="TimeBoxing"):
    with patch("skills.requirements_prioritize_mcp.save_artifact"):
        return mod53.start_prioritization_session(
            project_name=project,
            session_label=session,
            method=method,
            capacity=capacity,
            capacity_unit=capacity_unit,
        )


class TestTimeboxSessionConfig(BaseMCPTest):
    """Task 1 — capacity is the whole technique; a session without it is undefined."""

    def test_capacity_must_be_positive(self):
        setup_timebox_repo()
        out = start_timebox(capacity=0)
        self.assertIn("❌", out)
        self.assertIn("capacity", out)
        # The session must NOT have been created.
        path = mod53._prio_path(PROJECT)
        self.assertFalse(os.path.exists(path))

    def test_negative_capacity_rejected(self):
        setup_timebox_repo()
        out = start_timebox(capacity=-5)
        self.assertIn("❌", out)

    def test_capacity_stored_on_session(self):
        setup_timebox_repo()
        start_timebox(capacity=20, capacity_unit="story points")
        prio = mod53._load_prio(PROJECT)
        session = prio["sessions"][0]
        self.assertEqual(session["capacity"], 20.0)
        self.assertEqual(session["capacity_unit"], "story points")

    def test_blank_unit_defaults_to_units(self):
        setup_timebox_repo()
        start_timebox(capacity=20, capacity_unit="   ")
        session = mod53._load_prio(PROJECT)["sessions"][0]
        self.assertEqual(session["capacity_unit"], "units")

    def test_capacity_on_other_method_is_ignored_but_announced(self):
        """A silently dropped scope limit leaves the BA believing a budget applied."""
        setup_timebox_repo()
        out = start_timebox(capacity=20, method="MoSCoW")
        session = mod53._load_prio(PROJECT)["sessions"][0]
        self.assertIsNone(session["capacity"])
        self.assertIn("ignored", out.lower())
        self.assertIn("MoSCoW", out)

    def test_no_capacity_on_other_method_stays_silent(self):
        setup_timebox_repo()
        out = start_timebox(capacity=0, capacity_unit="", method="MoSCoW")
        self.assertNotIn("ignored", out.lower())

    def test_report_shows_capacity_and_cost_column(self):
        setup_timebox_repo()
        out = start_timebox(capacity=20, capacity_unit="story points")
        self.assertIn("**Capacity:** 20 story points", out)
        self.assertIn("Cost, story points", out)
        # Current priority is shown so the BA can see what the value fallback will use.
        self.assertIn("Current priority", out)


def add_timebox_scores(project=PROJECT, session=SESSION, sh_id="DEV-TEAM",
                       influence="Medium", scores=None):
    if scores is None:
        scores = [{"req_id": "FR-001", "cost": 5}]
    with patch("skills.requirements_prioritize_mcp.save_artifact"):
        return mod53.add_stakeholder_scores(
            project_name=project,
            session_label=session,
            stakeholder_id=sh_id,
            stakeholder_influence=influence,
            scores_json=json.dumps(scores),
        )


class TestTimeboxScoreInput(BaseMCPTest):
    """Task 2 — 'the input parses' is not 'the input fits' (class CH4-A / F-C)."""

    def setUp(self):
        super().setUp()
        setup_timebox_repo()
        start_timebox()

    def test_missing_cost_is_rejected_by_name(self):
        out = add_timebox_scores(scores=[{"req_id": "FR-001", "value": "Must"}])
        self.assertIn("❌", out)
        self.assertIn("FR-001", out)
        self.assertIn("cost", out)

    def test_non_numeric_cost_is_rejected(self):
        out = add_timebox_scores(scores=[{"req_id": "FR-001", "cost": "large"}])
        self.assertIn("❌", out)
        self.assertIn("FR-001", out)

    def test_negative_cost_is_rejected(self):
        out = add_timebox_scores(scores=[{"req_id": "FR-001", "cost": -3}])
        self.assertIn("❌", out)

    def test_zero_cost_is_accepted(self):
        out = add_timebox_scores(scores=[{"req_id": "FR-001", "cost": 0}])
        self.assertIn("✅", out)

    def test_numeric_string_cost_is_accepted(self):
        out = add_timebox_scores(scores=[{"req_id": "FR-001", "cost": "5"}])
        self.assertIn("✅", out)
        stored = mod53._load_prio(PROJECT)["sessions"][0]["stakeholder_scores"]
        self.assertEqual(stored["DEV-TEAM"]["FR-001"]["cost"], 5.0)

    def test_bad_value_label_is_rejected(self):
        out = add_timebox_scores(
            scores=[{"req_id": "FR-001", "cost": 5, "value": "Critical"}])
        self.assertIn("❌", out)
        self.assertIn("Critical", out)

    def test_value_is_optional_and_stored_as_none(self):
        add_timebox_scores(scores=[{"req_id": "FR-001", "cost": 5}])
        stored = mod53._load_prio(PROJECT)["sessions"][0]["stakeholder_scores"]
        self.assertEqual(stored["DEV-TEAM"]["FR-001"], {"cost": 5.0, "value": None})

    def test_value_is_stored_when_given(self):
        add_timebox_scores(
            scores=[{"req_id": "FR-001", "cost": 5, "value": "Must"}])
        stored = mod53._load_prio(PROJECT)["sessions"][0]["stakeholder_scores"]
        self.assertEqual(stored["DEV-TEAM"]["FR-001"]["value"], "Must")

    def test_scalar_json_returns_error_not_exception(self):
        """Class F-C: a wrong SHAPE must be a ❌ line, never a protocol error."""
        with patch("skills.requirements_prioritize_mcp.save_artifact"):
            out = mod53.add_stakeholder_scores(
                project_name=PROJECT, session_label=SESSION,
                stakeholder_id="DEV-TEAM", stakeholder_influence="Medium",
                scores_json='"42"')
        self.assertIn("❌", out)

    def test_list_of_strings_returns_error_not_exception(self):
        with patch("skills.requirements_prioritize_mcp.save_artifact"):
            out = mod53.add_stakeholder_scores(
                project_name=PROJECT, session_label=SESSION,
                stakeholder_id="DEV-TEAM", stakeholder_influence="Medium",
                scores_json='["FR-001", "FR-002"]')
        self.assertIn("❌", out)


class TestFmtNum(unittest.TestCase):
    def test_whole_floats_render_without_decimal(self):
        self.assertEqual(mod53._fmt_num(40.0), "40")
        self.assertEqual(mod53._fmt_num(2.5), "2.5")
        self.assertEqual(mod53._fmt_num(None), "None")


if __name__ == "__main__":
    unittest.main()
