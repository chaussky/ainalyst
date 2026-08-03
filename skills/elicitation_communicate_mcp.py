"""
BABOK 4.4 — Communicate Business Analysis Information
MCP tools for preparing and logging communication packages.

Tools:
  - prepare_communication_package  — save a package adapted for the audience
  - log_communication              — log the fact of a communication and its outcome
  - check_communication_schedule   — who is overdue for contact, and which events triggered it

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
from datetime import date
from typing import Literal
from mcp.server.fastmcp import FastMCP
from skills.common import (
    save_artifact, logger, parse_json_dict, parse_json_dict_list,
    pick_field, unrecognized_records_error,
    info_management_section, load_ba_plan, planned_abstraction_level,
    ABSTRACTION_LEVELS, reg_norm, guard_artifact_errors)

mcp = FastMCP("BABOK_Communicate")

# BABOK 3.4 element .2 — what a planned level of detail MEANS when a package is built.
# A bare label with no consequence is the "declared but dead" class; this turns the
# planning decision into an instruction the BA can follow while adapting the content.
_LEVEL_GUIDANCE = {
    "Summary": ("conclusions, business value, the decision being asked for",
                "requirement IDs, NFR wording, model internals"),
    "Standard": ("requirements as a list with priorities, key risks, open questions",
                 "acceptance criteria, exception flows, diagram internals"),
    "Detailed": ("full requirement wording, acceptance criteria, exceptions, models",
                 "nothing — this audience works with the material directly"),
}


# ---------------------------------------------------------------------------
# 4.4.1 — Prepare an adapted communication package
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def prepare_communication_package(
    project_name: str,
    source_artifact_path: str,
    audience_role: Literal[
        "Business Sponsor",
        "Manager",
        "Developer",
        "Architect / Tech Lead",
        "Tester",
        "End User",
        "Customer",
        "Domain SME",
    ],
    audience_profile_json: str,
    adapted_content: str,
    key_messages_json: str,
    recommended_format: Literal[
        "Formal Document",
        "Informal Document",
        "Presentation",
        "Email",
        "1-on-1 Meeting",
        "Group Meeting",
    ],
    recommended_channel: str,
    open_questions: str,
    ba_notes: str,
) -> str:
    """
    BABOK 4.4 — Saves an adapted communication package.
    Contains the artifact repackaged for a specific audience,
    plus recommendations on format and delivery channel.

    Args:
        project_name:           Project name.
        source_artifact_path:   Path to the source artifact (from 4.3 or another task).
        audience_role:          Target audience role.
        audience_profile_json:  Audience profile from the stakeholder registry. Format:
                                {
                                  "stakeholder_role": "...",
                                  "influence": "High | Medium | Low",
                                  "interest": "High | Medium | Low",
                                  "attitude": "Champion | Neutral | Blocker",
                                  "communication_preference": "text or ''",
                                  "key_concerns": "text or ''"
                                }
        adapted_content:        Adapted artifact content — text rephrased
                                into language for this specific audience.
                                This is the package's main block.
        key_messages_json:      Key messages — 3-5 main points the audience
                                should take away. Format:
                                [
                                  {
                                    "message": "Point",
                                    "why_it_matters": "Why it matters to this audience"
                                  }
                                ]
        recommended_format:     Recommended format for presenting the material.
        recommended_channel:    Recommended channel (email, Confluence, Jira, meeting, etc.).
        open_questions:         Questions the audience may raise.
                                The BA should be ready to answer them.
        ba_notes:               BA notes: specifics of this audience, what to watch for.

    Returns:
        Path to the saved communication package.
    """
    logger.info(f"4.4 Preparing package: project='{project_name}', audience='{audience_role}'")

    profile, error = parse_json_dict(
        audience_profile_json, "audience_profile_json",
        example='{"stakeholder_role": "...", "influence": "High", "attitude": "Neutral"}')
    if error:
        return error

    key_messages, error = parse_json_dict_list(
        key_messages_json, "key_messages_json",
        example='[{"message": "...", "why_it_matters": "..."}]')
    if error:
        return error

    today = date.today().strftime("%d.%m.%Y")

    # BABOK 3.4 element .2. The plan keys a row by an audience the BA named — an
    # archetype from this tool's vocabulary OR a job title from the stakeholder map.
    # Matching on one of the two alone could not succeed by construction;
    # check_communication_schedule already carries the same fix.
    plan, plan_note = load_ba_plan(project_name)
    level_row = planned_abstraction_level(
        plan, audience_role, profile.get("stakeholder_role", ""))
    planned_rows = info_management_section(plan).get("abstraction_levels")
    planned_rows = planned_rows if isinstance(planned_rows, list) else []
    # str() because the value is whatever was stored: a numeric audience used to break
    # the join that renders this list.
    planned_audiences = [str(r.get("audience") or "") for r in planned_rows
                         if isinstance(r, dict)]
    # A row for THIS audience whose level the platform cannot act on: the reader drops
    # it, so without this distinction the note said the audience was both unplanned and
    # planned in one sentence, and the BA could not tell which field to repair.
    unusable_level = None
    if not level_row:
        for row in planned_rows:
            if not isinstance(row, dict):
                continue
            if reg_norm(row.get("audience")) in {
                    reg_norm(audience_role), reg_norm(profile.get("stakeholder_role", ""))} - {""}:
                unusable_level = row.get("level")
                break

    # Icons for attitude
    attitude = profile.get("attitude", "Neutral")
    attitude_icon = {"Champion": "🟢", "Neutral": "🟡", "Blocker": "🔴"}.get(attitude, "🟡")

    # -----------------------------------------------------------------------
    # Build the package
    # -----------------------------------------------------------------------
    lines = []
    lines.append(f"# Communication Package: {audience_role}\n")
    lines.append(f"**Project:** {project_name}  ")
    lines.append(f"**Audience:** {audience_role}  ")
    lines.append(f"**Preparation date:** {today}  ")
    if level_row:
        note = f" — {level_row['note']}" if level_row.get("note") else ""
        lines.append(
            f"**Level of detail (planned in 3.4):** {level_row['level']}{note}  ")
    lines.append(f"**Source:** `{source_artifact_path}`\n")
    lines.append("---\n")

    # Audience profile
    lines.append("## Audience Profile\n")
    lines.append(f"| Parameter | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Influence | {profile.get('influence', '—')} |")
    lines.append(f"| Interest | {profile.get('interest', '—')} |")
    lines.append(f"| Attitude toward the project | {attitude_icon} {attitude} |")
    if profile.get("communication_preference"):
        lines.append(f"| Communication style | {profile['communication_preference']} |")
    if profile.get("key_concerns"):
        lines.append(f"| Key concerns | {profile['key_concerns']} |\n")
    else:
        lines.append("")

    # The decoded level lives in the ARTEFACT, not in the return value: this tool
    # returns only the save_artifact line, so a checklist put there would never reach
    # the BA. Here it sits next to the material being adapted.
    if level_row:
        include, leave_out = _LEVEL_GUIDANCE.get(level_row["level"], ("", ""))
        lines.append("---\n")
        lines.append(f"## Level of Detail — {level_row['level']} (planned in 3.4)\n")
        lines.append(f"**Include:** {include}  ")
        lines.append(f"**Leave out:** {leave_out}\n")

    # Key messages
    if key_messages:
        lines.append("---\n")
        lines.append("## Key Messages\n")
        lines.append("_What the audience should take away from this communication:_\n")
        for i, msg in enumerate(key_messages, 1):
            lines.append(f"**{i}. {msg.get('message', '—')}**  ")
            if msg.get("why_it_matters"):
                lines.append(f"*Why it matters: {msg['why_it_matters']}*\n")
            else:
                lines.append("")

    # Adapted content
    lines.append("---\n")
    lines.append(f"## Package Content [{audience_role}]\n")
    lines.append(adapted_content)
    lines.append("")

    # Delivery recommendations
    lines.append("---\n")
    lines.append("## Delivery Recommendations\n")
    lines.append(f"| Parameter | Recommendation |")
    lines.append(f"|---|---|")
    lines.append(f"| Format | {recommended_format} |")
    lines.append(f"| Channel | {recommended_channel} |\n")

    # Possible questions from the audience
    if open_questions:
        lines.append("---\n")
        lines.append("## Possible Questions from the Audience\n")
        lines.append("_The BA should be ready to answer:_\n")
        lines.append(open_questions)
        lines.append("")

    # Blocker — special section
    if attitude == "Blocker":
        lines.append("---\n")
        lines.append("## ⚠️ Caution: Audience Is Skeptical\n")
        lines.append(
            "The stakeholder is classified as a Blocker. Recommended:\n"
            "- Hold a 1-on-1 meeting before the group presentation\n"
            "- Explicitly address their key concerns at the start of the package\n"
            "- Prepare a \"What this means for you personally\" section\n"
        )

    # BA notes
    if ba_notes:
        lines.append("---\n")
        lines.append("## BA Notes\n")
        lines.append(ba_notes)
        lines.append("")

    lines.append("---\n")
    lines.append(
        f"*BABOK 4.4 — Communication Package. "
        f"Project: {project_name}. Audience: {audience_role}. Date: {today}.*\n"
    )

    content = "\n".join(lines)

    meta = (
        f"<!--\n"
        f"  BABOK 4.4 — Communication Package\n"
        f"  Project: {project_name}\n"
        f"  Audience: {audience_role}\n"
        f"  Attitude: {attitude}\n"
        f"  Format: {recommended_format}\n"
        f"  Channel: {recommended_channel}\n"
        f"  Created: {today}\n"
        f"-->\n\n"
    )

    saved = save_artifact(meta + content, prefix="4_4_comm_package",
                          project_id=project_name)

    notes = []
    if plan_note:
        notes.append(plan_note)
    elif unusable_level is not None:
        notes.append(
            f"⚠️ 3.4 does plan a detail level for `{audience_role}`, but its value "
            f"`{unusable_level}` is not one of {', '.join(ABSTRACTION_LEVELS)} — fix it "
            f"in `plan_information_management(abstraction_levels_json=...)`.")
    elif planned_audiences and not level_row:
        # Only when the project actually planned detail levels for SOMEONE. A project
        # that planned storage but no levels has made no decision to be reminded of.
        notes.append(
            f"⚠️ Detail level for `{audience_role}` is not planned in 3.4. "
            f"Planned audiences: {', '.join(a for a in planned_audiences if a)}.")
    return saved + ("\n\n" + "\n".join(notes) if notes else "")


# ---------------------------------------------------------------------------
# 4.4.2 — Log the fact of a communication
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def log_communication(
    project_name: str,
    communication_package_path: str,
    audience_role: str,
    communication_date: str,
    channel_used: Literal[
        "Email",
        "1-on-1 Meeting",
        "Group Meeting",
        "Messenger",
        "Confluence / Document",
        "Other",
    ],
    participants_json: str,
    understanding_status: Literal[
        "Understood and Agreed",
        "Partially Understood",
        "Not Understood — Needs Repeat",
        "No Response",
        "Disagreed",
    ],
    feedback_summary: str,
    action_items_json: str,
    needs_followup: bool,
    followup_deadline: str,
) -> str:
    """
    BABOK 4.4 — Logs the fact of a communication and its outcome.
    Creates an entry in the project's communication log.

    Args:
        project_name:               Project name.
        communication_package_path: Path to the delivered package (from prepare_communication_package).
        audience_role:              Recipient's role.
        communication_date:         Communication date in DD.MM.YYYY format.
        channel_used:               Channel actually used.
        participants_json:          List of participants. Format:
                                    [{"name": "Name or role", "role": "job title"}]
        understanding_status:       Audience's understanding status after the communication.
        feedback_summary:           Brief summary of feedback: what was said, what concerns
                                    were raised, what questions came up.
        action_items_json:          List of resulting actions. Format:
                                    [
                                      {
                                        "action": "What to do",
                                        "owner": "Who is doing it",
                                        "deadline": "DD.MM.YYYY or ''"
                                      }
                                    ]
        needs_followup:             True if a repeat communication is needed.
        followup_deadline:          Follow-up deadline in DD.MM.YYYY format, or '' if not needed.

    Returns:
        Path to the saved communication log entry.
    """
    logger.info(f"4.4 Communication log: project='{project_name}', audience='{audience_role}'")

    participants, error = parse_json_dict_list(
        participants_json, "participants_json",
        example='[{"name": "Alex Kim", "role": "Backend developer"}]')
    if error:
        return error

    action_items, error = parse_json_dict_list(
        action_items_json, "action_items_json",
        example='[{"action": "...", "owner": "...", "deadline": "DD.MM.YYYY"}]')
    if error:
        return error

    today = date.today().strftime("%d.%m.%Y")

    # Understanding status icon
    status_icons = {
        "Understood and Agreed": "✅",
        "Partially Understood": "🟡",
        "Not Understood — Needs Repeat": "🔴",
        "No Response": "⏳",
        "Disagreed": "❌",
    }
    status_icon = status_icons.get(understanding_status, "❓")

    # -----------------------------------------------------------------------
    # Build the log entry
    # -----------------------------------------------------------------------
    lines = []
    lines.append(f"# Communication Log — {audience_role}\n")
    lines.append(f"**Project:** {project_name}  ")
    lines.append(f"**Communication date:** {communication_date}  ")
    lines.append(f"**Logged on:** {today}  ")
    lines.append(f"**Package:** `{communication_package_path}`\n")
    lines.append("---\n")

    # Fact of the communication
    lines.append("## Communication Details\n")
    lines.append(f"| Parameter | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Audience | {audience_role} |")
    lines.append(f"| Channel | {channel_used} |")
    lines.append(f"| Participants | {', '.join(p.get('name', '—') for p in participants)} |")
    lines.append(f"| Understanding status | {status_icon} {understanding_status} |\n")

    # Feedback
    if feedback_summary:
        lines.append("---\n")
        lines.append("## Audience Feedback\n")
        lines.append(feedback_summary)
        lines.append("")

    # Action items
    if action_items:
        lines.append("---\n")
        lines.append("## Action Items\n")
        lines.append(f"| # | Action | Owner | Deadline |")
        lines.append(f"|---|---|---|---|")
        for i, item in enumerate(action_items, 1):
            deadline = item.get("deadline") or "—"
            lines.append(
                f"| {i} | {item.get('action', '—')} "
                f"| {item.get('owner', '—')} "
                f"| {deadline} |"
            )
        lines.append("")

    # Follow-up
    lines.append("---\n")
    if needs_followup:
        lines.append("## 🔄 Follow-up Required\n")
        lines.append(f"**Deadline:** {followup_deadline or 'not specified'}  ")
        if understanding_status == "Not Understood — Needs Repeat":
            lines.append(
                "\n*Recommendation: change the format or delivery channel — "
                "the current one did not achieve the result.*\n"
            )
        elif understanding_status == "Disagreed":
            lines.append(
                "\n*Recommendation: move to task 4.5 (Manage Stakeholder Collaboration) "
                "— this is no longer a communication issue but a disagreement to manage.*\n"
            )
        else:
            lines.append("")
    else:
        lines.append("## ✅ Communication Completed\n")
        lines.append("No repeat communication is required.\n")

    lines.append("---\n")
    lines.append(
        f"*BABOK 4.4 — Communication Log. "
        f"Project: {project_name}. Logged on: {today}.*\n"
    )

    content = "\n".join(lines)

    meta = (
        f"<!--\n"
        f"  BABOK 4.4 — Communication Log\n"
        f"  Project: {project_name}\n"
        f"  Audience: {audience_role}\n"
        f"  Date: {communication_date}\n"
        f"  Understanding status: {understanding_status}\n"
        f"  Follow-up: {needs_followup}\n"
        f"  Logged on: {today}\n"
        f"-->\n\n"
    )

    return save_artifact(meta + content, prefix="4_4_comm_log", project_id=project_name)


# ---------------------------------------------------------------------------
# 4.4.3 — Check the communication schedule
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def check_communication_schedule(
    project_name: str,
    today_date: str,
    stakeholders_json: str,
    communication_log_json: str,
    triggered_events_json: str,
) -> str:
    """
    BABOK 4.4 — Checks the communication schedule and produces a list
    of stakeholders who need to be contacted now.
    Compares the date of the last communication against the frequency from
    the plan (3.2) and checks whether any trigger events have occurred.

    Args:
        project_name:           Project name.
        today_date:             Today's date in DD.MM.YYYY format.
        stakeholders_json:      Stakeholder registry with schedule. Format:
                                [
                                  {
                                    "role": "Sponsor",
                                    "name": "Name or ''",
                                    "influence": "High | Medium | Low",
                                    "interest": "High | Medium | Low",
                                    "attitude": "Champion | Neutral | Blocker",
                                    "comm_frequency": "After Each Session | Weekly | At Milestone | On Request",
                                    "comm_triggers": ["Requirements change", "New decision"],
                                    "last_communication_date": "DD.MM.YYYY or ''",
                                    "last_communication_topic": "What was discussed last time, or ''"
                                  }
                                ]
        communication_log_json: Recent entries from log_communication. Format:
                                [
                                  {
                                    "audience_role": "role",
                                    "communication_date": "DD.MM.YYYY",
                                    "understanding_status": "status",
                                    "needs_followup": true
                                  }
                                ]
        triggered_events_json:  Events that occurred since the last check. Format:
                                [
                                  {
                                    "event_type": "Elicitation session completed | Decision made | Requirements change | Milestone reached | Risk identified",
                                    "description": "Brief event description",
                                    "date": "DD.MM.YYYY"
                                  }
                                ]

    Returns:
        Path to the saved communication schedule report.
    """
    logger.info(f"4.4 Checking schedule: project='{project_name}', date='{today_date}'")

    stakeholders, error = parse_json_dict_list(
        stakeholders_json, "stakeholders_json",
        example='[{"role": "Sponsor", "influence": "High", "comm_frequency": "Weekly", '
                '"last_communication_date": "DD.MM.YYYY"}]')
    if error:
        return error

    comm_log, error = parse_json_dict_list(
        communication_log_json, "communication_log_json",
        example='[{"audience_role": "...", "communication_date": "DD.MM.YYYY"}]')
    if error:
        return error

    events, error = parse_json_dict_list(
        triggered_events_json, "triggered_events_json",
        example='[{"event_type": "Decision made", "description": "...", "date": "DD.MM.YYYY"}]')
    if error:
        return error

    # Normalise the spellings before anything reads these records. Reading only
    # `event_type` / `description` / `date` rendered "- [—] **—**: —" into the delivered
    # schedule — a row about nothing — while the header counted "Triggered: 0" and the
    # tool reported success.
    EVENT_TYPE_KEYS = ("event_type", "type", "event")
    events = [
        {
            **e,
            "event_type": pick_field(e, *EVENT_TYPE_KEYS),
            "description": pick_field(e, "description", "summary", "details",
                                      *EVENT_TYPE_KEYS),
            "date": pick_field(e, "date", "on", "occurred"),
        }
        for e in events
    ]
    if events and not any(e["event_type"] for e in events):
        return unrecognized_records_error(
            "triggered_events_json", EVENT_TYPE_KEYS,
            '[{"event_type": "Decision made", "description": "...", "date": "DD.MM.YYYY"}]')

    from datetime import datetime, timedelta

    def parse_date(s: str):
        if not s:
            return None
        try:
            return datetime.strptime(s.strip(), "%d.%m.%Y")
        except ValueError:
            return None

    today = parse_date(today_date) or datetime.today()

    # Most recent communications from the log (supplement the registry data)
    # Key the log by every identifier it carries, lower-cased.
    #
    # `log_communication` records `audience_role` from the 4.4 audience vocabulary
    # ("Business Sponsor", "Developer", …), while the stakeholder map carries job titles
    # from 3.2/4.2 ("Head of Retail Lending"). Matching those two by exact string could
    # not succeed by construction, so a communication logged days earlier never
    # suppressed the urgency and the schedule stated "No communication on record yet"
    # about someone who had just been briefed. Accept a match on either identifier.
    log_by_role = {}

    def _remember(key, payload):
        key = str(key).strip().lower()
        if not key:
            return
        if key not in log_by_role or payload["date"] > log_by_role[key]["date"]:
            log_by_role[key] = payload

    for entry in comm_log:
        d = parse_date(entry.get("communication_date", ""))
        if not d:
            continue
        payload = {
            "date": d,
            "status": entry.get("understanding_status", ""),
            "followup": entry.get("needs_followup", False),
        }
        for key in (entry.get("audience_role"), entry.get("role"),
                    entry.get("stakeholder_name"), entry.get("name")):
            _remember(key, payload)

    # Frequency → number of days.
    #
    # The producer of this field is 3.2 `plan_stakeholder_engagement`, which assigns it
    # from QUADRANT_STRATEGIES: Weekly / At milestones / Bi-weekly / Monthly /
    # Quarterly. The set below originally shared exactly ONE value with that list, so a
    # stakeholder on a Bi-weekly or Monthly cadence yielded `days_limit = None`, fell
    # through both overdue branches, and vanished from the queue — after which the tool
    # printed "✅ All communications are on track". Silent degradation is tolerable only
    # when the tool then says LESS, never when it makes a confident positive claim.
    # Matching is case-insensitive because "At milestones" and "At Milestone" are the
    # same cadence written by two authors.
    freq_days = {
        "after each session": 3,      # 3-day grace period
        "weekly": 7,
        "bi-weekly": 14,
        "biweekly": 14,
        "monthly": 30,
        "quarterly": 90,
        "at milestone": None,         # trigger-only
        "at milestones": None,
        "on request": None,
    }
    unknown_frequencies = set()
    # An empty or absent comm_frequency is NOT "On Request": On Request is the
    # analyst's explicit choice of a trigger-only cadence, while empty means no
    # cadence was ever planned. Defaulting the absent key to "On Request"
    # fabricated that choice, and the empty string slipped past the
    # unknown-frequency guard (`if freq_key and ...`) — so a caller building this
    # input from the 4.2 registry (which deliberately carries no comm_frequency)
    # had every stakeholder silently excluded under a clean "on track" verdict.
    no_cadence_roles = []

    # Build the communication queue
    urgent = []       # needed today
    due_soon = []     # within the next 3 days
    triggered = []    # trigger fired
    followup_due = [] # unresolved follow-up from the log

    for sh in stakeholders:
        role = sh.get("role") or sh.get("name") or "—"
        freq = sh.get("comm_frequency", "")
        triggers = sh.get("comm_triggers", [])

        # Determine the date of the last communication. Look the stakeholder up by
        # every identifier they carry, since the log may be keyed by either.
        logged = None
        for key in (sh.get("role"), sh.get("name")):
            candidate = log_by_role.get(str(key).strip().lower()) if key else None
            if candidate and (logged is None or candidate["date"] > logged["date"]):
                logged = candidate

        last_date = parse_date(sh.get("last_communication_date", ""))
        if logged and (not last_date or logged["date"] > last_date):
            last_date = logged["date"]

        # Check overdue status by frequency
        freq_key = str(freq).strip().lower()
        days_limit = freq_days.get(freq_key)
        if not freq_key:
            no_cadence_roles.append(role)
        elif freq_key not in freq_days:
            unknown_frequencies.add(str(freq))
        if days_limit and last_date:
            days_since = (today - last_date).days
            overdue = days_since - days_limit
            if overdue >= 0:
                urgent.append({
                    "role": role,
                    "reason": f"Overdue by {overdue} day(s) (frequency: {freq}, last time: {sh.get('last_communication_date', '—')})",
                    "influence": sh.get("influence", "—"),
                    "last_topic": sh.get("last_communication_topic", ""),
                })
            elif overdue >= -3:
                due_soon.append({
                    "role": role,
                    "reason": f"In {-overdue} day(s) (frequency: {freq})",
                    "influence": sh.get("influence", "—"),
                })
        elif days_limit and not last_date:
            urgent.append({
                "role": role,
                "reason": f"No communication on record yet (frequency: {freq})",
                "influence": sh.get("influence", "—"),
                "last_topic": "",
            })

        # Check triggers
        for event in events:
            event_type = event.get("event_type", "")
            for trigger in triggers:
                if trigger.lower() in event_type.lower() or event_type.lower() in trigger.lower():
                    triggered.append({
                        "role": role,
                        "trigger": trigger,
                        "event": event.get("description", event_type),
                        "event_date": event.get("date", "—"),
                        "influence": sh.get("influence", "—"),
                    })

        # Unresolved follow-ups
        if logged and logged.get("followup"):
            followup_due.append({
                "role": role,
                "status": logged.get("status", "—"),
                "date": logged["date"].strftime("%d.%m.%Y"),
            })

    # -----------------------------------------------------------------------
    # Build the report
    # -----------------------------------------------------------------------
    lines = []
    lines.append(f"# Communication Schedule — Check on {today_date}\n")
    lines.append(f"**Project:** {project_name}  ")
    lines.append(f"**Check date:** {today_date}\n")
    lines.append("---\n")

    # Summary
    total_actions = len(urgent) + len(triggered) + len(followup_due)
    if total_actions == 0:
        if unknown_frequencies or no_cadence_roles:
            # Degrading is fine; making a confident positive claim on top of it is not.
            lines.append("## ⚠️ Schedule Could Not Be Fully Checked\n")
            if unknown_frequencies:
                lines.append(
                    f"No overdue communications among the cadences this tool recognises, "
                    f"but {len(unknown_frequencies)} unrecognised value(s) were skipped: "
                    f"{', '.join(sorted(unknown_frequencies))}. Those stakeholders were "
                    f"NOT evaluated — this is not a clean bill of health.\n"
                )
            if no_cadence_roles:
                lines.append(
                    f"{len(no_cadence_roles)} stakeholder(s) have no communication cadence "
                    f"on record and were NOT evaluated: {', '.join(no_cadence_roles)}. "
                    f"Set `comm_frequency` (the 3.2 plan assigns one per quadrant) to "
                    f"include them in this check.\n"
                )
        else:
            lines.append("## ✅ All Communications Are on Track\n")
            lines.append("No overdue or triggered communications.\n")
    else:
        lines.append(f"## Need Attention Today: {total_actions} stakeholder(s)\n")
        if unknown_frequencies:
            lines.append(
                f"> ⚠️ Skipped {len(unknown_frequencies)} unrecognised cadence(s): "
                f"{', '.join(sorted(unknown_frequencies))}.\n"
            )
        if no_cadence_roles:
            lines.append(
                f"> ⚠️ {len(no_cadence_roles)} stakeholder(s) have no communication cadence "
                f"on record and were NOT evaluated: {', '.join(no_cadence_roles)}.\n"
            )

    # Urgent (overdue) — ranked by influence (High first). Sorting the raw
    # "High"/"Medium"/"Low" label alphabetically is wrong: alphabetical order
    # (High < Low < Medium) does not match the ordinal, so map to a numeric rank.
    influence_rank = {"High": 3, "Medium": 2, "Low": 1}
    if urgent:
        lines.append("---\n")
        lines.append("## 🔴 Urgent — Overdue\n")
        for item in sorted(urgent, key=lambda x: influence_rank.get(x.get("influence"), 0), reverse=True):
            lines.append(f"**{item['role']}** (influence: {item['influence']})  ")
            lines.append(f"- {item['reason']}  ")
            if item.get("last_topic"):
                lines.append(f"- Last topic: {item['last_topic']}  ")
            lines.append("")

    # Triggered events
    if triggered:
        lines.append("---\n")
        lines.append("## 🟡 Trigger Fired\n")
        seen = set()
        for item in triggered:
            key = (item["role"], item["trigger"])
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"**{item['role']}** (influence: {item['influence']})  ")
            lines.append(f"- Trigger: «{item['trigger']}»  ")
            lines.append(f"- Event: {item['event']} ({item['event_date']})  ")
            lines.append("")

    # Follow-up
    if followup_due:
        lines.append("---\n")
        lines.append("## 🔄 Unresolved Follow-ups\n")
        for item in followup_due:
            lines.append(f"**{item['role']}** — status: {item['status']}, date: {item['date']}")
        lines.append("")

    # Coming soon (within the next 3 days)
    if due_soon:
        lines.append("---\n")
        lines.append("## 🟢 Coming Soon (Next 3 Days)\n")
        for item in due_soon:
            lines.append(f"- **{item['role']}**: {item['reason']}")
        lines.append("")

    # Past events
    if events:
        lines.append("---\n")
        lines.append("## Events Since Last Check\n")
        for ev in events:
            lines.append(f"- [{ev.get('date', '—')}] **{ev.get('event_type', '—')}**: {ev.get('description', '—')}")
        lines.append("")

    lines.append("---\n")
    lines.append(
        f"*BABOK 4.4 — Communication Schedule Check. "
        f"Project: {project_name}. Date: {today_date}.*\n"
    )

    content = "\n".join(lines)

    meta = (
        f"<!--\n"
        f"  BABOK 4.4 — Communication Schedule\n"
        f"  Project: {project_name}\n"
        f"  Check date: {today_date}\n"
        f"  Urgent: {len(urgent)}, Triggered: {len(triggered)}, Follow-up: {len(followup_due)}\n"
        f"-->\n\n"
    )

    return save_artifact(meta + content, prefix="4_4_comm_schedule", project_id=project_name)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
