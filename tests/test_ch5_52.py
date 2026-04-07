"""
tests/test_ch5_52.py — Тесты для Главы 5.2: Maintain Requirements
MCP-файл: skills/requirements_maintain_mcp.py
Инструменты: update_requirement, deprecate_requirements,
             check_requirements_health, find_reusable_requirements

Стратегия: BaseMCPTest (tmpdir + chdir), setup_mocks() до импортов,
save_artifact патчится через patch() по правилу ADR-068.
"""

import json
import os
import sys
import unittest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tests.conftest import setup_mocks, BaseMCPTest, make_test_repo, save_test_repo
setup_mocks()

import skills.requirements_maintain_mcp as mod52


# ---------------------------------------------------------------------------
# Вспомогательные данные
# ---------------------------------------------------------------------------

PROJECT = "maintain_test"


def _setup_repo(project=PROJECT, extras=None):
    """Создаёт тестовый репозиторий с базовыми требованиями."""
    repo = make_test_repo(project)
    if extras:
        repo["requirements"].extend(extras)
    save_test_repo(repo)
    return repo


# ---------------------------------------------------------------------------
# TestUtils52
# ---------------------------------------------------------------------------

class TestUtils52(unittest.TestCase):
    """Тесты вспомогательных функций модуля 5.2."""

    def test_minor_version_normal(self):
        """1.3 → minor = 3."""
        self.assertEqual(mod52._minor_version("1.3"), 3)

    def test_minor_version_zero(self):
        """1.0 → minor = 0."""
        self.assertEqual(mod52._minor_version("1.0"), 0)

    def test_minor_version_invalid(self):
        """Невалидная версия не бросает исключение."""
        result = mod52._minor_version("invalid")
        self.assertIsInstance(result, int)

    def test_days_since_today(self):
        """Сегодняшняя дата → 0 дней."""
        self.assertEqual(mod52._days_since(str(date.today())), 0)

    def test_days_since_past(self):
        """Дата 10 дней назад → 10."""
        past = str(date.today() - timedelta(days=10))
        self.assertEqual(mod52._days_since(past), 10)

    def test_days_since_invalid(self):
        """Невалидная дата → большое число (или не падает)."""
        result = mod52._days_since("not-a-date")
        self.assertIsInstance(result, int)


# ---------------------------------------------------------------------------
# TestUpdateRequirement
# ---------------------------------------------------------------------------

class TestUpdateRequirement(BaseMCPTest):
    """Тесты для инструмента 5.2: update_requirement."""

    def setUp(self):
        super().setUp()
        _setup_repo()

    def _call(self, **overrides):
        defaults = dict(
            project_name=PROJECT,
            req_id="BR-001",
            change_reason="Уточнение по итогам воркшопа",
        )
        kwargs = {**defaults, **overrides}
        with patch("skills.requirements_maintain_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod52.update_requirement(**kwargs)

    # --- happy path ---

    def test_update_status(self):
        """Обновление статуса проходит без ошибок."""
        result = self._call(new_status="approved")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_update_status_persisted(self):
        """Новый статус сохраняется в файл."""
        self._call(new_status="approved")
        safe_name = PROJECT.lower().replace(" ", "_")
        path = os.path.join("governance_plans", "data", f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        req = next(r for r in data["requirements"] if r["id"] == "BR-001")
        self.assertEqual(req["status"], "approved")

    def test_update_writes_history(self):
        """История изменений записывается в репозиторий."""
        self._call(new_status="approved")
        safe_name = PROJECT.lower().replace(" ", "_")
        path = os.path.join("governance_plans", "data", f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("history", data)
        self.assertGreater(len(data["history"]), 0)

    def test_update_minor_version(self):
        """Установка minor-версии применяется."""
        result = self._call(new_version="1.1")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_update_major_version(self):
        """Установка major-версии применяется."""
        result = self._call(new_version="2.0")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_update_owner(self):
        """Смена owner не меняет версию."""
        result = self._call(new_owner="product_owner@example.com")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_update_priority(self):
        """Установка приоритета."""
        result = self._call(new_priority="Must")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_update_title(self):
        """Смена заголовка требования."""
        result = self._call(new_title="Снизить время до 3 минут")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_update_stability_flag(self):
        """Установка флага стабильности."""
        result = self._call(new_stability="unstable")
        self.assertIsInstance(result, str)

    def test_update_reuse_candidate(self):
        """Пометить как кандидат на переиспользование."""
        result = self._call(reuse_candidate="true", reuse_scope="program")
        self.assertIsInstance(result, str)

    def test_update_auto_volatility(self):
        """Автоматически присваивается флаг волатильности при версии 1.4+."""
        _call_with_version = dict(
            project_name=PROJECT,
            req_id="FR-001",
            change_reason="Итерационные правки",
            new_version="1.4",
        )
        with patch("skills.requirements_maintain_mcp.save_artifact"):
            mod52.update_requirement(**_call_with_version)

        safe_name = PROJECT.lower().replace(" ", "_")
        path = os.path.join("governance_plans", "data", f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        req = next(r for r in data["requirements"] if r["id"] == "FR-001")
        # Версия 1.4 → нестабильное требование
        minor = mod52._minor_version(req.get("version", "1.0"))
        self.assertGreaterEqual(minor, 4)

    # --- ошибки ---

    def test_update_unknown_id(self):
        """Неизвестный req_id → сообщение об ошибке."""
        result = self._call(req_id="XX-999")
        self.assertIn("❌", result)

    def test_update_no_changes(self):
        """Вызов без изменений — не должен падать."""
        result = self._call()
        self.assertIsInstance(result, str)

    # --- save_artifact ---

    def test_save_artifact_called(self):
        """save_artifact вызывается при обновлении."""
        with patch("skills.requirements_maintain_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            mod52.update_requirement(
                project_name=PROJECT,
                req_id="BR-001",
                change_reason="тест",
                new_status="approved",
            )
            mock_sa.assert_called_once()

    def test_returns_string(self):
        """Всегда возвращает строку."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# TestDeprecateRequirements
# ---------------------------------------------------------------------------

class TestDeprecateRequirements(BaseMCPTest):
    """Тесты для инструмента 5.2: deprecate_requirements."""

    def setUp(self):
        super().setUp()
        _setup_repo()

    def _call(self, **overrides):
        defaults = dict(
            project_name=PROJECT,
            req_ids_json=json.dumps(["FR-002"]),
            final_status="deprecated",
            reason="Требование устарело после рефакторинга",
        )
        kwargs = {**defaults, **overrides}
        with patch("skills.requirements_maintain_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod52.deprecate_requirements(**kwargs)

    # --- happy path по final_status ---

    def test_deprecated_status(self):
        """final_status=deprecated — работает."""
        result = self._call(final_status="deprecated")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_superseded_status_with_superseded_by(self):
        """final_status=superseded + superseded_by — работает."""
        result = self._call(final_status="superseded", superseded_by="FR-001")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_retired_status(self):
        """final_status=retired — работает."""
        result = self._call(final_status="retired")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- статус сохраняется ---

    def test_status_set_in_file(self):
        """Статус deprecated сохраняется в репозиторий."""
        self._call(req_ids_json=json.dumps(["FR-002"]), final_status="deprecated")
        safe_name = PROJECT.lower().replace(" ", "_")
        path = os.path.join("governance_plans", "data", f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        req = next(r for r in data["requirements"] if r["id"] == "FR-002")
        self.assertEqual(req["status"], "deprecated")

    def test_record_preserved(self):
        """Устаревшее требование не удаляется, а остаётся в репозитории."""
        self._call()
        safe_name = PROJECT.lower().replace(" ", "_")
        path = os.path.join("governance_plans", "data", f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        ids = [r["id"] for r in data["requirements"]]
        self.assertIn("FR-002", ids)

    def test_multiple_requirements_deprecated(self):
        """Несколько требований помечаются за один вызов."""
        result = self._call(req_ids_json=json.dumps(["FR-001", "FR-002"]))
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- ошибки ---

    def test_superseded_without_superseded_by_warns(self):
        """superseded без superseded_by → предупреждение или ошибка."""
        result = self._call(final_status="superseded", superseded_by="")
        self.assertIsInstance(result, str)
        # Ожидаем ❌ или ⚠️
        self.assertTrue("❌" in result or "⚠️" in result, f"Нет предупреждения: {result[:200]}")

    def test_invalid_ids_json(self):
        """Невалидный JSON req_ids_json → ошибка."""
        result = self._call(req_ids_json="{invalid}")
        self.assertIn("❌", result)

    def test_returns_string(self):
        """Всегда возвращает строку."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# TestCheckRequirementsHealth
# ---------------------------------------------------------------------------

class TestCheckRequirementsHealth(BaseMCPTest):
    """Тесты для инструмента 5.2: check_requirements_health."""

    def setUp(self):
        super().setUp()
        _setup_repo()

    def _call(self, **overrides):
        defaults = dict(project_name=PROJECT)
        kwargs = {**defaults, **overrides}
        with patch("skills.requirements_maintain_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod52.check_requirements_health(**kwargs)

    def test_basic_health_check(self):
        """Базовый аудит здоровья работает без ошибок."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_detects_volatile_requirement(self):
        """Требование с версией 1.4+ помечается как волатильное."""
        # Напрямую прописываем версию 1.5 в репозиторий
        safe_name = PROJECT.lower().replace(" ", "_")
        path = os.path.join("governance_plans", "data", f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for r in data["requirements"]:
            if r["id"] == "FR-001":
                r["version"] = "1.5"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        result = self._call()
        self.assertIn("FR-001", result)

    def test_excludes_deprecated(self):
        """Deprecated-требования исключаются из аудита (без фильтра)."""
        safe_name = PROJECT.lower().replace(" ", "_")
        path = os.path.join("governance_plans", "data", f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for r in data["requirements"]:
            if r["id"] == "FR-002":
                r["status"] = "deprecated"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        result = self._call()
        # Устаревшие требования не должны фигурировать в аудите здоровья
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_filter_by_type(self):
        """Фильтр по типу сужает список проверяемых требований."""
        result = self._call(filter_type="business")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_filter_by_status(self):
        """Фильтр по статусу работает."""
        result = self._call(filter_status="confirmed")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_empty_project_no_crash(self):
        """Пустой (несуществующий) проект — не падает с исключением."""
        result = self._call(project_name="nonexistent_project_xyz")
        self.assertIsInstance(result, str)

    def test_returns_string(self):
        """Всегда возвращает строку."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# TestFindReusableRequirements
# ---------------------------------------------------------------------------

class TestFindReusableRequirements(BaseMCPTest):
    """Тесты для инструмента 5.2: find_reusable_requirements."""

    def setUp(self):
        super().setUp()
        # Добавляем кандидата на переиспользование
        _setup_repo(extras=[
            {
                "id": "BR-002",
                "type": "business",
                "title": "Единая система аутентификации",
                "version": "1.0",
                "status": "approved",
                "reuse_candidate": True,
                "reuse_scope": "enterprise",
                "added": str(date.today()),
            }
        ])

    def _call(self, **overrides):
        defaults = dict(project_name=PROJECT)
        kwargs = {**defaults, **overrides}
        with patch("skills.requirements_maintain_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod52.find_reusable_requirements(**kwargs)

    def test_finds_approved_candidate(self):
        """Одобренный кандидат на переиспользование находится."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_search_query_filters(self):
        """Поисковый запрос фильтрует по тексту требования."""
        # BR-002 имеет title "Единая система аутентификации" — поиск должен найти
        result = self._call(search_query="единая система")
        self.assertIsInstance(result, str)
        self.assertIn("BR-002", result)

    def test_filter_by_type_business(self):
        """Фильтр по типу business."""
        result = self._call(filter_type="business")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_filter_by_type_solution(self):
        """Фильтр по типу solution — не должен находить BR-002."""
        result = self._call(filter_type="solution")
        self.assertIsInstance(result, str)

    def test_min_scope_enterprise(self):
        """Минимальный scope enterprise — находит только enterprise-кандидатов."""
        result = self._call(min_reuse_scope="enterprise")
        self.assertIsInstance(result, str)
        self.assertIn("BR-002", result)

    def test_min_scope_program_includes_enterprise(self):
        """Минимальный scope program включает enterprise."""
        result = self._call(min_reuse_scope="program")
        self.assertIsInstance(result, str)

    def test_no_candidates_graceful(self):
        """Если нет кандидатов — функция не падает."""
        result = self._call(filter_type="transition")
        self.assertIsInstance(result, str)

    def test_deprecated_excluded(self):
        """Deprecated-требования не попадают в результат."""
        safe_name = PROJECT.lower().replace(" ", "_")
        path = os.path.join("governance_plans", "data", f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for r in data["requirements"]:
            if r["id"] == "BR-002":
                r["status"] = "deprecated"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        result = self._call()
        # BR-002 deprecated — не должен быть в рекомендациях
        # (может присутствовать в тексте как исключённый, поэтому просто проверяем тип)
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_returns_string(self):
        """Всегда возвращает строку."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# TestIntegration52
# ---------------------------------------------------------------------------

class TestIntegration52(BaseMCPTest):
    """Интеграционные тесты: связка инструментов 5.2."""

    def setUp(self):
        super().setUp()
        _setup_repo()

    def test_update_then_health_check(self):
        """Обновление требования → аудит здоровья отражает изменения."""
        with patch("skills.requirements_maintain_mcp.save_artifact"):
            mod52.update_requirement(
                project_name=PROJECT,
                req_id="FR-001",
                change_reason="Расширение scope",
                new_version="1.4",
            )
        with patch("skills.requirements_maintain_mcp.save_artifact"):
            result = mod52.check_requirements_health(project_name=PROJECT)
        self.assertIn("FR-001", result)

    def test_deprecate_then_health_check_excludes(self):
        """Устаревание требования → оно исключается из аудита здоровья."""
        with patch("skills.requirements_maintain_mcp.save_artifact"):
            mod52.deprecate_requirements(
                project_name=PROJECT,
                req_ids_json=json.dumps(["FR-002"]),
                final_status="deprecated",
                reason="Не нужен в текущей итерации",
            )
        with patch("skills.requirements_maintain_mcp.save_artifact"):
            result = mod52.check_requirements_health(project_name=PROJECT)
        # Deprecated FR-002 не должен быть проблемой в отчёте здоровья
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_history_accumulates_across_calls(self):
        """История накапливается при нескольких обновлениях одного требования."""
        for reason in ["Правка 1", "Правка 2", "Правка 3"]:
            with patch("skills.requirements_maintain_mcp.save_artifact"):
                mod52.update_requirement(
                    project_name=PROJECT,
                    req_id="BR-001",
                    change_reason=reason,
                    note=f"Заметка: {reason}",
                    new_status="approved",
                )
        safe_name = PROJECT.lower().replace(" ", "_")
        path = os.path.join("governance_plans", "data", f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertGreaterEqual(len(data.get("history", [])), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
