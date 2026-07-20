"""
tests/test_artifact_layout.py — artifact layout in project subfolders (issue #1).

Covers:
  - safe normalization of project_id (protection against path traversal);
  - the data_path resolver (nested write + flat fallback);
  - save_artifact with project_id (markdown in reports/<project_id>/);
  - the migrate_artifacts.py migration script (move-only, dry-run, idempotent).
"""

import os
import importlib
import shutil
import tempfile
import unittest

import tests.conftest  # noqa: F401  — applies the sys.modules mocks before importing the project
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

    def test_legacy_flat_is_read_in_place(self):
        flat = "governance_plans/data/crm_traceability_repo.json"
        with open(flat, "w", encoding="utf-8") as f:
            f.write("{}")
        p = common.data_path("crm", "crm_traceability_repo.json")
        self.assertEqual(os.path.normpath(p), os.path.normpath(flat))

    def test_nested_wins_over_flat(self):
        os.makedirs("governance_plans/data/crm", exist_ok=True)
        nested = "governance_plans/data/crm/crm_traceability_repo.json"
        with open(nested, "w", encoding="utf-8") as f:
            f.write("{}")
        with open("governance_plans/data/crm_traceability_repo.json", "w", encoding="utf-8") as f:
            f.write("{}")
        p = common.data_path("crm", "crm_traceability_repo.json")
        self.assertEqual(os.path.normpath(p), os.path.normpath(nested))

    def test_legacy_exotic_name_is_found(self):
        # legacy file created by pre-migration normalization (the dot was kept by the old _safe)
        legacy = "governance_plans/data/demo.v2_traceability_repo.json"
        with open(legacy, "w", encoding="utf-8") as f:
            f.write("{}")
        # the runtime builds the name via normalize_project_id (demo_v2_...), but must find the legacy file
        p = common.data_path("demo.v2", "demo_v2_traceability_repo.json")
        self.assertEqual(os.path.normpath(p), os.path.normpath(legacy))

    def test_specs_dir_finds_legacy_exotic(self):
        os.makedirs("governance_plans/data/demo.v2_specs", exist_ok=True)
        d = common.specs_dir("demo.v2")
        self.assertEqual(
            os.path.normpath(d),
            os.path.normpath("governance_plans/data/demo.v2_specs"),
        )

    def test_specs_dir_new_is_nested_canonical(self):
        d = common.specs_dir("Demo V2")
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
        # conftest mocked common.save_artifact — restore the real one via reload
        importlib.reload(common)

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)
        importlib.reload(common)  # restore the module state (conftest mocks)

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
        common.save_artifact("# hi", "Elicitation_Plan_CRM/Q3 upgrade", project_id="CRM/Q3 upgrade")
        written = []
        for root, _dirs, fs in os.walk("governance_plans/reports"):
            for f in fs:
                written.append(os.path.normpath(os.path.join(root, f)))
        self.assertEqual(len(written), 1)
        self.assertTrue(
            written[0].startswith(os.path.normpath("governance_plans/reports/crm_q3_upgrade")),
            written[0])
        self.assertFalse(os.path.isdir(os.path.join("governance_plans", "reports", "CRM")))

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


class TestMigration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._cwd = os.getcwd()
        os.chdir(self.tmp)
        os.makedirs("governance_plans/data", exist_ok=True)
        os.makedirs("governance_plans/reports", exist_ok=True)

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, path, text="{}"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def test_moves_flat_data_into_subdir(self):
        import migrate_artifacts
        self._write("governance_plans/data/crm_traceability_repo.json", '{"x":1}')
        migrate_artifacts.migrate(apply=True)
        self.assertTrue(os.path.exists("governance_plans/data/crm/crm_traceability_repo.json"))
        self.assertFalse(os.path.exists("governance_plans/data/crm_traceability_repo.json"))
        with open("governance_plans/data/crm/crm_traceability_repo.json", encoding="utf-8") as f:
            self.assertEqual(f.read(), '{"x":1}')  # data is intact

    def test_dry_run_moves_nothing(self):
        import migrate_artifacts
        self._write("governance_plans/data/crm_traceability_repo.json")
        migrate_artifacts.migrate(apply=False)
        self.assertTrue(os.path.exists("governance_plans/data/crm_traceability_repo.json"))

    def test_idempotent_and_never_overwrites(self):
        import migrate_artifacts
        self._write("governance_plans/data/crm/crm_traceability_repo.json", '{"nested":1}')
        self._write("governance_plans/data/crm_traceability_repo.json", '{"flat":1}')
        migrate_artifacts.migrate(apply=True)  # target is occupied → don't touch either
        with open("governance_plans/data/crm/crm_traceability_repo.json", encoding="utf-8") as f:
            self.assertEqual(f.read(), '{"nested":1}')
        self.assertTrue(os.path.exists("governance_plans/data/crm_traceability_repo.json"))

    def test_specs_dir_migrates(self):
        import migrate_artifacts
        self._write("governance_plans/data/crm_specs/dd_001.md", "# dd")
        migrate_artifacts.migrate(apply=True)
        self.assertTrue(os.path.exists("governance_plans/data/crm/specs/dd_001.md"))

    def test_report_with_embedded_project_migrates(self):
        import migrate_artifacts
        self._write("governance_plans/reports/6_1_current_state_crm_20260616_120000.md", "# r")
        migrate_artifacts.migrate(apply=True)
        self.assertTrue(os.path.exists(
            "governance_plans/reports/crm/6_1_current_state_crm_20260616_120000.md"))

    def test_report_without_project_stays_put(self):
        import migrate_artifacts
        self._write("governance_plans/reports/4_4_comm_package_20260616_120000.md", "# r")
        migrate_artifacts.migrate(apply=True)
        self.assertTrue(os.path.exists(
            "governance_plans/reports/4_4_comm_package_20260616_120000.md"))

    def test_migration_canonicalizes_exotic_name(self):
        # legacy file with an exotic name → canonical layout (both folder and name normalized)
        import migrate_artifacts
        import skills.common as c
        self._write("governance_plans/data/demo.v2_traceability_repo.json", '{"x":1}')
        migrate_artifacts.migrate(apply=True)
        self.assertTrue(os.path.exists(
            "governance_plans/data/demo_v2/demo_v2_traceability_repo.json"))
        # and the runtime finds the file by the original (exotic) project_id
        self.assertTrue(os.path.exists(c.data_path("demo.v2", "demo_v2_traceability_repo.json")))
        with open("governance_plans/data/demo_v2/demo_v2_traceability_repo.json", encoding="utf-8") as f:
            self.assertEqual(f.read(), '{"x":1}')
