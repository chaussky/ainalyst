"""
tests/conftest.py — shared utilities and fixtures for all tests.

Mocking strategy:
  All external dependencies (mcp, pydantic, atlassian) are mocked at the sys.modules
  level in the setup_mocks() function — called once before the first import of project modules.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock
from datetime import date

# Add the project root to the path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def setup_mocks():
    """
    Mocks all external dependencies before importing project modules.
    Call once at the start of a test file.
    """
    # FastMCP: the @mcp.tool() decorator must return the function as-is
    mock_instance = MagicMock()
    mock_instance.tool = lambda: (lambda f: f)

    mock_fastmcp_cls = MagicMock(return_value=mock_instance)

    fastmcp_mod = MagicMock()
    fastmcp_mod.FastMCP = mock_fastmcp_cls

    sys.modules.setdefault("mcp", MagicMock())
    sys.modules.setdefault("mcp.server", MagicMock())
    sys.modules["mcp.server.fastmcp"] = fastmcp_mod

    # Pydantic: a minimal BaseModel
    if "pydantic" not in sys.modules:
        pydantic_mock = MagicMock()

        class BaseModel:
            def __init__(self, **kw):
                for k, v in kw.items():
                    setattr(self, k, v)
            def __init_subclass__(cls, **kwargs):
                pass

        pydantic_mock.BaseModel = BaseModel
        pydantic_mock.Field = MagicMock(return_value=None)
        sys.modules["pydantic"] = pydantic_mock

    # Atlassian Confluence
    sys.modules.setdefault("atlassian", MagicMock())

    # markdown2 — returns the input text as HTML (enough for the tests)
    markdown2_mock = MagicMock()
    markdown2_mock.markdown = lambda text, **kwargs: f"<p>{text}</p>" if text else ""
    sys.modules["markdown2"] = markdown2_mock

    # Patch save_artifact in common
    import skills.common as common_mod
    common_mod.save_artifact = MagicMock(return_value="✅ Saved")


# Apply the mocks immediately on importing conftest
setup_mocks()


def make_test_repo(project_name: str = "test_project") -> dict:
    """Creates a minimal test traceability repository."""
    return {
        "project": project_name,
        "formality_level": "Standard",
        "created": str(date.today()),
        "updated": str(date.today()),
        "requirements": [
            {
                "id": "BR-001",
                "type": "business",
                "title": "Reduce request processing time",
                "version": "1.0",
                "status": "confirmed",
                "source_artifact": "governance_plans/4_3_test.md",
                "added": str(date.today()),
            },
            {
                "id": "FR-001",
                "type": "solution",
                "title": "The system automatically distributes requests",
                "version": "1.0",
                "status": "confirmed",
                "source_artifact": "governance_plans/4_3_test.md",
                "added": str(date.today()),
            },
            {
                "id": "FR-002",
                "type": "solution",
                "title": "Notifications on request status change",
                "version": "1.0",
                "status": "draft",
                "source_artifact": "governance_plans/4_3_test.md",
                "added": str(date.today()),
            },
            {
                "id": "TC-001",
                "type": "test",
                "title": "Auto-distribution test",
                "version": "1.0",
                "status": "draft",
                "added": str(date.today()),
            },
        ],
        "links": [
            {
                "from": "FR-001",
                "to": "BR-001",
                "relation": "derives",
                "rationale": "FR derives from the business requirement",
                "added": str(date.today()),
            },
            {
                "from": "TC-001",
                "to": "FR-001",
                "relation": "verifies",
                "rationale": "The test verifies the requirement",
                "added": str(date.today()),
            },
        ],
        "history": [],
    }


def save_test_repo(repo: dict, governance_dir: str = "governance_plans/data") -> str:
    """Saves the test repository FLAT (legacy layout, issue #1).

    Intentionally writes to a flat data/ to reproduce already-existing
    (pre-migration) artifacts: the module path resolver data_path will see the flat
    file and keep reading/writing it in place — a fallback to legacy.
    """
    safe_name = repo["project"].lower().replace(" ", "_")
    path = os.path.join(governance_dir, f"{safe_name}_traceability_repo.json")
    os.makedirs(governance_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)
    return path


def load_test_repo(project_name: str, governance_dir: str = "governance_plans/data") -> dict:
    """Loads the test repository via the shared path resolver (issue #1)."""
    from skills.common import data_path
    safe_name = project_name.lower().replace(" ", "_")
    path = data_path(project_name, f"{safe_name}_traceability_repo.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_data_files(suffix: str = ".json", base: str = "governance_plans/data") -> list:
    """Recursively lists files in data/ (including project subfolders, issue #1)."""
    out = []
    for root, _dirs, files in os.walk(base):
        for f in files:
            if f.endswith(suffix):
                out.append(os.path.join(root, f))
    return out


class BaseMCPTest(unittest.TestCase):
    """
    Base class for testing MCP tools.
    Creates a temporary directory and switches into it (all files are written there).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self._orig_cwd = os.getcwd()
        os.chdir(self.tmp_dir)
        os.makedirs("governance_plans", exist_ok=True)
        os.makedirs("governance_plans/data", exist_ok=True)
        os.makedirs("governance_plans/reports", exist_ok=True)

    def tearDown(self):
        os.chdir(self._orig_cwd)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
