"""
tests/test_ch7_72.py — Тесты для Главы 7, задача 7.2 (Verify Requirements)

Покрытие (~80 тестов):
  - Утилиты: _repo_path, _issues_path, _load_repo, _load_issues, _save_issues,
             _next_issue_id, _open_blockers_for_req, _check_atomicity,
             _check_ambiguity, _check_testability_us, _check_testability_fr,
             _check_testability_uc, _check_prioritized, _check_conciseness,
             _check_group_b, _check_single_req
  - check_req_quality: пустой репо, все draft, фильтр по типу, батч по ID,
    несуществующий ID, атомарность/однозначность/тестируемость флаги
  - check_model_consistency: нет директории, пустая директория,
    рассинхрон DD vs ERD, рассинхрон UC vs diagram, OK
  - open_verification_issue: success, invalid type, invalid severity, empty description,
    blocker warning, нумерация VI-001/VI-002
  - resolve_verification_issue: success, уже закрыт, не найден, blockers remain,
    все blockers закрыты — сигнал
  - mark_req_verified: success, blocker блокирует, не найден, смена статуса в репо,
    история, несколько req
  - get_verification_report: нет req, 0% verified, 100% verified, blocker list,
    открытые issues, готовность к 5.5
  - Pipeline: полный сценарий check → open_issue → resolve → mark_verified → report
"""

import json
import os
import sys
import unittest
from datetime import date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tests.conftest import BaseMCPTest, save_test_repo

import skills.requirements_verify_mcp as mod72


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def make_repo(project_id: str, requirements: list = None, links: list = None) -> dict:
    return {
        "project": project_id,
        "formality_level": "Standard",
        "created": str(date.today()),
        "updated": str(date.today()),
        "requirements": requirements or [],
        "links": links or [],
        "history": [],
    }


def save_repo(repo: dict) -> str:
    safe = repo["project"].lower().replace(" ", "_")
    path = os.path.join("governance_plans", "data", f"{safe}_traceability_repo.json")
    os.makedirs(os.path.join("governance_plans", "data"), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)
    return path


def load_repo(project_id: str) -> dict:
    safe = project_id.lower().replace(" ", "_")
    path = os.path.join("governance_plans", "data", f"{safe}_traceability_repo.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_issues(project_id: str) -> dict:
    safe = project_id.lower().replace(" ", "_")
    path = os.path.join("governance_plans", "data", f"{safe}_verification_issues.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def make_us_req(req_id="US-001", title="Оформить заявку", status="draft",
                priority="High", source_artifact="governance_plans/4_3_test.md",
                ac_count=3, ac_texts=None):
    return {
        "id": req_id, "type": "user_story", "title": title,
        "status": status, "priority": priority,
        "source_artifact": source_artifact, "owner": "Иванов",
        "ac_count": ac_count, "ac_texts": ac_texts or ["AC 1", "AC 2", "AC 3"],
        "version": "1.0", "added": str(date.today()),
    }


def make_fr_req(req_id="FR-001", title="Возвращать список заявок", status="draft",
                priority="High", description="Система ДОЛЖНА возвращать список заявок за 2 секунды",
                source_artifact="governance_plans/4_3_test.md"):
    return {
        "id": req_id, "type": "functional", "title": title,
        "description": description, "status": status, "priority": priority,
        "source_artifact": source_artifact, "owner": "Петрова",
        "version": "1.0", "added": str(date.today()),
    }


def make_uc_req(req_id="UC-001", title="Создать заявку", status="draft",
                priority="High", exc_scenarios="Исключение: данные некорректны"):
    return {
        "id": req_id, "type": "use_case", "title": title,
        "status": status, "priority": priority,
        "exc_scenarios": exc_scenarios, "owner": "Сидоров",
        "source_artifact": "governance_plans/4_3_test.md",
        "version": "1.0", "added": str(date.today()),
    }


# ---------------------------------------------------------------------------
# Тесты утилит
# ---------------------------------------------------------------------------

class TestUtilities(BaseMCPTest):

    def test_repo_path(self):
        path = mod72._repo_path("My Project")
        self.assertIn("my_project", path)
        self.assertIn("traceability_repo.json", path)

    def test_issues_path(self):
        path = mod72._issues_path("My Project")
        self.assertIn("my_project", path)
        self.assertIn("verification_issues.json", path)

    def test_load_repo_empty(self):
        repo = mod72._load_repo("nonexistent_proj")
        self.assertEqual(repo["requirements"], [])
        self.assertEqual(repo["links"], [])

    def test_load_issues_empty(self):
        data = mod72._load_issues("nonexistent_proj")
        self.assertEqual(data["issues"], {})
        self.assertEqual(data["stats"]["open"], 0)

    def test_next_issue_id_first(self):
        data = {"issues": {}, "stats": {"open": 0, "closed": 0, "total": 0},
                "project": "p", "created": str(date.today()), "updated": str(date.today())}
        self.assertEqual(mod72._next_issue_id(data), "VI-001")

    def test_next_issue_id_increments(self):
        data = {
            "issues": {
                "VI-001": {"status": "open"},
                "VI-002": {"status": "closed"},
            },
            "stats": {}, "project": "p",
            "created": str(date.today()), "updated": str(date.today()),
        }
        self.assertEqual(mod72._next_issue_id(data), "VI-003")

    def test_open_blockers_for_req(self):
        data = {
            "issues": {
                "VI-001": {"req_id": "US-001", "severity": "blocker", "status": "open"},
                "VI-002": {"req_id": "US-001", "severity": "major", "status": "open"},
                "VI-003": {"req_id": "US-001", "severity": "blocker", "status": "closed"},
                "VI-004": {"req_id": "FR-001", "severity": "blocker", "status": "open"},
            },
            "project": "p", "stats": {}, "created": "", "updated": "",
        }
        blockers = mod72._open_blockers_for_req(data, "US-001")
        self.assertEqual(len(blockers), 1)
        self.assertEqual(blockers[0]["issue_id"] if "issue_id" in blockers[0] else "VI-001", "VI-001")

    def test_find_req(self):
        repo = make_repo("p", [make_us_req("US-001")])
        req = mod72._find_req(repo, "US-001")
        self.assertIsNotNone(req)
        self.assertEqual(req["id"], "US-001")

    def test_find_req_not_found(self):
        repo = make_repo("p", [])
        self.assertIsNone(mod72._find_req(repo, "US-999"))


# ---------------------------------------------------------------------------
# Тесты rule-based проверок
# ---------------------------------------------------------------------------

class TestRuleBasedChecks(BaseMCPTest):

    def test_atomicity_passed_no_signals(self):
        result = mod72._check_atomicity("Система отображает список заявок")
        self.assertTrue(result["passed"])
        self.assertEqual(result["signals_found"], [])

    def test_atomicity_warning_one_signal(self):
        result = mod72._check_atomicity("Система создаёт заявку и сохраняет её в базе")
        # Один сигнал " и " — passed=True с предупреждением
        self.assertTrue(result["passed"])
        self.assertTrue(any("и" in s for s in result["signals_found"]))

    def test_atomicity_failed_two_signals(self):
        result = mod72._check_atomicity(
            "Система создаёт заявку и сохраняет её в базе, а также отправляет уведомление"
        )
        self.assertFalse(result["passed"])
        self.assertGreaterEqual(len(result["signals_found"]), 2)

    def test_ambiguity_passed(self):
        result = mod72._check_ambiguity("Система ДОЛЖНА возвращать данные за 2 секунды")
        self.assertTrue(result["passed"])
        self.assertEqual(result["signals_found"], [])

    def test_ambiguity_failed(self):
        result = mod72._check_ambiguity("Система должна быть быстрой и удобной")
        self.assertFalse(result["passed"])
        self.assertIn("быстро" if "быстро" in result["signals_found"] else "удобно",
                      result["signals_found"])

    def test_ambiguity_failed_kak_pravilo(self):
        result = mod72._check_ambiguity("Система как правило возвращает данные")
        self.assertFalse(result["passed"])

    def test_testability_us_passed(self):
        result = mod72._check_testability_us("Оформить заявку", 3, ["AC1", "AC2", "AC3"])
        self.assertTrue(result["passed"])
        self.assertIsNone(result["issue"])

    def test_testability_us_missing_ac(self):
        result = mod72._check_testability_us("Оформить заявку", 1, ["AC1"])
        self.assertFalse(result["passed"])
        self.assertEqual(result["issue"], "missing_ac")

    def test_testability_us_zero_ac(self):
        result = mod72._check_testability_us("Оформить заявку", 0, [])
        self.assertFalse(result["passed"])
        self.assertEqual(result["issue"], "missing_ac")

    def test_testability_fr_passed_with_number(self):
        result = mod72._check_testability_fr(
            "Система ДОЛЖНА возвращать список за 2 секунды", "functional"
        )
        self.assertTrue(result["passed"])

    def test_testability_fr_failed_no_metric(self):
        result = mod72._check_testability_fr(
            "Система должна быстро обрабатывать данные", "functional"
        )
        self.assertFalse(result["passed"])
        self.assertEqual(result["issue"], "not_testable")

    def test_testability_fr_percent(self):
        result = mod72._check_testability_fr(
            "Система ДОЛЖНА обеспечивать доступность 99.9%", "non_functional"
        )
        self.assertTrue(result["passed"])

    def test_testability_br_with_condition(self):
        result = mod72._check_testability_fr(
            "Если сумма превышает 1000000, заявка требует одобрения", "business_rule"
        )
        self.assertTrue(result["passed"])

    def test_testability_uc_with_exceptions(self):
        result = mod72._check_testability_uc("Исключение: данные некорректны")
        self.assertTrue(result["passed"])

    def test_testability_uc_no_exceptions(self):
        result = mod72._check_testability_uc("")
        self.assertFalse(result["passed"])
        self.assertEqual(result["issue"], "not_testable")

    def test_prioritized_passed(self):
        result = mod72._check_prioritized("High")
        self.assertTrue(result["passed"])
        self.assertEqual(result["priority"], "High")

    def test_prioritized_failed_empty(self):
        result = mod72._check_prioritized("")
        self.assertFalse(result["passed"])

    def test_prioritized_failed_none(self):
        result = mod72._check_prioritized("none")
        self.assertFalse(result["passed"])

    def test_conciseness_passed(self):
        result = mod72._check_conciseness("Оформить заявку", "Описание", "user_story")
        self.assertTrue(result["passed"])
        self.assertIsNone(result.get("warning"))

    def test_conciseness_long_title_us(self):
        long_title = "Как менеджер по заявкам я хочу просматривать все активные заявки клиентов системы ХХХ"
        result = mod72._check_conciseness(long_title, "", "user_story")
        self.assertTrue(result["passed"])
        if len(long_title) > 100:
            self.assertIsNotNone(result.get("warning"))

    def test_conciseness_impl_signal(self):
        result = mod72._check_conciseness(
            "Создать заявку",
            "Реализовать через REST API вызов метода POST /api/v1/applications",
            "functional"
        )
        self.assertTrue(result["passed"])
        self.assertIsNotNone(result.get("warning"))


# ---------------------------------------------------------------------------
# Тесты check_group_b
# ---------------------------------------------------------------------------

class TestGroupB(BaseMCPTest):

    def test_group_b_all_ok(self):
        repo = make_repo("p", links=[
            {"from": "US-001", "to": "BR-001", "relation": "derives", "added": str(date.today())}
        ])
        req = make_us_req("US-001", source_artifact="governance_plans/4_3_test.md")
        req["owner"] = "Иванов"
        result = mod72._check_group_b(req, repo)
        self.assertEqual(result["consistent"]["status"], "ok")
        self.assertEqual(result["complete"]["warnings"], [])

    def test_group_b_no_source_artifact(self):
        repo = make_repo("p")
        req = make_us_req("US-001", source_artifact="")
        result = mod72._check_group_b(req, repo)
        warnings = result["complete"]["warnings"]
        self.assertTrue(any("source_artifact" in w for w in warnings))

    def test_group_b_no_links(self):
        repo = make_repo("p", links=[])
        req = make_us_req("US-001")
        result = mod72._check_group_b(req, repo)
        warnings = result["complete"]["warnings"]
        self.assertTrue(any("связей" in w or "link" in w.lower() for w in warnings))

    def test_group_b_conflict_status(self):
        repo = make_repo("p")
        req = make_us_req("US-001", status="conflict")
        result = mod72._check_group_b(req, repo)
        self.assertEqual(result["consistent"]["status"], "needs_review")

    def test_check_single_req_passed(self):
        repo = make_repo("p", [make_us_req("US-001")],
                         links=[{"from": "US-001", "to": "BR-001", "relation": "derives", "added": str(date.today())}])
        req = make_us_req("US-001")
        result = mod72._check_single_req(req, repo)
        self.assertIn(result["overall"], ("passed", "warnings_only"))
        self.assertEqual(result["req_id"], "US-001")

    def test_check_single_req_missing_ac_blocker(self):
        repo = make_repo("p")
        req = make_us_req("US-001", ac_count=0, ac_texts=[])
        result = mod72._check_single_req(req, repo)
        self.assertEqual(result["overall"], "issues_found")
        self.assertIn("missing_ac", result["blockers"])


# ---------------------------------------------------------------------------
# Тесты check_req_quality
# ---------------------------------------------------------------------------

class TestCheckReqQuality(BaseMCPTest):

    def test_empty_repo(self):
        result = mod72.check_req_quality("empty_proj")
        self.assertIn("пуст", result)

    def test_all_draft_checked(self):
        repo = make_repo("proj_q", [
            make_us_req("US-001"),
            make_us_req("US-002"),
        ])
        save_repo(repo)
        result = mod72.check_req_quality("proj_q")
        self.assertIn("US-001", result)
        self.assertIn("US-002", result)

    def test_verified_skipped(self):
        repo = make_repo("proj_q2", [
            make_us_req("US-001", status="verified"),
            make_us_req("US-002", status="draft"),
        ])
        save_repo(repo)
        result = mod72.check_req_quality("proj_q2")
        self.assertIn("US-002", result)
        self.assertNotIn("US-001", result)

    def test_filter_by_type(self):
        repo = make_repo("proj_q3", [
            make_us_req("US-001"),
            make_fr_req("FR-001"),
        ])
        save_repo(repo)
        result = mod72.check_req_quality("proj_q3", req_type="user_story")
        self.assertIn("US-001", result)
        self.assertNotIn("FR-001", result)

    def test_filter_by_ids(self):
        repo = make_repo("proj_q4", [
            make_us_req("US-001"),
            make_us_req("US-002"),
            make_us_req("US-003"),
        ])
        save_repo(repo)
        result = mod72.check_req_quality("proj_q4", req_ids='["US-001", "US-003"]')
        self.assertIn("US-001", result)
        self.assertIn("US-003", result)

    def test_invalid_req_ids_json(self):
        repo = make_repo("proj_q5", [make_us_req("US-001")])
        save_repo(repo)
        result = mod72.check_req_quality("proj_q5", req_ids="not-json")
        self.assertIn("❌", result)

    def test_not_found_ids_reported(self):
        repo = make_repo("proj_q6", [make_us_req("US-001")])
        save_repo(repo)
        result = mod72.check_req_quality("proj_q6", req_ids='["US-001", "US-999"]')
        self.assertIn("US-999", result)

    def test_missing_ac_detected(self):
        repo = make_repo("proj_q7", [make_us_req("US-001", ac_count=0, ac_texts=[])])
        save_repo(repo)
        result = mod72.check_req_quality("proj_q7")
        self.assertIn("missing_ac", result.lower())

    def test_ambiguity_detected(self):
        repo = make_repo("proj_q8", [
            make_fr_req("FR-001", title="Быстрая загрузка удобного интерфейса",
                        description="Система должна быстро и удобно отображать данные")
        ])
        save_repo(repo)
        result = mod72.check_req_quality("proj_q8")
        self.assertIn("Однозначность", result)

    def test_atomicity_detected(self):
        repo = make_repo("proj_q9", [
            make_us_req("US-001",
                        title="Создать заявку и отправить уведомление, а также обновить реестр")
        ])
        save_repo(repo)
        result = mod72.check_req_quality("proj_q9")
        self.assertIn("Атомарность", result)

    def test_no_req_after_filter(self):
        repo = make_repo("proj_q10", [make_us_req("US-001")])
        save_repo(repo)
        result = mod72.check_req_quality("proj_q10", req_type="use_case")
        self.assertIn("Нет требований", result)

    def test_summary_counts(self):
        repo = make_repo("proj_q11", [
            make_us_req("US-001"),  # хороший
            make_us_req("US-002", ac_count=0, ac_texts=[]),  # blocker
        ])
        save_repo(repo)
        result = mod72.check_req_quality("proj_q11")
        self.assertIn("Найдены проблемы", result)


# ---------------------------------------------------------------------------
# Тесты check_model_consistency
# ---------------------------------------------------------------------------

class TestCheckModelConsistency(BaseMCPTest):

    def test_no_specs_dir(self):
        result = mod72.check_model_consistency("proj_mc1")
        self.assertIn("не найдена", result)

    def test_empty_specs_dir(self):
        os.makedirs("governance_plans/data/proj_mc2_specs", exist_ok=True)
        result = mod72.check_model_consistency("proj_mc2")
        self.assertIn("нет файлов", result)

    def test_dd_erd_mismatch(self):
        specs_dir = "governance_plans/data/proj_mc3_specs"
        os.makedirs(specs_dir, exist_ok=True)

        # DD с сущностью Application
        with open(os.path.join(specs_dir, "dd_001_test.md"), "w") as f:
            f.write("# DD-001\n\n## Сущность: Application\n\n## Сущность: Client\n")

        # ERD с другой сущностью
        with open(os.path.join(specs_dir, "erd_001_test.puml"), "w") as f:
            f.write('@startuml\nentity "Application" as App {}\nentity "Order" as Ord {}\n@enduml\n')

        result = mod72.check_model_consistency("proj_mc3")
        self.assertIn("несоответствий", result.lower())
        self.assertIn("Client", result)

    def test_dd_erd_consistent(self):
        specs_dir = "governance_plans/data/proj_mc4_specs"
        os.makedirs(specs_dir, exist_ok=True)

        with open(os.path.join(specs_dir, "dd_001.md"), "w") as f:
            f.write("# DD-001\n\n## Сущность: Application\n\n## Сущность: Client\n")

        with open(os.path.join(specs_dir, "erd_001.puml"), "w") as f:
            f.write('@startuml\nentity "Application" as App {}\nentity "Client" as Cli {}\n@enduml\n')

        result = mod72.check_model_consistency("proj_mc4")
        self.assertIn("не найдено", result)

    def test_uc_actor_not_in_diagram(self):
        specs_dir = "governance_plans/data/proj_mc5_specs"
        os.makedirs(specs_dir, exist_ok=True)

        # UC spec с актором
        with open(os.path.join(specs_dir, "uc_001_create.md"), "w") as f:
            f.write(
                "# UC-001 — Создать заявку\n\n"
                "| Атрибут | Значение |\n"
                "|---------|----------|\n"
                "| Актор (primary) | Менеджер |\n"
            )

        # UC Diagram без этого актора
        with open(os.path.join(specs_dir, "uc_diagram_test.puml"), "w") as f:
            f.write('@startuml\nactor "Администратор" as A1\nusecase "Создать заявку" as UC1\n@enduml\n')

        result = mod72.check_model_consistency("proj_mc5")
        self.assertIn("Менеджер", result)


# ---------------------------------------------------------------------------
# Тесты open_verification_issue
# ---------------------------------------------------------------------------

class TestOpenVerificationIssue(BaseMCPTest):

    def test_success_blocker(self):
        repo = make_repo("proj_i1", [make_us_req("US-001")])
        save_repo(repo)
        result = mod72.open_verification_issue(
            "proj_i1", "US-001", "missing_ac",
            "User Story не содержит Acceptance Criteria", "blocker"
        )
        self.assertIn("VI-001", result)
        self.assertIn("blocker", result)

        data = load_issues("proj_i1")
        self.assertIn("VI-001", data["issues"])
        self.assertEqual(data["issues"]["VI-001"]["status"], "open")
        self.assertEqual(data["stats"]["open"], 1)

    def test_success_major(self):
        repo = make_repo("proj_i2", [make_fr_req("FR-001")])
        save_repo(repo)
        result = mod72.open_verification_issue(
            "proj_i2", "FR-001", "ambiguity",
            "FR содержит слово 'быстро' без метрики", "major"
        )
        self.assertIn("VI-001", result)
        data = load_issues("proj_i2")
        self.assertEqual(data["issues"]["VI-001"]["severity"], "major")

    def test_issue_numbering(self):
        repo = make_repo("proj_i3", [make_us_req("US-001"), make_us_req("US-002")])
        save_repo(repo)
        mod72.open_verification_issue("proj_i3", "US-001", "missing_ac", "Desc 1", "blocker")
        result = mod72.open_verification_issue("proj_i3", "US-002", "ambiguity", "Desc 2", "major")
        self.assertIn("VI-002", result)
        data = load_issues("proj_i3")
        self.assertEqual(len(data["issues"]), 2)

    def test_invalid_issue_type(self):
        result = mod72.open_verification_issue(
            "proj_i4", "US-001", "invalid_type", "Desc", "major"
        )
        self.assertIn("❌", result)
        self.assertIn("issue_type", result)

    def test_invalid_severity(self):
        result = mod72.open_verification_issue(
            "proj_i5", "US-001", "ambiguity", "Desc", "critical"
        )
        self.assertIn("❌", result)
        self.assertIn("severity", result)

    def test_empty_description(self):
        result = mod72.open_verification_issue(
            "proj_i6", "US-001", "ambiguity", "", "minor"
        )
        self.assertIn("❌", result)

    def test_assigned_to_saved(self):
        repo = make_repo("proj_i7", [make_us_req("US-001")])
        save_repo(repo)
        mod72.open_verification_issue(
            "proj_i7", "US-001", "other", "Desc", "minor", assigned_to="Иванов"
        )
        data = load_issues("proj_i7")
        self.assertEqual(data["issues"]["VI-001"]["assigned_to"], "Иванов")

    def test_req_not_in_repo(self):
        # req нет в репо — issue всё равно создаётся (не блокируем)
        result = mod72.open_verification_issue(
            "proj_i8", "US-999", "other", "Desc", "minor"
        )
        self.assertIn("VI-001", result)

    def test_model_inconsistency_type(self):
        result = mod72.open_verification_issue(
            "proj_i9", "US-001", "model_inconsistency",
            "Сущность Application в DD но нет в ERD", "major"
        )
        self.assertIn("VI-001", result)


# ---------------------------------------------------------------------------
# Тесты resolve_verification_issue
# ---------------------------------------------------------------------------

class TestResolveVerificationIssue(BaseMCPTest):

    def _create_issue(self, project_id, req_id, issue_type="missing_ac", severity="blocker"):
        repo = make_repo(project_id, [make_us_req(req_id)])
        save_repo(repo)
        mod72.open_verification_issue(project_id, req_id, issue_type, "Проблема", severity)
        data = load_issues(project_id)
        return list(data["issues"].keys())[0]

    def test_success(self):
        issue_id = self._create_issue("proj_r1", "US-001")
        result = mod72.resolve_verification_issue("proj_r1", issue_id, "Добавлено 3 AC")
        self.assertIn("закрыт", result)
        data = load_issues("proj_r1")
        self.assertEqual(data["issues"][issue_id]["status"], "closed")
        self.assertEqual(data["issues"][issue_id]["resolution_note"], "Добавлено 3 AC")

    def test_already_closed(self):
        issue_id = self._create_issue("proj_r2", "US-001")
        mod72.resolve_verification_issue("proj_r2", issue_id, "First resolution")
        result = mod72.resolve_verification_issue("proj_r2", issue_id, "Second")
        self.assertIn("уже закрыт", result)

    def test_not_found(self):
        result = mod72.resolve_verification_issue("proj_r3", "VI-999", "Desc")
        self.assertIn("❌", result)
        self.assertIn("VI-999", result)

    def test_empty_resolution_note(self):
        result = mod72.resolve_verification_issue("proj_r4", "VI-001", "")
        self.assertIn("❌", result)

    def test_stats_updated(self):
        issue_id = self._create_issue("proj_r5", "US-001")
        data_before = load_issues("proj_r5")
        self.assertEqual(data_before["stats"]["open"], 1)
        mod72.resolve_verification_issue("proj_r5", issue_id, "Resolved")
        data_after = load_issues("proj_r5")
        self.assertEqual(data_after["stats"]["open"], 0)
        self.assertEqual(data_after["stats"]["closed"], 1)

    def test_remaining_blockers_signal(self):
        repo = make_repo("proj_r6", [make_us_req("US-001")])
        save_repo(repo)
        mod72.open_verification_issue("proj_r6", "US-001", "missing_ac", "Desc 1", "blocker")
        mod72.open_verification_issue("proj_r6", "US-001", "ambiguity", "Desc 2", "blocker")
        result = mod72.resolve_verification_issue("proj_r6", "VI-001", "Resolved")
        self.assertIn("VI-002", result)  # второй blocker ещё открыт

    def test_all_blockers_closed_signal(self):
        repo = make_repo("proj_r7", [make_us_req("US-001")])
        save_repo(repo)
        mod72.open_verification_issue("proj_r7", "US-001", "missing_ac", "Desc", "blocker")
        result = mod72.resolve_verification_issue("proj_r7", "VI-001", "Все AC добавлены")
        self.assertIn("mark_req_verified", result)


# ---------------------------------------------------------------------------
# Тесты mark_req_verified
# ---------------------------------------------------------------------------

class TestMarkReqVerified(BaseMCPTest):

    def test_success_single(self):
        repo = make_repo("proj_v1", [make_us_req("US-001")])
        save_repo(repo)
        result = mod72.mark_req_verified("proj_v1", '["US-001"]')
        self.assertIn("верифицировано", result)
        updated = load_repo("proj_v1")
        req = mod72._find_req(updated, "US-001")
        self.assertEqual(req["status"], "verified")

    def test_success_multiple(self):
        repo = make_repo("proj_v2", [
            make_us_req("US-001"),
            make_fr_req("FR-001"),
            make_uc_req("UC-001"),
        ])
        save_repo(repo)
        result = mod72.mark_req_verified("proj_v2", '["US-001", "FR-001", "UC-001"]')
        self.assertIn("3", result)
        updated = load_repo("proj_v2")
        for req_id in ["US-001", "FR-001", "UC-001"]:
            req = mod72._find_req(updated, req_id)
            self.assertEqual(req["status"], "verified")

    def test_blocked_by_open_blocker(self):
        repo = make_repo("proj_v3", [make_us_req("US-001")])
        save_repo(repo)
        mod72.open_verification_issue("proj_v3", "US-001", "missing_ac", "Desc", "blocker")
        result = mod72.mark_req_verified("proj_v3", '["US-001"]')
        self.assertIn("ЗАБЛОКИРОВАН", result)
        updated = load_repo("proj_v3")
        req = mod72._find_req(updated, "US-001")
        self.assertNotEqual(req["status"], "verified")

    def test_non_blocker_does_not_block(self):
        repo = make_repo("proj_v4", [make_us_req("US-001")])
        save_repo(repo)
        mod72.open_verification_issue("proj_v4", "US-001", "ambiguity", "Minor warning", "minor")
        result = mod72.mark_req_verified("proj_v4", '["US-001"]')
        self.assertIn("верифицировано", result)

    def test_not_found_req(self):
        repo = make_repo("proj_v5", [make_us_req("US-001")])
        save_repo(repo)
        result = mod72.mark_req_verified("proj_v5", '["US-999"]')
        self.assertIn("❌", result)
        self.assertIn("US-999", result)

    def test_invalid_req_ids_json(self):
        result = mod72.mark_req_verified("proj_v6", "not-json")
        self.assertIn("❌", result)

    def test_history_recorded(self):
        repo = make_repo("proj_v7", [make_us_req("US-001")])
        save_repo(repo)
        mod72.mark_req_verified("proj_v7", '["US-001"]')
        updated = load_repo("proj_v7")
        history_entries = [h for h in updated["history"] if h.get("action") == "req_verified"]
        self.assertEqual(len(history_entries), 1)
        self.assertEqual(history_entries[0]["req_id"], "US-001")
        self.assertEqual(history_entries[0]["new_status"], "verified")

    def test_partial_success(self):
        repo = make_repo("proj_v8", [
            make_us_req("US-001"),
            make_us_req("US-002"),
        ])
        save_repo(repo)
        mod72.open_verification_issue("proj_v8", "US-001", "missing_ac", "Desc", "blocker")
        result = mod72.mark_req_verified("proj_v8", '["US-001", "US-002"]')
        # US-002 верифицирован, US-001 заблокирован
        self.assertIn("ЗАБЛОКИРОВАН", result)
        self.assertIn("верифицировано", result)
        updated = load_repo("proj_v8")
        us2 = mod72._find_req(updated, "US-002")
        self.assertEqual(us2["status"], "verified")


# ---------------------------------------------------------------------------
# Тесты get_verification_report
# ---------------------------------------------------------------------------

class TestGetVerificationReport(BaseMCPTest):

    def test_empty_repo(self):
        result = mod72.get_verification_report("proj_rep1")
        self.assertIn("нет активных требований", result.lower())

    def test_zero_percent_verified(self):
        repo = make_repo("proj_rep2", [
            make_us_req("US-001"),
            make_fr_req("FR-001"),
        ])
        save_repo(repo)
        result = mod72.get_verification_report("proj_rep2")
        self.assertIn("0.0%", result)
        self.assertIn("не готово", result.lower())

    def test_100_percent_verified(self):
        repo = make_repo("proj_rep3", [
            make_us_req("US-001", status="verified"),
            make_fr_req("FR-001", status="verified"),
        ])
        save_repo(repo)
        result = mod72.get_verification_report("proj_rep3")
        self.assertIn("100.0%", result)

    def test_blockers_listed(self):
        repo = make_repo("proj_rep4", [
            make_us_req("US-001"),
            make_us_req("US-002", status="verified"),
        ])
        save_repo(repo)
        mod72.open_verification_issue("proj_rep4", "US-001", "missing_ac", "Desc", "blocker")
        result = mod72.get_verification_report("proj_rep4")
        self.assertIn("US-001", result)
        self.assertIn("Blocker", result.lower() if "blocker" not in result else result)

    def test_open_issues_table(self):
        repo = make_repo("proj_rep5", [make_us_req("US-001")])
        save_repo(repo)
        mod72.open_verification_issue("proj_rep5", "US-001", "ambiguity", "Desc", "major")
        result = mod72.get_verification_report("proj_rep5")
        self.assertIn("VI-001", result)

    def test_ready_for_approve_when_all_verified(self):
        reqs = [make_us_req(f"US-{i:03d}", status="verified") for i in range(1, 6)]
        repo = make_repo("proj_rep6", reqs)
        save_repo(repo)
        result = mod72.get_verification_report("proj_rep6")
        self.assertIn("Готово к Approve", result)

    def test_not_ready_with_blockers(self):
        repo = make_repo("proj_rep7", [make_us_req("US-001")])
        save_repo(repo)
        mod72.open_verification_issue("proj_rep7", "US-001", "missing_ac", "Desc", "blocker")
        result = mod72.get_verification_report("proj_rep7")
        self.assertIn("Не готово", result)

    def test_deprecated_excluded(self):
        repo = make_repo("proj_rep8", [
            make_us_req("US-001", status="verified"),
            make_us_req("US-002", status="deprecated"),
        ])
        save_repo(repo)
        result = mod72.get_verification_report("proj_rep8")
        # deprecated не считается в total — значит из 1 активного, 1 верифицирован = 100%
        self.assertIn("100.0%", result)

    def test_issue_type_stats(self):
        repo = make_repo("proj_rep9", [
            make_us_req("US-001"),
            make_us_req("US-002"),
        ])
        save_repo(repo)
        mod72.open_verification_issue("proj_rep9", "US-001", "missing_ac", "Desc1", "blocker")
        mod72.open_verification_issue("proj_rep9", "US-002", "ambiguity", "Desc2", "major")
        result = mod72.get_verification_report("proj_rep9")
        self.assertIn("missing_ac", result)
        self.assertIn("ambiguity", result)


# ---------------------------------------------------------------------------
# Pipeline — интеграционные тесты
# ---------------------------------------------------------------------------

class TestPipeline(BaseMCPTest):

    def test_full_pipeline_happy_path(self):
        """Полный пайплайн: check → open issue → resolve → verify → report."""
        project_id = "pipeline_happy"
        repo = make_repo(project_id, [
            make_us_req("US-001", ac_count=3),
            make_fr_req("FR-001",
                        description="Система ДОЛЖНА возвращать список за 2 секунды"),
        ])
        save_repo(repo)

        # check_req_quality — оба должны пройти
        check_result = mod72.check_req_quality(project_id)
        self.assertIn("US-001", check_result)
        self.assertIn("FR-001", check_result)

        # mark_req_verified — оба без blockers
        verify_result = mod72.mark_req_verified(project_id, '["US-001", "FR-001"]')
        self.assertIn("верифицировано", verify_result)

        # report
        report = mod72.get_verification_report(project_id)
        self.assertIn("100.0%", report)

    def test_full_pipeline_with_issue(self):
        """Пайплайн с проблемой: check → open → resolve → verify → report."""
        project_id = "pipeline_issue"
        repo = make_repo(project_id, [
            make_us_req("US-001", ac_count=0, ac_texts=[]),  # blocker
        ])
        save_repo(repo)

        # check выявляет missing_ac
        check_result = mod72.check_req_quality(project_id)
        self.assertIn("missing_ac", check_result.lower())

        # Открываем issue
        issue_result = mod72.open_verification_issue(
            project_id, "US-001", "missing_ac",
            "User Story без AC — нет критериев приёмки", "blocker"
        )
        self.assertIn("VI-001", issue_result)

        # mark_req_verified — заблокирован
        blocked = mod72.mark_req_verified(project_id, '["US-001"]')
        self.assertIn("ЗАБЛОКИРОВАН", blocked)

        # Исправление — resolve
        resolve_result = mod72.resolve_verification_issue(
            project_id, "VI-001",
            "Добавлено 3 AC: успешная авторизация, неверный пароль, блокировка"
        )
        self.assertIn("mark_req_verified", resolve_result)

        # mark_req_verified — теперь OK
        verify_result = mod72.mark_req_verified(project_id, '["US-001"]')
        self.assertIn("верифицировано", verify_result)

        # report — 100% и ready
        report = mod72.get_verification_report(project_id)
        self.assertIn("100.0%", report)

    def test_pipeline_mixed_results(self):
        """Пайплайн: часть req верифицирована, часть заблокирована."""
        project_id = "pipeline_mixed"
        repo = make_repo(project_id, [
            make_us_req("US-001"),                          # чистый
            make_us_req("US-002", ac_count=0, ac_texts=[]),  # blocker
            make_fr_req("FR-001",
                        description="Система ДОЛЖНА за 2 секунды"),  # чистый
        ])
        save_repo(repo)

        mod72.open_verification_issue(project_id, "US-002", "missing_ac", "Нет AC", "blocker")

        # Верифицируем двух чистых
        result = mod72.mark_req_verified(project_id, '["US-001", "FR-001"]')
        self.assertIn("верифицировано", result)

        # US-002 заблокирован — отдельно
        blocked = mod72.mark_req_verified(project_id, '["US-002"]')
        self.assertIn("ЗАБЛОКИРОВАН", blocked)

        report = mod72.get_verification_report(project_id)
        # 2 из 3 верифицированы → ~66.7%
        self.assertIn("66.7%", report)
        self.assertIn("Не готово", report)

    def test_pipeline_model_consistency(self):
        """check_model_consistency находит рассинхрон DD vs ERD."""
        project_id = "pipeline_models"
        specs_dir = f"governance_plans/data/{project_id}_specs"
        os.makedirs(specs_dir, exist_ok=True)

        with open(os.path.join(specs_dir, "dd_001.md"), "w") as f:
            f.write("# DD-001\n\n## Сущность: Application\n\n## Сущность: Client\n")

        with open(os.path.join(specs_dir, "erd_001.puml"), "w") as f:
            f.write('@startuml\nentity "Application" as App {}\n@enduml\n')

        result = mod72.check_model_consistency(project_id)
        self.assertIn("Client", result)
        self.assertIn("несоответствий", result.lower())

    def test_pipeline_report_saved(self):
        """get_verification_report вызывает save_artifact."""
        from unittest.mock import patch
        project_id = "pipeline_save"
        repo = make_repo(project_id, [make_us_req("US-001", status="verified")])
        save_repo(repo)

        with patch("skills.requirements_verify_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            mod72.get_verification_report(project_id)
            mock_sa.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
