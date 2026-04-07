"""
BABOK 4.2 — Conduct Elicitation
MCP-инструменты для обработки результатов выявления.

Инструменты:
  - process_elicitation_results  — сохранить структурированный результат сессии
  - compare_elicitation_results  — сравнить несколько сессий, найти противоречия
  - save_gap_analysis            — сохранить gap-анализ и рекомендации BA

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
from datetime import date
from typing import Literal
from mcp.server.fastmcp import FastMCP
from skills.common import save_artifact, logger

mcp = FastMCP("BABOK_Elicitation_Conduct")


# ---------------------------------------------------------------------------
# 4.2.1 — Сохранить структурированные результаты одной сессии
# ---------------------------------------------------------------------------

@mcp.tool()
def process_elicitation_results(
    project_name: str,
    session_date: str,
    stakeholder_role: str,
    session_type: Literal["Интервью", "Воркшоп", "Анкетирование", "Наблюдение", "Анализ документов"],
    stakeholder_profile_json: str,
    pains_json: str,
    requirements_json: str,
    gaps_and_signals: str,
    ba_recommendations: str,
    maturity_level: Literal["Низкий", "Средний", "Хороший", "Высокий"],
    maturity_notes: str,
) -> str:
    """
    BABOK 4.2 — Сохраняет структурированные результаты одной сессии выявления.
    Результат передаётся в задачу 4.3 (подтверждение).

    Args:
        project_name:              Название проекта.
        session_date:              Дата сессии в формате ДД.ММ.ГГГГ.
        stakeholder_role:          Роль стейкхолдера (должность / функция).
        session_type:              Тип сессии выявления.
        stakeholder_profile_json:  Профайл стейкхолдера. Формат:
                                   {
                                     "participation_type": "Decision maker / Influencer / End user",
                                     "influence": "High / Medium / Low",
                                     "interest": "High / Medium / Low",
                                     "attitude": "Champion / Neutral / Blocker",
                                     "key_expectations": "текст",
                                     "key_concerns": "текст",
                                     "related_stakeholders": ["роль 1", "роль 2"]
                                   }
        pains_json:                Список болей. Формат:
                                   [
                                     {
                                       "title": "краткое название",
                                       "description": "контекст и суть",
                                       "frequency": "как часто",
                                       "business_impact": "влияние на бизнес",
                                       "quote": "дословная цитата если есть"
                                     }
                                   ]
        requirements_json:         Требования по типам. Формат:
                                   {
                                     "functional": ["FR-001: ...", "FR-002: ..."],
                                     "non_functional": ["NFR-001: ..."],
                                     "constraints": ["..."],
                                     "business_rules": ["..."]
                                   }
        gaps_and_signals:          Анализ белых пятен и скрытых сигналов.
                                   Текст с описанием недосказанностей, незакрытых тем,
                                   противоречий, политических сигналов.
        ba_recommendations:        Конкретные рекомендации BA: что уточнить,
                                   у кого, нужен ли follow-up.
        maturity_level:            Общий уровень зрелости требований.
        maturity_notes:            Комментарий к оценке зрелости.

    Returns:
        Путь к сохранённому файлу результатов выявления.
    """
    logger.info(f"4.2 Сохранение результатов выявления: проект='{project_name}', тип='{session_type}'")

    # Парсим JSON
    try:
        profile = json.loads(stakeholder_profile_json)
        pains = json.loads(pains_json)
        reqs = json.loads(requirements_json)
    except json.JSONDecodeError as e:
        return f"❌ Ошибка разбора JSON: {e}"

    # Формируем блок болей
    pains_md = ""
    for i, p in enumerate(pains, 1):
        pains_md += f"\n### Боль {i}: {p.get('title', '—')}\n"
        pains_md += f"- **Описание:** {p.get('description', '—')}\n"
        pains_md += f"- **Частота:** {p.get('frequency', '—')}\n"
        pains_md += f"- **Влияние на бизнес:** {p.get('business_impact', '—')}\n"
        if p.get('quote'):
            pains_md += f"- **Цитата:** *«{p['quote']}»*\n"

    # Формируем блок требований
    def req_list(items):
        return "\n".join(f"- {r}" for r in items) if items else "- Не выявлено"

    # Формируем блок профайла
    related = ", ".join(profile.get("related_stakeholders", [])) or "Не выявлены"

    content = f"""# Результаты выявления (неподтверждённые)

**Проект:** {project_name}
**Дата сессии:** {session_date}
**Тип сессии:** {session_type}
**Стейкхолдер:** {stakeholder_role}
**Статус:** Неподтверждённые результаты → передаётся в задачу 4.3

---

## 1. Профайл стейкхолдера

| Параметр | Значение |
| :--- | :--- |
| **Тип участия** | {profile.get('participation_type', '—')} |
| **Влияние** | {profile.get('influence', '—')} |
| **Интерес** | {profile.get('interest', '—')} |
| **Отношение к проекту** | {profile.get('attitude', '—')} |
| **Ключевые ожидания** | {profile.get('key_expectations', '—')} |
| **Основные опасения** | {profile.get('key_concerns', '—')} |
| **Смежные стейкхолдеры** | {related} |

---

## 2. Потребности и боли
{pains_md}

---

## 3. Требования

### Функциональные требования
{req_list(reqs.get('functional', []))}

### Нефункциональные требования
{req_list(reqs.get('non_functional', []))}

### Ограничения
{req_list(reqs.get('constraints', []))}

### Бизнес-правила
{req_list(reqs.get('business_rules', []))}

---

## 4. Белые пятна и скрытые сигналы

{gaps_and_signals}

---

## 5. Рекомендации BA

{ba_recommendations}

---

## 6. Оценка зрелости требований

**Общий уровень:** {maturity_level}

{maturity_notes}
"""

    suffix = save_artifact(
        content,
        f"Elicitation_Results_{project_name.replace(' ', '_')}_{session_date.replace('.', '-')}"
    )
    return f"✅ Результаты выявления сохранены.{suffix}"


# ---------------------------------------------------------------------------
# 4.2.2 — Сохранить кросс-анализ нескольких сессий
# ---------------------------------------------------------------------------

@mcp.tool()
def compare_elicitation_results(
    project_name: str,
    sessions_summary: str,
    contradictions: str,
    requirements_registry_json: str,
    political_map: str,
    follow_up_plan: str,
) -> str:
    """
    BABOK 4.2 — Сохраняет кросс-анализ нескольких сессий выявления.

    Args:
        project_name:                Название проекта.
        sessions_summary:            Краткое описание проанализированных сессий
                                     (кто, когда, тип).
        contradictions:              Описание противоречий между стейкхолдерами:
                                     фактические, приоритетные, пробелы покрытия.
        requirements_registry_json:  Сводный реестр требований. Формат:
                                     [
                                       {
                                         "id": "FR-001",
                                         "requirement": "текст",
                                         "sources": ["Стейкхолдер А", "Стейкхолдер Б"],
                                         "priority": "High / Medium / Low / Не определён",
                                         "status": "Согласовано / Требует подтверждения / Противоречие",
                                         "notes": "примечание"
                                       }
                                     ]
        political_map:               Наблюдения о политической динамике между
                                     стейкхолдерами и рисках для проекта.
        follow_up_plan:              План довыявления: вопросы, стейкхолдеры,
                                     форматы, приоритеты.

    Returns:
        Путь к сохранённому файлу кросс-анализа.
    """
    logger.info(f"4.2 Кросс-анализ: проект='{project_name}'")

    try:
        registry = json.loads(requirements_registry_json)
    except json.JSONDecodeError as e:
        return f"❌ Ошибка разбора requirements_registry_json: {e}"

    # Формируем таблицу реестра
    reg_rows = "\n".join([
        f"| {r.get('id','—')} | {r.get('requirement','—')} | "
        f"{', '.join(r.get('sources',[]))} | {r.get('priority','—')} | "
        f"{r.get('status','—')} | {r.get('notes','—')} |"
        for r in registry
    ])

    reg_table = (
        "| ID | Требование | Источники | Приоритет | Статус | Примечание |\n"
        "| :--- | :--- | :--- | :---: | :--- | :--- |\n"
        + reg_rows
    )

    content = f"""# Кросс-анализ результатов выявления

**Проект:** {project_name}
**Дата анализа:** {date.today().strftime("%d.%m.%Y")}
**Статус:** Неподтверждённые результаты → передаётся в задачу 4.3

---

## 1. Проанализированные сессии

{sessions_summary}

---

## 2. Противоречия между стейкхолдерами

{contradictions}

---

## 3. Сводный реестр требований

{reg_table}

---

## 4. Политическая карта

{political_map}

---

## 5. План довыявления

{follow_up_plan}
"""

    suffix = save_artifact(content, f"Cross_Analysis_{project_name.replace(' ', '_')}")
    return f"✅ Кросс-анализ сохранён.{suffix}"


# ---------------------------------------------------------------------------
# 4.2.3 — Сохранить анализ выявления в контексте Change Request
# ---------------------------------------------------------------------------

@mcp.tool()
def save_cr_elicitation_analysis(
    project_name: str,
    cr_description: str,
    affected_artifacts_json: str,
    outdated_data: str,
    follow_up_questions: str,
    scope_assessment: str,
    workshop_needed: bool,
    workshop_notes: str = "",
) -> str:
    """
    BABOK 4.2 — Сохраняет анализ выявления в контексте Change Request.

    Args:
        project_name:              Название проекта.
        cr_description:            Описание CR: что меняется, инициатор, причина.
        affected_artifacts_json:   Затронутые артефакты. Формат:
                                   [
                                     {
                                       "artifact": "название / ID",
                                       "type": "Профайл / Боль / FR / NFR / User Story",
                                       "affected": true,
                                       "change_type": "Обновить / Удалить / Заморозить"
                                     }
                                   ]
        outdated_data:             Описание устаревших данных и что с ними делать.
        follow_up_questions:       Новые вопросы для выявления: что, у кого,
                                   приоритет, формат.
        scope_assessment:          Оценка масштаба довыявления и рисков.
        workshop_needed:           Нужен ли воркшоп для согласования.
        workshop_notes:            Состав участников и повестка воркшопа (если нужен).

    Returns:
        Путь к сохранённому файлу анализа CR.
    """
    logger.info(f"4.2 CR-анализ: проект='{project_name}'")

    try:
        artifacts = json.loads(affected_artifacts_json)
    except json.JSONDecodeError as e:
        return f"❌ Ошибка разбора affected_artifacts_json: {e}"

    # Формируем таблицу артефактов
    art_rows = "\n".join([
        f"| {a.get('artifact','—')} | {a.get('type','—')} | "
        f"{'✅' if a.get('affected') else '—'} | {a.get('change_type','—')} |"
        for a in artifacts
    ])

    art_table = (
        "| Артефакт | Тип | Затронут | Действие |\n"
        "| :--- | :--- | :---: | :--- |\n"
        + art_rows
    )

    workshop_block = ""
    if workshop_needed:
        workshop_block = f"\n## 6. Воркшоп\n\n**Необходим:** Да\n\n{workshop_notes}\n"
    else:
        workshop_block = "\n## 6. Воркшоп\n\n**Необходим:** Нет\n"

    content = f"""# Анализ выявления в контексте Change Request

**Проект:** {project_name}
**Дата анализа:** {date.today().strftime("%d.%m.%Y")}
**Статус:** Требует довыявления

---

## 1. Описание Change Request

{cr_description}

---

## 2. Зона влияния

{art_table}

---

## 3. Устаревшие данные

{outdated_data}

---

## 4. План довыявления

{follow_up_questions}

---

## 5. Оценка масштаба

{scope_assessment}
{workshop_block}
"""

    suffix = save_artifact(content, f"CR_Elicitation_{project_name.replace(' ', '_')}")
    return f"✅ Анализ CR сохранён.{suffix}"


# ---------------------------------------------------------------------------
# 4.2.4 — Обновить живой реестр стейкхолдеров
# ---------------------------------------------------------------------------

@mcp.tool()
def update_stakeholder_registry(
    project_name: str,
    session_source: str,
    new_stakeholders_json: str,
) -> str:
    """
    BABOK 4.2 / 3.2 — Обновляет живой реестр стейкхолдеров проекта.

    Реестр стейкхолдеров — живой документ. Он начинается с 1–2 известных людей
    (обычно спонсор) и пополняется после каждой сессии выявления по цепочке:
    каждый стейкхолдер называет следующих.

    Вызывай этот инструмент после каждого интервью / воркшопа / анализа документов.

    Args:
        project_name:           Название проекта.
        session_source:         Откуда получена информация о новых стейкхолдерах.
                                Пример: "Интервью с Ивановым И.И. (CFO), 15.03.2024"
        new_stakeholders_json:  Список новых или обновлённых стейкхолдеров. Формат:
                                [
                                  {
                                    "name": "Петров П.П.",
                                    "role": "Руководитель отдела закупок",
                                    "department": "Закупки",
                                    "found_through": "Иванов И.И. (CFO)",
                                    "why_important": "Принимает решения по бюджету закупок",
                                    "influence": "High / Medium / Low",
                                    "interest": "High / Medium / Low",
                                    "attitude": "Champion / Neutral / Blocker / Неизвестно",
                                    "coverage_status": "Не охвачен / В плане / Выявлен",
                                    "priority": "Срочно / По плану / Под вопросом",
                                    "recommended_format": "Интервью / Воркшоп / Письменный запрос",
                                    "notes": "доп. информация"
                                  }
                                ]

    Returns:
        Путь к обновлённому файлу реестра стейкхолдеров.
    """
    logger.info(f"4.2 Обновление реестра стейкхолдеров: проект='{project_name}', источник='{session_source}'")

    try:
        stakeholders = json.loads(new_stakeholders_json)
    except json.JSONDecodeError as e:
        return (
            f"❌ Ошибка разбора new_stakeholders_json: {e}\n\n"
            f"Ожидаемый формат: список объектов с полями name, role, found_through и др."
        )

    today = date.today().strftime("%d.%m.%Y")

    # Таблица новых стейкхолдеров
    rows = []
    for s in stakeholders:
        rows.append(
            f"| {s.get('name', '—')} | {s.get('role', '—')} | "
            f"{s.get('department', '—')} | {s.get('found_through', '—')} | "
            f"{s.get('influence', '—')} | {s.get('interest', '—')} | "
            f"{s.get('attitude', 'Неизвестно')} | {s.get('coverage_status', '—')} | "
            f"{s.get('priority', '—')} | {s.get('recommended_format', '—')} |"
        )

    table_header = (
        "| Стейкхолдер | Роль | Отдел | Найден через | Влияние | Интерес | "
        "Отношение | Статус охвата | Приоритет | Формат |\n"
        "| :--- | :--- | :--- | :--- | :---: | :---: | :--- | :--- | :---: | :--- |\n"
    )

    # Цепочка обнаружения
    chain_lines = []
    for s in stakeholders:
        source = s.get('found_through', 'Неизвестно')
        name = s.get('name', '—')
        role = s.get('role', '—')
        why = s.get('why_important', '')
        chain_lines.append(f"- **{name}** ({role}) ← через: {source}" + (f"\n  > {why}" if why else ""))

    # Не охваченные — отдельный список действий
    uncovered = [s for s in stakeholders if s.get('coverage_status') == 'Не охвачен']
    urgent = [s for s in uncovered if s.get('priority') == 'Срочно']

    uncovered_block = ""
    if uncovered:
        uncovered_block = "\n## ⚠️ Требуют охвата выявлением\n\n"
        if urgent:
            uncovered_block += "### Срочно\n"
            for s in urgent:
                uncovered_block += (
                    f"- **{s.get('name', '—')}** ({s.get('role', '—')}) — "
                    f"{s.get('recommended_format', 'Интервью')}\n"
                    f"  Почему важен: {s.get('why_important', '—')}\n"
                )
        not_urgent = [s for s in uncovered if s.get('priority') != 'Срочно']
        if not_urgent:
            uncovered_block += "\n### По плану\n"
            for s in not_urgent:
                uncovered_block += (
                    f"- **{s.get('name', '—')}** ({s.get('role', '—')}) — "
                    f"{s.get('recommended_format', 'Интервью')}\n"
                )

    content = f"""# Реестр стейкхолдеров (живой документ)

**Проект:** {project_name}
**Последнее обновление:** {today}
**Источник обновления:** {session_source}

---

## Новые / обновлённые стейкхолдеры

{table_header}{"".join(rows) if rows else "| — | — | — | — | — | — | — | — | — | — |"}

---

## Цепочка обнаружения

{chr(10).join(chain_lines) if chain_lines else "— Нет данных —"}

{uncovered_block}
---

> Этот файл обновляется после каждой сессии выявления.
> Полный реестр проекта формируется накопительно из всех обновлений.
"""

    suffix = save_artifact(content, f"Stakeholder_Registry_{project_name.replace(' ', '_')}")
    return f"✅ Реестр стейкхолдеров обновлён. Новых записей: {len(stakeholders)}.{suffix}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
