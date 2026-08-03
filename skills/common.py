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

# The three terminal statuses `deprecate_requirements` (5.2) can assign. A requirement
# in one of them is ARCHIVED: kept forever for audit (nothing is ever deleted here) and
# counted by nothing. The set has been settled since 5.2 shipped and is spelled out
# locally in six modules; 7.4 was the one chapter that never asked the question at all,
# so a stakeholder whose every tie had been deprecated read as fully covered in a signed
# architecture document (branch review B-2).
#
# NOTE the deliberate distinction from NON_REQUIREMENT_NODE_TYPES above: a TYPE says
# what a node IS (a risk is not a requirement), a STATUS says what stage it is at (a
# deprecated requirement is still a requirement). The two are treated differently on
# purpose — 7.4 refuses to record a tie to a risk and accepts one to an archived
# requirement with a warning.
ARCHIVED_REQUIREMENT_STATUSES = {"deprecated", "superseded", "retired"}

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


# ---------------------------------------------------------------------------
# project_id validity — the mapping id -> folder must be INJECTIVE
# ---------------------------------------------------------------------------
#
# normalize_project_id above keeps only [a-z0-9_-]; everything else is stripped. That
# makes it many-to-one, and a many-to-one KEY is a data collision: two different
# cyrillic ids both became '_unknown' and the two projects silently mixed each other's
# artifacts (a delivered 6.1 document titled after one project listed the business
# needs of two others). The mixed case was worse — 'crm_обновление' collapsed onto the
# EXISTING project 'crm' and served its data back as if it were its own.
#
# Owner's decision (2026-08-03, E2E gate): REFUSE an id that cannot survive the
# mapping. The alternatives were rejected deliberately. Transliterating would make a
# lookup table part of the on-disk path contract — edit the table later and old
# projects stop being found. Storing a display id alongside the folder id would give
# one concept two keys, and every one of the ~114 tools would have to know which of
# the two it means.
#
# Transliteration is still used — but ONLY to build the SUGGESTION inside the refusal
# text. It never reaches a path, so no hidden state enters the artifact layout.
#
# The validator is deliberately SEPARATE from normalize_project_id: the normaliser is
# called on ids that are already valid and on the legacy-path fallbacks, so making it
# raise would change a primitive used far from this decision. Pinned by
# tests/test_project_id_validation.py::test_the_normaliser_itself_is_unchanged.


class InvalidProjectIdError(Exception):
    """A project_id that cannot be represented as a folder name. `str(exc)` is BA-facing.

    Converted into the ❌ answer a tool must return by the EXISTING tool boundary,
    `guard_artifact_errors` — the same event class as a corrupt artifact: the call
    cannot proceed, nothing has been written, and the analyst needs one sentence
    saying what to do. It is a sibling rather than a subclass of CorruptArtifactError
    so that "the artifact is damaged" and "the id is unusable" stay separable for any
    future caller that wants to treat only one of them.
    """


# What an id may be built from. The rule is deliberately about the ALPHABET and
# stateless — it never consults the disk — because the alternative (allow anything that
# already has files) re-opens the exact hole it closes: 'crm_обновление' would resolve
# onto the EXISTING project 'crm' and be waved through precisely because the collision
# target exists.
#
# The rule is ONE sentence: a project_id must be spelled exactly the way its folder will
# be, i.e. it must be a FIXED POINT of normalize_project_id. That makes id -> folder
# bijective, so a collision cannot be constructed at all — there is no second spelling
# that lands on the same folder.
#
# Owner's decision, 2026-08-03 (second round). The earlier, softer rule accepted any
# latin spelling and let the normaliser fold it, which left a residual class of
# collisions: 'demo.v2'/'demo_v2' and 'crm up'/'crm_up' shared a folder. Warning about
# them was the alternative and was rejected — a warning has to be carried through the
# hottest path in the platform (every path helper) to reach the analyst, and it still
# leaves two projects in one folder for anyone who ignores it.
#
# Refused by this rule, each for the same reason (the normaliser would rewrite them):
# 'CRM Up' (case and space), 'demo.v2' (dot), 'crm__up' (doubled separator), '_crm'
# (leading separator), 'црм_апгрейд' (nothing survives).
_PID_ACCEPTABLE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

# Cyrillic -> latin, for the HINT ONLY. 'ц' -> 'c' rather than 'ts' because the ids a
# Russian-speaking BA types are usually latin words spelled in cyrillic ('црм' = CRM).
_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "і": "i", "ї": "yi", "є": "e", "ґ": "g",
}

_PID_FALLBACK_SUGGESTION = "my_project"

# The placeholder normalize_project_id returns for input it cannot represent is itself
# a well-formed id, so it PASSED the alphabet check — and a caller that normalised
# before asking (the documented contract is to pass the RAW id) walked straight past
# the guard: every unusable id collapsed onto this one name and two projects shared a
# folder again, which is the exact defect the guard exists to stop. Reserving the word
# closes that door from the other side, so the guard no longer depends on every caller
# getting the argument right.
_PID_RESERVED = {"unknown", "_unknown"}


def _pid_is_acceptable(text: str) -> bool:
    """The shared predicate. Kept separate from project_id_error so the error text and
    the suggestion cannot call each other — an id of 'unknown' made that pair recurse
    without end.

    The alphabet check and the fixed-point check look redundant and are not: the
    alphabet rejects characters, the fixed point rejects SPELLINGS the normaliser would
    rewrite (`crm__up`, `_crm`). Either alone leaves a way for two ids to share a
    folder.
    """
    if not text or not _PID_ACCEPTABLE.match(text):
        return False
    if text.lower() in _PID_RESERVED:
        return False
    return normalize_project_id(text) == text


def project_id_suggestion(project_id) -> str:
    """A valid latin id built from `project_id`, for the refusal text only.

    Guarantees a VALID result: whatever survives transliteration is normalised, and if
    nothing usable survives ('!!!', or an alphabet the table does not cover) a generic
    example is returned instead. A hint the analyst cannot copy-paste is not a hint —
    but see project_id_error: the generic example is NOT offered as a ready value,
    because handing the same name to every uncovered alphabet rebuilds the collision.
    """
    text = str(project_id or "").strip().lower()
    out = "".join(_TRANSLIT.get(ch, ch) for ch in text)
    candidate = normalize_project_id(out)
    if not _pid_is_acceptable(candidate):
        return _PID_FALLBACK_SUGGESTION
    return candidate


def project_id_error(project_id) -> Optional[str]:
    """The BA-facing refusal for an unusable `project_id`, or None when it is fine.

    Returns a string rather than raising so callers that want to ASK (validators,
    tests, a future CLI front-end) do not have to catch. `require_valid_project_id`
    is the raising variant used on the path helpers.

    The id is judged EXACTLY as given — not stripped first. Surrounding spaces are a
    rewriting the analyst cannot see, and `'crm'` and `'  crm  '` sharing one folder is
    the same collision as any other, just harder to notice.
    """
    text = str(project_id or "")
    if _pid_is_acceptable(text):
        return None

    shown = str(project_id) if str(project_id or "").strip() else "(empty)"
    suggestion = project_id_suggestion(project_id)
    if suggestion == _PID_FALLBACK_SUGGESTION:
        # Naming a value the analyst can copy would hand the SAME name to every
        # project whose alphabet the table does not cover, recreating the collision
        # through the advice itself. Say so instead of offering it.
        hint = (f"   Nothing could be transliterated automatically — pick a short "
                f"latin name yourself (for example `{_PID_FALLBACK_SUGGESTION}`).")
    else:
        hint = f"   Try: `{suggestion}`"
        # The suggestion is not part of the path contract, so it MAY look at the disk
        # — and it must: advising a name that is already another project's folder
        # would walk the analyst back into the collision this refusal just prevented.
        try:
            if os.path.isdir(os.path.join(DATA_DIR, normalize_project_id(suggestion))):
                hint += (f"\n   ⚠️ `{suggestion}` already belongs to another project "
                         f"in this workspace — choose a different name.")
        except OSError:
            pass

    return (
        f"❌ `project_id` cannot be `{shown}`.\n"
        f"   `project_id` is the key to every artifact of the project: it IS the name "
        f"of the project's folder, so it has to be spelled exactly the way a folder is "
        f"— lower-case `a-z`, `0-9`, `_` and `-`, starting with a letter or a digit, "
        f"with no spaces and no doubled `_`. Any other spelling would have to be "
        f"rewritten to fit, and two different ids rewritten the same way would land in "
        f"ONE folder and overwrite each other's artifacts.\n"
        f"{hint}\n"
        f"   No project data has been written."
    )


def require_valid_project_id(project_id) -> None:
    """Raises InvalidProjectIdError for an id that cannot be used as a folder name."""
    message = project_id_error(project_id)
    if message is not None:
        raise InvalidProjectIdError(message)


def data_dir_for(project_id: str) -> str:
    """governance_plans/data/<safe_pid>/ — the project's JSON-artifact directory."""
    require_valid_project_id(project_id)
    return os.path.join(DATA_DIR, normalize_project_id(project_id))


def report_dir_for(project_id: str) -> str:
    """governance_plans/reports/<safe_pid>/ — the project's Markdown-report directory."""
    require_valid_project_id(project_id)
    return os.path.join(REPORTS_DIR, normalize_project_id(project_id))


def data_path(project_id: str, filename: str) -> str:
    """Single resolver for the JSON path (used for both reading and writing).

    filename already includes the {safe_pid}_ prefix. There is exactly ONE candidate,
    data/<project_id>/<filename>, and it is where the artifact is both written and
    looked for. The directory is created by the writing side:
    os.makedirs(os.path.dirname(path), ...).

    Until 2026-08-03 this resolver tried five locations, so that artifacts written
    before the per-project layout existed kept resolving. The owner dropped that
    compatibility: no project predates the platform, so the fallbacks could only ever
    find a file some TEST had placed, while costing every reader a five-way search
    whose result depended on what happened to be on disk.

    The project_id guard runs FIRST and is not conditioned on whether files already
    exist. Conditioning it on existence was tried and reverted — "already exists" is
    true precisely in the dangerous case, where an id collapses onto ANOTHER project's
    folder, so the escape hatch waved through the worst input it was supposed to stop.
    """
    require_valid_project_id(project_id)
    return os.path.join(DATA_DIR, normalize_project_id(project_id), filename)


def specs_dir(project_id: str) -> str:
    """The 7.1 specs directory: data/<project_id>/specs/.

    One location, like data_path above.
    """
    require_valid_project_id(project_id)
    return os.path.join(DATA_DIR, normalize_project_id(project_id), "specs")


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
    """Converts the two BA-facing failures into the ❌ string an MCP tool must return.

    Applied at the tool boundary rather than at each of the ~32 load sites, so a new
    tool cannot forget it. Only these two exceptions are caught — everything else
    propagates unchanged, because swallowing unknown errors is how a tool starts
    reporting success it did not achieve.

      CorruptArtifactError  — a stored artifact exists but cannot be parsed.
      InvalidProjectIdError — the project_id cannot be used as a folder name.

    Both share the contract that makes returning them safe: they are raised BEFORE
    anything is written, so the ❌ answer is also a promise that nothing changed.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (CorruptArtifactError, InvalidProjectIdError) as exc:
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
# Verified against update_requirement (5.2) and the node creators (5.1 / 7.1 / 7.4).
# BABOK also lists author, risks and urgency (p. 45-46); this model has no field
# for them, so planning them is refused rather than accepted and never checked.
# `stakeholders` joined with ADR-098: 7.4's declare_stakeholder_interest is its
# writer. The list is the answer to "can the platform store this?", and the day a
# field acquires a writer is the day the answer changes — leaving it out would make
# 3.4 refuse to plan an attribute that now exists.
PLANNABLE_ATTRIBUTES = (
    "status", "version", "source", "priority", "owner",
    "stability", "complexity", "reuse_candidate", "reuse_scope", "last_reviewed",
    "stakeholders",
)

# WHICH TOOL actually writes each plannable attribute. Nine of the twelve are
# `update_requirement`'s parameters; three are not, and the 5.2 audit named
# `update_requirement` for all of them because the tool's name was hard-coded into the
# advice line.
#
# The heavy one is `source`, and it predates ADR-098 by a long way: a node created by
# the standard `init_traceability_repo` has no `source` key at all (it has
# `source_artifact`, a different field), and the Minimum preset — the smallest and
# commonest — audits `source`. So the false advice fires on the DEFAULT route of every
# project that ever wrote a 3.4 plan. The writer exists; it is simply not the tool the
# line named.
#
# Kept next to PLANNABLE_ATTRIBUTES so the two cannot drift: an attribute added to that
# tuple without a writer here is a promise the platform cannot keep (branch review R-4).
ATTRIBUTE_WRITERS = {
    "status": "`update_requirement` (5.2)",
    "version": "`update_requirement` (5.2)",
    "priority": "`update_requirement` (5.2)",
    "owner": "`update_requirement` (5.2)",
    "stability": "`update_requirement` (5.2)",
    "complexity": "`update_requirement` (5.2)",
    "reuse_candidate": "`update_requirement` (5.2)",
    "reuse_scope": "`update_requirement` (5.2)",
    "title": "`update_requirement` (5.2)",
    "source": "`init_traceability_repo` (5.1 — re-state the requirement; it merges "
              "by `stated` rather than duplicating)",
    "stakeholders": "`declare_stakeholder_interest` (7.4, `design` phase)",
    "last_reviewed": "stamped by the platform on every update (nothing to fill in "
                     "by hand — drop it from the plan if it keeps showing up)",
}


def attribute_writer(attribute: str) -> str:
    """The tool that can fill `attribute` in, or a safe fallback for an unknown one."""
    return ATTRIBUTE_WRITERS.get(attribute, "`update_requirement` (5.2)")


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
        # Not "the 3.4 information management plan": this reader serves 4.4 and 5.2
        # (section 3.4), 5.5 (the 3.1 timing form) and 4.1 (the 3.1 work period). The
        # 3.4 wording was accurate when 3.4 was the only consumer, and it now
        # contradicts the sentence the caller prints above it.
        return None, (f"⚠️ The chapter-3 BA plan exists but could not be read "
                      f"(`{path}`) — continuing without it.")
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


# ---------------------------------------------------------------------------
# 3.1 BA Activities (.3) and Timing of BA Work (.4) — shared reader (B3-1)
# ---------------------------------------------------------------------------
#
# Same placement reason as the 3.4 block above: chapter 3 sits in phase.py
# BASE_SERVER and chapters 4/5 load in their own phases, so a consumer may not
# import the chapter-3 module.
#
# BABOK 3.1 element .4 (printed p. 28) is a statement ABOUT the other knowledge
# areas — "whether the business analysis tasks performed within the other
# knowledge areas will be performed primarily in specific phases or iteratively".
# That is why the planned unit of work is a BABOK TASK ID of this platform, not
# free prose: a closed vocabulary is the only kind a consumer can match.

TIMING_FORMS = ("phases", "iterations")

# Same scale as influence/interest in 3.2 — one vocabulary per module is cheaper
# to keep correct than three.
EFFORT_LEVELS = ("Low", "Medium", "High")

# The 25 BABOK tasks this platform implements. Chapter 8 (Solution Evaluation) is
# deliberately absent — it is outside the release perimeter (decision 2026-07-26),
# so planning work for it would point the BA at tools that do not exist.
PLATFORM_TASKS = (
    "3.1", "3.2", "3.3", "3.4", "3.5",
    "4.1", "4.2", "4.3", "4.4", "4.5",
    "5.1", "5.2", "5.3", "5.4", "5.5",
    "6.1", "6.2", "6.3", "6.4",
    "7.1", "7.2", "7.3", "7.4", "7.5", "7.6",
)

PLATFORM_CHAPTERS = ("3", "4", "5", "6", "7")

# ONE rule, two callers (the 3.1b writer derives the form, the 5.5 reader falls
# back to it). Two copies of a decision rule is exactly how the 5.5 dashboard and
# the baseline gate drifted apart. Plain "Hybrid" is ABSENT on purpose: BABOK
# calls predictive/adaptive a continuum (printed p. 26), a hybrid sits between the
# two, and guessing would print an invented methodology onto a document that goes
# out for signature. The tool asks instead.
_TIMING_FORM_BY_APPROACH = {
    "Predictive (Waterfall)": "phases",
    "Adaptive (Agile)": "iterations",
    "Hybrid (Agile + compliance gates)": "iterations",
}


def approach_to_timing_form(approach_label) -> str:
    """`ba_approach.recommended_approach` -> "phases" / "iterations" / ""."""
    if not isinstance(approach_label, str):
        return ""
    return _TIMING_FORM_BY_APPROACH.get(approach_label.strip(), "")


_TASK_REF_PREFIXES = ("task ", "chapter ", "ch.", "ch ")


def normalize_task_ref(value) -> str:
    """A BA-written task reference -> canonical "4.1" / "4", or "" if unrecognised.

    The producer validates and the consumers match through THIS function, both of
    them. When a producer validates raw casing and a consumer matches normalised,
    the BA gets a confident false claim — the 3.4 archetype defect.
    """
    if not isinstance(value, str):
        return ""
    text = value.strip().lower().rstrip(".")
    for prefix in _TASK_REF_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    # "Ch4" / "ch4" carry no separator, so the prefix loop above cannot strip them.
    if text.startswith("ch") and text[2:].strip() in PLATFORM_CHAPTERS:
        text = text[2:].strip()
    if text in PLATFORM_TASKS or text in PLATFORM_CHAPTERS:
        return text
    return ""


def activities_section(plan) -> dict:
    """The `ba_activities` section, coerced into the shapes consumers assume.

    `periods` is always a list of dicts here. Guarding only the section was not
    enough one level down in 3.4, and a bare string where a list belongs is worse
    than a crash: iterating it yields one entry per CHARACTER.
    """
    if not isinstance(plan, dict):
        return {}
    section = plan.get("ba_activities")
    if not isinstance(section, dict):
        return {}
    out = dict(section)
    periods = out.get("periods")
    out["periods"] = ([p for p in periods if isinstance(p, dict)]
                      if isinstance(periods, list) else [])
    return out


def planned_timing_form(plan):
    """Element .4 — "phases" / "iterations", or None when nothing usable is planned."""
    form = activities_section(plan).get("timing_form")
    return form if form in TIMING_FORMS else None


def _period_task_refs(period: dict) -> list:
    """Canonical task refs of one period. A bare string counts as ONE ref."""
    raw = period.get("tasks")
    if isinstance(raw, str):
        raw = [raw]
    elif not isinstance(raw, list):
        raw = []
    return [ref for ref in (normalize_task_ref(t) for t in raw) if ref]


def planned_work_period(plan, task_ref):
    """Element .3 — the period that covers `task_ref`, or None.

    A chapter shorthand covers its tasks ("4" answers a query for "4.1"); a task
    does NOT answer a query for its whole chapter. That asymmetry falls out of the
    vocabulary rather than out of a condition here: when the query IS a chapter,
    `wanted` and `chapter` are the same string, so the second test below can only
    ever repeat the first. Mutation testing is what showed that — an explicit
    `wanted != chapter` guard written to "enforce" the asymmetry could be deleted
    with every test still green, i.e. it was dead code claiming to do work. Both
    directions are pinned by tests instead.

    The record always carries all five keys with safe types: the 4.1 consumer
    INDEXES it, and a shared reader must cover the consumer that indexes, not only
    the ones that re-coerce.
    """
    wanted = normalize_task_ref(task_ref)
    if not wanted:
        return None
    chapter = wanted.split(".")[0]
    for period in activities_section(plan).get("periods", []):
        refs = _period_task_refs(period)
        if wanted in refs or chapter in refs:
            deliverables = period.get("deliverables")
            return {
                "name": str(period.get("name") or ""),
                "tasks": refs,
                "deliverables": ([d for d in deliverables if isinstance(d, str)]
                                 if isinstance(deliverables, list) else []),
                "effort": str(period.get("effort") or ""),
                "when": str(period.get("when") or ""),
            }
    return None


# ---------------------------------------------------------------------------
# BABOK 3.3 — Governance Approach: the shared reader (B3-2)
#
# Chapters 5.3 / 5.4 / 5.5 read the governance plan ONLY through these helpers.
# They load in the `lifecycle` phase and chapter 3 loads in BASE_SERVER, so no
# chapter may import another's module.
# ---------------------------------------------------------------------------

# Moved here from planning_mcp so the "declared vs template" source label is decided
# in exactly ONE place. Two copies of one decision rule is precisely how the 5.5
# dashboard and the baseline gate drifted apart.
GOVERNANCE_TEMPLATES = {
    "High": {
        "change_control": "Formal: Change Request (CR) → assessment → CAB approval",
        "approval":       "Requires sign-off from Sponsor + Product Owner",
        "review_cycle":   "Weekly status + formal review on every CR",
        "escalation":     "BA → PM → Steering Committee",
    },
    "Medium": {
        "change_control": "Adaptive: PO approves changes via the Backlog",
        "approval":       "Product Owner + Lead BA",
        "review_cycle":   "Bi-weekly review, retrospectives",
        "escalation":     "BA → PO → PM",
    },
    "Low": {
        "change_control": "Minimal: logged in Jira, verbal sign-off",
        "approval":       "Lead BA",
        "review_cycle":   "On request",
        "escalation":     "BA → PM",
    },
}

# BABOK 3.3 element .3. A CLOSED vocabulary, identical to the `method` Literal of
# 5.3 start_prioritization_session: an open string could only be compared to the
# session's method by fuzzy match, and a fuzzy match inside a cross-check is a guess
# wearing the costume of a verification. Pinned by a test, because chapter 3 cannot
# import chapter 5 to build it at runtime.
PRIORITIZATION_TECHNIQUES = ("MoSCoW", "WSJF", "ImpactEffort", "TimeBoxing")

# The ceiling for an approval SLA. A year is already absurd for one package; the
# bound exists so a typo cannot travel on the document that goes out for signature.
MAX_APPROVAL_SLA_DAYS = 365

# Field name in the plan -> its key in GOVERNANCE_TEMPLATES. Defined once and
# imported by the writer, so the reader and the writer cannot disagree about which
# template backs which field.
TEMPLATE_FIELD_KEYS = {
    "change_control": "change_control",
    "approval_process": "approval",
    "review_cycle": "review_cycle",
    "escalation_path": "escalation",
}


def governance_section(plan) -> dict:
    """The `governance` section, or {} for any shape that is not a dict.

    Deliberately does NOT supply missing keys. A coercion that fills the dict makes
    its result permanently truthy, and every caller here asks "was THIS value
    planned?", never "is the section truthy?".
    """
    if not isinstance(plan, dict):
        return {}
    section = plan.get("governance")
    return section if isinstance(section, dict) else {}


def _governance_string_list(value) -> list:
    """Every non-blank string in `value`, or [] for anything that is not a list.

    isinstance BEFORE use, never `or []`: a bare string where a list belongs is an
    ordinary LLM mistake, and iterating it yields one entry per CHARACTER — invented
    data a consumer would then present as planned governance.
    """
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, str) and v.strip()]


def planned_decision_makers(plan) -> list:
    """BABOK 3.3 .1 — the roles holding decision authority, or []."""
    return _governance_string_list(governance_section(plan).get("decision_makers"))


def registry_labels(s: dict) -> set:
    """Every normalised label one registry record answers to: its name and its role.

    A role is not a person and a person is not a role, but the registry is the only
    place the two are tied together, and consumers are called with whichever the BA
    typed. Kept in ONE function because `party_aliases` computed the same set inline
    and a second copy would drift the day a third label (an email, an id) is added.
    """
    if not isinstance(s, dict):
        return set()
    return {reg_norm(s.get("name")), reg_norm(s.get("role"))} - {""}


def party_aliases(project_id: str, who) -> set:
    """Every normalised label the stakeholder registry ties to `who` — name and role.

    3.3 plans ROLES ("Product Owner"). 5.3, 5.4 and 5.5 are called with whatever the
    BA types, which is usually a PERSON ("John Smith"). Comparing the two directly is
    a join that cannot succeed by construction, and the failure is not a silent no-op:
    it reports a legitimate approver as an authority exception in a signed document.

    The registry that 3.2 seeds and 4.2 maintains is the only place the two are tied
    together, and it is the same dual-key idea 3.4 -> 4.4 already uses ("an archetype
    from 4.4 OR a job title from the stakeholder map"). A role is not unique, so one
    label can resolve to several people; for a cross-check that is the safe direction —
    it can only prevent a false accusation, never invent one.
    """
    key = reg_norm(who)
    if not key:
        return set()
    aliases = {key}
    for s in load_stakeholder_registry(project_id).get("stakeholders", []):
        if not isinstance(s, dict):
            continue
        labels = registry_labels(s)
        if key in labels:
            aliases |= labels
    return aliases


# The three answers a governance cross-check can honestly give.
PARTY_PLANNED = "planned"
PARTY_UNPLANNED = "unplanned"
PARTY_UNBRIDGEABLE = "unbridgeable"


# Is a typed label known to the stakeholder registry at all? A separate question from
# `planned_party_status`, which asks about the 3.3 GOVERNANCE plan.
PARTY_IN_REGISTRY = "in_registry"
PARTY_NOT_IN_REGISTRY = "not_in_registry"


def registry_party_status(project_id: str, who) -> str:
    """Does the registry know `who`? IN_REGISTRY / NOT_IN_REGISTRY / UNBRIDGEABLE.

    The third answer exists because the registry is a LIVING document (ADR-003): a
    project may legitimately have none yet, and "not in the registry" said about a
    project with no registry is an accusation manufactured from missing data — the
    B3-2 lesson, one chapter over.

    Note the deliberate asymmetry with 6.4's `gap_source`, where an unknown value is
    REFUSED: there the vocabulary is CLOSED (eight elements the platform knows in
    full), here it is OPEN and grows as stakeholders are discovered. Refusing against
    an open list blocks the analyst exactly when they are recording something new.

    UNBRIDGEABLE is decided by the FILE, not by the list inside it. An empty registry
    is a legitimate early state of a living document — the file exists, it was read,
    and it simply holds nobody yet — so "there is no registry, create it via 3.2 or
    4.2" is a false statement about a project that has one on disk. It also made this
    function disagree with itself: rows that carry no name and no role already
    returned NOT_IN_REGISTRY, the same state answered differently depending on how
    many unusable rows happened to be in the list (branch review B-1).
    """
    key = reg_norm(who)
    if not key:
        return PARTY_UNBRIDGEABLE
    if not os.path.exists(stakeholder_registry_path(project_id)):
        return PARTY_UNBRIDGEABLE
    for s in load_stakeholder_registry(project_id).get("stakeholders") or []:
        if key in registry_labels(s):
            return PARTY_IN_REGISTRY
    return PARTY_NOT_IN_REGISTRY


def planned_party_status(project_id: str, planned: list, who) -> str:
    """Is `who` one of `planned`? PARTY_PLANNED / PARTY_UNPLANNED / PARTY_UNBRIDGEABLE.

    The third answer is the point. With no stakeholder registry there is nothing to
    bridge a planned ROLE to a typed NAME, so a non-match means "these two labels
    cannot be compared", not "this person lacks authority" — and a document that says
    the second when it means the first is worse than one that says nothing.
    """
    if not planned:
        return PARTY_PLANNED
    aliases = party_aliases(project_id, who)
    if not aliases:
        return PARTY_UNBRIDGEABLE
    if any(reg_norm(p) in aliases for p in planned):
        return PARTY_PLANNED
    # A registry exists: the platform does know who its people are, so a name it
    # cannot tie to any planned role is a finding worth stating.
    if load_stakeholder_registry(project_id).get("stakeholders"):
        return PARTY_UNPLANNED
    return PARTY_UNBRIDGEABLE


def is_planned_decision_maker(plan, who, project_id: str = "") -> bool:
    """Is `who` one of the planned decision makers?

    The ONLY name matcher for governance. 5.4 passes `decided_by` and 5.5 passes
    `stakeholder_name`; both are "a role or a name", and the plan holds roles. The
    comparison runs through reg_norm on BOTH sides — when a producer validates raw
    casing and a consumer matches normalised, the tool makes confident false claims.

    With `project_id`, the registry bridges role and name (see `party_aliases`).
    Without it the behaviour is the old exact match; callers that can name the project
    should pass it, and every caller in this repo does.
    """
    key = reg_norm(who)
    if not key:
        return False
    planned = planned_decision_makers(plan)
    if project_id:
        return reg_norm(who) in {reg_norm(p) for p in planned} or any(
            reg_norm(p) in party_aliases(project_id, who) for p in planned)
    return any(reg_norm(dm) == key for dm in planned)


def _governance_declared(plan) -> set:
    return set(_governance_string_list(governance_section(plan).get("declared")))


def _governance_carried_over(plan) -> set:
    """Fields kept from a plan written before `declared` existed — origin unknown."""
    return set(_governance_string_list(governance_section(plan).get("carried_over")))


def _governance_template_value(plan, field: str) -> tuple:
    """(text, source) for one template-backed field.

    `declared` is a RECORD carried on the section, never a comparison of the stored
    value against the template: a BA who states wording identical to the template
    still stated it, and a source recovered by comparing strings would be a lookalike
    condition drifting from the fact it imitates.
    """
    section = governance_section(plan)
    # THREE states, the same three the writer records. Teaching the writer and the BA
    # Plan renderer about `carried_over` and not this reader left one project with two
    # delivered documents naming different escalation paths — and the CR Decision
    # Record's was a template string the plan file does not contain anywhere.
    declared = _governance_declared(plan)
    carried = _governance_carried_over(plan)
    if field in declared or field in carried:
        value = section.get(field)
        if isinstance(value, str) and value.strip():
            return value, ("declared in 3.3" if field in declared
                           else "carried over from an earlier plan")
    criticality = section.get("project_criticality")
    template = (GOVERNANCE_TEMPLATES.get(criticality)
                if isinstance(criticality, str) else None)
    if not template:
        return "", ""
    return template[TEMPLATE_FIELD_KEYS[field]], f"from the {criticality} template"


def planned_approval_process(plan) -> tuple:
    """BABOK 3.3 .4 — (process text, source). Source is "" when nothing is planned."""
    return _governance_template_value(plan, "approval_process")


def planned_escalation_path(plan) -> tuple:
    """BABOK 3.3 .1 — (escalation path, source). Source is "" when nothing is planned."""
    return _governance_template_value(plan, "escalation_path")


def planned_approval_timing(plan) -> tuple:
    """BABOK 3.3 .4 "the timing for the approvals" — (days, note, source).

    `days` is a plain integer of BUSINESS days; the platform does no date arithmetic
    (it has no working calendar, and a wrong date would travel on a signed document).
    `note` carries event-based timing a number cannot express ("to the monthly CAB").

    There is deliberately NO template fallback: a made-up deadline on a package that
    goes out for signature is worse than no deadline at all.
    """
    section = governance_section(plan)
    raw = section.get("approval_sla_days")
    # `bool` is an `int` in Python, so a stored `true` would otherwise become a
    # one-business-day deadline printed on the approval package.
    days = (raw if isinstance(raw, int) and not isinstance(raw, bool)
            and 1 <= raw <= MAX_APPROVAL_SLA_DAYS else None)
    raw_note = section.get("approval_timing_note")
    note = raw_note.strip() if isinstance(raw_note, str) else ""
    source = "declared in 3.3" if (days is not None or note) else ""
    return days, note, source


def planned_prioritization(plan) -> dict:
    """BABOK 3.3 .3 — {technique, participants, criteria}; missing parts are empty.

    `technique` is emptied unless it is one of PRIORITIZATION_TECHNIQUES: the value
    exists to be compared with 5.3's `method`, and rendering an unrecognised string
    as "the planned technique" would present junk from a hand-edited file as a plan.
    """
    block = governance_section(plan).get("prioritization")
    if not isinstance(block, dict):
        return {"technique": "", "participants": [], "criteria": []}
    technique = block.get("technique")
    return {
        "technique": technique if technique in PRIORITIZATION_TECHNIQUES else "",
        "participants": _governance_string_list(block.get("participants")),
        "criteria": _governance_string_list(block.get("criteria")),
    }


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
