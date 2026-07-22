"""
tests/test_corrupt_artifact_guard_ch3_ch6_ch7.py

A corrupt stored file must degrade into a readable ❌ line naming the file — never
escape as a protocol error, and never be silently replaced.

Chapters 5 and 7.1–7.3 already behave this way (read_json_artifact raises a typed
CorruptArtifactError; guard_artifact_errors converts it at the tool boundary). The
modules covered here kept bare `json.load` loaders: the same damaged traceability
repository produced "❌ … could not be read: `<path>`" from check_coverage (5.1) and
a JSONDecodeError stack trace from analyze_requirements_architecture (7.4).

The worst case was 6.4 (`_load_strategy`): a corrupt change-strategy file silently
became an EMPTY SKELETON, and the next writing tool answered "✅" while overwriting
the analyst's whole strategy — reproduced live: a 10 560-byte file replaced by a
933-byte skeleton. Raising beats returning an empty structure: degradation may say
LESS; it may not conclude more, and it must never destroy what it could not read.
"""

import json
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tests.conftest import BaseMCPTest, make_test_repo, save_test_repo

from skills.common import data_path

import skills.planning_mcp as ch3
import skills.current_state_mcp as ch61
import skills.future_state_mcp as ch62
import skills.risk_assessment_mcp as ch63
import skills.change_strategy_mcp as ch64
import skills.requirements_architecture_mcp as ch74
import skills.design_options_mcp as ch75
import skills.value_recommend_mcp as ch76

CORRUPT = "{ broken json"


def _write_corrupt(pid: str, filename: str) -> str:
    path = data_path(pid, filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(CORRUPT)
    return path


class CorruptGuardMixin:
    """Call the tool over a corrupt store; the answer must be an error LINE that
    names the file — not an exception, not a confident result."""

    def assert_degrades(self, result, path):
        self.assertIsInstance(result, str)
        self.assertIn("❌", result, f"expected an error line, got: {result[:200]}")
        self.assertIn(os.path.basename(path), result,
                      "the error must NAME the unreadable file")


class TestCh3PlanGuard(CorruptGuardMixin, BaseMCPTest):
    def test_save_ba_plan_over_corrupt_plan(self):
        path = _write_corrupt("guard3", "guard3_ba_plan.json")
        self.assert_degrades(ch3.save_ba_plan("guard3"), path)


class TestCh61StateGuard(CorruptGuardMixin, BaseMCPTest):
    def test_capture_element_over_corrupt_state(self):
        path = _write_corrupt("guard61", "guard61_current_state.json")
        self.assert_degrades(
            ch61.capture_current_state_element(
                "guard61", element="capabilities", description="probe"),
            path,
        )


class TestCh62GoalsGuard(CorruptGuardMixin, BaseMCPTest):
    def test_define_goal_over_corrupt_goals_file(self):
        path = _write_corrupt("guard62", "guard62_future_state_goals.json")
        self.assert_degrades(
            ch62.define_goals_and_objectives(
                "guard62", goal_title="Probe goal", description="probe",
                objectives_json="[]", register_in_traceability=False),
            path,
        )


class TestCh63AssessmentGuard(CorruptGuardMixin, BaseMCPTest):
    def test_add_risk_over_corrupt_assessment(self):
        path = _write_corrupt("guard63", "guard63_risk_assessment.json")
        self.assert_degrades(
            ch63.add_risk(
                "guard63", category="operational", source="change",
                description="probe", likelihood=3, impact=3,
                response_strategy="accept"),
            path,
        )


class TestCh64StrategyGuard(CorruptGuardMixin, BaseMCPTest):
    def test_add_option_over_corrupt_strategy_answers_error(self):
        path = _write_corrupt("guard64", "guard64_change_strategy.json")
        self.assert_degrades(
            ch64.add_strategy_option(
                "guard64", name="Probe", strategy_type="big_bang",
                investment_level="low", timeline_months=3,
                pros='["p"]', cons='["c"]'),
            path,
        )

    def test_corrupt_strategy_is_not_overwritten(self):
        """The regression that matters most: the tool must not replace the file it
        could not read. Never delete data."""
        path = _write_corrupt("guard64b", "guard64b_change_strategy.json")
        ch64.add_strategy_option(
            "guard64b", name="Probe", strategy_type="big_bang",
            investment_level="low", timeline_months=3,
            pros='["p"]', cons='["c"]')
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), CORRUPT,
                             "the corrupt file was OVERWRITTEN — data loss")


class TestCh74RepoGuard(CorruptGuardMixin, BaseMCPTest):
    def test_analyze_over_corrupt_shared_repo(self):
        path = _write_corrupt("guard74", "guard74_traceability_repo.json")
        self.assert_degrades(
            ch74.analyze_requirements_architecture("guard74"), path)


class TestCh75RepoGuard(CorruptGuardMixin, BaseMCPTest):
    def test_allocate_over_corrupt_shared_repo(self):
        # a real option first, so the failure is the repo read, not a missing option
        ch75.create_design_option(
            "guard75", option_id="OPT-001", title="Probe", approach="build",
            components_json='["c"]', improvement_opportunities_json="[]",
            effectiveness_measures_json='["m"]')
        path = _write_corrupt("guard75", "guard75_traceability_repo.json")
        self.assert_degrades(
            ch75.allocate_requirements("guard75", option_id="OPT-001"), path)


class TestCh76RecommendationGuard(CorruptGuardMixin, BaseMCPTest):
    def test_compare_value_over_corrupt_recommendation(self):
        path = _write_corrupt("guard76", "guard76_recommendation.json")
        self.assert_degrades(ch76.compare_value("guard76"), path)


class TestCh63PushGuard(CorruptGuardMixin, BaseMCPTest):
    """The push branches read the SHARED graph before writing to it — a corrupt
    repository must stop the push with a named file, not crash or half-write."""

    def test_risk_push_over_corrupt_repo(self):
        ch63.add_risk(
            "guard63p", category="operational", source="change",
            description="probe risk", likelihood=3, impact=3,
            response_strategy="accept")
        ch63.set_risk_tolerance("guard63p", tolerance_level="neutral")
        ch63.run_risk_matrix("guard63p")
        ch63.generate_recommendation("guard63p")
        path = _write_corrupt("guard63p", "guard63p_traceability_repo.json")
        self.assert_degrades(
            ch63.save_risk_assessment("guard63p", push_to_traceability=True), path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
