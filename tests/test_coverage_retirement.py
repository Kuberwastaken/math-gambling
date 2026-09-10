"""Suspended clients must resume after old tail files leave publication."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from coverage_client import CoverageIndex, CoverageError
from coverage_format import bucket_for
from coverage_index import publish_coverage, prune_retired
from ingest import atomic_json
from search_core import make_task, task_id


def candidates():
    first = make_task('c00', 0)
    bucket = bucket_for(task_id(first))
    same, other = [first], None
    for row in range(128, 128 * 10000, 128):
        task = make_task('c00', row)
        if bucket_for(task_id(task)) == bucket:
            same.append(task)
        elif other is None:
            other = task
        if len(same) == 3 and other is not None:
            return same, other, bucket
    raise AssertionError('bounded routing fixture did not find three IDs')


SAME, OTHER, BUCKET = candidates()


def ledger(tasks):
    return [dict(schema='math-gambling-verified-task-v1', sequence=i + 1,
                 result=dict(task=task, id=task_id(task))) for i, task in enumerate(tasks)]


class RetirementTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.server = self.root / 'server'
        self.coverage = self.server / 'coverage'
        self.requests = []
        self.first = publish_coverage(self.server, ledger(SAME[:1]))
        node = json.loads((self.coverage / self.first['shards']['c00']['file']).read_bytes())
        self.old_tail = node['buckets'][BUCKET][0]['file']
        def fetch(url, cap):
            name = url.rsplit('/', 1)[-1]
            self.requests.append(name)
            try:
                with (self.coverage / name).open('rb') as handle:
                    return handle.read(cap + 1)
            except OSError as exc:
                raise CoverageError(str(exc)) from None
        self.client = CoverageIndex(self.root / 'empty-bundle', self.root / 'cache', fetch=fetch)
        self.client.refresh()

    def tearDown(self):
        self.temporary.cleanup()

    def test_current_membership_survives_25_hour_retirement_of_unseen_tail(self):
        # Observe the old context descriptor without ever loading its old tail.
        self.assertFalse(self.client.contains(OTHER))
        self.assertNotIn(self.old_tail, self.requests)
        publish_coverage(self.server, ledger(SAME[:2]))
        stamp = datetime(2026, 9, 10, tzinfo=timezone.utc)
        prune_retired(self.server, observed=stamp)
        prune_retired(self.server, observed=stamp + timedelta(hours=25))
        self.assertFalse((self.coverage / self.old_tail).exists())
        self.client.refresh()
        self.assertTrue(self.client.contains(SAME[0]))
        self.assertTrue(self.client.contains(SAME[1]))
        self.assertFalse(self.client.contains(SAME[2]))
        self.assertNotIn(self.old_tail, self.requests, 'freshness must not depend on downloading a retired tail')

    def assert_retained_tail_tamper_rejected(self, *, evict_memory):
        self.assertTrue(self.client.contains(SAME[0]))
        if evict_memory:
            self.client.loaded.clear()
        second = publish_coverage(self.server, ledger(SAME[:2]))
        entry = second['shards']['c00']
        node = json.loads((self.coverage / entry['file']).read_bytes())
        old = node['buckets'][BUCKET][0]
        chunk = json.loads((self.coverage / old['file']).read_bytes())
        # Correct hashes/counts cannot authorize erasing retained observations.
        chunk['tasks'] = sorted(map(task_id, SAME[1:]))
        def replace(prefix, value):
            stage = self.coverage / 'fixture.json'
            atomic_json(stage, value)
            sha = hashlib.sha256(stage.read_bytes()).hexdigest()
            file = f'{prefix}-{sha}.json'
            stage.replace(self.coverage / file)
            return dict(file=file, sha256=sha, count=2)
        node['buckets'][BUCKET] = [replace(f'c00-b{BUCKET}', chunk)]
        second['shards']['c00'] = replace('c00', node)
        atomic_json(self.coverage / 'index.json', second)
        self.client.refresh()
        with self.assertRaisesRegex(CoverageError, 'removed completed work'):
            self.client.contains(SAME[1])

    def test_retained_memory_membership_still_blocks_removal(self):
        self.assert_retained_tail_tamper_rejected(evict_memory=False)

    def test_validated_disk_membership_still_blocks_removal(self):
        self.assert_retained_tail_tamper_rejected(evict_memory=True)


if __name__ == '__main__':
    unittest.main()
