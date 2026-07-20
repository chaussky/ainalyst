"""
BABOK 5.5 — Approve Requirements
MCP tools for approving requirements and creating a Requirements Baseline.

Tools:
  - prepare_approval_package    — prepare a requirements package for approval
  - record_approval_decision    — record a stakeholder's decision
  - close_approval_condition    — close a satisfied condition (Conditional)
  - check_approval_status       — dashboard of the package's baseline readiness
  - create_requirements_baseline — create the official Requirements Baseline

Storage:
  - Approval decisions: in the 5.1 repository nodes ({project}_traceability_repo.json)
  - Baseline history: {project}_approval_history.json
  - Approval Record: saved via save_artifact

Integration:
  In:  5.1 repository (graph+statuses), 5.3 priorities, 5.4 CR Records, 4.2 stakeholders
  Out: Approval Record → 4.4 (communication), Chapter 6 (development)
       approved statuses in the 5.1 repository

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date, datetime
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import save_artifact, logger, DATA_DIR, data_path, normalize_project_id

mcp = FastMCP("BABOK_Requirements_Approve")

REPO_FILENAME = "traceability_repo.json"
APPROVAL_HISTORY_FILENAME = "approval_history.json"

# Valid decision statuses
VALID_DECISIONS = {"approved", "conditional", "rejected", "abstained"}

# Requirement statuses in the 5.5 pipeline
STATUS_PENDING = "pending_approval"
STATUS_APPROVED = "approved"
STATUS_CONDITIONAL = "conditional_approved"
STATUS_REJECTED = "rejected"


# ---------------------------------------------------------------------------
# Utilities — file layer
# ---------------------------------------------------------------------------

def _repo_path(project_name: str) -> str:
    safe = normalize_project_id(project_name)
    return data_path(project_name, f"{safe}_{REPO_FILENAME}")


def _approval_history_path(project_name: str) -> str:
    safe = normalize_project_id(project_name)
    return data_path(project_name, f"{safe}_{APPROVAL_HISTORY_FILENAME}")


def _load_repo(project_name: str) -> dict:
    path = _repo_path(project_name)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"project": project_name, "requirements": [], "links": [], "history": []}


def _save_repo(project_name: str, repo: dict) -> None:
    path = _repo_path(project_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    repo["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)


def _load_approval_history(project_name: str) -> dict:
    path = _approval_history_path(project_name)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"project": project_name, "packages": {}, "baselines": []}


def _save_approval_history(project_name: str, history: dict) -> None:
    path = _approval_history_path(project_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    history["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def _find_node(repo: dict, node_id: str) -> Optional[dict]:
    for r in repo["requirements"]:
        if r["id"] == node_id:
            return r
    return None


def _get_package(history: dict, package_id: str) -> Optional[dict]:
    return history["packages"].get(package_id)


def _get_req_approval_summary(package: dict, req_id: str) -> dict:
    """Collects all decisions for a specific requirement across all stakeholders."""
    decisions = []
    for sh_name, sh_data in package.get("stakeholder_decisions", {}).items():
        for rd in sh_data.get("req_decisions", []):
            if rd["req_id"] == req_id:
                decisions.append({
                    "stakeholder": sh_name,
                    "raci": sh_data.get("raci", "consulted"),
                    "decision": rd["decision"],
                    "condition_text": rd.get("condition_text", ""),
                    "condition_closed": rd.get("condition_closed", False),
                    "rejection_reason": rd.get("rejection_reason", ""),
                })
    return {"req_id": req_id, "decisions": decisions}


def _compute_req_status(req_id: str, package: dict) -> str:
    """Computes the final status of a requirement based on all stakeholder decisions."""
    decisions_by_stakeholder = []
    for sh_name, sh_data in package.get("stakeholder_decisions", {}).items():
        raci = sh_data.get("raci", "consulted")
        for rd in sh_data.get("req_decisions", []):
            if rd["req_id"] == req_id:
                decisions_by_stakeholder.append({
                    "raci": raci,
                    "decision": rd["decision"],
                    "condition_closed": rd.get("condition_closed", False),
                })

    if not decisions_by_stakeholder:
        return STATUS_PENDING

    # Rejected from Accountable/Responsible → rejected
    for d in decisions_by_stakeholder:
        if d["decision"] == "rejected" and d["raci"] in ("accountable", "responsible"):
            return STATUS_REJECTED

    # An open conditional from any A/R → conditional_approved
    for d in decisions_by_stakeholder:
        if d["decision"] == "conditional" and not d["condition_closed"] and d["raci"] in ("accountable", "responsible"):
            return STATUS_CONDITIONAL

    # All A/R approved (or abstained/consulted-rejected) → approved
    ar_decisions = [d for d in decisions_by_stakeholder if d["raci"] in ("accountable", "responsible")]
    if ar_decisions and all(
        d["decision"] in ("approved", "abstained") or
        (d["decision"] == "conditional" and d["condition_closed"])
        for d in ar_decisions
    ):
        return STATUS_APPROVED

    return STATUS_PENDING


MIN_APPROVED_PCT = 70


def _baseline_gate(package: dict) -> dict:
    """THE readiness predicate for a baseline — the single source of truth.

    Used by BOTH `check_approval_status` (which renders the "Ready / Not ready"
    verdict) and `create_requirements_baseline` (which enforces it). These two used
    to compute readiness separately and had already drifted: the dashboard applied
    four gates, creation only two, so a package the dashboard called "🔴 Not ready"
    could still be baselined — in the worst case producing an EMPTY baseline with no
    warning. Any change to what "ready" means belongs here, once.

    Returns the raw facts; callers do their own formatting.
    """
    req_ids = package.get("req_ids", [])
    statuses = {rid: _compute_req_status(rid, package) for rid in req_ids}

    counts = {STATUS_APPROVED: 0, STATUS_CONDITIONAL: 0, STATUS_REJECTED: 0, STATUS_PENDING: 0}
    for status in statuses.values():
        counts[status] = counts.get(status, 0) + 1

    total = len(req_ids)
    approved_pct = round(counts[STATUS_APPROVED] / total * 100) if total else 0

    ar_rejections = []
    open_conditions = []
    overdue_conditions = []
    today = date.today()

    for sh_name, sh_data in package.get("stakeholder_decisions", {}).items():
        raci = sh_data.get("raci", "consulted")
        for rd in sh_data.get("req_decisions", []):
            if rd["decision"] == "rejected" and raci in ("accountable", "responsible"):
                ar_rejections.append({
                    "req_id": rd["req_id"],
                    "stakeholder": sh_name,
                    "raci": raci,
                    "reason": rd.get("rejection_reason", "—"),
                })
            if rd["decision"] == "conditional" and not rd.get("condition_closed"):
                entry = {
                    "req_id": rd["req_id"],
                    "stakeholder": sh_name,
                    "condition_text": rd.get("condition_text", "—"),
                    "condition_deadline": rd.get("condition_deadline", ""),
                    "condition_owner": rd.get("condition_owner", "—"),
                }
                open_conditions.append(entry)
                if rd.get("condition_deadline"):
                    try:
                        if date.fromisoformat(rd["condition_deadline"]) < today:
                            entry["overdue"] = True
                            overdue_conditions.append(entry)
                    except ValueError:
                        pass

    pending_reqs = [rid for rid in req_ids if statuses[rid] == STATUS_PENDING]
    # An empty approved set is 0% and is therefore blocked by this same rule.
    low_approval = approved_pct < MIN_APPROVED_PCT

    return {
        "statuses": statuses,
        "counts": counts,
        "total": total,
        "approved_pct": approved_pct,
        "ar_rejections": ar_rejections,
        "pending_reqs": pending_reqs,
        "open_conditions": open_conditions,
        "overdue_conditions": overdue_conditions,
        "low_approval": low_approval,
        "can_baseline": not (ar_rejections or pending_reqs or overdue_conditions or low_approval),
    }


def _get_cr_context(repo: dict, req_id: str) -> list:
    """Looks for CRs affecting the requirement (modifies links)."""
    cr_refs = []
    for lnk in repo.get("links", []):
        if lnk.get("to") == req_id and lnk.get("relation") == "modifies":
            cr_node = _find_node(repo, lnk["from"])
            if cr_node and cr_node.get("type") == "change_request":
                cr_refs.append({
                    "cr_id": cr_node["id"],
                    "title": cr_node.get("title", "—"),
                    "status": cr_node.get("status", "unknown"),
                    "decision": (cr_node.get("decision") or {}).get("verdict", "—"),
                })
    return cr_refs


# ---------------------------------------------------------------------------
# 5.5.1 — Prepare a package for approval
# ---------------------------------------------------------------------------

@mcp.tool()
def prepare_approval_package(
    project_name: str,
    package_id: str,
    package_title: str,
    req_ids_json: str,
    approach: Literal["predictive", "agile"],
    audience: Literal["business", "developer", "regulator", "all"] = "all",
    sprint_number: str = "",
) -> str:
    """
    BABOK 5.5 — Step 1: Prepare a requirements package for approval.

    Gathers requirements from the 5.1 repository, adds context from 5.3 and 5.4,
    and builds an Approval Package for stakeholders.

    Args:
        project_name:   Project name.
        package_id:     Unique package ID. Recommended format: APKG-001.
        package_title:  Package title (e.g.: "Feature: User Onboarding").
        req_ids_json:   JSON list of requirement IDs for the package.
                        Example: '["FR-001", "FR-002", "NFR-001"]'
        approach:       Methodology: predictive (Waterfall) or agile (Scrum/Kanban).
        audience:       Package audience:
                        - business: business requirements and acceptance criteria
                        - developer: functional + non-functional requirements
                        - regulator: compliance requirements with traceability
                        - all: full package for all audiences
        sprint_number:  Sprint number (agile only, e.g.: "5").

    Returns:
        A Markdown Approval Package to hand off to stakeholders.
        Creates a package entry in {project}_approval_history.json.
    """
    logger.info(f"prepare_approval_package: {package_id} / {project_name}")

    try:
        req_ids = json.loads(req_ids_json)
    except json.JSONDecodeError:
        return "❌ Error: `req_ids_json` must be a valid JSON list. Example: '[\"FR-001\"]'"

    if not req_ids:
        return "❌ Error: the requirement list cannot be empty."

    repo = _load_repo(project_name)
    history = _load_approval_history(project_name)

    # Check: does the package already exist?
    if package_id in history["packages"]:
        return (
            f"⚠️ Package `{package_id}` already exists for project `{project_name}`.\n"
            f"Use a different ID, or review the existing package via `check_approval_status`."
        )

    # Check: do the requirements exist?
    missing = [rid for rid in req_ids if not _find_node(repo, rid)]
    if missing:
        return (
            f"⚠️ The following requirements were not found in the repository: {missing}\n"
            f"Check the ID, or add the requirements via `init_traceability_repo` (5.1)."
        )

    # Gather requirement data
    req_details = []
    cr_warnings = []
    for rid in req_ids:
        node = _find_node(repo, rid)
        cr_refs = _get_cr_context(repo, rid)
        if cr_refs:
            open_crs = [c for c in cr_refs if c["status"] in ("open", "under_change")]
            if open_crs:
                cr_warnings.append((rid, open_crs))
        req_details.append({
            "id": rid,
            "title": node.get("title", "—"),
            "type": node.get("type", "functional"),
            "description": node.get("description", ""),
            "status": node.get("status", "unknown"),
            "priority": node.get("priority", "—"),
            "version": node.get("version", "1.0"),
            "owner": node.get("owner", "—"),
            "acceptance_criteria": node.get("acceptance_criteria", ""),
            "cr_refs": cr_refs,
        })

    # Create the package entry in approval_history
    package_record = {
        "package_id": package_id,
        "package_title": package_title,
        "approach": approach,
        "audience": audience,
        "sprint_number": sprint_number,
        "req_ids": req_ids,
        "created_date": str(date.today()),
        "stakeholder_decisions": {},
        "baseline_version": None,
        "status": "open",
    }
    history["packages"][package_id] = package_record
    _save_approval_history(project_name, history)

    # Update requirement statuses to pending_approval in the 5.1 repository
    for rid in req_ids:
        node = _find_node(repo, rid)
        if node:
            node["status"] = STATUS_PENDING
    _save_repo(project_name, repo)

    # Build the Approval Package
    approach_label = "Predictive / Waterfall" if approach == "predictive" else "Agile"
    sprint_label = f" | Sprint: {sprint_number}" if sprint_number else ""

    lines = [
        f"<!-- BABOK 5.5 — Approval Package, Project: {project_name}, Package: {package_id}, Date: {date.today()} -->",
        "",
        f"# Approval Package: {package_title}",
        f"**Project:** {project_name}  ",
        f"**Package:** {package_id}  ",
        f"**Methodology:** {approach_label}{sprint_label}  ",
        f"**Audience:** {audience}  ",
        f"**Date:** {date.today()}  ",
        f"**Requirements in the package:** {len(req_ids)}  ",
        "",
        "---",
        "",
    ]

    # Warnings about open CRs
    if cr_warnings:
        lines += ["## ⚠️ Warnings: open Change Requests", ""]
        for rid, open_crs in cr_warnings:
            cr_list = ", ".join(f"`{c['cr_id']}` ({c['status']})" for c in open_crs)
            lines.append(f"- `{rid}` is affected by open CRs: {cr_list}")
        lines += ["", "Recommend closing the CR (5.4) before approval.", ""]

    # Requirements by type (filtered by audience)
    if audience == "business":
        filtered = [r for r in req_details if r["type"] in ("business", "stakeholder")]
        if not filtered:
            filtered = req_details
    elif audience == "developer":
        filtered = [r for r in req_details if r["type"] in ("functional", "non_functional", "transition")]
        if not filtered:
            filtered = req_details
    elif audience == "regulator":
        filtered = [r for r in req_details if r.get("regulatory") or "compliance" in r.get("title", "").lower()]
        if not filtered:
            filtered = req_details
    else:
        filtered = req_details

    lines += ["## Requirements for approval", ""]

    for req in filtered:
        priority_str = f" | Priority: {req['priority']}" if req['priority'] != "—" else ""
        lines += [
            f"### {req['id']}: {req['title']}",
            f"**Type:** {req['type']} | **Version:** {req['version']}{priority_str}  ",
            f"**Owner:** {req['owner']}  ",
        ]
        if req.get("description"):
            lines += ["", req["description"], ""]
        if req.get("acceptance_criteria"):
            lines += [f"**Acceptance criteria:** {req['acceptance_criteria']}", ""]
        if req["cr_refs"]:
            cr_info = "; ".join(f"{c['cr_id']} ({c['status']}/{c['decision']})" for c in req["cr_refs"])
            lines += [f"**CR history:** {cr_info}", ""]
        lines.append("")

    # Instructions for stakeholders
    if approach == "predictive":
        instruction = (
            "Please review the requirements and provide a decision for each:\n"
            "- **Approved** — agreed without reservations\n"
            "- **Conditional** — agreed subject to a condition (state the condition)\n"
            "- **Rejected** — not agreed (state the reason)\n"
            "- **Abstained** — abstaining\n\n"
            "Response deadline: per the project's governance plan."
        )
    else:
        sprint_ref = f" sprint {sprint_number}" if sprint_number else ""
        instruction = (
            f"For Sprint Planning{sprint_ref}. The Product Owner reviews and approves the backlog.\n"
            "Requirements accepted into the sprint will get status Approved and join the Sprint Baseline."
        )

    lines += [
        "---",
        "",
        "## Instructions for stakeholders",
        "",
        instruction,
        "",
        "---",
        "",
        "## Next step",
        "",
        f"Once stakeholder responses are in — call `record_approval_decision`:",
        f"  - `project_name`: \"{project_name}\"",
        f"  - `package_id`: \"{package_id}\"",
        f"  - `stakeholder_name`: the stakeholder's name",
        f"  - `decision`: approved / conditional / rejected / abstained",
    ]

    artifact_content = "\n".join(lines)
    save_path = save_artifact(artifact_content, prefix=f"5_5_approval_package_{package_id}", project_id=project_name)

    return artifact_content + save_path


# ---------------------------------------------------------------------------
# 5.5.2 — Record a stakeholder's decision
# ---------------------------------------------------------------------------

@mcp.tool()
def record_approval_decision(
    project_name: str,
    package_id: str,
    stakeholder_name: str,
    stakeholder_raci: Literal["accountable", "responsible", "consulted"],
    decision: Literal["approved", "conditional", "rejected", "abstained"],
    req_decisions_json: str = "[]",
    rejection_reason: str = "",
    comment: str = "",
) -> str:
    """
    BABOK 5.5 — Step 2: Record a stakeholder's decision on the package.

    Called separately for each stakeholder (similar to add_stakeholder_scores in 5.3).
    On rejected — automatically analyzes context from 5.3 and 5.4 to flag conflicts.

    Args:
        project_name:       Project name.
        package_id:         Package ID (from prepare_approval_package).
        stakeholder_name:   The stakeholder's name or role.
        stakeholder_raci:   RACI role: accountable / responsible / consulted.
                            Rejected from accountable/responsible = a baseline blocker.
                            Rejected from consulted = input for risk assessment.
        decision:           Overall decision on the package: approved / conditional / rejected / abstained.
                            Used if req_decisions_json is empty — applied to all requirements.
        req_decisions_json: JSON list of decisions for individual requirements in the package.
                            If provided — overrides the overall decision for the listed requirements.
                            Format:
                            [
                              {"req_id": "FR-001", "decision": "approved"},
                              {"req_id": "FR-002", "decision": "conditional",
                               "condition_text": "Clarify the acceptance criterion",
                               "condition_deadline": "2026-04-01",
                               "condition_owner": "J. Smith"},
                              {"req_id": "FR-003", "decision": "rejected",
                               "rejection_reason": "Out of scope"}
                            ]
                            If empty ([]) — decision applies to all requirements in the package.
        rejection_reason:   Reason for rejection (required if decision=rejected
                            and req_decisions_json is empty).
        comment:            Additional comment from the stakeholder.

    Returns:
        Confirmation that the decision was recorded, conflict analysis (on rejected),
        updated requirement statuses.
    """
    logger.info(f"record_approval_decision: {package_id} / {stakeholder_name} / {project_name}")

    try:
        req_decisions = json.loads(req_decisions_json)
    except json.JSONDecodeError:
        return "❌ Error: `req_decisions_json` must be a valid JSON list."

    history = _load_approval_history(project_name)
    package = _get_package(history, package_id)
    if not package:
        return (
            f"❌ Package `{package_id}` not found for project `{project_name}`.\n"
            f"Run `prepare_approval_package` first."
        )

    if package.get("status") == "baselined":
        return f"⚠️ Package `{package_id}` has already been baselined. Changes are not possible."

    repo = _load_repo(project_name)
    req_ids = package["req_ids"]

    # If req_decisions is empty — apply the overall decision to all requirements
    if not req_decisions:
        if decision == "rejected" and not rejection_reason:
            return "❌ When decision=rejected, you must provide `rejection_reason`."
        req_decisions = []
        for rid in req_ids:
            rd = {"req_id": rid, "decision": decision}
            if decision == "rejected":
                rd["rejection_reason"] = rejection_reason
            req_decisions.append(rd)

    # Validation: are all req_id values part of the package?
    unknown_reqs = [rd["req_id"] for rd in req_decisions if rd["req_id"] not in req_ids]
    if unknown_reqs:
        return (
            f"⚠️ Requirements {unknown_reqs} are not part of package `{package_id}`.\n"
            f"The package contains: {req_ids}"
        )

    # Conditional validation
    for rd in req_decisions:
        if rd["decision"] == "conditional":
            if not rd.get("condition_text"):
                return (
                    f"❌ For a conditional approval of requirement `{rd['req_id']}` "
                    f"you must provide `condition_text` in req_decisions."
                )

    # For requirements not mentioned in req_decisions — apply the overall decision
    mentioned = {rd["req_id"] for rd in req_decisions}
    for rid in req_ids:
        if rid not in mentioned:
            rd = {"req_id": rid, "decision": decision}
            if decision == "rejected":
                rd["rejection_reason"] = rejection_reason
            req_decisions.append(rd)

    # Conflict analysis on rejected — context from 5.3 and 5.4
    conflict_analysis = []
    for rd in req_decisions:
        if rd["decision"] == "rejected":
            req_id = rd["req_id"]
            node = _find_node(repo, req_id)
            conflicts = []

            if node:
                # Check the priority from 5.3
                priority = node.get("priority", "")
                if priority == "Must":
                    conflicts.append(
                        f"🔴 Must priority (5.3) — rejecting a critically important requirement"
                    )
                elif priority in ("Should", "Could"):
                    conflicts.append(f"🟡 {priority} priority (5.3) — recommend reviewing the necessity")

                # WSJF score if present
                wsjf = node.get("wsjf_score")
                if wsjf and float(wsjf) > 2.0:
                    conflicts.append(f"🟡 WSJF score {wsjf} (5.3) — high business value")

            # Check the CR from 5.4
            cr_refs = _get_cr_context(repo, req_id)
            open_crs = [c for c in cr_refs if c["status"] in ("open", "under_change")]
            if open_crs:
                cr_list = ", ".join(f"`{c['cr_id']}` ({c['status']})" for c in open_crs)
                conflicts.append(f"🟡 Open CRs from 5.4: {cr_list} — the requirement is under change")

            if conflicts:
                conflict_analysis.append({
                    "req_id": req_id,
                    "stakeholder": stakeholder_name,
                    "raci": stakeholder_raci,
                    "conflicts": conflicts,
                })

    # Save the stakeholder's decision
    stakeholder_record = {
        "stakeholder_name": stakeholder_name,
        "raci": stakeholder_raci,
        "overall_decision": decision,
        "req_decisions": req_decisions,
        "rejection_reason": rejection_reason,
        "comment": comment,
        "recorded_date": str(date.today()),
    }

    package["stakeholder_decisions"][stakeholder_name] = stakeholder_record
    _save_approval_history(project_name, history)

    # Update requirement statuses in the 5.1 repository
    updated_statuses = {}
    for rid in req_ids:
        new_status = _compute_req_status(rid, package)
        node = _find_node(repo, rid)
        if node:
            old_status = node.get("status", "unknown")
            if old_status != new_status:
                node["status"] = new_status
                node.setdefault("history", []).append({
                    "date": str(date.today()),
                    "action": "approval_decision",
                    "from": old_status,
                    "to": new_status,
                    "stakeholder": stakeholder_name,
                    "raci": stakeholder_raci,
                })
            updated_statuses[rid] = new_status

    _save_repo(project_name, repo)

    # Build the report
    decision_icon = {
        "approved": "✅",
        "conditional": "🟡",
        "rejected": "❌",
        "abstained": "⚪",
    }.get(decision, "—")

    lines = [
        f"<!-- BABOK 5.5 — Approval Decision, Project: {project_name}, Package: {package_id}, "
        f"Stakeholder: {stakeholder_name}, Date: {date.today()} -->",
        "",
        f"## {decision_icon} Decision recorded: {stakeholder_name}",
        "",
        f"**Package:** {package_id} | **RACI:** {stakeholder_raci} | **Date:** {date.today()}",
        f"**Overall decision:** {decision}",
    ]

    if comment:
        lines += [f"**Comment:** {comment}", ""]

    # Details by requirement
    lines += ["", "### Decisions by requirement", ""]
    for rd in req_decisions:
        rid = rd["req_id"]
        dec = rd["decision"]
        dec_icon = {"approved": "✅", "conditional": "🟡", "rejected": "❌", "abstained": "⚪"}.get(dec, "—")
        node = _find_node(repo, rid)
        title = node.get("title", "—") if node else "—"

        line = f"- {dec_icon} `{rid}` {title}"
        if dec == "conditional":
            line += f"\n  → Condition: {rd.get('condition_text', '—')}"
            if rd.get("condition_deadline"):
                line += f" | Deadline: {rd['condition_deadline']}"
            if rd.get("condition_owner"):
                line += f" | Owner: {rd['condition_owner']}"
        elif dec == "rejected":
            line += f"\n  → Reason: {rd.get('rejection_reason', rejection_reason or '—')}"
        lines.append(line)

    lines.append("")

    # Conflicts
    if conflict_analysis:
        lines += ["### ⚠️ Conflicts found", ""]
        for ca in conflict_analysis:
            lines.append(f"**`{ca['req_id']}`** (rejected by {ca['stakeholder']}, role: {ca['raci']}):")
            for c in ca["conflicts"]:
                lines.append(f"  - {c}")
        lines += ["", "The BA should review the conflicts before creating a baseline.", ""]

    # RACI advice for rejected from consulted
    rejected_req_ids = [rd["req_id"] for rd in req_decisions if rd["decision"] == "rejected"]
    if rejected_req_ids and stakeholder_raci == "consulted":
        lines += [
            f"ℹ️ **{stakeholder_name}'s role is Consulted.** Rejected from C does not block the baseline.",
            "Document the disagreement as a managed risk in `check_approval_status`.",
            "",
        ]

    # Updated statuses
    lines += ["### Requirement statuses after the decision", ""]
    for rid, status in updated_statuses.items():
        status_icon = {
            STATUS_APPROVED: "✅",
            STATUS_CONDITIONAL: "🟡",
            STATUS_REJECTED: "❌",
            STATUS_PENDING: "⏳",
        }.get(status, "—")
        lines.append(f"- {status_icon} `{rid}` → `{status}`")

    lines += [
        "",
        "---",
        "",
        "## ➡️ Next step",
        "",
    ]

    has_conditional = any(rd["decision"] == "conditional" for rd in req_decisions)
    if has_conditional:
        lines += [
            "There are conditional approvals. Once the conditions are met, call `close_approval_condition`.",
            "Then check the package's readiness via `check_approval_status`.",
        ]
    else:
        lines += [
            "Record the decisions of the remaining stakeholders via `record_approval_decision`.",
            "Once all decisions are in — check readiness via `check_approval_status`.",
        ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 5.5.3 — Close a condition (Conditional)
# ---------------------------------------------------------------------------

@mcp.tool()
def close_approval_condition(
    project_name: str,
    package_id: str,
    req_id: str,
    stakeholder_name: str,
    resolution_notes: str,
) -> str:
    """
    BABOK 5.5 — Step 3 (if needed): Close a satisfied condition.

    Once a conditional-approval condition has been satisfied, updates the
    requirement's status from conditional_approved to approved.

    Args:
        project_name:      Project name.
        package_id:        Package ID.
        req_id:             ID of the requirement with an open condition.
        stakeholder_name:  Name of the stakeholder who set the condition.
        resolution_notes:  How the condition was satisfied (what specifically changed).

    Returns:
        Confirmation that the condition was closed, the requirement's updated status.
    """
    logger.info(f"close_approval_condition: {package_id} / {req_id} / {project_name}")

    history = _load_approval_history(project_name)
    package = _get_package(history, package_id)
    if not package:
        return f"❌ Package `{package_id}` not found. Run `prepare_approval_package` first."

    sh_data = package["stakeholder_decisions"].get(stakeholder_name)
    if not sh_data:
        return (
            f"❌ Stakeholder `{stakeholder_name}` not found in package `{package_id}`.\n"
            f"Available stakeholders: {list(package['stakeholder_decisions'].keys())}"
        )

    # Look for a conditional decision for req_id
    condition_found = False
    for rd in sh_data["req_decisions"]:
        if rd["req_id"] == req_id and rd["decision"] == "conditional":
            if rd.get("condition_closed"):
                return f"⚠️ The condition for `{req_id}` from `{stakeholder_name}` is already closed."
            rd["condition_closed"] = True
            rd["condition_closed_date"] = str(date.today())
            rd["resolution_notes"] = resolution_notes
            condition_found = True
            break

    if not condition_found:
        return (
            f"❌ No open condition found for requirement `{req_id}` from `{stakeholder_name}`.\n"
            f"Check the req_id and stakeholder_name."
        )

    _save_approval_history(project_name, history)

    # Recompute the requirement's status
    repo = _load_repo(project_name)
    node = _find_node(repo, req_id)
    new_status = _compute_req_status(req_id, package)
    if node:
        old_status = node.get("status", "unknown")
        node["status"] = new_status
        node.setdefault("history", []).append({
            "date": str(date.today()),
            "action": "condition_closed",
            "from": old_status,
            "to": new_status,
            "stakeholder": stakeholder_name,
            "resolution_notes": resolution_notes,
        })
    _save_repo(project_name, repo)

    status_icon = "✅" if new_status == STATUS_APPROVED else "🟡"

    return "\n".join([
        f"<!-- BABOK 5.5 — Condition Closed, Project: {project_name}, "
        f"Package: {package_id}, Requirement: {req_id}, Date: {date.today()} -->",
        "",
        f"## ✅ Condition closed: {req_id}",
        "",
        f"**Stakeholder:** {stakeholder_name}  ",
        f"**Closed on:** {date.today()}  ",
        f"**Description:** {resolution_notes}  ",
        "",
        f"**New requirement status:** {status_icon} `{new_status}`",
        "",
        "---",
        "",
        "## ➡️ Next step",
        "",
        f"Check the readiness of package `{package_id}` via `check_approval_status`.",
    ])


# ---------------------------------------------------------------------------
# 5.5.4 — Baseline readiness dashboard
# ---------------------------------------------------------------------------

@mcp.tool()
def check_approval_status(
    project_name: str,
    package_id: str,
) -> str:
    """
    BABOK 5.5 — Step 4: Dashboard of the package's readiness to create a baseline.

    Analyzes all stakeholder decisions and gives a verdict:
    ready / not ready for a baseline.

    Args:
        project_name:  Project name.
        package_id:    Package ID.

    Returns:
        The package's full status: approval statistics, blockers, open conditions,
        verdict on baseline readiness.
    """
    logger.info(f"check_approval_status: {package_id} / {project_name}")

    history = _load_approval_history(project_name)
    package = _get_package(history, package_id)
    if not package:
        return f"❌ Package `{package_id}` not found. Run `prepare_approval_package` first."

    repo = _load_repo(project_name)
    req_ids = package["req_ids"]

    gate = _baseline_gate(package)
    req_statuses = gate["statuses"]
    counts = gate["counts"]
    total = gate["total"]
    approved_pct = gate["approved_pct"]

    # Blockers: rejected by accountable/responsible (enriched with the title for display)
    blockers = []
    for b in gate["ar_rejections"]:
        node = _find_node(repo, b["req_id"])
        blockers.append({**b, "title": node.get("title", "—") if node else "—"})

    open_conditions = gate["open_conditions"]
    overdue_conditions = gate["overdue_conditions"]

    # Stakeholders without a decision (if the package was sent but there's no response)
    # We don't store an "expected list" — we show those who did respond
    responding_stakeholders = list(package["stakeholder_decisions"].keys())

    # Verdict — from the shared gate, so the dashboard and create_requirements_baseline
    # can never disagree about readiness.
    can_baseline = gate["can_baseline"]
    verdict_reasons = []

    if blockers:
        verdict_reasons.append(f"🔴 {len(blockers)} rejection(s) from Accountable/Responsible stakeholders")

    if overdue_conditions:
        verdict_reasons.append(f"🔴 {len(overdue_conditions)} overdue condition(s)")

    if open_conditions and not overdue_conditions:
        # Not blocking, but flag it
        verdict_reasons.append(f"🟡 {len(open_conditions)} open condition(s) (not overdue)")

    if counts[STATUS_PENDING] > 0:
        verdict_reasons.append(f"🔴 {counts[STATUS_PENDING]} requirement(s) still in pending_approval status")

    if gate["low_approval"]:
        verdict_reasons.append(f"🔴 Only {approved_pct}% of requirements approved (minimum 70%)")

    # Consulted-rejected (does not block, but we flag it)
    consulted_rejected = []
    for sh_name, sh_data in package["stakeholder_decisions"].items():
        if sh_data["raci"] == "consulted":
            for rd in sh_data["req_decisions"]:
                if rd["decision"] == "rejected":
                    consulted_rejected.append({
                        "req_id": rd["req_id"],
                        "stakeholder": sh_name,
                        "reason": rd.get("rejection_reason", "—"),
                    })

    # Build the report
    verdict_icon = "✅" if can_baseline else ("🟡" if not blockers and not counts[STATUS_PENDING] else "🔴")

    lines = [
        f"<!-- BABOK 5.5 — Approval Status, Project: {project_name}, Package: {package_id}, Date: {date.today()} -->",
        "",
        f"## 📊 Package status: {package_id} — {package.get('package_title', '—')}",
        "",
        f"**Project:** {project_name} | **Date:** {date.today()}",
        f"**Methodology:** {package.get('approach', '—')}",
        f"**Stakeholders who responded:** {', '.join(responding_stakeholders) if responding_stakeholders else '(no responses)'}",
        "",
        "### Approval statistics",
        "",
        f"| Status | Count | % |",
        f"|--------|-------|---|",
        f"| ✅ Approved | {counts[STATUS_APPROVED]} | {approved_pct}% |",
        f"| 🟡 Conditional (open conditions) | {counts[STATUS_CONDITIONAL]} | {round(counts[STATUS_CONDITIONAL]/total*100) if total else 0}% |",
        f"| ❌ Rejected | {counts[STATUS_REJECTED]} | {round(counts[STATUS_REJECTED]/total*100) if total else 0}% |",
        f"| ⏳ Pending | {counts[STATUS_PENDING]} | {round(counts[STATUS_PENDING]/total*100) if total else 0}% |",
        f"| **Total** | **{total}** | **100%** |",
        "",
    ]

    if blockers:
        lines += ["### 🔴 Blockers (Rejected from Accountable/Responsible)", ""]
        for b in blockers:
            lines.append(f"- `{b['req_id']}` {b['title']} — rejected by `{b['stakeholder']}` ({b['raci']}): {b['reason']}")
        lines.append("")

    if open_conditions:
        lines += ["### 🟡 Open conditions (Conditional)", ""]
        for c in open_conditions:
            overdue_flag = " ⚠️ OVERDUE" if c.get("overdue") else ""
            deadline_str = f" | Deadline: {c['condition_deadline']}{overdue_flag}" if c['condition_deadline'] else ""
            lines.append(
                f"- `{c['req_id']}` — {c['condition_text']}"
                f"{deadline_str} | Owner: {c['condition_owner']}"
            )
        lines.append("")

    if consulted_rejected:
        lines += ["### ℹ️ Rejections from Consulted (do not block the baseline)", ""]
        for cr in consulted_rejected:
            lines.append(f"- `{cr['req_id']}` — rejected by `{cr['stakeholder']}` (consulted): {cr['reason']}")
        lines += ["", "Recommend documenting this as a managed risk.", ""]

    # Verdict
    lines += [
        "---",
        "",
        f"## {verdict_icon} Verdict: {'Ready for baseline' if can_baseline else 'Not ready for baseline'}",
        "",
    ]

    if verdict_reasons:
        for reason in verdict_reasons:
            lines.append(f"- {reason}")
        lines.append("")

    if can_baseline:
        lines += [
            "All mandatory conditions are satisfied. You can create the Requirements Baseline.",
            "",
            "➡️ Call `create_requirements_baseline`:",
            f"  - `project_name`: \"{project_name}\"",
            f"  - `package_id`: \"{package_id}\"",
            f"  - `baseline_version`: \"v1.0\" (or sprint-N for agile)",
            f"  - `decided_by`: the authorized stakeholder",
        ]
    else:
        lines += ["Resolve the blockers before creating the baseline."]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 5.5.5 — Create the Requirements Baseline
# ---------------------------------------------------------------------------

@mcp.tool()
def create_requirements_baseline(
    project_name: str,
    package_id: str,
    baseline_version: str,
    decided_by: str,
    force: bool = False,
) -> str:
    """
    BABOK 5.5 — Step 5: Create the official Requirements Baseline.

    Records a snapshot of the package in {project}_approval_history.json.
    Updates requirement statuses in the 5.1 repository to 'approved'.
    Generates an Approval Record (Markdown) via save_artifact.

    Args:
        project_name:      Project name.
        package_id:        Package ID (must have gone through check_approval_status).
        baseline_version:  Baseline version: v1.0, v1.1, sprint-5, etc.
        decided_by:        Who is confirming the baseline creation (sponsor / PO).
        force:             True — create the baseline even if there are warnings
                           (open conditions, consulted-rejected).
                           False (default) — block if blockers exist.

    Returns:
        The Approval Record (Markdown), saved via save_artifact.
        Updated approved statuses in the 5.1 repository.
    """
    logger.info(f"create_requirements_baseline: {package_id} / {baseline_version} / {project_name}")

    history = _load_approval_history(project_name)
    package = _get_package(history, package_id)
    if not package:
        return f"❌ Package `{package_id}` not found. Run `prepare_approval_package` first."

    if package.get("status") == "baselined":
        return (
            f"⚠️ Package `{package_id}` already has baseline `{package.get('baseline_version')}`.\n"
            f"For a new baseline, create a new package with a different package_id."
        )

    repo = _load_repo(project_name)
    req_ids = package["req_ids"]

    # Readiness gate — the SAME predicate check_approval_status renders, so the
    # dashboard's "Ready / Not ready" verdict is the real contract. force=True is
    # the deliberate override.
    gate = _baseline_gate(package)
    statuses = gate["statuses"]
    pending_reqs = gate["pending_reqs"]
    approved_pct = gate["approved_pct"]

    if not gate["can_baseline"] and not force:
        lines = ["❌ Baseline blocked:", ""]
        if gate["ar_rejections"]:
            lines.append("**Rejections from Accountable/Responsible:**")
            for b in gate["ar_rejections"]:
                lines.append(f"  - `{b['req_id']}` rejected by {b['stakeholder']} ({b['raci']})")
        if pending_reqs:
            lines.append(f"**Requirements in pending_approval status:** {pending_reqs}")
        if gate["overdue_conditions"]:
            overdue = ", ".join(f"`{c['req_id']}` ({c['stakeholder']})"
                                for c in gate["overdue_conditions"])
            lines.append(f"**Overdue conditions:** {overdue}")
        if gate["low_approval"]:
            lines.append(f"**Only {approved_pct}% of requirements approved** "
                         f"(minimum {MIN_APPROVED_PCT}%).")
        lines += [
            "",
            "Resolve the issues above, or use `force=true` to force the baseline creation.",
        ]
        return "\n".join(lines)

    # Check for open conditional items (warnings, do not block when force is used)
    open_conditions = []
    for sh_name, sh_data in package["stakeholder_decisions"].items():
        for rd in sh_data["req_decisions"]:
            if rd["decision"] == "conditional" and not rd.get("condition_closed"):
                open_conditions.append({
                    "req_id": rd["req_id"],
                    "stakeholder": sh_name,
                    "condition_text": rd.get("condition_text", "—"),
                    "condition_deadline": rd.get("condition_deadline", ""),
                })

    # Update approved requirement statuses in the 5.1 repository
    approved_reqs = []
    for rid in req_ids:
        status = _compute_req_status(rid, package)
        node = _find_node(repo, rid)
        if node:
            if status == STATUS_APPROVED:
                node["status"] = STATUS_APPROVED
                approved_reqs.append(rid)
                node.setdefault("history", []).append({
                    "date": str(date.today()),
                    "action": "baselined",
                    "baseline_version": baseline_version,
                    "decided_by": decided_by,
                })
            elif status == STATUS_CONDITIONAL and force:
                node["status"] = STATUS_CONDITIONAL
                node.setdefault("history", []).append({
                    "date": str(date.today()),
                    "action": "baselined_with_open_condition",
                    "baseline_version": baseline_version,
                    "decided_by": decided_by,
                })

    _save_repo(project_name, repo)

    # Baseline snapshot in approval_history
    baseline_snapshot = {
        "baseline_version": baseline_version,
        "package_id": package_id,
        "package_title": package.get("package_title", "—"),
        "approach": package.get("approach", "—"),
        "created_date": str(date.today()),
        "decided_by": decided_by,
        "approved_req_ids": approved_reqs,
        "open_conditions": open_conditions,
        "force_created": force and bool(gate["ar_rejections"] or open_conditions),
        "stakeholder_summary": {
            sh_name: {
                "raci": sh_data["raci"],
                "overall_decision": sh_data["overall_decision"],
                "recorded_date": sh_data.get("recorded_date", "—"),
            }
            for sh_name, sh_data in package["stakeholder_decisions"].items()
        },
    }

    history["baselines"].append(baseline_snapshot)
    package["status"] = "baselined"
    package["baseline_version"] = baseline_version
    _save_approval_history(project_name, history)

    # Generate the Approval Record
    approach_label = "Predictive / Waterfall" if package.get("approach") == "predictive" else "Agile"
    force_warning = "\n\n> ⚠️ The baseline was created forcibly (force=true). Open conditions remain." if force and open_conditions else ""

    record_lines = [
        f"<!-- BABOK 5.5 — Approval Record, Project: {project_name}, "
        f"Baseline: {baseline_version}, Date: {date.today()} -->",
        "",
        f"# Requirements Baseline: {baseline_version}",
        f"**Project:** {project_name}  ",
        f"**Package:** {package_id} — {package.get('package_title', '—')}  ",
        f"**Methodology:** {approach_label}  ",
        f"**Created on:** {date.today()}  ",
        f"**Confirmed by:** {decided_by}  ",
        f"**Requirements in the baseline:** {len(approved_reqs)}  ",
        force_warning,
        "",
        "---",
        "",
        "## Approved requirements",
        "",
    ]

    for rid in approved_reqs:
        node = _find_node(repo, rid)
        title = node.get("title", "—") if node else "—"
        version = node.get("version", "—") if node else "—"
        priority = node.get("priority", "—") if node else "—"
        record_lines.append(f"- ✅ `{rid}` {title} (v{version}, priority: {priority})")

    record_lines += ["", "---", "", "## Stakeholder decisions", ""]
    for sh_name, sh_summary in baseline_snapshot["stakeholder_summary"].items():
        icon = {"approved": "✅", "conditional": "🟡", "rejected": "❌", "abstained": "⚪"}.get(
            sh_summary["overall_decision"], "—"
        )
        record_lines.append(
            f"- {icon} **{sh_name}** ({sh_summary['raci']}) — "
            f"{sh_summary['overall_decision']} ({sh_summary['recorded_date']})"
        )

    if open_conditions:
        record_lines += ["", "---", "", "## 🟡 Open conditions (risk)", ""]
        for oc in open_conditions:
            record_lines.append(
                f"- `{oc['req_id']}` — {oc['condition_text']}"
                + (f" | Deadline: {oc['condition_deadline']}" if oc['condition_deadline'] else "")
            )
        record_lines += [
            "",
            "> Conditions must be closed via `close_approval_condition` "
            "and recorded in the next baseline.",
        ]

    record_lines += [
        "",
        "---",
        "",
        "## Next steps",
        "",
        f"1. Hand off the Approval Record to stakeholders via `prepare_communication_package` (4.4)",
        f"2. Hand off the list of approved requirements to development (Chapter 6)",
        f"3. Any changes to approved requirements — only via `open_cr` (5.4)",
        "",
        "---",
        "",
        "*Generated by: AInalyst BABOK 5.5*",
    ]

    artifact_content = "\n".join(record_lines)
    save_path = save_artifact(artifact_content, prefix=f"5_5_approval_record_{baseline_version}", project_id=project_name)

    # Final output
    output_lines = [
        f"## ✅ Requirements Baseline created: {baseline_version}",
        "",
        f"**Project:** {project_name} | **Package:** {package_id}  ",
        f"**Confirmed by:** {decided_by} | **Date:** {date.today()}  ",
        f"**Requirements approved:** {len(approved_reqs)} of {len(req_ids)}",
        "",
    ]

    if open_conditions and force:
        output_lines += [
            f"⚠️ The baseline was created with {len(open_conditions)} open condition(s).",
            "They need to be closed via `close_approval_condition`.",
            "",
        ]

    output_lines += [
        "### Next steps",
        "",
        "1. Hand off the Approval Record to stakeholders via `prepare_communication_package` (4.4)",
        "2. Hand off the list of approved requirements to development (Chapter 6)",
        "3. Any changes to approved requirements — only via `open_cr` (5.4)",
        "",
        save_path,
    ]

    return "\n".join(output_lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
