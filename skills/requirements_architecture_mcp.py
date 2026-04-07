"""
BABOK 7.4 — Define Requirements Architecture
MCP-инструменты для организации требований по точкам зрения (viewpoints),
выявления архитектурных разрывов и фиксации архитектурного снапшота.

Инструменты:
  - analyze_requirements_architecture — автоматически строит viewpoints из типов артефактов
  - add_custom_viewpoint              — BA добавляет кастомную точку зрения (по req_ids)
  - check_architecture_gaps          — матрица покрытия + семантические разрывы (два уровня)
  - save_architecture_snapshot       — фиксирует снапшот архитектуры, генерирует Markdown

ADR-034: VIEWPOINT_MAP — константа маппинга типов → точки зрения
ADR-035: читает реестр стейкхолдеров из 4.2 ({project}_stakeholders.json) напрямую
ADR-036: кастомные viewpoints привязываются к req_ids, не к типам
ADR-037: {project}_architecture.json со снапшотами (паттерн из 5.5)
ADR-038: check_architecture_gaps — два уровня: матрица покрытия + семантические разрывы

Читает: {project}_traceability_repo.json (5.1)
        {project}_stakeholders.json (4.2) — опционально
        {project}_business_context.json (7.3) — опционально
Пишет:  {project}_architecture.json
        7_4_architecture_*.md (через save_artifact)
Выход: Architecture Document → 4.4 (коммуникация), 7.5 (варианты дизайна)

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from collections import deque
from datetime import date
from typing import Optional
from mcp.server.fastmcp import FastMCP
from skills.common import save_artifact, logger, DATA_DIR

mcp = FastMCP("BABOK_Requirements_Architecture")

REPO_FILENAME = "traceability_repo.json"
STAKEHOLDERS_FILENAME = "stakeholders.json"
CONTEXT_FILENAME = "business_context.json"
ARCHITECTURE_FILENAME = "architecture.json"

# ADR-034: маппинг типов артефактов на точки зрения
VIEWPOINT_MAP = {
    "business_process": {
        "label": "Бизнес-процессы",
        "audience": "Бизнес-заказчик, владельцы процессов",
    },
    "data_dictionary": {
        "label": "Данные и информация",
        "audience": "Архитектор данных, DBA",
    },
    "erd": {
        "label": "Данные и информация",
        "audience": "Архитектор данных, DBA",
    },
    "user_story": {
        "label": "Пользователи и взаимодействие",
        "audience": "UX-дизайнер, разработчик, тестировщик",
    },
    "use_case": {
        "label": "Пользователи и взаимодействие",
        "audience": "UX-дизайнер, разработчик, тестировщик",
    },
    "functional": {
        "label": "Функциональность",
        "audience": "Разработчик, архитектор",
    },
    "non_functional": {
        "label": "Функциональность",
        "audience": "Разработчик, архитектор",
    },
    "business_rule": {
        "label": "Бизнес-правила",
        "audience": "Бизнес-аналитик, юрист, compliance",
    },
}

# Типы которые НЕ включаются в viewpoints (они узлы графа, не артефакты)
SKIP_TYPES = {"business", "test"}


# ---------------------------------------------------------------------------
# Утилиты — пути и загрузка файлов
# ---------------------------------------------------------------------------

def _safe(project_id: str) -> str:
    return project_id.lower().replace(" ", "_")


def _repo_path(project_id: str) -> str:
    return os.path.join(DATA_DIR, f"{_safe(project_id)}_{REPO_FILENAME}")


def _stakeholders_path(project_id: str) -> str:
    return os.path.join(DATA_DIR, f"{_safe(project_id)}_{STAKEHOLDERS_FILENAME}")


def _context_path(project_id: str) -> str:
    return os.path.join(DATA_DIR, f"{_safe(project_id)}_{CONTEXT_FILENAME}")


def _architecture_path(project_id: str) -> str:
    return os.path.join(DATA_DIR, f"{_safe(project_id)}_{ARCHITECTURE_FILENAME}")


def _load_repo(project_id: str) -> dict:
    path = _repo_path(project_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"project": project_id, "requirements": [], "links": [], "history": []}


def _load_stakeholders(project_id: str) -> Optional[dict]:
    """ADR-035: читаем реестр стейкхолдеров из 4.2 напрямую. Если файла нет — возвращаем None."""
    path = _stakeholders_path(project_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _load_context(project_id: str) -> Optional[dict]:
    path = _context_path(project_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _load_architecture(project_id: str) -> dict:
    path = _architecture_path(project_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "project_id": project_id,
        "viewpoints": {},
        "views": {},
        "gaps": {"critical": [], "warning": [], "info": []},
        "snapshots": [],
        "created": str(date.today()),
        "updated": str(date.today()),
    }


def _save_architecture(data: dict) -> None:
    project_id = data["project_id"]
    path = _architecture_path(project_id)
    os.makedirs(DATA_DIR, exist_ok=True)
    data["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Архитектура сохранена: {path}")


def _find_req(repo: dict, req_id: str) -> Optional[dict]:
    for r in repo.get("requirements", []):
        if r["id"] == req_id:
            return r
    return None


# ---------------------------------------------------------------------------
# BFS для анализа семантических разрывов
# ---------------------------------------------------------------------------

def _get_linked_ids(repo: dict, req_id: str, relation_filter: Optional[set] = None) -> set:
    """
    Возвращает ID всех req, связанных с req_id в репозитории 5.1.
    Если relation_filter задан — только связи указанных типов.
    """
    links = repo.get("links", [])
    result = set()
    for link in links:
        rel = link.get("relation", "")
        if relation_filter and rel not in relation_filter:
            continue
        if link.get("from") == req_id:
            result.add(link.get("to"))
        elif link.get("to") == req_id:
            result.add(link.get("from"))
    result.discard(None)
    return result


def _build_views_from_repo(repo: dict) -> dict:
    """
    Строит словарь {viewpoint_key: [req_id, ...]} из репозитория 5.1.
    Использует VIEWPOINT_MAP для маппинга типов → точки зрения.
    """
    views: dict = {}
    for req in repo.get("requirements", []):
        req_type = req.get("type", "")
        if req_type in SKIP_TYPES:
            continue
        vp_key = req_type  # ключ viewpoint совпадает с типом артефакта
        if vp_key in VIEWPOINT_MAP:
            views.setdefault(vp_key, [])
            if req["id"] not in views[vp_key]:
                views[vp_key].append(req["id"])
    return views


# ---------------------------------------------------------------------------
# 7.4.1 — analyze_requirements_architecture
# ---------------------------------------------------------------------------

@mcp.tool()
def analyze_requirements_architecture(
    project_id: str,
) -> str:
    """
    BABOK 7.4 — Автоматически строит точки зрения (viewpoints) из типов артефактов
    в репозитории 5.1. Маппинг: ADR-034 (VIEWPOINT_MAP).

    Дополнительно:
    - Читает кастомные viewpoints из {project}_architecture.json (если есть)
    - Строит матрицу покрытия BG × точки зрения (если есть business_context из 7.3)
    - Показывает какие типы артефактов отсутствуют

    Args:
        project_id: Идентификатор проекта.

    Returns:
        Полная картина архитектуры требований: viewpoints, views, coverage matrix.
    """
    logger.info(f"analyze_requirements_architecture: project_id='{project_id}'")

    repo = _load_repo(project_id)
    all_reqs = repo.get("requirements", [])

    if not all_reqs:
        return (
            f"⚠️ Репозиторий 5.1 для проекта `{project_id}` пуст или не найден.\n\n"
            f"Создай требования через инструменты 7.1 перед работой над архитектурой."
        )

    # Строим views из репозитория
    auto_views = _build_views_from_repo(repo)

    # Загружаем существующую архитектуру (для кастомных viewpoints)
    arch = _load_architecture(project_id)
    custom_viewpoints = {
        k: v for k, v in arch.get("viewpoints", {}).items()
        if not v.get("auto", True)
    }

    # Обновляем автоматические viewpoints в архитектуре
    for vp_key, req_ids in auto_views.items():
        vp_meta = VIEWPOINT_MAP[vp_key]
        arch["viewpoints"][vp_key] = {
            "label": vp_meta["label"],
            "auto": True,
            "artifact_types": [vp_key],
            "audience": vp_meta["audience"],
        }
    arch["views"] = {**auto_views}

    # Добавляем views для кастомных viewpoints (из архитектуры)
    for vp_key, vp_data in custom_viewpoints.items():
        arch["views"][vp_key] = vp_data.get("req_ids", [])

    _save_architecture(arch)

    # Статистика
    active_reqs = [r for r in all_reqs if r.get("type", "") not in SKIP_TYPES]
    total = len(active_reqs)
    in_viewpoints = sum(len(ids) for ids in auto_views.values())
    coverage_pct = round(in_viewpoints / total * 100, 1) if total > 0 else 0.0

    # Типы которых нет в репозитории
    all_auto_types = set(VIEWPOINT_MAP.keys())
    present_types = set(auto_views.keys())
    missing_types = all_auto_types - present_types

    # Business context для coverage matrix
    ctx = _load_context(project_id)
    goals = ctx.get("business_goals", []) if ctx else []

    lines = [
        f"<!-- BABOK 7.4 — Requirements Architecture | Проект: {project_id} | {date.today()} -->",
        "",
        f"# 🏗️ Архитектура требований — {project_id}",
        "",
        f"**Дата:** {date.today()}  ",
        f"**Всего активных req:** {total}  ",
        f"**Охвачено viewpoints:** {in_viewpoints} ({coverage_pct}%)",
        "",
        "---",
        "",
        "## Точки зрения (Viewpoints)",
        "",
    ]

    # Группируем по уникальным labels (DD и ERD → один viewpoint «Данные»)
    seen_labels: dict = {}  # label → {artifact_types: [], req_ids: []}
    for vp_key, req_ids in auto_views.items():
        meta = VIEWPOINT_MAP[vp_key]
        label = meta["label"]
        if label not in seen_labels:
            seen_labels[label] = {
                "artifact_types": [],
                "req_ids": [],
                "audience": meta["audience"],
            }
        seen_labels[label]["artifact_types"].append(vp_key)
        seen_labels[label]["req_ids"].extend(req_ids)

    # Таблица viewpoints
    lines += [
        "| Точка зрения | Артефакты | Кол-во req | Аудитория |",
        "|--------------|-----------|-----------|-----------|",
    ]
    for label, data in seen_labels.items():
        types_str = ", ".join(f"`{t}`" for t in data["artifact_types"])
        req_count = len(data["req_ids"])
        icon = "✅" if req_count > 0 else "⚠️ пусто"
        lines.append(
            f"| {label} | {types_str} | {req_count} {icon} | {data['audience']} |"
        )

    # Кастомные viewpoints
    if custom_viewpoints:
        lines += [
            "",
            "## Кастомные точки зрения",
            "",
            "| ID | Название | Req | Описание |",
            "|----|----------|-----|---------|",
        ]
        for vp_key, vp_data in custom_viewpoints.items():
            req_count = len(vp_data.get("req_ids", []))
            lines.append(
                f"| `{vp_key}` | {vp_data['label']} | {req_count} | "
                f"{vp_data.get('description', '—')[:60]} |"
            )

    # Детали по каждому viewpoint
    lines += [
        "",
        "## Детали по точкам зрения",
        "",
    ]
    for label, data in seen_labels.items():
        req_ids = data["req_ids"]
        lines.append(f"### {label} ({len(req_ids)} req)")
        if req_ids:
            # Показываем до 10 req, остальные — счётчик
            preview = req_ids[:10]
            lines.append(f"{' '.join(f'`{i}`' for i in preview)}"
                         + (f" _+{len(req_ids) - 10} ещё_" if len(req_ids) > 10 else ""))
        else:
            lines.append("_Нет req этого типа_")
        lines.append("")

    # Кастомные viewpoints детали
    for vp_key, vp_data in custom_viewpoints.items():
        req_ids = vp_data.get("req_ids", [])
        lines.append(f"### {vp_data['label']} [кастомный] ({len(req_ids)} req)")
        if req_ids:
            preview = req_ids[:10]
            lines.append(f"{' '.join(f'`{i}`' for i in preview)}"
                         + (f" _+{len(req_ids) - 10} ещё_" if len(req_ids) > 10 else ""))
        lines.append("")

    # Отсутствующие типы
    if missing_types:
        lines += [
            "## ⚠️ Отсутствующие типы артефактов",
            "",
            "> Эти точки зрения пусты — артефактов данных типов нет в репозитории.",
            "",
        ]
        type_labels = {k: VIEWPOINT_MAP[k]["label"] for k in missing_types}
        for t, label in sorted(type_labels.items()):
            lines.append(f"- `{t}` → {label}")
        lines.append("")

    # Coverage matrix BG × viewpoints
    if goals:
        lines += [
            "## Coverage Matrix — Бизнес-цели × Точки зрения",
            "",
            "> Показывает: через какие точки зрения покрыта каждая бизнес-цель.",
            "",
        ]
        # Строим: для каждого req смотрим его viewpoint и связи с BG
        from collections import defaultdict
        bg_to_viewpoints: dict = defaultdict(set)

        for req in all_reqs:
            req_id = req.get("id", "")
            req_type = req.get("type", "")
            if req_type in SKIP_TYPES:
                continue
            vp_key = req_type
            if vp_key not in VIEWPOINT_MAP:
                continue
            # BFS к узлам типа 'business'
            linked = _get_linked_ids(repo, req_id)
            for linked_id in linked:
                linked_req = _find_req(repo, linked_id)
                if linked_req and linked_req.get("type") == "business":
                    bg_to_viewpoints[linked_id].add(VIEWPOINT_MAP[vp_key]["label"])

        vp_labels = sorted(set(v["label"] for v in VIEWPOINT_MAP.values()))
        header = "| BG | Название | " + " | ".join(vp_labels) + " |"
        sep = "|----|---------| " + " | ".join(["---"] * len(vp_labels)) + " |"
        lines += [header, sep]

        for g in goals:
            bg_id = g["id"]
            covered_vps = bg_to_viewpoints.get(bg_id, set())
            cells = [
                "✅" if label in covered_vps else "—"
                for label in vp_labels
            ]
            lines.append(f"| `{bg_id}` | {g['title'][:35]} | " + " | ".join(cells) + " |")
        lines.append("")

    lines += [
        "---",
        "",
        "## Следующие шаги",
        "",
    ]

    if missing_types:
        lines.append(
            f"1. Создай недостающие артефакты ({', '.join(f'`{t}`' for t in sorted(missing_types))}) "
            f"через инструменты 7.1 или обоснуй их отсутствие."
        )
    lines += [
        "2. `check_architecture_gaps` — проверь архитектурные разрывы.",
        "3. При необходимости: `add_custom_viewpoint` для регуляторных/специфических требований.",
        f"4. `save_architecture_snapshot(project_id='{project_id}', version='v1.0')` — зафиксируй.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.4.2 — add_custom_viewpoint
# ---------------------------------------------------------------------------

@mcp.tool()
def add_custom_viewpoint(
    project_id: str,
    viewpoint_id: str,
    label: str,
    req_ids_json: str,
    description: str = "",
    stakeholder_roles: str = "",
) -> str:
    """
    BABOK 7.4 — Добавляет кастомную точку зрения (viewpoint) с привязкой к req_ids.
    ADR-036: кастомные viewpoints задаются через req_ids (не через типы артефактов).

    Кастомные viewpoints нужны для специфических перспектив: Безопасность, Аудит/Compliance,
    Миграция данных, Интеграции — всё что не покрывается стандартными пятью точками зрения.

    Args:
        project_id:        Идентификатор проекта.
        viewpoint_id:      Уникальный идентификатор (lowercase, без пробелов): security, audit, migration.
        label:             Название точки зрения: «Безопасность и доступ», «Аудит и compliance».
        req_ids_json:      JSON-список ID требований: '["NFR-003", "FR-015", "BR-002"]'.
                           Все ID должны существовать в репозитории 5.1.
        description:       Описание: что представляет эта точка зрения (необязательно).
        stakeholder_roles: Для кого эта точка зрения: «Архитектор безопасности, CISO» (необязательно).

    Returns:
        Подтверждение с составом кастомного viewpoint.
    """
    logger.info(f"add_custom_viewpoint: project_id='{project_id}', viewpoint_id='{viewpoint_id}'")

    # Валидация viewpoint_id
    viewpoint_id = viewpoint_id.lower().strip()
    if not viewpoint_id or " " in viewpoint_id:
        return (
            f"❌ viewpoint_id должен быть строчным без пробелов: 'security', 'audit', 'migration'.\n"
            f"Получено: '{viewpoint_id}'"
        )

    if viewpoint_id in VIEWPOINT_MAP:
        return (
            f"❌ viewpoint_id '{viewpoint_id}' совпадает со стандартным типом артефакта.\n"
            f"Используй другое имя, например: 'security', 'audit', 'migration'."
        )

    if not label.strip():
        return "❌ label не может быть пустым — укажи название точки зрения."

    # Парсинг req_ids
    try:
        req_ids_list = json.loads(req_ids_json)
        if not isinstance(req_ids_list, list) or not req_ids_list:
            raise ValueError("Список не должен быть пустым")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Ошибка парсинга req_ids_json: {e}\n\n"
            f"Ожидается непустой JSON-список: '[\"NFR-003\", \"FR-015\"]'"
        )

    # Валидация: все req должны существовать в репозитории 5.1 (ADR-036)
    repo = _load_repo(project_id)
    repo_ids = {r["id"] for r in repo.get("requirements", [])}

    not_found = [rid for rid in req_ids_list if rid not in repo_ids]
    if not_found:
        return (
            f"❌ Следующие req_ids не найдены в репозитории 5.1 проекта `{project_id}`:\n"
            f"{', '.join(f'`{i}`' for i in not_found)}\n\n"
            f"Создай req через инструменты 7.1 или исправь ID."
        )

    # Сохраняем
    arch = _load_architecture(project_id)

    is_update = viewpoint_id in arch.get("viewpoints", {}) and not arch["viewpoints"][viewpoint_id].get("auto", True)

    arch["viewpoints"][viewpoint_id] = {
        "label": label,
        "auto": False,
        "req_ids": req_ids_list,
        "description": description,
        "stakeholder_roles": stakeholder_roles,
        "created": str(date.today()),
    }
    # Обновляем views
    arch["views"][viewpoint_id] = req_ids_list

    _save_architecture(arch)

    # Детали req
    req_details = []
    for rid in req_ids_list:
        req = _find_req(repo, rid)
        if req:
            req_details.append(f"- `{rid}` ({req.get('type', '?')}) — {req.get('title', '')}")

    action = "обновлена" if is_update else "создана"
    lines = [
        f"✅ Кастомная точка зрения **{action}**: `{viewpoint_id}`",
        "",
        f"| Поле | Значение |",
        f"|------|----------|",
        f"| ID | `{viewpoint_id}` |",
        f"| Название | {label} |",
        f"| Req | {len(req_ids_list)} |",
        f"| Аудитория | {stakeholder_roles or '—'} |",
        f"| Дата | {date.today()} |",
    ]

    if description:
        lines += [
            "",
            f"**Описание:** {description}",
        ]

    lines += [
        "",
        "**Требования в этой точке зрения:**",
        "",
    ]
    lines.extend(req_details)

    lines += [
        "",
        "---",
        "",
        "**Следующий шаг:**",
        f"`check_architecture_gaps(project_id='{project_id}')` — проверить разрывы с учётом новой точки зрения.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.4.3 — check_architecture_gaps
# ---------------------------------------------------------------------------

@mcp.tool()
def check_architecture_gaps(
    project_id: str,
) -> str:
    """
    BABOK 7.4 — Проверяет архитектуру требований на разрывы двух уровней (ADR-038).

    Уровень 1 — Матрица покрытия:
      - Стейкхолдер без представления (из реестра 4.2) → critical
      - BG без покрытия viewpoint (из business_context 7.3) → warning
      - Пустая точка зрения (viewpoint без req) → info

    Уровень 2 — Семантические разрывы (использует граф связей 5.1):
      - UC без соответствующего BP → warning
      - NFR без привязки к FR → warning
      - FR без UC или US → info
      - Стейкхолдер в реестре без ни одного req → critical

    Args:
        project_id: Идентификатор проекта.

    Returns:
        Отчёт по разрывам с severity: critical / warning / info.
        Severity не блокирует — только информирует (паттерн проекта).
    """
    logger.info(f"check_architecture_gaps: project_id='{project_id}'")

    repo = _load_repo(project_id)
    all_reqs = repo.get("requirements", [])
    reqs_by_id = {r["id"]: r for r in all_reqs}

    if not all_reqs:
        return (
            f"⚠️ Репозиторий 5.1 для проекта `{project_id}` пуст.\n\n"
            f"Сначала создай требования через инструменты 7.1."
        )

    arch = _load_architecture(project_id)

    # Строим актуальные views (авто + кастомные)
    auto_views = _build_views_from_repo(repo)
    views = {**auto_views}
    for vp_key, vp_data in arch.get("viewpoints", {}).items():
        if not vp_data.get("auto", True):
            views[vp_key] = vp_data.get("req_ids", [])

    gaps_critical = []
    gaps_warning = []
    gaps_info = []

    # ------------------------------------------------------------------
    # УРОВЕНЬ 1: Матрица покрытия
    # ------------------------------------------------------------------

    # 1a. Пустые viewpoints (info)
    for vp_key, req_ids in views.items():
        if not req_ids:
            label = arch["viewpoints"].get(vp_key, {}).get("label") or \
                    VIEWPOINT_MAP.get(vp_key, {}).get("label", vp_key)
            gaps_info.append({
                "type": "empty_viewpoint",
                "viewpoint": vp_key,
                "label": label,
                "message": f"Точка зрения «{label}» (`{vp_key}`) пуста — нет req этого типа.",
            })

    # 1b. Стейкхолдер без представления — ADR-035
    stakeholders_data = _load_stakeholders(project_id)
    if stakeholders_data is None:
        # Graceful: предупреждаем, не падаем
        gaps_info.append({
            "type": "no_stakeholder_registry",
            "message": (
                f"Реестр стейкхолдеров не найден (`{project_id}_stakeholders.json`). "
                f"Проверка покрытия стейкхолдеров пропущена. "
                f"Создай реестр через инструменты 4.2."
            ),
        })
        all_stakeholders = []
    else:
        all_stakeholders = stakeholders_data.get("stakeholders", [])

    if all_stakeholders:
        # Собираем упоминания стейкхолдеров в req (из поля stakeholders или title)
        req_stakeholder_mentions: set = set()
        for req in all_reqs:
            for sh in req.get("stakeholders", []):
                req_stakeholder_mentions.add(str(sh).lower())
            title = req.get("title", "").lower()
            req_stakeholder_mentions.update(title.split())

        for sh in all_stakeholders:
            sh_name = sh.get("name", "").lower()
            sh_id = sh.get("id", "")
            # Простая проверка: имя стейкхолдера встречается в req
            mentioned = any(
                sh_name in mention or mention in sh_name
                for mention in req_stakeholder_mentions
                if len(mention) >= 4
            )
            if not mentioned:
                gaps_critical.append({
                    "type": "stakeholder_no_view",
                    "stakeholder_id": sh_id,
                    "stakeholder_name": sh.get("name", ""),
                    "message": (
                        f"Стейкхолдер `{sh_id}` ({sh.get('name', '')}) "
                        f"не представлен ни в одном req. "
                        f"Его интересы могут быть не покрыты."
                    ),
                })

    # 1c. BG без покрытия viewpoint (warning)
    ctx = _load_context(project_id)
    goals = ctx.get("business_goals", []) if ctx else []

    if goals:
        # Для каждой BG смотрим есть ли хотя бы одна связь в граф
        goal_ids = {g["id"] for g in goals}
        bg_in_graph = {r["id"] for r in all_reqs if r.get("type") == "business"}
        for g in goals:
            if g["id"] not in bg_in_graph:
                gaps_warning.append({
                    "type": "bg_not_in_graph",
                    "bg_id": g["id"],
                    "title": g["title"],
                    "message": (
                        f"Бизнес-цель `{g['id']}` («{g['title'][:50]}») "
                        f"не представлена как узел в графе 5.1. "
                        f"Добавь BG-узел через 5.1 (`add_req`) для трассировки."
                    ),
                })

    # ------------------------------------------------------------------
    # УРОВЕНЬ 2: Семантические разрывы (использует граф 5.1)
    # ------------------------------------------------------------------

    reqs_by_type: dict = {}
    for req in all_reqs:
        t = req.get("type", "")
        if t not in SKIP_TYPES:
            reqs_by_type.setdefault(t, []).append(req)

    bp_ids = {r["id"] for r in reqs_by_type.get("business_process", [])}
    fr_ids = {r["id"] for r in reqs_by_type.get("functional", [])}
    uc_ids = {r["id"] for r in reqs_by_type.get("use_case", [])}
    us_ids = {r["id"] for r in reqs_by_type.get("user_story", [])}
    nfr_ids = {r["id"] for r in reqs_by_type.get("non_functional", [])}

    # 2a. UC без соответствующего BP (warning)
    for req in reqs_by_type.get("use_case", []):
        uc_id = req["id"]
        linked = _get_linked_ids(repo, uc_id)
        has_bp = bool(linked & bp_ids)
        if not has_bp:
            gaps_warning.append({
                "type": "uc_without_bp",
                "req_id": uc_id,
                "title": req.get("title", ""),
                "message": (
                    f"`{uc_id}` — Use Case «{req.get('title', '')[:50]}» "
                    f"не связан ни с одним Business Process. "
                    f"Пользователь взаимодействует, но процесс не описан."
                ),
            })

    # 2b. NFR без привязки к FR (warning)
    for req in reqs_by_type.get("non_functional", []):
        nfr_id = req["id"]
        linked = _get_linked_ids(repo, nfr_id)
        has_fr = bool(linked & fr_ids)
        if not has_fr:
            gaps_warning.append({
                "type": "nfr_without_fr",
                "req_id": nfr_id,
                "title": req.get("title", ""),
                "message": (
                    f"`{nfr_id}` — NFR «{req.get('title', '')[:50]}» "
                    f"не привязан ни к одному FR. "
                    f"Нефункциональное ограничение «в воздухе»."
                ),
            })

    # 2c. FR без UC или US (info)
    for req in reqs_by_type.get("functional", []):
        fr_id = req["id"]
        linked = _get_linked_ids(repo, fr_id)
        has_uc_or_us = bool(linked & (uc_ids | us_ids))
        if not has_uc_or_us:
            gaps_info.append({
                "type": "fr_without_scenario",
                "req_id": fr_id,
                "title": req.get("title", ""),
                "message": (
                    f"`{fr_id}` — FR «{req.get('title', '')[:50]}» "
                    f"не связан с UC или US. "
                    f"Функция есть, но сценарий использования не задокументирован."
                ),
            })

    # Сохраняем gaps в архитектуру
    arch["gaps"] = {
        "critical": [g["message"] for g in gaps_critical],
        "warning": [g["message"] for g in gaps_warning],
        "info": [g["message"] for g in gaps_info],
    }
    _save_architecture(arch)

    # ------------------------------------------------------------------
    # Формируем отчёт
    # ------------------------------------------------------------------

    total_gaps = len(gaps_critical) + len(gaps_warning) + len(gaps_info)
    verdict = "✅ Нет критических разрывов" if not gaps_critical else f"❌ {len(gaps_critical)} критических разрыва(ов)"

    lines = [
        f"<!-- BABOK 7.4 — Architecture Gaps | Проект: {project_id} | {date.today()} -->",
        "",
        f"# 🔍 Архитектурные разрывы — {project_id}",
        "",
        f"**Дата:** {date.today()}  ",
        f"**Вердикт:** {verdict}",
        "",
        "| Severity | Количество |",
        "|----------|-----------|",
        f"| 🔴 Critical | {len(gaps_critical)} |",
        f"| 🟡 Warning | {len(gaps_warning)} |",
        f"| ℹ️ Info | {len(gaps_info)} |",
        f"| **Всего** | **{total_gaps}** |",
        "",
        "> ⚠️ **Паттерн проекта:** severity не блокирует работу — только информирует. "
        "> Устрани critical до передачи в 7.5.",
        "",
        "---",
        "",
    ]

    if gaps_critical:
        lines += [
            "## 🔴 Critical — требуют устранения",
            "",
        ]
        for i, gap in enumerate(gaps_critical, 1):
            lines.append(f"**{i}.** {gap['message']}")
            lines.append("")

    if gaps_warning:
        lines += [
            "## 🟡 Warning — стоит рассмотреть",
            "",
        ]
        for i, gap in enumerate(gaps_warning, 1):
            lines.append(f"**{i}.** {gap['message']}")
            lines.append("")

    if gaps_info:
        lines += [
            "## ℹ️ Info — для полноты картины",
            "",
        ]
        for i, gap in enumerate(gaps_info, 1):
            lines.append(f"**{i}.** {gap['message']}")
            lines.append("")

    if total_gaps == 0:
        lines += [
            "## ✅ Разрывов не обнаружено",
            "",
            "Архитектура требований выглядит полной.",
            "Можно фиксировать снапшот и передавать в 7.5.",
            "",
        ]

    # Нотация о ложных срабатываниях
    if any(g["type"] in ("uc_without_bp", "nfr_without_fr", "fr_without_scenario")
           for g in gaps_warning + gaps_info):
        lines += [
            "---",
            "",
            "> ℹ️ **О ложных срабатываниях (уровень 2):** разрывы типа UC без BP, "
            "> NFR без FR, FR без UC зависят от полноты связей в репозитории 5.1. "
            "> Если связи добавлялись редко — часть сигналов может быть ложной. "
            "> Проверяй через `run_impact_analysis` в 5.1.",
            "",
        ]

    lines += [
        "---",
        "",
        "## Следующие шаги",
        "",
        "1. Устрани **critical** разрывы: создай недостающие req (7.1) или добавь трассировку (5.1).",
        "2. Рассмотри **warning** разрывы — особенно NFR без FR и UC без BP.",
        f"3. После устранения: `save_architecture_snapshot(project_id='{project_id}', version='v1.0')`",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.4.4 — save_architecture_snapshot
# ---------------------------------------------------------------------------

@mcp.tool()
def save_architecture_snapshot(
    project_id: str,
    version: str,
    notes: str = "",
    author: str = "",
) -> str:
    """
    BABOK 7.4 — Фиксирует снапшот архитектуры требований.
    ADR-037: снапшоты накапливаются в {project}_architecture.json — история не перезаписывается.

    Генерирует Architecture Document (Markdown) через save_artifact.
    Документ передаётся в 4.4 (коммуникация со стейкхолдерами) и 7.5 (дизайн решений).

    Args:
        project_id: Идентификатор проекта.
        version:    Версия снапшота: v1.0, v1.1, v2.0.
        notes:      Примечания к снапшоту (что изменилось, контекст).
        author:     Автор снапшота (необязательно).

    Returns:
        Architecture Document в Markdown + подтверждение сохранения.
    """
    logger.info(f"save_architecture_snapshot: project_id='{project_id}', version='{version}'")

    if not version.strip():
        return "❌ version не может быть пустым. Используй формат: v1.0, v1.1, v2.0"

    repo = _load_repo(project_id)
    all_reqs = repo.get("requirements", [])

    if not all_reqs:
        return (
            f"⚠️ Репозиторий 5.1 пуст — нечего фиксировать.\n"
            f"Сначала вызови `analyze_requirements_architecture` для анализа."
        )

    arch = _load_architecture(project_id)

    # Строим актуальные views
    auto_views = _build_views_from_repo(repo)
    all_views = {**auto_views}
    custom_viewpoints = {}
    for vp_key, vp_data in arch.get("viewpoints", {}).items():
        if not vp_data.get("auto", True):
            all_views[vp_key] = vp_data.get("req_ids", [])
            custom_viewpoints[vp_key] = vp_data

    # Обновляем arch перед снапшотом
    for vp_key, req_ids in auto_views.items():
        vp_meta = VIEWPOINT_MAP[vp_key]
        arch["viewpoints"][vp_key] = {
            "label": vp_meta["label"],
            "auto": True,
            "artifact_types": [vp_key],
            "audience": vp_meta["audience"],
        }
    arch["views"] = all_views

    # Сводная статистика для снапшота
    total_reqs = len([r for r in all_reqs if r.get("type", "") not in SKIP_TYPES])
    viewpoints_count = len(all_views)
    custom_count = len(custom_viewpoints)
    gaps = arch.get("gaps", {"critical": [], "warning": [], "info": []})
    summary = {
        "total_reqs": total_reqs,
        "viewpoints_count": viewpoints_count,
        "custom_viewpoints_count": custom_count,
        "gaps_critical": len(gaps.get("critical", [])),
        "gaps_warning": len(gaps.get("warning", [])),
        "gaps_info": len(gaps.get("info", [])),
    }

    snapshot = {
        "version": version,
        "date": str(date.today()),
        "author": author or "",
        "notes": notes or "",
        "summary": summary,
    }

    # Проверяем дублирование версии
    existing_versions = [s["version"] for s in arch.get("snapshots", [])]
    if version in existing_versions:
        return (
            f"⚠️ Версия `{version}` уже существует в снапшотах проекта `{project_id}`.\n"
            f"Существующие версии: {', '.join(existing_versions)}\n"
            f"Используй следующую версию, например: "
            f"`{version.replace('v', 'v').split('.')[0]}.{int(version.split('.')[-1]) + 1}`"
        )

    arch["snapshots"].append(snapshot)
    _save_architecture(arch)

    # ------------------------------------------------------------------
    # Генерируем Architecture Document (Markdown)
    # ------------------------------------------------------------------

    ctx = _load_context(project_id)
    goals = ctx.get("business_goals", []) if ctx else []

    # Группируем viewpoints по уникальным labels
    seen_labels: dict = {}
    for vp_key, req_ids in auto_views.items():
        meta = VIEWPOINT_MAP[vp_key]
        label = meta["label"]
        if label not in seen_labels:
            seen_labels[label] = {
                "artifact_types": [],
                "req_ids": [],
                "audience": meta["audience"],
            }
        seen_labels[label]["artifact_types"].append(vp_key)
        seen_labels[label]["req_ids"].extend(req_ids)

    doc_lines = [
        f"<!-- BABOK 7.4 — Architecture Document | Проект: {project_id} | {version} | {date.today()} -->",
        "",
        f"# 📐 Архитектурный документ требований",
        "",
        f"| Поле | Значение |",
        f"|------|----------|",
        f"| Проект | {project_id} |",
        f"| Версия | {version} |",
        f"| Дата | {date.today()} |",
        f"| Автор | {author or '—'} |",
        f"| Всего req | {total_reqs} |",
        f"| Точек зрения | {viewpoints_count} ({custom_count} кастомных) |",
        "",
    ]

    if notes:
        doc_lines += [
            f"**Примечания:** {notes}",
            "",
        ]

    doc_lines += [
        "---",
        "",
        "## Точки зрения (Viewpoints)",
        "",
        "| Точка зрения | Артефакты | Кол-во req | Аудитория |",
        "|--------------|-----------|-----------|-----------|",
    ]

    for label, data in seen_labels.items():
        types_str = ", ".join(f"`{t}`" for t in data["artifact_types"])
        req_count = len(data["req_ids"])
        doc_lines.append(
            f"| {label} | {types_str} | {req_count} | {data['audience']} |"
        )

    for vp_key, vp_data in custom_viewpoints.items():
        req_count = len(vp_data.get("req_ids", []))
        doc_lines.append(
            f"| {vp_data['label']} _(кастомный)_ | req_ids | {req_count} | "
            f"{vp_data.get('stakeholder_roles', '—')} |"
        )

    doc_lines.append("")

    # Детали по viewpoints
    doc_lines += [
        "## Детали по точкам зрения",
        "",
    ]

    for label, data in seen_labels.items():
        req_ids = data["req_ids"]
        doc_lines.append(f"### {label} ({len(req_ids)} req)")
        if req_ids:
            # Таблица req
            doc_lines += [
                "| ID | Тип | Название |",
                "|----|-----|---------|",
            ]
            for rid in req_ids[:20]:
                req = _find_req(repo, rid)
                if req:
                    doc_lines.append(
                        f"| `{rid}` | {req.get('type', '?')} | {req.get('title', '')[:60]} |"
                    )
            if len(req_ids) > 20:
                doc_lines.append(f"| _+{len(req_ids) - 20} ещё_ | | |")
        else:
            doc_lines.append("_Нет req_")
        doc_lines.append("")

    for vp_key, vp_data in custom_viewpoints.items():
        req_ids = vp_data.get("req_ids", [])
        doc_lines.append(f"### {vp_data['label']} [кастомный] ({len(req_ids)} req)")
        if vp_data.get("description"):
            doc_lines.append(f"_{vp_data['description']}_")
            doc_lines.append("")
        if req_ids:
            doc_lines += [
                "| ID | Тип | Название |",
                "|----|-----|---------|",
            ]
            for rid in req_ids[:20]:
                req = _find_req(repo, rid)
                if req:
                    doc_lines.append(
                        f"| `{rid}` | {req.get('type', '?')} | {req.get('title', '')[:60]} |"
                    )
        doc_lines.append("")

    # Состояние разрывов
    doc_lines += [
        "## Архитектурные разрывы",
        "",
        f"| Severity | Количество |",
        f"|----------|-----------|",
        f"| 🔴 Critical | {len(gaps.get('critical', []))} |",
        f"| 🟡 Warning | {len(gaps.get('warning', []))} |",
        f"| ℹ️ Info | {len(gaps.get('info', []))} |",
        "",
    ]

    if gaps.get("critical"):
        doc_lines.append("**Critical разрывы:**")
        for g in gaps["critical"]:
            doc_lines.append(f"- {g}")
        doc_lines.append("")

    # История снапшотов
    all_snapshots = arch.get("snapshots", [])
    if len(all_snapshots) > 1:
        doc_lines += [
            "## История снапшотов",
            "",
            "| Версия | Дата | Автор | Примечания |",
            "|--------|------|-------|-----------|",
        ]
        for s in all_snapshots:
            doc_lines.append(
                f"| {s['version']} | {s['date']} | {s.get('author', '—')} | "
                f"{s.get('notes', '—')[:60]} |"
            )
        doc_lines.append("")

    doc_lines += [
        "---",
        "",
        "## Передача артефакта",
        "",
        "| Направление | Назначение |",
        "|-------------|-----------|",
        "| → **4.4** Communicate | Коммуникация архитектуры со стейкхолдерами |",
        "| → **7.5** Design Options | Основа для определения вариантов дизайна решения |",
    ]

    content = "\n".join(doc_lines)

    # Сохраняем через save_artifact
    save_artifact(content, prefix="7_4_architecture")

    # Ответ пользователю
    result_lines = [
        f"✅ Снапшот **{version}** зафиксирован — **{project_id}**",
        "",
        f"| Поле | Значение |",
        f"|------|----------|",
        f"| Версия | {version} |",
        f"| Дата | {date.today()} |",
        f"| Req охвачено | {total_reqs} |",
        f"| Viewpoints | {viewpoints_count} |",
        f"| 🔴 Critical gaps | {summary['gaps_critical']} |",
        f"| 🟡 Warning gaps | {summary['gaps_warning']} |",
        "",
    ]

    if notes:
        result_lines += [f"**Примечания:** {notes}", ""]

    result_lines += [
        "Architecture Document сохранён через `save_artifact` (префикс: `7_4_architecture`).",
        "",
        "---",
        "",
        "**Следующие шаги:**",
        f"- → **4.4** `prepare_communication_package` — коммуникация архитектуры со стейкхолдерами",
        f"- → **7.5** Используй Architecture Document как входной артефакт для Design Options",
    ]

    if summary["gaps_critical"] > 0:
        result_lines += [
            "",
            f"⚠️ **{summary['gaps_critical']} critical разрыва(ов) не устранены.** "
            f"Рекомендуется устранить перед передачей в 7.5.",
        ]

    return "\n".join(result_lines)


if __name__ == "__main__":
    mcp.run()
