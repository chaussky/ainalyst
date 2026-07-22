"""
BABOK 5.2 — Maintain Requirements
MCP tools for keeping requirements and their attributes up to date.

Tools:
  - update_requirement           — update a requirement's attributes (status, version, priority...)
  - deprecate_requirements       — mark requirements as deprecated or superseded
  - check_requirements_health    — registry health audit: volatility, stale, abandoned
  - find_reusable_requirements   — find candidates for reuse

Storage: the same JSON repository as 5.1 ({project}_traceability_repo.json).
Each change's history is written to repo["history"].

Hooks: _export_hook() is called after every update.
Returns local_only until integrations/confluence_mcp.py is wired up.

Integration:
  In:  results from 4.3 (status→confirmed), 5.3 (priority), 5.4 (CR decisions), 5.5 (status→approved)
  Out: an up-to-date registry for 5.3, 5.5, 6.x; hook → Confluence

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date, datetime
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import (save_artifact, logger, DATA_DIR, data_path,
                           normalize_project_id, NON_REQUIREMENT_NODE_TYPES,
                           has_been_approved,
    read_json_artifact, guard_artifact_errors,
    VALID_PRIORITIES, MOSCOW_PRIORITIES, LEVEL_PRIORITIES,
)

mcp = FastMCP("BABOK_Requirements_Maintain")

REPO_FILENAME = "traceability_repo.json"

# Volatility threshold — minor version above this value triggers a warning
VOLATILITY_WARNING_THRESHOLD = 3   # version 1.3+
VOLATILITY_CRITICAL_THRESHOLD = 4  # version 1.4+

# "Staleness" threshold in days without an update
STALE_DAYS_WARNING = 30
STALE_DAYS_CRITICAL = 60


# ---------------------------------------------------------------------------
# Utilities — shared with 5.1 (duplicated to avoid circular dependencies)
# ---------------------------------------------------------------------------

def _repo_path(project_name: str) -> str:
    safe_name = normalize_project_id(project_name)
    return data_path(project_name, f"{safe_name}_{REPO_FILENAME}")


def _load_repo(project_name: str) -> dict:
    path = _repo_path(project_name)
    if os.path.exists(path):
        # Raises CorruptArtifactError, converted to a ❌ line by guard_artifact_errors
        # at the tool boundary. A bare json.load here made a damaged file a protocol
        # error in every downstream tool.
        return read_json_artifact(path, "5.1 traceability repository")
    return {
        "project": project_name,
        "formality_level": "Standard",
        "created": str(date.today()),
        "updated": str(date.today()),
        "requirements": [],
        "links": [],
        "history": []
    }


def _save_repo(repo: dict) -> str:
    path = _repo_path(repo["project"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    repo["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)
    logger.info(f"Repository updated (5.2): {path}")
    return path


def _find_req(repo: dict, req_id: str) -> Optional[dict]:
    for r in repo["requirements"]:
        if r["id"] == req_id:
            return r
    return None


def _version_to_float(version: str) -> float:
    """Converts '1.3' → 1.3 for comparison."""
    try:
        return float(version)
    except (ValueError, TypeError):
        return 1.0


def _minor_version(version: str) -> int:
    """Returns the minor part of the version: '1.3' → 3."""
    try:
        parts = str(version).split(".")
        return int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return 0


def _days_since(date_str: str) -> int:
    """Number of days since the given date."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return (date.today() - d).days
    except (ValueError, TypeError):
        return 0


# ---------------------------------------------------------------------------
# Hook for external storage
# ---------------------------------------------------------------------------

_ARTIFACT_LABELS = {
    "requirement_update": "Requirement update",
    "deprecation": "Deprecated requirements",
    "health_report": "Requirements health audit",
    "reuse_list": "Reuse candidates",
}

# Snapshots of the CURRENT state: there should be exactly one page per project that
# gets updated in place. Dating their titles creates a new page every day and the
# "living" report fragments into dozens of copies.
_LIVING_ARTIFACTS = {"health_report", "reuse_list"}


def _requirement_discriminator(metadata: dict) -> str:
    """Requirement ids that keep event-page titles distinct.

    Without this, two updates of DIFFERENT requirements on the same day produce the
    same page title and the second silently overwrites the first in Confluence.
    """
    req_id = metadata.get("req_id")
    if req_id:
        return str(req_id)

    req_ids = metadata.get("req_ids") or []
    if isinstance(req_ids, str):
        req_ids = [req_ids]
    if not req_ids:
        return ""

    shown = ", ".join(str(r) for r in req_ids[:3])
    return f"{shown} +{len(req_ids) - 3}" if len(req_ids) > 3 else shown


def _confluence_page_title(artifact_type: str, project_name: str, metadata: dict) -> str:
    """Builds the Confluence page title for an exported 5.2 artifact."""
    label = _ARTIFACT_LABELS.get(artifact_type, artifact_type)

    if artifact_type in _LIVING_ARTIFACTS:
        return f"{project_name} — {label}"

    discriminator = _requirement_discriminator(metadata)
    if discriminator:
        return f"{project_name} — {label} — {discriminator} ({date.today()})"
    return f"{project_name} — {label} ({date.today()})"


def _export_hook(artifact_type: str, content: str, metadata: dict) -> dict:
    """
    Export hook — called after every significant update in 5.2.

    If the CONFLUENCE_URL + CONFLUENCE_API_TOKEN environment variables are set,
    automatically syncs the artifact to Confluence via confluence_mcp.
    Otherwise returns local_only.

    Args:
        artifact_type: artifact type ('requirement_update', 'health_report', 'reuse_list')
        content:       Markdown content of the artifact
        metadata:      dict with project_name, req_ids, operation, etc.

    Returns:
        {"status": "synced", "url": "..."} or {"status": "local_only", "note": "..."}
    """
    # Check for Confluence config
    if not os.environ.get("CONFLUENCE_URL") or not os.environ.get("CONFLUENCE_API_TOKEN"):
        return {
            "status": "local_only",
            "note": (
                "To sync with Confluence, set the environment variables: "
                "CONFLUENCE_URL, CONFLUENCE_API_TOKEN, CONFLUENCE_SPACE_KEY. "
                "Details: skills/integrations/confluence_mcp.py"
            )
        }

    try:
        from skills.integrations.confluence_mcp import export_artifact_to_confluence

        project_name = metadata.get("project_name", "BA Project")
        page_title = _confluence_page_title(artifact_type, project_name, metadata)

        result = export_artifact_to_confluence(
            content_markdown=content,
            page_title=page_title,
        )
        logger.info(f"[export_hook] Confluence: {result.get('status')}")
        # Callers report the failure reason via `note`; export_artifact_to_confluence
        # reports it via `message`. Normalize here so a configured-but-failing sync
        # (bad token, missing CONFLUENCE_SPACE_KEY, no permission) is never silent.
        if result.get("status") != "synced" and not result.get("note"):
            result["note"] = result.get("message") or "Confluence sync failed."
        return result

    except ImportError:
        return {"status": "local_only", "note": "The integrations/confluence_mcp.py module is unavailable"}
    except Exception as e:
        logger.warning(f"[export_hook] Confluence error: {e}")
        return {"status": "local_only", "note": f"Sync error: {e}"}


# ---------------------------------------------------------------------------
# 5.2.1 — Update a requirement or its attributes
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def update_requirement(
    project_name: str,
    req_id: str,
    change_reason: str,
    new_status: str = "",
    new_version: str = "",
    new_priority: str = "",
    new_owner: str = "",
    new_stability: str = "",
    new_title: str = "",
    reuse_candidate: str = "",
    reuse_scope: str = "",
    complexity: str = "",
    note: str = "",
) -> str:
    """
    BABOK 5.2 — Updates a requirement's attributes. Records the change in the history.

    Versioning rule:
      Minor (1.0→1.1): wording clarification, acceptance-criteria change
      Major (1.0→2.0): change in substance, merging or splitting requirements
      No version change: status, priority, owner change (content unchanged)

    Args:
        project_name:    Project name.
        req_id:          Requirement ID: BR-001, FR-007, etc.
        change_reason:   Reason for the change — required. Recorded in the history.
        new_status:      New status. Allowed values:
                         draft | confirmed | approved | implemented |
                         on_hold | deprecated | superseded | retired
                         Empty string — leave unchanged.
        new_version:     New version in major.minor format (1.1, 2.0).
                         Empty string — leave unchanged.
        new_priority:    High | Medium | Low. Empty string — leave unchanged.
        new_owner:       Owner name/role. Empty string — leave unchanged.
        new_stability:   Stable | Volatile | Unknown. Empty string — leave unchanged.
        new_title:       New requirement wording. Empty string — leave unchanged.
        reuse_candidate: "true" | "false". Empty string — leave unchanged.
        reuse_scope:     initiative | program | division | enterprise. Empty string — leave unchanged.
        complexity:      Low | Medium | High. Empty string — leave unchanged.
        note:            Additional BA note (optional).

    Returns:
        Update confirmation with the requirement's change history.
    """
    logger.info(f"update_requirement: {req_id} in project '{project_name}'")

    repo = _load_repo(project_name)
    req = _find_req(repo, req_id)

    if not req:
        return (
            f"❌ Requirement `{req_id}` not found in the `{project_name}` project repository.\n"
            f"Check the ID, or add the requirement via `init_traceability_repo` (5.1)."
        )

    # `priority` is the one attribute here with a closed vocabulary, and it was the one
    # attribute not validated. An unrecognised value stored cleanly and then matched no
    # consumer: 5.3's aggregation, 5.5's critical-requirement warning and 7.5's Must
    # coverage all simply skipped it, so the requirement lost its priority silently.
    if new_priority and new_priority not in VALID_PRIORITIES:
        return (
            f"❌ Unknown priority `{new_priority}`.\n"
            f"   MoSCoW (5.3): {', '.join(sorted(MOSCOW_PRIORITIES))}\n"
            f"   Levels (7.1): {', '.join(sorted(LEVEL_PRIORITIES))}"
        )

    changes = []
    old_values = {}

    def _apply(attr: str, new_val: str, display_name: str):
        if new_val:
            old_values[attr] = req.get(attr, "—")
            req[attr] = new_val
            changes.append(f"- **{display_name}:** `{old_values[attr]}` → `{new_val}`")

    _apply("status", new_status, "Status")
    _apply("version", new_version, "Version")
    _apply("priority", new_priority, "Priority")
    _apply("owner", new_owner, "Owner")
    _apply("stability", new_stability, "Stability")
    _apply("title", new_title, "Wording")
    _apply("complexity", complexity, "Complexity")
    _apply("reuse_scope", reuse_scope, "Reuse scope")

    if reuse_candidate:
        old_val = req.get("reuse_candidate", "—")
        val = reuse_candidate.lower() == "true"
        req["reuse_candidate"] = val
        changes.append(f"- **Reuse candidate:** `{old_val}` → `{val}`")

    if not changes:
        return f"ℹ️ No changes for requirement `{req_id}`. Specify at least one attribute to update."

    req["last_reviewed"] = str(date.today())

    # Auto-recalculate stability based on volatility
    if not new_stability and new_version:
        minor = _minor_version(req.get("version", "1.0"))
        if minor >= VOLATILITY_CRITICAL_THRESHOLD:
            req["stability"] = "Volatile"
            changes.append(f"- **Stability (auto):** recalculated → `Volatile` (version {req['version']})")
        elif minor >= VOLATILITY_WARNING_THRESHOLD:
            if req.get("stability") != "Volatile":
                req["stability"] = "Volatile"
                changes.append(f"- **Stability (auto):** recalculated → `Volatile` (version {req['version']})")

    # Record in history
    history_entry = {
        "action": "requirement_updated",
        "req_id": req_id,
        "changes": {k: {"from": old_values[k], "to": req[k]} for k in old_values},
        "reason": change_reason,
        "note": note,
        "date": str(date.today()),
    }
    repo["history"].append(history_entry)

    _save_repo(repo)

    # Volatility check — warning
    volatility_warning = ""
    current_minor = _minor_version(req.get("version", "1.0"))
    if current_minor >= VOLATILITY_CRITICAL_THRESHOLD:
        volatility_warning = (
            f"\n\n🔴 **High volatility:** version `{req.get('version')}` — "
            f"the requirement is unstable. Recommend discussing the root cause with the stakeholder."
        )
    elif current_minor >= VOLATILITY_WARNING_THRESHOLD:
        volatility_warning = (
            f"\n\n⚠️ **Note:** version `{req.get('version')}` — "
            f"the requirement is starting to show signs of instability."
        )

    lines = [
        f"✅ Requirement `{req_id}` updated",
        "",
        f"**Project:** {project_name}  ",
        f"**Reason for change:** {change_reason}  ",
        f"**Date:** {date.today()}",
        "",
        "### Changes:",
        "",
    ] + changes

    if note:
        lines += ["", f"**BA note:** {note}"]

    lines += [
        "",
        "### Current requirement state:",
        "",
        f"| Attribute | Value |",
        f"|---------|----------|",
        f"| ID | `{req.get('id')}` |",
        f"| Type | {req.get('type', '—')} |",
        f"| Wording | {req.get('title', '—')} |",
        f"| Status | {req.get('status', '—')} |",
        f"| Version | {req.get('version', '—')} |",
        f"| Priority | {req.get('priority', '—')} |",
        f"| Owner | {req.get('owner', '—')} |",
        f"| Stability | {req.get('stability', '—')} |",
        f"| Reuse candidate | {req.get('reuse_candidate', '—')} |",
        f"| Last reviewed | {req.get('last_reviewed', '—')} |",
    ]

    content = "\n".join(lines) + volatility_warning

    # Export hook
    hook_result = _export_hook(
        "requirement_update",
        content,
        {"project_name": project_name, "req_id": req_id, "operation": "update"}
    )
    if hook_result.get("status") == "synced":
        content += f"\n\n🔗 Synced: {hook_result.get('url', '')}"
    else:
        content += f"\n\n💾 Saved locally. {hook_result.get('note', '')}"

    save_artifact(content, prefix="5_2_requirement_update", project_id=project_name)
    return content


# ---------------------------------------------------------------------------
# 5.2.2 — Mark requirements as deprecated / superseded
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def deprecate_requirements(
    project_name: str,
    req_ids_json: str,
    final_status: Literal["deprecated", "superseded", "retired"],
    reason: str,
    superseded_by: str = "",
) -> str:
    """
    BABOK 5.2 — Marks requirements as deprecated, superseded, or retired.

    Requirements are NOT deleted — only marked. The history is preserved for audit and traceability.
    After deprecation, recommend checking active links via check_coverage (5.1).

    Args:
        project_name:   Project name.
        req_ids_json:   JSON list of requirement IDs: ["FR-007", "FR-008"]
        final_status:   deprecated  — outdated, no replacement
                        superseded  — replaced by another requirement
                        retired     — project complete, requirement archived
        reason:         Reason (required). Recorded in the history.
        superseded_by:  ID of the new requirement (only for superseded). E.g.: "FR-012"

    Returns:
        Report on marked requirements + a warning about active links.
    """
    logger.info(f"deprecate_requirements: status={final_status}, project='{project_name}'")

    try:
        req_ids = json.loads(req_ids_json)
    except json.JSONDecodeError as e:
        return f"❌ Error parsing req_ids_json: {e}"

    repo = _load_repo(project_name)

    if final_status == "superseded" and not superseded_by:
        return "❌ For the `superseded` status, you must specify `superseded_by` — the ID of the new requirement."

    processed = []
    not_found = []

    for req_id in req_ids:
        req = _find_req(repo, req_id)
        if not req:
            not_found.append(req_id)
            continue

        old_status = req.get("status", "—")
        req["status"] = final_status
        req["last_reviewed"] = str(date.today())
        if superseded_by:
            req["superseded_by"] = superseded_by

        repo["history"].append({
            "action": f"requirement_{final_status}",
            "req_id": req_id,
            "changes": {"status": {"from": old_status, "to": final_status}},
            "reason": reason,
            "superseded_by": superseded_by or None,
            "date": str(date.today()),
        })
        processed.append({"id": req_id, "title": req.get("title", "—"), "old_status": old_status})

    _save_repo(repo)

    # Check active links for deprecated requirements
    active_links_warning = []
    for item in processed:
        req_id = item["id"]
        active = [
            lnk for lnk in repo["links"]
            if (lnk["from"] == req_id or lnk["to"] == req_id)
        ]
        if active:
            active_links_warning.append(f"`{req_id}` has **{len(active)}** active traceability link(s)")

    status_labels = {
        "deprecated": "🗄️ Deprecated",
        "superseded": "🔄 Superseded",
        "retired": "📦 Retired (archived)",
    }

    lines = [
        f"<!-- BABOK 5.2 — Deprecation | Project: {project_name} | {date.today()} -->",
        "",
        f"# {status_labels[final_status]}",
        "",
        f"**Project:** {project_name}  ",
        f"**Reason:** {reason}  ",
        f"**Date:** {date.today()}",
    ]

    if superseded_by:
        lines.append(f"**Superseded by:** `{superseded_by}`  ")

    lines += [
        "",
        f"## Processed: {len(processed)} requirement(s)",
        "",
        "| ID | Title | Old status | New status |",
        "|----|----------|-----------|--------------|",
    ]

    for item in processed:
        lines.append(
            f"| `{item['id']}` | {item['title']} | {item['old_status']} | **{final_status}** |"
        )

    if not_found:
        lines += [
            "",
            f"⚠️ Not found in the repository: {', '.join(f'`{i}`' for i in not_found)}",
        ]

    if active_links_warning:
        lines += [
            "",
            "## ⚠️ Warning: active traceability links",
            "",
            "The following requirements have active links — recommend checking via `check_coverage` (5.1):",
            "",
        ]
        for w in active_links_warning:
            lines.append(f"- {w}")
        lines += [
            "",
            "> Links may point to tests, components, or other requirements that",
            "> still reference the deprecated requirement.",
        ]

    lines += [
        "",
        "---",
        "**Next step:** run `check_coverage` (5.1) to check for orphaned links.",
    ]

    content = "\n".join(lines)

    hook_result = _export_hook(
        "deprecation",
        content,
        {"project_name": project_name, "req_ids": req_ids, "final_status": final_status}
    )
    if hook_result.get("status") != "synced":
        content += f"\n\n💾 Saved locally. {hook_result.get('note', '')}"

    save_artifact(content, prefix="5_2_deprecation", project_id=project_name)
    return content


# ---------------------------------------------------------------------------
# 5.2.3 — Requirements registry health audit
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def check_requirements_health(
    project_name: str,
    filter_type: str = "",
    filter_status: str = "",
) -> str:
    """
    BABOK 5.2 — Requirements registry health audit.

    What it looks for:
      🔴 High volatility (version 1.4+) — the requirement is unstable
      🟡 Medium volatility (version 1.2-1.3) — worth checking
      🟡 Stale (not updated for >60 days) — possibly outdated
      🟡 Long in draft (>30 days) — confirm or freeze
      🟡 No owner — nobody accountable for keeping it current
      🟢 Healthy requirements — all good

    Args:
        project_name:   Project name.
        filter_type:    Filter by type: business | stakeholder | solution | transition
                        Empty string — all.
        filter_status:  Filter by status. Empty string — all active
                        (excludes deprecated, superseded, retired).

    Returns:
        Registry health report with recommendations.
    """
    logger.info(f"check_requirements_health: '{project_name}'")

    repo = _load_repo(project_name)
    # Only requirements are maintained here. The health criteria — volatility, owner,
    # staleness, reuse — describe a requirement's lifecycle, so applying them to other
    # chapters' nodes produced a report demanding an owner for every business objective
    # and every risk in the register. An explicit filter_type still wins, so a BA who
    # deliberately asks for `risk` gets it.
    requirements = repo["requirements"]
    if not filter_type:
        requirements = [r for r in requirements
                        if r.get("type", "") not in NON_REQUIREMENT_NODE_TYPES]

    # By default — active only (not archived)
    archive_statuses = {"deprecated", "superseded", "retired"}
    if not filter_status:
        requirements = [r for r in requirements if r.get("status") not in archive_statuses]
    else:
        requirements = [r for r in requirements if r.get("status") == filter_status]

    if filter_type:
        requirements = [r for r in requirements if r.get("type") == filter_type]

    if not requirements:
        return f"ℹ️ No active requirements found in the `{project_name}` repository."

    critical = []    # 🔴
    warnings = []    # 🟡
    healthy = []     # 🟢

    for req in requirements:
        req_id = req.get("id", "?")
        issues = []

        # Volatility
        minor = _minor_version(req.get("version", "1.0"))
        if minor >= VOLATILITY_CRITICAL_THRESHOLD:
            issues.append(f"🔴 High volatility (v{req.get('version')})")
        elif minor >= VOLATILITY_WARNING_THRESHOLD:
            issues.append(f"🟡 Medium volatility (v{req.get('version')})")

        # Stale
        last_reviewed = req.get("last_reviewed") or req.get("added", "")
        if last_reviewed:
            days = _days_since(last_reviewed)
            if days > STALE_DAYS_CRITICAL:
                issues.append(f"🟡 Not updated for {days} days")
            elif days > STALE_DAYS_WARNING:
                issues.append(f"🟡 Not updated for {days} days — worth checking")

        # Long in draft
        if req.get("status") == "draft":
            added = req.get("added", "")
            if added:
                days_draft = _days_since(added)
                if days_draft > STALE_DAYS_WARNING:
                    issues.append(f"🟡 In draft status for {days_draft} days already")

        # No owner
        if not req.get("owner"):
            issues.append("🟡 No owner")

        req_info = {
            "id": req_id,
            "title": req.get("title", "—"),
            "type": req.get("type", "—"),
            "status": req.get("status", "—"),
            "version": req.get("version", "1.0"),
            "owner": req.get("owner", "—"),
            "issues": issues,
        }

        if any("🔴" in i for i in issues):
            critical.append(req_info)
        elif issues:
            warnings.append(req_info)
        else:
            healthy.append(req_info)

    total = len(requirements)
    health_pct = round(len(healthy) / total * 100) if total else 0

    lines = [
        f"<!-- BABOK 5.2 — Health Audit | Project: {project_name} | {date.today()} -->",
        "",
        f"# 🏥 Requirements registry health audit",
        "",
        f"**Project:** {project_name}  ",
        f"**Filter:** type={filter_type or 'all'}, status={filter_status or 'active'}  ",
        f"**Date:** {date.today()}",
        "",
        "## Summary",
        "",
        "| Status | Count | % |",
        "|--------|--------|---|",
        f"| 🟢 Healthy | {len(healthy)} | {health_pct}% |",
        f"| 🟡 Need attention | {len(warnings)} | {round(len(warnings)/total*100) if total else 0}% |",
        f"| 🔴 Critical | {len(critical)} | {round(len(critical)/total*100) if total else 0}% |",
        f"| **Total active** | **{total}** | 100% |",
        "",
    ]

    if critical:
        lines += [
            "## 🔴 Critical issues",
            "",
            "| ID | Type | Title | v | Status | Issue |",
            "|----|-----|----------|---|--------|----------|",
        ]
        for r in critical:
            problem = "; ".join(r["issues"])
            lines.append(
                f"| `{r['id']}` | {r['type']} | {r['title']} | {r['version']} | {r['status']} | {problem} |"
            )
        lines += [
            "",
            "> **Recommendation:** discuss the root cause of instability with the stakeholder.",
            "> High volatility often points to an elicitation problem (4.2), not the content itself.",
            "",
        ]

    if warnings:
        lines += [
            "## 🟡 Need attention",
            "",
            "| ID | Type | Title | v | Owner | Issue |",
            "|----|-----|----------|---|----------|----------|",
        ]
        for r in warnings:
            problem = "; ".join(r["issues"])
            lines.append(
                f"| `{r['id']}` | {r['type']} | {r['title']} | {r['version']} | {r['owner']} | {problem} |"
            )
        lines.append("")

    if healthy:
        lines += [
            "## 🟢 Healthy requirements",
            "",
            f"**{len(healthy)} requirement(s)** in good shape — current, have an owner, stable.",
            "",
        ]

    lines += [
        "---",
        "",
        "## Recommended actions",
        "",
    ]

    if critical:
        lines.append(
            f"1. 🔴 **{len(critical)} critical** — discuss the volatility, "
            f"update via `update_requirement` or `deprecate_requirements`."
        )
    if warnings:
        no_owner = sum(1 for r in warnings if "owner" in " ".join(r["issues"]))
        stale = sum(1 for r in warnings if "days" in " ".join(r["issues"]))
        if no_owner:
            lines.append(f"2. 🟡 **{no_owner} without an owner** — assign an owner via `update_requirement`.")
        if stale:
            lines.append(f"3. 🟡 **{stale} not updated in a while** — confirm relevance with the stakeholder.")
    if not critical and not warnings:
        lines.append("✅ The registry is in good shape. Ready for prioritization (5.3) and approval (5.5).")

    content = "\n".join(lines)

    hook_result = _export_hook(
        "health_report",
        content,
        {"project_name": project_name, "health_pct": health_pct}
    )
    if hook_result.get("status") != "synced":
        content += f"\n\n💾 Saved locally. {hook_result.get('note', '')}"

    save_artifact(content, prefix="5_2_health_check", project_id=project_name)
    return content


# ---------------------------------------------------------------------------
# 5.2.4 — Find candidates for reuse
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def find_reusable_requirements(
    project_name: str,
    search_query: str = "",
    filter_type: str = "",
    min_reuse_scope: Literal["initiative", "program", "division", "enterprise"] = "initiative",
) -> str:
    """
    BABOK 5.2 — Finds requirements that are candidates for reuse.

    Good-candidate criteria (checked automatically):
      ✅ reuse_candidate flag = True
      ✅ Status approved or implemented (proven in practice)
      ✅ Low volatility (version ≤ 1.1)
      ✅ Type business or stakeholder (high level of abstraction)

    Args:
        project_name:     Project name.
        search_query:     Search query against the requirement text (optional).
        filter_type:      Filter by type: business | stakeholder | solution | transition
        min_reuse_scope:  Minimum scope level: initiative | program | division | enterprise

    Returns:
        List of candidates with a reuse-suitability score.
    """
    logger.info(f"find_reusable_requirements: '{project_name}', query='{search_query}'")

    repo = _load_repo(project_name)
    scope_order = ["initiative", "program", "division", "enterprise"]
    min_scope_idx = scope_order.index(min_reuse_scope)

    candidates = []
    others = []  # requirements without the reuse flag, but potentially suitable

    for req in repo["requirements"]:
        # Skip archived
        if req.get("status") in {"deprecated", "superseded", "retired"}:
            continue

        # Only requirement-role nodes can be reused as requirements. The neighbour
        # check_requirements_health already filters by role; this loop did not, so
        # the reuse report offered a change request as a confirmed candidate (its
        # 5.4 status literal is `approved`, which scores like a 5.5 approval) and
        # every risk and goal as potential candidates.
        #
        # `business` is deliberately NOT excluded here, although it sits in
        # NON_REQUIREMENT_NODE_TYPES as the legacy root type: the same literal is
        # ALSO the BABOK requirement CLASS (business requirement — the most
        # reusable kind, which this very loop scores "+2 high level of
        # abstraction"). Dropping it would silently discard BRs an analyst flagged
        # `reuse_candidate` — the `solution` lesson (one literal, two populations;
        # under-counting a requirement is the worse failure) applied to its twin.
        if req.get("type", "") in (NON_REQUIREMENT_NODE_TYPES - {"business"}):
            continue

        # Filter by type
        if filter_type and req.get("type") != filter_type:
            continue

        # Filter by search query
        if search_query:
            text = (req.get("title", "") + " " + req.get("id", "")).lower()
            if search_query.lower() not in text:
                continue

        # Suitability score
        score = 0
        score_notes = []

        is_reuse = req.get("reuse_candidate", False)
        if is_reuse:
            score += 3
            score_notes.append("✅ Marked as a reuse candidate")

        status = req.get("status", "")
        # "Proven in practice" is a fact about the requirement's history, not about
        # whichever chapter wrote `status` last. A requirement approved in 5.5 and
        # then validated in 7.3 reads `validated` and used to silently lose the two
        # points — the reuse ranking degraded as the project matured.
        if has_been_approved(project_name, req.get("id", "")):
            score += 2
            score_notes.append("✅ Approved in 5.5 — proven in practice")
        elif status == "implemented":
            score += 2
            score_notes.append("✅ Status implemented — proven in practice")
        elif status == "approved":
            # No approval records (a legacy project, or an approval recorded outside
            # 5.5). The status is the only evidence there is, so it still counts.
            score += 2
            score_notes.append("✅ Status approved — proven in practice")
        elif status == "confirmed":
            score += 1
            score_notes.append("🟡 Status confirmed — not yet approved")

        minor = _minor_version(req.get("version", "1.0"))
        if minor <= 1:
            score += 2
            score_notes.append(f"✅ Low volatility (v{req.get('version', '1.0')})")
        elif minor <= 3:
            score += 1
            score_notes.append(f"🟡 Moderate volatility (v{req.get('version')})")
        else:
            score_notes.append(f"❌ High volatility (v{req.get('version')}) — risk on reuse")

        req_type = req.get("type", "")
        if req_type in ("business", "stakeholder"):
            score += 2
            score_notes.append("✅ High level of abstraction (business/stakeholder)")
        elif req_type == "solution":
            score += 0
            score_notes.append("🟡 Solution requirement — limited reuse")

        req_scope = req.get("reuse_scope", "initiative")
        scope_idx = scope_order.index(req_scope) if req_scope in scope_order else 0
        if scope_idx >= min_scope_idx:
            score += 1

        req_info = {
            "id": req.get("id"),
            "title": req.get("title", "—"),
            "type": req_type,
            "status": status,
            "version": req.get("version", "1.0"),
            "owner": req.get("owner", "—"),
            "reuse_scope": req.get("reuse_scope", "initiative"),
            "score": score,
            "score_notes": score_notes,
            "is_reuse": is_reuse,
        }

        if is_reuse or score >= 5:
            candidates.append(req_info)
        elif score >= 3:
            others.append(req_info)

    # Sort by score
    candidates.sort(key=lambda x: x["score"], reverse=True)
    others.sort(key=lambda x: x["score"], reverse=True)

    lines = [
        f"<!-- BABOK 5.2 — Reuse | Project: {project_name} | {date.today()} -->",
        "",
        f"# ♻️ Reuse candidates",
        "",
        f"**Project:** {project_name}  ",
        f"**Query:** {search_query or 'all'}  ",
        f"**Type:** {filter_type or 'all'}  ",
        f"**Minimum scope:** {min_reuse_scope}  ",
        f"**Date:** {date.today()}",
        "",
        f"Found **{len(candidates)}** confirmed candidate(s), "
        f"**{len(others)}** potential.",
        "",
    ]

    if candidates:
        lines += [
            "## ✅ Confirmed candidates",
            "",
        ]
        for r in candidates:
            lines += [
                f"### `{r['id']}` — {r['title']}",
                "",
                f"| Attribute | Value |",
                f"|---------|----------|",
                f"| Type | {r['type']} |",
                f"| Status | {r['status']} |",
                f"| Version | {r['version']} |",
                f"| Owner | {r['owner']} |",
                f"| Scope | {r['reuse_scope']} |",
                f"| Score | {'⭐' * min(r['score'], 5)} ({r['score']}/10) |",
                "",
                "**Suitability score:**",
            ]
            for note in r["score_notes"]:
                lines.append(f"- {note}")
            lines.append("")

    if others:
        lines += [
            "## 🟡 Potential candidates (not explicitly flagged)",
            "",
            "| ID | Type | Title | Status | v | Score |",
            "|----|-----|----------|--------|---|--------|",
        ]
        for r in others:
            stars = "⭐" * min(r["score"], 5)
            lines.append(
                f"| `{r['id']}` | {r['type']} | {r['title']} | {r['status']} | {r['version']} | {stars} |"
            )
        lines += [
            "",
            "> Flag as a reuse candidate: `update_requirement(reuse_candidate='true')`",
        ]

    if not candidates and not others:
        lines += [
            "ℹ️ No suitable candidates found matching the given criteria.",
            "",
            "Try:",
            "- Removing the type filter",
            "- Lowering min_reuse_scope to 'initiative'",
            "- Flagging requirements via `update_requirement(reuse_candidate='true')`",
        ]

    lines += [
        "",
        "---",
        "",
        "## Next step",
        "",
        "Before including in a new initiative — stakeholders verify the selected",
        "requirements are still current. A requirement being reused is added to the new",
        "repository with a `source` pointing back to the original.",
    ]

    content = "\n".join(lines)

    hook_result = _export_hook(
        "reuse_list",
        content,
        {"project_name": project_name, "candidates_count": len(candidates)}
    )
    if hook_result.get("status") != "synced":
        content += f"\n\n💾 Saved locally. {hook_result.get('note', '')}"

    save_artifact(content, prefix="5_2_reuse_candidates", project_id=project_name)
    return content


if __name__ == "__main__":
    mcp.run()
