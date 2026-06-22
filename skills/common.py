# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
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


class Stakeholder(BaseModel):
    """Stakeholder model for the engagement matrix."""
    name: str = Field(..., description="Stakeholder name or role")
    influence: str = Field(..., pattern="^(Low|Medium|High)$", description="Level of influence")
    interest: str = Field(..., pattern="^(Low|Medium|High)$", description="Level of interest")
    attitude: Optional[str] = Field("Neutral", description="Attitude toward the project: Neutral / Champion / Blocker")


def save_artifact(content: str, prefix: str, project_id: Optional[str] = None) -> str:
    """Saves a Markdown artifact to reports/ and returns the path.

    If project_id is provided, the artifact is written to reports/<project_id>/ (issue #1).
    Without project_id, the default behavior is preserved (flat reports/).
    """
    _ensure_dirs()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.md"
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
