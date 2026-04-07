"""
BABOK 6.4 — Define Change Strategy
MCP-инструменты для определения стратегии изменения.

Инструменты:
  - scope_change_strategy       — инициализация + автоимпорт из 6.1, 6.2, 6.3
  - define_solution_scope       — capabilities по категориям + explicitly_excluded
  - assess_enterprise_readiness — 6 измерений готовности × скор 1–5 → readiness_score
  - add_strategy_option         — карточка варианта стратегии
  - compare_strategy_options    — взвешенная матрица → winner + opportunity cost
  - define_transition_states    — фазы перехода с capabilities, gaps, рисками, ценностью
  - save_change_strategy        — финализация: JSON + Markdown + опц. push в 5.1

Хранение:
  - {project}_change_strategy_scope.json  — скоуп и контекст
  - {project}_change_strategy.json        — финальный артефакт (контракт для 7.x, 8.x)

Интеграция:
  Вход: 6.1 (business_needs), 6.2 (future_state, gap_analysis), 6.3 (risk_assessment)
  Выход: change_strategy.json → 7.1, 7.4, 7.5, 7.6, 8.x;
         узел solution + satisfies → 5.1 (опционально)

ADR-077: scope_change_strategy — автоимпорт из 6.1+6.2+6.3, graceful degradation
ADR-078: GAP встроен в define_solution_scope (gap_severity + gap_source)
ADR-079: 6 измерений готовности (change_history добавлен к базовым 5)
ADR-080: do_nothing добавляется автоматически как OPT-000
ADR-081: дефолтные 6 критериев + опциональные кастомные
ADR-082: новый тип узла `solution` в репозитории 5.1
ADR-083: JSON-контракт — один файл с секциями solution_scope + change_strategy

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import save_artifact, logger, DATA_DIR

mcp = FastMCP("BABOK_ChangeStrategy")

SCOPE_FILENAME = "change_strategy_scope.json"
STRATEGY_FILENAME = "change_strategy.json"
REPO_FILENAME = "traceability_repo.json"

# Файлы из предыдущих задач (опциональные источники)
BUSINESS_NEEDS_FILENAME = "business_needs.json"
FUTURE_STATE_FILENAME = "future_state.json"
GAP_FILENAME = "gap_analysis.json"
RISK_ASSESSMENT_FILENAME = "risk_assessment.json"

VALID_CHANGE_TYPES = ["transformation", "process_improvement", "technology_implementation", "regulatory_compliance", "other"]
VALID_METHODOLOGIES = ["agile", "waterfall", "hybrid"]
VALID_STRATEGY_TYPES = ["big_bang", "phased", "pilot_first", "do_nothing"]
VALID_INVESTMENT_LEVELS = ["high", "medium", "low"]
VALID_RISK_IMPACTS = ["mitigates", "exacerbates", "neutral"]
VALID_CAP_CATEGORIES = ["process", "technology", "data", "people", "org_structure", "knowledge", "location"]
VALID_GAP_SEVERITIES = ["none", "low", "medium", "high"]
VALID_VERDICTS = ["ready", "proceed_with_caution", "not_ready"]

DEFAULT_CRITERIA_WEIGHTS = {
    "alignment_to_goals": 25,
    "risk_mitigation": 20,
    "cost": 20,
    "time_to_value": 15,
    "org_readiness_fit": 10,
    "feasibility": 10,
}

DO_NOTHING_OPTION_ID = "OPT-000"


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def _safe(project_id: str) -> str:
    return project_id.lower().replace(" ", "_")


def _scope_path(project_id: str) -> str:
    return os.path.join(DATA_DIR, f"{_safe(project_id)}_{SCOPE_FILENAME}")


def _strategy_path(project_id: str) -> str:
    return os.path.join(DATA_DIR, f"{_safe(project_id)}_{STRATEGY_FILENAME}")


def _repo_path(project_id: str, repo_project_id: Optional[str] = None) -> str:
    pid = repo_project_id or project_id
    return os.path.join(DATA_DIR, f"{_safe(pid)}_{REPO_FILENAME}")


def _safe_load_json(path: str) -> Optional[dict]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _load_strategy(project_id: str) -> dict:
    path = _strategy_path(project_id)
    if not os.path.exists(path):
        return _empty_strategy(project_id)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_strategy(data: dict, project_id: str):
    os.makedirs(DATA_DIR, exist_ok=True)
    data["updated"] = str(date.today())
    with open(_strategy_path(project_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _empty_strategy(project_id: str) -> dict:
    return {
        "project_id": project_id,
        "created": str(date.today()),
        "updated": str(date.today()),
        "scope": {},
        "imported_context": {
            "business_needs": [],
            "business_goals": [],
            "risks": [],
        },
        "solution_scope": {
            "capabilities": [],
            "explicitly_excluded": [],
            "scope_summary": "",
        },
        "enterprise_readiness": {},
        "change_strategy": {
            "options": [],
            "selected_option_id": None,
            "rejected_alternatives": [],
            "opportunity_cost": "",
        },
        "transition_states": [],
    }


def _next_option_id(options: list) -> str:
    """Генерирует следующий OPT-xxx ID (пропускает OPT-000)."""
    existing_nums = []
    for o in options:
        oid = o.get("option_id", "")
        if oid.startswith("OPT-") and oid[4:].isdigit():
            n = int(oid[4:])
            if n > 0:
                existing_nums.append(n)
    if not existing_nums:
        return "OPT-001"
    return f"OPT-{max(existing_nums) + 1:03d}"


def _readiness_verdict(score: float) -> str:
    if score >= 4.0:
        return "ready"
    elif score >= 2.5:
        return "proceed_with_caution"
    else:
        return "not_ready"


# ---------------------------------------------------------------------------
# Инструменты
# ---------------------------------------------------------------------------

@mcp.tool()
def scope_change_strategy(
    project_id: str,
    change_type: Literal["transformation", "process_improvement", "technology_implementation", "regulatory_compliance", "other"],
    time_horizon_months: int,
    methodology: Literal["agile", "waterfall", "hybrid"],
    source_project_ids: str = "[]",
    ba_notes: str = "",
) -> str:
    """
    Шаг 1 пайплайна 6.4: инициализировать стратегию изменения.

    Фиксирует тип изменения, горизонт, методологию.
    Автоматически импортирует контекст из 6.1 (business_needs), 6.2 (future_state, gap_analysis),
    6.3 (risk_assessment). Добавляет do_nothing как OPT-000.
    Graceful degradation: отсутствующие артефакты пропускаются с предупреждением.

    Args:
        project_id: Идентификатор проекта
        change_type: Тип изменения (transformation/process_improvement/technology_implementation/regulatory_compliance/other)
        time_horizon_months: Целевой горизонт в месяцах
        methodology: Методология (agile/waterfall/hybrid)
        source_project_ids: JSON-список project_id из 6.1/6.2/6.3 для автоимпорта, напр. '["crm_upgrade"]'
        ba_notes: Дополнительный контекст
    """
    try:
        source_ids = json.loads(source_project_ids) if source_project_ids.strip() else []
    except json.JSONDecodeError:
        return "❌ Ошибка: source_project_ids должен быть JSON-массивом, напр. '[\"crm\"]'"

    if time_horizon_months <= 0:
        return "❌ time_horizon_months должен быть > 0"

    scope = {
        "project_id": project_id,
        "change_type": change_type,
        "time_horizon_months": time_horizon_months,
        "methodology": methodology,
        "source_project_ids": source_ids,
        "ba_notes": ba_notes,
        "created": str(date.today()),
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_scope_path(project_id), "w", encoding="utf-8") as f:
        json.dump(scope, f, ensure_ascii=False, indent=2)

    strategy = _load_strategy(project_id)
    strategy["scope"] = scope

    # --- Автоимпорт контекста ---
    warnings = []
    imported_bn = []
    imported_bg = []
    imported_risks = []

    if not source_ids:
        source_ids = [project_id]

    for src_id in source_ids:
        # 6.1: business_needs
        needs_path = os.path.join(DATA_DIR, f"{_safe(src_id)}_{BUSINESS_NEEDS_FILENAME}")
        needs_data = _safe_load_json(needs_path)
        if needs_data:
            for bn in needs_data.get("business_needs", []):
                imported_bn.append({
                    "id": bn.get("id", ""),
                    "title": bn.get("title", bn.get("description", ""))[:80],
                    "priority": bn.get("priority", ""),
                    "source_project": src_id,
                })
        else:
            warnings.append(f"⚠️ 6.1 business_needs не найден для '{src_id}'")

        # 6.2: future_state (goals)
        fs_path = os.path.join(DATA_DIR, f"{_safe(src_id)}_{FUTURE_STATE_FILENAME}")
        fs_data = _safe_load_json(fs_path)
        if fs_data:
            for bg in fs_data.get("goals", []):
                imported_bg.append({
                    "id": bg.get("id", ""),
                    "title": bg.get("title", bg.get("description", ""))[:80],
                    "source_project": src_id,
                })
        else:
            warnings.append(f"⚠️ 6.2 future_state не найден для '{src_id}'")

        # 6.3: risk_assessment
        risk_path = os.path.join(DATA_DIR, f"{_safe(src_id)}_{RISK_ASSESSMENT_FILENAME}")
        risk_data = _safe_load_json(risk_path)
        if risk_data:
            for rk in risk_data.get("risks", []):
                if rk.get("status") == "identified":
                    imported_risks.append({
                        "id": rk.get("risk_id", ""),
                        "description": rk.get("description", "")[:80],
                        "zone": rk.get("zone", "medium"),
                        "risk_score": rk.get("risk_score", 0),
                        "response_strategy": rk.get("response_strategy", ""),
                        "source_project": src_id,
                    })
        else:
            warnings.append(f"⚠️ 6.3 risk_assessment не найден для '{src_id}'")

    strategy["imported_context"] = {
        "business_needs": imported_bn,
        "business_goals": imported_bg,
        "risks": imported_risks,
    }

    # do_nothing добавляется автоматически (ADR-080)
    existing_options = strategy["change_strategy"].get("options", [])
    if not any(o.get("option_id") == DO_NOTHING_OPTION_ID for o in existing_options):
        existing_options.insert(0, {
            "option_id": DO_NOTHING_OPTION_ID,
            "name": "Do Nothing (статус-кво)",
            "strategy_type": "do_nothing",
            "investment_level": "low",
            "timeline_months": 0,
            "linked_risks": [],
            "risk_impact": "exacerbates",
            "pros": ["Нет затрат на изменение", "Нет операционного риска внедрения"],
            "cons": [
                "Бизнес-потребности остаются нереализованными",
                "Конкурентное отставание продолжается",
                "Текущие проблемы усугубляются со временем",
            ],
            "weighted_score": None,
            "selected": False,
            "auto_added": True,
        })
    strategy["change_strategy"]["options"] = existing_options

    _save_strategy(strategy, project_id)

    # --- Форматирование вывода ---
    lines = [
        f"✅ Стратегия изменения инициализирована\n\n",
        f"  Проект:     {project_id}\n",
        f"  Тип:        {change_type}\n",
        f"  Горизонт:   {time_horizon_months} месяцев\n",
        f"  Методология: {methodology}\n\n",
    ]

    if imported_bn or imported_bg or imported_risks:
        lines.append("**Импортированный контекст:**\n")
        if imported_bn:
            lines.append(f"  📋 Бизнес-потребности (6.1): {len(imported_bn)} шт. — "
                         + ", ".join(bn["id"] for bn in imported_bn if bn["id"]) + "\n")
        if imported_bg:
            lines.append(f"  🎯 Бизнес-цели (6.2):        {len(imported_bg)} шт. — "
                         + ", ".join(bg["id"] for bg in imported_bg if bg["id"]) + "\n")
        if imported_risks:
            high_risks = [r for r in imported_risks if r.get("zone") == "high"]
            lines.append(f"  ⚠️  Риски (6.3):              {len(imported_risks)} шт."
                         + (f" ({len(high_risks)} High)" if high_risks else "") + "\n")

    if warnings:
        lines.append("\n**Предупреждения (graceful degradation):**\n")
        for w in warnings:
            lines.append(f"  {w}\n")

    lines.append(
        f"\n  ℹ️ OPT-000 (do_nothing) добавлен автоматически как baseline.\n\n"
        f"**Следующий шаг:** `define_solution_scope` — определи capabilities решения."
    )

    return "".join(lines)


@mcp.tool()
def define_solution_scope(
    project_id: str,
    capabilities_json: str,
    explicitly_excluded: str = "[]",
    scope_summary: str = "",
) -> str:
    """
    Шаг 2 пайплайна 6.4: определить скоуп решения через capabilities.

    Каждый capability имеет категорию (process/technology/data/people/org_structure/knowledge/location),
    gap_severity (none/low/medium/high) и признак in_scope.
    explicitly_excluded фиксирует что осознанно вне скоупа — предотвращает scope creep.

    Args:
        project_id: Идентификатор проекта
        capabilities_json: JSON-массив capabilities. Формат объекта:
            {"name": "...", "category": "technology", "description": "...",
             "gap_severity": "high", "gap_source": "6.2:gap_analysis", "in_scope": true}
        explicitly_excluded: JSON-список строк — что явно НЕ входит в скоуп
        scope_summary: 2–3 предложения: что делаем и чего не делаем
    """
    try:
        capabilities = json.loads(capabilities_json)
    except json.JSONDecodeError:
        return "❌ Ошибка парсинга capabilities_json. Проверь синтаксис JSON."

    if not isinstance(capabilities, list):
        return "❌ capabilities_json должен быть JSON-массивом."

    try:
        excluded = json.loads(explicitly_excluded) if explicitly_excluded.strip() else []
    except json.JSONDecodeError:
        excluded = []

    # Валидация capabilities
    valid_caps = []
    errors = []
    for i, cap in enumerate(capabilities):
        name = cap.get("name", "")
        category = cap.get("category", "")
        gap_severity = cap.get("gap_severity", "medium")
        if not name:
            errors.append(f"Capability #{i+1}: отсутствует поле 'name'")
            continue
        if category not in VALID_CAP_CATEGORIES:
            errors.append(f"Capability '{name}': неверная category '{category}'. Допустимые: {', '.join(VALID_CAP_CATEGORIES)}")
            continue
        if gap_severity not in VALID_GAP_SEVERITIES:
            errors.append(f"Capability '{name}': неверная gap_severity '{gap_severity}'")
            continue
        valid_caps.append({
            "name": name,
            "category": category,
            "description": cap.get("description", ""),
            "gap_severity": gap_severity,
            "gap_source": cap.get("gap_source", "manual"),
            "in_scope": cap.get("in_scope", True),
        })

    if errors:
        return "❌ Ошибки в capabilities_json:\n" + "\n".join(f"  • {e}" for e in errors)

    strategy = _load_strategy(project_id)
    strategy["solution_scope"] = {
        "capabilities": valid_caps,
        "explicitly_excluded": excluded,
        "scope_summary": scope_summary,
    }
    _save_strategy(strategy, project_id)

    in_scope = [c for c in valid_caps if c.get("in_scope", True)]
    out_of_scope = [c for c in valid_caps if not c.get("in_scope", True)]

    # Статистика по категориям
    cats = {}
    for c in in_scope:
        cats[c["category"]] = cats.get(c["category"], 0) + 1

    # Статистика по gap_severity
    gaps = {"high": 0, "medium": 0, "low": 0, "none": 0}
    for c in in_scope:
        gaps[c["gap_severity"]] = gaps.get(c["gap_severity"], 0) + 1

    lines = [
        f"✅ Скоуп решения определён\n\n",
        f"  В скоупе capabilities: {len(in_scope)}\n",
        f"  Явные исключения:      {len(excluded)}\n\n",
    ]

    if cats:
        lines.append("**Capabilities по категориям:**\n")
        for cat, cnt in sorted(cats.items()):
            lines.append(f"  {cat}: {cnt}\n")

    lines.append("\n**Распределение по gap_severity:**\n")
    if gaps["high"] > 0:
        lines.append(f"  🔴 high:   {gaps['high']} (критичные gaps — определят структуру фаз)\n")
    if gaps["medium"] > 0:
        lines.append(f"  🟡 medium: {gaps['medium']}\n")
    if gaps["low"] > 0:
        lines.append(f"  🟢 low:    {gaps['low']}\n")
    if gaps["none"] > 0:
        lines.append(f"  ⚪ none:   {gaps['none']} (capabilities уже есть)\n")

    if excluded:
        lines.append("\n**Явные исключения из скоупа:**\n")
        for ex in excluded:
            lines.append(f"  • {ex}\n")

    if scope_summary:
        lines.append(f"\n**Резюме скоупа:** {scope_summary}\n")

    lines.append(
        f"\n→ Следующий шаг: `assess_enterprise_readiness` — оцени готовность организации."
    )

    return "".join(lines)


@mcp.tool()
def assess_enterprise_readiness(
    project_id: str,
    leadership_commitment: int,
    cultural_readiness: int,
    resource_availability: int,
    operational_readiness: int,
    technical_readiness: int,
    change_history: int,
    leadership_rationale: str = "",
    cultural_rationale: str = "",
    resource_rationale: str = "",
    operational_rationale: str = "",
    technical_rationale: str = "",
    change_history_rationale: str = "",
) -> str:
    """
    Шаг 3 пайплайна 6.4: оценить готовность организации к изменению.

    Оценивает 6 измерений по шкале 1–5. Вычисляет readiness_score (среднее) и вердикт:
    ready (≥4.0) / proceed_with_caution (2.5–3.9) / not_ready (<2.5).
    ADR-079: change_history добавлен к базовым 5 измерениям.

    Args:
        project_id: Идентификатор проекта
        leadership_commitment: Готовность руководства 1–5
        cultural_readiness: Культурная готовность 1–5
        resource_availability: Доступность ресурсов 1–5
        operational_readiness: Операционная готовность 1–5
        technical_readiness: Техническая готовность 1–5
        change_history: История изменений в организации 1–5
        leadership_rationale: Обоснование оценки leadership
        cultural_rationale: Обоснование оценки culture
        resource_rationale: Обоснование оценки resource
        operational_rationale: Обоснование оценки operational
        technical_rationale: Обоснование оценки technical
        change_history_rationale: Обоснование оценки change_history
    """
    dimensions = {
        "leadership_commitment": leadership_commitment,
        "cultural_readiness": cultural_readiness,
        "resource_availability": resource_availability,
        "operational_readiness": operational_readiness,
        "technical_readiness": technical_readiness,
        "change_history": change_history,
    }
    rationales = {
        "leadership_commitment": leadership_rationale,
        "cultural_readiness": cultural_rationale,
        "resource_availability": resource_rationale,
        "operational_readiness": operational_rationale,
        "technical_readiness": technical_rationale,
        "change_history": change_history_rationale,
    }

    errors = []
    for dim, val in dimensions.items():
        if not 1 <= val <= 5:
            errors.append(f"{dim} должен быть от 1 до 5, получено: {val}")
    if errors:
        return "❌ Ошибки валидации:\n" + "\n".join(f"  • {e}" for e in errors)

    score = sum(dimensions.values()) / len(dimensions)
    score = round(score, 2)
    verdict = _readiness_verdict(score)

    readiness_data = {
        "dimensions": {
            dim: {"score": val, "rationale": rationales.get(dim, "")}
            for dim, val in dimensions.items()
        },
        "readiness_score": score,
        "verdict": verdict,
        "assessed_on": str(date.today()),
    }

    strategy = _load_strategy(project_id)
    strategy["enterprise_readiness"] = readiness_data
    _save_strategy(strategy, project_id)

    verdict_emoji = {"ready": "🟢", "proceed_with_caution": "🟡", "not_ready": "🔴"}
    verdict_text = {
        "ready": "Организация готова к изменению",
        "proceed_with_caution": "Есть пробелы — нужны подготовительные меры",
        "not_ready": "Требуется отдельная программа подготовки организации",
    }

    weak_dims = [(dim, val) for dim, val in dimensions.items() if val <= 2]
    medium_dims = [(dim, val) for dim, val in dimensions.items() if val == 3]

    lines = [
        f"✅ Оценка готовности завершена\n\n",
        f"  Readiness Score: {score:.1f} / 5.0\n",
        f"  Вердикт: {verdict_emoji[verdict]} {verdict} — {verdict_text[verdict]}\n\n",
        f"**Профиль по измерениям:**\n",
    ]

    dim_labels = {
        "leadership_commitment": "Готовность руководства",
        "cultural_readiness": "Культурная готовность",
        "resource_availability": "Доступность ресурсов",
        "operational_readiness": "Операционная готовность",
        "technical_readiness": "Техническая готовность",
        "change_history": "История изменений",
    }
    score_bar = {1: "▪▫▫▫▫", 2: "▪▪▫▫▫", 3: "▪▪▪▫▫", 4: "▪▪▪▪▫", 5: "▪▪▪▪▪"}

    for dim, val in dimensions.items():
        bar = score_bar.get(val, "?????")
        label = dim_labels.get(dim, dim)
        lines.append(f"  {bar} {val}/5  {label}\n")

    if weak_dims:
        lines.append("\n**⚠️ Критические пробелы (оценка ≤ 2):**\n")
        for dim, val in weak_dims:
            rat = rationales.get(dim, "")
            lines.append(f"  • {dim_labels.get(dim, dim)}: {val}/5"
                         + (f" — {rat}" if rat else "") + "\n")
        if verdict != "not_ready":
            lines.append(
                "  → Рекомендуется рассмотреть pilot_first или phased стратегию\n"
                "     и добавить подготовительную Фазу 0 в transition states\n"
            )

    if verdict == "proceed_with_caution" and medium_dims:
        lines.append("\n**🟡 Измерения требующие внимания (оценка = 3):**\n")
        for dim, val in medium_dims:
            lines.append(f"  • {dim_labels.get(dim, dim)}: {val}/5\n")

    lines.append(
        f"\n→ Следующий шаг: `add_strategy_option` — добавь варианты стратегии (min 1 реальный).\n"
        f"  OPT-000 (do_nothing) уже добавлен автоматически."
    )

    return "".join(lines)


@mcp.tool()
def add_strategy_option(
    project_id: str,
    name: str,
    strategy_type: Literal["big_bang", "phased", "pilot_first"],
    investment_level: Literal["high", "medium", "low"],
    timeline_months: int,
    pros: str,
    cons: str,
    linked_risks: str = "[]",
    risk_impact: Literal["mitigates", "exacerbates", "neutral"] = "neutral",
) -> str:
    """
    Шаг 4 пайплайна 6.4: добавить вариант стратегии.

    do_nothing (OPT-000) добавлен автоматически — не нужно добавлять снова.
    Минимум 1 реальный вариант. Оптимально 2–3 реальных варианта + do_nothing.

    Args:
        project_id: Идентификатор проекта
        name: Название варианта (например "Поэтапная замена CRM")
        strategy_type: Тип стратегии (big_bang/phased/pilot_first)
        investment_level: Уровень инвестиций (high/medium/low)
        timeline_months: Срок реализации в месяцах
        pros: JSON-список преимуществ, напр. '["Быстрый time-to-value", "Низкий риск"]'
        cons: JSON-список недостатков, напр. '["Высокая стоимость", "Длительный срок"]'
        linked_risks: JSON-список RK-xxx рисков, напр. '["RK-001", "RK-003"]'
        risk_impact: Как вариант влияет на linked_risks (mitigates/exacerbates/neutral)
    """
    try:
        pros_list = json.loads(pros) if pros.strip() else []
    except json.JSONDecodeError:
        return "❌ Ошибка парсинга pros. Должен быть JSON-массив строк."

    try:
        cons_list = json.loads(cons) if cons.strip() else []
    except json.JSONDecodeError:
        return "❌ Ошибка парсинга cons. Должен быть JSON-массив строк."

    try:
        risks_list = json.loads(linked_risks) if linked_risks.strip() else []
    except json.JSONDecodeError:
        risks_list = []

    if timeline_months <= 0:
        return "❌ timeline_months должен быть > 0"
    if not name.strip():
        return "❌ name не может быть пустым"

    strategy = _load_strategy(project_id)
    options = strategy["change_strategy"].get("options", [])

    option_id = _next_option_id(options)

    option = {
        "option_id": option_id,
        "name": name,
        "strategy_type": strategy_type,
        "investment_level": investment_level,
        "timeline_months": timeline_months,
        "linked_risks": risks_list,
        "risk_impact": risk_impact,
        "pros": pros_list,
        "cons": cons_list,
        "weighted_score": None,
        "selected": False,
    }

    options.append(option)
    strategy["change_strategy"]["options"] = options
    _save_strategy(strategy, project_id)

    total_real = len([o for o in options if o.get("strategy_type") != "do_nothing"])
    risks_hint = f"\n  Связанные риски: {', '.join(risks_list)} ({risk_impact})" if risks_list else ""

    return (
        f"✅ Вариант стратегии добавлен: {option_id}\n\n"
        f"  Название:    {name}\n"
        f"  Тип:         {strategy_type}\n"
        f"  Инвестиции:  {investment_level}\n"
        f"  Срок:        {timeline_months} мес.\n"
        f"  Плюсов:      {len(pros_list)}\n"
        f"  Минусов:     {len(cons_list)}\n"
        f"{risks_hint}\n\n"
        f"  Реальных вариантов в реестре: {total_real}\n\n"
        f"→ Добавь ещё вариант (`add_strategy_option`) или переходи к `compare_strategy_options`."
    )


@mcp.tool()
def compare_strategy_options(
    project_id: str,
    scores_json: str,
    opportunity_cost: str,
    weights_json: str = "{}",
    custom_criteria_json: str = "{}",
) -> str:
    """
    Шаг 5 пайплайна 6.4: сравнить варианты через взвешенную матрицу.

    Вычисляет weighted_score для каждого варианта, определяет winner,
    фиксирует opportunity cost отвергнутых вариантов.

    Args:
        project_id: Идентификатор проекта
        scores_json: JSON-матрица оценок 1–5 по каждому критерию.
            Формат: {"OPT-001": {"alignment_to_goals": 4, "risk_mitigation": 3, "cost": 3,
                                 "time_to_value": 4, "org_readiness_fit": 3, "feasibility": 4}}
            OPT-000 (do_nothing) должен быть включён для корректного сравнения.
        opportunity_cost: Что теряем, выбрав winner вместо остальных (обязательный текст)
        weights_json: Опционально — переопределить веса дефолтных критериев.
            Сумма всех весов (включая кастомные) должна быть 100.
            Формат: {"alignment_to_goals": 30, "risk_mitigation": 25, ...}
        custom_criteria_json: Опционально — добавить кастомные критерии с весами.
            Формат: {"regulatory_compliance": {"weight": 15, "description": "..."}}
    """
    if not opportunity_cost.strip():
        return "❌ opportunity_cost обязателен. Опишите что теряем, выбрав лучший вариант вместо остальных."

    try:
        scores = json.loads(scores_json)
    except json.JSONDecodeError:
        return "❌ Ошибка парсинга scores_json. Проверь синтаксис JSON."

    try:
        weights_override = json.loads(weights_json) if weights_json.strip() else {}
    except json.JSONDecodeError:
        weights_override = {}

    try:
        custom_criteria = json.loads(custom_criteria_json) if custom_criteria_json.strip() else {}
    except json.JSONDecodeError:
        custom_criteria = {}

    # Итоговые веса
    final_weights = dict(DEFAULT_CRITERIA_WEIGHTS)
    if weights_override:
        final_weights.update(weights_override)

    # Добавляем кастомные критерии
    for crit_name, crit_data in custom_criteria.items():
        if isinstance(crit_data, dict):
            final_weights[crit_name] = crit_data.get("weight", 0)
        else:
            final_weights[crit_name] = int(crit_data)

    total_weight = sum(final_weights.values())
    if abs(total_weight - 100) > 1:
        return f"❌ Сумма весов должна быть 100, получено: {total_weight}. Скорректируй weights_json."

    strategy = _load_strategy(project_id)
    options = strategy["change_strategy"].get("options", [])

    if not options:
        return "⚠️ Нет вариантов стратегии. Добавь через `add_strategy_option`."

    # Вычисляем weighted_score
    scored_options = []
    for opt in options:
        oid = opt["option_id"]
        opt_scores = scores.get(oid, {})
        if not opt_scores and oid != DO_NOTHING_OPTION_ID:
            continue

        if oid == DO_NOTHING_OPTION_ID and oid not in scores:
            # do_nothing без явных оценок — формируем минимальные
            opt_scores = {crit: 1 for crit in final_weights}

        weighted = 0.0
        for crit, weight in final_weights.items():
            crit_score = opt_scores.get(crit, 0)
            weighted += crit_score * (weight / 100)

        opt["weighted_score"] = round(weighted, 2)
        opt["scores_detail"] = opt_scores
        scored_options.append(opt)

    if not scored_options:
        return "⚠️ Нет оценённых вариантов. Проверь что option_id в scores_json совпадают с добавленными вариантами."

    # Определяем winner (максимальный score среди не-do_nothing)
    real_options = [o for o in scored_options if o.get("strategy_type") != "do_nothing"]
    if not real_options:
        return "⚠️ Нет реальных вариантов (не do_nothing). Добавь через `add_strategy_option`."

    winner = max(real_options, key=lambda o: o.get("weighted_score", 0))
    winner_id = winner["option_id"]

    # Обновляем selected
    for opt in options:
        opt["selected"] = (opt["option_id"] == winner_id)

    # Формируем rejected_alternatives
    rejected = []
    for opt in scored_options:
        if opt["option_id"] != winner_id:
            rejected.append({
                "option_id": opt["option_id"],
                "name": opt.get("name", ""),
                "weighted_score": opt.get("weighted_score"),
                "rationale": f"Уступил {winner_id} по взвешенной оценке: "
                             f"{opt.get('weighted_score', 0):.2f} vs {winner.get('weighted_score', 0):.2f}",
            })

    strategy["change_strategy"]["options"] = options
    strategy["change_strategy"]["selected_option_id"] = winner_id
    strategy["change_strategy"]["rejected_alternatives"] = rejected
    strategy["change_strategy"]["opportunity_cost"] = opportunity_cost
    strategy["change_strategy"]["criteria_weights_used"] = final_weights
    strategy["change_strategy"]["compared_on"] = str(date.today())

    _save_strategy(strategy, project_id)

    # --- Форматирование вывода ---
    lines = [
        f"✅ Сравнение вариантов завершено\n\n",
        f"  **Победитель: {winner_id} — {winner.get('name', '')}**\n",
        f"  Weighted Score: {winner.get('weighted_score', 0):.2f} / 5.00\n",
        f"  Тип стратегии: {winner.get('strategy_type', '')}\n",
        f"  Срок: {winner.get('timeline_months', 0)} мес. | Инвестиции: {winner.get('investment_level', '')}\n\n",
        f"**Матрица сравнения:**\n",
    ]

    # Таблица
    header_opts = [o["option_id"] for o in scored_options]
    lines.append(f"  {'Критерий':<25} | " + " | ".join(f"{oid:>8}" for oid in header_opts) + " | Вес\n")
    lines.append(f"  {'-'*25}-+-" + "-+-".join(["-"*8]*len(header_opts)) + "-+-----\n")
    for crit, weight in final_weights.items():
        row = f"  {crit:<25} | "
        for opt in scored_options:
            val = opt.get("scores_detail", {}).get(crit, "-")
            row += f"{val:>8} | "
        row += f"{weight}%\n"
        lines.append(row)
    lines.append(f"  {'ИТОГО (weighted)':<25} | ")
    for opt in scored_options:
        lines[-1] += f"{opt.get('weighted_score', 0):>8.2f} | "
    lines[-1] += "\n"

    lines.append(f"\n**Opportunity Cost:**\n  {opportunity_cost}\n")

    lines.append(
        f"\n→ Следующий шаг: `define_transition_states` — опиши фазы перехода."
    )

    return "".join(lines)


@mcp.tool()
def define_transition_states(
    project_id: str,
    phase_number: int,
    phase_name: str,
    duration_months: int,
    capabilities_delivered: str,
    gaps_closed: str,
    risks_remaining: str,
    value_realizable: str,
) -> str:
    """
    Шаг 6 пайплайна 6.4: описать фазу перехода (transition state).

    Вызывай для каждой фазы. Для big_bang — одна фаза.
    Для phased — 2–5 фаз. Каждая фаза должна давать standalone value.

    Args:
        project_id: Идентификатор проекта
        phase_number: Номер фазы (1, 2, 3...)
        phase_name: Название фазы (например "Пилот: базовый CRM")
        duration_months: Длительность фазы в месяцах
        capabilities_delivered: JSON-список названий capabilities реализуемых в этой фазе
        gaps_closed: JSON-список названий gaps закрытых к концу фазы
        risks_remaining: JSON-список RK-xxx рисков которые остаются активными после фазы
        value_realizable: Ценность реализуемая к концу фазы (для спонсора)
    """
    try:
        caps = json.loads(capabilities_delivered) if capabilities_delivered.strip() else []
    except json.JSONDecodeError:
        return "❌ Ошибка парсинга capabilities_delivered. Должен быть JSON-массив строк."

    try:
        gaps = json.loads(gaps_closed) if gaps_closed.strip() else []
    except json.JSONDecodeError:
        gaps = []

    try:
        risks = json.loads(risks_remaining) if risks_remaining.strip() else []
    except json.JSONDecodeError:
        risks = []

    if phase_number <= 0:
        return "❌ phase_number должен быть > 0"
    if duration_months <= 0:
        return "❌ duration_months должен быть > 0"
    if not phase_name.strip():
        return "❌ phase_name не может быть пустым"
    if not value_realizable.strip():
        return "⚠️ value_realizable не заполнен — каждая фаза должна давать конкретную ценность."

    transition_state = {
        "phase": phase_number,
        "name": phase_name,
        "duration_months": duration_months,
        "capabilities_delivered": caps,
        "gaps_closed": gaps,
        "risks_remaining": risks,
        "value_realizable": value_realizable,
    }

    strategy = _load_strategy(project_id)
    states = strategy.get("transition_states", [])

    # Заменяем если фаза уже была определена
    states = [s for s in states if s.get("phase") != phase_number]
    states.append(transition_state)
    states.sort(key=lambda s: s.get("phase", 0))
    strategy["transition_states"] = states

    _save_strategy(strategy, project_id)

    total_caps = sum(len(s.get("capabilities_delivered", [])) for s in states)
    total_months = sum(s.get("duration_months", 0) for s in states)

    risks_note = ""
    if risks:
        risks_note = f"\n  Остающиеся риски: {', '.join(risks)}"

    return (
        f"✅ Фаза {phase_number} зафиксирована\n\n"
        f"  Название:      {phase_name}\n"
        f"  Длительность:  {duration_months} мес.\n"
        f"  Capabilities:  {len(caps)}\n"
        f"  Gaps закрыто:  {len(gaps)}\n"
        f"{risks_note}\n"
        f"  Ценность:      {value_realizable[:80]}{'...' if len(value_realizable) > 80 else ''}\n\n"
        f"  Итого фаз определено: {len(states)} | "
        f"Суммарно: {total_caps} capabilities, {total_months} мес.\n\n"
        f"→ Добавь следующую фазу или вызови `save_change_strategy` для финализации."
    )


@mcp.tool()
def save_change_strategy(
    project_id: str,
    push_to_traceability: bool = False,
    traceability_project_id: str = "",
) -> str:
    """
    Шаг 7 пайплайна 6.4: финализировать стратегию изменения.

    Сохраняет {project}_change_strategy.json (контракт для 7.x, 8.x) и генерирует
    Markdown-отчёт через save_artifact. Опционально регистрирует solution в
    репозитории 5.1 как узел типа 'solution' со связями 'satisfies'.

    Args:
        project_id: Идентификатор проекта
        push_to_traceability: Регистрировать solution в репозитории 5.1 (default: False)
        traceability_project_id: project_id репозитория 5.1 (если отличается от основного)
    """
    strategy = _load_strategy(project_id)
    scope = strategy.get("solution_scope", {})
    readiness = strategy.get("enterprise_readiness", {})
    cs = strategy.get("change_strategy", {})
    states = strategy.get("transition_states", [])

    capabilities = scope.get("capabilities", [])
    selected_id = cs.get("selected_option_id")
    options = cs.get("options", [])

    if not capabilities:
        return "⚠️ Скоуп решения не определён. Вызови `define_solution_scope`."
    if not selected_id:
        return "⚠️ Вариант стратегии не выбран. Вызови `compare_strategy_options`."
    if not readiness:
        return "⚠️ Оценка готовности не заполнена. Вызови `assess_enterprise_readiness`."
    if not states:
        return "⚠️ Фазы перехода не определены. Вызови `define_transition_states`."

    selected_option = next((o for o in options if o.get("option_id") == selected_id), None)
    if not selected_option:
        return f"⚠️ Выбранный вариант {selected_id} не найден в реестре."

    # --- Опциональный push в трассировку 5.1 (ADR-082) ---
    traceability_notes = []
    if push_to_traceability:
        repo_pid = traceability_project_id or project_id
        repo_path = _repo_path(project_id, repo_pid)
        if os.path.exists(repo_path):
            with open(repo_path, encoding="utf-8") as f:
                repo = json.load(f)

            existing_ids = {r["id"] for r in repo.get("requirements", [])}
            sol_id = "SOL-001"

            # Узел solution
            if sol_id not in existing_ids:
                repo.setdefault("requirements", []).append({
                    "id": sol_id,
                    "type": "solution",
                    "title": f"Solution Scope — {project_id}",
                    "version": "1.0",
                    "status": "approved",
                    "added": str(date.today()),
                })
                existing_ids.add(sol_id)
                traceability_notes.append(f"✅ Узел {sol_id} (solution) добавлен в 5.1")

            # Связи satisfies с business_goals
            added_links = 0
            bg_list = strategy.get("imported_context", {}).get("business_goals", [])
            for bg in bg_list:
                bg_id = bg.get("id", "")
                if bg_id and bg_id in existing_ids:
                    repo.setdefault("links", []).append({
                        "from": sol_id,
                        "to": bg_id,
                        "relation": "satisfies",
                        "rationale": f"Solution scope реализует {bg_id}",
                        "added": str(date.today()),
                    })
                    added_links += 1

            if added_links:
                traceability_notes.append(f"✅ Добавлено {added_links} связей satisfies → BG")

            repo["updated"] = str(date.today())
            with open(repo_path, "w", encoding="utf-8") as f:
                json.dump(repo, f, ensure_ascii=False, indent=2)
        else:
            traceability_notes.append(
                f"⚠️ Репозиторий трассировки 5.1 не найден для '{repo_pid}' "
                f"— push пропущен. Сначала инициализируй репозиторий."
            )

    # --- Markdown отчёт ---
    verdict = readiness.get("verdict", "")
    readiness_score = readiness.get("readiness_score", 0)
    excluded = scope.get("explicitly_excluded", [])
    in_scope_caps = [c for c in capabilities if c.get("in_scope", True)]

    md_lines = [
        f"# Стратегия изменения — {project_id}",
        f"**Дата:** {date.today()}  ",
        f"**Тип изменения:** {strategy.get('scope', {}).get('change_type', '')}  ",
        f"**Горизонт:** {strategy.get('scope', {}).get('time_horizon_months', '')} месяцев  ",
        f"**Методология:** {strategy.get('scope', {}).get('methodology', '')}",
        "",
        "---",
        "",
        "## Выбранная стратегия",
        "",
        f"**{selected_id} — {selected_option.get('name', '')}**",
        f"- Тип: {selected_option.get('strategy_type', '')}",
        f"- Инвестиции: {selected_option.get('investment_level', '')}",
        f"- Срок реализации: {selected_option.get('timeline_months', '')} мес.",
        f"- Weighted Score: {selected_option.get('weighted_score', 'N/A')}",
        "",
    ]

    if selected_option.get("pros"):
        md_lines.append("**Преимущества:**")
        for p in selected_option["pros"]:
            md_lines.append(f"- {p}")
        md_lines.append("")

    if selected_option.get("cons"):
        md_lines.append("**Риски / недостатки:**")
        for c in selected_option["cons"]:
            md_lines.append(f"- {c}")
        md_lines.append("")

    if cs.get("opportunity_cost"):
        md_lines.extend([
            "**Opportunity Cost:**",
            cs["opportunity_cost"],
            "",
        ])

    # Rejected alternatives
    rejected = cs.get("rejected_alternatives", [])
    if rejected:
        md_lines.extend(["## Отвергнутые варианты", ""])
        for rej in rejected:
            rej_opt = next((o for o in options if o.get("option_id") == rej["option_id"]), {})
            md_lines.append(
                f"- **{rej['option_id']} — {rej.get('name', '')}** "
                f"(score: {rej.get('weighted_score', 'N/A')}): {rej.get('rationale', '')}"
            )
        md_lines.append("")

    md_lines.extend([
        "---",
        "",
        "## Скоуп решения",
        "",
        f"**Capabilities ({len(in_scope_caps)}):**",
        "",
    ])

    cats = {}
    for cap in in_scope_caps:
        cats.setdefault(cap["category"], []).append(cap)
    for cat, caps_list in sorted(cats.items()):
        md_lines.append(f"### {cat}")
        for cap in caps_list:
            gap_icon = {"high": "🔴", "medium": "🟡", "low": "🟢", "none": "⚪"}.get(cap["gap_severity"], "")
            md_lines.append(
                f"- {cap['name']} {gap_icon} gap:{cap['gap_severity']} | {cap.get('description', '')}"
            )
        md_lines.append("")

    if excluded:
        md_lines.extend(["**Явно вне скоупа:**", ""])
        for ex in excluded:
            md_lines.append(f"- {ex}")
        md_lines.append("")

    md_lines.extend([
        "---",
        "",
        "## Готовность организации",
        "",
        f"**Readiness Score: {readiness_score:.1f} / 5.0 — {verdict}**",
        "",
    ])

    dims = readiness.get("dimensions", {})
    dim_labels = {
        "leadership_commitment": "Готовность руководства",
        "cultural_readiness": "Культурная готовность",
        "resource_availability": "Доступность ресурсов",
        "operational_readiness": "Операционная готовность",
        "technical_readiness": "Техническая готовность",
        "change_history": "История изменений",
    }
    for dim, data in dims.items():
        sc = data.get("score", "?")
        rat = data.get("rationale", "")
        md_lines.append(f"- {dim_labels.get(dim, dim)}: {sc}/5" + (f" — {rat}" if rat else ""))
    md_lines.append("")

    if states:
        md_lines.extend([
            "---",
            "",
            "## Фазы перехода (Transition States)",
            "",
        ])
        for st in states:
            md_lines.extend([
                f"### Фаза {st['phase']}: {st['name']} ({st.get('duration_months', 0)} мес.)",
                "",
            ])
            if st.get("capabilities_delivered"):
                md_lines.append("**Capabilities:**")
                for cap in st["capabilities_delivered"]:
                    md_lines.append(f"- {cap}")
            if st.get("gaps_closed"):
                md_lines.append("\n**Закрытые gaps:**")
                for g in st["gaps_closed"]:
                    md_lines.append(f"- {g}")
            if st.get("risks_remaining"):
                md_lines.append(f"\n**Остающиеся риски:** {', '.join(st['risks_remaining'])}")
            md_lines.extend([
                f"\n**Ценность:** {st.get('value_realizable', '')}",
                "",
            ])

    md_content = "\n".join(md_lines)
    artifact_result = save_artifact(md_content, f"6_4_change_strategy_{_safe(project_id)}")

    # Финализируем JSON
    strategy["status"] = "finalized"
    strategy["finalized_on"] = str(date.today())
    _save_strategy(strategy, project_id)

    json_path = _strategy_path(project_id)
    total_months = sum(s.get("duration_months", 0) for s in states)

    output = [
        f"✅ Стратегия изменения финализирована\n\n",
        f"  Проект:     {project_id}\n",
        f"  Стратегия:  {selected_id} — {selected_option.get('name', '')}\n",
        f"  Тип:        {selected_option.get('strategy_type', '')}\n",
        f"  Фаз:        {len(states)} | Общий срок: {total_months} мес.\n",
        f"  Readiness:  {readiness_score:.1f}/5.0 — {verdict}\n\n",
        f"  📄 JSON (для 7.x, 8.x): `{json_path}`\n",
        artifact_result, "\n",
    ]

    if traceability_notes:
        output.extend(["\n"] + traceability_notes + ["\n"])

    output.append(
        f"\n**Следующие шаги:**\n"
        f"• 7.1 Specify Requirements → скоуп из `solution_scope.capabilities`\n"
        f"• 7.4 Define Requirements Architecture → фазы из `transition_states`\n"
        f"• 7.5 Define Design Options → выбранный вариант + отвергнутые альтернативы\n"
    )

    if verdict != "ready":
        weak = [(d, v["score"]) for d, v in dims.items() if v["score"] <= 2]
        if weak:
            output.append(
                f"\n⚠️ Обратите внимание на низкие измерения готовности: "
                + ", ".join(f"{d}={s}" for d, s in weak)
                + " — план мероприятий перед стартом.\n"
            )

    return "".join(output)


if __name__ == "__main__":
    mcp.run()
