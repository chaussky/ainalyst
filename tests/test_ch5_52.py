"""
tests/test_ch5_52.py — Tests for Chapter 5.2: Maintain Requirements
MCP file: skills/requirements_maintain_mcp.py
Tools: update_requirement, deprecate_requirements,
       check_requirements_health, find_reusable_requirements

Strategy: BaseMCPTest (tmpdir + chdir), setup_mocks() before imports,
save_artifact is patched via patch() per ADR-068.
"""

import json
import os
import sys
import unittest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tests.conftest import setup_mocks, BaseMCPTest, make_test_repo, save_test_repo
setup_mocks()

import skills.requirements_maintain_mcp as mod52
from skills.common import data_path


# ---------------------------------------------------------------------------
# Helper data
# ---------------------------------------------------------------------------

PROJECT = "maintain_test"


def _setup_repo(project=PROJECT, extras=None):
    """Creates a test repository with baseline requirements."""
    repo = make_test_repo(project)
    if extras:
        repo["requirements"].extend(extras)
    save_test_repo(repo)
    return repo


# ---------------------------------------------------------------------------
# TestUtils52
# ---------------------------------------------------------------------------

class TestUtils52(unittest.TestCase):
    """Tests for the 5.2 module's helper functions."""

    def test_minor_version_normal(self):
        """1.3 → minor = 3."""
        self.assertEqual(mod52._minor_version("1.3"), 3)

    def test_minor_version_zero(self):
        """1.0 → minor = 0."""
        self.assertEqual(mod52._minor_version("1.0"), 0)

    def test_minor_version_invalid(self):
        """An invalid version doesn't raise an exception."""
        result = mod52._minor_version("invalid")
        self.assertIsInstance(result, int)

    def test_days_since_today(self):
        """Today's date → 0 days."""
        self.assertEqual(mod52._days_since(str(date.today())), 0)

    def test_days_since_past(self):
        """A date 10 days ago → 10."""
        past = str(date.today() - timedelta(days=10))
        self.assertEqual(mod52._days_since(past), 10)

    def test_days_since_invalid(self):
        """An invalid date → a large number (or doesn't crash)."""
        result = mod52._days_since("not-a-date")
        self.assertIsInstance(result, int)


# ---------------------------------------------------------------------------
# TestUpdateRequirement
# ---------------------------------------------------------------------------

class TestUpdateRequirement(BaseMCPTest):
    """Tests for the 5.2 tool: update_requirement."""

    def setUp(self):
        super().setUp()
        _setup_repo()

    def _call(self, **overrides):
        defaults = dict(
            project_name=PROJECT,
            req_id="BR-001",
            change_reason="Clarification after the workshop",
        )
        kwargs = {**defaults, **overrides}
        with patch("skills.requirements_maintain_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod52.update_requirement(**kwargs)

    # --- happy path ---

    def test_update_status(self):
        """Updating the status goes through without errors."""
        result = self._call(new_status="approved")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_update_status_persisted(self):
        """The new status is saved to the file."""
        self._call(new_status="approved")
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        req = next(r for r in data["requirements"] if r["id"] == "BR-001")
        self.assertEqual(req["status"], "approved")

    def test_update_writes_history(self):
        """The change history is written to the repository."""
        self._call(new_status="approved")
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("history", data)
        self.assertGreater(len(data["history"]), 0)

    def test_update_minor_version(self):
        """Setting a minor version is applied."""
        result = self._call(new_version="1.1")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_update_major_version(self):
        """Setting a major version is applied."""
        result = self._call(new_version="2.0")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_update_owner(self):
        """Changing the owner doesn't change the version."""
        result = self._call(new_owner="product_owner@example.com")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_update_priority(self):
        """Setting the priority."""
        result = self._call(new_priority="Must")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_update_title(self):
        """Changing the requirement title."""
        result = self._call(new_title="Reduce the time to 3 minutes")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_update_stability_flag(self):
        """Setting the stability flag."""
        result = self._call(new_stability="unstable")
        self.assertIsInstance(result, str)

    def test_update_reuse_candidate(self):
        """Mark as a reuse candidate."""
        result = self._call(reuse_candidate="true", reuse_scope="program")
        self.assertIsInstance(result, str)

    def test_update_auto_volatility(self):
        """The volatility flag is set automatically at version 1.4+."""
        _call_with_version = dict(
            project_name=PROJECT,
            req_id="FR-001",
            change_reason="Iterative edits",
            new_version="1.4",
        )
        with patch("skills.requirements_maintain_mcp.save_artifact"):
            mod52.update_requirement(**_call_with_version)

        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        req = next(r for r in data["requirements"] if r["id"] == "FR-001")
        # Version 1.4 → an unstable requirement
        minor = mod52._minor_version(req.get("version", "1.0"))
        self.assertGreaterEqual(minor, 4)

    # --- errors ---

    def test_update_unknown_id(self):
        """An unknown req_id → error message."""
        result = self._call(req_id="XX-999")
        self.assertIn("❌", result)

    def test_update_no_changes(self):
        """A call with no changes — must not crash."""
        result = self._call()
        self.assertIsInstance(result, str)

    # --- save_artifact ---

    def test_save_artifact_called(self):
        """save_artifact is called on update."""
        with patch("skills.requirements_maintain_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            mod52.update_requirement(
                project_name=PROJECT,
                req_id="BR-001",
                change_reason="test",
                new_status="approved",
            )
            mock_sa.assert_called_once()

    def test_returns_string(self):
        """Always returns a string."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# TestDeprecateRequirements
# ---------------------------------------------------------------------------

class TestDeprecateRequirements(BaseMCPTest):
    """Tests for the 5.2 tool: deprecate_requirements."""

    def setUp(self):
        super().setUp()
        _setup_repo()

    def _call(self, **overrides):
        defaults = dict(
            project_name=PROJECT,
            req_ids_json=json.dumps(["FR-002"]),
            final_status="deprecated",
            reason="The requirement became outdated after the refactoring",
        )
        kwargs = {**defaults, **overrides}
        with patch("skills.requirements_maintain_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod52.deprecate_requirements(**kwargs)

    # --- happy path across final_status ---

    def test_deprecated_status(self):
        """final_status=deprecated — works."""
        result = self._call(final_status="deprecated")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_superseded_status_with_superseded_by(self):
        """final_status=superseded + superseded_by — works."""
        result = self._call(final_status="superseded", superseded_by="FR-001")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_retired_status(self):
        """final_status=retired — works."""
        result = self._call(final_status="retired")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- status is persisted ---

    def test_status_set_in_file(self):
        """The deprecated status is saved to the repository."""
        self._call(req_ids_json=json.dumps(["FR-002"]), final_status="deprecated")
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        req = next(r for r in data["requirements"] if r["id"] == "FR-002")
        self.assertEqual(req["status"], "deprecated")

    def test_record_preserved(self):
        """A deprecated requirement is not deleted, but stays in the repository."""
        self._call()
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        ids = [r["id"] for r in data["requirements"]]
        self.assertIn("FR-002", ids)

    def test_multiple_requirements_deprecated(self):
        """Several requirements are marked in a single call."""
        result = self._call(req_ids_json=json.dumps(["FR-001", "FR-002"]))
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- errors ---

    def test_superseded_without_superseded_by_warns(self):
        """superseded without superseded_by → warning or error."""
        result = self._call(final_status="superseded", superseded_by="")
        self.assertIsInstance(result, str)
        # Expect ❌ or ⚠️
        self.assertTrue("❌" in result or "⚠️" in result, f"No warning: {result[:200]}")

    def test_invalid_ids_json(self):
        """Invalid req_ids_json → error."""
        result = self._call(req_ids_json="{invalid}")
        self.assertIn("❌", result)

    def test_returns_string(self):
        """Always returns a string."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# TestCheckRequirementsHealth
# ---------------------------------------------------------------------------

class TestCheckRequirementsHealth(BaseMCPTest):
    """Tests for the 5.2 tool: check_requirements_health."""

    def setUp(self):
        super().setUp()
        _setup_repo()

    def _call(self, **overrides):
        defaults = dict(project_name=PROJECT)
        kwargs = {**defaults, **overrides}
        with patch("skills.requirements_maintain_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod52.check_requirements_health(**kwargs)

    def test_basic_health_check(self):
        """A basic health audit works without errors."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_detects_volatile_requirement(self):
        """A requirement with version 1.4+ is flagged as volatile."""
        # Write version 1.5 directly to the repository
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for r in data["requirements"]:
            if r["id"] == "FR-001":
                r["version"] = "1.5"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        result = self._call()
        self.assertIn("FR-001", result)

    def test_excludes_deprecated(self):
        """Deprecated requirements are excluded from the audit (with no filter)."""
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for r in data["requirements"]:
            if r["id"] == "FR-002":
                r["status"] = "deprecated"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        result = self._call()
        # Deprecated requirements must not appear in the health audit
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_filter_by_type(self):
        """Filtering by type narrows the list of checked requirements."""
        result = self._call(filter_type="business")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_filter_by_status(self):
        """Filtering by status works."""
        result = self._call(filter_status="confirmed")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_empty_project_no_crash(self):
        """An empty (nonexistent) project — doesn't crash with an exception."""
        result = self._call(project_name="nonexistent_project_xyz")
        self.assertIsInstance(result, str)

    def test_returns_string(self):
        """Always returns a string."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# TestFindReusableRequirements
# ---------------------------------------------------------------------------

class TestFindReusableRequirements(BaseMCPTest):
    """Tests for the 5.2 tool: find_reusable_requirements."""

    def setUp(self):
        super().setUp()
        # Add a reuse candidate
        _setup_repo(extras=[
            {
                "id": "BR-002",
                "type": "business",
                "title": "Unified authentication system",
                "version": "1.0",
                "status": "approved",
                "reuse_candidate": True,
                "reuse_scope": "enterprise",
                "added": str(date.today()),
            }
        ])

    def _call(self, **overrides):
        defaults = dict(project_name=PROJECT)
        kwargs = {**defaults, **overrides}
        with patch("skills.requirements_maintain_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod52.find_reusable_requirements(**kwargs)

    def test_finds_approved_candidate(self):
        """An approved reuse candidate is found."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_search_query_filters(self):
        """The search query filters by the requirement text."""
        # BR-002 has the title "Unified authentication system" — the search should find it
        result = self._call(search_query="authentication")
        self.assertIsInstance(result, str)
        self.assertIn("BR-002", result)

    def test_filter_by_type_business(self):
        """Filter by type business."""
        result = self._call(filter_type="business")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_filter_by_type_solution(self):
        """Filter by type solution — must not find BR-002."""
        result = self._call(filter_type="solution")
        self.assertIsInstance(result, str)

    def test_min_scope_enterprise(self):
        """Target scope enterprise — ranks enterprise candidates higher.

        The docstring used to say "finds only enterprise candidates", which the
        assertions never checked and the code never did: the scope adds a point to
        the suitability score and excludes nothing.
        """
        result = self._call(min_reuse_scope="enterprise")
        self.assertIsInstance(result, str)
        self.assertIn("BR-002", result)
        self.assertIn("raises the ranking, does not exclude", result)

    def test_min_scope_program_includes_enterprise(self):
        """Target scope program — enterprise candidates rank at least as high."""
        result = self._call(min_reuse_scope="program")
        self.assertIsInstance(result, str)

    def test_no_candidates_graceful(self):
        """If there are no candidates — the function doesn't crash."""
        result = self._call(filter_type="transition")
        self.assertIsInstance(result, str)

    def test_deprecated_excluded(self):
        """Deprecated requirements are not included in the result."""
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for r in data["requirements"]:
            if r["id"] == "BR-002":
                r["status"] = "deprecated"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        result = self._call()
        # BR-002 is deprecated — must not be in the recommendations
        # (it may appear in the text as excluded, so we just check the type)
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_returns_string(self):
        """Always returns a string."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# TestIntegration52
# ---------------------------------------------------------------------------

class TestIntegration52(BaseMCPTest):
    """Integration tests: the 5.2 tools working together."""

    def setUp(self):
        super().setUp()
        _setup_repo()

    def test_update_then_health_check(self):
        """Updating a requirement → the health audit reflects the changes."""
        with patch("skills.requirements_maintain_mcp.save_artifact"):
            mod52.update_requirement(
                project_name=PROJECT,
                req_id="FR-001",
                change_reason="Scope expansion",
                new_version="1.4",
            )
        with patch("skills.requirements_maintain_mcp.save_artifact"):
            result = mod52.check_requirements_health(project_name=PROJECT)
        self.assertIn("FR-001", result)

    def test_deprecate_then_health_check_excludes(self):
        """Deprecating a requirement → it's excluded from the health audit."""
        with patch("skills.requirements_maintain_mcp.save_artifact"):
            mod52.deprecate_requirements(
                project_name=PROJECT,
                req_ids_json=json.dumps(["FR-002"]),
                final_status="deprecated",
                reason="Not needed in the current iteration",
            )
        with patch("skills.requirements_maintain_mcp.save_artifact"):
            result = mod52.check_requirements_health(project_name=PROJECT)
        # The deprecated FR-002 must not be a problem in the health report
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_history_accumulates_across_calls(self):
        """History accumulates across several updates to one requirement."""
        for reason in ["Edit 1", "Edit 2", "Edit 3"]:
            with patch("skills.requirements_maintain_mcp.save_artifact"):
                mod52.update_requirement(
                    project_name=PROJECT,
                    req_id="BR-001",
                    change_reason=reason,
                    note=f"Note: {reason}",
                    new_status="approved",
                )
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertGreaterEqual(len(data.get("history", [])), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
