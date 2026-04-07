"""
BABOK 7.3 — Validate Requirements
MCP-инструменты для валидации требований: проверка соответствия бизнес-целям,
управление предположениями, критерии успеха, статус validated.

Инструменты:
  - set_business_context       — создать/обновить бизнес-контекст проекта (суррогат Гл.6)
  - check_business_alignment   — проверить трассировку req к бизнес-целям (BFS + matching)
  - set_success_criteria       — привязать измеримый критерий успеха к req
  - log_assumption             — зафиксировать предположение (AS-001, ...)
  - resolve_assumption         — закрыть предположение (confirmed/refuted)
  - mark_req_validated         — статус verified → validated (предупреждения, не блокировки)
  - get_validation_report      — сводный отчёт: coverage matrix, сироты, assumptions, вердикт

ADR-030: {project}_business_context.json — суррогат Главы 6
ADR-031: {project}_assumptions.json — реестр предположений
ADR-032: set_success_criteria — необязательный шаг pipeline
ADR-033: mark_req_validated — предупреждения, не жёсткие блокировки

Читает: репозиторий 5.1 ({project}_traceability_repo.json)
Пишет: {project}_business_context.json, {project}_assumptions.json,
        статус validated в 5.1
Выход: Validation Report → 7.5 (Design Options)

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from collections import deque
from datetime import date
from typing import Optional
from mcp.server.fastmcp import FastMCP
from skills.common import save_artifact, logger, DATA_DIR

mcp = FastMCP("BABOK_Requirements_Validate")

REPO_FILENAME = "traceability_repo.json"
CONTEXT_FILENAME = "business_context.json"
ASSUMPTIONS_FILENAME = "assumptions.json"


# ---------------------------------------------------------------------------
# Утилиты — пути и загрузка файлов
# ---------------------------------------------------------------------------

def _safe(project_id: str) -> str:
    return project_id.lower().replace(" ", "_")


def _repo_path(project_id: str) -> str:
    return os.path.join(DATA_DIR, f"{_safe(project_id)}_{REPO_FILENAME}")


def _context_path(project_id: str) -> str:
    return os.path.join(DATA_DIR, f"{_safe(project_id)}_{CONTEXT_FILENAME}")


def _assumptions_path(project_id: str) -> str:
    return os.path.join(DATA_DIR, f"{_safe(project_id)}_{ASSUMPTIONS_FILENAME}")


def _load_repo(project_id: str) -> dict:
    path = _repo_path(project_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"project": project_id, "requirements": [], "links": [], "history": []}


def _save_repo(repo: dict) -> None:
    project_id = repo["project"]
    path = _repo_path(project_id)
    os.makedirs(DATA_DIR, exist_ok=True)
    repo["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)
    logger.info(f"Репозиторий 5.1 обновлён (7.3): {path}")


def _load_context(project_id: str) -> Optional[dict]:
    path = _context_path(project_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_context(data: dict) -> None:
    path = _context_path(data["project_id"])
    os.makedirs(DATA_DIR, exist_ok=True)
    data["updated_at"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Бизнес-контекст сохранён: {path}")


def _load_assumptions(project_id: str) -> dict:
    path = _assumptions_path(project_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "project": project_id,
        "assumptions": {},
        "stats": {"open": 0, "confirmed": 0, "refuted": 0},
        "created": str(date.today()),
        "updated": str(date.today()),
    }


def _save_assumptions(data: dict) -> None:
    path = _assumptions_path(data["project"])
    os.makedirs(DATA_DIR, exist_ok=True)
    data["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Assumptions обновлены: {path}")


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

def _bfs_to_business(repo: dict, start_id: str) -> list:
    """
    BFS-обход графа трассировки 5.1. Возвращает список узлов типа 'business'
    достижимых из start_id. Используется для check_business_alignment.
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
        if node and current != start_id:
            if node.get("type") == "business":
                business_nodes.append(node)

        # Переходим по всем рёбрам (в любую сторону)
        for link in links:
            neighbor = None
            if link.get("from") == current:
                neighbor = link.get("to")
            elif link.get("to") == current:
                neighbor = link.get("from")
            if neighbor and neighbor not in visited:
                queue.append(neighbor)

    return business_nodes


def _title_matches_goal(req_title: str, goal_title: str) -> bool:
    """
    Простой title-matching: проверяет пересечение ключевых слов (≥3 символа).
    Используется как второй метод поиска выравнивания.
    """
    req_words = set(w.lower() for w in req_title.split() if len(w) >= 5)
    goal_words = set(w.lower() for w in goal_title.split() if len(w) >= 5)
    return bool(req_words & goal_words)


# ---------------------------------------------------------------------------
# 7.3.1 — set_business_context (ADR-030)
# ---------------------------------------------------------------------------

@mcp.tool()
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
    BABOK 7.3 — Создаёт или обновляет бизнес-контекст проекта.
    ADR-030: суррогат Главы 6 (Strategy Analysis). Мигрировать при реализации 6.1/6.2.

    ⚠️ Вызывать один раз в начале работы над валидацией. При обновлении — предупреждение.

    Args:
        project_id:          Идентификатор проекта.
        business_goals_json: JSON-список бизнес-целей:
                             '[{"id":"BG-001","title":"...","description":"...","kpi":"..."}]'.
                             id должен начинаться с BG-.
        future_state:        Описание желаемого будущего состояния (Free State).
        solution_scope:      Границы решения: что входит, что не входит.
        potential_value:          Потенциальная ценность/выгода (необязательно).
        from_current_state_project_id: ⚠️ DEPRECATED — используйте from_strategy_project_id.
                                 Предзаполняет из данных 6.1. Оставлен для совместимости (ADR-055).
        from_strategy_project_id: Читает данные из 6.1 И 6.2 и предзаполняет цели, future_state,
                                 скоуп (ADR-065). Заменяет from_current_state_project_id.

    Returns:
        Подтверждение с кратким саммари бизнес-контекста.
    """
    logger.info(f"set_business_context: project_id=\'{project_id}\'")

    # ADR-065: новый параметр from_strategy_project_id читает 6.1 + 6.2
    prefill_status = ""
    if from_strategy_project_id.strip():
        safe_sp = from_strategy_project_id.lower().replace(" ", "_")
        fs_goals_path = os.path.join(DATA_DIR, f"{safe_sp}_future_state_goals.json")
        fs_state_path = os.path.join(DATA_DIR, f"{safe_sp}_future_state.json")
        fs_scope_path = os.path.join(DATA_DIR, f"{safe_sp}_future_state_scope.json")
        cs_needs_path = os.path.join(DATA_DIR, f"{safe_sp}_business_needs.json")

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
                            "id": f"BG-{idx_n:03d}",
                            "title": need.get("need_title", f"Потребность {idx_n}"),
                            "description": need.get("description", ""),
                            "kpi": need.get("cost_of_inaction", ""),
                            "source_bn": need.get("id", ""),
                        }
                        for idx_n, need in enumerate(needs_list, 1)
                    ]
                    business_goals_json = json.dumps(auto_goals, ensure_ascii=False)
                    prefill_parts.append(f"✅ Бизнес-цели предзаполнены из 6.1 BN ({len(auto_goals)} шт.)")

            if prefill_parts:
                prefill_status = "\n\n## Автозаполнение из 6.1+6.2 (ADR-065)\n\n" + "\n".join(prefill_parts)
            else:
                prefill_status = f"\n\n⚠️ Данные 6.1/6.2 для проекта `{from_strategy_project_id}` не найдены."

        except (json.JSONDecodeError, KeyError, IOError) as e:
            prefill_status = f"\n\n⚠️ Не удалось прочитать данные 6.1/6.2: {e}."

    # ADR-055: предзаполнение из 6.1 если передан from_current_state_project_id (deprecated)
    elif from_current_state_project_id.strip():
        prefill_status = "\n\n⚠️ Параметр `from_current_state_project_id` устарел. Используйте `from_strategy_project_id` (ADR-065)."
        safe_cs = from_current_state_project_id.lower().replace(" ", "_")
        needs_path = os.path.join(DATA_DIR, f"{safe_cs}_business_needs.json")
        scope_path = os.path.join(DATA_DIR, f"{safe_cs}_current_state_scope.json")

        if os.path.exists(needs_path):
            try:
                with open(needs_path, "r", encoding="utf-8") as f_n:
                    needs_data = json.load(f_n)
                needs_list = needs_data.get("needs", [])

                if (not business_goals_json.strip() or business_goals_json.strip() == "[]") and needs_list:
                    auto_goals = []
                    for idx_n, need in enumerate(needs_list, 1):
                        auto_goals.append({
                            "id": f"BG-{idx_n:03d}",
                            "title": need.get("need_title", f"Потребность {idx_n}"),
                            "description": need.get("description", ""),
                            "kpi": need.get("cost_of_inaction", ""),
                            "source_bn": need.get("id", ""),
                        })
                    business_goals_json = json.dumps(auto_goals, ensure_ascii=False)
                    mapping_parts = []
                    for i, n in enumerate(needs_list, 1):
                        mapping_parts.append(n.get("id", "?") + "→BG-" + str(i).zfill(3))
                    mapping = ", ".join(mapping_parts)
                    prefill_status += (
                        f"\n\n## Автозаполнение из 6.1 (ADR-055)\n\n"
                        f"✅ Бизнес-цели предзаполнены из {len(auto_goals)} "
                        f"бизнес-потребностей `{from_current_state_project_id}`.\n"
                        f"Маппинг: {mapping}"
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
        f"> ⚠️ **Временный суррогат Главы 6** — мигрировать при реализации задач 6.1/6.2 (ADR-030)",
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
def check_business_alignment(
    project_id: str,
    req_ids: str = "",
) -> str:
    """
    BABOK 7.3 — Проверяет трассировку требований к бизнес-целям.
    Методы: BFS-поиск по узлам типа 'business' в репозитории 5.1 +
            title-matching с BG-xxx из business_context.json.

    ADR-030: бизнес-цели берутся из {project}_business_context.json.

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
        # Берём verified req (и validated — переповтор не страшен)
        target_statuses = {"verified", "validated"}
        reqs_to_check = [r for r in all_reqs if r.get("status", "") in target_statuses]
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

        # Пропускаем бизнес-узлы самого репо и тест-узлы
        if req_type in ("business", "test"):
            continue

        # Метод 1: BFS к узлам типа 'business'
        bfs_nodes = _bfs_to_business(repo, req_id)
        bfs_goal_ids = {n["id"] for n in bfs_nodes if n["id"] in goal_ids}

        # Метод 2: title-matching с BG-xxx
        title_matched_goals = set()
        for g in goals:
            if _title_matches_goal(req.get("title", ""), g["title"]):
                title_matched_goals.add(g["id"])

        found_goals = bfs_goal_ids | title_matched_goals

        if found_goals:
            covered_goals |= found_goals
            aligned_reqs.append({
                "req_id": req_id,
                "title": req.get("title", ""),
                "aligned_goals": sorted(found_goals),
                "method": "bfs" if bfs_goal_ids else "title_match",
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
        f"| ✅ Aligned (есть трассировка к BG) | {len(aligned_reqs)} ({aligned_pct}%) |",
        f"| ❌ Orphan (нет трассировки к BG) | {len(orphan_reqs)} |",
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
            method_note = " _(BFS)_" if r["method"] == "bfs" else " _(title-match)_"
            goals_str = ", ".join(f"`{g}`" for g in r["aligned_goals"])
            lines.append(f"- `{r['req_id']}` — {r['title']} → {goals_str}{method_note}")
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
    save_artifact(content, prefix="7_3_business_alignment")
    return content


# ---------------------------------------------------------------------------
# 7.3.3 — set_success_criteria (ADR-032)
# ---------------------------------------------------------------------------

@mcp.tool()
def set_success_criteria(
    project_id: str,
    req_id: str,
    criteria_json: str,
) -> str:
    """
    BABOK 7.3 — Привязывает измеримый критерий успеха к требованию.
    Необязательный шаг pipeline (ADR-032). Рекомендуется для критичных req.

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
        f"| Target | {criteria['target']} |",
        f"| Метод измерения | {criteria['measurement_method']} |",
        f"| KPI ref | {kpi_ref or '—'} |",
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
def log_assumption(
    project_id: str,
    description: str,
    req_ids: str,
    risk_level: str,
    assigned_to: str = "",
) -> str:
    """
    BABOK 7.3 — Фиксирует предположение (assumption) с risk_level и связанными req.
    ADR-031: хранится в {project}_assumptions.json, нумерация AS-001/AS-002/...

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
        f"| Risk level | {icon} {risk_level} |",
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
def resolve_assumption(
    project_id: str,
    assumption_id: str,
    resolution: str,
    resolution_note: str,
) -> str:
    """
    BABOK 7.3 — Закрывает предположение как подтверждённое или опровергнутое.
    ADR-031: при refuted — предупреждение о связанных req.

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
        f"**Resolution note:** {resolution_note}",
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
def mark_req_validated(
    project_id: str,
    req_ids: str,
    force: bool = False,
) -> str:
    """
    BABOK 7.3 — Устанавливает статус 'validated' в репозитории 5.1.
    Предусловия (ADR-033): предупреждения, не жёсткие блокировки.

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

        # Предусловие 1: статус verified
        current_status = req.get("status", "draft")
        if current_status not in ("verified", "validated"):
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
            title_matched = {
                g["id"] for g in goals
                if _title_matches_goal(req.get("title", ""), g["title"])
            }
            if not (bfs_goal_ids | title_matched):
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
                           + (" [force override]" if force and warnings else ""),
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
    skip_types = {"business", "test"}
    active_reqs = [
        r for r in all_reqs
        if r.get("status") not in skip_statuses
        and r.get("type", "") not in skip_types
    ]
    total = len(active_reqs)

    if total == 0:
        return (
            f"⚠️ Нет активных требований подходящего типа в проекте `{project_id}`.\n"
            f"Проверь что требования созданы через инструменты 7.1."
        )

    validated = [r for r in active_reqs if r.get("status") == "validated"]
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
        bfs_nodes = _bfs_to_business(repo, req_id)
        bfs_goal_ids = {n["id"] for n in bfs_nodes if n["id"] in goal_ids}
        title_matched = {g["id"] for g in goals if _title_matches_goal(req.get("title", ""), g["title"])}
        found = bfs_goal_ids | title_matched
        if found:
            covered_goals |= found
        else:
            orphan_reqs.append(req)

    uncovered_goals = [g for g in goals if g["id"] not in covered_goals]

    # Вердикт готовности к 7.5
    ready = (
        validated_pct >= 80
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
            "## 📐 Criteria Success Coverage",
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
    save_artifact(content, prefix="7_3_validation_report")
    return content


if __name__ == "__main__":
    mcp.run()
