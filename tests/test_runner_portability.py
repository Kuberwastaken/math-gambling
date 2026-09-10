"""Bounded real-process checks for the downloaded standard-library client.

These tests do not post issues or fetch shared strategy. The same subprocess
and spawn paths execute on macOS, Windows and Linux. Optional archive smoke
uses MG_RUNNER_ARCHIVE to verify the actual build output after extraction.
"""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import runner
import search_core as core

PERSON = {'name': 'Portable Δ test', 'github': 'portable-test'}


def fixture_task(context):
    c = core.CONTEXT_BY_ID[context]
    row = int(c['totalRows']) // 7 // core.ROWS_PER_TASK * core.ROWS_PER_TASK
    return core.make_task(context, row, c['blocks'] // 2)


def reserve(out, tasks, person=PERSON):
    out.mkdir(parents=True, exist_ok=True)
    db = runner.open_state(out, person)
    for task in tasks:
        db.execute('INSERT INTO tasks(id,task) VALUES(?,?)',
                   (core.task_id(task), core.canonical_json(task)))
    db.commit()
    db.close()


def invoke(root, out, count=1, *, extra=()):
    return subprocess.run([
        sys.executable, str(root / 'tools' / 'runner.py'), '--offline',
        '--name', PERSON['name'], '--github', PERSON['github'],
        '--minutes', '1', '--workers', str(min(2, os.cpu_count() or 1)),
        '--max-tasks', str(count), '--output', str(out), *extra,
    ], cwd=root, capture_output=True, encoding='utf-8', errors='replace', timeout=60)


class RunnerPortabilityTests(unittest.TestCase):
    def test_spawn_checkpoint_resume_and_exact_receipts(self):
        tasks = [fixture_task(c) for c in ('c03', 'c05', 'c08')]
        with tempfile.TemporaryDirectory(prefix='mg114 portable ') as directory:
            out = Path(directory) / 'results with spaces'
            reserve(out, tasks)
            first = invoke(ROOT, out, 2)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            status = json.loads((out / 'status.json').read_text(encoding='utf-8'))
            self.assertEqual(status['completed_this_run'], 2)
            banks_before = {p.name: p.read_bytes() for p in (out / 'banks').glob('bank-*.json')}
            self.assertEqual(len(banks_before), 1)
            second = invoke(ROOT, out, 1)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            status = json.loads((out / 'status.json').read_text(encoding='utf-8'))
            self.assertEqual(status['completed_this_run'], 1)
            self.assertEqual(status['state'], 'stopped')
            with closing(sqlite3.connect(out / 'checkpoint.sqlite3')) as db:
                rows = db.execute('SELECT id,result FROM tasks').fetchall()
                self.assertEqual(len(rows), 3)
                self.assertTrue(all(result for _, result in rows))
                self.assertEqual({tid: json.loads(result) for tid, result in rows},
                                 {core.task_id(task): core.run_task(task) for task in tasks})
            claims = []
            for path in (out / 'banks').glob('bank-*.json'):
                bank = json.loads(path.read_text(encoding='utf-8'))
                self.assertEqual(bank['contributor'], PERSON)
                claims.extend(bank['tasks'])
            self.assertEqual(len(claims), 3)
            self.assertEqual(len({core.task_id(claim['task']) for claim in claims}), 3)
            for name, content in banks_before.items():
                self.assertEqual((out / 'banks' / name).read_bytes(), content)
            self.assertGreater(sum(core.run_task(task)['counters']['exact_tests'] for task in tasks), 0)

    def test_output_lock_rejects_second_process(self):
        with tempfile.TemporaryDirectory(prefix='mg114 lock ') as directory:
            out = Path(directory)
            held = runner.lock_output(out / 'runner.lock')
            try:
                result = invoke(ROOT, out)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Another runner owns this output directory', result.stderr)
                self.assertFalse((out / 'checkpoint.sqlite3').exists())
            finally:
                held.close()

    def test_help_and_public_link_validation(self):
        result = subprocess.run([sys.executable, str(ROOT / 'tools/runner.py'), '--help'],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--url', result.stdout)
        self.assertEqual(runner.profile_url('https://example.org/about?q=114#me'),
                         'https://example.org/about?q=114#me')
        self.assertIsNone(runner.profile_url(''))
        for bad in ('javascript:alert(1)', '//example.org', 'https://me:pw@example.org',
                    'https://example.org/hello world', 'https://example.org/\nnext',
                    'https://example.org\\evil', 'https://', 'https://example.org:bad',
                    'https://example.org/' + 'x' * 2048):
            with self.subTest(value=bad[:80]), self.assertRaises(argparse.ArgumentTypeError):
                runner.profile_url(bad)

    def test_optional_link_survives_local_bank(self):
        with tempfile.TemporaryDirectory(prefix='mg114 link ') as directory:
            out = Path(directory)
            person = {**PERSON, 'url': 'https://example.org/'}
            reserve(out, [fixture_task('c05')], person)
            result = invoke(ROOT, out, extra=('--url', person['url']))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            banks = list((out / 'banks').glob('bank-*.json'))
            self.assertEqual(len(banks), 1)
            self.assertEqual(json.loads(banks[0].read_text())['contributor'], person)

    @unittest.skipUnless(os.environ.get('MG_RUNNER_ARCHIVE'), 'archive path is supplied after site build')
    def test_actual_download_extracts_and_runs(self):
        archive = Path(os.environ['MG_RUNNER_ARCHIVE']).resolve()
        with tempfile.TemporaryDirectory(prefix='mg114 extracted download ') as directory:
            destination = Path(directory)
            with zipfile.ZipFile(archive) as zipped:
                self.assertIn('math-gambling/docs/RUNNER_SETUP.md', zipped.namelist())
                zipped.extractall(destination)
            root = destination / 'math-gambling'
            out = root / 'first result'
            reserve(out, [fixture_task('c05')])
            result = invoke(root, out)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads((out / 'status.json').read_text())['completed_this_run'], 1)
            self.assertEqual(len(list((out / 'banks').glob('bank-*.json'))), 1)


if __name__ == '__main__':
    unittest.main()
