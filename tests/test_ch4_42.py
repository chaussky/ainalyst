"""
tests/test_ch4_42.py — Тесты для Главы 4.2: Conduct Elicitation
MCP-файл: skills/elicitation_conduct_mcp.py
Инструменты: process_elicitation_results, compare_elicitation_results,
             save_cr_elicitation_analysis, update_stakeholder_registry

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

import skills.elicitation_conduct_mcp as mod42


# ---------------------------------------------------------------------------
# Вспомогательные данные
# ---------------------------------------------------------------------------

STAKEHOLDER_PROFILE_VALID = {
    "name": "Иван Петров",
    "role": "Менеджер продаж",
    "influence": "High",
    "interest": "High",
    "key_expectations": "Автоматизация обработки заявок",
    "key_concerns": "Сложность внедрения для пользователей",
    "related_stakeholders": ["Директор по продажам"],
}

PAINS_VALID = [
    {
        "title": "Долгая обработка заявок",
        "description": "Ручная обработка занимает 2–3 часа",
        "frequency": "Ежедневно",
        "business_impact": "Потеря клиентов из-за задержек",
        "quote": "Мы теряем до 20% клиентов из-за медленного ответа",
    },
    {
        "title": "Нет единой базы клиентов",
        "description": "Данные в Excel и в голове у менеджеров",
        "frequency": "Постоянно",
        "business_impact": "Дублирование работы",
        "quote": "",
    },
]

REQUIREMENTS_VALID = {
    "functional": [
        {"id": "FR-001", "statement": "Интеграция с 1С для синхронизации заказов", "priority": "High"},
        {"id": "FR-002", "statement": "Автоматические уведомления клиентам", "priority": "Medium"},
    ],
    "non_functional": [
        {"id": "NFR-001", "statement": "Время отклика не более 2 секунд", "priority": "High"},
    ],
    "constraints": ["Бюджет проекта — до 3 млн рублей"],
    "business_rules": ["Заявки обрабатываются в порядке поступления"],
}

PROCESS_BASE = dict(
    project_name="crm_upgrade",
    session_date="2025-03-17",
    stakeholder_role="Менеджер продаж",
    session_type="Интервью",
    stakeholder_profile_json=json.dumps(STAKEHOLDER_PROFILE_VALID),
    pains_json=json.dumps(PAINS_VALID),
    requirements_json=json.dumps(REQUIREMENTS_VALID),
    gaps_and_signals="Не уточнил версию 1С; неясно кто администрирует систему",
    ba_recommendations="Провести техническое интервью с ИТ-директором",
    maturity_level="Средний",
    maturity_notes="Хорошо понимает бизнес, но не технические детали",
)


# ---------------------------------------------------------------------------
# process_elicitation_results
# ---------------------------------------------------------------------------

class TestProcessElicitationResults(BaseMCPTest):
    """Тесты для 4.2: process_elicitation_results."""

    def _call(self, **overrides):
        kwargs = {**PROCESS_BASE, **overrides}
        with patch("skills.elicitation_conduct_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod42.process_elicitation_results(**kwargs)

    # --- happy path по всем типам сессий ---

    def test_session_type_interview(self):
        """Тип сессии: Интервью."""
        result = self._call(session_type="Интервью")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_session_type_workshop(self):
        """Тип сессии: Воркшоп."""
        result = self._call(session_type="Воркшоп")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_session_type_questionnaire(self):
        """Тип сессии: Анкетирование."""
        result = self._call(session_type="Анкетирование")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_session_type_observation(self):
        """Тип сессии: Наблюдение."""
        result = self._call(session_type="Наблюдение")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_session_type_document_analysis(self):
        """Тип сессии: Анализ документов."""
        result = self._call(session_type="Анализ документов")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- maturity levels ---

    def test_maturity_low(self):
        """Уровень зрелости: Низкий."""
        result = self._call(maturity_level="Низкий", maturity_notes="Не понимает IT")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_maturity_good(self):
        """Уровень зрелости: Хороший."""
        result = self._call(maturity_level="Хороший")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_maturity_high(self):
        """Уровень зрелости: Высокий."""
        result = self._call(maturity_level="Высокий")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- edge cases ---

    def test_empty_pains(self):
        """Нет болей — не должно падать."""
        result = self._call(pains_json=json.dumps([]))
        self.assertIsInstance(result, str)

    def test_empty_requirements(self):
        """Пустые требования — не должно падать."""
        empty_reqs = {"functional": [], "non_functional": [], "constraints": [], "business_rules": []}
        result = self._call(requirements_json=json.dumps(empty_reqs))
        self.assertIsInstance(result, str)

    def test_empty_gaps(self):
        """Нет пробелов в данных."""
        result = self._call(gaps_and_signals="")
        self.assertIsInstance(result, str)

    def test_save_artifact_called(self):
        """save_artifact вызывается при успешном выполнении."""
        with patch("skills.elicitation_conduct_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            mod42.process_elicitation_results(**PROCESS_BASE)
            mock_sa.assert_called_once()

    # --- error cases ---

    def test_invalid_profile_json(self):
        """Невалидный JSON профиля стейкхолдера → ошибка."""
        result = self._call(stakeholder_profile_json="{bad json}")
        self.assertIn("❌", result)

    def test_invalid_pains_json(self):
        """Невалидный JSON болей → ошибка."""
        result = self._call(pains_json="not a list")
        self.assertIn("❌", result)

    def test_invalid_requirements_json(self):
        """Невалидный JSON требований → ошибка."""
        result = self._call(requirements_json="{bad}")
        self.assertIn("❌", result)

    def test_returns_string(self):
        """Всегда возвращает строку."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# compare_elicitation_results
# ---------------------------------------------------------------------------

class TestCompareElicitationResults(BaseMCPTest):
    """Тесты для 4.2: compare_elicitation_results."""

    SESSIONS_SUMMARY = "Сессия 1 (Менеджер): нужна интеграция с 1С. Сессия 2 (ИТ-директор): 1С v8.3, ограничение по API."
    REQS_REGISTRY = json.dumps([
        {"id": "BR-001", "statement": "Снизить время обработки заявки", "source": "Менеджер продаж"},
        {"id": "FR-001", "statement": "Интеграция с 1С v8.3", "source": "ИТ-директор"},
    ])

    def _call(self, **overrides):
        defaults = {
            "project_name": "crm_upgrade",
            "sessions_summary": self.SESSIONS_SUMMARY,
            "contradictions": "Менеджер хочет интеграцию сразу, ИТ говорит что 1С v7 не поддерживает REST",
            "requirements_registry_json": self.REQS_REGISTRY,
            "political_map": "Менеджер — Champion, ИТ-директор — Neutral (осторожный)",
            "follow_up_plan": "Технический воркшоп с ИТ и вендором 1С",
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_conduct_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod42.compare_elicitation_results(**kwargs)

    def test_basic_comparison(self):
        """Базовое сравнение двух сессий."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_no_contradictions(self):
        """Нет противоречий — граничный случай."""
        result = self._call(contradictions="")
        self.assertIsInstance(result, str)

    def test_empty_requirements_registry(self):
        """Пустой реестр требований."""
        result = self._call(requirements_registry_json=json.dumps([]))
        self.assertIsInstance(result, str)

    def test_invalid_requirements_json(self):
        """Невалидный JSON реестра → ошибка."""
        result = self._call(requirements_registry_json="{bad}")
        self.assertIn("❌", result)

    def test_returns_string(self):
        """Всегда возвращает строку."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# save_cr_elicitation_analysis
# ---------------------------------------------------------------------------

class TestSaveCrElicitationAnalysis(BaseMCPTest):
    """Тесты для 4.2: save_cr_elicitation_analysis."""

    AFFECTED_ARTIFACTS = json.dumps([
        {"artifact": "FR-001", "type": "FR", "affected": True, "change_type": "Обновить"},
        {"artifact": "NFR-001", "type": "NFR", "affected": False, "change_type": ""},
    ])

    def _call(self, **overrides):
        defaults = {
            "project_name": "crm_upgrade",
            "cr_description": "Добавить модуль аналитики продаж с дашбордами",
            "affected_artifacts_json": self.AFFECTED_ARTIFACTS,
            "outdated_data": "Раздел требований к отчётности (FR-009–FR-011) устарел",
            "follow_up_questions": "Какой формат дашбордов? Какие KPI нужны?",
            "scope_assessment": "Средний объём — 4–5 новых требований, 2 недели",
            "workshop_needed": False,
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_conduct_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod42.save_cr_elicitation_analysis(**kwargs)

    def test_basic_cr(self):
        """Базовый CR без воркшопа."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_cr_with_workshop(self):
        """CR требует воркшопа."""
        result = self._call(
            workshop_needed=True,
            workshop_notes="Нужно собрать ИТ + бизнес для согласования требований",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_no_affected_artifacts(self):
        """Нет затронутых артефактов."""
        result = self._call(affected_artifacts_json=json.dumps([]))
        self.assertIsInstance(result, str)

    def test_invalid_affected_json(self):
        """Невалидный JSON артефактов → ошибка."""
        result = self._call(affected_artifacts_json="{bad}")
        self.assertIn("❌", result)

    def test_empty_follow_up(self):
        """Нет последующих вопросов."""
        result = self._call(follow_up_questions="")
        self.assertIsInstance(result, str)

    def test_returns_string(self):
        """Всегда возвращает строку."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# update_stakeholder_registry
# ---------------------------------------------------------------------------

class TestUpdateStakeholderRegistry(BaseMCPTest):
    """Тесты для 4.2: update_stakeholder_registry."""

    NEW_STAKEHOLDERS_VALID = json.dumps([
        {
            "name": "Пётр Васильев",
            "role": "Архитектор",
            "influence": "High",
            "interest": "Medium",
            "attitude": "Neutral",
            "contact": "petr@company.com",
            "comm_frequency": "Bi-weekly",
            "comm_triggers": ["Technical decision", "Architecture review"],
        }
    ])

    def _call(self, **overrides):
        defaults = {
            "project_name": "crm_upgrade",
            "session_source": "Интервью с ИТ-директором 2025-03-17",
            "new_stakeholders_json": self.NEW_STAKEHOLDERS_VALID,
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_conduct_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod42.update_stakeholder_registry(**kwargs)

    def test_add_single_stakeholder(self):
        """Добавление одного нового стейкхолдера."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_add_multiple_stakeholders(self):
        """Добавление нескольких стейкхолдеров за раз."""
        result = self._call(
            new_stakeholders_json=json.dumps([
                {
                    "name": "Аня",
                    "role": "QA Lead",
                    "influence": "Low",
                    "interest": "High",
                    "attitude": "Champion",
                    "contact": "anya@company.com",
                    "comm_frequency": "Weekly",
                    "comm_triggers": ["Release"],
                },
                {
                    "name": "Борис",
                    "role": "DevOps",
                    "influence": "Low",
                    "interest": "Low",
                    "attitude": "Neutral",
                    "contact": "boris@company.com",
                    "comm_frequency": "Monthly",
                    "comm_triggers": [],
                },
            ])
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_blocker_attitude(self):
        """Стейкхолдер с attitude=Blocker."""
        result = self._call(
            new_stakeholders_json=json.dumps([{
                "name": "Скептик",
                "role": "CFO",
                "influence": "High",
                "interest": "Low",
                "attitude": "Blocker",
                "contact": "",
                "comm_frequency": "Monthly",
                "comm_triggers": ["Budget review"],
            }])
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_empty_stakeholders_list(self):
        """Пустой список — нет новых стейкхолдеров."""
        result = self._call(new_stakeholders_json=json.dumps([]))
        self.assertIsInstance(result, str)

    def test_invalid_stakeholders_json(self):
        """Невалидный JSON → ошибка."""
        result = self._call(new_stakeholders_json="{bad json}")
        self.assertIn("❌", result)

    def test_returns_string(self):
        """Всегда возвращает строку."""
        self.assertIsInstance(self._call(), str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
