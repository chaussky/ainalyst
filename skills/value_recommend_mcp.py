"""
BABOK 7.6 — Analyze Potential Value and Recommend Solution
MCP tools for assessing the value of design options and forming
the final recommendation for the sponsor.

Tools:
  - add_value_assessment    — assess a single option: benefits, costs, risks
  - compare_value           — automatic Value Score matrix
  - check_value_readiness   — optional pre-flight check
  - save_recommendation     — final Recommendation Document

ADR-042: value assessment structure (benefits/costs/risks per option)
ADR-043: Value Score formula: Benefits×2.0 + Alignment×1.5 - Cost×1.5 - Risk×1.0
ADR-044: check_value_readiness — optional check, does not block
ADR-045: recommendation_type — mandatory Literal with 4 outcomes
ADR-046: {project}_recommendation.json — single store for task 7.6

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
from skills.common import (
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

# Valid values (ADR-045, ADR-042)
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

# Mapping of qualitative assessments to numbers (ADR-043)
MAGNITUDE_MAP = {"Low": 1, "Medium": 2, "High": 3}
CONFIDENCE_MAP = {"Low": 0.5, "Medium": 1.0, "High": 1.5}
RISK_LEVEL_MAP = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}


# ---------------------------------------------------------------------------
# Utilities — paths and file loading
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
    with open(_rec_path(data["project_id"]), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
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
# Math — Value Score (ADR-043)
# ---------------------------------------------------------------------------

def _calc_benefits_score(benefits: list) -> float:
    """Benefits_Score = weighted average (magnitude × confidence) across all benefits."""
    if not benefits:
        return 0.0
    scores = []
    for b in benefits:
        mag = MAGNITUDE_MAP.get(b.get("magnitude", "Low"), 1)
        conf = CONFIDENCE_MAP.get(b.get("confidence", "Medium"), 1.0)
        scores.append(mag * conf)
    return round(sum(scores) / len(scores), 3)


def _calc_cost_score(costs: dict) -> float:
    """Cost_Score = average magnitude across all cost_items of all components."""
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
    Alignment_Score = the share of business goals from 7.3 supported by
    the option's improvement_opportunities. Range: 0.0–1.0
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
        # Simple heuristic: at least one word from the goal appears in opportunities
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
    Computes the Value Score and breakdown.
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
        return "✅ Strong recommendation"
    if score >= 5.0:
        return "🟡 Conditional recommendation"
    if score >= 2.0:
        return "⚠️ Needs review"
    return "❌ Not recommended"


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
    ADR-042: the assessment structure contains benefits, costs, risks.
    Idempotent by option_id: calling again updates the assessment.

    Reads {project}_risks.json if it exists (from task 6.3) — graceful degradation.
    Called separately for each option from 7.5.

    Args:
        project_id:    Project identifier.
        option_id:     Design option ID (from create_design_option in 7.5). For example: OPT-001.
        benefits_json: JSON list of the option's benefits.
                       Each item: {
                         "type": "financial|operational|strategic|regulatory|user_experience",
                         "description": "...",
                         "magnitude": "Low|Medium|High",
                         "tangibility": "tangible|intangible",
                         "confidence": "Low|Medium|High"
                       }
                       Example: '[{"type": "operational", "description": "Reduce processing time",
                                  "magnitude": "High", "tangibility": "tangible", "confidence": "High"}]'
        costs_json:    JSON object of the option's costs.
                       Format: {
                         "components": [
                           {
                             "component": "Component name",
                             "cost_items": [
                               {"category": "development|acquisition|maintenance|operations|resources|opportunity",
                                "description": "...", "magnitude": "Low|Medium|High"}
                             ]
                           }
                         ],
                         "opportunity_cost": "Description of the opportunity cost (optional)"
                       }
        risks_json:    JSON list of risks (optional — if there is no file from 6.3).
                       Each item: {
                         "risk_id": "RSK-001",
                         "description": "...",
                         "probability": "Low|Medium|High",
                         "impact": "Low|Medium|High",
                         "risk_level": "Low|Medium|High|Critical"
                       }
                       If '[]' is passed and {project}_risks.json (6.3) exists —
                       risks will be read from there.
        notes:         Additional notes (optional).

    Returns:
        Confirmation with the Value Score and breakdown.
    """
    logger.info(f"add_value_assessment: project_id='{project_id}', option_id='{option_id}'")

    if not option_id.strip():
        return "❌ option_id cannot be empty. Use the format: OPT-001, OPT-002."

    # Parse benefits
    try:
        benefits = json.loads(benefits_json)
        if not isinstance(benefits, list):
            raise ValueError("Expected a list")
        if not benefits:
            raise ValueError("The benefits list must not be empty")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Failed to parse benefits_json: {e}\n\n"
            f"Expected a non-empty JSON list. Example:\n"
            f'\'[{{"type": "operational", "description": "...", '
            f'"magnitude": "High", "tangibility": "tangible", "confidence": "High"}}]\''
        )

    # Validate benefit types
    invalid_types = [
        b.get("type", "") for b in benefits
        if isinstance(b, dict) and b.get("type", "") not in VALID_BENEFIT_TYPES
    ]
    if invalid_types:
        return (
            f"❌ Invalid benefit types: {invalid_types}\n\n"
            f"Valid types: {', '.join(sorted(VALID_BENEFIT_TYPES))}"
        )

    # Validate magnitude/confidence in benefits
    for b in benefits:
        if not isinstance(b, dict):
            continue
        if b.get("magnitude", "Medium") not in VALID_MAGNITUDES:
            return (
                f"❌ Invalid magnitude in benefits: '{b.get('magnitude')}'.\n"
                f"Valid values: {', '.join(VALID_MAGNITUDES)}"
            )
        if b.get("confidence", "Medium") not in VALID_CONFIDENCES:
            return (
                f"❌ Invalid confidence in benefits: '{b.get('confidence')}'.\n"
                f"Valid values: {', '.join(VALID_CONFIDENCES)}"
            )

    # Parse costs
    try:
        costs = json.loads(costs_json)
        if not isinstance(costs, dict):
            raise ValueError("Expected an object (dict)")
        if "components" not in costs:
            raise ValueError("The 'components' field is required")
        if not isinstance(costs["components"], list):
            raise ValueError("'components' must be a list")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Failed to parse costs_json: {e}\n\n"
            f'Expected an object with a components field. Example:\n'
            f'{{"components": [{{"component": "Backend", "cost_items": ['
            f'{{"category": "development", "description": "...", "magnitude": "High"}}]}}]}}'
        )

    # Validate cost_items
    for comp in costs.get("components", []):
        for ci in comp.get("cost_items", []):
            if not isinstance(ci, dict):
                continue
            if ci.get("category", "") not in VALID_COST_CATEGORIES:
                return (
                    f"❌ Invalid cost category: '{ci.get('category')}'.\n"
                    f"Valid categories: {', '.join(sorted(VALID_COST_CATEGORIES))}"
                )
            if ci.get("magnitude", "Medium") not in VALID_MAGNITUDES:
                return (
                    f"❌ Invalid magnitude in costs: '{ci.get('magnitude')}'.\n"
                    f"Valid values: {', '.join(VALID_MAGNITUDES)}"
                )

    # Parse risks
    try:
        risks_input = json.loads(risks_json) if risks_json.strip() else []
        if not isinstance(risks_input, list):
            raise ValueError("Expected a list")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Failed to parse risks_json: {e}\n\n"
            f"Expected a JSON list. Pass '[]' to use risks from 6.3."
        )

    # Validate risk_level
    for r in risks_input:
        if not isinstance(r, dict):
            continue
        if r.get("risk_level", "Low") not in VALID_RISK_LEVELS:
            return (
                f"❌ Invalid risk_level: '{r.get('risk_level')}'.\n"
                f"Valid values: {', '.join(VALID_RISK_LEVELS)}"
            )

    # Graceful degradation: read risks from 6.3 if risks_input is empty
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

    # Load design_options to get the option data
    do_data = _load_design_options(project_id)
    option_meta = None
    if do_data:
        option_meta = next((o for o in do_data.get("options", []) if o["option_id"] == option_id), None)

    if option_meta is None:
        # Graceful degradation: option not found, but don't block
        option_meta = {"option_id": option_id, "improvement_opportunities": []}

    # Load context for Alignment_Score
    context = _load_context(project_id)

    # Build the assessment
    assessment = {
        "option_id": option_id,
        "benefits": benefits,
        "costs": costs,
        "risks": risks,
        "notes": notes,
        "risks_source": risks_source,
        "assessed_at": str(date.today()),
    }

    # Compute the Value Score
    score_data = _calc_value_score(assessment, option_meta, context)
    assessment["value_score"] = score_data["value_score"]
    assessment["score_breakdown"] = score_data["score_breakdown"]

    # Save
    rec_data = _load_recommendation(project_id)
    is_update = option_id in rec_data.get("value_assessments", {})
    rec_data.setdefault("value_assessments", {})[option_id] = assessment
    _save_recommendation(rec_data)

    action = "updated" if is_update else "added"
    score = score_data["value_score"]
    bd = score_data["score_breakdown"]
    label = _score_label(score)

    lines = [
        f"✅ Value assessment **{action}** — option `{option_id}`",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Option | `{option_id}` |",
        f"| Benefits | {len(benefits)} |",
        f"| Cost components | {len(costs.get('components', []))} |",
        f"| Risks | {len(risks)} ({risks_source}) |",
        f"| **Value Score** | **{score}** — {label} |",
        "",
        "**Score Breakdown:**",
        "",
        f"| Component | Value | Weight |",
        f"|-----------|-------|--------|",
        f"| Benefits Score | {bd['benefits_score']} | ×2.0 = {round(bd['benefits_score']*2, 2)} |",
        f"| Alignment Score | {bd['alignment_score']} | ×1.5 = {round(bd['alignment_score']*1.5, 2)} |",
        f"| Cost Score | -{bd['cost_score']} | ×1.5 = -{round(bd['cost_score']*1.5, 2)} |",
        f"| Risk Penalty | -{bd['risk_penalty']} | ×1.0 = -{round(bd['risk_penalty']*1.0, 2)} |",
        f"| **Value Score** | **{score}** | |",
        "",
    ]

    if not context:
        lines += [
            "> ℹ️ **Alignment Score = 0** — business_context.json (7.3) not found.",
            "> To compute Alignment accurately, create the business context in task 7.3.",
            "",
        ]

    if risks_source == "none":
        lines += [
            "> ℹ️ **No risks specified.** Risk Penalty = 0.",
            "> It's recommended to add risks via the `risks_json` parameter or create a risks file in task 6.3.",
            "",
        ]
    elif risks_source == "6.3_file":
        # The penalty is correct for this option's ABSOLUTE score — the project really
        # does carry that risk. It is useless for COMPARING options, because every
        # option is scored against the same project-wide register, so the term is a
        # constant that cancels out. Saying so is the whole fix: the number appears in
        # a comparison table, where it reads as though it discriminated.
        lines += [
            "> ⚠️ **Risk Penalty is project-wide**, taken from the 6.3 register because no "
            "option-specific risks were supplied.",
            "> Every option therefore receives the SAME penalty: it is correct for this "
            "option's absolute score, but it **does not differentiate** the options in "
            "`compare_value`.",
            "> To make risk discriminate between options, pass option-specific risks via "
            "`risks_json`.",
            "",
        ]

    # Count how many options have been assessed
    total_assessed = len(rec_data.get("value_assessments", {}))
    do_options_count = len(do_data.get("options", [])) if do_data else "?"

    lines += [
        "---",
        "",
        f"Options assessed: **{total_assessed}** of {do_options_count}",
        "",
        "**Next steps:**",
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
                f"— assess the next option."
            )
    else:
        lines.append(
            f"`compare_value(project_id='{project_id}')` — compare all options and determine the winner."
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
    ADR-043: Value Score formula = Benefits×2.0 + Alignment×1.5 - Cost×1.5 - Risk×1.0.

    Reads all value_assessments from {project}_recommendation.json.
    Reads business_context (7.3) for Alignment_Score (optional).
    Saves the result to the `comparison` section of recommendation.json.

    Args:
        project_id: Project identifier.

    Returns:
        A Value Score matrix with ranking and winner.
    """
    logger.info(f"compare_value: project_id='{project_id}'")

    rec_data = _load_recommendation(project_id)
    assessments = rec_data.get("value_assessments", {})

    if not assessments:
        return (
            f"⚠️ No value assessments for project `{project_id}`.\n\n"
            f"First call `add_value_assessment` for each design option."
        )

    # Load context and design_options to recompute with the current context
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

        # Update the score in the assessment
        assessment["value_score"] = score_data["value_score"]
        assessment["score_breakdown"] = score_data["score_breakdown"]

    # Ranking: from high to low
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
        f"<!-- BABOK 7.6 — Value Comparison | Project: {project_id} | {date.today()} -->",
        "",
        f"# 📊 Value Score Matrix — {project_id}",
        "",
        f"**Date:** {date.today()}  ",
        f"**Options:** {len(scores)}  ",
        f"**Winner:** `{winner}`",
        "",
        "---",
        "",
        "## Value Score summary table",
        "",
    ]

    # Table header
    lines += [
        "| Rank | Option | Benefits | Alignment | Cost | Risk | **Score** | Interpretation |",
        "|------|--------|----------|-----------|------|------|-----------|----------------|",
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
        "> **Formula:** Score = Benefits×2.0 + Alignment×1.5 − Cost×1.5 − Risk×1.0",
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
            f"> ⚠️ **The Risk column does not differentiate these options.** Every option "
            f"was scored against the same project-wide 6.3 register (penalty "
            f"{next(iter(penalties.values()))} for all), because no option-specific risks "
            f"were supplied — so the risk term cancels out of the ranking.",
            "> Pass option-specific risks via `risks_json` in `add_value_assessment` to "
            "make risk affect the comparison.",
            "",
        ]

    lines += [
        "---",
        "",
        "## Detailed breakdown",
        "",
    ]

    for option_id in ranking:
        score = scores[option_id]
        bd = breakdowns[option_id]
        is_winner = option_id == winner
        winner_marker = " 🏆 **WINNER**" if is_winner else ""

        # Get the option title
        opt_title = ""
        if do_data:
            opt = next((o for o in do_data.get("options", []) if o["option_id"] == option_id), None)
            if opt:
                opt_title = f" — {opt['title']}"

        lines += [
            f"### `{option_id}`{opt_title}{winner_marker}",
            "",
            f"| Component | Raw | Weight | Contribution |",
            f"|-----------|-----|--------|--------------|",
            f"| Benefits Score | {bd['benefits_score']} | ×2.0 | +{round(bd['benefits_score']*2, 2)} |",
            f"| Alignment Score | {bd['alignment_score']} | ×1.5 | +{round(bd['alignment_score']*1.5, 2)} |",
            f"| Cost Score | {bd['cost_score']} | ×1.5 | -{round(bd['cost_score']*1.5, 2)} |",
            f"| Risk Penalty | {bd['risk_penalty']} | ×1.0 | -{round(bd['risk_penalty']*1.0, 2)} |",
            f"| **Value Score** | | | **{score}** |",
            "",
        ]

        # Show the option's benefits
        assessment = assessments.get(option_id, {})
        benefits = assessment.get("benefits", [])
        if benefits:
            lines.append("**Benefits:**")
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
            lines.append(f"**Risks ({len(risks)}):** maximum level: {int(bd['risk_penalty'])} → {['Low', 'Medium', 'High', 'Critical'][int(min(bd['risk_penalty'], 3))]}")
            lines.append("")

    if not context:
        lines += [
            "> ℹ️ **Alignment Score = 0 for all options** — business_context.json (7.3) not found.",
            "> This lowers the Score for options with many improvement_opportunities.",
            "",
        ]

    lines += [
        "---",
        "",
        "**Next step:**",
        f"`save_recommendation(project_id='{project_id}', recommendation_type='recommend_option', "
        f"recommended_option_id='{winner}', ...)` — save the final recommendation.",
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
    ADR-044: only informs (severity warning/info), does not block.

    What it checks:
    - All options from design_options.json have a value assessment
    - Each assessment has at least one benefit and one cost_item
    - compare_value was called (the comparison field exists)
    - Critical architecture gaps from 7.4 (if any — warning)
    - Unallocated req from 7.5 (if any — info)

    Args:
        project_id: Project identifier.

    Returns:
        A Readiness Report in Markdown (not saved via save_artifact).
    """
    logger.info(f"check_value_readiness: project_id='{project_id}'")

    rec_data = _load_recommendation(project_id)
    do_data = _load_design_options(project_id)
    arch = _load_architecture(project_id)

    issues = []
    warnings = []
    infos = []

    # Check 1: options exist
    if not do_data:
        issues.append(
            "❌ **design_options.json not found** — the task 7.5 file is missing. "
            "Make sure task 7.5 is complete."
        )
    else:
        options = do_data.get("options", [])
        if not options:
            issues.append("❌ **No design options** in design_options.json.")
        else:
            # Check 2: all options assessed
            assessments = rec_data.get("value_assessments", {})
            not_assessed = [o["option_id"] for o in options if o["option_id"] not in assessments]
            if not_assessed:
                issues.append(
                    f"❌ **Not all options assessed**: {not_assessed}.\n"
                    f"  Call `add_value_assessment` for each."
                )

            # Check 3: completeness of each assessment
            for option_id, assessment in assessments.items():
                benefits = assessment.get("benefits", [])
                costs = assessment.get("costs", {})
                cost_items = []
                for comp in costs.get("components", []):
                    cost_items.extend(comp.get("cost_items", []))

                if not benefits:
                    warnings.append(
                        f"⚠️ **`{option_id}`**: no benefits — benefits is empty. "
                        f"Value Score may be understated."
                    )
                if not cost_items:
                    warnings.append(
                        f"⚠️ **`{option_id}`**: no cost items — cost_items is empty. "
                        f"Cost Score = 0, which will overstate the final Score."
                    )

            # Check 4: compare_value was called
            if "comparison" not in rec_data:
                issues.append(
                    "❌ **compare_value not called** — the `comparison` field is missing. "
                    "Call `compare_value` before save_recommendation."
                )

        # Check 5: unallocated req
        allocation = do_data.get("allocation", {})
        if not allocation:
            infos.append(
                "ℹ️ **Allocation is empty** — req are not allocated to versions. "
                "It's recommended to run `allocate_requirements` in task 7.5."
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
                    f"⚠️ **Critical architecture gap**: {text[:100]}. "
                    f"Make sure this gap is accounted for in the value assessment."
                )

    # Summary
    total_issues = len(issues)
    total_warnings = len(warnings)
    total_infos = len(infos)

    status_icon = "✅" if total_issues == 0 else "⚠️" if total_warnings > 0 else "❌"
    status_text = "Ready for recommendation" if total_issues == 0 else "There are issues"

    lines = [
        f"# {status_icon} Value Readiness Report — {project_id}",
        "",
        f"**Date:** {date.today()}  ",
        f"**Status:** {status_text}",
        "",
        f"| Type | Count |",
        f"|------|-------|",
        f"| ❌ Critical (block the recommendation) | {total_issues} |",
        f"| ⚠️ Warnings | {total_warnings} |",
        f"| ℹ️ Info | {total_infos} |",
        "",
        "> ℹ️ This tool only informs — it does not block `save_recommendation`.",
        "",
    ]

    if issues:
        lines += ["---", "", "## ❌ Critical issues", ""]
        for issue in issues:
            lines.append(f"- {issue}")
        lines.append("")

    if warnings:
        lines += ["---", "", "## ⚠️ Warnings", ""]
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")

    if infos:
        lines += ["---", "", "## ℹ️ Info", ""]
        for info in infos:
            lines.append(f"- {info}")
        lines.append("")

    if total_issues == 0 and total_warnings == 0:
        lines += [
            "---",
            "",
            "✅ All checks passed. The data is ready for the final recommendation.",
            "",
        ]

    lines += [
        "---",
        "",
        "**Next step:**",
        f"`save_recommendation(project_id='{project_id}', recommendation_type='...', ...)` "
        f"— save the final Recommendation Document.",
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
    ADR-045: mandatory recommendation_type parameter with 4 outcomes.
    Idempotent: calling again updates the recommendation.

    Four legitimate outcomes per BABOK:
    - recommend_option    — recommend one specific option
    - recommend_parallel  — implement two options in parallel (pilot + main)
    - recommend_reanalyze — no option fits, a new analysis is needed
    - no_action           — the change is not justified, benefits < costs + risks

    Generates 7_6_recommendation_*.md via save_artifact.
    success_metrics become the baseline for Chapter 8 (Solution Evaluation).

    Args:
        project_id:               Project identifier.
        recommendation_type:      Recommendation type:
                                  recommend_option | recommend_parallel |
                                  recommend_reanalyze | no_action
        rationale:                Rationale for the recommendation (required for all types).
                                  For recommend_reanalyze: what exactly is unsatisfactory and why.
                                  For no_action: why the change is not justified.
        recommended_option_id:    ID of the recommended option (required for recommend_option).
                                  Example: 'OPT-002'
        parallel_option_ids_json: JSON list of option IDs for parallel implementation
                                  (for recommend_parallel). Example: '["OPT-001", "OPT-002"]'
        success_metrics_json:     JSON list of success metrics (required for recommend_option
                                  and recommend_parallel). Become the baseline for Chapter 8.
                                  Format: '[{"metric": "Request processing time",
                                             "baseline": "2 hours", "target": "15 minutes",
                                             "measurement_method": "CRM monitoring"}]'
        risks_acknowledged_json:  JSON list of acknowledged risk IDs.
                                  Example: '["RSK-001", "RSK-002"]'
        notes:                    Additional notes (optional).

    Returns:
        The final Recommendation Document + a save confirmation.
    """
    logger.info(
        f"save_recommendation: project_id='{project_id}', "
        f"recommendation_type='{recommendation_type}'"
    )

    # Validate recommendation_type
    if recommendation_type not in VALID_RECOMMENDATION_TYPES:
        return (
            f"❌ Invalid recommendation_type: '{recommendation_type}'.\n\n"
            f"Valid values:\n"
            f"- `recommend_option` — recommend one option\n"
            f"- `recommend_parallel` — implement options in parallel\n"
            f"- `recommend_reanalyze` — a new round of analysis is needed\n"
            f"- `no_action` — the change is not justified"
        )

    if not rationale.strip():
        return "❌ rationale cannot be empty — a rationale is required for any recommendation type."

    # Validate recommended_option_id for recommend_option
    if recommendation_type == "recommend_option" and not recommended_option_id.strip():
        return (
            "❌ `recommend_option` requires the `recommended_option_id` parameter.\n"
            "Specify a design option ID, for example: 'OPT-002'."
        )

    # Parse parallel_option_ids
    try:
        parallel_ids = json.loads(parallel_option_ids_json) if parallel_option_ids_json.strip() else []
        if not isinstance(parallel_ids, list):
            raise ValueError("Expected a list")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Failed to parse parallel_option_ids_json: {e}\n\n"
            f"Expected a JSON list: '[\"OPT-001\", \"OPT-002\"]'"
        )

    # Parse success_metrics
    try:
        success_metrics = json.loads(success_metrics_json) if success_metrics_json.strip() else []
        if not isinstance(success_metrics, list):
            raise ValueError("Expected a list")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Failed to parse success_metrics_json: {e}\n\n"
            f"Expected a JSON list of metrics:\n"
            f'[{{"metric": "...", "baseline": "...", "target": "...", "measurement_method": "..."}}]'
        )

    # Warning: success_metrics are required for recommend_option and recommend_parallel
    metrics_warning = ""
    if recommendation_type in ("recommend_option", "recommend_parallel") and not success_metrics:
        metrics_warning = (
            "\n\n> ⚠️ **It's recommended to specify success_metrics** for `recommend_option` "
            "and `recommend_parallel`.\n"
            "> The metrics become the baseline for Chapter 8 (Solution Evaluation)."
        )

    # Parse risks_acknowledged
    try:
        risks_acknowledged = json.loads(risks_acknowledged_json) if risks_acknowledged_json.strip() else []
        if not isinstance(risks_acknowledged, list):
            raise ValueError("Expected a list")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Failed to parse risks_acknowledged_json: {e}\n\n"
            f"Expected a JSON list of risk IDs: '[\"RSK-001\", \"RSK-002\"]'"
        )

    # Load data
    rec_data = _load_recommendation(project_id)
    assessments = rec_data.get("value_assessments", {})
    comparison = rec_data.get("comparison", {})
    do_data = _load_design_options(project_id)
    context = _load_context(project_id)
    arch = _load_architecture(project_id)

    # Check that option_id exists (for recommend_option)
    if recommended_option_id:
        known_options = list(assessments.keys())
        if do_data:
            known_options = [o["option_id"] for o in do_data.get("options", [])]
        if recommended_option_id not in known_options and known_options:
            return (
                f"❌ Option `{recommended_option_id}` not found.\n\n"
                f"Known options: {', '.join(known_options)}"
            )

    is_update = "recommendation" in rec_data

    # Build the recommendation
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
    # Generate the Recommendation Document
    # ------------------------------------------------------------------

    type_icons = {
        "recommend_option": "✅ Recommendation: implement the option",
        "recommend_parallel": "🔀 Recommendation: parallel implementation",
        "recommend_reanalyze": "🔄 Recommendation: re-analyze",
        "no_action": "⛔ Recommendation: do not implement",
    }
    rec_title = type_icons.get(recommendation_type, recommendation_type)

    doc_lines = [
        f"<!-- BABOK 7.6 — Recommendation Document | Project: {project_id} | {date.today()} -->",
        "",
        f"# 📋 Recommendation Document",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Project | {project_id} |",
        f"| Date | {date.today()} |",
        f"| Recommendation type | **{rec_title}** |",
    ]

    if recommended_option_id:
        opt_title = ""
        if do_data:
            opt = next((o for o in do_data.get("options", []) if o["option_id"] == recommended_option_id), None)
            if opt:
                opt_title = f" — {opt['title']}"
        doc_lines.append(f"| Recommended option | `{recommended_option_id}`{opt_title} |")

    if parallel_ids:
        doc_lines.append(f"| Parallel options | {', '.join(f'`{i}`' for i in parallel_ids)} |")

    doc_lines += ["", "---", ""]

    # Executive Summary
    doc_lines += [
        "## Executive Summary",
        "",
        rationale,
        "",
    ]

    if notes:
        doc_lines += [f"**Notes:** {notes}", ""]

    doc_lines += ["---", ""]

    # Value assessment per option
    if assessments:
        doc_lines += [
            "## Value assessment of options",
            "",
        ]

        ranking = comparison.get("ranking", list(assessments.keys()))
        scores = comparison.get("scores", {})

        # Summary table
        doc_lines += [
            "### Value Score summary table",
            "",
            "| Rank | Option | Value Score | Interpretation |",
            "|------|--------|-------------|----------------|",
        ]
        for rank, opt_id in enumerate(ranking, 1):
            score = scores.get(opt_id, assessments.get(opt_id, {}).get("value_score", "—"))
            label = _score_label(score) if isinstance(score, (int, float)) else "—"
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")
            is_rec = (opt_id == recommended_option_id) or (opt_id in parallel_ids)
            rec_marker = " ⭐" if is_rec else ""
            doc_lines.append(f"| {medal} {rank} | `{opt_id}`{rec_marker} | {score} | {label} |")

        doc_lines += [""]

        # Details per option
        for opt_id in ranking:
            assessment = assessments[opt_id]
            score = assessment.get("value_score", "—")
            bd = assessment.get("score_breakdown", {})
            is_rec = (opt_id == recommended_option_id) or (opt_id in parallel_ids)
            rec_marker = " ⭐ **RECOMMENDED**" if is_rec else ""

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
                    f"| Component | Value | Weight | Contribution |",
                    f"|-----------|-------|--------|--------------|",
                    f"| Benefits Score | {bd.get('benefits_score', '—')} | ×2.0 | +{round(bd.get('benefits_score', 0)*2, 2)} |",
                    f"| Alignment Score | {bd.get('alignment_score', '—')} | ×1.5 | +{round(bd.get('alignment_score', 0)*1.5, 2)} |",
                    f"| Cost Score | {bd.get('cost_score', '—')} | ×1.5 | -{round(bd.get('cost_score', 0)*1.5, 2)} |",
                    f"| Risk Penalty | {bd.get('risk_penalty', '—')} | ×1.0 | -{round(bd.get('risk_penalty', 0)*1.0, 2)} |",
                    "",
                ]

            # Benefits
            benefits = assessment.get("benefits", [])
            if benefits:
                doc_lines.append("**Benefits:**")
                type_icons_map = {
                    "financial": "💰 Financial",
                    "operational": "⚙️ Operational",
                    "strategic": "🎯 Strategic",
                    "regulatory": "📋 Regulatory",
                    "user_experience": "👤 User Experience",
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

            # Risks
            risks = assessment.get("risks", [])
            if risks:
                doc_lines.append("**Risks:**")
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
            "## Success Metrics (baseline for Chapter 8)",
            "",
            "| Metric | Baseline | Target | Measurement method |",
            "|--------|----------|--------|--------------------|",
        ]
        for m in success_metrics:
            doc_lines.append(
                f"| {m.get('metric', '—')} | {m.get('baseline', '—')} | "
                f"{m.get('target', '—')} | {m.get('measurement_method', '—')} |"
            )
        doc_lines += [
            "",
            "> 📌 These metrics become the baseline for Chapter 8 (Solution Evaluation).",
            "",
            "---",
            "",
        ]

    # Acknowledged risks
    if risks_acknowledged:
        doc_lines += [
            "## Risks acknowledged",
            "",
            f"{', '.join(f'`{r}`' for r in risks_acknowledged)}",
            "",
            "---",
            "",
        ]

    # Architecture gaps warning
    if arch:
        critical_gaps = arch.get("gaps", {}).get("critical", [])
        if critical_gaps:
            doc_lines += [
                "## ⚠️ Architecture gaps (for awareness)",
                "",
                f"> Found **{len(critical_gaps)} critical architecture gap(s)** from task 7.4.",
                "> Accounted for in the analysis.",
                "",
                "---",
                "",
            ]

    # Artifact handoff
    doc_lines += [
        "## Artifact handoff",
        "",
        "| Direction | Purpose |",
        "|-----------|---------|",
        "| → **6.4** Define Change Strategy | The recommendation as an input artifact for the change strategy |",
        "| → **Chapter 8** Solution Evaluation | success_metrics become the baseline for solution evaluation |",
        "| → **4.4** Communicate | Communicate the decision to stakeholders |",
    ]

    content = "\n".join(doc_lines)
    save_artifact(content, prefix="7_6_recommendation", project_id=project_id)

    # Response to the user
    action = "updated" if is_update else "created"

    result_lines = [
        f"✅ Recommendation Document **{action}** — **{project_id}**",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Type | `{recommendation_type}` |",
        f"| Date | {date.today()} |",
    ]

    if recommended_option_id:
        result_lines.append(f"| Recommended option | `{recommended_option_id}` |")

    if parallel_ids:
        result_lines.append(f"| Parallel options | {', '.join(parallel_ids)} |")

    result_lines += [
        f"| Success Metrics | {len(success_metrics)} |",
        f"| Risks acknowledged | {len(risks_acknowledged)} |",
        "",
    ]

    if metrics_warning:
        result_lines.append(metrics_warning)

    result_lines += [
        "",
        "Recommendation Document saved via `save_artifact` (prefix: `7_6_recommendation`).",
        "",
        "---",
        "",
        "**Next steps:**",
        "- → **6.4** Define Change Strategy — hand off the recommendation as an input artifact",
        "- → **Chapter 8** Solution Evaluation — use success_metrics as the baseline",
        "- → **4.4** `prepare_communication_package` — communicate the decision to stakeholders",
    ]

    return "\n".join(result_lines)


if __name__ == "__main__":
    mcp.run()
