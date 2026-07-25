"""
BABOK 7.2 — Verify Requirements
MCP tools for verifying requirements: checking the quality of statements,
model consistency, issue tracking, status management.

Tools:
  - check_req_quality         — checks reqs against the 9 BABOK characteristics (Groups A+B)
  - check_model_consistency   — cross-model check of .md and .puml files from 7.1
  - open_verification_issue   — record a verification problem
  - resolve_verification_issue — close an issue after a fix
  - mark_req_verified         — set the verified status in 5.1
  - get_verification_report   — summary report on project verification

ADR-027: rule-based MCP + interpretation in Claude Code (not API-in-MCP)
ADR-028: issues in a separate file {project}_verification_issues.json
ADR-029: cross-model verification — a separate tool

Reads: repository 5.1, the specs directory from 7.1
Writes: the verified status in 5.1, {project}_verification_issues.json
Output: Verification Report -> 5.5 (Approve), 7.3 (Validate)

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
import re
import glob
from datetime import date, datetime
from typing import Optional
from mcp.server.fastmcp import FastMCP
from skills.common import (
    save_artifact, logger, DATA_DIR, data_path, normalize_project_id, specs_dir,
    has_passed_verification, was_verification_forced, NON_REQUIREMENT_NODE_TYPES,
    approval_outcome, APPROVAL_OUTCOME_APPROVED, APPROVAL_OUTCOME_CONDITIONAL,
    APPROVAL_OUTCOME_UNKNOWN,
    read_json_artifact, guard_artifact_errors,
    find_spec_file, spec_section_body,
)

mcp = FastMCP("BABOK_Requirements_Verify")

REPO_FILENAME = "traceability_repo.json"
ISSUES_FILENAME = "verification_issues.json"

# Statuses that record an OUTCOME of the 5.5 approval process. A 7.2 re-check must not
# roll one of these back: verification keeps its own durable history record, approval
# does not, so the downgrade would destroy the only trace of the decision.
APPROVAL_OUTCOME_STATUSES = {"approved", "conditional_approved", "rejected"}


# ---------------------------------------------------------------------------
# Dictionaries and patterns (ADR-027: rule-based)
# ---------------------------------------------------------------------------

ATOMICITY_SIGNALS = [
    " and ", " as well as ", " plus ",
    " in addition ", " additionally ", " also ",
    " besides ", " moreover ", " furthermore ",
    " along with ", " together with ",
]

AMBIGUITY_SIGNALS = [
    "fast", "quick", "quickly", "faster",
    "slow", "slowly",
    "convenient", "conveniently", "user-friendly", "user friendly",
    "easy", "easily", "simple",
    "good", "nice",
    "high-quality", "high quality", "quality",
    "efficient", "efficiently",
    "optimal", "optimally",
    "often", "rarely", "periodically", "sometimes",
    "usually", "as a rule", "in most cases", "frequently",
    "should try to", "if possible", "where possible",
    "in a timely manner", "as soon as possible", "as fast as possible",
    "if necessary", "desirable", "preferably", "recommended",
    "acceptable", "allowed",
    "small", "large", "significant", "substantial",
    "enough", "sufficient", "adequate", "appropriate",
    "on time", "promptly", "without delays", "swiftly",
    "and/or", "modern", "up-to-date", "standard", "typical",
]

CONCISENESS_SIGNALS = [
    "implement via", "implement using", "use the technology",
    "use the framework", "write code", "create a table in the database",
    "use rest", "use api", "call the method",
    "previously was", "historically", "in the previous version",
]

MEASURABILITY_PATTERNS = [
    r'\d+\s*(?:ms|s\b|sec|min|hr|hour|%|mb|gb|tb|rpm|rps|tps)',
    r'no more than \d+', r'no less than \d+', r'up to \d+', r'from \d+',
    r'\d+\s*seconds?', r'\d+\s*minutes?', r'\d+\s*users?',
    r'100\s*%', r'0 errors', r'zero', r'fully',
    r'\d+\s*requests?', r'\d+\s*transactions?',
]

CONDITION_PATTERNS = [
    r'if ', r'when ', r'upon ', r'in case ', r'provided that ',
    r'unless ', r'whenever ',
]


# ---------------------------------------------------------------------------
# Utilities — repository 5.1
# ---------------------------------------------------------------------------

def _repo_path(project_id: str) -> str:
    safe = normalize_project_id(project_id)
    return data_path(project_id, f"{safe}_{REPO_FILENAME}")


def _load_repo(project_id: str) -> dict:
    path = _repo_path(project_id)
    if os.path.exists(path):
        # Raises CorruptArtifactError, converted to a ❌ line by guard_artifact_errors
        # at the tool boundary. A bare json.load here made a damaged file a protocol
        # error in every downstream tool.
        return read_json_artifact(path, "5.1 traceability repository")
    return {"project": project_id, "requirements": [], "links": [], "history": []}


def _save_repo(repo: dict) -> None:
    project_id = repo["project"]
    path = _repo_path(project_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    repo["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)
    logger.info(f"Repository 5.1 updated (7.2): {path}")


def _find_req(repo: dict, req_id: str) -> Optional[dict]:
    for r in repo["requirements"]:
        if r["id"] == req_id:
            return r
    return None


# ---------------------------------------------------------------------------
# Utilities — issues file (ADR-028)
# ---------------------------------------------------------------------------

def _issues_path(project_id: str) -> str:
    safe = normalize_project_id(project_id)
    return data_path(project_id, f"{safe}_{ISSUES_FILENAME}")


def _load_issues(project_id: str) -> dict:
    path = _issues_path(project_id)
    if os.path.exists(path):
        # Raises CorruptArtifactError, converted to a ❌ line by guard_artifact_errors
        # at the tool boundary. A bare json.load here made a damaged file a protocol
        # error in every downstream tool.
        return read_json_artifact(path, "7.2 verification issues file")
    return {
        "project": project_id,
        "issues": {},
        "stats": {"open": 0, "closed": 0, "total": 0},
        "created": str(date.today()),
        "updated": str(date.today()),
    }


def _save_issues(data: dict) -> None:
    path = _issues_path(data["project"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Issues file updated (7.2): {path}")


def _next_issue_id(data: dict) -> str:
    existing = [k for k in data["issues"].keys() if k.startswith("VI-")]
    if not existing:
        return "VI-001"
    nums = [int(k.split("-")[1]) for k in existing if k.split("-")[1].isdigit()]
    return f"VI-{(max(nums) + 1):03d}" if nums else "VI-001"


def _open_issues_for_req(data: dict, req_id: str) -> list:
    """Returns the list of open issues for the given req_id."""
    return [
        v for v in data["issues"].values()
        if v.get("req_id") == req_id and v.get("status") == "open"
    ]


def _open_blockers_for_req(data: dict, req_id: str) -> list:
    """Returns the list of open blocker issues for req_id."""
    return [
        v for v in data["issues"].values()
        if v.get("req_id") == req_id
        and v.get("status") == "open"
        and v.get("severity") == "blocker"
    ]


# ---------------------------------------------------------------------------
# Utilities — specs directory (7.1)
# ---------------------------------------------------------------------------

def _specs_dir(project_id: str) -> str:
    # issue #1: specs live in data/<project>/specs/, with a fallback to legacy layouts.
    # Single source of truth — common.specs_dir.
    return specs_dir(project_id)


# Single implementation in common.py — 5.5's approval package reads the same spec
# files to show the stakeholder the text they sign; two parsers would drift.
_spec_section_body = spec_section_body


def _read_spec_fields(req: dict, project_id: str) -> Optional[dict]:
    """Reads the 7.1 spec .md for a requirement and extracts the fields the quality checks need
    (audit finding 7.2-A). The 5.1 repo stores only metadata; the real text (AC, statement,
    exception scenarios) lives in the 7.1 spec files. Returns a dict of extracted fields, or None
    if no spec file is found/readable (the caller then degrades gracefully rather than false-flag).

    File location: the node's source_artifact (7.1 registers the spec path there), else a glob
    <id>_*.md in the specs directory.
    """
    # Resolution lives in common.find_spec_file — shared with the 5.5 package.
    path = find_spec_file(req, project_id)
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except IOError:
        return None

    req_type = req.get("type", "")
    fields: dict = {}
    if req_type == "user_story":
        ac_body = _spec_section_body(content, "Acceptance Criteria")
        ac_texts = [
            re.sub(r"^\d+\.\s*", "", ln.strip())
            for ln in ac_body.split("\n")
            if re.match(r"^\s*\d+\.\s+", ln)
        ]
        fields["ac_count"] = len(ac_texts)
        fields["ac_texts"] = ac_texts
    elif req_type in ("functional", "non_functional", "business_rule"):
        stmt = _spec_section_body(content, "Statement")
        # drop the italic hint line ("> _..._") the 7.1 template prepends
        stmt = "\n".join(l for l in stmt.split("\n") if not l.strip().startswith(">")).strip()
        if stmt:
            fields["description"] = stmt
    elif req_type == "use_case":
        # present the exception-scenarios section (empty string if the section is absent)
        fields["exc_scenarios"] = _spec_section_body(content, "Exception scenarios")
    return fields


def _enrich_req_from_spec(req: dict, project_id: str) -> dict:
    """Returns a copy of the req augmented with fields parsed from its 7.1 spec file, so the
    quality checks run on the real requirement text rather than on repo metadata alone."""
    enriched = dict(req)
    fields = _read_spec_fields(req, project_id)
    if fields:
        enriched.update(fields)
    return enriched


# ---------------------------------------------------------------------------
# Rule-based checks (ADR-027)
# ---------------------------------------------------------------------------

def _check_atomicity(text: str) -> dict:
    """Checks atomicity based on signal words."""
    text_lower = text.lower()
    found = [s.strip() for s in ATOMICITY_SIGNALS if s in text_lower]
    if len(found) >= 2:
        return {"passed": False, "signals_found": found,
                "note": f"Found {len(found)} conjunction signals — the requirement may be compound"}
    elif len(found) == 1:
        return {"passed": True, "signals_found": found,
                "note": "One signal — check the context: it may be a list of values, not two requirements"}
    return {"passed": True, "signals_found": [], "note": None}


def _check_ambiguity(text: str) -> dict:
    """Checks unambiguousness based on signal words."""
    text_lower = text.lower()
    found = [s for s in AMBIGUITY_SIGNALS if s in text_lower]
    if found:
        return {"passed": False, "signals_found": found,
                "note": f"Found words without measurable criteria: {', '.join(repr(s) for s in found[:5])}"}
    return {"passed": True, "signals_found": [], "note": None}


def _check_testability_us(title: str, ac_count: int, ac_texts: list) -> dict:
    """User Story testability: checks AC."""
    if ac_count < 2:
        return {"passed": False, "issue": "missing_ac", "ac_count": ac_count,
                "note": f"User Story contains {ac_count} AC, at least 2 are required"}
    # Check the AC for ambiguity
    ac_full = " ".join(ac_texts).lower()
    ambiguous_in_ac = [s for s in AMBIGUITY_SIGNALS if s in ac_full]
    if ambiguous_in_ac:
        return {"passed": True, "issue": None, "ac_count": ac_count,
                "note": f"AC contain signal words: {', '.join(repr(s) for s in ambiguous_in_ac[:3])} — clarification recommended"}
    return {"passed": True, "issue": None, "ac_count": ac_count, "note": None}


def _check_testability_fr(description: str, req_type: str) -> dict:
    """FR/NFR/BR testability: checks for the presence of a measurable criterion."""
    desc_lower = description.lower()

    if req_type == "business_rule":
        # BR: the presence of a condition is enough
        has_condition = any(re.search(p, desc_lower) for p in CONDITION_PATTERNS)
        if has_condition:
            return {"passed": True, "issue": None, "note": None}
        return {"passed": True, "issue": None,
                "note": "BR without an explicit condition — check whether the context in which the rule applies is clear"}

    # functional / non_functional
    has_measure = any(re.search(p, desc_lower) for p in MEASURABILITY_PATTERNS)
    if has_measure:
        return {"passed": True, "issue": None, "note": None}
    return {
        "passed": False, "issue": "not_testable",
        "note": "No measurable criterion — add a numeric value, a metric, or a clear binary condition"
    }


def _check_testability_uc(exc_scenarios: str) -> dict:
    """UC testability: presence of exception scenarios."""
    if exc_scenarios and exc_scenarios.strip():
        return {"passed": True, "issue": None, "note": None}
    return {"passed": False, "issue": "not_testable",
            "note": "Use Case without exception scenarios — boundary-condition testing is impossible"}


def _check_prioritized(priority: str) -> dict:
    """Checks for the presence of a priority."""
    if priority and priority.strip() and priority.lower() not in ("", "none", "null", "-"):
        return {"passed": True, "priority": priority, "note": None}
    return {"passed": False, "priority": None,
            "note": "Priority not set — fill it in via the 5.3 tools (Prioritize Requirements)"}


def _check_conciseness(title: str, description: str, req_type: str) -> dict:
    """Checks conciseness: length and signals of redundancy."""
    warnings = []

    # Title length
    if req_type == "user_story" and len(title) > 100:
        warnings.append(f"Story title is {len(title)} characters long — recommended ≤ 100")
    elif len(title) > 150:
        warnings.append(f"Title is {len(title)} characters long — recommended ≤ 150")

    # Description length
    if description and len(description) > 800:
        warnings.append(f"Description is {len(description)} characters long — recommended ≤ 800, "
                        f"the requirement may be compound")

    # Implementation signals in the requirement description
    desc_lower = description.lower() if description else ""
    impl_signals = [s for s in CONCISENESS_SIGNALS if s in desc_lower]
    if impl_signals:
        warnings.append(f"Possible implementation description: {', '.join(repr(s) for s in impl_signals[:2])}")

    if warnings:
        return {"passed": True, "warning": " | ".join(warnings)}
    return {"passed": True, "warning": None}


def _check_group_b(req: dict, repo: dict) -> dict:
    """Group B: consistency and completeness via the 5.1 repository data."""
    req_id = req["id"]
    result = {}

    # Completeness: presence of source_artifact
    has_source = bool(req.get("source_artifact", "").strip())
    # Presence of owner
    has_owner = bool(req.get("owner", "").strip())
    # Presence of at least one link in the graph
    has_links = any(
        lnk.get("from") == req_id or lnk.get("to") == req_id
        for lnk in repo.get("links", [])
    )
    result["complete"] = {
        "has_source": has_source,
        "has_links": has_links,
        "has_owner": has_owner,
        "warnings": [],
    }
    if not has_source:
        result["complete"]["warnings"].append("No traceability to the 4.3 artifact (source_artifact is empty)")
    if not has_links:
        result["complete"]["warnings"].append("No links in repository 5.1 — isolated requirement")
    if not has_owner:
        result["complete"]["warnings"].append("No owner specified — who is responsible for this requirement?")

    # Consistency: look at the req status
    req_status = req.get("status", "draft")
    conflict_statuses = {"conflict", "rejected", "superseded"}
    if req_status in conflict_statuses:
        result["consistent"] = {
            "status": "needs_review",
            "note": f"Requirement in status '{req_status}' — check for conflicts"
        }
    else:
        result["consistent"] = {"status": "ok", "note": None}

    return result


def _check_single_req(req: dict, repo: dict) -> dict:
    """Runs all checks for a single requirement. Returns a structured result."""
    req_id = req["id"]
    req_type = req.get("type", "")
    title = req.get("title", "")
    # description may be in the req itself or we need to read the file — MCP stores only metadata.
    # By the 5.1 architecture, desc is not stored in the repo (only id, type, title, status, priority...).
    # Text checks are done on the title (which we have) + on the fields available in the repo.
    description = req.get("description", "")  # may be empty
    priority = req.get("priority", "")

    checks = {}
    blockers = []
    majors = []
    minors = []

    # --- Atomicity ---
    text_for_atomicity = title + " " + description
    checks["atomic"] = _check_atomicity(text_for_atomicity)
    if not checks["atomic"]["passed"] and len(checks["atomic"]["signals_found"]) >= 2:
        majors.append("not_atomic")

    # --- Unambiguousness ---
    text_for_ambiguity = title + " " + description
    checks["unambiguous"] = _check_ambiguity(text_for_ambiguity)
    if not checks["unambiguous"]["passed"]:
        majors.append("ambiguity")

    # --- Testability (depends on the type) ---
    # The real text (AC / statement / exception scenarios) lives in the 7.1 spec files; the caller
    # enriches req from there before this runs (audit finding 7.2-A). "Known" = the relevant field
    # is present (from the spec file or already on the node). If unknown, DEGRADE gracefully with a
    # "verify manually" note instead of a false blocker/major.
    if req_type == "user_story":
        if "ac_count" in req:
            ac_count = req.get("ac_count", 0)
            ac_texts = req.get("ac_texts", [])
            checks["testable"] = _check_testability_us(title, ac_count, ac_texts)
            if not checks["testable"]["passed"]:
                blockers.append(checks["testable"].get("issue", "missing_ac"))
        else:
            checks["testable"] = {"passed": True, "issue": None,
                                  "note": "Acceptance Criteria not found in the 7.1 spec file — verify manually"}

    elif req_type in ("functional", "non_functional", "business_rule"):
        desc = (description or "").strip()
        if desc:
            checks["testable"] = _check_testability_fr(desc, req_type)
            if not checks["testable"]["passed"]:
                majors.append(checks["testable"].get("issue", "not_testable"))
        else:
            checks["testable"] = {"passed": True, "issue": None,
                                  "note": "Requirement statement not found in the 7.1 spec file — verify testability manually"}

    elif req_type == "use_case":
        if "exc_scenarios" in req:
            exc = req.get("exc_scenarios", "")
            checks["testable"] = _check_testability_uc(exc)
            if not checks["testable"]["passed"]:
                majors.append(checks["testable"].get("issue", "not_testable"))
        else:
            checks["testable"] = {"passed": True, "issue": None,
                                  "note": "Use Case scenarios not found in the 7.1 spec file — verify manually"}

    else:
        # business_process, data_dictionary, erd — basic check by title
        checks["testable"] = {"passed": True, "issue": None,
                               "note": f"Type '{req_type}' — testability is checked manually against the checklist"}

    # --- Prioritization ---
    checks["prioritized"] = _check_prioritized(priority)
    if not checks["prioritized"]["passed"]:
        minors.append("not_prioritized")

    # --- Conciseness ---
    checks["concise"] = _check_conciseness(title, description, req_type)
    if checks["concise"].get("warning"):
        minors.append("conciseness_warning")

    # --- Group B ---
    group_b = _check_group_b(req, repo)
    for w in group_b["complete"]["warnings"]:
        minors.append(f"completeness: {w[:30]}")

    # --- Result ---
    if blockers:
        overall = "issues_found"
    elif majors:
        overall = "issues_found"
    elif minors:
        overall = "warnings_only"
    else:
        overall = "passed"

    return {
        "req_id": req_id,
        "req_type": req_type,
        "title": title,
        "current_status": req.get("status", "draft"),
        "checks": checks,
        "group_b": group_b,
        "group_c_note": "Feasibility and Understandability — check manually against references/checklist_templates.md",
        "overall": overall,
        "blockers": blockers,
        "majors": majors,
        "minors": minors,
    }


# ---------------------------------------------------------------------------
# 7.2.1 — check_req_quality
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def check_req_quality(
    project_id: str,
    req_ids: str = "",
    req_type: str = "",
) -> str:
    """
    BABOK 7.2 — Checks requirements against the 9 BABOK quality characteristics.
    Group A (rule-based): atomicity, unambiguousness, testability, prioritization, conciseness.
    Group B (repository): consistency, completeness.
    Group C: a reminder to go through the checklists manually.

    ADR-027: MCP does the rule-based checks, Claude Code interprets and writes recommendations.

    Args:
        project_id: Project identifier.
        req_ids:    JSON list of IDs to check: '["US-001", "FR-001"]'.
                    If empty — checks all reqs with status draft.
        req_type:   Filter by type: user_story | functional | non_functional |
                    business_rule | use_case | business_process | data_dictionary | erd.
                    If empty — all types.

    Returns:
        Structured check results for interpretation by Claude Code.
    """
    logger.info(f"check_req_quality: project_id='{project_id}', req_ids='{req_ids}', req_type='{req_type}'")

    repo = _load_repo(project_id)
    all_reqs = repo.get("requirements", [])

    if not all_reqs:
        return (
            f"⚠️ Repository 5.1 for project `{project_id}` is empty or not found.\n\n"
            f"Make sure requirements were created via the 7.1 tools and the repository exists at:\n"
            f"`governance_plans/{project_id.lower().replace(' ', '_')}_traceability_repo.json`"
        )

    # Filter by ID
    if req_ids.strip():
        try:
            ids_to_check = json.loads(req_ids)
            if not isinstance(ids_to_check, list):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            return f"❌ Error parsing req_ids: expected a JSON list, e.g.: '[\"US-001\", \"FR-001\"]'"
        reqs_to_check = [r for r in all_reqs if r["id"] in ids_to_check]
        not_found = [i for i in ids_to_check if i not in {r["id"] for r in all_reqs}]
    else:
        # Take all draft reqs (not verified, not rejected).
        #
        # Selecting by status alone swept in every node another chapter registers:
        # 6.1's needs, 6.2's objectives, 6.3's risks and 5.4's change requests all
        # carry statuses this set does not mention, so the quality checklist was
        # applied to them — telling the analyst a business need lacks an owner and an
        # objective lacks a priority. Select by ROLE first, then by status.
        skip_statuses = {"verified", "approved", "deprecated", "superseded", "retired", "rejected"}
        reqs_to_check = [
            r for r in all_reqs
            if r.get("type", "") not in NON_REQUIREMENT_NODE_TYPES
            and r.get("status", "draft") not in skip_statuses
        ]
        not_found = []

    # Filter by type
    if req_type.strip():
        reqs_to_check = [r for r in reqs_to_check if r.get("type", "") == req_type]

    if not reqs_to_check:
        msg = f"ℹ️ No requirements to check in project `{project_id}`"
        if req_type:
            msg += f" (type: {req_type})"
        msg += ".\n\nPerhaps all requirements already have the status `verified`."
        return msg

    # Run the checks — enrich each req from its 7.1 spec file first (audit finding 7.2-A), so
    # quality is judged on the real requirement text, not on repo metadata alone.
    enriched_reqs = [_enrich_req_from_spec(r, project_id) for r in reqs_to_check]
    results = [_check_single_req(r, repo) for r in enriched_reqs]

    # Aggregation
    passed_count = sum(1 for r in results if r["overall"] == "passed")
    warnings_count = sum(1 for r in results if r["overall"] == "warnings_only")
    issues_count = sum(1 for r in results if r["overall"] == "issues_found")

    all_blockers = [(r["req_id"], b) for r in results for b in r["blockers"]]
    all_majors = [(r["req_id"], m) for r in results for m in r["majors"]]

    # Build the report
    lines = [
        f"<!-- BABOK 7.2 — Quality Check | Project: {project_id} | {date.today()} -->",
        "",
        f"# 🔍 Requirements verification — {project_id}",
        "",
        f"**Date:** {date.today()}  ",
        f"**Checked:** {len(results)} requirements  ",
        f"**Type filter:** {req_type or 'all types'}",
        "",
        "## Summary",
        "",
        "| Status | Count |",
        "|--------|-----------|",
        f"| ✅ Passed all checks | {passed_count} |",
        f"| ⚠️ Warnings only | {warnings_count} |",
        f"| ❌ Issues found | {issues_count} |",
        "",
    ]

    if not_found:
        lines += [
            f"⚠️ Not found in the repository: {', '.join(f'`{i}`' for i in not_found)}",
            "",
        ]

    if all_blockers:
        lines += [
            "## 🚨 Blockers (must be fixed before 5.5)",
            "",
        ]
        for req_id, issue in all_blockers:
            lines.append(f"- `{req_id}`: **{issue}**")
        lines.append("")

    if all_majors:
        lines += [
            "## ⚠️ Major issues (major)",
            "",
        ]
        for req_id, issue in all_majors:
            lines.append(f"- `{req_id}`: {issue}")
        lines.append("")

    # Details for each req
    lines += [
        "---",
        "",
        "## Results per requirement",
        "",
        "*(Claude Code: for each req with issues_found — explain the problem and suggest a fix)*",
        "",
    ]

    for r in results:
        icon = {"passed": "✅", "warnings_only": "⚠️", "issues_found": "❌"}.get(r["overall"], "❓")
        lines.append(f"### {icon} `{r['req_id']}` — {r['title']}")
        lines.append(f"**Type:** {r['req_type']} | **Status:** {r['current_status']}")
        lines.append("")

        # Group A
        checks = r["checks"]

        atomic = checks.get("atomic", {})
        mark = "✅" if atomic.get("passed") else "❌"
        note = f" _{atomic.get('note', '')}_" if atomic.get("note") else ""
        lines.append(f"- {mark} **Atomicity**{note}")

        unamb = checks.get("unambiguous", {})
        mark = "✅" if unamb.get("passed") else "❌"
        signals = unamb.get("signals_found", [])
        note = f" — signals: {', '.join(repr(s) for s in signals[:3])}" if signals else ""
        lines.append(f"- {mark} **Unambiguousness**{note}")

        testable = checks.get("testable", {})
        mark = "✅" if testable.get("passed") else "❌"
        note = f" — {testable.get('note', '')}" if testable.get("note") else ""
        lines.append(f"- {mark} **Testability**{note}")

        prioritized = checks.get("prioritized", {})
        mark = "✅" if prioritized.get("passed") else "⚠️"
        prio = prioritized.get("priority")
        note = f" ({prio})" if prio else " — not set"
        lines.append(f"- {mark} **Prioritization**{note}")

        concise = checks.get("concise", {})
        warning = concise.get("warning")
        mark = "⚠️" if warning else "✅"
        note = f" — {warning}" if warning else ""
        lines.append(f"- {mark} **Conciseness**{note}")

        # Group B
        group_b = r.get("group_b", {})
        complete = group_b.get("complete", {})
        consistent = group_b.get("consistent", {})

        cons_ok = consistent.get("status") == "ok"
        mark = "✅" if cons_ok else "⚠️"
        cons_note = f" — {consistent.get('note', '')}" if not cons_ok else ""
        lines.append(f"- {mark} **Consistency**{cons_note}")

        comp_warnings = complete.get("warnings", [])
        mark = "✅" if not comp_warnings else "⚠️"
        comp_note = f" — {comp_warnings[0]}" if comp_warnings else ""
        lines.append(f"- {mark} **Completeness**{comp_note}")

        lines.append(f"- 📋 **Feasibility + Understandability** — check the checklist manually")

        if r["blockers"] or r["majors"]:
            lines.append("")
            lines.append(f"> **Recommendation for Claude Code:** "
                         f"Blockers: {r['blockers'] or 'none'} | "
                         f"Majors: {r['majors'] or 'none'}")
            lines.append("> Explain to the BA exactly what is violated and suggest a concrete rewording.")

        lines.append("")

    # Next steps
    lines += [
        "---",
        "",
        "## Next steps",
        "",
    ]

    if issues_count > 0 or len(all_blockers) > 0:
        lines.append("1. For each problem above: `open_verification_issue` with a description.")
        lines.append("2. Fix the requirements (via the 7.1 tools or manually in the specs/ files).")
        lines.append("3. Close the issues: `resolve_verification_issue`.")
    lines.append(f"4. Check model consistency: `check_model_consistency(project_id='{project_id}')`.")
    lines.append(f"5. Go through the Group C checklists from `references/checklist_templates.md`.")
    lines.append(f"6. Verify the ready reqs: `mark_req_verified`.")
    lines.append(f"7. Generate the report: `get_verification_report(project_id='{project_id}')`.")

    content = "\n".join(lines)
    save_artifact(content, prefix="7_2_quality_check", project_id=project_id)
    return content


# ---------------------------------------------------------------------------
# 7.2.2 — check_model_consistency (ADR-029)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def check_model_consistency(
    project_id: str,
) -> str:
    """
    BABOK 7.2 — Cross-model verification: compares the .md and .puml files from 7.1.
    ADR-029: a separate tool for checking model consistency.

    What it checks:
      - Entities in the Data Dictionary (.md) vs the ERD (.puml): name mismatch
      - Use Cases in repository 5.1 vs the UC Diagram (.puml): UC without an actor
      - Business Process participants (.md) vs actors in the UC Diagram (.puml)

    Reads files from governance_plans/{project_id}_specs/ using the 7.1 templates.

    Args:
        project_id: Project identifier.

    Returns:
        A list of inconsistencies between models for interpretation by Claude Code.
    """
    logger.info(f"check_model_consistency: project_id='{project_id}'")

    specs_dir = _specs_dir(project_id)
    if not os.path.exists(specs_dir):
        return (
            f"⚠️ Specifications directory not found: `{specs_dir}`\n\n"
            f"Make sure the artifacts were created via the 7.1 tools "
            f"(`create_data_dictionary`, `create_erd`, `create_use_case`, `create_business_process`)."
        )

    all_files = glob.glob(os.path.join(specs_dir, "*.md")) + glob.glob(os.path.join(specs_dir, "*.puml"))
    if not all_files:
        return (
            f"⚠️ Directory `{specs_dir}` has no .md or .puml files.\n"
            f"Create specifications via the 7.1 tools."
        )

    issues = []

    # --- Parse DD: extract entity names ---
    dd_entities = set()
    dd_files = glob.glob(os.path.join(specs_dir, "dd_*.md"))
    for filepath in dd_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            # 7.1 template: "## Entity: EntityName"
            for match in re.finditer(r"##\s+Entity:\s+(.+)", content):
                name = match.group(1).strip()
                if name:
                    dd_entities.add(name)
        except IOError:
            pass

    # --- Parse ERD .puml: extract entity names ---
    erd_entities = set()
    erd_files = glob.glob(os.path.join(specs_dir, "erd_*.puml"))
    for filepath in erd_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            # PlantUML: entity "Name" as Alias { ... }
            for match in re.finditer(r'entity\s+"([^"]+)"', content):
                name = match.group(1).strip()
                if name:
                    erd_entities.add(name)
        except IOError:
            pass

    # DD vs ERD: entities in DD but not in ERD and vice versa
    if dd_entities and erd_entities:
        in_dd_not_erd = dd_entities - erd_entities
        in_erd_not_dd = erd_entities - dd_entities
        for name in sorted(in_dd_not_erd):
            issues.append({
                "type": "model_inconsistency",
                "models": ["Data Dictionary", "ERD"],
                "description": f"Entity '{name}' is in the Data Dictionary but missing from the ERD",
                "severity": "major",
            })
        for name in sorted(in_erd_not_dd):
            issues.append({
                "type": "model_inconsistency",
                "models": ["ERD", "Data Dictionary"],
                "description": f"Entity '{name}' is in the ERD but missing from the Data Dictionary",
                "severity": "major",
            })

    # --- Parse UC Diagram .puml: actors and UC aliases ---
    uc_diagram_actors = set()
    uc_diagram_usecases = set()
    uc_puml_files = glob.glob(os.path.join(specs_dir, "uc_diagram_*.puml"))
    for filepath in uc_puml_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            # actor "Name" as Alias
            for match in re.finditer(r'actor\s+"([^"]+)"', content):
                uc_diagram_actors.add(match.group(1).strip())
            # usecase "Name" as Alias
            for match in re.finditer(r'usecase\s+"([^"]+)"', content):
                uc_diagram_usecases.add(match.group(1).strip())
        except IOError:
            pass

    # --- Parse UC .md files: primary actor ---
    uc_spec_actors = {}  # uc_title -> primary_actor
    uc_md_files = glob.glob(os.path.join(specs_dir, "uc_*.md"))
    for filepath in uc_md_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            # From the table: | Actor (primary) | ActorName |
            actor_match = re.search(r'\|\s*Actor \(primary\)\s*\|\s*(.+?)\s*\|', content)
            # File heading: # UC-001 — Title
            title_match = re.search(r'#\s+UC-\d+\s+—\s+(.+)', content)
            if actor_match and title_match:
                uc_title = title_match.group(1).strip()
                actor = actor_match.group(1).strip()
                if actor and actor != "Value":
                    uc_spec_actors[uc_title] = actor
        except IOError:
            pass

    # UC actor from .md is present but not in the UC Diagram
    for uc_title, actor in uc_spec_actors.items():
        if uc_diagram_actors and actor not in uc_diagram_actors:
            issues.append({
                "type": "model_inconsistency",
                "models": ["Use Case (.md)", "UC Diagram (.puml)"],
                "description": f"Actor '{actor}' is mentioned in the UC specification '{uc_title}', "
                               f"but missing from the UC Diagram",
                "severity": "minor",
            })

    # UC from specs but not on the diagram (by title)
    if uc_diagram_usecases:
        for uc_title in uc_spec_actors:
            if uc_title not in uc_diagram_usecases:
                issues.append({
                    "type": "model_inconsistency",
                    "models": ["Use Case (.md)", "UC Diagram (.puml)"],
                    "description": f"Use Case '{uc_title}' is in the specification but not on the UC Diagram",
                    "severity": "minor",
                })

    # --- Parse BP .md: participants ---
    bp_participants = set()
    bp_md_files = glob.glob(os.path.join(specs_dir, "bp_*.md"))
    for filepath in bp_md_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            # | Participants | Role1, Role2 |
            p_match = re.search(r'\|\s*Participants\s*\|\s*(.+?)\s*\|', content)
            if p_match:
                participants_str = p_match.group(1).strip()
                for p in participants_str.split(","):
                    p = p.strip()
                    if p and p != "Value":
                        bp_participants.add(p)
        except IOError:
            pass

    # BP participants are present but not as actors in the UC Diagram
    if bp_participants and uc_diagram_actors:
        for participant in sorted(bp_participants):
            if participant not in uc_diagram_actors:
                issues.append({
                    "type": "model_inconsistency",
                    "models": ["Business Process (.md)", "UC Diagram (.puml)"],
                    "description": f"Participant '{participant}' is mentioned in the Business Process "
                                   f"but not defined as an actor in the UC Diagram",
                    "severity": "minor",
                })

    # --- Build the report ---
    lines = [
        f"<!-- BABOK 7.2 — Model Consistency | Project: {project_id} | {date.today()} -->",
        "",
        f"# 🔗 Model consistency — {project_id}",
        "",
        f"**Date:** {date.today()}  ",
        f"**Specs directory:** `{specs_dir}`  ",
        f"**Files checked:** {len(all_files)}",
        "",
        "## What was checked",
        "",
        f"- Data Dictionary files: {len(dd_files)} (entities: {len(dd_entities)})",
        f"- ERD files: {len(erd_files)} (entities: {len(erd_entities)})",
        f"- UC Diagram files: {len(uc_puml_files)} (actors: {len(uc_diagram_actors)})",
        f"- Use Case .md files: {len(uc_md_files)}",
        f"- Business Process .md files: {len(bp_md_files)}",
        "",
    ]

    if not issues:
        lines += [
            "## ✅ No inconsistencies found",
            "",
            "All models are consistent with each other.",
            "",
            "**Note:** Parsing works against the standard 7.1 templates. "
            "Non-standard file formatting may not be detected automatically — "
            "a visual review is recommended.",
        ]
    else:
        major_issues = [i for i in issues if i["severity"] == "major"]
        minor_issues = [i for i in issues if i["severity"] == "minor"]

        lines += [
            f"## Result: {len(issues)} inconsistencies",
            "",
            f"- 🔴 Major: {len(major_issues)}",
            f"- 🟡 Minor: {len(minor_issues)}",
            "",
        ]

        if major_issues:
            lines += ["## 🔴 Major inconsistencies", ""]
            for issue in major_issues:
                models = " ↔ ".join(issue["models"])
                lines.append(f"- **{models}:** {issue['description']}")
            lines.append("")

        if minor_issues:
            lines += ["## 🟡 Minor inconsistencies", ""]
            for issue in minor_issues:
                models = " ↔ ".join(issue["models"])
                lines.append(f"- {models}: {issue['description']}")
            lines.append("")

        lines += [
            "---",
            "",
            "## Next steps",
            "",
            "1. For each inconsistency: `open_verification_issue` with `issue_type='model_inconsistency'`.",
            "2. Fix the relevant file in `governance_plans/{project}_specs/` (or recreate it via 7.1).",
            "3. After fixing: `resolve_verification_issue`.",
        ]

    content = "\n".join(lines)
    save_artifact(content, prefix="7_2_model_consistency", project_id=project_id)
    return content


# ---------------------------------------------------------------------------
# 7.2.3 — open_verification_issue (ADR-028)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def open_verification_issue(
    project_id: str,
    req_id: str,
    issue_type: str,
    description: str,
    severity: str,
    assigned_to: str = "",
) -> str:
    """
    BABOK 7.2 — Records a problem found while verifying a requirement.
    ADR-028: issues are stored in {project}_verification_issues.json.

    Args:
        project_id:  Project identifier.
        req_id:      ID of the requirement with the problem (US-001, FR-003, etc.).
        issue_type:  Problem type:
                     ambiguity         — vague statement
                     not_testable      — no testing criterion
                     not_atomic        — compound requirement
                     missing_ac        — no Acceptance Criteria (for US)
                     model_inconsistency — mismatch between models
                     other             — other
        description: Exactly what is violated and why it is a problem.
        severity:    blocker | major | minor
        assigned_to: Whom to assign it to (a BA or stakeholder name). Empty by default.

    Returns:
        Confirmation with the ID of the created issue.
    """
    logger.info(f"open_verification_issue: project_id='{project_id}', req_id='{req_id}'")

    valid_issue_types = {"ambiguity", "not_testable", "not_atomic", "missing_ac",
                         "model_inconsistency", "other"}
    if issue_type not in valid_issue_types:
        return (
            f"❌ Invalid issue_type: '{issue_type}'.\n"
            f"Allowed values: {' | '.join(sorted(valid_issue_types))}"
        )

    valid_severities = {"blocker", "major", "minor"}
    if severity not in valid_severities:
        return (
            f"❌ Invalid severity: '{severity}'.\n"
            f"Allowed values: blocker | major | minor"
        )

    if not description.strip():
        return "❌ description cannot be empty — describe exactly what is violated."

    # Check that the req exists in the repository
    repo = _load_repo(project_id)
    req = _find_req(repo, req_id)
    req_title = req["title"] if req else "(requirement not found in 5.1)"

    data = _load_issues(project_id)
    issue_id = _next_issue_id(data)

    severity_labels = {"blocker": "🚨 blocker", "major": "⚠️ major", "minor": "💬 minor"}

    data["issues"][issue_id] = {
        "issue_id": issue_id,
        "req_id": req_id,
        "req_title": req_title,
        "issue_type": issue_type,
        "description": description,
        "severity": severity,
        "assigned_to": assigned_to or "",
        "status": "open",
        "opened_date": str(date.today()),
        "resolved_date": None,
        "resolution_note": "",
    }

    # Update statistics
    data["stats"]["open"] = sum(1 for v in data["issues"].values() if v["status"] == "open")
    data["stats"]["total"] = len(data["issues"])
    data["stats"]["closed"] = data["stats"]["total"] - data["stats"]["open"]

    _save_issues(data)

    lines = [
        f"✅ Issue recorded: **{issue_id}**",
        "",
        f"| Field | Value |",
        f"|------|----------|",
        f"| Issue ID | `{issue_id}` |",
        f"| Requirement | `{req_id}` — {req_title} |",
        f"| Problem type | {issue_type} |",
        f"| Severity | {severity_labels[severity]} |",
        f"| Assigned to | {assigned_to or '—'} |",
        f"| Status | open |",
        f"| Opened date | {date.today()} |",
        "",
        f"**Description:** {description}",
        "",
        "---",
        "",
        "**Next step:** fix the requirement and call:",
        f"`resolve_verification_issue(project_id='{project_id}', issue_id='{issue_id}', resolution_note='...')`",
    ]

    if severity == "blocker":
        lines.insert(1, "")
        lines.insert(2, f"> 🚨 **Blocker:** `{req_id}` cannot be verified until this issue is closed.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.2.4 — resolve_verification_issue
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def resolve_verification_issue(
    project_id: str,
    issue_id: str,
    resolution_note: str,
) -> str:
    """
    BABOK 7.2 — Closes a verification issue after the BA fixes it.

    Args:
        project_id:      Project identifier.
        issue_id:        Issue ID: VI-001, VI-002, etc.
        resolution_note: Exactly what was fixed (for the audit trail).

    Returns:
        Confirmation of closure + the status of remaining blockers for this req.
    """
    logger.info(f"resolve_verification_issue: project_id='{project_id}', issue_id='{issue_id}'")

    if not resolution_note.strip():
        return "❌ resolution_note cannot be empty — describe exactly what was fixed."

    data = _load_issues(project_id)

    if issue_id not in data["issues"]:
        return (
            f"❌ Issue `{issue_id}` not found in project `{project_id}`.\n"
            f"Open issues: {', '.join(k for k, v in data['issues'].items() if v['status'] == 'open') or 'none'}"
        )

    issue = data["issues"][issue_id]

    if issue["status"] == "closed":
        return (
            f"ℹ️ Issue `{issue_id}` is already closed ({issue.get('resolved_date', '?')}).\n"
            f"Resolution: {issue.get('resolution_note', '—')}"
        )

    req_id = issue["req_id"]
    issue["status"] = "closed"
    issue["resolved_date"] = str(date.today())
    issue["resolution_note"] = resolution_note

    # Update statistics
    data["stats"]["open"] = sum(1 for v in data["issues"].values() if v["status"] == "open")
    data["stats"]["closed"] = sum(1 for v in data["issues"].values() if v["status"] == "closed")

    _save_issues(data)

    # Check the remaining blockers for this req
    remaining_blockers = _open_blockers_for_req(data, req_id)
    remaining_all = _open_issues_for_req(data, req_id)

    lines = [
        f"✅ Issue **{issue_id}** closed.",
        "",
        f"| Field | Value |",
        f"|------|----------|",
        f"| Requirement | `{req_id}` |",
        f"| Type | {issue['issue_type']} |",
        f"| Severity | {issue['severity']} |",
        f"| Closed date | {date.today()} |",
        "",
        f"**Resolution:** {resolution_note}",
        "",
        "---",
        "",
    ]

    if remaining_blockers:
        lines.append(f"⚠️ `{req_id}` still has open **blockers**: "
                     f"{', '.join(b['issue_id'] for b in remaining_blockers)}")
        lines.append(f"Verification of `{req_id}` is blocked until they are closed.")
    elif remaining_all:
        lines.append(f"ℹ️ `{req_id}` still has open non-blocker issues: "
                     f"{', '.join(i['issue_id'] for i in remaining_all)}")
        lines.append(f"✅ No blockers — you can call `mark_req_verified` for `{req_id}`.")
    else:
        lines.append(f"✅ All issues for `{req_id}` are closed.")
        lines.append(f"Next step: `mark_req_verified(project_id='{project_id}', req_ids='[\"{req_id}\"]')`")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.2.5 — mark_req_verified
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def mark_req_verified(
    project_id: str,
    req_ids: str,
    force: bool = False,
) -> str:
    """
    BABOK 7.2 — Sets the 'verified' status in repository 5.1.
    Precondition: checks for open blocker issues.

    Args:
        project_id: Project identifier.
        req_ids:    JSON list of IDs: '["US-001", "FR-001", "US-002"]'.
        force:      Verify even when a req has open blocker issues. The decision
                    belongs to the BA, so an override exists — but it is deliberate
                    and recorded: the repository history keeps the overridden blocker
                    ids, and the verification report lists every forced req.
                    Without it, the only way past a blocker would be to close an
                    issue that is not actually resolved, corrupting the audit trail.

    Returns:
        A result per req: successfully verified / a warning about blockers.
    """
    logger.info(f"mark_req_verified: project_id='{project_id}', req_ids='{req_ids}'")

    try:
        ids_list = json.loads(req_ids)
        if not isinstance(ids_list, list) or not ids_list:
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        return "❌ req_ids must be a non-empty JSON list: '[\"US-001\", \"FR-001\"]'"

    repo = _load_repo(project_id)
    data = _load_issues(project_id)

    results = []
    verified_count = 0
    blocked_count = 0
    forced_count = 0
    not_found_count = 0

    for req_id in ids_list:
        req = _find_req(repo, req_id)
        if not req:
            results.append(f"❌ `{req_id}` — not found in repository 5.1")
            not_found_count += 1
            continue

        # Check blockers
        blockers = _open_blockers_for_req(data, req_id)
        blocker_ids = [b["issue_id"] for b in blockers]
        if blockers and not force:
            results.append(
                f"⚠️ `{req_id}` — BLOCKED. Open blockers: {', '.join(blocker_ids)}. "
                f"Close them via `resolve_verification_issue`, or use force=true "
                f"to verify anyway (the override is recorded)."
            )
            blocked_count += 1
            continue

        # Change the status — unless it already records a STRONGER outcome.
        #
        # `status` is one field shared by four chapters, so whoever writes last wins.
        # Overwriting an approval 5.5 had recorded printed "verified (was: approved)"
        # and destroyed the fact: verification survives such a clobber because it has a
        # durable `req_verified` history record, but approval has no symmetric
        # predicate, so it was simply gone and the matrix filtered by `approved` lost
        # the requirement. Since verification is read from history and not from this
        # field, there is nothing to gain by downgrading a stronger status.
        #
        # `pending_approval` is deliberately NOT in this set: 5.5 stamps it on every
        # requirement the moment a package opens, so it is process state, not an outcome.
        # `validated` (7.3) is a LATER pipeline stage than `verified`, so a re-run of 7.2
        # must not silently downgrade the visible status of an already-validated
        # requirement — the same reasoning as the approval statuses above (the durable
        # fact lives in history; there is nothing to gain by clobbering a stronger status).
        old_status = req.get("status", "draft")
        status_preserved = old_status in APPROVAL_OUTCOME_STATUSES or old_status == "validated"
        if not status_preserved:
            req["status"] = "verified"

        # History — the durable record. A forced verification and a preserved approval
        # both stay visible in the audit trail.
        entry = {
            "action": "req_verified",
            "req_id": req_id,
            "old_status": old_status,
            "new_status": old_status if status_preserved else "verified",
            "source": "7.2_verify",
            "date": str(date.today()),
        }
        if status_preserved:
            entry["status_preserved"] = True
        if blockers:
            entry["forced"] = True
            entry["overridden_blockers"] = blocker_ids
        repo["history"].append(entry)

        if blockers:
            results.append(
                f"⚠️ `{req_id}` — verified WITH FORCE despite open blockers: "
                f"{', '.join(blocker_ids)} (was: {old_status})"
            )
            forced_count += 1
        elif status_preserved:
            results.append(
                f"✅ `{req_id}` — verified; status left as `{old_status}` "
                f"(a 5.5 decision is not overwritten by a 7.2 re-check)"
            )
        else:
            results.append(f"✅ `{req_id}` — verified (was: {old_status})")
        verified_count += 1

    if verified_count > 0:
        _save_repo(repo)

    lines = [
        f"# Verification result — {project_id}",
        "",
        f"**Date:** {date.today()}  ",
        f"**Processed:** {len(ids_list)} requirements  ",
        f"**Verified:** ✅ {verified_count}  ",
        f"**Of which forced (open blockers overridden):** ⚠️ {forced_count}  ",
        f"**Blocked:** ⚠️ {blocked_count}  ",
        f"**Not found:** ❌ {not_found_count}",
        "",
        "## Details",
        "",
    ]
    lines.extend(results)

    if blocked_count > 0:
        lines += [
            "",
            "---",
            "",
            f"⚠️ {blocked_count} requirements are blocked by open blockers.",
            "After fixing and closing the issues — call `mark_req_verified` again.",
            "If you judge a blocker acceptable, `force=true` verifies anyway and records "
            "the override (the blocker itself stays open — do NOT close an unresolved issue).",
        ]

    if forced_count > 0:
        lines += [
            "",
            "---",
            "",
            f"⚠️ {forced_count} requirements were verified WITH FORCE over open blockers.",
            "The override is recorded in the repository history and listed in "
            "`get_verification_report`. The blocker issues remain open.",
        ]

    if verified_count > 0:
        lines += [
            "",
            "---",
            "",
            f"✅ The `verified` status is set in repository 5.1.",
            f"Next step: `get_verification_report(project_id='{project_id}')` for the summary report.",
        ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.2.6 — get_verification_report
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def get_verification_report(
    project_id: str,
) -> str:
    """
    BABOK 7.2 — Generates a summary report on project verification.

    Contains:
      - % verified out of all reqs
      - Top problems by characteristic type
      - List of reqs with open blocker issues
      - Open issues with details
      - Verdict: whether it is ready for Approve (5.5) and Validate (7.3)

    Saves Markdown via save_artifact for handoff to 5.5 and 7.3.

    Args:
        project_id: Project identifier.

    Returns:
        Verification Report in Markdown.
    """
    logger.info(f"get_verification_report: project_id='{project_id}'")

    repo = _load_repo(project_id)
    all_reqs = repo.get("requirements", [])
    data = _load_issues(project_id)

    # Statistics by requirements
    skip_statuses = {"deprecated", "superseded", "retired"}
    # Same rule as check_req_quality: only requirements are verified. Counting other
    # chapters' nodes in the denominator drove the verified percentage down and made
    # the report answer "not ready for 5.5" because of objectives and risks, which are
    # not verifiable artifacts. It also reported 6.4's scope node — stored with
    # `status: approved` in the sense "scope settled" — as approved in the 5.5 sense.
    active_reqs = [
        r for r in all_reqs
        if r.get("type", "") not in NON_REQUIREMENT_NODE_TYPES
        and r.get("status") not in skip_statuses
    ]
    total = len(active_reqs)

    if total == 0:
        return (
            f"⚠️ No active requirements in the repository for project `{project_id}`.\n"
            f"Create requirements via the 7.1 tools before verification."
        )

    verified = [r for r in active_reqs if r.get("status") == "verified"]
    draft = [r for r in active_reqs if r.get("status") == "draft"]

    # Approval, like verification above, is a FACT and not a snapshot of the current
    # status. Reading `status` here meant the count fell as soon as 7.3 validated an
    # approved requirement, and it counted anything a producer happened to label
    # `approved` in its own sense — 6.4's scope node used to do exactly that, so this
    # line credited 5.5 with an approval on a project where 5.5 had never run. The
    # durable answer is recomputed from the stakeholder decisions 5.5 stored.
    approved = [r for r in active_reqs
                if approval_outcome(project_id, r.get("id")) in
                (APPROVAL_OUTCOME_APPROVED, APPROVAL_OUTCOME_CONDITIONAL)]
    # `unknown` means there are no approval records at all — a legacy project, or one
    # that has not reached 5.5. Reported separately rather than folded into "not
    # approved", so the report never asserts more than the records support.
    approval_unknown = all(
        approval_outcome(project_id, r.get("id")) == APPROVAL_OUTCOME_UNKNOWN
        for r in active_reqs)

    # "Has passed verification" is a FACT, not a snapshot of the current status.
    # `status` is a single field shared across chapters (draft → verified →
    # pending_approval → approved), so 5.5 overwrites `verified` on approval and the
    # evidence disappears: the percentage used to FALL as approvals succeeded, and the
    # report then declared "Not ready for Approve (5.5)" precisely because 5.5 had
    # worked. The durable record is the `req_verified` entry 7.2 writes to history.
    # NB: approval is deliberately NOT treated as proof of verification — 5.5 never
    # checks for it, so a req can reach `approved` without ever passing 7.2.
    # The union with the current status covers legacy repos that predate the history.
    # The shared predicate in common.py IS this formula — 7.2 is where it was extracted
    # from. Keeping a second inline copy is how "two gates for one decision" starts, the
    # class that already bit 5.5 (dashboard vs. baseline gate).
    verified_reqs = [r for r in active_reqs if has_passed_verification(repo, r.get("id"))]

    verified_pct = round(len(verified_reqs) / total * 100, 1) if total > 0 else 0.0

    # Statistics by issues
    all_issues = list(data["issues"].values())
    open_issues = [i for i in all_issues if i["status"] == "open"]
    open_blockers = [i for i in open_issues if i["severity"] == "blocker"]
    open_majors = [i for i in open_issues if i["severity"] == "major"]

    # Top problems by type
    from collections import Counter
    issue_type_counts = Counter(i["issue_type"] for i in all_issues)
    open_type_counts = Counter(i["issue_type"] for i in open_issues)

    # reqs with open blockers
    blocked_req_ids = set(i["req_id"] for i in open_blockers)

    # Readiness for 5.5
    ready_for_approve = len(open_blockers) == 0 and verified_pct >= 80
    ready_label = "✅ Ready for Approve (5.5)" if ready_for_approve else "❌ Not ready for Approve (5.5)"

    lines = [
        f"<!-- BABOK 7.2 — Verification Report | Project: {project_id} | {date.today()} -->",
        "",
        f"# 📋 Requirements verification report",
        "",
        f"**Project:** {project_id}  ",
        f"**Report date:** {date.today()}  ",
        f"**Readiness:** {ready_label}",
        "",
        "---",
        "",
        "## Requirements summary",
        "",
        "| Metric | Value |",
        "|------------|----------|",
        f"| Total active reqs | {total} |",
        f"| ✅ Passed verification | {len(verified_reqs)} ({verified_pct}%) |",
        f"| &nbsp;&nbsp;↳ currently in `verified` status | {len(verified)} |",
        f"| ✅ Approved in 5.5 | {'— (5.5 has not run)' if approval_unknown else len(approved)} |",
        f"| 📝 Draft (not verified) | {len(draft)} |",
        "",
    ]

    # Progress bar (text)
    filled = int(verified_pct / 10)
    bar = "█" * filled + "░" * (10 - filled)
    lines.append(f"**Verification progress:** `[{bar}]` {verified_pct}%")
    lines.append("")

    # Issues summary
    lines += [
        "## Verification issues summary",
        "",
        "| Metric | Value |",
        "|------------|----------|",
        f"| Total issues | {len(all_issues)} |",
        f"| 🚨 Open blockers | {len(open_blockers)} |",
        f"| ⚠️ Open majors | {len(open_majors)} |",
        f"| ✅ Closed issues | {data['stats'].get('closed', 0)} |",
        "",
    ]

    # Top problems
    if issue_type_counts:
        lines += [
            "## Top problems by type",
            "",
            "| Problem type | Total | Open |",
            "|-------------|-------|----------|",
        ]
        for issue_type, count in issue_type_counts.most_common():
            open_count = open_type_counts.get(issue_type, 0)
            lines.append(f"| {issue_type} | {count} | {open_count} |")
        lines.append("")

    # Reqs blocked for 5.5
    if blocked_req_ids:
        lines += [
            "## 🚨 Requirements with open blockers",
            "",
            "> These requirements cannot be approved (5.5) until the blockers are closed.",
            "",
        ]
        for req_id in sorted(blocked_req_ids):
            req = _find_req(repo, req_id)
            title = req["title"] if req else "—"
            blockers_for_req = [i for i in open_blockers if i["req_id"] == req_id]
            blocker_ids = ", ".join(b["issue_id"] for b in blockers_for_req)
            lines.append(f"- `{req_id}` — {title} | Blockers: {blocker_ids}")
        lines.append("")

    # Forced verifications — the BA's override must be visible to whoever approves in 5.5,
    # otherwise "recorded in history" is the same as hidden.
    forced_entries = {}
    for h in repo.get("history", []):
        if h.get("action") == "req_verified" and h.get("forced"):
            forced_entries[h["req_id"]] = h
    if forced_entries:
        lines += [
            "## ⚠️ Verified with force (blockers overridden by the BA)",
            "",
            "> The BA judged these blockers acceptable and verified anyway. "
            "The blocker issues are still open — review before approving in 5.5.",
            "",
        ]
        for req_id in sorted(forced_entries):
            req = _find_req(repo, req_id)
            title = req["title"] if req else "—"
            overridden = ", ".join(forced_entries[req_id].get("overridden_blockers", []))
            lines.append(f"- `{req_id}` — {title} | Overridden: {overridden} "
                         f"| Date: {forced_entries[req_id].get('date', '—')}")
        lines.append("")

    # Open issues
    if open_issues:
        lines += [
            "## Open issues",
            "",
            "| Issue ID | Req | Type | Severity | Assigned | Date |",
            "|----------|-----|-----|----------|----------|------|",
        ]
        for issue in sorted(open_issues, key=lambda x: (x["severity"] != "blocker", x["opened_date"])):
            severity_icon = {"blocker": "🚨", "major": "⚠️", "minor": "💬"}.get(issue["severity"], "")
            lines.append(
                f"| `{issue['issue_id']}` | `{issue['req_id']}` | {issue['issue_type']} | "
                f"{severity_icon} {issue['severity']} | {issue.get('assigned_to') or '—'} | {issue['opened_date']} |"
            )
        lines.append("")

    # Reqs that have passed verification (including those 5.5 has since approved)
    if verified_reqs:
        lines += [
            "## ✅ Requirements that passed verification",
            "",
        ]
        by_type: dict = {}
        for r in verified_reqs:
            t = r.get("type", "other")
            by_type.setdefault(t, []).append(r["id"])
        for req_type, ids in sorted(by_type.items()):
            lines.append(f"**{req_type}:** {', '.join(f'`{i}`' for i in sorted(ids))}")
        lines.append("")

    # Verdict and next steps
    lines += [
        "---",
        "",
        "## Verdict and next steps",
        "",
    ]

    if ready_for_approve:
        lines += [
            "### ✅ Ready for handoff to the next tasks",
            "",
            f"- **5.5 Approve Requirements:** {len(verified)} reqs currently in status `verified` are ready for baseline "
            f"({len(verified_reqs)} have passed verification in total).",
            f"- **7.3 Validate Requirements:** the verified reqs are ready for validation with the business.",
            "",
            "**Hand this report to 5.5:** use `prepare_approval_package` with a reference to this report.",
        ]
    else:
        reasons = []
        if open_blockers:
            reasons.append(f"🚨 {len(open_blockers)} open blockers are not closed")
        if verified_pct < 80:
            reasons.append(f"📊 Only {verified_pct}% of reqs verified (recommended ≥ 80%)")
        if draft:
            reasons.append(f"📝 {len(draft)} requirements are not yet verified")

        lines += [
            "### ❌ Not ready for 5.5 Approve",
            "",
        ]
        for r in reasons:
            lines.append(f"- {r}")
        lines += [
            "",
            "**Actions:**",
            "1. Close all blocker issues via `resolve_verification_issue`.",
            f"2. Verify the remaining reqs via `check_req_quality` -> `mark_req_verified`.",
            f"3. Re-run `get_verification_report` for the updated status.",
        ]

    content = "\n".join(lines)
    save_artifact(content, prefix="7_2_verification_report", project_id=project_id)
    return content


if __name__ == "__main__":
    mcp.run()
