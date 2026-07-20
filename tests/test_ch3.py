"""
tests/test_ch3.py — Tests for task 3 (Business Analysis Planning)

Coverage:
  - suggest_ba_approach            (14 tests)
  - plan_stakeholder_engagement    (14 tests)
  - plan_ba_governance             (12 tests)
  - plan_information_management    (12 tests)
  - evaluate_ba_performance        (11 tests)
  - save_ba_plan                   (10 tests)
  - Utilities (_safe, _classify_stakeholder, _load/_save_plan)  (7 tests)
  - Integration pipeline tests  (8 tests)
Total: ~88 tests
"""

import json
import os
import sys
import unittest
from datetime import date
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import setup_mocks, BaseMCPTest

setup_mocks()

from skills.planning_mcp import (
    suggest_ba_approach,
    plan_stakeholder_engagement,
    plan_ba_governance,
    plan_information_management,
    evaluate_ba_performance,
    save_ba_plan,
    _safe, _classify_stakeholder, _load_plan, _save_plan,
    _plan_path,
    DATA_DIR,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT = "test_project_ch3"
TODAY = str(date.today())


def _load(project_id: str = PROJECT) -> dict:
    path = _plan_path(project_id)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _make_approach(project_id: str = PROJECT, **kwargs):
    params = dict(
        project_id=project_id,
        change_frequency="Medium",
        uncertainty="Medium",
        regulatory_need=False,
    )
    params.update(kwargs)
    return suggest_ba_approach(**params)


def _make_stakeholders(project_id: str = PROJECT, **kwargs):
    stakeholders = [
        {"name": "Sponsor", "role": "CEO", "influence": "High", "interest": "High", "attitude": "Champion"},
        {"name": "User", "role": "End User", "influence": "Low", "interest": "High", "attitude": "Neutral"},
    ]
    params = dict(
        project_id=project_id,
        stakeholders_json=json.dumps(stakeholders),
    )
    params.update(kwargs)
    return plan_stakeholder_engagement(**params)


def _make_governance(project_id: str = PROJECT, **kwargs):
    params = dict(
        project_id=project_id,
        project_criticality="Medium",
        decision_makers_json='["Sponsor", "PO"]',
    )
    params.update(kwargs)
    return plan_ba_governance(**params)


def _make_info_mgmt(project_id: str = PROJECT, **kwargs):
    params = dict(
        project_id=project_id,
        storage_tools_json='["Confluence", "Jira"]',
        traceability_level="Medium",
    )
    params.update(kwargs)
    return plan_information_management(**params)


def _make_performance(project_id: str = PROJECT, **kwargs):
    params = dict(
        project_id=project_id,
        current_issues_json='["no templates", "weak traceability"]',
    )
    params.update(kwargs)
    return evaluate_ba_performance(**params)


def _setup_full_pipeline(project_id: str = PROJECT) -> dict:
    _make_approach(project_id)
    _make_stakeholders(project_id)
    _make_governance(project_id)
    _make_info_mgmt(project_id)
    _make_performance(project_id)
    return _load(project_id)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

class TestUtils(BaseMCPTest):

    def test_safe_spaces(self):
        self.assertEqual(_safe("CRM Project"), "crm_project")

    def test_safe_already_lower(self):
        self.assertEqual(_safe("test"), "test")

    def test_safe_mixed(self):
        self.assertEqual(_safe("My BA Plan"), "my_ba_plan")

    def test_classify_high_high(self):
        q, s, f = _classify_stakeholder("High", "High")
        self.assertEqual(q, "Key Players")

    def test_classify_high_low(self):
        q, s, f = _classify_stakeholder("High", "Low")
        self.assertEqual(q, "Context Setters")

    def test_classify_low_high(self):
        q, s, f = _classify_stakeholder("Low", "High")
        self.assertEqual(q, "Subjects")

    def test_classify_low_low(self):
        q, s, f = _classify_stakeholder("Low", "Low")
        self.assertEqual(q, "Crowd")


# ---------------------------------------------------------------------------
# suggest_ba_approach (3.1)
# ---------------------------------------------------------------------------

class TestSuggestBaApproach(BaseMCPTest):

    def test_basic_success(self):
        result = _make_approach()
        self.assertIn("✅", result)
        self.assertIn(PROJECT, result)

    def test_file_created(self):
        _make_approach()
        self.assertTrue(os.path.exists(_plan_path(PROJECT)))

    def test_high_high_agile(self):
        _make_approach(change_frequency="High", uncertainty="High")
        plan = _load()
        self.assertIn("Agile", plan["ba_approach"]["recommended_approach"])

    def test_low_low_predictive(self):
        _make_approach(change_frequency="Low", uncertainty="Low")
        plan = _load()
        self.assertIn("Predictive", plan["ba_approach"]["recommended_approach"])

    def test_regulatory_override_agile(self):
        _make_approach(change_frequency="High", uncertainty="High", regulatory_need=True)
        plan = _load()
        self.assertIn("Hybrid", plan["ba_approach"]["recommended_approach"])

    def test_regulatory_no_override_predictive(self):
        """Predictive + regulatory → stays Predictive (override only for Agile/Hybrid)."""
        _make_approach(change_frequency="Low", uncertainty="Low", regulatory_need=True)
        plan = _load()
        self.assertIn("Predictive", plan["ba_approach"]["recommended_approach"])

    def test_techniques_saved(self):
        _make_approach()
        plan = _load()
        self.assertIsInstance(plan["ba_approach"]["techniques"], list)
        self.assertGreater(len(plan["ba_approach"]["techniques"]), 0)

    def test_ba_notes_saved(self):
        _make_approach(ba_notes="Hard Q2 deadline")
        plan = _load()
        self.assertEqual(plan["ba_approach"]["ba_notes"], "Hard Q2 deadline")

    def test_decided_on_today(self):
        _make_approach()
        plan = _load()
        self.assertEqual(plan["ba_approach"]["decided_on"], TODAY)

    def test_hybrid_medium_medium(self):
        _make_approach(change_frequency="Medium", uncertainty="Medium")
        plan = _load()
        self.assertIn("Hybrid", plan["ba_approach"]["recommended_approach"])

    def test_second_call_overwrites(self):
        _make_approach(change_frequency="Low", uncertainty="Low")
        _make_approach(change_frequency="High", uncertainty="High")
        plan = _load()
        self.assertIn("Agile", plan["ba_approach"]["recommended_approach"])

    def test_output_contains_techniques(self):
        result = _make_approach()
        self.assertIn("BABOK techniques", result)

    def test_output_contains_next_step(self):
        result = _make_approach()
        self.assertIn("plan_stakeholder_engagement", result)

    def test_regulatory_note_in_output(self):
        result = _make_approach(change_frequency="High", uncertainty="High", regulatory_need=True)
        self.assertIn("Regulatory override", result)


# ---------------------------------------------------------------------------
# plan_stakeholder_engagement (3.2)
# ---------------------------------------------------------------------------

class TestPlanStakeholderEngagement(BaseMCPTest):

    def test_basic_success(self):
        result = _make_stakeholders()
        self.assertIn("✅", result)

    def test_stakeholders_saved(self):
        _make_stakeholders()
        plan = _load()
        stakeholders = plan["stakeholder_engagement"]["stakeholders"]
        self.assertEqual(len(stakeholders), 2)

    def test_quadrant_assigned(self):
        _make_stakeholders()
        plan = _load()
        stakeholders = plan["stakeholder_engagement"]["stakeholders"]
        names = [s["name"] for s in stakeholders]
        self.assertIn("Sponsor", names)
        sponsor = next(s for s in stakeholders if s["name"] == "Sponsor")
        self.assertEqual(sponsor["quadrant"], "Key Players")

    def test_subjects_quadrant(self):
        _make_stakeholders()
        plan = _load()
        user = next(s for s in plan["stakeholder_engagement"]["stakeholders"]
                    if s["name"] == "User")
        self.assertEqual(user["quadrant"], "Subjects")

    def test_invalid_json(self):
        result = plan_stakeholder_engagement(PROJECT, "not-json")
        self.assertIn("❌", result)

    def test_not_list(self):
        result = plan_stakeholder_engagement(PROJECT, '{"name": "test"}')
        self.assertIn("❌", result)

    def test_empty_list(self):
        result = plan_stakeholder_engagement(PROJECT, "[]")
        self.assertIn("⚠️", result)

    def test_missing_name(self):
        bad = [{"role": "CEO", "influence": "High", "interest": "High"}]
        result = plan_stakeholder_engagement(PROJECT, json.dumps(bad))
        self.assertIn("❌", result)

    def test_invalid_influence(self):
        bad = [{"name": "X", "influence": "VeryHigh", "interest": "High"}]
        result = plan_stakeholder_engagement(PROJECT, json.dumps(bad))
        self.assertIn("❌", result)

    def test_blocker_warning(self):
        stakeholders = [
            {"name": "Blocker", "role": "CTO", "influence": "High", "interest": "Low", "attitude": "Blocker"}
        ]
        result = plan_stakeholder_engagement(PROJECT, json.dumps(stakeholders))
        self.assertIn("Blockers", result)

    def test_comm_frequency_saved(self):
        _make_stakeholders()
        plan = _load()
        sponsor = next(s for s in plan["stakeholder_engagement"]["stakeholders"]
                       if s["name"] == "Sponsor")
        self.assertIn("comm_frequency", sponsor)
        self.assertTrue(len(sponsor["comm_frequency"]) > 0)

    def test_total_count_correct(self):
        _make_stakeholders()
        plan = _load()
        self.assertEqual(plan["stakeholder_engagement"]["total"], 2)

    def test_output_contains_next_step(self):
        result = _make_stakeholders()
        self.assertIn("plan_ba_governance", result)

    def test_contact_field_saved(self):
        stakeholders = [
            {"name": "Ivan", "role": "PM", "influence": "High", "interest": "High",
             "attitude": "Champion", "contact": "ivan@test.com"}
        ]
        _make_stakeholders(stakeholders_json=json.dumps(stakeholders))
        plan = _load()
        ivan = next(s for s in plan["stakeholder_engagement"]["stakeholders"] if s["name"] == "Ivan")
        self.assertEqual(ivan["contact"], "ivan@test.com")


# ---------------------------------------------------------------------------
# plan_ba_governance (3.3)
# ---------------------------------------------------------------------------

class TestPlanBaGovernance(BaseMCPTest):

    def test_basic_success(self):
        result = _make_governance()
        self.assertIn("✅", result)

    def test_governance_saved(self):
        _make_governance()
        plan = _load()
        self.assertIn("project_criticality", plan["governance"])

    def test_high_criticality(self):
        _make_governance(project_criticality="High")
        plan = _load()
        self.assertEqual(plan["governance"]["project_criticality"], "High")
        self.assertIn("CAB", plan["governance"]["change_control"])

    def test_low_criticality(self):
        _make_governance(project_criticality="Low")
        plan = _load()
        self.assertIn("Minimal", plan["governance"]["change_control"])

    def test_decision_makers_saved(self):
        _make_governance(decision_makers_json='["Sponsor", "PO", "Lead BA"]')
        plan = _load()
        self.assertEqual(len(plan["governance"]["decision_makers"]), 3)
        self.assertIn("Sponsor", plan["governance"]["decision_makers"])

    def test_invalid_json(self):
        result = plan_ba_governance(PROJECT, "High", "not-json")
        self.assertIn("❌", result)

    def test_not_list(self):
        result = plan_ba_governance(PROJECT, "High", '{"key": "val"}')
        self.assertIn("❌", result)

    def test_custom_change_control(self):
        custom = "All CRs via a weekly meeting"
        _make_governance(change_control_process=custom)
        plan = _load()
        self.assertEqual(plan["governance"]["change_control"], custom)

    def test_default_change_control_when_empty(self):
        _make_governance(change_control_process="")
        plan = _load()
        self.assertTrue(len(plan["governance"]["change_control"]) > 0)

    def test_escalation_path_present(self):
        _make_governance()
        plan = _load()
        self.assertIn("escalation_path", plan["governance"])

    def test_output_contains_next_step(self):
        result = _make_governance()
        self.assertIn("plan_information_management", result)

    def test_defined_on_today(self):
        _make_governance()
        plan = _load()
        self.assertEqual(plan["governance"]["defined_on"], TODAY)


# ---------------------------------------------------------------------------
# plan_information_management (3.4)
# ---------------------------------------------------------------------------

class TestPlanInformationManagement(BaseMCPTest):

    def test_basic_success(self):
        result = _make_info_mgmt()
        self.assertIn("✅", result)

    def test_tools_saved(self):
        _make_info_mgmt()
        plan = _load()
        tools = plan["information_management"]["storage_tools"]
        self.assertIn("Confluence", tools)
        self.assertIn("Jira", tools)

    def test_traceability_level_saved(self):
        _make_info_mgmt(traceability_level="High")
        plan = _load()
        self.assertEqual(plan["information_management"]["traceability_level"], "High")

    def test_traceability_description_present(self):
        _make_info_mgmt(traceability_level="High")
        plan = _load()
        desc = plan["information_management"]["traceability_description"]
        self.assertIn("Full", desc)

    def test_artifact_types_saved(self):
        _make_info_mgmt(artifact_types_json='["User Story", "BRD"]')
        plan = _load()
        types = plan["information_management"]["artifact_types"]
        self.assertIn("User Story", types)

    def test_invalid_tools_json(self):
        result = plan_information_management(PROJECT, "not-json")
        self.assertIn("❌", result)

    def test_empty_tools(self):
        result = plan_information_management(PROJECT, "[]")
        self.assertIn("❌", result)

    def test_access_rules_default(self):
        _make_info_mgmt()
        plan = _load()
        self.assertIn("BA", plan["information_management"]["access_rules"])

    def test_custom_access_rules(self):
        _make_info_mgmt(access_rules="BA and PM only")
        plan = _load()
        self.assertEqual(plan["information_management"]["access_rules"], "BA and PM only")

    def test_output_contains_next_step(self):
        result = _make_info_mgmt()
        self.assertIn("evaluate_ba_performance", result)

    def test_defined_on_today(self):
        _make_info_mgmt()
        plan = _load()
        self.assertEqual(plan["information_management"]["defined_on"], TODAY)

    def test_three_tools(self):
        _make_info_mgmt(storage_tools_json='["Confluence", "Jira", "GitHub"]')
        plan = _load()
        self.assertEqual(len(plan["information_management"]["storage_tools"]), 3)


# ---------------------------------------------------------------------------
# evaluate_ba_performance (3.5)
# ---------------------------------------------------------------------------

class TestEvaluateBaPerformance(BaseMCPTest):

    def test_basic_success(self):
        result = _make_performance()
        self.assertIn("✅", result)

    def test_recommendations_generated(self):
        _make_performance()
        plan = _load()
        recs = plan["performance"]["recommendations"]
        self.assertGreater(len(recs), 0)

    def test_known_issue_matched(self):
        _make_performance(current_issues_json='["no templates"]')
        plan = _load()
        recs = [r["recommendation"] for r in plan["performance"]["recommendations"]]
        self.assertTrue(any("template" in r.lower() for r in recs))

    def test_traceability_issue_matched(self):
        _make_performance(current_issues_json='["weak traceability"]')
        plan = _load()
        recs = [r["recommendation"] for r in plan["performance"]["recommendations"]]
        self.assertTrue(any("traceability" in r.lower() for r in recs))

    def test_unknown_issue_flagged(self):
        _make_performance(current_issues_json='["mysterious problem XYZ"]')
        plan = _load()
        recs = [r["recommendation"] for r in plan["performance"]["recommendations"]]
        self.assertTrue(any("manual analysis" in r.lower() for r in recs))

    def test_empty_issues(self):
        _make_performance(current_issues_json="[]")
        plan = _load()
        recs = plan["performance"]["recommendations"]
        self.assertEqual(len(recs), 1)
        self.assertIn("retrospective", recs[0]["recommendation"].lower())

    def test_metrics_saved(self):
        metrics = [{"name": "Defect Rate", "baseline": "15%", "target": "5%"}]
        _make_performance(metrics_json=json.dumps(metrics))
        plan = _load()
        self.assertEqual(len(plan["performance"]["metrics"]), 1)
        self.assertEqual(plan["performance"]["metrics"][0]["name"], "Defect Rate")

    def test_assessed_on_today(self):
        _make_performance()
        plan = _load()
        self.assertEqual(plan["performance"]["assessed_on"], TODAY)

    def test_output_contains_save_hint(self):
        result = _make_performance()
        self.assertIn("save_ba_plan", result)

    def test_issues_count_in_output(self):
        result = _make_performance(current_issues_json='["issue1", "issue2"]')
        self.assertIn("2", result)

    def test_multiple_known_issues(self):
        issues = ["no templates", "weak traceability", "scope creep"]
        _make_performance(current_issues_json=json.dumps(issues))
        plan = _load()
        self.assertEqual(len(plan["performance"]["current_issues"]), 3)


# ---------------------------------------------------------------------------
# save_ba_plan (finalization)
# ---------------------------------------------------------------------------

class TestCh3AuditRegressions(BaseMCPTest):
    """Regression tests for the Ch3 audit findings (3.3 / 3.4 / 3.5 + save_ba_plan).

    All of these were reachable through the documented parameters and none were
    covered before: the list parameters accepted shapes that either crashed the tool
    or were silently mangled.
    """

    # --- list inputs holding non-strings crashed the tool -------------------

    def test_governance_rejects_object_decision_makers(self):
        """Was: TypeError from ', '.join(...) escaping the MCP tool."""
        result = plan_ba_governance(PROJECT, "High", '[{"role": "PO"}]')
        self.assertIn("❌", result)
        self.assertIn("decision_makers_json", result)

    def test_performance_rejects_object_issues(self):
        """Was: AttributeError — 'dict' object has no attribute 'lower'."""
        result = evaluate_ba_performance(PROJECT, current_issues_json='[{"issue": "x"}]')
        self.assertIn("❌", result)
        self.assertIn("current_issues_json", result)

    def test_info_mgmt_rejects_object_tools(self):
        result = plan_information_management(PROJECT, '[{"tool": "Jira"}]')
        self.assertIn("❌", result)
        self.assertIn("storage_tools_json", result)

    # --- a JSON scalar was shredded into characters ------------------------

    def test_artifact_types_bare_string_rejected(self):
        """Was: '"BRD"' stored as the string 'BRD' and rendered as 'B, R, D'."""
        result = plan_information_management(PROJECT, '["Confluence"]',
                                             artifact_types_json='"BRD"')
        self.assertIn("❌", result)
        self.assertIn("artifact_types_json", result)

    def test_rejected_call_writes_nothing(self):
        plan_information_management("untouched_project", '["Confluence"]',
                                    artifact_types_json='"BRD"')
        self.assertFalse(os.path.exists(_plan_path("untouched_project")))

    # --- malformed JSON was swallowed, producing a misleading verdict ------

    def test_performance_reports_malformed_issues_json(self):
        """Was: silently became [] and the tool answered 'no explicit issues'
        with a 'hold a retrospective' recommendation — about data the BA never gave."""
        result = evaluate_ba_performance(PROJECT, current_issues_json="no templates, scope creep")
        self.assertIn("❌", result)
        self.assertNotIn("retrospective", result.lower())

    def test_performance_reports_malformed_metrics_json(self):
        result = evaluate_ba_performance(PROJECT, metrics_json="{oops")
        self.assertIn("❌", result)
        self.assertIn("metrics_json", result)

    # --- governance with nobody deciding -----------------------------------

    def test_governance_rejects_empty_decision_makers(self):
        """The sibling tool already rejected an empty list; governance did not."""
        result = plan_ba_governance(PROJECT, "High", "[]")
        self.assertIn("❌", result)

    # --- happy paths must survive the stricter validation ------------------

    def test_valid_inputs_still_accepted(self):
        self.assertIn("✅", plan_ba_governance(PROJECT, "High", '["Sponsor", "PO"]'))
        self.assertIn("✅", plan_information_management(
            PROJECT, '["Confluence"]', artifact_types_json='["BRD"]'))
        self.assertIn("✅", evaluate_ba_performance(
            PROJECT, current_issues_json='["scope creep"]',
            metrics_json='[{"name": "Rework Rate", "baseline": "20%", "target": "8%"}]'))

    def test_metrics_accepts_plain_strings_too(self):
        """metrics entries may be objects OR strings — the renderer handles both."""
        result = evaluate_ba_performance(PROJECT, metrics_json='["Defect Rate"]')
        self.assertIn("✅", result)

    def test_optional_lists_may_be_omitted(self):
        self.assertIn("✅", evaluate_ba_performance(PROJECT))
        self.assertIn("✅", plan_information_management(PROJECT, '["Jira"]'))

    # --- the "empty plan" gate ignored section 3.5 -------------------------

    def test_performance_only_plan_is_not_empty(self):
        """Was: refused as 'empty or not filled in' although save_ba_plan renders
        a 3.5 section whenever performance is present."""
        evaluate_ba_performance("perf_only", current_issues_json='["no templates"]')
        result = save_ba_plan("perf_only")
        self.assertIn("✅", result)
        self.assertNotIn("empty", result.lower())

    def test_truly_empty_plan_still_warns(self):
        result = save_ba_plan("nothing_here")
        self.assertIn("⚠️", result)

    # --- the report dropped data the tools had collected -------------------

    def _full_plan(self, project_id="report_content"):
        suggest_ba_approach(project_id, "High", "High", ba_notes="APPROACH NOTE")
        plan_stakeholder_engagement(project_id, json.dumps([
            {"name": "Jane Doe", "role": "Sponsor", "influence": "High", "interest": "High"}]))
        plan_ba_governance(project_id, "High", '["Sponsor", "PO"]',
                           ba_notes="GOVERNANCE NOTE")
        plan_information_management(project_id, '["Confluence"]',
                                    artifact_types_json='["BRD", "User Story"]',
                                    ba_notes="INFO NOTE")
        evaluate_ba_performance(project_id, current_issues_json='["scope creep"]',
                                ba_notes="PERF NOTE")
        return project_id

    def _report_text(self, project_id):
        """save_artifact is mocked by conftest, so read the content it was handed."""
        with patch("skills.planning_mcp.save_artifact") as mock_save:
            save_ba_plan(project_id)
        return mock_save.call_args[0][0]

    def test_report_keeps_ba_notes_from_every_section(self):
        """Was: all four ba_notes were stored in JSON and never rendered, so the
        BA's own agreements vanished from the deliverable."""
        report = self._report_text(self._full_plan())
        for note in ("APPROACH NOTE", "GOVERNANCE NOTE", "INFO NOTE", "PERF NOTE"):
            self.assertIn(note, report, f"{note} missing from the BA Plan report")

    def test_report_keeps_artifact_types(self):
        """Was: 3.4 stored artifact_types and echoed them in its own output, but the
        report's 3.4 section omitted them entirely."""
        report = self._report_text(self._full_plan())
        self.assertIn("BRD", report)
        self.assertIn("User Story", report)

    def test_report_omits_notes_block_when_empty(self):
        """No empty '> **BA notes:**' lines when the BA left them blank."""
        plan_ba_governance("no_notes", "Low", '["Lead BA"]')
        report = self._report_text("no_notes")
        self.assertNotIn("BA notes", report)

    def test_finalize_does_not_promise_automatic_handoff(self):
        """The tool used to tell the BA governance was 'passed automatically' to 5.5,
        but no module outside planning_mcp reads ba_plan.json."""
        result = save_ba_plan(self._full_plan("promise_check"))
        self.assertNotIn("automatically\n", result)
        self.assertIn("update_stakeholder_registry", result)


class TestSaveBaPlan(BaseMCPTest):

    def test_full_plan_success(self):
        _setup_full_pipeline()
        with patch("skills.planning_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            result = save_ba_plan(PROJECT)
        self.assertIn("✅", result)

    def test_save_artifact_called(self):
        _setup_full_pipeline()
        with patch("skills.planning_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            save_ba_plan(PROJECT)
            mock_sa.assert_called_once()

    def test_status_finalized(self):
        _setup_full_pipeline()
        with patch("skills.planning_mcp.save_artifact", return_value="✅"):
            save_ba_plan(PROJECT)
        plan = _load()
        self.assertEqual(plan["status"], "finalized")

    def test_finalized_on_today(self):
        _setup_full_pipeline()
        with patch("skills.planning_mcp.save_artifact", return_value="✅"):
            save_ba_plan(PROJECT)
        plan = _load()
        self.assertEqual(plan["finalized_on"], TODAY)

    def test_empty_plan_warning(self):
        # Create an empty plan
        empty = {"project_id": "empty_ch3", "created": TODAY, "updated": TODAY,
                 "ba_approach": {}, "stakeholder_engagement": {},
                 "governance": {}, "information_management": {}, "performance": {}}
        _save_plan(empty, "empty_ch3")
        result = save_ba_plan("empty_ch3")
        self.assertIn("⚠️", result)

    def test_markdown_contains_approach(self):
        _setup_full_pipeline()
        captured = {}
        with patch("skills.planning_mcp.save_artifact") as mock_sa:
            mock_sa.side_effect = lambda c, n, project_id=None: captured.update({"content": c}) or "✅"
            save_ba_plan(PROJECT)
        self.assertIn("3.1", captured["content"])
        self.assertIn("Approach", captured["content"])

    def test_markdown_contains_stakeholders(self):
        _setup_full_pipeline()
        captured = {}
        with patch("skills.planning_mcp.save_artifact") as mock_sa:
            mock_sa.side_effect = lambda c, n, project_id=None: captured.update({"content": c}) or "✅"
            save_ba_plan(PROJECT)
        self.assertIn("Sponsor", captured["content"])

    def test_markdown_contains_governance(self):
        _setup_full_pipeline()
        captured = {}
        with patch("skills.planning_mcp.save_artifact") as mock_sa:
            mock_sa.side_effect = lambda c, n, project_id=None: captured.update({"content": c}) or "✅"
            save_ba_plan(PROJECT)
        self.assertIn("3.3", captured["content"])

    def test_artifact_name_contains_project(self):
        _setup_full_pipeline()
        captured = {}
        with patch("skills.planning_mcp.save_artifact") as mock_sa:
            mock_sa.side_effect = lambda c, n, project_id=None: captured.update({"name": n}) or "✅"
            save_ba_plan(PROJECT)
        self.assertIn("3_ba_plan", captured["name"])

    def test_json_path_in_output(self):
        _setup_full_pipeline()
        with patch("skills.planning_mcp.save_artifact", return_value="✅"):
            result = save_ba_plan(PROJECT)
        self.assertIn("ba_plan.json", result)


# ---------------------------------------------------------------------------
# Integration pipeline tests
# ---------------------------------------------------------------------------

class TestPipeline(BaseMCPTest):

    def test_full_pipeline_json_structure(self):
        """All 5 sections are filled after the full pipeline."""
        _setup_full_pipeline()
        plan = _load()
        self.assertIn("ba_approach", plan)
        self.assertIn("stakeholder_engagement", plan)
        self.assertIn("governance", plan)
        self.assertIn("information_management", plan)
        self.assertIn("performance", plan)

    def test_sections_not_empty(self):
        _setup_full_pipeline()
        plan = _load()
        self.assertTrue(len(plan["ba_approach"]) > 0)
        self.assertTrue(len(plan["stakeholder_engagement"]) > 0)
        self.assertTrue(len(plan["governance"]) > 0)
        self.assertTrue(len(plan["information_management"]) > 0)
        self.assertTrue(len(plan["performance"]) > 0)

    def test_project_id_preserved(self):
        _setup_full_pipeline()
        plan = _load()
        self.assertEqual(plan["project_id"], PROJECT)

    def test_updated_field_set(self):
        _setup_full_pipeline()
        plan = _load()
        self.assertEqual(plan["updated"], TODAY)

    def test_different_projects_isolated(self):
        proj_a = "pipeline_ch3_a"
        proj_b = "pipeline_ch3_b"
        _make_approach(project_id=proj_a, change_frequency="High", uncertainty="High")
        _make_approach(project_id=proj_b, change_frequency="Low", uncertainty="Low")
        plan_a = _load(proj_a)
        plan_b = _load(proj_b)
        self.assertIn("Agile", plan_a["ba_approach"]["recommended_approach"])
        self.assertIn("Predictive", plan_b["ba_approach"]["recommended_approach"])

    def test_later_step_does_not_overwrite_earlier(self):
        """plan_ba_governance must not overwrite ba_approach."""
        _make_approach()
        _make_governance()
        plan = _load()
        self.assertIn("recommended_approach", plan["ba_approach"])
        self.assertIn("project_criticality", plan["governance"])

    def test_stakeholder_data_in_plan_for_downstream(self):
        """Stakeholder data is available from JSON for use in 4.x."""
        _setup_full_pipeline()
        plan = _load()
        stakeholders = plan["stakeholder_engagement"]["stakeholders"]
        self.assertGreater(len(stakeholders), 0)
        # Each stakeholder has the fields needed for 4.x
        for s in stakeholders:
            self.assertIn("name", s)
            self.assertIn("role", s)
            self.assertIn("quadrant", s)
            self.assertIn("comm_frequency", s)

    def test_governance_fields_for_downstream_55(self):
        """Governance contains the fields needed for 5.5 (approval, escalation)."""
        _setup_full_pipeline()
        plan = _load()
        gov = plan["governance"]
        self.assertIn("approval_process", gov)
        self.assertIn("escalation_path", gov)
        self.assertIn("change_control", gov)


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# A2 — 3.2 seeds the living stakeholder registry that 4.2 maintains
# ---------------------------------------------------------------------------

class TestStakeholderRegistrySeeding(BaseMCPTest):

    def _registry(self, project_id=PROJECT):
        from skills.common import load_stakeholder_registry
        return load_stakeholder_registry(project_id)

    def test_registry_is_created_with_the_source_fields(self):
        _make_stakeholders()
        entries = self._registry()["stakeholders"]
        names = {e["name"] for e in entries}
        self.assertEqual(names, {"Sponsor", "User"})
        sponsor = next(e for e in entries if e["name"] == "Sponsor")
        self.assertEqual(sponsor["role"], "CEO")
        self.assertEqual(sponsor["influence"], "High")
        self.assertEqual(sponsor["interest"], "High")
        self.assertEqual(sponsor["attitude"], "Champion")

    def test_derived_fields_are_not_carried_into_the_registry(self):
        """quadrant/strategy/comm_frequency are computed from influence+interest.
        In the registry they would go stale the moment 4.2 updates those inputs."""
        _make_stakeholders()
        sponsor = next(e for e in self._registry()["stakeholders"]
                       if e["name"] == "Sponsor")
        self.assertNotIn("quadrant", sponsor)
        self.assertNotIn("strategy", sponsor)
        self.assertNotIn("comm_frequency", sponsor)

    def test_seeded_entries_are_marked_not_covered_and_sourced_to_the_plan(self):
        _make_stakeholders()
        sponsor = next(e for e in self._registry()["stakeholders"]
                       if e["name"] == "Sponsor")
        self.assertEqual(sponsor["coverage_status"], "Not covered")
        self.assertIn("3.2", sponsor["found_through"])

    def test_rerun_updates_in_place_instead_of_duplicating(self):
        _make_stakeholders()
        _make_stakeholders()
        self.assertEqual(len(self._registry()["stakeholders"]), 2)

    def test_rerun_does_not_reset_progress_recorded_by_42(self):
        """The regression insert_defaults exists for: an interview happened between
        the two 3.2 runs, and its result must survive."""
        _make_stakeholders()
        from skills.common import (load_stakeholder_registry,
                                   save_stakeholder_registry)
        registry = load_stakeholder_registry(PROJECT)
        sponsor = next(e for e in registry["stakeholders"] if e["name"] == "Sponsor")
        sponsor["coverage_status"] = "Elicited"
        sponsor["found_through"] = "J. Smith (CFO)"
        save_stakeholder_registry(PROJECT, registry)

        _make_stakeholders()

        sponsor = next(e for e in self._registry()["stakeholders"]
                       if e["name"] == "Sponsor")
        self.assertEqual(sponsor["coverage_status"], "Elicited")
        self.assertEqual(sponsor["found_through"], "J. Smith (CFO)")

    def test_validation_errors_seed_nothing(self):
        bad = json.dumps([{"name": "X", "influence": "Massive", "interest": "High"}])
        result = plan_stakeholder_engagement(project_id=PROJECT, stakeholders_json=bad)
        self.assertIn("❌", result)
        self.assertEqual(self._registry()["stakeholders"], [])

    def test_empty_list_seeds_nothing(self):
        result = plan_stakeholder_engagement(project_id=PROJECT, stakeholders_json="[]")
        self.assertIn("⚠️", result)
        self.assertEqual(self._registry()["stakeholders"], [])

    def test_registry_write_failure_warns_but_the_plan_still_saves(self):
        """Don't block — warn. A planning tool must not die on a downstream file."""
        with patch("skills.planning_mcp.update_stakeholder_registry_file",
                   return_value={"added": [], "updated": [], "dup_warnings": [],
                                 "registry": {}, "saved": False}):
            result = _make_stakeholders()
        self.assertIn("✅", result)
        self.assertIn("⚠️", result)
        plan = _load()
        self.assertEqual(len(plan["stakeholder_engagement"]["stakeholders"]), 2)
