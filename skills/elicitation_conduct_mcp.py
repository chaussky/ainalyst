"""
BABOK 4.2 — Conduct Elicitation
MCP tools for processing elicitation results.

Tools:
  - process_elicitation_results   — save the structured result of a session
                                    (+ elicitation_results.json with risks, read by 6.3)
  - compare_elicitation_results   — compare multiple sessions, find contradictions
  - save_cr_elicitation_analysis  — elicitation analysis in the context of a Change Request
  - update_stakeholder_registry   — merge newly discovered stakeholders into the living registry

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date
from typing import Literal
from mcp.server.fastmcp import FastMCP
from skills.common import (write_json_artifact,
    save_artifact, logger, data_path, normalize_project_id,
    parse_json_dict, parse_json_dict_list, parse_json_list,
    update_stakeholder_registry_file, guard_artifact_errors)

mcp = FastMCP("BABOK_Elicitation_Conduct")


# The single structured artifact 6.3 `import_risks_from_context` reads. The name must
# match the consumer exactly: it builds the path with the same normalize_project_id and
# data_path (finding 7.4-A and 7.6-A were both consumers reading a filename nobody wrote).
ELICITATION_RESULTS_FILENAME = "elicitation_results.json"


def _elicitation_results_path(project_name: str) -> str:
    safe = normalize_project_id(project_name)
    return data_path(project_name, f"{safe}_{ELICITATION_RESULTS_FILENAME}")


def _parse_session_risks(risks_json: str, default_stakeholder: str):
    """Parses `risks_json` into [{"description", "stakeholder"}]. Returns (risks, error).

    Tolerant at the boundary, strict in what is stored: a bare string becomes a
    description, and the `risk`/`source` spellings 6.3 accepts on read are accepted here
    too. The input is written by an LLM, and CH4-A was exactly the class where a
    wrong-but-meaningful shape crashed instead of being handled.
    """
    raw, error = parse_json_list(
        risks_json, "risks_json",
        example='[{"description": "The legacy API may not survive the load"}]')
    if error:
        return None, error

    risks = []
    for item in raw:
        if isinstance(item, str):
            description, stakeholder = item.strip(), default_stakeholder
        elif isinstance(item, dict):
            description = str(item.get("description") or item.get("risk") or "").strip()
            stakeholder = (str(item.get("stakeholder") or item.get("source") or "").strip()
                           or default_stakeholder)
        else:
            return None, (
                "❌ `risks_json`: every item must be an object or a string.\n"
                'Example: [{"description": "The legacy API may not survive the load"}]'
            )
        if description:
            risks.append({"description": description, "stakeholder": stakeholder})

    # The caller supplied items but none carried a description under any accepted
    # spelling — i.e. the wrong FIELD NAME, this repo's most repeated defect class.
    # Dropping them silently and still answering "✅ saved" is the worst outcome: the
    # BA believes the risks were recorded and 6.3 later finds nothing.
    if raw and not risks:
        return None, (
            "❌ `risks_json`: no risk had a description. Accepted keys are "
            "`description` (or `risk`) and `stakeholder` (or `source`); a bare string "
            'is read as the description.\n'
            'Example: [{"description": "The legacy API may not survive the load"}]'
        )
    return risks, ""


def _record_session_risks(project_name: str, session_date: str, stakeholder_role: str,
                          session_type: str, risks: list) -> bool:
    """Accumulates this session's risks into the one JSON per project that 6.3 reads.

    Sessions are keyed by (date, role, type): re-running one REPLACES its slice in place
    rather than appending duplicates. The flat top-level `risks_mentioned` — the exact
    shape 6.3 consumes — is rebuilt from all sessions on every write, so it can never
    drift from `sessions`.

    No risks: the file is neither created NOR modified. An omission means the caller
    supplied nothing this time, not that recorded risks should be deleted.
    """
    if not risks:
        return False

    path = _elicitation_results_path(project_name)
    today = date.today().strftime("%d.%m.%Y")
    data = {"project": project_name, "created": today, "updated": today, "sessions": []}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                # Validate ELEMENTS, not just the container: the loop below calls
                # `s.get(...)` and unpacks `{**risk}`, so a stored file whose sessions
                # list holds a string raised AttributeError/TypeError — and because this
                # runs BEFORE the Markdown is saved, the BA lost the whole session
                # report too. Corrupt entries are dropped, never fatal.
                sessions = [
                    s for s in loaded.get("sessions", [])
                    if isinstance(s, dict) and isinstance(s.get("risks_mentioned"), list)
                ]
                for s in sessions:
                    s["risks_mentioned"] = [
                        r for r in s["risks_mentioned"] if isinstance(r, dict)
                    ]
                loaded["sessions"] = sessions
                # A file with a top-level `risks_mentioned` but no `sessions` is what a
                # BA would hand-write while the producer did not exist. Overwriting it
                # destroyed their data; the project rule is "never delete data", so the
                # orphaned risks are migrated into a session instead.
                if not sessions and isinstance(loaded.get("risks_mentioned"), list):
                    orphans = [r for r in loaded["risks_mentioned"] if isinstance(r, dict)]
                    if orphans:
                        loaded["sessions"] = [{
                            "session_date": "", "stakeholder_role": "",
                            "session_type": "Imported",
                            "risks_mentioned": orphans,
                        }]
                data = loaded
        except (json.JSONDecodeError, OSError):
            pass  # unreadable/corrupt: start fresh rather than blocking the BA

    entry = {
        "session_date": session_date,
        "stakeholder_role": stakeholder_role,
        "session_type": session_type,
        "risks_mentioned": risks,
    }
    key = (session_date, stakeholder_role, session_type)
    sessions = data.setdefault("sessions", [])
    # Replace-in-place only on a FULLY specified key. A blank component means
    # "unspecified", not "the same session", and collapsing on it silently discarded
    # the earlier slice.
    if all(key):
        for i, s in enumerate(sessions):
            if (s.get("session_date"), s.get("stakeholder_role"),
                    s.get("session_type")) == key:
                sessions[i] = entry  # replace in place, preserving order
                break
        else:
            sessions.append(entry)
    else:
        sessions.append(entry)

    data["risks_mentioned"] = [
        {**risk, "session_date": s.get("session_date", "")}
        for s in sessions for risk in s.get("risks_mentioned", [])
    ]
    data["updated"] = today
    data.setdefault("created", today)

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write_json_artifact(path, data)
        return True
    except OSError as e:
        logger.warning(f"4.2 Could not persist elicitation results JSON: {e}")
        return False


# ---------------------------------------------------------------------------
# 4.2.1 — Save structured results of a single session
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def process_elicitation_results(
    project_name: str,
    session_date: str,
    stakeholder_role: str,
    session_type: Literal["Interview", "Workshop", "Survey", "Observation", "Document Analysis",
                          "Brainstorming", "Prototyping", "Focus Group", "Benchmarking", "Experiments"],
    stakeholder_profile_json: str,
    pains_json: str,
    requirements_json: str,
    gaps_and_signals: str,
    ba_recommendations: str,
    maturity_level: Literal["Low", "Medium", "Good", "High"],
    maturity_notes: str,
    risks_json: str = "[]",
) -> str:
    """
    BABOK 4.2 — Saves the structured results of a single elicitation session.
    The result is passed on to task 4.3 (confirmation).

    Args:
        project_name:              Project name.
        session_date:              Session date in DD.MM.YYYY format.
        stakeholder_role:          Stakeholder role (job title / function).
        session_type:              Type of elicitation session.
        stakeholder_profile_json:  Stakeholder profile. Format:
                                   {
                                     "participation_type": "Decision maker / Influencer / End user",
                                     "influence": "High / Medium / Low",
                                     "interest": "High / Medium / Low",
                                     "attitude": "Champion / Neutral / Blocker",
                                     "key_expectations": "text",
                                     "key_concerns": "text",
                                     "related_stakeholders": ["role 1", "role 2"]
                                   }
        pains_json:                List of pain points. Format:
                                   [
                                     {
                                       "title": "short title",
                                       "description": "context and substance",
                                       "frequency": "how often",
                                       "business_impact": "impact on the business",
                                       "quote": "verbatim quote if available"
                                     }
                                   ]
        requirements_json:         Requirements by type. Format:
                                   {
                                     "functional": ["FR-001: ...", "FR-002: ..."],
                                     "non_functional": ["NFR-001: ..."],
                                     "constraints": ["..."],
                                     "business_rules": ["..."]
                                   }
        gaps_and_signals:          Analysis of blind spots and hidden signals.
                                   Text describing unspoken issues, open topics,
                                   contradictions, and political signals.
        ba_recommendations:        Specific BA recommendations: what to clarify,
                                   with whom, whether a follow-up is needed.
        maturity_level:            Overall maturity level of the requirements.
        maturity_notes:            Comment on the maturity assessment.
        risks_json:                Risks the stakeholder raised in this session. Optional.
                                   Format: [{"description": "...", "stakeholder": "..."}]
                                   Example: '[{"description": "The legacy API may not survive the load", "stakeholder": "Architect"}]'
                                   `stakeholder` defaults to stakeholder_role. A bare
                                   string is accepted and read as the description.
                                   Consumed by 6.3 `import_risks_from_context`.

    Returns:
        Path to the saved elicitation results file.
    """
    logger.info(f"4.2 Saving elicitation results: project='{project_name}', type='{session_type}'")

    profile, error = parse_json_dict(
        stakeholder_profile_json, "stakeholder_profile_json",
        example='{"participation_type": "Decision maker", "influence": "High"}')
    if error:
        return error

    pains, error = parse_json_dict_list(
        pains_json, "pains_json",
        example='[{"title": "...", "description": "...", "business_impact": "..."}]')
    if error:
        return error

    reqs, error = parse_json_dict(
        requirements_json, "requirements_json",
        example='{"functional": ["FR-001: ..."], "non_functional": ["NFR-001: ..."]}')
    if error:
        return error

    risks, error = _parse_session_risks(risks_json, stakeholder_role)
    if error:
        return error

    # Build the pain points block
    pains_md = ""
    for i, p in enumerate(pains, 1):
        pains_md += f"\n### Pain point {i}: {p.get('title', '—')}\n"
        pains_md += f"- **Description:** {p.get('description', '—')}\n"
        pains_md += f"- **Frequency:** {p.get('frequency', '—')}\n"
        pains_md += f"- **Business impact:** {p.get('business_impact', '—')}\n"
        if p.get('quote'):
            pains_md += f"- **Quote:** *«{p['quote']}»*\n"

    # Build the requirements block
    def req_list(items):
        return "\n".join(f"- {r}" for r in items) if items else "- None identified"

    # Build the profile block
    related = ", ".join(profile.get("related_stakeholders", [])) or "None identified"

    risks_md = ("\n".join(f"- {r['description']} — *{r['stakeholder']}*" for r in risks)
                if risks else "- None mentioned")

    content = f"""# Elicitation Results (Unconfirmed)

**Project:** {project_name}
**Session date:** {session_date}
**Session type:** {session_type}
**Stakeholder:** {stakeholder_role}
**Status:** Unconfirmed results → passed to task 4.3

---

## 1. Stakeholder Profile

| Parameter | Value |
| :--- | :--- |
| **Participation type** | {profile.get('participation_type', '—')} |
| **Influence** | {profile.get('influence', '—')} |
| **Interest** | {profile.get('interest', '—')} |
| **Attitude toward the project** | {profile.get('attitude', '—')} |
| **Key expectations** | {profile.get('key_expectations', '—')} |
| **Key concerns** | {profile.get('key_concerns', '—')} |
| **Related stakeholders** | {related} |

---

## 2. Needs and Pain Points
{pains_md}

---

## 3. Requirements

### Functional Requirements
{req_list(reqs.get('functional', []))}

### Non-Functional Requirements
{req_list(reqs.get('non_functional', []))}

### Constraints
{req_list(reqs.get('constraints', []))}

### Business Rules
{req_list(reqs.get('business_rules', []))}

---

## 4. Blind Spots and Hidden Signals

{gaps_and_signals}

---

## 5. Risks Mentioned by the Stakeholder

{risks_md}

---

## 6. BA Recommendations

{ba_recommendations}

---

## 7. Requirements Maturity Assessment

**Overall level:** {maturity_level}

{maturity_notes}
"""

    # Structured output for 6.3 import_risks_from_context. The Markdown below is for
    # people; this file is the machine contract, and 6.3 is its only consumer today.
    risks_saved = _record_session_risks(
        project_name, session_date, stakeholder_role, session_type, risks)

    # The session date stays in the name — it distinguishes sessions within a project.
    suffix = save_artifact(
        content,
        f"4_2_elicitation_results_{session_date.replace('.', '-')}",
        project_id=project_name,
    )
    # The Markdown prints the risks either way, so a silent persist failure would tell
    # the BA the session was recorded while 6.3 later finds nothing. Same reasoning as
    # the stakeholder registry a few lines down — the two writers must not disagree.
    if risks and not risks_saved:
        return (
            f"⚠️ Elicitation results saved, but the risk file for 6.3 could NOT be "
            f"written — the risks below are in the report only, and "
            f"`import_risks_from_context` will not see them.{suffix}"
        )
    return f"✅ Elicitation results saved.{suffix}"


# ---------------------------------------------------------------------------
# 4.2.2 — Save the cross-analysis of multiple sessions
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def compare_elicitation_results(
    project_name: str,
    sessions_summary: str,
    contradictions: str,
    requirements_registry_json: str,
    political_map: str,
    follow_up_plan: str,
) -> str:
    """
    BABOK 4.2 — Saves the cross-analysis of multiple elicitation sessions.

    Args:
        project_name:                Project name.
        sessions_summary:            Brief description of the analyzed sessions
                                     (who, when, type).
        contradictions:              Description of contradictions between stakeholders:
                                     factual, priority-related, coverage gaps.
        requirements_registry_json:  Consolidated requirements registry. Format:
                                     [
                                       {
                                         "id": "FR-001",
                                         "requirement": "text",
                                         "sources": ["Stakeholder A", "Stakeholder B"],
                                         "priority": "High / Medium / Low / Undetermined",
                                         "status": "Agreed / Needs confirmation / Contradiction",
                                         "notes": "note"
                                       }
                                     ]
        political_map:               Observations on political dynamics among
                                     stakeholders and risks to the project.
        follow_up_plan:              Plan for further elicitation: questions, stakeholders,
                                     formats, priorities.

    Returns:
        Path to the saved cross-analysis file.
    """
    logger.info(f"4.2 Cross-analysis: project='{project_name}'")

    registry, error = parse_json_dict_list(
        requirements_registry_json, "requirements_registry_json",
        example='[{"id": "FR-001", "requirement": "...", "sources": ["..."], '
                '"priority": "High", "status": "Agreed"}]')
    if error:
        return error

    # Build the registry table
    reg_rows = "\n".join([
        f"| {r.get('id','—')} | {r.get('requirement','—')} | "
        f"{', '.join(r.get('sources',[]))} | {r.get('priority','—')} | "
        f"{r.get('status','—')} | {r.get('notes','—')} |"
        for r in registry
    ])

    reg_table = (
        "| ID | Requirement | Sources | Priority | Status | Notes |\n"
        "| :--- | :--- | :--- | :---: | :--- | :--- |\n"
        + reg_rows
    )

    content = f"""# Cross-Analysis of Elicitation Results

**Project:** {project_name}
**Analysis date:** {date.today().strftime("%d.%m.%Y")}
**Status:** Unconfirmed results → passed to task 4.3

---

## 1. Analyzed Sessions

{sessions_summary}

---

## 2. Contradictions Between Stakeholders

{contradictions}

---

## 3. Consolidated Requirements Registry

{reg_table}

---

## 4. Political Map

{political_map}

---

## 5. Further Elicitation Plan

{follow_up_plan}
"""

    suffix = save_artifact(content, "4_2_cross_analysis", project_id=project_name)
    return f"✅ Cross-analysis saved.{suffix}"


# ---------------------------------------------------------------------------
# 4.2.3 — Save the elicitation analysis in the context of a Change Request
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def save_cr_elicitation_analysis(
    project_name: str,
    cr_description: str,
    affected_artifacts_json: str,
    outdated_data: str,
    follow_up_questions: str,
    scope_assessment: str,
    workshop_needed: bool,
    workshop_notes: str = "",
) -> str:
    """
    BABOK 4.2 — Saves the elicitation analysis in the context of a Change Request.

    Args:
        project_name:              Project name.
        cr_description:            CR description: what is changing, initiator, reason.
        affected_artifacts_json:   Affected artifacts. Format:
                                   [
                                     {
                                       "artifact": "name / ID",
                                       "type": "Profile / Pain point / FR / NFR / User Story",
                                       "affected": true,
                                       "change_type": "Update / Remove / Freeze"
                                     }
                                   ]
        outdated_data:             Description of outdated data and what to do about it.
        follow_up_questions:       New elicitation questions: what, with whom,
                                   priority, format.
        scope_assessment:          Assessment of the scope and risks of further elicitation.
        workshop_needed:           Whether a workshop is needed for alignment.
        workshop_notes:            Participant list and agenda for the workshop (if needed).

    Returns:
        Path to the saved CR analysis file.
    """
    logger.info(f"4.2 CR analysis: project='{project_name}'")

    artifacts, error = parse_json_dict_list(
        affected_artifacts_json, "affected_artifacts_json",
        example='[{"artifact": "FR-001", "type": "FR", "affected": true, '
                '"change_type": "Update"}]')
    if error:
        return error

    # Build the artifacts table
    art_rows = "\n".join([
        f"| {a.get('artifact','—')} | {a.get('type','—')} | "
        f"{'✅' if a.get('affected') else '—'} | {a.get('change_type','—')} |"
        for a in artifacts
    ])

    art_table = (
        "| Artifact | Type | Affected | Action |\n"
        "| :--- | :--- | :---: | :--- |\n"
        + art_rows
    )

    workshop_block = ""
    if workshop_needed:
        workshop_block = f"\n## 6. Workshop\n\n**Needed:** Yes\n\n{workshop_notes}\n"
    else:
        workshop_block = "\n## 6. Workshop\n\n**Needed:** No\n"

    content = f"""# Elicitation Analysis in the Context of a Change Request

**Project:** {project_name}
**Analysis date:** {date.today().strftime("%d.%m.%Y")}
**Status:** Requires further elicitation

---

## 1. Change Request Description

{cr_description}

---

## 2. Impact Zone

{art_table}

---

## 3. Outdated Data

{outdated_data}

---

## 4. Further Elicitation Plan

{follow_up_questions}

---

## 5. Scope Assessment

{scope_assessment}
{workshop_block}
"""

    suffix = save_artifact(content, "4_2_cr_elicitation", project_id=project_name)
    return f"✅ CR analysis saved.{suffix}"


# ---------------------------------------------------------------------------
# 4.2.4 — Update the living stakeholder registry
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def update_stakeholder_registry(
    project_name: str,
    session_source: str,
    new_stakeholders_json: str,
) -> str:
    """
    BABOK 4.2 / 3.2 — Updates the project's living stakeholder registry.

    The stakeholder registry is a living document. It starts with 1-2 known people
    (usually the sponsor) and grows after each elicitation session via a chain:
    each stakeholder names the next ones.

    Call this tool after every interview / workshop / document analysis.

    Args:
        project_name:           Project name.
        session_source:         Where the information about the new stakeholders came from.
                                Example: "Interview with J. Smith (CFO), 03/15/2024"
        new_stakeholders_json:  List of new or updated stakeholders. Format:
                                [
                                  {
                                    "name": "J. Doe",
                                    "role": "Head of Procurement",
                                    "department": "Procurement",
                                    "found_through": "J. Smith (CFO)",
                                    "why_important": "Makes decisions on the procurement budget",
                                    "influence": "High / Medium / Low",
                                    "interest": "High / Medium / Low",
                                    "attitude": "Champion / Neutral / Blocker / Unknown",
                                    "coverage_status": "Not covered / Planned / Elicited",
                                    "priority": "Urgent / As planned / Uncertain",
                                    "recommended_format": "Interview / Workshop / Written request",
                                    "notes": "additional information"
                                  }
                                ]

    Returns:
        Path to the updated stakeholder registry file.
    """
    logger.info(f"4.2 Updating stakeholder registry: project='{project_name}', source='{session_source}'")

    incoming, error = parse_json_dict_list(
        new_stakeholders_json, "new_stakeholders_json",
        example='[{"name": "Jane Doe", "role": "Head of Sales", "influence": "High"}]')
    if error:
        return error

    today = date.today().strftime("%d.%m.%Y")

    # -----------------------------------------------------------------------
    # Read the living registry (JSON source of truth), merge, write it back.
    # This is what makes it a living document: the latest artifact always holds
    # the FULL registry, not just the current session's slice.
    # The merge itself lives in common.py so 3.2 can seed the same registry
    # without Chapter 3 depending on Chapter 4.
    # -----------------------------------------------------------------------
    merge_result = update_stakeholder_registry_file(
        project_name, incoming, source=session_source)

    registry = merge_result["registry"]
    existing = registry["stakeholders"]
    added = merge_result["added"]
    updated = merge_result["updated"]
    dup_warnings = merge_result["dup_warnings"]

    # -----------------------------------------------------------------------
    # Render the .md report from the FULL registry.
    # -----------------------------------------------------------------------
    table_header = (
        "| Stakeholder | Role | Department | Found through | Influence | Interest | "
        "Attitude | Coverage status | Priority | Format |\n"
        "| :--- | :--- | :--- | :--- | :---: | :---: | :--- | :--- | :---: | :--- |\n"
    )
    rows = []
    for s in existing:
        rows.append(
            f"| {s.get('name', '—')} | {s.get('role', '—')} | "
            f"{s.get('department', '—')} | {s.get('found_through', '—')} | "
            f"{s.get('influence', '—')} | {s.get('interest', '—')} | "
            f"{s.get('attitude', 'Unknown')} | {s.get('coverage_status', '—')} | "
            f"{s.get('priority', '—')} | {s.get('recommended_format', '—')} |"
        )

    # Changes made in this update — lets the BA see add vs. update at a glance.
    change_lines = [
        f"- **Added:** {len(added)}" + (f" ({', '.join(added)})" if added else ""),
        f"- **Updated:** {len(updated)}" + (f" ({', '.join(updated)})" if updated else ""),
    ]
    changes_block = "\n".join(change_lines)

    # Possible-duplicate warnings (soft, non-blocking).
    dup_block = ""
    if dup_warnings:
        dup_block = "\n## ⚠️ Possible Duplicates\n\n"
        for new_name, existing_name in dup_warnings:
            dup_block += (
                f"- **{new_name}** shares a role with **{existing_name}** already in the registry. "
                f"Possibly the same person as \"{existing_name}\" — please verify.\n"
            )

    # Discovery chain (full registry).
    chain_lines = []
    for s in existing:
        source = s.get('found_through', 'Unknown')
        name = s.get('name', '—')
        role = s.get('role', '—')
        why = s.get('why_important', '')
        chain_lines.append(f"- **{name}** ({role}) ← via: {source}" + (f"\n  > {why}" if why else ""))

    # Not covered — separate action list (full registry).
    uncovered = [s for s in existing if s.get('coverage_status') == 'Not covered']
    urgent = [s for s in uncovered if s.get('priority') == 'Urgent']
    uncovered_block = ""
    if uncovered:
        uncovered_block = "\n## ⚠️ Require Elicitation Coverage\n\n"
        if urgent:
            uncovered_block += "### Urgent\n"
            for s in urgent:
                uncovered_block += (
                    f"- **{s.get('name', '—')}** ({s.get('role', '—')}) — "
                    f"{s.get('recommended_format', 'Interview')}\n"
                    f"  Why important: {s.get('why_important', '—')}\n"
                )
        not_urgent = [s for s in uncovered if s.get('priority') != 'Urgent']
        if not_urgent:
            uncovered_block += "\n### As Planned\n"
            for s in not_urgent:
                uncovered_block += (
                    f"- **{s.get('name', '—')}** ({s.get('role', '—')}) — "
                    f"{s.get('recommended_format', 'Interview')}\n"
                )

    content = f"""# Stakeholder Registry (Living Document)

**Project:** {project_name}
**Last updated:** {today}
**Update source:** {session_source}
**Total stakeholders:** {len(existing)}

---

## Changes in This Update

{changes_block}
{dup_block}
---

## Full Registry (Current)

{table_header}{chr(10).join(rows) if rows else "| — | — | — | — | — | — | — | — | — | — |"}

---

## Discovery Chain

{chr(10).join(chain_lines) if chain_lines else "— No data —"}

{uncovered_block}
---

> This file is updated after every elicitation session.
> The full registry accumulates cumulatively from all updates.
"""

    suffix = save_artifact(content, "4_2_stakeholder_registry", project_id=project_name)
    # The JSON is the source of truth; the Markdown is a rendering of it. Reporting
    # success when the JSON did not persist would tell the BA their session was
    # recorded while the next session silently starts from the old registry.
    # 3.2 already surfaces this on its side — the two writers must not disagree.
    if not merge_result.get("saved"):
        return (
            f"⚠️ Stakeholder registry could NOT be saved to disk — the report below was "
            f"generated, but the changes are not persisted and the next session will not "
            f"see them. Added: {len(added)}, updated: {len(updated)}.{suffix}"
        )
    return (
        f"✅ Stakeholder registry updated. Added: {len(added)}, updated: {len(updated)}. "
        f"Total in registry: {len(existing)}.{suffix}"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
