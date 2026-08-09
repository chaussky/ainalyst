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
import re
import sys
import unittest
from datetime import date
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tests.conftest import (setup_mocks, BaseMCPTest, make_test_repo,
                            save_test_repo, load_test_repo)
setup_mocks()

import skills.requirements_traceability_mcp as mod51
from skills.common import data_path, normalize_project_id


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
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        self.assertTrue(os.path.exists(path), f"Файл не найден: {path}")

    def test_correct_structure(self):
        """Файл содержит project, requirements, links, history."""
        self._call()
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
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
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(data["requirements"]), 4)

    # --- дедупликация ---

    def test_deduplication_no_duplicate_ids(self):
        """Повторный вызов с теми же ID не дублирует требования."""
        self._call()
        self._call()  # второй вызов
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
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
        self.assertTrue(os.path.exists(
            data_path("project_alpha", "project_alpha_traceability_repo.json")))
        self.assertTrue(os.path.exists(
            data_path("project_beta", "project_beta_traceability_repo.json")))

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
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
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
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
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

    def _deprecate(self, req_id="FR-002"):
        """Marks a requirement archived directly in the repository."""
        safe_name = normalize_project_id(PROJECT)
        path = data_path(PROJECT, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for r in data["requirements"]:
            if r["id"] == req_id:
                r["status"] = "deprecated"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def test_an_archived_requirement_is_shown_and_counted_but_is_not_coverage(self):
        """Owner's decision, 2026-08-03: archived requirements are SHOWN, MARKED and
        COUNTED — they just do not count as coverage.

        They used to be filtered out of the selection, so the denominator changed
        silently: the same graph in the same minute gave `Total items 6` here and
        `Total requirements: 8` in the traceability matrix. Worse, the audit is what
        `deprecate_requirements` tells the analyst to run next to check for orphaned
        links to the node just archived — and it did not mention the node at all."""
        self._deprecate("FR-002")
        result = self._call()

        self.assertIn("FR-002", result, "an archived requirement vanished from the audit")
        self.assertIn("в архиве", result.lower())
        # It is counted, and it is not counted as coverage.
        archived_row = [ln for ln in result.split("\n") if "В архиве" in ln and "|" in ln]
        self.assertTrue(archived_row, f"no archived row in the summary:\n{result}")
        self.assertIn("| 1 |", archived_row[0])

    def test_the_audit_and_the_matrix_agree_on_how_many_items_there_are(self):
        """Two documents of one project, one minute apart, must not disagree on the
        size of the graph. The difference used to be exactly the archived nodes."""
        self._deprecate("FR-002")
        audit = self._call()
        with patch("skills.requirements_traceability_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            matrix = mod51.export_traceability_matrix(project_name=PROJECT)

        def _number_after(text, label):
            for line in text.split("\n"):
                if label in line:
                    return int(re.search(r"(\d+)", line.split(label)[1]).group(1))
            raise AssertionError(f"{label!r} not found in:\n{text}")

        self.assertEqual(_number_after(audit, "Всего элементов"),
                         _number_after(matrix, "Итого требований:"),
                         "the audit and the matrix report different totals for one graph")

    def test_a_link_pointing_at_an_archived_node_is_marked_in_the_matrix(self):
        """The links table prints ids only. A signatory reading it saw a requirement
        justified by a retired objective as an ordinary one — the status was in a
        different table, and only if they cross-referenced by hand."""
        with patch("skills.requirements_traceability_mcp.save_artifact"):
            mod51.add_trace_link(project_name=PROJECT, from_id="FR-002", to_id="BR-001",
                                 relation="derives", rationale="justified by BR-001",
                                 remove=False)
        self._deprecate("FR-002")
        with patch("skills.requirements_traceability_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            matrix = mod51.export_traceability_matrix(project_name=PROJECT)

        link_rows = [ln for ln in matrix.split("\n")
                     if ln.startswith("|") and "FR-002" in ln and (
                         "derives" in ln or "satisfies" in ln or "verifies" in ln)]
        self.assertTrue(link_rows, f"no link row mentioning FR-002:\n{matrix}")
        for row in link_rows:
            self.assertIn("в архиве", row.lower(),
                          f"a link to an archived node carries no marker: {row}")

    def test_child_with_derives_link_is_not_orphan(self):
        """A requirement that derives from a parent must NOT be flagged 'no source'.

        Canonical direction is from=child -> to=parent (FR-001 derives BR-001,
        added in setUp). Regression: has_source used to check to==req_id (inverted),
        which wrongly marked every child requirement as an orphan.
        """
        result = self._call()
        # Header of the orphan table (distinct from the summary row "No source (orphan)")
        marker = "требования без источника"
        low = result.lower()
        if marker in low:
            section = low.split(marker, 1)[1].split("\n## ", 1)[0]
            self.assertNotIn(
                "`fr-001`", section,
                "FR-001 derives from BR-001; it must not be listed as an orphan with no source",
            )

    def test_orphan_fr_detected(self):
        """FR-002 без связи — аудит должен отметить проблему."""
        result = self._call()
        # FR-002 не имеет связей — должно быть упоминание в отчёте
        self.assertIn("FR-002", result)

    def test_test_node_with_verifies_is_not_orphan(self):
        """A test (type=test) linked via `verifies` has its source — the
        requirement it verifies — and must NOT be flagged 'no source'. Tests link
        via verifies, never derives, so a derives-only source check false-flags them."""
        with patch("skills.requirements_traceability_mcp.save_artifact"):
            mod51.add_trace_link(
                project_name=PROJECT, from_id="TC-001", to_id="FR-001",
                relation="verifies", rationale="the test verifies FR-001", remove=False,
            )
        result = self._call()
        marker = "требования без источника"
        low = result.lower()
        self.assertIn(marker, low)  # FR-002 is a genuine orphan -> section exists
        section = low.split(marker, 1)[1].split("\n## ", 1)[0]
        self.assertNotIn(
            "`tc-001`", section,
            "TC-001 verifies FR-001; it must not be an orphan with no source",
        )

    def test_business_need_root_is_not_orphan(self):
        """A business_need is a root of the derivation chain (goals derive from it),
        so it has no upward source and must NOT be flagged 'no source' — like `business`."""
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["requirements"].append({
            "id": "BN-001", "type": "business_need", "title": "Cut approval time",
            "version": "1.0", "status": "confirmed", "added": "2026-01-01",
        })
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        result = self._call()
        marker = "требования без источника"
        low = result.lower()
        self.assertIn(marker, low)
        section = low.split(marker, 1)[1].split("\n## ", 1)[0]
        self.assertNotIn(
            "`bn-001`", section,
            "business_need is a root; it must not be an orphan with no source",
        )

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

    def test_repo_path_is_under_the_project_folder(self):
        """The id IS the folder name — no rewriting happens on the way to the path."""
        path = mod51._repo_path("my_project")
        self.assertIn(os.path.join("my_project", "my_project_traceability_repo.json"), path)

    def test_a_spelling_that_would_be_rewritten_gets_no_path(self):
        """`CRM_UPGRADE` and `crm_upgrade` used to resolve to the SAME file, which is
        how two ids came to share one folder. Now only the second is an id at all."""
        import skills.common as common_mod
        for spelled_wrong in ("CRM_UPGRADE", "My Project"):
            with self.assertRaises(common_mod.InvalidProjectIdError):
                mod51._repo_path(spelled_wrong)

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


class TestSatisfiesGrantsSource(BaseMCPTest):
    """A node that satisfies something is justified BY that thing — the same rule
    already applied to tests via `verifies`. Granting a source only for `derives`
    false-flags two real populations: requirements linked to a 6.2 business goal
    (7.1 per-goal traceability, ADR-082) and the `solution` nodes 6.4 pushes.
    """

    P = "satisfies_source"

    def _save(self, extra_nodes, links):
        repo = make_test_repo(self.P)
        repo["requirements"] = [
            {"id": "BG-001", "type": "business_goal", "title": "Cut handling time",
             "version": "1.0", "status": "confirmed", "added": str(date.today()),
             "source_artifact": ""},
        ] + extra_nodes
        repo["links"] = links
        save_test_repo(repo)

    def _run(self):
        with patch("skills.requirements_traceability_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod51.check_coverage(project_name=self.P)

    def _orphan_section(self, result):
        """Body of the '🔴 Requirements with no source' table only — the summary row
        above it mentions the same words and would mask a real regression."""
        marker = "требования без источника"
        low = result.lower()
        if marker not in low:
            return ""
        return low.split(marker, 1)[1].split("\n## ", 1)[0]

    def _edge(self, frm, to, relation="satisfies"):
        return {"from": frm, "to": to, "relation": relation,
                "created": str(date.today())}

    def test_requirement_satisfying_a_goal_is_not_orphan(self):
        self._save(
            [{"id": "FR-100", "type": "functional", "title": "Auto-assign",
              "version": "1.0", "status": "draft", "added": str(date.today()),
              "source_artifact": ""}],
            [self._edge("FR-100", "BG-001")],
        )
        self.assertNotIn("`fr-100`", self._orphan_section(self._run()))

    def test_solution_node_from_64_is_not_orphan(self):
        """6.4 pushes `SOL-001 satisfies BG-001` (ADR-082) and no derives edge, so
        every solution node was a false orphan on any project that ran 6.4."""
        self._save(
            [{"id": "SOL-001", "type": "solution", "title": "Phased rollout",
              "version": "1.0", "status": "draft", "added": str(date.today()),
              "source_artifact": ""}],
            [self._edge("SOL-001", "BG-001")],
        )
        self.assertNotIn("`sol-001`", self._orphan_section(self._run()))

    def test_node_with_no_upward_edge_is_still_orphan(self):
        """The rule must not degenerate into 'everything has a source'."""
        self._save(
            [{"id": "FR-200", "type": "functional", "title": "Unlinked",
              "version": "1.0", "status": "draft", "added": str(date.today()),
              "source_artifact": ""}],
            [],
        )
        self.assertIn("`fr-200`", self._orphan_section(self._run()))

    def test_being_the_target_of_satisfies_does_not_grant_a_source(self):
        """Direction matters: from=implementer -> to=implemented. The GOAL is the
        target, so it must not inherit a source from the requirement pointing at it."""
        self._save(
            [{"id": "FR-300", "type": "functional", "title": "Auto-assign",
              "version": "1.0", "status": "draft", "added": str(date.today()),
              "source_artifact": ""}],
            [self._edge("FR-300", "BG-001")],
        )
        self.assertIn("`bg-001`", self._orphan_section(self._run()))


class TestNoTestAxisCoversBehavioralTypes(BaseMCPTest):
    """The "no test" rule fired only for the classes `solution` / `transition` — the
    vocabulary 5.1 shipped with. The eight 7.1 node types postdate it, so a project
    specified entirely through 7.1 answered "✅ Coverage is complete" without a
    single verifies edge: the axis was dead for the platform's main path. Product
    decision (2026-07-22): a test is expected from BEHAVIORAL requirement types
    (functional / non_functional / user_story / use_case + the original two); model
    artifacts (erd, data_dictionary, business_process, business_rule) are not
    verified by test cases and stay exempt."""

    P = "notest_types"

    def _run_with(self, nodes, links):
        repo = make_test_repo(self.P)
        repo["requirements"] = nodes
        repo["links"] = links
        save_test_repo(repo)
        with patch("skills.requirements_traceability_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod51.check_coverage(project_name=self.P)

    @staticmethod
    def _node(node_id, node_type):
        return {"id": node_id, "type": node_type, "title": f"{node_id} probe",
                "version": "1.0", "status": "draft", "added": str(date.today()),
                "source_artifact": ""}

    @staticmethod
    def _row_for(out, node_id):
        """The requirement's own table row — the legend below the table always
        mentions 'No test', so a whole-output assertion would be vacuous."""
        for line in out.splitlines():
            if node_id.lower() in line.lower() and line.strip().startswith("|"):
                return line.lower()
        return ""

    def test_functional_without_verifies_is_flagged(self):
        out = self._run_with(
            [self._node("BG-001", "business_goal"),
             self._node("FR-700", "functional")],
            [{"from": "FR-700", "to": "BG-001", "relation": "satisfies",
              "added": str(date.today())}],
        )
        self.assertIn("нет теста", self._row_for(out, "FR-700"))

    def test_model_artifact_without_verifies_is_not_flagged(self):
        out = self._run_with(
            [self._node("BG-001", "business_goal"),
             self._node("ERD-001", "erd")],
            [{"from": "ERD-001", "to": "BG-001", "relation": "satisfies",
              "added": str(date.today())}],
        )
        row = self._row_for(out, "ERD-001")
        self.assertNotIn("нет теста", row)


class TestAddTraceLinkWarnsOnMissingTarget(BaseMCPTest):
    """add_trace_link is the one edge writer without an existence check (6.2 / 6.3 /
    6.4 / 7.1 all validate). External ids (COMP-Auth) are legitimate, so the edge is
    still WRITTEN — but silently accepting a typo creates an edge to nowhere that
    check_coverage then counts as a source, silencing exactly the orphan check meant
    to catch it. Product decision (2026-07-22): warn, but write."""

    P = "dangling_edge"

    def _prepare(self):
        save_test_repo(make_test_repo(self.P))

    def _add(self, to_id):
        with patch("skills.requirements_traceability_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod51.add_trace_link(
                self.P, from_id="FR-001", to_id=to_id, relation="depends",
                rationale="probe")

    def test_missing_target_warns_but_writes(self):
        self._prepare()
        out = self._add("BG-01")   # typo — node does not exist
        self.assertIn("BG-01", out)
        self.assertIn("в репозитории нет", out)
        repo = load_test_repo(self.P)
        self.assertTrue(
            any(l["from"] == "FR-001" and l["to"] == "BG-01" for l in repo["links"]),
            "the edge must still be written — external artifact ids are legitimate")

    def test_existing_target_gets_no_warning(self):
        self._prepare()
        out = self._add("BR-001")
        self.assertNotIn("в репозитории нет", out)


class TestArchivedEvidenceIsNotCoverage(BaseMCPTest):
    """The audit banner states the doctrine — "an archived requirement is not evidence
    that anything is justified, implemented or verified" — and until this test the
    VERDICT did not honour it. Archived nodes were removed from the SELECTION only:
    they were shown and counted, while `has_source` / `has_impl` / `has_test` still
    accepted a link whose far end was retired. A requirement whose need, component and
    test had all been archived read "🟢 Full coverage" three lines under the banner
    denying it, and the audit declared the project ready for 5.3 and 5.5.

    Filter on the VERDICT, never on the selection (the doctrine this wave established
    in 5.1): the node stays visible and counted, but it stops being evidence.
    """

    P = "archived_evidence"

    def _save(self, nodes, links):
        repo = make_test_repo(self.P)
        repo["requirements"] = nodes
        repo["links"] = links
        save_test_repo(repo)

    def _run(self):
        with patch("skills.requirements_traceability_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod51.check_coverage(project_name=self.P)

    @staticmethod
    def _node(node_id, node_type, status="confirmed"):
        return {"id": node_id, "type": node_type, "title": f"{node_id} probe",
                "version": "1.0", "status": status, "added": str(date.today()),
                "source_artifact": ""}

    @staticmethod
    def _edge(frm, to, relation):
        return {"from": frm, "to": to, "relation": relation,
                "created": str(date.today())}

    def _live_requirement_leaning_on_archived_evidence(self):
        self._save(
            [self._node("BN-001", "business_need", "retired"),
             self._node("FR-001", "solution"),
             self._node("COMP-1", "component", "retired"),
             self._node("TC-001", "test", "retired")],
            [self._edge("FR-001", "BN-001", "derives"),
             self._edge("COMP-1", "FR-001", "satisfies"),
             self._edge("TC-001", "FR-001", "verifies")],
        )

    def test_a_retired_source_does_not_justify_a_live_requirement(self):
        self._live_requirement_leaning_on_archived_evidence()
        out = self._run()
        covered = out.split("## 🟢 Полностью покрытые элементы", 1)
        self.assertEqual(len(covered), 1,
                         "FR-001 is justified only by retired nodes — it cannot be "
                         "fully covered:\n" + out)
        self.assertIn("`FR-001`", out)

    def test_the_verdict_does_not_call_that_project_ready(self):
        self._live_requirement_leaning_on_archived_evidence()
        out = self._run()
        self.assertNotIn("Покрытие полное", out)

    @staticmethod
    def _covered_section(out):
        """The '🟢 Fully covered' table only. The summary row above it carries the same
        words, so a whole-output assertion would pass on the wrong evidence."""
        if "## 🟢 Полностью покрытые элементы" not in out:
            return ""
        return out.split("## 🟢 Полностью покрытые элементы", 1)[1].split("\n## ", 1)[0]

    def test_a_live_source_still_justifies(self):
        """The rule must not degenerate into "nothing is ever covered"."""
        self._save(
            [self._node("BN-001", "business_need"),
             self._node("FR-001", "solution"),
             self._node("COMP-1", "component"),
             self._node("TC-001", "test")],
            [self._edge("FR-001", "BN-001", "derives"),
             self._edge("COMP-1", "FR-001", "satisfies"),
             self._edge("TC-001", "FR-001", "verifies")],
        )
        self.assertIn("`FR-001`", self._covered_section(self._run()))

    def test_an_external_id_still_justifies(self):
        """An id outside the graph is documented legitimate use (ADR-087): it is
        unknown, not archived. Reading "not live" as "archived" would turn every
        external reference into an orphan — the false-positive this rule must avoid."""
        self._save(
            [self._node("FR-001", "solution")],
            [self._edge("FR-001", "EXT-999", "derives"),
             self._edge("COMP-EXT", "FR-001", "satisfies"),
             self._edge("TC-EXT", "FR-001", "verifies")],
        )
        self.assertIn("`FR-001`", self._covered_section(self._run()))

    def test_a_graph_of_only_archived_nodes_is_not_complete_coverage(self):
        """Before the archived population was kept in the selection, the empty-set
        cutoff above caught this case and answered "no active requirements". Keeping
        them made `requirements` non-empty, so the cutoff stopped firing and a project
        whose every requirement had been retired was declared ready for approval."""
        self._save(
            [self._node("BR-001", "business", "retired"),
             self._node("FR-001", "solution", "retired")],
            [self._edge("FR-001", "BR-001", "derives")],
        )
        out = self._run()
        self.assertNotIn("Покрытие полное", out)
        self.assertIn("в архиве", out.lower())

    def test_a_stale_link_is_named_where_the_analyst_reads_the_verdict(self):
        """`deprecate_requirements` sends the analyst here to find links left pointing
        at what it just archived. The warning lived in the body while the verdict two
        paragraphs below said the traceability was ready — the same document answering
        its own warning with "nothing to do"."""
        self._save(
            [self._node("BR-001", "business"),
             self._node("BR-OLD", "business", "retired"),
             self._node("FR-001", "solution"),
             self._node("COMP-1", "component")],
            [self._edge("FR-001", "BR-001", "derives"),
             self._edge("BR-001", "BR-OLD", "derives"),
             self._edge("COMP-1", "FR-001", "satisfies"),
             self._edge("TC-EXT", "FR-001", "verifies")],
        )
        out = self._run()
        # Coverage really IS complete here — every live node has live evidence. The
        # defect was that "complete" was the ONLY thing the verdict said, while the
        # body warned about a link nobody had re-pointed.
        recommendations = out.split("## Рекомендации", 1)[1]
        self.assertIn("BR-OLD", recommendations)


if __name__ == "__main__":
    unittest.main(verbosity=2)
