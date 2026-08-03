"""
tests/test_e2e3_findings.py — regression tests for defects found in the
E2E #3 (hr_onboard) untrodden-route audit. Each test fails on the pre-fix code.

Findings covered:
  F-C  malformed JSON SHAPE (scalar / list-of-strings) must return "❌", not raise
       (deprecate_requirements 5.2, open_cr 5.4, prepare_approval_package 5.5,
        define_solution_scope 6.4) — same class as CH3-A/B, CH4-A.
  F-D  generate_recommendation must reach 6.2 potential_value when source_ids is empty.
  F-E  save_change_strategy must not crash when a 7.5 surrogate wrote scope as a string.
  F-A  7.3 must not claim alignment/coverage from a title word-overlap with no graph edge.
  F-B  7.3 validated verdict must read the durable fact, not the mutable status.
"""
import json
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tests.conftest import BaseMCPTest

import skills.requirements_maintain_mcp as mod52
import skills.requirements_assess_changes_mcp as mod54
import skills.requirements_approve_mcp as mod55
import skills.change_strategy_mcp as mod64


# ---------------------------------------------------------------------------
# F-C — a wrong JSON SHAPE (an LLM writing a scalar or a list of strings where
# objects are expected) must produce a readable "❌", never an escaping
# TypeError/AttributeError (which surfaces to the BA as an opaque protocol error).
# ---------------------------------------------------------------------------

class TestFC_ShapeGuards(BaseMCPTest):

    def test_deprecate_requirements_scalar_returns_error(self):
        out = mod52.deprecate_requirements(
            project_name="hr_onboard", req_ids_json="42",
            final_status="deprecated", reason="probe")
        self.assertIsInstance(out, str)
        self.assertTrue(out.startswith("❌"), out[:120])

    def test_deprecate_requirements_object_returns_error(self):
        out = mod52.deprecate_requirements(
            project_name="hr_onboard", req_ids_json='{"a": 1}',
            final_status="deprecated", reason="probe")
        self.assertTrue(out.startswith("❌"), out[:120])

    def test_open_cr_scalar_returns_error(self):
        out = mod54.open_cr(
            project_name="hr_onboard", cr_id="CR-P", title="p", description="d",
            initiator="i", cr_type="change_existing", formality="standard",
            target_req_ids_json="42")
        self.assertIsInstance(out, str)
        self.assertTrue(out.startswith("❌"), out[:120])

    def test_prepare_approval_package_scalar_returns_error(self):
        out = mod55.prepare_approval_package(
            project_name="hr_onboard", package_id="PKG-P", package_title="p",
            req_ids_json="42", approach="predictive")
        self.assertIsInstance(out, str)
        self.assertTrue(out.startswith("❌"), out[:120])

    def test_define_solution_scope_list_of_strings_returns_error(self):
        out = mod64.define_solution_scope(
            project_id="hr_onboard", capabilities_json='["Payroll", "Portal"]')
        self.assertIsInstance(out, str)
        self.assertTrue(out.startswith("❌"), out[:120])


# ---------------------------------------------------------------------------
# F-E — a 7.5 surrogate writes `scope` as a flat STRING; 6.4 readers index it as a
# dict. _normalize_strategy must coerce it so save_change_strategy does not crash.
# ---------------------------------------------------------------------------

class TestFE_ScopeStringGuard(unittest.TestCase):

    def test_normalize_coerces_string_scope_to_dict(self):
        out = mod64._normalize_strategy({"scope": "Automate onboarding only"}, "hr_onboard")
        self.assertIsInstance(out["scope"], dict)
        self.assertIn("Automate onboarding only", json.dumps(out["scope"]))

    def test_dict_scope_readers_do_not_raise_on_former_string(self):
        strat = mod64._normalize_strategy({"scope": "flat text"}, "hr_onboard")
        # save_change_strategy does strategy.get('scope', {}).get('change_type', '')
        self.assertEqual(strat["scope"].get("change_type", ""), "")


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# F-D — generate_recommendation (6.3) must reach the 6.2 potential_value even when
# the BA named no explicit sources (scope stores source_project_ids as []).
# ---------------------------------------------------------------------------

class TestFD_RecommendationPullsValue(BaseMCPTest):

    def test_recommendation_reaches_62_value_with_empty_sources(self):
        import skills.future_state_mcp as fs
        import skills.risk_assessment_mcp as risk
        pid = "hr_onboard"
        marker = "PRODUCTIVITY_MARKER_XYZ"
        fs.assess_potential_value(
            pid,
            benefits_json=json.dumps([{"benefit_title": "b", "benefit_type": "operational",
                                       "magnitude": "high", "confidence": "medium",
                                       "description": "d"}]),
            investment_level="medium", value_summary=marker)
        # source_project_ids defaults to "[]" -> stored as []
        risk.scope_risk_assessment(pid, "process_improvement", "standard")
        risk.add_risk(pid, category="technical", source="future_state",
                      description="If X then Y happens", likelihood=3, impact=3,
                      response_strategy="accept")
        risk.set_risk_tolerance(pid, "neutral")
        risk.run_risk_matrix(pid)
        out = risk.generate_recommendation(pid)
        self.assertIn(marker, out)


# ---------------------------------------------------------------------------
# F-A — 7.3 must read alignment/coverage from the graph edges only. A title
# word-overlap with no link must be advisory, never counted as aligned/covered.
# ---------------------------------------------------------------------------

class TestFA_GraphTruthAlignment(BaseMCPTest):

    def test_title_overlap_without_edge_is_not_alignment(self):
        import skills.requirements_traceability_mcp as trace
        import skills.requirements_validate_mcp as val
        pid = "hr_onboard"
        trace.init_traceability_repo(pid, "Standard", json.dumps([
            {"id": "FR-DECOY", "type": "functional",
             "title": "Access badge printing for site visitors", "status": "draft"}]))
        val.set_business_context(
            pid,
            business_goals_json=json.dumps([{"id": "BG-001",
                "title": "100% access provisioned by day 1", "description": "", "kpi": ""}]),
            future_state="future", solution_scope="scope")
        out = val.check_business_alignment(pid, req_ids='["FR-DECOY"]')
        self.assertIn("0 (0.0%)", out)            # nothing counted as aligned
        self.assertIn("Title match only", out)    # advisory summary row
        self.assertIn("advisory", out.lower())    # advisory section present
        # the decoy must NOT be listed as an aligned requirement
        self.assertNotIn("→ `BG-001` _(traced in graph)_", out)


# ---------------------------------------------------------------------------
# R1-1 — set_business_context prefilled from 6.1 keeps the REAL business-need id, so a
# requirement traced to that need in the graph is aligned (not falsely orphan).
# ---------------------------------------------------------------------------

class TestR11_SixOneOnlyPath(BaseMCPTest):

    def test_req_traced_to_need_aligned_after_61_only_context(self):
        import skills.current_state_mcp as cs
        import skills.requirements_traceability_mcp as trace
        import skills.requirements_validate_mcp as val
        pid = "hr_onboard"
        # init the repo first so define_business_needs registers BN-001 as a graph node
        trace.init_traceability_repo(pid, "Standard", json.dumps([
            {"id": "FR-001", "type": "functional", "title": "System engine module",
             "status": "draft"}]))  # title shares NO >=5 word with the need title
        cs.define_business_needs(pid, need_title="Automate provisioning", description="d",
                                 need_type="problem", priority="High", source="s")
        trace.add_trace_link(pid, from_id="FR-001", to_id="BN-001", relation="derives",
                             rationale="serves the need")
        # business_goals_json empty -> prefilled from 6.1 needs (real BN id); future_state
        # and solution_scope are required by the tool, so supply them explicitly.
        val.set_business_context(pid, business_goals_json="",
                                 future_state="Onboarding future state",
                                 solution_scope="Onboarding scope",
                                 from_current_state_project_id=pid)
        out = val.check_business_alignment(pid, req_ids='["FR-001"]')
        self.assertIn("1 (100.0%)", out)          # aligned via the graph edge
        self.assertIn("traced in graph", out)


# ---------------------------------------------------------------------------
# F-B — the validated verdict must survive a later status overwrite (approve / CR /
# re-verify), reading the durable history record, not the mutable status field.
# ---------------------------------------------------------------------------

class TestFB_DurableValidated(BaseMCPTest):

    def test_validated_survives_status_overwrite(self):
        import skills.requirements_traceability_mcp as trace
        import skills.requirements_validate_mcp as val
        import skills.requirements_verify_mcp as ver
        from skills.common import has_been_validated
        pid = "hr_onboard"
        trace.init_traceability_repo(pid, "Standard", json.dumps([
            {"id": "FR-001", "type": "functional", "title": "R", "status": "verified"}]))
        val.mark_req_validated(pid, req_ids='["FR-001"]', force=True)
        # A later 5.5 approval / 5.4 CR overwrites the shared `status` field. The durable
        # validation fact (history) must survive it. (7.2 re-verify no longer downgrades —
        # see R2-4 — so overwrite via the approval status, the real lossy path.)
        repo_path = os.path.join("governance_plans", "data", pid, f"{pid}_traceability_repo.json")
        repo = json.load(open(repo_path, encoding="utf-8"))
        for r in repo["requirements"]:
            if r["id"] == "FR-001":
                r["status"] = "approved"
        json.dump(repo, open(repo_path, "w", encoding="utf-8"))
        repo = json.load(open(repo_path, encoding="utf-8"))
        self.assertEqual(next(r["status"] for r in repo["requirements"] if r["id"] == "FR-001"),
                         "approved")
        self.assertTrue(has_been_validated(repo, "FR-001"))
        out = val.get_validation_report(pid)
        self.assertNotIn("Validated | 0", out)


# ---------------------------------------------------------------------------
# Phase-2 backlog (A + B) closed alongside the E2E-3 fixes.
#   B4-1  session_type (4.2) must cover the technique vocabulary (4.1) + Experiments
#   B4-2  audience_role (4.4) must include End User / Customer / Domain SME
#   B4-3  the 4.1 plan title uses BABOK v3's term "Elicitation Activity Plan"
#   B5-1  the `verifies` relation is documented as BABOK's "Validate"
# ---------------------------------------------------------------------------

class TestBacklogDictionaries(unittest.TestCase):

    def test_b41_session_type_covers_techniques(self):
        import inspect
        import skills.elicitation_conduct_mcp as m
        ann = str(inspect.signature(m.process_elicitation_results)
                  .parameters["session_type"].annotation)
        for v in ["Brainstorming", "Prototyping", "Focus Group", "Benchmarking", "Experiments"]:
            self.assertIn(v, ann)

    def test_b42_audience_role_has_end_user_customer_sme(self):
        import inspect
        import skills.elicitation_communicate_mcp as m
        ann = str(inspect.signature(m.prepare_communication_package)
                  .parameters["audience_role"].annotation)
        for v in ["End User", "Customer", "Domain SME"]:
            self.assertIn(v, ann)

    def test_b51_verifies_documented_as_validate(self):
        import skills.requirements_traceability_mcp as m
        self.assertIn("Validate", m.add_trace_link.__doc__)


class TestBacklogPlanTitle(BaseMCPTest):

    def test_b43_plan_uses_babok_activity_plan_term(self):
        import skills.elicitation_mcp as m
        m.save_artifact.reset_mock()
        m.save_elicitation_plan(
            project_name="p", goals="Learn the current process",
            stakeholders_json='[{"name":"A","role":"R","influence":"High","interest":"High"}]',
            technique="Interview", technique_rationale="fits a 1-1",
            questions_or_agenda="1. ...", expected_outcomes="pains captured")
        content = m.save_artifact.call_args.args[0]   # the plan markdown handed to save_artifact
        self.assertIn("Elicitation Activity Plan", content)
        self.assertNotIn("# Requirements Elicitation Plan", content)


# ---------------------------------------------------------------------------
# Confirmation-run findings (fixed alongside): honesty/consistency at the seams.
#   R1-1  7.3 report must not claim "ready / all trace" with NO business context
#   R2-4  a re-run of 7.2 verify must not downgrade a `validated` status
#   R2-1  check_coverage must separate requirements from analysis artifacts
#   R1-2  7.4 must place 5.1 requirement classes (solution/transition/...) in a viewpoint
#   R2-2  a `component` (a realizer) must not be flagged "no implementation"
# ---------------------------------------------------------------------------

class TestConfirmationFindings(BaseMCPTest):

    def _repo(self, pid):
        return json.load(open(os.path.join(
            "governance_plans", "data", pid, f"{pid}_traceability_repo.json"), encoding="utf-8"))

    def test_r1_1_no_context_not_ready_no_false_trace(self):
        import skills.requirements_traceability_mcp as tr
        import skills.requirements_verify_mcp as ver
        import skills.requirements_validate_mcp as val
        pid = "noctx"
        tr.init_traceability_repo(pid, "Standard", json.dumps([
            {"id": "FR-001", "type": "functional", "title": "X", "status": "draft"}]))
        ver.mark_req_verified(pid, req_ids='["FR-001"]', force=True)
        val.mark_req_validated(pid, req_ids='["FR-001"]', force=True)
        out = val.get_validation_report(pid)
        self.assertIn("Not ready for 7.5", out)
        self.assertNotIn("All reqs trace to business objectives", out)
        self.assertIn("Business context not set", out)

    def test_r2_4_reverify_keeps_validated_status(self):
        import skills.requirements_traceability_mcp as tr
        import skills.requirements_validate_mcp as val
        import skills.requirements_verify_mcp as ver
        pid = "keepval"
        tr.init_traceability_repo(pid, "Standard", json.dumps([
            {"id": "FR-001", "type": "functional", "title": "X", "status": "verified"}]))
        val.mark_req_validated(pid, req_ids='["FR-001"]', force=True)
        ver.mark_req_verified(pid, req_ids='["FR-001"]', force=True)   # re-verify must not downgrade
        self.assertEqual(
            next(r["status"] for r in self._repo(pid)["requirements"] if r["id"] == "FR-001"),
            "validated")

    def test_r2_1_check_coverage_separates_analysis_artifacts(self):
        import skills.requirements_traceability_mcp as tr
        pid = "cov"
        tr.init_traceability_repo(pid, "Standard", json.dumps([
            {"id": "FR-001", "type": "functional", "title": "R", "status": "confirmed"},
            {"id": "RK-001", "type": "risk", "title": "Risk", "status": "identified"},
            {"id": "SOL-001", "type": "solution_scope", "title": "Scope", "status": "defined"}]))
        tr.add_trace_link(pid, "RK-001", "FR-001", "threatens", "x")
        tr.add_trace_link(pid, "SOL-001", "FR-001", "satisfies", "x")
        out = tr.check_coverage(pid)
        self.assertIn("Total items", out)
        self.assertIn("non-requirement node", out)
        self.assertIn("Fully covered items", out)
        # G-6: the caption is built from the types actually present. It used to be a
        # fixed list printed beside a count taken over a wider set, so a project with
        # no risk and no change request still read "(risks / change requests / ...)".
        self.assertIn("risks (6.3)", out)
        self.assertIn("solution scope (6.4)", out)
        self.assertNotIn("change requests (5.4)", out,
                         "the caption names a category this project does not contain")

    def test_r1_2_arch_places_51_classes_in_other_viewpoint(self):
        import skills.requirements_traceability_mcp as tr
        import skills.requirements_architecture_mcp as arch
        pid = "arch"
        tr.init_traceability_repo(pid, "Standard", json.dumps([
            {"id": "SR-001", "type": "solution", "title": "Sol req", "status": "confirmed"},
            {"id": "TR-001", "type": "transition", "title": "Trans req", "status": "confirmed"}]))
        out = arch.analyze_requirements_architecture(pid)
        self.assertIn("Other requirements", out)
        self.assertIn("(100.0%)", out)     # both counted -> full viewpoint coverage
        self.assertIn("SR-001", out)

    def test_r2_2_component_not_flagged_no_implementation(self):
        import skills.requirements_traceability_mcp as tr
        pid = "comp"
        tr.init_traceability_repo(pid, "Standard", json.dumps([
            {"id": "FR-001", "type": "functional", "title": "R", "status": "confirmed"},
            {"id": "COMP-1", "type": "component", "title": "Auth component", "status": "confirmed"}]))
        tr.add_trace_link(pid, "COMP-1", "FR-001", "satisfies", "implements")
        out = tr.check_coverage(pid)
        self.assertIn("Fully covered items", out)
        # the component is a realizer -> fully covered, NOT flagged for missing implementation
        self.assertIn("COMP-1", out.split("Fully covered items")[1])

    def test_r1_4_priority_not_written_to_non_requirement_node(self):
        import skills.requirements_traceability_mcp as tr
        import skills.requirements_prioritize_mcp as p53
        pid = "prio"
        tr.init_traceability_repo(pid, "Standard", json.dumps([
            {"id": "FR-001", "type": "functional", "title": "R", "status": "confirmed"},
            {"id": "BG-001", "type": "business_goal", "title": "Goal", "status": "confirmed"}]))
        p53.start_prioritization_session(pid, "s1", "MoSCoW")
        p53.add_stakeholder_scores(pid, "s1", "SH-1", "High",
            '[{"req_id":"FR-001","score":"Must"},{"req_id":"BG-001","score":"Must"}]')
        p53.run_aggregation(pid, "s1")
        out = p53.save_prioritization_result(pid, "s1")
        repo = self._repo(pid)
        fr = next(r for r in repo["requirements"] if r["id"] == "FR-001")
        bg = next(r for r in repo["requirements"] if r["id"] == "BG-001")
        self.assertIn("priority", fr)          # a real requirement is prioritised
        self.assertNotIn("priority", bg)       # the business_goal node is NOT
        self.assertIn("NOT requirements", out)  # and the report explains the skip


if __name__ == "__main__":
    unittest.main()
