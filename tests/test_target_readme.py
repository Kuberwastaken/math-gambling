"""The README TARGETS block renders from summary data and touches nothing else."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import target_readme as tr

SUMMARY = {
    "updated_at": "2026-09-14T00:00:00Z",
    "targets": {
        "627": {"verified_tasks": 100, "curves": 5000, "exact_tests": 3, "empty_tasks": 70},
        "390": {"verified_tasks": 50, "curves": 1000, "exact_tests": 1, "empty_tasks": 40},
    },
    "leaderboard": {"kazenoko-git": 100, "GithubAnant": 50},
    "discoveries": [],
}


class TargetReadmeTests(unittest.TestCase):
    def _readme(self, d):
        p = Path(d) / "README.md"
        p.write_text("Intro.\n\n" + tr.START + "\nold\n" + tr.END + "\n\nAfter.\n", encoding="utf-8")
        return p

    def test_empty_summary_renders_placeholder(self):
        self.assertEqual(tr.render(None), tr.PLACEHOLDER)
        self.assertEqual(tr.render({"targets": {}}), tr.PLACEHOLDER)

    def test_populated_summary_has_table_and_leaderboard(self):
        out = tr.render(SUMMARY)
        self.assertIn("| Target |", out)
        self.assertIn("| 627 |", out)
        self.assertIn("70%", out)                    # empty fraction
        self.assertIn("@kazenoko-git (100)", out)

    def test_update_replaces_only_the_block_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._readme(d)
            tr.update(p, SUMMARY)
            text = p.read_text()
            self.assertIn("Intro.", text)
            self.assertIn("After.", text)
            self.assertIn("| 627 |", text)
            self.assertEqual(text.count(tr.START), 1)
            self.assertEqual(text.count(tr.END), 1)
            once = p.read_text()
            tr.update(p, SUMMARY)
            self.assertEqual(p.read_text(), once)     # idempotent
            # Reverting to no data restores the placeholder cleanly.
            tr.update(p, None)
            self.assertIn(tr.PLACEHOLDER, p.read_text())
            self.assertNotIn("| 627 |", p.read_text())


if __name__ == '__main__':
    unittest.main()
