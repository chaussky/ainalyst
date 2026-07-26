"""
BABOK 4.1 — Prepare for Elicitation
MCP tools to prepare for requirements elicitation.

Tools:
  - save_elicitation_plan      — save the elicitation plan to .md
  - create_google_form         — create a Google Form (stub, requires OAuth setup)
  - get_form_responses         — retrieve responses from a Google Form (stub)

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
from typing import Literal
from mcp.server.fastmcp import FastMCP
from skills.common import (save_artifact, logger, parse_json_dict_list,
                           update_stakeholder_registry_file,
                           load_ba_plan, planned_work_period)

mcp = FastMCP("BABOK_Elicitation_Prep")


# ---------------------------------------------------------------------------
# 4.1.1 — Save the elicitation plan
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Living stakeholder registry (ADR-003) — 4.1 seeds, 4.2 maintains, 7.4 reads
# ---------------------------------------------------------------------------

_REGISTRY_SOURCE_41 = "4.1 elicitation plan"

# Only fields the BA actually STATES about a person. `what_to_learn` is about the
# session, not the stakeholder, so it stays out of the registry.
_REGISTRY_SEED_FIELDS_41 = ("name", "role", "influence", "interest", "contact")


def _seed_registry_from_plan(project_name: str, stakeholders: list) -> str:
    """Seeds the living registry from the people this session will talk to.

    Never raises: the plan is the deliverable and is already built by the time this
    runs — a registry write that fails must not cost the BA their plan.

    Everything here is INSERT-ONLY beyond the stated fields. 4.1 PLANS an interview,
    it does not observe one, so it must never overwrite what an interview established;
    that is exactly the defect A2 found when planning re-seeded a post-default record
    and reverted an elicited attitude. 4.5 is the tool that observes change, and its
    update is deliberately not insert-only.
    """
    incoming = []
    for s in stakeholders:
        entry = {f: s.get(f) for f in _REGISTRY_SEED_FIELDS_41 if s.get(f)}
        if entry:
            incoming.append(entry)
    if not incoming:
        return ""

    try:
        result = update_stakeholder_registry_file(
            project_name, incoming, source=_REGISTRY_SOURCE_41,
            insert_defaults={
                "found_through": _REGISTRY_SOURCE_41,
                # Planned, not yet elicited. Insert-only, so a later 'Elicited' from
                # 4.2 is never reset by re-running the planning step.
                "coverage_status": "Not covered",
            },
        )
    except Exception as e:  # noqa: BLE001 — never let the plan fail on this
        logger.warning(f"4.1 could not update the stakeholder registry: {e}")
        return ("\n⚠️ Stakeholder registry not updated — "
                "the elicitation plan is saved.")

    added, updated = len(result.get("added", [])), len(result.get("updated", []))
    if not (added or updated):
        return ""
    return (f"\n📇 Stakeholder registry: +{added} new, {updated} updated "
            f"(the same registry 4.2 maintains and 7.4 reads).")


# 3.1 records techniques for the WHOLE practice (BABOK ch. 10), and only four of them
# are elicitation techniques this tool can run. Every adaptive cell of APPROACH_MATRIX
# is Backlog Management / User Stories / Retrospectives — comparing outside this
# intersection would flag EVERY agile project, the way the 4.4 schedule check claimed
# "no communication on record" because its two vocabularies could not meet.
_PLANNED_ELICITATION_TECHNIQUES = {
    "document analysis": "Document Analysis",
    "interview": "Interview", "interviews": "Interview",
    "prototyping": "Prototyping",
    "workshop": "Workshop", "workshops": "Workshop",
}


def _planned_context(project_name: str, technique: str) -> tuple:
    """(markdown_block, warning) for the 3.1 plan behind this session.

    Advisory only: a session plan must never fail because the BA plan is missing or
    damaged.
    """
    plan, note = load_ba_plan(project_name)
    if not isinstance(plan, dict):
        return "", note

    lines = []
    period = planned_work_period(plan, "4.1")
    if period:
        detail = [f"**{period['name']}**"]
        if period["effort"]:
            detail.append(f"planned effort: {period['effort']}")
        if period["when"]:
            detail.append(period["when"])
        lines.append(f"- **Planned work period (BABOK 3.1, element .3/.4):** "
                     f"{' — '.join(detail)}")

    approach = plan.get("ba_approach")
    raw_techniques = approach.get("techniques") if isinstance(approach, dict) else None
    techniques = ([t for t in raw_techniques if isinstance(t, str)]
                  if isinstance(raw_techniques, list) else [])
    if techniques:
        planned = []
        for name in techniques:
            mapped = _PLANNED_ELICITATION_TECHNIQUES.get(name.strip().lower())
            if mapped and mapped not in planned:
                planned.append(mapped)
        if not planned:
            lines.append(
                f"- ℹ️ The 3.1 plan recommends no elicitation techniques "
                f"({', '.join(techniques)}), so there is nothing to cross-check "
                f"against `{technique}`.")
        elif technique in planned:
            lines.append(
                f"- ✅ `{technique}` is among the techniques 3.1 recommended "
                f"({', '.join(planned)}).")
        else:
            lines.append(
                f"- ⚠️ 3.1 recommended {', '.join(planned)}; this session uses "
                f"`{technique}`. Not a blocker — the rationale below is what matters.")

    if not lines:
        return "", note
    # The trailing blank line is load-bearing for the document, not for Markdown: every
    # other separator in this artefact is followed by one, and the block is spliced in
    # directly before a heading.
    block = "\n".join(["## From the BA plan (3.1)", ""] + lines + ["", "---", "", ""])
    return block, note


@mcp.tool()
def save_elicitation_plan(
    project_name: str,
    goals: str,
    stakeholders_json: str,
    technique: Literal[
        "Interview",
        "Survey",
        "Workshop",
        "Brainstorming",
        "Document Analysis",
        "Observation",
        "Prototyping",
        "Focus Group",
        "Benchmarking"
    ],
    technique_rationale: str,
    questions_or_agenda: str,
    expected_outcomes: str,
) -> str:
    """
    BABOK 4.1 — Saves the requirements elicitation plan to a .md file.

    Args:
        project_name:          Name of the project or initiative.
        goals:                 Elicitation goals. What you need to learn / confirm.
        stakeholders_json:     JSON array of stakeholders. Format:
                               [{"name": "Jane Doe", "role": "Process Owner",
                                 "influence": "High", "interest": "High",
                                 "what_to_learn": "Pain points of the current process"}]
        technique:             Selected elicitation technique.
        technique_rationale:   Rationale for the chosen technique.
        questions_or_agenda:   Questions (for interview/survey) or agenda (for workshop).
                               Pass as numbered text or markdown.
        expected_outcomes:     Expected outcomes of the elicitation session.

    Returns:
        Path to the saved elicitation plan file.
    """
    logger.info(f"4.1 Saving elicitation plan: project='{project_name}', technique='{technique}'")

    # An elicitation plan without stakeholders is meaningless — keep this required
    # (the previous json.loads("") failure had made it required by accident).
    stakeholders, error = parse_json_dict_list(
        stakeholders_json, "stakeholders_json", required=True,
        example='[{"name": "Jane Doe", "role": "Process Owner", "influence": "High", '
                '"interest": "High", "what_to_learn": "Pain points of the current process"}]')
    if error:
        return error

    # Build the stakeholder table
    stakeholder_rows = "\n".join([
        f"| {s.get('name', '—')} | {s.get('role', '—')} | "
        f"{s.get('influence', '—')} | {s.get('interest', '—')} | "
        f"{s.get('what_to_learn', '—')} |"
        for s in stakeholders
    ])

    stakeholder_table = (
        "| Stakeholder | Role | Influence | Interest | What we want to learn |\n"
        "| :--- | :--- | :---: | :---: | :--- |\n"
        + stakeholder_rows
    )

    planned_block, plan_note = _planned_context(project_name, technique)

    from datetime import date
    content = f"""# Elicitation Activity Plan

**Project:** {project_name}
**Prepared on:** {date.today().strftime("%d.%m.%Y")}
**Technique:** {technique}

---

{planned_block}## Elicitation Goals

{goals}

---

## Stakeholders

{stakeholder_table}

---

## Selected Technique: {technique}

**Rationale:** {technique_rationale}

---

## Questions / Agenda

{questions_or_agenda}

---

## Expected Outcomes

{expected_outcomes}
"""

    # Numbered prefix like every other chapter; project_id is the FOLDER, so repeating
    # the project name in the filename is redundant (and was the shape that misled the
    # 7.1 consumer into globbing for a pid that the filename never carries).
    suffix = save_artifact(content, "4_1_elicitation_plan", project_id=project_name)
    registry_note = _seed_registry_from_plan(project_name, stakeholders)
    return f"✅ Elicitation plan saved.{suffix}{registry_note}" + (
        f"\n{plan_note}" if plan_note else "")


# ---------------------------------------------------------------------------
# 4.1.2 — Create a Google Form (stub)
# ---------------------------------------------------------------------------

@mcp.tool()
def create_google_form(
    title: str,
    description: str,
    questions_json: str,
) -> str:
    """
    BABOK 4.1 — Creates a Google Form for surveying stakeholders.

    ⚠️  STUB: requires Google OAuth and Forms API setup.
        Setup instructions appear at the end of the response.

    Args:
        title:          Form title (survey name).
        description:    Intro text for respondents. State the survey's purpose and deadline.
        questions_json: JSON array of questions. Format:
                        [
                          {
                            "text": "Question text",
                            "type": "text" | "scale" | "choice" | "checkbox" | "ranking",
                            "required": true | false,
                            "options": ["Option 1", "Option 2"]  // for choice / checkbox / ranking
                          }
                        ]

    Returns:
        A link to the created form (once the API is configured) or setup instructions.
    """
    logger.info(f"4.1 create_google_form called: title='{title}'")

    questions, error = parse_json_dict_list(
        questions_json, "questions_json",
        example='[{"text": "Question text", "type": "text", "required": true}]')
    if error:
        return error

    # Build the survey preview
    preview_lines = [f"## Survey preview: {title}\n", f"_{description}_\n"]
    for i, q in enumerate(questions, 1):
        q_type = q.get("type", "text")
        required = "\\*" if q.get("required") else ""
        preview_lines.append(f"**{i}. {q.get('text', '—')}** {required} `[{q_type}]`")
        if q.get("options"):
            for opt in q["options"]:
                preview_lines.append(f"   - {opt}")

    preview = "\n".join(preview_lines)

    setup_instructions = """
---

## ⚙️ Google Forms API setup

To activate this tool, follow these steps:

### 1. Google Cloud Project
1. Go to https://console.cloud.google.com
2. Create a new project (or select an existing one)
3. Enable the **Google Forms API**: APIs & Services → Enable APIs → "Google Forms API"
4. Enable the **Google Drive API** (needed to retrieve responses)

### 2. OAuth 2.0 credentials
1. APIs & Services → Credentials → Create Credentials → OAuth Client ID
2. Type: Desktop App
3. Download `credentials.json`

### 3. Install dependencies
```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 googleapiclient
```

### 4. Activate in code
In `skills/elicitation_mcp.py`, replace:
```python
# GOOGLE_CREDENTIALS_PATH = "credentials.json"  # uncomment
# GOOGLE_TOKEN_PATH = "token.json"               # uncomment
```

Once configured, this tool will create the form and return a link to share.
"""

    return preview + setup_instructions


# ---------------------------------------------------------------------------
# 4.1.3 — Retrieve responses from a Google Form (stub)
# ---------------------------------------------------------------------------

@mcp.tool()
def get_form_responses(
    form_id: str,
    export_format: Literal["summary", "full", "csv"] = "summary",
) -> str:
    """
    BABOK 4.1 — Retrieves and structures responses from a Google Form.

    ⚠️  STUB: requires Google OAuth to be configured (see create_google_form).

    Args:
        form_id:        Form ID from the Google Forms URL.
                        Example: from https://forms.gle/ABC123 → form_id = "ABC123"
                        Full ID from the editor URL: /forms/d/{FORM_ID}/edit
        export_format:  Output format:
                        - "summary"  — per-question summary with aggregation
                        - "full"     — all responses, row by row
                        - "csv"      — data for saving to a spreadsheet

    Returns:
        Structured responses from the form, or setup instructions for the API.
    """
    logger.info(f"4.1 get_form_responses called: form_id='{form_id}', format='{export_format}'")

    mock_note = f"""
## ⚠️ Stub: get_form_responses

Tool called for form `{form_id}` (format: {export_format}).

Once the Google API is configured, this tool will:
- Retrieve all responses via the Google Forms API
- For `summary`: aggregate responses per question and surface patterns
- For `full`: return a table of all responses with dates
- For `csv`: save the data to a file for analysis in Excel / Google Sheets

### What to do right now

If responses have already been collected manually — paste them as text or CSV
directly into the chat, and Claude will structure and analyze them without the API.

### API setup
See the instructions in the `create_google_form` tool.
"""
    return mock_note


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
