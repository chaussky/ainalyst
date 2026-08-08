"""
tests/test_json_writer.py

Durability of the stored artifacts — the one guarantee the platform never made.

Every project fact the analyst owns (the requirements graph, the approval decisions,
the priorities) lives in a JSON file, and until now 32 places wrote such a file the
same unsafe way: `open(path, "w")` TRUNCATES the previous version before a single
byte of the new one is written. An interruption there — Ctrl+C, a full disk, an
antivirus holding the handle — left a half-written file and took the whole project
with it. There were no backups: the error message for a damaged artifact already
advised "restore it from a backup" while nothing on disk could satisfy that advice.

Three properties are pinned here, and they cover different failure modes:

  * atomicity   — a write that fails part-way leaves the PREVIOUS version whole.
                  This is what `os.replace` buys: the name points at one complete
                  file or the other, never at a torn one.
  * generations — the previous version is copied aside before being replaced. This
                  covers what atomicity CANNOT: logical corruption written by our
                  own correct-looking code (init_traceability_repo once destroyed a
                  node type this way) and hand edits.
  * shape       — refuse to write a graph that is not a graph. Validation on READ
                  has existed for a while; the write side accepted anything, so a
                  wrong-shaped structure became the stored truth and the read-side
                  guard only reported it afterwards.
"""

import json
import os
import sys
import unittest
from unittest import mock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tests.conftest import BaseMCPTest, make_test_repo, save_test_repo, data_file

import skills.common as m


def _graph(title: str = "first") -> dict:
    return {"requirements": [{"id": "FR-001", "title": title}], "links": []}


def _repo_target(pid: str = "writer_probe") -> str:
    """A path the shape check treats as the requirements graph."""
    return data_file(pid, "traceability_repo.json")


def _history_copies(target: str) -> list:
    """The generations kept for one artifact, oldest first."""
    hist = os.path.join(m.BASE_DIR, m.HISTORY_DIRNAME)
    if not os.path.isdir(hist):
        return []
    stem = os.path.basename(target) + "."
    return sorted(f for f in os.listdir(hist)
                  if f.startswith(stem) and f.endswith(".json"))


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class TestAtomicWrite(BaseMCPTest):
    """A failed write must not consume the version that was already on disk."""

    def test_the_write_is_interrupted_at_the_moment_of_replacement(self):
        """The discriminating test for the atomic rename.

        The replacement is fully built and the process dies before it is moved into
        place. An implementation that writes THROUGH the artifact has already
        truncated it by this point and loses everything; one that builds a temporary
        file and renames it loses only the new version.
        """
        target = _repo_target()
        m.write_json_artifact(target, _graph("survivor"))
        before = _read(target)

        with mock.patch.object(m.os, "replace",
                               side_effect=OSError("simulated interruption")):
            with self.assertRaises(OSError):
                m.write_json_artifact(target, _graph("never stored"))

        self.assertEqual(_read(target), before,
                         "the previous version must survive an interrupted write")
        self.assertEqual(json.loads(_read(target))["requirements"][0]["title"],
                         "survivor")

    def test_an_interrupted_write_leaves_no_debris_beside_the_artifact(self):
        target = _repo_target()
        m.write_json_artifact(target, _graph())
        with mock.patch.object(m.os, "replace", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                m.write_json_artifact(target, _graph("never stored"))

        siblings = os.listdir(os.path.dirname(target))
        self.assertEqual(siblings, [os.path.basename(target)],
                         f"a temporary file was left behind: {siblings}")

    def test_content_that_cannot_be_encoded_never_touches_the_stored_file(self):
        """A set is not JSON-serialisable — a defect in the calling tool. The cost
        of that defect must not be the analyst's stored project."""
        target = _repo_target()
        m.write_json_artifact(target, _graph("survivor"))
        before = _read(target)

        with self.assertRaises(TypeError):
            m.write_json_artifact(target, {"requirements": [], "links": [],
                                           "bad": {1, 2, 3}})

        self.assertEqual(_read(target), before)
        self.assertEqual(os.listdir(os.path.dirname(target)),
                         [os.path.basename(target)])

    def test_a_successful_write_does_replace_the_content(self):
        target = _repo_target()
        m.write_json_artifact(target, _graph("old"))
        m.write_json_artifact(target, _graph("new"))
        self.assertEqual(
            json.loads(_read(target))["requirements"][0]["title"], "new")

    def test_the_writer_creates_the_folder_it_writes_into(self):
        target = os.path.join(m.DATA_DIR, "brand_new", "brand_new_prio.json")
        m.write_json_artifact(target, {"project": "brand_new"})
        self.assertTrue(os.path.isfile(target))


class TestGenerations(BaseMCPTest):
    """The version being replaced is copied aside, and the copies are bounded."""

    def test_the_replaced_version_is_copied_into_history(self):
        target = _repo_target()
        m.write_json_artifact(target, _graph("generation-1"))
        m.write_json_artifact(target, _graph("generation-2"))

        copies = _history_copies(target)
        self.assertEqual(len(copies), 1,
                         "replacing a file must leave its predecessor behind")
        kept = json.loads(_read(os.path.join(m.BASE_DIR, m.HISTORY_DIRNAME,
                                             copies[0])))
        self.assertEqual(kept["requirements"][0]["title"], "generation-1")

    def test_creating_a_file_copies_nothing(self):
        target = _repo_target()
        m.write_json_artifact(target, _graph())
        self.assertEqual(_history_copies(target), [],
                         "there is no predecessor to keep on the first write")

    def test_history_keeps_five_generations_and_discards_older_ones(self):
        target = _repo_target()
        for i in range(8):
            m.write_json_artifact(target, _graph(f"v{i}"))

        copies = _history_copies(target)
        self.assertEqual(len(copies), 5, f"expected 5 generations, got {copies}")

        hist = os.path.join(m.BASE_DIR, m.HISTORY_DIRNAME)
        titles = [json.loads(_read(os.path.join(hist, c)))["requirements"][0]["title"]
                  for c in copies]
        # Eight writes replace v0..v6; the five survivors are the most recent of them.
        self.assertEqual(titles, ["v2", "v3", "v4", "v5", "v6"],
                         "the five KEPT generations must be the five newest")

    def test_one_project_does_not_evict_another_projects_generations(self):
        """The flat .history/ rests on artifact names carrying the project prefix."""
        mine = _repo_target("proj_a")
        yours = _repo_target("proj_b")
        for i in range(8):
            m.write_json_artifact(mine, _graph(f"a{i}"))
        m.write_json_artifact(yours, _graph("b0"))
        m.write_json_artifact(yours, _graph("b1"))

        self.assertEqual(len(_history_copies(mine)), 5)
        self.assertEqual(len(_history_copies(yours)), 1,
                         "pruning must count per artifact, not per directory")

    def test_an_interrupted_copy_does_not_leave_a_torn_generation_behind(self):
        """A backup is a write too, and it fails the same ways. A half-copied
        generation is worse than a missing one: it occupies one of the five slots
        and only announces itself on the day someone needs it."""
        target = _repo_target()
        m.write_json_artifact(target, _graph("v1"))

        def dies_part_way(src, dst, *args, **kwargs):
            with open(dst, "w", encoding="utf-8") as f:
                f.write('{"requirem')
            raise OSError("interrupted while copying")

        with mock.patch.object(m.shutil, "copy2", side_effect=dies_part_way):
            m.write_json_artifact(target, _graph("v2"))

        history = os.path.join(m.BASE_DIR, m.HISTORY_DIRNAME)
        leftovers = os.listdir(history) if os.path.isdir(history) else []
        self.assertEqual(leftovers, [],
                         f"a torn backup was kept: {leftovers}")
        # The analyst's actual work still went through — a backup that cannot be
        # taken is a warning, not a refusal.
        self.assertEqual(
            json.loads(_read(target))["requirements"][0]["title"], "v2")

    def test_debris_from_a_killed_process_does_not_take_a_generation_slot(self):
        """A process killed outright gets no chance to clean up after itself. What
        it leaves in .history/ must not be counted as a version — counting it would
        quietly evict a real one, which is the exact loss the directory prevents."""
        target = _repo_target()
        for i in range(6):
            m.write_json_artifact(target, _graph(f"v{i}"))

        history = os.path.join(m.BASE_DIR, m.HISTORY_DIRNAME)
        # Dated far ahead so a filter that counts it would keep it and drop a real one.
        debris = os.path.join(
            history, f"{os.path.basename(target)}.29991231_235959_999999.json.part")
        with open(debris, "w", encoding="utf-8") as f:
            f.write('{"requirem')

        m.write_json_artifact(target, _graph("v6"))

        self.assertEqual(len(_history_copies(target)), 5,
                         "debris must not displace a real generation")
        self.assertNotIn(os.path.basename(debris), _history_copies(target))

    def test_a_generation_is_a_byte_for_byte_copy_of_what_was_replaced(self):
        target = _repo_target()
        m.write_json_artifact(target, _graph("exact"))
        original = _read(target)
        m.write_json_artifact(target, _graph("next"))

        copy = os.path.join(m.BASE_DIR, m.HISTORY_DIRNAME,
                            _history_copies(target)[0])
        self.assertEqual(_read(copy), original)


class TestShapeCheckOnWrite(BaseMCPTest):
    """A graph file may only receive something shaped like a graph."""

    def test_a_graph_missing_its_links_is_refused(self):
        target = _repo_target()
        with self.assertRaises(m.ArtifactShapeError):
            m.write_json_artifact(target, {"requirements": []})

    def test_a_graph_whose_requirements_are_not_a_list_is_refused(self):
        target = _repo_target()
        with self.assertRaises(m.ArtifactShapeError):
            m.write_json_artifact(target, {"requirements": "FR-001", "links": []})

    def test_a_refused_write_leaves_the_stored_graph_untouched(self):
        target = _repo_target()
        m.write_json_artifact(target, _graph("keep me"))
        before = _read(target)
        with self.assertRaises(m.ArtifactShapeError):
            m.write_json_artifact(target, {"requirements": {}, "links": []})
        self.assertEqual(_read(target), before)
        self.assertEqual(_history_copies(target), [],
                         "a refusal is not a generation — nothing was replaced")

    def test_a_non_graph_artifact_is_not_asked_for_graph_keys(self):
        target = data_file("writer_probe", "prioritization.json")
        m.write_json_artifact(target, {"project": "writer_probe", "items": []})
        self.assertTrue(os.path.isfile(target))

    def test_the_refusal_reaches_the_analyst_as_a_cross_line(self):
        """The claim the design rests on: the shape error is a CorruptArtifactError,
        so the EXISTING tool boundary converts it instead of letting it escape as a
        protocol error."""
        target = _repo_target()

        @m.guard_artifact_errors
        def a_tool():
            m.write_json_artifact(target, {"requirements": None, "links": None})
            return "✅ written"

        answer = a_tool()
        self.assertIsInstance(answer, str)
        self.assertIn("❌", answer)
        self.assertIn(os.path.basename(target), answer,
                      "the refusal must name the file it refused to write")
        self.assertNotIn("✅", answer)


class TestTheRestoreAdviceIsExecutable(BaseMCPTest):
    """The message for a damaged artifact told the analyst to "restore it from a
    backup" for as long as no backup existed anywhere. Advice that cannot be carried
    out is worse than no advice: it sends someone looking for a file that was never
    written. Now that generations exist, the message must point AT them — and the
    place it points at must actually hold a copy at the moment it is printed."""

    def test_the_damaged_file_message_points_at_a_directory_that_has_the_copy(self):
        target = _repo_target()
        m.write_json_artifact(target, _graph("v1"))
        m.write_json_artifact(target, _graph("v2"))
        with open(target, "w", encoding="utf-8") as f:
            f.write('{"requirements": [ truncated')

        with self.assertRaises(m.CorruptArtifactError) as caught:
            m.read_json_artifact(target, "5.1 traceability repository")
        message = str(caught.exception)

        history = os.path.join(m.BASE_DIR, m.HISTORY_DIRNAME)
        self.assertIn(history, message,
                      "the advice must name where the copies are")
        copies = _history_copies(target)
        self.assertTrue(copies, "the named directory must actually hold a copy")

        # And carrying the advice out has to work.
        import shutil
        shutil.copy2(os.path.join(history, copies[-1]), target)
        self.assertEqual(
            json.loads(_read(target))["requirements"][0]["title"], "v1")


class TestEveryChapterWritesThroughTheWriter(BaseMCPTest):
    """The writer is worth nothing if 32 call sites still bypass it."""

    def test_a_real_tool_leaves_a_generation_behind(self):
        import skills.requirements_traceability_mcp as ch51

        repo = make_test_repo("writerlive")
        target = save_test_repo(repo)
        answer = ch51.add_trace_link(
            "writerlive", from_id="FR-002", to_id="BR-001",
            relation="derives", rationale="written by a real tool",
        )
        self.assertIn("✅", answer)
        self.assertEqual(len(_history_copies(target)), 1,
                         "a chapter tool must write through the shared writer")
        kept = json.loads(_read(os.path.join(m.BASE_DIR, m.HISTORY_DIRNAME,
                                             _history_copies(target)[0])))
        self.assertEqual(len(kept["links"]), 2,
                         "the generation must hold the graph as it was BEFORE the call")
        self.assertEqual(len(json.loads(_read(target))["links"]), 3)


class TestNoDirectWritesRemain(unittest.TestCase):
    """A structural guard: the next tool cannot quietly reintroduce the old way."""

    def test_no_skill_module_dumps_json_into_a_file_itself(self):
        import glob as _glob
        offenders = []
        for path in _glob.glob(os.path.join(PROJECT_ROOT, "skills", "**", "*.py"),
                               recursive=True):
            with open(path, "r", encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    if "json.dump(" in line:
                        offenders.append(f"{os.path.basename(path)}:{n}")
        self.assertEqual(
            offenders, [],
            "these places write JSON straight over the previous version; "
            f"route them through write_json_artifact: {offenders}")


if __name__ == "__main__":
    unittest.main()
