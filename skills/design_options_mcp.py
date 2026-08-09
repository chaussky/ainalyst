"""
BABOK 7.5 — Define Design Options
MCP tools for defining solution design options, allocating requirements across
versions, and comparing options.

Tools:
  - set_change_strategy      — manual/flat entry point for 6.4 data when 6.4 was not run; 6.4 writes the same file
  - create_design_option     — create/update a design option (build/buy/hybrid)
  - allocate_requirements    — semi-automatic allocation of req across versions
  - compare_design_options   — comparison matrix of options against criteria
  - save_design_options_report — final report → 7.6 (Analyze Value and Recommend Solution)

set_change_strategy — flat stand-in for 6.4; 6.4 (implemented) writes the SAME file, so the two coexist (6.4's rich contract wins, see the guard in set_change_strategy)
single file {project}_design_options.json with an options[] array
allocation — semi-automatic, versions v1/v2/out_of_scope, depends-conflict check

Reads:  {project}_traceability_repo.json (5.1) — dependency graph and priorities
        (5.3 priorities are NOT read from its file. They reach 7.5 through the 5.1
         repository, where save_prioritization_result writes each requirement's
         `priority` — see MUST_PRIORITIES.)
        {project}_business_context.json (7.3) — business goals (optional)
        {project}_architecture.json (7.4) — viewpoints and gaps (optional)
        {project}_change_strategy.json (6.4 surrogate) — constraints (optional)
Writes: {project}_design_options.json
        {project}_change_strategy.json
        7_5_design_options_*.md (через save_artifact)
Выход: Design Options Report → 7.6 (Analyze Value and Recommend Solution)

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date
from typing import Optional
from mcp.server.fastmcp import FastMCP
from skills.common import (write_json_artifact,
    save_artifact, logger, DATA_DIR, data_path, normalize_project_id,
    NON_REQUIREMENT_NODE_TYPES, MUST_PRIORITIES,
    read_json_artifact, guard_artifact_errors,
)

mcp = FastMCP("BABOK_Design_Options")

REPO_FILENAME = "traceability_repo.json"
DESIGN_OPTIONS_FILENAME = "design_options.json"
CHANGE_STRATEGY_FILENAME = "change_strategy.json"
CONTEXT_FILENAME = "business_context.json"
ARCHITECTURE_FILENAME = "architecture.json"

# Допустимые значения
VALID_APPROACHES = {"build", "buy", "hybrid"}
VALID_CHANGE_TYPES = {"technology", "process", "organizational", "hybrid"}
VALID_VERSIONS = {"v1", "v2", "out_of_scope"}
VALID_OPPORTUNITY_TYPES = {"efficiency", "information_access", "new_capability"}

# Маппинг MoSCoW/WSJF приоритетов на версии (ADR-041)
PRIORITY_TO_VERSION = {
    "Must": "v1",
    "High": "v1",
    "Should": "v1",   # Should → v1, но BA может переопределить на v2
    "Medium": "v2",
    "Could": "v2",
    "Low": "v2",
    "Won't": "out_of_scope",
}

# "Critical" priorities for req_coverage (audit finding 7.5-A). 7.1 sets High/Medium/Low; 5.3 sets
# MoSCoW. Both Must and High map to v1 in PRIORITY_TO_VERSION, so req_coverage must count both —
# otherwise a project that skipped 5.3 (repo priority = High) always shows req_coverage = N/A.
# MUST_PRIORITIES itself is imported from common.py: this module used to keep an identical local
# copy, which is exactly the two-copies-drift-apart shape the shared constants exist to prevent.

# Default comparison criteria
DEFAULT_CRITERIA = [
    {"id": "cost", "label": "Стоимость реализации", "weight": "high"},
    {"id": "speed", "label": "Скорость запуска (time-to-market)", "weight": "high"},
    {"id": "risk", "label": "Совокупный риск", "weight": "medium"},
    {"id": "req_coverage", "label": "Покрытие Must-требований", "weight": "high"},
    {"id": "flexibility", "label": "Гибкость (изменения после запуска)", "weight": "medium"},
]


# ---------------------------------------------------------------------------
# Утилиты — пути и загрузка файлов
# ---------------------------------------------------------------------------

def _safe(project_id: str) -> str:
    return normalize_project_id(project_id)


def _repo_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{REPO_FILENAME}")


def _design_options_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{DESIGN_OPTIONS_FILENAME}")


def _change_strategy_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{CHANGE_STRATEGY_FILENAME}")


def _context_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{CONTEXT_FILENAME}")


def _architecture_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{ARCHITECTURE_FILENAME}")


def _load_json(path: str, default: dict) -> dict:
    if os.path.exists(path):
        # Corrupt -> CorruptArtifactError, converted to a ❌ line at the tool
        # boundary by guard_artifact_errors (the chapters-5 / 7.1-7.3 pattern).
        return read_json_artifact(path, "7.5 stored artifact")
    return default


def _save_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data["updated"] = str(date.today())
    write_json_artifact(path, data)


def _load_repo(project_id: str) -> dict:
    return _load_json(_repo_path(project_id), {
        "project": project_id, "requirements": [], "links": [], "history": []
    })


def _load_design_options(project_id: str) -> dict:
    return _load_json(_design_options_path(project_id), {
        "project_id": project_id,
        "change_strategy_ref": "",
        "options": [],
        "allocation": {},
        "created": str(date.today()),
        "updated": str(date.today()),
    })


def _save_design_options(data: dict) -> None:
    project_id = data["project_id"]
    _save_json(_design_options_path(project_id), data)
    logger.info(f"Design options сохранены: {_design_options_path(project_id)}")


def _load_change_strategy(project_id: str) -> Optional[dict]:
    path = _change_strategy_path(project_id)
    if os.path.exists(path):
        # Corrupt -> CorruptArtifactError, converted to a ❌ line at the tool
        # boundary by guard_artifact_errors (the chapters-5 / 7.1-7.3 pattern).
        return read_json_artifact(path, "7.5 stored artifact")
    return None


def _is_rich_strategy(strategy: Optional[dict]) -> bool:
    """True if change_strategy.json is the RICH 6.4 format (the real Chapter 6 contract), not the
    flat 7.5 surrogate (audit finding 7.5-B). 6.4 nests `scope` as a dict and adds solution_scope /
    change_strategy sections; the 7.5 surrogate has a flat string `scope` and top-level change_type.
    """
    if not strategy:
        return False
    return isinstance(strategy.get("scope"), dict) or \
        "solution_scope" in strategy or "change_strategy" in strategy


def _extract_strategy_fields(strategy: Optional[dict]) -> Optional[dict]:
    """Normalises either the 6.4 rich format or the 7.5 flat surrogate into a flat
    {change_type, scope, constraints, timeline} for display (audit finding 7.5-B)."""
    if not strategy:
        return None
    if _is_rich_strategy(strategy):
        scope6 = strategy.get("scope", {}) or {}
        sol = strategy.get("solution_scope", {}) or {}
        thm = scope6.get("time_horizon_months")
        excluded = sol.get("explicitly_excluded", []) or []
        scope_txt = sol.get("scope_summary", "") or ""
        if not scope_txt:
            caps = sol.get("capabilities", []) or []
            if caps:
                scope_txt = "Capabilities: " + ", ".join(
                    str(c.get("name", c) if isinstance(c, dict) else c) for c in caps[:5])
        constraints = ("Out of scope: " + "; ".join(str(e) for e in excluded)) if excluded \
            else (scope6.get("ba_notes", "") or "—")
        return {
            "change_type": scope6.get("change_type", "—"),
            "scope": scope_txt or "—",
            "constraints": constraints,
            "timeline": f"{thm} months" if thm else "—",
        }
    # 7.5 flat surrogate
    return {
        "change_type": strategy.get("change_type", "—"),
        "scope": strategy.get("scope", "—"),
        "constraints": strategy.get("constraints", "—"),
        "timeline": strategy.get("timeline", "—"),
    }


def _load_context(project_id: str) -> Optional[dict]:
    return _load_json(_context_path(project_id), None) if os.path.exists(_context_path(project_id)) else None


def _load_architecture(project_id: str) -> Optional[dict]:
    return _load_json(_architecture_path(project_id), None) if os.path.exists(_architecture_path(project_id)) else None


def _find_req(repo: dict, req_id: str) -> Optional[dict]:
    for r in repo.get("requirements", []):
        if r["id"] == req_id:
            return r
    return None


def _get_depends_links(repo: dict) -> list:
    """Возвращает список (from, to) для связей типа depends."""
    return [
        (link["from"], link["to"])
        for link in repo.get("links", [])
        if link.get("relation") == "depends"
    ]


# ---------------------------------------------------------------------------
# 7.5.1 — set_change_strategy (суррогат 6.4, ADR-039)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def set_change_strategy(
    project_id: str,
    change_type: str,
    scope: str,
    constraints: str,
    timeline: str,
    notes: str = "",
) -> str:
    """
    BABOK 7.5 / flat stand-in for 6.4 — Records the change strategy for the project.
    lets 7.5 run standalone by entering the change strategy by hand. Chapter 6
    (Strategy Analysis) is implemented; task 6.4 writes the SAME file with a richer
    contract, and a real 6.4 contract is never clobbered (see the guard below).

    Change Strategy определяет стратегический контекст для Design Options:
    какой тип изменения происходит, что входит в скоуп, какие ограничения действуют.

    Args:
        project_id:  Project identifier.
        change_type: Change type: technology | process | organizational | hybrid.
                     technology — replacing/introducing technology.
                     process — changing business processes.
                     organizational — restructuring, roles, responsibilities.
                     hybrid — several types at once.

                     ⚠️ THIS IS NOT THE 6.4 VOCABULARY. Task 6.4 asks the same
                     question with five longer answers, and the two sets share no
                     value, so 6.4's answer is not accepted here and vice versa:

                       6.4 `technology_implementation` ~ `technology`  (clean match)
                       6.4 `process_improvement`       ~ `process`     (clean match)
                       6.4 `transformation`            — no counterpart; usually
                            `hybrid`, or `organizational` if the change is purely
                            structural
                       6.4 `regulatory_compliance`     — no counterpart; choose by
                            what the work actually is, most often `process`
                       6.4 `other`                     — no counterpart; choose by
                            what dominates

                     If this project HAS a 6.4 change strategy, you do not need this
                     tool at all: 7.5 reads 6.4 directly, and the call is refused
                     before any of these values is even looked at. The two vocabularies
                     are merged for real during the CLI port, not here — a merge means
                     migrating strategies already written to disk.
        scope:       Change scope: what changes, what stays the same.
                     Example: "Replace the legacy CRM for the sales department. Financial accounting out of scope."
        constraints: Key constraints: budget, deadlines, technologies, regulations.
                     Example: "Budget $200k. Timeline — 12 months. Cloud solutions only."
        timeline:    Timeframe and phases.
                     Example: "Phase 1 (MVP): Q2 2025. Phase 2 (full): Q4 2025."
        notes:       Additional notes (optional).

    Returns:
        Подтверждение с сохранённой стратегией изменения.
    """
    logger.info(f"set_change_strategy: project_id='{project_id}', change_type='{change_type}'")

    # This check comes FIRST, before any parameter is judged (pre-release E2E finding
    # E1-1). It answers a question the analyst is actually asking, and it used to sit
    # three validations below — unreachable for exactly the people it was written for.
    #
    # 6.4 and 7.5 name change types from vocabularies that share NO value
    # (`technology_implementation` there, `technology` here). So a BA who completed 6.4
    # and reached for the obvious next tool was handed "❌ Invalid change_type … Valid
    # values: hybrid, organizational, process, technology" — a dead end quoting four
    # words they had never seen — while the sentence that resolves their situation,
    # "7.5 reads the 6.4 Change Strategy directly, no surrogate is needed", waited
    # below. Nothing was ever overwritten; the answer was simply out of reach.
    #
    # Same class as branch-review A-2: a guard written correctly and placed after the
    # thing it guards.
    existing = _load_change_strategy(project_id)
    if _is_rich_strategy(existing):
        return (
            f"⚠️ `{project_id}_change_strategy.json` is already populated by task 6.4 "
            f"(the richer Change Strategy contract for 7.x/8.x). **Not overwriting.**\n\n"
            f"7.5 reads the 6.4 Change Strategy directly — no surrogate is needed. "
            f"To change the strategy, edit it via the 6.4 tools (`change_strategy` phase)."
        )

    if change_type not in VALID_CHANGE_TYPES:
        return (
            f"❌ Invalid change_type: '{change_type}'.\n\n"
            f"Valid values: {', '.join(sorted(VALID_CHANGE_TYPES))}\n"
            f"If this project already has a 6.4 Change Strategy, you do not need this "
            f"tool at all — 7.5 reads 6.4 directly. 6.4 uses its own, longer vocabulary "
            f"(`technology_implementation`, `process_improvement`, …); the two are not "
            f"interchangeable."
        )

    if not scope.strip():
        return "❌ scope не может быть пустым — опиши что входит и что не входит в скоуп изменения."

    if not constraints.strip():
        return "❌ constraints не может быть пустым — укажи хотя бы одно ключевое ограничение."

    if not timeline.strip():
        return "❌ timeline не может быть пустым — укажи временные рамки или фазы."

    path = _change_strategy_path(project_id)
    is_update = os.path.exists(path)

    strategy = {
        "project_id": project_id,
        "change_type": change_type,
        "scope": scope,
        "constraints": constraints,
        "timeline": timeline,
        "notes": notes,
        "created": str(date.today()) if not is_update else _load_change_strategy(project_id).get("created", str(date.today())),
        "updated": str(date.today()),
    }

    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_json_artifact(path, strategy)

    # Обновляем ссылку в design_options если файл существует
    do_data = _load_design_options(project_id)
    do_data["change_strategy_ref"] = path
    _save_design_options(do_data)

    action = "обновлена" if is_update else "зафиксирована"

    lines = [
        f"✅ Change Strategy **{action}** — проект `{project_id}`",
        "",
        f"| Поле | Значение |",
        f"|------|----------|",
        f"| Тип изменения | `{change_type}` |",
        f"| Дата | {date.today()} |",
        "",
        f"**Скоуп:** {scope}",
        "",
        f"**Ограничения:** {constraints}",
        "",
        f"**Временные рамки:** {timeline}",
    ]

    if notes:
        lines += ["", f"**Примечания:** {notes}"]

    lines += [
        "",
        "> ℹ️ **Entered manually in 7.5.** Task 6.4 (Define Change Strategy) writes this",
        "> same strategy automatically when you run Chapter 6 — and its richer contract wins.",
        "",
        "---",
        "",
        "**Следующий шаг:**",
        f"`create_design_option(project_id='{project_id}', option_id='OPT-001', ...)` — создай первый вариант дизайна.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.5.2 — create_design_option (ADR-040)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def create_design_option(
    project_id: str,
    option_id: str,
    title: str,
    approach: str,
    components_json: str,
    improvement_opportunities_json: str,
    effectiveness_measures_json: str,
    notes: str = "",
    vendor_notes: str = "",
) -> str:
    """
    BABOK 7.5 — Creates or updates a solution design option.
    options accumulate in {project}_design_options.json.
    Idempotent by option_id: calling again updates the existing option.

    Рекомендуется создавать 2–3 варианта для сравнения:
    обычно Build (разработка), Buy (готовое решение) и Hybrid (комбинация).

    Args:
        project_id:      Идентификатор проекта.
        option_id:       Уникальный ID варианта: OPT-001, OPT-002, OPT-003.
        title:           Название варианта: «Разработка собственной системы», «Salesforce CRM».
        approach:        Подход: build | buy | hybrid.
                         build — разработка с нуля.
                         buy — готовое решение / SaaS.
                         hybrid — комбинация своего и готового.
        components_json: JSON-список компонентов решения.
                         Пример: '["Backend API", "Web UI", "PostgreSQL", "Интеграционный слой"]'
        improvement_opportunities_json: JSON-список возможностей улучшения бизнеса.
                         Каждый элемент: {"type": "efficiency|information_access|new_capability", "description": "..."}
                         Пример: '[{"type": "efficiency", "description": "Автоматическое формирование отчётов"}]'
        effectiveness_measures_json: JSON-список метрик эффективности решения.
                         Пример: '["Снижение времени обработки заявки с 2 ч до 15 мин", "NPS > 8"]'
        notes:           Дополнительные заметки по варианту (необязательно).
        vendor_notes:    Оценка вендора — для подходов buy/hybrid (необязательно).
                         Включи: название вендора, стоимость, ограничения, референсы.

    Returns:
        Подтверждение создания/обновления варианта дизайна.
    """
    logger.info(f"create_design_option: project_id='{project_id}', option_id='{option_id}'")

    # Валидация
    if not option_id.strip():
        return "❌ option_id не может быть пустым. Используй формат: OPT-001, OPT-002."

    if approach not in VALID_APPROACHES:
        return (
            f"❌ Invalid approach: '{approach}'.\n\n"
            f"Valid values: {', '.join(sorted(VALID_APPROACHES))}"
        )

    if not title.strip():
        return "❌ title не может быть пустым — укажи название варианта."

    # Парсинг components
    try:
        components = json.loads(components_json)
        if not isinstance(components, list):
            raise ValueError("Ожидается список")
        if not components:
            raise ValueError("Список компонентов не должен быть пустым")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Failed to parse components_json: {e}\n\n"
            f"Expected a non-empty JSON list: '[\"Backend API\", \"Web UI\"]'"
        )

    # Парсинг improvement_opportunities
    try:
        opportunities = json.loads(improvement_opportunities_json)
        if not isinstance(opportunities, list):
            raise ValueError("Ожидается список")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Failed to parse improvement_opportunities_json: {e}\n\n"
            f"Expected a JSON list: '[{{\"type\": \"efficiency\", \"description\": \"...\"}}]'"
        )

    # Валидация типов opportunities
    invalid_types = [
        o.get("type", "") for o in opportunities
        if isinstance(o, dict) and o.get("type", "") not in VALID_OPPORTUNITY_TYPES
    ]
    if invalid_types:
        return (
            f"❌ Invalid improvement opportunity types: {invalid_types}\n\n"
            f"Valid types: {', '.join(sorted(VALID_OPPORTUNITY_TYPES))}"
        )

    # Парсинг effectiveness_measures
    try:
        measures = json.loads(effectiveness_measures_json)
        if not isinstance(measures, list):
            raise ValueError("Ожидается список")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Failed to parse effectiveness_measures_json: {e}\n\n"
            f"Expected a JSON list: '[\"Reduce processing time by 40%\"]'"
        )

    # Предупреждение: vendor_notes рекомендуется для buy/hybrid
    vendor_warning = ""
    if approach in ("buy", "hybrid") and not vendor_notes.strip():
        vendor_warning = (
            "\n\n> ℹ️ **Recommendation:** for approach `{approach}` it's recommended to fill in `vendor_notes` "
            "— specify the vendor, cost, constraints, references."
        ).format(approach=approach)

    # Загружаем и обновляем
    do_data = _load_design_options(project_id)
    existing_idx = next((i for i, o in enumerate(do_data["options"]) if o["option_id"] == option_id), -1)
    is_update = existing_idx >= 0

    option = {
        "option_id": option_id,
        "title": title,
        "approach": approach,
        "components": components,
        "improvement_opportunities": opportunities,
        "effectiveness_measures": measures,
        "notes": notes,
        "vendor_notes": vendor_notes,
        "created": str(date.today()) if not is_update else do_data["options"][existing_idx].get("created", str(date.today())),
        "updated": str(date.today()),
    }

    if is_update:
        do_data["options"][existing_idx] = option
    else:
        do_data["options"].append(option)

    _save_design_options(do_data)

    action = "обновлён" if is_update else "создан"
    total_options = len(do_data["options"])

    lines = [
        f"✅ Вариант дизайна **{action}**: `{option_id}`",
        "",
        f"| Поле | Значение |",
        f"|------|----------|",
        f"| ID | `{option_id}` |",
        f"| Название | {title} |",
        f"| Подход | `{approach}` |",
        f"| Компоненты | {len(components)} |",
        f"| Возможности улучшения | {len(opportunities)} |",
        f"| Метрики эффективности | {len(measures)} |",
        f"| Всего вариантов в файле | {total_options} |",
        "",
        "**Компоненты:**",
    ]

    for c in components:
        lines.append(f"- {c}")

    if opportunities:
        lines += ["", "**Возможности улучшения бизнеса:**", ""]
        type_icons = {
            "efficiency": "⚡ Эффективность",
            "information_access": "📊 Доступ к информации",
            "new_capability": "🚀 Новая возможность",
        }
        for opp in opportunities:
            t = opp.get("type", "")
            label = type_icons.get(t, t)
            lines.append(f"- **{label}:** {opp.get('description', '')}")

    if measures:
        lines += ["", "**Метрики эффективности:**"]
        for m in measures:
            lines.append(f"- {m}")

    if vendor_notes:
        lines += ["", f"**Вендор:** {vendor_notes}"]

    if vendor_warning:
        lines.append(vendor_warning)

    lines += [
        "",
        "---",
        "",
        "**Следующие шаги:**",
    ]

    if total_options < 2:
        lines.append(
            f"`create_design_option(project_id='{project_id}', option_id='OPT-{total_options + 1:03d}', ...)` — создай ещё вариант для сравнения."
        )
    else:
        lines.append(
            f"`allocate_requirements(project_id='{project_id}', option_id='{option_id}', auto_suggest=True)` — распредели req по версиям."
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.5.3 — allocate_requirements (ADR-041)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def allocate_requirements(
    project_id: str,
    option_id: str,
    assignments_json: str = "[]",
    auto_suggest: bool = True,
) -> str:
    """
    BABOK 7.5 — Semi-automatic allocation of requirements across solution versions.
    reads priorities from the 5.1 repository, proposes an allocation,
    the BA confirms it or passes overrides via assignments_json.

    Версии: v1 (MVP) / v2 (следующая фаза) / out_of_scope (вне проекта).

    Алгоритм auto_suggest (простой вариант):
      Must/High → v1
      Should → v1 (BA может переопределить на v2)
      Could/Medium → v2
      Won't/Low → out_of_scope
      Без приоритета → предупреждение, BA решает вручную

    После утверждения — проверяет depends-конфликты в графе 5.1:
    если req A (v1) depends от req B (v2) — предупреждение.

    Args:
        project_id:       Идентификатор проекта.
        option_id:        ID варианта дизайна (из create_design_option).
        assignments_json: JSON-список ручных назначений (переопределяют auto_suggest).
                          Формат: '[{"req_id": "FR-001", "version": "v1", "rationale": "..."}]'
                          Версии: v1 | v2 | out_of_scope.
                          Передавай только те req, которые хочешь переопределить.
        auto_suggest:     True — сначала предложить распределение по приоритетам (рекомендуется).
                          False — только записать assignments_json без авто-предложения.

    Returns:
        Allocation map с предложением / результатом + предупреждения о depends-конфликтах.
    """
    logger.info(f"allocate_requirements: project_id='{project_id}', option_id='{option_id}'")

    # Проверяем option_id
    do_data = _load_design_options(project_id)
    option = next((o for o in do_data["options"] if o["option_id"] == option_id), None)
    if option is None:
        return (
            f"❌ Design option `{option_id}` not found in project `{project_id}`.\n\n"
            f"Existing options: {[o['option_id'] for o in do_data['options']]}\n"
            f"First call `create_design_option`."
        )

    # Парсинг assignments
    try:
        assignments_list = json.loads(assignments_json) if assignments_json.strip() else []
        if not isinstance(assignments_list, list):
            raise ValueError("Ожидается список")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Failed to parse assignments_json: {e}\n\n"
            f"Expected a JSON list: '[{{\"req_id\": \"FR-001\", \"version\": \"v1\", \"rationale\": \"...\"}}]'\n"
            f"Or pass an empty list '[]' to use auto_suggest only."
        )

    # Валидация assignments
    invalid_versions = [
        a.get("version", "") for a in assignments_list
        if isinstance(a, dict) and a.get("version", "") not in VALID_VERSIONS
    ]
    if invalid_versions:
        return (
            f"❌ Invalid versions in assignments: {invalid_versions}\n\n"
            f"Valid versions: {', '.join(sorted(VALID_VERSIONS))}"
        )

    assignments_map = {
        a["req_id"]: {"version": a["version"], "rationale": a.get("rationale", "")}
        for a in assignments_list
        if isinstance(a, dict) and "req_id" in a and "version" in a
    }

    # Загружаем репозиторий 5.1
    repo = _load_repo(project_id)
    # Role filter from common.py: the hand-written set {business, test,
    # change_request} predated the 6.1/6.2/6.3/6.4 node types, so goals, needs,
    # risks and the 6.4 scope node landed in "Requirements without priority" and the
    # BA was asked to assign a business goal to v1/v2/out_of_scope.
    all_reqs = [
        r for r in repo.get("requirements", [])
        if r.get("type", "") not in NON_REQUIREMENT_NODE_TYPES
    ]

    if not all_reqs:
        return (
            f"⚠️ The 5.1 repository for project `{project_id}` is empty or has no requirements.\n\n"
            f"Create requirements via the 7.1 tools before allocation."
        )

    lines = [
        f"<!-- BABOK 7.5 — Allocation | Проект: {project_id} | Вариант: {option_id} | {date.today()} -->",
        "",
        f"# 📦 Allocation требований — {option_id}: {option['title']}",
        "",
        f"**Проект:** {project_id}  ",
        f"**Вариант:** {option_id} — {option['title']} (`{option['approach']}`)  ",
        f"**Дата:** {date.today()}",
        "",
    ]

    # ------------------------------------------------------------------
    # auto_suggest: предлагаем распределение по приоритетам
    # ------------------------------------------------------------------

    no_priority_reqs = []
    suggested: dict = {}  # req_id → {"version": ..., "source": "auto"|"manual", "rationale": ""}

    if auto_suggest:
        for req in all_reqs:
            req_id = req["id"]
            priority = req.get("priority", "")

            # Ручное переопределение имеет приоритет
            if req_id in assignments_map:
                suggested[req_id] = {
                    "version": assignments_map[req_id]["version"],
                    "rationale": assignments_map[req_id]["rationale"],
                    "source": "manual",
                }
                continue

            # Авто-предложение по приоритету
            if priority and priority in PRIORITY_TO_VERSION:
                suggested[req_id] = {
                    "version": PRIORITY_TO_VERSION[priority],
                    "rationale": f"Auto: {priority} → {PRIORITY_TO_VERSION[priority]}",
                    "source": "auto",
                }
            else:
                no_priority_reqs.append(req)

    else:
        # Только ручные назначения
        for req_id, data in assignments_map.items():
            suggested[req_id] = {
                "version": data["version"],
                "rationale": data["rationale"],
                "source": "manual",
            }

    # ------------------------------------------------------------------
    # Формируем allocation map
    # ------------------------------------------------------------------

    allocation_map: dict = {}
    for req_id, data in suggested.items():
        allocation_map[req_id] = {
            "version": data["version"],
            "option_id": option_id,
            "rationale": data["rationale"],
            "source": data["source"],
        }

    # Статистика по версиям
    version_counts: dict = {"v1": [], "v2": [], "out_of_scope": []}
    auto_count = 0
    manual_count = 0
    for req_id, data in allocation_map.items():
        v = data["version"]
        if v in version_counts:
            version_counts[v].append(req_id)
        if data["source"] == "auto":
            auto_count += 1
        else:
            manual_count += 1

    lines += [
        "## Сводка распределения",
        "",
        f"| Версия | Количество req |",
        f"|--------|---------------|",
        f"| v1 (MVP) | {len(version_counts['v1'])} |",
        f"| v2 (Phase 2) | {len(version_counts['v2'])} |",
        f"| out_of_scope | {len(version_counts['out_of_scope'])} |",
        f"| ⚠️ Без приоритета | {len(no_priority_reqs)} |",
        f"| **Всего** | **{len(allocation_map) + len(no_priority_reqs)}** |",
        "",
        f"_Авто-распределено: {auto_count}, ручное переопределение: {manual_count}_",
        "",
    ]

    # Таблицы по версиям
    for version_key, version_label in [("v1", "v1 — MVP"), ("v2", "v2 — Phase 2"), ("out_of_scope", "out_of_scope — вне проекта")]:
        ids_in_version = version_counts[version_key]
        if not ids_in_version:
            continue
        lines += [
            f"## 📌 {version_label} ({len(ids_in_version)} req)",
            "",
            "| ID | Тип | Название | Приоритет | Источник | Обоснование |",
            "|----|-----|----------|-----------|----------|-------------|",
        ]
        for req_id in ids_in_version:
            req = next((r for r in all_reqs if r["id"] == req_id), None)
            if req:
                prio = req.get("priority", "—")
                title_short = req.get("title", "")[:50]
                req_type = req.get("type", "?")
                source = allocation_map[req_id]["source"]
                rationale = allocation_map[req_id]["rationale"][:60]
                source_icon = "✋ ручн." if source == "manual" else "🤖 авто"
                lines.append(
                    f"| `{req_id}` | {req_type} | {title_short} | {prio} | {source_icon} | {rationale} |"
                )
        lines.append("")

    # Req без приоритета
    if no_priority_reqs:
        lines += [
            "## ⚠️ Требования без приоритета",
            "",
            "> Эти req не были приоритизированы в задаче 5.3.",
            "> BA должен вручную назначить их версию через `assignments_json`.",
            "",
            "| ID | Тип | Название |",
            "|----|-----|---------|",
        ]
        for req in no_priority_reqs:
            lines.append(f"| `{req['id']}` | {req.get('type', '?')} | {req.get('title', '')[:60]} |")
        lines.append("")

    # ------------------------------------------------------------------
    # Проверка depends-конфликтов
    # ------------------------------------------------------------------

    depends_links = _get_depends_links(repo)
    conflicts = []

    for from_id, to_id in depends_links:
        from_alloc = allocation_map.get(from_id)
        to_alloc = allocation_map.get(to_id)

        if from_alloc is None or to_alloc is None:
            continue  # req не в allocation — пропускаем

        from_v = from_alloc["version"]
        to_v = to_alloc["version"]

        # Конфликт: req A (v1) depends req B (v2 или out_of_scope)
        version_order = {"v1": 1, "v2": 2, "out_of_scope": 3}
        if version_order.get(from_v, 0) < version_order.get(to_v, 0):
            from_req = _find_req(repo, from_id)
            to_req = _find_req(repo, to_id)
            conflicts.append({
                "from_id": from_id,
                "from_title": from_req.get("title", "") if from_req else "",
                "from_version": from_v,
                "to_id": to_id,
                "to_title": to_req.get("title", "") if to_req else "",
                "to_version": to_v,
            })

    if conflicts:
        lines += [
            "## ⚠️ Конфликты depends-зависимостей",
            "",
            "> Следующие req имеют конфликт: req A (v1) depends req B (v2/out_of_scope).",
            "> Это значит v1 не может быть реализован без B.",
            "> **Рекомендуется:** переместить B в v1 или пересмотреть зависимость в 5.1.",
            "",
            "| Req A (раньше) | Версия | depends | Req B (зависимость) | Версия |",
            "|----------------|--------|---------|---------------------|--------|",
        ]
        for c in conflicts:
            lines.append(
                f"| `{c['from_id']}` {c['from_title'][:30]} | `{c['from_version']}` | → | "
                f"`{c['to_id']}` {c['to_title'][:30]} | `{c['to_version']}` |"
            )
        lines += [
            "",
            f"_Всего конфликтов: {len(conflicts)}_",
            "",
        ]
    else:
        lines += [
            "## ✅ Конфликты зависимостей",
            "",
            "Нарушений depends-зависимостей между версиями не обнаружено.",
            "",
        ]

    # ------------------------------------------------------------------
    # Сохраняем allocation в design_options.json
    # ------------------------------------------------------------------

    # Обновляем только req из текущего allocation (не перетираем другие варианты)
    for req_id, data in allocation_map.items():
        do_data["allocation"][req_id] = data

    _save_design_options(do_data)

    lines += [
        "---",
        "",
        f"Allocation для варианта `{option_id}` сохранён в `{_safe(project_id)}_design_options.json`.",
        "",
        "**Следующие шаги:**",
    ]

    if no_priority_reqs:
        lines.append(
            f"1. Назначь req без приоритета вручную: передай `assignments_json` с вариантом версии."
        )

    if conflicts:
        lines.append(
            f"{'2' if no_priority_reqs else '1'}. Разреши {len(conflicts)} depends-конфликт(ов): "
            "перемести зависимости в ту же версию или пересмотри связи в 5.1."
        )

    lines.append(
        f"{'3' if (no_priority_reqs and conflicts) else '2' if (no_priority_reqs or conflicts) else '1'}. "
        f"`compare_design_options(project_id='{project_id}')` — сравни варианты после allocation."
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.5.4 — compare_design_options
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def compare_design_options(
    project_id: str,
    criteria_json: str = "[]",
) -> str:
    """
    BABOK 7.5 — Строит сравнительную матрицу всех вариантов дизайна по критериям.
    Читает все варианты из {project}_design_options.json.

    Дефолтные критерии сравнения: стоимость, скорость, риски, покрытие req, гибкость.
    BA может дополнить кастомными критериями через criteria_json.

    Покрытие Must-требований рассчитывается автоматически по данным allocation.

    Args:
        project_id:    Идентификатор проекта.
        criteria_json: JSON-список кастомных критериев сравнения (дополняет дефолтные).
                       Формат: '[{"id": "vendor_support", "label": "Поддержка вендора", "weight": "medium"}]'
                       Дефолтные критерии всегда включаются.
                       Передай '[]' для использования только дефолтных критериев.

    Returns:
        Comparison Document: сравнительная матрица для стейкхолдеров.
    """
    logger.info(f"compare_design_options: project_id='{project_id}'")

    do_data = _load_design_options(project_id)
    options = do_data.get("options", [])

    if not options:
        return (
            f"⚠️ No design options for project `{project_id}`.\n\n"
            f"First create options via `create_design_option`."
        )

    if len(options) < 2:
        return (
            f"⚠️ At least 2 design options are needed for comparison.\n\n"
            f"Current options: {len(options)}. Create one more via `create_design_option`."
        )

    # Парсинг кастомных критериев
    try:
        custom_criteria = json.loads(criteria_json) if criteria_json.strip() else []
        if not isinstance(custom_criteria, list):
            raise ValueError("Ожидается список")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Failed to parse criteria_json: {e}\n\n"
            f"Expected a JSON list: '[{{\"id\": \"vendor_support\", \"label\": \"Vendor support\", \"weight\": \"medium\"}}]'"
        )

    all_criteria = DEFAULT_CRITERIA + custom_criteria

    # Рассчитываем req_coverage автоматически
    repo = _load_repo(project_id)
    all_reqs = [r for r in repo.get("requirements", []) if r.get("priority") in MUST_PRIORITIES]
    must_count = len(all_reqs)
    must_ids = {r["id"] for r in all_reqs}

    allocation = do_data.get("allocation", {})

    def _calc_coverage(option_id: str) -> str:
        """Рассчитывает % Must-req в v1 для варианта."""
        if must_count == 0:
            return "N/A"
        v1_must = sum(
            1 for req_id, data in allocation.items()
            if data.get("option_id") == option_id
            and data.get("version") == "v1"
            and req_id in must_ids
        )
        pct = round(v1_must / must_count * 100)
        return f"{pct}% ({v1_must}/{must_count})"

    lines = [
        f"<!-- BABOK 7.5 — Design Options Comparison | Проект: {project_id} | {date.today()} -->",
        "",
        f"# 📊 Сравнение вариантов дизайна — {project_id}",
        "",
        f"**Дата:** {date.today()}  ",
        f"**Вариантов:** {len(options)}  ",
        f"**Критериев:** {len(all_criteria)} ({len(DEFAULT_CRITERIA)} дефолтных + {len(custom_criteria)} кастомных)",
        "",
        "---",
        "",
    ]

    # Краткое описание вариантов
    lines += [
        "## Варианты дизайна",
        "",
        "| ID | Название | Подход | Компоненты | Возможности улучшения |",
        "|----|----------|--------|-----------|----------------------|",
    ]

    for opt in options:
        approach_icons = {"build": "🔨 Build", "buy": "🛒 Buy", "hybrid": "🔀 Hybrid"}
        approach_label = approach_icons.get(opt.get("approach", ""), opt.get("approach", ""))
        comp_count = len(opt.get("components", []))
        opp_count = len(opt.get("improvement_opportunities", []))
        lines.append(
            f"| `{opt['option_id']}` | {opt['title']} | {approach_label} | {comp_count} | {opp_count} |"
        )

    lines += ["", "---", ""]

    # Сравнительная матрица
    weight_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}

    # Заголовок таблицы
    opt_headers = " | ".join(f"`{o['option_id']}`" for o in options)
    sep_cols = " | ".join(["---"] * len(options))

    lines += [
        "## Сравнительная матрица",
        "",
        "> ⚠️ **Покрытие req** рассчитано автоматически по данным allocation.",
        "> Остальные критерии — качественная оценка BA. Заполни матрицу по своему проекту.",
        "",
        f"| Критерий | Вес | {opt_headers} |",
        f"|----------|-----|{sep_cols}|",
    ]

    for crit in all_criteria:
        crit_id = crit.get("id", "")
        crit_label = crit.get("label", crit_id)
        weight = crit.get("weight", "medium")
        weight_icon = weight_icons.get(weight, "🟡")

        cells = []
        for opt in options:
            if crit_id == "req_coverage":
                cells.append(_calc_coverage(opt["option_id"]))
            else:
                cells.append("_—_")  # BA заполняет вручную

        cells_str = " | ".join(cells)
        lines.append(f"| {crit_label} | {weight_icon} {weight} | {cells_str} |")

    lines += [
        "",
        "> **Как читать:** 🔴 high — ключевой критерий, 🟡 medium — важный, 🟢 low — желательный.",
        "",
        "---",
        "",
    ]

    # Детали по каждому варианту
    lines += [
        "## Детали вариантов",
        "",
    ]

    for opt in options:
        approach_icons = {"build": "🔨", "buy": "🛒", "hybrid": "🔀"}
        icon = approach_icons.get(opt.get("approach", ""), "📋")
        lines += [
            f"### {icon} {opt['option_id']} — {opt['title']}",
            "",
            f"**Подход:** `{opt.get('approach', '?')}`  ",
            f"**Создан:** {opt.get('created', '—')}",
            "",
        ]

        components = opt.get("components", [])
        if components:
            lines.append("**Компоненты:**")
            for c in components:
                lines.append(f"- {c}")
            lines.append("")

        opportunities = opt.get("improvement_opportunities", [])
        if opportunities:
            lines.append("**Возможности улучшения бизнеса:**")
            type_labels = {
                "efficiency": "⚡ Эффективность",
                "information_access": "📊 Доступ к информации",
                "new_capability": "🚀 Новая возможность",
            }
            for opp in opportunities:
                t = opp.get("type", "")
                label = type_labels.get(t, t)
                lines.append(f"- **{label}:** {opp.get('description', '')}")
            lines.append("")

        measures = opt.get("effectiveness_measures", [])
        if measures:
            lines.append("**Метрики эффективности:**")
            for m in measures:
                lines.append(f"- {m}")
            lines.append("")

        if opt.get("vendor_notes"):
            lines += [f"**Вендор:** {opt['vendor_notes']}", ""]

        if opt.get("notes"):
            lines += [f"**Примечания:** {opt['notes']}", ""]

        # Allocation summary для варианта
        v1_ids = [rid for rid, d in allocation.items() if d.get("option_id") == opt["option_id"] and d.get("version") == "v1"]
        v2_ids = [rid for rid, d in allocation.items() if d.get("option_id") == opt["option_id"] and d.get("version") == "v2"]
        oos_ids = [rid for rid, d in allocation.items() if d.get("option_id") == opt["option_id"] and d.get("version") == "out_of_scope"]
        coverage_str = _calc_coverage(opt["option_id"])

        lines += [
            f"**Allocation:** v1: {len(v1_ids)} req | v2: {len(v2_ids)} req | out_of_scope: {len(oos_ids)} req  ",
            f"**Покрытие Must:** {coverage_str}",
            "",
        ]

    lines += [
        "---",
        "",
        "## Передача артефакта",
        "",
        "| Направление | Назначение |",
        "|-------------|-----------|",
        "| → **4.4** Communicate | Presentation для стейкхолдеров: заполни матрицу оценками |",
        "| → **7.5** `save_design_options_report` | Финальный отчёт с рекомендацией |",
        "",
        "---",
        "",
        "**Следующий шаг:**",
        f"`save_design_options_report(project_id='{project_id}', recommended_option_id='OPT-XXX')` — сохрани финальный Design Options Report.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.5.5 — save_design_options_report
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def save_design_options_report(
    project_id: str,
    recommended_option_id: str = "",
    notes: str = "",
) -> str:
    """
    BABOK 7.5 — Генерирует финальный Design Options Report.
    Сохраняет через save_artifact (префикс 7_5_design_options).
    Передаётся в 7.6 (Analyze Value and Recommend Solution).

    Включает: все варианты дизайна, allocation map, improvement opportunities,
    контекст (change_strategy, business_context, architecture),
    опциональную предварительную рекомендацию BA.

    Args:
        project_id:              Идентификатор проекта.
        recommended_option_id:   Опциональный ID рекомендуемого варианта (например, 'OPT-002').
                                 Это предварительный вывод BA — финальная рекомендация в 7.6.
        notes:                   Дополнительные заметки к отчёту (необязательно).

    Returns:
        Design Options Report в Markdown + подтверждение сохранения через save_artifact.
    """
    logger.info(f"save_design_options_report: project_id='{project_id}'")

    do_data = _load_design_options(project_id)
    options = do_data.get("options", [])

    if not options:
        return (
            f"⚠️ No design options for project `{project_id}`.\n\n"
            f"Create options via `create_design_option` before generating the report."
        )

    # Валидация recommended_option_id
    if recommended_option_id:
        option_ids = [o["option_id"] for o in options]
        if recommended_option_id not in option_ids:
            return (
                f"❌ Option `{recommended_option_id}` not found.\n\n"
                f"Existing options: {', '.join(option_ids)}"
            )

    # Загружаем контекст
    strategy = _load_change_strategy(project_id)
    ctx = _load_context(project_id)
    arch = _load_architecture(project_id)
    repo = _load_repo(project_id)
    allocation = do_data.get("allocation", {})

    all_reqs = [r for r in repo.get("requirements", [])
                if r.get("type", "") not in NON_REQUIREMENT_NODE_TYPES]
    must_reqs = [r for r in all_reqs if r.get("priority") in MUST_PRIORITIES]
    must_ids = {r["id"] for r in must_reqs}

    def _calc_coverage(option_id: str) -> tuple:
        if not must_reqs:
            return (0, 0, "N/A")
        v1_must = sum(
            1 for req_id, data in allocation.items()
            if data.get("option_id") == option_id
            and data.get("version") == "v1"
            and req_id in must_ids
        )
        pct = round(v1_must / len(must_reqs) * 100)
        return (v1_must, len(must_reqs), f"{pct}%")

    # ------------------------------------------------------------------
    # Генерируем Design Options Report
    # ------------------------------------------------------------------

    doc_lines = [
        f"<!-- BABOK 7.5 — Design Options Report | Проект: {project_id} | {date.today()} -->",
        "",
        f"# 🎨 Design Options Report",
        "",
        f"| Поле | Значение |",
        f"|------|----------|",
        f"| Проект | {project_id} |",
        f"| Дата | {date.today()} |",
        f"| Вариантов дизайна | {len(options)} |",
        f"| Распределено req | {len(allocation)} |",
    ]

    if recommended_option_id:
        rec_opt = next((o for o in options if o["option_id"] == recommended_option_id), None)
        rec_title = rec_opt["title"] if rec_opt else recommended_option_id
        doc_lines.append(f"| ⭐ Предварительная рекомендация | `{recommended_option_id}` — {rec_title} |")

    doc_lines += [""]

    if notes:
        doc_lines += [f"**Примечания:** {notes}", ""]

    doc_lines += ["---", ""]

    # Change Strategy
    if strategy:
        # Read either the 6.4 rich contract or the 7.5 flat surrogate (audit finding 7.5-B).
        sf = _extract_strategy_fields(strategy)
        source_note = " _(from 6.4 Change Strategy)_" if _is_rich_strategy(strategy) else ""
        doc_lines += [
            f"## Change strategy{source_note}",
            "",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| Type | `{sf['change_type']}` |",
            f"| Scope | {sf['scope']} |",
            f"| Constraints | {sf['constraints']} |",
            f"| Timeline | {sf['timeline']} |",
            "",
        ]
    else:
        doc_lines += [
            "> ℹ️ **Change Strategy не задана.** Для полноты отчёта рекомендуется вызвать `set_change_strategy`.",
            "",
        ]

    # Business Context
    if ctx:
        goals = ctx.get("business_goals", [])
        future_state = ctx.get("future_state", "")
        doc_lines += [
            "## Бизнес-контекст (7.3)",
            "",
        ]
        if future_state:
            doc_lines += [f"**Future State:** {future_state}", ""]
        if goals:
            doc_lines += [
                "**Бизнес-цели:**",
                "",
                "| ID | Цель |",
                "|----|------|",
            ]
            for g in goals[:10]:
                doc_lines.append(f"| `{g.get('id', '?')}` | {g.get('title', '')[:80]} |")
            doc_lines.append("")

    # Architecture gaps summary
    if arch:
        gaps = arch.get("gaps", {})
        critical_count = len(gaps.get("critical", []))
        warning_count = len(gaps.get("warning", []))
        doc_lines += [
            "## Архитектурный контекст (7.4)",
            "",
            f"| Viewpoints | Critical gaps | Warning gaps |",
            f"|------------|--------------|-------------|",
            f"| {len(arch.get('viewpoints', {}))} | {critical_count} | {warning_count} |",
            "",
        ]
        if critical_count > 0:
            doc_lines += [
                "> ⚠️ **Есть критические архитектурные разрывы.** Рекомендуется устранить перед 7.6.",
                "",
            ]

    # Варианты дизайна
    doc_lines += [
        "---",
        "",
        "## Варианты дизайна",
        "",
    ]

    approach_icons = {"build": "🔨 Build", "buy": "🛒 Buy", "hybrid": "🔀 Hybrid"}

    for opt in options:
        opt_id = opt["option_id"]
        is_recommended = opt_id == recommended_option_id
        rec_marker = " ⭐ **РЕКОМЕНДУЕТСЯ**" if is_recommended else ""
        approach_label = approach_icons.get(opt.get("approach", ""), opt.get("approach", ""))

        v1_count = sum(1 for d in allocation.values() if d.get("option_id") == opt_id and d.get("version") == "v1")
        v2_count = sum(1 for d in allocation.values() if d.get("option_id") == opt_id and d.get("version") == "v2")
        oos_count = sum(1 for d in allocation.values() if d.get("option_id") == opt_id and d.get("version") == "out_of_scope")
        _, _, coverage_pct = _calc_coverage(opt_id)

        doc_lines += [
            f"### {opt_id} — {opt['title']}{rec_marker}",
            "",
            f"| Поле | Значение |",
            f"|------|----------|",
            f"| Подход | {approach_label} |",
            f"| Покрытие Must-req (v1) | {coverage_pct} |",
            f"| Allocation: v1 | {v1_count} req |",
            f"| Allocation: v2 | {v2_count} req |",
            f"| Allocation: out_of_scope | {oos_count} req |",
            "",
        ]

        components = opt.get("components", [])
        if components:
            doc_lines.append("**Компоненты решения:**")
            for c in components:
                doc_lines.append(f"- {c}")
            doc_lines.append("")

        opportunities = opt.get("improvement_opportunities", [])
        if opportunities:
            type_labels = {
                "efficiency": "⚡ Эффективность",
                "information_access": "📊 Доступ к информации",
                "new_capability": "🚀 Новая возможность",
            }
            doc_lines.append("**Возможности улучшения бизнеса:**")
            for opp in opportunities:
                t = opp.get("type", "")
                label = type_labels.get(t, t)
                doc_lines.append(f"- **{label}:** {opp.get('description', '')}")
            doc_lines.append("")

        measures = opt.get("effectiveness_measures", [])
        if measures:
            doc_lines.append("**Метрики эффективности:**")
            for m in measures:
                doc_lines.append(f"- {m}")
            doc_lines.append("")

        if opt.get("vendor_notes"):
            doc_lines += [f"**Вендор:** {opt['vendor_notes']}", ""]

        if opt.get("notes"):
            doc_lines += [f"**Примечания:** {opt['notes']}", ""]

    # Allocation summary
    doc_lines += [
        "---",
        "",
        "## Сводная Allocation Map",
        "",
        "| ID | Тип | Название | Приоритет | Версия | Вариант | Обоснование |",
        "|----|-----|---------|-----------|--------|---------|-------------|",
    ]

    for req_id, alloc_data in allocation.items():
        req = _find_req(repo, req_id)
        if req:
            doc_lines.append(
                f"| `{req_id}` | {req.get('type', '?')} | {req.get('title', '')[:40]} | "
                f"{req.get('priority', '—')} | `{alloc_data.get('version', '?')}` | "
                f"`{alloc_data.get('option_id', '?')}` | {alloc_data.get('rationale', '')[:50]} |"
            )

    doc_lines += [""]

    # Рекомендация
    if recommended_option_id:
        rec_opt = next((o for o in options if o["option_id"] == recommended_option_id), None)
        doc_lines += [
            "---",
            "",
            "## ⭐ Предварительная рекомендация BA",
            "",
            f"**Рекомендуемый вариант:** `{recommended_option_id}` — {rec_opt['title'] if rec_opt else ''}",
            "",
        ]
        if notes:
            doc_lines += [f"**Обоснование:** {notes}", ""]

        doc_lines += [
            "> ⚠️ **Это предварительный вывод BA.** Финальная рекомендация и оценка ценности —",
            "> в задаче 7.6 (Analyze Value and Recommend Solution).",
            "",
        ]

    doc_lines += [
        "---",
        "",
        "## Передача артефакта",
        "",
        "| Направление | Назначение |",
        "|-------------|-----------|",
        "| → **7.6** Analyze Value | Оценить ценность каждого варианта и дать финальную рекомендацию |",
        "| → **4.4** Communicate | Коммуникация вариантов со стейкхолдерами |",
    ]

    content = "\n".join(doc_lines)

    # Сохраняем через save_artifact
    save_artifact(content, prefix="7_5_design_options", project_id=project_id)

    # Ответ пользователю
    result_lines = [
        f"✅ Design Options Report сохранён — **{project_id}**",
        "",
        f"| Поле | Значение |",
        f"|------|----------|",
        f"| Вариантов дизайна | {len(options)} |",
        f"| Распределено req | {len(allocation)} |",
        f"| Дата | {date.today()} |",
    ]

    if recommended_option_id:
        rec_opt = next((o for o in options if o["option_id"] == recommended_option_id), None)
        result_lines.append(
            f"| ⭐ Рекомендация | `{recommended_option_id}` — {rec_opt['title'] if rec_opt else ''} |"
        )

    result_lines += [
        "",
        "Design Options Report сохранён через `save_artifact` (префикс: `7_5_design_options`).",
        "",
    ]

    # Предупреждения
    if not strategy:
        result_lines += [
            "> ⚠️ **Change Strategy не задана.** Для полноты рекомендуется `set_change_strategy`.",
            "",
        ]

    unallocated = [r["id"] for r in all_reqs if r["id"] not in allocation]
    if unallocated:
        result_lines += [
            f"> ⚠️ **{len(unallocated)} req не распределены по версиям.** "
            f"Запусти `allocate_requirements` для полноты allocation.",
            "",
        ]

    result_lines += [
        "---",
        "",
        "**Следующие шаги:**",
        "- → **7.6** `analyze_value_and_recommend` — оценить ценность вариантов и дать финальную рекомендацию",
        "- → **4.4** `prepare_communication_package` — подготовить коммуникационный пакет для стейкхолдеров",
    ]

    return "\n".join(result_lines)


if __name__ == "__main__":
    mcp.run()
