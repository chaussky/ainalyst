"""
BABOK 4.1 — Prepare for Elicitation
MCP-инструменты для подготовки к выявлению требований.

Инструменты:
  - save_elicitation_plan      — сохранить план выявления в .md
  - create_google_form         — создать Google Form (заглушка, требует настройки OAuth)
  - get_form_responses         — получить ответы из Google Form (заглушка)

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
from typing import Literal
from mcp.server.fastmcp import FastMCP
from skills.common import (save_artifact, logger, parse_json_dict_list,
                           update_stakeholder_registry_file,
                           activities_section, load_ba_plan, planned_work_period, guard_artifact_errors)

mcp = FastMCP("BABOK_Elicitation_Prep")


# ---------------------------------------------------------------------------
# 4.1.1 — Сохранить план выявления
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Living stakeholder registry (ADR-003) — 4.1 seeds, 4.2 maintains, 7.4 reads
# ---------------------------------------------------------------------------

_REGISTRY_SOURCE_41 = "4.1 elicitation plan"

# Only fields the BA actually STATES about a person. `what_to_learn` is about the
# session, not the stakeholder, so it stays out of the registry.
_REGISTRY_SEED_FIELDS_41 = ("name", "role", "influence", "interest", "contact")


def _seed_registry_from_plan(project_name: str, stakeholders: list) -> str:
    """Seeds the living registry from the people this session will talk to.

    Never raises: the plan is the deliverable and is already built by the time this
    runs — a registry write that fails must not cost the BA their plan.

    Everything here is INSERT-ONLY beyond the stated fields. 4.1 PLANS an interview,
    it does not observe one, so it must never overwrite what an interview established;
    that is exactly the defect A2 found when planning re-seeded a post-default record
    and reverted an elicited attitude. 4.5 is the tool that observes change, and its
    update is deliberately not insert-only.
    """
    incoming = []
    for s in stakeholders:
        entry = {f: s.get(f) for f in _REGISTRY_SEED_FIELDS_41 if s.get(f)}
        if entry:
            incoming.append(entry)
    if not incoming:
        return ""

    try:
        result = update_stakeholder_registry_file(
            project_name, incoming, source=_REGISTRY_SOURCE_41,
            insert_defaults={
                "found_through": _REGISTRY_SOURCE_41,
                # Planned, not yet elicited. Insert-only, so a later 'Elicited' from
                # 4.2 is never reset by re-running the planning step.
                "coverage_status": "Not covered",
            },
        )
    except Exception as e:  # noqa: BLE001 — never let the plan fail on this
        logger.warning(f"4.1 could not update the stakeholder registry: {e}")
        return ("\n⚠️ Реестр стейкхолдеров не обновлён — "
                "план выявления сохранён.")

    added, updated = len(result.get("added", [])), len(result.get("updated", []))
    if not (added or updated):
        return ""
    return (f"\n📇 Реестр стейкхолдеров: +{added} новых, обновлено {updated} "
            f"(тот же реестр, который ведёт 4.2 и читает 7.4).")


# 3.1 records techniques for the WHOLE practice (BABOK ch. 10), and only four of them
# are elicitation techniques this tool can run. Every adaptive cell of APPROACH_MATRIX
# is Backlog Management / User Stories / Retrospectives — comparing outside this
# intersection would flag EVERY agile project, the way the 4.4 schedule check claimed
# "no communication on record" because its two vocabularies could not meet.
_PLANNED_ELICITATION_TECHNIQUES = {
    "document analysis": "Document Analysis",
    "interview": "Interview", "interviews": "Interview",
    "prototyping": "Prototyping",
    "workshop": "Workshop", "workshops": "Workshop",
}


def _planned_context(project_name: str, technique: str) -> tuple:
    """(markdown_block, warning) for the 3.1 plan behind this session.

    Advisory only: a session plan must never fail because the BA plan is missing or
    damaged.
    """
    plan, note = load_ba_plan(project_name)
    if not isinstance(plan, dict):
        return "", note

    lines = []
    period = planned_work_period(plan, "4.1")
    if period:
        detail = [f"**{period['name']}**"]
        if period["effort"]:
            detail.append(f"плановая трудоёмкость: {period['effort']}")
        if period["when"]:
            detail.append(period["when"])
        lines.append(f"- **Запланированный период работ (BABOK 3.1, элемент .3/.4):** "
                     f"{' — '.join(detail)}")
        # 3.1b marks a machine-made skeleton, and the BA plan report says so. Repeating
        # the period here without that mark would state an invented name and effort as
        # something someone planned.
        if activities_section(plan).get("generated"):
            lines.append(
                "  ℹ️ Этот период сгенерирован из выбранного подхода, а не запланирован "
                "вручную — если он не подходит, поправьте его через `plan_ba_activities`.")

    approach = plan.get("ba_approach")
    raw_techniques = approach.get("techniques") if isinstance(approach, dict) else None
    techniques = ([t for t in raw_techniques if isinstance(t, str)]
                  if isinstance(raw_techniques, list) else [])
    if techniques:
        planned = []
        for name in techniques:
            mapped = _PLANNED_ELICITATION_TECHNIQUES.get(name.strip().lower())
            if mapped and mapped not in planned:
                planned.append(mapped)
        if not planned:
            lines.append(
                f"- ℹ️ План 3.1 не рекомендует ни одной техники выявления "
                f"({', '.join(techniques)}), поэтому сверять `{technique}` "
                f"не с чем.")
        elif technique in planned:
            lines.append(
                f"- ✅ `{technique}` есть среди техник, рекомендованных 3.1 "
                f"({', '.join(planned)}).")
        else:
            lines.append(
                f"- ⚠️ 3.1 рекомендовала {', '.join(planned)}; эта сессия идёт по "
                f"`{technique}`. Это не блокер — важно обоснование ниже.")

    if not lines:
        return "", note
    # The trailing blank line is load-bearing for the document, not for Markdown: every
    # other separator in this artefact is followed by one, and the block is spliced in
    # directly before a heading.
    block = "\n".join(["## Из плана БА (3.1)", ""] + lines + ["", "---", "", ""])
    return block, note


@mcp.tool()
@guard_artifact_errors
def save_elicitation_plan(
    project_name: str,
    goals: str,
    stakeholders_json: str,
    technique: Literal[
        "Интервью",
        "Анкетирование",
        "Воркшоп",
        "Мозговой штурм",
        "Анализ документов",
        "Наблюдение",
        "Прототипирование",
        "Фокус-группа",
        "Бенчмаркинг"
    ],
    technique_rationale: str,
    questions_or_agenda: str,
    expected_outcomes: str,
) -> str:
    """
    BABOK 4.1 — Сохраняет план выявления требований в .md файл.

    Args:
        project_name:          Название проекта или инициативы.
        goals:                 Цели выявления. Что должны узнать / подтвердить.
        stakeholders_json:     JSON-массив стейкхолдеров. Формат:
                               [{"name": "Иванов И.И.", "role": "Владелец процесса",
                                 "influence": "High", "interest": "High",
                                 "what_to_learn": "Боли текущего процесса"}]
        technique:             Выбранная техника выявления.
        technique_rationale:   Обоснование выбора техники.
        questions_or_agenda:   Вопросы (для интервью/анкеты) или повестка (для воркшопа).
                               Передавать как текст с нумерацией или markdown.
        expected_outcomes:     Ожидаемые результаты сессии выявления.

    Returns:
        Путь к сохранённому файлу плана выявления.
    """
    logger.info(f"4.1 Сохранение плана выявления: проект='{project_name}', техника='{technique}'")

    # An elicitation plan without stakeholders is meaningless — keep this required
    # (the previous json.loads("") failure had made it required by accident).
    stakeholders, error = parse_json_dict_list(
        stakeholders_json, "stakeholders_json", required=True,
        example='[{"name": "Jane Doe", "role": "Process Owner", "influence": "High", '
                '"interest": "High", "what_to_learn": "Pain points of the current process"}]')
    if error:
        return error

    # Формируем таблицу стейкхолдеров
    stakeholder_rows = "\n".join([
        f"| {s.get('name', '—')} | {s.get('role', '—')} | "
        f"{s.get('influence', '—')} | {s.get('interest', '—')} | "
        f"{s.get('what_to_learn', '—')} |"
        for s in stakeholders
    ])

    stakeholder_table = (
        "| Стейкхолдер | Роль | Влияние | Интерес | Что хотим узнать |\n"
        "| :--- | :--- | :---: | :---: | :--- |\n"
        + stakeholder_rows
    )

    planned_block, plan_note = _planned_context(project_name, technique)

    from datetime import date
    content = f"""# Elicitation Activity Plan

**Проект:** {project_name}  
**Дата подготовки:** {date.today().strftime("%d.%m.%Y")}  
**Техника:** {technique}  

---

{planned_block}## Цели выявления

{goals}

---

## Стейкхолдеры

{stakeholder_table}

---

## Выбранная техника: {technique}

**Обоснование:** {technique_rationale}

---

## Вопросы / Повестка

{questions_or_agenda}

---

## Ожидаемые результаты

{expected_outcomes}
"""

    # Numbered prefix like every other chapter; project_id is the FOLDER, so repeating
    # the project name in the filename is redundant (and was the shape that misled the
    # 7.1 consumer into globbing for a pid that the filename never carries).
    suffix = save_artifact(content, "4_1_elicitation_plan", project_id=project_name)
    registry_note = _seed_registry_from_plan(project_name, stakeholders)
    return f"✅ План выявления сохранён.{suffix}{registry_note}" + (
        f"\n{plan_note}" if plan_note else "")


# ---------------------------------------------------------------------------
# 4.1.2 — Создать Google Form (заглушка)
# ---------------------------------------------------------------------------

@mcp.tool()
def create_google_form(
    title: str,
    description: str,
    questions_json: str,
) -> str:
    """
    BABOK 4.1 — Создаёт Google Form для анкетирования стейкхолдеров.

    ⚠️  ЗАГЛУШКА: требует настройки Google OAuth и Forms API.
        Инструкция по настройке в конце ответа.

    Args:
        title:          Заголовок формы (название анкеты).
        description:    Вводный текст для респондентов. Укажи цель опроса и дедлайн.
        questions_json: JSON-массив вопросов. Формат:
                        [
                          {
                            "text": "Текст вопроса",
                            "type": "text" | "scale" | "choice" | "checkbox" | "ranking",
                            "required": true | false,
                            "options": ["Вариант 1", "Вариант 2"]  // для choice / checkbox / ranking
                          }
                        ]

    Returns:
        Ссылку на созданную форму (после настройки API) или инструкцию по настройке.
    """
    logger.info(f"4.1 create_google_form вызван: title='{title}'")

    questions, error = parse_json_dict_list(
        questions_json, "questions_json",
        example='[{"text": "Question text", "type": "text", "required": true}]')
    if error:
        return error

    # Формируем превью анкеты
    preview_lines = [f"## Превью анкеты: {title}\n", f"_{description}_\n"]
    for i, q in enumerate(questions, 1):
        q_type = q.get("type", "text")
        required = "\\*" if q.get("required") else ""
        preview_lines.append(f"**{i}. {q.get('text', '—')}** {required} `[{q_type}]`")
        if q.get("options"):
            for opt in q["options"]:
                preview_lines.append(f"   - {opt}")

    preview = "\n".join(preview_lines)

    setup_instructions = """
---

## ⚙️ Настройка Google Forms API

Для активации инструмента выполни следующие шаги:

### 1. Google Cloud Project
1. Перейди на https://console.cloud.google.com
2. Создай новый проект (или выбери существующий)
3. Включи **Google Forms API**: APIs & Services → Enable APIs → "Google Forms API"
4. Включи **Google Drive API** (нужен для получения ответов)

### 2. OAuth 2.0 credentials
1. APIs & Services → Credentials → Create Credentials → OAuth Client ID
2. Тип: Desktop App
3. Скачай `credentials.json`

### 3. Установка зависимостей
```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 googleapiclient
```

### 4. Активация в коде
Замени в файле `skills/elicitation_mcp.py`:
```python
# GOOGLE_CREDENTIALS_PATH = "credentials.json"  # раскомментируй
# GOOGLE_TOKEN_PATH = "token.json"               # раскомментируй
```

После настройки инструмент создаст форму и вернёт ссылку для рассылки.
"""

    return preview + setup_instructions


# ---------------------------------------------------------------------------
# 4.1.3 — Получить ответы из Google Form (заглушка)
# ---------------------------------------------------------------------------

@mcp.tool()
def get_form_responses(
    form_id: str,
    export_format: Literal["summary", "full", "csv"] = "summary",
) -> str:
    """
    BABOK 4.1 — Получает и структурирует ответы из Google Form.

    ⚠️  ЗАГЛУШКА: требует настроенного Google OAuth (см. create_google_form).

    Args:
        form_id:        ID формы из URL Google Forms.
                        Пример: из https://forms.gle/ABC123 → form_id = "ABC123"
                        Полный ID из URL редактора: /forms/d/{FORM_ID}/edit
        export_format:  Формат вывода:
                        - "summary"  — сводка по каждому вопросу с агрегацией
                        - "full"     — все ответы построчно
                        - "csv"      — данные для сохранения в таблицу

    Returns:
        Структурированные ответы из формы или инструкцию по настройке API.
    """
    logger.info(f"4.1 get_form_responses вызван: form_id='{form_id}', format='{export_format}'")

    mock_note = f"""
## ⚠️ Заглушка: get_form_responses

Инструмент вызван для формы `{form_id}` (формат: {export_format}).

После настройки Google API этот инструмент:
- Получит все ответы через Google Forms API
- Для `summary`: агрегирует ответы по каждому вопросу, выделит паттерны
- Для `full`: вернёт таблицу всех ответов с датами
- Для `csv`: сохранит данные в файл для анализа в Excel / Google Sheets

### Что делать прямо сейчас

Если ответы уже собраны вручную — передай их как текст или CSV напрямую в чат,
и Claude структурирует и проанализирует их без API.

### Настройка API
См. инструкцию в инструменте `create_google_form`.
"""
    return mock_note


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
