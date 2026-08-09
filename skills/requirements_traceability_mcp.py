"""
BABOK 5.1 — Trace Requirements
MCP-инструменты для управления трассировкой требований.

Инструменты:
  - init_traceability_repo    — создать/переинициализировать репозиторий трассировки
  - add_trace_link            — добавить или удалить связь между артефактами
  - run_impact_analysis       — анализ влияния: что затронет изменение требования
  - check_coverage            — аудит покрытия: orphan-требования, дыры в реализации
  - export_traceability_matrix — сгенерировать Markdown-матрицу из репозитория

Хранение: JSON-репозиторий (граф в формате edge list) + Markdown по запросу.

Интеграция:
  Вход: артефакты 4.3 (save_confirmed_elicitation_result),
        артефакты 4.2 при CR (save_cr_elicitation_analysis)
  Выход: run_impact_analysis → используется в 5.4
         export_traceability_matrix → используется в 5.5
         check_coverage → используется в 5.3, 5.5

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date, datetime
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import (write_json_artifact, save_artifact, logger, DATA_DIR, data_path,
                           normalize_project_id, ANALYSIS_NODE_TYPES,
                           NON_REQUIREMENT_NODE_TYPES,
                           BUSINESS_NODE_TYPES, has_been_approved,
    has_passed_verification, has_been_validated,
    read_json_artifact, guard_artifact_errors, parse_json_dict_list,
    link_date, is_archived, archived_suffix, NODE_TYPE_LABELS,
    list_with_cap,
)

from skills.plural_ru import plural_ru

mcp = FastMCP("BABOK_Requirements_Traceability")

REPO_FILENAME = "traceability_repo.json"

# Requirement types whose behaviour a test case can verify — the "no test" coverage
# axis applies to these and only these. The two BABOK classes are the original rule;
# the four 7.1 types joined by product decision (2026-07-22). Model artifacts
# (erd, data_dictionary, business_process, business_rule) are deliberately absent:
# they are reviewed, not executed against a test.
BEHAVIORAL_REQ_TYPES = {
    "solution", "transition",
    "functional", "non_functional", "user_story", "use_case",
}


# ---------------------------------------------------------------------------
# Утилиты работы с репозиторием
# ---------------------------------------------------------------------------

def _repo_path(project_name: str) -> str:
    """Возвращает путь к JSON-файлу репозитория для проекта."""
    safe_name = normalize_project_id(project_name)
    return data_path(project_name, f"{safe_name}_{REPO_FILENAME}")


def _load_repo(project_name: str) -> dict:
    """Загружает репозиторий из JSON. Возвращает пустую структуру если не существует."""
    path = _repo_path(project_name)
    if os.path.exists(path):
        # Raises CorruptArtifactError, converted to a ❌ line by guard_artifact_errors
        # at the tool boundary. A bare json.load here made a damaged file a protocol
        # error in every downstream tool.
        return read_json_artifact(path, "5.1 traceability repository")
    return {
        "project": project_name,
        "formality_level": "Standard",
        "created": str(date.today()),
        "updated": str(date.today()),
        "requirements": [],
        "links": [],
        "history": []
    }


def _save_repo(repo: dict) -> str:
    """Сохраняет репозиторий в JSON. Возвращает путь."""
    project_name = repo["project"]
    path = _repo_path(project_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    repo["updated"] = str(date.today())
    write_json_artifact(path, repo)
    logger.info(f"Traceability repository updated: {path}")
    return path


def _find_req(repo: dict, req_id: str) -> Optional[dict]:
    """Находит требование по ID."""
    for r in repo["requirements"]:
        if r["id"] == req_id:
            return r
    return None


def _counts_as_evidence(repo: dict, node_id: str) -> bool:
    """May a link to `node_id` be read as justification, implementation or a test?

    No, if the node has been archived by 5.2 — that is the doctrine the coverage audit
    prints above its archived table, and it has to hold for the VERDICT and not only
    for the selection. A requirement whose need, component and test were all retired
    was reported as fully covered three lines under the banner denying it.

    Yes, if the id is not in the graph at all: an id outside the repository is a
    documented legitimate reference, so it is EXTERNAL, not archived. Reading
    "not live" as "archived" would turn every external reference into an orphan — the
    false positive `add_trace_link` was deliberately built to avoid.
    """
    return not is_archived(_find_req(repo, node_id))


def _find_links(repo: dict, req_id: str) -> list:
    """Возвращает все связи где req_id фигурирует как from или to."""
    return [lnk for lnk in repo["links"]
            if lnk["from"] == req_id or lnk["to"] == req_id]


# ---------------------------------------------------------------------------
# 5.1.1 — Инициализация репозитория трассировки
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def init_traceability_repo(
    project_name: str,
    formality_level: Literal["Lite", "Standard", "Full"],
    requirements_json: str,
) -> str:
    """
    BABOK 5.1 — Создаёт или переинициализирует репозиторий трассировки требований.
    Вызывается один раз при старте проекта или при добавлении первой партии требований.

    Args:
        project_name:        Название проекта (должно совпадать во всех инструментах 5.x).
        formality_level:     Уровень формальности:
                             - Lite     — только derives-цепочка. Agile, небольшие проекты.
                             - Standard — derives + verifies. Большинство проектов.
                             - Full     — все 4 типа связей + rationale обязателен. Regulated domains.
        requirements_json:   Начальный список требований. Формат:
                             [
                               {
                                 "id": "BR-001",
                                 "type": "business",
                                 "title": "Снизить время обработки заявки до 5 минут",
                                 "version": "1.0",
                                 "status": "confirmed",
                                 "source_artifact": "governance_plans/4_3_..._confirmed.md"
                               }
                             ]
                             Допустимые type: business | stakeholder | solution | transition | test | component
                             Допустимые status: draft | confirmed | approved | deprecated

    Returns:
        Отчёт о создании репозитория + статистика по требованиям.
    """
    logger.info(f"init_traceability_repo: {project_name}, уровень: {formality_level}")

    # Shape, not just syntax. The elements are used as objects a few lines down, so a
    # list of bare ids — the most likely mistake, since neighbouring parameters
    # legitimately take strings — used to raise AttributeError out of the tool.
    requirements, shape_error = parse_json_dict_list(
        requirements_json, "requirements_json", required=True,
        example='[{"id": "FR-001", "type": "functional", "title": "..."}]')
    if shape_error:
        return shape_error

    # Загружаем существующий репозиторий (если есть) — не затираем links
    repo = _load_repo(project_name)
    repo["formality_level"] = formality_level

    # Добавляем требования (дедупликация по id)
    existing_ids = {r["id"] for r in repo["requirements"]}
    added = []
    updated = []

    for req in requirements:
        req_id = req.get("id", "")
        if not req_id:
            continue
        # What the CALLER actually stated, before defaults are filled in. A default is
        # an assumption, and an assumption must never overwrite a value another chapter
        # established — the same rule the 3.2 registry seeding follows.
        stated = {k: v for k, v in req.items() if v not in (None, "")}

        req.setdefault("version", "1.0")
        req.setdefault("status", "draft")
        req.setdefault("source_artifact", "")
        req["added"] = str(date.today())

        if req_id in existing_ids:
            # MERGE into the existing entry, never replace it.
            #
            # Wholesale replacement destroyed every field the caller did not restate —
            # above all `type`, which 6.1 and 6.2 set when they register their nodes and
            # which every other chapter's traversal and skip-filter depends on. An
            # analyst re-running this tool with BN-001 in the list turned a
            # `business_need/confirmed` node into `type: None, status: draft`, after
            # which it silently dropped out of the coverage roots, the 7.1 objective
            # source and the 7.3/7.4 filters. Explicit values still win; omitted ones
            # are inherited.
            for i, r in enumerate(repo["requirements"]):
                if r["id"] == req_id:
                    merged = dict(r)
                    merged.update(stated)
                    merged["added"] = r.get("added", req["added"])
                    repo["requirements"][i] = merged
                    updated.append(req_id)
                    break
        else:
            repo["requirements"].append(req)
            added.append(req_id)
            existing_ids.add(req_id)

    repo_path = _save_repo(repo)

    # Статистика по типам
    type_counts: dict = {}
    for r in repo["requirements"]:
        t = r.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    # Формируем отчёт
    lines = [
        f"<!-- BABOK 5.1 — Трассировка требований | Проект: {project_name} | {date.today()} -->",
        "",
        f"# 📐 Репозиторий трассировки инициализирован",
        "",
        f"**Проект:** {project_name}  ",
        f"**Уровень формальности:** {formality_level}  ",
        f"**Файл репозитория:** `{repo_path}`  ",
        f"**Дата:** {date.today()}",
        "",
        "## Статистика требований",
        "",
        f"- **Всего:** {len(repo['requirements'])}",
        f"- **Добавлено сейчас:** {len(added)}",
        f"- **Обновлено:** {len(updated)}",
        f"- **Связей в репозитории:** {len(repo['links'])}",
        "",
        "### По типам:",
    ]

    type_labels = {
        "business": "Бизнес-требования (BR)",
        "stakeholder": "Требования стейкхолдеров (SR)",
        "solution": "Требования к решению (FR/NFR)",
        "transition": "Переходные требования (TR)",
        "test": "Тесты (TC)",
        "component": "Компоненты (COMP)",
        "solution_scope": "Границы решения (6.4)",
    }
    for t, count in type_counts.items():
        label = type_labels.get(t, t)
        lines.append(f"- {label}: **{count}**")

    lines += [
        "",
        "## Уровень формальности — что трассируем",
        "",
    ]

    if formality_level == "Lite":
        lines += [
            "| Тип связи | Статус |",
            "|-----------|--------|",
            "| `derives` (вертикальная иерархия) | ✅ Обязательно |",
            "| `depends` (горизонтальные зависимости) | — Не требуется |",
            "| `satisfies` (компонент реализует) | — Не требуется |",
            "| `verifies` (тест проверяет) | — Не требуется |",
            "",
            "> **Lite** подходит для Agile-проектов и небольших команд.",
        ]
    elif formality_level == "Standard":
        lines += [
            "| Тип связи | Статус |",
            "|-----------|--------|",
            "| `derives` (вертикальная иерархия) | ✅ Обязательно |",
            "| `depends` (горизонтальные зависимости) | 🟡 Опционально |",
            "| `satisfies` (компонент реализует) | 🟡 Опционально |",
            "| `verifies` (тест проверяет) | ✅ Обязательно |",
            "",
            "> **Standard** — оптимальный баланс для большинства проектов.",
        ]
    else:  # Full
        lines += [
            "| Тип связи | Статус |",
            "|-----------|--------|",
            "| `derives` (вертикальная иерархия) | ✅ Обязательно |",
            "| `depends` (горизонтальные зависимости) | ✅ Обязательно |",
            "| `satisfies` (компонент реализует) | ✅ Обязательно |",
            "| `verifies` (тест проверяет) | ✅ Обязательно |",
            "",
            "> **Full** — все связи + `rationale` обязателен. Regulated domains, compliance.",
        ]

    if added:
        lines += ["", "## Добавленные требования", ""]
        for req in repo["requirements"]:
            if req["id"] in added:
                lines.append(f"- `{req['id']}` v{req.get('version','1.0')} [{req.get('status','draft')}] — {req.get('title','')}")

    lines += [
        "",
        "---",
        "**Следующий шаг:** добавить связи между требованиями через `add_trace_link`",
        f"или запустить аудит покрытия через `check_coverage`.",
    ]

    content = "\n".join(lines)
    save_artifact(content, prefix="5_1_traceability_init", project_id=project_name)
    return content + f"\n\n✅ Репозиторий сохранён: `{repo_path}`"


# ---------------------------------------------------------------------------
# 5.1.2 — Добавление / удаление связи между артефактами
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def add_trace_link(
    project_name: str,
    from_id: str,
    to_id: str,
    # `threatens` (6.3) and `modifies` (5.4) are here so a wrong edge written by those
    # chapters can be REMOVED through the tool. Without them the only way to delete one
    # was hand-editing the repository JSON — which is exactly what this tool exists to
    # prevent the analyst from doing.
    relation: Literal["derives", "depends", "satisfies", "verifies",
                      "threatens", "modifies"],
    rationale: str,
    remove: bool = False,
) -> str:
    """
    BABOK 5.1 — Добавляет или удаляет связь между двумя артефактами в репозитории.

    Link semantics:
      - derives:   from derives from to (top-down hierarchy: BR → SR → FR)
      - depends:   from doesn't make sense without to (horizontal dependency)
      - satisfies: from (component) implements to (requirement) — direction: COMP satisfies FR
      - verifies:  from (test) verifies to (requirement) — direction: TC verifies FR
                   (corresponds to BABOK's "Validate" trace relation — same definition;
                    the name follows the SysML/DOORS convention)

    Args:
        project_name:  Название проекта.
        from_id:       ID артефакта-источника (BR-001, FR-007, TC-042, COMP-Auth).
        to_id:         ID артефакта-цели.
        relation:      Тип отношения: derives | depends | satisfies | verifies
        rationale:     Обоснование связи. В Full — обязательно подробное.
                       В Lite/Standard — можно кратко или пустую строку.
        remove:        Если True — удалить существующую связь вместо добавления.

    Returns:
        Подтверждение операции + текущее состояние связей артефакта.
    """
    logger.info(f"add_trace_link: {from_id} --[{relation}]--> {to_id}, remove={remove}")

    repo = _load_repo(project_name)

    if remove:
        # Удаляем связь
        before = len(repo["links"])
        repo["links"] = [
            lnk for lnk in repo["links"]
            if not (lnk["from"] == from_id and lnk["to"] == to_id and lnk["relation"] == relation)
        ]
        after = len(repo["links"])
        if before == after:
            return f"⚠️ Связь `{from_id} --[{relation}]--> {to_id}` не найдена в репозитории."
        # Пишем в историю
        repo["history"].append({
            "action": "link_removed",
            "from": from_id,
            "to": to_id,
            "relation": relation,
            "date": str(date.today()),
        })
        _save_repo(repo)
        return f"✅ Связь `{from_id} --[{relation}]--> {to_id}` удалена из репозитория."

    # Проверяем дубликат
    for lnk in repo["links"]:
        if lnk["from"] == from_id and lnk["to"] == to_id and lnk["relation"] == relation:
            return f"ℹ️ Связь `{from_id} --[{relation}]--> {to_id}` уже существует."

    # Warn about ends that are not repository nodes — but still write the edge.
    # External artifact ids (COMP-Auth, a Jira ticket) are legitimate targets, so a
    # hard check would break real usage; accepting a typo SILENTLY, however, creates
    # an edge to nowhere that check_coverage counts as a source — silencing exactly
    # the orphan check meant to catch it. Product decision (2026-07-22): warn + write.
    missing_ends = [
        node_id for node_id in (from_id, to_id) if _find_req(repo, node_id) is None
    ]
    dangling_note = ""
    if missing_ends:
        listed = ", ".join(f"`{node_id}`" for node_id in missing_ends)
        dangling_note = (
            f"\n⚠️ {listed}: в репозитории нет. Если это внешний артефакт "
            f"(компонент, тикет) — всё в порядке; если это опечатка, снимите связь "
            f"через `remove=True`: проверки покрытия считают такую связь настоящим "
            f"обоснованием.\n"
        )

    # Add the link
    new_link = {
        "from": from_id,
        "to": to_id,
        "relation": relation,
        "rationale": rationale,
        "added": str(date.today()),
    }
    repo["links"].append(new_link)

    # Пишем в историю
    repo["history"].append({
        "action": "link_added",
        "from": from_id,
        "to": to_id,
        "relation": relation,
        "date": str(date.today()),
    })

    _save_repo(repo)

    # Показываем все текущие связи обоих узлов
    from_links = _find_links(repo, from_id)
    to_links = _find_links(repo, to_id)

    rel_icons = {
        "derives": "⬇️",
        "depends": "↔️",
        "satisfies": "✔️",
        "verifies": "🧪",
    }

    lines = [
        f"✅ Связь добавлена: `{from_id}` --[**{relation}**]--> `{to_id}`",
        dangling_note,
        f"**Rationale:** {rationale or '—'}",
        "",
        f"### Текущие связи `{from_id}`:",
    ]
    if from_links:
        for lnk in from_links:
            icon = rel_icons.get(lnk["relation"], "→")
            direction = f"`{lnk['from']}` {icon}[{lnk['relation']}]→ `{lnk['to']}`"
            lines.append(f"- {direction}")
    else:
        lines.append("- (нет связей)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 5.1.3 — Анализ влияния изменения
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def run_impact_analysis(
    project_name: str,
    changed_req_id: str,
    change_description: str,
    depth: Literal["direct", "full"] = "full",
) -> str:
    """
    BABOK 5.1 — Анализ влияния: обходит граф связей и возвращает все затронутые артефакты.

    Это техническая операция — обход графа. Экспертная оценка «брать/не брать»
    и приоритизация последствий — задача 5.4.

    Args:
        project_name:        Название проекта.
        changed_req_id:      ID изменяемого / удаляемого требования.
        change_description:  Краткое описание изменения (для отчёта).
        depth:               - direct: только прямые связи (1 уровень)
                             - full:   полный обход в обе стороны (рекомендуется)

    Returns:
        Отчёт: что затронуто, типы связей, рекомендуемые действия для 5.4.
    """
    logger.info(f"run_impact_analysis: {changed_req_id}, depth={depth}")

    repo = _load_repo(project_name)
    req = _find_req(repo, changed_req_id)

    if not req:
        return (
            f"⚠️ Требование `{changed_req_id}` не найдено в репозитории проекта `{project_name}`.\n"
            f"Проверьте ID или инициализируйте репозиторий через `init_traceability_repo`."
        )

    # BFS обход графа
    visited = set()
    queue = [changed_req_id]
    affected: list[dict] = []

    while queue:
        current_id = queue.pop(0)
        if current_id in visited:
            continue
        visited.add(current_id)

        direct_links = _find_links(repo, current_id)
        for lnk in direct_links:
            neighbor_id = lnk["to"] if lnk["from"] == current_id else lnk["from"]
            if neighbor_id == changed_req_id:
                continue
            neighbor_req = _find_req(repo, neighbor_id)
            direction = "downstream" if lnk["from"] == current_id else "upstream"
            affected.append({
                "id": neighbor_id,
                "title": neighbor_req.get("title", "—") if neighbor_req else "внешний артефакт",
                "type": neighbor_req.get("type", "unknown") if neighbor_req else "external",
                "relation": lnk["relation"],
                "direction": direction,
                "via": current_id,
                "status": neighbor_req.get("status", "—") if neighbor_req else "—",
            })
            # Report the business node as affected, but do NOT continue THROUGH it.
            #
            # Objectives are hubs: since 7.1 began writing `satisfies` from every
            # requirement to the objectives it serves (ADR-082), expanding past one
            # walked back down to every other requirement serving the same objective.
            # Changing a single requirement was reported as affecting 14 of 16 nodes,
            # and the better the analyst's traceability, the more inflated the estimate
            # — which also drove 5.4's Impact and Schedule Risk scores. Siblings sharing
            # an objective are not impacted by each other; the objective itself is worth
            # flagging, so it stays in the list.
            neighbor_is_business = (
                neighbor_req is not None
                and neighbor_req.get("type") in BUSINESS_NODE_TYPES
            )
            if depth == "full" and neighbor_id not in visited and not neighbor_is_business:
                queue.append(neighbor_id)

    # Деduplication по id (оставляем первое вхождение)
    seen_ids: set = set()
    unique_affected = []
    for item in affected:
        if item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            unique_affected.append(item)

    # Group by link type.
    #
    # The headline count comes from `unique_affected`, so every relation reachable in
    # the graph MUST have a bucket here. Grouping into a fixed four while counting all
    # of them printed "13 artifacts affected" above tables holding nine rows, and the
    # artifacts it dropped were the ones reached over `threatens` — the risks
    # endangering the objective, which is precisely what impact analysis exists to
    # surface. Build the buckets from what is actually present.
    rel_labels = {
        "derives": ("⬇️ Производные требования", "Пересмотреть — они выведены из изменяемого"),
        "depends": ("↔️ Зависимые требования", "Проверить — без изменяемого они могут потерять смысл"),
        "satisfies": ("✔️ Связаны через satisfies (компоненты / достигаемые цели)",
                      "Компоненты: оценить переделку. Цели: проверить, что цель по-прежнему достигается"),
        "verifies": ("🧪 Тесты", "Перезапустить или обновить тест-кейсы"),
        "threatens": ("⚠️ Риски (6.3)", "Переоценить — они угрожают изменяемому"),
        "modifies": ("📝 Запросы на изменение (5.4)", "Проверить, применим ли ещё незакрытый CR"),
    }

    by_relation: dict = {rel: [] for rel in rel_labels}
    for item in unique_affected:
        rel = item["relation"]
        by_relation.setdefault(rel, []).append(item)
        rel_labels.setdefault(
            rel, (f"🔗 Связано через `{rel}`", "Пересмотреть связь"))

    lines = [
        f"<!-- BABOK 5.1 — Анализ влияния | Проект: {project_name} | {date.today()} -->",
        "",
        f"# 🔍 Анализ влияния изменения",
        "",
        f"**Проект:** {project_name}  ",
        f"**Изменяемое требование:** `{changed_req_id}` — {req.get('title', '')}  ",
        f"**Описание изменения:** {change_description}  ",
        f"**Режим обхода:** {depth}  ",
        f"**Дата:** {date.today()}",
        "",
        f"## Итог: затронуто **{len(unique_affected)}** артефактов",
        "",
    ]

    if not unique_affected:
        lines += [
            "Связей с другими артефактами не найдено.",
            "",
            "> ℹ️ Либо требование изолированное, либо трассировка ещё не заполнена.",
            "> Рекомендуется проверить через `check_coverage`.",
        ]
    else:
        for rel, (label, action) in rel_labels.items():
            items = by_relation[rel]
            if not items:
                continue
            lines += [
                f"### {label} ({len(items)})",
                f"> **Действие:** {action}",
                "",
                "| ID | Тип | Название | Статус | Через |",
                "|----|-----|----------|--------|-------|",
            ]
            for item in items:
                via = f"`{item['via']}`" if item["via"] != changed_req_id else "напрямую"
                lines.append(
                    f"| `{item['id']}` | {item['type']} | {item['title']} | {item['status']} | {via} |"
                )
            lines.append("")

    lines += [
        "---",
        "",
        "## Передать в 5.4 для экспертной оценки",
        "",
        "Этот отчёт — техническая карта затронутых артефактов.",
        "Задача **5.4** добавляет экспертное решение:",
        "",
        "- Стоит ли брать это изменение?",
        "- Какова цена (время, ресурсы, риски)?",
        "- Что откладывается в backlog?",
        "- Нужно ли формальное согласование (5.5)?",
    ]

    content = "\n".join(lines)
    save_artifact(content, prefix="5_1_impact_analysis", project_id=project_name)
    return content


# ---------------------------------------------------------------------------
# 5.1.4 — Аудит покрытия
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def check_coverage(
    project_name: str,
    filter_type: str = "",
) -> str:
    """
    BABOK 5.1 — Аудит покрытия трассировки. Находит orphan-требования и дыры.

    What it looks for:
      🔴 Orphan with no source — no derives/satisfies link upward (no business justification)
      🟡 No implementation     — no derives/satisfies link downward (not implemented)
      🟡 No test               — no verifies link (not verified)
      🟢 Full coverage         — has source + implementation + test

    Args:
        project_name:  Название проекта.
        filter_type:   Фильтр по типу требований: business | stakeholder | solution | transition
                       Пустая строка — проверить все.

    Returns:
        Отчёт о покрытии по каждому требованию с рекомендациями.
    """
    logger.info(f"check_coverage: {project_name}, filter_type={filter_type!r}")

    repo = _load_repo(project_name)
    formality = repo.get("formality_level", "Standard")

    # Archived requirements are SHOWN, MARKED and COUNTED — they simply never count as
    # coverage (owner's decision, 2026-08-03; see the doctrine at ARCHIVED_REQUIREMENT_
    # STATUSES). They used to be dropped from the selection here, which moved the
    # denominator without saying so: this audit answered `Total items 6` while the
    # matrix answered 8 for the same graph. It also silenced the audit about exactly
    # what `deprecate_requirements` sends the analyst here to check — links still
    # pointing at the node just archived.
    requirements = list(repo["requirements"])
    if filter_type:
        requirements = [r for r in requirements if r.get("type") == filter_type]

    if not requirements:
        return f"ℹ️ Требований{' типа `' + filter_type + '`' if filter_type else ''} в репозитории проекта `{project_name}` не найдено."

    archived = [r for r in requirements if is_archived(r)]
    live = [r for r in requirements if not is_archived(r)]

    # Computed ONCE, and both the table and the recommendations below read it: the count
    # and the list have to come from the same traversal, or the document ends up
    # printing a number no row supports.
    archived_referrers = {
        req["id"]: sorted({
            lnk["from"] for lnk in _find_links(repo, req["id"])
            if lnk["to"] == req["id"] and not is_archived(_find_req(repo, lnk["from"]))
        })
        for req in archived
    }
    still_referenced = sorted(k for k, v in archived_referrers.items() if v)

    orphans_no_source = []
    orphans_no_impl = []
    orphans_no_test = []
    fully_covered = []

    for req in live:
        req_id = req["id"]
        req_type = req.get("type", "")

        links = _find_links(repo, req_id)

        # A node HAS a source when it points UPWARD at something: it derives from a
        # parent, or it satisfies a goal/requirement. Both relations share the canonical
        # direction from=child/implementer -> to=parent/implemented, so the node is the
        # `from` in either case. (`verifies` gets the same treatment for tests below.)
        # Counting only `derives` false-flags two real populations: a 7.1 requirement
        # linked to a 6.2 business goal (ADR-082) and the `solution` nodes 6.4 pushes,
        # neither of which ever has a derives edge.
        # HAS an implementation when something derives from it (children point in as
        # `to`) or something satisfies it.
        #
        # Every one of the three asks the SAME question of the far end: is the node at
        # the other end of this link still evidence? An archived one is not — see
        # `_counts_as_evidence`.
        has_source = any(
            lnk["relation"] in ("derives", "satisfies") and lnk["from"] == req_id
            and _counts_as_evidence(repo, lnk["to"])
            for lnk in links
        )
        has_impl = any(
            ((lnk["relation"] == "derives" and lnk["to"] == req_id) or
             (lnk["relation"] == "satisfies" and lnk["to"] == req_id))
            and _counts_as_evidence(repo, lnk["from"])
            for lnk in links
        )
        has_test = any(
            lnk["relation"] == "verifies" and lnk["to"] == req_id
            and _counts_as_evidence(repo, lnk["from"])
            for lnk in links
        )

        # Root requirement types have no "source" above them — that's expected
        # (a business need is the root of the derivation chain, like a business req).
        if req_type in ("business", "business_need"):
            has_source = True
        # A test's source is the requirement it verifies: tests link via `verifies`
        # (from=test -> to=req), never `derives`, so a test that verifies something
        # is not an orphan.
        elif req_type == "test":
            has_source = has_source or any(
                lnk["relation"] == "verifies" and lnk["from"] == req_id
                and _counts_as_evidence(repo, lnk["to"])
                for lnk in links
            )
        # Analysis artifacts from other chapters anchor themselves with their OWN
        # relation: 6.3 writes `threatens` (from=risk -> to=objective) and 5.4 writes
        # `modifies` (from=CR -> to=requirement). Judging them by `derives`/`satisfies`
        # alone made every risk and every change request an orphan, and the audit told
        # the analyst to "find a business justification or freeze it" for nodes that
        # were already anchored.
        elif req_type in ANALYSIS_NODE_TYPES:
            has_source = has_source or any(
                lnk["relation"] in ("threatens", "modifies") and lnk["from"] == req_id
                and _counts_as_evidence(repo, lnk["to"])
                for lnk in links
            )
            # Nor is anything supposed to IMPLEMENT them. An analysis artifact points
            # upward at what it concerns and that is its whole shape: nothing derives
            # from a risk, nothing satisfies a change request, and 6.4's scope node is
            # itself the implementer of the objectives it satisfies. Judging them by
            # the requirement rule told the analyst to "fill the gaps: add
            # implementation" for every risk in the project — the same misclassification
            # as the orphan verdict, one column over.
            has_impl = True
        # A component IS an implementer (it satisfies requirements); nothing implements a
        # component further, so a manually-added COMP node is not "missing implementation".
        elif req_type == "component":
            has_impl = True

        issues = []
        if not has_source:
            issues.append("no_source")
        if not has_impl:
            issues.append("no_impl")
        # Тест проверяем только в Standard и Full
        if formality in ("Standard", "Full") and not has_test:
            # A test is expected from BEHAVIORAL requirement types. The original
            # rule knew only the classes `solution` / `transition` — the vocabulary
            # 5.1 shipped with — so the eight 7.1 node types were never checked and
            # a project specified entirely through 7.1 answered "✅ Coverage is
            # complete" without a single verifies edge (the axis was dead for the
            # platform's main path). Model artifacts (erd, data_dictionary,
            # business_process, business_rule) are not verified by test cases and
            # business/stakeholder requirements stay exempt as before.
            if req_type in BEHAVIORAL_REQ_TYPES:
                issues.append("no_test")

        req_info = {
            "id": req_id,
            "title": req.get("title", "—"),
            "type": req_type,
            "version": req.get("version", "1.0"),
            "status": req.get("status", "—"),
            "links_count": len(links),
        }

        if "no_source" in issues:
            orphans_no_source.append(req_info)
        elif "no_impl" in issues or "no_test" in issues:
            req_info["issues"] = issues
            orphans_no_impl.append(req_info)
        else:
            fully_covered.append(req_info)

    # Every item of the graph is in exactly one bucket, and the four sum to the total:
    # covered + orphan + gaps + archived. A reader adding up the column gets the number
    # printed under it.
    total = len(requirements)
    covered_pct = round(len(fully_covered) / total * 100) if total else 0
    # The audit spans the whole traceability graph. Analysis artifacts (risk /
    # change_request / solution_scope) are traced for connectivity but are NOT
    # requirements to prioritise (5.3) or approve (5.5) — call that out so the counts
    # and the "ready for 5.3/5.5" verdict are not read as a requirement tally.
    non_requirements = [r for r in requirements
                        if r.get("type", "") in NON_REQUIREMENT_NODE_TYPES]
    analysis_count = len(non_requirements)
    # The caption is built from the types actually present. It used to be a hard-coded
    # list ("risks / change requests / solution scope") printed beside a count taken
    # over a WIDER set (business roots + analysis + tests), so a project with no risk
    # and no CR still read "4 analysis artifact(s) (risks / change requests / ...)" —
    # a caption naming categories the project does not contain.
    present_labels = sorted({
        NODE_TYPE_LABELS.get(r.get("type", ""), r.get("type", "") or "untyped")
        for r in non_requirements
    })

    lines = [
        f"<!-- BABOK 5.1 — Аудит покрытия | Проект: {project_name} | {date.today()} -->",
        "",
        f"# 📊 Аудит покрытия трассировки",
        "",
        f"**Проект:** {project_name}  ",
        f"**Уровень формальности:** {formality}  ",
        f"**Фильтр:** {filter_type or 'все требования'}  ",
        f"**Дата:** {date.today()}",
        "",
        "## Сводка",
        "",
        f"| Статус | Количество | % |",
        f"|--------|------------|---|",
        f"| 🟢 Полное покрытие | {len(fully_covered)} | {covered_pct}% |",
        f"| 🔴 Без источника (orphan) | {len(orphans_no_source)} | {round(len(orphans_no_source)/total*100) if total else 0}% |",
        f"| 🟡 Пробелы в покрытии | {len(orphans_no_impl)} | {round(len(orphans_no_impl)/total*100) if total else 0}% |",
        f"| 📦 В архиве (5.2) | {len(archived)} | {round(len(archived)/total*100) if total else 0}% |",
        f"| **Всего элементов** | **{total}** | 100% |",
        "",
    ]
    if analysis_count:
        lines += [
            f"> ℹ️ Требований: **{total - analysis_count}**, узлов другого рода: "
            f"**{analysis_count}** ({', '.join(present_labels)}). Они проверяются только "
            f"на связность графа — их не приоритизируют (5.3) и не согласуют (5.5).",
            "",
        ]

    if orphans_no_source:
        lines += [
            "## 🔴 Требования без источника (orphan)",
            "",
            "> **Диагноз:** нет связи `derives` или `satisfies` вверх. Неизвестно, из какой бизнес-потребности или цели требование выросло.",
            "> **Действие:** найдите бизнес-обоснование через `add_trace_link` либо заморозьте требование.",
            "",
            "| ID | Тип | Название | Статус |",
            "|----|-----|----------|--------|",
        ]
        for r in orphans_no_source:
            lines.append(f"| `{r['id']}` | {r['type']} | {r['title']} | {r['status']} |")
        lines.append("")

    if orphans_no_impl:
        lines += [
            "## 🟡 Требования с пробелами в покрытии",
            "",
            "| ID | Тип | Название | Статус | Проблема |",
            "|----|-----|----------|--------|----------|",
        ]
        for r in orphans_no_impl:
            issues = r.get("issues", [])
            problem_parts = []
            if "no_impl" in issues:
                problem_parts.append("нет реализации")
            if "no_test" in issues:
                problem_parts.append("нет теста")
            problem = ", ".join(problem_parts)
            lines.append(f"| `{r['id']}` | {r['type']} | {r['title']} | {r['status']} | {problem} |")
        lines.append("")

        lines += [
            "> **Нет реализации:** добавьте связь `satisfies` (компонент или требование, которое его реализует) либо `derives` (дочернее требование)",
            "> **Нет теста:** добавьте связь `verifies` (тест-кейс)",
            "",
        ]

    if fully_covered:
        lines += [
            "## 🟢 Полностью покрытые элементы",
            "",
            "| ID | Тип | Название | Связей |",
            "|----|-----|----------|--------|",
        ]
        for r in fully_covered:
            lines.append(f"| `{r['id']}` | {r['type']} | {r['title']} | {r['links_count']} |")
        lines.append("")

    if archived:
        # This section is the reason `deprecate_requirements` says "run check_coverage
        # next": a link left pointing at an archived node still LOOKS like a
        # justification on every other surface. Naming the live nodes that still lean
        # on it is the whole answer the analyst came for.
        lines += [
            "## 📦 Требования в архиве (5.2)",
            "",
            "> Хранятся для аудита — на платформе ничего не удаляется. Они показаны и "
            "посчитаны, но покрытием **не** считаются: требование в архиве не является "
            "доказательством того, что что-то обосновано, реализовано или проверено.",
            "",
            "| ID | Тип | Название | Статус | На него всё ещё ссылаются |",
            "|----|-----|----------|--------|---------------------|",
        ]
        for req in archived:
            req_id = req["id"]
            referrers = archived_referrers[req_id]
            shown = ", ".join(f"`{r}`" for r in referrers) if referrers else "—"
            lines.append(
                f"| `{req_id}` | {req.get('type', '?')} | {req.get('title', '—')} "
                f"| {req.get('status', '—')} | {shown} |")
        lines.append("")
        if still_referenced:
            lines += [
                f"> ⚠️ **На требования в архиве всё ещё ссылаются живые: "
                f"{len(still_referenced)} "
                f"{plural_ru(len(still_referenced), 'требование', 'требования', 'требований')}.** "
                f"Везде в других местах такие связи читаются как обычное обоснование — "
                f"перенаправьте их через `add_trace_link` либо отправьте в архив то, что "
                f"от них зависит.",
                "",
            ]

    lines += [
        "---",
        "",
        "## Рекомендации",
        "",
    ]

    # The verdict is built from what the body of this document actually found. It used
    # to be able to say "Coverage is complete" over a warning printed six lines above
    # it, and over a project whose every requirement had been archived — the empty-set
    # cutoff at the top stopped firing once archived nodes were kept in the selection,
    # and `fully_covered` is computed over the LIVE set, so "no orphans" was vacuously
    # true where there was nothing to have an orphan.
    actions = []
    if orphans_no_source:
        actions.append(
            f"⚠️ **Требования-сироты: {len(orphans_no_source)}** — закройте по ним "
            f"вопрос до приоритизации (5.3) и согласования (5.5).")
    if orphans_no_impl:
        actions.append(
            f"🔧 **Закройте пробелы** в {len(orphans_no_impl)} "
            f"{plural_ru(len(orphans_no_impl), 'требовании', 'требованиях', 'требованиях')}: "
            f"добавьте реализацию и/или тесты.")
    if still_referenced:
        actions.append(
            f"📦 **Перенаправьте или отправьте в архив связи, которые всё ещё указывают "
            f"на {len(still_referenced)} "
            f"{plural_ru(len(still_referenced), 'требование', 'требования', 'требований')} "
            f"в архиве:** "
            + list_with_cap(still_referenced, formatter=lambda i: f"`{i}`")
            + ". Доказательством они не являются, поэтому выше не засчитаны в покрытие.")

    if actions:
        lines += [f"{n}. {text}" for n, text in enumerate(actions, 1)]
    elif not live:
        lines.append(
            f"ℹ️ Все требования проекта в архиве ({len(archived)} из "
            f"{len(archived)}). Приоритизировать (5.3) и согласовывать (5.5) нечего, и это "
            f"не утверждение о том, что с трассировкой всё в порядке — верните в работу "
            f"то, что осталось в границах, через `update_requirement` (5.2).")
    else:
        lines.append("✅ Покрытие полное. Трассировка готова к 5.3 (приоритизация) и 5.5 (согласование).")

    content = "\n".join(lines)
    save_artifact(content, prefix="5_1_coverage_check", project_id=project_name)
    return content


# ---------------------------------------------------------------------------
# 5.1.5 — Экспорт матрицы трассировки в Markdown
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def export_traceability_matrix(
    project_name: str,
    filter_relation: str = "",
    filter_status: str = "",
    filter_type: str = "",
) -> str:
    """
    BABOK 5.1 — Генерирует Markdown-матрицу трассировки из JSON-репозитория.
    Используется для передачи стейкхолдерам, на ревью, в пакет утверждения 5.5.

    Args:
        project_name:      Название проекта.
        filter_relation:   Фильтр по типу связи: derives | depends | satisfies | verifies
                           Пустая строка — все связи.
        filter_status:     Фильтр по статусу требования: draft | confirmed | approved | deprecated
                           Пустая строка — все статусы.
        filter_type:       Фильтр по типу требования: business | stakeholder | solution | transition
                           Пустая строка — все типы.

    Returns:
        Markdown-матрица трассировки. Также сохраняется как артефакт.
    """
    logger.info(f"export_traceability_matrix: {project_name}, rel={filter_relation}, status={filter_status}")

    repo = _load_repo(project_name)

    requirements = repo["requirements"]
    if filter_type:
        requirements = [r for r in requirements if r.get("type") == filter_type]
    if filter_status == "approved":
        # `approved` is the one status value that is a durable FACT rather than a
        # position in the workflow, and it is not owned by this field: 7.3 overwrites
        # it with `validated` on the very requirements 5.5 approved. Filtering on the
        # literal silently dropped them from a matrix that goes into the 5.5 signing
        # package — the reader sees a shorter list and no indication anything is
        # missing. The durable answer is 5.5's own stored decisions; the literal is
        # kept as a fallback for projects with no approval records.
        # Role guard on the fallback: 5.4 writes status="approved" on the CR node
        # meaning "the change request was accepted", and a pre-migration 6.4 scope
        # node carried the same literal meaning "the scope is settled". Without the
        # guard both passed this filter and appeared in the approved-requirements
        # matrix — a document that goes into the 5.5 signing package. Same
        # one-literal-two-meanings class ADR-082 resolved for the type field.
        requirements = [
            r for r in requirements
            if r.get("type", "") not in ANALYSIS_NODE_TYPES
            and (has_been_approved(project_name, r.get("id", ""))
                 or r.get("status") == "approved")
        ]
    elif filter_status == "verified":
        # Same durable-fact reasoning as `approved`: 7.3/5.5 overwrite `verified` in the
        # shared status field, so the literal drops verified requirements from the matrix.
        requirements = [r for r in requirements
                        if has_passed_verification(repo, r.get("id", ""))]
    elif filter_status == "validated":
        # 5.5 (approved) / 5.4 (under_change) / a re-run 7.2 overwrite `validated`.
        requirements = [r for r in requirements
                        if has_been_validated(repo, r.get("id", ""))]
    elif filter_status:
        requirements = [r for r in requirements if r.get("status") == filter_status]

    req_ids = {r["id"] for r in requirements}

    links = repo["links"]
    if filter_relation:
        links = [lnk for lnk in links if lnk["relation"] == filter_relation]
    # Показываем только связи где хотя бы один конец в отфильтрованных требованиях
    if filter_type or filter_status:
        links = [lnk for lnk in links if lnk["from"] in req_ids or lnk["to"] in req_ids]

    rel_icons = {
        "derives": "⬇️ derives",
        "depends": "↔️ depends",
        "satisfies": "✔️ satisfies",
        "verifies": "🧪 verifies",
    }

    # Rendering order for the types 5.1 itself defines. It is an ORDER, not a filter:
    # any type not listed here still gets a section (see below). Driving the render
    # off a positive list meant every type added by a later chapter — 6.1's needs,
    # 6.2's goals, 6.3's risks, 5.4's change requests and all eight of 7.1's
    # specification types — was counted in the header and then never rendered. This
    # document goes into the 5.5 approval package, so the omission is silent and signed.
    type_order = ["business", "stakeholder", "solution", "transition", "test", "component"]
    type_labels = {
        "business": "Бизнес-требования",
        "stakeholder": "Требования стейкхолдеров",
        "solution": "Требования к решению",
        "transition": "Переходные требования",
        "test": "Тесты",
        "component": "Компоненты",
        "business_need": "Бизнес-потребности (6.1)",
        "business_goal": "Бизнес-цели (6.2)",
        "risk": "Риски (6.3)",
        "change_request": "Запросы на изменение (5.4)",
        "solution_scope": "Границы решения (6.4)",
        "functional": "Функциональные требования",
        "non_functional": "Нефункциональные требования",
        "business_rule": "Бизнес-правила",
        "user_story": "Пользовательские истории",
        "use_case": "Use Cases",
        "business_process": "Бизнес-процессы",
        "data_dictionary": "Словари данных",
        "erd": "Модели «сущность — связь»",
    }
    # Known types first, in the order above; then anything else, so a node type
    # introduced later is rendered under its own name instead of disappearing.
    present_types = {r.get("type") or "untyped" for r in requirements}
    render_order = [t for t in type_order if t in present_types]
    render_order += sorted(present_types - set(type_order))

    lines = [
        f"<!-- BABOK 5.1 — Матрица трассировки | Проект: {project_name} | {date.today()} -->",
        "",
        f"# 🗺️ Матрица трассировки требований",
        "",
        f"**Проект:** {project_name}  ",
        f"**Уровень формальности:** {repo.get('formality_level', 'Standard')}  ",
        f"**Фильтры:** тип={filter_type or 'все'}, статус={filter_status or 'все'}, связи={filter_relation or 'все'}  ",
        f"**Дата генерации:** {date.today()}",
        "",
        f"**Итого требований:** {len(requirements)} | **Связей:** {len(links)}",
        "",
    ]

    # Секция: требования по типам
    lines.append("## Требования")
    lines.append("")

    for req_type in render_order:
        type_reqs = [r for r in requirements
                     if (r.get("type") or "untyped") == req_type]
        if not type_reqs:
            continue
        label = type_labels.get(req_type, req_type)
        lines += [
            f"### {label}",
            "",
            "| ID | v | Название | Статус | Источник |",
            "|----|---|----------|--------|----------|",
        ]
        for r in sorted(type_reqs, key=lambda x: x["id"]):
            src = r.get("source_artifact", "")
            src_short = src.split("/")[-1] if src else "—"
            lines.append(
                f"| `{r['id']}` | {r.get('version','1.0')} | {r.get('title','—')} "
                f"| {r.get('status','—')} | {src_short} |"
            )
        lines.append("")

    # Секция: связи
    lines += [
        "## Связи трассировки",
        "",
        "| От | Тип связи | К | Обоснование | Добавлено |",
        "|----|-----------|---|-------------|-----------|",
    ]

    # Each end is labelled by asking the NODE, not by printing the id. The status is
    # already in the requirements table above, but a signatory reading the links
    # section saw `FR-001 satisfies BG-002` with no hint that BG-002 was retired last
    # month — the two halves of one document, and only a manual cross-reference
    # between them.
    for lnk in sorted(links, key=lambda x: (x.get("relation", ""), x.get("from", ""))):
        rel = rel_icons.get(lnk["relation"], lnk["relation"])
        rationale = lnk.get("rationale", "—")
        added = link_date(lnk)
        src = f"`{lnk['from']}`{archived_suffix(_find_req(repo, lnk['from']))}"
        dst = f"`{lnk['to']}`{archived_suffix(_find_req(repo, lnk['to']))}"
        lines.append(f"| {src} | {rel} | {dst} | {rationale} | {added} |")

    if not links:
        lines.append("| — | — | — | Связей пока нет | — |")

    lines += [
        "",
        "---",
        f"*Сгенерировано: {datetime.now().strftime('%d.%m.%Y %H:%M')}*  ",
        f"*Репозиторий: `{_repo_path(project_name)}`*",
    ]

    content = "\n".join(lines)
    save_artifact(content, prefix="5_1_traceability_matrix", project_id=project_name)
    return content


if __name__ == "__main__":
    mcp.run()
