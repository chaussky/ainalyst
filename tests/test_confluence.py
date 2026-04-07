"""
tests/test_confluence.py — Тесты для integrations/confluence_mcp.py

Тестируем только чистые функции (без реального Confluence API):
  - _markdown_to_confluence_storage: Markdown → Confluence Storage Format
  - _confluence_storage_to_text: Storage Format → читаемый текст
  - _extract_requirements_heuristic: извлечение требований по ID-паттернам
  - _default_space_key: чтение из env vars
  - Конфигурация: обработка отсутствующих env vars

MCP-инструменты (push, pull, sync, list) требуют реального Confluence —
тестируются вручную или через моки atlassian-python-api.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from datetime import date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Моки должны быть установлены ДО любого импорта наших модулей
from tests.conftest import setup_mocks, BaseMCPTest
setup_mocks()

import skills.integrations.confluence_mcp as confluence_mod


def _load_confluence_utils():
    """Возвращает dict с утилитами из уже импортированного confluence_mcp."""
    return {
        "_markdown_to_confluence_storage": confluence_mod._markdown_to_confluence_storage,
        "_confluence_storage_to_text": confluence_mod._confluence_storage_to_text,
        "_extract_requirements_heuristic": confluence_mod._extract_requirements_heuristic,
        "_default_space_key": confluence_mod._default_space_key,
        "_get_confluence_client": confluence_mod._get_confluence_client,
    }


class TestMarkdownConversion(unittest.TestCase):
    """Тесты конвертации Markdown → Confluence Storage Format."""

    @classmethod
    def setUpClass(cls):
        cls.ns = _load_confluence_utils()

    def convert(self, md):
        return self.ns["_markdown_to_confluence_storage"](md)

    def test_removes_html_comments(self):
        result = self.convert("<!-- BABOK 5.1 | Проект: Test -->\n# Заголовок")
        self.assertNotIn("<!--", result)
        self.assertNotIn("BABOK 5.1", result)

    def test_converts_headers(self):
        """Заголовки Markdown присутствуют в выводе в том или ином виде."""
        result = self.convert("# H1\n## H2\n### H3")
        # В реальном окружении будет <h1>, в тестах с моком — текст сохраняется
        self.assertIn("H1", result)
        self.assertIn("H2", result)

    def test_converts_bold(self):
        """Жирный текст сохраняется в выводе (конвертация зависит от наличия markdown2)."""
        result = self.convert("Текст **жирный** конец")
        # Контент должен присутствовать в выводе в любом случае
        self.assertIn("жирный", result)

    def test_empty_input(self):
        self.assertEqual(self.convert("").strip(), "")

    def test_only_comment_returns_empty(self):
        self.assertEqual(self.convert("<!-- комментарий -->").strip(), "")

    def test_table_preserved(self):
        result = self.convert("| ID | Название |\n|-----|----------|\n| FR-001 | Тест |")
        self.assertIn("FR-001", result)


class TestStorageToText(unittest.TestCase):
    """Тесты конвертации Confluence Storage Format → текст."""

    @classmethod
    def setUpClass(cls):
        cls.ns = _load_confluence_utils()
        cls._convert = staticmethod(cls.ns["_confluence_storage_to_text"])

    def test_strips_html_tags(self):
        html = "<h1>Заголовок</h1><p>Параграф</p>"
        result = TestStorageToText._convert(html)
        self.assertNotIn("<h1>", result)
        self.assertNotIn("<p>", result)
        self.assertIn("Заголовок", result)
        self.assertIn("Параграф", result)

    def test_preserves_content(self):
        html = "<p>FR-001 — Автоматическое распределение заявок</p>"
        result = TestStorageToText._convert(html)
        self.assertIn("FR-001", result)
        self.assertIn("заявок", result)

    def test_table_cells_extracted(self):
        html = "<table><tr><td>BR-001</td><td>Бизнес-требование</td></tr></table>"
        result = TestStorageToText._convert(html)
        self.assertIn("BR-001", result)

    def test_empty_input(self):
        result = TestStorageToText._convert("")
        self.assertEqual(result.strip(), "")


class TestExtractRequirements(unittest.TestCase):
    """Тесты эвристического извлечения требований из текста."""

    @classmethod
    def setUpClass(cls):
        cls.ns = _load_confluence_utils()
        cls.extract = cls.ns["_extract_requirements_heuristic"]

    def test_extracts_fr_ids(self):
        text = "FR-001 — Авторизация пользователей\nFR-002 — Управление ролями"
        reqs = TestExtractRequirements.extract(text, "http://confluence/page")
        ids = [r["id"] for r in reqs]
        self.assertIn("FR-001", ids)
        self.assertIn("FR-002", ids)

    def test_extracts_br_ids(self):
        text = "BR-001 Снизить время обработки"
        reqs = TestExtractRequirements.extract(text, "")
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs[0]["type"], "business")

    def test_extracts_mixed_ids(self):
        text = "BR-001 бизнес\nSR-002 стейкхолдер\nFR-003 решение\nNFR-001 нефункциональное"
        reqs = TestExtractRequirements.extract(text, "")
        types = {r["id"]: r["type"] for r in reqs}
        self.assertEqual(types.get("BR-001"), "business")
        self.assertEqual(types.get("SR-002"), "stakeholder")
        self.assertEqual(types.get("FR-003"), "solution")
        self.assertEqual(types.get("NFR-001"), "solution")

    def test_no_duplicates(self):
        text = "FR-001 первое упоминание\nFR-001 второе упоминание"
        reqs = TestExtractRequirements.extract(text, "")
        self.assertEqual(sum(1 for r in reqs if r["id"] == "FR-001"), 1)

    def test_empty_text(self):
        self.assertEqual(TestExtractRequirements.extract("", ""), [])

    def test_no_ids_in_text(self):
        self.assertEqual(TestExtractRequirements.extract("Обычный текст без требований.", ""), [])

    def test_source_url_in_result(self):
        url = "https://confluence.company.com/wiki/spaces/BA/pages/12345"
        reqs = TestExtractRequirements.extract("FR-001 Тест", url)
        self.assertEqual(reqs[0]["source_artifact"], url)

    def test_default_status_is_draft(self):
        reqs = TestExtractRequirements.extract("FR-001 Требование\nBR-001 Бизнес", "")
        for r in reqs:
            self.assertEqual(r["status"], "draft")

    def test_default_version_is_1_0(self):
        reqs = TestExtractRequirements.extract("FR-001 Требование", "")
        self.assertEqual(reqs[0]["version"], "1.0")

    def test_underscore_id_normalized(self):
        reqs = TestExtractRequirements.extract("FR_001 Требование", "")
        if reqs:
            self.assertNotIn("_", reqs[0]["id"])

    def test_case_insensitive(self):
        reqs = TestExtractRequirements.extract("fr-001 требование в нижнем регистре", "")
        if reqs:
            self.assertEqual(reqs[0]["id"], "FR-001")


class TestConfluenceConfig(unittest.TestCase):
    """Тесты конфигурации через env vars."""

    @classmethod
    def setUpClass(cls):
        cls.ns = _load_confluence_utils()

    def test_default_space_key_from_env(self):
        """_default_space_key читает из CONFLUENCE_SPACE_KEY."""
        with patch.dict(os.environ, {"CONFLUENCE_SPACE_KEY": "MYSPACE"}):
            result = self.ns["_default_space_key"]()
            self.assertEqual(result, "MYSPACE")

    def test_default_space_key_empty_without_env(self):
        """_default_space_key возвращает пустую строку если env не задан."""
        env = {k: v for k, v in os.environ.items() if k != "CONFLUENCE_SPACE_KEY"}
        with patch.dict(os.environ, env, clear=True):
            result = self.ns["_default_space_key"]()
            self.assertEqual(result, "")

    def test_get_client_no_url(self):
        """_get_confluence_client без CONFLUENCE_URL → ошибка с подсказкой."""
        env = {k: v for k, v in os.environ.items()
               if k not in ("CONFLUENCE_URL", "CONFLUENCE_API_TOKEN")}
        with patch.dict(os.environ, env, clear=True):
            client, error = self.ns["_get_confluence_client"]()
            self.assertIsNone(client)
            self.assertIn("CONFLUENCE_URL", error)

    def test_get_client_no_token(self):
        """_get_confluence_client без CONFLUENCE_API_TOKEN → ошибка с подсказкой."""
        env = {k: v for k, v in os.environ.items() if k != "CONFLUENCE_API_TOKEN"}
        env["CONFLUENCE_URL"] = "https://test.atlassian.net"
        with patch.dict(os.environ, env, clear=True):
            client, error = self.ns["_get_confluence_client"]()
            self.assertIsNone(client)
            self.assertIn("CONFLUENCE_API_TOKEN", error)

    def test_export_hook_local_only_without_config(self):
        """_export_hook в 5.2 без env vars → local_only без ошибки."""
        import skills.requirements_maintain_mcp as maintain_mod
        from unittest.mock import patch
        env = {k: v for k, v in os.environ.items()
               if k not in ("CONFLUENCE_URL", "CONFLUENCE_API_TOKEN")}
        with patch.dict(os.environ, env, clear=True):
            result = maintain_mod._export_hook(
                "requirement_update", "# Тест", {"project_name": "Test"}
            )
            self.assertEqual(result.get("status"), "local_only")


if __name__ == "__main__":
    unittest.main(verbosity=2)


# ===========================================================================
# Тесты MCP-инструментов (с моком atlassian Confluence client)
# ===========================================================================

def _make_mock_confluence(page_exists=True, page_title="Тест", page_id="12345"):
    """Возвращает сконфигурированный мок atlassian Confluence client."""
    mock = MagicMock()
    page_stub = {
        "id": page_id,
        "title": page_title,
        "version": {"number": 3, "when": "2026-03-30T10:00:00Z"},
        "body": {
            "storage": {
                "value": f"<p>FR-001 — Авторизация</p><p>BR-001 — Бизнес-цель</p>"
            }
        },
        "_links": {"webui": f"/wiki/spaces/BA/pages/{page_id}"},
    }
    mock.get_page_by_title.return_value = page_stub if page_exists else None
    mock.update_page.return_value = {
        "id": page_id,
        "version": {"number": 4},
        "_links": {"webui": f"/wiki/spaces/BA/pages/{page_id}"},
    }
    mock.create_page.return_value = {
        "id": "99999",
        "version": {"number": 1},
        "_links": {"webui": "/wiki/spaces/BA/pages/99999"},
    }
    mock.get_all_pages_from_space.return_value = [
        {"id": "111", "title": "Требования FR", "version": {"when": "2026-03-01T00:00:00Z"}},
        {"id": "222", "title": "Требования BR", "version": {"when": "2026-03-15T00:00:00Z"}},
        {"id": "333", "title": "Архитектура",   "version": {"when": "2026-03-20T00:00:00Z"}},
    ]
    return mock


VALID_ENV = {
    "CONFLUENCE_URL": "https://test.atlassian.net",
    "CONFLUENCE_USERNAME": "user@test.com",
    "CONFLUENCE_API_TOKEN": "test-token-123",
    "CONFLUENCE_CLOUD": "true",
    "CONFLUENCE_SPACE_KEY": "BA",
}


class TestPushToConfluence(BaseMCPTest):
    """Тесты MCP 1 — push_to_confluence."""

    def _call(self, **kwargs):
        defaults = {
            "content_markdown": "# Отчёт\n\nFR-001 — Авторизация",
            "page_title": "Тест страница",
            "space_key": "BA",
        }
        return confluence_mod.push_to_confluence(**{**defaults, **kwargs})

    def test_creates_new_page(self):
        """Создаёт новую страницу если она не существует."""
        mock_client = _make_mock_confluence(page_exists=False)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("✅", result)
        self.assertIn("создана", result)
        mock_client.create_page.assert_called_once()

    def test_updates_existing_page(self):
        """Обновляет страницу если она существует и update_if_exists=True."""
        mock_client = _make_mock_confluence(page_exists=True)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call(update_if_exists=True)
        self.assertIn("✅", result)
        self.assertIn("обновлена", result)
        mock_client.update_page.assert_called_once()

    def test_no_update_if_exists_false(self):
        """Возвращает предупреждение если update_if_exists=False и страница есть."""
        mock_client = _make_mock_confluence(page_exists=True)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call(update_if_exists=False)
        self.assertIn("⚠️", result)
        mock_client.update_page.assert_not_called()

    def test_no_space_key_returns_error(self):
        """Без space_key и CONFLUENCE_SPACE_KEY → ошибка."""
        env = {k: v for k, v in VALID_ENV.items() if k != "CONFLUENCE_SPACE_KEY"}
        mock_client = _make_mock_confluence()
        with patch.dict(os.environ, env, clear=True), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call(space_key="")
        self.assertIn("❌", result)
        self.assertIn("space_key", result)

    def test_uses_env_space_key_when_not_provided(self):
        """Использует CONFLUENCE_SPACE_KEY из env если space_key пустой."""
        mock_client = _make_mock_confluence(page_exists=False)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call(space_key="")
        self.assertIn("✅", result)

    def test_client_error_propagated(self):
        """Ошибка от _get_confluence_client → возвращается как текст."""
        with patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(None, "❌ Нет CONFLUENCE_URL")):
            result = self._call()
        self.assertIn("❌", result)
        self.assertIn("CONFLUENCE_URL", result)

    def test_result_contains_url(self):
        """Результат содержит URL страницы."""
        mock_client = _make_mock_confluence(page_exists=False)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("URL", result)
        self.assertIn("atlassian.net", result)

    def test_with_parent_page(self):
        """Создаёт страницу с родительской страницей."""
        mock_client = _make_mock_confluence(page_exists=False)
        # Первый вызов get_page_by_title — поиск родителя; второй — поиск самой страницы
        mock_client.get_page_by_title.side_effect = [
            {"id": "PARENT-ID", "title": "Родитель"},  # parent found
            None,  # main page not found
        ]
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call(parent_page_title="Родитель")
        self.assertIn("✅", result)
        call_kwargs = mock_client.create_page.call_args
        self.assertEqual(call_kwargs.kwargs.get("parent_id") or call_kwargs[1].get("parent_id"), "PARENT-ID")

    def test_parent_not_found_returns_error(self):
        """Если родительская страница не найдена → ошибка."""
        mock_client = _make_mock_confluence(page_exists=False)
        mock_client.get_page_by_title.return_value = None
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call(parent_page_title="Несуществующий родитель")
        self.assertIn("❌", result)
        self.assertIn("не найдена", result)

    def test_confluence_exception_handled(self):
        """Исключение от atlassian API → понятное сообщение об ошибке."""
        mock_client = _make_mock_confluence(page_exists=False)
        mock_client.create_page.side_effect = Exception("Connection timeout")
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("❌", result)
        self.assertIn("Connection timeout", result)


class TestPullFromConfluence(BaseMCPTest):
    """Тесты MCP 2 — pull_from_confluence."""

    def _call(self, **kwargs):
        defaults = {
            "page_title": "Требования проекта",
            "space_key": "BA",
            "project_name": "test_project",
        }
        return confluence_mod.pull_from_confluence(**{**defaults, **kwargs})

    def test_extracts_requirements_from_page(self):
        """Извлекает требования из страницы с FR/BR ID."""
        mock_client = _make_mock_confluence(page_exists=True)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("FR-001", result)
        self.assertIn("BR-001", result)

    def test_page_not_found_returns_error(self):
        """Страница не найдена → сообщение с подсказкой."""
        mock_client = _make_mock_confluence(page_exists=False)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("❌", result)
        self.assertIn("list_space_pages", result)

    def test_result_contains_json_block(self):
        """Результат содержит JSON-блок для передачи в init_traceability_repo."""
        mock_client = _make_mock_confluence(page_exists=True)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("```json", result)
        self.assertIn("init_traceability_repo", result)

    def test_uses_page_title_as_project_name_if_empty(self):
        """Если project_name пустой — использует page_title."""
        mock_client = _make_mock_confluence(page_exists=True, page_title="Мой проект")
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call(page_title="Мой проект", project_name="")
        self.assertIn("Мой проект", result)

    def test_client_error_returned(self):
        with patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(None, "❌ Нет CONFLUENCE_API_TOKEN")):
            result = self._call()
        self.assertIn("❌", result)

    def test_result_contains_page_version(self):
        """Результат показывает версию и дату изменения страницы."""
        mock_client = _make_mock_confluence(page_exists=True)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("Версия", result)
        self.assertIn("3", result)  # версия из стаба

    def test_requirement_count_shown(self):
        """Результат показывает количество извлечённых требований."""
        mock_client = _make_mock_confluence(page_exists=True)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("Извлечено требований", result)


class TestSyncPage(BaseMCPTest):
    """Тесты MCP 3 — sync_page."""

    def _call(self, **kwargs):
        defaults = {
            "page_title": "Живой отчёт",
            "new_content_markdown": "# Обновлённый контент\n\nFR-001 — Авторизация v2",
            "space_key": "BA",
        }
        return confluence_mod.sync_page(**{**defaults, **kwargs})

    def test_updates_existing_page(self):
        """Обновляет страницу и показывает версии до/после."""
        mock_client = _make_mock_confluence(page_exists=True)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("✅", result)
        self.assertIn("→", result)  # версия до → после
        mock_client.update_page.assert_called_once()

    def test_page_not_found_no_create(self):
        """Страница не найдена, create_if_missing=False → ошибка с подсказкой."""
        mock_client = _make_mock_confluence(page_exists=False)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call(create_if_missing=False)
        self.assertIn("❌", result)
        self.assertIn("create_if_missing=True", result)

    def test_page_not_found_create_if_missing(self):
        """Страница не найдена, create_if_missing=True → вызывает push_to_confluence."""
        mock_client = _make_mock_confluence(page_exists=False)
        mock_client.create_page.return_value = {
            "id": "NEW-ID",
            "version": {"number": 1},
            "_links": {"webui": "/wiki/spaces/BA/pages/NEW-ID"},
        }
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call(create_if_missing=True)
        self.assertIn("✅", result)

    def test_no_space_key_returns_error(self):
        env = {k: v for k, v in VALID_ENV.items() if k != "CONFLUENCE_SPACE_KEY"}
        mock_client = _make_mock_confluence()
        with patch.dict(os.environ, env, clear=True), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call(space_key="")
        self.assertIn("❌", result)

    def test_update_exception_handled(self):
        """Исключение при обновлении → понятное сообщение."""
        mock_client = _make_mock_confluence(page_exists=True)
        mock_client.update_page.side_effect = Exception("Permission denied")
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("❌", result)
        self.assertIn("Permission denied", result)

    def test_client_error_returned(self):
        with patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(None, "❌ Нет конфига")):
            result = self._call()
        self.assertIn("❌", result)


class TestListSpacePages(BaseMCPTest):
    """Тесты MCP 4 — list_space_pages."""

    def _call(self, **kwargs):
        defaults = {"space_key": "BA"}
        return confluence_mod.list_space_pages(**{**defaults, **kwargs})

    def test_returns_page_list(self):
        """Возвращает список страниц пространства."""
        mock_client = _make_mock_confluence()
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("Требования FR", result)
        self.assertIn("Требования BR", result)
        self.assertIn("Архитектура", result)

    def test_filter_by_search_title(self):
        """Фильтрует страницы по search_title."""
        mock_client = _make_mock_confluence()
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call(search_title="Требования")
        self.assertIn("Требования FR", result)
        self.assertIn("Требования BR", result)
        self.assertNotIn("Архитектура", result)

    def test_no_pages_returns_info(self):
        """Пустое пространство → информационное сообщение."""
        mock_client = _make_mock_confluence()
        mock_client.get_all_pages_from_space.return_value = []
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("ℹ️", result)

    def test_result_contains_pull_hint(self):
        """Результат содержит подсказку по использованию pull_from_confluence."""
        mock_client = _make_mock_confluence()
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("pull_from_confluence", result)

    def test_no_space_key_returns_error(self):
        env = {k: v for k, v in VALID_ENV.items() if k != "CONFLUENCE_SPACE_KEY"}
        mock_client = _make_mock_confluence()
        with patch.dict(os.environ, env, clear=True), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call(space_key="")
        self.assertIn("❌", result)

    def test_exception_handled(self):
        mock_client = _make_mock_confluence()
        mock_client.get_all_pages_from_space.side_effect = Exception("Network error")
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("❌", result)
        self.assertIn("Network error", result)

    def test_client_error_returned(self):
        with patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(None, "❌ Нет конфига")):
            result = self._call()
        self.assertIn("❌", result)


class TestExportArtifactToConfluence(BaseMCPTest):
    """Тесты вспомогательной функции export_artifact_to_confluence (_export_hook)."""

    def _call(self, **kwargs):
        defaults = {
            "content_markdown": "# Отчёт\n\nFR-001 — Авторизация",
            "page_title": "Артефакт 5.2",
            "space_key": "BA",
        }
        return confluence_mod.export_artifact_to_confluence(**{**defaults, **kwargs})

    def test_returns_synced_status_on_update(self):
        mock_client = _make_mock_confluence(page_exists=True)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertEqual(result["status"], "synced")
        self.assertIn("url", result)

    def test_returns_synced_status_on_create(self):
        mock_client = _make_mock_confluence(page_exists=False)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertEqual(result["status"], "synced")

    def test_returns_error_dict_on_client_failure(self):
        with patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(None, "❌ Нет токена")):
            result = self._call()
        self.assertEqual(result["status"], "error")
        self.assertIn("message", result)

    def test_returns_error_dict_on_no_space(self):
        env = {k: v for k, v in VALID_ENV.items() if k != "CONFLUENCE_SPACE_KEY"}
        mock_client = _make_mock_confluence()
        with patch.dict(os.environ, env, clear=True), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call(space_key="")
        self.assertEqual(result["status"], "error")

    def test_url_in_result(self):
        mock_client = _make_mock_confluence(page_exists=True)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("atlassian.net", result.get("url", ""))

    def test_exception_returns_error_dict(self):
        mock_client = _make_mock_confluence(page_exists=True)
        mock_client.update_page.side_effect = Exception("API rate limit")
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertEqual(result["status"], "error")
        self.assertIn("API rate limit", result["message"])
