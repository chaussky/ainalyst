"""
tests/test_common_stakeholder_registry.py — the shared living-registry helpers.

Extracted from 4.2 so that 3.2 can seed the same registry without either chapter
depending on the other (Chapter 3 loads in every phase, Chapter 4 only in
`elicitation`).
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.conftest import setup_mocks, BaseMCPTest

setup_mocks()

from skills.common import (
    reg_norm,
    stakeholder_identity,
    load_stakeholder_registry,
    save_stakeholder_registry,
    merge_stakeholders,
    update_stakeholder_registry_file,
    registry_labels,
    registry_party_status,
    PARTY_IN_REGISTRY,
    PARTY_NOT_IN_REGISTRY,
    PARTY_UNBRIDGEABLE,
)

TODAY = "20.07.2026"


class TestIdentity(unittest.TestCase):

    def test_name_is_the_key(self):
        self.assertEqual(stakeholder_identity({"name": "  Jane  Doe ", "role": "CFO"}),
                         "jane doe")

    def test_role_is_the_fallback_when_name_is_missing(self):
        self.assertEqual(stakeholder_identity({"role": "Head of Sales"}), "head of sales")

    def test_neither_name_nor_role_yields_no_key(self):
        self.assertEqual(stakeholder_identity({"notes": "someone"}), "")

    def test_reg_norm_collapses_whitespace_and_case(self):
        self.assertEqual(reg_norm("  Head   OF  Sales "), "head of sales")


class TestMergeStakeholders(unittest.TestCase):

    def test_adds_a_new_entry(self):
        existing = []
        result = merge_stakeholders(existing, [{"name": "Jane", "role": "CFO"}],
                                    source="interview", today=TODAY)
        self.assertEqual(result["added"], ["Jane"])
        self.assertEqual(len(existing), 1)
        self.assertEqual(existing[0]["_update_source"], "interview")

    def test_updates_an_existing_entry_by_identity(self):
        existing = [{"name": "Jane", "role": "CFO", "influence": "Low"}]
        result = merge_stakeholders(existing, [{"name": "Jane", "influence": "High"}],
                                    source="interview", today=TODAY)
        self.assertEqual(result["updated"], ["Jane"])
        self.assertEqual(len(existing), 1)
        self.assertEqual(existing[0]["influence"], "High")

    def test_identity_match_is_case_insensitive_and_the_name_is_restyled(self):
        """Documents pre-existing 4.2 behaviour, carried over unchanged.

        Matching ignores case, so this updates the same person rather than adding a
        second one — but `name` is an ordinary field, so the incoming spelling
        overwrites the stored one. Re-entering someone in different casing therefore
        restyles their display name. Harmless (same record, same identity), but real.
        """
        existing = [{"name": "Jane", "role": "CFO"}]
        result = merge_stakeholders(existing, [{"name": "jane", "influence": "High"}],
                                    source="interview", today=TODAY)
        self.assertEqual(len(existing), 1)
        self.assertEqual(existing[0]["name"], "jane")
        self.assertEqual(result["updated"], ["jane"])

    def test_empty_incoming_fields_do_not_wipe_stored_values(self):
        existing = [{"name": "Jane", "role": "CFO"}]
        merge_stakeholders(existing, [{"name": "Jane", "role": ""}],
                           source="interview", today=TODAY)
        self.assertEqual(existing[0]["role"], "CFO")

    def test_new_person_sharing_a_role_raises_a_duplicate_warning(self):
        existing = [{"name": "Jane", "role": "CFO"}]
        result = merge_stakeholders(existing, [{"name": "John", "role": "CFO"}],
                                    source="interview", today=TODAY)
        self.assertEqual(len(result["dup_warnings"]), 1)

    def test_entry_without_identity_is_skipped(self):
        existing = []
        merge_stakeholders(existing, [{"notes": "anonymous"}], source="x", today=TODAY)
        self.assertEqual(existing, [])

    def test_insert_defaults_apply_when_the_entry_is_created(self):
        existing = []
        merge_stakeholders(existing, [{"name": "Jane"}], source="3.2 plan", today=TODAY,
                           insert_defaults={"coverage_status": "Not covered"})
        self.assertEqual(existing[0]["coverage_status"], "Not covered")

    def test_insert_defaults_do_NOT_apply_on_update(self):
        """THE regression this parameter exists for.

        Without it, re-running 3.2 after an interview resets coverage_status from
        'Elicited' back to 'Not covered' and overwrites found_through — silently
        destroying elicitation progress and the discovery chain.
        """
        existing = [{"name": "Jane", "coverage_status": "Elicited",
                     "found_through": "J. Smith (CFO)"}]
        merge_stakeholders(existing, [{"name": "Jane", "influence": "High"}],
                           source="3.2 plan", today=TODAY,
                           insert_defaults={"coverage_status": "Not covered",
                                            "found_through": "3.2 BA plan"})
        self.assertEqual(existing[0]["coverage_status"], "Elicited")
        self.assertEqual(existing[0]["found_through"], "J. Smith (CFO)")
        self.assertEqual(existing[0]["influence"], "High")

    def test_insert_defaults_do_not_override_an_explicit_incoming_value(self):
        existing = []
        merge_stakeholders(existing, [{"name": "Jane", "coverage_status": "Planned"}],
                           source="x", today=TODAY,
                           insert_defaults={"coverage_status": "Not covered"})
        self.assertEqual(existing[0]["coverage_status"], "Planned")


class TestRegistryFile(BaseMCPTest):

    PID = "a2proj"

    def test_load_returns_a_fresh_registry_when_absent(self):
        registry = load_stakeholder_registry(self.PID)
        self.assertEqual(registry["stakeholders"], [])
        self.assertEqual(registry["project"], self.PID)

    def test_save_then_load_round_trips(self):
        registry = load_stakeholder_registry(self.PID)
        registry["stakeholders"].append({"name": "Jane"})
        self.assertTrue(save_stakeholder_registry(self.PID, registry))
        self.assertEqual(load_stakeholder_registry(self.PID)["stakeholders"][0]["name"],
                         "Jane")

    def test_update_file_merges_persists_and_records_history(self):
        update_stakeholder_registry_file(
            self.PID, [{"name": "Jane", "role": "CFO"}], source="3.2 plan")
        result = update_stakeholder_registry_file(
            self.PID, [{"name": "Jane", "influence": "High"}], source="interview")
        self.assertEqual(result["updated"], ["Jane"])
        self.assertTrue(result["saved"])
        stored = load_stakeholder_registry(self.PID)
        self.assertEqual(len(stored["stakeholders"]), 1)
        self.assertEqual(stored["stakeholders"][0]["influence"], "High")
        self.assertEqual(len(stored["history"]), 2)


class TestRegistryPartyStatusHasThreeAnswers(unittest.TestCase):
    """"Not in the registry" and "there is no registry" are different findings.

    Saying the first when the platform means the second accuses the analyst of an
    omission it cannot see — the distinction PARTY_UNBRIDGEABLE was introduced for
    in B3-2, reused here because the stakeholder registry is a LIVING document.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = os.getcwd()
        os.chdir(self.tmp)
        os.makedirs(os.path.join("governance_plans", "data"), exist_ok=True)

    def tearDown(self):
        os.chdir(self.old)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_registry(self, project_id, stakeholders):
        path = os.path.join("governance_plans", "data",
                            f"{project_id}_stakeholder_registry.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"project": project_id, "stakeholders": stakeholders,
                       "history": []}, f)

    def test_labels_of_a_record_carry_both_name_and_role(self):
        labels = registry_labels({"name": "Ivan Petrov", "role": "Product Owner"})
        self.assertEqual(labels, {"ivan petrov", "product owner"})

    def test_labels_drop_the_empty_ones(self):
        # A registry entry with no name is ordinary — 3.2 seeds role-only rows.
        self.assertEqual(registry_labels({"name": "", "role": "Sponsor"}),
                         {"sponsor"})
        self.assertEqual(registry_labels({"name": None, "role": None}), set())

    def test_a_name_in_the_registry_is_in_registry(self):
        self._write_registry("pstat", [{"name": "Ivan Petrov", "role": "Product Owner"}])
        self.assertEqual(registry_party_status("pstat", "Ivan Petrov"),
                         PARTY_IN_REGISTRY)

    def test_a_role_resolves_too_because_the_bridge_is_two_way(self):
        self._write_registry("pstat2", [{"name": "Ivan Petrov", "role": "Product Owner"}])
        self.assertEqual(registry_party_status("pstat2", "product owner"),
                         PARTY_IN_REGISTRY)

    def test_an_unknown_name_against_a_populated_registry_is_not_in_registry(self):
        self._write_registry("pstat3", [{"name": "Ivan Petrov", "role": "Product Owner"}])
        self.assertEqual(registry_party_status("pstat3", "Nobody At All"),
                         PARTY_NOT_IN_REGISTRY)

    def test_no_registry_at_all_is_unbridgeable_not_absent(self):
        # THE point of the third answer: nothing was written for this project, so the
        # platform cannot say the person is missing — only that it cannot compare.
        self.assertEqual(registry_party_status("pstat_none", "Ivan Petrov"),
                         PARTY_UNBRIDGEABLE)

    def test_an_empty_registry_file_is_not_the_same_as_no_registry(self):
        # WAS `test_an_empty_registry_file_is_also_unbridgeable`, and it cemented the
        # very collapse the third answer exists to prevent (branch review B-1).
        # UNBRIDGEABLE means "there is nothing here to compare against, so no claim can
        # be made" and its advice is "create the registry" — false and unhelpful for a
        # project that HAS one, on disk, that simply holds nobody yet. The registry is
        # a living document: empty is a legitimate early state, not a missing artifact.
        #
        # The old verdict was inconsistent inside this very function too: a registry of
        # [{"influence": "High"}] — rows present, none identifiable — already returned
        # NOT_IN_REGISTRY. Same state, different answer, decided by list length.
        self._write_registry("pstat4", [])
        self.assertEqual(registry_party_status("pstat4", "Ivan Petrov"),
                         PARTY_NOT_IN_REGISTRY)

    def test_a_registry_of_unidentifiable_rows_answers_the_same_as_an_empty_one(self):
        self._write_registry("pstat4b", [{"influence": "High"}])
        self.assertEqual(registry_party_status("pstat4b", "Ivan Petrov"),
                         PARTY_NOT_IN_REGISTRY)

    def test_a_registry_holding_only_null_is_still_a_registry_that_exists(self):
        # The file is there and was read; `stakeholders: null` is a damaged list, not
        # a missing artifact, so "create the registry" is still the wrong advice.
        path = os.path.join("governance_plans", "data",
                            "pstat4c_stakeholder_registry.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"project": "pstat4c", "stakeholders": None}, f)
        self.assertEqual(registry_party_status("pstat4c", "Ivan Petrov"),
                         PARTY_NOT_IN_REGISTRY)

    def test_a_blank_name_is_unbridgeable_rather_than_matching_everything(self):
        self._write_registry("pstat5", [{"name": "Ivan Petrov", "role": "Product Owner"}])
        self.assertEqual(registry_party_status("pstat5", "   "),
                         PARTY_UNBRIDGEABLE)


if __name__ == "__main__":
    unittest.main()
