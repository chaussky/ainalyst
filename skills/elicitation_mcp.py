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
from skills.common import save_artifact, logger

mcp = FastMCP("BABOK_Elicitation_Prep")


# ---------------------------------------------------------------------------
# 4.1.1 — Сохранить план выявления
# ---------------------------------------------------------------------------

@mcp.tool()
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

    # Парсим стейкхолдеров
    try:
        stakeholders = json.loads(stakeholders_json)
    except json.JSONDecodeError as e:
        return (
            f"❌ Ошибка разбора stakeholders_json: {e}\n\n"
            f"Ожидаемый формат:\n"
            f'```json\n'
            f'[{{"name": "Иванов И.И.", "role": "Владелец процесса", '
            f'"influence": "High", "interest": "High", '
            f'"what_to_learn": "Боли текущего процесса"}}]\n'
            f'```'
        )

    if not isinstance(stakeholders, list):
        return "❌ Ошибка: stakeholders_json должен быть списком (JSON array), получен объект другого типа"

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

    from datetime import date
    content = f"""# План выявления требований

**Проект:** {project_name}  
**Дата подготовки:** {date.today().strftime("%d.%m.%Y")}  
**Техника:** {technique}  

---

## Цели выявления

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

    suffix = save_artifact(content, f"Elicitation_Plan_{project_name.replace(' ', '_')}")
    return f"✅ План выявления сохранён.{suffix}"


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

    # Валидируем вопросы
    try:
        questions = json.loads(questions_json)
    except json.JSONDecodeError as e:
        return f"❌ Ошибка разбора questions_json: {e}"

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
