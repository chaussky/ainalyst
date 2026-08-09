"""
BABOK 6.3 — Assess Risks
MCP-инструменты для оценки рисков инициативы.

Инструменты:
  - scope_risk_assessment         — скоуп: тип инициативы, глубина, источники
  - import_risks_from_context     — черновики рисков из 6.1, 6.2, 4.2
  - add_risk                      — добавить/подтвердить риск в реестр
  - set_risk_tolerance            — tolerance level + max_acceptable_score
  - run_risk_matrix               — zone matrix, cumulative profile
  - generate_recommendation       — recommendation type + narrative
  - save_risk_assessment          — finalize: JSON + Markdown + opt. push to 5.1

Storage:
  - {project}_risk_assessment_scope.json  — scope
  - {project}_risk_assessment.json        — risk register (contract for 6.4)
  - {project}_risk_assessment_*.md        — report (via save_artifact)

Integration:
  In: 6.1 (current_state, business_needs), 6.2 (future_state, gap_analysis), 4.2 (elicitation)
  Out: risk_assessment.json → 6.4; risk + threatens nodes → 5.1 (optional)

hybrid storage (own JSON + optional push to 5.1)
import_risks_from_context — draft mode
1-5 x 1-5 scale, Low/Medium/High zones
generate_recommendation — hybrid approach (logic + Claude narrative)
node type `risk` and relation `threatens` in the 5.1 repository
risk card structure (14 fields)
export format for 6.4

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date, datetime
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import (write_json_artifact,
    save_artifact, logger, DATA_DIR, data_path, normalize_project_id,
    read_json_artifact, guard_artifact_errors, secondary_project_ids_error,
)

mcp = FastMCP("BABOK_RiskAssessment")

SCOPE_FILENAME = "risk_assessment_scope.json"
ASSESSMENT_FILENAME = "risk_assessment.json"
REPO_FILENAME = "traceability_repo.json"

# Файлы 6.1 (опциональный источник)
CS_STATE_FILENAME = "current_state.json"
CS_NEEDS_FILENAME = "business_needs.json"

# Файлы 6.2 (опциональный источник)
FS_STATE_FILENAME = "future_state.json"
GAP_FILENAME = "gap_analysis.json"

# Файлы 4.2 (опциональный источник)
ELICITATION_FILENAME = "elicitation_results.json"

VALID_CATEGORIES = ["strategic", "operational", "financial", "technical", "regulatory", "people", "external"]
VALID_SOURCES = ["change", "current_state", "future_state", "requirement", "stakeholder", "assumption", "constraint"]
VALID_STRATEGIES = ["accept", "mitigate", "transfer", "avoid"]
VALID_HORIZONS = ["immediate", "short_term", "medium_term", "long_term"]
VALID_TOLERANCE = ["risk_averse", "neutral", "risk_seeking"]
VALID_DEPTH = ["quick", "standard", "comprehensive"]
VALID_INITIATIVE_TYPES = ["process_improvement", "new_system", "regulatory", "cost_reduction", "market_opportunity", "other"]

ZONE_LABELS = {
    "low": "🟢 Low",
    "medium": "🟡 Medium",
    "high": "🔴 High",
}


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def _safe(project_id: str) -> str:
    return normalize_project_id(project_id)


def _scope_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{SCOPE_FILENAME}")


def _assessment_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{ASSESSMENT_FILENAME}")


def _repo_path(project_id: str, repo_project_id: Optional[str] = None) -> str:
    pid = repo_project_id or project_id
    return data_path(pid, f"{_safe(pid)}_{REPO_FILENAME}")


def _cs_state_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{CS_STATE_FILENAME}")


def _cs_needs_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{CS_NEEDS_FILENAME}")


def _fs_state_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{FS_STATE_FILENAME}")


def _gap_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{GAP_FILENAME}")


def _elicitation_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{ELICITATION_FILENAME}")


def _load_assessment(project_id: str) -> dict:
    path = _assessment_path(project_id)
    if not os.path.exists(path):
        return _empty_assessment(project_id)
    # Corrupt -> CorruptArtifactError, converted to a ❌ line at the tool boundary
    # by guard_artifact_errors. Returning an empty assessment instead would let the
    # next `_save_assessment` overwrite the analyst's whole register with it.
    return read_json_artifact(path, "6.3 risk assessment")


def _save_assessment(data: dict, project_id: str):
    os.makedirs(os.path.dirname(_assessment_path(project_id)), exist_ok=True)
    data["updated"] = str(date.today())
    write_json_artifact(_assessment_path(project_id), data)


def _empty_assessment(project_id: str) -> dict:
    return {
        "project_id": project_id,
        "created": str(date.today()),
        "updated": str(date.today()),
        "scope": {},
        "risk_tolerance": {
            "level": "neutral",
            "max_acceptable_score": 15,
            "organization_context": "",
            "sponsor_risk_appetite": "",
            "mandatory_avoid_categories": [],
            "escalation_threshold": 15,
        },
        "risks": [],
        "risk_matrix": {},
        "cumulative_profile": {},
        "recommendation": {},
    }


def _next_risk_id(risks: list) -> str:
    if not risks:
        return "RK-001"
    existing_nums = []
    for r in risks:
        rid = r.get("risk_id", "")
        if rid.startswith("RK-") and rid[3:].isdigit():
            existing_nums.append(int(rid[3:]))
    if not existing_nums:
        return "RK-001"
    return f"RK-{max(existing_nums) + 1:03d}"


def _zone_for_score(score: int, max_acceptable: int) -> str:
    if score >= max_acceptable:
        return "high"
    elif score >= 6:
        return "medium"
    else:
        return "low"


def _safe_load_json(path: str) -> Optional[dict]:
    """Loads an OPTIONAL import source. Missing -> None (the import branch prints
    its "not found — skipping" warning). Corrupt -> CorruptArtifactError: a file
    that EXISTS but cannot be read must not be reported as "not found" — that is a
    confident false diagnosis, and the analyst would go looking for a missing file
    instead of repairing a damaged one."""
    if not os.path.exists(path):
        return None
    data = read_json_artifact(path, "6.3 import source")
    # The return type says dict and every caller immediately does `.get(...)`, but a
    # JSON file may legally hold a list or a scalar at the top level. A file corrupted
    # into a list would raise AttributeError in all five import branches at once.
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------------------
# Инструменты
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def scope_risk_assessment(
    project_id: str,
    initiative_type: Literal["process_improvement", "new_system", "regulatory", "cost_reduction", "market_opportunity", "other"],
    analysis_depth: Literal["quick", "standard", "comprehensive"],
    source_project_ids: str = "[]",
    ba_notes: str = "",
) -> str:
    """
    Шаг 1 пайплайна 6.3: зафиксировать скоуп оценки рисков.

    Определяет тип инициативы, глубину анализа и источники данных.
    Источники (6.1, 6.2, 4.2) используются в import_risks_from_context.

    Args:
        project_id: Идентификатор проекта
        initiative_type: Тип инициативы (process_improvement/new_system/regulatory/cost_reduction/market_opportunity/other)
        analysis_depth: Глубина анализа (quick=3-5 рисков / standard=7-15 / comprehensive=15-30)
        source_project_ids: JSON-список project_id из 6.1/6.2 для автоимпорта, напр. '["crm_upgrade"]'
        ba_notes: Дополнительный контекст или ограничения
    """
    try:
        source_ids = json.loads(source_project_ids) if source_project_ids.strip() else []
    except json.JSONDecodeError:
        return "❌ Ошибка: source_project_ids должен быть JSON-массивом, напр. '[\"crm\"]'"

    # Validate the OTHER projects' ids here, before anything is written. Carried
    # unchecked, a broken one landed in a saved artifact under a ✅ and the refusal
    # surfaced a step later, from a path helper, naming `project_id` — which the
    # analyst had spelled correctly.
    bad = secondary_project_ids_error(source_ids, "source_project_ids")
    if bad:
        return bad

    scope = {
        "project_id": project_id,
        "initiative_type": initiative_type,
        "analysis_depth": analysis_depth,
        "source_project_ids": source_ids,
        "ba_notes": ba_notes,
        "created": str(date.today()),
    }

    os.makedirs(os.path.dirname(_scope_path(project_id)), exist_ok=True)
    write_json_artifact(_scope_path(project_id), scope)

    # Инициализируем пустой реестр рисков
    assessment = _load_assessment(project_id)
    assessment["scope"] = scope
    _save_assessment(assessment, project_id)

    depth_guide = {
        "quick": "3–5 рисков (ключевые угрозы, ~1 час)",
        "standard": "7–15 рисков (основной анализ, ~2–3 часа)",
        "comprehensive": "15–30 рисков (полный анализ, ~полдня)",
    }

    sources_hint = ""
    if source_ids:
        sources_hint = f"\n  Источники для импорта: {', '.join(source_ids)}"
        sources_hint += "\n  → Вызови `import_risks_from_context` для автоматического сбора черновиков"
    else:
        sources_hint = "\n  Источники 6.1/6.2 не указаны → добавляй риски вручную через `add_risk`"

    return (
        f"✅ Скоуп оценки рисков зафиксирован\n\n"
        f"  Проект:     {project_id}\n"
        f"  Инициатива: {initiative_type}\n"
        f"  Глубина:    {analysis_depth} — {depth_guide[analysis_depth]}\n"
        f"{sources_hint}\n\n"
        f"**Следующий шаг:** `import_risks_from_context` (если есть 6.1/6.2) "
        f"или сразу `add_risk` для первого риска."
    )


@mcp.tool()
@guard_artifact_errors
def import_risks_from_context(
    project_id: str,
    source_project_ids: str = "[]",
) -> str:
    """
    Шаг 2 пайплайна 6.3: собрать черновики рисков из артефактов 6.1, 6.2, 4.2.

    Сканирует доступные артефакты и предлагает черновики рисков со статусом 'draft'.
    BA просматривает черновики и подтверждает нужные через add_risk.
    Graceful degradation: отсутствующие артефакты пропускаются с предупреждением.

    Args:
        project_id: Идентификатор проекта
        source_project_ids: JSON-список project_id для сканирования (по умолчанию — текущий проект)
    """
    try:
        source_ids = json.loads(source_project_ids) if source_project_ids.strip() else []
    except json.JSONDecodeError:
        source_ids = []

    bad = secondary_project_ids_error(source_ids, "source_project_ids")
    if bad:
        return bad

    if not source_ids:
        source_ids = [project_id]

    drafts = []
    warnings = []

    for src_id in source_ids:
        # --- 6.2: ограничения ---
        fs_data = _safe_load_json(_fs_state_path(src_id))
        if fs_data:
            constraints = fs_data.get("constraints", [])
            for c in constraints:
                desc = c.get("description", "")
                category = c.get("category", "")
                if desc:
                    # 6.2 and 6.3 name the same idea differently. `capture_constraints`
                    # offers budget/time/technology/policy/resources/compliance/other —
                    # `regulatory` is not in that vocabulary at all, so comparing
                    # against it meant a compliance constraint always became an
                    # `operational` risk. That is the one category an analyst is most
                    # likely to put in `mandatory_avoid_categories`, so the
                    # misclassification quietly cost the constraint its override.
                    _CONSTRAINT_TO_RISK_CATEGORY = {
                        "compliance": "regulatory",
                        "regulatory": "regulatory",
                        "policy": "regulatory",
                        "budget": "financial",
                        "time": "operational",
                        "technology": "technical",
                        "resources": "operational",
                    }
                    risk_cat = _CONSTRAINT_TO_RISK_CATEGORY.get(
                        str(category).strip().lower(), "operational")
                    drafts.append({
                        "status": "draft",
                        "import_source": f"6.2 constraint ({src_id})",
                        "category": risk_cat,
                        "source": "constraint",
                        "description": f"Если ограничение «{desc}» не будет преодолено, то цели проекта могут быть не достигнуты",
                        "likelihood": 3,
                        "impact": 3,
                        "response_strategy": "mitigate",
                    })
        else:
            warnings.append(f"⚠️ 6.2 future_state не найден для '{src_id}' — пропускаем")

        # --- 6.2: gap-анализ ---
        gap_data = _safe_load_json(_gap_path(src_id))
        if gap_data:
            gaps = gap_data.get("gaps", [])
            for g in gaps:
                complexity = g.get("complexity", "")
                element = g.get("element", g.get("name", ""))
                if complexity == "high" and element:
                    drafts.append({
                        "status": "draft",
                        "import_source": f"6.2 gap_analysis ({src_id})",
                        "category": "technical",
                        "source": "future_state",
                        "description": f"Если gap в элементе «{element}» окажется сложнее ожидаемого, то переход к будущему состоянию затянется",
                        "likelihood": 3,
                        "impact": 4,
                        "response_strategy": "mitigate",
                    })

        # --- 6.1: корневые причины ---
        cs_data = _safe_load_json(_cs_state_path(src_id))
        if cs_data:
            # 6.1 stores root_causes at the TOP level; each record's cause is `root_cause`.
            root_causes = cs_data.get("root_causes", [])
            for rc in root_causes:
                desc = rc if isinstance(rc, str) else rc.get("root_cause", rc.get("description", ""))
                if desc:
                    drafts.append({
                        "status": "draft",
                        "import_source": f"6.1 root_cause_analysis ({src_id})",
                        "category": "operational",
                        "source": "current_state",
                        "description": f"Если корневая причина «{desc}» не будет устранена в ходе проекта, то проблема возникнет снова",
                        "likelihood": 2,
                        "impact": 3,
                        "response_strategy": "mitigate",
                    })
        else:
            warnings.append(f"⚠️ 6.1 current_state не найден для '{src_id}' — пропускаем")

        # --- 6.1: бизнес-потребности высокого приоритета ---
        needs_data = _safe_load_json(_cs_needs_path(src_id))
        if needs_data:
            # 6.1 stores needs under `needs`; title is `need_title`; priority is capitalized.
            needs = needs_data.get("needs", [])
            for need in needs:
                if str(need.get("priority", "")).lower() in ("high", "critical"):
                    bn_id = need.get("id", "BN-?")
                    title = need.get("need_title", need.get("title", need.get("description", "")))
                    if title:
                        drafts.append({
                            "status": "draft",
                            "import_source": f"6.1 business_needs ({src_id})",
                            "category": "strategic",
                            "source": "current_state",
                            "description": f"Если бизнес-потребность {bn_id} «{title}» не будет реализована в полном объёме, то ожидаемая ценность не будет достигнута",
                            "likelihood": 2,
                            "impact": 4,
                            "response_strategy": "mitigate",
                            "linked_bn": bn_id,
                        })

        # --- 4.2: риски, упомянутые стейкхолдерами ---
        elicitation_data = _safe_load_json(_elicitation_path(src_id))
        if elicitation_data:
            risks_mentioned = elicitation_data.get("risks_mentioned", [])
            for rm in risks_mentioned:
                if isinstance(rm, dict):
                    desc = rm.get("description", rm.get("risk", ""))
                    stakeholder = rm.get("stakeholder", rm.get("source", "стейкхолдер"))
                else:
                    desc = str(rm)
                    stakeholder = "стейкхолдер"
                if desc:
                    drafts.append({
                        "status": "draft",
                        "import_source": f"4.2 elicitation ({src_id})",
                        "category": "operational",
                        "source": "stakeholder",
                        "description": f"Стейкхолдер ({stakeholder}) отметил риск: {desc}",
                        "likelihood": 3,
                        "impact": 3,
                        "response_strategy": "mitigate",
                    })
        else:
            warnings.append(
                f"⚠️ 4.2 elicitation results not found for '{src_id}' — skipping "
                f"(run `process_elicitation_results` with `risks_json` to produce it)"
            )

    if not drafts and not warnings:
        return (
            "ℹ️ Источники для импорта не нашли данных.\n\n"
            "Возможные причины:\n"
            "  • Артефакты 6.1/6.2 ещё не заполнены\n"
            "  • project_id не совпадает с указанным в source_project_ids\n\n"
            "→ Добавляй риски вручную через `add_risk`."
        )

    # Сохраняем черновики в assessment
    assessment = _load_assessment(project_id)
    existing_drafts = [r for r in assessment["risks"] if r.get("status") == "draft"]
    # Очищаем старые черновики и добавляем новые
    assessment["risks"] = [r for r in assessment["risks"] if r.get("status") != "draft"]
    assessment["risks"].extend(drafts)
    _save_assessment(assessment, project_id)

    lines = [f"✅ Импортировано черновиков рисков: {len(drafts)}\n"]

    if warnings:
        lines.append("**Предупреждения:**")
        lines.extend(warnings)
        lines.append("")

    lines.append("**Черновики (требуют подтверждения через `add_risk`):**\n")
    for i, d in enumerate(drafts, 1):
        lines.append(
            f"{i}. [{d['category']}] {d['description'][:100]}{'...' if len(d['description']) > 100 else ''}\n"
            f"   Источник: {d['import_source']} | По умолчанию: L={d['likelihood']} × I={d['impact']} → score {d['likelihood'] * d['impact']}\n"
        )

    lines.append(
        "\n**Следующий шаг:** для каждого релевантного черновика вызови `add_risk` "
        "(можно скорректировать оценки). Нерелевантные — просто пропусти."
    )

    return "\n".join(lines)


@mcp.tool()
@guard_artifact_errors
def add_risk(
    project_id: str,
    category: Literal["strategic", "operational", "financial", "technical", "regulatory", "people", "external"],
    source: Literal["change", "current_state", "future_state", "requirement", "stakeholder", "assumption", "constraint"],
    description: str,
    likelihood: int,
    impact: int,
    response_strategy: Literal["accept", "mitigate", "transfer", "avoid"],
    likelihood_rationale: str = "",
    impact_rationale: str = "",
    time_horizon: str = "",
    mitigation_plan: str = "",
    owner: str = "",
    linked_bn: str = "",
    linked_bg: str = "",
    linked_req: str = "",
) -> str:
    """
    Шаг 3 пайплайна 6.3: добавить риск в реестр.

    Автоматически присваивает risk_id (RK-001...) и вычисляет risk_score = likelihood × impact.
    Используется как для подтверждения черновиков из import_risks_from_context,
    так и для добавления новых рисков.

    Args:
        project_id: Идентификатор проекта
        category: Категория риска (strategic/operational/financial/technical/regulatory/people/external)
        source: Источник риска (change/current_state/future_state/requirement/stakeholder/assumption/constraint)
        description: Описание в формате «Если X, то Y»
        likelihood: Вероятность 1–5 (1=<10%, 2=10-30%, 3=30-60%, 4=60-80%, 5=>80%)
        impact: Воздействие 1–5 (1=Negligible, 2=Minor, 3=Moderate, 4=Major, 5=Critical)
        response_strategy: Ответная стратегия (accept/mitigate/transfer/avoid)
        likelihood_rationale: Обоснование оценки вероятности
        impact_rationale: Обоснование оценки воздействия
        time_horizon: Горизонт риска (immediate/short_term/medium_term/long_term)
        mitigation_plan: План снижения (обязателен при strategy=mitigate)
        owner: stakeholder_id из реестра 3.2
        linked_bn: ID бизнес-потребности (BN-xxx)
        linked_bg: ID бизнес-цели (BG-xxx)
        linked_req: ID требования (FR-xxx, BR-xxx...)
    """
    # Валидация
    if not 1 <= likelihood <= 5:
        return f"❌ likelihood должен быть от 1 до 5, получено: {likelihood}"
    if not 1 <= impact <= 5:
        return f"❌ impact должен быть от 1 до 5, получено: {impact}"
    if response_strategy == "mitigate" and not mitigation_plan:
        return "⚠️ При strategy=mitigate рекомендуется заполнить mitigation_plan"

    assessment = _load_assessment(project_id)

    # Удаляем черновики с совпадающим описанием (подтверждение черновика)
    assessment["risks"] = [
        r for r in assessment["risks"]
        if not (r.get("status") == "draft" and r.get("description", "")[:80] == description[:80])
    ]

    risk_id = _next_risk_id([r for r in assessment["risks"] if r.get("status") != "draft"])
    score = likelihood * impact

    risk = {
        "risk_id": risk_id,
        "category": category,
        "source": source,
        "description": description,
        "likelihood": likelihood,
        "likelihood_rationale": likelihood_rationale,
        "impact": impact,
        "impact_rationale": impact_rationale,
        "risk_score": score,
        "time_horizon": time_horizon,
        "response_strategy": response_strategy,
        "mitigation_plan": mitigation_plan,
        "owner": owner,
        "linked_bn": linked_bn,
        "linked_bg": linked_bg,
        "linked_req": linked_req,
        "status": "identified",
        "added": str(date.today()),
    }

    assessment["risks"].append(risk)
    _save_assessment(assessment, project_id)

    # Определяем предварительную зону (до set_risk_tolerance может не быть tolerance)
    max_acc = assessment.get("risk_tolerance", {}).get("max_acceptable_score", 15)
    zone = _zone_for_score(score, max_acc)
    zone_label = ZONE_LABELS[zone]

    total_identified = len([r for r in assessment["risks"] if r.get("status") == "identified"])

    warn = ""
    if response_strategy == "mitigate" and not mitigation_plan:
        warn = "\n  ⚠️ Рекомендуется добавить mitigation_plan"

    return (
        f"✅ Риск добавлен: {risk_id}\n\n"
        f"  Категория:   {category}\n"
        f"  Описание:    {description[:80]}{'...' if len(description) > 80 else ''}\n"
        f"  Оценка:      L={likelihood} × I={impact} = score {score} {zone_label}\n"
        f"  Стратегия:   {response_strategy}\n"
        f"{warn}\n"
        f"  Всего рисков в реестре: {total_identified}\n\n"
        f"→ Продолжай `add_risk` или переходи к `set_risk_tolerance`."
    )


@mcp.tool()
@guard_artifact_errors
def set_risk_tolerance(
    project_id: str,
    tolerance_level: Literal["risk_averse", "neutral", "risk_seeking"],
    max_acceptable_score: int = 15,
    organization_context: str = "",
    sponsor_risk_appetite: str = "",
    mandatory_avoid_categories: str = "[]",
    escalation_threshold: int = 0,
) -> str:
    """
    Шаг 4 пайплайна 6.3: задать толерантность к риску.

    Определяет стратегическую позицию и числовой порог High-рисков.
    Риски с score >= max_acceptable_score считаются High и требуют активного реагирования.

    Args:
        project_id: Идентификатор проекта
        tolerance_level: Уровень толерантности (risk_averse/neutral/risk_seeking)
        max_acceptable_score: Порог High-риска (1–25). Риски >= порога = High. Default: 15
        organization_context: Контекст организации (отрасль, специфика)
        sponsor_risk_appetite: Позиция спонсора (прямая цитата или интерпретация)
        mandatory_avoid_categories: JSON-список категорий, которые всегда → avoid, напр. '["regulatory"]'
        escalation_threshold: Score для эскалации к спонсору (0 = равен max_acceptable_score)
    """
    if not 1 <= max_acceptable_score <= 25:
        return f"❌ max_acceptable_score должен быть от 1 до 25, получено: {max_acceptable_score}"

    try:
        avoid_cats = json.loads(mandatory_avoid_categories) if mandatory_avoid_categories.strip() else []
    except json.JSONDecodeError:
        avoid_cats = []

    esc_threshold = escalation_threshold if escalation_threshold > 0 else max_acceptable_score

    assessment = _load_assessment(project_id)
    assessment["risk_tolerance"] = {
        "level": tolerance_level,
        "max_acceptable_score": max_acceptable_score,
        "organization_context": organization_context,
        "sponsor_risk_appetite": sponsor_risk_appetite,
        "mandatory_avoid_categories": avoid_cats,
        "escalation_threshold": esc_threshold,
        "set_on": str(date.today()),
    }
    _save_assessment(assessment, project_id)

    # Подсказки по калибровке
    hints = {
        "risk_averse": "Рекомендуемый диапазон порога: 10–12. Все риски Medium+ требуют активного плана.",
        "neutral": "Рекомендуемый диапазон порога: 14–16. Стандартный корпоративный подход.",
        "risk_seeking": "Рекомендуемый диапазон порога: 18–20. Скорость и возможности важнее предсказуемости.",
    }

    avoid_note = ""
    if avoid_cats:
        avoid_note = f"\n  Обязательные avoid: {', '.join(avoid_cats)}"

    return (
        f"✅ Толерантность к риску задана\n\n"
        f"  Уровень:         {tolerance_level}\n"
        f"  Порог High-риска: score ≥ {max_acceptable_score} → 🔴 High\n"
        f"  Порог эскалации:  score ≥ {esc_threshold} → требует разговора со спонсором\n"
        f"{avoid_note}\n\n"
        f"  {hints[tolerance_level]}\n\n"
        f"→ Следующий шаг: `run_risk_matrix` для классификации всех рисков."
    )


@mcp.tool()
@guard_artifact_errors
def run_risk_matrix(project_id: str) -> str:
    """
    Шаг 5 пайплайна 6.3: построить матрицу рисков и cumulative profile.

    Классифицирует все риски по зонам (Low/Medium/High) на основе tolerance,
    вычисляет суммарный профиль. Результат используется в generate_recommendation.

    Args:
        project_id: Идентификатор проекта
    """
    assessment = _load_assessment(project_id)
    identified_risks = [r for r in assessment["risks"] if r.get("status") == "identified"]

    if not identified_risks:
        return (
            "⚠️ Реестр рисков пуст. Добавь хотя бы один риск через `add_risk` перед запуском матрицы."
        )

    tolerance = assessment.get("risk_tolerance", {})
    max_acc = tolerance.get("max_acceptable_score", 15)
    mandatory_avoid = tolerance.get("mandatory_avoid_categories", [])

    classified = []
    for r in identified_risks:
        score = r.get("risk_score", r.get("likelihood", 1) * r.get("impact", 1))
        # mandatory_avoid переопределяет стратегию
        if r.get("category") in mandatory_avoid and r.get("response_strategy") != "avoid":
            zone = "high"
            note = " ⚠️ категория в mandatory_avoid — стратегия должна быть avoid"
        else:
            note = ""
            zone = _zone_for_score(score, max_acc)

        # Write the zone back onto the STORED risk, not only into this copy.
        #
        # The zone is a decision, not a restatement of the score: it honours the
        # analyst's `max_acceptable_score` and forces any category in
        # `mandatory_avoid_categories` to high regardless of the number. Keeping it
        # only in `risk_matrix.classified_risks` meant every consumer —
        # generate_recommendation, the 6.3 report itself, and 6.4 scope_change_strategy
        # — fell back to `_zone_for_score(raw)` and silently lost the override, so the
        # summary table and the sections below it could disagree about the same risk.
        r["zone"] = zone
        r["zone_note"] = note
        classified.append({**r, "zone": zone, "zone_note": note})

    high_risks = [r for r in classified if r["zone"] == "high"]
    medium_risks = [r for r in classified if r["zone"] == "medium"]
    low_risks = [r for r in classified if r["zone"] == "low"]

    total_score = sum(r.get("risk_score", 0) for r in classified)
    avg_score = total_score / len(classified) if classified else 0

    cumulative_profile = {
        "total_risks": len(classified),
        "high_risks_count": len(high_risks),
        "medium_risks_count": len(medium_risks),
        "low_risks_count": len(low_risks),
        "above_threshold": len(high_risks),
        "total_score": total_score,
        "avg_score": round(avg_score, 1),
        "max_acceptable_score": max_acc,
    }

    assessment["risk_matrix"] = {
        "classified_risks": classified,
        "run_on": str(date.today()),
    }
    assessment["cumulative_profile"] = cumulative_profile
    _save_assessment(assessment, project_id)

    # --- Форматирование вывода ---
    lines = [
        f"✅ Матрица рисков построена\n",
        f"  Всего рисков: {len(classified)} | Порог High: score ≥ {max_acc}\n",
        f"  🔴 High: {len(high_risks)} | 🟡 Medium: {len(medium_risks)} | 🟢 Low: {len(low_risks)}\n",
        f"  Суммарный score: {total_score} | Средний: {avg_score:.1f}\n",
    ]

    if high_risks:
        lines.append("\n**🔴 High-риски (требуют немедленного внимания):**\n")
        for r in sorted(high_risks, key=lambda x: -x["risk_score"]):
            lines.append(
                f"  {r['risk_id']} [{r['category']}] score={r['risk_score']} "
                f"(L={r['likelihood']}×I={r['impact']}) — {r['description'][:70]}...\n"
                f"    Стратегия: {r['response_strategy']}"
                + (f"{r.get('zone_note', '')}" if r.get("zone_note") else "") + "\n"
            )

    if medium_risks:
        lines.append("\n**🟡 Medium-риски:**\n")
        for r in sorted(medium_risks, key=lambda x: -x["risk_score"]):
            lines.append(
                f"  {r['risk_id']} [{r['category']}] score={r['risk_score']} — "
                f"{r['description'][:60]}...\n"
            )

    if low_risks:
        lines.append(f"\n**🟢 Low-риски:** {len(low_risks)} шт. (детали в JSON)\n")

    lines.append(
        f"\n→ Следующий шаг: `generate_recommendation` для формирования рекомендации спонсору."
    )

    return "".join(lines)


@mcp.tool()
@guard_artifact_errors
def generate_recommendation(
    project_id: str,
    potential_value_summary: str = "",
    value_vs_risk: Literal["", "value_exceeds_risk", "comparable", "risk_exceeds_value"] = "",
) -> str:
    """
    Шаг 6 пайплайна 6.3: сформировать рекомендацию (тип + narrative).

    Deterministic logic determines the recommendation type.
    Claude writes a 2-4 sentence narrative with concrete data.

    Args:
        project_id: Project identifier
        potential_value_summary: Short description of the expected value from 6.2 (if not filled in automatically)
        value_vs_risk: The BA's judgement on whether the expected value justifies the
            cumulative risk exposure. BABOK reserves `seek_higher_value` for
            "potential value < cumulative risk exposure", but that comparison has no
            honest arithmetic here: 6.2 states value qualitatively, and the cumulative
            exposure is a sum of 1-25 risk scores — the units are not comparable, so a
            numeric comparison would be false precision. The trade-off is therefore a
            judgement the BA makes explicitly (the precise numeric version lives in 7.6,
            which scores value against a risk penalty).
            - "risk_exceeds_value" → recommendation `seek_higher_value`
            - "" (default) → the type is decided by the risk logic alone, as before.
    """
    assessment = _load_assessment(project_id)
    profile = assessment.get("cumulative_profile", {})
    tolerance = assessment.get("risk_tolerance", {})
    risks = [r for r in assessment.get("risks", []) if r.get("status") == "identified"]

    if not profile:
        return "⚠️ Сначала запусти `run_risk_matrix` — нужен cumulative profile."

    max_acc = tolerance.get("max_acceptable_score", 15)
    tol_level = tolerance.get("level", "neutral")
    high_count = profile.get("high_risks_count", 0)
    total_score = profile.get("total_score", 0)
    total_risks = profile.get("total_risks", 0)

    # Попытка автозагрузки potential_value из 6.2
    if not potential_value_summary:
        scope = assessment.get("scope", {})
        # scope_risk_assessment stores source_project_ids as [] for the ordinary
        # single-project case (the BA named no external sources). `.get(key, default)`
        # returns that stored [], NOT the default, so the loop never ran and the
        # sponsor recommendation dropped the 6.2 value. Fall back to the project
        # itself, exactly as import_risks_from_context does.
        source_ids = scope.get("source_project_ids") or [project_id]
        for src_id in source_ids:
            fs_data = _safe_load_json(_fs_state_path(src_id))
            if fs_data:
                pv = fs_data.get("potential_value") or {}
                # 6.2 `assess_potential_value` stores the analyst's text under
                # `value_summary`. Reading `summary`/`description` — neither of which
                # that producer ever writes — meant the sponsor recommendation never
                # once mentioned the value the analyst had assessed, while the
                # truthy-dict check made the miss silent and stopped the search.
                # Legacy spellings stay accepted.
                summary = (pv.get("value_summary") or pv.get("summary")
                           or pv.get("description") or "")
                if summary:
                    potential_value_summary = summary
                    break

    # --- Детерминированная логика выбора типа ---
    high_risks = [r for r in risks if r.get("zone", _zone_for_score(r.get("risk_score", 0), max_acc)) == "high"]
    critical_without_mitigation = [
        r for r in high_risks
        if r.get("impact") == 5 and r.get("response_strategy") == "accept" and not r.get("mitigation_plan")
    ]

    # ADR-073 order: an unresolvable critical risk outranks everything; otherwise, if
    # the BA judges the exposure to outweigh the value, the answer is to revisit scope
    # rather than to proceed. Without that judgement the type follows the risk logic alone.
    if critical_without_mitigation:
        rec_type = "do_not_proceed"
    elif value_vs_risk == "risk_exceeds_value":
        rec_type = "seek_higher_value"
    elif not high_risks:
        rec_type = "proceed_despite_risk"
    else:
        rec_type = "proceed_with_mitigation"

    # Описания типов
    rec_descriptions = {
        "proceed_despite_risk": "Продолжать без дополнительных мер",
        "proceed_with_mitigation": "Продолжать с реализацией планов снижения рисков",
        "seek_higher_value": "Пересмотреть скоуп или подход для повышения ценности",
        "do_not_proceed": "Не продолжать до устранения критических рисков",
    }

    # Топ-3 High-риска для narrative
    top_risks = sorted(high_risks, key=lambda x: -x.get("risk_score", 0))[:3]
    top_risk_summary = "; ".join([
        f"{r['risk_id']} (score {r['risk_score']}, {r['response_strategy']})"
        for r in top_risks
    ]) or "нет"

    mitigation_risks = [r for r in high_risks if r.get("response_strategy") == "mitigate"]

    recommendation = {
        "type": rec_type,
        "description": rec_descriptions[rec_type],
        "value_vs_risk": value_vs_risk or "not_assessed",
        "high_risks_addressed": len(mitigation_risks),
        "rationale": (
            f"Из {total_risks} идентифицированных рисков {high_count} находятся в High-зоне "
            f"(score ≥ {max_acc}). Суммарный рисковый профиль: {total_score}. "
            f"Ключевые High-риски: {top_risk_summary}. "
            f"Толерантность организации: {tol_level}. "
            + (f"Ожидаемая ценность: {potential_value_summary}. " if potential_value_summary else "")
            + (
                "The BA judged the cumulative risk exposure to outweigh the expected value. "
                if value_vs_risk == "risk_exceeds_value" else ""
            )
            + (
                f"Once the {len(mitigation_risks)} mitigation plans are executed, the risk profile will decrease."
                if rec_type == "proceed_with_mitigation" else ""
            )
        ),
        "generated_on": str(date.today()),
    }

    assessment["recommendation"] = recommendation
    _save_assessment(assessment, project_id)

    rec_emoji = {
        "proceed_despite_risk": "🟢",
        "proceed_with_mitigation": "🟡",
        "seek_higher_value": "🟠",
        "do_not_proceed": "🔴",
    }

    output = [
        f"✅ Рекомендация сформирована\n\n",
        f"  {rec_emoji.get(rec_type, '◯')} **{rec_type}** — {rec_descriptions[rec_type]}\n\n",
        f"  **Обоснование:** {recommendation['rationale']}\n\n",
    ]

    if rec_type == "proceed_with_mitigation" and top_risks:
        output.append("  **Приоритетные действия (High-риски):**\n")
        for r in top_risks:
            plan = r.get("mitigation_plan", "—")
            output.append(f"  • {r['risk_id']}: {plan[:80]}\n")

    if rec_type == "do_not_proceed":
        output.append(
            "\n  ⚠️ Рекомендация 'do_not_proceed' — критический результат.\n"
            "  Необходима немедленная эскалация к спонсору.\n"
        )

    if rec_type == "seek_higher_value":
        output.append(
            "\n  🟠 The risks are manageable, but you judged them to outweigh the expected value.\n"
            "  Revisit scope or approach in 6.4 (`add_strategy_option`) to raise the value,\n"
            "  or narrow the scope so the exposure drops.\n"
        )

    if not value_vs_risk and high_risks:
        output.append(
            "\n  ℹ️ Value vs risk was not assessed. With High risks present, state whether the\n"
            "  expected value still justifies the exposure: pass `value_vs_risk=` \n"
            "  (value_exceeds_risk / comparable / risk_exceeds_value).\n"
        )

    output.append(
        f"\n→ Следующий шаг: `save_risk_assessment` для финализации и генерации отчёта."
    )

    return "".join(output)


@mcp.tool()
@guard_artifact_errors
def save_risk_assessment(
    project_id: str,
    push_to_traceability: bool = False,
    traceability_project_id: str = "",
) -> str:
    """
    Шаг 7 пайплайна 6.3: финализировать оценку рисков.

    Сохраняет {project}_risk_assessment.json (вход для 6.4) и генерирует
    Markdown-отчёт через save_artifact. Опционально регистрирует риски
    в репозитории 5.1 как узлы типа 'risk' со связями 'threatens'.

    Args:
        project_id: Идентификатор проекта
        push_to_traceability: Регистрировать риски в репозитории 5.1 (default: False)
        traceability_project_id: project_id репозитория 5.1 (если отличается от основного)
    """
    assessment = _load_assessment(project_id)
    risks = [r for r in assessment.get("risks", []) if r.get("status") == "identified"]
    profile = assessment.get("cumulative_profile", {})
    tolerance = assessment.get("risk_tolerance", {})
    recommendation = assessment.get("recommendation", {})

    if not risks:
        return "⚠️ Реестр рисков пуст. Добавь хотя бы один риск через `add_risk`."
    if not recommendation:
        return "⚠️ Сначала вызови `generate_recommendation`."

    # --- Опциональный push в трассировку 5.1 ---
    traceability_notes = []
    if push_to_traceability:
        bad = secondary_project_ids_error(
            [traceability_project_id] if traceability_project_id else [],
            "traceability_project_id")
        if bad:
            return bad
        repo_pid = traceability_project_id or project_id
        repo_path = _repo_path(project_id, repo_pid)
        if os.path.exists(repo_path):
            # The push reads the SHARED 5.1 graph before writing into it — a
            # corrupt repository must stop the push with a named file (via
            # guard_artifact_errors), not crash or write into a broken graph.
            repo = read_json_artifact(repo_path, "5.1 traceability repository")

            existing_ids = {r["id"] for r in repo.get("requirements", [])}
            # Existing threatens edges — so a re-run (re-finalize) does not duplicate them.
            existing_threatens = {
                (l.get("from"), l.get("to"))
                for l in repo.get("links", [])
                if l.get("relation") == "threatens"
            }
            added_nodes = 0
            added_links = 0
            missing_targets = []

            for risk in risks:
                rid = risk["risk_id"]
                if rid not in existing_ids:
                    repo.setdefault("requirements", []).append({
                        "id": rid,
                        "type": "risk",
                        "title": risk["description"][:80],
                        "version": "1.0",
                        "status": risk.get("status", "identified"),
                        "added": str(date.today()),
                    })
                    existing_ids.add(rid)
                    added_nodes += 1

                # threatens links (deduplicated by from/to so re-runs don't pile up)
                for linked_field in ["linked_bn", "linked_bg", "linked_req"]:
                    linked_id = risk.get(linked_field, "")
                    if linked_id and linked_id not in existing_ids:
                        # The existence check is right, but reporting only the count
                        # made its effect invisible: "+0 threatens links" beside a ✅
                        # reads as success, when in fact every target was missing.
                        missing_targets.append((rid, linked_id))
                        continue
                    if linked_id and linked_id in existing_ids and (rid, linked_id) not in existing_threatens:
                        repo.setdefault("links", []).append({
                            "from": rid,
                            "to": linked_id,
                            "relation": "threatens",
                            "rationale": f"Риск угрожает {linked_id}",
                            "added": str(date.today()),
                        })
                        existing_threatens.add((rid, linked_id))
                        added_links += 1

            repo["updated"] = str(date.today())
            write_json_artifact(repo_path, repo)

            traceability_notes.append(
                f"✅ Трассировка 5.1 обновлена: +{added_nodes} узлов risk, +{added_links} связей threatens"
            )
            if missing_targets:
                # Without this the analyst reads "+0 links" as "nothing needed doing".
                pairs = ", ".join(f"`{r}` → `{t}`" for r, t in missing_targets[:5])
                more = f" (+{len(missing_targets) - 5} more)" if len(missing_targets) > 5 else ""
                traceability_notes.append(
                    f"⚠️ {len(missing_targets)} link(s) NOT written — the target is not a "
                    f"node in the 5.1 repository: {pairs}{more}.\n"
                    f"   Register the objective or requirement first, then re-run the push."
                )
        else:
            traceability_notes.append(
                f"⚠️ Репозиторий трассировки 5.1 не найден для '{repo_pid}' "
                f"— push пропущен. Сначала инициализируй репозиторий через `init_traceability_repo`."
            )

    # --- Markdown отчёт ---
    high_risks = [r for r in risks if r.get("zone", _zone_for_score(r.get("risk_score", 0), tolerance.get("max_acceptable_score", 15))) == "high"]
    medium_risks = [r for r in risks if r.get("zone", _zone_for_score(r.get("risk_score", 0), tolerance.get("max_acceptable_score", 15))) == "medium"]
    low_risks = [r for r in risks if r.get("zone", _zone_for_score(r.get("risk_score", 0), tolerance.get("max_acceptable_score", 15))) == "low"]

    rec_type = recommendation.get("type", "")
    rec_emoji = {"proceed_despite_risk": "🟢", "proceed_with_mitigation": "🟡", "seek_higher_value": "🟠", "do_not_proceed": "🔴"}

    md_lines = [
        f"# Оценка рисков — {project_id}",
        f"**Дата:** {date.today()}  ",
        f"**Толерантность:** {tolerance.get('level', 'neutral')} | Порог High: {tolerance.get('max_acceptable_score', 15)}",
        "",
        "---",
        "",
        "## Резюме",
        "",
        f"| Параметр | Значение |",
        f"|----------|---------|",
        f"| Всего рисков | {profile.get('total_risks', len(risks))} |",
        f"| 🔴 High | {profile.get('high_risks_count', len(high_risks))} |",
        f"| 🟡 Medium | {profile.get('medium_risks_count', len(medium_risks))} |",
        f"| 🟢 Low | {profile.get('low_risks_count', len(low_risks))} |",
        f"| Суммарный score | {profile.get('total_score', 0)} |",
        f"| Средний score | {profile.get('avg_score', 0)} |",
        "",
        f"## Рекомендация",
        "",
        f"{rec_emoji.get(rec_type, '◯')} **{rec_type}** — {recommendation.get('description', '')}",
        "",
        f"{recommendation.get('rationale', '')}",
        "",
        "---",
        "",
        "## Реестр рисков",
        "",
    ]

    def _risks_section(title: str, risk_list: list) -> list:
        if not risk_list:
            return []
        out = [f"### {title}", ""]
        for r in sorted(risk_list, key=lambda x: -x.get("risk_score", 0)):
            out.extend([
                f"#### {r['risk_id']} — {r['description'][:60]}",
                f"- **Категория:** {r['category']} | **Источник:** {r['source']}",
                f"- **Оценка:** L={r['likelihood']} × I={r['impact']} = score {r['risk_score']}",
                f"- **Стратегия:** {r['response_strategy']}",
            ])
            if r.get("mitigation_plan"):
                out.append(f"- **План снижения:** {r['mitigation_plan']}")
            if r.get("owner"):
                out.append(f"- **Владелец:** {r['owner']}")
            out.append("")
        return out

    md_lines.extend(_risks_section("🔴 High-риски", high_risks))
    md_lines.extend(_risks_section("🟡 Medium-риски", medium_risks))
    md_lines.extend(_risks_section("🟢 Low-риски", low_risks))

    md_content = "\n".join(md_lines)
    artifact_result = save_artifact(md_content, f"6_3_risk_assessment_{_safe(project_id)}", project_id=project_id)

    # Финализируем JSON
    assessment["status"] = "finalized"
    assessment["finalized_on"] = str(date.today())
    _save_assessment(assessment, project_id)

    json_path = _assessment_path(project_id)

    output = [
        f"✅ Оценка рисков финализирована\n\n",
        f"  Проект: {project_id}\n",
        f"  Рисков: {len(risks)} | High: {len(high_risks)} | Medium: {len(medium_risks)} | Low: {len(low_risks)}\n",
        f"  Рекомендация: {rec_emoji.get(rec_type, '')} {rec_type}\n\n",
        f"  📄 JSON (для 6.4): `{json_path}`\n",
        artifact_result, "\n",
    ]

    if traceability_notes:
        output.extend(["\n"] + traceability_notes)

    output.append(
        f"\n\n**Следующий шаг:**\n"
        f"• Для спонсора: предоставь Markdown-отчёт\n"
        f"• Для 6.4 Define Change Strategy: передай `{json_path}`\n"
    )
    if high_risks:
        output.append(f"• Приоритет: назначь владельцев для {len(high_risks)} High-рисков\n")

    return "".join(output)


if __name__ == "__main__":
    mcp.run()
