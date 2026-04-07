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

# Моки применяются через conftest
from tests.conftest import BaseMCPTest, make_test_repo, save_test_repo, load_test_repo

import skills.requirements_spec_mcp as mod71


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
    """Сохраняет репозиторий 5.1 для тестов."""
    safe = repo["project"].lower().replace(" ", "_")
    path = os.path.join(governance_dir, f"{safe}_traceability_repo.json")
    os.makedirs(governance_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)
    return path


def load_spec_repo(project_id: str, governance_dir: str = "governance_plans/data") -> dict:
    """Загружает репозиторий 5.1."""
    safe = project_id.lower().replace(" ", "_")
    path = os.path.join(governance_dir, f"{safe}_traceability_repo.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def make_confirmed_artifact(project_id: str, content: str = None) -> str:
    """Создаёт тестовый артефакт 4.3 и возвращает путь."""
    safe = project_id.lower().replace(" ", "_")
    filename = f"4_3_{safe}_confirmed_test.md"
    path = os.path.join("governance_plans", "data", filename)
    os.makedirs(os.path.join("governance_plans", "data"), exist_ok=True)
    artifact_content = content or f"""# Подтверждённые результаты выявления

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
    with open(path, "w", encoding="utf-8") as f:
        f.write(artifact_content)
    return path


# ---------------------------------------------------------------------------
# 7.1 — Тесты утилит
# ---------------------------------------------------------------------------

class TestSpecUtilities(unittest.TestCase):

    def test_repo_path_normalizes_spaces(self):
        path = mod71._repo_path("My Project")
        self.assertNotIn(" ", path)
        self.assertIn("my_project", path)
        self.assertIn("traceability_repo.json", path)

    def test_repo_path_lowercase(self):
        path = mod71._repo_path("CRM 2024")
        self.assertIn("crm_2024", path)

    def test_specs_dir_format(self):
        d = mod71._specs_dir("crm_2024")
        self.assertIn("crm_2024_specs", d)
        self.assertIn("governance_plans", d)

    def test_specs_dir_normalizes_spaces(self):
        d = mod71._specs_dir("My Project")
        self.assertNotIn(" ", d)
        self.assertIn("my_project_specs", d)

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

    def test_deprecated_excluded(self):
        """Deprecated требования не включаются в матрицу."""
        repo = make_spec_repo(self.P, [
            {"id": "FR-001", "type": "functional", "title": "Активный",
             "version": "1.0", "status": "draft", "added": str(date.today()),
             "source_artifact": ""},
            {"id": "FR-DEP", "type": "functional", "title": "Устаревший",
             "version": "1.0", "status": "deprecated", "added": str(date.today()),
             "source_artifact": ""},
        ])
        save_spec_repo(repo)
        result = mod71.build_coverage_matrix(self.P)
        # FR-001 должен быть, FR-DEP — нет
        self.assertIn("FR-001", result)
        self.assertNotIn("FR-DEP", result)

    def test_shows_summary_table(self):
        repo = make_spec_repo(self.P, [
            {"id": "FR-001", "type": "functional", "title": "Тест",
             "version": "1.0", "status": "draft", "added": str(date.today()), "source_artifact": ""},
        ])
        save_spec_repo(repo)
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("Сводка", result)
        self.assertIn("Требований в реестре", result)

    def test_over_engineering_flag_triggers(self):
        """10+ требований на одну цель → флаг over-engineering."""
        reqs = [
            {"id": f"FR-{i:03d}", "type": "functional", "title": f"Req {i}",
             "version": "1.0", "status": "draft", "added": str(date.today()), "source_artifact": ""}
            for i in range(12)
        ]
        save_spec_repo(make_spec_repo(self.P, reqs))
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("🟡", result)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
