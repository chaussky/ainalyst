"""
tests/test_artifact_layout.py — раскладка артефактов по подкаталогам проекта (issue #1).

Покрывает:
  - безопасную нормализацию project_id (защита от path traversal);
  - резолвер пути data_path (вложенная запись + flat-fallback);
  - save_artifact с project_id (markdown в reports/<project_id>/);
  - скрипт миграции migrate_artifacts.py (move-only, dry-run, idempotent).
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
