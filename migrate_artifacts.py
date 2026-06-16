# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""Одноразовый перенос плоских артефактов governance_plans/ в подпапки проекта (issue #1).

Только перемещает (никогда не удаляет). По умолчанию dry-run — ничего не трогает,
пока не передан --apply. Идемпотентен: уже вложенные файлы пропускает, занятую
цель не перезаписывает.

Использование:
    python migrate_artifacts.py            # показать, что будет перемещено (dry-run)
    python migrate_artifacts.py --apply    # реально переместить
"""
import argparse
import os
import re
import shutil

BASE_DIR = "governance_plans"
DATA_DIR = os.path.join(BASE_DIR, "data")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

# Известные хвосты json-артефактов (project_id всегда лидирующий сегмент имени).
DATA_SUFFIXES = [
    "traceability_repo.json", "prioritization.json", "approval_history.json",
    "design_options.json", "recommendation.json", "business_context.json",
    "assumptions.json", "architecture.json", "change_strategy.json",
    "business_needs.json", "current_state_scope.json", "current_state.json",
    "future_state_scope.json", "future_state_goals.json", "future_state.json",
    "gap_analysis.json", "risk_assessment.json", "risk_scope.json",
    "verification_issues.json", "change_scope.json",
]

# Префиксы markdown-отчётов, в которых project_id встроен ПОСЛЕ кода задачи.
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
    """Возвращает список строк-операций (для отчёта и тестов)."""
    log = []

    # --- data/ ---
    if os.path.isdir(DATA_DIR):
        for entry in sorted(os.listdir(DATA_DIR)):
            full = os.path.join(DATA_DIR, entry)
            if os.path.isdir(full):
                if entry.endswith("_specs"):
                    pid = entry[: -len("_specs")]
                    for f in sorted(os.listdir(full)):
                        _move(os.path.join(full, f),
                              os.path.join(DATA_DIR, pid, "specs", f), apply, log)
                continue
            pid = _project_from_data(entry)
            if pid:
                _move(full, os.path.join(DATA_DIR, pid, entry), apply, log)
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
                _move(full, os.path.join(REPORTS_DIR, pid, entry), apply, log)
            else:
                log.append(f"skip (project unknown): {entry}")

    return log


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Перенос артефактов в подпапки проекта.")
    ap.add_argument("--apply", action="store_true",
                    help="реально перемещать (без флага — dry-run)")
    args = ap.parse_args()
    header = "=== МИГРАЦИЯ АРТЕФАКТОВ ==="
    if not args.apply:
        header += " (DRY-RUN, ничего не перемещается)"
    print(header)
    for line in migrate(apply=args.apply):
        print(line)
    if not args.apply:
        print("\nЗапусти с --apply чтобы выполнить перемещение.")
