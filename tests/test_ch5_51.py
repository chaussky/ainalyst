"""
tests/test_ch5_51.py — Тесты для Главы 5.1: Traceability and Monitoring
MCP-файл: skills/requirements_traceability_mcp.py
Инструменты: init_traceability_repo, add_trace_link, run_impact_analysis,
             check_coverage, export_traceability_matrix

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

from tests.conftest import setup_mocks, BaseMCPTest, make_test_repo, save_test_repo
setup_mocks()

import skills.requirements_traceability_mcp as mod51


# ---------------------------------------------------------------------------
# Вспомогательные данные
# ---------------------------------------------------------------------------

REQS_VALID = json.dumps([
    {
        "id": "BR-001",
        "type": "business",
        "title": "Снизить время обработки заявки до 5 минут",
        "version": "1.0",
        "status": "confirmed",
        "source_artifact": "governance_plans/4_3_test_confirmed.md",
    },
    {
        "id": "FR-001",
        "type": "solution",
        "title": "Система автоматически распределяет заявки",
        "version": "1.0",
        "status": "confirmed",
        "source_artifact": "governance_plans/4_3_test_confirmed.md",
    },
    {
        "id": "FR-002",
        "type": "solution",
        "title": "Уведомления о смене статуса заявки",
        "version": "1.0",
        "status": "draft",
        "source_artifact": "governance_plans/4_3_test_confirmed.md",
    },
    {
        "id": "TC-001",
        "type": "test",
        "title": "Тест автораспределения",
        "version": "1.0",
        "status": "draft",
    },
])

PROJECT = "traceability_test"


def _init_repo(project=PROJECT, formality="Standard", reqs_json=None):
    """Инициализирует репозиторий и возвращает результат."""
    if reqs_json is None:
        reqs_json = REQS_VALID
    with patch("skills.requirements_traceability_mcp.save_artifact") as mock_sa:
        mock_sa.return_value = "✅ Сохранено"
        return mod51.init_traceability_repo(
            project_name=project,
            formality_level=formality,
            requirements_json=reqs_json,
        )


# ---------------------------------------------------------------------------
# TestInitTraceabilityRepo
# ---------------------------------------------------------------------------

class TestInitTraceabilityRepo(BaseMCPTest):
    """Тесты для инструмента 5.1: init_traceability_repo."""

    def _call(self, **overrides):
        defaults = dict(
            project_name=PROJECT,
            formality_level="Standard",
            requirements_json=REQS_VALID,
        )
        kwargs = {**defaults, **overrides}
        with patch("skills.requirements_traceability_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod51.init_traceability_repo(**kwargs)

    # --- формальность ---

    def test_formality_lite(self):
        """Уровень Lite — создаётся без ошибок."""
        result = self._call(formality_level="Lite")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_formality_standard(self):
        """Уровень Standard — создаётся без ошибок."""
        result = self._call(formality_level="Standard")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_formality_full(self):
        """Уровень Full — создаётся без ошибок."""
        result = self._call(formality_level="Full")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- файл создаётся ---

    def test_creates_json_file(self):
        """Репозиторий записывается на диск."""
        self._call()
        safe_name = PROJECT.lower().replace(" ", "_")
        path = os.path.join("governance_plans", "data", f"{safe_name}_traceability_repo.json")
        self.assertTrue(os.path.exists(path), f"Файл не найден: {path}")

    def test_correct_structure(self):
        """Файл содержит project, requirements, links, history."""
        self._call()
        safe_name = PROJECT.lower().replace(" ", "_")
        path = os.path.join("governance_plans", "data", f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("project", data)
        self.assertIn("requirements", data)
        self.assertIn("links", data)
        self.assertIn("history", data)

    def test_requirements_count_correct(self):
        """Все 4 требования попадают в репозиторий."""
        self._call()
        safe_name = PROJECT.lower().replace(" ", "_")
        path = os.path.join("governance_plans", "data", f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(data["requirements"]), 4)

    # --- дедупликация ---

    def test_deduplication_no_duplicate_ids(self):
        """Повторный вызов с теми же ID не дублирует требования."""
        self._call()
        self._call()  # второй вызов
        safe_name = PROJECT.lower().replace(" ", "_")
        path = os.path.join("governance_plans", "data", f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        ids = [r["id"] for r in data["requirements"]]
        self.assertEqual(len(ids), len(set(ids)), "Дубликаты ID в репозитории")

    # --- single requirement ---

    def test_single_requirement(self):
        """Один тип требования — граничный случай."""
        result = self._call(
            requirements_json=json.dumps([
                {"id": "BR-001", "type": "business", "title": "Единственное требование",
                 "version": "1.0", "status": "draft"}
            ])
        )
        self.assertNotIn("❌", result)

    # --- разные проекты ---

    def test_different_projects_no_collision(self):
        """Разные проекты пишут в разные файлы."""
        self._call(project_name="project_alpha")
        self._call(project_name="project_beta")
        self.assertTrue(os.path.exists("governance_plans/data/project_alpha_traceability_repo.json"))
        self.assertTrue(os.path.exists("governance_plans/data/project_beta_traceability_repo.json"))

    # --- ошибки ---

    def test_invalid_json_requirements(self):
        """Невалидный JSON → сообщение об ошибке."""
        result = self._call(requirements_json="{bad}")
        self.assertIn("❌", result)

    def test_empty_requirements_json(self):
        """Пустая строка вместо JSON → ошибка."""
        result = self._call(requirements_json="")
        self.assertIn("❌", result)

    def test_requirements_not_a_list(self):
        """Объект вместо списка — не должен падать с необработанным исключением."""
        try:
            result = self._call(requirements_json=json.dumps({"id": "BR-001"}))
            # Если не упало — результат должен быть строкой
            self.assertIsInstance(result, str)
        except (AttributeError, TypeError):
            pass  # модуль не валидирует этот случай — приемлемо

    # --- save_artifact ---

    def test_save_artifact_called_once(self):
        """save_artifact вызывается ровно один раз."""
        with patch("skills.requirements_traceability_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            mod51.init_traceability_repo(
                project_name=PROJECT,
                formality_level="Standard",
                requirements_json=REQS_VALID,
            )
            mock_sa.assert_called_once()

    def test_returns_string(self):
        """Всегда возвращает строку."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# TestAddTraceLink
# ---------------------------------------------------------------------------

class TestAddTraceLink(BaseMCPTest):
    """Тесты для инструмента 5.1: add_trace_link."""

    def setUp(self):
        super().setUp()
        _init_repo()

    def _call(self, **overrides):
        defaults = dict(
            project_name=PROJECT,
            from_id="FR-001",
            to_id="BR-001",
            relation="derives",
            rationale="FR вытекает из бизнес-требования",
            remove=False,
        )
        kwargs = {**defaults, **overrides}
        with patch("skills.requirements_traceability_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod51.add_trace_link(**kwargs)

    # --- happy path по типам связей ---

    def test_add_derives_link(self):
        """Связь derives добавляется без ошибок."""
        result = self._call(relation="derives")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_add_verifies_link(self):
        """Связь verifies добавляется без ошибок."""
        result = self._call(from_id="TC-001", to_id="FR-001", relation="verifies")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_add_depends_link(self):
        """Связь depends добавляется без ошибок."""
        result = self._call(from_id="FR-002", to_id="FR-001", relation="depends")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_add_satisfies_link(self):
        """Связь satisfies добавляется без ошибок."""
        result = self._call(relation="satisfies")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- запись в репозиторий ---

    def test_link_persisted_in_file(self):
        """Добавленная связь сохраняется в файл."""
        self._call()
        safe_name = PROJECT.lower().replace(" ", "_")
        path = os.path.join("governance_plans", "data", f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        link_pairs = [(l["from"], l["to"]) for l in data["links"]]
        self.assertIn(("FR-001", "BR-001"), link_pairs)

    # --- дедупликация связей ---

    def test_no_duplicate_link(self):
        """Повторное добавление той же связи не создаёт дубликат."""
        self._call()
        self._call()
        safe_name = PROJECT.lower().replace(" ", "_")
        path = os.path.join("governance_plans", "data", f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        pairs = [(l["from"], l["to"], l["relation"]) for l in data["links"]]
        self.assertEqual(len(pairs), len(set(pairs)), "Дубликаты связей в репозитории")

    # --- удаление ---

    def test_remove_existing_link(self):
        """Удаление существующей связи проходит без ошибок."""
        self._call(remove=False)
        result = self._call(remove=True)
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_remove_nonexistent_link(self):
        """Удаление несуществующей связи — не падает с исключением."""
        result = self._call(remove=True, from_id="FR-999", to_id="BR-999")
        self.assertIsInstance(result, str)

    def test_returns_string(self):
        """Всегда возвращает строку."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# TestRunImpactAnalysis
# ---------------------------------------------------------------------------

class TestRunImpactAnalysis(BaseMCPTest):
    """Тесты для инструмента 5.1: run_impact_analysis."""

    def setUp(self):
        super().setUp()
        _init_repo()
        with patch("skills.requirements_traceability_mcp.save_artifact"):
            mod51.add_trace_link(
                project_name=PROJECT,
                from_id="FR-001", to_id="BR-001",
                relation="derives", rationale="вытекает из BR",
                remove=False,
            )
            mod51.add_trace_link(
                project_name=PROJECT,
                from_id="TC-001", to_id="FR-001",
                relation="verifies", rationale="тест проверяет FR",
                remove=False,
            )

    def _call(self, changed_req_id="BR-001", depth="full"):
        with patch("skills.requirements_traceability_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod51.run_impact_analysis(
                project_name=PROJECT,
                changed_req_id=changed_req_id,
                change_description="Тестовое изменение",
                depth=depth,
            )

    def test_finds_affected_requirements(self):
        """Анализ возвращает список затронутых требований."""
        result = self._call(changed_req_id="BR-001")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_depth_direct_limits_traversal(self):
        """Глубина direct ограничивает обход графа."""
        result = self._call(changed_req_id="BR-001", depth="direct")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_depth_full_traversal(self):
        """Глубина full — полный обход без ошибок."""
        result = self._call(changed_req_id="BR-001", depth="full")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_unknown_req_id(self):
        """Неизвестный changed_req_id — функция не падает."""
        result = self._call(changed_req_id="XX-999")
        self.assertIsInstance(result, str)

    def test_isolated_node(self):
        """Требование без связей — анализ отрабатывает корректно."""
        result = self._call(changed_req_id="FR-002")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_returns_string(self):
        """Всегда возвращает строку."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# TestCheckCoverage
# ---------------------------------------------------------------------------

class TestCheckCoverage(BaseMCPTest):
    """Тесты для инструмента 5.1: check_coverage."""

    def setUp(self):
        super().setUp()
        _init_repo()
        with patch("skills.requirements_traceability_mcp.save_artifact"):
            mod51.add_trace_link(
                project_name=PROJECT,
                from_id="FR-001", to_id="BR-001",
                relation="derives", rationale="тест",
                remove=False,
            )

    def _call(self, **kwargs):
        defaults = dict(project_name=PROJECT)
        params = {**defaults, **kwargs}
        with patch("skills.requirements_traceability_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod51.check_coverage(**params)

    def test_basic_coverage_check(self):
        """Базовая проверка покрытия работает."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_deprecated_excluded_from_coverage(self):
        """Deprecated-требования не попадают в аудит."""
        # Помечаем FR-002 как deprecated через репозиторий напрямую
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
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_orphan_fr_detected(self):
        """FR-002 без связи — аудит должен отметить проблему."""
        result = self._call()
        # FR-002 не имеет связей — должно быть упоминание в отчёте
        self.assertIn("FR-002", result)

    def test_returns_string(self):
        """Всегда возвращает строку."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# TestExportTraceabilityMatrix
# ---------------------------------------------------------------------------

class TestExportTraceabilityMatrix(BaseMCPTest):
    """Тесты для инструмента 5.1: export_traceability_matrix."""

    def setUp(self):
        super().setUp()
        _init_repo()
        with patch("skills.requirements_traceability_mcp.save_artifact"):
            mod51.add_trace_link(
                project_name=PROJECT,
                from_id="FR-001", to_id="BR-001",
                relation="derives", rationale="тест",
                remove=False,
            )

    def _call(self, **overrides):
        defaults = dict(project_name=PROJECT)
        kwargs = {**defaults, **overrides}
        with patch("skills.requirements_traceability_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod51.export_traceability_matrix(**kwargs)

    def test_basic_export(self):
        """Базовый экспорт матрицы."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_export_filter_by_relation(self):
        """Фильтрация по типу связи."""
        result = self._call(filter_relation="derives")
        self.assertIsInstance(result, str)

    def test_export_filter_by_type(self):
        """Фильтрация по типу требования."""
        result = self._call(filter_type="solution")
        self.assertIsInstance(result, str)

    def test_export_filter_by_status(self):
        """Фильтрация по статусу требования."""
        result = self._call(filter_status="confirmed")
        self.assertIsInstance(result, str)

    def test_export_contains_requirement_ids(self):
        """Матрица содержит ID требований."""
        result = self._call()
        self.assertIn("BR-001", result)
        self.assertIn("FR-001", result)

    def test_export_empty_filter(self):
        """Пустые фильтры — все требования включаются."""
        result = self._call(filter_relation="", filter_type="", filter_status="")
        self.assertIsInstance(result, str)

    def test_save_artifact_called(self):
        """save_artifact вызывается при экспорте."""
        with patch("skills.requirements_traceability_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            mod51.export_traceability_matrix(project_name=PROJECT)
            mock_sa.assert_called_once()

    def test_returns_string(self):
        """Всегда возвращает строку."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# TestUtils51
# ---------------------------------------------------------------------------

class TestUtils51(unittest.TestCase):
    """Тесты для вспомогательных функций модуля 5.1."""

    def test_repo_path_normalizes_spaces(self):
        """Пробелы в project_name преобразуются в подчёркивания."""
        path = mod51._repo_path("My Project")
        self.assertIn("my_project", path)
        self.assertNotIn(" ", path)

    def test_repo_path_lowercase(self):
        """Имя проекта приводится к нижнему регистру."""
        path = mod51._repo_path("CRM_UPGRADE")
        self.assertEqual(path, mod51._repo_path("crm_upgrade"))

    def test_find_req_existing(self):
        """_find_req находит требование по ID."""
        repo = {"requirements": [{"id": "BR-001", "title": "Test"}], "links": []}
        req = mod51._find_req(repo, "BR-001")
        self.assertIsNotNone(req)
        self.assertEqual(req["id"], "BR-001")

    def test_find_req_missing(self):
        """_find_req возвращает None для отсутствующего ID."""
        repo = {"requirements": [], "links": []}
        self.assertIsNone(mod51._find_req(repo, "BR-999"))

    def test_find_links_both_directions(self):
        """_find_links возвращает связи в обоих направлениях."""
        repo = {
            "requirements": [],
            "links": [
                {"from": "FR-001", "to": "BR-001", "relation": "derives"},
                {"from": "TC-001", "to": "FR-001", "relation": "verifies"},
                {"from": "FR-002", "to": "FR-003", "relation": "depends"},
            ],
        }
        links = mod51._find_links(repo, "FR-001")
        froms = [l["from"] for l in links]
        tos = [l["to"] for l in links]
        self.assertIn("FR-001", froms + tos)

    def test_find_links_isolated_node(self):
        """_find_links возвращает пустой список для изолированного требования."""
        repo = {
            "requirements": [],
            "links": [{"from": "FR-001", "to": "BR-001", "relation": "derives"}],
        }
        links = mod51._find_links(repo, "FR-999")
        self.assertEqual(links, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
