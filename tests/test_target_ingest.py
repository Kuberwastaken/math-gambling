"""The target verifier is a sound, isolated parallel to the 114 pipeline.

Key invariants: it credits only independently-replayed matches, deduplicates by
namespaced id, and never reads or writes the 114 ledger. The 114 verifier and
the target verifier ignore each other's bank issues, so neither can corrupt the
other's data.
"""
import copy
import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import multi_target as mt
import target_ingest as ti
import ingest


def bank_for(k, rows):
    tasks = []
    for row in rows:
        t = mt.make_target_task(k, 'c00', row)
        tasks.append({"task": t, "digest": mt.run_target_task(t)["digest"]})
    return {"schema": "math-gambling-target-bank-v1",
            "contributor": {"name": "Ivan", "github": "kazenoko-git"}, "tasks": tasks}


class TargetIngestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def src(self, n):
        return {"id": f"issue:{n}", "kind": "issue", "number": n, "submitter": "kazenoko-git", "url": "u"}

    def test_accepts_verified_work_and_writes_only_target_namespace(self):
        rec = ti.process_target_bank(bank_for(627, (0, 128, 256)), self.src(1), self.data, ti.Budget())
        self.assertEqual(rec["status"], "accepted")
        self.assertEqual(len(rec["accepted"]), 3)
        self.assertTrue((self.data / "targets" / "627" / "tasks").exists())
        # The 114 ledger is never created by the target verifier.
        self.assertFalse((self.data / "receipts").exists())
        self.assertFalse((self.data / "coverage").exists())

    def test_deduplicates_and_credits_duplicates(self):
        bank = bank_for(627, (0, 128))
        ti.process_target_bank(bank, self.src(1), self.data, ti.Budget())
        second = ti.process_target_bank(bank, self.src(2), self.data, ti.Budget())
        self.assertEqual(len(second["accepted"]), 0)
        self.assertEqual(len(second["duplicate"]), 2)

    def test_rejects_tampered_digest_on_new_task(self):
        bank = bank_for(627, (0,))
        bank["tasks"][0]["digest"] = "0" * 64
        rec = ti.process_target_bank(bank, self.src(1), self.data, ti.Budget())
        self.assertEqual(rec["status"], "rejected")
        self.assertEqual(len(rec["accepted"]), 0)

    def test_rejects_wrong_digest_on_already_verified_task(self):
        bank = bank_for(627, (0,))
        ti.process_target_bank(bank, self.src(1), self.data, ti.Budget())
        forged = copy.deepcopy(bank)
        forged["tasks"][0]["digest"] = "1" * 64
        rec = ti.process_target_bank(forged, self.src(2), self.data, ti.Budget())
        self.assertEqual(len(rec["accepted"]), 0)
        self.assertEqual(len(rec["duplicate"]), 0)
        self.assertEqual(len(rec["rejected"]), 1)

    def test_aggregate_produces_summary_and_leaderboard(self):
        ti.process_target_bank(bank_for(627, (0, 128)), self.src(1), self.data, ti.Budget())
        summary = ti.aggregate_targets(self.data)
        self.assertEqual(summary["targets"]["627"]["verified_tasks"], 2)
        self.assertEqual(summary["leaderboard"]["kazenoko-git"], 2)

    def test_title_search_does_not_depend_on_labels_and_persists_cursor(self):
        issue = dict(number=77, title="[bank-mt] Target bank x", body=json.dumps(bank_for(627, (0,))),
                     user={"login": "p"}, labels=[])
        calls = []
        def api(url, *_args, **_kwargs):
            calls.append(url)
            return {"items": [issue]} if "search/issues" in url else issue
        with mock.patch.object(ti, "api_request", side_effect=api):
            entries, poll = ti.collect_target_issues("example/test", "token", self.data, float("inf"))
        self.assertEqual(entries[0][1]["number"], 77)
        self.assertIn("in%3Atitle", calls[0])
        self.assertEqual(poll["pending"], [{"number": 77}])

    def test_native_target_replay_cross_checks_deterministically(self):
        task = mt.make_target_task(627, "c00", 0)
        expected = mt.run_target_task(task)
        class Kernel:
            last_cpu_ms = 1.5
            def run(self, supplied): return expected
            def close(self): pass
        replay = object.__new__(ti.NativeTargetReplay)
        replay.kernel, replay.one_in, replay.python_replay, replay.cross_checked = Kernel(), 1, lambda t: (expected, 2), 0
        result, cpu = replay(task)
        self.assertEqual(result, expected); self.assertEqual(cpu, 1.5); self.assertEqual(replay.cross_checked, 1)

    def test_mutual_isolation_of_the_two_verifiers(self):
        # The 114 verifier ignores [bank-mt]; the target verifier ignores [bank].
        mt_issue = dict(number=5, title="[bank-mt] Target bank abcd", body="{}",
                        user={"login": "p"}, updated_at="2026-09-13T00:00:00Z")
        self.assertIsNone(ingest.parse_issue(mt_issue, "o/r"))
        c114_issue = dict(number=6, title="[bank] Bank-in abcd", body="{}",
                          user={"login": "p"}, updated_at="2026-09-13T00:00:00Z")
        self.assertIsNone(ti.parse_target_issue(c114_issue, "o/r"))
        # And a real target bank issue parses for the target verifier.
        self.assertIsNotNone(ti.parse_target_issue(dict(number=7, title="[bank-mt] x",
            body=json.dumps(bank_for(627, (0,))), user={"login": "p"}), "o/r"))


if __name__ == '__main__':
    unittest.main()
