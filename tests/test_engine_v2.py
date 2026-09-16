"""Engine v2 (1024-row tasks) must equal the sum of its eight aligned v1 tasks."""
import random
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import search_core as core


class EngineV2Tests(unittest.TestCase):
    def sample(self, n=2, seed=1142):
        rng = random.Random(seed)
        out = []
        for c in core.CONTEXTS:
            for _ in range(n):
                row = rng.randrange(int(c["rowTasksV2"])) * c["rowStrideV2"]
                out.append(core.make_task(c["id"], row, rng.randrange(c["blocks"]), 2))
        return out

    def test_v2_equals_concatenated_v1_subtasks(self):
        for task in self.sample():
            subs = core.subtasks(task)
            self.assertTrue(1 <= len(subs) <= 8)
            self.assertTrue(all(s["version"] == 1 for s in subs))
            parts = [core.run_task(s) for s in subs]
            whole = core.run_task(task)
            self.assertEqual(whole["id"], f"{core.ENGINE_V2}:{task['context']}:{task['row']}:{task['block']}")
            for key in whole["counters"]:
                self.assertEqual(whole["counters"][key], sum(p["counters"][key] for p in parts), key)
            self.assertEqual(whole["hits"], [h for p in parts for h in p["hits"]])
            self.assertEqual(core.prove_empty_task(task), all(core.prove_empty_task(s) for s in subs))

    def test_v1_ids_and_receipts_are_unchanged(self):
        task = core.make_task("c00", 128)
        self.assertEqual(task, {"version": 1, "engine": "mg114-offset-v1", "context": "c00", "row": "128", "block": 0})
        self.assertEqual(core.task_id(task), "mg114-offset-v1:c00:128:0")
        self.assertEqual(core.task_rows(task), 128)

    def test_overlap_helpers(self):
        v1 = core.make_task("c05", 128 * 9, 1)
        container = core.container_task(v1)
        self.assertEqual((container["version"], container["row"], container["block"]), (2, "1024", 1))
        self.assertEqual(core.overlapping_ids(v1), [core.task_id(container)])
        ids = core.overlapping_ids(container)
        self.assertEqual(len(ids), 8)
        self.assertIn(core.task_id(v1), ids)
        self.assertEqual(core.container_task(container), container)
        self.assertEqual(core.subtasks(v1), [v1])

    def test_v2_rejects_misaligned_or_wrong_engine(self):
        for bad in ({"version": 2, "engine": core.ENGINE, "context": "c00", "row": "0", "block": 0},
                    {"version": 2, "engine": core.ENGINE_V2, "context": "c00", "row": "128", "block": 0},
                    {"version": 1, "engine": core.ENGINE_V2, "context": "c00", "row": "0", "block": 0},
                    {"version": 3, "engine": core.ENGINE_V2, "context": "c00", "row": "0", "block": 0}):
            with self.assertRaises(ValueError):
                core.validate_task(bad)

    def test_last_v2_task_is_truncated_at_context_end(self):
        c = core.CONTEXTS[0]
        last = (int(c["totalRows"]) - 1) // 1024 * 1024
        task = core.make_task(c["id"], last, 0, 2)
        self.assertLessEqual(len(core.subtasks(task)), 8)
        self.assertEqual(core.run_task(task)["counters"]["generators"],
                         sum(core.run_task(s)["counters"]["generators"] for s in core.subtasks(task)))


if __name__ == "__main__":
    unittest.main()
