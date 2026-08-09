"""
tests/test_ch4_45.py — Тесты для Главы 4.5: Manage Stakeholder Collaboration
MCP-файл: skills/elicitation_collaborate_mcp.py
Инструменты: log_decision, save_meeting_notes, update_engagement_status

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

import skills.elicitation_collaborate_mcp as mod45


# ---------------------------------------------------------------------------
# Вспомогательные данные
# ---------------------------------------------------------------------------

ALTERNATIVES_SOAP_VS_REST = json.dumps([
    {
        "option": "SOAP",
        "reason_rejected": "Устаревший стандарт, нет поддержки в новых клиентских библиотеках",
    },
    {
        "option": "GraphQL",
        "reason_rejected": "Избыточно для задачи; 1С v8.3 не поддерживает нативно",
    },
])

PARTICIPANTS_TECH = json.dumps([
    {"name": "Сергей Краснов", "position": "Предложил REST API"},
    {"name": "Пётр Сидоров", "position": "Подтвердил реализуемость"},
    {"name": "Анна BA", "position": "Зафиксировала решение"},
])

PARTICIPANTS_WORKSHOP = json.dumps([
    {"name": "Иван Иванов", "position": "Представитель бизнеса"},
    {"name": "Анна BA", "position": "Фасилитатор"},
    {"name": "Пётр Сидоров", "position": "Разработчик"},
    {"name": "Сергей Краснов", "position": "Архитектор"},
])

AGENDA_WORKSHOP = json.dumps([
    {"item": "Обзор требований FR-001–FR-010", "owner": "Анна BA"},
    {"item": "Вопросы интеграции с 1С", "owner": "Сергей Краснов"},
    {"item": "Приоритизация МВП", "owner": "Иван Иванов"},
])

DECISIONS_WORKSHOP = json.dumps([
    {
        "decision": "REST API через /api/v1/1c/sync, батч каждые 15 минут",
        "decision_maker": "Сергей Краснов",
    },
    {
        "decision": "FR-007 вынести за скоуп МВП, реализовать в v2.0",
        "decision_maker": "Иван Иванов",
    },
])

ACTION_ITEMS_WORKSHOP = json.dumps([
    {"task": "Обновить FR-007 — пометить как out of scope МВП", "owner": "Анна BA", "due": "2025-03-21"},
    {"task": "Подготовить Swagger для 1С интеграции", "owner": "Пётр Сидоров", "due": "2025-03-28"},
])


# ---------------------------------------------------------------------------
# log_decision
# ---------------------------------------------------------------------------

class TestLogDecision(BaseMCPTest):
    """Тесты для 4.5: log_decision."""

    def _call(self, **overrides):
        defaults = {
            "project_name": "crm_upgrade",
            "decision_date": "2025-03-19",
            "decision_statement": "Использовать REST API для интеграции с 1С v8.3",
            "context": "Нужно выбрать протокол интеграции с корпоративной ERP",
            "alternatives_json": ALTERNATIVES_SOAP_VS_REST,
            "decision_maker": "Архитектор Сергей Краснов",
            "participants_json": PARTICIPANTS_TECH,
            "decision_type": "Архитектурное",
            "affected_artifacts_json": json.dumps([
                {"artifact": "FR-001", "impact": "Обновить формулировку — добавить REST API"},
                {"artifact": "NFR-002", "impact": "Добавить требования к безопасности API"},
            ]),
            "rationale": "REST лучше документирован, поддерживается современными библиотеками, реализуем на 1С v8.3+",
            "risks": "Нужна валидация совместимости с конкретной версией 1С на стороне вендора",
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_collaborate_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod45.log_decision(**kwargs)

    # --- happy path по всем типам решений ---

    def test_type_requirement(self):
        """Тип решения: Требование."""
        result = self._call(
            decision_type="Требование",
            decision_statement="FR-007 выносится за скоуп МВП",
            rationale="Не критично для запуска",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_type_priority(self):
        """Тип решения: Приоритет."""
        result = self._call(
            decision_type="Приоритет",
            decision_statement="FR-001 — Must Have, FR-007 — Could Have",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_type_architectural(self):
        """Тип решения: Архитектурное."""
        result = self._call(decision_type="Архитектурное")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_type_process(self):
        """Тип решения: Процессное."""
        result = self._call(
            decision_type="Процессное",
            decision_statement="Утверждать требования на еженедельных встречах",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_type_scope(self):
        """Тип решения: Scope."""
        result = self._call(
            decision_type="Scope",
            decision_statement="Модуль аналитики выносится в v2.0",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_type_other(self):
        """Тип решения: Другое."""
        result = self._call(decision_type="Другое")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- edge cases ---

    def test_no_alternatives(self):
        """Не было альтернатив — единственный вариант."""
        result = self._call(
            alternatives_json=json.dumps([]),
            rationale="Единственный технически доступный вариант",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_no_affected_artifacts(self):
        """Решение не затрагивает артефакты напрямую."""
        result = self._call(affected_artifacts_json=json.dumps([]))
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_no_risks(self):
        """Нет рисков."""
        result = self._call(risks="")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_single_participant(self):
        """Только один участник (единоличное решение)."""
        result = self._call(
            participants_json=json.dumps([
                {"name": "Директор", "position": "Принял решение единолично"}
            ])
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_save_artifact_called(self):
        """save_artifact вызывается ровно один раз."""
        with patch("skills.elicitation_collaborate_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            mod45.log_decision(
                project_name="crm_upgrade",
                decision_date="2025-03-19",
                decision_statement="REST API",
                context="Выбор протокола",
                alternatives_json=ALTERNATIVES_SOAP_VS_REST,
                decision_maker="Архитектор",
                participants_json=PARTICIPANTS_TECH,
                decision_type="Архитектурное",
                affected_artifacts_json=json.dumps([]),
                rationale="Лучший выбор",
                risks="",
            )
            mock_sa.assert_called_once()

    # --- error cases ---

    def test_invalid_alternatives_json(self):
        result = self._call(alternatives_json="{bad}")
        self.assertIn("❌", result)

    def test_invalid_participants_json(self):
        result = self._call(participants_json="{bad json}")
        self.assertIn("❌", result)

    def test_invalid_affected_artifacts_json(self):
        result = self._call(affected_artifacts_json="not json")
        self.assertIn("❌", result)

    def test_returns_string(self):
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# save_meeting_notes
# ---------------------------------------------------------------------------

class TestSaveMeetingNotes(BaseMCPTest):
    """Тесты для 4.5: save_meeting_notes."""

    def _call(self, **overrides):
        defaults = {
            "project_name": "crm_upgrade",
            "meeting_date": "2025-03-19",
            "meeting_type": "Воркшоп",
            "participants_json": PARTICIPANTS_WORKSHOP,
            "agenda_json": AGENDA_WORKSHOP,
            "discussion_summary": "Разобрали FR-001–FR-010. Согласовали REST API. FR-007 вынесли в v2.0.",
            "decisions_json": DECISIONS_WORKSHOP,
            "action_items_json": ACTION_ITEMS_WORKSHOP,
            "open_questions": "Нужна ли авторизация для API через OAuth или достаточно API key?",
            "risks_identified": "Вендор 1С не подтвердил совместимость — риск задержки",
            "next_meeting": "2025-03-26",
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_collaborate_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod45.save_meeting_notes(**kwargs)

    # --- happy path по всем типам встреч ---

    def test_type_interview(self):
        """Тип встречи: Интервью."""
        result = self._call(meeting_type="Интервью")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_type_workshop(self):
        """Тип встречи: Воркшоп."""
        result = self._call(meeting_type="Воркшоп")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_type_status_meeting(self):
        """Тип встречи: Статус-митинг."""
        result = self._call(
            meeting_type="Статус-митинг",
            discussion_summary="Обсудили прогресс: 70% требований собрано",
            decisions_json=json.dumps([]),
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_type_facilitation(self):
        """Тип встречи: Фасилитационная сессия."""
        result = self._call(meeting_type="Фасилитационная сессия")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_type_one_on_one(self):
        """Тип встречи: Встреча 1-на-1."""
        result = self._call(
            meeting_type="Встреча 1-на-1",
            participants_json=json.dumps([
                {"name": "Иван Иванов", "position": "Директор"},
                {"name": "Анна BA", "position": "Аналитик"},
            ]),
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_type_presentation(self):
        """Тип встречи: Презентация."""
        result = self._call(
            meeting_type="Презентация",
            discussion_summary="Представили требования спонсору. Одобрено.",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_type_other(self):
        """Тип встречи: Другое."""
        result = self._call(meeting_type="Другое")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- edge cases ---

    def test_no_decisions(self):
        """Встреча без решений (только обсуждение)."""
        result = self._call(decisions_json=json.dumps([]))
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_no_action_items(self):
        """Нет задач по итогам встречи."""
        result = self._call(action_items_json=json.dumps([]))
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_no_open_questions(self):
        """Все вопросы закрыты."""
        result = self._call(open_questions="")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_no_next_meeting(self):
        """Нет следующей встречи."""
        result = self._call(next_meeting="")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_no_risks(self):
        """Нет выявленных рисков."""
        result = self._call(risks_identified="")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_save_artifact_called(self):
        """save_artifact вызывается ровно один раз."""
        with patch("skills.elicitation_collaborate_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            mod45.save_meeting_notes(
                project_name="crm_upgrade",
                meeting_date="2025-03-19",
                meeting_type="Воркшоп",
                participants_json=PARTICIPANTS_WORKSHOP,
                agenda_json=AGENDA_WORKSHOP,
                discussion_summary="Обсуждение требований",
                decisions_json=DECISIONS_WORKSHOP,
                action_items_json=ACTION_ITEMS_WORKSHOP,
                open_questions="",
                risks_identified="",
                next_meeting="",
            )
            mock_sa.assert_called_once()

    # --- error cases ---

    def test_invalid_participants_json(self):
        result = self._call(participants_json="{bad}")
        self.assertIn("❌", result)

    def test_invalid_agenda_json(self):
        result = self._call(agenda_json="not json")
        self.assertIn("❌", result)

    def test_invalid_decisions_json(self):
        result = self._call(decisions_json="{bad}")
        self.assertIn("❌", result)

    def test_invalid_action_items_json(self):
        result = self._call(action_items_json="not json")
        self.assertIn("❌", result)

    def test_returns_string(self):
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# update_engagement_status
# ---------------------------------------------------------------------------

class TestUpdateEngagementStatus(BaseMCPTest):
    """Тесты для 4.5: update_engagement_status."""

    def _call(self, **overrides):
        defaults = {
            "project_name": "crm_upgrade",
            "stakeholder_role": "Директор по продажам",
            "change_date": "2025-03-19",
            "attitude_before": "Champion",
            "attitude_after": "Neutral",
            "engagement_level_before": "Активный",
            "engagement_level_after": "Пассивный",
            "signal_observed": "Пропустил два статус-митинга, не отвечает на письма 5 дней",
            "probable_cause": "Предполагаемая реорганизация в его отделе",
            "ba_action_taken": "Написал в мессенджер напрямую, назначил встречу 1-на-1",
            "ba_action_planned": "Выяснить причину изменения позиции, возможно нужна эскалация",
            "escalation_needed": False,
            "escalation_to": "",
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_collaborate_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod45.update_engagement_status(**kwargs)

    # --- happy path — все комбинации переходов attitude ---

    def test_champion_to_neutral(self):
        """Champion → Neutral."""
        result = self._call(attitude_before="Champion", attitude_after="Neutral")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_champion_to_blocker(self):
        """Champion → Blocker (критический переход)."""
        result = self._call(
            attitude_before="Champion",
            attitude_after="Blocker",
            signal_observed="Публично выразил несогласие на совете директоров",
            escalation_needed=True,
            escalation_to="PM → Steering Committee",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_neutral_to_champion(self):
        """Neutral → Champion (позитивный переход)."""
        result = self._call(
            attitude_before="Neutral",
            attitude_after="Champion",
            engagement_level_before="Пассивный",
            engagement_level_after="Активный",
            signal_observed="Начал активно предлагать улучшения, привлёк дополнительных стейкхолдеров",
            ba_action_taken="Вовлёк в детальное обсуждение требований к дашбордам",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_neutral_to_blocker(self):
        """Neutral → Blocker."""
        result = self._call(
            attitude_before="Neutral",
            attitude_after="Blocker",
            escalation_needed=True,
            escalation_to="PM",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_blocker_to_neutral(self):
        """Blocker → Neutral (улучшение ситуации)."""
        result = self._call(
            attitude_before="Blocker",
            attitude_after="Neutral",
            signal_observed="После встречи с PM согласился на компромисс",
            ba_action_taken="Организовал встречу с PM и стейкхолдером",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_blocker_to_champion(self):
        """Blocker → Champion (лучший исход)."""
        result = self._call(
            attitude_before="Blocker",
            attitude_after="Champion",
            signal_observed="После демо прототипа стал активным сторонником",
            ba_action_planned="Привлечь к UAT как ключевого тестировщика",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- engagement level transitions ---

    def test_passive_to_active(self):
        """Пассивный → Активный."""
        result = self._call(
            engagement_level_before="Пассивный",
            engagement_level_after="Активный",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_absent_to_passive(self):
        """Отсутствует → Пассивный."""
        result = self._call(
            engagement_level_before="Отсутствует",
            engagement_level_after="Пассивный",
            signal_observed="Впервые появился на встрече",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_active_to_absent(self):
        """Активный → Отсутствует (тревожный сигнал)."""
        result = self._call(
            engagement_level_before="Активный",
            engagement_level_after="Отсутствует",
            escalation_needed=True,
            escalation_to="PM",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- escalation scenarios ---

    def test_escalation_needed_with_target(self):
        """Нужна эскалация — указан получатель."""
        result = self._call(
            escalation_needed=True,
            escalation_to="PM → Steering Committee",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_no_escalation(self):
        """Эскалация не нужна."""
        result = self._call(escalation_needed=False, escalation_to="")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_save_artifact_called(self):
        """save_artifact вызывается ровно один раз."""
        with patch("skills.elicitation_collaborate_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            mod45.update_engagement_status(
                project_name="crm_upgrade",
                stakeholder_role="Директор",
                change_date="2025-03-19",
                attitude_before="Champion",
                attitude_after="Neutral",
                engagement_level_before="Активный",
                engagement_level_after="Пассивный",
                signal_observed="Перестал отвечать",
                probable_cause="Неизвестно",
                ba_action_taken="Написал",
                ba_action_planned="Встреча",
                escalation_needed=False,
                escalation_to="",
            )
            mock_sa.assert_called_once()

    def test_returns_string(self):
        self.assertIsInstance(self._call(), str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
