# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""Regression tests: phase.py must generate a LAUNCHABLE server config.

The generated .mcp.json runs `python <abs path to skills/xxx_mcp.py>`.
In script mode Python puts the SCRIPT's directory (skills/) on sys.path —
not the project root and not the cwd — so `from skills.common import ...`
inside every server died with `ModuleNotFoundError: No module named
'skills'` on any machine, regardless of where the client launched it.
The unit suite never saw it because conftest mocks the mcp package and
imports modules in-process, where the root IS on sys.path.

Fix under test: _server() ships env.PYTHONPATH = project root.
"""

import os
import subprocess
import sys

import phase


def test_server_config_carries_pythonpath():
    cfg = phase._server("skills/planning_mcp.py")
    assert cfg.get("env", {}).get("PYTHONPATH") == str(phase.PROJECT_ROOT)


def test_every_phase_server_carries_pythonpath():
    for phase_name, ph in phase.PHASES.items():
        for server_name, cfg in ph["servers"].items():
            assert cfg.get("env", {}).get("PYTHONPATH") == str(phase.PROJECT_ROOT), (
                f"{phase_name}/{server_name} is generated without PYTHONPATH "
                "and cannot resolve the skills package when launched"
            )


def test_script_mode_launch_resolves_skills_package():
    """Launch a server exactly the way .mcp.json does.

    A missing external dependency (`No module named 'mcp'` on hosts without
    the real package) is an install concern and is tolerated here; the path
    defect (`No module named 'skills'`) is ours and is not.
    """
    cfg = phase._server("skills/planning_mcp.py")
    env = {**os.environ, **cfg.get("env", {})}
    proc = subprocess.run(
        [sys.executable, *cfg["args"]],
        input="",
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        cwd=str(phase.PROJECT_ROOT),
    )
    assert "No module named 'skills'" not in proc.stderr
