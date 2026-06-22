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
from skills.common import save_artifact, logger

mcp = FastMCP("BABOK_Elicitation_Prep")


# ---------------------------------------------------------------------------
# 4.1.1 — Save the elicitation plan
# ---------------------------------------------------------------------------

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

    # Parse stakeholders
    try:
        stakeholders = json.loads(stakeholders_json)
    except json.JSONDecodeError as e:
        return (
            f"❌ Error parsing stakeholders_json: {e}\n\n"
            f"Expected format:\n"
            f'```json\n'
            f'[{{"name": "Jane Doe", "role": "Process Owner", '
            f'"influence": "High", "interest": "High", '
            f'"what_to_learn": "Pain points of the current process"}}]\n'
            f'```'
        )

    if not isinstance(stakeholders, list):
        return "❌ Error: stakeholders_json must be a list (JSON array), got an object of a different type"

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

    from datetime import date
    content = f"""# Requirements Elicitation Plan

**Project:** {project_name}
**Prepared on:** {date.today().strftime("%d.%m.%Y")}
**Technique:** {technique}

---

## Elicitation Goals

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

    suffix = save_artifact(content, f"Elicitation_Plan_{project_name.replace(' ', '_')}", project_id=project_name)
    return f"✅ Elicitation plan saved.{suffix}"


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

    # Validate questions
    try:
        questions = json.loads(questions_json)
    except json.JSONDecodeError as e:
        return f"❌ Error parsing questions_json: {e}"

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
