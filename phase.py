#!/usr/bin/env python3
"""
AInalyst — BABOK phase switcher.

Usage:
    python phase.py              # show the current phase and the list of all phases
    python phase.py planning     # switch to the planning phase (Ch. 3)
    python phase.py elicitation  # Ch. 4 — requirements elicitation
    python phase.py lifecycle    # Ch. 5 — requirements lifecycle management
    python phase.py analysis     # Ch. 6 — strategy analysis
    python phase.py design       # Ch. 7 — requirements analysis and design
    python phase.py full         # all servers (unrestricted mode)

After switching — restart Claude Code: /restart
"""

import json
import os
import sys
from pathlib import Path

# Make non-ASCII output (box glyphs, arrows) safe on Windows consoles (cp1251/cp866)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Project root — for absolute paths in .mcp.json (ADR-REVIEW item 10)
# ---------------------------------------------------------------------------

# Absolute path to the project root (where this file lives).
# Used when generating .mcp.json so Claude Code can find the servers
# regardless of the working directory at startup.
PROJECT_ROOT = Path(__file__).resolve().parent


def _server(script: str) -> dict:
    """Returns the MCP server configuration with an absolute path to the script."""
    # Script mode puts the SCRIPT's directory (skills/) on sys.path — not the
    # project root — so without PYTHONPATH every `from skills.common import ...`
    # dies with ModuleNotFoundError: No module named 'skills', on any machine.
    return {
        "command": "python",
        "args": [str(PROJECT_ROOT / script)],
        "env": {"PYTHONPATH": str(PROJECT_ROOT)},
    }


# ---------------------------------------------------------------------------
# Phase configuration
# ---------------------------------------------------------------------------

# The base server (Ch. 3 — planning) is present in ALL phases.
# It's lightweight (5 tools) and always needed: project_id, stakeholder registry, etc.
BASE_SERVER = {
    "babok-ch3": _server("skills/planning_mcp.py"),
    # Confluence is present in all phases — the server is small (4 tools),
    # it starts without .env (the error only occurs when a tool is called).
    "babok-confluence": _server("skills/integrations/confluence_mcp.py"),
}

PHASES = {
    "planning": {
        "label": "Chapter 3 — Business Analysis Planning",
        "hint": "New project, approach selection, stakeholder map, BA plan",
        "tokens_saved": "33,000",
        "servers": {
            **BASE_SERVER,
        }
    },

    "elicitation": {
        "label": "Chapter 4 — Elicitation and Collaboration",
        "hint": "Interviews, workshops, surveys, meeting minutes",
        "tokens_saved": "27,000",
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
        "label": "Chapter 5 — Requirements Lifecycle Management",
        "hint": "Traceability, prioritization, CRs, approval, maintenance",
        "tokens_saved": "27,000",
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
        "label": "Chapter 6 — Strategy Analysis",
        "hint": "Current state analysis (as-is), future state (to-be), gap analysis, risk assessment, change strategy",
        "tokens_saved": "28,000",
        "servers": {
            **BASE_SERVER,
            "babok-ch6-61": _server("skills/current_state_mcp.py"),
            "babok-ch6-62": _server("skills/future_state_mcp.py"),
            "babok-ch6-63": _server("skills/risk_assessment_mcp.py"),
            "babok-ch6-64": _server("skills/change_strategy_mcp.py"),
        }
    },

    "design": {
        "label": "Chapter 7 — Requirements Analysis and Design",
        "hint": "Specification, verification, validation, architecture, design, value assessment",
        "tokens_saved": "18,000",
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
        "label": "All chapters (full mode)",
        "hint": "All 18 servers. Use only when you need tools from different chapters at the same time",
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
# Files
# ---------------------------------------------------------------------------

MCP_FILE = Path(".mcp.json")
STATE_FILE = Path(".ainalyst_phase")  # remembers the current phase


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
    """Checks whether the minimum required Confluence environment variables are set."""
    return bool(os.environ.get("CONFLUENCE_URL") and os.environ.get("CONFLUENCE_API_TOKEN"))


def show_status():
    current = read_current_phase()
    print()
    print(c("bold", "AInalyst — BABOK phase switcher"))
    print(c("gray", "─" * 55))

    if current:
        phase_info = PHASES[current]
        print(f"  Current phase: {c('green', current)} — {phase_info['label']}")
        server_count = len(phase_info["servers"])
        print(f"  Active servers: {c('cyan', str(server_count))} of {len(PHASES['full']['servers'])}")
    else:
        print(f"  Current phase: {c('yellow', 'not set')} (using .mcp.json as is)")

    print()
    print(c("bold", "Available phases:"))
    print()

    for key, info in PHASES.items():
        marker = c("green", "▶ ") if key == current else "  "
        saved = info["tokens_saved"]
        servers = len(info["servers"])
        saved_str = f"saves ~{saved} tokens" if saved != "0" else "all servers"
        print(f"{marker}{c('cyan', key):<22} {info['label']}")
        print(f"   {c('gray', info['hint'])}")
        print(f"   {c('gray', f'{servers} servers · {saved_str}')}")
        print()

    confluence_available = _confluence_env_set()
    confluence_status = c("green", "configured") if confluence_available else c("yellow", "not configured — fill in .env")
    print(c("gray", "─" * 55))
    print(f"  Confluence: {confluence_status}")
    print()
    print(c("gray", "─" * 55))
    print(f"  Usage: {c('bold', 'python phase.py <phase>')}")
    print(f"  After switching: {c('yellow', '/restart')} in Claude Code")
    print()


def switch_phase(phase: str):
    if phase not in PHASES:
        print(c("red", f"Error: phase '{phase}' does not exist."))
        print(f"Available: {', '.join(PHASES.keys())}")
        sys.exit(1)

    old_phase = read_current_phase()
    write_phase(phase)

    info = PHASES[phase]
    server_count = len(info["servers"])
    full_count = len(PHASES["full"]["servers"])

    print()
    print(c("green", "✓") + f" Phase switched: {c('bold', phase)}")
    print(f"  {info['label']}")
    print(f"  {c('gray', info['hint'])}")
    print()
    print(f"  Active servers: {c('cyan', str(server_count))} of {full_count}")

    if info["tokens_saved"] != "0":
        print(f"  Context savings: ~{c('green', info['tokens_saved'])} tokens")

    if old_phase and old_phase != phase:
        print(f"  {c('gray', f'Previous: {old_phase}')}")

    print()
    print(c("yellow", "  → Restart Claude Code: /restart"))
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) == 1:
        show_status()
    elif len(sys.argv) == 2:
        switch_phase(sys.argv[1])
    else:
        print(c("red", "Usage: python phase.py [phase]"))
        sys.exit(1)


if __name__ == "__main__":
    main()
