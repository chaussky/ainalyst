"""
tests/test_artifact_layout.py — раскладка артефактов по подкаталогам проекта (issue #1).

Covers:
  - safe normalization of project_id (protection against path traversal);
  - the data_path resolver (one location: data/<project_id>/);
  - save_artifact with project_id (markdown in reports/<project_id>/).
"""

import os
import importlib
import shutil
import tempfile
import unittest

import tests.conftest  # noqa: F401  — применяет моки sys.modules до импорта проекта
import skills.common as common


class TestNormalizeProjectId(unittest.TestCase):
    def test_basic_lower_and_spaces(self):
        self.assertEqual(common.normalize_project_id("  CRM Up "), "crm_up")

    def test_traversal_is_neutralized(self):
        for evil in ["../../etc", "..", "a/b\\c", "/abs/path", "..\\..\\x"]:
            out = common.normalize_project_id(evil)
            self.assertNotIn("/", out)
            self.assertNotIn("\\", out)
            self.assertNotIn("..", out)
            joined = os.path.realpath(os.path.join(common.DATA_DIR, out))
            base = os.path.realpath(common.DATA_DIR)
            self.assertTrue(joined.startswith(base))

    def test_empty_becomes_unknown(self):
        self.assertEqual(common.normalize_project_id(""), "_unknown")
        self.assertEqual(common.normalize_project_id(".."), "_unknown")


class TestDataPath(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._cwd = os.getcwd()
        os.chdir(self.tmp)
        os.makedirs("governance_plans/data", exist_ok=True)

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_new_artifact_goes_nested(self):
        p = common.data_path("crm", "crm_traceability_repo.json")
        self.assertEqual(
            os.path.normpath(p),
            os.path.normpath("governance_plans/data/crm/crm_traceability_repo.json"),
        )

    def test_a_file_beside_the_project_folder_is_not_this_project_s_file(self):
        """The resolver answers with ONE location and does not go looking around it.

        It used to try five, so that artifacts predating the per-project layout kept
        resolving. A flat file carries no project id in its folder, so the search
        could only ever be a guess — and it guessed against whatever happened to be
        on disk. Owner's decision (2026-08-03): one layout, no fallbacks."""
        flat = "governance_plans/data/crm_traceability_repo.json"
        with open(flat, "w", encoding="utf-8") as f:
            f.write("{}")
        p = common.data_path("crm", "crm_traceability_repo.json")
        self.assertEqual(
            os.path.normpath(p),
            os.path.normpath("governance_plans/data/crm/crm_traceability_repo.json"))

    def test_specs_dir_is_nested_canonical(self):
        d = common.specs_dir("demo_v2")
        self.assertEqual(
            os.path.normpath(d),
            os.path.normpath("governance_plans/data/demo_v2/specs"),
        )

    def test_dir_helpers(self):
        self.assertEqual(
            os.path.normpath(common.data_dir_for("crm")),
            os.path.normpath("governance_plans/data/crm"),
        )
        self.assertEqual(
            os.path.normpath(common.report_dir_for("crm")),
            os.path.normpath("governance_plans/reports/crm"),
        )


class TestSaveArtifact(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._cwd = os.getcwd()
        os.chdir(self.tmp)
        # conftest замокал common.save_artifact — восстановим реальную через reload
        importlib.reload(common)

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)
        importlib.reload(common)  # вернуть состояние модуля (моки conftest)

    def test_with_project_id_nests(self):
        common.save_artifact("# hi", "6_1_current_state_crm", project_id="crm")
        files = []
        for root, _dirs, fs in os.walk("governance_plans/reports"):
            for f in fs:
                files.append(os.path.join(root, f))
        self.assertEqual(len(files), 1)
        self.assertIn(
            os.path.normpath("governance_plans/reports/crm"),
            os.path.normpath(files[0]),
        )

    def test_without_project_id_is_flat_backcompat(self):
        common.save_artifact("# hi", "legacy_prefix")
        flat = [f for f in os.listdir("governance_plans/reports") if f.endswith(".md")]
        self.assertEqual(len(flat), 1)

    # --- the FILENAME needed the same guard the DIRECTORY already had ---------

    def test_separator_in_prefix_does_not_escape_the_project_folder(self):
        """Several tools build the prefix from free text (project name, session date):
        e.g. "Elicitation_Plan_{project_name}". normalize_project_id guarded the folder,
        but a separator inside the PREFIX made the write land outside it — or fail with
        FileNotFoundError because the implied directory does not exist."""
        # The project_id here is a VALID one: since the E2E gate of 2026-08-03 an id
        # carrying a separator is refused outright (see the assertion at the end and
        # tests/test_project_id_validation.py). The property this test exists for —
        # a separator inside the PREFIX must not steer the write out of the folder —
        # is unaffected by that decision and is still exercised.
        common.save_artifact("# hi", "Elicitation_Plan_CRM/Q3 upgrade", project_id="crm_q3_upgrade")
        written = []
        for root, _dirs, fs in os.walk("governance_plans/reports"):
            for f in fs:
                written.append(os.path.normpath(os.path.join(root, f)))
        self.assertEqual(len(written), 1)
        self.assertTrue(
            written[0].startswith(os.path.normpath("governance_plans/reports/crm_q3_upgrade")),
            written[0])
        self.assertFalse(os.path.isdir(os.path.join("governance_plans", "reports", "CRM")))

        # ...and the id itself no longer gets silently rewritten into that folder.
        with self.assertRaises(common.InvalidProjectIdError):
            common.save_artifact("# hi", "Elicitation_Plan", project_id="CRM/Q3 upgrade")

    def test_backslash_and_traversal_in_prefix_neutralized(self):
        common.save_artifact("# hi", "..\\..\\evil", project_id="proj")
        written = [f for f in os.listdir("governance_plans/reports/proj")]
        self.assertEqual(len(written), 1)
        self.assertNotIn("..", written[0])

    def test_ordinary_prefixes_are_unchanged(self):
        """The guard must not rename the artifacts the platform already produces."""
        for prefix in ("4_3_confirmed_result", "6_1_current_state_crm", "confluence_pull",
                       "Elicitation_Results_crm_upgrade_12-03-2026"):
            self.assertEqual(common.safe_filename_part(prefix), prefix)
