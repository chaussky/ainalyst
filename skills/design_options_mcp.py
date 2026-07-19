"""
BABOK 7.5 — Define Design Options
MCP tools for defining solution design options, allocating requirements across
versions, and comparing options.

Tools:
  - set_change_strategy      — surrogate for task 6.4 (ADR-039), temporary until Chapter 6 is implemented
  - create_design_option     — create/update a design option (build/buy/hybrid)
  - allocate_requirements    — semi-automatic allocation of req across versions (ADR-041)
  - compare_design_options   — comparison matrix of options against criteria
  - save_design_options_report — final report → 7.6 (Analyze Value and Recommend Solution)

ADR-039: set_change_strategy — surrogate for 6.4, will be replaced when Chapter 6 is implemented
ADR-040: single file {project}_design_options.json with an options[] array
ADR-041: allocation — semi-automatic, versions v1/v2/out_of_scope, depends-conflict check

Reads:  {project}_traceability_repo.json (5.1) — dependency graph and priorities
        {project}_prioritization.json (5.3) — priorities (optional)
        {project}_business_context.json (7.3) — business goals (optional)
        {project}_architecture.json (7.4) — viewpoints and gaps (optional)
        {project}_change_strategy.json (6.4 surrogate) — constraints (optional)
Writes: {project}_design_options.json
        {project}_change_strategy.json
        7_5_design_options_*.md (via save_artifact)
Output: Design Options Report → 7.6 (Analyze Value and Recommend Solution)

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date
from typing import Optional
from mcp.server.fastmcp import FastMCP
from skills.common import save_artifact, logger, DATA_DIR, data_path, normalize_project_id

mcp = FastMCP("BABOK_Design_Options")

REPO_FILENAME = "traceability_repo.json"
DESIGN_OPTIONS_FILENAME = "design_options.json"
CHANGE_STRATEGY_FILENAME = "change_strategy.json"
CONTEXT_FILENAME = "business_context.json"
ARCHITECTURE_FILENAME = "architecture.json"

# Valid values
VALID_APPROACHES = {"build", "buy", "hybrid"}
VALID_CHANGE_TYPES = {"technology", "process", "organizational", "hybrid"}
VALID_VERSIONS = {"v1", "v2", "out_of_scope"}
VALID_OPPORTUNITY_TYPES = {"efficiency", "information_access", "new_capability"}

# Mapping of MoSCoW/WSJF priorities to versions (ADR-041)
PRIORITY_TO_VERSION = {
    "Must": "v1",
    "High": "v1",
    "Should": "v1",   # Should → v1, but the BA can override to v2
    "Medium": "v2",
    "Could": "v2",
    "Low": "v2",
    "Won't": "out_of_scope",
}

# "Critical" priorities for req_coverage (audit finding 7.5-A). 7.1 sets High/Medium/Low; 5.3 sets
# MoSCoW. Both Must and High map to v1 in PRIORITY_TO_VERSION, so req_coverage must count both —
# otherwise a project that skipped 5.3 (repo priority = High) always shows req_coverage = N/A.
MUST_PRIORITIES = {"Must", "High"}

# Default comparison criteria
DEFAULT_CRITERIA = [
    {"id": "cost", "label": "Implementation cost", "weight": "high"},
    {"id": "speed", "label": "Launch speed (time-to-market)", "weight": "high"},
    {"id": "risk", "label": "Total risk", "weight": "medium"},
    {"id": "req_coverage", "label": "Must requirements coverage", "weight": "high"},
    {"id": "flexibility", "label": "Flexibility (changes after launch)", "weight": "medium"},
]


# ---------------------------------------------------------------------------
# Utilities — paths and file loading
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
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def _save_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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
    logger.info(f"Design options saved: {_design_options_path(project_id)}")


def _load_change_strategy(project_id: str) -> Optional[dict]:
    path = _change_strategy_path(project_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
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
    """Returns a list of (from, to) for links of type depends."""
    return [
        (link["from"], link["to"])
        for link in repo.get("links", [])
        if link.get("relation") == "depends"
    ]


# ---------------------------------------------------------------------------
# 7.5.1 — set_change_strategy (surrogate for 6.4, ADR-039)
# ---------------------------------------------------------------------------

@mcp.tool()
def set_change_strategy(
    project_id: str,
    change_type: str,
    scope: str,
    constraints: str,
    timeline: str,
    notes: str = "",
) -> str:
    """
    BABOK 7.5 / surrogate for 6.4 — Records the change strategy for the project.
    ADR-039: temporary tool until Chapter 6 of BABOK (Strategy Analysis) is implemented.
    ⚠️ Will be replaced by the full task 6.4 when Chapter 6 is implemented.

    The Change Strategy defines the strategic context for Design Options:
    what kind of change is happening, what is in scope, which constraints apply.

    Args:
        project_id:  Project identifier.
        change_type: Change type: technology | process | organizational | hybrid.
                     technology — replacing/introducing technology.
                     process — changing business processes.
                     organizational — restructuring, roles, responsibilities.
                     hybrid — several types at once.
        scope:       Change scope: what changes, what stays the same.
                     Example: "Replace the legacy CRM for the sales department. Financial accounting out of scope."
        constraints: Key constraints: budget, deadlines, technologies, regulations.
                     Example: "Budget $200k. Timeline — 12 months. Cloud solutions only."
        timeline:    Timeframe and phases.
                     Example: "Phase 1 (MVP): Q2 2025. Phase 2 (full): Q4 2025."
        notes:       Additional notes (optional).

    Returns:
        Confirmation with the saved change strategy.
    """
    logger.info(f"set_change_strategy: project_id='{project_id}', change_type='{change_type}'")

    if change_type not in VALID_CHANGE_TYPES:
        return (
            f"❌ Invalid change_type: '{change_type}'.\\n\\n"
            f"Valid values: {', '.join(sorted(VALID_CHANGE_TYPES))}"
        )

    if not scope.strip():
        return "❌ scope cannot be empty — describe what's in and out of the change scope."

    if not constraints.strip():
        return "❌ constraints cannot be empty — specify at least one key constraint."

    if not timeline.strip():
        return "❌ timeline cannot be empty — specify a timeline or phases."

    path = _change_strategy_path(project_id)
    is_update = os.path.exists(path)

    # Guard: do NOT clobber a real 6.4 Change Strategy contract with the flat 7.5 surrogate
    # (audit finding 7.5-B). 6.4 is the authoritative source for 7.x/8.x; 7.5 reads it directly.
    existing = _load_change_strategy(project_id)
    if _is_rich_strategy(existing):
        return (
            f"⚠️ `{project_id}_change_strategy.json` is already populated by task 6.4 "
            f"(the richer Change Strategy contract for 7.x/8.x). **Not overwriting.**\n\n"
            f"7.5 reads the 6.4 Change Strategy directly — no surrogate is needed. "
            f"To change the strategy, edit it via the 6.4 tools (`change_strategy` phase)."
        )

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
    with open(path, "w", encoding="utf-8") as f:
        json.dump(strategy, f, ensure_ascii=False, indent=2)

    # Update the reference in design_options if the file exists
    do_data = _load_design_options(project_id)
    do_data["change_strategy_ref"] = path
    _save_design_options(do_data)

    action = "updated" if is_update else "recorded"

    lines = [
        f"✅ Change Strategy **{action}** — project `{project_id}`",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Change type | `{change_type}` |",
        f"| Date | {date.today()} |",
        "",
        f"**Scope:** {scope}",
        "",
        f"**Constraints:** {constraints}",
        "",
        f"**Timeline:** {timeline}",
    ]

    if notes:
        lines += ["", f"**Notes:** {notes}"]

    lines += [
        "",
        "> ⚠️ **6.4 surrogate:** this tool is a temporary solution until Chapter 6",
        "> of BABOK (Strategy Analysis) is implemented. It will be replaced then.",
        "",
        "---",
        "",
        "**Next step:**",
        f"`create_design_option(project_id='{project_id}', option_id='OPT-001', ...)` — create the first design option.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.5.2 — create_design_option (ADR-040)
# ---------------------------------------------------------------------------

@mcp.tool()
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
    ADR-040: options accumulate in {project}_design_options.json.
    Idempotent by option_id: calling again updates the existing option.

    It's recommended to create 2–3 options for comparison:
    usually Build (custom development), Buy (off-the-shelf) and Hybrid (a mix).

    Args:
        project_id:      Project identifier.
        option_id:       Unique option ID: OPT-001, OPT-002, OPT-003.
        title:           Option title: "Build our own system", "Salesforce CRM".
        approach:        Approach: build | buy | hybrid.
                         build — build from scratch.
                         buy — off-the-shelf solution / SaaS.
                         hybrid — a mix of custom and off-the-shelf.
        components_json: JSON list of solution components.
                         Example: '["Backend API", "Web UI", "PostgreSQL", "Integration layer"]'
        improvement_opportunities_json: JSON list of business improvement opportunities.
                         Each item: {"type": "efficiency|information_access|new_capability", "description": "..."}
                         Example: '[{"type": "efficiency", "description": "Automated report generation"}]'
        effectiveness_measures_json: JSON list of solution effectiveness measures.
                         Example: '["Reduce request processing time from 2 h to 15 min", "NPS > 8"]'
        notes:           Additional notes on the option (optional).
        vendor_notes:    Vendor assessment — for buy/hybrid approaches (optional).
                         Include: vendor name, cost, constraints, references.

    Returns:
        Confirmation of the created/updated design option.
    """
    logger.info(f"create_design_option: project_id='{project_id}', option_id='{option_id}'")

    # Validation
    if not option_id.strip():
        return "❌ option_id cannot be empty. Use the format: OPT-001, OPT-002."

    if approach not in VALID_APPROACHES:
        return (
            f"❌ Invalid approach: '{approach}'.\\n\\n"
            f"Valid values: {', '.join(sorted(VALID_APPROACHES))}"
        )

    if not title.strip():
        return "❌ title cannot be empty — provide an option title."

    # Parse components
    try:
        components = json.loads(components_json)
        if not isinstance(components, list):
            raise ValueError("Expected a list")
        if not components:
            raise ValueError("The components list must not be empty")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Failed to parse components_json: {e}\\n\\n"
            f"Expected a non-empty JSON list: '[\"Backend API\", \"Web UI\"]'"
        )

    # Parse improvement_opportunities
    try:
        opportunities = json.loads(improvement_opportunities_json)
        if not isinstance(opportunities, list):
            raise ValueError("Expected a list")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Failed to parse improvement_opportunities_json: {e}\\n\\n"
            f"Expected a JSON list: '[{{\"type\": \"efficiency\", \"description\": \"...\"}}]'"
        )

    # Validate opportunity types
    invalid_types = [
        o.get("type", "") for o in opportunities
        if isinstance(o, dict) and o.get("type", "") not in VALID_OPPORTUNITY_TYPES
    ]
    if invalid_types:
        return (
            f"❌ Invalid improvement opportunity types: {invalid_types}\\n\\n"
            f"Valid types: {', '.join(sorted(VALID_OPPORTUNITY_TYPES))}"
        )

    # Parse effectiveness_measures
    try:
        measures = json.loads(effectiveness_measures_json)
        if not isinstance(measures, list):
            raise ValueError("Expected a list")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Failed to parse effectiveness_measures_json: {e}\\n\\n"
            f"Expected a JSON list: '[\"Reduce processing time by 40%\"]'"
        )

    # Warning: vendor_notes is recommended for buy/hybrid
    vendor_warning = ""
    if approach in ("buy", "hybrid") and not vendor_notes.strip():
        vendor_warning = (
            "\\n\\n> ℹ️ **Recommendation:** for approach `{approach}` it's recommended to fill in `vendor_notes` "
            "— specify the vendor, cost, constraints, references."
        ).format(approach=approach)

    # Load and update
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

    action = "updated" if is_update else "created"
    total_options = len(do_data["options"])

    lines = [
        f"✅ Design option **{action}**: `{option_id}`",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| ID | `{option_id}` |",
        f"| Title | {title} |",
        f"| Approach | `{approach}` |",
        f"| Components | {len(components)} |",
        f"| Improvement opportunities | {len(opportunities)} |",
        f"| Effectiveness measures | {len(measures)} |",
        f"| Total options in file | {total_options} |",
        "",
        "**Components:**",
    ]

    for c in components:
        lines.append(f"- {c}")

    if opportunities:
        lines += ["", "**Business improvement opportunities:**", ""]
        type_icons = {
            "efficiency": "⚡ Efficiency",
            "information_access": "📊 Information access",
            "new_capability": "🚀 New capability",
        }
        for opp in opportunities:
            t = opp.get("type", "")
            label = type_icons.get(t, t)
            lines.append(f"- **{label}:** {opp.get('description', '')}")

    if measures:
        lines += ["", "**Effectiveness measures:**"]
        for m in measures:
            lines.append(f"- {m}")

    if vendor_notes:
        lines += ["", f"**Vendor:** {vendor_notes}"]

    if vendor_warning:
        lines.append(vendor_warning)

    lines += [
        "",
        "---",
        "",
        "**Next steps:**",
    ]

    if total_options < 2:
        lines.append(
            f"`create_design_option(project_id='{project_id}', option_id='OPT-{total_options + 1:03d}', ...)` — create another option for comparison."
        )
    else:
        lines.append(
            f"`allocate_requirements(project_id='{project_id}', option_id='{option_id}', auto_suggest=True)` — allocate req across versions."
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.5.3 — allocate_requirements (ADR-041)
# ---------------------------------------------------------------------------

@mcp.tool()
def allocate_requirements(
    project_id: str,
    option_id: str,
    assignments_json: str = "[]",
    auto_suggest: bool = True,
) -> str:
    """
    BABOK 7.5 — Semi-automatic allocation of requirements across solution versions.
    ADR-041: reads priorities from the 5.1 repository, proposes an allocation,
    the BA confirms it or passes overrides via assignments_json.

    Versions: v1 (MVP) / v2 (next phase) / out_of_scope (out of the project).

    auto_suggest algorithm (simple version):
      Must/High → v1
      Should → v1 (the BA can override to v2)
      Could/Medium → v2
      Won't/Low → out_of_scope
      No priority → warning, the BA decides manually

    After confirmation — checks depends conflicts in the 5.1 graph:
    if req A (v1) depends on req B (v2) — a warning.

    Args:
        project_id:       Project identifier.
        option_id:        Design option ID (from create_design_option).
        assignments_json: JSON list of manual assignments (override auto_suggest).
                          Format: '[{"req_id": "FR-001", "version": "v1", "rationale": "..."}]'
                          Versions: v1 | v2 | out_of_scope.
                          Pass only the req you want to override.
        auto_suggest:     True — first propose an allocation by priority (recommended).
                          False — only record assignments_json without auto-suggestion.

    Returns:
        An allocation map with the proposal / result + warnings about depends conflicts.
    """
    logger.info(f"allocate_requirements: project_id='{project_id}', option_id='{option_id}'")

    # Check option_id
    do_data = _load_design_options(project_id)
    option = next((o for o in do_data["options"] if o["option_id"] == option_id), None)
    if option is None:
        return (
            f"❌ Design option `{option_id}` not found in project `{project_id}`.\\n\\n"
            f"Existing options: {[o['option_id'] for o in do_data['options']]}\\n"
            f"First call `create_design_option`."
        )

    # Parse assignments
    try:
        assignments_list = json.loads(assignments_json) if assignments_json.strip() else []
        if not isinstance(assignments_list, list):
            raise ValueError("Expected a list")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Failed to parse assignments_json: {e}\\n\\n"
            f"Expected a JSON list: '[{{\"req_id\": \"FR-001\", \"version\": \"v1\", \"rationale\": \"...\"}}]'\\n"
            f"Or pass an empty list '[]' to use auto_suggest only."
        )

    # Validate assignments
    invalid_versions = [
        a.get("version", "") for a in assignments_list
        if isinstance(a, dict) and a.get("version", "") not in VALID_VERSIONS
    ]
    if invalid_versions:
        return (
            f"❌ Invalid versions in assignments: {invalid_versions}\\n\\n"
            f"Valid versions: {', '.join(sorted(VALID_VERSIONS))}"
        )

    assignments_map = {
        a["req_id"]: {"version": a["version"], "rationale": a.get("rationale", "")}
        for a in assignments_list
        if isinstance(a, dict) and "req_id" in a and "version" in a
    }

    # Load the 5.1 repository
    repo = _load_repo(project_id)
    all_reqs = [
        r for r in repo.get("requirements", [])
        if r.get("type", "") not in {"business", "test", "change_request"}
    ]

    if not all_reqs:
        return (
            f"⚠️ The 5.1 repository for project `{project_id}` is empty or has no requirements.\\n\\n"
            f"Create requirements via the 7.1 tools before allocation."
        )

    lines = [
        f"<!-- BABOK 7.5 — Allocation | Project: {project_id} | Option: {option_id} | {date.today()} -->",
        "",
        f"# 📦 Requirements allocation — {option_id}: {option['title']}",
        "",
        f"**Project:** {project_id}  ",
        f"**Option:** {option_id} — {option['title']} (`{option['approach']}`)  ",
        f"**Date:** {date.today()}",
        "",
    ]

    # ------------------------------------------------------------------
    # auto_suggest: propose allocation by priority
    # ------------------------------------------------------------------

    no_priority_reqs = []
    suggested: dict = {}  # req_id → {"version": ..., "source": "auto"|"manual", "rationale": ""}

    if auto_suggest:
        for req in all_reqs:
            req_id = req["id"]
            priority = req.get("priority", "")

            # Manual override takes precedence
            if req_id in assignments_map:
                suggested[req_id] = {
                    "version": assignments_map[req_id]["version"],
                    "rationale": assignments_map[req_id]["rationale"],
                    "source": "manual",
                }
                continue

            # Auto suggestion by priority
            if priority and priority in PRIORITY_TO_VERSION:
                suggested[req_id] = {
                    "version": PRIORITY_TO_VERSION[priority],
                    "rationale": f"Auto: {priority} → {PRIORITY_TO_VERSION[priority]}",
                    "source": "auto",
                }
            else:
                no_priority_reqs.append(req)

    else:
        # Manual assignments only
        for req_id, data in assignments_map.items():
            suggested[req_id] = {
                "version": data["version"],
                "rationale": data["rationale"],
                "source": "manual",
            }

    # ------------------------------------------------------------------
    # Build the allocation map
    # ------------------------------------------------------------------

    allocation_map: dict = {}
    for req_id, data in suggested.items():
        allocation_map[req_id] = {
            "version": data["version"],
            "option_id": option_id,
            "rationale": data["rationale"],
            "source": data["source"],
        }

    # Per-version statistics
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
        "## Allocation summary",
        "",
        f"| Version | Req count |",
        f"|---------|-----------|",
        f"| v1 (MVP) | {len(version_counts['v1'])} |",
        f"| v2 (Phase 2) | {len(version_counts['v2'])} |",
        f"| out_of_scope | {len(version_counts['out_of_scope'])} |",
        f"| ⚠️ Without priority | {len(no_priority_reqs)} |",
        f"| **Total** | **{len(allocation_map) + len(no_priority_reqs)}** |",
        "",
        f"_Auto-allocated: {auto_count}, manual override: {manual_count}_",
        "",
    ]

    # Per-version tables
    for version_key, version_label in [("v1", "v1 — MVP"), ("v2", "v2 — Phase 2"), ("out_of_scope", "out_of_scope — out of project")]:
        ids_in_version = version_counts[version_key]
        if not ids_in_version:
            continue
        lines += [
            f"## 📌 {version_label} ({len(ids_in_version)} req)",
            "",
            "| ID | Type | Title | Priority | Source | Rationale |",
            "|----|------|-------|----------|--------|-----------|",
        ]
        for req_id in ids_in_version:
            req = next((r for r in all_reqs if r["id"] == req_id), None)
            if req:
                prio = req.get("priority", "—")
                title_short = req.get("title", "")[:50]
                req_type = req.get("type", "?")
                source = allocation_map[req_id]["source"]
                rationale = allocation_map[req_id]["rationale"][:60]
                source_icon = "✋ manual" if source == "manual" else "🤖 auto"
                lines.append(
                    f"| `{req_id}` | {req_type} | {title_short} | {prio} | {source_icon} | {rationale} |"
                )
        lines.append("")

    # Req without priority
    if no_priority_reqs:
        lines += [
            "## ⚠️ Requirements without priority",
            "",
            "> These req were not prioritized in task 5.3.",
            "> The BA must manually assign their version via `assignments_json`.",
            "",
            "| ID | Type | Title |",
            "|----|------|-------|",
        ]
        for req in no_priority_reqs:
            lines.append(f"| `{req['id']}` | {req.get('type', '?')} | {req.get('title', '')[:60]} |")
        lines.append("")

    # ------------------------------------------------------------------
    # Check depends conflicts
    # ------------------------------------------------------------------

    depends_links = _get_depends_links(repo)
    conflicts = []

    for from_id, to_id in depends_links:
        from_alloc = allocation_map.get(from_id)
        to_alloc = allocation_map.get(to_id)

        if from_alloc is None or to_alloc is None:
            continue  # req not in allocation — skip

        from_v = from_alloc["version"]
        to_v = to_alloc["version"]

        # Conflict: req A (v1) depends on req B (v2 or out_of_scope)
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
            "## ⚠️ Conflicts in depends dependencies",
            "",
            "> The following req have a conflict: req A (v1) depends on req B (v2/out_of_scope).",
            "> This means v1 cannot be implemented without B.",
            "> **Recommended:** move B to v1 or revisit the dependency in 5.1.",
            "",
            "| Req A (earlier) | Version | depends | Req B (dependency) | Version |",
            "|-----------------|---------|---------|--------------------|---------|",
        ]
        for c in conflicts:
            lines.append(
                f"| `{c['from_id']}` {c['from_title'][:30]} | `{c['from_version']}` | → | "
                f"`{c['to_id']}` {c['to_title'][:30]} | `{c['to_version']}` |"
            )
        lines += [
            "",
            f"_Total conflicts: {len(conflicts)}_",
            "",
        ]
    else:
        lines += [
            "## ✅ Dependency conflicts",
            "",
            "No depends-dependency violations between versions were found.",
            "",
        ]

    # ------------------------------------------------------------------
    # Save allocation to design_options.json
    # ------------------------------------------------------------------

    # Update only req from the current allocation (don't overwrite other options)
    for req_id, data in allocation_map.items():
        do_data["allocation"][req_id] = data

    _save_design_options(do_data)

    lines += [
        "---",
        "",
        f"Allocation for option `{option_id}` saved to `{_safe(project_id)}_design_options.json`.",
        "",
        "**Next steps:**",
    ]

    if no_priority_reqs:
        lines.append(
            f"1. Assign req without priority manually: pass `assignments_json` with a version choice."
        )

    if conflicts:
        lines.append(
            f"{'2' if no_priority_reqs else '1'}. Resolve {len(conflicts)} depends conflict(s): "
            "move dependencies into the same version or revisit the links in 5.1."
        )

    lines.append(
        f"{'3' if (no_priority_reqs and conflicts) else '2' if (no_priority_reqs or conflicts) else '1'}. "
        f"`compare_design_options(project_id='{project_id}')` — compare options after allocation."
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.5.4 — compare_design_options
# ---------------------------------------------------------------------------

@mcp.tool()
def compare_design_options(
    project_id: str,
    criteria_json: str = "[]",
) -> str:
    """
    BABOK 7.5 — Builds a comparison matrix of all design options against criteria.
    Reads all options from {project}_design_options.json.

    Default comparison criteria: cost, speed, risk, req coverage, flexibility.
    The BA can add custom criteria via criteria_json.

    Must requirements coverage is computed automatically from allocation data.

    Args:
        project_id:    Project identifier.
        criteria_json: JSON list of custom comparison criteria (added to the defaults).
                       Format: '[{"id": "vendor_support", "label": "Vendor support", "weight": "medium"}]'
                       The default criteria are always included.
                       Pass '[]' to use only the default criteria.

    Returns:
        A Comparison Document: comparison matrix for stakeholders.
    """
    logger.info(f"compare_design_options: project_id='{project_id}'")

    do_data = _load_design_options(project_id)
    options = do_data.get("options", [])

    if not options:
        return (
            f"⚠️ No design options for project `{project_id}`.\\n\\n"
            f"First create options via `create_design_option`."
        )

    if len(options) < 2:
        return (
            f"⚠️ At least 2 design options are needed for comparison.\\n\\n"
            f"Current options: {len(options)}. Create one more via `create_design_option`."
        )

    # Parse custom criteria
    try:
        custom_criteria = json.loads(criteria_json) if criteria_json.strip() else []
        if not isinstance(custom_criteria, list):
            raise ValueError("Expected a list")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Failed to parse criteria_json: {e}\\n\\n"
            f"Expected a JSON list: '[{{\"id\": \"vendor_support\", \"label\": \"Vendor support\", \"weight\": \"medium\"}}]'"
        )

    all_criteria = DEFAULT_CRITERIA + custom_criteria

    # Compute req_coverage automatically
    repo = _load_repo(project_id)
    all_reqs = [r for r in repo.get("requirements", []) if r.get("priority") in MUST_PRIORITIES]
    must_count = len(all_reqs)
    must_ids = {r["id"] for r in all_reqs}

    allocation = do_data.get("allocation", {})

    def _calc_coverage(option_id: str) -> str:
        """Computes the % of Must-req in v1 for an option."""
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
        f"<!-- BABOK 7.5 — Design Options Comparison | Project: {project_id} | {date.today()} -->",
        "",
        f"# 📊 Design options comparison — {project_id}",
        "",
        f"**Date:** {date.today()}  ",
        f"**Options:** {len(options)}  ",
        f"**Criteria:** {len(all_criteria)} ({len(DEFAULT_CRITERIA)} default + {len(custom_criteria)} custom)",
        "",
        "---",
        "",
    ]

    # Brief description of the options
    lines += [
        "## Design options",
        "",
        "| ID | Title | Approach | Components | Improvement opportunities |",
        "|----|-------|----------|------------|---------------------------|",
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

    # Comparison matrix
    weight_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}

    # Table header
    opt_headers = " | ".join(f"`{o['option_id']}`" for o in options)
    sep_cols = " | ".join(["---"] * len(options))

    lines += [
        "## Comparison matrix",
        "",
        "> ⚠️ **Req coverage** is computed automatically from allocation data.",
        "> The other criteria are the BA's qualitative assessment. Fill in the matrix for your project.",
        "",
        f"| Criterion | Weight | {opt_headers} |",
        f"|-----------|--------|{sep_cols}|",
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
                cells.append("_—_")  # the BA fills this in manually

        cells_str = " | ".join(cells)
        lines.append(f"| {crit_label} | {weight_icon} {weight} | {cells_str} |")

    lines += [
        "",
        "> **How to read:** 🔴 high — key criterion, 🟡 medium — important, 🟢 low — nice to have.",
        "",
        "---",
        "",
    ]

    # Details per option
    lines += [
        "## Option details",
        "",
    ]

    for opt in options:
        approach_icons = {"build": "🔨", "buy": "🛒", "hybrid": "🔀"}
        icon = approach_icons.get(opt.get("approach", ""), "📋")
        lines += [
            f"### {icon} {opt['option_id']} — {opt['title']}",
            "",
            f"**Approach:** `{opt.get('approach', '?')}`  ",
            f"**Created:** {opt.get('created', '—')}",
            "",
        ]

        components = opt.get("components", [])
        if components:
            lines.append("**Components:**")
            for c in components:
                lines.append(f"- {c}")
            lines.append("")

        opportunities = opt.get("improvement_opportunities", [])
        if opportunities:
            lines.append("**Business improvement opportunities:**")
            type_labels = {
                "efficiency": "⚡ Efficiency",
                "information_access": "📊 Information access",
                "new_capability": "🚀 New capability",
            }
            for opp in opportunities:
                t = opp.get("type", "")
                label = type_labels.get(t, t)
                lines.append(f"- **{label}:** {opp.get('description', '')}")
            lines.append("")

        measures = opt.get("effectiveness_measures", [])
        if measures:
            lines.append("**Effectiveness measures:**")
            for m in measures:
                lines.append(f"- {m}")
            lines.append("")

        if opt.get("vendor_notes"):
            lines += [f"**Vendor:** {opt['vendor_notes']}", ""]

        if opt.get("notes"):
            lines += [f"**Notes:** {opt['notes']}", ""]

        # Allocation summary for the option
        v1_ids = [rid for rid, d in allocation.items() if d.get("option_id") == opt["option_id"] and d.get("version") == "v1"]
        v2_ids = [rid for rid, d in allocation.items() if d.get("option_id") == opt["option_id"] and d.get("version") == "v2"]
        oos_ids = [rid for rid, d in allocation.items() if d.get("option_id") == opt["option_id"] and d.get("version") == "out_of_scope"]
        coverage_str = _calc_coverage(opt["option_id"])

        lines += [
            f"**Allocation:** v1: {len(v1_ids)} req | v2: {len(v2_ids)} req | out_of_scope: {len(oos_ids)} req  ",
            f"**Must coverage:** {coverage_str}",
            "",
        ]

    lines += [
        "---",
        "",
        "## Artifact handoff",
        "",
        "| Direction | Purpose |",
        "|-----------|---------|",
        "| → **4.4** Communicate | Presentation for stakeholders: fill in the matrix with assessments |",
        "| → **7.5** `save_design_options_report` | Final report with a recommendation |",
        "",
        "---",
        "",
        "**Next step:**",
        f"`save_design_options_report(project_id='{project_id}', recommended_option_id='OPT-XXX')` — save the final Design Options Report.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.5.5 — save_design_options_report
# ---------------------------------------------------------------------------

@mcp.tool()
def save_design_options_report(
    project_id: str,
    recommended_option_id: str = "",
    notes: str = "",
) -> str:
    """
    BABOK 7.5 — Generates the final Design Options Report.
    Saves it via save_artifact (prefix 7_5_design_options).
    Handed off to 7.6 (Analyze Value and Recommend Solution).

    Includes: all design options, allocation map, improvement opportunities,
    context (change_strategy, business_context, architecture),
    an optional preliminary BA recommendation.

    Args:
        project_id:              Project identifier.
        recommended_option_id:   Optional ID of the recommended option (e.g., 'OPT-002').
                                 This is the BA's preliminary conclusion — the final recommendation is in 7.6.
        notes:                   Additional notes for the report (optional).

    Returns:
        The Design Options Report in Markdown + a confirmation of saving via save_artifact.
    """
    logger.info(f"save_design_options_report: project_id='{project_id}'")

    do_data = _load_design_options(project_id)
    options = do_data.get("options", [])

    if not options:
        return (
            f"⚠️ No design options for project `{project_id}`.\\n\\n"
            f"Create options via `create_design_option` before generating the report."
        )

    # Validate recommended_option_id
    if recommended_option_id:
        option_ids = [o["option_id"] for o in options]
        if recommended_option_id not in option_ids:
            return (
                f"❌ Option `{recommended_option_id}` not found.\\n\\n"
                f"Existing options: {', '.join(option_ids)}"
            )

    # Load context
    strategy = _load_change_strategy(project_id)
    ctx = _load_context(project_id)
    arch = _load_architecture(project_id)
    repo = _load_repo(project_id)
    allocation = do_data.get("allocation", {})

    all_reqs = [r for r in repo.get("requirements", []) if r.get("type", "") not in {"business", "test", "change_request"}]
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
    # Generate the Design Options Report
    # ------------------------------------------------------------------

    doc_lines = [
        f"<!-- BABOK 7.5 — Design Options Report | Project: {project_id} | {date.today()} -->",
        "",
        f"# 🎨 Design Options Report",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Project | {project_id} |",
        f"| Date | {date.today()} |",
        f"| Design options | {len(options)} |",
        f"| Allocated req | {len(allocation)} |",
    ]

    if recommended_option_id:
        rec_opt = next((o for o in options if o["option_id"] == recommended_option_id), None)
        rec_title = rec_opt["title"] if rec_opt else recommended_option_id
        doc_lines.append(f"| ⭐ Preliminary recommendation | `{recommended_option_id}` — {rec_title} |")

    doc_lines += [""]

    if notes:
        doc_lines += [f"**Notes:** {notes}", ""]

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
            "> ℹ️ **Change Strategy is not set.** For a complete report it's recommended to call `set_change_strategy`.",
            "",
        ]

    # Business Context
    if ctx:
        goals = ctx.get("business_goals", [])
        future_state = ctx.get("future_state", "")
        doc_lines += [
            "## Business context (7.3)",
            "",
        ]
        if future_state:
            doc_lines += [f"**Future State:** {future_state}", ""]
        if goals:
            doc_lines += [
                "**Business goals:**",
                "",
                "| ID | Goal |",
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
            "## Architecture context (7.4)",
            "",
            f"| Viewpoints | Critical gaps | Warning gaps |",
            f"|------------|---------------|--------------|",
            f"| {len(arch.get('viewpoints', {}))} | {critical_count} | {warning_count} |",
            "",
        ]
        if critical_count > 0:
            doc_lines += [
                "> ⚠️ **There are critical architecture gaps.** It's recommended to resolve them before 7.6.",
                "",
            ]

    # Design options
    doc_lines += [
        "---",
        "",
        "## Design options",
        "",
    ]

    approach_icons = {"build": "🔨 Build", "buy": "🛒 Buy", "hybrid": "🔀 Hybrid"}

    for opt in options:
        opt_id = opt["option_id"]
        is_recommended = opt_id == recommended_option_id
        rec_marker = " ⭐ **RECOMMENDED**" if is_recommended else ""
        approach_label = approach_icons.get(opt.get("approach", ""), opt.get("approach", ""))

        v1_count = sum(1 for d in allocation.values() if d.get("option_id") == opt_id and d.get("version") == "v1")
        v2_count = sum(1 for d in allocation.values() if d.get("option_id") == opt_id and d.get("version") == "v2")
        oos_count = sum(1 for d in allocation.values() if d.get("option_id") == opt_id and d.get("version") == "out_of_scope")
        _, _, coverage_pct = _calc_coverage(opt_id)

        doc_lines += [
            f"### {opt_id} — {opt['title']}{rec_marker}",
            "",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| Approach | {approach_label} |",
            f"| Must-req coverage (v1) | {coverage_pct} |",
            f"| Allocation: v1 | {v1_count} req |",
            f"| Allocation: v2 | {v2_count} req |",
            f"| Allocation: out_of_scope | {oos_count} req |",
            "",
        ]

        components = opt.get("components", [])
        if components:
            doc_lines.append("**Solution components:**")
            for c in components:
                doc_lines.append(f"- {c}")
            doc_lines.append("")

        opportunities = opt.get("improvement_opportunities", [])
        if opportunities:
            type_labels = {
                "efficiency": "⚡ Efficiency",
                "information_access": "📊 Information access",
                "new_capability": "🚀 New capability",
            }
            doc_lines.append("**Business improvement opportunities:**")
            for opp in opportunities:
                t = opp.get("type", "")
                label = type_labels.get(t, t)
                doc_lines.append(f"- **{label}:** {opp.get('description', '')}")
            doc_lines.append("")

        measures = opt.get("effectiveness_measures", [])
        if measures:
            doc_lines.append("**Effectiveness measures:**")
            for m in measures:
                doc_lines.append(f"- {m}")
            doc_lines.append("")

        if opt.get("vendor_notes"):
            doc_lines += [f"**Vendor:** {opt['vendor_notes']}", ""]

        if opt.get("notes"):
            doc_lines += [f"**Notes:** {opt['notes']}", ""]

    # Allocation summary
    doc_lines += [
        "---",
        "",
        "## Allocation Map summary",
        "",
        "| ID | Type | Title | Priority | Version | Option | Rationale |",
        "|----|------|-------|----------|---------|--------|-----------|",
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

    # Recommendation
    if recommended_option_id:
        rec_opt = next((o for o in options if o["option_id"] == recommended_option_id), None)
        doc_lines += [
            "---",
            "",
            "## ⭐ BA preliminary recommendation",
            "",
            f"**Recommended option:** `{recommended_option_id}` — {rec_opt['title'] if rec_opt else ''}",
            "",
        ]
        if notes:
            doc_lines += [f"**Rationale:** {notes}", ""]

        doc_lines += [
            "> ⚠️ **This is the BA's preliminary conclusion.** The final recommendation and value assessment —",
            "> in task 7.6 (Analyze Value and Recommend Solution).",
            "",
        ]

    doc_lines += [
        "---",
        "",
        "## Artifact handoff",
        "",
        "| Direction | Purpose |",
        "|-----------|---------|",
        "| → **7.6** Analyze Value | Assess the value of each option and give a final recommendation |",
        "| → **4.4** Communicate | Communicate the options to stakeholders |",
    ]

    content = "\n".join(doc_lines)

    # Save via save_artifact
    save_artifact(content, prefix="7_5_design_options", project_id=project_id)

    # Response to the user
    result_lines = [
        f"✅ Design Options Report saved — **{project_id}**",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Design options | {len(options)} |",
        f"| Allocated req | {len(allocation)} |",
        f"| Date | {date.today()} |",
    ]

    if recommended_option_id:
        rec_opt = next((o for o in options if o["option_id"] == recommended_option_id), None)
        result_lines.append(
            f"| ⭐ Recommendation | `{recommended_option_id}` — {rec_opt['title'] if rec_opt else ''} |"
        )

    result_lines += [
        "",
        "Design Options Report saved via `save_artifact` (prefix: `7_5_design_options`).",
        "",
    ]

    # Warnings
    if not strategy:
        result_lines += [
            "> ⚠️ **Change Strategy is not set.** For completeness `set_change_strategy` is recommended.",
            "",
        ]

    unallocated = [r["id"] for r in all_reqs if r["id"] not in allocation]
    if unallocated:
        result_lines += [
            f"> ⚠️ **{len(unallocated)} req are not allocated to versions.** "
            f"Run `allocate_requirements` to complete the allocation.",
            "",
        ]

    result_lines += [
        "---",
        "",
        "**Next steps:**",
        "- → **7.6** `analyze_value_and_recommend` — assess the value of options and give a final recommendation",
        "- → **4.4** `prepare_communication_package` — prepare a communication package for stakeholders",
    ]

    return "\n".join(result_lines)


if __name__ == "__main__":
    mcp.run()
