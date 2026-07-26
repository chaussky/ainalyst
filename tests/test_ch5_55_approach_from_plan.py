"""5.5 takes the methodology from the 3.1 plan instead of asking twice (B3-1).

Before this, `approach` was a REQUIRED parameter of prepare_approval_package — the
BA restated a decision 3.1 had already recorded, and nothing compared the two.

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.conftest import setup_mocks, BaseMCPTest, make_test_repo, save_test_repo

setup_mocks()

from skills.common import ba_plan_path, data_path, normalize_project_id
from skills.requirements_approve_mcp import (
    create_requirements_baseline,
    prepare_approval_package,
    record_approval_decision,
)

PROJECT = "b31_ch55"


def _seed_plan(section=None, approach_label=None, raw=None):
    path = ba_plan_path(PROJECT)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if raw is not None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(raw)
        return
    plan = {"project_id": PROJECT}
    if section is not None:
        plan["ba_activities"] = section
    if approach_label is not None:
        plan["ba_approach"] = {"recommended_approach": approach_label}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f)


def _history():
    safe = normalize_project_id(PROJECT)
    with open(data_path(PROJECT, f"{safe}_approval_history.json"),
              "r", encoding="utf-8") as f:
        return json.load(f)


class TestResolution(BaseMCPTest):

    def setUp(self):
        super().setUp()
        repo = make_test_repo(PROJECT)
        for req in repo["requirements"]:
            if req["type"] != "test":
                req["status"] = "verified"
        save_test_repo(repo)

    def _prepare(self, package_id="PKG-1", **kwargs):
        return prepare_approval_package(
            project_name=PROJECT, package_id=package_id, package_title="T",
            req_ids_json='["FR-001"]', **kwargs)

    def test_an_explicit_value_still_wins_and_is_labelled_as_such(self):
        _seed_plan({"timing_form": "iterations"})
        out = self._prepare(approach="predictive")
        self.assertIn("Predictive / Waterfall", out)
        self.assertIn("stated in this call", out)
        self.assertEqual(_history()["packages"]["PKG-1"]["approach"], "predictive")

    def test_the_timing_form_supplies_the_methodology(self):
        _seed_plan({"timing_form": "iterations"})
        out = self._prepare()
        self.assertIn("Agile", out)
        self.assertIn("3.1 BA plan", out)
        self.assertIn("iterations", out)
        record = _history()["packages"]["PKG-1"]
        self.assertEqual(record["approach"], "agile")
        self.assertIn("timing form", record["approach_source"])

    def test_phases_resolve_to_predictive(self):
        _seed_plan({"timing_form": "phases"})
        out = self._prepare()
        self.assertIn("Predictive / Waterfall", out)
        self.assertEqual(_history()["packages"]["PKG-1"]["approach"], "predictive")

    def test_the_approach_label_is_the_fallback_when_no_timing_form_exists(self):
        _seed_plan(approach_label="Adaptive (Agile)")
        out = self._prepare()
        self.assertIn("Agile", out)
        self.assertIn("Adaptive (Agile)", out)
        self.assertEqual(_history()["packages"]["PKG-1"]["approach"], "agile")

    def test_the_timing_form_beats_the_approach_label(self):
        """The form is the BA's later, more specific statement about the same thing."""
        _seed_plan({"timing_form": "phases"}, approach_label="Adaptive (Agile)")
        self._prepare()
        self.assertEqual(_history()["packages"]["PKG-1"]["approach"], "predictive")

    def test_a_regulated_hybrid_gets_the_FORMAL_package_not_the_sprint_one(self):
        """`approach` selects the approval CEREMONY here — the four-option decision
        menu with a deadline, or "For Sprint Planning, the PO approves the backlog".
        `Hybrid (Agile + compliance gates)` exists because regulatory_need=True, and
        its whole point is formal sign-off for audit. Resolving it through the timing
        form mapped a CADENCE onto a CEREMONY and handed exactly those projects the
        informal package."""
        _seed_plan({"timing_form": "iterations"},
                   approach_label="Hybrid (Agile + compliance gates)")
        out = self._prepare()
        self.assertIn("**Conditional**", out)
        self.assertIn("Response deadline", out)
        self.assertNotIn("For Sprint Planning", out)
        self.assertEqual(_history()["packages"]["PKG-1"]["approach"], "predictive")

    def test_the_OTHER_regulatory_label_is_formal_too(self):
        """`REGULATORY_OVERRIDE` produces TWO labels and both exist only because
        regulatory_need=True. Fixing one and leaving the other is the same defect,
        and the docs steer the BA of that project into declaring a timing form —
        which is precisely the path that handed it the informal package."""
        _seed_plan({"timing_form": "iterations"},
                   approach_label="Hybrid (with strengthened governance)")
        out = self._prepare()
        self.assertIn("**Conditional**", out)
        self.assertNotIn("For Sprint Planning", out)
        self.assertEqual(_history()["packages"]["PKG-1"]["approach"], "predictive")

    def test_a_sprint_number_on_a_formal_package_is_explained_not_contradicted(self):
        """A compliance-gates project runs sprints AND signs off formally, so the
        header would otherwise read "Predictive / Waterfall | Sprint: 5" with an
        instruction block that never mentions the sprint."""
        _seed_plan({"timing_form": "iterations"},
                   approach_label="Hybrid (Agile + compliance gates)")
        out = self._prepare(sprint_number="5")
        self.assertIn("Sprint: 5", out)
        # NOT assertIn("compliance gates"): the resolution source line already
        # contains the label, so that would hold with no explanation printed at all.
        self.assertIn("The work runs in sprints", out)

    def test_plain_hybrid_refuses_and_names_both_ways_out(self):
        _seed_plan(approach_label="Hybrid")
        out = self._prepare()
        self.assertIn("❌", out)
        self.assertIn("approach", out)
        self.assertIn("plan_ba_activities", out)
        self.assertFalse(os.path.exists(data_path(
            PROJECT, f"{normalize_project_id(PROJECT)}_approval_history.json")))

    def test_no_plan_at_all_refuses_the_same_way(self):
        out = self._prepare()
        self.assertIn("❌", out)
        self.assertIn("plan_ba_activities", out)

    def test_an_unreadable_plan_shows_the_warning_instead_of_staying_silent(self):
        _seed_plan(raw="{not json")
        out = self._prepare()
        self.assertIn("❌", out)
        self.assertIn("⚠️", out)

    def test_an_offvocabulary_explicit_value_passes_through_unchanged(self):
        """pydantic rejects it in production; the mocked test bootstrap does not, and
        an existing setup call (tests/test_ch5_ch7_input_shapes.py) relies on the
        package still being created."""
        _seed_plan({"timing_form": "phases"})
        out = self._prepare(approach="formal")
        self.assertIn("Agile", out)          # today's rendering: anything != predictive
        self.assertEqual(_history()["packages"]["PKG-1"]["approach"], "formal")

    def test_the_baseline_record_reads_the_stored_value_not_the_plan_again(self):
        """Carry the data on the record — never re-derive it or re-parse rendered text.

        Asserted on the Approval Record DOCUMENT, not on the tool's return: the tool
        returns a short summary and the record itself goes through save_artifact.
        """
        # `phases`, not `iterations`: the rendered label is
        # `"Predictive / Waterfall" if approach == "predictive" else "Agile"`, so an
        # assertion on "Agile" is the DEFAULT branch and would hold with the stored
        # value deleted — the test would pass for the wrong reason.
        _seed_plan({"timing_form": "phases"})
        self._prepare(package_id="PKG-2")
        record_approval_decision(
            project_name=PROJECT, package_id="PKG-2", stakeholder_name="Ivanov",
            stakeholder_raci="accountable", decision="approved",
            req_decisions_json="[]")
        os.remove(ba_plan_path(PROJECT))          # the plan is gone
        with patch("skills.requirements_approve_mcp.save_artifact") as saver:
            saver.return_value = "\n\n✅ Saved"
            create_requirements_baseline(
                project_name=PROJECT, package_id="PKG-2", baseline_version="v1.0",
                decided_by="Ivanov")
        self.assertTrue(saver.call_args, "the Approval Record was not written")
        record = saver.call_args[0][0]
        self.assertIn("**Methodology:** Predictive / Waterfall", record)
        # The Approval Record is the document an auditor reads; where the methodology
        # came from belongs in it, and storing the source is pointless otherwise.
        self.assertIn("timing form: phases", record)


if __name__ == "__main__":
    unittest.main()
