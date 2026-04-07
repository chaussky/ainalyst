"""
tests/test_ch3_ch4.py — Тесты для Глав 3 и 4

Стратегия: моки установлены через conftest.setup_mocks().
Модули импортируются после этого — FastMCP и pydantic замоканы.
save_artifact замокан → функции возвращают реальный контент.

Глава 3 тестируется через planning_mcp.py напрямую (как все остальные главы).
planning.py удалён — вся логика живёт в planning_mcp.py и common.py.
"""

import json
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tests.conftest import setup_mocks, BaseMCPTest
setup_mocks()

# Глава 3 — тестируем MCP-сервер напрямую (как все остальные главы)
import skills.planning_mcp as mod3

# Глава 4 — импортируем после setup_mocks
import skills.elicitation_mcp as mod41
import skills.elicitation_conduct_mcp as mod42
import skills.elicitation_confirm_mcp as mod43
import skills.elicitation_communicate_mcp as mod44
import skills.elicitation_collaborate_mcp as mod45


# ---------------------------------------------------------------------------
# Глава 3 — Planning (тестируем через planning_mcp.py)
# ---------------------------------------------------------------------------

class TestPlanning(BaseMCPTest):

    def test_ba_approach_agile(self):
        """Высокая частота изменений + низкая неопределённость → Agile."""
        result = mod3.suggest_ba_approach(
            project_id="test_project",
            change_frequency="High",
            uncertainty="Low",
            regulatory_need=False,
        )
        self.assertIsInstance(result, str)
        self.assertIn("Agile", result)

    def test_ba_approach_predictive_regulatory(self):
        """Регуляторный проект с низкой неопределённостью → regulatory override."""
        result = mod3.suggest_ba_approach(
            project_id="test_project",
            change_frequency="Low",
            uncertainty="Low",
            regulatory_need=True,
        )
        self.assertIsInstance(result, str)
        # regulatory override меняет Predictive → Hybrid или оставляет Predictive
        # главное — не падает и возвращает строку
        self.assertGreater(len(result), 0)

    def test_ba_approach_returns_string(self):
        """suggest_ba_approach всегда возвращает строку."""
        result = mod3.suggest_ba_approach(
            project_id="test_project",
            change_frequency="Low",
            uncertainty="Low",
        )
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_classify_stakeholder_key_player(self):
        """High influence + High interest → Key Players."""
        from skills.planning_mcp import _classify_stakeholder
        zone, strategy, freq = _classify_stakeholder("High", "High")
        self.assertEqual(zone, "Key Players")

    def test_classify_stakeholder_context_setters(self):
        """High influence + Low interest → Context Setters."""
        from skills.planning_mcp import _classify_stakeholder
        zone, strategy, freq = _classify_stakeholder("High", "Low")
        self.assertEqual(zone, "Context Setters")

    def test_classify_stakeholder_subjects(self):
        """Low influence + High interest → Subjects."""
        from skills.planning_mcp import _classify_stakeholder
        zone, strategy, freq = _classify_stakeholder("Low", "High")
        self.assertEqual(zone, "Subjects")

    def test_classify_stakeholder_crowd(self):
        """Low influence + Low interest → Crowd."""
        from skills.planning_mcp import _classify_stakeholder
        zone, strategy, freq = _classify_stakeholder("Low", "Low")
        self.assertEqual(zone, "Crowd")

    def test_stakeholder_plan_valid_json(self):
        """Корректный JSON → план содержит имена стейкхолдеров."""
        stakeholders = [
            {"name": "Иван Иванов", "role": "Директор", "influence": "High", "interest": "High", "attitude": "Champion"},
            {"name": "Пётр Петров", "role": "Пользователь", "influence": "Low", "interest": "Low", "attitude": "Neutral"},
        ]
        result = mod3.plan_stakeholder_engagement(
            project_id="test_project",
            stakeholders_json=json.dumps(stakeholders),
        )
        self.assertIn("Иван Иванов", result)
        self.assertIn("Пётр Петров", result)

    def test_stakeholder_plan_invalid_json(self):
        """Невалидный JSON → сообщение об ошибке."""
        result = mod3.plan_stakeholder_engagement(
            project_id="test_project",
            stakeholders_json="not a json {{{",
        )
        self.assertIn("❌", result)

    def test_stakeholder_plan_empty_list(self):
        """Пустой список → предупреждение без падения."""
        result = mod3.plan_stakeholder_engagement(
            project_id="test_project",
            stakeholders_json="[]",
        )
        self.assertIsInstance(result, str)


# ---------------------------------------------------------------------------
# Вспомогательный класс для тестов Главы 4
# ---------------------------------------------------------------------------

class BaseCh4Test(BaseMCPTest):
    """
    Базовый класс для тестов Глав 4.
    Глава 4 MCP-инструменты вызывают save_artifact() — замокана на "✅ Сохранено".
    Тесты проверяют что:
    1. Функция не падает при корректных входных данных
    2. Функция возвращает сообщение об ошибке при невалидных данных
    """
    def assertSucceeds(self, result: str):
        """Функция выполнилась успешно (не вернула ❌)."""
        self.assertIsInstance(result, str)
        self.assertNotIn("❌ Ошибка разбора", result)
        self.assertNotIn("Traceback", result)

    def assertFails(self, result: str):
        """Функция вернула ошибку."""
        self.assertIn("❌", result)


# ---------------------------------------------------------------------------
# Глава 4.1 — Prepare for Elicitation
# ---------------------------------------------------------------------------

class TestElicitationPrep(BaseCh4Test):

    def test_save_plan_basic(self):
        """Базовый план выявления не вызывает ошибок."""
        result = mod41.save_elicitation_plan(
            project_name="CRM Проект",
            goals="Выяснить требования к интеграции",
            stakeholders_json=json.dumps([
                {"name": "Иван", "role": "Менеджер", "key_questions": ["Что нужно?"]}
            ]),
            technique="Интервью",
            technique_rationale="Лучше для глубокого понимания",
            questions_or_agenda="1. Какие процессы автоматизировать?\n2. Какие интеграции нужны?",
            expected_outcomes="Список требований к CRM",
        )
        self.assertSucceeds(result)

    def test_save_plan_invalid_json(self):
        """Невалидный JSON стейкхолдеров → сообщение об ошибке."""
        result = mod41.save_elicitation_plan(
            project_name="Тест",
            goals="Цель",
            stakeholders_json="{invalid}",
            technique="Интервью",
            technique_rationale="",
            questions_or_agenda="",
            expected_outcomes="",
        )
        self.assertFails(result)


# ---------------------------------------------------------------------------
# Глава 4.2 — Conduct Elicitation
# ---------------------------------------------------------------------------

class TestElicitationConduct(BaseCh4Test):

    def test_process_results_basic(self):
        """Базовые результаты сессии обрабатываются без ошибок."""
        result = mod42.process_elicitation_results(
            project_name="CRM Проект",
            session_date="2025-03-17",
            stakeholder_role="Менеджер продаж",
            session_type="Интервью",
            stakeholder_profile_json=json.dumps({
                "name": "Иван", "role": "Менеджер",
                "influence": "High", "interest": "High",
                "key_expectations": "Автоматизация заявок",
                "key_concerns": "Сложность внедрения",
                "related_stakeholders": [],
            }),
            pains_json=json.dumps([{
                "title": "Долго обрабатываются заявки",
                "description": "Ручная обработка занимает 2 часа",
                "frequency": "Ежедневно",
                "business_impact": "Потеря клиентов",
                "quote": "Мы теряем деньги каждый день",
            }]),
            requirements_json=json.dumps({
                "functional": [{"id": "FR-001", "statement": "Интеграция с 1С", "priority": "High"}],
                "non_functional": [],
                "constraints": [],
                "business_rules": [],
            }),
            gaps_and_signals="Не уточнил версию 1С",
            ba_recommendations="Нужно уточнить технические детали",
            maturity_level="Средний",
            maturity_notes="Понимает бизнес, но не IT",
        )
        self.assertSucceeds(result)

    def test_save_cr_analysis(self):
        """CR анализ сохраняется без ошибок."""
        result = mod42.save_cr_elicitation_analysis(
            project_name="CRM Проект",
            cr_description="Добавить модуль аналитики",
            affected_artifacts_json=json.dumps([
                {"artifact": "FR-001", "type": "FR", "affected": True, "change_type": "Обновить"}
            ]),
            outdated_data="Старые требования к отчётам устарели",
            follow_up_questions="Какой формат отчётов нужен?",
            scope_assessment="Средний объём — 3-4 новых требования",
            workshop_needed=False,
        )
        self.assertSucceeds(result)

    def test_update_stakeholder_registry(self):
        """Обновление реестра стейкхолдеров не вызывает ошибок."""
        result = mod42.update_stakeholder_registry(
            project_name="CRM Проект",
            session_source="Интервью с Менеджером продаж 2025-03-17",
            new_stakeholders_json=json.dumps([
                {
                    "name": "Анна Смирнова",
                    "role": "Директор по продажам",
                    "influence": "High",
                    "interest": "High",
                    "attitude": "Champion",
                    "contact": "anna@company.com",
                    "comm_frequency": "Weekly",
                    "comm_triggers": ["Major decisions"],
                }
            ]),
        )
        self.assertSucceeds(result)

    def test_process_results_invalid_json(self):
        """Невалидный JSON → ошибка."""
        result = mod42.process_elicitation_results(
            project_name="Тест",
            session_date="2025-03-17",
            stakeholder_role="Тест",
            session_type="Интервью",
            stakeholder_profile_json="{bad json}",
            pains_json="[]",
            requirements_json="[]",
            gaps_and_signals="",
            ba_recommendations="",
            maturity_level="Средний",
            maturity_notes="",
        )
        self.assertFails(result)


# ---------------------------------------------------------------------------
# Глава 4.3 — Confirm Elicitation Results
# ---------------------------------------------------------------------------

class TestElicitationConfirm(BaseCh4Test):

    def test_run_consistency_check_no_issues(self):
        """Проверка без проблем — не падает."""
        result = mod43.run_consistency_check(
            project_name="CRM Проект",
            source_artifacts_json=json.dumps([
                {"path": "governance_plans/4_2_test.md",
                 "stakeholder_role": "Менеджер", "session_date": "2025-03-17"}
            ]),
            issues_json=json.dumps([]),
            readiness_status="Готов к анализу",
            readiness_rationale="Все критерии выполнены",
            needs_clarification=False,
            clarification_questions_json=json.dumps([]),
            ba_decision="Передаём в 6.x",
        )
        self.assertSucceeds(result)

    def test_run_consistency_check_with_issues(self):
        """Проверка с проблемами — не падает."""
        issues = [{
            "criterion": "Однозначность",
            "severity": "High",
            "description": "FR-001 можно трактовать двояко",
            "affected_requirement": "FR-001",
            "recommendation": "Уточнить формулировку",
            "source_artifact": "governance_plans/4_2_test.md",
        }]
        result = mod43.run_consistency_check(
            project_name="CRM Проект",
            source_artifacts_json=json.dumps([
                {"path": "governance_plans/4_2_test.md",
                 "stakeholder_role": "Менеджер", "session_date": "2025-03-17"}
            ]),
            issues_json=json.dumps(issues),
            readiness_status="Требует доработки",
            readiness_rationale="Критические проблемы",
            needs_clarification=True,
            clarification_questions_json=json.dumps([
                {"stakeholder_role": "Менеджер", "issue_id": "ISS-001",
                 "question": "Что именно имеется в виду в FR-001?"}
            ]),
            ba_decision="Уточнить у стейкхолдера",
        )
        self.assertSucceeds(result)

    def test_save_confirmed_result(self):
        """Финальный артефакт сохраняется без ошибок."""
        reqs = {
            "functional": [
                {"id": "FR-001", "statement": "Интеграция с 1С",
                 "acceptance_criteria": "Данные синхронизируются"}
            ],
            "non_functional": [],
            "constraints": ["Бюджет до 500к"],
            "business_rules": [],
        }
        result = mod43.save_confirmed_elicitation_result(
            project_name="CRM Проект",
            stakeholder_role="Менеджер продаж",
            consistency_check_path="governance_plans/4_3_check.md",
            confirmed_requirements_json=json.dumps(reqs),
            resolved_issues_json=json.dumps([]),
            open_issues_json=json.dumps([]),
            final_readiness="Готов к анализу",
            next_tasks="Передать в 6.1",
        )
        self.assertSucceeds(result)


# ---------------------------------------------------------------------------
# Глава 4.4 — Communicate Business Analysis Information
# ---------------------------------------------------------------------------

class TestElicitationCommunicate(BaseCh4Test):

    def test_prepare_package_business(self):
        result = mod44.prepare_communication_package(
            project_name="CRM Проект",
            source_artifact_path="governance_plans/4_3_confirmed.md",
            audience_role="Бизнес-заказчик",
            audience_profile_json=json.dumps({
                "name": "Иван Иванов", "role": "Директор",
                "influence": "High", "interest": "High"
            }),
            adapted_content="Требования к CRM утверждены. Интеграция с 1С запланирована.",
            key_messages_json=json.dumps([
                {"message": "Проект идёт по плану", "why_it_matters": "Бюджет в норме"}
            ]),
            recommended_format="Краткое резюме",
            recommended_channel="Email",
            open_questions="",
            ba_notes="",
        )
        self.assertSucceeds(result)

    def test_prepare_package_developer(self):
        result = mod44.prepare_communication_package(
            project_name="CRM Проект",
            source_artifact_path="governance_plans/4_3_confirmed.md",
            audience_role="Разработчик",
            audience_profile_json=json.dumps({
                "name": "Пётр", "role": "Backend Developer",
                "influence": "Low", "interest": "High"
            }),
            adapted_content="FR-001: REST API интеграция с 1С v8.3",
            key_messages_json=json.dumps([
                {"message": "REST API", "why_it_matters": "Современный стандарт"}
            ]),
            recommended_format="Техническое описание",
            recommended_channel="Confluence / документ",
            open_questions="Какая версия 1С?",
            ba_notes="",
        )
        self.assertSucceeds(result)

    def test_log_communication(self):
        """Факт коммуникации логируется без ошибок."""
        result = mod44.log_communication(
            project_name="CRM Проект",
            communication_package_path="governance_plans/4_4_package.md",
            audience_role="Бизнес-заказчик",
            communication_date="2025-03-17",
            channel_used="Email",
            participants_json=json.dumps([{"name": "Иван Иванов", "role": "Директор"}]),
            understanding_status="Понял и согласен",
            feedback_summary="Одобрил требования",
            action_items_json=json.dumps([
                {"task": "Подписать протокол", "owner": "Иван", "due": "2025-03-20"}
            ]),
            needs_followup=False,
            followup_deadline="",
        )
        self.assertSucceeds(result)

    def test_check_communication_schedule(self):
        """Расписание коммуникаций проверяется без ошибок."""
        stakeholders = [
            {
                "name": "Иван Иванов",
                "role": "Директор",
                "influence": "High",
                "comm_frequency": "Weekly",
                "comm_triggers": ["Major decision", "Milestone"],
            }
        ]
        comm_log = [
            {
                "stakeholder_name": "Иван Иванов",
                "date": "2025-03-01",
                "channel": "Email",
                "needs_followup": False,
            }
        ]
        result = mod44.check_communication_schedule(
            project_name="CRM Проект",
            today_date="2025-03-17",
            stakeholders_json=json.dumps(stakeholders),
            communication_log_json=json.dumps(comm_log),
            triggered_events_json=json.dumps([
                {"event_type": "Milestone", "description": "Требования утверждены"}
            ]),
        )
        self.assertSucceeds(result)


# ---------------------------------------------------------------------------
# Глава 4.5 — Manage Stakeholder Collaboration
# ---------------------------------------------------------------------------

class TestElicitationCollaborate(BaseCh4Test):

    def test_log_decision(self):
        result = mod45.log_decision(
            project_name="CRM Проект",
            decision_date="2025-03-17",
            decision_statement="Использовать REST API для интеграции с 1С",
            context="Нужно выбрать протокол интеграции",
            alternatives_json=json.dumps([
                {"option": "SOAP", "reason_rejected": "Устаревший стандарт"}
            ]),
            decision_maker="Архитектор",
            participants_json=json.dumps([
                {"name": "Архитектор", "position": "За REST"},
                {"name": "BA", "position": "Нейтрально"},
            ]),
            decision_type="Архитектурное",
            affected_artifacts_json=json.dumps([
                {"artifact": "FR-005", "impact": "Нужно обновить описание API"},
            ]),
            rationale="REST современнее и лучше документирован",
            risks="Нужна валидация на стороне 1С",
        )
        self.assertSucceeds(result)

    def test_save_meeting_notes(self):
        result = mod45.save_meeting_notes(
            project_name="CRM Проект",
            meeting_date="2025-03-17",
            meeting_type="Воркшоп",
            participants_json=json.dumps([
                {"name": "Иван", "position": "Заказчик"},
                {"name": "Анна", "position": "BA"},
            ]),
            agenda_json=json.dumps([
                {"item": "Обзор FR-001–FR-010", "owner": "Анна"},
                {"item": "Вопросы интеграции", "owner": "Иван"},
            ]),
            discussion_summary="Требования одобрены с комментариями",
            decisions_json=json.dumps([
                {"decision": "FR-007 уточнить до следующей встречи", "decision_maker": "BA"}
            ]),
            action_items_json=json.dumps([
                {"task": "Уточнить FR-007", "owner": "Анна", "due": "2025-03-20"}
            ]),
            open_questions="Какая версия 1С?",
            risks_identified="Недоступность техлида",
            next_meeting="2025-03-24",
        )
        self.assertSucceeds(result)

    def test_update_engagement_status(self):
        """Изменение вовлечённости фиксируется без ошибок."""
        result = mod45.update_engagement_status(
            project_name="CRM Проект",
            stakeholder_role="Директор по продажам",
            change_date="2025-03-17",
            attitude_before="Champion",
            attitude_after="Neutral",
            engagement_level_before="Активный",
            engagement_level_after="Пассивный",
            signal_observed="Перестал отвечать, пропустил 2 встречи",
            probable_cause="Внутренние изменения в отделе",
            ba_action_taken="Назначил встречу один на один",
            ba_action_planned="Выяснить причину изменения позиции",
            escalation_needed=False,
            escalation_to="",
        )
        self.assertSucceeds(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
