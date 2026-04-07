"""
BABOK 4.4 — Communicate Business Analysis Information
MCP-инструменты для подготовки и фиксации коммуникационных пакетов.

Инструменты:
  - prepare_communication_package  — сохранить адаптированный пакет для аудитории
  - log_communication              — зафиксировать факт коммуникации и её результат

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
from datetime import date
from typing import Literal
from mcp.server.fastmcp import FastMCP
from skills.common import save_artifact, logger

mcp = FastMCP("BABOK_Communicate")


# ---------------------------------------------------------------------------
# 4.4.1 — Подготовить адаптированный коммуникационный пакет
# ---------------------------------------------------------------------------

@mcp.tool()
def prepare_communication_package(
    project_name: str,
    source_artifact_path: str,
    audience_role: Literal[
        "Бизнес-заказчик",
        "Руководитель",
        "Разработчик",
        "Архитектор / Техлид",
        "Тестировщик",
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

    try:
        profile = json.loads(audience_profile_json)
        key_messages = json.loads(key_messages_json)
    except json.JSONDecodeError as e:
        return f"❌ Ошибка разбора JSON: {e}"

    today = date.today().strftime("%d.%m.%Y")

    # Иконки для attitude
    attitude = profile.get("attitude", "Neutral")
    attitude_icon = {"Champion": "🟢", "Neutral": "🟡", "Blocker": "🔴"}.get(attitude, "🟡")

    # -----------------------------------------------------------------------
    # Формируем пакет
    # -----------------------------------------------------------------------
    lines = []
    lines.append(f"# Коммуникационный пакет: {audience_role}\n")
    lines.append(f"**Проект:** {project_name}  ")
    lines.append(f"**Аудитория:** {audience_role}  ")
    lines.append(f"**Дата подготовки:** {today}  ")
    lines.append(f"**Источник:** `{source_artifact_path}`\n")
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

    # Ключевые сообщения
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

    return save_artifact(meta + content, prefix="4_4_comm_package")


# ---------------------------------------------------------------------------
# 4.4.2 — Зафиксировать факт коммуникации
# ---------------------------------------------------------------------------

@mcp.tool()
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

    try:
        participants = json.loads(participants_json)
        action_items = json.loads(action_items_json)
    except json.JSONDecodeError as e:
        return f"❌ Ошибка разбора JSON: {e}"

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

    return save_artifact(meta + content, prefix="4_4_comm_log")


# ---------------------------------------------------------------------------
# 4.4.3 — Проверить расписание коммуникаций
# ---------------------------------------------------------------------------

@mcp.tool()
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

    try:
        stakeholders = json.loads(stakeholders_json)
        comm_log = json.loads(communication_log_json)
        events = json.loads(triggered_events_json)
    except json.JSONDecodeError as e:
        return f"❌ Ошибка разбора JSON: {e}"

    from datetime import datetime, timedelta

    def parse_date(s: str):
        if not s:
            return None
        try:
            return datetime.strptime(s.strip(), "%d.%m.%Y")
        except ValueError:
            return None

    today = parse_date(today_date) or datetime.today()

    # Последние коммуникации из лога (дополняют данные реестра)
    log_by_role = {}
    for entry in comm_log:
        role = entry.get("audience_role", "")
        d = parse_date(entry.get("communication_date", ""))
        if d and (role not in log_by_role or d > log_by_role[role]["date"]):
            log_by_role[role] = {"date": d, "status": entry.get("understanding_status", ""), "followup": entry.get("needs_followup", False)}

    # Частота → количество дней
    freq_days = {
        "После каждой сессии": 3,      # grace period 3 дня
        "Еженедельно": 7,
        "По milestone": None,           # только триггер
        "По запросу": None,
    }

    # Собираем очередь коммуникаций
    urgent = []       # нужно сегодня
    due_soon = []     # в ближайшие 3 дня
    triggered = []    # сработал триггер
    followup_due = [] # незакрытый follow-up из лога

    for sh in stakeholders:
        role = sh.get("role", "—")
        freq = sh.get("comm_frequency", "По запросу")
        triggers = sh.get("comm_triggers", [])

        # Определяем дату последней коммуникации
        last_date = parse_date(sh.get("last_communication_date", ""))
        if role in log_by_role and (not last_date or log_by_role[role]["date"] > last_date):
            last_date = log_by_role[role]["date"]

        # Проверяем просроченность по частоте
        days_limit = freq_days.get(freq)
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

        # Незакрытые follow-up
        if role in log_by_role and log_by_role[role].get("followup"):
            followup_due.append({
                "role": role,
                "status": log_by_role[role].get("status", "—"),
                "date": log_by_role[role]["date"].strftime("%d.%m.%Y"),
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
        lines.append("## ✅ Все коммуникации в порядке\n")
        lines.append("Нет просроченных или триггерных коммуникаций.\n")
    else:
        lines.append(f"## Требуют внимания сегодня: {total_actions} стейкхолдер(а)\n")

    # Срочные (просроченные)
    if urgent:
        lines.append("---\n")
        lines.append("## 🔴 Срочно — просрочено\n")
        for item in sorted(urgent, key=lambda x: x.get("influence", "Low"), reverse=True):
            lines.append(f"**{item['role']}** (влияние: {item['influence']})  ")
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

    return save_artifact(meta + content, prefix="4_4_comm_schedule")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
