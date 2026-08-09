"""
BABOK 7.1 — Specify and Model Requirements
MCP tools for formalizing requirements from elicitation results.

Tools:
  - analyze_elicitation_context  — analyzes 4.3 artifacts, list of candidate requirements
  - create_user_story            — User Story with AC, auto-registration in 5.1
  - create_functional_requirement — SRS-style (functional/non_functional/business_rule), auto-registration in 5.1
  - create_use_case              — textual UC specification, auto-registration in 5.1
  - generate_use_case_diagram    — PlantUML Use Case Diagram for all project UCs
  - create_business_process      — text + PlantUML Activity Diagram, auto-registration in 5.1
  - create_data_dictionary       — registry of entities and attributes, auto-registration in 5.1
  - create_erd                   — description of relationships + PlantUML ER Diagram, auto-registration in 5.1
  - build_coverage_matrix        — "business objective -> requirements" matrix with coverage flags

every creating tool registers the req in 5.1 automatically (status draft)
analyze_elicitation_context — hybrid reading (4.3 file -> fallback to context_text)
create_business_process generates .md + .puml
PlantUML for all diagrams

Artifact storage: governance_plans/{project_id}_specs/

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
import glob
from datetime import date
from typing import Optional
from mcp.server.fastmcp import FastMCP
from skills.common import (write_json_artifact,
    save_artifact, logger, DATA_DIR, data_path, normalize_project_id, specs_dir,
    parse_json_str_list, BUSINESS_NODE_TYPES, SOLUTION_SCOPE_NODE_TYPE,
    read_json_artifact, guard_artifact_errors, is_archived, archived_suffix,
    safe_filename_part, CorruptArtifactError, list_with_cap,
)

from skills.plural_ru import plural_ru

mcp = FastMCP("BABOK_Requirements_Spec")

REPO_FILENAME = "traceability_repo.json"
CONFIRMED_GLOB = "4_3_*_confirmed*.md"

# Nodes in the 5.1 graph that are NOT specification requirements, so they must not be
# counted in the coverage matrix nor reported as "unlinked to an objective". Beyond the
# business roots these are the nodes other chapters push into the SAME graph: `test`
# (5.1), `change_request` (5.4) and `risk` (6.3, ADR-074).
# Found by E2E: a CR opened in 5.4 was being counted as an uncovered requirement here.
# Same class as findings 7.3-A / 7.4-C — a skip-filter that knows only part of the set.
#
# `solution` stays a REQUIREMENT here: it is the BABOK requirement CLASS in the 5.1
# vocabulary (business | stakeholder | solution | transition), which is how
# `init_traceability_repo` and the Confluence import label ordinary FR/NFR. 6.4's scope
# node used to share that literal, which is why it could not be skipped; it now types
# itself `solution_scope` (ADR-082, revised), so the scope node is excluded and real
# requirements are not.
NON_SPEC_NODE_TYPES = BUSINESS_NODE_TYPES | {
    "test", "change_request", "risk", SOLUTION_SCOPE_NODE_TYPE,
}


# ---------------------------------------------------------------------------
# Утилиты — репозиторий 5.1
# ---------------------------------------------------------------------------

def _repo_path(project_id: str) -> str:
    safe = normalize_project_id(project_id)
    return data_path(project_id, f"{safe}_{REPO_FILENAME}")


def _load_repo(project_id: str) -> dict:
    path = _repo_path(project_id)
    if os.path.exists(path):
        # Raises CorruptArtifactError, converted to a ❌ line by guard_artifact_errors
        # at the tool boundary. A bare json.load here made a damaged file a protocol
        # error in every downstream tool.
        return read_json_artifact(path, "5.1 traceability repository")
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
    os.makedirs(os.path.dirname(path), exist_ok=True)
    repo["updated"] = str(date.today())
    write_json_artifact(path, repo)
    logger.info(f"Repository 5.1 updated (7.1): {path}")


def _register_in_repo(project_id: str, req_id: str, req_type: str,
                      title: str, source_artifact: str, priority: str = "Medium",
                      business_goal_ids: Optional[list] = None,
                      owner: str = "") -> str:
    """
    registers a requirement in repository 5.1 with status draft.
    If a requirement with this ID already exists — skips the node (without an error).

    A1: also writes the BA-declared `satisfies` edges requirement -> business objective
    (from=requirement to=objective). These edges are what makes per-goal coverage
    in `build_coverage_matrix` a real claim instead of a project-level average, and they
    are what `check_coverage` (5.1) and CR impact analysis (5.4) read.

    Node registration and edge registration are INDEPENDENT on purpose: registration
    returns early for an already-known id, so an existing requirement must still receive
    newly declared links — otherwise a re-run meant to add the objective silently does
    nothing.

    Returns a marker string to include in the artifact.
    """
    repo = _load_repo(project_id)
    # `_load_repo` returns a stored file as-is, so a legacy or partial repo may be missing
    # keys the default skeleton has. Writing edges made `links` a hard dependency here for
    # the first time; an absent key would raise instead of returning a readable message
    # (the CH3-A / CH4-A class). `history` is hardened alongside it — same one-line risk.
    repo.setdefault("requirements", [])
    repo.setdefault("links", [])
    repo.setdefault("history", [])

    existing_ids = {r["id"] for r in repo["requirements"]}
    notes = []

    if req_id in existing_ids:
        logger.info(f"_register_in_repo: {req_id} already in repository, skipping node")
        # The node stays, but what THIS specification states must not vanish into it.
        #
        # The documented order is 5.1 first (ids, types, titles), then 7.1 for each
        # specification — and 7.1 is where the analyst names the owner. Returning early
        # dropped that name, so `owner` stayed empty on the node: 7.4 reads it as
        # EVIDENCE of representation and turned the named person into a critical gap in
        # a signed document, the 5.5 package printed a blank owner, and the 5.2 audit
        # called the attribute unfilled. Found by a pre-release live run (E2-1).
        #
        # INSERT-ONLY, the same rule the 3.2 registry seeding follows: a value already
        # on the node was put there by another chapter, and a specification re-run must
        # not silently replace it. Only what is absent or empty is filled.
        node = next(r for r in repo["requirements"] if r.get("id") == req_id)
        filled = []
        for field, value in (("owner", owner), ("priority", priority),
                             ("source_artifact", source_artifact)):
            if value and not node.get(field):
                node[field] = value
                filled.append(field)
        if filled:
            notes.append(
                f"ℹ️ `{req_id}` уже зарегистрировано в репозитории 5.1 — из этой "
                f"спецификации заполнено: {', '.join(filled)}.")
        else:
            notes.append(f"ℹ️ `{req_id}` уже зарегистрировано в репозитории 5.1.")
    else:
        repo["requirements"].append({
            "id": req_id,
            "type": req_type,
            "title": title,
            "version": "1.0",
            "status": "draft",
            "priority": priority,
            # The creating call's owner used to be dropped here (hard-coded ""),
            # so the approval package and every owner-reading consumer showed a
            # blank owner for requirements whose author had named one.
            "owner": owner,
            "stability": "Unknown",
            "source_artifact": source_artifact,
            "added": str(date.today()),
            "last_reviewed": str(date.today()),
        })
        repo["history"].append({
            "action": "requirement_added",
            "req_id": req_id,
            "source": "7.1_spec",
            "date": str(date.today()),
        })
        notes.append(f"✅ `{req_id}` зарегистрировано в репозитории 5.1 (статус: draft).")

    nodes_by_id = {r["id"]: r for r in repo["requirements"]}
    # Idempotency on EDGES, not just on nodes — the bug that recurred in 6.3 and 6.4.
    existing_edges = {
        (lnk.get("from"), lnk.get("to"), lnk.get("relation")) for lnk in repo["links"]
    }
    added = 0

    for goal_id in (business_goal_ids or []):
        target = nodes_by_id.get(goal_id)
        if target is None:
            # Never invent the node: a phantom objective would poison check_coverage,
            # the 7.3 BFS, the 7.4 matrix and 5.4 impact analysis. Warn, don't block.
            notes.append(
                f"⚠️ Цели `{goal_id}` нет в репозитории 5.1 — связь пропущена. "
                f"Задайте цели в 6.2 (`define_goals_and_objectives`)."
            )
            continue
        if target.get("type") not in BUSINESS_NODE_TYPES:
            notes.append(
                f"⚠️ `{goal_id}` — узел типа `{target.get('type')}`, а не бизнес-цель: "
                f"связь пропущена. Для отношений между требованиями используйте "
                f"`add_trace_link` (5.1)."
            )
            continue
        key = (req_id, goal_id, "satisfies")
        if key in existing_edges:
            continue
        repo["links"].append({
            "from": req_id,
            "to": goal_id,
            "relation": "satisfies",
            # `rationale` is REQUIRED at Full formality and the matrix renders it, so
            # omitting it put a dash in the column a regulated project exists to fill.
            # `added` is the spelling every other producer uses; `created` was read by
            # nobody.
            "rationale": f"Требование {req_id} служит цели {goal_id}",
            "added": str(date.today()),
        })
        existing_edges.add(key)
        added += 1

    if added:
        notes.append(
            f"🔗 Связано с бизнес-целями через `satisfies`: {added} "
            f"{plural_ru(added, 'цель', 'цели', 'целей')}.")

    _save_repo(repo)
    return " ".join(notes)


# ---------------------------------------------------------------------------
# Утилиты — файловая система
# ---------------------------------------------------------------------------

def _specs_dir(project_id: str) -> str:
    # issue #1: спеки в data/<project>/specs/, с fallback на legacy-раскладки.
    # Единый источник истины — common.specs_dir.
    return specs_dir(project_id)


def _save_spec(content: str, project_id: str, filename: str) -> str:
    """Saves a specification to data/<project_id>/specs/. Returns the path.

    The guard lives HERE, in the one writer, rather than in each of the six producers
    that build a filename. Every producer composes the name out of the requirement id
    and its TITLE — free text, written by an LLM from the analyst's dictation — and none
    of them called the shared sanitiser: `title="../../../escaped"` put the file two
    levels above specs/, answered with the full document and no warning, and left the
    graph node's `source_artifact` pointing at a path that does not exist.

    Two layers, deliberately. `safe_filename_part` removes the separators; the
    containment check then refuses anything that still resolves outside the directory,
    so a future producer that formats its own name cannot reopen this.
    """
    target_dir = _specs_dir(project_id)
    os.makedirs(target_dir, exist_ok=True)
    filepath = os.path.join(target_dir, safe_filename_part(filename))

    real_dir = os.path.realpath(target_dir)
    real_path = os.path.realpath(filepath)
    if os.path.commonpath([real_path, real_dir]) != real_dir:
        raise CorruptArtifactError(
            f"❌ Имя файла спецификации уводит за пределы папки specs этого проекта: "
            f"`{filename}`.\n"
            f"   Ничего не записано. Переименуйте требование так, чтобы его заголовок "
            f"не читался как путь."
        )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"Спецификация сохранена: {filepath}")
    return filepath


def _confirmed_artifact_pattern(project_id: str) -> str:
    """The ONE glob the 4.3 lookup runs — and the one its "not found" message quotes.

    They used to be two independent strings, and the wave that removed the flat
    fallbacks updated only the search: the message went on naming
    `governance_plans/4_3_<project_id>_confirmed*.md`, a shape nothing looks at, so an
    analyst who followed it put the file where the tool would never find it. A
    statement about where the tool searched has to be derived from where it searched.
    """
    from skills.common import report_dir_for
    return os.path.join(report_dir_for(project_id), "4_3_*confirmed*.md")


def _find_confirmed_artifact(project_id: str):
    """Finds the latest confirmed 4.3 artifact for project_id, or None.

    The 4.3 producer (save_confirmed_elicitation_result -> save_artifact) writes the report to
      reports/<project_id>/4_3_confirmed_result_<timestamp>.md
    i.e. project_id is the FOLDER name, and the filename itself does NOT contain project_id.
    An earlier implementation searched only flat data/ with masks that REQUIRED project_id
    inside the filename, so it never matched the real artifact (audit finding 7.1-A).

    ONE pattern, and the project folder is what scopes it. The flat fallbacks that used
    to follow it could not filter by project at all — a flat artifact carries the
    project id neither in its name nor in its folder — so they could hand THIS project
    the elicitation results of another one, and requirements derived from another
    project's interviews look perfectly ordinary. They warned about themselves, which
    is why the caller used to receive a `project_scoped` flag. Both went with the legacy
    layout (owner's decision, 2026-08-03).
    """
    matches = glob.glob(_confirmed_artifact_pattern(project_id))
    if not matches:
        return None
    # latest by modification time (filenames carry a timestamp, but mtime is robust)
    return max(matches, key=os.path.getmtime)


def _read_confirmed_artifact(path: str) -> str:
    """Читает содержимое артефакта 4.3."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _load_future_state_goals(project_id: str) -> list:
    """Reads the 6.2 business objectives from future_state_goals.json (audit finding 7.1-C).

    6.2 (Define Future State) is the real source of business objectives, not the 4.3 confirmed
    artifact. Returns a list of goal_title strings (empty if the 6.2 file is absent/unreadable).
    Contract matches the 6.2 producer: key 'goals', field 'goal_title'.
    """
    safe = normalize_project_id(project_id)
    path = data_path(project_id, f"{safe}_future_state_goals.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [
                g.get("goal_title", "").strip()
                for g in data.get("goals", [])
                if g.get("goal_title", "").strip()
            ]
        except (IOError, json.JSONDecodeError, TypeError):
            pass
    return []


# ---------------------------------------------------------------------------
# 7.1.1 — Анализ контекста выявления (ADR-023)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def analyze_elicitation_context(
    project_id: str,
    context_text: str = "",
) -> str:
    """
    BABOK 7.1 — Анализирует подтверждённые результаты выявления (4.3) и предлагает
    список требований-кандидатов с классификацией по типу и рекомендуемым ID-префиксом.

    Hybrid reading:
      1. Tries to find the 4.3 file by project_id in governance_plans/
      2. If not found and context_text is empty — returns instructions
      3. If not found but context_text is provided — uses the supplied text

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
            f"⚠️ Артефакт 4.3 для проекта `{project_id}` не найден.\n\n"
            f"Инструмент искал файлы по шаблону:\n"
            f"`{_confirmed_artifact_pattern(project_id)}`\n\n"
            f"(id проекта — это ПАПКА; в имени файла его нет)\n\n"
            f"**Варианты:**\n"
            f"1. Убедитесь, что артефакт 4.3 создан через `save_confirmed_elicitation_result` (4.3)\n"
            f"2. Передайте содержимое вручную: `analyze_elicitation_context("
            f"project_id='{project_id}', context_text='[вставьте текст артефакта 4.3]')`"
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
    save_artifact(result, prefix="7_1_context_analysis", project_id=project_id)
    return result


# ---------------------------------------------------------------------------
# 7.1.2 — User Story
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
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
    business_goal_ids_json: str = "[]",
) -> str:
    """
    BABOK 7.1 — Creates a User Story with Acceptance Criteria.
    Automatically registers it in repository 5.1 (status draft).

    Args:
        project_id:                Project identifier.
        story_id:                  Story ID: US-001, US-002, etc.
        title:                     Short title (for the heading and the 5.1 registry).
        role:                      User role: "Application Manager", "Customer", "Administrator".
        action:                    What the user wants to do (without "I want").
        benefit:                   Business value (without "so that").
        acceptance_criteria_json:  JSON list of acceptance criteria: ["Criterion 1", "Criterion 2"]
                                   At least 2 criteria.
        priority:                  High | Medium | Low. Default Medium.
        source_artifact:           Path to the 4.3 artifact (for traceability).
        notes:                     Additional context, constraints, references.
        business_goal_ids_json:  JSON list of 6.2 business objective IDs this item serves:
                                 ["BG-001", "BG-002"]. Writes `satisfies` links into the
                                 5.1 graph — that is what makes per-objective coverage in
                                 `build_coverage_matrix` precise. Empty — no links.

    Returns:
        Markdown-артефакт User Story + подтверждение регистрации в 5.1.
    """
    logger.info(f"create_user_story: {story_id} в проекте '{project_id}'")

    # Parsed BEFORE the artifact is written, so a rejected call leaves no orphan file.
    goal_ids, goal_err = parse_json_str_list(
        business_goal_ids_json, "business_goal_ids_json", example='["BG-001"]')
    if goal_err:
        return goal_err

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

    # ADR-022: auto-registration in 5.1
    reg_note = _register_in_repo(project_id, story_id, "user_story", title, spec_path, priority, goal_ids)

    return content + f"\n\n---\n\n**Регистрация в 5.1:** {reg_note}\n**Файл:** `{spec_path}`"


# ---------------------------------------------------------------------------
# 7.1.3 — Functional Requirement
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
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
    business_goal_ids_json: str = "[]",
) -> str:
    """
    BABOK 7.1 — Creates a formal SRS-style requirement.
    Automatically registers it in repository 5.1 (status draft).

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
        owner:             Owner/stakeholder responsible for the requirement.
        source_artifact:   Path to the 4.3 artifact.
        constraints:       Constraints and assumptions.
        related_ids_json:  JSON list of related IDs: ["BR-001", "UC-001"]
        business_goal_ids_json:  JSON list of 6.2 business objective IDs this item serves:
                                 ["BG-001", "BG-002"]. Writes `satisfies` links into the
                                 5.1 graph — that is what makes per-objective coverage in
                                 `build_coverage_matrix` precise. Empty — no links.

    Returns:
        Markdown-артефакт требования + подтверждение регистрации в 5.1.
    """
    logger.info(f"create_functional_requirement: {req_id} ({req_type}) в проекте '{project_id}'")

    # Parsed BEFORE the artifact is written, so a rejected call leaves no orphan file.
    goal_ids, goal_err = parse_json_str_list(
        business_goal_ids_json, "business_goal_ids_json", example='["BG-001"]')
    if goal_err:
        return goal_err

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
    reg_note = _register_in_repo(project_id, req_id, repo_type_map[req_type], title, spec_path, priority, goal_ids, owner=owner)

    return content + f"\n\n---\n\n**Регистрация в 5.1:** {reg_note}\n**Файл:** `{spec_path}`"


# ---------------------------------------------------------------------------
# 7.1.4 — Use Case
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
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
    business_goal_ids_json: str = "[]",
) -> str:
    """
    BABOK 7.1 — Creates a textual Use Case specification.
    Automatically registers it in repository 5.1 (status draft).

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
        secondary_actors:  Secondary actors, comma-separated.
        alt_scenarios:     Alternative scenarios (numbering: 2a, 3b...).
        exc_scenarios:     Exception scenarios (numbering: Xa, Yb...).
        business_rules:    Business rules applied in the UC.
        source_artifact:   Path to the 4.3 artifact.
        business_goal_ids_json: JSON list of 6.2 business objective IDs this item serves:
                         ["BG-001", "BG-002"]. Writes `satisfies` links into the 5.1 graph —
                         that is what makes per-objective coverage in `build_coverage_matrix`
                         precise. Empty — no links.

    Returns:
        Markdown-артефакт Use Case + подтверждение регистрации в 5.1.
    """
    logger.info(f"create_use_case: {uc_id} в проекте '{project_id}'")

    # Parsed BEFORE the artifact is written, so a rejected call leaves no orphan file.
    goal_ids, goal_err = parse_json_str_list(
        business_goal_ids_json, "business_goal_ids_json", example='["BG-001"]')
    if goal_err:
        return goal_err

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

    reg_note = _register_in_repo(project_id, uc_id, "use_case", title, spec_path, priority, goal_ids)

    return content + f"\n\n---\n\n**Регистрация в 5.1:** {reg_note}\n**Файл:** `{spec_path}`"


# ---------------------------------------------------------------------------
# 7.1.5 — Use Case Diagram (PlantUML)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def generate_use_case_diagram(
    project_id: str,
    system_boundary: str,
    diagram_name: str = "",
) -> str:
    """
    BABOK 7.1 — Generates a PlantUML Use Case Diagram from all UCs in repository 5.1.
    PlantUML notation.

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
    save_artifact(result, prefix="7_1_uc_diagram", project_id=project_id)
    return result


# ---------------------------------------------------------------------------
# 7.1.6 — Business Process (ADR-024: .md + .puml)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
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
    business_goal_ids_json: str = "[]",
) -> str:
    """
    BABOK 7.1 — Creates a business process description.
    generates TWO files — a textual description .md and an Activity Diagram .puml.
    Automatically registers it in repository 5.1 (status draft).

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
        business_rules:  Business rules and constraints of the process.
        metrics:         Metrics: time, conversion, cost.
        exceptions:      Exceptional situations and error handling.
        source_artifact: Path to the 4.3 artifact.
        business_goal_ids_json: JSON list of 6.2 business objective IDs this item serves:
                         ["BG-001", "BG-002"]. Writes `satisfies` links into the 5.1 graph —
                         that is what makes per-objective coverage in `build_coverage_matrix`
                         precise. Empty — no links.

    Returns:
        Markdown-артефакт процесса + PlantUML Activity Diagram + подтверждение регистрации в 5.1.
    """
    logger.info(f"create_business_process: {bp_id} в проекте '{project_id}'")

    # Parsed BEFORE the artifacts are written, so a rejected call leaves no orphan files.
    goal_ids, goal_err = parse_json_str_list(
        business_goal_ids_json, "business_goal_ids_json", example='["BG-001"]')
    if goal_err:
        return goal_err

    # --- Textual description .md ---
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

    # ADR-022: auto-registration in 5.1
    reg_note = _register_in_repo(project_id, bp_id, "business_process", title, md_path, priority, goal_ids)

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
@guard_artifact_errors
def create_data_dictionary(
    project_id: str,
    dd_id: str,
    title: str,
    entities_json: str,
    source_artifact: str = "",
    business_goal_ids_json: str = "[]",
) -> str:
    """
    BABOK 7.1 — Creates a Data Dictionary: a registry of entities with attributes, types and constraints.
    Automatically registers it in repository 5.1 (status draft).

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
        source_artifact: Path to the 4.3 artifact.
        business_goal_ids_json: JSON list of 6.2 business objective IDs this item serves:
                         ["BG-001", "BG-002"]. Writes `satisfies` links into the 5.1 graph —
                         that is what makes per-objective coverage in `build_coverage_matrix`
                         precise. Empty — no links.

    Returns:
        Markdown Data Dictionary + подтверждение регистрации в 5.1.
    """
    logger.info(f"create_data_dictionary: {dd_id} в проекте '{project_id}'")

    # Parsed BEFORE the artifact is written, so a rejected call leaves no orphan file.
    goal_ids, goal_err = parse_json_str_list(
        business_goal_ids_json, "business_goal_ids_json", example='["BG-001"]')
    if goal_err:
        return goal_err

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

    reg_note = _register_in_repo(project_id, dd_id, "data_dictionary", title, spec_path, "Medium", goal_ids)

    return content + f"\n\n---\n\n**Регистрация в 5.1:** {reg_note}\n**Файл:** `{spec_path}`"


# ---------------------------------------------------------------------------
# 7.1.8 — ERD (.md + .puml)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def create_erd(
    project_id: str,
    erd_id: str,
    title: str,
    entities_json: str,
    relations_json: str,
    source_artifact: str = "",
    business_goal_ids_json: str = "[]",
) -> str:
    """
    BABOK 7.1 — Creates a description of entities and relationships + PlantUML ER Diagram (.puml).
    PlantUML notation.
    Automatically registers it in repository 5.1 (status draft).

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
        source_artifact: Path to the 4.3 artifact.
        business_goal_ids_json: JSON list of 6.2 business objective IDs this item serves:
                         ["BG-001", "BG-002"]. Writes `satisfies` links into the 5.1 graph —
                         that is what makes per-objective coverage in `build_coverage_matrix`
                         precise. Empty — no links.

    Returns:
        Markdown ERD описание + PlantUML код + подтверждение регистрации в 5.1.
    """
    logger.info(f"create_erd: {erd_id} в проекте '{project_id}'")

    # Parsed BEFORE the artifacts are written, so a rejected call leaves no orphan files.
    goal_ids, goal_err = parse_json_str_list(
        business_goal_ids_json, "business_goal_ids_json", example='["BG-001"]')
    if goal_err:
        return goal_err

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

    reg_note = _register_in_repo(project_id, erd_id, "erd", title, md_path, "Medium", goal_ids)

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
@guard_artifact_errors
def build_coverage_matrix(
    project_id: str,
) -> str:
    """
    BABOK 7.1 — Строит матрицу покрытия «бизнес-цель → требования».

    Business objectives come from 6.2 (Define Future State), in this order: the
    `business_goal` nodes 6.2 registers in the 5.1 graph, then `future_state_goals.json`,
    then a legacy hand-written "Business objectives" section in the 4.3 artifact, then
    grouping by source artifact. Requirements come from repository 5.1.

    Two modes, chosen by whether the objectives carry graph ids:

      PRECISE — objectives are `business_goal` nodes. Coverage is computed by traversing
        the `satisfies` links the BA declares (7.1 creating tools, or `add_trace_link` in
        5.1); `derives` links to an objective are counted too. The per-objective flags are
        real claims backed by edges.
      DEGRADED — objectives came from `future_state_goals.json`, a legacy 4.3 section, or
        grouping by source. That is text without ids, so no per-objective claim is made:
        the objectives are shown as a checklist and the report says so. A mapping is never
        inferred from text — doing that was audit finding 7.1-B.

    Flags (precise mode only):
      🔴 Business objective not covered by any requirement
      🟡 Business objective covered by 10+ requirements (possible over-engineering)
      🟢 Normal coverage (1–9 requirements)

    Args:
        project_id: Идентификатор проекта.

    Returns:
        Markdown Coverage Matrix с флагами и рекомендациями.
    """
    logger.info(f"build_coverage_matrix: '{project_id}'")

    repo = _load_repo(project_id)
    # Archived requirements are SHOWN, MARKED and COUNTED here; what they never do is
    # count as coverage of an objective (owner's decision, 2026-08-03 — see the doctrine
    # at common.ARCHIVED_REQUIREMENT_STATUSES). Dropping them from the selection made
    # this matrix and the 5.1 documents of the same project report different sizes for
    # the same graph.
    active = list(repo["requirements"])

    if not active:
        return (
            f"⚠️ В репозитории проекта `{project_id}` нет требований.\n"
            f"Сначала создай требования с помощью инструментов 7.1."
        )

    # Objectives are the 6.2 business_goal nodes; spec requirements are everything specifiable in
    # 7.1. Exclude the goal/need/business roots so they don't inflate the requirement count or
    # show up in the requirements list.
    goal_nodes = [r for r in active if r.get("type") == "business_goal"]
    requirements = [
        r for r in active
        if r.get("type") not in NON_SPEC_NODE_TYPES
    ]

    # C1 (audit finding 7.1-C): the REAL source of business objectives is 6.2 (Define Future
    # State), NOT the 4.3 confirmed artifact — which holds requirements/rules/issues, never a
    # business-objectives section. 6.2 registers each goal as a `business_goal` node in the 5.1
    # graph AND stores it in future_state_goals.json. Prefer the graph nodes (canonical, and what
    # a future per-goal traceability pass would traverse), then the 6.2 file, then a legacy
    # "Business objectives" section written into the 4.3 artifact by hand, then group-by-source.
    #
    # A1: when the objectives ARE graph nodes they carry an id, and the id is what makes
    # precise per-objective traversal possible. The other three sources yield text only —
    # there is no honest way to attach a requirement to a bare string, so the tool degrades
    # to the C1 checklist instead of guessing.
    business_goals = []
    goal_entries = []   # (goal_id, title); goal_id is "" in degraded mode
    precise = False
    source_info = ""

    if goal_nodes:
        goal_entries = [(g["id"], g.get("title") or g["id"]) for g in goal_nodes]
        business_goals = [t for _, t in goal_entries]
        precise = True
        source_info = "📂 Бизнес-цели — из целей 6.2, зарегистрированных в графе 5.1 (узлы business_goal)."

    if not business_goals:
        fs_goals = _load_future_state_goals(project_id)
        if fs_goals:
            business_goals = fs_goals
            source_info = "📂 Бизнес-цели — из `future_state_goals.json` (6.2)."

    if not business_goals:
        artifact_path = _find_confirmed_artifact(project_id)
        if artifact_path:
            try:
                content = _read_confirmed_artifact(artifact_path)
                source_info = f"📂 Бизнес-цели извлечены из артефакта 4.3: `{artifact_path}`"
                # Simple parsing: look for the section with business objectives
                in_goals_section = False
                for line in content.split("\n"):
                    line_stripped = line.strip()
                    lower = line_stripped.lower()
                    if any(kw in lower for kw in ["business objective", "business goal", "бизнес-цел", "цели проекта"]):
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
            source_info = "📋 Ни целей 6.2, ни целей из 4.3 не найдено. Показана группировка по источнику требований."
        else:
            business_goals = ["Бизнес-цели не заданы"]
            source_info = "⚠️ Бизнес-цели не найдены. Задайте их в 6.2 (`define_goals_and_objectives`) либо запустите `analyze_elicitation_context`."

    if not precise:
        goal_entries = [("", t) for t in business_goals]

    # A1 coverage. Per-objective claims are made ONLY from real edges in the 5.1 graph.
    # The original defect (finding 7.1-B) compared a file PATH (source_artifact) against
    # goal TEXT, so every requirement fell into the FIRST objective and all the others were
    # falsely flagged uncovered. Nothing here infers a mapping from text — an objective is
    # covered when a requirement points at its NODE, and not otherwise.
    total_reqs = len(requirements)
    num_goals = len(business_goals)
    avg_per_goal = total_reqs / max(1, num_goals)
    over_engineering = avg_per_goal >= 10  # global heuristic, kept for the degraded mode

    links = repo.get("links", [])
    req_ids = {r["id"] for r in requirements}
    # Read BOTH relations: A1 writes `satisfies` (ADR-082), but a BA may have linked
    # manually with `derives` via add_trace_link (5.1), and ignoring that encoding would
    # silently under-report coverage.
    goal_link_relations = ("satisfies", "derives")

    per_goal = {}              # goal_id -> [req_id, ...]
    linked_req_ids = set()     # requirements attached to a displayed objective
    need_only_req_ids = set()  # attached to a business_need/business root only

    if precise:
        goal_ids_set = {gid for gid, _ in goal_entries}
        need_ids = {
            r["id"] for r in active
            if r.get("type") in ("business_need", "business")
        }
        per_goal = {gid: [] for gid in goal_ids_set}
        archived_req_ids = {r["id"] for r in requirements if is_archived(r)}
        for lnk in links:
            if lnk.get("relation") not in goal_link_relations:
                continue
            frm, to = lnk.get("from"), lnk.get("to")
            if frm not in req_ids:
                continue
            # An archived requirement is not evidence that its objective is served: it
            # was withdrawn. It stays in the registry table below, marked.
            if frm in archived_req_ids:
                continue
            if to in goal_ids_set:
                if frm not in per_goal[to]:
                    per_goal[to].append(frm)
                linked_req_ids.add(frm)
            elif to in need_ids:
                need_only_req_ids.add(frm)
        need_only_req_ids -= linked_req_ids

    unattached = [
        r for r in requirements
        if r["id"] not in linked_req_ids and r["id"] not in need_only_req_ids
        and not is_archived(r)
    ]
    archived_reqs = [r for r in requirements if is_archived(r)]
    by_id = {r["id"]: r for r in active}

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
        f"| Бизнес-цели | {num_goals} |",
        f"| Требований в реестре | {total_reqs} |",
        f"| — из них в архиве (5.2) | {len(archived_reqs)} |",
    ]
    if precise:
        # Counted over LINKS, so it matches the column of the table below: a
        # requirement serving two objectives is counted under each of them. The old
        # figure was registry/objectives, which agrees with no list in the document.
        pairs = sum(len(v) for v in per_goal.values())
        lines.append(
            f"| Требований на цель в среднем | {pairs / max(1, num_goals):.1f} "
            f"(по {pairs} связям цель↔требование) |")
    else:
        lines.append(
            f"| Требований на цель (реестр ÷ цели) | {avg_per_goal:.1f} |")

    if precise:
        covered_count = sum(1 for gid in per_goal if per_goal[gid])
        lines += [
            f"| Целей покрыто | {covered_count} из {num_goals} |",
            "",
            "> **Покрытие по каждой цели считается по связям `satisfies` в графе 5.1.** "
            "Требование попадает под цель только потому, что аналитик его туда связал — "
            "из текста ничего не выводится.",
            "",
            "## Покрытие по бизнес-целям",
            "",
            "| | Цель | Требований | ID |",
            "|---|-----------|--------------|-----|",
        ]
        # The threshold is relative: "far more than this project's own average"
        # rather than a fixed 10. On 105 requirements across 4 objectives every
        # objective was permanently 🟡, so the flag stopped carrying information.
        # The floor keeps it meaningful on small projects, where the average is tiny.
        mean_per_goal = sum(len(v) for v in per_goal.values()) / max(1, num_goals)
        over_threshold = max(10, mean_per_goal * 2)
        for gid, title in goal_entries:
            covered = per_goal.get(gid, [])
            if not covered:
                flag = "🔴"
            elif len(covered) > over_threshold:
                flag = "🟡"
            else:
                flag = "🟢"
            title_short = title[:70] + "..." if len(title) > 70 else title
            ids = list_with_cap(covered)
            mark = archived_suffix(by_id.get(gid))
            lines.append(
                f"| {flag} | `{gid}` {title_short}{mark} | {len(covered)} | {ids} |")
        lines += [
            "",
            f"> 🔴 цели не служит ни одно требование &nbsp;|&nbsp; 🟢 норма "
            f"&nbsp;|&nbsp; 🟡 больше {over_threshold:.0f} — вдвое выше среднего по "
            f"проекту ({mean_per_goal:.1f}), возможно переусложнение",
            "",
        ]
    else:
        lines += [
            "",
            "> **Цели пришли из источника без id в графе**, поэтому покрытие по каждой "
            "цели посчитать нельзя — и оно не утверждается. Задайте цели в 6.2 "
            "(`define_goals_and_objectives`): они регистрируются как узлы графа, и связывание "
            "требований с ними (параметр `business_goal_ids_json` у создающих инструментов "
            "7.1) превращает этот отчёт в точную матрицу по каждой цели.",
            "",
            "## Бизнес-цели — чеклист",
            "",
            "> Убедитесь глазами, что каждой цели отвечает хотя бы одно требование из списка ниже.",
            "",
        ]
        for goal in business_goals:
            goal_short = goal[:80] + "..." if len(goal) > 80 else goal
            lines.append(f"- [ ] {goal_short}")
        lines.append("")

    lines += [
        "## Требования в реестре",
        "",
        "| ID | Тип | Название |",
        "|----|------|-------|",
    ]
    for req in requirements:
        lines.append(f"| `{req['id']}` | {req.get('type', '—')} | {req.get('title', '—')}"
                     f"{archived_suffix(req)} |")

    # Precise mode ONLY. In degraded mode nothing is linked because nothing CAN be linked,
    # so listing every requirement as unattached would be exactly the kind of false claim
    # this report exists to avoid.
    if precise and unattached:
        by_type = {}
        for r in unattached:
            by_type.setdefault(r.get("type", "—"), []).append(r["id"])
        lines += ["", "## Требования, не связанные ни с одной целью", ""]
        for rtype in sorted(by_type):
            ids = ", ".join(f"`{i}`" for i in sorted(by_type[rtype]))
            lines.append(f"- **{rtype}** ({len(by_type[rtype])}): {ids}")
        lines += [
            "",
            "> Вспомогательные модели (словарь данных, ERD) обычно оставляют без связи — "
            "они описывают решение, а не служат цели напрямую.",
        ]

    if need_only_req_ids:
        ids = ", ".join(f"`{i}`" for i in sorted(need_only_req_ids))
        lines += [
            "",
            f"> **Трассировано на бизнес-потребность, но не на цель:** {ids}. "
            f"Обычно это значит, что 6.2 ещё не раскрыла эту потребность в цели.",
        ]

    lines += [
        "",
        "---",
        "",
        "## Сигналы и рекомендации",
        "",
    ]
    if precise:
        uncovered = [f"`{gid}`" for gid, _ in goal_entries if not per_goal.get(gid)]
        if uncovered:
            lines.append(
                f"- 🔴 **Целей без единого требования: {len(uncovered)}** — "
                f"{', '.join(uncovered)}. Либо опишите для них требования, либо свяжите "
                f"существующие через создающие инструменты 7.1 / `add_trace_link` (5.1)."
            )
        crowded = [f"`{gid}`" for gid, _ in goal_entries if len(per_goal.get(gid, [])) >= 10]
        if crowded:
            lines.append(
                f"- 🟡 **Возможно переусложнение:** на {', '.join(crowded)} приходится "
                f"по 10+ требований. Проверьте на дубликаты через `check_coverage` (5.1)."
            )
    elif over_engineering:
        lines.append(
            f"- 🟡 **Возможно переусложнение или дублирование:** {total_reqs} требований на "
            f"{num_goals} {plural_ru(num_goals, 'бизнес-цель', 'бизнес-цели', 'бизнес-целей')} "
            f"(в среднем {avg_per_goal:.1f} на цель). Проверьте на дубликаты через "
            f"`check_coverage` (5.1)."
        )
    lines.append(
        "- ✅ **Дальше:** убедитесь, что закрыта каждая цель, затем запускайте "
        "верификацию (7.2) и валидацию (7.3)."
    )
    lines.append(
        "- ℹ️ Для полной трассировки по каждому требованию (источники, реализация, тесты) "
        "запустите `check_coverage` (5.1)."
    )

    content = "\n".join(lines)
    save_artifact(content, prefix="7_1_coverage_matrix", project_id=project_id)
    return content


if __name__ == "__main__":
    mcp.run()
