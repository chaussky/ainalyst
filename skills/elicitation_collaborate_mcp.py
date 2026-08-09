"""
BABOK 4.5 — Manage Stakeholder Collaboration
MCP-инструменты для управления сотрудничеством с заинтересованными сторонами.

Инструменты:
  - log_decision               — зафиксировать принятое решение (Decision Log)
  - save_meeting_notes         — сохранить протокол встречи с action items
  - update_engagement_status   — зафиксировать изменение вовлечённости стейкхолдера

Примечание по архитектуре:
  update_engagement_status (4.5) и update_stakeholder_registry (4.2) — разные инструменты.
  4.2 регистрирует стейкхолдера / обновляет базовый профайл.
  4.5 фиксирует изменение вовлечённости с историей: было/стало, причина, действие BA.
  Разделение намеренное — в будущем можно объединить если практика покажет избыточность.

  BOTH write to the living registry. They used not to: 4.5 wrote only a
  Markdown report, so "became a Blocker" never reached the registry that 7.4 reads and
  3.2's conflict detector compares against. Separating the REPORT from the FACT is not
  the same as separating the tools — the report is 4.5's alone, the fact is shared.

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
from datetime import date
from typing import Literal
from mcp.server.fastmcp import FastMCP
from skills.common import (save_artifact, logger, parse_json_dict_list,
                           update_stakeholder_registry_file,
                           load_stakeholder_registry, reg_norm, guard_artifact_errors)

mcp = FastMCP("BABOK_Collaborate")


# ---------------------------------------------------------------------------
# 4.5.1 — Decision Log
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Living stakeholder registry (ADR-003) — 4.5 records observed CHANGE
# ---------------------------------------------------------------------------

_REGISTRY_SOURCE_45 = "4.5 engagement status"


def _record_engagement_in_registry(project_name: str, stakeholder_role: str,
                                   attitude_after: str,
                                   engagement_level_after: str) -> str:
    """Writes the observed attitude/engagement into the living registry.

    This tool exists to record that a stakeholder's stance CHANGED, and until now the
    fact lived only in a Markdown report — so the registry 7.4 reads, and 3.2's
    conflict detector compares against, still held the stale value. An analyst could
    read "became a Blocker" in one artifact and "Neutral" in another on the same day.

    Deliberately NOT insert-only, unlike 3.2's and 4.1's seeding. Those tools PLAN and
    must never overwrite what an interview established; this one OBSERVES, so its
    value is the newer evidence and has to win. That asymmetry is the difference
    between the two tools, not an inconsistency.

    The tool takes a ROLE and no name, but registry identity is the NAME — so the role
    is resolved to the person already holding it before writing, and only falls back to
    a role-keyed entry when nobody in the registry holds that role. An ambiguous role
    (two people) is reported rather than guessed: attaching one person's observed
    change to another's record is worse than not recording it automatically.

    Never raises: the engagement record is the deliverable and is already on disk.
    """
    if not stakeholder_role.strip():
        return ""

    # Resolve the ROLE to the NAMED person already holding it.
    #
    # Registry identity is the name, falling back to the role only when there is no
    # name. This tool takes a role and no name, so writing role-keyed created a SECOND
    # record for someone already registered under their name — the duplicate said
    # "Blocker" while the record 7.4 actually reads still said nothing. Found by a live
    # run through 4.1 -> 4.2 -> 4.5; the per-tool tests could not see it, because each
    # wrote the registry from empty.
    try:
        registry = load_stakeholder_registry(project_name)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"4.5 could not read the stakeholder registry: {e}")
        registry = {"stakeholders": []}

    role_key = reg_norm(stakeholder_role)
    matches = [s for s in registry.get("stakeholders", [])
               if reg_norm(s.get("role")) == role_key and reg_norm(s.get("name"))]

    if len(matches) > 1:
        # Guessing would attach an observation about one person to another's record.
        names = ", ".join(f"`{s.get('name')}`" for s in matches)
        return (f"\n⚠️ Реестр стейкхолдеров НЕ обновлён — роль `{stakeholder_role}` "
                f"занимает больше одного человека: {names}.\n"
                f"   Запишите изменение на конкретного человека через "
                f"`update_stakeholder_registry` (4.2), чтобы оно попало на нужного. "
                f"Сама запись о вовлечении сохранена.")

    incoming = {"role": stakeholder_role,
                "attitude": attitude_after,
                "engagement_level": engagement_level_after}
    if matches:
        # Carry the stored name so the merge resolves to the SAME record.
        incoming["name"] = matches[0]["name"]

    try:
        result = update_stakeholder_registry_file(
            project_name, [incoming],
            source=_REGISTRY_SOURCE_45,
            insert_defaults={"found_through": _REGISTRY_SOURCE_45},
        )
    except Exception as e:  # noqa: BLE001 — never let the engagement record fail on this
        logger.warning(f"4.5 could not update the stakeholder registry: {e}")
        return ("\n⚠️ Реестр стейкхолдеров не обновлён — "
                "запись о вовлечении сохранена.")

    added = len(result.get("added", []))
    verb = "добавлен в" if added else "обновлён в"
    return (f"\n📇 `{stakeholder_role}` {verb} реестре стейкхолдеров: "
            f"отношение → {attitude_after}, вовлечённость → {engagement_level_after} "
            f"(тот самый реестр, который читает 7.4).")



@mcp.tool()
@guard_artifact_errors
def log_decision(
    project_name: str,
    decision_date: str,
    decision_statement: str,
    context: str,
    alternatives_json: str,
    decision_maker: str,
    participants_json: str,
    decision_type: Literal[
        "Требование",
        "Приоритет",
        "Архитектурное",
        "Процессное",
        "Scope",
        "Другое",
    ],
    affected_artifacts_json: str,
    rationale: str,
    risks: str,
) -> str:
    """
    BABOK 4.5 — Фиксирует принятое решение в Decision Log.
    Обеспечивает трассировку: почему требования именно такие.

    Args:
        project_name:           Название проекта.
        decision_date:          Дата принятия решения ДД.ММ.ГГГГ.
        decision_statement:     Решение одним предложением — чётко и однозначно.
        context:                Контекст: что обсуждалось, какая проблема решалась.
        alternatives_json:      Рассмотренные альтернативы. Формат:
                                [
                                  {
                                    "option": "Описание варианта",
                                    "pros": "Плюсы",
                                    "cons": "Минусы",
                                    "rejected_reason": "Почему отклонён или ''"
                                  }
                                ]
        decision_maker:         Кто принял финальное решение (роль или имя).
        participants_json:      Участники обсуждения. Формат:
                                [{"name": "имя или роль", "position": "позиция по решению"}]
        decision_type:          Тип решения.
        affected_artifacts_json: Затронутые артефакты. Формат:
                                [{"artifact": "название или путь", "impact": "как меняется"}]
        rationale:              Обоснование выбранного решения.
        risks:                  Риски принятого решения или '' если нет.

    Returns:
        Путь к сохранённой записи Decision Log.
    """
    logger.info(f"4.5 Decision Log: проект='{project_name}', тип='{decision_type}'")

    alternatives, error = parse_json_dict_list(
        alternatives_json, "alternatives_json",
        example='[{"option": "...", "pros": "...", "cons": "...", "rejected_reason": "..."}]')
    if error:
        return error

    participants, error = parse_json_dict_list(
        participants_json, "participants_json",
        example='[{"name": "name or role", "position": "position on the decision"}]')
    if error:
        return error

    artifacts, error = parse_json_dict_list(
        affected_artifacts_json, "affected_artifacts_json",
        example='[{"artifact": "FR-001", "impact": "how it changes"}]')
    if error:
        return error

    today = date.today().strftime("%d.%m.%Y")

    # Генерируем ID решения на основе даты
    decision_id = f"DEC-{decision_date.replace('.', '')}"

    lines = []
    lines.append(f"# Decision Log — {decision_id}\n")
    lines.append(f"**Проект:** {project_name}  ")
    lines.append(f"**Дата:** {decision_date}  ")
    lines.append(f"**Тип:** {decision_type}  ")
    lines.append(f"**Принял решение:** {decision_maker}\n")
    lines.append("---\n")

    lines.append("## Решение\n")
    lines.append(f"> {decision_statement}\n")

    lines.append("---\n")
    lines.append("## Контекст\n")
    lines.append(f"{context}\n")

    lines.append("---\n")
    lines.append("## Обоснование\n")
    lines.append(f"{rationale}\n")

    if alternatives:
        lines.append("---\n")
        lines.append("## Рассмотренные альтернативы\n")
        for i, alt in enumerate(alternatives, 1):
            lines.append(f"### Вариант {i}: {alt.get('option', '—')}\n")
            if alt.get("pros"):
                lines.append(f"- **Плюсы:** {alt['pros']}  ")
            if alt.get("cons"):
                lines.append(f"- **Минусы:** {alt['cons']}  ")
            if alt.get("rejected_reason"):
                lines.append(f"- **Почему отклонён:** {alt['rejected_reason']}\n")
            else:
                lines.append("")

    lines.append("---\n")
    lines.append("## Участники обсуждения\n")
    lines.append("| Участник | Позиция |")
    lines.append("|---|---|")
    for p in participants:
        lines.append(f"| {p.get('name', '—')} | {p.get('position', '—')} |")
    lines.append("")

    if artifacts:
        lines.append("---\n")
        lines.append("## Затронутые артефакты\n")
        for a in artifacts:
            lines.append(f"- **{a.get('artifact', '—')}**: {a.get('impact', '—')}")
        lines.append("")

    if risks:
        lines.append("---\n")
        lines.append("## Риски решения\n")
        lines.append(f"{risks}\n")

    lines.append("---\n")
    lines.append(f"*BABOK 4.5 — Decision Log {decision_id}. Проект: {project_name}. Зафиксировано: {today}.*\n")

    content = "\n".join(lines)
    meta = (
        f"<!--\n"
        f"  BABOK 4.5 — Decision Log\n"
        f"  ID: {decision_id}\n"
        f"  Проект: {project_name}\n"
        f"  Тип: {decision_type}\n"
        f"  Decision maker: {decision_maker}\n"
        f"  Дата: {decision_date}\n"
        f"  Альтернатив рассмотрено: {len(alternatives)}\n"
        f"  Зафиксировано: {today}\n"
        f"-->\n\n"
    )
    return save_artifact(meta + content, prefix="4_5_decision_log", project_id=project_name)


# ---------------------------------------------------------------------------
# 4.5.2 — Протокол встречи
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def save_meeting_notes(
    project_name: str,
    meeting_date: str,
    meeting_type: Literal[
        "Интервью",
        "Воркшоп",
        "Статус-митинг",
        "Фасилитационная сессия",
        "Встреча 1-на-1",
        "Презентация",
        "Другое",
    ],
    participants_json: str,
    agenda_json: str,
    discussion_summary: str,
    decisions_json: str,
    action_items_json: str,
    open_questions: str,
    risks_identified: str,
    next_meeting: str,
) -> str:
    """
    BABOK 4.5 — Сохраняет структурированный протокол встречи.
    Используется после любой встречи в рамках проекта.

    Args:
        project_name:       Название проекта.
        meeting_date:       Дата встречи ДД.ММ.ГГГГ.
        meeting_type:       Тип встречи.
        participants_json:  Участники. Формат:
                            [{"name": "имя или роль", "department": "отдел или ''"}]
        agenda_json:        Повестка. Формат:
                            [{"item": "пункт повестки", "owner": "кто вёл"}]
        discussion_summary: Краткое резюме обсуждения — ключевые моменты,
                            важные высказывания, контекст договорённостей.
        decisions_json:     Принятые решения. Формат:
                            [{"decision": "формулировка", "decision_maker": "кто"}]
                            Пустой список [] если решений не было.
        action_items_json:  Action items. Формат:
                            [
                              {
                                "action": "Что сделать",
                                "owner": "Кто делает",
                                "deadline": "ДД.ММ.ГГГГ или ''",
                                "priority": "Высокий | Средний | Низкий"
                              }
                            ]
        open_questions:     Вопросы которые остались открытыми — текст или ''.
        risks_identified:   Риски выявленные в ходе встречи — текст или ''.
        next_meeting:       Когда следующая встреча и что обсудить — или ''.

    Returns:
        Путь к сохранённому протоколу встречи.
    """
    logger.info(f"4.5 Протокол встречи: проект='{project_name}', тип='{meeting_type}'")

    participants, error = parse_json_dict_list(
        participants_json, "participants_json",
        example='[{"name": "name or role", "department": "department"}]')
    if error:
        return error

    agenda, error = parse_json_dict_list(
        agenda_json, "agenda_json",
        example='[{"item": "agenda item", "owner": "who led it"}]')
    if error:
        return error

    decisions, error = parse_json_dict_list(
        decisions_json, "decisions_json",
        example='[{"decision": "statement", "decision_maker": "who"}]')
    if error:
        return error

    action_items, error = parse_json_dict_list(
        action_items_json, "action_items_json",
        example='[{"action": "...", "owner": "...", "deadline": "DD.MM.YYYY", "priority": "High"}]')
    if error:
        return error

    today = date.today().strftime("%d.%m.%Y")

    lines = []
    lines.append(f"# Протокол встречи — {meeting_type}\n")
    lines.append(f"**Проект:** {project_name}  ")
    lines.append(f"**Дата:** {meeting_date}  ")
    lines.append(f"**Тип:** {meeting_type}  ")
    lines.append(f"**Участники:** {', '.join(p.get('name', '—') for p in participants)}\n")
    lines.append("---\n")

    if agenda:
        lines.append("## Повестка\n")
        for i, item in enumerate(agenda, 1):
            owner = f" *({item['owner']})*" if item.get("owner") else ""
            lines.append(f"{i}. {item.get('item', '—')}{owner}")
        lines.append("")

    lines.append("---\n")
    lines.append("## Резюме обсуждения\n")
    lines.append(f"{discussion_summary}\n")

    if decisions:
        lines.append("---\n")
        lines.append("## Принятые решения\n")
        for i, d in enumerate(decisions, 1):
            dm = f" *(решение: {d['decision_maker']})*" if d.get("decision_maker") else ""
            lines.append(f"**Р{i}.** {d.get('decision', '—')}{dm}")
        lines.append("")

    if action_items:
        lines.append("---\n")
        lines.append("## Action Items\n")
        lines.append("| # | Действие | Кто | Срок | Приоритет |")
        lines.append("|---|---|---|---|---|")
        for i, item in enumerate(action_items, 1):
            deadline = item.get("deadline") or "—"
            priority = item.get("priority", "Средний")
            priority_icon = {"Высокий": "🔴", "Средний": "🟡", "Низкий": "🟢"}.get(priority, "🟡")
            lines.append(
                f"| {i} | {item.get('action', '—')} "
                f"| {item.get('owner', '—')} "
                f"| {deadline} "
                f"| {priority_icon} {priority} |"
            )
        lines.append("")

    if open_questions:
        lines.append("---\n")
        lines.append("## Открытые вопросы\n")
        lines.append(f"{open_questions}\n")

    if risks_identified:
        lines.append("---\n")
        lines.append("## Выявленные риски\n")
        lines.append(f"{risks_identified}\n")

    if next_meeting:
        lines.append("---\n")
        lines.append("## Следующая встреча\n")
        lines.append(f"{next_meeting}\n")

    lines.append("---\n")
    lines.append(f"*BABOK 4.5 — Meeting Notes. Проект: {project_name}. Зафиксировано: {today}.*\n")

    content = "\n".join(lines)
    meta = (
        f"<!--\n"
        f"  BABOK 4.5 — Meeting Notes\n"
        f"  Проект: {project_name}\n"
        f"  Тип: {meeting_type}\n"
        f"  Дата: {meeting_date}\n"
        f"  Участников: {len(participants)}\n"
        f"  Решений: {len(decisions)}\n"
        f"  Action items: {len(action_items)}\n"
        f"  Зафиксировано: {today}\n"
        f"-->\n\n"
    )
    return save_artifact(meta + content, prefix="4_5_meeting_notes", project_id=project_name)


# ---------------------------------------------------------------------------
# 4.5.3 — Обновление статуса вовлечённости стейкхолдера
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def update_engagement_status(
    project_name: str,
    stakeholder_role: str,
    change_date: str,
    attitude_before: Literal["Champion", "Neutral", "Blocker"],
    attitude_after: Literal["Champion", "Neutral", "Blocker"],
    engagement_level_before: Literal["Активный", "Пассивный", "Отсутствует"],
    engagement_level_after: Literal["Активный", "Пассивный", "Отсутствует"],
    signal_observed: str,
    probable_cause: str,
    ba_action_taken: str,
    ba_action_planned: str,
    escalation_needed: bool,
    escalation_to: str,
) -> str:
    """
    BABOK 4.5 — Фиксирует изменение вовлечённости стейкхолдера.
    Ведёт историю изменений: было/стало, причина, действие BA.

    Отличие от update_stakeholder_registry (4.2):
    - 4.2 регистрирует нового стейкхолдера или обновляет базовый профайл
    - 4.5 фиксирует динамику: что изменилось, почему, что BA сделал

    Args:
        project_name:             Название проекта.
        stakeholder_role:         Роль стейкхолдера.
        change_date:              Дата когда изменение замечено ДД.ММ.ГГГГ.
        attitude_before:          Отношение до изменения.
        attitude_after:           Отношение после изменения.
        engagement_level_before:  Уровень вовлечённости до.
        engagement_level_after:   Уровень вовлечённости после.
        signal_observed:          Что именно наблюдал BA — конкретное поведение.
        probable_cause:           Вероятная причина изменения (версия BA).
        ba_action_taken:          Что BA уже сделал в ответ.
        ba_action_planned:        Что BA планирует сделать далее.
        escalation_needed:        True если требуется эскалация.
        escalation_to:            Кому эскалировать или '' если не нужно.

    Returns:
        Путь к сохранённой записи об изменении вовлечённости.
    """
    logger.info(f"4.5 Статус вовлечённости: проект='{project_name}', стейкхолдер='{stakeholder_role}'")

    today = date.today().strftime("%d.%m.%Y")

    # Определяем направление изменения
    attitude_values = {"Champion": 3, "Neutral": 2, "Blocker": 1}
    engagement_values = {"Активный": 3, "Пассивный": 2, "Отсутствует": 1}

    attitude_delta = attitude_values.get(attitude_after, 2) - attitude_values.get(attitude_before, 2)
    engagement_delta = engagement_values.get(engagement_level_after, 2) - engagement_values.get(engagement_level_before, 2)

    if attitude_delta > 0 or engagement_delta > 0:
        trend = "📈 Улучшение"
    elif attitude_delta < 0 or engagement_delta < 0:
        trend = "📉 Ухудшение"
    else:
        trend = "➡️ Без изменений"

    attitude_icons = {"Champion": "🟢", "Neutral": "🟡", "Blocker": "🔴"}

    lines = []
    lines.append(f"# Изменение вовлечённости — {stakeholder_role}\n")
    lines.append(f"**Проект:** {project_name}  ")
    lines.append(f"**Стейкхолдер:** {stakeholder_role}  ")
    lines.append(f"**Дата изменения:** {change_date}  ")
    lines.append(f"**Тренд:** {trend}\n")
    lines.append("---\n")

    lines.append("## Динамика\n")
    lines.append("| Параметр | Было | Стало |")
    lines.append("|---|---|---|")
    lines.append(
        f"| Отношение | {attitude_icons.get(attitude_before, '—')} {attitude_before} "
        f"| {attitude_icons.get(attitude_after, '—')} {attitude_after} |"
    )
    lines.append(
        f"| Вовлечённость | {engagement_level_before} | {engagement_level_after} |\n"
    )

    lines.append("---\n")
    lines.append("## Наблюдаемый сигнал\n")
    lines.append(f"{signal_observed}\n")

    lines.append("---\n")
    lines.append("## Вероятная причина\n")
    lines.append(f"{probable_cause}\n")

    lines.append("---\n")
    lines.append("## Действия BA\n")
    if ba_action_taken:
        lines.append(f"**Уже сделано:** {ba_action_taken}  ")
    lines.append(f"**Планируется:** {ba_action_planned}\n")

    if escalation_needed:
        lines.append("---\n")
        lines.append("## ⚠️ Требуется эскалация\n")
        lines.append(f"**Кому:** {escalation_to or 'не указано'}  ")
        lines.append(
            "\n*Рекомендация: зафиксировать факт эскалации в протоколе встречи "
            "через `save_meeting_notes`.*\n"
        )

    lines.append("---\n")
    lines.append(
        f"*BABOK 4.5 — Engagement Status Update. "
        f"Проект: {project_name}. Зафиксировано: {today}.*\n"
    )

    content = "\n".join(lines)
    meta = (
        f"<!--\n"
        f"  BABOK 4.5 — Engagement Status\n"
        f"  Проект: {project_name}\n"
        f"  Стейкхолдер: {stakeholder_role}\n"
        f"  Attitude: {attitude_before} → {attitude_after}\n"
        f"  Вовлечённость: {engagement_level_before} → {engagement_level_after}\n"
        f"  Тренд: {trend}\n"
        f"  Эскалация: {escalation_needed}\n"
        f"  Дата: {change_date}\n"
        f"  Зафиксировано: {today}\n"
        f"-->\n\n"
    )
    artifact = save_artifact(meta + content, prefix="4_5_engagement_status",
                             project_id=project_name)
    return artifact + _record_engagement_in_registry(
        project_name, stakeholder_role, attitude_after, engagement_level_after)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
