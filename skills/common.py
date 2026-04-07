# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
import os
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


class Stakeholder(BaseModel):
    """Модель стейкхолдера для матрицы вовлечения."""
    name: str = Field(..., description="Имя или роль стейкхолдера")
    influence: str = Field(..., pattern="^(Low|Medium|High)$", description="Уровень влияния")
    interest: str = Field(..., pattern="^(Low|Medium|High)$", description="Уровень интереса")
    attitude: Optional[str] = Field("Neutral", description="Отношение к проекту: Neutral / Champion / Blocker")


def save_artifact(content: str, prefix: str) -> str:
    """Сохраняет Markdown-артефакт в reports/ и возвращает путь."""
    _ensure_dirs()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.md"
    filepath = os.path.join(REPORTS_DIR, filename)

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
