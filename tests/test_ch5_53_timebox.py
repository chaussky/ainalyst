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


class TestAggregateTimebox(unittest.TestCase):
    """Task 3 — the box itself. Pure function, no filesystem."""

    def setUp(self):
        self.repo = make_timebox_repo()

    def agg(self, scores_by_sh, influence=None, capacity=20):
        influence = influence or {sh: "Medium" for sh in scores_by_sh}
        return mod53._aggregate_timebox(scores_by_sh, influence, self.repo, capacity)

    # --- value precedence -------------------------------------------------
    def test_session_value_wins_over_graph(self):
        out = self.agg({"SH-1": {"FR-003": {"cost": 1, "value": "Must"}}})
        self.assertEqual(out["FR-003"]["value_label"], "Must")   # graph says Could
        self.assertEqual(out["FR-003"]["value_source"], "session")

    def test_graph_priority_used_when_no_session_value(self):
        out = self.agg({"SH-1": {"FR-002": {"cost": 1, "value": None}}})
        self.assertEqual(out["FR-002"]["value_label"], "Should")
        self.assertEqual(out["FR-002"]["value_source"], "graph")

    def test_graph_high_medium_low_are_normalised(self):
        """7.1 writes High/Medium/Low into the same field 5.3 writes MoSCoW into."""
        out = self.agg({"SH-1": {"FR-005": {"cost": 1, "value": None}}})
        self.assertEqual(out["FR-005"]["value_label"], "Must")   # graph says High
        self.assertEqual(out["FR-005"]["value_source"], "graph")

    def test_default_when_neither_session_nor_graph(self):
        out = self.agg({"SH-1": {"FR-004": {"cost": 1, "value": None}}})
        self.assertEqual(out["FR-004"]["value_label"], "Could")
        self.assertEqual(out["FR-004"]["value_source"], "default")

    def test_session_values_are_influence_weighted(self):
        """Reuses _aggregate_moscow, so a High-influence voice outweighs a Low one."""
        out = self.agg(
            {"SH-HIGH": {"FR-004": {"cost": 1, "value": "Must"}},
             "SH-LOW": {"FR-004": {"cost": 1, "value": "Won't"}}},
            influence={"SH-HIGH": "High", "SH-LOW": "Low"})
        self.assertEqual(out["FR-004"]["value_source"], "session")
        self.assertIn(out["FR-004"]["value_label"], ("Must", "Should"))

    def test_stakeholder_without_value_does_not_dilute_the_vote(self):
        out = self.agg(
            {"SH-1": {"FR-004": {"cost": 1, "value": "Must"}},
             "DEV-TEAM": {"FR-004": {"cost": 8, "value": None}}},
            influence={"SH-1": "Medium", "DEV-TEAM": "High"})
        self.assertEqual(out["FR-004"]["value_label"], "Must")

    # --- cost -------------------------------------------------------------
    def test_cost_is_averaged_without_influence_weighting(self):
        out = self.agg(
            {"SH-HIGH": {"FR-001": {"cost": 10, "value": None}},
             "SH-LOW": {"FR-001": {"cost": 2, "value": None}}},
            influence={"SH-HIGH": "High", "SH-LOW": "Low"})
        self.assertEqual(out["FR-001"]["cost"], 6.0)       # plain mean, not 8.0
        self.assertEqual(out["FR-001"]["cost_spread"], 8.0)

    # --- fill -------------------------------------------------------------
    def test_fill_order_is_value_then_cheapest_then_id(self):
        out = self.agg({"SH-1": {
            "FR-001": {"cost": 5, "value": "Must"},
            "FR-002": {"cost": 3, "value": "Must"},
            "FR-003": {"cost": 1, "value": "Could"},
        }}, capacity=100)
        placed = sorted((d["cumulative"], r) for r, d in out.items()
                        if d["cumulative"] is not None)
        self.assertEqual([r for _, r in placed], ["FR-002", "FR-001", "FR-003"])

    def test_cost_exactly_equal_to_remaining_capacity_fits(self):
        out = self.agg({"SH-1": {
            "FR-001": {"cost": 6, "value": "Must"},
            "FR-002": {"cost": 4, "value": "Should"},
        }}, capacity=10)
        self.assertTrue(out["FR-001"]["in_box"])
        self.assertTrue(out["FR-002"]["in_box"])

    def test_continue_fill_takes_a_cheaper_item_below_a_skipped_one(self):
        out = self.agg({"SH-1": {
            "FR-001": {"cost": 9, "value": "Must"},
            "FR-002": {"cost": 8, "value": "Should"},
            "FR-003": {"cost": 1, "value": "Could"},
        }}, capacity=10)
        self.assertTrue(out["FR-001"]["in_box"])
        self.assertFalse(out["FR-002"]["in_box"])   # 9 + 8 > 10
        self.assertTrue(out["FR-003"]["in_box"])    # 9 + 1 == 10
        self.assertTrue(out["FR-002"].get("skipped_over"))
        self.assertEqual(out["FR-002"]["remaining_at_skip"], 1.0)

    def test_cut_requirement_becomes_wont(self):
        out = self.agg({"SH-1": {
            "FR-001": {"cost": 20, "value": "Must"},
            "FR-002": {"cost": 20, "value": "Should"},
        }}, capacity=20)
        self.assertEqual(out["FR-002"]["priority"], "Won't")

    def test_requirement_in_box_keeps_its_own_value_label(self):
        """D2: the box line is the Won't boundary; it does not promote everything."""
        out = self.agg({"SH-1": {
            "FR-003": {"cost": 1, "value": "Could"},
        }}, capacity=20)
        self.assertTrue(out["FR-003"]["in_box"])
        self.assertEqual(out["FR-003"]["priority"], "Could")

    # --- population and unestimated ---------------------------------------
    def test_box_covers_the_whole_backlog_not_just_scored_items(self):
        """The deliverable is 'what of the scope fits', so unscored items appear."""
        out = self.agg({"SH-1": {"FR-001": {"cost": 5, "value": "Must"}}},
                       capacity=20)
        self.assertEqual(set(out), {"FR-001", "FR-002", "FR-003", "FR-004", "FR-005"})

    def test_unestimated_requirement_gets_no_priority(self):
        """Marking it Won't would be a conclusion drawn from missing data (CH3-D).

        FR-004 is reachable ONLY through the repo population: add_stakeholder_scores
        requires a cost, so no scored entry can ever carry cost=None. Feeding the
        aggregator {"cost": None} directly would test a shape the producer never
        writes.
        """
        out = self.agg({"SH-1": {"FR-001": {"cost": 5, "value": "Must"}}},
                       capacity=20)
        self.assertIsNone(out["FR-004"]["priority"])
        self.assertFalse(out["FR-004"]["in_box"])
        self.assertIsNone(out["FR-004"]["cost"])

    def test_scored_id_absent_from_the_graph_still_surfaces(self):
        """save_prioritization_result names typo'd ids; the union keeps that alive."""
        out = self.agg({"SH-1": {"FR-01": {"cost": 2, "value": "Must"}}}, capacity=20)
        self.assertIn("FR-01", out)
        self.assertTrue(out["FR-01"]["in_box"])

    def test_deprecated_requirements_are_left_out(self):
        self.repo["requirements"][3]["status"] = "deprecated"   # FR-004
        out = self.agg({"SH-1": {"FR-001": {"cost": 5, "value": "Must"}}},
                       capacity=20)
        self.assertNotIn("FR-004", out)

    def test_non_requirement_nodes_are_left_out(self):
        self.repo["requirements"].append(
            {"id": "RISK-001", "type": "risk", "title": "Vendor delay",
             "version": "1.0", "status": "confirmed"})
        out = self.agg({"SH-1": {"FR-001": {"cost": 5, "value": "Must"}}},
                       capacity=20)
        self.assertNotIn("RISK-001", out)

    def test_determinism_across_runs(self):
        scores = {"SH-1": {
            "FR-001": {"cost": 5, "value": "Must"},
            "FR-002": {"cost": 5, "value": "Must"},
            "FR-003": {"cost": 5, "value": "Must"},
        }}
        first = self.agg(scores, capacity=10)
        second = self.agg(scores, capacity=10)
        self.assertEqual({r: d["in_box"] for r, d in first.items()},
                         {r: d["in_box"] for r, d in second.items()})


class TestMustInflationDenominator(unittest.TestCase):
    """Task 3 — unplaced requirements must not dilute the Must ratio."""

    def test_entries_without_priority_are_excluded(self):
        result = mod53._check_must_inflation({
            "FR-001": {"priority": "Must"},
            "FR-002": {"priority": "Must"},
            "FR-003": {"priority": "Could"},
            "FR-004": {"priority": None},
        })
        self.assertEqual(result["must_ratio"], 0.67)
        self.assertTrue(result["inflated"])

    def test_existing_methods_unaffected(self):
        result = mod53._check_must_inflation({
            "FR-001": {"priority": "Must"},
            "FR-002": {"priority": "Could"},
        })
        self.assertEqual(result["must_ratio"], 0.5)


if __name__ == "__main__":
    unittest.main()
