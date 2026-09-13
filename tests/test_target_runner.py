"""End-to-end: the standalone target runner produces banks that the target
verifier accepts — the full cross-target loop, and it never touches 114 state."""
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import target_runner as tr
import target_ingest as ti


class TargetRunnerTests(unittest.TestCase):
    def _args(self, out, **kw):
        base = dict(output=out, minutes=5.0, bank_every=3, name="Anant", github="GithubAnant",
                    url="", submit=False, repo="o/r", seed=42, max_tasks=6,
                    targets=list(tr.tb.OPEN_TARGETS))
        base.update(kw)
        return types.SimpleNamespace(**base)

    def test_runner_output_verifies_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "run"
            completed = tr.run(self._args(out))
            self.assertGreater(completed, 0)
            banks = sorted((out / "banks").glob("bank-mt-*.json"))
            self.assertTrue(banks, "runner should write at least one [bank-mt] bank")

            verify = Path(d) / "verify"
            accepted = 0
            for i, bp in enumerate(banks):
                bank = json.loads(bp.read_text())
                self.assertEqual(bank["schema"], "math-gambling-target-bank-v1")
                rec = ti.process_target_bank(
                    bank, {"id": f"issue:{i}", "kind": "issue", "number": i,
                           "submitter": "GithubAnant", "url": "u"}, verify, ti.Budget())
                self.assertEqual(rec["rejected"], [])          # everything the runner banked verifies
                accepted += len(rec["accepted"])
            self.assertGreater(accepted, 0)
            summary = ti.aggregate_targets(verify)
            self.assertGreater(sum(t["verified_tasks"] for t in summary["targets"].values()), 0)
            self.assertIn("GithubAnant", summary["leaderboard"])

    def test_runner_never_writes_114_state(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "run"
            tr.run(self._args(out, max_tasks=3, bank_every=2))
            self.assertFalse((out / "receipts").exists())
            self.assertFalse((out / "coverage").exists())
            self.assertTrue((out / "banks").exists())


if __name__ == '__main__':
    unittest.main()
