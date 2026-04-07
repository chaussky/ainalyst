"""
BABOK 5.2 — Maintain Requirements
MCP-инструменты для поддержания актуальности требований и их атрибутов.

Инструменты:
  - update_requirement           — обновить атрибуты требования (статус, версия, приоритет...)
  - deprecate_requirements       — пометить требования как устаревшие или заменённые
  - check_requirements_health    — аудит здоровья реестра: волатильность, заброшенные, давно не обновлялись
  - find_reusable_requirements   — найти кандидатов на повторное использование

Хранение: тот же JSON-репозиторий что и 5.1 ({project}_traceability_repo.json).
История каждого изменения пишется в repo["history"].

Хуки: после каждого обновления вызывается _export_hook().
До подключения integrations/confluence_mcp.py возвращает local_only.

Интеграция:
  Вход: результаты 4.3 (status→confirmed), 5.3 (priority), 5.4 (CR-решения), 5.5 (status→approved)
  Выход: актуальный реестр для 5.3, 5.5, 6.x; хук → Confluence

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date, datetime
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import save_artifact, logger, DATA_DIR

mcp = FastMCP("BABOK_Requirements_Maintain")

REPO_FILENAME = "traceability_repo.json"

# Порог волатильности — minor-версия выше этого значения → предупреждение
VOLATILITY_WARNING_THRESHOLD = 3   # версия 1.3+
VOLATILITY_CRITICAL_THRESHOLD = 4  # версия 1.4+

# Порог «заброшенности» в днях без обновления
STALE_DAYS_WARNING = 30
STALE_DAYS_CRITICAL = 60


# ---------------------------------------------------------------------------
# Утилиты — общие с 5.1 (дублируем чтобы не создавать циклических зависимостей)
# ---------------------------------------------------------------------------

def _repo_path(project_name: str) -> str:
    safe_name = project_name.lower().replace(" ", "_")
    return os.path.join(DATA_DIR, f"{safe_name}_{REPO_FILENAME}")


def _load_repo(project_name: str) -> dict:
    path = _repo_path(project_name)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "project": project_name,
        "formality_level": "Standard",
        "created": str(date.today()),
        "updated": str(date.today()),
        "requirements": [],
        "links": [],
        "history": []
    }


def _save_repo(repo: dict) -> str:
    path = _repo_path(repo["project"])
    os.makedirs(DATA_DIR, exist_ok=True)
    repo["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)
    logger.info(f"Репозиторий обновлён (5.2): {path}")
    return path


def _find_req(repo: dict, req_id: str) -> Optional[dict]:
    for r in repo["requirements"]:
        if r["id"] == req_id:
            return r
    return None


def _version_to_float(version: str) -> float:
    """Конвертирует '1.3' → 1.3 для сравнения."""
    try:
        return float(version)
    except (ValueError, TypeError):
        return 1.0


def _minor_version(version: str) -> int:
    """Возвращает minor-часть версии: '1.3' → 3."""
    try:
        parts = str(version).split(".")
        return int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return 0


def _days_since(date_str: str) -> int:
    """Количество дней с указанной даты."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return (date.today() - d).days
    except (ValueError, TypeError):
        return 0


# ---------------------------------------------------------------------------
# Хук для внешних хранилищ
# ---------------------------------------------------------------------------

def _export_hook(artifact_type: str, content: str, metadata: dict) -> dict:
    """
    Хук экспорта — вызывается после каждого значимого обновления в 5.2.

    Если заданы переменные окружения CONFLUENCE_URL + CONFLUENCE_API_TOKEN —
    автоматически синхронизирует артефакт с Confluence через confluence_mcp.
    Иначе возвращает local_only.

    Args:
        artifact_type: тип артефакта ('requirement_update', 'health_report', 'reuse_list')
        content:       Markdown-содержимое артефакта
        metadata:      dict с project_name, req_ids, operation и др.

    Returns:
        {"status": "synced", "url": "..."} или {"status": "local_only", "note": "..."}
    """
    # Проверяем наличие Confluence конфига
    if not os.environ.get("CONFLUENCE_URL") or not os.environ.get("CONFLUENCE_API_TOKEN"):
        return {
            "status": "local_only",
            "note": (
                "Для синхронизации с Confluence задай переменные окружения: "
                "CONFLUENCE_URL, CONFLUENCE_API_TOKEN, CONFLUENCE_SPACE_KEY. "
                "Подробнее: skills/integrations/confluence_mcp.py"
            )
        }

    try:
        from skills.integrations.confluence_mcp import export_artifact_to_confluence

        project_name = metadata.get("project_name", "BA Project")
        type_labels = {
            "requirement_update": "Обновление требования",
            "deprecation": "Устаревшие требования",
            "health_report": "Аудит здоровья требований",
            "reuse_list": "Кандидаты на повторное использование",
        }
        label = type_labels.get(artifact_type, artifact_type)
        page_title = f"{project_name} — {label} ({date.today()})"

        result = export_artifact_to_confluence(
            content_markdown=content,
            page_title=page_title,
        )
        logger.info(f"[export_hook] Confluence: {result.get('status')}")
        return result

    except ImportError:
        return {"status": "local_only", "note": "Модуль integrations/confluence_mcp.py недоступен"}
    except Exception as e:
        logger.warning(f"[export_hook] Ошибка Confluence: {e}")
        return {"status": "local_only", "note": f"Ошибка синхронизации: {e}"}


# ---------------------------------------------------------------------------
# 5.2.1 — Обновление требования или его атрибутов
# ---------------------------------------------------------------------------

@mcp.tool()
def update_requirement(
    project_name: str,
    req_id: str,
    change_reason: str,
    new_status: str = "",
    new_version: str = "",
    new_priority: str = "",
    new_owner: str = "",
    new_stability: str = "",
    new_title: str = "",
    reuse_candidate: str = "",
    reuse_scope: str = "",
    complexity: str = "",
    note: str = "",
) -> str:
    """
    BABOK 5.2 — Обновляет атрибуты требования. Пишет историю изменений.

    Правило версионности:
      Minor (1.0→1.1): уточнение формулировки, изменение критериев приёмки
      Major (1.0→2.0): изменение сути, слияние, разделение требований
      Без изменения версии: смена статуса, приоритета, owner (содержание не менялось)

    Args:
        project_name:    Название проекта.
        req_id:          ID требования: BR-001, FR-007 и т.д.
        change_reason:   Причина изменения — обязательно. Пишется в историю.
        new_status:      Новый статус. Допустимые значения:
                         draft | confirmed | approved | implemented |
                         on_hold | deprecated | superseded | retired
                         Пустая строка — не менять.
        new_version:     Новая версия в формате major.minor (1.1, 2.0).
                         Пустая строка — не менять.
        new_priority:    High | Medium | Low. Пустая строка — не менять.
        new_owner:       Имя/роль владельца. Пустая строка — не менять.
        new_stability:   Stable | Volatile | Unknown. Пустая строка — не менять.
        new_title:       Новая формулировка требования. Пустая строка — не менять.
        reuse_candidate: "true" | "false". Пустая строка — не менять.
        reuse_scope:     initiative | program | division | enterprise. Пустая строка — не менять.
        complexity:      Low | Medium | High. Пустая строка — не менять.
        note:            Дополнительная заметка BA (опционально).

    Returns:
        Подтверждение обновления с историей изменений требования.
    """
    logger.info(f"update_requirement: {req_id} в проекте '{project_name}'")

    repo = _load_repo(project_name)
    req = _find_req(repo, req_id)

    if not req:
        return (
            f"❌ Требование `{req_id}` не найдено в репозитории проекта `{project_name}`.\n"
            f"Проверьте ID или добавьте требование через `init_traceability_repo` (5.1)."
        )

    changes = []
    old_values = {}

    def _apply(attr: str, new_val: str, display_name: str):
        if new_val:
            old_values[attr] = req.get(attr, "—")
            req[attr] = new_val
            changes.append(f"- **{display_name}:** `{old_values[attr]}` → `{new_val}`")

    _apply("status", new_status, "Статус")
    _apply("version", new_version, "Версия")
    _apply("priority", new_priority, "Приоритет")
    _apply("owner", new_owner, "Владелец")
    _apply("stability", new_stability, "Стабильность")
    _apply("title", new_title, "Формулировка")
    _apply("complexity", complexity, "Сложность")
    _apply("reuse_scope", reuse_scope, "Scope повторного использования")

    if reuse_candidate:
        old_val = req.get("reuse_candidate", "—")
        val = reuse_candidate.lower() == "true"
        req["reuse_candidate"] = val
        changes.append(f"- **Кандидат на reuse:** `{old_val}` → `{val}`")

    if not changes:
        return f"ℹ️ Нет изменений для требования `{req_id}`. Укажите хотя бы один атрибут для обновления."

    req["last_reviewed"] = str(date.today())

    # Автоматический пересчёт stability по волатильности
    if not new_stability and new_version:
        minor = _minor_version(req.get("version", "1.0"))
        if minor >= VOLATILITY_CRITICAL_THRESHOLD:
            req["stability"] = "Volatile"
            changes.append(f"- **Стабильность (авто):** пересчитана → `Volatile` (версия {req['version']})")
        elif minor >= VOLATILITY_WARNING_THRESHOLD:
            if req.get("stability") != "Volatile":
                req["stability"] = "Volatile"
                changes.append(f"- **Стабильность (авто):** пересчитана → `Volatile` (версия {req['version']})")

    # Пишем в историю
    history_entry = {
        "action": "requirement_updated",
        "req_id": req_id,
        "changes": {k: {"from": old_values[k], "to": req[k]} for k in old_values},
        "reason": change_reason,
        "note": note,
        "date": str(date.today()),
    }
    repo["history"].append(history_entry)

    _save_repo(repo)

    # Проверка волатильности — предупреждение
    volatility_warning = ""
    current_minor = _minor_version(req.get("version", "1.0"))
    if current_minor >= VOLATILITY_CRITICAL_THRESHOLD:
        volatility_warning = (
            f"\n\n🔴 **Высокая волатильность:** версия `{req.get('version')}` — "
            f"требование нестабильно. Рекомендуется обсудить первопричину со стейкхолдером."
        )
    elif current_minor >= VOLATILITY_WARNING_THRESHOLD:
        volatility_warning = (
            f"\n\n⚠️ **Внимание:** версия `{req.get('version')}` — "
            f"требование начинает проявлять признаки нестабильности."
        )

    lines = [
        f"✅ Требование `{req_id}` обновлено",
        "",
        f"**Проект:** {project_name}  ",
        f"**Причина изменения:** {change_reason}  ",
        f"**Дата:** {date.today()}",
        "",
        "### Изменения:",
        "",
    ] + changes

    if note:
        lines += ["", f"**Заметка BA:** {note}"]

    lines += [
        "",
        "### Текущее состояние требования:",
        "",
        f"| Атрибут | Значение |",
        f"|---------|----------|",
        f"| ID | `{req.get('id')}` |",
        f"| Тип | {req.get('type', '—')} |",
        f"| Формулировка | {req.get('title', '—')} |",
        f"| Статус | {req.get('status', '—')} |",
        f"| Версия | {req.get('version', '—')} |",
        f"| Приоритет | {req.get('priority', '—')} |",
        f"| Владелец | {req.get('owner', '—')} |",
        f"| Стабильность | {req.get('stability', '—')} |",
        f"| Reuse кандидат | {req.get('reuse_candidate', '—')} |",
        f"| Последняя проверка | {req.get('last_reviewed', '—')} |",
    ]

    content = "\n".join(lines) + volatility_warning

    # Хук экспорта
    hook_result = _export_hook(
        "requirement_update",
        content,
        {"project_name": project_name, "req_id": req_id, "operation": "update"}
    )
    if hook_result.get("status") == "synced":
        content += f"\n\n🔗 Синхронизировано: {hook_result.get('url', '')}"
    else:
        content += f"\n\n💾 Сохранено локально. {hook_result.get('note', '')}"

    save_artifact(content, prefix="5_2_requirement_update")
    return content


# ---------------------------------------------------------------------------
# 5.2.2 — Пометить требования как устаревшие / замененные
# ---------------------------------------------------------------------------

@mcp.tool()
def deprecate_requirements(
    project_name: str,
    req_ids_json: str,
    final_status: Literal["deprecated", "superseded", "retired"],
    reason: str,
    superseded_by: str = "",
) -> str:
    """
    BABOK 5.2 — Помечает требования как устаревшие, заменённые или выведенные из эксплуатации.

    Требования НЕ удаляются — только помечаются. История сохраняется для аудита и трассировки.
    После deprecation рекомендуется проверить активные связи через check_coverage (5.1).

    Args:
        project_name:   Название проекта.
        req_ids_json:   JSON-список ID требований: ["FR-007", "FR-008"]
        final_status:   deprecated  — устарело, нет замены
                        superseded  — заменено другим требованием
                        retired     — проект завершён, требование в архив
        reason:         Причина (обязательно). Пишется в историю.
        superseded_by:  ID нового требования (только для superseded). Например: "FR-012"

    Returns:
        Отчёт о помеченных требованиях + предупреждение об активных связях.
    """
    logger.info(f"deprecate_requirements: статус={final_status}, проект='{project_name}'")

    try:
        req_ids = json.loads(req_ids_json)
    except json.JSONDecodeError as e:
        return f"❌ Ошибка парсинга req_ids_json: {e}"

    repo = _load_repo(project_name)

    if final_status == "superseded" and not superseded_by:
        return "❌ Для статуса `superseded` необходимо указать `superseded_by` — ID нового требования."

    processed = []
    not_found = []

    for req_id in req_ids:
        req = _find_req(repo, req_id)
        if not req:
            not_found.append(req_id)
            continue

        old_status = req.get("status", "—")
        req["status"] = final_status
        req["last_reviewed"] = str(date.today())
        if superseded_by:
            req["superseded_by"] = superseded_by

        repo["history"].append({
            "action": f"requirement_{final_status}",
            "req_id": req_id,
            "changes": {"status": {"from": old_status, "to": final_status}},
            "reason": reason,
            "superseded_by": superseded_by or None,
            "date": str(date.today()),
        })
        processed.append({"id": req_id, "title": req.get("title", "—"), "old_status": old_status})

    _save_repo(repo)

    # Проверить активные связи для deprecated требований
    active_links_warning = []
    for item in processed:
        req_id = item["id"]
        active = [
            lnk for lnk in repo["links"]
            if (lnk["from"] == req_id or lnk["to"] == req_id)
        ]
        if active:
            active_links_warning.append(f"`{req_id}` имеет **{len(active)}** активных связей в трассировке")

    status_labels = {
        "deprecated": "🗄️ Deprecated (устарело)",
        "superseded": "🔄 Superseded (заменено)",
        "retired": "📦 Retired (архив)",
    }

    lines = [
        f"<!-- BABOK 5.2 — Deprecation | Проект: {project_name} | {date.today()} -->",
        "",
        f"# {status_labels[final_status]}",
        "",
        f"**Проект:** {project_name}  ",
        f"**Причина:** {reason}  ",
        f"**Дата:** {date.today()}",
    ]

    if superseded_by:
        lines.append(f"**Заменено на:** `{superseded_by}`  ")

    lines += [
        "",
        f"## Обработано: {len(processed)} требований",
        "",
        "| ID | Название | Был статус | Новый статус |",
        "|----|----------|-----------|--------------|",
    ]

    for item in processed:
        lines.append(
            f"| `{item['id']}` | {item['title']} | {item['old_status']} | **{final_status}** |"
        )

    if not_found:
        lines += [
            "",
            f"⚠️ Не найдено в репозитории: {', '.join(f'`{i}`' for i in not_found)}",
        ]

    if active_links_warning:
        lines += [
            "",
            "## ⚠️ Внимание: активные связи трассировки",
            "",
            "Следующие требования имеют активные связи — рекомендуется проверить через `check_coverage` (5.1):",
            "",
        ]
        for w in active_links_warning:
            lines.append(f"- {w}")
        lines += [
            "",
            "> Связи могут указывать на тесты, компоненты или другие требования которые",
            "> всё ещё ссылаются на deprecated требование.",
        ]

    lines += [
        "",
        "---",
        "**Следующий шаг:** запустить `check_coverage` (5.1) для проверки осиротевших связей.",
    ]

    content = "\n".join(lines)

    hook_result = _export_hook(
        "deprecation",
        content,
        {"project_name": project_name, "req_ids": req_ids, "final_status": final_status}
    )
    if hook_result.get("status") != "synced":
        content += f"\n\n💾 Сохранено локально. {hook_result.get('note', '')}"

    save_artifact(content, prefix="5_2_deprecation")
    return content


# ---------------------------------------------------------------------------
# 5.2.3 — Аудит здоровья реестра требований
# ---------------------------------------------------------------------------

@mcp.tool()
def check_requirements_health(
    project_name: str,
    filter_type: str = "",
    filter_status: str = "",
) -> str:
    """
    BABOK 5.2 — Аудит здоровья реестра требований.

    Что ищет:
      🔴 Высокая волатильность (версия 1.4+) — требование нестабильно
      🟡 Средняя волатильность (версия 1.2-1.3) — стоит проверить
      🟡 Давно не обновлялись (>60 дней) — возможно устарели
      🟡 Долго в draft (>30 дней) — подтвердить или заморозить
      🟡 Нет owner — некому отвечать за актуальность
      🟢 Здоровые требования — всё в порядке

    Args:
        project_name:   Название проекта.
        filter_type:    Фильтр по типу: business | stakeholder | solution | transition
                        Пустая строка — все.
        filter_status:  Фильтр по статусу. Пустая строка — все активные
                        (исключает deprecated, superseded, retired).

    Returns:
        Отчёт о состоянии реестра с рекомендациями.
    """
    logger.info(f"check_requirements_health: '{project_name}'")

    repo = _load_repo(project_name)
    requirements = repo["requirements"]

    # По умолчанию — только активные (не архивные)
    archive_statuses = {"deprecated", "superseded", "retired"}
    if not filter_status:
        requirements = [r for r in requirements if r.get("status") not in archive_statuses]
    else:
        requirements = [r for r in requirements if r.get("status") == filter_status]

    if filter_type:
        requirements = [r for r in requirements if r.get("type") == filter_type]

    if not requirements:
        return f"ℹ️ Активных требований не найдено в репозитории `{project_name}`."

    critical = []    # 🔴
    warnings = []    # 🟡
    healthy = []     # 🟢

    for req in requirements:
        req_id = req.get("id", "?")
        issues = []

        # Волатильность
        minor = _minor_version(req.get("version", "1.0"))
        if minor >= VOLATILITY_CRITICAL_THRESHOLD:
            issues.append(f"🔴 Высокая волатильность (v{req.get('version')})")
        elif minor >= VOLATILITY_WARNING_THRESHOLD:
            issues.append(f"🟡 Средняя волатильность (v{req.get('version')})")

        # Давно не обновлялось
        last_reviewed = req.get("last_reviewed") or req.get("added", "")
        if last_reviewed:
            days = _days_since(last_reviewed)
            if days > STALE_DAYS_CRITICAL:
                issues.append(f"🟡 Не обновлялось {days} дней")
            elif days > STALE_DAYS_WARNING:
                issues.append(f"🟡 Не обновлялось {days} дней — стоит проверить")

        # Долго в draft
        if req.get("status") == "draft":
            added = req.get("added", "")
            if added:
                days_draft = _days_since(added)
                if days_draft > STALE_DAYS_WARNING:
                    issues.append(f"🟡 В статусе draft уже {days_draft} дней")

        # Нет owner
        if not req.get("owner"):
            issues.append("🟡 Нет владельца (owner)")

        req_info = {
            "id": req_id,
            "title": req.get("title", "—"),
            "type": req.get("type", "—"),
            "status": req.get("status", "—"),
            "version": req.get("version", "1.0"),
            "owner": req.get("owner", "—"),
            "issues": issues,
        }

        if any("🔴" in i for i in issues):
            critical.append(req_info)
        elif issues:
            warnings.append(req_info)
        else:
            healthy.append(req_info)

    total = len(requirements)
    health_pct = round(len(healthy) / total * 100) if total else 0

    lines = [
        f"<!-- BABOK 5.2 — Аудит здоровья | Проект: {project_name} | {date.today()} -->",
        "",
        f"# 🏥 Аудит здоровья реестра требований",
        "",
        f"**Проект:** {project_name}  ",
        f"**Фильтр:** тип={filter_type or 'все'}, статус={filter_status or 'активные'}  ",
        f"**Дата:** {date.today()}",
        "",
        "## Сводка",
        "",
        "| Статус | Кол-во | % |",
        "|--------|--------|---|",
        f"| 🟢 Здоровые | {len(healthy)} | {health_pct}% |",
        f"| 🟡 Требуют внимания | {len(warnings)} | {round(len(warnings)/total*100) if total else 0}% |",
        f"| 🔴 Критические | {len(critical)} | {round(len(critical)/total*100) if total else 0}% |",
        f"| **Всего активных** | **{total}** | 100% |",
        "",
    ]

    if critical:
        lines += [
            "## 🔴 Критические проблемы",
            "",
            "| ID | Тип | Название | v | Статус | Проблема |",
            "|----|-----|----------|---|--------|----------|",
        ]
        for r in critical:
            problem = "; ".join(r["issues"])
            lines.append(
                f"| `{r['id']}` | {r['type']} | {r['title']} | {r['version']} | {r['status']} | {problem} |"
            )
        lines += [
            "",
            "> **Рекомендация:** обсудить первопричину нестабильности со стейкхолдером.",
            "> Высокая волатильность часто указывает на проблему выявления (4.2), а не содержания.",
            "",
        ]

    if warnings:
        lines += [
            "## 🟡 Требуют внимания",
            "",
            "| ID | Тип | Название | v | Владелец | Проблема |",
            "|----|-----|----------|---|----------|----------|",
        ]
        for r in warnings:
            problem = "; ".join(r["issues"])
            lines.append(
                f"| `{r['id']}` | {r['type']} | {r['title']} | {r['version']} | {r['owner']} | {problem} |"
            )
        lines.append("")

    if healthy:
        lines += [
            "## 🟢 Здоровые требования",
            "",
            f"**{len(healthy)} требований** в хорошем состоянии — актуальны, имеют владельца, стабильны.",
            "",
        ]

    lines += [
        "---",
        "",
        "## Рекомендуемые действия",
        "",
    ]

    if critical:
        lines.append(
            f"1. 🔴 **{len(critical)} критических** — обсудить волатильность, "
            f"обновить через `update_requirement` или `deprecate_requirements`."
        )
    if warnings:
        no_owner = sum(1 for r in warnings if "владельца" in " ".join(r["issues"]))
        stale = sum(1 for r in warnings if "дней" in " ".join(r["issues"]))
        if no_owner:
            lines.append(f"2. 🟡 **{no_owner} без владельца** — назначить owner через `update_requirement`.")
        if stale:
            lines.append(f"3. 🟡 **{stale} давно не обновлялись** — проверить актуальность у стейкхолдера.")
    if not critical and not warnings:
        lines.append("✅ Реестр в хорошем состоянии. Готов к приоритизации (5.3) и утверждению (5.5).")

    content = "\n".join(lines)

    hook_result = _export_hook(
        "health_report",
        content,
        {"project_name": project_name, "health_pct": health_pct}
    )
    if hook_result.get("status") != "synced":
        content += f"\n\n💾 Сохранено локально. {hook_result.get('note', '')}"

    save_artifact(content, prefix="5_2_health_check")
    return content


# ---------------------------------------------------------------------------
# 5.2.4 — Поиск кандидатов на повторное использование
# ---------------------------------------------------------------------------

@mcp.tool()
def find_reusable_requirements(
    project_name: str,
    search_query: str = "",
    filter_type: str = "",
    min_reuse_scope: Literal["initiative", "program", "division", "enterprise"] = "initiative",
) -> str:
    """
    BABOK 5.2 — Находит требования — кандидатов на повторное использование.

    Критерии хорошего кандидата (автоматически проверяются):
      ✅ Флаг reuse_candidate = True
      ✅ Статус approved или implemented (проверено практикой)
      ✅ Низкая волатильность (версия ≤ 1.1)
      ✅ Тип business или stakeholder (высокий уровень абстракции)

    Args:
        project_name:     Название проекта.
        search_query:     Поисковый запрос по тексту требования (опционально).
        filter_type:      Фильтр по типу: business | stakeholder | solution | transition
        min_reuse_scope:  Минимальный уровень scope: initiative | program | division | enterprise

    Returns:
        Список кандидатов с оценкой пригодности для повторного использования.
    """
    logger.info(f"find_reusable_requirements: '{project_name}', query='{search_query}'")

    repo = _load_repo(project_name)
    scope_order = ["initiative", "program", "division", "enterprise"]
    min_scope_idx = scope_order.index(min_reuse_scope)

    candidates = []
    others = []  # требования без флага reuse, но потенциально подходящие

    for req in repo["requirements"]:
        # Пропускаем архивные
        if req.get("status") in {"deprecated", "superseded", "retired"}:
            continue

        # Фильтр по типу
        if filter_type and req.get("type") != filter_type:
            continue

        # Фильтр по поисковому запросу
        if search_query:
            text = (req.get("title", "") + " " + req.get("id", "")).lower()
            if search_query.lower() not in text:
                continue

        # Оценка пригодности
        score = 0
        score_notes = []

        is_reuse = req.get("reuse_candidate", False)
        if is_reuse:
            score += 3
            score_notes.append("✅ Помечен как reuse-кандидат")

        status = req.get("status", "")
        if status in ("approved", "implemented"):
            score += 2
            score_notes.append(f"✅ Статус {status} — проверено практикой")
        elif status == "confirmed":
            score += 1
            score_notes.append("🟡 Статус confirmed — ещё не утверждён")

        minor = _minor_version(req.get("version", "1.0"))
        if minor <= 1:
            score += 2
            score_notes.append(f"✅ Низкая волатильность (v{req.get('version', '1.0')})")
        elif minor <= 3:
            score += 1
            score_notes.append(f"🟡 Умеренная волатильность (v{req.get('version')})")
        else:
            score_notes.append(f"❌ Высокая волатильность (v{req.get('version')}) — риск при reuse")

        req_type = req.get("type", "")
        if req_type in ("business", "stakeholder"):
            score += 2
            score_notes.append("✅ Высокий уровень абстракции (бизнес/стейкхолдер)")
        elif req_type == "solution":
            score += 0
            score_notes.append("🟡 Требование к решению — ограниченный reuse")

        req_scope = req.get("reuse_scope", "initiative")
        scope_idx = scope_order.index(req_scope) if req_scope in scope_order else 0
        if scope_idx >= min_scope_idx:
            score += 1

        req_info = {
            "id": req.get("id"),
            "title": req.get("title", "—"),
            "type": req_type,
            "status": status,
            "version": req.get("version", "1.0"),
            "owner": req.get("owner", "—"),
            "reuse_scope": req.get("reuse_scope", "initiative"),
            "score": score,
            "score_notes": score_notes,
            "is_reuse": is_reuse,
        }

        if is_reuse or score >= 5:
            candidates.append(req_info)
        elif score >= 3:
            others.append(req_info)

    # Сортируем по score
    candidates.sort(key=lambda x: x["score"], reverse=True)
    others.sort(key=lambda x: x["score"], reverse=True)

    lines = [
        f"<!-- BABOK 5.2 — Повторное использование | Проект: {project_name} | {date.today()} -->",
        "",
        f"# ♻️ Кандидаты на повторное использование",
        "",
        f"**Проект:** {project_name}  ",
        f"**Запрос:** {search_query or 'все'}  ",
        f"**Тип:** {filter_type or 'все'}  ",
        f"**Минимальный scope:** {min_reuse_scope}  ",
        f"**Дата:** {date.today()}",
        "",
        f"Найдено **{len(candidates)}** подтверждённых кандидатов, "
        f"**{len(others)}** потенциальных.",
        "",
    ]

    if candidates:
        lines += [
            "## ✅ Подтверждённые кандидаты",
            "",
        ]
        for r in candidates:
            lines += [
                f"### `{r['id']}` — {r['title']}",
                "",
                f"| Атрибут | Значение |",
                f"|---------|----------|",
                f"| Тип | {r['type']} |",
                f"| Статус | {r['status']} |",
                f"| Версия | {r['version']} |",
                f"| Владелец | {r['owner']} |",
                f"| Scope | {r['reuse_scope']} |",
                f"| Оценка | {'⭐' * min(r['score'], 5)} ({r['score']}/10) |",
                "",
                "**Оценка пригодности:**",
            ]
            for note in r["score_notes"]:
                lines.append(f"- {note}")
            lines.append("")

    if others:
        lines += [
            "## 🟡 Потенциальные кандидаты (не помечены явно)",
            "",
            "| ID | Тип | Название | Статус | v | Оценка |",
            "|----|-----|----------|--------|---|--------|",
        ]
        for r in others:
            stars = "⭐" * min(r["score"], 5)
            lines.append(
                f"| `{r['id']}` | {r['type']} | {r['title']} | {r['status']} | {r['version']} | {stars} |"
            )
        lines += [
            "",
            "> Пометить как reuse-кандидата: `update_requirement(reuse_candidate='true')`",
        ]

    if not candidates and not others:
        lines += [
            "ℹ️ Подходящих кандидатов не найдено по заданным критериям.",
            "",
            "Попробуйте:",
            "- Убрать фильтр по типу",
            "- Снизить min_reuse_scope до 'initiative'",
            "- Пометить требования через `update_requirement(reuse_candidate='true')`",
        ]

    lines += [
        "",
        "---",
        "",
        "## Следующий шаг",
        "",
        "Перед включением в новую инициативу — стейкхолдеры проверяют отобранные",
        "требования на актуальность. Требование для reuse добавляется в новый",
        "репозиторий с `source` указывающим на оригинал.",
    ]

    content = "\n".join(lines)

    hook_result = _export_hook(
        "reuse_list",
        content,
        {"project_name": project_name, "candidates_count": len(candidates)}
    )
    if hook_result.get("status") != "synced":
        content += f"\n\n💾 Сохранено локально. {hook_result.get('note', '')}"

    save_artifact(content, prefix="5_2_reuse_candidates")
    return content


if __name__ == "__main__":
    mcp.run()
