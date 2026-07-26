# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
import functools
import glob
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

# 6.4's solution-scope node (ADR-082, revised). It used to be typed `solution`, which
# is ALSO the BABOK requirement CLASS in the 5.1 vocabulary
# (business | stakeholder | solution | transition) — the class init_traceability_repo
# and the Confluence import assign to ordinary FR/NFR. One literal, two populations:
# the scope node could not be excluded without dropping real requirements, so it was
# counted as a requirement everywhere — asked for a test case by 5.1, for an owner by
# 5.2, for a MoSCoW vote by 5.3. Renaming the SCOPE node (the smaller, single-writer
# population) separates them; `solution` again means only the requirement class.
# Graphs written before the rename are migrated by migrate_solution_scope.py.
SOLUTION_SCOPE_NODE_TYPE = "solution_scope"

# Other chapters' analysis artifacts. They live in the graph for traceability but
# are not requirements: they are never specified, prioritised, verified or approved.
ANALYSIS_NODE_TYPES = {"risk", "change_request", SOLUTION_SCOPE_NODE_TYPE}

TEST_NODE_TYPES = {"test"}

# Everything that must not be counted, scored, verified or approved as a requirement.
NON_REQUIREMENT_NODE_TYPES = BUSINESS_NODE_TYPES | ANALYSIS_NODE_TYPES | TEST_NODE_TYPES

# Relations that justify a node's existence upward — "something explains why I am here".
# `threatens` (6.3) and `modifies` (5.4) belong here: a risk that threatens an
# objective and a change request that modifies a requirement are both anchored, and
# reporting them as orphans sends the analyst hunting for a justification they have.
SOURCE_RELATIONS = {"derives", "satisfies", "threatens", "modifies"}

# Every relation any chapter writes. 5.1's own tool accepted only the four it defined,
# so an edge written by 6.3 (`threatens`) or 5.4 (`modifies`) could not be removed
# through the tool at all — the analyst's only route to deleting a wrong edge was
# hand-editing the JSON.
ALL_RELATIONS = {"derives", "depends", "satisfies", "verifies", "threatens", "modifies"}

# The date on a LINK, written under three different spellings: `added` (5.1, 6.2, 6.3,
# 6.4), `added_date` (5.4) and `created` (7.1). Readers knowing only one rendered a
# dash for every edge the other producers wrote — in the traceability matrix, which
# goes into the approval package a stakeholder signs. New writers should use `added`;
# the readers accept all three so stored graphs keep working.
LINK_DATE_KEYS = ("added", "added_date", "created")


def link_date(link: dict, default: str = "—") -> str:
    """The date a link was created, whichever spelling its producer used."""
    for key in LINK_DATE_KEYS:
        value = link.get(key)
        if value:
            return str(value)
    return default


# `priority` carries TWO scales: 5.3 writes MoSCoW, 7.1 writes High/Medium/Low, and a
# project that specifies without ever running a prioritisation session only ever has
# the second. A consumer that knows one scale silently does nothing on the other —
# 5.5's "you are rejecting a critically important requirement" warning tested for
# `Must` alone, so it never fired on exactly those projects.
MOSCOW_PRIORITIES = {"Must", "Should", "Could", "Won't"}
LEVEL_PRIORITIES = {"High", "Medium", "Low"}
VALID_PRIORITIES = MOSCOW_PRIORITIES | LEVEL_PRIORITIES

# "Critically important" in either scale.
MUST_PRIORITIES = {"Must", "High"}


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


def has_been_validated(repo: dict, req_id: str) -> bool:
    """True if the requirement has passed 7.3 validation.

    The mirror of `has_passed_verification`. `status` is a single field shared across
    chapters, so 5.5 (approved), 5.4 resolve_cr (under_change) and even a re-run of
    7.2 mark_req_verified overwrite `validated` and the evidence disappears from the
    node — after which get_validation_report counted fewer validated requirements and
    reported "Not ready for 7.5" about work that was in fact validated. The lasting
    proof is the `req_validated` entry mark_req_validated appends to repo["history"].
    The union with the current status covers repositories written before the history
    record existed. A forced validation counts: force=true is a recorded BA decision.
    """
    for entry in repo.get("history", []):
        if entry.get("action") == "req_validated" and entry.get("req_id") == req_id:
            return True
    for req in repo.get("requirements", []):
        if req.get("id") == req_id and req.get("status") == "validated":
            return True
    return False


# ---------------------------------------------------------------------------
# 7.1 spec files — shared by every consumer that needs the requirement's TEXT
# ---------------------------------------------------------------------------
#
# The 5.1 graph node carries only metadata (id/type/title/priority/...); the real
# statement and acceptance criteria live in the 7.1 spec .md. Two consumers need
# that text — 7.2's quality checks (which read repo metadata alone and false-
# flagged every requirement, finding 7.2-A) and 5.5's approval package (which
# showed a stakeholder bare titles to sign). One resolver and one section parser
# here, so the two readers cannot drift apart.

def find_spec_file(req: dict, project_id: str):
    """Path of the requirement's 7.1 spec .md, or None.

    The node's `source_artifact` is preferred (7.1 registers the spec path
    there); otherwise a glob `<id>_*.md` in the project's specs directory.
    """
    sa = req.get("source_artifact", "") or ""
    if sa.lower().endswith(".md") and os.path.exists(sa):
        return sa
    safe_id = req.get("id", "").lower().replace("-", "_")
    if safe_id:
        matches = glob.glob(os.path.join(specs_dir(project_id), f"{safe_id}_*.md"))
        if matches:
            return sorted(matches)[0]
    return None


def spec_section_body(content: str, header: str) -> str:
    """Text of a '## <header>' section up to the next '##' or '---' or EOF.
    Header match is a case-insensitive prefix, so "Main scenario" finds
    "## Main scenario (Happy Path)"."""
    lines = content.split("\n")
    body, in_section = [], False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") and stripped[3:].strip().lower().startswith(header.lower()):
            in_section = True
            continue
        if in_section:
            if stripped.startswith("## ") or stripped == "---":
                break
            body.append(line)
    return "\n".join(body).strip()


# ---------------------------------------------------------------------------
# Stored-artifact corruption — shared by every chapter that loads a repository
# ---------------------------------------------------------------------------
#
# Every `_load_repo` in chapters 5 and 7 called `json.load` bare, so a damaged file
# turned every downstream tool into a PROTOCOL error: the analyst got a stack trace
# where every neighbouring tool returns a readable ❌ line, with no idea which file was
# at fault or whether anything had been written. The correct behaviour already existed
# one module away in `load_stakeholder_registry`.
#
# The loaders raise, and the tool boundary converts. Raising keeps the alternative —
# "return an empty repository" — off the table: that is silent data loss, and it makes
# a tool state confidently that a project has no requirements when in fact its file
# could not be read. Degradation may say LESS; it may not conclude more (CH3-D).


class CorruptArtifactError(Exception):
    """A stored artifact exists but cannot be parsed. `str(exc)` is BA-facing."""


def read_json_artifact(path: str, what: str = "artifact") -> dict:
    """Reads a stored JSON artifact, raising CorruptArtifactError with the path.

    The path is part of the message on purpose: "something went wrong" is not
    actionable, whereas a filename tells the analyst exactly what to inspect or
    restore.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError) as exc:
        # UnicodeDecodeError is a ValueError, not an OSError — a distinction that
        # already let a non-UTF-8 file escape one guard in this codebase (A4).
        raise CorruptArtifactError(
            f"❌ The {what} could not be read: `{path}`\n"
            f"   {type(exc).__name__}: {exc}\n"
            f"   The file exists but is not valid JSON. Restore it from version "
            f"control or a backup — no data has been changed by this call."
        ) from exc


def guard_artifact_errors(fn):
    """Converts CorruptArtifactError into the ❌ string an MCP tool must return.

    Applied at the tool boundary rather than at each of the ~32 load sites, so a new
    tool cannot forget it. Only this one exception is caught — everything else
    propagates unchanged, because swallowing unknown errors is how a tool starts
    reporting success it did not achieve.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except CorruptArtifactError as exc:
            logger.warning(f"{fn.__name__}: {exc}")
            return str(exc)
    return wrapper


# ---------------------------------------------------------------------------
# Approval evidence (5.5) — shared by 5.1, 5.2 and 7.2
# ---------------------------------------------------------------------------
#
# The mirror of has_passed_verification above, and it exists for the same reason:
# `status` is ONE field written by four chapters (7.1 draft -> 7.2 verified ->
# 5.5 pending_approval/approved -> 7.3 validated), so the last writer wins and any
# consumer asking "was this approved?" by reading the status gets an answer with a
# shelf life. 7.2's report credited 5.5 with approvals; 5.2 scored reuse on
# "proven in practice" — both lose the fact the moment another chapter moves on.
#
# Where the two predicates DIFFER is the source, and that is not an inconsistency.
# 7.2 has no artifact of its own, so verification had to be recorded into the
# repository history. 5.5 has written `{project}_approval_history.json` all along:
# every package, every stakeholder, every per-requirement decision with the RACI it
# was cast under. The evidence was never missing — it was simply never read. So the
# outcome is RECOMPUTED from the decisions, which means no migration and a correct
# answer for every project that has ever run 5.5.
#
# Not node["history"]: 5.5 appends there only when the status actually CHANGES, so a
# requirement approved while already in `approved` records nothing. Lossy by
# construction, and therefore no basis for a predicate.

APPROVAL_HISTORY_FILENAME = "approval_history.json"

APPROVAL_OUTCOME_APPROVED = "approved"
APPROVAL_OUTCOME_CONDITIONAL = "conditional_approved"
APPROVAL_OUTCOME_REJECTED = "rejected"
APPROVAL_OUTCOME_PENDING = "pending_approval"
# The records exist and simply do not cover this requirement — it was never put in
# front of anyone.
APPROVAL_OUTCOME_NOT_SUBMITTED = "not_submitted"
# There are no records at all. Distinct from NOT_SUBMITTED on purpose (the B2-bis
# precedent): telling a BA "this was not approved" about a project whose history
# predates the file is an assertion the records cannot support.
APPROVAL_OUTCOME_UNKNOWN = "unknown"


def compute_approval_outcome(package: dict, req_id: str) -> str:
    """Folds one package's stakeholder decisions into a per-requirement outcome.

    THE single implementation of the rule — 5.5 calls this one too. Two copies of a
    decision rule is exactly how 5.5's dashboard verdict and baseline gate drifted
    apart, letting a package the dashboard called "Not ready" baseline cleanly.

    RACI semantics: only Accountable and Responsible carry a requirement. An
    abstention is a first-class decision meaning "I decline to take a position" — it
    does not block, but it cannot carry the requirement either, or a package where
    everyone abstained reaches "approved" with nobody having approved anything.
    """
    decisions = []
    for sh_data in package.get("stakeholder_decisions", {}).values():
        raci = sh_data.get("raci", "consulted")
        for rd in sh_data.get("req_decisions", []):
            if rd.get("req_id") == req_id:
                decisions.append({
                    "raci": raci,
                    "decision": rd.get("decision"),
                    "condition_closed": rd.get("condition_closed", False),
                })

    if not decisions:
        return APPROVAL_OUTCOME_PENDING

    for d in decisions:
        if d["decision"] == "rejected" and d["raci"] in ("accountable", "responsible"):
            return APPROVAL_OUTCOME_REJECTED

    for d in decisions:
        if (d["decision"] == "conditional" and not d["condition_closed"]
                and d["raci"] in ("accountable", "responsible")):
            return APPROVAL_OUTCOME_CONDITIONAL

    ar = [d for d in decisions if d["raci"] in ("accountable", "responsible")]

    def _affirmative(d):
        return (d["decision"] == "approved"
                or (d["decision"] == "conditional" and d["condition_closed"]))

    def _acceptable(d):
        return _affirmative(d) or d["decision"] == "abstained"

    if ar and all(_acceptable(d) for d in ar):
        if any(_affirmative(d) for d in ar):
            return APPROVAL_OUTCOME_APPROVED
        return APPROVAL_OUTCOME_PENDING

    return APPROVAL_OUTCOME_PENDING


def load_approval_history(project_id: str) -> Optional[dict]:
    """Reads 5.5's approval history. Returns None when there is nothing to read.

    None means UNKNOWN, not empty: a missing or damaged file must not be reported as
    "nothing was approved". Same graceful-degradation contract as
    load_stakeholder_registry — a damaged file must never turn a report into a
    protocol error.
    """
    safe = normalize_project_id(project_id)
    path = data_path(project_id, f"{safe}_{APPROVAL_HISTORY_FILENAME}")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            history = json.load(f)
    except (OSError, ValueError) as exc:
        logger.warning(f"load_approval_history: unreadable {path}: {exc}")
        return None
    if not isinstance(history, dict) or not isinstance(history.get("packages"), dict):
        logger.warning(f"load_approval_history: unexpected shape in {path}")
        return None
    return history


def approval_outcome(project_id: str, req_id: str) -> str:
    """The 5.5 outcome for one requirement, recomputed from the durable decisions.

    Where a requirement appears in several packages the LATEST one governs: a
    requirement re-submitted after a rejection is decided by the newer round, not by
    whichever package happens to sit first in the file. Packages carry
    `created_date`; ties fall back to insertion order, which is chronological
    because packages are only ever appended.
    """
    history = load_approval_history(project_id)
    if history is None:
        return APPROVAL_OUTCOME_UNKNOWN

    candidates = [pkg for pkg in history["packages"].values()
                  if isinstance(pkg, dict) and req_id in (pkg.get("req_ids") or [])]
    if not candidates:
        return APPROVAL_OUTCOME_NOT_SUBMITTED

    latest = max(enumerate(candidates),
                 key=lambda pair: (str(pair[1].get("created_date", "")), pair[0]))[1]
    return compute_approval_outcome(latest, req_id)


def has_been_approved(project_id: str, req_id: str) -> bool:
    """True only for a full approval.

    A conditional approval is deliberately NOT folded in: an open condition is not a
    signature. Callers that want to count it must ask for the outcome and say so.
    """
    return approval_outcome(project_id, req_id) == APPROVAL_OUTCOME_APPROVED


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


# ---------------------------------------------------------------------------
# 3.4 Information Management plan — shared reader (B3-3)
# ---------------------------------------------------------------------------
#
# Chapter 3 writes {pid}_ba_plan.json and sits in phase.py BASE_SERVER; chapters 4
# and 5 load in other phases and must NOT import the chapter-3 MCP module to read
# it. Same reason the living stakeholder registry lives here.
#
# BABOK 3.4.1 (printed p. 43) names the consumers of the Information Management
# Approach itself: 4.4, 5.1, 5.2, 7.4. Wired here: 4.4, and 5.2 (twice).

BA_PLAN_SUFFIX = "ba_plan.json"

# Element .2 — how much breadth/depth an audience gets (printed p. 44).
ABSTRACTION_LEVELS = ("Summary", "Standard", "Detailed")

# Element .6 — attributes the PLATFORM can actually store on a requirement node.
# Verified against update_requirement (5.2) and the node creators (5.1 / 7.1).
# BABOK also lists author, risks and urgency (p. 45-46); this model has no field
# for them, so planning them is refused rather than accepted and never checked.
PLANNABLE_ATTRIBUTES = (
    "status", "version", "source", "priority", "owner",
    "stability", "complexity", "reuse_candidate", "reuse_scope", "last_reviewed",
)

# Mirrors the table in skills/requirements_maintain/SKILL.md ("Always" / "Standard+"
# / "Full") — that prose existed with nothing selecting it. `last_reviewed` is in no
# preset on purpose: the platform stamps it on every update, so it would flag every
# requirement that has simply not been edited yet.
ATTRIBUTE_PRESETS = {
    "Minimum":  ("status", "version", "source"),
    "Standard": ("status", "version", "source", "priority", "owner",
                 "stability", "reuse_candidate"),
    "Full":     ("status", "version", "source", "priority", "owner",
                 "stability", "reuse_candidate", "reuse_scope", "complexity"),
}

# Element .4 — categories BABOK calls long-term reuse candidates (printed p. 44).
# The list is open ("may also be reused when describing common features"), so an
# unlisted category is warned about, never refused.
REUSE_CATEGORIES = (
    "regulatory", "contractual", "quality standards", "service level agreements",
    "business rules", "business processes", "products",
)

# ORDER IS LOAD-BEARING: narrow -> wide. 5.2 calls .index() on this tuple and compares
# the positions, so reordering it would silently invert the reuse ranking. Pinned by
# tests/test_ch5_52_info_mgmt_plan.py::test_the_scope_bonus_still_shows_up_in_the_score.
REUSE_SCOPES = ("initiative", "program", "division", "enterprise")


def ba_plan_path(project_id: str) -> str:
    """Path of the chapter-3 BA plan. Mirrors planning_mcp._plan_path exactly.

    A consumer that guesses this wrong reads nothing and says nothing — the failure
    mode that hit 6.3, 6.4, 7.1 and 7.6, each time on a different axis (file name,
    container folder, field name). A test pins it against the producer.
    """
    safe = normalize_project_id(project_id)
    return data_path(project_id, f"{safe}_{BA_PLAN_SUFFIX}")


def load_ba_plan(project_id: str):
    """Reads the BA plan for a consumer in another chapter.

    Returns `(plan, note)`:
      - no file            -> (None, "")        the project simply never planned
      - unreadable file    -> (None, warning)   the caller must SHOW the warning
      - readable JSON dict -> (plan, "")

    Two values rather than one because "never planned" and "planned but the file is
    damaged" are different answers to the BA, and a consumer that conflates them
    would silently drop a plan the BA did write. NOTE: the tuple is always truthy —
    unpack it, never test it directly.
    """
    path = ba_plan_path(project_id)
    if not os.path.exists(path):
        return None, ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        loaded = None
    if not isinstance(loaded, dict):
        return None, (f"⚠️ The 3.4 information management plan exists but could not be "
                      f"read (`{path}`) — continuing without it.")
    return loaded, ""


def info_management_section(plan) -> dict:
    """The `information_management` section, or {} for any shape that is not a dict."""
    if not isinstance(plan, dict):
        return {}
    section = plan.get("information_management")
    return section if isinstance(section, dict) else {}


def planned_abstraction_level(plan, *audiences):
    """Element .2 — the planned detail level for an audience, or None.

    Accepts several identifiers and returns the first hit. 4.4 knows the archetype
    ("Business Sponsor"); the stakeholder map knows the job title ("Head of Retail
    Lending"). Matching on one of the two alone could not succeed by construction —
    the same defect that made check_communication_schedule claim "no communication
    on record" about someone briefed days earlier.
    """
    rows = info_management_section(plan).get("abstraction_levels")
    if not isinstance(rows, list):
        return None
    for audience in audiences:
        key = reg_norm(audience)
        if not key:
            continue
        for row in rows:
            if not isinstance(row, dict) or reg_norm(row.get("audience")) != key:
                continue
            # A row is returned only when its level is one this platform can act on.
            # The consumer indexes `row["level"]` and looks it up in a guidance table,
            # so a missing, non-string or unknown level was an uncaught exception (a
            # protocol error, not a ❌ line) or — for a null level — a delivered
            # package claiming a detail level of "None" with an empty checklist. The
            # guard lives here so it covers every consumer, present and future.
            if row.get("level") in ABSTRACTION_LEVELS:
                return {"audience": str(row.get("audience") or ""),
                        "level": row["level"],
                        "note": str(row.get("note") or "")}
    return None


def planned_reuse(plan):
    """Element .4 — {target_scope, repository, categories}, or None if nothing planned."""
    reuse = info_management_section(plan).get("reuse")
    if not isinstance(reuse, dict):
        return None
    # `isinstance(..., list)` before the comprehension, not `or []`: a bare string
    # where a list was meant is an ordinary LLM mistake, and iterating it yields one
    # entry per CHARACTER — invented data the reuse report would then present as
    # planned categories. A non-iterable value raised outright.
    raw_categories = reuse.get("categories")
    categories = ([c for c in raw_categories if isinstance(c, str)]
                  if isinstance(raw_categories, list) else [])
    scope = reuse.get("target_scope")
    result = {
        "target_scope": scope if scope in REUSE_SCOPES else "",
        "repository": str(reuse.get("repository") or ""),
        "categories": categories,
    }
    return result if any(result.values()) else None


def planned_attribute_set(plan):
    """Element .6 — (attributes, source_label), or None if nothing planned.

    The single place where a preset is expanded. The expansion is deliberately NOT
    stored in the plan file: two copies of one rule is exactly how the 5.5 dashboard
    and the baseline gate drifted apart, and a stored expansion would also go stale
    the moment the preset table changes.
    """
    attrs_plan = info_management_section(plan).get("attributes")
    if not isinstance(attrs_plan, dict):
        return None
    # A non-string preset is not just wrong, it is fatal: ATTRIBUTE_PRESETS.get() with
    # a list raises "unhashable type". Same guard reasoning as `categories` above.
    raw_preset = attrs_plan.get("preset")
    preset = raw_preset if isinstance(raw_preset, str) else ""
    raw_additional = attrs_plan.get("additional")
    additional = ([a for a in raw_additional
                   if isinstance(a, str) and a in PLANNABLE_ATTRIBUTES]
                  if isinstance(raw_additional, list) else [])
    base = ATTRIBUTE_PRESETS.get(preset, ())
    merged = tuple(dict.fromkeys(list(base) + additional))
    if not merged:
        return None
    if preset and additional:
        label = f"3.4 plan, preset {preset} + {len(additional)} added"
    elif preset:
        label = f"3.4 plan, preset {preset}"
    else:
        label = "3.4 plan, explicit list"
    return merged, label


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
