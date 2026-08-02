"""
tests/test_ch7_74.py — Tests for Chapter 7, task 7.4 (Define Requirements Architecture)

Coverage (75 tests):
  - Utilities: _safe, _repo_path, _architecture_path, _load_repo, _load_architecture,
               _save_architecture, _load_stakeholders, _load_context,
               _find_req, _get_linked_ids, _build_views_from_repo

  - analyze_requirements_architecture: empty repo, auto viewpoints built,
    missing types reported, custom viewpoints included, coverage matrix with BG,
    no BG context (graceful), updates architecture file

  - add_custom_viewpoint: success create, success update, invalid viewpoint_id (spaces),
    viewpoint_id conflicts with standard type, empty label,
    invalid req_ids JSON, empty req_ids list, req_ids not in repo,
    partial not_found, validates all IDs exist, saves to architecture

  - check_architecture_gaps: empty repo, empty viewpoint → info,
    stakeholder without representation → critical,
    no stakeholders file → graceful (info not critical),
    BG not in graph → warning, UC without BP → warning,
    NFR without FR → warning, FR without UC or US → info,
    no gaps → clean verdict, gaps saved to architecture,
    all gap types in one run

  - save_architecture_snapshot: success v1.0, duplicate version rejected,
    empty version rejected, empty repo rejected,
    snapshot added to history (not overwritten),
    multiple snapshots accumulate, notes and author saved,
    summary counts correct, architecture document generated (save_artifact called),
    critical gaps count in result

  - Pipeline: full happy path analyze → custom_viewpoint → gaps → snapshot,
    graceful without stakeholders and context
"""

import json
import os
import sys
import unittest
from datetime import date
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tests.conftest import BaseMCPTest

import skills.requirements_architecture_mcp as mod74
from skills.common import data_path


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def make_req(req_id, req_type, title="Test requirement", status="verified"):
    return {
        "id": req_id,
        "type": req_type,
        "title": title,
        "status": status,
        "priority": "Medium",
        "version": "1.0",
        "added": str(date.today()),
    }


def make_repo(project_id, requirements=None, links=None):
    return {
        "project": project_id,
        "formality_level": "Standard",
        "created": str(date.today()),
        "updated": str(date.today()),
        "requirements": requirements or [],
        "links": links or [],
        "history": [],
    }


def save_repo(repo):
    safe = repo["project"].lower().replace(" ", "_")
    path = os.path.join("governance_plans", "data", f"{safe}_traceability_repo.json")
    os.makedirs(os.path.join("governance_plans", "data"), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)


def load_arch(project_id):
    safe = project_id.lower().replace(" ", "_")
    path = data_path(project_id, f"{safe}_architecture.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def make_stakeholders(project_id, stakeholders=None):
    return {
        "project": project_id,
        "stakeholders": stakeholders or [
            {"id": "SH-001", "name": "Ivanov", "role": "Sponsor"},
            {"id": "SH-002", "name": "Petrova", "role": "User"},
        ],
    }


def save_stakeholders(data):
    safe = data["project"].lower().replace(" ", "_")
    path = os.path.join("governance_plans", "data", f"{safe}_stakeholders.json")
    os.makedirs(os.path.join("governance_plans", "data"), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def make_context(project_id, goals=None):
    return {
        "project_id": project_id,
        "business_goals": goals or [
            {"id": "BG-001", "title": "Reduce processing time", "kpi": "from 24h to 4h"},
            {"id": "BG-002", "title": "Increase NPS", "kpi": "from 45 to 65"},
        ],
        "future_state": "Single window for operators",
        "solution_scope": "In scope: CRM. Out of scope: mobile app",
        "created_at": str(date.today()),
        "updated_at": str(date.today()),
    }


def save_context(ctx):
    safe = ctx["project_id"].lower().replace(" ", "_")
    path = os.path.join("governance_plans", "data", f"{safe}_business_context.json")
    os.makedirs(os.path.join("governance_plans", "data"), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ctx, f, ensure_ascii=False, indent=2)


def make_full_repo(project_id):
    """Repository with all artifact types."""
    reqs = [
        make_req("BP-001", "business_process", "Receive a request from the client"),
        make_req("BP-002", "business_process", "Process the request by an operator"),
        make_req("DD-001", "data_dictionary", "Entity: Request"),
        make_req("ERD-001", "erd", "ERD: Client — Request — Operator"),
        make_req("US-001", "user_story", "As an operator I want to see the queue"),
        make_req("US-002", "user_story", "As a manager I want to see statistics"),
        make_req("UC-001", "use_case", "UC: Assign an operator to a request"),
        make_req("FR-001", "functional", "Automated distribution of requests"),
        make_req("FR-002", "functional", "Notifications on status change"),
        make_req("NFR-001", "non_functional", "Response time < 2 sec"),
        make_req("BR-001", "business_rule", "A request is assigned to the least loaded operator"),
        make_req("BG-001", "business", "Reduce processing time"),
    ]
    links = [
        {"from": "UC-001", "to": "BP-001", "relation": "derives", "added": str(date.today())},
        {"from": "US-001", "to": "FR-001", "relation": "derives", "added": str(date.today())},
        {"from": "NFR-001", "to": "FR-001", "relation": "satisfies", "added": str(date.today())},
        {"from": "FR-001", "to": "BG-001", "relation": "satisfies", "added": str(date.today())},
    ]
    return make_repo(project_id, reqs, links)


# ---------------------------------------------------------------------------
# Utility tests
# ---------------------------------------------------------------------------

class TestUtilities(BaseMCPTest):

    def test_safe_basic(self):
        self.assertEqual(mod74._safe("CRM Upgrade"), "crm_upgrade")

    def test_safe_already_lower(self):
        self.assertEqual(mod74._safe("myproject"), "myproject")

    def test_safe_multiple_spaces(self):
        self.assertEqual(mod74._safe("A B C"), "a_b_c")

    def test_repo_path(self):
        path = mod74._repo_path("CRM Upgrade")
        self.assertIn("crm_upgrade", path)
        self.assertIn("traceability_repo", path)

    def test_architecture_path(self):
        path = mod74._architecture_path("crm_upgrade")
        self.assertIn("crm_upgrade", path)
        self.assertIn("architecture.json", path)

    def test_load_repo_missing(self):
        repo = mod74._load_repo("nonexistent_project")
        self.assertEqual(repo["requirements"], [])
        self.assertEqual(repo["links"], [])

    def test_load_architecture_missing_returns_default(self):
        arch = mod74._load_architecture("no_arch_project")
        self.assertIn("viewpoints", arch)
        self.assertIn("views", arch)
        self.assertIn("snapshots", arch)
        self.assertEqual(arch["snapshots"], [])

    def test_save_and_load_architecture(self):
        arch = mod74._load_architecture("save_test")
        arch["viewpoints"]["custom_test"] = {"label": "Test", "auto": False, "req_ids": ["FR-001"]}
        mod74._save_architecture(arch)
        loaded = mod74._load_architecture("save_test")
        self.assertIn("custom_test", loaded["viewpoints"])

    def test_load_stakeholders_missing_returns_none(self):
        result = mod74._load_stakeholders("no_stakeholders_project")
        self.assertIsNone(result)

    def test_load_context_missing_returns_none(self):
        result = mod74._load_context("no_context_project")
        self.assertIsNone(result)

    def test_find_req_found(self):
        repo = make_repo("p", [make_req("FR-001", "functional")])
        found = mod74._find_req(repo, "FR-001")
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], "FR-001")

    def test_find_req_not_found(self):
        repo = make_repo("p", [make_req("FR-001", "functional")])
        found = mod74._find_req(repo, "FR-999")
        self.assertIsNone(found)

    def test_get_linked_ids_both_directions(self):
        repo = make_repo("p", [], [
            {"from": "UC-001", "to": "BP-001", "relation": "derives", "added": str(date.today())},
        ])
        # UC-001 → BP-001
        linked_from_uc = mod74._get_linked_ids(repo, "UC-001")
        self.assertIn("BP-001", linked_from_uc)
        # BP-001 ← UC-001 (reverse direction)
        linked_from_bp = mod74._get_linked_ids(repo, "BP-001")
        self.assertIn("UC-001", linked_from_bp)

    def test_get_linked_ids_with_filter(self):
        repo = make_repo("p", [], [
            {"from": "NFR-001", "to": "FR-001", "relation": "satisfies", "added": str(date.today())},
            {"from": "TC-001", "to": "FR-001", "relation": "verifies", "added": str(date.today())},
        ])
        linked = mod74._get_linked_ids(repo, "FR-001", relation_filter={"satisfies"})
        self.assertIn("NFR-001", linked)
        self.assertNotIn("TC-001", linked)

    def test_build_views_from_repo_maps_types(self):
        repo = make_repo("p", [
            make_req("BP-001", "business_process"),
            make_req("FR-001", "functional"),
            make_req("US-001", "user_story"),
            make_req("BG-001", "business"),   # should be skipped
            make_req("TC-001", "test"),        # should be skipped
        ])
        views = mod74._build_views_from_repo(repo)
        self.assertIn("business_process", views)
        self.assertIn("BP-001", views["business_process"])
        self.assertIn("functional", views)
        self.assertIn("FR-001", views["functional"])
        self.assertIn("user_story", views)
        self.assertNotIn("business", views)
        self.assertNotIn("test", views)


# ---------------------------------------------------------------------------
# analyze_requirements_architecture tests
# ---------------------------------------------------------------------------

class TestAnalyzeRequirementsArchitecture(BaseMCPTest):

    def test_empty_repo_returns_warning(self):
        result = mod74.analyze_requirements_architecture("empty_proj")
        self.assertIn("empty", result)

    def test_builds_auto_viewpoints(self):
        repo = make_full_repo("crm")
        save_repo(repo)
        result = mod74.analyze_requirements_architecture("crm")
        self.assertIn("Business processes", result)
        self.assertIn("Functionality", result)
        self.assertIn("Users and interaction", result)
        self.assertIn("Data and information", result)
        self.assertIn("Business rules", result)

    def test_reports_missing_types(self):
        # Only BP — the other types should be in "missing"
        repo = make_repo("partial", [make_req("BP-001", "business_process")])
        save_repo(repo)
        result = mod74.analyze_requirements_architecture("partial")
        self.assertIn("Missing", result)

    def test_no_missing_when_all_types_present(self):
        repo = make_full_repo("full")
        save_repo(repo)
        result = mod74.analyze_requirements_architecture("full")
        # With all types present — the missing section should not contain all of them
        # (it may be empty or contain not all types)
        arch = load_arch("full")
        self.assertIn("business_process", arch["views"])
        self.assertIn("functional", arch["views"])

    def test_includes_custom_viewpoints_from_existing_arch(self):
        repo = make_repo("proj", [make_req("FR-001", "functional")])
        save_repo(repo)
        # Pre-create a custom viewpoint in the architecture
        arch = mod74._load_architecture("proj")
        arch["viewpoints"]["security"] = {
            "label": "Security", "auto": False,
            "req_ids": ["FR-001"], "description": "Test",
        }
        mod74._save_architecture(arch)
        result = mod74.analyze_requirements_architecture("proj")
        self.assertIn("Custom viewpoints", result)
        self.assertIn("security", result)

    def test_coverage_matrix_shown_when_context_exists(self):
        repo = make_full_repo("ctx_proj")
        save_repo(repo)
        save_context(make_context("ctx_proj"))
        result = mod74.analyze_requirements_architecture("ctx_proj")
        self.assertIn("Coverage Matrix", result)
        self.assertIn("BG-001", result)

    def test_no_coverage_matrix_without_context(self):
        repo = make_full_repo("no_ctx")
        save_repo(repo)
        result = mod74.analyze_requirements_architecture("no_ctx")
        # Without business_context — no matrix
        self.assertNotIn("Coverage Matrix", result)

    def test_updates_architecture_file(self):
        repo = make_repo("arch_file", [make_req("BP-001", "business_process")])
        save_repo(repo)
        mod74.analyze_requirements_architecture("arch_file")
        arch = load_arch("arch_file")
        self.assertIn("business_process", arch["viewpoints"])
        self.assertIn("business_process", arch["views"])
        self.assertIn("BP-001", arch["views"]["business_process"])

    def test_req_ids_in_views(self):
        repo = make_repo("view_ids", [
            make_req("FR-001", "functional"),
            make_req("FR-002", "functional"),
        ])
        save_repo(repo)
        mod74.analyze_requirements_architecture("view_ids")
        arch = load_arch("view_ids")
        self.assertIn("FR-001", arch["views"]["functional"])
        self.assertIn("FR-002", arch["views"]["functional"])


# ---------------------------------------------------------------------------
# add_custom_viewpoint tests
# ---------------------------------------------------------------------------

class TestAddCustomViewpoint(BaseMCPTest):

    def _setup_repo_with_reqs(self, project_id):
        repo = make_repo(project_id, [
            make_req("FR-001", "functional"),
            make_req("NFR-001", "non_functional"),
            make_req("BR-001", "business_rule"),
        ])
        save_repo(repo)

    def test_success_create(self):
        self._setup_repo_with_reqs("sec_proj")
        result = mod74.add_custom_viewpoint(
            project_id="sec_proj",
            viewpoint_id="security",
            label="Security and access",
            req_ids_json='["FR-001", "NFR-001"]',
            description="Security requirements",
            stakeholder_roles="CISO",
        )
        self.assertIn("created", result)
        self.assertIn("security", result)
        arch = load_arch("sec_proj")
        self.assertIn("security", arch["viewpoints"])
        self.assertEqual(arch["viewpoints"]["security"]["auto"], False)
        self.assertIn("FR-001", arch["viewpoints"]["security"]["req_ids"])

    def test_success_update(self):
        self._setup_repo_with_reqs("upd_proj")
        mod74.add_custom_viewpoint(
            project_id="upd_proj",
            viewpoint_id="audit",
            label="Audit",
            req_ids_json='["BR-001"]',
        )
        result = mod74.add_custom_viewpoint(
            project_id="upd_proj",
            viewpoint_id="audit",
            label="Audit and compliance",
            req_ids_json='["BR-001", "FR-001"]',
        )
        self.assertIn("updated", result)
        arch = load_arch("upd_proj")
        self.assertIn("FR-001", arch["viewpoints"]["audit"]["req_ids"])

    def test_invalid_viewpoint_id_with_spaces(self):
        self._setup_repo_with_reqs("space_proj")
        result = mod74.add_custom_viewpoint(
            project_id="space_proj",
            viewpoint_id="my security",
            label="Security",
            req_ids_json='["FR-001"]',
        )
        self.assertIn("❌", result)
        self.assertIn("space", result.lower())

    def test_viewpoint_id_conflicts_with_standard_type(self):
        self._setup_repo_with_reqs("conflict_proj")
        result = mod74.add_custom_viewpoint(
            project_id="conflict_proj",
            viewpoint_id="functional",
            label="Custom functionality",
            req_ids_json='["FR-001"]',
        )
        self.assertIn("❌", result)
        self.assertIn("standard", result)

    def test_empty_label(self):
        self._setup_repo_with_reqs("lbl_proj")
        result = mod74.add_custom_viewpoint(
            project_id="lbl_proj",
            viewpoint_id="custom",
            label="",
            req_ids_json='["FR-001"]',
        )
        self.assertIn("❌", result)
        self.assertIn("label", result)

    def test_invalid_req_ids_json(self):
        self._setup_repo_with_reqs("json_proj")
        result = mod74.add_custom_viewpoint(
            project_id="json_proj",
            viewpoint_id="custom",
            label="Test",
            req_ids_json='not-json',
        )
        self.assertIn("❌", result)

    def test_empty_req_ids_list(self):
        self._setup_repo_with_reqs("empty_ids_proj")
        result = mod74.add_custom_viewpoint(
            project_id="empty_ids_proj",
            viewpoint_id="custom",
            label="Test",
            req_ids_json='[]',
        )
        self.assertIn("❌", result)

    def test_req_ids_not_in_repo(self):
        self._setup_repo_with_reqs("notfound_proj")
        result = mod74.add_custom_viewpoint(
            project_id="notfound_proj",
            viewpoint_id="custom",
            label="Test",
            req_ids_json='["XX-999", "YY-000"]',
        )
        self.assertIn("❌", result)
        self.assertIn("XX-999", result)

    def test_partial_not_found_blocks_save(self):
        self._setup_repo_with_reqs("partial_proj")
        result = mod74.add_custom_viewpoint(
            project_id="partial_proj",
            viewpoint_id="custom",
            label="Test",
            req_ids_json='["FR-001", "XX-999"]',
        )
        self.assertIn("❌", result)
        # The architecture file must not contain this viewpoint
        arch = mod74._load_architecture("partial_proj")
        self.assertNotIn("custom", arch["viewpoints"])

    def test_views_updated_after_add(self):
        self._setup_repo_with_reqs("views_upd")
        mod74.add_custom_viewpoint(
            project_id="views_upd",
            viewpoint_id="migration",
            label="Data migration",
            req_ids_json='["FR-001", "NFR-001"]',
        )
        arch = load_arch("views_upd")
        self.assertIn("migration", arch["views"])
        self.assertIn("FR-001", arch["views"]["migration"])


# ---------------------------------------------------------------------------
# check_architecture_gaps tests
# ---------------------------------------------------------------------------

class TestCheckArchitectureGaps(BaseMCPTest):

    def test_empty_repo_returns_warning(self):
        result = mod74.check_architecture_gaps("empty_gaps")
        self.assertIn("empty", result)

    def test_empty_viewpoint_info_gap(self):
        # Only FR — no BP, UC, etc. → empty viewpoints as info
        repo = make_repo("info_gaps", [make_req("FR-001", "functional")])
        save_repo(repo)
        result = mod74.check_architecture_gaps("info_gaps")
        self.assertIn("Info", result)

    def test_no_stakeholders_file_graceful(self):
        repo = make_repo("no_sh", [make_req("FR-001", "functional")])
        save_repo(repo)
        # No stakeholders file — must not crash, info message
        result = mod74.check_architecture_gaps("no_sh")
        self.assertNotIn("❌ Error", result)
        self.assertIn("Stakeholder registry", result)

    def test_bg_not_in_graph_warning(self):
        # BG in business_context but not as a node in the 5.1 repository
        repo = make_repo("bg_gap", [make_req("FR-001", "functional")])
        save_repo(repo)
        save_context(make_context("bg_gap"))
        result = mod74.check_architecture_gaps("bg_gap")
        self.assertIn("Warning", result)
        self.assertIn("BG-001", result)

    def test_bg_in_graph_no_warning(self):
        # BG exists as a node in the repository → no BG warning
        repo = make_repo("bg_ok", [
            make_req("FR-001", "functional"),
            make_req("BG-001", "business", "Reduce processing time"),
        ])
        save_repo(repo)
        save_context(make_context("bg_ok", goals=[
            {"id": "BG-001", "title": "Reduce processing time", "kpi": ""}
        ]))
        result = mod74.check_architecture_gaps("bg_ok")
        # There should be no warning about BG-001 not being in the graph
        self.assertNotIn("BG-001` (", result.split("Warning")[1] if "Warning" in result else result)

    def test_uc_without_bp_warning(self):
        # UC with no link to BP → warning
        repo = make_repo("uc_gap", [
            make_req("UC-001", "use_case", "UC without BP"),
            make_req("BP-001", "business_process", "Process"),
        ])
        # No UC→BP links
        save_repo(repo)
        result = mod74.check_architecture_gaps("uc_gap")
        self.assertIn("UC-001", result)
        self.assertIn("Warning", result)

    def test_uc_with_bp_no_warning(self):
        # UC linked to BP → no warning
        links = [{"from": "UC-001", "to": "BP-001", "relation": "derives", "added": str(date.today())}]
        repo = make_repo("uc_ok", [
            make_req("UC-001", "use_case", "UC with BP"),
            make_req("BP-001", "business_process", "Process"),
        ], links)
        save_repo(repo)
        result = mod74.check_architecture_gaps("uc_ok")
        # UC-001 must not appear in a warning about UC without BP
        if "UC-001" in result:
            # Make sure it is not the uc_without_bp warning
            self.assertNotIn("is not linked to any Business Process", result)

    def test_nfr_without_fr_warning(self):
        links = []  # No links
        repo = make_repo("nfr_gap", [
            make_req("NFR-001", "non_functional", "Performance"),
            make_req("FR-001", "functional", "Function"),
        ], links)
        save_repo(repo)
        result = mod74.check_architecture_gaps("nfr_gap")
        self.assertIn("NFR-001", result)
        self.assertIn("Warning", result)

    def test_nfr_with_fr_no_warning(self):
        links = [{"from": "NFR-001", "to": "FR-001", "relation": "satisfies", "added": str(date.today())}]
        repo = make_repo("nfr_ok", [
            make_req("NFR-001", "non_functional", "Performance"),
            make_req("FR-001", "functional", "Function"),
        ], links)
        save_repo(repo)
        result = mod74.check_architecture_gaps("nfr_ok")
        # NFR-001 not in a gap
        self.assertNotIn("NFR-001` — NFR", result)

    def test_fr_without_uc_us_info(self):
        # FR without UC or US → info
        repo = make_repo("fr_gap", [
            make_req("FR-001", "functional", "Function without a scenario"),
        ])
        save_repo(repo)
        result = mod74.check_architecture_gaps("fr_gap")
        self.assertIn("FR-001", result)
        self.assertIn("Info", result)

    def test_fr_with_us_no_info(self):
        links = [{"from": "US-001", "to": "FR-001", "relation": "derives", "added": str(date.today())}]
        repo = make_repo("fr_us_ok", [
            make_req("FR-001", "functional"),
            make_req("US-001", "user_story"),
        ], links)
        save_repo(repo)
        result = mod74.check_architecture_gaps("fr_us_ok")
        # FR-001 must not appear in an info about FR without a scenario
        if "FR-001" in result and "Info" in result:
            # Make sure it is not our info about FR without a scenario
            self.assertNotIn("FR-001` — FR", result)

    def test_no_gaps_clean_verdict(self):
        # Full repository with proper links — no critical gaps
        repo = make_full_repo("clean_proj")
        save_repo(repo)
        result = mod74.check_architecture_gaps("clean_proj")
        # Critical = 0, verdict without critical gaps
        self.assertIn("No critical gaps", result)
        self.assertIn("Critical | 0", result)

    def test_gaps_saved_to_architecture(self):
        repo = make_repo("save_gaps", [make_req("NFR-001", "non_functional")])
        save_repo(repo)
        mod74.check_architecture_gaps("save_gaps")
        arch = load_arch("save_gaps")
        self.assertIn("gaps", arch)
        # NFR without FR → warning → must be in gaps
        self.assertTrue(len(arch["gaps"]["warning"]) > 0)

    def test_all_gap_types_in_one_run(self):
        # Repo with UC without BP (warning), NFR without FR (warning), FR without UC (info)
        repo = make_repo("all_gaps", [
            make_req("UC-001", "use_case"),
            make_req("NFR-001", "non_functional"),
            make_req("FR-001", "functional"),
        ])
        save_repo(repo)
        result = mod74.check_architecture_gaps("all_gaps")
        self.assertIn("Warning", result)
        self.assertIn("Info", result)


# ---------------------------------------------------------------------------
# save_architecture_snapshot tests
# ---------------------------------------------------------------------------

class TestSaveArchitectureSnapshot(BaseMCPTest):

    def test_empty_repo_rejected(self):
        result = mod74.save_architecture_snapshot("empty_snap", "v1.0")
        self.assertIn("empty", result.lower())

    def test_empty_version_rejected(self):
        repo = make_repo("ver_proj", [make_req("FR-001", "functional")])
        save_repo(repo)
        result = mod74.save_architecture_snapshot("ver_proj", "")
        self.assertIn("❌", result)
        self.assertIn("version", result)

    def test_success_v1(self):
        repo = make_full_repo("snap_proj")
        save_repo(repo)
        result = mod74.save_architecture_snapshot("snap_proj", "v1.0", "First version", "Ivanov")
        self.assertIn("v1.0", result)
        self.assertIn("recorded", result)

    def test_snapshot_added_to_history(self):
        repo = make_full_repo("hist_proj")
        save_repo(repo)
        mod74.save_architecture_snapshot("hist_proj", "v1.0")
        arch = load_arch("hist_proj")
        self.assertEqual(len(arch["snapshots"]), 1)
        self.assertEqual(arch["snapshots"][0]["version"], "v1.0")

    def test_multiple_snapshots_accumulate(self):
        repo = make_full_repo("multi_snap")
        save_repo(repo)
        mod74.save_architecture_snapshot("multi_snap", "v1.0")
        mod74.save_architecture_snapshot("multi_snap", "v1.1", "UCs added")
        arch = load_arch("multi_snap")
        self.assertEqual(len(arch["snapshots"]), 2)
        versions = [s["version"] for s in arch["snapshots"]]
        self.assertIn("v1.0", versions)
        self.assertIn("v1.1", versions)

    def test_duplicate_version_rejected(self):
        repo = make_full_repo("dup_proj")
        save_repo(repo)
        mod74.save_architecture_snapshot("dup_proj", "v1.0")
        result = mod74.save_architecture_snapshot("dup_proj", "v1.0")
        self.assertIn("⚠️", result)
        self.assertIn("already exists", result)
        # The second snapshot is not added
        arch = load_arch("dup_proj")
        v1_count = sum(1 for s in arch["snapshots"] if s["version"] == "v1.0")
        self.assertEqual(v1_count, 1)

    def test_notes_and_author_saved(self):
        repo = make_full_repo("notes_proj")
        save_repo(repo)
        mod74.save_architecture_snapshot("notes_proj", "v1.0", "First baseline", "Petrova")
        arch = load_arch("notes_proj")
        snap = arch["snapshots"][0]
        self.assertEqual(snap["notes"], "First baseline")
        self.assertEqual(snap["author"], "Petrova")

    def test_summary_counts_correct(self):
        repo = make_full_repo("counts_proj")
        save_repo(repo)
        mod74.save_architecture_snapshot("counts_proj", "v1.0")
        arch = load_arch("counts_proj")
        snap = arch["snapshots"][0]
        # total_reqs > 0 (full_repo has many req, excluding business and test)
        self.assertGreater(snap["summary"]["total_reqs"], 0)
        self.assertGreater(snap["summary"]["viewpoints_count"], 0)

    def test_save_artifact_called(self):
        """save_artifact is called when creating a snapshot."""
        repo = make_full_repo("artifact_proj")
        save_repo(repo)
        calls = []
        original = mod74.save_artifact
        mod74.save_artifact = lambda content, prefix="", project_id=None: calls.append(prefix) or "✅"
        try:
            mod74.save_architecture_snapshot("artifact_proj", "v1.0")
        finally:
            mod74.save_artifact = original
        self.assertTrue(any("7_4" in str(c) for c in calls))

    def test_critical_gaps_warning_in_result(self):
        # First create gaps with critical
        repo = make_repo("crit_proj", [make_req("FR-001", "functional")])
        save_repo(repo)
        save_stakeholders(make_stakeholders("crit_proj"))
        mod74.check_architecture_gaps("crit_proj")
        result = mod74.save_architecture_snapshot("crit_proj", "v1.0")
        # If there are critical gaps — a warning in the result
        arch = load_arch("crit_proj")
        if arch["gaps"].get("critical"):
            self.assertIn("critical", result.lower())

    def test_architecture_doc_contains_viewpoints_section(self):
        """The Architecture Document contains a Viewpoints section."""
        doc_content = []
        original = mod74.save_artifact
        mod74.save_artifact = lambda content, prefix="", project_id=None: doc_content.append(content) or "✅"
        try:
            repo = make_full_repo("doc_proj")
            save_repo(repo)
            mod74.save_architecture_snapshot("doc_proj", "v1.0")
        finally:
            mod74.save_artifact = original
        self.assertTrue(len(doc_content) > 0)
        self.assertIn("Viewpoints", doc_content[0])

    def test_architecture_doc_contains_delivery_section(self):
        """The Architecture Document contains a handoff section to 4.4 and 7.5."""
        doc_content = []
        original = mod74.save_artifact
        mod74.save_artifact = lambda content, prefix="", project_id=None: doc_content.append(content) or "✅"
        try:
            repo = make_full_repo("delivery_proj")
            save_repo(repo)
            mod74.save_architecture_snapshot("delivery_proj", "v1.0")
        finally:
            mod74.save_artifact = original
        self.assertTrue(len(doc_content) > 0)
        self.assertIn("4.4", doc_content[0])
        self.assertIn("7.5", doc_content[0])


# ---------------------------------------------------------------------------
# Pipeline — full scenario
# ---------------------------------------------------------------------------

class TestPipeline(BaseMCPTest):

    def test_full_happy_path(self):
        """
        Full pipeline: analyze → add_custom_viewpoint → check_gaps → snapshot.
        All steps run without errors.
        """
        project_id = "pipeline_proj"
        repo = make_full_repo(project_id)
        save_repo(repo)
        save_context(make_context(project_id))
        save_stakeholders(make_stakeholders(project_id))

        # Step 1: analyze
        r1 = mod74.analyze_requirements_architecture(project_id)
        self.assertIn("Business processes", r1)
        self.assertNotIn("empty", r1)

        # Step 2: add_custom_viewpoint
        r2 = mod74.add_custom_viewpoint(
            project_id=project_id,
            viewpoint_id="security",
            label="Security",
            req_ids_json='["NFR-001"]',
            description="Non-functional security requirements",
        )
        self.assertIn("created", r2)

        # Step 3: check_gaps
        r3 = mod74.check_architecture_gaps(project_id)
        self.assertNotIn("❌ Error", r3)

        # Step 4: snapshot
        r4 = mod74.save_architecture_snapshot(project_id, "v1.0", "After full analysis")
        self.assertIn("v1.0", r4)
        self.assertIn("recorded", r4)

        # Check the final architecture file
        arch = load_arch(project_id)
        self.assertEqual(len(arch["snapshots"]), 1)
        self.assertIn("security", arch["viewpoints"])
        self.assertIn("business_process", arch["viewpoints"])

    def test_graceful_without_stakeholders_and_context(self):
        """
        Pipeline without a stakeholder registry and business_context — does not crash.
        """
        project_id = "minimal_proj"
        repo = make_repo(project_id, [
            make_req("FR-001", "functional"),
            make_req("US-001", "user_story"),
        ])
        save_repo(repo)

        r1 = mod74.analyze_requirements_architecture(project_id)
        self.assertNotIn("❌ Error", r1)

        r2 = mod74.check_architecture_gaps(project_id)
        self.assertNotIn("❌ Error", r2)
        # No stakeholders file → info, not critical
        self.assertIn("Stakeholder registry", r2)

        r3 = mod74.save_architecture_snapshot(project_id, "v1.0")
        self.assertIn("v1.0", r3)

    def test_custom_viewpoint_in_snapshot(self):
        """A custom viewpoint is visible in the Architecture Document."""
        project_id = "custom_snap_proj"
        repo = make_repo(project_id, [
            make_req("FR-001", "functional"),
            make_req("NFR-001", "non_functional"),
        ])
        save_repo(repo)

        mod74.add_custom_viewpoint(
            project_id=project_id,
            viewpoint_id="compliance",
            label="Regulatory compliance",
            req_ids_json='["NFR-001"]',
        )

        doc_content = []
        original = mod74.save_artifact
        mod74.save_artifact = lambda content, prefix="", project_id=None: doc_content.append(content) or "✅"
        try:
            mod74.save_architecture_snapshot(project_id, "v1.0")
        finally:
            mod74.save_artifact = original

        self.assertTrue(len(doc_content) > 0)
        self.assertIn("Regulatory compliance", doc_content[0])
        self.assertIn("custom", doc_content[0])


# ---------------------------------------------------------------------------
# 7.4 audit regression (2026-07-19): stakeholder-registry filename contract (4.2)
# and 6.1/6.2 business-goal node types.
# ---------------------------------------------------------------------------

def save_stakeholder_registry(project_id, stakeholders=None):
    """Writes the registry under the REAL 4.2 filename (*_stakeholder_registry.json)."""
    safe = project_id.lower().replace(" ", "_")
    path = os.path.join("governance_plans", "data", f"{safe}_stakeholder_registry.json")
    os.makedirs(os.path.join("governance_plans", "data"), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"project": project_id, "stakeholders": stakeholders or
                   [{"name": "Head of Sales", "role": "Sponsor"}], "history": []}, f)
    return path


class TestArchAuditRegressions(BaseMCPTest):

    def test_load_stakeholders_from_registry_filename(self):
        save_stakeholder_registry("reg74")
        result = mod74._load_stakeholders("reg74")
        self.assertIsNotNone(result)
        self.assertEqual(result["stakeholders"][0]["name"], "Head of Sales")

    def test_gaps_finds_stakeholder_registry(self):
        save_repo(make_repo("reg74b", [make_req("FR-001", "functional", "Auto routing")]))
        save_stakeholder_registry("reg74b")
        result = mod74.check_architecture_gaps("reg74b")
        self.assertNotIn("registry not found", result.lower())

    def test_analyze_excludes_business_goal_from_total(self):
        save_repo(make_repo("bg74", [
            make_req("FR-001", "functional", "Auto routing"),
            make_req("BG-001", "business_goal", "Reduce waiting", status="confirmed"),
        ], links=[{"from": "FR-001", "to": "BG-001", "relation": "derives"}]))
        result = mod74.analyze_requirements_architecture("bg74")
        self.assertIn("**Total active req:** 1", result)

    def test_gaps_recognizes_business_goal_node_in_graph(self):
        save_repo(make_repo("bg74c", [
            make_req("FR-001", "functional", "Auto routing"),
            make_req("BG-001", "business_goal", "Reduce waiting", status="confirmed"),
        ], links=[{"from": "FR-001", "to": "BG-001", "relation": "derives"}]))
        save_context(make_context("bg74c", goals=[{"id": "BG-001", "title": "Reduce waiting"}]))
        result = mod74.check_architecture_gaps("bg74c")
        self.assertNotIn("not represented as a node", result)


class TestStakeholderRepresentationCountsOwner(BaseMCPTest):
    """The representation check matched only title WORDS (the node `stakeholders`
    field is written by no producer), so the OWNER of a requirement — the person
    most concretely tied to it — was reported as a critical "not represented" gap
    (reproduced live: the owner of FR-102 was flagged). The owner field now counts,
    and the gap message names its heuristic method instead of implying a real
    stakeholder↔requirement model."""

    def test_requirement_owner_is_represented(self):
        repo = make_repo("own74", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["owner"] = "David Kim"
        save_repo(repo)
        save_stakeholder_registry(
            "own74",
            [{"name": "David Kim", "role": "SIU Fraud Investigator"}])
        result = mod74.check_architecture_gaps("own74")
        self.assertNotIn("David Kim", result.split("## ")[0] if "## " in result else result)
        self.assertNotIn("`David Kim` is not named", result)

    def test_uncovered_stakeholder_gap_names_its_method(self):
        save_repo(make_repo("own74b", [make_req("FR-001", "functional", "Auto routing")]))
        save_stakeholder_registry(
            "own74b",
            [{"name": "Priya Nair", "role": "Compliance Officer"}])
        result = mod74.check_architecture_gaps("own74b")
        self.assertIn("Priya Nair", result)
        self.assertIn("heuristic", result,
                      "the verdict must say HOW it looked (owner + title words)")


class TestDeclaredConcernsReadBothForms(BaseMCPTest):
    """The field is written as objects and READ in two forms.

    The bare string is what the previous reader understood (`str(sh).lower()`), so a
    repository written by an older build — or by a human editing JSON — must keep
    rendering. And a missing key, an explicit null and a non-list are THREE different
    inputs: `.get(k, default)` is the border between the first two, and it is exactly
    the border a `del`-only fixture never tests.
    """

    def test_the_object_form_yields_the_name(self):
        req = {"id": "FR-001", "stakeholders": [
            {"name": "Sales Head", "declared": "2026-08-01", "note": "revenue"}]}
        self.assertEqual(mod74._declared_concerns(req), ["Sales Head"])

    def test_the_bare_string_form_still_reads(self):
        req = {"id": "FR-001", "stakeholders": ["Sales Head"]}
        self.assertEqual(mod74._declared_concerns(req), ["Sales Head"])

    def test_both_forms_in_one_list_read_together(self):
        req = {"id": "FR-001", "stakeholders": [
            "Sales Head", {"name": "Data Architect"}]}
        self.assertEqual(mod74._declared_concerns(req), ["Sales Head", "Data Architect"])

    def test_a_missing_key_yields_nothing(self):
        self.assertEqual(mod74._declared_concerns({"id": "FR-001"}), [])

    def test_an_explicit_null_yields_nothing_and_does_not_raise(self):
        # NOT the same fixture as the one above: `.get(k, default)` protects against
        # the missing key and does nothing about a key holding None.
        self.assertEqual(mod74._declared_concerns({"id": "FR-001", "stakeholders": None}), [])

    def test_a_non_list_value_yields_nothing_and_does_not_raise(self):
        self.assertEqual(
            mod74._declared_concerns({"id": "FR-001", "stakeholders": "Sales Head"}), [])
        self.assertEqual(
            mod74._declared_concerns({"id": "FR-001", "stakeholders": {"name": "X"}}), [])

    def test_unreadable_entries_are_skipped_not_stringified(self):
        # `str(entry)` on a number would put "42" into a signed document as a person.
        req = {"id": "FR-001", "stakeholders": [42, None, {"role": "no name key"},
                                                {"name": ""}, "Real Person"]}
        self.assertEqual(mod74._declared_concerns(req), ["Real Person"])

    def test_duplicates_collapse_by_normalised_identity(self):
        req = {"id": "FR-001", "stakeholders": [
            "Sales Head", {"name": "  sales   head "}, "SALES HEAD"]}
        self.assertEqual(mod74._declared_concerns(req), ["Sales Head"])


class TestEvidenceHasFourNamedSources(BaseMCPTest):
    """Every tie carries WHERE it came from, and nothing is copied.

    `owner` belongs to 7.1 and the votes belong to 5.5. A copy of either would go
    stale the moment its owner changed it — so both are computed on read and the
    stored field holds only what the BA declared.
    """

    def _write_approvals(self, project_id, packages):
        safe = project_id.lower().replace(" ", "_")
        path = os.path.join("governance_plans", "data",
                            f"{safe}_approval_history.json")
        os.makedirs(os.path.join("governance_plans", "data"), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"project": project_id, "packages": packages}, f)

    def test_a_declared_name_is_evidence_labelled_declared(self):
        repo = make_repo("ev74", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["stakeholders"] = [{"name": "Sales Head"}]
        ev = mod74._stakeholder_evidence("ev74", repo)
        # `archived` travels WITH the tie (branch review B-2) rather than being looked
        # up again by each consumer, so the gap report and the document cannot disagree
        # about which ties are live. Asserted in full, not by subset: a field that
        # silently stops being written is exactly what a subset assertion hides.
        self.assertEqual(ev["FR-001"], [{"who": "Sales Head", "source": "declared",
                                         "archived": False, "note": ""}])

    def test_the_owner_is_evidence_labelled_with_its_chapter(self):
        repo = make_repo("ev74b", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["owner"] = "Ivan Petrov"
        ev = mod74._stakeholder_evidence("ev74b", repo)
        self.assertEqual(ev["FR-001"], [{"who": "Ivan Petrov", "source": "7.1:owner",
                                         "archived": False, "note": ""}])

    def test_the_note_travels_with_the_declaration(self):
        # `note` was a write-only field until branch review B-4: stored, invited by the
        # docstring, read by nobody. It rides with the tie so the document can print it.
        repo = make_repo("ev74n", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["stakeholders"] = [
            {"name": "Sales Head", "note": "owns the revenue report"}]
        ev = mod74._stakeholder_evidence("ev74n", repo)
        self.assertEqual(ev["FR-001"], [{"who": "Sales Head", "source": "declared",
                                         "archived": False,
                                         "note": "owns the revenue report"}])

    def test_the_archived_flag_follows_the_requirement_status(self):
        repo = make_repo("ev74m", [
            make_req("FR-001", "functional", "Old feature", status="deprecated")])
        repo["requirements"][0]["stakeholders"] = [{"name": "Sales Head"}]
        ev = mod74._stakeholder_evidence("ev74m", repo)
        self.assertEqual(ev["FR-001"], [{"who": "Sales Head", "source": "declared",
                                         "archived": True, "note": ""}])

    def test_a_5_5_vote_on_this_requirement_is_evidence(self):
        self._write_approvals("ev74c", {"PKG-001": {"req_ids": ["FR-001"],
            "stakeholder_decisions": {"Priya Nair": {"raci": "accountable",
                "req_decisions": [{"req_id": "FR-001", "decision": "approved"}]}}}})
        repo = make_repo("ev74c", [make_req("FR-001", "functional", "Auto routing")])
        ev = mod74._stakeholder_evidence("ev74c", repo)
        self.assertEqual(ev["FR-001"], [{"who": "Priya Nair", "source": "5.5:approval",
                                         "archived": False, "note": ""}])

    def test_a_rejection_counts_as_interest_too(self):
        # Interest is not agreement: someone who voted AGAINST a requirement is the
        # clearest possible evidence that it touches them.
        self._write_approvals("ev74d", {"PKG-001": {"req_ids": ["FR-001"],
            "stakeholder_decisions": {"Priya Nair": {"raci": "accountable",
                "req_decisions": [{"req_id": "FR-001", "decision": "rejected",
                                   "rejection_reason": "too costly"}]}}}})
        repo = make_repo("ev74d", [make_req("FR-001", "functional", "Auto routing")])
        ev = mod74._stakeholder_evidence("ev74d", repo)
        self.assertEqual([e["who"] for e in ev["FR-001"]], ["Priya Nair"])

    def test_a_vote_on_a_different_requirement_is_not_evidence_for_this_one(self):
        self._write_approvals("ev74e", {"PKG-001": {"req_ids": ["FR-002"],
            "stakeholder_decisions": {"Priya Nair": {"raci": "consulted",
                "req_decisions": [{"req_id": "FR-002", "decision": "approved"}]}}}})
        repo = make_repo("ev74e", [make_req("FR-001", "functional", "Auto routing"),
                                   make_req("FR-002", "functional", "Notifications")])
        ev = mod74._stakeholder_evidence("ev74e", repo)
        self.assertEqual(ev["FR-001"], [])
        self.assertEqual([e["who"] for e in ev["FR-002"]], ["Priya Nair"])

    def test_no_approval_file_degrades_to_the_other_sources(self):
        repo = make_repo("ev74f", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["owner"] = "Ivan Petrov"
        ev = mod74._stakeholder_evidence("ev74f", repo)
        self.assertEqual([e["source"] for e in ev["FR-001"]], ["7.1:owner"])

    def test_a_damaged_approval_file_does_not_take_the_tool_down(self):
        safe = "ev74g"
        path = os.path.join("governance_plans", "data", f"{safe}_approval_history.json")
        os.makedirs(os.path.join("governance_plans", "data"), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("{not json at all")
        repo = make_repo("ev74g", [make_req("FR-001", "functional", "Auto routing")])
        self.assertEqual(mod74._stakeholder_evidence("ev74g", repo)["FR-001"], [])

    def test_an_approval_file_whose_packages_is_a_list_does_not_raise(self):
        # A top level that is valid JSON but the wrong SHAPE.
        #
        # This asserts the ROUTE, not the packages-level guard: `load_approval_history`
        # validates two levels and returns None for this file, so execution stops at
        # `isinstance(history, dict)` and never reaches the guard the comment used to
        # claim it covered (branch review A-5; the same reason mutating that guard
        # leaves the suite green, recorded as T3-1). The route is worth pinning on its
        # own — it is the one a real project takes.
        self._write_approvals("ev74h", ["PKG-001"])
        repo = make_repo("ev74h", [make_req("FR-001", "functional", "Auto routing")])
        self.assertEqual(mod74._stakeholder_evidence("ev74h", repo)["FR-001"], [])

    def test_a_non_dict_packages_reaching_the_reader_directly_is_still_guarded(self):
        # And THIS one reaches the guard. `_approval_voters` is defence in depth for
        # the day something calls it without going through the shared reader, so the
        # test has to bypass the reader the same way that caller would.
        with patch.object(mod74, "load_approval_history",
                          return_value={"packages": ["PKG-001"]}):
            self.assertEqual(mod74._approval_voters("ev74h2"), {})
        with patch.object(mod74, "load_approval_history", return_value="not a dict"):
            self.assertEqual(mod74._approval_voters("ev74h3"), {})

    def test_the_same_person_from_two_sources_is_kept_twice_with_both_labels(self):
        # NOT deduped across sources: "declared AND voted in 5.5" is stronger evidence
        # than either alone, and the document is entitled to show both.
        self._write_approvals("ev74i", {"PKG-001": {"req_ids": ["FR-001"],
            "stakeholder_decisions": {"Sales Head": {"raci": "accountable",
                "req_decisions": [{"req_id": "FR-001", "decision": "approved"}]}}}})
        repo = make_repo("ev74i", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["stakeholders"] = [{"name": "Sales Head"}]
        ev = mod74._stakeholder_evidence("ev74i", repo)
        self.assertEqual(sorted(e["source"] for e in ev["FR-001"]),
                         ["5.5:approval", "declared"])

    def test_ties_for_labels_finds_a_person_by_either_name_or_role(self):
        repo = make_repo("ev74j", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["stakeholders"] = [{"name": "Product Owner"}]
        repo["requirements"][0]["owner"] = "Ivan Petrov"
        ev = mod74._stakeholder_evidence("ev74j", repo)
        ties = mod74._ties_for_labels({"ivan petrov", "product owner"}, ev)
        self.assertEqual(sorted(t["source"] for t in ties),
                         ["7.1:owner", "declared"])

    def test_ties_for_labels_ignores_everyone_else(self):
        repo = make_repo("ev74k", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["owner"] = "Ivan Petrov"
        ev = mod74._stakeholder_evidence("ev74k", repo)
        self.assertEqual(mod74._ties_for_labels({"someone else"}, ev), [])

    def test_evidence_never_reads_the_title(self):
        # The title heuristic is deliberately NOT one of the three evidence sources —
        # it stays where it is, in the gap check, explicitly labelled as a heuristic.
        repo = make_repo("ev74l", [make_req("FR-001", "functional", "Sales Head report")])
        self.assertEqual(mod74._stakeholder_evidence("ev74l", repo)["FR-001"], [])


class TestDeclareStakeholderInterest(BaseMCPTest):
    """The tool the whole feature exists for — and the one that can destroy BA input.

    Repeat-call semantics are MERGE: all parameters are optional-looking and a replace
    on the second call is this repository's "silent data loss" class. Removal is only
    ever explicit, the way `add_trace_link(remove=...)` does it in 5.1.
    """

    def _repo(self, project_id="dsi74"):
        save_repo(make_repo(project_id, [
            make_req("FR-001", "functional", "Auto routing"),
            make_req("FR-002", "functional", "Notifications"),
        ]))
        return project_id

    def _stored(self, project_id, req_id="FR-001"):
        path = data_path(project_id, f"{project_id}_traceability_repo.json")
        with open(path, "r", encoding="utf-8") as f:
            repo = json.load(f)
        return next(r for r in repo["requirements"] if r["id"] == req_id)

    def test_a_declaration_is_stored_as_an_object_with_its_date(self):
        pid = self._repo()
        save_stakeholder_registry(pid, [{"name": "Sales Head", "role": "Sponsor"}])
        mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]',
                                           note="revenue reporting")
        entry = self._stored(pid)["stakeholders"][0]
        self.assertEqual(entry["name"], "Sales Head")
        self.assertEqual(entry["declared"], str(date.today()))
        self.assertEqual(entry["note"], "revenue reporting")

    def test_the_reply_counts_what_it_did(self):
        pid = self._repo()
        save_stakeholder_registry(pid, [{"name": "Sales Head", "role": "Sponsor"}])
        result = mod74.declare_stakeholder_interest(pid, "Sales Head",
                                                    '["FR-001", "FR-002"]')
        self.assertIn("declared on 2 requirement(s)", result)

    def test_a_second_identical_call_adds_nothing_and_says_so(self):
        # Silence is right for an accusation and wrong for a count: "done" after a
        # no-op leaves the BA unable to tell whether anything was recorded.
        pid = self._repo()
        save_stakeholder_registry(pid, [{"name": "Sales Head", "role": "Sponsor"}])
        mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]')
        result = mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]')
        self.assertIn("declared on 0 requirement(s)", result)
        self.assertIn("already declared on 1", result)
        self.assertEqual(len(self._stored(pid)["stakeholders"]), 1)

    def test_a_second_call_with_different_case_is_still_the_same_person(self):
        # Identity is compared normalised (reg_norm), not by the raw string: a BA who
        # types the same name with different capitalisation the second time must not
        # produce a duplicate entry.
        pid = self._repo()
        save_stakeholder_registry(pid, [{"name": "Sales Head", "role": "Sponsor"}])
        mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]')
        result = mod74.declare_stakeholder_interest(pid, "sales head", '["FR-001"]')
        self.assertIn("declared on 0 requirement(s)", result)
        self.assertIn("already declared on 1", result)
        self.assertEqual(len(self._stored(pid)["stakeholders"]), 1)

    def test_a_second_call_for_someone_else_does_not_erase_the_first(self):
        # THE data-loss test. A replace here would wipe input the BA never withdrew.
        pid = self._repo()
        save_stakeholder_registry(pid, [{"name": "Sales Head"}, {"name": "Data Architect"}])
        mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]')
        mod74.declare_stakeholder_interest(pid, "Data Architect", '["FR-001"]')
        names = [e["name"] for e in self._stored(pid)["stakeholders"]]
        self.assertEqual(sorted(names), ["Data Architect", "Sales Head"])

    def test_remove_takes_the_declaration_back_out(self):
        pid = self._repo()
        save_stakeholder_registry(pid, [{"name": "Sales Head"}])
        mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]')
        result = mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]',
                                                    remove=True)
        self.assertIn("removed from 1 requirement(s)", result)
        self.assertEqual(self._stored(pid)["stakeholders"], [])

    def test_removing_what_was_never_declared_reports_zero(self):
        pid = self._repo()
        save_stakeholder_registry(pid, [{"name": "Sales Head"}])
        result = mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]',
                                                    remove=True)
        self.assertIn("removed from 0 requirement(s)", result)

    def test_an_unknown_req_id_is_refused_with_the_ones_that_exist(self):
        # The requirement vocabulary is CLOSED — it is this project's own graph — so a
        # typo is refused at the call, the cheapest moment to fix it.
        pid = self._repo()
        result = mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-999"]')
        self.assertTrue(result.startswith("❌"))
        self.assertIn("FR-999", result)
        self.assertIn("FR-001", result)
        self.assertEqual(self._stored(pid).get("stakeholders", []), [])

    def test_one_bad_id_refuses_the_whole_call_and_writes_nothing(self):
        pid = self._repo()
        result = mod74.declare_stakeholder_interest(pid, "Sales Head",
                                                    '["FR-001", "FR-999"]')
        self.assertTrue(result.startswith("❌"))
        self.assertEqual(self._stored(pid).get("stakeholders", []), [])

    def test_a_known_stakeholder_gets_no_registry_warning(self):
        pid = self._repo()
        save_stakeholder_registry(pid, [{"name": "Sales Head", "role": "Sponsor"}])
        result = mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]')
        self.assertNotIn("not in the stakeholder registry", result)
        self.assertNotIn("no stakeholder registry", result)

    def test_a_role_resolves_against_the_registry_too(self):
        pid = self._repo()
        save_stakeholder_registry(pid, [{"name": "Ivan Petrov", "role": "Product Owner"}])
        result = mod74.declare_stakeholder_interest(pid, "Product Owner", '["FR-001"]')
        self.assertNotIn("not in the stakeholder registry", result)

    def test_an_unknown_stakeholder_is_recorded_with_a_warning(self):
        # The registry is a LIVING document: refusing here would block a BA who just
        # heard the name in an interview. Warn, record, and point at the fix.
        pid = self._repo()
        save_stakeholder_registry(pid, [{"name": "Sales Head"}])
        result = mod74.declare_stakeholder_interest(pid, "Brand New Person", '["FR-001"]')
        self.assertIn("not in the stakeholder registry", result)
        self.assertIn("update_stakeholder_registry", result)
        self.assertEqual(self._stored(pid)["stakeholders"][0]["name"], "Brand New Person")

    def test_no_registry_at_all_says_it_cannot_compare_not_that_the_person_is_missing(self):
        pid = self._repo("dsi74noreg")
        result = mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]')
        self.assertIn("no stakeholder registry", result)
        self.assertNotIn("not in the stakeholder registry", result)
        self.assertEqual(self._stored(pid)["stakeholders"][0]["name"], "Sales Head")

    def test_an_empty_stakeholder_name_is_refused(self):
        pid = self._repo()
        result = mod74.declare_stakeholder_interest(pid, "   ", '["FR-001"]')
        self.assertTrue(result.startswith("❌"))

    def test_broken_req_ids_json_is_refused(self):
        pid = self._repo()
        result = mod74.declare_stakeholder_interest(pid, "Sales Head", "not json")
        self.assertTrue(result.startswith("❌"))

    def test_an_empty_repository_degrades_softly(self):
        result = mod74.declare_stakeholder_interest("dsi74empty", "Sales Head",
                                                    '["FR-001"]')
        self.assertTrue(result.startswith("⚠️"))

    def test_the_declaration_is_written_to_history(self):
        pid = self._repo()
        save_stakeholder_registry(pid, [{"name": "Sales Head"}])
        mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]')
        path = data_path(pid, f"{pid}_traceability_repo.json")
        with open(path, "r", encoding="utf-8") as f:
            repo = json.load(f)
        actions = [h["action"] for h in repo["history"]]
        self.assertIn("stakeholder_interest_declared", actions)
        self.assertEqual(repo["history"][-1]["source"], "7.4_architecture")

    def test_a_removal_is_written_to_history_too(self):
        # Nothing disappears without a trace — the project rule for deprecation.
        pid = self._repo()
        save_stakeholder_registry(pid, [{"name": "Sales Head"}])
        mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]')
        mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]', remove=True)
        path = data_path(pid, f"{pid}_traceability_repo.json")
        with open(path, "r", encoding="utf-8") as f:
            repo = json.load(f)
        self.assertIn("stakeholder_interest_removed",
                      [h["action"] for h in repo["history"]])

    def test_declaring_does_not_touch_any_other_field_of_the_requirement(self):
        pid = self._repo()
        save_stakeholder_registry(pid, [{"name": "Sales Head"}])
        before = self._stored(pid)
        mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]')
        after = self._stored(pid)
        for key in ("id", "type", "title", "status", "priority", "version"):
            self.assertEqual(before[key], after[key])


class TestStakeholderVerdictRestsOnEvidence(BaseMCPTest):
    """The critical verdict stops being a coincidence between a name and a title word.

    The title heuristic is NOT deleted — deleting it would hand every existing project
    a batch of new red gaps on upgrade. It is demoted: a stakeholder reachable only
    that way is a WARNING that names its own weakness.
    """

    def test_a_declared_stakeholder_is_represented_and_the_source_is_named(self):
        repo = make_repo("gv74", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["stakeholders"] = [{"name": "Priya Nair"}]
        save_repo(repo)
        save_stakeholder_registry("gv74", [{"name": "Priya Nair", "role": "Compliance"}])
        result = mod74.check_architecture_gaps("gv74")
        self.assertNotIn("`Priya Nair` has no recorded tie", result)
        # An EXACT tie must be fully silent — not merely "not critical". Without
        # this, disabling the tie short-circuit still passes: the person's own
        # exact evidence string re-enters through the name-pool heuristic and
        # produces a warning instead, which the check above would not catch.
        self.assertIn("🟡 Warning | 0", result)

    def test_a_5_5_voter_is_represented_without_any_declaration(self):
        # The point of reading 5.5: this works on projects that never call the new tool.
        save_repo(make_repo("gv74b", [make_req("FR-001", "functional", "Auto routing")]))
        path = os.path.join("governance_plans", "data", "gv74b_approval_history.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"project": "gv74b", "packages": {"PKG-001": {
                "req_ids": ["FR-001"], "stakeholder_decisions": {"Priya Nair": {
                    "raci": "accountable",
                    "req_decisions": [{"req_id": "FR-001", "decision": "approved"}]}}}}}, f)
        save_stakeholder_registry("gv74b", [{"name": "Priya Nair", "role": "Compliance"}])
        result = mod74.check_architecture_gaps("gv74b")
        self.assertNotIn("`Priya Nair` has no recorded tie", result)
        self.assertIn("🟡 Warning | 0", result)

    def test_a_stakeholder_reachable_only_by_a_title_word_is_a_warning_not_critical(self):
        save_repo(make_repo("gv74c", [
            make_req("FR-001", "functional", "Compliance reporting rules")]))
        save_stakeholder_registry("gv74c", [{"name": "", "role": "Compliance"}])
        result = mod74.check_architecture_gaps("gv74c")
        # Discriminating check (a prior version of this assertion was dead code:
        # `"## 🔴" in critical_block` was always False here since `gaps_critical`
        # is empty in this fixture, so the guarded expression was always "" and
        # `assertNotIn` could never fail for any implementation).
        self.assertIn("🔴 Critical | 0", result)
        self.assertIn("only by a word in a requirement title", result)
        self.assertIn("declare_stakeholder_interest", result)

    def test_a_stakeholder_with_nothing_at_all_is_still_critical(self):
        save_repo(make_repo("gv74d", [make_req("FR-001", "functional", "Auto routing")]))
        save_stakeholder_registry("gv74d", [{"name": "Priya Nair", "role": "Compliance"}])
        result = mod74.check_architecture_gaps("gv74d")
        self.assertIn("`Priya Nair` has no recorded tie", result)
        self.assertIn("🔴 Critical | 1", result)

    def test_the_critical_message_names_every_place_it_looked(self):
        # A verdict that hides its method invites more confidence than its evidence
        # carries — the ADR-088 rule, kept and made specific.
        save_repo(make_repo("gv74e", [make_req("FR-001", "functional", "Auto routing")]))
        save_stakeholder_registry("gv74e", [{"name": "Priya Nair", "role": "Compliance"}])
        result = mod74.check_architecture_gaps("gv74e")
        self.assertIn("declared interest", result)
        self.assertIn("7.1 owner", result)
        self.assertIn("5.5 approval", result)

    def test_the_owner_is_still_represented_and_now_says_which_requirement(self):
        # ADR-088 kept: the owner counts. What is NEW is that the reader can check it.
        repo = make_repo("gv74f", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["owner"] = "David Kim"
        save_repo(repo)
        save_stakeholder_registry("gv74f", [{"name": "David Kim", "role": "SIU"}])
        result = mod74.check_architecture_gaps("gv74f")
        self.assertNotIn("`David Kim` has no recorded tie", result)
        self.assertIn("🟡 Warning | 0", result)

    def test_a_role_only_registry_row_resolves_through_its_role(self):
        repo = make_repo("gv74g", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["stakeholders"] = [{"name": "Product Owner"}]
        save_repo(repo)
        save_stakeholder_registry("gv74g", [{"name": "Ivan Petrov", "role": "Product Owner"}])
        result = mod74.check_architecture_gaps("gv74g")
        self.assertNotIn("has no recorded tie", result)
        self.assertIn("🟡 Warning | 0", result)

    def test_the_missing_registry_warning_is_unchanged(self):
        # Regression guard: this branch is explicitly out of scope for the feature.
        save_repo(make_repo("gv74h", [make_req("FR-001", "functional", "Auto routing")]))
        result = mod74.check_architecture_gaps("gv74h")
        self.assertIn("Stakeholder registry not found", result)

    def test_a_short_shared_word_does_not_count_as_a_title_match(self):
        # "it" is a real word of the title AND the stakeholder's role, but it is only
        # 2 letters — below the 4-letter floor the heuristic requires. Without the
        # floor this coincidence would wrongly demote a real gap to a warning.
        save_repo(make_repo("gv74i", [make_req("FR-001", "functional", "Wire it now")]))
        save_stakeholder_registry("gv74i", [{"name": "", "role": "IT"}])
        result = mod74.check_architecture_gaps("gv74i")
        self.assertIn("`IT` has no recorded tie", result)

    def test_a_registry_row_with_neither_name_nor_role_is_silently_skipped(self):
        # A row with nothing to key on cannot be looked up in evidence OR title words —
        # it is not identifiable, so it must not be reported at all (not as a fabricated
        # "—" critical gap).
        save_repo(make_repo("gv74j", [make_req("FR-001", "functional", "Auto routing")]))
        save_stakeholder_registry("gv74j", [{"name": "", "role": ""}])
        result = mod74.check_architecture_gaps("gv74j")
        self.assertNotIn("Stakeholder `—`", result)
        self.assertIn("🔴 Critical | 0", result)

    def test_a_partial_name_match_is_a_warning_not_a_critical(self):
        # Review round 1, finding 1: `_ties_for_labels` matches evidence EXACTLY
        # (correct — a fact), so "Priya" (owner) is no longer an exact tie to the
        # registry's "Priya Nair". Before this fix that turned into a brand-new
        # critical — exactly the "no existing project acquires new red gaps"
        # invariant the brief exists to protect, broken through a different door.
        # A partial match must land as a warning: not silence, not critical.
        repo = make_repo("gv74k", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["owner"] = "Priya"
        save_repo(repo)
        save_stakeholder_registry("gv74k", [{"name": "Priya Nair", "role": "Compliance"}])
        result = mod74.check_architecture_gaps("gv74k")
        self.assertNotIn("`Priya Nair` has no recorded tie", result)
        self.assertIn("🔴 Critical | 0", result)
        self.assertIn("🟡 Warning | 1", result)
        # A phrase only the new partial-name warning branch can assemble — the
        # report has several sections, so a bare common word would be ambiguous.
        self.assertIn("partial name match", result)

    def test_an_exact_name_match_still_silences_the_gap(self):
        # Guard against over-widening: adding the name pool must not stop an EXACT
        # match from taking the tie path (silent) — it must still short-circuit
        # before the heuristic is even consulted.
        repo = make_repo("gv74l", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["owner"] = "Priya Nair"
        save_repo(repo)
        save_stakeholder_registry("gv74l", [{"name": "Priya Nair", "role": "Compliance"}])
        result = mod74.check_architecture_gaps("gv74l")
        self.assertNotIn("`Priya Nair` has no recorded tie", result)
        self.assertNotIn("partial name match", result)
        self.assertIn("🟡 Warning | 0", result)

    def test_a_short_partial_name_fragment_does_not_count_as_evidence(self):
        # The 4-character floor applies to the name pool exactly as it does to
        # title words: a 2-letter fragment ("Al" as an owner) must not manufacture
        # a false "represented" warning for an unrelated registry row.
        repo = make_repo("gv74m", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["owner"] = "Al"
        save_repo(repo)
        save_stakeholder_registry("gv74m", [{"name": "Alina Petrova", "role": "Consultant"}])
        result = mod74.check_architecture_gaps("gv74m")
        self.assertIn("`Alina Petrova` has no recorded tie", result)
        self.assertIn("🔴 Critical | 1", result)


class TestTheDocumentCarriesStakeholderConcerns(BaseMCPTest):
    """Assertions go against the DELIVERED document, not the reply.

    `save_architecture_snapshot` sends the document to save_artifact and RETURNS a
    summary — the two are different texts, and asserting the block against the return
    value would pass vacuously forever.
    """

    def _doc(self, project_id, version="v1.0"):
        with patch.object(mod74, "save_artifact") as mock_sa:
            mod74.save_architecture_snapshot(project_id, version)
            self.assertTrue(mock_sa.called, "save_artifact was not reached — "
                                            "check the tool's early returns")
            return mock_sa.call_args[0][0]

    def test_a_declared_tie_is_shown_with_its_requirement_and_its_source(self):
        # Every claim must be checkable ON THIS PAGE: the req_id is printed, so the
        # reader can find it in the viewpoint tables above.
        repo = make_repo("doc74", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["stakeholders"] = [{"name": "Priya Nair"}]
        save_repo(repo)
        save_stakeholder_registry("doc74", [{"name": "Priya Nair", "role": "Compliance"}])
        doc = self._doc("doc74")
        self.assertIn("## Stakeholder concerns", doc)
        self.assertIn("Priya Nair", doc)
        self.assertIn("`FR-001` (declared)", doc)

    def test_the_owner_tie_names_its_chapter_in_the_document(self):
        repo = make_repo("doc74b", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["owner"] = "David Kim"
        save_repo(repo)
        save_stakeholder_registry("doc74b", [{"name": "David Kim", "role": "SIU"}])
        doc = self._doc("doc74b")
        self.assertIn("`FR-001` (7.1:owner)", doc)

    def test_a_stakeholder_with_no_tie_is_a_state_not_an_accusation(self):
        save_repo(make_repo("doc74c", [make_req("FR-001", "functional", "Auto routing")]))
        save_stakeholder_registry("doc74c", [{"name": "Priya Nair", "role": "Compliance"}])
        doc = self._doc("doc74c")
        self.assertIn("no interest recorded", doc)

    def test_without_a_registry_the_section_says_the_list_was_not_checked(self):
        # The denominator is a claim about the domain too: with no registry the
        # platform must not imply the list of people is complete.
        repo = make_repo("doc74d", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["owner"] = "David Kim"
        save_repo(repo)
        doc = self._doc("doc74d")
        self.assertIn("stakeholder registry not found", doc.lower())
        self.assertIn("David Kim", doc)

    def test_the_section_lands_before_the_gaps_section(self):
        # Placement matters: anything appended after `"\n".join(doc_lines)` is dead
        # code that neither errors nor prints — the 6.4 Task-4 trap.
        repo = make_repo("doc74e", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["owner"] = "David Kim"
        save_repo(repo)
        save_stakeholder_registry("doc74e", [{"name": "David Kim"}])
        doc = self._doc("doc74e")
        self.assertLess(doc.index("## Stakeholder concerns"),
                        doc.index("## Architecture gaps"))

    def test_the_summary_reply_does_not_contain_the_section(self):
        # Documents the asymmetry so a later reader does not "fix" the test by
        # asserting against the return value.
        repo = make_repo("doc74f", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["owner"] = "David Kim"
        save_repo(repo)
        save_stakeholder_registry("doc74f", [{"name": "David Kim"}])
        with patch.object(mod74, "save_artifact"):
            reply = mod74.save_architecture_snapshot("doc74f", "v1.0")
        self.assertNotIn("## Stakeholder concerns", reply)

    def test_one_tie_and_two_ties_both_read_correctly(self):
        # A number branch that inflects one of two agreeing words is half a fix — check
        # BOTH forms in one test, not only the one the run happened to hit.
        repo = make_repo("doc74g", [make_req("FR-001", "functional", "Auto routing"),
                                    make_req("FR-002", "functional", "Notifications")])
        repo["requirements"][0]["stakeholders"] = [{"name": "Solo Person"}]
        repo["requirements"][1]["stakeholders"] = [{"name": "Busy Person"}]
        repo["requirements"][0]["owner"] = "Busy Person"
        save_repo(repo)
        save_stakeholder_registry("doc74g", [{"name": "Solo Person"}, {"name": "Busy Person"}])
        doc = self._doc("doc74g")
        self.assertIn("1 requirement", doc)
        self.assertIn("2 requirements", doc)
        self.assertNotIn("1 requirements", doc)

    def test_a_null_stakeholders_field_does_not_lose_the_document(self):
        # An explicit null, not a deleted key — different guards, and this is the one
        # `.get(k, default)` does nothing about.
        repo = make_repo("doc74h", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["stakeholders"] = None
        save_repo(repo)
        save_stakeholder_registry("doc74h", [{"name": "David Kim"}])
        doc = self._doc("doc74h")
        self.assertIn("## Stakeholder concerns", doc)

    def test_a_registry_row_with_neither_name_nor_role_is_not_rendered(self):
        # Mirrors the gaps-side guard
        # (test_a_registry_row_with_neither_name_nor_role_is_silently_skipped): a row
        # with nothing to key on is not identifiable, so the document must not
        # fabricate a "—" bullet for it.
        #
        # Fix review round 1: the file WAS found here — it just has no identifiable
        # rows — so the document must not say "not found" either. That claim is
        # false and a sponsor cannot tell "nobody registered yet" from "the
        # registry step was skipped entirely".
        repo = make_repo("doc74i", [make_req("FR-001", "functional", "Auto routing")])
        save_repo(repo)
        save_stakeholder_registry("doc74i", [{"name": "", "role": ""}])
        doc = self._doc("doc74i")
        self.assertNotIn("**—**", doc)
        self.assertNotIn("registry not found", doc.lower())
        self.assertIn("no identifiable people", doc)

    def test_an_empty_registry_list_is_not_reported_as_not_found(self):
        # A registry persisted as {"stakeholders": []} — the ordinary shape the
        # first time elicitation runs with nobody identified yet. The file exists
        # and was read; the document must say THAT, not that it was not found.
        #
        # NOTE: `save_stakeholder_registry(pid, [])` cannot express this — its
        # `stakeholders or [default row]` falls back to a non-empty default on an
        # empty list, since `[]` is falsy. Writing the registry file directly here
        # to get a genuinely empty list on disk.
        repo = make_repo("doc74j", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["owner"] = "David Kim"
        save_repo(repo)
        os.makedirs(os.path.join("governance_plans", "data"), exist_ok=True)
        with open(os.path.join("governance_plans", "data", "doc74j_stakeholder_registry.json"),
                  "w", encoding="utf-8") as f:
            json.dump({"project": "doc74j", "stakeholders": [], "history": []}, f)
        doc = self._doc("doc74j")
        self.assertIn("no identifiable people", doc)
        self.assertNotIn("not found", doc.lower())
        self.assertIn("David Kim", doc)

    def test_the_no_registry_fallback_merges_case_variants_of_one_person(self):
        # `_stakeholder_evidence` stores `who` verbatim and normalises only for
        # comparison. Two producer tasks (7.4's declaration, 7.1's owner field) can
        # type the same human differently — "David Kim" vs "david kim" — and
        # grouping by the raw string split one person into two under-reporting
        # bullets (fix review round 1). Grouping by identity keeps them as one.
        repo = make_repo("doc74k", [make_req("FR-001", "functional", "Auto routing"),
                                    make_req("FR-002", "functional", "Notifications")])
        repo["requirements"][0]["stakeholders"] = [{"name": "David Kim"}]
        repo["requirements"][1]["owner"] = "david kim"
        save_repo(repo)
        doc = self._doc("doc74k")
        self.assertEqual(doc.count("**David Kim**"), 1)
        self.assertNotIn("**david kim**", doc)
        self.assertIn("`FR-001` (declared)", doc)
        self.assertIn("`FR-002` (7.1:owner)", doc)
        self.assertIn("2 requirements", doc)


class TestLiveRunFindings74(BaseMCPTest):
    """Three defects a live run found by READING the delivered document.

    None of them is reachable by grep: each one is a true statement sitting next to
    another true statement, and only the assembled page shows the contradiction.
    """

    def _doc(self, project_id, version="v1.0"):
        with patch.object(mod74, "save_artifact") as mock_sa:
            mod74.save_architecture_snapshot(project_id, version)
            self.assertTrue(mock_sa.called, "save_artifact was not reached — "
                                            "check the tool's early returns")
            return mock_sa.call_args[0][0]

    def test_two_sources_on_one_requirement_are_one_reference_not_two(self):
        """L-1. The count said "1 requirement" and the list showed `FR-001` twice.

        Both halves were literally true — one requirement, two sources — but a reader
        sees a count that disagrees with the list beneath it and stops trusting the
        page. Sources belong grouped under the requirement they are sources for.
        """
        repo = make_repo("live74a", [make_req("FR-001", "functional", "Shift handover")])
        repo["requirements"][0]["owner"] = "Marcus Webb"
        repo["requirements"][0]["stakeholders"] = [{"name": "Marcus Webb"}]
        save_repo(repo)
        save_stakeholder_registry("live74a", [{"name": "Marcus Webb", "role": "Nurse"}])
        doc = self._doc("live74a")
        self.assertIn("`FR-001` (7.1:owner, declared)", doc)
        concerns = doc.split("## Stakeholder concerns")[1].split("## Architecture gaps")[0]
        self.assertEqual(concerns.count("`FR-001`"), 1,
                         "one requirement must be referenced once, however many "
                         "sources vouch for it")
        self.assertIn("1 requirement:", concerns)

    def test_a_person_declared_but_absent_from_the_registry_is_still_shown(self):
        """L-2. The tool said "recorded anyway"; the document showed nothing.

        `declare_stakeholder_interest` deliberately accepts a stakeholder the registry
        does not know — the registry is a living document. But the section was built by
        walking the REGISTRY, so that person appeared nowhere, and the analyst who was
        told the declaration was recorded could not find it on the page.
        """
        repo = make_repo("live74b", [make_req("FR-001", "functional", "Consent capture")])
        repo["requirements"][0]["stakeholders"] = [{"name": "Helen Vasquez"}]
        save_repo(repo)
        save_stakeholder_registry("live74b", [{"name": "Ivan Petrov", "role": "PO"}])
        doc = self._doc("live74b")
        self.assertIn("Helen Vasquez", doc)
        self.assertIn("not in the 4.2 registry", doc)
        self.assertIn("`FR-001` (declared)", doc)

    def test_a_heuristic_only_stakeholder_is_not_reported_as_having_nothing(self):
        """L-3. Two people in different states rendered identically.

        `owner: "Priya"` against a registry row "Priya Nair" is a heuristic match — the
        gap report says so and calls it a warning. The document said "no interest
        recorded", the same words it used for a stakeholder with nothing at all, so the
        page erased a distinction the platform had already drawn.
        """
        repo = make_repo("live74c", [
            make_req("FR-001", "functional", "Retention schedule"),
            make_req("FR-002", "functional", "Bulk export"),
        ])
        repo["requirements"][0]["owner"] = "Priya"
        save_repo(repo)
        save_stakeholder_registry("live74c", [
            {"name": "Priya Nair", "role": "Compliance"},
            {"name": "Marcus Webb", "role": "Nurse"},
        ])
        doc = self._doc("live74c")
        concerns = doc.split("## Stakeholder concerns")[1].split("## Architecture gaps")[0]
        self.assertIn("**Priya Nair** — no exact tie recorded", concerns)
        self.assertIn("**Marcus Webb** — no interest recorded", concerns)
        self.assertNotIn("**Priya Nair** — no interest recorded", concerns)

    def test_a_short_form_of_a_registry_name_is_flagged_as_probably_the_same_person(self):
        """L-4, produced by the fix for L-2 and found by re-reading the page.

        `owner: "Priya"` against a registry row "Priya Nair" now appears TWICE: above as
        a registry member with no exact tie, and below as an unknown party. They are one
        human, and the advice attached to the lower entry ("add them to the registry") is
        actively wrong for them — the fix is to correct the owner field, not the registry.
        """
        repo = make_repo("live74e", [make_req("FR-001", "functional", "Retention schedule")])
        repo["requirements"][0]["owner"] = "Priya"
        save_repo(repo)
        save_stakeholder_registry("live74e", [{"name": "Priya Nair", "role": "Compliance"}])
        doc = self._doc("live74e")
        concerns = doc.split("## Stakeholder concerns")[1].split("## Architecture gaps")[0]
        self.assertIn("possibly the same person as **Priya Nair**", concerns)

    def test_a_genuinely_unknown_party_carries_no_same_person_hint(self):
        """The other side of the branch: a name that resembles nobody in the registry
        must not acquire a hint, or the hint means nothing."""
        repo = make_repo("live74f", [make_req("FR-001", "functional", "Retention schedule")])
        repo["requirements"][0]["stakeholders"] = [{"name": "Helen Vasquez"}]
        save_repo(repo)
        save_stakeholder_registry("live74f", [{"name": "Ivan Petrov", "role": "PO"}])
        doc = self._doc("live74f")
        concerns = doc.split("## Stakeholder concerns")[1].split("## Architecture gaps")[0]
        self.assertIn("**Helen Vasquez**", concerns)
        self.assertNotIn("possibly the same person", concerns)

    def test_the_two_states_agree_with_the_gap_report(self):
        """The document and the gap report must not disagree about the same person.

        Same fixture as above, read through the other tool: whoever the report calls a
        warning must not be the one the document calls empty, and vice versa.
        """
        repo = make_repo("live74d", [
            make_req("FR-001", "functional", "Retention schedule"),
            make_req("FR-002", "functional", "Bulk export"),
        ])
        repo["requirements"][0]["owner"] = "Priya"
        save_repo(repo)
        save_stakeholder_registry("live74d", [
            {"name": "Priya Nair", "role": "Compliance"},
            {"name": "Marcus Webb", "role": "Nurse"},
        ])
        report = mod74.check_architecture_gaps("live74d")
        self.assertIn("🔴 Critical | 1", report)
        self.assertIn("🟡 Warning | 1", report)
        doc = self._doc("live74d")
        concerns = doc.split("## Stakeholder concerns")[1].split("## Architecture gaps")[0]
        self.assertIn("**Priya Nair** — no exact tie recorded", concerns)
        self.assertIn("**Marcus Webb** — no interest recorded", concerns)


class TestOnlyRequirementsCarryStakeholderTies(BaseMCPTest):
    """Branch review R-1. The whole new path walked `repo["requirements"]` with no
    type filter, while every OTHER 7.4 path filters by `SKIP_TYPES`.

    Three independently serious consequences, all reproduced live: the tool called a
    risk "a requirement"; the coverage check the feature exists for could be silenced
    with a business goal; and the delivered document printed ids that appear nowhere
    else on the page, under a header saying "Total req | 1".
    """

    def _doc(self, project_id, version="v1.0"):
        with patch.object(mod74, "save_artifact") as mock_sa:
            mod74.save_architecture_snapshot(project_id, version)
            self.assertTrue(mock_sa.called, "save_artifact was not reached")
            return mock_sa.call_args[0][0]

    def _mixed_repo(self, project_id):
        return make_repo(project_id, [
            make_req("FR-001", "functional", "Auto routing"),
            make_req("RISK-002", "risk", "Compliance officer unavailable for sign-off"),
            make_req("BG-001", "business_goal", "Reduce processing time"),
            make_req("CR-001", "change_request", "Widen the export"),
        ])

    def test_a_hand_written_tie_on_a_risk_node_is_not_evidence(self):
        repo = self._mixed_repo("skip74")
        repo["requirements"][1]["stakeholders"] = [{"name": "Helen Vasquez"}]
        repo["requirements"][1]["owner"] = "Helen Vasquez"
        ev = mod74._stakeholder_evidence("skip74", repo)
        self.assertNotIn("RISK-002", ev)
        self.assertEqual(ev["FR-001"], [])

    def test_declaring_interest_on_a_risk_node_is_refused_and_says_why(self):
        # A SILENT skip would be the same defect class this branch already fixed
        # twice: the tool would answer "declared on 0" and never say which id it
        # dropped or why.
        save_repo(self._mixed_repo("skip74b"))
        result = mod74.declare_stakeholder_interest(
            "skip74b", "Helen Vasquez", '["RISK-002", "BG-001"]')
        self.assertTrue(result.startswith("❌"), result)
        self.assertIn("RISK-002", result)
        self.assertIn("risk", result)
        self.assertIn("BG-001", result)
        self.assertIn("business_goal", result)

    def test_one_non_requirement_id_refuses_the_whole_call_and_writes_nothing(self):
        pid = "skip74c"
        save_repo(self._mixed_repo(pid))
        result = mod74.declare_stakeholder_interest(
            pid, "Helen Vasquez", '["FR-001", "RISK-002"]')
        self.assertTrue(result.startswith("❌"), result)
        path = data_path(pid, f"{pid}_traceability_repo.json")
        with open(path, "r", encoding="utf-8") as f:
            stored = json.load(f)
        fr = next(r for r in stored["requirements"] if r["id"] == "FR-001")
        self.assertEqual(fr.get("stakeholders", []), [])

    def test_the_existing_ids_offered_by_the_refusal_are_requirements_only(self):
        save_repo(self._mixed_repo("skip74d"))
        result = mod74.declare_stakeholder_interest("skip74d", "Helen", '["FR-999"]')
        self.assertIn("`FR-001`", result)
        self.assertNotIn("`RISK-002`", result)
        self.assertNotIn("`BG-001`", result)

    def test_a_risk_title_is_not_a_word_the_heuristic_may_match(self):
        # The second symptom of the same root: the heuristic pool ate risk and CR
        # titles, so a `Compliance` role was demoted to a warning that claimed the
        # word came from "a requirement title". No requirement mentions it.
        save_repo(self._mixed_repo("skip74e"))
        save_stakeholder_registry("skip74e", [{"name": "", "role": "Compliance"}])
        result = mod74.check_architecture_gaps("skip74e")
        self.assertIn("🔴 Critical | 1", result)
        self.assertNotIn("only by a word in a requirement title", result)

    def test_a_business_goal_cannot_silence_the_coverage_check(self):
        repo = self._mixed_repo("skip74f")
        repo["requirements"][2]["stakeholders"] = [{"name": "Helen Vasquez"}]
        save_repo(repo)
        save_stakeholder_registry("skip74f", [{"name": "Helen Vasquez", "role": "Ops"}])
        result = mod74.check_architecture_gaps("skip74f")
        self.assertIn("`Helen Vasquez` has no recorded tie", result)
        self.assertIn("🔴 Critical | 1", result)

    def test_the_document_never_prints_an_id_it_does_not_count(self):
        repo = self._mixed_repo("skip74g")
        repo["requirements"][1]["stakeholders"] = [{"name": "Helen Vasquez"}]
        repo["requirements"][2]["stakeholders"] = [{"name": "Helen Vasquez"}]
        save_repo(repo)
        save_stakeholder_registry("skip74g", [{"name": "Helen Vasquez", "role": "Ops"}])
        doc = self._doc("skip74g")
        self.assertIn("| Total req | 1 |", doc)
        concerns = doc.split("## Stakeholder concerns")[1].split("## Architecture gaps")[0]
        self.assertNotIn("RISK-002", concerns)
        self.assertNotIn("BG-001", concerns)
        self.assertIn("**Helen Vasquez** — no interest recorded", concerns)


class TestTheSnapshotRecomputesItsOwnGaps(BaseMCPTest):
    """Branch review A-1. The delivered document contradicted itself along the route
    this chapter's own SKILL.md prescribes.

    `_concern_lines` is computed LIVE at save time; the "Architecture gaps" block ten
    lines below it read `arch["gaps"]`, frozen by the last `check_architecture_gaps`.
    The standard workflow is 4 `check_architecture_gaps` → 5 "resolve critical gaps:
    declare the interests you know" → 6 `save_architecture_snapshot`, so the stale
    block is what the ordinary route produces, not an edge case.

    Marking the block "possibly stale" instead was structurally blind to the finding:
    both files stamp `updated` as a DATE, and the whole route runs inside one session,
    so a same-day comparison always says "fresh".
    """

    def _doc(self, project_id, version="v1.0"):
        with patch.object(mod74, "save_artifact") as mock_sa:
            mod74.save_architecture_snapshot(project_id, version)
            self.assertTrue(mock_sa.called, "save_artifact was not reached")
            return mock_sa.call_args[0][0]

    def _project(self, pid):
        save_repo(make_repo(pid, [make_req("FR-001", "functional", "Auto routing")]))
        save_stakeholder_registry(pid, [{"name": "Priya Nair", "role": "Compliance"}])
        return pid

    def test_a_gap_resolved_between_the_check_and_the_snapshot_is_gone_from_the_document(self):
        pid = self._project("a1_74")
        report = mod74.check_architecture_gaps(pid)
        self.assertIn("🔴 Critical | 1", report)
        mod74.declare_stakeholder_interest(pid, "Priya Nair", '["FR-001"]')
        doc = self._doc(pid)
        concerns = doc.split("## Stakeholder concerns")[1].split("## Architecture gaps")[0]
        gaps_block = doc.split("## Architecture gaps")[1]
        self.assertIn("`FR-001` (declared)", concerns)
        self.assertIn("| 🔴 Critical | 0 |", gaps_block)
        self.assertNotIn("has no recorded tie", gaps_block)

    def test_the_reply_stops_claiming_an_unresolved_gap_that_was_resolved(self):
        pid = self._project("a1_74b")
        mod74.check_architecture_gaps(pid)
        mod74.declare_stakeholder_interest(pid, "Priya Nair", '["FR-001"]')
        with patch.object(mod74, "save_artifact"):
            reply = mod74.save_architecture_snapshot(pid, "v1.0")
        self.assertIn("| 🔴 Critical gaps | 0 |", reply)
        self.assertNotIn("critical gap(s) not resolved", reply)

    def test_a_gap_that_appeared_after_the_check_is_in_the_snapshot(self):
        # The other direction: recomputing must not only ever lower the number.
        pid = "a1_74c"
        save_repo(make_repo(pid, [make_req("FR-001", "functional", "Auto routing")]))
        save_stakeholder_registry(pid, [{"name": "Priya Nair", "role": "Compliance"}])
        mod74.declare_stakeholder_interest(pid, "Priya Nair", '["FR-001"]')
        report = mod74.check_architecture_gaps(pid)
        self.assertIn("🔴 Critical | 0", report)
        mod74.declare_stakeholder_interest(pid, "Priya Nair", '["FR-001"]', remove=True)
        doc = self._doc(pid)
        gaps_block = doc.split("## Architecture gaps")[1]
        self.assertIn("| 🔴 Critical | 1 |", gaps_block)
        self.assertIn("has no recorded tie", gaps_block)

    def test_the_snapshot_stores_the_recomputed_gaps_on_the_architecture_file(self):
        pid = self._project("a1_74d")
        mod74.check_architecture_gaps(pid)
        mod74.declare_stakeholder_interest(pid, "Priya Nair", '["FR-001"]')
        with patch.object(mod74, "save_artifact"):
            mod74.save_architecture_snapshot(pid, "v1.0")
        self.assertEqual(load_arch(pid)["gaps"]["critical"], [])

    def test_a_refused_duplicate_version_writes_nothing_at_all(self):
        # The recompute rides along with `_save_architecture`, so it must sit AFTER
        # the duplicate-version guard: an early return that had already rewritten
        # the gaps would be a write the BA was told did not happen.
        pid = self._project("a1_74e")
        mod74.check_architecture_gaps(pid)
        with patch.object(mod74, "save_artifact"):
            mod74.save_architecture_snapshot(pid, "v1.0")
        before = json.dumps(load_arch(pid), sort_keys=True)
        mod74.declare_stakeholder_interest(pid, "Priya Nair", '["FR-001"]')
        with patch.object(mod74, "save_artifact") as mock_sa:
            reply = mod74.save_architecture_snapshot(pid, "v1.0")
            self.assertFalse(mock_sa.called)
        self.assertIn("already exists", reply)
        self.assertEqual(json.dumps(load_arch(pid), sort_keys=True), before)

    def test_the_snapshot_and_the_gap_report_agree_without_calling_the_check_at_all(self):
        # A project that never runs `check_architecture_gaps` used to sign a document
        # whose gap table was all zeros because nothing had ever filled it in.
        pid = self._project("a1_74f")
        doc = self._doc(pid)
        gaps_block = doc.split("## Architecture gaps")[1]
        self.assertIn("| 🔴 Critical | 1 |", gaps_block)
        self.assertIn("`Priya Nair` has no recorded tie", gaps_block)


class TestStoredShapesThatUsedToKillTheTool(BaseMCPTest):
    """Branch review R-2, R-3 and A-2 — three stored shapes that escaped as raw
    exceptions past `guard_artifact_errors`, which only converts CorruptArtifactError.

    All three are the class this repository keeps re-learning: guard by TYPE, not by
    truthiness, and put the guard BEFORE the access it protects. The neighbouring
    functions already did it right — `_declared_concerns` uses `.get(k) or []` and says
    why, `load_stakeholder_registry` normalises `history` and says why — so each of
    these is one function that did not follow a rule written two screens away.
    """

    def _doc(self, project_id, version="v1.0"):
        with patch.object(mod74, "save_artifact") as mock_sa:
            mod74.save_architecture_snapshot(project_id, version)
            self.assertTrue(mock_sa.called, "save_artifact was not reached")
            return mock_sa.call_args[0][0]

    def _write_registry(self, project_id, payload):
        os.makedirs(os.path.join("governance_plans", "data"), exist_ok=True)
        path = os.path.join("governance_plans", "data",
                            f"{project_id}_stakeholder_registry.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)

    def test_a_null_stakeholders_list_in_the_registry_still_delivers_the_document(self):
        # R-2. `.get("stakeholders", [])` returns None for an explicit null and the
        # next line iterates it. check_architecture_gaps degrades cleanly on the very
        # same file, so the two tools disagreed about whether it is readable.
        repo = make_repo("shape74", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["owner"] = "David Kim"
        save_repo(repo)
        self._write_registry("shape74", {"project": "shape74", "stakeholders": None})
        doc = self._doc("shape74")
        self.assertIn("## Stakeholder concerns", doc)
        self.assertIn("David Kim", doc)

    def test_a_non_list_stakeholders_value_in_the_registry_does_not_raise_either(self):
        repo = make_repo("shape74b", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["owner"] = "David Kim"
        save_repo(repo)
        self._write_registry("shape74b", {"project": "shape74b",
                                          "stakeholders": {"name": "Ivan"}})
        doc = self._doc("shape74b")
        self.assertIn("## Stakeholder concerns", doc)

    def test_a_registry_row_that_is_a_bare_string_does_not_take_the_gap_check_down(self):
        # A-2. The guard `if not labels: continue` existed — two lines BELOW the
        # `sh.get("name")` it protects.
        save_repo(make_repo("shape74c", [make_req("FR-001", "functional", "Auto routing")]))
        self._write_registry("shape74c", {"project": "shape74c",
                                          "stakeholders": ["Ivan Petrov"]})
        result = mod74.check_architecture_gaps("shape74c")
        self.assertIn("🔴 Critical | 0", result)
        self.assertNotIn("Traceback", result)

    def test_a_dict_history_does_not_lose_the_declaration(self):
        # R-3. `.setdefault("history", []).append(...)` raises on a stored dict, and
        # the raise happens BEFORE _save_repo — so the declaration vanished from
        # memory as well as from disk.
        pid = "shape74d"
        repo = make_repo(pid, [make_req("FR-001", "functional", "Auto routing")])
        repo["history"] = {}
        save_repo(repo)
        result = mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]')
        self.assertIn("declared on 1 requirement(s)", result)
        path = data_path(pid, f"{pid}_traceability_repo.json")
        with open(path, "r", encoding="utf-8") as f:
            stored = json.load(f)
        self.assertEqual(stored["requirements"][0]["stakeholders"][0]["name"],
                         "Sales Head")
        self.assertIn("stakeholder_interest_declared",
                      [h["action"] for h in stored["history"]])

    def test_a_string_history_is_normalised_the_same_way(self):
        pid = "shape74e"
        repo = make_repo(pid, [make_req("FR-001", "functional", "Auto routing")])
        repo["history"] = "was a list once"
        save_repo(repo)
        mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]')
        path = data_path(pid, f"{pid}_traceability_repo.json")
        with open(path, "r", encoding="utf-8") as f:
            stored = json.load(f)
        self.assertIsInstance(stored["history"], list)
        self.assertEqual(stored["history"][-1]["action"],
                         "stakeholder_interest_declared")


class TestArchivedRequirementsAreNotCoverage(BaseMCPTest):
    """Branch review B-2. 7.4 filtered by `type` and never once by `status`.

    Declare an interest, then deprecate the requirement: the gap report said 🔴 0 /
    🟡 0 and the document printed "Helen Vasquez — 1 requirement: `FR-002` (declared)"
    with no mark at all. A stakeholder whose every tie is archived reads as fully
    covered — and the archive set {deprecated, superseded, retired} has been settled
    across six modules since long before this chapter existed.

    The verdict is a WARNING, never a critical: decision 6 of this feature says no
    existing project may acquire a NEW red gap on upgrade, and silence → warning is
    allowed where silence → critical is not (the invariant already broken once, T5-1).
    """

    def _doc(self, project_id, version="v1.0"):
        with patch.object(mod74, "save_artifact") as mock_sa:
            mod74.save_architecture_snapshot(project_id, version)
            self.assertTrue(mock_sa.called, "save_artifact was not reached")
            return mock_sa.call_args[0][0]

    def _repo_with(self, pid, statuses):
        reqs = []
        for i, status in enumerate(statuses, 1):
            reqs.append(make_req(f"FR-00{i}", "functional", f"Feature {i}",
                                 status=status))
            reqs[-1]["stakeholders"] = [{"name": "Helen Vasquez"}]
        save_repo(make_repo(pid, reqs))
        save_stakeholder_registry(pid, [{"name": "Helen Vasquez", "role": "Ops"}])
        return pid

    def test_a_stakeholder_whose_only_tie_is_deprecated_is_a_warning(self):
        pid = self._repo_with("arch74", ["deprecated"])
        result = mod74.check_architecture_gaps(pid)
        self.assertIn("🔴 Critical | 0", result)
        self.assertIn("🟡 Warning | 1", result)
        self.assertIn("archived", result)
        self.assertIn("Helen Vasquez", result)

    def test_superseded_and_retired_count_as_archived_too(self):
        for status in ("superseded", "retired"):
            with self.subTest(status=status):
                pid = self._repo_with(f"arch74_{status}", [status])
                result = mod74.check_architecture_gaps(pid)
                self.assertIn("🟡 Warning | 1", result)

    def test_one_live_tie_among_archived_ones_is_still_full_coverage(self):
        pid = self._repo_with("arch74b", ["deprecated", "verified"])
        result = mod74.check_architecture_gaps(pid)
        self.assertIn("🔴 Critical | 0", result)
        self.assertIn("🟡 Warning | 0", result)

    def test_an_all_archived_stakeholder_never_becomes_a_new_critical(self):
        # The invariant guard: warning is the ceiling for this state.
        pid = self._repo_with("arch74c", ["deprecated", "retired"])
        result = mod74.check_architecture_gaps(pid)
        self.assertIn("🔴 Critical | 0", result)
        self.assertNotIn("has no recorded tie", result)

    def test_the_document_shows_the_archived_tie_and_marks_it(self):
        # Hiding it would be the "silent skip" class this branch fixed twice: the BA
        # declared that tie and must see what became of it.
        pid = self._repo_with("arch74d", ["deprecated"])
        doc = self._doc(pid)
        concerns = doc.split("## Stakeholder concerns")[1].split("## Architecture gaps")[0]
        self.assertIn("`FR-001` (declared, archived)", concerns)
        self.assertIn("Helen Vasquez", concerns)

    def test_a_live_tie_carries_no_archived_mark(self):
        pid = self._repo_with("arch74e", ["verified"])
        doc = self._doc(pid)
        concerns = doc.split("## Stakeholder concerns")[1].split("## Architecture gaps")[0]
        self.assertIn("`FR-001` (declared)", concerns)
        self.assertNotIn("archived", concerns)

    def test_declaring_on_an_archived_requirement_is_accepted_with_a_warning(self):
        # A STATUS is not a TYPE: a deprecated requirement is still a requirement, so
        # the tool records the declaration and says what it recorded it on. Refusing
        # here (the R-1 treatment) would be wrong — nothing was misrepresented.
        pid = "arch74f"
        save_repo(make_repo(pid, [
            make_req("FR-001", "functional", "Old feature", status="deprecated")]))
        save_stakeholder_registry(pid, [{"name": "Helen Vasquez", "role": "Ops"}])
        result = mod74.declare_stakeholder_interest(pid, "Helen Vasquez", '["FR-001"]')
        self.assertIn("declared on 1 requirement(s)", result)
        self.assertIn("archived", result.lower())
        self.assertIn("FR-001", result)
        path = data_path(pid, f"{pid}_traceability_repo.json")
        with open(path, "r", encoding="utf-8") as f:
            stored = json.load(f)
        self.assertEqual(stored["requirements"][0]["stakeholders"][0]["name"],
                         "Helen Vasquez")

    def test_declaring_on_a_live_requirement_says_nothing_about_archives(self):
        pid = "arch74g"
        save_repo(make_repo(pid, [make_req("FR-001", "functional", "Live feature")]))
        save_stakeholder_registry(pid, [{"name": "Helen Vasquez", "role": "Ops"}])
        result = mod74.declare_stakeholder_interest(pid, "Helen Vasquez", '["FR-001"]')
        self.assertNotIn("archived", result.lower())


class TestAnEmptyRegistryIsNotAMissingOne(BaseMCPTest):
    """Branch review B-1. The three-valued answer collapsed on two surfaces of three.

    (a) `registry_party_status` asked "is the people list empty?" and answered
    UNBRIDGEABLE — the answer reserved for "there is nothing to compare against".
    So with the file ON DISK the tool said "There is no stakeholder registry for
    `s_empty` … Create it via the 3.2 or 4.2 tools" while the document for the same
    project said "Stakeholder registry has no identifiable people". Two surfaces
    asserting opposite things about one state, and the advice was wrong.

    (b) `check_architecture_gaps` printed 🔴 0 / 🟡 0 and NOT ONE info note, because
    its "registry not found" note fires only on a missing FILE. The sponsor read a
    clean verdict on a project where nobody had been checked.
    """

    def _doc(self, project_id, version="v1.0"):
        with patch.object(mod74, "save_artifact") as mock_sa:
            mod74.save_architecture_snapshot(project_id, version)
            self.assertTrue(mock_sa.called, "save_artifact was not reached")
            return mock_sa.call_args[0][0]

    def _write_registry(self, project_id, payload):
        os.makedirs(os.path.join("governance_plans", "data"), exist_ok=True)
        path = os.path.join("governance_plans", "data",
                            f"{project_id}_stakeholder_registry.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)

    def test_declaring_against_an_empty_registry_does_not_tell_the_ba_to_create_one(self):
        pid = "b1_74"
        save_repo(make_repo(pid, [make_req("FR-001", "functional", "Auto routing")]))
        self._write_registry(pid, {"project": pid, "stakeholders": []})
        result = mod74.declare_stakeholder_interest(pid, "Helen Vasquez", '["FR-001"]')
        self.assertNotIn("no stakeholder registry", result)
        self.assertIn("not in the stakeholder registry", result)

    def test_the_tool_and_the_document_agree_about_an_empty_registry(self):
        pid = "b1_74b"
        save_repo(make_repo(pid, [make_req("FR-001", "functional", "Auto routing")]))
        self._write_registry(pid, {"project": pid, "stakeholders": []})
        reply = mod74.declare_stakeholder_interest(pid, "Helen Vasquez", '["FR-001"]')
        doc = self._doc(pid)
        self.assertNotIn("Create it via the 3.2 or 4.2 tools", reply)
        self.assertIn("no identifiable people", doc)

    def test_a_missing_registry_still_says_it_cannot_compare(self):
        # The other side of the branch: the third answer must survive where it is true.
        pid = "b1_74c"
        save_repo(make_repo(pid, [make_req("FR-001", "functional", "Auto routing")]))
        result = mod74.declare_stakeholder_interest(pid, "Helen Vasquez", '["FR-001"]')
        self.assertIn("no stakeholder registry", result)

    def test_an_empty_registry_produces_an_info_note_in_the_gap_report(self):
        pid = "b1_74d"
        save_repo(make_repo(pid, [make_req("FR-001", "functional", "Auto routing")]))
        self._write_registry(pid, {"project": pid, "stakeholders": []})
        result = mod74.check_architecture_gaps(pid)
        self.assertIn("nobody identifiable", result)
        self.assertNotIn("registry not found", result.lower())

    def test_a_registry_of_unidentifiable_rows_produces_the_same_note(self):
        pid = "b1_74e"
        save_repo(make_repo(pid, [make_req("FR-001", "functional", "Auto routing")]))
        self._write_registry(pid, {"project": pid,
                                   "stakeholders": [{"influence": "High"}]})
        result = mod74.check_architecture_gaps(pid)
        self.assertIn("nobody identifiable", result)

    def test_a_null_stakeholder_list_produces_the_note_rather_than_a_clean_verdict(self):
        pid = "b1_74f"
        save_repo(make_repo(pid, [make_req("FR-001", "functional", "Auto routing")]))
        self._write_registry(pid, {"project": pid, "stakeholders": None})
        result = mod74.check_architecture_gaps(pid)
        self.assertIn("nobody identifiable", result)

    def test_a_populated_registry_gets_no_such_note(self):
        pid = "b1_74g"
        save_repo(make_repo(pid, [make_req("FR-001", "functional", "Auto routing")]))
        save_stakeholder_registry(pid, [{"name": "Helen Vasquez", "role": "Ops"}])
        result = mod74.check_architecture_gaps(pid)
        self.assertNotIn("nobody identifiable", result)


class TestNothingThatUsedToBeSilentBecomesCritical(BaseMCPTest):
    """Branch review A-3. `_heuristic_hit`'s docstring claims the set of stakeholders
    the OLD rule called "represented" stays a subset of (silent | warning). For values
    the old code reached through `str()`, it did not.

    The old rule built its bucket with `str(sh).lower()` and `str(owner).lower()`, so a
    dict in the `stakeholders` field or a non-string `owner` still put SOMETHING in it
    to match against. Evidence deliberately drops both — `str(42)` would print "42" into
    a signed document as a person — but dropping them from the COINCIDENCE pool as well
    turned yesterday's silence into today's critical, which is the one thing decision 6
    of this feature forbids.

    Making the claim TRUE rather than narrowing it: the raw values rejoin the heuristic
    pool, which is only ever matched against and never printed, so nothing becomes
    evidence and nothing gets rendered as a person.
    """

    def _doc(self, project_id, version="v1.0"):
        with patch.object(mod74, "save_artifact") as mock_sa:
            mod74.save_architecture_snapshot(project_id, version)
            self.assertTrue(mock_sa.called, "save_artifact was not reached")
            return mock_sa.call_args[0][0]

    def test_a_role_only_dict_in_the_stakeholders_field_is_not_a_new_critical(self):
        repo = make_repo("a3_74", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["stakeholders"] = [{"role": "Compliance Officer"}]
        save_repo(repo)
        save_stakeholder_registry("a3_74", [{"name": "", "role": "Compliance Officer"}])
        result = mod74.check_architecture_gaps("a3_74")
        self.assertIn("🔴 Critical | 0", result)
        self.assertIn("🟡 Warning | 1", result)

    def test_a_non_string_owner_is_not_a_new_critical_either(self):
        repo = make_repo("a3_74b", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["owner"] = {"name": "Priya Nair"}
        save_repo(repo)
        save_stakeholder_registry("a3_74b", [{"name": "Priya Nair", "role": "Compliance"}])
        result = mod74.check_architecture_gaps("a3_74b")
        self.assertIn("🔴 Critical | 0", result)
        self.assertIn("🟡 Warning | 1", result)

    def test_the_unreadable_value_never_becomes_evidence(self):
        # The pool is matched against, never rendered. A number in the field must not
        # acquire a name, a tie or a line in the document.
        repo = make_repo("a3_74c", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["stakeholders"] = [{"role": "Compliance Officer"}]
        repo["requirements"][0]["owner"] = 42
        ev = mod74._stakeholder_evidence("a3_74c", repo)
        self.assertEqual(ev["FR-001"], [])

    def test_the_unreadable_value_is_never_printed_as_a_person(self):
        repo = make_repo("a3_74d", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["owner"] = {"name": "Priya Nair"}
        save_repo(repo)
        save_stakeholder_registry("a3_74d", [{"name": "Priya Nair", "role": "Compliance"}])
        doc = self._doc("a3_74d")
        concerns = doc.split("## Stakeholder concerns")[1].split("## Architecture gaps")[0]
        self.assertNotIn("{'name'", concerns)
        self.assertIn("**Priya Nair** — no exact tie recorded", concerns)

    def test_an_unrelated_unreadable_value_still_leaves_a_real_gap_critical(self):
        # Guard against over-widening: the pool must not match everyone just because
        # it now holds a stringified dict.
        repo = make_repo("a3_74e", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["owner"] = {"name": "Someone Else"}
        save_repo(repo)
        save_stakeholder_registry("a3_74e", [{"name": "Priya Nair", "role": "Compl"}])
        result = mod74.check_architecture_gaps("a3_74e")
        self.assertIn("`Priya Nair` has no recorded tie", result)
        self.assertIn("🔴 Critical | 1", result)


class TestTheSamePersonHintAdmitsItIsAHeuristic(BaseMCPTest):
    """Branch review A-4. The one heuristic claim on the branch that did not say so.

    Reproduced: registry {"name": "Ivan Petrov", "role": "Compliance"} and an owner
    field reading "Compliance Officer" produced "**Compliance Officer** — 1 requirement:
    `FR-001` (7.1:owner) — possibly the same person as **Ivan Petrov**". Two different
    named humans, welded together by the word "compliance", stated flatly. Every other
    heuristic statement in this feature names itself as one.

    `sorted(label_owner)` also picked one match alphabetically and hid the rest, so the
    document could not even be checked against its own data.
    """

    def _doc(self, project_id, version="v1.0"):
        with patch.object(mod74, "save_artifact") as mock_sa:
            mod74.save_architecture_snapshot(project_id, version)
            self.assertTrue(mock_sa.called, "save_artifact was not reached")
            return mock_sa.call_args[0][0]

    def test_the_hint_says_what_matched_and_that_it_is_a_coincidence(self):
        repo = make_repo("a4_74", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["owner"] = "Compliance Officer"
        save_repo(repo)
        save_stakeholder_registry("a4_74", [{"name": "Ivan Petrov",
                                             "role": "Compliance"}])
        doc = self._doc("a4_74")
        concerns = doc.split("## Stakeholder concerns")[1].split("## Architecture gaps")[0]
        self.assertIn("possibly the same person as **Ivan Petrov**", concerns)
        self.assertIn("compliance", concerns)
        self.assertIn("coincidence", concerns)

    def test_every_registry_member_that_matches_is_named_not_just_the_first(self):
        repo = make_repo("a4_74b", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["owner"] = "Compliance Officer"
        save_repo(repo)
        # Two humans sharing ONE role label. `label_owner.setdefault` kept only the
        # first, so the second could not be named however the match was picked —
        # the other half of A-4's "chosen alphabetically among several matches".
        save_stakeholder_registry("a4_74b", [
            {"name": "Ivan Petrov", "role": "Compliance"},
            {"name": "Zoe Adams", "role": "Compliance"},
        ])
        doc = self._doc("a4_74b")
        concerns = doc.split("## Stakeholder concerns")[1].split("## Architecture gaps")[0]
        hint = concerns.split("not in the 4.2 registry")[1]
        self.assertIn("Ivan Petrov", hint)
        self.assertIn("Zoe Adams", hint)

    def test_an_exact_short_form_still_reads_as_one_person(self):
        # The L-4 fixture must keep working: this is the case the hint exists for.
        repo = make_repo("a4_74c", [make_req("FR-001", "functional", "Retention")])
        repo["requirements"][0]["owner"] = "Priya"
        save_repo(repo)
        save_stakeholder_registry("a4_74c", [{"name": "Priya Nair", "role": "Compl"}])
        doc = self._doc("a4_74c")
        concerns = doc.split("## Stakeholder concerns")[1].split("## Architecture gaps")[0]
        self.assertIn("possibly the same person as **Priya Nair**", concerns)


class TestNothingIsDiscardedOrRecordedInSilence(BaseMCPTest):
    """Branch review A-7 and B-4 — two halves of the same promise.

    A-7: a `stakeholders` value that is not a list is REPLACED, and the tool said
    nothing. SKILL.md and the user guide both promise the platform "never silently
    erases". The replacement stays — a hand-edited dict cannot be merged into a list of
    declarations — but it is now named, so the sentence is true.

    B-4: `note` was a write-only field. One write, zero reads: the docstring invites the
    BA to record WHY the interests are touched, and the concerns section — the one place
    a sponsor needs that "why" — never showed it. Tested as data, never as output.
    """

    def _doc(self, project_id, version="v1.0"):
        with patch.object(mod74, "save_artifact") as mock_sa:
            mod74.save_architecture_snapshot(project_id, version)
            self.assertTrue(mock_sa.called, "save_artifact was not reached")
            return mock_sa.call_args[0][0]

    def _repo(self, pid="a7_74"):
        save_repo(make_repo(pid, [make_req("FR-001", "functional", "Auto routing"),
                                  make_req("FR-002", "functional", "Notifications")]))
        save_stakeholder_registry(pid, [{"name": "Sales Head", "role": "Sponsor"}])
        return pid

    def test_replacing_a_non_list_stakeholders_value_is_named_in_the_reply(self):
        pid = self._repo()
        repo = make_repo(pid, [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["stakeholders"] = {"name": "Old Note", "why": "keep me"}
        save_repo(repo)
        result = mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]')
        self.assertIn("FR-001", result)
        self.assertIn("replaced", result.lower())

    def test_the_discarded_value_is_kept_in_the_repository_history(self):
        # "Never delete data" is a project rule, not a preference.
        pid = self._repo("a7_74b")
        repo = make_repo(pid, [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["stakeholders"] = {"name": "Old Note", "why": "keep me"}
        save_repo(repo)
        mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]')
        path = data_path(pid, f"{pid}_traceability_repo.json")
        with open(path, "r", encoding="utf-8") as f:
            stored = json.load(f)
        replaced = [h for h in stored["history"] if h.get("replaced")]
        self.assertTrue(replaced, "the discarded value must survive somewhere")
        self.assertEqual(replaced[0]["replaced"]["FR-001"],
                         {"name": "Old Note", "why": "keep me"})

    def test_an_ordinary_list_value_produces_no_such_warning(self):
        pid = self._repo("a7_74c")
        mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]')
        result = mod74.declare_stakeholder_interest(pid, "Data Architect", '["FR-001"]')
        self.assertNotIn("replaced", result.lower())

    def test_the_note_reaches_the_delivered_document(self):
        pid = self._repo("b4_74")
        mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]',
                                           note="owns the revenue report these feed")
        doc = self._doc(pid)
        concerns = doc.split("## Stakeholder concerns")[1].split("## Architecture gaps")[0]
        self.assertIn("owns the revenue report these feed", concerns)
        self.assertIn("FR-001", concerns)

    def test_a_declaration_without_a_note_adds_no_empty_line(self):
        pid = self._repo("b4_74b")
        mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]')
        doc = self._doc(pid)
        concerns = doc.split("## Stakeholder concerns")[1].split("## Architecture gaps")[0]
        self.assertIn("**Sales Head** — 1 requirement: `FR-001` (declared)", concerns)
        self.assertNotIn("  - `FR-001`:", concerns)

    def test_each_note_says_which_requirement_it_belongs_to(self):
        pid = self._repo("b4_74c")
        mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]',
                                           note="revenue")
        mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-002"]',
                                           note="SLA reporting")
        doc = self._doc(pid)
        concerns = doc.split("## Stakeholder concerns")[1].split("## Architecture gaps")[0]
        self.assertIn("`FR-001`: revenue", concerns)
        self.assertIn("`FR-002`: SLA reporting", concerns)


class TestTheConcernsSectionSurvivesHostileInput(BaseMCPTest):
    """Branch review B-5. `_group_refs` had no ceiling and `who` was interpolated raw.

    The viewpoint tables one section up cap themselves at `req_ids[:20]`; this one did
    not, so one person on 60 requirements produced a single 1297-character bullet. And
    a name containing `**` rendered as `****Bold Person****` while a name containing a
    newline broke the list apart — the delivered document is Markdown, and the names in
    it come from a stakeholder registry a human types into.
    """

    def _doc(self, project_id, version="v1.0"):
        with patch.object(mod74, "save_artifact") as mock_sa:
            mod74.save_architecture_snapshot(project_id, version)
            self.assertTrue(mock_sa.called, "save_artifact was not reached")
            return mock_sa.call_args[0][0]

    def test_a_person_on_sixty_requirements_does_not_produce_one_endless_line(self):
        reqs = []
        for i in range(1, 61):
            r = make_req(f"FR-{i:03d}", "functional", f"Feature {i}")
            r["stakeholders"] = [{"name": "Busy Person"}]
            reqs.append(r)
        save_repo(make_repo("b5_74", reqs))
        save_stakeholder_registry("b5_74", [{"name": "Busy Person", "role": "Ops"}])
        doc = self._doc("b5_74")
        concerns = doc.split("## Stakeholder concerns")[1].split("## Architecture gaps")[0]
        bullet = next(l for l in concerns.splitlines() if "Busy Person" in l)
        self.assertLess(len(bullet), 500, "one bullet must not run to a paragraph")
        self.assertIn("60 requirements", bullet)
        self.assertIn("more", bullet)
        self.assertIn("`FR-001`", bullet)

    def test_the_count_still_reports_every_requirement_not_only_the_shown_ones(self):
        # Truncating the LIST is honest; truncating the COUNT would be a false number
        # in a signed document.
        reqs = []
        for i in range(1, 31):
            r = make_req(f"FR-{i:03d}", "functional", f"Feature {i}")
            r["stakeholders"] = [{"name": "Busy Person"}]
            reqs.append(r)
        save_repo(make_repo("b5_74b", reqs))
        save_stakeholder_registry("b5_74b", [{"name": "Busy Person", "role": "Ops"}])
        doc = self._doc("b5_74b")
        self.assertIn("30 requirements", doc)

    def test_a_name_with_markdown_in_it_does_not_reformat_the_page(self):
        repo = make_repo("b5_74c", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["stakeholders"] = [{"name": "**Bold Person**"}]
        save_repo(repo)
        save_stakeholder_registry("b5_74c", [{"name": "**Bold Person**", "role": "Ops"}])
        doc = self._doc("b5_74c")
        concerns = doc.split("## Stakeholder concerns")[1].split("## Architecture gaps")[0]
        self.assertNotIn("****", concerns)
        self.assertIn("Bold Person", concerns)

    def test_a_name_with_a_newline_does_not_break_the_list_apart(self):
        repo = make_repo("b5_74d", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["stakeholders"] = [{"name": "Line One\nLine Two"}]
        save_repo(repo)
        save_stakeholder_registry("b5_74d", [{"name": "Line One\nLine Two"}])
        doc = self._doc("b5_74d")
        concerns = doc.split("## Stakeholder concerns")[1].split("## Architecture gaps")[0]
        bullets = [l for l in concerns.splitlines() if l.startswith("- **")]
        self.assertEqual(len(bullets), 1)
        self.assertIn("Line One Line Two", bullets[0])

    def test_a_hostile_name_is_also_tamed_in_the_gap_report(self):
        # The gap message quotes `who` inside backticks, and a backtick in the name
        # ends the code span early.
        save_repo(make_repo("b5_74e", [make_req("FR-001", "functional", "Auto routing")]))
        save_stakeholder_registry("b5_74e", [{"name": "Weird `Name`", "role": "Ops"}])
        result = mod74.check_architecture_gaps("b5_74e")
        self.assertIn("Weird", result)
        self.assertNotIn("`Weird `Name``", result)

    def test_an_endless_note_is_capped_too(self):
        pid = "b5_74f"
        save_repo(make_repo(pid, [make_req("FR-001", "functional", "Auto routing")]))
        save_stakeholder_registry(pid, [{"name": "Sales Head", "role": "Ops"}])
        mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]',
                                           note="x" * 900)
        doc = self._doc(pid)
        note_line = next(l for l in doc.splitlines() if l.strip().startswith("- `FR-001`:"))
        self.assertLess(len(note_line), 300)


class TestGapsInCoverageTheMutationsExposed(BaseMCPTest):
    """Branch review A-5 and B-6 — two places where a mutation survived because
    nothing tested the behaviour, not because the mutation was inert.

    A-5: dropping the source dedup in `_group_refs` left the suite green. Two
    declarations that resolve to ONE person through name AND role produce the same
    (req_id, source) pair twice, so without the dedup the page reads
    "`FR-001` (declared, declared)".

    B-6: `_save_repo` was rewritten to write unconditionally to the canonical NESTED
    path, and 138/138 passed — because every 7.4 fixture writes the repository FLAT,
    and `data_path` follows the file that already exists. The docstring's claim that
    no second copy can appear had zero coverage. The live run says the code is right;
    this is the missing test, not a bug.
    """

    def test_one_person_reached_by_both_name_and_role_is_not_listed_twice(self):
        repo = make_repo("a5_74", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["stakeholders"] = [{"name": "Ivan Petrov"},
                                                   {"name": "Product Owner"}]
        ev = mod74._stakeholder_evidence("a5_74", repo)
        ties = mod74._ties_for_labels({"ivan petrov", "product owner"}, ev)
        self.assertEqual(len(ties), 2, "both declarations are real evidence")
        rendered = mod74._group_refs(
            (t["req_id"], t["source"], t["archived"]) for t in ties)
        self.assertEqual(rendered, "`FR-001` (declared)")

    def test_the_same_person_in_the_document_is_one_requirement_not_two(self):
        repo = make_repo("a5_74b", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["stakeholders"] = [{"name": "Ivan Petrov"},
                                                   {"name": "Product Owner"}]
        save_repo(repo)
        save_stakeholder_registry("a5_74b", [{"name": "Ivan Petrov",
                                              "role": "Product Owner"}])
        with patch.object(mod74, "save_artifact") as mock_sa:
            mod74.save_architecture_snapshot("a5_74b", "v1.0")
            doc = mock_sa.call_args[0][0]
        concerns = doc.split("## Stakeholder concerns")[1].split("## Architecture gaps")[0]
        self.assertIn("1 requirement: `FR-001` (declared)", concerns)
        self.assertNotIn("declared, declared", concerns)

    def test_a_nested_repository_is_written_back_in_place(self):
        pid = "b6_74"
        nested_dir = os.path.join("governance_plans", "data", pid)
        os.makedirs(nested_dir, exist_ok=True)
        nested = os.path.join(nested_dir, f"{pid}_traceability_repo.json")
        with open(nested, "w", encoding="utf-8") as f:
            json.dump(make_repo(pid, [make_req("FR-001", "functional", "Auto routing")]),
                      f)
        mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]')
        flat = os.path.join("governance_plans", "data", f"{pid}_traceability_repo.json")
        self.assertFalse(os.path.exists(flat),
                         "a second copy under the flat layout would split the graph")
        with open(nested, "r", encoding="utf-8") as f:
            stored = json.load(f)
        self.assertEqual(stored["requirements"][0]["stakeholders"][0]["name"],
                         "Sales Head")

    def test_a_flat_repository_is_also_written_back_in_place(self):
        # The other half of the same claim: `data_path` returns the path it READ from,
        # so a legacy flat file must not sprout a nested twin either.
        pid = "b6_74b"
        save_repo(make_repo(pid, [make_req("FR-001", "functional", "Auto routing")]))
        mod74.declare_stakeholder_interest(pid, "Sales Head", '["FR-001"]')
        nested = os.path.join("governance_plans", "data", pid,
                              f"{pid}_traceability_repo.json")
        self.assertFalse(os.path.exists(nested))


class TestTheSourceConstantsAreActuallyRead(BaseMCPTest):
    """Branch review A-6. `CONCERN_TITLE` and `CONCERN_EVIDENCE` were declared and read
    nowhere, while the four sources they name were spelled out by hand in the prose of
    the critical gap message. A constant that lives only in prose drifts away from the
    code the day one of them is renamed, and nothing fails.
    """

    def _project(self, pid):
        save_repo(make_repo(pid, [make_req("FR-001", "functional", "Auto routing")]))
        save_stakeholder_registry(pid, [{"name": "Priya Nair", "role": "Compliance"}])
        return pid

    def test_every_evidence_source_has_a_human_label(self):
        for source in mod74.CONCERN_EVIDENCE + (mod74.CONCERN_TITLE,):
            with self.subTest(source=source):
                self.assertIn(source, mod74.CONCERN_LABELS)

    def test_the_critical_message_is_assembled_from_those_labels(self):
        # Patched rather than string-matched: matching the words proves only that the
        # words are somewhere, not that the constant is what put them there.
        pid = self._project("a6_74")
        with patch.dict(mod74.CONCERN_LABELS,
                        {mod74.CONCERN_OWNER: "SENTINEL-OWNER-LABEL"}):
            result = mod74.check_architecture_gaps(pid)
        self.assertIn("SENTINEL-OWNER-LABEL", result)

    def test_the_heuristic_source_is_named_from_its_own_constant(self):
        pid = self._project("a6_74b")
        with patch.dict(mod74.CONCERN_LABELS,
                        {mod74.CONCERN_TITLE: "SENTINEL-TITLE-LABEL"}):
            result = mod74.check_architecture_gaps(pid)
        self.assertIn("SENTINEL-TITLE-LABEL", result)

    def test_the_message_still_names_all_three_evidence_sources_in_plain_words(self):
        pid = self._project("a6_74c")
        result = mod74.check_architecture_gaps(pid)
        self.assertIn("declared interest", result)
        self.assertIn("7.1 owner", result)
        self.assertIn("5.5 approval", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
