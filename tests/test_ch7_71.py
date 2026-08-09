"""
tests/test_ch7_71.py — Тесты для Главы 7, задача 7.1 (Specify and Model Requirements)

Покрытие (~70 тестов):
  - Утилиты: _repo_path, _load_repo, _save_repo, _register_in_repo, _specs_dir,
             _find_confirmed_artifact, _save_spec
  - analyze_elicitation_context: файл найден, context_text fallback, оба отсутствуют
  - create_user_story: success, недостаточно AC, плохой JSON, дубль в реестре
  - create_functional_requirement: все три типа, невалидный тип, related_ids
  - create_use_case: success, альтернативы/исключения, без вторичных акторов
  - generate_use_case_diagram: UC есть, UC нет, актор из файла спецификации
  - create_business_process: success, .md и .puml файлы, регистрация
  - create_data_dictionary: success, плохой JSON, пустой список
  - create_erd: success, нотация кардинальности, плохой JSON
  - build_coverage_matrix: с требованиями, без требований, флаги покрытия
  - Интеграция: полный пайплайн (analyze → create → coverage)
"""

import json
import os
import sys
import unittest
from datetime import date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Mocks are applied via conftest
from tests.conftest import (BaseMCPTest, make_test_repo, save_test_repo, load_test_repo,
                            data_file)

import skills.requirements_spec_mcp as mod71
from skills.common import specs_dir
from skills.common import data_path, normalize_project_id, InvalidProjectIdError


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def make_spec_repo(project_id: str, requirements: list = None) -> dict:
    """Создаёт и сохраняет репозиторий 5.1 с заданными требованиями."""
    repo = {
        "project": project_id,
        "formality_level": "Standard",
        "created": str(date.today()),
        "updated": str(date.today()),
        "requirements": requirements or [],
        "links": [],
        "history": [],
    }
    return repo


def save_spec_repo(repo: dict, governance_dir: str = "governance_plans/data") -> str:
    """Saves the 5.1 repository for the tests."""
    path = data_file(repo["project"], "traceability_repo.json", governance_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)
    return path


def load_spec_repo(project_id: str, governance_dir: str = "governance_plans/data") -> dict:
    """Loads the 5.1 repository."""
    safe = normalize_project_id(project_id)
    path = data_path(project_id, f"{safe}_traceability_repo.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def make_confirmed_artifact_reports(project_id: str, content: str = None) -> str:
    """Creates a test 4.3 artifact in the REAL producer layout and returns the path.

    The 4.3 producer (save_confirmed_elicitation_result -> save_artifact) writes to
    reports/<project_id>/4_3_confirmed_result_<timestamp>.md (project_id is the FOLDER,
    NOT part of the filename). This helper reproduces that real contract, unlike the
    legacy make_confirmed_artifact which wrote to a flat data/ with pid in the name.
    """
    from skills.common import report_dir_for
    d = report_dir_for(project_id)
    os.makedirs(d, exist_ok=True)
    filename = "4_3_confirmed_result_20260101_000000.md"
    path = os.path.join(d, filename)
    artifact_content = content or """# Confirmed elicitation results

## Business objectives

1. Reduce application processing time to 2 days
2. Automate the distribution of applications between managers
3. Provide process transparency for the customer
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(artifact_content)
    return path


def make_confirmed_artifact(project_id: str, content: str = None) -> str:
    """A 4.3 artifact with the fuller default body (needs and NFRs, not objectives only).

    Writes through make_confirmed_artifact_reports: there is one layout, and a fixture
    seeded anywhere else is a file the consumer cannot find.
    """
    artifact_content = content or f"""# Confirmed elicitation results

## Бизнес-цели

1. Сократить время обработки заявок до 2 дней
2. Автоматизировать распределение заявок между менеджерами
3. Обеспечить прозрачность процесса для клиента

## Выявленные потребности

- Менеджеры хотят видеть все активные заявки в одном месте
- Руководитель хочет получать отчёты по эффективности менеджеров
- Клиент хочет знать статус своей заявки

## Нефункциональные требования

- Система должна работать 24/7
- Время отклика не более 3 секунд
"""
    return make_confirmed_artifact_reports(project_id, artifact_content)


# ---------------------------------------------------------------------------
# 7.1 — Тесты утилит
# ---------------------------------------------------------------------------

class TestSpecUtilities(unittest.TestCase):

    def test_repo_path_is_under_the_project_folder(self):
        path = mod71._repo_path("my_project")
        self.assertIn(os.path.join("my_project", "my_project_traceability_repo.json"), path)

    def test_a_path_is_never_built_for_an_id_that_needs_rewriting(self):
        # Both spellings used to be accepted and folded onto `my_project`, which is
        # what made two ids share one folder. The path helper is the place that has to
        # refuse, because it is the last step before a read or a write.
        #
        # The exception class is looked up through the module ON EACH CALL, not bound
        # at import: other tests reload skills.common, and a class captured beforehand
        # stops being the one that is raised.
        import skills.common as common_mod
        for spelled_wrong in ("My Project", "CRM 2024", "my__project"):
            with self.assertRaises(common_mod.InvalidProjectIdError):
                mod71._repo_path(spelled_wrong)
            with self.assertRaises(common_mod.InvalidProjectIdError):
                mod71._specs_dir(spelled_wrong)

    def test_specs_dir_format(self):
        # issue #1: спеки в data/<project>/specs/ (новая вложенная раскладка)
        d = mod71._specs_dir("crm_2024")
        self.assertIn(os.path.join("crm_2024", "specs"), d)
        self.assertIn("governance_plans", d)

    def test_load_repo_empty_when_missing(self):
        """Загрузка несуществующего репозитория возвращает пустую структуру."""
        repo = mod71._load_repo("nonexistent_project_xyz")
        self.assertEqual(repo["project"], "nonexistent_project_xyz")
        self.assertEqual(repo["requirements"], [])
        self.assertEqual(repo["links"], [])
        self.assertEqual(repo["history"], [])

    def test_load_repo_preserves_formality(self):
        repo = mod71._load_repo("nonexistent_project_xyz")
        self.assertIn("formality_level", repo)

    def test_cardinality_map_complete(self):
        """Все нужные типы кардинальности присутствуют в нотации."""
        # Проверяем через create_erd с разными cardinality
        expected = [
            "one-to-one", "one-to-many", "many-to-one",
            "many-to-many", "zero-or-one-to-many"
        ]
        # Убеждаемся что маппинг существует в модуле
        # (косвенная проверка через строку в исходнике)
        import inspect
        source = inspect.getsource(mod71.create_erd)
        for card in expected:
            self.assertIn(card, source)


class TestRegisterInRepo(BaseMCPTest):
    """Тесты функции _register_in_repo (ADR-022)."""

    P = "reg_test_proj"

    def test_register_creates_repo_if_missing(self):
        """Если репозиторий не существует — создаёт его."""
        mod71._register_in_repo(self.P, "FR-001", "functional", "Тест", "test.md")
        repo = load_spec_repo(self.P)
        self.assertEqual(len(repo["requirements"]), 1)
        self.assertEqual(repo["requirements"][0]["id"], "FR-001")

    def test_register_status_is_draft(self):
        mod71._register_in_repo(self.P, "FR-001", "functional", "Тест", "test.md")
        repo = load_spec_repo(self.P)
        self.assertEqual(repo["requirements"][0]["status"], "draft")

    def test_register_version_is_1_0(self):
        mod71._register_in_repo(self.P, "US-001", "user_story", "История", "test.md")
        repo = load_spec_repo(self.P)
        self.assertEqual(repo["requirements"][0]["version"], "1.0")

    def test_register_writes_history(self):
        mod71._register_in_repo(self.P, "UC-001", "use_case", "Сценарий", "test.md")
        repo = load_spec_repo(self.P)
        self.assertTrue(len(repo["history"]) > 0)
        self.assertEqual(repo["history"][0]["req_id"], "UC-001")

    def test_register_no_duplicate(self):
        """Повторная регистрация одного ID не создаёт дубль."""
        mod71._register_in_repo(self.P, "FR-001", "functional", "Тест", "test.md")
        mod71._register_in_repo(self.P, "FR-001", "functional", "Тест v2", "test2.md")
        repo = load_spec_repo(self.P)
        count = sum(1 for r in repo["requirements"] if r["id"] == "FR-001")
        self.assertEqual(count, 1)

    def test_register_duplicate_returns_info(self):
        mod71._register_in_repo(self.P, "FR-001", "functional", "Тест", "test.md")
        result = mod71._register_in_repo(self.P, "FR-001", "functional", "Тест v2", "test2.md")
        self.assertIn("уже зарегистрирован", result)

    def test_register_priority_stored(self):
        mod71._register_in_repo(self.P, "BR-001", "business_rule", "Правило", "test.md", "High")
        repo = load_spec_repo(self.P)
        self.assertEqual(repo["requirements"][0]["priority"], "High")

    def test_register_multiple_different_ids(self):
        for i in range(5):
            mod71._register_in_repo(self.P, f"FR-{i:03d}", "functional", f"Req {i}", "test.md")
        repo = load_spec_repo(self.P)
        self.assertEqual(len(repo["requirements"]), 5)


# ---------------------------------------------------------------------------
# 7.1.1 — analyze_elicitation_context
# ---------------------------------------------------------------------------

class TestAnalyzeElicitationContext(BaseMCPTest):

    P = "analyze_test"

    def test_returns_guide_when_no_file_no_text(self):
        """Без файла и без текста — возвращает инструкцию."""
        result = mod71.analyze_elicitation_context(self.P)
        self.assertIn("не найден", result)
        self.assertIn("context_text", result)

    def test_uses_file_when_found(self):
        """Если файл 4.3 найден — использует его."""
        make_confirmed_artifact(self.P)
        result = mod71.analyze_elicitation_context(self.P)
        self.assertIn("Файл найден", result)
        self.assertNotIn("не найден", result.split("##")[0])

    def test_uses_context_text_when_no_file(self):
        """Если файл не найден но передан context_text — использует текст."""
        result = mod71.analyze_elicitation_context(
            "nonexistent_project_42",
            context_text="Бизнес-цели: 1. Ускорить процесс. Потребности стейкхолдеров: ..."
        )
        self.assertIn("вручную", result)

    def test_shows_analysis_guide(self):
        """Результат содержит инструкцию по анализу для Claude Code."""
        make_confirmed_artifact(self.P)
        result = mod71.analyze_elicitation_context(self.P)
        self.assertIn("Инструкция по анализу", result)

    def test_shows_classification_table(self):
        """Результат содержит таблицу типов требований."""
        result = mod71.analyze_elicitation_context(
            "proj_text", context_text="Содержимое артефакта 4.3"
        )
        self.assertIn("user_story", result)
        self.assertIn("functional", result)

    def test_context_text_overrides_file_not_found(self):
        """context_text позволяет работать без файла."""
        result = mod71.analyze_elicitation_context(
            "completely_new_project_99",
            context_text="Требования: нужна система учёта заявок"
        )
        self.assertNotIn("Варианты действий", result)
        self.assertIn("Следующий шаг", result)


# ---------------------------------------------------------------------------
# 7.1.2 — create_user_story
# ---------------------------------------------------------------------------

class TestCreateUserStory(BaseMCPTest):

    P = "us_test"

    def _make(self, story_id="US-001", criteria=None):
        if criteria is None:
            criteria = ["Система сохраняет заявку с ID", "Менеджер получает уведомление"]
        return mod71.create_user_story(
            project_id=self.P,
            story_id=story_id,
            title="Создать заявку на кредит",
            role="Менеджер",
            action="создать новую заявку",
            benefit="заявка попала в очередь обработки",
            acceptance_criteria_json=json.dumps(criteria),
            priority="High",
            source_artifact="governance_plans/4_3_test_confirmed.md",
        )

    def test_success_contains_story_id(self):
        result = self._make()
        self.assertIn("US-001", result)

    def test_a_title_cannot_steer_the_spec_out_of_the_specs_folder(self):
        """The 7.1 producers build the spec filename themselves out of the id and the
        TITLE — free text an LLM writes from the analyst's dictation. Nothing
        sanitised it, so `title="../../../escaped"` wrote two levels above specs/ and
        answered with the full document and no warning, while the graph node pointed
        at a path that did not exist."""
        result = mod71.create_user_story(
            project_id=self.P, story_id="US-900", title="../../../escaped",
            role="Manager", action="do a thing", benefit="value accrues",
            acceptance_criteria_json=json.dumps(["First criterion", "Second criterion"]),
            priority="High", source_artifact="")
        self.assertNotIn("❌", result)

        specs = os.path.realpath(mod71._specs_dir(self.P))
        written = []
        for root, _dirs, files in os.walk("governance_plans"):
            written += [os.path.realpath(os.path.join(root, f)) for f in files
                        if f.endswith(".md")]
        self.assertTrue(written, "nothing was written at all")
        for path in written:
            self.assertEqual(os.path.commonpath([path, specs]), specs,
                             f"a spec escaped the specs folder: {path}")

        # ...and the graph points at the file that actually exists.
        repo = load_spec_repo(self.P)
        node = [r for r in repo["requirements"] if r["id"] == "US-900"][0]
        self.assertTrue(os.path.exists(node["source_artifact"]),
                        f"source_artifact points nowhere: {node['source_artifact']}")

    def test_success_contains_as_a(self):
        result = self._make()
        self.assertIn("As a", result)
        self.assertIn("I want", result)
        self.assertIn("So that", result)

    def test_success_contains_acceptance_criteria(self):
        result = self._make()
        self.assertIn("Acceptance Criteria", result)
        self.assertIn("Система сохраняет заявку с ID", result)

    def test_success_registers_in_repo(self):
        self._make()
        repo = load_spec_repo(self.P)
        ids = [r["id"] for r in repo["requirements"]]
        self.assertIn("US-001", ids)

    def test_registered_type_is_user_story(self):
        self._make()
        repo = load_spec_repo(self.P)
        req = next(r for r in repo["requirements"] if r["id"] == "US-001")
        self.assertEqual(req["type"], "user_story")

    def test_registered_status_is_draft(self):
        self._make()
        repo = load_spec_repo(self.P)
        req = next(r for r in repo["requirements"] if r["id"] == "US-001")
        self.assertEqual(req["status"], "draft")

    def test_creates_md_file(self):
        self._make()
        specs_dir = mod71._specs_dir(self.P)
        files = os.listdir(specs_dir)
        self.assertTrue(any("us_001" in f for f in files))

    def test_too_few_criteria_returns_error(self):
        """Менее 2 критериев — ошибка."""
        result = mod71.create_user_story(
            project_id=self.P, story_id="US-002", title="T",
            role="R", action="A", benefit="B",
            acceptance_criteria_json=json.dumps(["Только один критерий"]),
        )
        self.assertIn("❌", result)
        self.assertIn("минимум 2", result)

    def test_invalid_json_returns_error(self):
        result = mod71.create_user_story(
            project_id=self.P, story_id="US-003", title="T",
            role="R", action="A", benefit="B",
            acceptance_criteria_json="не JSON",
        )
        self.assertIn("❌", result)

    def test_notes_included_when_provided(self):
        result = mod71.create_user_story(
            project_id=self.P, story_id="US-004", title="T",
            role="R", action="A", benefit="B",
            acceptance_criteria_json=json.dumps(["AC1", "AC2"]),
            notes="Важный контекст для разработчика",
        )
        self.assertIn("Важный контекст для разработчика", result)

    def test_multiple_stories_no_duplication_in_repo(self):
        """Несколько историй — каждая регистрируется один раз."""
        for i in range(3):
            self._make(story_id=f"US-{i + 1:03d}")
        repo = load_spec_repo(self.P)
        ids = [r["id"] for r in repo["requirements"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_priority_stored_in_repo(self):
        self._make()
        repo = load_spec_repo(self.P)
        req = next(r for r in repo["requirements"] if r["id"] == "US-001")
        self.assertEqual(req["priority"], "High")


# ---------------------------------------------------------------------------
# 7.1.3 — create_functional_requirement
# ---------------------------------------------------------------------------

class TestCreateFunctionalRequirement(BaseMCPTest):

    P = "fr_test"

    def _make(self, req_id="FR-001", req_type="functional"):
        return mod71.create_functional_requirement(
            project_id=self.P,
            req_id=req_id,
            req_type=req_type,
            title="Автоматическое распределение заявок",
            description="Система ДОЛЖНА автоматически распределять заявки.",
            rationale="Снижает нагрузку на менеджеров.",
            priority="High",
            owner="Руководитель отдела",
            source_artifact="governance_plans/4_3_test.md",
        )

    def test_functional_success(self):
        result = self._make("FR-001", "functional")
        self.assertIn("FR-001", result)
        self.assertIn("Функциональное требование", result)

    def test_non_functional_success(self):
        result = self._make("NFR-001", "non_functional")
        self.assertIn("NFR-001", result)
        self.assertIn("Нефункциональное требование", result)

    def test_business_rule_success(self):
        result = self._make("BR-001", "business_rule")
        self.assertIn("BR-001", result)
        self.assertIn("Бизнес-правило", result)

    def test_invalid_type_returns_error(self):
        result = mod71.create_functional_requirement(
            project_id=self.P, req_id="XX-001", req_type="unknown_type",
            title="T", description="D", rationale="R",
        )
        self.assertIn("❌", result)
        self.assertIn("req_type", result)

    def test_registers_functional_type_in_repo(self):
        self._make("FR-001", "functional")
        repo = load_spec_repo(self.P)
        req = next(r for r in repo["requirements"] if r["id"] == "FR-001")
        self.assertEqual(req["type"], "functional")

    def test_registers_non_functional_type(self):
        self._make("NFR-001", "non_functional")
        repo = load_spec_repo(self.P)
        req = next(r for r in repo["requirements"] if r["id"] == "NFR-001")
        self.assertEqual(req["type"], "non_functional")

    def test_registers_business_rule_type(self):
        self._make("BR-001", "business_rule")
        repo = load_spec_repo(self.P)
        req = next(r for r in repo["requirements"] if r["id"] == "BR-001")
        self.assertEqual(req["type"], "business_rule")

    def test_creates_md_file(self):
        self._make()
        specs_dir = mod71._specs_dir(self.P)
        files = os.listdir(specs_dir)
        self.assertTrue(any("fr_001" in f for f in files))

    def test_related_ids_valid_json(self):
        result = mod71.create_functional_requirement(
            project_id=self.P, req_id="FR-002", req_type="functional",
            title="T", description="D", rationale="R",
            related_ids_json='["BR-001", "UC-001"]',
        )
        self.assertIn("BR-001", result)
        self.assertIn("UC-001", result)

    def test_related_ids_invalid_json_fallback(self):
        """Невалидный related_ids_json — не падает, просто игнорирует."""
        result = mod71.create_functional_requirement(
            project_id=self.P, req_id="FR-003", req_type="functional",
            title="T", description="D", rationale="R",
            related_ids_json="не_json",
        )
        self.assertIn("FR-003", result)
        # Не должен упасть с ошибкой регистрации
        repo = load_spec_repo(self.P)
        ids = [r["id"] for r in repo["requirements"]]
        self.assertIn("FR-003", ids)

    def test_constraints_included_when_provided(self):
        result = mod71.create_functional_requirement(
            project_id=self.P, req_id="FR-004", req_type="functional",
            title="T", description="D", rationale="R",
            constraints="Работает только в рабочее время (9:00–18:00)",
        )
        self.assertIn("Ограничения", result)
        self.assertIn("рабочее время", result)

    def test_formulation_hint_in_output(self):
        """Вывод содержит подсказку о формулировке для типа."""
        result = self._make("FR-005", "functional")
        self.assertIn("ДОЛЖНА", result)


# ---------------------------------------------------------------------------
# 7.1.4 — create_use_case
# ---------------------------------------------------------------------------

class TestCreateUseCase(BaseMCPTest):

    P = "uc_test"

    def _make(self, uc_id="UC-001"):
        return mod71.create_use_case(
            project_id=self.P,
            uc_id=uc_id,
            title="Рассмотреть заявку",
            primary_actor="Кредитный аналитик",
            precondition="Заявка в статусе 'На рассмотрении'",
            postcondition="Заявка одобрена или отклонена",
            trigger="Аналитик открывает заявку",
            main_scenario="1. Аналитик открывает заявку.\n2. Система отображает данные.",
            priority="High",
            source_artifact="governance_plans/4_3_test.md",
        )

    def test_success_contains_uc_id(self):
        result = self._make()
        self.assertIn("UC-001", result)

    def test_success_contains_actors(self):
        result = self._make()
        self.assertIn("Кредитный аналитик", result)

    def test_success_contains_happy_path(self):
        result = self._make()
        self.assertIn("Happy Path", result)

    def test_success_contains_precondition(self):
        result = self._make()
        self.assertIn("Предусловие", result)

    def test_registers_use_case_type(self):
        self._make()
        repo = load_spec_repo(self.P)
        req = next(r for r in repo["requirements"] if r["id"] == "UC-001")
        self.assertEqual(req["type"], "use_case")

    def test_creates_md_file(self):
        self._make()
        specs_dir = mod71._specs_dir(self.P)
        files = os.listdir(specs_dir)
        self.assertTrue(any("uc_001" in f for f in files))

    def test_alt_scenarios_included(self):
        result = mod71.create_use_case(
            project_id=self.P, uc_id="UC-002",
            title="Оформить кредит",
            primary_actor="Клиент",
            precondition="Клиент авторизован",
            postcondition="Заявка создана",
            trigger="Клиент нажал 'Подать заявку'",
            main_scenario="1. Клиент заполняет форму.\n2. Система сохраняет.",
            alt_scenarios="1а. Клиент ввёл некорректные данные: система выдаёт ошибку.",
        )
        self.assertIn("Альтернативные", result)
        self.assertIn("некорректные данные", result)

    def test_exc_scenarios_included(self):
        result = mod71.create_use_case(
            project_id=self.P, uc_id="UC-003",
            title="Получить справку",
            primary_actor="Клиент",
            precondition="Авторизован",
            postcondition="Справка выдана",
            trigger="Запрос клиента",
            main_scenario="1. Клиент запрашивает справку.",
            exc_scenarios="Xа. Сервис недоступен: уведомить клиента.",
        )
        self.assertIn("исключений", result)

    def test_secondary_actors_included(self):
        result = mod71.create_use_case(
            project_id=self.P, uc_id="UC-004",
            title="Проверить скоринг",
            primary_actor="Аналитик",
            secondary_actors="Система скоринга, Служба безопасности",
            precondition="Заявка открыта",
            postcondition="Скоринг получен",
            trigger="Запрос аналитика",
            main_scenario="1. Аналитик запрашивает скоринг.",
        )
        self.assertIn("Служба безопасности", result)


# ---------------------------------------------------------------------------
# 7.1.5 — generate_use_case_diagram
# ---------------------------------------------------------------------------

class TestGenerateUseCaseDiagram(BaseMCPTest):

    P = "ucd_test"

    def _seed_use_cases(self):
        """Создаём несколько UC в репозитории."""
        repo = make_spec_repo(self.P, [
            {"id": "UC-001", "type": "use_case", "title": "Подать заявку",
             "version": "1.0", "status": "draft", "priority": "High", "added": str(date.today())},
            {"id": "UC-002", "type": "use_case", "title": "Рассмотреть заявку",
             "version": "1.0", "status": "draft", "priority": "High", "added": str(date.today())},
            {"id": "FR-001", "type": "functional", "title": "FR не UC",
             "version": "1.0", "status": "draft", "priority": "Medium", "added": str(date.today())},
        ])
        save_spec_repo(repo)

    def test_no_use_cases_returns_warning(self):
        """Если нет UC — возвращает предупреждение."""
        repo = make_spec_repo(self.P, [
            {"id": "FR-001", "type": "functional", "title": "FR",
             "version": "1.0", "status": "draft", "added": str(date.today())}
        ])
        save_spec_repo(repo)
        result = mod71.generate_use_case_diagram(self.P, "Тест")
        self.assertIn("⚠️", result)
        self.assertIn("Use Cases", result)

    def test_generates_plantuml(self):
        self._seed_use_cases()
        result = mod71.generate_use_case_diagram(self.P, "CRM-система")
        self.assertIn("@startuml", result)
        self.assertIn("@enduml", result)

    def test_contains_system_boundary(self):
        self._seed_use_cases()
        result = mod71.generate_use_case_diagram(self.P, "CRM-система")
        self.assertIn("CRM-система", result)

    def test_all_ucs_on_diagram(self):
        self._seed_use_cases()
        result = mod71.generate_use_case_diagram(self.P, "CRM")
        self.assertIn("Подать заявку", result)
        self.assertIn("Рассмотреть заявку", result)

    def test_fr_not_on_diagram(self):
        """Функциональные требования не попадают на UC Diagram."""
        self._seed_use_cases()
        result = mod71.generate_use_case_diagram(self.P, "CRM")
        # FR-001 должен быть в таблице но не как UC
        # Диаграмма не должна содержать "FR не UC" как usecase
        puml_block = result.split("```plantuml")[1].split("```")[0] if "```plantuml" in result else result
        self.assertNotIn("FR не UC", puml_block)

    def test_creates_puml_file(self):
        self._seed_use_cases()
        mod71.generate_use_case_diagram(self.P, "CRM", diagram_name="test_diagram")
        specs_dir = mod71._specs_dir(self.P)
        files = os.listdir(specs_dir)
        self.assertTrue(any("test_diagram.puml" in f for f in files))

    def test_custom_diagram_name(self):
        self._seed_use_cases()
        result = mod71.generate_use_case_diagram(self.P, "CRM", diagram_name="my_uc_diagram")
        self.assertIn("my_uc_diagram", result)


# ---------------------------------------------------------------------------
# 7.1.6 — create_business_process
# ---------------------------------------------------------------------------

class TestCreateBusinessProcess(BaseMCPTest):

    P = "bp_test"

    def _make(self, bp_id="BP-001"):
        return mod71.create_business_process(
            project_id=self.P,
            bp_id=bp_id,
            title="Обработка заявки",
            process_owner="Руководитель отдела",
            trigger="Клиент подаёт заявку",
            outcome="Заявка одобрена или закрыта",
            participants="Менеджер, Аналитик, Система",
            steps="1. Менеджер: принять заявку.\n2. Аналитик: проверить документы.\n3. Система: уведомить клиента.",
            priority="High",
            source_artifact="governance_plans/4_3_test.md",
        )

    def test_success_contains_bp_id(self):
        result = self._make()
        self.assertIn("BP-001", result)

    def test_success_contains_trigger(self):
        result = self._make()
        self.assertIn("Клиент подаёт заявку", result)

    def test_success_contains_plantuml(self):
        """ADR-024: должен содержать PlantUML Activity Diagram."""
        result = self._make()
        self.assertIn("@startuml", result)
        self.assertIn("@enduml", result)

    def test_success_contains_activity_start_stop(self):
        result = self._make()
        self.assertIn("start", result)
        self.assertIn("stop", result)

    def test_creates_md_file(self):
        """ADR-024: создаёт .md файл."""
        self._make()
        specs_dir = mod71._specs_dir(self.P)
        files = os.listdir(specs_dir)
        self.assertTrue(any("bp_001" in f and f.endswith(".md") for f in files))

    def test_creates_puml_file(self):
        """ADR-024: создаёт .puml файл."""
        self._make()
        specs_dir = mod71._specs_dir(self.P)
        files = os.listdir(specs_dir)
        self.assertTrue(any("bp_001" in f and f.endswith(".puml") for f in files))

    def test_registers_in_repo(self):
        self._make()
        repo = load_spec_repo(self.P)
        ids = [r["id"] for r in repo["requirements"]]
        self.assertIn("BP-001", ids)

    def test_registered_type_is_business_process(self):
        self._make()
        repo = load_spec_repo(self.P)
        req = next(r for r in repo["requirements"] if r["id"] == "BP-001")
        self.assertEqual(req["type"], "business_process")

    def test_business_rules_included(self):
        result = mod71.create_business_process(
            project_id=self.P, bp_id="BP-002",
            title="Выдача кредита",
            process_owner="Директор",
            trigger="Решение принято",
            outcome="Кредит выдан",
            participants="Кассир",
            steps="1. Кассир: выдать деньги.",
            business_rules="Максимальная сумма — 1 000 000 руб.",
        )
        self.assertIn("Бизнес-правила", result)
        self.assertIn("1 000 000", result)

    def test_metrics_included(self):
        result = mod71.create_business_process(
            project_id=self.P, bp_id="BP-003",
            title="Проверка документов",
            process_owner="Аналитик",
            trigger="Заявка поступила",
            outcome="Документы проверены",
            participants="Аналитик",
            steps="1. Аналитик: проверяет.",
            metrics="Среднее время: 30 минут.",
        )
        self.assertIn("Метрики", result)


# ---------------------------------------------------------------------------
# 7.1.7 — create_data_dictionary
# ---------------------------------------------------------------------------

class TestCreateDataDictionary(BaseMCPTest):

    P = "dd_test"

    def _make_entities(self):
        return json.dumps([
            {
                "name": "Application",
                "description": "Заявка на кредит",
                "attributes": [
                    {"name": "id", "type": "Integer", "required": True,
                     "constraints": "PK, AUTO_INCREMENT", "description": "ID заявки"},
                    {"name": "status", "type": "Enum", "required": True,
                     "constraints": "draft|submitted|approved|rejected", "description": "Статус"},
                ],
                "business_rules": ["Статус меняется только по бизнес-правилам"]
            }
        ])

    def test_success_contains_dd_id(self):
        result = mod71.create_data_dictionary(
            self.P, "DD-001", "Сущности CRM", self._make_entities()
        )
        self.assertIn("DD-001", result)

    def test_success_contains_entity_name(self):
        result = mod71.create_data_dictionary(
            self.P, "DD-001", "Сущности CRM", self._make_entities()
        )
        self.assertIn("Application", result)

    def test_success_contains_attributes_table(self):
        result = mod71.create_data_dictionary(
            self.P, "DD-001", "Сущности CRM", self._make_entities()
        )
        self.assertIn("Тип данных", result)
        self.assertIn("Обязательный", result)

    def test_success_contains_attribute_values(self):
        result = mod71.create_data_dictionary(
            self.P, "DD-001", "Сущности CRM", self._make_entities()
        )
        self.assertIn("Integer", result)
        self.assertIn("AUTO_INCREMENT", result)

    def test_success_contains_business_rules(self):
        result = mod71.create_data_dictionary(
            self.P, "DD-001", "Сущности CRM", self._make_entities()
        )
        self.assertIn("Бизнес-правила", result)

    def test_registers_in_repo(self):
        mod71.create_data_dictionary(self.P, "DD-001", "Сущности CRM", self._make_entities())
        repo = load_spec_repo(self.P)
        ids = [r["id"] for r in repo["requirements"]]
        self.assertIn("DD-001", ids)

    def test_registered_type_is_data_dictionary(self):
        mod71.create_data_dictionary(self.P, "DD-001", "T", self._make_entities())
        repo = load_spec_repo(self.P)
        req = next(r for r in repo["requirements"] if r["id"] == "DD-001")
        self.assertEqual(req["type"], "data_dictionary")

    def test_creates_md_file(self):
        mod71.create_data_dictionary(self.P, "DD-001", "Сущности", self._make_entities())
        specs_dir = mod71._specs_dir(self.P)
        files = os.listdir(specs_dir)
        self.assertTrue(any("dd_001" in f for f in files))

    def test_invalid_json_returns_error(self):
        result = mod71.create_data_dictionary(self.P, "DD-002", "T", "не JSON")
        self.assertIn("❌", result)

    def test_empty_list_returns_error(self):
        result = mod71.create_data_dictionary(self.P, "DD-003", "T", "[]")
        self.assertIn("❌", result)

    def test_multiple_entities(self):
        entities = json.dumps([
            {"name": "Client", "description": "Клиент", "attributes": [
                {"name": "id", "type": "Integer", "required": True, "constraints": "PK", "description": "ID"}
            ], "business_rules": []},
            {"name": "Manager", "description": "Менеджер", "attributes": [
                {"name": "id", "type": "Integer", "required": True, "constraints": "PK", "description": "ID"}
            ], "business_rules": []},
        ])
        result = mod71.create_data_dictionary(self.P, "DD-004", "Все сущности", entities)
        self.assertIn("Client", result)
        self.assertIn("Manager", result)


# ---------------------------------------------------------------------------
# 7.1.8 — create_erd
# ---------------------------------------------------------------------------

class TestCreateERD(BaseMCPTest):

    P = "erd_test"

    def _make_entities(self):
        return json.dumps([
            {"name": "Application", "pk": "id", "attributes": ["client_id FK", "status Enum"]},
            {"name": "Client", "pk": "id", "attributes": ["name String", "inn String"]},
        ])

    def _make_relations(self):
        return json.dumps([
            {"from": "Application", "to": "Client", "cardinality": "many-to-one", "label": "belongs to"}
        ])

    def test_success_contains_erd_id(self):
        result = mod71.create_erd(self.P, "ERD-001", "Основные сущности",
                                   self._make_entities(), self._make_relations())
        self.assertIn("ERD-001", result)

    def test_success_contains_plantuml(self):
        """ADR-025: содержит PlantUML ER Diagram."""
        result = mod71.create_erd(self.P, "ERD-001", "T",
                                   self._make_entities(), self._make_relations())
        self.assertIn("@startuml", result)
        self.assertIn("@enduml", result)

    def test_plantuml_contains_entities(self):
        result = mod71.create_erd(self.P, "ERD-001", "T",
                                   self._make_entities(), self._make_relations())
        self.assertIn("Application", result)
        self.assertIn("Client", result)

    def test_plantuml_contains_relation_notation(self):
        result = mod71.create_erd(self.P, "ERD-001", "T",
                                   self._make_entities(), self._make_relations())
        # many-to-one → }o--||
        self.assertIn("}o--||", result)

    def test_plantuml_contains_relation_label(self):
        result = mod71.create_erd(self.P, "ERD-001", "T",
                                   self._make_entities(), self._make_relations())
        self.assertIn("belongs to", result)

    def test_registers_in_repo(self):
        mod71.create_erd(self.P, "ERD-001", "T",
                          self._make_entities(), self._make_relations())
        repo = load_spec_repo(self.P)
        ids = [r["id"] for r in repo["requirements"]]
        self.assertIn("ERD-001", ids)

    def test_registered_type_is_erd(self):
        mod71.create_erd(self.P, "ERD-001", "T",
                          self._make_entities(), self._make_relations())
        repo = load_spec_repo(self.P)
        req = next(r for r in repo["requirements"] if r["id"] == "ERD-001")
        self.assertEqual(req["type"], "erd")

    def test_creates_md_file(self):
        mod71.create_erd(self.P, "ERD-001", "Сущности", self._make_entities(), self._make_relations())
        specs_dir = mod71._specs_dir(self.P)
        files = os.listdir(specs_dir)
        self.assertTrue(any("erd_001" in f and f.endswith(".md") for f in files))

    def test_creates_puml_file(self):
        """ADR-025: создаёт .puml файл."""
        mod71.create_erd(self.P, "ERD-001", "Сущности", self._make_entities(), self._make_relations())
        specs_dir = mod71._specs_dir(self.P)
        files = os.listdir(specs_dir)
        self.assertTrue(any("erd_001" in f and f.endswith(".puml") for f in files))

    def test_invalid_entities_json_returns_error(self):
        result = mod71.create_erd(self.P, "ERD-002", "T", "не JSON", "[]")
        self.assertIn("❌", result)

    def test_empty_relations_no_error(self):
        """Пустой список связей — не ошибка."""
        result = mod71.create_erd(self.P, "ERD-003", "T", self._make_entities(), "[]")
        self.assertIn("ERD-003", result)
        self.assertNotIn("❌", result)

    def test_one_to_many_notation(self):
        relations = json.dumps([{"from": "A", "to": "B", "cardinality": "one-to-many", "label": "has"}])
        entities = json.dumps([
            {"name": "A", "pk": "id", "attributes": []},
            {"name": "B", "pk": "id", "attributes": []},
        ])
        result = mod71.create_erd(self.P, "ERD-004", "T", entities, relations)
        self.assertIn("||--o{", result)


# ---------------------------------------------------------------------------
# 7.1.9 — build_coverage_matrix
# ---------------------------------------------------------------------------

class TestBuildCoverageMatrix(BaseMCPTest):

    P = "cov_test"

    def test_no_requirements_returns_warning(self):
        """Пустой репозиторий — возвращает предупреждение."""
        save_spec_repo(make_spec_repo(self.P, []))
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("⚠️", result)

    def test_with_requirements_shows_matrix(self):
        """С требованиями — показывает матрицу."""
        repo = make_spec_repo(self.P, [
            {"id": "FR-001", "type": "functional", "title": "Тест",
             "version": "1.0", "status": "draft", "added": str(date.today()),
             "source_artifact": "governance_plans/4_3_cov_test_confirmed.md"},
        ])
        save_spec_repo(repo)
        make_confirmed_artifact(self.P)
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("Матрица покрытия", result)

    def test_deprecated_is_shown_and_marked_but_is_not_coverage(self):
        """Owner's decision, 2026-08-03: archived requirements are shown, marked and
        counted — they only stop counting as coverage.

        Hiding them moved the denominator silently: this matrix and the 5.1 documents
        of the same project reported different sizes for the same graph."""
        repo = make_spec_repo(self.P, [
            {"id": "BG-001", "type": "business_goal", "title": "Faster processing",
             "version": "1.0", "status": "confirmed", "added": str(date.today()),
             "source_artifact": ""},
            {"id": "FR-001", "type": "functional", "title": "Active",
             "version": "1.0", "status": "draft", "added": str(date.today()),
             "source_artifact": ""},
            {"id": "FR-DEP", "type": "functional", "title": "Устаревший",
             "version": "1.0", "status": "deprecated", "added": str(date.today()),
             "source_artifact": ""},
        ])
        repo["links"] = [
            {"from": "FR-DEP", "to": "BG-001", "relation": "satisfies",
             "rationale": "withdrawn", "added": str(date.today())},
        ]
        save_spec_repo(repo)
        result = mod71.build_coverage_matrix(self.P)

        self.assertIn("FR-DEP", result, "an archived requirement vanished from the matrix")
        dep_row = [ln for ln in result.split("\n") if "FR-DEP" in ln and ln.startswith("|")]
        self.assertTrue(dep_row)
        self.assertIn("в архиве", dep_row[0].lower(), "it is shown but not marked")
        self.assertIn("| — of them archived (5.2) | 1 |", result)

        # ...and the objective it used to serve is NOT covered by it.
        goal_row = [ln for ln in result.split("\n")
                    if "BG-001" in ln and "Faster processing" in ln]
        self.assertTrue(goal_row)
        self.assertIn("🔴", goal_row[0],
                      "a withdrawn requirement was counted as serving the objective")

    def test_shows_summary_table(self):
        repo = make_spec_repo(self.P, [
            {"id": "FR-001", "type": "functional", "title": "Тест",
             "version": "1.0", "status": "draft", "added": str(date.today()), "source_artifact": ""},
        ])
        save_spec_repo(repo)
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("Сводка", result)
        self.assertIn("Требований в реестре", result)

    def _matrix_with_goals(self, per_goal_counts):
        """One objective per entry, carrying that many `satisfies` links."""
        reqs, links, goals, n = [], [], [], 0
        for gi, count in enumerate(per_goal_counts, start=1):
            gid = f"BG-{gi:03d}"
            goals.append({"id": gid, "type": "business_goal", "title": f"Objective {gi}",
                          "version": "1.0", "status": "confirmed",
                          "added": str(date.today()), "source_artifact": ""})
            for _ in range(count):
                n += 1
                rid = f"FR-{n:03d}"
                reqs.append({"id": rid, "type": "functional", "title": f"Req {n}",
                             "version": "1.0", "status": "draft",
                             "added": str(date.today()), "source_artifact": ""})
                links.append({"from": rid, "to": gid, "relation": "satisfies",
                              "rationale": "serves", "added": str(date.today())})
        repo = make_spec_repo(self.P, goals + reqs)
        repo["links"] = links
        save_spec_repo(repo)
        return mod71.build_coverage_matrix(self.P)

    def _row_for(self, result, goal_id):
        rows = [ln for ln in result.split("\n")
                if ln.startswith("|") and f"`{goal_id}`" in ln]
        self.assertTrue(rows, f"no row for {goal_id}:\n{result}")
        return rows[0]

    def test_over_engineering_flags_the_objective_that_stands_out(self):
        """The old test built 12 requirements with NO objectives and asserted `🟡` was
        somewhere in the output — which the LEGEND line satisfies on its own, so it
        passed whatever the flag did. This one reads the objective's own row.

        The threshold is relative: an absolute "10+" left every objective permanently
        yellow on a real project (105 requirements over 4 objectives), and a signal
        that never switches off teaches the analyst to ignore the colour."""
        result = self._matrix_with_goals([40, 2, 2, 2])
        self.assertIn("🟡", self._row_for(result, "BG-001"),
                      "the objective carrying 40 of 46 requirements is not flagged")
        for gid in ("BG-002", "BG-003", "BG-004"):
            self.assertNotIn("🟡", self._row_for(result, gid))

    def test_an_evenly_loaded_project_flags_nothing(self):
        """105 requirements over 4 objectives is a NORMAL large project, not four
        anomalies."""
        result = self._matrix_with_goals([26, 26, 26, 27])
        for gid in ("BG-001", "BG-002", "BG-003", "BG-004"):
            self.assertNotIn("🟡", self._row_for(result, gid))

    def test_the_id_list_in_a_cell_has_a_ceiling(self):
        """B-1. A cell held 60 identifiers — some 700 characters in one Markdown table
        cell — while 7.4 had solved this next door. The COUNT is never capped."""
        result = self._matrix_with_goals([60])
        row = self._row_for(result, "BG-001")
        self.assertIn("| 60 |", row, "the count must stay complete")
        self.assertIn("+ещё", row, "the id list has no ceiling")
        self.assertLess(row.count("`FR-"), 15, f"the whole list is still printed: {row}")

    def test_the_average_matches_the_column_under_it(self):
        """B-2. "Avg requirements per objective 26.2" sat above a column summing to
        135: the average was registry ÷ objectives, while the table counts
        objective↔requirement PAIRS, and a requirement may serve several."""
        result = self._matrix_with_goals([3, 3, 2])
        rows = result.split("\n")
        avg_line = [ln for ln in rows if "Avg requirements per objective" in ln][0]
        counts = [int(ln.split("|")[3].strip()) for ln in rows
                  if ln.startswith("| 🟢") or ln.startswith("| 🟡") or ln.startswith("| 🔴")]
        expected = sum(counts) / len(counts) if counts else 0
        self.assertIn(f"{expected:.1f}", avg_line,
                      f"average {avg_line!r} does not describe the column {counts}")

    def test_reads_business_goals_from_artifact(self):
        """Если артефакт 4.3 есть — использует его бизнес-цели."""
        make_confirmed_artifact(self.P, content="""## Бизнес-цели

1. Сократить время обработки заявок
2. Автоматизировать распределение
""")
        repo = make_spec_repo(self.P, [
            {"id": "FR-001", "type": "functional", "title": "Тест",
             "version": "1.0", "status": "draft", "added": str(date.today()), "source_artifact": ""},
        ])
        save_spec_repo(repo)
        result = mod71.build_coverage_matrix(self.P)
        # Должна быть упомянута хотя бы одна бизнес-цель из файла
        self.assertTrue(
            "Сократить" in result or "Автоматизировать" in result,
            "Бизнес-цели из артефакта 4.3 не найдены в матрице"
        )


# ---------------------------------------------------------------------------
# Интеграционные тесты — полный пайплайн
# ---------------------------------------------------------------------------

class TestIntegrationPipeline(BaseMCPTest):
    """
    Проверяем что созданные артефакты корректно взаимодействуют.
    """

    P = "integration_test"

    def test_full_pipeline_spec_to_repo(self):
        """
        Полный пайплайн: создаём US + FR + UC → все регистрируются в репозитории 5.1.
        """
        mod71.create_user_story(
            project_id=self.P, story_id="US-001", title="История",
            role="Пользователь", action="сделать действие", benefit="получить результат",
            acceptance_criteria_json=json.dumps(["AC1", "AC2"]),
        )
        mod71.create_functional_requirement(
            project_id=self.P, req_id="FR-001", req_type="functional",
            title="Требование", description="Система ДОЛЖНА...", rationale="Потому что"
        )
        mod71.create_use_case(
            project_id=self.P, uc_id="UC-001", title="Сценарий",
            primary_actor="Актор", precondition="Условие", postcondition="Результат",
            trigger="Триггер", main_scenario="1. Актор делает. 2. Система отвечает.",
        )

        repo = load_spec_repo(self.P)
        ids = {r["id"] for r in repo["requirements"]}
        self.assertIn("US-001", ids)
        self.assertIn("FR-001", ids)
        self.assertIn("UC-001", ids)

    def test_specs_dir_created_with_files(self):
        """
        После создания артефактов папка specs существует и содержит файлы.
        """
        mod71.create_user_story(
            project_id=self.P, story_id="US-001", title="История",
            role="Р", action="А", benefit="Б",
            acceptance_criteria_json=json.dumps(["AC1", "AC2"]),
        )
        mod71.create_functional_requirement(
            project_id=self.P, req_id="FR-001", req_type="functional",
            title="Т", description="Д", rationale="О",
        )
        specs_dir = mod71._specs_dir(self.P)
        self.assertTrue(os.path.isdir(specs_dir))
        files = os.listdir(specs_dir)
        self.assertGreater(len(files), 0)

    def test_coverage_matrix_after_creation(self):
        """
        После создания нескольких требований coverage matrix строится без ошибок.
        """
        for i in range(3):
            mod71.create_functional_requirement(
                project_id=self.P, req_id=f"FR-{i + 1:03d}", req_type="functional",
                title=f"Требование {i + 1}", description="D", rationale="R",
            )
        result = mod71.build_coverage_matrix(self.P)
        self.assertNotIn("⚠️", result.split("##")[0])
        self.assertIn("Матрица", result)

    def test_uc_diagram_after_use_cases_created(self):
        """
        generate_use_case_diagram видит UC созданные через create_use_case.
        """
        for i in range(2):
            mod71.create_use_case(
                project_id=self.P, uc_id=f"UC-{i + 1:03d}",
                title=f"Сценарий {i + 1}",
                primary_actor="Актор",
                precondition="Условие", postcondition="Результат",
                trigger="Триггер", main_scenario="1. Шаг.",
            )
        result = mod71.generate_use_case_diagram(self.P, "Тестовая система")
        self.assertIn("@startuml", result)
        self.assertIn("Сценарий 1", result)
        self.assertIn("Сценарий 2", result)

    def test_all_types_registered_correctly(self):
        """
        Все типы артефактов регистрируются с правильным type в репозитории.
        """
        mod71.create_user_story(
            project_id=self.P, story_id="US-001", title="История",
            role="Р", action="А", benefit="Б",
            acceptance_criteria_json=json.dumps(["AC1", "AC2"]),
        )
        mod71.create_functional_requirement(
            project_id=self.P, req_id="FR-001", req_type="functional",
            title="FR", description="D", rationale="R",
        )
        mod71.create_use_case(
            project_id=self.P, uc_id="UC-001", title="UC",
            primary_actor="А", precondition="П", postcondition="Р",
            trigger="Т", main_scenario="1. Шаг.",
        )
        mod71.create_business_process(
            project_id=self.P, bp_id="BP-001", title="Процесс",
            process_owner="Владелец", trigger="Триггер", outcome="Результат",
            participants="Участник", steps="1. Участник: шаг.",
        )
        mod71.create_data_dictionary(
            project_id=self.P, dd_id="DD-001", title="Сущности",
            entities_json=json.dumps([{
                "name": "E", "description": "D",
                "attributes": [{"name": "id", "type": "Integer", "required": True,
                                "constraints": "PK", "description": "ID"}],
                "business_rules": []
            }])
        )
        mod71.create_erd(
            project_id=self.P, erd_id="ERD-001", title="ERD",
            entities_json=json.dumps([{"name": "E", "pk": "id", "attributes": []}]),
            relations_json="[]",
        )

        repo = load_spec_repo(self.P)
        type_map = {r["id"]: r["type"] for r in repo["requirements"]}

        self.assertEqual(type_map["US-001"], "user_story")
        self.assertEqual(type_map["FR-001"], "functional")
        self.assertEqual(type_map["UC-001"], "use_case")
        self.assertEqual(type_map["BP-001"], "business_process")
        self.assertEqual(type_map["DD-001"], "data_dictionary")
        self.assertEqual(type_map["ERD-001"], "erd")


# ---------------------------------------------------------------------------
# 7.1 audit regressions (2026-07-19): producer(4.3)/consumer(7.1) contract + hybrid matrix
# ---------------------------------------------------------------------------

class TestConfirmedArtifactRealLayout(BaseMCPTest):
    """Bug 7.1-A: the 4.3 producer writes to reports/<pid>/4_3_confirmed_result_<ts>.md,
    but the consumer only searched flat data/ with pid-in-filename masks -> never found it."""

    P = "layout_test"

    def test_find_confirmed_artifact_in_reports_layout(self):
        path = make_confirmed_artifact_reports(self.P)
        found = mod71._find_confirmed_artifact(self.P)
        self.assertIsNotNone(found, "consumer must find the artifact in the real reports/<pid>/ layout")
        self.assertEqual(os.path.abspath(found), os.path.abspath(path))

    def test_another_projects_artifact_is_not_offered_as_this_ones(self):
        # The folder is the ONLY thing that says whose artifact this is. The search
        # used to fall back to patterns that could not filter by project at all, so
        # this project could be handed another one's interviews and derive
        # requirements from them — the fallback warned, but the warning was the only
        # thing standing between the two projects.
        make_confirmed_artifact_reports("someone_else")
        self.assertIsNone(mod71._find_confirmed_artifact(self.P))

    def test_analyze_finds_real_producer_artifact(self):
        make_confirmed_artifact_reports(self.P)
        result = mod71.analyze_elicitation_context(self.P)
        self.assertIn("File found", result)
        self.assertNotIn("not found", result.split("##")[0])


class TestCoverageMatrixHybrid(BaseMCPTest):
    """Bug 7.1-B: the goal<->requirement mapping compared a file PATH (source_artifact)
    against goal TEXT, so every requirement fell into the first goal and all other goals
    were falsely flagged 🔴 uncovered. Hybrid (B1+B3): no fake per-goal flags; goals as a
    checklist; explicit limitation note pointing to check_coverage (5.1)."""

    P = "hybrid_test"

    def _multi_goal_artifact(self):
        make_confirmed_artifact(self.P, content="""## Business objectives

1. Alpha goal reduce processing time
2. Beta goal automate the routing
3. Gamma goal transparency for clients
""")

    def test_no_false_per_goal_uncovered_when_requirements_exist(self):
        self._multi_goal_artifact()
        save_spec_repo(make_spec_repo(self.P, [
            {"id": "FR-001", "type": "functional", "title": "Auto route",
             "version": "1.0", "status": "draft", "added": str(date.today()),
             "source_artifact": "governance_plans/reports/hybrid_test/4_3_confirmed_result_x.md"},
            {"id": "FR-002", "type": "functional", "title": "Transparency",
             "version": "1.0", "status": "draft", "added": str(date.today()),
             "source_artifact": "governance_plans/reports/hybrid_test/4_3_confirmed_result_x.md"},
        ]))
        result = mod71.build_coverage_matrix(self.P)
        self.assertNotIn("Uncovered business objectives", result)
        # Beta/Gamma must NOT be flagged as red-uncovered lines
        self.assertNotIn("🔴", result)

    def test_goals_shown_as_checklist(self):
        self._multi_goal_artifact()
        save_spec_repo(make_spec_repo(self.P, [
            {"id": "FR-001", "type": "functional", "title": "T",
             "version": "1.0", "status": "draft", "added": str(date.today()), "source_artifact": ""},
        ]))
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("Alpha goal reduce processing time", result)
        self.assertIn("Beta goal automate the routing", result)
        self.assertIn("Gamma goal transparency for clients", result)

    def test_matrix_notes_traceability_limitation_and_points_to_check_coverage(self):
        save_spec_repo(make_spec_repo(self.P, [
            {"id": "FR-001", "type": "functional", "title": "T",
             "version": "1.0", "status": "draft", "added": str(date.today()), "source_artifact": ""},
        ]))
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("check_coverage", result)

    # --- C1: objectives come from the REAL source (6.2), not the 4.3 artifact ---

    def test_goals_read_from_6_2_graph_nodes(self):
        """6.2 registers business_goal nodes in the 5.1 repo; the matrix must use them
        as the objectives, not fall back to synthetic source grouping.

        A1 note: the ASSERTION changed, the intent did not. Graph nodes carry ids, so the
        objectives are now rendered as a per-objective coverage table instead of a plain
        checklist — the checklist survives only for id-less sources.
        """
        save_spec_repo(make_spec_repo(self.P, [
            {"id": "BG-001", "type": "business_goal", "title": "Cut processing time to 2 days",
             "version": "1.0", "status": "confirmed", "added": str(date.today()), "source_artifact": ""},
            {"id": "FR-001", "type": "functional", "title": "Auto route",
             "version": "1.0", "status": "draft", "added": str(date.today()), "source_artifact": ""},
        ]))
        result = mod71.build_coverage_matrix(self.P)
        # appears as an objective row, not as a requirement row
        self.assertIn("`BG-001` Cut processing time to 2 days", result)
        self.assertIn("6.2 goals registered in the 5.1 graph", result)

    def test_business_goal_node_not_counted_as_requirement(self):
        """A business_goal node is an objective, not a spec requirement — it must not inflate
        the requirements count nor appear in the requirements list."""
        save_spec_repo(make_spec_repo(self.P, [
            {"id": "BG-001", "type": "business_goal", "title": "Goal one",
             "version": "1.0", "status": "confirmed", "added": str(date.today()), "source_artifact": ""},
            {"id": "FR-001", "type": "functional", "title": "Req one",
             "version": "1.0", "status": "draft", "added": str(date.today()), "source_artifact": ""},
        ]))
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("| Requirements in the registry | 1 |", result)

    def test_goals_read_from_future_state_goals_file(self):
        """If goals are not in the graph (register_in_traceability=False) but the 6.2 file
        exists, read objectives from future_state_goals.json."""
        from skills.common import data_path
        import os as _os
        safe = self.P.lower().replace(" ", "_")
        path = data_path(self.P, f"{safe}_future_state_goals.json")
        _os.makedirs(_os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"goals": [
                {"id": "BG-001", "goal_title": "Improve NPS to 60", "description": "d",
                 "objectives": [], "linked_business_needs": []},
            ]}, f)
        save_spec_repo(make_spec_repo(self.P, [
            {"id": "FR-001", "type": "functional", "title": "Feature",
             "version": "1.0", "status": "draft", "added": str(date.today()), "source_artifact": ""},
        ]))
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("Improve NPS to 60", result)


class TestGoalEdgesAtRegistration(BaseMCPTest):
    """A1: the BA declares which objective a requirement serves, and the shared
    registration point writes the `satisfies` edge (from=requirement, to=objective,
    ADR-082). Nothing is ever inferred from text — that was finding 7.1-B.
    """

    P = "goal_edges"

    def setUp(self):
        super().setUp()
        save_spec_repo(make_spec_repo(self.P, [
            {"id": "BG-001", "type": "business_goal", "title": "Cut handling time",
             "version": "1.0", "status": "confirmed", "added": str(date.today()),
             "source_artifact": ""},
            {"id": "BN-001", "type": "business_need", "title": "Routing is manual",
             "version": "1.0", "status": "confirmed", "added": str(date.today()),
             "source_artifact": ""},
        ]))

    def _links(self):
        return load_spec_repo(self.P)["links"]

    def test_edge_written_for_valid_objective(self):
        mod71._register_in_repo(self.P, "FR-001", "functional", "Auto-assign",
                                "spec.md", "High", business_goal_ids=["BG-001"])
        self.assertEqual(
            [(l["from"], l["to"], l["relation"]) for l in self._links()],
            [("FR-001", "BG-001", "satisfies")],
        )

    def test_business_need_is_a_valid_target(self):
        """The FULL root set is accepted — linking a requirement straight to a need is
        legitimate BABOK. Checking a partial set is the class behind 7.3-A / 7.4-B."""
        mod71._register_in_repo(self.P, "FR-002", "functional", "Queue view",
                                "spec.md", "Medium", business_goal_ids=["BN-001"])
        self.assertEqual(len(self._links()), 1)

    def test_unknown_id_warns_and_writes_no_edge(self):
        note = mod71._register_in_repo(self.P, "FR-003", "functional", "X",
                                       "spec.md", "Medium",
                                       business_goal_ids=["BG-999"])
        self.assertEqual(self._links(), [])
        self.assertIn("BG-999", note)

    def test_unknown_id_creates_no_phantom_node(self):
        """A phantom objective would poison check_coverage, the 7.3 BFS, 7.4 and 5.4."""
        mod71._register_in_repo(self.P, "FR-004", "functional", "X",
                                "spec.md", "Medium", business_goal_ids=["BG-999"])
        ids = {r["id"] for r in load_spec_repo(self.P)["requirements"]}
        self.assertNotIn("BG-999", ids)

    def test_unknown_id_does_not_abort_registration(self):
        """Don't block — warn. The requirement is still created."""
        mod71._register_in_repo(self.P, "FR-005", "functional", "X",
                                "spec.md", "Medium", business_goal_ids=["BG-999"])
        ids = {r["id"] for r in load_spec_repo(self.P)["requirements"]}
        self.assertIn("FR-005", ids)

    def test_non_root_target_is_refused_with_a_pointer(self):
        mod71._register_in_repo(self.P, "FR-006", "functional", "X", "spec.md")
        note = mod71._register_in_repo(self.P, "FR-007", "functional", "Y",
                                       "spec.md", "Medium",
                                       business_goal_ids=["FR-006"])
        self.assertEqual(self._links(), [])
        self.assertIn("add_trace_link", note)

    def test_edge_is_idempotent_across_reruns(self):
        """Node dedup without edge dedup is the bug that recurred in 6.3 and 6.4."""
        for _ in range(3):
            mod71._register_in_repo(self.P, "FR-008", "functional", "Auto-assign",
                                    "spec.md", "High", business_goal_ids=["BG-001"])
        self.assertEqual(len(self._links()), 1)

    def test_existing_node_still_receives_a_new_edge(self):
        """THE TRAP: registration returns early for a known id. Node and edge handling
        must be independent, or a re-run meant to add the objective link does nothing."""
        mod71._register_in_repo(self.P, "FR-009", "functional", "Auto-assign",
                                "spec.md", "High")
        self.assertEqual(self._links(), [])
        mod71._register_in_repo(self.P, "FR-009", "functional", "Auto-assign",
                                "spec.md", "High", business_goal_ids=["BG-001"])
        self.assertEqual(len(self._links()), 1)

    def test_several_objectives_at_once(self):
        mod71._register_in_repo(self.P, "FR-010", "functional", "X", "spec.md",
                                "High", business_goal_ids=["BG-001", "BN-001"])
        self.assertEqual(len(self._links()), 2)

    def test_no_objectives_writes_no_edges(self):
        mod71._register_in_repo(self.P, "FR-011", "functional", "X", "spec.md")
        self.assertEqual(self._links(), [])

    def test_repo_without_a_links_key_does_not_crash(self):
        """Found in review: writing edges made `links` a hard dependency of registration
        for the first time, and _load_repo returns a stored file as-is. A legacy or partial
        repo without that key raised KeyError — a protocol-level error instead of a
        readable answer (the CH3-A / CH4-A class)."""
        path = data_path(self.P, f"{self.P}_traceability_repo.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"project": self.P, "requirements": []}, f)

        note = mod71._register_in_repo(self.P, "FR-100", "functional", "X", "spec.md")
        self.assertIn("FR-100", note)

    def test_node_registration_is_unchanged(self):
        """The pre-existing contract still holds: the node is registered as draft."""
        note = mod71._register_in_repo(self.P, "FR-012", "functional", "Auto-assign",
                                       "spec.md", "High", business_goal_ids=["BG-001"])
        node = next(r for r in load_spec_repo(self.P)["requirements"]
                    if r["id"] == "FR-012")
        self.assertEqual(node["status"], "draft")
        self.assertEqual(node["priority"], "High")
        self.assertIn("FR-012", note)


class TestCreateToolsAcceptGoalIds(BaseMCPTest):
    """The parameter is uniform across all six creating tools: whether an artefact
    serves an objective is the analyst's judgment, not the tool's."""

    P = "create_goal_ids"

    def setUp(self):
        super().setUp()
        save_spec_repo(make_spec_repo(self.P, [
            {"id": "BG-001", "type": "business_goal", "title": "Cut handling time",
             "version": "1.0", "status": "confirmed", "added": str(date.today()),
             "source_artifact": ""},
        ]))

    def _edges(self):
        return {(l["from"], l["to"], l["relation"])
                for l in load_spec_repo(self.P)["links"]}

    def test_user_story_links_to_objective(self):
        mod71.create_user_story(
            project_id=self.P, story_id="US-001", title="Fast assignment",
            role="Manager", action="assign a request in one click",
            benefit="handling time drops",
            acceptance_criteria_json='["Assigned in one click", "Audit entry written"]',
            business_goal_ids_json='["BG-001"]')
        self.assertIn(("US-001", "BG-001", "satisfies"), self._edges())

    def test_functional_requirement_links_to_objective(self):
        mod71.create_functional_requirement(
            project_id=self.P, req_id="FR-001", req_type="functional",
            title="Auto-assign", description="The system SHALL assign automatically",
            rationale="Manual routing is slow",
            business_goal_ids_json='["BG-001"]')
        self.assertIn(("FR-001", "BG-001", "satisfies"), self._edges())

    def test_use_case_links_to_objective(self):
        mod71.create_use_case(
            project_id=self.P, uc_id="UC-001", title="Assign a request",
            primary_actor="Manager", precondition="The request is in the queue",
            postcondition="The request has an assignee", trigger="A request arrives",
            main_scenario="1. Manager opens the queue\n2. Manager assigns the request",
            business_goal_ids_json='["BG-001"]')
        self.assertIn(("UC-001", "BG-001", "satisfies"), self._edges())

    def test_data_dictionary_links_to_objective(self):
        """The two tools that pass no priority must still reach the new argument."""
        mod71.create_data_dictionary(
            project_id=self.P, dd_id="DD-001", title="Request entity",
            entities_json='[{"name": "Request", "description": "An incoming request", '
                          '"attributes": [{"name": "id", "type": "UUID"}]}]',
            business_goal_ids_json='["BG-001"]')
        self.assertIn(("DD-001", "BG-001", "satisfies"), self._edges())

    def test_bad_shape_returns_error_not_exception(self):
        """LLM-written JSON of the wrong shape must produce a readable error
        (class CH3-A / CH4-A), never a protocol-level exception."""
        result = mod71.create_functional_requirement(
            project_id=self.P, req_id="FR-002", req_type="functional",
            title="X", description="The system SHALL x", rationale="y",
            business_goal_ids_json='[{"id": "BG-001"}]')
        self.assertIn("❌", result)
        self.assertEqual(self._edges(), set())

    def test_bad_shape_writes_no_spec_file(self):
        """The parse happens before the artefact is written, so a rejected call
        leaves no orphan .md on disk."""
        mod71.create_functional_requirement(
            project_id=self.P, req_id="FR-003", req_type="functional",
            title="X", description="The system SHALL x", rationale="y",
            business_goal_ids_json='not json at all')
        specs = specs_dir(self.P)
        found = os.path.exists(specs) and [f for f in os.listdir(specs) if "fr_003" in f]
        self.assertFalse(found)

    def test_default_is_no_links(self):
        mod71.create_functional_requirement(
            project_id=self.P, req_id="FR-004", req_type="functional",
            title="X", description="The system SHALL x", rationale="y")
        self.assertEqual(self._edges(), set())


class TestCoverageMatrixPrecise(BaseMCPTest):
    """A1: with real edges in the graph the matrix makes REAL per-objective claims.
    Without graph ids in the objective source it degrades to the C1 checklist rather
    than guessing — inferring the mapping from text was finding 7.1-B."""

    P = "matrix_precise"

    def _nodes(self):
        return [
            {"id": "BG-001", "type": "business_goal", "title": "Cut handling time",
             "version": "1.0", "status": "confirmed", "added": str(date.today()),
             "source_artifact": ""},
            {"id": "BG-002", "type": "business_goal", "title": "Improve transparency",
             "version": "1.0", "status": "confirmed", "added": str(date.today()),
             "source_artifact": ""},
            {"id": "BN-001", "type": "business_need", "title": "Routing is manual",
             "version": "1.0", "status": "confirmed", "added": str(date.today()),
             "source_artifact": ""},
            {"id": "FR-001", "type": "functional", "title": "Auto-assign",
             "version": "1.0", "status": "draft", "added": str(date.today()),
             "source_artifact": ""},
            {"id": "FR-002", "type": "functional", "title": "Status page",
             "version": "1.0", "status": "draft", "added": str(date.today()),
             "source_artifact": ""},
            {"id": "DD-001", "type": "data_dictionary", "title": "Request entity",
             "version": "1.0", "status": "draft", "added": str(date.today()),
             "source_artifact": ""},
        ]

    def _save(self, links, nodes=None):
        repo = make_spec_repo(self.P, nodes if nodes is not None else self._nodes())
        repo["links"] = links
        save_spec_repo(repo)

    def _edge(self, frm, to, rel="satisfies"):
        return {"from": frm, "to": to, "relation": rel, "created": str(date.today())}

    def test_covered_objective_lists_its_requirement(self):
        self._save([self._edge("FR-001", "BG-001")])
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("FR-001", result)
        self.assertIn("Cut handling time", result)

    def test_uncovered_objective_is_flagged_red(self):
        """A REAL claim now — BG-002 genuinely has no satisfying requirement."""
        self._save([self._edge("FR-001", "BG-001")])
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("🔴", result)
        self.assertIn("Improve transparency", result)

    def _coverage_table(self, result):
        """Rows of the per-objective table only. The flag legend below it mentions every
        symbol by design, so scanning the whole document would never detect a false flag."""
        if "## Coverage by business objective" not in result:
            return ""
        return result.split("## Coverage by business objective", 1)[1].split("\n\n>", 1)[0]

    def test_covered_objective_is_not_flagged_red(self):
        """Both objectives covered -> no red row."""
        self._save([self._edge("FR-001", "BG-001"), self._edge("FR-002", "BG-002")])
        result = mod71.build_coverage_matrix(self.P)
        self.assertNotIn("🔴", self._coverage_table(result))
        self.assertIn("🟢", self._coverage_table(result))

    def test_derives_edge_to_objective_is_counted_on_read(self):
        """A BA may have linked manually with derives via add_trace_link; ignoring it
        would silently under-report coverage. Written edges are always satisfies."""
        self._save([self._edge("FR-001", "BG-001", "derives")])
        result = mod71.build_coverage_matrix(self.P)
        red_section = result.split("Improve transparency", 1)[0]
        self.assertIn("FR-001", red_section)

    def test_requirement_without_any_objective_is_listed_unattached(self):
        self._save([self._edge("FR-001", "BG-001")])
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("not linked to any objective", result.lower())
        self.assertIn("FR-002", result)

    def test_need_only_link_is_not_called_unattached(self):
        """Calling it unattached would be false; it means 6.2 has not refined that
        need into objectives yet."""
        self._save([self._edge("FR-002", "BN-001")])
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("business need", result.lower())

    def test_no_text_similarity_matching(self):
        """Titles deliberately identical, but with no edge the objective stays
        uncovered. This is finding 7.1-B, pinned so it cannot come back."""
        nodes = self._nodes()
        for n in nodes:
            if n["id"] == "FR-002":
                n["title"] = "Improve transparency"
        self._save([], nodes=nodes)
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("🔴", result)

    def test_objective_nodes_are_not_counted_as_requirements(self):
        """Roots must not inflate the requirement count (finding 7.1-C)."""
        self._save([self._edge("FR-001", "BG-001")])
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("| Requirements in the registry | 3 |", result)

    def test_degraded_mode_when_objectives_have_no_ids(self):
        """No business_goal nodes -> objectives come from an id-less source ->
        checklist, no per-objective flags, and the tool says which mode it is in."""
        save_spec_repo(make_spec_repo(self.P, [
            {"id": "FR-001", "type": "functional", "title": "Auto-assign",
             "version": "1.0", "status": "draft", "added": str(date.today()),
             "source_artifact": "governance_plans/reports/matrix_precise/4_3_x.md"},
        ]))
        result = mod71.build_coverage_matrix(self.P)
        self.assertNotIn("🔴", result)
        self.assertIn("check_coverage", result)

    def test_degraded_mode_does_not_call_everything_unattached(self):
        """Nothing is linked because nothing CAN be linked — listing every requirement
        as unattached would be exactly the kind of false claim A1 removes."""
        save_spec_repo(make_spec_repo(self.P, [
            {"id": "FR-001", "type": "functional", "title": "Auto-assign",
             "version": "1.0", "status": "draft", "added": str(date.today()),
             "source_artifact": "governance_plans/reports/matrix_precise/4_3_x.md"},
        ]))
        result = mod71.build_coverage_matrix(self.P)
        self.assertNotIn("not linked to any objective", result.lower())

    def test_precise_mode_is_announced(self):
        self._save([self._edge("FR-001", "BG-001")])
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("satisfies", result.lower())

    def test_other_chapters_nodes_are_not_counted_as_requirements(self):
        """FOUND BY E2E, not by unit tests: other chapters push their own nodes into the
        SAME 5.1 graph — `change_request` (5.4), `risk` (6.3), `solution` (6.4), plus
        `test` (5.1). The skip-filter knew only the business roots, so a CR opened in 5.4
        was counted as a requirement AND listed as 'not linked to any objective'.

        Same class as findings 7.3-A / 7.4-C: a filter that knows only part of the set.
        """
        nodes = self._nodes() + [
            {"id": "CR-001", "type": "change_request", "title": "Change the rule",
             "version": "1.0", "status": "open", "added": str(date.today()),
             "source_artifact": ""},
            {"id": "RK-001", "type": "risk", "title": "Vendor delay",
             "version": "1.0", "status": "open", "added": str(date.today()),
             "source_artifact": ""},
            # NOTE: `solution` is deliberately NOT in this list — see the dedicated
            # test below. The literal is shared with the BABOK requirement class.
            {"id": "TC-001", "type": "test", "title": "Assignment test",
             "version": "1.0", "status": "draft", "added": str(date.today()),
             "source_artifact": ""},
        ]
        self._save([self._edge("FR-001", "BG-001")], nodes=nodes)
        result = mod71.build_coverage_matrix(self.P)
        # unchanged count: FR-001, FR-002, DD-001 only
        self.assertIn("| Requirements in the registry | 3 |", result)
        for foreign in ("CR-001", "RK-001", "TC-001"):
            self.assertNotIn(foreign, result)

    def test_a_solution_class_requirement_is_still_counted(self):
        """`solution` is TWO things: 6.4's scope node (ADR-082) AND the BABOK
        requirement class in the 5.1 vocabulary — which is how init_traceability_repo
        and the Confluence import label ordinary FR/NFR.

        Skipping the literal to exclude 6.4's node silently dropped real requirements
        from the matrix. Between over-counting a scope node and under-counting a
        requirement, only the second is a lie about coverage.
        """
        nodes = [
            {"id": "BG-001", "type": "business_goal", "title": "Cut handling time",
             "version": "1.0", "status": "confirmed", "added": str(date.today()),
             "source_artifact": ""},
            {"id": "FR-900", "type": "solution", "title": "Auto-assign requests",
             "version": "1.0", "status": "draft", "added": str(date.today()),
             "source_artifact": ""},
        ]
        self._save([], nodes=nodes)
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("| Requirements in the registry | 1 |", result)
        self.assertIn("FR-900", result)


class TestTheSpecFillsAGraphNodeThatWasCreatedEmpty(BaseMCPTest):
    """Pre-release E2E finding E2-1. The analyst's `owner` never reached the graph.

    The documented order is: `init_traceability_repo` (5.1) lays out the ids, titles and
    types, then 7.1 writes each specification — with the owner, the priority and the
    source artifact. But `_register_in_repo` returns early for an id it already knows,
    so everything the specification stated was dropped into the void, and the note said
    only "already registered in repository 5.1".

    Live consequences, all on the default route: 7.4 reads `owner` as EVIDENCE that a
    stakeholder is represented, so the person the analyst named became a 🔴 critical gap
    in a signed architecture document; the 5.5 approval package showed a blank owner —
    the exact defect the comment on the CREATE path says was fixed; and the 5.2 audit
    reported the attribute as unfilled.

    This module had already learned the lesson FOR EDGES: its own docstring says an
    early return must not stop newly declared links from being written. Fields were left
    behind.

    Insert-only: a value already on the node is never overwritten — that is another
    chapter's statement, and a specification re-run must not silently replace it.
    """

    P = "backfill71"

    def _seed_graph(self, **extra):
        node = {"id": "FR-001", "type": "functional", "title": "Invoice matching",
                "version": "1.0", "status": "draft"}
        node.update(extra)
        save_spec_repo({"project": self.P, "requirements": [node],
                        "links": [], "history": []})

    def test_the_owner_named_in_the_spec_reaches_the_graph(self):
        self._seed_graph()
        mod71._register_in_repo(self.P, "FR-001", "functional", "Invoice matching",
                                "spec.md", "High", owner="Sergey Bok")
        node = load_spec_repo(self.P)["requirements"][0]
        self.assertEqual(node.get("owner"), "Sergey Bok")

    def test_an_owner_already_recorded_is_never_replaced(self):
        self._seed_graph(owner="Vera Ilyina")
        mod71._register_in_repo(self.P, "FR-001", "functional", "Invoice matching",
                                "spec.md", "High", owner="Sergey Bok")
        node = load_spec_repo(self.P)["requirements"][0]
        self.assertEqual(node.get("owner"), "Vera Ilyina",
                         "another chapter's statement is not overwritten by a re-run")

    def test_the_note_says_what_it_filled_in(self):
        self._seed_graph()
        note = mod71._register_in_repo(self.P, "FR-001", "functional", "Invoice matching",
                                       "spec.md", "High", owner="Sergey Bok")
        self.assertIn("owner", note.lower(),
                      "silently filling is better than silently dropping, but saying "
                      "so is better than both")

    def test_nothing_is_claimed_when_there_was_nothing_to_fill(self):
        self._seed_graph(owner="Vera Ilyina", priority="High",
                         source_artifact="spec.md")
        note = mod71._register_in_repo(self.P, "FR-001", "functional", "Invoice matching",
                                       "spec.md", "High", owner="Sergey Bok")
        self.assertNotIn("owner", note.lower())

    def test_a_brand_new_node_still_carries_its_owner(self):
        """The guard on over-fixing: the CREATE path must keep working."""
        mod71._register_in_repo(self.P, "FR-777", "functional", "New one",
                                "spec.md", "High", owner="Sergey Bok")
        node = [r for r in load_spec_repo(self.P)["requirements"]
                if r["id"] == "FR-777"][0]
        self.assertEqual(node["owner"], "Sergey Bok")


class TestTheNotFoundMessageDescribesTheSearchThatRan(BaseMCPTest):
    """The wave removed the flat fallbacks and left the diagnostics describing them.

    `_find_confirmed_artifact` globs `reports/<project_id>/4_3_*confirmed*.md` — the
    project id is the FOLDER, and the filename does not carry it. The message still
    announced `governance_plans/4_3_<project_id>_confirmed*.md`, a shape nothing looks
    at any more. An analyst who follows it literally puts the file where the tool will
    never look, and "the tool searched for" is a false statement about the tool.

    So the message is built from the same pattern the search uses, and the test does
    what the analyst would do: read the path out of the message, put a file there, and
    require the tool to find it."""

    P = "pattern_probe"

    def _named_pattern(self, out):
        """The path the message tells the analyst about."""
        quoted = [seg for seg in out.split("`") if "4_3" in seg and seg.endswith(".md")]
        self.assertEqual(len(quoted), 1, f"expected exactly one named path in:\n{out}")
        return quoted[0]

    def test_following_the_named_pattern_produces_a_file_the_tool_finds(self):
        out = mod71.analyze_elicitation_context(self.P)
        self.assertIn("not found", out)

        pattern = self._named_pattern(out)
        concrete = os.path.join(PROJECT_ROOT_TMP(), pattern.replace("*", "probe"))
        os.makedirs(os.path.dirname(concrete), exist_ok=True)
        with open(concrete, "w", encoding="utf-8") as f:
            f.write("# 4.3 confirmed result\n\nBusiness objective: cut handling time.\n")

        out2 = mod71.analyze_elicitation_context(self.P)
        self.assertIn("File found", out2,
                      f"the analyst followed the message and put the file at "
                      f"{concrete}; the tool still does not see it")

    def test_the_message_does_not_name_the_layout_that_was_removed(self):
        out = mod71.analyze_elicitation_context(self.P)
        self.assertNotIn(f"governance_plans/4_3_{self.P}", out,
                         "the flat layout was dropped on 2026-08-03")


def PROJECT_ROOT_TMP():
    """Tests run chdir'd into a temp dir (BaseMCPTest); paths in the message are
    relative to it, which is exactly how the analyst would read them."""
    return os.getcwd()


if __name__ == "__main__":
    unittest.main(verbosity=2)
