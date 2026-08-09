"""
BABOK 4.5 — Manage Stakeholder Collaboration
MCP tools for managing collaboration with stakeholders.

Tools:
  - log_decision               — record a decision made (Decision Log)
  - save_meeting_notes         — save meeting notes with action items
  - update_engagement_status   — record a change in stakeholder engagement

Architecture note:
  update_engagement_status (4.5) and update_stakeholder_registry (4.2) are distinct tools.
  4.2 registers a stakeholder / updates the base profile.
  4.5 records an engagement change with history: before/after, cause, BA action.
  The split is intentional — they could be merged later if practice shows it's redundant.

  BOTH write to the living registry. They used not to: 4.5 wrote only a
  Markdown report, so "became a Blocker" never reached the registry that 7.4 reads and
  3.2's conflict detector compares against. Separating the REPORT from the FACT is not
  the same as separating the tools — the report is 4.5's alone, the fact is shared.

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
from datetime import date
from typing import Literal
from mcp.server.fastmcp import FastMCP
from skills.common import (save_artifact, logger, parse_json_dict_list,
                           update_stakeholder_registry_file,
                           load_stakeholder_registry, reg_norm, guard_artifact_errors)

mcp = FastMCP("BABOK_Collaborate")


# ---------------------------------------------------------------------------
# 4.5.1 — Decision Log
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Living stakeholder registry (ADR-003) — 4.5 records observed CHANGE
# ---------------------------------------------------------------------------

_REGISTRY_SOURCE_45 = "4.5 engagement status"


def _record_engagement_in_registry(project_name: str, stakeholder_role: str,
                                   attitude_after: str,
                                   engagement_level_after: str) -> str:
    """Writes the observed attitude/engagement into the living registry.

    This tool exists to record that a stakeholder's stance CHANGED, and until now the
    fact lived only in a Markdown report — so the registry 7.4 reads, and 3.2's
    conflict detector compares against, still held the stale value. An analyst could
    read "became a Blocker" in one artifact and "Neutral" in another on the same day.

    Deliberately NOT insert-only, unlike 3.2's and 4.1's seeding. Those tools PLAN and
    must never overwrite what an interview established; this one OBSERVES, so its
    value is the newer evidence and has to win. That asymmetry is the difference
    between the two tools, not an inconsistency.

    The tool takes a ROLE and no name, but registry identity is the NAME — so the role
    is resolved to the person already holding it before writing, and only falls back to
    a role-keyed entry when nobody in the registry holds that role. An ambiguous role
    (two people) is reported rather than guessed: attaching one person's observed
    change to another's record is worse than not recording it automatically.

    Never raises: the engagement record is the deliverable and is already on disk.
    """
    if not stakeholder_role.strip():
        return ""

    # Resolve the ROLE to the NAMED person already holding it.
    #
    # Registry identity is the name, falling back to the role only when there is no
    # name. This tool takes a role and no name, so writing role-keyed created a SECOND
    # record for someone already registered under their name — the duplicate said
    # "Blocker" while the record 7.4 actually reads still said nothing. Found by a live
    # run through 4.1 -> 4.2 -> 4.5; the per-tool tests could not see it, because each
    # wrote the registry from empty.
    try:
        registry = load_stakeholder_registry(project_name)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"4.5 could not read the stakeholder registry: {e}")
        registry = {"stakeholders": []}

    role_key = reg_norm(stakeholder_role)
    matches = [s for s in registry.get("stakeholders", [])
               if reg_norm(s.get("role")) == role_key and reg_norm(s.get("name"))]

    if len(matches) > 1:
        # Guessing would attach an observation about one person to another's record.
        names = ", ".join(f"`{s.get('name')}`" for s in matches)
        return (f"\n⚠️ Stakeholder registry NOT updated — more than one person holds "
                f"the role `{stakeholder_role}`: {names}.\n"
                f"   Record the change against the individual via "
                f"`update_stakeholder_registry` (4.2) so it lands on the right person. "
                f"The engagement record itself is saved.")

    incoming = {"role": stakeholder_role,
                "attitude": attitude_after,
                "engagement_level": engagement_level_after}
    if matches:
        # Carry the stored name so the merge resolves to the SAME record.
        incoming["name"] = matches[0]["name"]

    try:
        result = update_stakeholder_registry_file(
            project_name, [incoming],
            source=_REGISTRY_SOURCE_45,
            insert_defaults={"found_through": _REGISTRY_SOURCE_45},
        )
    except Exception as e:  # noqa: BLE001 — never let the engagement record fail on this
        logger.warning(f"4.5 could not update the stakeholder registry: {e}")
        return ("\n⚠️ Stakeholder registry not updated — "
                "the engagement record is saved.")

    added = len(result.get("added", []))
    verb = "added to" if added else "updated in"
    return (f"\n📇 `{stakeholder_role}` {verb} the stakeholder registry: "
            f"attitude → {attitude_after}, engagement → {engagement_level_after} "
            f"(the registry 7.4 reads).")



@mcp.tool()
@guard_artifact_errors
def log_decision(
    project_name: str,
    decision_date: str,
    decision_statement: str,
    context: str,
    alternatives_json: str,
    decision_maker: str,
    participants_json: str,
    decision_type: Literal[
        "Requirement",
        "Priority",
        "Architectural",
        "Process",
        "Scope",
        "Other",
    ],
    affected_artifacts_json: str,
    rationale: str,
    risks: str,
) -> str:
    """
    BABOK 4.5 — Records a decision made in the Decision Log.
    Provides traceability: why the requirements ended up the way they are.

    Args:
        project_name:           Project name.
        decision_date:          Decision date DD.MM.YYYY.
        decision_statement:     The decision in one sentence — clear and unambiguous.
        context:                Context: what was discussed, what problem was being solved.
        alternatives_json:      Alternatives considered. Format:
                                [
                                  {
                                    "option": "Option description",
                                    "pros": "Pros",
                                    "cons": "Cons",
                                    "rejected_reason": "Why rejected, or ''"
                                  }
                                ]
        decision_maker:         Who made the final decision (role or name).
        participants_json:      Discussion participants. Format:
                                [{"name": "name or role", "position": "position on the decision"}]
        decision_type:          Decision type.
        affected_artifacts_json: Affected artifacts. Format:
                                [{"artifact": "name or path", "impact": "how it changes"}]
        rationale:              Rationale for the chosen decision.
        risks:                  Risks of the decision made, or '' if none.

    Returns:
        Path to the saved Decision Log entry.
    """
    logger.info(f"4.5 Decision Log: project='{project_name}', type='{decision_type}'")

    alternatives, error = parse_json_dict_list(
        alternatives_json, "alternatives_json",
        example='[{"option": "...", "pros": "...", "cons": "...", "rejected_reason": "..."}]')
    if error:
        return error

    participants, error = parse_json_dict_list(
        participants_json, "participants_json",
        example='[{"name": "name or role", "position": "position on the decision"}]')
    if error:
        return error

    artifacts, error = parse_json_dict_list(
        affected_artifacts_json, "affected_artifacts_json",
        example='[{"artifact": "FR-001", "impact": "how it changes"}]')
    if error:
        return error

    today = date.today().strftime("%d.%m.%Y")

    # Generate the decision ID based on the date
    decision_id = f"DEC-{decision_date.replace('.', '')}"

    lines = []
    lines.append(f"# Decision Log — {decision_id}\n")
    lines.append(f"**Project:** {project_name}  ")
    lines.append(f"**Date:** {decision_date}  ")
    lines.append(f"**Type:** {decision_type}  ")
    lines.append(f"**Decision maker:** {decision_maker}\n")
    lines.append("---\n")

    lines.append("## Decision\n")
    lines.append(f"> {decision_statement}\n")

    lines.append("---\n")
    lines.append("## Context\n")
    lines.append(f"{context}\n")

    lines.append("---\n")
    lines.append("## Rationale\n")
    lines.append(f"{rationale}\n")

    if alternatives:
        lines.append("---\n")
        lines.append("## Alternatives Considered\n")
        for i, alt in enumerate(alternatives, 1):
            lines.append(f"### Option {i}: {alt.get('option', '—')}\n")
            if alt.get("pros"):
                lines.append(f"- **Pros:** {alt['pros']}  ")
            if alt.get("cons"):
                lines.append(f"- **Cons:** {alt['cons']}  ")
            if alt.get("rejected_reason"):
                lines.append(f"- **Why rejected:** {alt['rejected_reason']}\n")
            else:
                lines.append("")

    lines.append("---\n")
    lines.append("## Discussion Participants\n")
    lines.append("| Participant | Position |")
    lines.append("|---|---|")
    for p in participants:
        lines.append(f"| {p.get('name', '—')} | {p.get('position', '—')} |")
    lines.append("")

    if artifacts:
        lines.append("---\n")
        lines.append("## Affected Artifacts\n")
        for a in artifacts:
            lines.append(f"- **{a.get('artifact', '—')}**: {a.get('impact', '—')}")
        lines.append("")

    if risks:
        lines.append("---\n")
        lines.append("## Risks of This Decision\n")
        lines.append(f"{risks}\n")

    lines.append("---\n")
    lines.append(f"*BABOK 4.5 — Decision Log {decision_id}. Project: {project_name}. Recorded: {today}.*\n")

    content = "\n".join(lines)
    meta = (
        f"<!--\n"
        f"  BABOK 4.5 — Decision Log\n"
        f"  ID: {decision_id}\n"
        f"  Project: {project_name}\n"
        f"  Type: {decision_type}\n"
        f"  Decision maker: {decision_maker}\n"
        f"  Date: {decision_date}\n"
        f"  Alternatives considered: {len(alternatives)}\n"
        f"  Recorded: {today}\n"
        f"-->\n\n"
    )
    return save_artifact(meta + content, prefix="4_5_decision_log", project_id=project_name)


# ---------------------------------------------------------------------------
# 4.5.2 — Meeting Notes
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def save_meeting_notes(
    project_name: str,
    meeting_date: str,
    meeting_type: Literal[
        "Interview",
        "Workshop",
        "Status Meeting",
        "Facilitation Session",
        "1-on-1 Meeting",
        "Presentation",
        "Other",
    ],
    participants_json: str,
    agenda_json: str,
    discussion_summary: str,
    decisions_json: str,
    action_items_json: str,
    open_questions: str,
    risks_identified: str,
    next_meeting: str,
) -> str:
    """
    BABOK 4.5 — Saves structured meeting notes.
    Used after any meeting within the project.

    Args:
        project_name:       Project name.
        meeting_date:       Meeting date DD.MM.YYYY.
        meeting_type:       Meeting type.
        participants_json:  Participants. Format:
                            [{"name": "name or role", "department": "department or ''"}]
        agenda_json:        Agenda. Format:
                            [{"item": "agenda item", "owner": "who led it"}]
        discussion_summary: Brief discussion summary — key points,
                            important statements, context of agreements.
        decisions_json:     Decisions made. Format:
                            [{"decision": "statement", "decision_maker": "who"}]
                            Empty list [] if no decisions were made.
        action_items_json:  Action items. Format:
                            [
                              {
                                "action": "What to do",
                                "owner": "Who does it",
                                "deadline": "DD.MM.YYYY or ''",
                                "priority": "High | Medium | Low"
                              }
                            ]
        open_questions:     Questions that remained open — text or ''.
        risks_identified:   Risks identified during the meeting — text or ''.
        next_meeting:       When the next meeting is and what to discuss, or ''.

    Returns:
        Path to the saved meeting notes.
    """
    logger.info(f"4.5 Meeting notes: project='{project_name}', type='{meeting_type}'")

    participants, error = parse_json_dict_list(
        participants_json, "participants_json",
        example='[{"name": "name or role", "department": "department"}]')
    if error:
        return error

    agenda, error = parse_json_dict_list(
        agenda_json, "agenda_json",
        example='[{"item": "agenda item", "owner": "who led it"}]')
    if error:
        return error

    decisions, error = parse_json_dict_list(
        decisions_json, "decisions_json",
        example='[{"decision": "statement", "decision_maker": "who"}]')
    if error:
        return error

    action_items, error = parse_json_dict_list(
        action_items_json, "action_items_json",
        example='[{"action": "...", "owner": "...", "deadline": "DD.MM.YYYY", "priority": "High"}]')
    if error:
        return error

    today = date.today().strftime("%d.%m.%Y")

    lines = []
    lines.append(f"# Meeting Notes — {meeting_type}\n")
    lines.append(f"**Project:** {project_name}  ")
    lines.append(f"**Date:** {meeting_date}  ")
    lines.append(f"**Type:** {meeting_type}  ")
    lines.append(f"**Participants:** {', '.join(p.get('name', '—') for p in participants)}\n")
    lines.append("---\n")

    if agenda:
        lines.append("## Agenda\n")
        for i, item in enumerate(agenda, 1):
            owner = f" *({item['owner']})*" if item.get("owner") else ""
            lines.append(f"{i}. {item.get('item', '—')}{owner}")
        lines.append("")

    lines.append("---\n")
    lines.append("## Discussion Summary\n")
    lines.append(f"{discussion_summary}\n")

    if decisions:
        lines.append("---\n")
        lines.append("## Decisions Made\n")
        for i, d in enumerate(decisions, 1):
            dm = f" *(decision maker: {d['decision_maker']})*" if d.get("decision_maker") else ""
            lines.append(f"**D{i}.** {d.get('decision', '—')}{dm}")
        lines.append("")

    if action_items:
        lines.append("---\n")
        lines.append("## Action Items\n")
        lines.append("| # | Action | Owner | Deadline | Priority |")
        lines.append("|---|---|---|---|---|")
        for i, item in enumerate(action_items, 1):
            deadline = item.get("deadline") or "—"
            priority = item.get("priority", "Medium")
            priority_icon = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(priority, "🟡")
            lines.append(
                f"| {i} | {item.get('action', '—')} "
                f"| {item.get('owner', '—')} "
                f"| {deadline} "
                f"| {priority_icon} {priority} |"
            )
        lines.append("")

    if open_questions:
        lines.append("---\n")
        lines.append("## Open Questions\n")
        lines.append(f"{open_questions}\n")

    if risks_identified:
        lines.append("---\n")
        lines.append("## Risks Identified\n")
        lines.append(f"{risks_identified}\n")

    if next_meeting:
        lines.append("---\n")
        lines.append("## Next Meeting\n")
        lines.append(f"{next_meeting}\n")

    lines.append("---\n")
    lines.append(f"*BABOK 4.5 — Meeting Notes. Project: {project_name}. Recorded: {today}.*\n")

    content = "\n".join(lines)
    meta = (
        f"<!--\n"
        f"  BABOK 4.5 — Meeting Notes\n"
        f"  Project: {project_name}\n"
        f"  Type: {meeting_type}\n"
        f"  Date: {meeting_date}\n"
        f"  Participants: {len(participants)}\n"
        f"  Decisions: {len(decisions)}\n"
        f"  Action items: {len(action_items)}\n"
        f"  Recorded: {today}\n"
        f"-->\n\n"
    )
    return save_artifact(meta + content, prefix="4_5_meeting_notes", project_id=project_name)


# ---------------------------------------------------------------------------
# 4.5.3 — Update stakeholder engagement status
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def update_engagement_status(
    project_name: str,
    stakeholder_role: str,
    change_date: str,
    attitude_before: Literal["Champion", "Neutral", "Blocker"],
    attitude_after: Literal["Champion", "Neutral", "Blocker"],
    engagement_level_before: Literal["Active", "Passive", "Absent"],
    engagement_level_after: Literal["Active", "Passive", "Absent"],
    signal_observed: str,
    probable_cause: str,
    ba_action_taken: str,
    ba_action_planned: str,
    escalation_needed: bool,
    escalation_to: str,
) -> str:
    """
    BABOK 4.5 — Records a change in stakeholder engagement.
    Maintains a history of changes: before/after, cause, BA action.

    Difference from update_stakeholder_registry (4.2):
    - 4.2 registers a new stakeholder or updates the base profile
    - 4.5 records the dynamics: what changed, why, what the BA did

    Args:
        project_name:             Project name.
        stakeholder_role:         Stakeholder role.
        change_date:              Date the change was observed, DD.MM.YYYY.
        attitude_before:          Attitude before the change.
        attitude_after:           Attitude after the change.
        engagement_level_before:  Engagement level before.
        engagement_level_after:   Engagement level after.
        signal_observed:          What exactly the BA observed — concrete behavior.
        probable_cause:           Probable cause of the change (BA's hypothesis).
        ba_action_taken:          What the BA has already done in response.
        ba_action_planned:        What the BA plans to do next.
        escalation_needed:        True if escalation is required.
        escalation_to:            Who to escalate to, or '' if not needed.

    Returns:
        Path to the saved engagement-status change record.
    """
    logger.info(f"4.5 Engagement status: project='{project_name}', stakeholder='{stakeholder_role}'")

    today = date.today().strftime("%d.%m.%Y")

    # Determine the direction of change
    attitude_values = {"Champion": 3, "Neutral": 2, "Blocker": 1}
    engagement_values = {"Active": 3, "Passive": 2, "Absent": 1}

    attitude_delta = attitude_values.get(attitude_after, 2) - attitude_values.get(attitude_before, 2)
    engagement_delta = engagement_values.get(engagement_level_after, 2) - engagement_values.get(engagement_level_before, 2)

    if attitude_delta > 0 or engagement_delta > 0:
        trend = "📈 Improving"
    elif attitude_delta < 0 or engagement_delta < 0:
        trend = "📉 Declining"
    else:
        trend = "➡️ No change"

    attitude_icons = {"Champion": "🟢", "Neutral": "🟡", "Blocker": "🔴"}

    lines = []
    lines.append(f"# Engagement Change — {stakeholder_role}\n")
    lines.append(f"**Project:** {project_name}  ")
    lines.append(f"**Stakeholder:** {stakeholder_role}  ")
    lines.append(f"**Date of change:** {change_date}  ")
    lines.append(f"**Trend:** {trend}\n")
    lines.append("---\n")

    lines.append("## Dynamics\n")
    lines.append("| Parameter | Before | After |")
    lines.append("|---|---|---|")
    lines.append(
        f"| Attitude | {attitude_icons.get(attitude_before, '—')} {attitude_before} "
        f"| {attitude_icons.get(attitude_after, '—')} {attitude_after} |"
    )
    lines.append(
        f"| Engagement | {engagement_level_before} | {engagement_level_after} |\n"
    )

    lines.append("---\n")
    lines.append("## Signal Observed\n")
    lines.append(f"{signal_observed}\n")

    lines.append("---\n")
    lines.append("## Probable Cause\n")
    lines.append(f"{probable_cause}\n")

    lines.append("---\n")
    lines.append("## BA Actions\n")
    if ba_action_taken:
        lines.append(f"**Already done:** {ba_action_taken}  ")
    lines.append(f"**Planned:** {ba_action_planned}\n")

    if escalation_needed:
        lines.append("---\n")
        lines.append("## ⚠️ Escalation Required\n")
        lines.append(f"**To whom:** {escalation_to or 'not specified'}  ")
        lines.append(
            "\n*Recommendation: record the escalation in the meeting notes "
            "via `save_meeting_notes`.*\n"
        )

    lines.append("---\n")
    lines.append(
        f"*BABOK 4.5 — Engagement Status Update. "
        f"Project: {project_name}. Recorded: {today}.*\n"
    )

    content = "\n".join(lines)
    meta = (
        f"<!--\n"
        f"  BABOK 4.5 — Engagement Status\n"
        f"  Project: {project_name}\n"
        f"  Stakeholder: {stakeholder_role}\n"
        f"  Attitude: {attitude_before} → {attitude_after}\n"
        f"  Engagement: {engagement_level_before} → {engagement_level_after}\n"
        f"  Trend: {trend}\n"
        f"  Escalation: {escalation_needed}\n"
        f"  Date: {change_date}\n"
        f"  Recorded: {today}\n"
        f"-->\n\n"
    )
    artifact = save_artifact(meta + content, prefix="4_5_engagement_status",
                             project_id=project_name)
    return artifact + _record_engagement_in_registry(
        project_name, stakeholder_role, attitude_after, engagement_level_after)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
