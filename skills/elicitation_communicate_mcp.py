"""
BABOK 4.4 — Communicate Business Analysis Information
MCP-инструменты для подготовки и фиксации коммуникационных пакетов.

Tools:
  - prepare_communication_package  — save a package adapted for the audience
  - log_communication              — log the fact of a communication and its outcome
  - check_communication_schedule   — who is overdue for contact, and which events triggered it

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
from datetime import date
from typing import Literal
from mcp.server.fastmcp import FastMCP
from skills.common import (
    save_artifact, logger, parse_json_dict, parse_json_dict_list,
    pick_field, unrecognized_records_error,
    info_management_section, load_ba_plan, planned_abstraction_level,
    ABSTRACTION_LEVELS, reg_norm, guard_artifact_errors)

mcp = FastMCP("BABOK_Communicate")

# BABOK 3.4 element .2 — what a planned level of detail MEANS when a package is built.
# A bare label with no consequence is the "declared but dead" class; this turns the
# planning decision into an instruction the BA can follow while adapting the content.
_LEVEL_GUIDANCE = {
    "Summary": ("conclusions, business value, the decision being asked for",
                "requirement IDs, NFR wording, model internals"),
    "Standard": ("requirements as a list with priorities, key risks, open questions",
                 "acceptance criteria, exception flows, diagram internals"),
    "Detailed": ("full requirement wording, acceptance criteria, exceptions, models",
                 "nothing — this audience works with the material directly"),
}


# ---------------------------------------------------------------------------
# 4.4.1 — Подготовить адаптированный коммуникационный пакет
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def prepare_communication_package(
    project_name: str,
    source_artifact_path: str,
    audience_role: Literal[
        "Business Sponsor",
        "Manager",
        "Developer",
        "Architect / Tech Lead",
        "Tester",
        "End User",
        "Customer",
        "Domain SME",
    ],
    audience_profile_json: str,
    adapted_content: str,
    key_messages_json: str,
    recommended_format: Literal[
        "Формальный документ",
        "Неформальный документ",
        "Презентация",
        "Email",
        "Встреча 1-на-1",
        "Групповая встреча",
    ],
    recommended_channel: str,
    open_questions: str,
    ba_notes: str,
) -> str:
    """
    BABOK 4.4 — Сохраняет адаптированный коммуникационный пакет.
    Содержит переупакованный артефакт под конкретную аудиторию,
    рекомендации по формату и каналу доставки.

    Args:
        project_name:           Название проекта.
        source_artifact_path:   Путь к исходному артефакту (из 4.3 или другой задачи).
        audience_role:          Роль целевой аудитории.
        audience_profile_json:  Профайл аудитории из реестра стейкхолдеров. Формат:
                                {
                                  "stakeholder_role": "...",
                                  "influence": "High | Medium | Low",
                                  "interest": "High | Medium | Low",
                                  "attitude": "Champion | Neutral | Blocker",
                                  "communication_preference": "текст или ''",
                                  "key_concerns": "текст или ''"
                                }
        adapted_content:        Адаптированное содержимое артефакта — текст,
                                переформулированный на язык данной аудитории.
                                Это основной блок пакета.
        key_messages_json:      Ключевые сообщения — 3–5 главных тезисов
                                которые аудитория должна вынести. Формат:
                                [
                                  {
                                    "message": "Тезис",
                                    "why_it_matters": "Почему важно для этой аудитории"
                                  }
                                ]
        recommended_format:     Рекомендованный формат подачи материала.
        recommended_channel:    Рекомендованный канал (email, Confluence, Jira, встреча и т.д.).
        open_questions:         Вопросы, которые могут возникнуть у аудитории.
                                BA должен быть готов ответить на них.
        ba_notes:               Заметки BA: особенности этой аудитории, на что обратить внимание.

    Returns:
        Путь к сохранённому коммуникационному пакету.
    """
    logger.info(f"4.4 Подготовка пакета: проект='{project_name}', аудитория='{audience_role}'")

    profile, error = parse_json_dict(
        audience_profile_json, "audience_profile_json",
        example='{"stakeholder_role": "...", "influence": "High", "attitude": "Neutral"}')
    if error:
        return error

    key_messages, error = parse_json_dict_list(
        key_messages_json, "key_messages_json",
        example='[{"message": "...", "why_it_matters": "..."}]')
    if error:
        return error

    today = date.today().strftime("%d.%m.%Y")

    # BABOK 3.4 element .2. The plan keys a row by an audience the BA named — an
    # archetype from this tool's vocabulary OR a job title from the stakeholder map.
    # Matching on one of the two alone could not succeed by construction;
    # check_communication_schedule already carries the same fix.
    plan, plan_note = load_ba_plan(project_name)
    level_row = planned_abstraction_level(
        plan, audience_role, profile.get("stakeholder_role", ""))
    planned_rows = info_management_section(plan).get("abstraction_levels")
    planned_rows = planned_rows if isinstance(planned_rows, list) else []
    # str() because the value is whatever was stored: a numeric audience used to break
    # the join that renders this list.
    planned_audiences = [str(r.get("audience") or "") for r in planned_rows
                         if isinstance(r, dict)]
    # A row for THIS audience whose level the platform cannot act on: the reader drops
    # it, so without this distinction the note said the audience was both unplanned and
    # planned in one sentence, and the BA could not tell which field to repair.
    unusable_level = None
    if not level_row:
        for row in planned_rows:
            if not isinstance(row, dict):
                continue
            if reg_norm(row.get("audience")) in {
                    reg_norm(audience_role), reg_norm(profile.get("stakeholder_role", ""))} - {""}:
                unusable_level = row.get("level")
                break

    # Icons for attitude
    attitude = profile.get("attitude", "Neutral")
    attitude_icon = {"Champion": "🟢", "Neutral": "🟡", "Blocker": "🔴"}.get(attitude, "🟡")

    # -----------------------------------------------------------------------
    # Формируем пакет
    # -----------------------------------------------------------------------
    lines = []
    lines.append(f"# Communication Package: {audience_role}\n")
    lines.append(f"**Project:** {project_name}  ")
    lines.append(f"**Audience:** {audience_role}  ")
    lines.append(f"**Preparation date:** {today}  ")
    if level_row:
        note = f" — {level_row['note']}" if level_row.get("note") else ""
        lines.append(
            f"**Level of detail (planned in 3.4):** {level_row['level']}{note}  ")
    lines.append(f"**Source:** `{source_artifact_path}`\n")
    lines.append("---\n")

    # Профайл аудитории
    lines.append("## Профайл аудитории\n")
    lines.append(f"| Параметр | Значение |")
    lines.append(f"|---|---|")
    lines.append(f"| Влияние | {profile.get('influence', '—')} |")
    lines.append(f"| Интерес | {profile.get('interest', '—')} |")
    lines.append(f"| Отношение к проекту | {attitude_icon} {attitude} |")
    if profile.get("communication_preference"):
        lines.append(f"| Стиль общения | {profile['communication_preference']} |")
    if profile.get("key_concerns"):
        lines.append(f"| Ключевые опасения | {profile['key_concerns']} |\n")
    else:
        lines.append("")

    # The decoded level lives in the ARTEFACT, not in the return value: this tool
    # returns only the save_artifact line, so a checklist put there would never reach
    # the BA. Here it sits next to the material being adapted.
    if level_row:
        include, leave_out = _LEVEL_GUIDANCE.get(level_row["level"], ("", ""))
        lines.append("---\n")
        lines.append(f"## Level of Detail — {level_row['level']} (planned in 3.4)\n")
        lines.append(f"**Include:** {include}  ")
        lines.append(f"**Leave out:** {leave_out}\n")

    # Key messages
    if key_messages:
        lines.append("---\n")
        lines.append("## Ключевые сообщения\n")
        lines.append("_Что аудитория должна вынести из этой коммуникации:_\n")
        for i, msg in enumerate(key_messages, 1):
            lines.append(f"**{i}. {msg.get('message', '—')}**  ")
            if msg.get("why_it_matters"):
                lines.append(f"*Почему важно: {msg['why_it_matters']}*\n")
            else:
                lines.append("")

    # Адаптированное содержимое
    lines.append("---\n")
    lines.append(f"## Содержимое пакета [{audience_role}]\n")
    lines.append(adapted_content)
    lines.append("")

    # Рекомендации по доставке
    lines.append("---\n")
    lines.append("## Рекомендации по доставке\n")
    lines.append(f"| Параметр | Рекомендация |")
    lines.append(f"|---|---|")
    lines.append(f"| Формат | {recommended_format} |")
    lines.append(f"| Канал | {recommended_channel} |\n")

    # Возможные вопросы от аудитории
    if open_questions:
        lines.append("---\n")
        lines.append("## Возможные вопросы от аудитории\n")
        lines.append("_BA должен быть готов ответить:_\n")
        lines.append(open_questions)
        lines.append("")

    # Blocker — специальный раздел
    if attitude == "Blocker":
        lines.append("---\n")
        lines.append("## ⚠️ Внимание: аудитория настроена скептически\n")
        lines.append(
            "Стейкхолдер классифицирован как Blocker. Рекомендуется:\n"
            "- Провести встречу 1-на-1 до групповой презентации\n"
            "- Явно адресовать его ключевые опасения в начале пакета\n"
            "- Подготовить раздел «Что это даёт лично вам»\n"
        )

    # Заметки BA
    if ba_notes:
        lines.append("---\n")
        lines.append("## Заметки BA\n")
        lines.append(ba_notes)
        lines.append("")

    lines.append("---\n")
    lines.append(
        f"*BABOK 4.4 — Communication Package. "
        f"Проект: {project_name}. Аудитория: {audience_role}. Дата: {today}.*\n"
    )

    content = "\n".join(lines)

    meta = (
        f"<!--\n"
        f"  BABOK 4.4 — Communication Package\n"
        f"  Проект: {project_name}\n"
        f"  Аудитория: {audience_role}\n"
        f"  Attitude: {attitude}\n"
        f"  Формат: {recommended_format}\n"
        f"  Канал: {recommended_channel}\n"
        f"  Создан: {today}\n"
        f"-->\n\n"
    )

    saved = save_artifact(meta + content, prefix="4_4_comm_package",
                          project_id=project_name)

    notes = []
    if plan_note:
        notes.append(plan_note)
    elif unusable_level is not None:
        notes.append(
            f"⚠️ 3.4 does plan a detail level for `{audience_role}`, but its value "
            f"`{unusable_level}` is not one of {', '.join(ABSTRACTION_LEVELS)} — fix it "
            f"in `plan_information_management(abstraction_levels_json=...)`.")
    elif planned_audiences and not level_row:
        # Only when the project actually planned detail levels for SOMEONE. A project
        # that planned storage but no levels has made no decision to be reminded of.
        notes.append(
            f"⚠️ Detail level for `{audience_role}` is not planned in 3.4. "
            f"Planned audiences: {', '.join(a for a in planned_audiences if a)}.")
    return saved + ("\n\n" + "\n".join(notes) if notes else "")


# ---------------------------------------------------------------------------
# 4.4.2 — Зафиксировать факт коммуникации
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def log_communication(
    project_name: str,
    communication_package_path: str,
    audience_role: str,
    communication_date: str,
    channel_used: Literal[
        "Email",
        "Встреча 1-на-1",
        "Групповая встреча",
        "Мессенджер",
        "Confluence / документ",
        "Другое",
    ],
    participants_json: str,
    understanding_status: Literal[
        "Понял и согласен",
        "Понял частично",
        "Не понял — нужен повтор",
        "Нет ответа",
        "Не согласен",
    ],
    feedback_summary: str,
    action_items_json: str,
    needs_followup: bool,
    followup_deadline: str,
) -> str:
    """
    BABOK 4.4 — Фиксирует факт коммуникации и её результат.
    Создаёт запись в журнале коммуникаций проекта.

    Args:
        project_name:               Название проекта.
        communication_package_path: Путь к переданному пакету (из prepare_communication_package).
        audience_role:              Роль получателя.
        communication_date:         Дата коммуникации в формате ДД.ММ.ГГГГ.
        channel_used:               Фактически использованный канал.
        participants_json:          Список участников. Формат:
                                    [{"name": "Имя или роль", "role": "должность"}]
        understanding_status:       Статус понимания аудитории по итогам коммуникации.
        feedback_summary:           Краткое резюме обратной связи: что сказали, что волнует,
                                    какие вопросы задали.
        action_items_json:          Список действий по итогам. Формат:
                                    [
                                      {
                                        "action": "Что сделать",
                                        "owner": "Кто делает",
                                        "deadline": "ДД.ММ.ГГГГ или ''"
                                      }
                                    ]
        needs_followup:             True если нужна повторная коммуникация.
        followup_deadline:          Срок follow-up в формате ДД.ММ.ГГГГ или '' если не нужен.

    Returns:
        Путь к сохранённой записи журнала коммуникаций.
    """
    logger.info(f"4.4 Журнал коммуникации: проект='{project_name}', аудитория='{audience_role}'")

    participants, error = parse_json_dict_list(
        participants_json, "participants_json",
        example='[{"name": "Alex Kim", "role": "Backend developer"}]')
    if error:
        return error

    action_items, error = parse_json_dict_list(
        action_items_json, "action_items_json",
        example='[{"action": "...", "owner": "...", "deadline": "DD.MM.YYYY"}]')
    if error:
        return error

    today = date.today().strftime("%d.%m.%Y")

    # Иконка статуса понимания
    status_icons = {
        "Понял и согласен": "✅",
        "Понял частично": "🟡",
        "Не понял — нужен повтор": "🔴",
        "Нет ответа": "⏳",
        "Не согласен": "❌",
    }
    status_icon = status_icons.get(understanding_status, "❓")

    # -----------------------------------------------------------------------
    # Формируем запись журнала
    # -----------------------------------------------------------------------
    lines = []
    lines.append(f"# Журнал коммуникации — {audience_role}\n")
    lines.append(f"**Проект:** {project_name}  ")
    lines.append(f"**Дата коммуникации:** {communication_date}  ")
    lines.append(f"**Зафиксировано:** {today}  ")
    lines.append(f"**Пакет:** `{communication_package_path}`\n")
    lines.append("---\n")

    # Факт коммуникации
    lines.append("## Факт коммуникации\n")
    lines.append(f"| Параметр | Значение |")
    lines.append(f"|---|---|")
    lines.append(f"| Аудитория | {audience_role} |")
    lines.append(f"| Канал | {channel_used} |")
    lines.append(f"| Участники | {', '.join(p.get('name', '—') for p in participants)} |")
    lines.append(f"| Статус понимания | {status_icon} {understanding_status} |\n")

    # Обратная связь
    if feedback_summary:
        lines.append("---\n")
        lines.append("## Обратная связь аудитории\n")
        lines.append(feedback_summary)
        lines.append("")

    # Action items
    if action_items:
        lines.append("---\n")
        lines.append("## Action Items\n")
        lines.append(f"| # | Действие | Кто | Срок |")
        lines.append(f"|---|---|---|---|")
        for i, item in enumerate(action_items, 1):
            deadline = item.get("deadline") or "—"
            lines.append(
                f"| {i} | {item.get('action', '—')} "
                f"| {item.get('owner', '—')} "
                f"| {deadline} |"
            )
        lines.append("")

    # Follow-up
    lines.append("---\n")
    if needs_followup:
        lines.append("## 🔄 Требуется Follow-up\n")
        lines.append(f"**Срок:** {followup_deadline or 'не указан'}  ")
        if understanding_status == "Не понял — нужен повтор":
            lines.append(
                "\n*Рекомендация: изменить формат или канал подачи — "
                "текущий не дал результата.*\n"
            )
        elif understanding_status == "Не согласен":
            lines.append(
                "\n*Рекомендация: перейти к задаче 4.5 (Manage Stakeholder Collaboration) "
                "— здесь уже не вопрос коммуникации, а управление разногласием.*\n"
            )
        else:
            lines.append("")
    else:
        lines.append("## ✅ Коммуникация завершена\n")
        lines.append("Повторная коммуникация не требуется.\n")

    lines.append("---\n")
    lines.append(
        f"*BABOK 4.4 — Communication Log. "
        f"Проект: {project_name}. Дата записи: {today}.*\n"
    )

    content = "\n".join(lines)

    meta = (
        f"<!--\n"
        f"  BABOK 4.4 — Communication Log\n"
        f"  Проект: {project_name}\n"
        f"  Аудитория: {audience_role}\n"
        f"  Дата: {communication_date}\n"
        f"  Статус понимания: {understanding_status}\n"
        f"  Follow-up: {needs_followup}\n"
        f"  Зафиксировано: {today}\n"
        f"-->\n\n"
    )

    return save_artifact(meta + content, prefix="4_4_comm_log", project_id=project_name)


# ---------------------------------------------------------------------------
# 4.4.3 — Проверить расписание коммуникаций
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def check_communication_schedule(
    project_name: str,
    today_date: str,
    stakeholders_json: str,
    communication_log_json: str,
    triggered_events_json: str,
) -> str:
    """
    BABOK 4.4 — Проверяет расписание коммуникаций и выдаёт список
    стейкхолдеров, которым нужно написать сейчас.
    Сравнивает дату последней коммуникации с частотой из плана (3.2)
    и проверяет наступление триггерных событий.

    Args:
        project_name:           Название проекта.
        today_date:             Сегодняшняя дата в формате ДД.ММ.ГГГГ.
        stakeholders_json:      Реестр стейкхолдеров с расписанием. Формат:
                                [
                                  {
                                    "role": "Спонсор",
                                    "name": "Имя или ''",
                                    "influence": "High | Medium | Low",
                                    "interest": "High | Medium | Low",
                                    "attitude": "Champion | Neutral | Blocker",
                                    "comm_frequency": "После каждой сессии | Еженедельно | По milestone | По запросу",
                                    "comm_triggers": ["Изменение требований", "Новое решение"],
                                    "last_communication_date": "ДД.ММ.ГГГГ или ''",
                                    "last_communication_topic": "О чём писали последний раз или ''"
                                  }
                                ]
        communication_log_json: Последние записи из log_communication. Формат:
                                [
                                  {
                                    "audience_role": "роль",
                                    "communication_date": "ДД.ММ.ГГГГ",
                                    "understanding_status": "статус",
                                    "needs_followup": true
                                  }
                                ]
        triggered_events_json:  События, произошедшие с момента последней проверки. Формат:
                                [
                                  {
                                    "event_type": "Завершена сессия выявления | Принято решение | Изменение требований | Достигнут milestone | Выявлен риск",
                                    "description": "Краткое описание события",
                                    "date": "ДД.ММ.ГГГГ"
                                  }
                                ]

    Returns:
        Путь к сохранённому отчёту о расписании коммуникаций.
    """
    logger.info(f"4.4 Проверка расписания: проект='{project_name}', дата='{today_date}'")

    stakeholders, error = parse_json_dict_list(
        stakeholders_json, "stakeholders_json",
        example='[{"role": "Sponsor", "influence": "High", "comm_frequency": "Weekly", '
                '"last_communication_date": "DD.MM.YYYY"}]')
    if error:
        return error

    comm_log, error = parse_json_dict_list(
        communication_log_json, "communication_log_json",
        example='[{"audience_role": "...", "communication_date": "DD.MM.YYYY"}]')
    if error:
        return error

    events, error = parse_json_dict_list(
        triggered_events_json, "triggered_events_json",
        example='[{"event_type": "Decision made", "description": "...", "date": "DD.MM.YYYY"}]')
    if error:
        return error

    # Normalise the spellings before anything reads these records. Reading only
    # `event_type` / `description` / `date` rendered "- [—] **—**: —" into the delivered
    # schedule — a row about nothing — while the header counted "Triggered: 0" and the
    # tool reported success.
    EVENT_TYPE_KEYS = ("event_type", "type", "event")
    events = [
        {
            **e,
            "event_type": pick_field(e, *EVENT_TYPE_KEYS),
            "description": pick_field(e, "description", "summary", "details",
                                      *EVENT_TYPE_KEYS),
            "date": pick_field(e, "date", "on", "occurred"),
        }
        for e in events
    ]
    if events and not any(e["event_type"] for e in events):
        return unrecognized_records_error(
            "triggered_events_json", EVENT_TYPE_KEYS,
            '[{"event_type": "Decision made", "description": "...", "date": "DD.MM.YYYY"}]')

    from datetime import datetime, timedelta

    def parse_date(s: str):
        if not s:
            return None
        try:
            return datetime.strptime(s.strip(), "%d.%m.%Y")
        except ValueError:
            return None

    today = parse_date(today_date) or datetime.today()

    # Most recent communications from the log (supplement the registry data)
    # Key the log by every identifier it carries, lower-cased.
    #
    # `log_communication` records `audience_role` from the 4.4 audience vocabulary
    # ("Business Sponsor", "Developer", …), while the stakeholder map carries job titles
    # from 3.2/4.2 ("Head of Retail Lending"). Matching those two by exact string could
    # not succeed by construction, so a communication logged days earlier never
    # suppressed the urgency and the schedule stated "No communication on record yet"
    # about someone who had just been briefed. Accept a match on either identifier.
    log_by_role = {}

    def _remember(key, payload):
        key = str(key).strip().lower()
        if not key:
            return
        if key not in log_by_role or payload["date"] > log_by_role[key]["date"]:
            log_by_role[key] = payload

    for entry in comm_log:
        d = parse_date(entry.get("communication_date", ""))
        if not d:
            continue
        payload = {
            "date": d,
            "status": entry.get("understanding_status", ""),
            "followup": entry.get("needs_followup", False),
        }
        for key in (entry.get("audience_role"), entry.get("role"),
                    entry.get("stakeholder_name"), entry.get("name")):
            _remember(key, payload)

    # Frequency → number of days.
    #
    # The producer of this field is 3.2 `plan_stakeholder_engagement`, which assigns it
    # from QUADRANT_STRATEGIES: Weekly / At milestones / Bi-weekly / Monthly /
    # Quarterly. The set below originally shared exactly ONE value with that list, so a
    # stakeholder on a Bi-weekly or Monthly cadence yielded `days_limit = None`, fell
    # through both overdue branches, and vanished from the queue — after which the tool
    # printed "✅ All communications are on track". Silent degradation is tolerable only
    # when the tool then says LESS, never when it makes a confident positive claim.
    # Matching is case-insensitive because "At milestones" and "At Milestone" are the
    # same cadence written by two authors.
    freq_days = {
        "after each session": 3,      # 3-day grace period
        "weekly": 7,
        "bi-weekly": 14,
        "biweekly": 14,
        "monthly": 30,
        "quarterly": 90,
        "at milestone": None,         # trigger-only
        "at milestones": None,
        "on request": None,
    }
    unknown_frequencies = set()
    # An empty or absent comm_frequency is NOT "On Request": On Request is the
    # analyst's explicit choice of a trigger-only cadence, while empty means no
    # cadence was ever planned. Defaulting the absent key to "On Request"
    # fabricated that choice, and the empty string slipped past the
    # unknown-frequency guard (`if freq_key and ...`) — so a caller building this
    # input from the 4.2 registry (which deliberately carries no comm_frequency)
    # had every stakeholder silently excluded under a clean "on track" verdict.
    no_cadence_roles = []

    # Собираем очередь коммуникаций
    urgent = []       # нужно сегодня
    due_soon = []     # в ближайшие 3 дня
    triggered = []    # сработал триггер
    followup_due = [] # незакрытый follow-up из лога

    for sh in stakeholders:
        role = sh.get("role") or sh.get("name") or "—"
        freq = sh.get("comm_frequency", "")
        triggers = sh.get("comm_triggers", [])

        # Determine the date of the last communication. Look the stakeholder up by
        # every identifier they carry, since the log may be keyed by either.
        logged = None
        for key in (sh.get("role"), sh.get("name")):
            candidate = log_by_role.get(str(key).strip().lower()) if key else None
            if candidate and (logged is None or candidate["date"] > logged["date"]):
                logged = candidate

        last_date = parse_date(sh.get("last_communication_date", ""))
        if logged and (not last_date or logged["date"] > last_date):
            last_date = logged["date"]

        # Check overdue status by frequency
        freq_key = str(freq).strip().lower()
        days_limit = freq_days.get(freq_key)
        if not freq_key:
            no_cadence_roles.append(role)
        elif freq_key not in freq_days:
            unknown_frequencies.add(str(freq))
        if days_limit and last_date:
            days_since = (today - last_date).days
            overdue = days_since - days_limit
            if overdue >= 0:
                urgent.append({
                    "role": role,
                    "reason": f"Просрочено на {overdue} дн. (частота: {freq}, последний раз: {sh.get('last_communication_date', '—')})",
                    "influence": sh.get("influence", "—"),
                    "last_topic": sh.get("last_communication_topic", ""),
                })
            elif overdue >= -3:
                due_soon.append({
                    "role": role,
                    "reason": f"Через {-overdue} дн. (частота: {freq})",
                    "influence": sh.get("influence", "—"),
                })
        elif days_limit and not last_date:
            urgent.append({
                "role": role,
                "reason": f"Нет ни одной коммуникации (частота: {freq})",
                "influence": sh.get("influence", "—"),
                "last_topic": "",
            })

        # Проверяем триггеры
        for event in events:
            event_type = event.get("event_type", "")
            for trigger in triggers:
                if trigger.lower() in event_type.lower() or event_type.lower() in trigger.lower():
                    triggered.append({
                        "role": role,
                        "trigger": trigger,
                        "event": event.get("description", event_type),
                        "event_date": event.get("date", "—"),
                        "influence": sh.get("influence", "—"),
                    })

        # Unresolved follow-ups
        if logged and logged.get("followup"):
            followup_due.append({
                "role": role,
                "status": logged.get("status", "—"),
                "date": logged["date"].strftime("%d.%m.%Y"),
            })

    # -----------------------------------------------------------------------
    # Формируем отчёт
    # -----------------------------------------------------------------------
    lines = []
    lines.append(f"# Расписание коммуникаций — проверка на {today_date}\n")
    lines.append(f"**Проект:** {project_name}  ")
    lines.append(f"**Дата проверки:** {today_date}\n")
    lines.append("---\n")

    # Сводка
    total_actions = len(urgent) + len(triggered) + len(followup_due)
    if total_actions == 0:
        if unknown_frequencies or no_cadence_roles:
            # Degrading is fine; making a confident positive claim on top of it is not.
            lines.append("## ⚠️ Schedule Could Not Be Fully Checked\n")
            if unknown_frequencies:
                lines.append(
                    f"No overdue communications among the cadences this tool recognises, "
                    f"but {len(unknown_frequencies)} unrecognised value(s) were skipped: "
                    f"{', '.join(sorted(unknown_frequencies))}. Those stakeholders were "
                    f"NOT evaluated — this is not a clean bill of health.\n"
                )
            if no_cadence_roles:
                lines.append(
                    f"{len(no_cadence_roles)} stakeholder(s) have no communication cadence "
                    f"on record and were NOT evaluated: {', '.join(no_cadence_roles)}. "
                    f"Set `comm_frequency` (the 3.2 plan assigns one per quadrant) to "
                    f"include them in this check.\n"
                )
        else:
            lines.append("## ✅ All Communications Are on Track\n")
            lines.append("No overdue or triggered communications.\n")
    else:
        lines.append(f"## Need Attention Today: {total_actions} stakeholder(s)\n")
        if unknown_frequencies:
            lines.append(
                f"> ⚠️ Skipped {len(unknown_frequencies)} unrecognised cadence(s): "
                f"{', '.join(sorted(unknown_frequencies))}.\n"
            )
        if no_cadence_roles:
            lines.append(
                f"> ⚠️ {len(no_cadence_roles)} stakeholder(s) have no communication cadence "
                f"on record and were NOT evaluated: {', '.join(no_cadence_roles)}.\n"
            )

    # Urgent (overdue) — ranked by influence (High first). Sorting the raw
    # "High"/"Medium"/"Low" label alphabetically is wrong: alphabetical order
    # (High < Low < Medium) does not match the ordinal, so map to a numeric rank.
    influence_rank = {"High": 3, "Medium": 2, "Low": 1}
    if urgent:
        lines.append("---\n")
        lines.append("## 🔴 Urgent — Overdue\n")
        for item in sorted(urgent, key=lambda x: influence_rank.get(x.get("influence"), 0), reverse=True):
            lines.append(f"**{item['role']}** (influence: {item['influence']})  ")
            lines.append(f"- {item['reason']}  ")
            if item.get("last_topic"):
                lines.append(f"- Последняя тема: {item['last_topic']}  ")
            lines.append("")

    # Триггерные события
    if triggered:
        lines.append("---\n")
        lines.append("## 🟡 Сработал триггер\n")
        seen = set()
        for item in triggered:
            key = (item["role"], item["trigger"])
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"**{item['role']}** (влияние: {item['influence']})  ")
            lines.append(f"- Триггер: «{item['trigger']}»  ")
            lines.append(f"- Событие: {item['event']} ({item['event_date']})  ")
            lines.append("")

    # Follow-up
    if followup_due:
        lines.append("---\n")
        lines.append("## 🔄 Незакрытые follow-up\n")
        for item in followup_due:
            lines.append(f"**{item['role']}** — статус: {item['status']}, дата: {item['date']}")
        lines.append("")

    # Скоро (в ближайшие 3 дня)
    if due_soon:
        lines.append("---\n")
        lines.append("## 🟢 Скоро (в ближайшие 3 дня)\n")
        for item in due_soon:
            lines.append(f"- **{item['role']}**: {item['reason']}")
        lines.append("")

    # Прошедшие события
    if events:
        lines.append("---\n")
        lines.append("## События с последней проверки\n")
        for ev in events:
            lines.append(f"- [{ev.get('date', '—')}] **{ev.get('event_type', '—')}**: {ev.get('description', '—')}")
        lines.append("")

    lines.append("---\n")
    lines.append(
        f"*BABOK 4.4 — Communication Schedule Check. "
        f"Проект: {project_name}. Дата: {today_date}.*\n"
    )

    content = "\n".join(lines)

    meta = (
        f"<!--\n"
        f"  BABOK 4.4 — Communication Schedule\n"
        f"  Проект: {project_name}\n"
        f"  Дата проверки: {today_date}\n"
        f"  Срочных: {len(urgent)}, Триггерных: {len(triggered)}, Follow-up: {len(followup_due)}\n"
        f"-->\n\n"
    )

    # A CHECK's product is the answer, not the file. Returning only the save line meant
    # the analyst asked "who have I not spoken to in a while?" and got back
    # "✅ Artifact saved" — which reads as "all clear", and swallowed precisely the
    # warning that exists to stop that reading. (Contrast the package-building tools of
    # this module, which deliberately return only the save line: their content is large
    # and meant for forwarding.)
    saved = save_artifact(meta + content, prefix="4_4_comm_schedule", project_id=project_name)

    verdict = [f"📡 **Communication schedule check — {project_name}**", ""]
    if urgent or triggered or followup_due:
        verdict.append(f"- 🔴 Urgent: {len(urgent)}")
        verdict.append(f"- 🟠 Triggered by events: {len(triggered)}")
        verdict.append(f"- 🟡 Follow-up due: {len(followup_due)}")
    else:
        verdict.append("- ✅ Nothing overdue among the cadences this tool recognises")
    if unknown_frequencies or no_cadence_roles:
        skipped = len(unknown_frequencies) + len(no_cadence_roles)
        verdict.append(
            f"- ⚠️ **{skipped} stakeholder(s)/cadence(s) were NOT evaluated** "
            f"(unrecognised cadence, or none recorded) — this is not a clean bill of health")
    return "\n".join(verdict) + "\n" + saved


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
