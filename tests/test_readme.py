"""Deterministic live README updates and safe untrusted attribution rendering."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from readme_snapshot import CONTEXTS, START, END, render_snapshot, update_readme


def fixture(total=128):
    allocation = {context: 1 / 81 for context in CONTEXTS}
    epoch = total // 64
    policy = dict(schema="math-gambling-strategy-v1", epoch=epoch, epoch_size=64,
                  through_verified_tasks=epoch * 64, exploration_fraction=0.4,
                  contexts=[dict(id=c, weight=w) for c, w in allocation.items()])
    report = dict(schema="math-gambling-cluster-v1", updated_at="2026-09-10T12:00:00Z",
                  totals=dict(verified_unique_tasks=total, verified_hits=0,
                              counters=dict(generators="238592", curves="20891",
                                            quotient_points="33121245", exact_tests="56")),
                  contributors=[], coverage=dict(verified_task_count=total),
                  calibration_history=[dict(epoch=n, through_verified_tasks=n * 64,
                                            weights=allocation.copy()) for n in range(1, epoch + 1)])
    return report, policy


def participant(name="Example", url=""):
    return dict(name=name, github="real-user", submitter="real-user", github_verified=True,
                verified_computations="1024", verified_tasks=2, url=url)


class ReadmeTests(unittest.TestCase):
    def test_snapshot_uses_exact_units_current_policy_and_recorded_history(self):
        report, policy = fixture(130)
        report["totals"]["counters"]["generators"] = "123456789012345678901234567890"
        rendered = render_snapshot(report, policy)
        self.assertIn("123,456,789,012,345,678,901,234,567,890", rendered)
        self.assertIn("33,121,245", rendered)
        self.assertIn("**Epoch 2**, frozen from **128 verified tasks**", rendered)
        self.assertIn("**62 more accepted unique tasks**", rendered)
        self.assertIn("Epoch 1: 64 tasks", rendered)
        self.assertIn("40% uniform exploration across 81 contexts", rendered)
        self.assertIn("60% weighted by measured replay efficiency", rendered)
        self.assertIn("Independently verified identities for 114 | 0", rendered)
        self.assertIn("No participants have independently verified work yet.", rendered)

    def test_policy_change_regenerates_allocation_and_history_without_inventing_hits(self):
        report, policy = fixture()
        before = render_snapshot(report, policy)
        revised = {context: (0.2 if context == "c50" else 0.8 / 80) for context in CONTEXTS}
        report["calibration_history"][-1]["weights"] = revised
        policy["contexts"] = [dict(id=context, weight=weight) for context, weight in revised.items()]
        after = render_snapshot(report, policy)
        self.assertNotEqual(after, before)
        self.assertIn('C0["c50: 20.00%"]', after)
        self.assertIn("| 2 | 128 | c50 | 20.0000% |", after)
        self.assertIn("Independently verified identities for 114 | 0", after)
        self.assertEqual(render_snapshot(report, policy), after)

    def test_aliases_cannot_inject_markdown_html_markers_or_mermaid(self):
        report, policy = fixture()
        alias = 'Evil | [link](javascript:alert(1))\n<script>x</script> ```mermaid\nA-->B ' + END
        report["contributors"] = [participant(alias, 'https://example.org/a>(x)?q="hello"')]
        rendered = render_snapshot(report, policy)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn(END, rendered)
        self.assertIn("Evil \\| \\[link\\]", rendered)
        self.assertIn("https://example.org/a%3E%28x%29?q=%22hello%22", rendered)
        self.assertIn("[@real-user](https://github.com/real-user)", rendered)
        mermaid = rendered.split("```mermaid\n", 1)[1].split("```", 1)[0]
        self.assertNotIn("Evil", mermaid)
        self.assertNotIn("A-->B", mermaid)
        for url in ("javascript:alert(1)", "data:text/html,hello", "//evil.example",
                    "https://user:password@example.org", "https://example.org/ bad"):
            report["contributors"] = [participant("Plain alias", url)]
            output = render_snapshot(report, policy)
            self.assertIn("| 1 | Plain alias |", output)
            self.assertNotIn(url, output)

    def test_only_authenticated_accounts_receive_leaderboard_rows_and_alias_overrides(self):
        report, policy = fixture()
        valid = participant("Original name", "https://example.org/me")
        fake = participant("Forged account")
        fake["github_verified"] = False
        mismatch = participant("Mismatched account")
        mismatch["submitter"] = "someone-else"
        report["contributors"] = [valid, fake, mismatch]
        output = render_snapshot(report, policy, {"display_aliases": {"real-user": "Shown alias"}})
        self.assertIn("[Shown alias](<https://example.org/me>)", output)
        self.assertNotIn("Original name", output)
        self.assertNotIn("Forged account", output)
        self.assertNotIn("Mismatched account", output)

    def test_updates_are_idempotent_and_preserve_manual_narrative_exactly(self):
        report, policy = fixture()
        snapshot = render_snapshot(report, policy)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "README.md"
            head, tail = "# Human introduction\n\n", "\n\n## Human research notes\nKeep this wording.\n"
            path.write_text(head + START + "\nold generated material\n" + END + tail)
            self.assertTrue(update_readme(path, snapshot))
            first = path.read_bytes()
            self.assertFalse(update_readme(path, snapshot))
            self.assertEqual(path.read_bytes(), first)
            text = first.decode()
            self.assertTrue(text.startswith(head + START))
            self.assertTrue(text.endswith(END + tail))
            self.assertEqual(text.count(START), 1)
            self.assertEqual(text.count(END), 1)
            for invalid in ("No markers", START + START + END, END + START):
                path.write_text(invalid)
                with self.assertRaises(ValueError):
                    update_readme(path, snapshot)
                self.assertEqual(path.read_text(), invalid)

    def test_invalid_state_cannot_publish_an_unsupported_allocation(self):
        for mutate in (
            lambda r, p: p.update(epoch=True),
            lambda r, p: p.update(exploration_fraction=0.1),
            lambda r, p: p["contexts"][0].update(id='c00"] --> Inject'),
            lambda r, p: p["contexts"][0].update(weight=float("nan")),
            lambda r, p: r["totals"]["counters"].update(generators="-1"),
            lambda r, p: r.update(updated_at='</text><script>x</script>'),
        ):
            report, policy = fixture()
            mutate(report, policy)
            with self.assertRaises((ValueError, TypeError)):
                render_snapshot(report, policy)


if __name__ == "__main__":
    unittest.main()
