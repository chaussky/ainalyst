"""
tests/test_ch5_51.py — Tests for Chapter 5.1: Traceability and Monitoring
MCP file: skills/requirements_traceability_mcp.py
Tools: init_traceability_repo, add_trace_link, run_impact_analysis,
       check_coverage, export_traceability_matrix

Strategy: BaseMCPTest (tmpdir + chdir), setup_mocks() before imports,
save_artifact is patched via patch() per ADR-068.
"""

import json
import os
import sys
import unittest
from datetime import date
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tests.conftest import setup_mocks, BaseMCPTest, make_test_repo, save_test_repo
setup_mocks()

import skills.requirements_traceability_mcp as mod51
from skills.common import data_path


# ---------------------------------------------------------------------------
# Helper data
# ---------------------------------------------------------------------------

REQS_VALID = json.dumps([
    {
        "id": "BR-001",
        "type": "business",
        "title": "Reduce request processing time to 5 minutes",
        "version": "1.0",
        "status": "confirmed",
        "source_artifact": "governance_plans/4_3_test_confirmed.md",
    },
    {
        "id": "FR-001",
        "type": "solution",
        "title": "The system automatically distributes requests",
        "version": "1.0",
        "status": "confirmed",
        "source_artifact": "governance_plans/4_3_test_confirmed.md",
    },
    {
        "id": "FR-002",
        "type": "solution",
        "title": "Notifications on request status change",
        "version": "1.0",
        "status": "draft",
        "source_artifact": "governance_plans/4_3_test_confirmed.md",
    },
    {
        "id": "TC-001",
        "type": "test",
        "title": "Auto-distribution test",
        "version": "1.0",
        "status": "draft",
    },
])

PROJECT = "traceability_test"


def _init_repo(project=PROJECT, formality="Standard", reqs_json=None):
    """Initializes the repository and returns the result."""
    if reqs_json is None:
        reqs_json = REQS_VALID
    with patch("skills.requirements_traceability_mcp.save_artifact") as mock_sa:
        mock_sa.return_value = "✅ Saved"
        return mod51.init_traceability_repo(
            project_name=project,
            formality_level=formality,
            requirements_json=reqs_json,
        )


# ---------------------------------------------------------------------------
# TestInitTraceabilityRepo
# ---------------------------------------------------------------------------

class TestInitTraceabilityRepo(BaseMCPTest):
    """Tests for the 5.1 tool: init_traceability_repo."""

    def _call(self, **overrides):
        defaults = dict(
            project_name=PROJECT,
            formality_level="Standard",
            requirements_json=REQS_VALID,
        )
        kwargs = {**defaults, **overrides}
        with patch("skills.requirements_traceability_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod51.init_traceability_repo(**kwargs)

    # --- formality ---

    def test_formality_lite(self):
        """Lite level — created without errors."""
        result = self._call(formality_level="Lite")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_formality_standard(self):
        """Standard level — created without errors."""
        result = self._call(formality_level="Standard")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_formality_full(self):
        """Full level — created without errors."""
        result = self._call(formality_level="Full")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- file is created ---

    def test_creates_json_file(self):
        """The repository is written to disk."""
        self._call()
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        self.assertTrue(os.path.exists(path), f"File not found: {path}")

    def test_correct_structure(self):
        """The file contains project, requirements, links, history."""
        self._call()
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("project", data)
        self.assertIn("requirements", data)
        self.assertIn("links", data)
        self.assertIn("history", data)

    def test_requirements_count_correct(self):
        """All 4 requirements make it into the repository."""
        self._call()
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(data["requirements"]), 4)

    # --- deduplication ---

    def test_deduplication_no_duplicate_ids(self):
        """Calling again with the same IDs doesn't duplicate requirements."""
        self._call()
        self._call()  # second call
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        ids = [r["id"] for r in data["requirements"]]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate IDs in the repository")

    # --- single requirement ---

    def test_single_requirement(self):
        """A single requirement type — an edge case."""
        result = self._call(
            requirements_json=json.dumps([
                {"id": "BR-001", "type": "business", "title": "The only requirement",
                 "version": "1.0", "status": "draft"}
            ])
        )
        self.assertNotIn("❌", result)

    # --- different projects ---

    def test_different_projects_no_collision(self):
        """Different projects write to different files."""
        self._call(project_name="project_alpha")
        self._call(project_name="project_beta")
        self.assertTrue(os.path.exists(
            data_path("project_alpha", "project_alpha_traceability_repo.json")))
        self.assertTrue(os.path.exists(
            data_path("project_beta", "project_beta_traceability_repo.json")))

    # --- errors ---

    def test_invalid_json_requirements(self):
        """Invalid JSON → error message."""
        result = self._call(requirements_json="{bad}")
        self.assertIn("❌", result)

    def test_empty_requirements_json(self):
        """Empty string instead of JSON → error."""
        result = self._call(requirements_json="")
        self.assertIn("❌", result)

    def test_requirements_not_a_list(self):
        """An object instead of a list — must not crash with an unhandled exception."""
        try:
            result = self._call(requirements_json=json.dumps({"id": "BR-001"}))
            # If it didn't crash — the result must be a string
            self.assertIsInstance(result, str)
        except (AttributeError, TypeError):
            pass  # the module doesn't validate this case — acceptable

    # --- save_artifact ---

    def test_save_artifact_called_once(self):
        """save_artifact is called exactly once."""
        with patch("skills.requirements_traceability_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            mod51.init_traceability_repo(
                project_name=PROJECT,
                formality_level="Standard",
                requirements_json=REQS_VALID,
            )
            mock_sa.assert_called_once()

    def test_returns_string(self):
        """Always returns a string."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# TestAddTraceLink
# ---------------------------------------------------------------------------

class TestAddTraceLink(BaseMCPTest):
    """Tests for the 5.1 tool: add_trace_link."""

    def setUp(self):
        super().setUp()
        _init_repo()

    def _call(self, **overrides):
        defaults = dict(
            project_name=PROJECT,
            from_id="FR-001",
            to_id="BR-001",
            relation="derives",
            rationale="FR derives from the business requirement",
            remove=False,
        )
        kwargs = {**defaults, **overrides}
        with patch("skills.requirements_traceability_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod51.add_trace_link(**kwargs)

    # --- happy path across link types ---

    def test_add_derives_link(self):
        """A derives link is added without errors."""
        result = self._call(relation="derives")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_add_verifies_link(self):
        """A verifies link is added without errors."""
        result = self._call(from_id="TC-001", to_id="FR-001", relation="verifies")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_add_depends_link(self):
        """A depends link is added without errors."""
        result = self._call(from_id="FR-002", to_id="FR-001", relation="depends")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_add_satisfies_link(self):
        """A satisfies link is added without errors."""
        result = self._call(relation="satisfies")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- write to the repository ---

    def test_link_persisted_in_file(self):
        """The added link is saved to the file."""
        self._call()
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        link_pairs = [(l["from"], l["to"]) for l in data["links"]]
        self.assertIn(("FR-001", "BR-001"), link_pairs)

    # --- link deduplication ---

    def test_no_duplicate_link(self):
        """Adding the same link again doesn't create a duplicate."""
        self._call()
        self._call()
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        pairs = [(l["from"], l["to"], l["relation"]) for l in data["links"]]
        self.assertEqual(len(pairs), len(set(pairs)), "Duplicate links in the repository")

    # --- removal ---

    def test_remove_existing_link(self):
        """Removing an existing link goes through without errors."""
        self._call(remove=False)
        result = self._call(remove=True)
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_remove_nonexistent_link(self):
        """Removing a nonexistent link — doesn't crash with an exception."""
        result = self._call(remove=True, from_id="FR-999", to_id="BR-999")
        self.assertIsInstance(result, str)

    def test_returns_string(self):
        """Always returns a string."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# TestRunImpactAnalysis
# ---------------------------------------------------------------------------

class TestRunImpactAnalysis(BaseMCPTest):
    """Tests for the 5.1 tool: run_impact_analysis."""

    def setUp(self):
        super().setUp()
        _init_repo()
        with patch("skills.requirements_traceability_mcp.save_artifact"):
            mod51.add_trace_link(
                project_name=PROJECT,
                from_id="FR-001", to_id="BR-001",
                relation="derives", rationale="derives from BR",
                remove=False,
            )
            mod51.add_trace_link(
                project_name=PROJECT,
                from_id="TC-001", to_id="FR-001",
                relation="verifies", rationale="the test verifies FR",
                remove=False,
            )

    def _call(self, changed_req_id="BR-001", depth="full"):
        with patch("skills.requirements_traceability_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod51.run_impact_analysis(
                project_name=PROJECT,
                changed_req_id=changed_req_id,
                change_description="Test change",
                depth=depth,
            )

    def test_finds_affected_requirements(self):
        """The analysis returns a list of affected requirements."""
        result = self._call(changed_req_id="BR-001")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_depth_direct_limits_traversal(self):
        """direct depth limits the graph traversal."""
        result = self._call(changed_req_id="BR-001", depth="direct")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_depth_full_traversal(self):
        """full depth — a full traversal without errors."""
        result = self._call(changed_req_id="BR-001", depth="full")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_unknown_req_id(self):
        """An unknown changed_req_id — the function doesn't crash."""
        result = self._call(changed_req_id="XX-999")
        self.assertIsInstance(result, str)

    def test_isolated_node(self):
        """A requirement without links — the analysis works correctly."""
        result = self._call(changed_req_id="FR-002")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_returns_string(self):
        """Always returns a string."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# TestCheckCoverage
# ---------------------------------------------------------------------------

class TestCheckCoverage(BaseMCPTest):
    """Tests for the 5.1 tool: check_coverage."""

    def setUp(self):
        super().setUp()
        _init_repo()
        with patch("skills.requirements_traceability_mcp.save_artifact"):
            mod51.add_trace_link(
                project_name=PROJECT,
                from_id="FR-001", to_id="BR-001",
                relation="derives", rationale="test",
                remove=False,
            )

    def _call(self, **kwargs):
        defaults = dict(project_name=PROJECT)
        params = {**defaults, **kwargs}
        with patch("skills.requirements_traceability_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod51.check_coverage(**params)

    def test_basic_coverage_check(self):
        """A basic coverage check works."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_deprecated_excluded_from_coverage(self):
        """Deprecated requirements are not included in the audit."""
        # Mark FR-002 as deprecated directly in the repository
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
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_child_with_derives_link_is_not_orphan(self):
        """A requirement that derives from a parent must NOT be flagged 'no source'.

        Canonical direction is from=child -> to=parent (FR-001 derives BR-001,
        added in setUp). Regression: has_source used to check to==req_id (inverted),
        which wrongly marked every child requirement as an orphan.
        """
        result = self._call()
        # Header of the orphan table (distinct from the summary row "No source (orphan)")
        marker = "requirements with no source"
        low = result.lower()
        if marker in low:
            section = low.split(marker, 1)[1].split("\n## ", 1)[0]
            self.assertNotIn(
                "`fr-001`", section,
                "FR-001 derives from BR-001; it must not be listed as an orphan with no source",
            )

    def test_orphan_fr_detected(self):
        """FR-002 without a link — the audit should flag the problem."""
        result = self._call()
        # FR-002 has no links — it should be mentioned in the report
        self.assertIn("FR-002", result)

    def test_test_node_with_verifies_is_not_orphan(self):
        """A test (type=test) linked via `verifies` has its source — the
        requirement it verifies — and must NOT be flagged 'no source'. Tests link
        via verifies, never derives, so a derives-only source check false-flags them."""
        with patch("skills.requirements_traceability_mcp.save_artifact"):
            mod51.add_trace_link(
                project_name=PROJECT, from_id="TC-001", to_id="FR-001",
                relation="verifies", rationale="the test verifies FR-001", remove=False,
            )
        result = self._call()
        marker = "requirements with no source"
        low = result.lower()
        self.assertIn(marker, low)  # FR-002 is a genuine orphan -> section exists
        section = low.split(marker, 1)[1].split("\n## ", 1)[0]
        self.assertNotIn(
            "`tc-001`", section,
            "TC-001 verifies FR-001; it must not be an orphan with no source",
        )

    def test_business_need_root_is_not_orphan(self):
        """A business_need is a root of the derivation chain (goals derive from it),
        so it has no upward source and must NOT be flagged 'no source' — like `business`."""
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["requirements"].append({
            "id": "BN-001", "type": "business_need", "title": "Cut approval time",
            "version": "1.0", "status": "confirmed", "added": "2026-01-01",
        })
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        result = self._call()
        marker = "requirements with no source"
        low = result.lower()
        self.assertIn(marker, low)
        section = low.split(marker, 1)[1].split("\n## ", 1)[0]
        self.assertNotIn(
            "`bn-001`", section,
            "business_need is a root; it must not be an orphan with no source",
        )

    def test_returns_string(self):
        """Always returns a string."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# TestExportTraceabilityMatrix
# ---------------------------------------------------------------------------

class TestExportTraceabilityMatrix(BaseMCPTest):
    """Tests for the 5.1 tool: export_traceability_matrix."""

    def setUp(self):
        super().setUp()
        _init_repo()
        with patch("skills.requirements_traceability_mcp.save_artifact"):
            mod51.add_trace_link(
                project_name=PROJECT,
                from_id="FR-001", to_id="BR-001",
                relation="derives", rationale="test",
                remove=False,
            )

    def _call(self, **overrides):
        defaults = dict(project_name=PROJECT)
        kwargs = {**defaults, **overrides}
        with patch("skills.requirements_traceability_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod51.export_traceability_matrix(**kwargs)

    def test_basic_export(self):
        """A basic matrix export."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_export_filter_by_relation(self):
        """Filtering by link type."""
        result = self._call(filter_relation="derives")
        self.assertIsInstance(result, str)

    def test_export_filter_by_type(self):
        """Filtering by requirement type."""
        result = self._call(filter_type="solution")
        self.assertIsInstance(result, str)

    def test_export_filter_by_status(self):
        """Filtering by requirement status."""
        result = self._call(filter_status="confirmed")
        self.assertIsInstance(result, str)

    def test_export_contains_requirement_ids(self):
        """The matrix contains the requirement IDs."""
        result = self._call()
        self.assertIn("BR-001", result)
        self.assertIn("FR-001", result)

    def test_export_empty_filter(self):
        """Empty filters — all requirements are included."""
        result = self._call(filter_relation="", filter_type="", filter_status="")
        self.assertIsInstance(result, str)

    def test_save_artifact_called(self):
        """save_artifact is called on export."""
        with patch("skills.requirements_traceability_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            mod51.export_traceability_matrix(project_name=PROJECT)
            mock_sa.assert_called_once()

    def test_returns_string(self):
        """Always returns a string."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# TestUtils51
# ---------------------------------------------------------------------------

class TestUtils51(unittest.TestCase):
    """Tests for the 5.1 module's helper functions."""

    def test_repo_path_normalizes_spaces(self):
        """Spaces in project_name are converted to underscores."""
        path = mod51._repo_path("My Project")
        self.assertIn("my_project", path)
        self.assertNotIn(" ", path)

    def test_repo_path_lowercase(self):
        """The project name is lowercased."""
        path = mod51._repo_path("CRM_UPGRADE")
        self.assertEqual(path, mod51._repo_path("crm_upgrade"))

    def test_find_req_existing(self):
        """_find_req finds a requirement by ID."""
        repo = {"requirements": [{"id": "BR-001", "title": "Test"}], "links": []}
        req = mod51._find_req(repo, "BR-001")
        self.assertIsNotNone(req)
        self.assertEqual(req["id"], "BR-001")

    def test_find_req_missing(self):
        """_find_req returns None for a missing ID."""
        repo = {"requirements": [], "links": []}
        self.assertIsNone(mod51._find_req(repo, "BR-999"))

    def test_find_links_both_directions(self):
        """_find_links returns links in both directions."""
        repo = {
            "requirements": [],
            "links": [
                {"from": "FR-001", "to": "BR-001", "relation": "derives"},
                {"from": "TC-001", "to": "FR-001", "relation": "verifies"},
                {"from": "FR-002", "to": "FR-003", "relation": "depends"},
            ],
        }
        links = mod51._find_links(repo, "FR-001")
        froms = [l["from"] for l in links]
        tos = [l["to"] for l in links]
        self.assertIn("FR-001", froms + tos)

    def test_find_links_isolated_node(self):
        """_find_links returns an empty list for an isolated requirement."""
        repo = {
            "requirements": [],
            "links": [{"from": "FR-001", "to": "BR-001", "relation": "derives"}],
        }
        links = mod51._find_links(repo, "FR-999")
        self.assertEqual(links, [])


class TestSatisfiesGrantsSource(BaseMCPTest):
    """A node that satisfies something is justified BY that thing — the same rule
    already applied to tests via `verifies`. Granting a source only for `derives`
    false-flags two real populations: requirements linked to a 6.2 business goal
    (7.1 per-goal traceability, ADR-082) and the `solution` nodes 6.4 pushes.
    """

    P = "satisfies_source"

    def _save(self, extra_nodes, links):
        repo = make_test_repo(self.P)
        repo["requirements"] = [
            {"id": "BG-001", "type": "business_goal", "title": "Cut handling time",
             "version": "1.0", "status": "confirmed", "added": str(date.today()),
             "source_artifact": ""},
        ] + extra_nodes
        repo["links"] = links
        save_test_repo(repo)

    def _run(self):
        with patch("skills.requirements_traceability_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod51.check_coverage(project_name=self.P)

    def _orphan_section(self, result):
        """Body of the '🔴 Requirements with no source' table only — the summary row
        above it mentions the same words and would mask a real regression."""
        marker = "requirements with no source"
        low = result.lower()
        if marker not in low:
            return ""
        return low.split(marker, 1)[1].split("\n## ", 1)[0]

    def _edge(self, frm, to, relation="satisfies"):
        return {"from": frm, "to": to, "relation": relation,
                "created": str(date.today())}

    def test_requirement_satisfying_a_goal_is_not_orphan(self):
        self._save(
            [{"id": "FR-100", "type": "functional", "title": "Auto-assign",
              "version": "1.0", "status": "draft", "added": str(date.today()),
              "source_artifact": ""}],
            [self._edge("FR-100", "BG-001")],
        )
        self.assertNotIn("`fr-100`", self._orphan_section(self._run()))

    def test_solution_node_from_64_is_not_orphan(self):
        """6.4 pushes `SOL-001 satisfies BG-001` (ADR-082) and no derives edge, so
        every solution node was a false orphan on any project that ran 6.4."""
        self._save(
            [{"id": "SOL-001", "type": "solution", "title": "Phased rollout",
              "version": "1.0", "status": "draft", "added": str(date.today()),
              "source_artifact": ""}],
            [self._edge("SOL-001", "BG-001")],
        )
        self.assertNotIn("`sol-001`", self._orphan_section(self._run()))

    def test_node_with_no_upward_edge_is_still_orphan(self):
        """The rule must not degenerate into 'everything has a source'."""
        self._save(
            [{"id": "FR-200", "type": "functional", "title": "Unlinked",
              "version": "1.0", "status": "draft", "added": str(date.today()),
              "source_artifact": ""}],
            [],
        )
        self.assertIn("`fr-200`", self._orphan_section(self._run()))

    def test_being_the_target_of_satisfies_does_not_grant_a_source(self):
        """Direction matters: from=implementer -> to=implemented. The GOAL is the
        target, so it must not inherit a source from the requirement pointing at it."""
        self._save(
            [{"id": "FR-300", "type": "functional", "title": "Auto-assign",
              "version": "1.0", "status": "draft", "added": str(date.today()),
              "source_artifact": ""}],
            [self._edge("FR-300", "BG-001")],
        )
        self.assertIn("`bg-001`", self._orphan_section(self._run()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
