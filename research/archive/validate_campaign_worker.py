#!/usr/bin/env python3
"""Exact regression tests for the deterministic worker; no discovery claim.

Known curves are supplied to the worker. Correctness tests do not measure the
probability or efficiency of finding an unknown solution.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import subprocess
import time

ROOT = Path(__file__).resolve().parent


def invoke(binary, *args):
    p = subprocess.run([str(binary), *map(str, args)], text=True,
                       capture_output=True, timeout=45, check=True)
    if p.stderr.strip():
        raise AssertionError(p.stderr)
    rows = [json.loads(s) for s in p.stdout.splitlines()]
    assert rows and rows[-1]['type'] == 'stats' and rows[-1]['complete']
    pts = set()
    for row in rows[:-1]:
        assert row['type'] == 'hit'
        xyz = tuple(sorted(map(int, row['xyz'])))
        assert sum(v**3 for v in xyz) == row['k']
        assert int(row['r']) + int(row['D']) * int(row['q']) in xyz
        pts.add(xyz)
    return pts, rows[-1]


def exact_interval(k, d, r, lo, hi):
    eps = (k // 3) % 3
    s = d if d % 3 == 2 * eps % 3 else -d
    out = set()
    for q in range(lo, hi + 1):
        z = r + d * q
        a, rem = divmod(4 * (k - z**3) - s**3, 3 * s)
        if rem or a < 0:
            continue
        v = math.isqrt(a)
        if v * v != a or (s + v) % 2:
            continue
        x, y = (s + v) // 2, (s - v) // 2
        if abs(z) <= min(abs(x), abs(y)):
            out.add(tuple(sorted((x, y, z))))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--binary', type=Path, default=ROOT / 'bin/campaign_worker')
    p.add_argument('--quick', action='store_true')
    p.add_argument('--output', type=Path, default=ROOT / 'runs/campaign-worker-validation.json')
    args = p.parse_args()
    begun = time.monotonic()
    cases = json.loads((ROOT / 'data/known-curves.json').read_text())['cases']
    cases.append(dict(k=3, xyz=sorted([569936821221962380720,
                  -569936821113563493509, -472715493453327032]),
                  d=108398887211, r=21397363547, R=5000000))
    if args.quick:
        cases = cases[::31] + [cases[-1]]
    source = f'read("{ROOT / "norm_search.gp"}");\n'
    for i, c in enumerate(cases):
        source += f'print("CASE ",[{i},curve_points({c["k"]},{c["d"]},{c["r"]},{c["R"]},0,0)]);\n'
    p = subprocess.run([str(ROOT / 'bin/gp'), '-q', '-f'], input=source+'\nquit;\n',
                       capture_output=True, text=True, check=True, timeout=60)
    assert not p.stderr.strip(), p.stderr
    refs = {}
    for line in p.stdout.splitlines():
        if line.startswith('CASE '):
            i, pts = json.loads(line[5:])
            refs[i] = {tuple(x) for x in pts}
    assert len(refs) == len(cases)
    for i, c in enumerate(cases):
        pts, _ = invoke(args.binary, 'curve', c['k'], c['d'], c['r'], c['R'], 'fixed')
        assert tuple(c['xyz']) in pts, (i, c)
        assert pts == refs[i], ('GP set mismatch', i, pts, refs[i])
    small_cases = 0
    for k in (3, 6, 12, 15, 21, 30, 39, 114):
        for d in range(2, 35 if args.quick else 81):
            if d % 3 == 0:
                continue
            for r in range(d):
                if r**3 % d != k % d:
                    continue
                expected = exact_interval(k, d, r, -40, 40)
                pts, _ = invoke(args.binary, 'interval', k, d, r, -40, 40, 'adaptive')
                assert pts == expected, ('Integer interval mismatch', k, d, r, pts, expected)
                small_cases += 1
    # Endpoint is independently computed from the known large k=3 solution.
    z, d, r = -472715493453327032, 108398887211, 21397363547
    q = (z-r)//d
    assert r+d*q == z
    pts, _ = invoke(args.binary, 'interval', 3, d, r, q, q, 'fixed')
    assert tuple(cases[-1]['xyz']) in pts
    for t in (q-1, q+1):
        pts, _ = invoke(args.binary, 'interval', 3, d, r, t, t, 'fixed')
        assert tuple(cases[-1]['xyz']) not in pts
    fields = ['candidates', 'curves', 'quotient_points', 'exact_tests', 'hits',
              'zero_norm', 'invalid_d', 'unsupported_D', 'noninvertible_C', 'covered', 'symmetry_rejected']
    tiling = []
    for ell, radius in ((1, 50000), (5, 85499), (25, 146201)):
        _, whole = invoke(args.binary, 'tile', ell, radius, 23456, 200000, 128, 'fixed')
        _, a = invoke(args.binary, 'tile', ell, radius, 23456, 70000, 128, 'adaptive')
        _, b = invoke(args.binary, 'tile', ell, radius, 93456, 130000, 128, 'fixed')
        assert a['end'] == b['start'] and whole['end'] == b['end']
        for field in fields:
            assert whole[field] == a[field] + b[field], (ell, field)
        _, low = invoke(args.binary, 'tile', ell, radius, 23456, 200000, 64, 'fixed')
        _, high = invoke(args.binary, 'tile', ell, radius, 23456, 200000, 128, 'fixed', 64)
        for field in ('quotient_points', 'exact_tests', 'hits'):
            assert whole[field] == low[field] + high[field], ('Band partition', ell, field)
        _, reordered = invoke(args.binary, 'tile', ell, radius, 23456, 200000, 128,
                             '61,59,53,47,43,41,37,31,23,19,17,13,11,7,5')
        for field in fields:
            assert whole[field] == reordered[field], ('Order invariance', ell, field)
        assert math.gcd(whole['permutation_stride'], whole['total']) == 1
        tiling.append(dict(ell=ell, radius=radius, total=whole['total'],
                           exact_tests=whole['exact_tests'], quotient_points=whole['quotient_points']))
    bad_args = [
        ['tile', 2, 50000, 0, 1, 64, 'fixed'],
        ['tile', 1, 1, 27, 1, 64, 'fixed'],
        ['tile', 1, 50000, 0, 1, 64, 'fixed', 64],
        ['tile', 1, 50000, '-1', 1, 64, 'fixed'],
        ['curve', 114, 3, 0, 64, 'fixed'],
        ['curve', 114, 5, 0, 64, 'fixed'],
        ['curve', 114, 5, 4, 64, '5,7'],
        ['interval', 114, 5, 4, -20000003, 0, 'fixed'],
    ]
    for bad in bad_args:
        run = subprocess.run([str(args.binary), *map(str, bad)], capture_output=True, text=True)
        assert run.returncode == 2, (bad, run.returncode)
    _, overflow = invoke(args.binary, 'tile', 1, 1000000, 0, 10000, 64, 'adaptive')
    assert overflow['unsupported_D'] > 0
    result = dict(known_curve_cases=len(cases), gp_complete_sets_agree=True,
                  brute_force_integer_intervals=small_cases, endpoint_tests=3,
                  tiling_and_band_partition=tiling, rejected_invalid_inputs=len(bad_args),
                  overflow_guard_observed=overflow['unsupported_D'],
                  validation_scope='Worker arithmetic and finite tiling; not discovery probability',
                  seconds=time.monotonic()-begun,
                  source_sha256=hashlib.sha256((ROOT/'campaign_worker.c').read_bytes()).hexdigest(),
                  binary_sha256=hashlib.sha256(args.binary.read_bytes()).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
