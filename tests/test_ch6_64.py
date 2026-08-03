"""
tests/test_ch6_64.py — Tests for task 6.4 (Define Change Strategy)

Coverage:
  - scope_change_strategy          (14 tests)
  - define_solution_scope          (15 tests)
  - assess_enterprise_readiness    (15 tests)
  - add_strategy_option            (14 tests)
  - compare_strategy_options       (16 tests)
  - define_transition_states       (13 tests)
  - save_change_strategy           (15 tests)
  - Integration pipeline tests     (10 tests)
Total: ~112 tests
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

from skills.change_strategy_mcp import (
    scope_change_strategy,
    define_solution_scope,
    assess_enterprise_readiness,
    add_strategy_option,
    compare_strategy_options,
    define_transition_states,
    save_change_strategy,
    _safe, _next_option_id, _readiness_verdict,
    _strategy_path, _scope_path, _gap_file_path,
    DO_NOTHING_OPTION_ID,
    GAP_ANALYSIS_FILENAME,
    DATA_DIR,
    _declared_element, _gap_coverage, _gap_file_seen, _gap_coverage_lines,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROJECT = "test_project_64"
TODAY = str(date.today())


def _load_strategy(project_id: str = PROJECT) -> dict:
    path = _strategy_path(project_id)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _make_scope(project_id: str = PROJECT, **kwargs):
    params = dict(
        project_id=project_id,
        change_type="technology_implementation",
        time_horizon_months=12,
        methodology="agile",
        source_project_ids="[]",
    )
    params.update(kwargs)
    return scope_change_strategy(**params)


def _make_readiness(project_id: str = PROJECT, **kwargs):
    params = dict(
        project_id=project_id,
        leadership_commitment=4,
        cultural_readiness=3,
        resource_availability=3,
        operational_readiness=3,
        technical_readiness=4,
        change_history=3,
    )
    params.update(kwargs)
    return assess_enterprise_readiness(**params)


def _make_scope_def(project_id: str = PROJECT, **kwargs):
    caps = [
        {"name": "CRM System", "category": "technology", "description": "New CRM",
         "gap_severity": "high", "gap_source": "6.2:gap_analysis", "in_scope": True},
        {"name": "Staff Training", "category": "people", "description": "Training sessions",
         "gap_severity": "medium", "gap_source": "manual", "in_scope": True},
    ]
    params = dict(
        project_id=project_id,
        capabilities_json=json.dumps(caps),
        explicitly_excluded='["Mobile Application"]',
        scope_summary="CRM implementation with staff training.",
    )
    params.update(kwargs)
    return define_solution_scope(**params)


def _add_option(project_id: str = PROJECT, **kwargs):
    params = dict(
        project_id=project_id,
        name="Phased CRM Replacement",
        strategy_type="phased",
        investment_level="medium",
        timeline_months=12,
        pros='["Manageable risk", "Early value delivery"]',
        cons='["Extended co-existence period"]',
        linked_risks='["RK-001"]',
        risk_impact="mitigates",
    )
    params.update(kwargs)
    return add_strategy_option(**params)


def _setup_full_pipeline(project_id: str = PROJECT) -> dict:
    """Creates a fully populated change strategy for final-step tests."""
    _make_scope(project_id)
    _make_scope_def(project_id)
    _make_readiness(project_id)
    _add_option(project_id, name="Phased Implementation", strategy_type="phased")
    _add_option(project_id, name="Big Bang Launch", strategy_type="big_bang",
                investment_level="high", timeline_months=4)

    # compare
    scores = {
        "OPT-001": {"alignment_to_goals": 4, "risk_mitigation": 4, "cost": 3,
                    "time_to_value": 3, "org_readiness_fit": 3, "feasibility": 4},
        "OPT-002": {"alignment_to_goals": 4, "risk_mitigation": 2, "cost": 2,
                    "time_to_value": 5, "org_readiness_fit": 2, "feasibility": 3},
        DO_NOTHING_OPTION_ID: {"alignment_to_goals": 1, "risk_mitigation": 1, "cost": 5,
                                "time_to_value": 1, "org_readiness_fit": 1, "feasibility": 1},
    }
    compare_strategy_options(
        project_id=project_id,
        scores_json=json.dumps(scores),
        opportunity_cost="We forgo fast ROI in favor of manageable risk.",
    )

    define_transition_states(
        project_id=project_id,
        phase_number=1,
        phase_name="Basic CRM",
        duration_months=4,
        capabilities_delivered='["CRM System"]',
        gaps_closed='["gap_crm_data"]',
        risks_remaining='["RK-002"]',
        value_realizable="Operators can see customer history",
    )
    define_transition_states(
        project_id=project_id,
        phase_number=2,
        phase_name="Analytics",
        duration_months=5,
        capabilities_delivered='["Analytics"]',
        gaps_closed='["gap_reporting"]',
        risks_remaining='[]',
        value_realizable="60% reduction in manual reporting",
    )
    return _load_strategy(project_id)


# ---------------------------------------------------------------------------
# Utilities (unit)
# ---------------------------------------------------------------------------

class TestUtils(BaseMCPTest):

    def test_safe(self):
        self.assertEqual(_safe("CRM Project"), "crm_project")
        self.assertEqual(_safe("test"), "test")

    def test_next_option_id_empty(self):
        self.assertEqual(_next_option_id([]), "OPT-001")

    def test_next_option_id_with_do_nothing(self):
        opts = [{"option_id": "OPT-000"}]
        self.assertEqual(_next_option_id(opts), "OPT-001")

    def test_next_option_id_increments(self):
        opts = [{"option_id": "OPT-000"}, {"option_id": "OPT-001"}, {"option_id": "OPT-002"}]
        self.assertEqual(_next_option_id(opts), "OPT-003")

    def test_readiness_verdict_ready(self):
        self.assertEqual(_readiness_verdict(4.0), "ready")
        self.assertEqual(_readiness_verdict(5.0), "ready")

    def test_readiness_verdict_caution(self):
        self.assertEqual(_readiness_verdict(3.5), "proceed_with_caution")
        self.assertEqual(_readiness_verdict(2.5), "proceed_with_caution")

    def test_readiness_verdict_not_ready(self):
        self.assertEqual(_readiness_verdict(2.4), "not_ready")
        self.assertEqual(_readiness_verdict(1.0), "not_ready")


# ---------------------------------------------------------------------------
# scope_change_strategy
# ---------------------------------------------------------------------------

class TestScopeChangeStrategy(BaseMCPTest):

    def test_basic_success(self):
        result = _make_scope()
        self.assertIn("✅", result)
        self.assertIn(PROJECT, result)

    def test_scope_file_created(self):
        _make_scope()
        self.assertTrue(os.path.exists(_scope_path(PROJECT)))

    def test_strategy_file_created(self):
        _make_scope()
        self.assertTrue(os.path.exists(_strategy_path(PROJECT)))

    def test_do_nothing_auto_added(self):
        _make_scope()
        strategy = _load_strategy()
        options = strategy["change_strategy"]["options"]
        do_nothing = next((o for o in options if o["option_id"] == DO_NOTHING_OPTION_ID), None)
        self.assertIsNotNone(do_nothing)

    def test_do_nothing_is_auto_added_flag(self):
        _make_scope()
        strategy = _load_strategy()
        do_nothing = next(o for o in strategy["change_strategy"]["options"]
                          if o["option_id"] == DO_NOTHING_OPTION_ID)
        self.assertTrue(do_nothing.get("auto_added"))

    def test_scope_fields_saved(self):
        _make_scope(change_type="transformation", time_horizon_months=24, methodology="waterfall")
        strategy = _load_strategy()
        scope = strategy["scope"]
        self.assertEqual(scope["change_type"], "transformation")
        self.assertEqual(scope["time_horizon_months"], 24)
        self.assertEqual(scope["methodology"], "waterfall")

    def test_invalid_time_horizon(self):
        result = _make_scope(time_horizon_months=0)
        self.assertIn("❌", result)

    def test_invalid_source_ids_json(self):
        result = _make_scope(source_project_ids="not-json")
        self.assertIn("❌", result)

    def test_graceful_degradation_missing_artifacts(self):
        result = _make_scope(source_project_ids='["nonexistent_project"]')
        self.assertIn("✅", result)  # does not crash
        self.assertIn("⚠️", result)  # warning present

    def test_autoimport_from_6_1(self):
        """Test import of business_needs from 6.1 (REAL 6.1 structure)."""
        needs_data = {
            "needs": [
                {"id": "BN-001", "need_title": "CRM Required", "priority": "High"}
            ]
        }
        needs_path = data_file(_safe(PROJECT), "business_needs.json")
        with open(needs_path, "w", encoding="utf-8") as f:
            json.dump(needs_data, f)

        result = _make_scope(source_project_ids=f'["{PROJECT}"]')
        strategy = _load_strategy()
        bns = strategy["imported_context"]["business_needs"]
        self.assertTrue(len(bns) > 0)
        self.assertEqual(bns[0]["id"], "BN-001")

    def test_autoimport_from_6_2(self):
        """Test import of business_goals from 6.2 (REAL 6.2: goals live in the
        future_state_goals.json file with a goal_title field)."""
        goals_data = {"goals": [{"id": "BG-001", "goal_title": "NPS growth by 15%"}]}
        goals_path = data_file(_safe(PROJECT), "future_state_goals.json")
        with open(goals_path, "w", encoding="utf-8") as f:
            json.dump(goals_data, f)

        _make_scope(source_project_ids=f'["{PROJECT}"]')
        strategy = _load_strategy()
        bgs = strategy["imported_context"]["business_goals"]
        self.assertTrue(len(bgs) > 0)
        self.assertEqual(bgs[0]["id"], "BG-001")
        self.assertEqual(bgs[0]["title"], "NPS growth by 15%")

    def test_autoimport_from_6_3(self):
        """Test import of risks from 6.3."""
        risk_data = {
            "risks": [
                {"risk_id": "RK-001", "description": "Integration risk",
                 "status": "identified", "zone": "high", "risk_score": 16,
                 "response_strategy": "mitigate"}
            ]
        }
        risk_path = data_file(_safe(PROJECT), "risk_assessment.json")
        with open(risk_path, "w", encoding="utf-8") as f:
            json.dump(risk_data, f)

        _make_scope(source_project_ids=f'["{PROJECT}"]')
        strategy = _load_strategy()
        risks = strategy["imported_context"]["risks"]
        self.assertTrue(len(risks) > 0)
        self.assertEqual(risks[0]["id"], "RK-001")

    def test_do_nothing_not_duplicated_on_second_call(self):
        _make_scope()
        _make_scope()  # second call
        strategy = _load_strategy()
        do_nothing_count = sum(1 for o in strategy["change_strategy"]["options"]
                               if o["option_id"] == DO_NOTHING_OPTION_ID)
        self.assertEqual(do_nothing_count, 1)

    def test_ba_notes_saved(self):
        _make_scope(ba_notes="Regulatory deadline — Q2 2025")
        strategy = _load_strategy()
        self.assertEqual(strategy["scope"]["ba_notes"], "Regulatory deadline — Q2 2025")


def _write_gap_file(project_id: str = PROJECT, gaps=None):
    """Builds a 6.2 gap analysis by hand, in the shape run_gap_analysis writes."""
    if gaps is None:
        gaps = [
            {"element": "technology", "element_label": "Technology and Infrastructure",
             "current_description": "Paper intake", "future_description": "Portal intake",
             "gap_summary": "Current: paper... -> Target: portal...",
             "change_type": "improve", "complexity": "high"},
            {"element": "policies", "element_label": "Policies",
             "current_description": None, "future_description": "New retention policy",
             "gap_summary": "No current state - created from scratch",
             "change_type": "new", "complexity": "medium"},
        ]
    data = {"project_id": project_id, "has_current_state_baseline": True,
            "gaps": gaps, "created": TODAY, "updated": TODAY}
    path = data_file(project_id, GAP_ANALYSIS_FILENAME)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return path


def _write_gap_file_raw(project_id: str, content):
    """Writes ANY JSON value as the gap analysis file's top level — including
    non-dict shapes (`[]`, `0`, ...) that `_write_gap_file` cannot produce, since
    it always wraps `gaps` inside a dict."""
    path = data_file(project_id, GAP_ANALYSIS_FILENAME)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(content, f)
    return path


class TestGapAnalysisImport(BaseMCPTest):

    def test_gaps_are_imported_into_the_mirror(self):
        _write_gap_file()
        _make_scope(source_project_ids=f'["{PROJECT}"]')
        gaps = _load_strategy()["imported_context"]["gaps"]
        self.assertEqual([g["element"] for g in gaps], ["technology", "policies"])
        self.assertEqual(gaps[0]["complexity"], "high")
        self.assertEqual(gaps[0]["change_type"], "improve")
        self.assertEqual(gaps[0]["source_project"], PROJECT)

    def test_the_reply_names_the_imported_elements(self):
        """The joined element list, not a bare "technology": _make_scope defaults to
        change_type="technology_implementation", which the header prints on every run,
        so asserting the substring alone holds with the join deleted."""
        _write_gap_file()
        result = _make_scope(source_project_ids=f'["{PROJECT}"]')
        self.assertIn("Gap analysis (6.2)", result)
        self.assertIn("technology, policies", result)

    def test_a_project_with_ONLY_a_gap_analysis_still_gets_the_context_header(self):
        """The 'Imported context' header was gated on the other three sources.
        A project whose only artefact is a gap analysis must not lose the evidence."""
        _write_gap_file()
        result = _make_scope(source_project_ids=f'["{PROJECT}"]')
        self.assertIn("Imported context", result)
        self.assertIn("Gap analysis (6.2)", result)

    def test_a_missing_gap_analysis_warns_and_does_not_block(self):
        result = _make_scope(source_project_ids=f'["{PROJECT}"]')
        self.assertIn("✅", result)
        self.assertIn("6.2 gap_analysis not found", result)
        self.assertEqual(_load_strategy()["imported_context"]["gaps"], [])

    def test_the_mirror_is_RECOMPUTED_on_a_re_run_not_merged(self):
        """imported_context mirrors a source file. A merge would let an element that
        6.2 has since dropped outlive the analysis that named it."""
        _write_gap_file()
        _make_scope(source_project_ids=f'["{PROJECT}"]')
        _write_gap_file(gaps=[{"element": "assets", "element_label": "Internal Assets",
                               "gap_summary": "s", "change_type": "new",
                               "complexity": "low"}])
        _make_scope(source_project_ids=f'["{PROJECT}"]')
        gaps = _load_strategy()["imported_context"]["gaps"]
        self.assertEqual([g["element"] for g in gaps], ["assets"])

    def test_a_gap_without_an_element_is_skipped_not_imported_as_blank(self):
        _write_gap_file(gaps=[
            {"element": "", "gap_summary": "s", "complexity": "low"},
            {"element": "   ", "gap_summary": "s", "complexity": "low"},
            {"element": 7, "gap_summary": "s", "complexity": "low"},
            "not a dict",
            {"element": "technology", "gap_summary": "s", "complexity": "low"},
        ])
        _make_scope(source_project_ids=f'["{PROJECT}"]')
        gaps = _load_strategy()["imported_context"]["gaps"]
        self.assertEqual([g["element"] for g in gaps], ["technology"])

    def test_the_capabilities_of_the_analyst_are_never_touched_by_the_import(self):
        """The whole point: the import writes context, never the BA's own judgement."""
        _make_scope()
        _make_scope_def()
        before = _load_strategy()["solution_scope"]
        _write_gap_file()
        _make_scope(source_project_ids=f'["{PROJECT}"]')
        self.assertEqual(_load_strategy()["solution_scope"], before)

    def test_a_corrupt_gap_file_is_reported_not_silently_skipped(self):
        path = data_file(PROJECT, GAP_ANALYSIS_FILENAME)
        with open(path, "w", encoding="utf-8") as f:
            f.write("{not json")
        result = _make_scope(source_project_ids=f'["{PROJECT}"]')
        self.assertIn("❌", result)
        self.assertIn("gap_analysis", result)

    def test_a_top_level_list_is_degraded_not_crashed(self):
        """Regression: `if gap_data is not None:` reached `gap_data.get("gaps", ...)`
        on a bare `[]`, and `list` has no `.get` — an unhandled AttributeError on
        step 1 of the pipeline instead of a warning. A dict is the only shape this
        importer can read `gaps` out of; everything else non-None must degrade."""
        _write_gap_file_raw(PROJECT, [])
        result = _make_scope(source_project_ids=f'["{PROJECT}"]')
        self.assertIn("✅", result)
        self.assertEqual(_load_strategy()["imported_context"]["gaps"], [])

    def test_a_top_level_int_is_degraded_not_crashed(self):
        """Same regression, `int` this time — `0` has no `.get` either."""
        _write_gap_file_raw(PROJECT, 0)
        result = _make_scope(source_project_ids=f'["{PROJECT}"]')
        self.assertIn("✅", result)
        self.assertEqual(_load_strategy()["imported_context"]["gaps"], [])

    def test_an_unusable_top_level_shape_is_not_reported_as_not_found(self):
        """A file that exists but is the wrong shape must stay distinguishable from
        a missing file — 'not found' sends the analyst hunting for a file they
        already have, instead of fixing the one that's actually broken."""
        _write_gap_file_raw(PROJECT, [])
        result = _make_scope(source_project_ids=f'["{PROJECT}"]')
        self.assertNotIn("6.2 gap_analysis not found", result)
        self.assertIn(
            f"6.2 gap_analysis for '{PROJECT}' was read but holds no usable "
            f"elements", result)

    def test_context_elements_are_named_and_counted_in_the_reply(self):
        """Regression: the reply printed '4 elements' while the coverage block one
        call later said '(1 of 2 analysed)', with nothing on the page explaining why
        4 and 2 were both true. The reply must name how many of its own count are
        context elements, so the two numbers reconcile without outside knowledge."""
        _write_gap_file(gaps=[
            {"element": "business_needs", "gap_summary": "s", "complexity": "low"},
            {"element": "technology", "gap_summary": "s", "complexity": "high"},
            {"element": "policies", "gap_summary": "s", "complexity": "medium"},
            {"element": "external", "gap_summary": "s", "complexity": "low"},
        ])
        result = _make_scope(source_project_ids=f'["{PROJECT}"]')
        self.assertIn("4 elements", result)
        self.assertIn("of which 2 are context", result)
        self.assertIn("business_needs, external", result)

        # The reconciliation itself: total unique elements minus context elements
        # is exactly what the coverage block calls "analysed" on the next call.
        cov = _gap_coverage(_load_strategy())
        self.assertEqual(len(cov["context_elements"]), 2)
        self.assertEqual(len(cov["analysed"]), 4 - len(cov["context_elements"]))

    def test_no_context_line_when_no_context_elements_are_present(self):
        _write_gap_file()  # technology, policies only — no business_needs/external
        result = _make_scope(source_project_ids=f'["{PROJECT}"]')
        self.assertIn("Gap analysis (6.2)", result)
        self.assertNotIn("of which", result)

    def test_singular_wording_for_a_single_context_element(self):
        _write_gap_file(gaps=[
            {"element": "external", "gap_summary": "s", "complexity": "low"},
            {"element": "technology", "gap_summary": "s", "complexity": "high"},
        ])
        result = _make_scope(source_project_ids=f'["{PROJECT}"]')
        self.assertIn("of which 1 is context", result)


# ---------------------------------------------------------------------------
# define_solution_scope
# ---------------------------------------------------------------------------

class TestDefineSolutionScope(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _make_scope()

    def test_basic_success(self):
        result = _make_scope_def()
        self.assertIn("✅", result)

    def test_capabilities_saved(self):
        _make_scope_def()
        strategy = _load_strategy()
        caps = strategy["solution_scope"]["capabilities"]
        self.assertEqual(len(caps), 2)

    def test_categories_in_output(self):
        result = _make_scope_def()
        self.assertIn("technology", result)
        self.assertIn("people", result)

    def test_excluded_saved(self):
        _make_scope_def()
        strategy = _load_strategy()
        excluded = strategy["solution_scope"]["explicitly_excluded"]
        self.assertIn("Mobile Application", excluded)

    def test_scope_summary_saved(self):
        _make_scope_def(scope_summary="Project X — CRM Replacement")
        strategy = _load_strategy()
        self.assertEqual(strategy["solution_scope"]["scope_summary"], "Project X — CRM Replacement")

    def test_invalid_json(self):
        result = define_solution_scope(PROJECT, capabilities_json="not-json")
        self.assertIn("❌", result)

    def test_not_list(self):
        result = define_solution_scope(PROJECT, capabilities_json='{"a": 1}')
        self.assertIn("❌", result)

    def test_missing_name_field(self):
        caps = [{"category": "technology", "gap_severity": "high", "in_scope": True}]
        result = define_solution_scope(PROJECT, capabilities_json=json.dumps(caps))
        self.assertIn("❌", result)

    def test_invalid_category(self):
        caps = [{"name": "Test", "category": "invalid_cat", "gap_severity": "high", "in_scope": True}]
        result = define_solution_scope(PROJECT, capabilities_json=json.dumps(caps))
        self.assertIn("❌", result)

    def test_invalid_gap_severity(self):
        caps = [{"name": "Test", "category": "technology", "gap_severity": "extreme", "in_scope": True}]
        result = define_solution_scope(PROJECT, capabilities_json=json.dumps(caps))
        self.assertIn("❌", result)

    def test_gap_severity_stats(self):
        caps = [
            {"name": "A", "category": "technology", "gap_severity": "high", "in_scope": True},
            {"name": "B", "category": "process", "gap_severity": "low", "in_scope": True},
        ]
        result = define_solution_scope(PROJECT, capabilities_json=json.dumps(caps))
        self.assertIn("high", result)
        self.assertIn("low", result)

    def test_out_of_scope_capability(self):
        caps = [
            {"name": "In", "category": "technology", "gap_severity": "high", "in_scope": True},
            {"name": "Out", "category": "technology", "gap_severity": "none", "in_scope": False},
        ]
        _make_scope_def(capabilities_json=json.dumps(caps))
        strategy = _load_strategy()
        in_scope = [c for c in strategy["solution_scope"]["capabilities"] if c.get("in_scope")]
        out_scope = [c for c in strategy["solution_scope"]["capabilities"] if not c.get("in_scope")]
        self.assertEqual(len(in_scope), 1)
        self.assertEqual(len(out_scope), 1)

    def test_gap_source_manual_default(self):
        caps = [{"name": "Test Cap", "category": "data", "gap_severity": "medium", "in_scope": True}]
        _make_scope_def(capabilities_json=json.dumps(caps))
        strategy = _load_strategy()
        cap = strategy["solution_scope"]["capabilities"][0]
        self.assertEqual(cap["gap_source"], "manual")

    def test_empty_excluded_list(self):
        result = _make_scope_def(explicitly_excluded="[]")
        self.assertIn("✅", result)

    def test_multiple_categories(self):
        caps = [
            {"name": "P1", "category": "process", "gap_severity": "low", "in_scope": True},
            {"name": "P2", "category": "process", "gap_severity": "medium", "in_scope": True},
            {"name": "T1", "category": "technology", "gap_severity": "high", "in_scope": True},
        ]
        result = _make_scope_def(capabilities_json=json.dumps(caps))
        self.assertIn("process", result)
        self.assertIn("technology", result)


# ---------------------------------------------------------------------------
# assess_enterprise_readiness
# ---------------------------------------------------------------------------

class TestAssessEnterpriseReadiness(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _make_scope()

    def test_basic_success(self):
        result = _make_readiness()
        self.assertIn("✅", result)

    def test_readiness_saved(self):
        _make_readiness()
        strategy = _load_strategy()
        readiness = strategy["enterprise_readiness"]
        self.assertIn("readiness_score", readiness)
        self.assertIn("verdict", readiness)

    def test_all_5_score_is_ready(self):
        result = _make_readiness(
            leadership_commitment=5, cultural_readiness=5,
            resource_availability=5, operational_readiness=5,
            technical_readiness=5, change_history=5,
        )
        self.assertIn("ready", result)
        strategy = _load_strategy()
        self.assertEqual(strategy["enterprise_readiness"]["verdict"], "ready")

    def test_all_1_score_is_not_ready(self):
        _make_readiness(
            leadership_commitment=1, cultural_readiness=1,
            resource_availability=1, operational_readiness=1,
            technical_readiness=1, change_history=1,
        )
        strategy = _load_strategy()
        self.assertEqual(strategy["enterprise_readiness"]["verdict"], "not_ready")

    def test_mixed_score_caution(self):
        _make_readiness(
            leadership_commitment=3, cultural_readiness=3,
            resource_availability=3, operational_readiness=3,
            technical_readiness=3, change_history=3,
        )
        strategy = _load_strategy()
        self.assertEqual(strategy["enterprise_readiness"]["verdict"], "proceed_with_caution")

    def test_invalid_score_low(self):
        result = _make_readiness(leadership_commitment=0)
        self.assertIn("❌", result)

    def test_invalid_score_high(self):
        result = _make_readiness(cultural_readiness=6)
        self.assertIn("❌", result)

    def test_readiness_score_calculation(self):
        _make_readiness(
            leadership_commitment=4, cultural_readiness=4,
            resource_availability=4, operational_readiness=4,
            technical_readiness=4, change_history=4,
        )
        strategy = _load_strategy()
        self.assertAlmostEqual(strategy["enterprise_readiness"]["readiness_score"], 4.0)

    def test_rationale_saved(self):
        _make_readiness(leadership_rationale="Sponsor personally attends meetings")
        strategy = _load_strategy()
        dims = strategy["enterprise_readiness"]["dimensions"]
        self.assertEqual(dims["leadership_commitment"]["rationale"], "Sponsor personally attends meetings")

    def test_6_dimensions_all_present(self):
        _make_readiness()
        strategy = _load_strategy()
        dims = strategy["enterprise_readiness"]["dimensions"]
        expected = [
            "leadership_commitment", "cultural_readiness", "resource_availability",
            "operational_readiness", "technical_readiness", "change_history",
        ]
        for d in expected:
            self.assertIn(d, dims)

    def test_weak_dimension_mentioned_in_output(self):
        result = _make_readiness(
            leadership_commitment=2, cultural_readiness=3,
            resource_availability=3, operational_readiness=3,
            technical_readiness=3, change_history=3,
        )
        self.assertIn("⚠️", result)

    def test_assessed_on_date(self):
        _make_readiness()
        strategy = _load_strategy()
        self.assertEqual(strategy["enterprise_readiness"]["assessed_on"], TODAY)

    def test_score_bar_in_output(self):
        result = _make_readiness()
        self.assertIn("▪", result)

    def test_score_4_verdict_ready(self):
        _make_readiness(
            leadership_commitment=4, cultural_readiness=4,
            resource_availability=4, operational_readiness=4,
            technical_readiness=4, change_history=4,
        )
        strategy = _load_strategy()
        self.assertEqual(strategy["enterprise_readiness"]["verdict"], "ready")

    def test_overwrite_on_second_call(self):
        _make_readiness(leadership_commitment=3)
        _make_readiness(leadership_commitment=5)
        strategy = _load_strategy()
        dims = strategy["enterprise_readiness"]["dimensions"]
        self.assertEqual(dims["leadership_commitment"]["score"], 5)


# ---------------------------------------------------------------------------
# add_strategy_option
# ---------------------------------------------------------------------------

class TestAddStrategyOption(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _make_scope()

    def test_basic_success(self):
        result = _add_option()
        self.assertIn("✅", result)
        self.assertIn("OPT-001", result)

    def test_option_saved(self):
        _add_option()
        strategy = _load_strategy()
        real_opts = [o for o in strategy["change_strategy"]["options"]
                     if o["strategy_type"] != "do_nothing"]
        self.assertEqual(len(real_opts), 1)

    def test_option_id_increments(self):
        _add_option()
        _add_option(name="Second Option", strategy_type="big_bang")
        strategy = _load_strategy()
        ids = [o["option_id"] for o in strategy["change_strategy"]["options"]
               if o["strategy_type"] != "do_nothing"]
        self.assertIn("OPT-001", ids)
        self.assertIn("OPT-002", ids)

    def test_linked_risks_saved(self):
        _add_option(linked_risks='["RK-001", "RK-003"]')
        strategy = _load_strategy()
        opt = next(o for o in strategy["change_strategy"]["options"]
                   if o["option_id"] == "OPT-001")
        self.assertIn("RK-001", opt["linked_risks"])
        self.assertIn("RK-003", opt["linked_risks"])

    def test_risk_impact_saved(self):
        _add_option(risk_impact="mitigates")
        strategy = _load_strategy()
        opt = next(o for o in strategy["change_strategy"]["options"]
                   if o["option_id"] == "OPT-001")
        self.assertEqual(opt["risk_impact"], "mitigates")

    def test_invalid_pros_json(self):
        result = _add_option(pros="not-json")
        self.assertIn("❌", result)

    def test_invalid_cons_json(self):
        result = _add_option(cons="not-json")
        self.assertIn("❌", result)

    def test_invalid_timeline(self):
        result = _add_option(timeline_months=0)
        self.assertIn("❌", result)

    def test_empty_name(self):
        result = _add_option(name="")
        self.assertIn("❌", result)

    def test_do_nothing_not_overwritten(self):
        _add_option()
        strategy = _load_strategy()
        do_nothing = next((o for o in strategy["change_strategy"]["options"]
                           if o["option_id"] == DO_NOTHING_OPTION_ID), None)
        self.assertIsNotNone(do_nothing)

    def test_pros_cons_saved(self):
        _add_option(pros='["Fast", "Cheap"]', cons='["Risky"]')
        strategy = _load_strategy()
        opt = next(o for o in strategy["change_strategy"]["options"]
                   if o["option_id"] == "OPT-001")
        self.assertEqual(len(opt["pros"]), 2)
        self.assertEqual(len(opt["cons"]), 1)

    def test_selected_is_false_by_default(self):
        _add_option()
        strategy = _load_strategy()
        opt = next(o for o in strategy["change_strategy"]["options"]
                   if o["option_id"] == "OPT-001")
        self.assertFalse(opt["selected"])

    def test_weighted_score_none_before_compare(self):
        _add_option()
        strategy = _load_strategy()
        opt = next(o for o in strategy["change_strategy"]["options"]
                   if o["option_id"] == "OPT-001")
        self.assertIsNone(opt["weighted_score"])

    def test_three_options_total_with_do_nothing(self):
        _add_option(name="Option A", strategy_type="phased")
        _add_option(name="Option B", strategy_type="big_bang")
        strategy = _load_strategy()
        self.assertEqual(len(strategy["change_strategy"]["options"]), 3)  # OPT-000 + 2


# ---------------------------------------------------------------------------
# compare_strategy_options
# ---------------------------------------------------------------------------

class TestCompareStrategyOptions(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _make_scope()
        _add_option(name="Option A", strategy_type="phased", investment_level="medium", timeline_months=12)
        _add_option(name="Option B", strategy_type="big_bang", investment_level="high", timeline_months=6)

    def _default_scores(self):
        return {
            "OPT-001": {"alignment_to_goals": 4, "risk_mitigation": 4, "cost": 3,
                        "time_to_value": 3, "org_readiness_fit": 3, "feasibility": 4},
            "OPT-002": {"alignment_to_goals": 3, "risk_mitigation": 2, "cost": 2,
                        "time_to_value": 5, "org_readiness_fit": 2, "feasibility": 3},
            DO_NOTHING_OPTION_ID: {"alignment_to_goals": 1, "risk_mitigation": 1, "cost": 5,
                                    "time_to_value": 1, "org_readiness_fit": 1, "feasibility": 1},
        }

    def test_basic_success(self):
        result = compare_strategy_options(
            project_id=PROJECT,
            scores_json=json.dumps(self._default_scores()),
            opportunity_cost="We forgo fast ROI.",
        )
        self.assertIn("✅", result)

    def test_winner_selected(self):
        compare_strategy_options(
            project_id=PROJECT,
            scores_json=json.dumps(self._default_scores()),
            opportunity_cost="Test",
        )
        strategy = _load_strategy()
        self.assertIsNotNone(strategy["change_strategy"]["selected_option_id"])

    def test_rejected_alternatives_filled(self):
        compare_strategy_options(
            project_id=PROJECT,
            scores_json=json.dumps(self._default_scores()),
            opportunity_cost="Test",
        )
        strategy = _load_strategy()
        rejected = strategy["change_strategy"]["rejected_alternatives"]
        self.assertGreater(len(rejected), 0)

    def test_opportunity_cost_saved(self):
        compare_strategy_options(
            project_id=PROJECT,
            scores_json=json.dumps(self._default_scores()),
            opportunity_cost="Forgoing fast ROI — the price of stability.",
        )
        strategy = _load_strategy()
        self.assertIn("fast ROI", strategy["change_strategy"]["opportunity_cost"])

    def test_empty_opportunity_cost_rejected(self):
        result = compare_strategy_options(
            project_id=PROJECT,
            scores_json=json.dumps(self._default_scores()),
            opportunity_cost="",
        )
        self.assertIn("❌", result)

    def test_invalid_scores_json(self):
        result = compare_strategy_options(
            project_id=PROJECT,
            scores_json="not-json",
            opportunity_cost="Test",
        )
        self.assertIn("❌", result)

    def test_weights_sum_validation(self):
        wrong_weights = {"alignment_to_goals": 50, "risk_mitigation": 50, "cost": 20,
                         "time_to_value": 15, "org_readiness_fit": 10, "feasibility": 10}
        result = compare_strategy_options(
            project_id=PROJECT,
            scores_json=json.dumps(self._default_scores()),
            opportunity_cost="Test",
            weights_json=json.dumps(wrong_weights),
        )
        self.assertIn("❌", result)

    def test_selected_option_is_winner(self):
        compare_strategy_options(
            project_id=PROJECT,
            scores_json=json.dumps(self._default_scores()),
            opportunity_cost="Test",
        )
        strategy = _load_strategy()
        selected_id = strategy["change_strategy"]["selected_option_id"]
        winner = next(o for o in strategy["change_strategy"]["options"]
                      if o["option_id"] == selected_id)
        self.assertTrue(winner["selected"])

    def test_non_winners_not_selected(self):
        compare_strategy_options(
            project_id=PROJECT,
            scores_json=json.dumps(self._default_scores()),
            opportunity_cost="Test",
        )
        strategy = _load_strategy()
        selected_id = strategy["change_strategy"]["selected_option_id"]
        losers = [o for o in strategy["change_strategy"]["options"]
                  if o["option_id"] != selected_id]
        for loser in losers:
            self.assertFalse(loser["selected"])

    def test_weighted_scores_computed(self):
        compare_strategy_options(
            project_id=PROJECT,
            scores_json=json.dumps(self._default_scores()),
            opportunity_cost="Test",
        )
        strategy = _load_strategy()
        for opt in strategy["change_strategy"]["options"]:
            if opt.get("scores_detail"):
                self.assertIsNotNone(opt["weighted_score"])

    def test_custom_criteria_accepted(self):
        custom = {"regulatory_compliance": {"weight": 5, "description": "Compliance"}}
        # Adjust default weights so sum = 100
        weights = {"alignment_to_goals": 20, "risk_mitigation": 20, "cost": 20,
                   "time_to_value": 15, "org_readiness_fit": 10, "feasibility": 10}
        scores_with_custom = self._default_scores()
        for oid in scores_with_custom:
            scores_with_custom[oid]["regulatory_compliance"] = 3
        result = compare_strategy_options(
            project_id=PROJECT,
            scores_json=json.dumps(scores_with_custom),
            opportunity_cost="Test",
            weights_json=json.dumps(weights),
            custom_criteria_json=json.dumps(custom),
        )
        self.assertIn("✅", result)

    def test_no_options_returns_warning(self):
        # Recreate without adding options
        empty_proj = "empty_64"
        _make_scope(project_id=empty_proj)
        result = compare_strategy_options(
            project_id=empty_proj,
            scores_json='{}',
            opportunity_cost="Test",
        )
        self.assertIn("⚠️", result)

    def test_criteria_weights_saved(self):
        compare_strategy_options(
            project_id=PROJECT,
            scores_json=json.dumps(self._default_scores()),
            opportunity_cost="Test",
        )
        strategy = _load_strategy()
        self.assertIn("criteria_weights_used", strategy["change_strategy"])

    def test_comparison_table_in_output(self):
        result = compare_strategy_options(
            project_id=PROJECT,
            scores_json=json.dumps(self._default_scores()),
            opportunity_cost="Test",
        )
        self.assertIn("Criterion", result)
        self.assertIn("TOTAL", result)

    def test_compared_on_date_saved(self):
        compare_strategy_options(
            project_id=PROJECT,
            scores_json=json.dumps(self._default_scores()),
            opportunity_cost="Test",
        )
        strategy = _load_strategy()
        self.assertEqual(strategy["change_strategy"]["compared_on"], TODAY)

    def test_do_nothing_auto_scored_if_missing(self):
        """do_nothing without explicit scores — should receive minimum scores."""
        scores_no_do_nothing = {
            "OPT-001": {"alignment_to_goals": 4, "risk_mitigation": 4, "cost": 3,
                        "time_to_value": 3, "org_readiness_fit": 3, "feasibility": 4},
        }
        result = compare_strategy_options(
            project_id=PROJECT,
            scores_json=json.dumps(scores_no_do_nothing),
            opportunity_cost="Test",
        )
        self.assertIn("✅", result)


# ---------------------------------------------------------------------------
# define_transition_states
# ---------------------------------------------------------------------------

class TestDefineTransitionStates(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _make_scope()

    def _make_phase(self, phase_number=1, **kwargs):
        params = dict(
            project_id=PROJECT,
            phase_number=phase_number,
            phase_name=f"Phase {phase_number}",
            duration_months=4,
            capabilities_delivered='["CRM System"]',
            gaps_closed='["gap_crm_data"]',
            risks_remaining='["RK-002"]',
            value_realizable="Operators can see customer history",
        )
        params.update(kwargs)
        return define_transition_states(**params)

    def test_basic_success(self):
        result = self._make_phase()
        self.assertIn("✅", result)

    def test_phase_saved(self):
        self._make_phase()
        strategy = _load_strategy()
        self.assertEqual(len(strategy["transition_states"]), 1)

    def test_multiple_phases(self):
        self._make_phase(1)
        self._make_phase(2, phase_name="Analytics Phase")
        strategy = _load_strategy()
        self.assertEqual(len(strategy["transition_states"]), 2)

    def test_phases_sorted(self):
        self._make_phase(2, phase_name="Second")
        self._make_phase(1, phase_name="First")
        strategy = _load_strategy()
        phases = strategy["transition_states"]
        self.assertEqual(phases[0]["phase"], 1)
        self.assertEqual(phases[1]["phase"], 2)

    def test_phase_overwrites_same_number(self):
        self._make_phase(1, phase_name="Initial")
        self._make_phase(1, phase_name="Updated")
        strategy = _load_strategy()
        self.assertEqual(len(strategy["transition_states"]), 1)
        self.assertEqual(strategy["transition_states"][0]["name"], "Updated")

    def test_invalid_phase_number(self):
        result = self._make_phase(phase_number=0)
        self.assertIn("❌", result)

    def test_invalid_duration(self):
        result = self._make_phase(duration_months=0)
        self.assertIn("❌", result)

    def test_empty_phase_name(self):
        result = self._make_phase(phase_name="")
        self.assertIn("❌", result)

    def test_empty_value_realizable_warning(self):
        result = self._make_phase(value_realizable="")
        self.assertIn("⚠️", result)

    def test_risks_remaining_saved(self):
        self._make_phase(risks_remaining='["RK-001", "RK-003"]')
        strategy = _load_strategy()
        phase = strategy["transition_states"][0]
        self.assertIn("RK-001", phase["risks_remaining"])
        self.assertIn("RK-003", phase["risks_remaining"])

    def test_capabilities_saved(self):
        self._make_phase(capabilities_delivered='["Cap A", "Cap B"]')
        strategy = _load_strategy()
        phase = strategy["transition_states"][0]
        self.assertEqual(len(phase["capabilities_delivered"]), 2)

    def test_total_months_in_output(self):
        self._make_phase(1, duration_months=4)
        result = self._make_phase(2, duration_months=5)
        self.assertIn("9", result)

    def test_invalid_capabilities_json(self):
        result = self._make_phase(capabilities_delivered="not-json")
        self.assertIn("❌", result)


# ---------------------------------------------------------------------------
# save_change_strategy
# ---------------------------------------------------------------------------

class TestSaveChangeStrategy(BaseMCPTest):

    def test_full_pipeline_success(self):
        _setup_full_pipeline()
        with patch("skills.change_strategy_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            result = save_change_strategy(project_id=PROJECT)
        self.assertIn("✅", result)

    def test_json_finalized(self):
        _setup_full_pipeline()
        with patch("skills.change_strategy_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅"
            save_change_strategy(project_id=PROJECT)
        strategy = _load_strategy()
        self.assertEqual(strategy["status"], "finalized")

    def test_finalized_on_date(self):
        _setup_full_pipeline()
        with patch("skills.change_strategy_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅"
            save_change_strategy(project_id=PROJECT)
        strategy = _load_strategy()
        self.assertEqual(strategy["finalized_on"], TODAY)

    def test_save_artifact_called(self):
        _setup_full_pipeline()
        with patch("skills.change_strategy_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            save_change_strategy(project_id=PROJECT)
            mock_sa.assert_called_once()

    def test_missing_scope_warning(self):
        _make_scope()
        result = save_change_strategy(project_id=PROJECT)
        self.assertIn("⚠️", result)

    def test_missing_selected_option_warning(self):
        _make_scope()
        _make_scope_def()
        _make_readiness()
        define_transition_states(
            project_id=PROJECT, phase_number=1, phase_name="P1",
            duration_months=3, capabilities_delivered='["A"]',
            gaps_closed='[]', risks_remaining='[]',
            value_realizable="Some value",
        )
        result = save_change_strategy(project_id=PROJECT)
        self.assertIn("⚠️", result)

    def test_missing_readiness_warning(self):
        _make_scope()
        _make_scope_def()
        _add_option()
        result = save_change_strategy(project_id=PROJECT)
        self.assertIn("⚠️", result)

    def test_missing_transition_states_warning(self):
        _make_scope()
        _make_scope_def()
        _make_readiness()
        _add_option()
        scores = {
            "OPT-001": {"alignment_to_goals": 4, "risk_mitigation": 3, "cost": 3,
                        "time_to_value": 3, "org_readiness_fit": 3, "feasibility": 4},
            DO_NOTHING_OPTION_ID: {"alignment_to_goals": 1, "risk_mitigation": 1, "cost": 5,
                                    "time_to_value": 1, "org_readiness_fit": 1, "feasibility": 1},
        }
        compare_strategy_options(
            project_id=PROJECT,
            scores_json=json.dumps(scores),
            opportunity_cost="Test",
        )
        result = save_change_strategy(project_id=PROJECT)
        self.assertIn("⚠️", result)

    def test_push_to_traceability_no_repo(self):
        """push_to_traceability=True without a repository — graceful degradation."""
        _setup_full_pipeline()
        with patch("skills.change_strategy_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅"
            result = save_change_strategy(project_id=PROJECT, push_to_traceability=True)
        self.assertIn("⚠️", result)
        self.assertIn("traceability repository", result.lower())

    def test_push_to_traceability_with_repo(self):
        """push_to_traceability=True with an existing repository."""
        _setup_full_pipeline()

        # Create a traceability repository with BG-001
        repo = {
            "project_id": PROJECT,
            "requirements": [{"id": "BG-001", "type": "business_goal", "title": "NPS Growth"}],
            "links": [],
        }
        repo_path = data_file(_safe(PROJECT), "traceability_repo.json")
        with open(repo_path, "w", encoding="utf-8") as f:
            json.dump(repo, f)

        # Add BG to imported_context for satisfies links
        strategy = _load_strategy()
        strategy["imported_context"]["business_goals"] = [
            {"id": "BG-001", "title": "NPS Growth", "source_project": PROJECT}
        ]
        from skills.change_strategy_mcp import _save_strategy
        _save_strategy(strategy, PROJECT)

        with patch("skills.change_strategy_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅"
            result = save_change_strategy(project_id=PROJECT, push_to_traceability=True)

        self.assertIn("SOL-001", result)

        # Verify the node was added to the repository
        with open(repo_path, encoding="utf-8") as f:
            updated_repo = json.load(f)
        # `solution_scope`, not `solution`: the latter is the BABOK requirement class
        # (ADR-082, revised — see tests/test_solution_scope_node_type.py).
        sol_nodes = [r for r in updated_repo["requirements"]
                     if r.get("type") == "solution_scope"]
        self.assertEqual(len(sol_nodes), 1)
        self.assertEqual(sol_nodes[0]["id"], "SOL-001")

    def test_markdown_contains_strategy_name(self):
        _setup_full_pipeline()
        md_content_captured = {}
        with patch("skills.change_strategy_mcp.save_artifact") as mock_sa:
            def capture(content, name, project_id=None):
                md_content_captured["content"] = content
                return "✅"
            mock_sa.side_effect = capture
            save_change_strategy(project_id=PROJECT)
        self.assertIn("Phased Implementation", md_content_captured.get("content", ""))

    def test_markdown_contains_capabilities(self):
        _setup_full_pipeline()
        md_content_captured = {}
        with patch("skills.change_strategy_mcp.save_artifact") as mock_sa:
            def capture(content, name, project_id=None):
                md_content_captured["content"] = content
                return "✅"
            mock_sa.side_effect = capture
            save_change_strategy(project_id=PROJECT)
        self.assertIn("CRM System", md_content_captured.get("content", ""))

    def test_output_contains_json_path(self):
        _setup_full_pipeline()
        with patch("skills.change_strategy_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅"
            result = save_change_strategy(project_id=PROJECT)
        self.assertIn("change_strategy.json", result)

    def test_sol_not_duplicated_on_second_push(self):
        """SOL-001 is not duplicated on a second push."""
        _setup_full_pipeline()
        repo = {
            "project_id": PROJECT,
            "requirements": [{"id": "BG-001", "type": "business_goal", "title": "Test"}],
            "links": [],
        }
        repo_path = data_file(_safe(PROJECT), "traceability_repo.json")
        with open(repo_path, "w", encoding="utf-8") as f:
            json.dump(repo, f)

        with patch("skills.change_strategy_mcp.save_artifact", return_value="✅"):
            save_change_strategy(project_id=PROJECT, push_to_traceability=True)
            save_change_strategy(project_id=PROJECT, push_to_traceability=True)

        with open(repo_path, encoding="utf-8") as f:
            updated = json.load(f)
        sol_nodes = [r for r in updated["requirements"]
                     if r.get("type") == "solution_scope"]
        self.assertEqual(len(sol_nodes), 1)


# ---------------------------------------------------------------------------
# Integration pipeline tests
# ---------------------------------------------------------------------------

class TestPipeline(BaseMCPTest):

    def test_full_pipeline_runs(self):
        """Full 7-step pipeline completes without errors."""
        result = _setup_full_pipeline()
        self.assertEqual(result["status"], "finalized") if "status" in result else None
        # Verify all sections are populated
        strategy = _load_strategy()
        self.assertTrue(len(strategy["solution_scope"]["capabilities"]) > 0)
        self.assertIsNotNone(strategy["enterprise_readiness"])
        self.assertIsNotNone(strategy["change_strategy"]["selected_option_id"])
        self.assertTrue(len(strategy["transition_states"]) > 0)

    def test_json_structure_complete(self):
        """JSON contract contains all key sections (ADR-083)."""
        _setup_full_pipeline()
        strategy = _load_strategy()
        self.assertIn("solution_scope", strategy)
        self.assertIn("change_strategy", strategy)
        self.assertIn("enterprise_readiness", strategy)
        self.assertIn("transition_states", strategy)

    def test_solution_scope_has_capabilities(self):
        _setup_full_pipeline()
        strategy = _load_strategy()
        self.assertTrue(len(strategy["solution_scope"]["capabilities"]) >= 2)

    def test_change_strategy_has_options(self):
        _setup_full_pipeline()
        strategy = _load_strategy()
        self.assertTrue(len(strategy["change_strategy"]["options"]) >= 3)  # OPT-000 + 2 real

    def test_selected_option_is_real_not_do_nothing(self):
        """Winner must not be do_nothing when scores are set correctly."""
        _setup_full_pipeline()
        strategy = _load_strategy()
        selected = strategy["change_strategy"]["selected_option_id"]
        self.assertNotEqual(selected, DO_NOTHING_OPTION_ID)

    def test_transition_states_are_ordered(self):
        _setup_full_pipeline()
        strategy = _load_strategy()
        phases = [s["phase"] for s in strategy["transition_states"]]
        self.assertEqual(phases, sorted(phases))

    def test_total_duration_correct(self):
        """Total phase duration is correct."""
        _setup_full_pipeline()
        strategy = _load_strategy()
        total = sum(s["duration_months"] for s in strategy["transition_states"])
        self.assertEqual(total, 9)  # 4 + 5 from _setup_full_pipeline

    def test_imported_context_preserved(self):
        """imported_context is not overwritten in later steps."""
        _make_scope(
            source_project_ids="[]",
        )
        # Manually insert context
        strategy = _load_strategy()
        strategy["imported_context"]["business_goals"] = [
            {"id": "BG-001", "title": "Test goal"}
        ]
        from skills.change_strategy_mcp import _save_strategy
        _save_strategy(strategy, PROJECT)

        _make_scope_def()  # must not overwrite imported_context
        strategy = _load_strategy()
        self.assertTrue(len(strategy["imported_context"]["business_goals"]) > 0)

    def test_different_projects_isolated(self):
        """Two projects do not affect each other."""
        proj_a = "proj_a_64"
        proj_b = "proj_b_64"
        _make_scope(project_id=proj_a, time_horizon_months=6)
        _make_scope(project_id=proj_b, time_horizon_months=18)
        a = _load_strategy(proj_a)
        b = _load_strategy(proj_b)
        self.assertEqual(a["scope"]["time_horizon_months"], 6)
        self.assertEqual(b["scope"]["time_horizon_months"], 18)

    def test_save_creates_correct_filename(self):
        _setup_full_pipeline()
        with patch("skills.change_strategy_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅"
            save_change_strategy(project_id=PROJECT)
            args = mock_sa.call_args[0]
            self.assertIn("6_4_change_strategy", args[1])

    def test_save_push_traceability_is_idempotent_no_duplicate_satisfies(self):
        """Re-running save_change_strategy(push=True) must NOT duplicate satisfies
        links. The solution node is deduplicated, but the satisfies links were
        appended unconditionally each call (same class as the 6.3 threatens bug)."""
        _setup_full_pipeline()
        strategy = _load_strategy()
        strategy["imported_context"]["business_goals"] = [{"id": "BG-001", "title": "Goal"}]
        from skills.change_strategy_mcp import _save_strategy
        _save_strategy(strategy, PROJECT)

        repo = {
            "project": PROJECT,
            "requirements": [{"id": "BG-001", "type": "business_goal", "title": "Goal",
                              "version": "1.0", "status": "confirmed", "added": TODAY}],
            "links": [],
        }
        repo_path = data_file(_safe(PROJECT), "traceability_repo.json")
        with open(repo_path, "w", encoding="utf-8") as f:
            json.dump(repo, f)

        with patch("skills.change_strategy_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅"
            save_change_strategy(project_id=PROJECT, push_to_traceability=True)
            save_change_strategy(project_id=PROJECT, push_to_traceability=True)  # re-finalize

        with open(repo_path, encoding="utf-8") as f:
            updated = json.load(f)
        satisfies = [l for l in updated.get("links", []) if l.get("relation") == "satisfies"]
        self.assertEqual(len(satisfies), 1, "satisfies links must not be duplicated on re-push")


class TestImportedRiskZoneDerivedFromScore(BaseMCPTest):
    """6.3's `zone` appears on a risk only after run_risk_matrix, but the register
    file exists from the first add_risk. The import defaulted a missing zone to
    "medium", so a score-20 risk arrived as medium and vanished from the High
    count — a confident claim over degraded data (reproduced live: an L5×I4 risk
    imported as `zone: medium`). The fallback now derives the zone from the score
    against the assessment's own tolerance, as 7.6 already does."""

    def test_high_score_risk_without_zone_imports_as_high(self):
        import json as _json
        from skills.common import data_path as _dp
        import os as _os
        pid = "zonefall"
        path = _dp(pid, f"{pid}_risk_assessment.json")
        _os.makedirs(_os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            _json.dump({
                "project_id": pid,
                "risk_tolerance": {"max_acceptable_score": 15},
                "risks": [
                    {"risk_id": "RK-001", "status": "identified",
                     "description": "Score 20, matrix never run",
                     "risk_score": 20, "response_strategy": "mitigate"},
                    {"risk_id": "RK-002", "status": "identified",
                     "description": "Score 4 stays low",
                     "risk_score": 4, "response_strategy": "accept"},
                ],
            }, f)
        scope_change_strategy(
            pid, change_type="other", time_horizon_months=6,
            methodology="agile", source_project_ids=f'["{pid}"]')
        with open(_dp(pid, f"{pid}_change_strategy.json"), encoding="utf-8") as f:
            strategy = _json.load(f)
        zones = {r["id"]: r["zone"] for r in strategy["imported_context"]["risks"]}
        self.assertEqual(zones["RK-001"], "high")
        self.assertEqual(zones["RK-002"], "low")


class TestGapCoverage(BaseMCPTest):

    def _strategy(self, caps, gaps=("technology", "policies")):
        return {
            "imported_context": {"gaps": [
                {"element": e, "element_label": e, "complexity": "medium",
                 "change_type": "improve", "gap_summary": "s"} for e in gaps]},
            "solution_scope": {"capabilities": caps},
            "scope": {"source_project_ids": []},
        }

    # --- _declared_element ---

    def test_the_new_form_names_the_element(self):
        self.assertEqual(_declared_element({"gap_source": "6.2:technology"}), "technology")

    def test_the_prefixed_form_also_names_the_element(self):
        self.assertEqual(
            _declared_element({"gap_source": "6.2:gap_analysis:technology"}), "technology")

    def test_the_OLD_bare_form_names_no_element(self):
        """'6.2:gap_analysis' is a SOURCE, not an element. It must stay UNKNOWN and
        must not become a phantom element named 'gap_analysis'."""
        self.assertEqual(_declared_element({"gap_source": "6.2:gap_analysis"}), "")

    def test_manual_and_missing_and_non_string_all_name_no_element(self):
        for src in ("manual", "", "   ", "6.2:", 7, ["6.2:technology"], None):
            self.assertEqual(_declared_element({"gap_source": src}), "", repr(src))
        self.assertEqual(_declared_element({}), "")

    # --- _gap_coverage ---

    def test_a_declared_in_scope_capability_covers_its_element(self):
        cov = _gap_coverage(self._strategy(
            [{"name": "A", "gap_source": "6.2:technology", "in_scope": True}]))
        self.assertTrue(cov["checked"])
        self.assertEqual(cov["covered"], ["technology"])
        self.assertEqual(cov["undeclared"], ["policies"])
        self.assertEqual(cov["unknown_caps"], 0)

    def test_an_OUT_OF_SCOPE_declaration_is_deliberate_exclusion_not_coverage(self):
        cov = _gap_coverage(self._strategy(
            [{"name": "A", "gap_source": "6.2:technology", "in_scope": False}]))
        self.assertEqual(cov["covered"], [])
        self.assertEqual(cov["excluded"], ["technology"])
        self.assertNotIn("technology", cov["undeclared"])

    def test_an_in_scope_capability_wins_over_an_out_of_scope_sibling(self):
        cov = _gap_coverage(self._strategy([
            {"name": "A", "gap_source": "6.2:technology", "in_scope": False},
            {"name": "B", "gap_source": "6.2:technology", "in_scope": True}]))
        self.assertEqual(cov["covered"], ["technology"])
        self.assertEqual(cov["excluded"], [])

    def test_an_element_the_analysis_does_not_contain_is_flagged_not_counted(self):
        cov = _gap_coverage(self._strategy(
            [{"name": "A", "gap_source": "6.2:assets", "in_scope": True}]))
        self.assertEqual(cov["claimed_absent"], ["assets"])
        self.assertEqual(cov["covered"], [])
        self.assertNotIn("assets", cov["analysed"])

    def test_a_capability_with_no_declared_element_is_counted_as_uncheckable(self):
        cov = _gap_coverage(self._strategy([
            {"name": "A", "gap_source": "manual", "in_scope": True},
            {"name": "B", "gap_source": "6.2:gap_analysis", "in_scope": True}]))
        self.assertEqual(cov["unknown_caps"], 2)
        self.assertEqual(cov["covered"], [])

    def test_with_NO_imported_gaps_the_verdict_is_unchecked_and_carries_no_counts(self):
        """Silence is right for the accusation and wrong for the count: a platform
        that cannot tell must say so, not report a number it does not know."""
        cov = _gap_coverage(self._strategy(
            [{"name": "A", "gap_source": "6.2:technology"}], gaps=()))
        self.assertFalse(cov["checked"])
        self.assertEqual(cov["analysed"], [])
        self.assertEqual(cov["covered"], [])
        self.assertEqual(cov["undeclared"], [])
        self.assertEqual(cov["unknown_caps"], 0)

    def test_a_strategy_written_BEFORE_this_feature_has_no_gaps_key_at_all(self):
        """An ABSENT key is not an empty one. Every real project planned before this
        branch has `imported_context` WITHOUT `gaps` — a shape the current writer can
        no longer produce, so it must be built by hand."""
        legacy = {
            "imported_context": {"business_needs": [], "business_goals": [], "risks": []},
            "solution_scope": {"capabilities": [
                {"name": "A", "gap_source": "6.2:technology", "in_scope": True}]},
            "scope": {},
        }
        cov = _gap_coverage(legacy)
        self.assertFalse(cov["checked"])

    def test_junk_shapes_degrade_to_unchecked_instead_of_raising(self):
        for mirror in ("not a list", 7, None, [1, 2, "x"], [{"element": 5}]):
            cov = _gap_coverage({"imported_context": {"gaps": mirror},
                                 "solution_scope": {"capabilities": "not a list"},
                                 "scope": {}})
            self.assertFalse(cov["checked"], repr(mirror))

    def test_junk_CAPABILITIES_under_a_VALID_mirror_degrade_instead_of_raising(self):
        """The case above never reaches the capability guards at all: every mirror in
        it is invalid, so the function returns before `isinstance(caps, list)` is ever
        evaluated. A valid mirror is what puts that line under test."""
        for caps in ("not a list", 7, None, {"name": "A"}, [1, "x", None]):
            cov = _gap_coverage({
                "imported_context": {"gaps": [{"element": "technology"}]},
                "solution_scope": {"capabilities": caps},
                "scope": {}})
            self.assertTrue(cov["checked"], repr(caps))
            self.assertEqual(cov["analysed"], ["technology"], repr(caps))
            self.assertEqual(cov["covered"], [], repr(caps))
            self.assertEqual(cov["undeclared"], ["technology"], repr(caps))
            self.assertEqual(cov["unknown_caps"], 0, repr(caps))

    def test_a_junk_solution_scope_or_imported_context_degrades_too(self):
        """`x or {}` rescues None but not a non-empty string, which is truthy and has
        no .get. Found by the case above, which is the first to get far enough to
        dereference these two containers."""
        cov = _gap_coverage({"imported_context": {"gaps": [{"element": "technology"}]},
                             "solution_scope": "not a dict", "scope": "not a dict"})
        self.assertTrue(cov["checked"])
        self.assertEqual(cov["undeclared"], ["technology"])
        self.assertFalse(_gap_coverage({"imported_context": "not a dict"})["checked"])
        self.assertFalse(_gap_file_seen({"scope": "not a dict"}, "no_such_project"))

    def test_defaulting_in_scope_matches_define_solution_scope(self):
        """define_solution_scope defaults in_scope to True; coverage must agree, or a
        capability the BA left implicit would read as deliberately excluded."""
        cov = _gap_coverage(self._strategy([{"name": "A", "gap_source": "6.2:technology"}]))
        self.assertEqual(cov["covered"], ["technology"])

    # --- _gap_coverage_lines ---

    def test_the_block_states_the_covered_count_against_the_analysed_total(self):
        lines = "\n".join(_gap_coverage_lines(self._strategy(
            [{"name": "A", "gap_source": "6.2:technology"}]), PROJECT))
        self.assertIn("**6.2 gap coverage:**", lines)
        self.assertIn("Declared covered: `technology` (1 of 2 analysed)", lines)
        self.assertIn("No in-scope capability DECLARES coverage of: `policies`", lines)

    def test_without_an_analysis_the_block_says_so_and_prints_no_digits(self):
        lines = "\n".join(_gap_coverage_lines(self._strategy([], gaps=()), PROJECT))
        self.assertIn("no 6.2 gap analysis imported", lines)
        self.assertIn("coverage was not checked", lines)
        self.assertNotIn("of 0 analysed", lines)
        self.assertNotIn("covered:", lines)

    def test_a_gap_file_on_disk_that_was_never_imported_gets_its_own_message(self):
        """Otherwise the analyst reads 'cannot tell' over a file sitting in their
        own project folder, and the advice ('re-run scope_change_strategy') is lost."""
        _write_gap_file()
        lines = "\n".join(_gap_coverage_lines(self._strategy([], gaps=()), PROJECT))
        self.assertIn("exists but was not imported", lines)
        self.assertIn("scope_change_strategy", lines)

    def test_the_uncheckable_count_is_singular_for_one(self):
        lines = "\n".join(_gap_coverage_lines(self._strategy(
            [{"name": "A", "gap_source": "manual"}]), PROJECT))
        self.assertIn("Cannot be checked: 1 capability (no 6.2 element", lines)

    def test_every_optional_line_is_absent_when_it_has_nothing_to_say(self):
        lines = "\n".join(_gap_coverage_lines(self._strategy([
            {"name": "A", "gap_source": "6.2:technology"},
            {"name": "B", "gap_source": "6.2:policies"}]), PROJECT))
        self.assertIn("Declared covered: `technology`, `policies`", lines)
        self.assertNotIn("Cannot be checked", lines)
        self.assertNotIn("Claimed but absent", lines)
        self.assertNotIn("Deliberately left unaddressed", lines)
        self.assertNotIn("DECLARES coverage of", lines)


class TestLiveRunFindings(BaseMCPTest):
    """Three defects found by READING the delivered document of a live run, not by
    grepping it. Each is invisible to a substring check: one is grammar, one is
    evidence missing from the page, one is a word colliding with a heading twenty
    lines above it."""

    def _strategy(self, caps, gaps=("technology", "policies")):
        return {
            "imported_context": {"gaps": [
                {"element": e, "element_label": e, "complexity": "medium",
                 "change_type": "improve", "gap_summary": "s"} for e in gaps]},
            "solution_scope": {"capabilities": caps},
            "scope": {"source_project_ids": []},
        }

    def test_the_uncheckable_line_is_grammatical_for_one_and_for_many(self):
        """The live document read "1 capability state no 6.2 element" — the noun was
        singularised and the verb was not."""
        one = "\n".join(_gap_coverage_lines(self._strategy(
            [{"name": "A", "gap_source": "manual"}]), PROJECT))
        many = "\n".join(_gap_coverage_lines(self._strategy(
            [{"name": "A", "gap_source": "manual"},
             {"name": "B", "gap_source": "manual"}]), PROJECT))
        self.assertIn("Cannot be checked: 1 capability (", one)
        self.assertNotIn("capability state", one)
        self.assertIn("Cannot be checked: 2 capabilities (", many)

    def test_a_deliberate_exclusion_names_the_capability_that_carries_it(self):
        """The live document asserted "Deliberately left unaddressed (out of scope):
        org_structure" while the capability holding that decision appeared NOWHERE in
        the document — the capability list renders in-scope entries only, and the
        "Explicitly out of scope" list holds different data. A sponsor read a claim
        with no evidence anywhere on the page."""
        out = "\n".join(_gap_coverage_lines(self._strategy([
            {"name": "Second clinic site", "gap_source": "6.2:policies",
             "in_scope": False}]), PROJECT))
        self.assertIn("Deliberately left unaddressed (out of scope):", out)
        self.assertIn("Second clinic site", out)

    def test_two_capabilities_excluding_one_element_are_both_named(self):
        out = "\n".join(_gap_coverage_lines(self._strategy([
            {"name": "Site B", "gap_source": "6.2:policies", "in_scope": False},
            {"name": "Site C", "gap_source": "6.2:policies", "in_scope": False}]),
            PROJECT))
        self.assertIn("Site B", out)
        self.assertIn("Site C", out)

    def test_element_names_are_quoted_so_they_cannot_read_as_prose(self):
        """The document renders "**Capabilities (4):**" as a heading, and the 6.2
        element `capabilities` appeared bare twenty lines below it. The capability
        sub-lines already quote element names; the block did not."""
        out = "\n".join(_gap_coverage_lines(self._strategy(
            [{"name": "A", "gap_source": "6.2:technology"}],
            gaps=("technology", "capabilities")), PROJECT))
        self.assertIn("Declared covered: `technology`", out)
        self.assertIn("DECLARES coverage of: `capabilities`", out)
        self.assertNotIn("coverage of: capabilities", out)


class TestSolutionScopeReportsCoverage(BaseMCPTest):

    def _caps(self, *pairs):
        return json.dumps([
            {"name": n, "category": "technology", "description": "d",
             "gap_severity": "high", "gap_source": s, "in_scope": True}
            for n, s in pairs])

    def test_the_reply_reports_coverage_when_an_analysis_was_imported(self):
        _write_gap_file()
        _make_scope(source_project_ids=f'["{PROJECT}"]')
        out = define_solution_scope(PROJECT, self._caps(("A", "6.2:technology")))
        self.assertIn("**6.2 gap coverage:**", out)
        self.assertIn("Declared covered: `technology` (1 of 2 analysed)", out)
        self.assertIn("No in-scope capability DECLARES coverage of: `policies`", out)

    def test_the_reply_says_it_could_not_check_rather_than_reporting_zero(self):
        _make_scope()
        out = define_solution_scope(PROJECT, self._caps(("A", "6.2:technology")))
        self.assertIn("coverage was not checked", out)
        self.assertNotIn("0 of", out)

    def test_the_reply_flags_an_element_the_analysis_does_not_contain(self):
        _write_gap_file()
        _make_scope(source_project_ids=f'["{PROJECT}"]')
        out = define_solution_scope(PROJECT, self._caps(("A", "6.2:assets")))
        self.assertIn("Claimed but absent from the 6.2 analysis: `assets`", out)

    def test_the_existing_severity_distribution_still_renders(self):
        """A positive companion: the block must be ADDED, not swapped in for the
        distribution the analyst already relies on."""
        _write_gap_file()
        _make_scope(source_project_ids=f'["{PROJECT}"]')
        out = define_solution_scope(PROJECT, self._caps(("A", "6.2:technology")))
        self.assertIn("Distribution by gap_severity", out)
        self.assertIn("🔴 high:   1", out)

    def test_coverage_reflects_the_capabilities_of_THIS_call_not_the_previous_one(self):
        """define_solution_scope replaces solution_scope wholesale; the coverage block
        must be computed from what was just saved, or it reports the previous run."""
        _write_gap_file()
        _make_scope(source_project_ids=f'["{PROJECT}"]')
        define_solution_scope(PROJECT, self._caps(("A", "6.2:technology")))
        out = define_solution_scope(PROJECT, self._caps(("B", "6.2:policies")))
        self.assertIn("Declared covered: `policies` (1 of 2 analysed)", out)
        self.assertIn("DECLARES coverage of: `technology`", out)


class TestChangeStrategyDocumentCarriesCoverage(BaseMCPTest):

    def _doc(self, project_id=PROJECT):
        """The DELIVERED document — save_change_strategy RETURNS a summary, and the
        markdown goes to save_artifact. Asserting on the return value would pass or
        fail for reasons unrelated to the document."""
        with patch("skills.change_strategy_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            save_change_strategy(project_id=project_id)
            return mock_sa.call_args[0][0]

    def _pipeline_with_gaps(self, caps):
        _write_gap_file()
        _make_scope(source_project_ids=f'["{PROJECT}"]')
        define_solution_scope(PROJECT, json.dumps(caps))
        _make_readiness()
        _add_option()
        compare_strategy_options(
            project_id=PROJECT,
            scores_json=json.dumps({"OPT-001": {
                "alignment_to_goals": 4, "risk_mitigation": 4, "cost": 3,
                "time_to_value": 3, "org_readiness_fit": 3, "feasibility": 4}}),
            opportunity_cost="none")
        # save_change_strategy refuses to run (and never calls save_artifact) without
        # at least one transition state — a precondition unrelated to gap coverage,
        # but required for _doc() to reach the markdown at all.
        define_transition_states(
            project_id=PROJECT,
            phase_number=1,
            phase_name="Phase 1",
            duration_months=6,
            capabilities_delivered='["Delivered capability"]',
            gaps_closed='[]',
            risks_remaining='[]',
            value_realizable="Value delivered",
        )

    def test_the_document_carries_the_coverage_block(self):
        self._pipeline_with_gaps([
            {"name": "Portal", "category": "technology", "description": "d",
             "gap_severity": "high", "gap_source": "6.2:technology", "in_scope": True}])
        doc = self._doc()
        self.assertIn("**6.2 gap coverage:**", doc)
        self.assertIn("Declared covered: `technology` (1 of 2 analysed)", doc)
        self.assertIn("DECLARES coverage of: `policies`", doc)

    def test_the_block_sits_inside_Solution_Scope_not_after_the_document(self):
        self._pipeline_with_gaps([
            {"name": "Portal", "category": "technology", "description": "d",
             "gap_severity": "high", "gap_source": "6.2:technology", "in_scope": True}])
        doc = self._doc()
        self.assertLess(doc.index("## Solution Scope"), doc.index("**6.2 gap coverage:**"))
        self.assertLess(doc.index("**6.2 gap coverage:**"), doc.index("## Enterprise Readiness"))

    def test_a_capability_line_names_its_6_2_origin_and_labels_the_other_scale(self):
        """gap_severity and complexity DELIBERATELY differ here. _write_gap_file gives
        `technology` complexity "high"; a capability whose gap_severity were also "high"
        would read the same whichever field the sub-line printed, and the assertion
        would prove nothing about which scale is being rendered."""
        self._pipeline_with_gaps([
            {"name": "Portal", "category": "technology", "description": "d",
             "gap_severity": "low", "gap_source": "6.2:technology", "in_scope": True}])
        doc = self._doc()
        self.assertIn("↳ from 6.2 gap `technology` — change effort there: high", doc)
        self.assertIn("(effort, not gap size)", doc)
        self.assertIn("gap:low", doc)

    def test_a_capability_with_no_declared_element_says_so_on_its_own_line(self):
        self._pipeline_with_gaps([
            {"name": "Portal", "category": "technology", "description": "d",
             "gap_severity": "high", "gap_source": "manual", "in_scope": True}])
        doc = self._doc()
        self.assertIn("no 6.2 element stated in gap_source", doc)

    def test_with_no_analysis_the_document_prints_the_block_ONCE_and_no_sub_lines(self):
        """Every capability is formally uncheckable with no analysis. Saying it under
        each one buries the document in a fact the block states in one line."""
        _make_scope()
        define_solution_scope(PROJECT, json.dumps([
            {"name": "A", "category": "technology", "description": "d",
             "gap_severity": "high", "gap_source": "manual", "in_scope": True},
            {"name": "B", "category": "people", "description": "d",
             "gap_severity": "low", "gap_source": "manual", "in_scope": True}]))
        _make_readiness()
        _add_option()
        compare_strategy_options(
            project_id=PROJECT,
            scores_json=json.dumps({"OPT-001": {
                "alignment_to_goals": 4, "risk_mitigation": 4, "cost": 3,
                "time_to_value": 3, "org_readiness_fit": 3, "feasibility": 4}}),
            opportunity_cost="none")
        define_transition_states(
            project_id=PROJECT,
            phase_number=1,
            phase_name="Phase 1",
            duration_months=6,
            capabilities_delivered='["Delivered capability"]',
            gaps_closed='[]',
            risks_remaining='[]',
            value_realizable="Value delivered",
        )
        doc = self._doc()
        self.assertIn("coverage was not checked", doc)
        self.assertNotIn("↳", doc)

    def test_a_capability_missing_gap_severity_no_longer_crashes_the_save(self):
        """A HAND EDIT of the strategy JSON produces capabilities without the key —
        define_solution_scope always writes it, and the 7.5 surrogate this docstring
        once blamed cannot: `set_change_strategy` writes neither `solution_scope` nor
        `capabilities`, so such a file never reaches this renderer at all. The renderer
        indexed the key directly and raised KeyError INSIDE the final save — the one
        step whose failure loses the delivered document."""
        self._pipeline_with_gaps([
            {"name": "Portal", "category": "technology", "description": "d",
             "gap_severity": "high", "gap_source": "6.2:technology", "in_scope": True}])
        path = _strategy_path(PROJECT)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        del data["solution_scope"]["capabilities"][0]["gap_severity"]
        del data["solution_scope"]["capabilities"][0]["category"]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        doc = self._doc()
        self.assertIn("Portal", doc)
        self.assertIn("gap:not stated", doc)

    def test_the_existing_capability_line_format_is_unchanged_for_valid_data(self):
        """A positive companion for the KeyError fix: .get must not alter the string
        every existing consumer and test reads."""
        self._pipeline_with_gaps([
            {"name": "Portal", "category": "technology", "description": "Portal intake",
             "gap_severity": "high", "gap_source": "6.2:technology", "in_scope": True}])
        doc = self._doc()
        self.assertIn("- Portal 🔴 gap:high | Portal intake", doc)


class TestContextElementsAreNotUncoveredGaps(BaseMCPTest):
    """`business_needs` sits in every one of 6.2's six default element sets and
    `external` is influences nobody builds a capability for. Counting them as
    uncovered printed an accusation on every normal project, and the only way to
    silence it was a false declaration."""

    def _strategy(self, caps, gaps):
        return {
            "imported_context": {"gaps": [
                {"element": e, "element_label": e, "complexity": "medium",
                 "change_type": "improve", "gap_summary": "s"} for e in gaps]},
            "solution_scope": {"capabilities": caps},
            "scope": {"source_project_ids": []},
        }

    def test_context_elements_leave_the_denominator_and_the_accusation(self):
        cov = _gap_coverage(self._strategy(
            [{"name": "A", "gap_source": "6.2:technology"}],
            gaps=("business_needs", "technology", "policies", "external")))
        self.assertEqual(cov["analysed"], ["technology", "policies"])
        self.assertEqual(cov["undeclared"], ["policies"])
        self.assertEqual(cov["context_elements"], ["business_needs", "external"])

    def test_the_block_names_them_on_their_own_line_and_counts_two_not_four(self):
        lines = "\n".join(_gap_coverage_lines(self._strategy(
            [{"name": "A", "gap_source": "6.2:technology"}],
            gaps=("business_needs", "technology", "policies", "external")), PROJECT))
        self.assertIn("- Context elements, not closed by capabilities: "
                      "`business_needs`, `external`", lines)
        self.assertIn("(1 of 2 analysed)", lines)
        self.assertNotIn("coverage of: `business_needs`", lines)
        self.assertNotIn("`external`,", lines.split("Context elements")[0])

    def test_the_context_line_is_absent_when_the_analysis_carries_none(self):
        lines = "\n".join(_gap_coverage_lines(self._strategy(
            [{"name": "A", "gap_source": "6.2:technology"}],
            gaps=("technology", "policies")), PROJECT))
        self.assertNotIn("Context elements", lines)

    def test_an_EXPLICIT_declaration_pulls_a_context_element_back_into_the_count(self):
        """The analyst knows the project better than the platform's default list."""
        cov = _gap_coverage(self._strategy(
            [{"name": "A", "gap_source": "6.2:business_needs"}],
            gaps=("business_needs", "technology")))
        self.assertEqual(cov["covered"], ["business_needs"])
        self.assertEqual(cov["analysed"], ["business_needs", "technology"])
        self.assertEqual(cov["context_elements"], [])
        self.assertEqual(cov["undeclared"], ["technology"])

    def test_a_declared_context_element_is_never_ALSO_listed_as_context(self):
        lines = "\n".join(_gap_coverage_lines(self._strategy(
            [{"name": "A", "gap_source": "6.2:external"}],
            gaps=("external", "technology")), PROJECT))
        self.assertIn("Declared covered: `external` (1 of 2 analysed)", lines)
        self.assertNotIn("Context elements", lines)

    def test_architecture_and_assets_are_capabilities_and_stay_in_the_denominator(self):
        cov = _gap_coverage(self._strategy([], gaps=("architecture", "assets")))
        self.assertEqual(cov["analysed"], ["architecture", "assets"])
        self.assertEqual(cov["undeclared"], ["architecture", "assets"])
        self.assertEqual(cov["context_elements"], [])

    def test_an_analysis_of_ONLY_context_elements_reports_no_uncovered_anything(self):
        lines = "\n".join(_gap_coverage_lines(
            self._strategy([], gaps=("business_needs", "external")), PROJECT))
        self.assertIn("Context elements, not closed by capabilities", lines)
        self.assertNotIn("DECLARES coverage of", lines)
        self.assertNotIn("analysed)", lines)


class TestTheBlockOnlyJudgesWhatTheDocumentShows(BaseMCPTest):
    """The delivered document renders IN-SCOPE capabilities only. `excluded_by` was
    fixed to name its capabilities; the other two lines of the block still counted
    out-of-scope ones, so a page where every rendered capability is traced could still
    carry "Cannot be checked: 1 capability" over nothing the sponsor can find."""

    def _strategy(self, caps, gaps=("technology", "policies")):
        return {
            "imported_context": {"gaps": [
                {"element": e, "element_label": e, "complexity": "medium",
                 "change_type": "improve", "gap_summary": "s"} for e in gaps]},
            "solution_scope": {"capabilities": caps},
            "scope": {"source_project_ids": []},
        }

    def test_an_OUT_OF_SCOPE_capability_with_no_element_is_not_counted_uncheckable(self):
        cov = _gap_coverage(self._strategy([
            {"name": "Traced", "gap_source": "6.2:technology", "in_scope": True},
            {"name": "Dropped", "gap_source": "manual", "in_scope": False}]))
        self.assertEqual(cov["unknown_caps"], 0)

    def test_the_uncheckable_line_is_absent_when_only_out_of_scope_caps_lack_elements(self):
        lines = "\n".join(_gap_coverage_lines(self._strategy([
            {"name": "Traced", "gap_source": "6.2:technology", "in_scope": True},
            {"name": "Dropped", "gap_source": "manual", "in_scope": False}]), PROJECT))
        self.assertNotIn("Cannot be checked", lines)

    def test_an_OUT_OF_SCOPE_capability_claiming_an_absent_element_is_not_flagged(self):
        cov = _gap_coverage(self._strategy(
            [{"name": "Dropped", "gap_source": "6.2:assets", "in_scope": False}]))
        self.assertEqual(cov["claimed_absent"], [])

    def test_the_claimed_absent_line_is_absent_for_an_out_of_scope_claim(self):
        lines = "\n".join(_gap_coverage_lines(self._strategy(
            [{"name": "Dropped", "gap_source": "6.2:assets", "in_scope": False}]),
            PROJECT))
        self.assertNotIn("Claimed but absent", lines)

    def test_IN_SCOPE_capabilities_are_still_counted_by_both_lines(self):
        """The positive companion: the fix must narrow the count to in-scope, not
        switch it off."""
        cov = _gap_coverage(self._strategy([
            {"name": "A", "gap_source": "manual", "in_scope": True},
            {"name": "B", "gap_source": "6.2:assets", "in_scope": True}]))
        self.assertEqual(cov["unknown_caps"], 1)
        self.assertEqual(cov["claimed_absent"], ["assets"])


class TestTheNotImportedMessageTellsTheTruth(BaseMCPTest):
    """"a 6.2 gap analysis exists but was not imported — re-run scope_change_strategy"
    is actionable advice, and it was printed in two situations where re-running changes
    nothing at all."""

    def _strategy(self, sources):
        return {
            "imported_context": {"gaps": []},
            "solution_scope": {"capabilities": []},
            "scope": {"source_project_ids": sources},
        }

    # --- (a) the file was read and had nothing usable in it ---

    def test_an_EMPTY_gaps_list_warns_instead_of_passing_for_a_clean_import(self):
        _write_gap_file(gaps=[])
        result = _make_scope(source_project_ids=f'["{PROJECT}"]')
        self.assertIn("no usable", result)
        self.assertNotIn("6.2 gap_analysis not found", result)

    def test_a_file_of_ONLY_unusable_entries_warns_too(self):
        _write_gap_file(gaps=[{"element": ""}, "not a dict", {"element": 7}])
        result = _make_scope(source_project_ids=f'["{PROJECT}"]')
        self.assertIn("no usable", result)

    def test_a_missing_file_still_says_NOT_FOUND_and_not_the_empty_wording(self):
        """The two must stay distinguishable: one sends the analyst to build an
        artefact, the other to repair one."""
        result = _make_scope(source_project_ids=f'["{PROJECT}"]')
        self.assertIn("6.2 gap_analysis not found", result)
        self.assertNotIn("no usable", result)

    def test_a_populated_file_warns_about_neither(self):
        _write_gap_file()
        result = _make_scope(source_project_ids=f'["{PROJECT}"]')
        self.assertNotIn("no usable", result)
        self.assertNotIn("6.2 gap_analysis not found", result)

    # --- (b) the detector must ask the importer's own question ---

    def test_a_file_the_IMPORTER_would_never_read_is_not_reported_as_seen(self):
        """The importer walks `sources or [project_id]`; the detector walked
        `sources + [project_id]`. With sources set to another project, the detector
        found the current project's file — which the import never opens — and advised
        a re-run that cannot possibly pick it up."""
        _write_gap_file(project_id=PROJECT)
        self.assertTrue(os.path.exists(_gap_file_path(PROJECT)))
        self.assertFalse(_gap_file_seen(self._strategy(["some_other_project"]), PROJECT))

    def test_the_block_does_not_advise_an_impossible_re_run(self):
        _write_gap_file(project_id=PROJECT)
        lines = "\n".join(_gap_coverage_lines(
            self._strategy(["some_other_project"]), PROJECT))
        self.assertIn("no 6.2 gap analysis imported", lines)
        self.assertNotIn("exists but was not imported", lines)

    def test_a_file_at_a_NAMED_source_is_still_seen(self):
        _write_gap_file(project_id="donor_project")
        self.assertTrue(_gap_file_seen(self._strategy(["donor_project"]), PROJECT))

    def test_with_no_sources_the_current_project_is_still_the_fallback(self):
        """`sources or [project_id]` — the importer's own fallback, unchanged."""
        _write_gap_file(project_id=PROJECT)
        self.assertTrue(_gap_file_seen(self._strategy([]), PROJECT))


class TestGapSourceElementIsValidatedAndCaseInsensitive(BaseMCPTest):
    """`gap_source` was the only field of a capability nobody checked, and comparison
    was case-sensitive — so one capital letter produced two mutually exclusive
    sentences in the same delivered document."""

    def setUp(self):
        super().setUp()
        _write_gap_file()
        _make_scope(source_project_ids=f'["{PROJECT}"]')

    def _cap(self, source, name="A"):
        return json.dumps([{"name": name, "category": "technology", "description": "d",
                            "gap_severity": "high", "gap_source": source,
                            "in_scope": True}])

    def test_a_6_4_CATEGORY_name_is_rejected_not_silently_accepted(self):
        """"6.2:process" is the most plausible mistake there is: `process` is a valid
        6.4 category and no 6.2 element at all."""
        out = define_solution_scope(PROJECT, self._cap("6.2:process"))
        self.assertIn("❌", out)
        self.assertIn("process", out)
        self.assertIn("org_structure", out)

    def test_the_error_names_the_bad_value_and_lists_the_allowed_ones(self):
        out = define_solution_scope(PROJECT, self._cap("6.2:invented_element"))
        self.assertIn("invented_element", out)
        for element in ("business_needs", "technology", "policies", "external"):
            self.assertIn(element, out)

    def test_a_rejected_capability_is_not_saved(self):
        define_solution_scope(PROJECT, self._cap("6.2:process"))
        self.assertEqual(
            _load_strategy()["solution_scope"].get("capabilities", []), [])

    def test_all_eight_elements_are_accepted(self):
        for element in ("business_needs", "org_structure", "capabilities", "technology",
                        "policies", "architecture", "assets", "external"):
            out = define_solution_scope(PROJECT, self._cap(f"6.2:{element}"))
            self.assertIn("✅", out, element)

    def test_manual_and_the_legacy_bare_form_are_still_accepted(self):
        for source in ("manual", "6.2:gap_analysis", ""):
            self.assertIn("✅", define_solution_scope(PROJECT, self._cap(source)), source)

    def test_a_capitalised_element_does_not_produce_two_opposite_verdicts(self):
        """6.2's own report prints element_label "Technology and Infrastructure"; an
        LLM copying the case produced BOTH "No in-scope capability DECLARES coverage
        of: `technology`" AND "Claimed but absent: `Technology`" on one page."""
        out = define_solution_scope(PROJECT, self._cap("6.2:Technology"))
        self.assertIn("✅", out)
        self.assertIn("Declared covered: `technology` (1 of 2 analysed)", out)
        self.assertNotIn("Claimed but absent", out)
        self.assertNotIn("DECLARES coverage of: `technology`", out)

    def test_the_document_sub_line_matches_a_capitalised_element_too(self):
        define_solution_scope(PROJECT, self._cap("6.2:Technology", name="Portal"))
        _make_readiness()
        _add_option()
        compare_strategy_options(
            project_id=PROJECT,
            scores_json=json.dumps({"OPT-001": {
                "alignment_to_goals": 4, "risk_mitigation": 4, "cost": 3,
                "time_to_value": 3, "org_readiness_fit": 3, "feasibility": 4}}),
            opportunity_cost="none")
        define_transition_states(
            project_id=PROJECT, phase_number=1, phase_name="P1", duration_months=6,
            capabilities_delivered='["Portal"]', gaps_closed='[]',
            risks_remaining='[]', value_realizable="v")
        with patch("skills.change_strategy_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            save_change_strategy(project_id=PROJECT)
            doc = mock_sa.call_args[0][0]
        self.assertIn("change effort there: high", doc)
        self.assertNotIn("does not contain", doc)

    def test_a_VALID_element_absent_from_THIS_analysis_is_still_flagged(self):
        """The line keeps its legitimate job: `assets` is a real 6.2 element that this
        particular analysis simply never captured."""
        out = define_solution_scope(PROJECT, self._cap("6.2:assets"))
        self.assertIn("✅", out)
        self.assertIn("Claimed but absent from the 6.2 analysis: `assets`", out)


class TestNullFieldsDoNotLoseTheDeliveredDocument(BaseMCPTest):
    """`.get(key, default)` returns the default for an ABSENT key and None for a key
    present with value null. A hand-edited strategy JSON carries the second shape, and
    `sorted(cats.items())` then raised TypeError comparing str to None — out of
    save_change_strategy, past guard_artifact_errors (which catches only
    CorruptArtifactError), losing the document at the last step of the chapter."""

    def _pipeline(self):
        _write_gap_file()
        _make_scope(source_project_ids=f'["{PROJECT}"]')
        define_solution_scope(PROJECT, json.dumps([
            {"name": "Portal", "category": "technology", "description": "d",
             "gap_severity": "high", "gap_source": "6.2:technology", "in_scope": True},
            {"name": "Training", "category": "people", "description": "d",
             "gap_severity": "low", "gap_source": "6.2:policies", "in_scope": True}]))
        _make_readiness()
        _add_option()
        compare_strategy_options(
            project_id=PROJECT,
            scores_json=json.dumps({"OPT-001": {
                "alignment_to_goals": 4, "risk_mitigation": 4, "cost": 3,
                "time_to_value": 3, "org_readiness_fit": 3, "feasibility": 4}}),
            opportunity_cost="none")
        define_transition_states(
            project_id=PROJECT, phase_number=1, phase_name="P1", duration_months=6,
            capabilities_delivered='["Portal"]', gaps_closed='[]',
            risks_remaining='[]', value_realizable="v")

    def _nullify(self, *fields):
        """NULL, not `del`: the existing test deletes the keys, which is exactly the
        shape `.get(key, default)` already handles. Only an explicit null reaches the
        comparison. TWO capabilities, so `sorted` actually compares a pair."""
        path = _strategy_path(PROJECT)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for field in fields:
            data["solution_scope"]["capabilities"][0][field] = None
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def _doc(self):
        with patch("skills.change_strategy_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            save_change_strategy(project_id=PROJECT)
            return mock_sa.call_args[0][0]

    def test_a_NULL_category_does_not_raise_out_of_the_tool(self):
        self._pipeline()
        self._nullify("category")
        doc = self._doc()
        self.assertIn("uncategorised", doc)
        self.assertIn("Portal", doc)
        self.assertIn("Training", doc)

    def test_a_NULL_name_and_description_render_as_empty_not_as_the_word_None(self):
        self._pipeline()
        self._nullify("name", "description")
        doc = self._doc()
        self.assertNotIn("None", doc)

    def test_a_NULL_gap_severity_reads_as_not_stated(self):
        self._pipeline()
        self._nullify("gap_severity")
        self.assertIn("gap:not stated", self._doc())

    def test_all_of_them_null_at_once_still_delivers_the_document(self):
        self._pipeline()
        self._nullify("category", "name", "description", "gap_severity")
        doc = self._doc()
        self.assertIn("## Solution Scope", doc)
        self.assertIn("Training", doc)


class TestASecondCallAnnouncesWhatItErased(BaseMCPTest):
    """The coverage block invites the analyst back to add `gap_source`. That second
    call carries `capabilities_json` and usually nothing else, and the tool replaces
    solution_scope wholesale — so "Explicitly out of scope" vanished from the delivered
    document without a word. The semantics stay a full replacement; the silence does
    not."""

    def setUp(self):
        super().setUp()
        _make_scope()

    def _caps(self):
        return json.dumps([{"name": "A", "category": "technology", "description": "d",
                            "gap_severity": "high", "gap_source": "6.2:technology",
                            "in_scope": True}])

    def test_dropping_the_exclusions_is_announced_with_a_count(self):
        define_solution_scope(PROJECT, self._caps(),
                              explicitly_excluded='["Mobile app", "Billing"]',
                              scope_summary="s")
        out = define_solution_scope(PROJECT, self._caps())
        self.assertIn("⚠️", out)
        self.assertIn("2 explicit exclusions", out)

    def test_clearing_the_summary_is_announced(self):
        define_solution_scope(PROJECT, self._caps(), scope_summary="A real summary")
        out = define_solution_scope(PROJECT, self._caps())
        self.assertIn("scope summary", out)

    def test_one_exclusion_is_announced_in_the_singular(self):
        define_solution_scope(PROJECT, self._caps(), explicitly_excluded='["Mobile"]')
        out = define_solution_scope(PROJECT, self._caps())
        self.assertIn("1 explicit exclusion ", out)

    def test_the_semantics_are_UNCHANGED_the_call_still_replaces_wholesale(self):
        """Warn, do not rescue: the contract stays a full replacement."""
        define_solution_scope(PROJECT, self._caps(),
                              explicitly_excluded='["Mobile app"]', scope_summary="s")
        define_solution_scope(PROJECT, self._caps())
        scope = _load_strategy()["solution_scope"]
        self.assertEqual(scope["explicitly_excluded"], [])
        self.assertEqual(scope["scope_summary"], "")

    def test_re_sending_both_values_triggers_no_warning(self):
        define_solution_scope(PROJECT, self._caps(),
                              explicitly_excluded='["Mobile app"]', scope_summary="s")
        out = define_solution_scope(PROJECT, self._caps(),
                                    explicitly_excluded='["Mobile app"]',
                                    scope_summary="s")
        self.assertNotIn("⚠️", out)

    def test_a_FIRST_call_with_neither_value_warns_about_nothing(self):
        out = define_solution_scope(PROJECT, self._caps())
        self.assertNotIn("⚠️", out)


class TestTheImportReplyCountsElementsNotRecords(BaseMCPTest):
    """Two source projects that analysed the same elements printed "4 elements —
    technology, policies, technology, policies" while the coverage block one call later
    said "(2 of 2 analysed)". Two texts about one thing, differing by a factor of two."""

    def test_duplicate_elements_across_sources_are_counted_once(self):
        _write_gap_file(project_id="src_a")
        _write_gap_file(project_id="src_b")
        result = _make_scope(source_project_ids='["src_a", "src_b"]')
        self.assertIn("Gap analysis (6.2): 2 elements — technology, policies", result)
        self.assertNotIn("technology, policies, technology", result)

    def test_the_mirror_itself_still_keeps_BOTH_records_with_their_provenance(self):
        """Only the count is deduplicated. The mirror stays a faithful copy — dropping
        a record would lose which project contributed it."""
        _write_gap_file(project_id="src_a")
        _write_gap_file(project_id="src_b")
        _make_scope(source_project_ids='["src_a", "src_b"]')
        gaps = _load_strategy()["imported_context"]["gaps"]
        self.assertEqual(len(gaps), 4)
        self.assertEqual({g["source_project"] for g in gaps}, {"src_a", "src_b"})

    def test_the_reply_count_and_the_coverage_denominator_agree(self):
        _write_gap_file(project_id="src_a")
        _write_gap_file(project_id="src_b")
        _make_scope(source_project_ids='["src_a", "src_b"]')
        out = define_solution_scope(PROJECT, json.dumps([
            {"name": "A", "category": "technology", "description": "d",
             "gap_severity": "high", "gap_source": "6.2:technology",
             "in_scope": True}]))
        self.assertIn("(1 of 2 analysed)", out)

    def test_distinct_elements_are_all_still_listed(self):
        _write_gap_file(project_id="src_a", gaps=[
            {"element": "technology", "gap_summary": "s", "complexity": "high"}])
        _write_gap_file(project_id="src_b", gaps=[
            {"element": "assets", "gap_summary": "s", "complexity": "low"}])
        result = _make_scope(source_project_ids='["src_a", "src_b"]')
        self.assertIn("Gap analysis (6.2): 2 elements — technology, assets", result)


if __name__ == "__main__":
    unittest.main()
