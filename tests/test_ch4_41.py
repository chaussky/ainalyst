"""
tests/test_ch4_41.py — Тесты для Главы 4.1: Prepare for Elicitation
MCP-файл: skills/elicitation_mcp.py
Инструменты: save_elicitation_plan, create_google_form, get_form_responses

Стратегия: BaseMCPTest (tmpdir + chdir), setup_mocks() до импортов,
save_artifact патчится через patch() по правилу ADR-068.
"""

import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tests.conftest import setup_mocks, BaseMCPTest
setup_mocks()

import skills.elicitation_mcp as mod41


# ---------------------------------------------------------------------------
# Вспомогательные данные
# ---------------------------------------------------------------------------

STAKEHOLDERS_VALID = json.dumps([
    {
        "name": "Иван Петров",
        "role": "Менеджер продаж",
        "key_questions": ["Какие процессы автоматизировать?", "Какие KPI?"],
    },
    {
        "name": "Анна Смирнова",
        "role": "ИТ-директор",
        "key_questions": ["Какие интеграции?", "Какие ограничения по безопасности?"],
    },
])

PLAN_BASE = dict(
    project_name="crm_upgrade",
    goals="Выяснить требования к автоматизации продаж",
    stakeholders_json=STAKEHOLDERS_VALID,
    technique="Интервью",
    technique_rationale="Глубокое понимание болей стейкхолдеров",
    questions_or_agenda="1. Текущие процессы?\n2. Что мешает работе?\n3. Ожидания от системы?",
    expected_outcomes="Список функциональных требований и болей",
)


# ---------------------------------------------------------------------------
# save_elicitation_plan
# ---------------------------------------------------------------------------

class TestSaveElicitationPlan(BaseMCPTest):
    """Тесты для инструмента 4.1: save_elicitation_plan."""

    def _call(self, **overrides):
        kwargs = {**PLAN_BASE, **overrides}
        with patch("skills.elicitation_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod41.save_elicitation_plan(**kwargs)

    # --- happy path по всем техникам ---

    def test_technique_interview(self):
        """Техника Интервью — базовый сценарий."""
        result = self._call(technique="Интервью")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_technique_workshop(self):
        """Техника Воркшоп."""
        result = self._call(
            technique="Воркшоп",
            technique_rationale="Нужно согласование между отделами",
            questions_or_agenda="09:00 Вступление\n09:30 Анализ AS-IS\n10:30 TO-BE",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_technique_questionnaire(self):
        """Техника Анкетирование."""
        result = self._call(
            technique="Анкетирование",
            technique_rationale="Много участников, нужен масштаб",
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_technique_brainstorm(self):
        """Техника Мозговой штурм."""
        result = self._call(technique="Мозговой штурм")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_technique_document_analysis(self):
        """Техника Анализ документов."""
        result = self._call(technique="Анализ документов")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_technique_observation(self):
        """Техника Наблюдение."""
        result = self._call(technique="Наблюдение")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_technique_prototyping(self):
        """Техника Прототипирование."""
        result = self._call(technique="Прототипирование")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_technique_focus_group(self):
        """Техника Фокус-группа."""
        result = self._call(technique="Фокус-группа")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_technique_benchmarking(self):
        """Техника Бенчмаркинг."""
        result = self._call(technique="Бенчмаркинг")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- edge cases ---

    def test_single_stakeholder(self):
        """Один стейкхолдер — граничный случай."""
        result = self._call(
            stakeholders_json=json.dumps([
                {"name": "Директор", "role": "CEO", "key_questions": ["Зачем проект?"]}
            ])
        )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_empty_questions_or_agenda(self):
        """Пустая повестка — не должна падать."""
        result = self._call(questions_or_agenda="")
        self.assertIsInstance(result, str)

    def test_empty_expected_outcomes(self):
        """Пустые ожидаемые результаты — не должны падать."""
        result = self._call(expected_outcomes="")
        self.assertIsInstance(result, str)

    def test_different_project_names(self):
        """Разные project_name не вызывают коллизий."""
        result1 = self._call(project_name="project_alpha")
        result2 = self._call(project_name="project_beta")
        self.assertNotIn("❌", result1)
        self.assertNotIn("❌", result2)

    # --- error cases ---

    def test_invalid_json_stakeholders(self):
        """Невалидный JSON стейкхолдеров → ошибка."""
        result = self._call(stakeholders_json="{bad json}")
        self.assertIn("❌", result)

    def test_empty_json_stakeholders(self):
        """Пустая строка вместо JSON → ошибка."""
        result = self._call(stakeholders_json="")
        self.assertIn("❌", result)

    def test_stakeholders_not_a_list(self):
        """JSON-объект вместо списка → ошибка."""
        result = self._call(stakeholders_json=json.dumps({"name": "Иван"}))
        self.assertIn("❌", result)

    def test_save_artifact_called(self):
        """save_artifact вызывается ровно один раз."""
        with patch("skills.elicitation_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            mod41.save_elicitation_plan(**PLAN_BASE)
            mock_sa.assert_called_once()

    def test_returns_string(self):
        """Функция всегда возвращает строку."""
        result = self._call()
        self.assertIsInstance(result, str)


# ---------------------------------------------------------------------------
# create_google_form
# ---------------------------------------------------------------------------

class TestCreateGoogleForm(BaseMCPTest):
    """Тесты для инструмента 4.1: create_google_form."""

    QUESTIONS_VALID = json.dumps([
        {
            "question": "Какие процессы чаще всего вызывают задержки?",
            "type": "paragraph",
            "required": True,
        },
        {
            "question": "Насколько вы довольны текущей системой? (1–5)",
            "type": "scale",
            "required": True,
        },
        {
            "question": "Какой функционал вы хотели бы видеть?",
            "type": "multiple_choice",
            "options": ["Отчёты", "Интеграции", "Автоматизация"],
            "required": False,
        },
    ])

    def _call(self, **overrides):
        defaults = {
            "title": "Анкета: требования к CRM",
            "description": "Помогите нам понять ваши потребности",
            "questions_json": self.QUESTIONS_VALID,
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.elicitation_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod41.create_google_form(**kwargs)

    def test_basic_form(self):
        """Базовая форма создаётся без ошибок."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_single_question(self):
        """Форма с одним вопросом."""
        result = self._call(
            questions_json=json.dumps([
                {"question": "Что улучшить?", "type": "paragraph", "required": True}
            ])
        )
        self.assertIsInstance(result, str)

    def test_returns_string(self):
        """Всегда возвращает строку."""
        self.assertIsInstance(self._call(), str)

    def test_invalid_questions_json(self):
        """Невалидный JSON вопросов → ошибка."""
        result = self._call(questions_json="{invalid}")
        self.assertIn("❌", result)

    def test_empty_title(self):
        """Пустой заголовок — не должен падать с исключением."""
        result = self._call(title="")
        self.assertIsInstance(result, str)


# ---------------------------------------------------------------------------
# get_form_responses
# ---------------------------------------------------------------------------

class TestGetFormResponses(BaseMCPTest):
    """Тесты для инструмента 4.1: get_form_responses."""

    def _call(self, form_id="form_12345", export_format="summary"):
        with patch("skills.elicitation_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod41.get_form_responses(
                form_id=form_id,
                export_format=export_format,
            )

    def test_summary_format(self):
        """Формат summary."""
        result = self._call(export_format="summary")
        self.assertIsInstance(result, str)

    def test_full_format(self):
        """Формат full."""
        result = self._call(export_format="full")
        self.assertIsInstance(result, str)

    def test_csv_format(self):
        """Формат csv."""
        result = self._call(export_format="csv")
        self.assertIsInstance(result, str)

    def test_empty_form_id(self):
        """Пустой form_id — функция не должна падать с исключением."""
        result = self._call(form_id="")
        self.assertIsInstance(result, str)

    def test_returns_string(self):
        """Всегда возвращает строку."""
        self.assertIsInstance(self._call(), str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
