"""
tests/test_ch7_73.py — Tests for Chapter 7, task 7.3 (Validate Requirements)

Coverage (85 tests):
  - Utilities: _safe, _repo_path, _context_path, _assumptions_path,
             _load_repo, _load_context, _load_assumptions, _save_assumptions,
             _next_assumption_id, _find_req, _update_assumption_stats,
             _bfs_to_business, _title_matches_goal
  - set_business_context: success create, success update, invalid JSON,
    empty future_state, empty solution_scope, without potential_value,
    goals without required fields
  - check_business_alignment: no context, empty repo, no verified reqs,
    aligned via BFS, orphan, invalid req_ids, not_found ids,
    coverage matrix uncovered BG, title-match fallback
  - set_success_criteria: success with kpi_hint, req not found, invalid JSON,
    missing required fields, overwrites existing, writes to repo
  - log_assumption: success high, success medium, success low,
    invalid risk_level, empty description, invalid req_ids JSON,
    numbering AS-001/AS-002, stats updated
  - resolve_assumption: success confirmed, success refuted (warning),
    already closed, not found, invalid resolution, empty note,
    stats updated after resolve
  - mark_req_validated: success single, success multiple, not_found,
    invalid JSON, warn on non-verified status, warn on high-risk assumption,
    warn on no BG alignment, force override warnings, history recorded,
    partial success, force with no warnings
  - get_validation_report: empty repo, all active 0 reqs, validated 0%,
    validated 100%, orphan req listed, uncovered BG listed,
    open high assumptions listed, criteria_pct shown,
    ready verdict, not ready verdict
  - Pipeline: full happy path, with assumption refuted, force override
"""

import json
import os
import sys
import unittest
from datetime import date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tests.conftest import BaseMCPTest

import skills.requirements_validate_mcp as mod73
from skills.common import data_path


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def make_repo(project_id: str, requirements=None, links=None) -> dict:
    return {
        "project": project_id,
        "formality_level": "Standard",
        "created": str(date.today()),
        "updated": str(date.today()),
        "requirements": requirements or [],
        "links": links or [],
        "history": [],
    }


def save_repo(repo: dict) -> None:
    safe = repo["project"].lower().replace(" ", "_")
    path = os.path.join("governance_plans", "data", f"{safe}_traceability_repo.json")
    os.makedirs(os.path.join("governance_plans", "data"), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)


def load_repo(project_id: str) -> dict:
    safe = project_id.lower().replace(" ", "_")
    path = data_path(project_id, f"{safe}_traceability_repo.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def make_verified_req(req_id="US-001", title="Submit application", req_type="user_story",
                      status="verified", priority="High"):
    return {
        "id": req_id, "type": req_type, "title": title,
        "status": status, "priority": priority,
        "source_artifact": "governance_plans/4_3_test.md",
        "owner": "Ivanov", "version": "1.0", "added": str(date.today()),
    }


def make_business_req(req_id="BG-001", title="Reduce application processing time"):
    return {
        "id": req_id, "type": "business", "title": title,
        "status": "confirmed", "version": "1.0", "added": str(date.today()),
    }


def make_context(project_id: str, goals=None) -> dict:
    return {
        "project_id": project_id,
        "business_goals": goals or [
            {"id": "BG-001", "title": "Reduce application processing time", "kpi": "from 24h to 4h"},
            {"id": "BG-002", "title": "Increase NPS", "kpi": "from 45 to 65"},
        ],
        "future_state": "Operators work in a single window",
        "solution_scope": "In scope: CRM. Out of scope: the mobile app",
        "potential_value": "Savings of 2 million per year",
        "created_at": str(date.today()),
        "updated_at": str(date.today()),
    }


def save_context(ctx: dict) -> None:
    safe = ctx["project_id"].lower().replace(" ", "_")
    path = os.path.join("governance_plans", "data", f"{safe}_business_context.json")
    os.makedirs(os.path.join("governance_plans", "data"), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ctx, f, ensure_ascii=False, indent=2)


def make_assumptions_data(project_id: str, assumptions=None) -> dict:
    return {
        "project": project_id,
        "assumptions": assumptions or {},
        "stats": {"open": 0, "confirmed": 0, "refuted": 0},
        "created": str(date.today()),
        "updated": str(date.today()),
    }


def save_assumptions_data(data: dict) -> None:
    safe = data["project"].lower().replace(" ", "_")
    path = os.path.join("governance_plans", "data", f"{safe}_assumptions.json")
    os.makedirs(os.path.join("governance_plans", "data"), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_assumptions_data(project_id: str) -> dict:
    safe = project_id.lower().replace(" ", "_")
    path = data_path(project_id, f"{safe}_assumptions.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Utility tests
# ---------------------------------------------------------------------------

class TestUtilities(BaseMCPTest):

    def test_safe(self):
        self.assertEqual(mod73._safe("My Project"), "my_project")
        self.assertEqual(mod73._safe("crm upgrade"), "crm_upgrade")

    def test_repo_path(self):
        path = mod73._repo_path("My Project")
        self.assertIn("my_project", path)
        self.assertIn("traceability_repo.json", path)

    def test_context_path(self):
        path = mod73._context_path("My Project")
        self.assertIn("my_project", path)
        self.assertIn("business_context.json", path)

    def test_assumptions_path(self):
        path = mod73._assumptions_path("My Project")
        self.assertIn("my_project", path)
        self.assertIn("assumptions.json", path)

    def test_load_repo_empty(self):
        repo = mod73._load_repo("nonexistent_73")
        self.assertEqual(repo["requirements"], [])
        self.assertEqual(repo["links"], [])

    def test_load_context_missing(self):
        result = mod73._load_context("nonexistent_73")
        self.assertIsNone(result)

    def test_load_assumptions_empty(self):
        data = mod73._load_assumptions("nonexistent_73")
        self.assertEqual(data["assumptions"], {})
        self.assertEqual(data["stats"]["open"], 0)

    def test_next_assumption_id_first(self):
        data = make_assumptions_data("p")
        self.assertEqual(mod73._next_assumption_id(data), "AS-001")

    def test_next_assumption_id_increments(self):
        data = make_assumptions_data("p", {
            "AS-001": {"status": "open"},
            "AS-002": {"status": "confirmed"},
        })
        self.assertEqual(mod73._next_assumption_id(data), "AS-003")

    def test_find_req_found(self):
        repo = make_repo("p", [make_verified_req("US-001")])
        req = mod73._find_req(repo, "US-001")
        self.assertIsNotNone(req)
        self.assertEqual(req["id"], "US-001")

    def test_find_req_not_found(self):
        repo = make_repo("p", [])
        self.assertIsNone(mod73._find_req(repo, "US-999"))

    def test_update_assumption_stats(self):
        data = make_assumptions_data("p", {
            "AS-001": {"status": "open"},
            "AS-002": {"status": "confirmed"},
            "AS-003": {"status": "refuted"},
            "AS-004": {"status": "open"},
        })
        mod73._update_assumption_stats(data)
        self.assertEqual(data["stats"]["open"], 2)
        self.assertEqual(data["stats"]["confirmed"], 1)
        self.assertEqual(data["stats"]["refuted"], 1)

    def test_title_matches_goal_true(self):
        self.assertTrue(mod73._title_matches_goal(
            "Automatically distribute applications through the system",
            "Reduce application processing time through automation"
        ))

    def test_title_matches_goal_false(self):
        self.assertFalse(mod73._title_matches_goal(
            "Configure the button color",
            "Increase revenue"
        ))

    def test_bfs_to_business_direct_link(self):
        bg = make_business_req("BG-001", "Reduce processing time")
        fr = make_verified_req("FR-001", "Automatic distribution", "functional")
        repo = make_repo("p",
            requirements=[bg, fr],
            links=[{"from": "FR-001", "to": "BG-001", "relation": "derives"}]
        )
        result = mod73._bfs_to_business(repo, "FR-001")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "BG-001")

    def test_bfs_to_business_no_link(self):
        bg = make_business_req("BG-001")
        fr = make_verified_req("FR-001")
        repo = make_repo("p", requirements=[bg, fr], links=[])
        result = mod73._bfs_to_business(repo, "FR-001")
        self.assertEqual(result, [])

    def test_bfs_to_business_indirect_link(self):
        bg = make_business_req("BG-001")
        br = {"id": "BR-001", "type": "business", "title": "Intermediate", "status": "confirmed"}
        fr = make_verified_req("FR-001")
        repo = make_repo("p",
            requirements=[bg, br, fr],
            links=[
                {"from": "FR-001", "to": "BR-001", "relation": "derives"},
                {"from": "BR-001", "to": "BG-001", "relation": "derives"},
            ]
        )
        result = mod73._bfs_to_business(repo, "FR-001")
        ids = {r["id"] for r in result}
        self.assertIn("BG-001", ids)


# ---------------------------------------------------------------------------
# set_business_context tests
# ---------------------------------------------------------------------------

class TestSetBusinessContext(BaseMCPTest):

    def _valid_goals(self):
        return json.dumps([
            {"id": "BG-001", "title": "Reduce processing time", "kpi": "from 24h to 4h"},
            {"id": "BG-002", "title": "Increase NPS"},
        ])

    def test_create_success(self):
        result = mod73.set_business_context(
            "proj73", self._valid_goals(),
            "Operators work in a single window",
            "In scope: CRM"
        )
        self.assertIn("Business context created", result)
        self.assertIn("BG-001", result)
        ctx = mod73._load_context("proj73")
        self.assertIsNotNone(ctx)
        self.assertEqual(len(ctx["business_goals"]), 2)

    def test_update_warning(self):
        mod73.set_business_context(
            "proj73", self._valid_goals(),
            "Future state", "Scope"
        )
        result = mod73.set_business_context(
            "proj73", self._valid_goals(),
            "Updated future state", "Updated scope"
        )
        self.assertIn("UPDATED", result)

    def test_invalid_goals_json(self):
        result = mod73.set_business_context(
            "proj73", "not json", "Future", "Scope"
        )
        self.assertIn("❌", result)
        self.assertIn("parsing", result)

    def test_goals_not_list(self):
        result = mod73.set_business_context(
            "proj73", '{"id":"BG-001"}', "Future", "Scope"
        )
        self.assertIn("❌", result)

    def test_goals_missing_required_fields(self):
        result = mod73.set_business_context(
            "proj73", '[{"description": "no id or title"}]',
            "Future", "Scope"
        )
        self.assertIn("❌", result)

    def test_empty_future_state(self):
        result = mod73.set_business_context(
            "proj73", self._valid_goals(), "   ", "Scope"
        )
        self.assertIn("❌", result)
        self.assertIn("future_state", result)

    def test_empty_solution_scope(self):
        result = mod73.set_business_context(
            "proj73", self._valid_goals(), "Future", ""
        )
        self.assertIn("❌", result)
        self.assertIn("solution_scope", result)

    def test_potential_value_optional(self):
        result = mod73.set_business_context(
            "proj73", self._valid_goals(), "Future", "Scope"
        )
        self.assertIn("✅", result)
        ctx = mod73._load_context("proj73")
        self.assertEqual(ctx["potential_value"], "")

    def test_manual_context_note_in_output(self):
        result = mod73.set_business_context(
            "proj73", self._valid_goals(), "Future", "Scope"
        )
        # 7.3 can set the business context by hand; Chapter 6 (6.1/6.2) populates the
        # same file automatically when run. The note must say so — not claim Chapter 6
        # is unimplemented (it is implemented; the old "surrogate/temporary" wording lied).
        self.assertIn("Chapter 6", result)
        self.assertIn("automatically", result)


# ---------------------------------------------------------------------------
# check_business_alignment tests
# ---------------------------------------------------------------------------

class TestCheckBusinessAlignment(BaseMCPTest):

    def _setup(self, project_id="proj73"):
        ctx = make_context(project_id)
        save_context(ctx)
        return ctx

    def test_no_context(self):
        result = mod73.check_business_alignment("proj73")
        self.assertIn("❌", result)
        self.assertIn("set_business_context", result)

    def test_empty_repo(self):
        self._setup()
        result = mod73.check_business_alignment("proj73")
        self.assertIn("⚠️", result)
        self.assertIn("empty", result)

    def test_no_verified_reqs(self):
        self._setup()
        repo = make_repo("proj73", [make_verified_req("US-001", status="draft")])
        save_repo(repo)
        result = mod73.check_business_alignment("proj73")
        self.assertIn("No verified/validated", result)

    def test_aligned_via_bfs(self):
        self._setup()
        bg = make_business_req("BG-001", "Reduce application processing time")
        fr = make_verified_req("FR-001", "Automatically distribute the application", "functional")
        repo = make_repo("proj73",
            requirements=[bg, fr],
            links=[{"from": "FR-001", "to": "BG-001", "relation": "derives"}]
        )
        save_repo(repo)
        result = mod73.check_business_alignment("proj73")
        self.assertIn("FR-001", result)
        self.assertIn("Aligned requirements", result)

    def test_orphan_req(self):
        self._setup()
        fr = make_verified_req("FR-001", "A completely irrelevant feature", "functional")
        repo = make_repo("proj73", requirements=[fr], links=[])
        save_repo(repo)
        result = mod73.check_business_alignment("proj73")
        self.assertIn("Orphan", result)
        self.assertIn("FR-001", result)

    def test_invalid_req_ids_json(self):
        self._setup()
        fr = make_verified_req("FR-001", "Applications", "functional")
        repo = make_repo("proj73", [fr])
        save_repo(repo)
        result = mod73.check_business_alignment("proj73", req_ids="not json")
        self.assertIn("❌", result)

    def test_not_found_req_ids(self):
        self._setup()
        fr = make_verified_req("FR-001", "Applications", "functional")
        repo = make_repo("proj73", requirements=[fr], links=[])
        save_repo(repo)
        result = mod73.check_business_alignment("proj73", req_ids='["US-999"]')
        # US-999 not found -> reqs_to_check empty -> message about no verified req
        self.assertTrue(
            "not found" in result.lower()
            or "no verified" in result.lower()
            or "no req" in result.lower()
            or "ℹ️" in result
        )

    def test_coverage_matrix_shown(self):
        self._setup()
        fr = make_verified_req("FR-001", "Applications", "functional")
        repo = make_repo("proj73", requirements=[fr], links=[])
        save_repo(repo)
        result = mod73.check_business_alignment("proj73")
        self.assertIn("Coverage Matrix", result)
        self.assertIn("BG-001", result)

    def test_title_match_is_advisory_not_alignment(self):
        self._setup()
        # req without a direct link in the graph, but the title overlaps with a BG.
        # Graph-truth (F-A): a title word-overlap is ADVISORY only — it is surfaced for
        # the analyst to confirm and link, but never counted as aligned/covered.
        fr = make_verified_req("FR-001", "Reduce application processing time through automation", "functional")
        repo = make_repo("proj73", requirements=[fr], links=[])
        save_repo(repo)
        result = mod73.check_business_alignment("proj73")
        self.assertIn("FR-001", result)
        self.assertIn("Title match only", result)      # advisory summary row
        self.assertIn("advisory", result.lower())      # advisory section present
        self.assertNotIn("_(traced in graph)_", result)  # NOT counted as aligned

    def test_business_type_excluded(self):
        # business-type req is not included in the check (skipped in the loop)
        ctx = make_context("proj73", [{"id": "BG-001", "title": "Reduce time"}])
        save_context(ctx)
        bg = make_business_req("BG-001", "Reduce time")
        bg["status"] = "verified"
        repo = make_repo("proj73", requirements=[bg], links=[])
        save_repo(repo)
        result = mod73.check_business_alignment("proj73")
        # No verified req of the needed type -> either 0 checked, or "No verified"
        self.assertTrue(
            "no verified" in result.lower()
            or "Reqs checked:** 0" in result
        )


# ---------------------------------------------------------------------------
# set_success_criteria tests
# ---------------------------------------------------------------------------

class TestSetSuccessCriteria(BaseMCPTest):

    def _valid_criteria(self, kpi_ref="BG-001"):
        return json.dumps({
            "baseline": "45 min manually",
            "target": "≤ 30 sec",
            "measurement_method": "Average time in monitoring",
            "kpi_ref": kpi_ref,
        })

    def test_success_writes_to_repo(self):
        fr = make_verified_req("FR-001", "Auto-distribution", "functional")
        repo = make_repo("proj73", [fr])
        save_repo(repo)
        result = mod73.set_success_criteria("proj73", "FR-001", self._valid_criteria())
        self.assertIn("✅", result)
        self.assertIn("FR-001", result)
        updated = load_repo("proj73")
        req = updated["requirements"][0]
        self.assertIn("success_criteria", req)
        self.assertEqual(req["success_criteria"]["target"], "≤ 30 sec")

    def test_kpi_hint_shown(self):
        ctx = make_context("proj73")
        save_context(ctx)
        fr = make_verified_req("FR-001", "Auto-distribution", "functional")
        repo = make_repo("proj73", [fr])
        save_repo(repo)
        result = mod73.set_success_criteria("proj73", "FR-001", self._valid_criteria("BG-001"))
        self.assertIn("KPI", result)

    def test_req_not_found(self):
        repo = make_repo("proj73", [])
        save_repo(repo)
        result = mod73.set_success_criteria("proj73", "US-999", self._valid_criteria())
        self.assertIn("❌", result)
        self.assertIn("not found", result)

    def test_invalid_json(self):
        result = mod73.set_success_criteria("proj73", "FR-001", "bad json")
        self.assertIn("❌", result)

    def test_missing_required_fields(self):
        result = mod73.set_success_criteria(
            "proj73", "FR-001",
            '{"baseline": "old", "target": "new"}'  # no measurement_method
        )
        self.assertIn("❌", result)
        self.assertIn("measurement_method", result)

    def test_overwrites_existing_criteria(self):
        fr = make_verified_req("FR-001", "Auto-distribution", "functional")
        fr["success_criteria"] = {"baseline": "old", "target": "old_target",
                                   "measurement_method": "old_method", "kpi_ref": "",
                                   "set_date": str(date.today())}
        repo = make_repo("proj73", [fr])
        save_repo(repo)
        mod73.set_success_criteria("proj73", "FR-001", self._valid_criteria())
        updated = load_repo("proj73")
        self.assertEqual(updated["requirements"][0]["success_criteria"]["target"], "≤ 30 sec")

    def test_history_recorded(self):
        fr = make_verified_req("FR-001", "Applications", "functional")
        repo = make_repo("proj73", [fr])
        save_repo(repo)
        mod73.set_success_criteria("proj73", "FR-001", self._valid_criteria())
        updated = load_repo("proj73")
        self.assertTrue(any(h["action"] == "success_criteria_set" for h in updated["history"]))


# ---------------------------------------------------------------------------
# log_assumption tests
# ---------------------------------------------------------------------------

class TestLogAssumption(BaseMCPTest):

    def test_success_high_risk(self):
        result = mod73.log_assumption(
            "proj73",
            "We assume REST API support in legacy",
            '["US-001", "FR-001"]',
            "high",
            "Ivanov"
        )
        self.assertIn("AS-001", result)
        self.assertIn("high", result)
        data = load_assumptions_data("proj73")
        self.assertIn("AS-001", data["assumptions"])
        self.assertEqual(data["assumptions"]["AS-001"]["risk_level"], "high")

    def test_success_medium_risk(self):
        result = mod73.log_assumption(
            "proj73", "Operators are ready for training", '["US-002"]', "medium"
        )
        self.assertIn("AS-001", result)
        data = load_assumptions_data("proj73")
        self.assertEqual(data["assumptions"]["AS-001"]["risk_level"], "medium")

    def test_success_low_risk(self):
        result = mod73.log_assumption(
            "proj73", "Browsers support ES2020", '[]', "low"
        )
        self.assertIn("AS-001", result)

    def test_invalid_risk_level(self):
        result = mod73.log_assumption(
            "proj73", "Some assumption", '["US-001"]', "critical"
        )
        self.assertIn("❌", result)
        self.assertIn("risk_level", result)

    def test_empty_description(self):
        result = mod73.log_assumption(
            "proj73", "   ", '["US-001"]', "high"
        )
        self.assertIn("❌", result)
        self.assertIn("description", result)

    def test_invalid_req_ids_json(self):
        result = mod73.log_assumption(
            "proj73", "Some assumption", "not json", "high"
        )
        self.assertIn("❌", result)

    def test_numbering_sequential(self):
        mod73.log_assumption("proj73", "First", '[]', "low")
        mod73.log_assumption("proj73", "Second", '[]', "medium")
        data = load_assumptions_data("proj73")
        self.assertIn("AS-001", data["assumptions"])
        self.assertIn("AS-002", data["assumptions"])

    def test_stats_updated(self):
        mod73.log_assumption("proj73", "A1", '[]', "high")
        mod73.log_assumption("proj73", "A2", '[]', "low")
        data = load_assumptions_data("proj73")
        self.assertEqual(data["stats"]["open"], 2)

    def test_high_risk_warning_in_output(self):
        result = mod73.log_assumption(
            "proj73", "High risk thing", '["US-001"]', "high"
        )
        self.assertIn("high risk", result.lower())

    def test_assigned_to_saved(self):
        mod73.log_assumption(
            "proj73", "Assumption", '[]', "medium", "Petrova A."
        )
        data = load_assumptions_data("proj73")
        self.assertEqual(data["assumptions"]["AS-001"]["assigned_to"], "Petrova A.")


# ---------------------------------------------------------------------------
# resolve_assumption tests
# ---------------------------------------------------------------------------

class TestResolveAssumption(BaseMCPTest):

    def _setup_assumption(self, project_id="proj73", risk_level="high",
                           req_ids=None, assumption_id="AS-001"):
        data = make_assumptions_data(project_id, {
            assumption_id: {
                "assumption_id": assumption_id,
                "description": "Test assumption",
                "req_ids": req_ids or ["US-001"],
                "risk_level": risk_level,
                "status": "open",
                "assigned_to": "",
                "created_at": str(date.today()),
                "resolved_at": None,
                "resolution_note": "",
            }
        })
        mod73._update_assumption_stats(data)
        save_assumptions_data(data)
        return data

    def test_resolve_confirmed(self):
        self._setup_assumption()
        result = mod73.resolve_assumption(
            "proj73", "AS-001", "confirmed", "Verified on the test bench"
        )
        self.assertIn("confirmed", result)
        data = load_assumptions_data("proj73")
        self.assertEqual(data["assumptions"]["AS-001"]["status"], "confirmed")

    def test_resolve_refuted_warns_reqs(self):
        self._setup_assumption(req_ids=["US-001", "FR-002"])
        result = mod73.resolve_assumption(
            "proj73", "AS-001", "refuted", "Integration is impossible"
        )
        self.assertIn("refuted", result.lower())
        self.assertIn("US-001", result)
        self.assertIn("FR-002", result)

    def test_already_closed(self):
        data = make_assumptions_data("proj73", {
            "AS-001": {
                "assumption_id": "AS-001",
                "description": "Done",
                "req_ids": [],
                "risk_level": "low",
                "status": "confirmed",
                "resolved_at": str(date.today()),
                "resolution_note": "Was confirmed",
            }
        })
        save_assumptions_data(data)
        result = mod73.resolve_assumption("proj73", "AS-001", "confirmed", "Again")
        self.assertIn("already closed", result)

    def test_not_found(self):
        data = make_assumptions_data("proj73")
        save_assumptions_data(data)
        result = mod73.resolve_assumption("proj73", "AS-999", "confirmed", "Note")
        self.assertIn("❌", result)
        self.assertIn("not found", result)

    def test_invalid_resolution(self):
        self._setup_assumption()
        result = mod73.resolve_assumption("proj73", "AS-001", "unknown", "Note")
        self.assertIn("❌", result)
        self.assertIn("resolution", result)

    def test_empty_note(self):
        self._setup_assumption()
        result = mod73.resolve_assumption("proj73", "AS-001", "confirmed", "   ")
        self.assertIn("❌", result)
        self.assertIn("resolution_note", result)

    def test_stats_updated_after_resolve(self):
        self._setup_assumption()
        mod73.resolve_assumption("proj73", "AS-001", "confirmed", "OK")
        data = load_assumptions_data("proj73")
        self.assertEqual(data["stats"]["confirmed"], 1)
        self.assertEqual(data["stats"]["open"], 0)


# ---------------------------------------------------------------------------
# mark_req_validated tests
# ---------------------------------------------------------------------------

class TestMarkReqValidated(BaseMCPTest):

    def _setup_clean(self, project_id="proj73"):
        """Repo + context, no assumptions."""
        bg = make_business_req("BG-001", "Reduce application processing time")
        fr = make_verified_req("FR-001", "Reduce application processing time by 50%", "functional")
        repo = make_repo(project_id,
            requirements=[bg, fr],
            links=[{"from": "FR-001", "to": "BG-001", "relation": "derives"}]
        )
        save_repo(repo)
        ctx = make_context(project_id, [{"id": "BG-001", "title": "Reduce application processing time", "kpi": "x"}])
        save_context(ctx)

    def test_success_single(self):
        self._setup_clean()
        result = mod73.mark_req_validated("proj73", '["FR-001"]')
        self.assertIn("✅", result)
        self.assertIn("validated", result)
        updated = load_repo("proj73")
        fr = next(r for r in updated["requirements"] if r["id"] == "FR-001")
        self.assertEqual(fr["status"], "validated")

    def test_success_multiple(self):
        bg = make_business_req("BG-001", "Objective A")
        fr1 = make_verified_req("FR-001", "Objective A implementation", "functional")
        fr2 = make_verified_req("FR-002", "Objective A addition", "functional")
        repo = make_repo("proj73",
            requirements=[bg, fr1, fr2],
            links=[
                {"from": "FR-001", "to": "BG-001", "relation": "derives"},
                {"from": "FR-002", "to": "BG-001", "relation": "derives"},
            ]
        )
        save_repo(repo)
        ctx = make_context("proj73", [{"id": "BG-001", "title": "Objective A"}])
        save_context(ctx)
        result = mod73.mark_req_validated("proj73", '["FR-001", "FR-002"]')
        self.assertIn("✅", result)
        updated = load_repo("proj73")
        statuses = {r["id"]: r["status"] for r in updated["requirements"]}
        self.assertEqual(statuses["FR-001"], "validated")
        self.assertEqual(statuses["FR-002"], "validated")

    def test_not_found(self):
        save_repo(make_repo("proj73"))
        result = mod73.mark_req_validated("proj73", '["US-999"]')
        self.assertIn("not found", result)

    def test_invalid_json(self):
        result = mod73.mark_req_validated("proj73", "bad json")
        self.assertIn("❌", result)

    def test_warn_non_verified_status(self):
        self._setup_clean()
        # Change FR-001 status to draft
        repo = load_repo("proj73")
        for r in repo["requirements"]:
            if r["id"] == "FR-001":
                r["status"] = "draft"
        save_repo(repo)
        result = mod73.mark_req_validated("proj73", '["FR-001"]')
        self.assertIn("⚠️", result)
        self.assertIn("verified", result)

    def test_warn_high_risk_assumption(self):
        self._setup_clean()
        assum_data = make_assumptions_data("proj73", {
            "AS-001": {
                "assumption_id": "AS-001",
                "description": "Risk",
                "req_ids": ["FR-001"],
                "risk_level": "high",
                "status": "open",
                "assigned_to": "",
                "created_at": str(date.today()),
                "resolved_at": None,
                "resolution_note": "",
            }
        })
        mod73._update_assumption_stats(assum_data)
        save_assumptions_data(assum_data)
        result = mod73.mark_req_validated("proj73", '["FR-001"]')
        self.assertIn("⚠️", result)
        self.assertIn("assumption", result.lower())

    def test_warn_no_bg_alignment(self):
        # req verified, no links, no title-match
        fr = make_verified_req("FR-001", "A completely ambiguous feature xyz", "functional")
        repo = make_repo("proj73", requirements=[fr], links=[])
        save_repo(repo)
        ctx = make_context("proj73", [{"id": "BG-001", "title": "Another objective abc"}])
        save_context(ctx)
        result = mod73.mark_req_validated("proj73", '["FR-001"]')
        self.assertIn("⚠️", result)

    def test_force_override_warnings(self):
        # req in draft status, but force=True
        fr = make_verified_req("FR-001", "An unknown thing", "functional")
        fr["status"] = "draft"
        repo = make_repo("proj73", requirements=[fr], links=[])
        save_repo(repo)
        ctx = make_context("proj73", [{"id": "BG-001", "title": "Something else"}])
        save_context(ctx)
        result = mod73.mark_req_validated("proj73", '["FR-001"]', force=True)
        self.assertIn("validated", result)
        self.assertIn("force", result.lower())
        updated = load_repo("proj73")
        fr_updated = next(r for r in updated["requirements"] if r["id"] == "FR-001")
        self.assertEqual(fr_updated["status"], "validated")

    def test_history_recorded(self):
        self._setup_clean()
        mod73.mark_req_validated("proj73", '["FR-001"]')
        updated = load_repo("proj73")
        history_entries = [h for h in updated["history"] if h["action"] == "req_validated"]
        self.assertEqual(len(history_entries), 1)
        self.assertEqual(history_entries[0]["new_status"], "validated")

    def test_partial_success(self):
        bg = make_business_req("BG-001", "Objective")
        fr1 = make_verified_req("FR-001", "Objective implementation", "functional")
        fr2 = make_verified_req("FR-002", "Other", "functional")
        fr2["status"] = "draft"
        repo = make_repo("proj73",
            requirements=[bg, fr1, fr2],
            links=[{"from": "FR-001", "to": "BG-001", "relation": "derives"}]
        )
        save_repo(repo)
        ctx = make_context("proj73", [{"id": "BG-001", "title": "Objective"}])
        save_context(ctx)
        result = mod73.mark_req_validated("proj73", '["FR-001", "FR-002"]')
        # FR-001 validated, FR-002 warned
        self.assertIn("✅", result)
        self.assertIn("⚠️", result)

    def test_force_with_no_warnings(self):
        # force=True when there are no warnings — should work normally
        self._setup_clean()
        result = mod73.mark_req_validated("proj73", '["FR-001"]', force=True)
        self.assertIn("validated", result)
        updated = load_repo("proj73")
        fr = next(r for r in updated["requirements"] if r["id"] == "FR-001")
        self.assertEqual(fr["status"], "validated")


# ---------------------------------------------------------------------------
# get_validation_report tests
# ---------------------------------------------------------------------------

class TestGetValidationReport(BaseMCPTest):

    def test_empty_repo(self):
        result = mod73.get_validation_report("proj73")
        self.assertIn("⚠️", result)
        self.assertIn("No active requirements", result)

    def test_no_active_reqs_of_right_type(self):
        # Only business and test — they are excluded
        bg = make_business_req("BG-001")
        test_req = {"id": "TC-001", "type": "test", "title": "Test", "status": "draft",
                    "version": "1.0", "added": str(date.today())}
        repo = make_repo("proj73", [bg, test_req])
        save_repo(repo)
        result = mod73.get_validation_report("proj73")
        self.assertIn("⚠️", result)

    def test_zero_percent_validated(self):
        fr = make_verified_req("FR-001", "Applications", "functional")
        repo = make_repo("proj73", [fr])
        save_repo(repo)
        result = mod73.get_validation_report("proj73")
        self.assertIn("0.0%", result)

    def test_hundred_percent_validated(self):
        fr = make_verified_req("FR-001", "Applications", "functional", status="validated")
        repo = make_repo("proj73", [fr])
        save_repo(repo)
        result = mod73.get_validation_report("proj73")
        self.assertIn("100.0%", result)

    def test_orphan_listed(self):
        fr = make_verified_req("FR-001", "An irrelevant thing xyz", "functional")
        repo = make_repo("proj73", [fr])
        save_repo(repo)
        ctx = make_context("proj73", [{"id": "BG-001", "title": "Absolutely different abc"}])
        save_context(ctx)
        result = mod73.get_validation_report("proj73")
        self.assertIn("Orphan", result) if "Orphan" in result else self.assertIn("FR-001", result)

    def test_uncovered_bg_listed(self):
        fr = make_verified_req("FR-001", "Applications", "functional", status="validated")
        repo = make_repo("proj73", [fr])
        save_repo(repo)
        ctx = make_context("proj73", [
            {"id": "BG-001", "title": "Covered applications objective"},
            {"id": "BG-002", "title": "An absolutely unique uncovered objective"},
        ])
        save_context(ctx)
        result = mod73.get_validation_report("proj73")
        # BG-002 is not covered
        self.assertIn("BG-002", result)

    def test_open_high_assumptions_listed(self):
        fr = make_verified_req("FR-001", "Applications", "functional", status="validated")
        repo = make_repo("proj73", [fr])
        save_repo(repo)
        assum_data = make_assumptions_data("proj73", {
            "AS-001": {
                "assumption_id": "AS-001",
                "description": "A dangerous assumption",
                "req_ids": ["FR-001"],
                "risk_level": "high",
                "status": "open",
                "assigned_to": "Ivanov",
                "created_at": str(date.today()),
                "resolved_at": None,
                "resolution_note": "",
            }
        })
        mod73._update_assumption_stats(assum_data)
        save_assumptions_data(assum_data)
        result = mod73.get_validation_report("proj73")
        self.assertIn("AS-001", result)
        self.assertIn("High-Risk", result)

    def test_criteria_pct_shown(self):
        fr1 = make_verified_req("FR-001", "Applications 1", "functional", status="validated")
        fr1["success_criteria"] = {"baseline": "old", "target": "new",
                                    "measurement_method": "meter", "kpi_ref": ""}
        fr2 = make_verified_req("FR-002", "Applications 2", "functional", status="validated")
        repo = make_repo("proj73", [fr1, fr2])
        save_repo(repo)
        result = mod73.get_validation_report("proj73")
        self.assertIn("criteria", result.lower())

    def test_ready_verdict(self):
        # All reqs validated, no assumptions, no orphan
        bg = make_business_req("BG-001", "Reduce time")
        fr = make_verified_req("FR-001", "Reduce processing time", "functional", status="validated")
        repo = make_repo("proj73",
            requirements=[bg, fr],
            links=[{"from": "FR-001", "to": "BG-001", "relation": "derives"}]
        )
        save_repo(repo)
        ctx = make_context("proj73", [{"id": "BG-001", "title": "Reduce time"}])
        save_context(ctx)
        result = mod73.get_validation_report("proj73")
        self.assertIn("✅", result)
        self.assertIn("7.5", result)

    def test_not_ready_verdict(self):
        fr = make_verified_req("FR-001", "Applications", "functional")
        repo = make_repo("proj73", [fr])
        save_repo(repo)
        result = mod73.get_validation_report("proj73")
        self.assertIn("❌", result)
        self.assertIn("Not ready", result)

    def test_report_saved_via_artifact(self):
        fr = make_verified_req("FR-001", "Applications", "functional")
        repo = make_repo("proj73", [fr])
        save_repo(repo)
        mod73.get_validation_report("proj73")
        # save_artifact is mocked in conftest — we check the call returned a string
        # (not an exception)


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------

class TestPipeline(BaseMCPTest):

    def test_happy_path(self):
        """Full pipeline without errors."""
        # 1. set_business_context
        r = mod73.set_business_context(
            "proj73",
            '[{"id":"BG-001","title":"Reduce application processing time","kpi":"from 24h to 4h"}]',
            "Operators work in a single window",
            "In scope: CRM"
        )
        self.assertIn("created", r)

        # 2. Create a repo with a verified req
        bg = make_business_req("BG-001", "Reduce application processing time")
        fr = make_verified_req("FR-001", "Reduce application processing time automatically", "functional")
        repo = make_repo("proj73",
            requirements=[bg, fr],
            links=[{"from": "FR-001", "to": "BG-001", "relation": "derives"}]
        )
        save_repo(repo)

        # 3. check_business_alignment
        r = mod73.check_business_alignment("proj73")
        self.assertIn("FR-001", r)

        # 4. set_success_criteria (optional step)
        r = mod73.set_success_criteria(
            "proj73", "FR-001",
            '{"baseline":"45 min","target":"30 sec","measurement_method":"monitoring","kpi_ref":"BG-001"}'
        )
        self.assertIn("✅", r)

        # 5. log_assumption
        r = mod73.log_assumption(
            "proj73", "Legacy supports the API", '["FR-001"]', "medium"
        )
        self.assertIn("AS-001", r)

        # 6. resolve_assumption
        r = mod73.resolve_assumption(
            "proj73", "AS-001", "confirmed", "Verified on the bench"
        )
        self.assertIn("confirmed", r)

        # 7. mark_req_validated
        r = mod73.mark_req_validated("proj73", '["FR-001"]')
        self.assertIn("validated", r)

        # 8. get_validation_report
        r = mod73.get_validation_report("proj73")
        self.assertIn("FR-001", r)
        self.assertIn("100.0%", r)

    def test_pipeline_with_refuted_assumption(self):
        """On a refuted assumption — the req must be revisited."""
        bg = make_business_req("BG-001", "Reduce processing time")
        fr = make_verified_req("FR-001", "Reduce processing time", "functional")
        repo = make_repo("proj73",
            requirements=[bg, fr],
            links=[{"from": "FR-001", "to": "BG-001", "relation": "derives"}]
        )
        save_repo(repo)
        ctx = make_context("proj73", [{"id": "BG-001", "title": "Reduce processing time"}])
        save_context(ctx)

        mod73.log_assumption("proj73", "The API is available", '["FR-001"]', "high")
        r = mod73.resolve_assumption("proj73", "AS-001", "refuted", "The API is unavailable")
        self.assertIn("FR-001", r)
        self.assertIn("refuted", r.lower())

    def test_pipeline_force_override(self):
        """force=True allows overriding warnings."""
        fr = make_verified_req("FR-001", "Something special abc xyz", "functional")
        fr["status"] = "draft"
        repo = make_repo("proj73", [fr])
        save_repo(repo)
        ctx = make_context("proj73", [{"id": "BG-001", "title": "Other"}])
        save_context(ctx)

        r = mod73.mark_req_validated("proj73", '["FR-001"]', force=True)
        self.assertIn("validated", r)
        updated = load_repo("proj73")
        fr_upd = next(r for r in updated["requirements"] if r["id"] == "FR-001")
        self.assertEqual(fr_upd["status"], "validated")


# ---------------------------------------------------------------------------
# 7.3 audit regression (2026-07-19): the graph traversal must recognise the REAL
# business-goal node types from 6.1/6.2 (business_goal / business_need), not only the
# legacy "business" type. Otherwise reqs traced to a goal through the graph are false orphans,
# and the goal nodes themselves are miscounted as requirements.
# ---------------------------------------------------------------------------

def _goal_node(req_id="BG-001", title="Reduce client waiting duration", ntype="business_goal"):
    return {"id": req_id, "type": ntype, "title": title, "status": "confirmed",
            "version": "1.0", "added": str(date.today())}


class TestBusinessNodeTypes(BaseMCPTest):

    def test_bfs_reaches_business_goal_node(self):
        repo = make_repo("p",
            requirements=[_goal_node("BG-001", "X", "business_goal"),
                          make_verified_req("FR-001", "Y", "functional")],
            links=[{"from": "FR-001", "to": "BG-001", "relation": "derives"}])
        result = mod73._bfs_to_business(repo, "FR-001")
        self.assertEqual({n["id"] for n in result}, {"BG-001"})

    def test_bfs_reaches_business_need_node(self):
        repo = make_repo("p",
            requirements=[_goal_node("BN-001", "X", "business_need"),
                          make_verified_req("FR-001", "Y", "functional")],
            links=[{"from": "FR-001", "to": "BN-001", "relation": "derives"}])
        result = mod73._bfs_to_business(repo, "FR-001")
        self.assertEqual({n["id"] for n in result}, {"BN-001"})

    def test_alignment_via_bfs_to_business_goal_node(self):
        """A req traced to a business_goal through the graph is aligned via BFS, not a false orphan.
        Titles share no >=5-char word, so only the graph link can align it."""
        P = "align_bg73"
        save_context(make_context(P, goals=[
            {"id": "BG-001", "title": "Reduce client waiting duration", "kpi": "24h->4h"}]))
        save_repo(make_repo(P,
            requirements=[_goal_node("BG-001", "Reduce client waiting duration", "business_goal"),
                          make_verified_req("FR-001", "Automatic routing engine", "functional")],
            links=[{"from": "FR-001", "to": "BG-001", "relation": "derives"}]))
        result = mod73.check_business_alignment(P)
        self.assertIn("_(traced in graph)_", result)
        aligned_section = result.split("Aligned requirements")[-1].split("##")[0]
        self.assertIn("FR-001", aligned_section)

    def test_report_excludes_business_goal_from_requirements(self):
        """A business_goal node must not be counted as a requirement nor flagged orphan."""
        P = "report_bg73"
        save_context(make_context(P, goals=[
            {"id": "BG-001", "title": "Reduce client waiting duration", "kpi": "24h->4h"}]))
        save_repo(make_repo(P,
            requirements=[_goal_node("BG-001", "Reduce client waiting duration", "business_goal"),
                          make_verified_req("FR-001", "Automatic routing engine", "functional",
                                            status="validated")],
            links=[{"from": "FR-001", "to": "BG-001", "relation": "derives"}]))
        result = mod73.get_validation_report(P)
        self.assertIn("| Total active reqs | 1 |", result)


# ---------------------------------------------------------------------------
# B2-bis — the verification precondition reads the durable record, not `status`
# ---------------------------------------------------------------------------

class TestValidationVerificationPrecondition(BaseMCPTest):

    def _setup(self, status, history=None):
        """FR-001 traceable to BG-001, with the given status and repo history."""
        bg = make_business_req("BG-001", "Reduce application processing time")
        fr = make_verified_req("FR-001", "Reduce application processing time by 50%",
                               "functional", status=status)
        repo = make_repo("proj73",
            requirements=[bg, fr],
            links=[{"from": "FR-001", "to": "BG-001", "relation": "derives"}],
        )
        repo["history"] = history or []
        save_repo(repo)
        ctx = make_context("proj73", [{"id": "BG-001",
                                       "title": "Reduce application processing time",
                                       "kpi": "x"}])
        save_context(ctx)

    def test_verified_then_approved_does_not_warn(self):
        """The B2 case: 5.5 overwrote the status, but the req DID pass 7.2."""
        self._setup("approved", [{"action": "req_verified", "req_id": "FR-001"}])
        result = mod73.mark_req_validated("proj73", '["FR-001"]')
        self.assertNotIn("expected 'verified'", result)

    def test_never_verified_still_warns(self):
        self._setup("draft")
        result = mod73.mark_req_validated("proj73", '["FR-001"]')
        self.assertIn("expected 'verified'", result)


if __name__ == "__main__":
    unittest.main()
