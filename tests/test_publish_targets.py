"""publish_targets commits only the target namespace + README, leaving main's
working tree and index untouched."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import publish_targets as pt


class PublishTargetsTests(unittest.TestCase):
    def test_publishes_only_target_paths_and_leaves_main_index_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)

            def g(*a):
                subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)

            g("init", "-q", "-b", "main")
            g("config", "user.email", "t@t")
            g("config", "user.name", "t")
            g("config", "core.hooksPath", str(repo / ".nohooks"))  # never fire dev hooks
            (repo / "data/targets/627/tasks").mkdir(parents=True)
            (repo / "data/targets/627/tasks/a.json").write_text("{}")
            (repo / "README.md").write_text("readme")
            (repo / "tools").mkdir()
            (repo / "tools/foo.py").write_text("code")
            g("add", "-A")
            g("commit", "-qm", "init")

            index_before = (repo / ".git/index").read_bytes()
            res = pt.publish(repo)
            self.assertTrue(res["changed"])

            names = subprocess.run(["git", "-C", str(repo), "ls-tree", "-r", "--name-only", res["commit"]],
                                   capture_output=True, text=True).stdout.split()
            self.assertIn("README.md", names)
            self.assertIn("data/targets/627/tasks/a.json", names)
            self.assertNotIn("tools/foo.py", names)   # only the target namespace is published
            self.assertEqual((repo / ".git/index").read_bytes(), index_before)  # main index untouched


if __name__ == '__main__':
    unittest.main()
