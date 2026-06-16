# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
import os
import re
import sys
import logging
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional

# Настройка логирования (stderr — не мешает протоколу JSON-RPC)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("BABOK_Toolkit")

BASE_DIR = "governance_plans"
DATA_DIR = os.path.join(BASE_DIR, "data")      # JSON: машиночитаемые файлы для MCP
REPORTS_DIR = os.path.join(BASE_DIR, "reports") # Markdown: документы для людей


def _ensure_dirs():
    """Создаёт все нужные папки если их нет."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Раскладка артефактов по подкаталогам проекта (issue #1)
# ---------------------------------------------------------------------------

_PID_DISALLOWED = re.compile(r"[^a-z0-9_-]+")


def normalize_project_id(project_id: str) -> str:
    """Безопасное имя проекта для использования как имя каталога.

    Защита от path traversal: убирает '/', '\\', '..', абсолютные пути;
    оставляет whitelist [a-z0-9_-]. Пустой результат → '_unknown'.
    """
    if not project_id:
        return "_unknown"
    s = str(project_id).strip().lower()
    s = s.replace("\\", "_").replace("/", "_").replace(" ", "_")
    s = _PID_DISALLOWED.sub("_", s)
    s = re.sub(r"_+", "_", s)
    s = s.strip("._-")
    return s or "_unknown"


def data_dir_for(project_id: str) -> str:
    """governance_plans/data/<safe_pid>/ — каталог json-артефактов проекта."""
    return os.path.join(DATA_DIR, normalize_project_id(project_id))


def report_dir_for(project_id: str) -> str:
    """governance_plans/reports/<safe_pid>/ — каталог markdown-отчётов проекта."""
    return os.path.join(REPORTS_DIR, normalize_project_id(project_id))


def _legacy_safe(project_id: str) -> str:
    """Домиграционная нормализация имени (issue #1) — ТОЛЬКО для поиска уже
    существующих legacy-файлов. До перехода на normalize_project_id имена строились
    как project_id.lower().replace(" ", "_"), что сохраняло точки и прочие символы.
    """
    return str(project_id).lower().replace(" ", "_")


def data_path(project_id: str, filename: str) -> str:
    """Единый резолвер пути json (и чтение, и запись).

    filename уже включает префикс {safe_pid}_ (issue #1, развилка 1). Возвращает
    первый существующий из кандидатов, иначе — каноническую вложенную раскладку:
      1) data/<norm>/<filename>          — каноническая вложенная;
      2) data/<filename>                 — каноническая плоская (legacy-раскладка);
      3..5) то же, но с ДОмиграционным именем (для project_id с символами вне
            [a-z0-9_-], например с точками — их старый _safe сохранял, а
            normalize_project_id переписывает).
    Каталог создаёт сторона записи: os.makedirs(os.path.dirname(path), ...).
    """
    norm = normalize_project_id(project_id)
    candidates = [
        os.path.join(DATA_DIR, norm, filename),
        os.path.join(DATA_DIR, filename),
    ]
    legacy = _legacy_safe(project_id)
    if legacy != norm and filename.startswith(norm + "_"):
        legacy_name = legacy + filename[len(norm):]
        candidates += [
            os.path.join(DATA_DIR, norm, legacy_name),
            os.path.join(DATA_DIR, legacy, legacy_name),
            os.path.join(DATA_DIR, legacy_name),
        ]
    for cand in candidates:
        if os.path.exists(cand):
            return cand
    return candidates[0]  # новый артефакт → каноническая вложенная раскладка


def specs_dir(project_id: str) -> str:
    """Каталог спеков 7.1: data/<project_id>/specs/ (issue #1).

    Fallback на legacy-раскладки (включая ДОмиграционные имена с точками и т.п.):
    плоский data/<safe>_specs/ и варианты со старой нормализацией.
    """
    norm = normalize_project_id(project_id)
    nested = os.path.join(DATA_DIR, norm, "specs")
    candidates = [nested, os.path.join(DATA_DIR, f"{norm}_specs")]
    legacy = _legacy_safe(project_id)
    if legacy != norm:
        candidates += [
            os.path.join(DATA_DIR, legacy, "specs"),
            os.path.join(DATA_DIR, f"{legacy}_specs"),
        ]
    for cand in candidates:
        if os.path.isdir(cand):
            return cand
    return nested


class Stakeholder(BaseModel):
    """Модель стейкхолдера для матрицы вовлечения."""
    name: str = Field(..., description="Имя или роль стейкхолдера")
    influence: str = Field(..., pattern="^(Low|Medium|High)$", description="Уровень влияния")
    interest: str = Field(..., pattern="^(Low|Medium|High)$", description="Уровень интереса")
    attitude: Optional[str] = Field("Neutral", description="Отношение к проекту: Neutral / Champion / Blocker")


def save_artifact(content: str, prefix: str, project_id: Optional[str] = None) -> str:
    """Сохраняет Markdown-артефакт в reports/ и возвращает путь.

    Если передан project_id — артефакт пишется в reports/<project_id>/ (issue #1).
    Без project_id сохраняется поведение по умолчанию (плоский reports/).
    """
    _ensure_dirs()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.md"
    if project_id:
        out_dir = report_dir_for(project_id)
        os.makedirs(out_dir, exist_ok=True)
    else:
        out_dir = REPORTS_DIR
    filepath = os.path.join(out_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"Артефакт сохранен: {filepath}")
    return f"\n\n✅ Артефакт сохранен: `{filepath}`"


# ---------------------------------------------------------------------------
# Shared matrices — используются в planning.py и planning_mcp.py
# Единственный источник истины (ADR-REVIEW-п5)
# ---------------------------------------------------------------------------

APPROACH_MATRIX: dict[tuple[str, str], tuple[str, list[str]]] = {
    ("Low",    "Low"):    ("Predictive (Waterfall)", ["Document Analysis", "Financial Analysis", "Business Rules Analysis"]),
    ("Low",    "Medium"): ("Predictive (Waterfall)", ["Document Analysis", "Interviews", "Prototyping"]),
    ("Low",    "High"):   ("Hybrid",                 ["Workshops", "Prototyping", "Risk Analysis"]),
    ("Medium", "Low"):    ("Hybrid",                 ["Workshops", "Prioritization", "Use Cases"]),
    ("Medium", "Medium"): ("Hybrid",                 ["Workshops", "User Stories", "Prioritization"]),
    ("Medium", "High"):   ("Adaptive (Agile)",        ["Backlog Management", "User Stories", "Retrospectives"]),
    ("High",   "Low"):    ("Adaptive (Agile)",        ["Backlog Management", "User Stories", "Kanban"]),
    ("High",   "Medium"): ("Adaptive (Agile)",        ["Backlog Management", "User Stories", "Retrospectives"]),
    ("High",   "High"):   ("Adaptive (Agile)",        ["Backlog Management", "Spike / PoC", "Retrospectives"]),
}

REGULATORY_OVERRIDE: dict[str, str] = {
    "Adaptive (Agile)": "Hybrid (Agile + compliance gates)",
    "Hybrid":           "Hybrid (с усиленным Governance)",
}

QUADRANT_STRATEGIES: dict[tuple[str, str], tuple[str, str, str]] = {
    ("High", "High"):     ("Key Players",     "Manage Closely — вовлекать в каждое решение",       "Еженедельно"),
    ("High", "Medium"):   ("Context Setters", "Keep Satisfied — информировать о ключевых вехах",   "При вехах"),
    ("High", "Low"):      ("Context Setters", "Keep Satisfied — информировать о ключевых вехах",   "При вехах"),
    ("Medium", "High"):   ("Subjects",        "Keep Informed — демонстрации, Sprint Review",        "Bi-weekly"),
    ("Low",  "High"):     ("Subjects",        "Keep Informed — демонстрации, Sprint Review",        "Bi-weekly"),
    ("Medium", "Medium"): ("Subjects",        "Keep Informed — регулярные обновления",              "Ежемесячно"),
    ("Medium", "Low"):    ("Crowd",           "Monitor — общая рассылка, низкий приоритет",         "Квартально"),
    ("Low",  "Medium"):   ("Crowd",           "Monitor — общая рассылка, низкий приоритет",         "Квартально"),
    ("Low",  "Low"):      ("Crowd",           "Monitor — общая рассылка, низкий приоритет",         "Квартально"),
}
