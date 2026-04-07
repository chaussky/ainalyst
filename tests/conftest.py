"""
tests/conftest.py — общие утилиты и фикстуры для всех тестов.

Стратегия мокинга:
  Все внешние зависимости (mcp, pydantic, atlassian) мокаются на уровне sys.modules
  в функции setup_mocks() — вызывается один раз перед первым импортом модулей проекта.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock
from datetime import date

# Добавляем корень проекта в path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def setup_mocks():
    """
    Мокает все внешние зависимости до импорта модулей проекта.
    Вызывать один раз в начале тестового файла.
    """
    # FastMCP: декоратор @mcp.tool() должен возвращать функцию как есть
    mock_instance = MagicMock()
    mock_instance.tool = lambda: (lambda f: f)

    mock_fastmcp_cls = MagicMock(return_value=mock_instance)

    fastmcp_mod = MagicMock()
    fastmcp_mod.FastMCP = mock_fastmcp_cls

    sys.modules.setdefault("mcp", MagicMock())
    sys.modules.setdefault("mcp.server", MagicMock())
    sys.modules["mcp.server.fastmcp"] = fastmcp_mod

    # Pydantic: минимальный BaseModel
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

    # markdown2 — возвращает входной текст как HTML (достаточно для тестов)
    markdown2_mock = MagicMock()
    markdown2_mock.markdown = lambda text, **kwargs: f"<p>{text}</p>" if text else ""
    sys.modules["markdown2"] = markdown2_mock

    # Патчим save_artifact в common
    import skills.common as common_mod
    common_mod.save_artifact = MagicMock(return_value="✅ Сохранено")


# Применяем моки сразу при импорте conftest
setup_mocks()


def make_test_repo(project_name: str = "test_project") -> dict:
    """Создаёт минимальный тестовый репозиторий трассировки."""
    return {
        "project": project_name,
        "formality_level": "Standard",
        "created": str(date.today()),
        "updated": str(date.today()),
        "requirements": [
            {
                "id": "BR-001",
                "type": "business",
                "title": "Снизить время обработки заявки",
                "version": "1.0",
                "status": "confirmed",
                "source_artifact": "governance_plans/4_3_test.md",
                "added": str(date.today()),
            },
            {
                "id": "FR-001",
                "type": "solution",
                "title": "Система автоматически распределяет заявки",
                "version": "1.0",
                "status": "confirmed",
                "source_artifact": "governance_plans/4_3_test.md",
                "added": str(date.today()),
            },
            {
                "id": "FR-002",
                "type": "solution",
                "title": "Уведомления о смене статуса заявки",
                "version": "1.0",
                "status": "draft",
                "source_artifact": "governance_plans/4_3_test.md",
                "added": str(date.today()),
            },
            {
                "id": "TC-001",
                "type": "test",
                "title": "Тест автораспределения",
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
                "rationale": "FR вытекает из бизнес-требования",
                "added": str(date.today()),
            },
            {
                "from": "TC-001",
                "to": "FR-001",
                "relation": "verifies",
                "rationale": "Тест проверяет требование",
                "added": str(date.today()),
            },
        ],
        "history": [],
    }


def save_test_repo(repo: dict, governance_dir: str = "governance_plans/data") -> str:
    """Сохраняет тестовый репозиторий. Возвращает путь."""
    safe_name = repo["project"].lower().replace(" ", "_")
    path = os.path.join(governance_dir, f"{safe_name}_traceability_repo.json")
    os.makedirs(governance_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)
    return path


def load_test_repo(project_name: str, governance_dir: str = "governance_plans/data") -> dict:
    """Загружает тестовый репозиторий."""
    safe_name = project_name.lower().replace(" ", "_")
    path = os.path.join(governance_dir, f"{safe_name}_traceability_repo.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class BaseMCPTest(unittest.TestCase):
    """
    Базовый класс для тестирования MCP-инструментов.
    Создаёт временную директорию и переходит в неё (все файлы пишутся там).
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
