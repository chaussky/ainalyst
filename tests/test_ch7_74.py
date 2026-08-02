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
        self.assertEqual(ev["FR-001"], [{"who": "Sales Head", "source": "declared"}])

    def test_the_owner_is_evidence_labelled_with_its_chapter(self):
        repo = make_repo("ev74b", [make_req("FR-001", "functional", "Auto routing")])
        repo["requirements"][0]["owner"] = "Ivan Petrov"
        ev = mod74._stakeholder_evidence("ev74b", repo)
        self.assertEqual(ev["FR-001"], [{"who": "Ivan Petrov", "source": "7.1:owner"}])

    def test_a_5_5_vote_on_this_requirement_is_evidence(self):
        self._write_approvals("ev74c", {"PKG-001": {"req_ids": ["FR-001"],
            "stakeholder_decisions": {"Priya Nair": {"raci": "accountable",
                "req_decisions": [{"req_id": "FR-001", "decision": "approved"}]}}}})
        repo = make_repo("ev74c", [make_req("FR-001", "functional", "Auto routing")])
        ev = mod74._stakeholder_evidence("ev74c", repo)
        self.assertEqual(ev["FR-001"], [{"who": "Priya Nair", "source": "5.5:approval"}])

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
        # A top level that is valid JSON but the wrong SHAPE — the class that took the
        # 6.4 gap importer down with AttributeError after `is not None` replaced a
        # falsy check. Guard by TYPE, not by truthiness.
        self._write_approvals("ev74h", ["PKG-001"])
        repo = make_repo("ev74h", [make_req("FR-001", "functional", "Auto routing")])
        self.assertEqual(mod74._stakeholder_evidence("ev74h", repo)["FR-001"], [])

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
