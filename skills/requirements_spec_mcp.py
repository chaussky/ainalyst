"""
BABOK 7.1 — Specify and Model Requirements
MCP-инструменты для формализации требований из результатов выявления.

Инструменты:
  - analyze_elicitation_context  — анализ артефактов 4.3, список требований-кандидатов
  - create_user_story            — User Story с AC, авторегистрация в 5.1
  - create_functional_requirement — SRS-style (functional/non_functional/business_rule), авторегистрация в 5.1
  - create_use_case              — текстовая спецификация UC, авторегистрация в 5.1
  - generate_use_case_diagram    — PlantUML Use Case Diagram по всем UC проекта
  - create_business_process      — текст + PlantUML Activity Diagram, авторегистрация в 5.1
  - create_data_dictionary       — реестр сущностей и атрибутов, авторегистрация в 5.1
  - create_erd                   — описание связей + PlantUML ER Diagram, авторегистрация в 5.1
  - build_coverage_matrix        — матрица «бизнес-цель → требования» с флагами покрытия

ADR-022: каждый создающий инструмент регистрирует req в 5.1 автоматически (статус draft)
ADR-023: analyze_elicitation_context — гибридное чтение (файл 4.3 → fallback на context_text)
ADR-024: create_business_process генерирует .md + .puml
ADR-025: PlantUML для всех диаграмм

Хранение артефактов: governance_plans/{project_id}_specs/

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
import glob
from datetime import date
from typing import Optional
from mcp.server.fastmcp import FastMCP
from skills.common import save_artifact, logger, DATA_DIR

mcp = FastMCP("BABOK_Requirements_Spec")

REPO_FILENAME = "traceability_repo.json"
CONFIRMED_GLOB = "4_3_*_confirmed*.md"


# ---------------------------------------------------------------------------
# Утилиты — репозиторий 5.1
# ---------------------------------------------------------------------------

def _repo_path(project_id: str) -> str:
    safe = project_id.lower().replace(" ", "_")
    return os.path.join(DATA_DIR, f"{safe}_{REPO_FILENAME}")


def _load_repo(project_id: str) -> dict:
    path = _repo_path(project_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "project": project_id,
        "formality_level": "Standard",
        "created": str(date.today()),
        "updated": str(date.today()),
        "requirements": [],
        "links": [],
        "history": [],
    }


def _save_repo(repo: dict) -> None:
    path = _repo_path(repo["project"])
    os.makedirs(DATA_DIR, exist_ok=True)
    repo["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)
    logger.info(f"Репозиторий 5.1 обновлён (7.1): {path}")


def _register_in_repo(project_id: str, req_id: str, req_type: str,
                      title: str, source_artifact: str, priority: str = "Medium") -> str:
    """
    ADR-022: регистрирует требование в репозитории 5.1 со статусом draft.
    Если требование с таким ID уже есть — пропускает (без ошибки).
    Возвращает строку-пометку для включения в артефакт.
    """
    repo = _load_repo(project_id)
    existing_ids = {r["id"] for r in repo["requirements"]}

    if req_id in existing_ids:
        logger.info(f"_register_in_repo: {req_id} уже в репозитории, пропускаем")
        return f"ℹ️ `{req_id}` уже зарегистрирован в репозитории 5.1."

    entry = {
        "id": req_id,
        "type": req_type,
        "title": title,
        "version": "1.0",
        "status": "draft",
        "priority": priority,
        "owner": "",
        "stability": "Unknown",
        "source_artifact": source_artifact,
        "added": str(date.today()),
        "last_reviewed": str(date.today()),
    }
    repo["requirements"].append(entry)
    repo["history"].append({
        "action": "requirement_added",
        "req_id": req_id,
        "source": "7.1_spec",
        "date": str(date.today()),
    })
    _save_repo(repo)
    return f"✅ `{req_id}` зарегистрирован в репозитории 5.1 (статус: draft)."


# ---------------------------------------------------------------------------
# Утилиты — файловая система
# ---------------------------------------------------------------------------

def _specs_dir(project_id: str) -> str:
    safe = project_id.lower().replace(" ", "_")
    return os.path.join(DATA_DIR, f"{safe}_specs")


def _save_spec(content: str, project_id: str, filename: str) -> str:
    """Сохраняет артефакт в governance_plans/{project_id}_specs/. Возвращает путь."""
    specs_dir = _specs_dir(project_id)
    os.makedirs(specs_dir, exist_ok=True)
    filepath = os.path.join(specs_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"Спецификация сохранена: {filepath}")
    return filepath


def _find_confirmed_artifact(project_id: str) -> Optional[str]:
    """
    ADR-023: ищет последний подтверждённый артефакт 4.3 для project_id.
    Паттерн: governance_plans/4_3_{project_id}_confirmed*.md (регистронезависимо).
    """
    safe = project_id.lower().replace(" ", "_")
    patterns = [
        os.path.join(DATA_DIR, f"4_3_{safe}_confirmed*.md"),
        os.path.join(DATA_DIR, f"4_3_*{safe}*confirmed*.md"),
        os.path.join(DATA_DIR, f"*4_3*{safe}*confirmed*.md"),
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            # берём самый свежий по имени
            return sorted(matches)[-1]
    return None


def _read_confirmed_artifact(path: str) -> str:
    """Читает содержимое артефакта 4.3."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# 7.1.1 — Анализ контекста выявления (ADR-023)
# ---------------------------------------------------------------------------

@mcp.tool()
def analyze_elicitation_context(
    project_id: str,
    context_text: str = "",
) -> str:
    """
    BABOK 7.1 — Анализирует подтверждённые результаты выявления (4.3) и предлагает
    список требований-кандидатов с классификацией по типу и рекомендуемым ID-префиксом.

    ADR-023 (гибридное чтение):
      1. Пробует найти файл 4.3 по project_id в governance_plans/
      2. Если не найден и context_text пустой — возвращает инструкцию
      3. Если не найден, но context_text задан — использует переданный текст

    Args:
        project_id:    Идентификатор проекта (используется для поиска файла 4.3).
        context_text:  Текст артефакта 4.3 (если файл не найден автоматически).
                       Оставить пустым — инструмент попробует найти файл сам.

    Returns:
        Список бизнес-целей, требований-кандидатов и информационных пробелов.
    """
    logger.info(f"analyze_elicitation_context: project_id='{project_id}'")

    # ADR-023: гибридное чтение
    source_used = ""
    content_to_analyze = ""

    artifact_path = _find_confirmed_artifact(project_id)
    if artifact_path:
        content_to_analyze = _read_confirmed_artifact(artifact_path)
        source_used = f"📂 Файл найден автоматически: `{artifact_path}`"
        logger.info(f"Найден артефакт 4.3: {artifact_path}")
    elif context_text.strip():
        content_to_analyze = context_text.strip()
        source_used = "📋 Использован текст, переданный вручную."
        logger.info("Артефакт 4.3 не найден — используем context_text")
    else:
        return (
            f"⚠️ Артефакт 4.3 не найден для проекта `{project_id}`.\n\n"
            f"Инструмент искал файлы по паттерну:\n"
            f"`governance_plans/4_3_{project_id.lower().replace(' ', '_')}_confirmed*.md`\n\n"
            f"**Варианты действий:**\n"
            f"1. Убедись что артефакт 4.3 создан через `save_confirmed_elicitation_result` (4.3)\n"
            f"2. Передай содержимое вручную: `analyze_elicitation_context("
            f"project_id='{project_id}', context_text='[вставь текст артефакта 4.3]')`"
        )

    # Формируем аналитический запрос к содержимому
    # (Инструмент выполняется Claude Code — он читает контент и рассуждает о нём)
    word_count = len(content_to_analyze.split())
    line_count = content_to_analyze.count("\n")

    lines = [
        f"<!-- BABOK 7.1 — Анализ контекста | Проект: {project_id} | {date.today()} -->",
        "",
        f"# 🔍 Анализ контекста выявления",
        "",
        f"**Проект:** {project_id}  ",
        f"**Дата:** {date.today()}  ",
        f"**Источник:** {source_used}  ",
        f"**Объём:** {word_count} слов, {line_count} строк",
        "",
        "---",
        "",
        "## Содержимое артефакта 4.3 для анализа",
        "",
        "Claude Code: прочти содержимое ниже и выполни анализ согласно шагам.",
        "",
        "```",
        content_to_analyze[:3000] + ("..." if len(content_to_analyze) > 3000 else ""),
        "```",
        "",
        "---",
        "",
        "## Инструкция по анализу (для Claude Code)",
        "",
        "На основе содержимого артефакта 4.3 выше выполни следующее:",
        "",
        "### 1. Извлеки бизнес-цели",
        "Найди все упомянутые бизнес-цели (раздел 'Бизнес-цели' или эквивалент).",
        "Если явного раздела нет — выведи цели из контекста.",
        "",
        "### 2. Классифицируй требования-кандидаты",
        "Для каждого выявленного требования/потребности определи тип:",
        "",
        "| Тип | ID-префикс | Когда использовать |",
        "|-----|-----------|-------------------|",
        "| user_story | US- | Пользовательская потребность в Agile-контексте |",
        "| functional | FR- | Поведение системы, Predictive-контекст |",
        "| non_functional | NFR- | Качественные характеристики (SLA, скорость, безопасность) |",
        "| business_rule | BR- | Бизнес-правило или ограничение предметной области |",
        "| use_case | UC- | Сценарий взаимодействия актора с системой |",
        "| business_process | BP- | Бизнес-процесс с несколькими участниками |",
        "| data_dictionary | DD- | Описание структуры данных/сущностей |",
        "| erd | ERD- | Связи между сущностями |",
        "",
        "### 3. Выяви информационные пробелы",
        "Укажи темы, по которым выявление не дало достаточно информации для спецификации.",
        "Для каждого пробела — рекомендация: провести дополнительную сессию выявления или уточнить у стейкхолдера.",
        "",
        "### 4. Предложи порядок создания артефактов",
        "Порядок от общего к частному: бизнес-правила → use cases → functional requirements → данные.",
        "",
        "---",
        "",
        "## Следующий шаг",
        "",
        "После анализа используй инструменты 7.1 для создания артефактов:",
        "- `create_user_story` — для User Stories",
        "- `create_functional_requirement` — для FR/NFR/BR",
        "- `create_use_case` — для Use Cases",
        "- `create_business_process` — для Business Processes",
        "- `create_data_dictionary` + `create_erd` — для данных",
        "- `build_coverage_matrix` — в конце для проверки покрытия",
    ]

    result = "\n".join(lines)
    save_artifact(result, prefix="7_1_context_analysis")
    return result


# ---------------------------------------------------------------------------
# 7.1.2 — User Story
# ---------------------------------------------------------------------------

@mcp.tool()
def create_user_story(
    project_id: str,
    story_id: str,
    title: str,
    role: str,
    action: str,
    benefit: str,
    acceptance_criteria_json: str,
    priority: str = "Medium",
    source_artifact: str = "",
    notes: str = "",
) -> str:
    """
    BABOK 7.1 — Создаёт User Story с Acceptance Criteria.
    Автоматически регистрирует в репозитории 5.1 (статус draft). ADR-022.

    Args:
        project_id:                Идентификатор проекта.
        story_id:                  ID истории: US-001, US-002 и т.д.
        title:                     Краткое название (для заголовка и реестра 5.1).
        role:                      Роль пользователя: «Менеджер по заявкам», «Клиент», «Администратор».
        action:                    Что пользователь хочет сделать (без «я хочу»).
        benefit:                   Бизнес-ценность (без «чтобы»).
        acceptance_criteria_json:  JSON-список критериев приёмки: ["Критерий 1", "Критерий 2"]
                                   Минимум 2 критерия.
        priority:                  High | Medium | Low. По умолчанию Medium.
        source_artifact:           Путь к артефакту 4.3 (для трассировки).
        notes:                     Дополнительный контекст, ограничения, ссылки.

    Returns:
        Markdown-артефакт User Story + подтверждение регистрации в 5.1.
    """
    logger.info(f"create_user_story: {story_id} в проекте '{project_id}'")

    try:
        criteria = json.loads(acceptance_criteria_json)
        if not isinstance(criteria, list):
            raise ValueError("Должен быть список")
    except (json.JSONDecodeError, ValueError) as e:
        return f"❌ Ошибка парсинга acceptance_criteria_json: {e}\nОжидается JSON-список: [\"Критерий 1\", \"Критерий 2\"]"

    if len(criteria) < 2:
        return "❌ Необходимо минимум 2 Acceptance Criteria. User Story без AC — не требование."

    criteria_md = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(criteria))

    lines = [
        f"<!-- BABOK 7.1 — User Story | Проект: {project_id} | {date.today()} -->",
        "",
        f"# {story_id} — {title}",
        "",
        "| Атрибут | Значение |",
        "|---------|----------|",
        f"| Тип | User Story |",
        f"| Проект | {project_id} |",
        f"| Источник | {source_artifact or '—'} |",
        f"| Приоритет | {priority} |",
        f"| Статус | draft |",
        f"| Версия | 1.0 |",
        f"| Дата | {date.today()} |",
        "",
        "---",
        "",
        "## История",
        "",
        f"As a **{role}**,  ",
        f"I want **{action}**,  ",
        f"So that **{benefit}**.",
        "",
        "## Acceptance Criteria",
        "",
        criteria_md,
    ]

    if notes:
        lines += ["", "## Дополнительный контекст", "", notes]

    lines += [
        "",
        "---",
        "",
        "## Трассировка",
        "",
        f"| Связь | Артефакт |",
        f"|-------|----------|",
        f"| Источник (4.3) | {source_artifact or '—'} |",
        f"| Реестр (5.1) | регистрация автоматическая |",
    ]

    content = "\n".join(lines)

    # Сохраняем артефакт
    safe_id = story_id.lower().replace("-", "_")
    safe_title = title.lower().replace(" ", "_")[:30]
    filename = f"{safe_id}_{safe_title}.md"
    spec_path = _save_spec(content, project_id, filename)

    # ADR-022: авторегистрация в 5.1
    reg_note = _register_in_repo(project_id, story_id, "user_story", title, spec_path, priority)

    return content + f"\n\n---\n\n**Регистрация в 5.1:** {reg_note}\n**Файл:** `{spec_path}`"


# ---------------------------------------------------------------------------
# 7.1.3 — Functional Requirement
# ---------------------------------------------------------------------------

@mcp.tool()
def create_functional_requirement(
    project_id: str,
    req_id: str,
    req_type: str,
    title: str,
    description: str,
    rationale: str,
    priority: str = "Medium",
    owner: str = "",
    source_artifact: str = "",
    constraints: str = "",
    related_ids_json: str = "[]",
) -> str:
    """
    BABOK 7.1 — Создаёт формальное требование в стиле SRS.
    Автоматически регистрирует в репозитории 5.1 (статус draft). ADR-022.

    Args:
        project_id:        Идентификатор проекта.
        req_id:            ID требования: FR-001, NFR-001, BR-001.
        req_type:          functional | non_functional | business_rule
        title:             Краткое название требования.
        description:       Полная формулировка.
                           functional:     «Система ДОЛЖНА [действие]...»
                           non_functional: «Система ДОЛЖНА [метрика] [значение] при [условии]»
                           business_rule:  «[Субъект] [ограничение/правило]»
        rationale:         Обоснование — зачем нужно это требование.
        priority:          High | Medium | Low.
        owner:             Владелец/стейкхолдер ответственный за требование.
        source_artifact:   Путь к артефакту 4.3.
        constraints:       Ограничения и допущения.
        related_ids_json:  JSON-список связанных ID: ["BR-001", "UC-001"]

    Returns:
        Markdown-артефакт требования + подтверждение регистрации в 5.1.
    """
    logger.info(f"create_functional_requirement: {req_id} ({req_type}) в проекте '{project_id}'")

    valid_types = {"functional", "non_functional", "business_rule"}
    if req_type not in valid_types:
        return (
            f"❌ Недопустимый req_type: '{req_type}'.\n"
            f"Допустимые значения: functional | non_functional | business_rule"
        )

    try:
        related_ids = json.loads(related_ids_json)
        if not isinstance(related_ids, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        related_ids = []

    type_labels = {
        "functional": "Функциональное требование",
        "non_functional": "Нефункциональное требование",
        "business_rule": "Бизнес-правило",
    }

    type_hints = {
        "functional": "Формулировка: «Система ДОЛЖНА [действие]...»",
        "non_functional": "Формулировка: «Система ДОЛЖНА [метрика] [значение] при [условии]»",
        "business_rule": "Формулировка: «[Субъект] [ограничение]» — без привязки к системе",
    }

    related_md = ", ".join(f"`{r}`" for r in related_ids) if related_ids else "—"

    lines = [
        f"<!-- BABOK 7.1 — {type_labels[req_type]} | Проект: {project_id} | {date.today()} -->",
        "",
        f"# {req_id} — {title}",
        "",
        "| Атрибут | Значение |",
        "|---------|----------|",
        f"| Тип | {type_labels[req_type]} |",
        f"| Проект | {project_id} |",
        f"| Источник | {source_artifact or '—'} |",
        f"| Приоритет | {priority} |",
        f"| Владелец | {owner or '—'} |",
        f"| Статус | draft |",
        f"| Версия | 1.0 |",
        f"| Дата | {date.today()} |",
        "",
        "---",
        "",
        "## Формулировка",
        "",
        f"> _{type_hints[req_type]}_",
        "",
        description,
        "",
        "## Обоснование",
        "",
        rationale,
    ]

    if constraints:
        lines += ["", "## Ограничения и допущения", "", constraints]

    lines += [
        "",
        "## Связанные требования",
        "",
        related_md,
        "",
        "---",
        "",
        "## Трассировка",
        "",
        "| Связь | Артефакт |",
        "|-------|----------|",
        f"| Источник (4.3) | {source_artifact or '—'} |",
        f"| Реестр (5.1) | регистрация автоматическая |",
    ]

    content = "\n".join(lines)

    safe_id = req_id.lower().replace("-", "_")
    safe_title = title.lower().replace(" ", "_")[:30]
    filename = f"{safe_id}_{safe_title}.md"
    spec_path = _save_spec(content, project_id, filename)

    # ADR-022: авторегистрация
    repo_type_map = {
        "functional": "functional",
        "non_functional": "non_functional",
        "business_rule": "business_rule",
    }
    reg_note = _register_in_repo(project_id, req_id, repo_type_map[req_type], title, spec_path, priority)

    return content + f"\n\n---\n\n**Регистрация в 5.1:** {reg_note}\n**Файл:** `{spec_path}`"


# ---------------------------------------------------------------------------
# 7.1.4 — Use Case
# ---------------------------------------------------------------------------

@mcp.tool()
def create_use_case(
    project_id: str,
    uc_id: str,
    title: str,
    primary_actor: str,
    precondition: str,
    postcondition: str,
    trigger: str,
    main_scenario: str,
    priority: str = "Medium",
    secondary_actors: str = "",
    alt_scenarios: str = "",
    exc_scenarios: str = "",
    business_rules: str = "",
    source_artifact: str = "",
) -> str:
    """
    BABOK 7.1 — Создаёт текстовую спецификацию Use Case.
    Автоматически регистрирует в репозитории 5.1 (статус draft). ADR-022.

    Args:
        project_id:        Идентификатор проекта.
        uc_id:             ID use case: UC-001, UC-002.
        title:             Название UC в формате «Глагол + Объект»: «Оформить заявку».
        primary_actor:     Основной актор инициирующий UC.
        precondition:      Условие которое должно быть истинно до начала UC.
        postcondition:     Состояние системы после успешного завершения UC.
        trigger:           Событие запускающее UC.
        main_scenario:     Основной сценарий (Happy Path). Нумерованные шаги через \\n.
        priority:          High | Medium | Low.
        secondary_actors:  Вторичные акторы через запятую.
        alt_scenarios:     Альтернативные сценарии (нумерация: 2а, 3б...).
        exc_scenarios:     Сценарии исключений (нумерация: Xа, Yб...).
        business_rules:    Бизнес-правила применяемые в UC.
        source_artifact:   Путь к артефакту 4.3.

    Returns:
        Markdown-артефакт Use Case + подтверждение регистрации в 5.1.
    """
    logger.info(f"create_use_case: {uc_id} в проекте '{project_id}'")

    lines = [
        f"<!-- BABOK 7.1 — Use Case | Проект: {project_id} | {date.today()} -->",
        "",
        f"# {uc_id} — {title}",
        "",
        "| Атрибут | Значение |",
        "|---------|----------|",
        f"| Тип | Use Case |",
        f"| Проект | {project_id} |",
        f"| Источник | {source_artifact or '—'} |",
        f"| Приоритет | {priority} |",
        f"| Статус | draft |",
        f"| Версия | 1.0 |",
        f"| Дата | {date.today()} |",
        "",
        "---",
        "",
        "## Общая информация",
        "",
        "| Атрибут | Значение |",
        "|---------|----------|",
        f"| Актор (primary) | {primary_actor} |",
        f"| Акторы (secondary) | {secondary_actors or '—'} |",
        f"| Предусловие | {precondition} |",
        f"| Постусловие | {postcondition} |",
        f"| Триггер | {trigger} |",
        "",
        "## Основной сценарий (Happy Path)",
        "",
        main_scenario,
    ]

    if alt_scenarios:
        lines += ["", "## Альтернативные сценарии", "", alt_scenarios]

    if exc_scenarios:
        lines += ["", "## Сценарии исключений", "", exc_scenarios]

    if business_rules:
        lines += ["", "## Бизнес-правила и ограничения", "", business_rules]

    lines += [
        "",
        "---",
        "",
        "## Трассировка",
        "",
        "| Связь | Артефакт |",
        "|-------|----------|",
        f"| Источник (4.3) | {source_artifact or '—'} |",
        f"| Реестр (5.1) | регистрация автоматическая |",
    ]

    content = "\n".join(lines)

    safe_id = uc_id.lower().replace("-", "_")
    safe_title = title.lower().replace(" ", "_")[:30]
    filename = f"{safe_id}_{safe_title}.md"
    spec_path = _save_spec(content, project_id, filename)

    reg_note = _register_in_repo(project_id, uc_id, "use_case", title, spec_path, priority)

    return content + f"\n\n---\n\n**Регистрация в 5.1:** {reg_note}\n**Файл:** `{spec_path}`"


# ---------------------------------------------------------------------------
# 7.1.5 — Use Case Diagram (PlantUML)
# ---------------------------------------------------------------------------

@mcp.tool()
def generate_use_case_diagram(
    project_id: str,
    system_boundary: str,
    diagram_name: str = "",
) -> str:
    """
    BABOK 7.1 — Генерирует PlantUML Use Case Diagram по всем UC из репозитория 5.1.
    ADR-025: PlantUML нотация.

    Читает все требования типа 'use_case' из репозитория 5.1 и строит сводную диаграмму.
    Акторы извлекаются из файлов спецификаций UC (если доступны).

    Args:
        project_id:      Идентификатор проекта.
        system_boundary: Название системы/подсистемы (прямоугольник на диаграмме).
        diagram_name:    Имя файла диаграммы (без расширения). По умолчанию: {project_id}_uc.

    Returns:
        PlantUML-код диаграммы + путь к .puml файлу.
    """
    logger.info(f"generate_use_case_diagram: '{project_id}'")

    repo = _load_repo(project_id)
    use_cases = [r for r in repo["requirements"] if r.get("type") == "use_case"]

    if not use_cases:
        return (
            f"⚠️ В репозитории проекта `{project_id}` нет Use Cases.\n"
            f"Сначала создай Use Cases с помощью `create_use_case`."
        )

    name = diagram_name or f"{project_id.lower().replace(' ', '_')}_uc"

    # Генерируем PlantUML
    puml_lines = [
        f"@startuml {name}",
        "left to right direction",
        "skinparam packageStyle rectangle",
        "skinparam actorStyle awesome",
        "skinparam backgroundColor #FFFFFF",
        "skinparam usecase {",
        "  BackgroundColor #FAFAFA",
        "  BorderColor #AAAAAA",
        "}",
        "",
        f'title Use Case Diagram — {system_boundary}',
        "",
    ]

    # Пробуем извлечь акторов из файлов спецификаций
    actors = set()
    uc_actor_map = {}  # uc_id -> primary_actor

    specs_dir = _specs_dir(project_id)
    for uc in use_cases:
        uc_id = uc["id"]
        # Ищем файл спецификации
        pattern = os.path.join(specs_dir, f"{uc_id.lower().replace('-', '_')}*.md")
        matches = glob.glob(pattern)
        if matches:
            try:
                with open(matches[0], "r", encoding="utf-8") as f:
                    spec_content = f.read()
                # Простой парсинг primary actor из таблицы
                for line in spec_content.split("\n"):
                    if "Актор (primary)" in line:
                        parts = line.split("|")
                        if len(parts) >= 3:
                            actor = parts[2].strip()
                            if actor and actor != "Значение":
                                actors.add(actor)
                                uc_actor_map[uc_id] = actor
            except (IOError, IndexError):
                pass

    if not actors:
        actors = {"Пользователь"}  # fallback
        for uc in use_cases:
            uc_actor_map[uc["id"]] = "Пользователь"

    # Объявляем акторов
    actor_aliases = {}
    for i, actor in enumerate(sorted(actors)):
        alias = f"A{i + 1}"
        actor_aliases[actor] = alias
        puml_lines.append(f'actor "{actor}" as {alias}')

    puml_lines.append("")

    # Прямоугольник системы
    puml_lines.append(f'rectangle "{system_boundary}" {{')

    for uc in use_cases:
        uc_alias = uc["id"].replace("-", "")
        puml_lines.append(f'    usecase "{uc["title"]}" as {uc_alias}')

    puml_lines.append("}")
    puml_lines.append("")

    # Связи актор → UC
    for uc in use_cases:
        uc_id = uc["id"]
        actor = uc_actor_map.get(uc_id, sorted(actors)[0])
        actor_alias = actor_aliases.get(actor, "A1")
        uc_alias = uc_id.replace("-", "")
        puml_lines.append(f"{actor_alias} --> {uc_alias}")

    puml_lines.append("")
    puml_lines.append("@enduml")

    puml_content = "\n".join(puml_lines)

    # Сохраняем .puml
    puml_filename = f"uc_diagram_{name}.puml"
    puml_path = _save_spec(puml_content, project_id, puml_filename)

    result_lines = [
        f"<!-- BABOK 7.1 — Use Case Diagram | Проект: {project_id} | {date.today()} -->",
        "",
        f"# Use Case Diagram — {system_boundary}",
        "",
        f"**Проект:** {project_id}  ",
        f"**Use Cases на диаграмме:** {len(use_cases)}  ",
        f"**Акторы:** {', '.join(sorted(actors))}  ",
        f"**Файл диаграммы:** `{puml_path}`  ",
        f"**Дата:** {date.today()}",
        "",
        "---",
        "",
        "## PlantUML код",
        "",
        "```plantuml",
        puml_content,
        "```",
        "",
        "---",
        "",
        "## Как рендерить",
        "",
        "1. **PlantUML Online:** https://www.plantuml.com/plantuml/uml/",
        "2. **VS Code:** расширение «PlantUML» (jebbs.plantuml)",
        "3. **CLI:** `plantuml " + puml_path + "`",
        "",
        "---",
        "",
        "## Use Cases на диаграмме",
        "",
        "| ID | Название | Статус |",
        "|----|----------|--------|",
    ]

    for uc in use_cases:
        result_lines.append(f"| `{uc['id']}` | {uc['title']} | {uc.get('status', 'draft')} |")

    result = "\n".join(result_lines)
    save_artifact(result, prefix="7_1_uc_diagram")
    return result


# ---------------------------------------------------------------------------
# 7.1.6 — Business Process (ADR-024: .md + .puml)
# ---------------------------------------------------------------------------

@mcp.tool()
def create_business_process(
    project_id: str,
    bp_id: str,
    title: str,
    process_owner: str,
    trigger: str,
    outcome: str,
    participants: str,
    steps: str,
    priority: str = "Medium",
    business_rules: str = "",
    metrics: str = "",
    exceptions: str = "",
    source_artifact: str = "",
) -> str:
    """
    BABOK 7.1 — Создаёт описание бизнес-процесса.
    ADR-024: генерирует ДВА файла — текстовое описание .md и Activity Diagram .puml.
    Автоматически регистрирует в репозитории 5.1 (статус draft). ADR-022.

    Args:
        project_id:      Идентификатор проекта.
        bp_id:           ID процесса: BP-001, BP-002.
        title:           Название процесса: «Жизненный цикл заявки».
        process_owner:   Роль/подразделение ответственное за процесс.
        trigger:         Событие запускающее процесс.
        outcome:         Результат успешного завершения процесса.
        participants:    Участники процесса через запятую (роли/системы).
        steps:           Шаги процесса. Формат: «1. Роль: действие\\n2. Роль: действие».
                         Ветвления: «2а. Если [условие]: → шаг X. 2б. Иначе: → шаг Y.»
        priority:        High | Medium | Low.
        business_rules:  Бизнес-правила и ограничения процесса.
        metrics:         Метрики: время, конверсия, стоимость.
        exceptions:      Нештатные ситуации и обработка ошибок.
        source_artifact: Путь к артефакту 4.3.

    Returns:
        Markdown-артефакт процесса + PlantUML Activity Diagram + подтверждение регистрации в 5.1.
    """
    logger.info(f"create_business_process: {bp_id} в проекте '{project_id}'")

    # --- Текстовое описание .md ---
    participants_list = [p.strip() for p in participants.split(",") if p.strip()]

    md_lines = [
        f"<!-- BABOK 7.1 — Business Process | Проект: {project_id} | {date.today()} -->",
        "",
        f"# {bp_id} — {title}",
        "",
        "| Атрибут | Значение |",
        "|---------|----------|",
        f"| Тип | Business Process |",
        f"| Проект | {project_id} |",
        f"| Источник | {source_artifact or '—'} |",
        f"| Приоритет | {priority} |",
        f"| Статус | draft |",
        f"| Версия | 1.0 |",
        f"| Дата | {date.today()} |",
        "",
        "---",
        "",
        "## Общая информация",
        "",
        "| Атрибут | Значение |",
        "|---------|----------|",
        f"| Владелец процесса | {process_owner} |",
        f"| Триггер | {trigger} |",
        f"| Результат | {outcome} |",
        f"| Участники | {', '.join(participants_list)} |",
        "",
        "## Шаги процесса",
        "",
        steps,
    ]

    if business_rules:
        md_lines += ["", "## Бизнес-правила", "", business_rules]

    if metrics:
        md_lines += ["", "## Метрики процесса", "", metrics]

    if exceptions:
        md_lines += ["", "## Исключения и нештатные ситуации", "", exceptions]

    md_lines += [
        "",
        "---",
        "",
        "## Связанная диаграмма",
        "",
        f"Activity Diagram: `{bp_id.lower().replace('-', '_')}_{title.lower().replace(' ', '_')[:20]}.puml`",
        "",
        "Для рендеринга: https://www.plantuml.com/plantuml/uml/",
    ]

    md_content = "\n".join(md_lines)

    # --- PlantUML Activity Diagram .puml ---
    # ADR-024: генерируем из шагов текстового описания
    # Простая структура: swimlanes для участников + шаги из steps
    puml_name = f"{bp_id.lower().replace('-', '_')}_{title.lower().replace(' ', '_')[:20]}"

    puml_lines = [
        f"@startuml {puml_name}",
        "skinparam activityArrowColor #666666",
        "skinparam activityBackgroundColor #FAFAFA",
        "skinparam activityBorderColor #AAAAAA",
        "skinparam backgroundColor #FFFFFF",
        "",
        f"title Activity Diagram — {title}",
        "",
    ]

    # Swimlanes для участников
    if participants_list:
        first_participant = participants_list[0]
        puml_lines.append(f"|{first_participant}|")
    else:
        puml_lines.append("|Участник|")

    puml_lines.append("start")
    puml_lines.append("")

    # Добавляем триггер и шаги
    puml_lines.append(f":{trigger};")
    puml_lines.append("")

    # Парсим шаги — каждую строку начинающуюся с цифры добавляем как активность
    current_swimlane = participants_list[0] if participants_list else "Участник"
    step_count = 0
    for line in steps.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Ищем смену участника (формат "1. Роль: действие")
        if ". " in line and ":" in line:
            parts = line.split(":", 1)
            if len(parts) == 2:
                # Пытаемся определить участника
                step_part = parts[0]
                # Убираем номер шага
                for p in participants_list:
                    if p.lower() in step_part.lower():
                        if p != current_swimlane:
                            current_swimlane = p
                            puml_lines.append(f"|{p}|")
                        break

                action = parts[1].strip()
                if action:
                    puml_lines.append(f":{action};")
                    step_count += 1
        elif line.startswith(("2а", "2б", "3а", "3б")) or "Если" in line or "если" in line:
            # Упрощённая обработка ветвлений — как текстовая заметка
            note = line.lstrip("0123456789абвгдеёжзийклмнопрстуфхцчшщъыьэюяabcdefghijklmnopqrstuvwxyz. ")
            if note:
                puml_lines.append(f"note right: {note[:50]}")

    if step_count == 0:
        # Fallback: просто добавляем outcome как конечное состояние
        puml_lines.append(f":{outcome};")

    puml_lines.append("")
    puml_lines.append("stop")
    puml_lines.append("@enduml")

    puml_content = "\n".join(puml_lines)

    # Сохраняем оба файла
    safe_id = bp_id.lower().replace("-", "_")
    safe_title = title.lower().replace(" ", "_")[:30]

    md_filename = f"{safe_id}_{safe_title}.md"
    puml_filename = f"{safe_id}_{safe_title}.puml"

    md_path = _save_spec(md_content, project_id, md_filename)
    puml_path = _save_spec(puml_content, project_id, puml_filename)

    # ADR-022: авторегистрация в 5.1
    reg_note = _register_in_repo(project_id, bp_id, "business_process", title, md_path, priority)

    result = (
        md_content
        + f"\n\n---\n\n## PlantUML Activity Diagram\n\n```plantuml\n{puml_content}\n```"
        + f"\n\n---\n\n**Регистрация в 5.1:** {reg_note}"
        + f"\n**Файлы:** `{md_path}`, `{puml_path}`"
    )

    return result


# ---------------------------------------------------------------------------
# 7.1.7 — Data Dictionary
# ---------------------------------------------------------------------------

@mcp.tool()
def create_data_dictionary(
    project_id: str,
    dd_id: str,
    title: str,
    entities_json: str,
    source_artifact: str = "",
) -> str:
    """
    BABOK 7.1 — Создаёт Data Dictionary: реестр сущностей с атрибутами, типами и ограничениями.
    Автоматически регистрирует в репозитории 5.1 (статус draft). ADR-022.

    Args:
        project_id:      Идентификатор проекта.
        dd_id:           ID артефакта: DD-001.
        title:           Название: «Сущности заявочной системы».
        entities_json:   JSON-список сущностей. Формат:
                         [
                           {
                             "name": "Application",
                             "description": "Заявка на кредит",
                             "attributes": [
                               {
                                 "name": "id",
                                 "type": "Integer",
                                 "required": true,
                                 "constraints": "PK, AUTO_INCREMENT",
                                 "description": "Уникальный идентификатор"
                               }
                             ],
                             "business_rules": ["Правило 1", "Правило 2"]
                           }
                         ]
        source_artifact: Путь к артефакту 4.3.

    Returns:
        Markdown Data Dictionary + подтверждение регистрации в 5.1.
    """
    logger.info(f"create_data_dictionary: {dd_id} в проекте '{project_id}'")

    try:
        entities = json.loads(entities_json)
        if not isinstance(entities, list) or len(entities) == 0:
            raise ValueError("Должен быть непустой список")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Ошибка парсинга entities_json: {e}\n"
            f"Ожидается JSON-список сущностей. Пример в references/templates.md."
        )

    lines = [
        f"<!-- BABOK 7.1 — Data Dictionary | Проект: {project_id} | {date.today()} -->",
        "",
        f"# {dd_id} — {title}",
        "",
        "| Атрибут | Значение |",
        "|---------|----------|",
        f"| Тип | Data Dictionary |",
        f"| Проект | {project_id} |",
        f"| Источник | {source_artifact or '—'} |",
        f"| Сущностей | {len(entities)} |",
        f"| Статус | draft |",
        f"| Версия | 1.0 |",
        f"| Дата | {date.today()} |",
        "",
        "---",
    ]

    for entity in entities:
        name = entity.get("name", "Unnamed")
        description = entity.get("description", "")
        attributes = entity.get("attributes", [])
        rules = entity.get("business_rules", [])

        lines += [
            "",
            f"## Сущность: {name}",
            "",
        ]

        if description:
            lines += [f"**Описание:** {description}", ""]

        if attributes:
            lines += [
                "| Атрибут | Тип данных | Обязательный | Ограничения | Описание |",
                "|---------|-----------|--------------|-------------|----------|",
            ]
            for attr in attributes:
                attr_name = attr.get("name", "—")
                attr_type = attr.get("type", "—")
                required = "Да" if attr.get("required", False) else "Нет"
                constraints = attr.get("constraints", "—")
                attr_desc = attr.get("description", "—")
                lines.append(f"| `{attr_name}` | {attr_type} | {required} | {constraints} | {attr_desc} |")
        else:
            lines.append("_Атрибуты не заданы._")

        if rules:
            lines += ["", "**Бизнес-правила:**"]
            for rule in rules:
                lines.append(f"- {rule}")

        lines.append("")

    lines += [
        "---",
        "",
        "## Трассировка",
        "",
        "| Связь | Артефакт |",
        "|-------|----------|",
        f"| Источник (4.3) | {source_artifact or '—'} |",
        f"| Реестр (5.1) | регистрация автоматическая |",
    ]

    content = "\n".join(lines)

    safe_id = dd_id.lower().replace("-", "_")
    safe_title = title.lower().replace(" ", "_")[:30]
    filename = f"{safe_id}_{safe_title}.md"
    spec_path = _save_spec(content, project_id, filename)

    reg_note = _register_in_repo(project_id, dd_id, "data_dictionary", title, spec_path)

    return content + f"\n\n---\n\n**Регистрация в 5.1:** {reg_note}\n**Файл:** `{spec_path}`"


# ---------------------------------------------------------------------------
# 7.1.8 — ERD (.md + .puml)
# ---------------------------------------------------------------------------

@mcp.tool()
def create_erd(
    project_id: str,
    erd_id: str,
    title: str,
    entities_json: str,
    relations_json: str,
    source_artifact: str = "",
) -> str:
    """
    BABOK 7.1 — Создаёт описание сущностей и связей + PlantUML ER Diagram (.puml).
    ADR-025: PlantUML нотация.
    Автоматически регистрирует в репозитории 5.1 (статус draft). ADR-022.

    Args:
        project_id:      Идентификатор проекта.
        erd_id:          ID артефакта: ERD-001.
        title:           Название: «Основные сущности CRM».
        entities_json:   JSON-список сущностей. Формат:
                         [
                           {
                             "name": "Application",
                             "pk": "id",
                             "attributes": ["client_id FK", "status Enum", "created_at DateTime"]
                           }
                         ]
        relations_json:  JSON-список связей. Формат:
                         [
                           {
                             "from": "Application",
                             "to": "Client",
                             "cardinality": "many-to-one",
                             "label": "belongs to"
                           }
                         ]
                         Допустимые cardinality:
                         one-to-one | one-to-many | many-to-one | many-to-many |
                         zero-or-one-to-many | zero-or-one-to-one
        source_artifact: Путь к артефакту 4.3.

    Returns:
        Markdown ERD описание + PlantUML код + подтверждение регистрации в 5.1.
    """
    logger.info(f"create_erd: {erd_id} в проекте '{project_id}'")

    try:
        entities = json.loads(entities_json)
        if not isinstance(entities, list) or len(entities) == 0:
            raise ValueError("Должен быть непустой список")
    except (json.JSONDecodeError, ValueError) as e:
        return f"❌ Ошибка парсинга entities_json: {e}"

    try:
        relations = json.loads(relations_json)
        if not isinstance(relations, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        relations = []

    # Нотация кардинальности PlantUML
    cardinality_map = {
        "one-to-one": "||--||",
        "one-to-many": "||--o{",
        "many-to-one": "}o--||",
        "many-to-many": "}o--o{",
        "zero-or-one-to-many": "|o--o{",
        "zero-or-one-to-one": "|o--o|",
    }

    # --- PlantUML ERD ---
    puml_name = f"{erd_id.lower().replace('-', '_')}_{title.lower().replace(' ', '_')[:20]}"
    puml_lines = [
        f"@startuml {puml_name}",
        "hide methods",
        "hide stereotypes",
        "",
        "skinparam classBackgroundColor #FAFAFA",
        "skinparam classBorderColor #AAAAAA",
        "skinparam backgroundColor #FFFFFF",
        "",
        f'title ERD — {title}',
        "",
    ]

    for entity in entities:
        name = entity.get("name", "Entity")
        pk = entity.get("pk", "id")
        attrs = entity.get("attributes", [])

        puml_lines += [
            f'entity "{name}" as {name} {{',
            f"  + {pk} : Integer [PK]",
            "  --",
        ]
        for attr in attrs:
            puml_lines.append(f"  {attr}")
        puml_lines.append("}")
        puml_lines.append("")

    for rel in relations:
        from_e = rel.get("from", "")
        to_e = rel.get("to", "")
        card = rel.get("cardinality", "one-to-many")
        label = rel.get("label", "")
        notation = cardinality_map.get(card, "||--o{")

        if label:
            puml_lines.append(f'{from_e} {notation} {to_e} : "{label}"')
        else:
            puml_lines.append(f"{from_e} {notation} {to_e}")

    puml_lines.append("")
    puml_lines.append("@enduml")
    puml_content = "\n".join(puml_lines)

    # --- Markdown описание ---
    md_lines = [
        f"<!-- BABOK 7.1 — ERD | Проект: {project_id} | {date.today()} -->",
        "",
        f"# {erd_id} — {title}",
        "",
        "| Атрибут | Значение |",
        "|---------|----------|",
        f"| Тип | ERD |",
        f"| Проект | {project_id} |",
        f"| Источник | {source_artifact or '—'} |",
        f"| Сущностей | {len(entities)} |",
        f"| Связей | {len(relations)} |",
        f"| Статус | draft |",
        f"| Версия | 1.0 |",
        f"| Дата | {date.today()} |",
        "",
        "---",
        "",
        "## Сущности",
        "",
        "| Сущность | PK | Атрибуты |",
        "|----------|----|----------|",
    ]

    for entity in entities:
        name = entity.get("name", "—")
        pk = entity.get("pk", "id")
        attrs = ", ".join(entity.get("attributes", []))
        md_lines.append(f"| **{name}** | `{pk}` | {attrs or '—'} |")

    if relations:
        md_lines += [
            "",
            "## Связи",
            "",
            "| От | К | Кардинальность | Описание |",
            "|----|---|----------------|----------|",
        ]
        for rel in relations:
            md_lines.append(
                f"| `{rel.get('from', '—')}` | `{rel.get('to', '—')}` | "
                f"{rel.get('cardinality', '—')} | {rel.get('label', '—')} |"
            )

    md_lines += [
        "",
        "---",
        "",
        "## Трассировка",
        "",
        "| Связь | Артефакт |",
        "|-------|----------|",
        f"| Источник (4.3) | {source_artifact or '—'} |",
        f"| Реестр (5.1) | регистрация автоматическая |",
    ]

    md_content = "\n".join(md_lines)

    # Сохраняем оба файла
    safe_id = erd_id.lower().replace("-", "_")
    safe_title = title.lower().replace(" ", "_")[:30]

    md_filename = f"{safe_id}_{safe_title}.md"
    puml_filename = f"{safe_id}_{safe_title}.puml"

    md_path = _save_spec(md_content, project_id, md_filename)
    puml_path = _save_spec(puml_content, project_id, puml_filename)

    reg_note = _register_in_repo(project_id, erd_id, "erd", title, md_path)

    result = (
        md_content
        + f"\n\n---\n\n## PlantUML ER Diagram\n\n```plantuml\n{puml_content}\n```"
        + f"\n\n---\n\n**Регистрация в 5.1:** {reg_note}"
        + f"\n**Файлы:** `{md_path}`, `{puml_path}`"
    )
    return result


# ---------------------------------------------------------------------------
# 7.1.9 — Coverage Matrix
# ---------------------------------------------------------------------------

@mcp.tool()
def build_coverage_matrix(
    project_id: str,
) -> str:
    """
    BABOK 7.1 — Строит матрицу покрытия «бизнес-цель → требования».

    Читает бизнес-цели из последнего артефакта 4.3 и список требований из репозитория 5.1.
    Флаги:
      🔴 Бизнес-цель не покрыта ни одним требованием
      🟡 Бизнес-цель покрыта 10+ требованиями (возможный over-engineering)
      🟢 Нормальное покрытие (1–9 требований)

    Args:
        project_id: Идентификатор проекта.

    Returns:
        Markdown Coverage Matrix с флагами и рекомендациями.
    """
    logger.info(f"build_coverage_matrix: '{project_id}'")

    repo = _load_repo(project_id)
    requirements = [
        r for r in repo["requirements"]
        if r.get("status") not in {"deprecated", "superseded", "retired"}
    ]

    if not requirements:
        return (
            f"⚠️ В репозитории проекта `{project_id}` нет требований.\n"
            f"Сначала создай требования с помощью инструментов 7.1."
        )

    # Пробуем найти артефакт 4.3 для извлечения бизнес-целей
    artifact_path = _find_confirmed_artifact(project_id)
    business_goals = []
    source_info = ""

    if artifact_path:
        try:
            content = _read_confirmed_artifact(artifact_path)
            source_info = f"📂 Бизнес-цели извлечены из: `{artifact_path}`"
            # Простой парсинг: ищем раздел с бизнес-целями
            lines = content.split("\n")
            in_goals_section = False
            for line in lines:
                line_stripped = line.strip()
                lower = line_stripped.lower()
                if any(kw in lower for kw in ["бизнес-цел", "business goal", "цели проекта", "цели:"]):
                    in_goals_section = True
                    continue
                if in_goals_section:
                    if line_stripped.startswith("#"):
                        in_goals_section = False
                        continue
                    if line_stripped.startswith("-") or (
                        line_stripped and line_stripped[0].isdigit() and ". " in line_stripped
                    ):
                        goal = line_stripped.lstrip("-•*0123456789. ").strip()
                        if len(goal) > 5:
                            business_goals.append(goal)
        except IOError:
            pass

    if not business_goals:
        # Fallback: синтетические "цели" из source_artifact требований
        source_artifacts = set()
        for r in requirements:
            sa = r.get("source_artifact", "")
            if sa:
                source_artifacts.add(sa)

        if source_artifacts:
            business_goals = [f"Цели из: {sa}" for sa in sorted(source_artifacts)]
            source_info = "📋 Бизнес-цели не извлечены из 4.3. Показана группировка по источникам."
        else:
            business_goals = ["Бизнес-цели не определены"]
            source_info = "⚠️ Артефакт 4.3 не найден. Запусти `analyze_elicitation_context` для анализа."

    # Строим матрицу
    # Для реальной трассировки используем source_artifact как связь
    goal_coverage = {}
    for goal in business_goals:
        goal_coverage[goal] = []

    for req in requirements:
        req_source = req.get("source_artifact", "")
        # Привязываем к цели по source_artifact или ко всем целям если один источник
        matched = False
        for goal in business_goals:
            if req_source and (req_source in goal or goal in req_source):
                goal_coverage[goal].append(req)
                matched = True
        if not matched and business_goals:
            goal_coverage[business_goals[0]].append(req)

    # Статистика
    uncovered = [g for g, reqs in goal_coverage.items() if len(reqs) == 0]
    over_engineered = [g for g, reqs in goal_coverage.items() if len(reqs) >= 10]
    normal = [g for g, reqs in goal_coverage.items() if 1 <= len(reqs) < 10]

    total_reqs = len(requirements)
    covered_reqs = sum(len(r) for r in goal_coverage.values())

    lines = [
        f"<!-- BABOK 7.1 — Coverage Matrix | Проект: {project_id} | {date.today()} -->",
        "",
        f"# 📊 Матрица покрытия требований",
        "",
        f"**Проект:** {project_id}  ",
        f"**Дата:** {date.today()}  ",
        f"**Источник целей:** {source_info}",
        "",
        "## Сводка",
        "",
        "| Показатель | Значение |",
        "|------------|----------|",
        f"| Бизнес-целей | {len(business_goals)} |",
        f"| Требований в реестре | {total_reqs} |",
        f"| 🔴 Целей без покрытия | {len(uncovered)} |",
        f"| 🟡 Целей с 10+ требованиями | {len(over_engineered)} |",
        f"| 🟢 Целей с нормальным покрытием | {len(normal)} |",
        "",
    ]

    if uncovered:
        lines += [
            "## 🔴 Не покрытые бизнес-цели",
            "",
            "> Для каждой цели необходимо создать хотя бы одно требование.",
            "",
        ]
        for goal in uncovered:
            lines.append(f"- **{goal}**")
        lines.append("")

    if over_engineered:
        lines += [
            "## 🟡 Возможный over-engineering",
            "",
            "> 10+ требований на одну цель — стоит проверить, не дублируются ли требования.",
            "",
        ]
        for goal in over_engineered:
            req_ids = [r["id"] for r in goal_coverage[goal]]
            lines.append(f"- **{goal}** ({len(req_ids)} требований): {', '.join(f'`{i}`' for i in req_ids[:5])}{'...' if len(req_ids) > 5 else ''}")
        lines.append("")

    lines += [
        "## Полная матрица",
        "",
        "| Бизнес-цель | Требования | Покрытие |",
        "|-------------|-----------|---------|",
    ]

    for goal in business_goals:
        reqs = goal_coverage[goal]
        req_ids = [r["id"] for r in reqs]
        count = len(req_ids)
        if count == 0:
            icon = "🔴"
        elif count >= 10:
            icon = "🟡"
        else:
            icon = "🟢"
        ids_str = ", ".join(f"`{i}`" for i in req_ids[:5])
        if len(req_ids) > 5:
            ids_str += f"... (+{len(req_ids) - 5})"
        goal_short = goal[:50] + "..." if len(goal) > 50 else goal
        lines.append(f"| {goal_short} | {ids_str or '—'} | {icon} {count} req |")

    lines += [
        "",
        "---",
        "",
        "## Рекомендации",
        "",
    ]

    if uncovered:
        lines.append(
            f"1. 🔴 **{len(uncovered)} целей без покрытия** — создай требования через инструменты 7.1."
        )
    if over_engineered:
        lines.append(
            f"2. 🟡 **{len(over_engineered)} целей с избыточным покрытием** — "
            f"проверь на дублирование через `check_coverage` (5.1)."
        )
    if not uncovered and not over_engineered:
        lines.append("✅ Все бизнес-цели покрыты. Готово к верификации (7.2) и валидации (7.3).")
    else:
        lines.append(
            f"\n**Следующий шаг:** после устранения пробелов — запусти верификацию (7.2)."
        )

    content = "\n".join(lines)
    save_artifact(content, prefix="7_1_coverage_matrix")
    return content


if __name__ == "__main__":
    mcp.run()
