"""
tests/test_registry_seams_ch4.py — 4.1 and 4.5 reach the living stakeholder registry.

ADR-003 makes the registry a LIVING document, and 4.2 maintains it — but two tools
that learn things about stakeholders wrote only Markdown:

  * 4.5 `update_engagement_status` is the ONE tool whose entire purpose is to record
    that a stakeholder's attitude changed. "Became a Blocker" landed in a report and
    nowhere else, so the registry 7.4 reads and 3.2's conflict detector compares
    against still said whatever it said before.
  * 4.1 `save_elicitation_plan` takes a stakeholder list and neither read nor updated
    the registry, so a person identified while PLANNING an interview never reached it
    and had to be typed in again in 4.2.

Both now go through `update_stakeholder_registry_file` — the same merge 3.2 and 4.2
use (extracted to common.py in A2), so identity matching, partial updates and
insert-only defaults behave identically no matter which chapter is writing.

The insert-only rule matters here in BOTH directions:
  * 4.1 plans an interview, so it must not overwrite an attitude an interview already
    established — its seeds are insert-only, like 3.2's.
  * 4.5 observes a change, so its attitude is an ORDINARY update and must overwrite.
    That asymmetry is the whole point of the two tools.
"""

import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import setup_mocks, BaseMCPTest

setup_mocks()

from skills.common import (load_stakeholder_registry, stakeholder_identity,
                           update_stakeholder_registry_file)
import skills.elicitation_mcp as t41
import skills.elicitation_collaborate_mcp as t45

PID = "seams"


def _entry(registry, key):
    for s in registry.get("stakeholders", []):
        if stakeholder_identity(s) == key:
            return s
    return None


class TestElicitationPlanSeedsTheRegistry(BaseMCPTest):

    def _save_plan(self, stakeholders):
        with patch("skills.elicitation_mcp.save_artifact", return_value="✅ Saved"):
            return t41.save_elicitation_plan(
                project_name=PID,
                goals="Understand the current underwriting process",
                stakeholders_json=json.dumps(stakeholders),
                technique="Interview",
                technique_rationale="One-to-one depth on a sensitive process",
                questions_or_agenda="1. Walk me through a rejection.",
                expected_outcomes="A list of pain points",
            )

    def test_a_stakeholder_named_in_the_plan_reaches_the_registry(self):
        self._save_plan([{"name": "Jane Doe", "role": "Process Owner",
                          "influence": "High", "interest": "High"}])
        entry = _entry(load_stakeholder_registry(PID), "jane doe")
        self.assertIsNotNone(
            entry, "the person the BA is about to interview never reached the registry")
        self.assertEqual(entry.get("role"), "Process Owner")

    def test_the_report_tells_the_ba_the_registry_was_updated(self):
        out = self._save_plan([{"name": "Jane Doe", "role": "Process Owner"}])
        self.assertIn("registry", out.lower())

    def test_planning_does_not_overwrite_an_elicited_attitude(self):
        """4.1 plans; it does not observe. An attitude it did not receive must never
        overwrite one an interview established — the A2 defect, in a new chapter."""
        update_stakeholder_registry_file(
            PID, [{"name": "Jane Doe", "role": "Process Owner", "attitude": "Blocker"}],
            source="4.2 interview")
        self._save_plan([{"name": "Jane Doe", "role": "Process Owner"}])
        self.assertEqual(_entry(load_stakeholder_registry(PID), "jane doe")["attitude"],
                         "Blocker")

    def test_a_failing_registry_write_does_not_break_the_plan(self):
        """The plan is the deliverable; the registry is a side effect."""
        with patch("skills.elicitation_mcp.update_stakeholder_registry_file",
                   side_effect=OSError("disk full")):
            out = self._save_plan([{"name": "Jane Doe", "role": "Process Owner"}])
        self.assertNotIn("Traceback", out)


class TestEngagementChangeReachesTheRegistry(BaseMCPTest):

    def _record_change(self, before="Neutral", after="Blocker", role="Compliance Officer"):
        with patch("skills.elicitation_collaborate_mcp.save_artifact",
                   return_value="✅ Saved"):
            return t45.update_engagement_status(
                project_name=PID,
                stakeholder_role=role,
                change_date="21.07.2026",
                attitude_before=before,
                attitude_after=after,
                engagement_level_before="Active",
                engagement_level_after="Passive",
                signal_observed="Stopped replying and escalated to the sponsor",
                probable_cause="Scope grew past what was agreed",
                ba_action_taken="Requested a one-to-one",
                ba_action_planned="Re-baseline the scope with them",
                escalation_needed=False,
                escalation_to="",
            )

    def test_the_new_attitude_lands_in_the_registry(self):
        self._record_change()
        entry = _entry(load_stakeholder_registry(PID), "compliance officer")
        self.assertIsNotNone(entry, "the engagement change never reached the registry")
        self.assertEqual(
            entry.get("attitude"), "Blocker",
            "'became a Blocker' stayed in the Markdown report, where 7.4 and 3.2 "
            "cannot see it",
        )

    def test_an_observed_change_OVERWRITES_the_stored_attitude(self):
        """The asymmetry with 4.1: this tool observed the change, so it wins."""
        update_stakeholder_registry_file(
            PID, [{"role": "Compliance Officer", "attitude": "Champion"}],
            source="3.2 plan")
        self._record_change(before="Champion", after="Blocker")
        self.assertEqual(
            _entry(load_stakeholder_registry(PID), "compliance officer")["attitude"],
            "Blocker")

    def test_the_engagement_level_is_recorded_too(self):
        self._record_change()
        entry = _entry(load_stakeholder_registry(PID), "compliance officer")
        self.assertEqual(entry.get("engagement_level"), "Passive")

    def test_the_report_tells_the_ba_the_registry_was_updated(self):
        out = self._record_change()
        self.assertIn("registry", out.lower())

    def test_a_failing_registry_write_does_not_break_the_record(self):
        with patch("skills.elicitation_collaborate_mcp.update_stakeholder_registry_file",
                   side_effect=OSError("disk full")):
            out = self._record_change()
        self.assertNotIn("Traceback", out)

    def test_it_updates_the_NAMED_person_holding_that_role(self):
        """Found by a live run, not by the fixtures above.

        Registry identity is the NAME, falling back to the role only when there is no
        name. 4.5 takes a role and no name, so writing role-keyed created a SECOND
        entry for a person already recorded under their name: the duplicate said
        Blocker while the entry 7.4 actually reads still said nothing. Two records,
        one person, and the reader sees the stale one.
        """
        update_stakeholder_registry_file(
            PID, [{"name": "Sam Reed", "role": "Compliance Officer",
                   "attitude": "Neutral"}],
            source="4.1 elicitation plan")
        self._record_change(role="Compliance Officer")

        registry = load_stakeholder_registry(PID)
        self.assertEqual(
            len(registry["stakeholders"]), 1,
            f"4.5 created a duplicate record: {registry['stakeholders']}")
        self.assertEqual(_entry(registry, "sam reed")["attitude"], "Blocker")

    def test_role_matching_is_case_insensitive(self):
        update_stakeholder_registry_file(
            PID, [{"name": "Sam Reed", "role": "compliance officer"}],
            source="4.1 elicitation plan")
        self._record_change(role="Compliance Officer")
        registry = load_stakeholder_registry(PID)
        self.assertEqual(len(registry["stakeholders"]), 1)

    def test_an_ambiguous_role_is_flagged_rather_than_guessed(self):
        """Two people share a role: picking one silently would put an observation on
        the wrong person's record."""
        update_stakeholder_registry_file(
            PID, [{"name": "Sam Reed", "role": "Compliance Officer"},
                  {"name": "Ada Vance", "role": "Compliance Officer"}],
            source="4.1 elicitation plan")
        out = self._record_change(role="Compliance Officer")
        self.assertIn("more than one", out.lower())
        for name in ("sam reed", "ada vance"):
            self.assertNotEqual(
                _entry(load_stakeholder_registry(PID), name).get("attitude"),
                "Blocker",
                "an observation was attached to a guessed person")

    def test_an_unknown_role_still_creates_an_entry(self):
        """A stakeholder first met through an engagement change is still a
        stakeholder — falling back to a role-keyed entry is correct when nobody in
        the registry holds that role."""
        self._record_change(role="Data Protection Officer")
        self.assertIsNotNone(
            _entry(load_stakeholder_registry(PID), "data protection officer"))


if __name__ == "__main__":
    unittest.main()
