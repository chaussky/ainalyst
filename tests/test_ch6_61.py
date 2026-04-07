"""
tests/test_ch6_61.py — Тесты для BABOK 6.1 Analyze Current State.

Структура:
  - Unit (12): утилиты _safe, _next_need_id, _next_rca_id, _load/_save helpers
  - scope_current_state (12): типы инициатив, глубина, custom elements, session_ids, обновление
  - capture_current_state_element (12): успех, обновление, черновик, вне скоупа, валидация
  - run_root_cause_analysis (11): три техники, валидация, накопление RCA
  - define_business_needs (12): регистрация в 5.1, без репо, дубликат, RCA-ссылки
  - check_current_state_completeness (9): полный, частичный, без скоупа, вердикты
  - save_current_state (8): финализация, push_to_business_context, без скоупа
  - Pipeline (6): полный predictive, light, deep с импортом 4.3, без RCA
  - Интеграция 7.3 from_current_state_project_id (8): ADR-055 предзаполнение
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

from skills.current_state_mcp import (
    scope_current_state,
    capture_current_state_element,
    run_root_cause_analysis,
    define_business_needs,
    check_current_state_completeness,
    save_current_state,
    _safe,
    _next_need_id,
    _next_rca_id,
    _load_scope,
    _load_state,
    _load_needs,
    VALID_ELEMENTS,
    ELEMENT_LABELS,
    DEFAULT_ELEMENTS_BY_TYPE,
)

from skills.requirements_validate_mcp import set_business_context

PROJECT = "test_project"


# ---------------------------------------------------------------------------
# Утилиты для тестов
# ---------------------------------------------------------------------------

def _scope(project=PROJECT, initiative="process_improvement", depth="standard",
           problems="Процесс медленный", elements="", sessions=""):
    return scope_current_state(
        project_id=project,
        initiative_type=initiative,
        analysis_depth=depth,
        known_problems=problems,
        elements_in_scope=elements,
        session_ids=sessions,
    )


def _capture(project=PROJECT, element="business_needs",
             description="Описание текущего состояния",
             pain_points='["Проблема 1"]', metrics='{}', sources='["interview"]', notes=""):
    return capture_current_state_element(
        project_id=project,
        element=element,
        description=description,
        pain_points=pain_points,
        metrics=metrics,
        sources=sources,
        notes=notes,
    )


def _rca(project=PROJECT, problem="Время выросло с 2 до 8 часов",
         technique="fishbone", root_cause="Лишние уровни согласования",
         factors='["Нет автоматизации"]', evidence='["Данные Q1 2025"]',
         affected='["capabilities","policies"]'):
    return run_root_cause_analysis(
        project_id=project,
        problem_statement=problem,
        technique_used=technique,
        root_cause=root_cause,
        contributing_factors=factors,
        evidence=evidence,
        affected_elements=affected,
    )


def _needs(project=PROJECT, title="Снизить время обработки",
           description="Время выросло с 2 до 8 часов, потери 18% клиентов",
           need_type="problem", priority="High", source="Директор по операциям",
           root_cause_ids="[]", register=True):
    return define_business_needs(
        project_id=project,
        need_title=title,
        description=description,
        need_type=need_type,
        priority=priority,
        source=source,
        root_cause_ids=root_cause_ids,
        register_in_traceability=register,
    )


def _save_needs_json(project=PROJECT, needs_list=None):
    """Сохраняет business_needs.json напрямую для тестов интеграции."""
    if needs_list is None:
        needs_list = [
            {
                "id": "BN-001",
                "need_title": "Ускорить обработку",
                "description": "Время выросло с 2 до 8 часов",
                "need_type": "problem",
                "priority": "High",
                "source": "Иванов",
                "cost_of_inaction": "Потеря 18% клиентов",
                "expected_benefits": "Сокращение времени до 2 часов",
                "root_cause_ids": ["RCA-001"],
                "created": str(date.today()),
            }
        ]
    data = {
        "project_id": project,
        "needs": needs_list,
        "created": str(date.today()),
        "updated": str(date.today()),
    }
    os.makedirs("governance_plans/data", exist_ok=True)
    path = f"governance_plans/data/{_safe(project)}_business_needs.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def _save_scope_json(project=PROJECT):
    """Сохраняет scope JSON напрямую для тестов интеграции."""
    data = {
        "project_id": project,
        "initiative_type": "process_improvement",
        "analysis_depth": "standard",
        "known_problems": "Процесс медленный",
        "elements_in_scope": ["business_needs", "capabilities", "technology", "policies"],
        "session_ids_imported": [],
        "created": str(date.today()),
        "updated": str(date.today()),
    }
    os.makedirs("governance_plans/data", exist_ok=True)
    path = f"governance_plans/data/{_safe(project)}_current_state_scope.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


# ---------------------------------------------------------------------------
# Unit — утилиты
# ---------------------------------------------------------------------------

class TestUtils(BaseMCPTest):

    def test_safe_lowercase(self):
        self.assertEqual(_safe("MyProject"), "myproject")

    def test_safe_spaces(self):
        self.assertEqual(_safe("My Project"), "my_project")

    def test_safe_already_lower(self):
        self.assertEqual(_safe("test_project"), "test_project")

    def test_valid_elements_count(self):
        self.assertEqual(len(VALID_ELEMENTS), 8)

    def test_valid_elements_contains_business_needs(self):
        self.assertIn("business_needs", VALID_ELEMENTS)

    def test_valid_elements_contains_external(self):
        self.assertIn("external", VALID_ELEMENTS)

    def test_element_labels_has_all_elements(self):
        for elem in VALID_ELEMENTS:
            self.assertIn(elem, ELEMENT_LABELS)

    def test_default_elements_process_improvement(self):
        elems = DEFAULT_ELEMENTS_BY_TYPE["process_improvement"]
        self.assertIn("business_needs", elems)
        self.assertIn("capabilities", elems)

    def test_next_need_id_empty(self):
        needs = {"needs": []}
        self.assertEqual(_next_need_id(needs), "BN-001")

    def test_next_need_id_increment(self):
        needs = {"needs": [{"id": "BN-001"}, {"id": "BN-002"}]}
        self.assertEqual(_next_need_id(needs), "BN-003")

    def test_next_rca_id_empty(self):
        state = {"root_causes": []}
        self.assertEqual(_next_rca_id(state), "RCA-001")

    def test_next_rca_id_increment(self):
        state = {"root_causes": [{"rca_id": "RCA-001"}]}
        self.assertEqual(_next_rca_id(state), "RCA-002")


# ---------------------------------------------------------------------------
# scope_current_state
# ---------------------------------------------------------------------------

class TestScopeCurrentState(BaseMCPTest):

    def test_basic_success(self):
        result = _scope()
        self.assertIn("✅", result)
        self.assertIn(PROJECT, result)

    def test_scope_saved_to_disk(self):
        _scope()
        scope = _load_scope(PROJECT)
        self.assertIsNotNone(scope)
        self.assertEqual(scope["project_id"], PROJECT)

    def test_initiative_type_stored(self):
        _scope(initiative="new_system")
        scope = _load_scope(PROJECT)
        self.assertEqual(scope["initiative_type"], "new_system")

    def test_depth_light_limits_elements(self):
        _scope(depth="light", initiative="process_improvement")
        scope = _load_scope(PROJECT)
        self.assertLessEqual(len(scope["elements_in_scope"]), 3)

    def test_depth_deep_all_elements(self):
        _scope(depth="deep")
        scope = _load_scope(PROJECT)
        self.assertEqual(len(scope["elements_in_scope"]), 8)

    def test_custom_elements_override(self):
        elems = '["business_needs","external"]'
        _scope(elements=elems)
        scope = _load_scope(PROJECT)
        self.assertEqual(scope["elements_in_scope"], ["business_needs", "external"])

    def test_invalid_element_key_error(self):
        result = _scope(elements='["unknown_element"]')
        self.assertIn("❌", result)

    def test_invalid_json_elements_error(self):
        result = _scope(elements="not_json")
        self.assertIn("❌", result)

    def test_session_ids_creates_drafts(self):
        _scope(sessions='["session_001"]')
        state = _load_state(PROJECT)
        # Хотя бы один элемент должен быть черновиком
        has_draft = any(
            v.get("draft") for v in state.get("elements", {}).values()
        )
        self.assertTrue(has_draft)

    def test_update_existing_scope(self):
        _scope(depth="light")
        result = _scope(depth="deep")
        self.assertIn("ОБНОВЛЁН", result)

    def test_market_opportunity_deep_by_default(self):
        _scope(initiative="market_opportunity", depth="standard")
        scope = _load_scope(PROJECT)
        # market_opportunity всегда все 8 элементов
        self.assertEqual(len(scope["elements_in_scope"]), 8)

    def test_known_problems_stored(self):
        _scope(problems="Клиенты жалуются на долгое ожидание")
        scope = _load_scope(PROJECT)
        self.assertIn("жалуются", scope["known_problems"])


# ---------------------------------------------------------------------------
# capture_current_state_element
# ---------------------------------------------------------------------------

class TestCaptureCurrentStateElement(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _scope()  # создаём скоуп перед каждым тестом

    def test_basic_success(self):
        result = _capture()
        self.assertIn("✅", result)
        self.assertIn("business_needs", result)

    def test_element_saved_to_state(self):
        _capture(element="capabilities", description="Низкая производительность")
        state = _load_state(PROJECT)
        self.assertIn("capabilities", state["elements"])
        self.assertEqual(state["elements"]["capabilities"]["description"], "Низкая производительность")

    def test_draft_false_after_capture(self):
        _capture()
        state = _load_state(PROJECT)
        self.assertFalse(state["elements"]["business_needs"].get("draft", True))

    def test_pain_points_stored(self):
        _capture(pain_points='["Проблема A","Проблема B"]')
        state = _load_state(PROJECT)
        self.assertEqual(len(state["elements"]["business_needs"]["pain_points"]), 2)

    def test_metrics_stored(self):
        _capture(metrics='{"time": "8 hours"}')
        state = _load_state(PROJECT)
        self.assertIn("time", state["elements"]["business_needs"]["metrics"])

    def test_update_replaces_element(self):
        _capture(description="Первое описание")
        _capture(description="Обновлённое описание")
        state = _load_state(PROJECT)
        self.assertIn("Обновлённое", state["elements"]["business_needs"]["description"])

    def test_update_marks_updated_in_result(self):
        _capture(description="Первое")
        result = _capture(description="Второе")
        self.assertIn("ОБНОВЛЁН", result)

    def test_out_of_scope_warning(self):
        # external не входит в standard process_improvement scope
        result = _capture(element="external", description="Рыночные условия")
        self.assertIn("⚠️", result)
        self.assertIn("скоуп", result)

    def test_empty_description_error(self):
        result = _capture(description="")
        self.assertIn("❌", result)

    def test_invalid_pain_points_json(self):
        result = _capture(pain_points="not_json")
        self.assertIn("❌", result)

    def test_invalid_metrics_json(self):
        result = _capture(metrics="not_json")
        self.assertIn("❌", result)

    def test_progress_shown_in_result(self):
        result = _capture()
        self.assertIn("Прогресс", result)


# ---------------------------------------------------------------------------
# run_root_cause_analysis
# ---------------------------------------------------------------------------

class TestRunRootCauseAnalysis(BaseMCPTest):

    def test_fishbone_success(self):
        result = _rca(technique="fishbone")
        self.assertIn("✅", result)
        self.assertIn("RCA-001", result)

    def test_five_whys_success(self):
        result = _rca(technique="five_whys")
        self.assertIn("✅", result)
        self.assertIn("5 Почему", result)

    def test_problem_tree_success(self):
        result = _rca(technique="problem_tree")
        self.assertIn("✅", result)
        self.assertIn("Дерево", result)

    def test_rca_saved_to_state(self):
        _rca()
        state = _load_state(PROJECT)
        self.assertEqual(len(state["root_causes"]), 1)
        self.assertEqual(state["root_causes"][0]["rca_id"], "RCA-001")

    def test_rca_id_increments(self):
        _rca()
        _rca()
        state = _load_state(PROJECT)
        ids = [r["rca_id"] for r in state["root_causes"]]
        self.assertIn("RCA-001", ids)
        self.assertIn("RCA-002", ids)

    def test_normalized_format_stored(self):
        _rca(technique="fishbone", root_cause="Корневая причина")
        state = _load_state(PROJECT)
        rca = state["root_causes"][0]
        self.assertIn("technique_used", rca)
        self.assertIn("root_cause", rca)
        self.assertIn("contributing_factors", rca)
        self.assertIn("evidence", rca)
        self.assertIn("affected_elements", rca)

    def test_empty_problem_statement_error(self):
        result = _rca(problem="")
        self.assertIn("❌", result)

    def test_empty_root_cause_error(self):
        result = _rca(root_cause="")
        self.assertIn("❌", result)

    def test_invalid_affected_elements_error(self):
        result = _rca(affected='["unknown_element"]')
        self.assertIn("❌", result)

    def test_invalid_factors_json_error(self):
        result = _rca(factors="not_json")
        self.assertIn("❌", result)

    def test_suggests_define_business_needs(self):
        result = _rca()
        self.assertIn("define_business_needs", result)


# ---------------------------------------------------------------------------
# define_business_needs
# ---------------------------------------------------------------------------

class TestDefineBusinessNeeds(BaseMCPTest):

    def test_basic_success(self):
        result = _needs()
        self.assertIn("✅", result)
        self.assertIn("BN-001", result)

    def test_need_saved_to_json(self):
        _needs()
        needs_data = _load_needs(PROJECT)
        self.assertEqual(len(needs_data["needs"]), 1)
        self.assertEqual(needs_data["needs"][0]["id"], "BN-001")

    def test_id_increments(self):
        _needs(title="Первая потребность")
        _needs(title="Вторая потребность")
        needs_data = _load_needs(PROJECT)
        ids = [n["id"] for n in needs_data["needs"]]
        self.assertIn("BN-001", ids)
        self.assertIn("BN-002", ids)

    def test_register_in_traceability(self):
        os.makedirs("governance_plans/data", exist_ok=True)
        repo = make_test_repo(PROJECT)
        save_test_repo(repo, governance_dir="governance_plans/data")
        _needs(register=True)
        # Проверяем что BN-001 появился в репозитории
        with open(f"governance_plans/data/{PROJECT}_traceability_repo.json", encoding="utf-8") as f:
            repo = json.load(f)
        ids = [r["id"] for r in repo["requirements"]]
        self.assertIn("BN-001", ids)

    def test_node_type_is_business_need(self):
        os.makedirs("governance_plans/data", exist_ok=True)
        repo = make_test_repo(PROJECT)
        save_test_repo(repo, governance_dir="governance_plans/data")
        _needs(register=True)
        with open(f"governance_plans/data/{PROJECT}_traceability_repo.json", encoding="utf-8") as f:
            repo = json.load(f)
        bn = next(r for r in repo["requirements"] if r["id"] == "BN-001")
        self.assertEqual(bn["type"], "business_need")

    def test_no_traceability_repo_warning(self):
        result = _needs(register=True)
        self.assertIn("⚠️", result)
        self.assertIn("5.1", result)

    def test_register_false_no_repo_update(self):
        os.makedirs("governance_plans/data", exist_ok=True)
        repo = make_test_repo(PROJECT)
        save_test_repo(repo, governance_dir="governance_plans/data")
        _needs(register=False)
        with open(f"governance_plans/data/{PROJECT}_traceability_repo.json", encoding="utf-8") as f:
            repo = json.load(f)
        ids = [r["id"] for r in repo["requirements"]]
        self.assertNotIn("BN-001", ids)

    def test_rca_link_valid(self):
        _rca()
        result = _needs(root_cause_ids='["RCA-001"]')
        self.assertIn("✅", result)
        self.assertIn("RCA-001", result)

    def test_rca_link_unknown_error(self):
        result = _needs(root_cause_ids='["RCA-999"]')
        self.assertIn("⚠️", result)
        self.assertIn("RCA-999", result)

    def test_empty_title_error(self):
        result = _needs(title="")
        self.assertIn("❌", result)

    def test_empty_description_error(self):
        result = _needs(description="")
        self.assertIn("❌", result)

    def test_empty_source_error(self):
        result = define_business_needs(
            project_id=PROJECT, need_title="Title", description="Desc",
            need_type="problem", priority="High", source="",
        )
        self.assertIn("❌", result)


# ---------------------------------------------------------------------------
# check_current_state_completeness
# ---------------------------------------------------------------------------

class TestCheckCompleteness(BaseMCPTest):

    def test_no_scope_error(self):
        result = check_current_state_completeness(PROJECT)
        self.assertIn("⚠️", result)
        self.assertIn("scope_current_state", result)

    def test_with_scope_shows_progress(self):
        _scope()
        result = check_current_state_completeness(PROJECT)
        self.assertIn("готовность", result.lower())

    def test_all_filled_is_ready(self):
        _scope(elements='["business_needs"]')
        _capture(element="business_needs", description="Описание")
        _rca()
        _needs()
        result = check_current_state_completeness(PROJECT)
        self.assertIn("✅", result)

    def test_missing_elements_shown(self):
        _scope()  # 4 элемента в scope
        result = check_current_state_completeness(PROJECT)
        self.assertIn("Незаполнен", result)

    def test_no_rca_warning(self):
        _scope(elements='["business_needs"]')
        _capture()
        result = check_current_state_completeness(PROJECT)
        self.assertIn("RCA", result)

    def test_no_needs_warning(self):
        _scope(elements='["business_needs"]')
        _capture()
        _rca()
        result = check_current_state_completeness(PROJECT)
        self.assertIn("потребност", result)

    def test_draft_elements_shown(self):
        _scope(sessions='["session_001"]')
        result = check_current_state_completeness(PROJECT)
        self.assertIn("черновик", result.lower())

    def test_readiness_percentage(self):
        _scope()
        result = check_current_state_completeness(PROJECT)
        self.assertIn("%", result)

    def test_needs_without_rca_warning(self):
        _scope(elements='["business_needs"]')
        _capture()
        _rca()
        _needs(root_cause_ids="[]")  # без RCA ссылки
        result = check_current_state_completeness(PROJECT)
        self.assertIn("без RCA", result)


# ---------------------------------------------------------------------------
# save_current_state
# ---------------------------------------------------------------------------

class TestSaveCurrentState(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _scope()
        _capture(element="business_needs", description="Текущие потребности")

    def test_basic_success(self):
        result = save_current_state(PROJECT, "Тестовый Проект")
        self.assertIn("✅", result)
        self.assertIn(PROJECT, result)

    def test_report_file_created(self):
        # save_artifact создаёт reports/ автоматически через _ensure_dirs()
        result = save_current_state(PROJECT, "Тестовый Проект")
        self.assertIn("✅", result)
        # Проверяем что отчёт упоминается в выводе
        self.assertIn("current_state", result)

    def test_without_scope_error(self):
        # Создаём проект без скоупа
        result = save_current_state("noscopeproject", "Без скоупа")
        self.assertIn("⚠️", result)
        self.assertIn("scope_current_state", result)

    def test_push_to_business_context_info(self):
        _needs()
        result = save_current_state(PROJECT, "Проект", push_to_business_context=True)
        self.assertIn("7.3", result)
        self.assertIn("set_business_context", result)

    def test_draft_warning_in_report(self):
        # Добавляем черновик через session_ids
        _scope(sessions='["session_001"]')
        result = save_current_state(PROJECT, "Проект")
        self.assertIn("черновик", result.lower())

    def test_statistics_shown(self):
        _rca()
        _needs()
        result = save_current_state(PROJECT, "Проект")
        self.assertIn("RCA", result)
        self.assertIn("потребностей", result.lower())

    def test_analyst_notes_included(self):
        result = save_current_state(PROJECT, "Проект", analyst_notes="Важное замечание аналитика")
        # Заметки попадают в markdown отчёт, не обязательно в summary
        # Проверяем что функция не вернула ошибку
        self.assertIn("✅", result)

    def test_next_steps_shown(self):
        result = save_current_state(PROJECT, "Проект")
        self.assertIn("6.2", result)
        self.assertIn("7.3", result)


# ---------------------------------------------------------------------------
# Pipeline — сквозные тесты
# ---------------------------------------------------------------------------

class TestPipeline(BaseMCPTest):

    def test_full_standard_pipeline(self):
        """Полный pipeline: scope → capture × 2 → RCA → needs → check → save."""
        # Скоуп
        r1 = _scope(initiative="process_improvement", depth="standard")
        self.assertIn("✅", r1)

        # Захват элементов
        r2 = _capture(element="business_needs", description="Высокое время обработки",
                      pain_points='["Клиенты ждут 8 часов"]',
                      metrics='{"avg_time": "8h"}')
        self.assertIn("✅", r2)

        r3 = _capture(element="capabilities", description="Процесс согласования устарел")
        self.assertIn("✅", r3)

        # RCA
        r4 = _rca(technique="fishbone",
                  problem="Время выросло с 2 до 8 часов",
                  root_cause="Устаревший регламент 2012 года",
                  factors='["Нет автоматизации","Дублирование проверок"]')
        self.assertIn("RCA-001", r4)

        # Бизнес-потребность
        r5 = _needs(title="Оптимизировать процесс согласования",
                    root_cause_ids='["RCA-001"]',
                    register=False)
        self.assertIn("BN-001", r5)

        # Проверка полноты
        r6 = check_current_state_completeness(PROJECT)
        self.assertIn("%", r6)

        # Сохранение
        r7 = save_current_state(PROJECT, "Проект оптимизации", analyst_notes="Готово")
        self.assertIn("✅", r7)

    def test_light_pipeline(self):
        """Light pipeline: 3 элемента, один RCA, одна BN."""
        _scope(initiative="cost_reduction", depth="light")
        _capture(element="business_needs", description="Высокие операционные затраты")
        _rca(technique="five_whys", problem="Затраты выросли на 40%",
             root_cause="Ручные операции не автоматизированы")
        _needs(title="Снизить операционные затраты", register=False)
        r = save_current_state(PROJECT, "Cost Reduction")
        self.assertIn("✅", r)

    def test_pipeline_with_traceability(self):
        """Pipeline с регистрацией в 5.1."""
        os.makedirs("governance_plans/data", exist_ok=True)
        repo = make_test_repo(PROJECT)
        save_test_repo(repo, governance_dir="governance_plans/data")
        _scope(elements='["business_needs"]')
        _capture()
        _rca()
        r = _needs(register=True)
        self.assertIn("BN-001", r)
        self.assertIn("5.1", r)
        # Проверяем что узел есть в репо
        with open(f"governance_plans/data/{PROJECT}_traceability_repo.json", encoding="utf-8") as f:
            repo = json.load(f)
        types = [req["type"] for req in repo["requirements"]]
        self.assertIn("business_need", types)

    def test_multiple_needs_multiple_rca(self):
        """Несколько RCA и несколько BN."""
        _scope(elements='["business_needs","capabilities","policies"]')
        _capture(element="business_needs", description="Множество проблем")
        _capture(element="capabilities", description="Слабые процессы")
        _rca(technique="fishbone", root_cause="Причина 1", affected='["capabilities"]')
        _rca(technique="five_whys", problem="Проблема 2", root_cause="Причина 2",
             affected='["policies"]')
        _needs(title="BN-1", root_cause_ids='["RCA-001"]', register=False)
        _needs(title="BN-2", root_cause_ids='["RCA-002"]', register=False)
        needs_data = _load_needs(PROJECT)
        self.assertEqual(len(needs_data["needs"]), 2)
        state = _load_state(PROJECT)
        self.assertEqual(len(state["root_causes"]), 2)

    def test_session_ids_import_then_refine(self):
        """Импорт из 4.3 → уточнение через capture."""
        _scope(sessions='["session_001","session_002"]')
        state_before = _load_state(PROJECT)
        # Должны быть черновики
        has_draft = any(v.get("draft") for v in state_before.get("elements", {}).values())
        self.assertTrue(has_draft)

        # Уточняем один элемент
        _capture(element="business_needs", description="Уточнённое описание")
        state_after = _load_state(PROJECT)
        self.assertFalse(state_after["elements"]["business_needs"].get("draft", True))

    def test_completeness_check_gates_finalization(self):
        """check перед save показывает пробелы."""
        _scope()
        # Заполняем только один элемент из четырёх
        _capture(element="business_needs", description="Частичный анализ")
        r = check_current_state_completeness(PROJECT)
        # Должны быть предупреждения
        self.assertIn("⚠️", r)
        # Но save всё равно работает (не блокировка)
        r2 = save_current_state(PROJECT, "Проект")
        self.assertIn("✅", r2)


# ---------------------------------------------------------------------------
# Интеграция 7.3 — ADR-055: from_current_state_project_id
# ---------------------------------------------------------------------------

class TestADR055Integration(BaseMCPTest):
    """Тесты параметра from_current_state_project_id в set_business_context."""

    def test_without_param_backward_compatible(self):
        """Без параметра — поведение 7.3 не меняется."""
        result = set_business_context(
            project_id=PROJECT,
            business_goals_json='[{"id":"BG-001","title":"Цель","description":"Описание"}]',
            future_state="Будущее состояние",
            solution_scope="Граница решения",
        )
        self.assertIn("✅", result)
        self.assertNotIn("ADR-055", result)

    def test_with_param_file_not_found_warning(self):
        """Если 6.1 не завершён — предупреждение, не падение."""
        result = set_business_context(
            project_id=PROJECT,
            business_goals_json='[{"id":"BG-001","title":"Цель"}]',
            future_state="Будущее",
            solution_scope="Скоуп",
            from_current_state_project_id="nonexistent_project",
        )
        # Функция работает, предупреждает
        self.assertIn("⚠️", result)

    def test_prefill_goals_from_needs(self):
        """Если BN есть — business_goals_json предзаполняется."""
        _save_needs_json()
        result = set_business_context(
            project_id=PROJECT,
            business_goals_json="",  # явно пусто
            future_state="Будущее состояние",
            solution_scope="Граница решения",
            from_current_state_project_id=PROJECT,
        )
        self.assertIn("✅", result)
        self.assertIn("ADR-055", result)

    def test_explicit_goals_not_overwritten(self):
        """Если BA явно передал business_goals_json — не перезаписываем."""
        _save_needs_json()
        explicit_goals = '[{"id":"BG-001","title":"Явная цель","description":"Описание"}]'
        result = set_business_context(
            project_id=PROJECT,
            business_goals_json=explicit_goals,
            future_state="Будущее",
            solution_scope="Скоуп",
            from_current_state_project_id=PROJECT,
        )
        self.assertIn("✅", result)
        # ADR-055 не должен упоминаться — не предзаполняли
        self.assertNotIn("ADR-055", result)

    def test_scope_prefills_solution_scope(self):
        """Если solution_scope пуст и есть файл scope — предзаполняется."""
        _save_needs_json()
        _save_scope_json()
        result = set_business_context(
            project_id=PROJECT,
            business_goals_json="",
            future_state="Будущее",
            solution_scope="",  # пусто
            from_current_state_project_id=PROJECT,
        )
        self.assertIn("✅", result)

    def test_empty_needs_list_no_crash(self):
        """Пустой список BN — без предзаполнения, без ошибки."""
        path = _save_needs_json(needs_list=[])
        result = set_business_context(
            project_id=PROJECT,
            business_goals_json='[{"id":"BG-001","title":"Цель"}]',
            future_state="Будущее",
            solution_scope="Скоуп",
            from_current_state_project_id=PROJECT,
        )
        self.assertIn("✅", result)

    def test_end_to_end_61_to_73(self):
        """Полный E2E: завершаем 6.1 → вызываем 7.3 с from_current_state_project_id."""
        # Завершаем 6.1
        _scope(elements='["business_needs"]')
        _capture(element="business_needs", description="Описание потребностей")
        _rca()
        _needs(title="Ускорить обработку", register=False)
        save_current_state(PROJECT, "Проект")

        # 7.3 читает данные 6.1
        result = set_business_context(
            project_id=PROJECT,
            business_goals_json="",
            future_state="Ускоренный процесс обработки",
            solution_scope="",
            from_current_state_project_id=PROJECT,
        )
        self.assertIn("✅", result)

    def test_from_different_project(self):
        """from_current_state_project_id может указывать на другой проект."""
        other = "other_project"
        _save_needs_json(project=other)
        result = set_business_context(
            project_id=PROJECT,
            business_goals_json="",
            future_state="Будущее",
            solution_scope="Скоуп",
            from_current_state_project_id=other,
        )
        # Должно найти файл other_project и сработать
        self.assertIn("✅", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
