"""Tests for lab/lab_paths.py. All names in this file are made up."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lab"))
sys.path.insert(0, HERE)

import lab_paths as lp  # noqa: E402


class DataDirTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = os.path.join(self.tmp.name, "repo")
        os.makedirs(os.path.join(self.repo, ".git"))
        self.outside = os.path.join(self.tmp.name, "scratch")
        os.makedirs(self.outside)

    def test_an_unset_variable_fails(self):
        with self.assertRaises(lp.PathError) as ctx:
            lp.data_dir({}, worktree=self.repo)
        self.assertIn("STYLE_LAB_DATA is not set", str(ctx.exception))

    def test_a_missing_folder_fails(self):
        with self.assertRaises(lp.PathError) as ctx:
            lp.data_dir({"STYLE_LAB_DATA": os.path.join(self.tmp.name, "nowhere")}, worktree=self.repo)
        self.assertIn("does not exist", str(ctx.exception))

    def test_a_folder_inside_the_worktree_fails(self):
        inside = os.path.join(self.repo, "data")
        os.makedirs(inside)
        with self.assertRaises(lp.PathError) as ctx:
            lp.data_dir({"STYLE_LAB_DATA": inside}, worktree=self.repo)
        self.assertIn("inside the git worktree", str(ctx.exception))

    def test_the_worktree_itself_fails(self):
        with self.assertRaises(lp.PathError):
            lp.data_dir({"STYLE_LAB_DATA": self.repo}, worktree=self.repo)

    def test_a_link_that_points_into_the_worktree_fails(self):
        inside = os.path.join(self.repo, "data")
        os.makedirs(inside)
        link = os.path.join(self.outside, "link")
        os.symlink(inside, link)
        with self.assertRaises(lp.PathError):
            lp.data_dir({"STYLE_LAB_DATA": link}, worktree=self.repo)

    def test_a_folder_outside_passes(self):
        self.assertEqual(lp.data_dir({"STYLE_LAB_DATA": self.outside}, worktree=self.repo),
                         os.path.realpath(self.outside))

    def test_a_sibling_whose_name_starts_with_the_worktree_name_passes(self):
        sibling = self.repo + "-scratch"
        os.makedirs(sibling)
        self.assertEqual(lp.data_dir({"STYLE_LAB_DATA": sibling}, worktree=self.repo),
                         os.path.realpath(sibling))

    def test_worktree_root_finds_the_git_entry_above_a_folder(self):
        deep = os.path.join(self.repo, "a", "b")
        os.makedirs(deep)
        self.assertEqual(lp.worktree_root(deep), os.path.realpath(self.repo))

    def test_worktree_root_returns_none_without_a_git_entry(self):
        self.assertIsNone(lp.worktree_root(self.outside))


class PathHelperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = self.tmp.name

    def test_pilot_folders_are_inside_the_data_directory(self):
        self.assertEqual(lp.manifests_dir(self.data, True), os.path.join(self.data, "pilot", "manifests"))
        self.assertEqual(lp.profiles_dir(self.data, True), os.path.join(self.data, "pilot", "profiles"))
        self.assertTrue(os.path.isdir(os.path.join(self.data, "pilot", "manifests")))

    def test_production_folders_are_in_the_plugin(self):
        self.assertEqual(lp.manifests_dir(self.data, False), os.path.join(lp.PLUGIN_ROOT, "manifests"))
        self.assertEqual(lp.profiles_dir(self.data, False), os.path.join(lp.PLUGIN_ROOT, "profiles"))

    def test_stage_dir(self):
        self.assertEqual(lp.stage_dir(self.data, True, "surface"), os.path.join(self.data, "pilot", "surface"))
        self.assertEqual(lp.stage_dir(self.data, False, "surface"), os.path.join(self.data, "surface"))

    def test_item_paths(self):
        self.assertEqual(lp.works_path("D", "ada"), os.path.join("D", "works", "ada.json"))
        self.assertEqual(lp.paper_path("D", "ada", "W1"), os.path.join("D", "papers", "ada", "W1.json"))
        self.assertEqual(lp.extraction_path("D", "ada", "W1"), os.path.join("D", "extract", "ada", "W1.json"))
        self.assertEqual(lp.extraction_path("D", "ada", "W1", "agreement"),
                         os.path.join("D", "extract", "ada", "W1.agreement.json"))
        self.assertEqual(lp.check_path("D", "ada", "W1"), os.path.join("D", "extract", "ada", "W1.check.json"))
        self.assertEqual(lp.check_path("D", "ada", "W1", "agreement"),
                         os.path.join("D", "extract", "ada", "W1.agreement.check.json"))


class WriteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "sub", "profile.json")

    def test_write_json_creates_the_folder_and_leaves_no_temporary_file(self):
        lp.write_json(self.path, {"n_papers": 3, "name": "Ada Quill é"})
        self.assertEqual(lp.read_json(self.path)["name"], "Ada Quill é")
        self.assertFalse(os.path.exists(self.path + ".tmp"))

    def test_the_guard_refuses_a_smaller_file(self):
        lp.write_json(self.path, {"n_papers": 15})
        with self.assertRaises(lp.PathError) as ctx:
            lp.write_json_guarded(self.path, {"n_papers": 9})
        self.assertIn("--force", str(ctx.exception))
        self.assertEqual(lp.read_json(self.path)["n_papers"], 15)

    def test_the_guard_allows_an_equal_or_larger_file(self):
        lp.write_json(self.path, {"n_papers": 15})
        lp.write_json_guarded(self.path, {"n_papers": 15, "v": 2})
        self.assertEqual(lp.read_json(self.path)["v"], 2)
        lp.write_json_guarded(self.path, {"n_papers": 16})
        self.assertEqual(lp.read_json(self.path)["n_papers"], 16)

    def test_force_replaces_a_larger_file(self):
        lp.write_json(self.path, {"n_papers": 15})
        lp.write_json_guarded(self.path, {"n_papers": 2}, force=True)
        self.assertEqual(lp.read_json(self.path)["n_papers"], 2)

    def test_the_guard_writes_a_new_file(self):
        lp.write_json_guarded(self.path, {"n_papers": 1})
        self.assertEqual(lp.read_json(self.path)["n_papers"], 1)


if __name__ == "__main__":
    unittest.main()
