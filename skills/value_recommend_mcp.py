"""
BABOK 7.6 — Analyze Potential Value and Recommend Solution
MCP tools for assessing the value of design options and forming
the final recommendation for the sponsor.

Tools:
  - add_value_assessment    — assess a single option: benefits, costs, risks
  - compare_value           — automatic Value Score matrix
  - check_value_readiness   — optional pre-flight check
  - save_recommendation     — final Recommendation Document

value assessment structure (benefits/costs/risks per option)
Value Score formula: Benefits×2.0 + Alignment×1.5 - Cost×1.5 - Risk×1.0
check_value_readiness — optional check, does not block
recommendation_type — mandatory Literal with 4 outcomes
{project}_recommendation.json — single store for task 7.6

Reads:  {project}_design_options.json (7.5)
        {project}_business_context.json (7.3, optional)
        {project}_architecture.json (7.4, optional)
        {project}_traceability_repo.json (5.1, optional)
        {project}_risks.json (6.3, optional — graceful degradation)
Writes: {project}_recommendation.json
        7_6_recommendation_*.md (via save_artifact)
Output: Recommendation Document → 6.4 (Change Strategy), Chapter 8 (Solution Evaluation)

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date
from typing import Optional
from mcp.server.fastmcp import FastMCP
from skills.common import (write_json_artifact,
    save_artifact, logger, DATA_DIR, data_path, normalize_project_id,
    read_json_artifact, guard_artifact_errors,
)

mcp = FastMCP("BABOK_Value_Recommend")

RECOMMENDATION_FILENAME = "recommendation.json"
DESIGN_OPTIONS_FILENAME = "design_options.json"
CONTEXT_FILENAME = "business_context.json"
ARCHITECTURE_FILENAME = "architecture.json"
RISKS_FILENAME = "risks.json"
REPO_FILENAME = "traceability_repo.json"

# Допустимые значения (ADR-045, ADR-042)
VALID_RECOMMENDATION_TYPES = {
    "recommend_option",
    "recommend_parallel",
    "recommend_reanalyze",
    "no_action",
}
VALID_BENEFIT_TYPES = {
    "financial", "operational", "strategic", "regulatory", "user_experience"
}
VALID_COST_CATEGORIES = {
    "development", "acquisition", "maintenance", "operations", "resources", "opportunity"
}
VALID_MAGNITUDES = {"Low", "Medium", "High"}
VALID_CONFIDENCES = {"Low", "Medium", "High"}
VALID_RISK_LEVELS = {"Low", "Medium", "High", "Critical"}
VALID_PROBABILITIES = {"Low", "Medium", "High"}
VALID_IMPACTS = {"Low", "Medium", "High"}

# Маппинг качественных оценок в числа (ADR-043)
MAGNITUDE_MAP = {"Low": 1, "Medium": 2, "High": 3}
CONFIDENCE_MAP = {"Low": 0.5, "Medium": 1.0, "High": 1.5}
RISK_LEVEL_MAP = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}


# ---------------------------------------------------------------------------
# Утилиты — пути и загрузка файлов
# ---------------------------------------------------------------------------

def _safe(project_id: str) -> str:
    return normalize_project_id(project_id)


def _rec_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{RECOMMENDATION_FILENAME}")


def _design_options_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{DESIGN_OPTIONS_FILENAME}")


def _context_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{CONTEXT_FILENAME}")


def _architecture_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{ARCHITECTURE_FILENAME}")


def _risks_path(project_id: str) -> str:
    # 6.3 writes the risk register to <pid>_risk_assessment.json (the real producer file); older
    # data may use the flat <pid>_risks.json. Prefer the real one, fall back to legacy (audit
    # finding 7.6-A — the consumer read the wrong filename).
    safe = _safe(project_id)
    real = data_path(project_id, f"{safe}_risk_assessment.json")
    if os.path.exists(real):
        return real
    legacy = data_path(project_id, f"{safe}_{RISKS_FILENAME}")
    return legacy if os.path.exists(legacy) else real


def _repo_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{REPO_FILENAME}")


def _load_json(path: str, default) -> dict:
    if os.path.exists(path):
        # Corrupt -> CorruptArtifactError, converted to a ❌ line at the tool
        # boundary by guard_artifact_errors (the chapters-5 / 7.1-7.3 pattern).
        return read_json_artifact(path, "7.6 stored artifact")
    return default


def _load_recommendation(project_id: str) -> dict:
    return _load_json(_rec_path(project_id), {
        "project_id": project_id,
        "value_assessments": {},
        "created": str(date.today()),
        "updated": str(date.today()),
    })


def _save_recommendation(data: dict) -> None:
    os.makedirs(os.path.dirname(_rec_path(data["project_id"])), exist_ok=True)
    data["updated"] = str(date.today())
    write_json_artifact(_rec_path(data["project_id"]), data)
    logger.info(f"Recommendation saved: {_rec_path(data['project_id'])}")


def _load_design_options(project_id: str) -> Optional[dict]:
    path = _design_options_path(project_id)
    return _load_json(path, None) if os.path.exists(path) else None


def _load_context(project_id: str) -> Optional[dict]:
    path = _context_path(project_id)
    return _load_json(path, None) if os.path.exists(path) else None


def _load_architecture(project_id: str) -> Optional[dict]:
    path = _architecture_path(project_id)
    return _load_json(path, None) if os.path.exists(path) else None


def _load_risks(project_id: str) -> Optional[dict]:
    path = _risks_path(project_id)
    return _load_json(path, None) if os.path.exists(path) else None


# ---------------------------------------------------------------------------
# Математика — Value Score (ADR-043)
# ---------------------------------------------------------------------------

def _calc_benefits_score(benefits: list) -> float:
    """Benefits_Score = среднее взвешенное (magnitude × confidence) по всем выгодам."""
    if not benefits:
        return 0.0
    scores = []
    for b in benefits:
        mag = MAGNITUDE_MAP.get(b.get("magnitude", "Low"), 1)
        conf = CONFIDENCE_MAP.get(b.get("confidence", "Medium"), 1.0)
        scores.append(mag * conf)
    return round(sum(scores) / len(scores), 3)


def _calc_cost_score(costs: dict) -> float:
    """Cost_Score = среднее magnitude по всем cost_items всех компонентов."""
    items = []
    for comp in costs.get("components", []):
        for ci in comp.get("cost_items", []):
            mag = MAGNITUDE_MAP.get(ci.get("magnitude", "Medium"), 2)
            items.append(mag)
    if not items:
        return 0.0
    return round(sum(items) / len(items), 3)


def _calc_alignment_score(option: dict, context: Optional[dict]) -> float:
    """
    Alignment_Score = доля бизнес-целей из 7.3, поддерживаемых
    improvement_opportunities варианта. Диапазон: 0.0–1.0
    """
    if not context:
        return 0.0
    goals = context.get("business_goals", [])
    if not goals:
        return 0.0
    opportunities = option.get("improvement_opportunities", [])
    opp_descriptions = " ".join(
        o.get("description", "").lower() for o in opportunities
    )
    matched = 0
    for goal in goals:
        goal_title = goal.get("title", "").lower()
        # Простая эвристика: хотя бы одно слово из goal встречается в opportunities
        words = [w for w in goal_title.split() if len(w) > 3]
        if any(w in opp_descriptions for w in words):
            matched += 1
    return round(matched / len(goals), 3)


def _risk_level_from_score(score) -> str:
    """Maps a 6.3 risk_score (likelihood × impact, 1-25) to a 7.6 risk_level (audit finding 7.6-A).
    Aligned with the 6.3 zones (High at score >= 15, Medium at >= 6); Critical is reserved for the
    top of the 5×5 matrix (>= 20)."""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "Low"
    if s >= 20:
        return "Critical"
    if s >= 15:
        return "High"
    if s >= 6:
        return "Medium"
    return "Low"


def _risk_level_of(risk: dict) -> str:
    """A risk's level: an explicit risk_level (7.5/manual format) wins; otherwise derive it from a
    6.3 risk_score. This bridges the 6.3 register (risk_score, no risk_level) to the 7.6 formula."""
    lvl = risk.get("risk_level")
    if lvl in RISK_LEVEL_MAP:
        return lvl

    # The ZONE 6.3 computed, when it is there. 6.3 classifies against
    # `max_acceptable_score`, which the analyst sets through set_risk_tolerance;
    # re-deriving the level here from fixed thresholds silently overrode that. On a
    # risk-averse project (threshold 10) a score of 12 is High to 6.3 and was Medium
    # here — in the recommendation that goes to the sponsor, which is the last place
    # the analyst's stated risk appetite should be quietly discarded. 6.3 now persists
    # the zone on each risk record, so the honest answer is simply to read it.
    zone = str(risk.get("zone", "")).lower()
    if zone == "high":
        # 6.3's scale tops out at "high"; Critical stays reserved for the top of the
        # 5x5 matrix, so a high-zone risk scoring >= 20 is still Critical.
        return "Critical" if _score_or_zero(risk) >= 20 else "High"
    if zone == "medium":
        return "Medium"
    if zone == "low":
        return "Low"

    if "risk_score" in risk:
        return _risk_level_from_score(risk.get("risk_score"))
    return "Low"


def _score_or_zero(risk: dict) -> float:
    try:
        return float(risk.get("risk_score", 0))
    except (TypeError, ValueError):
        return 0.0


def _calc_risk_penalty(risks: list) -> float:
    """Risk_Penalty = the maximum risk level among all risks of the option."""
    if not risks:
        return 0.0
    penalties = [RISK_LEVEL_MAP.get(_risk_level_of(r), 0) for r in risks]
    return float(max(penalties))


def _calc_value_score(assessment: dict, option: dict, context: Optional[dict]) -> dict:
    """
    Вычисляет Value Score и breakdown.
    Formula: (Benefits×2.0) + (Alignment×1.5) - (Cost×1.5) - (Risk×1.0)
    """
    benefits_score = _calc_benefits_score(assessment.get("benefits", []))
    cost_score = _calc_cost_score(assessment.get("costs", {}))
    alignment_score = _calc_alignment_score(option, context)
    risk_penalty = _calc_risk_penalty(assessment.get("risks", []))

    value_score = round(
        (benefits_score * 2.0)
        + (alignment_score * 1.5)
        - (cost_score * 1.5)
        - (risk_penalty * 1.0),
        2,
    )

    return {
        "value_score": value_score,
        "score_breakdown": {
            "benefits_score": benefits_score,
            "alignment_score": alignment_score,
            "cost_score": cost_score,
            "risk_penalty": risk_penalty,
            "formula": (
                f"{benefits_score}×2.0 + {alignment_score}×1.5 "
                f"- {cost_score}×1.5 - {risk_penalty}×1.0"
            ),
        },
    }


def _score_label(score: float) -> str:
    if score >= 8.0:
        return "✅ Сильная рекомендация"
    if score >= 5.0:
        return "🟡 Условная рекомендация"
    if score >= 2.0:
        return "⚠️ Требует пересмотра"
    return "❌ Не рекомендуется"


# ---------------------------------------------------------------------------
# 7.6.1 — add_value_assessment (ADR-042)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def add_value_assessment(
    project_id: str,
    option_id: str,
    benefits_json: str,
    costs_json: str,
    risks_json: str = "[]",
    notes: str = "",
) -> str:
    """
    BABOK 7.6 — Assesses the potential value of a single design option.
    the assessment structure contains benefits, costs, risks.
    Idempotent by option_id: calling again updates the assessment.

    Читает {project}_risks.json если существует (из задачи 6.3) — graceful degradation.
    Вызывается отдельно для каждого варианта из 7.5.

    Args:
        project_id:    Идентификатор проекта.
        option_id:     ID варианта дизайна (из create_design_option в 7.5). Например: OPT-001.
        benefits_json: JSON-список выгод варианта.
                       Каждый элемент: {
                         "type": "financial|operational|strategic|regulatory|user_experience",
                         "description": "...",
                         "magnitude": "Low|Medium|High",
                         "tangibility": "tangible|intangible",
                         "confidence": "Low|Medium|High"
                       }
                       Пример: '[{"type": "operational", "description": "Снижение времени обработки",
                                  "magnitude": "High", "tangibility": "tangible", "confidence": "High"}]'
        costs_json:    JSON-объект затрат варианта.
                       Формат: {
                         "components": [
                           {
                             "component": "Название компонента",
                             "cost_items": [
                               {"category": "development|acquisition|maintenance|operations|resources|opportunity",
                                "description": "...", "magnitude": "Low|Medium|High"}
                             ]
                           }
                         ],
                         "opportunity_cost": "Описание альтернативных издержек (опционально)"
                       }
                       Пример: '{"components": [{"component": "Backend", "cost_items": [{"category": "development", "description": "Разработка API", "magnitude": "High"}]}], "opportunity_cost": "Запуск мобильного приложения откладывается"}'
        risks_json:    JSON-список рисков (опционально — если нет файла из 6.3).
                       Каждый элемент: {
                         "risk_id": "RSK-001",
                         "description": "...",
                         "probability": "Low|Medium|High",
                         "impact": "Low|Medium|High",
                         "risk_level": "Low|Medium|High|Critical"
                       }
                       Если передан '[]' и существует {project}_risks.json (6.3) —
                       риски будут прочитаны оттуда.
                       Пример: '[{"risk_id": "RSK-001", "description": "Задержка поставки от вендора", "probability": "Medium", "impact": "High", "risk_level": "High"}]'
        notes:         Дополнительные заметки (необязательно).

    Returns:
        Подтверждение с Value Score и breakdown.
    """
    logger.info(f"add_value_assessment: project_id='{project_id}', option_id='{option_id}'")

    if not option_id.strip():
        return "❌ option_id не может быть пустым. Используй формат: OPT-001, OPT-002."

    # Парсинг benefits
    try:
        benefits = json.loads(benefits_json)
        if not isinstance(benefits, list):
            raise ValueError("Ожидается список")
        if not benefits:
            raise ValueError("Список выгод не должен быть пустым")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Ошибка парсинга benefits_json: {e}\n\n"
            f"Ожидается непустой JSON-список. Пример:\n"
            f'\'[{{"type": "operational", "description": "...", '
            f'"magnitude": "High", "tangibility": "tangible", "confidence": "High"}}]\''
        )

    # Валидация типов выгод
    invalid_types = [
        b.get("type", "") for b in benefits
        if isinstance(b, dict) and b.get("type", "") not in VALID_BENEFIT_TYPES
    ]
    if invalid_types:
        return (
            f"❌ Недопустимые типы выгод: {invalid_types}\n\n"
            f"Допустимые типы: {', '.join(sorted(VALID_BENEFIT_TYPES))}"
        )

    # Валидация magnitude/confidence в benefits
    for b in benefits:
        if not isinstance(b, dict):
            continue
        if b.get("magnitude", "Medium") not in VALID_MAGNITUDES:
            return (
                f"❌ Недопустимый magnitude в benefits: '{b.get('magnitude')}'.\n"
                f"Допустимые значения: {', '.join(VALID_MAGNITUDES)}"
            )
        if b.get("confidence", "Medium") not in VALID_CONFIDENCES:
            return (
                f"❌ Недопустимый confidence в benefits: '{b.get('confidence')}'.\n"
                f"Допустимые значения: {', '.join(VALID_CONFIDENCES)}"
            )

    # Парсинг costs
    try:
        costs = json.loads(costs_json)
        if not isinstance(costs, dict):
            raise ValueError("Ожидается объект (dict)")
        if "components" not in costs:
            raise ValueError("Поле 'components' обязательно")
        if not isinstance(costs["components"], list):
            raise ValueError("'components' должен быть списком")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Ошибка парсинга costs_json: {e}\n\n"
            f'Ожидается объект с полем components. Пример:\n'
            f'{{"components": [{{"component": "Backend", "cost_items": ['
            f'{{"category": "development", "description": "...", "magnitude": "High"}}]}}]}}'
        )

    # Валидация cost_items
    for comp in costs.get("components", []):
        for ci in comp.get("cost_items", []):
            if not isinstance(ci, dict):
                continue
            if ci.get("category", "") not in VALID_COST_CATEGORIES:
                return (
                    f"❌ Недопустимая категория затрат: '{ci.get('category')}'.\n"
                    f"Допустимые категории: {', '.join(sorted(VALID_COST_CATEGORIES))}"
                )
            if ci.get("magnitude", "Medium") not in VALID_MAGNITUDES:
                return (
                    f"❌ Недопустимый magnitude в costs: '{ci.get('magnitude')}'.\n"
                    f"Допустимые значения: {', '.join(VALID_MAGNITUDES)}"
                )

    # Парсинг рисков
    try:
        risks_input = json.loads(risks_json) if risks_json.strip() else []
        if not isinstance(risks_input, list):
            raise ValueError("Ожидается список")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Ошибка парсинга risks_json: {e}\n\n"
            f"Ожидается JSON-список. Передай '[]' для использования рисков из 6.3."
        )

    # Валидация risk_level
    for r in risks_input:
        if not isinstance(r, dict):
            continue
        if r.get("risk_level", "Low") not in VALID_RISK_LEVELS:
            return (
                f"❌ Недопустимый risk_level: '{r.get('risk_level')}'.\n"
                f"Допустимые значения: {', '.join(VALID_RISK_LEVELS)}"
            )

    # Graceful degradation: читаем риски из 6.3 если risks_input пуст
    risks_source = "manual"
    risks = risks_input
    if not risks:
        external_risks = _load_risks(project_id)
        if external_risks:
            risks_node = external_risks.get("risks", [])
            if isinstance(risks_node, dict):
                # legacy shape {option_id: [...]}: take this option, else flatten all option lists
                option_risks = risks_node.get(option_id, [])
                if not option_risks:
                    option_risks = [
                        r for lst in risks_node.values() if isinstance(lst, list) for r in lst
                    ]
            elif isinstance(risks_node, list):
                # 6.3 shape: a flat list of the project's risks (only identified ones count)
                option_risks = [
                    r for r in risks_node
                    if isinstance(r, dict) and r.get("status", "identified") == "identified"
                ]
            else:
                option_risks = []
            risks = option_risks if isinstance(option_risks, list) else []
            risks_source = "6.3_file" if risks else "none"

    # Загружаем design_options для получения данных варианта
    do_data = _load_design_options(project_id)
    option_meta = None
    if do_data:
        option_meta = next((o for o in do_data.get("options", []) if o["option_id"] == option_id), None)

    if option_meta is None:
        # Graceful degradation: вариант не найден, но не блокируем
        option_meta = {"option_id": option_id, "improvement_opportunities": []}

    # Загружаем контекст для Alignment_Score
    context = _load_context(project_id)

    # Формируем assessment
    assessment = {
        "option_id": option_id,
        "benefits": benefits,
        "costs": costs,
        "risks": risks,
        "notes": notes,
        "risks_source": risks_source,
        "assessed_at": str(date.today()),
    }

    # Вычисляем Value Score
    score_data = _calc_value_score(assessment, option_meta, context)
    assessment["value_score"] = score_data["value_score"]
    assessment["score_breakdown"] = score_data["score_breakdown"]

    # Сохраняем
    rec_data = _load_recommendation(project_id)
    is_update = option_id in rec_data.get("value_assessments", {})
    rec_data.setdefault("value_assessments", {})[option_id] = assessment
    _save_recommendation(rec_data)

    action = "обновлена" if is_update else "добавлена"
    score = score_data["value_score"]
    bd = score_data["score_breakdown"]
    label = _score_label(score)

    lines = [
        f"✅ Оценка ценности **{action}** — вариант `{option_id}`",
        "",
        f"| Поле | Значение |",
        f"|------|----------|",
        f"| Вариант | `{option_id}` |",
        f"| Выгод | {len(benefits)} |",
        f"| Компонентов затрат | {len(costs.get('components', []))} |",
        f"| Рисков | {len(risks)} ({risks_source}) |",
        f"| **Value Score** | **{score}** — {label} |",
        "",
        "**Разбор оценки:**",
        "",
        f"| Составляющая | Значение | Вес |",
        f"|-------------|---------|-----|",
        f"| Benefits Score | {bd['benefits_score']} | ×2.0 = {round(bd['benefits_score']*2, 2)} |",
        f"| Alignment Score | {bd['alignment_score']} | ×1.5 = {round(bd['alignment_score']*1.5, 2)} |",
        f"| Cost Score | -{bd['cost_score']} | ×1.5 = -{round(bd['cost_score']*1.5, 2)} |",
        f"| Risk Penalty | -{bd['risk_penalty']} | ×1.0 = -{round(bd['risk_penalty']*1.0, 2)} |",
        f"| **Value Score** | **{score}** | |",
        "",
    ]

    if not context:
        lines += [
            "> ℹ️ **Alignment Score = 0** — файл business_context.json (7.3) не найден.",
            "> Для точного расчёта Alignment создай бизнес-контекст в задаче 7.3.",
            "",
        ]

    if risks_source == "none":
        lines += [
            "> ℹ️ **Риски не указаны.** Risk Penalty = 0.",
            "> Рекомендуется добавить риски через параметр `risks_json` или создать файл рисков в задаче 6.3.",
            "",
        ]
    elif risks_source == "6.3_file":
        # The penalty is correct for this option's ABSOLUTE score — the project really
        # does carry that risk. It is useless for COMPARING options, because every
        # option is scored against the same project-wide register, so the term is a
        # constant that cancels out. Saying so is the whole fix: the number appears in
        # a comparison table, where it reads as though it discriminated.
        lines += [
            "> ⚠️ **Risk Penalty взят по проекту целиком** — из реестра 6.3, потому что "
            "рисков, специфичных для варианта, передано не было.",
            "> Значит каждый вариант получает ОДИН И ТОТ ЖЕ штраф: для абсолютной оценки "
            "этого варианта он верен, но варианты в `compare_value` он **не различает**.",
            "> Чтобы риск различал варианты, передайте специфичные для варианта риски "
            "через `risks_json`.",
            "",
        ]

    # Считаем сколько вариантов оценено
    total_assessed = len(rec_data.get("value_assessments", {}))
    do_options_count = len(do_data.get("options", [])) if do_data else "?"

    lines += [
        "---",
        "",
        f"Оценено вариантов: **{total_assessed}** из {do_options_count}",
        "",
        "**Следующие шаги:**",
    ]

    if isinstance(do_options_count, int) and total_assessed < do_options_count:
        remaining_options = [
            o["option_id"] for o in do_data.get("options", [])
            if o["option_id"] not in rec_data.get("value_assessments", {})
        ]
        if remaining_options:
            next_opt = remaining_options[0]
            lines.append(
                f"`add_value_assessment(project_id='{project_id}', option_id='{next_opt}', ...)` "
                f"— оцени следующий вариант."
            )
    else:
        lines.append(
            f"`compare_value(project_id='{project_id}')` — сравни все варианты и определи winner."
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.6.2 — compare_value (ADR-043)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def compare_value(
    project_id: str,
) -> str:
    """
    BABOK 7.6 — Builds an automatic Value Score matrix of all assessed options.
    Value Score formula = Benefits×2.0 + Alignment×1.5 - Cost×1.5 - Risk×1.0.

    Читает все value_assessments из {project}_recommendation.json.
    Читает business_context (7.3) для Alignment_Score (опционально).
    Сохраняет результат в секцию `comparison` файла recommendation.json.

    Args:
        project_id: Идентификатор проекта.

    Returns:
        Value Score матрица с ranking и winner.
    """
    logger.info(f"compare_value: project_id='{project_id}'")

    rec_data = _load_recommendation(project_id)
    assessments = rec_data.get("value_assessments", {})

    if not assessments:
        return (
            f"⚠️ Нет оценок ценности для проекта `{project_id}`.\n\n"
            f"Сначала вызови `add_value_assessment` для каждого варианта дизайна."
        )

    # Загружаем контекст и design_options для пересчёта с актуальным context
    context = _load_context(project_id)
    do_data = _load_design_options(project_id)

    scores: dict = {}
    breakdowns: dict = {}

    for option_id, assessment in assessments.items():
        option_meta = None
        if do_data:
            option_meta = next(
                (o for o in do_data.get("options", []) if o["option_id"] == option_id), None
            )
        if option_meta is None:
            option_meta = {"option_id": option_id, "improvement_opportunities": []}

        score_data = _calc_value_score(assessment, option_meta, context)
        scores[option_id] = score_data["value_score"]
        breakdowns[option_id] = score_data["score_breakdown"]

        # Обновляем score в assessment
        assessment["value_score"] = score_data["value_score"]
        assessment["score_breakdown"] = score_data["score_breakdown"]

    # Ranking: от высокого к низкому
    ranking = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
    winner = ranking[0] if ranking else None

    comparison = {
        "scores": scores,
        "breakdowns": breakdowns,
        "ranking": ranking,
        "winner": winner,
        "generated_at": str(date.today()),
    }

    rec_data["value_assessments"] = assessments
    rec_data["comparison"] = comparison
    _save_recommendation(rec_data)

    lines = [
        f"<!-- BABOK 7.6 — Value Comparison | Проект: {project_id} | {date.today()} -->",
        "",
        f"# 📊 Value Score Матрица — {project_id}",
        "",
        f"**Дата:** {date.today()}  ",
        f"**Вариантов:** {len(scores)}  ",
        f"**Winner:** `{winner}`",
        "",
        "---",
        "",
        "## Сводная таблица Value Score",
        "",
    ]

    # Заголовок таблицы
    lines += [
        "| Место | Вариант | Benefits | Alignment | Cost | Risk | **Score** | Интерпретация |",
        "|-------|---------|----------|-----------|------|------|-----------|---------------|",
    ]

    for rank, option_id in enumerate(ranking, 1):
        score = scores[option_id]
        bd = breakdowns[option_id]
        label = _score_label(score)
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")
        lines.append(
            f"| {medal} {rank} | `{option_id}` | "
            f"{bd['benefits_score']} | {bd['alignment_score']} | "
            f"{bd['cost_score']} | {bd['risk_penalty']} | "
            f"**{score}** | {label} |"
        )

    lines += [
        "",
        "> **Формула:** Score = Benefits×2.0 + Alignment×1.5 − Cost×1.5 − Risk×1.0",
        "",
    ]

    # If every option's risks came from the project-wide 6.3 register, the Risk column
    # holds the same number in every row: it is a constant, it cancels out of the
    # ranking, and it is the one column here that looks like it discriminated. The
    # score itself stays correct in absolute terms — only the comparative reading of
    # this column is wrong, so the fix is to say so rather than to change the number.
    penalties = {oid: breakdowns[oid].get("risk_penalty", 0) for oid in ranking}
    sources = {
        oid: (rec_data.get("value_assessments", {}).get(oid, {}) or {}).get("risks_source")
        for oid in ranking
    }
    if (len(ranking) > 1 and len(set(penalties.values())) == 1
            and any(v == "6.3_file" for v in sources.values())):
        lines += [
            f"> ⚠️ **Колонка Risk эти варианты не различает.** Все они оценены по одному и "
            f"тому же реестру 6.3 на весь проект (штраф "
            f"{next(iter(penalties.values()))} у всех), потому что рисков, специфичных для "
            f"варианта, передано не было, — и в ранжировании слагаемое риска сокращается.",
            "> Передайте специфичные для варианта риски через `risks_json` в "
            "`add_value_assessment`, чтобы риск влиял на сравнение.",
            "",
        ]

    lines += [
        "---",
        "",
        "## Детальный breakdown",
        "",
    ]

    for option_id in ranking:
        score = scores[option_id]
        bd = breakdowns[option_id]
        is_winner = option_id == winner
        winner_marker = " 🏆 **WINNER**" if is_winner else ""

        # Получаем название варианта
        opt_title = ""
        if do_data:
            opt = next((o for o in do_data.get("options", []) if o["option_id"] == option_id), None)
            if opt:
                opt_title = f" — {opt['title']}"

        lines += [
            f"### `{option_id}`{opt_title}{winner_marker}",
            "",
            f"| Составляющая | Raw | Вес | Вклад |",
            f"|-------------|-----|-----|-------|",
            f"| Benefits Score | {bd['benefits_score']} | ×2.0 | +{round(bd['benefits_score']*2, 2)} |",
            f"| Alignment Score | {bd['alignment_score']} | ×1.5 | +{round(bd['alignment_score']*1.5, 2)} |",
            f"| Cost Score | {bd['cost_score']} | ×1.5 | -{round(bd['cost_score']*1.5, 2)} |",
            f"| Risk Penalty | {bd['risk_penalty']} | ×1.0 | -{round(bd['risk_penalty']*1.0, 2)} |",
            f"| **Value Score** | | | **{score}** |",
            "",
        ]

        # Показываем выгоды варианта
        assessment = assessments.get(option_id, {})
        benefits = assessment.get("benefits", [])
        if benefits:
            lines.append("**Выгоды:**")
            type_icons = {
                "financial": "💰",
                "operational": "⚙️",
                "strategic": "🎯",
                "regulatory": "📋",
                "user_experience": "👤",
            }
            for b in benefits:
                icon = type_icons.get(b.get("type", ""), "•")
                lines.append(
                    f"- {icon} **{b.get('type', '')}** — {b.get('description', '')} "
                    f"(magnitude: {b.get('magnitude', '?')}, confidence: {b.get('confidence', '?')})"
                )
            lines.append("")

        risks = assessment.get("risks", [])
        if risks:
            lines.append(f"**Риски ({len(risks)}):** максимальный уровень: {int(bd['risk_penalty'])} → {['Low', 'Medium', 'High', 'Critical'][int(min(bd['risk_penalty'], 3))]}")
            lines.append("")

    if not context:
        lines += [
            "> ℹ️ **Alignment Score = 0 для всех вариантов** — business_context.json (7.3) не найден.",
            "> Это занижает Score для вариантов с большим количеством improvement_opportunities.",
            "",
        ]

    lines += [
        "---",
        "",
        "**Следующий шаг:**",
        f"`save_recommendation(project_id='{project_id}', recommendation_type='recommend_option', "
        f"recommended_option_id='{winner}', ...)` — сохрани финальную рекомендацию.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.6.3 — check_value_readiness (ADR-044)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def check_value_readiness(
    project_id: str,
) -> str:
    """
    BABOK 7.6 — Optional pre-flight check before save_recommendation.
    only informs (severity warning/info), does not block.

    Что проверяет:
    - Все варианты из design_options.json имеют value assessment
    - У каждого assessment есть хотя бы одна выгода и один cost_item
    - compare_value был вызван (поле comparison существует)
    - Архитектурные critical gaps из 7.4 (если есть — warning)
    - Нераспределённые req из 7.5 (если есть — info)

    Args:
        project_id: Идентификатор проекта.

    Returns:
        Readiness Report в Markdown (не сохраняется через save_artifact).
    """
    logger.info(f"check_value_readiness: project_id='{project_id}'")

    rec_data = _load_recommendation(project_id)
    do_data = _load_design_options(project_id)
    arch = _load_architecture(project_id)

    issues = []
    warnings = []
    infos = []

    # Проверка 1: наличие вариантов
    if not do_data:
        issues.append(
            "❌ **design_options.json не найден** — файл задачи 7.5 отсутствует. "
            "Убедись что задача 7.5 завершена."
        )
    else:
        options = do_data.get("options", [])
        if not options:
            issues.append("❌ **Нет вариантов дизайна** в design_options.json.")
        else:
            # Проверка 2: все варианты оценены
            assessments = rec_data.get("value_assessments", {})
            not_assessed = [o["option_id"] for o in options if o["option_id"] not in assessments]
            if not_assessed:
                issues.append(
                    f"❌ **Не все варианты оценены**: {not_assessed}.\n"
                    f"  Вызови `add_value_assessment` для каждого."
                )

            # Проверка 3: полнота каждой оценки
            for option_id, assessment in assessments.items():
                benefits = assessment.get("benefits", [])
                costs = assessment.get("costs", {})
                cost_items = []
                for comp in costs.get("components", []):
                    cost_items.extend(comp.get("cost_items", []))

                if not benefits:
                    warnings.append(
                        f"⚠️ **`{option_id}`**: нет выгод — benefits пуст. "
                        f"Value Score может быть занижен."
                    )
                if not cost_items:
                    warnings.append(
                        f"⚠️ **`{option_id}`**: нет статей затрат — cost_items пуст. "
                        f"Cost Score = 0, что завысит итоговый Score."
                    )

            # Проверка 4: compare_value вызван
            if "comparison" not in rec_data:
                issues.append(
                    "❌ **compare_value не вызван** — поле `comparison` отсутствует. "
                    "Вызови `compare_value` перед save_recommendation."
                )

        # Проверка 5: нераспределённые req
        allocation = do_data.get("allocation", {})
        if not allocation:
            infos.append(
                "ℹ️ **Allocation пуст** — req не распределены по версиям. "
                "Рекомендуется запустить `allocate_requirements` в задаче 7.5."
            )

    # Check 6: critical gaps from architecture 7.4.
    # 7.4 stores gaps as MESSAGE STRINGS (`[g["message"] for g in gaps_critical]`);
    # older / hand-written files may hold objects. Calling `.get()` on the string
    # shape crashed this tool with AttributeError exactly when the architecture HAD
    # critical gaps — the moment the pre-flight mattered. Accept both spellings.
    if arch:
        critical_gaps = arch.get("gaps", {}).get("critical", [])
        if critical_gaps:
            for gap in critical_gaps:
                text = gap.get("description", "") if isinstance(gap, dict) else str(gap)
                warnings.append(
                    f"⚠️ **Critical-разрыв архитектуры**: {text[:100]}. "
                    f"Убедитесь, что этот разрыв учтён в оценке ценности."
                )

    # Итог
    total_issues = len(issues)
    total_warnings = len(warnings)
    total_infos = len(infos)

    status_icon = "✅" if total_issues == 0 else "⚠️" if total_warnings > 0 else "❌"
    status_text = "Готово к рекомендации" if total_issues == 0 else "Есть замечания"

    lines = [
        f"# {status_icon} Value Readiness Report — {project_id}",
        "",
        f"**Дата:** {date.today()}  ",
        f"**Статус:** {status_text}",
        "",
        f"| Тип | Количество |",
        f"|-----|-----------|",
        f"| ❌ Критические (блокируют рекомендацию) | {total_issues} |",
        f"| ⚠️ Предупреждения | {total_warnings} |",
        f"| ℹ️ Информационные | {total_infos} |",
        "",
        "> ℹ️ Этот инструмент только информирует — он не блокирует `save_recommendation`.",
        "",
    ]

    if issues:
        lines += ["---", "", "## ❌ Критические замечания", ""]
        for issue in issues:
            lines.append(f"- {issue}")
        lines.append("")

    if warnings:
        lines += ["---", "", "## ⚠️ Предупреждения", ""]
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")

    if infos:
        lines += ["---", "", "## ℹ️ Информационные замечания", ""]
        for info in infos:
            lines.append(f"- {info}")
        lines.append("")

    if total_issues == 0 and total_warnings == 0:
        lines += [
            "---",
            "",
            "✅ Все проверки пройдены. Данные готовы для финальной рекомендации.",
            "",
        ]

    lines += [
        "---",
        "",
        "**Следующий шаг:**",
        f"`save_recommendation(project_id='{project_id}', recommendation_type='...', ...)` "
        f"— сохрани финальный Recommendation Document.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.6.4 — save_recommendation (ADR-045)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def save_recommendation(
    project_id: str,
    recommendation_type: str,
    rationale: str,
    recommended_option_id: str = "",
    parallel_option_ids_json: str = "[]",
    success_metrics_json: str = "[]",
    risks_acknowledged_json: str = "[]",
    notes: str = "",
) -> str:
    """
    BABOK 7.6 — Generates the final Recommendation Document.
    mandatory recommendation_type parameter with 4 outcomes.
    Idempotent: calling again updates the recommendation.

    Четыре легитимных исхода по BABOK:
    - recommend_option    — рекомендовать один конкретный вариант
    - recommend_parallel  — реализовать два варианта параллельно (пилот + основное)
    - recommend_reanalyze — ни один вариант не подходит, нужен новый анализ
    - no_action           — изменение не оправдано, выгоды < затраты + риски

    Generates 7_6_recommendation_*.md через save_artifact.
    success_metrics становятся baseline для Главы 8 (Solution Evaluation).

    Args:
        project_id:               Идентификатор проекта.
        recommendation_type:      Тип рекомендации:
                                  recommend_option | recommend_parallel |
                                  recommend_reanalyze | no_action
        rationale:                Обоснование рекомендации (обязательно для всех типов).
                                  Для recommend_reanalyze: что именно не устраивает и почему.
                                  Для no_action: почему изменение не оправдано.
        recommended_option_id:    ID рекомендуемого варианта (обязательно для recommend_option).
                                  Пример: 'OPT-002'
        parallel_option_ids_json: JSON-список ID вариантов для параллельной реализации
                                  (для recommend_parallel). Пример: '["OPT-001", "OPT-002"]'
        success_metrics_json:     JSON-список метрик успеха (обязательно для recommend_option
                                  и recommend_parallel). Становятся baseline для Главы 8.
                                  Формат: '[{"metric": "Время обработки заявки",
                                             "baseline": "2 часа", "target": "15 минут",
                                             "measurement_method": "Мониторинг CRM"}]'
                                  Пример: '[{"metric": "Время обработки заявки", "baseline": "2 часа", "target": "15 минут", "measurement_method": "Мониторинг CRM"}]'
        risks_acknowledged_json:  JSON-список ID рисков принятых к сведению.
                                  Пример: '["RSK-001", "RSK-002"]'
        notes:                    Дополнительные заметки (необязательно).

    Returns:
        Финальный Recommendation Document + подтверждение сохранения.
    """
    logger.info(
        f"save_recommendation: project_id='{project_id}', "
        f"recommendation_type='{recommendation_type}'"
    )

    # Валидация recommendation_type
    if recommendation_type not in VALID_RECOMMENDATION_TYPES:
        return (
            f"❌ Недопустимый recommendation_type: '{recommendation_type}'.\n\n"
            f"Допустимые значения:\n"
            f"- `recommend_option` — рекомендовать один вариант\n"
            f"- `recommend_parallel` — реализовать варианты параллельно\n"
            f"- `recommend_reanalyze` — нужен новый раунд анализа\n"
            f"- `no_action` — изменение не оправдано"
        )

    if not rationale.strip():
        return "❌ rationale не может быть пустым — обоснование обязательно для любого типа рекомендации."

    # Валидация recommended_option_id для recommend_option
    if recommendation_type == "recommend_option" and not recommended_option_id.strip():
        return (
            "❌ Для `recommend_option` обязателен параметр `recommended_option_id`.\n"
            "Укажи ID варианта дизайна, например: 'OPT-002'."
        )

    # Парсинг parallel_option_ids
    try:
        parallel_ids = json.loads(parallel_option_ids_json) if parallel_option_ids_json.strip() else []
        if not isinstance(parallel_ids, list):
            raise ValueError("Ожидается список")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Ошибка парсинга parallel_option_ids_json: {e}\n\n"
            f"Ожидается JSON-список: '[\"OPT-001\", \"OPT-002\"]'"
        )

    # Парсинг success_metrics
    try:
        success_metrics = json.loads(success_metrics_json) if success_metrics_json.strip() else []
        if not isinstance(success_metrics, list):
            raise ValueError("Ожидается список")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Ошибка парсинга success_metrics_json: {e}\n\n"
            f"Ожидается JSON-список метрик:\n"
            f'[{{"metric": "...", "baseline": "...", "target": "...", "measurement_method": "..."}}]'
        )

    # Предупреждение: success_metrics обязательны для recommend_option и recommend_parallel
    metrics_warning = ""
    if recommendation_type in ("recommend_option", "recommend_parallel") and not success_metrics:
        metrics_warning = (
            "\n\n> ⚠️ **Рекомендуется указать success_metrics** для `recommend_option` "
            "и `recommend_parallel`.\n"
            "> Метрики становятся baseline для Главы 8 (Solution Evaluation)."
        )

    # Парсинг risks_acknowledged
    try:
        risks_acknowledged = json.loads(risks_acknowledged_json) if risks_acknowledged_json.strip() else []
        if not isinstance(risks_acknowledged, list):
            raise ValueError("Ожидается список")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Ошибка парсинга risks_acknowledged_json: {e}\n\n"
            f"Ожидается JSON-список ID рисков: '[\"RSK-001\", \"RSK-002\"]'"
        )

    # Загружаем данные
    rec_data = _load_recommendation(project_id)
    assessments = rec_data.get("value_assessments", {})
    comparison = rec_data.get("comparison", {})
    do_data = _load_design_options(project_id)
    context = _load_context(project_id)
    arch = _load_architecture(project_id)

    # Проверяем что option_id существует (для recommend_option)
    if recommended_option_id:
        known_options = list(assessments.keys())
        if do_data:
            known_options = [o["option_id"] for o in do_data.get("options", [])]
        if recommended_option_id not in known_options and known_options:
            return (
                f"❌ Вариант `{recommended_option_id}` не найден.\n\n"
                f"Известные варианты: {', '.join(known_options)}"
            )

    is_update = "recommendation" in rec_data

    # Формируем recommendation
    recommendation = {
        "recommendation_type": recommendation_type,
        "recommended_option_id": recommended_option_id,
        "parallel_option_ids": parallel_ids,
        "rationale": rationale,
        "success_metrics": success_metrics,
        "risks_acknowledged": risks_acknowledged,
        "notes": notes,
        "created": str(date.today()) if not is_update else rec_data.get("recommendation", {}).get("created", str(date.today())),
        "updated": str(date.today()),
    }

    rec_data["recommendation"] = recommendation
    _save_recommendation(rec_data)

    # ------------------------------------------------------------------
    # Генерируем Recommendation Document
    # ------------------------------------------------------------------

    type_icons = {
        "recommend_option": "✅ Рекомендация: реализовать вариант",
        "recommend_parallel": "🔀 Рекомендация: параллельная реализация",
        "recommend_reanalyze": "🔄 Рекомендация: пересмотр анализа",
        "no_action": "⛔ Рекомендация: не реализовывать",
    }
    rec_title = type_icons.get(recommendation_type, recommendation_type)

    doc_lines = [
        f"<!-- BABOK 7.6 — Recommendation Document | Проект: {project_id} | {date.today()} -->",
        "",
        f"# 📋 Recommendation Document",
        "",
        f"| Поле | Значение |",
        f"|------|----------|",
        f"| Проект | {project_id} |",
        f"| Дата | {date.today()} |",
        f"| Тип рекомендации | **{rec_title}** |",
    ]

    if recommended_option_id:
        opt_title = ""
        if do_data:
            opt = next((o for o in do_data.get("options", []) if o["option_id"] == recommended_option_id), None)
            if opt:
                opt_title = f" — {opt['title']}"
        doc_lines.append(f"| Рекомендуемый вариант | `{recommended_option_id}`{opt_title} |")

    if parallel_ids:
        doc_lines.append(f"| Параллельные варианты | {', '.join(f'`{i}`' for i in parallel_ids)} |")

    doc_lines += ["", "---", ""]

    # Executive Summary
    doc_lines += [
        "## Резюме для спонсора",
        "",
        rationale,
        "",
    ]

    if notes:
        doc_lines += [f"**Примечания:** {notes}", ""]

    doc_lines += ["---", ""]

    # Value Assessment по каждому варианту
    if assessments:
        doc_lines += [
            "## Оценка ценности вариантов",
            "",
        ]

        ranking = comparison.get("ranking", list(assessments.keys()))
        scores = comparison.get("scores", {})

        # Сводная таблица
        doc_lines += [
            "### Сводная таблица Value Score",
            "",
            "| Место | Вариант | Value Score | Интерпретация |",
            "|-------|---------|-------------|---------------|",
        ]
        for rank, opt_id in enumerate(ranking, 1):
            score = scores.get(opt_id, assessments.get(opt_id, {}).get("value_score", "—"))
            label = _score_label(score) if isinstance(score, (int, float)) else "—"
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")
            is_rec = (opt_id == recommended_option_id) or (opt_id in parallel_ids)
            rec_marker = " ⭐" if is_rec else ""
            doc_lines.append(f"| {medal} {rank} | `{opt_id}`{rec_marker} | {score} | {label} |")

        doc_lines += [""]

        # Детали по каждому варианту
        for opt_id in ranking:
            assessment = assessments[opt_id]
            score = assessment.get("value_score", "—")
            bd = assessment.get("score_breakdown", {})
            is_rec = (opt_id == recommended_option_id) or (opt_id in parallel_ids)
            rec_marker = " ⭐ **РЕКОМЕНДУЕТСЯ**" if is_rec else ""

            opt_title = ""
            if do_data:
                opt = next((o for o in do_data.get("options", []) if o["option_id"] == opt_id), None)
                if opt:
                    opt_title = f" — {opt['title']}"

            doc_lines += [
                f"### `{opt_id}`{opt_title}{rec_marker}",
                "",
                f"**Value Score: {score}** ({_score_label(score) if isinstance(score, (int, float)) else '—'})",
                "",
            ]

            if bd:
                doc_lines += [
                    f"| Составляющая | Значение | Вес | Вклад |",
                    f"|-------------|---------|-----|-------|",
                    f"| Benefits Score | {bd.get('benefits_score', '—')} | ×2.0 | +{round(bd.get('benefits_score', 0)*2, 2)} |",
                    f"| Alignment Score | {bd.get('alignment_score', '—')} | ×1.5 | +{round(bd.get('alignment_score', 0)*1.5, 2)} |",
                    f"| Cost Score | {bd.get('cost_score', '—')} | ×1.5 | -{round(bd.get('cost_score', 0)*1.5, 2)} |",
                    f"| Risk Penalty | {bd.get('risk_penalty', '—')} | ×1.0 | -{round(bd.get('risk_penalty', 0)*1.0, 2)} |",
                    "",
                ]

            # Выгоды
            benefits = assessment.get("benefits", [])
            if benefits:
                doc_lines.append("**Выгоды:**")
                type_icons_map = {
                    "financial": "💰 Финансовая",
                    "operational": "⚙️ Операционная",
                    "strategic": "🎯 Стратегическая",
                    "regulatory": "📋 Регуляторная",
                    "user_experience": "👤 Пользовательский опыт",
                }
                for b in benefits:
                    type_label = type_icons_map.get(b.get("type", ""), b.get("type", ""))
                    doc_lines.append(
                        f"- **{type_label}** — {b.get('description', '')} "
                        f"(magnitude: {b.get('magnitude', '?')}, "
                        f"confidence: {b.get('confidence', '?')}, "
                        f"tangibility: {b.get('tangibility', '?')})"
                    )
                doc_lines.append("")

            # Риски
            risks = assessment.get("risks", [])
            if risks:
                doc_lines.append("**Риски:**")
                for r in risks:
                    doc_lines.append(
                        f"- `{r.get('risk_id', '?')}` — {r.get('description', '')} "
                        f"(risk_level: **{_risk_level_of(r)}**)"
                    )
                doc_lines.append("")

        doc_lines += ["---", ""]

    # Success Metrics
    if success_metrics:
        doc_lines += [
            "## Success Metrics (baseline для Главы 8)",
            "",
            "| Метрика | Baseline | Target | Метод измерения |",
            "|---------|----------|--------|----------------|",
        ]
        for m in success_metrics:
            doc_lines.append(
                f"| {m.get('metric', '—')} | {m.get('baseline', '—')} | "
                f"{m.get('target', '—')} | {m.get('measurement_method', '—')} |"
            )
        doc_lines += [
            "",
            "> 📌 Эти метрики становятся baseline для Главы 8 (Solution Evaluation).",
            "",
            "---",
            "",
        ]

    # Учтённые риски
    if risks_acknowledged:
        doc_lines += [
            "## Риски, принятые к сведению",
            "",
            f"{', '.join(f'`{r}`' for r in risks_acknowledged)}",
            "",
            "---",
            "",
        ]

    # Architecture gaps предупреждение
    if arch:
        critical_gaps = arch.get("gaps", {}).get("critical", [])
        if critical_gaps:
            doc_lines += [
                "## ⚠️ Архитектурные gaps (к сведению)",
                "",
                f"> Выявлено **{len(critical_gaps)} критических архитектурных gap(ов)** из задачи 7.4.",
                "> Учтены в анализе.",
                "",
                "---",
                "",
            ]

    # Передача артефакта
    doc_lines += [
        "## Передача артефакта",
        "",
        "| Направление | Назначение |",
        "|-------------|-----------|",
        "| → **6.4** Define Change Strategy | Рекомендация как входной артефакт стратегии изменений |",
        "| → **Глава 8** Solution Evaluation | success_metrics становятся baseline оценки решения |",
        "| → **4.4** Communicate | Коммуникация решения стейкхолдерам |",
    ]

    content = "\n".join(doc_lines)
    save_artifact(content, prefix="7_6_recommendation", project_id=project_id)

    # Ответ пользователю
    action = "обновлена" if is_update else "создана"

    result_lines = [
        f"✅ Recommendation Document **{action}** — **{project_id}**",
        "",
        f"| Поле | Значение |",
        f"|------|----------|",
        f"| Тип | `{recommendation_type}` |",
        f"| Дата | {date.today()} |",
    ]

    if recommended_option_id:
        result_lines.append(f"| Рекомендуемый вариант | `{recommended_option_id}` |")

    if parallel_ids:
        result_lines.append(f"| Параллельные варианты | {', '.join(parallel_ids)} |")

    result_lines += [
        f"| Success Metrics | {len(success_metrics)} |",
        f"| Рисков принято к сведению | {len(risks_acknowledged)} |",
        "",
    ]

    if metrics_warning:
        result_lines.append(metrics_warning)

    result_lines += [
        "",
        "Recommendation Document сохранён через `save_artifact` (префикс: `7_6_recommendation`).",
        "",
        "---",
        "",
        "**Следующие шаги:**",
        "- → **6.4** Define Change Strategy — передай рекомендацию как входной артефакт",
        "- → **Глава 8** Solution Evaluation — используй success_metrics как baseline",
        "- → **4.4** `prepare_communication_package` — коммуникация решения стейкхолдерам",
    ]

    return "\n".join(result_lines)


if __name__ == "__main__":
    mcp.run()
