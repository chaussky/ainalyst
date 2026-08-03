"""
tests/test_ch6_62.py — Tests for BABOK 6.2 Define Future State.

Structure:
  - Unit (10): utilities _safe, _next_goal_id, _validate_smart, _load/_save helpers
  - scope_future_state (12): initiative types, depth, custom elements, with/without 6.1
  - capture_future_state_element (11): success, update, out of scope, UX pattern 6.1, validation
  - define_goals_and_objectives (13): SMART validation, registration in 5.1, BN→BG links
  - capture_constraints (9): categories, statuses, update, validation
  - run_gap_analysis (10): with 6.1, without 6.1, change types, complexity
  - assess_potential_value (10): benefit types, validation, value profile
  - check_future_state_completeness (10): complete, partial, no scope, verdicts
  - save_future_state (8): finalization, push_to_business_context, no scope
  - Pipeline (7): full, without 6.1, scope+goals only, gap without current state
  - Integration 7.3 from_strategy_project_id (8): ADR-065 pre-fill

Total: ~108 tests
"""

import json
import os
import sys
import unittest
from datetime import date
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.conftest import setup_mocks, BaseMCPTest, make_test_repo, save_test_repo, data_file

setup_mocks()

from skills.future_state_mcp import (
    scope_future_state,
    capture_future_state_element,
    define_goals_and_objectives,
    capture_constraints,
    run_gap_analysis,
    assess_potential_value,
    check_future_state_completeness,
    save_future_state,
    _safe,
    _next_goal_id,
    _validate_smart,
    _load_scope,
    _load_state,
    _load_goals,
    _load_gap,
    VALID_ELEMENTS,
    ELEMENT_LABELS,
    DEFAULT_ELEMENTS_BY_TYPE,
)

from skills.requirements_validate_mcp import set_business_context

PROJECT = "test_project"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _scope(project=PROJECT, initiative="process_improvement", depth="standard",
           goals="", elements=""):
    return scope_future_state(
        project_id=project,
        initiative_type=initiative,
        analysis_depth=depth,
        known_goals=goals,
        elements_in_scope=elements,
    )


def _capture(project=PROJECT, element="capabilities",
             description="Automated approval process in 2 hours",
             target_metrics='{"processing_time": "2 hours"}',
             linked_bn='["BN-001"]', sources='["elicitation"]', notes=""):
    return capture_future_state_element(
        project_id=project,
        element=element,
        description=description,
        target_metrics=target_metrics,
        linked_business_needs=linked_bn,
        sources=sources,
        notes=notes,
    )


def _goal(project=PROJECT, title="Reduce request processing time",
          description="Achieve processing speed of 2 hours instead of 8",
          objectives='[{"title":"Time","metric":"hours","baseline":"8 hours","target":"2 hours","deadline":"2025-12-31"}]',
          linked_bn='["BN-001"]', register=True):
    return define_goals_and_objectives(
        project_id=project,
        goal_title=title,
        description=description,
        objectives_json=objectives,
        linked_business_needs=linked_bn,
        register_in_traceability=register,
    )


def _constraint(project=PROJECT, title="Project budget",
                category="budget", description="Budget is limited to 5M USD",
                status="confirmed", linked="[]"):
    return capture_constraints(
        project_id=project,
        constraint_title=title,
        category=category,
        description=description,
        status=status,
        linked_elements=linked,
    )


def _value(project=PROJECT,
           benefits='[{"benefit_title":"Process acceleration","benefit_type":"operational","magnitude":"high","confidence":"medium","description":"Text"}]',
           investment="medium", summary="High value at medium investment level"):
    return assess_potential_value(
        project_id=project,
        benefits_json=benefits,
        investment_level=investment,
        value_summary=summary,
    )


def _save_current_state_data(project=PROJECT):
    """Saves 6.1 test data for integration testing."""
    os.makedirs("governance_plans/data", exist_ok=True)
    # current_state_scope
    scope_data = {
        "project_id": project,
        "initiative_type": "process_improvement",
        "analysis_depth": "standard",
        "known_problems": "Processing time increased from 2 to 8 hours",
        "elements_in_scope": ["business_needs", "capabilities", "technology", "policies"],
        "session_ids_imported": [],
        "created": str(date.today()),
        "updated": str(date.today()),
    }
    with open(data_file(_safe(project), "current_state_scope.json"), "w") as f:
        json.dump(scope_data, f)

    # current_state
    state_data = {
        "project_id": project,
        "elements": {
            "capabilities": {
                "description": "Manual approval process, 8 hours, 3 levels",
                "pain_points": ["Slow", "Many errors", "No notifications"],
                "metrics": {"processing_time": "8 hours", "error_rate": "12%"},
                "sources": ["interview"],
                "notes": "",
                "draft": False,
                "last_updated": str(date.today()),
            }
        },
        "root_causes": [],
        "created": str(date.today()),
        "updated": str(date.today()),
    }
    with open(data_file(_safe(project), "current_state.json"), "w") as f:
        json.dump(state_data, f)

    # business_needs
    needs_data = {
        "project_id": project,
        "needs": [
            {
                "id": "BN-001",
                "need_title": "Speed up request processing",
                "description": "Processing time grew from 2 to 8 hours",
                "need_type": "problem",
                "priority": "High",
                "source": "Director",
                "root_cause_ids": [],
                "created": str(date.today()),
            },
            {
                "id": "BN-002",
                "need_title": "Reduce error rate",
                "description": "Errors account for 12%",
                "need_type": "problem",
                "priority": "Medium",
                "source": "Director",
                "root_cause_ids": [],
                "created": str(date.today()),
            },
        ],
        "created": str(date.today()),
        "updated": str(date.today()),
    }
    with open(data_file(_safe(project), "business_needs.json"), "w") as f:
        json.dump(needs_data, f)


def _save_future_state_goals(project=PROJECT):
    """Saves 6.2 goals test data for 7.3 integration testing."""
    os.makedirs("governance_plans/data", exist_ok=True)
    goals_data = {
        "project_id": project,
        "goals": [
            {
                "id": "BG-001",
                "goal_title": "Reduce processing time to 2 hours",
                "description": "Automate the approval workflow",
                "objectives": [
                    {
                        "title": "Processing time",
                        "metric": "hours",
                        "baseline": "8 hours",
                        "target": "2 hours",
                        "deadline": "2025-12-31",
                    }
                ],
                "linked_business_needs": ["BN-001"],
                "smart_validated": True,
                "created": str(date.today()),
            }
        ],
        "created": str(date.today()),
        "updated": str(date.today()),
    }
    with open(data_file(_safe(project), "future_state_goals.json"), "w") as f:
        json.dump(goals_data, f)


def _full_pipeline(project=PROJECT, with_current_state=True):
    """Runs the full 6.2 pipeline."""
    if with_current_state:
        _save_current_state_data(project)

    repo = make_test_repo(project)
    repo["project"] = project
    repo["requirements"] = []
    repo["links"] = []
    save_test_repo(repo, "governance_plans/data")

    _scope(project=project)
    _capture(project=project, element="capabilities")
    _capture(project=project, element="technology",
             description="Cloud platform with API integration")
    _goal(project=project)
    _constraint(project=project)
    run_gap_analysis(project_id=project)
    _value(project=project)


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestUtils(BaseMCPTest):

    def test_safe_lowercase(self):
        self.assertEqual(_safe("My Project"), "my_project")

    def test_safe_spaces_to_underscore(self):
        self.assertEqual(_safe("project 2025"), "project_2025")

    def test_safe_already_clean(self):
        self.assertEqual(_safe("test_project"), "test_project")

    def test_next_goal_id_empty(self):
        goals_data = {"goals": []}
        self.assertEqual(_next_goal_id(goals_data), "BG-001")

    def test_next_goal_id_sequential(self):
        goals_data = {"goals": [{"id": "BG-001"}, {"id": "BG-002"}]}
        self.assertEqual(_next_goal_id(goals_data), "BG-003")

    def test_next_goal_id_gap(self):
        goals_data = {"goals": [{"id": "BG-001"}, {"id": "BG-005"}]}
        self.assertEqual(_next_goal_id(goals_data), "BG-006")

    def test_validate_smart_ok(self):
        objectives = [{"title": "KPI", "metric": "hours", "baseline": "8", "target": "2", "deadline": "2025-12-31"}]
        issues = _validate_smart("Reduce request processing time", "Achieve speed", objectives)
        self.assertEqual(issues, [])

    def test_validate_smart_no_kpi(self):
        issues = _validate_smart("Improve process", "Description", [])
        self.assertTrue(any("Measurable" in i for i in issues))

    def test_validate_smart_no_target(self):
        objectives = [{"title": "KPI", "metric": "hours", "baseline": "8"}]
        issues = _validate_smart("Reduce processing time", "Description", objectives)
        self.assertTrue(any("target" in i for i in issues))

    def test_validate_smart_no_deadline(self):
        objectives = [{"title": "KPI", "metric": "hours", "baseline": "8", "target": "2"}]
        issues = _validate_smart("Reduce processing time", "Description", objectives)
        self.assertTrue(any("Time-bound" in i for i in issues))


# ---------------------------------------------------------------------------
# scope_future_state
# ---------------------------------------------------------------------------

class TestScopeFutureState(BaseMCPTest):

    def test_scope_basic_success(self):
        r = _scope()
        self.assertIn("✅", r)
        self.assertIn(PROJECT, r)

    def test_scope_creates_file(self):
        _scope()
        scope = _load_scope(PROJECT)
        self.assertIsNotNone(scope)
        self.assertEqual(scope["initiative_type"], "process_improvement")

    def test_scope_light_depth_3_elements(self):
        _scope(depth="light")
        scope = _load_scope(PROJECT)
        self.assertLessEqual(len(scope["elements_in_scope"]), 4)

    def test_scope_deep_all_8_elements(self):
        _scope(depth="deep")
        scope = _load_scope(PROJECT)
        self.assertEqual(len(scope["elements_in_scope"]), 8)

    def test_scope_standard_default_elements(self):
        _scope(initiative="new_system", depth="standard")
        scope = _load_scope(PROJECT)
        self.assertIn("business_needs", scope["elements_in_scope"])

    def test_scope_custom_elements(self):
        r = _scope(elements='["business_needs","technology"]')
        self.assertIn("✅", r)
        scope = _load_scope(PROJECT)
        self.assertEqual(scope["elements_in_scope"], ["business_needs", "technology"])

    def test_scope_invalid_element(self):
        r = _scope(elements='["unknown_element"]')
        self.assertIn("❌", r)

    def test_scope_invalid_json(self):
        r = _scope(elements="not_json")
        self.assertIn("❌", r)

    def test_scope_update(self):
        _scope(depth="light")
        r = _scope(depth="deep")
        scope = _load_scope(PROJECT)
        self.assertEqual(scope["analysis_depth"], "deep")
        self.assertIn("UPDATED", r)

    def test_scope_with_known_goals(self):
        r = _scope(goals="We want to speed up processing 4x")
        self.assertIn("Known goals", r)

    def test_scope_with_current_state_data(self):
        _save_current_state_data()
        r = _scope()
        self.assertIn("6.1 found", r)

    def test_scope_without_current_state(self):
        r = _scope()
        self.assertIn("No 6.1 data found", r)

    def test_scope_market_opportunity_all_elements(self):
        _scope(initiative="market_opportunity", depth="standard")
        scope = _load_scope(PROJECT)
        self.assertEqual(len(scope["elements_in_scope"]), 8)


# ---------------------------------------------------------------------------
# capture_future_state_element
# ---------------------------------------------------------------------------

class TestCaptureFutureStateElement(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _scope()

    def test_capture_basic_success(self):
        r = _capture()
        self.assertIn("✅", r)
        self.assertIn("capabilities", r)

    def test_capture_saves_to_state(self):
        _capture(element="capabilities", description="New automated process")
        state = _load_state(PROJECT)
        self.assertIn("capabilities", state["elements"])
        self.assertEqual(state["elements"]["capabilities"]["description"], "New automated process")

    def test_capture_update_existing(self):
        _capture(element="technology", description="First version")
        _capture(element="technology", description="Updated description")
        state = _load_state(PROJECT)
        self.assertEqual(state["elements"]["technology"]["description"], "Updated description")
        self.assertFalse(state["elements"]["technology"]["draft"])

    def test_capture_empty_description_error(self):
        r = capture_future_state_element(
            project_id=PROJECT, element="capabilities", description="   "
        )
        self.assertIn("❌", r)

    def test_capture_invalid_target_metrics_json(self):
        r = capture_future_state_element(
            project_id=PROJECT, element="capabilities",
            description="Description", target_metrics="not_json"
        )
        self.assertIn("❌", r)

    def test_capture_invalid_linked_bn_json(self):
        r = capture_future_state_element(
            project_id=PROJECT, element="capabilities",
            description="Description", linked_business_needs="not_json"
        )
        self.assertIn("❌", r)

    def test_capture_target_metrics_stored(self):
        _capture(target_metrics='{"speed": "2h", "accuracy": "99%"}')
        state = _load_state(PROJECT)
        self.assertEqual(state["elements"]["capabilities"]["target_metrics"]["speed"], "2h")

    def test_capture_linked_bn_stored(self):
        _capture(linked_bn='["BN-001","BN-002"]')
        state = _load_state(PROJECT)
        self.assertIn("BN-001", state["elements"]["capabilities"]["linked_business_needs"])

    def test_capture_shows_current_state_context(self):
        _save_current_state_data()
        r = _capture(element="capabilities")
        self.assertIn("current state", r.lower())

    def test_capture_out_of_scope_warning(self):
        r = capture_future_state_element(
            project_id=PROJECT,
            element="external",  # not in the standard process_improvement scope
            description="External partners",
        )
        # Should save but warn
        state = _load_state(PROJECT)
        self.assertIn("external", state["elements"])

    def test_capture_progress_shown(self):
        r = _capture(element="capabilities")
        self.assertIn("Progress", r)


# ---------------------------------------------------------------------------
# define_goals_and_objectives
# ---------------------------------------------------------------------------

class TestDefineGoalsAndObjectives(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _scope()

    def test_goal_basic_success(self):
        r = _goal()
        self.assertIn("✅", r)
        self.assertIn("BG-001", r)

    def test_goal_saved_to_file(self):
        _goal()
        goals_data = _load_goals(PROJECT)
        self.assertEqual(len(goals_data["goals"]), 1)
        self.assertEqual(goals_data["goals"][0]["id"], "BG-001")

    def test_goal_sequential_ids(self):
        _goal(title="Goal 1")
        _goal(title="Goal 2")
        goals_data = _load_goals(PROJECT)
        ids = [g["id"] for g in goals_data["goals"]]
        self.assertIn("BG-001", ids)
        self.assertIn("BG-002", ids)

    def test_goal_smart_valid(self):
        r = _goal()
        self.assertIn("SMART criteria met", r)
        goals_data = _load_goals(PROJECT)
        self.assertTrue(goals_data["goals"][0]["smart_validated"])

    def test_goal_smart_no_kpi_warning(self):
        r = define_goals_and_objectives(
            project_id=PROJECT,
            goal_title="Improve process",
            description="Description",
            objectives_json="[]",
        )
        self.assertIn("SMART notes", r)

    def test_goal_empty_title_error(self):
        r = define_goals_and_objectives(
            project_id=PROJECT, goal_title="", description="Description",
            objectives_json="[]"
        )
        self.assertIn("❌", r)

    def test_goal_invalid_objectives_json(self):
        r = define_goals_and_objectives(
            project_id=PROJECT, goal_title="Goal",
            description="Description", objectives_json="not_json"
        )
        self.assertIn("❌", r)

    def test_goal_registers_in_traceability(self):
        repo = make_test_repo(PROJECT)
        repo["project"] = PROJECT
        repo["requirements"] = []
        repo["links"] = []
        save_test_repo(repo, "governance_plans/data")

        _goal(linked_bn='["BN-001"]', register=True)

        with open(data_file(_safe(PROJECT), "traceability_repo.json")) as f:
            updated_repo = json.load(f)

        ids = [r["id"] for r in updated_repo["requirements"]]
        self.assertIn("BG-001", ids)

    def test_goal_creates_bn_bg_link(self):
        repo = make_test_repo(PROJECT)
        repo["project"] = PROJECT
        # BN-001 must EXIST for the link to be written. The fixture used to leave the
        # repository empty and still assert the edge, encoding the dangling-edge
        # behaviour 6.2 has since stopped producing: an edge to a node that is not in
        # the graph made the coverage audit report the objective as justified.
        # The missing-target case is covered by tests/test_graph_contracts.py.
        repo["requirements"] = [
            {"id": "BN-001", "type": "business_need", "title": "Cut the cycle",
             "version": "1.0", "status": "confirmed"},
        ]
        repo["links"] = []
        save_test_repo(repo, "governance_plans/data")

        _goal(linked_bn='["BN-001"]')

        with open(data_file(_safe(PROJECT), "traceability_repo.json")) as f:
            updated_repo = json.load(f)

        links = updated_repo["links"]
        derives_links = [l for l in links if l["relation"] == "derives"]
        self.assertTrue(any(l["from"] == "BG-001" and l["to"] == "BN-001" for l in derives_links))

    def test_goal_no_repo_warning(self):
        r = _goal(register=True)
        self.assertIn("does not exist yet", r.lower())

    def test_the_warning_promises_only_what_the_platform_does(self):
        """G-1. The message used to say that creating the repository would add this
        node "automatically". There is no back-fill: registration is a side effect of
        THIS call, so the analyst followed the instruction, got an empty graph, and
        nothing said so. 6.2 did not even offer the manual route 6.1 mentioned."""
        r = _goal(register=True)
        self.assertNotIn("will then be added automatically", r)
        self.assertIn("not be added retroactively", r)
        self.assertIn("requirements_json", r, "no route that actually works was named")

    def test_goal_register_false_no_repo_needed(self):
        r = _goal(register=False)
        self.assertIn("BG-001", r)
        # Without repository there should be no error

    def test_goal_linked_bn_stored(self):
        _goal(linked_bn='["BN-001","BN-002"]')
        goals_data = _load_goals(PROJECT)
        self.assertIn("BN-001", goals_data["goals"][0]["linked_business_needs"])

    def test_goal_objectives_stored(self):
        _goal()
        goals_data = _load_goals(PROJECT)
        objectives = goals_data["goals"][0]["objectives"]
        self.assertEqual(objectives[0]["target"], "2 hours")


# ---------------------------------------------------------------------------
# capture_constraints
# ---------------------------------------------------------------------------

class TestCaptureConstraints(BaseMCPTest):

    def test_constraint_basic_success(self):
        r = _constraint()
        self.assertIn("✅", r)
        self.assertIn("Project budget", r)

    def test_constraint_saved_to_state(self):
        _constraint(title="Budget", category="budget", description="5M USD")
        state = _load_state(PROJECT)
        self.assertEqual(len(state["constraints"]), 1)
        self.assertEqual(state["constraints"][0]["title"], "Budget")

    def test_constraint_multiple_categories(self):
        _constraint(title="Budget", category="budget")
        _constraint(title="Deadline", category="time", description="Launch by 01.04")
        _constraint(title="Compliance-152", category="compliance", description="Regulatory compliance")
        state = _load_state(PROJECT)
        self.assertEqual(len(state["constraints"]), 3)

    def test_constraint_assumed_status_warning(self):
        r = _constraint(status="assumed")
        self.assertIn("assumption", r.lower())

    def test_constraint_confirmed_status(self):
        r = _constraint(status="confirmed")
        self.assertIn("Confirmed", r)

    def test_constraint_empty_title_error(self):
        r = capture_constraints(
            project_id=PROJECT, constraint_title="",
            category="budget", description="Description", status="confirmed"
        )
        self.assertIn("❌", r)

    def test_constraint_empty_description_error(self):
        r = capture_constraints(
            project_id=PROJECT, constraint_title="Budget",
            category="budget", description="", status="confirmed"
        )
        self.assertIn("❌", r)

    def test_constraint_invalid_linked_elements(self):
        r = capture_constraints(
            project_id=PROJECT, constraint_title="Constraint",
            category="other", description="Description", status="confirmed",
            linked_elements='["unknown_element"]'
        )
        self.assertIn("❌", r)

    def test_constraint_update_existing(self):
        _constraint(title="Budget", description="First description")
        _constraint(title="Budget", description="Updated description")
        state = _load_state(PROJECT)
        budget_items = [c for c in state["constraints"] if c["title"] == "Budget"]
        self.assertEqual(len(budget_items), 1)
        self.assertEqual(budget_items[0]["description"], "Updated description")


# ---------------------------------------------------------------------------
# run_gap_analysis
# ---------------------------------------------------------------------------

class TestRunGapAnalysis(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _scope()
        _capture(element="capabilities", description="Automated process")
        _capture(element="technology", description="Cloud platform")

    def test_gap_basic_success(self):
        r = run_gap_analysis(project_id=PROJECT)
        self.assertIn("✅", r)
        self.assertIn("Gap analysis completed", r)

    def test_gap_creates_file(self):
        run_gap_analysis(project_id=PROJECT)
        gap = _load_gap(PROJECT)
        self.assertIsNotNone(gap)
        self.assertIn("gaps", gap)

    def test_gap_elements_count(self):
        run_gap_analysis(project_id=PROJECT)
        gap = _load_gap(PROJECT)
        self.assertEqual(len(gap["gaps"]), 2)

    def test_gap_without_current_state(self):
        run_gap_analysis(project_id=PROJECT)
        gap = _load_gap(PROJECT)
        self.assertFalse(gap["has_current_state_baseline"])
        for g in gap["gaps"]:
            self.assertEqual(g["change_type"], "new")
            self.assertIsNone(g["current_description"])

    def test_gap_with_current_state(self):
        _save_current_state_data()
        run_gap_analysis(project_id=PROJECT)
        gap = _load_gap(PROJECT)
        self.assertTrue(gap["has_current_state_baseline"])
        caps_gap = next((g for g in gap["gaps"] if g["element"] == "capabilities"), None)
        self.assertIsNotNone(caps_gap)
        self.assertIsNotNone(caps_gap["current_description"])

    def test_gap_improve_type_with_current_state(self):
        _save_current_state_data()
        run_gap_analysis(project_id=PROJECT)
        gap = _load_gap(PROJECT)
        caps_gap = next((g for g in gap["gaps"] if g["element"] == "capabilities"), None)
        self.assertEqual(caps_gap["change_type"], "improve")

    def test_gap_sets_done_flag(self):
        run_gap_analysis(project_id=PROJECT)
        state = _load_state(PROJECT)
        self.assertTrue(state["gap_analysis_done"])

    def test_gap_no_elements_error(self):
        # Empty project
        r = run_gap_analysis(project_id="empty_project")
        self.assertIn("⚠️", r)

    def test_gap_summary_in_report(self):
        run_gap_analysis(project_id=PROJECT)
        # Verify that the type summary is present in the report
        r = run_gap_analysis(project_id=PROJECT)
        self.assertIn("summary", r.lower())

    def test_gap_complexity_assigned(self):
        _save_current_state_data()
        run_gap_analysis(project_id=PROJECT)
        gap = _load_gap(PROJECT)
        for g in gap["gaps"]:
            self.assertIn(g["complexity"], ["low", "medium", "high"])


# ---------------------------------------------------------------------------
# assess_potential_value
# ---------------------------------------------------------------------------

class TestAssessPotentialValue(BaseMCPTest):

    def test_value_basic_success(self):
        r = _value()
        self.assertIn("✅", r)
        self.assertIn("Potential value assessed", r)

    def test_value_saved_to_state(self):
        _value()
        state = _load_state(PROJECT)
        self.assertIsNotNone(state["potential_value"])
        self.assertEqual(state["potential_value"]["investment_level"], "medium")

    def test_value_multiple_benefits(self):
        benefits = json.dumps([
            {"benefit_title": "Acceleration", "benefit_type": "operational", "magnitude": "high", "confidence": "medium"},
            {"benefit_title": "Cost reduction", "benefit_type": "financial", "magnitude": "medium", "confidence": "high"},
        ])
        r = assess_potential_value(project_id=PROJECT, benefits_json=benefits, investment_level="medium")
        self.assertIn("✅", r)

    def test_value_invalid_benefit_type(self):
        benefits = json.dumps([
            {"benefit_title": "Acceleration", "benefit_type": "unknown_type", "magnitude": "high", "confidence": "medium"}
        ])
        r = assess_potential_value(project_id=PROJECT, benefits_json=benefits, investment_level="medium")
        self.assertIn("❌", r)

    def test_value_invalid_magnitude(self):
        benefits = json.dumps([
            {"benefit_title": "Acceleration", "benefit_type": "operational", "magnitude": "extreme", "confidence": "medium"}
        ])
        r = assess_potential_value(project_id=PROJECT, benefits_json=benefits, investment_level="medium")
        self.assertIn("❌", r)

    def test_value_invalid_confidence(self):
        benefits = json.dumps([
            {"benefit_title": "Acceleration", "benefit_type": "operational", "magnitude": "high", "confidence": "very_high"}
        ])
        r = assess_potential_value(project_id=PROJECT, benefits_json=benefits, investment_level="medium")
        self.assertIn("❌", r)

    def test_value_empty_benefits_error(self):
        r = assess_potential_value(project_id=PROJECT, benefits_json="[]", investment_level="medium")
        self.assertIn("❌", r)

    def test_value_investment_levels(self):
        for level in ["low", "medium", "high", "unknown"]:
            r = assess_potential_value(
                project_id=PROJECT,
                benefits_json='[{"benefit_title":"B","benefit_type":"operational","magnitude":"high","confidence":"medium"}]',
                investment_level=level,
            )
            self.assertIn("✅", r)

    def test_value_profile_attractive(self):
        r = assess_potential_value(
            project_id=PROJECT,
            benefits_json='[{"benefit_title":"B","benefit_type":"operational","magnitude":"high","confidence":"high"}]',
            investment_level="low",
        )
        self.assertIn("Attractive", r)

    def test_value_summary_stored(self):
        _value(summary="Very attractive value profile")
        state = _load_state(PROJECT)
        self.assertEqual(state["potential_value"]["value_summary"], "Very attractive value profile")


# ---------------------------------------------------------------------------
# check_future_state_completeness
# ---------------------------------------------------------------------------

class TestCheckFutureStateCompleteness(BaseMCPTest):

    def test_check_no_scope_error(self):
        r = check_future_state_completeness(project_id=PROJECT)
        self.assertIn("⚠️", r)
        self.assertIn("scope", r.lower())

    def test_check_incomplete_no_elements(self):
        _scope()
        r = check_future_state_completeness(project_id=PROJECT)
        self.assertIn("⚠️", r)
        self.assertNotIn("✅ Analysis ready for finalization", r)

    def test_check_no_goals_warning(self):
        _scope()
        _capture()
        r = check_future_state_completeness(project_id=PROJECT)
        self.assertIn("goal", r.lower())

    def test_check_no_gap_warning(self):
        _scope()
        _capture()
        _goal()
        _constraint()
        _value()
        r = check_future_state_completeness(project_id=PROJECT)
        self.assertIn("Gap", r)

    def test_check_no_constraints_warning(self):
        _scope()
        _capture()
        _goal()
        r = check_future_state_completeness(project_id=PROJECT)
        self.assertIn("constraint", r.lower())

    def test_check_readiness_percentage(self):
        _scope()
        _capture()
        r = check_future_state_completeness(project_id=PROJECT)
        self.assertIn("%", r)

    def test_check_bn_coverage_with_61_data(self):
        _save_current_state_data()
        _scope()
        _capture()
        _goal(linked_bn='["BN-001"]')  # BN-002 not linked
        _constraint()
        run_gap_analysis(project_id=PROJECT)
        _value()
        r = check_future_state_completeness(project_id=PROJECT)
        self.assertIn("BN-002", r)

    def test_check_goals_without_kpi(self):
        _scope()
        _capture()
        define_goals_and_objectives(
            project_id=PROJECT,
            goal_title="Improve something",
            description="Description",
            objectives_json="[]",
        )
        r = check_future_state_completeness(project_id=PROJECT)
        self.assertIn("KPI", r)

    def test_check_all_passed(self):
        # Scope with 2 elements, both filled
        scope_future_state(
            project_id=PROJECT,
            initiative_type="process_improvement",
            analysis_depth="light",
            elements_in_scope='["capabilities","technology"]',
        )
        _capture(element="capabilities")
        _capture(element="technology", description="Cloud platform")
        _goal()
        _constraint()
        run_gap_analysis(project_id=PROJECT)
        _value()
        r = check_future_state_completeness(project_id=PROJECT)
        self.assertIn("100%", r)

    def test_check_no_value_warning(self):
        _scope()
        _capture()
        _goal()
        _constraint()
        run_gap_analysis(project_id=PROJECT)
        # Without value assessment
        r = check_future_state_completeness(project_id=PROJECT)
        self.assertIn("value", r.lower())


# ---------------------------------------------------------------------------
# save_future_state
# ---------------------------------------------------------------------------

class TestTheDocumentAgreesWithTheGraph(BaseMCPTest):
    """G-3. A business goal lives in TWO stores: 6.2's own JSON and the node 5.1 holds.
    Chapter 5 tools write the graph, 6.2 re-reads only its own copy, and both render
    documents with equal confidence. In one minute, one project, the analyst got two
    different titles for BG-001 and a retired goal shown as live with a SMART tick."""

    def _rebuild(self):
        with patch("skills.future_state_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            save_future_state(project_id=PROJECT, project_title="Project")
            return mock_sa.call_args[0][0]

    def _graph_edit(self, goal_id, **fields):
        import skills.future_state_mcp as mod
        repo = mod._load_repo(PROJECT)
        for node in repo["requirements"]:
            if node["id"] == goal_id:
                node.update(fields)
        mod._save_repo(repo)

    def test_a_title_changed_in_the_graph_is_not_silently_overwritten(self):
        _full_pipeline()
        self._graph_edit("BG-001", title="Make the application visible to the customer",
                         version="2.0")
        doc = self._rebuild()
        self.assertIn("Make the application visible to the customer", doc,
                       "6.2 redrew its own stale copy as if nothing had happened")
        self.assertIn("differs", doc.lower())

    def test_a_superseded_need_is_not_offered_as_a_live_justification(self):
        import skills.future_state_mcp as mod
        _full_pipeline()
        repo = mod._load_repo(PROJECT)
        repo["requirements"].append(
            {"id": "BN-001", "type": "business_need", "title": "Applications get lost",
             "version": "1.0", "status": "superseded"})
        mod._save_repo(repo)
        doc = self._rebuild()
        bn_lines = [ln for ln in doc.split("\n") if "Addresses BN" in ln]
        self.assertTrue(bn_lines, doc)
        for line in bn_lines:
            self.assertIn("archived", line.lower(),
                          f"a superseded need was cited as a standing justification: {line}")

    def test_a_goal_retired_in_the_graph_is_not_shown_as_live(self):
        _full_pipeline()
        self._graph_edit("BG-001", status="retired")
        doc = self._rebuild()
        goal_heading = [ln for ln in doc.split("\n") if ln.startswith("### BG-001")]
        self.assertTrue(goal_heading, doc)
        self.assertIn("archived", goal_heading[0].lower(),
                      "a retired goal was presented as a live one")


class TestSaveFutureState(BaseMCPTest):

    def test_save_no_scope_error(self):
        r = save_future_state(project_id=PROJECT, project_title="Test")
        self.assertIn("⚠️", r)

    def test_save_basic_success(self):
        _full_pipeline()
        r = save_future_state(project_id=PROJECT, project_title="Acceleration Project")
        self.assertIn("✅", r)
        self.assertIn("Acceleration Project", r)

    def test_save_creates_report_artifact(self):
        from unittest.mock import patch
        _full_pipeline()
        with patch("skills.future_state_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            save_future_state(project_id=PROJECT, project_title="Project")
            mock_sa.assert_called()

    def test_save_statistics_in_response(self):
        _full_pipeline()
        r = save_future_state(project_id=PROJECT, project_title="Project")
        self.assertIn("Statistics", r)
        self.assertIn("Gap analysis", r)

    def test_save_push_to_business_context(self):
        _full_pipeline()
        r = save_future_state(project_id=PROJECT, project_title="Project",
                              push_to_business_context=True)
        self.assertIn("7.3", r)
        self.assertIn("from_strategy_project_id", r)

    def test_save_draft_warning(self):
        _scope()
        state = _load_state(PROJECT)
        state["elements"]["capabilities"] = {"description": "Draft", "draft": True, "last_updated": str(date.today())}
        from skills.future_state_mcp import _save_state
        _save_state(state)
        r = save_future_state(project_id=PROJECT, project_title="Project")
        self.assertIn("Drafts", r)

    def test_save_analyst_notes_in_report(self):
        from unittest.mock import patch
        _full_pipeline()
        with patch("skills.future_state_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            save_future_state(
                project_id=PROJECT, project_title="Project",
                analyst_notes="Important analyst note"
            )
            call_args = mock_sa.call_args
            report = call_args[0][0]
            self.assertIn("Important analyst note", report)

    def test_save_next_steps_in_response(self):
        _full_pipeline()
        r = save_future_state(project_id=PROJECT, project_title="Project")
        self.assertIn("6.4", r)
        self.assertIn("7.3", r)


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------

class TestPipeline(BaseMCPTest):

    def test_full_pipeline_with_61(self):
        _full_pipeline(with_current_state=True)
        r = save_future_state(project_id=PROJECT, project_title="Full Pipeline")
        self.assertIn("✅", r)

    def test_pipeline_without_61(self):
        _full_pipeline(with_current_state=False)
        r = save_future_state(project_id=PROJECT, project_title="Pipeline without 6.1")
        self.assertIn("✅", r)

    def test_pipeline_gap_without_current_state_new_type(self):
        _scope()
        _capture()
        run_gap_analysis(project_id=PROJECT)
        gap = _load_gap(PROJECT)
        for g in gap["gaps"]:
            self.assertEqual(g["change_type"], "new")

    def test_pipeline_goals_registered_in_51(self):
        repo = make_test_repo(PROJECT)
        repo["project"] = PROJECT
        repo["requirements"] = []
        repo["links"] = []
        save_test_repo(repo, "governance_plans/data")

        _scope()
        _goal(title="Goal 1", register=True)
        _goal(title="Goal 2", register=True)

        with open(data_file(_safe(PROJECT), "traceability_repo.json")) as f:
            updated_repo = json.load(f)

        ids = [r["id"] for r in updated_repo["requirements"]]
        self.assertIn("BG-001", ids)
        self.assertIn("BG-002", ids)

    def test_pipeline_completeness_all_green_after_full(self):
        # Explicitly restrict scope to only the elements we fill in
        scope_future_state(
            project_id=PROJECT,
            initiative_type="process_improvement",
            analysis_depth="light",
            elements_in_scope='["capabilities","technology"]',
        )
        _save_current_state_data(PROJECT)
        repo = make_test_repo(PROJECT)
        repo["project"] = PROJECT
        repo["requirements"] = []
        repo["links"] = []
        save_test_repo(repo, "governance_plans/data")
        _capture(element="capabilities")
        _capture(element="technology", description="Cloud platform")
        _goal(linked_bn='["BN-001","BN-002"]')
        _constraint()
        run_gap_analysis(project_id=PROJECT)
        _value()
        r = check_future_state_completeness(project_id=PROJECT)
        self.assertIn("100%", r)

    def test_pipeline_multiple_constraints_stored(self):
        _scope()
        _constraint(title="Budget", category="budget")
        _constraint(title="Deadline", category="time", description="Q4 2025")
        _constraint(title="Compliance-152", category="compliance", description="Regulatory compliance")
        state = _load_state(PROJECT)
        self.assertEqual(len(state["constraints"]), 3)

    def test_pipeline_scope_and_goals_only_no_error(self):
        """Minimal pipeline: only scope and one goal — must not raise exceptions."""
        try:
            _scope()
            _goal()
            r = check_future_state_completeness(project_id=PROJECT)
            # Should work without exceptions — return warnings, not crash
            self.assertIn("⚠️", r)
            self.assertIn("Warnings", r)
        except Exception as e:
            self.fail(f"pipeline without errors must not raise exceptions: {e}")


# ---------------------------------------------------------------------------
# Integration 7.3 from_strategy_project_id (ADR-065)
# ---------------------------------------------------------------------------

class TestIntegration73(BaseMCPTest):

    def test_from_strategy_with_62_goals(self):
        _save_future_state_goals()
        _scope()
        state_data = {
            "project_id": PROJECT,
            "elements": {"capabilities": {"description": "Automated process", "draft": False}},
            "constraints": [],
            "potential_value": None,
            "gap_analysis_done": False,
            "created": str(date.today()),
            "updated": str(date.today()),
        }
        with open(data_file(_safe(PROJECT), "future_state.json"), "w") as f:
            json.dump(state_data, f)

        r = set_business_context(
            project_id=PROJECT,
            business_goals_json="[]",
            future_state="",
            solution_scope="",
            from_strategy_project_id=PROJECT,
        )
        self.assertIn("BG-001", r)

    def test_from_strategy_fills_business_goals(self):
        _save_future_state_goals()
        r = set_business_context(
            project_id=PROJECT,
            business_goals_json="[]",
            future_state="Future state",
            solution_scope="Scope",
            from_strategy_project_id=PROJECT,
        )
        self.assertIn("6.2", r)

    def test_from_strategy_fills_future_state(self):
        _scope()
        state_data = {
            "project_id": PROJECT,
            "elements": {"capabilities": {"description": "Automated process in 2 hours", "draft": False}},
            "constraints": [],
            "potential_value": None,
            "gap_analysis_done": False,
            "created": str(date.today()),
            "updated": str(date.today()),
        }
        with open(data_file(_safe(PROJECT), "future_state.json"), "w") as f:
            json.dump(state_data, f)
        scope_data = {
            "project_id": PROJECT,
            "initiative_type": "process_improvement",
            "elements_in_scope": ["capabilities"],
            "analysis_depth": "standard",
            "created": str(date.today()),
            "updated": str(date.today()),
        }
        with open(data_file(_safe(PROJECT), "future_state_scope.json"), "w") as f:
            json.dump(scope_data, f)

        r = set_business_context(
            project_id=PROJECT,
            business_goals_json='[{"id":"BG-001","title":"Goal"}]',
            future_state="",
            solution_scope="",
            from_strategy_project_id=PROJECT,
        )
        self.assertIn("6.2", r)

    def test_from_strategy_fallback_to_61_bn(self):
        """If 6.2 is absent but 6.1 exists — pre-fills from BN."""
        _save_current_state_data()
        r = set_business_context(
            project_id=PROJECT,
            business_goals_json="[]",
            future_state="Future state",
            solution_scope="Scope",
            from_strategy_project_id=PROJECT,
        )
        # R1-1: prefilled objectives keep the REAL business-need id (BN-001), not a
        # synthesised BG-{n}, so graph traceability from a requirement matches.
        self.assertIn("BN-001", r)

    def test_from_strategy_no_data_warning(self):
        r = set_business_context(
            project_id=PROJECT,
            business_goals_json='[{"id":"BG-001","title":"Goal"}]',
            future_state="Future state",
            solution_scope="Scope",
            from_strategy_project_id="nonexistent_project",
        )
        self.assertIn("⚠️", r)

    def test_deprecated_from_current_state_warning(self):
        _save_current_state_data()
        r = set_business_context(
            project_id=PROJECT,
            business_goals_json="[]",
            future_state="Future state",
            solution_scope="Scope",
            from_current_state_project_id=PROJECT,
        )
        self.assertIn("deprecated", r.lower())

    def test_deprecated_still_works(self):
        """Deprecated parameter still works but shows a warning."""
        _save_current_state_data()
        r = set_business_context(
            project_id=PROJECT,
            business_goals_json="[]",
            future_state="Future state",
            solution_scope="Scope",
            from_current_state_project_id=PROJECT,
        )
        # Should pre-fill (with the real BN id, R1-1) and warn
        self.assertIn("BN-001", r)
        self.assertIn("deprecated", r.lower())

    def test_from_strategy_does_not_override_explicit_goals(self):
        """from_strategy_project_id does not override explicitly passed goals."""
        _save_future_state_goals()
        r = set_business_context(
            project_id=PROJECT,
            business_goals_json='[{"id":"BG-999","title":"Explicit goal"}]',
            future_state="Future state",
            solution_scope="Scope",
            from_strategy_project_id=PROJECT,
        )
        self.assertIn("BG-999", r)


if __name__ == "__main__":
    unittest.main(verbosity=2)
