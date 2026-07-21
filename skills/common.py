# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
import json
import os
import re
import sys
import logging
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional

# Logging setup (stderr — does not interfere with the JSON-RPC protocol)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("BABOK_Toolkit")

BASE_DIR = "governance_plans"
DATA_DIR = os.path.join(BASE_DIR, "data")      # JSON: machine-readable files for MCP
REPORTS_DIR = os.path.join(BASE_DIR, "reports") # Markdown: documents for humans

# Root node types in the 5.1 traceability graph — the things a requirement traces UP to.
# 6.1 registers needs as `business_need`, 6.2 registers goals as `business_goal`, and
# `business` is the legacy/manual type. A traversal or skip-filter that knows only the
# legacy type silently ignores real 6.x goals; that single incompleteness produced audit
# findings 7.3-A, 7.4-B and 7.4-C. One definition, imported by every consumer.
#
# NOTE: the root exemption inside `check_coverage` (5.1) is deliberately the SUBSET
# ("business", "business_need") — `business_goal` must keep failing the no-source check,
# because a goal derives from a need and therefore should have a source. Do not
# substitute this constant there.
# ---------------------------------------------------------------------------
# The 5.1 graph vocabulary, grouped by the ROLE a node plays
# ---------------------------------------------------------------------------
# Nine producers write into <project>_traceability_repo.json and each new chapter
# added its own node type. A consumer that hard-codes the subset it knew about does
# not fail loudly, it misclassifies: goals get asked for owners, risks are reported
# as unjustified orphans, and requirements vanish from a signed traceability matrix.
# Group by role here, once, so a type added later is classified rather than ignored.

# Roots — the WHY. They have no upstream source by definition.
BUSINESS_NODE_TYPES = {"business", "business_goal", "business_need"}

# Other chapters' analysis artifacts. They live in the graph for traceability but
# are not requirements: they are never specified, prioritised, verified or approved.
ANALYSIS_NODE_TYPES = {"risk", "change_request"}

# NOTE — `solution` is deliberately absent from ANALYSIS_NODE_TYPES. The literal
# carries two meanings in the same field: 6.4's solution-scope node AND the BABOK
# requirement CLASS that init_traceability_repo and the Confluence import assign to
# ordinary requirements. Excluding it would drop real requirements from every count.
# Between over-counting one scope node and under-counting requirements, only the
# second is a lie about coverage. Resolving this properly means renaming 6.4's node
# type, which is an ADR change plus a migration for graphs already written.

TEST_NODE_TYPES = {"test"}

# Everything that must not be counted, scored, verified or approved as a requirement.
NON_REQUIREMENT_NODE_TYPES = BUSINESS_NODE_TYPES | ANALYSIS_NODE_TYPES | TEST_NODE_TYPES

# Relations that justify a node's existence upward — "something explains why I am here".
# `threatens` (6.3) and `modifies` (5.4) belong here: a risk that threatens an
# objective and a change request that modifies a requirement are both anchored, and
# reporting them as orphans sends the analyst hunting for a justification they have.
SOURCE_RELATIONS = {"derives", "satisfies", "threatens", "modifies"}


def _ensure_dirs():
    """Creates all required folders if they don't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Artifact layout in per-project subdirectories (issue #1)
# ---------------------------------------------------------------------------

_PID_DISALLOWED = re.compile(r"[^a-z0-9_-]+")


def normalize_project_id(project_id: str) -> str:
    """Safe project name for use as a directory name.

    Protects against path traversal: strips '/', '\\', '..', absolute paths;
    keeps only the whitelist [a-z0-9_-]. Empty result → '_unknown'.
    """
    if not project_id:
        return "_unknown"
    s = str(project_id).strip().lower()
    s = s.replace("\\", "_").replace("/", "_").replace(" ", "_")
    s = _PID_DISALLOWED.sub("_", s)
    s = re.sub(r"_+", "_", s)
    s = s.strip("._-")
    return s or "_unknown"


def data_dir_for(project_id: str) -> str:
    """governance_plans/data/<safe_pid>/ — the project's JSON-artifact directory."""
    return os.path.join(DATA_DIR, normalize_project_id(project_id))


def report_dir_for(project_id: str) -> str:
    """governance_plans/reports/<safe_pid>/ — the project's Markdown-report directory."""
    return os.path.join(REPORTS_DIR, normalize_project_id(project_id))


def _legacy_safe(project_id: str) -> str:
    """Pre-migration name normalization (issue #1) — used ONLY to locate already
    existing legacy files. Before normalize_project_id was introduced, names were
    built as project_id.lower().replace(" ", "_"), which kept dots and other characters.
    """
    return str(project_id).lower().replace(" ", "_")


def data_path(project_id: str, filename: str) -> str:
    """Single resolver for the JSON path (used for both reading and writing).

    filename already includes the {safe_pid}_ prefix (issue #1, decision point 1). Returns
    the first existing candidate, otherwise falls back to the canonical nested layout:
      1) data/<norm>/<filename>          — canonical nested;
      2) data/<filename>                 — canonical flat (legacy layout);
      3..5) same, but with the PRE-migration name (for project_id values with characters
            outside [a-z0-9_-], e.g. dots — the old _safe kept them, while
            normalize_project_id rewrites them).
    The directory is created by the writing side: os.makedirs(os.path.dirname(path), ...).
    """
    norm = normalize_project_id(project_id)
    candidates = [
        os.path.join(DATA_DIR, norm, filename),
        os.path.join(DATA_DIR, filename),
    ]
    legacy = _legacy_safe(project_id)
    if legacy != norm and filename.startswith(norm + "_"):
        legacy_name = legacy + filename[len(norm):]
        candidates += [
            os.path.join(DATA_DIR, norm, legacy_name),
            os.path.join(DATA_DIR, legacy, legacy_name),
            os.path.join(DATA_DIR, legacy_name),
        ]
    for cand in candidates:
        if os.path.exists(cand):
            return cand
    return candidates[0]  # new artifact → canonical nested layout


def specs_dir(project_id: str) -> str:
    """The 7.1 specs directory: data/<project_id>/specs/ (issue #1).

    Falls back to legacy layouts (including PRE-migration names with dots, etc.):
    flat data/<safe>_specs/ and variants using the old normalization.
    """
    norm = normalize_project_id(project_id)
    nested = os.path.join(DATA_DIR, norm, "specs")
    candidates = [nested, os.path.join(DATA_DIR, f"{norm}_specs")]
    legacy = _legacy_safe(project_id)
    if legacy != norm:
        candidates += [
            os.path.join(DATA_DIR, legacy, "specs"),
            os.path.join(DATA_DIR, f"{legacy}_specs"),
        ]
    for cand in candidates:
        if os.path.isdir(cand):
            return cand
    return nested


# ---------------------------------------------------------------------------
# Shared JSON-parameter validation
#
# MCP tools take structured input as JSON strings written by an LLM, so a wrong
# SHAPE (a list of strings where objects are expected, an object where a list is)
# is a routine failure mode. Every tool must answer with a readable "❌ ..." string:
# an AttributeError/TypeError escaping the tool surfaces as a protocol error the BA
# cannot act on. Keeping these here — rather than per module — stops sibling tools
# from validating differently (the drift already seen in the 5.5 gate).
#
# Each returns (value, error_message); error_message is "" on success.
# ---------------------------------------------------------------------------

def _json_load_field(raw: str, field: str, example: str):
    text = (raw or "").strip()
    if not text:
        return None, ""
    try:
        return json.loads(text), ""
    except json.JSONDecodeError as e:
        return None, (f"❌ Error parsing {field}: {e}\n"
                      f"Expected JSON, e.g. '{example}'.")


def parse_json_list(raw: str, field: str, required: bool = False,
                    example: str = '["item1", "item2"]') -> tuple:
    """Parses a JSON array. Elements may be of any type."""
    value, error = _json_load_field(raw, field, example)
    if error:
        return [], error
    if value is None:
        if required:
            return [], f"❌ {field} is required. Expected a JSON array, e.g. '{example}'."
        return [], ""
    if not isinstance(value, list):
        return [], (f"❌ {field} must be a JSON array, got {type(value).__name__}. "
                    f"Example: '{example}'.")
    if required and not value:
        return [], f"❌ {field} must be a non-empty JSON array."
    return value, ""


def parse_json_str_list(raw: str, field: str, required: bool = False,
                        example: str = '["Sponsor", "Product Owner"]') -> tuple:
    """Parses a JSON array of strings."""
    values, error = parse_json_list(raw, field, required=required, example=example)
    if error:
        return [], error
    bad = next((v for v in values if not isinstance(v, str)), None)
    if bad is not None:
        return [], (f"❌ {field} must contain only strings — got "
                    f"{type(bad).__name__}: {json.dumps(bad, ensure_ascii=False)[:60]}. "
                    f"Example: '{example}'.")
    return values, ""


def pick_field(record: dict, *names: str):
    """First non-empty value among several spellings of the same field.

    The JSON for these parameters is written by an LLM, so a plausible-but-wrong key
    (`metric` where the tool documents `name`, `objective` where it documents `title`)
    is an ordinary case, not an exotic one. Reading a single spelling and falling back
    to a dash rendered em-dashes into DELIVERED documents while the tool answered
    success — the analyst then believes the content was recorded.

    Pair with `unrecognized_records_error` for the case where nothing is recognised:
    accepting synonyms is only half the policy, the other half is refusing to claim
    success over records whose content was dropped. 4.2 `_parse_session_risks` settled
    this shape first.
    """
    for name in names:
        value = record.get(name)
        if value not in (None, ""):
            return value
    return ""


def unrecognized_records_error(field: str, accepted: tuple, example: str) -> str:
    """The message for "you supplied records, none of them carried the key field"."""
    spellings = " or ".join(f"`{a}`" for a in accepted)
    return (
        f"❌ `{field}`: no entry had a recognisable name. Accepted spellings are "
        f"{spellings}.\nExample: {example}"
    )


def parse_json_dict_list(raw: str, field: str, required: bool = False,
                         example: str = '[{"name": "...", "role": "..."}]') -> tuple:
    """Parses a JSON array of objects (the common shape for MCP list parameters)."""
    values, error = parse_json_list(raw, field, required=required, example=example)
    if error:
        return [], error
    bad = next((v for v in values if not isinstance(v, dict)), None)
    if bad is not None:
        return [], (f"❌ {field} must be a JSON array of objects — got "
                    f"{type(bad).__name__}: {json.dumps(bad, ensure_ascii=False)[:60]}. "
                    f"Example: '{example}'.")
    return values, ""


def parse_json_dict(raw: str, field: str, required: bool = False,
                    example: str = '{"key": "value"}') -> tuple:
    """Parses a single JSON object."""
    value, error = _json_load_field(raw, field, example)
    if error:
        return {}, error
    if value is None:
        if required:
            return {}, f"❌ {field} is required. Expected a JSON object, e.g. '{example}'."
        return {}, ""
    if not isinstance(value, dict):
        return {}, (f"❌ {field} must be a JSON object, got {type(value).__name__}. "
                    f"Example: '{example}'.")
    return value, ""


class Stakeholder(BaseModel):
    """Stakeholder model for the engagement matrix."""
    name: str = Field(..., description="Stakeholder name or role")
    influence: str = Field(..., pattern="^(Low|Medium|High)$", description="Level of influence")
    interest: str = Field(..., pattern="^(Low|Medium|High)$", description="Level of interest")
    attitude: Optional[str] = Field("Neutral", description="Attitude toward the project: Neutral / Champion / Blocker")


_FILENAME_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def safe_filename_part(part: str) -> str:
    """Makes caller-supplied text safe to embed in a FILENAME.

    Several tools build the artifact prefix out of free text — the project name or a
    session date (e.g. "Elicitation_Plan_{project_name}"). normalize_project_id already
    guards the DIRECTORY, but nothing guarded the filename: a project named "CRM/Q3"
    produced a path with a separator inside the file part, so the write landed in a
    directory that does not exist (FileNotFoundError) or outside the intended folder.
    Sanitizing here covers every current and future caller in one place.

    Case is preserved so existing artifact names are unchanged.
    """
    cleaned = _FILENAME_ILLEGAL.sub("_", str(part))
    cleaned = cleaned.replace("..", "_")
    cleaned = re.sub(r"_{2,}", "_", cleaned).strip(" .")
    return cleaned or "artifact"


# ---------------------------------------------------------------------------
# Verification evidence (7.2) — shared by 5.5 and 7.3
# ---------------------------------------------------------------------------

def has_passed_verification(repo: dict, req_id: str) -> bool:
    """True if the requirement has passed 7.2 verification.

    Reads the DURABLE record, not the snapshot. `status` is a single field shared
    across chapters (draft -> verified -> pending_approval -> approved), so both 5.5
    and 7.2 overwrite `verified` and the evidence disappears from the node. The
    lasting proof is the `req_verified` entry 7.2 appends to repo["history"].

    The union with the current status covers legacy repositories written before 7.2
    started recording history.

    A forced verification (B1) still counts: force=true is a recorded BA decision,
    not the absence of one. Use `was_verification_forced` to report it separately.
    """
    for entry in repo.get("history", []):
        if entry.get("action") == "req_verified" and entry.get("req_id") == req_id:
            return True
    for req in repo.get("requirements", []):
        if req.get("id") == req_id and req.get("status") == "verified":
            return True
    return False


def was_verification_forced(repo: dict, req_id: str) -> bool:
    """True if the requirement was verified with force=true over open blockers.

    Only the history record can tell — a legacy status-only repository has no
    override information, and reports False.
    """
    for entry in repo.get("history", []):
        if (entry.get("action") == "req_verified"
                and entry.get("req_id") == req_id
                and entry.get("forced")):
            return True
    return False


# ---------------------------------------------------------------------------
# Living stakeholder registry (ADR-003) — shared by 3.2 and 4.2
# ---------------------------------------------------------------------------
#
# Extracted from 4.2 so 3.2 can seed the same registry without either chapter
# importing the other: Chapter 3 sits in phase.py BASE_SERVER and loads in EVERY
# phase, while Chapter 4 loads only in `elicitation`.

STAKEHOLDER_REGISTRY_SUFFIX = "stakeholder_registry.json"


def reg_norm(value) -> str:
    """Normalize a name/role for identity matching: trim, lowercase, collapse spaces."""
    return " ".join(str(value or "").strip().lower().split())


def stakeholder_identity(s: dict) -> str:
    """Merge key for a stakeholder: normalized name, or normalized role if name is empty.

    Rationale: the name is the closest stable proxy for a person and survives a role
    change (a promotion updates the same record instead of duplicating it). Role-only
    keying is avoided because roles are not unique and would silently collapse distinct
    people. Entries with neither name nor role have an empty key and are skipped.
    """
    return reg_norm(s.get("name")) or reg_norm(s.get("role"))


def stakeholder_registry_path(project_id: str) -> str:
    safe = normalize_project_id(project_id)
    return data_path(project_id, f"{safe}_{STAKEHOLDER_REGISTRY_SUFFIX}")


def _registry_today() -> str:
    """The registry has always used dd.mm.yyyy — keep it stable for existing files."""
    return datetime.now().strftime("%d.%m.%Y")


def load_stakeholder_registry(project_id: str) -> dict:
    """Reads the JSON source of truth, or returns a fresh empty registry.

    A corrupt or unreadable file starts a fresh registry rather than blocking the BA.
    """
    today = _registry_today()
    registry = {"project": project_id, "created": today, "updated": today,
                "stakeholders": [], "history": []}
    path = stakeholder_registry_path(project_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict) and isinstance(loaded.get("stakeholders"), list):
                # `history` is appended to with `.setdefault("history", []).append(...)`,
                # which raises if the stored value is a dict rather than a list. 3.2
                # swallows that in its blanket guard, 4.2 does not — so normalise here,
                # where both readers pass through.
                if not isinstance(loaded.get("history"), list):
                    loaded["history"] = []
                # Drop entries that are not objects: the merge indexes into each one.
                loaded["stakeholders"] = [
                    s for s in loaded["stakeholders"] if isinstance(s, dict)
                ]
                registry = loaded
        except (json.JSONDecodeError, OSError):
            pass
    return registry


def save_stakeholder_registry(project_id: str, registry: dict) -> bool:
    """Persists the registry. Returns False on I/O error instead of raising, so a
    caller can warn and carry on rather than failing the whole tool."""
    path = stakeholder_registry_path(project_id)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(registry, f, ensure_ascii=False, indent=2)
        return True
    except OSError as e:
        logger.warning(f"Could not persist stakeholder registry JSON: {e}")
        return False


def merge_stakeholders(existing: list, incoming: list, source: str, today: str,
                       insert_defaults: Optional[dict] = None) -> dict:
    """Merges `incoming` into `existing` in place, by stakeholder identity.

    A non-empty incoming field overwrites; an empty one does NOT wipe a stored value.

    `insert_defaults` are applied ONLY when an entry is created, never on update, and
    never over a value the caller supplied explicitly. This exists because 3.2 seeds
    `coverage_status` and `found_through`: as ordinary fields, re-running 3.2 after an
    interview would reset the status from 'Elicited' back to 'Not covered' and
    overwrite the discovery chain — silently destroying work 4.2 recorded.

    Returns {"added": [names], "updated": [names], "dup_warnings": [(new, existing)]}.
    """
    index = {}
    for s in existing:
        key = stakeholder_identity(s)
        if key:
            index[key] = s

    added, updated, dup_warnings = [], [], []
    for s in incoming:
        if not isinstance(s, dict):
            continue
        key = stakeholder_identity(s)
        if not key:
            continue  # neither name nor role — nothing to identify by
        if key in index:
            # Partial update: non-empty incoming fields overwrite; empties do NOT wipe.
            target = index[key]
            for field, value in s.items():
                if value not in (None, "", [], {}):
                    target[field] = value
            target["_last_updated"] = today
            target["_update_source"] = source
            updated.append(target.get("name") or target.get("role") or key)
        else:
            # Duplicate guard: a NEW person whose role matches a DIFFERENT existing one.
            new_role = reg_norm(s.get("role"))
            if new_role:
                for ex in existing:
                    if stakeholder_identity(ex) != key and reg_norm(ex.get("role")) == new_role:
                        dup_warnings.append((s.get("name") or s.get("role"),
                                             ex.get("name") or ex.get("role")))
                        break
            entry = dict(s)
            for field, value in (insert_defaults or {}).items():
                # `if not entry.get(field)`, not setdefault: this module treats an empty
                # value as "not supplied" everywhere else (that is what makes partial
                # updates work), so an incoming `{"coverage_status": ""}` must take the
                # default rather than store a blank that no later update can dislodge.
                if not entry.get(field):
                    entry[field] = value
            entry["_first_seen"] = today
            entry["_last_updated"] = today
            entry["_update_source"] = source
            existing.append(entry)
            index[key] = entry
            added.append(entry.get("name") or entry.get("role") or key)

    return {"added": added, "updated": updated, "dup_warnings": dup_warnings}


def update_stakeholder_registry_file(project_id: str, incoming: list, source: str,
                                     insert_defaults: Optional[dict] = None) -> dict:
    """Load + merge + persist, with the history envelope. The one entry point chapters use.

    Returns the merge result plus {"registry": dict, "saved": bool}.
    """
    today = _registry_today()
    registry = load_stakeholder_registry(project_id)
    result = merge_stakeholders(registry.setdefault("stakeholders", []), incoming,
                                source=source, today=today,
                                insert_defaults=insert_defaults)
    registry["updated"] = today
    registry.setdefault("created", today)
    registry.setdefault("history", []).append(
        {"date": today, "source": source,
         "added": result["added"], "updated": result["updated"]})
    result["registry"] = registry
    result["saved"] = save_stakeholder_registry(project_id, registry)
    return result


def save_artifact(content: str, prefix: str, project_id: Optional[str] = None) -> str:
    """Saves a Markdown artifact to reports/ and returns the path.

    If project_id is provided, the artifact is written to reports/<project_id>/ (issue #1).
    Without project_id, the default behavior is preserved (flat reports/).
    """
    _ensure_dirs()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_filename_part(prefix)}_{timestamp}.md"
    if project_id:
        out_dir = report_dir_for(project_id)
        os.makedirs(out_dir, exist_ok=True)
    else:
        out_dir = REPORTS_DIR
    filepath = os.path.join(out_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"Artifact saved: {filepath}")
    return f"\n\n✅ Artifact saved: `{filepath}`"


# ---------------------------------------------------------------------------
# Shared matrices — used in planning.py and planning_mcp.py
# Single source of truth (ADR-REVIEW-5)
# ---------------------------------------------------------------------------

APPROACH_MATRIX: dict[tuple[str, str], tuple[str, list[str]]] = {
    ("Low",    "Low"):    ("Predictive (Waterfall)", ["Document Analysis", "Financial Analysis", "Business Rules Analysis"]),
    ("Low",    "Medium"): ("Predictive (Waterfall)", ["Document Analysis", "Interviews", "Prototyping"]),
    ("Low",    "High"):   ("Hybrid",                 ["Workshops", "Prototyping", "Risk Analysis"]),
    ("Medium", "Low"):    ("Hybrid",                 ["Workshops", "Prioritization", "Use Cases"]),
    ("Medium", "Medium"): ("Hybrid",                 ["Workshops", "User Stories", "Prioritization"]),
    ("Medium", "High"):   ("Adaptive (Agile)",        ["Backlog Management", "User Stories", "Retrospectives"]),
    ("High",   "Low"):    ("Adaptive (Agile)",        ["Backlog Management", "User Stories", "Kanban"]),
    ("High",   "Medium"): ("Adaptive (Agile)",        ["Backlog Management", "User Stories", "Retrospectives"]),
    ("High",   "High"):   ("Adaptive (Agile)",        ["Backlog Management", "Spike / PoC", "Retrospectives"]),
}

REGULATORY_OVERRIDE: dict[str, str] = {
    "Adaptive (Agile)": "Hybrid (Agile + compliance gates)",
    "Hybrid":           "Hybrid (with strengthened governance)",
}

QUADRANT_STRATEGIES: dict[tuple[str, str], tuple[str, str, str]] = {
    ("High", "High"):     ("Key Players",     "Manage Closely — involve in every decision",        "Weekly"),
    ("High", "Medium"):   ("Context Setters", "Keep Satisfied — inform about key milestones",       "At milestones"),
    ("High", "Low"):      ("Context Setters", "Keep Satisfied — inform about key milestones",       "At milestones"),
    ("Medium", "High"):   ("Subjects",        "Keep Informed — demos, Sprint Review",               "Bi-weekly"),
    ("Low",  "High"):     ("Subjects",        "Keep Informed — demos, Sprint Review",               "Bi-weekly"),
    ("Medium", "Medium"): ("Subjects",        "Keep Informed — regular updates",                    "Monthly"),
    ("Medium", "Low"):    ("Crowd",           "Monitor — general broadcast, low priority",          "Quarterly"),
    ("Low",  "Medium"):   ("Crowd",           "Monitor — general broadcast, low priority",          "Quarterly"),
    ("Low",  "Low"):      ("Crowd",           "Monitor — general broadcast, low priority",          "Quarterly"),
}
