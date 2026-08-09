"""
BABOK 7.4 — Define Requirements Architecture
MCP tools for organizing requirements by viewpoints, detecting architecture
gaps, and recording an architecture snapshot.

Tools:
  - analyze_requirements_architecture — automatically builds viewpoints from artifact types
  - add_custom_viewpoint              — BA adds a custom viewpoint (by req_ids)
  - declare_stakeholder_interest      — BA states whose interests a requirement touches
  - check_architecture_gaps          — coverage matrix + semantic gaps (two levels)
  - save_architecture_snapshot       — records an architecture snapshot, generates Markdown

VIEWPOINT_MAP — constant mapping of types → viewpoints
reads the stakeholder registry from 4.2 ({project}_stakeholder_registry.json) directly
         (legacy fallback: {project}_stakeholders.json)
custom viewpoints are bound to req_ids, not to types
{project}_architecture.json with snapshots (pattern from 5.5)
check_architecture_gaps — two levels: coverage matrix + semantic gaps
stakeholder↔requirement model. The `stakeholders` field on a requirement node
         holds ONLY what the BA declares here; the owner (7.1) and approval decisions
         (5.5) are read on demand and never copied, so no stored copy can go stale.
         A title-word match is kept as a fourth, explicitly labelled source and is a
         warning, never a critical verdict (this REVISES the earlier rule, which labelled the
         heuristic honestly because no model existed yet).

Reads:  {project}_traceability_repo.json (5.1) — also WRITTEN by declare_stakeholder_interest
        {project}_stakeholder_registry.json (4.2) — optional
        {project}_approval_history.json (5.5) — optional, evidence of interest
        {project}_business_context.json (7.3) — optional
Writes: {project}_architecture.json
        {project}_traceability_repo.json (5.1) — the `stakeholders` field only
        7_4_architecture_*.md (via save_artifact)
Output: Architecture Document → 4.4 (communication), 7.5 (design options)

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from collections import deque
from datetime import date
from typing import Optional
from mcp.server.fastmcp import FastMCP
from skills.common import (write_json_artifact,
    save_artifact, logger, DATA_DIR, data_path, normalize_project_id,
    BUSINESS_NODE_TYPES, NON_REQUIREMENT_NODE_TYPES, stakeholder_registry_path,
    read_json_artifact, guard_artifact_errors, reg_norm, load_approval_history,
    parse_json_str_list, registry_party_status, PARTY_IN_REGISTRY,
    PARTY_NOT_IN_REGISTRY, PARTY_UNBRIDGEABLE, registry_labels,
    ARCHIVED_REQUIREMENT_STATUSES, list_with_cap,
)

mcp = FastMCP("BABOK_Requirements_Architecture")

REPO_FILENAME = "traceability_repo.json"
STAKEHOLDERS_FILENAME = "stakeholders.json"
CONTEXT_FILENAME = "business_context.json"
ARCHITECTURE_FILENAME = "architecture.json"

# ADR-034: mapping of artifact types to viewpoints
VIEWPOINT_MAP = {
    "business_process": {
        "label": "Business processes",
        "audience": "Business sponsor, process owners",
    },
    "data_dictionary": {
        "label": "Data and information",
        "audience": "Data architect, DBA",
    },
    "erd": {
        "label": "Data and information",
        "audience": "Data architect, DBA",
    },
    "user_story": {
        "label": "Users and interaction",
        "audience": "UX designer, developer, tester",
    },
    "use_case": {
        "label": "Users and interaction",
        "audience": "UX designer, developer, tester",
    },
    "functional": {
        "label": "Functionality",
        "audience": "Developer, architect",
    },
    "non_functional": {
        "label": "Functionality",
        "audience": "Developer, architect",
    },
    "business_rule": {
        "label": "Business rules",
        "audience": "Business analyst, legal, compliance",
    },
    # On-demand fallback for the requirement CLASSES 5.1 can hold (solution / transition /
    # stakeholder / component) that have no dedicated 7.1 viewpoint. Without it they were
    # counted in the denominator but appeared in NO viewpoint and NOWHERE in the signed
    # architecture document — the 7.4 mirror of the coverage-vocabulary class. Populated
    # only when such requirements exist (never flagged as a "missing" viewpoint).
    "other": {
        "label": "Other requirements",
        "audience": "Architect, business analyst",
    },
}

# Types that are NOT viewpoint artifacts. The local set used to be
# BUSINESS_NODE_TYPES | {"test"} (audit finding 7.4-C) — a snapshot taken before
# `risk` (6.3), `change_request` (5.4) and `solution_scope` (6.4) existed. Those
# nodes then counted as "active requirements", could never appear in any viewpoint
# (their types are not in VIEWPOINT_MAP), and diluted "Covered by viewpoints %" —
# the number that lands in the signed architecture snapshot. Ask the shared,
# growing definition instead of freezing it locally (the Part-2d class).
SKIP_TYPES = NON_REQUIREMENT_NODE_TYPES


# ---------------------------------------------------------------------------
# Utilities — paths and file loading
# ---------------------------------------------------------------------------

def _safe(project_id: str) -> str:
    return normalize_project_id(project_id)


def _repo_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{REPO_FILENAME}")


def _stakeholders_path(project_id: str) -> str:
    # 4.2 writes the living registry to <pid>_stakeholder_registry.json (the real producer file);
    # older data may use the flat <pid>_stakeholders.json. Prefer the registry, fall back to legacy
    # (audit finding 7.4-A — the consumer read the wrong filename).
    # Built by the SAME helper the producers write through, so the path cannot drift
    # apart again (finding 7.4-A was exactly that drift, and 3.2 is now a second writer).
    registry = stakeholder_registry_path(project_id)
    if os.path.exists(registry):
        return registry
    legacy = data_path(project_id, f"{_safe(project_id)}_{STAKEHOLDERS_FILENAME}")
    return legacy if os.path.exists(legacy) else registry


def _context_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{CONTEXT_FILENAME}")


def _architecture_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{ARCHITECTURE_FILENAME}")


def _load_repo(project_id: str) -> dict:
    path = _repo_path(project_id)
    if os.path.exists(path):
        # Corrupt -> CorruptArtifactError, converted to a ❌ line at the tool
        # boundary by guard_artifact_errors (the chapters-5 / 7.1-7.3 pattern).
        return read_json_artifact(path, "7.4 stored artifact")
    return {"project": project_id, "requirements": [], "links": [], "history": []}


def _save_repo(repo: dict, project_id: str) -> None:
    """Persists the 5.1 graph. 7.4 is a writer of this file the same way 7.1, 6.3 and
    5.4 already are — `data_path` returns the path it READ from, so no second copy of
    the repository can appear under a different layout."""
    path = _repo_path(project_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    repo["updated"] = str(date.today())
    write_json_artifact(path, repo)
    logger.info(f"Traceability repo saved by 7.4: {path}")


def _load_stakeholders(project_id: str) -> Optional[dict]:
    """Read the stakeholder registry from 4.2 directly. Returns None if the file is missing."""
    path = _stakeholders_path(project_id)
    if os.path.exists(path):
        # Corrupt -> CorruptArtifactError, converted to a ❌ line at the tool
        # boundary by guard_artifact_errors (the chapters-5 / 7.1-7.3 pattern).
        return read_json_artifact(path, "7.4 stored artifact")
    return None


def _load_context(project_id: str) -> Optional[dict]:
    path = _context_path(project_id)
    if os.path.exists(path):
        # Corrupt -> CorruptArtifactError, converted to a ❌ line at the tool
        # boundary by guard_artifact_errors (the chapters-5 / 7.1-7.3 pattern).
        return read_json_artifact(path, "7.4 stored artifact")
    return None


def _load_architecture(project_id: str) -> dict:
    path = _architecture_path(project_id)
    if os.path.exists(path):
        # Corrupt -> CorruptArtifactError, converted to a ❌ line at the tool
        # boundary by guard_artifact_errors (the chapters-5 / 7.1-7.3 pattern).
        return read_json_artifact(path, "7.4 stored artifact")
    return {
        "project_id": project_id,
        "viewpoints": {},
        "views": {},
        "gaps": {"critical": [], "warning": [], "info": []},
        "snapshots": [],
        "created": str(date.today()),
        "updated": str(date.today()),
    }


def _save_architecture(data: dict) -> None:
    project_id = data["project_id"]
    path = _architecture_path(project_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data["updated"] = str(date.today())
    write_json_artifact(path, data)
    logger.info(f"Architecture saved: {path}")


def _find_req(repo: dict, req_id: str) -> Optional[dict]:
    for r in repo.get("requirements", []):
        if r["id"] == req_id:
            return r
    return None


def _is_requirement(node) -> bool:
    """Is this graph node a REQUIREMENT, or another chapter's artifact?

    Nine producers write into the 5.1 graph. A risk (6.3), a business goal (6.2), a
    change request (5.4), the 6.4 solution scope and a test case all live there for
    traceability and are none of them requirements — `_build_views_from_repo`, the
    `Total req` count and the level-2 type buckets have always said so. The
    stakeholder path added later did not, so a declared interest on a risk was
    answered "interest declared on 1 requirement(s)", counted as coverage, and
    printed in the signed document under a header saying the project has one
    requirement (branch review R-1).
    """
    return isinstance(node, dict) and node.get("type", "") not in SKIP_TYPES


def _is_archived(node) -> bool:
    """Is this requirement retired from the active set? (5.2's three terminal statuses.)

    Archived requirements are never deleted — the project rule — so they stay in the
    graph, in the history and in the traceability matrix. What they must NOT do is
    count as coverage: a stakeholder whose every recorded tie was deprecated last
    month is not represented in the architecture being signed today.
    """
    return isinstance(node, dict) and node.get("status") in ARCHIVED_REQUIREMENT_STATUSES


def _viewpoint_row(repo: dict, req_id: str) -> str:
    """One row of a viewpoint table in the delivered document, or "" if unknown.

    The table is addressed to "Developer, architect" and is an input artifact for 7.5,
    so a requirement 5.2 retired must not read here as one to build — the concerns
    section on the same page already says an archived tie is not live coverage, and one
    id governed by two rules on one page is the defect class this branch keeps meeting.

    MARKED, never dropped. Dropping the row would move `Total req` for every existing
    project, and that is a released number; marking adds the missing fact and changes
    no count. It is also the choice B-2 already made one section down.

    Both the auto and the custom viewpoint tables render through here: two copies of
    this rule would drift apart, which is exactly how T8-3 happened.
    """
    req = _find_req(repo, req_id)
    if not req:
        return ""
    # NOT `_md_label` on the title. That one strips `*` and `_` because a NAME holding
    # them is a formatting accident, but a requirement title reading "user_id must be
    # unique" means it, and quietly serving "userid" would be a worse lie than a bold
    # word. Only what actually breaks a table cell is neutralised: a pipe and a newline.
    title = " ".join(str(req.get("title", "")).split()).replace("|", r"\|")[:60]
    mark = " _(archived)_" if _is_archived(req) else ""
    return f"| `{_md_id(req_id)}` | {req.get('type', '?')} | {title}{mark} |"


# ---------------------------------------------------------------------------
# Stakeholder↔requirement model (ADR-098)
# ---------------------------------------------------------------------------

def _concern_name(entry) -> str:
    """One declared stakeholder name from a `stakeholders` entry, or "".

    TWO forms are accepted on read and exactly ONE is ever written. The bare string is
    the form this module's previous reader understood (`str(sh).lower()`), so a file an
    older build or a human wrote keeps rendering. Anything else returns "" rather than
    being stringified: `str(42)` would put "42" into a signed document as a person.
    """
    if isinstance(entry, str):
        return entry.strip()
    if isinstance(entry, dict):
        name = entry.get("name")
        return name.strip() if isinstance(name, str) else ""
    return ""


def _concern_note(entry) -> str:
    """The `why` the BA typed alongside a declaration, or "".

    Only the object form can carry one; the bare-string form is a name and nothing else.
    """
    if isinstance(entry, dict):
        note = entry.get("note")
        return note.strip() if isinstance(note, str) else ""
    return ""


def _declared_entries(req: dict) -> list:
    """[(name, note)] the BA declared on ONE requirement, in order, deduped by reg_norm.

    `.get(k) or []` rather than `.get(k, [])`: the missing key and an explicit null are
    different inputs and only the first is what a default protects against. A non-list
    value is a third input again — a hand-edited file — and must degrade, not raise.
    """
    raw = req.get("stakeholders") or []
    if not isinstance(raw, list):
        return []
    out, seen = [], set()
    for entry in raw:
        name = _concern_name(entry)
        key = reg_norm(name)
        if key and key not in seen:
            seen.add(key)
            out.append((name, _concern_note(entry)))
    return out


def _declared_concerns(req: dict) -> list:
    """Just the names — the shape every caller wanted before `note` became readable."""
    return [name for name, _ in _declared_entries(req)]


# Where a stakeholder↔requirement tie came from. The first three are EVIDENCE — a fact
# some chapter recorded on purpose. The fourth is the pre-existing title heuristic,
# kept so no existing project loses coverage it had yesterday, and labelled so no
# reader mistakes it for the other three.
CONCERN_DECLARED = "declared"
CONCERN_OWNER = "7.1:owner"
CONCERN_APPROVAL = "5.5:approval"
CONCERN_TITLE = "title-match"

CONCERN_EVIDENCE = (CONCERN_DECLARED, CONCERN_OWNER, CONCERN_APPROVAL)

# How each source reads to a human. The gap message used to spell the same four out by
# hand in its prose, so `CONCERN_TITLE` and `CONCERN_EVIDENCE` were declared and read
# nowhere: rename a source and the message keeps quoting the old name, with nothing to
# fail (branch review A-6). The verdict is now assembled from the tuple, in its order.
CONCERN_LABELS = {
    CONCERN_DECLARED: "declared interest (7.4)",
    CONCERN_OWNER: "7.1 owner",
    CONCERN_APPROVAL: "5.5 approval decision on it",
    CONCERN_TITLE: "requirement title mentioning them (heuristic)",
}


def _approval_voters(project_id: str) -> dict:
    """{req_id: [stakeholder names]} from 5.5's durable record, or {} when unreadable.

    Read through the SHARED loader rather than by importing 5.5: that module loads in
    the `lifecycle` phase and this one in `design`, so the phases never overlap and the
    import would fail at runtime. `_compute_req_status` in 5.5 documents the same
    constraint from the other side.

    Every level is guarded by TYPE, not by truthiness. A file that is valid JSON of the
    wrong shape ("packages" as a list) reaches `.get` and raises AttributeError, which
    `guard_artifact_errors` does not catch — the exact failure that lost the first step
    of chapter 6 until afe5961.
    """
    history = load_approval_history(project_id)
    if not isinstance(history, dict):
        return {}
    packages = history.get("packages")
    if not isinstance(packages, dict):
        return {}
    out: dict = {}
    for pkg in packages.values():
        if not isinstance(pkg, dict):
            continue
        decisions = pkg.get("stakeholder_decisions")
        if not isinstance(decisions, dict):
            continue
        for sh_name, sh_data in decisions.items():
            if not isinstance(sh_data, dict):
                continue
            req_decisions = sh_data.get("req_decisions")
            if not isinstance(req_decisions, list):
                continue
            for rd in req_decisions:
                if not isinstance(rd, dict):
                    continue
                req_id = rd.get("req_id")
                if not isinstance(req_id, str) or not req_id:
                    continue
                names = out.setdefault(req_id, [])
                if sh_name not in names:
                    names.append(sh_name)
    return out


def _stakeholder_evidence(project_id: str, repo: dict) -> dict:
    """{req_id: [{"who", "source", "archived", "note"}]} — every RECORDED tie, with its
    provenance and the BA's own reason where they gave one.

    Nothing here is written back. `owner` is 7.1's field and the votes are 5.5's record;
    a stored copy would say the wrong name the moment either owner changed theirs, which
    is the whole reason the declared field holds declarations only.

    A person reached from two sources is kept TWICE, once per source: "declared and also
    voted in 5.5" is stronger than either alone, and the document may show both.

    Only REQUIREMENTS are walked. A tie recorded on a risk or a business goal — by hand
    or by an older build — is not evidence of anything about requirement coverage, and
    counting it let a business goal silence the very check this model exists for.

    Each item also carries `archived` — the STATUS of the requirement the tie points at.
    It travels with the tie rather than being looked up again by every consumer, so the
    gap report and the document cannot disagree about which ties are live.
    """
    voters = _approval_voters(project_id)
    evidence: dict = {}
    for req in repo.get("requirements", []):
        if not _is_requirement(req):
            continue
        req_id = req.get("id")
        if not isinstance(req_id, str) or not req_id:
            continue
        archived = _is_archived(req)
        found: list = []
        seen: set = set()

        def _add(who: str, source: str, note: str = "") -> None:
            key = (reg_norm(who), source)
            if key[0] and key not in seen:
                seen.add(key)
                found.append({"who": who, "source": source, "archived": archived,
                              "note": note})

        for name, note in _declared_entries(req):
            _add(name, CONCERN_DECLARED, note)
        owner = req.get("owner")
        if isinstance(owner, str):
            _add(owner.strip(), CONCERN_OWNER)
        for name in voters.get(req_id, []):
            if isinstance(name, str):
                _add(name.strip(), CONCERN_APPROVAL)
        evidence[req_id] = found
    return evidence


def _ties_for_labels(labels: set, evidence: dict) -> list:
    """Recorded ties for ONE stakeholder: the evidence items that resolve to them.

    `labels` is what `registry_labels` returns for that person — name AND role — so a
    requirement whose owner is a name and whose declaration is a role both resolve to
    the same human. Sorted so the delivered document does not reorder between runs on
    identical data.
    """
    ties = []
    for req_id, items in evidence.items():
        for item in items:
            if reg_norm(item["who"]) in labels:
                ties.append({"req_id": req_id, "source": item["source"],
                             "archived": item.get("archived", False),
                             "note": item.get("note", "")})
    return sorted(ties, key=lambda t: (t["req_id"], t["source"]))


def _heuristic_pools(all_reqs: list, evidence: dict) -> tuple:
    """The coincidence pools a label can match: title words — kept apart by whether the
    title belonged to a requirement — and recorded names.

    Lives here, called from BOTH `check_architecture_gaps` and `_concern_lines`, because
    the gap report and the delivered document describe the same person and must not
    reach different conclusions about them. Two copies of this rule would drift, and the
    drift would surface as one page contradicting another in front of a sponsor.

    The pool spans the WHOLE 5.1 graph, risks and goals and change requests included,
    exactly as the earlier bucket did. R-1's objection was never that the pool was
    too wide — it was that the sentence LIED about where the platform had looked, saying
    "a word in a requirement title" when the word sat in a risk title. That is fixed by
    keeping the two title sets apart and naming the right one, not by narrowing the
    pool: narrowing it turned silence into a critical for a role-only registry row named
    by a risk, and for the owner of a risk node, which is the single outcome decision 6
    forbids (re-review N-2, measured against `afe5961`).

    Nothing here can promote anything to evidence — `_stakeholder_evidence` stays
    requirements-only, so a declaration on a risk is still not coverage. This is a
    bucket that is matched against and never rendered, which is what lets it hold raw
    values (branch review A-3) and foreign node types alike.
    """
    title_words: set = set()
    outside_pool: set = set()
    name_pool: set = set()
    for req in all_reqs:
        if not isinstance(req, dict):
            continue
        words = str(req.get("title") or "").lower().split()
        if not _is_requirement(req):
            # Everything a NON-requirement node carries — its title words and any name
            # recorded on it — goes into one pool, because it answers one question:
            # "is this person traceable anywhere OUTSIDE the requirements?" The verdict
            # built from it says exactly that, which is the honesty R-1 asked for and
            # the silence decision 6 asked for, at the same time.
            outside_pool.update(words)
            outside_owner = reg_norm(req.get("owner"))
            if outside_owner:
                outside_pool.add(outside_owner)
            outside_declared = req.get("stakeholders")
            if isinstance(outside_declared, list):
                for entry in outside_declared:
                    token = reg_norm(entry if isinstance(entry, str)
                                     else _concern_name(entry) or str(entry))
                    if token:
                        outside_pool.add(token)
            continue
        title_words.update(words)
        # The pre-ADR-098 rule reached EVERY value through `str()`, so a non-string
        # `owner` and an unreadable `stakeholders` entry (a role-only dict, say) still
        # put something in the bucket it matched against. Evidence drops both on
        # purpose — `str(42)` would print "42" into a signed document as a person — but
        # dropping them from the COINCIDENCE pool as well turned yesterday's silence
        # into today's critical, the one outcome decision 6 forbids (branch review
        # A-3). This pool is only ever matched against and never rendered, so the raw
        # values can rejoin it without any of them becoming a name on the page.
        raw_owner = reg_norm(req.get("owner"))
        if raw_owner:
            name_pool.add(raw_owner)
        raw_declared = req.get("stakeholders")
        if isinstance(raw_declared, list):
            for entry in raw_declared:
                token = reg_norm(entry if isinstance(entry, str) else str(entry))
                if token:
                    name_pool.add(token)
    for items in evidence.values():
        for item in items:
            who_norm = reg_norm(item.get("who"))
            if who_norm:
                name_pool.add(who_norm)
    return title_words, outside_pool, name_pool


# What a coincidence pool can say about a stakeholder who has no exact tie. Values are
# internal keys, never printed: each surface writes its own sentence from them.
COINCIDENCE_NONE = ""
COINCIDENCE_REQUIREMENT = "requirement_side"
COINCIDENCE_OUTSIDE = "outside_requirements"


def _coincidence_kind(labels: set, title_words: set, name_pool: set,
                      outside_pool: set) -> str:
    """Which coincidence — if any — reaches this person. DECIDED HERE, rendered twice.

    ORDER IS LOAD-BEARING and it is the reason this function exists. "Traceable only
    OUTSIDE the requirements" is the WEAKEST of the three claims, and the word `only`
    makes it false the moment anything on the requirement side matches. The gap report
    and the delivered document each grew their own branch order — report
    title -> outside -> name, document (title or name) -> outside — and a person
    matching BOTH sides got two different descriptions of one state, the report's
    being contradicted three lines below on its own page.

    Aligning two hand-written orders would have held only until a fourth state
    appeared. Two surfaces describing one object must not each carry their own copy of
    the rule; that is the T8-3 lesson, and this fix is where it applies to itself.
    """
    if _heuristic_hit(labels, title_words) or _heuristic_hit(labels, name_pool):
        return COINCIDENCE_REQUIREMENT
    if _heuristic_hit(labels, outside_pool):
        return COINCIDENCE_OUTSIDE
    return COINCIDENCE_NONE


def _heuristic_hit(labels: set, pool: set) -> bool:
    """Bidirectional substring with the 4-character floor — the earlier rule.

    Kept verbatim from the old flat-bucket check, and fed from the same RAW values the
    old bucket held (see `_heuristic_pools`), so the set of stakeholders it called
    "represented" stays a subset of (silent | warning) and no upgrade turns an existing
    project's silence into a critical finding.
    """
    return any(
        label in entry or entry in label
        for label in labels
        for entry in pool
        if len(entry) >= 4
    )


# The delivered document is Markdown, and every name in it was typed by a human into a
# stakeholder registry. A name holding `**` rendered as `****Bold Person****`, a name
# holding a newline broke the bullet list apart, and a backtick closed the code span the
# gap message puts around it early (branch review B-5). Neutralised on the way OUT, once,
# rather than validated on the way in: the registry is a living document written by four
# producers and this is the only page that formats it.
_MD_SPECIALS = "*_`[]|<>\\"

# Ceilings. The viewpoint tables one section up already cap at `req_ids[:20]`; the
# concerns bullets had none, so one person on 60 requirements produced a single
# 1297-character line.
_MAX_REFS_SHOWN = 20
_MAX_LABEL_CHARS = 80
_MAX_NOTE_CHARS = 160


def _md_id(value, limit: int = 40) -> str:
    """A requirement id on its way into a `code span`, and NOT through `_md_label`.

    `_md_label` strips `_ * [ ] | < >` because a NAME holding them is a formatting
    accident. An id is not: inside backticks those characters are already literal, and
    a repository holding `FR_003` was served `FR003` in three places of the delivered
    document while the gap report of the same run printed `FR_003` (re-review N-1).
    Two surfaces disagreeing about one object is what the wave existed to remove.

    Only what a code span genuinely cannot survive is neutralised: a backtick closes
    it early, a pipe splits a table cell, a newline ends the line.
    """
    text = " ".join(str(value or "").split()).replace("`", "").replace("|", r"\|")
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def _md_label(value, limit: int = _MAX_LABEL_CHARS) -> str:
    """Free text made safe to interpolate into one line of the delivered Markdown."""
    text = " ".join(str(value or "").split())
    for ch in _MD_SPECIALS:
        text = text.replace(ch, "")
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def _note_lines(pairs) -> list:
    """The BA's own `why`, indented under the bullet that owns it.

    It was stored by `declare_stakeholder_interest`, invited by its docstring — and
    read by nobody: one write, zero reads (branch review B-4). B-4's fix then printed
    it in ONE of the three branches that render this section, so a person declared
    while not yet in the 4.2 registry — a route the tool supports on purpose — still
    lost their reason, and so did every project with no registry at all (re-review
    N-3). Those are the readers who need it most: nothing else corroborates their tie.

    One function, called from all three branches. Three copies of a rendering rule is
    how T8-3 happened.
    """
    return [f"  - `{_md_id(req_id)}`: {_md_label(why, _MAX_NOTE_CHARS)}"
            for req_id, why in sorted({(r, w) for r, w in pairs if w})]


def _group_refs(refs) -> str:
    """`FR-001` (7.1:owner, declared) — one reference per requirement, sources folded in.

    A requirement backed by two sources used to render as two entries, so the count
    ("1 requirement") disagreed with the list under it. Both halves were true and the
    page still read as broken (live-run finding L-1).

    An archived requirement (5.2 deprecated / superseded / retired) is SHOWN and
    marked, never hidden: the BA declared that tie and is entitled to see what became
    of it. Dropping it silently would be the same class this branch has already fixed
    twice — the tool saying it recorded something the page never mentions.
    """
    by_req: dict = {}
    archived: dict = {}
    for ref in refs:
        req_id, source = ref[0], ref[1]
        is_archived = bool(ref[2]) if len(ref) > 2 else False
        by_req.setdefault(req_id, [])
        if source not in by_req[req_id]:
            by_req[req_id].append(source)
        archived[req_id] = archived.get(req_id, False) or is_archived
    ordered = sorted(by_req.items())
    shown = ordered[:_MAX_REFS_SHOWN]
    rendered = ", ".join(
        f"`{_md_id(req_id)}` ({', '.join(sorted(sources))}"
        + (", archived)" if archived.get(req_id) else ")")
        for req_id, sources in shown
    )
    # The LIST is truncated, never the COUNT: the caller prints "60 requirements" above
    # this string, and a shortened number would be a false claim rather than a shorter
    # one. Saying how many were held back keeps the two halves consistent.
    if len(ordered) > len(shown):
        rendered += f", _+{len(ordered) - len(shown)} more_"
    return rendered


def _concern_lines(project_id: str, repo: dict) -> list:
    """The 'Stakeholder concerns' section of the architecture document.

    Every line names the req_id it rests on, because the reader of THIS page must be
    able to check it: a document renders a subset of the data, and a claim about
    something outside that subset is unverifiable (the class the 6.4 live run found).
    """
    evidence = _stakeholder_evidence(project_id, repo)
    registry = _load_stakeholders(project_id)
    # `.get(k) or []`, then a type check — the rule the function two screens up
    # states in its own docstring. A stored `"stakeholders": null` made `.get(k, [])`
    # hand back None and the comprehension below iterate it, and the resulting
    # TypeError is not a CorruptArtifactError, so `guard_artifact_errors` let it out
    # of the tool: no document at all, on a file `check_architecture_gaps` reads
    # happily (branch review R-2).
    raw_people = (registry.get("stakeholders") or []) if isinstance(registry, dict) else []
    people = ([s for s in raw_people if isinstance(s, dict) and registry_labels(s)]
              if isinstance(raw_people, list) else [])

    lines = ["## Stakeholder concerns", ""]

    if people:
        lines += [
            "Whose interests each requirement touches. `declared` is the analyst's own "
            "statement (7.4); the other sources are facts recorded by another task and "
            "read here without being copied.",
            "",
        ]
        title_words, outside_pool, name_pool = _heuristic_pools(
            repo.get("requirements", []), evidence)
        seen_labels: set = set()
        # label -> the display names that answer to it. A LIST, not one name: a role
        # is not unique, and two people sharing one ("Compliance") used to collapse to
        # whichever was read first, so the second could never be named in the
        # same-person hint below (branch review A-4).
        label_owner: dict = {}
        # normalised label -> the registry's OWN wording for it. `registry_labels`
        # returns comparison keys, and the hint below used to print one of those
        # straight into the delivered page: a sponsor read "(on `priya nair`)",
        # lower-cased and whitespace-collapsed, which is the platform's internal
        # value, not anything a human typed (re-review RR-2). Same class as the empty
        # backticks `stakeholder_id` used to render.
        label_text: dict = {}
        for sh in people:
            who = _md_label(sh.get("name") or sh.get("role") or "—")
            labels = registry_labels(sh)
            seen_labels |= labels
            for raw in (sh.get("name"), sh.get("role")):
                if isinstance(raw, str) and raw.strip():
                    label_text.setdefault(reg_norm(raw), raw.strip())
            for lab in labels:
                holders = label_owner.setdefault(lab, [])
                if who not in holders:
                    holders.append(who)
            ties = _ties_for_labels(labels, evidence)
            if not ties:
                # "Nothing at all" and "only a coincidence" are DIFFERENT states, and
                # the gap report already distinguishes them. Printing the same words
                # for both erased a distinction the platform had drawn one tool over
                # (live-run finding L-3), and left the sponsor unable to see why one
                # person was a critical gap and the other only a warning.
                kind = _coincidence_kind(labels, title_words, name_pool, outside_pool)
                if kind == COINCIDENCE_REQUIREMENT:
                    lines.append(
                        f"- **{who}** — no exact tie recorded; reachable only by a "
                        f"partial name or title match (a coincidence, not a fact). "
                        f"Confirm with `declare_stakeholder_interest`."
                    )
                elif kind == COINCIDENCE_OUTSIDE:
                    lines.append(
                        f"- **{who}** — no tie among the requirements; reachable only "
                        f"through something recorded outside them — a risk (6.3), a "
                        f"business goal (6.2) or a change request (5.4). A "
                        f"coincidence, not a fact. Confirm with "
                        f"`declare_stakeholder_interest`."
                    )
                else:
                    lines.append(f"- **{who}** — no interest recorded.")
                continue
            count = len({t["req_id"] for t in ties})
            noun = "requirement" if count == 1 else "requirements"
            # An all-archived person is a THIRD state again, and the gap report calls
            # it a warning — so the page must not read like full coverage (B-2).
            # The plural has to follow the count: "1 requirement … every one of them
            # archived" is not a sentence, and this line is read by a sponsor.
            if any(not t["archived"] for t in ties):
                all_archived = ""
            elif count == 1:
                # The ref already carries "(… , archived)", so repeating the word here
                # only stutters — the sentence has to add the CONSEQUENCE instead.
                all_archived = " — so it is not live coverage"
            else:
                all_archived = (" — every one of them archived (5.2), so none of it "
                                "is live coverage")
            lines.append(
                f"- **{who}** — {count} {noun}: "
                f"{_group_refs((t['req_id'], t['source'], t['archived']) for t in ties)}"
                f"{all_archived}")
            lines += _note_lines((t["req_id"], t.get("note")) for t in ties)

        # People the analyst tied to a requirement who are NOT in the registry.
        # `declare_stakeholder_interest` accepts them on purpose — the registry is a
        # living document — and says "recorded anyway". Walking only the registry made
        # that recording invisible on the page, so the analyst was told one thing and
        # shown another (live-run finding L-2).
        outside: dict = {}
        for req_id, items in evidence.items():
            for item in items:
                key = reg_norm(item["who"])
                if not key or key in seen_labels:
                    continue
                entry = outside.setdefault(key, {"display": item["who"], "refs": [],
                                                 "notes": []})
                entry["refs"].append((req_id, item["source"], item["archived"]))
                entry["notes"].append((req_id, item.get("note")))
        if outside:
            lines += ["", "**Tied to requirements but not in the 4.2 registry** — add "
                          "them with `update_stakeholder_registry` so the coverage "
                          "check can see them:", ""]
            for key in sorted(outside, key=lambda k: outside[k]["display"]):
                entry = outside[key]
                count = len({r for r, _, _ in entry["refs"]})
                noun = "requirement" if count == 1 else "requirements"
                # A short form of a registry name ("Priya" for "Priya Nair") lands here
                # because the label did not match EXACTLY — and then the block's advice,
                # "add them to the registry", is wrong for them: the thing to correct is
                # the owner field. Say which registry member they resemble, so the same
                # human is not read as two (live-run finding L-4, produced by the fix
                # for L-2 and caught only by re-reading the assembled page).
                #
                # It is a SUBSTRING match and it says so. "Compliance Officer" against a
                # registry row {"name": "Ivan Petrov", "role": "Compliance"} welded two
                # different named humans together on the strength of one shared word,
                # and stated it flatly — the only heuristic claim on this branch that
                # did not name itself as one (branch review A-4). Every match is listed,
                # not just whichever came first alphabetically, so the reader can check
                # the claim against the registry.
                matched = sorted(
                    {(lab, name) for lab in label_owner
                     if _heuristic_hit({key}, {lab})
                     for name in label_owner[lab]}
                )
                hint = ""
                if matched:
                    shown = matched[:3]
                    who_list = ", ".join(
                        f"**{_md_label(name)}** (on `{_md_id(label_text.get(lab, lab))}`)"
                        for lab, name in shown)
                    more = "" if len(matched) <= 3 else f" +{len(matched) - 3} more"
                    hint = (f" — possibly the same person as {who_list}{more}: a "
                            f"partial-label match, a coincidence rather than a fact. "
                            f"If it is the same person, correct the record this tie "
                            f"came from rather than adding them to the registry.")
                lines.append(f"- **{_md_label(entry['display'])}** — {count} "
                             f"{noun}: {_group_refs(entry['refs'])}{hint}")
                lines += _note_lines(entry["notes"])
    else:
        # No usable registry rows — but this covers TWO different facts, and the
        # document must not conflate them: the file may genuinely be absent, or it
        # may have been read successfully and simply hold nobody identifiable yet
        # (e.g. `{"stakeholders": []}` on the very first elicitation pass). Saying
        # "not found" in the second case is a false claim on a signed document — the
        # same denominator-is-a-claim problem this function's own docstring warns
        # about, only inverted (fix review round 1).
        if registry is None:
            lines.append(
                "⚠️ Stakeholder registry not found — the list of people was not checked "
                "for completeness. Below are only the ties recorded on the requirements "
                "themselves."
            )
        else:
            lines.append(
                "⚠️ Stakeholder registry has no identifiable people — none of its rows "
                "carries a name or a role, so completeness could not be checked against "
                "it. Below are only the ties recorded on the requirements themselves."
            )
        lines.append("")

        # Grouped by IDENTITY (reg_norm), not by the raw string: two producer tasks
        # (7.4's declaration, 7.1's owner field) type the same human differently —
        # "David Kim" vs "david kim" — and keying on the raw text split one person
        # into two bullets, each under-reporting their own tie count (fix review
        # round 1). The first spelling encountered is kept for display.
        named: dict = {}  # reg_norm(who) -> {"display": who, "refs": [(req_id, source, archived), ...]}
        for req_id, items in evidence.items():
            for item in items:
                key = reg_norm(item["who"])
                if not key:
                    continue
                entry = named.setdefault(key, {"display": item["who"], "refs": [],
                                               "notes": []})
                entry["refs"].append((req_id, item["source"], item["archived"]))
                entry["notes"].append((req_id, item.get("note")))
        for key in sorted(named, key=lambda k: named[k]["display"]):
            entry = named[key]
            refs = entry["refs"]
            count = len({r for r, _, _ in refs})
            noun = "requirement" if count == 1 else "requirements"
            lines.append(f"- **{_md_label(entry['display'])}** — {count} {noun}: "
                         f"{_group_refs(refs)}")
            lines += _note_lines(entry["notes"])
        if not named:
            lines.append("- No stakeholder ties recorded on any requirement.")

    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# BFS for semantic gap analysis
# ---------------------------------------------------------------------------

def _get_linked_ids(repo: dict, req_id: str, relation_filter: Optional[set] = None) -> set:
    """
    Returns the IDs of all req linked to req_id in the 5.1 repository.
    If relation_filter is set — only links of the specified types.
    """
    links = repo.get("links", [])
    result = set()
    for link in links:
        rel = link.get("relation", "")
        if relation_filter and rel not in relation_filter:
            continue
        if link.get("from") == req_id:
            result.add(link.get("to"))
        elif link.get("to") == req_id:
            result.add(link.get("from"))
    result.discard(None)
    return result


def _build_views_from_repo(repo: dict) -> dict:
    """
    Builds a dict {viewpoint_key: [req_id, ...]} from the 5.1 repository.
    Uses VIEWPOINT_MAP to map types → viewpoints.
    """
    views: dict = {}
    for req in repo.get("requirements", []):
        req_type = req.get("type", "")
        if req_type in SKIP_TYPES:
            continue
        # Requirement classes without a dedicated viewpoint (solution / transition /
        # stakeholder / component) fall into the "other" viewpoint so they still appear
        # in the architecture document and count toward coverage — instead of vanishing.
        vp_key = req_type if req_type in VIEWPOINT_MAP else "other"
        views.setdefault(vp_key, [])
        if req["id"] not in views[vp_key]:
            views[vp_key].append(req["id"])
    return views


# ---------------------------------------------------------------------------
# 7.4.1 — analyze_requirements_architecture
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def analyze_requirements_architecture(
    project_id: str,
) -> str:
    """
    BABOK 7.4 — Automatically builds viewpoints from artifact types in the 5.1
    repository. Mapping: VIEWPOINT_MAP.

    Additionally:
    - Reads custom viewpoints from {project}_architecture.json (if any)
    - Builds a BG × viewpoints coverage matrix (if business_context from 7.3 exists)
    - Shows which artifact types are missing

    Args:
        project_id: Project identifier.

    Returns:
        A full picture of the requirements architecture: viewpoints, views, coverage matrix.
    """
    logger.info(f"analyze_requirements_architecture: project_id='{project_id}'")

    repo = _load_repo(project_id)
    all_reqs = repo.get("requirements", [])

    if not all_reqs:
        return (
            f"⚠️ The 5.1 repository for project `{project_id}` is empty or not found.\n\n"
            f"Create requirements via the 7.1 tools before working on architecture."
        )

    # Build views from the repository
    auto_views = _build_views_from_repo(repo)

    # Load existing architecture (for custom viewpoints)
    arch = _load_architecture(project_id)
    custom_viewpoints = {
        k: v for k, v in arch.get("viewpoints", {}).items()
        if not v.get("auto", True)
    }

    # Update automatic viewpoints in the architecture
    for vp_key, req_ids in auto_views.items():
        vp_meta = VIEWPOINT_MAP[vp_key]
        arch["viewpoints"][vp_key] = {
            "label": vp_meta["label"],
            "auto": True,
            "artifact_types": [vp_key],
            "audience": vp_meta["audience"],
        }
    arch["views"] = {**auto_views}

    # Add views for custom viewpoints (from architecture)
    for vp_key, vp_data in custom_viewpoints.items():
        arch["views"][vp_key] = vp_data.get("req_ids", [])

    _save_architecture(arch)

    # Statistics
    active_reqs = [r for r in all_reqs if r.get("type", "") not in SKIP_TYPES]
    total = len(active_reqs)
    # This line used to read "Total **active** req", which is a claim about STATUS made
    # by a filter that only ever looked at TYPE (re-review N-5). The count itself stays
    # as it is: the delivered document counts archived rows in `Total req` on purpose,
    # and excluding them here would buy one true word at the price of two tools
    # disagreeing about one project. So the word goes and the fact is stated instead.
    archived_count = sum(1 for r in active_reqs if _is_archived(r))
    archived_note = f" _({archived_count} archived in 5.2)_" if archived_count else ""
    in_viewpoints = sum(len(ids) for ids in auto_views.values())
    coverage_pct = round(in_viewpoints / total * 100, 1) if total > 0 else 0.0

    # Types missing from the repository
    all_auto_types = set(VIEWPOINT_MAP.keys())
    present_types = set(auto_views.keys())
    # `other` is an on-demand fallback bucket, not an expected viewpoint — never report it
    # as "missing" when there are no unmapped requirement types.
    missing_types = all_auto_types - present_types - {"other"}

    # Business context for the coverage matrix
    ctx = _load_context(project_id)
    goals = ctx.get("business_goals", []) if ctx else []

    lines = [
        f"<!-- BABOK 7.4 — Requirements Architecture | Project: {project_id} | {date.today()} -->",
        "",
        f"# 🏗️ Requirements architecture — {project_id}",
        "",
        f"**Date:** {date.today()}  ",
        f"**Total req:** {total}{archived_note}  ",
        f"**Covered by viewpoints:** {in_viewpoints} ({coverage_pct}%)",
        "",
        "---",
        "",
        "## Viewpoints",
        "",
    ]

    # Group by unique labels (DD and ERD → one "Data" viewpoint)
    seen_labels: dict = {}  # label → {artifact_types: [], req_ids: []}
    for vp_key, req_ids in auto_views.items():
        meta = VIEWPOINT_MAP[vp_key]
        label = meta["label"]
        if label not in seen_labels:
            seen_labels[label] = {
                "artifact_types": [],
                "req_ids": [],
                "audience": meta["audience"],
            }
        seen_labels[label]["artifact_types"].append(vp_key)
        seen_labels[label]["req_ids"].extend(req_ids)

    # Viewpoints table
    lines += [
        "| Viewpoint | Artifacts | Req count | Audience |",
        "|-----------|-----------|-----------|----------|",
    ]
    for label, data in seen_labels.items():
        types_str = ", ".join(f"`{t}`" for t in data["artifact_types"])
        req_count = len(data["req_ids"])
        icon = "✅" if req_count > 0 else "⚠️ empty"
        lines.append(
            f"| {label} | {types_str} | {req_count} {icon} | {data['audience']} |"
        )

    # Custom viewpoints
    if custom_viewpoints:
        lines += [
            "",
            "## Custom viewpoints",
            "",
            "| ID | Label | Req | Description |",
            "|----|-------|-----|-------------|",
        ]
        for vp_key, vp_data in custom_viewpoints.items():
            req_count = len(vp_data.get("req_ids", []))
            lines.append(
                f"| `{vp_key}` | {vp_data['label']} | {req_count} | "
                f"{vp_data.get('description', '—')[:60]} |"
            )

    # Details per viewpoint
    lines += [
        "",
        "## Viewpoint details",
        "",
    ]
    for label, data in seen_labels.items():
        req_ids = data["req_ids"]
        lines.append(f"### {label} ({len(req_ids)} req)")
        if req_ids:
            # Show up to 10 req, the rest as a counter
            preview = req_ids[:10]
            lines.append(f"{' '.join(f'`{i}`' for i in preview)}"
                         + (f" _+{len(req_ids) - 10} more_" if len(req_ids) > 10 else ""))
        else:
            lines.append("_No req of this type_")
        lines.append("")

    # Custom viewpoints details
    for vp_key, vp_data in custom_viewpoints.items():
        req_ids = vp_data.get("req_ids", [])
        lines.append(f"### {vp_data['label']} [custom] ({len(req_ids)} req)")
        if req_ids:
            preview = req_ids[:10]
            lines.append(f"{' '.join(f'`{i}`' for i in preview)}"
                         + (f" _+{len(req_ids) - 10} more_" if len(req_ids) > 10 else ""))
        lines.append("")

    # Missing types
    if missing_types:
        lines += [
            "## ⚠️ Missing artifact types",
            "",
            "> These viewpoints are empty — no artifacts of these types exist in the repository.",
            "",
        ]
        type_labels = {k: VIEWPOINT_MAP[k]["label"] for k in missing_types}
        for t, label in sorted(type_labels.items()):
            lines.append(f"- `{t}` → {label}")
        lines.append("")

    # Coverage matrix BG × viewpoints
    if goals:
        lines += [
            "## Coverage Matrix — Business goals × Viewpoints",
            "",
            "> Shows which viewpoints cover each business goal.",
            "",
        ]
        # Build: for each req, look at its viewpoint and links to BG
        from collections import defaultdict
        bg_to_viewpoints: dict = defaultdict(set)

        for req in all_reqs:
            req_id = req.get("id", "")
            req_type = req.get("type", "")
            if req_type in SKIP_TYPES:
                continue
            vp_key = req_type
            if vp_key not in VIEWPOINT_MAP:
                continue
            # BFS to nodes of type 'business'
            linked = _get_linked_ids(repo, req_id)
            for linked_id in linked:
                linked_req = _find_req(repo, linked_id)
                if linked_req and linked_req.get("type") in BUSINESS_NODE_TYPES:
                    bg_to_viewpoints[linked_id].add(VIEWPOINT_MAP[vp_key]["label"])

        vp_labels = sorted(set(v["label"] for v in VIEWPOINT_MAP.values()))
        header = "| BG | Title | " + " | ".join(vp_labels) + " |"
        sep = "|----|-------| " + " | ".join(["---"] * len(vp_labels)) + " |"
        lines += [header, sep]

        for g in goals:
            bg_id = g["id"]
            covered_vps = bg_to_viewpoints.get(bg_id, set())
            cells = [
                "✅" if label in covered_vps else "—"
                for label in vp_labels
            ]
            lines.append(f"| `{bg_id}` | {g['title'][:35]} | " + " | ".join(cells) + " |")
        lines.append("")

    lines += [
        "---",
        "",
        "## Next steps",
        "",
    ]

    if missing_types:
        lines.append(
            f"1. Create the missing artifacts ({', '.join(f'`{t}`' for t in sorted(missing_types))}) "
            f"via the 7.1 tools, or justify their absence."
        )
    lines += [
        "2. `check_architecture_gaps` — check for architecture gaps.",
        "3. If needed: `add_custom_viewpoint` for regulatory/specific requirements.",
        f"4. `save_architecture_snapshot(project_id='{project_id}', version='v1.0')` — record it.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.4.2 — add_custom_viewpoint
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def add_custom_viewpoint(
    project_id: str,
    viewpoint_id: str,
    label: str,
    req_ids_json: str,
    description: str = "",
    stakeholder_roles: str = "",
) -> str:
    """
    BABOK 7.4 — Adds a custom viewpoint bound to req_ids.
    custom viewpoints are defined via req_ids (not via artifact types).

    Custom viewpoints are needed for specific perspectives: Security, Audit/Compliance,
    Data migration, Integrations — anything not covered by the standard five viewpoints.

    Args:
        project_id:        Project identifier.
        viewpoint_id:      Unique identifier (lowercase, no spaces): security, audit, migration.
        label:             Viewpoint label: "Security and access", "Audit and compliance".
        req_ids_json:      JSON list of requirement IDs: '["NFR-003", "FR-015", "BR-002"]'.
                           All IDs must exist in the 5.1 repository.
        description:       Description: what this viewpoint represents (optional).
        stakeholder_roles: Who this viewpoint is for: "Security architect, CISO" (optional).

    Returns:
        Confirmation with the composition of the custom viewpoint.
    """
    logger.info(f"add_custom_viewpoint: project_id='{project_id}', viewpoint_id='{viewpoint_id}'")

    # Validate viewpoint_id
    viewpoint_id = viewpoint_id.lower().strip()
    if not viewpoint_id or " " in viewpoint_id:
        return (
            f"❌ viewpoint_id must be lowercase with no spaces: 'security', 'audit', 'migration'.\n"
            f"Got: '{viewpoint_id}'"
        )

    if viewpoint_id in VIEWPOINT_MAP:
        return (
            f"❌ viewpoint_id '{viewpoint_id}' conflicts with a standard artifact type.\n"
            f"Use a different name, e.g.: 'security', 'audit', 'migration'."
        )

    if not label.strip():
        return "❌ label cannot be empty — provide a viewpoint label."

    # Parse req_ids
    try:
        req_ids_list = json.loads(req_ids_json)
        if not isinstance(req_ids_list, list) or not req_ids_list:
            raise ValueError("The list must not be empty")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Failed to parse req_ids_json: {e}\n\n"
            f"Expected a non-empty JSON list: '[\"NFR-003\", \"FR-015\"]'"
        )

    # Validation: all req must exist in the 5.1 repository (ADR-036)
    repo = _load_repo(project_id)
    repo_ids = {r["id"] for r in repo.get("requirements", [])}

    not_found = [rid for rid in req_ids_list if rid not in repo_ids]
    if not_found:
        return (
            f"❌ The following req_ids were not found in the 5.1 repository of project `{project_id}`:\n"
            f"{', '.join(f'`{i}`' for i in not_found)}\n\n"
            f"Create the req via the 7.1 tools or fix the IDs."
        )

    # Save
    arch = _load_architecture(project_id)

    is_update = viewpoint_id in arch.get("viewpoints", {}) and not arch["viewpoints"][viewpoint_id].get("auto", True)

    arch["viewpoints"][viewpoint_id] = {
        "label": label,
        "auto": False,
        "req_ids": req_ids_list,
        "description": description,
        "stakeholder_roles": stakeholder_roles,
        "created": str(date.today()),
    }
    # Update views
    arch["views"][viewpoint_id] = req_ids_list

    _save_architecture(arch)

    # Req details
    req_details = []
    for rid in req_ids_list:
        req = _find_req(repo, rid)
        if req:
            req_details.append(f"- `{rid}` ({req.get('type', '?')}) — {req.get('title', '')}")

    action = "updated" if is_update else "created"
    lines = [
        f"✅ Custom viewpoint **{action}**: `{viewpoint_id}`",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| ID | `{viewpoint_id}` |",
        f"| Label | {label} |",
        f"| Req | {len(req_ids_list)} |",
        f"| Audience | {stakeholder_roles or '—'} |",
        f"| Date | {date.today()} |",
    ]

    if description:
        lines += [
            "",
            f"**Description:** {description}",
        ]

    lines += [
        "",
        "**Requirements in this viewpoint:**",
        "",
    ]
    lines.extend(req_details)

    lines += [
        "",
        "---",
        "",
        "**Next step:**",
        f"`check_architecture_gaps(project_id='{project_id}')` — check gaps taking the new viewpoint into account.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.4 — declare_stakeholder_interest (ADR-098)
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def declare_stakeholder_interest(
    project_id: str,
    stakeholder: str,
    req_ids_json: str,
    note: str = "",
    remove: bool = False,
) -> str:
    """
    BABOK 7.4 — Declares that a stakeholder's interests are touched by requirements.

    This is the ONE relation the BA states by hand. It is deliberately NOT
    the same thing as two facts the platform already holds elsewhere:
      - `owner` (written by 7.1) — who is answerable for the WORDING of a requirement;
      - RACI (written by 5.5) — someone's role in a DECISION on an approval package.
    Both are read as evidence by `check_architecture_gaps` and by the architecture
    document, and NEITHER is copied here: a stored copy goes stale the moment its
    owner changes it.

    Repeat calls MERGE. Removal is explicit only (`remove=True`), the way 5.1's
    `add_trace_link` does it, and both directions are written to the repository
    history.

    A TYPE is refused, a STATUS is not. The 5.1 graph also holds risks (6.3), business
    goals (6.2), change requests (5.4) and test cases; none of them is a requirement, so
    an id naming one is refused BY NAME rather than skipped in silence — accepting it
    would let a business goal silence a coverage gap and would print an id the rest of
    the document does not count. An ARCHIVED requirement (deprecated / superseded /
    retired in 5.2) is a stage rather than a category: the declaration is accepted, with
    a warning that the coverage check will not read it as live representation.

    Args:
        project_id:   Project identifier.
        stakeholder:  A name OR a role — whichever the registry knows ("Ivan Petrov",
                      "Product Owner"). Both resolve to the same person.
        req_ids_json: JSON array of requirement IDs: '["FR-001", "FR-002"]'.
        note:         Why their interests are touched (optional, stored per entry).
                      PRINTED in the Architecture Document under the requirement it
                      belongs to — it is the one place a sponsor reads the "why" in the
                      analyst's own words, so write it for that reader.
        remove:       True — withdraw the declaration from these requirements.

    Returns:
        What changed, in counts, plus how the name compared against the 4.2 registry.
    """
    logger.info(
        f"declare_stakeholder_interest: project_id='{project_id}', "
        f"stakeholder='{stakeholder}', remove={remove}"
    )

    name = str(stakeholder or "").strip()
    if not reg_norm(name):
        return (
            "❌ `stakeholder` cannot be empty — give a name or a role, "
            "for example: `Ivan Petrov` or `Product Owner`."
        )

    req_ids, error = parse_json_str_list(
        req_ids_json, "req_ids_json", required=True, example='["FR-001", "FR-002"]'
    )
    if error:
        return error

    repo = _load_repo(project_id)
    all_reqs = repo.get("requirements", [])
    if not all_reqs:
        return (
            f"⚠️ The 5.1 repository for project `{project_id}` is empty — "
            f"nothing to declare interest in.\n"
            f"First create requirements via the 7.1 tools."
        )

    in_graph = {r["id"]: r for r in all_reqs
                if isinstance(r, dict) and isinstance(r.get("id"), str)}
    by_id = {rid: r for rid, r in in_graph.items() if _is_requirement(r)}
    unknown = [rid for rid in req_ids if rid not in in_graph]
    # In the graph, but NOT a requirement. Refused by NAME rather than skipped: a
    # silent skip would answer "declared on 0 requirement(s)" without ever saying
    # which id was dropped or why — the defect class this branch already fixed twice.
    # The distinction from an ARCHIVED requirement is deliberate: a type says what a
    # node IS (a risk is not a requirement, so recording the tie would be a lie about
    # what happened), a status says what STAGE it is at (a deprecated requirement is
    # still a requirement, so that call is accepted with a warning).
    non_reqs = [rid for rid in req_ids if rid in in_graph and rid not in by_id]
    if unknown or non_reqs:
        # Refused as a whole, so a partial write cannot leave the BA guessing which
        # half landed. The vocabulary here is CLOSED — it is this project's own graph.
        known = ", ".join(f"`{rid}`" for rid in sorted(by_id)[:20])
        more = "" if len(by_id) <= 20 else f" (+{len(by_id) - 20} more)"
        problems = []
        if unknown:
            problems.append(
                f"❌ Not in repository 5.1: {', '.join(f'`{u}`' for u in unknown)}."
            )
        if non_reqs:
            named = ", ".join(
                f"`{rid}` is a `{in_graph[rid].get('type') or '?'}` node"
                for rid in non_reqs
            )
            problems.append(
                f"❌ Not requirements: {named}.\n"
                f"   7.4 records whose interests a REQUIREMENT touches. Risks (6.3), "
                f"business goals (6.2), change requests (5.4), the 6.4 solution scope "
                f"and test cases share the 5.1 graph but are not requirements — no "
                f"other 7.4 count includes them either."
            )
        return "\n".join(problems + [
            f"   Existing requirements: {known or '—'}{more}",
            f"   Nothing was written — fix the IDs and call again.",
        ])

    today = str(date.today())
    key = reg_norm(name)
    changed, skipped = [], []
    # A `stakeholders` value that is not a list cannot be merged into — it is replaced.
    # That is the only honest option (there is no way to append a declaration to a dict
    # somebody hand-edited), but it used to happen in SILENCE, against the promise
    # "never silently erases" printed in both SKILL.md and the user guide. Named in the
    # reply and kept in the history, so the sentence becomes true (branch review A-7).
    replaced: dict = {}

    for rid in dict.fromkeys(req_ids):          # order kept, duplicates in ONE call collapsed
        req = by_id[rid]
        current = req.get("stakeholders")
        if not isinstance(current, list):
            if current is not None:
                replaced[rid] = current
            current = []
        present = key in {reg_norm(_concern_name(e)) for e in current}

        if remove:
            if present:
                req["stakeholders"] = [
                    e for e in current if reg_norm(_concern_name(e)) != key
                ]
                changed.append(rid)
            else:
                skipped.append(rid)
        else:
            if present:
                skipped.append(rid)
            else:
                entry = {"name": name, "declared": today}
                if note:
                    entry["note"] = note
                req["stakeholders"] = current + [entry]
                changed.append(rid)

    # Only the requirements actually WRITTEN can have lost anything: a `remove` that
    # matched nothing never reassigns the field, so the stored value is untouched and
    # claiming it was replaced would be its own false statement.
    replaced = {rid: value for rid, value in replaced.items() if rid in changed}

    if changed:
        # Normalised by TYPE before appending, the way `load_stakeholder_registry`
        # does it for the same field and for the same reason. `setdefault` only
        # protects against a MISSING key: on a stored `"history": {}` the append
        # raised AttributeError, which escaped `guard_artifact_errors` — and it
        # raised BEFORE `_save_repo`, so the declaration the BA had just made
        # disappeared from memory as well as from the file (branch review R-3).
        if not isinstance(repo.get("history"), list):
            repo["history"] = []
        entry = {
            "action": "stakeholder_interest_removed" if remove
                      else "stakeholder_interest_declared",
            "stakeholder": name,
            "req_ids": changed,
            "source": "7.4_architecture",
            "date": today,
        }
        if replaced:
            # Nothing is ever deleted in this project — a discarded hand-edit is data
            # too, and the history is where it survives.
            entry["replaced"] = replaced
        repo["history"].append(entry)
        _save_repo(repo, project_id)

    verb = "removed from" if remove else "declared on"
    lines = [
        f"✅ `{name}` — interest **{verb} {len(changed)} requirement(s)**"
        + (f": {', '.join(f'`{r}`' for r in changed)}" if changed else "."),
    ]
    if skipped:
        state = "was not declared on" if remove else "already declared on"
        lines.append(
            f"   ℹ️ {state} {len(skipped)}: {', '.join(f'`{r}`' for r in skipped)}"
        )

    if replaced:
        lines += [
            "",
            f"⚠️ Replaced, not merged: {', '.join(f'`{r}`' for r in sorted(replaced))} "
            f"held a `stakeholders` value that is not a list of declarations, so it "
            f"could not be appended to. The previous value is preserved under "
            f"`replaced` in the repository history.",
        ]

    # A STATUS is not a TYPE. A deprecated requirement is still a requirement, so the
    # call is ACCEPTED — refusing it (the treatment risks and business goals get) would
    # be wrong, nothing was misrepresented. But a tie to something 5.2 has retired is
    # not live coverage, and the BA who is about to read "declared on 1 requirement"
    # deserves to know which of them the gap check will not count (branch review B-2).
    archived_targets = sorted({rid for rid in req_ids
                               if rid in by_id and _is_archived(by_id[rid])})
    if archived_targets and not remove:
        lines += [
            "",
            f"⚠️ Archived in 5.2: {', '.join(f'`{r}`' for r in archived_targets)} "
            f"(deprecated / superseded / retired). The declaration was recorded — an "
            f"archived requirement is still a requirement — but the coverage check "
            f"does not count it as live representation.",
        ]

    status = registry_party_status(project_id, name)
    if status == PARTY_NOT_IN_REGISTRY:
        lines += [
            "",
            f"⚠️ `{name}` is not in the stakeholder registry (4.2). The declaration was "
            f"recorded anyway — the registry is a living document. Add them with 4.2 "
            f"`update_stakeholder_registry` so the coverage check can see them.",
        ]
    elif status == PARTY_UNBRIDGEABLE:
        lines += [
            "",
            f"⚠️ There is no stakeholder registry for `{project_id}`, so this name could "
            f"not be checked against anything. Create it via the 3.2 or 4.2 tools.",
        ]

    lines += [
        "",
        f"Next: `check_architecture_gaps(project_id='{project_id}')` — see which "
        f"stakeholders still have no recorded tie to any requirement.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.4.3 — check_architecture_gaps
# ---------------------------------------------------------------------------

def _compute_gaps(project_id: str, repo: dict, arch: dict) -> tuple:
    """(critical, warning, info) — the gap analysis, computed from what is on disk NOW.

    Lives in ONE function because TWO tools state its result: `check_architecture_gaps`
    prints it, and `save_architecture_snapshot` puts it in the signed document. The
    snapshot used to read `arch["gaps"]`, frozen by whenever the check last ran — and
    the workflow this chapter's own SKILL.md teaches is "check gaps → declare the
    interests you know → save the snapshot", so the ordinary route produced a document
    whose concerns section said a stakeholder was tied to `FR-001` and whose gap block,
    ten lines below, said the same stakeholder had no tie to anything (branch review
    A-1). Both halves were computed correctly; only one of them was computed now.

    Comparing timestamps instead would not have caught it: both files stamp `updated`
    as a DATE, and the whole route runs inside a single session.
    """
    all_reqs = repo.get("requirements", [])

    # Build current views (auto + custom)
    auto_views = _build_views_from_repo(repo)
    views = {**auto_views}
    for vp_key, vp_data in arch.get("viewpoints", {}).items():
        if not vp_data.get("auto", True):
            views[vp_key] = vp_data.get("req_ids", [])

    gaps_critical: list = []
    gaps_warning: list = []
    gaps_info: list = []

    # ------------------------------------------------------------------
    # LEVEL 1: Coverage matrix
    # ------------------------------------------------------------------

    # 1a. Empty viewpoints (info)
    for vp_key, req_ids in views.items():
        if not req_ids:
            label = arch["viewpoints"].get(vp_key, {}).get("label") or \
                    VIEWPOINT_MAP.get(vp_key, {}).get("label", vp_key)
            gaps_info.append({
                "type": "empty_viewpoint",
                "viewpoint": vp_key,
                "label": label,
                "message": f"Viewpoint '{label}' (`{vp_key}`) is empty — no req of this type.",
            })

    # 1b. Stakeholder without representation — ADR-035
    stakeholders_data = _load_stakeholders(project_id)
    if stakeholders_data is None:
        # Graceful: warn, don't fail
        gaps_info.append({
            "type": "no_stakeholder_registry",
            "message": (
                f"Stakeholder registry not found (`{project_id}_stakeholder_registry.json`). "
                f"Stakeholder coverage check skipped. "
                f"Create the registry via the 4.2 tools."
            ),
        })
        all_stakeholders = []
    else:
        raw = stakeholders_data.get("stakeholders")
        all_stakeholders = raw if isinstance(raw, list) else []
        # A registry that exists but holds nobody identifiable used to produce a
        # report of 🔴 0 / 🟡 0 and not one note: the "not found" note above fires
        # only on a missing FILE, so the sponsor read a clean verdict on a project
        # where no person had been checked against anything. An empty registry is a
        # legitimate early state, not a clean bill of health (branch review B-1).
        if not [s for s in all_stakeholders if registry_labels(s)]:
            gaps_info.append({
                "type": "stakeholder_registry_unusable",
                "message": (
                    f"The stakeholder registry for `{project_id}` was read, but holds "
                    f"nobody identifiable — no row carries a name or a role. Nobody was "
                    f"checked for representation, so this report says nothing about "
                    f"stakeholder coverage. Record the people via the 4.2 tools."
                ),
            })

    if all_stakeholders:
        # ADR-098: the verdict rests on RECORDED facts, each named in the message.
        # Three of them are evidence — a declaration (7.4), the owner field (7.1), a
        # vote on this requirement (5.5) — and evidence is matched EXACTLY (fix
        # review round 1: matching evidence by substring silently represented "Priya"
        # against a registry row "Priya Nair", which is a coincidence, not a fact).
        # A partial match — a shared word in a requirement TITLE, or a shared
        # fragment of a name recorded as evidence for some OTHER tie — is the
        # heuristic this module used to run alone before ADR-098. It is kept, so that
        # no existing project acquires a NEW critical on upgrade, and demoted to a
        # warning that names its own weakness.
        evidence = _stakeholder_evidence(project_id, repo)

        # The coincidence pools. Built by the SAME helper the delivered document
        # uses, so the report and the document cannot reach different conclusions
        # about the same person — two copies of this rule would drift, and the drift
        # would surface as one page contradicting another in front of a sponsor.
        title_words, outside_pool, name_pool = _heuristic_pools(all_reqs, evidence)

        for sh in all_stakeholders:
            # The guard comes FIRST. `registry_labels` is safe on any value, but the
            # line that used to sit between them was not: a registry row stored as a
            # bare string ("Ivan Petrov" instead of {"name": ...}) reached
            # `sh.get("name")` and took the whole tool down with AttributeError,
            # while `_concern_lines` — which filters by isinstance first — rendered
            # the same file without complaint (branch review A-2).
            labels = registry_labels(sh)
            if not labels:
                continue
            # Identify by name, else role: neither producer of the registry (3.2
            # seeding, 4.2 elicitation) writes an `id`, so quoting it rendered an
            # empty pair of backticks on every one of these gaps.
            who = _md_label(sh.get("name") or sh.get("role") or "—")

            ties = _ties_for_labels(labels, evidence)
            if any(not t["archived"] for t in ties):
                continue
            if ties:
                # Every recorded tie points at a requirement 5.2 has archived. That is
                # its own finding and its own message: "no tie" would be false (the BA
                # recorded these) and silence would be worse (nothing live covers this
                # person). A WARNING, never a critical — decision 6 forbids handing an
                # existing project a new red gap on upgrade, and this state used to be
                # silent (branch review B-2).
                archived_ids = sorted({t["req_id"] for t in ties})
                gaps_warning.append({
                    "type": "stakeholder_only_archived",
                    "stakeholder_id": sh.get("id", ""),
                    "stakeholder_name": sh.get("name", ""),
                    "message": (
                        f"Stakeholder `{who}` has ties only to archived requirements "
                        f"({', '.join(f'`{r}`' for r in archived_ids)}) — deprecated, "
                        f"superseded or retired in 5.2. Nothing live covers their "
                        f"interests. Re-declare against the replacement with "
                        f"`declare_stakeholder_interest`, or confirm they are out of "
                        f"scope now."
                    ),
                })
                continue

            # WHICH SIDE reaches this person is decided once, for both surfaces. This
            # report is then free to be more specific WITHIN the requirement side —
            # it has separate wording for a title word and for a partial name — but
            # it may not disagree with the document about whether anything on the
            # requirement side matched at all (re-review RR-1).
            kind = _coincidence_kind(labels, title_words, name_pool, outside_pool)
            title_hit = _heuristic_hit(labels, title_words)
            if kind == COINCIDENCE_REQUIREMENT and title_hit:
                gaps_warning.append({
                    "type": "stakeholder_heuristic_only",
                    "stakeholder_id": sh.get("id", ""),
                    "stakeholder_name": sh.get("name", ""),
                    "message": (
                        f"Stakeholder `{who}` is reachable only by a word in a "
                        f"requirement title (heuristic) — no declared interest, no "
                        f"requirement owned, no 5.5 approval decision. Confirm with "
                        f"`declare_stakeholder_interest`."
                    ),
                })
            elif kind == COINCIDENCE_REQUIREMENT:
                gaps_warning.append({
                    "type": "stakeholder_heuristic_only",
                    "stakeholder_id": sh.get("id", ""),
                    "stakeholder_name": sh.get("name", ""),
                    "message": (
                        f"Stakeholder `{who}` is reachable only by a partial name "
                        f"match (heuristic) — no exact declared interest, no "
                        f"requirement owned under this exact name, no 5.5 approval "
                        f"decision. Confirm with `declare_stakeholder_interest`."
                    ),
                })
            elif kind == COINCIDENCE_OUTSIDE:
                # Everything tying this person to the project sits OUTSIDE the
                # requirements: a risk title naming their role, a business goal they
                # were once declared on, a change request they own. Calling that "a
                # requirement title" was the false statement R-1 objected to; dropping
                # the case was the new critical N-2 measured against `afe5961`. Naming
                # the place avoids both, and tells the BA where to go look.
                gaps_warning.append({
                    "type": "stakeholder_outside_requirements",
                    "stakeholder_id": sh.get("id", ""),
                    "stakeholder_name": sh.get("name", ""),
                    "message": (
                        f"Stakeholder `{who}` is traceable only OUTSIDE the "
                        f"requirements (heuristic) — a risk (6.3), a business goal "
                        f"(6.2) or a change request (5.4) carries their name or a "
                        f"word of it. Nothing among the requirements does: no "
                        f"declared interest, no requirement owned, no 5.5 approval "
                        f"decision. Record what actually holds with "
                        f"`declare_stakeholder_interest`."
                    ),
                })
            else:
                gaps_critical.append({
                    "type": "stakeholder_no_view",
                    "stakeholder_id": sh.get("id", ""),
                    "stakeholder_name": sh.get("name", ""),
                    # Assembled from CONCERN_EVIDENCE, in its order, so renaming a
                    # source cannot leave this sentence quoting the old name (A-6).
                    "message": (
                        f"Stakeholder `{who}` has no recorded tie to any requirement: "
                        + ", ".join(f"no {CONCERN_LABELS[s]}" for s in CONCERN_EVIDENCE)
                        + f", and no {CONCERN_LABELS[CONCERN_TITLE]}. "
                        f"Their interests may be uncovered — record what you know with "
                        f"`declare_stakeholder_interest`."
                    ),
                })

    # 1c. BG without viewpoint coverage (warning)
    ctx = _load_context(project_id)
    goals = ctx.get("business_goals", []) if ctx else []

    if goals:
        # For each BG, check whether it has at least one link in the graph
        goal_ids = {g["id"] for g in goals}
        bg_in_graph = {r["id"] for r in all_reqs if r.get("type") in BUSINESS_NODE_TYPES}
        for g in goals:
            if g["id"] not in bg_in_graph:
                gaps_warning.append({
                    "type": "bg_not_in_graph",
                    "bg_id": g["id"],
                    "title": g["title"],
                    "message": (
                        f"Business goal `{g['id']}` ('{g['title'][:50]}') "
                        f"is not represented as a node in the 5.1 graph. "
                        f"Register it via 6.2 `define_goals_and_objectives` "
                        f"(register_in_traceability=True), or add the node directly "
                        f"with 5.1 `init_traceability_repo`."
                    ),
                })

    # ------------------------------------------------------------------
    # LEVEL 2: Semantic gaps (uses the 5.1 graph)
    # ------------------------------------------------------------------

    # Archived requirements leave this level entirely, and that cuts BOTH ways on
    # purpose — the same rule B-2 established one level up, applied consistently:
    #   as a SUBJECT: "write a use case for FR-003" is work the analyst must not be
    #     sent to do about something 5.2 retired last month;
    #   as a TARGET: a live UC whose only business process was deprecated is hanging,
    #     and calling it covered would be the exact "archived counts as coverage"
    #     defect B-2 fixed, merely relocated to level 2.
    # The second half can turn silence into a WARNING on an existing project, which
    # decision 6 permits (only silence → critical is forbidden), and it is pinned by
    # `test_a_live_use_case_left_with_only_an_archived_process_is_a_gap`.
    # 7.2 (`:1413`) and 7.3 (`:1308`) already skip these three statuses in their
    # audits — 7.4 was the last chapter reading them as live.
    reqs_by_type: dict = {}
    for req in all_reqs:
        t = req.get("type", "")
        if t not in SKIP_TYPES and not _is_archived(req):
            reqs_by_type.setdefault(t, []).append(req)

    bp_ids = {r["id"] for r in reqs_by_type.get("business_process", [])}
    fr_ids = {r["id"] for r in reqs_by_type.get("functional", [])}
    uc_ids = {r["id"] for r in reqs_by_type.get("use_case", [])}
    us_ids = {r["id"] for r in reqs_by_type.get("user_story", [])}
    nfr_ids = {r["id"] for r in reqs_by_type.get("non_functional", [])}

    # 2a. UC without a corresponding BP (warning)
    for req in reqs_by_type.get("use_case", []):
        uc_id = req["id"]
        linked = _get_linked_ids(repo, uc_id)
        has_bp = bool(linked & bp_ids)
        if not has_bp:
            gaps_warning.append({
                "type": "uc_without_bp",
                "req_id": uc_id,
                "title": req.get("title", ""),
                "message": (
                    f"`{uc_id}` — Use Case '{req.get('title', '')[:50]}' "
                    f"is not linked to any Business Process. "
                    f"The user interacts, but the process is not described."
                ),
            })

    # 2b. NFR without a link to an FR (warning)
    for req in reqs_by_type.get("non_functional", []):
        nfr_id = req["id"]
        linked = _get_linked_ids(repo, nfr_id)
        has_fr = bool(linked & fr_ids)
        if not has_fr:
            gaps_warning.append({
                "type": "nfr_without_fr",
                "req_id": nfr_id,
                "title": req.get("title", ""),
                "message": (
                    f"`{nfr_id}` — NFR '{req.get('title', '')[:50]}' "
                    f"is not linked to any FR. "
                    f"The non-functional constraint is left hanging."
                ),
            })

    # 2c. FR without a UC or US (info)
    for req in reqs_by_type.get("functional", []):
        fr_id = req["id"]
        linked = _get_linked_ids(repo, fr_id)
        has_uc_or_us = bool(linked & (uc_ids | us_ids))
        if not has_uc_or_us:
            gaps_info.append({
                "type": "fr_without_scenario",
                "req_id": fr_id,
                "title": req.get("title", ""),
                "message": (
                    f"`{fr_id}` — FR '{req.get('title', '')[:50]}' "
                    f"is not linked to a UC or US. "
                    f"The function exists, but the usage scenario is not documented."
                ),
            })

    return gaps_critical, gaps_warning, gaps_info


GAP_LIST_CAP = 10


def _render_gap_section(gaps: list, cap: int = GAP_LIST_CAP) -> list:
    """Gap lines, grouped by kind, with a CEILING on how many of each are listed.

    On 105 requirements the info section was 60 numbered items — a document the reader
    scrolls past rather than reads. The first answer to that was to collapse each run
    into one sentence taken from its first member, and it could not be made true: no
    gap type here has an explanation that is genuinely shared. Every message names its
    own subject and its own specifics, so the collapsed entry described the first use
    case and attributed it to all of them, captioned people as "requirement(s)", and
    printed `?` for every gap whose id lives under `stakeholder_name` rather than
    `req_id`.

    A ceiling solves the same length problem without inventing a sentence that fits
    nobody: each gap keeps its own message, the list is cut, and the count never is —
    the remainder is stated (invariant: truncate the list, never the number).
    """
    out: list = []
    by_type: dict = {}
    for gap in gaps:
        by_type.setdefault(gap.get("type", "other"), []).append(gap)

    n = 0
    for _gap_type, group in by_type.items():
        for gap in group[:cap]:
            n += 1
            out += [f"**{n}.** {gap['message']}", ""]
        if len(group) > cap:
            out += [
                f"   _+{len(group) - cap} more of the same kind ({len(group)} in "
                f"total). They are all in the architecture file._",
                "",
            ]
    return out


def _gaps_as_messages(gaps_critical: list, gaps_warning: list, gaps_info: list) -> dict:
    """The `gaps` block as it is stored on the architecture file — messages only."""
    return {
        "critical": [g["message"] for g in gaps_critical],
        "warning": [g["message"] for g in gaps_warning],
        "info": [g["message"] for g in gaps_info],
    }


@mcp.tool()
@guard_artifact_errors
def check_architecture_gaps(
    project_id: str,
) -> str:
    """
    BABOK 7.4 — Checks the requirements architecture for gaps at two levels.

    Level 1 — Coverage matrix:
      - Stakeholder with no recorded tie to any requirement → critical (
        declared interest 7.4, owner 7.1, approval decision 5.5 — a title-word match
        alone is a warning, not a verdict)
      - Stakeholder reachable only by a title-word match → warning
      - Stakeholder traceable only OUTSIDE the requirements — a risk (6.3), goal (6.2)
        or change request (5.4) carries their name or a word of it → warning. Never a
        critical: decision 6 forbids handing an existing project a new red gap, and
        the earlier bucket spanned the whole graph, so these were silent before
      - Stakeholder whose every tie points at a requirement archived in 5.2
        (deprecated / superseded / retired) → warning: a stage is not a category, so
        the tie is real, but nothing live covers that person
      - BG without viewpoint coverage (from business_context 7.3) → warning
      - Empty viewpoint (a viewpoint with no req) → info
      - Registry read but holding nobody identifiable → info: "nobody was checked" and
        "everybody is covered" must never render as the same clean sheet

    Level 2 — Semantic gaps (uses the 5.1 link graph):
      - UC without a corresponding BP → warning
      - NFR without a link to an FR → warning
      - FR without a UC or US → info

    Args:
        project_id: Project identifier.

    Returns:
        A gap report with severity: critical / warning / info.
        Severity does not block — it only informs (project pattern).
    """
    logger.info(f"check_architecture_gaps: project_id='{project_id}'")

    repo = _load_repo(project_id)
    all_reqs = repo.get("requirements", [])

    if not all_reqs:
        return (
            f"⚠️ The 5.1 repository for project `{project_id}` is empty.\n\n"
            f"First create requirements via the 7.1 tools."
        )

    arch = _load_architecture(project_id)
    gaps_critical, gaps_warning, gaps_info = _compute_gaps(project_id, repo, arch)

    # Save gaps to the architecture
    arch["gaps"] = _gaps_as_messages(gaps_critical, gaps_warning, gaps_info)
    _save_architecture(arch)

    # ------------------------------------------------------------------
    # Build the report
    # ------------------------------------------------------------------

    total_gaps = len(gaps_critical) + len(gaps_warning) + len(gaps_info)
    verdict = "✅ No critical gaps" if not gaps_critical else f"❌ {len(gaps_critical)} critical gap(s)"

    lines = [
        f"<!-- BABOK 7.4 — Architecture Gaps | Project: {project_id} | {date.today()} -->",
        "",
        f"# 🔍 Architecture gaps — {project_id}",
        "",
        f"**Date:** {date.today()}  ",
        f"**Verdict:** {verdict}",
        "",
        "| Severity | Count |",
        "|----------|-------|",
        f"| 🔴 Critical | {len(gaps_critical)} |",
        f"| 🟡 Warning | {len(gaps_warning)} |",
        f"| ℹ️ Info | {len(gaps_info)} |",
        f"| **Total** | **{total_gaps}** |",
        "",
        "> ⚠️ **Project pattern:** severity does not block work — it only informs. "
        "> Resolve critical gaps before handing off to 7.5.",
        "",
        "---",
        "",
    ]

    if gaps_critical:
        lines += [
            "## 🔴 Critical — require resolution",
            "",
        ]
        lines += _render_gap_section(gaps_critical)

    if gaps_warning:
        lines += [
            "## 🟡 Warning — worth reviewing",
            "",
        ]
        lines += _render_gap_section(gaps_warning)

    if gaps_info:
        lines += [
            "## ℹ️ Info — for completeness",
            "",
        ]
        lines += _render_gap_section(gaps_info)

    if total_gaps == 0:
        lines += [
            "## ✅ No gaps found",
            "",
            "The requirements architecture looks complete.",
            "You can record a snapshot and hand off to 7.5.",
            "",
        ]

    # Note about false positives
    if any(g["type"] in ("uc_without_bp", "nfr_without_fr", "fr_without_scenario")
           for g in gaps_warning + gaps_info):
        lines += [
            "---",
            "",
            "> ℹ️ **About false positives (level 2):** gaps such as UC without BP, "
            "> NFR without FR, FR without UC depend on how complete the links in the 5.1 "
            "> repository are. If links were added rarely — some signals may be false. "
            "> Verify via `run_impact_analysis` in 5.1.",
            "",
        ]

    lines += [
        "---",
        "",
        "## Next steps",
        "",
        "1. Resolve **critical** gaps: create missing req (7.1) or add traceability (5.1).",
        "2. Review **warning** gaps — especially NFR without FR and UC without BP.",
        f"3. Once resolved: `save_architecture_snapshot(project_id='{project_id}', version='v1.0')`",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.4.4 — save_architecture_snapshot
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def save_architecture_snapshot(
    project_id: str,
    version: str,
    notes: str = "",
    author: str = "",
) -> str:
    """
    BABOK 7.4 — Records a snapshot of the requirements architecture.
    snapshots accumulate in {project}_architecture.json — history is not overwritten.

    Generates an Architecture Document (Markdown) via save_artifact.
    The document is handed off to 4.4 (communication with stakeholders) and 7.5 (design options).

    The gap block inside that document is RECOMPUTED here, not read back from the last
    `check_architecture_gaps`. The workflow deliberately puts `declare_stakeholder_interest`
    between the two, so a stored block would report gaps the BA had just resolved —
    directly beneath a concerns section, computed live, saying the opposite about the
    same person. A project that never ran the check gets a real table rather than zeros.

    Args:
        project_id: Project identifier.
        version:    Snapshot version: v1.0, v1.1, v2.0.
        notes:      Notes for the snapshot (what changed, context).
        author:     Snapshot author (optional).

    Returns:
        The Architecture Document in Markdown + a save confirmation.
    """
    logger.info(f"save_architecture_snapshot: project_id='{project_id}', version='{version}'")

    if not version.strip():
        return "❌ version cannot be empty. Use the format: v1.0, v1.1, v2.0"

    repo = _load_repo(project_id)
    all_reqs = repo.get("requirements", [])

    if not all_reqs:
        return (
            f"⚠️ The 5.1 repository is empty — nothing to record.\n"
            f"First call `analyze_requirements_architecture` to analyze."
        )

    arch = _load_architecture(project_id)

    # Check for duplicate version FIRST. Everything below mutates `arch` — the
    # viewpoints, the views and (since A-1) the recomputed gaps — and this early
    # return must leave the stored file exactly as it found it, or the BA would be
    # told nothing was recorded while the gap block had already been rewritten.
    existing_versions = [s["version"] for s in arch.get("snapshots", [])]
    if version in existing_versions:
        return (
            f"⚠️ Version `{version}` already exists in the snapshots of project `{project_id}`.\n"
            f"Existing versions: {', '.join(existing_versions)}\n"
            f"Use the next version, for example: "
            f"`{version.replace('v', 'v').split('.')[0]}.{int(version.split('.')[-1]) + 1}`"
        )

    # Build current views
    auto_views = _build_views_from_repo(repo)
    all_views = {**auto_views}
    custom_viewpoints = {}
    for vp_key, vp_data in arch.get("viewpoints", {}).items():
        if not vp_data.get("auto", True):
            all_views[vp_key] = vp_data.get("req_ids", [])
            custom_viewpoints[vp_key] = vp_data

    # Update arch before the snapshot
    for vp_key, req_ids in auto_views.items():
        vp_meta = VIEWPOINT_MAP[vp_key]
        arch["viewpoints"][vp_key] = {
            "label": vp_meta["label"],
            "auto": True,
            "artifact_types": [vp_key],
            "audience": vp_meta["audience"],
        }
    arch["views"] = all_views

    # Gaps are RECOMPUTED, not read back. The section above this one is computed live
    # at save time, and the workflow SKILL.md teaches puts `declare_stakeholder_interest`
    # BETWEEN the gap check and the snapshot — so a stored block would state, ten lines
    # under a resolved tie, that the same person is tied to nothing (branch review A-1).
    gaps_critical, gaps_warning, gaps_info = _compute_gaps(project_id, repo, arch)
    gaps = _gaps_as_messages(gaps_critical, gaps_warning, gaps_info)
    arch["gaps"] = gaps

    # Summary statistics for the snapshot
    total_reqs = len([r for r in all_reqs if r.get("type", "") not in SKIP_TYPES])
    viewpoints_count = len(all_views)
    custom_count = len(custom_viewpoints)
    summary = {
        "total_reqs": total_reqs,
        "viewpoints_count": viewpoints_count,
        "custom_viewpoints_count": custom_count,
        "gaps_critical": len(gaps.get("critical", [])),
        "gaps_warning": len(gaps.get("warning", [])),
        "gaps_info": len(gaps.get("info", [])),
    }

    snapshot = {
        "version": version,
        "date": str(date.today()),
        "author": author or "",
        "notes": notes or "",
        "summary": summary,
    }

    arch["snapshots"].append(snapshot)
    _save_architecture(arch)

    # ------------------------------------------------------------------
    # Generate the Architecture Document (Markdown)
    # ------------------------------------------------------------------

    ctx = _load_context(project_id)
    goals = ctx.get("business_goals", []) if ctx else []

    # Group viewpoints by unique labels
    seen_labels: dict = {}
    for vp_key, req_ids in auto_views.items():
        meta = VIEWPOINT_MAP[vp_key]
        label = meta["label"]
        if label not in seen_labels:
            seen_labels[label] = {
                "artifact_types": [],
                "req_ids": [],
                "audience": meta["audience"],
            }
        seen_labels[label]["artifact_types"].append(vp_key)
        seen_labels[label]["req_ids"].extend(req_ids)

    doc_lines = [
        f"<!-- BABOK 7.4 — Architecture Document | Project: {project_id} | {version} | {date.today()} -->",
        "",
        f"# 📐 Requirements Architecture Document",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Project | {project_id} |",
        f"| Version | {version} |",
        f"| Date | {date.today()} |",
        f"| Author | {author or '—'} |",
        f"| Total req | {total_reqs} |",
        f"| Viewpoints | {viewpoints_count} ({custom_count} custom) |",
        "",
    ]

    if notes:
        doc_lines += [
            f"**Notes:** {notes}",
            "",
        ]

    doc_lines += [
        "---",
        "",
        "## Viewpoints",
        "",
        "| Viewpoint | Artifacts | Req count | Audience |",
        "|-----------|-----------|-----------|----------|",
    ]

    for label, data in seen_labels.items():
        types_str = ", ".join(f"`{t}`" for t in data["artifact_types"])
        req_count = len(data["req_ids"])
        doc_lines.append(
            f"| {label} | {types_str} | {req_count} | {data['audience']} |"
        )

    for vp_key, vp_data in custom_viewpoints.items():
        req_count = len(vp_data.get("req_ids", []))
        doc_lines.append(
            f"| {vp_data['label']} _(custom)_ | req_ids | {req_count} | "
            f"{vp_data.get('stakeholder_roles', '—')} |"
        )

    doc_lines.append("")

    # Viewpoint details
    doc_lines += [
        "## Viewpoint details",
        "",
    ]

    for label, data in seen_labels.items():
        req_ids = data["req_ids"]
        doc_lines.append(f"### {label} ({len(req_ids)} req)")
        if req_ids:
            # Req table
            doc_lines += [
                "| ID | Type | Title |",
                "|----|------|-------|",
            ]
            for rid in req_ids[:20]:
                row = _viewpoint_row(repo, rid)
                if row:
                    doc_lines.append(row)
            if len(req_ids) > 20:
                doc_lines.append(f"| _+{len(req_ids) - 20} more_ | | |")
        else:
            doc_lines.append("_No req_")
        doc_lines.append("")

    for vp_key, vp_data in custom_viewpoints.items():
        req_ids = vp_data.get("req_ids", [])
        doc_lines.append(f"### {vp_data['label']} [custom] ({len(req_ids)} req)")
        if vp_data.get("description"):
            doc_lines.append(f"_{vp_data['description']}_")
            doc_lines.append("")
        if req_ids:
            doc_lines += [
                "| ID | Type | Title |",
                "|----|------|-------|",
            ]
            for rid in req_ids[:20]:
                row = _viewpoint_row(repo, rid)
                if row:
                    doc_lines.append(row)
        doc_lines.append("")

    doc_lines += ["---", ""] + _concern_lines(project_id, repo)

    # Gap status
    doc_lines += [
        "## Architecture gaps",
        "",
        f"| Severity | Count |",
        f"|----------|-------|",
        f"| 🔴 Critical | {len(gaps.get('critical', []))} |",
        f"| 🟡 Warning | {len(gaps.get('warning', []))} |",
        f"| ℹ️ Info | {len(gaps.get('info', []))} |",
        "",
    ]

    if gaps.get("critical"):
        doc_lines.append("**Critical gaps:**")
        for g in gaps["critical"]:
            doc_lines.append(f"- {g}")
        doc_lines.append("")

    # Snapshot history
    all_snapshots = arch.get("snapshots", [])
    if len(all_snapshots) > 1:
        doc_lines += [
            "## Snapshot history",
            "",
            "| Version | Date | Author | Notes |",
            "|---------|------|--------|-------|",
        ]
        for s in all_snapshots:
            doc_lines.append(
                f"| {s['version']} | {s['date']} | {s.get('author', '—')} | "
                f"{s.get('notes', '—')[:60]} |"
            )
        doc_lines.append("")

    doc_lines += [
        "---",
        "",
        "## Artifact handoff",
        "",
        "| Direction | Purpose |",
        "|-----------|---------|",
        "| → **4.4** Communicate | Communicate the architecture to stakeholders |",
        "| → **7.5** Design Options | Basis for defining solution design options |",
    ]

    content = "\n".join(doc_lines)

    # Save via save_artifact
    save_artifact(content, prefix="7_4_architecture", project_id=project_id)

    # Response to the user
    result_lines = [
        f"✅ Snapshot **{version}** recorded — **{project_id}**",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Version | {version} |",
        f"| Date | {date.today()} |",
        f"| Req covered | {total_reqs} |",
        f"| Viewpoints | {viewpoints_count} |",
        f"| 🔴 Critical gaps | {summary['gaps_critical']} |",
        f"| 🟡 Warning gaps | {summary['gaps_warning']} |",
        "",
    ]

    if notes:
        result_lines += [f"**Notes:** {notes}", ""]

    result_lines += [
        "Architecture Document saved via `save_artifact` (prefix: `7_4_architecture`).",
        "",
        "---",
        "",
        "**Next steps:**",
        f"- → **4.4** `prepare_communication_package` — communicate the architecture to stakeholders",
        f"- → **7.5** Use the Architecture Document as an input artifact for Design Options",
    ]

    if summary["gaps_critical"] > 0:
        result_lines += [
            "",
            f"⚠️ **{summary['gaps_critical']} critical gap(s) not resolved.** "
            f"It's recommended to resolve them before handing off to 7.5.",
        ]

    return "\n".join(result_lines)


if __name__ == "__main__":
    mcp.run()
