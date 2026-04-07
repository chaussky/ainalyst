"""
BABOK 4.3 — Confirm Elicitation Results
MCP-инструменты для подтверждения результатов выявления.

Инструменты:
  - run_consistency_check          — проверить артефакт(ы) 4.2 по 5 критериям качества
  - save_confirmed_elicitation_result — сохранить финальный подтверждённый артефакт

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
from datetime import date
from typing import Literal
from mcp.server.fastmcp import FastMCP
from skills.common import save_artifact, logger, DATA_DIR

mcp = FastMCP("BABOK_Elicitation_Confirm")


# ---------------------------------------------------------------------------
# 4.3.1 — Проверка качества артефактов выявления по 5 критериям
# ---------------------------------------------------------------------------

@mcp.tool()
def run_consistency_check(
    project_name: str,
    source_artifacts_json: str,
    issues_json: str,
    readiness_status: Literal["Готов к анализу", "Готов условно", "Требует доработки"],
    readiness_rationale: str,
    needs_clarification: bool,
    clarification_questions_json: str,
    ba_decision: str,
) -> str:
    """
    BABOK 4.3 — Сохраняет отчёт о проверке качества артефактов выявления.
    Проверяет на полноту, точность, непротиворечивость, однозначность, тестируемость.

    Args:
        project_name:               Название проекта.
        source_artifacts_json:      Список проверенных артефактов. Формат:
                                    [
                                      {
                                        "path": "governance_plans/4_2_..._results.md",
                                        "stakeholder_role": "Руководитель отдела продаж",
                                        "session_date": "ДД.ММ.ГГГГ"
                                      }
                                    ]
        issues_json:                Найденные проблемы. Формат:
                                    [
                                      {
                                        "issue_id": "ISS-001",
                                        "criterion": "Полнота | Точность | Непротиворечивость | Однозначность | Тестируемость",
                                        "severity": "Критическая | Существенная | Незначительная",
                                        "description": "Описание проблемы",
                                        "evidence": "Цитата или ID требования из артефакта",
                                        "source_artifact": "путь к файлу или роль стейкхолдера",
                                        "recommendation": "Что сделать для устранения"
                                      }
                                    ]
        readiness_status:           Итоговый рейтинг готовности артефакта.
        readiness_rationale:        Обоснование рейтинга — почему именно этот статус.
        needs_clarification:        True если нужно уточнение у стейкхолдера.
        clarification_questions_json: Список точечных вопросов если needs_clarification=True. Формат:
                                    [
                                      {
                                        "stakeholder_role": "Кому адресован вопрос",
                                        "issue_id": "ISS-001",
                                        "question": "Текст вопроса для стейкхолдера",
                                        "context": "Контекст: на встрече вы говорили о...",
                                        "options": ["Вариант A", "Вариант B"]
                                      }
                                    ]
        ba_decision:                Решение BA: что делать дальше (текстовое описание).

    Returns:
        Путь к сохранённому отчёту о проверке.
    """
    logger.info(f"4.3 Проверка качества: проект='{project_name}'")

    try:
        artifacts = json.loads(source_artifacts_json)
        issues = json.loads(issues_json)
        questions = json.loads(clarification_questions_json) if clarification_questions_json else []
    except json.JSONDecodeError as e:
        return f"❌ Ошибка разбора JSON: {e}"

    today = date.today().strftime("%d.%m.%Y")

    # Статистика проблем
    critical = [i for i in issues if i.get("severity") == "Критическая"]
    significant = [i for i in issues if i.get("severity") == "Существенная"]
    minor = [i for i in issues if i.get("severity") == "Незначительная"]

    by_criterion = {}
    for issue in issues:
        c = issue.get("criterion", "—")
        by_criterion.setdefault(c, []).append(issue)

    # Иконка статуса
    status_icon = {"Готов к анализу": "✅", "Готов условно": "⚠️", "Требует доработки": "🔴"}.get(
        readiness_status, "❓"
    )

    # -----------------------------------------------------------------------
    # Формируем отчёт
    # -----------------------------------------------------------------------
    lines = []
    lines.append("# Отчёт о проверке результатов выявления (BABOK 4.3)\n")
    lines.append(f"**Проект:** {project_name}  ")
    lines.append(f"**Дата проверки:** {today}  ")
    lines.append(f"**Статус готовности:** {status_icon} {readiness_status}\n")
    lines.append("---\n")

    # Проверенные артефакты
    lines.append("## Проверенные артефакты\n")
    for a in artifacts:
        lines.append(
            f"- `{a.get('path', '—')}` "
            f"— {a.get('stakeholder_role', '—')}, {a.get('session_date', '—')}"
        )
    lines.append("")

    # Итоговый рейтинг
    lines.append("---\n")
    lines.append(f"## {status_icon} Рейтинг готовности: {readiness_status}\n")
    lines.append(f"{readiness_rationale}\n")

    # Сводка проблем
    lines.append("---\n")
    lines.append("## Сводка проблем\n")
    lines.append(f"| Серьёзность | Количество |")
    lines.append(f"|---|---|")
    lines.append(f"| 🔴 Критические | {len(critical)} |")
    lines.append(f"| 🟡 Существенные | {len(significant)} |")
    lines.append(f"| 🟢 Незначительные | {len(minor)} |")
    lines.append(f"| **Итого** | **{len(issues)}** |\n")

    if not issues:
        lines.append("_Проблем не обнаружено. Артефакт соответствует всем критериям качества._\n")
    else:
        # Проблемы по критериям
        lines.append("---\n")
        lines.append("## Проблемы по критериям\n")

        criterion_order = ["Полнота", "Точность", "Непротиворечивость", "Однозначность", "Тестируемость"]
        for criterion in criterion_order:
            criterion_issues = by_criterion.get(criterion, [])
            if not criterion_issues:
                continue
            lines.append(f"### {criterion}\n")
            for iss in criterion_issues:
                sev = iss.get("severity", "—")
                sev_icon = {"Критическая": "🔴", "Существенная": "🟡", "Незначительная": "🟢"}.get(sev, "❓")
                lines.append(f"**{iss.get('issue_id', '—')}** {sev_icon} {sev}  ")
                lines.append(f"- **Проблема:** {iss.get('description', '—')}  ")
                if iss.get("evidence"):
                    lines.append(f"- **Пример:** {iss['evidence']}  ")
                if iss.get("source_artifact"):
                    lines.append(f"- **Источник:** `{iss['source_artifact']}`  ")
                lines.append(f"- **Рекомендация:** {iss.get('recommendation', '—')}\n")

    # Вопросы для уточнения
    if needs_clarification and questions:
        lines.append("---\n")
        lines.append("## Вопросы для уточнения у стейкхолдеров\n")

        by_stakeholder = {}
        for q in questions:
            role = q.get("stakeholder_role", "Не указан")
            by_stakeholder.setdefault(role, []).append(q)

        for role, qs in by_stakeholder.items():
            lines.append(f"### {role}\n")
            for q in qs:
                lines.append(f"**[{q.get('issue_id', '—')}]** {q.get('question', '—')}  ")
                if q.get("context"):
                    lines.append(f"*Контекст: {q['context']}*  ")
                options = q.get("options", [])
                if options:
                    for i, opt in enumerate(options, 1):
                        lines.append(f"  - Вариант {i}: {opt}")
                lines.append("")
    elif needs_clarification:
        lines.append("---\n")
        lines.append("## Уточнение необходимо\n")
        lines.append("_Список вопросов сформулирован в чате. Уточните у стейкхолдеров перед продолжением._\n")

    # Решение BA
    lines.append("---\n")
    lines.append("## Решение BA\n")
    lines.append(f"{ba_decision}\n")
    lines.append("---\n")
    lines.append(
        f"*BABOK 4.3 — Consistency Check Report. "
        f"Проект: {project_name}. Дата: {today}.*\n"
    )

    content = "\n".join(lines)

    meta = (
        f"<!--\n"
        f"  BABOK 4.3 — Consistency Check\n"
        f"  Проект: {project_name}\n"
        f"  Артефактов проверено: {len(artifacts)}\n"
        f"  Проблем: {len(issues)} (крит: {len(critical)}, сущ: {len(significant)}, незнач: {len(minor)})\n"
        f"  Статус: {readiness_status}\n"
        f"  Требует уточнения: {needs_clarification}\n"
        f"  Создан: {today}\n"
        f"-->\n\n"
    )

    return save_artifact(meta + content, prefix="4_3_consistency_check")


# ---------------------------------------------------------------------------
# 4.3.2 — Сохранить финальный подтверждённый артефакт
# ---------------------------------------------------------------------------

@mcp.tool()
def save_confirmed_elicitation_result(
    project_name: str,
    stakeholder_role: str,
    consistency_check_path: str,
    confirmed_requirements_json: str,
    resolved_issues_json: str,
    open_issues_json: str,
    final_readiness: Literal["Готов к анализу", "Готов условно"],
    next_tasks: str,
) -> str:
    """
    BABOK 4.3 — Сохраняет финальный подтверждённый артефакт выявления.
    Является входом для задач 6.1 (Анализ текущего состояния) и 6.3 (Оценка рисков).

    Args:
        project_name:               Название проекта.
        stakeholder_role:           Роль стейкхолдера (источник требований).
        consistency_check_path:     Путь к отчёту run_consistency_check.
        confirmed_requirements_json: Подтверждённые требования — финальные формулировки. Формат:
                                    {
                                      "functional": [
                                        {"id": "FR-001", "statement": "...", "acceptance_criteria": "..."},
                                      ],
                                      "non_functional": [
                                        {"id": "NFR-001", "statement": "...", "metric": "..."}
                                      ],
                                      "constraints": ["..."],
                                      "business_rules": ["..."]
                                    }
        resolved_issues_json:       Закрытые проблемы из consistency check. Формат:
                                    [
                                      {
                                        "issue_id": "ISS-001",
                                        "resolution": "Как была закрыта",
                                        "updated_requirement_id": "FR-001 или null"
                                      }
                                    ]
        open_issues_json:           Оставшиеся открытые проблемы (known issues). Формат:
                                    [
                                      {
                                        "issue_id": "ISS-002",
                                        "description": "Краткое описание",
                                        "risk": "Чем рискуем если не закрыть",
                                        "owner": "Кто должен закрыть"
                                      }
                                    ]
        final_readiness:            Финальный статус. Только Готов к анализу или Готов условно
                                    (Требует доработки не может быть финальным статусом).
        next_tasks:                 Конкретные следующие шаги — что делать дальше.

    Returns:
        Путь к сохранённому подтверждённому артефакту.
    """
    logger.info(f"4.3 Сохранение подтверждённого артефакта: проект='{project_name}'")

    try:
        reqs = json.loads(confirmed_requirements_json)
        resolved = json.loads(resolved_issues_json)
        open_iss = json.loads(open_issues_json)
    except json.JSONDecodeError as e:
        return f"❌ Ошибка разбора JSON: {e}"

    today = date.today().strftime("%d.%m.%Y")
    status_icon = {"Готов к анализу": "✅", "Готов условно": "⚠️"}.get(final_readiness, "✅")

    # Считаем требования
    functional = reqs.get("functional", [])
    non_functional = reqs.get("non_functional", [])
    constraints = reqs.get("constraints", [])
    business_rules = reqs.get("business_rules", [])

    # -----------------------------------------------------------------------
    # Формируем артефакт
    # -----------------------------------------------------------------------
    lines = []
    lines.append("# Подтверждённые результаты выявления (BABOK 4.3)\n")
    lines.append(f"**Проект:** {project_name}  ")
    lines.append(f"**Стейкхолдер:** {stakeholder_role}  ")
    lines.append(f"**Дата подтверждения:** {today}  ")
    lines.append(f"**Статус:** {status_icon} {final_readiness}  ")
    lines.append(f"**На основе проверки:** `{consistency_check_path}`\n")
    lines.append("---\n")

    # Сводка
    lines.append("## Сводка\n")
    lines.append(f"| Тип | Количество |")
    lines.append(f"|---|---|")
    lines.append(f"| Функциональные требования | {len(functional)} |")
    lines.append(f"| Нефункциональные требования | {len(non_functional)} |")
    lines.append(f"| Ограничения | {len(constraints)} |")
    lines.append(f"| Бизнес-правила | {len(business_rules)} |")
    lines.append(f"| Закрытых проблем | {len(resolved)} |")
    lines.append(f"| Открытых проблем (known issues) | {len(open_iss)} |\n")

    # Функциональные требования
    if functional:
        lines.append("---\n")
        lines.append("## Функциональные требования\n")
        for r in functional:
            lines.append(f"**{r.get('id', '—')}:** {r.get('statement', '—')}  ")
            if r.get("acceptance_criteria"):
                lines.append(f"*Критерий приёмки: {r['acceptance_criteria']}*\n")
            else:
                lines.append("")

    # Нефункциональные требования
    if non_functional:
        lines.append("---\n")
        lines.append("## Нефункциональные требования\n")
        for r in non_functional:
            lines.append(f"**{r.get('id', '—')}:** {r.get('statement', '—')}  ")
            if r.get("metric"):
                lines.append(f"*Метрика: {r['metric']}*\n")
            else:
                lines.append("")

    # Ограничения
    if constraints:
        lines.append("---\n")
        lines.append("## Ограничения\n")
        for c in constraints:
            lines.append(f"- {c}")
        lines.append("")

    # Бизнес-правила
    if business_rules:
        lines.append("---\n")
        lines.append("## Бизнес-правила\n")
        for br in business_rules:
            lines.append(f"- {br}")
        lines.append("")

    # Закрытые проблемы
    if resolved:
        lines.append("---\n")
        lines.append("## Закрытые проблемы\n")
        for r in resolved:
            upd = f" → обновлено `{r['updated_requirement_id']}`" if r.get("updated_requirement_id") else ""
            lines.append(f"- **{r.get('issue_id', '—')}:** {r.get('resolution', '—')}{upd}")
        lines.append("")

    # Открытые проблемы (known issues)
    if open_iss:
        lines.append("---\n")
        lines.append("## ⚠️ Открытые проблемы (known issues)\n")
        lines.append("_Передаются в следующие задачи как явные риски._\n")
        for iss in open_iss:
            lines.append(f"**{iss.get('issue_id', '—')}:** {iss.get('description', '—')}  ")
            if iss.get("risk"):
                lines.append(f"- Риск: {iss['risk']}  ")
            if iss.get("owner"):
                lines.append(f"- Владелец: {iss['owner']}\n")
            else:
                lines.append("")

    # Следующие шаги
    lines.append("---\n")
    lines.append("## Следующие шаги\n")
    lines.append(f"{next_tasks}\n")
    lines.append("---\n")
    lines.append("## Передаётся в\n")
    lines.append("- **6.1** — Анализ текущего состояния  ")
    lines.append("- **6.3** — Оценка рисков\n")
    lines.append("---\n")
    lines.append(
        f"*BABOK 4.3 — Confirmed Elicitation Result. "
        f"Проект: {project_name}. Дата: {today}.*\n"
    )

    content = "\n".join(lines)

    meta = (
        f"<!--\n"
        f"  BABOK 4.3 — Confirmed Result\n"
        f"  Проект: {project_name}\n"
        f"  Стейкхолдер: {stakeholder_role}\n"
        f"  ФТ: {len(functional)}, НФТ: {len(non_functional)}\n"
        f"  Ограничения: {len(constraints)}, БП: {len(business_rules)}\n"
        f"  Закрытых проблем: {len(resolved)}, Открытых: {len(open_iss)}\n"
        f"  Статус: {final_readiness}\n"
        f"  Создан: {today}\n"
        f"-->\n\n"
    )

    return save_artifact(meta + content, prefix="4_3_confirmed_result")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
