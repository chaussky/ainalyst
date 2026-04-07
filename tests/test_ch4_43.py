"""
tests/test_ch4_43.py — Тесты для Главы 4.3: Confirm Elicitation Results
MCP-файл: skills/elicitation_confirm_mcp.py
Инструменты: run_consistency_check, save_confirmed_elicitation_result

Стратегия: BaseMCPTest (tmpdir + chdir), setup_mocks() до импортов,
save_artifact патчится через patch() по правилу ADR-068.
"""

import json
import os
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tests.conftest import setup_mocks, BaseMCPTest
setup_mocks()

import skills.elicitation_confirm_mcp as mod43


# ---------------------------------------------------------------------------
# Вспомогательные данные
# ---------------------------------------------------------------------------

SOURCE_ARTIFACTS = [
    {"path": "governance_plans/reports/4_2_crm_interview.md",
     "stakeholder_role": "Менеджер продаж",
     "session_date": "2025-03-17"},
    {"path": "governance_plans/reports/4_2_crm_it_director.md",
     "stakeholder_role": "ИТ-директор",
     "session_date": "2025-03-18"},
]

ISSUE_HIGH = {
    "criterion": "Однозначность",
    "severity": "High",
    "description": "FR-001 можно трактовать как синхронизацию в реальном времени или батч",
    "affected_requirement": "FR-001",
    "recommendation": "Уточнить у ИТ-директора: real-time или батч-обработка?",
    "source_artifact": "governance_plans/reports/4_2_crm_interview.md",
}

ISSUE_LOW = {
    "criterion": "Полнота",
    "severity": "Low",
    "description": "NFR-001 не содержит метрики для нагрузочного тестирования",
    "affected_requirement": "NFR-001",
    "recommendation": "Добавить условие нагрузки (например: 100 одновременных пользователей)",
    "source_artifact": "governance_plans/reports/4_2_crm_it_director.md",
}

CONFIRMED_REQUIREMENTS = {
    "functional": [
        {"id": "FR-001",
         "statement": "Интеграция с 1С v8.3 через REST API (батч, раз в 15 минут)",
         "acceptance_criteria": "Данные синхронизируются без ошибок за 15 минут"},
        {"id": "FR-002",
         "statement": "Email-уведомление клиенту при изменении статуса заявки",
         "acceptance_criteria": "Письмо доходит в течение 5 минут после смены статуса"},
    ],
    "non_functional": [
        {"id": "NFR-001",
         "statement": "Время отклика системы не более 2 секунд при 100 одновременных пользователях",
         "acceptance_criteria": "Нагрузочный тест показывает P95 < 2с"},
    ],
    "constraints": ["Бюджет — до 3 млн рублей", "Запуск — до 01.06.2025"],
    "business_rules": ["Заявки обрабатываются в порядке поступления"],
}


# ---------------------------------------------------------------------------
# run_consistency_check
# ---------------------------------------------------------------------------

class TestRunConsistencyCheck(BaseMCPTest):
    """Тесты для 4.3: run_consistency_check."""

    def _call(self, **overrides):
        defaults = {
            "project_name": "crm_upgrade",
            "source_artifacts_json": json.dumps(SOURCE_ARTIFACTS),
            "issues_json": json.dumps([]),
            "readiness_status": "Готов к анализу",
            "readiness_rationale": "Все требования однозначны и полны",
            "needs_clarification": False,
            "clarification_questions_json": json.dumps([]),
            "ba_decision": "Передаём в анализ текущего состояния (6.1)",
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_confirm_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod43.run_consistency_check(**kwargs)

    # --- happy path по всем статусам готовности ---

    def test_status_ready_no_issues(self):
        """Статус: Готов к анализу, нет проблем."""
        result = self._call(
            readiness_status="Готов к анализу",
            issues_json=json.dumps([]),
            needs_clarification=False,
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_status_conditional_with_low_issues(self):
        """Статус: Готов условно, Low-severity проблемы."""
        result = self._call(
            readiness_status="Готов условно",
            readiness_rationale="Minor issues — не блокируют анализ",
            issues_json=json.dumps([ISSUE_LOW]),
            needs_clarification=False,
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_status_needs_rework_high_issues(self):
        """Статус: Требует доработки, High-severity проблемы с вопросами."""
        result = self._call(
            readiness_status="Требует доработки",
            readiness_rationale="Критическая неоднозначность в FR-001",
            issues_json=json.dumps([ISSUE_HIGH]),
            needs_clarification=True,
            clarification_questions_json=json.dumps([
                {
                    "stakeholder_role": "ИТ-директор",
                    "issue_id": "ISS-001",
                    "question": "FR-001: нужна синхронизация в реальном времени или батч каждые 15 минут?",
                }
            ]),
            ba_decision="Уточнить у ИТ-директора до 20.03",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_multiple_issues_mixed_severity(self):
        """Несколько проблем разного severity."""
        result = self._call(
            readiness_status="Готов условно",
            issues_json=json.dumps([ISSUE_HIGH, ISSUE_LOW]),
            needs_clarification=True,
            clarification_questions_json=json.dumps([
                {"stakeholder_role": "ИТ-директор", "issue_id": "ISS-001",
                 "question": "Real-time или батч?"}
            ]),
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_single_artifact(self):
        """Только один источник данных."""
        result = self._call(
            source_artifacts_json=json.dumps([SOURCE_ARTIFACTS[0]])
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_no_clarification_questions_when_not_needed(self):
        """needs_clarification=False, пустой список вопросов."""
        result = self._call(
            needs_clarification=False,
            clarification_questions_json=json.dumps([]),
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_save_artifact_called(self):
        """save_artifact вызывается ровно один раз."""
        with patch("skills.elicitation_confirm_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            mod43.run_consistency_check(
                project_name="crm_upgrade",
                source_artifacts_json=json.dumps(SOURCE_ARTIFACTS),
                issues_json=json.dumps([]),
                readiness_status="Готов к анализу",
                readiness_rationale="OK",
                needs_clarification=False,
                clarification_questions_json=json.dumps([]),
                ba_decision="Передать в 6.1",
            )
            mock_sa.assert_called_once()

    # --- error cases ---

    def test_invalid_artifacts_json(self):
        """Невалидный JSON артефактов → ошибка."""
        result = self._call(source_artifacts_json="{bad json}")
        self.assertIn("❌", result)

    def test_invalid_issues_json(self):
        """Невалидный JSON проблем → ошибка."""
        result = self._call(issues_json="not a list")
        self.assertIn("❌", result)

    def test_invalid_questions_json(self):
        """Невалидный JSON вопросов → ошибка."""
        result = self._call(
            needs_clarification=True,
            clarification_questions_json="{bad}",
        )
        self.assertIn("❌", result)

    def test_returns_string(self):
        """Всегда возвращает строку."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# save_confirmed_elicitation_result
# ---------------------------------------------------------------------------

class TestSaveConfirmedElicitationResult(BaseMCPTest):
    """Тесты для 4.3: save_confirmed_elicitation_result."""

    def _call(self, **overrides):
        defaults = {
            "project_name": "crm_upgrade",
            "stakeholder_role": "Менеджер продаж",
            "consistency_check_path": "governance_plans/reports/4_3_consistency_crm_upgrade.md",
            "confirmed_requirements_json": json.dumps(CONFIRMED_REQUIREMENTS),
            "resolved_issues_json": json.dumps([
                {"issue_id": "ISS-001", "resolution": "Уточнено: батч каждые 15 минут"}
            ]),
            "open_issues_json": json.dumps([]),
            "final_readiness": "Готов к анализу",
            "next_tasks": "Передать в 6.1 — анализ текущего состояния",
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_confirm_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod43.save_confirmed_elicitation_result(**kwargs)

    # --- happy path ---

    def test_fully_confirmed(self):
        """Все требования подтверждены, нет открытых вопросов."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_conditional_readiness(self):
        """Статус: Готов условно — есть открытые вопросы."""
        result = self._call(
            final_readiness="Готов условно",
            open_issues_json=json.dumps([
                {"issue_id": "ISS-002",
                 "description": "NFR метрики не подтверждены нагрузочным тестом",
                 "owner": "ИТ-директор",
                 "deadline": "2025-03-25"}
            ]),
            next_tasks="Дождаться подтверждения NFR-001 от ИТ; затем 6.1",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_no_resolved_issues(self):
        """Нет решённых вопросов (не было проблем изначально)."""
        result = self._call(resolved_issues_json=json.dumps([]))
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_requirements_with_only_functional(self):
        """Требования только функциональные."""
        only_functional = {
            "functional": CONFIRMED_REQUIREMENTS["functional"],
            "non_functional": [],
            "constraints": [],
            "business_rules": [],
        }
        result = self._call(confirmed_requirements_json=json.dumps(only_functional))
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_different_stakeholder_roles(self):
        """Разные роли стейкхолдеров."""
        for role in ["ИТ-директор", "Архитектор", "Конечный пользователь"]:
            result = self._call(stakeholder_role=role)
            self.assertIsInstance(result, str)
            self.assertNotIn("❌", result)

    def test_save_artifact_called(self):
        """save_artifact вызывается ровно один раз."""
        with patch("skills.elicitation_confirm_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            mod43.save_confirmed_elicitation_result(
                project_name="crm_upgrade",
                stakeholder_role="Менеджер",
                consistency_check_path="governance_plans/reports/check.md",
                confirmed_requirements_json=json.dumps(CONFIRMED_REQUIREMENTS),
                resolved_issues_json=json.dumps([]),
                open_issues_json=json.dumps([]),
                final_readiness="Готов к анализу",
                next_tasks="→ 6.1",
            )
            mock_sa.assert_called_once()

    # --- error cases ---

    def test_invalid_requirements_json(self):
        """Невалидный JSON требований → ошибка."""
        result = self._call(confirmed_requirements_json="{bad}")
        self.assertIn("❌", result)

    def test_invalid_resolved_json(self):
        """Невалидный JSON решённых вопросов → ошибка."""
        result = self._call(resolved_issues_json="not json")
        self.assertIn("❌", result)

    def test_invalid_open_issues_json(self):
        """Невалидный JSON открытых вопросов → ошибка."""
        result = self._call(open_issues_json="{bad}")
        self.assertIn("❌", result)

    def test_returns_string(self):
        """Всегда возвращает строку."""
        self.assertIsInstance(self._call(), str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
