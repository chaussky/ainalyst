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
from skills.common import save_artifact, logger, DATA_DIR

mcp = FastMCP("BABOK_Requirements_Traceability")

REPO_FILENAME = "traceability_repo.json"


# ---------------------------------------------------------------------------
# Утилиты работы с репозиторием
# ---------------------------------------------------------------------------

def _repo_path(project_name: str) -> str:
    """Возвращает путь к JSON-файлу репозитория для проекта."""
    safe_name = project_name.lower().replace(" ", "_")
    return os.path.join(DATA_DIR, f"{safe_name}_{REPO_FILENAME}")


def _load_repo(project_name: str) -> dict:
    """Загружает репозиторий из JSON. Возвращает пустую структуру если не существует."""
    path = _repo_path(project_name)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
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
    os.makedirs(DATA_DIR, exist_ok=True)
    repo["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)
    logger.info(f"Репозиторий трассировки обновлён: {path}")
    return path


def _find_req(repo: dict, req_id: str) -> Optional[dict]:
    """Находит требование по ID."""
    for r in repo["requirements"]:
        if r["id"] == req_id:
            return r
    return None


def _find_links(repo: dict, req_id: str) -> list:
    """Возвращает все связи где req_id фигурирует как from или to."""
    return [lnk for lnk in repo["links"]
            if lnk["from"] == req_id or lnk["to"] == req_id]


# ---------------------------------------------------------------------------
# 5.1.1 — Инициализация репозитория трассировки
# ---------------------------------------------------------------------------

@mcp.tool()
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

    try:
        requirements = json.loads(requirements_json)
    except json.JSONDecodeError as e:
        return f"❌ Ошибка парсинга requirements_json: {e}"

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
        req.setdefault("version", "1.0")
        req.setdefault("status", "draft")
        req.setdefault("source_artifact", "")
        req["added"] = str(date.today())

        if req_id in existing_ids:
            # Обновляем существующее
            for i, r in enumerate(repo["requirements"]):
                if r["id"] == req_id:
                    repo["requirements"][i] = req
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
    save_artifact(content, prefix="5_1_traceability_init")
    return content + f"\n\n✅ Репозиторий сохранён: `{repo_path}`"


# ---------------------------------------------------------------------------
# 5.1.2 — Добавление / удаление связи между артефактами
# ---------------------------------------------------------------------------

@mcp.tool()
def add_trace_link(
    project_name: str,
    from_id: str,
    to_id: str,
    relation: Literal["derives", "depends", "satisfies", "verifies"],
    rationale: str,
    remove: bool = False,
) -> str:
    """
    BABOK 5.1 — Добавляет или удаляет связь между двумя артефактами в репозитории.

    Семантика связей:
      - derives:   from вытекает из to (иерархия сверху вниз: BR → SR → FR)
      - depends:   from не имеет смысла без to (горизонтальная зависимость)
      - satisfies: from (компонент) реализует to (требование) — направление: COMP satisfies FR
      - verifies:  from (тест) проверяет to (требование) — направление: TC verifies FR

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

    # Добавляем связь
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
        "",
        f"**Обоснование:** {rationale or '—'}",
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
            if depth == "full" and neighbor_id not in visited:
                queue.append(neighbor_id)

    # Деduplication по id (оставляем первое вхождение)
    seen_ids: set = set()
    unique_affected = []
    for item in affected:
        if item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            unique_affected.append(item)

    # Группируем по типу связи
    by_relation: dict = {
        "derives": [],
        "depends": [],
        "satisfies": [],
        "verifies": [],
    }
    for item in unique_affected:
        rel = item["relation"]
        if rel in by_relation:
            by_relation[rel].append(item)

    rel_labels = {
        "derives": ("⬇️ Производные требования", "Пересмотреть — они вытекают из изменённого"),
        "depends": ("↔️ Зависимые требования", "Проверить — могут потерять смысл без изменённого"),
        "satisfies": ("✔️ Компоненты реализации", "Оценить объём доработки кода / дизайна"),
        "verifies": ("🧪 Тесты", "Перезапустить или обновить тест-кейсы"),
    }

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
    save_artifact(content, prefix="5_1_impact_analysis")
    return content


# ---------------------------------------------------------------------------
# 5.1.4 — Аудит покрытия
# ---------------------------------------------------------------------------

@mcp.tool()
def check_coverage(
    project_name: str,
    filter_type: str = "",
) -> str:
    """
    BABOK 5.1 — Аудит покрытия трассировки. Находит orphan-требования и дыры.

    Что ищет:
      🔴 Orphan без источника  — нет derives-связи вверх (нет бизнес-обоснования)
      🟡 Нет реализации        — нет derives/satisfies-связи вниз (не реализовано)
      🟡 Нет теста             — нет verifies-связи (не верифицировано)
      🟢 Полное покрытие       — есть источник + реализация + тест

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

    # Исключаем архивные статусы — они не должны попадать в аудит покрытия
    archive_statuses = {"deprecated", "superseded", "retired"}
    requirements = [r for r in repo["requirements"] if r.get("status") not in archive_statuses]
    if filter_type:
        requirements = [r for r in requirements if r.get("type") == filter_type]

    if not requirements:
        return f"ℹ️ Активных требований {'типа `' + filter_type + '`' if filter_type else ''} не найдено в репозитории `{project_name}`."

    orphans_no_source = []
    orphans_no_impl = []
    orphans_no_test = []
    fully_covered = []

    for req in requirements:
        req_id = req["id"]
        req_type = req.get("type", "")

        links = _find_links(repo, req_id)

        has_source = any(
            lnk["relation"] == "derives" and lnk["to"] == req_id
            for lnk in links
        )
        has_impl = any(
            (lnk["relation"] == "derives" and lnk["from"] == req_id) or
            (lnk["relation"] == "satisfies" and lnk["to"] == req_id)
            for lnk in links
        )
        has_test = any(
            lnk["relation"] == "verifies" and lnk["to"] == req_id
            for lnk in links
        )

        # Бизнес-требования — у них нет «источника» выше, это нормально
        if req_type == "business":
            has_source = True

        issues = []
        if not has_source:
            issues.append("no_source")
        if not has_impl:
            issues.append("no_impl")
        # Тест проверяем только в Standard и Full
        if formality in ("Standard", "Full") and not has_test:
            # Тест не нужен для business/stakeholder требований напрямую
            if req_type in ("solution", "transition"):
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

    total = len(requirements)
    covered_pct = round(len(fully_covered) / total * 100) if total else 0

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
        f"| 🔴 Нет источника (orphan) | {len(orphans_no_source)} | {round(len(orphans_no_source)/total*100) if total else 0}% |",
        f"| 🟡 Пробелы в покрытии | {len(orphans_no_impl)} | {round(len(orphans_no_impl)/total*100) if total else 0}% |",
        f"| **Всего** | **{total}** | 100% |",
        "",
    ]

    if orphans_no_source:
        lines += [
            "## 🔴 Требования без источника (orphan)",
            "",
            "> **Диагноз:** нет `derives`-связи вверх. Неизвестно из какой бизнес-потребности возникло.",
            "> **Действие:** найти бизнес-обоснование через `add_trace_link`, или заморозить.",
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
            "> **Нет реализации:** добавить `satisfies`-связь (компонент) или `derives`-связь (дочернее требование)",
            "> **Нет теста:** добавить `verifies`-связь (тест-кейс)",
            "",
        ]

    if fully_covered:
        lines += [
            "## 🟢 Полностью покрытые требования",
            "",
            "| ID | Тип | Название | Связей |",
            "|----|-----|----------|--------|",
        ]
        for r in fully_covered:
            lines.append(f"| `{r['id']}` | {r['type']} | {r['title']} | {r['links_count']} |")
        lines.append("")

    lines += [
        "---",
        "",
        "## Рекомендации",
        "",
    ]

    if orphans_no_source:
        lines.append(f"1. ⚠️ **Закрыть {len(orphans_no_source)} orphan-требований** перед приоритизацией (5.3) и утверждением (5.5).")
    if orphans_no_impl:
        lines.append(f"2. 🔧 **Заполнить пробелы** в {len(orphans_no_impl)} требованиях: добавить реализацию и/или тесты.")
    if not orphans_no_source and not orphans_no_impl:
        lines.append("✅ Покрытие полное. Трассировка готова для 5.3 (Приоритизация) и 5.5 (Утверждение).")

    content = "\n".join(lines)
    save_artifact(content, prefix="5_1_coverage_check")
    return content


# ---------------------------------------------------------------------------
# 5.1.5 — Экспорт матрицы трассировки в Markdown
# ---------------------------------------------------------------------------

@mcp.tool()
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
    if filter_status:
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

    type_order = ["business", "stakeholder", "solution", "transition", "test", "component"]
    type_labels = {
        "business": "Бизнес-требования",
        "stakeholder": "Требования стейкхолдеров",
        "solution": "Требования к решению",
        "transition": "Переходные требования",
        "test": "Тесты",
        "component": "Компоненты",
    }

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

    for req_type in type_order:
        type_reqs = [r for r in requirements if r.get("type") == req_type]
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

    for lnk in sorted(links, key=lambda x: (x.get("relation", ""), x.get("from", ""))):
        rel = rel_icons.get(lnk["relation"], lnk["relation"])
        rationale = lnk.get("rationale", "—")
        added = lnk.get("added", "—")
        lines.append(
            f"| `{lnk['from']}` | {rel} | `{lnk['to']}` | {rationale} | {added} |"
        )

    if not links:
        lines.append("| — | — | — | Связей пока нет | — |")

    lines += [
        "",
        "---",
        f"*Сгенерировано: {datetime.now().strftime('%d.%m.%Y %H:%M')}*  ",
        f"*Репозиторий: `{_repo_path(project_name)}`*",
    ]

    content = "\n".join(lines)
    save_artifact(content, prefix="5_1_traceability_matrix")
    return content


if __name__ == "__main__":
    mcp.run()
