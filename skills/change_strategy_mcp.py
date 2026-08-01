"""
BABOK 6.4 — Define Change Strategy
MCP tools for defining the change strategy.

Tools:
  - scope_change_strategy       — initialization + auto-import from 6.1, 6.2 (goals + gaps), 6.3
  - define_solution_scope       — capabilities by category + explicitly_excluded
  - assess_enterprise_readiness — 6 readiness dimensions x score 1-5 -> readiness_score
  - add_strategy_option         — strategy option card
  - compare_strategy_options    — weighted matrix -> winner + opportunity cost
  - define_transition_states    — transition phases with capabilities, gaps, risks, value
  - save_change_strategy        — finalize: JSON + Markdown + opt. push to 5.1

Storage:
  - {project}_change_strategy_scope.json  — scope and context
  - {project}_change_strategy.json        — final artifact (contract for 7.x, 8.x)

Integration:
  In: 6.1 (business_needs), 6.2 (future_state_goals + gap_analysis), 6.3 (risk_assessment)
      The 6.2 gap analysis is imported as CONTEXT and cross-checked against the
      capabilities: gap_severity and in_scope stay the analyst's own judgement and are
      never written by the import (6.2 measures change EFFORT, 6.4 measures gap SIZE).
  Out: change_strategy.json -> 7.1, 7.4, 7.5, 7.6, 8.x;
       solution_scope + satisfies node -> 5.1 (optional)

ADR-077: scope_change_strategy — auto-import from 6.1+6.2+6.3, graceful degradation
ADR-078: GAP embedded in define_solution_scope (gap_severity + gap_source)
ADR-079: 6 readiness dimensions (change_history added to the base 5)
ADR-080: do_nothing is added automatically as OPT-000
ADR-081: default 6 criteria + optional custom ones
ADR-082: node type `solution_scope` in the 5.1 repository (revised 2026-07-21 from `solution`)
ADR-083: JSON contract — a single file with solution_scope + change_strategy sections

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import (save_artifact, logger, DATA_DIR, data_path,
                           normalize_project_id, SOLUTION_SCOPE_NODE_TYPE,
    read_json_artifact, guard_artifact_errors,
)

mcp = FastMCP("BABOK_ChangeStrategy")

SCOPE_FILENAME = "change_strategy_scope.json"
STRATEGY_FILENAME = "change_strategy.json"
REPO_FILENAME = "traceability_repo.json"

# Files from previous tasks (optional sources)
BUSINESS_NEEDS_FILENAME = "business_needs.json"
FUTURE_STATE_GOALS_FILENAME = "future_state_goals.json"  # 6.2 stores goals separately
RISK_ASSESSMENT_FILENAME = "risk_assessment.json"
# 6.2 writes the gap analysis; 6.4 reads it. The name is duplicated rather than
# imported from future_state_mcp on purpose — these are two separate MCP servers,
# and the three filenames above already follow this pattern.
GAP_ANALYSIS_FILENAME = "gap_analysis.json"

VALID_CHANGE_TYPES = ["transformation", "process_improvement", "technology_implementation", "regulatory_compliance", "other"]
VALID_METHODOLOGIES = ["agile", "waterfall", "hybrid"]
VALID_STRATEGY_TYPES = ["big_bang", "phased", "pilot_first", "do_nothing"]
VALID_INVESTMENT_LEVELS = ["high", "medium", "low"]
VALID_RISK_IMPACTS = ["mitigates", "exacerbates", "neutral"]
VALID_CAP_CATEGORIES = ["process", "technology", "data", "people", "org_structure", "knowledge", "location"]
VALID_GAP_SEVERITIES = ["none", "low", "medium", "high"]
# 6.2's eight future-state elements — the vocabulary `gap_source` draws from. Duplicated
# rather than imported from future_state_mcp on purpose: these are two separate MCP
# servers, only one of which is loaded in most phases, and the four import filenames
# above already follow this rule. Without a dictionary here, "6.2:process" — a 6.4
# CATEGORY, the most plausible mistake there is — was accepted in silence.
VALID_GAP_ELEMENTS = ["business_needs", "org_structure", "capabilities", "technology",
                      "policies", "architecture", "assets", "external"]
_VALID_GAP_ELEMENT_KEYS = {e.casefold() for e in VALID_GAP_ELEMENTS}
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
# Utilities
# ---------------------------------------------------------------------------

def _safe(project_id: str) -> str:
    return normalize_project_id(project_id)


def _scope_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{SCOPE_FILENAME}")


def _gap_file_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{GAP_ANALYSIS_FILENAME}")


def _strategy_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{STRATEGY_FILENAME}")


def _repo_path(project_id: str, repo_project_id: Optional[str] = None) -> str:
    pid = repo_project_id or project_id
    return data_path(pid, f"{_safe(pid)}_{REPO_FILENAME}")


def _safe_load_json(path: str) -> Optional[dict]:
    """Loads an OPTIONAL import source. Missing -> None (the caller prints its
    "not found — skipping" warning). Corrupt -> CorruptArtifactError: an existing
    but unreadable file reported as "not found" sends the analyst hunting for a
    missing file instead of repairing a damaged one."""
    if not os.path.exists(path):
        return None
    return read_json_artifact(path, "6.4 import source")


def _normalize_strategy(data: dict, project_id: str) -> dict:
    """Guarantees the skeleton every 6.4 tool indexes into, whoever wrote the file.

    7.5 `set_change_strategy` is a flat surrogate for this chapter and writes the SAME
    filename. 7.5 already knows how to detect the rich 6.4 contract and refuse to
    overwrite it — but the protection was one-directional, so an analyst who used the
    surrogate in the `design` phase and then came to do the real 6.4 in `analysis` hit
    `KeyError: 'change_strategy'` in three of the five tools, leaving the chapter
    unusable for that project until someone hand-edited the JSON.

    Fill in what is missing and keep what is there: the surrogate's own fields
    (change_type, scope, timeline, constraints) are real analyst input.
    """
    if not isinstance(data, dict):
        return _empty_strategy(project_id)
    # The 7.5 surrogate writes `scope` as a flat STRING, while every 6.4 reader indexes
    # it as a dict (scope.get('change_type')...). If a BA used the surrogate and then
    # ran a 6.4 tool WITHOUT scope_change_strategy (the only tool that rewrites scope to
    # a dict), save_change_strategy hit `AttributeError: 'str' object has no attribute
    # 'get'` instead of returning a readable result. Coerce a non-dict scope to a dict,
    # keeping the surrogate's text so nothing the analyst wrote is lost.
    if "scope" in data and not isinstance(data["scope"], dict):
        data["scope"] = {"scope_summary": data["scope"]}
    skeleton = _empty_strategy(project_id)
    for key, value in skeleton.items():
        data.setdefault(key, value)
    return data


def _load_strategy(project_id: str) -> dict:
    path = _strategy_path(project_id)
    if not os.path.exists(path):
        return _empty_strategy(project_id)
    # A corrupt file must RAISE (converted to a ❌ line at the tool boundary), not
    # silently become an empty skeleton: every writing tool in this module calls
    # `_save_strategy` next, so the skeleton would OVERWRITE the analyst's whole
    # strategy while the tool answered "✅" — reproduced live on the audit run:
    # a 10 560-byte strategy file replaced by a 933-byte skeleton. Degradation may
    # say LESS; it may never destroy what it could not read ("Never delete data").
    data = read_json_artifact(path, "6.4 change strategy")
    return _normalize_strategy(data, project_id)


def _save_strategy(data: dict, project_id: str):
    os.makedirs(os.path.dirname(_strategy_path(project_id)), exist_ok=True)
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
            "gaps": [],
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
    """Generates the next OPT-xxx ID (skips OPT-000)."""
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


# --- 6.2 gap coverage (ADR-097) -------------------------------------------
# The join between 6.2 and 6.4 is what the ANALYST declared in `gap_source`, never
# what the platform inferred. The two chapters use different vocabularies: 6.2's
# eight ELEMENTS overlap 6.4's seven CATEGORIES on exactly two values, so matching
# by category would report six of eight elements uncovered on every project — an
# accusation manufactured by a namespace mismatch.

# 6.2 records a gap card for every future-state element it captured, including the two
# that describe the CONTEXT of the change rather than a capability the organisation
# must acquire. `business_needs` is in every one of 6.2's default element sets and
# `external` is influences nobody builds a capability for. Counting them as uncovered
# manufactures an accusation out of a vocabulary mismatch — the very thing matching by
# category was rejected for, one level down.
GAP_CONTEXT_ELEMENTS = ("business_needs", "external")

_GAP_SOURCE_PREFIX = "6.2:"


def _declared_element(cap: dict) -> str:
    """The 6.2 element a capability declares it covers, or "" when it declares none.

    "" is a THIRD answer, not a negative one: it means the labels cannot be compared,
    not that the gap is unaddressed. The pre-feature convention was the bare
    "6.2:gap_analysis" — a source, not an element — and it must stay uncomparable
    rather than become a phantom element named `gap_analysis`.
    """
    if not isinstance(cap, dict):
        return ""
    src = cap.get("gap_source", "")
    if not isinstance(src, str):
        return ""
    src = src.strip()
    if not src.startswith(_GAP_SOURCE_PREFIX):
        return ""
    element = src[len(_GAP_SOURCE_PREFIX):].strip()
    if element.startswith("gap_analysis:"):
        element = element[len("gap_analysis:"):].strip()
    if not element or element == "gap_analysis":
        return ""
    return element


def _gap_coverage(strategy: dict) -> dict:
    """Reconciles the imported 6.2 gap mirror against the analyst's declarations.

    `checked` False means the platform has nothing to compare against, and every
    caller must then render "not checked" instead of a count: a number the platform
    cannot support is worse than an admission that it has none.
    """
    empty = {"checked": False, "analysed": [], "covered": [], "undeclared": [],
             "excluded": [], "excluded_by": {}, "claimed_absent": [],
             "context_elements": [], "unknown_caps": 0}
    if not isinstance(strategy, dict):
        return empty
    # `x or {}` rescues None and {} but NOT a non-empty string, which is truthy and has
    # no .get — the same degrade-don't-raise guard the mirror and the capability list
    # each already carry, applied to the two containers holding them.
    context = strategy.get("imported_context")
    mirror = context.get("gaps", []) if isinstance(context, dict) else []
    if not isinstance(mirror, list):
        mirror = []

    # Keyed by casefold, valued by the first spelling seen: comparison ignores case,
    # printing keeps whatever 6.2 actually wrote.
    analysed_all: dict = {}
    for gap in mirror:
        if not isinstance(gap, dict):
            continue
        element = gap.get("element")
        if isinstance(element, str) and element.strip():
            analysed_all.setdefault(element.strip().casefold(), element.strip())
    if not analysed_all:
        return empty

    scope_section = strategy.get("solution_scope")
    caps = scope_section.get("capabilities", []) if isinstance(scope_section, dict) else []
    if not isinstance(caps, list):
        caps = []

    # A capability that names a context element in `gap_source` is the analyst stating
    # that on THIS project the element is closed by a capability after all. That is a
    # judgement the platform has no standing to overrule, so an explicit declaration
    # pulls the element back into the count — in scope or out of it, the declaration is
    # what matters here.
    declared_keys = {e.casefold() for e in (_declared_element(c) for c in caps
                                            if isinstance(c, dict)) if e}
    context_keys = [k for k in analysed_all
                    if k in GAP_CONTEXT_ELEMENTS and k not in declared_keys]
    context_elements = [analysed_all[k] for k in context_keys]
    analysed_keys = {k: v for k, v in analysed_all.items() if k not in context_keys}
    analysed = list(analysed_keys.values())

    covered, excluded, claimed_absent = [], [], []
    # Which capability carries each deliberate exclusion. The document renders IN-SCOPE
    # capabilities only, so without this the block asserts "org_structure was left
    # unaddressed on purpose" while the capability holding that decision appears
    # nowhere on the page — a finding a sponsor cannot check against anything.
    excluded_by: dict = {}
    unknown_caps = 0
    for cap in caps:
        if not isinstance(cap, dict):
            continue
        element = _declared_element(cap)
        # `in_scope` defaults to True exactly as define_solution_scope defaults it.
        in_scope = bool(cap.get("in_scope", True))
        # IN-SCOPE only, for this line and for `claimed_absent` below. The delivered
        # document renders in-scope capabilities and nothing else, so an out-of-scope
        # one raises "Cannot be checked: 1 capability" over a page on which every
        # capability shown IS traced — the same evidence-free claim `excluded_by` was
        # added to fix. Counting rather than naming is the right half of that symmetry
        # here: each in-scope capability already carries its own "no 6.2 element stated"
        # sub-line in the document, so the count has its evidence on the page. The
        # exclusion line names names instead, because there the out-of-scope
        # capability's decision IS the claim being made.
        if not element:
            if in_scope:
                unknown_caps += 1
            continue
        key = element.casefold()
        if key not in analysed_keys:
            if in_scope and key not in {c.casefold() for c in claimed_absent}:
                claimed_absent.append(element)
            continue
        canonical = analysed_keys[key]
        if in_scope:
            if canonical not in covered:
                covered.append(canonical)
            continue
        if canonical not in excluded:
            excluded.append(canonical)
        name = cap.get("name")
        if isinstance(name, str) and name.strip():
            excluded_by.setdefault(canonical, []).append(name.strip())

    # One in-scope capability is enough: an element it covers is covered, whatever an
    # out-of-scope sibling also says about it.
    excluded = [e for e in excluded if e not in covered]
    excluded_by = {e: n for e, n in excluded_by.items() if e in excluded}
    undeclared = [e for e in analysed if e not in covered and e not in excluded]
    return {"checked": True, "analysed": analysed, "covered": covered,
            "undeclared": undeclared, "excluded": excluded,
            "excluded_by": excluded_by, "claimed_absent": claimed_absent,
            "context_elements": context_elements, "unknown_caps": unknown_caps}


def _gap_file_seen(strategy: dict, project_id: str) -> bool:
    """Is there a 6.2 gap analysis on disk for this strategy's import sources?

    Separates "there is no gap analysis" from "there is one and it was not imported".
    The second is one re-run away; telling the analyst the first sends them to build
    an artefact they already have.
    """
    scope_section = strategy.get("scope")
    sources = (scope_section.get("source_project_ids")
               if isinstance(scope_section, dict) else None) or []
    if not isinstance(sources, list):
        sources = []
    # EXACTLY the importer's own source set — `sources or [project_id]`, the fallback
    # scope_change_strategy applies — and not a superset of it. Scanning the current
    # project on top found files the import would never open once `source_project_ids`
    # named someone else, and the message it triggered ("re-run scope_change_strategy")
    # then advised a re-run that cannot pick the file up.
    for src in (sources or [project_id]):
        if isinstance(src, str) and src and os.path.exists(_gap_file_path(src)):
            return True
    return False


def _gap_coverage_lines(strategy: dict, project_id: str) -> list:
    """The coverage block — ONE renderer for the tool reply and the delivered document.

    Two renderers is how the previous feature ended up with a BA Plan and a CR record
    that stated different governance for the same project. There is one here.
    """
    cov = _gap_coverage(strategy)
    if not cov["checked"]:
        if _gap_file_seen(strategy, project_id):
            return ["**6.2 gap coverage:** a 6.2 gap analysis exists but was not "
                    "imported — re-run `scope_change_strategy` to pull it in."]
        return ["**6.2 gap coverage:** no 6.2 gap analysis imported "
                "— coverage was not checked."]

    # Element names are quoted here as they are on the capability sub-lines. Bare, they
    # read as prose — and one of them, `capabilities`, is also the heading of the very
    # section this block sits in, twenty lines further up the delivered document.
    def _els(names):
        return ", ".join(f"`{n}`" for n in names)

    lines = ["**6.2 gap coverage:**"]
    if cov["covered"]:
        # "Declared covered", not "Covered": this line and the "DECLARES coverage of"
        # line below are read off the SAME analyst declaration. Stating the positive as
        # platform fact while hedging the negative would let a sponsor read the first as
        # verified delivery and the second as a mere bookkeeping gap.
        lines.append(f"- Declared covered: {_els(cov['covered'])} "
                     f"({len(cov['covered'])} of {len(cov['analysed'])} analysed)")
    if cov["undeclared"]:
        # "DECLARES", not "covers": while any capability is uncheckable the three lists
        # are not a partition, and an uncheckable capability may well cover this very
        # element. The sentence states what the platform knows — the declarations.
        lines.append("- No in-scope capability DECLARES coverage of: "
                     + _els(cov["undeclared"]))
    if cov["context_elements"]:
        # Named, never hidden: 6.2 analysed them and the sponsor should see that the
        # platform knows it. They are simply not something a capability closes, so
        # they carry no accusation and sit outside the count above.
        lines.append("- Context elements, not closed by capabilities: "
                     + _els(cov["context_elements"]))
    if cov["excluded"]:
        parts = []
        for element in cov["excluded"]:
            by = cov.get("excluded_by", {}).get(element) or []
            parts.append(f"`{element}` ({', '.join(by)})" if by else f"`{element}`")
        lines.append("- Deliberately left unaddressed (out of scope): "
                     + ", ".join(parts))
    if cov["claimed_absent"]:
        lines.append("- Claimed but absent from the 6.2 analysis: "
                     + _els(cov["claimed_absent"]))
    if cov["unknown_caps"]:
        # Parenthesised, so the sentence needs no verb: "1 capability state" was the
        # live document's own grammar, with the noun singularised and the verb left
        # plural.
        noun = "capability" if cov["unknown_caps"] == 1 else "capabilities"
        lines.append(f"- Cannot be checked: {cov['unknown_caps']} {noun} "
                     f"(no 6.2 element stated in gap_source)")
    return lines


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def scope_change_strategy(
    project_id: str,
    change_type: Literal["transformation", "process_improvement", "technology_implementation", "regulatory_compliance", "other"],
    time_horizon_months: int,
    methodology: Literal["agile", "waterfall", "hybrid"],
    source_project_ids: str = "[]",
    ba_notes: str = "",
) -> str:
    """
    Step 1 of the 6.4 pipeline: initialize the change strategy.

    Locks in the change type, horizon, and methodology.
    Automatically imports context from 6.1 (business_needs), 6.2 (future_state_goals
    and gap_analysis) and 6.3 (risk_assessment). The gap analysis arrives as context
    only — record gap_severity per capability in define_solution_scope yourself, and
    name the element there as gap_source "6.2:<element>" so coverage can be checked.
    Adds do_nothing as OPT-000.
    Graceful degradation: missing artifacts are skipped with a warning.

    Args:
        project_id: Project identifier
        change_type: Change type (transformation/process_improvement/technology_implementation/regulatory_compliance/other)
        time_horizon_months: Target horizon in months
        methodology: Methodology (agile/waterfall/hybrid)
        source_project_ids: JSON list of project_id from 6.1/6.2/6.3 for auto-import, e.g. '["crm_upgrade"]'
        ba_notes: Additional context
    """
    try:
        source_ids = json.loads(source_project_ids) if source_project_ids.strip() else []
    except json.JSONDecodeError:
        return "❌ Error: source_project_ids must be a JSON array, e.g. '[\"crm\"]'"

    if time_horizon_months <= 0:
        return "❌ time_horizon_months must be > 0"

    scope = {
        "project_id": project_id,
        "change_type": change_type,
        "time_horizon_months": time_horizon_months,
        "methodology": methodology,
        "source_project_ids": source_ids,
        "ba_notes": ba_notes,
        "created": str(date.today()),
    }

    os.makedirs(os.path.dirname(_scope_path(project_id)), exist_ok=True)
    with open(_scope_path(project_id), "w", encoding="utf-8") as f:
        json.dump(scope, f, ensure_ascii=False, indent=2)

    strategy = _load_strategy(project_id)
    strategy["scope"] = scope

    # --- Auto-import context ---
    warnings = []
    imported_bn = []
    imported_bg = []
    imported_risks = []
    imported_gaps = []

    if not source_ids:
        source_ids = [project_id]

    for src_id in source_ids:
        # 6.1: business needs (6.1 stores them under the `needs` key, field `need_title`)
        needs_path = data_path(src_id, f"{_safe(src_id)}_{BUSINESS_NEEDS_FILENAME}")
        needs_data = _safe_load_json(needs_path)
        if needs_data:
            for bn in needs_data.get("needs", []):
                imported_bn.append({
                    "id": bn.get("id", ""),
                    "title": bn.get("need_title", bn.get("title", bn.get("description", "")))[:80],
                    "priority": bn.get("priority", ""),
                    "source_project": src_id,
                })
        else:
            warnings.append(f"⚠️ 6.1 business_needs not found for '{src_id}'")

        # 6.2: goals (6.2 stores goals in future_state_goals.json, field `goal_title`)
        goals_path = data_path(src_id, f"{_safe(src_id)}_{FUTURE_STATE_GOALS_FILENAME}")
        goals_data = _safe_load_json(goals_path)
        if goals_data:
            for bg in goals_data.get("goals", []):
                imported_bg.append({
                    "id": bg.get("id", ""),
                    "title": bg.get("goal_title", bg.get("title", bg.get("description", "")))[:80],
                    "source_project": src_id,
                })
        else:
            warnings.append(f"⚠️ 6.2 goals not found for '{src_id}'")

        # 6.3: risk_assessment
        risk_path = data_path(src_id, f"{_safe(src_id)}_{RISK_ASSESSMENT_FILENAME}")
        risk_data = _safe_load_json(risk_path)
        if risk_data:
            # `zone` appears on a risk only after 6.3's run_risk_matrix; the file
            # itself exists from the first add_risk. Defaulting a missing zone to
            # "medium" imported a score-20 risk as medium and dropped it from the
            # High count — a confident statement over degraded data. Derive the
            # zone from the stored score against the assessment's own tolerance
            # instead (the same fallback 7.6 applies to this producer).
            max_acc = (risk_data.get("risk_tolerance", {}) or {}).get(
                "max_acceptable_score", 15)

            def _zone_of(rk_record):
                zone = rk_record.get("zone")
                if zone:
                    return zone
                score = rk_record.get("risk_score", 0) or 0
                if score >= max_acc:
                    return "high"
                return "medium" if score >= 6 else "low"

            for rk in risk_data.get("risks", []):
                if rk.get("status") == "identified":
                    imported_risks.append({
                        "id": rk.get("risk_id", ""),
                        "description": rk.get("description", "")[:80],
                        "zone": _zone_of(rk),
                        "risk_score": rk.get("risk_score", 0),
                        "response_strategy": rk.get("response_strategy", ""),
                        "source_project": src_id,
                    })
        else:
            warnings.append(f"⚠️ 6.3 risk_assessment not found for '{src_id}'")

        # 6.2: gap analysis (BABOK's .2 Gap Analysis element of 6.4, produced in 6.2).
        # Imported as CONTEXT ONLY: it never writes gap_severity or in_scope. 6.2's unit
        # is an ELEMENT (one of eight fixed areas) where 6.4's is a CAPABILITY, and 6.2's
        # `complexity` measures change EFFORT where `gap_severity` measures gap SIZE.
        # A platform that mapped one onto the other would be classifying, not importing.
        gap_data = _safe_load_json(_gap_file_path(src_id))
        # `is None` is the only "no file" signal — but "no file" and "usable" are not
        # the only two shapes a file can hand back. Any valid JSON round-trips through
        # read_json_artifact (a bare `[]`, `0`, `""` or `false` is not corrupt, so
        # guard_artifact_errors never sees it), so `if gap_data is not None:` let a
        # non-dict top level reach `gap_data.get("gaps", ...)` and raise AttributeError
        # — an unhandled crash on step 1 of the pipeline where the previous `if
        # gap_data:` had at least degraded into the "not found" branch. Guard by TYPE:
        # a dict is the only shape this importer can read `gaps` out of. Everything
        # else that is not None — including `[]` and `0` — reaches the shared
        # "holds no usable elements" warning below, exactly like a dict whose `gaps`
        # was empty or absent: from the analyst's side both are the same fact, a file
        # that exists but gave nothing to import.
        gaps_before = len(imported_gaps)
        if gap_data is None:
            warnings.append(f"⚠️ 6.2 gap_analysis not found for '{src_id}'")
        elif isinstance(gap_data, dict):
            for gp in gap_data.get("gaps", []) if isinstance(gap_data.get("gaps"), list) else []:
                if not isinstance(gp, dict):
                    continue
                element = gp.get("element", "")
                if not isinstance(element, str) or not element.strip():
                    continue
                summary = gp.get("gap_summary", "")
                imported_gaps.append({
                    "element": element.strip(),
                    "element_label": gp.get("element_label", element.strip()),
                    "change_type": gp.get("change_type", ""),
                    "complexity": gp.get("complexity", ""),
                    "gap_summary": summary[:120] if isinstance(summary, str) else "",
                    "source_project": src_id,
                })

        if gap_data is not None and len(imported_gaps) == gaps_before:
            warnings.append(
                f"⚠️ 6.2 gap_analysis for '{src_id}' was read but holds no usable "
                f"elements — nothing imported from it")

    strategy["imported_context"] = {
        "business_needs": imported_bn,
        "business_goals": imported_bg,
        "risks": imported_risks,
        "gaps": imported_gaps,
    }

    # do_nothing is added automatically (ADR-080)
    existing_options = strategy["change_strategy"].get("options", [])
    if not any(o.get("option_id") == DO_NOTHING_OPTION_ID for o in existing_options):
        existing_options.insert(0, {
            "option_id": DO_NOTHING_OPTION_ID,
            "name": "Do Nothing (status quo)",
            "strategy_type": "do_nothing",
            "investment_level": "low",
            "timeline_months": 0,
            "linked_risks": [],
            "risk_impact": "exacerbates",
            "pros": ["No cost of change", "No operational rollout risk"],
            "cons": [
                "Business needs remain unmet",
                "Competitive gap keeps widening",
                "Current problems worsen over time",
            ],
            "weighted_score": None,
            "selected": False,
            "auto_added": True,
        })
    strategy["change_strategy"]["options"] = existing_options

    _save_strategy(strategy, project_id)

    # --- Output formatting ---
    lines = [
        f"✅ Change strategy initialized\n\n",
        f"  Project:     {project_id}\n",
        f"  Type:        {change_type}\n",
        f"  Horizon:     {time_horizon_months} months\n",
        f"  Methodology: {methodology}\n\n",
    ]

    if imported_bn or imported_bg or imported_risks or imported_gaps:
        lines.append("**Imported context:**\n")
        if imported_bn:
            lines.append(f"  📋 Business needs (6.1): {len(imported_bn)} — "
                         + ", ".join(bn["id"] for bn in imported_bn if bn["id"]) + "\n")
        if imported_bg:
            lines.append(f"  🎯 Business goals (6.2): {len(imported_bg)} — "
                         + ", ".join(bg["id"] for bg in imported_bg if bg["id"]) + "\n")
        if imported_risks:
            high_risks = [r for r in imported_risks if r.get("zone") == "high"]
            lines.append(f"  ⚠️  Risks (6.3):          {len(imported_risks)}"
                         + (f" ({len(high_risks)} High)" if high_risks else "") + "\n")
        if imported_gaps:
            # UNIQUE elements, deduplicated the way _gap_coverage deduplicates them
            # (by casefold, first spelling kept). Counting records made two source
            # projects that analysed the same elements print "4 elements — technology,
            # policies, technology, policies" while the coverage block one call later
            # said "(2 of 2 analysed)". The mirror still keeps every record and its
            # source_project; only this count collapses them.
            unique_elements: dict = {}
            for g in imported_gaps:
                unique_elements.setdefault(g["element"].casefold(), g["element"])
            lines.append(f"  🔍 Gap analysis (6.2): {len(unique_elements)} elements — "
                         + ", ".join(unique_elements.values()) + "\n")
            # Reconciles this count with the "(N of M analysed)" the coverage block
            # prints on the NEXT call (define_solution_scope): business_needs/external
            # are CONTEXT elements, excluded from that denominator by default (see
            # GAP_CONTEXT_ELEMENTS below), so "4 elements" here and "(1 of 2 analysed)"
            # there were two true numbers about the same import with no stated link
            # between them. Printed only when a context element is actually present.
            context_elements = _gap_coverage(strategy).get("context_elements", [])
            if context_elements:
                lines.append(
                    f"     — of which {len(context_elements)} "
                    + ("is" if len(context_elements) == 1 else "are")
                    + " context (not a capability target, excluded from coverage): "
                    + ", ".join(context_elements) + "\n")

    if warnings:
        lines.append("\n**Warnings (graceful degradation):**\n")
        for w in warnings:
            lines.append(f"  {w}\n")

    lines.append(
        f"\n  ℹ️ OPT-000 (do_nothing) added automatically as the baseline.\n\n"
        f"**Next step:** `define_solution_scope` — define the solution capabilities."
    )

    return "".join(lines)


@mcp.tool()
@guard_artifact_errors
def define_solution_scope(
    project_id: str,
    capabilities_json: str,
    explicitly_excluded: str = "[]",
    scope_summary: str = "",
) -> str:
    """
    Step 2 of the 6.4 pipeline: define the solution scope via capabilities.

    Each capability has a category (process/technology/data/people/org_structure/knowledge/location),
    a gap_severity (none/low/medium/high), and an in_scope flag.
    explicitly_excluded records what is deliberately out of scope — prevents scope creep.

    Args:
        project_id: Project identifier
        capabilities_json: JSON array of capabilities. Object format:
            {"name": "...", "category": "technology", "description": "...",
             "gap_severity": "high", "gap_source": "6.2:technology", "in_scope": true}
            gap_source names the 6.2 element this capability covers ("6.2:technology",
            "6.2:policies", ...) — that declaration is what lets the platform report
            which analysed gaps no capability addresses. "manual" or a bare
            "6.2:gap_analysis" names no element, and coverage is then reported as
            uncheckable rather than as uncovered.
        explicitly_excluded: JSON list of strings — what is explicitly NOT in scope
        scope_summary: 2-3 sentences: what we are doing and what we are not doing
    """
    # Shape, not just syntax: a list of strings (names) where objects are expected —
    # a plausible LLM mistake — must return a readable "❌", not an AttributeError
    # escaping the tool when the render loop calls cap.get(...).
    from skills.common import parse_json_dict_list
    capabilities, shape_error = parse_json_dict_list(capabilities_json, "capabilities_json")
    if shape_error:
        return shape_error

    try:
        excluded = json.loads(explicitly_excluded) if explicitly_excluded.strip() else []
    except json.JSONDecodeError:
        excluded = []

    # Validate capabilities
    valid_caps = []
    errors = []
    for i, cap in enumerate(capabilities):
        name = cap.get("name", "")
        category = cap.get("category", "")
        gap_severity = cap.get("gap_severity", "medium")
        if not name:
            errors.append(f"Capability #{i+1}: missing 'name' field")
            continue
        if category not in VALID_CAP_CATEGORIES:
            errors.append(f"Capability '{name}': invalid category '{category}'. Allowed: {', '.join(VALID_CAP_CATEGORIES)}")
            continue
        if gap_severity not in VALID_GAP_SEVERITIES:
            errors.append(f"Capability '{name}': invalid gap_severity '{gap_severity}'")
            continue
        # Only a gap_source that NAMES an element is checked. "manual" and the legacy
        # bare "6.2:gap_analysis" name none, stay accepted, and report as uncheckable.
        declared = _declared_element(cap)
        if declared and declared.casefold() not in _VALID_GAP_ELEMENT_KEYS:
            errors.append(
                f"Capability '{name}': invalid gap_source element '{declared}'. "
                f"gap_source names a 6.2 element as \"6.2:<element>\". "
                f"Allowed: {', '.join(VALID_GAP_ELEMENTS)}")
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
        return "❌ Errors in capabilities_json:\n" + "\n".join(f"  • {e}" for e in errors)

    strategy = _load_strategy(project_id)
    # Read BEFORE the replacement. The coverage block invites the analyst back to add
    # `gap_source`, and that second call carries capabilities_json and nothing else —
    # which silently dropped the exclusions and the summary, taking "Explicitly out of
    # scope" out of the delivered document. The tool still REPLACES wholesale (that is
    # its contract); it just no longer does it quietly.
    previous_scope = strategy.get("solution_scope") or {}
    prev_excluded = previous_scope.get("explicitly_excluded") or []
    prev_summary = previous_scope.get("scope_summary") or ""
    strategy["solution_scope"] = {
        "capabilities": valid_caps,
        "explicitly_excluded": excluded,
        "scope_summary": scope_summary,
    }
    _save_strategy(strategy, project_id)

    overwritten = []
    if prev_excluded and not excluded:
        noun = "exclusion" if len(prev_excluded) == 1 else "exclusions"
        verb = "was" if len(prev_excluded) == 1 else "were"
        overwritten.append(f"{len(prev_excluded)} explicit {noun} {verb} replaced "
                           f"by an empty list")
    if prev_summary and not scope_summary:
        overwritten.append("the scope summary was cleared")

    in_scope = [c for c in valid_caps if c.get("in_scope", True)]
    out_of_scope = [c for c in valid_caps if not c.get("in_scope", True)]

    # Stats by category
    cats = {}
    for c in in_scope:
        cats[c["category"]] = cats.get(c["category"], 0) + 1

    # Stats by gap_severity
    gaps = {"high": 0, "medium": 0, "low": 0, "none": 0}
    for c in in_scope:
        gaps[c["gap_severity"]] = gaps.get(c["gap_severity"], 0) + 1

    lines = [
        f"✅ Solution scope defined\n\n",
        f"  Capabilities in scope: {len(in_scope)}\n",
        f"  Explicit exclusions:   {len(excluded)}\n\n",
    ]

    if overwritten:
        # Directly under the "Explicit exclusions: 0" the analyst is about to misread.
        lines.append(
            "⚠️ This call REPLACED the previous solution scope: "
            + "; ".join(overwritten)
            + ". `define_solution_scope` replaces solution_scope wholesale — re-send "
              "`explicitly_excluded` and `scope_summary` to keep them.\n\n")

    if cats:
        lines.append("**Capabilities by category:**\n")
        for cat, cnt in sorted(cats.items()):
            lines.append(f"  {cat}: {cnt}\n")

    lines.append("\n**Distribution by gap_severity:**\n")
    if gaps["high"] > 0:
        lines.append(f"  🔴 high:   {gaps['high']} (critical gaps — will drive the phase structure)\n")
    if gaps["medium"] > 0:
        lines.append(f"  🟡 medium: {gaps['medium']}\n")
    if gaps["low"] > 0:
        lines.append(f"  🟢 low:    {gaps['low']}\n")
    if gaps["none"] > 0:
        lines.append(f"  ⚪ none:   {gaps['none']} (capability already exists)\n")

    # Computed AFTER _save_strategy, from the capabilities this call just stored —
    # the tool replaces solution_scope wholesale, so anything read earlier describes
    # the previous run.
    lines.append("\n" + "\n".join(_gap_coverage_lines(strategy, project_id)) + "\n")

    if excluded:
        lines.append("\n**Explicit exclusions from scope:**\n")
        for ex in excluded:
            lines.append(f"  • {ex}\n")

    if scope_summary:
        lines.append(f"\n**Scope summary:** {scope_summary}\n")

    lines.append(
        f"\n→ Next step: `assess_enterprise_readiness` — assess the organization's readiness."
    )

    return "".join(lines)


@mcp.tool()
@guard_artifact_errors
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
    Step 3 of the 6.4 pipeline: assess the organization's readiness for change.

    Rates 6 dimensions on a 1-5 scale. Computes the readiness_score (average) and a verdict:
    ready (>=4.0) / proceed_with_caution (2.5-3.9) / not_ready (<2.5).
    ADR-079: change_history added to the base 5 dimensions.

    Args:
        project_id: Project identifier
        leadership_commitment: Leadership commitment 1-5
        cultural_readiness: Cultural readiness 1-5
        resource_availability: Resource availability 1-5
        operational_readiness: Operational readiness 1-5
        technical_readiness: Technical readiness 1-5
        change_history: Organization's track record with change 1-5
        leadership_rationale: Rationale for the leadership rating
        cultural_rationale: Rationale for the culture rating
        resource_rationale: Rationale for the resource rating
        operational_rationale: Rationale for the operational rating
        technical_rationale: Rationale for the technical rating
        change_history_rationale: Rationale for the change_history rating
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
            errors.append(f"{dim} must be between 1 and 5, got: {val}")
    if errors:
        return "❌ Validation errors:\n" + "\n".join(f"  • {e}" for e in errors)

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
        "ready": "The organization is ready for change",
        "proceed_with_caution": "There are gaps — preparatory measures are needed",
        "not_ready": "A dedicated organizational readiness program is required",
    }

    weak_dims = [(dim, val) for dim, val in dimensions.items() if val <= 2]
    medium_dims = [(dim, val) for dim, val in dimensions.items() if val == 3]

    lines = [
        f"✅ Readiness assessment complete\n\n",
        f"  Readiness Score: {score:.1f} / 5.0\n",
        f"  Verdict: {verdict_emoji[verdict]} {verdict} — {verdict_text[verdict]}\n\n",
        f"**Profile by dimension:**\n",
    ]

    dim_labels = {
        "leadership_commitment": "Leadership commitment",
        "cultural_readiness": "Cultural readiness",
        "resource_availability": "Resource availability",
        "operational_readiness": "Operational readiness",
        "technical_readiness": "Technical readiness",
        "change_history": "Change history",
    }
    score_bar = {1: "▪▫▫▫▫", 2: "▪▪▫▫▫", 3: "▪▪▪▫▫", 4: "▪▪▪▪▫", 5: "▪▪▪▪▪"}

    for dim, val in dimensions.items():
        bar = score_bar.get(val, "?????")
        label = dim_labels.get(dim, dim)
        lines.append(f"  {bar} {val}/5  {label}\n")

    if weak_dims:
        lines.append("\n**⚠️ Critical gaps (score ≤ 2):**\n")
        for dim, val in weak_dims:
            rat = rationales.get(dim, "")
            lines.append(f"  • {dim_labels.get(dim, dim)}: {val}/5"
                         + (f" — {rat}" if rat else "") + "\n")
        if verdict != "not_ready":
            lines.append(
                "  → Consider a pilot_first or phased strategy\n"
                "     and add a preparatory Phase 0 to the transition states\n"
            )

    if verdict == "proceed_with_caution" and medium_dims:
        lines.append("\n**🟡 Dimensions needing attention (score = 3):**\n")
        for dim, val in medium_dims:
            lines.append(f"  • {dim_labels.get(dim, dim)}: {val}/5\n")

    lines.append(
        f"\n→ Next step: `add_strategy_option` — add strategy options (min 1 real one).\n"
        f"  OPT-000 (do_nothing) has already been added automatically."
    )

    return "".join(lines)


@mcp.tool()
@guard_artifact_errors
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
    Step 4 of the 6.4 pipeline: add a strategy option.

    do_nothing (OPT-000) is added automatically — no need to add it again.
    Minimum 1 real option. Optimally 2-3 real options + do_nothing.

    Args:
        project_id: Project identifier
        name: Option name (e.g. "Phased CRM replacement")
        strategy_type: Strategy type (big_bang/phased/pilot_first)
        investment_level: Investment level (high/medium/low)
        timeline_months: Implementation timeline in months
        pros: JSON list of advantages, e.g. '["Fast time-to-value", "Low risk"]'
        cons: JSON list of disadvantages, e.g. '["High cost", "Long timeline"]'
        linked_risks: JSON list of RK-xxx risks, e.g. '["RK-001", "RK-003"]'
        risk_impact: How the option affects linked_risks (mitigates/exacerbates/neutral)
    """
    try:
        pros_list = json.loads(pros) if pros.strip() else []
    except json.JSONDecodeError:
        return "❌ Error parsing pros. Must be a JSON array of strings."

    try:
        cons_list = json.loads(cons) if cons.strip() else []
    except json.JSONDecodeError:
        return "❌ Error parsing cons. Must be a JSON array of strings."

    try:
        risks_list = json.loads(linked_risks) if linked_risks.strip() else []
    except json.JSONDecodeError:
        risks_list = []

    if timeline_months <= 0:
        return "❌ timeline_months must be > 0"
    if not name.strip():
        return "❌ name cannot be empty"

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
    risks_hint = f"\n  Linked risks: {', '.join(risks_list)} ({risk_impact})" if risks_list else ""

    return (
        f"✅ Strategy option added: {option_id}\n\n"
        f"  Name:        {name}\n"
        f"  Type:        {strategy_type}\n"
        f"  Investment:  {investment_level}\n"
        f"  Timeline:    {timeline_months} mo.\n"
        f"  Pros:        {len(pros_list)}\n"
        f"  Cons:        {len(cons_list)}\n"
        f"{risks_hint}\n\n"
        f"  Real options in the register: {total_real}\n\n"
        f"→ Add another option (`add_strategy_option`) or move on to `compare_strategy_options`."
    )


@mcp.tool()
@guard_artifact_errors
def compare_strategy_options(
    project_id: str,
    scores_json: str,
    opportunity_cost: str,
    weights_json: str = "{}",
    custom_criteria_json: str = "{}",
) -> str:
    """
    Step 5 of the 6.4 pipeline: compare options via a weighted matrix.

    Computes the weighted_score for each option, determines the winner,
    and records the opportunity cost of the rejected options.

    Args:
        project_id: Project identifier
        scores_json: JSON matrix of 1-5 scores per criterion.
            Format: {"OPT-001": {"alignment_to_goals": 4, "risk_mitigation": 3, "cost": 3,
                                 "time_to_value": 4, "org_readiness_fit": 3, "feasibility": 4}}
            OPT-000 (do_nothing) should be included for a correct comparison.
            ⚠️ SCORING DIRECTION — 5 is ALWAYS the best outcome, on EVERY criterion.
            All weights are positive and the score is a weighted average, so a
            "bad is high" reading would silently invert the winner. For the criteria
            where that is counter-intuitive, score the OUTCOME, not the magnitude:
              • cost            — 5 = cheapest        (NOT "costs the most")
              • risk_mitigation — 5 = risk best handled (NOT "riskiest")
              • time_to_value   — 5 = fastest payback (NOT "takes longest")
        opportunity_cost: What we give up by choosing the winner over the rest (required text)
        weights_json: Optional — override the default criteria weights.
            The sum of all weights (including custom ones) must be 100.
            Format: {"alignment_to_goals": 30, "risk_mitigation": 25, ...}
        custom_criteria_json: Optional — add custom criteria with weights.
            Format: {"regulatory_compliance": {"weight": 15, "description": "..."}}
    """
    if not opportunity_cost.strip():
        return "❌ opportunity_cost is required. Describe what we give up by choosing the best option over the rest."

    try:
        scores = json.loads(scores_json)
    except json.JSONDecodeError:
        return "❌ Error parsing scores_json. Check the JSON syntax."

    try:
        weights_override = json.loads(weights_json) if weights_json.strip() else {}
    except json.JSONDecodeError:
        weights_override = {}

    try:
        custom_criteria = json.loads(custom_criteria_json) if custom_criteria_json.strip() else {}
    except json.JSONDecodeError:
        custom_criteria = {}

    # Final weights
    final_weights = dict(DEFAULT_CRITERIA_WEIGHTS)
    if weights_override:
        final_weights.update(weights_override)

    # Add custom criteria
    for crit_name, crit_data in custom_criteria.items():
        if isinstance(crit_data, dict):
            final_weights[crit_name] = crit_data.get("weight", 0)
        else:
            final_weights[crit_name] = int(crit_data)

    total_weight = sum(final_weights.values())
    if abs(total_weight - 100) > 1:
        return f"❌ The sum of weights must be 100, got: {total_weight}. Adjust weights_json."

    strategy = _load_strategy(project_id)
    options = strategy["change_strategy"].get("options", [])

    if not options:
        return "⚠️ No strategy options. Add one via `add_strategy_option`."

    # Compute weighted_score
    scored_options = []
    for opt in options:
        oid = opt["option_id"]
        opt_scores = scores.get(oid, {})
        if not opt_scores and oid != DO_NOTHING_OPTION_ID:
            continue

        if oid == DO_NOTHING_OPTION_ID and oid not in scores:
            # do_nothing without explicit scores — use minimal ones
            opt_scores = {crit: 1 for crit in final_weights}

        weighted = 0.0
        for crit, weight in final_weights.items():
            crit_score = opt_scores.get(crit, 0)
            weighted += crit_score * (weight / 100)

        opt["weighted_score"] = round(weighted, 2)
        opt["scores_detail"] = opt_scores
        scored_options.append(opt)

    if not scored_options:
        return "⚠️ No scored options. Check that the option_id values in scores_json match the options you added."

    # Determine the winner (highest score among non-do_nothing options)
    real_options = [o for o in scored_options if o.get("strategy_type") != "do_nothing"]
    if not real_options:
        return "⚠️ No real options (other than do_nothing). Add one via `add_strategy_option`."

    winner = max(real_options, key=lambda o: o.get("weighted_score", 0))
    winner_id = winner["option_id"]

    # Update selected
    for opt in options:
        opt["selected"] = (opt["option_id"] == winner_id)

    # Build rejected_alternatives
    rejected = []
    for opt in scored_options:
        if opt["option_id"] != winner_id:
            rejected.append({
                "option_id": opt["option_id"],
                "name": opt.get("name", ""),
                "weighted_score": opt.get("weighted_score"),
                "rationale": f"Lost to {winner_id} on weighted score: "
                             f"{opt.get('weighted_score', 0):.2f} vs {winner.get('weighted_score', 0):.2f}",
            })

    strategy["change_strategy"]["options"] = options
    strategy["change_strategy"]["selected_option_id"] = winner_id
    strategy["change_strategy"]["rejected_alternatives"] = rejected
    strategy["change_strategy"]["opportunity_cost"] = opportunity_cost
    strategy["change_strategy"]["criteria_weights_used"] = final_weights
    strategy["change_strategy"]["compared_on"] = str(date.today())

    _save_strategy(strategy, project_id)

    # --- Output formatting ---
    lines = [
        f"✅ Comparison of options complete\n\n",
        f"  **Winner: {winner_id} — {winner.get('name', '')}**\n",
        f"  Weighted Score: {winner.get('weighted_score', 0):.2f} / 5.00\n",
        f"  Strategy type: {winner.get('strategy_type', '')}\n",
        f"  Timeline: {winner.get('timeline_months', 0)} mo. | Investment: {winner.get('investment_level', '')}\n\n",
        f"**Comparison matrix:**\n",
    ]

    # Table
    header_opts = [o["option_id"] for o in scored_options]
    lines.append(f"  {'Criterion':<25} | " + " | ".join(f"{oid:>8}" for oid in header_opts) + " | Weight\n")
    lines.append(f"  {'-'*25}-+-" + "-+-".join(["-"*8]*len(header_opts)) + "-+-----\n")
    for crit, weight in final_weights.items():
        row = f"  {crit:<25} | "
        for opt in scored_options:
            val = opt.get("scores_detail", {}).get(crit, "-")
            row += f"{val:>8} | "
        row += f"{weight}%\n"
        lines.append(row)
    lines.append(f"  {'TOTAL (weighted)':<25} | ")
    for opt in scored_options:
        lines[-1] += f"{opt.get('weighted_score', 0):>8.2f} | "
    lines[-1] += "\n"

    lines.append(f"\n**Opportunity Cost:**\n  {opportunity_cost}\n")

    lines.append(
        f"\n→ Next step: `define_transition_states` — describe the transition phases."
    )

    return "".join(lines)


@mcp.tool()
@guard_artifact_errors
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
    Step 6 of the 6.4 pipeline: describe a transition state (phase).

    Call this for each phase. For big_bang — a single phase.
    For phased — 2-5 phases. Each phase should deliver standalone value.

    Args:
        project_id: Project identifier
        phase_number: Phase number (1, 2, 3...)
        phase_name: Phase name (e.g. "Pilot: basic CRM")
        duration_months: Phase duration in months
        capabilities_delivered: JSON list of capability names delivered in this phase
        gaps_closed: JSON list of gap names closed by the end of this phase
        risks_remaining: JSON list of RK-xxx risks that remain active after this phase
        value_realizable: Value realized by the end of the phase (for the sponsor)
    """
    try:
        caps = json.loads(capabilities_delivered) if capabilities_delivered.strip() else []
    except json.JSONDecodeError:
        return "❌ Error parsing capabilities_delivered. Must be a JSON array of strings."

    try:
        gaps = json.loads(gaps_closed) if gaps_closed.strip() else []
    except json.JSONDecodeError:
        gaps = []

    try:
        risks = json.loads(risks_remaining) if risks_remaining.strip() else []
    except json.JSONDecodeError:
        risks = []

    if phase_number <= 0:
        return "❌ phase_number must be > 0"
    if duration_months <= 0:
        return "❌ duration_months must be > 0"
    if not phase_name.strip():
        return "❌ phase_name cannot be empty"
    if not value_realizable.strip():
        return "⚠️ value_realizable is not filled in — every phase should deliver concrete value."

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

    # Replace if this phase was already defined
    states = [s for s in states if s.get("phase") != phase_number]
    states.append(transition_state)
    states.sort(key=lambda s: s.get("phase", 0))
    strategy["transition_states"] = states

    _save_strategy(strategy, project_id)

    total_caps = sum(len(s.get("capabilities_delivered", [])) for s in states)
    total_months = sum(s.get("duration_months", 0) for s in states)

    risks_note = ""
    if risks:
        risks_note = f"\n  Remaining risks: {', '.join(risks)}"

    return (
        f"✅ Phase {phase_number} recorded\n\n"
        f"  Name:          {phase_name}\n"
        f"  Duration:      {duration_months} mo.\n"
        f"  Capabilities:  {len(caps)}\n"
        f"  Gaps closed:   {len(gaps)}\n"
        f"{risks_note}\n"
        f"  Value:         {value_realizable[:80]}{'...' if len(value_realizable) > 80 else ''}\n\n"
        f"  Total phases defined: {len(states)} | "
        f"Total: {total_caps} capabilities, {total_months} mo.\n\n"
        f"→ Add the next phase or call `save_change_strategy` to finalize."
    )


@mcp.tool()
@guard_artifact_errors
def save_change_strategy(
    project_id: str,
    push_to_traceability: bool = False,
    traceability_project_id: str = "",
) -> str:
    """
    Step 7 of the 6.4 pipeline: finalize the change strategy.

    Saves {project}_change_strategy.json (a contract for 7.x, 8.x) and generates
    a Markdown report via save_artifact. Optionally registers the solution in
    the 5.1 repository as a 'solution_scope'-type node with 'satisfies' links.

    Args:
        project_id: Project identifier
        push_to_traceability: Register the solution in the 5.1 repository (default: False)
        traceability_project_id: project_id of the 5.1 repository (if different from the main one)
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
        return "⚠️ Solution scope is not defined. Call `define_solution_scope`."
    if not selected_id:
        return "⚠️ No strategy option selected. Call `compare_strategy_options`."
    if not readiness:
        return "⚠️ Readiness assessment is not filled in. Call `assess_enterprise_readiness`."
    if not states:
        return "⚠️ Transition states are not defined. Call `define_transition_states`."

    selected_option = next((o for o in options if o.get("option_id") == selected_id), None)
    if not selected_option:
        return f"⚠️ Selected option {selected_id} not found in the register."

    # --- Optional push to the 5.1 traceability repository (ADR-082) ---
    traceability_notes = []
    if push_to_traceability:
        repo_pid = traceability_project_id or project_id
        repo_path = _repo_path(project_id, repo_pid)
        if os.path.exists(repo_path):
            # The push reads the SHARED 5.1 graph before writing into it — a
            # corrupt repository must stop the push with a named file (via
            # guard_artifact_errors), not crash or write into a broken graph.
            repo = read_json_artifact(repo_path, "5.1 traceability repository")

            existing_ids = {r["id"] for r in repo.get("requirements", [])}
            # Existing satisfies edges — so a re-run (re-finalize) does not duplicate them.
            existing_satisfies = {
                (l.get("from"), l.get("to"))
                for l in repo.get("links", [])
                if l.get("relation") == "satisfies"
            }
            sol_id = "SOL-001"

            # solution node
            if sol_id not in existing_ids:
                repo.setdefault("requirements", []).append({
                    "id": sol_id,
                    "type": SOLUTION_SCOPE_NODE_TYPE,
                    "title": f"Solution Scope — {project_id}",
                    "version": "1.0",
                    # NOT `approved`: that literal is 5.5's approval OUTCOME, and 7.2
                    # counted this node as a requirement the stakeholders had signed
                    # off on a project where 5.5 had never run. `defined` says what
                    # 6.4 actually established — the scope is settled.
                    "status": "defined",
                    "added": str(date.today()),
                })
                existing_ids.add(sol_id)
                # chr(10): the two ✅ notes are joined by the caller without a
                # separator, so this note must end its own line.
                traceability_notes.append(
                    f"✅ Node {sol_id} ({SOLUTION_SCOPE_NODE_TYPE}) added to 5.1"
                    + chr(10))

            # satisfies links to business_goals
            added_links = 0
            missing_goals = []
            bg_list = strategy.get("imported_context", {}).get("business_goals", [])
            for bg in bg_list:
                bg_id = bg.get("id", "")
                if bg_id and bg_id not in existing_ids:
                    missing_goals.append(bg_id)
                    continue
                if bg_id and bg_id in existing_ids and (sol_id, bg_id) not in existing_satisfies:
                    repo.setdefault("links", []).append({
                        "from": sol_id,
                        "to": bg_id,
                        "relation": "satisfies",
                        "rationale": f"Solution scope fulfills {bg_id}",
                        "added": str(date.today()),
                    })
                    existing_satisfies.add((sol_id, bg_id))
                    added_links += 1

            if added_links:
                traceability_notes.append(f"✅ Added {added_links} satisfies links → BG")
            elif bg_list:
                # Previously this branch said NOTHING: the analyst explicitly asked for
                # a push, got a node and no links, and no explanation of either.
                traceability_notes.append(
                    "ℹ️ No new satisfies links — every objective was already linked."
                    if not missing_goals else ""
                )
            if missing_goals:
                shown = ", ".join(f"`{g}`" for g in missing_goals[:5])
                more = f" (+{len(missing_goals) - 5} more)" if len(missing_goals) > 5 else ""
                traceability_notes.append(
                    f"⚠️ {len(missing_goals)} objective(s) NOT linked — not a node in the "
                    f"5.1 repository: {shown}{more}.\n"
                    f"   Register them via 6.2 `define_goals_and_objectives`"
                    f" (register_in_traceability=True), then re-run this push."
                )
            traceability_notes = [n for n in traceability_notes if n]

            repo["updated"] = str(date.today())
            with open(repo_path, "w", encoding="utf-8") as f:
                json.dump(repo, f, ensure_ascii=False, indent=2)
        else:
            traceability_notes.append(
                f"⚠️ 5.1 traceability repository not found for '{repo_pid}' "
                f"— push skipped. Initialize the repository first."
            )

    # --- Markdown report ---
    verdict = readiness.get("verdict", "")
    readiness_score = readiness.get("readiness_score", 0)
    excluded = scope.get("explicitly_excluded", [])
    in_scope_caps = [c for c in capabilities if c.get("in_scope", True)]

    md_lines = [
        f"# Change Strategy — {project_id}",
        f"**Date:** {date.today()}  ",
        f"**Change type:** {strategy.get('scope', {}).get('change_type', '')}  ",
        f"**Horizon:** {strategy.get('scope', {}).get('time_horizon_months', '')} months  ",
        f"**Methodology:** {strategy.get('scope', {}).get('methodology', '')}",
        "",
        "---",
        "",
        "## Selected Strategy",
        "",
        f"**{selected_id} — {selected_option.get('name', '')}**",
        f"- Type: {selected_option.get('strategy_type', '')}",
        f"- Investment: {selected_option.get('investment_level', '')}",
        f"- Implementation timeline: {selected_option.get('timeline_months', '')} mo.",
        f"- Weighted Score: {selected_option.get('weighted_score', 'N/A')}",
        "",
    ]

    if selected_option.get("pros"):
        md_lines.append("**Pros:**")
        for p in selected_option["pros"]:
            md_lines.append(f"- {p}")
        md_lines.append("")

    if selected_option.get("cons"):
        md_lines.append("**Risks / drawbacks:**")
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
        md_lines.extend(["## Rejected Options", ""])
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
        "## Solution Scope",
        "",
        f"**Capabilities ({len(in_scope_caps)}):**",
        "",
    ])

    cats = {}
    for cap in in_scope_caps:
        # `or`, not a .get default: a key PRESENT with value null returns None, which
        # `sorted(cats.items())` then compares against a str and raises TypeError.
        cats.setdefault(cap.get("category") or "uncategorised", []).append(cap)

    # Keyed by casefold, exactly as _gap_coverage matches. Keyed by the raw string, a
    # capability declaring "6.2:Technology" was counted as covered by the block and
    # reported one screen above as an element "the imported gap analysis does not
    # contain" — two opposite verdicts on one page.
    gap_by_element = {}
    for gap in (strategy.get("imported_context") or {}).get("gaps", []) or []:
        if isinstance(gap, dict) and isinstance(gap.get("element"), str):
            gap_by_element.setdefault(gap["element"].strip().casefold(), gap)
    coverage_checked = _gap_coverage(strategy)["checked"]

    for cat, caps_list in sorted(cats.items()):
        md_lines.append(f"### {cat}")
        for cap in caps_list:
            # `cap.get(k) or default` throughout, never `cap[k]` and never
            # `cap.get(k, default)`. define_solution_scope always writes these keys, so
            # a capability missing one — or holding an explicit null — got here by a
            # hand edit of the strategy JSON. (Not, as this comment once claimed, from
            # a 7.5 surrogate: `set_change_strategy` in design_options_mcp writes
            # neither `solution_scope` nor `capabilities`, and such a file stops at the
            # earlier "⚠️ Solution scope is not defined" return.) A raise here loses the
            # delivered document at the last step of the chapter.
            severity = cap.get("gap_severity") or "not stated"
            gap_icon = {"high": "🔴", "medium": "🟡", "low": "🟢", "none": "⚪"}.get(severity, "")
            md_lines.append(
                f"- {cap.get('name') or ''} {gap_icon} gap:{severity} "
                f"| {cap.get('description') or ''}"
            )
            # The provenance sub-line exists only where there is provenance to state.
            # With nothing imported EVERY capability is formally uncheckable, and the
            # coverage block already says that once.
            if not coverage_checked:
                continue
            element = _declared_element(cap)
            if not element:
                md_lines.append("  ↳ no 6.2 element stated in gap_source "
                                "— coverage cannot be checked for this one")
            elif element.casefold() in gap_by_element:
                matched = gap_by_element[element.casefold()]
                effort = matched.get("complexity") or "not stated"
                # The 6.2 spelling, not the capability's: one name for one element
                # across the whole document, the same one the coverage block prints.
                shown = (matched.get("element") or element).strip()
                # The scale label rides on EVERY line, not in a header: `gap:` and
                # `effort:` share the low/medium/high letters and mean different
                # things — size of the gap versus effort of the change.
                md_lines.append(f"  ↳ from 6.2 gap `{shown}` — change effort there: "
                                f"{effort} (effort, not gap size)")
            else:
                md_lines.append(f"  ↳ declares 6.2 element `{element}`, which the "
                                f"imported gap analysis does not contain")
        md_lines.append("")

    md_lines.extend(_gap_coverage_lines(strategy, project_id) + [""])

    if excluded:
        md_lines.extend(["**Explicitly out of scope:**", ""])
        for ex in excluded:
            md_lines.append(f"- {ex}")
        md_lines.append("")

    md_lines.extend([
        "---",
        "",
        "## Enterprise Readiness",
        "",
        f"**Readiness Score: {readiness_score:.1f} / 5.0 — {verdict}**",
        "",
    ])

    dims = readiness.get("dimensions", {})
    dim_labels = {
        "leadership_commitment": "Leadership commitment",
        "cultural_readiness": "Cultural readiness",
        "resource_availability": "Resource availability",
        "operational_readiness": "Operational readiness",
        "technical_readiness": "Technical readiness",
        "change_history": "Change history",
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
            "## Transition States",
            "",
        ])
        for st in states:
            md_lines.extend([
                f"### Phase {st['phase']}: {st['name']} ({st.get('duration_months', 0)} mo.)",
                "",
            ])
            if st.get("capabilities_delivered"):
                md_lines.append("**Capabilities:**")
                for cap in st["capabilities_delivered"]:
                    md_lines.append(f"- {cap}")
            if st.get("gaps_closed"):
                md_lines.append("\n**Gaps closed:**")
                for g in st["gaps_closed"]:
                    md_lines.append(f"- {g}")
            if st.get("risks_remaining"):
                md_lines.append(f"\n**Remaining risks:** {', '.join(st['risks_remaining'])}")
            md_lines.extend([
                f"\n**Value:** {st.get('value_realizable', '')}",
                "",
            ])

    md_content = "\n".join(md_lines)
    artifact_result = save_artifact(md_content, f"6_4_change_strategy_{_safe(project_id)}", project_id=project_id)

    # Finalize the JSON
    strategy["status"] = "finalized"
    strategy["finalized_on"] = str(date.today())
    _save_strategy(strategy, project_id)

    json_path = _strategy_path(project_id)
    total_months = sum(s.get("duration_months", 0) for s in states)

    output = [
        f"✅ Change strategy finalized\n\n",
        f"  Project:    {project_id}\n",
        f"  Strategy:   {selected_id} — {selected_option.get('name', '')}\n",
        f"  Type:       {selected_option.get('strategy_type', '')}\n",
        f"  Phases:     {len(states)} | Total timeline: {total_months} mo.\n",
        f"  Readiness:  {readiness_score:.1f}/5.0 — {verdict}\n\n",
        f"  📄 JSON (for 7.x, 8.x): `{json_path}`\n",
        artifact_result, "\n",
    ]

    if traceability_notes:
        output.extend(["\n"] + traceability_notes + ["\n"])

    output.append(
        f"\n**Next steps:**\n"
        f"• 7.1 Specify Requirements → scope from `solution_scope.capabilities`\n"
        f"• 7.4 Define Requirements Architecture → phases from `transition_states`\n"
        f"• 7.5 Define Design Options → selected option + rejected alternatives\n"
    )

    if verdict != "ready":
        weak = [(d, v["score"]) for d, v in dims.items() if v["score"] <= 2]
        if weak:
            output.append(
                f"\n⚠️ Pay attention to the low readiness dimensions: "
                + ", ".join(f"{d}={s}" for d, s in weak)
                + " — prepare a mitigation plan before kickoff.\n"
            )

    return "".join(output)


if __name__ == "__main__":
    mcp.run()
