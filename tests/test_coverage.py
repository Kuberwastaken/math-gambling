"""Exact shared coverage, immutable snapshots, and fail-closed publication."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import coverage_client
import coverage_index as coverage
import ingest
import aggregate
from search_core import make_task, run_task, task_id


def verified(sequence, context="c00", row=0, version=1):
    task = make_task(context, row, 0, version)
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
        with mock.patch.object(coverage, "MAX_INDEX_BYTES", 10):
            with self.assertRaisesRegex(ValueError, "capacity|size"):
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

    def test_chunk_extension_reuses_sealed_bytes_and_clients_check_exact_membership(self):
        from coverage_format import bucket_for
        from coverage_client import CoverageIndex
        import json
        chosen = []
        for row in range(0, 20000000, 128):
            if bucket_for(task_id(make_task('c00', row))) == '00':
                chosen.append(row)
                if len(chosen) == 257: break
        self.assertEqual(len(chosen), 257)
        tasks = [verified(i+1, row=row) for i,row in enumerate(chosen)]
        first = coverage.publish_coverage(self.data, tasks[:256])
        node = json.loads((self.directory/first['shards']['c00']['file']).read_bytes())
        sealed = node['buckets']['00'][0]
        original = (self.directory/sealed['file']).read_bytes()
        with mock.patch.object(coverage, 'MAX_SHARD_TASKS', 1):
            second = coverage.publish_coverage(self.data, tasks)
        node2 = json.loads((self.directory/second['shards']['c00']['file']).read_bytes())
        self.assertEqual(node2['buckets']['00'][0], sealed)
        self.assertEqual((self.directory/sealed['file']).read_bytes(), original)
        self.assertEqual(len(node2['buckets']['00']), 2)
        client = CoverageIndex(self.directory, self.data/'cache', offline=True)
        client.refresh()
        self.assertTrue(client.contains(make_task('c00', chosen[0])))
        self.assertTrue(client.contains(make_task('c00', chosen[-1])))
        self.assertFalse(client.contains(make_task('c00', 20000000)))
        self.assertLessEqual(len(client.loaded), 64)

    def test_retirement_grace_and_current_snapshot_survive_cleanup(self):
        from datetime import datetime, timezone, timedelta
        first = coverage.publish_coverage(self.data, [verified(1)])
        old = self.directory/first['shards']['c00']['file']
        second = coverage.publish_coverage(self.data, [verified(1), verified(2,row=128)])
        stamp = datetime(2026,9,10,tzinfo=timezone.utc)
        self.assertEqual(coverage.prune_retired(self.data, observed=stamp), 0)
        self.assertTrue(old.exists())
        coverage.prune_retired(self.data, observed=stamp+timedelta(hours=23))
        self.assertTrue(old.exists())
        self.assertGreater(coverage.prune_retired(self.data, observed=stamp+timedelta(hours=25)), 0)
        self.assertFalse(old.exists())
        self.assertEqual(coverage.read_coverage(self.directory)[0], second)

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


class CoverageEngineV2Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.data = Path(self.temporary.name)
        self.directory = self.data / "coverage"
        self.v2 = self.directory / "v2"

    def tearDown(self):
        self.temporary.cleanup()

    def test_v1_index_is_byte_identical_when_v2_records_are_added(self):
        only_v1 = [verified(1, row=0), verified(2, row=128)]
        first = coverage.publish_coverage(self.data, only_v1)
        original = (self.directory / "index.json").read_bytes()
        mixed = only_v1 + [verified(3, "c01", 0, 2), verified(4, "c01", 1024, 2)]
        published = coverage.publish_versions(self.data, mixed)
        self.assertEqual(published[1], first)
        self.assertEqual((self.directory / "index.json").read_bytes(), original)
        self.assertEqual(published[2]["engine"], "mg114-offset-v2")
        self.assertEqual(published[2]["revision"], 2)
        self.assertEqual(published[2]["verified_task_count"], 2)
        self.assertEqual(set(published[2]["shards"]), set(coverage.CONTEXT_IDS))
        manifest, completed = coverage.read_coverage(self.v2, 2)
        self.assertEqual(manifest, published[2])
        self.assertEqual(completed["c01"], {task_id(make_task("c01", 0, 0, 2)), task_id(make_task("c01", 1024, 0, 2))})
        self.assertEqual(completed["c00"], set())
        # The v1 reader must refuse the v2 index, and the reverse.
        with self.assertRaises(ValueError):
            coverage.read_coverage(self.v2, 1)
        with self.assertRaises(ValueError):
            coverage.read_coverage(self.directory, 2)

    def test_v2_membership_chunks_prune_and_never_regress(self):
        from datetime import datetime, timezone, timedelta
        tasks = [verified(1, "c00", 0, 2)]
        coverage.publish_versions(self.data, tasks)
        old = self.v2 / coverage.read_coverage(self.v2, 2)[0]["shards"]["c00"]["file"]
        tasks.append(verified(2, "c00", 1024, 2))
        second = coverage.publish_versions(self.data, tasks)[2]
        self.assertEqual(second["revision"], 2)
        self.assertTrue(old.exists())
        stamp = datetime(2026, 9, 17, tzinfo=timezone.utc)
        self.assertEqual(coverage.prune_retired(self.data, observed=stamp), 0)
        self.assertGreater(coverage.prune_retired(self.data, observed=stamp + timedelta(hours=25)), 0)
        self.assertFalse(old.exists())
        self.assertEqual(coverage.read_coverage(self.v2, 2)[0], second)
        self.assertEqual(coverage.read_coverage(self.directory, 1)[0]["revision"], 0)
        with self.assertRaises(ValueError):
            coverage.publish_versions(self.data, [verified(1, "c00", 1024, 2)])

    def test_aggregate_reports_both_indexes(self):
        from search_core import run_task
        result = run_task(make_task("c02", 0, 0, 2))
        receipt = dict(schema="math-gambling-bank-v1", contributor=dict(name="Example", github="example"),
                       tasks=[dict(task=result["task"], digest=result["digest"])])
        ingest.process_receipt(receipt, dict(id="fixture-v2", kind="fixture"), self.data,
                               ingest.Budget(), replay=lambda task: (run_task(task), 1.0))
        report = aggregate.aggregate(self.data)
        self.assertEqual(report["coverage"]["revision"], 0)
        self.assertEqual(report["coverage"]["engine_v2"]["revision"], 1)
        self.assertEqual(report["coverage"]["engine_v2"]["index"], "coverage/v2/index.json")
        self.assertEqual(report["coverage"]["verified_task_count"], 1)
        self.assertEqual(report["totals"]["verified_computations"], str(result["counters"]["generators"]))
        _, completed = coverage.read_coverage(self.v2, 2)
        self.assertEqual(completed["c02"], {result["id"]})


class CoverageClientVersionTests(unittest.TestCase):
    """The runner's client must read both published indexes and apply the exact
    overlap rule: one engine version's record covers the other's positions."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.data = Path(self.temporary.name)
        self.directory = self.data / "coverage"

    def tearDown(self):
        self.temporary.cleanup()

    def client(self, offline=True):
        return coverage_client.CoverageIndex(self.directory, self.data / "cache", offline=offline)

    def test_overlapping_ids_are_covered_across_both_published_indexes(self):
        v1_only = make_task("c00", 2048)               # one eighth of a v2 task
        v2_only = make_task("c01", 1024, 0, 2)
        coverage.publish_versions(self.data, [verified(1, "c00", 2048), verified(2, "c01", 1024, 2)])
        client = self.client()
        snapshot = client.refresh()
        self.assertEqual(snapshot["revision"], 1)
        self.assertEqual(snapshot["engine_v2"]["revision"], 1)
        self.assertTrue(client.contains(v1_only))
        self.assertTrue(client.contains(v2_only))
        # A v2 task whose aligned v1 sub-task is already published is covered,
        # and each v1 sub-task of a published v2 task is covered too.
        self.assertTrue(client.contains(make_task("c00", 2048, 0, 2)))
        self.assertTrue(client.contains(make_task("c01", 1024 + 128 * 3)))
        self.assertFalse(client.contains(make_task("c00", 1024, 0, 2)))
        self.assertFalse(client.contains(make_task("c01", 0)))
        self.assertEqual(client.known_skips, 4)

    def test_absent_v2_index_is_empty_and_never_pauses_v1_dispatch(self):
        # An older snapshot, or any release published before the v2 index exists.
        coverage.publish_coverage(self.data, [verified(1, "c00", 0)])
        shutil.rmtree(self.directory / "v2", ignore_errors=True)
        client = self.client()
        snapshot = client.refresh()
        self.assertIsNone(snapshot["engine_v2"])
        self.assertIsNone(client.other.index)
        self.assertTrue(client.contains(make_task("c00", 0)))
        self.assertTrue(client.contains(make_task("c00", 0, 0, 2)))
        self.assertFalse(client.contains(make_task("c05", 0, 0, 2)))
        self.assertFalse(client.contains(make_task("c00", 1024, 0, 2)))

    def test_unreadable_v2_index_is_discarded_without_blocking_the_campaign(self):
        coverage.publish_versions(self.data, [verified(1, "c00", 0), verified(2, "c05", 0, 2)])
        (self.directory / "v2" / "index.json").write_text("{}")
        client = self.client()
        client.refresh()
        self.assertIsNone(client.other.index)
        self.assertIn("Invalid published coverage index", client.other.unavailable)
        self.assertTrue(client.contains(make_task("c00", 0)))
        self.assertFalse(client.contains(make_task("c05", 0, 0, 2)))

    def test_v1_shard_and_index_validation_is_unchanged_for_engine_v1(self):
        coverage.publish_coverage(self.data, [verified(1, "c00", 0)])
        raw = (self.directory / "index.json").read_bytes()
        index = coverage_client.validate_index(raw)
        self.assertEqual(index["engine"], "mg114-offset-v1")
        with self.assertRaises(coverage_client.CoverageError):
            coverage_client.validate_index(raw, 2)


if __name__ == "__main__":
    unittest.main()
