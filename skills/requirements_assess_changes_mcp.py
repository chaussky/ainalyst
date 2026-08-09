"""
BABOK 5.4 — Assess Requirements Changes
MCP-инструменты для оценки изменений требований (Change Request pipeline).

Инструменты:
  - open_cr          — зарегистрировать CR в репозитории 5.1
  - run_cr_impact    — BFS-анализ влияния, создать modifies-связи
  - score_cr         — скоринг по 5 осям + рекомендация
  - resolve_cr       — зафиксировать решение, обновить статусы, сгенерировать Decision Record

Хранение:
  - CR хранится как узел типа "change_request" в {project}_traceability_repo.json (5.1)
  - Связи CR→требования: тип "modifies"
  - CR Decision Record сохраняется через save_artifact

Integration:
  In:  5.1 repository (graph), 5.2 attributes (stability), 5.3 priorities
  Out: CR Decision Record → 4.4 (communication), 5.5 (audit)
       under_change status on affected requirements → 5.2 (content update)

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date, datetime
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import (write_json_artifact,
    save_artifact, logger, DATA_DIR, data_path, normalize_project_id,
    BUSINESS_NODE_TYPES, NON_REQUIREMENT_NODE_TYPES,
    read_json_artifact, guard_artifact_errors,
    load_ba_plan, planned_decision_makers, is_planned_decision_maker,
    planned_party_status, PARTY_UNPLANNED,
    planned_escalation_path,
)

mcp = FastMCP("BABOK_Requirements_Assess_Changes")

REPO_FILENAME = "traceability_repo.json"

# Типы связей — исходные из 5.1 + новый modifies для CR
VALID_RELATIONS = {"derives", "depends", "satisfies", "verifies", "modifies"}

# CR Score пороги для предварительного вердикта
SCORE_APPROVE = 8.0
SCORE_MODIFY = 4.0
SCORE_DEFER = 1.0

# Веса осей для формулы скоринга
# Score = Benefit*2 + Urgency*1.5 + Impact*1 - Cost*1.5 - Schedule_Risk*1
SCORE_WEIGHTS = {
    "benefit": 2.0,
    "urgency": 1.5,
    "impact": 1.0,
    "cost": -1.5,          # High cost=3 → штраф -4.5; Low cost=1 → штраф -1.5
    "schedule_risk": -1.0, # High risk=3 → штраф -3.0; Low risk=1 → штраф -1.0
}

# Маппинг текстовых оценок в числа
BENEFIT_MAP = {"High": 3, "Medium": 2, "Low": 1}
COST_MAP = {"High": 3, "Medium": 2, "Low": 1}   # High cost = высокий штраф (не инвертировано)
URGENCY_MAP = {"Critical": 3, "High": 2, "Normal": 1}
IMPACT_MAP = {"High": 3, "Medium": 2, "Low": 1}
SCHEDULE_MAP = {"High": 3, "Medium": 2, "Low": 1}  # High risk = high penalty (matches the formula)


# ---------------------------------------------------------------------------
# Утилиты — файловый слой
# ---------------------------------------------------------------------------

def _repo_path(project_name: str) -> str:
    safe = normalize_project_id(project_name)
    return data_path(project_name, f"{safe}_{REPO_FILENAME}")


def _load_repo(project_name: str) -> dict:
    path = _repo_path(project_name)
    if os.path.exists(path):
        # Raises CorruptArtifactError, converted to a ❌ line by guard_artifact_errors
        # at the tool boundary. A bare json.load here made a damaged file a protocol
        # error in every downstream tool.
        return read_json_artifact(path, "5.1 traceability repository")
    return {"project": project_name, "requirements": [], "links": [], "history": []}


def _save_repo(project_name: str, repo: dict) -> None:
    path = _repo_path(project_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    repo["updated"] = str(date.today())
    write_json_artifact(path, repo)


def _find_node(repo: dict, node_id: str) -> Optional[dict]:
    """Находит узел (требование или CR) по ID."""
    for r in repo["requirements"]:
        if r["id"] == node_id:
            return r
    return None


def _find_links(repo: dict, node_id: str) -> list:
    """Возвращает все связи где node_id фигурирует как from или to."""
    return [lnk for lnk in repo["links"]
            if lnk["from"] == node_id or lnk["to"] == node_id]


def _bfs_impact(repo: dict, start_ids: list) -> list:
    """
    BFS-обход графа от списка стартовых узлов.
    Возвращает список затронутых узлов с типами связей.
    """
    visited = set(start_ids)
    queue = list(start_ids)
    affected = []

    while queue:
        current_id = queue.pop(0)
        links = _find_links(repo, current_id)
        for lnk in links:
            neighbor_id = lnk["to"] if lnk["from"] == current_id else lnk["from"]
            relation = lnk.get("relation", "unknown")
            # Не обходим modifies-связи рекурсивно (CR→req, не req→req)
            if relation == "modifies":
                continue
            if neighbor_id not in visited:
                visited.add(neighbor_id)
                neighbor = _find_node(repo, neighbor_id)
                if neighbor:
                    affected.append({
                        "id": neighbor_id,
                        "title": neighbor.get("title", "—"),
                        "type": neighbor.get("type", "unknown"),
                        "relation": relation,
                        "via": current_id,
                        "status": neighbor.get("status", "unknown"),
                        "version": neighbor.get("version", "1.0"),
                        "stability": neighbor.get("stability", "Unknown"),
                        "priority": neighbor.get("priority", "—"),
                    })
                    # Report the business node as affected, but do NOT expand
                    # through it. Once every requirement links to the objectives it
                    # serves (7.1), an objective is a hub: continuing the walk
                    # returns down to every sibling serving the same objective, so
                    # a CR targeting ONE requirement reported the whole graph as
                    # affected and its Impact/Schedule Risk axes maxed out — the
                    # better the traceability, the worse the CR score. 5.1's
                    # run_impact_analysis applies the same stop; its fix note
                    # already named 5.4 as a consumer of the inflated count.
                    if neighbor.get("type", "") not in BUSINESS_NODE_TYPES:
                        queue.append(neighbor_id)

    return affected


def _calc_score(benefit: int, cost: int, urgency: int,
                impact: int, schedule_risk: int) -> float:
    """Рассчитывает CR Score по формуле с весами."""
    return (
        benefit * SCORE_WEIGHTS["benefit"]
        + urgency * SCORE_WEIGHTS["urgency"]
        + impact * SCORE_WEIGHTS["impact"]
        + cost * SCORE_WEIGHTS["cost"]              # High cost=3 → -4.5 (штраф)
        + schedule_risk * SCORE_WEIGHTS["schedule_risk"]  # High risk=3 → -3.0 (штраф)
    )


def _score_verdict(score: float) -> str:
    if score >= SCORE_APPROVE:
        return "✅ Approve"
    elif score >= SCORE_MODIFY:
        return "🟡 Modify"
    elif score >= SCORE_DEFER:
        return "⏳ Defer"
    else:
        return "❌ Reject"


def _get_version_minor(version_str: str) -> int:
    """Извлекает минорную версию из строки '1.3' → 3."""
    try:
        parts = str(version_str).split(".")
        return int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return 0


# ---------------------------------------------------------------------------
# 5.4.1 — Открыть CR
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def open_cr(
    project_name: str,
    cr_id: str,
    title: str,
    description: str,
    initiator: str,
    cr_type: Literal["new_requirement", "change_existing", "delete", "architectural"],
    formality: Literal["standard", "high"],
    target_req_ids_json: str,
    urgency: Literal["Critical", "High", "Normal"] = "Normal",
    project_phase: Literal["discovery", "development", "pre_release", "post_release"] = "development",
    related_cr_ids_json: str = "[]",
    regulatory: bool = False,
) -> str:
    """
    BABOK 5.4 — Шаг 1: Зарегистрировать Change Request в репозитории 5.1.

    CR создаётся как узел типа "change_request". Связи с целевыми требованиями
    добавляются на шаге run_cr_impact (тип 'modifies').

    Args:
        project_name:          Название проекта.
        cr_id:                 Уникальный ID CR. Рекомендуемый формат: CR-001, CR-002.
        title:                 Краткое название CR (до 80 символов).
        description:           Развёрнутое описание что и зачем нужно изменить.
        initiator:             Кто запросил CR (роль или имя стейкхолдера).
        cr_type:               Тип изменения:
                               - new_requirement: добавление нового требования
                               - change_existing: изменение существующего
                               - delete: удаление требования
                               - architectural: архитектурное изменение
        formality:             Уровень формальности оценки:
                               - standard: обычный CR
                               - high: Predictive-проект, близко к релизу, регуляторный
        target_req_ids_json:   JSON-список ID требований, которые CR затрагивает напрямую.
                               Пример: '["FR-001", "FR-003"]'
        urgency:               Срочность: Critical (регулятор/безопасность) / High / Normal.
        project_phase:         Фаза проекта (влияет на автоматический Schedule Risk).
        related_cr_ids_json:   JSON-список ID связанных CR (если несколько CR затрагивают
                               одни и те же требования). Пример: '["CR-001"]'
        regulatory:            True если CR вызван изменением законодательства или норматива.
                               Автоматически устанавливает urgency = Critical.

    Returns:
        Подтверждение регистрации CR с инструкцией по следующему шагу.
    """
    logger.info(f"open_cr: {cr_id} / {project_name}")

    # Parse JSON parameters. Shape, not just syntax: a scalar/object where a list of
    # ids is expected must return a readable "❌", not a TypeError escaping the tool.
    from skills.common import parse_json_str_list
    target_req_ids, shape_error = parse_json_str_list(
        target_req_ids_json, "target_req_ids_json")
    if shape_error:
        return shape_error

    related_cr_ids, rel_error = parse_json_str_list(
        related_cr_ids_json, "related_cr_ids_json")
    if rel_error:
        return rel_error

    # Регуляторный CR → всегда Critical urgency
    if regulatory:
        urgency = "Critical"

    repo = _load_repo(project_name)

    # Проверка: CR с таким ID уже существует?
    if _find_node(repo, cr_id):
        return (
            f"⚠️ CR `{cr_id}` уже существует в репозитории проекта `{project_name}`.\n"
            f"Используйте другой ID или проверьте существующий CR."
        )

    # Проверка: целевые требования существуют?
    missing = [rid for rid in target_req_ids if not _find_node(repo, rid)]
    if missing:
        return (
            f"⚠️ Следующие требования не найдены в репозитории: {missing}\n"
            f"Проверьте ID или добавьте требования через `init_traceability_repo` (5.1)."
        )

    # Создаём CR-узел
    cr_node = {
        "id": cr_id,
        "type": "change_request",
        "title": title,
        "description": description,
        "initiator": initiator,
        "cr_type": cr_type,
        "formality": formality,
        "urgency": urgency,
        "project_phase": project_phase,
        "regulatory": regulatory,
        "target_req_ids": target_req_ids,
        "related_cr_ids": related_cr_ids,
        "status": "open",
        "opened_date": str(date.today()),
        "impact_analysis": None,
        "score": None,
        "decision": None,
    }

    repo["requirements"].append(cr_node)

    # История
    repo.setdefault("history", []).append({
        "date": str(date.today()),
        "action": "cr_opened",
        "cr_id": cr_id,
        "initiator": initiator,
    })

    _save_repo(project_name, repo)

    # Предупреждения
    warnings = []
    if project_phase == "pre_release":
        warnings.append("⚠️ Проект в фазе pre_release — Schedule Risk будет автоматически повышен.")
    if regulatory:
        warnings.append("⚠️ Регуляторный CR: Urgency = Critical, Reject невозможен.")
    if related_cr_ids:
        warnings.append(f"ℹ️ Связан с CR: {related_cr_ids} — рекомендуется оценивать совместно.")

    lines = [
        f"<!-- BABOK 5.4 — Open CR, Проект: {project_name}, CR: {cr_id}, Дата: {date.today()} -->",
        "",
        f"## ✅ CR зарегистрирован: {cr_id}",
        "",
        f"**Название:** {title}",
        f"**Тип:** {cr_type} | **Формальность:** {formality} | **Срочность:** {urgency}",
        f"**Инициатор:** {initiator}",
        f"**Целевые требования:** {', '.join(target_req_ids)}",
        f"**Фаза проекта:** {project_phase}",
        "",
    ]

    if warnings:
        lines += ["### Предупреждения", ""] + warnings + [""]

    lines += [
        "---",
        "",
        "## ➡️ Следующий шаг — Шаг 2: Анализ влияния",
        "",
        f"Вызовите `run_cr_impact` с параметрами:",
        f"  - `project_name`: \"{project_name}\"",
        f"  - `cr_id`: \"{cr_id}\"",
        "",
        "Инструмент выполнит BFS-обход графа 5.1 и покажет все затронутые требования.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 5.4.2 — Анализ влияния
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def run_cr_impact(
    project_name: str,
    cr_id: str,
) -> str:
    """
    BABOK 5.4 — Шаг 2: BFS-анализ влияния CR через граф трассировки 5.1.

    Обходит граф от целевых требований CR, выявляет все затронутые узлы.
    Создаёт связи типа 'modifies' от CR к целевым требованиям.
    Автоматически рассчитывает технические оси Impact и Schedule Risk.

    Args:
        project_name:  Название проекта.
        cr_id:         ID ранее открытого CR (из open_cr).

    Returns:
        Отчёт о влиянии: затронутые требования по типам связей,
        автоматические оценки Impact и Schedule Risk, предупреждения.
    """
    logger.info(f"run_cr_impact: {cr_id} / {project_name}")

    repo = _load_repo(project_name)
    cr = _find_node(repo, cr_id)

    if not cr:
        return f"❌ CR `{cr_id}` не найден. Сначала выполните `open_cr`."

    if cr.get("type") != "change_request":
        return f"❌ `{cr_id}` не является CR. Убедитесь что передаёте ID CR, а не требования."

    if cr.get("status") != "open":
        return f"⚠️ CR `{cr_id}` имеет статус `{cr['status']}`. Анализ влияния применим только к открытым CR."

    target_req_ids = cr.get("target_req_ids", [])

    # Создаём modifies-связи CR → целевые требования
    existing_modifies = {
        lnk["to"] for lnk in repo["links"]
        if lnk.get("from") == cr_id and lnk.get("relation") == "modifies"
    }
    for req_id in target_req_ids:
        if req_id not in existing_modifies:
            repo["links"].append({
                "from": cr_id,
                "to": req_id,
                "relation": "modifies",
                # The matrix renders every link's rationale; an empty one printed
                # an em-dash in a document that goes into the signing package.
                "rationale": f"CR {cr_id} modifies {req_id}",
                "added_date": str(date.today()),
            })

    # BFS-обход от целевых требований
    affected = _bfs_impact(repo, target_req_ids)

    # Группировка затронутых по типу связи
    by_relation: dict = {}
    for item in affected:
        rel = item["relation"]
        by_relation.setdefault(rel, []).append(item)

    # Автоматический расчёт Impact
    total_affected = len(affected) + len(target_req_ids)
    if total_affected >= 8:
        impact_auto = "High"
        impact_score = 3
    elif total_affected >= 3:
        impact_auto = "Medium"
        impact_score = 2
    else:
        impact_auto = "Low"
        impact_score = 1

    # Automatic Schedule Risk calculation.
    # Non-inverted (High risk = 3): the formula subtracts ScheduleRisk*1, so a higher
    # risk value must yield a bigger penalty. High risk=3 → -3.0, Low risk=1 → -1.0.
    project_phase = cr.get("project_phase", "development")
    if project_phase == "pre_release":
        schedule_auto = "High"
        schedule_score = 3
    elif total_affected >= 8 or project_phase == "post_release":
        schedule_auto = "High"
        schedule_score = 3
    elif total_affected >= 3:
        schedule_auto = "Medium"
        schedule_score = 2
    else:
        schedule_auto = "Low"
        schedule_score = 1

    # Предупреждения: волатильные требования
    # Проверяем как affected (BFS), так и сами target_req_ids
    target_nodes = [_find_node(repo, rid) for rid in target_req_ids]
    target_nodes = [n for n in target_nodes if n]
    all_for_volatile = {item["id"]: item for item in affected}
    for n in target_nodes:
        all_for_volatile[n["id"]] = n
    volatile_reqs = [
        item for item in all_for_volatile.values()
        if _get_version_minor(item.get("version", "1.0")) >= 3
    ]

    # Предупреждения: конфликты с приоритетами
    priority_conflicts = []
    won_t_targets = [
        _find_node(repo, rid) for rid in target_req_ids
        if _find_node(repo, rid) and _find_node(repo, rid).get("priority") == "Won't"
    ]
    if won_t_targets:
        priority_conflicts = [r["id"] for r in won_t_targets if r]

    # Проверка трассировки к BR
    def _has_br_path(repo, req_id, visited=None):
        """Does this requirement trace UP to a business root?

        Two axes matter and both used to be wrong:
          - terminal node type: real roots are `business_goal` (6.2) and `business_need`
            (6.1), not only the legacy `business` — the class behind findings 7.3-A/7.4-B;
          - relation: 7.1 links a requirement to an objective with `satisfies`,
            so a derives-only walk cannot see those links at all.
        Both relations point from=child/implementer -> to=parent/goal, so the walk always
        follows `to`.
        """
        if visited is None:
            visited = set()
        if req_id in visited:
            return False
        visited.add(req_id)
        node = _find_node(repo, req_id)
        if node and node.get("type") in BUSINESS_NODE_TYPES:
            return True
        for lnk in repo["links"]:
            if lnk.get("from") == req_id and lnk.get("relation") in ("derives", "satisfies"):
                if _has_br_path(repo, lnk["to"], visited):
                    return True
        return False

    no_br_trace = [
        rid for rid in target_req_ids
        if not _has_br_path(repo, rid)
    ]

    # Сохраняем результаты impact analysis в CR-узел
    impact_data = {
        "affected_count": total_affected,
        "affected_ids": [item["id"] for item in affected] + target_req_ids,
        "impact_auto": impact_auto,
        "impact_score": impact_score,
        "schedule_auto": schedule_auto,
        "schedule_score": schedule_score,
        "by_relation": {k: [i["id"] for i in v] for k, v in by_relation.items()},
        "volatile_req_ids": [item["id"] for item in volatile_reqs],
        "priority_conflicts": priority_conflicts,
        "no_br_trace": no_br_trace,
        "analysis_date": str(date.today()),
    }
    cr["impact_analysis"] = impact_data

    _save_repo(project_name, repo)

    # Формируем отчёт
    lines = [
        f"<!-- BABOK 5.4 — Impact Analysis, Проект: {project_name}, CR: {cr_id}, Дата: {date.today()} -->",
        "",
        f"## 🔍 Анализ влияния: {cr_id} — {cr['title']}",
        "",
        f"**Целевые требования:** {', '.join(target_req_ids)}",
        f"**Всего затронуто узлов:** {total_affected}",
        "",
        "### Автоматические оценки технических осей",
        "",
        f"| Ось | Значение | Основание |",
        f"|-----|----------|-----------|",
        f"| Impact | **{impact_auto}** | {total_affected} затронутых узлов |",
        f"| Schedule Risk | **{schedule_auto}** | Фаза: {project_phase}, масштаб: {total_affected} |",
        "",
    ]

    # The count above includes the CR's own targets; the breakdown below groups by link
    # type, and a target has no link to itself, so it fell out of every group. "Total
    # nodes affected: 3" over a list of two — a reader adding up the rows gets a
    # different number from the one printed over them. Give the targets a row of their
    # own: more informative than shrinking the count, and the two agree again.
    if target_req_ids:
        lines += [
            "### Затронутые узлы по типу связи",
            "",
            f"**само изменение** — требований, которые переписывает CR: "
            f"{len(target_req_ids)}:",
        ]
        for rid in target_req_ids:
            node = _find_node(repo, rid)
            title = node.get("title", "—") if node else "—"
            lines.append(f"  - `{rid}` {title}")
        lines.append("")

    # Affected items by link type
    if affected:
        if not target_req_ids:
            lines += ["### Затронутые узлы по типу связи", ""]
        relation_comments = {
            "depends": "зависимые → могут потерять смысл",
            "verifies": "тесты → нужно пересмотреть или переписать",
            "satisfies": "реализующие компоненты / требования → нужно переделать",
            "derives": "дочерние требования → могут унаследовать изменение",
        }
        for rel, items in by_relation.items():
            comment = relation_comments.get(rel, "")
            lines.append(f"**`{rel}`** — {comment}")
            for item in items:
                priority_str = f" | приоритет: {item['priority']}" if item['priority'] != "—" else ""
                lines.append(
                    f"  - `{item['id']}` {item['title']} "
                    f"(v{item['version']}, {item['status']}{priority_str})"
                )
        lines.append("")
    else:
        lines += ["### Затронутые узлы", "", "✅ Изолированное изменение — связанных узлов не найдено.", ""]

    # Предупреждения
    warnings_section = []
    if no_br_trace:
        warnings_section.append(
            f"🔴 **Нет трассировки к бизнес-потребности:** {no_br_trace}\n"
            f"   CR должен трассироваться к BR. Уточните бизнес-обоснование."
        )
    if priority_conflicts:
        warnings_section.append(
            f"🔴 **Конфликт с приоритетами:** целевые требования {priority_conflicts} "
            f"имеют приоритет Won't. CR меняет это решение — требует явного пересмотра в 5.3."
        )
    if volatile_reqs:
        volatile_ids = [r["id"] for r in volatile_reqs]
        warnings_section.append(
            f"🟡 **Волатильные требования:** {volatile_ids} (версия 1.3+).\n"
            f"   Нестабильное требование + CR = двойная неопределённость."
        )

    if warnings_section:
        lines += ["### ⚠️ Предупреждения", ""] + warnings_section + [""]

    lines += [
        "---",
        "",
        "## ➡️ Следующий шаг — Шаг 3: Скоринг CR",
        "",
        "Технические оси заполнены автоматически. Введите бизнес-оси и вызовите `score_cr`:",
        "",
        f"  - `project_name`: \"{project_name}\"",
        f"  - `cr_id`: \"{cr_id}\"",
        f"  - `benefit`: High / Medium / Low — что получает бизнес?",
        f"  - `cost`: Low / Medium / High — полная стоимость включая альтернативные затраты",
        f"  - `urgency`: {cr.get('urgency', 'Normal')} (уже задан при open_cr, можно изменить)",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 5.4.3 — Скоринг CR
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def score_cr(
    project_name: str,
    cr_id: str,
    benefit: Literal["High", "Medium", "Low"],
    cost: Literal["Low", "Medium", "High"],
    urgency: Literal["Critical", "High", "Normal"] = "Normal",
    ba_notes: str = "",
) -> str:
    """
    BABOK 5.4 — Шаг 3: Скоринг CR по пяти осям + рекомендация.

    Технические оси (Impact, Schedule Risk) берутся из run_cr_impact.
    Бизнес-оси (Benefit, Cost, Urgency) вводит BA.

    Формула: Score = Benefit*2 + Urgency*1.5 + Impact*1 - Cost*1.5 - ScheduleRisk*1

    Пороги:
      ≥ 8.0 → Approve | 4.0–7.9 → Modify | 1.0–3.9 → Defer | < 1.0 → Reject

    Args:
        project_name:  Название проекта.
        cr_id:         ID CR (должен пройти run_cr_impact).
        benefit:       Выгода для бизнеса: High / Medium / Low.
        cost:          Полная стоимость реализации (включая альтернативные затраты):
                       Low / Medium / High.
        urgency:       Срочность (можно переопределить значение из open_cr):
                       Critical / High / Normal.
        ba_notes:      Дополнительный контекст от BA для обоснования рекомендации.

    Returns:
        CR Score, предварительный вердикт формулы, текстовая рекомендация,
        результаты автоматических проверок, инструкция по следующему шагу.
    """
    logger.info(f"score_cr: {cr_id} / {project_name}")

    repo = _load_repo(project_name)
    cr = _find_node(repo, cr_id)

    if not cr:
        return f"❌ CR `{cr_id}` не найден. Сначала выполните `open_cr`."

    if cr.get("type") != "change_request":
        return f"❌ `{cr_id}` не является CR."

    if not cr.get("impact_analysis"):
        return (
            f"❌ Impact analysis не выполнен для CR `{cr_id}`.\n"
            f"Сначала выполните `run_cr_impact`."
        )

    impact_data = cr["impact_analysis"]

    # Числовые значения осей
    benefit_n = BENEFIT_MAP[benefit]
    cost_n = COST_MAP[cost]          # High cost=3 → penalty via the negative weight
    urgency_n = URGENCY_MAP[urgency]
    impact_n = impact_data["impact_score"]
    schedule_n = impact_data["schedule_score"]  # High risk=3, Low risk=1 (penalty via negative weight)

    # Расчёт скора
    score = _calc_score(benefit_n, cost_n, urgency_n, impact_n, schedule_n)
    score = round(score, 1)
    verdict = _score_verdict(score)

    # Регуляторный CR — Reject невозможен
    regulatory = cr.get("regulatory", False)
    if regulatory and score < SCORE_DEFER:
        verdict = "⏳ Defer (Reject невозможен — регуляторный CR)"

    # Автоматические проверки
    checks = []
    no_br_trace = impact_data.get("no_br_trace", [])
    priority_conflicts = impact_data.get("priority_conflicts", [])
    volatile_reqs = impact_data.get("volatile_req_ids", [])

    if no_br_trace:
        checks.append(f"🔴 Нет трассировки к BR: {no_br_trace} — уточните бизнес-обоснование")
    if priority_conflicts:
        checks.append(f"🔴 Конфликт с приоритетами Won't: {priority_conflicts} — требует пересмотра в 5.3")
    if volatile_reqs:
        checks.append(f"🟡 Волатильные требования в зоне влияния: {volatile_reqs}")

    # Текстовая рекомендация (контекстная)
    recommendation_parts = []

    if score >= SCORE_APPROVE:
        recommendation_parts.append(
            f"CR демонстрирует высокую ценность (Benefit: {benefit}) при приемлемой стоимости "
            f"(Cost: {cost}). Масштаб влияния {impact_data['impact_auto']} ({impact_data['affected_count']} узлов) "
            f"управляем."
        )
        if urgency == "Critical":
            recommendation_parts.append("Критическая срочность дополнительно обосновывает немедленное принятие.")
    elif score >= SCORE_MODIFY:
        recommendation_parts.append(
            f"CR имеет потенциал, но текущий баланс ценность/стоимость требует пересмотра. "
            f"Рассмотрите возможность сужения скоупа для снижения Cost или Schedule Risk."
        )
        if impact_data["impact_auto"] == "High":
            recommendation_parts.append(
                f"Масштаб влияния высокий ({impact_data['affected_count']} узлов) — "
                f"возможно имеет смысл разбить CR на несколько меньших."
            )
    elif score >= SCORE_DEFER:
        recommendation_parts.append(
            f"CR не обоснован для текущей итерации. Ценность ({benefit}) не перекрывает "
            f"стоимость ({cost}) и риск графика ({impact_data['schedule_auto']})."
        )
        recommendation_parts.append("Рекомендуется вернуться к CR в следующей итерации с уточнённым обоснованием.")
    else:
        recommendation_parts.append(
            f"Затраты на реализацию CR значительно превышают ожидаемую ценность. "
            f"Стоимость: {cost}, риск по срокам: {impact_data['schedule_auto']}, выгода: {benefit}."
        )
        if not regulatory:
            recommendation_parts.append("Рекомендуется отклонить с явным rationale для audit trail.")

    if ba_notes:
        recommendation_parts.append(f"\n**Контекст от BA:** {ba_notes}")

    if checks:
        recommendation_parts.append(
            "\n**Внимание:** обнаружены проблемы (см. автоматические проверки ниже), "
            "которые могут повлиять на финальное решение независимо от скора."
        )

    # Сохраняем скоринг в CR-узел
    score_data = {
        "benefit": benefit,
        "benefit_n": benefit_n,
        "cost": cost,
        "cost_n": cost_n,
        "urgency": urgency,
        "urgency_n": urgency_n,
        "impact_auto": impact_data["impact_auto"],
        "impact_n": impact_n,
        "schedule_auto": impact_data["schedule_auto"],
        "schedule_n": schedule_n,
        "total_score": score,
        "formula_verdict": verdict,
        "ba_notes": ba_notes,
        "scored_date": str(date.today()),
    }
    cr["score"] = score_data
    cr["urgency"] = urgency  # обновляем urgency если переопределено

    _save_repo(project_name, repo)

    # Формируем отчёт
    lines = [
        f"<!-- BABOK 5.4 — CR Score, Проект: {project_name}, CR: {cr_id}, Score: {score}, Дата: {date.today()} -->",
        "",
        f"## 📊 Скоринг CR: {cr_id} — {cr['title']}",
        "",
        "### Оценки по осям",
        "",
        "| Ось | Значение | Числ. | Источник |",
        "|-----|----------|-------|----------|",
        f"| Benefit (×2.0) | {benefit} | {benefit_n} | BA |",
        f"| Cost (×1.5, инв.) | {cost} | {cost_n} | BA |",
        f"| Urgency (×1.5) | {urgency} | {urgency_n} | BA |",
        f"| Impact (×1.0) | {impact_data['impact_auto']} | {impact_n} | Авто (5.1) |",
        f"| Schedule Risk (×1.0, инв.) | {impact_data['schedule_auto']} | {schedule_n} | Авто (5.1) |",
        "",
        "### Результат",
        "",
        f"**CR Score: {score}**",
        "",
        f"**Предварительный вердикт формулы: {verdict}**",
        "",
        "### Рекомендация",
        "",
        " ".join(recommendation_parts),
        "",
    ]

    if checks:
        lines += ["### ⚠️ Автоматические проверки", ""] + [f"- {c}" for c in checks] + [""]

    # BABOK 3.3 .1 — NAME the planned decision authority instead of sending the BA off
    # to look up a plan nothing here had ever read. Without a plan the sentence stays
    # exactly as it was: it is still correct as an instruction, and silent degradation
    # is only acceptable when the tool says LESS, never when it invents a name.
    plan, plan_note = load_ba_plan(project_name)
    planned_deciders = planned_decision_makers(plan)
    decider_line = (
        f"Получи решение уполномоченного стейкхолдера — план governance 3.3 называет: "
        f"{', '.join(planned_deciders)}. Затем вызови `resolve_cr`:"
        if planned_deciders else
        "Получи решение уполномоченного стейкхолдера (из governance 3.3) и вызови "
        "`resolve_cr`:")

    lines += [
        "---",
        "",
        "## ➡️ Следующий шаг — Шаг 4: Зафиксировать решение",
        "",
        decider_line,
        "",
        f"  - `project_name`: \"{project_name}\"",
        f"  - `cr_id`: \"{cr_id}\"",
        f"  - `decision`: Approved / Approved_with_Modification / Deferred / Rejected",
        f"  - `decided_by`: кто принял решение",
        f"  - `rationale`: обоснование (обязательно для audit trail)",
    ]
    if plan_note:
        lines += ["", plan_note]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 5.4.4 — Зафиксировать решение
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def resolve_cr(
    project_name: str,
    cr_id: str,
    decision: Literal["Approved", "Approved_with_Modification", "Deferred", "Rejected"],
    decided_by: str,
    rationale: str,
    modification_notes: str = "",
) -> str:
    """
    BABOK 5.4 — Шаг 4: Зафиксировать решение по CR.

    При Approved / Approved_with_Modification:
      - Статус затронутых требований меняется на 'under_change'
      - Генерируется CR Decision Record (Markdown) через save_artifact

    При Deferred / Rejected:
      - Требования не изменяются
      - CR сохраняется в репозитории со статусом deferred/rejected (audit trail)
      - Генерируется CR Decision Record

    Args:
        project_name:         Project name.
        cr_id:                CR ID (must have gone through score_cr).
        decision:             Decision:
                              - Approved: accept the CR in full
                              - Approved_with_Modification: accept with a modified scope
                              - Deferred: postpone until a future iteration
                              - Rejected: reject
        decided_by:           Who made the decision (role/name). Cross-checked against
                              the decision makers planned in 3.3 — a mismatch is
                              flagged here and in the CR Decision Record, never
                              corrected and never blocked.
        rationale:            Rationale for the decision. Required — used in the audit trail.
        modification_notes:   Description of scope changes (only for Approved_with_Modification).

    Returns:
        CR Decision Record (Markdown), сохранённый через save_artifact.
        Статус обновлённых требований при Approved.
        Инструкции по следующим шагам.
    """
    logger.info(f"resolve_cr: {cr_id} / {decision} / {project_name}")

    repo = _load_repo(project_name)
    cr = _find_node(repo, cr_id)

    if not cr:
        return f"❌ CR `{cr_id}` не найден. Сначала выполните `open_cr`."

    if cr.get("type") != "change_request":
        return f"❌ `{cr_id}` не является CR."

    if not cr.get("score"):
        return (
            f"❌ Скоринг не выполнен для CR `{cr_id}`.\n"
            f"Сначала выполните `score_cr`."
        )

    # Проверка: регуляторный CR нельзя Reject
    if decision == "Rejected" and cr.get("regulatory"):
        return (
            f"❌ Регуляторный CR `{cr_id}` нельзя отклонить.\n"
            f"Регуляторные требования обязательны к исполнению. "
            f"Используйте Deferred если нужно отложить по срокам."
        )

    # Обновляем статус CR
    cr["status"] = decision.lower().replace("_with_modification", "_modified")
    cr["decision"] = {
        "verdict": decision,
        "decided_by": decided_by,
        "rationale": rationale,
        "modification_notes": modification_notes,
        "decision_date": str(date.today()),
    }

    # При Approved — меняем статус затронутых требований на under_change
    updated_reqs = []
    if decision in ("Approved", "Approved_with_Modification"):
        impact_data = cr.get("impact_analysis", {})
        affected_ids = impact_data.get("affected_ids", []) + cr.get("target_req_ids", [])
        affected_ids = list(set(affected_ids))  # дедупликация

        target_ids = set(cr.get("target_req_ids", []))
        for req_id in affected_ids:
            req = _find_node(repo, req_id)
            if not req:
                continue
            node_type = req.get("type", "")
            # `under_change` is a requirements-lifecycle status. Writing it on
            # every affected node erased statuses OTHER chapters own: 6.2's
            # `confirmed` on goals, 6.3's `identified` on risks, 6.4's `defined`
            # on the scope node (`status` is one field, last writer wins).
            # Exception: a legacy business-CLASS requirement the analyst NAMED as
            # the CR target is their explicit intent — `business` is both the
            # legacy root type and the BABOK requirement class, and silencing a
            # named target would drop a real requirement (the `solution` lesson).
            explicit_business_target = req_id in target_ids and node_type == "business"
            if node_type in NON_REQUIREMENT_NODE_TYPES and not explicit_business_target:
                continue
            old_status = req.get("status", "unknown")
            req["status"] = "under_change"
            req.setdefault("history", []).append({
                "date": str(date.today()),
                "action": "status_changed",
                "from": old_status,
                "to": "under_change",
                "reason": f"CR {cr_id} approved by {decided_by}",
            })
            updated_reqs.append(req_id)

    # История в репозитории
    repo.setdefault("history", []).append({
        "date": str(date.today()),
        "action": "cr_resolved",
        "cr_id": cr_id,
        "decision": decision,
        "decided_by": decided_by,
        "updated_requirements": updated_reqs,
    })

    _save_repo(project_name, repo)

    # Формируем CR Decision Record
    score_data = cr["score"]
    impact_data = cr.get("impact_analysis", {})

    decision_icon = {
        "Approved": "✅",
        "Approved_with_Modification": "✅🔧",
        "Deferred": "⏳",
        "Rejected": "❌",
    }.get(decision, "—")

    record_lines = [
        f"<!-- BABOK 5.4 — CR Decision Record, Проект: {project_name}, CR: {cr_id}, Дата: {date.today()} -->",
        "",
        f"# CR Decision Record: {cr_id}",
        f"**Проект:** {project_name}  ",
        f"**Дата:** {date.today()}  ",
        f"**Решение:** {decision_icon} {decision}  ",
        f"**Принял:** {decided_by}  ",
        "",
        "---",
        "",
        "## Описание CR",
        "",
        f"**Название:** {cr['title']}  ",
        f"**Тип:** {cr.get('cr_type', '—')} | **Инициатор:** {cr.get('initiator', '—')}  ",
        f"**Открыт:** {cr.get('opened_date', '—')}  ",
        f"**Регуляторный:** {'Да' if cr.get('regulatory') else 'Нет'}  ",
        "",
        f"{cr.get('description', '')}",
        "",
        "---",
        "",
        "## Анализ влияния",
        "",
        f"**Целевые требования:** {', '.join(cr.get('target_req_ids', []))}  ",
        f"**Всего затронуто узлов:** {impact_data.get('affected_count', '—')}  ",
        f"**Impact:** {impact_data.get('impact_auto', '—')} | **Schedule Risk:** {impact_data.get('schedule_auto', '—')}  ",
        "",
        "---",
        "",
        "## Скоринг",
        "",
        "| Ось | Значение |",
        "|-----|----------|",
        f"| Benefit | {score_data.get('benefit', '—')} |",
        f"| Cost | {score_data.get('cost', '—')} |",
        f"| Urgency | {score_data.get('urgency', '—')} |",
        f"| Impact | {score_data.get('impact_auto', '—')} |",
        f"| Schedule Risk | {score_data.get('schedule_auto', '—')} |",
        f"| **CR Score** | **{score_data.get('total_score', '—')}** |",
        f"| Вердикт формулы | {score_data.get('formula_verdict', '—')} |",
        "",
    ]

    if score_data.get("ba_notes"):
        record_lines += [f"**Контекст BA:** {score_data['ba_notes']}  ", ""]

    record_lines += [
        "---",
        "",
        "## Решение",
        "",
        f"**{decision_icon} {decision}**  ",
        f"**Принял:** {decided_by}  ",
        f"**Дата решения:** {date.today()}  ",
        "",
        f"**Обоснование:**  ",
        f"{rationale}",
        "",
    ]

    if modification_notes:
        record_lines += [
            f"**Изменения скоупа:**  ",
            f"{modification_notes}",
            "",
        ]

    # BABOK 3.3 .1/.2 — carry the planned decision authority and the escalation path
    # into the audit trail, and flag a decider who is not among them.
    #
    # `decided_by` is the BA's explicit statement and is NEVER rewritten: it is already
    # stored on the CR node and in the repository history above, and a Decision Record
    # that disagrees with the record it describes is worse than one that says nothing.
    # The match runs through the one shared `is_planned_decision_maker`, so this
    # warning and 5.5's cannot disagree about who counts as an authority.
    gov_plan, gov_note = load_ba_plan(project_name)
    planned_deciders = planned_decision_makers(gov_plan)
    escalation, escalation_source = planned_escalation_path(gov_plan)
    # Registry-bridged: the plan holds roles, `decided_by` is usually a person. Only
    # PARTY_UNPLANNED is a finding — with no registry the two labels cannot be
    # compared, and an audit record must not print a guess as a governance breach.
    unplanned_decider = planned_party_status(
        project_name, planned_deciders, decided_by) == PARTY_UNPLANNED

    if planned_deciders or escalation:
        record_lines += ["---", "", "## Governance (3.3)", ""]
        if planned_deciders:
            record_lines.append(
                f"**Запланированные полномочия на решение:** {', '.join(planned_deciders)}  ")
        if unplanned_decider:
            # Names the decider again rather than saying "them": directly under
            # "**Planned decision authority:** A, B" the pronoun resolves to A and B,
            # so "recorded as decided by them" stated the opposite of the fact — and
            # contradicted the `**Decided by:**` header three lines above it, in a
            # document written for an audit.
            record_lines.append(
                f"⚠️ `{decided_by}` среди них нет. Запись относит решение на "
                f"`{decided_by}` — ровно так, как оно было принято; либо обновите 3.3 "
                f"через `plan_ba_governance`, либо подтвердите полномочия этого "
                f"человека.  ")
        if escalation:
            record_lines.append(
                f"**Путь эскалации:** {escalation} *({escalation_source})*  ")
        record_lines.append("")

    # Next steps
    next_steps = []
    if decision in ("Approved", "Approved_with_Modification"):
        if updated_reqs:
            next_steps.append(
                f"1. Обновить содержание требований {updated_reqs} через `update_requirement` (5.2)"
            )
        next_steps.append("2. Проверить приоритеты затронутых требований в 5.3")
        next_steps.append("3. Отправить Decision Record стейкхолдерам через `prepare_communication_package` (4.4)")
        next_steps.append(f"4. Зафиксировать решение в Decision Log через `log_decision` (4.5)")
    elif decision == "Deferred":
        next_steps.append("1. Вернуться к CR в следующей итерации — пересмотреть Benefit/Cost")
        next_steps.append("2. Уведомить инициатора CR о переносе через `prepare_communication_package` (4.4)")
    else:  # Rejected
        next_steps.append("1. Уведомить инициатора CR об отклонении с обоснованием (4.4)")
        next_steps.append("2. CR сохранён в репозитории для audit trail")

    if next_steps:
        record_lines += ["## Следующие шаги", ""] + next_steps + [""]

    record_lines += ["---", "", "*Сгенерировано: AInalyst BABOK 5.4*"]

    artifact_content = "\n".join(record_lines)
    save_path = save_artifact(artifact_content, prefix=f"5_4_cr_decision_{cr_id}", project_id=project_name)

    # Итоговый вывод
    output_lines = [
        f"## {decision_icon} CR {cr_id} — {decision}",
        "",
        f"**Принял:** {decided_by}  ",
        f"**Обоснование:** {rationale}",
        "",
    ]

    if unplanned_decider:
        output_lines += [
            f"⚠️ `{decided_by}` нет среди запланированных принимающих решения (3.3): "
            f"{', '.join(planned_deciders)}. Решение остаётся ровно таким, как записано "
            f"— либо обновите 3.3 через `plan_ba_governance`, либо подтвердите, что этот "
            f"человек обладает полномочиями.",
            "",
        ]

    # Escalation is the next step only where the requester lost. On an Approved CR it
    # is in the record for the audit trail, but printing it here would be noise on the
    # output the BA reads every single time.
    if decision in ("Deferred", "Rejected") and escalation:
        output_lines += [
            f"ℹ️ If the requester disputes this, the planned escalation path is: "
            f"{escalation} *({escalation_source})*.",
            "",
        ]

    if updated_reqs:
        output_lines += [
            f"### Обновлённые требования",
            "",
            f"Следующие требования переведены в статус `under_change`:",
            ", ".join(f"`{r}`" for r in updated_reqs),
            "",
            "⚠️ Обновите содержание требований через `update_requirement` (5.2).",
            "",
        ]

    if modification_notes:
        output_lines += [
            "### Изменения скоупа",
            "",
            modification_notes,
            "",
        ]

    output_lines += [
        "### Следующие шаги",
        "",
    ] + next_steps + ["", save_path]

    # `load_ba_plan`'s contract is that the caller SHOWS this: an unreadable plan
    # silently disables every cross-check, and the audit trail then reads exactly like
    # a project that never planned governance. The BA has to be able to tell those
    # apart. It goes in the reply, not in the Decision Record — the record is a
    # statement about the CR, not about the platform's file system.
    if gov_note:
        output_lines += ["", gov_note]

    return "\n".join(output_lines)


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
