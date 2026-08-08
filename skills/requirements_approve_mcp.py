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
  In:  5.1 repository (graph+statuses), 5.3 priorities, 5.4 CR Records, 4.2 stakeholders,
       7.2 verification evidence (req_verified in the repository history — reported, not gated),
       3.1 BA plan (the approval ceremony, when `approach` is left empty — read through
       the shared helpers in skills/common.py, no chapter imports another)
  Out: Approval Record → 4.4 (communication), Chapter 6 (development)
       approved statuses in the 5.1 repository

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date, datetime
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import (
    save_artifact, logger, DATA_DIR, data_path, normalize_project_id,
    has_passed_verification, was_verification_forced, compute_approval_outcome,
    APPROVAL_HISTORY_FILENAME,
    read_json_artifact, guard_artifact_errors, parse_json_dict_list,
    MUST_PRIORITIES,
    find_spec_file, spec_section_body,
    load_ba_plan, planned_timing_form, approach_to_timing_form,
    planned_approval_timing, planned_approval_process, planned_decision_makers,
    is_planned_decision_maker, reg_norm,
    planned_party_status, party_aliases, PARTY_UNPLANNED, PARTY_UNBRIDGEABLE,
    parse_platform_date, deciding_package, superseding_packages, list_with_cap,
    load_approval_history, approval_outcome,
)

mcp = FastMCP("BABOK_Requirements_Approve")

REPO_FILENAME = "traceability_repo.json"
# APPROVAL_HISTORY_FILENAME is imported from common: 5.1, 5.2 and 7.2 now read this
# file too, and the name has to be agreed in one place. A consumer guessing a
# producer's filename is the single most repeated defect in this codebase.

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
        # Raises CorruptArtifactError, converted to a ❌ line by guard_artifact_errors
        # at the tool boundary. A bare json.load here made a damaged file a protocol
        # error in every downstream tool.
        return read_json_artifact(path, "5.1 traceability repository")
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
        # Raises CorruptArtifactError, converted to a ❌ line by guard_artifact_errors
        # at the tool boundary. A bare json.load here made a damaged file a protocol
        # error in every downstream tool.
        return read_json_artifact(path, "5.5 approval history")
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


def _decisions_this_round_overrides(project_name: str, package_id: str,
                                    req_ids: list) -> list:
    """Rejections and conditions recorded in EARLIER rounds for these requirements.

    Packages are rounds: where a requirement appears in several, the latest governs
    (common.approval_outcome). So a rejection from an earlier round is genuinely
    overridden here — and that is exactly the fact a reader of this record needs, since
    it means someone with decision authority said no and this document goes past them.
    """
    history = load_approval_history(project_name)
    if history is None:
        return []
    wanted = set(req_ids)
    out = []
    for other_id, other in history["packages"].items():
        if other_id == package_id or not isinstance(other, dict):
            continue
        shared = wanted & set(other.get("req_ids") or [])
        if not shared:
            continue
        for req_id in sorted(shared):
            # Only where THIS package is the one that decides now.
            decider_id, _ = deciding_package(project_name, req_id)
            if decider_id != package_id:
                continue
            for sh_name, sh_data in (other.get("stakeholder_decisions") or {}).items():
                for rd in sh_data.get("req_decisions", []):
                    if rd.get("req_id") != req_id:
                        continue
                    if rd.get("decision") not in ("rejected", "conditional"):
                        continue
                    out.append({
                        "req_id": req_id,
                        "package_id": other_id,
                        "stakeholder": sh_name,
                        "raci": sh_data.get("raci", "—"),
                        "decision": rd["decision"],
                        "reason": rd.get("rejection_reason") or rd.get("condition_text") or "",
                    })
    return out


def _compute_req_status(req_id: str, package: dict) -> str:
    """Computes the final status of a requirement based on all stakeholder decisions.

    The rule itself lives in `common.compute_approval_outcome`, because 5.1, 5.2 and
    7.2 need the same verdict from the durable record and cannot import this module
    (5.5 loads in the `lifecycle` phase, 7.2 in `design` — the phases never overlap).
    Keeping a second copy here is precisely how this module's dashboard verdict and
    baseline gate drifted apart once already.
    """
    return compute_approval_outcome(package, req_id)


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
                    # Both formats the platform writes; an unreadable one is UNKNOWN
                    # and must say so. `date.fromisoformat` inside `except: pass` meant
                    # a deadline written the chapter-4 way (`01.04.2025`, sixteen
                    # months past) printed with no marker while the verdict stated
                    # "not overdue" — and `overdue_conditions`, one of the four
                    # baseline gates, could never fire on such data.
                    parsed = parse_platform_date(rd["condition_deadline"])
                    if parsed is None:
                        entry["deadline_unreadable"] = True
                    elif parsed < today:
                        entry["overdue"] = True
                        overdue_conditions.append(entry)

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
        # An A/R rejection is the ONE gate `force` must not lift: it is a named person
        # with decision authority saying no, whereas the other three are process state
        # (a missed date, an unanswered request, a percentage). A single boolean flag
        # let an analyst forcing past a lapsed deadline also baseline over a live
        # objection without ever being told. Overriding a person is a different
        # decision from overriding a schedule, so it needs a different act.
        "hard_block": bool(ar_rejections),
        # What `force` WOULD lift here — named, so the Approval Record can list them
        # instead of recording an undifferentiated "forced".
        "forceable": [
            name for name, present in (
                ("pending approvals", bool(pending_reqs)),
                ("overdue conditions", bool(overdue_conditions)),
                (f"approval below {MIN_APPROVED_PCT}%", low_approval),
            ) if present
        ],
    }


def _verification_state(repo: dict, package: dict) -> dict:
    """Which requirements in the package passed 7.2 — live history ∪ stored snapshot.

    5.5 does not gate on this (see `_baseline_gate`, deliberately unchanged): the BA
    cannot fix it from here, because 7.2 lives in the `design` phase while 5.5 lives
    in `lifecycle`. Instead the fact is reported, and lands in the Approval Record.

    The snapshot is taken by `prepare_approval_package` before it overwrites `status`
    with pending_approval. Live history wins where present — the BA may have gone to
    7.2 after the package was prepared — so the snapshot only ever adds evidence.

    `known` is False only for packages created before this check existed; their
    verification state is genuinely unknowable, which is not the same as unverified.
    """
    snapshot = package.get("verification_snapshot")

    verified, unverified, unknown, forced = [], [], [], []
    for req_id in package.get("req_ids", []):
        live = has_passed_verification(repo, req_id)
        if live:
            verified.append(req_id)
            if was_verification_forced(repo, req_id):
                forced.append(req_id)
        elif snapshot is not None and req_id in snapshot:
            (verified if snapshot[req_id] else unverified).append(req_id)
        else:
            # No snapshot entry AND the durable history is silent — genuinely
            # unknowable. Judged PER REQUIREMENT, not per package: collapsing the
            # whole package on `snapshot is None` threw away live history that was
            # sitting right there, and produced a record that said verification
            # could not be determined and then named a specific override.
            unknown.append(req_id)

    return {
        # Kept for callers that only ask "is anything unknown here"; the per-id lists
        # above are the authority.
        "known": not unknown,
        "verified": verified,
        "unverified": unverified,
        "unknown": unknown,
        "forced": forced,
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

# The methodology is a 3.1 decision; before B3-1 the BA restated it here by hand and
# nothing compared the two. Resolution order: explicit -> the planned timing form ->
# the approach label. Plain "Hybrid" resolves to NEITHER of 5.5's two values, which is
# exactly why element .4 (phases vs iterations) is the authoritative source rather
# than the approach label.
_FORM_TO_APPROACH = {"phases": "predictive", "iterations": "agile"}

# `approach` selects the approval CEREMONY here — the four-option decision menu with a
# response deadline, or "For Sprint Planning, the Product Owner approves the backlog".
# The timing form answers a different question (cadence), and for these labels the two
# answers genuinely differ: BOTH are produced only by REGULATORY_OVERRIDE, i.e. only
# when regulatory_need=True, and their whole point is formal sign-off for audit.
# Resolving them through the cadence handed exactly the regulated projects the informal
# package, so the label pins the ceremony and outranks the form. Fixing one of the two
# and leaving the other is the same defect: the second is reachable through the very
# advice the docs give ("declare a timing form in 3.1b").
_CEREMONY_BY_APPROACH = {
    "Hybrid (Agile + compliance gates)": "predictive",
    "Hybrid (with strengthened governance)": "predictive",
}


def _plan_approach_label(plan) -> str:
    """`ba_approach.recommended_approach` from a plan of any shape, or ""."""
    if not isinstance(plan, dict):
        return ""
    section = plan.get("ba_approach")
    if not isinstance(section, dict):
        return ""
    raw = section.get("recommended_approach")
    return raw if isinstance(raw, str) else ""


def _resolve_approach(project_name: str, approach: str) -> tuple:
    """Returns (value, source_label, error). Only "" triggers resolution.

    A non-empty value passes through unvalidated: it is the BA's explicit statement,
    pydantic already checks it against the Literal in production, and rejecting it
    here would change behaviour well beyond this feature.
    """
    if approach:
        return approach, "stated in this call", ""
    plan, note = load_ba_plan(project_name)
    label = _plan_approach_label(plan)
    ceremony = _CEREMONY_BY_APPROACH.get(label.strip())
    if ceremony:
        return (ceremony,
                f"from the 3.1 BA plan — approach: {label} (formal sign-off)", "")
    form = planned_timing_form(plan)
    if form:
        return (_FORM_TO_APPROACH[form],
                f"from the 3.1 BA plan — timing form: {form}", "")
    derived = approach_to_timing_form(label)
    if derived:
        return (_FORM_TO_APPROACH[derived],
                f"from the 3.1 BA plan — approach: {label}", "")
    reason = (f"the 3.1 approach `{label}` sits between predictive and adaptive"
              if label else "the 3.1 BA plan does not state it")
    error = (
        f"❌ The methodology for this package could not be determined — {reason}.\n"
        + (f"  {note}\n" if note else "")
        + f"  Two ways to fix it:\n"
        f"    • pass `approach=\"predictive\"` or `approach=\"agile\"` here, or\n"
        f"    • record it once in 3.1 with `plan_ba_activities("
        f"timing_form=\"phases\"|\"iterations\")` — every package then takes it from "
        f"the plan.\n"
        f"  It is not guessed: this value is printed on the package that goes out "
        f"for signature."
    )
    return "", "", error


def _governance_block(project_name: str) -> tuple:
    """(markdown lines for the authority block, the deadline sentence or "").

    BABOK 3.3 .4 — "the timing for the approvals" and who approves. Everything here
    is NEW information: the package named no approver and stated no deadline, it only
    pointed at a plan nothing read ("Response deadline: per the project's governance
    plan."), printed inside a document that goes out for signature.

    So a project without a governance plan gets a tool that says LESS than before —
    never a dash, and never a refusal. That is the opposite of `_resolve_approach`
    above, and deliberately so: `approach` was ALREADY a required input, so refusing
    took nothing away, whereas refusing here would break every existing project.
    """
    plan, note = load_ba_plan(project_name)
    days, timing_note, _timing_source = planned_approval_timing(plan)
    process, process_source = planned_approval_process(plan)
    approvers = planned_decision_makers(plan)

    parts = []
    if days:
        parts.append(f"within {days} business days of receiving this package")
    if timing_note:
        parts.append(timing_note)
    deadline = (f"Response deadline: {'; '.join(parts)} "
                f"(per the 3.3 governance plan)." if parts else "")

    lines = []
    # The template's approval sentence NAMES ROLES ("Requires sign-off from Sponsor +
    # Product Owner"). Printed under a `**Approvers:**` line holding the BA's own list,
    # it made this package — a signature request — state two different sets of
    # approvers two lines apart, and a recipient could not tell which one binds them.
    # It was harmless while it only sat in the 3.3 table with nothing beside it.
    # So the generated wording is dropped once the BA has named the approvers: the
    # authoritative answer to "who signs" is their list, not a criticality default.
    show_process = bool(process) and (process_source == "declared in 3.3"
                                      or not approvers)
    if approvers or show_process:
        lines = ["---", "", "## Approval authority (3.3)", ""]
        if approvers:
            lines.append(f"**Approvers:** {', '.join(approvers)}  ")
        if show_process:
            lines.append(f"**Process:** {process} *({process_source})*  ")
        lines.append("")
    if note:
        lines = ["", note, ""] + lines
    return lines, deadline


@mcp.tool()
@guard_artifact_errors
def prepare_approval_package(
    project_name: str,
    package_id: str,
    package_title: str,
    req_ids_json: str,
    approach: Literal["predictive", "agile", ""] = "",
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
                        Leave empty to take it from the 3.1 BA plan — the planned
                        timing form, or failing that the recommended approach.
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

    # Shape, not just syntax: a scalar/object where a list of ids is expected must
    # return a readable "❌", not a TypeError escaping the tool.
    from skills.common import parse_json_str_list
    req_ids, shape_error = parse_json_str_list(req_ids_json, "req_ids_json")
    if shape_error:
        return shape_error

    if not req_ids:
        return "❌ Error: the requirement list cannot be empty."

    approach, approach_source, approach_error = _resolve_approach(
        project_name, approach)
    if approach_error:
        return approach_error

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
            # 5.4 CR statuses are open/approved/approved_modified/deferred/rejected;
            # "under_change" belongs to the REQUIREMENT status vocabulary and was a
            # dead branch here (one literal, two vocabularies).
            open_crs = [c for c in cr_refs if c["status"] == "open"]
            if open_crs:
                cr_warnings.append((rid, open_crs))
        # The graph node carries only metadata — 7.1 writes the statement and the
        # acceptance criteria into the spec .md, never onto the node. Reading the
        # node fields alone produced a signing package of bare titles: the
        # stakeholder was asked to approve requirements they could not read.
        # Fall back to the spec file the way 7.2's quality checks already do.
        description = node.get("description", "")
        acceptance = node.get("acceptance_criteria", "")
        if not (description and acceptance):
            spec_path = find_spec_file({**node, "id": rid}, project_name)
            if spec_path:
                try:
                    with open(spec_path, "r", encoding="utf-8") as f:
                        spec_text = f.read()
                except OSError:
                    spec_text = ""
                if spec_text:
                    if not description:
                        for header in ("Statement", "Story", "Main scenario"):
                            body = spec_section_body(spec_text, header)
                            # drop the italic hint line the 7.1 template prepends
                            body = "\n".join(
                                l for l in body.split("\n")
                                if not l.strip().startswith(">")).strip()
                            if body:
                                description = body
                                break
                    if not acceptance:
                        acceptance = spec_section_body(spec_text, "Acceptance Criteria")
        req_details.append({
            "id": rid,
            "title": node.get("title", "—"),
            "type": node.get("type", "functional"),
            "description": description,
            "status": node.get("status", "unknown"),
            "priority": node.get("priority", "—"),
            "version": node.get("version", "1.0"),
            "owner": node.get("owner", "—"),
            "acceptance_criteria": acceptance,
            "cr_refs": cr_refs,
        })

    # Create the package entry in approval_history
    package_record = {
        "package_id": package_id,
        "package_title": package_title,
        "approach": approach,
        # Where the methodology came from, carried on the record: the Approval Record
        # prints it back for the auditor, and re-deriving it later would give a
        # different answer once the plan changes — or none once it is gone.
        "approach_source": approach_source,
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

    # Snapshot 7.2 verification BEFORE the status is overwritten below. This is the
    # last moment it can be read for a legacy repository, where the only evidence is
    # the `verified` status itself — pending_approval erases it.
    verification_snapshot = {rid: has_passed_verification(repo, rid) for rid in req_ids}
    package_record["verification_snapshot"] = verification_snapshot
    _save_approval_history(project_name, history)

    # Update requirement statuses to pending_approval in the 5.1 repository
    for rid in req_ids:
        node = _find_node(repo, rid)
        if node:
            node["status"] = STATUS_PENDING
    _save_repo(project_name, repo)

    unverified_ids = [rid for rid, ok in verification_snapshot.items() if not ok]

    # Build the Approval Package
    approach_label = "Predictive / Waterfall" if approach == "predictive" else "Agile"
    sprint_label = f" | Sprint: {sprint_number}" if sprint_number else ""

    lines = [
        f"<!-- BABOK 5.5 — Approval Package, Project: {project_name}, Package: {package_id}, Date: {date.today()} -->",
        "",
        f"# Approval Package: {package_title}",
        f"**Project:** {project_name}  ",
        f"**Package:** {package_id}  ",
        f"**Methodology:** {approach_label}{sprint_label} ({approach_source})  ",
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

    gov_lines, gov_deadline = _governance_block(project_name)

    # Instructions for stakeholders
    if approach == "predictive":
        # A regulated hybrid signs off formally AND runs in sprints, so the header
        # would otherwise read "Predictive / Waterfall | Sprint: 5" above an
        # instruction block that never mentions the sprint.
        cadence_note = (
            f"\n\nThe work runs in sprints (Sprint {sprint_number}); the sign-off "
            f"itself is formal because of the project's compliance gates."
            if sprint_number else "")
        instruction = (
            "Please review the requirements and provide a decision for each:\n"
            "- **Approved** — agreed without reservations\n"
            "- **Conditional** — agreed subject to a condition (state the condition)\n"
            "- **Rejected** — not agreed (state the reason)\n"
            "- **Abstained** — abstaining"
            # Was: "Response deadline: per the project's governance plan." — a pointer
            # at a plan nothing read, printed on a document that goes out for
            # signature. It now states the deadline, or says nothing at all.
            + (f"\n\n{gov_deadline}" if gov_deadline else "")
            + cadence_note
        )
    else:
        sprint_ref = f" sprint {sprint_number}" if sprint_number else ""
        instruction = (
            f"For Sprint Planning{sprint_ref}. The Product Owner reviews and approves the backlog.\n"
            "Requirements accepted into the sprint will get status Approved and join the Sprint Baseline."
            # The SLA answers "the timing for the approvals" (BABOK 3.3 .4) whatever
            # the ceremony: a sprint package has a response window too. A project that
            # planned no SLA sees this branch exactly as it was.
            + (f"\n\n{gov_deadline}" if gov_deadline else "")
        )

    if unverified_ids:
        ids_str = ", ".join(f"`{rid}`" for rid in unverified_ids)
        lines += [
            "---",
            "",
            "## ⚠️ Not verified via 7.2",
            "",
            f"These requirements have not passed verification (7.2): {ids_str}",
            "",
            "This does not block approval — the decision stays with the BA — but it will be "
            "recorded in the Approval Record when the baseline is created.",
            "",
            "To verify them first (7.2 tools live in another phase):",
            "",
            "1. `python phase.py design`, then `/restart`",
            "2. `check_req_quality` → fix what it finds → `mark_req_verified`",
            "3. `python phase.py lifecycle`, then `/restart`, and continue here",
            "",
        ]

    lines += gov_lines
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
@guard_artifact_errors
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
                            IMPORTANT: a PARTIAL list works the same way. `decision` is
                            the stakeholder's blanket position and the list refines it,
                            so any requirement you do not mention still receives
                            `decision`. Listing only FR-001 as approved does NOT leave
                            the rest pending — they are recorded as approved by this
                            stakeholder too. To leave a requirement undecided, keep it
                            out of the package.
        rejection_reason:   Reason for rejection (required if decision=rejected
                            and req_decisions_json is empty).
        comment:            Additional comment from the stakeholder.

    Returns:
        Confirmation that the decision was recorded, conflict analysis (on rejected),
        updated requirement statuses.
    """
    logger.info(f"record_approval_decision: {package_id} / {stakeholder_name} / {project_name}")

    # `rd["req_id"]` is indexed a few lines down, so a list of bare ids raised
    # `TypeError: string indices must be integers` out of the tool. This one records
    # an official approval decision — failing it with a stack trace leaves the analyst
    # unsure whether the decision was stored.
    req_decisions, shape_error = parse_json_dict_list(
        req_decisions_json, "req_decisions_json",
        example='[{"req_id": "FR-001", "decision": "approved"}]')
    if shape_error:
        return shape_error

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
                # Both scales: 5.3 writes MoSCoW, 7.1 writes High/Medium/Low. Testing
                # for `Must` alone meant this warning never fired on a project that
                # specified requirements and never ran a prioritisation session.
                if priority in MUST_PRIORITIES:
                    conflicts.append(
                        f"🔴 {priority} priority — rejecting a critically important requirement"
                    )
                elif priority in ("Should", "Could", "Medium"):
                    conflicts.append(f"🟡 {priority} priority — recommend reviewing the necessity")

                # WSJF score if present
                wsjf = node.get("wsjf_score")
                if wsjf and float(wsjf) > 2.0:
                    conflicts.append(f"🟡 WSJF score {wsjf} (5.3) — high business value")

            # Check the CR from 5.4
            cr_refs = _get_cr_context(repo, req_id)
            # 5.4 CR statuses are open/approved/approved_modified/deferred/rejected;
            # "under_change" belongs to the REQUIREMENT status vocabulary and was a
            # dead branch here (one literal, two vocabularies).
            open_crs = [c for c in cr_refs if c["status"] == "open"]
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

    # BABOK 3.3 .1 — cross-check against the planned decision authority.
    #
    # It fires ONLY for accountable/responsible. A `consulted` stakeholder is a
    # reviewer, and BABOK 3.3 .1 lists reviewer and SME as roles distinct from
    # approver, so their absence from the plan's list is correct, not a finding.
    #
    # That makes the explicit `stakeholder_raci` the GUARD for this check rather than
    # its input — which is how this seam avoids the conflict that got B3-2 declined
    # once already. This value decides whether a rejection HARD BLOCKS the baseline
    # (`force` does not lift it), so deriving it from a plan would silently change
    # what blocks. It is read here and never written.
    if stakeholder_raci in ("accountable", "responsible"):
        plan, plan_note = load_ba_plan(project_name)
        planned = planned_decision_makers(plan)
        # Registry-bridged: 3.3 plans roles and this parameter is a person's name, so
        # the unbridged comparison reported the actual Product Owner as an authority
        # exception. PARTY_UNBRIDGEABLE stays silent — see `planned_party_status`.
        if planned_party_status(project_name, planned,
                                stakeholder_name) == PARTY_UNPLANNED:
            lines += [
                "",
                f"⚠️ `{stakeholder_name}` is recorded as **{stakeholder_raci}** but is "
                f"not among the planned decision makers (3.3): {', '.join(planned)}.",
                "The decision stands exactly as recorded — either update 3.3 with "
                "`plan_ba_governance`, or confirm this person holds the authority.",
            ]
        if plan_note:
            lines += ["", plan_note]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 5.5.3 — Close a condition (Conditional)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
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
@guard_artifact_errors
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

    # 7.2 verification — reported, never gated. See `_verification_state`.
    vstate = _verification_state(repo, package)

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

    unreadable_deadlines = [c for c in open_conditions if c.get("deadline_unreadable")]
    if unreadable_deadlines:
        # "Not overdue" is a claim, and it cannot be made about a deadline nobody could
        # read. Say what is actually known.
        verdict_reasons.append(
            f"🟡 {len(unreadable_deadlines)} condition(s) whose deadline could not be "
            f"read — whether they are overdue is UNKNOWN")

    if open_conditions and not overdue_conditions and not unreadable_deadlines:
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

    if vstate["verified"] or vstate["unverified"]:
        v_count = len(vstate["verified"])
        v_icon = "✅" if v_count == total else "🟡"
        lines += [f"{v_icon} **Verified (7.2): {v_count} of {total}**", ""]
        if vstate["unverified"]:
            ids_str = ", ".join(f"`{rid}`" for rid in vstate["unverified"])
            lines += [
                f"Not verified: {ids_str} — approval is not blocked, but the fact "
                f"is recorded in the Approval Record.",
                "",
            ]
        if vstate["unknown"]:
            unknown_str = ", ".join(f"`{rid}`" for rid in vstate["unknown"])
            lines += [
                f"Verification unknown: {unknown_str} — no record either way "
                f"(the package predates the check).",
                "",
            ]
        if vstate["forced"]:
            forced_str = ", ".join(f"`{rid}`" for rid in vstate["forced"])
            lines += [f"Verified with override (open blockers): {forced_str}", ""]
    else:
        lines += [
            "⚪ **Verified (7.2): unknown** — this package was created before the "
            "verification check existed.",
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
            overdue_flag = " ⚠️ OVERDUE" if c.get("overdue") else (
                " ⚠️ DEADLINE UNREADABLE" if c.get("deadline_unreadable") else "")
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

    # A package is modelled as a ROUND: where a requirement appears in several, the
    # LATEST one governs (common.approval_outcome — a settled decision, so a
    # re-submission after rework can be decided). That rule lived only inside the
    # computation, so an overtaken round went on rendering as though it were live:
    # `🔴 Verdict: Not ready for baseline` over a rejection a newer round had already
    # overturned, with nothing saying so. Two live documents of one project
    # contradicting each other.
    superseded_by = superseding_packages(project_name, package_id, package)
    fully_superseded = superseded_by and len(superseded_by) == len(package.get("req_ids") or [])
    if superseded_by:
        later = sorted(set(superseded_by.values()))
        listed = ", ".join(f"`{p}`" for p in later)
        if fully_superseded:
            lines += [
                f"> 📦 **This round has been superseded by {listed}.** Every requirement "
                f"in it has since been decided again, and the later round is what governs "
                f"— the verdict below describes THIS round's decisions, not the project's "
                f"current position.",
                "",
            ]
        else:
            rows = ", ".join(f"`{rid}` → `{pid}`" for rid, pid in sorted(superseded_by.items()))
            lines += [
                f"> 📦 **{len(superseded_by)} requirement(s) of this round have since been "
                f"decided by a later one:** {rows}. For those, the later round governs.",
                "",
            ]

    # Verdict
    verdict_word = "Ready for baseline" if can_baseline else "Not ready for baseline"
    if fully_superseded:
        verdict_icon, verdict_word = "📦", "Superseded — this round no longer decides anything"
    lines += [
        "---",
        "",
        f"## {verdict_icon} Verdict: {verdict_word}",
        "",
    ]

    if verdict_reasons:
        for reason in verdict_reasons:
            lines.append(f"- {reason}")
        lines.append("")

    if fully_superseded:
        # The verdict one line above says this round decides nothing. Inviting a
        # baseline right under it is the document contradicting itself — and the
        # invitation was the harmful half: following it produced a signed record over
        # decisions a later round had already replaced.
        governing = sorted(set(superseded_by.values()))
        lines += [
            "Nothing here is signed off from this round. The requirements have been "
            "decided again by "
            + list_with_cap(governing, formatter=lambda p: f"`{p}`")
            + " — baseline that round instead, or open a new one if the position has "
              "changed again.",
        ]
    elif can_baseline:
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
@guard_artifact_errors
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
        force:             True — baseline despite PROCESS obstacles: pending
                           approvals, overdue conditions, approval below the minimum.
                           Each override is named in the Approval Record.
                           It does NOT lift a rejection from an Accountable or
                           Responsible stakeholder — overriding a person who said no
                           is a different decision from overriding a lapsed date, and
                           one flag for both hid the former behind the latter.
                           (open conditions, consulted-rejected).
                           False (default) — block if blockers exist.

    Returns:
        A summary of the baseline and the next steps. The Approval Record itself is
        the Markdown artifact written via save_artifact — the return value is not it.
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

    # 7.2 verification — reported in the record, never gated (see `_verification_state`).
    vstate = _verification_state(repo, package)

    # Readiness gate — the SAME predicate check_approval_status renders, so the
    # dashboard's "Ready / Not ready" verdict is the real contract. force=True is
    # the deliberate override.
    gate = _baseline_gate(package)
    statuses = gate["statuses"]
    pending_reqs = gate["pending_reqs"]
    approved_pct = gate["approved_pct"]

    # An A/R rejection is not forceable. `force` covers process state — a lapsed
    # deadline, an unanswered request, a percentage — but a named person with decision
    # authority saying no is a different kind of obstacle, and one flag for both meant
    # an analyst forcing past the former silently baselined over the latter.
    if gate["hard_block"]:
        lines = [
            "❌ Baseline blocked by a rejection from an Accountable/Responsible "
            "stakeholder — this is NOT lifted by `force`:",
            "",
        ]
        for b in gate["ar_rejections"]:
            lines.append(
                f"  - `{b['req_id']}` rejected by {b['stakeholder']} ({b['raci']}) "
                f"— {b.get('reason') or '—'}"
            )
        lines += [
            "",
            "A person with decision authority said no. Resolve it with them, then "
            "record the new decision via `record_approval_decision`; or drop the "
            "requirement from the package and prepare a new one.",
        ]
        if gate["forceable"]:
            lines.append(
                f"\n(For reference, `force` would have covered: "
                f"{', '.join(gate['forceable'])}.)"
            )
        return "\n".join(lines)

    if not gate["can_baseline"] and not force:
        lines = ["❌ Baseline blocked:", ""]
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
            "Resolve the issues above, or use `force=true` to force the baseline "
            "creation. `force` will lift exactly: "
            f"{', '.join(gate['forceable'])} — and each one is named in the "
            "Approval Record.",
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
    #
    # A requirement of this package may since have been decided AGAIN by a later round,
    # and the later round governs — the same rule `approval_outcome` applies everywhere
    # else. Re-deriving the outcome from this package alone let a round that no longer
    # decides anything sign off a requirement the governing round had rejected: the
    # record listed it as approved over the rejecting stakeholder's own name, and
    # `status: approved` went into the 5.1 graph.
    #
    # This is NOT a gate. The baseline still gets created, and a requirement whose LATER
    # round approved it is baselined by that later round exactly as before — refusing on
    # decisions taken in other packages is the regression that would break re-submission
    # after rework.
    overtaken = superseding_packages(project_name, package_id, package)
    approved_reqs = []
    for rid in req_ids:
        if rid in overtaken:
            continue
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
        "force_created": force and bool(gate["forceable"] or open_conditions),
        # WHICH gates the override actually lifted. "force_created: true" alone told a
        # later reader that a rule was bypassed but not which one, so the record could
        # not answer the question an auditor asks first.
        "forced_gates": gate["forceable"] if force else [],
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
    # Name what was overridden. "Created forcibly" alone is the same failure as
    # recording nothing: the reader learns a rule was bypassed but not which one.
    forced_gates = gate["forceable"] if force else []
    if forced_gates:
        force_warning = (
            "\n\n> ⚠️ **Baselined with `force`.** These gates were overridden: "
            + ", ".join(forced_gates)
            + (". Open conditions remain." if open_conditions else ".")
        )
    elif force and open_conditions:
        force_warning = (
            "\n\n> ⚠️ The baseline was created with `force=true`. "
            "Open conditions remain."
        )
    else:
        force_warning = ""

    record_lines = [
        f"<!-- BABOK 5.5 — Approval Record, Project: {project_name}, "
        f"Baseline: {baseline_version}, Date: {date.today()} -->",
        "",
        f"# Requirements Baseline: {baseline_version}",
        f"**Project:** {project_name}  ",
        f"**Package:** {package_id} — {package.get('package_title', '—')}  ",
        f"**Methodology:** {approach_label}"
        + (f" ({package.get('approach_source')})" if package.get("approach_source")
           else "") + "  ",
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

    if not approved_reqs:
        record_lines.append("*(none — no requirement in this package reached full approval)*")
    for rid in approved_reqs:
        node = _find_node(repo, rid)
        title = node.get("title", "—") if node else "—"
        version = node.get("version", "—") if node else "—"
        priority = node.get("priority", "—") if node else "—"
        record_lines.append(f"- ✅ `{rid}` {title} (v{version}, priority: {priority})")

    # What this round is NOT entitled to sign off. Silence here would be the same defect
    # one step later: the requirement would simply be missing from the record, and a
    # reader comparing it against the package would find a requirement that went in and
    # never came out.
    if overtaken:
        record_lines += ["", "---", "", "## Decided by a later round", "",
                         "These requirements were in this package, but a later round "
                         "decided them again, and the later round governs. This "
                         "baseline does not sign them off:", ""]
        for rid, later_pkg in sorted(overtaken.items()):
            node = _find_node(repo, rid)
            title = node.get("title", "—") if node else "—"
            record_lines.append(
                f"- 📦 `{rid}` {title} — decided by `{later_pkg}` "
                f"(outcome there: **{approval_outcome(project_name, rid)}**)")

    # What THIS round overturned. A requirement rejected in an earlier round and
    # approved here is decided by this one (the settled "latest round governs" rule),
    # and the reversal is the single most consequential fact in the document — a person
    # with decision authority said no, and this record supersedes them. It used to
    # appear nowhere: the new record was silent, the old package still printed its
    # rejection as current, and the reversal was in no audit trail at all.
    overturned = _decisions_this_round_overrides(project_name, package_id, req_ids)
    if overturned:
        record_lines += ["", "---", "", "## Decisions this round overrides", ""]
        for item in overturned:
            record_lines.append(
                f"- `{item['req_id']}` was **{item['decision']}** by "
                f"`{item['stakeholder']}` ({item['raci']}) in package `{item['package_id']}`"
                + (f" — {item['reason']}" if item.get("reason") else "")
            )
        record_lines += [
            "",
            "These earlier decisions no longer govern: the round recorded here is the "
            "later one. Confirm the people who objected have been brought along.",
        ]

    record_lines += ["", "---", "", "## Stakeholder decisions", ""]
    if not baseline_snapshot["stakeholder_summary"]:
        record_lines.append("*(none — nobody recorded a decision on this package)*")
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

    # The record speaks about the BASELINE, so every statement here is scoped to what
    # actually entered it. Reporting over the whole package named rejected and pending
    # requirements as "approved without verification" — a false statement inside an
    # official artifact, in the very feature whose thesis is that the record must be
    # trustworthy. The dashboard above is different: there the package IS the subject.
    baselined = set(approved_reqs)
    unverified_in_baseline = [r for r in vstate["unverified"] if r in baselined]
    unknown_in_baseline = [r for r in vstate["unknown"] if r in baselined]
    forced_in_baseline = [r for r in vstate["forced"] if r in baselined]

    if unverified_in_baseline or unknown_in_baseline or forced_in_baseline:
        record_lines += ["", "---", "", "## 7.2 verification", ""]

    if unverified_in_baseline:
        ids_str = list_with_cap(unverified_in_baseline, cap=20)
        record_lines += [
            "### ⚠️ Baselined without 7.2 verification",
            "",
            f"**{len(unverified_in_baseline)} requirement(s)** entered the baseline "
            f"without passing verification (7.2): {ids_str}",
            "",
            "> Approval is a stakeholder decision; verification is a quality check.",
            "> These requirements carry an unmeasured quality risk into the baseline.",
            "",
        ]

    if unknown_in_baseline:
        ids_str = ", ".join(f"`{rid}`" for rid in unknown_in_baseline)
        record_lines += [
            "### ⚪ 7.2 verification unknown",
            "",
            f"There is no record either way for: {ids_str}. This package predates the "
            f"verification check, so whether they passed 7.2 cannot be determined — "
            f"which is not the same as saying they failed.",
            "",
        ]

    if forced_in_baseline:
        forced_str = ", ".join(f"`{rid}`" for rid in forced_in_baseline)
        record_lines += [
            "### Verified with override",
            "",
            f"7.2 blockers were open and deliberately overridden: {forced_str}",
            "",
        ]

    # BABOK 3.3 .1 — who was PLANNED to hold approval authority, and who of them
    # actually spoke. A fact for the official record, not a gate: `_baseline_gate`
    # is untouched by B3-2. Matched with the same `is_planned_decision_maker` the
    # warning in record_approval_decision uses, so the record and the warning cannot
    # disagree about who counts as an authority.
    plan, plan_note = load_ba_plan(project_name)
    planned_authority = planned_decision_makers(plan)
    if plan_note and not planned_authority:
        # Same rule as the 5.3 report: without this the Approval Record of a project
        # whose plan is corrupt is byte-identical to one that never planned governance,
        # and this is the document an auditor reads.
        record_lines += ["", "---", "", "## Governance (3.3)", "", plan_note, ""]
    if planned_authority:
        # RACI-guarded on BOTH sides of the block. It was guarded only on the
        # "signed without being planned" list, so a planned approver recorded as
        # `consulted` — a reviewer whose rejection explicitly does NOT block the
        # baseline — counted as having responded and suppressed the "no decision
        # recorded from" line. The record then showed the planned authority as having
        # spoken when it never exercised authority at all.
        authority_decisions = {
            name: sh for name, sh in package["stakeholder_decisions"].items()
            if sh.get("raci") in ("accountable", "responsible")}
        responded = [name for name in authority_decisions
                     if is_planned_decision_maker(plan, name, project_name)]
        responded_keys = set()
        for name in responded:
            responded_keys |= party_aliases(project_name, name)
        silent = [a for a in planned_authority if reg_norm(a) not in responded_keys]
        # Who signed WITHOUT being planned. `record_approval_decision` already warns
        # about this, but that warning lives only in the tool's reply; the Approval
        # Record is the durable document, and filtering the responder list down to
        # planned names left it silent about who actually carried the baseline.
        # B2-bis's rule: recorded without being stated is the same as hidden.
        # RACI-guarded, exactly like the warning — `consulted` is a reviewer and is
        # legitimately absent from the approver list, so naming them here would turn an
        # ordinary review into an authority exception.
        # Registry-bridged like every other governance match, and only a definite
        # PARTY_UNPLANNED is named: with no registry, a planned ROLE and a typed NAME
        # cannot be compared, and this document is signed.
        unplanned_authority, unmatched_authority = [], []
        for name in authority_decisions:
            status = planned_party_status(project_name, planned_authority, name)
            if status == PARTY_UNPLANNED:
                unplanned_authority.append(name)
            elif status == PARTY_UNBRIDGEABLE:
                # Neither list claimed them, so on a project with no registry the
                # record read "Responded: nobody" three lines under that person's own
                # signature — the very defect the unplanned-signer line was added to
                # close, reintroduced by the silence rule that protects them from a
                # false accusation. Silence is right for the accusation, not for the
                # roll-call.
                unmatched_authority.append(name)
        record_lines += [
            "",
            "---",
            "",
            "## Governance (3.3)",
            "",
            f"**Planned approval authority (3.3):** {', '.join(planned_authority)}  ",
            # "No decision recorded from" was false whenever the named person had in
            # fact recorded a `consulted` review — printed twenty lines above, in this
            # same document. The RACI reading is the intended one; the sentence has to
            # say which kind of decision it means.
            # Trailing hard break: without it the ⚠️ line below renders joined onto
            # this one as a single paragraph.
            (f"**Responded (accountable/responsible):** "
             f"{', '.join(responded) or 'nobody'}."
             + (f" No approval decision recorded from: {', '.join(silent)}."
                if silent else "")
             + "  "),
        ]
        if unmatched_authority:
            record_lines.append(
                f"ℹ️ Also decided by: {', '.join(unmatched_authority)} — the platform "
                f"cannot tell whether they are among the planned authority, because "
                f"3.3 plans roles and this record names people. Build the stakeholder "
                f"registry (3.2 / 4.2) to reconcile the two.  ")
        if unplanned_authority:
            record_lines.append(
                f"⚠️ Decided by, without being named in the 3.3 plan: "
                f"{', '.join(unplanned_authority)}.  ")
        record_lines.append("")

    # Built from what the baseline actually contains. As fixed text it advised handing
    # a list of approved requirements to development over a baseline holding NONE, next
    # to two section headings with no body and no word saying they were empty.
    record_lines += ["", "---", "", "## Next steps", ""]
    if approved_reqs:
        record_lines += [
            "1. Hand off the Approval Record to stakeholders via `prepare_communication_package` (4.4)",
            f"2. Hand off the {len(approved_reqs)} approved requirement(s) to development (Chapter 6)",
            "3. Any changes to approved requirements — only via `open_cr` (5.4)",
        ]
    else:
        record_lines += [
            "⚠️ **This baseline contains no approved requirements.** There is nothing to "
            "hand on to development, and nothing here is a statement that the scope was "
            "agreed.",
            "",
            "1. Check the package status with `check_approval_status` — it names what is "
            "pending, rejected or conditional",
            "2. Collect the missing decisions via `record_approval_decision`, then "
            "baseline a new version",
        ]
    record_lines += [
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

    # The same warning the Approval Record carries. The analyst reads THIS string in the
    # chat and does not always open the file, so the epilogue advising them to hand a
    # list of approved requirements to development had to stop being fixed text: over a
    # baseline holding none, step 2 is advice nobody can act on.
    if not approved_reqs:
        output_lines += [
            "⚠️ **This baseline contains no approved requirements.** There is nothing to "
            "hand on to development, and nothing here is a statement that the scope was "
            "agreed.",
            "",
            "### Next steps",
            "",
            "1. Check what is missing with `check_approval_status` — it names what is "
            "pending, rejected or conditional",
            "2. Collect the decisions via `record_approval_decision`, then baseline a "
            "new version",
            "",
            save_path,
        ]
    else:
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
