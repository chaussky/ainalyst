"""
BABOK 5.3 — Prioritize Requirements
MCP-инструменты для приоритизации требований и дизайнов.

Инструменты:
  - start_prioritization_session  — открыть сессию, выбрать метод, получить список требований
  - add_stakeholder_scores        — добавить оценки одного стейкхолдера
  - run_aggregation               — агрегировать оценки, выявить конфликты и dependency violations
  - resolve_conflict              — зафиксировать решение по конфликту
  - save_prioritization_result    — финализировать сессию, обновить репозиторий 5.1

Хранение:
  - Приоритеты пишутся в {project}_traceability_repo.json (поле priority в каждом требовании)
  - Снапшоты сессий хранятся в {project}_prioritization.json

Интеграция:
  Вход:  репозиторий 5.1 (зависимости), атрибуты 5.2 (стабильность), реестр 4.2 (influence)
  Выход: приоритизированные требования → 6.3 (Оценка рисков)

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date, datetime
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import save_artifact, logger, DATA_DIR

mcp = FastMCP("BABOK_Requirements_Prioritize")

REPO_FILENAME = "traceability_repo.json"
PRIO_FILENAME = "prioritization.json"

# MoSCoW числовые веса для агрегации
MOSCOW_WEIGHTS = {"Must": 4, "Should": 3, "Could": 2, "Won't": 1}
MOSCOW_THRESHOLDS = [("Must", 3.5), ("Should", 2.5), ("Could", 1.5), ("Won't", 0.0)]

# Influence веса для взвешенного голосования
INFLUENCE_WEIGHTS = {"High": 3, "Medium": 2, "Low": 1}

# Порог Must Inflation
MUST_INFLATION_THRESHOLD = 0.6

# Стабильность — пороги minor-версии (совпадают с 5.2)
VOLATILITY_WARNING = 3   # 1.3+
VOLATILITY_CRITICAL = 4  # 1.4+


# ---------------------------------------------------------------------------
# Утилиты — файловый слой
# ---------------------------------------------------------------------------

def _repo_path(project_name: str) -> str:
    safe = project_name.lower().replace(" ", "_")
    return os.path.join(DATA_DIR, f"{safe}_{REPO_FILENAME}")


def _prio_path(project_name: str) -> str:
    safe = project_name.lower().replace(" ", "_")
    return os.path.join(DATA_DIR, f"{safe}_{PRIO_FILENAME}")


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


def _load_prio(project_name: str) -> dict:
    path = _prio_path(project_name)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"project": project_name, "sessions": []}


def _save_prio(project_name: str, prio: dict) -> None:
    path = _prio_path(project_name)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(prio, f, ensure_ascii=False, indent=2)


def _find_session(sessions: list, label: str) -> Optional[dict]:
    for s in sessions:
        if s["label"] == label:
            return s
    return None


# ---------------------------------------------------------------------------
# Утилиты — логика методов
# ---------------------------------------------------------------------------

def _minor_version(version_str: str) -> int:
    """Извлекает minor-часть версии: '1.3' → 3"""
    try:
        parts = str(version_str).split(".")
        if len(parts) >= 2:
            return int(parts[1])
        return 0
    except (ValueError, IndexError):
        return 0


def _stability_flag(node: dict) -> Optional[str]:
    """Возвращает флаг стабильности или None если всё ок."""
    version = node.get("version", "1.0")
    minor = _minor_version(version)
    if minor >= VOLATILITY_CRITICAL:
        return "critical"
    if minor >= VOLATILITY_WARNING:
        return "warning"
    if node.get("stability") == "Unknown":
        return "unknown"
    return None


def _aggregate_moscow(scores_by_sh: dict, influence_by_sh: dict) -> dict:
    """
    Агрегирует MoSCoW-оценки нескольких стейкхолдеров с весами influence.
    Возвращает {req_id: {"priority": "Must"|..., "weighted_score": float}}
    """
    # Собираем все req_id
    all_reqs = set()
    for sh_scores in scores_by_sh.values():
        all_reqs.update(sh_scores.keys())

    result = {}
    for req_id in all_reqs:
        total_weight = 0.0
        weighted_sum = 0.0
        for sh_id, sh_scores in scores_by_sh.items():
            if req_id not in sh_scores:
                continue
            raw = sh_scores[req_id]
            score = MOSCOW_WEIGHTS.get(raw, 2)
            weight = INFLUENCE_WEIGHTS.get(influence_by_sh.get(sh_id, "Medium"), 2)
            weighted_sum += score * weight
            total_weight += weight

        if total_weight == 0:
            result[req_id] = {"priority": "Could", "weighted_score": 2.0}
            continue

        ws = weighted_sum / total_weight
        priority = "Won't"
        for label, threshold in MOSCOW_THRESHOLDS:
            if ws >= threshold:
                priority = label
                break
        result[req_id] = {"priority": priority, "weighted_score": round(ws, 2)}

    return result


def _aggregate_wsjf(scores_by_sh: dict, influence_by_sh: dict) -> dict:
    """
    Агрегирует WSJF-оценки.
    scores_by_sh[sh_id][req_id] = {"bv": N, "tc": N, "rr": N, "js": N}
    Возвращает {req_id: {"priority_score": float, "wsjf": float, "cod": float, "js": float}}
    """
    all_reqs = set()
    for sh_scores in scores_by_sh.values():
        all_reqs.update(sh_scores.keys())

    result = {}
    for req_id in all_reqs:
        bv_sum = tc_sum = rr_sum = js_sum = 0.0
        total_weight = 0.0

        for sh_id, sh_scores in scores_by_sh.items():
            if req_id not in sh_scores:
                continue
            s = sh_scores[req_id]
            weight = INFLUENCE_WEIGHTS.get(influence_by_sh.get(sh_id, "Medium"), 2)
            bv_sum += s.get("bv", 0) * weight
            tc_sum += s.get("tc", 0) * weight
            rr_sum += s.get("rr", 0) * weight
            # Job Size — техническая оценка, не взвешивается по influence
            js_sum += s.get("js", 1)
            total_weight += weight

        if total_weight == 0:
            continue

        cod = (bv_sum + tc_sum + rr_sum) / total_weight
        # JS усредняем по числу стейкхолдеров кто его дал
        n_sh = sum(1 for sh_scores in scores_by_sh.values() if req_id in sh_scores)
        js = js_sum / n_sh if n_sh > 0 else 1.0
        wsjf = round(cod / js, 2) if js > 0 else 0.0

        result[req_id] = {
            "priority_score": wsjf,
            "wsjf": wsjf,
            "cod": round(cod, 2),
            "js": round(js, 2),
        }

    # Нормализуем в MoSCoW-совместимые метки для единообразия
    if result:
        scores = [v["wsjf"] for v in result.values()]
        max_s = max(scores) if scores else 1
        for req_id, v in result.items():
            ratio = v["wsjf"] / max_s if max_s > 0 else 0
            if ratio >= 0.7:
                v["priority"] = "Must"
            elif ratio >= 0.4:
                v["priority"] = "Should"
            elif ratio >= 0.2:
                v["priority"] = "Could"
            else:
                v["priority"] = "Won't"

    return result


def _aggregate_impact_effort(scores_by_sh: dict, influence_by_sh: dict,
                              quadrant_mapping: dict) -> dict:
    """
    Агрегирует Impact/Effort оценки.
    scores_by_sh[sh_id][req_id] = {"impact": "High"|"Medium"|"Low", "effort": ...}
    quadrant_mapping: {"QuickWins": "Must", "BigBets": "Should", ...}
    """
    level_num = {"High": 3, "Medium": 2, "Low": 1}
    all_reqs = set()
    for sh_scores in scores_by_sh.values():
        all_reqs.update(sh_scores.keys())

    result = {}
    for req_id in all_reqs:
        imp_sum = eff_sum = total_weight = 0.0

        for sh_id, sh_scores in scores_by_sh.items():
            if req_id not in sh_scores:
                continue
            s = sh_scores[req_id]
            weight = INFLUENCE_WEIGHTS.get(influence_by_sh.get(sh_id, "Medium"), 2)
            imp_sum += level_num.get(s.get("impact", "Medium"), 2) * weight
            eff_sum += level_num.get(s.get("effort", "Medium"), 2) * weight
            total_weight += weight

        if total_weight == 0:
            continue

        avg_imp = imp_sum / total_weight
        avg_eff = eff_sum / total_weight

        # Определяем квадрант
        if avg_imp >= 2.5 and avg_eff < 2.5:
            quadrant = "QuickWins"
        elif avg_imp >= 2.5 and avg_eff >= 2.5:
            quadrant = "BigBets"
        elif avg_imp < 2.5 and avg_eff < 2.5:
            quadrant = "FillIns"
        else:
            quadrant = "ThanklessTasks"

        priority = quadrant_mapping.get(quadrant, "Could")
        result[req_id] = {
            "priority": priority,
            "quadrant": quadrant,
            "avg_impact": round(avg_imp, 2),
            "avg_effort": round(avg_eff, 2),
        }

    return result


def _find_dependency_violations(repo: dict, priorities: dict) -> list:
    """
    Ищет dependency violations: требование с Must/Should зависит от требования с более низким приоритетом.
    Возвращает список {"req_id", "depends_on", "req_priority", "dep_priority"}
    """
    violations = []
    order = {"Must": 4, "Should": 3, "Could": 2, "Won't": 1}

    for edge in repo.get("links", []):
        if edge.get("relation") != "depends":
            continue
        from_id = edge.get("from")
        to_id = edge.get("to")
        from_prio = priorities.get(from_id, {}).get("priority") if isinstance(
            priorities.get(from_id), dict) else priorities.get(from_id)
        to_prio = priorities.get(to_id, {}).get("priority") if isinstance(
            priorities.get(to_id), dict) else priorities.get(to_id)

        if from_prio and to_prio:
            if order.get(from_prio, 0) > order.get(to_prio, 0):
                violations.append({
                    "req_id": from_id,
                    "depends_on": to_id,
                    "req_priority": from_prio,
                    "dep_priority": to_prio,
                })
    return violations


def _detect_stakeholder_conflicts(scores_by_sh: dict, method: str) -> list:
    """
    Ищет конфликты между стейкхолдерами.
    MoSCoW: расхождение ≥ 2 категории.
    Возвращает список {"req_id", "conflict_type", "scores", "severity"}
    """
    if method != "MoSCoW":
        return []  # для WSJF и IE конфликты через агрегацию

    order = {"Must": 4, "Should": 3, "Could": 2, "Won't": 1}
    conflicts = []

    all_reqs = set()
    for sh_scores in scores_by_sh.values():
        all_reqs.update(sh_scores.keys())

    for req_id in all_reqs:
        req_scores = {sh_id: sh_scores[req_id]
                      for sh_id, sh_scores in scores_by_sh.items()
                      if req_id in sh_scores}
        if len(req_scores) < 2:
            continue

        values = [order.get(v, 2) for v in req_scores.values()]
        spread = max(values) - min(values)
        if spread >= 2:
            severity = "🔴 Критическое" if spread >= 3 else "🟠 Серьёзное"
            conflicts.append({
                "req_id": req_id,
                "conflict_type": "stakeholder_conflict",
                "scores": req_scores,
                "spread": spread,
                "severity": severity,
                "resolved": False,
                "resolution": None,
            })

    return conflicts


def _check_must_inflation(priorities: dict) -> dict:
    """Проверяет Must Inflation. Возвращает {"inflated": bool, "must_ratio": float}"""
    if not priorities:
        return {"inflated": False, "must_ratio": 0.0}
    must_count = sum(1 for v in priorities.values()
                     if (v.get("priority") if isinstance(v, dict) else v) == "Must")
    ratio = must_count / len(priorities)
    return {"inflated": ratio > MUST_INFLATION_THRESHOLD, "must_ratio": round(ratio, 2)}


# ---------------------------------------------------------------------------
# MCP-инструменты
# ---------------------------------------------------------------------------

@mcp.tool()
def start_prioritization_session(
    project_name: str,
    session_label: str,
    method: Literal["MoSCoW", "WSJF", "ImpactEffort"],
    wsjf_scale: Literal["Fibonacci", "Linear"] = "Fibonacci",
    quadrant_mapping_json: str = "",
) -> str:
    """
    Открыть новую сессию приоритизации.

    Читает требования из репозитория 5.1, проверяет стабильность (5.2),
    подготавливает список требований для оценки.

    Параметры:
    - project_name: название проекта (должен совпадать с именем в 5.1)
    - session_label: метка сессии, например "MVP scope" или "Sprint 3 planning"
    - method: метод приоритизации — MoSCoW / WSJF / ImpactEffort
    - wsjf_scale: шкала для WSJF — Fibonacci (1,2,3,5,8,13) или Linear (1-10)
    - quadrant_mapping_json: JSON маппинг квадрантов для ImpactEffort.
      Формат: {"QuickWins": "Must", "BigBets": "Should", "FillIns": "Could", "ThanklessTasks": "Won't"}
      Если пусто — используется дефолтный маппинг.
    """
    logger.info(f"5.3 start_prioritization_session: {project_name} / {session_label}")

    repo = _load_repo(project_name)
    prio_data = _load_prio(project_name)

    # Проверяем что сессия с таким именем не существует
    existing = _find_session(prio_data["sessions"], session_label)
    if existing:
        return (f"⚠️ Сессия '{session_label}' уже существует для проекта '{project_name}'.\n"
                f"Используйте другое название или продолжите работу с существующей сессией.")

    # Дефолтный маппинг квадрантов
    default_qmap = {
        "QuickWins": "Must",
        "BigBets": "Should",
        "FillIns": "Could",
        "ThanklessTasks": "Won't",
    }
    quadrant_mapping = default_qmap
    if quadrant_mapping_json.strip():
        try:
            quadrant_mapping = {**default_qmap, **json.loads(quadrant_mapping_json)}
        except json.JSONDecodeError:
            return "❌ Ошибка парсинга quadrant_mapping_json. Проверьте формат JSON."

    # Получаем требования из репозитория
    nodes = [n for n in repo.get("requirements", []) if n.get("status") != "deprecated"]
    if not nodes:
        return (f"⚠️ Репозиторий '{project_name}' не содержит требований или не существует.\n"
                f"Сначала создайте репозиторий через 5.1 (init_traceability_repo).")

    # Проверяем стабильность
    stability_warnings = []
    stability_critical = []
    for node in nodes:
        flag = _stability_flag(node)
        if flag == "critical":
            stability_critical.append(node["id"])
        elif flag in ("warning", "unknown"):
            stability_warnings.append(node["id"])

    # Создаём сессию
    session = {
        "label": session_label,
        "method": method,
        "wsjf_scale": wsjf_scale if method == "WSJF" else None,
        "quadrant_mapping": quadrant_mapping if method == "ImpactEffort" else None,
        "date": str(date.today()),
        "status": "open",
        "stakeholder_scores": {},
        "conflicts": [],
        "dependency_violations": [],
        "aggregated": {},
        "result": {},
    }
    prio_data["sessions"].append(session)
    _save_prio(project_name, prio_data)

    # Формируем отчёт
    lines = [
        f"<!-- BABOK 5.3 — Prioritize Requirements, Проект: {project_name}, "
        f"Сессия: {session_label}, Метод: {method}, Дата: {date.today()} -->",
        "",
        f"# Сессия приоритизации: {session_label}",
        f"**Проект:** {project_name}  ",
        f"**Метод:** {method}  ",
        f"**Дата открытия:** {date.today()}",
        "",
        "---",
        "",
        f"## Требования для оценки ({len(nodes)} шт.)",
        "",
    ]

    if method == "MoSCoW":
        lines.append("| ID | Название | Тип | Текущий приоритет | Stability |")
        lines.append("|-----|----------|-----|-------------------|-----------|")
        for n in nodes:
            flag = _stability_flag(n)
            stab_icon = {"critical": "🔴 Критично", "warning": "🟡 Внимание",
                         "unknown": "🟡 Unknown"}.get(flag, "🟢 Stable")
            lines.append(f"| {n['id']} | {n.get('title','—')} | {n.get('type','—')} "
                         f"| {n.get('priority','—')} | {stab_icon} |")
    elif method == "WSJF":
        lines.append(f"**Шкала:** {wsjf_scale}  ")
        if wsjf_scale == "Fibonacci":
            lines.append("**Значения:** 1, 2, 3, 5, 8, 13 (относительные, выберите эталон = 3)")
        else:
            lines.append("**Значения:** 1–10 (абсолютные)")
        lines.append("")
        lines.append("| ID | Название | Компоненты для оценки: BV, TC, RR, JS |")
        lines.append("|-----|----------|---------------------------------------|")
        for n in nodes:
            lines.append(f"| {n['id']} | {n.get('title','—')} | BV=?, TC=?, RR=?, JS=? |")
    else:  # ImpactEffort
        lines.append("**Маппинг квадрантов:**")
        for q, p in quadrant_mapping.items():
            q_label = {"QuickWins": "Quick Wins (High Impact, Low Effort)",
                       "BigBets": "Big Bets (High Impact, High Effort)",
                       "FillIns": "Fill-ins (Low Impact, Low Effort)",
                       "ThanklessTasks": "Thankless Tasks (Low Impact, High Effort)"}.get(q, q)
            lines.append(f"- {q_label} → **{p}**")
        lines.append("")
        lines.append("| ID | Название | Impact (Low/Medium/High) | Effort (Low/Medium/High) |")
        lines.append("|-----|----------|--------------------------|--------------------------|")
        for n in nodes:
            lines.append(f"| {n['id']} | {n.get('title','—')} | ? | ? |")

    if stability_critical:
        lines += [
            "",
            "---",
            "",
            "## ⚠️ Предупреждения о стабильности",
            "",
            "### 🔴 Критически нестабильные (версия 1.4+)",
            "Присвоение Must создаёт высокий риск переделок.",
            "",
        ]
        for rid in stability_critical:
            lines.append(f"- `{rid}`")

    if stability_warnings:
        lines += [
            "",
            "### 🟡 Нестабильные (версия 1.3+) или с неизвестной стабильностью",
            "",
        ]
        for rid in stability_warnings:
            lines.append(f"- `{rid}`")

    lines += [
        "",
        "---",
        "",
        "## Следующие шаги",
        "",
        "1. Вызвать `add_stakeholder_scores` для каждого стейкхолдера",
        "2. После сбора всех оценок — вызвать `run_aggregation`",
        "3. Разрешить конфликты (`resolve_conflict`) если они есть",
        "4. Финализировать: `save_prioritization_result`",
    ]

    return "\n".join(lines)


@mcp.tool()
def add_stakeholder_scores(
    project_name: str,
    session_label: str,
    stakeholder_id: str,
    stakeholder_influence: Literal["High", "Medium", "Low"],
    scores_json: str,
) -> str:
    """
    Добавить оценки одного стейкхолдера для текущей сессии.

    Вызывается по одному разу на стейкхолдера.
    Повторный вызов для того же стейкхолдера заменяет предыдущие оценки.

    Параметры:
    - stakeholder_id: ID из реестра стейкхолдеров (4.2), например "SH-001"
    - stakeholder_influence: уровень влияния стейкхолдера
    - scores_json: оценки в зависимости от метода:

      MoSCoW:
        [{"req_id": "FR-001", "score": "Must"}, ...]

      WSJF:
        [{"req_id": "FR-001", "bv": 5, "tc": 3, "rr": 2, "js": 3}, ...]
        (js — Job Size, оценка усилий от команды разработки)

      ImpactEffort:
        [{"req_id": "FR-001", "impact": "High", "effort": "Low"}, ...]
    """
    logger.info(f"5.3 add_stakeholder_scores: {project_name}/{session_label} ← {stakeholder_id}")

    prio_data = _load_prio(project_name)
    session = _find_session(prio_data["sessions"], session_label)
    if not session:
        return f"❌ Сессия '{session_label}' не найдена. Сначала вызовите start_prioritization_session."

    if session["status"] == "closed":
        return f"❌ Сессия '{session_label}' уже закрыта."

    try:
        raw_scores = json.loads(scores_json)
    except json.JSONDecodeError as e:
        return f"❌ Ошибка парсинга scores_json: {e}"

    # Валидация и нормализация оценок по методу
    method = session["method"]
    normalized = {}

    if method == "MoSCoW":
        valid_vals = set(MOSCOW_WEIGHTS.keys())
        for item in raw_scores:
            rid = item.get("req_id")
            score = item.get("score")
            if not rid:
                return f"❌ Отсутствует req_id в: {item}"
            if score not in valid_vals:
                return (f"❌ Недопустимое значение '{score}' для {rid}. "
                        f"Допустимо: Must / Should / Could / Won't")
            normalized[rid] = score

    elif method == "WSJF":
        for item in raw_scores:
            rid = item.get("req_id")
            if not rid:
                return f"❌ Отсутствует req_id в: {item}"
            normalized[rid] = {
                "bv": float(item.get("bv", 0)),
                "tc": float(item.get("tc", 0)),
                "rr": float(item.get("rr", 0)),
                "js": float(item.get("js", 1)),
            }

    elif method == "ImpactEffort":
        valid_ie = {"Low", "Medium", "High"}
        for item in raw_scores:
            rid = item.get("req_id")
            impact = item.get("impact", "Medium")
            effort = item.get("effort", "Medium")
            if not rid:
                return f"❌ Отсутствует req_id в: {item}"
            if impact not in valid_ie or effort not in valid_ie:
                return (f"❌ Недопустимое значение impact/effort для {rid}. "
                        f"Допустимо: Low / Medium / High")
            normalized[rid] = {"impact": impact, "effort": effort}

    # Сохраняем оценки и influence
    session["stakeholder_scores"][stakeholder_id] = normalized
    if "stakeholder_influence" not in session:
        session["stakeholder_influence"] = {}
    session["stakeholder_influence"][stakeholder_id] = stakeholder_influence

    _save_prio(project_name, prio_data)

    is_update = "(обновлено)" if stakeholder_id in session.get("stakeholder_influence", {}) else ""
    lines = [
        f"✅ Оценки стейкхолдера **{stakeholder_id}** ({stakeholder_influence} influence) "
        f"сохранены {is_update}",
        "",
        f"**Проект:** {project_name}  ",
        f"**Сессия:** {session_label}  ",
        f"**Метод:** {method}  ",
        f"**Требований оценено:** {len(normalized)}",
        "",
        f"**Стейкхолдеров с оценками:** {len(session['stakeholder_scores'])}",
        "",
        "Когда все стейкхолдеры оценили требования — вызовите `run_aggregation`.",
    ]
    return "\n".join(lines)


@mcp.tool()
def run_aggregation(
    project_name: str,
    session_label: str,
    conflict_threshold: Literal["Strict", "Normal", "Loose"] = "Normal",
) -> str:
    """
    Агрегировать оценки стейкхолдеров, рассчитать приоритеты, выявить конфликты.

    - Strict: конфликт при расхождении ≥ 1 категории
    - Normal: конфликт при расхождении ≥ 2 категории (рекомендуется)
    - Loose: конфликт только Must vs Won't

    Детектирует:
    - 🔴 Межстейкхолдерские конфликты
    - ⚠️ Dependency violations (Must/Should зависит от ниже-приоритетного)
    - 🟡 Must Inflation (>60% требований в Must)
    - 🟡 Нестабильные требования в высоком приоритете
    """
    logger.info(f"5.3 run_aggregation: {project_name}/{session_label}")

    prio_data = _load_prio(project_name)
    session = _find_session(prio_data["sessions"], session_label)
    if not session:
        return f"❌ Сессия '{session_label}' не найдена."

    if not session["stakeholder_scores"]:
        return "⚠️ Нет оценок стейкхолдеров. Сначала вызовите add_stakeholder_scores."

    repo = _load_repo(project_name)
    method = session["method"]
    scores_by_sh = session["stakeholder_scores"]
    influence_by_sh = session.get("stakeholder_influence", {})

    # Агрегация по методу
    if method == "MoSCoW":
        aggregated = _aggregate_moscow(scores_by_sh, influence_by_sh)
    elif method == "WSJF":
        aggregated = _aggregate_wsjf(scores_by_sh, influence_by_sh)
    else:
        qmap = session.get("quadrant_mapping") or {
            "QuickWins": "Must", "BigBets": "Should",
            "FillIns": "Could", "ThanklessTasks": "Won't"
        }
        aggregated = _aggregate_impact_effort(scores_by_sh, influence_by_sh, qmap)

    session["aggregated"] = aggregated

    # Конфликты стейкхолдеров (для MoSCoW)
    threshold_spread = {"Strict": 1, "Normal": 2, "Loose": 3}[conflict_threshold]
    conflicts = _detect_stakeholder_conflicts(scores_by_sh, method)
    conflicts = [c for c in conflicts if c["spread"] >= threshold_spread]
    session["conflicts"] = conflicts

    # Dependency violations
    violations = _find_dependency_violations(repo, aggregated)
    session["dependency_violations"] = violations

    # Must Inflation
    inflation = _check_must_inflation(aggregated)

    # Нестабильные в Must
    volatile_must = []
    nodes_by_id = {n["id"]: n for n in repo.get("requirements", [])}
    for req_id, agg in aggregated.items():
        prio = agg.get("priority") if isinstance(agg, dict) else agg
        if prio == "Must":
            node = nodes_by_id.get(req_id, {})
            flag = _stability_flag(node)
            if flag in ("critical", "warning"):
                volatile_must.append({"req_id": req_id, "flag": flag,
                                      "version": node.get("version", "?")})

    _save_prio(project_name, prio_data)

    # Отчёт
    lines = [
        f"<!-- BABOK 5.3 — Агрегация, {project_name}/{session_label}, {date.today()} -->",
        "",
        f"# Результаты агрегации: {session_label}",
        f"**Проект:** {project_name}  ",
        f"**Метод:** {method}  ",
        f"**Стейкхолдеров:** {len(scores_by_sh)}  ",
        f"**Порог конфликта:** {conflict_threshold}",
        "",
        "---",
        "",
        "## Итоговые приоритеты",
        "",
    ]

    if method == "MoSCoW":
        lines.append("| ID | Приоритет | Взвешенный балл |")
        lines.append("|-----|-----------|-----------------|")
        for req_id, data in sorted(aggregated.items(),
                                   key=lambda x: x[1].get("weighted_score", 0) if isinstance(x[1], dict) else 0,
                                   reverse=True):
            prio = data.get("priority", "—") if isinstance(data, dict) else data
            ws = data.get("weighted_score", "—") if isinstance(data, dict) else "—"
            icon = {"Must": "🔴", "Should": "🟠", "Could": "🟡", "Won't": "🟢"}.get(prio, "")
            lines.append(f"| {req_id} | {icon} {prio} | {ws} |")

    elif method == "WSJF":
        lines.append("| ID | Приоритет | WSJF | CoD | JS |")
        lines.append("|-----|-----------|------|-----|----|")
        for req_id, data in sorted(aggregated.items(),
                                   key=lambda x: x[1].get("wsjf", 0) if isinstance(x[1], dict) else 0,
                                   reverse=True):
            prio = data.get("priority", "—") if isinstance(data, dict) else data
            icon = {"Must": "🔴", "Should": "🟠", "Could": "🟡", "Won't": "🟢"}.get(prio, "")
            lines.append(f"| {req_id} | {icon} {prio} | {data.get('wsjf','—')} "
                         f"| {data.get('cod','—')} | {data.get('js','—')} |")

    else:
        lines.append("| ID | Приоритет | Квадрант | Avg Impact | Avg Effort |")
        lines.append("|-----|-----------|----------|------------|------------|")
        for req_id, data in aggregated.items():
            prio = data.get("priority", "—") if isinstance(data, dict) else data
            icon = {"Must": "🔴", "Should": "🟠", "Could": "🟡", "Won't": "🟢"}.get(prio, "")
            lines.append(f"| {req_id} | {icon} {prio} | {data.get('quadrant','—')} "
                         f"| {data.get('avg_impact','—')} | {data.get('avg_effort','—')} |")

    # Must Inflation
    if inflation["inflated"]:
        lines += [
            "",
            "---",
            "",
            f"## 🟠 Must Inflation — {int(inflation['must_ratio']*100)}% требований в Must",
            "",
            "Рекомендация: провести повторную сессию с техникой «фиксированного бюджета».",
            "Спросите стейкхолдеров: «Если бы мы могли реализовать только 40% — что выбрать?»",
        ]

    # Конфликты
    if conflicts:
        lines += [
            "",
            "---",
            "",
            f"## 🔴 Конфликты стейкхолдеров ({len(conflicts)} шт.)",
            "",
            "Требуют разрешения перед финализацией.",
            "",
        ]
        for c in conflicts:
            lines.append(f"### Требование `{c['req_id']}` — {c['severity']}")
            lines.append("")
            for sh_id, score in c["scores"].items():
                infl = influence_by_sh.get(sh_id, "Medium")
                lines.append(f"- **{sh_id}** ({infl}): **{score}**")
            lines.append("")
            lines.append("Вызовите `resolve_conflict` для фиксации решения.")
            lines.append("")
    else:
        lines += ["", "---", "", "## ✅ Конфликты стейкхолдеров", "", "Конфликтов не обнаружено.", ""]

    # Dependency violations
    if violations:
        lines += [
            "---",
            "",
            f"## ⚠️ Dependency Violations ({len(violations)} шт.)",
            "",
            "Логические противоречия: требование с высоким приоритетом зависит от низкоприоритетного.",
            "",
        ]
        for v in violations:
            lines.append(f"- `{v['req_id']}` (**{v['req_priority']}**) зависит от "
                         f"`{v['depends_on']}` (**{v['dep_priority']}**)")
        lines += [
            "",
            "Варианты: поднять зависимость / понизить требование / декомпозировать.",
            "Зафиксируйте решение через `resolve_conflict`.",
            "",
        ]

    # Нестабильные в Must
    if volatile_must:
        lines += [
            "---",
            "",
            "## 🟡 Нестабильные требования в Must",
            "",
        ]
        for item in volatile_must:
            icon = "🔴" if item["flag"] == "critical" else "🟡"
            lines.append(f"- {icon} `{item['req_id']}` (версия {item['version']}) — риск переделок")
        lines.append("")

    lines += [
        "---",
        "",
        "## Следующие шаги",
        "",
    ]
    has_open = conflicts or violations
    if has_open:
        lines.append("1. Разрешить конфликты → `resolve_conflict`")
        lines.append("2. После разрешения всех конфликтов → `save_prioritization_result`")
    else:
        lines.append("1. Все конфликты отсутствуют → можно вызывать `save_prioritization_result`")

    return "\n".join(lines)


@mcp.tool()
def resolve_conflict(
    project_name: str,
    session_label: str,
    req_id: str,
    conflict_type: Literal["stakeholder_conflict", "dependency_violation", "inflation"],
    final_priority: Literal["Must", "Should", "Could", "Won't"],
    rationale: str,
    decided_by: str,
) -> str:
    """
    Зафиксировать решение по конфликту приоритизации.

    Параметры:
    - req_id: ID требования с конфликтом
    - conflict_type: тип конфликта
    - final_priority: итоговый приоритет после разрешения
    - rationale: обоснование решения
    - decided_by: кто принял решение (stakeholder_id или роль, например "Sponsor")
    """
    logger.info(f"5.3 resolve_conflict: {project_name}/{session_label} req={req_id}")

    prio_data = _load_prio(project_name)
    session = _find_session(prio_data["sessions"], session_label)
    if not session:
        return f"❌ Сессия '{session_label}' не найдена."

    # Обновляем агрегированное значение
    if req_id in session["aggregated"]:
        if isinstance(session["aggregated"][req_id], dict):
            session["aggregated"][req_id]["priority"] = final_priority
            session["aggregated"][req_id]["resolved"] = True
        else:
            session["aggregated"][req_id] = {
                "priority": final_priority, "resolved": True
            }
    else:
        session["aggregated"][req_id] = {"priority": final_priority, "resolved": True}

    # Помечаем конфликт как разрешённый
    resolution = {
        "req_id": req_id,
        "conflict_type": conflict_type,
        "final_priority": final_priority,
        "rationale": rationale,
        "decided_by": decided_by,
        "resolved_at": str(date.today()),
        "resolved": True,
    }

    found = False
    for c in session["conflicts"]:
        if c["req_id"] == req_id and c["conflict_type"] == conflict_type:
            c["resolved"] = True
            c["resolution"] = resolution
            found = True
            break
    for v in session["dependency_violations"]:
        if v["req_id"] == req_id:
            v["resolved"] = True
            v["resolution"] = resolution
            found = True
            break

    if not found:
        # Добавляем как отдельную запись (ручное разрешение)
        session["conflicts"].append({
            "req_id": req_id,
            "conflict_type": conflict_type,
            "resolved": True,
            "resolution": resolution,
        })

    _save_prio(project_name, prio_data)

    # Проверяем остались ли нерешённые конфликты
    open_conflicts = [c for c in session["conflicts"] if not c.get("resolved")]
    open_violations = [v for v in session["dependency_violations"] if not v.get("resolved")]

    lines = [
        f"✅ Конфликт по `{req_id}` разрешён",
        "",
        f"**Итоговый приоритет:** {final_priority}  ",
        f"**Принял решение:** {decided_by}  ",
        f"**Обоснование:** {rationale}",
        "",
    ]

    if open_conflicts or open_violations:
        total_open = len(open_conflicts) + len(open_violations)
        lines.append(f"⚠️ Остаётся **{total_open}** нерешённых конфликтов/violations.")
        lines.append("Продолжайте вызывать `resolve_conflict` для каждого.")
    else:
        lines.append("✅ Все конфликты разрешены. Можно вызывать `save_prioritization_result`.")

    return "\n".join(lines)


@mcp.tool()
def save_prioritization_result(
    project_name: str,
    session_label: str,
) -> str:
    """
    Финализировать сессию приоритизации.

    Действия:
    1. Проверяет что все конфликты разрешены
    2. Обновляет поле priority в репозитории 5.1
    3. Закрывает сессию в {project}_prioritization.json
    4. Сохраняет Markdown-отчёт

    Предупреждает если остались нерешённые конфликты (но позволяет сохранить).
    """
    logger.info(f"5.3 save_prioritization_result: {project_name}/{session_label}")

    prio_data = _load_prio(project_name)
    session = _find_session(prio_data["sessions"], session_label)
    if not session:
        return f"❌ Сессия '{session_label}' не найдена."

    open_conflicts = [c for c in session["conflicts"] if not c.get("resolved")]
    open_violations = [v for v in session["dependency_violations"] if not v.get("resolved")]

    # Обновляем репозиторий 5.1
    repo = _load_repo(project_name)
    updated_count = 0
    priority_summary = {}

    for req_id, agg_data in session["aggregated"].items():
        priority = agg_data.get("priority") if isinstance(agg_data, dict) else agg_data
        if not priority:
            continue
        for node in repo.get("requirements", []):
            if node["id"] == req_id:
                old_priority = node.get("priority", "—")
                node["priority"] = priority
                updated_count += 1
                priority_summary.setdefault(priority, []).append(req_id)

                # История изменений
                if "history" not in repo:
                    repo["history"] = []
                repo["history"].append({
                    "date": str(date.today()),
                    "action": "priority_updated",
                    "req_id": req_id,
                    "old_priority": old_priority,
                    "new_priority": priority,
                    "session": session_label,
                    "method": session["method"],
                })
                break

    _save_repo(project_name, repo)

    # Закрываем сессию
    session["status"] = "closed"
    session["closed_at"] = str(date.today())
    _save_prio(project_name, prio_data)

    # Markdown отчёт
    lines = [
        f"<!-- BABOK 5.3 — Prioritize Requirements (результат), "
        f"Проект: {project_name}, Сессия: {session_label}, Дата: {date.today()} -->",
        "",
        f"# Результаты приоритизации: {session_label}",
        f"**Проект:** {project_name}  ",
        f"**Метод:** {session['method']}  ",
        f"**Дата:** {date.today()}  ",
        f"**Обновлено требований:** {updated_count}",
        "",
        "---",
        "",
        "## Итоговые приоритеты",
        "",
    ]

    for prio_label in ["Must", "Should", "Could", "Won't"]:
        reqs = priority_summary.get(prio_label, [])
        icon = {"Must": "🔴", "Should": "🟠", "Could": "🟡", "Won't": "🟢"}[prio_label]
        lines.append(f"### {icon} {prio_label} ({len(reqs)} шт.)")
        if reqs:
            for rid in reqs:
                lines.append(f"- `{rid}`")
        else:
            lines.append("*(нет требований)*")
        lines.append("")

    # Метаданные сессии
    total_conflicts = len(session["conflicts"])
    resolved_conflicts = sum(1 for c in session["conflicts"] if c.get("resolved"))
    total_violations = len(session["dependency_violations"])
    resolved_violations = sum(1 for v in session["dependency_violations"] if v.get("resolved"))

    lines += [
        "---",
        "",
        "## Статистика сессии",
        "",
        f"- Стейкхолдеров: {len(session['stakeholder_scores'])}",
        f"- Конфликтов: {total_conflicts} (разрешено: {resolved_conflicts})",
        f"- Dependency violations: {total_violations} (разрешено: {resolved_violations})",
        "",
    ]

    if open_conflicts or open_violations:
        lines += [
            "---",
            "",
            "## ⚠️ Нерешённые конфликты",
            "",
            f"Осталось нерешённых: {len(open_conflicts)} конфликтов, {len(open_violations)} violations.",
            "Результат сохранён, но рекомендуется зафиксировать решения через `resolve_conflict`.",
            "",
        ]

    lines += [
        "---",
        "",
        "## Следующие шаги",
        "",
        "- Приоритеты записаны в репозиторий 5.1",
        "- Результаты доступны для 6.3 (Оценка рисков)",
        "- При изменении контекста — провести новую сессию приоритизации",
    ]

    content = "\n".join(lines)
    saved = save_artifact(content, prefix=f"5_3_prioritization_{project_name.lower().replace(' ', '_')}")
    return content + saved


if __name__ == "__main__":
    mcp.run()
