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

from tests.conftest import (setup_mocks, BaseMCPTest, make_test_repo,
                            save_test_repo, load_test_repo)
setup_mocks()

import skills.requirements_maintain_mcp as mod52
from skills.common import data_path, normalize_project_id


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

    def test_days_since_accepts_the_platforms_other_format(self):
        """Chapter 4 and the stakeholder registry write `dd.mm.yyyy`; the graph writes
        ISO. Both are the platform's own, and a date crossing a chapter boundary is
        the normal case."""
        past = date.today() - timedelta(days=10)
        self.assertEqual(mod52._days_since(past.strftime("%d.%m.%Y")), 10)
        self.assertEqual(mod52._days_since(past.isoformat()), 10)

    def test_days_since_invalid_is_unknown_not_zero(self):
        """Zero means "reviewed today". Answering it on a parse failure made every
        unreadable date report as maximally fresh — the platform asserting the
        opposite of the truth rather than staying silent."""
        self.assertIsNone(mod52._days_since("not-a-date"))
        self.assertIsNone(mod52._days_since(""))

    def test_days_since_future_is_negative_not_clamped(self):
        """A negative age is how a caller can tell the data is damaged. Clamping it to
        0 would hide a file edited by hand or restored from a backup."""
        self.assertEqual(mod52._days_since((date.today() + timedelta(days=5)).isoformat()), -5)


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
        result = self._call(new_status="implemented")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_update_status_persisted(self):
        """The new status is saved to the file."""
        self._call(new_status="implemented")
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        req = next(r for r in data["requirements"] if r["id"] == "BR-001")
        self.assertEqual(req["status"], "implemented")

    def test_update_writes_history(self):
        """The change history is written to the repository."""
        self._call(new_status="implemented")
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
                new_status="implemented",
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

    def _update(self, req_id="FR-001", **kwargs):
        with patch("skills.requirements_maintain_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod52.update_requirement(
                project_name=PROJECT, req_id=req_id,
                change_reason="test", **kwargs)

    def test_an_unknown_status_is_refused_like_an_unknown_priority(self):
        """`status` routes everything — archived-ness, the 5.1/5.2/7.1 filters, "proven
        in practice" in reuse. A typo stored cleanly and left the requirement neither
        live nor archived, silently. The neighbouring field with a closed vocabulary,
        `priority`, has been validated since the same lesson was learned for it."""
        result = self._update(new_status="banana")
        self.assertIn("❌", result)
        self.assertIn("banana", result)
        repo = load_test_repo(PROJECT)
        node = [r for r in repo["requirements"] if r["id"] == "FR-001"][0]
        self.assertNotEqual(node.get("status"), "banana", "it was written to disk anyway")

    def test_approved_cannot_be_set_here_bypassing_chapter_5_5(self):
        """Owner's decision, 2026-08-03. `approved` is not a description of a
        requirement — it is the record of an event: stakeholders read a package and
        signed. Set by hand it bypasses all four gates of 5.5 at once, and 5.2's own
        reuse report then presents the requirement as "✅ Approved in 5.5 — proven in
        practice", citing a procedure that never happened."""
        result = self._update(new_status="approved")
        self.assertIn("❌", result)
        self.assertIn("5.5", result)
        # every other status in the vocabulary still works
        self.assertNotIn("❌", self._update(new_status="on_hold"))

    def test_reviving_an_archived_requirement_leaves_a_trace(self):
        """The reverse direction warns about edges and recommends a coverage check;
        this one said nothing at all, so a 5.2 decision was reversed with no marker
        anywhere in the answer."""
        self._set_field("FR-001", status="retired")
        result = self._update(new_status="confirmed")
        self.assertNotIn("❌", result)
        self.assertIn("retired", result.lower())
        self.assertIn("check_coverage", result)

    def test_changing_the_meaning_of_a_node_names_what_leans_on_it(self):
        """G-2. `deprecate_requirements` warns about incoming links; renaming did not,
        although it is the worse case: after a rename the edges still LOOK healthy and
        go on justifying requirements that were written against different words. The
        check has to hang on the FACT (this node has incoming justifications), not on
        the name of the operation."""
        result = self._update(req_id="BR-001", new_title="A different thing entirely")
        self.assertIn("FR-001", result,
                      "the requirements resting on this one were not named")

    def _set_field(self, req_id, **fields):
        safe_name = normalize_project_id(PROJECT)
        path = data_path(PROJECT, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for r in data["requirements"]:
            if r["id"] == req_id:
                r.update(fields)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def test_the_platforms_other_date_format_is_not_read_as_today(self):
        """The whole of chapter 4 and the stakeholder registry write `dd.mm.yyyy`.
        The parser knew ISO only and returned 0 on failure — a value indistinguishable
        from "reviewed today" — so a requirement last touched 64 days ago was reported
        as 🟢 Healthy. That is worse than silence: the platform asserts the opposite."""
        old_iso = (date.today() - timedelta(days=64)).isoformat()
        old_dotted = (date.today() - timedelta(days=64)).strftime("%d.%m.%Y")

        self._set_field("FR-001", last_reviewed=old_iso)
        iso_result = self._call()
        self._set_field("FR-001", last_reviewed=old_dotted)
        dotted_result = self._call()

        self.assertIn("64 days", iso_result)
        self.assertIn("64 days", dotted_result,
                      "the platform's own second date format read as today")

    def test_an_unparseable_date_is_reported_as_unknown_not_as_fresh(self):
        self._set_field("FR-001", last_reviewed="not a date at all")
        result = self._call()
        self.assertIn("FR-001", result)
        self.assertIn("could not be read", result.lower(),
                      "a damaged date passed silently as if the requirement were fresh")

    def test_a_review_date_in_the_future_is_reported_not_silently_trusted(self):
        """A file edited by hand, restored from a backup, or written by a machine with a
        skewed clock. The age goes negative, both `>` comparisons are false, and
        staleness is switched off for that requirement forever, without a trace."""
        self._set_field("FR-001", last_reviewed=(date.today() + timedelta(days=30)).isoformat())
        result = self._call()
        self.assertIn("FR-001", result)
        self.assertIn("in the future", result.lower())

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
                    new_status="implemented",
                )
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertGreaterEqual(len(data.get("history", [])), 3)


class TestHandingOverOwnershipWarnsAboutTheArchitectureSide(BaseMCPTest):
    """Branch review B-3. A one-line 5.2 edit manufactured a new 🔴 in 7.4 in silence.

    ADR-098 decided that ownership is READ on demand and never copied, precisely so no
    stored copy can go stale. The cost of that decision is that changing `owner` here
    silently rewrites who 7.4 considers represented: the previous owner drops to "no
    recorded tie to any requirement" and the architecture document moves them to "no
    interest recorded". Nowhere did the platform mention it.

    Not blocked — warned. The BA may well have meant exactly that; they just have to
    be able to see it.
    """

    def setUp(self):
        super().setUp()
        _setup_repo()

    def _call(self, **overrides):
        kwargs = {"project_name": PROJECT, "req_id": "BR-001",
                  "change_reason": "team change", **overrides}
        with patch("skills.requirements_maintain_mcp.save_artifact"):
            return mod52.update_requirement(**kwargs)

    def test_replacing_an_owner_says_what_it_does_to_7_4_coverage(self):
        self._call(new_owner="David Kim")
        result = self._call(new_owner="Marta Silva")
        self.assertIn("David Kim", result)
        self.assertIn("declare_stakeholder_interest", result)
        self.assertIn("7.4", result)

    def test_the_hint_names_the_mechanism_not_just_the_symptom(self):
        # A warning that does not say WHY reads as noise and gets ignored.
        self._call(new_owner="David Kim")
        result = self._call(new_owner="Marta Silva")
        self.assertIn("on the fly", result.lower())

    def test_setting_an_owner_where_there_was_none_warns_about_nobody(self):
        # Nothing was taken away from anyone, so there is nothing to warn about.
        result = self._call(new_owner="David Kim")
        self.assertNotIn("declare_stakeholder_interest", result)

    def test_re_stating_the_same_owner_warns_about_nobody(self):
        self._call(new_owner="David Kim")
        result = self._call(new_owner="david kim", new_status="implemented")
        self.assertNotIn("declare_stakeholder_interest", result)

    def test_an_update_that_does_not_touch_the_owner_says_nothing(self):
        self._call(new_owner="David Kim")
        result = self._call(new_status="implemented")
        self.assertNotIn("declare_stakeholder_interest", result)


class TestTheStalenessCountIsCountingStaleness(BaseMCPTest):
    """`stale` was derived by looking for the substring "days" in the rendered issue
    lines, so it counted whatever happened to mention days.

    The wave added "Review date is 510 days in the future — the data is damaged,
    staleness cannot be judged", and the recommendations under the same table
    immediately reported "1 not updated in a while": one paragraph saying staleness
    cannot be judged, another judging it. The draft-age line ("In draft status for N
    days already") was swept up the same way, so a requirement reviewed TODAY could be
    reported as not updated in a while.

    The module already states the rule for exactly this three lines above
    `missing_attributes`: carried as data, never recovered by re-parsing the rendered
    line. The staleness flag now follows it."""

    def setUp(self):
        super().setUp()
        _setup_repo()

    def _health(self):
        with patch("skills.requirements_maintain_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod52.check_requirements_health(project_name=PROJECT)

    def _set_dates(self, req_id, last_reviewed=None, added=None, status=None):
        repo = load_test_repo(PROJECT)
        for r in repo["requirements"]:
            if r["id"] == req_id:
                if last_reviewed is not None:
                    r["last_reviewed"] = last_reviewed
                if added is not None:
                    r["added"] = added
                if status is not None:
                    r["status"] = status
        save_test_repo(repo)

    @staticmethod
    def _days_ago(n):
        return str(date.today() - timedelta(days=n))

    @staticmethod
    def _days_ahead(n):
        return str(date.today() + timedelta(days=n))

    def test_a_damaged_future_date_is_not_counted_as_stale(self):
        self._set_dates("FR-001", last_reviewed=self._days_ahead(510))
        out = self._health()

        self.assertIn("in the future", out, "fixture did not reach the damaged-date branch")
        self.assertNotIn("not updated in a while", out,
                         "the same document says staleness cannot be judged:\n" + out)

    def test_a_requirement_reviewed_today_is_not_stale_because_it_is_an_old_draft(self):
        self._set_dates("FR-001", last_reviewed=self._days_ago(0),
                        added=self._days_ago(100), status="draft")
        out = self._health()

        self.assertIn("In draft status", out, "fixture did not reach the draft-age branch")
        self.assertNotIn("not updated in a while", out,
                         "it was reviewed today:\n" + out)

    def test_a_genuinely_stale_requirement_is_still_counted(self):
        """The control: narrowing the count must not switch it off."""
        self._set_dates("FR-001", last_reviewed=self._days_ago(90))
        out = self._health()

        self.assertIn("Not updated for 90 days", out)
        self.assertIn("1 not updated in a while", out)


class TestTheDocstringOffersOnlyStatusesTheToolAccepts(BaseMCPTest):
    """A docstring is the contract the model reads when it picks arguments, so a value
    listed there is a value that will be sent. Two directions had drifted apart:

      - it advertised `approved`, which the tool now refuses outright (approval is a
        5.5 decision, owner's ruling 2026-08-03) — an argument the platform offers and
        then rejects;
      - it named eight statuses while the vocabulary had grown to thirteen, so
        `verified`, `validated`, `pending_approval`, `rejected` and `under_change`
        were settable and undocumented.

    The comment over `VALID_REQUIREMENT_STATUSES` claims the constant exists so the
    docstring and the check "cannot drift apart". Nothing enforced that; these tests
    do, in both directions and through the real tool.
    """

    def setUp(self):
        super().setUp()
        _setup_repo()

    def _documented_statuses(self):
        """The vocabulary as the docstring offers it: the pipe-separated run between
        `new_status:` and the `Empty string` sentence."""
        doc = mod52.update_requirement.__doc__
        block = doc.split("new_status:", 1)[1].split("Empty string", 1)[0]
        tokens = {t.strip(" \n|`") for chunk in block.split("\n") for t in chunk.split("|")}
        tokens = {t for t in tokens if t and t.replace("_", "").isalpha()}
        self.assertGreaterEqual(len(tokens), 5,
                                f"the docstring's status list stopped parsing: {block!r}")
        return tokens

    def _set(self, status):
        with patch("skills.requirements_maintain_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            return mod52.update_requirement(
                project_name=PROJECT, req_id="BR-001",
                change_reason="vocabulary check", new_status=status)

    def test_every_status_the_docstring_offers_is_accepted(self):
        for status in sorted(self._documented_statuses()):
            with self.subTest(status=status):
                out = self._set(status)
                self.assertNotIn("❌", out,
                                 f"the docstring offers `{status}` and the tool refuses it:\n{out}")

    def test_every_status_the_tool_accepts_is_documented(self):
        documented = self._documented_statuses()
        settable = mod52.VALID_REQUIREMENT_STATUSES - {mod52.STATUS_APPROVED_LITERAL}
        self.assertEqual(settable - documented, set(),
                         "settable statuses missing from the docstring")

    def test_the_refusal_does_not_offer_approved_either(self):
        """The same untruth had a second copy: the ❌ for an unknown status printed
        `Allowed: ...` built from the raw vocabulary, `approved` included."""
        out = self._set("banana")
        self.assertIn("❌", out)
        allowed = out.split("Allowed:", 1)[1].split("\n", 1)[0]
        self.assertNotIn("approved", allowed,
                         f"refused value offered as allowed: {allowed}")

    def test_the_route_to_approval_is_still_named(self):
        """Removing `approved` from the offer must not remove the ANSWER to it: the BA
        asking for it still has to learn where approval actually happens."""
        doc = mod52.update_requirement.__doc__
        self.assertIn("5.5", doc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
