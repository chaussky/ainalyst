"""
tests/test_ch6_62.py — Тесты для BABOK 6.2 Define Future State.

Структура:
  - Unit (10): утилиты _safe, _next_goal_id, _validate_smart, _load/_save helpers
  - scope_future_state (12): типы инициатив, глубина, custom elements, с/без 6.1
  - capture_future_state_element (11): успех, обновление, вне скоупа, UX-паттерн 6.1, валидация
  - define_goals_and_objectives (13): SMART-валидация, регистрация в 5.1, связи BN→BG
  - capture_constraints (9): категории, статусы, обновление, валидация
  - run_gap_analysis (10): с 6.1, без 6.1, типы изменений, сложность
  - assess_potential_value (10): типы выгод, валидация, профиль ценности
  - check_future_state_completeness (10): полный, частичный, без скоупа, вердикты
  - save_future_state (8): финализация, push_to_business_context, без скоупа
  - Pipeline (7): полный, без 6.1, только скоуп+цели, gap без текущего состояния
  - Интеграция 7.3 from_strategy_project_id (8): ADR-065 предзаполнение

Итого: ~108 тестов
"""

import json
import os
import sys
import unittest
from datetime import date
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.conftest import setup_mocks, BaseMCPTest, make_test_repo, save_test_repo

setup_mocks()

from skills.future_state_mcp import (
    scope_future_state,
    capture_future_state_element,
    define_goals_and_objectives,
    capture_constraints,
    run_gap_analysis,
    assess_potential_value,
    check_future_state_completeness,
    save_future_state,
    _safe,
    _next_goal_id,
    _validate_smart,
    _load_scope,
    _load_state,
    _load_goals,
    _load_gap,
    VALID_ELEMENTS,
    ELEMENT_LABELS,
    DEFAULT_ELEMENTS_BY_TYPE,
)

from skills.requirements_validate_mcp import set_business_context

PROJECT = "test_project"


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _scope(project=PROJECT, initiative="process_improvement", depth="standard",
           goals="", elements=""):
    return scope_future_state(
        project_id=project,
        initiative_type=initiative,
        analysis_depth=depth,
        known_goals=goals,
        elements_in_scope=elements,
    )


def _capture(project=PROJECT, element="capabilities",
             description="Автоматизированный процесс согласования за 2 часа",
             target_metrics='{"processing_time": "2 hours"}',
             linked_bn='["BN-001"]', sources='["elicitation"]', notes=""):
    return capture_future_state_element(
        project_id=project,
        element=element,
        description=description,
        target_metrics=target_metrics,
        linked_business_needs=linked_bn,
        sources=sources,
        notes=notes,
    )


def _goal(project=PROJECT, title="Сократить время обработки заявок",
          description="Достичь скорости обработки 2 часа вместо 8",
          objectives='[{"title":"Время","metric":"часы","baseline":"8 часов","target":"2 часа","deadline":"2025-12-31"}]',
          linked_bn='["BN-001"]', register=True):
    return define_goals_and_objectives(
        project_id=project,
        goal_title=title,
        description=description,
        objectives_json=objectives,
        linked_business_needs=linked_bn,
        register_in_traceability=register,
    )


def _constraint(project=PROJECT, title="Бюджет проекта",
                category="budget", description="Бюджет ограничен 5 млн руб.",
                status="confirmed", linked="[]"):
    return capture_constraints(
        project_id=project,
        constraint_title=title,
        category=category,
        description=description,
        status=status,
        linked_elements=linked,
    )


def _value(project=PROJECT,
           benefits='[{"benefit_title":"Ускорение процесса","benefit_type":"operational","magnitude":"high","confidence":"medium","description":"Текст"}]',
           investment="medium", summary="Высокая ценность при среднем уровне инвестиций"):
    return assess_potential_value(
        project_id=project,
        benefits_json=benefits,
        investment_level=investment,
        value_summary=summary,
    )


def _save_current_state_data(project=PROJECT):
    """Сохраняет тестовые данные 6.1 для проверки интеграции."""
    os.makedirs("governance_plans/data", exist_ok=True)
    # current_state_scope
    scope_data = {
        "project_id": project,
        "initiative_type": "process_improvement",
        "analysis_depth": "standard",
        "known_problems": "Время обработки выросло с 2 до 8 часов",
        "elements_in_scope": ["business_needs", "capabilities", "technology", "policies"],
        "session_ids_imported": [],
        "created": str(date.today()),
        "updated": str(date.today()),
    }
    with open(f"governance_plans/data/{_safe(project)}_current_state_scope.json", "w") as f:
        json.dump(scope_data, f)

    # current_state
    state_data = {
        "project_id": project,
        "elements": {
            "capabilities": {
                "description": "Ручной процесс согласования, 8 часов, 3 уровня",
                "pain_points": ["Медленно", "Много ошибок", "Нет уведомлений"],
                "metrics": {"processing_time": "8 hours", "error_rate": "12%"},
                "sources": ["interview"],
                "notes": "",
                "draft": False,
                "last_updated": str(date.today()),
            }
        },
        "root_causes": [],
        "created": str(date.today()),
        "updated": str(date.today()),
    }
    with open(f"governance_plans/data/{_safe(project)}_current_state.json", "w") as f:
        json.dump(state_data, f)

    # business_needs
    needs_data = {
        "project_id": project,
        "needs": [
            {
                "id": "BN-001",
                "need_title": "Ускорить обработку заявок",
                "description": "Время выросло с 2 до 8 часов",
                "need_type": "problem",
                "priority": "High",
                "source": "Директор",
                "root_cause_ids": [],
                "created": str(date.today()),
            },
            {
                "id": "BN-002",
                "need_title": "Снизить уровень ошибок",
                "description": "Ошибки составляют 12%",
                "need_type": "problem",
                "priority": "Medium",
                "source": "Директор",
                "root_cause_ids": [],
                "created": str(date.today()),
            },
        ],
        "created": str(date.today()),
        "updated": str(date.today()),
    }
    with open(f"governance_plans/data/{_safe(project)}_business_needs.json", "w") as f:
        json.dump(needs_data, f)


def _save_future_state_goals(project=PROJECT):
    """Сохраняет тестовые данные 6.2 goals для проверки интеграции 7.3."""
    os.makedirs("governance_plans/data", exist_ok=True)
    goals_data = {
        "project_id": project,
        "goals": [
            {
                "id": "BG-001",
                "goal_title": "Сократить время обработки до 2 часов",
                "description": "Автоматизировать согласование",
                "objectives": [
                    {
                        "title": "Время обработки",
                        "metric": "часы",
                        "baseline": "8 часов",
                        "target": "2 часа",
                        "deadline": "2025-12-31",
                    }
                ],
                "linked_business_needs": ["BN-001"],
                "smart_validated": True,
                "created": str(date.today()),
            }
        ],
        "created": str(date.today()),
        "updated": str(date.today()),
    }
    with open(f"governance_plans/data/{_safe(project)}_future_state_goals.json", "w") as f:
        json.dump(goals_data, f)


def _full_pipeline(project=PROJECT, with_current_state=True):
    """Запускает полный pipeline 6.2."""
    if with_current_state:
        _save_current_state_data(project)

    repo = make_test_repo(project)
    repo["project"] = project
    repo["requirements"] = []
    repo["links"] = []
    save_test_repo(repo, "governance_plans/data")

    _scope(project=project)
    _capture(project=project, element="capabilities")
    _capture(project=project, element="technology",
             description="Облачная платформа с API-интеграцией")
    _goal(project=project)
    _constraint(project=project)
    run_gap_analysis(project_id=project)
    _value(project=project)


# ---------------------------------------------------------------------------
# Unit-тесты
# ---------------------------------------------------------------------------

class TestUtils(BaseMCPTest):

    def test_safe_lowercase(self):
        self.assertEqual(_safe("My Project"), "my_project")

    def test_safe_spaces_to_underscore(self):
        self.assertEqual(_safe("project 2025"), "project_2025")

    def test_safe_already_clean(self):
        self.assertEqual(_safe("test_project"), "test_project")

    def test_next_goal_id_empty(self):
        goals_data = {"goals": []}
        self.assertEqual(_next_goal_id(goals_data), "BG-001")

    def test_next_goal_id_sequential(self):
        goals_data = {"goals": [{"id": "BG-001"}, {"id": "BG-002"}]}
        self.assertEqual(_next_goal_id(goals_data), "BG-003")

    def test_next_goal_id_gap(self):
        goals_data = {"goals": [{"id": "BG-001"}, {"id": "BG-005"}]}
        self.assertEqual(_next_goal_id(goals_data), "BG-006")

    def test_validate_smart_ok(self):
        objectives = [{"title": "KPI", "metric": "часы", "baseline": "8", "target": "2", "deadline": "2025-12-31"}]
        issues = _validate_smart("Сократить время обработки заявок", "Достичь скорости", objectives)
        self.assertEqual(issues, [])

    def test_validate_smart_no_kpi(self):
        issues = _validate_smart("Улучшить процесс", "Описание", [])
        self.assertTrue(any("Measurable" in i for i in issues))

    def test_validate_smart_no_target(self):
        objectives = [{"title": "KPI", "metric": "часы", "baseline": "8"}]
        issues = _validate_smart("Сократить время обработки", "Описание", objectives)
        self.assertTrue(any("target" in i for i in issues))

    def test_validate_smart_no_deadline(self):
        objectives = [{"title": "KPI", "metric": "часы", "baseline": "8", "target": "2"}]
        issues = _validate_smart("Сократить время обработки", "Описание", objectives)
        self.assertTrue(any("Time-bound" in i for i in issues))


# ---------------------------------------------------------------------------
# scope_future_state
# ---------------------------------------------------------------------------

class TestScopeFutureState(BaseMCPTest):

    def test_scope_basic_success(self):
        r = _scope()
        self.assertIn("✅", r)
        self.assertIn(PROJECT, r)

    def test_scope_creates_file(self):
        _scope()
        scope = _load_scope(PROJECT)
        self.assertIsNotNone(scope)
        self.assertEqual(scope["initiative_type"], "process_improvement")

    def test_scope_light_depth_3_elements(self):
        _scope(depth="light")
        scope = _load_scope(PROJECT)
        self.assertLessEqual(len(scope["elements_in_scope"]), 4)

    def test_scope_deep_all_8_elements(self):
        _scope(depth="deep")
        scope = _load_scope(PROJECT)
        self.assertEqual(len(scope["elements_in_scope"]), 8)

    def test_scope_standard_default_elements(self):
        _scope(initiative="new_system", depth="standard")
        scope = _load_scope(PROJECT)
        self.assertIn("business_needs", scope["elements_in_scope"])

    def test_scope_custom_elements(self):
        r = _scope(elements='["business_needs","technology"]')
        self.assertIn("✅", r)
        scope = _load_scope(PROJECT)
        self.assertEqual(scope["elements_in_scope"], ["business_needs", "technology"])

    def test_scope_invalid_element(self):
        r = _scope(elements='["unknown_element"]')
        self.assertIn("❌", r)

    def test_scope_invalid_json(self):
        r = _scope(elements="not_json")
        self.assertIn("❌", r)

    def test_scope_update(self):
        _scope(depth="light")
        r = _scope(depth="deep")
        scope = _load_scope(PROJECT)
        self.assertEqual(scope["analysis_depth"], "deep")
        self.assertIn("ОБНОВЛЁН", r)

    def test_scope_with_known_goals(self):
        r = _scope(goals="Хотим ускорить обработку в 4 раза")
        self.assertIn("Известные цели", r)

    def test_scope_with_current_state_data(self):
        _save_current_state_data()
        r = _scope()
        self.assertIn("6.1 найдены", r)

    def test_scope_without_current_state(self):
        r = _scope()
        self.assertIn("6.1 не найдены", r)

    def test_scope_market_opportunity_all_elements(self):
        _scope(initiative="market_opportunity", depth="standard")
        scope = _load_scope(PROJECT)
        self.assertEqual(len(scope["elements_in_scope"]), 8)


# ---------------------------------------------------------------------------
# capture_future_state_element
# ---------------------------------------------------------------------------

class TestCaptureFutureStateElement(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _scope()

    def test_capture_basic_success(self):
        r = _capture()
        self.assertIn("✅", r)
        self.assertIn("capabilities", r)

    def test_capture_saves_to_state(self):
        _capture(element="capabilities", description="Новый автоматизированный процесс")
        state = _load_state(PROJECT)
        self.assertIn("capabilities", state["elements"])
        self.assertEqual(state["elements"]["capabilities"]["description"], "Новый автоматизированный процесс")

    def test_capture_update_existing(self):
        _capture(element="technology", description="Первая версия")
        _capture(element="technology", description="Обновлённое описание")
        state = _load_state(PROJECT)
        self.assertEqual(state["elements"]["technology"]["description"], "Обновлённое описание")
        self.assertFalse(state["elements"]["technology"]["draft"])

    def test_capture_empty_description_error(self):
        r = capture_future_state_element(
            project_id=PROJECT, element="capabilities", description="   "
        )
        self.assertIn("❌", r)

    def test_capture_invalid_target_metrics_json(self):
        r = capture_future_state_element(
            project_id=PROJECT, element="capabilities",
            description="Описание", target_metrics="not_json"
        )
        self.assertIn("❌", r)

    def test_capture_invalid_linked_bn_json(self):
        r = capture_future_state_element(
            project_id=PROJECT, element="capabilities",
            description="Описание", linked_business_needs="not_json"
        )
        self.assertIn("❌", r)

    def test_capture_target_metrics_stored(self):
        _capture(target_metrics='{"speed": "2h", "accuracy": "99%"}')
        state = _load_state(PROJECT)
        self.assertEqual(state["elements"]["capabilities"]["target_metrics"]["speed"], "2h")

    def test_capture_linked_bn_stored(self):
        _capture(linked_bn='["BN-001","BN-002"]')
        state = _load_state(PROJECT)
        self.assertIn("BN-001", state["elements"]["capabilities"]["linked_business_needs"])

    def test_capture_shows_current_state_context(self):
        _save_current_state_data()
        r = _capture(element="capabilities")
        self.assertIn("текущее состояние", r.lower())

    def test_capture_out_of_scope_warning(self):
        r = capture_future_state_element(
            project_id=PROJECT,
            element="external",  # не в стандартном скоупе process_improvement
            description="Внешние партнёры",
        )
        # Должно сохранить, но предупредить
        state = _load_state(PROJECT)
        self.assertIn("external", state["elements"])

    def test_capture_progress_shown(self):
        r = _capture(element="capabilities")
        self.assertIn("Прогресс", r)


# ---------------------------------------------------------------------------
# define_goals_and_objectives
# ---------------------------------------------------------------------------

class TestDefineGoalsAndObjectives(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _scope()

    def test_goal_basic_success(self):
        r = _goal()
        self.assertIn("✅", r)
        self.assertIn("BG-001", r)

    def test_goal_saved_to_file(self):
        _goal()
        goals_data = _load_goals(PROJECT)
        self.assertEqual(len(goals_data["goals"]), 1)
        self.assertEqual(goals_data["goals"][0]["id"], "BG-001")

    def test_goal_sequential_ids(self):
        _goal(title="Цель 1")
        _goal(title="Цель 2")
        goals_data = _load_goals(PROJECT)
        ids = [g["id"] for g in goals_data["goals"]]
        self.assertIn("BG-001", ids)
        self.assertIn("BG-002", ids)

    def test_goal_smart_valid(self):
        r = _goal()
        self.assertIn("SMART-критерии соблюдены", r)
        goals_data = _load_goals(PROJECT)
        self.assertTrue(goals_data["goals"][0]["smart_validated"])

    def test_goal_smart_no_kpi_warning(self):
        r = define_goals_and_objectives(
            project_id=PROJECT,
            goal_title="Улучшить процесс",
            description="Описание",
            objectives_json="[]",
        )
        self.assertIn("SMART-замечания", r)

    def test_goal_empty_title_error(self):
        r = define_goals_and_objectives(
            project_id=PROJECT, goal_title="", description="Описание",
            objectives_json="[]"
        )
        self.assertIn("❌", r)

    def test_goal_invalid_objectives_json(self):
        r = define_goals_and_objectives(
            project_id=PROJECT, goal_title="Цель",
            description="Описание", objectives_json="not_json"
        )
        self.assertIn("❌", r)

    def test_goal_registers_in_traceability(self):
        repo = make_test_repo(PROJECT)
        repo["project"] = PROJECT
        repo["requirements"] = []
        repo["links"] = []
        save_test_repo(repo, "governance_plans/data")

        _goal(linked_bn='["BN-001"]', register=True)

        with open(f"governance_plans/data/{_safe(PROJECT)}_traceability_repo.json") as f:
            updated_repo = json.load(f)

        ids = [r["id"] for r in updated_repo["requirements"]]
        self.assertIn("BG-001", ids)

    def test_goal_creates_bn_bg_link(self):
        repo = make_test_repo(PROJECT)
        repo["project"] = PROJECT
        repo["requirements"] = []
        repo["links"] = []
        save_test_repo(repo, "governance_plans/data")

        _goal(linked_bn='["BN-001"]')

        with open(f"governance_plans/data/{_safe(PROJECT)}_traceability_repo.json") as f:
            updated_repo = json.load(f)

        links = updated_repo["links"]
        derives_links = [l for l in links if l["relation"] == "derives"]
        self.assertTrue(any(l["from"] == "BG-001" and l["to"] == "BN-001" for l in derives_links))

    def test_goal_no_repo_warning(self):
        r = _goal(register=True)
        self.assertIn("не найден", r.lower())

    def test_goal_register_false_no_repo_needed(self):
        r = _goal(register=False)
        self.assertIn("BG-001", r)
        # Без репозитория не должно быть ошибки

    def test_goal_linked_bn_stored(self):
        _goal(linked_bn='["BN-001","BN-002"]')
        goals_data = _load_goals(PROJECT)
        self.assertIn("BN-001", goals_data["goals"][0]["linked_business_needs"])

    def test_goal_objectives_stored(self):
        _goal()
        goals_data = _load_goals(PROJECT)
        objectives = goals_data["goals"][0]["objectives"]
        self.assertEqual(objectives[0]["target"], "2 часа")


# ---------------------------------------------------------------------------
# capture_constraints
# ---------------------------------------------------------------------------

class TestCaptureConstraints(BaseMCPTest):

    def test_constraint_basic_success(self):
        r = _constraint()
        self.assertIn("✅", r)
        self.assertIn("Бюджет", r)

    def test_constraint_saved_to_state(self):
        _constraint(title="Бюджет", category="budget", description="5 млн")
        state = _load_state(PROJECT)
        self.assertEqual(len(state["constraints"]), 1)
        self.assertEqual(state["constraints"][0]["title"], "Бюджет")

    def test_constraint_multiple_categories(self):
        _constraint(title="Бюджет", category="budget")
        _constraint(title="Дедлайн", category="time", description="Запуск до 01.04")
        _constraint(title="152-ФЗ", category="compliance", description="Соответствие")
        state = _load_state(PROJECT)
        self.assertEqual(len(state["constraints"]), 3)

    def test_constraint_assumed_status_warning(self):
        r = _constraint(status="assumed")
        self.assertIn("предположение", r.lower())

    def test_constraint_confirmed_status(self):
        r = _constraint(status="confirmed")
        self.assertIn("Подтверждено", r)

    def test_constraint_empty_title_error(self):
        r = capture_constraints(
            project_id=PROJECT, constraint_title="",
            category="budget", description="Описание", status="confirmed"
        )
        self.assertIn("❌", r)

    def test_constraint_empty_description_error(self):
        r = capture_constraints(
            project_id=PROJECT, constraint_title="Бюджет",
            category="budget", description="", status="confirmed"
        )
        self.assertIn("❌", r)

    def test_constraint_invalid_linked_elements(self):
        r = capture_constraints(
            project_id=PROJECT, constraint_title="Ограничение",
            category="other", description="Описание", status="confirmed",
            linked_elements='["unknown_element"]'
        )
        self.assertIn("❌", r)

    def test_constraint_update_existing(self):
        _constraint(title="Бюджет", description="Первое описание")
        _constraint(title="Бюджет", description="Обновлённое описание")
        state = _load_state(PROJECT)
        budget_items = [c for c in state["constraints"] if c["title"] == "Бюджет"]
        self.assertEqual(len(budget_items), 1)
        self.assertEqual(budget_items[0]["description"], "Обновлённое описание")


# ---------------------------------------------------------------------------
# run_gap_analysis
# ---------------------------------------------------------------------------

class TestRunGapAnalysis(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _scope()
        _capture(element="capabilities", description="Автоматизированный процесс")
        _capture(element="technology", description="Облачная платформа")

    def test_gap_basic_success(self):
        r = run_gap_analysis(project_id=PROJECT)
        self.assertIn("✅", r)
        self.assertIn("Gap-анализ проведён", r)

    def test_gap_creates_file(self):
        run_gap_analysis(project_id=PROJECT)
        gap = _load_gap(PROJECT)
        self.assertIsNotNone(gap)
        self.assertIn("gaps", gap)

    def test_gap_elements_count(self):
        run_gap_analysis(project_id=PROJECT)
        gap = _load_gap(PROJECT)
        self.assertEqual(len(gap["gaps"]), 2)

    def test_gap_without_current_state(self):
        run_gap_analysis(project_id=PROJECT)
        gap = _load_gap(PROJECT)
        self.assertFalse(gap["has_current_state_baseline"])
        for g in gap["gaps"]:
            self.assertEqual(g["change_type"], "new")
            self.assertIsNone(g["current_description"])

    def test_gap_with_current_state(self):
        _save_current_state_data()
        run_gap_analysis(project_id=PROJECT)
        gap = _load_gap(PROJECT)
        self.assertTrue(gap["has_current_state_baseline"])
        caps_gap = next((g for g in gap["gaps"] if g["element"] == "capabilities"), None)
        self.assertIsNotNone(caps_gap)
        self.assertIsNotNone(caps_gap["current_description"])

    def test_gap_improve_type_with_current_state(self):
        _save_current_state_data()
        run_gap_analysis(project_id=PROJECT)
        gap = _load_gap(PROJECT)
        caps_gap = next((g for g in gap["gaps"] if g["element"] == "capabilities"), None)
        self.assertEqual(caps_gap["change_type"], "improve")

    def test_gap_sets_done_flag(self):
        run_gap_analysis(project_id=PROJECT)
        state = _load_state(PROJECT)
        self.assertTrue(state["gap_analysis_done"])

    def test_gap_no_elements_error(self):
        # Пустой project
        r = run_gap_analysis(project_id="empty_project")
        self.assertIn("⚠️", r)

    def test_gap_summary_in_report(self):
        run_gap_analysis(project_id=PROJECT)
        # Проверяем что сводка по типам есть в отчёте
        r = run_gap_analysis(project_id=PROJECT)
        self.assertIn("Сводка", r)

    def test_gap_complexity_assigned(self):
        _save_current_state_data()
        run_gap_analysis(project_id=PROJECT)
        gap = _load_gap(PROJECT)
        for g in gap["gaps"]:
            self.assertIn(g["complexity"], ["low", "medium", "high"])


# ---------------------------------------------------------------------------
# assess_potential_value
# ---------------------------------------------------------------------------

class TestAssessPotentialValue(BaseMCPTest):

    def test_value_basic_success(self):
        r = _value()
        self.assertIn("✅", r)
        self.assertIn("Потенциальная ценность оценена", r)

    def test_value_saved_to_state(self):
        _value()
        state = _load_state(PROJECT)
        self.assertIsNotNone(state["potential_value"])
        self.assertEqual(state["potential_value"]["investment_level"], "medium")

    def test_value_multiple_benefits(self):
        benefits = json.dumps([
            {"benefit_title": "Ускорение", "benefit_type": "operational", "magnitude": "high", "confidence": "medium"},
            {"benefit_title": "Снижение затрат", "benefit_type": "financial", "magnitude": "medium", "confidence": "high"},
        ])
        r = assess_potential_value(project_id=PROJECT, benefits_json=benefits, investment_level="medium")
        self.assertIn("✅", r)

    def test_value_invalid_benefit_type(self):
        benefits = json.dumps([
            {"benefit_title": "Ускорение", "benefit_type": "unknown_type", "magnitude": "high", "confidence": "medium"}
        ])
        r = assess_potential_value(project_id=PROJECT, benefits_json=benefits, investment_level="medium")
        self.assertIn("❌", r)

    def test_value_invalid_magnitude(self):
        benefits = json.dumps([
            {"benefit_title": "Ускорение", "benefit_type": "operational", "magnitude": "extreme", "confidence": "medium"}
        ])
        r = assess_potential_value(project_id=PROJECT, benefits_json=benefits, investment_level="medium")
        self.assertIn("❌", r)

    def test_value_invalid_confidence(self):
        benefits = json.dumps([
            {"benefit_title": "Ускорение", "benefit_type": "operational", "magnitude": "high", "confidence": "very_high"}
        ])
        r = assess_potential_value(project_id=PROJECT, benefits_json=benefits, investment_level="medium")
        self.assertIn("❌", r)

    def test_value_empty_benefits_error(self):
        r = assess_potential_value(project_id=PROJECT, benefits_json="[]", investment_level="medium")
        self.assertIn("❌", r)

    def test_value_investment_levels(self):
        for level in ["low", "medium", "high", "unknown"]:
            r = assess_potential_value(
                project_id=PROJECT,
                benefits_json='[{"benefit_title":"B","benefit_type":"operational","magnitude":"high","confidence":"medium"}]',
                investment_level=level,
            )
            self.assertIn("✅", r)

    def test_value_profile_attractive(self):
        r = assess_potential_value(
            project_id=PROJECT,
            benefits_json='[{"benefit_title":"B","benefit_type":"operational","magnitude":"high","confidence":"high"}]',
            investment_level="low",
        )
        self.assertIn("Привлекательный", r)

    def test_value_summary_stored(self):
        _value(summary="Очень привлекательный профиль")
        state = _load_state(PROJECT)
        self.assertEqual(state["potential_value"]["value_summary"], "Очень привлекательный профиль")


# ---------------------------------------------------------------------------
# check_future_state_completeness
# ---------------------------------------------------------------------------

class TestCheckFutureStateCompleteness(BaseMCPTest):

    def test_check_no_scope_error(self):
        r = check_future_state_completeness(project_id=PROJECT)
        self.assertIn("⚠️", r)
        self.assertIn("scope", r.lower())

    def test_check_incomplete_no_elements(self):
        _scope()
        r = check_future_state_completeness(project_id=PROJECT)
        self.assertIn("⚠️", r)
        self.assertNotIn("✅ Все проверки пройдены", r)

    def test_check_no_goals_warning(self):
        _scope()
        _capture()
        r = check_future_state_completeness(project_id=PROJECT)
        self.assertIn("цел", r.lower())

    def test_check_no_gap_warning(self):
        _scope()
        _capture()
        _goal()
        _constraint()
        _value()
        r = check_future_state_completeness(project_id=PROJECT)
        self.assertIn("Gap", r)

    def test_check_no_constraints_warning(self):
        _scope()
        _capture()
        _goal()
        r = check_future_state_completeness(project_id=PROJECT)
        self.assertIn("ограничен", r.lower())

    def test_check_readiness_percentage(self):
        _scope()
        _capture()
        r = check_future_state_completeness(project_id=PROJECT)
        self.assertIn("%", r)

    def test_check_bn_coverage_with_61_data(self):
        _save_current_state_data()
        _scope()
        _capture()
        _goal(linked_bn='["BN-001"]')  # BN-002 не привязан
        _constraint()
        run_gap_analysis(project_id=PROJECT)
        _value()
        r = check_future_state_completeness(project_id=PROJECT)
        self.assertIn("BN-002", r)

    def test_check_goals_without_kpi(self):
        _scope()
        _capture()
        define_goals_and_objectives(
            project_id=PROJECT,
            goal_title="Улучшить что-то",
            description="Описание",
            objectives_json="[]",
        )
        r = check_future_state_completeness(project_id=PROJECT)
        self.assertIn("KPI", r)

    def test_check_all_passed(self):
        # Скоуп с 2 элементами, оба заполнены
        scope_future_state(
            project_id=PROJECT,
            initiative_type="process_improvement",
            analysis_depth="light",
            elements_in_scope='["capabilities","technology"]',
        )
        _capture(element="capabilities")
        _capture(element="technology", description="Облачная платформа")
        _goal()
        _constraint()
        run_gap_analysis(project_id=PROJECT)
        _value()
        r = check_future_state_completeness(project_id=PROJECT)
        self.assertIn("100%", r)

    def test_check_no_value_warning(self):
        _scope()
        _capture()
        _goal()
        _constraint()
        run_gap_analysis(project_id=PROJECT)
        # Без value assessment
        r = check_future_state_completeness(project_id=PROJECT)
        self.assertIn("ценность", r.lower())


# ---------------------------------------------------------------------------
# save_future_state
# ---------------------------------------------------------------------------

class TestSaveFutureState(BaseMCPTest):

    def test_save_no_scope_error(self):
        r = save_future_state(project_id=PROJECT, project_title="Тест")
        self.assertIn("⚠️", r)

    def test_save_basic_success(self):
        _full_pipeline()
        r = save_future_state(project_id=PROJECT, project_title="Проект Ускорения")
        self.assertIn("✅", r)
        self.assertIn("Проект Ускорения", r)

    def test_save_creates_report_artifact(self):
        from unittest.mock import patch
        _full_pipeline()
        with patch("skills.future_state_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            save_future_state(project_id=PROJECT, project_title="Проект")
            mock_sa.assert_called()

    def test_save_statistics_in_response(self):
        _full_pipeline()
        r = save_future_state(project_id=PROJECT, project_title="Проект")
        self.assertIn("Статистика", r)
        self.assertIn("Gap-анализ", r)

    def test_save_push_to_business_context(self):
        _full_pipeline()
        r = save_future_state(project_id=PROJECT, project_title="Проект",
                              push_to_business_context=True)
        self.assertIn("7.3", r)
        self.assertIn("from_strategy_project_id", r)

    def test_save_draft_warning(self):
        _scope()
        state = _load_state(PROJECT)
        state["elements"]["capabilities"] = {"description": "Черновик", "draft": True, "last_updated": str(date.today())}
        from skills.future_state_mcp import _save_state
        _save_state(state)
        r = save_future_state(project_id=PROJECT, project_title="Проект")
        self.assertIn("Черновик", r)

    def test_save_analyst_notes_in_report(self):
        from unittest.mock import patch
        _full_pipeline()
        with patch("skills.future_state_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            save_future_state(
                project_id=PROJECT, project_title="Проект",
                analyst_notes="Важное замечание аналитика"
            )
            call_args = mock_sa.call_args
            report = call_args[0][0]
            self.assertIn("Важное замечание аналитика", report)

    def test_save_next_steps_in_response(self):
        _full_pipeline()
        r = save_future_state(project_id=PROJECT, project_title="Проект")
        self.assertIn("6.4", r)
        self.assertIn("7.3", r)


# ---------------------------------------------------------------------------
# Pipeline-тесты
# ---------------------------------------------------------------------------

class TestPipeline(BaseMCPTest):

    def test_full_pipeline_with_61(self):
        _full_pipeline(with_current_state=True)
        r = save_future_state(project_id=PROJECT, project_title="Полный Pipeline")
        self.assertIn("✅", r)

    def test_pipeline_without_61(self):
        _full_pipeline(with_current_state=False)
        r = save_future_state(project_id=PROJECT, project_title="Pipeline без 6.1")
        self.assertIn("✅", r)

    def test_pipeline_gap_without_current_state_new_type(self):
        _scope()
        _capture()
        run_gap_analysis(project_id=PROJECT)
        gap = _load_gap(PROJECT)
        for g in gap["gaps"]:
            self.assertEqual(g["change_type"], "new")

    def test_pipeline_goals_registered_in_51(self):
        repo = make_test_repo(PROJECT)
        repo["project"] = PROJECT
        repo["requirements"] = []
        repo["links"] = []
        save_test_repo(repo, "governance_plans/data")

        _scope()
        _goal(title="Цель 1", register=True)
        _goal(title="Цель 2", register=True)

        with open(f"governance_plans/data/{_safe(PROJECT)}_traceability_repo.json") as f:
            updated_repo = json.load(f)

        ids = [r["id"] for r in updated_repo["requirements"]]
        self.assertIn("BG-001", ids)
        self.assertIn("BG-002", ids)

    def test_pipeline_completeness_all_green_after_full(self):
        # Явно ограничиваем скоуп только теми элементами что заполняем
        scope_future_state(
            project_id=PROJECT,
            initiative_type="process_improvement",
            analysis_depth="light",
            elements_in_scope='["capabilities","technology"]',
        )
        _save_current_state_data(PROJECT)
        repo = make_test_repo(PROJECT)
        repo["project"] = PROJECT
        repo["requirements"] = []
        repo["links"] = []
        save_test_repo(repo, "governance_plans/data")
        _capture(element="capabilities")
        _capture(element="technology", description="Облачная платформа")
        _goal(linked_bn='["BN-001","BN-002"]')
        _constraint()
        run_gap_analysis(project_id=PROJECT)
        _value()
        r = check_future_state_completeness(project_id=PROJECT)
        self.assertIn("100%", r)

    def test_pipeline_multiple_constraints_stored(self):
        _scope()
        _constraint(title="Бюджет", category="budget")
        _constraint(title="Срок", category="time", description="Q4 2025")
        _constraint(title="152-ФЗ", category="compliance", description="Соответствие")
        state = _load_state(PROJECT)
        self.assertEqual(len(state["constraints"]), 3)

    def test_pipeline_scope_and_goals_only_no_error(self):
        """Минимальный pipeline: только скоуп и одна цель — не должно быть исключений."""
        try:
            _scope()
            _goal()
            r = check_future_state_completeness(project_id=PROJECT)
            # Должно работать без исключений — вернуть предупреждения, не краш
            self.assertIn("⚠️", r)
            self.assertIn("Предупреждения", r)
        except Exception as e:
            self.fail(f"pipeline без ошибок не должен вызывать исключений: {e}")


# ---------------------------------------------------------------------------
# Интеграция 7.3 from_strategy_project_id (ADR-065)
# ---------------------------------------------------------------------------

class TestIntegration73(BaseMCPTest):

    def test_from_strategy_with_62_goals(self):
        _save_future_state_goals()
        _scope()
        state_data = {
            "project_id": PROJECT,
            "elements": {"capabilities": {"description": "Авто-процесс", "draft": False}},
            "constraints": [],
            "potential_value": None,
            "gap_analysis_done": False,
            "created": str(date.today()),
            "updated": str(date.today()),
        }
        with open(f"governance_plans/data/{_safe(PROJECT)}_future_state.json", "w") as f:
            json.dump(state_data, f)

        r = set_business_context(
            project_id=PROJECT,
            business_goals_json="[]",
            future_state="",
            solution_scope="",
            from_strategy_project_id=PROJECT,
        )
        self.assertIn("BG-001", r)

    def test_from_strategy_fills_business_goals(self):
        _save_future_state_goals()
        r = set_business_context(
            project_id=PROJECT,
            business_goals_json="[]",
            future_state="Будущее",
            solution_scope="Скоуп",
            from_strategy_project_id=PROJECT,
        )
        self.assertIn("6.2", r)

    def test_from_strategy_fills_future_state(self):
        _scope()
        state_data = {
            "project_id": PROJECT,
            "elements": {"capabilities": {"description": "Авто-процесс за 2 часа", "draft": False}},
            "constraints": [],
            "potential_value": None,
            "gap_analysis_done": False,
            "created": str(date.today()),
            "updated": str(date.today()),
        }
        with open(f"governance_plans/data/{_safe(PROJECT)}_future_state.json", "w") as f:
            json.dump(state_data, f)
        scope_data = {
            "project_id": PROJECT,
            "initiative_type": "process_improvement",
            "elements_in_scope": ["capabilities"],
            "analysis_depth": "standard",
            "created": str(date.today()),
            "updated": str(date.today()),
        }
        with open(f"governance_plans/data/{_safe(PROJECT)}_future_state_scope.json", "w") as f:
            json.dump(scope_data, f)

        r = set_business_context(
            project_id=PROJECT,
            business_goals_json='[{"id":"BG-001","title":"Цель"}]',
            future_state="",
            solution_scope="",
            from_strategy_project_id=PROJECT,
        )
        self.assertIn("6.2", r)

    def test_from_strategy_fallback_to_61_bn(self):
        """Если 6.2 нет но есть 6.1 — предзаполняет из BN."""
        _save_current_state_data()
        r = set_business_context(
            project_id=PROJECT,
            business_goals_json="[]",
            future_state="Будущее",
            solution_scope="Скоуп",
            from_strategy_project_id=PROJECT,
        )
        self.assertIn("BG-001", r)

    def test_from_strategy_no_data_warning(self):
        r = set_business_context(
            project_id=PROJECT,
            business_goals_json='[{"id":"BG-001","title":"Цель"}]',
            future_state="Будущее",
            solution_scope="Скоуп",
            from_strategy_project_id="nonexistent_project",
        )
        self.assertIn("⚠️", r)

    def test_deprecated_from_current_state_warning(self):
        _save_current_state_data()
        r = set_business_context(
            project_id=PROJECT,
            business_goals_json="[]",
            future_state="Будущее",
            solution_scope="Скоуп",
            from_current_state_project_id=PROJECT,
        )
        self.assertIn("устарел", r.lower())

    def test_deprecated_still_works(self):
        """Deprecated параметр работает, но показывает предупреждение."""
        _save_current_state_data()
        r = set_business_context(
            project_id=PROJECT,
            business_goals_json="[]",
            future_state="Будущее",
            solution_scope="Скоуп",
            from_current_state_project_id=PROJECT,
        )
        # Должно предзаполнить и предупредить
        self.assertIn("BG-001", r)
        self.assertIn("устарел", r.lower())

    def test_from_strategy_does_not_override_explicit_goals(self):
        """from_strategy_project_id не перебивает явно переданные goals."""
        _save_future_state_goals()
        r = set_business_context(
            project_id=PROJECT,
            business_goals_json='[{"id":"BG-999","title":"Явная цель"}]',
            future_state="Будущее",
            solution_scope="Скоуп",
            from_strategy_project_id=PROJECT,
        )
        self.assertIn("BG-999", r)


if __name__ == "__main__":
    unittest.main(verbosity=2)
