"""
BABOK 5.5 — Approve Requirements
MCP-инструменты для утверждения требований и создания Requirements Baseline.

Инструменты:
  - prepare_approval_package    — подготовить пакет требований к согласованию
  - record_approval_decision    — зафиксировать решение стейкхолдера
  - close_approval_condition    — закрыть выполненное условие (Conditional)
  - check_approval_status       — дашборд готовности пакета к baseline
  - create_requirements_baseline — создать official Requirements Baseline

Хранение:
  - Решения по одобрению: в узлах репозитория 5.1 ({project}_traceability_repo.json)
  - История baseline-ов: {project}_approval_history.json
  - Approval Record: сохраняется через save_artifact

Интеграция:
  Вход:  репозиторий 5.1 (граф+статусы), приоритеты 5.3, CR Records 5.4, стейкхолдеры 4.2
  Выход: Approval Record → 4.4 (коммуникация), Глава 6 (разработка)
         approved-статусы в репозитории 5.1

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date, datetime
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import save_artifact, logger, DATA_DIR

mcp = FastMCP("BABOK_Requirements_Approve")

REPO_FILENAME = "traceability_repo.json"
APPROVAL_HISTORY_FILENAME = "approval_history.json"

# Допустимые статусы решений
VALID_DECISIONS = {"approved", "conditional", "rejected", "abstained"}

# Статусы требований в pipeline 5.5
STATUS_PENDING = "pending_approval"
STATUS_APPROVED = "approved"
STATUS_CONDITIONAL = "conditional_approved"
STATUS_REJECTED = "rejected"


# ---------------------------------------------------------------------------
# Утилиты — файловый слой
# ---------------------------------------------------------------------------

def _repo_path(project_name: str) -> str:
    safe = project_name.lower().replace(" ", "_")
    return os.path.join(DATA_DIR, f"{safe}_{REPO_FILENAME}")


def _approval_history_path(project_name: str) -> str:
    safe = project_name.lower().replace(" ", "_")
    return os.path.join(DATA_DIR, f"{safe}_{APPROVAL_HISTORY_FILENAME}")


def _load_repo(project_name: str) -> dict:
    path = _repo_path(project_name)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"project": project_name, "requirements": [], "links": [], "history": []}


def _save_repo(project_name: str, repo: dict) -> None:
    path = _repo_path(project_name)
    os.makedirs(DATA_DIR, exist_ok=True)
    repo["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)


def _load_approval_history(project_name: str) -> dict:
    path = _approval_history_path(project_name)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"project": project_name, "packages": {}, "baselines": []}


def _save_approval_history(project_name: str, history: dict) -> None:
    path = _approval_history_path(project_name)
    os.makedirs(DATA_DIR, exist_ok=True)
    history["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def _find_node(repo: dict, node_id: str) -> Optional[dict]:
    for r in repo["requirements"]:
        if r["id"] == node_id:
            return r
    return None


def _get_package(history: dict, package_id: str) -> Optional[dict]:
    return history["packages"].get(package_id)


def _get_req_approval_summary(package: dict, req_id: str) -> dict:
    """Собирает все решения по конкретному требованию из всех стейкхолдеров."""
    decisions = []
    for sh_name, sh_data in package.get("stakeholder_decisions", {}).items():
        for rd in sh_data.get("req_decisions", []):
            if rd["req_id"] == req_id:
                decisions.append({
                    "stakeholder": sh_name,
                    "raci": sh_data.get("raci", "consulted"),
                    "decision": rd["decision"],
                    "condition_text": rd.get("condition_text", ""),
                    "condition_closed": rd.get("condition_closed", False),
                    "rejection_reason": rd.get("rejection_reason", ""),
                })
    return {"req_id": req_id, "decisions": decisions}


def _compute_req_status(req_id: str, package: dict) -> str:
    """Вычисляет итоговый статус требования на основе всех решений стейкхолдеров."""
    decisions_by_stakeholder = []
    for sh_name, sh_data in package.get("stakeholder_decisions", {}).items():
        raci = sh_data.get("raci", "consulted")
        for rd in sh_data.get("req_decisions", []):
            if rd["req_id"] == req_id:
                decisions_by_stakeholder.append({
                    "raci": raci,
                    "decision": rd["decision"],
                    "condition_closed": rd.get("condition_closed", False),
                })

    if not decisions_by_stakeholder:
        return STATUS_PENDING

    # Rejected от Accountable/Responsible → rejected
    for d in decisions_by_stakeholder:
        if d["decision"] == "rejected" and d["raci"] in ("accountable", "responsible"):
            return STATUS_REJECTED

    # Открытое conditional от любого A/R → conditional_approved
    for d in decisions_by_stakeholder:
        if d["decision"] == "conditional" and not d["condition_closed"] and d["raci"] in ("accountable", "responsible"):
            return STATUS_CONDITIONAL

    # Все A/R одобрили (или abstained/consulted-rejected) → approved
    ar_decisions = [d for d in decisions_by_stakeholder if d["raci"] in ("accountable", "responsible")]
    if ar_decisions and all(
        d["decision"] in ("approved", "abstained") or
        (d["decision"] == "conditional" and d["condition_closed"])
        for d in ar_decisions
    ):
        return STATUS_APPROVED

    return STATUS_PENDING


def _get_cr_context(repo: dict, req_id: str) -> list:
    """Ищет CR, затрагивающие требование (modifies-связи)."""
    cr_refs = []
    for lnk in repo.get("links", []):
        if lnk.get("to") == req_id and lnk.get("relation") == "modifies":
            cr_node = _find_node(repo, lnk["from"])
            if cr_node and cr_node.get("type") == "change_request":
                cr_refs.append({
                    "cr_id": cr_node["id"],
                    "title": cr_node.get("title", "—"),
                    "status": cr_node.get("status", "unknown"),
                    "decision": (cr_node.get("decision") or {}).get("verdict", "—"),
                })
    return cr_refs


# ---------------------------------------------------------------------------
# 5.5.1 — Подготовить пакет к согласованию
# ---------------------------------------------------------------------------

@mcp.tool()
def prepare_approval_package(
    project_name: str,
    package_id: str,
    package_title: str,
    req_ids_json: str,
    approach: Literal["predictive", "agile"],
    audience: Literal["business", "developer", "regulator", "all"] = "all",
    sprint_number: str = "",
) -> str:
    """
    BABOK 5.5 — Шаг 1: Подготовить пакет требований к согласованию.

    Собирает требования из репозитория 5.1, добавляет контекст из 5.3 и 5.4,
    формирует Approval Package для стейкхолдеров.

    Args:
        project_name:   Название проекта.
        package_id:     Уникальный ID пакета. Рекомендуемый формат: APKG-001.
        package_title:  Название пакета (например: «Фича: Онбординг пользователей»).
        req_ids_json:   JSON-список ID требований для пакета.
                        Пример: '["FR-001", "FR-002", "NFR-001"]'
        approach:       Методология: predictive (Waterfall) или agile (Scrum/Kanban).
        audience:       Аудитория пакета:
                        - business: бизнес-требования и критерии приёмки
                        - developer: функциональные + нефункциональные требования
                        - regulator: compliance-требования с трассировкой
                        - all: полный пакет для всех аудиторий
        sprint_number:  Номер спринта (только для agile, например: "5").

    Returns:
        Markdown Approval Package для передачи стейкхолдерам.
        Создаёт запись пакета в {project}_approval_history.json.
    """
    logger.info(f"prepare_approval_package: {package_id} / {project_name}")

    try:
        req_ids = json.loads(req_ids_json)
    except json.JSONDecodeError:
        return "❌ Ошибка: `req_ids_json` должен быть валидным JSON-списком. Пример: '[\"FR-001\"]'"

    if not req_ids:
        return "❌ Ошибка: список требований не может быть пустым."

    repo = _load_repo(project_name)
    history = _load_approval_history(project_name)

    # Проверка: пакет уже существует?
    if package_id in history["packages"]:
        return (
            f"⚠️ Пакет `{package_id}` уже существует для проекта `{project_name}`.\n"
            f"Используйте другой ID или проверьте существующий пакет через `check_approval_status`."
        )

    # Проверка: требования существуют?
    missing = [rid for rid in req_ids if not _find_node(repo, rid)]
    if missing:
        return (
            f"⚠️ Следующие требования не найдены в репозитории: {missing}\n"
            f"Проверьте ID или добавьте требования через `init_traceability_repo` (5.1)."
        )

    # Собираем данные по требованиям
    req_details = []
    cr_warnings = []
    for rid in req_ids:
        node = _find_node(repo, rid)
        cr_refs = _get_cr_context(repo, rid)
        if cr_refs:
            open_crs = [c for c in cr_refs if c["status"] in ("open", "under_change")]
            if open_crs:
                cr_warnings.append((rid, open_crs))
        req_details.append({
            "id": rid,
            "title": node.get("title", "—"),
            "type": node.get("type", "functional"),
            "description": node.get("description", ""),
            "status": node.get("status", "unknown"),
            "priority": node.get("priority", "—"),
            "version": node.get("version", "1.0"),
            "owner": node.get("owner", "—"),
            "acceptance_criteria": node.get("acceptance_criteria", ""),
            "cr_refs": cr_refs,
        })

    # Создаём запись пакета в approval_history
    package_record = {
        "package_id": package_id,
        "package_title": package_title,
        "approach": approach,
        "audience": audience,
        "sprint_number": sprint_number,
        "req_ids": req_ids,
        "created_date": str(date.today()),
        "stakeholder_decisions": {},
        "baseline_version": None,
        "status": "open",
    }
    history["packages"][package_id] = package_record
    _save_approval_history(project_name, history)

    # Обновляем статусы требований на pending_approval в репозитории 5.1
    for rid in req_ids:
        node = _find_node(repo, rid)
        if node:
            node["status"] = STATUS_PENDING
    _save_repo(project_name, repo)

    # Формируем Approval Package
    approach_label = "Predictive / Waterfall" if approach == "predictive" else "Agile"
    sprint_label = f" | Спринт: {sprint_number}" if sprint_number else ""

    lines = [
        f"<!-- BABOK 5.5 — Approval Package, Проект: {project_name}, Пакет: {package_id}, Дата: {date.today()} -->",
        "",
        f"# Approval Package: {package_title}",
        f"**Проект:** {project_name}  ",
        f"**Пакет:** {package_id}  ",
        f"**Методология:** {approach_label}{sprint_label}  ",
        f"**Аудитория:** {audience}  ",
        f"**Дата:** {date.today()}  ",
        f"**Требований в пакете:** {len(req_ids)}  ",
        "",
        "---",
        "",
    ]

    # Предупреждения об открытых CR
    if cr_warnings:
        lines += ["## ⚠️ Предупреждения: открытые Change Requests", ""]
        for rid, open_crs in cr_warnings:
            cr_list = ", ".join(f"`{c['cr_id']}` ({c['status']})" for c in open_crs)
            lines.append(f"- `{rid}` затронуто открытыми CR: {cr_list}")
        lines += ["", "Рекомендуется закрыть CR (5.4) перед согласованием.", ""]

    # Требования по типам (фильтрация по audience)
    if audience == "business":
        filtered = [r for r in req_details if r["type"] in ("business", "stakeholder")]
        if not filtered:
            filtered = req_details
    elif audience == "developer":
        filtered = [r for r in req_details if r["type"] in ("functional", "non_functional", "transition")]
        if not filtered:
            filtered = req_details
    elif audience == "regulator":
        filtered = [r for r in req_details if r.get("regulatory") or "compliance" in r.get("title", "").lower()]
        if not filtered:
            filtered = req_details
    else:
        filtered = req_details

    lines += ["## Требования для согласования", ""]

    for req in filtered:
        priority_str = f" | Приоритет: {req['priority']}" if req['priority'] != "—" else ""
        lines += [
            f"### {req['id']}: {req['title']}",
            f"**Тип:** {req['type']} | **Версия:** {req['version']}{priority_str}  ",
            f"**Owner:** {req['owner']}  ",
        ]
        if req.get("description"):
            lines += ["", req["description"], ""]
        if req.get("acceptance_criteria"):
            lines += [f"**Критерии приёмки:** {req['acceptance_criteria']}", ""]
        if req["cr_refs"]:
            cr_info = "; ".join(f"{c['cr_id']} ({c['status']}/{c['decision']})" for c in req["cr_refs"])
            lines += [f"**CR-история:** {cr_info}", ""]
        lines.append("")

    # Инструкция для стейкхолдеров
    if approach == "predictive":
        instruction = (
            "Просьба рассмотреть требования и предоставить решение по каждому:\n"
            "- **Approved** — согласен без оговорок\n"
            "- **Conditional** — согласен при выполнении условия (укажите условие)\n"
            "- **Rejected** — не согласен (укажите причину)\n"
            "- **Abstained** — воздерживаюсь\n\n"
            "Срок ответа: согласно governance-плану проекта."
        )
    else:
        sprint_ref = f" спринта {sprint_number}" if sprint_number else ""
        instruction = (
            f"Для Sprint Planning{sprint_ref}. Product Owner рассматривает и одобряет backlog.\n"
            "Требования принятые в спринт получат статус Approved и войдут в Sprint Baseline."
        )

    lines += [
        "---",
        "",
        "## Инструкция для стейкхолдеров",
        "",
        instruction,
        "",
        "---",
        "",
        "## Следующий шаг",
        "",
        f"После получения ответов стейкхолдеров — вызывайте `record_approval_decision`:",
        f"  - `project_name`: \"{project_name}\"",
        f"  - `package_id`: \"{package_id}\"",
        f"  - `stakeholder_name`: имя стейкхолдера",
        f"  - `decision`: approved / conditional / rejected / abstained",
    ]

    artifact_content = "\n".join(lines)
    save_path = save_artifact(artifact_content, prefix=f"5_5_approval_package_{package_id}")

    return artifact_content + save_path


# ---------------------------------------------------------------------------
# 5.5.2 — Зафиксировать решение стейкхолдера
# ---------------------------------------------------------------------------

@mcp.tool()
def record_approval_decision(
    project_name: str,
    package_id: str,
    stakeholder_name: str,
    stakeholder_raci: Literal["accountable", "responsible", "consulted"],
    decision: Literal["approved", "conditional", "rejected", "abstained"],
    req_decisions_json: str = "[]",
    rejection_reason: str = "",
    comment: str = "",
) -> str:
    """
    BABOK 5.5 — Шаг 2: Зафиксировать решение стейкхолдера по пакету.

    Вызывается отдельно для каждого стейкхолдера (аналог add_stakeholder_scores в 5.3).
    При rejected — автоматически анализирует контекст из 5.3 и 5.4 для флагования конфликтов.

    Args:
        project_name:       Название проекта.
        package_id:         ID пакета (из prepare_approval_package).
        stakeholder_name:   Имя или роль стейкхолдера.
        stakeholder_raci:   Роль в RACI: accountable / responsible / consulted.
                            Rejected от accountable/responsible = блокировщик baseline.
                            Rejected от consulted = input для risk assessment.
        decision:           Общее решение по пакету: approved / conditional / rejected / abstained.
                            Используется если req_decisions_json пуст — применяется ко всем req.
        req_decisions_json: JSON-список решений по отдельным требованиям пакета.
                            Если передан — overrides общий decision для указанных req.
                            Формат:
                            [
                              {"req_id": "FR-001", "decision": "approved"},
                              {"req_id": "FR-002", "decision": "conditional",
                               "condition_text": "Уточнить критерий приёмки",
                               "condition_deadline": "2026-04-01",
                               "condition_owner": "Иванов А."},
                              {"req_id": "FR-003", "decision": "rejected",
                               "rejection_reason": "За пределами скоупа"}
                            ]
                            Если пуст ([]) — decision применяется ко всем req пакета.
        rejection_reason:   Причина отклонения (обязательно если decision=rejected
                            и req_decisions_json пуст).
        comment:            Дополнительный комментарий стейкхолдера.

    Returns:
        Подтверждение записи решения, анализ конфликтов (при rejected),
        обновлённые статусы требований.
    """
    logger.info(f"record_approval_decision: {package_id} / {stakeholder_name} / {project_name}")

    try:
        req_decisions = json.loads(req_decisions_json)
    except json.JSONDecodeError:
        return "❌ Ошибка: `req_decisions_json` должен быть валидным JSON-списком."

    history = _load_approval_history(project_name)
    package = _get_package(history, package_id)
    if not package:
        return (
            f"❌ Пакет `{package_id}` не найден для проекта `{project_name}`.\n"
            f"Сначала выполните `prepare_approval_package`."
        )

    if package.get("status") == "baselined":
        return f"⚠️ Пакет `{package_id}` уже переведён в baseline. Изменения невозможны."

    repo = _load_repo(project_name)
    req_ids = package["req_ids"]

    # Если req_decisions пуст — применяем общий decision ко всем req
    if not req_decisions:
        if decision == "rejected" and not rejection_reason:
            return "❌ При decision=rejected необходимо указать `rejection_reason`."
        req_decisions = []
        for rid in req_ids:
            rd = {"req_id": rid, "decision": decision}
            if decision == "rejected":
                rd["rejection_reason"] = rejection_reason
            req_decisions.append(rd)

    # Валидация: все req_id из пакета?
    unknown_reqs = [rd["req_id"] for rd in req_decisions if rd["req_id"] not in req_ids]
    if unknown_reqs:
        return (
            f"⚠️ Требования {unknown_reqs} не входят в пакет `{package_id}`.\n"
            f"Пакет содержит: {req_ids}"
        )

    # Валидация conditional
    for rd in req_decisions:
        if rd["decision"] == "conditional":
            if not rd.get("condition_text"):
                return (
                    f"❌ Для conditional-одобрения требования `{rd['req_id']}` "
                    f"необходимо указать `condition_text` в req_decisions."
                )

    # Для req не упомянутых в req_decisions — применяем общий decision
    mentioned = {rd["req_id"] for rd in req_decisions}
    for rid in req_ids:
        if rid not in mentioned:
            rd = {"req_id": rid, "decision": decision}
            if decision == "rejected":
                rd["rejection_reason"] = rejection_reason
            req_decisions.append(rd)

    # Анализ конфликтов при rejected — контекст из 5.3 и 5.4
    conflict_analysis = []
    for rd in req_decisions:
        if rd["decision"] == "rejected":
            req_id = rd["req_id"]
            node = _find_node(repo, req_id)
            conflicts = []

            if node:
                # Проверяем приоритет из 5.3
                priority = node.get("priority", "")
                if priority == "Must":
                    conflicts.append(
                        f"🔴 Приоритет Must (5.3) — отклонение критически важного требования"
                    )
                elif priority in ("Should", "Could"):
                    conflicts.append(f"🟡 Приоритет {priority} (5.3) — рекомендуется пересмотреть необходимость")

                # WSJF-скор если есть
                wsjf = node.get("wsjf_score")
                if wsjf and float(wsjf) > 2.0:
                    conflicts.append(f"🟡 WSJF-скор {wsjf} (5.3) — высокая бизнес-ценность")

            # Проверяем CR из 5.4
            cr_refs = _get_cr_context(repo, req_id)
            open_crs = [c for c in cr_refs if c["status"] in ("open", "under_change")]
            if open_crs:
                cr_list = ", ".join(f"`{c['cr_id']}` ({c['status']})" for c in open_crs)
                conflicts.append(f"🟡 Открытые CR из 5.4: {cr_list} — требование под изменением")

            if conflicts:
                conflict_analysis.append({
                    "req_id": req_id,
                    "stakeholder": stakeholder_name,
                    "raci": stakeholder_raci,
                    "conflicts": conflicts,
                })

    # Сохраняем решение стейкхолдера
    stakeholder_record = {
        "stakeholder_name": stakeholder_name,
        "raci": stakeholder_raci,
        "overall_decision": decision,
        "req_decisions": req_decisions,
        "rejection_reason": rejection_reason,
        "comment": comment,
        "recorded_date": str(date.today()),
    }

    package["stakeholder_decisions"][stakeholder_name] = stakeholder_record
    _save_approval_history(project_name, history)

    # Обновляем статусы требований в репозитории 5.1
    updated_statuses = {}
    for rid in req_ids:
        new_status = _compute_req_status(rid, package)
        node = _find_node(repo, rid)
        if node:
            old_status = node.get("status", "unknown")
            if old_status != new_status:
                node["status"] = new_status
                node.setdefault("history", []).append({
                    "date": str(date.today()),
                    "action": "approval_decision",
                    "from": old_status,
                    "to": new_status,
                    "stakeholder": stakeholder_name,
                    "raci": stakeholder_raci,
                })
            updated_statuses[rid] = new_status

    _save_repo(project_name, repo)

    # Формируем отчёт
    decision_icon = {
        "approved": "✅",
        "conditional": "🟡",
        "rejected": "❌",
        "abstained": "⚪",
    }.get(decision, "—")

    lines = [
        f"<!-- BABOK 5.5 — Approval Decision, Проект: {project_name}, Пакет: {package_id}, "
        f"Стейкхолдер: {stakeholder_name}, Дата: {date.today()} -->",
        "",
        f"## {decision_icon} Решение зафиксировано: {stakeholder_name}",
        "",
        f"**Пакет:** {package_id} | **RACI:** {stakeholder_raci} | **Дата:** {date.today()}",
        f"**Общее решение:** {decision}",
    ]

    if comment:
        lines += [f"**Комментарий:** {comment}", ""]

    # Детали по требованиям
    lines += ["", "### Решения по требованиям", ""]
    for rd in req_decisions:
        rid = rd["req_id"]
        dec = rd["decision"]
        dec_icon = {"approved": "✅", "conditional": "🟡", "rejected": "❌", "abstained": "⚪"}.get(dec, "—")
        node = _find_node(repo, rid)
        title = node.get("title", "—") if node else "—"

        line = f"- {dec_icon} `{rid}` {title}"
        if dec == "conditional":
            line += f"\n  → Условие: {rd.get('condition_text', '—')}"
            if rd.get("condition_deadline"):
                line += f" | Дедлайн: {rd['condition_deadline']}"
            if rd.get("condition_owner"):
                line += f" | Ответственный: {rd['condition_owner']}"
        elif dec == "rejected":
            line += f"\n  → Причина: {rd.get('rejection_reason', rejection_reason or '—')}"
        lines.append(line)

    lines.append("")

    # Конфликты
    if conflict_analysis:
        lines += ["### ⚠️ Обнаруженные конфликты", ""]
        for ca in conflict_analysis:
            lines.append(f"**`{ca['req_id']}`** (отклонено {ca['stakeholder']}, роль: {ca['raci']}):")
            for c in ca["conflicts"]:
                lines.append(f"  - {c}")
        lines += ["", "BA рекомендуется проанализировать конфликты перед созданием baseline.", ""]

    # Совет по RACI при rejected от consulted
    rejected_req_ids = [rd["req_id"] for rd in req_decisions if rd["decision"] == "rejected"]
    if rejected_req_ids and stakeholder_raci == "consulted":
        lines += [
            f"ℹ️ **Роль {stakeholder_name} — Consulted.** Rejected от C не блокирует baseline.",
            "Задокументируйте несогласие как управляемый риск в `check_approval_status`.",
            "",
        ]

    # Обновлённые статусы
    lines += ["### Статусы требований после решения", ""]
    for rid, status in updated_statuses.items():
        status_icon = {
            STATUS_APPROVED: "✅",
            STATUS_CONDITIONAL: "🟡",
            STATUS_REJECTED: "❌",
            STATUS_PENDING: "⏳",
        }.get(status, "—")
        lines.append(f"- {status_icon} `{rid}` → `{status}`")

    lines += [
        "",
        "---",
        "",
        "## ➡️ Следующий шаг",
        "",
    ]

    has_conditional = any(rd["decision"] == "conditional" for rd in req_decisions)
    if has_conditional:
        lines += [
            "Есть условные одобрения. После выполнения условий вызовите `close_approval_condition`.",
            "Затем проверьте готовность пакета через `check_approval_status`.",
        ]
    else:
        lines += [
            "Запишите решения остальных стейкхолдеров через `record_approval_decision`.",
            "После всех решений — проверьте готовность через `check_approval_status`.",
        ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 5.5.3 — Закрыть условие (Conditional)
# ---------------------------------------------------------------------------

@mcp.tool()
def close_approval_condition(
    project_name: str,
    package_id: str,
    req_id: str,
    stakeholder_name: str,
    resolution_notes: str,
) -> str:
    """
    BABOK 5.5 — Шаг 3 (при необходимости): Закрыть выполненное условие.

    После выполнения условия conditional-одобрения обновляет статус
    требования с conditional_approved на approved.

    Args:
        project_name:      Название проекта.
        package_id:        ID пакета.
        req_id:            ID требования с открытым условием.
        stakeholder_name:  Имя стейкхолдера, выставившего условие.
        resolution_notes:  Как условие было закрыто (что конкретно изменилось).

    Returns:
        Подтверждение закрытия условия, обновлённый статус требования.
    """
    logger.info(f"close_approval_condition: {package_id} / {req_id} / {project_name}")

    history = _load_approval_history(project_name)
    package = _get_package(history, package_id)
    if not package:
        return f"❌ Пакет `{package_id}` не найден. Сначала выполните `prepare_approval_package`."

    sh_data = package["stakeholder_decisions"].get(stakeholder_name)
    if not sh_data:
        return (
            f"❌ Стейкхолдер `{stakeholder_name}` не найден в пакете `{package_id}`.\n"
            f"Доступные стейкхолдеры: {list(package['stakeholder_decisions'].keys())}"
        )

    # Ищем conditional-решение по req_id
    condition_found = False
    for rd in sh_data["req_decisions"]:
        if rd["req_id"] == req_id and rd["decision"] == "conditional":
            if rd.get("condition_closed"):
                return f"⚠️ Условие по `{req_id}` от `{stakeholder_name}` уже закрыто."
            rd["condition_closed"] = True
            rd["condition_closed_date"] = str(date.today())
            rd["resolution_notes"] = resolution_notes
            condition_found = True
            break

    if not condition_found:
        return (
            f"❌ Открытое условие по требованию `{req_id}` от `{stakeholder_name}` не найдено.\n"
            f"Проверьте req_id и stakeholder_name."
        )

    _save_approval_history(project_name, history)

    # Пересчитываем статус требования
    repo = _load_repo(project_name)
    node = _find_node(repo, req_id)
    new_status = _compute_req_status(req_id, package)
    if node:
        old_status = node.get("status", "unknown")
        node["status"] = new_status
        node.setdefault("history", []).append({
            "date": str(date.today()),
            "action": "condition_closed",
            "from": old_status,
            "to": new_status,
            "stakeholder": stakeholder_name,
            "resolution_notes": resolution_notes,
        })
    _save_repo(project_name, repo)

    status_icon = "✅" if new_status == STATUS_APPROVED else "🟡"

    return "\n".join([
        f"<!-- BABOK 5.5 — Condition Closed, Проект: {project_name}, "
        f"Пакет: {package_id}, Требование: {req_id}, Дата: {date.today()} -->",
        "",
        f"## ✅ Условие закрыто: {req_id}",
        "",
        f"**Стейкхолдер:** {stakeholder_name}  ",
        f"**Дата закрытия:** {date.today()}  ",
        f"**Описание:** {resolution_notes}  ",
        "",
        f"**Новый статус требования:** {status_icon} `{new_status}`",
        "",
        "---",
        "",
        "## ➡️ Следующий шаг",
        "",
        f"Проверьте готовность пакета `{package_id}` через `check_approval_status`.",
    ])


# ---------------------------------------------------------------------------
# 5.5.4 — Дашборд готовности к baseline
# ---------------------------------------------------------------------------

@mcp.tool()
def check_approval_status(
    project_name: str,
    package_id: str,
) -> str:
    """
    BABOK 5.5 — Шаг 4: Дашборд готовности пакета к созданию baseline.

    Анализирует все решения стейкхолдеров и даёт вердикт:
    готов / не готов к baseline.

    Args:
        project_name:  Название проекта.
        package_id:    ID пакета.

    Returns:
        Полный статус пакета: статистика одобрений, блокеры, открытые условия,
        вердикт готовности к baseline.
    """
    logger.info(f"check_approval_status: {package_id} / {project_name}")

    history = _load_approval_history(project_name)
    package = _get_package(history, package_id)
    if not package:
        return f"❌ Пакет `{package_id}` не найден. Сначала выполните `prepare_approval_package`."

    repo = _load_repo(project_name)
    req_ids = package["req_ids"]

    # Собираем статусы всех требований
    req_statuses = {}
    for rid in req_ids:
        node = _find_node(repo, rid)
        current_status = node.get("status", STATUS_PENDING) if node else STATUS_PENDING
        computed_status = _compute_req_status(rid, package)
        req_statuses[rid] = computed_status

    # Статистика
    counts = {
        STATUS_APPROVED: 0,
        STATUS_CONDITIONAL: 0,
        STATUS_REJECTED: 0,
        STATUS_PENDING: 0,
    }
    for status in req_statuses.values():
        counts[status] = counts.get(status, 0) + 1

    total = len(req_ids)
    approved_pct = round(counts[STATUS_APPROVED] / total * 100) if total else 0

    # Блокеры: rejected от accountable/responsible
    blockers = []
    for sh_name, sh_data in package["stakeholder_decisions"].items():
        if sh_data["raci"] in ("accountable", "responsible"):
            for rd in sh_data["req_decisions"]:
                if rd["decision"] == "rejected":
                    node = _find_node(repo, rd["req_id"])
                    title = node.get("title", "—") if node else "—"
                    blockers.append({
                        "req_id": rd["req_id"],
                        "title": title,
                        "stakeholder": sh_name,
                        "raci": sh_data["raci"],
                        "reason": rd.get("rejection_reason", "—"),
                    })

    # Открытые conditional
    open_conditions = []
    overdue_conditions = []
    today = date.today()
    for sh_name, sh_data in package["stakeholder_decisions"].items():
        for rd in sh_data["req_decisions"]:
            if rd["decision"] == "conditional" and not rd.get("condition_closed"):
                condition_entry = {
                    "req_id": rd["req_id"],
                    "stakeholder": sh_name,
                    "condition_text": rd.get("condition_text", "—"),
                    "condition_deadline": rd.get("condition_deadline", ""),
                    "condition_owner": rd.get("condition_owner", "—"),
                }
                open_conditions.append(condition_entry)
                # Проверяем просрочку
                if rd.get("condition_deadline"):
                    try:
                        deadline = date.fromisoformat(rd["condition_deadline"])
                        if deadline < today:
                            condition_entry["overdue"] = True
                            overdue_conditions.append(condition_entry)
                    except ValueError:
                        pass

    # Стейкхолдеры без решения (если пакет был отправлен, но ответа нет)
    # Мы не храним "ожидаемый список" — показываем тех кто ответил
    responding_stakeholders = list(package["stakeholder_decisions"].keys())

    # Вердикт
    can_baseline = True
    verdict_reasons = []

    if blockers:
        can_baseline = False
        verdict_reasons.append(f"🔴 {len(blockers)} отклонений от Accountable/Responsible стейкхолдеров")

    if overdue_conditions:
        can_baseline = False
        verdict_reasons.append(f"🔴 {len(overdue_conditions)} просроченных условий")

    if open_conditions and not overdue_conditions:
        # Не блокирует, но предупреждаем
        verdict_reasons.append(f"🟡 {len(open_conditions)} открытых условий (не просрочены)")

    if counts[STATUS_PENDING] > 0:
        can_baseline = False
        verdict_reasons.append(f"🔴 {counts[STATUS_PENDING]} требований ещё в статусе pending_approval")

    if approved_pct < 70:
        can_baseline = False
        verdict_reasons.append(f"🔴 Только {approved_pct}% требований одобрено (минимум 70%)")

    # Consulted-rejected (не блокирует, но отмечаем)
    consulted_rejected = []
    for sh_name, sh_data in package["stakeholder_decisions"].items():
        if sh_data["raci"] == "consulted":
            for rd in sh_data["req_decisions"]:
                if rd["decision"] == "rejected":
                    consulted_rejected.append({
                        "req_id": rd["req_id"],
                        "stakeholder": sh_name,
                        "reason": rd.get("rejection_reason", "—"),
                    })

    # Формируем отчёт
    verdict_icon = "✅" if can_baseline else ("🟡" if not blockers and not counts[STATUS_PENDING] else "🔴")

    lines = [
        f"<!-- BABOK 5.5 — Approval Status, Проект: {project_name}, Пакет: {package_id}, Дата: {date.today()} -->",
        "",
        f"## 📊 Статус пакета: {package_id} — {package.get('package_title', '—')}",
        "",
        f"**Проект:** {project_name} | **Дата:** {date.today()}",
        f"**Методология:** {package.get('approach', '—')}",
        f"**Стейкхолдеры ответили:** {', '.join(responding_stakeholders) if responding_stakeholders else '(нет ответов)'}",
        "",
        "### Статистика одобрений",
        "",
        f"| Статус | Кол-во | % |",
        f"|--------|--------|---|",
        f"| ✅ Approved | {counts[STATUS_APPROVED]} | {approved_pct}% |",
        f"| 🟡 Conditional (открытые условия) | {counts[STATUS_CONDITIONAL]} | {round(counts[STATUS_CONDITIONAL]/total*100) if total else 0}% |",
        f"| ❌ Rejected | {counts[STATUS_REJECTED]} | {round(counts[STATUS_REJECTED]/total*100) if total else 0}% |",
        f"| ⏳ Pending | {counts[STATUS_PENDING]} | {round(counts[STATUS_PENDING]/total*100) if total else 0}% |",
        f"| **Итого** | **{total}** | **100%** |",
        "",
    ]

    if blockers:
        lines += ["### 🔴 Блокеры (Rejected от Accountable/Responsible)", ""]
        for b in blockers:
            lines.append(f"- `{b['req_id']}` {b['title']} — отклонено `{b['stakeholder']}` ({b['raci']}): {b['reason']}")
        lines.append("")

    if open_conditions:
        lines += ["### 🟡 Открытые условия (Conditional)", ""]
        for c in open_conditions:
            overdue_flag = " ⚠️ ПРОСРОЧЕНО" if c.get("overdue") else ""
            deadline_str = f" | Дедлайн: {c['condition_deadline']}{overdue_flag}" if c['condition_deadline'] else ""
            lines.append(
                f"- `{c['req_id']}` — {c['condition_text']}"
                f"{deadline_str} | Ответственный: {c['condition_owner']}"
            )
        lines.append("")

    if consulted_rejected:
        lines += ["### ℹ️ Отклонения от Consulted (не блокируют baseline)", ""]
        for cr in consulted_rejected:
            lines.append(f"- `{cr['req_id']}` — отклонено `{cr['stakeholder']}` (consulted): {cr['reason']}")
        lines += ["", "Рекомендуется задокументировать как управляемый риск.", ""]

    # Вердикт
    lines += [
        "---",
        "",
        f"## {verdict_icon} Вердикт: {'Готов к baseline' if can_baseline else 'Не готов к baseline'}",
        "",
    ]

    if verdict_reasons:
        for reason in verdict_reasons:
            lines.append(f"- {reason}")
        lines.append("")

    if can_baseline:
        lines += [
            "Все обязательные условия выполнены. Можно создавать Requirements Baseline.",
            "",
            "➡️ Вызовите `create_requirements_baseline`:",
            f"  - `project_name`: \"{project_name}\"",
            f"  - `package_id`: \"{package_id}\"",
            f"  - `baseline_version`: \"v1.0\" (или sprint-N для agile)",
            f"  - `decided_by`: уполномоченный стейкхолдер",
        ]
    else:
        lines += ["Устраните блокеры перед созданием baseline."]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 5.5.5 — Создать Requirements Baseline
# ---------------------------------------------------------------------------

@mcp.tool()
def create_requirements_baseline(
    project_name: str,
    package_id: str,
    baseline_version: str,
    decided_by: str,
    force: bool = False,
) -> str:
    """
    BABOK 5.5 — Шаг 5: Создать official Requirements Baseline.

    Фиксирует snapshot пакета в {project}_approval_history.json.
    Обновляет статусы требований в репозитории 5.1 на 'approved'.
    Генерирует Approval Record (Markdown) через save_artifact.

    Args:
        project_name:      Название проекта.
        package_id:        ID пакета (должен пройти check_approval_status).
        baseline_version:  Версия baseline: v1.0, v1.1, sprint-5 и т.д.
        decided_by:        Кто подтверждает создание baseline (спонсор / PO).
        force:             True — создать baseline даже при наличии предупреждений
                           (open conditions, consulted-rejected).
                           False (по умолчанию) — блокировать при наличии блокеров.

    Returns:
        Approval Record (Markdown), сохранённый через save_artifact.
        Обновлённые статусы approved в репозитории 5.1.
    """
    logger.info(f"create_requirements_baseline: {package_id} / {baseline_version} / {project_name}")

    history = _load_approval_history(project_name)
    package = _get_package(history, package_id)
    if not package:
        return f"❌ Пакет `{package_id}` не найден. Сначала выполните `prepare_approval_package`."

    if package.get("status") == "baselined":
        return (
            f"⚠️ Пакет `{package_id}` уже имеет baseline `{package.get('baseline_version')}`.\n"
            f"Для нового baseline создайте новый пакет с другим package_id."
        )

    repo = _load_repo(project_name)
    req_ids = package["req_ids"]

    # Проверяем блокеры
    blockers = []
    for sh_name, sh_data in package["stakeholder_decisions"].items():
        if sh_data["raci"] in ("accountable", "responsible"):
            for rd in sh_data["req_decisions"]:
                if rd["decision"] == "rejected":
                    blockers.append(f"`{rd['req_id']}` отклонено {sh_name} ({sh_data['raci']})")

    pending_reqs = [
        rid for rid in req_ids
        if _compute_req_status(rid, package) == STATUS_PENDING
    ]

    if (blockers or pending_reqs) and not force:
        lines = ["❌ Baseline заблокирован:", ""]
        if blockers:
            lines.append("**Отклонения от Accountable/Responsible:**")
            for b in blockers:
                lines.append(f"  - {b}")
        if pending_reqs:
            lines.append(f"**Требования в статусе pending_approval:** {pending_reqs}")
        lines += [
            "",
            "Устраните блокеры или используйте `force=true` для принудительного создания baseline.",
        ]
        return "\n".join(lines)

    # Проверяем открытые conditional (предупреждения, не блокируют при force)
    open_conditions = []
    for sh_name, sh_data in package["stakeholder_decisions"].items():
        for rd in sh_data["req_decisions"]:
            if rd["decision"] == "conditional" and not rd.get("condition_closed"):
                open_conditions.append({
                    "req_id": rd["req_id"],
                    "stakeholder": sh_name,
                    "condition_text": rd.get("condition_text", "—"),
                    "condition_deadline": rd.get("condition_deadline", ""),
                })

    # Обновляем статусы approved требований в репозитории 5.1
    approved_reqs = []
    for rid in req_ids:
        status = _compute_req_status(rid, package)
        node = _find_node(repo, rid)
        if node:
            if status == STATUS_APPROVED:
                node["status"] = STATUS_APPROVED
                approved_reqs.append(rid)
                node.setdefault("history", []).append({
                    "date": str(date.today()),
                    "action": "baselined",
                    "baseline_version": baseline_version,
                    "decided_by": decided_by,
                })
            elif status == STATUS_CONDITIONAL and force:
                node["status"] = STATUS_CONDITIONAL
                node.setdefault("history", []).append({
                    "date": str(date.today()),
                    "action": "baselined_with_open_condition",
                    "baseline_version": baseline_version,
                    "decided_by": decided_by,
                })

    _save_repo(project_name, repo)

    # Snapshot baseline в approval_history
    baseline_snapshot = {
        "baseline_version": baseline_version,
        "package_id": package_id,
        "package_title": package.get("package_title", "—"),
        "approach": package.get("approach", "—"),
        "created_date": str(date.today()),
        "decided_by": decided_by,
        "approved_req_ids": approved_reqs,
        "open_conditions": open_conditions,
        "force_created": force and bool(blockers or open_conditions),
        "stakeholder_summary": {
            sh_name: {
                "raci": sh_data["raci"],
                "overall_decision": sh_data["overall_decision"],
                "recorded_date": sh_data.get("recorded_date", "—"),
            }
            for sh_name, sh_data in package["stakeholder_decisions"].items()
        },
    }

    history["baselines"].append(baseline_snapshot)
    package["status"] = "baselined"
    package["baseline_version"] = baseline_version
    _save_approval_history(project_name, history)

    # Генерируем Approval Record
    approach_label = "Predictive / Waterfall" if package.get("approach") == "predictive" else "Agile"
    force_warning = "\n\n> ⚠️ Baseline создан принудительно (force=true). Имеются открытые условия." if force and open_conditions else ""

    record_lines = [
        f"<!-- BABOK 5.5 — Approval Record, Проект: {project_name}, "
        f"Baseline: {baseline_version}, Дата: {date.today()} -->",
        "",
        f"# Requirements Baseline: {baseline_version}",
        f"**Проект:** {project_name}  ",
        f"**Пакет:** {package_id} — {package.get('package_title', '—')}  ",
        f"**Методология:** {approach_label}  ",
        f"**Дата создания:** {date.today()}  ",
        f"**Подтвердил:** {decided_by}  ",
        f"**Требований в baseline:** {len(approved_reqs)}  ",
        force_warning,
        "",
        "---",
        "",
        "## Одобренные требования",
        "",
    ]

    for rid in approved_reqs:
        node = _find_node(repo, rid)
        title = node.get("title", "—") if node else "—"
        version = node.get("version", "—") if node else "—"
        priority = node.get("priority", "—") if node else "—"
        record_lines.append(f"- ✅ `{rid}` {title} (v{version}, приоритет: {priority})")

    record_lines += ["", "---", "", "## Решения стейкхолдеров", ""]
    for sh_name, sh_summary in baseline_snapshot["stakeholder_summary"].items():
        icon = {"approved": "✅", "conditional": "🟡", "rejected": "❌", "abstained": "⚪"}.get(
            sh_summary["overall_decision"], "—"
        )
        record_lines.append(
            f"- {icon} **{sh_name}** ({sh_summary['raci']}) — "
            f"{sh_summary['overall_decision']} ({sh_summary['recorded_date']})"
        )

    if open_conditions:
        record_lines += ["", "---", "", "## 🟡 Открытые условия (risk)", ""]
        for oc in open_conditions:
            record_lines.append(
                f"- `{oc['req_id']}` — {oc['condition_text']}"
                + (f" | Дедлайн: {oc['condition_deadline']}" if oc['condition_deadline'] else "")
            )
        record_lines += [
            "",
            "> Условия должны быть закрыты через `close_approval_condition` "
            "и зафиксированы в следующем baseline.",
        ]

    record_lines += [
        "",
        "---",
        "",
        "## Следующие шаги",
        "",
        f"1. Передать Approval Record стейкхолдерам через `prepare_communication_package` (4.4)",
        f"2. Передать список approved требований в разработку (Глава 6)",
        f"3. Любые изменения approved требований — только через `open_cr` (5.4)",
        "",
        "---",
        "",
        "*Сгенерировано: AInalyst BABOK 5.5*",
    ]

    artifact_content = "\n".join(record_lines)
    save_path = save_artifact(artifact_content, prefix=f"5_5_approval_record_{baseline_version}")

    # Финальный вывод
    output_lines = [
        f"## ✅ Requirements Baseline создан: {baseline_version}",
        "",
        f"**Проект:** {project_name} | **Пакет:** {package_id}  ",
        f"**Подтвердил:** {decided_by} | **Дата:** {date.today()}  ",
        f"**Одобрено требований:** {len(approved_reqs)} из {len(req_ids)}",
        "",
    ]

    if open_conditions and force:
        output_lines += [
            f"⚠️ Baseline создан с {len(open_conditions)} открытыми условиями.",
            "Необходимо закрыть их через `close_approval_condition`.",
            "",
        ]

    output_lines += [
        "### Следующие шаги",
        "",
        "1. Передать Approval Record стейкхолдерам через `prepare_communication_package` (4.4)",
        "2. Передать список approved требований в разработку (Глава 6)",
        "3. Любые изменения approved требований — только через `open_cr` (5.4)",
        "",
        save_path,
    ]

    return "\n".join(output_lines)


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
