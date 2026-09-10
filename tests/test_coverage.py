"""Exact shared coverage, immutable snapshots, and fail-closed publication."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import coverage_index as coverage
import ingest
import aggregate
from search_core import make_task, run_task, task_id


def verified(sequence, context="c00", row=0):
    task = make_task(context, row)
    return dict(schema="math-gambling-verified-task-v1", sequence=sequence,
                result=dict(task=task, id=task_id(task)))


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.data = Path(self.temporary.name)
        self.directory = self.data / "coverage"

    def tearDown(self):
        self.temporary.cleanup()

    def test_empty_snapshot_has_all_81_exact_shards(self):
        manifest = coverage.publish_coverage(self.data, [])
        self.assertEqual(manifest["revision"], 0)
        self.assertEqual(manifest["verified_task_count"], 0)
        self.assertEqual(set(manifest["shards"]), set(coverage.CONTEXT_IDS))
        checked, completed = coverage.read_coverage(self.directory)
        self.assertEqual(checked, manifest)
        self.assertTrue(all(not ids for ids in completed.values()))
        for context, shard in manifest["shards"].items():
            raw = (self.directory / shard["file"]).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), shard["sha256"])
            self.assertTrue(raw.endswith(b"\n"))
            self.assertEqual(shard["file"], f"{context}-{shard['sha256']}.json")

    def test_exact_membership_sorted_ids_and_stable_repeat_publication(self):
        tasks = [verified(1, "c00", 256), verified(2, "c80", 0), verified(3, "c00", 128)]
        with mock.patch.object(coverage, "now", return_value="2026-09-10T00:00:00Z"):
            first = coverage.publish_coverage(self.data, tasks)
        original = (self.directory / "index.json").read_bytes()
        with mock.patch.object(coverage, "now", return_value="2026-09-11T00:00:00Z"):
            repeated = coverage.publish_coverage(self.data, list(reversed(tasks)))
        self.assertEqual(first, repeated)
        self.assertEqual((self.directory / "index.json").read_bytes(), original)
        manifest, completed = coverage.read_coverage(self.directory)
        self.assertEqual(manifest["revision"], 3)
        self.assertEqual(completed["c00"], {task_id(make_task("c00", 128)), task_id(make_task("c00", 256))})
        self.assertNotIn(task_id(make_task("c00", 0)), completed["c00"])

    def test_updates_keep_old_immutable_files_for_cached_manifest(self):
        first = coverage.publish_coverage(self.data, [verified(1)])
        old_bytes = {c: (self.directory / s["file"]).read_bytes() for c, s in first["shards"].items()}
        second = coverage.publish_coverage(self.data, [verified(1), verified(2, row=128)])
        self.assertEqual(second["revision"], 2)
        self.assertNotEqual(first["shards"]["c00"], second["shards"]["c00"])
        self.assertEqual(first["shards"]["c01"], second["shards"]["c01"])
        for context, entry in first["shards"].items():
            self.assertEqual((self.directory / entry["file"]).read_bytes(), old_bytes[context])

    def test_removals_replacements_duplicate_ids_and_invalid_scope_are_rejected(self):
        coverage.publish_coverage(self.data, [verified(1)])
        original = (self.directory / "index.json").read_bytes()
        bad_descriptor = verified(1)
        bad_descriptor["result"]["task"]["row"] = "1"
        bad_id = verified(1)
        bad_id["result"]["id"] = task_id(make_task("c01", 0))
        for tasks in ([], [verified(1, row=128)], [verified(1), verified(2)], [bad_descriptor], [bad_id], [verified(2)]):
            with self.subTest(tasks=tasks):
                with self.assertRaises(ValueError):
                    coverage.publish_coverage(self.data, tasks)
                self.assertEqual((self.directory / "index.json").read_bytes(), original)

    def test_corrupt_or_oversized_snapshots_do_not_advance_manifest(self):
        first = coverage.publish_coverage(self.data, [verified(1)])
        original = (self.directory / "index.json").read_bytes()
        shard = self.directory / first["shards"]["c00"]["file"]
        shard.write_bytes(shard.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "checksum"):
            coverage.publish_coverage(self.data, [verified(1), verified(2, row=128)])
        self.assertEqual((self.directory / "index.json").read_bytes(), original)
        shard.write_bytes(shard.read_bytes()[:-1])
        with mock.patch.object(coverage, "MAX_SHARD_TASKS", 1):
            with self.assertRaisesRegex(ValueError, "capacity"):
                coverage.publish_coverage(self.data, [verified(1), verified(2, row=128)])
        self.assertEqual((self.directory / "index.json").read_bytes(), original)
        with tempfile.TemporaryDirectory() as fresh, mock.patch.object(coverage, "MAX_SHARD_BYTES", 10):
            with self.assertRaisesRegex(ValueError, "capacity"):
                coverage.publish_coverage(Path(fresh), [])
            self.assertFalse((Path(fresh) / "coverage/index.json").exists())

    def test_failed_manifest_commit_keeps_previous_snapshot_usable(self):
        first = coverage.publish_coverage(self.data, [verified(1)])
        write = coverage.atomic_json
        def fail_manifest(path, value):
            if Path(path).name == ".index.pending.json":
                raise OSError("simulated interrupted publication")
            write(path, value)
        with mock.patch.object(coverage, "atomic_json", side_effect=fail_manifest):
            with self.assertRaises(OSError):
                coverage.publish_coverage(self.data, [verified(1), verified(2, row=128)])
        recovered, completed = coverage.read_coverage(self.directory)
        self.assertEqual(recovered, first)
        self.assertEqual(len(completed["c00"]), 1)
        self.assertEqual(coverage.publish_coverage(self.data, [verified(1), verified(2, row=128)])["revision"], 2)

    def test_aggregation_exports_only_independently_accepted_ids(self):
        result = run_task(make_task("c00", 0))
        receipt = dict(schema="math-gambling-bank-v1", contributor=dict(name="Example", github="example"),
                       tasks=[dict(task=result["task"], digest=result["digest"])])
        origin = dict(id="fixture-coverage", kind="fixture")
        ingest.process_receipt(receipt, origin, self.data, ingest.Budget(), replay=lambda task: (run_task(task), 1.0))
        summary = aggregate.aggregate(self.data)
        self.assertEqual(summary["coverage"]["revision"], summary["totals"]["verified_unique_tasks"])
        _, completed = coverage.read_coverage(self.directory)
        self.assertEqual(completed["c00"], {result["id"]})


if __name__ == "__main__":
    unittest.main()
