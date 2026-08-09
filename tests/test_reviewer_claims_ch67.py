"""
tests/test_reviewer_claims_ch67.py — the chapter 6/7 defects a static review raised
and execution confirmed.

Each was verified against BOTH sides of its seam before anything was changed. Of the
19 claims reviewed in this pass, one was refuted outright and two had their mechanism
misdescribed — so the tests below pin what was actually happening, not what was
alleged.

  * 7.4 matched stakeholders against requirement text with `in`, so a registry entry
    with an empty name matched everything and one with a null name crashed;
  * 7.1 fell back to an unfiltered artifact search that could silently read ANOTHER
    project's elicitation results;
  * 7.6 classified risk with hard-coded thresholds while 6.3 classified the same risk
    against the analyst's configured tolerance;
  * 7.6's risk penalty is identical for every option under degradation, so it cancels
    out of the comparison it appears in.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import setup_mocks, BaseMCPTest

setup_mocks()

from skills.common import normalize_project_id
import skills.requirements_architecture_mcp as t74
import skills.value_recommend_mcp as t76

PID = "claims"


class TestStakeholderCoverageMatching(BaseMCPTest):
    """`sh_name in mention or mention in sh_name` — with an empty name the first
    branch is true for every mention, so the stakeholder is always "covered" and the
    gap this check exists to find can never be reported. The module itself expects
    empty names: its own message falls back to the role when the name is missing."""

    def _setup(self, stakeholders):
        safe = normalize_project_id(PID)
        base = os.path.join("governance_plans", "data", safe)
        os.makedirs(base, exist_ok=True)
        with open(os.path.join(base, f"{safe}_stakeholder_registry.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"project": PID, "stakeholders": stakeholders}, f)
        with open(os.path.join(base, f"{safe}_traceability_repo.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"project": PID, "links": [], "history": [], "requirements": [
                {"id": "FR-001", "type": "functional",
                 "title": "Underwriter reviews the application",
                 "version": "1.0", "status": "draft"}]}, f)

    def test_a_stakeholder_with_no_name_is_not_silently_covered(self):
        self._setup([{"name": "", "role": "Compliance Officer"}])
        out = t74.check_architecture_gaps(PID)
        self.assertIn(
            "Compliance Officer", out,
            "a stakeholder recorded by role only was reported as covered by every "
            "requirement, because an empty name is a substring of everything",
        )

    def test_a_null_name_does_not_crash_the_tool(self):
        self._setup([{"name": None, "role": "Data Protection Officer"}])
        out = t74.check_architecture_gaps(PID)
        self.assertIsInstance(out, str)
        self.assertNotIn("Traceback", out)

    def test_a_genuinely_mentioned_stakeholder_is_still_covered(self):
        """The guard against over-correcting into "nobody is ever covered"."""
        self._setup([{"name": "Underwriter", "role": "Underwriter"}])
        out = t74.check_architecture_gaps(PID)
        gaps = out.split("stakeholder_no_view")[1] if "stakeholder_no_view" in out else ""
        self.assertNotIn("Underwriter", gaps)


class TestConfirmedArtifactSearchCannotReachAnotherProject(BaseMCPTest):
    """The search used to fall back to patterns that filter by nothing at all, so a
    flat artifact belonging to some other project could be read into THIS project's
    requirements. It announced itself when it did — but the announcement was the only
    thing standing between two projects. The fallbacks went with the legacy layout
    (owner's decision, 2026-08-03); the folder now IS the filter."""

    def _write_flat_artifact(self):
        os.makedirs(os.path.join("governance_plans", "reports"), exist_ok=True)
        path = os.path.join("governance_plans", "reports",
                            "4_3_confirmed_result_20260701_120000.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("# Confirmed results\n\nSome other project's elicitation.\n")
        return path

    def test_a_file_outside_the_project_folder_is_not_used(self):
        import skills.requirements_spec_mcp as t71
        self._write_flat_artifact()
        out = t71.analyze_elicitation_context(PID)
        self.assertNotIn("4_3_confirmed_result_20260701_120000.md", out,
                         "an artifact belonging to no project was read into this one")
        self.assertIn("не найден", out.lower())

    def test_the_file_that_was_used_is_named(self):
        import skills.requirements_spec_mcp as t71
        d = os.path.join("governance_plans", "reports", PID)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "4_3_confirmed_result_20260701_120000.md"),
                  "w", encoding="utf-8") as f:
            f.write("# Confirmed results\n\nContent.\n")
        out = t71.analyze_elicitation_context(PID)
        self.assertIn("4_3_confirmed_result_20260701_120000.md", out)


class TestRiskLevelFollowsTheAnalystsTolerance(unittest.TestCase):
    """6.3 classifies a risk against `max_acceptable_score`, which the analyst sets
    via set_risk_tolerance. 7.6 re-derived the level from hard-coded thresholds, so a
    risk-averse project's High risk was scored as Medium in the recommendation that
    goes to the sponsor. The zone 6.3 computed is now stored on the risk record, so
    7.6 can simply read it."""

    def test_a_stored_zone_wins_over_the_hard_coded_thresholds(self):
        # score 12 is BELOW 7.6's hard-coded High threshold of 15, but a risk-averse
        # project (max_acceptable_score=10) has already classified it as high.
        risk = {"risk_id": "RK-001", "risk_score": 12, "zone": "high"}
        self.assertEqual(t76._risk_level_of(risk), "High")

    def test_without_a_stored_zone_the_score_is_used(self):
        self.assertEqual(t76._risk_level_of({"risk_score": 20}), "Critical")
        self.assertEqual(t76._risk_level_of({"risk_score": 3}), "Low")

    def test_an_explicit_level_still_wins(self):
        self.assertEqual(
            t76._risk_level_of({"risk_level": "Critical", "risk_score": 1}), "Critical")


class TestProjectWideRiskPenaltyIsLabelled(BaseMCPTest):
    """Under degradation every option gets the SAME project-wide risk register, so the
    penalty is identical across options and cancels out of the comparison — while
    still appearing in it as though it discriminated. The number is correct for the
    ABSOLUTE value score, so it stays; what was missing is saying so."""

    def _setup_project_risks(self):
        safe = normalize_project_id(PID)
        base = os.path.join("governance_plans", "data", safe)
        os.makedirs(base, exist_ok=True)
        with open(os.path.join(base, f"{safe}_risk_assessment.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"project_id": PID, "risks": [
                {"risk_id": "RK-001", "description": "Regulator may reject",
                 "risk_score": 20, "zone": "high", "status": "identified"}]}, f)

    def test_the_assessment_records_that_the_risks_are_project_wide(self):
        self._setup_project_risks()
        out = t76.add_value_assessment(
            project_id=PID, option_id="OPT-001",
            benefits_json=json.dumps([{"type": "operational",
                                       "description": "Faster decisions",
                                       "magnitude": "High", "tangibility": "tangible",
                                       "confidence": "High"}]),
            costs_json=json.dumps({"components": [
                {"component": "Build", "cost_items": [
                    {"category": "development", "description": "Engineering",
                     "magnitude": "Medium"}]}]}))
        self.assertIn("по проекту целиком", out.lower())

    def test_the_comparison_says_the_penalty_does_not_differentiate(self):
        self._setup_project_risks()
        for opt in ("OPT-001", "OPT-002"):
            t76.add_value_assessment(
                project_id=PID, option_id=opt,
                benefits_json=json.dumps([{"type": "operational",
                                           "description": "Faster decisions",
                                           "magnitude": "High", "tangibility": "tangible",
                                           "confidence": "High"}]),
                costs_json=json.dumps({"components": [
                    {"component": "Build", "cost_items": [
                        {"category": "development", "description": "Engineering",
                         "magnitude": "Medium"}]}]}))
        out = t76.compare_value(PID)
        self.assertIn("не различает", out.lower())


if __name__ == "__main__":
    unittest.main()
