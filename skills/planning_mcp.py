"""
BABOK 3 — Business Analysis Planning and Monitoring
MCP-инструменты для планирования бизнес-анализа.

Tools:
  - suggest_ba_approach           — 3.1: choose a methodology (Predictive/Agile/Hybrid)
  - plan_ba_activities            — 3.1: elements .3/.4 — BA activities and timing
  - plan_stakeholder_engagement   — 3.2: Power/Interest stakeholder matrix + communication plan
  - plan_ba_governance            — 3.3: governance: change control, approval, escalation
  - plan_information_management   — 3.4: artifact storage and traceability architecture
  - evaluate_ba_performance       — 3.5: BA performance metrics + improvement plan
  - save_ba_plan                  — finalize: render the Markdown BA Plan report

Хранение:
  - {project}_ba_plan.json        — единый JSON-документ со всеми секциями плана
  - {project}_ba_plan_*.md        — Markdown-отчёт (через save_artifact)

Integration:
  Output: ba_plan.json. Sections 3.1b (ba_activities), 3.3 (governance) and 3.4
  (information_management) ARE read by other chapters — through the shared helpers in
  skills/common.py, so no chapter imports this module:
    - 4.4 prepare_communication_package — the planned level of detail per audience
    - 5.2 find_reusable_requirements    — the planned reuse scope and repository
    - 5.2 check_requirements_health     — the planned attribute set
    - 5.5 prepare_approval_package      — the methodology, from the planned timing
                                          form; the response deadline and the
                                          approvers, printed on the package
    - 5.5 record_approval_decision      — cross-checks an accountable/responsible
                                          decision against the planned authority
    - 5.4 resolve_cr                    — cross-checks `decided_by`; the escalation
                                          path in the CR Decision Record
    - 5.3 the prioritization session    — cross-checks the technique and the
                                          participants; the criteria in the report
    - 4.1 save_elicitation_plan         — the work period that covers elicitation
  3.2 additionally SEEDS the living stakeholder registry
  ({project}_stakeholder_registry.json) that 4.2 maintains and 7.4 reads, so the same
  people are not entered twice. Source fields only, and only on creation for the
  assumed ones — a re-run must never overwrite what elicitation established.
  3.3 also seeds 3.4's traceability level from the project criticality, insert-only.

  Every one of those is a CROSS-CHECK or a DEFAULT. No consumer overrides an explicit
  input with a planned value: the plan is what the BA meant to do, and the parameter is
  what the BA is doing.

  ⚠️ Still NOT consumed programmatically:
    - 7.3 takes its business context from 6.1/6.2, not from this plan.
  Wiring that is a planned feature, not current behavior — do not promise it to the
  BA in tool output.

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import (write_json_artifact,
    save_artifact, logger, DATA_DIR, data_path, normalize_project_id,
    APPROACH_MATRIX, REGULATORY_OVERRIDE, QUADRANT_STRATEGIES,
    parse_json_list as _parse_json_list,
    parse_json_str_list as _parse_string_list,
    pick_field, unrecognized_records_error,
    parse_json_dict_list as _parse_json_dict_list,
    update_stakeholder_registry_file, load_stakeholder_registry, stakeholder_identity,
    read_json_artifact, guard_artifact_errors,
    ABSTRACTION_LEVELS, PLANNABLE_ATTRIBUTES, REUSE_CATEGORIES,
    planned_attribute_set, reg_norm,
    EFFORT_LEVELS, TIMING_FORMS, normalize_task_ref, approach_to_timing_form,
    activities_section, planned_work_period,
    GOVERNANCE_TEMPLATES, TEMPLATE_FIELD_KEYS, MAX_APPROVAL_SLA_DAYS,
    PRIORITIZATION_TECHNIQUES,
)

mcp = FastMCP("BABOK_Planning")

PLAN_FILENAME = "ba_plan.json"

# ---------------------------------------------------------------------------
# Шаблоны (матрицы APPROACH_MATRIX, REGULATORY_OVERRIDE, QUADRANT_STRATEGIES
# перенесены в common.py — единственный источник истины, ADR-REVIEW-п5)
# ---------------------------------------------------------------------------

# The 3.3 criticality templates live in skills/common.py: the readers in 5.3/5.4/5.5
# decide "declared by the BA or from a template?" with the same table, and two copies
# of one decision rule is how the 5.5 dashboard and the baseline gate drifted apart.

# Display labels for the "Kept from the previous plan" line. Names only — the
# field -> template-key mapping itself is TEMPLATE_FIELD_KEYS, imported from common.
_FIELD_LABELS = {
    "change_control": "процесс изменений",
    "approval_process": "процесс согласования",
    "review_cycle": "цикл ревью",
    "escalation_path": "путь эскалации",
}

_SEEDED = "seeded"      # stored FACT; the wording is built by _trace_source_text


def _trace_source_text(level: str, criticality: str, source: str) -> str:
    """How the traceability level got its value, in words — or "" if the BA stated it.

    The FACT is stored and the SENTENCE is built here, by both the tool's reply and
    the BA Plan renderer, because only they can see the CURRENT criticality. A stored
    sentence naming the criticality at seed time went stale the moment 3.3 was
    re-planned, and the delivered document then showed `| Criticality | High |` one
    section above "(seeded from the 3.3 criticality: Low)" — two sections of one
    signed document disagreeing about a value one of them cites. The value itself is
    insert-only and does not move; only the explanation is recomputed.
    """
    # `startswith` accepts the SENTENCE the previous release stored as well as the
    # fact this one stores: without it, every project planned before the change lost
    # its label and delivered a platform default as the analyst's own decision.
    if source != _SEEDED and not str(source).startswith("seeded"):
        return ""
    if not criticality:
        # The criticality was removed or hand-edited into something unusable, and the
        # 3.3 table one section up now reads "not planned". Claiming the level came
        # from a criticality that section says does not exist is the contradiction
        # this helper was written to prevent.
        return f"задан по критичности из 3.3, которую 3.3 больше не указывает"
    if criticality != level:
        return (f"задан по критичности из 3.3, когда она была {level}; "
                f"сейчас 3.3 говорит {criticality} — укажите уровень заново, если он "
                f"должен следовать за ней")
    return f"задан по критичности из 3.3: {level}"


_TRACEABILITY_LEVELS = {
    "High":   "Полная трассировка: Бизнес-цели → Требования → Тест-кейсы → Код",
    "Medium": "Связь требований с задачами Jira и тест-кейсами",
    "Low":    "Базовая: нумерация требований, ссылки по необходимости",
}

# The eight 4.4 audience archetypes. Kept in sync with the `audience_role` Literal in
# elicitation_communicate_mcp.prepare_communication_package — Chapter 3 cannot import
# Chapter 4 (different phases), so this is a copy, and
# tests/test_ch3_info_mgmt_planning.py::TestVocabulariesStayInSync pins the two
# together. A plan row naming something else is still accepted (it may be a job
# title), just flagged: the consumer matches on either identifier.
_AUDIENCE_ARCHETYPES = (
    "Business Sponsor", "Manager", "Developer", "Architect / Tech Lead",
    "Tester", "End User", "Customer", "Domain SME",
)

_CLEAR_TEXT = "-"          # explicit clearing value for free-text parameters
_CLEAR_ENUM = "None"       # explicit clearing value for the Literal parameters

_ISSUE_RECOMMENDATIONS = {
    "нет шаблонов":        "📋 Внедрить стандартные шаблоны требований (SRS, User Story template)",
    "долгое согласование": "⚡ Сократить цепочку согласования, делегировать PO",
    "конфликты":           "🔍 Ввести обязательный peer-review требований перед передачей в разработку",
    "слабая трассировка":  "🔗 Настроить трассировку в Jira: Epic → Story → Test",
    "нет метрик":          "📊 Ввести метрики качества BA: Defect Rate, Rework Rate, Requirement Stability",
    "onboarding":          "🎓 Создать BA Playbook и базу знаний по проекту",
    "нет документации":    "📝 Создать единое хранилище артефактов с версионированием",
    "scope creep":         "🎯 Усилить Governance: формализовать процесс CR через 5.4",
}


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def _safe(project_id: str) -> str:
    return normalize_project_id(project_id)


def _plan_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{PLAN_FILENAME}")


def _load_plan(project_id: str) -> dict:
    path = _plan_path(project_id)
    if not os.path.exists(path):
        return _empty_plan(project_id)
    # Corrupt -> CorruptArtifactError, converted to a ❌ line at the tool boundary
    # by guard_artifact_errors. This module loads in EVERY phase, so a bare
    # json.load here turned one damaged plan file into a protocol error across
    # every session (the chapters-5 / 7.1-7.3 pattern).
    return read_json_artifact(path, "3.x BA plan")


def _save_plan(data: dict, project_id: str):
    path = _plan_path(project_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data["updated"] = str(date.today())
    write_json_artifact(path, data)


def _empty_plan(project_id: str) -> dict:
    return {
        "project_id": project_id,
        "created": str(date.today()),
        "updated": str(date.today()),
        "ba_approach": {},
        "stakeholder_engagement": {},
        "governance": {},
        "information_management": {},
        "performance": {},
    }


def _classify_stakeholder(influence: str, interest: str) -> tuple:
    """Возвращает (quadrant, strategy, frequency) по матрице Power/Interest."""
    key = (influence, interest)
    return QUADRANT_STRATEGIES.get(key, ("Crowd", "Monitor", "Квартально"))


# ---------------------------------------------------------------------------
# Инструменты
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def suggest_ba_approach(
    project_id: str,
    change_frequency: Literal["Low", "Medium", "High"],
    uncertainty: Literal["Low", "Medium", "High"],
    regulatory_need: bool = False,
    ba_notes: str = "",
) -> str:
    """
    BABOK 3.1 — Определить подход к бизнес-анализу (Predictive / Agile / Hybrid).

    Выбирает методологию по матрице BABOK на основе частоты изменений и неопределённости.
    При regulatory_need=True применяет compliance override.
    Сохраняет решение в {project}_ba_plan.json секция 'ba_approach'.

    Args:
        project_id: Идентификатор проекта
        change_frequency: Ожидаемая частота изменений требований (Low/Medium/High)
        uncertainty: Уровень неопределённости в проекте (Low/Medium/High)
        regulatory_need: True если проект требует строгого комплаенса/аудита
        ba_notes: Дополнительный контекст от BA
    """
    approach, techniques = APPROACH_MATRIX.get(
        (change_frequency, uncertainty),
        ("Hybrid", ["Workshops", "Prioritization"])
    )

    original_approach = approach
    regulatory_note = ""
    if regulatory_need and approach in REGULATORY_OVERRIDE:
        approach = REGULATORY_OVERRIDE[approach]
        regulatory_note = f"\n  ⚠️ Переопределено регуляторикой: {original_approach} → {approach}"

    plan = _load_plan(project_id)
    plan["ba_approach"] = {
        "change_frequency": change_frequency,
        "uncertainty": uncertainty,
        "regulatory_need": regulatory_need,
        "recommended_approach": approach,
        "techniques": techniques,
        "ba_notes": ba_notes,
        "decided_on": str(date.today()),
    }
    _save_plan(plan, project_id)

    approach_hints = {
        "Predictive (Waterfall)": "Чёткие требования с самого начала. Документируй тщательно.",
        "Hybrid": "Сочетай плановость и гибкость. Планируй фазы, адаптируйся внутри.",
        "Adaptive (Agile)": "Работай итерационно. User stories + backlog + ретроспективы.",
        "Hybrid (Agile + compliance gates)": "Agile-ритм + формальные точки согласования для аудита.",
        "Hybrid (с усиленным Governance)": "Гибридный подход + усиленный контроль изменений.",
    }
    hint = approach_hints.get(approach, "")

    return (
        f"✅ Подход к BA зафиксирован\n\n"
        f"  Проект:         {project_id}\n"
        f"  Частота изменений: {change_frequency}\n"
        f"  Неопределённость:  {uncertainty}\n"
        f"  Регуляторный:      {'Да' if regulatory_need else 'Нет'}"
        f"{regulatory_note}\n\n"
        f"  **Рекомендуемый подход: {approach}**\n"
        f"  Техники BABOK: {', '.join(techniques)}\n\n"
        f"  💡 {hint}\n\n"
        f"→ Следующий шаг: `plan_stakeholder_engagement` — построить карту стейкхолдеров.\n"
        f"   Перед этим можно: `plan_ba_activities` — какие задачи BABOK идут в каком "
        f"периоде и с какими трудозатратами (BABOK 3.1, элементы .3 и .4). 5.5 затем "
        f"берёт методологию оттуда, а не спрашивает вас снова."
    )


# The 3.2 map and the 4.2 registry describe the SAME people. Seeding here is what
# stops the BA entering them twice — and 4.2's file is the one 7.4 reads.
_REGISTRY_SOURCE = "3.2 план БА (карта Power/Interest)"

# Source data only. quadrant/strategy/comm_frequency are DERIVED from influence and
# interest, and a derived value inside a file another chapter mutates goes stale
# silently: an interview that updates influence via 4.2 would leave the quadrant wrong.
_REGISTRY_SEED_FIELDS = ("name", "role", "influence", "interest", "attitude", "contact")


def _attitude_conflicts(project_id: str, planned: list) -> list:
    """Where the plan and the living registry disagree about a stakeholder's attitude.

    Returns [(name, planned_attitude, recorded_attitude)]. Only reports a genuine
    disagreement: an entry the plan left unstated carries an assumed default and is
    not evidence of anything, so it is skipped.

    Never raises — this is advisory, and planning must not fail on a registry read.
    """
    try:
        registry = load_stakeholder_registry(project_id)
    except Exception:  # noqa: BLE001 — advisory only
        return []

    recorded = {stakeholder_identity(s): s for s in registry.get("stakeholders", [])}
    conflicts = []
    for s in planned:
        stated = str(s.get("attitude") or "").strip()
        if not stated:
            continue
        entry = recorded.get(stakeholder_identity(s))
        if not entry:
            continue
        known = str(entry.get("attitude") or "").strip()
        if known and known.lower() != stated.lower():
            conflicts.append((s.get("name") or s.get("role") or "—", stated, known))
    return conflicts


def _seed_stakeholder_registry(project_id: str, stakeholders: list) -> str:
    """Seeds the living stakeholder registry from the 3.2 map. Returns a report line.

    Never raises: the plan is already saved by the time this runs, and a planning tool
    must not become unusable because a downstream file could not be written.
    """
    incoming = []
    for s in stakeholders:
        entry = {f: s.get(f) for f in _REGISTRY_SEED_FIELDS if s.get(f)}
        if entry:
            incoming.append(entry)
    if not incoming:
        return ""

    try:
        result = update_stakeholder_registry_file(
            project_id, incoming, source=_REGISTRY_SOURCE,
            insert_defaults={
                "found_through": _REGISTRY_SOURCE,
                # A stakeholder known from planning has by definition not been
                # elicited yet. Insert-only, so a later 'Elicited' is never reset.
                "coverage_status": "Not covered",
                # Insert-only for the same reason: when the BA states no attitude,
                # 'Neutral' is an assumption, and an assumption must never overwrite
                # a Blocker/Champion an interview established.
                "attitude": "Neutral",
            },
        )
    except Exception as e:  # noqa: BLE001 — never let planning fail on this
        logger.warning(f"3.2 could not seed the stakeholder registry: {e}")
        return "\n⚠️ Реестр стейкхолдеров не обновлён — план БА сохранён.\n"

    if not result.get("saved"):
        return "\n⚠️ Записать реестр стейкхолдеров не удалось — план БА сохранён.\n"

    return (
        f"\n📇 Реестр стейкхолдеров: добавлено {len(result['added'])}, "
        f"обновлено {len(result['updated'])} "
        f"(тот же живой реестр, который поддерживает 4.2 `update_stakeholder_registry`).\n"
    )


@mcp.tool()
@guard_artifact_errors
def plan_stakeholder_engagement(
    project_id: str,
    stakeholders_json: str,
) -> str:
    """
    BABOK 3.2 — Составить матрицу вовлечения стейкхолдеров (Power/Interest Grid).

    Классифицирует каждого стейкхолдера по квадранту (Key Players / Context Setters /
    Subjects / Crowd) и назначает стратегию и частоту коммуникации.
    Сохраняет реестр в {project}_ba_plan.json секция 'stakeholder_engagement'.

    Args:
        project_id: Идентификатор проекта
        stakeholders_json: JSON-массив стейкхолдеров. Формат объекта:
            {
              "name": "Иван Петров",
              "role": "Product Owner",
              "influence": "High",
              "interest": "High",
              "attitude": "Champion",
              "contact": "ivan@company.com"
            }
            influence/interest: Low | Medium | High
            attitude: Champion | Neutral | Blocker
    """
    # Validating that the input PARSES is not validating that it FITS: this JSON is
    # written by an LLM, so a list of strings for a "list of stakeholders" parameter is
    # an ordinary case, and indexing it as objects raised AttributeError — a protocol
    # error out of an MCP tool instead of a readable answer (class CH3-A / CH4-A).
    # The other Chapter 3 tools were moved onto the shared validators; this one was the
    # last raw parse left in the module.
    stakeholders, shape_error = _parse_json_dict_list(
        stakeholders_json, "stakeholders_json",
        example='[{"name": "John Smith", "role": "Product Owner", '
                '"influence": "High", "interest": "High"}]')
    if shape_error:
        return shape_error

    if not stakeholders:
        return "⚠️ Список стейкхолдеров пуст. Добавь хотя бы одного стейкхолдера."

    valid = []
    seed_source = []
    errors = []
    for i, s in enumerate(stakeholders):
        name = s.get("name", "")
        influence = s.get("influence", "")
        interest = s.get("interest", "")
        if not name:
            errors.append(f"Стейкхолдер #{i+1}: отсутствует поле 'name'")
            continue
        if influence not in ("Low", "Medium", "High"):
            errors.append(f"'{name}': influence должен быть Low/Medium/High, получено '{influence}'")
            continue
        if interest not in ("Low", "Medium", "High"):
            errors.append(f"'{name}': interest должен быть Low/Medium/High, получено '{interest}'")
            continue
        quadrant, strategy, frequency = _classify_stakeholder(influence, interest)
        valid.append({
            "name": name,
            "role": s.get("role", ""),
            "influence": influence,
            "interest": interest,
            "attitude": s.get("attitude", "Neutral"),
            "contact": s.get("contact", ""),
            "quadrant": quadrant,
            "strategy": strategy,
            "comm_frequency": frequency,
        })
        # The registry is seeded from what the BA ACTUALLY supplied, not from the plan
        # record above: that one carries a synthesized `attitude` default, and a
        # fabricated value is indistinguishable from a stated one once merged, so it
        # would overwrite an attitude an interview established. Defaults belong in
        # insert_defaults, which applies on creation only.
        seed_source.append(s)

    if errors:
        return "❌ Ошибки в stakeholders_json:\n" + "\n".join(f"  • {e}" for e in errors)

    plan = _load_plan(project_id)
    plan["stakeholder_engagement"] = {
        "stakeholders": valid,
        "total": len(valid),
        "updated_on": str(date.today()),
    }
    _save_plan(plan, project_id)

    # Read BEFORE seeding: an explicitly stated attitude wins as an ordinary field, so
    # after the seed the registry already agrees and there would be nothing to report.
    conflicts = _attitude_conflicts(project_id, seed_source)

    # Seed the living registry 4.2 maintains and 7.4 reads, so the same people are
    # not entered twice. Only ever reached once the plan itself is saved.
    registry_note = _seed_stakeholder_registry(project_id, seed_source)

    # Quadrant statistics
    quadrants = {}
    for s in valid:
        q = s["quadrant"]
        quadrants[q] = quadrants.get(q, 0) + 1

    blockers = [s["name"] for s in valid if s.get("attitude") == "Blocker"]

    lines = [
        # "map", not "registry": the living registry is a different artifact, and this
        # tool now reports on both in the same message.
        f"✅ Карта стейкхолдеров сохранена\n\n",
        f"  Project:          {project_id}\n",
        f"  Stakeholders:     {len(valid)}\n\n",
        f"**Распределение по квадрантам:**\n",
    ]
    for q, cnt in sorted(quadrants.items()):
        lines.append(f"  {q}: {cnt}\n")

    lines.append("\n**Реестр:**\n")
    for s in valid:
        lines.append(
            f"  • {s['name']} ({s['role']}) — {s['quadrant']} | {s['comm_frequency']}\n"
            f"    Стратегия: {s['strategy']}\n"
        )

    if blockers:
        lines.append(f"\n⚠️ Blockers: {', '.join(blockers)} — требуют особого внимания\n")

    # The blocker line above describes the PLAN just submitted, which is right — that
    # is what this tool reports on. But an attitude STATED here overwrites what an
    # interview recorded, and doing that silently is how a Blocker flagged in
    # elicitation disappears. The overwrite is intended (a stated value is the BA's
    # judgment, not an assumption); it just must not be invisible.
    if conflicts:
        lines.append(
            "\n⚠️ Этот план переопределяет отношение, записанное при выявлении:\n"
        )
        for name, planned, recorded in conflicts:
            lines.append(
                f"  {name}: при выявлении записано {recorded}, этот план указывает "
                f"{planned} — в реестре теперь {planned}\n"
            )
        lines.append(
            "  Если интервью — более свежее свидетельство, укажите это здесь заново "
            "либо поправьте через `update_stakeholder_registry` (4.2).\n"
        )

    lines.append(registry_note)

    lines.append(
        f"\n→ Следующий шаг: `plan_ba_governance` — определи правила принятия решений."
    )
    return "".join(lines)


def _sane_governance_section(section) -> dict:
    """Coerce a stored 3.3 section into the shapes the merge code and renderer assume.

    The renderer already did `', '.join(governance.get('decision_makers', []))`, so a
    file that is valid JSON with `"decision_makers": "CFO"` rendered "C, F, O" into a
    DELIVERED document — three invented approvers — and this tool, the only one that
    can repair the section, died on the same value. Unusable values are dropped so the
    merge falls back to "not planned" and the BA can simply plan it again.
    """
    if not isinstance(section, dict):
        return {}
    out = dict(section)
    for key in ("decision_makers", "declared", "carried_over"):
        if key in out:
            if isinstance(out[key], list):
                out[key] = [v for v in out[key] if isinstance(v, str) and v.strip()]
            else:
                del out[key]
    for key in ("change_control", "approval_process", "review_cycle",
                "escalation_path", "approval_timing_note", "ba_notes",
                "project_criticality", "defined_on"):
        if key in out and not isinstance(out[key], str):
            del out[key]
    # Guarded for VALUE, like the traceability level and the technique. Type alone was
    # not enough: a hand-edited "Catastrophic" — or an ordinary lower-cased "high" —
    # left the readers returning nothing while the BA Plan's Source column cited "the
    # Catastrophic template", naming a template that does not exist and vouching for
    # the junk beside it.
    if out.get("project_criticality") not in GOVERNANCE_TEMPLATES:
        out.pop("project_criticality", None)
    raw_days = out.get("approval_sla_days")
    if "approval_sla_days" in out and not (
            isinstance(raw_days, int) and not isinstance(raw_days, bool)
            and 0 <= raw_days <= MAX_APPROVAL_SLA_DAYS):
        del out["approval_sla_days"]
    if "prioritization" in out:
        if isinstance(out["prioritization"], dict):
            out["prioritization"] = _sane_prioritization_block(out["prioritization"])
        else:
            del out["prioritization"]
    return out


def _sane_prioritization_block(block: dict) -> dict:
    """Coerce the element .3 block — the same guards, one nesting level deeper.

    `planned_prioritization` in common.py protects the 5.3 cross-check, but the BA
    Plan renderer reads the STORED block directly: without this, a hand-edited
    `"participants": "PO"` printed two planned scorers, P and O, into a delivered
    document, and `"technique": "Gut feel"` was rendered as the planned technique
    while the reader that 5.3 uses reported none. Present keys only — inventing the
    three keys here would make an empty block truthy for the renderer's `any()`.
    """
    out = dict(block)
    for key in ("participants", "criteria"):
        if key in out:
            out[key] = ([v for v in out[key] if isinstance(v, str) and v.strip()]
                        if isinstance(out[key], list) else [])
    if "technique" in out and out["technique"] not in PRIORITIZATION_TECHNIQUES:
        out["technique"] = ""
    return out


@mcp.tool()
@guard_artifact_errors
def plan_ba_governance(
    project_id: str,
    project_criticality: Literal["", "Low", "Medium", "High"] = "",
    decision_makers_json: str = "",
    change_control_process: str = "",
    ba_notes: str = "",
    approval_process: str = "",
    approval_sla_days: int = -1,
    approval_timing_note: str = "",
    review_cycle: str = "",
    escalation_path: str = "",
    prioritization_technique: Literal[
        "", "None", "MoSCoW", "WSJF", "ImpactEffort", "TimeBoxing"] = "",
    prioritization_participants_json: str = "",
    prioritization_criteria_json: str = "",
) -> str:
    """
    BABOK 3.3 — Определить план governance бизнес-анализа.

    Records decision authority, change control, approvals and their timing, and the
    prioritization approach. Project criticality supplies the DEFAULT wording for the
    process fields; anything you state yourself always wins and is labelled as yours
    wherever it is printed. Saves to {project}_ba_plan.json, section 'governance'.

    Re-running MERGES: a parameter left empty keeps its previous value. Clear a text
    field with "-", a list with "[]", an enum with "None", the SLA with 0.

    Args:
        project_id: Project identifier
        project_criticality: Project criticality (Low/Medium/High). Required the first
            time — it selects the default wording for every process field.
        decision_makers_json: JSON list of roles WITH DECISION AUTHORITY (BABOK 3.3 .1
            approvers), e.g. '["Sponsor", "PO", "Lead BA"]'. Required the first time.
        change_control_process: Change control process (optional — from a template)
        ba_notes: Additional agreements
        approval_process: BABOK 3.3 .4 — who approves and how (optional — template)
        approval_sla_days: BABOK 3.3 .4 — response deadline in BUSINESS days, 1-365.
            0 clears it; leave unset to keep the stored value.
        approval_timing_note: BABOK 3.3 .4 — event-based timing a number cannot
            express, e.g. "to the monthly CAB".
        review_cycle: BABOK 3.3 .1 — review cadence (optional — from a template)
        escalation_path: BABOK 3.3 .1 — escalation path (optional — from a template)
        prioritization_technique: BABOK 3.3 .3 — the technique prioritization is
            expected to use: MoSCoW / WSJF / ImpactEffort / TimeBoxing. "None"
            clears it. A closed vocabulary, identical to the `method` of a 5.3
            prioritization session.
        prioritization_participants_json: BABOK 3.3 .3 — JSON list of the roles
            expected to score, e.g. '["Product Owner", "Head of Risk"]'
        prioritization_criteria_json: BABOK 3.3 .3 — JSON list of the criteria the
            scoring is meant to weigh, e.g. '["cost", "risk", "value"]'
    """
    plan = _load_plan(project_id)
    previous = _sane_governance_section(plan.get("governance"))
    kept = []
    declared = set(previous.get("declared", []))
    # THREE states of provenance, not two. `declared` is new in this feature, so a
    # plan written before it cannot say which fields the BA authored — and an ABSENT
    # key is not the same statement as an EMPTY one: empty is the current writer
    # positively recording "the BA declared nothing", absent is "nobody knows".
    # Collapsing them regenerated the analyst's own change-control text from the
    # template on the very re-run this feature exists to encourage.
    # Carried-over fields are kept but NOT credited to the BA, and the set is
    # persisted so the second re-run does not undo what the first one preserved.
    carried = set(previous.get("carried_over", []))
    if "declared" not in previous:
        carried |= {f for f in TEMPLATE_FIELD_KEYS if previous.get(f)}

    # --- criticality: required DATA, optional PARAMETER ---------------------
    # Optional because merge would otherwise force the BA to retype it on every
    # refinement; still required, because without it every template default falls
    # silently to Medium.
    if project_criticality == "":
        criticality = previous.get("project_criticality", "")
        if criticality:
            kept.append("критичность")
    else:
        criticality = project_criticality
    if criticality not in GOVERNANCE_TEMPLATES:
        # The same wording defect Fix 10 diagnosed for `decision_makers_json`, and the
        # value guard added in this wave made it MORE reachable: a stored criticality
        # can now vanish on its own. On a plan that already holds other 3.3 content,
        # "the first time 3.3 is planned" is false and sends the BA looking for a file
        # that is right there.
        if previous:
            return ("❌ В сохранённом плане 3.3 нет `project_criticality` либо там "
                    "значение, которого платформа не знает.\n"
                    "   Оно выбирает формулировку по умолчанию для каждого поля процесса, "
                    "поэтому его надо указать заново: Low / Medium / High.\n"
                    "   Всё остальное, что вы запланировали в 3.3, не тронуто.")
        return ("❌ При первом планировании 3.3 `project_criticality` обязателен — он "
                "выбирает формулировку по умолчанию для каждого поля процесса.\n"
                "   Допустимо: Low / Medium / High")

    # --- decision makers ---------------------------------------------------
    if decision_makers_json == "":
        decision_makers = previous.get("decision_makers", [])
        if decision_makers:
            kept.append("принимающих решения")
    else:
        decision_makers, error = _parse_string_list(
            decision_makers_json, "decision_makers_json")
        if error:
            return error
    if not decision_makers:
        # Two different refusals, because the BA is in two different situations. On an
        # already-planned project "required the first time 3.3 is planned" is simply
        # false, and it sends them looking for a plan file that is right there.
        if previous.get("decision_makers"):
            return ("❌ `decision_makers_json` очистить нельзя: 5.4 и 5.5 сверяют с ним "
                    "каждое записанное решение, и пустой список молча выключил бы эти "
                    "проверки.\n"
                    "   Передайте вместо этого исправленный список: "
                    "'[\"Sponsor\", \"PO\", \"Lead BA\"]'\n"
                    f"   Currently planned: {', '.join(previous['decision_makers'])}")
        return ("❌ При первом планировании 3.3 `decision_makers_json` обязателен — без "
                "него 5.4 и 5.5 не с чем сверять записанное решение.\n"
                "   Пример: '[\"Sponsor\", \"PO\", \"Lead BA\"]'")

    # --- the four template-backed text fields ------------------------------
    # `declared` is a RECORD, not a comparison: a BA who states wording identical to
    # the template still stated it, and a source recovered by comparing strings would
    # be a lookalike condition drifting from the fact it imitates.
    values = {}
    for field, param in (("change_control", change_control_process),
                         ("approval_process", approval_process),
                         ("review_cycle", review_cycle),
                         ("escalation_path", escalation_path)):
        template = GOVERNANCE_TEMPLATES[criticality][TEMPLATE_FIELD_KEYS[field]]
        if param == "":
            if previous.get(field) and (field in declared or field in carried):
                values[field] = previous[field]
                kept.append(_FIELD_LABELS[field])
            else:
                # Undeclared fields are machine content: they must be regenerated
                # when the criticality they were generated for changes. The marker is
                # dropped with the value it described — the shape guard can delete a
                # damaged field, and a `declared` entry outliving its value made the
                # NEXT run stamp "declared in 3.3" on generated template text, in the
                # audit documents 5.4 and 5.5 render from it.
                declared.discard(field)
                carried.discard(field)
                values[field] = template
        elif param == _CLEAR_TEXT:
            declared.discard(field)
            carried.discard(field)
            values[field] = template
        else:
            declared.add(field)
            carried.discard(field)      # the BA has now authored it for real
            values[field] = param

    # --- element .4: the timing of approvals -------------------------------
    if approval_sla_days == -1:
        sla_days = previous.get("approval_sla_days", 0)
        if sla_days:
            kept.append("срок согласования")
    elif not 0 <= approval_sla_days <= MAX_APPROVAL_SLA_DAYS:
        return (f"❌ `approval_sla_days` должен быть от 0 до "
                f"{MAX_APPROVAL_SLA_DAYS} рабочих дней (0 очищает его). "
                f"Получено: {approval_sla_days}")
    else:
        sla_days = approval_sla_days

    if approval_timing_note == "":
        timing_note = previous.get("approval_timing_note", "")
        if timing_note:
            kept.append("примечание к срокам согласования")
    elif approval_timing_note == _CLEAR_TEXT:
        timing_note = ""
    else:
        timing_note = approval_timing_note

    # --- ba_notes ----------------------------------------------------------
    if ba_notes == "":
        notes = previous.get("ba_notes", "")
        if notes:
            kept.append("заметки")
    elif ba_notes == _CLEAR_TEXT:
        notes = ""
    else:
        notes = ba_notes

    # --- element .3: Plan Prioritization Approach --------------------------
    # The three parts are independent: clearing the technique must not silently
    # discard the participants the BA listed in a different call.
    prev_prio = previous.get("prioritization", {})
    if not isinstance(prev_prio, dict):
        prev_prio = {}

    if prioritization_technique == "":
        technique = prev_prio.get("technique", "")
        if technique:
            kept.append("технику приоритизации")
    elif prioritization_technique == _CLEAR_ENUM:
        technique = ""
    else:
        technique = prioritization_technique

    if prioritization_participants_json == "":
        prio_participants = prev_prio.get("participants", [])
        if prio_participants:
            kept.append("участников приоритизации")
    else:
        prio_participants, error = _parse_string_list(
            prioritization_participants_json, "prioritization_participants_json")
        if error:
            return error

    if prioritization_criteria_json == "":
        prio_criteria = prev_prio.get("criteria", [])
        if prio_criteria:
            kept.append("критерии приоритизации")
    else:
        prio_criteria, error = _parse_string_list(
            prioritization_criteria_json, "prioritization_criteria_json")
        if error:
            return error

    prioritization = {
        # Defence in depth: the Literal only constrains the MCP call, and the stored
        # value already passed _sane_prioritization_block on the way in.
        "technique": technique if technique in PRIORITIZATION_TECHNIQUES else "",
        "participants": prio_participants,
        "criteria": prio_criteria,
    }

    governance = {
        "project_criticality": criticality,
        "decision_makers": decision_makers,
        "change_control": values["change_control"],
        "approval_process": values["approval_process"],
        "review_cycle": values["review_cycle"],
        "escalation_path": values["escalation_path"],
        "approval_sla_days": sla_days,
        "approval_timing_note": timing_note,
        "prioritization": prioritization,
        "declared": sorted(declared),
        # Kept from a plan written before `declared` existed: the value survives, but
        # nobody can say whether the BA authored it or the old writer generated it, so
        # it is never credited to them in the Source column.
        "carried_over": sorted(carried),
        "ba_notes": notes,
        "defined_on": previous.get("defined_on", str(date.today())),
        "updated_on": str(date.today()),
    }

    plan["governance"] = governance
    _save_plan(plan, project_id)

    criticality_hints = {
        "High": "⚠️ Высокая критичность: формализуй каждый CR, ничего не меняй без подписи.",
        "Medium": "📋 Средняя критичность: стандартный process через PO/backlog.",
        "Low": "✅ Низкая критичность: гибкий процесс, фиксируй только ключевые решения.",
    }

    def _src(field):
        # The same three states the report's Source column and the shared readers use.
        # This echo knew only two, so a legacy re-run printed the analyst's own text
        # with "(from the High template)" beside it — and the template's wording for
        # that field was something else entirely.
        if field in declared:
            return "заявлено"
        if field in carried:
            return "перенесено из прежнего плана"
        return f"из шаблона {criticality}"

    deadline_line = (f"  Срок ответа:        {sla_days} рабочих дней\n"
                     if sla_days else "")
    timing_line = f"  Сроки согласования: {timing_note}\n" if timing_note else ""

    # Every part the BA may plan is echoed, including criteria on their own: a ✅ over
    # content the analyst cannot see recorded is how dropped input goes unnoticed.
    prio_line = ""
    if any(prioritization.values()):
        segments = [prioritization["technique"] or "техника не задана"]
        if prioritization["participants"]:
            segments.append(
                f"participants: {', '.join(prioritization['participants'])}")
        if prioritization["criteria"]:
            segments.append(f"criteria: {', '.join(prioritization['criteria'])}")
        prio_line = f"  Prioritization:     {' | '.join(segments)}\n"

    return (
        f"✅ План governance записан\n\n"
        f"  Проект:             {project_id}\n"
        f"  Критичность:        {criticality}\n"
        f"  Принимают решения:  {', '.join(decision_makers)}\n\n"
        f"  Процесс изменений:  {values['change_control']} ({_src('change_control')})\n"
        f"  Согласование:       {values['approval_process']} ({_src('approval_process')})\n"
        f"  Цикл ревью:         {values['review_cycle']} ({_src('review_cycle')})\n"
        f"  Escalation:         {values['escalation_path']} ({_src('escalation_path')})\n"
        f"{deadline_line}{timing_line}{prio_line}\n"
        + (f"  Сохранено из прежнего плана: {', '.join(kept)}\n\n" if kept else "")
        + f"  {criticality_hints[criticality]}\n\n"
        f"→ Следующий шаг: `plan_information_management` — определить архитектуру хранения."
    )


_ARCHETYPE_KEYS = {reg_norm(a) for a in _AUDIENCE_ARCHETYPES}


def _sane_info_section(section) -> dict:
    """Coerce a stored 3.4 section into the shapes the merge code and renderer assume.

    Guarding only the section itself was not enough: one level down, every branch
    called `.get()` / `.values()` / `[...]` on whatever was on disk, so a file that is
    valid JSON with `"reuse": "oops"` still killed this tool — the only tool that can
    overwrite a damaged section. A bare string where a list belongs is worse than a
    crash: `"storage_tools": "Confluence"` was accepted and echoed one entry per
    CHARACTER. Unusable values are dropped, so the merge falls back to "not planned"
    and the BA can simply plan it again.
    """
    if not isinstance(section, dict):
        return {}
    out = dict(section)
    for key in ("storage_tools", "artifact_types"):
        value = out.get(key)
        if isinstance(value, list):
            out[key] = [s for s in value if isinstance(s, str)]
        else:
            out.pop(key, None)
    rows = out.get("abstraction_levels")
    if isinstance(rows, list):
        out["abstraction_levels"] = [r for r in rows if isinstance(r, dict)]
    else:
        out.pop("abstraction_levels", None)
    for key in ("reuse", "attributes"):
        if not isinstance(out.get(key), dict):
            out.pop(key, None)
    for key in ("access_rules", "ba_notes", "traceability_level",
                "traceability_description", "traceability_source"):
        if key in out and not isinstance(out[key], str):
            out.pop(key, None)
    return out


def _sane_activities_section(section) -> dict:
    """Coerce a stored 3.1b section into the shapes the writer and renderer assume.

    Same reasoning as `_sane_info_section`: this is the only tool that can
    overwrite a damaged section, so it must survive reading one. `periods` is
    normalised by the shared reader, which both this module and the chapter-4/5
    consumers go through — one coercion, not three.
    """
    if not isinstance(section, dict):
        return {}
    out = dict(activities_section({"ba_activities": section}))
    for key in ("timing_form", "form_source", "ba_notes", "planned_on"):
        if key in out and not isinstance(out[key], str):
            out.pop(key, None)
    # Value, not just type: the merge path is the first that takes a form from stored
    # JSON rather than from the validated Literal, so a hand-edited "sprints" would be
    # written back, silence the "form is not set" warning and make the tool promise a
    # reader that then refuses.
    if out.get("timing_form") not in TIMING_FORMS:
        out.pop("timing_form", None)
    constraints = out.get("timing_constraints")
    out["timing_constraints"] = ([c for c in constraints if isinstance(c, str)]
                                 if isinstance(constraints, list) else [])
    if not isinstance(out.get("generated"), bool):
        out.pop("generated", None)
    return out


def _merge_text(new: str, previous, default: str = "") -> str:
    """Merge rule for a free-text field: "" keeps, "-" clears, anything else sets."""
    if new == "":
        return previous if previous is not None else default
    return "" if new == _CLEAR_TEXT else new


@mcp.tool()
@guard_artifact_errors
def plan_information_management(
    project_id: str,
    storage_tools_json: str = "",
    traceability_level: Literal["", "Low", "Medium", "High"] = "",
    artifact_types_json: str = "",
    access_rules: str = "",
    ba_notes: str = "",
    abstraction_levels_json: str = "",
    reuse_target_scope: Literal["", "None", "initiative", "program",
                                "division", "enterprise"] = "",
    reuse_repository: str = "",
    reuse_categories_json: str = "",
    attributes_preset: Literal["", "None", "Minimum", "Standard", "Full"] = "",
    additional_attributes_json: str = "",
) -> str:
    """
    BABOK 3.4 — Спланировать управление информацией BA.

    Defines where and how requirements and artifacts are stored, the traceability
    level, how much detail each audience gets, how requirements will be reused, and
    which attributes this project maintains.
    Saves to {project}_ba_plan.json, section 'information_management'.

    Re-running MERGES: a parameter left empty keeps its previous value. Clear a list
    with "[]", a text field with "-", an enum with "None". Two exceptions:
    `storage_tools` cannot be cleared at all (a plan with nowhere to store anything is
    an unfinished task), and clearing `access_rules` restores its standing default
    rather than emptying it.

    What reads this plan:
      - 4.4 prepare_communication_package  — the planned level of detail per audience
      - 5.2 find_reusable_requirements     — the planned reuse scope and repository
      - 5.2 check_requirements_health      — the planned attribute set

    Args:
        project_id: Project identifier
        storage_tools_json: JSON list of storage tools, e.g. '["Confluence", "Jira"]'
        traceability_level: Traceability level (Low/Medium/High). Default Medium.
        artifact_types_json: JSON list of artifact types, e.g. '["User Story", "BRD"]'
        access_rules: Access rules (who reads, who edits)
        ba_notes: Additional agreements
        abstraction_levels_json: BABOK 3.4 element .2 — JSON list of
            '[{"audience": "Business Sponsor", "level": "Summary", "note": "..."}]'.
            level: Summary | Standard | Detailed. `audience` may be one of the eight
            4.4 archetypes or a job title from the stakeholder map — 4.4 matches on
            either.
        reuse_target_scope: BABOK 3.4 element .4 — the reuse level this project aims
            for: initiative | program | division | enterprise. Becomes 5.2's DEFAULT;
            an explicit value passed to 5.2 always wins.
        reuse_repository: Where reusable requirements live and how other BAs reach it.
        reuse_categories_json: JSON list of reuse candidate categories, e.g.
            '["regulatory", "business rules"]'.
        attributes_preset: BABOK 3.4 element .6 — which attribute set this project
            maintains: Minimum | Standard | Full. 5.2's health audit checks exactly
            this set.
        additional_attributes_json: JSON list of attributes added on top of the preset.
    """
    plan = _load_plan(project_id)
    # Coerced, not just type-checked at the top: a file that is valid JSON with the
    # wrong shape anywhere inside the section passes read_json_artifact, and every
    # merge branch below reads it. This tool is the only one that can overwrite a
    # damaged section, so it must not be the tool that dies on it.
    previous = _sane_info_section(plan.get("information_management"))
    warnings = []
    kept = []

    # --- storage tools: mergeable, but never clearable ---------------------
    if storage_tools_json == "":
        storage_tools = previous.get("storage_tools", [])
        if not storage_tools:
            return ("❌ При первом планировании 3.4 `storage_tools_json` обязателен.\n"
                    "   Пример: '[\"Confluence\", \"Jira\"]'")
        kept.append("инструменты хранения")
    else:
        storage_tools, error = _parse_string_list(
            storage_tools_json, "storage_tools_json", required=True)
        if error:
            return error

    # --- traceability level ------------------------------------------------
    # BABOK Figure 3.3.1 makes 3.4 a consumer of the governance approach: the change
    # control and traceability standards together establish the product baselines. So
    # the 3.3 criticality supplies a DEFAULT here — insert-only. It never overrides a
    # level the BA stated, and it never rolls a stored one back when the criticality
    # later changes (the defect `insert_defaults` was created for in 3.2).
    trace_source = ""
    criticality = _sane_governance_section(
        plan.get("governance")).get("project_criticality")
    if traceability_level == "":
        stored = previous.get("traceability_level")
        # Guarded for VALUE, not only for type. A hand-edited level used to be echoed
        # under its own name while `.get(level, ...)` silently supplied Medium's
        # DESCRIPTION — a delivered plan naming a traceability level that does not exist.
        if stored in _TRACEABILITY_LEVELS:
            level = stored
            kept.append("уровень трассировки")
            # The LABEL is carried with the value it describes. It used to be written
            # only on the branch that performs the seed, so any ordinary follow-up call
            # — adding artifact types, a reuse scope — silently dropped it while the
            # seeded value stayed, and the guarantee that a default is visible as a
            # default lasted exactly one call.
            stored_source = previous.get("traceability_source", "")
            # The previous release stored the SENTENCE ("seeded from the 3.3
            # criticality: High"); this one stores the FACT. Without this line every
            # project planned before the change silently lost its label on the next
            # 3.4 call and delivered a platform default as the analyst's decision —
            # the same absent-versus-new-shape class as `declared`, in the sibling
            # field one function away, introduced by the fix for it.
            trace_source = (_SEEDED if stored_source.startswith("seeded")
                            else stored_source)
        else:
            if criticality in _TRACEABILITY_LEVELS:
                level = criticality
                trace_source = _SEEDED
            else:
                level = "Medium"
    else:
        level = traceability_level
    trace_desc = _TRACEABILITY_LEVELS[level]

    # --- artifact types ----------------------------------------------------
    if artifact_types_json == "":
        artifact_types = previous.get("artifact_types", [])
        if artifact_types:
            kept.append("типы артефактов")
    else:
        artifact_types, error = _parse_string_list(artifact_types_json, "artifact_types_json")
        if error:
            return error

    # --- element .2: level of abstraction ----------------------------------
    if abstraction_levels_json == "":
        abstraction_levels = previous.get("abstraction_levels", [])
        if abstraction_levels:
            kept.append("уровни детализации")
    else:
        rows, error = _parse_json_dict_list(
            abstraction_levels_json, "abstraction_levels_json",
            example='[{"audience": "Business Sponsor", "level": "Summary", "note": "..."}]')
        if error:
            return error
        abstraction_levels = []
        seen = {}
        for i, row in enumerate(rows, 1):
            audience = str(row.get("audience") or "").strip()
            if not audience:
                return (f"❌ `abstraction_levels_json`: в строке {i} нет `audience`.\n"
                        f"   Every row needs an audience — an archetype from 4.4 or a "
                        f"job title from the stakeholder map.")
            row_level = str(row.get("level") or "").strip()
            if row_level not in ABSTRACTION_LEVELS:
                return (f"❌ `abstraction_levels_json`: в строке {i} уровень "
                        f"`{row_level or '(пусто)'}`.\n"
                        f"   Allowed: {', '.join(ABSTRACTION_LEVELS)}")
            key = reg_norm(audience)
            # Compared through reg_norm, because that is how the CONSUMER matches:
            # a raw-casing check told the BA that "business sponsor" would "match only
            # by job title" while 4.4 resolved it as the archetype perfectly well — a
            # confident false claim, and one that also fired on the second row of any
            # case-differing duplicate.
            if key not in _ARCHETYPE_KEYS:
                warnings.append(
                    f"⚠️ `{audience}` не входит в архетипы аудиторий 4.4 — сопоставление "
                    f"пойдёт только по должности.")
            entry = {"audience": audience, "level": row_level,
                     "note": str(row.get("note") or "")}
            if key in seen:
                warnings.append(f"⚠️ `{audience}` встречается дважды — побеждает последняя строка.")
                abstraction_levels[seen[key]] = entry
            else:
                seen[key] = len(abstraction_levels)
                abstraction_levels.append(entry)

    # --- element .4: reuse -------------------------------------------------
    prev_reuse = previous.get("reuse") or {}
    if reuse_target_scope == "":
        target_scope = prev_reuse.get("target_scope", "")
        if target_scope:
            kept.append("scope переиспользования")
    else:
        target_scope = "" if reuse_target_scope == _CLEAR_ENUM else reuse_target_scope

    repository = _merge_text(reuse_repository, prev_reuse.get("repository"))
    if reuse_repository == "" and prev_reuse.get("repository"):
        kept.append("репозиторий переиспользования")

    if reuse_categories_json == "":
        reuse_categories = prev_reuse.get("categories", [])
        if reuse_categories:
            kept.append("категории переиспользования")
    else:
        reuse_categories, error = _parse_string_list(
            reuse_categories_json, "reuse_categories_json")
        if error:
            return error
        unlisted = [c for c in reuse_categories if c.lower() not in REUSE_CATEGORIES]
        if unlisted:
            # BABOK's list is explicitly open-ended, so this is a note, not a refusal.
            warnings.append(
                f"⚠️ Категории вне списка BABOK: {', '.join(unlisted)}. "
                f"Сохранены — список в руководстве не исчерпывающий.")

    # --- element .6: attributes -------------------------------------------
    prev_attrs = previous.get("attributes") or {}
    if attributes_preset == "":
        preset = prev_attrs.get("preset", "")
        if preset:
            kept.append("набор атрибутов")
    else:
        preset = "" if attributes_preset == _CLEAR_ENUM else attributes_preset

    if additional_attributes_json == "":
        additional = prev_attrs.get("additional", [])
        if additional:
            kept.append("дополнительные атрибуты")
    else:
        additional, error = _parse_string_list(
            additional_attributes_json, "additional_attributes_json")
        if error:
            return error
        unknown = [a for a in additional if a not in PLANNABLE_ATTRIBUTES]
        if unknown:
            # Planning an attribute the model cannot store would recreate the
            # "declared but dead" class inside this very feature.
            return (f"❌ Эта платформа такого не хранит: {', '.join(unknown)}.\n"
                    f"   Планируемые атрибуты: {', '.join(PLANNABLE_ATTRIBUTES)}\n"
                    f"   BABOK перечисляет ещё author, risks и urgency (с. 45-46), но в "
                    f"модели требования для них нет поля, поэтому 5.2 никогда не смогла бы "
                    f"их проверить.")

    # Tracked like every other merged field: a "Kept" line the BA is meant to trust
    # instead of opening the JSON must not under-report what actually survived.
    if access_rules == "" and previous.get("access_rules"):
        kept.append("правила доступа")
    if ba_notes == "" and previous.get("ba_notes"):
        kept.append("заметки БА")

    info_mgmt = {
        "storage_tools": storage_tools,
        "traceability_level": level,
        "traceability_description": trace_desc,
        # Stored, not just printed in the reply: the reply is ephemeral and the BA
        # Plan is the document that gets signed. Recomputed on every run rather than
        # merged — the moment the BA states a level, the value stops being a default,
        # and a stale "seeded" label would misdescribe their own decision.
        "traceability_source": trace_source,
        "artifact_types": artifact_types,
        # `-` restores the standing default rather than emptying the field: an empty
        # Access line in the delivered BA Plan is worse than the default it replaced.
        "access_rules": _merge_text(access_rules, previous.get("access_rules"),
                                    "BA правит, остальные читают") or "BA правит, остальные читают",
        "ba_notes": _merge_text(ba_notes, previous.get("ba_notes")),
        "abstraction_levels": abstraction_levels,
        "reuse": {"target_scope": target_scope, "repository": repository,
                  "categories": reuse_categories},
        "attributes": {"preset": preset, "additional": additional},
        "defined_on": str(date.today()),
    }

    plan["information_management"] = info_mgmt
    _save_plan(plan, project_id)

    trace_note = _trace_source_text(level, criticality, trace_source)
    out = [
        "✅ План управления информацией записан",
        "",
        f"  Project:           {project_id}",
        f"  Tools:             {', '.join(storage_tools)}",
        f"  Traceability:      {level} — {trace_desc}"
        + (f" ({trace_note})" if trace_note else ""),
    ]
    if artifact_types:
        out.append(f"  Типы артефактов:   {', '.join(artifact_types)}")
    out.append(f"  Access:            {info_mgmt['access_rules']}")

    if abstraction_levels:
        out.append("")
        out.append("  Уровень детализации (читает 4.4):")
        for row in abstraction_levels:
            suffix = f" — {row['note']}" if row["note"] else ""
            out.append(f"    • {row['audience']}: {row['level']}{suffix}")

    if target_scope or repository or reuse_categories:
        out.append("")
        out.append("  Переиспользование (читает 5.2):")
        if target_scope:
            out.append(f"    • Целевой scope: {target_scope} — 5.2 по нему ранжирует "
                       f"(ничего ниже он не исключает)")
        if repository:
            out.append(f"    • Repository:   {repository}")
        if reuse_categories:
            out.append(f"    • Categories:   {', '.join(reuse_categories)}")

    resolved = planned_attribute_set({"information_management": info_mgmt})
    if resolved:
        attrs, label = resolved
        out.append("")
        out.append(f"  Атрибуты, которые аудирует 5.2 ({label}):")
        out.append(f"    {', '.join(attrs)}")
        if "owner" not in attrs:
            out.append("    ⚠️ `owner` в этот набор не входит — аудит здоровья 5.2 "
                       "перестанет его спрашивать.")

    if kept:
        out.append("")
        out.append(f"  ↩️ Сохранено из прежнего плана: {', '.join(kept)}")

    for w in warnings:
        out.append(f"\n{w}")

    out.append("")
    out.append("→ Следующий шаг: `evaluate_ba_performance` — задать метрики эффективности.")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 3.1 elements .3 (BA Activities) and .4 (Timing of BA Work) — B3-1
# ---------------------------------------------------------------------------
#
# BABOK Figure 3.1.2 (printed p. 27) ties the FORM of the breakdown to the approach:
# predictive names the activities for each deliverable and then the tasks; adaptive
# divides the work into iterations, names the deliverables of each, then the
# activities. The skeletons below are those two shapes, expressed in the platform's
# own task ids so a consumer can match them.
#
# The word "Phase" is deliberately NOT used in period names: `python phase.py`
# switches the platform's SESSION phase, and a BA reading "Phase 2" in a plan would
# reasonably think it is a phase to switch to.
_SKELETON_ITERATIONS = (
    {"name": "Iteration 1", "tasks": ["4", "6.1"],
     "deliverables": ["Результаты выявления", "Понимание as-is"],
     "effort": "High", "when": ""},
    {"name": "Iteration 2", "tasks": ["5", "7"],
     "deliverables": ["Приоритизированный бэклог", "Спецификации требований"],
     "effort": "Medium", "when": ""},
)

_SKELETON_PHASES = (
    {"name": "Этап 1 — Discovery", "tasks": ["3", "4"],
     "deliverables": ["План БА", "Результаты выявления"],
     "effort": "High", "when": ""},
    {"name": "Этап 2 — Анализ", "tasks": ["6"],
     "deliverables": ["Модели as-is / to-be", "Стратегия изменений"],
     "effort": "High", "when": ""},
    {"name": "Этап 3 — Спецификация и согласование", "tasks": ["7", "5"],
     "deliverables": ["Спецификации требований", "Согласованный baseline"],
     "effort": "Medium", "when": ""},
)


@mcp.tool()
@guard_artifact_errors
def plan_ba_activities(
    project_id: str,
    timing_form: Literal["", "phases", "iterations"] = "",
    periods_json: str = "",
    timing_constraints_json: str = "",
    ba_notes: str = "",
) -> str:
    """
    BABOK 3.1 — plan the BA activities (element .3) and their timing (element .4).

    Optional step, run after `suggest_ba_approach`. Records WHICH BABOK tasks are
    done in which work period, with what effort, and what constrains the timing.
    Saves to {project}_ba_plan.json, section 'ba_activities'.

    Two chapters read this section afterwards:
      - 5.5 prepare_approval_package takes the methodology from the timing form,
        so the BA no longer states it a second time;
      - 4.1 save_elicitation_plan names the period that covers elicitation work.

    Args:
        project_id: Project identifier
        timing_form: "phases" (predictive) or "iterations" (adaptive). Leave empty
            to derive it from the approach chosen in 3.1.
        periods_json: JSON list of work periods. Leave empty for a starting
            skeleton generated from the approach. Format:
            '[{"name": "Iteration 1", "tasks": ["4.1", "4.2"],
               "deliverables": ["Elicitation results"], "effort": "High",
               "when": "Aug 2026"}]'
            `tasks` are BABOK task ids of this platform (3.1-7.6) or a whole
            chapter ("4").
        timing_constraints_json: JSON list of what constrains the timing, e.g.
            '["regulatory deadline 2026-12-31", "vendor available from September"]'
        ba_notes: Additional context from the BA
    """
    periods_in, error = _parse_json_dict_list(
        periods_json, "periods_json",
        example='[{"name": "Iteration 1", "tasks": ["4.1"], "effort": "High"}]')
    if error:
        return error
    constraints, error = _parse_string_list(
        timing_constraints_json, "timing_constraints_json",
        example='["regulatory deadline 2026-12-31"]')
    if error:
        return error

    plan = _load_plan(project_id)
    approach_section = plan.get("ba_approach")
    approach_label = ""
    if isinstance(approach_section, dict):
        raw_label = approach_section.get("recommended_approach")
        approach_label = raw_label if isinstance(raw_label, str) else ""
    derived = approach_to_timing_form(approach_label)

    # EVERY parameter here is optional, so "empty" has to mean KEEP, not WIPE — the
    # way `plan_information_management` already treats its own. A replace would let
    # the re-run this tool itself invites ("edit and re-run to make them yours")
    # silently discard the periods, the constraints and the notes the BA typed, and
    # revert a DECLARED timing form to the derived one — a value 5.5 prints on the
    # package that goes out for signature. It would also break the project rule that
    # recorded data is never deleted.
    previous = _sane_activities_section(plan.get("ba_activities"))
    kept = []

    warnings = []
    if timing_form:
        form, form_source = timing_form, "заявлено БА"
        if derived and derived != timing_form:
            warnings.append(
                f"⚠️ Вы заявили `{timing_form}`, а подход из 3.1 "
                f"({approach_label}) подразумевает `{derived}`. Сохранено то, что вы "
                f"заявили — решение за вами.")
    elif previous.get("timing_form"):
        form = previous["timing_form"]
        form_source = previous.get("form_source", "")
        kept.append(f"форму привязки ко времени ({form})")
        if derived and derived != form and form_source.startswith("выведено из подхода "):
            warnings.append(
                f"⚠️ Сохранённая форма выведена из подхода, отличного от того, что план "
                f"рекомендует сейчас ({approach_label}). Перезапустите с "
                f"`timing_form=\"{derived}\"`, чтобы сменить её, либо оставьте как есть.")
    elif derived:
        form, form_source = derived, f"выведено из подхода {approach_label}"
    else:
        form, form_source = "", ""

    # Nothing to derive AND nothing typed: there is nothing to store. An empty
    # section would claim the planning happened and would pass the "empty plan"
    # gate in save_ba_plan.
    if not form and not periods_in and not previous.get("periods"):
        reason = (f"подход `{approach_label}` лежит между предиктивным и адаптивным, "
                  f"поэтому форма из него не следует"
                  if approach_label else
                  "3.1 для этого проекта ещё не запускалась")
        return (
            f"⚠️ Ничего не записано — {reason}.\n\n"
            f"  Скажите, в какой форме идёт работа, и я это сохраню:\n"
            f"    • `timing_form=\"phases\"`     — задачи БА идут по этапам\n"
            f"    • `timing_form=\"iterations\"` — задачи БА идут итеративно\n\n"
            f"  (BABOK 3.1, элемент .4 — угадывать я это не буду: значение попадает в "
            f"пакет согласования, который уходит на подпись.)"
        )

    kept_skeleton_regenerated = False
    if periods_in:
        generated, source_periods = False, periods_in
    elif (previous.get("periods") and periods_json.strip() != "[]"
            and not (previous.get("generated")
                     and previous.get("timing_form") != form)):
        # Keep what is already recorded — including a skeleton the BA has since taken
        # over. Regenerating here is what discarded their work.
        generated = bool(previous.get("generated"))
        source_periods = previous["periods"]
        kept.append(f"периодов: {len(source_periods)}")
    else:
        # A stored SKELETON is 100% machine output built FOR a particular form, so
        # carrying it across a form change delivered a `phases` plan tabulating
        # `Iteration 1/2` — under a line claiming the BA's work had been preserved.
        # Nothing of theirs is at risk here: periods they typed are never `generated`.
        kept_skeleton_regenerated = bool(previous.get("periods")
                                         and previous.get("generated"))
        generated = True
        source_periods = [dict(p) for p in
                          (_SKELETON_ITERATIONS if form == "iterations"
                           else _SKELETON_PHASES)]

    unknown_refs = []
    off_scale_efforts = []
    periods = []
    for index, raw in enumerate(source_periods, start=1):
        raw_tasks = raw.get("tasks")
        if isinstance(raw_tasks, str):
            raw_tasks = [raw_tasks]
        elif not isinstance(raw_tasks, list):
            raw_tasks = []
        tasks = []
        for candidate in raw_tasks:
            ref = normalize_task_ref(candidate)
            if ref:
                if ref not in tasks:
                    tasks.append(ref)
            else:
                unknown_refs.append(str(candidate))
        raw_deliverables = raw.get("deliverables")
        deliverables = ([d for d in raw_deliverables if isinstance(d, str)]
                        if isinstance(raw_deliverables, list) else [])
        effort = str(raw.get("effort") or "")
        if effort and effort not in EFFORT_LEVELS:
            off_scale_efforts.append(effort)
        periods.append({
            "name": str(raw.get("name") or f"Period {index}"),
            "tasks": tasks,
            "deliverables": deliverables,
            "effort": effort,
            "when": str(raw.get("when") or ""),
        })

    if not form:
        warnings.append(
            "⚠️ Форма привязки ко времени не задана, поэтому 5.5 "
            "`prepare_approval_package` НЕ возьмёт методологию из этого плана — "
            "`approach` придётся передавать туда руками. Перезапустите с "
            "`timing_form=\"phases\"` или `timing_form=\"iterations\"`, чтобы это закрыть.")
    if unknown_refs:
        warnings.append(
            f"⚠️ Это не id задач BABOK этой платформы, поэтому они отброшены: "
            f"{', '.join(unknown_refs)}. Используйте 3.1-7.6 либо главу целиком (\"4\"). "
            f"Глава 8 пока не реализована.")
    if off_scale_efforts:
        warnings.append(
            f"⚠️ Трудозатраты вне шкалы Low/Medium/High, сохранены как есть: "
            f"{', '.join(off_scale_efforts)}.")

    # "" means "not passed" -> keep; "[]" is the explicit clear, the same idiom
    # plan_information_management documents. With "[]" as the DEFAULT the two were
    # indistinguishable and the constraints could not be cleared by any input at all.
    if (not constraints and previous.get("timing_constraints")
            and timing_constraints_json.strip() != "[]"):
        constraints = previous["timing_constraints"]
        kept.append(f"ограничений по срокам: {len(constraints)}")
    # `-` clears, "" keeps — the convention the rest of this module already uses.
    merged_notes = _merge_text(ba_notes, previous.get("ba_notes"))
    if ba_notes == "" and merged_notes:
        kept.append("заметки БА")

    plan["ba_activities"] = {
        "timing_form": form,
        "form_source": form_source,
        "generated": generated,
        "periods": periods,
        "timing_constraints": constraints,
        "ba_notes": merged_notes,
        "planned_on": str(date.today()),
    }
    _save_plan(plan, project_id)

    lines = [
        "✅ Работы БА и их сроки записаны\n",
        f"  Project:      {project_id}",
        f"  Форма привязки: {form or '(не задана)'}"
        + (f" ({form_source})" if form_source else ""),
        f"  Periods:      {len(periods)}"
        + ("  ℹ️ перегенерировано из подхода — прежние были заготовкой под другую форму"
           if kept_skeleton_regenerated else
           "  ℹ️ сгенерировано из подхода — отредактируйте и перезапустите, чтобы сделать своими"
           if generated else ""),
        "",
    ]
    for period in periods:
        lines.append(
            f"  • {period['name']}"
            f" — tasks: {', '.join(period['tasks']) or '—'}"
            f" | deliverables: {', '.join(period['deliverables']) or '—'}"
            f" | effort: {period['effort'] or '—'}"
            f" | when: {period['when'] or '—'}")
    if constraints:
        lines += ["", f"  Ограничения по срокам ({len(constraints)}):"]
        lines += [f"    – {c}" for c in constraints]
    if merged_notes:
        lines += ["", f"  BA notes: {merged_notes}"]
    if kept:
        lines += ["", f"  ↩️ Сохранено из прежнего плана: {', '.join(kept)}"]
    if warnings:
        lines += [""] + [f"  {w}" for w in warnings]
    # Printed unconditionally, this block contradicted the warnings above it: with no
    # timing form 5.5 takes nothing from here, and with no chapter-4 task in any period
    # 4.1 prints nothing. Claim only what this particular plan actually feeds.
    readers = []
    if form:
        readers.append(
            "  • 5.5 `prepare_approval_package` — берёт методологию из формы привязки, "
            "чтобы вам не указывать её дважды")
    # Ask the CONSUMER's own reader, not a lookalike condition: 4.1 queries for the
    # task `4.1`, so a period tagged only 4.2/4.3 answers nothing, and a footer built
    # on `startswith("4.")` promised output that never appears.
    if planned_work_period({"ba_activities": {"periods": periods}}, "4.1"):
        readers.append(
            "  • 4.1 `save_elicitation_plan` — называет период, который покрывает "
            "работы по выявлению, и запланированные трудозатраты")
    if readers:
        lines += ["", "ℹ️ Что теперь это читает:"] + readers
    lines += [
        "",
        "→ Следующий шаг: `plan_stakeholder_engagement` — построить карту стейкхолдеров.",
    ]
    return "\n".join(lines)


@mcp.tool()
@guard_artifact_errors
def evaluate_ba_performance(
    project_id: str,
    current_issues_json: str = "[]",
    metrics_json: str = "[]",
    ba_notes: str = "",
) -> str:
    """
    BABOK 3.5 — Оценить эффективность BA и составить план улучшений.

    Сопоставляет выявленные проблемы с рекомендациями, фиксирует метрики.
    Сохраняет в {project}_ba_plan.json секция 'performance'.

    Args:
        project_id: Идентификатор проекта
        current_issues_json: JSON-список текущих проблем, напр. '["нет шаблонов", "scope creep"]'
        metrics_json: JSON-список метрик для мониторинга, напр.
            '[{"name": "Defect Rate", "baseline": "15%", "target": "5%"}]'
        ba_notes: Дополнительный контекст
    """
    current_issues, error = _parse_string_list(current_issues_json, "current_issues_json")
    if error:
        return error

    # metrics entries may be objects ({name, baseline, target}) or plain strings
    metrics, error = _parse_json_list(metrics_json, "metrics_json")
    if error:
        return error

    # Normalise the object entries. `metric` and `title` are the near-misses an LLM
    # writes for `name`; reading only `name` rendered "• :  → < 10% per sprint" into the
    # delivered BA Plan — a bullet with no subject — while this tool answered "recorded".
    METRIC_NAME_KEYS = ("name", "metric", "title")
    normalized_metrics = []
    named = 0
    for m in metrics:
        if isinstance(m, dict):
            name = pick_field(m, *METRIC_NAME_KEYS)
            if name:
                named += 1
            entry = dict(m)
            entry["name"] = name
            normalized_metrics.append(entry)
        else:
            normalized_metrics.append(m)
            named += 1
    if metrics and named == 0:
        return unrecognized_records_error(
            "metrics_json", METRIC_NAME_KEYS,
            '[{"name": "Defect Rate", "baseline": "15%", "target": "5%"}]')
    metrics = normalized_metrics

    # Сопоставляем проблемы с рекомендациями
    recommendations = []
    unmatched = []
    for issue in current_issues:
        matched = False
        for keyword, rec in _ISSUE_RECOMMENDATIONS.items():
            if keyword.lower() in issue.lower():
                recommendations.append({"issue": issue, "recommendation": rec})
                matched = True
                break
        if not matched:
            unmatched.append(issue)
            recommendations.append({
                "issue": issue,
                "recommendation": f"⚠️ Требует ручного анализа: «{issue}»"
            })

    if not current_issues:
        recommendations.append({
            "issue": "нет явных проблем",
            "recommendation": "✅ Провести ретроспективу раз в квартал для профилактики."
        })

    performance = {
        "current_issues": current_issues,
        "recommendations": recommendations,
        "metrics": metrics,
        "ba_notes": ba_notes,
        "assessed_on": str(date.today()),
    }

    plan = _load_plan(project_id)
    plan["performance"] = performance
    _save_plan(plan, project_id)

    lines = [
        f"✅ Оценка эффективности BA зафиксирована\n\n",
        f"  Проект:   {project_id}\n",
        f"  Проблем:  {len(current_issues)}\n",
        f"  Метрик:   {len(metrics)}\n\n",
    ]

    if recommendations:
        lines.append("**Рекомендации по улучшению:**\n")
        for r in recommendations:
            lines.append(f"  {r['recommendation']}\n")

    if metrics:
        lines.append("\n**Метрики для мониторинга:**\n")
        for m in metrics:
            if isinstance(m, dict):
                name = m.get("name", "")
                baseline = m.get("baseline", "")
                target = m.get("target", "")
                lines.append(f"  • {name}: {baseline} → {target}\n")
            else:
                lines.append(f"  • {m}\n")

    lines.append(
        f"\n→ BA-план для проекта `{project_id}` готов.\n"
        f"  Вызови `save_ba_plan` для генерации Markdown-отчёта."
    )
    return "".join(lines)


@mcp.tool()
@guard_artifact_errors
def save_ba_plan(
    project_id: str,
) -> str:
    """
    Финализировать BA-план: сгенерировать Markdown-отчёт.

    Создаёт читаемый документ из всех секций {project}_ba_plan.json
    через save_artifact(). JSON остаётся как контракт для downstream задач.

    Args:
        project_id: Идентификатор проекта
    """
    plan = _load_plan(project_id)

    approach = plan.get("ba_approach", {})
    engagement = plan.get("stakeholder_engagement", {})
    governance = plan.get("governance", {})
    info_mgmt = plan.get("information_management", {})
    performance = plan.get("performance", {})
    activities = _sane_activities_section(plan.get("ba_activities"))
    # The coercion always supplies `periods` and `timing_constraints`, so the dict is
    # truthy even when nothing usable survived — and both the gate below and the
    # renderer test this value. Without the question "was anything actually planned?",
    # a damaged section produced an empty "## 3.1b" heading with a "(not set)" form
    # inside a DELIVERED document, and an empty section let an otherwise empty plan
    # through the gate.
    if not any([activities.get("timing_form"), activities.get("periods"),
                activities.get("timing_constraints"), activities.get("ba_notes")]):
        activities = {}

    # `performance` counts too: the report renders a 3.5 section when it is present,
    # so omitting it here refused a plan that actually had content.
    if not any([approach, activities, engagement, governance, info_mgmt, performance]):
        return (
            "⚠️ BA-план пуст или не заполнен.\n"
            "Пройди шаги 3.1–3.5 перед сохранением отчёта."
        )

    def _notes_block(section: dict) -> list:
        """Renders the BA's own notes for a section.

        Every 3.x tool collects `ba_notes` ("additional agreements", "additional
        context"). Dropping them from the report loses context the BA deliberately
        recorded — the report is the deliverable, the JSON is not.
        """
        note = str(section.get("ba_notes", "") or "").strip()
        return [f"> **BA notes:** {note}", ""] if note else []

    md_lines = [
        f"# BA Plan — {project_id}",
        f"**Дата:** {date.today()}",
        "",
        "---",
        "",
    ]

    if approach:
        md_lines += [
            "## 3.1 Подход к бизнес-анализу",
            "",
            f"| Параметр | Значение |",
            f"|----------|---------|",
            f"| Частота изменений | {approach.get('change_frequency', '')} |",
            f"| Неопределённость | {approach.get('uncertainty', '')} |",
            f"| Регуляторный | {'Да' if approach.get('regulatory_need') else 'Нет'} |",
            f"| **Рекомендуемый подход** | **{approach.get('recommended_approach', '')}** |",
            f"| Техники BABOK | {', '.join(approach.get('techniques', []))} |",
            "",
        ]
        md_lines += _notes_block(approach)

    if activities:
        form = activities.get("timing_form", "")
        source = activities.get("form_source", "")
        md_lines += [
            "## 3.1b Работы БА и их сроки",
            "",
            f"- **Форма привязки:** {form or '(не задана)'}"
            + (f" ({source})" if source else ""),
        ]
        if activities.get("generated"):
            md_lines.append(
                "- ℹ️ Сгенерировано из подхода — правьте через `plan_ba_activities`.")
        # A DERIVED form records the approach it came from, and that record stays true
        # forever — so a later 3.1 re-run leaves two ADJACENT sections of this one
        # delivered document disagreeing: 3.1 recommends X while 3.1b cites a
        # derivation from Y. Found by reading the rendered report, not by an assertion.
        # A form the BA DECLARED is not evidence about the approach either way, so it
        # is never flagged.
        derived_from = (source[len("выведено из подхода "):]
                        if source.startswith("выведено из подхода ") else "")
        # `approach` is only guaranteed to be a dict inside `if approach:` above; this
        # branch runs under `if activities:`, so a plan whose `ba_approach` is null,
        # "" or [] reached .get() here. planning_mcp loads in EVERY phase, so that
        # AttributeError is a protocol error in every session, not a ❌ line.
        current_approach = (str(approach.get("recommended_approach", "") or "")
                            if isinstance(approach, dict) else "")
        if derived_from and current_approach and derived_from != current_approach:
            md_lines.append(
                f"- ⚠️ Эта форма выведена из **{derived_from}**, который план больше не "
                f"рекомендует (сейчас **{current_approach}**). Чтобы её сменить, "
                f"перезапустите `plan_ba_activities` с явным `timing_form` — простой "
                f"перезапуск сохранит записанное здесь.")
        periods = activities.get("periods", [])
        if periods:
            md_lines += [
                "",
                "| Период | Задачи BABOK | Результаты | Трудозатраты | Когда |",
                "|--------|-------------|--------------|--------|------|",
            ]
            for period in periods:
                tasks = period.get("tasks")
                tasks = ", ".join(t for t in tasks if isinstance(t, str)) \
                    if isinstance(tasks, list) else ""
                deliverables = period.get("deliverables")
                deliverables = ", ".join(d for d in deliverables if isinstance(d, str)) \
                    if isinstance(deliverables, list) else ""
                md_lines.append(
                    f"| {period.get('name', '')} | {tasks or '—'} | "
                    f"{deliverables or '—'} | {period.get('effort', '') or '—'} | "
                    f"{period.get('when', '') or '—'} |")
        constraints = activities.get("timing_constraints", [])
        if constraints:
            md_lines += ["", "**Ограничения по срокам:**", ""]
            md_lines += [f"- {c}" for c in constraints]
        md_lines.append("")
        md_lines += _notes_block(activities)

    if engagement:
        stakeholders = engagement.get("stakeholders", [])
        md_lines += [
            "## 3.2 Вовлечение стейкхолдеров",
            "",
            f"| Стейкхолдер | Роль | Квадрант | Стратегия | Частота |",
            f"|-------------|------|----------|-----------|---------|",
        ]
        for s in stakeholders:
            md_lines.append(
                f"| {s['name']} | {s['role']} | {s['quadrant']} | {s['strategy']} | {s['comm_frequency']} |"
            )
        md_lines.append("")

    # Same coercion as the writer. Without it the join below turned a stored
    # `"decision_makers": "CFO"` into three approvers — "C, F, O" — inside a
    # delivered document; guarding only the section was never enough.
    governance = _sane_governance_section(governance)
    # Bound OUTSIDE the block: the 3.4 section below explains the traceability level
    # against it, and a project can have a 3.4 plan with no 3.3 one.
    gov_criticality = governance.get("project_criticality", "") if governance else ""
    if governance:
        gov_declared = set(governance.get("declared", []))
        gov_carried = set(governance.get("carried_over", []))

        def _gov_src(field):
            # Three states, because there are three. A value carried over from a plan
            # written before this feature is genuinely of unknown origin: crediting the
            # analyst for it would be as wrong as calling it a template default.
            if field in gov_declared:
                return "заявлено в 3.3"
            if field in gov_carried:
                return "перенесено из прежнего плана"
            return (f"из шаблона {gov_criticality}" if gov_criticality
                    else "значение шаблона по умолчанию")

        md_lines += [
            "## 3.3 Governance",
            "",
            f"| Параметр | Значение | Источник |",
            f"|----------|---------|--------|",
            f"| Criticality | {gov_criticality or '—'} | "
            f"{'заявлено в 3.3' if gov_criticality else 'не запланировано'} |",
            f"| Принимающие решения | {', '.join(governance.get('decision_makers', []))} | заявлено в 3.3 |",
            f"| Процесс изменений | {governance.get('change_control', '')} | {_gov_src('change_control')} |",
            f"| Approval | {governance.get('approval_process', '')} | {_gov_src('approval_process')} |",
            f"| Цикл ревью | {governance.get('review_cycle', '')} | {_gov_src('review_cycle')} |",
            f"| Escalation | {governance.get('escalation_path', '')} | {_gov_src('escalation_path')} |",
        ]
        if governance.get("approval_sla_days"):
            md_lines.append(
                f"| Срок ответа | {governance['approval_sla_days']} рабочих дней "
                f"| заявлено в 3.3 |")
        if governance.get("approval_timing_note"):
            md_lines.append(
                f"| Сроки согласования | {governance['approval_timing_note']} "
                f"| заявлено в 3.3 |")
        # Element .3 appears only when something was planned: an empty block in a
        # document that goes to people reads as a gap in the analysis, not as an
        # unused option. The block is already coerced by _sane_governance_section.
        prio = governance.get("prioritization")
        if isinstance(prio, dict) and any(prio.values()):
            md_lines += [
                "",
                "**Подход к приоритизации (BABOK 3.3 .3)**",
                "",
                f"- **Техника:** {prio.get('technique') or 'не задана'}",
            ]
            if prio.get("participants"):
                md_lines.append(
                    f"- **Participants:** {', '.join(prio['participants'])}")
            if prio.get("criteria"):
                md_lines.append(f"- **Criteria:** {', '.join(prio['criteria'])}")
        md_lines.append("")
        md_lines += _notes_block(governance)

    # Pre-existing sibling of the writer's guard: a section of the wrong shape reached
    # .get() here too, at every nesting level. Same coercion as the writer, so the
    # renderer skips unusable values rather than failing the whole report.
    info_mgmt = _sane_info_section(info_mgmt)
    if info_mgmt:
        # The source is stated for the same reason the 3.3 table one section up has a
        # Source column: an unlabelled default reads as the BA's decision. Built here
        # from the CURRENT criticality, so it cannot contradict the table above it.
        trace_note = _trace_source_text(info_mgmt.get("traceability_level", ""),
                                        gov_criticality,
                                        info_mgmt.get("traceability_source", ""))
        md_lines += [
            "## 3.4 Управление информацией",
            "",
            f"- **Tools:** {', '.join(info_mgmt.get('storage_tools', []))}",
            f"- **Traceability:** {info_mgmt.get('traceability_level', '')} — "
            f"{info_mgmt.get('traceability_description', '')}"
            + (f" *({trace_note})*" if trace_note else ""),
            f"- **Access:** {info_mgmt.get('access_rules', '')}",
        ]
        artifact_types = info_mgmt.get("artifact_types", [])
        if artifact_types:
            md_lines.append(f"- **Типы артефактов:** {', '.join(artifact_types)}")
        md_lines.append("")

        # Each block appears only when it holds data: an empty table in a document
        # that goes to people reads as a gap in the analysis, not as an unused option.
        rows = info_mgmt.get("abstraction_levels") or []
        if rows:
            md_lines += [
                "### Уровень детализации по аудиториям",
                "",
                "_Читается главой 4.4 при подготовке коммуникационного пакета._",
                "",
                "| Аудитория | Уровень | Примечание |",
                "|---|---|---|",
            ]
            for row in rows:
                md_lines.append(
                    f"| {row.get('audience', '—')} | {row.get('level', '—')} | "
                    f"{row.get('note') or '—'} |")
            md_lines.append("")

        reuse = info_mgmt.get("reuse") or {}
        if any(reuse.values()):
            md_lines += ["### Переиспользование требований", ""]
            if reuse.get("target_scope"):
                md_lines.append(f"- **Целевой scope:** {reuse['target_scope']} "
                                f"(значение, которое применяет 5.2 по умолчанию)")
            if reuse.get("repository"):
                md_lines.append(f"- **Repository:** {reuse['repository']}")
            if reuse.get("categories"):
                md_lines.append(
                    f"- **Категории-кандидаты:** {', '.join(reuse['categories'])}")
            md_lines.append("")

        resolved = planned_attribute_set({"information_management": info_mgmt})
        if resolved:
            attrs, label = resolved
            md_lines += [
                "### Атрибуты требований",
                "",
                f"- **Поддерживаемый набор** ({label}): {', '.join(attrs)}",
                "- _Аудит здоровья 5.2 проверяет ровно этот набор._",
                "",
            ]

        md_lines += _notes_block(info_mgmt)

    if performance:
        recs = performance.get("recommendations", [])
        md_lines += ["## 3.5 Эффективность BA", ""]
        for r in recs:
            md_lines.append(f"- {r['recommendation']}")
        md_lines.append("")
        metrics = performance.get("metrics", [])
        if metrics:
            md_lines.append("**Метрики:**")
            for m in metrics:
                if isinstance(m, dict):
                    md_lines.append(f"- {m.get('name', '')}: {m.get('baseline', '')} → {m.get('target', '')}")
                else:
                    md_lines.append(f"- {m}")
            md_lines.append("")
        md_lines += _notes_block(performance)

    md_content = "\n".join(md_lines)
    artifact_result = save_artifact(md_content, f"3_ba_plan_{_safe(project_id)}", project_id=project_id)

    plan["status"] = "finalized"
    plan["finalized_on"] = str(date.today())
    _save_plan(plan, project_id)

    json_path = _plan_path(project_id)

    return (
        f"✅ План БА финализирован\n\n"
        f"  Проект: {project_id}\n"
        f"  📄 JSON (запись плана): `{json_path}`\n"
        f"  {artifact_result}\n\n"
        f"**Следующий шаг:**\n"
        f"• Глава 4.1 — подготовка к выявлению\n\n"
        f"ℹ️ Что читается автоматически, а что нет:\n"
        f"  • Стейкхолдеры из 3.2 УЖЕ засеяны в живой реестр, который ведёт "
        f"4.2 и читает 7.4 — 4.2 дополняет его по мере того, как интервью открывают новых\n"
        f"  • Разделы 3.1b, 3.3 и 3.4 ЧИТАЮТСЯ: 5.5 берёт методологию пакета "
        f"согласования из запланированной формы сроков и печатает на нём срок ответа "
        f"и согласующих, 5.4 сверяет, кто закрыл CR, и переносит "
        f"цепочку эскалации в CR Decision Record, 5.3 сверяет "
        f"технику приоритизации и её участников, 4.1 называет период работ, "
        f"в который попадает выявление, 4.4 называет запланированный уровень детализации в каждом "
        f"коммуникационном пакете, а 5.2 ранжирует кандидатов на переиспользование по запланированному scope "
        f"и проверяет ровно запланированный набор атрибутов\n"
        f"  • Это сверки и значения по умолчанию — решения остаются за вами. Ни одно из "
        f"них не перекрывает значение, переданное явно\n"
        f"  • 7.3 по-прежнему берёт бизнес-контекст из 6.1/6.2, а не из этого плана\n"
    )


if __name__ == "__main__":
    mcp.run()
