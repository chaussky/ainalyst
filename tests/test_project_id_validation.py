"""
tests/test_project_id_validation.py — a project_id that cannot be represented as a
directory name is REFUSED, not silently replaced.

Why this exists (E2E gate 2026-08-03, dimension "alphabet"):
  normalize_project_id keeps the whitelist [a-z0-9_-], so every cyrillic id collapsed
  to the same placeholder '_unknown'. Two DIFFERENT projects then shared one directory
  and silently mixed each other's artifacts: a delivered 6.1 document titled after
  project C listed the business needs of projects A and B. A mixed id was worse still —
  'crm_обновление' collapsed onto the EXISTING project 'crm' and served its data back.

  Owner's decision (2026-08-03): REFUSE such an id with a message naming the allowed
  alphabet and a ready latin suggestion. Transliteration is used ONLY to build that
  hint — never to build a path, so no hidden state enters the artifact layout.

What must NOT change (pinned elsewhere, restated here so a future "fix" cannot merge
the two concepts): normalize_project_id stays a pure normalizer and keeps returning
'_unknown' for input it cannot represent. The refusal lives in a separate validator,
because the normalizer is also what builds paths for ids that are already valid.
"""

import os
import shutil
import tempfile
import unittest
import unittest.mock

import tests.conftest  # noqa: F401  — applies the sys.modules mocks first
import skills.common as common


class TestTheValidatorSeparatesRefusalFromNormalisation(unittest.TestCase):
    def test_the_normaliser_itself_is_unchanged(self):
        # The refusal must NOT be implemented by making the normaliser raise: it is
        # called on already-valid ids all over the codebase, and on the legacy path
        # fallbacks. Merging the two concepts is the regression this pins.
        self.assertEqual(common.normalize_project_id(""), "_unknown")
        self.assertEqual(common.normalize_project_id(".."), "_unknown")
        self.assertEqual(common.normalize_project_id("  CRM Up "), "crm_up")

    def test_two_different_cyrillic_ids_are_both_refused(self):
        first = common.project_id_error("црм_апгрейд")
        second = common.project_id_error("банк_портал")
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        # and the reason names the offending id, so two refusals are distinguishable
        self.assertIn("црм_апгрейд", first)
        self.assertIn("банк_портал", second)

    def test_a_mixed_id_is_refused_even_though_it_normalises_to_something(self):
        # 'crm_обновление' -> 'crm' is the dangerous case: the result is not a
        # placeholder, it is the name of a REAL other project.
        self.assertEqual(common.normalize_project_id("crm_обновление"), "crm")
        self.assertIsNotNone(common.project_id_error("crm_обновление"))

    def test_ids_that_normalise_to_the_placeholder_are_refused(self):
        for pid in ("!!!", "...", "   ", "", "-", "проект-1", "CRM/Q3 отчёт"):
            self.assertIsNotNone(common.project_id_error(pid), pid)

    def test_two_spellings_that_would_share_a_directory_are_refused(self):
        # 'a  b' and 'a b' both normalise to 'a_b'; only single-spaced words survive.
        self.assertIsNotNone(common.project_id_error("a  b"))

    def test_valid_ids_still_pass_untouched(self):
        for pid in ("crm_upgrade", "bank-portal", "hr_auto2", "crm2"):
            self.assertIsNone(common.project_id_error(pid), pid)

    def test_a_spelling_the_normaliser_would_rewrite_is_refused(self):
        """The rule is a FIXED POINT: an id must already be spelled the way its folder
        will be (owner's decision, 2026-08-03, second round).

        Every id below used to be accepted and folded. Folding is what made two
        different ids share one folder — `demo.v2` and `demo_v2` were two projects
        with one set of artifacts between them."""
        for pid in ("CRM Up", "  crm  ", "demo.v2", "crm__up", "_crm", "crm-",
                    "CRM_UPGRADE"):
            message = common.project_id_error(pid)
            self.assertIsNotNone(message, f"{pid!r} would be rewritten, so it is not an id")
            self.assertEqual(common.project_id_error(common.normalize_project_id(pid)), None,
                             f"the normalised form of {pid!r} must itself be usable")

    def test_the_guard_does_not_consult_the_disk(self):
        # The trap this pins: an earlier design let an id through when its normalised
        # folder already existed. That is exactly backwards — 'crm_обновление' folds
        # onto the EXISTING project 'crm', and "the folder exists" is true precisely
        # when another project's data is about to be served back as this one's.
        import tempfile
        tmp = tempfile.mkdtemp()
        cwd = os.getcwd()
        try:
            os.chdir(tmp)
            os.makedirs("governance_plans/data/crm", exist_ok=True)
            with open("governance_plans/data/crm/crm_business_needs.json", "w",
                      encoding="utf-8") as f:
                f.write("{}")
            with self.assertRaises(common.InvalidProjectIdError):
                common.data_path("crm_обновление", "crm_business_needs.json")
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_refusal_names_the_alphabet_and_offers_a_latin_suggestion(self):
        msg = common.project_id_error("црм_апгрейд")
        self.assertIn("a-z", msg)
        self.assertIn("crm_apgreyd", msg)

    def test_the_suggestion_is_itself_a_valid_id(self):
        for pid in ("црм_апгрейд", "банк_портал", "проект-1", "Портал Клиента"):
            msg = common.project_id_error(pid)
            suggestion = common.project_id_suggestion(pid)
            self.assertIsNone(common.project_id_error(suggestion), (pid, suggestion))
            self.assertIn(suggestion, msg)

    def test_an_id_with_nothing_transliterable_still_gets_a_usable_example(self):
        suggestion = common.project_id_suggestion("!!!")
        self.assertIsNone(common.project_id_error(suggestion))


class TestTheRefusalReachesTheToolAsAnAnswer(unittest.TestCase):
    """A refusal must arrive as the ❌ string a tool returns — never as an exception.
    Point 1 of the gate's failure definition is 'an unhandled exception instead of a
    tool answer'."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._cwd = os.getcwd()
        os.chdir(self.tmp)
        os.makedirs("governance_plans/data", exist_ok=True)
        os.makedirs("governance_plans/reports", exist_ok=True)

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_path_helpers_raise_the_dedicated_error(self):
        for helper in (common.data_dir_for, common.report_dir_for, common.specs_dir):
            with self.assertRaises(common.InvalidProjectIdError, msg=helper.__name__):
                helper("црм_апгрейд")
        with self.assertRaises(common.InvalidProjectIdError):
            common.data_path("црм_апгрейд", "x.json")

    def test_the_tool_boundary_turns_it_into_an_answer(self):
        @common.guard_artifact_errors
        def fake_tool(project_id):
            return common.data_dir_for(project_id)

        out = fake_tool("црм_апгрейд")
        self.assertIsInstance(out, str)
        self.assertTrue(out.startswith("❌"), out)
        self.assertIn("crm_apgreyd", out)

    def test_a_refused_id_writes_nothing_to_disk(self):
        """Against a REAL writing tool, not a path builder.

        The first version of this test called data_dir_for, which only ever builds a
        string — it passed whatever the guard did, so it protected nothing. The promise
        under test ("No project data has been written") is only meaningful for a tool
        that would otherwise write.
        """
        import skills.requirements_traceability_mcp as tr51
        reqs = '[{"id": "FR-001", "type": "solution", "title": "x", "version": "1.0"}]'
        for pid in ("црм_апгрейд", "банк_портал", "_unknown", "!!!"):
            out = tr51.init_traceability_repo(
                project_name=pid, formality_level="Standard", requirements_json=reqs)
            self.assertTrue(str(out).startswith("❌"), (pid, str(out)[:80]))
        written = []
        for root, _dirs, files in os.walk("governance_plans"):
            written += [os.path.join(root, f) for f in files]
        self.assertEqual(written, [], written)
        self.assertFalse(os.path.exists(os.path.join("governance_plans/data", "_unknown")))
        self.assertFalse(os.path.exists(os.path.join("governance_plans/data", "unknown")))

    def test_the_placeholder_is_not_itself_a_usable_id(self):
        """The value normalize_project_id falls back to must never be accepted AS an id.

        It passed the alphabet check, so a caller that normalised before asking — the
        contract is to pass the RAW id — walked past the guard and every unusable id
        collapsed onto this one folder again. Found by blind review; the hole defeated
        the whole point of the guard.
        """
        for pid in ("_unknown", "unknown", "__unknown__", "UNKNOWN"):
            self.assertIsNotNone(common.project_id_error(pid), pid)

    def test_pre_normalising_before_asking_cannot_smuggle_an_id_through(self):
        for raw in ("црм_апгрейд", "банк_портал", "統一平台"):
            pre = common.normalize_project_id(raw)
            with self.assertRaises(common.InvalidProjectIdError, msg=raw):
                common.data_path(pre, f"{pre}_x.json")

    def test_the_suggestion_never_recurses_on_a_reserved_word(self):
        # project_id_error and project_id_suggestion used to call each other; an id of
        # 'unknown' made the pair recurse without end.
        self.assertIsInstance(common.project_id_suggestion("unknown"), str)
        self.assertIsInstance(common.project_id_error("unknown"), str)

    def test_an_uncoverable_alphabet_is_not_handed_a_shared_name(self):
        """Two projects in an alphabet the table does not cover must not both be told
        to use the same id — that is the original collision, rebuilt through advice."""
        for pid in ("統一平台", "منصة", "!!!"):
            msg = common.project_id_error(pid)
            self.assertNotIn(f"Try: `{common._PID_FALLBACK_SUGGESTION}`", msg, pid)
            self.assertIn("pick a short latin name yourself", msg, pid)

    def test_a_valid_id_is_unaffected(self):
        self.assertEqual(
            os.path.normpath(common.data_dir_for("crm_upgrade")),
            os.path.normpath("governance_plans/data/crm_upgrade"),
        )


class TestEveryToolTakingAProjectIdIsGuarded(unittest.TestCase):
    """The tool boundary is what turns the refusal into an answer instead of a protocol
    error. It was applied by hand to 109 tools; nothing stopped the 110th from arriving
    without it, and a blind-review mutation proved the gap — removing one decorator left
    the whole suite green. This test is that missing guard.
    """

    def test_all_of_them_carry_the_boundary_decorator(self):
        import glob
        import importlib
        import inspect

        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        unguarded = []
        checked = 0
        for path in glob.glob(os.path.join(root, "skills", "**", "*_mcp.py"),
                              recursive=True):
            module_name = (os.path.relpath(path, root)
                           .replace(os.sep, ".")[:-len(".py")])
            module = importlib.import_module(module_name)
            source = open(path, encoding="utf-8").read()
            for name, fn in vars(module).items():
                if name.startswith("_") or not inspect.isfunction(fn):
                    continue
                if fn.__module__ != module_name:
                    continue
                # a tool is a module-level function registered with @mcp.tool()
                head = source.split(f"def {name}(")[0].rsplit("\n\n", 1)[-1]
                if "@mcp.tool()" not in head:
                    continue
                params = set(inspect.signature(fn).parameters)
                if not (params & {"project_id", "project_name"}):
                    continue
                checked += 1
                if not hasattr(fn, "__wrapped__"):
                    unguarded.append(f"{module_name}.{name}")

        self.assertGreater(checked, 90, "the scan found almost no tools — it broke")
        self.assertEqual(
            unguarded, [],
            "these tools take a project id but are not wrapped in "
            "@guard_artifact_errors, so an invalid id escapes as an unhandled "
            f"exception instead of an answer: {unguarded}")


class TestCyrillicContentStillPassesThrough(unittest.TestCase):
    """The refusal is about the ID only. Cyrillic in the CONTENT — stakeholder names,
    requirement titles — must keep working; that is what the ru port depends on."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._cwd = os.getcwd()
        os.chdir(self.tmp)
        os.makedirs("governance_plans/reports", exist_ok=True)

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    @staticmethod
    def _real_common():
        """A private module instance whose save_artifact is the REAL writer.

        conftest.setup_mocks replaces skills.common.save_artifact with a MagicMock for
        the whole suite, so asserting "the bytes landed on disk" against the shared
        module would pass against a mock that writes nothing. Loading a separate module
        object leaves the suite-wide mock untouched.
        """
        import importlib.util
        spec = importlib.util.find_spec("skills.common")
        fresh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fresh)
        assert not isinstance(fresh.save_artifact, unittest.mock.MagicMock)
        return fresh

    def test_a_cyrillic_document_body_is_written_and_read_back(self):
        body = "# Требования\n\nИванов И.И. — Владелец продукта"
        self._real_common().save_artifact(body, prefix="test_cyr",
                                          project_id="crm_upgrade")
        out_dir = os.path.join("governance_plans/reports", "crm_upgrade")
        files = os.listdir(out_dir)
        self.assertEqual(len(files), 1)
        written = open(os.path.join(out_dir, files[0]), encoding="utf-8").read()
        self.assertIn("Иванов И.И.", written)
        self.assertIn("Владелец продукта", written)


if __name__ == "__main__":
    unittest.main()
