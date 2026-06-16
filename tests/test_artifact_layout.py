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
