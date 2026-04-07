"""
tests/test_ch4_44.py — Тесты для Главы 4.4: Communicate Business Analysis Information
MCP-файл: skills/elicitation_communicate_mcp.py
Инструменты: prepare_communication_package, log_communication, check_communication_schedule

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

import skills.elicitation_communicate_mcp as mod44


# ---------------------------------------------------------------------------
# Вспомогательные данные
# ---------------------------------------------------------------------------

AUDIENCE_BUSINESS = json.dumps({
    "name": "Иван Иванов",
    "role": "Директор по продажам",
    "influence": "High",
    "interest": "High",
    "preferred_detail_level": "Executive summary",
    "preferred_format": "Email + Презентация",
})

AUDIENCE_DEVELOPER = json.dumps({
    "name": "Пётр Сидоров",
    "role": "Backend Developer",
    "influence": "Low",
    "interest": "High",
    "preferred_detail_level": "Полная техническая спецификация",
    "preferred_format": "Confluence + Jira",
})

AUDIENCE_ARCHITECT = json.dumps({
    "name": "Сергей Краснов",
    "role": "Архитектор",
    "influence": "High",
    "interest": "Medium",
    "preferred_detail_level": "Архитектурные решения и ограничения",
    "preferred_format": "Confluence",
})

KEY_MESSAGES = json.dumps([
    {
        "message": "Интеграция с 1С согласована — REST API, батч 15 мин",
        "why_it_matters": "Ключевое техническое решение проекта",
    },
    {
        "message": "Запуск запланирован на 01.06.2025",
        "why_it_matters": "Дедлайн не сдвигается",
    },
])

COMM_PACKAGE_PATH = "governance_plans/reports/4_4_package_crm_upgrade.md"


# ---------------------------------------------------------------------------
# prepare_communication_package
# ---------------------------------------------------------------------------

class TestPrepareCommunicationPackage(BaseMCPTest):
    """Тесты для 4.4: prepare_communication_package."""

    def _call(self, **overrides):
        defaults = {
            "project_name": "crm_upgrade",
            "source_artifact_path": "governance_plans/reports/4_3_confirmed_crm_upgrade.md",
            "audience_role": "Бизнес-заказчик",
            "audience_profile_json": AUDIENCE_BUSINESS,
            "adapted_content": "Требования к CRM утверждены. Интеграция с 1С согласована. Запуск 01.06.2025.",
            "key_messages_json": KEY_MESSAGES,
            "recommended_format": "Формальный документ",
            "recommended_channel": "Email",
            "open_questions": "",
            "ba_notes": "",
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_communicate_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod44.prepare_communication_package(**kwargs)

    # --- happy path по всем аудиториям ---

    def test_audience_business(self):
        """Аудитория: Бизнес-заказчик."""
        result = self._call(
            audience_role="Бизнес-заказчик",
            audience_profile_json=AUDIENCE_BUSINESS,
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_audience_manager(self):
        """Аудитория: Руководитель."""
        result = self._call(
            audience_role="Руководитель",
            audience_profile_json=AUDIENCE_BUSINESS,
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_audience_developer(self):
        """Аудитория: Разработчик."""
        result = self._call(
            audience_role="Разработчик",
            audience_profile_json=AUDIENCE_DEVELOPER,
            adapted_content="FR-001: REST API /orders/sync, батч каждые 15 минут. Endpoint: POST /api/v1/1c/sync",
            recommended_format="Неформальный документ",
            recommended_channel="Confluence / документ",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_audience_architect(self):
        """Аудитория: Архитектор / Техлид."""
        result = self._call(
            audience_role="Архитектор / Техлид",
            audience_profile_json=AUDIENCE_ARCHITECT,
            adapted_content="Интеграция через REST API. Ограничение: 1С v8.3+. Батч каждые 15 мин.",
            recommended_format="Формальный документ",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_audience_tester(self):
        """Аудитория: Тестировщик."""
        result = self._call(
            audience_role="Тестировщик",
            adapted_content="FR-001 AC: синхронизация без ошибок за 15 мин. NFR-001 AC: P95 < 2с при 100 пользователях.",
            recommended_format="Формальный документ",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- happy path по всем форматам ---

    def test_format_presentation(self):
        """Формат: Презентация."""
        result = self._call(recommended_format="Презентация")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_format_email(self):
        """Формат: Email."""
        result = self._call(recommended_format="Email")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_format_one_on_one(self):
        """Формат: Встреча 1-на-1."""
        result = self._call(recommended_format="Встреча 1-на-1")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_format_group_meeting(self):
        """Формат: Групповая встреча."""
        result = self._call(recommended_format="Групповая встреча")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- edge cases ---

    def test_with_open_questions(self):
        """Есть открытые вопросы."""
        result = self._call(
            open_questions="Нужно ли включать NFR в Executive Summary для директора?",
            ba_notes="Директор технически подкован — можно упомянуть NFR кратко",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_empty_key_messages(self):
        """Нет ключевых сообщений."""
        result = self._call(key_messages_json=json.dumps([]))
        self.assertIsInstance(result, str)

    def test_save_artifact_called(self):
        """save_artifact вызывается ровно один раз."""
        with patch("skills.elicitation_communicate_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            mod44.prepare_communication_package(
                project_name="crm_upgrade",
                source_artifact_path="governance_plans/reports/4_3.md",
                audience_role="Бизнес-заказчик",
                audience_profile_json=AUDIENCE_BUSINESS,
                adapted_content="Резюме требований",
                key_messages_json=KEY_MESSAGES,
                recommended_format="Email",
                recommended_channel="Email",
                open_questions="",
                ba_notes="",
            )
            mock_sa.assert_called_once()

    # --- error cases ---

    def test_invalid_audience_profile_json(self):
        """Невалидный JSON профиля → ошибка."""
        result = self._call(audience_profile_json="{bad json}")
        self.assertIn("❌", result)

    def test_invalid_key_messages_json(self):
        """Невалидный JSON ключевых сообщений → ошибка."""
        result = self._call(key_messages_json="not json")
        self.assertIn("❌", result)

    def test_returns_string(self):
        """Всегда возвращает строку."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# log_communication
# ---------------------------------------------------------------------------

class TestLogCommunication(BaseMCPTest):
    """Тесты для 4.4: log_communication."""

    PARTICIPANTS = json.dumps([
        {"name": "Иван Иванов", "role": "Директор по продажам"},
        {"name": "Анна BA", "role": "Бизнес-аналитик"},
    ])

    ACTION_ITEMS = json.dumps([
        {"task": "Подписать протокол требований", "owner": "Иван Иванов", "due": "2025-03-20"},
    ])

    def _call(self, **overrides):
        defaults = {
            "project_name": "crm_upgrade",
            "communication_package_path": COMM_PACKAGE_PATH,
            "audience_role": "Бизнес-заказчик",
            "communication_date": "2025-03-19",
            "channel_used": "Email",
            "participants_json": self.PARTICIPANTS,
            "understanding_status": "Понял и согласен",
            "feedback_summary": "Одобрил требования, попросил уточнить сроки развёртывания",
            "action_items_json": self.ACTION_ITEMS,
            "needs_followup": False,
            "followup_deadline": "",
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_communicate_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod44.log_communication(**kwargs)

    # --- happy path по всем каналам ---

    def test_channel_email(self):
        """Канал: Email."""
        result = self._call(channel_used="Email")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_channel_one_on_one(self):
        """Канал: Встреча 1-на-1."""
        result = self._call(channel_used="Встреча 1-на-1")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_channel_group_meeting(self):
        """Канал: Групповая встреча."""
        result = self._call(channel_used="Групповая встреча")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_channel_messenger(self):
        """Канал: Мессенджер."""
        result = self._call(channel_used="Мессенджер")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_channel_confluence(self):
        """Канал: Confluence / документ."""
        result = self._call(channel_used="Confluence / документ")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_channel_other(self):
        """Канал: Другое."""
        result = self._call(channel_used="Другое")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- happy path по всем статусам понимания ---

    def test_status_understood_agreed(self):
        result = self._call(understanding_status="Понял и согласен")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_status_partial(self):
        result = self._call(understanding_status="Понял частично")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_status_not_understood(self):
        """Статус: Не понял → нужен followup."""
        result = self._call(
            understanding_status="Не понял — нужен повтор",
            needs_followup=True,
            followup_deadline="2025-03-22",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_status_no_response(self):
        result = self._call(
            understanding_status="Нет ответа",
            needs_followup=True,
            followup_deadline="2025-03-21",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_status_disagreed(self):
        """Статус: Не согласен — эскалация."""
        result = self._call(
            understanding_status="Не согласен",
            feedback_summary="Считает что интеграция с 1С не нужна — достаточно ручного ввода",
            needs_followup=True,
            followup_deadline="2025-03-20",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- edge cases ---

    def test_empty_action_items(self):
        """Нет action items."""
        result = self._call(action_items_json=json.dumps([]))
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_followup_needed_with_deadline(self):
        """needs_followup=True с дедлайном."""
        result = self._call(needs_followup=True, followup_deadline="2025-03-25")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- error cases ---

    def test_invalid_participants_json(self):
        result = self._call(participants_json="{bad}")
        self.assertIn("❌", result)

    def test_invalid_action_items_json(self):
        result = self._call(action_items_json="not json")
        self.assertIn("❌", result)

    def test_returns_string(self):
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# check_communication_schedule
# ---------------------------------------------------------------------------

class TestCheckCommunicationSchedule(BaseMCPTest):
    """Тесты для 4.4: check_communication_schedule."""

    STAKEHOLDERS = [
        {
            "name": "Иван Иванов",
            "role": "Директор по продажам",
            "influence": "High",
            "comm_frequency": "Weekly",
            "comm_triggers": ["Major decision", "Milestone", "Risk identified"],
        },
        {
            "name": "Пётр Сидоров",
            "role": "Backend Developer",
            "influence": "Low",
            "comm_frequency": "Bi-weekly",
            "comm_triggers": ["Technical decision"],
        },
    ]

    COMM_LOG = [
        {
            "stakeholder_name": "Иван Иванов",
            "date": "2025-03-10",
            "channel": "Email",
            "needs_followup": False,
        },
        {
            "stakeholder_name": "Пётр Сидоров",
            "date": "2025-03-15",
            "channel": "Confluence / документ",
            "needs_followup": False,
        },
    ]

    def _call(self, **overrides):
        defaults = {
            "project_name": "crm_upgrade",
            "today_date": "2025-03-19",
            "stakeholders_json": json.dumps(self.STAKEHOLDERS),
            "communication_log_json": json.dumps(self.COMM_LOG),
            "triggered_events_json": json.dumps([]),
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_communicate_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod44.check_communication_schedule(**kwargs)

    def test_no_triggered_events(self):
        """Плановая проверка без событий-триггеров."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_with_milestone_trigger(self):
        """Есть событие-триггер: Milestone."""
        result = self._call(
            triggered_events_json=json.dumps([
                {"event_type": "Milestone", "description": "Требования утверждены и подписаны"}
            ])
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_with_risk_trigger(self):
        """Есть событие-триггер: Risk identified."""
        result = self._call(
            triggered_events_json=json.dumps([
                {"event_type": "Risk identified",
                 "description": "Вендор 1С уведомил о смене API в v8.4"}
            ])
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_multiple_triggers(self):
        """Несколько событий-триггеров."""
        result = self._call(
            triggered_events_json=json.dumps([
                {"event_type": "Milestone", "description": "Требования утверждены"},
                {"event_type": "Major decision", "description": "Выбрана архитектура интеграции"},
            ])
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_empty_comm_log(self):
        """Нет истории коммуникаций (новый проект)."""
        result = self._call(communication_log_json=json.dumps([]))
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_single_stakeholder(self):
        """Только один стейкхолдер."""
        result = self._call(
            stakeholders_json=json.dumps([self.STAKEHOLDERS[0]])
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- error cases ---

    def test_invalid_stakeholders_json(self):
        result = self._call(stakeholders_json="{bad}")
        self.assertIn("❌", result)

    def test_invalid_comm_log_json(self):
        result = self._call(communication_log_json="not json")
        self.assertIn("❌", result)

    def test_invalid_events_json(self):
        result = self._call(triggered_events_json="{bad}")
        self.assertIn("❌", result)

    def test_returns_string(self):
        self.assertIsInstance(self._call(), str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
