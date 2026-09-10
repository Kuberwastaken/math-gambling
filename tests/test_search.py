"""Independent brute-force, arithmetic, task-boundary and receipt checks."""
import copy
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import random
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import search_core as e
import runner


class SearchTests(unittest.TestCase):
    def test_exact_positive_regressions(self):
        fixtures = [(39, [-159380, 134476, 117367]),
                    (84, [41639611, -41531726, -8241191]),
                    (30, [2220422932, -2218888517, -283059965]),
                    (75, [-435203231, 435203083, 4381159]),
                    (69, [-1213102, 261692, 1209029])]
        for k, xyz in fixtures:
            x, y, z = xyz
            # Choose the smallest-magnitude coordinate for the canonical curve.
            xyz = sorted(xyz, key=abs)
            z, x, y = xyz
            d = abs(x+y)
            r, q = z % d, z//d
            found = e.scan_curve(k, d, r, q, q)['hits']
            self.assertEqual(len(found), 1)
            self.assertEqual(sorted(map(int, found[0]['xyz'])), sorted(xyz))
            self.assertTrue(e.verify_triple(found[0]['xyz'], k))
        self.assertFalse(e.verify_triple(['1', '2', '3']))
        self.assertFalse(e.verify_triple(['-0', '1', '1'], 2))
        self.assertFalse(e.verify_triple([1, 1, 1], 3))
        self.assertFalse(e.verify_triple(['1'*129, '1', '1'], 3))

    def test_brute_small_domain(self):
        # This oracle enumerates triples directly; it does not use the norm,
        # discriminant or modular sieve to decide what constitutes a solution.
        bound = 20
        for k in (3, 6, 12, 21, 30, 39, 75, 114):
            expected = set()
            for x in range(-bound, bound+1):
                for y in range(-bound, x+1):
                    for z in range(-min(abs(x), abs(y)), min(abs(x), abs(y))+1):
                        if x**3+y**3+z**3 == k and abs(x+y) >= 2:
                            expected.add((x, y, z))
            actual = set()
            for d in range(2, 2*bound+1):
                if d % 3 == 0:
                    continue
                for r in range(d):
                    if r**3 % d != k % d:
                        continue
                    lo, hi = (-bound-r)//d, (bound-r)//d
                    fast = e.scan_curve(k, d, r, lo, hi)
                    slow = e.scan_curve(k, d, r, lo, hi, sieve=False)
                    self.assertEqual(fast['hits'], slow['hits'])
                    for hit in fast['hits']:
                        xyz = tuple(map(int, hit['xyz']))
                        if max(map(abs, xyz)) <= bound:
                            actual.add(xyz)
            self.assertEqual(expected, actual, f'k={k}')

    def test_signed_filters_prove_impossible_residues(self):
        for modulus, forbidden in [(8, [0, 4, 6]), (361, [0, 19, 76, 95, 114, 133, 171, 209, 304, 323])]:
            cubes = {z**3 % modulus for z in range(modulus)}
            for s in forbidden:
                self.assertFalse(any((114-x**3-(s-x)**3) % modulus in cubes for x in range(modulus)))

    def test_square_boundaries(self):
        for n in [0, 1, 2, 3, 10**18, 2**127, 10**60]:
            for delta in [-1, 0, 1]:
                v = n*n+delta
                if v >= 0:
                    root = math.isqrt(v)
                    self.assertLessEqual(root*root, v)
                    self.assertGreater((root+1)**2, v)

    def test_norm_identity_and_lattice_rounding(self):
        rng = random.Random(114)
        for _ in range(1000):
            ell = rng.choice((1, 5, 25))
            b, c = rng.randrange(-6_000_000, 6_000_001), rng.randrange(-6_000_000, 6_000_001)
            a = e.offset_base(ell, b, c)+ell*rng.randrange(8, 8192)
            n = e.norm(a, b, c)
            B, C = 114*c*c-a*b, b*b-a*c
            self.assertEqual(B**3-114*C**3, n*(114*c**3-b**3))
            self.assertEqual(n % ell, 0)

    def test_fixed_manifest_and_digests(self):
        self.assertEqual(len(e.CONTEXTS), 81)
        for c in e.CONTEXTS:
            for row, block in [(0, 0), ((int(c['totalRows'])-1)//e.ROWS_PER_TASK*e.ROWS_PER_TASK, c['blocks']-1), (int(c['totalRows'])//7//e.ROWS_PER_TASK*e.ROWS_PER_TASK, c['blocks']//2)]:
                result = e.run_task(e.make_task(c['id'], row, block))
                core = {k: v for k, v in result.items() if k != 'digest'}
                self.assertEqual(result['digest'], hashlib.sha256(e.canonical_json(core).encode()).hexdigest())
                self.assertEqual(result['counters']['hits'], len(result['hits']))
        good = e.make_task('c00', 0)
        for key, value in [('row', '-1'), ('row', '1'), ('row', '01'), ('row', '9'*16), ('row', e.CONTEXTS[0]['totalRows']), ('version', True), ('block', True), ('block', -1), ('block', 2), ('context', 'c81'), ('engine', 'unknown')]:
            task = copy.deepcopy(good); task[key] = value
            with self.assertRaises(ValueError):
                e.run_task(task)
        with self.assertRaises(ValueError):
            e.run_task({**good, 'k': 3})

    def test_bank_size_checkpoint_and_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            person = {'name': 'Test contributor', 'github': 'test-user'}
            db = runner.open_state(out, person)
            # Empty-shell tasks are still real deterministic completed tasks.
            for index in range(256):
                task = e.make_task('c00', index*e.ROWS_PER_TASK)
                result = e.run_task(task)
                db.execute('INSERT INTO tasks(id,task,result) VALUES(?,?,?)',
                           (result['id'], e.canonical_json(task), e.canonical_json(result)))
            db.commit()
            with contextlib.redirect_stdout(io.StringIO()):
                bank = runner.write_bank(out, db, person)
            self.assertLessEqual(bank.stat().st_size, 60000)
            body = json.loads(bank.read_text())
            self.assertEqual(len(body['tasks']), 256)
            self.assertEqual(body['schema'], 'math-gambling-bank-v1')
            self.assertIsNone(runner.write_bank(out, db, person, force=True))
            db.close()
            db = runner.open_state(out, person)
            self.assertEqual(db.execute('SELECT count(*) FROM tasks WHERE result IS NOT NULL').fetchone()[0], 256)
            self.assertEqual(db.execute('SELECT count(*) FROM banks WHERE submitted IS NULL').fetchone()[0], 1)
            db.close()

    def test_gh_submission_prefix_body_match_and_idempotency(self):
        import ingest
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            person = {'name': 'Test contributor', 'github': 'test-user'}
            db = runner.open_state(out, person)
            task = e.make_task('c00', 0)
            result = e.run_task(task)
            db.execute('INSERT INTO tasks(id,task,result) VALUES(?,?,?)',
                       (result['id'], e.canonical_json(task), e.canonical_json(result)))
            db.commit()
            with contextlib.redirect_stdout(io.StringIO()):
                bank = runner.write_bank(out, db, person, force=True)
            calls = []
            def fake_run(command, **kwargs):
                calls.append(command)
                if command[2] == 'list':
                    return subprocess.CompletedProcess(command, 0, '[]', '')
                return subprocess.CompletedProcess(command, 0,
                    'https://github.com/Kuberwastaken/math-gambling/issues/123\n', '')
            with patch.object(runner.subprocess, 'run', side_effect=fake_run), contextlib.redirect_stdout(io.StringIO()):
                attempt = runner.maybe_submit(db, 'Kuberwastaken/math-gambling', -math.inf)
                runner.maybe_submit(db, 'Kuberwastaken/math-gambling', -math.inf)
            self.assertEqual(len(calls), 2)
            title = calls[1][calls[1].index('--title')+1]
            self.assertTrue(title.startswith('[bank]'))
            parsed = ingest.parse_issue(dict(number=123, title=title,
                body=bank.read_text(), user={'login': 'test-user'}, updated_at='2026-09-10T00:00:00Z'), 'Kuberwastaken/math-gambling')
            self.assertIsNotNone(parsed)
            self.assertEqual(parsed[0], json.loads(bank.read_text()))
            self.assertEqual(parsed[1]['submitter'], 'test-user')
            # A matching title with a different body is not the same bank.
            db.execute('UPDATE banks SET submitted=NULL'); db.commit(); calls.clear()
            def impostor_run(command, **kwargs):
                calls.append(command)
                if command[2] == 'list':
                    return subprocess.CompletedProcess(command, 0,
                        json.dumps([dict(title=title, body='{}', url='https://github.com/Kuberwastaken/math-gambling/issues/999')]), '')
                return subprocess.CompletedProcess(command, 0,
                    'https://github.com/Kuberwastaken/math-gambling/issues/124\n', '')
            with patch.object(runner.subprocess, 'run', side_effect=impostor_run), contextlib.redirect_stdout(io.StringIO()):
                runner.maybe_submit(db, 'Kuberwastaken/math-gambling', -math.inf)
            self.assertEqual(len(calls), 2)
            # Confirmed matching content avoids the create call after a resume.
            db.execute('UPDATE banks SET submitted=NULL'); db.commit(); calls.clear()
            def existing_run(command, **kwargs):
                calls.append(command)
                return subprocess.CompletedProcess(command, 0,
                    json.dumps([dict(title=title, body=bank.read_text(), url='https://github.com/Kuberwastaken/math-gambling/issues/124')]), '')
            with patch.object(runner.subprocess, 'run', side_effect=existing_run), contextlib.redirect_stdout(io.StringIO()):
                runner.maybe_submit(db, 'Kuberwastaken/math-gambling', -math.inf)
            self.assertEqual(len(calls), 1)
            # Timeout after dispatch is uncertain, retained and never blindly
            # retried by the automatic path (it may have created the issue).
            db.execute('UPDATE banks SET submitted=NULL'); db.commit(); calls.clear()
            def timeout_run(command, **kwargs):
                calls.append(command)
                if command[2] == 'list':
                    return subprocess.CompletedProcess(command, 0, '[]', '')
                raise subprocess.TimeoutExpired(command, 30)
            with patch.object(runner.subprocess, 'run', side_effect=timeout_run), contextlib.redirect_stderr(io.StringIO()):
                runner.maybe_submit(db, 'Kuberwastaken/math-gambling', -math.inf)
                runner.maybe_submit(db, 'Kuberwastaken/math-gambling', -math.inf)
            self.assertEqual(len(calls), 2)
            self.assertTrue(db.execute('SELECT submitted FROM banks').fetchone()[0].startswith('uncertain;'))
            self.assertTrue(bank.exists())
            db.close()


if __name__ == '__main__':
    unittest.main()
