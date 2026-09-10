"""Bounded native crash-boundary regressions; every external call is mocked.

Positive fixtures use the known k=39 identity under an explicitly patched
runner verifier. No fixture claims to solve 114 or leaves this test directory.
"""
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import closing, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import random
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import runner
import search_core as core

PERSON = {'name': 'Recovery regression', 'github': 'recovery-test'}
KNOWN39 = ['-159380', '134476', '117367']
SEED = '12'*32


class LocalCoverage:
    def __init__(self, *_args, **_kwargs):
        self.index = {'revision': 0}
        self.known_skips = 0

    def snapshot(self):
        return {'revision': 0, 'updated_at': 'fixture', 'mode': 'offline'}

    refresh = snapshot

    def contains(self, _task):
        return False


class ImmediatePool:
    """Deterministic executor double; no processes or external services."""
    def __init__(self, **_kwargs):
        self.submissions = 0

    def submit(self, function, *args):
        self.submissions += 1
        future = Future()
        try:
            future.set_result(function(*args))
        except Exception as exc:
            future.set_exception(exc)
        return future

    def shutdown(self, **_kwargs):
        pass


def arguments(out, *extra):
    return ['--offline', '--name', PERSON['name'], '--github', PERSON['github'],
            '--workers', '1', '--minutes', '1', '--max-tasks', '1',
            '--seed', SEED, '--output', str(out), *extra]


def reserve(db, task, result=None):
    db.execute('INSERT INTO tasks(id,task,result) VALUES(?,?,?)',
               (core.task_id(task), core.canonical_json(task),
                core.canonical_json(result) if result is not None else None))
    db.commit()


def known39_verifier(xyz):
    return core.verify_triple(xyz, 39)


class RunnerRecoveryTests(unittest.TestCase):
    def test_curve_callback_survives_later_candidate_failure(self):
        d, z = 24904, 117367
        actual_check = core.check_candidate
        found, checks = [], []

        def second_candidate_fails(k, s, candidate, **kwargs):
            checks.append(candidate)
            if len(checks) == 2:
                raise ArithmeticError('injected later candidate failure')
            return actual_check(k, s, candidate, **kwargs)

        with patch.object(core, 'check_candidate', side_effect=second_candidate_fails):
            with self.assertRaisesRegex(ArithmeticError, 'later candidate'):
                core.scan_curve(39, d, z % d, z//d, z//d+1, sieve=False, on_hit=found.append)
        self.assertEqual(checks, [z, z+d])
        self.assertEqual(len(found), 1)
        self.assertTrue(core.verify_triple(found[0]['xyz'], 39))

    def test_callback_leaves_final_task_digest_and_hit_order_unchanged(self):
        task = core.make_task('c05', 0)
        self.assertEqual(core.run_task(task), core.run_task(task, on_hit=lambda _hit: None))
        hits = []
        args = (39, 24904, 117367 % 24904, 117367//24904, 117367//24904)
        plain = core.scan_curve(*args)
        observed = core.scan_curve(*args, on_hit=hits.append)
        self.assertEqual(plain, observed)
        self.assertEqual(hits, plain['hits'])

    def test_worker_preserves_and_announces_identity_even_if_task_later_fails(self):
        def interrupted_task(_task, on_hit=None):
            on_hit({'xyz': KNOWN39})
            raise ArithmeticError('injected post-discovery hash failure')

        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            with closing(runner.open_state(out, PERSON)) as db:
                reserve(db, core.make_task('c00', 0))
            output, errors = io.StringIO(), io.StringIO()
            with patch.object(runner, 'verify_triple', side_effect=known39_verifier), \
                 patch.object(runner, 'run_task', side_effect=interrupted_task), \
                 patch.object(runner, 'CoverageIndex', LocalCoverage), \
                 patch.object(runner, 'ProcessPoolExecutor', ImmediatePool), \
                 patch.object(runner.signal, 'signal'), \
                 patch.object(runner.subprocess, 'run', side_effect=AssertionError('no external calls')), \
                 redirect_stdout(output), redirect_stderr(errors):
                status_code = runner.main(arguments(out))
            self.assertEqual(status_code, 2)
            self.assertIn('EXACT IDENTITY RECOVERED', output.getvalue())
            self.assertIn('post-discovery hash failure', errors.getvalue())
            files = list((out/'discoveries').glob('identity-*.json'))
            self.assertEqual(len(files), 1)
            identity = json.loads(files[0].read_text())
            self.assertTrue(known39_verifier(identity['hit']['xyz']))
            self.assertEqual(identity['task'], core.make_task('c00', 0))
            status = json.loads((out/'status.json').read_text())
            self.assertEqual(status['state'], 'failed')
            self.assertEqual(status['completed_this_run'], 0)
            self.assertEqual(len(status['discoveries']), 1)
            with closing(runner.open_state(out, PERSON)) as db:
                self.assertEqual(db.execute('SELECT result,bank FROM tasks').fetchone(), (None, None))
                self.assertEqual(db.execute('SELECT count(*) FROM bank_priority').fetchone()[0], 1)
            banks = [json.loads(path.read_text()) for path in (out/'banks').glob('*.json')]
            self.assertEqual(len(banks), 1)
            self.assertEqual(banks[0]['schema'], 'math-gambling-identity-v1')
            self.assertNotIn('tasks', banks[0])

    def test_startup_recovers_legacy_positive_result_before_coverage_or_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            task = core.make_task('c00', 0)
            result = core.run_task(task)
            result['hits'] = [{'xyz': KNOWN39}]
            with closing(runner.open_state(out, PERSON)) as db:
                reserve(db, task, result)
            with patch.object(runner, 'verify_triple', side_effect=known39_verifier), \
                 patch.object(runner, 'CoverageIndex', side_effect=AssertionError('no coverage needed')), \
                 patch.object(runner, 'ProcessPoolExecutor', side_effect=AssertionError('no new computation')), \
                 patch.object(runner.subprocess, 'run', side_effect=AssertionError('no external calls')), \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(runner.main(arguments(out)), 0)
                # Already registered discoveries also halt a later invocation.
                self.assertEqual(runner.main(arguments(out)), 0)
            status = json.loads((out/'status.json').read_text())
            self.assertEqual(status['state'], 'discovery_found')
            self.assertEqual(status['completed_this_run'], 0)
            with closing(runner.open_state(out, PERSON)) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM discoveries').fetchone()[0], 1)
                self.assertEqual(db.execute('SELECT count(*) FROM banks').fetchone()[0], 1)

    def test_corrupt_discovery_cannot_hide_another_valid_saved_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out/'discoveries').mkdir()
            (out/'discoveries'/'a-corrupt.json').write_text('{invalid', encoding='utf-8')
            runner.atomic_json(out/'discoveries'/'z-good.json', {'hit': {'xyz': KNOWN39}})
            output = io.StringIO()
            with patch.object(runner, 'verify_triple', side_effect=known39_verifier), \
                 patch.object(runner, 'CoverageIndex', side_effect=AssertionError('no new tasks')), \
                 redirect_stdout(output), redirect_stderr(io.StringIO()):
                self.assertEqual(runner.main(arguments(out)), 2)
            self.assertIn('EXACT IDENTITY RECOVERED', output.getvalue())
            status = json.loads((out/'status.json').read_text())
            self.assertEqual(status['state'], 'failed')
            self.assertEqual(len(status['discoveries']), 1)
            self.assertEqual(len(list((out/'banks').glob('*.json'))), 1)

    def test_seed_cursor_resumes_from_committed_allocation(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            control = out/'control'; control.mkdir()
            with closing(runner.open_state(out, PERSON)) as db:
                rng, resumed = runner.restore_rng(db, SEED)
                self.assertFalse(resumed)
                allocated = [runner.choose_task(rng, [1/81]*81, db, seed=SEED) for _ in range(4)]
            with closing(runner.open_state(out, PERSON)) as db:
                rng, resumed = runner.restore_rng(db, SEED)
                self.assertTrue(resumed)
                allocated.append(runner.choose_task(rng, [1/81]*81, db, seed=SEED))
            with closing(runner.open_state(control, PERSON)) as db:
                rng, _ = runner.restore_rng(db, SEED)
                expected = [runner.choose_task(rng, [1/81]*81, db, seed=SEED) for _ in range(5)]
            self.assertEqual(allocated, expected)
            self.assertEqual(len({core.task_id(task) for task in allocated}), 5)

    def test_legacy_seed_checkpoint_skips_its_existing_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            with closing(runner.open_state(out, PERSON)) as db:
                old_rng = random.Random(int(SEED, 16))
                old = [runner.choose_task(old_rng, [1/81]*81, db) for _ in range(3)]
                expected_context = old_rng.getstate()
                resumed, existed = runner.restore_rng(db, SEED)
                self.assertFalse(existed)
                fresh = runner.choose_task(resumed, [1/81]*81, db, seed=SEED)
                self.assertNotIn(fresh, old)
                independent = random.Random(); independent.setstate(expected_context)
                c = independent.choices(core.CONTEXTS, weights=[1/81]*81, k=1)[0]
                row = independent.randrange(int(c['rowTasks']))*c['rowStride']
                expected = core.make_task(c['id'], row, independent.randrange(c['blocks']))
                self.assertEqual(fresh, expected)
                saved, exists = runner.restore_rng(db, SEED)
                self.assertTrue(exists)
                self.assertEqual(saved.getstate(), resumed.getstate())

    def test_worker_failure_returns_nonzero_structured_status_and_retryable_task(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            with closing(runner.open_state(out, PERSON)) as db:
                reserve(db, core.make_task('c00', 0))
            with patch.object(runner, 'run_task', side_effect=ArithmeticError('injected worker failure')), \
                 patch.object(runner, 'CoverageIndex', LocalCoverage), \
                 patch.object(runner, 'ProcessPoolExecutor', ImmediatePool), \
                 patch.object(runner.signal, 'signal'), \
                 redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(runner.main(arguments(out)), 2)
            status = json.loads((out/'status.json').read_text())
            self.assertEqual(status['state'], 'failed')
            self.assertEqual(status['errors'], ['injected worker failure'])
            with closing(runner.open_state(out, PERSON)) as db:
                self.assertEqual(db.execute('SELECT result FROM tasks').fetchone(), (None,))

    def test_relative_bank_and_legacy_windows_path_resolve_after_relocation(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            with closing(runner.open_state(out, PERSON)) as db:
                task = core.make_task('c00', 0)
                reserve(db, task, core.run_task(task))
                with redirect_stdout(io.StringIO()):
                    path = runner.write_bank(out, db, PERSON, force=True)
                bid, relative = db.execute('SELECT id,path FROM banks').fetchone()
                self.assertEqual(relative, 'banks/'+path.name)
                legacy = 'C:\\old computer\\moved run\\banks\\'+path.name
                db.execute('UPDATE banks SET path=?', (legacy,)); db.commit()
                relocated, _ = runner.resolve_bank(db, bid, legacy)
                self.assertEqual(relocated.resolve(), path.resolve())
                self.assertEqual(db.execute('SELECT path FROM banks').fetchone()[0], relative)
                path.write_text('{}', encoding='utf-8')
                with patch.object(runner.subprocess, 'run', side_effect=AssertionError('tampered bank cannot be submitted')), \
                     redirect_stderr(io.StringIO()):
                    runner.maybe_submit(db, 'fixture/repository', -float('inf'))
                self.assertIsNone(db.execute('SELECT submitted FROM banks').fetchone()[0])

    def test_submission_intent_survives_interruption_without_blind_retry(self):
        class SimulatedInterruption(BaseException):
            pass

        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            with closing(runner.open_state(out, PERSON)) as db:
                task = core.make_task('c00', 0)
                reserve(db, task, core.run_task(task))
                with redirect_stdout(io.StringIO()):
                    runner.write_bank(out, db, PERSON, force=True)

                def mock_external(command, **_kwargs):
                    if command[2] == 'list':
                        return subprocess.CompletedProcess(command, 0, '[]', '')
                    self.assertEqual(command[2], 'create')
                    # A separate connection proves the intent was committed
                    # before dispatch, not just pending in memory.
                    with closing(sqlite3.connect(out/'checkpoint.sqlite3')) as observer:
                        self.assertTrue(observer.execute('SELECT submitted FROM banks').fetchone()[0].startswith('uncertain;'))
                    raise SimulatedInterruption()

                with patch.object(runner.subprocess, 'run', side_effect=mock_external):
                    with self.assertRaises(SimulatedInterruption):
                        runner.maybe_submit(db, 'fixture/repository', -float('inf'))
            with closing(runner.open_state(out, PERSON)) as db, \
                 patch.object(runner.subprocess, 'run', side_effect=AssertionError('uncertain bank must not be dispatched again')):
                runner.maybe_submit(db, 'fixture/repository', -float('inf'))
                self.assertEqual(runner.bank_queue(db)['uncertain'], 1)

    def test_atomic_json_concurrent_writers_have_independent_temporary_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'same-identity.json'
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(runner.atomic_json, path, {'writer': n}) for n in range(16)]
                for future in futures:
                    future.result()
            self.assertIn(json.loads(path.read_text())['writer'], range(16))
            self.assertEqual(list(path.parent.glob('*.tmp')), [])


if __name__ == '__main__':
    unittest.main()
