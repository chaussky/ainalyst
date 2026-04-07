"""
BABOK 6.1 — Analyze Current State
MCP-инструменты для анализа текущего состояния организации.

Инструменты:
  - scope_current_state              — скоуп анализа: тип инициативы, глубина, элементы
  - capture_current_state_element    — зафиксировать один из 8 элементов текущего состояния
  - run_root_cause_analysis          — провести RCA и сохранить нормализованный результат
  - define_business_needs            — сформулировать бизнес-потребность + регистрация в 5.1
  - check_current_state_completeness — проверить полноту анализа (coverage check)
  - save_current_state               — финализировать + Markdown отчёт + проброс в 7.3

Хранение:
  - {project}_current_state_scope.json   — скоуп анализа (контракт)
  - {project}_current_state.json         — данные по 8 элементам + RCA
  - {project}_business_needs.json        — реестр бизнес-потребностей
  - {project}_current_state_analysis.md  — читаемый отчёт (через save_artifact)

Интеграция:
  Вход: результаты 4.3 (session_ids для импорта черновика)
  Выход: BN-узлы в репозитории 5.1, данные для 7.3 set_business_context

ADR-054: business_need как тип узла в репозитории 5.1
ADR-055: backward compatibility set_business_context (7.3)
ADR-056: нормализованный выход RCA независимо от техники
ADR-057: импорт из 4.3 через session_ids
ADR-058: scope_current_state как явный contract
ADR-059: capture_current_state_element — итеративный паттерн

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date, datetime
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import save_artifact, logger, DATA_DIR

mcp = FastMCP("BABOK_CurrentState")

SCOPE_FILENAME = "current_state_scope.json"
STATE_FILENAME = "current_state.json"
NEEDS_FILENAME = "business_needs.json"
REPO_FILENAME = "traceability_repo.json"

VALID_ELEMENTS = [
    "business_needs", "org_structure", "capabilities",
    "technology", "policies", "architecture", "assets", "external"
]

ELEMENT_LABELS = {
    "business_needs": "Бизнес-потребности",
    "org_structure": "Организационная структура и культура",
    "capabilities": "Возможности и процессы",
    "technology": "Технологии и инфраструктура",
    "policies": "Политики",
    "architecture": "Бизнес-архитектура",
    "assets": "Внутренние активы",
    "external": "Внешние воздействия",
}

DEFAULT_ELEMENTS_BY_TYPE = {
    "process_improvement": ["business_needs", "capabilities", "technology", "policies"],
    "new_system": ["business_needs", "capabilities", "technology", "architecture"],
    "regulatory": ["business_needs", "policies", "technology", "external"],
    "cost_reduction": ["business_needs", "capabilities", "assets", "external"],
    "market_opportunity": VALID_ELEMENTS,
    "other": ["business_needs", "capabilities", "technology"],
}


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def _safe(project_id: str) -> str:
    return project_id.lower().replace(" ", "_")


def _scope_path(project_id: str) -> str:
    return os.path.join(DATA_DIR, f"{_safe(project_id)}_{SCOPE_FILENAME}")


def _state_path(project_id: str) -> str:
    return os.path.join(DATA_DIR, f"{_safe(project_id)}_{STATE_FILENAME}")


def _needs_path(project_id: str) -> str:
    return os.path.join(DATA_DIR, f"{_safe(project_id)}_{NEEDS_FILENAME}")


def _repo_path(project_id: str) -> str:
    return os.path.join(DATA_DIR, f"{_safe(project_id)}_{REPO_FILENAME}")


def _load_scope(project_id: str) -> Optional[dict]:
    path = _scope_path(project_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_scope(data: dict) -> str:
    path = _scope_path(data["project_id"])
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Скоуп анализа сохранён: {path}")
    return path


def _load_state(project_id: str) -> dict:
    path = _state_path(project_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "project_id": project_id,
        "scope_ref": f"{_safe(project_id)}_{SCOPE_FILENAME}",
        "elements": {},
        "root_causes": [],
        "created": str(date.today()),
        "updated": str(date.today()),
    }


def _save_state(data: dict) -> str:
    path = _state_path(data["project_id"])
    os.makedirs(DATA_DIR, exist_ok=True)
    data["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Данные текущего состояния сохранены: {path}")
    return path


def _load_needs(project_id: str) -> dict:
    path = _needs_path(project_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "project_id": project_id,
        "needs": [],
        "created": str(date.today()),
        "updated": str(date.today()),
    }


def _save_needs(data: dict) -> str:
    path = _needs_path(data["project_id"])
    os.makedirs(DATA_DIR, exist_ok=True)
    data["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Бизнес-потребности сохранены: {path}")
    return path


def _load_repo(project_id: str) -> Optional[dict]:
    path = _repo_path(project_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_repo(repo: dict) -> None:
    project_id = repo["project"]
    path = _repo_path(project_id)
    os.makedirs(DATA_DIR, exist_ok=True)
    repo["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)
    logger.info(f"Репозиторий трассировки обновлён из 6.1: {path}")


def _next_need_id(needs_data: dict) -> str:
    existing = [n["id"] for n in needs_data["needs"] if n["id"].startswith("BN-")]
    if not existing:
        return "BN-001"
    nums = [int(n.split("-")[1]) for n in existing if n.split("-")[1].isdigit()]
    return f"BN-{(max(nums) + 1):03d}" if nums else "BN-001"


def _next_rca_id(state: dict) -> str:
    existing = [r["rca_id"] for r in state["root_causes"] if r["rca_id"].startswith("RCA-")]
    if not existing:
        return "RCA-001"
    nums = [int(r.split("-")[1]) for r in existing if r.split("-")[1].isdigit()]
    return f"RCA-{(max(nums) + 1):03d}" if nums else "RCA-001"


# ---------------------------------------------------------------------------
# 6.1.1 — Скоупинг анализа текущего состояния
# ---------------------------------------------------------------------------

@mcp.tool()
def scope_current_state(
    project_id: str,
    initiative_type: Literal[
        "process_improvement", "new_system", "regulatory",
        "cost_reduction", "market_opportunity", "other"
    ],
    analysis_depth: Literal["light", "standard", "deep"],
    known_problems: str,
    elements_in_scope: str = "",
    session_ids: str = "",
) -> str:
    """
    BABOK 6.1 — Первый шаг: скоупинг анализа текущего состояния.
    Фиксирует явный контракт между BA и системой (ADR-058).
    Вызывается один раз в начале работы над 6.1.

    Args:
        project_id:        Идентификатор проекта.
        initiative_type:   Тип инициативы:
                           - process_improvement — улучшение процессов
                           - new_system          — внедрение новой системы
                           - regulatory          — выполнение регуляторных требований
                           - cost_reduction      — снижение затрат
                           - market_opportunity  — рыночная возможность
                           - other               — другое
        analysis_depth:    Глубина анализа:
                           - light    — 3–4 элемента, быстрый срез
                           - standard — 5–6 элементов, большинство проектов
                           - deep     — все 8 элементов, стратегические инициативы
        known_problems:    Краткое описание проблем или возможностей, инициировавших работу.
        elements_in_scope: Опционально — переопределить список элементов вручную.
                           JSON-список ключей, например:
                           '["business_needs","capabilities","technology"]'
                           Допустимые ключи: business_needs | org_structure | capabilities |
                           technology | policies | architecture | assets | external
        session_ids:       Опционально — список session_id из 4.3 для импорта черновика.
                           JSON-список строк: '["session_001","session_002"]'
                           Система пометит элементы как черновик для последующего уточнения.

    Returns:
        Подтверждение скоупа + рекомендованные элементы.
    """
    logger.info(f"scope_current_state: {project_id}, type={initiative_type}, depth={analysis_depth}")

    # Определяем элементы в скоупе
    if elements_in_scope.strip():
        try:
            custom_elements = json.loads(elements_in_scope)
            invalid = [e for e in custom_elements if e not in VALID_ELEMENTS]
            if invalid:
                return (
                    f"❌ Неизвестные элементы: {invalid}\n"
                    f"Допустимые: {VALID_ELEMENTS}"
                )
            chosen_elements = custom_elements
            elements_source = "указаны вручную"
        except json.JSONDecodeError as e:
            return f"❌ Ошибка парсинга elements_in_scope: {e}"
    else:
        # Автовыбор по типу и глубине
        base_elements = DEFAULT_ELEMENTS_BY_TYPE.get(initiative_type, ["business_needs", "capabilities"])
        if analysis_depth == "deep":
            chosen_elements = VALID_ELEMENTS
        elif analysis_depth == "light":
            chosen_elements = base_elements[:3]
        else:  # standard
            chosen_elements = base_elements
        elements_source = f"рекомендовано для {initiative_type}/{analysis_depth}"

    # Парсим session_ids
    imported_sessions = []
    if session_ids.strip():
        try:
            imported_sessions = json.loads(session_ids)
        except json.JSONDecodeError:
            return f"❌ Ошибка парсинга session_ids: ожидается JSON-список строк"

    # Проверяем существующий скоуп
    existing = _load_scope(project_id)
    is_update = existing is not None

    scope_data = {
        "project_id": project_id,
        "initiative_type": initiative_type,
        "analysis_depth": analysis_depth,
        "known_problems": known_problems,
        "elements_in_scope": chosen_elements,
        "session_ids_imported": imported_sessions,
        "created": existing["created"] if existing else str(date.today()),
        "updated": str(date.today()),
    }

    path = _save_scope(scope_data)

    # Если есть session_ids — инициализируем черновые записи в state
    if imported_sessions:
        state = _load_state(project_id)
        for elem in chosen_elements:
            if elem not in state["elements"]:
                state["elements"][elem] = {
                    "description": "",
                    "pain_points": [],
                    "metrics": {},
                    "sources": ["elicitation"],
                    "notes": f"Черновик: данные из сессий {imported_sessions}. Уточнить через capture_current_state_element.",
                    "draft": True,
                    "last_updated": str(date.today()),
                }
        _save_state(state)

    # Формируем ответ
    depth_labels = {
        "light": "Лёгкий (3–4 элемента, быстрый срез)",
        "standard": "Стандартный (5–6 элементов)",
        "deep": "Глубокий (все 8 элементов)",
    }
    type_labels = {
        "process_improvement": "Улучшение процессов",
        "new_system": "Внедрение новой системы",
        "regulatory": "Регуляторные требования",
        "cost_reduction": "Снижение затрат",
        "market_opportunity": "Рыночная возможность",
        "other": "Другое",
    }

    lines = [
        f"{'⚠️ Скоуп ОБНОВЛЁН' if is_update else '✅ Скоуп анализа определён'} — **{project_id}**",
        "",
        f"**Тип инициативы:** {type_labels.get(initiative_type, initiative_type)}",
        f"**Глубина анализа:** {depth_labels.get(analysis_depth, analysis_depth)}",
        f"**Дата:** {date.today()}",
        "",
        "## Описание проблемы / возможности",
        "",
        known_problems,
        "",
        f"## Элементы в скоупе ({len(chosen_elements)} из 8) — {elements_source}",
        "",
    ]

    for i, elem in enumerate(chosen_elements, 1):
        label = ELEMENT_LABELS.get(elem, elem)
        lines.append(f"{i}. **{elem}** — {label}")

    not_in_scope = [e for e in VALID_ELEMENTS if e not in chosen_elements]
    if not_in_scope:
        lines += ["", "### Элементы вне скоупа (не анализируем):"]
        for elem in not_in_scope:
            lines.append(f"- ~~{elem}~~ — {ELEMENT_LABELS.get(elem, elem)}")

    if imported_sessions:
        lines += [
            "",
            f"## Импорт из 4.3",
            "",
            f"Сессии для импорта: {imported_sessions}",
            f"Для каждого элемента создан черновик. Уточните данные через `capture_current_state_element`.",
        ]

    lines += [
        "",
        "---",
        "",
        "## Следующие шаги",
        "",
        "1. `capture_current_state_element` — заполнить каждый элемент из скоупа",
        "2. `run_root_cause_analysis` — провести RCA по ключевым проблемам",
        "3. `define_business_needs` — сформулировать бизнес-потребности",
        "4. `check_current_state_completeness` — проверить полноту",
        "5. `save_current_state` — финализировать анализ",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.1.2 — Итеративный сбор данных по элементам
# ---------------------------------------------------------------------------

@mcp.tool()
def capture_current_state_element(
    project_id: str,
    element: Literal[
        "business_needs", "org_structure", "capabilities",
        "technology", "policies", "architecture", "assets", "external"
    ],
    description: str,
    pain_points: str = "[]",
    metrics: str = "{}",
    sources: str = '["elicitation"]',
    notes: str = "",
) -> str:
    """
    BABOK 6.1 — Зафиксировать один элемент текущего состояния (ADR-059).
    Итеративный паттерн: вызывается по одному разу на каждый элемент, можно в разные сессии.
    Повторный вызов обновляет запись (идемпотентен по element).

    Args:
        project_id:   Идентификатор проекта.
        element:      Один из 8 элементов:
                      business_needs | org_structure | capabilities | technology |
                      policies | architecture | assets | external
        description:  Содержательное описание элемента (основное поле).
        pain_points:  Список проблем и симптомов в этом элементе.
                      JSON-список строк: '["Процесс медленный","Данные теряются"]'
        metrics:      Текущие измеримые показатели.
                      JSON-объект: '{"processing_time": "8 hours", "error_rate": "12%"}'
        sources:      Откуда данные: JSON-список из допустимых значений.
                      Допустимые: elicitation | document | observation | interview | other
        notes:        Свободные заметки (контекст, вопросы для уточнения).

    Returns:
        Подтверждение записи + статус по всем скоупированным элементам.
    """
    logger.info(f"capture_current_state_element: {project_id}, element={element}")

    # Валидируем JSON-поля
    try:
        pain_list = json.loads(pain_points) if pain_points.strip() else []
        if not isinstance(pain_list, list):
            return "❌ pain_points должен быть JSON-списком строк: '[\"проблема1\",\"проблема2\"]'"
    except json.JSONDecodeError as e:
        return f"❌ Ошибка парсинга pain_points: {e}"

    try:
        metrics_dict = json.loads(metrics) if metrics.strip() else {}
        if not isinstance(metrics_dict, dict):
            return "❌ metrics должен быть JSON-объектом: '{\"показатель\": \"значение\"}'"
    except json.JSONDecodeError as e:
        return f"❌ Ошибка парсинга metrics: {e}"

    try:
        sources_list = json.loads(sources) if sources.strip() else ["elicitation"]
        if not isinstance(sources_list, list):
            return "❌ sources должен быть JSON-списком"
    except json.JSONDecodeError as e:
        return f"❌ Ошибка парсинга sources: {e}"

    if not description.strip():
        return "❌ description не может быть пустым — опиши текущее состояние элемента."

    # Проверяем скоуп
    scope = _load_scope(project_id)
    scope_warning = ""
    if scope and element not in scope.get("elements_in_scope", []):
        scope_warning = f"\n⚠️ Элемент `{element}` не входит в текущий скоуп. Добавить в скоуп можно через повторный вызов `scope_current_state`."

    # Загружаем и обновляем state
    state = _load_state(project_id)
    is_update = element in state["elements"] and not state["elements"][element].get("draft", False)
    was_draft = element in state["elements"] and state["elements"].get(element, {}).get("draft", False)

    state["elements"][element] = {
        "description": description,
        "pain_points": pain_list,
        "metrics": metrics_dict,
        "sources": sources_list,
        "notes": notes,
        "draft": False,
        "last_updated": str(date.today()),
    }

    _save_state(state)

    label = ELEMENT_LABELS.get(element, element)
    action = "ОБНОВЛЁН" if is_update else ("сохранён (из черновика)" if was_draft else "сохранён")

    lines = [
        f"✅ Элемент **{label}** (`{element}`) {action}",
        "",
        f"**Описание:** {description[:200]}{'...' if len(description) > 200 else ''}",
    ]

    if pain_list:
        lines += ["", "**Проблемы и симптомы:**"]
        for p in pain_list:
            lines.append(f"- {p}")

    if metrics_dict:
        lines += ["", "**Метрики:**"]
        for k, v in metrics_dict.items():
            lines.append(f"- {k}: {v}")

    lines += ["", f"**Источники:** {', '.join(sources_list)}"]

    if scope_warning:
        lines.append(scope_warning)

    # Прогресс по скоупу
    if scope:
        elements_in_scope = scope.get("elements_in_scope", [])
        filled = [e for e in elements_in_scope if e in state["elements"] and not state["elements"][e].get("draft", True)]
        remaining = [e for e in elements_in_scope if e not in state["elements"] or state["elements"][e].get("draft", True)]

        lines += [
            "",
            f"## Прогресс анализа: {len(filled)}/{len(elements_in_scope)} элементов",
            "",
        ]
        for e in elements_in_scope:
            elem_label = ELEMENT_LABELS.get(e, e)
            if e in filled:
                status = "✅"
            elif e in state["elements"] and state["elements"][e].get("draft"):
                status = "📝 (черновик)"
            else:
                status = "⬜"
            lines.append(f"{status} {elem_label}")

        if remaining:
            lines += ["", f"**Следующий элемент:** `{remaining[0]}`"]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.1.3 — Root Cause Analysis
# ---------------------------------------------------------------------------

@mcp.tool()
def run_root_cause_analysis(
    project_id: str,
    problem_statement: str,
    technique_used: Literal["fishbone", "five_whys", "problem_tree"],
    root_cause: str,
    contributing_factors: str = "[]",
    evidence: str = "[]",
    affected_elements: str = "[]",
) -> str:
    """
    BABOK 6.1 — Провести RCA и сохранить нормализованный результат (ADR-056).
    Нормализованный формат: независимо от техники выход один и тот же.
    Техника — инструмент мышления. MCP сохраняет результат.

    Args:
        project_id:          Идентификатор проекта.
        problem_statement:   Чёткая, измеримая формулировка проблемы.
                             Пример: "Время обработки заявок выросло с 2 до 8 часов за 6 месяцев"
        technique_used:      Использованная техника RCA:
                             - fishbone   — диаграмма Исикавы по категориям
                             - five_whys  — 5 Почему, линейная цепочка
                             - problem_tree — дерево проблем (причины + следствия)
        root_cause:          Одна главная корневая причина (не симптом!).
                             Пример: "Регламент согласования 2012 года содержит 3 лишних уровня"
        contributing_factors: Факторы, усиливающие корневую причину.
                             JSON-список строк:
                             '["Нет автоматизации уведомлений","Менеджеры дублируют проверки"]'
        evidence:            Данные, подтверждающие причинно-следственную связь.
                             JSON-список строк:
                             '["5.5 ч из 8 уходит на согласование (данные системы Q1 2025)"]'
        affected_elements:   Какие из 8 элементов текущего состояния затронуты.
                             JSON-список ключей: '["capabilities","policies","technology"]'

    Returns:
        Карточка RCA с ID + рекомендации по связыванию с бизнес-потребностями.
    """
    logger.info(f"run_root_cause_analysis: {project_id}, technique={technique_used}")

    if not problem_statement.strip():
        return "❌ problem_statement не может быть пустым."
    if not root_cause.strip():
        return "❌ root_cause не может быть пустым."

    try:
        factors = json.loads(contributing_factors) if contributing_factors.strip() else []
    except json.JSONDecodeError as e:
        return f"❌ Ошибка парсинга contributing_factors: {e}"

    try:
        evidence_list = json.loads(evidence) if evidence.strip() else []
    except json.JSONDecodeError as e:
        return f"❌ Ошибка парсинга evidence: {e}"

    try:
        affected = json.loads(affected_elements) if affected_elements.strip() else []
        invalid_affected = [e for e in affected if e not in VALID_ELEMENTS]
        if invalid_affected:
            return f"❌ Неизвестные элементы в affected_elements: {invalid_affected}"
    except json.JSONDecodeError as e:
        return f"❌ Ошибка парсинга affected_elements: {e}"

    state = _load_state(project_id)
    rca_id = _next_rca_id(state)

    rca_record = {
        "rca_id": rca_id,
        "problem_statement": problem_statement,
        "technique_used": technique_used,
        "root_cause": root_cause,
        "contributing_factors": factors,
        "evidence": evidence_list,
        "affected_elements": affected,
        "created": datetime.now().isoformat(timespec="seconds"),
    }

    state["root_causes"].append(rca_record)
    _save_state(state)

    technique_labels = {
        "fishbone": "Fishbone / Диаграмма Исикавы",
        "five_whys": "5 Почему",
        "problem_tree": "Дерево проблем",
    }

    lines = [
        f"✅ RCA зафиксирован: **{rca_id}**",
        "",
        f"**Техника:** {technique_labels.get(technique_used, technique_used)}",
        f"**Дата:** {date.today()}",
        "",
        "## Проблема",
        "",
        problem_statement,
        "",
        "## Корневая причина",
        "",
        f"🎯 {root_cause}",
    ]

    if factors:
        lines += ["", "## Сопутствующие факторы", ""]
        for f in factors:
            lines.append(f"- {f}")

    if evidence_list:
        lines += ["", "## Доказательства", ""]
        for ev in evidence_list:
            lines.append(f"- {ev}")

    if affected:
        lines += ["", "## Затронутые элементы текущего состояния", ""]
        for elem in affected:
            lines.append(f"- `{elem}` — {ELEMENT_LABELS.get(elem, elem)}")

    total_rca = len(state["root_causes"])
    lines += [
        "",
        "---",
        "",
        f"Всего RCA в проекте: **{total_rca}**",
        "",
        f"**Следующий шаг:** зафиксировать бизнес-потребность через `define_business_needs`",
        f"и связать с этим RCA через параметр `root_cause_ids: [\"{rca_id}\"]`",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.1.4 — Формулировка бизнес-потребностей
# ---------------------------------------------------------------------------

@mcp.tool()
def define_business_needs(
    project_id: str,
    need_title: str,
    description: str,
    need_type: Literal["problem", "opportunity", "regulatory", "strategic"],
    priority: Literal["Critical", "High", "Medium", "Low"],
    source: str,
    cost_of_inaction: str = "",
    expected_benefits: str = "",
    root_cause_ids: str = "[]",
    register_in_traceability: bool = True,
) -> str:
    """
    BABOK 6.1 — Сформулировать бизнес-потребность.
    Опционально регистрирует узел business_need в репозитории 5.1 (ADR-054).

    Args:
        project_id:              Идентификатор проекта.
        need_title:              Краткий заголовок потребности (до 100 символов).
        description:             Полное описание потребности — чёткая, измеримая формулировка.
        need_type:               Тип потребности:
                                 - problem      — существующая проблема, которую нужно решить
                                 - opportunity  — рыночная или операционная возможность
                                 - regulatory   — требование регулятора / законодательства
                                 - strategic    — стратегическая инициатива
        priority:                Приоритет: Critical | High | Medium | Low
        source:                  Источник потребности (стейкхолдер, документ, анализ).
                                 Пример: "Директор по операциям, интервью 15.03.2025"
        cost_of_inaction:        Стоимость бездействия — что произойдёт если не менять.
                                 Пример: "Потеря 18% клиентов в год, ~2.4М руб."
        expected_benefits:       Ожидаемые выгоды от удовлетворения потребности.
        root_cause_ids:          Список ID RCA-артефактов, объясняющих эту потребность.
                                 JSON-список: '["RCA-001","RCA-002"]'
        register_in_traceability: Если True — создать узел business_need в репозитории 5.1.
                                 Default: True. Отключить если репозиторий 5.1 ещё не создан.

    Returns:
        Карточка бизнес-потребности с ID + подтверждение регистрации в 5.1.
    """
    logger.info(f"define_business_needs: {project_id}, title='{need_title[:50]}'")

    if not need_title.strip():
        return "❌ need_title не может быть пустым."
    if not description.strip():
        return "❌ description не может быть пустым."
    if not source.strip():
        return "❌ source не может быть пустым — укажи источник потребности."

    try:
        rca_ids = json.loads(root_cause_ids) if root_cause_ids.strip() else []
    except json.JSONDecodeError as e:
        return f"❌ Ошибка парсинга root_cause_ids: {e}"

    # Валидируем RCA IDs
    if rca_ids:
        state = _load_state(project_id)
        existing_rca = {r["rca_id"] for r in state["root_causes"]}
        unknown_rca = [r for r in rca_ids if r not in existing_rca]
        if unknown_rca:
            return (
                f"⚠️ RCA не найдены: {unknown_rca}\n"
                f"Существующие: {list(existing_rca)}\n"
                f"Создайте RCA через `run_root_cause_analysis` или уберите неизвестные ID."
            )

    needs_data = _load_needs(project_id)
    need_id = _next_need_id(needs_data)

    need_record = {
        "id": need_id,
        "need_title": need_title,
        "description": description,
        "need_type": need_type,
        "priority": priority,
        "source": source,
        "cost_of_inaction": cost_of_inaction,
        "expected_benefits": expected_benefits,
        "root_cause_ids": rca_ids,
        "created": str(date.today()),
    }
    needs_data["needs"].append(need_record)
    _save_needs(needs_data)

    # Регистрация в репозитории 5.1 (ADR-054)
    traceability_status = ""
    if register_in_traceability:
        repo = _load_repo(project_id)
        if repo is None:
            traceability_status = (
                "\n\n⚠️ Репозиторий трассировки 5.1 не найден.\n"
                "Создайте его через `init_traceability_repo` (5.1), "
                f"затем узел `{need_id}` типа `business_need` будет добавлен автоматически.\n"
                "Для ручного добавления используйте `init_traceability_repo` с этим требованием в списке."
            )
        else:
            existing_ids = {r["id"] for r in repo["requirements"]}
            if need_id not in existing_ids:
                repo["requirements"].append({
                    "id": need_id,
                    "type": "business_need",
                    "title": need_title,
                    "version": "1.0",
                    "status": "confirmed",
                    "source_artifact": f"6.1/{_safe(project_id)}_business_needs.json",
                    "added": str(date.today()),
                })
                repo["history"].append({
                    "action": "node_added",
                    "id": need_id,
                    "type": "business_need",
                    "source": "6.1 define_business_needs",
                    "date": str(date.today()),
                })
                _save_repo(repo)
                traceability_status = f"\n\n✅ Узел `{need_id}` (business_need) зарегистрирован в репозитории 5.1."
            else:
                traceability_status = f"\n\nℹ️ Узел `{need_id}` уже существует в репозитории 5.1."

    type_labels = {
        "problem": "Проблема",
        "opportunity": "Возможность",
        "regulatory": "Регуляторное требование",
        "strategic": "Стратегическая инициатива",
    }

    priority_icons = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}

    lines = [
        f"✅ Бизнес-потребность зафиксирована: **{need_id}**",
        "",
        f"**{priority_icons.get(priority, '')} {need_title}**",
        "",
        f"**Тип:** {type_labels.get(need_type, need_type)}  ",
        f"**Приоритет:** {priority}  ",
        f"**Источник:** {source}  ",
        f"**Дата:** {date.today()}",
        "",
        "## Описание",
        "",
        description,
    ]

    if cost_of_inaction:
        lines += ["", "## Стоимость бездействия", "", cost_of_inaction]

    if expected_benefits:
        lines += ["", "## Ожидаемые выгоды", "", expected_benefits]

    if rca_ids:
        lines += ["", f"**Связанные RCA:** {', '.join(rca_ids)}"]

    total_needs = len(needs_data["needs"])
    lines += [
        "",
        "---",
        "",
        f"Всего бизнес-потребностей в проекте: **{total_needs}**",
        traceability_status,
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.1.5 — Проверка полноты анализа
# ---------------------------------------------------------------------------

@mcp.tool()
def check_current_state_completeness(
    project_id: str,
) -> str:
    """
    BABOK 6.1 — Проверить полноту анализа текущего состояния перед финализацией.
    Не блокирует — информирует и предупреждает.

    Что проверяет:
    - Все ли скоупированные элементы заполнены (не черновики)?
    - Есть ли хотя бы один RCA?
    - Есть ли хотя бы одна бизнес-потребность?
    - Связаны ли бизнес-потребности с RCA?

    Args:
        project_id: Идентификатор проекта.

    Returns:
        Coverage report с рекомендациями и вердиктом о готовности.
    """
    logger.info(f"check_current_state_completeness: {project_id}")

    scope = _load_scope(project_id)
    state = _load_state(project_id)
    needs_data = _load_needs(project_id)

    if not scope:
        return (
            "⚠️ Скоуп анализа не определён.\n"
            "Начните с `scope_current_state` — это обязательный первый шаг."
        )

    elements_in_scope = scope.get("elements_in_scope", [])
    elements_data = state.get("elements", {})
    rca_list = state.get("root_causes", [])
    needs_list = needs_data.get("needs", [])

    # Проверка элементов
    filled_elements = []
    draft_elements = []
    missing_elements = []

    for elem in elements_in_scope:
        if elem in elements_data and not elements_data[elem].get("draft", True):
            filled_elements.append(elem)
        elif elem in elements_data and elements_data[elem].get("draft", True):
            draft_elements.append(elem)
        else:
            missing_elements.append(elem)

    # Проверка RCA
    has_rca = len(rca_list) > 0

    # Проверка бизнес-потребностей
    has_needs = len(needs_list) > 0

    # Проверка связи BN → RCA
    needs_with_rca = [n for n in needs_list if n.get("root_cause_ids")]
    needs_without_rca = [n for n in needs_list if not n.get("root_cause_ids")]

    # Вердикт
    warnings = []
    if missing_elements:
        warnings.append(f"Незаполнены {len(missing_elements)} элементов из скоупа")
    if draft_elements:
        warnings.append(f"{len(draft_elements)} элементов в черновике — нужно уточнить")
    if not has_rca:
        warnings.append("Нет ни одного RCA — причины проблем не выявлены")
    if not has_needs:
        warnings.append("Нет ни одной бизнес-потребности — результат анализа не сформулирован")
    if needs_without_rca:
        warnings.append(f"{len(needs_without_rca)} бизнес-потребностей не связаны с RCA")

    ready = len(warnings) == 0

    # Процент готовности
    total_checks = len(elements_in_scope) + 2  # элементы + RCA + потребности
    passed_checks = len(filled_elements) + (1 if has_rca else 0) + (1 if has_needs else 0)
    readiness_pct = round(passed_checks / total_checks * 100) if total_checks else 0

    lines = [
        f"# {'✅ Анализ готов к финализации' if ready else '⚠️ Анализ ещё не готов'}",
        "",
        f"**Проект:** {project_id}  ",
        f"**Готовность:** {readiness_pct}%  ",
        f"**Дата:** {date.today()}",
        "",
        "## Элементы текущего состояния",
        "",
        f"| Статус | Количество |",
        f"|--------|------------|",
        f"| ✅ Заполнены | {len(filled_elements)} |",
        f"| 📝 Черновики (нужно уточнить) | {len(draft_elements)} |",
        f"| ⬜ Не заполнены | {len(missing_elements)} |",
        f"| **Итого в скоупе** | **{len(elements_in_scope)}** |",
        "",
    ]

    if missing_elements:
        lines += ["### Незаполненные элементы:"]
        for e in missing_elements:
            lines.append(f"- ⬜ `{e}` — {ELEMENT_LABELS.get(e, e)}")
        lines.append("")

    if draft_elements:
        lines += ["### Черновики (уточнить через capture_current_state_element):"]
        for e in draft_elements:
            lines.append(f"- 📝 `{e}` — {ELEMENT_LABELS.get(e, e)}")
        lines.append("")

    lines += [
        "## Root Cause Analysis",
        "",
        f"{'✅' if has_rca else '❌'} RCA проведён: {len(rca_list)} {'анализ' if len(rca_list) == 1 else 'анализов'}",
        "",
        "## Бизнес-потребности",
        "",
        f"{'✅' if has_needs else '❌'} Бизнес-потребности: {len(needs_list)} {'потребность' if len(needs_list) == 1 else 'потребностей'}",
    ]

    if needs_list:
        lines += [""]
        for n in needs_list:
            rca_linked = "✅" if n.get("root_cause_ids") else "⚠️ без RCA"
            lines.append(f"- `{n['id']}` {n['need_title']} — {rca_linked}")

    if warnings:
        lines += ["", "## ⚠️ Предупреждения", ""]
        for w in warnings:
            lines.append(f"- {w}")
        lines += [
            "",
            "> Это предупреждения, не блокировки.",
            "> Вы можете продолжить через `save_current_state`, но рекомендуется устранить пробелы.",
        ]
    else:
        lines += [
            "",
            "---",
            "",
            "✅ Все проверки пройдены. Анализ готов к финализации.",
            "",
            "**Следующий шаг:** `save_current_state` — создать финальный отчёт.",
        ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.1.6 — Финализация и создание отчёта
# ---------------------------------------------------------------------------

@mcp.tool()
def save_current_state(
    project_id: str,
    project_title: str,
    push_to_business_context: bool = False,
    analyst_notes: str = "",
) -> str:
    """
    BABOK 6.1 — Финализировать анализ текущего состояния.
    Создаёт читаемый Markdown-отчёт. Опционально передаёт данные в 7.3 (ADR-055).

    Args:
        project_id:              Идентификатор проекта.
        project_title:           Читаемое название проекта для заголовка отчёта.
        push_to_business_context: Если True — автоматически вызывает set_business_context (7.3)
                                 с предзаполненными данными из 6.1 (ADR-055).
                                 Default: False — BA сам вызовет 7.3 когда нужно.
        analyst_notes:           Заключительные комментарии аналитика для отчёта.

    Returns:
        Подтверждение сохранения + ссылки на артефакты.
    """
    logger.info(f"save_current_state: {project_id}")

    scope = _load_scope(project_id)
    state = _load_state(project_id)
    needs_data = _load_needs(project_id)

    if not scope:
        return (
            "⚠️ Скоуп анализа не найден. Начните с `scope_current_state`."
        )

    elements_in_scope = scope.get("elements_in_scope", [])
    elements_data = state.get("elements", {})
    rca_list = state.get("root_causes", [])
    needs_list = needs_data.get("needs", [])

    # Предупреждения о черновиках
    draft_warnings = []
    for elem in elements_in_scope:
        if elem in elements_data and elements_data[elem].get("draft"):
            draft_warnings.append(elem)

    type_labels = {
        "process_improvement": "Улучшение процессов",
        "new_system": "Внедрение новой системы",
        "regulatory": "Регуляторные требования",
        "cost_reduction": "Снижение затрат",
        "market_opportunity": "Рыночная возможность",
        "other": "Другое",
    }
    depth_labels = {
        "light": "Лёгкий",
        "standard": "Стандартный",
        "deep": "Глубокий",
    }
    technique_labels = {
        "fishbone": "Fishbone / Исикава",
        "five_whys": "5 Почему",
        "problem_tree": "Дерево проблем",
    }
    priority_icons = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}
    need_type_labels = {
        "problem": "Проблема",
        "opportunity": "Возможность",
        "regulatory": "Регуляторное требование",
        "strategic": "Стратегическая инициатива",
    }

    # Строим Markdown-отчёт
    report_lines = [
        f"<!-- BABOK 6.1 — Current State Analysis | Проект: {project_id} | {date.today()} -->",
        "",
        f"# Анализ текущего состояния: {project_title}",
        "",
        f"**Проект:** {project_id}  ",
        f"**Тип инициативы:** {type_labels.get(scope.get('initiative_type', ''), scope.get('initiative_type', ''))}  ",
        f"**Глубина анализа:** {depth_labels.get(scope.get('analysis_depth', ''), scope.get('analysis_depth', ''))}  ",
        f"**Дата:** {date.today()}",
        "",
        "## Контекст и известные проблемы",
        "",
        scope.get("known_problems", "—"),
        "",
        "---",
        "",
        "## Текущее состояние: анализ по элементам",
        "",
    ]

    for elem in elements_in_scope:
        label = ELEMENT_LABELS.get(elem, elem)
        report_lines.append(f"### {label}")
        report_lines.append("")

        if elem in elements_data:
            elem_data = elements_data[elem]
            draft_mark = " *(черновик)*" if elem_data.get("draft") else ""
            report_lines.append(elem_data.get("description", "—") + draft_mark)

            if elem_data.get("pain_points"):
                report_lines += ["", "**Проблемы и симптомы:**"]
                for p in elem_data["pain_points"]:
                    report_lines.append(f"- {p}")

            if elem_data.get("metrics"):
                report_lines += ["", "**Метрики текущего состояния:**"]
                for k, v in elem_data["metrics"].items():
                    report_lines.append(f"- {k}: {v}")

            if elem_data.get("notes"):
                report_lines += ["", f"*Примечания: {elem_data['notes']}*"]
        else:
            report_lines.append("*Элемент не заполнен*")

        report_lines.append("")

    # RCA секция
    if rca_list:
        report_lines += [
            "---",
            "",
            "## Root Cause Analysis",
            "",
        ]
        for rca in rca_list:
            report_lines += [
                f"### {rca['rca_id']} — {technique_labels.get(rca['technique_used'], rca['technique_used'])}",
                "",
                f"**Проблема:** {rca['problem_statement']}",
                "",
                f"**Корневая причина:** {rca['root_cause']}",
                "",
            ]
            if rca.get("contributing_factors"):
                report_lines += ["**Сопутствующие факторы:**"]
                for f in rca["contributing_factors"]:
                    report_lines.append(f"- {f}")
                report_lines.append("")
            if rca.get("evidence"):
                report_lines += ["**Доказательства:**"]
                for ev in rca["evidence"]:
                    report_lines.append(f"- {ev}")
                report_lines.append("")

    # Бизнес-потребности
    if needs_list:
        report_lines += [
            "---",
            "",
            "## Бизнес-потребности",
            "",
        ]
        for need in needs_list:
            icon = priority_icons.get(need.get("priority", ""), "")
            report_lines += [
                f"### {need['id']} — {icon} {need['need_title']}",
                "",
                f"**Тип:** {need_type_labels.get(need.get('need_type', ''), need.get('need_type', ''))}  ",
                f"**Приоритет:** {need.get('priority', '—')}  ",
                f"**Источник:** {need.get('source', '—')}",
                "",
                need.get("description", "—"),
            ]
            if need.get("cost_of_inaction"):
                report_lines += ["", f"**Стоимость бездействия:** {need['cost_of_inaction']}"]
            if need.get("expected_benefits"):
                report_lines += ["", f"**Ожидаемые выгоды:** {need['expected_benefits']}"]
            if need.get("root_cause_ids"):
                report_lines += ["", f"**Связанные RCA:** {', '.join(need['root_cause_ids'])}"]
            report_lines.append("")

    if analyst_notes:
        report_lines += [
            "---",
            "",
            "## Заключение аналитика",
            "",
            analyst_notes,
            "",
        ]

    if draft_warnings:
        report_lines += [
            "---",
            "",
            f"⚠️ **Черновики:** элементы {draft_warnings} содержат неуточнённые данные из импорта.",
            "",
        ]

    report_lines += [
        "---",
        "",
        f"*Анализ текущего состояния выполнен по методологии BABOK v3, задача 6.1.*  ",
        f"*Сгенерировано: {datetime.now().strftime('%d.%m.%Y %H:%M')}*",
    ]

    report_content = "\n".join(report_lines)
    save_artifact(report_content, prefix=f"6_1_current_state_{_safe(project_id)}")

    # Проброс в 7.3 (ADR-055)
    push_status = ""
    if push_to_business_context and needs_list:
        push_status = (
            "\n\n## Интеграция с 7.3\n\n"
            f"Данные подготовлены для передачи в `set_business_context` (7.3).\n"
            f"Вызовите: `set_business_context(project_id='{project_id}', "
            f"from_current_state_project_id='{project_id}', ...)`\n"
            f"Параметр `from_current_state_project_id` предзаполнит бизнес-цели из {len(needs_list)} бизнес-потребностей."
        )

    result_lines = [
        f"✅ Анализ текущего состояния финализирован: **{project_id}**",
        "",
        f"**Проект:** {project_title}",
        f"**Дата:** {date.today()}",
        "",
        "## Сводка артефактов",
        "",
        f"- 📄 **Отчёт:** сохранён через save_artifact (`6_1_current_state_{_safe(project_id)}`)",
        f"- 📊 **Данные:** `{_safe(project_id)}_{STATE_FILENAME}`",
        f"- 📋 **Скоуп:** `{_safe(project_id)}_{SCOPE_FILENAME}`",
        f"- 🎯 **Бизнес-потребности:** `{_safe(project_id)}_{NEEDS_FILENAME}` ({len(needs_list)} шт.)",
        "",
        "## Статистика",
        "",
        f"- Элементов проанализировано: {len([e for e in elements_in_scope if e in elements_data])} / {len(elements_in_scope)}",
        f"- RCA проведено: {len(rca_list)}",
        f"- Бизнес-потребностей: {len(needs_list)}",
    ]

    if draft_warnings:
        result_lines += [
            "",
            f"⚠️ Черновики: {len(draft_warnings)} элементов имеют неуточнённые данные: {draft_warnings}",
        ]

    result_lines += [
        push_status,
        "",
        "---",
        "",
        "**Следующие шаги:**",
        "- Используйте результаты в задаче **6.2** (Define Future State) для gap analysis",
        "- Вызовите `set_business_context` в задаче **7.3** с `from_current_state_project_id` для автозаполнения",
        "- Бизнес-потребности (BN-xxx) доступны в репозитории 5.1 как upstream-узлы трассировки",
    ]

    return "\n".join(result_lines)


if __name__ == "__main__":
    mcp.run()
