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
from skills.common import save_artifact, logger, DATA_DIR, data_path, normalize_project_id, specs_dir

mcp = FastMCP("BABOK_Requirements_Spec")

REPO_FILENAME = "traceability_repo.json"
CONFIRMED_GLOB = "4_3_*_confirmed*.md"


# ---------------------------------------------------------------------------
# Utilities — repository 5.1
# ---------------------------------------------------------------------------

def _repo_path(project_id: str) -> str:
    safe = normalize_project_id(project_id)
    return data_path(project_id, f"{safe}_{REPO_FILENAME}")


def _load_repo(project_id: str) -> dict:
    path = _repo_path(project_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
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
                      title: str, source_artifact: str, priority: str = "Medium") -> str:
    """
    ADR-022: registers a requirement in repository 5.1 with status draft.
    If a requirement with this ID already exists — skips it (without an error).
    Returns a marker string to include in the artifact.
    """
    repo = _load_repo(project_id)
    existing_ids = {r["id"] for r in repo["requirements"]}

    if req_id in existing_ids:
        logger.info(f"_register_in_repo: {req_id} already in repository, skipping")
        return f"ℹ️ `{req_id}` is already registered in repository 5.1."

    entry = {
        "id": req_id,
        "type": req_type,
        "title": title,
        "version": "1.0",
        "status": "draft",
        "priority": priority,
        "owner": "",
        "stability": "Unknown",
        "source_artifact": source_artifact,
        "added": str(date.today()),
        "last_reviewed": str(date.today()),
    }
    repo["requirements"].append(entry)
    repo["history"].append({
        "action": "requirement_added",
        "req_id": req_id,
        "source": "7.1_spec",
        "date": str(date.today()),
    })
    _save_repo(repo)
    return f"✅ `{req_id}` registered in repository 5.1 (status: draft)."


# ---------------------------------------------------------------------------
# Utilities — file system
# ---------------------------------------------------------------------------

def _specs_dir(project_id: str) -> str:
    # issue #1: specs live in data/<project>/specs/, with a fallback to legacy layouts.
    # Single source of truth — common.specs_dir.
    return specs_dir(project_id)


def _save_spec(content: str, project_id: str, filename: str) -> str:
    """Saves an artifact to governance_plans/{project_id}_specs/. Returns the path."""
    specs_dir = _specs_dir(project_id)
    os.makedirs(specs_dir, exist_ok=True)
    filepath = os.path.join(specs_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"Specification saved: {filepath}")
    return filepath


def _find_confirmed_artifact(project_id: str) -> Optional[str]:
    """
    ADR-023: finds the latest confirmed 4.3 artifact for project_id.

    The 4.3 producer (save_confirmed_elicitation_result -> save_artifact) writes the report to
      reports/<project_id>/4_3_confirmed_result_<timestamp>.md
    i.e. project_id is the FOLDER name, and the filename itself does NOT contain project_id.
    The previous implementation searched only flat data/ with masks that REQUIRED project_id
    inside the filename, so it never matched the real artifact (audit finding 7.1-A). Search the
    real per-project reports/ layout first, then fall back to legacy layouts for older projects
    and test fixtures.
    """
    from skills.common import report_dir_for, REPORTS_DIR
    legacy_safe = project_id.lower().replace(" ", "_")
    patterns = [
        # canonical: per-project reports folder (folder filters by project; filename has no pid)
        os.path.join(report_dir_for(project_id), "4_3_*confirmed*.md"),
        # legacy flat reports/ (pre per-project layout, issue #1)
        os.path.join(REPORTS_DIR, f"4_3_*{legacy_safe}*confirmed*.md"),
        os.path.join(REPORTS_DIR, "4_3_*confirmed*.md"),
        # very-legacy / test fixtures: flat data/ with project_id in the filename
        os.path.join(DATA_DIR, f"4_3_{legacy_safe}_confirmed*.md"),
        os.path.join(DATA_DIR, f"4_3_*{legacy_safe}*confirmed*.md"),
        os.path.join(DATA_DIR, "4_3_*confirmed*.md"),
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            # take the latest by modification time (filenames carry a timestamp, but mtime is
            # robust when legacy and current naming are mixed)
            return max(matches, key=os.path.getmtime)
    return None


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

    Returns:
        Markdown User Story artifact + confirmation of registration in 5.1.
    """
    logger.info(f"create_user_story: {story_id} in project '{project_id}'")

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
    reg_note = _register_in_repo(project_id, story_id, "user_story", title, spec_path, priority)

    return content + f"\n\n---\n\n**Registration in 5.1:** {reg_note}\n**File:** `{spec_path}`"


# ---------------------------------------------------------------------------
# 7.1.3 — Functional Requirement
# ---------------------------------------------------------------------------

@mcp.tool()
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

    Returns:
        Markdown requirement artifact + confirmation of registration in 5.1.
    """
    logger.info(f"create_functional_requirement: {req_id} ({req_type}) in project '{project_id}'")

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
    reg_note = _register_in_repo(project_id, req_id, repo_type_map[req_type], title, spec_path, priority)

    return content + f"\n\n---\n\n**Registration in 5.1:** {reg_note}\n**File:** `{spec_path}`"


# ---------------------------------------------------------------------------
# 7.1.4 — Use Case
# ---------------------------------------------------------------------------

@mcp.tool()
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

    Returns:
        Markdown Use Case artifact + confirmation of registration in 5.1.
    """
    logger.info(f"create_use_case: {uc_id} in project '{project_id}'")

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

    reg_note = _register_in_repo(project_id, uc_id, "use_case", title, spec_path, priority)

    return content + f"\n\n---\n\n**Registration in 5.1:** {reg_note}\n**File:** `{spec_path}`"


# ---------------------------------------------------------------------------
# 7.1.5 — Use Case Diagram (PlantUML)
# ---------------------------------------------------------------------------

@mcp.tool()
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

    Returns:
        Markdown process artifact + PlantUML Activity Diagram + confirmation of registration in 5.1.
    """
    logger.info(f"create_business_process: {bp_id} in project '{project_id}'")

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
    reg_note = _register_in_repo(project_id, bp_id, "business_process", title, md_path, priority)

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
def create_data_dictionary(
    project_id: str,
    dd_id: str,
    title: str,
    entities_json: str,
    source_artifact: str = "",
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

    Returns:
        Markdown Data Dictionary + confirmation of registration in 5.1.
    """
    logger.info(f"create_data_dictionary: {dd_id} in project '{project_id}'")

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

    reg_note = _register_in_repo(project_id, dd_id, "data_dictionary", title, spec_path)

    return content + f"\n\n---\n\n**Registration in 5.1:** {reg_note}\n**File:** `{spec_path}`"


# ---------------------------------------------------------------------------
# 7.1.8 — ERD (.md + .puml)
# ---------------------------------------------------------------------------

@mcp.tool()
def create_erd(
    project_id: str,
    erd_id: str,
    title: str,
    entities_json: str,
    relations_json: str,
    source_artifact: str = "",
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

    Returns:
        Markdown ERD description + PlantUML code + confirmation of registration in 5.1.
    """
    logger.info(f"create_erd: {erd_id} in project '{project_id}'")

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

    reg_note = _register_in_repo(project_id, erd_id, "erd", title, md_path)

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
def build_coverage_matrix(
    project_id: str,
) -> str:
    """
    BABOK 7.1 — Builds a "business objective → requirements" coverage matrix.

    Business objectives come from 6.2 (Define Future State), in this order: the
    `business_goal` nodes 6.2 registers in the 5.1 graph, then `future_state_goals.json`,
    then a legacy hand-written "Business objectives" section in the 4.3 artifact, then
    grouping by source artifact. Requirements come from repository 5.1.

    Coverage is reported per project, not per objective: the matrix does not claim which
    requirement serves which goal, because no such link exists in the graph yet. Use
    `check_coverage` (5.1) for per-requirement traceability.

    Flags:
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
    active = [
        r for r in repo["requirements"]
        if r.get("status") not in {"deprecated", "superseded", "retired"}
    ]

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
        if r.get("type") not in {"business_goal", "business_need", "business"}
    ]

    # C1 (audit finding 7.1-C): the REAL source of business objectives is 6.2 (Define Future
    # State), NOT the 4.3 confirmed artifact — which holds requirements/rules/issues, never a
    # business-objectives section. 6.2 registers each goal as a `business_goal` node in the 5.1
    # graph AND stores it in future_state_goals.json. Prefer the graph nodes (canonical, and what
    # a future per-goal traceability pass would traverse), then the 6.2 file, then a legacy
    # "Business objectives" section written into the 4.3 artifact by hand, then group-by-source.
    business_goals = []
    source_info = ""

    if goal_nodes:
        business_goals = [g["title"] for g in goal_nodes if g.get("title")]
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

    # HYBRID coverage (audit finding 7.1-B). There is NO honest per-goal link between a business
    # objective (free text extracted from the 4.3 report) and a requirement (a 5.1 node): the old
    # code compared a file PATH (source_artifact) against goal TEXT, so every requirement fell into
    # the FIRST goal and all the others were falsely flagged "uncovered". We therefore do NOT
    # fabricate a per-goal mapping. Instead we show the objectives as a checklist for the BA to
    # eyeball, list the requirements, keep a single honest GLOBAL over-engineering hint, and point
    # to check_coverage (5.1) for real graph-based traceability. Precise per-goal coverage is a
    # deferred follow-up (register objectives as graph nodes + real satisfies/derives edges).
    total_reqs = len(requirements)
    num_goals = len(business_goals)
    avg_per_goal = total_reqs / max(1, num_goals)
    over_engineering = avg_per_goal >= 10  # global heuristic, not a per-goal claim

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
        f"| Business objectives (from 4.3) | {num_goals} |",
        f"| Requirements in the registry | {total_reqs} |",
        f"| Avg requirements per objective | {avg_per_goal:.1f} |",
        "",
        "> ⚠️ Precise objective-to-requirement mapping is not available here: business objectives "
        "are free text from the 4.3 report (not graph nodes), and 7.1 requirements are not yet "
        "linked to specific objectives. For exact coverage, link the requirements to their "
        "objectives and run `check_coverage` (5.1). Per-objective traceability is a planned "
        "follow-up.",
        "",
        "## Business objectives (from 4.3) — checklist",
        "",
        "> Confirm by eye that each objective is addressed by at least one requirement in the list below.",
        "",
    ]

    for goal in business_goals:
        goal_short = goal[:80] + "..." if len(goal) > 80 else goal
        lines.append(f"- [ ] {goal_short}")

    lines += [
        "",
        "## Requirements in the registry",
        "",
        "| ID | Type | Title |",
        "|----|------|-------|",
    ]
    for req in requirements:
        lines.append(f"| `{req['id']}` | {req.get('type', '—')} | {req.get('title', '—')} |")

    lines += [
        "",
        "---",
        "",
        "## Signals & recommendations",
        "",
    ]
    if over_engineering:
        lines.append(
            f"- 🟡 **Possible over-engineering / duplication:** {total_reqs} requirements for "
            f"{num_goals} business objective(s) (avg {avg_per_goal:.1f} per objective). "
            f"Check for duplicates via `check_coverage` (5.1)."
        )
    lines.append(
        "- ✅ **Next:** confirm every objective in the checklist is addressed, then run "
        "verification (7.2) and validation (7.3)."
    )

    content = "\n".join(lines)
    save_artifact(content, prefix="7_1_coverage_matrix", project_id=project_id)
    return content


if __name__ == "__main__":
    mcp.run()
