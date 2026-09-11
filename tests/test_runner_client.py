"""Versioned native-client scheduling, coverage and login regressions."""
import contextlib
import hashlib
import io
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import client_audit
import coverage_client as cc
import runner
import search_core as e


def snapshot(folder, completed=()):
    folder.mkdir(parents=True, exist_ok=True)
    shards = {}
    for c in e.CONTEXTS:
        tasks = sorted(tid for tid in completed if tid.split(':')[1] == c['id'])
        data = dict(schema='math-gambling-coverage-shard-v1', engine=e.ENGINE, context=c['id'], tasks=tasks)
        raw = (json.dumps(data, indent=2)+'\n').encode()
        digest = hashlib.sha256(raw).hexdigest()
        filename = f'{c["id"]}-{digest}.json'
        (folder/filename).write_bytes(raw)
        shards[c['id']] = dict(file=filename, sha256=digest, count=len(tasks))
    index = dict(schema='math-gambling-coverage-v1', engine=e.ENGINE, revision=len(completed),
                 verified_task_count=len(completed), updated_at='2026-09-10T12:00:00Z', shards=shards)
    raw = (json.dumps(index, indent=2)+'\n').encode()
    (folder/'index.json').write_bytes(raw)
    return raw


class RunnerClientTests(unittest.TestCase):
    def test_preflight_holds_context_and_bounded_fallback_never_credits_a_skip(self):
        with tempfile.TemporaryDirectory() as directory:
            db=runner.open_state(Path(directory),{'name':'proof fixture','github':'proof-fixture'})
            weights=runner.PolicyWeights([1/81]*81,{'proposal_preflight':'mg114-shell-tile-v1'})
            proposed=[]
            with patch('search_features.certified_empty',side_effect=lambda t:proposed.append(t) or True):
                task=runner.choose_task(random.Random(114),weights,db,seed='ab'*32)
            self.assertEqual(len(proposed),31)
            self.assertEqual({t['context'] for t in proposed},{task['context']})
            self.assertEqual(db.execute('SELECT count(*) FROM tasks').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM tasks WHERE result IS NOT NULL').fetchone()[0],0)
            db.close()
    @unittest.skipUnless(os.environ.get('MG_HTTP_FIXTURE'), 'local HTTP integration is enabled explicitly')
    def test_real_http_coverage_skips_reserved_task_before_spawn(self):
        with tempfile.TemporaryDirectory(prefix='mg114 http fixture ') as directory:
            root = Path(directory)
            known = e.make_task('c00', 0)
            fresh = e.make_task('c05', 128)
            snapshot(root/'published', [e.task_id(known)])
            agents = []
            class Handler(SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=str(root/'published'), **kwargs)
                def do_GET(self):
                    agents.append(self.headers.get('User-Agent'))
                    return super().do_GET()
                def log_message(self, *args):
                    pass
            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                out = root/'run'; out.mkdir()
                db = runner.open_state(out, {'name': 'HTTP fixture', 'github': 'test'})
                for task in (known, fresh):
                    db.execute('INSERT INTO tasks(id,task) VALUES(?,?)', (e.task_id(task), e.canonical_json(task)))
                db.commit(); db.close()
                url = f'http://127.0.0.1:{server.server_address[1]}/index.json'
                code = '''import functools,sys
sys.path.insert(0, sys.argv[1])
import runner
runner.CoverageIndex = functools.partial(runner.CoverageIndex, index_url=sys.argv[2])
runner.load_strategy = lambda offline=False: ([1/81]*81, 0)
raise SystemExit(runner.main(['--name','HTTP fixture','--github','test','--workers','1','--minutes','1','--max-tasks','1','--seed','11'*32,'--output',sys.argv[3]]))'''
                result = subprocess.run([sys.executable, '-c', code, str(ROOT/'tools'), url, str(out)],
                                        capture_output=True, encoding='utf-8', timeout=60)
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                status = json.loads((out/'status.json').read_text())
                self.assertEqual(status['completed_this_run'], 1)
                self.assertEqual(status['published_selections_skipped'], 1)
                self.assertEqual(status['seed'], '11'*32)
                self.assertTrue(agents)
                self.assertEqual(set(agents), {cc.UA})
            finally:
                server.shutdown(); server.server_close(); thread.join(timeout=5)

    def test_online_membership_hash_cache_and_rollback(self):
        known = e.make_task('c05', 0)
        other = e.make_task('c05', 128)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = snapshot(root/'server', [e.task_id(known)])
            requests = []
            def fetch(url, cap):
                requests.append(url)
                body = (root/'server'/url.rsplit('/', 1)[-1]).read_bytes()
                self.assertLessEqual(len(body), cap)
                return body
            coverage = cc.CoverageIndex(root/'missing-bundle', root/'cache', index_url='https://fixture.invalid/coverage/index.json', fetch=fetch)
            coverage.refresh()
            self.assertTrue(coverage.contains(known))
            self.assertFalse(coverage.contains(other))
            self.assertEqual(len(requests), 2)
            self.assertTrue(coverage.contains(known))
            self.assertEqual(len(requests), 2)
            current = cc.validate_index(raw)
            shard = current['shards']['c05']
            broken = (root/'server'/shard['file']).read_bytes() + b' '
            with self.assertRaises(cc.CoverageError):
                cc.validate_shard(broken, 'c05', shard)
            snapshot(root/'server')
            with self.assertRaisesRegex(cc.CoverageError, 'backwards'):
                coverage.refresh()
            self.assertEqual(coverage.snapshot()['revision'], 1)

    def test_invalid_coverage_never_silently_excludes(self):
        task = e.make_task('c05', 0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = snapshot(root/'bundle', [e.task_id(task)])
            index = cc.validate_index(raw)
            bad = dict(index, verified_task_count=999)
            with self.assertRaises(cc.CoverageError):
                cc.validate_index(json.dumps(bad).encode())
            entry = index['shards']['c05']
            (root/'bundle'/entry['file']).write_text('{}')
            coverage = cc.CoverageIndex(root/'bundle', root/'cache', offline=True)
            coverage.refresh()
            with self.assertRaises(cc.CoverageError):
                coverage.contains(task)

    def test_seed_and_policy_audit_does_not_change_task_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            seed = client_audit.seed_value('AB'*32)
            self.assertEqual(seed, 'ab'*32)
            digest = e.run_task(e.make_task('c05', 0))['digest']
            audit = client_audit.RunAudit(out, seed, {'workers': 1})
            audit.policy([1/81]*81, 0, {'revision': 128})
            audit.write('dispatch', task=e.make_task('c05', 0))
            records = [json.loads(line) for line in audit.path.read_text().splitlines()]
            self.assertEqual(records[0]['seed'], seed)
            self.assertEqual(records[0]['rng'], client_audit.RNG_ALGORITHM)
            self.assertEqual(records[1]['policy']['epoch'], 0)
            self.assertEqual(e.run_task(e.make_task('c05', 0))['digest'], digest)
            db1 = runner.open_state(out, {'name': 'Test', 'github': 'test'})
            rng1 = random.Random(int(seed, 16))
            first = [runner.choose_task(rng1, [1/81]*81, db1) for _ in range(3)]
            db1.close()
            other = out/'other'; other.mkdir()
            db2 = runner.open_state(other, {'name': 'Test', 'github': 'test'})
            rng2 = random.Random(int(seed, 16))
            second = [runner.choose_task(rng2, [1/81]*81, db2) for _ in range(3)]
            db2.close()
            self.assertEqual(first, second)

    def test_login_only_on_explicit_path_and_authenticated_name(self):
        calls = []
        def execute(command, **kwargs):
            calls.append(command)
            if command[1:3] == ['auth', 'status']:
                return subprocess.CompletedProcess(command, 1, '', '')
            if command[1:3] == ['auth', 'login']:
                return subprocess.CompletedProcess(command, 0)
            return subprocess.CompletedProcess(command, 0, 'signed-in-person\n', '')
        with patch.object(runner.subprocess, 'run', side_effect=execute):
            self.assertEqual(runner.github_identity(True), 'signed-in-person')
        self.assertEqual(sum(c[1:3] == ['auth', 'login'] for c in calls), 1)
        calls.clear()
        with patch.object(runner.subprocess, 'run', side_effect=execute), self.assertRaises(RuntimeError):
            runner.github_identity(False)
        self.assertFalse(any(c[1:3] == ['auth', 'login'] for c in calls))

    def test_configurable_bank_threshold_and_version(self):
        self.assertEqual(json.loads((ROOT/'data/runner-release.json').read_text())['version'], client_audit.VERSION)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            person = {'name': 'Bank test', 'github': 'test'}
            db = runner.open_state(out, person)
            for row in (0, 128):
                task = e.make_task('c00', row)
                result = e.run_task(task)
                db.execute('INSERT INTO tasks(id,task,result) VALUES(?,?,?)',
                           (e.task_id(task), e.canonical_json(task), e.canonical_json(result)))
                db.commit()
            with contextlib.redirect_stdout(io.StringIO()):
                first = runner.write_bank(out, db, person, bank_every=1)
                second = runner.write_bank(out, db, person, bank_every=1)
            self.assertEqual(len(json.loads(first.read_text())['tasks']), 1)
            self.assertEqual(len(json.loads(second.read_text())['tasks']), 1)
            self.assertEqual(runner.bank_queue(db)['pending'], 2)
            db.close()

    def test_discovery_bank_precedes_older_negative_queue(self):
        # Deliberately synthetic hit metadata exercises queue priority only;
        # it never goes through the verifier or any real GitHub request.
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            person = {'name': 'Priority test', 'github': 'test'}
            db = runner.open_state(out, person)
            tasks = [e.make_task('c00', row) for row in (0, 128, 256)]
            for index, task in enumerate(tasks):
                result = e.run_task(task)
                if index == 2:
                    result['hits'] = [{'xyz': ['1', '2', '3'], 'synthetic_fixture': True}]
                db.execute('INSERT INTO tasks(id,task,result) VALUES(?,?,?)',
                           (e.task_id(task), e.canonical_json(task), e.canonical_json(result)))
            db.commit()
            with contextlib.redirect_stdout(io.StringIO()):
                old = runner.write_bank(out, db, person, bank_every=1)
                priority = runner.write_bank(out, db, person, priority_id=e.task_id(tasks[2]))
            self.assertNotEqual(old, priority)
            bank = json.loads(priority.read_text())
            self.assertEqual(len(bank['tasks']), 1)
            self.assertEqual(bank['tasks'][0]['task'], tasks[2])
            posted = []
            def fake_run(command, **kwargs):
                if command[2] == 'list':
                    return subprocess.CompletedProcess(command, 0, '[]', '')
                posted.append(json.loads(kwargs['input'])['body'])
                return subprocess.CompletedProcess(command, 0, 'HTTP/2.0 201 Created\nContent-Type: application/json\n\n{"html_url":"https://github.com/example/test/issues/1"}', '')
            with patch.object(runner.subprocess, 'run', side_effect=fake_run), contextlib.redirect_stdout(io.StringIO()):
                runner.maybe_submit(db, 'example/test', -float('inf'))
            self.assertEqual([json.loads(body) for body in posted], [bank])
            db.close()


if __name__ == '__main__':
    unittest.main()
