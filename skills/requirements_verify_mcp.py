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

rule-based MCP + interpretation in Claude Code (not API-in-MCP)
issues in a separate file {project}_verification_issues.json
cross-model verification — a separate tool

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
from skills.common import (write_json_artifact,
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
# Словари и паттерны (ADR-027: rule-based)
# ---------------------------------------------------------------------------

ATOMICITY_SIGNALS = [
    " и ", " а также ", " а так же ",
    " а ещё ", " а еще ", " плюс к этому ",
    " кроме того ", " помимо этого ", " вдобавок ",
    " одновременно с ", " вместе с тем ",
]

AMBIGUITY_SIGNALS = [
    "быстро", "быстрый", "быстрая", "быстрое", "быстрее",
    "медленно", "медленный",
    "удобно", "удобный", "удобная", "удобное", "удобен",
    "легко", "легкий", "лёгкий", "легкая", "лёгкая",
    "хорошо", "хороший", "хорошая", "хорошее",
    "качественно", "качественный",
    "эффективно", "эффективный",
    "оптимально", "оптимальный",
    "часто", "редко", "периодически", "иногда",
    "обычно", "как правило", "в большинстве случаев", "зачастую",
    "должен стараться", "по возможности", "по мере возможности",
    "в разумные сроки", "в кратчайшие сроки", "максимально быстро",
    "при необходимости", "желательно", "предпочтительно", "рекомендуется",
    "допустимо", "допускается",
    "небольшой", "крупный", "значительный", "существенный",
    "достаточно", "достаточный", "адекватный", "приемлемый",
    "вовремя", "своевременно", "без задержек", "оперативно",
    "и/или", "современный", "актуальный", "стандартный", "типовой",
]

CONCISENESS_SIGNALS = [
    "реализовать через", "реализовать с помощью", "использовать технологию",
    "использовать фреймворк", "написать код", "создать таблицу в базе",
    "использовать rest", "использовать api", "вызвать метод",
    "ранее было", "исторически", "в предыдущей версии",
]

MEASURABILITY_PATTERNS = [
    r'\d+\s*(?:мс|ms|с\b|сек|мин|час|%|мб|гб|тб|rpm|rps|tps)',
    r'не более \d+', r'не менее \d+', r'до \d+', r'от \d+',
    r'\d+\s*секунд', r'\d+\s*минут', r'\d+\s*пользовател',
    r'100\s*%', r'0 ошибок', r'нулевой', r'полностью',
    r'\d+\s*запрос', r'\d+\s*транзакц',
]

CONDITION_PATTERNS = [
    r'если ', r'когда ', r'при ', r'в случае ', r'при условии ',
    r'if ', r'when ', r'unless ',
]


# ---------------------------------------------------------------------------
# Утилиты — репозиторий 5.1
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
    write_json_artifact(path, repo)
    logger.info(f"Repository 5.1 updated (7.2): {path}")


def _find_req(repo: dict, req_id: str) -> Optional[dict]:
    for r in repo["requirements"]:
        if r["id"] == req_id:
            return r
    return None


# ---------------------------------------------------------------------------
# Утилиты — файл issues (ADR-028)
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
    write_json_artifact(path, data)
    logger.info(f"Issues file updated (7.2): {path}")


def _next_issue_id(data: dict) -> str:
    existing = [k for k in data["issues"].keys() if k.startswith("VI-")]
    if not existing:
        return "VI-001"
    nums = [int(k.split("-")[1]) for k in existing if k.split("-")[1].isdigit()]
    return f"VI-{(max(nums) + 1):03d}" if nums else "VI-001"


def _open_issues_for_req(data: dict, req_id: str) -> list:
    """Возвращает список открытых issues для данного req_id."""
    return [
        v for v in data["issues"].values()
        if v.get("req_id") == req_id and v.get("status") == "open"
    ]


def _open_blockers_for_req(data: dict, req_id: str) -> list:
    """Возвращает список открытых blocker-issues для req_id."""
    return [
        v for v in data["issues"].values()
        if v.get("req_id") == req_id
        and v.get("status") == "open"
        and v.get("severity") == "blocker"
    ]


# ---------------------------------------------------------------------------
# Утилиты — specs-директория (7.1)
# ---------------------------------------------------------------------------

def _specs_dir(project_id: str) -> str:
    # issue #1: спеки в data/<project>/specs/, с fallback на legacy-раскладки.
    # Единый источник истины — common.specs_dir.
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
        # Заголовок секции — КОНТРАКТ с 7.1: ищем ровно то, что она печатает.
        stmt = _spec_section_body(content, "Формулировка")
        # drop the italic hint line ("> _..._") the 7.1 template prepends
        stmt = "\n".join(l for l in stmt.split("\n") if not l.strip().startswith(">")).strip()
        if stmt:
            fields["description"] = stmt
    elif req_type == "use_case":
        # present the exception-scenarios section (empty string if the section is absent)
        fields["exc_scenarios"] = _spec_section_body(content, "Сценарии исключений")
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
# Rule-based проверки (ADR-027)
# ---------------------------------------------------------------------------

def _check_atomicity(text: str) -> dict:
    """Проверяет атомарность по сигнальным словам."""
    text_lower = text.lower()
    found = [s.strip() for s in ATOMICITY_SIGNALS if s in text_lower]
    if len(found) >= 2:
        return {"passed": False, "signals_found": found,
                "note": f"Найдено {len(found)} соединительных сигнала — возможно требование составное"}
    elif len(found) == 1:
        return {"passed": True, "signals_found": found,
                "note": "Один сигнал — проверь контекст: может быть перечисление значений, а не два требования"}
    return {"passed": True, "signals_found": [], "note": None}


def _check_ambiguity(text: str) -> dict:
    """Проверяет однозначность по словам-сигналам."""
    text_lower = text.lower()
    found = [s for s in AMBIGUITY_SIGNALS if s in text_lower]
    if found:
        return {"passed": False, "signals_found": found,
                "note": f"Найдены слова без измеримых критериев: {', '.join(repr(s) for s in found[:5])}"}
    return {"passed": True, "signals_found": [], "note": None}


def _check_testability_us(title: str, ac_count: int, ac_texts: list) -> dict:
    """Тестируемость User Story: проверка AC."""
    if ac_count < 2:
        return {"passed": False, "issue": "missing_ac", "ac_count": ac_count,
                "note": f"User Story содержит {ac_count} AC, требуется минимум 2"}
    # Проверяем AC на неоднозначность
    ac_full = " ".join(ac_texts).lower()
    ambiguous_in_ac = [s for s in AMBIGUITY_SIGNALS if s in ac_full]
    if ambiguous_in_ac:
        return {"passed": True, "issue": None, "ac_count": ac_count,
                "note": f"AC содержат слова-сигналы: {', '.join(repr(s) for s in ambiguous_in_ac[:3])} — рекомендуется уточнить"}
    return {"passed": True, "issue": None, "ac_count": ac_count, "note": None}


def _check_testability_fr(description: str, req_type: str) -> dict:
    """Тестируемость FR/NFR/BR: проверка наличия измеримого критерия."""
    desc_lower = description.lower()

    if req_type == "business_rule":
        # BR: достаточно наличия условия
        has_condition = any(re.search(p, desc_lower) for p in CONDITION_PATTERNS)
        if has_condition:
            return {"passed": True, "issue": None, "note": None}
        return {"passed": True, "issue": None,
                "note": "BR без явного условия — проверь: ясно ли при каком контексте правило применяется"}

    # functional / non_functional
    has_measure = any(re.search(p, desc_lower) for p in MEASURABILITY_PATTERNS)
    if has_measure:
        return {"passed": True, "issue": None, "note": None}
    return {
        "passed": False, "issue": "not_testable",
        "note": "Нет измеримого критерия — добавь числовое значение, метрику или чёткое бинарное условие"
    }


def _check_testability_uc(exc_scenarios: str) -> dict:
    """Тестируемость UC: наличие сценариев исключений."""
    if exc_scenarios and exc_scenarios.strip():
        return {"passed": True, "issue": None, "note": None}
    return {"passed": False, "issue": "not_testable",
            "note": "Use Case без сценариев исключений — тестирование граничных условий невозможно"}


def _check_prioritized(priority: str) -> dict:
    """Проверяет наличие приоритета."""
    if priority and priority.strip() and priority.lower() not in ("", "none", "null", "-"):
        return {"passed": True, "priority": priority, "note": None}
    return {"passed": False, "priority": None,
            "note": "Приоритет не задан — заполни через инструменты 5.3 (Prioritize Requirements)"}


def _check_conciseness(title: str, description: str, req_type: str) -> dict:
    """Проверяет краткость: длина и сигналы лишнего."""
    warnings = []

    # Длина title
    if req_type == "user_story" and len(title) > 100:
        warnings.append(f"Название истории длиной {len(title)} символов — рекомендуется ≤ 100")
    elif len(title) > 150:
        warnings.append(f"Название длиной {len(title)} символов — рекомендуется ≤ 150")

    # Длина description
    if description and len(description) > 800:
        warnings.append(f"Описание длиной {len(description)} символов — рекомендуется ≤ 800, "
                        f"возможно требование составное")

    # Сигналы реализации в описании требования
    desc_lower = description.lower() if description else ""
    impl_signals = [s for s in CONCISENESS_SIGNALS if s in desc_lower]
    if impl_signals:
        warnings.append(f"Возможное описание реализации: {', '.join(repr(s) for s in impl_signals[:2])}")

    if warnings:
        return {"passed": True, "warning": " | ".join(warnings)}
    return {"passed": True, "warning": None}


def _check_group_b(req: dict, repo: dict) -> dict:
    """Группа B: согласованность и полнота через данные репозитория 5.1."""
    req_id = req["id"]
    result = {}

    # Полнота: наличие source_artifact
    has_source = bool(req.get("source_artifact", "").strip())
    # Наличие owner
    has_owner = bool(req.get("owner", "").strip())
    # Наличие хотя бы одной связи в графе
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
        result["complete"]["warnings"].append("Нет трассировки к артефакту 4.3 (source_artifact пустой)")
    if not has_links:
        result["complete"]["warnings"].append("Нет связей в репозитории 5.1 — изолированное требование")
    if not has_owner:
        result["complete"]["warnings"].append("Не указан owner — кто отвечает за это требование?")

    # Согласованность: смотрим на статус req
    req_status = req.get("status", "draft")
    conflict_statuses = {"conflict", "rejected", "superseded"}
    if req_status in conflict_statuses:
        result["consistent"] = {
            "status": "needs_review",
            "note": f"Требование в статусе '{req_status}' — проверь наличие конфликтов"
        }
    else:
        result["consistent"] = {"status": "ok", "note": None}

    return result


def _check_single_req(req: dict, repo: dict) -> dict:
    """Выполняет все проверки для одного требования. Возвращает структурированный результат."""
    req_id = req["id"]
    req_type = req.get("type", "")
    title = req.get("title", "")
    # description может быть в самом req или нам нужно читать файл — MCP хранит только мета.
    # По архитектуре 5.1 desc не хранится в репо (только id, type, title, status, priority...).
    # Проверки по тексту делаем по title (у нас есть) + по полям которые есть в репо.
    description = req.get("description", "")  # может быть пустым
    priority = req.get("priority", "")

    checks = {}
    blockers = []
    majors = []
    minors = []

    # --- Атомарность ---
    text_for_atomicity = title + " " + description
    checks["atomic"] = _check_atomicity(text_for_atomicity)
    if not checks["atomic"]["passed"] and len(checks["atomic"]["signals_found"]) >= 2:
        majors.append("not_atomic")

    # --- Однозначность ---
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
        # business_process, data_dictionary, erd — базовая проверка по title
        checks["testable"] = {"passed": True, "issue": None,
                               "note": f"Тип '{req_type}' — тестируемость проверяется вручную по чеклисту"}

    # --- Приоритизированность ---
    checks["prioritized"] = _check_prioritized(priority)
    if not checks["prioritized"]["passed"]:
        minors.append("not_prioritized")

    # --- Краткость ---
    checks["concise"] = _check_conciseness(title, description, req_type)
    if checks["concise"].get("warning"):
        minors.append("conciseness_warning")

    # --- Группа B ---
    group_b = _check_group_b(req, repo)
    for w in group_b["complete"]["warnings"]:
        minors.append(f"completeness: {w[:30]}")

    # --- Итог ---
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
        "group_c_note": "Выполнимость и Понятность — проверь вручную по references/checklist_templates.md",
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
    BABOK 7.2 — Проверяет требования по 9 характеристикам качества BABOK.
    Группа A (rule-based): атомарность, однозначность, тестируемость, приоритизированность, краткость.
    Группа B (репозиторий): согласованность, полнота.
    Группа C: напоминание пройти чеклисты вручную.

    MCP does the rule-based checks, Claude Code interprets and writes recommendations.

    Args:
        project_id: Идентификатор проекта.
        req_ids:    JSON-список ID для проверки: '["US-001", "FR-001"]'.
                    Если пустой — проверяет все req со статусом draft.
        req_type:   Фильтр по типу: user_story | functional | non_functional |
                    business_rule | use_case | business_process | data_dictionary | erd.
                    Если пустой — все типы.

    Returns:
        Структурированные результаты проверок для интерпретации Claude Code.
    """
    logger.info(f"check_req_quality: project_id='{project_id}', req_ids='{req_ids}', req_type='{req_type}'")

    repo = _load_repo(project_id)
    all_reqs = repo.get("requirements", [])

    if not all_reqs:
        return (
            f"⚠️ Репозиторий 5.1 для проекта `{project_id}` пуст или не найден.\n\n"
            f"Убедись что требования созданы через инструменты 7.1 и репозиторий существует по пути:\n"
            f"`governance_plans/{project_id.lower().replace(' ', '_')}_traceability_repo.json`"
        )

    # Фильтрация по ID
    if req_ids.strip():
        try:
            ids_to_check = json.loads(req_ids)
            if not isinstance(ids_to_check, list):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            return f"❌ Ошибка парсинга req_ids: ожидается JSON-список, например: '[\"US-001\", \"FR-001\"]'"
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

    # Фильтрация по типу
    if req_type.strip():
        reqs_to_check = [r for r in reqs_to_check if r.get("type", "") == req_type]

    if not reqs_to_check:
        msg = f"ℹ️ Нет требований для проверки в проекте `{project_id}`"
        if req_type:
            msg += f" (тип: {req_type})"
        msg += ".\n\nВозможно все требования уже имеют статус `verified`."
        return msg

    # Run the checks — enrich each req from its 7.1 spec file first (audit finding 7.2-A), so
    # quality is judged on the real requirement text, not on repo metadata alone.
    enriched_reqs = [_enrich_req_from_spec(r, project_id) for r in reqs_to_check]
    results = [_check_single_req(r, repo) for r in enriched_reqs]

    # Агрегация
    passed_count = sum(1 for r in results if r["overall"] == "passed")
    warnings_count = sum(1 for r in results if r["overall"] == "warnings_only")
    issues_count = sum(1 for r in results if r["overall"] == "issues_found")

    all_blockers = [(r["req_id"], b) for r in results for b in r["blockers"]]
    all_majors = [(r["req_id"], m) for r in results for m in r["majors"]]

    # Формируем отчёт
    lines = [
        f"<!-- BABOK 7.2 — Quality Check | Проект: {project_id} | {date.today()} -->",
        "",
        f"# 🔍 Верификация требований — {project_id}",
        "",
        f"**Дата:** {date.today()}  ",
        f"**Проверено:** {len(results)} требований  ",
        f"**Фильтр по типу:** {req_type or 'все типы'}",
        "",
        "## Сводка",
        "",
        "| Статус | Количество |",
        "|--------|-----------|",
        f"| ✅ Прошли все проверки | {passed_count} |",
        f"| ⚠️ Только предупреждения | {warnings_count} |",
        f"| ❌ Найдены проблемы | {issues_count} |",
        "",
    ]

    if not_found:
        lines += [
            f"⚠️ Не найдены в репозитории: {', '.join(f'`{i}`' for i in not_found)}",
            "",
        ]

    if all_blockers:
        lines += [
            "## 🚨 Блокеры (обязательно исправить перед 5.5)",
            "",
        ]
        for req_id, issue in all_blockers:
            lines.append(f"- `{req_id}`: **{issue}**")
        lines.append("")

    if all_majors:
        lines += [
            "## ⚠️ Серьёзные проблемы (major)",
            "",
        ]
        for req_id, issue in all_majors:
            lines.append(f"- `{req_id}`: {issue}")
        lines.append("")

    # Детали по каждому req
    lines += [
        "---",
        "",
        "## Результаты по каждому требованию",
        "",
        "*(Claude Code: для каждого req с issues_found — объясни проблему и предложи исправление)*",
        "",
    ]

    for r in results:
        icon = {"passed": "✅", "warnings_only": "⚠️", "issues_found": "❌"}.get(r["overall"], "❓")
        lines.append(f"### {icon} `{r['req_id']}` — {r['title']}")
        lines.append(f"**Тип:** {r['req_type']} | **Статус:** {r['current_status']}")
        lines.append("")

        # Группа A
        checks = r["checks"]

        atomic = checks.get("atomic", {})
        mark = "✅" if atomic.get("passed") else "❌"
        note = f" _{atomic.get('note', '')}_" if atomic.get("note") else ""
        lines.append(f"- {mark} **Атомарность**{note}")

        unamb = checks.get("unambiguous", {})
        mark = "✅" if unamb.get("passed") else "❌"
        signals = unamb.get("signals_found", [])
        note = f" — сигналы: {', '.join(repr(s) for s in signals[:3])}" if signals else ""
        lines.append(f"- {mark} **Однозначность**{note}")

        testable = checks.get("testable", {})
        mark = "✅" if testable.get("passed") else "❌"
        note = f" — {testable.get('note', '')}" if testable.get("note") else ""
        lines.append(f"- {mark} **Тестируемость**{note}")

        prioritized = checks.get("prioritized", {})
        mark = "✅" if prioritized.get("passed") else "⚠️"
        prio = prioritized.get("priority")
        note = f" ({prio})" if prio else " — не задан"
        lines.append(f"- {mark} **Приоритизированность**{note}")

        concise = checks.get("concise", {})
        warning = concise.get("warning")
        mark = "⚠️" if warning else "✅"
        note = f" — {warning}" if warning else ""
        lines.append(f"- {mark} **Краткость**{note}")

        # Группа B
        group_b = r.get("group_b", {})
        complete = group_b.get("complete", {})
        consistent = group_b.get("consistent", {})

        cons_ok = consistent.get("status") == "ok"
        mark = "✅" if cons_ok else "⚠️"
        cons_note = f" — {consistent.get('note', '')}" if not cons_ok else ""
        lines.append(f"- {mark} **Согласованность**{cons_note}")

        comp_warnings = complete.get("warnings", [])
        mark = "✅" if not comp_warnings else "⚠️"
        comp_note = f" — {comp_warnings[0]}" if comp_warnings else ""
        lines.append(f"- {mark} **Полнота**{comp_note}")

        lines.append(f"- 📋 **Выполнимость + Понятность** — проверь чеклист вручную")

        if r["blockers"] or r["majors"]:
            lines.append("")
            lines.append(f"> **Рекомендация для Claude Code:** "
                         f"Blockers: {r['blockers'] or 'нет'} | "
                         f"Majors: {r['majors'] or 'нет'}")
            lines.append("> Объясни BA что именно нарушено и предложи конкретную переформулировку.")

        lines.append("")

    # Следующие шаги
    lines += [
        "---",
        "",
        "## Следующие шаги",
        "",
    ]

    if issues_count > 0 or len(all_blockers) > 0:
        lines.append("1. Для каждой проблемы выше: `open_verification_issue` с описанием.")
        lines.append("2. Исправь требования (через инструменты 7.1 или вручную в файлах specs/).")
        lines.append("3. Закрой issues: `resolve_verification_issue`.")
    lines.append(f"4. Проверь согласованность моделей: `check_model_consistency(project_id='{project_id}')`.")
    lines.append(f"5. Пройди чеклисты Группы C из `references/checklist_templates.md`.")
    lines.append(f"6. Верифицируй готовые req: `mark_req_verified`.")
    lines.append(f"7. Сгенерируй отчёт: `get_verification_report(project_id='{project_id}')`.")

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
    a separate tool for checking model consistency.

    Что проверяет:
      - Сущности в Data Dictionary (.md) vs ERD (.puml): рассинхрон имён
      - Use Cases в репозитории 5.1 vs UC Diagram (.puml): UC без актора
      - Участники Business Process (.md) vs акторы в UC Diagram (.puml)

    Читает файлы из governance_plans/{project_id}_specs/ по шаблонам из 7.1.

    Args:
        project_id: Идентификатор проекта.

    Returns:
        Список несоответствий между моделями для интерпретации Claude Code.
    """
    logger.info(f"check_model_consistency: project_id='{project_id}'")

    specs_dir = _specs_dir(project_id)
    if not os.path.exists(specs_dir):
        return (
            f"⚠️ Директория со спецификациями не найдена: `{specs_dir}`\n\n"
            f"Убедись что артефакты созданы через инструменты 7.1 "
            f"(`create_data_dictionary`, `create_erd`, `create_use_case`, `create_business_process`)."
        )

    all_files = glob.glob(os.path.join(specs_dir, "*.md")) + glob.glob(os.path.join(specs_dir, "*.puml"))
    if not all_files:
        return (
            f"⚠️ В директории `{specs_dir}` нет файлов .md или .puml.\n"
            f"Создай спецификации через инструменты 7.1."
        )

    issues = []

    # --- Парсинг DD: извлечь имена сущностей ---
    dd_entities = set()
    dd_files = glob.glob(os.path.join(specs_dir, "dd_*.md"))
    for filepath in dd_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            # Шаблон 7.1: "## Сущность: EntityName"
            for match in re.finditer(r"##\s+Сущность:\s+(.+)", content):
                name = match.group(1).strip()
                if name:
                    dd_entities.add(name)
        except IOError:
            pass

    # --- Парсинг ERD .puml: извлечь имена entity ---
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

    # DD vs ERD: сущности в DD но не в ERD и наоборот
    if dd_entities and erd_entities:
        in_dd_not_erd = dd_entities - erd_entities
        in_erd_not_dd = erd_entities - dd_entities
        for name in sorted(in_dd_not_erd):
            issues.append({
                "type": "model_inconsistency",
                "models": ["Data Dictionary", "ERD"],
                "description": f"Сущность '{name}' есть в Data Dictionary, но отсутствует в ERD",
                "severity": "major",
            })
        for name in sorted(in_erd_not_dd):
            issues.append({
                "type": "model_inconsistency",
                "models": ["ERD", "Data Dictionary"],
                "description": f"Сущность '{name}' есть в ERD, но отсутствует в Data Dictionary",
                "severity": "major",
            })

    # --- Парсинг UC Diagram .puml: акторы и UC aliases ---
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

    # --- Парсинг UC .md файлов: актор primary ---
    uc_spec_actors = {}  # uc_title -> primary_actor
    uc_md_files = glob.glob(os.path.join(specs_dir, "uc_*.md"))
    for filepath in uc_md_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            # Из таблицы: | Актор (primary) | ActorName |
            actor_match = re.search(r'\|\s*Актор \(primary\)\s*\|\s*(.+?)\s*\|', content)
            # Заголовок файла: # UC-001 — Title
            title_match = re.search(r'#\s+UC-\d+\s+—\s+(.+)', content)
            if actor_match and title_match:
                uc_title = title_match.group(1).strip()
                actor = actor_match.group(1).strip()
                if actor and actor != "Значение":
                    uc_spec_actors[uc_title] = actor
        except IOError:
            pass

    # UC актора из .md есть, но не в UC Diagram
    for uc_title, actor in uc_spec_actors.items():
        if uc_diagram_actors and actor not in uc_diagram_actors:
            issues.append({
                "type": "model_inconsistency",
                "models": ["Use Case (.md)", "UC Diagram (.puml)"],
                "description": f"Актор '{actor}' упомянут в спецификации UC '{uc_title}', "
                               f"но отсутствует в UC Diagram",
                "severity": "minor",
            })

    # UC из specs, но не на диаграмме (по title)
    if uc_diagram_usecases:
        for uc_title in uc_spec_actors:
            if uc_title not in uc_diagram_usecases:
                issues.append({
                    "type": "model_inconsistency",
                    "models": ["Use Case (.md)", "UC Diagram (.puml)"],
                    "description": f"Use Case '{uc_title}' есть в спецификации, но не на UC Diagram",
                    "severity": "minor",
                })

    # --- Парсинг BP .md: участники ---
    bp_participants = set()
    bp_md_files = glob.glob(os.path.join(specs_dir, "bp_*.md"))
    for filepath in bp_md_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            # | Участники | Role1, Role2 |
            p_match = re.search(r'\|\s*Участники\s*\|\s*(.+?)\s*\|', content)
            if p_match:
                participants_str = p_match.group(1).strip()
                for p in participants_str.split(","):
                    p = p.strip()
                    if p and p != "Значение":
                        bp_participants.add(p)
        except IOError:
            pass

    # BP участники есть, но не как акторы в UC Diagram
    if bp_participants and uc_diagram_actors:
        for participant in sorted(bp_participants):
            if participant not in uc_diagram_actors:
                issues.append({
                    "type": "model_inconsistency",
                    "models": ["Business Process (.md)", "UC Diagram (.puml)"],
                    "description": f"Участник '{participant}' упомянут в Business Process, "
                                   f"но не определён как актор в UC Diagram",
                    "severity": "minor",
                })

    # --- Формируем отчёт ---
    lines = [
        f"<!-- BABOK 7.2 — Model Consistency | Проект: {project_id} | {date.today()} -->",
        "",
        f"# 🔗 Согласованность моделей — {project_id}",
        "",
        f"**Дата:** {date.today()}  ",
        f"**Директория specs:** `{specs_dir}`  ",
        f"**Файлов проверено:** {len(all_files)}",
        "",
        "## Что проверялось",
        "",
        f"- Data Dictionary файлов: {len(dd_files)} (сущностей: {len(dd_entities)})",
        f"- ERD файлов: {len(erd_files)} (сущностей: {len(erd_entities)})",
        f"- UC Diagram файлов: {len(uc_puml_files)} (акторов: {len(uc_diagram_actors)})",
        f"- Use Case .md файлов: {len(uc_md_files)}",
        f"- Business Process .md файлов: {len(bp_md_files)}",
        "",
    ]

    if not issues:
        lines += [
            "## ✅ Несоответствий не найдено",
            "",
            "Все модели согласованы между собой.",
            "",
            "**Примечание:** Парсинг работает по стандартным шаблонам из 7.1. "
            "Нестандартное форматирование файлов может не обнаруживаться автоматически — "
            "рекомендуется визуальная проверка.",
        ]
    else:
        major_issues = [i for i in issues if i["severity"] == "major"]
        minor_issues = [i for i in issues if i["severity"] == "minor"]

        lines += [
            f"## Результат: {len(issues)} несоответствий",
            "",
            f"- 🔴 Серьёзных (major): {len(major_issues)}",
            f"- 🟡 Незначительных (minor): {len(minor_issues)}",
            "",
        ]

        if major_issues:
            lines += ["## 🔴 Серьёзные несоответствия", ""]
            for issue in major_issues:
                models = " ↔ ".join(issue["models"])
                lines.append(f"- **{models}:** {issue['description']}")
            lines.append("")

        if minor_issues:
            lines += ["## 🟡 Незначительные несоответствия", ""]
            for issue in minor_issues:
                models = " ↔ ".join(issue["models"])
                lines.append(f"- {models}: {issue['description']}")
            lines.append("")

        lines += [
            "---",
            "",
            "## Следующие шаги",
            "",
            "1. Для каждого несоответствия: `open_verification_issue` с `issue_type='model_inconsistency'`.",
            "2. Исправь нужный файл в `governance_plans/{project}_specs/` (или пересоздай через 7.1).",
            "3. После исправления: `resolve_verification_issue`.",
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
    issues are stored in {project}_verification_issues.json.

    Args:
        project_id:  Идентификатор проекта.
        req_id:      ID требования с проблемой (US-001, FR-003 и т.д.).
        issue_type:  Тип проблемы:
                     ambiguity         — размытая формулировка
                     not_testable      — нет критерия тестирования
                     not_atomic        — требование составное
                     missing_ac        — нет Acceptance Criteria (для US)
                     model_inconsistency — рассинхрон между моделями
                     other             — другое
        description: Что именно нарушено и почему это проблема.
        severity:    blocker | major | minor
        assigned_to: Кому назначить (имя BA или stakeholder). По умолчанию пусто.

    Returns:
        Подтверждение с ID созданного issue.
    """
    logger.info(f"open_verification_issue: project_id='{project_id}', req_id='{req_id}'")

    valid_issue_types = {"ambiguity", "not_testable", "not_atomic", "missing_ac",
                         "model_inconsistency", "other"}
    if issue_type not in valid_issue_types:
        return (
            f"❌ Недопустимый issue_type: '{issue_type}'.\n"
            f"Допустимые значения: {' | '.join(sorted(valid_issue_types))}"
        )

    valid_severities = {"blocker", "major", "minor"}
    if severity not in valid_severities:
        return (
            f"❌ Недопустимый severity: '{severity}'.\n"
            f"Допустимые значения: blocker | major | minor"
        )

    if not description.strip():
        return "❌ description не может быть пустым — опиши что именно нарушено."

    # Проверяем что req существует в репозитории
    repo = _load_repo(project_id)
    req = _find_req(repo, req_id)
    req_title = req["title"] if req else "(требование не найдено в 5.1)"

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

    # Обновляем статистику
    data["stats"]["open"] = sum(1 for v in data["issues"].values() if v["status"] == "open")
    data["stats"]["total"] = len(data["issues"])
    data["stats"]["closed"] = data["stats"]["total"] - data["stats"]["open"]

    _save_issues(data)

    lines = [
        f"✅ Issue зафиксирован: **{issue_id}**",
        "",
        f"| Поле | Значение |",
        f"|------|----------|",
        f"| ID issue | `{issue_id}` |",
        f"| Требование | `{req_id}` — {req_title} |",
        f"| Тип проблемы | {issue_type} |",
        f"| Severity | {severity_labels[severity]} |",
        f"| Назначено | {assigned_to or '—'} |",
        f"| Статус | open |",
        f"| Дата открытия | {date.today()} |",
        "",
        f"**Описание:** {description}",
        "",
        "---",
        "",
        "**Следующий шаг:** исправь требование и вызови:",
        f"`resolve_verification_issue(project_id='{project_id}', issue_id='{issue_id}', resolution_note='...')`",
    ]

    if severity == "blocker":
        lines.insert(1, "")
        lines.insert(2, f"> 🚨 **Blocker:** `{req_id}` не может быть верифицирован до закрытия этого issue.")

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
    BABOK 7.2 — Закрывает verification issue после исправления BA.

    Args:
        project_id:      Идентификатор проекта.
        issue_id:        ID issue: VI-001, VI-002 и т.д.
        resolution_note: Что именно было исправлено (для аудита).

    Returns:
        Подтверждение закрытия + статус оставшихся blockers по этому req.
    """
    logger.info(f"resolve_verification_issue: project_id='{project_id}', issue_id='{issue_id}'")

    if not resolution_note.strip():
        return "❌ resolution_note не может быть пустым — опиши что именно было исправлено."

    data = _load_issues(project_id)

    if issue_id not in data["issues"]:
        return (
            f"❌ Issue `{issue_id}` не найден в проекте `{project_id}`.\n"
            f"Открытые issues: {', '.join(k for k, v in data['issues'].items() if v['status'] == 'open') or 'нет'}"
        )

    issue = data["issues"][issue_id]

    if issue["status"] == "closed":
        return (
            f"ℹ️ Issue `{issue_id}` уже закрыт ({issue.get('resolved_date', '?')}).\n"
            f"Resolution: {issue.get('resolution_note', '—')}"
        )

    req_id = issue["req_id"]
    issue["status"] = "closed"
    issue["resolved_date"] = str(date.today())
    issue["resolution_note"] = resolution_note

    # Обновляем статистику
    data["stats"]["open"] = sum(1 for v in data["issues"].values() if v["status"] == "open")
    data["stats"]["closed"] = sum(1 for v in data["issues"].values() if v["status"] == "closed")

    _save_issues(data)

    # Проверяем оставшиеся blockers для этого req
    remaining_blockers = _open_blockers_for_req(data, req_id)
    remaining_all = _open_issues_for_req(data, req_id)

    lines = [
        f"✅ Issue **{issue_id}** закрыт.",
        "",
        f"| Поле | Значение |",
        f"|------|----------|",
        f"| Требование | `{req_id}` |",
        f"| Тип | {issue['issue_type']} |",
        f"| Severity | {issue['severity']} |",
        f"| Дата закрытия | {date.today()} |",
        "",
        f"**Resolution:** {resolution_note}",
        "",
        "---",
        "",
    ]

    if remaining_blockers:
        lines.append(f"⚠️ По `{req_id}` остаются открытые **blockers**: "
                     f"{', '.join(b['issue_id'] for b in remaining_blockers)}")
        lines.append(f"Верификация `{req_id}` заблокирована до их закрытия.")
    elif remaining_all:
        lines.append(f"ℹ️ По `{req_id}` остаются открытые non-blocker issues: "
                     f"{', '.join(i['issue_id'] for i in remaining_all)}")
        lines.append(f"✅ Blockers отсутствуют — можно вызвать `mark_req_verified` для `{req_id}`.")
    else:
        lines.append(f"✅ Все issues по `{req_id}` закрыты.")
        lines.append(f"Следующий шаг: `mark_req_verified(project_id='{project_id}', req_ids='[\"{req_id}\"]')`")

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
    BABOK 7.2 — Устанавливает статус 'verified' в репозитории 5.1.
    Предусловие: проверяет наличие открытых blocker-issues.

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
        Результат по каждому req: успешно верифицировано / предупреждение о blockers.
    """
    logger.info(f"mark_req_verified: project_id='{project_id}', req_ids='{req_ids}'")

    try:
        ids_list = json.loads(req_ids)
        if not isinstance(ids_list, list) or not ids_list:
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        return "❌ req_ids должен быть непустым JSON-списком: '[\"US-001\", \"FR-001\"]'"

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
            results.append(f"❌ `{req_id}` — не найден в репозитории 5.1")
            not_found_count += 1
            continue

        # Проверяем blockers
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
        f"# Результат верификации — {project_id}",
        "",
        f"**Date:** {date.today()}  ",
        f"**Processed:** {len(ids_list)} requirements  ",
        f"**Verified:** ✅ {verified_count}  ",
        f"**Of which forced (open blockers overridden):** ⚠️ {forced_count}  ",
        f"**Blocked:** ⚠️ {blocked_count}  ",
        f"**Not found:** ❌ {not_found_count}",
        "",
        "## Детали",
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
            f"✅ Статус `verified` установлен в репозитории 5.1.",
            f"Следующий шаг: `get_verification_report(project_id='{project_id}')` для сводного отчёта.",
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
    BABOK 7.2 — Генерирует сводный отчёт по верификации проекта.

    Содержит:
      - % verified из всех req
      - Топ-проблемы по типам характеристик
      - Список req с открытыми blocker-issues
      - Открытые issues с деталями
      - Вердикт: готово ли к Approve (5.5) и Validate (7.3)

    Сохраняет Markdown через save_artifact для передачи в 5.5 и 7.3.

    Args:
        project_id: Идентификатор проекта.

    Returns:
        Verification Report в Markdown.
    """
    logger.info(f"get_verification_report: project_id='{project_id}'")

    repo = _load_repo(project_id)
    all_reqs = repo.get("requirements", [])
    data = _load_issues(project_id)

    # Статистика по требованиям
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
            f"⚠️ Нет активных требований в репозитории проекта `{project_id}`.\n"
            f"Создай требования через инструменты 7.1 перед верификацией."
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

    # Статистика по issues
    all_issues = list(data["issues"].values())
    open_issues = [i for i in all_issues if i["status"] == "open"]
    open_blockers = [i for i in open_issues if i["severity"] == "blocker"]
    open_majors = [i for i in open_issues if i["severity"] == "major"]

    # Топ-проблемы по типам
    from collections import Counter
    issue_type_counts = Counter(i["issue_type"] for i in all_issues)
    open_type_counts = Counter(i["issue_type"] for i in open_issues)

    # req с open blockers
    blocked_req_ids = set(i["req_id"] for i in open_blockers)

    # Готовность к 5.5
    ready_for_approve = len(open_blockers) == 0 and verified_pct >= 80
    ready_label = "✅ Готово к Approve (5.5)" if ready_for_approve else "❌ Не готово к Approve (5.5)"

    lines = [
        f"<!-- BABOK 7.2 — Verification Report | Проект: {project_id} | {date.today()} -->",
        "",
        f"# 📋 Отчёт верификации требований",
        "",
        f"**Проект:** {project_id}  ",
        f"**Дата отчёта:** {date.today()}  ",
        f"**Готовность:** {ready_label}",
        "",
        "---",
        "",
        "## Сводка по требованиям",
        "",
        "| Показатель | Значение |",
        "|------------|----------|",
        f"| Total active reqs | {total} |",
        f"| ✅ Passed verification | {len(verified_reqs)} ({verified_pct}%) |",
        f"| &nbsp;&nbsp;↳ currently in `verified` status | {len(verified)} |",
        f"| ✅ Approved in 5.5 | {'— (5.5 has not run)' if approval_unknown else len(approved)} |",
        f"| 📝 Draft (not verified) | {len(draft)} |",
        "",
    ]

    # Прогресс-бар (текстовый)
    filled = int(verified_pct / 10)
    bar = "█" * filled + "░" * (10 - filled)
    lines.append(f"**Прогресс верификации:** `[{bar}]` {verified_pct}%")
    lines.append("")

    # Сводка по issues
    lines += [
        "## Сводка по issues верификации",
        "",
        "| Показатель | Значение |",
        "|------------|----------|",
        f"| Всего issues | {len(all_issues)} |",
        f"| 🚨 Открытых blockers | {len(open_blockers)} |",
        f"| ⚠️ Открытых majors | {len(open_majors)} |",
        f"| ✅ Закрытых issues | {data['stats'].get('closed', 0)} |",
        "",
    ]

    # Топ-проблемы
    if issue_type_counts:
        lines += [
            "## Топ-проблемы по типам",
            "",
            "| Тип проблемы | Всего | Открытых |",
            "|-------------|-------|----------|",
        ]
        for issue_type, count in issue_type_counts.most_common():
            open_count = open_type_counts.get(issue_type, 0)
            lines.append(f"| {issue_type} | {count} | {open_count} |")
        lines.append("")

    # Req заблокированные для 5.5
    if blocked_req_ids:
        lines += [
            "## 🚨 Требования с открытыми blockers",
            "",
            "> Эти требования не могут быть одобрены (5.5) до закрытия blockers.",
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
            "## Открытые issues",
            "",
            "| Issue ID | Req | Тип | Severity | Назначен | Дата |",
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

    # Вердикт и следующие шаги
    lines += [
        "---",
        "",
        "## Вердикт и следующие шаги",
        "",
    ]

    if ready_for_approve:
        lines += [
            "### ✅ Готово к передаче в следующие задачи",
            "",
            f"- **5.5 Approve Requirements:** {len(verified)} reqs currently in status `verified` are ready for baseline "
            f"({len(verified_reqs)} have passed verification in total).",
            f"- **7.3 Validate Requirements:** the verified reqs are ready for validation with the business.",
            "",
            "**Передай этот отчёт в 5.5:** используй `prepare_approval_package` с ссылкой на данный отчёт.",
        ]
    else:
        reasons = []
        if open_blockers:
            reasons.append(f"🚨 {len(open_blockers)} открытых blockers не закрыты")
        if verified_pct < 80:
            reasons.append(f"📊 Верифицировано только {verified_pct}% req (рекомендуется ≥ 80%)")
        if draft:
            reasons.append(f"📝 {len(draft)} требований ещё не верифицированы")

        lines += [
            "### ❌ Не готово к 5.5 Approve",
            "",
        ]
        for r in reasons:
            lines.append(f"- {r}")
        lines += [
            "",
            "**Действия:**",
            "1. Закрой все blocker issues через `resolve_verification_issue`.",
            f"2. Верифицируй оставшиеся req через `check_req_quality` → `mark_req_verified`.",
            f"3. Повтори `get_verification_report` для обновлённого статуса.",
        ]

    content = "\n".join(lines)
    save_artifact(content, prefix="7_2_verification_report", project_id=project_id)
    return content


if __name__ == "__main__":
    mcp.run()
