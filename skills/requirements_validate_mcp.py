"""
BABOK 7.3 — Validate Requirements
MCP tools for validating requirements: checking alignment with business objectives,
managing assumptions, success criteria, the validated status.

Tools:
  - set_business_context       — create/update the business context by hand (6.1/6.2 populate the same file when run)
  - check_business_alignment   — check traceability of reqs to business objectives (BFS + matching)
  - set_success_criteria       — attach a measurable success criterion to a req
  - log_assumption             — record an assumption (AS-001, ...)
  - resolve_assumption         — close an assumption (confirmed/refuted)
  - mark_req_validated         — status verified -> validated (warnings, not blocks)
  - get_validation_report      — summary report: coverage matrix, orphans, assumptions, verdict

{project}_business_context.json — set here by hand or populated by Chapter 6 (6.1/6.2)
{project}_assumptions.json — the assumptions registry
set_success_criteria — an optional pipeline step
mark_req_validated — warnings, not hard blocks

Reads: repository 5.1 ({project}_traceability_repo.json)
Writes: {project}_business_context.json, {project}_assumptions.json,
        the validated status in 5.1
Output: Validation Report -> 7.5 (Design Options)

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from collections import deque
from datetime import date
from typing import Optional
from mcp.server.fastmcp import FastMCP
from skills.common import (write_json_artifact,
    save_artifact, logger, DATA_DIR, data_path, normalize_project_id,
    has_passed_verification, BUSINESS_NODE_TYPES, NON_REQUIREMENT_NODE_TYPES,
    read_json_artifact, guard_artifact_errors,
)

mcp = FastMCP("BABOK_Requirements_Validate")

REPO_FILENAME = "traceability_repo.json"
CONTEXT_FILENAME = "business_context.json"
ASSUMPTIONS_FILENAME = "assumptions.json"

# Node types that are NOT requirements to be validated. The local set used to be
# BUSINESS_NODE_TYPES | {"test"} — written before `risk` (6.3), `change_request`
# (5.4) and `solution_scope` (6.4) existed, so those nodes inflated the validated_pct
# denominator, were reported as "reqs without traceability to business objectives"
# and failed the Ready-for-7.5 gate, while check_business_alignment one screen up
# answered correctly. The vocabulary GROWS as chapters are added; consumers must ask
# the shared definition, not a snapshot of it (the Part-2d class, one more consumer).
NON_REQUIREMENT_TYPES = NON_REQUIREMENT_NODE_TYPES


# ---------------------------------------------------------------------------
# Утилиты — пути и загрузка файлов
# ---------------------------------------------------------------------------

def _safe(project_id: str) -> str:
    return normalize_project_id(project_id)


def _repo_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{REPO_FILENAME}")


def _context_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{CONTEXT_FILENAME}")


def _assumptions_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{ASSUMPTIONS_FILENAME}")


def _load_repo(project_id: str) -> dict:
    path = _repo_path(project_id)
    if os.path.exists(path):
        # Raises CorruptArtifactError, converted to a ❌ line by guard_artifact_errors
        # at the tool boundary. A bare json.load here made a damaged file a protocol
        # error in every downstream tool.
        return read_json_artifact(path, "5.1 traceability repository")
    return {"project": project_id, "requirements": [], "links": [], "history": []}


def _save_repo(repo: dict) -> None:
    project_id = repo["project"]
    path = _repo_path(project_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    repo["updated"] = str(date.today())
    write_json_artifact(path, repo)
    logger.info(f"Repository 5.1 updated (7.3): {path}")


def _load_context(project_id: str) -> Optional[dict]:
    path = _context_path(project_id)
    if os.path.exists(path):
        # Raises CorruptArtifactError, converted to a ❌ line by guard_artifact_errors
        # at the tool boundary. A bare json.load here made a damaged file a protocol
        # error in every downstream tool.
        return read_json_artifact(path, "7.3 business context file")
    return None


def _save_context(data: dict) -> None:
    path = _context_path(data["project_id"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data["updated_at"] = str(date.today())
    write_json_artifact(path, data)
    logger.info(f"Business context saved: {path}")


def _load_assumptions(project_id: str) -> dict:
    path = _assumptions_path(project_id)
    if os.path.exists(path):
        # Raises CorruptArtifactError, converted to a ❌ line by guard_artifact_errors
        # at the tool boundary. A bare json.load here made a damaged file a protocol
        # error in every downstream tool.
        return read_json_artifact(path, "7.3 assumptions file")
    return {
        "project": project_id,
        "assumptions": {},
        "stats": {"open": 0, "confirmed": 0, "refuted": 0},
        "created": str(date.today()),
        "updated": str(date.today()),
    }


def _save_assumptions(data: dict) -> None:
    path = _assumptions_path(data["project"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data["updated"] = str(date.today())
    write_json_artifact(path, data)
    logger.info(f"Assumptions updated: {path}")


def _next_assumption_id(data: dict) -> str:
    existing = [k for k in data["assumptions"].keys() if k.startswith("AS-")]
    if not existing:
        return "AS-001"
    nums = [int(k.split("-")[1]) for k in existing if k.split("-")[1].isdigit()]
    return f"AS-{(max(nums) + 1):03d}" if nums else "AS-001"


def _find_req(repo: dict, req_id: str) -> Optional[dict]:
    for r in repo["requirements"]:
        if r["id"] == req_id:
            return r
    return None


# ---------------------------------------------------------------------------
# BFS-поиск трассировки к бизнес-целям (ADR-030)
# ---------------------------------------------------------------------------

# Relations that mean "the source serves the target". Reaching an objective over
# anything else is not evidence that the requirement serves it.
_SERVES_RELATIONS = ("derives", "satisfies")


def _bfs_to_business(repo: dict, start_id: str) -> list:
    """
    Walks the 5.1 traceability graph UPWARD from start_id and returns the business
    nodes it serves. Used by check_business_alignment.

    Direction and relation both matter. The canonical edge is `from` = child/realizer,
    `to` = parent/objective, and only `derives` / `satisfies` express "serves".

    Traversing every edge in both directions turns the question "does this requirement
    trace to objective BG-001?" into "is it in the same connected component as BG-001?",
    which on a connected project is true of everything. It also produced positively
    wrong answers: a requirement whose only link was `depends` on a RISK that
    `threatens` an objective was reported as serving that objective — and, by
    continuing through it, every other objective the component touched.

    The walk stops at the first business node on each path: an objective's other
    children are siblings of the start node, not objectives of it. 5.4 `_has_br_path`
    applies the same rule.
    """
    links = repo.get("links", [])
    reqs_by_id = {r["id"]: r for r in repo.get("requirements", [])}

    visited = set()
    queue = deque([start_id])
    business_nodes = []

    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)

        node = reqs_by_id.get(current)
        if node and current != start_id and node.get("type") in BUSINESS_NODE_TYPES:
            business_nodes.append(node)
            # Do NOT stop here: business nodes chain upward too (6.2 writes
            # `business_goal derives -> business_need`, and a business requirement can
            # derive from an objective), so a requirement legitimately serves several
            # nodes up one line of descent. Walking only upward already makes it
            # impossible to reach an objective's other children.

        for link in links:
            if (link.get("from") == current
                    and link.get("relation") in _SERVES_RELATIONS):
                neighbor = link.get("to")
                if neighbor and neighbor not in visited:
                    queue.append(neighbor)

    return business_nodes


def _title_matches_goal(req_title: str, goal_title: str) -> bool:
    """
    Advisory title overlap: True if the requirement and objective titles share a word
    of >= 5 characters. This is a HINT surfaced to the analyst, never a substitute for
    a graph link — alignment and coverage are read from the 5.1 edges only.
    """
    req_words = set(w.lower() for w in req_title.split() if len(w) >= 5)
    goal_words = set(w.lower() for w in goal_title.split() if len(w) >= 5)
    return bool(req_words & goal_words)


# ---------------------------------------------------------------------------
# 7.3.1 — set_business_context (ADR-030)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def set_business_context(
    project_id: str,
    business_goals_json: str,
    future_state: str,
    solution_scope: str,
    potential_value: str = "",
    from_current_state_project_id: str = "",
    from_strategy_project_id: str = "",
) -> str:
    """
    BABOK 7.3 — Creates or updates the project's business context.
    sets the business context by hand so 7.3 can run standalone. Chapter 6
    (Strategy Analysis) is implemented; 6.1/6.2 populate the same file automatically when run.

    ⚠️ Вызывать один раз в начале работы над валидацией. При обновлении — предупреждение.

    Args:
        project_id:          Идентификатор проекта.
        business_goals_json: JSON-список бизнес-целей:
                             '[{"id":"BG-001","title":"...","description":"...","kpi":"..."}]'.
                             id must start with BG-.
        future_state:        Description of the desired future state (Free State).
        solution_scope:      Solution boundaries: what is in, what is out.
        potential_value:          Potential value/benefit (optional).
        from_current_state_project_id: ⚠️ DEPRECATED — use from_strategy_project_id.
                                 Prefills from 6.1 data. Kept for compatibility.
        from_strategy_project_id: Reads data from 6.1 AND 6.2 and prefills objectives, future_state,
                                 scope. Replaces from_current_state_project_id.

    Returns:
        Подтверждение с кратким саммари бизнес-контекста.
    """
    logger.info(f"set_business_context: project_id=\'{project_id}\'")

    # ADR-065: новый параметр from_strategy_project_id читает 6.1 + 6.2
    prefill_status = ""
    if from_strategy_project_id.strip():
        # normalize_project_id, NOT the legacy lower/replace: the 6.1/6.2
        # producers write their files through normalize_project_id, so a pid
        # with characters outside [a-z0-9_-] built a DIFFERENT filename here
        # and the prefill silently reported "data not found".
        # The normalised value belongs in the FILE NAME only. data_path takes the RAW
        # id — it normalises internally and derives the legacy fallbacks from it, and
        # handing it a pre-normalised value walks straight past the project_id guard:
        # every unusable id collapses to the same placeholder, which is itself a
        # well-formed id, so two different projects silently share one folder again.
        safe_sp = normalize_project_id(from_strategy_project_id)
        fs_goals_path = data_path(from_strategy_project_id, f"{safe_sp}_future_state_goals.json")
        fs_state_path = data_path(from_strategy_project_id, f"{safe_sp}_future_state.json")
        fs_scope_path = data_path(from_strategy_project_id, f"{safe_sp}_future_state_scope.json")
        cs_needs_path = data_path(from_strategy_project_id, f"{safe_sp}_business_needs.json")

        try:
            prefill_parts = []

            # Предзаполняем business_goals из BG-целей 6.2
            if os.path.exists(fs_goals_path) and (not business_goals_json.strip() or business_goals_json.strip() == "[]"):
                with open(fs_goals_path, "r", encoding="utf-8") as f_g:
                    goals_data = json.load(f_g)
                bg_list = goals_data.get("goals", [])
                if bg_list:
                    auto_goals = [
                        {
                            "id": g["id"],
                            "title": g["goal_title"],
                            "description": g.get("description", ""),
                            "kpi": "; ".join(
                                f"{o.get('title', '')}: {o.get('baseline', '?')} → {o.get('target', '?')}"
                                for o in g.get("objectives", [])
                            ),
                        }
                        for g in bg_list
                    ]
                    business_goals_json = json.dumps(auto_goals, ensure_ascii=False)
                    prefill_parts.append(f"✅ Бизнес-цели предзаполнены из 6.2 ({len(auto_goals)} BG-целей)")

            # Предзаполняем future_state из описания 6.2
            if os.path.exists(fs_state_path) and not future_state.strip():
                with open(fs_state_path, "r", encoding="utf-8") as f_s:
                    fs_data = json.load(f_s)
                elem_descs = [
                    f"{k}: {v.get('description', '')[:100]}"
                    for k, v in fs_data.get("elements", {}).items()
                    if v.get("description")
                ]
                if elem_descs:
                    future_state = "Будущее состояние: " + "; ".join(elem_descs[:3])
                    prefill_parts.append("✅ future_state предзаполнен из элементов 6.2")

            # Предзаполняем solution_scope из скоупа 6.2
            if os.path.exists(fs_scope_path) and not solution_scope.strip():
                with open(fs_scope_path, "r", encoding="utf-8") as f_sc:
                    scope_data_62 = json.load(f_sc)
                elements = scope_data_62.get("elements_in_scope", [])
                initiative = scope_data_62.get("initiative_type", "")
                if elements:
                    solution_scope = f"Элементы скоупа: {', '.join(elements)}. Тип: {initiative}."
                    prefill_parts.append("✅ solution_scope предзаполнен из скоупа 6.2")

            # Fallback: если цели ещё не заполнены — пробуем из 6.1 BN
            if (not business_goals_json.strip() or business_goals_json.strip() == "[]") and os.path.exists(cs_needs_path):
                with open(cs_needs_path, "r", encoding="utf-8") as f_n:
                    needs_data = json.load(f_n)
                needs_list = needs_data.get("needs", [])
                if needs_list:
                    auto_goals = [
                        {
                            # Keep the REAL business-need id. The graph traversal in
                            # check_business_alignment / get_validation_report finds
                            # `business_need` nodes (BN-xxx); a synthesised `BG-{n}` id
                            # here would never match them, so a requirement correctly
                            # linked to its need was reported orphan on the 6.1-only
                            # path. Objectives ARE the 6.1 needs at this stage.
                            "id": need.get("id") or f"BG-{idx_n:03d}",
                            "title": need.get("need_title", f"Need {idx_n}"),
                            "description": need.get("description", ""),
                            "kpi": need.get("cost_of_inaction", ""),
                            "source_bn": need.get("id", ""),
                        }
                        for idx_n, need in enumerate(needs_list, 1)
                    ]
                    business_goals_json = json.dumps(auto_goals, ensure_ascii=False)
                    prefill_parts.append(f"✅ Бизнес-цели предзаполнены из 6.1 BN ({len(auto_goals)} шт.)")

            if prefill_parts:
                prefill_status = "\n\n## Автозаполнение из 6.1+6.2\n\n" + "\n".join(prefill_parts)
            else:
                prefill_status = f"\n\n⚠️ Данные 6.1/6.2 для проекта `{from_strategy_project_id}` не найдены."

        except (json.JSONDecodeError, KeyError, IOError) as e:
            prefill_status = f"\n\n⚠️ Не удалось прочитать данные 6.1/6.2: {e}."

    # ADR-055: предзаполнение из 6.1 если передан from_current_state_project_id (deprecated)
    elif from_current_state_project_id.strip():
        prefill_status = "\n\n⚠️ Параметр `from_current_state_project_id` устарел. Используйте `from_strategy_project_id`."
        # Raw id to data_path, normalised value only in the file name — see the note
        # on the from_strategy_project_id branch above.
        safe_cs = normalize_project_id(from_current_state_project_id)
        needs_path = data_path(from_current_state_project_id, f"{safe_cs}_business_needs.json")
        scope_path = data_path(from_current_state_project_id, f"{safe_cs}_current_state_scope.json")

        if os.path.exists(needs_path):
            try:
                with open(needs_path, "r", encoding="utf-8") as f_n:
                    needs_data = json.load(f_n)
                needs_list = needs_data.get("needs", [])

                if (not business_goals_json.strip() or business_goals_json.strip() == "[]") and needs_list:
                    auto_goals = []
                    for idx_n, need in enumerate(needs_list, 1):
                        auto_goals.append({
                            # Keep the REAL business-need id so the graph traversal
                            # (which finds BN-xxx nodes) matches — see the note in the
                            # from_strategy branch above.
                            "id": need.get("id") or f"BG-{idx_n:03d}",
                            "title": need.get("need_title", f"Need {idx_n}"),
                            "description": need.get("description", ""),
                            "kpi": need.get("cost_of_inaction", ""),
                            "source_bn": need.get("id", ""),
                        })
                    business_goals_json = json.dumps(auto_goals, ensure_ascii=False)
                    ids_used = ", ".join(g["id"] for g in auto_goals)
                    prefill_status += (
                        f"\n\n## Автозаполнение из 6.1\n\n"
                        f"✅ Бизнес-цели предзаполнены из {len(auto_goals)} "
                        f"бизнес-потребностей проекта `{from_current_state_project_id}`.\n"
                        f"Цели сохраняют id бизнес-потребностей из 6.1, чтобы трассировка "
                        f"в графе совпадала: {ids_used}"
                    )

                if not solution_scope.strip() and os.path.exists(scope_path):
                    with open(scope_path, "r", encoding="utf-8") as f_s:
                        scope_data = json.load(f_s)
                    elements = scope_data.get("elements_in_scope", [])
                    initiative = scope_data.get("initiative_type", "")
                    problems = scope_data.get("known_problems", "")
                    if elements:
                        solution_scope = (
                            "Анализ охватывает элементы: " + ", ".join(elements) + ". "
                            "Тип инициативы: " + str(initiative) + ". "
                            "Контекст: " + str(problems[:200])
                        )

            except (json.JSONDecodeError, KeyError, IOError) as e:
                prefill_status += f"\n\n⚠️ Не удалось прочитать данные 6.1: {e}."
        else:
            prefill_status += (
                f"\n\n⚠️ Файл бизнес-потребностей 6.1 не найден: `{needs_path}`.\n"
                f"Завершите задачу 6.1 для проекта `{from_current_state_project_id}`."
            )

    # ADR-055: предзаполнение из 6.1 (old block placeholder removed)
    try:
        goals = json.loads(business_goals_json)
        if not isinstance(goals, list) or not goals:
            raise ValueError("Список не должен быть пустым")
        for g in goals:
            if not isinstance(g, dict) or "id" not in g or "title" not in g:
                raise ValueError("Каждая цель должна содержать поля 'id' и 'title'")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Ошибка парсинга business_goals_json: {e}\n\n"
            f"Ожидается JSON-список: "
            f'\'[{{"id":"BG-001","title":"Снизить время обработки","description":"...","kpi":"..."}}]\''
        )

    if not future_state.strip():
        return "❌ future_state не может быть пустым — опиши желаемое будущее состояние."

    if not solution_scope.strip():
        return "❌ solution_scope не может быть пустым — опиши границы решения."

    existing = _load_context(project_id)
    is_update = existing is not None

    data = {
        "project_id": project_id,
        "business_goals": goals,
        "future_state": future_state,
        "solution_scope": solution_scope,
        "potential_value": potential_value,
        "created_at": existing["created_at"] if existing else str(date.today()),
        "updated_at": str(date.today()),
    }

    _save_context(data)

    lines = [
        f"{'⚠️ Бизнес-контекст ОБНОВЛЁН' if is_update else '✅ Бизнес-контекст создан'} — **{project_id}**",
        "",
        f"> ℹ️ **Бизнес-контекст задан вручную в 7.3** — глава 6 (6.1/6.2) заполняет этот файл автоматически, когда её запускают",
        "",
        f"**Дата:** {date.today()}",
        "",
        f"## Бизнес-цели ({len(goals)})",
        "",
    ]

    for g in goals:
        kpi = f" | KPI: {g['kpi']}" if g.get("kpi") else ""
        desc = f" — {g['description'][:80]}..." if g.get("description") and len(g.get("description","")) > 80 \
               else (f" — {g['description']}" if g.get("description") else "")
        lines.append(f"- **{g['id']}** {g['title']}{desc}{kpi}")

    lines += [
        "",
        f"## Будущее состояние",
        "",
        future_state[:200] + ("..." if len(future_state) > 200 else ""),
        "",
        f"## Границы решения",
        "",
        solution_scope[:200] + ("..." if len(solution_scope) > 200 else ""),
    ]

    if potential_value:
        lines += [
            "",
            f"## Потенциальная ценность",
            "",
            potential_value[:200] + ("..." if len(potential_value) > 200 else ""),
        ]

    lines += [
        "",
        "---",
        "",
        "**Следующий шаг:**",
        f"`check_business_alignment(project_id='{project_id}')` — проверить трассировку req к BG",
    ]

    if prefill_status:
        lines.append(prefill_status)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.3.2 — check_business_alignment (ADR-030)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def check_business_alignment(
    project_id: str,
    req_ids: str = "",
) -> str:
    """
    BABOK 7.3 — Проверяет трассировку требований к бизнес-целям.
    Методы: BFS-поиск по узлам типа 'business' в репозитории 5.1 +
            title-matching с BG-xxx из business_context.json.

    business objectives are taken from {project}_business_context.json.

    Args:
        project_id: Идентификатор проекта.
        req_ids:    JSON-список ID для проверки: '["US-001", "FR-001"]'.
                    Если пустой — проверяет все verified req проекта.

    Returns:
        Coverage matrix: aligned / orphan / needs_review по каждому req.
        Дополнительно: какие BG не покрыты ни одним req.
    """
    logger.info(f"check_business_alignment: project_id='{project_id}', req_ids='{req_ids}'")

    ctx = _load_context(project_id)
    if ctx is None:
        return (
            f"❌ Бизнес-контекст для проекта `{project_id}` не найден.\n\n"
            f"Сначала вызови: `set_business_context(project_id='{project_id}', ...)`"
        )

    repo = _load_repo(project_id)
    all_reqs = repo.get("requirements", [])

    if not all_reqs:
        return (
            f"⚠️ Репозиторий 5.1 для проекта `{project_id}` пуст или не найден.\n\n"
            f"Убедись что требования созданы через инструменты 7.1."
        )

    # Фильтрация
    if req_ids.strip():
        try:
            ids_to_check = json.loads(req_ids)
            if not isinstance(ids_to_check, list):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            return f"❌ Ошибка парсинга req_ids: ожидается JSON-список, например: '[\"US-001\", \"FR-001\"]'"
        reqs_to_check = [r for r in all_reqs if r["id"] in ids_to_check]
        not_found = [i for i in ids_to_check if i not in {r["id"] for r in all_reqs}]
    else:
        # Verification is a durable FACT in history, not the current status: `status`
        # is one field shared across chapters, and 5.5 overwrites it with `approved`
        # on the way to a baseline. Selecting by status meant that once a project was
        # formally approved, this tool answered "no verified requirements to check"
        # and told the BA to go and verify them — advice they had already followed.
        # Same defect as the one fixed in mark_req_validated in this file.
        reqs_to_check = [
            r for r in all_reqs
            if has_passed_verification(repo, r["id"]) or r.get("status") == "validated"
        ]
        not_found = []

    if not reqs_to_check:
        return (
            f"ℹ️ Нет verified/validated требований для проверки в проекте `{project_id}`.\n\n"
            f"Верифицируй требования через инструменты 7.2 (`mark_req_verified`) "
            f"перед валидацией."
        )

    goals = ctx.get("business_goals", [])
    goal_ids = {g["id"] for g in goals}
    goals_by_id = {g["id"]: g for g in goals}

    # Проверяем каждый req
    aligned_reqs = []
    orphan_reqs = []
    needs_review_reqs = []

    # Для coverage matrix: какие BG покрыты
    covered_goals: set = set()

    for req in reqs_to_check:
        req_id = req["id"]
        req_type = req.get("type", "")

        # Skip the goal/root nodes (business / business_goal / business_need) and test nodes —
        # they are not requirements to be aligned (audit finding 7.3-A).
        if req_type in NON_REQUIREMENT_TYPES:
            continue

        # Alignment is a claim about TRACEABILITY, so it is read from the graph edges
        # ONLY — the same rule 7.1 build_coverage_matrix follows ("nothing is inferred
        # from text"). A title word-overlap between a requirement and an objective is a
        # HINT for the analyst, never a substitute for a link: it is surfaced as advisory
        # and does NOT count toward alignment or objective coverage.
        bfs_nodes = _bfs_to_business(repo, req_id)
        bfs_goal_ids = {n["id"] for n in bfs_nodes if n["id"] in goal_ids}

        title_hint_goals = {
            g["id"] for g in goals
            if g["id"] not in bfs_goal_ids
            and _title_matches_goal(req.get("title", ""), g["title"])
        }

        if bfs_goal_ids:
            covered_goals |= bfs_goal_ids
            aligned_reqs.append({
                "req_id": req_id,
                "title": req.get("title", ""),
                "aligned_goals": sorted(bfs_goal_ids),
                "method": "bfs",
            })
        elif title_hint_goals:
            needs_review_reqs.append({
                "req_id": req_id,
                "title": req.get("title", ""),
                "hint_goals": sorted(title_hint_goals),
            })
        else:
            orphan_reqs.append({
                "req_id": req_id,
                "title": req.get("title", ""),
                "type": req_type,
            })

    # BG без покрытия
    uncovered_goals = [g for g in goals if g["id"] not in covered_goals]

    # Формируем отчёт
    total = len(aligned_reqs) + len(orphan_reqs) + len(needs_review_reqs)
    aligned_pct = round(len(aligned_reqs) / total * 100, 1) if total > 0 else 0.0

    lines = [
        f"<!-- BABOK 7.3 — Business Alignment | Проект: {project_id} | {date.today()} -->",
        "",
        f"# 🎯 Выравнивание с бизнес-целями — {project_id}",
        "",
        f"**Дата:** {date.today()}  ",
        f"**Проверено req:** {total}  ",
        f"**Бизнес-целей:** {len(goals)}",
        "",
        "## Сводка",
        "",
        "| Статус | Количество |",
        "|--------|-----------|",
        f"| ✅ Согласовано (есть трассировка на BG в графе) | {len(aligned_reqs)} ({aligned_pct}%) |",
        f"| ⚠️ Только совпадение по заголовку (проверить и связать) | {len(needs_review_reqs)} |",
        f"| ❌ Сирота (нет трассировки на BG) | {len(orphan_reqs)} |",
        "",
    ]

    if not_found:
        lines += [
            f"⚠️ Не найдены в репозитории: {', '.join(f'`{i}`' for i in not_found)}",
            "",
        ]

    # Coverage matrix
    lines += [
        "## Coverage Matrix — Бизнес-цели",
        "",
        "| BG ID | Название | Покрытие req |",
        "|-------|----------|-------------|",
    ]
    for g in goals:
        covered = g["id"] in covered_goals
        icon = "✅" if covered else "❌"
        covering_reqs = [r["req_id"] for r in aligned_reqs if g["id"] in r["aligned_goals"]]
        req_list = ", ".join(f"`{r}`" for r in covering_reqs[:5])
        if len(covering_reqs) > 5:
            req_list += f" +{len(covering_reqs)-5} ещё"
        lines.append(f"| `{g['id']}` | {g['title']} | {icon} {req_list or '—'} |")
    lines.append("")

    # Aligned req
    if aligned_reqs:
        lines += [
            "## ✅ Выровненные требования",
            "",
        ]
        for r in aligned_reqs:
            goals_str = ", ".join(f"`{g}`" for g in r["aligned_goals"])
            lines.append(f"- `{r['req_id']}` — {r['title']} → {goals_str} _(трассировка в графе)_")
        lines.append("")

    # Title-match hints — advisory, NOT counted as coverage (graph is the source of truth)
    if needs_review_reqs:
        lines += [
            "## ⚠️ Возможные совпадения по заголовку (подсказка — покрытием НЕ считается)",
            "",
            "> Заголовок требования делит слова с формулировкой цели, но связи в графе 5.1 "
            "НЕТ. Подтвердите отношение и зафиксируйте его через `add_trace_link` "
            "(5.1) — тогда оно засчитается как настоящая трассировка.",
            "",
        ]
        for r in needs_review_reqs:
            hints = ", ".join(f"`{g}`" for g in r["hint_goals"])
            lines.append(f"- `{r['req_id']}` — {r['title']} → {hints}")
        lines.append("")

    # Orphan req
    if orphan_reqs:
        lines += [
            "## ❌ Требования без трассировки к бизнес-целям (Orphans)",
            "",
            "> Эти требования не связаны ни с одной бизнес-целью.",
            "> Возможно они избыточны или необходима трассировка через 5.1.",
            "",
        ]
        for r in orphan_reqs:
            lines.append(f"- `{r['req_id']}` ({r['type']}) — {r['title']}")
        lines.append("")

    # Непокрытые BG
    if uncovered_goals:
        lines += [
            "## ⚠️ Бизнес-цели без покрытия req",
            "",
            "> Эти бизнес-цели не покрыты ни одним верифицированным требованием.",
            "> Возможно нужны дополнительные требования.",
            "",
        ]
        for g in uncovered_goals:
            lines.append(f"- `{g['id']}` — {g['title']}")
        lines.append("")

    lines += [
        "---",
        "",
        "## Следующие шаги",
        "",
    ]

    if orphan_reqs:
        lines.append("1. Для каждого Orphan: проверь необходимость req и добавь трассировку через 5.1 "
                     "(`add_trace_link`) или удали как избыточное.")
    if uncovered_goals:
        lines.append("2. Для непокрытых BG: создай недостающие req через инструменты 7.1.")
    lines += [
        "3. Зафиксируй предположения: `log_assumption(project_id=...)` для рисковых допущений.",
        "4. Задай критерии успеха: `set_success_criteria(project_id=...)` для критичных req.",
        f"5. После устранения проблем: `mark_req_validated(project_id='{project_id}', req_ids='[...]')`",
    ]

    content = "\n".join(lines)
    save_artifact(content, prefix="7_3_business_alignment", project_id=project_id)
    return content


# ---------------------------------------------------------------------------
# 7.3.3 — set_success_criteria (ADR-032)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def set_success_criteria(
    project_id: str,
    req_id: str,
    criteria_json: str,
) -> str:
    """
    BABOK 7.3 — Attaches a measurable success criterion to a requirement.
    An optional pipeline step. Recommended for critical reqs.

    Данные пишутся в поле success_criteria узла req в репозитории 5.1.
    Связь с 8.1 (Measure Solution Performance): эти данные станут входными.

    Args:
        project_id:    Идентификатор проекта.
        req_id:        ID требования (US-001, FR-003 и т.д.).
        criteria_json: JSON с критериями:
                       '{"baseline":"...", "target":"...",
                         "measurement_method":"...", "kpi_ref":"BG-001"}'.

    Returns:
        Подтверждение + подсказка KPI из связанной бизнес-цели.
    """
    logger.info(f"set_success_criteria: project_id='{project_id}', req_id='{req_id}'")

    try:
        criteria = json.loads(criteria_json)
        if not isinstance(criteria, dict):
            raise ValueError("Ожидается JSON-объект")
        required_fields = {"baseline", "target", "measurement_method"}
        missing = required_fields - set(criteria.keys())
        if missing:
            raise ValueError(f"Отсутствуют обязательные поля: {', '.join(sorted(missing))}")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Ошибка парсинга criteria_json: {e}\n\n"
            f"Ожидается: "
            f'\'{{\"baseline\":\"текущий показатель\",\"target\":\"целевой показатель\","'
            f'"measurement_method\":\"как измеряем\",\"kpi_ref\":\"BG-001\"}}\''
        )

    repo = _load_repo(project_id)
    req = _find_req(repo, req_id)

    if not req:
        return (
            f"❌ Требование `{req_id}` не найдено в репозитории 5.1 проекта `{project_id}`.\n"
            f"Доступные req: {', '.join(r['id'] for r in repo.get('requirements', [])[:10])}"
        )

    # Подсказка KPI из связанной бизнес-цели
    kpi_hint = ""
    kpi_ref = criteria.get("kpi_ref", "")
    if kpi_ref:
        ctx = _load_context(project_id)
        if ctx:
            goals_by_id = {g["id"]: g for g in ctx.get("business_goals", [])}
            if kpi_ref in goals_by_id:
                goal = goals_by_id[kpi_ref]
                if goal.get("kpi"):
                    kpi_hint = f"\n💡 KPI бизнес-цели `{kpi_ref}`: {goal['kpi']}"

    # Пишем в req
    req["success_criteria"] = {
        "baseline": criteria.get("baseline", ""),
        "target": criteria.get("target", ""),
        "measurement_method": criteria.get("measurement_method", ""),
        "kpi_ref": kpi_ref,
        "set_date": str(date.today()),
    }

    repo["history"].append({
        "action": "success_criteria_set",
        "req_id": req_id,
        "source": "7.3_validate",
        "date": str(date.today()),
    })

    _save_repo(repo)

    lines = [
        f"✅ Критерий успеха привязан к **{req_id}**",
        "",
        f"| Поле | Значение |",
        f"|------|----------|",
        f"| Требование | `{req_id}` — {req.get('title', '')} |",
        f"| Baseline | {criteria['baseline']} |",
        f"| Цель | {criteria['target']} |",
        f"| Метод измерения | {criteria['measurement_method']} |",
        f"| Ссылка на KPI | {kpi_ref or '—'} |",
        f"| Дата | {date.today()} |",
    ]

    if kpi_hint:
        lines.append("")
        lines.append(kpi_hint)

    lines += [
        "",
        "---",
        "",
        f"**Связь с 8.1:** success_criteria из 7.3 станут входными данными для "
        f"Measure Solution Performance (Глава 8).",
        "",
        f"Продолжи: `mark_req_validated` или добавь критерии для других req.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.3.4 — log_assumption (ADR-031)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def log_assumption(
    project_id: str,
    description: str,
    req_ids: str,
    risk_level: str,
    assigned_to: str = "",
) -> str:
    """
    BABOK 7.3 — Records an assumption with a risk_level and linked reqs.
    stored in {project}_assumptions.json, numbering AS-001/AS-002/...

    Args:
        project_id:  Идентификатор проекта.
        description: Текст предположения.
        req_ids:     JSON-список связанных req: '["US-001", "FR-003"]'.
        risk_level:  Уровень риска: high | medium | low.
        assigned_to: Кому назначено для подтверждения. По умолчанию пусто.

    Returns:
        Подтверждение с ID созданного предположения.
    """
    logger.info(f"log_assumption: project_id='{project_id}', risk_level='{risk_level}'")

    valid_risk_levels = {"high", "medium", "low"}
    if risk_level not in valid_risk_levels:
        return (
            f"❌ Недопустимый risk_level: '{risk_level}'.\n"
            f"Допустимые значения: high | medium | low"
        )

    if not description.strip():
        return "❌ description не может быть пустым — опиши предположение."

    try:
        req_ids_list = json.loads(req_ids)
        if not isinstance(req_ids_list, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        return (
            f"❌ Ошибка парсинга req_ids: ожидается JSON-список, "
            f"например: '[\"US-001\", \"FR-001\"]'"
        )

    data = _load_assumptions(project_id)
    assumption_id = _next_assumption_id(data)

    data["assumptions"][assumption_id] = {
        "assumption_id": assumption_id,
        "description": description,
        "req_ids": req_ids_list,
        "risk_level": risk_level,
        "status": "open",
        "assigned_to": assigned_to or "",
        "created_at": str(date.today()),
        "resolved_at": None,
        "resolution_note": "",
    }

    # Обновляем статистику
    _update_assumption_stats(data)
    _save_assumptions(data)

    risk_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    icon = risk_icons.get(risk_level, "")

    lines = [
        f"✅ Предположение зафиксировано: **{assumption_id}**",
        "",
        f"| Поле | Значение |",
        f"|------|----------|",
        f"| ID | `{assumption_id}` |",
        f"| Уровень риска | {icon} {risk_level} |",
        f"| Связанные req | {', '.join(f'`{r}`' for r in req_ids_list) or '—'} |",
        f"| Назначено | {assigned_to or '—'} |",
        f"| Статус | open |",
        f"| Дата | {date.today()} |",
        "",
        f"**Описание:** {description}",
    ]

    if risk_level == "high":
        lines += [
            "",
            f"> 🔴 **High risk assumption:** `mark_req_validated` выдаст предупреждение "
            f"для req {', '.join(f'`{r}`' for r in req_ids_list)} "
            f"пока это предположение остаётся открытым.",
        ]

    lines += [
        "",
        "---",
        "",
        f"**Следующий шаг:** подтверди или опровергни предположение:",
        f"`resolve_assumption(project_id='{project_id}', assumption_id='{assumption_id}', "
        f"resolution='confirmed|refuted', resolution_note='...')`",
    ]

    return "\n".join(lines)


def _update_assumption_stats(data: dict) -> None:
    """Пересчитывает статистику assumptions."""
    all_assum = list(data["assumptions"].values())
    data["stats"]["open"] = sum(1 for a in all_assum if a["status"] == "open")
    data["stats"]["confirmed"] = sum(1 for a in all_assum if a["status"] == "confirmed")
    data["stats"]["refuted"] = sum(1 for a in all_assum if a["status"] == "refuted")


# ---------------------------------------------------------------------------
# 7.3.5 — resolve_assumption (ADR-031)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def resolve_assumption(
    project_id: str,
    assumption_id: str,
    resolution: str,
    resolution_note: str,
) -> str:
    """
    BABOK 7.3 — Closes an assumption as confirmed or refuted.
    on refuted — a warning about the linked reqs.

    Args:
        project_id:      Идентификатор проекта.
        assumption_id:   ID предположения: AS-001, AS-002 и т.д.
        resolution:      confirmed | refuted
        resolution_note: Что именно подтвердило или опровергло предположение.

    Returns:
        Подтверждение закрытия. При refuted — список req для пересмотра.
    """
    logger.info(f"resolve_assumption: project_id='{project_id}', assumption_id='{assumption_id}'")

    valid_resolutions = {"confirmed", "refuted"}
    if resolution not in valid_resolutions:
        return (
            f"❌ Недопустимый resolution: '{resolution}'.\n"
            f"Допустимые значения: confirmed | refuted"
        )

    if not resolution_note.strip():
        return "❌ resolution_note не может быть пустым — опиши что именно подтвердило/опровергло."

    data = _load_assumptions(project_id)

    if assumption_id not in data["assumptions"]:
        open_list = [k for k, v in data["assumptions"].items() if v["status"] == "open"]
        return (
            f"❌ Предположение `{assumption_id}` не найдено в проекте `{project_id}`.\n"
            f"Открытые: {', '.join(open_list) or 'нет'}"
        )

    assumption = data["assumptions"][assumption_id]

    if assumption["status"] != "open":
        return (
            f"ℹ️ Предположение `{assumption_id}` уже закрыто "
            f"({assumption['status']}, {assumption.get('resolved_at', '?')}).\n"
            f"Resolution: {assumption.get('resolution_note', '—')}"
        )

    req_ids_affected = assumption.get("req_ids", [])

    assumption["status"] = resolution
    assumption["resolved_at"] = str(date.today())
    assumption["resolution_note"] = resolution_note

    _update_assumption_stats(data)
    _save_assumptions(data)

    icon = "✅" if resolution == "confirmed" else "❌"
    lines = [
        f"{icon} Предположение **{assumption_id}** закрыто как **{resolution}**.",
        "",
        f"| Поле | Значение |",
        f"|------|----------|",
        f"| ID | `{assumption_id}` |",
        f"| Resolution | {resolution} |",
        f"| Дата закрытия | {date.today()} |",
        "",
        f"**Комментарий к закрытию:** {resolution_note}",
        "",
        "---",
        "",
    ]

    if resolution == "refuted":
        lines += [
            "## ⚠️ Предположение опровергнуто",
            "",
            "Связанные требования нужно пересмотреть:",
            "",
        ]
        for req_id in req_ids_affected:
            lines.append(f"- `{req_id}` — проверь актуальность в свете опровержения предположения")
        lines += [
            "",
            "> Возможно требуется переработка требований или новый раунд выявления (4.1–4.3).",
        ]
    else:
        lines += [
            f"✅ Предположение подтверждено. Требования {', '.join(f'`{r}`' for r in req_ids_affected)} "
            f"остаются актуальными.",
        ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.3.6 — mark_req_validated (ADR-033)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def mark_req_validated(
    project_id: str,
    req_ids: str,
    force: bool = False,
) -> str:
    """
    BABOK 7.3 — Sets the 'validated' status in repository 5.1.
    Preconditions: warnings, not hard blocks.

    Проверяет:
      (1) статус req = verified (из 7.2)
      (2) нет open high-risk assumptions по req в {project}_assumptions.json
      (3) есть трассировка к бизнес-цели (BFS или title-matching)

    Args:
        project_id: Идентификатор проекта.
        req_ids:    JSON-список ID: '["US-001", "FR-001"]'.
        force:      True — установить validated даже при предупреждениях (override).

    Returns:
        Результат по каждому req: validated / предупреждение.
    """
    logger.info(f"mark_req_validated: project_id='{project_id}', req_ids='{req_ids}'")

    try:
        ids_list = json.loads(req_ids)
        if not isinstance(ids_list, list) or not ids_list:
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        return "❌ req_ids должен быть непустым JSON-списком: '[\"US-001\", \"FR-001\"]'"

    repo = _load_repo(project_id)
    data_assum = _load_assumptions(project_id)
    ctx = _load_context(project_id)
    goals = ctx.get("business_goals", []) if ctx else []
    goal_ids = {g["id"] for g in goals}

    results = []
    validated_count = 0
    warned_count = 0
    not_found_count = 0

    for req_id in ids_list:
        req = _find_req(repo, req_id)
        if not req:
            results.append({
                "req_id": req_id,
                "outcome": "not_found",
                "message": f"❌ `{req_id}` — не найден в репозитории 5.1",
                "warnings": [],
            })
            not_found_count += 1
            continue

        warnings = []

        # Precondition 1: the req passed 7.2 verification.
        #
        # Read the DURABLE record, not `status`: that field is shared across chapters
        # and 5.5 overwrites `verified` with `approved`, so a req that genuinely passed
        # 7.2 used to produce a false warning here purely because it had been approved.
        # `validated` remains accepted as this chapter's own "already past this point".
        current_status = req.get("status", "draft")
        if not has_passed_verification(repo, req_id) and current_status != "validated":
            warnings.append(
                f"Статус '{current_status}' (ожидается 'verified'). "
                f"Верифицируй req через инструменты 7.2 перед валидацией."
            )

        # Предусловие 2: open high-risk assumptions
        open_high_risk = [
            a for a in data_assum["assumptions"].values()
            if a["status"] == "open"
            and a.get("risk_level") == "high"
            and req_id in a.get("req_ids", [])
        ]
        if open_high_risk:
            ids_str = ", ".join(f"`{a['assumption_id']}`" for a in open_high_risk)
            warnings.append(
                f"Есть открытые high-risk assumptions по этому req: {ids_str}. "
                f"Закрой их через `resolve_assumption` или используй force=True."
            )

        # Предусловие 3: трассировка к бизнес-цели
        if goals:
            bfs_nodes = _bfs_to_business(repo, req_id)
            bfs_goal_ids = {n["id"] for n in bfs_nodes if n["id"] in goal_ids}
            # Graph edges only (consistent with check_business_alignment): a title
            # word-overlap is a hint, not traceability, so it must not silence the
            # "no traceability" warning.
            if not bfs_goal_ids:
                warnings.append(
                    f"Нет трассировки к бизнес-целям. "
                    f"Проверь `check_business_alignment` или добавь связи в 5.1."
                )

        # Принимаем решение
        if warnings and not force:
            warned_count += 1
            results.append({
                "req_id": req_id,
                "outcome": "warned",
                "message": f"⚠️ `{req_id}` — предупреждения (не обновлён)",
                "warnings": warnings,
            })
        else:
            old_status = current_status
            req["status"] = "validated"

            repo["history"].append({
                "action": "req_validated",
                "req_id": req_id,
                "old_status": old_status,
                "new_status": "validated",
                "force": force,
                "source": "7.3_validate",
                "date": str(date.today()),
            })

            validated_count += 1
            outcome = "validated_with_warnings" if (warnings and force) else "validated"
            results.append({
                "req_id": req_id,
                "outcome": outcome,
                "message": f"✅ `{req_id}` — validated (было: {old_status})"
                           + (" [принудительно через force]" if force and warnings else ""),
                "warnings": warnings if force else [],
            })

    if validated_count > 0:
        _save_repo(repo)

    lines = [
        f"# Результат валидации — {project_id}",
        "",
        f"**Дата:** {date.today()}  ",
        f"**Обработано:** {len(ids_list)} требований  ",
        f"**Validated:** ✅ {validated_count}  ",
        f"**С предупреждениями (не обновлено):** ⚠️ {warned_count}  ",
        f"**Не найдено:** ❌ {not_found_count}",
        "",
        "## Детали",
        "",
    ]

    for r in results:
        lines.append(r["message"])
        for w in r["warnings"]:
            lines.append(f"  ⚠️ {w}")

    if warned_count > 0:
        lines += [
            "",
            "---",
            "",
            f"⚠️ {warned_count} req не обновлены из-за предупреждений.",
            "Устрани предупреждения или вызови повторно с `force=True` для override.",
            f"Пример: `mark_req_validated(project_id='{project_id}', "
            f"req_ids='{req_ids}', force=True)`",
        ]

    if validated_count > 0:
        lines += [
            "",
            "---",
            "",
            f"✅ Статус `validated` установлен в репозитории 5.1.",
            f"Следующий шаг: `get_validation_report(project_id='{project_id}')` для сводного отчёта.",
        ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.3.7 — get_validation_report
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def get_validation_report(
    project_id: str,
) -> str:
    """
    BABOK 7.3 — Генерирует сводный отчёт по валидации проекта.

    Содержит:
      - % validated из verified
      - Coverage matrix (BG → req)
      - Список «сирот» без трассировки к целям
      - Открытые assumptions по risk_level
      - % req с success_criteria
      - Вердикт готовности к 7.5 (Design Options)

    Сохраняет Markdown через save_artifact.

    Args:
        project_id: Идентификатор проекта.

    Returns:
        Validation Report в Markdown.
    """
    logger.info(f"get_validation_report: project_id='{project_id}'")

    repo = _load_repo(project_id)
    all_reqs = repo.get("requirements", [])

    if not all_reqs:
        return (
            f"⚠️ Нет активных требований в репозитории проекта `{project_id}`.\n"
            f"Создай требования через инструменты 7.1 перед валидацией."
        )

    ctx = _load_context(project_id)
    data_assum = _load_assumptions(project_id)

    # Статистика по требованиям
    skip_statuses = {"deprecated", "superseded", "retired"}
    active_reqs = [
        r for r in all_reqs
        if r.get("status") not in skip_statuses
        and r.get("type", "") not in NON_REQUIREMENT_TYPES
    ]
    total = len(active_reqs)

    if total == 0:
        return (
            f"⚠️ Нет активных требований подходящего типа в проекте `{project_id}`.\n"
            f"Проверь что требования созданы через инструменты 7.1."
        )

    # Validation is a durable fact in history, not the mutable status: 5.5 (approved),
    # 5.4 (under_change) and a re-run 7.2 overwrite `validated` in the shared field, so
    # a status-only count reported "Not ready for 7.5" about work that WAS validated.
    from skills.common import has_been_validated
    validated = [r for r in active_reqs if has_been_validated(repo, r["id"])]
    verified_only = [r for r in active_reqs if r.get("status") == "verified"]
    with_criteria = [r for r in active_reqs if r.get("success_criteria")]

    validated_pct = round(len(validated) / total * 100, 1) if total > 0 else 0.0
    criteria_pct = round(len(with_criteria) / total * 100, 1) if total > 0 else 0.0

    # Статистика assumptions
    all_assum = list(data_assum["assumptions"].values())
    open_assum = [a for a in all_assum if a["status"] == "open"]
    open_high = [a for a in open_assum if a.get("risk_level") == "high"]
    open_medium = [a for a in open_assum if a.get("risk_level") == "medium"]
    open_low = [a for a in open_assum if a.get("risk_level") == "low"]

    # Coverage matrix
    goals = ctx.get("business_goals", []) if ctx else []
    goal_ids = {g["id"] for g in goals}
    covered_goals: set = set()
    orphan_reqs = []

    for req in active_reqs:
        req_id = req["id"]
        if not goals:
            break
        # Graph edges only (see check_business_alignment): a title overlap is not a link.
        bfs_nodes = _bfs_to_business(repo, req_id)
        bfs_goal_ids = {n["id"] for n in bfs_nodes if n["id"] in goal_ids}
        if bfs_goal_ids:
            covered_goals |= bfs_goal_ids
        else:
            orphan_reqs.append(req)

    uncovered_goals = [g for g in goals if g["id"] not in covered_goals]

    # Readiness verdict for 7.5. Without a business context there are no objectives to
    # trace to, so `orphan_reqs` is vacuously empty — the report must NOT read that as
    # "all requirements trace to objectives" and wave the project through. No context =>
    # alignment is unchecked => not ready (same honesty rule as check_business_alignment).
    has_context = bool(goals)
    ready = (
        has_context
        and validated_pct >= 80
        and len(open_high) == 0
        and len(orphan_reqs) == 0
    )
    ready_label = "✅ Готово к 7.5 Design Options" if ready else "❌ Не готово к 7.5"

    # Формируем отчёт
    lines = [
        f"<!-- BABOK 7.3 — Validation Report | Проект: {project_id} | {date.today()} -->",
        "",
        f"# 📋 Отчёт валидации требований",
        "",
        f"**Проект:** {project_id}  ",
        f"**Дата отчёта:** {date.today()}  ",
        f"**Готовность:** {ready_label}",
        "",
        "---",
        "",
        "## Сводка по требованиям",
        "",
        "| Показатель | Значение |",
        "|------------|----------|",
        f"| Всего активных req | {total} |",
        f"| ✅ Validated | {len(validated)} ({validated_pct}%) |",
        f"| 🔍 Verified (ещё не validated) | {len(verified_only)} |",
        f"| 📐 С success_criteria | {len(with_criteria)} ({criteria_pct}%) |",
        "",
    ]

    # Прогресс-бар
    filled = int(validated_pct / 10)
    bar = "█" * filled + "░" * (10 - filled)
    lines.append(f"**Прогресс валидации:** `[{bar}]` {validated_pct}%")
    lines.append("")

    # Assumptions
    lines += [
        "## Сводка по предположениям",
        "",
        "| Показатель | Значение |",
        "|------------|----------|",
        f"| Всего assumptions | {len(all_assum)} |",
        f"| 🔴 Открытых high-risk | {len(open_high)} |",
        f"| 🟡 Открытых medium-risk | {len(open_medium)} |",
        f"| 🟢 Открытых low-risk | {len(open_low)} |",
        f"| ✅ Закрытых | {len([a for a in all_assum if a['status'] != 'open'])} |",
        "",
    ]

    # Coverage matrix
    if goals:
        lines += [
            "## Coverage Matrix — Бизнес-цели",
            "",
            "| BG ID | Название | Покрыто? | Req |",
            "|-------|----------|---------|-----|",
        ]
        for g in goals:
            covered = g["id"] in covered_goals
            icon = "✅" if covered else "❌"
            covering_reqs = []
            for req in active_reqs:
                bfs_nodes = _bfs_to_business(repo, req["id"])
                bfs_ids = {n["id"] for n in bfs_nodes if n["id"] in goal_ids}
                title_m = {gi["id"] for gi in goals if _title_matches_goal(req.get("title",""), gi["title"])}
                if g["id"] in (bfs_ids | title_m):
                    covering_reqs.append(req["id"])
            req_str = ", ".join(f"`{r}`" for r in covering_reqs[:3])
            if len(covering_reqs) > 3:
                req_str += f" +{len(covering_reqs)-3}"
            lines.append(f"| `{g['id']}` | {g['title'][:40]} | {icon} | {req_str or '—'} |")
        lines.append("")

    # Orphan req
    if orphan_reqs:
        lines += [
            "## ❌ Req без трассировки к бизнес-целям",
            "",
            "> Пересмотри необходимость этих требований.",
            "",
        ]
        for r in orphan_reqs:
            lines.append(f"- `{r['id']}` ({r.get('type','')}) — {r.get('title','')}")
        lines.append("")

    # Непокрытые BG
    if uncovered_goals:
        lines += [
            "## ⚠️ Бизнес-цели без покрытия",
            "",
        ]
        for g in uncovered_goals:
            lines.append(f"- `{g['id']}` — {g['title']}")
        lines.append("")

    # Open high-risk assumptions
    if open_high:
        lines += [
            "## 🔴 Открытые High-Risk Assumptions",
            "",
            "| AS ID | Описание | Req | Назначено |",
            "|-------|----------|-----|-----------|",
        ]
        for a in open_high:
            desc_short = a["description"][:60] + ("..." if len(a["description"]) > 60 else "")
            req_str = ", ".join(f"`{r}`" for r in a.get("req_ids", []))
            lines.append(
                f"| `{a['assumption_id']}` | {desc_short} | {req_str} | {a.get('assigned_to') or '—'} |"
            )
        lines.append("")

    # Success criteria coverage
    if with_criteria:
        lines += [
            "## 📐 Покрытие критериями успеха",
            "",
            f"**{len(with_criteria)}/{total} req** ({criteria_pct}%) имеют success_criteria.",
            "",
        ]
        if criteria_pct < 50:
            lines.append("⚠️ Менее 50% req имеют success_criteria — добавь критерии для критичных req через `set_success_criteria`.")
        lines.append("")

    # Validated req по типам
    if validated:
        lines += [
            "## ✅ Validated требования",
            "",
        ]
        by_type: dict = {}
        for r in validated:
            t = r.get("type", "other")
            by_type.setdefault(t, []).append(r["id"])
        for req_type, ids in sorted(by_type.items()):
            lines.append(f"**{req_type}:** {', '.join(f'`{i}`' for i in sorted(ids))}")
        lines.append("")

    # Вердикт
    lines += [
        "---",
        "",
        "## Вердикт и следующие шаги",
        "",
    ]

    if ready:
        lines += [
            "### ✅ Готово к 7.5 Design Options",
            "",
            f"- **{len(validated)}** req в статусе `validated` готовы к работе над дизайном решения.",
            f"- Нет открытых high-risk assumptions.",
            f"- Все req трассируются к бизнес-целям.",
            "",
            "**Передай этот отчёт в 7.5:** приступай к определению вариантов дизайна.",
        ]
    else:
        reasons = []
        if not has_context:
            reasons.append("⚠️ Бизнес-контекст не задан — согласованность с целями не проверялась. "
                           "Вызовите `set_business_context` (или запустите 6.1/6.2) и повторите.")
        if validated_pct < 80:
            reasons.append(f"📊 Validated только {validated_pct}% req (рекомендуется ≥ 80%)")
        if open_high:
            reasons.append(f"🔴 {len(open_high)} открытых high-risk assumptions")
        if orphan_reqs:
            reasons.append(f"❌ {len(orphan_reqs)} req без трассировки к бизнес-целям")

        lines += [
            "### ❌ Не готово к 7.5",
            "",
        ]
        for r in reasons:
            lines.append(f"- {r}")
        lines += [
            "",
            "**Действия:**",
            "1. Закрой high-risk assumptions через `resolve_assumption`.",
            "2. Исправь orphan req — добавь трассировку или удали избыточные.",
            f"3. Validate оставшиеся req через `mark_req_validated`.",
            f"4. Повтори `get_validation_report` для обновлённого статуса.",
        ]

    content = "\n".join(lines)
    save_artifact(content, prefix="7_3_validation_report", project_id=project_id)
    return content


if __name__ == "__main__":
    mcp.run()
