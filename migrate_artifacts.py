# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""One-time migration of flat artifacts in governance_plans/ into per-project subfolders (issue #1).

Only moves files (never deletes). Dry-run by default -- nothing is touched
until --apply is passed. Idempotent: already-nested files are skipped, and an
occupied target is never overwritten.

Usage:
    python migrate_artifacts.py            # show what would be moved (dry-run)
    python migrate_artifacts.py --apply    # actually move the files
"""
import argparse
import os
import re
import shutil

from skills.common import normalize_project_id

BASE_DIR = "governance_plans"
DATA_DIR = os.path.join(BASE_DIR, "data")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

# Known json-artifact suffixes (project_id is always the leading segment of the name).
DATA_SUFFIXES = [
    "traceability_repo.json", "prioritization.json", "approval_history.json",
    "design_options.json", "recommendation.json", "business_context.json",
    "assumptions.json", "architecture.json", "change_strategy.json",
    "business_needs.json", "current_state_scope.json", "current_state.json",
    "future_state_scope.json", "future_state_goals.json", "future_state.json",
    "gap_analysis.json", "risk_assessment.json", "risk_assessment_scope.json",
    "verification_issues.json", "change_strategy_scope.json",
    # 6.3/6.4 scope files carry the producer's real SCOPE_FILENAME suffix
    # (risk_assessment_scope / change_strategy_scope); the earlier "risk_scope" /
    # "change_scope" spellings matched no producer, so those scope files were left
    # flat with a "skip (project unknown)". The living stakeholder registry (4.2/3.2)
    # was absent from the list entirely.
    "stakeholder_registry.json",
]

# Markdown-report prefixes where the project_id is embedded AFTER the task code.
REPORT_PREFIXES = [
    "3_ba_plan_", "5_3_prioritization_", "6_1_current_state_", "6_2_future_state_",
    "6_3_risk_assessment_", "6_4_change_strategy_", "Elicitation_Plan_",
    "Cross_Analysis_", "CR_Elicitation_", "Stakeholder_Registry_",
]

_TIMESTAMP_RE = re.compile(r"_\d{8}_\d{6}\.md$")


def _project_from_data(name):
    for suf in DATA_SUFFIXES:
        if name.endswith("_" + suf) and len(name) > len(suf) + 1:
            return name[: -(len(suf) + 1)]
    return None


def _project_from_report(name):
    for pre in REPORT_PREFIXES:
        if name.startswith(pre):
            rest = name[len(pre):]
            rest = _TIMESTAMP_RE.sub("", rest)
            rest = re.sub(r"\.md$", "", rest)
            return rest or None
    return None


def _move(src, dst, apply, log):
    if os.path.exists(dst):
        log.append(f"skip (target exists): {src}")
        return
    if apply:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
    log.append(f"{'moved' if apply else 'would move'}: {src} -> {dst}")


def migrate(apply=False):
    """Returns a list of operation strings (for the report and for tests)."""
    log = []

    # --- data/ ---
    if os.path.isdir(DATA_DIR):
        for entry in sorted(os.listdir(DATA_DIR)):
            full = os.path.join(DATA_DIR, entry)
            if os.path.isdir(full):
                if entry.endswith("_specs"):
                    norm = normalize_project_id(entry[: -len("_specs")])
                    for f in sorted(os.listdir(full)):
                        _move(os.path.join(full, f),
                              os.path.join(DATA_DIR, norm, "specs", f), apply, log)
                continue
            pid = _project_from_data(entry)
            if pid:
                # Canonical layout: normalize BOTH the folder AND the file-name prefix,
                # so the runtime (data_path -> normalize_project_id) reliably finds the file.
                norm = normalize_project_id(pid)
                base = entry[len(pid) + 1:]
                _move(full, os.path.join(DATA_DIR, norm, f"{norm}_{base}"), apply, log)
            else:
                log.append(f"skip (project unknown): {entry}")

    # --- reports/ ---
    if os.path.isdir(REPORTS_DIR):
        for entry in sorted(os.listdir(REPORTS_DIR)):
            full = os.path.join(REPORTS_DIR, entry)
            if os.path.isdir(full) or not entry.endswith(".md"):
                continue
            pid = _project_from_report(entry)
            if pid:
                # Reports are only ever read via directory listing (glob) -- normalize the
                # folder, but leave the file name as-is (the embedded prefix is just a label).
                _move(full, os.path.join(REPORTS_DIR, normalize_project_id(pid), entry), apply, log)
            else:
                log.append(f"skip (project unknown): {entry}")

    return log


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Move artifacts into per-project subfolders.")
    ap.add_argument("--apply", action="store_true",
                    help="actually move the files (without this flag: dry-run)")
    args = ap.parse_args()
    header = "=== ARTIFACT MIGRATION ==="
    if not args.apply:
        header += " (DRY-RUN, nothing will be moved)"
    print(header)
    for line in migrate(apply=args.apply):
        print(line)
    if not args.apply:
        print("\nRun with --apply to perform the move.")
