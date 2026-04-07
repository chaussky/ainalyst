"""
BABOK 3 — Business Analysis Planning and Monitoring
MCP-инструменты для планирования бизнес-анализа.

Инструменты:
  - suggest_ba_approach           — 3.1: выбор методологии (Predictive/Agile/Hybrid)
  - plan_stakeholder_engagement   — 3.2: матрица стейкхолдеров Power/Interest + план коммуникации
  - plan_ba_governance            — 3.3: governance: контроль изменений, согласование, эскалация
  - plan_information_management   — 3.4: архитектура хранения артефактов и трассировки
  - evaluate_ba_performance       — 3.5: метрики эффективности BA + план улучшений

Хранение:
  - {project}_ba_plan.json        — единый JSON-документ со всеми секциями плана
  - {project}_ba_plan_*.md        — Markdown-отчёт (через save_artifact)

Интеграция:
  Выход: ba_plan.json → используется в 4.x (stakeholder_registry),
         7.3 (business_context), 5.5 (governance для approval)

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import (
    save_artifact, logger, DATA_DIR,
    APPROACH_MATRIX, REGULATORY_OVERRIDE, QUADRANT_STRATEGIES,
)

mcp = FastMCP("BABOK_Planning")

PLAN_FILENAME = "ba_plan.json"

# ---------------------------------------------------------------------------
# Шаблоны (матрицы APPROACH_MATRIX, REGULATORY_OVERRIDE, QUADRANT_STRATEGIES
# перенесены в common.py — единственный источник истины, ADR-REVIEW-п5)
# ---------------------------------------------------------------------------

_GOVERNANCE_TEMPLATES = {
    "High": {
        "change_control": "Формальный: Change Request (CR) → оценка → одобрение CAB",
        "approval":       "Требуется подпись Sponsor + Product Owner",
        "review_cycle":   "Еженедельный статус + формальный ревью при каждом CR",
        "escalation":     "BA → PM → Steering Committee",
    },
    "Medium": {
        "change_control": "Адаптивный: PO одобряет изменения через Backlog",
        "approval":       "Product Owner + Lead BA",
        "review_cycle":   "Bi-weekly review, ретроспективы",
        "escalation":     "BA → PO → PM",
    },
    "Low": {
        "change_control": "Минимальный: фиксация в Jira, устное согласование",
        "approval":       "Lead BA",
        "review_cycle":   "По запросу",
        "escalation":     "BA → PM",
    },
}

_TRACEABILITY_LEVELS = {
    "High":   "Полная трассировка: Бизнес-цели → Требования → Тест-кейсы → Код",
    "Medium": "Связь требований с задачами Jira и тест-кейсами",
    "Low":    "Базовая: нумерация требований, ссылки по необходимости",
}

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
    return project_id.lower().replace(" ", "_")


def _plan_path(project_id: str) -> str:
    return os.path.join(DATA_DIR, f"{_safe(project_id)}_{PLAN_FILENAME}")


def _load_plan(project_id: str) -> dict:
    path = _plan_path(project_id)
    if not os.path.exists(path):
        return _empty_plan(project_id)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_plan(data: dict, project_id: str):
    os.makedirs(DATA_DIR, exist_ok=True)
    data["updated"] = str(date.today())
    with open(_plan_path(project_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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
        regulatory_note = f"\n  ⚠️ Regulatory override: {original_approach} → {approach}"

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
        f"→ Следующий шаг: `plan_stakeholder_engagement` — составь карту стейкхолдеров."
    )


@mcp.tool()
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
    try:
        stakeholders = json.loads(stakeholders_json)
    except json.JSONDecodeError as e:
        return f"❌ Ошибка парсинга stakeholders_json: {e}\n\nОжидается JSON-массив объектов."

    if not isinstance(stakeholders, list):
        return "❌ stakeholders_json должен быть JSON-массивом."

    if not stakeholders:
        return "⚠️ Список стейкхолдеров пуст. Добавь хотя бы одного стейкхолдера."

    valid = []
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

    if errors:
        return "❌ Ошибки в stakeholders_json:\n" + "\n".join(f"  • {e}" for e in errors)

    plan = _load_plan(project_id)
    plan["stakeholder_engagement"] = {
        "stakeholders": valid,
        "total": len(valid),
        "updated_on": str(date.today()),
    }
    _save_plan(plan, project_id)

    # Статистика по квадрантам
    quadrants = {}
    for s in valid:
        q = s["quadrant"]
        quadrants[q] = quadrants.get(q, 0) + 1

    blockers = [s["name"] for s in valid if s.get("attitude") == "Blocker"]

    lines = [
        f"✅ Реестр стейкхолдеров сохранён\n\n",
        f"  Проект:          {project_id}\n",
        f"  Стейкхолдеров:   {len(valid)}\n\n",
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

    lines.append(
        f"\n→ Следующий шаг: `plan_ba_governance` — определи правила принятия решений."
    )
    return "".join(lines)


@mcp.tool()
def plan_ba_governance(
    project_id: str,
    project_criticality: Literal["Low", "Medium", "High"],
    decision_makers_json: str,
    change_control_process: str = "",
    ba_notes: str = "",
) -> str:
    """
    BABOK 3.3 — Определить план governance бизнес-анализа.

    Фиксирует процедуры контроля изменений, согласования и эскалации.
    Критичность проекта определяет уровень формализации.
    Сохраняет в {project}_ba_plan.json секция 'governance'.

    Args:
        project_id: Идентификатор проекта
        project_criticality: Критичность проекта (Low/Medium/High)
        decision_makers_json: JSON-список ролей принимающих решения, напр. '["Sponsor", "PO", "Lead BA"]'
        change_control_process: Описание процесса контроля изменений (опционально — заполнится по шаблону)
        ba_notes: Дополнительные договорённости
    """
    try:
        decision_makers = json.loads(decision_makers_json)
    except json.JSONDecodeError:
        return "❌ Ошибка парсинга decision_makers_json. Ожидается JSON-массив строк, напр. '[\"Sponsor\", \"PO\"]'"

    if not isinstance(decision_makers, list):
        return "❌ decision_makers_json должен быть JSON-массивом."

    tpl = _GOVERNANCE_TEMPLATES.get(project_criticality, _GOVERNANCE_TEMPLATES["Medium"])

    governance = {
        "project_criticality": project_criticality,
        "decision_makers": decision_makers,
        "change_control": change_control_process or tpl["change_control"],
        "approval_process": tpl["approval"],
        "review_cycle": tpl["review_cycle"],
        "escalation_path": tpl["escalation"],
        "ba_notes": ba_notes,
        "defined_on": str(date.today()),
    }

    plan = _load_plan(project_id)
    plan["governance"] = governance
    _save_plan(plan, project_id)

    criticality_hints = {
        "High": "⚠️ Высокая критичность: формализуй каждый CR, ничего не меняй без подписи.",
        "Medium": "📋 Средняя критичность: стандартный process через PO/backlog.",
        "Low": "✅ Низкая критичность: гибкий процесс, фиксируй только ключевые решения.",
    }

    return (
        f"✅ Governance план зафиксирован\n\n"
        f"  Проект:            {project_id}\n"
        f"  Критичность:       {project_criticality}\n"
        f"  Лица решений:      {', '.join(decision_makers)}\n\n"
        f"  Контроль изменений: {governance['change_control']}\n"
        f"  Согласование:       {governance['approval_process']}\n"
        f"  Цикл ревью:         {governance['review_cycle']}\n"
        f"  Эскалация:          {governance['escalation_path']}\n\n"
        f"  {criticality_hints.get(project_criticality, '')}\n\n"
        f"→ Следующий шаг: `plan_information_management` — определи архитектуру хранения."
    )


@mcp.tool()
def plan_information_management(
    project_id: str,
    storage_tools_json: str,
    traceability_level: Literal["Low", "Medium", "High"] = "Medium",
    artifact_types_json: str = "[]",
    access_rules: str = "",
    ba_notes: str = "",
) -> str:
    """
    BABOK 3.4 — Спланировать управление информацией BA.

    Определяет где и как хранить требования и артефакты, уровень трассировки.
    Сохраняет в {project}_ba_plan.json секция 'information_management'.

    Args:
        project_id: Идентификатор проекта
        storage_tools_json: JSON-список инструментов хранения, напр. '["Confluence", "Jira", "GitHub"]'
        traceability_level: Уровень трассировки (Low/Medium/High)
        artifact_types_json: JSON-список типов артефактов, напр. '["User Story", "BRD", "Test Case"]'
        access_rules: Правила доступа (кто читает, кто редактирует)
        ba_notes: Дополнительные договорённости
    """
    try:
        storage_tools = json.loads(storage_tools_json)
    except json.JSONDecodeError:
        return "❌ Ошибка парсинга storage_tools_json. Ожидается JSON-массив строк."

    try:
        artifact_types = json.loads(artifact_types_json) if artifact_types_json.strip() else []
    except json.JSONDecodeError:
        artifact_types = []

    if not isinstance(storage_tools, list) or not storage_tools:
        return "❌ storage_tools_json должен быть непустым JSON-массивом."

    trace_desc = _TRACEABILITY_LEVELS.get(traceability_level, _TRACEABILITY_LEVELS["Medium"])

    info_mgmt = {
        "storage_tools": storage_tools,
        "traceability_level": traceability_level,
        "traceability_description": trace_desc,
        "artifact_types": artifact_types,
        "access_rules": access_rules or "BA редактируют, остальные читают",
        "ba_notes": ba_notes,
        "defined_on": str(date.today()),
    }

    plan = _load_plan(project_id)
    plan["information_management"] = info_mgmt
    _save_plan(plan, project_id)

    artifacts_note = ""
    if artifact_types:
        artifacts_note = f"  Типы артефактов:   {', '.join(artifact_types)}\n"

    return (
        f"✅ План управления информацией зафиксирован\n\n"
        f"  Проект:            {project_id}\n"
        f"  Инструменты:       {', '.join(storage_tools)}\n"
        f"  Трассировка:       {traceability_level} — {trace_desc}\n"
        f"{artifacts_note}"
        f"  Доступ:            {info_mgmt['access_rules']}\n\n"
        f"→ Следующий шаг: `evaluate_ba_performance` — установи метрики эффективности."
    )


@mcp.tool()
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
    try:
        current_issues = json.loads(current_issues_json) if current_issues_json.strip() else []
    except json.JSONDecodeError:
        current_issues = []

    try:
        metrics = json.loads(metrics_json) if metrics_json.strip() else []
    except json.JSONDecodeError:
        metrics = []

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

    if not any([approach, engagement, governance, info_mgmt]):
        return (
            "⚠️ BA-план пуст или не заполнен.\n"
            "Пройди шаги 3.1–3.5 перед сохранением отчёта."
        )

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

    if governance:
        md_lines += [
            "## 3.3 Governance",
            "",
            f"| Параметр | Значение |",
            f"|----------|---------|",
            f"| Критичность | {governance.get('project_criticality', '')} |",
            f"| Лица решений | {', '.join(governance.get('decision_makers', []))} |",
            f"| Контроль изменений | {governance.get('change_control', '')} |",
            f"| Согласование | {governance.get('approval_process', '')} |",
            f"| Цикл ревью | {governance.get('review_cycle', '')} |",
            f"| Эскалация | {governance.get('escalation_path', '')} |",
            "",
        ]

    if info_mgmt:
        md_lines += [
            "## 3.4 Управление информацией",
            "",
            f"- **Инструменты:** {', '.join(info_mgmt.get('storage_tools', []))}",
            f"- **Трассировка:** {info_mgmt.get('traceability_level', '')} — {info_mgmt.get('traceability_description', '')}",
            f"- **Доступ:** {info_mgmt.get('access_rules', '')}",
            "",
        ]

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

    md_content = "\n".join(md_lines)
    artifact_result = save_artifact(md_content, f"3_ba_plan_{_safe(project_id)}")

    plan["status"] = "finalized"
    plan["finalized_on"] = str(date.today())
    _save_plan(plan, project_id)

    json_path = _plan_path(project_id)

    return (
        f"✅ BA-план финализирован\n\n"
        f"  Проект: {project_id}\n"
        f"  📄 JSON (для 4.x, 5.5): `{json_path}`\n"
        f"  {artifact_result}\n\n"
        f"**Следующий шаг:**\n"
        f"• Глава 4.1 — подготовка к выявлению (реестр стейкхолдеров готов)\n"
        f"• Глава 5.5 — governance context передаётся автоматически\n"
    )


if __name__ == "__main__":
    mcp.run()
