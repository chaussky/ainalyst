"""
tests/test_ch3.py — Тесты задачи 3 (Business Analysis Planning)

Покрытие:
  - suggest_ba_approach            (14 тестов)
  - plan_stakeholder_engagement    (14 тестов)
  - plan_ba_governance             (12 тестов)
  - plan_information_management    (12 тестов)
  - evaluate_ba_performance        (11 тестов)
  - save_ba_plan                   (10 тестов)
  - Утилиты (_safe, _classify_stakeholder, _load/_save_plan)  (7 тестов)
  - Интеграционные pipeline-тесты  (8 тестов)
Итого: ~88 тестов
"""

import json
import os
import sys
import unittest
from datetime import date
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import setup_mocks, BaseMCPTest

setup_mocks()

from skills.planning_mcp import (
    suggest_ba_approach,
    plan_stakeholder_engagement,
    plan_ba_governance,
    plan_information_management,
    evaluate_ba_performance,
    save_ba_plan,
    _safe, _classify_stakeholder, _load_plan, _save_plan,
    _plan_path,
    DATA_DIR,
)

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

PROJECT = "test_project_ch3"
TODAY = str(date.today())


def _load(project_id: str = PROJECT) -> dict:
    path = _plan_path(project_id)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _make_approach(project_id: str = PROJECT, **kwargs):
    params = dict(
        project_id=project_id,
        change_frequency="Medium",
        uncertainty="Medium",
        regulatory_need=False,
    )
    params.update(kwargs)
    return suggest_ba_approach(**params)


def _make_stakeholders(project_id: str = PROJECT, **kwargs):
    stakeholders = [
        {"name": "Спонсор", "role": "CEO", "influence": "High", "interest": "High", "attitude": "Champion"},
        {"name": "Пользователь", "role": "End User", "influence": "Low", "interest": "High", "attitude": "Neutral"},
    ]
    params = dict(
        project_id=project_id,
        stakeholders_json=json.dumps(stakeholders),
    )
    params.update(kwargs)
    return plan_stakeholder_engagement(**params)


def _make_governance(project_id: str = PROJECT, **kwargs):
    params = dict(
        project_id=project_id,
        project_criticality="Medium",
        decision_makers_json='["Sponsor", "PO"]',
    )
    params.update(kwargs)
    return plan_ba_governance(**params)


def _make_info_mgmt(project_id: str = PROJECT, **kwargs):
    params = dict(
        project_id=project_id,
        storage_tools_json='["Confluence", "Jira"]',
        traceability_level="Medium",
    )
    params.update(kwargs)
    return plan_information_management(**params)


def _make_performance(project_id: str = PROJECT, **kwargs):
    params = dict(
        project_id=project_id,
        current_issues_json='["нет шаблонов", "слабая трассировка"]',
    )
    params.update(kwargs)
    return evaluate_ba_performance(**params)


def _setup_full_pipeline(project_id: str = PROJECT) -> dict:
    _make_approach(project_id)
    _make_stakeholders(project_id)
    _make_governance(project_id)
    _make_info_mgmt(project_id)
    _make_performance(project_id)
    return _load(project_id)


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

class TestUtils(BaseMCPTest):

    def test_safe_spaces(self):
        self.assertEqual(_safe("CRM Project"), "crm_project")

    def test_safe_already_lower(self):
        self.assertEqual(_safe("test"), "test")

    def test_safe_mixed(self):
        self.assertEqual(_safe("My BA Plan"), "my_ba_plan")

    def test_classify_high_high(self):
        q, s, f = _classify_stakeholder("High", "High")
        self.assertEqual(q, "Key Players")

    def test_classify_high_low(self):
        q, s, f = _classify_stakeholder("High", "Low")
        self.assertEqual(q, "Context Setters")

    def test_classify_low_high(self):
        q, s, f = _classify_stakeholder("Low", "High")
        self.assertEqual(q, "Subjects")

    def test_classify_low_low(self):
        q, s, f = _classify_stakeholder("Low", "Low")
        self.assertEqual(q, "Crowd")


# ---------------------------------------------------------------------------
# suggest_ba_approach (3.1)
# ---------------------------------------------------------------------------

class TestSuggestBaApproach(BaseMCPTest):

    def test_basic_success(self):
        result = _make_approach()
        self.assertIn("✅", result)
        self.assertIn(PROJECT, result)

    def test_file_created(self):
        _make_approach()
        self.assertTrue(os.path.exists(_plan_path(PROJECT)))

    def test_high_high_agile(self):
        _make_approach(change_frequency="High", uncertainty="High")
        plan = _load()
        self.assertIn("Agile", plan["ba_approach"]["recommended_approach"])

    def test_low_low_predictive(self):
        _make_approach(change_frequency="Low", uncertainty="Low")
        plan = _load()
        self.assertIn("Predictive", plan["ba_approach"]["recommended_approach"])

    def test_regulatory_override_agile(self):
        _make_approach(change_frequency="High", uncertainty="High", regulatory_need=True)
        plan = _load()
        self.assertIn("Hybrid", plan["ba_approach"]["recommended_approach"])

    def test_regulatory_no_override_predictive(self):
        """Predictive + regulatory → остаётся Predictive (override только для Agile/Hybrid)."""
        _make_approach(change_frequency="Low", uncertainty="Low", regulatory_need=True)
        plan = _load()
        self.assertIn("Predictive", plan["ba_approach"]["recommended_approach"])

    def test_techniques_saved(self):
        _make_approach()
        plan = _load()
        self.assertIsInstance(plan["ba_approach"]["techniques"], list)
        self.assertGreater(len(plan["ba_approach"]["techniques"]), 0)

    def test_ba_notes_saved(self):
        _make_approach(ba_notes="Жёсткий дедлайн Q2")
        plan = _load()
        self.assertEqual(plan["ba_approach"]["ba_notes"], "Жёсткий дедлайн Q2")

    def test_decided_on_today(self):
        _make_approach()
        plan = _load()
        self.assertEqual(plan["ba_approach"]["decided_on"], TODAY)

    def test_hybrid_medium_medium(self):
        _make_approach(change_frequency="Medium", uncertainty="Medium")
        plan = _load()
        self.assertIn("Hybrid", plan["ba_approach"]["recommended_approach"])

    def test_second_call_overwrites(self):
        _make_approach(change_frequency="Low", uncertainty="Low")
        _make_approach(change_frequency="High", uncertainty="High")
        plan = _load()
        self.assertIn("Agile", plan["ba_approach"]["recommended_approach"])

    def test_output_contains_techniques(self):
        result = _make_approach()
        self.assertIn("Техники BABOK", result)

    def test_output_contains_next_step(self):
        result = _make_approach()
        self.assertIn("plan_stakeholder_engagement", result)

    def test_regulatory_note_in_output(self):
        result = _make_approach(change_frequency="High", uncertainty="High", regulatory_need=True)
        self.assertIn("Regulatory override", result)


# ---------------------------------------------------------------------------
# plan_stakeholder_engagement (3.2)
# ---------------------------------------------------------------------------

class TestPlanStakeholderEngagement(BaseMCPTest):

    def test_basic_success(self):
        result = _make_stakeholders()
        self.assertIn("✅", result)

    def test_stakeholders_saved(self):
        _make_stakeholders()
        plan = _load()
        stakeholders = plan["stakeholder_engagement"]["stakeholders"]
        self.assertEqual(len(stakeholders), 2)

    def test_quadrant_assigned(self):
        _make_stakeholders()
        plan = _load()
        stakeholders = plan["stakeholder_engagement"]["stakeholders"]
        names = [s["name"] for s in stakeholders]
        self.assertIn("Спонсор", names)
        sponsor = next(s for s in stakeholders if s["name"] == "Спонсор")
        self.assertEqual(sponsor["quadrant"], "Key Players")

    def test_subjects_quadrant(self):
        _make_stakeholders()
        plan = _load()
        user = next(s for s in plan["stakeholder_engagement"]["stakeholders"]
                    if s["name"] == "Пользователь")
        self.assertEqual(user["quadrant"], "Subjects")

    def test_invalid_json(self):
        result = plan_stakeholder_engagement(PROJECT, "not-json")
        self.assertIn("❌", result)

    def test_not_list(self):
        result = plan_stakeholder_engagement(PROJECT, '{"name": "test"}')
        self.assertIn("❌", result)

    def test_empty_list(self):
        result = plan_stakeholder_engagement(PROJECT, "[]")
        self.assertIn("⚠️", result)

    def test_missing_name(self):
        bad = [{"role": "CEO", "influence": "High", "interest": "High"}]
        result = plan_stakeholder_engagement(PROJECT, json.dumps(bad))
        self.assertIn("❌", result)

    def test_invalid_influence(self):
        bad = [{"name": "X", "influence": "VeryHigh", "interest": "High"}]
        result = plan_stakeholder_engagement(PROJECT, json.dumps(bad))
        self.assertIn("❌", result)

    def test_blocker_warning(self):
        stakeholders = [
            {"name": "Блокер", "role": "CTO", "influence": "High", "interest": "Low", "attitude": "Blocker"}
        ]
        result = plan_stakeholder_engagement(PROJECT, json.dumps(stakeholders))
        self.assertIn("Blockers", result)

    def test_comm_frequency_saved(self):
        _make_stakeholders()
        plan = _load()
        sponsor = next(s for s in plan["stakeholder_engagement"]["stakeholders"]
                       if s["name"] == "Спонсор")
        self.assertIn("comm_frequency", sponsor)
        self.assertTrue(len(sponsor["comm_frequency"]) > 0)

    def test_total_count_correct(self):
        _make_stakeholders()
        plan = _load()
        self.assertEqual(plan["stakeholder_engagement"]["total"], 2)

    def test_output_contains_next_step(self):
        result = _make_stakeholders()
        self.assertIn("plan_ba_governance", result)

    def test_contact_field_saved(self):
        stakeholders = [
            {"name": "Иван", "role": "PM", "influence": "High", "interest": "High",
             "attitude": "Champion", "contact": "ivan@test.com"}
        ]
        _make_stakeholders(stakeholders_json=json.dumps(stakeholders))
        plan = _load()
        ivan = next(s for s in plan["stakeholder_engagement"]["stakeholders"] if s["name"] == "Иван")
        self.assertEqual(ivan["contact"], "ivan@test.com")


# ---------------------------------------------------------------------------
# plan_ba_governance (3.3)
# ---------------------------------------------------------------------------

class TestPlanBaGovernance(BaseMCPTest):

    def test_basic_success(self):
        result = _make_governance()
        self.assertIn("✅", result)

    def test_governance_saved(self):
        _make_governance()
        plan = _load()
        self.assertIn("project_criticality", plan["governance"])

    def test_high_criticality(self):
        _make_governance(project_criticality="High")
        plan = _load()
        self.assertEqual(plan["governance"]["project_criticality"], "High")
        self.assertIn("CAB", plan["governance"]["change_control"])

    def test_low_criticality(self):
        _make_governance(project_criticality="Low")
        plan = _load()
        self.assertIn("Минимальный", plan["governance"]["change_control"])

    def test_decision_makers_saved(self):
        _make_governance(decision_makers_json='["Sponsor", "PO", "Lead BA"]')
        plan = _load()
        self.assertEqual(len(plan["governance"]["decision_makers"]), 3)
        self.assertIn("Sponsor", plan["governance"]["decision_makers"])

    def test_invalid_json(self):
        result = plan_ba_governance(PROJECT, "High", "not-json")
        self.assertIn("❌", result)

    def test_not_list(self):
        result = plan_ba_governance(PROJECT, "High", '{"key": "val"}')
        self.assertIn("❌", result)

    def test_custom_change_control(self):
        custom = "Все CR через weekly meeting"
        _make_governance(change_control_process=custom)
        plan = _load()
        self.assertEqual(plan["governance"]["change_control"], custom)

    def test_default_change_control_when_empty(self):
        _make_governance(change_control_process="")
        plan = _load()
        self.assertTrue(len(plan["governance"]["change_control"]) > 0)

    def test_escalation_path_present(self):
        _make_governance()
        plan = _load()
        self.assertIn("escalation_path", plan["governance"])

    def test_output_contains_next_step(self):
        result = _make_governance()
        self.assertIn("plan_information_management", result)

    def test_defined_on_today(self):
        _make_governance()
        plan = _load()
        self.assertEqual(plan["governance"]["defined_on"], TODAY)


# ---------------------------------------------------------------------------
# plan_information_management (3.4)
# ---------------------------------------------------------------------------

class TestPlanInformationManagement(BaseMCPTest):

    def test_basic_success(self):
        result = _make_info_mgmt()
        self.assertIn("✅", result)

    def test_tools_saved(self):
        _make_info_mgmt()
        plan = _load()
        tools = plan["information_management"]["storage_tools"]
        self.assertIn("Confluence", tools)
        self.assertIn("Jira", tools)

    def test_traceability_level_saved(self):
        _make_info_mgmt(traceability_level="High")
        plan = _load()
        self.assertEqual(plan["information_management"]["traceability_level"], "High")

    def test_traceability_description_present(self):
        _make_info_mgmt(traceability_level="High")
        plan = _load()
        desc = plan["information_management"]["traceability_description"]
        self.assertIn("Полная", desc)

    def test_artifact_types_saved(self):
        _make_info_mgmt(artifact_types_json='["User Story", "BRD"]')
        plan = _load()
        types = plan["information_management"]["artifact_types"]
        self.assertIn("User Story", types)

    def test_invalid_tools_json(self):
        result = plan_information_management(PROJECT, "not-json")
        self.assertIn("❌", result)

    def test_empty_tools(self):
        result = plan_information_management(PROJECT, "[]")
        self.assertIn("❌", result)

    def test_access_rules_default(self):
        _make_info_mgmt()
        plan = _load()
        self.assertIn("BA", plan["information_management"]["access_rules"])

    def test_custom_access_rules(self):
        _make_info_mgmt(access_rules="Только BA и PM")
        plan = _load()
        self.assertEqual(plan["information_management"]["access_rules"], "Только BA и PM")

    def test_output_contains_next_step(self):
        result = _make_info_mgmt()
        self.assertIn("evaluate_ba_performance", result)

    def test_defined_on_today(self):
        _make_info_mgmt()
        plan = _load()
        self.assertEqual(plan["information_management"]["defined_on"], TODAY)

    def test_three_tools(self):
        _make_info_mgmt(storage_tools_json='["Confluence", "Jira", "GitHub"]')
        plan = _load()
        self.assertEqual(len(plan["information_management"]["storage_tools"]), 3)


# ---------------------------------------------------------------------------
# evaluate_ba_performance (3.5)
# ---------------------------------------------------------------------------

class TestEvaluateBaPerformance(BaseMCPTest):

    def test_basic_success(self):
        result = _make_performance()
        self.assertIn("✅", result)

    def test_recommendations_generated(self):
        _make_performance()
        plan = _load()
        recs = plan["performance"]["recommendations"]
        self.assertGreater(len(recs), 0)

    def test_known_issue_matched(self):
        _make_performance(current_issues_json='["нет шаблонов"]')
        plan = _load()
        recs = [r["recommendation"] for r in plan["performance"]["recommendations"]]
        self.assertTrue(any("шаблон" in r.lower() for r in recs))

    def test_traceability_issue_matched(self):
        _make_performance(current_issues_json='["слабая трассировка"]')
        plan = _load()
        recs = [r["recommendation"] for r in plan["performance"]["recommendations"]]
        self.assertTrue(any("трассировк" in r.lower() for r in recs))

    def test_unknown_issue_flagged(self):
        _make_performance(current_issues_json='["загадочная проблема XYZ"]')
        plan = _load()
        recs = [r["recommendation"] for r in plan["performance"]["recommendations"]]
        self.assertTrue(any("ручного анализа" in r for r in recs))

    def test_empty_issues(self):
        _make_performance(current_issues_json="[]")
        plan = _load()
        recs = plan["performance"]["recommendations"]
        self.assertEqual(len(recs), 1)
        self.assertIn("ретроспективу", recs[0]["recommendation"])

    def test_metrics_saved(self):
        metrics = [{"name": "Defect Rate", "baseline": "15%", "target": "5%"}]
        _make_performance(metrics_json=json.dumps(metrics))
        plan = _load()
        self.assertEqual(len(plan["performance"]["metrics"]), 1)
        self.assertEqual(plan["performance"]["metrics"][0]["name"], "Defect Rate")

    def test_assessed_on_today(self):
        _make_performance()
        plan = _load()
        self.assertEqual(plan["performance"]["assessed_on"], TODAY)

    def test_output_contains_save_hint(self):
        result = _make_performance()
        self.assertIn("save_ba_plan", result)

    def test_issues_count_in_output(self):
        result = _make_performance(current_issues_json='["issue1", "issue2"]')
        self.assertIn("2", result)

    def test_multiple_known_issues(self):
        issues = ["нет шаблонов", "слабая трассировка", "scope creep"]
        _make_performance(current_issues_json=json.dumps(issues))
        plan = _load()
        self.assertEqual(len(plan["performance"]["current_issues"]), 3)


# ---------------------------------------------------------------------------
# save_ba_plan (финализация)
# ---------------------------------------------------------------------------

class TestSaveBaPlan(BaseMCPTest):

    def test_full_plan_success(self):
        _setup_full_pipeline()
        with patch("skills.planning_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            result = save_ba_plan(PROJECT)
        self.assertIn("✅", result)

    def test_save_artifact_called(self):
        _setup_full_pipeline()
        with patch("skills.planning_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            save_ba_plan(PROJECT)
            mock_sa.assert_called_once()

    def test_status_finalized(self):
        _setup_full_pipeline()
        with patch("skills.planning_mcp.save_artifact", return_value="✅"):
            save_ba_plan(PROJECT)
        plan = _load()
        self.assertEqual(plan["status"], "finalized")

    def test_finalized_on_today(self):
        _setup_full_pipeline()
        with patch("skills.planning_mcp.save_artifact", return_value="✅"):
            save_ba_plan(PROJECT)
        plan = _load()
        self.assertEqual(plan["finalized_on"], TODAY)

    def test_empty_plan_warning(self):
        # Создаём пустой план
        empty = {"project_id": "empty_ch3", "created": TODAY, "updated": TODAY,
                 "ba_approach": {}, "stakeholder_engagement": {},
                 "governance": {}, "information_management": {}, "performance": {}}
        _save_plan(empty, "empty_ch3")
        result = save_ba_plan("empty_ch3")
        self.assertIn("⚠️", result)

    def test_markdown_contains_approach(self):
        _setup_full_pipeline()
        captured = {}
        with patch("skills.planning_mcp.save_artifact") as mock_sa:
            mock_sa.side_effect = lambda c, n: captured.update({"content": c}) or "✅"
            save_ba_plan(PROJECT)
        self.assertIn("3.1", captured["content"])
        self.assertIn("Подход", captured["content"])

    def test_markdown_contains_stakeholders(self):
        _setup_full_pipeline()
        captured = {}
        with patch("skills.planning_mcp.save_artifact") as mock_sa:
            mock_sa.side_effect = lambda c, n: captured.update({"content": c}) or "✅"
            save_ba_plan(PROJECT)
        self.assertIn("Спонсор", captured["content"])

    def test_markdown_contains_governance(self):
        _setup_full_pipeline()
        captured = {}
        with patch("skills.planning_mcp.save_artifact") as mock_sa:
            mock_sa.side_effect = lambda c, n: captured.update({"content": c}) or "✅"
            save_ba_plan(PROJECT)
        self.assertIn("3.3", captured["content"])

    def test_artifact_name_contains_project(self):
        _setup_full_pipeline()
        captured = {}
        with patch("skills.planning_mcp.save_artifact") as mock_sa:
            mock_sa.side_effect = lambda c, n: captured.update({"name": n}) or "✅"
            save_ba_plan(PROJECT)
        self.assertIn("3_ba_plan", captured["name"])

    def test_json_path_in_output(self):
        _setup_full_pipeline()
        with patch("skills.planning_mcp.save_artifact", return_value="✅"):
            result = save_ba_plan(PROJECT)
        self.assertIn("ba_plan.json", result)


# ---------------------------------------------------------------------------
# Интеграционные pipeline-тесты
# ---------------------------------------------------------------------------

class TestPipeline(BaseMCPTest):

    def test_full_pipeline_json_structure(self):
        """Все 5 секций заполнены после полного пайплайна."""
        _setup_full_pipeline()
        plan = _load()
        self.assertIn("ba_approach", plan)
        self.assertIn("stakeholder_engagement", plan)
        self.assertIn("governance", plan)
        self.assertIn("information_management", plan)
        self.assertIn("performance", plan)

    def test_sections_not_empty(self):
        _setup_full_pipeline()
        plan = _load()
        self.assertTrue(len(plan["ba_approach"]) > 0)
        self.assertTrue(len(plan["stakeholder_engagement"]) > 0)
        self.assertTrue(len(plan["governance"]) > 0)
        self.assertTrue(len(plan["information_management"]) > 0)
        self.assertTrue(len(plan["performance"]) > 0)

    def test_project_id_preserved(self):
        _setup_full_pipeline()
        plan = _load()
        self.assertEqual(plan["project_id"], PROJECT)

    def test_updated_field_set(self):
        _setup_full_pipeline()
        plan = _load()
        self.assertEqual(plan["updated"], TODAY)

    def test_different_projects_isolated(self):
        proj_a = "pipeline_ch3_a"
        proj_b = "pipeline_ch3_b"
        _make_approach(project_id=proj_a, change_frequency="High", uncertainty="High")
        _make_approach(project_id=proj_b, change_frequency="Low", uncertainty="Low")
        plan_a = _load(proj_a)
        plan_b = _load(proj_b)
        self.assertIn("Agile", plan_a["ba_approach"]["recommended_approach"])
        self.assertIn("Predictive", plan_b["ba_approach"]["recommended_approach"])

    def test_later_step_does_not_overwrite_earlier(self):
        """plan_ba_governance не должен затирать ba_approach."""
        _make_approach()
        _make_governance()
        plan = _load()
        self.assertIn("recommended_approach", plan["ba_approach"])
        self.assertIn("project_criticality", plan["governance"])

    def test_stakeholder_data_in_plan_for_downstream(self):
        """Данные стейкхолдеров доступны из JSON для использования в 4.x."""
        _setup_full_pipeline()
        plan = _load()
        stakeholders = plan["stakeholder_engagement"]["stakeholders"]
        self.assertGreater(len(stakeholders), 0)
        # Каждый стейкхолдер имеет нужные поля для 4.x
        for s in stakeholders:
            self.assertIn("name", s)
            self.assertIn("role", s)
            self.assertIn("quadrant", s)
            self.assertIn("comm_frequency", s)

    def test_governance_fields_for_downstream_55(self):
        """Governance содержит поля нужные для 5.5 (approval, escalation)."""
        _setup_full_pipeline()
        plan = _load()
        gov = plan["governance"]
        self.assertIn("approval_process", gov)
        self.assertIn("escalation_path", gov)
        self.assertIn("change_control", gov)


if __name__ == "__main__":
    unittest.main()
