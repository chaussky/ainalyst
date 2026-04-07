"""
tests/test_ch7_75.py — Тесты для Главы 7, задача 7.5 (Define Design Options)

Покрытие (70 тестов):
  - Утилиты: _safe, _repo_path, _design_options_path, _change_strategy_path,
             _load_repo, _load_design_options, _save_design_options,
             _load_change_strategy, _find_req, _get_depends_links

  - set_change_strategy: success create, success update, invalid change_type,
    empty scope, empty constraints, empty timeline,
    graceful creates design_options file, all valid change_types accepted

  - create_design_option: success create, success update (idempotent),
    invalid approach, empty option_id, empty title,
    invalid components_json, empty components list,
    invalid opportunities_json, invalid opportunity type,
    invalid measures_json, vendor_notes warning for buy/hybrid without vendor,
    multiple options accumulated in file

  - allocate_requirements: option_id not found, auto_suggest True builds map,
    Must→v1, Could→v2, Won't→out_of_scope, Should→v1,
    manual assignments override auto_suggest,
    invalid assignments_json, invalid version in assignments,
    no_priority_reqs reported, depends conflict detected,
    no conflict when same version, allocation saved to design_options,
    empty repo graceful, auto_suggest False with manual assignments only

  - compare_design_options: no options → warning, single option → warning,
    two options success, req_coverage calculated from allocation,
    custom criteria merged with defaults, allocation summary per option,
    graceful without allocation data

  - save_design_options_report: no options → warning,
    recommended_option_id not found, success without recommendation,
    success with recommendation, change_strategy included if present,
    business_context included if present, architecture included if present,
    unallocated req warning, save_artifact called,
    allocation map in document

  - Pipeline: full happy path set_strategy → create × 2 → allocate → compare → report
"""

import json
import os
import sys
import unittest
from datetime import date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tests.conftest import BaseMCPTest, setup_mocks

setup_mocks()

import skills.design_options_mcp as mod75


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def make_req(req_id, req_type, title="Тестовое требование", priority=None, status="verified"):
    r = {"id": req_id, "type": req_type, "title": title, "status": status}
    if priority:
        r["priority"] = priority
    return r


def make_repo(reqs=None, links=None):
    return {
        "requirements": reqs or [],
        "links": links or [],
        "history": [],
    }


def make_link(from_id, to_id, relation="depends"):
    return {"from": from_id, "to": to_id, "relation": relation}


def make_option(option_id="OPT-001", title="Вариант 1", approach="build",
                components=None, opportunities=None, measures=None):
    return {
        "option_id": option_id,
        "title": title,
        "approach": approach,
        "components": components or ["Компонент A"],
        "improvement_opportunities": opportunities or [
            {"type": "efficiency", "description": "Автоматизация процесса"}
        ],
        "effectiveness_measures": measures or ["KPI 1"],
        "notes": "",
        "vendor_notes": "",
        "created": str(date.today()),
        "updated": str(date.today()),
    }


def make_design_options(project_id="test_proj", options=None, allocation=None):
    return {
        "project_id": project_id,
        "change_strategy_ref": "",
        "options": options or [],
        "allocation": allocation or {},
        "created": str(date.today()),
        "updated": str(date.today()),
    }


# ---------------------------------------------------------------------------
# Базовый класс
# ---------------------------------------------------------------------------

class Base75Test(BaseMCPTest):
    """Базовый класс: мокает save_artifact и переключает paths на tmp dir."""

    def setUp(self):
        super().setUp()
        self._orig_gp = None
        # Патчим governance_plans путь через переопределение функций-путей
        mod75.save_artifact = self._mock_save_artifact
        self._saved_artifacts = []

    def _mock_save_artifact(self, content, prefix="artifact"):
        self._saved_artifacts.append({"prefix": prefix, "content": content})

    def _write_repo(self, project_id, repo_data):
        path = mod75._repo_path(project_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(repo_data, f, ensure_ascii=False)

    def _write_design_options(self, project_id, data):
        path = mod75._design_options_path(project_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def _write_change_strategy(self, project_id, data):
        path = mod75._change_strategy_path(project_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def _write_context(self, project_id, data):
        path = mod75._context_path(project_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def _write_architecture(self, project_id, data):
        path = mod75._architecture_path(project_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def _read_design_options(self, project_id):
        path = mod75._design_options_path(project_id)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _read_change_strategy(self, project_id):
        path = mod75._change_strategy_path(project_id)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


# ===========================================================================
# Тесты утилит
# ===========================================================================

class TestUtils(Base75Test):

    def test_safe_lowercase(self):
        self.assertEqual(mod75._safe("My Project"), "my_project")

    def test_safe_spaces_to_underscore(self):
        self.assertEqual(mod75._safe("CRM System"), "crm_system")

    def test_repo_path_format(self):
        p = mod75._repo_path("alpha")
        self.assertIn("alpha_traceability_repo.json", p)

    def test_design_options_path_format(self):
        p = mod75._design_options_path("alpha")
        self.assertIn("alpha_design_options.json", p)

    def test_change_strategy_path_format(self):
        p = mod75._change_strategy_path("alpha")
        self.assertIn("alpha_change_strategy.json", p)

    def test_load_repo_missing_file(self):
        repo = mod75._load_repo("no_such_project_xyz")
        self.assertEqual(repo["requirements"], [])
        self.assertEqual(repo["links"], [])

    def test_load_design_options_missing_file(self):
        data = mod75._load_design_options("no_such_project_xyz")
        self.assertEqual(data["options"], [])
        self.assertEqual(data["allocation"], {})

    def test_load_change_strategy_missing_file(self):
        result = mod75._load_change_strategy("no_such_project_xyz")
        self.assertIsNone(result)

    def test_find_req_found(self):
        repo = make_repo(reqs=[make_req("FR-001", "functional")])
        found = mod75._find_req(repo, "FR-001")
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], "FR-001")

    def test_find_req_not_found(self):
        repo = make_repo(reqs=[])
        found = mod75._find_req(repo, "FR-999")
        self.assertIsNone(found)

    def test_get_depends_links_filtered(self):
        repo = make_repo(links=[
            make_link("FR-001", "FR-002", "depends"),
            make_link("FR-001", "FR-003", "derives"),  # не depends
        ])
        links = mod75._get_depends_links(repo)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0], ("FR-001", "FR-002"))

    def test_get_depends_links_empty(self):
        repo = make_repo(links=[])
        self.assertEqual(mod75._get_depends_links(repo), [])


# ===========================================================================
# Тесты set_change_strategy
# ===========================================================================

class TestSetChangeStrategy(Base75Test):

    def test_success_create(self):
        result = mod75.set_change_strategy(
            project_id="proj_cs",
            change_type="technology",
            scope="Замена CRM",
            constraints="Бюджет $100k",
            timeline="12 месяцев",
        )
        self.assertIn("✅", result)
        self.assertIn("technology", result)
        data = self._read_change_strategy("proj_cs")
        self.assertEqual(data["change_type"], "technology")
        self.assertEqual(data["scope"], "Замена CRM")

    def test_success_update(self):
        mod75.set_change_strategy(
            project_id="proj_cs2", change_type="technology",
            scope="Скоуп 1", constraints="Ограничение 1", timeline="Q1"
        )
        result = mod75.set_change_strategy(
            project_id="proj_cs2", change_type="process",
            scope="Скоуп 2", constraints="Ограничение 2", timeline="Q2"
        )
        self.assertIn("обновлена", result)
        data = self._read_change_strategy("proj_cs2")
        self.assertEqual(data["change_type"], "process")

    def test_invalid_change_type(self):
        result = mod75.set_change_strategy(
            project_id="proj_cs3", change_type="invalid_type",
            scope="x", constraints="y", timeline="z"
        )
        self.assertIn("❌", result)

    def test_empty_scope(self):
        result = mod75.set_change_strategy(
            project_id="proj_cs4", change_type="technology",
            scope="", constraints="y", timeline="z"
        )
        self.assertIn("❌", result)
        self.assertIn("scope", result)

    def test_empty_constraints(self):
        result = mod75.set_change_strategy(
            project_id="proj_cs5", change_type="technology",
            scope="x", constraints="", timeline="z"
        )
        self.assertIn("❌", result)

    def test_empty_timeline(self):
        result = mod75.set_change_strategy(
            project_id="proj_cs6", change_type="technology",
            scope="x", constraints="y", timeline=""
        )
        self.assertIn("❌", result)

    def test_all_valid_change_types(self):
        for ct in ["technology", "process", "organizational", "hybrid"]:
            result = mod75.set_change_strategy(
                project_id=f"proj_ct_{ct}", change_type=ct,
                scope="x", constraints="y", timeline="z"
            )
            self.assertIn("✅", result, f"Failed for change_type={ct}")

    def test_notes_optional(self):
        result = mod75.set_change_strategy(
            project_id="proj_cs7", change_type="technology",
            scope="x", constraints="y", timeline="z", notes="Доп. инфо"
        )
        self.assertIn("✅", result)
        data = self._read_change_strategy("proj_cs7")
        self.assertEqual(data["notes"], "Доп. инфо")

    def test_updates_design_options_ref(self):
        mod75.set_change_strategy(
            project_id="proj_cs8", change_type="technology",
            scope="x", constraints="y", timeline="z"
        )
        do_data = self._read_design_options("proj_cs8")
        self.assertIn("change_strategy_ref", do_data)


# ===========================================================================
# Тесты create_design_option
# ===========================================================================

class TestCreateDesignOption(Base75Test):

    def _make_call(self, **kwargs):
        defaults = dict(
            project_id="proj_do",
            option_id="OPT-001",
            title="Разработка своего решения",
            approach="build",
            components_json='["Backend", "UI", "DB"]',
            improvement_opportunities_json='[{"type": "efficiency", "description": "Автоматизация"}]',
            effectiveness_measures_json='["Снижение времени обработки на 40%"]',
        )
        defaults.update(kwargs)
        return mod75.create_design_option(**defaults)

    def test_success_create(self):
        result = self._make_call()
        self.assertIn("✅", result)
        self.assertIn("OPT-001", result)
        do_data = self._read_design_options("proj_do")
        self.assertEqual(len(do_data["options"]), 1)
        self.assertEqual(do_data["options"][0]["option_id"], "OPT-001")

    def test_success_update_idempotent(self):
        self._make_call(title="Версия 1")
        result = self._make_call(title="Версия 2")
        self.assertIn("обновлён", result)
        do_data = self._read_design_options("proj_do")
        self.assertEqual(len(do_data["options"]), 1)
        self.assertEqual(do_data["options"][0]["title"], "Версия 2")

    def test_invalid_approach(self):
        result = self._make_call(approach="outsource")
        self.assertIn("❌", result)

    def test_empty_option_id(self):
        result = self._make_call(option_id="")
        self.assertIn("❌", result)

    def test_empty_title(self):
        result = self._make_call(title="")
        self.assertIn("❌", result)

    def test_invalid_components_json(self):
        result = self._make_call(components_json="not json")
        self.assertIn("❌", result)

    def test_empty_components_list(self):
        result = self._make_call(components_json="[]")
        self.assertIn("❌", result)

    def test_invalid_opportunities_json(self):
        result = self._make_call(improvement_opportunities_json="not json")
        self.assertIn("❌", result)

    def test_invalid_opportunity_type(self):
        result = self._make_call(
            improvement_opportunities_json='[{"type": "unknown_type", "description": "x"}]'
        )
        self.assertIn("❌", result)

    def test_invalid_measures_json(self):
        result = self._make_call(effectiveness_measures_json="not json")
        self.assertIn("❌", result)

    def test_all_valid_approaches(self):
        for i, approach in enumerate(["build", "buy", "hybrid"]):
            result = self._make_call(
                project_id="proj_approaches",
                option_id=f"OPT-{i:03d}",
                approach=approach
            )
            self.assertIn("✅", result, f"Failed for approach={approach}")
        do_data = self._read_design_options("proj_approaches")
        self.assertEqual(len(do_data["options"]), 3)

    def test_vendor_warning_for_buy_without_vendor(self):
        result = self._make_call(
            project_id="proj_vendor",
            option_id="OPT-001",
            approach="buy",
            vendor_notes=""
        )
        self.assertIn("✅", result)
        self.assertIn("vendor_notes", result)

    def test_vendor_notes_saved(self):
        self._make_call(
            project_id="proj_vendor2",
            option_id="OPT-001",
            approach="buy",
            vendor_notes="Salesforce, $50k/год"
        )
        do_data = self._read_design_options("proj_vendor2")
        self.assertEqual(do_data["options"][0]["vendor_notes"], "Salesforce, $50k/год")

    def test_opportunities_saved_correctly(self):
        self._make_call(
            project_id="proj_opp",
            improvement_opportunities_json='[{"type": "new_capability", "description": "API интеграция"}]'
        )
        do_data = self._read_design_options("proj_opp")
        self.assertEqual(do_data["options"][0]["improvement_opportunities"][0]["type"], "new_capability")

    def test_multiple_options_accumulated(self):
        self._make_call(project_id="proj_multi", option_id="OPT-001")
        self._make_call(project_id="proj_multi", option_id="OPT-002", approach="buy")
        do_data = self._read_design_options("proj_multi")
        self.assertEqual(len(do_data["options"]), 2)


# ===========================================================================
# Тесты allocate_requirements
# ===========================================================================

class TestAllocateRequirements(Base75Test):

    def _setup_project(self, project_id, reqs, links=None):
        repo = make_repo(reqs=reqs, links=links or [])
        self._write_repo(project_id, repo)
        do_data = make_design_options(project_id=project_id, options=[
            make_option("OPT-001")
        ])
        self._write_design_options(project_id, do_data)

    def test_option_not_found(self):
        self._setup_project("proj_alloc_nf", [make_req("FR-001", "functional", priority="Must")])
        result = mod75.allocate_requirements(
            project_id="proj_alloc_nf", option_id="OPT-999"
        )
        self.assertIn("❌", result)

    def test_empty_repo(self):
        do_data = make_design_options(project_id="proj_alloc_empty", options=[make_option()])
        self._write_design_options("proj_alloc_empty", do_data)
        result = mod75.allocate_requirements(
            project_id="proj_alloc_empty", option_id="OPT-001"
        )
        self.assertIn("⚠️", result)

    def test_must_goes_to_v1(self):
        self._setup_project("proj_alloc_must", [make_req("FR-001", "functional", priority="Must")])
        mod75.allocate_requirements(project_id="proj_alloc_must", option_id="OPT-001", auto_suggest=True)
        do_data = self._read_design_options("proj_alloc_must")
        self.assertEqual(do_data["allocation"]["FR-001"]["version"], "v1")

    def test_could_goes_to_v2(self):
        self._setup_project("proj_alloc_could", [make_req("FR-001", "functional", priority="Could")])
        mod75.allocate_requirements(project_id="proj_alloc_could", option_id="OPT-001", auto_suggest=True)
        do_data = self._read_design_options("proj_alloc_could")
        self.assertEqual(do_data["allocation"]["FR-001"]["version"], "v2")

    def test_wont_goes_to_out_of_scope(self):
        self._setup_project("proj_alloc_wont", [make_req("FR-001", "functional", priority="Won't")])
        mod75.allocate_requirements(project_id="proj_alloc_wont", option_id="OPT-001", auto_suggest=True)
        do_data = self._read_design_options("proj_alloc_wont")
        self.assertEqual(do_data["allocation"]["FR-001"]["version"], "out_of_scope")

    def test_should_goes_to_v1(self):
        self._setup_project("proj_alloc_should", [make_req("FR-001", "functional", priority="Should")])
        mod75.allocate_requirements(project_id="proj_alloc_should", option_id="OPT-001", auto_suggest=True)
        do_data = self._read_design_options("proj_alloc_should")
        self.assertEqual(do_data["allocation"]["FR-001"]["version"], "v1")

    def test_no_priority_reported(self):
        self._setup_project("proj_alloc_noprio", [make_req("FR-001", "functional")])  # no priority
        result = mod75.allocate_requirements(project_id="proj_alloc_noprio", option_id="OPT-001", auto_suggest=True)
        self.assertIn("Без приоритета", result)

    def test_manual_assignment_overrides_auto(self):
        self._setup_project("proj_alloc_manual", [make_req("FR-001", "functional", priority="Must")])
        mod75.allocate_requirements(
            project_id="proj_alloc_manual", option_id="OPT-001",
            assignments_json='[{"req_id": "FR-001", "version": "out_of_scope", "rationale": "Убираем"}]',
            auto_suggest=True
        )
        do_data = self._read_design_options("proj_alloc_manual")
        self.assertEqual(do_data["allocation"]["FR-001"]["version"], "out_of_scope")

    def test_invalid_assignments_json(self):
        self._setup_project("proj_alloc_bad", [make_req("FR-001", "functional", priority="Must")])
        result = mod75.allocate_requirements(
            project_id="proj_alloc_bad", option_id="OPT-001",
            assignments_json="not valid json"
        )
        self.assertIn("❌", result)

    def test_invalid_version_in_assignments(self):
        self._setup_project("proj_alloc_inv_v", [make_req("FR-001", "functional", priority="Must")])
        result = mod75.allocate_requirements(
            project_id="proj_alloc_inv_v", option_id="OPT-001",
            assignments_json='[{"req_id": "FR-001", "version": "v5", "rationale": "x"}]'
        )
        self.assertIn("❌", result)

    def test_depends_conflict_detected(self):
        reqs = [
            make_req("FR-001", "functional", priority="Must"),   # → v1
            make_req("FR-002", "functional", priority="Could"),  # → v2
        ]
        links = [make_link("FR-001", "FR-002", "depends")]
        self._setup_project("proj_alloc_conflict", reqs, links)
        result = mod75.allocate_requirements(
            project_id="proj_alloc_conflict", option_id="OPT-001", auto_suggest=True
        )
        self.assertIn("Конфликты", result)
        self.assertIn("FR-001", result)
        self.assertIn("FR-002", result)

    def test_no_conflict_same_version(self):
        reqs = [
            make_req("FR-001", "functional", priority="Must"),
            make_req("FR-002", "functional", priority="Must"),
        ]
        links = [make_link("FR-001", "FR-002", "depends")]
        self._setup_project("proj_alloc_no_conflict", reqs, links)
        result = mod75.allocate_requirements(
            project_id="proj_alloc_no_conflict", option_id="OPT-001", auto_suggest=True
        )
        self.assertNotIn("❌", result)
        self.assertIn("✅", result)

    def test_auto_suggest_false_manual_only(self):
        self._setup_project("proj_alloc_manual_only", [make_req("FR-001", "functional", priority="Must")])
        mod75.allocate_requirements(
            project_id="proj_alloc_manual_only", option_id="OPT-001",
            assignments_json='[{"req_id": "FR-001", "version": "v2", "rationale": "Explicit"}]',
            auto_suggest=False
        )
        do_data = self._read_design_options("proj_alloc_manual_only")
        self.assertEqual(do_data["allocation"]["FR-001"]["version"], "v2")

    def test_allocation_saved_to_file(self):
        self._setup_project(
            "proj_alloc_save",
            [make_req("FR-001", "functional", priority="Must"), make_req("FR-002", "functional", priority="Could")]
        )
        mod75.allocate_requirements(project_id="proj_alloc_save", option_id="OPT-001", auto_suggest=True)
        do_data = self._read_design_options("proj_alloc_save")
        self.assertIn("FR-001", do_data["allocation"])
        self.assertIn("FR-002", do_data["allocation"])

    def test_business_and_test_types_excluded(self):
        reqs = [
            make_req("BG-001", "business", priority="Must"),
            make_req("TST-001", "test", priority="Must"),
            make_req("FR-001", "functional", priority="Must"),
        ]
        self._setup_project("proj_alloc_skip", reqs)
        mod75.allocate_requirements(project_id="proj_alloc_skip", option_id="OPT-001", auto_suggest=True)
        do_data = self._read_design_options("proj_alloc_skip")
        self.assertNotIn("BG-001", do_data["allocation"])
        self.assertNotIn("TST-001", do_data["allocation"])
        self.assertIn("FR-001", do_data["allocation"])


# ===========================================================================
# Тесты compare_design_options
# ===========================================================================

class TestCompareDesignOptions(Base75Test):

    def test_no_options_warning(self):
        do_data = make_design_options("proj_cmp_empty")
        self._write_design_options("proj_cmp_empty", do_data)
        result = mod75.compare_design_options("proj_cmp_empty")
        self.assertIn("⚠️", result)

    def test_single_option_warning(self):
        do_data = make_design_options("proj_cmp_one", options=[make_option()])
        self._write_design_options("proj_cmp_one", do_data)
        result = mod75.compare_design_options("proj_cmp_one")
        self.assertIn("⚠️", result)
        self.assertIn("2", result)

    def test_two_options_success(self):
        do_data = make_design_options("proj_cmp_two", options=[
            make_option("OPT-001", approach="build"),
            make_option("OPT-002", approach="buy"),
        ])
        self._write_design_options("proj_cmp_two", do_data)
        result = mod75.compare_design_options("proj_cmp_two")
        self.assertIn("OPT-001", result)
        self.assertIn("OPT-002", result)
        self.assertIn("Сравнительная матрица", result)

    def test_req_coverage_calculated_from_allocation(self):
        reqs = [
            make_req("FR-001", "functional", priority="Must"),
            make_req("FR-002", "functional", priority="Must"),
        ]
        self._write_repo("proj_cmp_cov", make_repo(reqs=reqs))
        allocation = {
            "FR-001": {"version": "v1", "option_id": "OPT-001", "rationale": "Auto", "source": "auto"},
            "FR-002": {"version": "v2", "option_id": "OPT-001", "rationale": "Auto", "source": "auto"},
        }
        do_data = make_design_options("proj_cmp_cov", options=[
            make_option("OPT-001"), make_option("OPT-002")
        ], allocation=allocation)
        self._write_design_options("proj_cmp_cov", do_data)
        result = mod75.compare_design_options("proj_cmp_cov")
        self.assertIn("50%", result)  # 1/2 Must в v1

    def test_custom_criteria_merged(self):
        do_data = make_design_options("proj_cmp_crit", options=[
            make_option("OPT-001"), make_option("OPT-002")
        ])
        self._write_design_options("proj_cmp_crit", do_data)
        result = mod75.compare_design_options(
            "proj_cmp_crit",
            criteria_json='[{"id": "vendor_support", "label": "Поддержка вендора", "weight": "medium"}]'
        )
        self.assertIn("Поддержка вендора", result)
        self.assertIn("Стоимость реализации", result)  # дефолтный тоже есть

    def test_invalid_criteria_json(self):
        do_data = make_design_options("proj_cmp_bad", options=[
            make_option("OPT-001"), make_option("OPT-002")
        ])
        self._write_design_options("proj_cmp_bad", do_data)
        result = mod75.compare_design_options("proj_cmp_bad", criteria_json="not json")
        self.assertIn("❌", result)

    def test_options_details_shown(self):
        opts = [
            make_option("OPT-001", approach="build"),
            make_option("OPT-002", approach="hybrid", title="Гибридное решение"),
        ]
        do_data = make_design_options("proj_cmp_det", options=opts)
        self._write_design_options("proj_cmp_det", do_data)
        result = mod75.compare_design_options("proj_cmp_det")
        self.assertIn("Гибридное решение", result)
        self.assertIn("Hybrid", result)


# ===========================================================================
# Тесты save_design_options_report
# ===========================================================================

class TestSaveDesignOptionsReport(Base75Test):

    def test_no_options_warning(self):
        do_data = make_design_options("proj_rep_empty")
        self._write_design_options("proj_rep_empty", do_data)
        result = mod75.save_design_options_report("proj_rep_empty")
        self.assertIn("⚠️", result)
        self.assertEqual(len(self._saved_artifacts), 0)

    def test_recommended_option_not_found(self):
        do_data = make_design_options("proj_rep_nf", options=[make_option()])
        self._write_design_options("proj_rep_nf", do_data)
        result = mod75.save_design_options_report("proj_rep_nf", recommended_option_id="OPT-999")
        self.assertIn("❌", result)

    def test_success_without_recommendation(self):
        do_data = make_design_options("proj_rep_ok", options=[
            make_option("OPT-001"), make_option("OPT-002")
        ])
        self._write_design_options("proj_rep_ok", do_data)
        result = mod75.save_design_options_report("proj_rep_ok")
        self.assertIn("✅", result)
        self.assertEqual(len(self._saved_artifacts), 1)
        self.assertEqual(self._saved_artifacts[0]["prefix"], "7_5_design_options")

    def test_success_with_recommendation(self):
        do_data = make_design_options("proj_rep_rec", options=[
            make_option("OPT-001"), make_option("OPT-002")
        ])
        self._write_design_options("proj_rep_rec", do_data)
        result = mod75.save_design_options_report("proj_rep_rec", recommended_option_id="OPT-002")
        self.assertIn("✅", result)
        self.assertIn("OPT-002", result)

    def test_change_strategy_included_in_doc(self):
        do_data = make_design_options("proj_rep_cs", options=[make_option()])
        self._write_design_options("proj_rep_cs", do_data)
        self._write_change_strategy("proj_rep_cs", {
            "project_id": "proj_rep_cs",
            "change_type": "technology",
            "scope": "Замена системы",
            "constraints": "Бюджет $200k",
            "timeline": "12 мес",
            "notes": "",
        })
        mod75.save_design_options_report("proj_rep_cs")
        content = self._saved_artifacts[0]["content"]
        self.assertIn("Стратегия изменения", content)
        self.assertIn("technology", content)

    def test_business_context_included(self):
        do_data = make_design_options("proj_rep_ctx", options=[make_option()])
        self._write_design_options("proj_rep_ctx", do_data)
        self._write_context("proj_rep_ctx", {
            "business_goals": [{"id": "BG-001", "title": "Рост продаж"}],
            "future_state": "Цифровая платформа"
        })
        mod75.save_design_options_report("proj_rep_ctx")
        content = self._saved_artifacts[0]["content"]
        self.assertIn("Бизнес-контекст", content)
        self.assertIn("Рост продаж", content)

    def test_architecture_included(self):
        do_data = make_design_options("proj_rep_arch", options=[make_option()])
        self._write_design_options("proj_rep_arch", do_data)
        self._write_architecture("proj_rep_arch", {
            "project_id": "proj_rep_arch",
            "viewpoints": {"functional": {"label": "Функциональность", "auto": True}},
            "views": {},
            "gaps": {"critical": ["критический разрыв"], "warning": [], "info": []},
            "snapshots": [],
        })
        mod75.save_design_options_report("proj_rep_arch")
        content = self._saved_artifacts[0]["content"]
        self.assertIn("Архитектурный контекст", content)

    def test_unallocated_req_warning(self):
        reqs = [make_req("FR-001", "functional", priority="Must")]
        self._write_repo("proj_rep_unalloc", make_repo(reqs=reqs))
        do_data = make_design_options("proj_rep_unalloc", options=[make_option()])
        # allocation пустой — req не распределён
        self._write_design_options("proj_rep_unalloc", do_data)
        result = mod75.save_design_options_report("proj_rep_unalloc")
        self.assertIn("не распределены", result)

    def test_allocation_map_in_document(self):
        reqs = [make_req("FR-001", "functional", priority="Must", title="Главная функция")]
        self._write_repo("proj_rep_alloc_doc", make_repo(reqs=reqs))
        allocation = {
            "FR-001": {"version": "v1", "option_id": "OPT-001", "rationale": "Must→v1", "source": "auto"}
        }
        do_data = make_design_options("proj_rep_alloc_doc", options=[make_option()], allocation=allocation)
        self._write_design_options("proj_rep_alloc_doc", do_data)
        mod75.save_design_options_report("proj_rep_alloc_doc")
        content = self._saved_artifacts[0]["content"]
        self.assertIn("Allocation Map", content)
        self.assertIn("FR-001", content)

    def test_save_artifact_called_with_correct_prefix(self):
        do_data = make_design_options("proj_rep_prefix", options=[make_option()])
        self._write_design_options("proj_rep_prefix", do_data)
        mod75.save_design_options_report("proj_rep_prefix")
        self.assertEqual(self._saved_artifacts[0]["prefix"], "7_5_design_options")


# ===========================================================================
# Тест Pipeline — полный сценарий
# ===========================================================================

class TestPipeline(Base75Test):

    def test_full_happy_path(self):
        """Полный pipeline: set_strategy → create × 2 → allocate → compare → report"""
        pid = "proj_pipeline"

        # Репозиторий с требованиями
        reqs = [
            make_req("FR-001", "functional", title="Авторизация", priority="Must"),
            make_req("FR-002", "functional", title="Поиск", priority="Should"),
            make_req("FR-003", "functional", title="Экспорт", priority="Could"),
            make_req("FR-004", "functional", title="Аналитика", priority="Won't"),
        ]
        self._write_repo(pid, make_repo(reqs=reqs))

        # Шаг 1: set_change_strategy
        r1 = mod75.set_change_strategy(
            project_id=pid,
            change_type="technology",
            scope="Замена legacy системы",
            constraints="Бюджет $300k",
            timeline="18 месяцев",
        )
        self.assertIn("✅", r1)

        # Шаг 2: create OPT-001 (Build)
        r2a = mod75.create_design_option(
            project_id=pid, option_id="OPT-001", title="Разработка с нуля",
            approach="build",
            components_json='["API", "UI", "DB"]',
            improvement_opportunities_json='[{"type": "efficiency", "description": "Автоматизация"}]',
            effectiveness_measures_json='["Время обработки -40%"]',
        )
        self.assertIn("✅", r2a)

        # Шаг 2: create OPT-002 (Buy)
        r2b = mod75.create_design_option(
            project_id=pid, option_id="OPT-002", title="Salesforce CRM",
            approach="buy",
            components_json='["Salesforce", "Интеграционный слой"]',
            improvement_opportunities_json='[{"type": "information_access", "description": "360 вид клиента"}]',
            effectiveness_measures_json='["NPS > 8"]',
            vendor_notes="Salesforce, $80k/год, стандартная кастомизация"
        )
        self.assertIn("✅", r2b)

        # Шаг 3: allocate OPT-001
        r3 = mod75.allocate_requirements(
            project_id=pid, option_id="OPT-001", auto_suggest=True
        )
        self.assertIn("v1", r3)
        do_data = self._read_design_options(pid)
        self.assertEqual(do_data["allocation"]["FR-001"]["version"], "v1")
        self.assertEqual(do_data["allocation"]["FR-004"]["version"], "out_of_scope")

        # Шаг 4: compare
        r4 = mod75.compare_design_options(pid)
        self.assertIn("OPT-001", r4)
        self.assertIn("OPT-002", r4)
        self.assertIn("Сравнительная матрица", r4)

        # Шаг 5: save report
        r5 = mod75.save_design_options_report(pid, recommended_option_id="OPT-001", notes="Build более гибкий")
        self.assertIn("✅", r5)
        self.assertEqual(len(self._saved_artifacts), 1)
        content = self._saved_artifacts[0]["content"]
        self.assertIn("Design Options Report", content)
        self.assertIn("РЕКОМЕНДУЕТСЯ", content)
        self.assertIn("OPT-001", content)

    def test_graceful_without_optional_inputs(self):
        """Pipeline работает без 5.3, 7.3, 7.4, 6.4 — graceful degradation."""
        pid = "proj_pipeline_minimal"

        # Только репозиторий с req без приоритетов
        self._write_repo(pid, make_repo(reqs=[make_req("FR-001", "functional")]))

        r1 = mod75.create_design_option(
            project_id=pid, option_id="OPT-001", title="Минимальный вариант",
            approach="build",
            components_json='["API"]',
            improvement_opportunities_json='[]',
            effectiveness_measures_json='["KPI 1"]',
        )
        self.assertIn("✅", r1)

        r2 = mod75.create_design_option(
            project_id=pid, option_id="OPT-002", title="Второй вариант",
            approach="buy",
            components_json='["SaaS"]',
            improvement_opportunities_json='[]',
            effectiveness_measures_json='["KPI 2"]',
        )
        self.assertIn("✅", r2)

        # Allocation без приоритетов — предупреждение, не ошибка
        r3 = mod75.allocate_requirements(pid, "OPT-001", auto_suggest=True)
        self.assertNotIn("❌", r3)

        # Report без change_strategy и context
        r4 = mod75.save_design_options_report(pid)
        self.assertIn("✅", r4)


if __name__ == "__main__":
    unittest.main()
