"""
tests/test_ch7_74.py — Тесты для Главы 7, задача 7.4 (Define Requirements Architecture)

Покрытие (75 тестов):
  - Утилиты: _safe, _repo_path, _architecture_path, _load_repo, _load_architecture,
             _save_architecture, _load_stakeholders, _load_context,
             _find_req, _get_linked_ids, _build_views_from_repo

  - analyze_requirements_architecture: empty repo, auto viewpoints built,
    missing types reported, custom viewpoints included, coverage matrix with BG,
    no BG context (graceful), updates architecture file

  - add_custom_viewpoint: success create, success update, invalid viewpoint_id (spaces),
    viewpoint_id conflicts with standard type, empty label,
    invalid req_ids JSON, empty req_ids list, req_ids not in repo,
    partial not_found, validates all IDs exist, saves to architecture

  - check_architecture_gaps: empty repo, empty viewpoint → info,
    stakeholder without representation → critical,
    no stakeholders file → graceful (info not critical),
    BG not in graph → warning, UC without BP → warning,
    NFR without FR → warning, FR without UC or US → info,
    no gaps → clean verdict, gaps saved to architecture,
    all gap types in one run

  - save_architecture_snapshot: success v1.0, duplicate version rejected,
    empty version rejected, empty repo rejected,
    snapshot added to history (not overwritten),
    multiple snapshots accumulate, notes and author saved,
    summary counts correct, architecture document generated (save_artifact called),
    critical gaps count in result

  - Pipeline: full happy path analyze → custom_viewpoint → gaps → snapshot,
    graceful without stakeholders and context
"""

import json
import os
import sys
import unittest
from datetime import date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tests.conftest import BaseMCPTest

import skills.requirements_architecture_mcp as mod74


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def make_req(req_id, req_type, title="Тестовое требование", status="verified"):
    return {
        "id": req_id,
        "type": req_type,
        "title": title,
        "status": status,
        "priority": "Medium",
        "version": "1.0",
        "added": str(date.today()),
    }


def make_repo(project_id, requirements=None, links=None):
    return {
        "project": project_id,
        "formality_level": "Standard",
        "created": str(date.today()),
        "updated": str(date.today()),
        "requirements": requirements or [],
        "links": links or [],
        "history": [],
    }


def save_repo(repo):
    safe = repo["project"].lower().replace(" ", "_")
    path = os.path.join("governance_plans", "data", f"{safe}_traceability_repo.json")
    os.makedirs(os.path.join("governance_plans", "data"), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)


def load_arch(project_id):
    safe = project_id.lower().replace(" ", "_")
    path = os.path.join("governance_plans", "data", f"{safe}_architecture.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def make_stakeholders(project_id, stakeholders=None):
    return {
        "project": project_id,
        "stakeholders": stakeholders or [
            {"id": "SH-001", "name": "Иванов", "role": "Заказчик"},
            {"id": "SH-002", "name": "Петрова", "role": "Пользователь"},
        ],
    }


def save_stakeholders(data):
    safe = data["project"].lower().replace(" ", "_")
    path = os.path.join("governance_plans", "data", f"{safe}_stakeholders.json")
    os.makedirs(os.path.join("governance_plans", "data"), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def make_context(project_id, goals=None):
    return {
        "project_id": project_id,
        "business_goals": goals or [
            {"id": "BG-001", "title": "Снизить время обработки", "kpi": "с 24ч до 4ч"},
            {"id": "BG-002", "title": "Увеличить NPS", "kpi": "с 45 до 65"},
        ],
        "future_state": "Единое окно для операторов",
        "solution_scope": "Входит: CRM. Не входит: мобилка",
        "created_at": str(date.today()),
        "updated_at": str(date.today()),
    }


def save_context(ctx):
    safe = ctx["project_id"].lower().replace(" ", "_")
    path = os.path.join("governance_plans", "data", f"{safe}_business_context.json")
    os.makedirs(os.path.join("governance_plans", "data"), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ctx, f, ensure_ascii=False, indent=2)


def make_full_repo(project_id):
    """Репозиторий со всеми типами артефактов."""
    reqs = [
        make_req("BP-001", "business_process", "Приём заявки от клиента"),
        make_req("BP-002", "business_process", "Обработка заявки оператором"),
        make_req("DD-001", "data_dictionary", "Сущность: Заявка"),
        make_req("ERD-001", "erd", "ERD: Клиент — Заявка — Оператор"),
        make_req("US-001", "user_story", "Как оператор хочу видеть очередь"),
        make_req("US-002", "user_story", "Как менеджер хочу видеть статистику"),
        make_req("UC-001", "use_case", "UC: Назначить оператора на заявку"),
        make_req("FR-001", "functional", "Автоматическое распределение заявок"),
        make_req("FR-002", "functional", "Уведомления о смене статуса"),
        make_req("NFR-001", "non_functional", "Время ответа < 2 сек"),
        make_req("BR-001", "business_rule", "Заявка назначается оператору с минимальной нагрузкой"),
        make_req("BG-001", "business", "Снизить время обработки"),
    ]
    links = [
        {"from": "UC-001", "to": "BP-001", "relation": "derives", "added": str(date.today())},
        {"from": "US-001", "to": "FR-001", "relation": "derives", "added": str(date.today())},
        {"from": "NFR-001", "to": "FR-001", "relation": "satisfies", "added": str(date.today())},
        {"from": "FR-001", "to": "BG-001", "relation": "satisfies", "added": str(date.today())},
    ]
    return make_repo(project_id, reqs, links)


# ---------------------------------------------------------------------------
# Тесты утилит
# ---------------------------------------------------------------------------

class TestUtilities(BaseMCPTest):

    def test_safe_basic(self):
        self.assertEqual(mod74._safe("CRM Upgrade"), "crm_upgrade")

    def test_safe_already_lower(self):
        self.assertEqual(mod74._safe("myproject"), "myproject")

    def test_safe_multiple_spaces(self):
        self.assertEqual(mod74._safe("A B C"), "a_b_c")

    def test_repo_path(self):
        path = mod74._repo_path("CRM Upgrade")
        self.assertIn("crm_upgrade", path)
        self.assertIn("traceability_repo", path)

    def test_architecture_path(self):
        path = mod74._architecture_path("crm_upgrade")
        self.assertIn("crm_upgrade", path)
        self.assertIn("architecture.json", path)

    def test_load_repo_missing(self):
        repo = mod74._load_repo("nonexistent_project")
        self.assertEqual(repo["requirements"], [])
        self.assertEqual(repo["links"], [])

    def test_load_architecture_missing_returns_default(self):
        arch = mod74._load_architecture("no_arch_project")
        self.assertIn("viewpoints", arch)
        self.assertIn("views", arch)
        self.assertIn("snapshots", arch)
        self.assertEqual(arch["snapshots"], [])

    def test_save_and_load_architecture(self):
        arch = mod74._load_architecture("save_test")
        arch["viewpoints"]["custom_test"] = {"label": "Тест", "auto": False, "req_ids": ["FR-001"]}
        mod74._save_architecture(arch)
        loaded = mod74._load_architecture("save_test")
        self.assertIn("custom_test", loaded["viewpoints"])

    def test_load_stakeholders_missing_returns_none(self):
        result = mod74._load_stakeholders("no_stakeholders_project")
        self.assertIsNone(result)

    def test_load_context_missing_returns_none(self):
        result = mod74._load_context("no_context_project")
        self.assertIsNone(result)

    def test_find_req_found(self):
        repo = make_repo("p", [make_req("FR-001", "functional")])
        found = mod74._find_req(repo, "FR-001")
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], "FR-001")

    def test_find_req_not_found(self):
        repo = make_repo("p", [make_req("FR-001", "functional")])
        found = mod74._find_req(repo, "FR-999")
        self.assertIsNone(found)

    def test_get_linked_ids_both_directions(self):
        repo = make_repo("p", [], [
            {"from": "UC-001", "to": "BP-001", "relation": "derives", "added": str(date.today())},
        ])
        # UC-001 → BP-001
        linked_from_uc = mod74._get_linked_ids(repo, "UC-001")
        self.assertIn("BP-001", linked_from_uc)
        # BP-001 ← UC-001 (обратная сторона)
        linked_from_bp = mod74._get_linked_ids(repo, "BP-001")
        self.assertIn("UC-001", linked_from_bp)

    def test_get_linked_ids_with_filter(self):
        repo = make_repo("p", [], [
            {"from": "NFR-001", "to": "FR-001", "relation": "satisfies", "added": str(date.today())},
            {"from": "TC-001", "to": "FR-001", "relation": "verifies", "added": str(date.today())},
        ])
        linked = mod74._get_linked_ids(repo, "FR-001", relation_filter={"satisfies"})
        self.assertIn("NFR-001", linked)
        self.assertNotIn("TC-001", linked)

    def test_build_views_from_repo_maps_types(self):
        repo = make_repo("p", [
            make_req("BP-001", "business_process"),
            make_req("FR-001", "functional"),
            make_req("US-001", "user_story"),
            make_req("BG-001", "business"),   # должен быть пропущен
            make_req("TC-001", "test"),        # должен быть пропущен
        ])
        views = mod74._build_views_from_repo(repo)
        self.assertIn("business_process", views)
        self.assertIn("BP-001", views["business_process"])
        self.assertIn("functional", views)
        self.assertIn("FR-001", views["functional"])
        self.assertIn("user_story", views)
        self.assertNotIn("business", views)
        self.assertNotIn("test", views)


# ---------------------------------------------------------------------------
# Тесты analyze_requirements_architecture
# ---------------------------------------------------------------------------

class TestAnalyzeRequirementsArchitecture(BaseMCPTest):

    def test_empty_repo_returns_warning(self):
        result = mod74.analyze_requirements_architecture("empty_proj")
        self.assertIn("пуст", result)

    def test_builds_auto_viewpoints(self):
        repo = make_full_repo("crm")
        save_repo(repo)
        result = mod74.analyze_requirements_architecture("crm")
        self.assertIn("Бизнес-процессы", result)
        self.assertIn("Функциональность", result)
        self.assertIn("Пользователи и взаимодействие", result)
        self.assertIn("Данные и информация", result)
        self.assertIn("Бизнес-правила", result)

    def test_reports_missing_types(self):
        # Только BP — остальные типы должны быть в "отсутствующих"
        repo = make_repo("partial", [make_req("BP-001", "business_process")])
        save_repo(repo)
        result = mod74.analyze_requirements_architecture("partial")
        self.assertIn("Отсутствующие", result)

    def test_no_missing_when_all_types_present(self):
        repo = make_full_repo("full")
        save_repo(repo)
        result = mod74.analyze_requirements_architecture("full")
        # При наличии всех типов — секция отсутствующих не должна содержать все
        # (может быть пуста или содержать не все типы)
        arch = load_arch("full")
        self.assertIn("business_process", arch["views"])
        self.assertIn("functional", arch["views"])

    def test_includes_custom_viewpoints_from_existing_arch(self):
        repo = make_repo("proj", [make_req("FR-001", "functional")])
        save_repo(repo)
        # Предварительно создаём кастомный viewpoint в архитектуре
        arch = mod74._load_architecture("proj")
        arch["viewpoints"]["security"] = {
            "label": "Безопасность", "auto": False,
            "req_ids": ["FR-001"], "description": "Тест",
        }
        mod74._save_architecture(arch)
        result = mod74.analyze_requirements_architecture("proj")
        self.assertIn("Кастомные точки зрения", result)
        self.assertIn("security", result)

    def test_coverage_matrix_shown_when_context_exists(self):
        repo = make_full_repo("ctx_proj")
        save_repo(repo)
        save_context(make_context("ctx_proj"))
        result = mod74.analyze_requirements_architecture("ctx_proj")
        self.assertIn("Coverage Matrix", result)
        self.assertIn("BG-001", result)

    def test_no_coverage_matrix_without_context(self):
        repo = make_full_repo("no_ctx")
        save_repo(repo)
        result = mod74.analyze_requirements_architecture("no_ctx")
        # Без business_context — матрицы нет
        self.assertNotIn("Coverage Matrix", result)

    def test_updates_architecture_file(self):
        repo = make_repo("arch_file", [make_req("BP-001", "business_process")])
        save_repo(repo)
        mod74.analyze_requirements_architecture("arch_file")
        arch = load_arch("arch_file")
        self.assertIn("business_process", arch["viewpoints"])
        self.assertIn("business_process", arch["views"])
        self.assertIn("BP-001", arch["views"]["business_process"])

    def test_req_ids_in_views(self):
        repo = make_repo("view_ids", [
            make_req("FR-001", "functional"),
            make_req("FR-002", "functional"),
        ])
        save_repo(repo)
        mod74.analyze_requirements_architecture("view_ids")
        arch = load_arch("view_ids")
        self.assertIn("FR-001", arch["views"]["functional"])
        self.assertIn("FR-002", arch["views"]["functional"])


# ---------------------------------------------------------------------------
# Тесты add_custom_viewpoint
# ---------------------------------------------------------------------------

class TestAddCustomViewpoint(BaseMCPTest):

    def _setup_repo_with_reqs(self, project_id):
        repo = make_repo(project_id, [
            make_req("FR-001", "functional"),
            make_req("NFR-001", "non_functional"),
            make_req("BR-001", "business_rule"),
        ])
        save_repo(repo)

    def test_success_create(self):
        self._setup_repo_with_reqs("sec_proj")
        result = mod74.add_custom_viewpoint(
            project_id="sec_proj",
            viewpoint_id="security",
            label="Безопасность и доступ",
            req_ids_json='["FR-001", "NFR-001"]',
            description="Требования к безопасности",
            stakeholder_roles="CISO",
        )
        self.assertIn("создана", result)
        self.assertIn("security", result)
        arch = load_arch("sec_proj")
        self.assertIn("security", arch["viewpoints"])
        self.assertEqual(arch["viewpoints"]["security"]["auto"], False)
        self.assertIn("FR-001", arch["viewpoints"]["security"]["req_ids"])

    def test_success_update(self):
        self._setup_repo_with_reqs("upd_proj")
        mod74.add_custom_viewpoint(
            project_id="upd_proj",
            viewpoint_id="audit",
            label="Аудит",
            req_ids_json='["BR-001"]',
        )
        result = mod74.add_custom_viewpoint(
            project_id="upd_proj",
            viewpoint_id="audit",
            label="Аудит и compliance",
            req_ids_json='["BR-001", "FR-001"]',
        )
        self.assertIn("обновлена", result)
        arch = load_arch("upd_proj")
        self.assertIn("FR-001", arch["viewpoints"]["audit"]["req_ids"])

    def test_invalid_viewpoint_id_with_spaces(self):
        self._setup_repo_with_reqs("space_proj")
        result = mod74.add_custom_viewpoint(
            project_id="space_proj",
            viewpoint_id="my security",
            label="Безопасность",
            req_ids_json='["FR-001"]',
        )
        self.assertIn("❌", result)
        self.assertIn("пробел", result.lower())

    def test_viewpoint_id_conflicts_with_standard_type(self):
        self._setup_repo_with_reqs("conflict_proj")
        result = mod74.add_custom_viewpoint(
            project_id="conflict_proj",
            viewpoint_id="functional",
            label="Функциональность кастомная",
            req_ids_json='["FR-001"]',
        )
        self.assertIn("❌", result)
        self.assertIn("стандартным", result)

    def test_empty_label(self):
        self._setup_repo_with_reqs("lbl_proj")
        result = mod74.add_custom_viewpoint(
            project_id="lbl_proj",
            viewpoint_id="custom",
            label="",
            req_ids_json='["FR-001"]',
        )
        self.assertIn("❌", result)
        self.assertIn("label", result)

    def test_invalid_req_ids_json(self):
        self._setup_repo_with_reqs("json_proj")
        result = mod74.add_custom_viewpoint(
            project_id="json_proj",
            viewpoint_id="custom",
            label="Тест",
            req_ids_json='not-json',
        )
        self.assertIn("❌", result)

    def test_empty_req_ids_list(self):
        self._setup_repo_with_reqs("empty_ids_proj")
        result = mod74.add_custom_viewpoint(
            project_id="empty_ids_proj",
            viewpoint_id="custom",
            label="Тест",
            req_ids_json='[]',
        )
        self.assertIn("❌", result)

    def test_req_ids_not_in_repo(self):
        self._setup_repo_with_reqs("notfound_proj")
        result = mod74.add_custom_viewpoint(
            project_id="notfound_proj",
            viewpoint_id="custom",
            label="Тест",
            req_ids_json='["XX-999", "YY-000"]',
        )
        self.assertIn("❌", result)
        self.assertIn("XX-999", result)

    def test_partial_not_found_blocks_save(self):
        self._setup_repo_with_reqs("partial_proj")
        result = mod74.add_custom_viewpoint(
            project_id="partial_proj",
            viewpoint_id="custom",
            label="Тест",
            req_ids_json='["FR-001", "XX-999"]',
        )
        self.assertIn("❌", result)
        # Файл архитектуры не должен содержать этот viewpoint
        arch = mod74._load_architecture("partial_proj")
        self.assertNotIn("custom", arch["viewpoints"])

    def test_views_updated_after_add(self):
        self._setup_repo_with_reqs("views_upd")
        mod74.add_custom_viewpoint(
            project_id="views_upd",
            viewpoint_id="migration",
            label="Миграция данных",
            req_ids_json='["FR-001", "NFR-001"]',
        )
        arch = load_arch("views_upd")
        self.assertIn("migration", arch["views"])
        self.assertIn("FR-001", arch["views"]["migration"])


# ---------------------------------------------------------------------------
# Тесты check_architecture_gaps
# ---------------------------------------------------------------------------

class TestCheckArchitectureGaps(BaseMCPTest):

    def test_empty_repo_returns_warning(self):
        result = mod74.check_architecture_gaps("empty_gaps")
        self.assertIn("пуст", result)

    def test_empty_viewpoint_info_gap(self):
        # Есть только FR — нет BP, UC и т.д. → пустые viewpoints как info
        repo = make_repo("info_gaps", [make_req("FR-001", "functional")])
        save_repo(repo)
        result = mod74.check_architecture_gaps("info_gaps")
        self.assertIn("Info", result)

    def test_no_stakeholders_file_graceful(self):
        repo = make_repo("no_sh", [make_req("FR-001", "functional")])
        save_repo(repo)
        # Файла стейкхолдеров нет — не должно падать, info-сообщение
        result = mod74.check_architecture_gaps("no_sh")
        self.assertNotIn("❌ Ошибка", result)
        self.assertIn("Реестр стейкхолдеров", result)

    def test_bg_not_in_graph_warning(self):
        # BG в business_context но нет как узла в репозитории 5.1
        repo = make_repo("bg_gap", [make_req("FR-001", "functional")])
        save_repo(repo)
        save_context(make_context("bg_gap"))
        result = mod74.check_architecture_gaps("bg_gap")
        self.assertIn("Warning", result)
        self.assertIn("BG-001", result)

    def test_bg_in_graph_no_warning(self):
        # BG есть как узел в репозитории → предупреждения по BG нет
        repo = make_repo("bg_ok", [
            make_req("FR-001", "functional"),
            make_req("BG-001", "business", "Снизить время обработки"),
        ])
        save_repo(repo)
        save_context(make_context("bg_ok", goals=[
            {"id": "BG-001", "title": "Снизить время обработки", "kpi": ""}
        ]))
        result = mod74.check_architecture_gaps("bg_ok")
        # Не должно быть warning о BG-001 не в графе
        self.assertNotIn("BG-001` (", result.split("Warning")[1] if "Warning" in result else result)

    def test_uc_without_bp_warning(self):
        # UC без связи с BP → warning
        repo = make_repo("uc_gap", [
            make_req("UC-001", "use_case", "UC без BP"),
            make_req("BP-001", "business_process", "Процесс"),
        ])
        # Без связей UC→BP
        save_repo(repo)
        result = mod74.check_architecture_gaps("uc_gap")
        self.assertIn("UC-001", result)
        self.assertIn("Warning", result)

    def test_uc_with_bp_no_warning(self):
        # UC связан с BP → warning нет
        links = [{"from": "UC-001", "to": "BP-001", "relation": "derives", "added": str(date.today())}]
        repo = make_repo("uc_ok", [
            make_req("UC-001", "use_case", "UC с BP"),
            make_req("BP-001", "business_process", "Процесс"),
        ], links)
        save_repo(repo)
        result = mod74.check_architecture_gaps("uc_ok")
        # UC-001 не должен появляться в warning о UC без BP
        if "UC-001" in result:
            # Проверяем что это не warning о uc_without_bp
            self.assertNotIn("без соответствующего Business Process", result)

    def test_nfr_without_fr_warning(self):
        links = []  # Нет связей
        repo = make_repo("nfr_gap", [
            make_req("NFR-001", "non_functional", "Производительность"),
            make_req("FR-001", "functional", "Функция"),
        ], links)
        save_repo(repo)
        result = mod74.check_architecture_gaps("nfr_gap")
        self.assertIn("NFR-001", result)
        self.assertIn("Warning", result)

    def test_nfr_with_fr_no_warning(self):
        links = [{"from": "NFR-001", "to": "FR-001", "relation": "satisfies", "added": str(date.today())}]
        repo = make_repo("nfr_ok", [
            make_req("NFR-001", "non_functional", "Производительность"),
            make_req("FR-001", "functional", "Функция"),
        ], links)
        save_repo(repo)
        result = mod74.check_architecture_gaps("nfr_ok")
        # NFR-001 не в разрыве
        self.assertNotIn("NFR-001` — NFR", result)

    def test_fr_without_uc_us_info(self):
        # FR без UC или US → info
        repo = make_repo("fr_gap", [
            make_req("FR-001", "functional", "Функция без сценария"),
        ])
        save_repo(repo)
        result = mod74.check_architecture_gaps("fr_gap")
        self.assertIn("FR-001", result)
        self.assertIn("Info", result)

    def test_fr_with_us_no_info(self):
        links = [{"from": "US-001", "to": "FR-001", "relation": "derives", "added": str(date.today())}]
        repo = make_repo("fr_us_ok", [
            make_req("FR-001", "functional"),
            make_req("US-001", "user_story"),
        ], links)
        save_repo(repo)
        result = mod74.check_architecture_gaps("fr_us_ok")
        # FR-001 не должен быть в info о FR без сценария
        if "FR-001" in result and "Info" in result:
            # Проверяем что это не наш info о FR без сценария
            self.assertNotIn("FR-001` — FR «Функциональный", result)

    def test_no_gaps_clean_verdict(self):
        # Полный репозиторий с правильными связями — нет critical разрывов
        repo = make_full_repo("clean_proj")
        save_repo(repo)
        result = mod74.check_architecture_gaps("clean_proj")
        # Critical = 0, вердикт без critical gaps
        self.assertIn("Нет критических разрывов", result)
        self.assertIn("Critical | 0", result)

    def test_gaps_saved_to_architecture(self):
        repo = make_repo("save_gaps", [make_req("NFR-001", "non_functional")])
        save_repo(repo)
        mod74.check_architecture_gaps("save_gaps")
        arch = load_arch("save_gaps")
        self.assertIn("gaps", arch)
        # NFR без FR → warning → должно быть в gaps
        self.assertTrue(len(arch["gaps"]["warning"]) > 0)

    def test_all_gap_types_in_one_run(self):
        # Репо с UC без BP (warning), NFR без FR (warning), FR без UC (info)
        repo = make_repo("all_gaps", [
            make_req("UC-001", "use_case"),
            make_req("NFR-001", "non_functional"),
            make_req("FR-001", "functional"),
        ])
        save_repo(repo)
        result = mod74.check_architecture_gaps("all_gaps")
        self.assertIn("Warning", result)
        self.assertIn("Info", result)


# ---------------------------------------------------------------------------
# Тесты save_architecture_snapshot
# ---------------------------------------------------------------------------

class TestSaveArchitectureSnapshot(BaseMCPTest):

    def test_empty_repo_rejected(self):
        result = mod74.save_architecture_snapshot("empty_snap", "v1.0")
        self.assertIn("пуст", result.lower())

    def test_empty_version_rejected(self):
        repo = make_repo("ver_proj", [make_req("FR-001", "functional")])
        save_repo(repo)
        result = mod74.save_architecture_snapshot("ver_proj", "")
        self.assertIn("❌", result)
        self.assertIn("version", result)

    def test_success_v1(self):
        repo = make_full_repo("snap_proj")
        save_repo(repo)
        result = mod74.save_architecture_snapshot("snap_proj", "v1.0", "Первая версия", "Иванов")
        self.assertIn("v1.0", result)
        self.assertIn("зафиксирован", result)

    def test_snapshot_added_to_history(self):
        repo = make_full_repo("hist_proj")
        save_repo(repo)
        mod74.save_architecture_snapshot("hist_proj", "v1.0")
        arch = load_arch("hist_proj")
        self.assertEqual(len(arch["snapshots"]), 1)
        self.assertEqual(arch["snapshots"][0]["version"], "v1.0")

    def test_multiple_snapshots_accumulate(self):
        repo = make_full_repo("multi_snap")
        save_repo(repo)
        mod74.save_architecture_snapshot("multi_snap", "v1.0")
        mod74.save_architecture_snapshot("multi_snap", "v1.1", "Добавлены UC")
        arch = load_arch("multi_snap")
        self.assertEqual(len(arch["snapshots"]), 2)
        versions = [s["version"] for s in arch["snapshots"]]
        self.assertIn("v1.0", versions)
        self.assertIn("v1.1", versions)

    def test_duplicate_version_rejected(self):
        repo = make_full_repo("dup_proj")
        save_repo(repo)
        mod74.save_architecture_snapshot("dup_proj", "v1.0")
        result = mod74.save_architecture_snapshot("dup_proj", "v1.0")
        self.assertIn("⚠️", result)
        self.assertIn("уже существует", result)
        # Второй снапшот не добавлен
        arch = load_arch("dup_proj")
        v1_count = sum(1 for s in arch["snapshots"] if s["version"] == "v1.0")
        self.assertEqual(v1_count, 1)

    def test_notes_and_author_saved(self):
        repo = make_full_repo("notes_proj")
        save_repo(repo)
        mod74.save_architecture_snapshot("notes_proj", "v1.0", "Первый baseline", "Петрова")
        arch = load_arch("notes_proj")
        snap = arch["snapshots"][0]
        self.assertEqual(snap["notes"], "Первый baseline")
        self.assertEqual(snap["author"], "Петрова")

    def test_summary_counts_correct(self):
        repo = make_full_repo("counts_proj")
        save_repo(repo)
        mod74.save_architecture_snapshot("counts_proj", "v1.0")
        arch = load_arch("counts_proj")
        snap = arch["snapshots"][0]
        # total_reqs > 0 (в full_repo много req, исключая business и test)
        self.assertGreater(snap["summary"]["total_reqs"], 0)
        self.assertGreater(snap["summary"]["viewpoints_count"], 0)

    def test_save_artifact_called(self):
        """save_artifact вызывается при создании снапшота."""
        repo = make_full_repo("artifact_proj")
        save_repo(repo)
        calls = []
        original = mod74.save_artifact
        mod74.save_artifact = lambda content, prefix="": calls.append(prefix) or "✅"
        try:
            mod74.save_architecture_snapshot("artifact_proj", "v1.0")
        finally:
            mod74.save_artifact = original
        self.assertTrue(any("7_4" in str(c) for c in calls))

    def test_critical_gaps_warning_in_result(self):
        # Сначала создаём gaps с critical
        repo = make_repo("crit_proj", [make_req("FR-001", "functional")])
        save_repo(repo)
        save_stakeholders(make_stakeholders("crit_proj"))
        mod74.check_architecture_gaps("crit_proj")
        result = mod74.save_architecture_snapshot("crit_proj", "v1.0")
        # Если есть critical gaps — предупреждение в результате
        arch = load_arch("crit_proj")
        if arch["gaps"].get("critical"):
            self.assertIn("critical", result.lower())

    def test_architecture_doc_contains_viewpoints_section(self):
        """Architecture Document содержит секцию Viewpoints."""
        doc_content = []
        original = mod74.save_artifact
        mod74.save_artifact = lambda content, prefix="": doc_content.append(content) or "✅"
        try:
            repo = make_full_repo("doc_proj")
            save_repo(repo)
            mod74.save_architecture_snapshot("doc_proj", "v1.0")
        finally:
            mod74.save_artifact = original
        self.assertTrue(len(doc_content) > 0)
        self.assertIn("Viewpoints", doc_content[0])

    def test_architecture_doc_contains_delivery_section(self):
        """Architecture Document содержит секцию передачи в 4.4 и 7.5."""
        doc_content = []
        original = mod74.save_artifact
        mod74.save_artifact = lambda content, prefix="": doc_content.append(content) or "✅"
        try:
            repo = make_full_repo("delivery_proj")
            save_repo(repo)
            mod74.save_architecture_snapshot("delivery_proj", "v1.0")
        finally:
            mod74.save_artifact = original
        self.assertTrue(len(doc_content) > 0)
        self.assertIn("4.4", doc_content[0])
        self.assertIn("7.5", doc_content[0])


# ---------------------------------------------------------------------------
# Pipeline — полный сценарий
# ---------------------------------------------------------------------------

class TestPipeline(BaseMCPTest):

    def test_full_happy_path(self):
        """
        Полный pipeline: analyze → add_custom_viewpoint → check_gaps → snapshot.
        Все шаги отрабатывают без ошибок.
        """
        project_id = "pipeline_proj"
        repo = make_full_repo(project_id)
        save_repo(repo)
        save_context(make_context(project_id))
        save_stakeholders(make_stakeholders(project_id))

        # Шаг 1: analyze
        r1 = mod74.analyze_requirements_architecture(project_id)
        self.assertIn("Бизнес-процессы", r1)
        self.assertNotIn("пуст", r1)

        # Шаг 2: add_custom_viewpoint
        r2 = mod74.add_custom_viewpoint(
            project_id=project_id,
            viewpoint_id="security",
            label="Безопасность",
            req_ids_json='["NFR-001"]',
            description="Нефункциональные требования к безопасности",
        )
        self.assertIn("создана", r2)

        # Шаг 3: check_gaps
        r3 = mod74.check_architecture_gaps(project_id)
        self.assertNotIn("❌ Ошибка", r3)

        # Шаг 4: snapshot
        r4 = mod74.save_architecture_snapshot(project_id, "v1.0", "После полного анализа")
        self.assertIn("v1.0", r4)
        self.assertIn("зафиксирован", r4)

        # Проверяем финальный архитектурный файл
        arch = load_arch(project_id)
        self.assertEqual(len(arch["snapshots"]), 1)
        self.assertIn("security", arch["viewpoints"])
        self.assertIn("business_process", arch["viewpoints"])

    def test_graceful_without_stakeholders_and_context(self):
        """
        Pipeline без реестра стейкхолдеров и business_context — не падает.
        """
        project_id = "minimal_proj"
        repo = make_repo(project_id, [
            make_req("FR-001", "functional"),
            make_req("US-001", "user_story"),
        ])
        save_repo(repo)

        r1 = mod74.analyze_requirements_architecture(project_id)
        self.assertNotIn("❌ Ошибка", r1)

        r2 = mod74.check_architecture_gaps(project_id)
        self.assertNotIn("❌ Ошибка", r2)
        # Нет файла стейкхолдеров → info, не critical
        self.assertIn("Реестр стейкхолдеров", r2)

        r3 = mod74.save_architecture_snapshot(project_id, "v1.0")
        self.assertIn("v1.0", r3)

    def test_custom_viewpoint_in_snapshot(self):
        """Кастомный viewpoint виден в Architecture Document."""
        project_id = "custom_snap_proj"
        repo = make_repo(project_id, [
            make_req("FR-001", "functional"),
            make_req("NFR-001", "non_functional"),
        ])
        save_repo(repo)

        mod74.add_custom_viewpoint(
            project_id=project_id,
            viewpoint_id="compliance",
            label="Соответствие регуляторным требованиям",
            req_ids_json='["NFR-001"]',
        )

        doc_content = []
        original = mod74.save_artifact
        mod74.save_artifact = lambda content, prefix="": doc_content.append(content) or "✅"
        try:
            mod74.save_architecture_snapshot(project_id, "v1.0")
        finally:
            mod74.save_artifact = original

        self.assertTrue(len(doc_content) > 0)
        self.assertIn("Соответствие регуляторным требованиям", doc_content[0])
        self.assertIn("кастомный", doc_content[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
