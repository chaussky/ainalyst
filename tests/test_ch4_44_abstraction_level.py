"""tests/test_ch4_44_abstraction_level.py — 4.4 consumes the 3.4 detail level (B3-3)."""

import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import setup_mocks, BaseMCPTest

setup_mocks()

from skills.common import ba_plan_path
from skills.elicitation_communicate_mcp import prepare_communication_package

PROJECT = "b33_comm"
PROFILE = json.dumps({"stakeholder_role": "Head of Retail Lending",
                      "influence": "High", "interest": "High", "attitude": "Neutral"})


def _write_plan(project_id: str, rows: list):
    path = ba_plan_path(project_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"project": project_id,
                   "information_management": {"abstraction_levels": rows}}, f)


def _package(project_id=PROJECT, audience="Business Sponsor"):
    """Returns (tool_return, artefact_text).

    save_artifact is patched per ADR-068 (the suite-wide mock writes nothing), so the
    artefact is captured from the call rather than read off disk. Task 8 runs the same
    flows against the REAL writer.
    """
    with patch("skills.elicitation_communicate_mcp.save_artifact") as mock_sa:
        mock_sa.return_value = "\n\n✅ Artifact saved: `x.md`"
        result = prepare_communication_package(
            project_name=project_id,
            source_artifact_path="reports/x/4_3_confirmed.md",
            audience_role=audience,
            audience_profile_json=PROFILE,
            adapted_content="Body of the package.",
            key_messages_json='[{"message": "Ship it", "why_it_matters": "value"}]',
            recommended_format="Presentation",
            recommended_channel="Meeting",
            open_questions="",
            ba_notes="")
        artefact = mock_sa.call_args[0][0] if mock_sa.call_args else ""
    return result, artefact


class TestPlannedDetailLevel(BaseMCPTest):

    def test_without_a_plan_nothing_new_is_said(self):
        result, artefact = _package()
        self.assertNotIn("Level of detail", artefact)
        self.assertNotIn("⚠️", result)

    def test_planned_level_appears_in_the_artefact_header(self):
        _write_plan(PROJECT, [{"audience": "Business Sponsor", "level": "Summary",
                               "note": "value and risks only"}])
        _, artefact = _package()
        self.assertIn("Level of detail (planned in 3.4)", artefact)
        self.assertIn("Summary", artefact)
        self.assertIn("value and risks only", artefact)

    def test_the_level_is_decoded_into_an_actionable_checklist(self):
        """A bare label is the 'declared but dead' class — the BA needs to know what
        the level MEANS for this package. The tool returns only the save line, so the
        checklist has to live in the artefact."""
        _write_plan(PROJECT, [{"audience": "Business Sponsor", "level": "Summary"}])
        _, artefact = _package()
        self.assertIn("Include:", artefact)
        self.assertIn("Leave out:", artefact)
        self.assertIn("requirement IDs", artefact)   # the Summary "leave out" list

    def test_job_title_row_matches_when_the_archetype_does_not(self):
        _write_plan(PROJECT, [{"audience": "Head of Retail Lending", "level": "Detailed"}])
        _, artefact = _package(audience="Manager")
        self.assertIn("**Level of detail (planned in 3.4):** Detailed", artefact)

    def test_archetype_row_matches_case_insensitively(self):
        """The writer accepts any casing, so the reader must too — otherwise the join
        fails on exactly the input the writer told the BA was fine."""
        _write_plan(PROJECT, [{"audience": "business sponsor", "level": "Detailed"}])
        _, artefact = _package(audience="Business Sponsor")
        self.assertIn("Level of detail (planned in 3.4)", artefact)

    def test_audience_absent_from_the_plan_is_flagged_in_the_return(self):
        _write_plan(PROJECT, [{"audience": "Developer", "level": "Detailed"}])
        result, artefact = _package(audience="Tester")
        self.assertIn("⚠️", result)
        self.assertIn("Developer", result)      # the planned audiences are listed
        self.assertNotIn("Level of detail (planned in 3.4)", artefact)

    def test_an_empty_plan_section_does_not_nag(self):
        """A project that planned storage but no detail levels has made no decision
        to be reminded of — warning there would be noise on every package."""
        path = ba_plan_path(PROJECT)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"project": PROJECT,
                       "information_management": {"storage_tools": ["Jira"]}}, f)
        result, _ = _package()
        self.assertNotIn("⚠️", result)

    def test_malformed_rows_never_reach_the_package(self):
        """The shape guards added to the reader stopped at the two chapter-5 consumers,
        which coerce everything they touch. 4.4 indexes the row directly, so a row
        with no `level`, a list `level` or a numeric `audience` raised an uncaught
        exception — a protocol error, not a ❌ line — and a null `level` shipped a
        package claiming a detail level of "None" with an empty checklist under it."""
        for row in ({"audience": "Business Sponsor"},
                    {"audience": "Business Sponsor", "level": ["Summary"]},
                    {"audience": "Business Sponsor", "level": None},
                    {"audience": "Business Sponsor", "level": "Verbose"},
                    {"audience": 5, "level": "Summary"}):
            with self.subTest(row=row):
                _write_plan(PROJECT, [row])
                result, artefact = _package()
                self.assertIn("✅", result)
                self.assertNotIn("None", artefact.split("## Audience Profile")[0])
                self.assertNotIn("Level of detail (planned in 3.4)", artefact)

    def test_corrupt_plan_does_not_kill_the_tool(self):
        path = ba_plan_path(PROJECT)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("{broken")
        result, _ = _package()
        self.assertIn("✅", result)
        self.assertIn("⚠️", result)


if __name__ == "__main__":
    unittest.main()
