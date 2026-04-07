#!/usr/bin/env python3
"""
AInalyst — переключатель фаз BABOK.

Использование:
    python phase.py              # показать текущую фазу и список всех фаз
    python phase.py planning     # переключиться на фазу планирования (Гл. 3)
    python phase.py elicitation  # Гл. 4 — выявление требований
    python phase.py lifecycle    # Гл. 5 — управление жизненным циклом
    python phase.py analysis     # Гл. 6 — анализ стратегии
    python phase.py design       # Гл. 7 — определение и проектирование требований
    python phase.py full         # все серверы (режим без ограничений)

После переключения — перезапустить Claude Code: /restart
"""

import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Корень проекта — для абсолютных путей в .mcp.json (ADR-REVIEW-п10)
# ---------------------------------------------------------------------------

# Абсолютный путь к корню проекта (там где лежит этот файл).
# Используется при генерации .mcp.json чтобы Claude Code находил серверы
# независимо от рабочей директории при запуске.
PROJECT_ROOT = Path(__file__).resolve().parent


def _server(script: str) -> dict:
    """Возвращает конфигурацию MCP-сервера с абсолютным путём к скрипту."""
    return {"command": "python", "args": [str(PROJECT_ROOT / script)]}


# ---------------------------------------------------------------------------
# Конфигурация фаз
# ---------------------------------------------------------------------------

# Базовый сервер (Гл. 3 — планирование) присутствует во ВСЕХ фазах.
# Он лёгкий (5 tools) и нужен всегда: project_id, stakeholder registry и т.д.
BASE_SERVER = {
    "babok-ch3": _server("skills/planning_mcp.py"),
    # Confluence присутствует во всех фазах — сервер маленький (3 инструмента),
    # стартует без .env (ошибка возникает только при вызове инструмента).
    "babok-confluence": _server("skills/integrations/confluence_mcp.py"),
}

PHASES = {
    "planning": {
        "label": "Глава 3 — Планирование бизнес-анализа",
        "hint": "Новый проект, выбор подхода, карта стейкхолдеров, план BA",
        "tokens_saved": "~33 000",
        "servers": {
            **BASE_SERVER,
        }
    },

    "elicitation": {
        "label": "Глава 4 — Выявление и сотрудничество",
        "hint": "Интервью, воркшопы, анкеты, протоколы встреч",
        "tokens_saved": "~27 000",
        "servers": {
            **BASE_SERVER,
            "babok-ch4-41": _server("skills/elicitation_mcp.py"),
            "babok-ch4-42": _server("skills/elicitation_conduct_mcp.py"),
            "babok-ch4-43": _server("skills/elicitation_confirm_mcp.py"),
            "babok-ch4-44": _server("skills/elicitation_communicate_mcp.py"),
            "babok-ch4-45": _server("skills/elicitation_collaborate_mcp.py"),
        }
    },

    "lifecycle": {
        "label": "Глава 5 — Управление жизненным циклом требований",
        "hint": "Трассировка, приоритизация, CR, утверждение, поддержка",
        "tokens_saved": "~27 000",
        "servers": {
            **BASE_SERVER,
            "babok-ch5-51": _server("skills/requirements_traceability_mcp.py"),
            "babok-ch5-52": _server("skills/requirements_maintain_mcp.py"),
            "babok-ch5-53": _server("skills/requirements_prioritize_mcp.py"),
            "babok-ch5-54": _server("skills/requirements_assess_changes_mcp.py"),
            "babok-ch5-55": _server("skills/requirements_approve_mcp.py"),
        }
    },

    "analysis": {
        "label": "Глава 6 — Анализ стратегии",
        "hint": "Анализ текущего состояния (as-is), будущее состояние (to-be), GAP, оценка рисков, стратегия изменения",
        "tokens_saved": "~28 000",
        "servers": {
            **BASE_SERVER,
            "babok-ch6-61": _server("skills/current_state_mcp.py"),
            "babok-ch6-62": _server("skills/future_state_mcp.py"),
            "babok-ch6-63": _server("skills/risk_assessment_mcp.py"),
            "babok-ch6-64": _server("skills/change_strategy_mcp.py"),
        }
    },

    "design": {
        "label": "Глава 7 — Определение и проектирование требований",
        "hint": "Спецификация, верификация, валидация, архитектура, дизайн, оценка ценности",
        "tokens_saved": "~18 000",
        "servers": {
            **BASE_SERVER,
            "babok-ch7-71": _server("skills/requirements_spec_mcp.py"),
            "babok-ch7-72": _server("skills/requirements_verify_mcp.py"),
            "babok-ch7-73": _server("skills/requirements_validate_mcp.py"),
            "babok-ch7-74": _server("skills/requirements_architecture_mcp.py"),
            "babok-ch7-75": _server("skills/design_options_mcp.py"),
            "babok-ch7-76": _server("skills/value_recommend_mcp.py"),
        }
    },

    "full": {
        "label": "Все главы (полный режим)",
        "hint": "Все 18 серверов. Используй только если нужны инструменты из разных глав одновременно",
        "tokens_saved": "0",
        "servers": {
            **BASE_SERVER,
            "babok-ch4-41": _server("skills/elicitation_mcp.py"),
            "babok-ch4-42": _server("skills/elicitation_conduct_mcp.py"),
            "babok-ch4-43": _server("skills/elicitation_confirm_mcp.py"),
            "babok-ch4-44": _server("skills/elicitation_communicate_mcp.py"),
            "babok-ch4-45": _server("skills/elicitation_collaborate_mcp.py"),
            "babok-ch5-51": _server("skills/requirements_traceability_mcp.py"),
            "babok-ch5-52": _server("skills/requirements_maintain_mcp.py"),
            "babok-ch5-53": _server("skills/requirements_prioritize_mcp.py"),
            "babok-ch5-54": _server("skills/requirements_assess_changes_mcp.py"),
            "babok-ch5-55": _server("skills/requirements_approve_mcp.py"),
            "babok-ch6-61": _server("skills/current_state_mcp.py"),
            "babok-ch6-62": _server("skills/future_state_mcp.py"),
            "babok-ch6-63": _server("skills/risk_assessment_mcp.py"),
            "babok-ch6-64": _server("skills/change_strategy_mcp.py"),
            "babok-ch7-71": _server("skills/requirements_spec_mcp.py"),
            "babok-ch7-72": _server("skills/requirements_verify_mcp.py"),
            "babok-ch7-73": _server("skills/requirements_validate_mcp.py"),
            "babok-ch7-74": _server("skills/requirements_architecture_mcp.py"),
            "babok-ch7-75": _server("skills/design_options_mcp.py"),
            "babok-ch7-76": _server("skills/value_recommend_mcp.py"),
        }
    },
}

# ---------------------------------------------------------------------------
# Файлы
# ---------------------------------------------------------------------------

MCP_FILE = Path(".mcp.json")
STATE_FILE = Path(".ainalyst_phase")  # запоминаем текущую фазу


def read_current_phase() -> str | None:
    if STATE_FILE.exists():
        return STATE_FILE.read_text().strip()
    return None


def write_phase(phase: str):
    config = {"mcpServers": PHASES[phase]["servers"]}
    MCP_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False))
    STATE_FILE.write_text(phase)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "cyan": "\033[36m",
    "gray": "\033[90m",
    "red": "\033[31m",
}


def c(color: str, text: str) -> str:
    return f"{COLORS[color]}{text}{COLORS['reset']}"


def _confluence_env_set() -> bool:
    """Проверяет что заданы минимально необходимые переменные для Confluence."""
    return bool(os.environ.get("CONFLUENCE_URL") and os.environ.get("CONFLUENCE_API_TOKEN"))


def show_status():
    current = read_current_phase()
    print()
    print(c("bold", "AInalyst — переключатель фаз BABOK"))
    print(c("gray", "─" * 55))

    if current:
        phase_info = PHASES[current]
        print(f"  Текущая фаза: {c('green', current)} — {phase_info['label']}")
        server_count = len(phase_info["servers"])
        print(f"  Активных серверов: {c('cyan', str(server_count))} из {len(PHASES['full']['servers'])}")
    else:
        print(f"  Текущая фаза: {c('yellow', 'не задана')} (используется .mcp.json как есть)")

    print()
    print(c("bold", "Доступные фазы:"))
    print()

    for key, info in PHASES.items():
        marker = c("green", "▶ ") if key == current else "  "
        saved = info["tokens_saved"]
        servers = len(info["servers"])
        saved_str = f"экономия ~{saved} токенов" if saved != "0" else "все серверы"
        print(f"{marker}{c('cyan', key):<22} {info['label']}")
        print(f"   {c('gray', info['hint'])}")
        print(f"   {c('gray', f'{servers} серверов · {saved_str}')}")
        print()

    confluence_available = _confluence_env_set()
    confluence_status = c("green", "настроен") if confluence_available else c("yellow", "не настроен — заполните .env")
    print(c("gray", "─" * 55))
    print(f"  Confluence: {confluence_status}")
    print()
    print(c("gray", "─" * 55))
    print(f"  Использование: {c('bold', 'python phase.py <фаза>')}")
    print(f"  После переключения: {c('yellow', '/restart')} в Claude Code")
    print()


def switch_phase(phase: str):
    if phase not in PHASES:
        print(c("red", f"Ошибка: фаза '{phase}' не существует."))
        print(f"Доступные: {', '.join(PHASES.keys())}")
        sys.exit(1)

    old_phase = read_current_phase()
    write_phase(phase)

    info = PHASES[phase]
    server_count = len(info["servers"])
    full_count = len(PHASES["full"]["servers"])

    print()
    print(c("green", "✓") + f" Фаза переключена: {c('bold', phase)}")
    print(f"  {info['label']}")
    print(f"  {c('gray', info['hint'])}")
    print()
    print(f"  Активных серверов: {c('cyan', str(server_count))} из {full_count}")

    if info["tokens_saved"] != "0":
        print(f"  Экономия контекста: ~{c('green', info['tokens_saved'])} токенов")

    if old_phase and old_phase != phase:
        print(f"  {c('gray', f'Было: {old_phase}')}")

    print()
    print(c("yellow", "  → Перезапусти Claude Code: /restart"))
    print()


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) == 1:
        show_status()
    elif len(sys.argv) == 2:
        switch_phase(sys.argv[1])
    else:
        print(c("red", "Использование: python phase.py [фаза]"))
        sys.exit(1)


if __name__ == "__main__":
    main()
