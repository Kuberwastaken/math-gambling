"""Fault and provenance checks for the separate mathematical-coverage export."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import math_coverage as mc
import search_core as core


EMPTY = core.make_task('c20', 354300175232, 268)
NONEMPTY = core.make_task('c09', 6742964476928, 8)
OTHER = core.make_task('c16', 4840679990528, 10)
KNOWN_39 = ['-159380', '134476', '117367']


def row(task, sequence):
    return {'schema': 'math-gambling-verified-task-v1', 'sequence': sequence,
        'result': core.run_task(task), 'verified_at': '2026-09-11T00:00:00Z',
        'source': {'kind': 'test'}, 'contributor': {'name': 'Fixture', 'github': 'fixture'},
        'server_replay_cpu_ms': 1.0}


def write_ledger(data, rows):
    for item in rows:
        digest = hashlib.sha256(item['result']['id'].encode()).hexdigest()
        mc.atomic_json(data/'receipts/tasks'/digest[:2]/f'{digest}.json', item)


class MathematicalCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.empty = row(EMPTY, 1)
        cls.nonempty = row(NONEMPTY, 2)
        cls.other = row(OTHER, 3)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root/'data'
        self.out = self.data/'math-coverage'

    def tearDown(self):
        self.temp.cleanup()

    def read_record(self, entry):
        raw = (self.out/entry['file']).read_bytes()
        self.assertEqual(mc.sha(raw), entry['sha256'])
        return json.loads(gzip.decompress(raw))

    def replay(self, task, output, timeout):
        return mc.execute_kernel(task, output)

    def test_empty_and_nonempty_tasks_describe_actual_replayed_domain(self):
        write_ledger(self.data, [self.empty, self.nonempty])
        index = mc.export(self.data, seconds=10, replay_fn=self.replay)
        self.assertEqual(index['status'], 'complete')
        self.assertEqual(index['empty_task_count'], 1)
        empty, full = map(self.read_record, index['records'])
        self.assertEqual(empty['certificate'], 'empty-task')
        self.assertTrue(empty['task_completed'])
        self.assertEqual(empty['intervals'], [])
        self.assertEqual(empty['q_positions_replayed'], '0')
        self.assertEqual(full['raw_scan_interval_count'], 619)
        self.assertEqual(int(full['q_positions_replayed']), self.nonempty['result']['counters']['quotient_points'])
        self.assertTrue(full['scope']['minimal_abs_z'])
        self.assertFalse(full['scope']['global_union_computed'])
        self.assertEqual(full['kernel_source_sha256'], mc.sha(Path(core.__file__).read_bytes()))

    def test_incremental_cap_and_repeat_do_not_replay_exported_prefix(self):
        write_ledger(self.data, [self.empty, self.nonempty, self.other])
        first = mc.export(self.data, max_tasks=1, seconds=10, replay_fn=self.replay)
        self.assertEqual(first['ledger_watermark'], 3)
        self.assertEqual(first['exported_through_sequence'], 1)
        self.assertEqual(first['last_run']['stop_reason'], 'task-cap')
        prior_bytes = (self.out/first['records'][0]['file']).read_bytes()
        calls = []
        def record_replay(task, output, timeout):
            calls.append(task)
            return self.replay(task, output, timeout)
        second = mc.export(self.data, seconds=10, replay_fn=record_replay)
        self.assertEqual(calls, [NONEMPTY, OTHER])
        self.assertEqual(prior_bytes, (self.out/second['records'][0]['file']).read_bytes())
        with patch.object(mc, 'replay_task', side_effect=AssertionError('no replay expected')):
            complete = mc.export(self.data, seconds=10, replay_fn=lambda *_: self.fail('replayed prefix'))
        self.assertEqual(complete['last_run']['attempted_tasks'], 0)

    def test_changed_kernel_hash_does_not_rewrite_completed_records(self):
        write_ledger(self.data, [self.empty, self.nonempty])
        first = mc.export(self.data, max_tasks=1, seconds=10, replay_fn=self.replay)
        def changed(task, output, timeout):
            result = self.replay(task, output, timeout)
            result['kernel_source_sha256'] = 'b'*64
            return result
        second = mc.export(self.data, seconds=10, replay_fn=changed)
        self.assertEqual(first['records'][0], second['records'][0])
        self.assertEqual(second['records'][1]['kernel_source_sha256'], 'b'*64)

    def test_complete_digest_mismatch_cannot_publish_any_intervals(self):
        write_ledger(self.data, [self.empty, self.nonempty])
        def altered(task, output, timeout):
            replay = self.replay(task, output, timeout)
            if task == NONEMPTY:
                replay['result']['counters']['exact_tests'] += 1
                body = {k: v for k, v in replay['result'].items() if k != 'digest'}
                replay['result']['digest'] = mc.sha(core.canonical_json(body).encode())
            return replay
        index = mc.export(self.data, seconds=10, replay_fn=altered)
        self.assertEqual(index['exported_task_count'], 1)
        self.assertIn('differs', index['last_run']['error'])
        self.assertEqual(len(list((self.out/'records').glob('*/*.gz'))), 1)

    def test_missing_completed_curve_callback_blocks_coverage(self):
        write_ledger(self.data, [self.empty, self.nonempty])
        def incomplete(task, output, timeout):
            replay = self.replay(task, output, timeout)
            if replay['curves']:
                replay['curves'].pop()
            return replay
        index = mc.export(self.data, seconds=10, replay_fn=incomplete)
        self.assertEqual(index['exported_task_count'], 1)
        self.assertIn('do not account', index['last_run']['error'])

    def test_task_local_union_merges_overlap_and_adjacency_only(self):
        def curve(lo, hi):
            return dict(D='5', r='4', s='-5', qlo=str(lo), qhi=str(hi), minimal_abs_z=True)
        self.assertEqual(mc.merge_intervals([curve(3, 5), curve(1, 3), curve(6, 6), curve(10, 11)]),
            [['5', '4', '-5', '1', '6'], ['5', '4', '-5', '10', '11']])
        bad = curve(1, 2); bad['minimal_abs_z'] = False
        with self.assertRaises(ValueError):
            mc.merge_intervals([bad])
        bad = curve(1, 2); bad['s'] = '5'
        with self.assertRaises(ValueError):
            mc.merge_intervals([bad])

    def test_deterministic_gzip_and_content_addressed_bytes(self):
        raw = b'large exact integers, inclusive intervals\n'*100
        first = mc.deterministic_gzip(raw)
        self.assertEqual(first, mc.deterministic_gzip(raw))
        self.assertEqual(first[4:8], bytes(4))
        self.assertEqual(first[9], 255)
        self.assertEqual(gzip.decompress(first), raw)

    def test_tampered_prior_blob_or_ledger_cannot_advance_index(self):
        write_ledger(self.data, [self.empty])
        index = mc.export(self.data, seconds=10, replay_fn=self.replay)
        previous = (self.out/'index.json').read_bytes()
        path = self.out/index['records'][0]['file']
        original = path.read_bytes()
        path.write_bytes(original+b'corrupt')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            mc.export(self.data, seconds=10, replay_fn=self.replay)
        self.assertEqual(previous, (self.out/'index.json').read_bytes())
        path.write_bytes(original)
        changed = copy.deepcopy(self.empty); changed['verified_at'] = '2026-09-11T01:00:00Z'
        write_ledger(self.data, [changed])
        with self.assertRaisesRegex(ValueError, 'changed within'):
            mc.export(self.data, seconds=10, replay_fn=self.replay)
        self.assertEqual(previous, (self.out/'index.json').read_bytes())

    def test_gap_and_duplicate_sequences_rejected_before_replay(self):
        write_ledger(self.data, [self.nonempty])
        with self.assertRaisesRegex(ValueError, 'not contiguous'):
            mc.export(self.data, seconds=10, replay_fn=lambda *_: self.fail('replayed invalid ledger'))
        self.assertFalse((self.out/'index.json').exists())

    def test_operational_failure_keeps_completed_prefix_and_retries_only_failure(self):
        write_ledger(self.data, [self.empty, self.nonempty])
        def fail(task, output, timeout):
            if task == NONEMPTY:
                raise subprocess.TimeoutExpired('test trusted worker', timeout)
            return self.replay(task, output, timeout)
        partial = mc.export(self.data, seconds=10, replay_fn=fail)
        self.assertEqual(partial['exported_task_count'], 1)
        self.assertEqual(partial['last_run']['stop_reason'], 'task-timeout')
        complete = mc.export(self.data, seconds=10, replay_fn=self.replay)
        self.assertEqual(complete['last_run']['attempted_tasks'], 1)
        self.assertFalse((self.out/'last-error.json').exists())

    def test_wall_and_task_limits_are_validated_and_bound_dispatch(self):
        write_ledger(self.data, [self.empty, self.nonempty])
        for kwargs in ({'seconds': float('nan')}, {'seconds': float('inf')}, {'seconds': 0},
                       {'max_tasks': 0}, {'max_tasks': True}, {'max_tasks': mc.MAX_TASKS+1}):
            with self.assertRaises(ValueError):
                mc.export(self.data, **kwargs)
        with patch.object(mc, 'load_ledger', return_value=[self.empty, self.nonempty]), \
             patch.object(mc, 'previous_records', return_value=[]), \
             patch.object(mc.time, 'monotonic', side_effect=[0, 0.999, 1]):
            index = mc.export(self.data, seconds=1, replay_fn=lambda *_: self.fail('dispatched after budget'))
        self.assertEqual(index['last_run']['attempted_tasks'], 0)
        self.assertEqual(index['last_run']['stop_reason'], 'wall-budget')

    def test_encountered_identity_survives_later_kernel_exception(self):
        # A known k=39 identity exercises persistence, with the verifier target
        # explicitly substituted; this test does not invent a solution to114.
        source = self.root/'fault_kernel.py'
        source.write_text('def run_task(task,on_hit=None,on_curve=None):\n'
            f'    on_hit({{"xyz":{KNOWN_39!r}}})\n'
            '    raise RuntimeError("later candidate failed")\n')
        with patch.object(mc, 'verify_triple', side_effect=lambda xyz: core.verify_triple(xyz, 39)):
            with self.assertRaisesRegex(RuntimeError, 'later candidate'):
                mc.execute_kernel(EMPTY, self.out, kernel_path=source)
        saved = list((self.out/'discoveries').glob('*.json'))
        self.assertEqual(len(saved), 1)
        evidence = json.loads(saved[0].read_text())
        self.assertTrue(core.verify_triple(evidence['hit']['xyz'], 39))
        self.assertFalse(evidence['task_completion_claimed'])
        self.assertFalse((self.out/'index.json').exists())

    def test_default_positive_verifier_rejects_wrong_target(self):
        with self.assertRaisesRegex(ValueError, 'cube verification'):
            mc.save_hit(self.out, {'xyz': KNOWN_39})
        self.assertFalse((self.out/'discoveries').exists())

    def test_real_isolated_subprocess_matches_complete_trusted_result(self):
        replay = mc.replay_task(NONEMPTY, self.out, timeout=5)
        self.assertEqual(replay['result'], self.nonempty['result'])
        self.assertEqual(len(replay['curves']), 619)

    def test_same_output_second_writer_is_rejected(self):
        with mc.output_lock(self.out):
            with self.assertRaisesRegex(RuntimeError, 'another mathematical exporter'):
                with mc.output_lock(self.out):
                    self.fail('second writer acquired lock')

    def test_interrupted_index_publication_leaves_only_uncredited_immutable_bytes(self):
        write_ledger(self.data, [self.empty])
        real_write = mc.atomic_bytes
        def interrupt(path, raw):
            if Path(path).name == 'index.json':
                raise OSError('injected index publication failure')
            return real_write(path, raw)
        with patch.object(mc, 'atomic_bytes', side_effect=interrupt):
            with self.assertRaisesRegex(OSError, 'injected'):
                mc.export(self.data, seconds=10, replay_fn=self.replay)
        self.assertFalse((self.out/'index.json').exists())
        orphan = list((self.out/'records').glob('*/*.gz'))
        self.assertEqual(len(orphan), 1)
        completed = mc.export(self.data, seconds=10, replay_fn=self.replay)
        self.assertEqual(completed['exported_task_count'], 1)
        self.assertEqual(list((self.out/'records').glob('*/*.gz')), orphan)

    def test_metadata_timeout_keeps_prior_index_and_records_operational_error(self):
        write_ledger(self.data, [self.empty])
        mc.export(self.data, seconds=10, replay_fn=self.replay)
        previous = (self.out/'index.json').read_bytes()
        with patch.object(mc, 'load_ledger', side_effect=TimeoutError('metadata budget exhausted')):
            with self.assertRaises(TimeoutError):
                mc.export(self.data, seconds=10, replay_fn=self.replay)
        self.assertEqual(previous, (self.out/'index.json').read_bytes())
        error = json.loads((self.out/'last-error.json').read_text())
        self.assertFalse(error['coverage_advanced'])
        self.assertIn('metadata', error['error'])


if __name__ == '__main__':
    unittest.main()
