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
from skills.common import (write_json_artifact, save_artifact, logger, DATA_DIR, data_path,
                           normalize_project_id, NON_REQUIREMENT_NODE_TYPES,
                           has_been_approved,
    read_json_artifact, guard_artifact_errors,
    VALID_PRIORITIES, MOSCOW_PRIORITIES, LEVEL_PRIORITIES,
    load_ba_plan, planned_attribute_set, planned_reuse, REUSE_SCOPES,
    attribute_writer, reg_norm, days_since, ARCHIVED_REQUIREMENT_STATUSES,
    approval_outcome,
)
from skills.plural_ru import plural_ru

mcp = FastMCP("BABOK_Requirements_Maintain")

REPO_FILENAME = "traceability_repo.json"

# Порог волатильности — minor-версия выше этого значения → предупреждение
VOLATILITY_WARNING_THRESHOLD = 3   # версия 1.3+
VOLATILITY_CRITICAL_THRESHOLD = 4  # версия 1.4+


# Written once, matched nowhere else: the missing names travel as data on req_info.
_ATTR_GAP_PREFIX = "🟡 Не заполнены атрибуты:"


def _attribute_missing(req: dict, attr: str) -> bool:
    """Is a planned attribute (BABOK 3.4 element .6) unfilled on this requirement?

    `reuse_candidate` is boolean and False is a legitimate answer — "not a reuse
    candidate" is a decision, not a gap. Absence of the key is the gap.
    """
    if attr == "reuse_candidate":
        return "reuse_candidate" not in req
    return not req.get(attr)

# "Staleness" threshold in days without an update
STALE_DAYS_WARNING = 30
STALE_DAYS_CRITICAL = 60

# The closed vocabulary of `status`, as documented by update_requirement. Kept as a
# constant so the docstring and the check cannot drift apart — the vocabulary was
# written down and never turned into a check, which is how `new_status="banana"` came
# to store cleanly.
STATUS_APPROVED_LITERAL = "approved"
VALID_REQUIREMENT_STATUSES = {
    "draft", "confirmed", STATUS_APPROVED_LITERAL, "implemented", "on_hold",
    "verified", "validated", "pending_approval", "rejected", "under_change",
} | ARCHIVED_REQUIREMENT_STATUSES

# What this tool will actually SET. `approved` stays in the vocabulary above so that
# asking for it is answered with the route to 5.5 rather than "unknown status" — but a
# list captioned "Allowed" that names a value the very next guard refuses is the same
# untruth as the docstring that used to advertise it. Offer only what is settable.
SETTABLE_REQUIREMENT_STATUSES = VALID_REQUIREMENT_STATUSES - {STATUS_APPROVED_LITERAL}


# ---------------------------------------------------------------------------
# Утилиты — общие с 5.1 (дублируем чтобы не создавать циклических зависимостей)
# ---------------------------------------------------------------------------

def _repo_path(project_name: str) -> str:
    safe_name = normalize_project_id(project_name)
    return data_path(project_name, f"{safe_name}_{REPO_FILENAME}")


def _load_repo(project_name: str) -> dict:
    path = _repo_path(project_name)
    if os.path.exists(path):
        # Raises CorruptArtifactError, converted to a ❌ line by guard_artifact_errors
        # at the tool boundary. A bare json.load here made a damaged file a protocol
        # error in every downstream tool.
        return read_json_artifact(path, "5.1 traceability repository")
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
    os.makedirs(os.path.dirname(path), exist_ok=True)
    repo["updated"] = str(date.today())
    write_json_artifact(path, repo)
    logger.info(f"Repository updated (5.2): {path}")
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


def _days_since(date_str: str):
    """Days since the given date, or None when the date cannot be read.

    Returns None rather than 0. Zero is the answer for "reviewed today", so returning
    it on a parse failure made every unreadable date report as maximally fresh — see
    common.days_since for the invariant.
    """
    return days_since(date_str)


# ---------------------------------------------------------------------------
# Хук для внешних хранилищ
# ---------------------------------------------------------------------------

_ARTIFACT_LABELS = {
    "requirement_update": "Обновление требования",
    "deprecation": "Устаревшие требования",
    "health_report": "Аудит здоровья требований",
    "reuse_list": "Кандидаты на переиспользование",
}

# Snapshots of the CURRENT state: there should be exactly one page per project that
# gets updated in place. Dating their titles creates a new page every day and the
# "living" report fragments into dozens of copies.
_LIVING_ARTIFACTS = {"health_report", "reuse_list"}


def _requirement_discriminator(metadata: dict) -> str:
    """Requirement ids that keep event-page titles distinct.

    Without this, two updates of DIFFERENT requirements on the same day produce the
    same page title and the second silently overwrites the first in Confluence.
    """
    req_id = metadata.get("req_id")
    if req_id:
        return str(req_id)

    req_ids = metadata.get("req_ids") or []
    if isinstance(req_ids, str):
        req_ids = [req_ids]
    if not req_ids:
        return ""

    shown = ", ".join(str(r) for r in req_ids[:3])
    return f"{shown} +{len(req_ids) - 3}" if len(req_ids) > 3 else shown


def _confluence_page_title(artifact_type: str, project_name: str, metadata: dict) -> str:
    """Builds the Confluence page title for an exported 5.2 artifact."""
    label = _ARTIFACT_LABELS.get(artifact_type, artifact_type)

    if artifact_type in _LIVING_ARTIFACTS:
        return f"{project_name} — {label}"

    discriminator = _requirement_discriminator(metadata)
    if discriminator:
        return f"{project_name} — {label} — {discriminator} ({date.today()})"
    return f"{project_name} — {label} ({date.today()})"


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
        page_title = _confluence_page_title(artifact_type, project_name, metadata)

        result = export_artifact_to_confluence(
            content_markdown=content,
            page_title=page_title,
        )
        logger.info(f"[export_hook] Confluence: {result.get('status')}")
        # Callers report the failure reason via `note`; export_artifact_to_confluence
        # reports it via `message`. Normalize here so a configured-but-failing sync
        # (bad token, missing CONFLUENCE_SPACE_KEY, no permission) is never silent.
        if result.get("status") != "synced" and not result.get("note"):
            result["note"] = result.get("message") or "Синхронизация с Confluence не удалась."
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
@guard_artifact_errors
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
        project_name:    Project name.
        req_id:          Requirement ID: BR-001, FR-007, etc.
        change_reason:   Reason for the change — required. Recorded in the history.
        new_status:      New status. Allowed values:
                         draft | confirmed | pending_approval | rejected |
                         under_change | verified | validated | implemented |
                         on_hold | deprecated | superseded | retired
                         `approved` is deliberately NOT among them: approval is a
                         decision stakeholders make, and chapter 5.5 records it after
                         checking its gates. Asking for it here returns that route.
                         Empty string — leave unchanged.
        new_version:     New version in major.minor format (1.1, 2.0).
                         Empty string — leave unchanged.
        new_priority:    High | Medium | Low. Empty string — leave unchanged.
        new_owner:       Owner name/role. Empty string — leave unchanged.
        new_stability:   Stable | Volatile | Unknown. Empty string — leave unchanged.
        new_title:       New requirement wording. Empty string — leave unchanged.
        reuse_candidate: "true" | "false". Empty string — leave unchanged.
        reuse_scope:     initiative | program | division | enterprise. Empty string — leave unchanged.
        complexity:      Low | Medium | High. Empty string — leave unchanged.
        note:            Additional BA note (optional).

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

    # `priority` is the one attribute here with a closed vocabulary, and it was the one
    # attribute not validated. An unrecognised value stored cleanly and then matched no
    # consumer: 5.3's aggregation, 5.5's critical-requirement warning and 7.5's Must
    # coverage all simply skipped it, so the requirement lost its priority silently.
    if new_priority and new_priority not in VALID_PRIORITIES:
        return (
            f"❌ Неизвестный приоритет `{new_priority}`.\n"
            f"   MoSCoW (5.3): {', '.join(sorted(MOSCOW_PRIORITIES))}\n"
            f"   Уровни (7.1): {', '.join(sorted(LEVEL_PRIORITIES))}"
        )

    # `status` has a closed vocabulary too — spelled out in this docstring — and it
    # routes MORE than priority does: archived-ness, the 5.1/5.2/7.1 filters, and
    # "proven in practice" in the reuse report. A typo stored cleanly and left the
    # requirement neither live nor archived, with nothing said.
    if new_status and new_status not in VALID_REQUIREMENT_STATUSES:
        return (
            f"❌ Неизвестный статус `{new_status}`.\n"
            f"   Допустимые: {', '.join(sorted(SETTABLE_REQUIREMENT_STATUSES))}\n"
            f"   (`approved` в их числе нет — его записывает 5.5.)\n"
            f"   Статус управляет архивацией и фильтрами всех глав, поэтому "
            f"нераспознанное значение оставляет требование ни живым, ни архивным."
        )

    # `approved` is not a description of a requirement — it is the record of an EVENT:
    # stakeholders read a package and signed it. Setting it here would bypass all four
    # gates of 5.5 in one call (no A/R rejection, ≥70% approval, no overdue conditions,
    # 7.2 verification), and 5.2's own reuse report would then present the requirement
    # as "✅ Approved in 5.5 — proven in practice", citing a procedure that never
    # happened. Owner's decision, 2026-08-03.
    if new_status == STATUS_APPROVED_LITERAL:
        return (
            f"❌ `approved` здесь поставить нельзя.\n"
            f"   Согласование — это решение стейкхолдеров, а не атрибут, который "
            f"правит аналитик: его записывает глава 5.5, и она проверяет, что никто "
            f"из Accountable/Responsible не отклонил требование, что согласовавших "
            f"достаточно и что условия по нему не просрочены.\n"
            f"   Маршрут: `prepare_approval_package` → `record_approval_decision` → "
            f"`create_requirements_baseline` (5.5).\n"
            f"   Ничего не изменено."
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

    # A node's MEANING changed (its wording, or its stage) — so ask the graph what was
    # resting on it. The check used to hang on the NAME of the operation:
    # `deprecate_requirements` warned about incoming links, `update_requirement` did
    # not, although renaming is the worse case. Deprecating makes the edges look
    # suspect; renaming leaves them looking healthy while they go on justifying
    # requirements written against different words.
    meaning_note = ""
    incoming = [lnk for lnk in repo.get("links", [])
                if lnk.get("to") == req_id
                and lnk.get("relation") in ("satisfies", "derives", "verifies")]
    if new_title and incoming:
        by_id = ", ".join(sorted({f"`{lnk['from']}`" for lnk in incoming}))
        meaning_note = (
            f"\n\n⚠️ **Этим требованием обоснованы {len(incoming)} "
            f"{plural_ru(len(incoming), 'требование', 'требования', 'требований')}, а "
            f"формулировка только что изменилась:** {by_id}.\n"
            f"Их связи по-прежнему читаются как обычное обоснование — проверьте, что "
            f"они держатся и на новой формулировке."
        )

    # Reviving an archived requirement reverses a 5.2 decision. The opposite direction
    # (deprecating) warns about links and recommends the coverage audit; this direction
    # said nothing at all.
    revival_note = ""
    old_status = str(old_values.get("status", "") or "")
    if old_status in ARCHIVED_REQUIREMENT_STATUSES and \
            new_status and new_status not in ARCHIVED_REQUIREMENT_STATUSES:
        incoming_ids = ", ".join(sorted({f"`{lnk['from']}`" for lnk in incoming}))
        edges_part = (
            f"; на него указывают {len(incoming)} "
            f"{plural_ru(len(incoming), 'связь', 'связи', 'связей')}: {incoming_ids}"
            if incoming else "")
        revival_note = (
            f"\n\n♻️ **Это требование было `{old_status}` и снова живо.** Это отменяет "
            f"решение 5.2{edges_part}.\n"
            f"Запустите `check_coverage` (5.1), чтобы увидеть, с чем оно связано теперь."
        )

    # Handing ownership over is a one-line edit here and a NEW 🔴 gap in 7.4 — ADR-098
    # reads `owner` on demand rather than storing a copy (so no copy can go stale), and
    # the price of that decision is that the previous owner's only recorded tie can
    # vanish with this call. Reproduced live: 🔴 0 before, 🔴 1 after, and the
    # architecture document moved the previous owner to "no interest recorded" without
    # anybody saying so (branch review B-3). Warn, never block: the BA may have meant
    # exactly this — they simply have to be able to see it.
    ownership_note = ""
    previous_owner = str(old_values.get("owner", "") or "").strip()
    if previous_owner and previous_owner != "—" and \
            reg_norm(previous_owner) != reg_norm(new_owner):
        ownership_note = (
            f"\n\n⚠️ **Владение ушло от `{previous_owner}`.** 7.4 вычисляет связи "
            f"«стейкхолдер ↔ требование» из поля `owner` НА ЛЕТУ, а не хранит их, "
            f"поэтому `{previous_owner}` может теперь появиться в "
            f"`check_architecture_gaps` как человек без единой записанной связи с "
            f"требованиями. Если его интересы по-прежнему затронуты — зафиксируйте это "
            f"через 7.4 `declare_stakeholder_interest`: это та связь, которую платформа "
            f"хранит."
        )

    content = ("\n".join(lines) + volatility_warning + ownership_note
               + meaning_note + revival_note)

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

    save_artifact(content, prefix="5_2_requirement_update", project_id=project_name)
    return content


# ---------------------------------------------------------------------------
# 5.2.2 — Пометить требования как устаревшие / замененные
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
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

    # Shape, not just syntax: an LLM writing a scalar or an object where a list of
    # ids is expected must get a readable "❌", not a TypeError escaping the tool.
    from skills.common import parse_json_str_list
    req_ids, shape_error = parse_json_str_list(req_ids_json, "req_ids_json")
    if shape_error:
        return shape_error

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

    save_artifact(content, prefix="5_2_deprecation", project_id=project_name)
    return content


# ---------------------------------------------------------------------------
# 5.2.3 — Аудит здоровья реестра требований
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def check_requirements_health(
    project_name: str,
    filter_type: str = "",
    filter_status: str = "",
) -> str:
    """
    BABOK 5.2 — Аудит здоровья реестра требований.

    What it looks for:
      🔴 High volatility (version 1.4+) — the requirement is unstable
      🟡 Medium volatility (version 1.2-1.3) — worth checking
      🟡 Stale (not updated for >60 days) — possibly outdated
      🟡 Long in draft (>30 days) — confirm or freeze
      🟡 Unfilled attributes — the set planned in 3.4 (`attributes_preset`).
         Without a 3.4 plan this is the single check "No owner", as before.
      🟢 Healthy requirements — all good

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

    # BABOK 3.4 element .6: the project plans WHICH attributes it maintains, and this
    # audit checks exactly that set. Without a plan the behaviour is unchanged — the
    # single hard-coded owner check, worded exactly as before, and not one new line.
    plan, plan_note = load_ba_plan(project_name)
    resolved = planned_attribute_set(plan)
    audited, audited_label = resolved if resolved else (("owner",), "умолчание платформы")

    # Only requirements are maintained here. The health criteria — volatility, owner,
    # staleness, reuse — describe a requirement's lifecycle, so applying them to other
    # chapters' nodes produced a report demanding an owner for every business objective
    # and every risk in the register. An explicit filter_type still wins, so a BA who
    # deliberately asks for `risk` gets it.
    requirements = repo["requirements"]
    if not filter_type:
        requirements = [r for r in requirements
                        if r.get("type", "") not in NON_REQUIREMENT_NODE_TYPES]

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

        # Stale. The flag is set where the judgement is MADE — the two branches that
        # actually judge a requirement out of date. The advice block used to recover it
        # by looking for "days" in the rendered line, which also matched "510 days in
        # the future" (a damaged date, explicitly NOT judged) and "in draft for 100
        # days" (which says nothing about when it was last reviewed).
        is_stale = False
        last_reviewed = req.get("last_reviewed") or req.get("added", "")
        if last_reviewed:
            days = _days_since(last_reviewed)
            if days is None:
                # Not "fresh" and not "stale" — unknown, and the analyst is the only
                # one who can say which. Staying silent here is how a damaged date
                # switched the staleness check off for good.
                issues.append(
                    f"🟡 Не удалось прочитать дату ревью (`{last_reviewed}`) — "
                    f"устаревание для этого требования НЕ проверялось")
            elif days < 0:
                issues.append(
                    f"🟡 Дата ревью на {abs(days)} "
                    f"{plural_ru(abs(days), 'день', 'дня', 'дней')} в будущем "
                    f"(`{last_reviewed}`) — данные испорчены, судить об устаревании нельзя")
            elif days > STALE_DAYS_CRITICAL:
                # The heavier branch must not read as LIGHTER than the softer one: it
                # used to lose the call to action the >30 case carries.
                issues.append(
                    f"🟡 Не обновлялось {days} "
                    f"{plural_ru(days, 'день', 'дня', 'дней')} — пересмотрите его")
                is_stale = True
            elif days > STALE_DAYS_WARNING:
                issues.append(
                    f"🟡 Не обновлялось {days} "
                    f"{plural_ru(days, 'день', 'дня', 'дней')} — стоит проверить")
                is_stale = True

        # Долго в draft
        if req.get("status") == "draft":
            added = req.get("added", "")
            if added:
                days_draft = _days_since(added)
                if days_draft is not None and days_draft > STALE_DAYS_WARNING:
                    issues.append(
                        f"🟡 В статусе draft уже {days_draft} "
                        f"{plural_ru(days_draft, 'день', 'дня', 'дней')}")

        # Planned attributes (BABOK 3.4 element .6). One line per requirement, not one
        # per attribute: a Full preset on a bare requirement would otherwise add nine
        # rows and push the real 🔴 findings out of the reader's view.
        missing = [a for a in audited if _attribute_missing(req, a)]
        if missing:
            if resolved:
                issues.append(f"{_ATTR_GAP_PREFIX} {', '.join(missing)}")
            else:
                # Legacy wording, byte-for-byte, for projects with no 3.4 plan.
                issues.append("🟡 Нет владельца")

        req_info = {
            "id": req_id,
            "title": req.get("title", "—"),
            "type": req.get("type", "—"),
            "status": req.get("status", "—"),
            "version": req.get("version", "1.0"),
            "owner": req.get("owner", "—"),
            "issues": issues,
            # Carried as data, not recovered by re-parsing the rendered issue line.
            # A re-parse is safe only while no attribute name contains the separators,
            # and a reworded issue string would silently empty the advice block —
            # reinstating the very self-contradiction this audit was fixed to avoid.
            "missing_attributes": missing,
            # Same rule as `missing_attributes` above, for the same reason.
            "stale": is_stale,
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
        f"**Фильтр:** type={filter_type or 'все'}, status={filter_status or 'active'}  ",
        # Named only when a plan actually selected the set: a project that never opened
        # chapter 3 gains no line here and keeps the legacy owner check and its wording.
        # (Two deliberate repairs in the same feature DO reach plan-less projects — the
        # action list is now numbered from 1, and the reuse report stopped calling a
        # ranking bonus a minimum. Neither is plan-dependent; "no plan, nothing new"
        # describes this feature's ADDITIONS, not those two fixes.)
        *([f"**Проверяемые атрибуты:** {', '.join(audited)} *({audited_label})*  "]
          if resolved else []),
        f"**Дата:** {date.today()}",
        "",
        *([plan_note, ""] if plan_note else []),
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
        # The legacy sentence names `owner` outright. Under a plan that does not audit
        # it, nothing here ever looked at the owner, so claiming every healthy
        # requirement has one is a confident false claim on the same page that chose
        # not to check. Without a plan the wording is untouched.
        n_h = len(healthy)
        noun_h = plural_ru(n_h, "требование", "требования", "требований")
        healthy_summary = (
            f"**{n_h} {noun_h}** в порядке — актуальны, стабильны и заполнены по "
            f"каждому проверяемому атрибуту."
            if resolved else
            f"**{n_h} {noun_h}** в порядке — актуальны, есть владелец, стабильны."
        )
        lines += [
            "## 🟢 Здоровые требования",
            "",
            healthy_summary,
            "",
        ]

    lines += [
        "---",
        "",
        "## Рекомендуемые действия",
        "",
    ]

    # Numbered as they are emitted. The numbers used to be hardcoded 1/2/3, so a
    # report with no critical findings opened its action list at "2." — a delivered
    # document with a missing first step.
    actions = []
    if critical:
        actions.append(
            f"🔴 **{len(critical)} critical** — обсудите волатильность, "
            f"обновите через `update_requirement` или `deprecate_requirements`."
        )
    if warnings:
        attr_gaps = [r for r in warnings if r["missing_attributes"]]
        stale = sum(1 for r in warnings if r.get("stale"))
        if attr_gaps:
            if resolved:
                # The counter used to look for the substring "owner", so a project on a
                # preset without it saw 🟡 rows and no advice about them at all — a
                # document contradicting itself inside one page.
                missing_names = sorted({name for r in attr_gaps
                                        for name in r["missing_attributes"]})
                # Routed through the shared table instead of hard-coding one tool's
                # name. `update_requirement` cannot write `source` or `stakeholders` —
                # it has no parameter for either — and `last_reviewed` is stamped by
                # the platform, so the old line sent the BA to a tool that would have
                # refused three of the twelve audited attributes. `source` in
                # particular is audited by the Minimum preset, so the wrong advice
                # fired on the default route of every planned project (R-4).
                by_writer: dict = {}
                for name in missing_names:
                    by_writer.setdefault(attribute_writer(name), []).append(name)
                routes = "; ".join(
                    f"{', '.join(names)} → {writer}"
                    for writer, names in sorted(by_writer.items(),
                                                key=lambda kv: kv[1][0])
                )
                actions.append(
                    f"🟡 **У {len(attr_gaps)} не заполнены атрибуты** "
                    f"({', '.join(missing_names)}) — заполните их: {routes}.")
            else:
                # Legacy wording, byte-for-byte, for projects with no 3.4 plan.
                actions.append(
                    f"🟡 **{len(attr_gaps)} без владельца** — "
                    f"назначьте владельца через `update_requirement`.")
        if stale:
            actions.append(
                f"🟡 **{stale} давно не обновлялись** — подтвердите актуальность у стейкхолдера.")

    lines += [f"{i}. {action}" for i, action in enumerate(actions, 1)]

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

    save_artifact(content, prefix="5_2_health_check", project_id=project_name)
    return content


# ---------------------------------------------------------------------------
# 5.2.4 — Поиск кандидатов на повторное использование
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def find_reusable_requirements(
    project_name: str,
    search_query: str = "",
    filter_type: str = "",
    min_reuse_scope: Literal["", "initiative", "program", "division", "enterprise"] = "",
) -> str:
    """
    BABOK 5.2 — Находит требования — кандидатов на повторное использование.

    Критерии хорошего кандидата (автоматически проверяются):
      ✅ Флаг reuse_candidate = True
      ✅ Статус approved или implemented (проверено практикой)
      ✅ Низкая волатильность (версия ≤ 1.1)
      ✅ Тип business или stakeholder (высокий уровень абстракции)

    Args:
        project_name:     Project name.
        search_query:     Search query against the requirement text (optional).
        filter_type:      Filter by type: business | stakeholder | solution | transition
        min_reuse_scope:  The reuse level being aimed for: initiative | program |
                          division | enterprise. It RANKS, it does not filter — a
                          requirement at or above the level scores one point more,
                          and nothing is excluded for being below it. Left empty, the
                          level planned in 3.4 is used; without a plan, `initiative`.
                          An explicit value always wins over the plan.

    Returns:
        Список кандидатов с оценкой пригодности для повторного использования.
    """
    logger.info(f"find_reusable_requirements: '{project_name}', query='{search_query}'")

    repo = _load_repo(project_name)

    # BABOK 3.4 element .4. The default used to live in the signature, which made "the
    # BA chose initiative" and "the BA chose nothing" indistinguishable — and a plan
    # that silently overrode an explicit input is exactly why the governance wiring was
    # refused in an earlier pass.
    plan, plan_note = load_ba_plan(project_name)
    reuse_plan = planned_reuse(plan) or {}
    if min_reuse_scope:
        effective_scope, scope_source = min_reuse_scope, ""
    elif reuse_plan.get("target_scope"):
        effective_scope, scope_source = reuse_plan["target_scope"], " *(из плана 3.4)*"
    else:
        effective_scope, scope_source = "initiative", ""

    # The shared constant, not a local copy: `planned_reuse` validates the stored value
    # against REUSE_SCOPES, so a fifth level added there would have been accepted by the
    # reader and then raised ValueError on this .index() call.
    scope_order = list(REUSE_SCOPES)
    min_scope_idx = scope_order.index(effective_scope)

    candidates = []
    others = []  # требования без флага reuse, но потенциально подходящие

    for req in repo["requirements"]:
        # Пропускаем архивные
        if req.get("status") in {"deprecated", "superseded", "retired"}:
            continue

        # Only requirement-role nodes can be reused as requirements. The neighbour
        # check_requirements_health already filters by role; this loop did not, so
        # the reuse report offered a change request as a confirmed candidate (its
        # 5.4 status literal is `approved`, which scores like a 5.5 approval) and
        # every risk and goal as potential candidates.
        #
        # `business` is deliberately NOT excluded here, although it sits in
        # NON_REQUIREMENT_NODE_TYPES as the legacy root type: the same literal is
        # ALSO the BABOK requirement CLASS (business requirement — the most
        # reusable kind, which this very loop scores "+2 high level of
        # abstraction"). Dropping it would silently discard BRs an analyst flagged
        # `reuse_candidate` — the `solution` lesson (one literal, two populations;
        # under-counting a requirement is the worse failure) applied to its twin.
        if req.get("type", "") in (NON_REQUIREMENT_NODE_TYPES - {"business"}):
            continue

        # Filter by type
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
        # "Proven in practice" is a fact about the requirement's history, not about
        # whichever chapter wrote `status` last. A requirement approved in 5.5 and
        # then validated in 7.3 reads `validated` and used to silently lose the two
        # points — the reuse ranking degraded as the project matured.
        if has_been_approved(project_name, req.get("id", "")):
            score += 2
            score_notes.append("✅ Согласовано в 5.5 — проверено практикой")
        elif status == "implemented":
            score += 2
            score_notes.append("✅ Статус implemented — проверено практикой")
        elif status == "approved":
            # No approval records (a legacy project, or an approval recorded outside
            # 5.5). The status is the only evidence there is, so it still counts.
            score += 2
            score_notes.append("✅ Статус approved — проверено практикой")
        elif status == "confirmed":
            score += 1
            score_notes.append("🟡 Статус confirmed — ещё не утверждён")

        # Age and unresolved objections. The module KNOWS how to compute both —
        # `check_requirements_health` next door reads staleness, and 5.5's decisions
        # are on disk — but the fitness card was built purely from node attributes, so
        # it offered a requirement nobody had looked at in two months, carrying an
        # Accountable rejection in another package, as "proven in practice".
        age = _days_since(req.get("last_reviewed") or req.get("added", ""))
        if age is None:
            score_notes.append("🟡 Возраст неизвестен — дату ревью прочитать не удалось")
        elif age > STALE_DAYS_CRITICAL:
            score_notes.append(
                f"🟡 Не пересматривалось {age} "
                f"{plural_ru(age, 'день', 'дня', 'дней')} — прежде чем переиспользовать, "
                f"подтвердите, что оно ещё отражает текущий процесс")
        outcome = approval_outcome(project_name, req.get("id", ""))
        if outcome == "rejected":
            score_notes.append(
                "❌ Отклонено в 5.5 — возражение так и не было снято")
        elif outcome == "conditional":
            score_notes.append("🟡 Согласовано в 5.5 с открытыми условиями")

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
        scope_bonus = 1 if scope_idx >= min_scope_idx else 0
        score += scope_bonus
        if not scope_bonus:
            # Named, because the bonus moves the printed score but deliberately not the
            # section: without this line a confirmed and a potential candidate could
            # show the same score with nothing in the document explaining why.
            score_notes.append(
                f"🟡 Ниже запланированного scope переиспользования ({effective_scope}) — на балл меньше")

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

        # Membership must NOT depend on the scope bonus, or planning a WIDER reuse
        # ambition in 3.4 shows FEWER candidates — the opposite of the point. An
        # untagged requirement counts as `initiative`, so above that target it loses
        # the point and used to fall under the threshold entirely; with no plan every
        # requirement earns it, so counting it as earned here keeps plan-less projects
        # byte-identical to before. The bonus still moves the printed score, which is
        # what "raises the ranking" means.
        membership_score = score + (1 - scope_bonus)
        if is_reuse or membership_score >= 5:
            candidates.append(req_info)
        elif membership_score >= 3:
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
        f"**Целевой scope переиспользования:** {effective_scope}{scope_source} — "
        f"поднимает в ранжировании, но не исключает  ",
        f"**Дата:** {date.today()}",
        "",
        *([plan_note, ""] if plan_note else []),
        f"Найдено **{len(candidates)}** "
        f"{plural_ru(len(candidates), 'подтверждённый кандидат', 'подтверждённых кандидата', 'подтверждённых кандидатов')}, "
        f"**{len(others)}** потенциальных.",
        "",
    ]

    if reuse_plan.get("categories"):
        lines += [
            "**Запланированные категории кандидатов (3.4):** "
            + ", ".join(reuse_plan["categories"]),
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

    repository = reuse_plan.get("repository")

    if not candidates and not others:
        lines += [
            "ℹ️ Подходящих кандидатов не найдено по заданным критериям.",
            "",
            "Попробуйте:",
            "- Снять фильтр по типу",
            "- Расширить поисковый запрос",
            # "Lowering min_reuse_scope" used to be offered here. It could never change
            # an empty result: the scope adds a point to the suitability score and
            # excludes nothing. Advice that cannot work is worse than no advice.
            "- Помечать требования через `update_requirement(reuse_candidate='true')`",
        ]
        if repository:
            lines.append(f"- Посмотреть в репозитории переиспользования из плана 3.4: {repository}")

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
    if repository:
        # BABOK p. 45: reusable requirements must live "in a repository that is
        # available to other business analysts". Naming the planned one turns generic
        # advice into an address.
        lines += ["", f"Репозиторий переиспользования из плана 3.4: **{repository}**"]

    content = "\n".join(lines)

    hook_result = _export_hook(
        "reuse_list",
        content,
        {"project_name": project_name, "candidates_count": len(candidates)}
    )
    if hook_result.get("status") != "synced":
        content += f"\n\n💾 Сохранено локально. {hook_result.get('note', '')}"

    save_artifact(content, prefix="5_2_reuse_candidates", project_id=project_name)
    return content


if __name__ == "__main__":
    mcp.run()
