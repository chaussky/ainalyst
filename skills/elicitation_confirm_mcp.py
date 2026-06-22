"""
BABOK 4.3 — Confirm Elicitation Results
MCP tools for confirming elicitation results.

Tools:
  - run_consistency_check          — check artifact(s) from 4.2 against 5 quality criteria
  - save_confirmed_elicitation_result — save the final confirmed artifact

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
from datetime import date
from typing import Literal
from mcp.server.fastmcp import FastMCP
from skills.common import save_artifact, logger, DATA_DIR

mcp = FastMCP("BABOK_Elicitation_Confirm")


# ---------------------------------------------------------------------------
# 4.3.1 — Quality check of elicitation artifacts against 5 criteria
# ---------------------------------------------------------------------------

@mcp.tool()
def run_consistency_check(
    project_name: str,
    source_artifacts_json: str,
    issues_json: str,
    readiness_status: Literal["Ready for Analysis", "Conditionally Ready", "Needs Rework"],
    readiness_rationale: str,
    needs_clarification: bool,
    clarification_questions_json: str,
    ba_decision: str,
) -> str:
    """
    BABOK 4.3 — Saves a quality-check report for elicitation artifacts.
    Checks completeness, correctness, consistency, unambiguity, and testability.

    Args:
        project_name:               Project name.
        source_artifacts_json:      List of checked artifacts. Format:
                                    [
                                      {
                                        "path": "governance_plans/4_2_..._results.md",
                                        "stakeholder_role": "Head of Sales",
                                        "session_date": "DD.MM.YYYY"
                                      }
                                    ]
        issues_json:                Identified issues. Format:
                                    [
                                      {
                                        "issue_id": "ISS-001",
                                        "criterion": "Completeness | Correctness | Consistency | Unambiguity | Testability",
                                        "severity": "Critical | Significant | Minor",
                                        "description": "Description of the issue",
                                        "evidence": "Quote or requirement ID from the artifact",
                                        "source_artifact": "file path or stakeholder role",
                                        "recommendation": "What to do to resolve it"
                                      }
                                    ]
        readiness_status:           Overall readiness rating of the artifact.
        readiness_rationale:        Rationale for the rating — why this particular status.
        needs_clarification:        True if clarification from the stakeholder is needed.
        clarification_questions_json: List of targeted questions if needs_clarification=True. Format:
                                    [
                                      {
                                        "stakeholder_role": "Who the question is addressed to",
                                        "issue_id": "ISS-001",
                                        "question": "Question text for the stakeholder",
                                        "context": "Context: in the meeting you mentioned...",
                                        "options": ["Option A", "Option B"]
                                      }
                                    ]
        ba_decision:                BA's decision: what to do next (free text).

    Returns:
        Path to the saved quality-check report.
    """
    logger.info(f"4.3 Quality check: project='{project_name}'")

    try:
        artifacts = json.loads(source_artifacts_json)
        issues = json.loads(issues_json)
        questions = json.loads(clarification_questions_json) if clarification_questions_json else []
    except json.JSONDecodeError as e:
        return f"❌ Error parsing JSON: {e}"

    today = date.today().strftime("%d.%m.%Y")

    # Issue statistics
    critical = [i for i in issues if i.get("severity") == "Critical"]
    significant = [i for i in issues if i.get("severity") == "Significant"]
    minor = [i for i in issues if i.get("severity") == "Minor"]

    by_criterion = {}
    for issue in issues:
        c = issue.get("criterion", "—")
        by_criterion.setdefault(c, []).append(issue)

    # Status icon
    status_icon = {"Ready for Analysis": "✅", "Conditionally Ready": "⚠️", "Needs Rework": "🔴"}.get(
        readiness_status, "❓"
    )

    # -----------------------------------------------------------------------
    # Build the report
    # -----------------------------------------------------------------------
    lines = []
    lines.append("# Elicitation Results Quality-Check Report (BABOK 4.3)\n")
    lines.append(f"**Project:** {project_name}  ")
    lines.append(f"**Check date:** {today}  ")
    lines.append(f"**Readiness status:** {status_icon} {readiness_status}\n")
    lines.append("---\n")

    # Checked artifacts
    lines.append("## Checked Artifacts\n")
    for a in artifacts:
        lines.append(
            f"- `{a.get('path', '—')}` "
            f"— {a.get('stakeholder_role', '—')}, {a.get('session_date', '—')}"
        )
    lines.append("")

    # Overall rating
    lines.append("---\n")
    lines.append(f"## {status_icon} Readiness Rating: {readiness_status}\n")
    lines.append(f"{readiness_rationale}\n")

    # Issue summary
    lines.append("---\n")
    lines.append("## Issue Summary\n")
    lines.append(f"| Severity | Count |")
    lines.append(f"|---|---|")
    lines.append(f"| 🔴 Critical | {len(critical)} |")
    lines.append(f"| 🟡 Significant | {len(significant)} |")
    lines.append(f"| 🟢 Minor | {len(minor)} |")
    lines.append(f"| **Total** | **{len(issues)}** |\n")

    if not issues:
        lines.append("_No issues found. The artifact meets all quality criteria._\n")
    else:
        # Issues by criterion
        lines.append("---\n")
        lines.append("## Issues by Criterion\n")

        criterion_order = ["Completeness", "Correctness", "Consistency", "Unambiguity", "Testability"]
        for criterion in criterion_order:
            criterion_issues = by_criterion.get(criterion, [])
            if not criterion_issues:
                continue
            lines.append(f"### {criterion}\n")
            for iss in criterion_issues:
                sev = iss.get("severity", "—")
                sev_icon = {"Critical": "🔴", "Significant": "🟡", "Minor": "🟢"}.get(sev, "❓")
                lines.append(f"**{iss.get('issue_id', '—')}** {sev_icon} {sev}  ")
                lines.append(f"- **Issue:** {iss.get('description', '—')}  ")
                if iss.get("evidence"):
                    lines.append(f"- **Example:** {iss['evidence']}  ")
                if iss.get("source_artifact"):
                    lines.append(f"- **Source:** `{iss['source_artifact']}`  ")
                lines.append(f"- **Recommendation:** {iss.get('recommendation', '—')}\n")

    # Clarification questions
    if needs_clarification and questions:
        lines.append("---\n")
        lines.append("## Questions for Stakeholder Clarification\n")

        by_stakeholder = {}
        for q in questions:
            role = q.get("stakeholder_role", "Not specified")
            by_stakeholder.setdefault(role, []).append(q)

        for role, qs in by_stakeholder.items():
            lines.append(f"### {role}\n")
            for q in qs:
                lines.append(f"**[{q.get('issue_id', '—')}]** {q.get('question', '—')}  ")
                if q.get("context"):
                    lines.append(f"*Context: {q['context']}*  ")
                options = q.get("options", [])
                if options:
                    for i, opt in enumerate(options, 1):
                        lines.append(f"  - Option {i}: {opt}")
                lines.append("")
    elif needs_clarification:
        lines.append("---\n")
        lines.append("## Clarification Needed\n")
        lines.append("_The list of questions has been drafted in the chat. Clarify with the stakeholders before continuing._\n")

    # BA decision
    lines.append("---\n")
    lines.append("## BA Decision\n")
    lines.append(f"{ba_decision}\n")
    lines.append("---\n")
    lines.append(
        f"*BABOK 4.3 — Consistency Check Report. "
        f"Project: {project_name}. Date: {today}.*\n"
    )

    content = "\n".join(lines)

    meta = (
        f"<!--\n"
        f"  BABOK 4.3 — Consistency Check\n"
        f"  Project: {project_name}\n"
        f"  Artifacts checked: {len(artifacts)}\n"
        f"  Issues: {len(issues)} (critical: {len(critical)}, significant: {len(significant)}, minor: {len(minor)})\n"
        f"  Status: {readiness_status}\n"
        f"  Needs clarification: {needs_clarification}\n"
        f"  Created: {today}\n"
        f"-->\n\n"
    )

    return save_artifact(meta + content, prefix="4_3_consistency_check", project_id=project_name)


# ---------------------------------------------------------------------------
# 4.3.2 — Save the final confirmed artifact
# ---------------------------------------------------------------------------

@mcp.tool()
def save_confirmed_elicitation_result(
    project_name: str,
    stakeholder_role: str,
    consistency_check_path: str,
    confirmed_requirements_json: str,
    resolved_issues_json: str,
    open_issues_json: str,
    final_readiness: Literal["Ready for Analysis", "Conditionally Ready"],
    next_tasks: str,
) -> str:
    """
    BABOK 4.3 — Saves the final confirmed elicitation artifact.
    Serves as input for tasks 6.1 (Current State Analysis) and 6.3 (Risk Assessment).

    Args:
        project_name:               Project name.
        stakeholder_role:           Stakeholder role (source of the requirements).
        consistency_check_path:     Path to the run_consistency_check report.
        confirmed_requirements_json: Confirmed requirements — final wording. Format:
                                    {
                                      "functional": [
                                        {"id": "FR-001", "statement": "...", "acceptance_criteria": "..."},
                                      ],
                                      "non_functional": [
                                        {"id": "NFR-001", "statement": "...", "metric": "..."}
                                      ],
                                      "constraints": ["..."],
                                      "business_rules": ["..."]
                                    }
        resolved_issues_json:       Issues closed from the consistency check. Format:
                                    [
                                      {
                                        "issue_id": "ISS-001",
                                        "resolution": "How it was closed",
                                        "updated_requirement_id": "FR-001 or null"
                                      }
                                    ]
        open_issues_json:           Remaining open issues (known issues). Format:
                                    [
                                      {
                                        "issue_id": "ISS-002",
                                        "description": "Brief description",
                                        "risk": "What's at risk if not closed",
                                        "owner": "Who should close it"
                                      }
                                    ]
        final_readiness:            Final status. Either Ready for Analysis or Conditionally Ready
                                    (Needs Rework cannot be a final status).
        next_tasks:                 Specific next steps — what to do next.

    Returns:
        Path to the saved confirmed artifact.
    """
    logger.info(f"4.3 Saving confirmed artifact: project='{project_name}'")

    try:
        reqs = json.loads(confirmed_requirements_json)
        resolved = json.loads(resolved_issues_json)
        open_iss = json.loads(open_issues_json)
    except json.JSONDecodeError as e:
        return f"❌ Error parsing JSON: {e}"

    today = date.today().strftime("%d.%m.%Y")
    status_icon = {"Ready for Analysis": "✅", "Conditionally Ready": "⚠️"}.get(final_readiness, "✅")

    # Count requirements
    functional = reqs.get("functional", [])
    non_functional = reqs.get("non_functional", [])
    constraints = reqs.get("constraints", [])
    business_rules = reqs.get("business_rules", [])

    # -----------------------------------------------------------------------
    # Build the artifact
    # -----------------------------------------------------------------------
    lines = []
    lines.append("# Confirmed Elicitation Results (BABOK 4.3)\n")
    lines.append(f"**Project:** {project_name}  ")
    lines.append(f"**Stakeholder:** {stakeholder_role}  ")
    lines.append(f"**Confirmation date:** {today}  ")
    lines.append(f"**Status:** {status_icon} {final_readiness}  ")
    lines.append(f"**Based on check:** `{consistency_check_path}`\n")
    lines.append("---\n")

    # Summary
    lines.append("## Summary\n")
    lines.append(f"| Type | Count |")
    lines.append(f"|---|---|")
    lines.append(f"| Functional requirements | {len(functional)} |")
    lines.append(f"| Non-functional requirements | {len(non_functional)} |")
    lines.append(f"| Constraints | {len(constraints)} |")
    lines.append(f"| Business rules | {len(business_rules)} |")
    lines.append(f"| Closed issues | {len(resolved)} |")
    lines.append(f"| Open issues (known issues) | {len(open_iss)} |\n")

    # Functional requirements
    if functional:
        lines.append("---\n")
        lines.append("## Functional Requirements\n")
        for r in functional:
            lines.append(f"**{r.get('id', '—')}:** {r.get('statement', '—')}  ")
            if r.get("acceptance_criteria"):
                lines.append(f"*Acceptance criteria: {r['acceptance_criteria']}*\n")
            else:
                lines.append("")

    # Non-functional requirements
    if non_functional:
        lines.append("---\n")
        lines.append("## Non-Functional Requirements\n")
        for r in non_functional:
            lines.append(f"**{r.get('id', '—')}:** {r.get('statement', '—')}  ")
            if r.get("metric"):
                lines.append(f"*Metric: {r['metric']}*\n")
            else:
                lines.append("")

    # Constraints
    if constraints:
        lines.append("---\n")
        lines.append("## Constraints\n")
        for c in constraints:
            lines.append(f"- {c}")
        lines.append("")

    # Business rules
    if business_rules:
        lines.append("---\n")
        lines.append("## Business Rules\n")
        for br in business_rules:
            lines.append(f"- {br}")
        lines.append("")

    # Closed issues
    if resolved:
        lines.append("---\n")
        lines.append("## Closed Issues\n")
        for r in resolved:
            upd = f" → updated `{r['updated_requirement_id']}`" if r.get("updated_requirement_id") else ""
            lines.append(f"- **{r.get('issue_id', '—')}:** {r.get('resolution', '—')}{upd}")
        lines.append("")

    # Open issues (known issues)
    if open_iss:
        lines.append("---\n")
        lines.append("## ⚠️ Open Issues (Known Issues)\n")
        lines.append("_Passed to subsequent tasks as explicit risks._\n")
        for iss in open_iss:
            lines.append(f"**{iss.get('issue_id', '—')}:** {iss.get('description', '—')}  ")
            if iss.get("risk"):
                lines.append(f"- Risk: {iss['risk']}  ")
            if iss.get("owner"):
                lines.append(f"- Owner: {iss['owner']}\n")
            else:
                lines.append("")

    # Next steps
    lines.append("---\n")
    lines.append("## Next Steps\n")
    lines.append(f"{next_tasks}\n")
    lines.append("---\n")
    lines.append("## Passed to\n")
    lines.append("- **6.1** — Current State Analysis  ")
    lines.append("- **6.3** — Risk Assessment\n")
    lines.append("---\n")
    lines.append(
        f"*BABOK 4.3 — Confirmed Elicitation Result. "
        f"Project: {project_name}. Date: {today}.*\n"
    )

    content = "\n".join(lines)

    meta = (
        f"<!--\n"
        f"  BABOK 4.3 — Confirmed Result\n"
        f"  Project: {project_name}\n"
        f"  Stakeholder: {stakeholder_role}\n"
        f"  FR: {len(functional)}, NFR: {len(non_functional)}\n"
        f"  Constraints: {len(constraints)}, BR: {len(business_rules)}\n"
        f"  Closed issues: {len(resolved)}, Open: {len(open_iss)}\n"
        f"  Status: {final_readiness}\n"
        f"  Created: {today}\n"
        f"-->\n\n"
    )

    return save_artifact(meta + content, prefix="4_3_confirmed_result", project_id=project_name)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
