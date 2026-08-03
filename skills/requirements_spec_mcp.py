"""
BABOK 7.1 — Specify and Model Requirements
MCP tools for formalizing requirements from elicitation results.

Tools:
  - analyze_elicitation_context  — analyzes 4.3 artifacts, list of candidate requirements
  - create_user_story            — User Story with AC, auto-registration in 5.1
  - create_functional_requirement — SRS-style (functional/non_functional/business_rule), auto-registration in 5.1
  - create_use_case              — textual UC specification, auto-registration in 5.1
  - generate_use_case_diagram    — PlantUML Use Case Diagram for all project UCs
  - create_business_process      — text + PlantUML Activity Diagram, auto-registration in 5.1
  - create_data_dictionary       — registry of entities and attributes, auto-registration in 5.1
  - create_erd                   — description of relationships + PlantUML ER Diagram, auto-registration in 5.1
  - build_coverage_matrix        — "business objective -> requirements" matrix with coverage flags

ADR-022: every creating tool registers the req in 5.1 automatically (status draft)
ADR-023: analyze_elicitation_context — hybrid reading (4.3 file -> fallback to context_text)
ADR-024: create_business_process generates .md + .puml
ADR-025: PlantUML for all diagrams

Artifact storage: governance_plans/{project_id}_specs/

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
import glob
from datetime import date
from typing import Optional
from mcp.server.fastmcp import FastMCP
from skills.common import (
    save_artifact, logger, DATA_DIR, data_path, normalize_project_id, specs_dir,
    parse_json_str_list, BUSINESS_NODE_TYPES, SOLUTION_SCOPE_NODE_TYPE,
    read_json_artifact, guard_artifact_errors, is_archived, archived_suffix,
    safe_filename_part, CorruptArtifactError,
)

mcp = FastMCP("BABOK_Requirements_Spec")

REPO_FILENAME = "traceability_repo.json"
CONFIRMED_GLOB = "4_3_*_confirmed*.md"

# Nodes in the 5.1 graph that are NOT specification requirements, so they must not be
# counted in the coverage matrix nor reported as "unlinked to an objective". Beyond the
# business roots these are the nodes other chapters push into the SAME graph: `test`
# (5.1), `change_request` (5.4) and `risk` (6.3, ADR-074).
# Found by E2E: a CR opened in 5.4 was being counted as an uncovered requirement here.
# Same class as findings 7.3-A / 7.4-C — a skip-filter that knows only part of the set.
#
# `solution` stays a REQUIREMENT here: it is the BABOK requirement CLASS in the 5.1
# vocabulary (business | stakeholder | solution | transition), which is how
# `init_traceability_repo` and the Confluence import label ordinary FR/NFR. 6.4's scope
# node used to share that literal, which is why it could not be skipped; it now types
# itself `solution_scope` (ADR-082, revised), so the scope node is excluded and real
# requirements are not.
NON_SPEC_NODE_TYPES = BUSINESS_NODE_TYPES | {
    "test", "change_request", "risk", SOLUTION_SCOPE_NODE_TYPE,
}


# ---------------------------------------------------------------------------
# Utilities — repository 5.1
# ---------------------------------------------------------------------------

def _repo_path(project_id: str) -> str:
    safe = normalize_project_id(project_id)
    return data_path(project_id, f"{safe}_{REPO_FILENAME}")


def _load_repo(project_id: str) -> dict:
    path = _repo_path(project_id)
    if os.path.exists(path):
        # Raises CorruptArtifactError, converted to a ❌ line by guard_artifact_errors
        # at the tool boundary. A bare json.load here made a damaged file a protocol
        # error in every downstream tool.
        return read_json_artifact(path, "5.1 traceability repository")
    return {
        "project": project_id,
        "formality_level": "Standard",
        "created": str(date.today()),
        "updated": str(date.today()),
        "requirements": [],
        "links": [],
        "history": [],
    }


def _save_repo(repo: dict) -> None:
    path = _repo_path(repo["project"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    repo["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)
    logger.info(f"Repository 5.1 updated (7.1): {path}")


def _register_in_repo(project_id: str, req_id: str, req_type: str,
                      title: str, source_artifact: str, priority: str = "Medium",
                      business_goal_ids: Optional[list] = None,
                      owner: str = "") -> str:
    """
    ADR-022: registers a requirement in repository 5.1 with status draft.
    If a requirement with this ID already exists — skips the node (without an error).

    A1: also writes the BA-declared `satisfies` edges requirement -> business objective
    (ADR-082, from=requirement to=objective). These edges are what makes per-goal coverage
    in `build_coverage_matrix` a real claim instead of a project-level average, and they
    are what `check_coverage` (5.1) and CR impact analysis (5.4) read.

    Node registration and edge registration are INDEPENDENT on purpose: registration
    returns early for an already-known id, so an existing requirement must still receive
    newly declared links — otherwise a re-run meant to add the objective silently does
    nothing.

    Returns a marker string to include in the artifact.
    """
    repo = _load_repo(project_id)
    # `_load_repo` returns a stored file as-is, so a legacy or partial repo may be missing
    # keys the default skeleton has. Writing edges made `links` a hard dependency here for
    # the first time; an absent key would raise instead of returning a readable message
    # (the CH3-A / CH4-A class). `history` is hardened alongside it — same one-line risk.
    repo.setdefault("requirements", [])
    repo.setdefault("links", [])
    repo.setdefault("history", [])

    existing_ids = {r["id"] for r in repo["requirements"]}
    notes = []

    if req_id in existing_ids:
        logger.info(f"_register_in_repo: {req_id} already in repository, skipping node")
        # The node stays, but what THIS specification states must not vanish into it.
        #
        # The documented order is 5.1 first (ids, types, titles), then 7.1 for each
        # specification — and 7.1 is where the analyst names the owner. Returning early
        # dropped that name, so `owner` stayed empty on the node: 7.4 reads it as
        # EVIDENCE of representation and turned the named person into a critical gap in
        # a signed document, the 5.5 package printed a blank owner, and the 5.2 audit
        # called the attribute unfilled. Found by a pre-release live run (E2-1).
        #
        # INSERT-ONLY, the same rule the 3.2 registry seeding follows: a value already
        # on the node was put there by another chapter, and a specification re-run must
        # not silently replace it. Only what is absent or empty is filled.
        node = next(r for r in repo["requirements"] if r.get("id") == req_id)
        filled = []
        for field, value in (("owner", owner), ("priority", priority),
                             ("source_artifact", source_artifact)):
            if value and not node.get(field):
                node[field] = value
                filled.append(field)
        if filled:
            notes.append(
                f"ℹ️ `{req_id}` is already registered in repository 5.1 — filled in "
                f"from this specification: {', '.join(filled)}.")
        else:
            notes.append(f"ℹ️ `{req_id}` is already registered in repository 5.1.")
    else:
        repo["requirements"].append({
            "id": req_id,
            "type": req_type,
            "title": title,
            "version": "1.0",
            "status": "draft",
            "priority": priority,
            # The creating call's owner used to be dropped here (hard-coded ""),
            # so the approval package and every owner-reading consumer showed a
            # blank owner for requirements whose author had named one.
            "owner": owner,
            "stability": "Unknown",
            "source_artifact": source_artifact,
            "added": str(date.today()),
            "last_reviewed": str(date.today()),
        })
        repo["history"].append({
            "action": "requirement_added",
            "req_id": req_id,
            "source": "7.1_spec",
            "date": str(date.today()),
        })
        notes.append(f"✅ `{req_id}` registered in repository 5.1 (status: draft).")

    nodes_by_id = {r["id"]: r for r in repo["requirements"]}
    # Idempotency on EDGES, not just on nodes — the bug that recurred in 6.3 and 6.4.
    existing_edges = {
        (lnk.get("from"), lnk.get("to"), lnk.get("relation")) for lnk in repo["links"]
    }
    added = 0

    for goal_id in (business_goal_ids or []):
        target = nodes_by_id.get(goal_id)
        if target is None:
            # Never invent the node: a phantom objective would poison check_coverage,
            # the 7.3 BFS, the 7.4 matrix and 5.4 impact analysis. Warn, don't block.
            notes.append(
                f"⚠️ Objective `{goal_id}` is not in repository 5.1 — link skipped. "
                f"Define objectives in 6.2 (`define_goals_and_objectives`)."
            )
            continue
        if target.get("type") not in BUSINESS_NODE_TYPES:
            notes.append(
                f"⚠️ `{goal_id}` is a `{target.get('type')}` node, not a business objective — "
                f"link skipped. For requirement-to-requirement relations use "
                f"`add_trace_link` (5.1)."
            )
            continue
        key = (req_id, goal_id, "satisfies")
        if key in existing_edges:
            continue
        repo["links"].append({
            "from": req_id,
            "to": goal_id,
            "relation": "satisfies",
            # `rationale` is REQUIRED at Full formality and the matrix renders it, so
            # omitting it put a dash in the column a regulated project exists to fill.
            # `added` is the spelling every other producer uses; `created` was read by
            # nobody.
            "rationale": f"Requirement {req_id} serves objective {goal_id}",
            "added": str(date.today()),
        })
        existing_edges.add(key)
        added += 1

    if added:
        notes.append(f"🔗 Linked to {added} business objective(s) via `satisfies`.")

    _save_repo(repo)
    return " ".join(notes)


# ---------------------------------------------------------------------------
# Utilities — file system
# ---------------------------------------------------------------------------

def _specs_dir(project_id: str) -> str:
    # issue #1: specs live in data/<project>/specs/, with a fallback to legacy layouts.
    # Single source of truth — common.specs_dir.
    return specs_dir(project_id)


def _save_spec(content: str, project_id: str, filename: str) -> str:
    """Saves a specification to data/<project_id>/specs/. Returns the path.

    The guard lives HERE, in the one writer, rather than in each of the six producers
    that build a filename. Every producer composes the name out of the requirement id
    and its TITLE — free text, written by an LLM from the analyst's dictation — and none
    of them called the shared sanitiser: `title="../../../escaped"` put the file two
    levels above specs/, answered with the full document and no warning, and left the
    graph node's `source_artifact` pointing at a path that does not exist.

    Two layers, deliberately. `safe_filename_part` removes the separators; the
    containment check then refuses anything that still resolves outside the directory,
    so a future producer that formats its own name cannot reopen this.
    """
    target_dir = _specs_dir(project_id)
    os.makedirs(target_dir, exist_ok=True)
    filepath = os.path.join(target_dir, safe_filename_part(filename))

    real_dir = os.path.realpath(target_dir)
    real_path = os.path.realpath(filepath)
    if os.path.commonpath([real_path, real_dir]) != real_dir:
        raise CorruptArtifactError(
            f"❌ The specification file name resolves outside the project's specs "
            f"folder: `{filename}`.\n"
            f"   Nothing has been written. Rename the requirement so its title does "
            f"not read as a path."
        )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"Specification saved: {filepath}")
    return filepath


def _find_confirmed_artifact(project_id: str):
    """ADR-023: finds the latest confirmed 4.3 artifact for project_id, or None.

    The 4.3 producer (save_confirmed_elicitation_result -> save_artifact) writes the report to
      reports/<project_id>/4_3_confirmed_result_<timestamp>.md
    i.e. project_id is the FOLDER name, and the filename itself does NOT contain project_id.
    An earlier implementation searched only flat data/ with masks that REQUIRED project_id
    inside the filename, so it never matched the real artifact (audit finding 7.1-A).

    ONE pattern, and the project folder is what scopes it. The flat fallbacks that used
    to follow it could not filter by project at all — a flat artifact carries the
    project id neither in its name nor in its folder — so they could hand THIS project
    the elicitation results of another one, and requirements derived from another
    project's interviews look perfectly ordinary. They warned about themselves, which
    is why the caller used to receive a `project_scoped` flag. Both went with the legacy
    layout (owner's decision, 2026-08-03).
    """
    from skills.common import report_dir_for
    matches = glob.glob(os.path.join(report_dir_for(project_id), "4_3_*confirmed*.md"))
    if not matches:
        return None
    # latest by modification time (filenames carry a timestamp, but mtime is robust)
    return max(matches, key=os.path.getmtime)


def _read_confirmed_artifact(path: str) -> str:
    """Reads the contents of the 4.3 artifact."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _load_future_state_goals(project_id: str) -> list:
    """Reads the 6.2 business objectives from future_state_goals.json (audit finding 7.1-C).

    6.2 (Define Future State) is the real source of business objectives, not the 4.3 confirmed
    artifact. Returns a list of goal_title strings (empty if the 6.2 file is absent/unreadable).
    Contract matches the 6.2 producer: key 'goals', field 'goal_title'.
    """
    safe = normalize_project_id(project_id)
    path = data_path(project_id, f"{safe}_future_state_goals.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [
                g.get("goal_title", "").strip()
                for g in data.get("goals", [])
                if g.get("goal_title", "").strip()
            ]
        except (IOError, json.JSONDecodeError, TypeError):
            pass
    return []


# ---------------------------------------------------------------------------
# 7.1.1 — Analyze elicitation context (ADR-023)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def analyze_elicitation_context(
    project_id: str,
    context_text: str = "",
) -> str:
    """
    BABOK 7.1 — Analyzes confirmed elicitation results (4.3) and proposes
    a list of candidate requirements classified by type with a recommended ID prefix.

    ADR-023 (hybrid reading):
      1. Tries to find the 4.3 file by project_id in governance_plans/
      2. If not found and context_text is empty — returns instructions
      3. If not found but context_text is provided — uses the supplied text

    Args:
        project_id:    Project identifier (used to locate the 4.3 file).
        context_text:  Text of the 4.3 artifact (if the file is not found automatically).
                       Leave empty — the tool will try to find the file itself.

    Returns:
        A list of business objectives, candidate requirements and information gaps.
    """
    logger.info(f"analyze_elicitation_context: project_id='{project_id}'")

    # ADR-023: hybrid reading
    source_used = ""
    content_to_analyze = ""

    artifact_path = _find_confirmed_artifact(project_id)
    if artifact_path:
        content_to_analyze = _read_confirmed_artifact(artifact_path)
        source_used = f"📂 File found automatically: `{artifact_path}`"
        logger.info(f"4.3 artifact found: {artifact_path}")
    elif context_text.strip():
        content_to_analyze = context_text.strip()
        source_used = "📋 Used text supplied manually."
        logger.info("4.3 artifact not found — using context_text")
    else:
        return (
            f"⚠️ 4.3 artifact not found for project `{project_id}`.\n\n"
            f"The tool searched for files matching the pattern:\n"
            f"`governance_plans/4_3_{project_id.lower().replace(' ', '_')}_confirmed*.md`\n\n"
            f"**Options:**\n"
            f"1. Make sure the 4.3 artifact was created via `save_confirmed_elicitation_result` (4.3)\n"
            f"2. Pass the content manually: `analyze_elicitation_context("
            f"project_id='{project_id}', context_text='[paste the 4.3 artifact text]')`"
        )

    # Build the analytical query over the content
    # (The tool is executed by Claude Code — it reads the content and reasons about it)
    word_count = len(content_to_analyze.split())
    line_count = content_to_analyze.count("\n")

    lines = [
        f"<!-- BABOK 7.1 — Context analysis | Project: {project_id} | {date.today()} -->",
        "",
        f"# 🔍 Elicitation context analysis",
        "",
        f"**Project:** {project_id}  ",
        f"**Date:** {date.today()}  ",
        f"**Source:** {source_used}  ",
        f"**Size:** {word_count} words, {line_count} lines",
        "",
        "---",
        "",
        "## Contents of the 4.3 artifact to analyze",
        "",
        "Claude Code: read the content below and perform the analysis per the steps.",
        "",
        "```",
        content_to_analyze[:3000] + ("..." if len(content_to_analyze) > 3000 else ""),
        "```",
        "",
        "---",
        "",
        "## Analysis instructions (for Claude Code)",
        "",
        "Based on the contents of the 4.3 artifact above, do the following:",
        "",
        "### 1. Extract business objectives",
        "Find all mentioned business objectives (the 'Business objectives' section or equivalent).",
        "If there is no explicit section — infer the objectives from the context.",
        "",
        "### 2. Classify candidate requirements",
        "For each elicited requirement/need, determine the type:",
        "",
        "| Type | ID prefix | When to use |",
        "|-----|-----------|-------------------|",
        "| user_story | US- | User need in an Agile context |",
        "| functional | FR- | System behavior, Predictive context |",
        "| non_functional | NFR- | Quality characteristics (SLA, speed, security) |",
        "| business_rule | BR- | Business rule or domain constraint |",
        "| use_case | UC- | Scenario of an actor interacting with the system |",
        "| business_process | BP- | Business process with several participants |",
        "| data_dictionary | DD- | Description of the data/entity structure |",
        "| erd | ERD- | Relationships between entities |",
        "",
        "### 3. Identify information gaps",
        "List topics for which elicitation did not yield enough information for specification.",
        "For each gap — a recommendation: run an additional elicitation session or clarify with the stakeholder.",
        "",
        "### 4. Propose an order for creating artifacts",
        "Order from general to specific: business rules → use cases → functional requirements → data.",
        "",
        "---",
        "",
        "## Next step",
        "",
        "After the analysis, use the 7.1 tools to create artifacts:",
        "- `create_user_story` — for User Stories",
        "- `create_functional_requirement` — for FR/NFR/BR",
        "- `create_use_case` — for Use Cases",
        "- `create_business_process` — for Business Processes",
        "- `create_data_dictionary` + `create_erd` — for data",
        "- `build_coverage_matrix` — at the end to check coverage",
    ]

    result = "\n".join(lines)
    save_artifact(result, prefix="7_1_context_analysis", project_id=project_id)
    return result


# ---------------------------------------------------------------------------
# 7.1.2 — User Story
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def create_user_story(
    project_id: str,
    story_id: str,
    title: str,
    role: str,
    action: str,
    benefit: str,
    acceptance_criteria_json: str,
    priority: str = "Medium",
    source_artifact: str = "",
    notes: str = "",
    business_goal_ids_json: str = "[]",
) -> str:
    """
    BABOK 7.1 — Creates a User Story with Acceptance Criteria.
    Automatically registers it in repository 5.1 (status draft). ADR-022.

    Args:
        project_id:                Project identifier.
        story_id:                  Story ID: US-001, US-002, etc.
        title:                     Short title (for the heading and the 5.1 registry).
        role:                      User role: "Application Manager", "Customer", "Administrator".
        action:                    What the user wants to do (without "I want").
        benefit:                   Business value (without "so that").
        acceptance_criteria_json:  JSON list of acceptance criteria: ["Criterion 1", "Criterion 2"]
                                   At least 2 criteria.
        priority:                  High | Medium | Low. Default Medium.
        source_artifact:           Path to the 4.3 artifact (for traceability).
        notes:                     Additional context, constraints, references.
        business_goal_ids_json:  JSON list of 6.2 business objective IDs this item serves:
                                 ["BG-001", "BG-002"]. Writes `satisfies` links into the
                                 5.1 graph — that is what makes per-objective coverage in
                                 `build_coverage_matrix` precise. Empty — no links.

    Returns:
        Markdown User Story artifact + confirmation of registration in 5.1.
    """
    logger.info(f"create_user_story: {story_id} in project '{project_id}'")

    # Parsed BEFORE the artifact is written, so a rejected call leaves no orphan file.
    goal_ids, goal_err = parse_json_str_list(
        business_goal_ids_json, "business_goal_ids_json", example='["BG-001"]')
    if goal_err:
        return goal_err

    try:
        criteria = json.loads(acceptance_criteria_json)
        if not isinstance(criteria, list):
            raise ValueError("Must be a list")
    except (json.JSONDecodeError, ValueError) as e:
        return f"❌ Error parsing acceptance_criteria_json: {e}\nExpected a JSON list: [\"Criterion 1\", \"Criterion 2\"]"

    if len(criteria) < 2:
        return "❌ At least 2 Acceptance Criteria are required. A User Story without AC is not a requirement."

    criteria_md = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(criteria))

    lines = [
        f"<!-- BABOK 7.1 — User Story | Project: {project_id} | {date.today()} -->",
        "",
        f"# {story_id} — {title}",
        "",
        "| Attribute | Value |",
        "|---------|----------|",
        f"| Type | User Story |",
        f"| Project | {project_id} |",
        f"| Source | {source_artifact or '—'} |",
        f"| Priority | {priority} |",
        f"| Status | draft |",
        f"| Version | 1.0 |",
        f"| Date | {date.today()} |",
        "",
        "---",
        "",
        "## Story",
        "",
        f"As a **{role}**,  ",
        f"I want **{action}**,  ",
        f"So that **{benefit}**.",
        "",
        "## Acceptance Criteria",
        "",
        criteria_md,
    ]

    if notes:
        lines += ["", "## Additional context", "", notes]

    lines += [
        "",
        "---",
        "",
        "## Traceability",
        "",
        f"| Link | Artifact |",
        f"|-------|----------|",
        f"| Source (4.3) | {source_artifact or '—'} |",
        f"| Registry (5.1) | automatic registration |",
    ]

    content = "\n".join(lines)

    # Save the artifact
    safe_id = story_id.lower().replace("-", "_")
    safe_title = title.lower().replace(" ", "_")[:30]
    filename = f"{safe_id}_{safe_title}.md"
    spec_path = _save_spec(content, project_id, filename)

    # ADR-022: auto-registration in 5.1
    reg_note = _register_in_repo(project_id, story_id, "user_story", title, spec_path, priority, goal_ids)

    return content + f"\n\n---\n\n**Registration in 5.1:** {reg_note}\n**File:** `{spec_path}`"


# ---------------------------------------------------------------------------
# 7.1.3 — Functional Requirement
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def create_functional_requirement(
    project_id: str,
    req_id: str,
    req_type: str,
    title: str,
    description: str,
    rationale: str,
    priority: str = "Medium",
    owner: str = "",
    source_artifact: str = "",
    constraints: str = "",
    related_ids_json: str = "[]",
    business_goal_ids_json: str = "[]",
) -> str:
    """
    BABOK 7.1 — Creates a formal SRS-style requirement.
    Automatically registers it in repository 5.1 (status draft). ADR-022.

    Args:
        project_id:        Project identifier.
        req_id:            Requirement ID: FR-001, NFR-001, BR-001.
        req_type:          functional | non_functional | business_rule
        title:             Short requirement title.
        description:       Full statement.
                           functional:     "The system SHALL [action]..."
                           non_functional: "The system SHALL [metric] [value] under [condition]"
                           business_rule:  "[Subject] [constraint/rule]"
        rationale:         Rationale — why this requirement is needed.
        priority:          High | Medium | Low.
        owner:             Owner/stakeholder responsible for the requirement.
        source_artifact:   Path to the 4.3 artifact.
        constraints:       Constraints and assumptions.
        related_ids_json:  JSON list of related IDs: ["BR-001", "UC-001"]
        business_goal_ids_json:  JSON list of 6.2 business objective IDs this item serves:
                                 ["BG-001", "BG-002"]. Writes `satisfies` links into the
                                 5.1 graph — that is what makes per-objective coverage in
                                 `build_coverage_matrix` precise. Empty — no links.

    Returns:
        Markdown requirement artifact + confirmation of registration in 5.1.
    """
    logger.info(f"create_functional_requirement: {req_id} ({req_type}) in project '{project_id}'")

    # Parsed BEFORE the artifact is written, so a rejected call leaves no orphan file.
    goal_ids, goal_err = parse_json_str_list(
        business_goal_ids_json, "business_goal_ids_json", example='["BG-001"]')
    if goal_err:
        return goal_err

    valid_types = {"functional", "non_functional", "business_rule"}
    if req_type not in valid_types:
        return (
            f"❌ Invalid req_type: '{req_type}'.\n"
            f"Allowed values: functional | non_functional | business_rule"
        )

    try:
        related_ids = json.loads(related_ids_json)
        if not isinstance(related_ids, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        related_ids = []

    type_labels = {
        "functional": "Functional requirement",
        "non_functional": "Non-functional requirement",
        "business_rule": "Business rule",
    }

    type_hints = {
        "functional": "Statement: \"The system SHALL [action]...\"",
        "non_functional": "Statement: \"The system SHALL [metric] [value] under [condition]\"",
        "business_rule": "Statement: \"[Subject] [constraint]\" — not tied to the system",
    }

    related_md = ", ".join(f"`{r}`" for r in related_ids) if related_ids else "—"

    lines = [
        f"<!-- BABOK 7.1 — {type_labels[req_type]} | Project: {project_id} | {date.today()} -->",
        "",
        f"# {req_id} — {title}",
        "",
        "| Attribute | Value |",
        "|---------|----------|",
        f"| Type | {type_labels[req_type]} |",
        f"| Project | {project_id} |",
        f"| Source | {source_artifact or '—'} |",
        f"| Priority | {priority} |",
        f"| Owner | {owner or '—'} |",
        f"| Status | draft |",
        f"| Version | 1.0 |",
        f"| Date | {date.today()} |",
        "",
        "---",
        "",
        "## Statement",
        "",
        f"> _{type_hints[req_type]}_",
        "",
        description,
        "",
        "## Rationale",
        "",
        rationale,
    ]

    if constraints:
        lines += ["", "## Constraints and assumptions", "", constraints]

    lines += [
        "",
        "## Related requirements",
        "",
        related_md,
        "",
        "---",
        "",
        "## Traceability",
        "",
        "| Link | Artifact |",
        "|-------|----------|",
        f"| Source (4.3) | {source_artifact or '—'} |",
        f"| Registry (5.1) | automatic registration |",
    ]

    content = "\n".join(lines)

    safe_id = req_id.lower().replace("-", "_")
    safe_title = title.lower().replace(" ", "_")[:30]
    filename = f"{safe_id}_{safe_title}.md"
    spec_path = _save_spec(content, project_id, filename)

    # ADR-022: auto-registration
    repo_type_map = {
        "functional": "functional",
        "non_functional": "non_functional",
        "business_rule": "business_rule",
    }
    reg_note = _register_in_repo(project_id, req_id, repo_type_map[req_type], title, spec_path, priority, goal_ids, owner=owner)

    return content + f"\n\n---\n\n**Registration in 5.1:** {reg_note}\n**File:** `{spec_path}`"


# ---------------------------------------------------------------------------
# 7.1.4 — Use Case
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def create_use_case(
    project_id: str,
    uc_id: str,
    title: str,
    primary_actor: str,
    precondition: str,
    postcondition: str,
    trigger: str,
    main_scenario: str,
    priority: str = "Medium",
    secondary_actors: str = "",
    alt_scenarios: str = "",
    exc_scenarios: str = "",
    business_rules: str = "",
    source_artifact: str = "",
    business_goal_ids_json: str = "[]",
) -> str:
    """
    BABOK 7.1 — Creates a textual Use Case specification.
    Automatically registers it in repository 5.1 (status draft). ADR-022.

    Args:
        project_id:        Project identifier.
        uc_id:             Use case ID: UC-001, UC-002.
        title:             UC title in the form "Verb + Object": "Submit application".
        primary_actor:     Primary actor initiating the UC.
        precondition:      Condition that must be true before the UC starts.
        postcondition:     System state after the UC completes successfully.
        trigger:           Event that triggers the UC.
        main_scenario:     Main scenario (Happy Path). Numbered steps separated by \\n.
        priority:          High | Medium | Low.
        secondary_actors:  Secondary actors, comma-separated.
        alt_scenarios:     Alternative scenarios (numbering: 2a, 3b...).
        exc_scenarios:     Exception scenarios (numbering: Xa, Yb...).
        business_rules:    Business rules applied in the UC.
        source_artifact:   Path to the 4.3 artifact.
        business_goal_ids_json: JSON list of 6.2 business objective IDs this item serves:
                         ["BG-001", "BG-002"]. Writes `satisfies` links into the 5.1 graph —
                         that is what makes per-objective coverage in `build_coverage_matrix`
                         precise. Empty — no links.

    Returns:
        Markdown Use Case artifact + confirmation of registration in 5.1.
    """
    logger.info(f"create_use_case: {uc_id} in project '{project_id}'")

    # Parsed BEFORE the artifact is written, so a rejected call leaves no orphan file.
    goal_ids, goal_err = parse_json_str_list(
        business_goal_ids_json, "business_goal_ids_json", example='["BG-001"]')
    if goal_err:
        return goal_err

    lines = [
        f"<!-- BABOK 7.1 — Use Case | Project: {project_id} | {date.today()} -->",
        "",
        f"# {uc_id} — {title}",
        "",
        "| Attribute | Value |",
        "|---------|----------|",
        f"| Type | Use Case |",
        f"| Project | {project_id} |",
        f"| Source | {source_artifact or '—'} |",
        f"| Priority | {priority} |",
        f"| Status | draft |",
        f"| Version | 1.0 |",
        f"| Date | {date.today()} |",
        "",
        "---",
        "",
        "## General information",
        "",
        "| Attribute | Value |",
        "|---------|----------|",
        f"| Actor (primary) | {primary_actor} |",
        f"| Actors (secondary) | {secondary_actors or '—'} |",
        f"| Precondition | {precondition} |",
        f"| Postcondition | {postcondition} |",
        f"| Trigger | {trigger} |",
        "",
        "## Main scenario (Happy Path)",
        "",
        main_scenario,
    ]

    if alt_scenarios:
        lines += ["", "## Alternative scenarios", "", alt_scenarios]

    if exc_scenarios:
        lines += ["", "## Exception scenarios", "", exc_scenarios]

    if business_rules:
        lines += ["", "## Business rules and constraints", "", business_rules]

    lines += [
        "",
        "---",
        "",
        "## Traceability",
        "",
        "| Link | Artifact |",
        "|-------|----------|",
        f"| Source (4.3) | {source_artifact or '—'} |",
        f"| Registry (5.1) | automatic registration |",
    ]

    content = "\n".join(lines)

    safe_id = uc_id.lower().replace("-", "_")
    safe_title = title.lower().replace(" ", "_")[:30]
    filename = f"{safe_id}_{safe_title}.md"
    spec_path = _save_spec(content, project_id, filename)

    reg_note = _register_in_repo(project_id, uc_id, "use_case", title, spec_path, priority, goal_ids)

    return content + f"\n\n---\n\n**Registration in 5.1:** {reg_note}\n**File:** `{spec_path}`"


# ---------------------------------------------------------------------------
# 7.1.5 — Use Case Diagram (PlantUML)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def generate_use_case_diagram(
    project_id: str,
    system_boundary: str,
    diagram_name: str = "",
) -> str:
    """
    BABOK 7.1 — Generates a PlantUML Use Case Diagram from all UCs in repository 5.1.
    ADR-025: PlantUML notation.

    Reads all requirements of type 'use_case' from repository 5.1 and builds a summary diagram.
    Actors are extracted from the UC specification files (if available).

    Args:
        project_id:      Project identifier.
        system_boundary: Name of the system/subsystem (the rectangle on the diagram).
        diagram_name:    Diagram file name (without extension). Default: {project_id}_uc.

    Returns:
        PlantUML diagram code + path to the .puml file.
    """
    logger.info(f"generate_use_case_diagram: '{project_id}'")

    repo = _load_repo(project_id)
    use_cases = [r for r in repo["requirements"] if r.get("type") == "use_case"]

    if not use_cases:
        return (
            f"⚠️ Repository for project `{project_id}` has no Use Cases.\n"
            f"First create Use Cases with `create_use_case`."
        )

    name = diagram_name or f"{project_id.lower().replace(' ', '_')}_uc"

    # Generate PlantUML
    puml_lines = [
        f"@startuml {name}",
        "left to right direction",
        "skinparam packageStyle rectangle",
        "skinparam actorStyle awesome",
        "skinparam backgroundColor #FFFFFF",
        "skinparam usecase {",
        "  BackgroundColor #FAFAFA",
        "  BorderColor #AAAAAA",
        "}",
        "",
        f'title Use Case Diagram — {system_boundary}',
        "",
    ]

    # Try to extract actors from the specification files
    actors = set()
    uc_actor_map = {}  # uc_id -> primary_actor

    specs_dir = _specs_dir(project_id)
    for uc in use_cases:
        uc_id = uc["id"]
        # Look for the specification file
        pattern = os.path.join(specs_dir, f"{uc_id.lower().replace('-', '_')}*.md")
        matches = glob.glob(pattern)
        if matches:
            try:
                with open(matches[0], "r", encoding="utf-8") as f:
                    spec_content = f.read()
                # Simple parsing of the primary actor from the table
                for line in spec_content.split("\n"):
                    if "Actor (primary)" in line:
                        parts = line.split("|")
                        if len(parts) >= 3:
                            actor = parts[2].strip()
                            if actor and actor != "Value":
                                actors.add(actor)
                                uc_actor_map[uc_id] = actor
            except (IOError, IndexError):
                pass

    if not actors:
        actors = {"User"}  # fallback
        for uc in use_cases:
            uc_actor_map[uc["id"]] = "User"

    # Declare actors
    actor_aliases = {}
    for i, actor in enumerate(sorted(actors)):
        alias = f"A{i + 1}"
        actor_aliases[actor] = alias
        puml_lines.append(f'actor "{actor}" as {alias}')

    puml_lines.append("")

    # System rectangle
    puml_lines.append(f'rectangle "{system_boundary}" {{')

    for uc in use_cases:
        uc_alias = uc["id"].replace("-", "")
        puml_lines.append(f'    usecase "{uc["title"]}" as {uc_alias}')

    puml_lines.append("}")
    puml_lines.append("")

    # Actor -> UC links
    for uc in use_cases:
        uc_id = uc["id"]
        actor = uc_actor_map.get(uc_id, sorted(actors)[0])
        actor_alias = actor_aliases.get(actor, "A1")
        uc_alias = uc_id.replace("-", "")
        puml_lines.append(f"{actor_alias} --> {uc_alias}")

    puml_lines.append("")
    puml_lines.append("@enduml")

    puml_content = "\n".join(puml_lines)

    # Save .puml
    puml_filename = f"uc_diagram_{name}.puml"
    puml_path = _save_spec(puml_content, project_id, puml_filename)

    result_lines = [
        f"<!-- BABOK 7.1 — Use Case Diagram | Project: {project_id} | {date.today()} -->",
        "",
        f"# Use Case Diagram — {system_boundary}",
        "",
        f"**Project:** {project_id}  ",
        f"**Use Cases on the diagram:** {len(use_cases)}  ",
        f"**Actors:** {', '.join(sorted(actors))}  ",
        f"**Diagram file:** `{puml_path}`  ",
        f"**Date:** {date.today()}",
        "",
        "---",
        "",
        "## PlantUML code",
        "",
        "```plantuml",
        puml_content,
        "```",
        "",
        "---",
        "",
        "## How to render",
        "",
        "1. **PlantUML Online:** https://www.plantuml.com/plantuml/uml/",
        "2. **VS Code:** the \"PlantUML\" extension (jebbs.plantuml)",
        "3. **CLI:** `plantuml " + puml_path + "`",
        "",
        "---",
        "",
        "## Use Cases on the diagram",
        "",
        "| ID | Title | Status |",
        "|----|----------|--------|",
    ]

    for uc in use_cases:
        result_lines.append(f"| `{uc['id']}` | {uc['title']} | {uc.get('status', 'draft')} |")

    result = "\n".join(result_lines)
    save_artifact(result, prefix="7_1_uc_diagram", project_id=project_id)
    return result


# ---------------------------------------------------------------------------
# 7.1.6 — Business Process (ADR-024: .md + .puml)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def create_business_process(
    project_id: str,
    bp_id: str,
    title: str,
    process_owner: str,
    trigger: str,
    outcome: str,
    participants: str,
    steps: str,
    priority: str = "Medium",
    business_rules: str = "",
    metrics: str = "",
    exceptions: str = "",
    source_artifact: str = "",
    business_goal_ids_json: str = "[]",
) -> str:
    """
    BABOK 7.1 — Creates a business process description.
    ADR-024: generates TWO files — a textual description .md and an Activity Diagram .puml.
    Automatically registers it in repository 5.1 (status draft). ADR-022.

    Args:
        project_id:      Project identifier.
        bp_id:           Process ID: BP-001, BP-002.
        title:           Process name: "Application life cycle".
        process_owner:   Role/department responsible for the process.
        trigger:         Event that starts the process.
        outcome:         Result of successful process completion.
        participants:    Process participants, comma-separated (roles/systems).
        steps:           Process steps. Format: "1. Role: action\\n2. Role: action".
                         Branches: "2a. If [condition]: → step X. 2b. Otherwise: → step Y."
        priority:        High | Medium | Low.
        business_rules:  Business rules and constraints of the process.
        metrics:         Metrics: time, conversion, cost.
        exceptions:      Exceptional situations and error handling.
        source_artifact: Path to the 4.3 artifact.
        business_goal_ids_json: JSON list of 6.2 business objective IDs this item serves:
                         ["BG-001", "BG-002"]. Writes `satisfies` links into the 5.1 graph —
                         that is what makes per-objective coverage in `build_coverage_matrix`
                         precise. Empty — no links.

    Returns:
        Markdown process artifact + PlantUML Activity Diagram + confirmation of registration in 5.1.
    """
    logger.info(f"create_business_process: {bp_id} in project '{project_id}'")

    # Parsed BEFORE the artifacts are written, so a rejected call leaves no orphan files.
    goal_ids, goal_err = parse_json_str_list(
        business_goal_ids_json, "business_goal_ids_json", example='["BG-001"]')
    if goal_err:
        return goal_err

    # --- Textual description .md ---
    participants_list = [p.strip() for p in participants.split(",") if p.strip()]

    md_lines = [
        f"<!-- BABOK 7.1 — Business Process | Project: {project_id} | {date.today()} -->",
        "",
        f"# {bp_id} — {title}",
        "",
        "| Attribute | Value |",
        "|---------|----------|",
        f"| Type | Business Process |",
        f"| Project | {project_id} |",
        f"| Source | {source_artifact or '—'} |",
        f"| Priority | {priority} |",
        f"| Status | draft |",
        f"| Version | 1.0 |",
        f"| Date | {date.today()} |",
        "",
        "---",
        "",
        "## General information",
        "",
        "| Attribute | Value |",
        "|---------|----------|",
        f"| Process owner | {process_owner} |",
        f"| Trigger | {trigger} |",
        f"| Result | {outcome} |",
        f"| Participants | {', '.join(participants_list)} |",
        "",
        "## Process steps",
        "",
        steps,
    ]

    if business_rules:
        md_lines += ["", "## Business rules", "", business_rules]

    if metrics:
        md_lines += ["", "## Process metrics", "", metrics]

    if exceptions:
        md_lines += ["", "## Exceptions and abnormal situations", "", exceptions]

    md_lines += [
        "",
        "---",
        "",
        "## Related diagram",
        "",
        f"Activity Diagram: `{bp_id.lower().replace('-', '_')}_{title.lower().replace(' ', '_')[:20]}.puml`",
        "",
        "To render: https://www.plantuml.com/plantuml/uml/",
    ]

    md_content = "\n".join(md_lines)

    # --- PlantUML Activity Diagram .puml ---
    # ADR-024: generate from the steps of the textual description
    # Simple structure: swimlanes for participants + steps from steps
    puml_name = f"{bp_id.lower().replace('-', '_')}_{title.lower().replace(' ', '_')[:20]}"

    puml_lines = [
        f"@startuml {puml_name}",
        "skinparam activityArrowColor #666666",
        "skinparam activityBackgroundColor #FAFAFA",
        "skinparam activityBorderColor #AAAAAA",
        "skinparam backgroundColor #FFFFFF",
        "",
        f"title Activity Diagram — {title}",
        "",
    ]

    # Swimlanes for participants
    if participants_list:
        first_participant = participants_list[0]
        puml_lines.append(f"|{first_participant}|")
    else:
        puml_lines.append("|Participant|")

    puml_lines.append("start")
    puml_lines.append("")

    # Add the trigger and the steps
    puml_lines.append(f":{trigger};")
    puml_lines.append("")

    # Parse steps — each line starting with a digit is added as an activity
    current_swimlane = participants_list[0] if participants_list else "Participant"
    step_count = 0
    for line in steps.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Look for a participant change (format "1. Role: action")
        if ". " in line and ":" in line:
            parts = line.split(":", 1)
            if len(parts) == 2:
                # Try to determine the participant
                step_part = parts[0]
                # Strip the step number
                for p in participants_list:
                    if p.lower() in step_part.lower():
                        if p != current_swimlane:
                            current_swimlane = p
                            puml_lines.append(f"|{p}|")
                        break

                action = parts[1].strip()
                if action:
                    puml_lines.append(f":{action};")
                    step_count += 1
        elif line.startswith(("2a", "2b", "3a", "3b")) or "If" in line or "if" in line:
            # Simplified branch handling — as a text note
            note = line.lstrip("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ. ")
            if note:
                puml_lines.append(f"note right: {note[:50]}")

    if step_count == 0:
        # Fallback: simply add the outcome as the final state
        puml_lines.append(f":{outcome};")

    puml_lines.append("")
    puml_lines.append("stop")
    puml_lines.append("@enduml")

    puml_content = "\n".join(puml_lines)

    # Save both files
    safe_id = bp_id.lower().replace("-", "_")
    safe_title = title.lower().replace(" ", "_")[:30]

    md_filename = f"{safe_id}_{safe_title}.md"
    puml_filename = f"{safe_id}_{safe_title}.puml"

    md_path = _save_spec(md_content, project_id, md_filename)
    puml_path = _save_spec(puml_content, project_id, puml_filename)

    # ADR-022: auto-registration in 5.1
    reg_note = _register_in_repo(project_id, bp_id, "business_process", title, md_path, priority, goal_ids)

    result = (
        md_content
        + f"\n\n---\n\n## PlantUML Activity Diagram\n\n```plantuml\n{puml_content}\n```"
        + f"\n\n---\n\n**Registration in 5.1:** {reg_note}"
        + f"\n**Files:** `{md_path}`, `{puml_path}`"
    )

    return result


# ---------------------------------------------------------------------------
# 7.1.7 — Data Dictionary
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def create_data_dictionary(
    project_id: str,
    dd_id: str,
    title: str,
    entities_json: str,
    source_artifact: str = "",
    business_goal_ids_json: str = "[]",
) -> str:
    """
    BABOK 7.1 — Creates a Data Dictionary: a registry of entities with attributes, types and constraints.
    Automatically registers it in repository 5.1 (status draft). ADR-022.

    Args:
        project_id:      Project identifier.
        dd_id:           Artifact ID: DD-001.
        title:           Name: "Entities of the application system".
        entities_json:   JSON list of entities. Format:
                         [
                           {
                             "name": "Application",
                             "description": "Loan application",
                             "attributes": [
                               {
                                 "name": "id",
                                 "type": "Integer",
                                 "required": true,
                                 "constraints": "PK, AUTO_INCREMENT",
                                 "description": "Unique identifier"
                               }
                             ],
                             "business_rules": ["Rule 1", "Rule 2"]
                           }
                         ]
        source_artifact: Path to the 4.3 artifact.
        business_goal_ids_json: JSON list of 6.2 business objective IDs this item serves:
                         ["BG-001", "BG-002"]. Writes `satisfies` links into the 5.1 graph —
                         that is what makes per-objective coverage in `build_coverage_matrix`
                         precise. Empty — no links.

    Returns:
        Markdown Data Dictionary + confirmation of registration in 5.1.
    """
    logger.info(f"create_data_dictionary: {dd_id} in project '{project_id}'")

    # Parsed BEFORE the artifact is written, so a rejected call leaves no orphan file.
    goal_ids, goal_err = parse_json_str_list(
        business_goal_ids_json, "business_goal_ids_json", example='["BG-001"]')
    if goal_err:
        return goal_err

    try:
        entities = json.loads(entities_json)
        if not isinstance(entities, list) or len(entities) == 0:
            raise ValueError("Must be a non-empty list")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Error parsing entities_json: {e}\n"
            f"Expected a JSON list of entities. See an example in references/templates.md."
        )

    lines = [
        f"<!-- BABOK 7.1 — Data Dictionary | Project: {project_id} | {date.today()} -->",
        "",
        f"# {dd_id} — {title}",
        "",
        "| Attribute | Value |",
        "|---------|----------|",
        f"| Type | Data Dictionary |",
        f"| Project | {project_id} |",
        f"| Source | {source_artifact or '—'} |",
        f"| Entities | {len(entities)} |",
        f"| Status | draft |",
        f"| Version | 1.0 |",
        f"| Date | {date.today()} |",
        "",
        "---",
    ]

    for entity in entities:
        name = entity.get("name", "Unnamed")
        description = entity.get("description", "")
        attributes = entity.get("attributes", [])
        rules = entity.get("business_rules", [])

        lines += [
            "",
            f"## Entity: {name}",
            "",
        ]

        if description:
            lines += [f"**Description:** {description}", ""]

        if attributes:
            lines += [
                "| Attribute | Data type | Required | Constraints | Description |",
                "|---------|-----------|--------------|-------------|----------|",
            ]
            for attr in attributes:
                attr_name = attr.get("name", "—")
                attr_type = attr.get("type", "—")
                required = "Yes" if attr.get("required", False) else "No"
                constraints = attr.get("constraints", "—")
                attr_desc = attr.get("description", "—")
                lines.append(f"| `{attr_name}` | {attr_type} | {required} | {constraints} | {attr_desc} |")
        else:
            lines.append("_No attributes specified._")

        if rules:
            lines += ["", "**Business rules:**"]
            for rule in rules:
                lines.append(f"- {rule}")

        lines.append("")

    lines += [
        "---",
        "",
        "## Traceability",
        "",
        "| Link | Artifact |",
        "|-------|----------|",
        f"| Source (4.3) | {source_artifact or '—'} |",
        f"| Registry (5.1) | automatic registration |",
    ]

    content = "\n".join(lines)

    safe_id = dd_id.lower().replace("-", "_")
    safe_title = title.lower().replace(" ", "_")[:30]
    filename = f"{safe_id}_{safe_title}.md"
    spec_path = _save_spec(content, project_id, filename)

    reg_note = _register_in_repo(project_id, dd_id, "data_dictionary", title, spec_path, "Medium", goal_ids)

    return content + f"\n\n---\n\n**Registration in 5.1:** {reg_note}\n**File:** `{spec_path}`"


# ---------------------------------------------------------------------------
# 7.1.8 — ERD (.md + .puml)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def create_erd(
    project_id: str,
    erd_id: str,
    title: str,
    entities_json: str,
    relations_json: str,
    source_artifact: str = "",
    business_goal_ids_json: str = "[]",
) -> str:
    """
    BABOK 7.1 — Creates a description of entities and relationships + PlantUML ER Diagram (.puml).
    ADR-025: PlantUML notation.
    Automatically registers it in repository 5.1 (status draft). ADR-022.

    Args:
        project_id:      Project identifier.
        erd_id:          Artifact ID: ERD-001.
        title:           Name: "Core CRM entities".
        entities_json:   JSON list of entities. Format:
                         [
                           {
                             "name": "Application",
                             "pk": "id",
                             "attributes": ["client_id FK", "status Enum", "created_at DateTime"]
                           }
                         ]
        relations_json:  JSON list of relationships. Format:
                         [
                           {
                             "from": "Application",
                             "to": "Client",
                             "cardinality": "many-to-one",
                             "label": "belongs to"
                           }
                         ]
                         Allowed cardinality:
                         one-to-one | one-to-many | many-to-one | many-to-many |
                         zero-or-one-to-many | zero-or-one-to-one
        source_artifact: Path to the 4.3 artifact.
        business_goal_ids_json: JSON list of 6.2 business objective IDs this item serves:
                         ["BG-001", "BG-002"]. Writes `satisfies` links into the 5.1 graph —
                         that is what makes per-objective coverage in `build_coverage_matrix`
                         precise. Empty — no links.

    Returns:
        Markdown ERD description + PlantUML code + confirmation of registration in 5.1.
    """
    logger.info(f"create_erd: {erd_id} in project '{project_id}'")

    # Parsed BEFORE the artifacts are written, so a rejected call leaves no orphan files.
    goal_ids, goal_err = parse_json_str_list(
        business_goal_ids_json, "business_goal_ids_json", example='["BG-001"]')
    if goal_err:
        return goal_err

    try:
        entities = json.loads(entities_json)
        if not isinstance(entities, list) or len(entities) == 0:
            raise ValueError("Must be a non-empty list")
    except (json.JSONDecodeError, ValueError) as e:
        return f"❌ Error parsing entities_json: {e}"

    try:
        relations = json.loads(relations_json)
        if not isinstance(relations, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        relations = []

    # PlantUML cardinality notation
    cardinality_map = {
        "one-to-one": "||--||",
        "one-to-many": "||--o{",
        "many-to-one": "}o--||",
        "many-to-many": "}o--o{",
        "zero-or-one-to-many": "|o--o{",
        "zero-or-one-to-one": "|o--o|",
    }

    # --- PlantUML ERD ---
    puml_name = f"{erd_id.lower().replace('-', '_')}_{title.lower().replace(' ', '_')[:20]}"
    puml_lines = [
        f"@startuml {puml_name}",
        "hide methods",
        "hide stereotypes",
        "",
        "skinparam classBackgroundColor #FAFAFA",
        "skinparam classBorderColor #AAAAAA",
        "skinparam backgroundColor #FFFFFF",
        "",
        f'title ERD — {title}',
        "",
    ]

    for entity in entities:
        name = entity.get("name", "Entity")
        pk = entity.get("pk", "id")
        attrs = entity.get("attributes", [])

        puml_lines += [
            f'entity "{name}" as {name} {{',
            f"  + {pk} : Integer [PK]",
            "  --",
        ]
        for attr in attrs:
            puml_lines.append(f"  {attr}")
        puml_lines.append("}")
        puml_lines.append("")

    for rel in relations:
        from_e = rel.get("from", "")
        to_e = rel.get("to", "")
        card = rel.get("cardinality", "one-to-many")
        label = rel.get("label", "")
        notation = cardinality_map.get(card, "||--o{")

        if label:
            puml_lines.append(f'{from_e} {notation} {to_e} : "{label}"')
        else:
            puml_lines.append(f"{from_e} {notation} {to_e}")

    puml_lines.append("")
    puml_lines.append("@enduml")
    puml_content = "\n".join(puml_lines)

    # --- Markdown description ---
    md_lines = [
        f"<!-- BABOK 7.1 — ERD | Project: {project_id} | {date.today()} -->",
        "",
        f"# {erd_id} — {title}",
        "",
        "| Attribute | Value |",
        "|---------|----------|",
        f"| Type | ERD |",
        f"| Project | {project_id} |",
        f"| Source | {source_artifact or '—'} |",
        f"| Entities | {len(entities)} |",
        f"| Relationships | {len(relations)} |",
        f"| Status | draft |",
        f"| Version | 1.0 |",
        f"| Date | {date.today()} |",
        "",
        "---",
        "",
        "## Entities",
        "",
        "| Entity | PK | Attributes |",
        "|----------|----|----------|",
    ]

    for entity in entities:
        name = entity.get("name", "—")
        pk = entity.get("pk", "id")
        attrs = ", ".join(entity.get("attributes", []))
        md_lines.append(f"| **{name}** | `{pk}` | {attrs or '—'} |")

    if relations:
        md_lines += [
            "",
            "## Relationships",
            "",
            "| From | To | Cardinality | Description |",
            "|----|---|----------------|----------|",
        ]
        for rel in relations:
            md_lines.append(
                f"| `{rel.get('from', '—')}` | `{rel.get('to', '—')}` | "
                f"{rel.get('cardinality', '—')} | {rel.get('label', '—')} |"
            )

    md_lines += [
        "",
        "---",
        "",
        "## Traceability",
        "",
        "| Link | Artifact |",
        "|-------|----------|",
        f"| Source (4.3) | {source_artifact or '—'} |",
        f"| Registry (5.1) | automatic registration |",
    ]

    md_content = "\n".join(md_lines)

    # Save both files
    safe_id = erd_id.lower().replace("-", "_")
    safe_title = title.lower().replace(" ", "_")[:30]

    md_filename = f"{safe_id}_{safe_title}.md"
    puml_filename = f"{safe_id}_{safe_title}.puml"

    md_path = _save_spec(md_content, project_id, md_filename)
    puml_path = _save_spec(puml_content, project_id, puml_filename)

    reg_note = _register_in_repo(project_id, erd_id, "erd", title, md_path, "Medium", goal_ids)

    result = (
        md_content
        + f"\n\n---\n\n## PlantUML ER Diagram\n\n```plantuml\n{puml_content}\n```"
        + f"\n\n---\n\n**Registration in 5.1:** {reg_note}"
        + f"\n**Files:** `{md_path}`, `{puml_path}`"
    )
    return result


# ---------------------------------------------------------------------------
# 7.1.9 — Coverage Matrix
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def build_coverage_matrix(
    project_id: str,
) -> str:
    """
    BABOK 7.1 — Builds a "business objective → requirements" coverage matrix.

    Business objectives come from 6.2 (Define Future State), in this order: the
    `business_goal` nodes 6.2 registers in the 5.1 graph, then `future_state_goals.json`,
    then a legacy hand-written "Business objectives" section in the 4.3 artifact, then
    grouping by source artifact. Requirements come from repository 5.1.

    Two modes, chosen by whether the objectives carry graph ids:

      PRECISE — objectives are `business_goal` nodes. Coverage is computed by traversing
        the `satisfies` links the BA declares (7.1 creating tools, or `add_trace_link` in
        5.1); `derives` links to an objective are counted too. The per-objective flags are
        real claims backed by edges.
      DEGRADED — objectives came from `future_state_goals.json`, a legacy 4.3 section, or
        grouping by source. That is text without ids, so no per-objective claim is made:
        the objectives are shown as a checklist and the report says so. A mapping is never
        inferred from text — doing that was audit finding 7.1-B.

    Flags (precise mode only):
      🔴 Business objective not covered by any requirement
      🟡 Business objective covered by 10+ requirements (possible over-engineering)
      🟢 Normal coverage (1–9 requirements)

    Args:
        project_id: Project identifier.

    Returns:
        Markdown Coverage Matrix with flags and recommendations.
    """
    logger.info(f"build_coverage_matrix: '{project_id}'")

    repo = _load_repo(project_id)
    # Archived requirements are SHOWN, MARKED and COUNTED here; what they never do is
    # count as coverage of an objective (owner's decision, 2026-08-03 — see the doctrine
    # at common.ARCHIVED_REQUIREMENT_STATUSES). Dropping them from the selection made
    # this matrix and the 5.1 documents of the same project report different sizes for
    # the same graph.
    active = list(repo["requirements"])

    if not active:
        return (
            f"⚠️ Repository for project `{project_id}` has no requirements.\n"
            f"First create requirements with the 7.1 tools."
        )

    # Objectives are the 6.2 business_goal nodes; spec requirements are everything specifiable in
    # 7.1. Exclude the goal/need/business roots so they don't inflate the requirement count or
    # show up in the requirements list.
    goal_nodes = [r for r in active if r.get("type") == "business_goal"]
    requirements = [
        r for r in active
        if r.get("type") not in NON_SPEC_NODE_TYPES
    ]

    # C1 (audit finding 7.1-C): the REAL source of business objectives is 6.2 (Define Future
    # State), NOT the 4.3 confirmed artifact — which holds requirements/rules/issues, never a
    # business-objectives section. 6.2 registers each goal as a `business_goal` node in the 5.1
    # graph AND stores it in future_state_goals.json. Prefer the graph nodes (canonical, and what
    # a future per-goal traceability pass would traverse), then the 6.2 file, then a legacy
    # "Business objectives" section written into the 4.3 artifact by hand, then group-by-source.
    #
    # A1: when the objectives ARE graph nodes they carry an id, and the id is what makes
    # precise per-objective traversal possible. The other three sources yield text only —
    # there is no honest way to attach a requirement to a bare string, so the tool degrades
    # to the C1 checklist instead of guessing.
    business_goals = []
    goal_entries = []   # (goal_id, title); goal_id is "" in degraded mode
    precise = False
    source_info = ""

    if goal_nodes:
        goal_entries = [(g["id"], g.get("title") or g["id"]) for g in goal_nodes]
        business_goals = [t for _, t in goal_entries]
        precise = True
        source_info = "📂 Business objectives from the 6.2 goals registered in the 5.1 graph (business_goal nodes)."

    if not business_goals:
        fs_goals = _load_future_state_goals(project_id)
        if fs_goals:
            business_goals = fs_goals
            source_info = "📂 Business objectives from 6.2 `future_state_goals.json`."

    if not business_goals:
        artifact_path = _find_confirmed_artifact(project_id)
        if artifact_path:
            try:
                content = _read_confirmed_artifact(artifact_path)
                source_info = f"📂 Business objectives extracted from the 4.3 artifact: `{artifact_path}`"
                # Simple parsing: look for the section with business objectives
                in_goals_section = False
                for line in content.split("\n"):
                    line_stripped = line.strip()
                    lower = line_stripped.lower()
                    if any(kw in lower for kw in ["business objective", "business goal", "project objectives", "objectives:"]):
                        in_goals_section = True
                        continue
                    if in_goals_section:
                        if line_stripped.startswith("#"):
                            in_goals_section = False
                            continue
                        if line_stripped.startswith("-") or (
                            line_stripped and line_stripped[0].isdigit() and ". " in line_stripped
                        ):
                            goal = line_stripped.lstrip("-•*0123456789. ").strip()
                            if len(goal) > 5:
                                business_goals.append(goal)
            except IOError:
                pass

    if not business_goals:
        # Fallback: synthetic "objectives" from the requirements' source_artifact
        source_artifacts = set()
        for r in requirements:
            sa = r.get("source_artifact", "")
            if sa:
                source_artifacts.add(sa)

        if source_artifacts:
            business_goals = [f"Objectives from: {sa}" for sa in sorted(source_artifacts)]
            source_info = "📋 No 6.2 goals and no 4.3 objectives found. Showing grouping by requirement source."
        else:
            business_goals = ["Business objectives not defined"]
            source_info = "⚠️ No business objectives found. Define them in 6.2 (`define_goals_and_objectives`) or run `analyze_elicitation_context`."

    if not precise:
        goal_entries = [("", t) for t in business_goals]

    # A1 coverage. Per-objective claims are made ONLY from real edges in the 5.1 graph.
    # The original defect (finding 7.1-B) compared a file PATH (source_artifact) against
    # goal TEXT, so every requirement fell into the FIRST objective and all the others were
    # falsely flagged uncovered. Nothing here infers a mapping from text — an objective is
    # covered when a requirement points at its NODE, and not otherwise.
    total_reqs = len(requirements)
    num_goals = len(business_goals)
    avg_per_goal = total_reqs / max(1, num_goals)
    over_engineering = avg_per_goal >= 10  # global heuristic, kept for the degraded mode

    links = repo.get("links", [])
    req_ids = {r["id"] for r in requirements}
    # Read BOTH relations: A1 writes `satisfies` (ADR-082), but a BA may have linked
    # manually with `derives` via add_trace_link (5.1), and ignoring that encoding would
    # silently under-report coverage.
    goal_link_relations = ("satisfies", "derives")

    per_goal = {}              # goal_id -> [req_id, ...]
    linked_req_ids = set()     # requirements attached to a displayed objective
    need_only_req_ids = set()  # attached to a business_need/business root only

    if precise:
        goal_ids_set = {gid for gid, _ in goal_entries}
        need_ids = {
            r["id"] for r in active
            if r.get("type") in ("business_need", "business")
        }
        per_goal = {gid: [] for gid in goal_ids_set}
        archived_req_ids = {r["id"] for r in requirements if is_archived(r)}
        for lnk in links:
            if lnk.get("relation") not in goal_link_relations:
                continue
            frm, to = lnk.get("from"), lnk.get("to")
            if frm not in req_ids:
                continue
            # An archived requirement is not evidence that its objective is served: it
            # was withdrawn. It stays in the registry table below, marked.
            if frm in archived_req_ids:
                continue
            if to in goal_ids_set:
                if frm not in per_goal[to]:
                    per_goal[to].append(frm)
                linked_req_ids.add(frm)
            elif to in need_ids:
                need_only_req_ids.add(frm)
        need_only_req_ids -= linked_req_ids

    unattached = [
        r for r in requirements
        if r["id"] not in linked_req_ids and r["id"] not in need_only_req_ids
        and not is_archived(r)
    ]
    archived_reqs = [r for r in requirements if is_archived(r)]
    by_id = {r["id"]: r for r in active}

    lines = [
        f"<!-- BABOK 7.1 — Coverage Matrix | Project: {project_id} | {date.today()} -->",
        "",
        f"# 📊 Requirements coverage matrix",
        "",
        f"**Project:** {project_id}  ",
        f"**Date:** {date.today()}  ",
        f"**Objectives source:** {source_info}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|------------|----------|",
        f"| Business objectives | {num_goals} |",
        f"| Requirements in the registry | {total_reqs} |",
        f"| — of them archived (5.2) | {len(archived_reqs)} |",
        f"| Avg requirements per objective | {avg_per_goal:.1f} |",
    ]

    if precise:
        covered_count = sum(1 for gid in per_goal if per_goal[gid])
        lines += [
            f"| Objectives covered | {covered_count} of {num_goals} |",
            "",
            "> **Per-objective coverage is computed from `satisfies` links in the 5.1 graph.** "
            "A requirement appears under an objective only because the analyst linked it there — "
            "nothing is inferred from text.",
            "",
            "## Coverage by business objective",
            "",
            "| | Objective | Requirements | IDs |",
            "|---|-----------|--------------|-----|",
        ]
        for gid, title in goal_entries:
            covered = per_goal.get(gid, [])
            if not covered:
                flag = "🔴"
            elif len(covered) >= 10:
                flag = "🟡"
            else:
                flag = "🟢"
            title_short = title[:70] + "..." if len(title) > 70 else title
            ids = ", ".join(f"`{i}`" for i in covered) if covered else "—"
            mark = archived_suffix(by_id.get(gid))
            lines.append(
                f"| {flag} | `{gid}` {title_short}{mark} | {len(covered)} | {ids} |")
        lines += [
            "",
            "> 🔴 no requirement serves this objective &nbsp;|&nbsp; 🟢 1–9 &nbsp;|&nbsp; "
            "🟡 10+ (possible over-engineering)",
            "",
        ]
    else:
        lines += [
            "",
            "> **Objectives came from a source without graph ids**, so per-objective coverage "
            "cannot be computed and none is claimed. Define objectives in 6.2 "
            "(`define_goals_and_objectives`) — they are registered as graph nodes, and linking "
            "requirements to them (the `business_goal_ids_json` parameter of the 7.1 creating "
            "tools) turns this report into a precise per-objective matrix.",
            "",
            "## Business objectives — checklist",
            "",
            "> Confirm by eye that each objective is addressed by at least one requirement in the list below.",
            "",
        ]
        for goal in business_goals:
            goal_short = goal[:80] + "..." if len(goal) > 80 else goal
            lines.append(f"- [ ] {goal_short}")
        lines.append("")

    lines += [
        "## Requirements in the registry",
        "",
        "| ID | Type | Title |",
        "|----|------|-------|",
    ]
    for req in requirements:
        lines.append(f"| `{req['id']}` | {req.get('type', '—')} | {req.get('title', '—')}"
                     f"{archived_suffix(req)} |")

    # Precise mode ONLY. In degraded mode nothing is linked because nothing CAN be linked,
    # so listing every requirement as unattached would be exactly the kind of false claim
    # this report exists to avoid.
    if precise and unattached:
        by_type = {}
        for r in unattached:
            by_type.setdefault(r.get("type", "—"), []).append(r["id"])
        lines += ["", "## Requirements not linked to any objective", ""]
        for rtype in sorted(by_type):
            ids = ", ".join(f"`{i}`" for i in sorted(by_type[rtype]))
            lines.append(f"- **{rtype}** ({len(by_type[rtype])}): {ids}")
        lines += [
            "",
            "> Supporting models (data dictionary, ERD) are normally left unlinked — they "
            "describe the solution rather than serve an objective directly.",
        ]

    if need_only_req_ids:
        ids = ", ".join(f"`{i}`" for i in sorted(need_only_req_ids))
        lines += [
            "",
            f"> **Traced to a business need, not to an objective:** {ids}. "
            f"This usually means 6.2 has not yet refined that need into objectives.",
        ]

    lines += [
        "",
        "---",
        "",
        "## Signals & recommendations",
        "",
    ]
    if precise:
        uncovered = [f"`{gid}`" for gid, _ in goal_entries if not per_goal.get(gid)]
        if uncovered:
            lines.append(
                f"- 🔴 **{len(uncovered)} objective(s) with no requirement:** "
                f"{', '.join(uncovered)}. Either specify requirements for them, or "
                f"link existing ones via the 7.1 creating tools / `add_trace_link` (5.1)."
            )
        crowded = [f"`{gid}`" for gid, _ in goal_entries if len(per_goal.get(gid, [])) >= 10]
        if crowded:
            lines.append(
                f"- 🟡 **Possible over-engineering:** {', '.join(crowded)} carry 10+ "
                f"requirements each. Check for duplicates via `check_coverage` (5.1)."
            )
    elif over_engineering:
        lines.append(
            f"- 🟡 **Possible over-engineering / duplication:** {total_reqs} requirements for "
            f"{num_goals} business objective(s) (avg {avg_per_goal:.1f} per objective). "
            f"Check for duplicates via `check_coverage` (5.1)."
        )
    lines.append(
        "- ✅ **Next:** confirm every objective is addressed, then run "
        "verification (7.2) and validation (7.3)."
    )
    lines.append(
        "- ℹ️ For full per-requirement traceability (sources, implementation, tests) run "
        "`check_coverage` (5.1)."
    )

    content = "\n".join(lines)
    save_artifact(content, prefix="7_1_coverage_matrix", project_id=project_id)
    return content


if __name__ == "__main__":
    mcp.run()
