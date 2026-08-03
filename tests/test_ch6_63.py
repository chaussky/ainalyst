"""
tests/test_ch6_63.py — Tests for task 6.3 (Assess Risks)

Coverage:
  - scope_risk_assessment         (10 tests)
  - import_risks_from_context     (12 tests)
  - add_risk                      (18 tests)
  - set_risk_tolerance            (10 tests)
  - run_risk_matrix               (15 tests)
  - generate_recommendation       (14 tests)
  - save_risk_assessment          (16 tests)
  - Integration pipeline tests     (10 tests)
Total: ~105 tests
"""

import json
import os
import sys
import unittest
from datetime import date
from unittest.mock import patch

# Path setup
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import conftest for mocking
from tests.conftest import setup_mocks, BaseMCPTest, data_file

setup_mocks()

from skills.risk_assessment_mcp import (
    scope_risk_assessment,
    import_risks_from_context,
    add_risk,
    set_risk_tolerance,
    run_risk_matrix,
    generate_recommendation,
    save_risk_assessment,
    _safe, _zone_for_score, _next_risk_id,
    _assessment_path, _scope_path,
    DATA_DIR,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROJECT = "test_project"
TODAY = str(date.today())


def _load_assessment(project_id: str = PROJECT) -> dict:
    path = _assessment_path(project_id)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _make_scope(project_id: str = PROJECT, **kwargs):
    params = dict(
        project_id=project_id,
        initiative_type="new_system",
        analysis_depth="standard",
        source_project_ids="[]",
    )
    params.update(kwargs)
    return scope_risk_assessment(**params)


def _make_tolerance(project_id: str = PROJECT, **kwargs):
    params = dict(
        project_id=project_id,
        tolerance_level="neutral",
        max_acceptable_score=15,
    )
    params.update(kwargs)
    return set_risk_tolerance(**params)


def _add_sample_risk(project_id: str = PROJECT, likelihood: int = 3, impact: int = 3, **kwargs) -> str:
    params = dict(
        project_id=project_id,
        category="technical",
        source="future_state",
        description="If ERP integration takes longer than expected, the timeline will slip by 4 weeks",
        likelihood=likelihood,
        impact=impact,
        response_strategy="mitigate",
        mitigation_plan="Conduct prototyping in Sprint 0",
    )
    params.update(kwargs)
    return add_risk(**params)


def _setup_full_pipeline(
    project_id: str = PROJECT,
    num_risks: int = 3,
    tolerance: str = "neutral",
    threshold: int = 15,
) -> dict:
    """Creates a fully populated assessment for final-step tests."""
    _make_scope(project_id)
    _make_tolerance(project_id, tolerance_level=tolerance, max_acceptable_score=threshold)
    for i in range(num_risks):
        add_risk(
            project_id=project_id,
            category="technical",
            source="future_state",
            description=f"If risk {i + 1} materializes, then consequence {i + 1}",
            likelihood=3 + (i % 2),
            impact=3 + (i % 3),
            response_strategy="mitigate",
            mitigation_plan=f"Mitigation plan for risk {i + 1}",
        )
    run_risk_matrix(project_id)
    generate_recommendation(project_id, potential_value_summary="20% cost reduction")
    return _load_assessment(project_id)


# ---------------------------------------------------------------------------
# 1. scope_risk_assessment
# ---------------------------------------------------------------------------

class TestScopeRiskAssessment(BaseMCPTest):

    def test_scope_creates_json_file(self):
        _make_scope()
        self.assertTrue(os.path.exists(_scope_path(PROJECT)))

    def test_scope_creates_assessment_file(self):
        _make_scope()
        self.assertTrue(os.path.exists(_assessment_path(PROJECT)))

    def test_scope_stores_initiative_type(self):
        _make_scope(initiative_type="regulatory")
        data = _load_assessment()
        self.assertEqual(data["scope"]["initiative_type"], "regulatory")

    def test_scope_stores_analysis_depth(self):
        _make_scope(analysis_depth="comprehensive")
        data = _load_assessment()
        self.assertEqual(data["scope"]["analysis_depth"], "comprehensive")

    def test_scope_stores_source_project_ids(self):
        _make_scope(source_project_ids='["other_project"]')
        data = _load_assessment()
        self.assertIn("other_project", data["scope"]["source_project_ids"])

    def test_scope_empty_source_ids(self):
        result = _make_scope(source_project_ids="[]")
        self.assertIn("✅", result)

    def test_a_broken_source_id_is_refused_before_anything_is_written(self):
        """P3. Secondary ids were carried unchecked into a saved artifact under a ✅,
        and the refusal arrived a STEP LATER out of a path helper — saying
        "`project_id` cannot be …" when the analyst's own project_id was correct."""
        result = _make_scope(source_project_ids='["CRM Upgrade"]')
        self.assertIn("❌", result)
        self.assertIn("source_project_ids", result,
                      "the refusal blamed the wrong parameter")
        written = [os.path.join(r, f)
                   for r, _d, fs in os.walk("governance_plans") for f in fs]
        self.assertEqual(written, [], f"files were written before the refusal: {written}")

    def test_scope_invalid_source_ids_json(self):
        result = scope_risk_assessment(
            project_id=PROJECT,
            initiative_type="new_system",
            analysis_depth="standard",
            source_project_ids="not_json",
        )
        self.assertIn("❌", result)

    def test_scope_returns_success_message(self):
        result = _make_scope()
        self.assertIn("✅", result)
        self.assertIn(PROJECT, result)

    def test_scope_hint_for_sources(self):
        result = _make_scope(source_project_ids='["src_project"]')
        self.assertIn("import_risks_from_context", result)

    def test_scope_hint_without_sources(self):
        result = _make_scope(source_project_ids="[]")
        self.assertIn("add_risk", result)

    def test_scope_initializes_empty_risks(self):
        _make_scope()
        data = _load_assessment()
        self.assertEqual(data["risks"], [])

    def test_scope_all_initiative_types(self):
        types = ["process_improvement", "new_system", "regulatory", "cost_reduction", "market_opportunity", "other"]
        for t in types:
            result = scope_risk_assessment(
                project_id=f"proj_{t}",
                initiative_type=t,
                analysis_depth="quick",
            )
            self.assertIn("✅", result, f"Failed for type: {t}")


# ---------------------------------------------------------------------------
# 2. import_risks_from_context
# ---------------------------------------------------------------------------

class TestImportRisksFromContext(BaseMCPTest):

    def _write_json(self, project_id: str, suffix: str, data: dict):
        # The project_id is passed in, never derived from the file name. The name's
        # prefix IS the normalised id, but taking it back out of the name is a guess
        # (`b33_writer_future_state.json` -> `b33`) and seeds the fixture into a folder
        # no tool will ever look in.
        path = data_file(project_id, suffix)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def _write_fs_state(self, project_id: str = PROJECT):
        self._write_json(project_id, "future_state.json", {
            "constraints": [
                {"description": "Budget is limited", "category": "financial"},
                {"description": "Q3 deadline", "category": "time"},
            ]
        })

    def _write_gap(self, project_id: str = PROJECT):
        self._write_json(project_id, "gap_analysis.json", {
            "gaps": [
                {"element": "technology", "complexity": "high"},
                {"element": "capabilities", "complexity": "low"},
            ]
        })

    def _write_cs_state(self, project_id: str = PROJECT):
        # REAL 6.1 structure: root_causes at the top level, each with a `root_cause` field.
        self._write_json(project_id, "current_state.json", {
            "root_causes": [
                {"rca_id": "RCA-001", "problem_statement": "P", "root_cause": "Outdated processes"},
            ]
        })

    def _write_cs_needs(self, project_id: str = PROJECT):
        # REAL 6.1 structure: key `needs`, field `need_title`, capitalized priority.
        self._write_json(project_id, "business_needs.json", {
            "needs": [
                {"id": "BN-001", "need_title": "HR Automation", "priority": "High"},
                {"id": "BN-002", "need_title": "Cost Reduction", "priority": "Medium"},
                {"id": "BN-003", "need_title": "Compliance", "priority": "Critical"},
            ]
        })

    def _write_elicitation(self, project_id: str = PROJECT):
        self._write_json(project_id, "elicitation_results.json", {
            "risks_mentioned": [
                {"description": "Employee resistance to change", "stakeholder": "HR Director"},
            ]
        })

    def test_import_with_all_sources(self):
        _make_scope()
        self._write_fs_state()
        self._write_gap()
        self._write_cs_state()
        self._write_cs_needs()
        self._write_elicitation()

        result = import_risks_from_context(PROJECT, f'["{PROJECT}"]')
        self.assertIn("✅", result)
        data = _load_assessment()
        drafts = [r for r in data["risks"] if r.get("status") == "draft"]
        self.assertGreater(len(drafts), 0)

    def test_import_from_constraints(self):
        _make_scope()
        self._write_fs_state()
        result = import_risks_from_context(PROJECT, f'["{PROJECT}"]')
        self.assertIn("✅", result)
        data = _load_assessment()
        constraint_drafts = [r for r in data["risks"] if "constraint" in r.get("import_source", "")]
        self.assertGreater(len(constraint_drafts), 0)

    def test_import_from_gap_analysis(self):
        _make_scope()
        self._write_gap()
        import_risks_from_context(PROJECT, f'["{PROJECT}"]')
        data = _load_assessment()
        gap_drafts = [r for r in data["risks"] if "gap_analysis" in r.get("import_source", "")]
        self.assertGreater(len(gap_drafts), 0)

    def test_import_only_high_complexity_gaps(self):
        _make_scope()
        self._write_gap()
        import_risks_from_context(PROJECT, f'["{PROJECT}"]')
        data = _load_assessment()
        gap_drafts = [r for r in data["risks"] if "gap_analysis" in r.get("import_source", "")]
        # Only technology (high), not capabilities (low)
        self.assertEqual(len(gap_drafts), 1)

    def test_import_from_root_causes(self):
        _make_scope()
        self._write_cs_state()
        import_risks_from_context(PROJECT, f'["{PROJECT}"]')
        data = _load_assessment()
        rca_drafts = [r for r in data["risks"] if "root_cause" in r.get("import_source", "")]
        self.assertGreater(len(rca_drafts), 0)

    def test_import_only_high_priority_needs(self):
        _make_scope()
        self._write_cs_needs()
        import_risks_from_context(PROJECT, f'["{PROJECT}"]')
        data = _load_assessment()
        needs_drafts = [r for r in data["risks"] if "business_needs" in r.get("import_source", "")]
        # BN-001 (High) and BN-003 (Critical) import; BN-002 (Medium) does not.
        self.assertEqual(len(needs_drafts), 2)

    def test_import_from_elicitation(self):
        _make_scope()
        self._write_elicitation()
        import_risks_from_context(PROJECT, f'["{PROJECT}"]')
        data = _load_assessment()
        eli_drafts = [r for r in data["risks"] if "elicitation" in r.get("import_source", "")]
        self.assertGreater(len(eli_drafts), 0)

    def test_import_graceful_no_sources(self):
        _make_scope()
        result = import_risks_from_context(PROJECT, f'["{PROJECT}"]')
        # No artifacts — warning, not error
        self.assertNotIn("❌", result)

    def test_import_warnings_for_missing_sources(self):
        _make_scope()
        result = import_risks_from_context(PROJECT, f'["{PROJECT}"]')
        self.assertIn("⚠️", result)

    def test_import_drafts_have_correct_status(self):
        _make_scope()
        self._write_fs_state()
        import_risks_from_context(PROJECT, f'["{PROJECT}"]')
        data = _load_assessment()
        for r in data["risks"]:
            if r.get("import_source"):
                self.assertEqual(r["status"], "draft")

    def test_import_drafts_replaced_on_second_call(self):
        _make_scope()
        self._write_fs_state()
        import_risks_from_context(PROJECT, f'["{PROJECT}"]')
        data1 = _load_assessment()
        cnt1 = len([r for r in data1["risks"] if r.get("status") == "draft"])

        import_risks_from_context(PROJECT, f'["{PROJECT}"]')
        data2 = _load_assessment()
        cnt2 = len([r for r in data2["risks"] if r.get("status") == "draft"])
        # Do not accumulate — drafts are replaced
        self.assertEqual(cnt1, cnt2)

    def test_import_uses_default_project_id(self):
        _make_scope()
        self._write_fs_state()
        # Without source_project_ids — project_id is used
        result = import_risks_from_context(PROJECT)
        self.assertNotIn("❌", result)


# ---------------------------------------------------------------------------
# 3. add_risk
# ---------------------------------------------------------------------------

class TestAddRisk(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _make_scope()

    def test_add_risk_creates_assessment(self):
        _add_sample_risk()
        self.assertTrue(os.path.exists(_assessment_path(PROJECT)))

    def test_add_risk_auto_assigns_id(self):
        _add_sample_risk()
        data = _load_assessment()
        identified = [r for r in data["risks"] if r.get("status") == "identified"]
        self.assertEqual(identified[0]["risk_id"], "RK-001")

    def test_add_risk_sequential_ids(self):
        _add_sample_risk()
        _add_sample_risk()
        data = _load_assessment()
        identified = [r for r in data["risks"] if r.get("status") == "identified"]
        ids = [r["risk_id"] for r in identified]
        self.assertIn("RK-001", ids)
        self.assertIn("RK-002", ids)

    def test_add_risk_calculates_score(self):
        _add_sample_risk(likelihood=4, impact=3)
        data = _load_assessment()
        identified = [r for r in data["risks"] if r.get("status") == "identified"]
        self.assertEqual(identified[0]["risk_score"], 12)

    def test_add_risk_stores_category(self):
        _add_sample_risk(category="financial")
        data = _load_assessment()
        identified = [r for r in data["risks"] if r.get("status") == "identified"]
        self.assertEqual(identified[0]["category"], "financial")

    def test_add_risk_stores_strategy(self):
        _add_sample_risk(response_strategy="avoid")
        data = _load_assessment()
        identified = [r for r in data["risks"] if r.get("status") == "identified"]
        self.assertEqual(identified[0]["response_strategy"], "avoid")

    def test_add_risk_status_is_identified(self):
        _add_sample_risk()
        data = _load_assessment()
        identified = [r for r in data["risks"] if r.get("status") == "identified"]
        self.assertEqual(identified[0]["status"], "identified")

    def test_add_risk_rejects_likelihood_out_of_range(self):
        result = _add_sample_risk(likelihood=0)
        self.assertIn("❌", result)

    def test_add_risk_rejects_likelihood_too_high(self):
        result = _add_sample_risk(likelihood=6)
        self.assertIn("❌", result)

    def test_add_risk_rejects_impact_out_of_range(self):
        result = _add_sample_risk(impact=0)
        self.assertIn("❌", result)

    def test_add_risk_rejects_impact_too_high(self):
        result = _add_sample_risk(impact=6)
        self.assertIn("❌", result)

    def test_add_risk_warns_mitigate_without_plan(self):
        result = add_risk(
            project_id=PROJECT,
            category="technical",
            source="future_state",
            description="If X occurs, then Y follows",
            likelihood=3,
            impact=3,
            response_strategy="mitigate",
        )
        self.assertIn("⚠️", result)

    def test_add_risk_with_owner(self):
        _add_sample_risk(owner="SH-001")
        data = _load_assessment()
        identified = [r for r in data["risks"] if r.get("status") == "identified"]
        self.assertEqual(identified[0]["owner"], "SH-001")

    def test_add_risk_with_linked_bn(self):
        _add_sample_risk(linked_bn="BN-001")
        data = _load_assessment()
        identified = [r for r in data["risks"] if r.get("status") == "identified"]
        self.assertEqual(identified[0]["linked_bn"], "BN-001")

    def test_add_risk_removes_matching_draft(self):
        # Manually add a draft
        assessment = _load_assessment()
        desc = "If X occurs, then Y follows"
        assessment["risks"].append({
            "status": "draft",
            "description": desc,
            "import_source": "test",
        })
        with open(_assessment_path(PROJECT), "w", encoding="utf-8") as f:
            json.dump(assessment, f)

        add_risk(
            project_id=PROJECT,
            category="technical",
            source="future_state",
            description=desc,
            likelihood=3,
            impact=3,
            response_strategy="mitigate",
            mitigation_plan="Plan",
        )
        data = _load_assessment()
        draft_count = len([r for r in data["risks"] if r.get("status") == "draft"])
        self.assertEqual(draft_count, 0)

    def test_add_risk_all_categories(self):
        categories = ["strategic", "operational", "financial", "technical", "regulatory", "people", "external"]
        for cat in categories:
            result = add_risk(
                project_id=f"proj_{cat}",
                category=cat,
                source="change",
                description=f"If {cat} risk materializes, then consequence follows",
                likelihood=2,
                impact=2,
                response_strategy="accept",
            )
            self.assertIn("✅", result, f"Failed for category: {cat}")

    def test_add_risk_accept_without_plan_ok(self):
        result = add_risk(
            project_id=PROJECT,
            category="operational",
            source="change",
            description="If X occurs, then Y follows",
            likelihood=2,
            impact=2,
            response_strategy="accept",
        )
        self.assertIn("RK-", result)

    def test_add_risk_returns_total_count(self):
        _add_sample_risk()
        _add_sample_risk()
        result = _add_sample_risk()
        self.assertIn("3", result)


# ---------------------------------------------------------------------------
# 4. set_risk_tolerance
# ---------------------------------------------------------------------------

class TestSetRiskTolerance(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _make_scope()

    def test_tolerance_stores_level(self):
        _make_tolerance(tolerance_level="risk_averse")
        data = _load_assessment()
        self.assertEqual(data["risk_tolerance"]["level"], "risk_averse")

    def test_tolerance_stores_threshold(self):
        _make_tolerance(max_acceptable_score=12)
        data = _load_assessment()
        self.assertEqual(data["risk_tolerance"]["max_acceptable_score"], 12)

    def test_tolerance_stores_context(self):
        _make_tolerance(organization_context="Banking sector")
        data = _load_assessment()
        self.assertEqual(data["risk_tolerance"]["organization_context"], "Banking sector")

    def test_tolerance_invalid_threshold_zero(self):
        result = set_risk_tolerance(PROJECT, "neutral", max_acceptable_score=0)
        self.assertIn("❌", result)

    def test_tolerance_invalid_threshold_too_high(self):
        result = set_risk_tolerance(PROJECT, "neutral", max_acceptable_score=26)
        self.assertIn("❌", result)

    def test_tolerance_escalation_default_equals_threshold(self):
        _make_tolerance(max_acceptable_score=12)
        data = _load_assessment()
        self.assertEqual(data["risk_tolerance"]["escalation_threshold"], 12)

    def test_tolerance_custom_escalation(self):
        set_risk_tolerance(PROJECT, "neutral", max_acceptable_score=15, escalation_threshold=12)
        data = _load_assessment()
        self.assertEqual(data["risk_tolerance"]["escalation_threshold"], 12)

    def test_tolerance_mandatory_avoid_categories(self):
        set_risk_tolerance(PROJECT, "risk_averse", mandatory_avoid_categories='["regulatory"]')
        data = _load_assessment()
        self.assertIn("regulatory", data["risk_tolerance"]["mandatory_avoid_categories"])

    def test_tolerance_returns_success(self):
        result = _make_tolerance()
        self.assertIn("✅", result)

    def test_tolerance_hint_in_result(self):
        result = _make_tolerance(tolerance_level="risk_averse")
        self.assertIn("10–12", result)  # hint for risk_averse


# ---------------------------------------------------------------------------
# 5. run_risk_matrix
# ---------------------------------------------------------------------------

class TestRunRiskMatrix(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _make_scope()
        _make_tolerance(max_acceptable_score=15)

    def test_matrix_no_risks_returns_warning(self):
        result = run_risk_matrix(PROJECT)
        self.assertIn("⚠️", result)

    def test_matrix_classifies_high_risk(self):
        _add_sample_risk(likelihood=5, impact=5)  # score 25 >= 15
        run_risk_matrix(PROJECT)
        data = _load_assessment()
        high = [r for r in data["risk_matrix"]["classified_risks"] if r["zone"] == "high"]
        self.assertEqual(len(high), 1)

    def test_matrix_classifies_medium_risk(self):
        _add_sample_risk(likelihood=3, impact=3)  # score 9, 6<=9<15
        run_risk_matrix(PROJECT)
        data = _load_assessment()
        medium = [r for r in data["risk_matrix"]["classified_risks"] if r["zone"] == "medium"]
        self.assertEqual(len(medium), 1)

    def test_matrix_classifies_low_risk(self):
        _add_sample_risk(likelihood=1, impact=2)  # score 2, <=5
        run_risk_matrix(PROJECT)
        data = _load_assessment()
        low = [r for r in data["risk_matrix"]["classified_risks"] if r["zone"] == "low"]
        self.assertEqual(len(low), 1)

    def test_matrix_boundary_high(self):
        _add_sample_risk(likelihood=3, impact=5)  # score 15 == threshold
        run_risk_matrix(PROJECT)
        data = _load_assessment()
        high = [r for r in data["risk_matrix"]["classified_risks"] if r["zone"] == "high"]
        self.assertEqual(len(high), 1)

    def test_matrix_boundary_just_below_high(self):
        _add_sample_risk(likelihood=2, impact=7 // 2)  # score 14 < 15
        run_risk_matrix(PROJECT)
        data = _load_assessment()
        medium = [r for r in data["risk_matrix"]["classified_risks"] if r["zone"] == "medium"]
        self.assertGreaterEqual(len(medium), 1)

    def test_matrix_cumulative_profile_total_score(self):
        _add_sample_risk(likelihood=3, impact=4)  # score 12
        _add_sample_risk(likelihood=4, impact=4)  # score 16
        run_risk_matrix(PROJECT)
        data = _load_assessment()
        self.assertEqual(data["cumulative_profile"]["total_score"], 28)

    def test_matrix_cumulative_high_count(self):
        _add_sample_risk(likelihood=5, impact=4)  # score 20 - high
        _add_sample_risk(likelihood=2, impact=3)  # score 6 - medium
        run_risk_matrix(PROJECT)
        data = _load_assessment()
        self.assertEqual(data["cumulative_profile"]["high_risks_count"], 1)

    def test_matrix_above_threshold_equals_high_count(self):
        _add_sample_risk(likelihood=5, impact=5)
        run_risk_matrix(PROJECT)
        data = _load_assessment()
        self.assertEqual(
            data["cumulative_profile"]["above_threshold"],
            data["cumulative_profile"]["high_risks_count"]
        )

    def test_matrix_mandatory_avoid_flags_risk(self):
        set_risk_tolerance(PROJECT, "risk_averse", mandatory_avoid_categories='["regulatory"]')
        add_risk(
            project_id=PROJECT,
            category="regulatory",
            source="constraint",
            description="If the regulator changes requirements, a refactor will be needed",
            likelihood=2,
            impact=2,  # score 4 - normally low
            response_strategy="accept",
        )
        run_risk_matrix(PROJECT)
        data = _load_assessment()
        reg_risks = [r for r in data["risk_matrix"]["classified_risks"] if r["category"] == "regulatory"]
        # regulatory in mandatory_avoid → must be flagged as high
        self.assertEqual(reg_risks[0]["zone"], "high")

    def test_matrix_result_contains_zones(self):
        _add_sample_risk(likelihood=5, impact=5)
        result = run_risk_matrix(PROJECT)
        self.assertIn("🔴", result)

    def test_matrix_avg_score_calculated(self):
        _add_sample_risk(likelihood=4, impact=4)  # 16
        _add_sample_risk(likelihood=2, impact=2)  # 4
        run_risk_matrix(PROJECT)
        data = _load_assessment()
        self.assertEqual(data["cumulative_profile"]["avg_score"], 10.0)

    def test_matrix_respects_custom_threshold(self):
        _make_tolerance(max_acceptable_score=10)
        _add_sample_risk(likelihood=3, impact=4)  # score 12 >= 10 → high
        run_risk_matrix(PROJECT)
        data = _load_assessment()
        high = [r for r in data["risk_matrix"]["classified_risks"] if r["zone"] == "high"]
        self.assertEqual(len(high), 1)

    def test_matrix_stores_run_date(self):
        _add_sample_risk()
        run_risk_matrix(PROJECT)
        data = _load_assessment()
        self.assertEqual(data["risk_matrix"]["run_on"], TODAY)

    def test_matrix_low_count_correct(self):
        _add_sample_risk(likelihood=1, impact=1)  # score 1 - low
        _add_sample_risk(likelihood=1, impact=2)  # score 2 - low
        run_risk_matrix(PROJECT)
        data = _load_assessment()
        self.assertEqual(data["cumulative_profile"]["low_risks_count"], 2)


# ---------------------------------------------------------------------------
# 6. generate_recommendation
# ---------------------------------------------------------------------------

class TestGenerateRecommendation(BaseMCPTest):

    def _setup_with_risks(self, risks_config: list, tolerance_level="neutral", threshold=15):
        _make_scope()
        _make_tolerance(tolerance_level=tolerance_level, max_acceptable_score=threshold)
        for r in risks_config:
            add_risk(
                project_id=PROJECT,
                category=r.get("category", "technical"),
                source="future_state",
                description=r.get("description", "If X occurs, then Y follows"),
                likelihood=r.get("likelihood", 3),
                impact=r.get("impact", 3),
                response_strategy=r.get("strategy", "mitigate"),
                mitigation_plan=r.get("plan", "Mitigate"),
            )
        run_risk_matrix(PROJECT)

    def test_no_matrix_returns_warning(self):
        _make_scope()
        result = generate_recommendation(PROJECT)
        self.assertIn("⚠️", result)

    def test_no_high_risks_proceed_despite(self):
        self._setup_with_risks([{"likelihood": 1, "impact": 2}])  # score 2 - low
        result = generate_recommendation(PROJECT)
        self.assertIn("proceed_despite_risk", result)

    def test_high_risks_neutral_proceed_with_mitigation(self):
        self._setup_with_risks([{"likelihood": 5, "impact": 5, "strategy": "mitigate", "plan": "plan"}])
        result = generate_recommendation(PROJECT)
        self.assertIn("proceed_with_mitigation", result)

    # --- seek_higher_value: the ADR-073 branch that was unreachable -----------

    def test_risk_exceeds_value_emits_seek_higher_value(self):
        """ADR-073 defines seek_higher_value for "potential value < cumulative risk
        exposure", but no branch ever assigned it: 6.2 states value qualitatively and
        the exposure is a sum of 1-25 scores, so there is no honest arithmetic. The
        trade-off is now the BA's explicit judgement."""
        self._setup_with_risks([{"likelihood": 5, "impact": 5, "strategy": "mitigate", "plan": "plan"}])
        result = generate_recommendation(PROJECT, value_vs_risk="risk_exceeds_value")
        self.assertIn("seek_higher_value", result)

    def test_value_exceeds_risk_keeps_the_risk_verdict(self):
        self._setup_with_risks([{"likelihood": 5, "impact": 5, "strategy": "mitigate", "plan": "plan"}])
        result = generate_recommendation(PROJECT, value_vs_risk="value_exceeds_risk")
        self.assertIn("proceed_with_mitigation", result)

    def test_unassessed_value_behaves_exactly_as_before(self):
        self._setup_with_risks([{"likelihood": 5, "impact": 5, "strategy": "mitigate", "plan": "plan"}])
        self.assertIn("proceed_with_mitigation", generate_recommendation(PROJECT))

    def test_critical_risk_outranks_the_value_judgement(self):
        """An unresolvable critical risk is not a "revisit scope" situation."""
        _make_scope()
        _make_tolerance()
        add_risk(
            project_id=PROJECT, category="technical", source="future_state",
            description="If X occurs, then Y follows", likelihood=5, impact=5,
            response_strategy="accept",
        )
        run_risk_matrix(PROJECT)
        result = generate_recommendation(PROJECT, value_vs_risk="risk_exceeds_value")
        self.assertIn("do_not_proceed", result)

    def test_judgement_recorded_in_the_assessment(self):
        self._setup_with_risks([{"likelihood": 5, "impact": 5, "strategy": "mitigate", "plan": "plan"}])
        generate_recommendation(PROJECT, value_vs_risk="risk_exceeds_value")
        rec = _load_assessment(PROJECT)["recommendation"]
        self.assertEqual(rec["value_vs_risk"], "risk_exceeds_value")

    def test_prompt_when_high_risks_and_no_judgement(self):
        self._setup_with_risks([{"likelihood": 5, "impact": 5, "strategy": "mitigate", "plan": "plan"}])
        self.assertIn("value_vs_risk", generate_recommendation(PROJECT))

    def test_critical_without_mitigation_do_not_proceed(self):
        _make_scope()
        _make_tolerance()
        add_risk(
            project_id=PROJECT,
            category="technical",
            source="future_state",
            description="If X occurs, then Y follows",
            likelihood=5,
            impact=5,  # Critical, score 25
            response_strategy="accept",  # without mitigation_plan
        )
        run_risk_matrix(PROJECT)
        result = generate_recommendation(PROJECT)
        self.assertIn("do_not_proceed", result)

    def test_recommendation_stored_in_assessment(self):
        self._setup_with_risks([{"likelihood": 2, "impact": 2}])
        generate_recommendation(PROJECT)
        data = _load_assessment()
        self.assertIn("type", data["recommendation"])

    def test_recommendation_has_rationale(self):
        self._setup_with_risks([{"likelihood": 3, "impact": 3}])
        generate_recommendation(PROJECT)
        data = _load_assessment()
        self.assertTrue(len(data["recommendation"]["rationale"]) > 10)

    def test_recommendation_with_value_summary(self):
        self._setup_with_risks([{"likelihood": 2, "impact": 2}])
        result = generate_recommendation(PROJECT, potential_value_summary="ROI 150%")
        self.assertIn("ROI", result)

    def test_recommendation_stored_date(self):
        self._setup_with_risks([{"likelihood": 2, "impact": 2}])
        generate_recommendation(PROJECT)
        data = _load_assessment()
        self.assertEqual(data["recommendation"]["generated_on"], TODAY)

    def test_recommendation_high_count_in_rationale(self):
        self._setup_with_risks([
            {"likelihood": 5, "impact": 5, "strategy": "mitigate", "plan": "p1"},
            {"likelihood": 5, "impact": 4, "strategy": "mitigate", "plan": "p2"},
        ])
        generate_recommendation(PROJECT)
        data = _load_assessment()
        self.assertIn("2", data["recommendation"]["rationale"])

    def test_recommendation_do_not_proceed_warning(self):
        _make_scope()
        _make_tolerance()
        add_risk(PROJECT, "technical", "future_state", "X", 5, 5, "accept")
        run_risk_matrix(PROJECT)
        result = generate_recommendation(PROJECT)
        self.assertIn("⚠️", result)

    def test_proceed_despite_no_action_items(self):
        self._setup_with_risks([{"likelihood": 1, "impact": 1}])  # score 1 - low
        result = generate_recommendation(PROJECT)
        self.assertIn("proceed_despite_risk", result)

    def test_proceed_with_mitigation_shows_priority_actions(self):
        self._setup_with_risks([{"likelihood": 5, "impact": 5, "strategy": "mitigate", "plan": "Sprint 0 prototype"}])
        result = generate_recommendation(PROJECT)
        self.assertIn("Sprint 0", result)

    def test_risk_averse_with_high_risk(self):
        self._setup_with_risks(
            [{"likelihood": 3, "impact": 4, "strategy": "mitigate", "plan": "plan"}],
            tolerance_level="risk_averse",
            threshold=10
        )
        result = generate_recommendation(PROJECT)
        self.assertIn("proceed_with_mitigation", result)

    def test_recommendation_includes_total_risks(self):
        self._setup_with_risks([
            {"likelihood": 2, "impact": 2},
            {"likelihood": 3, "impact": 3},
        ])
        generate_recommendation(PROJECT)
        data = _load_assessment()
        self.assertIn("2", data["recommendation"]["rationale"])


# ---------------------------------------------------------------------------
# 7. save_risk_assessment
# ---------------------------------------------------------------------------

class TestSaveRiskAssessment(BaseMCPTest):

    def setUp(self):
        super().setUp()

    def test_save_empty_risks_warning(self):
        _make_scope()
        with patch("skills.risk_assessment_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            result = save_risk_assessment(PROJECT)
        self.assertIn("⚠️", result)

    def test_save_without_recommendation_warning(self):
        _make_scope()
        _make_tolerance()
        _add_sample_risk()
        run_risk_matrix(PROJECT)
        result = save_risk_assessment(PROJECT)
        self.assertIn("⚠️", result)

    def test_save_creates_json(self):
        _setup_full_pipeline()
        with patch("skills.risk_assessment_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            save_risk_assessment(PROJECT)
        self.assertTrue(os.path.exists(_assessment_path(PROJECT)))

    def test_save_calls_save_artifact(self):
        _setup_full_pipeline()
        with patch("skills.risk_assessment_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            save_risk_assessment(PROJECT)
            mock_sa.assert_called_once()

    def test_save_sets_finalized_status(self):
        _setup_full_pipeline()
        with patch("skills.risk_assessment_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            save_risk_assessment(PROJECT)
        data = _load_assessment()
        self.assertEqual(data["status"], "finalized")

    def test_save_stores_finalized_date(self):
        _setup_full_pipeline()
        with patch("skills.risk_assessment_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            save_risk_assessment(PROJECT)
        data = _load_assessment()
        self.assertEqual(data["finalized_on"], TODAY)

    def test_save_returns_json_path(self):
        _setup_full_pipeline()
        with patch("skills.risk_assessment_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            result = save_risk_assessment(PROJECT)
        self.assertIn("risk_assessment.json", result)

    def test_save_result_contains_risk_counts(self):
        _setup_full_pipeline(num_risks=3)
        with patch("skills.risk_assessment_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            result = save_risk_assessment(PROJECT)
        self.assertIn("3", result)

    def test_save_push_traceability_no_repo_warning(self):
        _setup_full_pipeline()
        with patch("skills.risk_assessment_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            result = save_risk_assessment(PROJECT, push_to_traceability=True)
        self.assertIn("⚠️", result)

    def test_save_push_traceability_with_repo(self):
        _setup_full_pipeline()
        # Create traceability repository
        repo = {
            "project": PROJECT,
            "requirements": [{"id": "BN-001", "type": "business_need", "title": "Test", "version": "1.0", "status": "confirmed", "added": TODAY}],
            "links": [],
            "history": [],
        }
        repo_path = data_file(_safe(PROJECT), "traceability_repo.json")
        with open(repo_path, "w", encoding="utf-8") as f:
            json.dump(repo, f)

        # Add linked_bn to the risk
        data = _load_assessment()
        if data["risks"]:
            data["risks"][0]["linked_bn"] = "BN-001"
            with open(_assessment_path(PROJECT), "w", encoding="utf-8") as f:
                json.dump(data, f)

        with patch("skills.risk_assessment_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            result = save_risk_assessment(PROJECT, push_to_traceability=True)
        self.assertIn("✅", result)

        # Verify risks were added to the repository
        with open(repo_path, encoding="utf-8") as f:
            updated_repo = json.load(f)
        risk_nodes = [r for r in updated_repo["requirements"] if r.get("type") == "risk"]
        self.assertGreater(len(risk_nodes), 0)

    def test_save_push_traceability_creates_threatens_links(self):
        _make_scope()
        _make_tolerance()
        add_risk(
            project_id=PROJECT,
            category="technical",
            source="future_state",
            description="If X occurs, then Y follows",
            likelihood=3,
            impact=3,
            response_strategy="mitigate",
            mitigation_plan="Plan",
            linked_bn="BN-001",
        )
        run_risk_matrix(PROJECT)
        generate_recommendation(PROJECT, potential_value_summary="Value")

        repo = {
            "project": PROJECT,
            "requirements": [{"id": "BN-001", "type": "business_need", "title": "T", "version": "1.0", "status": "confirmed", "added": TODAY}],
            "links": [],
        }
        repo_path = data_file(_safe(PROJECT), "traceability_repo.json")
        with open(repo_path, "w", encoding="utf-8") as f:
            json.dump(repo, f)

        with patch("skills.risk_assessment_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅"
            save_risk_assessment(PROJECT, push_to_traceability=True)

        with open(repo_path, encoding="utf-8") as f:
            updated = json.load(f)
        threatens = [lnk for lnk in updated.get("links", []) if lnk.get("relation") == "threatens"]
        self.assertGreater(len(threatens), 0)

    def test_save_push_traceability_is_idempotent_no_duplicate_threatens(self):
        """Re-running save_risk_assessment(push=True) must NOT duplicate threatens
        links. The risk node is deduplicated, but the threatens links were appended
        unconditionally on every call."""
        _make_scope()
        _make_tolerance()
        add_risk(
            project_id=PROJECT, category="technical", source="future_state",
            description="If X occurs, then Y follows", likelihood=3, impact=3,
            response_strategy="mitigate", mitigation_plan="Plan", linked_bn="BN-001",
        )
        run_risk_matrix(PROJECT)
        generate_recommendation(PROJECT, potential_value_summary="Value")

        repo = {
            "project": PROJECT,
            "requirements": [{"id": "BN-001", "type": "business_need", "title": "T", "version": "1.0", "status": "confirmed", "added": TODAY}],
            "links": [],
        }
        repo_path = data_file(_safe(PROJECT), "traceability_repo.json")
        with open(repo_path, "w", encoding="utf-8") as f:
            json.dump(repo, f)

        with patch("skills.risk_assessment_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅"
            save_risk_assessment(PROJECT, push_to_traceability=True)
            save_risk_assessment(PROJECT, push_to_traceability=True)  # re-finalize

        with open(repo_path, encoding="utf-8") as f:
            updated = json.load(f)
        threatens = [lnk for lnk in updated.get("links", []) if lnk.get("relation") == "threatens"]
        self.assertEqual(len(threatens), 1, "threatens links must not be duplicated on re-push")

    def test_save_assessment_json_structure(self):
        _setup_full_pipeline()
        with patch("skills.risk_assessment_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            save_risk_assessment(PROJECT)
        data = _load_assessment()
        for key in ["project_id", "risks", "risk_tolerance", "cumulative_profile", "recommendation"]:
            self.assertIn(key, data, f"Key '{key}' missing in assessment")

    def test_save_report_prefix(self):
        _setup_full_pipeline()
        with patch("skills.risk_assessment_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            save_risk_assessment(PROJECT)
        call_args = mock_sa.call_args
        self.assertIn("6_3_risk_assessment", call_args[0][1])

    def test_save_next_steps_shown(self):
        _setup_full_pipeline()
        with patch("skills.risk_assessment_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            result = save_risk_assessment(PROJECT)
        self.assertIn("6.4", result)


# ---------------------------------------------------------------------------
# 8. Integration tests (pipeline)
# ---------------------------------------------------------------------------

class TestPipeline(BaseMCPTest):

    def test_full_pipeline_no_high_risks(self):
        """Full pipeline: no High risks → proceed_despite_risk."""
        scope_risk_assessment(PROJECT, "new_system", "standard")
        set_risk_tolerance(PROJECT, "neutral", max_acceptable_score=15)
        add_risk(PROJECT, "technical", "future_state", "If X occurs, then Y follows", 1, 2, "accept")
        add_risk(PROJECT, "people", "stakeholder", "If Y occurs, then Z follows", 2, 2, "accept")
        run_risk_matrix(PROJECT)
        generate_recommendation(PROJECT, potential_value_summary="Value")
        with patch("skills.risk_assessment_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅"
            result = save_risk_assessment(PROJECT)
        self.assertIn("✅", result)
        data = _load_assessment()
        self.assertEqual(data["recommendation"]["type"], "proceed_despite_risk")

    def test_full_pipeline_with_high_risks(self):
        """Full pipeline: High risks present → proceed_with_mitigation."""
        scope_risk_assessment(PROJECT, "new_system", "comprehensive")
        set_risk_tolerance(PROJECT, "neutral", max_acceptable_score=15)
        add_risk(PROJECT, "technical", "future_state", "If integration is complex, then delay", 5, 5, "mitigate", mitigation_plan="Prototype")
        add_risk(PROJECT, "people", "stakeholder", "If there is no adoption, then failure", 3, 3, "mitigate", mitigation_plan="Training")
        run_risk_matrix(PROJECT)
        generate_recommendation(PROJECT)
        with patch("skills.risk_assessment_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅"
            result = save_risk_assessment(PROJECT)
        data = _load_assessment()
        self.assertEqual(data["recommendation"]["type"], "proceed_with_mitigation")

    def test_full_pipeline_risk_averse(self):
        """Pipeline with risk_averse and a low threshold."""
        scope_risk_assessment(PROJECT, "regulatory", "standard")
        set_risk_tolerance(PROJECT, "risk_averse", max_acceptable_score=10)
        add_risk(PROJECT, "regulatory", "constraint", "If the regulator changes rules, then fines apply", 3, 4, "mitigate", mitigation_plan="Monitoring")
        run_risk_matrix(PROJECT)
        result = generate_recommendation(PROJECT)
        self.assertIn("proceed_with_mitigation", result)

    def test_pipeline_without_import(self):
        """Pipeline without import_risks_from_context works correctly."""
        scope_risk_assessment(PROJECT, "cost_reduction", "quick")
        set_risk_tolerance(PROJECT, "neutral")
        add_risk(PROJECT, "financial", "change", "If the budget is cut, then scope will shrink", 3, 4, "mitigate", mitigation_plan="20% reserve")
        run_risk_matrix(PROJECT)
        generate_recommendation(PROJECT, potential_value_summary="15% OPEX reduction")
        data = _load_assessment()
        self.assertIn("type", data["recommendation"])

    def test_pipeline_multiple_projects_isolated(self):
        """Two projects do not interfere with each other."""
        for pid in ["project_a", "project_b"]:
            scope_risk_assessment(pid, "new_system", "quick")
            set_risk_tolerance(pid, "neutral")
            add_risk(pid, "technical", "future_state", f"Risk for {pid}", 3, 3, "mitigate", mitigation_plan="Plan")
            run_risk_matrix(pid)
            generate_recommendation(pid)

        with open(_assessment_path("project_a"), encoding="utf-8") as f:
            data_a = json.load(f)
        with open(_assessment_path("project_b"), encoding="utf-8") as f:
            data_b = json.load(f)
        self.assertEqual(data_a["project_id"], "project_a")
        self.assertEqual(data_b["project_id"], "project_b")

    def test_pipeline_risk_count_in_profile(self):
        _make_scope()
        _make_tolerance()
        for _ in range(5):
            _add_sample_risk()
        run_risk_matrix(PROJECT)
        data = _load_assessment()
        self.assertEqual(data["cumulative_profile"]["total_risks"], 5)

    def test_pipeline_do_not_proceed(self):
        """Critical risk without mitigation → do_not_proceed."""
        _make_scope()
        _make_tolerance()
        add_risk(PROJECT, "technical", "future_state", "Critical risk", 5, 5, "accept")
        run_risk_matrix(PROJECT)
        generate_recommendation(PROJECT)
        data = _load_assessment()
        self.assertEqual(data["recommendation"]["type"], "do_not_proceed")

    def test_assessment_json_is_valid_for_64(self):
        """JSON file contains all contract fields for 6.4 (ADR-076)."""
        _setup_full_pipeline()
        with patch("skills.risk_assessment_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅"
            save_risk_assessment(PROJECT)
        data = _load_assessment()
        # ADR-076 contract
        self.assertIn("project_id", data)
        self.assertIn("risk_tolerance", data)
        self.assertIn("risks", data)
        self.assertIn("cumulative_profile", data)
        self.assertIn("recommendation", data)

    def test_utility_zone_for_score(self):
        """Test for helper function _zone_for_score."""
        self.assertEqual(_zone_for_score(5, 15), "low")
        self.assertEqual(_zone_for_score(6, 15), "medium")
        self.assertEqual(_zone_for_score(14, 15), "medium")
        self.assertEqual(_zone_for_score(15, 15), "high")
        self.assertEqual(_zone_for_score(25, 15), "high")

    def test_utility_next_risk_id(self):
        """Test for helper function _next_risk_id."""
        self.assertEqual(_next_risk_id([]), "RK-001")
        risks = [{"risk_id": "RK-003"}, {"risk_id": "RK-001"}]
        self.assertEqual(_next_risk_id(risks), "RK-004")




class TestElicitationSourceWarning(BaseMCPTest):
    """The 4.2 branch used to skip silently while 6.1/6.2 warned (INT-H class)."""

    def test_missing_elicitation_artifact_is_reported(self):
        _make_scope()
        result = import_risks_from_context(PROJECT, f'["{PROJECT}"]')
        self.assertIn("4.2", result)
        self.assertIn("not found", result.lower())
        # Assert the actual sentence, not the bare token "4.2": that would pass on any
        # incidental occurrence elsewhere in the report.
        self.assertRegex(result, r"(?i)4\.2[^\n]*not found")


class TestElicitationSeamAgainstRealProducer(BaseMCPTest):
    """The seam 4.2 → 6.3, driven by the REAL producer instead of a hand-written fixture.

    Every other test on this contract writes its own idea of the file and then reads it
    back, which structurally cannot catch producer/consumer drift — the class that had
    the filename, the container shape AND the field name wrong simultaneously in 7.6-A.
    Here Chapter 4 writes and Chapter 6 reads, so a change to either side fails this.
    """

    PID = "seam_42_63"

    def _session(self, date_str, role, risks):
        import skills.elicitation_conduct_mcp as mod42
        return mod42.process_elicitation_results(
            project_name=self.PID, session_date=date_str, stakeholder_role=role,
            session_type="Interview",
            stakeholder_profile_json=json.dumps(
                {"influence": "High", "interest": "High", "attitude": "Neutral"}),
            pains_json=json.dumps([{"title": "Manual routing", "description": "By hand"}]),
            requirements_json=json.dumps({"functional": ["FR-001: auto-assign"]}),
            gaps_and_signals="-", ba_recommendations="-",
            maturity_level="Medium", maturity_notes="-",
            risks_json=json.dumps(risks))

    def test_risks_from_two_real_sessions_reach_63(self):
        _make_scope(self.PID)
        self._session("2026-03-15", "CFO",
                      [{"description": "The vendor may miss the deadline"}])
        self._session("2026-03-20", "Head of Support",
                      [{"description": "Support staff may resist the routing change"}])

        result = import_risks_from_context(self.PID, f'["{self.PID}"]')

        self.assertIn("vendor may miss", result.lower())
        self.assertIn("resist the routing", result.lower())

    def test_rerunning_a_session_does_not_duplicate_what_63_imports(self):
        _make_scope(self.PID)
        self._session("2026-03-15", "CFO", [{"description": "Vendor may miss the deadline"}])
        self._session("2026-03-15", "CFO", [{"description": "Vendor may miss the deadline"}])

        result = import_risks_from_context(self.PID, f'["{self.PID}"]')

        self.assertEqual(result.lower().count("vendor may miss the deadline"), 1,
                         "a re-run replaces the session slice, so 6.3 must see it once")

if __name__ == "__main__":
    unittest.main(verbosity=2)
