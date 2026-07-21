"""
tests/test_confluence.py — Tests for integrations/confluence_mcp.py

We test only the pure functions (without a real Confluence API):
  - _markdown_to_confluence_storage: Markdown → Confluence Storage Format
  - _confluence_storage_to_text: Storage Format → readable text
  - _extract_requirements_heuristic: extracting requirements by ID patterns
  - _default_space_key: reading from env vars
  - Configuration: handling of missing env vars

MCP tools (push, pull, sync, list) require a real Confluence —
they are tested manually or via atlassian-python-api mocks.
"""

import os
import re
import sys
import unittest
from unittest.mock import patch, MagicMock
from datetime import date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Mocks must be installed BEFORE importing any of our modules
from tests.conftest import setup_mocks, BaseMCPTest
setup_mocks()

import skills.integrations.confluence_mcp as confluence_mod


def _load_confluence_utils():
    """Returns a dict with the utilities from the already-imported confluence_mcp."""
    return {
        "_markdown_to_confluence_storage": confluence_mod._markdown_to_confluence_storage,
        "_confluence_storage_to_text": confluence_mod._confluence_storage_to_text,
        "_extract_requirements_heuristic": confluence_mod._extract_requirements_heuristic,
        "_default_space_key": confluence_mod._default_space_key,
        "_get_confluence_client": confluence_mod._get_confluence_client,
    }


class TestMarkdownConversion(unittest.TestCase):
    """Tests for the Markdown → Confluence Storage Format conversion."""

    @classmethod
    def setUpClass(cls):
        cls.ns = _load_confluence_utils()

    def convert(self, md):
        return self.ns["_markdown_to_confluence_storage"](md)

    def test_removes_html_comments(self):
        result = self.convert("<!-- BABOK 5.1 | Project: Test -->\n# Heading")
        self.assertNotIn("<!--", result)
        self.assertNotIn("BABOK 5.1", result)

    def test_converts_headers(self):
        """Markdown headers are present in the output in one form or another."""
        result = self.convert("# H1\n## H2\n### H3")
        # In a real environment this will be <h1>, in tests with a mock — the text is preserved
        self.assertIn("H1", result)
        self.assertIn("H2", result)

    def test_converts_bold(self):
        """Bold text is preserved in the output (conversion depends on whether markdown2 is present)."""
        result = self.convert("Text **bold** end")
        # The content must be present in the output either way
        self.assertIn("bold", result)

    def test_empty_input(self):
        self.assertEqual(self.convert("").strip(), "")

    def test_only_comment_returns_empty(self):
        self.assertEqual(self.convert("<!-- comment -->").strip(), "")

    def test_table_preserved(self):
        result = self.convert("| ID | Title |\n|-----|-------|\n| FR-001 | Test |")
        self.assertIn("FR-001", result)


class TestStorageToText(unittest.TestCase):
    """Tests for the Confluence Storage Format → text conversion."""

    @classmethod
    def setUpClass(cls):
        cls.ns = _load_confluence_utils()
        cls._convert = staticmethod(cls.ns["_confluence_storage_to_text"])

    def test_strips_html_tags(self):
        html = "<h1>Heading</h1><p>Paragraph</p>"
        result = TestStorageToText._convert(html)
        self.assertNotIn("<h1>", result)
        self.assertNotIn("<p>", result)
        self.assertIn("Heading", result)
        self.assertIn("Paragraph", result)

    def test_preserves_content(self):
        html = "<p>FR-001 — Automated request distribution</p>"
        result = TestStorageToText._convert(html)
        self.assertIn("FR-001", result)
        self.assertIn("request", result)

    def test_table_cells_extracted(self):
        html = "<table><tr><td>BR-001</td><td>Business requirement</td></tr></table>"
        result = TestStorageToText._convert(html)
        self.assertIn("BR-001", result)

    def test_empty_input(self):
        result = TestStorageToText._convert("")
        self.assertEqual(result.strip(), "")


class TestExtractRequirements(unittest.TestCase):
    """Tests for the heuristic extraction of requirements from text."""

    @classmethod
    def setUpClass(cls):
        cls.ns = _load_confluence_utils()
        cls.extract = cls.ns["_extract_requirements_heuristic"]

    def test_extracts_fr_ids(self):
        text = "FR-001 — User authentication\nFR-002 — Role management"
        reqs = TestExtractRequirements.extract(text, "http://confluence/page")
        ids = [r["id"] for r in reqs]
        self.assertIn("FR-001", ids)
        self.assertIn("FR-002", ids)

    def test_extracts_br_ids(self):
        text = "BR-001 Reduce processing time"
        reqs = TestExtractRequirements.extract(text, "")
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs[0]["type"], "business")

    def test_extracts_mixed_ids(self):
        text = "BR-001 business\nSR-002 stakeholder\nFR-003 solution\nNFR-001 non-functional"
        reqs = TestExtractRequirements.extract(text, "")
        types = {r["id"]: r["type"] for r in reqs}
        self.assertEqual(types.get("BR-001"), "business")
        self.assertEqual(types.get("SR-002"), "stakeholder")
        self.assertEqual(types.get("FR-003"), "solution")
        self.assertEqual(types.get("NFR-001"), "solution")

    def test_no_duplicates(self):
        text = "FR-001 first mention\nFR-001 second mention"
        reqs = TestExtractRequirements.extract(text, "")
        self.assertEqual(sum(1 for r in reqs if r["id"] == "FR-001"), 1)

    def test_empty_text(self):
        self.assertEqual(TestExtractRequirements.extract("", ""), [])

    def test_no_ids_in_text(self):
        self.assertEqual(TestExtractRequirements.extract("Plain text without requirements.", ""), [])

    def test_source_url_in_result(self):
        url = "https://confluence.company.com/wiki/spaces/BA/pages/12345"
        reqs = TestExtractRequirements.extract("FR-001 Test", url)
        self.assertEqual(reqs[0]["source_artifact"], url)

    def test_default_status_is_draft(self):
        reqs = TestExtractRequirements.extract("FR-001 Requirement\nBR-001 Business", "")
        for r in reqs:
            self.assertEqual(r["status"], "draft")

    def test_default_version_is_1_0(self):
        reqs = TestExtractRequirements.extract("FR-001 Requirement", "")
        self.assertEqual(reqs[0]["version"], "1.0")

    def test_underscore_id_normalized(self):
        reqs = TestExtractRequirements.extract("FR_001 Requirement", "")
        if reqs:
            self.assertNotIn("_", reqs[0]["id"])

    def test_case_insensitive(self):
        reqs = TestExtractRequirements.extract("fr-001 requirement in lowercase", "")
        if reqs:
            self.assertEqual(reqs[0]["id"], "FR-001")


class TestConfluenceConfig(unittest.TestCase):
    """Tests for configuration via env vars."""

    @classmethod
    def setUpClass(cls):
        cls.ns = _load_confluence_utils()

    def test_default_space_key_from_env(self):
        """_default_space_key reads from CONFLUENCE_SPACE_KEY."""
        with patch.dict(os.environ, {"CONFLUENCE_SPACE_KEY": "MYSPACE"}):
            result = self.ns["_default_space_key"]()
            self.assertEqual(result, "MYSPACE")

    def test_default_space_key_empty_without_env(self):
        """_default_space_key returns an empty string if the env var is not set."""
        env = {k: v for k, v in os.environ.items() if k != "CONFLUENCE_SPACE_KEY"}
        with patch.dict(os.environ, env, clear=True):
            result = self.ns["_default_space_key"]()
            self.assertEqual(result, "")

    def test_get_client_no_url(self):
        """_get_confluence_client without CONFLUENCE_URL → error with a hint."""
        env = {k: v for k, v in os.environ.items()
               if k not in ("CONFLUENCE_URL", "CONFLUENCE_API_TOKEN")}
        with patch.dict(os.environ, env, clear=True):
            client, error = self.ns["_get_confluence_client"]()
            self.assertIsNone(client)
            self.assertIn("CONFLUENCE_URL", error)

    def test_get_client_no_token(self):
        """_get_confluence_client without CONFLUENCE_API_TOKEN → error with a hint."""
        env = {k: v for k, v in os.environ.items() if k != "CONFLUENCE_API_TOKEN"}
        env["CONFLUENCE_URL"] = "https://test.atlassian.net"
        with patch.dict(os.environ, env, clear=True):
            client, error = self.ns["_get_confluence_client"]()
            self.assertIsNone(client)
            self.assertIn("CONFLUENCE_API_TOKEN", error)

    def test_export_hook_local_only_without_config(self):
        """_export_hook in 5.2 without env vars → local_only without an error."""
        import skills.requirements_maintain_mcp as maintain_mod
        from unittest.mock import patch
        env = {k: v for k, v in os.environ.items()
               if k not in ("CONFLUENCE_URL", "CONFLUENCE_API_TOKEN")}
        with patch.dict(os.environ, env, clear=True):
            result = maintain_mod._export_hook(
                "requirement_update", "# Test", {"project_name": "Test"}
            )
            self.assertEqual(result.get("status"), "local_only")


if __name__ == "__main__":
    unittest.main(verbosity=2)


# ===========================================================================
# MCP tool tests (with a mocked atlassian Confluence client)
# ===========================================================================

CLOUD_BASE = "https://test.atlassian.net/wiki"


def _make_mock_confluence(page_exists=True, page_title="Test", page_id="12345"):
    """Returns a configured mock of the atlassian Confluence client.

    The `_links` shapes mirror the REAL Confluence API:
      - `webui` is relative to the deployment's context path and does NOT contain /wiki;
      - content objects (create_page / update_page) carry `_links.base`;
      - a get_page_by_title hit is a search result and carries NO `base`.
    """
    mock = MagicMock()
    page_stub = {
        "id": page_id,
        "title": page_title,
        "version": {"number": 3, "when": "2026-03-30T10:00:00Z"},
        "body": {
            "storage": {
                "value": f"<p>FR-001 — Authentication</p><p>BR-001 — Business goal</p>"
            }
        },
        "_links": {"webui": f"/spaces/BA/pages/{page_id}"},
    }
    mock.get_page_by_title.return_value = page_stub if page_exists else None
    mock.update_page.return_value = {
        "id": page_id,
        "version": {"number": 4},
        "_links": {"base": CLOUD_BASE, "webui": f"/spaces/BA/pages/{page_id}"},
    }
    mock.create_page.return_value = {
        "id": "99999",
        "version": {"number": 1},
        "_links": {"base": CLOUD_BASE, "webui": "/spaces/BA/pages/99999"},
    }
    space_pages = [
        {"id": "111", "title": "Requirements FR", "version": {"when": "2026-03-01T00:00:00Z"}},
        {"id": "222", "title": "Requirements BR", "version": {"when": "2026-03-15T00:00:00Z"}},
        {"id": "333", "title": "Architecture",   "version": {"when": "2026-03-20T00:00:00Z"}},
    ]
    mock.get_all_pages_from_space.return_value = space_pages

    def _cql(cql_query, **kwargs):
        """Behaves like the server: matches `title ~ "..."` across the whole space
        and returns hits in the rest/api/search shape (page wrapped in `content`)."""
        match = re.search(r'title ~ "([^"]*)"', cql_query)
        needle = (match.group(1) if match else "").lower()
        return {
            "results": [
                {"content": p, "title": p["title"], "lastModified": p["version"]["when"]}
                for p in space_pages if needle in p["title"].lower()
            ]
        }

    mock.cql.side_effect = _cql
    return mock


VALID_ENV = {
    "CONFLUENCE_URL": "https://test.atlassian.net",
    "CONFLUENCE_USERNAME": "user@test.com",
    "CONFLUENCE_API_TOKEN": "test-token-123",
    "CONFLUENCE_CLOUD": "true",
    "CONFLUENCE_SPACE_KEY": "BA",
}


class TestPushToConfluence(BaseMCPTest):
    """Tests for MCP 1 — push_to_confluence."""

    def _call(self, **kwargs):
        defaults = {
            "content_markdown": "# Report\n\nFR-001 — Authentication",
            "page_title": "Test page",
            "space_key": "BA",
        }
        return confluence_mod.push_to_confluence(**{**defaults, **kwargs})

    def test_creates_new_page(self):
        """Creates a new page if it doesn't exist."""
        mock_client = _make_mock_confluence(page_exists=False)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("✅", result)
        self.assertIn("created", result)
        mock_client.create_page.assert_called_once()

    def test_updates_existing_page(self):
        """Updates the page if it exists and update_if_exists=True."""
        mock_client = _make_mock_confluence(page_exists=True)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call(update_if_exists=True)
        self.assertIn("✅", result)
        self.assertIn("updated", result)
        mock_client.update_page.assert_called_once()

    def test_no_update_if_exists_false(self):
        """Returns a warning if update_if_exists=False and the page exists."""
        mock_client = _make_mock_confluence(page_exists=True)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call(update_if_exists=False)
        self.assertIn("⚠️", result)
        mock_client.update_page.assert_not_called()

    def test_no_space_key_returns_error(self):
        """Without space_key and CONFLUENCE_SPACE_KEY → error."""
        env = {k: v for k, v in VALID_ENV.items() if k != "CONFLUENCE_SPACE_KEY"}
        mock_client = _make_mock_confluence()
        with patch.dict(os.environ, env, clear=True), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call(space_key="")
        self.assertIn("❌", result)
        self.assertIn("space_key", result)

    def test_uses_env_space_key_when_not_provided(self):
        """Uses CONFLUENCE_SPACE_KEY from env if space_key is empty."""
        mock_client = _make_mock_confluence(page_exists=False)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call(space_key="")
        self.assertIn("✅", result)

    def test_client_error_propagated(self):
        """An error from _get_confluence_client → returned as text."""
        with patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(None, "❌ No CONFLUENCE_URL")):
            result = self._call()
        self.assertIn("❌", result)
        self.assertIn("CONFLUENCE_URL", result)

    def test_result_contains_url(self):
        """The result contains the page URL."""
        mock_client = _make_mock_confluence(page_exists=False)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("URL", result)
        self.assertIn("atlassian.net", result)

    def test_with_parent_page(self):
        """Creates a page under a parent page."""
        mock_client = _make_mock_confluence(page_exists=False)
        # First get_page_by_title call — searching for the parent; second — searching for the page itself
        mock_client.get_page_by_title.side_effect = [
            {"id": "PARENT-ID", "title": "Parent"},  # parent found
            None,  # main page not found
        ]
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call(parent_page_title="Parent")
        self.assertIn("✅", result)
        call_kwargs = mock_client.create_page.call_args
        self.assertEqual(call_kwargs.kwargs.get("parent_id") or call_kwargs[1].get("parent_id"), "PARENT-ID")

    def test_parent_not_found_returns_error(self):
        """If the parent page is not found → error."""
        mock_client = _make_mock_confluence(page_exists=False)
        mock_client.get_page_by_title.return_value = None
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call(parent_page_title="Nonexistent parent")
        self.assertIn("❌", result)
        self.assertIn("not found", result)

    def test_confluence_exception_handled(self):
        """An exception from the atlassian API → a clear error message."""
        mock_client = _make_mock_confluence(page_exists=False)
        mock_client.create_page.side_effect = Exception("Connection timeout")
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("❌", result)
        self.assertIn("Connection timeout", result)


class TestPullFromConfluence(BaseMCPTest):
    """Tests for MCP 2 — pull_from_confluence."""

    def _call(self, **kwargs):
        defaults = {
            "page_title": "Project requirements",
            "space_key": "BA",
            "project_name": "test_project",
        }
        return confluence_mod.pull_from_confluence(**{**defaults, **kwargs})

    def test_extracts_requirements_from_page(self):
        """Extracts requirements from a page with FR/BR IDs."""
        mock_client = _make_mock_confluence(page_exists=True)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("FR-001", result)
        self.assertIn("BR-001", result)

    def test_page_not_found_returns_error(self):
        """Page not found → message with a hint."""
        mock_client = _make_mock_confluence(page_exists=False)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("❌", result)
        self.assertIn("list_space_pages", result)

    def test_result_contains_json_block(self):
        """The result contains a JSON block to pass to init_traceability_repo."""
        mock_client = _make_mock_confluence(page_exists=True)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("```json", result)
        self.assertIn("init_traceability_repo", result)

    def test_uses_page_title_as_project_name_if_empty(self):
        """If project_name is empty — uses page_title."""
        mock_client = _make_mock_confluence(page_exists=True, page_title="My project")
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call(page_title="My project", project_name="")
        self.assertIn("My project", result)

    def test_client_error_returned(self):
        with patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(None, "❌ No CONFLUENCE_API_TOKEN")):
            result = self._call()
        self.assertIn("❌", result)

    def test_result_contains_page_version(self):
        """The result shows the version and the page's modification date."""
        mock_client = _make_mock_confluence(page_exists=True)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("Version", result)
        self.assertIn("3", result)  # version from the stub

    def test_requirement_count_shown(self):
        """The result shows the number of extracted requirements."""
        mock_client = _make_mock_confluence(page_exists=True)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("Requirements extracted", result)


class TestSyncPage(BaseMCPTest):
    """Tests for MCP 3 — sync_page."""

    def _call(self, **kwargs):
        defaults = {
            "page_title": "Live report",
            "new_content_markdown": "# Updated content\n\nFR-001 — Authentication v2",
            "space_key": "BA",
        }
        return confluence_mod.sync_page(**{**defaults, **kwargs})

    def test_updates_existing_page(self):
        """Updates the page and shows the before/after versions."""
        mock_client = _make_mock_confluence(page_exists=True)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("✅", result)
        self.assertIn("→", result)  # version before → after
        mock_client.update_page.assert_called_once()

    def test_page_not_found_no_create(self):
        """Page not found, create_if_missing=False → error with a hint."""
        mock_client = _make_mock_confluence(page_exists=False)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call(create_if_missing=False)
        self.assertIn("❌", result)
        self.assertIn("create_if_missing=True", result)

    def test_page_not_found_create_if_missing(self):
        """Page not found, create_if_missing=True → calls push_to_confluence."""
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
        """An exception while updating → a clear message."""
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
                   return_value=(None, "❌ No config")):
            result = self._call()
        self.assertIn("❌", result)


class TestListSpacePages(BaseMCPTest):
    """Tests for MCP 4 — list_space_pages."""

    def _call(self, **kwargs):
        defaults = {"space_key": "BA"}
        return confluence_mod.list_space_pages(**{**defaults, **kwargs})

    def test_returns_page_list(self):
        """Returns the list of pages in a space."""
        mock_client = _make_mock_confluence()
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("Requirements FR", result)
        self.assertIn("Requirements BR", result)
        self.assertIn("Architecture", result)

    def test_filter_by_search_title(self):
        """Filters pages by search_title."""
        mock_client = _make_mock_confluence()
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call(search_title="Requirements")
        self.assertIn("Requirements FR", result)
        self.assertIn("Requirements BR", result)
        self.assertNotIn("Architecture", result)

    def test_no_pages_returns_info(self):
        """Empty space → informational message."""
        mock_client = _make_mock_confluence()
        mock_client.get_all_pages_from_space.return_value = []
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = self._call()
        self.assertIn("ℹ️", result)

    def test_result_contains_pull_hint(self):
        """The result contains a hint on using pull_from_confluence."""
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
                   return_value=(None, "❌ No config")):
            result = self._call()
        self.assertIn("❌", result)


class TestConfluenceAuditRegressions(BaseMCPTest):
    """Regression tests for the audit findings in integrations/confluence_mcp.py."""

    # --- C1: Python 3.10/3.11 compatibility (PEP 701) -----------------------

    def test_no_backslash_inside_fstring_expressions(self):
        """A backslash inside an f-string replacement field is a SyntaxError before
        Python 3.12 (lifted only by PEP 701). The project supports Python 3.10+, and
        this module is loaded in EVERY phase (phase.py BASE_SERVER), so such a line
        takes the whole Confluence server down on the declared minimum version."""
        import ast
        import pathlib

        src_path = pathlib.Path(confluence_mod.__file__)
        src = src_path.read_text(encoding="utf-8")
        tree = ast.parse(src)

        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FormattedValue):
                segment = ast.get_source_segment(src, node.value) or ""
                if "\\" in segment:
                    offenders.append((getattr(node, "lineno", "?"), segment))

        self.assertEqual(
            offenders, [],
            f"Backslash inside an f-string expression (SyntaxError on Python <3.12): {offenders}",
        )

    def test_list_space_pages_renders_filter_note(self):
        """The line that carried the backslash still renders the filter note."""
        mock_client = _make_mock_confluence()
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = confluence_mod.list_space_pages(space_key="BA", search_title="Requirements")
        self.assertIn('filter: "Requirements"', result)

    # --- C2: URL building for Cloud vs Server/DC ----------------------------

    def test_cloud_url_has_exactly_one_wiki_context(self):
        """Cloud: base already ends with /wiki and webui is relative to it."""
        mock_client = _make_mock_confluence(page_exists=False)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = confluence_mod.push_to_confluence(
                content_markdown="# X", page_title="P", space_key="BA")
        self.assertIn("https://test.atlassian.net/wiki/spaces/BA/pages/99999", result)
        self.assertNotIn("/wiki/wiki", result)

    def test_server_dc_url_has_no_wiki_context(self):
        """Server/DC serves the web UI at the site root — a hardcoded /wiki 404s.

        Uses a response WITHOUT `_links.base` to exercise the env-var fallback.
        """
        server_env = {
            "CONFLUENCE_URL": "https://wiki.company.com",
            "CONFLUENCE_API_TOKEN": "pat-token",
            "CONFLUENCE_CLOUD": "false",
            "CONFLUENCE_SPACE_KEY": "BA",
        }
        mock_client = _make_mock_confluence(page_exists=False)
        mock_client.create_page.return_value = {
            "id": "777",
            "version": {"number": 1},
            "_links": {"webui": "/display/BA/Requirements"},
        }
        with patch.dict(os.environ, server_env, clear=True), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = confluence_mod.push_to_confluence(
                content_markdown="# X", page_title="Requirements", space_key="BA")
        self.assertIn("https://wiki.company.com/display/BA/Requirements", result)
        self.assertNotIn("/wiki/display", result)

    def test_page_url_prefers_links_base_over_env(self):
        """`_links.base` from the API wins — it carries the correct context path."""
        with patch.dict(os.environ, VALID_ENV):
            url = confluence_mod._page_url(
                {"_links": {"base": "https://other.example.com", "webui": "/display/X/Y"}}
            )
        self.assertEqual(url, "https://other.example.com/display/X/Y")

    # --- I1/I2: fidelity of the Confluence → requirements import path -------

    def test_paragraphs_do_not_merge_into_one_line(self):
        """Storage format writes each requirement in its own block element. If the
        closing tag does not end the line, the next ID gets glued to the previous
        text ('routingBR-002'), the \\b in the ID pattern stops matching, and the
        requirement is SILENTLY dropped from the import."""
        html = "<p>FR-001 — Automated routing</p><p>BR-002 — Cut handling time</p>"
        text = confluence_mod._confluence_storage_to_text(html)
        reqs = confluence_mod._extract_requirements_heuristic(text, "")
        ids = [r["id"] for r in reqs]
        self.assertIn("FR-001", ids)
        self.assertIn("BR-002", ids, "the second paragraph's requirement was lost on import")

    def test_html_entities_are_decoded(self):
        """Confluence storage format is XHTML — entities must not reach titles."""
        html = "<p>BR-002 &mdash; Cut cost &amp; time</p><p>NFR-003 &mdash; Response &lt; 2s</p>"
        text = confluence_mod._confluence_storage_to_text(html)
        self.assertNotIn("&mdash;", text)
        self.assertNotIn("&amp;", text)
        self.assertNotIn("&lt;", text)
        titles = {r["id"]: r["title"] for r in confluence_mod._extract_requirements_heuristic(text, "")}
        self.assertEqual(titles.get("BR-002"), "Cut cost & time")
        self.assertEqual(titles.get("NFR-003"), "Response < 2s")

    def test_title_has_no_leading_dash_or_trailing_pipe(self):
        """Separators from the source markup must not survive into the title."""
        html = "<table><tr><td>FR-007</td><td>Bulk export</td></tr></table>"
        text = confluence_mod._confluence_storage_to_text(html)
        reqs = confluence_mod._extract_requirements_heuristic(text, "")
        self.assertEqual(reqs[0]["title"], "Bulk export")

    def test_imported_types_are_valid_for_traceability_repo(self):
        """The pulled JSON is advertised as ready for init_traceability_repo (5.1),
        whose allowed types are business|stakeholder|solution|transition|test|component."""
        allowed = {"business", "stakeholder", "solution", "transition", "test", "component"}
        text = "BR-001 a\nSR-002 b\nFR-003 c\nNFR-004 d\nTR-005 e\nUC-006 f\nUS-007 g\nREQ-008 h"
        for r in confluence_mod._extract_requirements_heuristic(text, ""):
            self.assertIn(r["type"], allowed, f"{r['id']} has a type 5.1 would reject")
            self.assertIn(r["status"], {"draft", "confirmed", "approved", "deprecated"})

    # --- fallback converter must emit valid XHTML --------------------------

    def test_fallback_escapes_xml_special_characters(self):
        """Without markdown2 the fallback shipped raw '&' and '<' — Confluence storage
        format is strict XHTML, so an NFR like "response < 2s" made the body invalid
        and the API rejected the whole page with a 400."""
        import builtins
        real_import = builtins.__import__

        def no_markdown2(name, *args, **kwargs):
            if name == "markdown2":
                raise ImportError("markdown2 not installed")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", no_markdown2):
            html = confluence_mod._markdown_to_confluence_storage(
                "Response time < 2s & uptime > 99%")
        self.assertIn("&amp;", html)
        self.assertIn("&lt;", html)
        self.assertNotIn("< 2s", html)

    def test_fallback_converts_tables(self):
        """BABOK artifacts are table-heavy; raw pipes would ship an unreadable page."""
        import builtins
        real_import = builtins.__import__

        def no_markdown2(name, *args, **kwargs):
            if name == "markdown2":
                raise ImportError("markdown2 not installed")
            return real_import(name, *args, **kwargs)

        md = "| ID | Title |\n|----|-------|\n| FR-001 | Login |"
        with patch.object(builtins, "__import__", no_markdown2):
            html = confluence_mod._markdown_to_confluence_storage(md)
        self.assertIn("<table>", html)
        self.assertIn("<th>ID</th>", html)
        self.assertIn("<td>FR-001</td>", html)
        self.assertNotIn("|----", html)

    # --- C3: the pull artifact must land in the project's report folder -----

    def test_pull_saves_artifact_under_project_folder(self):
        """pull_from_confluence computed a project name but never used it: the
        artifact went to flat reports/ instead of reports/<project_id>/.

        (conftest replaces save_artifact with a mock, so we assert the call; the
        real on-disk layout is covered by the E2E script.)
        """
        mock_client = _make_mock_confluence(page_exists=True)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)), \
             patch("skills.integrations.confluence_mcp.save_artifact") as mock_save:
            confluence_mod.pull_from_confluence(
                page_title="Project requirements",
                space_key="BA",
                project_name="conf_import",
            )
        mock_save.assert_called_once()
        self.assertEqual(
            mock_save.call_args.kwargs.get("project_id"), "conf_import",
            "the pull artifact is not routed to the project's report folder",
        )

    def test_pull_falls_back_to_page_title_as_project(self):
        """Without project_name the page title becomes the project id."""
        mock_client = _make_mock_confluence(page_exists=True)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)), \
             patch("skills.integrations.confluence_mcp.save_artifact") as mock_save:
            result = confluence_mod.pull_from_confluence(
                page_title="CRM Upgrade", space_key="BA", project_name="")
        self.assertIn("**Project:** CRM Upgrade", result)
        self.assertEqual(mock_save.call_args.kwargs.get("project_id"), "CRM Upgrade")


class TestExportHookErrorSurfacing(BaseMCPTest):
    """C4 — a configured-but-failing Confluence sync must not fail silently in 5.2."""

    def test_error_from_confluence_is_surfaced_as_note(self):
        import skills.requirements_maintain_mcp as maintain_mod

        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp.export_artifact_to_confluence",
                   return_value={"status": "error", "message": "CONFLUENCE_SPACE_KEY is not set"}):
            result = maintain_mod._export_hook(
                "health_report", "# Report", {"project_name": "Test"}
            )
        self.assertNotEqual(result.get("status"), "synced")
        self.assertIn("CONFLUENCE_SPACE_KEY", result.get("note", ""),
                      "the sync failure reason was swallowed — the BA sees no explanation")

    def test_update_requirement_reports_sync_failure(self):
        """The reason must reach the artifact text the BA actually reads."""
        import skills.requirements_traceability_mcp as trace_mod
        import skills.requirements_maintain_mcp as maintain_mod

        trace_mod.init_traceability_repo(
            project_name="hooktest",
            formality_level="Standard",
            requirements_json='[{"id": "FR-001", "type": "solution", "title": "Login"}]',
        )
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp.export_artifact_to_confluence",
                   return_value={"status": "error", "message": "API rate limit"}):
            content = maintain_mod.update_requirement(
                project_name="hooktest",
                req_id="FR-001",
                change_reason="audit",
                new_status="confirmed",
            )
        self.assertIn("API rate limit", content)


class TestSearchIsServerSide(BaseMCPTest):
    """INT-H — search_title must query the whole space, not the fetched window."""

    def _client_with_cql(self):
        mock_client = _make_mock_confluence()
        mock_client.cql.side_effect = None  # override the fixture's space-search stub
        mock_client.cql.return_value = {
            "results": [
                {   # rest/api/search wraps the page under "content"
                    "content": {
                        "id": "888",
                        "title": "Requirements — deep in the space",
                        "version": {"number": 2},
                    },
                    "title": "Requirements — deep in the space",
                    "lastModified": "2026-05-05T12:00:00Z",
                },
            ]
        }
        return mock_client

    def test_search_uses_cql_scoped_to_space_and_title(self):
        mock_client = self._client_with_cql()
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = confluence_mod.list_space_pages(space_key="BA", search_title="Requirements")

        mock_client.cql.assert_called_once()
        query = mock_client.cql.call_args[0][0]
        self.assertIn('space = "BA"', query)
        self.assertIn('title ~ "Requirements"', query)
        self.assertIn("type = page", query)
        # a page beyond the first `limit` of the space is now found
        self.assertIn("Requirements — deep in the space", result)
        self.assertIn("searched the whole space", result)
        mock_client.get_all_pages_from_space.assert_not_called()

    def test_search_hit_unwrapped_shape_also_supported(self):
        """Some endpoints/versions return the content object directly."""
        mock_client = _make_mock_confluence()
        mock_client.cql.side_effect = None  # override the fixture's space-search stub
        mock_client.cql.return_value = {
            "results": [{"id": "888", "title": "Flat shape", "version": {"when": "2026-05-05T12:00:00Z"}}]
        }
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = confluence_mod.list_space_pages(space_key="BA", search_title="Flat")
        self.assertIn("Flat shape", result)
        self.assertIn("2026-05-05", result)

    def test_search_falls_back_when_cql_unavailable(self):
        """A deployment that restricts CQL degrades instead of erroring out."""
        mock_client = _make_mock_confluence()
        mock_client.cql.side_effect = Exception("CQL disabled")
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = confluence_mod.list_space_pages(space_key="BA", search_title="Requirements")
        self.assertIn("Requirements FR", result)
        self.assertNotIn("Architecture", result)
        self.assertIn("CQL unavailable", result)

    def test_no_search_still_lists_the_space(self):
        mock_client = _make_mock_confluence()
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = confluence_mod.list_space_pages(space_key="BA")
        mock_client.cql.assert_not_called()
        self.assertIn("Architecture", result)

    def test_empty_search_result_message_mentions_the_filter(self):
        mock_client = _make_mock_confluence()
        mock_client.cql.side_effect = None  # override the fixture's space-search stub
        mock_client.cql.return_value = {"results": []}
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = confluence_mod.list_space_pages(space_key="BA", search_title="Nothing")
        self.assertIn("ℹ️", result)
        self.assertIn("Nothing", result)


class TestExportPageTitles(BaseMCPTest):
    """INT-G — auto-published 5.2 page titles must not collide or proliferate."""

    def title(self, artifact_type, metadata):
        import skills.requirements_maintain_mcp as maintain_mod
        return maintain_mod._confluence_page_title(artifact_type, "CRM", metadata)

    def test_different_requirements_same_day_get_different_pages(self):
        """The collision that silently overwrote the earlier page in Confluence."""
        first = self.title("requirement_update", {"req_id": "FR-001"})
        second = self.title("requirement_update", {"req_id": "FR-002"})
        self.assertNotEqual(first, second)
        self.assertIn("FR-001", first)
        self.assertIn("FR-002", second)

    def test_living_reports_have_no_date_so_they_update_in_place(self):
        for artifact_type in ("health_report", "reuse_list"):
            title = self.title(artifact_type, {})
            self.assertNotIn(str(date.today()), title,
                             f"{artifact_type} is a living report — a dated title forks a new page daily")

    def test_living_report_title_is_stable_across_calls(self):
        self.assertEqual(self.title("health_report", {"health_pct": 80}),
                         self.title("health_report", {"health_pct": 95}))

    def test_deprecation_batch_lists_ids_and_caps_them(self):
        few = self.title("deprecation", {"req_ids": ["FR-001", "FR-002"]})
        self.assertIn("FR-001, FR-002", few)
        many = self.title("deprecation", {"req_ids": [f"FR-00{i}" for i in range(1, 6)]})
        self.assertIn("+2", many)

    def test_event_without_ids_still_dated(self):
        title = self.title("requirement_update", {})
        self.assertIn(str(date.today()), title)


class TestExportArtifactToConfluence(BaseMCPTest):
    """Tests for the export_artifact_to_confluence helper (_export_hook)."""

    def _call(self, **kwargs):
        defaults = {
            "content_markdown": "# Report\n\nFR-001 — Authentication",
            "page_title": "Artifact 5.2",
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
                   return_value=(None, "❌ No token")):
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


# ---------------------------------------------------------------------------
# A4 — page title derived from the artifact filename
# ---------------------------------------------------------------------------

class TestDerivePageTitle(unittest.TestCase):
    """The filename prefix IS the stable page identity — the producer put the
    discriminator there, so INT-G's living-vs-event semantics fall out mechanically."""

    def title(self, project_id, filename):
        return confluence_mod._derive_page_title(
            project_id, os.path.join("governance_plans", "reports", project_id, filename)
        )

    def test_event_artifact_keeps_its_discriminator(self):
        self.assertEqual(
            self.title("crm_upgrade", "5_5_approval_record_v1.0_20260720_151747.md"),
            "crm_upgrade — 5.5 Approval Record v1.0",
        )

    def test_living_report_has_no_date_so_it_updates_in_place(self):
        self.assertEqual(
            self.title("crm_upgrade", "7_2_verification_report_20260720_151747.md"),
            "crm_upgrade — 7.2 Verification Report",
        )

    def test_uppercase_discriminator_is_preserved_verbatim(self):
        self.assertEqual(
            self.title("crm_upgrade", "5_4_cr_decision_CR-003_20260720_151747.md"),
            "crm_upgrade — 5.4 CR Decision CR-003",
        )

    def test_known_acronym_is_upper_cased(self):
        self.assertEqual(
            self.title("crm_upgrade", "7_1_uc_diagram_20260720_151747.md"),
            "crm_upgrade — 7.1 UC Diagram",
        )

    def test_project_id_already_in_the_stem_is_not_duplicated(self):
        """6.1/6.2/5.3 embed the project in the prefix — prepending would double it.
        The suffix is stripped so every page of a project shares one title shape."""
        self.assertEqual(
            self.title("crm", "6_1_current_state_crm_20260720_151747.md"),
            "crm — 6.1 Current State",
        )

    def test_project_named_like_a_trailing_word_loses_it_ACCEPTED_TRADEOFF(self):
        """DELIBERATE, not an oversight — do not "fix" this without reading why.

        The strip cannot tell "the producer appended the project id" from "the prefix
        happens to end with that word", so a project literally named `state` has the
        word eaten out of `6_1_current_state`.

        Chosen anyway: without the strip, EVERY 6.1/6.2/5.3 artifact in EVERY project
        titles as "crm — 6.1 Current State crm" — guaranteed and constant, versus this,
        which needs the project id to equal the last word of a prefix. Both failure
        modes are purely cosmetic: neither collides pages, loses data nor overwrites
        anything, and both are STABLE, so no page proliferation either way.

        A "keep at least 2 tokens" heuristic was tried and rejected: it breaks the real
        case 5_3_prioritization_{pid}, which legitimately reduces to one token.
        """
        self.assertEqual(
            self.title("state", "6_1_current_state_20260720_151747.md"),
            "state — 6.1 Current",
        )

    def test_strip_timestamp_removes_only_the_suffix(self):
        self.assertEqual(
            confluence_mod._strip_timestamp("5_5_approval_record_v1.0_20260720_151747.md"),
            "5_5_approval_record_v1.0",
        )

    def test_name_without_a_timestamp_is_left_alone(self):
        self.assertEqual(
            confluence_mod._strip_timestamp("legacy_report.md"), "legacy_report"
        )


# ---------------------------------------------------------------------------
# A4 — resolving an artifact from the project's own directories
# ---------------------------------------------------------------------------

class TestResolveArtifact(BaseMCPTest):

    PID = "a4proj"

    def _write(self, relative_dir, filename, content="# Artifact\n"):
        path = os.path.join("governance_plans", relative_dir, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_prefix_resolves_to_the_single_match(self):
        self._write(f"reports/{self.PID}", "7_6_recommendation_20260720_101010.md")
        path, note = confluence_mod._resolve_artifact(self.PID, "7_6_recommendation")
        self.assertIsNotNone(path)
        self.assertIn("7_6_recommendation_20260720_101010.md", path)

    def test_prefix_with_several_matches_takes_the_newest_and_says_so(self):
        self._write(f"reports/{self.PID}", "7_6_recommendation_20260720_101010.md")
        self._write(f"reports/{self.PID}", "7_6_recommendation_20260721_090000.md")
        path, note = confluence_mod._resolve_artifact(self.PID, "7_6_recommendation")
        self.assertIn("20260721_090000", path)
        self.assertIn("2", note)  # candidate count is reported

    def test_prefix_matching_is_case_insensitive(self):
        self._write(f"reports/{self.PID}", "7_6_recommendation_20260720_101010.md")
        path, _ = confluence_mod._resolve_artifact(self.PID, "7_6_Recommendation")
        self.assertIsNotNone(path)

    def test_specs_directory_is_searched_too(self):
        """7.1 specs are a real deliverable and do NOT live under reports/."""
        self._write(f"data/{self.PID}/specs", "us_001_login_20260720_101010.md")
        path, _ = confluence_mod._resolve_artifact(self.PID, "us_001")
        self.assertIsNotNone(path)
        self.assertIn("specs", path)

    def test_explicit_in_project_path_is_used(self):
        p = self._write(f"reports/{self.PID}", "7_6_recommendation_20260720_101010.md")
        path, _ = confluence_mod._resolve_artifact(self.PID, p)
        self.assertIsNotNone(path)

    def test_path_outside_the_project_is_refused(self):
        """Refused AND the message names the allowed roots — an analyst who mistyped a
        path needs to know where the tool will look, not just that it said no."""
        self._write(f"reports/{self.PID}", "7_6_recommendation_20260720_101010.md")
        outside = self._write("reports/other_project", "secret.md", "# Not this project\n")
        path, message = confluence_mod._resolve_artifact(self.PID, outside)
        self.assertIsNone(path)
        self.assertIn("❌", message)
        self.assertIn(self.PID, message)
        self.assertIn("irreversible", message.lower())

    def test_legacy_flat_report_gets_an_accurate_refusal(self):
        """A pre-layout artifact in the flat reports/ folder really IS this project's
        file, so "outside project X" was a false statement. The flat directory stays
        out of the roots on purpose — it is not scoped to a project."""
        self._write(f"reports/{self.PID}", "7_6_recommendation_20260720_101010.md")
        legacy = self._write("reports", "Old_Report.md", "# Legacy\n")
        path, message = confluence_mod._resolve_artifact(self.PID, legacy)
        self.assertIsNone(path)
        self.assertIn("migrate_artifacts", message)

    def test_a_non_markdown_artifact_is_refused(self):
        """A .puml is diagram source: it renders as noise, and the extension leaks
        into the derived page title."""
        self._write(f"reports/{self.PID}", "7_6_recommendation_20260720_101010.md")
        puml = self._write(f"reports/{self.PID}", "uc_diagram.puml", "@startuml\n@enduml\n")
        path, message = confluence_mod._resolve_artifact(self.PID, puml)
        self.assertIsNone(path)
        self.assertIn("Markdown", message)

    def test_empty_selector_lists_what_is_available(self):
        self._write(f"reports/{self.PID}", "7_6_recommendation_20260720_101010.md")
        path, message = confluence_mod._resolve_artifact(self.PID, "")
        self.assertIsNone(path)
        self.assertIn("7_6_recommendation_20260720_101010.md", message)

    def test_no_match_lists_what_is_available_instead_of_a_bare_error(self):
        self._write(f"reports/{self.PID}", "7_6_recommendation_20260720_101010.md")
        path, message = confluence_mod._resolve_artifact(self.PID, "9_9_nonexistent")
        self.assertIsNone(path)
        self.assertIn("7_6_recommendation_20260720_101010.md", message)

    def test_search_scope_is_always_printed(self):
        """INT-H: 'nothing found' must never be ambiguous about where we looked."""
        self._write(f"reports/{self.PID}", "7_6_recommendation_20260720_101010.md")
        path, message = confluence_mod._resolve_artifact(self.PID, "anything")
        self.assertIsNone(path)
        self.assertIn("reports", message)


# ---------------------------------------------------------------------------
# A4 — publish_artifact_to_confluence
# ---------------------------------------------------------------------------

class TestPublishArtifactToConfluence(BaseMCPTest):

    PID = "a4proj"

    def _write_artifact(self, filename="7_6_recommendation_20260720_101010.md",
                        content="# Recommendation\n\nPick option B.\n"):
        path = os.path.join("governance_plans", "reports", self.PID, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def _publish(self, mock_client, **kwargs):
        defaults = {"project_id": self.PID, "artifact": "7_6_recommendation",
                    "space_key": "BA"}
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            return confluence_mod.publish_artifact_to_confluence(**{**defaults, **kwargs})

    def test_publishes_the_file_content_verbatim(self):
        """The point of the feature: the artifact never passes through the model.

        Asserted BYTE FOR BYTE, by spying on the converter's input. Checking that a
        substring survived HTML conversion would still pass if a generative step were
        reintroduced and rewrote everything around it — the test name would then be
        claiming more than the test checks.
        """
        body = "# Recommendation\n\nPick option B. Cost < $2 & risk low.\n"
        path = self._write_artifact(content=body)
        mock_client = _make_mock_confluence(page_exists=False)

        captured = {}
        real_converter = confluence_mod._markdown_to_confluence_storage

        def spy(md):
            captured["markdown"] = md
            return real_converter(md)

        with patch.object(confluence_mod, "_markdown_to_confluence_storage", spy):
            result = self._publish(mock_client)

        self.assertIn("✅", result)
        with open(path, encoding="utf-8") as f:
            on_disk = f.read()
        self.assertEqual(captured["markdown"], on_disk)

    def test_derived_title_is_used(self):
        self._write_artifact()
        mock_client = _make_mock_confluence(page_exists=False)
        self._publish(mock_client)
        self.assertEqual(
            mock_client.create_page.call_args.kwargs["title"],
            f"{self.PID} — 7.6 Recommendation",
        )

    def test_explicit_page_title_overrides_the_derived_one(self):
        self._write_artifact()
        mock_client = _make_mock_confluence(page_exists=False)
        self._publish(mock_client, page_title="My own title")
        self.assertEqual(
            mock_client.create_page.call_args.kwargs["title"], "My own title"
        )

    def test_reports_updated_for_an_existing_page(self):
        self._write_artifact()
        mock_client = _make_mock_confluence(page_exists=True)
        result = self._publish(mock_client)
        self.assertIn("updated", result)

    def test_reports_created_for_a_new_page(self):
        self._write_artifact()
        mock_client = _make_mock_confluence(page_exists=False)
        result = self._publish(mock_client)
        self.assertIn("created", result)

    def test_missing_artifact_returns_the_listing(self):
        self._write_artifact()
        mock_client = _make_mock_confluence(page_exists=False)
        result = self._publish(mock_client, artifact="9_9_nope")
        self.assertIn("7_6_recommendation_20260720_101010.md", result)
        mock_client.create_page.assert_not_called()

    def test_failure_reason_is_surfaced(self):
        """INT-D: a configured-but-failing sync must never be silent."""
        self._write_artifact()
        mock_client = _make_mock_confluence(page_exists=False)
        mock_client.create_page.side_effect = Exception("permission denied in space BA")
        result = self._publish(mock_client)
        self.assertIn("permission denied", result)


class TestExportHelperOperationKey(BaseMCPTest):

    def test_success_dict_reports_created_or_updated(self):
        mock_client = _make_mock_confluence(page_exists=True)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            result = confluence_mod.export_artifact_to_confluence(
                content_markdown="# X", page_title="T", space_key="BA"
            )
        self.assertEqual(result["status"], "synced")
        self.assertEqual(result["operation"], "updated")

    def test_extra_key_does_not_disturb_the_52_hook(self):
        """All hook consumers read named keys via .get(), so this is inert."""
        import skills.requirements_maintain_mcp as maintain_mod
        mock_client = _make_mock_confluence(page_exists=False)
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            hook = maintain_mod._export_hook(
                "health_report", "# Health", {"project_name": "a4proj"}
            )
        self.assertEqual(hook["status"], "synced")
        self.assertIn("url", hook)


class TestPublishFailureEdges(BaseMCPTest):
    """Every case here used to end in `✅` for something that had not happened, or in
    an exception escaping the tool as a protocol error."""

    PID = "a4proj"

    def _write(self, filename, content, encoding="utf-8"):
        path = os.path.join("governance_plans", "reports", self.PID, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding=encoding) as f:
            f.write(content)
        return path

    def _publish(self, mock_client, **kwargs):
        defaults = {"project_id": self.PID, "artifact": "7_6_recommendation",
                    "space_key": "BA"}
        with patch.dict(os.environ, VALID_ENV), \
             patch("skills.integrations.confluence_mcp._get_confluence_client",
                   return_value=(mock_client, None)):
            return confluence_mod.publish_artifact_to_confluence(**{**defaults, **kwargs})

    def test_non_utf8_artifact_returns_an_error_not_an_exception(self):
        """UnicodeDecodeError is a ValueError, not an OSError, so it escaped the read
        guard. Reachable: a file a person dropped in, or a cp1251 console default."""
        self._write("7_6_recommendation_20260720_101010.md",
                    "# Отчёт\n\nРекомендация.\n", encoding="cp1251")
        mock_client = _make_mock_confluence(page_exists=False)
        result = self._publish(mock_client)
        self.assertIn("❌", result)
        self.assertIn("UTF-8", result)
        mock_client.create_page.assert_not_called()

    def test_empty_artifact_is_refused(self):
        """Publishing it would blank an existing wiki page while reporting success,
        and publication is irreversible."""
        self._write("7_6_recommendation_20260720_101010.md", "   \n")
        mock_client = _make_mock_confluence(page_exists=True)
        result = self._publish(mock_client)
        self.assertIn("❌", result)
        mock_client.update_page.assert_not_called()

    def test_title_uses_the_normalized_project_id(self):
        """report_dir_for normalizes, so two casings resolve to ONE file — but the raw
        id in the title made them two Confluence pages for one artifact."""
        self._write("7_6_recommendation_20260720_101010.md", "# R\n\nBody.\n")
        titles = set()
        for pid in ("a4proj", "A4Proj"):
            mock_client = _make_mock_confluence(page_exists=False)
            self._publish(mock_client, project_id=pid)
            titles.add(mock_client.create_page.call_args.kwargs["title"])
        self.assertEqual(len(titles), 1, f"one artifact must map to one page: {titles}")

    def test_missing_parent_page_is_refused_not_ignored(self):
        """It used to create the page at the space root and answer ✅ — telling the BA
        the page was filed where they asked. push_to_confluence refuses the same input."""
        self._write("7_6_recommendation_20260720_101010.md", "# R\n\nBody.\n")
        mock_client = _make_mock_confluence(page_exists=False)
        mock_client.get_page_by_title.return_value = None
        result = self._publish(mock_client, parent_page_title="No Such Parent")
        self.assertIn("❌", result)
        mock_client.create_page.assert_not_called()

    def test_empty_api_response_is_not_reported_as_success(self):
        self._write("7_6_recommendation_20260720_101010.md", "# R\n\nBody.\n")
        mock_client = _make_mock_confluence(page_exists=False)
        mock_client.create_page.return_value = None
        result = self._publish(mock_client)
        self.assertIn("❌", result)

    def test_search_hit_shape_is_normalized(self):
        """`rest/api/search` wraps the page under `content`; indexing ["id"] bare
        surfaced as an unactionable "Publication failed: 'id'"."""
        self._write("7_6_recommendation_20260720_101010.md", "# R\n\nBody.\n")
        mock_client = _make_mock_confluence(page_exists=True)
        mock_client.get_page_by_title.return_value = {
            "content": {"id": "999", "title": "Test",
                        "_links": {"webui": "/pages/999"}},
            "lastModified": "2026-03-30T10:00:00Z",
        }
        result = self._publish(mock_client)
        self.assertNotIn("❌", result)
        self.assertEqual(mock_client.update_page.call_args.kwargs["page_id"], "999")
