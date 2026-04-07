"""
BABOK 6.2 — Define Future State
MCP-инструменты для определения будущего состояния организации.

Инструменты:
  - scope_future_state                — скоуп анализа: тип инициативы, глубина, элементы
  - capture_future_state_element      — зафиксировать один из 8 элементов будущего состояния
  - define_goals_and_objectives       — SMART-цели с KPI + регистрация в 5.1 как business_goal
  - capture_constraints               — реестр ограничений по категориям
  - run_gap_analysis                  — gap-анализ текущего vs будущего (прямой вход для 6.4)
  - assess_potential_value            — качественная оценка потенциальной ценности (контекст для 7.6)
  - check_future_state_completeness   — coverage check перед финализацией
  - save_future_state                 — финализация + Markdown отчёт + проброс в 7.3

Хранение:
  - {project}_future_state_scope.json   — скоуп анализа (контракт)
  - {project}_future_state.json         — элементы, цели, ограничения, value, статус
  - {project}_future_state_goals.json   — цели и KPI (+ регистрация BG в 5.1)
  - {project}_gap_analysis.json         — результаты gap-анализа для 6.4
  - {project}_future_state_analysis.md  — читаемый отчёт (через save_artifact)

Интеграция:
  Вход: 6.1 данные (опционально) — business_needs, current_state, current_state_scope
  Выход: BG-узлы в репозитории 5.1, gap_analysis для 6.4, данные для 7.3 set_business_context

ADR-060: связь 6.2 и 6.1 — модульная (6.1 опционален, при наличии — автоимпорт)
ADR-061: элементы 6.2 — те же 8 доменов что в 6.1 + отдельные инструменты для целей и ограничений
ADR-062: business_goal как тип узла в репозитории 5.1
ADR-063: gap-анализ — отдельный явный инструмент
ADR-064: потенциальная ценность в 6.2 — качественная структурированная
ADR-065: from_strategy_project_id — единый параметр для 7.3
ADR-066: check_future_state_completeness — отдельный инструмент по паттерну 6.1

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date, datetime
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import save_artifact, logger, DATA_DIR

mcp = FastMCP("BABOK_FutureState")

SCOPE_FILENAME = "future_state_scope.json"
STATE_FILENAME = "future_state.json"
GOALS_FILENAME = "future_state_goals.json"
GAP_FILENAME = "gap_analysis.json"
REPO_FILENAME = "traceability_repo.json"

# Файлы 6.1 (опциональный источник)
CS_SCOPE_FILENAME = "current_state_scope.json"
CS_STATE_FILENAME = "current_state.json"
CS_NEEDS_FILENAME = "business_needs.json"

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


def _goals_path(project_id: str) -> str:
    return os.path.join(DATA_DIR, f"{_safe(project_id)}_{GOALS_FILENAME}")


def _gap_path(project_id: str) -> str:
    return os.path.join(DATA_DIR, f"{_safe(project_id)}_{GAP_FILENAME}")


def _repo_path(project_id: str) -> str:
    return os.path.join(DATA_DIR, f"{_safe(project_id)}_{REPO_FILENAME}")


def _cs_scope_path(project_id: str) -> str:
    return os.path.join(DATA_DIR, f"{_safe(project_id)}_{CS_SCOPE_FILENAME}")


def _cs_state_path(project_id: str) -> str:
    return os.path.join(DATA_DIR, f"{_safe(project_id)}_{CS_STATE_FILENAME}")


def _cs_needs_path(project_id: str) -> str:
    return os.path.join(DATA_DIR, f"{_safe(project_id)}_{CS_NEEDS_FILENAME}")


def _load_json(path: str) -> Optional[dict]:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_json(path: str, data: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_scope(project_id: str) -> Optional[dict]:
    return _load_json(_scope_path(project_id))


def _save_scope(data: dict) -> str:
    path = _scope_path(data["project_id"])
    _save_json(path, data)
    logger.info(f"Скоуп будущего состояния сохранён: {path}")
    return path


def _load_state(project_id: str) -> dict:
    data = _load_json(_state_path(project_id))
    if data:
        return data
    return {
        "project_id": project_id,
        "scope_ref": f"{_safe(project_id)}_{SCOPE_FILENAME}",
        "elements": {},
        "constraints": [],
        "potential_value": None,
        "gap_analysis_done": False,
        "created": str(date.today()),
        "updated": str(date.today()),
    }


def _save_state(data: dict) -> str:
    path = _state_path(data["project_id"])
    data["updated"] = str(date.today())
    _save_json(path, data)
    logger.info(f"Данные будущего состояния сохранены: {path}")
    return path


def _load_goals(project_id: str) -> dict:
    data = _load_json(_goals_path(project_id))
    if data:
        return data
    return {
        "project_id": project_id,
        "goals": [],
        "created": str(date.today()),
        "updated": str(date.today()),
    }


def _save_goals(data: dict) -> str:
    path = _goals_path(data["project_id"])
    data["updated"] = str(date.today())
    _save_json(path, data)
    logger.info(f"Цели будущего состояния сохранены: {path}")
    return path


def _load_gap(project_id: str) -> Optional[dict]:
    return _load_json(_gap_path(project_id))


def _save_gap(data: dict) -> str:
    path = _gap_path(data["project_id"])
    _save_json(path, data)
    logger.info(f"Gap-анализ сохранён: {path}")
    return path


def _load_repo(project_id: str) -> Optional[dict]:
    return _load_json(_repo_path(project_id))


def _save_repo(repo: dict) -> None:
    path = _repo_path(repo["project"])
    repo["updated"] = str(date.today())
    _save_json(path, repo)
    logger.info(f"Репозиторий трассировки обновлён из 6.2: {path}")


def _next_goal_id(goals_data: dict) -> str:
    existing = [g["id"] for g in goals_data["goals"] if g["id"].startswith("BG-")]
    if not existing:
        return "BG-001"
    nums = [int(g.split("-")[1]) for g in existing if g.split("-")[1].isdigit()]
    return f"BG-{(max(nums) + 1):03d}" if nums else "BG-001"


def _validate_smart(goal_title: str, description: str, objectives: list) -> list:
    """Проверяет SMART-критерии для цели. Возвращает список замечаний."""
    issues = []
    if len(goal_title.strip()) < 10:
        issues.append("S (Specific): заголовок цели слишком короткий — добавьте конкретики")
    if not objectives:
        issues.append("M (Measurable): нет ни одного целевого показателя — добавьте KPI")
    else:
        for obj in objectives:
            if not obj.get("target"):
                issues.append(f"M (Measurable): в показателе '{obj.get('title', '?')}' не указано target значение")
            if not obj.get("baseline"):
                issues.append(f"M (Measurable): в показателе '{obj.get('title', '?')}' не указан baseline (текущее значение)")
            if not obj.get("deadline"):
                issues.append(f"T (Time-bound): в показателе '{obj.get('title', '?')}' не указан deadline")
    return issues


# ---------------------------------------------------------------------------
# 6.2.1 — Скоупинг анализа будущего состояния
# ---------------------------------------------------------------------------

@mcp.tool()
def scope_future_state(
    project_id: str,
    initiative_type: Literal[
        "process_improvement", "new_system", "regulatory",
        "cost_reduction", "market_opportunity", "other"
    ],
    analysis_depth: Literal["light", "standard", "deep"],
    known_goals: str = "",
    elements_in_scope: str = "",
) -> str:
    """
    BABOK 6.2 — Первый шаг: скоуп анализа будущего состояния.
    По аналогии с scope_current_state (6.1) — явный контракт (ADR-058/ADR-060).
    При наличии данных 6.1 — автоматически читает их как контекст.

    Args:
        project_id:        Идентификатор проекта (тот же что в 6.1).
        initiative_type:   Тип инициативы:
                           - process_improvement — улучшение процессов
                           - new_system          — внедрение новой системы
                           - regulatory          — выполнение регуляторных требований
                           - cost_reduction      — снижение затрат
                           - market_opportunity  — рыночная возможность
                           - other               — другое
        analysis_depth:    Глубина анализа:
                           - light    — 3–4 элемента, стратегический срез
                           - standard — 5–6 элементов, большинство проектов
                           - deep     — все 8 элементов, стратегические инициативы
        known_goals:       Опционально — известные цели от спонсора (свободный текст).
        elements_in_scope: Опционально — переопределить список элементов вручную.
                           JSON-список ключей:
                           '[\"business_needs\",\"capabilities\",\"technology\"]'
                           Допустимые ключи: business_needs | org_structure | capabilities |
                           technology | policies | architecture | assets | external

    Returns:
        Подтверждение скоупа + контекст из 6.1 (если есть) + следующие шаги.
    """
    logger.info(f"scope_future_state: {project_id}, type={initiative_type}, depth={analysis_depth}")

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
        base_elements = DEFAULT_ELEMENTS_BY_TYPE.get(initiative_type, ["business_needs", "capabilities"])
        if analysis_depth == "deep":
            chosen_elements = VALID_ELEMENTS
        elif analysis_depth == "light":
            chosen_elements = base_elements[:3]
        else:
            chosen_elements = base_elements
        elements_source = f"рекомендовано для {initiative_type}/{analysis_depth}"

    # Читаем данные 6.1 если есть (ADR-060)
    cs_scope = _load_json(_cs_scope_path(project_id))
    cs_needs = _load_json(_cs_needs_path(project_id))
    has_current_state = cs_scope is not None

    existing = _load_scope(project_id)
    is_update = existing is not None

    scope_data = {
        "project_id": project_id,
        "initiative_type": initiative_type,
        "analysis_depth": analysis_depth,
        "known_goals": known_goals,
        "elements_in_scope": chosen_elements,
        "has_current_state_data": has_current_state,
        "created": existing["created"] if existing else str(date.today()),
        "updated": str(date.today()),
    }

    _save_scope(scope_data)

    type_labels = {
        "process_improvement": "Улучшение процессов",
        "new_system": "Внедрение новой системы",
        "regulatory": "Регуляторные требования",
        "cost_reduction": "Снижение затрат",
        "market_opportunity": "Рыночная возможность",
        "other": "Другое",
    }
    depth_labels = {
        "light": "Лёгкий (3–4 элемента, стратегический срез)",
        "standard": "Стандартный (5–6 элементов)",
        "deep": "Глубокий (все 8 элементов)",
    }

    lines = [
        f"{'⚠️ Скоуп ОБНОВЛЁН' if is_update else '✅ Скоуп анализа будущего состояния определён'} — **{project_id}**",
        "",
        f"**Тип инициативы:** {type_labels.get(initiative_type, initiative_type)}",
        f"**Глубина анализа:** {depth_labels.get(analysis_depth, analysis_depth)}",
        f"**Дата:** {date.today()}",
        "",
        f"## Элементы в скоупе ({len(chosen_elements)} из 8) — {elements_source}",
        "",
    ]

    for i, elem in enumerate(chosen_elements, 1):
        label = ELEMENT_LABELS.get(elem, elem)
        lines.append(f"{i}. **{elem}** — {label}")

    not_in_scope = [e for e in VALID_ELEMENTS if e not in chosen_elements]
    if not_in_scope:
        lines += ["", "### Элементы вне скоупа:"]
        for elem in not_in_scope:
            lines.append(f"- ~~{elem}~~ — {ELEMENT_LABELS.get(elem, elem)}")

    # Контекст из 6.1
    if has_current_state:
        bn_count = len(cs_needs.get("needs", [])) if cs_needs else 0
        cs_elements = cs_scope.get("elements_in_scope", [])
        lines += [
            "",
            "## ✅ Данные из 6.1 найдены",
            "",
            f"- Элементов текущего состояния: {len(cs_elements)}",
            f"- Бизнес-потребностей: {bn_count}",
            "",
            "При заполнении элементов (`capture_future_state_element`) система покажет",
            "текущее состояние рядом с будущим — используйте как ориентир.",
            "Цели (`define_goals_and_objectives`) можно привязать к существующим BN-xxx.",
        ]
    else:
        lines += [
            "",
            "ℹ️ Данные 6.1 не найдены — gap-анализ будет работать без базы текущего состояния.",
            "Если 6.1 ещё не проводилась — рекомендуется начать с неё.",
        ]

    if known_goals:
        lines += [
            "",
            "## Известные цели",
            "",
            known_goals,
        ]

    lines += [
        "",
        "---",
        "",
        "## Следующие шаги",
        "",
        "1. `capture_future_state_element` — заполнить каждый элемент из скоупа",
        "2. `define_goals_and_objectives` — зафиксировать SMART-цели с KPI",
        "3. `capture_constraints` — зафиксировать ограничения",
        "4. `run_gap_analysis` — сравнить текущее и будущее состояние",
        "5. `assess_potential_value` — оценить потенциальную ценность",
        "6. `check_future_state_completeness` — проверить готовность",
        "7. `save_future_state` — финализировать анализ",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.2.2 — Итеративный сбор данных по элементам будущего состояния
# ---------------------------------------------------------------------------

@mcp.tool()
def capture_future_state_element(
    project_id: str,
    element: Literal[
        "business_needs", "org_structure", "capabilities",
        "technology", "policies", "architecture", "assets", "external"
    ],
    description: str,
    target_metrics: str = "{}",
    linked_business_needs: str = "[]",
    sources: str = '["elicitation"]',
    notes: str = "",
) -> str:
    """
    BABOK 6.2 — Зафиксировать один элемент будущего состояния (ADR-061).
    Итеративный паттерн: вызывается по одному разу на каждый элемент.
    При наличии 6.1 — показывает текущее состояние рядом («прошлое рядом с будущим»).

    Args:
        project_id:             Идентификатор проекта.
        element:                Один из 8 элементов:
                                business_needs | org_structure | capabilities | technology |
                                policies | architecture | assets | external
        description:            Описание целевого состояния элемента («как должно быть»).
                                Ориентировано на результат, не на процесс внедрения.
        target_metrics:         Целевые измеримые показатели для этого элемента.
                                JSON-объект: '{\"processing_time\": \"2 hours\", \"error_rate\": \"<2%\"}'
        linked_business_needs:  Список BN-xxx из 6.1, которые этот элемент адресует.
                                JSON-список строк: '[\"BN-001\",\"BN-002\"]'
        sources:                Откуда данные: JSON-список источников.
                                Допустимые: elicitation | document | workshop | interview | other
        notes:                  Свободные заметки (допущения, вопросы, открытые пункты).

    Returns:
        Подтверждение записи + текущее состояние из 6.1 (если есть) + прогресс.
    """
    logger.info(f"capture_future_state_element: {project_id}, element={element}")

    if not description.strip():
        return "❌ description не может быть пустым — опиши целевое состояние элемента."

    try:
        target_dict = json.loads(target_metrics) if target_metrics.strip() else {}
        if not isinstance(target_dict, dict):
            return "❌ target_metrics должен быть JSON-объектом: '{\"показатель\": \"значение\"}'"
    except json.JSONDecodeError as e:
        return f"❌ Ошибка парсинга target_metrics: {e}"

    try:
        bn_list = json.loads(linked_business_needs) if linked_business_needs.strip() else []
        if not isinstance(bn_list, list):
            return "❌ linked_business_needs должен быть JSON-списком строк"
    except json.JSONDecodeError as e:
        return f"❌ Ошибка парсинга linked_business_needs: {e}"

    try:
        sources_list = json.loads(sources) if sources.strip() else ["elicitation"]
        if not isinstance(sources_list, list):
            return "❌ sources должен быть JSON-списком"
    except json.JSONDecodeError as e:
        return f"❌ Ошибка парсинга sources: {e}"

    # Проверяем скоуп
    scope = _load_scope(project_id)
    scope_warning = ""
    if scope and element not in scope.get("elements_in_scope", []):
        scope_warning = (
            f"\n⚠️ Элемент `{element}` не входит в текущий скоуп. "
            f"Добавить через повторный вызов `scope_future_state`."
        )

    # Загружаем и обновляем state
    state = _load_state(project_id)
    is_update = element in state["elements"]

    state["elements"][element] = {
        "description": description,
        "target_metrics": target_dict,
        "linked_business_needs": bn_list,
        "sources": sources_list,
        "notes": notes,
        "draft": False,
        "last_updated": str(date.today()),
    }
    _save_state(state)

    label = ELEMENT_LABELS.get(element, element)
    action = "ОБНОВЛЁН" if is_update else "сохранён"

    lines = [
        f"✅ Элемент будущего состояния **{label}** (`{element}`) {action}",
        "",
        f"**Описание:** {description[:200]}{'...' if len(description) > 200 else ''}",
    ]

    if target_dict:
        lines += ["", "**Целевые метрики:**"]
        for k, v in target_dict.items():
            lines.append(f"- {k}: {v}")

    if bn_list:
        lines += ["", f"**Связанные бизнес-потребности:** {', '.join(bn_list)}"]

    lines += ["", f"**Источники:** {', '.join(sources_list)}"]

    if scope_warning:
        lines.append(scope_warning)

    # Текущее состояние из 6.1 (UX-паттерн «прошлое рядом с будущим»)
    cs_state = _load_json(_cs_state_path(project_id))
    if cs_state and element in cs_state.get("elements", {}):
        cs_elem = cs_state["elements"][element]
        cs_desc = cs_elem.get("description", "")
        if cs_desc:
            lines += [
                "",
                "---",
                "",
                f"### 🔍 Для сравнения — текущее состояние (`{element}` из 6.1):",
                "",
                cs_desc[:300] + ("..." if len(cs_desc) > 300 else ""),
            ]
            cs_metrics = cs_elem.get("metrics", {})
            if cs_metrics:
                lines += ["", "**Текущие метрики:**"]
                for k, v in cs_metrics.items():
                    lines.append(f"- {k}: {v}")
            lines += ["", "---"]

    # Прогресс по скоупу
    if scope:
        elements_in_scope = scope.get("elements_in_scope", [])
        filled = [e for e in elements_in_scope if e in state["elements"] and not state["elements"][e].get("draft", True)]
        remaining = [e for e in elements_in_scope if e not in state["elements"] or state["elements"][e].get("draft", True)]

        lines += [
            "",
            f"## Прогресс: {len(filled)}/{len(elements_in_scope)} элементов",
            "",
        ]
        for e in elements_in_scope:
            elem_label = ELEMENT_LABELS.get(e, e)
            status = "✅" if e in filled else "⬜"
            lines.append(f"{status} {elem_label}")

        if remaining:
            lines += ["", f"**Следующий элемент:** `{remaining[0]}`"]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.2.3 — Бизнес-цели и KPI
# ---------------------------------------------------------------------------

@mcp.tool()
def define_goals_and_objectives(
    project_id: str,
    goal_title: str,
    description: str,
    objectives_json: str,
    linked_business_needs: str = "[]",
    register_in_traceability: bool = True,
) -> str:
    """
    BABOK 6.2 — Зафиксировать бизнес-цель с KPI. SMART-валидация (ADR-062).
    Регистрирует цель как узел business_goal в репозитории 5.1.
    Обеспечивает трассировку BN → derives → BG.

    Args:
        project_id:              Идентификатор проекта.
        goal_title:              Краткий заголовок цели (до 100 символов).
        description:             Описание цели — чего достигнем и почему это важно.
        objectives_json:         Список целевых показателей (KPI) — JSON-список объектов.
                                 Каждый объект:
                                 {
                                   \"title\": \"Сократить время обработки заявок\",
                                   \"metric\": \"Время обработки (часы)\",
                                   \"baseline\": \"8 часов (Q1 2025)\",
                                   \"target\": \"2 часа\",
                                   \"deadline\": \"2025-12-31\"
                                 }
        linked_business_needs:   Список BN-xxx из 6.1, к которым привязана цель.
                                 JSON-список строк: '[\"BN-001\",\"BN-002\"]'
        register_in_traceability: Если True — создать узел business_goal в репозитории 5.1.
                                 Default: True. Отключить если репозиторий 5.1 не создан.

    Returns:
        Карточка цели с ID + SMART-замечания + статус регистрации в 5.1.
    """
    logger.info(f"define_goals_and_objectives: {project_id}, title='{goal_title[:50]}'")

    if not goal_title.strip():
        return "❌ goal_title не может быть пустым."
    if not description.strip():
        return "❌ description не может быть пустым."

    try:
        objectives = json.loads(objectives_json) if objectives_json.strip() else []
        if not isinstance(objectives, list):
            return "❌ objectives_json должен быть JSON-списком объектов."
    except json.JSONDecodeError as e:
        return f"❌ Ошибка парсинга objectives_json: {e}"

    try:
        bn_list = json.loads(linked_business_needs) if linked_business_needs.strip() else []
        if not isinstance(bn_list, list):
            return "❌ linked_business_needs должен быть JSON-списком строк."
    except json.JSONDecodeError as e:
        return f"❌ Ошибка парсинга linked_business_needs: {e}"

    # SMART-валидация
    smart_issues = _validate_smart(goal_title, description, objectives)

    goals_data = _load_goals(project_id)
    goal_id = _next_goal_id(goals_data)

    goal_record = {
        "id": goal_id,
        "goal_title": goal_title,
        "description": description,
        "objectives": objectives,
        "linked_business_needs": bn_list,
        "smart_validated": len(smart_issues) == 0,
        "created": str(date.today()),
    }
    goals_data["goals"].append(goal_record)
    _save_goals(goals_data)

    # Регистрация в репозитории 5.1 (ADR-062)
    traceability_status = ""
    if register_in_traceability:
        repo = _load_repo(project_id)
        if repo is None:
            traceability_status = (
                "\n\n⚠️ Репозиторий трассировки 5.1 не найден.\n"
                "Создайте его через `init_traceability_repo` (5.1), "
                f"затем узел `{goal_id}` типа `business_goal` будет добавлен автоматически."
            )
        else:
            existing_ids = {r["id"] for r in repo["requirements"]}
            if goal_id not in existing_ids:
                repo["requirements"].append({
                    "id": goal_id,
                    "type": "business_goal",
                    "title": goal_title,
                    "version": "1.0",
                    "status": "confirmed",
                    "source_artifact": f"6.2/{_safe(project_id)}_future_state_goals.json",
                    "added": str(date.today()),
                })
                # Добавляем связи BN → BG
                for bn_id in bn_list:
                    repo["links"].append({
                        "from": goal_id,
                        "to": bn_id,
                        "relation": "derives",
                        "rationale": f"Бизнес-цель вытекает из бизнес-потребности {bn_id}",
                        "added": str(date.today()),
                    })
                repo["history"].append({
                    "action": "node_added",
                    "id": goal_id,
                    "type": "business_goal",
                    "source": "6.2 define_goals_and_objectives",
                    "date": str(date.today()),
                })
                _save_repo(repo)
                trace_chain = " → ".join([f"{bn}" for bn in bn_list]) + f" → {goal_id}" if bn_list else goal_id
                traceability_status = (
                    f"\n\n✅ Узел `{goal_id}` (business_goal) зарегистрирован в репозитории 5.1."
                    + (f"\n   Трассировка: {trace_chain}" if bn_list else "")
                )
            else:
                traceability_status = f"\n\nℹ️ Узел `{goal_id}` уже существует в репозитории 5.1."

    lines = [
        f"✅ Бизнес-цель зафиксирована: **{goal_id}**",
        "",
        f"**{goal_title}**",
        "",
        f"**Дата:** {date.today()}",
        "",
        "## Описание",
        "",
        description,
    ]

    if objectives:
        lines += ["", "## Целевые показатели (KPI)", ""]
        for i, obj in enumerate(objectives, 1):
            lines += [
                f"### {i}. {obj.get('title', '—')}",
                f"- **Метрика:** {obj.get('metric', '—')}",
                f"- **Baseline:** {obj.get('baseline', '—')}",
                f"- **Target:** {obj.get('target', '—')}",
                f"- **Дедлайн:** {obj.get('deadline', '—')}",
                "",
            ]

    if bn_list:
        lines += [f"**Связанные бизнес-потребности:** {', '.join(bn_list)}"]

    # SMART-замечания
    if smart_issues:
        lines += [
            "",
            "## ⚠️ SMART-замечания",
            "",
            "> Цель сохранена. Устраните замечания для соответствия SMART-критериям:",
            "",
        ]
        for issue in smart_issues:
            lines.append(f"- {issue}")
    else:
        lines += ["", "✅ SMART-критерии соблюдены."]

    total_goals = len(goals_data["goals"])
    lines += [
        "",
        "---",
        "",
        f"Всего бизнес-целей в проекте: **{total_goals}**",
        traceability_status,
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.2.4 — Реестр ограничений
# ---------------------------------------------------------------------------

@mcp.tool()
def capture_constraints(
    project_id: str,
    constraint_title: str,
    category: Literal["budget", "time", "technology", "policy", "resources", "compliance", "other"],
    description: str,
    status: Literal["confirmed", "assumed"],
    linked_elements: str = "[]",
) -> str:
    """
    BABOK 6.2 — Зафиксировать ограничение, сужающее пространство решений (ADR-061).
    Ограничения проверяются в 7.5 при разработке дизайн-опций.

    Args:
        project_id:       Идентификатор проекта.
        constraint_title: Краткий заголовок ограничения.
        category:         Категория ограничения:
                          - budget     — финансовый лимит
                          - time       — временные рамки, дедлайны
                          - technology — технологические стандарты
                          - policy     — внутренние политики и правила
                          - resources  — команда, компетенции, мощности
                          - compliance — регуляторные и законодательные требования
                          - other      — прочее
        description:      Полное описание ограничения и его влияния.
        status:           Статус подтверждения:
                          - confirmed — подтверждено документально или уполномоченным лицом
                          - assumed   — BA предполагает наличие ограничения
        linked_elements:  Элементы будущего состояния, на которые влияет ограничение.
                          JSON-список ключей: '[\"technology\",\"capabilities\"]'

    Returns:
        Карточка ограничения + итоговый реестр ограничений проекта.
    """
    logger.info(f"capture_constraints: {project_id}, category={category}, title='{constraint_title[:40]}'")

    if not constraint_title.strip():
        return "❌ constraint_title не может быть пустым."
    if not description.strip():
        return "❌ description не может быть пустым."

    try:
        elements_list = json.loads(linked_elements) if linked_elements.strip() else []
        invalid = [e for e in elements_list if e not in VALID_ELEMENTS]
        if invalid:
            return f"❌ Неизвестные элементы в linked_elements: {invalid}"
    except json.JSONDecodeError as e:
        return f"❌ Ошибка парсинга linked_elements: {e}"

    state = _load_state(project_id)

    # Проверяем дубликат по заголовку
    existing_titles = [c["title"] for c in state.get("constraints", [])]
    is_duplicate = constraint_title in existing_titles

    constraint_record = {
        "title": constraint_title,
        "category": category,
        "description": description,
        "status": status,
        "linked_elements": elements_list,
        "created": str(date.today()),
    }

    if is_duplicate:
        # Обновляем существующее
        state["constraints"] = [c for c in state["constraints"] if c["title"] != constraint_title]
    state["constraints"].append(constraint_record)
    _save_state(state)

    category_labels = {
        "budget": "Финансовый лимит",
        "time": "Временные рамки",
        "technology": "Технологические стандарты",
        "policy": "Внутренние политики",
        "resources": "Ресурсы и компетенции",
        "compliance": "Регуляторные требования",
        "other": "Прочее",
    }

    status_icons = {"confirmed": "✅ Подтверждено", "assumed": "🔶 Предположение"}

    lines = [
        f"{'⚠️ Ограничение ОБНОВЛЕНО' if is_duplicate else '✅ Ограничение зафиксировано'}",
        "",
        f"**{constraint_title}**",
        f"**Категория:** {category_labels.get(category, category)}  ",
        f"**Статус:** {status_icons.get(status, status)}  ",
        f"**Дата:** {date.today()}",
        "",
        "## Описание",
        "",
        description,
    ]

    if elements_list:
        lines += ["", f"**Затронутые элементы:** {', '.join(elements_list)}"]

    if status == "assumed":
        lines += [
            "",
            "⚠️ Ограничение помечено как предположение.",
            "Рекомендуется валидировать у уполномоченного лица до начала дизайна решения.",
        ]

    # Итоговый реестр
    all_constraints = state.get("constraints", [])
    confirmed = [c for c in all_constraints if c.get("status") == "confirmed"]
    assumed = [c for c in all_constraints if c.get("status") == "assumed"]

    lines += [
        "",
        "---",
        "",
        f"## Реестр ограничений проекта: {len(all_constraints)} шт.",
        f"✅ Подтверждено: {len(confirmed)}  |  🔶 Предположений: {len(assumed)}",
        "",
    ]
    by_cat: dict = {}
    for c in all_constraints:
        cat = c.get("category", "other")
        by_cat.setdefault(cat, []).append(c)
    for cat, items in by_cat.items():
        lines.append(f"**{category_labels.get(cat, cat)}:** {', '.join(i['title'] for i in items)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.2.5 — Gap-анализ
# ---------------------------------------------------------------------------

@mcp.tool()
def run_gap_analysis(
    project_id: str,
) -> str:
    """
    BABOK 6.2 — Провести gap-анализ: сравнить текущее и будущее состояние (ADR-063).
    Явный отдельный инструмент: BA запускает осознанно после заполнения всех элементов.
    Результат — прямой вход для 6.4 (Define Change Strategy).

    По каждому элементу будущего состояния:
    - Сравнивает с текущим состоянием из 6.1 (если есть)
    - Формулирует разрыв (gap_summary)
    - Определяет тип изменения: new | improve | eliminate | replace
    - Оценивает сложность: low | medium | high

    Args:
        project_id: Идентификатор проекта.

    Returns:
        Gap-карточки по всем элементам + сводка + артефакт {project}_gap_analysis.json.
    """
    logger.info(f"run_gap_analysis: {project_id}")

    state = _load_state(project_id)
    elements_data = state.get("elements", {})

    if not elements_data:
        return (
            "⚠️ Нет данных будущего состояния.\n"
            "Сначала заполните элементы через `capture_future_state_element`."
        )

    # Читаем данные 6.1 для сравнения
    cs_state = _load_json(_cs_state_path(project_id))
    cs_elements = cs_state.get("elements", {}) if cs_state else {}
    has_current_state = bool(cs_elements)

    gaps = []
    for element, fs_data in elements_data.items():
        if fs_data.get("draft"):
            continue
        cs_elem = cs_elements.get(element, {})
        current_desc = cs_elem.get("description") if cs_elem else None
        future_desc = fs_data.get("description", "")

        # Автоматическая классификация типа изменения
        if not current_desc:
            change_type = "new"
            gap_summary = f"Нет текущего состояния — элемент создаётся с нуля. Целевое: {future_desc[:100]}"
            complexity = "medium"
        else:
            change_type = "improve"
            gap_summary = f"Текущее: {current_desc[:80]}... → Целевое: {future_desc[:80]}..."
            # Простая эвристика сложности
            current_pain = len(cs_elem.get("pain_points", []))
            target_metrics = fs_data.get("target_metrics", {})
            if current_pain >= 3 or len(target_metrics) >= 3:
                complexity = "high"
            elif current_pain >= 1 or len(target_metrics) >= 1:
                complexity = "medium"
            else:
                complexity = "low"

        gap_record = {
            "element": element,
            "element_label": ELEMENT_LABELS.get(element, element),
            "current_description": current_desc,
            "future_description": future_desc,
            "gap_summary": gap_summary,
            "change_type": change_type,
            "complexity": complexity,
        }
        gaps.append(gap_record)

    gap_data = {
        "project_id": project_id,
        "has_current_state_baseline": has_current_state,
        "gaps": gaps,
        "created": str(date.today()),
        "updated": str(date.today()),
    }
    _save_gap(gap_data)

    # Обновляем флаг в state
    state["gap_analysis_done"] = True
    _save_state(state)

    # Формируем отчёт
    complexity_icons = {"low": "🟢", "medium": "🟡", "high": "🔴"}
    change_labels = {
        "new": "🆕 Новое",
        "improve": "⬆️ Улучшение",
        "eliminate": "🗑️ Устранение",
        "replace": "🔄 Замена",
    }

    lines = [
        f"✅ Gap-анализ проведён — **{project_id}**",
        "",
        f"**Дата:** {date.today()}",
        f"**Элементов проанализировано:** {len(gaps)}",
        f"**Базис текущего состояния:** {'✅ из 6.1' if has_current_state else '⚠️ отсутствует (gap = null → future)'}",
        "",
        "---",
        "",
    ]

    for gap in gaps:
        lines += [
            f"## {gap['element_label']} (`{gap['element']}`)",
            "",
            f"**Тип изменения:** {change_labels.get(gap['change_type'], gap['change_type'])}  ",
            f"**Сложность:** {complexity_icons.get(gap['complexity'], '')} {gap['complexity'].capitalize()}",
            "",
        ]
        if gap["current_description"]:
            lines += [
                f"**Текущее состояние:** {gap['current_description'][:150]}{'...' if len(gap['current_description']) > 150 else ''}",
            ]
        else:
            lines.append("**Текущее состояние:** *(данных 6.1 нет)*")
        lines += [
            f"**Целевое состояние:** {gap['future_description'][:150]}{'...' if len(gap['future_description']) > 150 else ''}",
            "",
            f"**Gap:** {gap['gap_summary']}",
            "",
        ]

    # Сводка
    by_type: dict = {}
    by_complexity: dict = {}
    for g in gaps:
        by_type[g["change_type"]] = by_type.get(g["change_type"], 0) + 1
        by_complexity[g["complexity"]] = by_complexity.get(g["complexity"], 0) + 1

    lines += [
        "---",
        "",
        "## Сводка gap-анализа",
        "",
        "### По типу изменений:",
    ]
    for ct, cnt in by_type.items():
        lines.append(f"- {change_labels.get(ct, ct)}: {cnt}")
    lines += ["", "### По сложности:"]
    for cx, cnt in by_complexity.items():
        lines.append(f"- {complexity_icons.get(cx, '')} {cx.capitalize()}: {cnt}")

    lines += [
        "",
        "---",
        "",
        f"**Артефакт:** `{_safe(project_id)}_{GAP_FILENAME}`",
        "",
        "**Следующий шаг:**",
        "- `assess_potential_value` — оценить потенциальную ценность изменений",
        "- В задаче **6.4** этот gap-анализ станет основой стратегии изменений",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.2.6 — Потенциальная ценность
# ---------------------------------------------------------------------------

@mcp.tool()
def assess_potential_value(
    project_id: str,
    benefits_json: str,
    investment_level: Literal["low", "medium", "high", "unknown"],
    value_summary: str = "",
) -> str:
    """
    BABOK 6.2 — Предварительная качественная оценка потенциальной ценности (ADR-064).
    Без формулы — структурированный список выгод. Это контекст для 7.6, не замена.

    Args:
        project_id:       Идентификатор проекта.
        benefits_json:    Список выгод. JSON-список объектов:
                          [
                            {
                              \"benefit_title\": \"Сокращение времени обработки\",
                              \"benefit_type\": \"operational\",
                              \"magnitude\": \"high\",
                              \"confidence\": \"medium\",
                              \"description\": \"Описание выгоды\",
                              \"linked_business_needs\": [\"BN-001\"],
                              \"linked_goals\": [\"BG-001\"]
                            }
                          ]
                          benefit_type: financial | operational | strategic | compliance
                          magnitude: high | medium | low
                          confidence: high | medium | low
        investment_level: Качественный уровень инвестиций:
                          - low     — небольшие изменения без разработки
                          - medium  — умеренная разработка / закупка, 3–12 месяцев
                          - high    — трансформационный проект, 12+ месяцев
                          - unknown — пока невозможно оценить
        value_summary:    Суммарный тезис о ценности для коммуникации со спонсором.

    Returns:
        Структурированная карточка потенциальной ценности + профиль «выгода / инвестиции».
    """
    logger.info(f"assess_potential_value: {project_id}")

    try:
        benefits = json.loads(benefits_json) if benefits_json.strip() else []
        if not isinstance(benefits, list):
            return "❌ benefits_json должен быть JSON-списком объектов."
    except json.JSONDecodeError as e:
        return f"❌ Ошибка парсинга benefits_json: {e}"

    if not benefits:
        return "❌ benefits_json не может быть пустым — добавьте хотя бы одну выгоду."

    valid_types = {"financial", "operational", "strategic", "compliance"}
    valid_magnitude = {"high", "medium", "low"}
    valid_confidence = {"high", "medium", "low"}

    for i, b in enumerate(benefits):
        if b.get("benefit_type") not in valid_types:
            return f"❌ Выгода {i+1}: benefit_type должен быть одним из {valid_types}"
        if b.get("magnitude") not in valid_magnitude:
            return f"❌ Выгода {i+1}: magnitude должен быть одним из {valid_magnitude}"
        if b.get("confidence") not in valid_confidence:
            return f"❌ Выгода {i+1}: confidence должен быть одним из {valid_confidence}"

    value_data = {
        "benefits": benefits,
        "investment_level": investment_level,
        "value_summary": value_summary,
        "assessed_date": str(date.today()),
    }

    state = _load_state(project_id)
    state["potential_value"] = value_data
    _save_state(state)

    type_labels = {
        "financial": "💰 Финансовая",
        "operational": "⚙️ Операционная",
        "strategic": "🎯 Стратегическая",
        "compliance": "📋 Соответствие требованиям",
    }
    magnitude_icons = {"high": "🔺 Высокий", "medium": "▶️ Средний", "low": "🔻 Низкий"}
    confidence_icons = {"high": "✅ Высокая", "medium": "🟡 Средняя", "low": "⚠️ Низкая"}
    investment_labels = {
        "low": "Низкий (без значительной разработки)",
        "medium": "Средний (умеренная разработка/закупка)",
        "high": "Высокий (трансформационный проект)",
        "unknown": "Неизвестен (требует уточнения)",
    }

    lines = [
        f"✅ Потенциальная ценность оценена — **{project_id}**",
        "",
        f"**Дата:** {date.today()}",
        f"**Уровень инвестиций:** {investment_labels.get(investment_level, investment_level)}",
        "",
    ]

    if value_summary:
        lines += [
            "## Суммарная оценка",
            "",
            value_summary,
            "",
        ]

    lines += ["## Структура выгод", ""]

    for i, b in enumerate(benefits, 1):
        lines += [
            f"### {i}. {b.get('benefit_title', '—')}",
            f"**Тип:** {type_labels.get(b.get('benefit_type', ''), b.get('benefit_type', ''))}  ",
            f"**Масштаб:** {magnitude_icons.get(b.get('magnitude', ''), b.get('magnitude', ''))}  ",
            f"**Уверенность:** {confidence_icons.get(b.get('confidence', ''), b.get('confidence', ''))}",
            "",
        ]
        if b.get("description"):
            lines.append(b["description"])
            lines.append("")
        if b.get("linked_business_needs"):
            lines.append(f"*Связано с BN:* {', '.join(b['linked_business_needs'])}")
        if b.get("linked_goals"):
            lines.append(f"*Связано с BG:* {', '.join(b['linked_goals'])}")
        lines.append("")

    # Профиль ценности
    high_mag = sum(1 for b in benefits if b.get("magnitude") == "high")
    med_mag = sum(1 for b in benefits if b.get("magnitude") == "medium")
    high_conf = sum(1 for b in benefits if b.get("confidence") == "high")

    lines += [
        "---",
        "",
        "## Профиль потенциальной ценности",
        "",
        f"- Выгод с высоким масштабом: {high_mag}/{len(benefits)}",
        f"- Выгод с высокой уверенностью: {high_conf}/{len(benefits)}",
        f"- Уровень инвестиций: {investment_level}",
        "",
    ]

    # Упрощённая оценка профиля
    if high_mag >= len(benefits) // 2 and investment_level in ("low", "medium"):
        profile = "🟢 Привлекательный профиль — высокая ценность при умеренных инвестициях"
    elif investment_level == "high" and high_mag < len(benefits) // 2:
        profile = "🔴 Требует обоснования — высокие инвестиции при неочевидной ценности"
    else:
        profile = "🟡 Средний профиль — уточните в 7.6 с детальным расчётом"

    lines += [
        profile,
        "",
        "**Следующий шаг:** `check_future_state_completeness` → `save_future_state`",
        "",
        "ℹ️ Эти данные будут доступны в **7.6** как контекст для детального value assessment.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.2.7 — Проверка полноты
# ---------------------------------------------------------------------------

@mcp.tool()
def check_future_state_completeness(
    project_id: str,
) -> str:
    """
    BABOK 6.2 — Проверить полноту анализа будущего состояния перед финализацией (ADR-066).
    По паттерну check_current_state_completeness (6.1). Не блокирует — информирует.

    Что проверяет:
    - Все ли скоупированные элементы заполнены (не черновики)?
    - Есть ли хотя бы одна цель с KPI?
    - Привязаны ли BN к целям (если данные 6.1 есть)?
    - Есть ли хотя бы одно ограничение?
    - Запущен ли gap-анализ?
    - Есть ли предварительная оценка потенциальной ценности?

    Args:
        project_id: Идентификатор проекта.

    Returns:
        Coverage report с вердиктами и рекомендациями.
    """
    logger.info(f"check_future_state_completeness: {project_id}")

    scope = _load_scope(project_id)
    state = _load_state(project_id)
    goals_data = _load_goals(project_id)

    if not scope:
        return (
            "⚠️ Скоуп анализа не определён.\n"
            "Начните с `scope_future_state` — обязательный первый шаг."
        )

    elements_in_scope = scope.get("elements_in_scope", [])
    elements_data = state.get("elements", {})
    constraints = state.get("constraints", [])
    potential_value = state.get("potential_value")
    gap_done = state.get("gap_analysis_done", False)
    goals_list = goals_data.get("goals", [])

    # Проверка элементов
    filled_elements = []
    draft_elements = []
    missing_elements = []
    for elem in elements_in_scope:
        if elem in elements_data and not elements_data[elem].get("draft", True):
            filled_elements.append(elem)
        elif elem in elements_data:
            draft_elements.append(elem)
        else:
            missing_elements.append(elem)

    # Проверка целей
    has_goals = len(goals_list) > 0
    goals_with_kpi = [g for g in goals_list if g.get("objectives")]
    goals_without_kpi = [g for g in goals_list if not g.get("objectives")]

    # Проверка привязки BN → BG (если есть 6.1)
    cs_needs = _load_json(_cs_needs_path(project_id))
    bn_coverage_issue = None
    if cs_needs:
        bn_ids = {n["id"] for n in cs_needs.get("needs", [])}
        linked_bns = set()
        for g in goals_list:
            linked_bns.update(g.get("linked_business_needs", []))
        uncovered_bns = bn_ids - linked_bns
        if uncovered_bns:
            bn_coverage_issue = f"BN не привязаны к целям: {', '.join(sorted(uncovered_bns))}"

    # Собираем предупреждения
    warnings = []
    if missing_elements:
        warnings.append(f"Незаполнены {len(missing_elements)} элементов из скоупа")
    if draft_elements:
        warnings.append(f"{len(draft_elements)} элементов в черновике")
    if not has_goals:
        warnings.append("Нет ни одной бизнес-цели — результат 6.2 не сформулирован")
    if goals_without_kpi:
        warnings.append(f"{len(goals_without_kpi)} целей без KPI (нарушение SMART)")
    if not constraints:
        warnings.append("Нет ни одного ограничения — пространство решений не ограничено")
    if not gap_done:
        warnings.append("Gap-анализ не проведён — обязательный вход для 6.4")
    if not potential_value:
        warnings.append("Потенциальная ценность не оценена — нет контекста для 7.6")
    if bn_coverage_issue:
        warnings.append(bn_coverage_issue)

    ready = len(warnings) == 0

    # Процент готовности
    total_checks = len(elements_in_scope) + 4  # элементы + цели + ограничения + gap + value
    passed = (
        len(filled_elements)
        + (1 if has_goals and not goals_without_kpi else 0)
        + (1 if constraints else 0)
        + (1 if gap_done else 0)
        + (1 if potential_value else 0)
    )
    readiness_pct = round(passed / total_checks * 100) if total_checks else 0

    lines = [
        f"# {'✅ Анализ готов к финализации' if ready else '⚠️ Анализ ещё не готов'}",
        "",
        f"**Проект:** {project_id}  ",
        f"**Готовность:** {readiness_pct}%  ",
        f"**Дата:** {date.today()}",
        "",
        "## Элементы будущего состояния",
        "",
        f"| Статус | Количество |",
        f"|--------|------------|",
        f"| ✅ Заполнены | {len(filled_elements)} |",
        f"| 📝 Черновики | {len(draft_elements)} |",
        f"| ⬜ Не заполнены | {len(missing_elements)} |",
        f"| **Итого в скоупе** | **{len(elements_in_scope)}** |",
        "",
    ]

    if missing_elements:
        lines += ["### Незаполненные элементы:"]
        for e in missing_elements:
            lines.append(f"- ⬜ `{e}` — {ELEMENT_LABELS.get(e, e)}")
        lines.append("")

    lines += [
        "## Бизнес-цели",
        "",
        f"{'✅' if goals_with_kpi else '❌'} Целей с KPI: {len(goals_with_kpi)}  ",
        f"{'⚠️' if goals_without_kpi else ''} Целей без KPI: {len(goals_without_kpi)}",
        "",
        "## Ограничения",
        "",
        f"{'✅' if constraints else '❌'} Ограничений зафиксировано: {len(constraints)}",
        "",
        "## Gap-анализ",
        "",
        f"{'✅' if gap_done else '❌'} Gap-анализ: {'проведён' if gap_done else 'НЕ проведён'}",
        "",
        "## Потенциальная ценность",
        "",
        f"{'✅' if potential_value else '❌'} Оценка потенциальной ценности: {'есть' if potential_value else 'отсутствует'}",
    ]

    if cs_needs and bn_coverage_issue:
        lines += ["", f"## BN-покрытие", "", f"⚠️ {bn_coverage_issue}"]

    if warnings:
        lines += [
            "",
            "## ⚠️ Предупреждения",
            "",
        ]
        for w in warnings:
            lines.append(f"- {w}")
        lines += [
            "",
            "> Это предупреждения, не блокировки.",
            "> Вы можете продолжить через `save_future_state`, но рекомендуется устранить пробелы.",
        ]
    else:
        lines += [
            "",
            "---",
            "",
            "✅ Все проверки пройдены. Анализ готов к финализации.",
            "",
            "**Следующий шаг:** `save_future_state` — создать финальный отчёт.",
        ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.2.8 — Финализация и создание отчёта
# ---------------------------------------------------------------------------

@mcp.tool()
def save_future_state(
    project_id: str,
    project_title: str,
    push_to_business_context: bool = False,
    analyst_notes: str = "",
) -> str:
    """
    BABOK 6.2 — Финализировать анализ будущего состояния.
    Создаёт читаемый Markdown-отчёт. Опционально передаёт данные в 7.3 (ADR-065).

    Args:
        project_id:              Идентификатор проекта.
        project_title:           Читаемое название проекта для заголовка отчёта.
        push_to_business_context: Если True — данные 6.2 будут доступны для
                                 `set_business_context(from_strategy_project_id=...)` в 7.3.
                                 Default: False.
        analyst_notes:           Заключительные комментарии аналитика.

    Returns:
        Подтверждение сохранения + ссылки на артефакты + следующие шаги.
    """
    logger.info(f"save_future_state: {project_id}")

    scope = _load_scope(project_id)
    state = _load_state(project_id)
    goals_data = _load_goals(project_id)
    gap_data = _load_gap(project_id)

    if not scope:
        return "⚠️ Скоуп анализа не найден. Начните с `scope_future_state`."

    elements_in_scope = scope.get("elements_in_scope", [])
    elements_data = state.get("elements", {})
    constraints = state.get("constraints", [])
    potential_value = state.get("potential_value")
    goals_list = goals_data.get("goals", [])

    # Предупреждения о черновиках
    draft_warnings = [
        e for e in elements_in_scope
        if e in elements_data and elements_data[e].get("draft")
    ]

    type_labels = {
        "process_improvement": "Улучшение процессов",
        "new_system": "Внедрение новой системы",
        "regulatory": "Регуляторные требования",
        "cost_reduction": "Снижение затрат",
        "market_opportunity": "Рыночная возможность",
        "other": "Другое",
    }
    depth_labels = {"light": "Лёгкий", "standard": "Стандартный", "deep": "Глубокий"}
    change_labels = {
        "new": "🆕 Новое",
        "improve": "⬆️ Улучшение",
        "eliminate": "🗑️ Устранение",
        "replace": "🔄 Замена",
    }

    # Строим Markdown-отчёт
    report_lines = [
        f"<!-- BABOK 6.2 — Define Future State | Проект: {project_id} | {date.today()} -->",
        "",
        f"# Анализ будущего состояния: {project_title}",
        "",
        f"**Проект:** {project_id}  ",
        f"**Тип инициативы:** {type_labels.get(scope.get('initiative_type', ''), scope.get('initiative_type', ''))}  ",
        f"**Глубина анализа:** {depth_labels.get(scope.get('analysis_depth', ''), scope.get('analysis_depth', ''))}  ",
        f"**Дата:** {date.today()}",
        "",
    ]

    if scope.get("known_goals"):
        report_lines += [
            "## Известные цели (от спонсора)",
            "",
            scope["known_goals"],
            "",
        ]

    report_lines += [
        "---",
        "",
        "## Будущее состояние: анализ по элементам",
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
            if elem_data.get("target_metrics"):
                report_lines += ["", "**Целевые метрики:**"]
                for k, v in elem_data["target_metrics"].items():
                    report_lines.append(f"- {k}: {v}")
            if elem_data.get("linked_business_needs"):
                report_lines.append(f"\n*Адресует BN:* {', '.join(elem_data['linked_business_needs'])}")
            if elem_data.get("notes"):
                report_lines.append(f"\n*Примечания: {elem_data['notes']}*")
        else:
            report_lines.append("*Элемент не заполнен*")
        report_lines.append("")

    # Бизнес-цели
    if goals_list:
        report_lines += [
            "---",
            "",
            "## Бизнес-цели и KPI",
            "",
        ]
        for goal in goals_list:
            smart_mark = "✅ SMART" if goal.get("smart_validated") else "⚠️ требует доработки"
            report_lines += [
                f"### {goal['id']} — {goal['goal_title']} ({smart_mark})",
                "",
                goal.get("description", "—"),
            ]
            if goal.get("objectives"):
                report_lines += ["", "**Целевые показатели:**"]
                for obj in goal["objectives"]:
                    report_lines.append(
                        f"- **{obj.get('title', '—')}**: {obj.get('baseline', '?')} → {obj.get('target', '?')} к {obj.get('deadline', '?')}"
                    )
            if goal.get("linked_business_needs"):
                report_lines.append(f"\n*Адресует BN:* {', '.join(goal['linked_business_needs'])}")
            report_lines.append("")

    # Ограничения
    if constraints:
        category_labels = {
            "budget": "Финансовый лимит",
            "time": "Временные рамки",
            "technology": "Технологические стандарты",
            "policy": "Внутренние политики",
            "resources": "Ресурсы",
            "compliance": "Регуляторные требования",
            "other": "Прочее",
        }
        report_lines += [
            "---",
            "",
            "## Ограничения",
            "",
        ]
        for c in constraints:
            status_mark = "✅" if c.get("status") == "confirmed" else "🔶 предположение"
            report_lines += [
                f"### {c['title']} ({category_labels.get(c.get('category', 'other'), c.get('category', 'other'))}) — {status_mark}",
                "",
                c.get("description", "—"),
                "",
            ]

    # Gap-анализ
    if gap_data and gap_data.get("gaps"):
        report_lines += [
            "---",
            "",
            "## Gap-анализ",
            "",
            f"*Базис текущего состояния: {'есть (6.1)' if gap_data.get('has_current_state_baseline') else 'отсутствует'}*",
            "",
        ]
        for gap in gap_data["gaps"]:
            report_lines += [
                f"### {gap['element_label']}",
                f"- **Тип изменения:** {change_labels.get(gap['change_type'], gap['change_type'])}",
                f"- **Сложность:** {gap['complexity']}",
                f"- **Gap:** {gap['gap_summary']}",
                "",
            ]

    # Потенциальная ценность
    if potential_value:
        report_lines += [
            "---",
            "",
            "## Потенциальная ценность",
            "",
        ]
        if potential_value.get("value_summary"):
            report_lines += [potential_value["value_summary"], ""]
        report_lines.append(f"**Уровень инвестиций:** {potential_value.get('investment_level', '—')}")
        report_lines.append("")
        for b in potential_value.get("benefits", []):
            report_lines.append(
                f"- **{b.get('benefit_title', '—')}** ({b.get('benefit_type', '—')}): "
                f"magnitude={b.get('magnitude', '—')}, confidence={b.get('confidence', '—')}"
            )
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
            f"⚠️ **Черновики:** элементы {draft_warnings} содержат неподтверждённые данные.",
            "",
        ]

    report_lines += [
        "---",
        "",
        f"*Анализ будущего состояния выполнен по методологии BABOK v3, задача 6.2.*  ",
        f"*Сгенерировано: {datetime.now().strftime('%d.%m.%Y %H:%M')}*",
    ]

    report_content = "\n".join(report_lines)
    save_artifact(report_content, prefix=f"6_2_future_state_{_safe(project_id)}")

    # Проброс в 7.3 (ADR-065)
    push_status = ""
    if push_to_business_context:
        goals_summary = [
            {"id": g["id"], "title": g["goal_title"]}
            for g in goals_list
        ]
        push_status = (
            "\n\n## Интеграция с 7.3\n\n"
            f"Данные 6.2 подготовлены для передачи в `set_business_context` (7.3).\n"
            f"Вызовите: `set_business_context(project_id='{project_id}', "
            f"from_strategy_project_id='{project_id}', ...)`\n"
            f"Параметр `from_strategy_project_id` предзаполнит бизнес-цели из {len(goals_list)} BG-целей.\n"
            f"(ADR-065: единый параметр для данных 6.1 + 6.2)"
        )

    result_lines = [
        f"✅ Анализ будущего состояния финализирован: **{project_id}**",
        "",
        f"**Проект:** {project_title}",
        f"**Дата:** {date.today()}",
        "",
        "## Сводка артефактов",
        "",
        f"- 📄 **Отчёт:** сохранён (`6_2_future_state_{_safe(project_id)}`)",
        f"- 📊 **Данные:** `{_safe(project_id)}_{STATE_FILENAME}`",
        f"- 📋 **Скоуп:** `{_safe(project_id)}_{SCOPE_FILENAME}`",
        f"- 🎯 **Цели:** `{_safe(project_id)}_{GOALS_FILENAME}` ({len(goals_list)} шт.)",
    ]

    if gap_data:
        result_lines.append(f"- 🔍 **Gap-анализ:** `{_safe(project_id)}_{GAP_FILENAME}` ({len(gap_data.get('gaps', []))} элементов)")

    result_lines += [
        "",
        "## Статистика",
        "",
        f"- Элементов проанализировано: {len([e for e in elements_in_scope if e in elements_data])} / {len(elements_in_scope)}",
        f"- Бизнес-целей с KPI: {len([g for g in goals_list if g.get('objectives')])}",
        f"- Ограничений: {len(constraints)}",
        f"- Gap-анализ: {'✅ проведён' if gap_data else '⚠️ не проведён'}",
        f"- Потенциальная ценность: {'✅ оценена' if potential_value else '⚠️ не оценена'}",
    ]

    if draft_warnings:
        result_lines += [
            "",
            f"⚠️ Черновики: {len(draft_warnings)} элементов — {draft_warnings}",
        ]

    result_lines += [
        push_status,
        "",
        "---",
        "",
        "**Следующие шаги:**",
        "- Используйте `{project}_gap_analysis.json` в задаче **6.4** (Define Change Strategy)",
        "- Вызовите `set_business_context` в задаче **7.3** с `from_strategy_project_id`",
        "- Бизнес-цели (BG-xxx) доступны в репозитории 5.1 для трассировки требований",
        "- Данные потенциальной ценности доступны в **7.6** как контекст для value assessment",
    ]

    return "\n".join(result_lines)


if __name__ == "__main__":
    mcp.run()
