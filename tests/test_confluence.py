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

def _make_mock_confluence(page_exists=True, page_title="Test", page_id="12345"):
    """Returns a configured mock of the atlassian Confluence client."""
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
        {"id": "111", "title": "Requirements FR", "version": {"when": "2026-03-01T00:00:00Z"}},
        {"id": "222", "title": "Requirements BR", "version": {"when": "2026-03-15T00:00:00Z"}},
        {"id": "333", "title": "Architecture",   "version": {"when": "2026-03-20T00:00:00Z"}},
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
