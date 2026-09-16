"""Engine v2 dispatch plus the cross-target 60/40 slice in the main runner.

Everything here runs offline against the bundled snapshot: no network, no gh.
114 claims must stay in `[bank]` banks with engine v2 tasks, cross-target claims
must land in separate `[bank-mt]` banks that the target verifier accepts, and
both must survive a restart without recomputing or re-posting banked work.
"""
from contextlib import closing
import json
from pathlib import Path
import random
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import runner
import multi_target as mt
from native_kernel import binary_path
import target_ingest as ti
import search_core as core

PERSON = {'name': 'Targets fixture', 'github': 'targets-fixture'}


def invoke(out, *extra, tasks='6'):
    return subprocess.run([sys.executable, str(ROOT/'tools/runner.py'), '--offline', '--kernel', 'python',
                           '--name', PERSON['name'], '--github', PERSON['github'], '--workers', '1',
                           '--minutes', '2', '--max-tasks', tasks, '--output', str(out), *extra],
                          stdin=subprocess.DEVNULL, capture_output=True, text=True,
                          encoding='utf-8', timeout=600)


def banks(out, prefix):
    """Bank files in one namespace: 'bank-' is 114, 'bank-mt-' is cross-target."""
    return sorted(p for p in (out/'banks').glob('bank-*.json')
                  if p.name.startswith(prefix) and p.name.startswith('bank-mt-') == (prefix == 'bank-mt-'))


class RunnerTargetTests(unittest.TestCase):
    def test_offline_run_banks_v2_114_work_and_separate_target_banks(self):
        with tempfile.TemporaryDirectory(prefix='mg targets ') as tmp:
            out = Path(tmp)
            result = invoke(out, '--targets-share', '0.5', '--bank-every', '1', '--seed', '2c'*32)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            primary, targets = banks(out, 'bank-'), banks(out, 'bank-mt-')
            self.assertTrue(primary, result.stdout)
            self.assertTrue(targets, result.stdout)
            for path in primary:
                bank = json.loads(path.read_text())
                self.assertEqual(bank['schema'], 'math-gambling-bank-v1')
                for claim in bank['tasks']:
                    self.assertEqual(claim['task']['engine'], core.ENGINE_V2)
                    self.assertEqual(claim['task']['version'], 2)
                    self.assertEqual(int(claim['task']['row']) % 1024, 0)
            verify = Path(tmp)/'verify'
            accepted = 0
            for index, path in enumerate(targets):
                bank = json.loads(path.read_text())
                self.assertEqual(bank['schema'], 'math-gambling-target-bank-v1')
                self.assertEqual(bank['contributor'], PERSON)
                for claim in bank['tasks']:
                    self.assertNotEqual(mt.parse_engine(claim['task']['engine']), None)
                    self.assertNotEqual(claim['task']['engine'], core.ENGINE)
                record = ti.process_target_bank(bank, {'id': f'issue:{index}', 'kind': 'issue', 'number': index,
                                                       'submitter': PERSON['github'], 'url': 'u'}, verify, ti.Budget())
                self.assertEqual(record['rejected'], [])
                accepted += len(record['accepted'])
            self.assertGreater(accepted, 0)
            status = json.loads((out/'status.json').read_text())
            self.assertEqual(status['state'], 'stopped')
            self.assertGreater(status['target_tasks_this_run'], 0)
            self.assertLess(status['target_tasks_this_run'], status['completed_this_run'])

    def test_targets_share_zero_runs_only_114(self):
        with tempfile.TemporaryDirectory(prefix='mg targets off ') as tmp:
            out = Path(tmp)
            result = invoke(out, '--targets-share', '0', '--bank-every', '1', tasks='3')
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertEqual(banks(out, 'bank-mt-'), [])
            self.assertTrue(banks(out, 'bank-'))
            with closing(sqlite3.connect(out/'checkpoint.sqlite3')) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM target_tasks').fetchone()[0], 0)
            status = json.loads((out/'status.json').read_text())
            self.assertEqual(status['target_tasks_this_run'], 0)
            self.assertEqual(status['targets_share'], 0)

    def test_restart_resumes_reserved_target_work_without_reposting_banks(self):
        with tempfile.TemporaryDirectory(prefix='mg targets resume ') as tmp:
            out = Path(tmp)
            first = invoke(out, '--targets-share', '0.5', '--bank-every', '1', tasks='4')
            self.assertEqual(first.returncode, 0, first.stdout+first.stderr)
            # Reserve an unfinished target task, as a crash mid-dispatch would.
            with closing(runner.open_state(out, PERSON)) as db:
                task = mt.make_target_task(627, mt.ELL1_CONTEXTS[0], 0, 0)
                db.execute('INSERT OR REPLACE INTO target_tasks(id,task) VALUES(?,?)',
                           (mt.target_task_id(task), core.canonical_json(task)))
                db.commit()
                before = {p.name: p.read_bytes() for p in (out/'banks').glob('*.json')}
                banked = db.execute('SELECT count(*) FROM target_tasks WHERE bank IS NOT NULL').fetchone()[0]
            second = invoke(out, '--targets-share', '0.5', '--bank-every', '1', tasks='2')
            self.assertEqual(second.returncode, 0, second.stdout+second.stderr)
            with closing(sqlite3.connect(out/'checkpoint.sqlite3')) as db:
                self.assertIsNotNone(db.execute('SELECT result FROM target_tasks WHERE id=?',
                                                (mt.target_task_id(task),)).fetchone()[0])
                self.assertGreater(db.execute('SELECT count(*) FROM target_tasks WHERE bank IS NOT NULL').fetchone()[0], banked)
                # Every claim is banked exactly once, in its own namespace.
                rows = db.execute("SELECT id,COALESCE(kind,'bank') FROM banks").fetchall()
            self.assertEqual({kind for _, kind in rows}, {'bank', 'bank-mt'})
            for name, raw in before.items():
                self.assertEqual((out/'banks'/name).read_bytes(), raw)
            claims = [mt.target_task_id(claim['task']) for path in (out/'banks').glob('bank-mt-*.json')
                      for claim in json.loads(path.read_text())['tasks']]
            self.assertEqual(len(claims), len(set(claims)))
            self.assertFalse([tid for tid in claims if tid.startswith('mg114-')])

    def test_target_selection_is_reserved_deduplicated_and_never_provably_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            with closing(runner.open_state(out, PERSON)) as db:
                weights = runner.target_weights((390, 627))
                self.assertAlmostEqual(sum(weights.values()), 1.0)
                rng = random.Random(114)
                chosen = [runner.choose_target_task(rng, weights, db, seed='ab'*32) for _ in range(4)]
                ids = [mt.target_task_id(task) for task in chosen]
                self.assertEqual(len(set(ids)), 4)
                for task in chosen:
                    self.assertIn(mt.parse_engine(task['engine']), (390, 627))
                    self.assertIn(task['context'], mt.ELL1_CONTEXTS)
                    self.assertFalse(mt.prove_empty_target(task))
                    self.assertEqual(task['version'], 1)
                reserved = {row[0] for row in db.execute('SELECT id FROM target_tasks')}
                self.assertEqual(reserved, set(ids))
                # A reserved id is never proposed twice, even in a fresh process.
                repeat = runner.choose_target_task(random.Random(114), weights, db)
                self.assertNotIn(mt.target_task_id(repeat), ids)

    def test_target_hit_is_preserved_immediately_outside_the_114_discovery_folder(self):
        # Synthetic hit metadata: it exercises identity-first preservation only.
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            hit = {'xyz': ['1', '1', '1'], 'D': '7', 'r': '1', 'q': '0'}
            task = mt.make_target_task(3, mt.ELL1_CONTEXTS[0], 0, 0)
            path = runner.preserve_target_identity(out, 3, hit, task)
            self.assertTrue(path.exists())
            self.assertEqual(path.parent, out/'discoveries'/'targets')
            self.assertEqual(list((out/'discoveries').glob('*.json')), [])
            saved = json.loads(path.read_text())
            self.assertEqual(saved['k'], 3)
            self.assertEqual(saved['task'], task)
            with self.assertRaises(ArithmeticError):
                runner.preserve_target_identity(out, 114, hit, task)


class RunnerTargetRustKernelTests(unittest.TestCase):
    """The Rust kernel must produce exactly the Python target results it replaces."""

    @unittest.skipUnless(binary_path().is_file(), 'build Rust with tools/build_native.py')
    def test_rust_kernel_target_results_match_python(self):
        with tempfile.TemporaryDirectory(prefix='mg targets rust ') as tmp:
            out = Path(tmp)
            result = invoke(out, '--kernel', 'rust', '--targets-share', '1', '--bank-every', '1', tasks='4')
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            lines = (out/'target-results.jsonl').read_text().splitlines()
            self.assertTrue(lines)
            for line in lines:
                saved = json.loads(line)
                self.assertEqual(saved, mt.run_target_task(saved['task']))
            self.assertTrue(banks(out, 'bank-mt-'))


if __name__ == '__main__':
    unittest.main()
