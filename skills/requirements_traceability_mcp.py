"""
BABOK 5.1 — Trace Requirements
MCP tools for managing requirements traceability.

Tools:
  - init_traceability_repo    — create/reinitialize the traceability repository
  - add_trace_link            — add or remove a link between artifacts
  - run_impact_analysis       — impact analysis: what a requirement change will affect
  - check_coverage            — coverage audit: orphan requirements, implementation gaps
  - export_traceability_matrix — generate a Markdown matrix from the repository

Storage: JSON repository (edge-list graph) + Markdown on request.

Integration:
  In:  4.3 artifacts (save_confirmed_elicitation_result),
       4.2 artifacts for CRs (save_cr_elicitation_analysis)
  Out: run_impact_analysis → used in 5.4
       export_traceability_matrix → used in 5.5
       check_coverage → used in 5.3, 5.5

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date, datetime
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import (save_artifact, logger, DATA_DIR, data_path,
                           normalize_project_id, ANALYSIS_NODE_TYPES,
                           BUSINESS_NODE_TYPES, has_been_approved,
    has_passed_verification, has_been_validated,
    read_json_artifact, guard_artifact_errors, parse_json_dict_list,
    link_date,
)

mcp = FastMCP("BABOK_Requirements_Traceability")

REPO_FILENAME = "traceability_repo.json"

# Requirement types whose behaviour a test case can verify — the "no test" coverage
# axis applies to these and only these. The two BABOK classes are the original rule;
# the four 7.1 types joined by product decision (2026-07-22). Model artifacts
# (erd, data_dictionary, business_process, business_rule) are deliberately absent:
# they are reviewed, not executed against a test.
BEHAVIORAL_REQ_TYPES = {
    "solution", "transition",
    "functional", "non_functional", "user_story", "use_case",
}


# ---------------------------------------------------------------------------
# Repository utilities
# ---------------------------------------------------------------------------

def _repo_path(project_name: str) -> str:
    """Returns the path to the project's JSON repository file."""
    safe_name = normalize_project_id(project_name)
    return data_path(project_name, f"{safe_name}_{REPO_FILENAME}")


def _load_repo(project_name: str) -> dict:
    """Loads the repository from JSON. Returns an empty structure if it doesn't exist."""
    path = _repo_path(project_name)
    if os.path.exists(path):
        # Raises CorruptArtifactError, converted to a ❌ line by guard_artifact_errors
        # at the tool boundary. A bare json.load here made a damaged file a protocol
        # error in every downstream tool.
        return read_json_artifact(path, "5.1 traceability repository")
    return {
        "project": project_name,
        "formality_level": "Standard",
        "created": str(date.today()),
        "updated": str(date.today()),
        "requirements": [],
        "links": [],
        "history": []
    }


def _save_repo(repo: dict) -> str:
    """Saves the repository to JSON. Returns the path."""
    project_name = repo["project"]
    path = _repo_path(project_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    repo["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)
    logger.info(f"Traceability repository updated: {path}")
    return path


def _find_req(repo: dict, req_id: str) -> Optional[dict]:
    """Finds a requirement by ID."""
    for r in repo["requirements"]:
        if r["id"] == req_id:
            return r
    return None


def _find_links(repo: dict, req_id: str) -> list:
    """Returns all links where req_id appears as from or to."""
    return [lnk for lnk in repo["links"]
            if lnk["from"] == req_id or lnk["to"] == req_id]


# ---------------------------------------------------------------------------
# 5.1.1 — Initialize the traceability repository
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def init_traceability_repo(
    project_name: str,
    formality_level: Literal["Lite", "Standard", "Full"],
    requirements_json: str,
) -> str:
    """
    BABOK 5.1 — Creates or reinitializes the requirements traceability repository.
    Called once at project start, or when the first batch of requirements is added.

    Args:
        project_name:        Project name (must match across all 5.x tools).
        formality_level:     Formality level:
                             - Lite     — derives chain only. Agile, small projects.
                             - Standard — derives + verifies. Most projects.
                             - Full     — all 4 link types + rationale required. Regulated domains.
        requirements_json:   Initial list of requirements. Format:
                             [
                               {
                                 "id": "BR-001",
                                 "type": "business",
                                 "title": "Reduce application processing time to 5 minutes",
                                 "version": "1.0",
                                 "status": "confirmed",
                                 "source_artifact": "governance_plans/4_3_..._confirmed.md"
                               }
                             ]
                             Allowed type: business | stakeholder | solution | transition | test | component
                             Allowed status: draft | confirmed | approved | deprecated

    Returns:
        Repository-creation report + requirements statistics.
    """
    logger.info(f"init_traceability_repo: {project_name}, level: {formality_level}")

    # Shape, not just syntax. The elements are used as objects a few lines down, so a
    # list of bare ids — the most likely mistake, since neighbouring parameters
    # legitimately take strings — used to raise AttributeError out of the tool.
    requirements, shape_error = parse_json_dict_list(
        requirements_json, "requirements_json", required=True,
        example='[{"id": "FR-001", "type": "functional", "title": "..."}]')
    if shape_error:
        return shape_error

    # Load the existing repository (if any) — don't wipe out links
    repo = _load_repo(project_name)
    repo["formality_level"] = formality_level

    # Add requirements (deduplicated by id)
    existing_ids = {r["id"] for r in repo["requirements"]}
    added = []
    updated = []

    for req in requirements:
        req_id = req.get("id", "")
        if not req_id:
            continue
        # What the CALLER actually stated, before defaults are filled in. A default is
        # an assumption, and an assumption must never overwrite a value another chapter
        # established — the same rule the 3.2 registry seeding follows.
        stated = {k: v for k, v in req.items() if v not in (None, "")}

        req.setdefault("version", "1.0")
        req.setdefault("status", "draft")
        req.setdefault("source_artifact", "")
        req["added"] = str(date.today())

        if req_id in existing_ids:
            # MERGE into the existing entry, never replace it.
            #
            # Wholesale replacement destroyed every field the caller did not restate —
            # above all `type`, which 6.1 and 6.2 set when they register their nodes and
            # which every other chapter's traversal and skip-filter depends on. An
            # analyst re-running this tool with BN-001 in the list turned a
            # `business_need/confirmed` node into `type: None, status: draft`, after
            # which it silently dropped out of the coverage roots, the 7.1 objective
            # source and the 7.3/7.4 filters. Explicit values still win; omitted ones
            # are inherited.
            for i, r in enumerate(repo["requirements"]):
                if r["id"] == req_id:
                    merged = dict(r)
                    merged.update(stated)
                    merged["added"] = r.get("added", req["added"])
                    repo["requirements"][i] = merged
                    updated.append(req_id)
                    break
        else:
            repo["requirements"].append(req)
            added.append(req_id)
            existing_ids.add(req_id)

    repo_path = _save_repo(repo)

    # Stats by type
    type_counts: dict = {}
    for r in repo["requirements"]:
        t = r.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    # Build the report
    lines = [
        f"<!-- BABOK 5.1 — Requirements Traceability | Project: {project_name} | {date.today()} -->",
        "",
        f"# 📐 Traceability repository initialized",
        "",
        f"**Project:** {project_name}  ",
        f"**Formality level:** {formality_level}  ",
        f"**Repository file:** `{repo_path}`  ",
        f"**Date:** {date.today()}",
        "",
        "## Requirements statistics",
        "",
        f"- **Total:** {len(repo['requirements'])}",
        f"- **Added now:** {len(added)}",
        f"- **Updated:** {len(updated)}",
        f"- **Links in repository:** {len(repo['links'])}",
        "",
        "### By type:",
    ]

    type_labels = {
        "business": "Business requirements (BR)",
        "stakeholder": "Stakeholder requirements (SR)",
        "solution": "Solution requirements (FR/NFR)",
        "transition": "Transition requirements (TR)",
        "test": "Tests (TC)",
        "component": "Components (COMP)",
        "solution_scope": "Solution scope (6.4)",
    }
    for t, count in type_counts.items():
        label = type_labels.get(t, t)
        lines.append(f"- {label}: **{count}**")

    lines += [
        "",
        "## Formality level — what gets traced",
        "",
    ]

    if formality_level == "Lite":
        lines += [
            "| Link type | Status |",
            "|-----------|--------|",
            "| `derives` (vertical hierarchy) | ✅ Required |",
            "| `depends` (horizontal dependencies) | — Not required |",
            "| `satisfies` (component implements) | — Not required |",
            "| `verifies` (test verifies) | — Not required |",
            "",
            "> **Lite** suits Agile projects and small teams.",
        ]
    elif formality_level == "Standard":
        lines += [
            "| Link type | Status |",
            "|-----------|--------|",
            "| `derives` (vertical hierarchy) | ✅ Required |",
            "| `depends` (horizontal dependencies) | 🟡 Optional |",
            "| `satisfies` (component implements) | 🟡 Optional |",
            "| `verifies` (test verifies) | ✅ Required |",
            "",
            "> **Standard** — the optimal balance for most projects.",
        ]
    else:  # Full
        lines += [
            "| Link type | Status |",
            "|-----------|--------|",
            "| `derives` (vertical hierarchy) | ✅ Required |",
            "| `depends` (horizontal dependencies) | ✅ Required |",
            "| `satisfies` (component implements) | ✅ Required |",
            "| `verifies` (test verifies) | ✅ Required |",
            "",
            "> **Full** — all links + `rationale` required. Regulated domains, compliance.",
        ]

    if added:
        lines += ["", "## Requirements added", ""]
        for req in repo["requirements"]:
            if req["id"] in added:
                lines.append(f"- `{req['id']}` v{req.get('version','1.0')} [{req.get('status','draft')}] — {req.get('title','')}")

    lines += [
        "",
        "---",
        "**Next step:** add links between requirements via `add_trace_link`",
        f"or run a coverage audit via `check_coverage`.",
    ]

    content = "\n".join(lines)
    save_artifact(content, prefix="5_1_traceability_init", project_id=project_name)
    return content + f"\n\n✅ Repository saved: `{repo_path}`"


# ---------------------------------------------------------------------------
# 5.1.2 — Add / remove a link between artifacts
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def add_trace_link(
    project_name: str,
    from_id: str,
    to_id: str,
    # `threatens` (6.3) and `modifies` (5.4) are here so a wrong edge written by those
    # chapters can be REMOVED through the tool. Without them the only way to delete one
    # was hand-editing the repository JSON — which is exactly what this tool exists to
    # prevent the analyst from doing.
    relation: Literal["derives", "depends", "satisfies", "verifies",
                      "threatens", "modifies"],
    rationale: str,
    remove: bool = False,
) -> str:
    """
    BABOK 5.1 — Adds or removes a link between two artifacts in the repository.

    Link semantics:
      - derives:   from derives from to (top-down hierarchy: BR → SR → FR)
      - depends:   from doesn't make sense without to (horizontal dependency)
      - satisfies: from (component) implements to (requirement) — direction: COMP satisfies FR
      - verifies:  from (test) verifies to (requirement) — direction: TC verifies FR

    Args:
        project_name:  Project name.
        from_id:       Source artifact ID (BR-001, FR-007, TC-042, COMP-Auth).
        to_id:         Target artifact ID.
        relation:      Relation type: derives | depends | satisfies | verifies
        rationale:     Link rationale. Required in detail for Full.
                       Can be brief or an empty string for Lite/Standard.
        remove:        If True — remove the existing link instead of adding it.

    Returns:
        Operation confirmation + the artifact's current link state.
    """
    logger.info(f"add_trace_link: {from_id} --[{relation}]--> {to_id}, remove={remove}")

    repo = _load_repo(project_name)

    if remove:
        # Remove the link
        before = len(repo["links"])
        repo["links"] = [
            lnk for lnk in repo["links"]
            if not (lnk["from"] == from_id and lnk["to"] == to_id and lnk["relation"] == relation)
        ]
        after = len(repo["links"])
        if before == after:
            return f"⚠️ Link `{from_id} --[{relation}]--> {to_id}` not found in the repository."
        # Record in history
        repo["history"].append({
            "action": "link_removed",
            "from": from_id,
            "to": to_id,
            "relation": relation,
            "date": str(date.today()),
        })
        _save_repo(repo)
        return f"✅ Link `{from_id} --[{relation}]--> {to_id}` removed from the repository."

    # Check for a duplicate
    for lnk in repo["links"]:
        if lnk["from"] == from_id and lnk["to"] == to_id and lnk["relation"] == relation:
            return f"ℹ️ Link `{from_id} --[{relation}]--> {to_id}` already exists."

    # Warn about ends that are not repository nodes — but still write the edge.
    # External artifact ids (COMP-Auth, a Jira ticket) are legitimate targets, so a
    # hard check would break real usage; accepting a typo SILENTLY, however, creates
    # an edge to nowhere that check_coverage counts as a source — silencing exactly
    # the orphan check meant to catch it. Product decision (2026-07-22): warn + write.
    missing_ends = [
        node_id for node_id in (from_id, to_id) if _find_req(repo, node_id) is None
    ]
    dangling_note = ""
    if missing_ends:
        listed = ", ".join(f"`{node_id}`" for node_id in missing_ends)
        dangling_note = (
            f"\n⚠️ {listed}: not in the repository. If this is an external artifact "
            f"(component, ticket), that is fine; if it is a typo, remove the link "
            f"with `remove=True` — coverage checks will treat this edge as a real "
            f"justification.\n"
        )

    # Add the link
    new_link = {
        "from": from_id,
        "to": to_id,
        "relation": relation,
        "rationale": rationale,
        "added": str(date.today()),
    }
    repo["links"].append(new_link)

    # Record in history
    repo["history"].append({
        "action": "link_added",
        "from": from_id,
        "to": to_id,
        "relation": relation,
        "date": str(date.today()),
    })

    _save_repo(repo)

    # Show all current links for both nodes
    from_links = _find_links(repo, from_id)
    to_links = _find_links(repo, to_id)

    rel_icons = {
        "derives": "⬇️",
        "depends": "↔️",
        "satisfies": "✔️",
        "verifies": "🧪",
    }

    lines = [
        f"✅ Link added: `{from_id}` --[**{relation}**]--> `{to_id}`",
        dangling_note,
        f"**Rationale:** {rationale or '—'}",
        "",
        f"### Current links for `{from_id}`:",
    ]
    if from_links:
        for lnk in from_links:
            icon = rel_icons.get(lnk["relation"], "→")
            direction = f"`{lnk['from']}` {icon}[{lnk['relation']}]→ `{lnk['to']}`"
            lines.append(f"- {direction}")
    else:
        lines.append("- (no links)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 5.1.3 — Change impact analysis
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def run_impact_analysis(
    project_name: str,
    changed_req_id: str,
    change_description: str,
    depth: Literal["direct", "full"] = "full",
) -> str:
    """
    BABOK 5.1 — Impact analysis: traverses the link graph and returns all affected artifacts.

    This is a technical operation — a graph traversal. The expert "take it / don't take it"
    judgment and prioritizing the consequences is task 5.4.

    Args:
        project_name:        Project name.
        changed_req_id:      ID of the requirement being changed / removed.
        change_description:  Brief description of the change (for the report).
        depth:               - direct: direct links only (1 level)
                             - full:   full traversal in both directions (recommended)

    Returns:
        Report: what's affected, link types, recommended actions for 5.4.
    """
    logger.info(f"run_impact_analysis: {changed_req_id}, depth={depth}")

    repo = _load_repo(project_name)
    req = _find_req(repo, changed_req_id)

    if not req:
        return (
            f"⚠️ Requirement `{changed_req_id}` not found in the `{project_name}` project repository.\n"
            f"Check the ID, or initialize the repository via `init_traceability_repo`."
        )

    # BFS graph traversal
    visited = set()
    queue = [changed_req_id]
    affected: list[dict] = []

    while queue:
        current_id = queue.pop(0)
        if current_id in visited:
            continue
        visited.add(current_id)

        direct_links = _find_links(repo, current_id)
        for lnk in direct_links:
            neighbor_id = lnk["to"] if lnk["from"] == current_id else lnk["from"]
            if neighbor_id == changed_req_id:
                continue
            neighbor_req = _find_req(repo, neighbor_id)
            direction = "downstream" if lnk["from"] == current_id else "upstream"
            affected.append({
                "id": neighbor_id,
                "title": neighbor_req.get("title", "—") if neighbor_req else "external artifact",
                "type": neighbor_req.get("type", "unknown") if neighbor_req else "external",
                "relation": lnk["relation"],
                "direction": direction,
                "via": current_id,
                "status": neighbor_req.get("status", "—") if neighbor_req else "—",
            })
            # Report the business node as affected, but do NOT continue THROUGH it.
            #
            # Objectives are hubs: since 7.1 began writing `satisfies` from every
            # requirement to the objectives it serves (ADR-082), expanding past one
            # walked back down to every other requirement serving the same objective.
            # Changing a single requirement was reported as affecting 14 of 16 nodes,
            # and the better the analyst's traceability, the more inflated the estimate
            # — which also drove 5.4's Impact and Schedule Risk scores. Siblings sharing
            # an objective are not impacted by each other; the objective itself is worth
            # flagging, so it stays in the list.
            neighbor_is_business = (
                neighbor_req is not None
                and neighbor_req.get("type") in BUSINESS_NODE_TYPES
            )
            if depth == "full" and neighbor_id not in visited and not neighbor_is_business:
                queue.append(neighbor_id)

    # Deduplicate by id (keep the first occurrence)
    seen_ids: set = set()
    unique_affected = []
    for item in affected:
        if item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            unique_affected.append(item)

    # Group by link type.
    #
    # The headline count comes from `unique_affected`, so every relation reachable in
    # the graph MUST have a bucket here. Grouping into a fixed four while counting all
    # of them printed "13 artifacts affected" above tables holding nine rows, and the
    # artifacts it dropped were the ones reached over `threatens` — the risks
    # endangering the objective, which is precisely what impact analysis exists to
    # surface. Build the buckets from what is actually present.
    rel_labels = {
        "derives": ("⬇️ Derived requirements", "Review — they derive from the changed item"),
        "depends": ("↔️ Dependent requirements", "Check — they may lose meaning without the changed item"),
        "satisfies": ("✔️ Satisfies-linked (components / objectives served)",
                      "Components: estimate rework. Objectives: check the target is still met"),
        "verifies": ("🧪 Tests", "Rerun or update the test cases"),
        "threatens": ("⚠️ Risks (6.3)", "Re-assess — they threaten the changed item"),
        "modifies": ("📝 Change requests (5.4)", "Check whether the pending change still applies"),
    }

    by_relation: dict = {rel: [] for rel in rel_labels}
    for item in unique_affected:
        rel = item["relation"]
        by_relation.setdefault(rel, []).append(item)
        rel_labels.setdefault(
            rel, (f"🔗 Linked via `{rel}`", "Review the relationship"))

    lines = [
        f"<!-- BABOK 5.1 — Impact Analysis | Project: {project_name} | {date.today()} -->",
        "",
        f"# 🔍 Change impact analysis",
        "",
        f"**Project:** {project_name}  ",
        f"**Requirement being changed:** `{changed_req_id}` — {req.get('title', '')}  ",
        f"**Change description:** {change_description}  ",
        f"**Traversal mode:** {depth}  ",
        f"**Date:** {date.today()}",
        "",
        f"## Result: **{len(unique_affected)}** artifacts affected",
        "",
    ]

    if not unique_affected:
        lines += [
            "No links to other artifacts were found.",
            "",
            "> ℹ️ Either the requirement is isolated, or traceability hasn't been populated yet.",
            "> Recommend checking via `check_coverage`.",
        ]
    else:
        for rel, (label, action) in rel_labels.items():
            items = by_relation[rel]
            if not items:
                continue
            lines += [
                f"### {label} ({len(items)})",
                f"> **Action:** {action}",
                "",
                "| ID | Type | Title | Status | Via |",
                "|----|-----|----------|--------|-------|",
            ]
            for item in items:
                via = f"`{item['via']}`" if item["via"] != changed_req_id else "direct"
                lines.append(
                    f"| `{item['id']}` | {item['type']} | {item['title']} | {item['status']} | {via} |"
                )
            lines.append("")

    lines += [
        "---",
        "",
        "## Hand off to 5.4 for expert evaluation",
        "",
        "This report is a technical map of affected artifacts.",
        "Task **5.4** adds the expert decision:",
        "",
        "- Is this change worth taking?",
        "- What's the cost (time, resources, risks)?",
        "- What gets deferred to the backlog?",
        "- Is formal sign-off required (5.5)?",
    ]

    content = "\n".join(lines)
    save_artifact(content, prefix="5_1_impact_analysis", project_id=project_name)
    return content


# ---------------------------------------------------------------------------
# 5.1.4 — Coverage audit
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def check_coverage(
    project_name: str,
    filter_type: str = "",
) -> str:
    """
    BABOK 5.1 — Traceability coverage audit. Finds orphan requirements and gaps.

    What it looks for:
      🔴 Orphan with no source — no derives/satisfies link upward (no business justification)
      🟡 No implementation     — no derives/satisfies link downward (not implemented)
      🟡 No test               — no verifies link (not verified)
      🟢 Full coverage         — has source + implementation + test

    Args:
        project_name:  Project name.
        filter_type:   Filter by requirement type: business | stakeholder | solution | transition
                       Empty string — check all.

    Returns:
        Coverage report per requirement with recommendations.
    """
    logger.info(f"check_coverage: {project_name}, filter_type={filter_type!r}")

    repo = _load_repo(project_name)
    formality = repo.get("formality_level", "Standard")

    # Exclude archived statuses — they shouldn't appear in the coverage audit
    archive_statuses = {"deprecated", "superseded", "retired"}
    requirements = [r for r in repo["requirements"] if r.get("status") not in archive_statuses]
    if filter_type:
        requirements = [r for r in requirements if r.get("type") == filter_type]

    if not requirements:
        return f"ℹ️ No active requirements {'of type `' + filter_type + '`' if filter_type else ''} found in the `{project_name}` repository."

    orphans_no_source = []
    orphans_no_impl = []
    orphans_no_test = []
    fully_covered = []

    for req in requirements:
        req_id = req["id"]
        req_type = req.get("type", "")

        links = _find_links(repo, req_id)

        # A node HAS a source when it points UPWARD at something: it derives from a
        # parent, or it satisfies a goal/requirement. Both relations share the canonical
        # direction from=child/implementer -> to=parent/implemented, so the node is the
        # `from` in either case. (`verifies` gets the same treatment for tests below.)
        # Counting only `derives` false-flags two real populations: a 7.1 requirement
        # linked to a 6.2 business goal (ADR-082) and the `solution` nodes 6.4 pushes,
        # neither of which ever has a derives edge.
        # HAS an implementation when something derives from it (children point in as
        # `to`) or something satisfies it.
        has_source = any(
            lnk["relation"] in ("derives", "satisfies") and lnk["from"] == req_id
            for lnk in links
        )
        has_impl = any(
            (lnk["relation"] == "derives" and lnk["to"] == req_id) or
            (lnk["relation"] == "satisfies" and lnk["to"] == req_id)
            for lnk in links
        )
        has_test = any(
            lnk["relation"] == "verifies" and lnk["to"] == req_id
            for lnk in links
        )

        # Root requirement types have no "source" above them — that's expected
        # (a business need is the root of the derivation chain, like a business req).
        if req_type in ("business", "business_need"):
            has_source = True
        # A test's source is the requirement it verifies: tests link via `verifies`
        # (from=test -> to=req), never `derives`, so a test that verifies something
        # is not an orphan.
        elif req_type == "test":
            has_source = has_source or any(
                lnk["relation"] == "verifies" and lnk["from"] == req_id
                for lnk in links
            )
        # Analysis artifacts from other chapters anchor themselves with their OWN
        # relation: 6.3 writes `threatens` (from=risk -> to=objective) and 5.4 writes
        # `modifies` (from=CR -> to=requirement). Judging them by `derives`/`satisfies`
        # alone made every risk and every change request an orphan, and the audit told
        # the analyst to "find a business justification or freeze it" for nodes that
        # were already anchored.
        elif req_type in ANALYSIS_NODE_TYPES:
            has_source = has_source or any(
                lnk["relation"] in ("threatens", "modifies") and lnk["from"] == req_id
                for lnk in links
            )
            # Nor is anything supposed to IMPLEMENT them. An analysis artifact points
            # upward at what it concerns and that is its whole shape: nothing derives
            # from a risk, nothing satisfies a change request, and 6.4's scope node is
            # itself the implementer of the objectives it satisfies. Judging them by
            # the requirement rule told the analyst to "fill the gaps: add
            # implementation" for every risk in the project — the same misclassification
            # as the orphan verdict, one column over.
            has_impl = True

        issues = []
        if not has_source:
            issues.append("no_source")
        if not has_impl:
            issues.append("no_impl")
        # Test is checked only for Standard and Full
        if formality in ("Standard", "Full") and not has_test:
            # A test is expected from BEHAVIORAL requirement types. The original
            # rule knew only the classes `solution` / `transition` — the vocabulary
            # 5.1 shipped with — so the eight 7.1 node types were never checked and
            # a project specified entirely through 7.1 answered "✅ Coverage is
            # complete" without a single verifies edge (the axis was dead for the
            # platform's main path). Model artifacts (erd, data_dictionary,
            # business_process, business_rule) are not verified by test cases and
            # business/stakeholder requirements stay exempt as before.
            if req_type in BEHAVIORAL_REQ_TYPES:
                issues.append("no_test")

        req_info = {
            "id": req_id,
            "title": req.get("title", "—"),
            "type": req_type,
            "version": req.get("version", "1.0"),
            "status": req.get("status", "—"),
            "links_count": len(links),
        }

        if "no_source" in issues:
            orphans_no_source.append(req_info)
        elif "no_impl" in issues or "no_test" in issues:
            req_info["issues"] = issues
            orphans_no_impl.append(req_info)
        else:
            fully_covered.append(req_info)

    total = len(requirements)
    covered_pct = round(len(fully_covered) / total * 100) if total else 0

    lines = [
        f"<!-- BABOK 5.1 — Coverage Audit | Project: {project_name} | {date.today()} -->",
        "",
        f"# 📊 Traceability coverage audit",
        "",
        f"**Project:** {project_name}  ",
        f"**Formality level:** {formality}  ",
        f"**Filter:** {filter_type or 'all requirements'}  ",
        f"**Date:** {date.today()}",
        "",
        "## Summary",
        "",
        f"| Status | Count | % |",
        f"|--------|------------|---|",
        f"| 🟢 Full coverage | {len(fully_covered)} | {covered_pct}% |",
        f"| 🔴 No source (orphan) | {len(orphans_no_source)} | {round(len(orphans_no_source)/total*100) if total else 0}% |",
        f"| 🟡 Coverage gaps | {len(orphans_no_impl)} | {round(len(orphans_no_impl)/total*100) if total else 0}% |",
        f"| **Total** | **{total}** | 100% |",
        "",
    ]

    if orphans_no_source:
        lines += [
            "## 🔴 Requirements with no source (orphan)",
            "",
            "> **Diagnosis:** no `derives` or `satisfies` link upward. Unknown which business need or objective it came from.",
            "> **Action:** find a business justification via `add_trace_link`, or freeze it.",
            "",
            "| ID | Type | Title | Status |",
            "|----|-----|----------|--------|",
        ]
        for r in orphans_no_source:
            lines.append(f"| `{r['id']}` | {r['type']} | {r['title']} | {r['status']} |")
        lines.append("")

    if orphans_no_impl:
        lines += [
            "## 🟡 Requirements with coverage gaps",
            "",
            "| ID | Type | Title | Status | Issue |",
            "|----|-----|----------|--------|----------|",
        ]
        for r in orphans_no_impl:
            issues = r.get("issues", [])
            problem_parts = []
            if "no_impl" in issues:
                problem_parts.append("no implementation")
            if "no_test" in issues:
                problem_parts.append("no test")
            problem = ", ".join(problem_parts)
            lines.append(f"| `{r['id']}` | {r['type']} | {r['title']} | {r['status']} | {problem} |")
        lines.append("")

        lines += [
            "> **No implementation:** add a `satisfies` link (a component or requirement that implements it) or a `derives` link (child requirement)",
            "> **No test:** add a `verifies` link (test case)",
            "",
        ]

    if fully_covered:
        lines += [
            "## 🟢 Fully covered requirements",
            "",
            "| ID | Type | Title | Links |",
            "|----|-----|----------|--------|",
        ]
        for r in fully_covered:
            lines.append(f"| `{r['id']}` | {r['type']} | {r['title']} | {r['links_count']} |")
        lines.append("")

    lines += [
        "---",
        "",
        "## Recommendations",
        "",
    ]

    if orphans_no_source:
        lines.append(f"1. ⚠️ **Close out {len(orphans_no_source)} orphan requirement(s)** before prioritization (5.3) and approval (5.5).")
    if orphans_no_impl:
        lines.append(f"2. 🔧 **Fill the gaps** in {len(orphans_no_impl)} requirement(s): add implementation and/or tests.")
    if not orphans_no_source and not orphans_no_impl:
        lines.append("✅ Coverage is complete. Traceability is ready for 5.3 (Prioritization) and 5.5 (Approval).")

    content = "\n".join(lines)
    save_artifact(content, prefix="5_1_coverage_check", project_id=project_name)
    return content


# ---------------------------------------------------------------------------
# 5.1.5 — Export the traceability matrix to Markdown
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def export_traceability_matrix(
    project_name: str,
    filter_relation: str = "",
    filter_status: str = "",
    filter_type: str = "",
) -> str:
    """
    BABOK 5.1 — Generates a Markdown traceability matrix from the JSON repository.
    Used for handing off to stakeholders, for review, and in the 5.5 approval package.

    Args:
        project_name:      Project name.
        filter_relation:   Filter by link type: derives | depends | satisfies | verifies
                           Empty string — all links.
        filter_status:     Filter by requirement status: draft | confirmed | approved | deprecated
                           Empty string — all statuses.
        filter_type:       Filter by requirement type: business | stakeholder | solution | transition
                           Empty string — all types.

    Returns:
        Markdown traceability matrix. Also saved as an artifact.
    """
    logger.info(f"export_traceability_matrix: {project_name}, rel={filter_relation}, status={filter_status}")

    repo = _load_repo(project_name)

    requirements = repo["requirements"]
    if filter_type:
        requirements = [r for r in requirements if r.get("type") == filter_type]
    if filter_status == "approved":
        # `approved` is the one status value that is a durable FACT rather than a
        # position in the workflow, and it is not owned by this field: 7.3 overwrites
        # it with `validated` on the very requirements 5.5 approved. Filtering on the
        # literal silently dropped them from a matrix that goes into the 5.5 signing
        # package — the reader sees a shorter list and no indication anything is
        # missing. The durable answer is 5.5's own stored decisions; the literal is
        # kept as a fallback for projects with no approval records.
        # Role guard on the fallback: 5.4 writes status="approved" on the CR node
        # meaning "the change request was accepted", and a pre-migration 6.4 scope
        # node carried the same literal meaning "the scope is settled". Without the
        # guard both passed this filter and appeared in the approved-requirements
        # matrix — a document that goes into the 5.5 signing package. Same
        # one-literal-two-meanings class ADR-082 resolved for the type field.
        requirements = [
            r for r in requirements
            if r.get("type", "") not in ANALYSIS_NODE_TYPES
            and (has_been_approved(project_name, r.get("id", ""))
                 or r.get("status") == "approved")
        ]
    elif filter_status == "verified":
        # Same durable-fact reasoning as `approved`: 7.3/5.5 overwrite `verified` in the
        # shared status field, so the literal drops verified requirements from the matrix.
        requirements = [r for r in requirements
                        if has_passed_verification(repo, r.get("id", ""))]
    elif filter_status == "validated":
        # 5.5 (approved) / 5.4 (under_change) / a re-run 7.2 overwrite `validated`.
        requirements = [r for r in requirements
                        if has_been_validated(repo, r.get("id", ""))]
    elif filter_status:
        requirements = [r for r in requirements if r.get("status") == filter_status]

    req_ids = {r["id"] for r in requirements}

    links = repo["links"]
    if filter_relation:
        links = [lnk for lnk in links if lnk["relation"] == filter_relation]
    # Only show links where at least one end is among the filtered requirements
    if filter_type or filter_status:
        links = [lnk for lnk in links if lnk["from"] in req_ids or lnk["to"] in req_ids]

    rel_icons = {
        "derives": "⬇️ derives",
        "depends": "↔️ depends",
        "satisfies": "✔️ satisfies",
        "verifies": "🧪 verifies",
    }

    # Rendering order for the types 5.1 itself defines. It is an ORDER, not a filter:
    # any type not listed here still gets a section (see below). Driving the render
    # off a positive list meant every type added by a later chapter — 6.1's needs,
    # 6.2's goals, 6.3's risks, 5.4's change requests and all eight of 7.1's
    # specification types — was counted in the header and then never rendered. This
    # document goes into the 5.5 approval package, so the omission is silent and signed.
    type_order = ["business", "stakeholder", "solution", "transition", "test", "component"]
    type_labels = {
        "business": "Business requirements",
        "stakeholder": "Stakeholder requirements",
        "solution": "Solution requirements",
        "transition": "Transition requirements",
        "test": "Tests",
        "component": "Components",
        "business_need": "Business needs (6.1)",
        "business_goal": "Business objectives (6.2)",
        "risk": "Risks (6.3)",
        "change_request": "Change requests (5.4)",
        "solution_scope": "Solution scope (6.4)",
        "functional": "Functional requirements",
        "non_functional": "Non-functional requirements",
        "business_rule": "Business rules",
        "user_story": "User stories",
        "use_case": "Use cases",
        "business_process": "Business processes",
        "data_dictionary": "Data dictionaries",
        "erd": "Entity-relationship models",
    }
    # Known types first, in the order above; then anything else, so a node type
    # introduced later is rendered under its own name instead of disappearing.
    present_types = {r.get("type") or "untyped" for r in requirements}
    render_order = [t for t in type_order if t in present_types]
    render_order += sorted(present_types - set(type_order))

    lines = [
        f"<!-- BABOK 5.1 — Traceability Matrix | Project: {project_name} | {date.today()} -->",
        "",
        f"# 🗺️ Requirements traceability matrix",
        "",
        f"**Project:** {project_name}  ",
        f"**Formality level:** {repo.get('formality_level', 'Standard')}  ",
        f"**Filters:** type={filter_type or 'all'}, status={filter_status or 'all'}, links={filter_relation or 'all'}  ",
        f"**Generated on:** {date.today()}",
        "",
        f"**Total requirements:** {len(requirements)} | **Links:** {len(links)}",
        "",
    ]

    # Section: requirements by type
    lines.append("## Requirements")
    lines.append("")

    for req_type in render_order:
        type_reqs = [r for r in requirements
                     if (r.get("type") or "untyped") == req_type]
        if not type_reqs:
            continue
        label = type_labels.get(req_type, req_type)
        lines += [
            f"### {label}",
            "",
            "| ID | v | Title | Status | Source |",
            "|----|---|----------|--------|----------|",
        ]
        for r in sorted(type_reqs, key=lambda x: x["id"]):
            src = r.get("source_artifact", "")
            src_short = src.split("/")[-1] if src else "—"
            lines.append(
                f"| `{r['id']}` | {r.get('version','1.0')} | {r.get('title','—')} "
                f"| {r.get('status','—')} | {src_short} |"
            )
        lines.append("")

    # Section: links
    lines += [
        "## Traceability links",
        "",
        "| From | Link type | To | Rationale | Added |",
        "|----|-----------|---|-------------|-----------|",
    ]

    for lnk in sorted(links, key=lambda x: (x.get("relation", ""), x.get("from", ""))):
        rel = rel_icons.get(lnk["relation"], lnk["relation"])
        rationale = lnk.get("rationale", "—")
        added = link_date(lnk)
        lines.append(
            f"| `{lnk['from']}` | {rel} | `{lnk['to']}` | {rationale} | {added} |"
        )

    if not links:
        lines.append("| — | — | — | No links yet | — |")

    lines += [
        "",
        "---",
        f"*Generated: {datetime.now().strftime('%d.%m.%Y %H:%M')}*  ",
        f"*Repository: `{_repo_path(project_name)}`*",
    ]

    content = "\n".join(lines)
    save_artifact(content, prefix="5_1_traceability_matrix", project_id=project_name)
    return content


if __name__ == "__main__":
    mcp.run()
