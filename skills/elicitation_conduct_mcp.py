"""
BABOK 4.2 — Conduct Elicitation
MCP-инструменты для обработки результатов выявления.

Tools:
  - process_elicitation_results   — save the structured result of a session
                                    (+ elicitation_results.json with risks, read by 6.3)
  - compare_elicitation_results   — compare multiple sessions, find contradictions
  - save_cr_elicitation_analysis  — elicitation analysis in the context of a Change Request
  - update_stakeholder_registry   — merge newly discovered stakeholders into the living registry

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date
from typing import Literal
from mcp.server.fastmcp import FastMCP
from skills.common import (write_json_artifact,
    save_artifact, logger, data_path, normalize_project_id,
    parse_json_dict, parse_json_dict_list, parse_json_list,
    update_stakeholder_registry_file, guard_artifact_errors)

mcp = FastMCP("BABOK_Elicitation_Conduct")


# The single structured artifact 6.3 `import_risks_from_context` reads. The name must
# match the consumer exactly: it builds the path with the same normalize_project_id and
# data_path (finding 7.4-A and 7.6-A were both consumers reading a filename nobody wrote).
ELICITATION_RESULTS_FILENAME = "elicitation_results.json"


def _elicitation_results_path(project_name: str) -> str:
    safe = normalize_project_id(project_name)
    return data_path(project_name, f"{safe}_{ELICITATION_RESULTS_FILENAME}")


def _parse_session_risks(risks_json: str, default_stakeholder: str):
    """Parses `risks_json` into [{"description", "stakeholder"}]. Returns (risks, error).

    Tolerant at the boundary, strict in what is stored: a bare string becomes a
    description, and the `risk`/`source` spellings 6.3 accepts on read are accepted here
    too. The input is written by an LLM, and CH4-A was exactly the class where a
    wrong-but-meaningful shape crashed instead of being handled.
    """
    raw, error = parse_json_list(
        risks_json, "risks_json",
        example='[{"description": "The legacy API may not survive the load"}]')
    if error:
        return None, error

    risks = []
    for item in raw:
        if isinstance(item, str):
            description, stakeholder = item.strip(), default_stakeholder
        elif isinstance(item, dict):
            description = str(item.get("description") or item.get("risk") or "").strip()
            stakeholder = (str(item.get("stakeholder") or item.get("source") or "").strip()
                           or default_stakeholder)
        else:
            return None, (
                "❌ `risks_json`: каждый элемент должен быть объектом или строкой.\n"
                'Пример: [{"description": "Legacy-API может не выдержать нагрузку"}]'
            )
        if description:
            risks.append({"description": description, "stakeholder": stakeholder})

    # The caller supplied items but none carried a description under any accepted
    # spelling — i.e. the wrong FIELD NAME, this repo's most repeated defect class.
    # Dropping them silently and still answering "✅ saved" is the worst outcome: the
    # BA believes the risks were recorded and 6.3 later finds nothing.
    if raw and not risks:
        return None, (
            "❌ `risks_json`: ни у одного риска нет описания. Принимаются ключи "
            "`description` (или `risk`) и `stakeholder` (или `source`); голая строка "
            'читается как описание.\n'
            'Пример: [{"description": "Legacy-API может не выдержать нагрузку"}]'
        )
    return risks, ""


def _record_session_risks(project_name: str, session_date: str, stakeholder_role: str,
                          session_type: str, risks: list) -> bool:
    """Accumulates this session's risks into the one JSON per project that 6.3 reads.

    Sessions are keyed by (date, role, type): re-running one REPLACES its slice in place
    rather than appending duplicates. The flat top-level `risks_mentioned` — the exact
    shape 6.3 consumes — is rebuilt from all sessions on every write, so it can never
    drift from `sessions`.

    No risks: the file is neither created NOR modified. An omission means the caller
    supplied nothing this time, not that recorded risks should be deleted.
    """
    if not risks:
        return False

    path = _elicitation_results_path(project_name)
    today = date.today().strftime("%d.%m.%Y")
    data = {"project": project_name, "created": today, "updated": today, "sessions": []}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                # Validate ELEMENTS, not just the container: the loop below calls
                # `s.get(...)` and unpacks `{**risk}`, so a stored file whose sessions
                # list holds a string raised AttributeError/TypeError — and because this
                # runs BEFORE the Markdown is saved, the BA lost the whole session
                # report too. Corrupt entries are dropped, never fatal.
                sessions = [
                    s for s in loaded.get("sessions", [])
                    if isinstance(s, dict) and isinstance(s.get("risks_mentioned"), list)
                ]
                for s in sessions:
                    s["risks_mentioned"] = [
                        r for r in s["risks_mentioned"] if isinstance(r, dict)
                    ]
                loaded["sessions"] = sessions
                # A file with a top-level `risks_mentioned` but no `sessions` is what a
                # BA would hand-write while the producer did not exist. Overwriting it
                # destroyed their data; the project rule is "never delete data", so the
                # orphaned risks are migrated into a session instead.
                if not sessions and isinstance(loaded.get("risks_mentioned"), list):
                    orphans = [r for r in loaded["risks_mentioned"] if isinstance(r, dict)]
                    if orphans:
                        loaded["sessions"] = [{
                            "session_date": "", "stakeholder_role": "",
                            "session_type": "Imported",
                            "risks_mentioned": orphans,
                        }]
                data = loaded
        except (json.JSONDecodeError, OSError):
            pass  # unreadable/corrupt: start fresh rather than blocking the BA

    entry = {
        "session_date": session_date,
        "stakeholder_role": stakeholder_role,
        "session_type": session_type,
        "risks_mentioned": risks,
    }
    key = (session_date, stakeholder_role, session_type)
    sessions = data.setdefault("sessions", [])
    # Replace-in-place only on a FULLY specified key. A blank component means
    # "unspecified", not "the same session", and collapsing on it silently discarded
    # the earlier slice.
    if all(key):
        for i, s in enumerate(sessions):
            if (s.get("session_date"), s.get("stakeholder_role"),
                    s.get("session_type")) == key:
                sessions[i] = entry  # replace in place, preserving order
                break
        else:
            sessions.append(entry)
    else:
        sessions.append(entry)

    data["risks_mentioned"] = [
        {**risk, "session_date": s.get("session_date", "")}
        for s in sessions for risk in s.get("risks_mentioned", [])
    ]
    data["updated"] = today
    data.setdefault("created", today)

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write_json_artifact(path, data)
        return True
    except OSError as e:
        logger.warning(f"4.2 Could not persist elicitation results JSON: {e}")
        return False


# ---------------------------------------------------------------------------
# 4.2.1 — Сохранить структурированные результаты одной сессии
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def process_elicitation_results(
    project_name: str,
    session_date: str,
    stakeholder_role: str,
    session_type: Literal["Interview", "Workshop", "Survey", "Observation", "Document Analysis",
                          "Brainstorming", "Prototyping", "Focus Group", "Benchmarking", "Experiments"],
    stakeholder_profile_json: str,
    pains_json: str,
    requirements_json: str,
    gaps_and_signals: str,
    ba_recommendations: str,
    maturity_level: Literal["Низкий", "Средний", "Хороший", "Высокий"],
    maturity_notes: str,
    risks_json: str = "[]",
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
        gaps_and_signals:          Analysis of blind spots and hidden signals.
                                   Text describing unspoken issues, open topics,
                                   contradictions, and political signals.
        ba_recommendations:        Specific BA recommendations: what to clarify,
                                   with whom, whether a follow-up is needed.
        maturity_level:            Overall maturity level of the requirements.
        maturity_notes:            Comment on the maturity assessment.
        risks_json:                Risks the stakeholder raised in this session. Optional.
                                   Format: [{"description": "...", "stakeholder": "..."}]
                                   `stakeholder` defaults to stakeholder_role. A bare
                                   string is accepted and read as the description.
                                   Consumed by 6.3 `import_risks_from_context`.

    Returns:
        Путь к сохранённому файлу результатов выявления.
    """
    logger.info(f"4.2 Сохранение результатов выявления: проект='{project_name}', тип='{session_type}'")

    profile, error = parse_json_dict(
        stakeholder_profile_json, "stakeholder_profile_json",
        example='{"participation_type": "Decision maker", "influence": "High"}')
    if error:
        return error

    pains, error = parse_json_dict_list(
        pains_json, "pains_json",
        example='[{"title": "...", "description": "...", "business_impact": "..."}]')
    if error:
        return error

    reqs, error = parse_json_dict(
        requirements_json, "requirements_json",
        example='{"functional": ["FR-001: ..."], "non_functional": ["NFR-001: ..."]}')
    if error:
        return error

    risks, error = _parse_session_risks(risks_json, stakeholder_role)
    if error:
        return error

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

    risks_md = ("\n".join(f"- {r['description']} — *{r['stakeholder']}*" for r in risks)
                if risks else "- Не упоминались")

    content = f"""# Elicitation Results (Unconfirmed)

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

## 5. Риски, названные стейкхолдером

{risks_md}

---

## 6. BA Recommendations

{ba_recommendations}

---

## 7. Requirements Maturity Assessment

**Общий уровень:** {maturity_level}

{maturity_notes}
"""

    # Structured output for 6.3 import_risks_from_context. The Markdown below is for
    # people; this file is the machine contract, and 6.3 is its only consumer today.
    risks_saved = _record_session_risks(
        project_name, session_date, stakeholder_role, session_type, risks)

    # The session date stays in the name — it distinguishes sessions within a project.
    suffix = save_artifact(
        content,
        f"4_2_elicitation_results_{session_date.replace('.', '-')}",
        project_id=project_name,
    )
    # The Markdown prints the risks either way, so a silent persist failure would tell
    # the BA the session was recorded while 6.3 later finds nothing. Same reasoning as
    # the stakeholder registry a few lines down — the two writers must not disagree.
    if risks and not risks_saved:
        return (
            f"⚠️ Результаты выявления сохранены, но файл рисков для 6.3 записать НЕ "
            f"удалось — риски ниже есть только в отчёте, и "
            f"`import_risks_from_context` их не увидит.{suffix}"
        )
    return f"✅ Результаты выявления сохранены.{suffix}"


# ---------------------------------------------------------------------------
# 4.2.2 — Сохранить кросс-анализ нескольких сессий
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
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

    registry, error = parse_json_dict_list(
        requirements_registry_json, "requirements_registry_json",
        example='[{"id": "FR-001", "requirement": "...", "sources": ["..."], '
                '"priority": "High", "status": "Agreed"}]')
    if error:
        return error

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

    suffix = save_artifact(content, "4_2_cross_analysis", project_id=project_name)
    return f"✅ Cross-analysis saved.{suffix}"


# ---------------------------------------------------------------------------
# 4.2.3 — Сохранить анализ выявления в контексте Change Request
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
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

    artifacts, error = parse_json_dict_list(
        affected_artifacts_json, "affected_artifacts_json",
        example='[{"artifact": "FR-001", "type": "FR", "affected": true, '
                '"change_type": "Update"}]')
    if error:
        return error

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

    suffix = save_artifact(content, "4_2_cr_elicitation", project_id=project_name)
    return f"✅ CR analysis saved.{suffix}"


# ---------------------------------------------------------------------------
# 4.2.4 — Обновить живой реестр стейкхолдеров
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
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

    incoming, error = parse_json_dict_list(
        new_stakeholders_json, "new_stakeholders_json",
        example='[{"name": "Jane Doe", "role": "Head of Sales", "influence": "High"}]')
    if error:
        return error

    today = date.today().strftime("%d.%m.%Y")

    # -----------------------------------------------------------------------
    # Read the living registry (JSON source of truth), merge, write it back.
    # This is what makes it a living document: the latest artifact always holds
    # the FULL registry, not just the current session's slice.
    # The merge itself lives in common.py so 3.2 can seed the same registry
    # without Chapter 3 depending on Chapter 4.
    # -----------------------------------------------------------------------
    merge_result = update_stakeholder_registry_file(
        project_name, incoming, source=session_source)

    registry = merge_result["registry"]
    existing = registry["stakeholders"]
    added = merge_result["added"]
    updated = merge_result["updated"]
    dup_warnings = merge_result["dup_warnings"]

    # -----------------------------------------------------------------------
    # Render the .md report from the FULL registry.
    # -----------------------------------------------------------------------
    table_header = (
        "| Стейкхолдер | Роль | Подразделение | Как найден | Влияние | Интерес | "
        "Отношение | Статус охвата | Приоритет | Формат |\n"
        "| :--- | :--- | :--- | :--- | :---: | :---: | :--- | :--- | :---: | :--- |\n"
    )
    rows = []
    for s in existing:
        rows.append(
            f"| {s.get('name', '—')} | {s.get('role', '—')} | "
            f"{s.get('department', '—')} | {s.get('found_through', '—')} | "
            f"{s.get('influence', '—')} | {s.get('interest', '—')} | "
            f"{s.get('attitude', 'Неизвестно')} | {s.get('coverage_status', '—')} | "
            f"{s.get('priority', '—')} | {s.get('recommended_format', '—')} |"
        )

    # Changes made in this update — lets the BA see add vs. update at a glance.
    change_lines = [
        f"- **Added:** {len(added)}" + (f" ({', '.join(added)})" if added else ""),
        f"- **Updated:** {len(updated)}" + (f" ({', '.join(updated)})" if updated else ""),
    ]
    changes_block = "\n".join(change_lines)

    # Possible-duplicate warnings (soft, non-blocking).
    dup_block = ""
    if dup_warnings:
        dup_block = "\n## ⚠️ Возможные дубликаты\n\n"
        for new_name, existing_name in dup_warnings:
            dup_block += (
                f"- У **{new_name}** та же роль, что и у **{existing_name}**, уже записанного в реестре. "
                f"Возможно, это тот же человек, что и \"{existing_name}\", — проверьте.\n"
            )

    # Discovery chain (full registry).
    chain_lines = []
    for s in existing:
        source = s.get('found_through', 'Unknown')
        name = s.get('name', '—')
        role = s.get('role', '—')
        why = s.get('why_important', '')
        chain_lines.append(f"- **{name}** ({role}) ← через: {source}" + (f"\n  > {why}" if why else ""))

    # Not covered — separate action list (full registry).
    uncovered = [s for s in existing if s.get('coverage_status') == 'Not covered']
    urgent = [s for s in uncovered if s.get('priority') == 'Urgent']
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
**Обновлён:** {today}
**Источник обновления:** {session_source}
**Всего стейкхолдеров:** {len(existing)}

---

## Изменения в этом обновлении

{changes_block}
{dup_block}
---

## Полный реестр (актуальный)

{table_header}{chr(10).join(rows) if rows else "| — | — | — | — | — | — | — | — | — | — |"}

---

## Цепочка обнаружения

{chr(10).join(chain_lines) if chain_lines else "— Нет данных —"}

{uncovered_block}
---

> Этот файл обновляется после каждой сессии выявления.
> Полный реестр накапливается из всех обновлений.
"""

    suffix = save_artifact(content, "4_2_stakeholder_registry", project_id=project_name)
    # The JSON is the source of truth; the Markdown is a rendering of it. Reporting
    # success when the JSON did not persist would tell the BA their session was
    # recorded while the next session silently starts from the old registry.
    # 3.2 already surfaces this on its side — the two writers must not disagree.
    if not merge_result.get("saved"):
        return (
            f"⚠️ Реестр стейкхолдеров НЕ удалось сохранить на диск — отчёт ниже "
            f"сформирован, но изменения не записаны, и следующая сессия их не "
            f"увидит. Добавлено: {len(added)}, обновлено: {len(updated)}.{suffix}"
        )
    return (
        f"✅ Реестр стейкхолдеров обновлён. Добавлено: {len(added)}, обновлено: {len(updated)}. "
        f"Всего в реестре: {len(existing)}.{suffix}"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
