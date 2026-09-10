#!/usr/bin/env python3
"""Independent, bounded differential validation and paired timing for phase3.

Never launches a campaign. Repeated timing inputs are calibration, not coverage.
Trace builds are temporary, leaving frozen phase2 and production binaries intact.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import argparse
import hashlib
import json
import math
import os
import platform
import random
import sqlite3
import statistics
import subprocess
import tempfile
import time
import traceback

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent
PROJECT = LAB.parent.parent
OLD = LAB / 'phase2'
HEADERS = PROJECT / 'work/pari-include'
DREF = 10**19 // 54
DEN, ALPHA, ALPHA2 = 10**18, 4848807585839879338, 23510935004498358840
PRIMES = (5, 7, 11, 13, 17, 19, 23, 31, 37, 41, 43, 47, 53, 59, 61)
BAD8 = {0, 4, 6}
BAD361 = {0, 19, 76, 95, 114, 133, 171, 209, 304, 323}
COUNTERS = ('rows', 'empty_rows', 'candidates', 'eligible_inputs', 'outside_shell',
            'rejected_signed', 'rejected_signed8', 'rejected_signed361', 'invalid_d',
            'noninvertible_C', 'unsupported_D', 'covered', 'curves', 'zero_norm',
            'symmetry_rejected', 'quotient_points', 'rejected_mod243',
            'rejected_parity', 'exact_tests', 'hits', 'reorders', 'calibration_samples')
TRACE_HEADER = r'''
#include <stdio.h>
#include <stdlib.h>
static void audit_int(__int128 x) {
  char b[48];int n=0;unsigned __int128 a=x<0?-x:x;
  do {b[n++]=(char)('0'+a%10);a/=10;} while(a);
  putchar('"');if(x<0)putchar('-');while(n)putchar(b[--n]);putchar('"');
}
static void audit_candidate(unsigned long long i,__int128 t,__int128 a,
                            __int128 b,__int128 c,__int128 d) {
  printf("{\"type\":\"candidate_trace\",\"index\":%llu,\"t\":",i);audit_int(t);
  printf(",\"a\":");audit_int(a);printf(",\"b\":");audit_int(b);
  printf(",\"c\":");audit_int(c);printf(",\"D\":");audit_int(d);puts("}");
}
static void audit_root(unsigned long long i,__int128 t,unsigned long long d,
                       unsigned long long r) {
  printf("{\"type\":\"root_trace\",\"index\":%llu,\"t\":",i);audit_int(t);
  printf(",\"D\":%llu,\"r\":%llu}\n",d,r);
}
static void audit_q(long k,__int128 s,unsigned long long d,
                    unsigned long long r,__int128 q) {
  if(!getenv("AUDIT_Q"))return;
  printf("{\"type\":\"q_trace\",\"k\":%ld,\"s\":",k);audit_int(s);
  printf(",\"D\":%llu,\"r\":%llu,\"q\":",d,r);audit_int(q);puts("}");
}
#ifdef AUDIT_CANDIDATES
#define OFFSET_TRACE_CANDIDATE(i,t,a,b,c,d) audit_candidate(i,t,a,b,c,d)
#endif
#define OFFSET_TRACE_ROOT(i,t,d,r) audit_root(i,t,d,r)
#define CAMPAIGN_TRACE_Q(q) audit_q(k,s,d,r,q)
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def base(ell, b, c):
    residue = (-4*b - 16*c) % ell
    numerator = -ALPHA*b - ALPHA2*c - residue*DEN
    return residue + ell*((2*numerator + ell*DEN)//(2*ell*DEN))


def norm(a, b, c):
    return a**3 + 114*b**3 + 12996*c**3 - 342*a*b*c


def permutation(ell, radius, seed):
    mask = 2**64-1
    def mix(v):
        v = ((v ^ (v >> 30))*0xbf58476d1ce4e5b9) & mask
        v = ((v ^ (v >> 27))*0x94d049bb133111eb) & mask
        return v ^ (v >> 31)
    total = (2*radius+1)**2
    v = mix(seed ^ mix(ell) ^ mix(radius))
    offset = v % total
    stride = mix((v+0x9e3779b97f4a7c15) & mask) % total or 1
    while math.gcd(stride, total) != 1:
        stride = (stride+1) % total or 1
    return stride, offset, total


def qbounds(d, r, low, high):
    zmin = max(10**19 if d <= DREF else 10**17, low*d)
    zmax = high*d
    if zmax <= zmin:
        return None
    if d % 3 != 1:
        lo, hi = (zmin-r)//d+1, (zmax-r)//d
    else:
        lo, hi = -((zmax+r)//d), -((zmin+r)//d)-1
    return (lo, hi) if lo <= hi else None


def tile_args(spec, start, count, policy='fixed', method='inversion', seed=114):
    return ['tile', *map(str, (spec['ell'], spec['radius'], spec['tlo'], spec['thi'],
                              spec['dlo'], spec['dhi'], start, count, spec['high'],
                              spec['low'])), policy, method, str(seed)]


def invoke(binary, args, qtrace=False, timeout=30):
    env = os.environ.copy()
    if qtrace:
        env['AUDIT_Q'] = '1'
    else:
        env.pop('AUDIT_Q', None)
    begun = time.perf_counter()
    p = subprocess.run([str(binary), *args], text=True, capture_output=True,
                       env=env, timeout=timeout)
    elapsed = time.perf_counter()-begun
    assert p.returncode == 0, (args, p.returncode, p.stderr[-3000:])
    assert not p.stderr.strip(), p.stderr[-3000:]
    records = [json.loads(line) for line in p.stdout.splitlines()]
    assert records and records[-1]['type'] == 'stats', p.stdout[-1000:]
    stats = records[-1]
    if args[0] == 'tile':
        assert stats['complete'] and stats['version'] == 2
        assert stats['candidates'] == int(args[8])*(int(args[4])-int(args[3])+1)
        assert stats['candidates'] == sum(stats[k] for k in (
            'outside_shell', 'rejected_signed', 'invalid_d', 'noninvertible_C',
            'unsupported_D', 'covered', 'curves'))
    assert stats['quotient_points'] == stats['rejected_mod243'] + stats['rejected_parity'] + stats['exact_tests'] + sum(f['rejected'] for f in stats['filters'])
    for row in records:
        if row['type'] == 'hit':
            assert sum(int(v)**3 for v in row['xyz']) == int(row['k'])
    return records, stats, elapsed


def traces(records, kind):
    keys = {'candidate_trace': ('index', 't', 'a', 'b', 'c', 'D'),
            'root_trace': ('index', 't', 'D', 'r'),
            'q_trace': ('k', 's', 'D', 'r', 'q')}[kind]
    return [tuple(int(r[k]) for k in keys) for r in records if r['type'] == kind]


def hits(records):
    return sorted((int(r['k']), tuple(sorted(map(int, r['xyz']))))
                  for r in records if r['type'] == 'hit')


def same_result(a, b, context, strict_filters=True):
    ar, sa, _ = a
    br, sb, _ = b
    for k in COUNTERS:
        if k in sa and k in sb:
            assert sa[k] == sb[k], (context, k, sa[k], sb[k])
    if strict_filters:
        for k in ('filters', 'final_order'):
            assert sa[k] == sb[k], (context, k, sa[k], sb[k])
    if 'exposure_sum' in sa:
        assert math.isclose(sa['exposure_sum'], sb['exposure_sum'], rel_tol=2e-12,
                            abs_tol=1e-12), context
    assert hits(ar) == hits(br), (context, hits(ar), hits(br))


def oracle(spec, start, count, seed):
    stride, offset, total = permutation(spec['ell'], spec['radius'], seed)
    expected_candidates, expected_roots = [], []
    counters = dict.fromkeys(('outside_shell', 'invalid_d', 'rejected_signed',
                             'rejected_signed8', 'rejected_signed361',
                             'noninvertible_C', 'covered', 'curves', 'quotient_points'), 0)
    masses = []
    checked = 0
    width, ell = 2*spec['radius']+1, spec['ell']
    for index in range(start, start+count):
        v = (index*stride+offset) % total
        b, c = v % width-spec['radius'], v//width-spec['radius']
        aa = base(ell, b, c)
        for t in range(spec['tlo'], spec['thi']+1):
            a = aa+ell*t
            n = norm(a, b, c)
            checked += 1
            assert n > 0 and n % ell == 0 and (a+4*b+16*c) % ell == 0
            d = n//ell
            if not spec['dlo'] < d <= spec['dhi']:
                counters['outside_shell'] += 1
                continue
            expected_candidates.append((index, t, a, b, c, d))
            if d < 2 or d % 3 == 0:
                counters['invalid_d'] += 1
                continue
            s = d if d % 3 == 1 else -d
            category = 'rejected_signed8' if s % 8 in BAD8 else 'rejected_signed361' if s % 361 in BAD361 else None
            if category:
                counters[category] += 1
                counters['rejected_signed'] += 1
                continue
            cc, bb = b*b-a*c, 114*c*c-a*b
            if math.gcd(cc, d) != 1:
                counters['noninvertible_C'] += 1
                continue
            r = bb*pow(cc, -1, d) % d
            assert pow(r, 3, d) == 114 % d
            expected_roots.append((index, t, d, r))
            bounds = qbounds(d, r, spec['low'], spec['high'])
            if bounds is None:
                counters['covered'] += 1
            else:
                counters['curves'] += 1
                counters['quotient_points'] += bounds[1]-bounds[0]+1
                masses.append(DREF/d)
    return expected_candidates, expected_roots, counters, math.fsum(masses), checked


def compare_oracle(result, expected, candidate=True):
    records, stats, _ = result
    ec, er, counters, mass, _ = expected
    if candidate:
        assert traces(records, 'candidate_trace') == ec
    assert traces(records, 'root_trace') == er
    for key, value in counters.items():
        assert stats[key] == value, (key, stats[key], value)
    assert math.isclose(stats['exposure_sum'], mass, rel_tol=2e-12, abs_tol=1e-9)


@lru_cache(maxsize=None)
def possible_z(k, s):
    pair = {(x**3+(s-x)**3) % 243 for x in range(243)}
    return {z for z in range(243) if (k-z**3) % 243 in pair}


def interval_oracle(k, d, r, lo, hi):
    eps = (k//3) % 3
    s = d if d % 3 == 2*eps % 3 else -d
    qs, exact_points, passed = [], [], 0
    reject243 = reject2 = 0
    for q in range(lo, hi+1):
        z = r+d*q
        if z % 243 not in possible_z(k, s % 243):
            reject243 += 1
            continue
        if (k-s-z) % 2:
            reject2 += 1
            continue
        qs.append((k, s, d, r, q))
        if any((3*s*(4*k-4*z**3-s**3)) % p not in {x*x % p for x in range(p)} for p in PRIMES):
            continue
        passed += 1
        numerator, denominator = 4*(k-z**3)-s**3, 3*s
        if numerator % denominator:
            continue
        square = numerator//denominator
        if square < 0:
            continue
        v = math.isqrt(square)
        if v*v != square or (s+v) % 2:
            continue
        x, y = (s+v)//2, (s-v)//2
        if abs(z) <= min(abs(x), abs(y)):
            assert x**3+y**3+z**3 == k
            exact_points.append((k, tuple(sorted((x, y, z)))))
    return qs, sorted(exact_points), reject243, reject2, passed


def compile_trace(directory, source, name, candidates):
    binary = directory/name
    args = ['clang', '-O1', '-fsanitize=undefined', '-fno-sanitize-recover=all',
            '-include', str(directory/'trace.h'), '-I', str(HEADERS)]
    if candidates:
        args.append('-DAUDIT_CANDIDATES=1')
    args += [str(source), '-L', str(LAB/'bin'), '-lpari', '-o', str(binary)]
    p = subprocess.run(args, capture_output=True, text=True, check=True, timeout=60)
    return binary


def validation(result):
    specs = json.loads((OLD/'runs/context-specs.json').read_text())
    assert len(specs) == 81
    old_bin, new_bin = OLD/'bin/offset_worker', ROOT/'bin/offset_worker'
    rng = random.Random(114303)
    checks, roots, eligible = 0, 0, 0
    with tempfile.TemporaryDirectory(prefix='phase3-validation-', dir=PROJECT/'work') as tmp:
        tmp = Path(tmp)
        (tmp/'libpari.dylib').symlink_to(LAB/'bin/libpari.dylib')
        (tmp/'trace.h').write_text(TRACE_HEADER)
        old_trace = compile_trace(tmp, OLD/'offset_worker.c', 'old-trace', True)
        new_trace = compile_trace(tmp, ROOT/'offset_worker.c', 'new-trace', True)
        # Candidate hook disables row skipping; ROOT-only build exercises it.
        new_optimized = compile_trace(tmp, ROOT/'offset_worker.c', 'new-optimized-trace', False)
        geometry_records = []
        for i, spec in enumerate(specs):
            start, seed = 777+37*i, 114 if i % 2 else 2**64-1-i
            args = tile_args(spec, start, 1, seed=seed)
            expected = oracle(spec, start, 1, seed)
            old = invoke(old_trace, args)
            new = invoke(new_trace, args)
            fast = invoke(new_optimized, args)
            for sample in (old, new):
                compare_oracle(sample, expected)
            compare_oracle(fast, expected, candidate=False)
            same_result(old, new, spec['key'])
            same_result(old, fast, spec['key'])
            checks += expected[-1]
            roots += len(expected[1])
            eligible += len(expected[0])
            # The ordinary binaries, in both policies, cover a larger interval.
            native_results = {}
            for policy in ('fixed', 'adaptive'):
                a = tile_args(spec, start+5, 12, policy=policy, seed=seed)
                old_native, new_native = invoke(old_bin, a), invoke(new_bin, a)
                same_result(old_native, new_native, (spec['key'], policy))
                native_results[policy] = new_native[1]
            geometry_records.append(dict(key=spec['key'], start=start, seed=seed,
                                         oracle_inputs=expected[-1], roots=len(expected[1]),
                                         native_quotients=native_results['fixed']['quotient_points']))
        # Full tiny domains plus exact shell endpoints, without frontier timing.
        endpoint_count = 0
        for ell in (1, 5, 25):
            for radius in (2, 5):
                spec = dict(ell=ell, radius=radius, tlo=8, thi=12,
                            dlo=0, dhi=2**63-1, low=0, high=64)
                count = (2*radius+1)**2
                expected = oracle(spec, 0, count, 114)
                old = invoke(old_trace, tile_args(spec, 0, count, method='probe'))
                new = invoke(new_trace, tile_args(spec, 0, count, method='probe'))
                compare_oracle(old, expected)
                compare_oracle(new, expected)
                same_result(old, new, ('tiny', ell, radius))
                checks += expected[-1]
                for _ in range(3):
                    b, c, t = rng.randint(-radius, radius), rng.randint(-radius, radius), rng.randint(8, 12)
                    d = norm(base(ell, b, c)+ell*t, b, c)//ell
                    for dlo, dhi, expected_inside in ((d, d+1, False), (max(0, d-1), d, True)):
                        es = dict(spec, dlo=dlo, dhi=dhi)
                        a = tile_args(es, 0, count, method='probe')
                        samples = [invoke(binary, a) for binary in (old_trace, new_trace)]
                        same_result(*samples, context=('endpoint', ell, b, c, t, dlo, dhi))
                        for sample in samples:
                            selected = [r for r in traces(sample[0], 'candidate_trace') if r[1:5] == (t, base(ell, b, c)+ell*t, b, c)]
                            assert bool(selected) == expected_inside
                        endpoint_count += 1
        # Tile splits and q-band additivity, including both signs of S.
        partitions = []
        for ell in (1, 5, 25):
            spec = next(s for s in specs if s['ell'] == ell and s['shape_index'] == 1 and s['shell_index'] == 0 and s['band_index'] == 1)
            combined = dict(spec, low=0, high=4096)
            whole = invoke(new_bin, tile_args(combined, 931, 48))
            left = invoke(new_bin, tile_args(combined, 931, 19))
            right = invoke(new_bin, tile_args(combined, 950, 29))
            additive = ('candidates', 'eligible_inputs', 'outside_shell', 'rejected_signed',
                        'invalid_d', 'noninvertible_C', 'covered', 'curves',
                        'quotient_points', 'rejected_mod243', 'rejected_parity', 'exact_tests', 'hits')
            for key in additive:
                assert whole[1][key] == left[1][key]+right[1][key], ('partition', key)
            bands = [invoke(new_bin, tile_args(dict(spec, low=lo, high=hi), 931, 48))
                     for lo, hi in ((0, 64), (64, 256), (256, 4096))]
            for key in ('quotient_points', 'rejected_mod243', 'rejected_parity', 'exact_tests', 'hits'):
                assert whole[1][key] == sum(b[1][key] for b in bands), ('qband', key)
            partitions.append(dict(ell=ell, quotients=whole[1]['quotient_points']))
        # Exact known positives: singleton quotient intervals avoid expensive scans.
        known = json.loads((LAB/'data/known-curves.json').read_text())['cases']
        chosen = [known[i] for i in sorted({0, len(known)-1, *range(0, len(known), max(1, len(known)//16))})]
        chosen.append(dict(k=3, xyz=[569936821221962380720, -569936821113563493509, -472715493453327032], d=108398887211, r=21397363547))
        interval_cases = []
        for c in chosen:
            k, d, r = (int(c[x]) for x in ('k', 'd', 'r'))
            z = min(map(int, c['xyz']), key=abs)
            assert (z-r) % d == 0 and sum(int(v)**3 for v in c['xyz']) == k
            q = (z-r)//d
            interval_cases.append((k, d, r, q, q, tuple(sorted(map(int, c['xyz'])))))
        # Mod243 / parity periods, wheel1024 boundary, and int64 edges.
        interval_cases += [(114, d, r, lo, hi, None) for d, r in ((5, 4), (10, 4), (19, 0), (38, 0))
                           for lo, hi in ((-1025, -2), (-486, 486), (-2, 1022),
                                          (0, 0), (2**63-1026, 2**63-2),
                                          (-(2**63-1), -(2**63-1)+1024))]
        qvisited, exact_checks = 0, 0
        for k, d, r, lo, hi, positive in interval_cases:
            expected = interval_oracle(k, d, r, lo, hi)
            baseline = None
            for policy in ('direct:fixed', 'wheel:fixed', 'direct:adaptive', 'wheel:adaptive'):
                args = ['interval', *map(str, (k, d, r, lo, hi)), policy]
                old = invoke(old_trace, args, qtrace=True)
                new = invoke(new_optimized, args, qtrace=True)
                same_result(old, new, ('interval', k, d, lo, hi, policy))
                assert traces(old[0], 'q_trace') == traces(new[0], 'q_trace')
                assert sorted(traces(new[0], 'q_trace')) == expected[0]
                assert hits(new[0]) == expected[1]
                for key, val in zip(('rejected_mod243', 'rejected_parity', 'exact_tests'), expected[2:]):
                    assert new[1][key] == val, (key, new[1][key], val)
                if positive:
                    assert (k, positive) in hits(new[0])
                if baseline is not None:
                    # Sieve stage ordering can differ across direct/wheel engines.
                    assert hits(new[0]) == hits(baseline[0])
                    assert new[1]['exact_tests'] == baseline[1]['exact_tests']
                baseline = new
            qvisited += len(expected[0])
            exact_checks += expected[-1]
        # Empty CLI intervals are invalid, rather than successful zero-work jobs.
        for binary in (old_bin, new_bin):
            p = subprocess.run([str(binary), 'interval', '114', '5', '4', '1', '0', 'fixed'], capture_output=True, text=True)
            assert p.returncode == 2 and 'Invalid curve parameters' in p.stderr
        result['correctness'] = dict(status='passed', all_geometry_strata=81,
            fixed_and_adaptive_native_pairs=162, candidate_oracle_checks=checks,
            candidate_traces_compared=eligible, optimized_root_traces_compared=roots,
            full_small_domains=6, shell_endpoint_cases=endpoint_count,
            partition_and_qband_tests=partitions, interval_cases=len(interval_cases),
            known_positive_fixtures=len(chosen), independent_q_visits=qvisited,
            independent_exact_survivors=exact_checks, empty_intervals_rejected=True, ubsan=True,
            trace_note='Candidate trace builds disable row skipping; ROOT-only UBSan build separately exercises optimized skipping.',
            geometry_records=geometry_records)


def performance(result, budget_seconds):
    specs = json.loads((OLD/'runs/context-specs.json').read_text())
    old_bin, new_bin = OLD/'bin/offset_worker', ROOT/'bin/offset_worker'
    rng = random.Random(1143303)
    begun = time.perf_counter()
    records = []
    # Nine geometry/band combinations, both fixed/adaptive, same inputs per pair.
    selected = [s for s in specs if s['ell'] == 5 and s['shell_index'] == 0]
    pilots = {}
    warmups = []
    for s in selected:
        a = tile_args(s, 12345, 256, policy='adaptive')
        sample = invoke(old_bin, a)
        new_sample = invoke(new_bin, a)
        same_result(sample, new_sample, ('warmup', s['key']))
        count = max(128, min(32768, int(256*0.06/max(sample[2], 0.001))))
        pilots[s['key']] = count
        warmups.append(dict(key=s['key'], rows=256, selected_rows=count,
                            phase2_elapsed=sample[2], phase3_elapsed=new_sample[2]))
    jobs = [(s, p, repeat) for repeat in range(3) for s in selected for p in ('fixed', 'adaptive')]
    rng.shuffle(jobs)
    for s, policy, repeat in jobs:
        if time.perf_counter()-begun > budget_seconds*0.65:
            break
        count = pilots[s['key']]
        a = tile_args(s, 12345+repeat*50000, count, policy=policy)
        order = [('phase2', old_bin), ('phase3', new_bin)]
        rng.shuffle(order)
        pair = {}
        for name, binary in order:
            pair[name] = invoke(binary, a)
        same_result(pair['phase2'], pair['phase3'], ('benchmark', s['key'], policy, repeat))
        records.append(dict(key=s['key'], policy=policy, repeat=repeat, rows=count,
            start=int(a[7]), order=[name for name, _ in order],
            phase2_elapsed=pair['phase2'][2], phase3_elapsed=pair['phase3'][2],
            phase2_cpu=pair['phase2'][1]['cpu_seconds'], phase3_cpu=pair['phase3'][1]['cpu_seconds'],
            phase2_internal_wall=pair['phase2'][1]['wall_seconds'], phase3_internal_wall=pair['phase3'][1]['wall_seconds'],
            curves=pair['phase3'][1]['curves'], quotient_points=pair['phase3'][1]['quotient_points'],
            exposure=pair['phase3'][1]['exposure_sum'], hits=pair['phase3'][1]['hits']))
    scaling = []
    # Same12-job workload for1/12 workers and old/new; bounds remain finite.
    contexts = [specs[i] for i in (0, 2, 9, 11, 18, 20, 27, 38, 47, 54, 65, 74)]
    task_args = []
    for i, s in enumerate(contexts):
        representative = next(t for t in selected if t['shape_index'] == s['shape_index'] and t['band_index'] == s['band_index'])
        rows = min(131072, pilots[representative['key']]*4)
        task_args.append(tile_args(s, 234567+i*10000, rows, policy='adaptive'))
    batches = [(name, binary, workers, rep) for rep in range(2)
               for workers in (1, 12) for name, binary in (('phase2', old_bin), ('phase3', new_bin))]
    rng.shuffle(batches)
    reference = None
    for name, binary, workers, rep in batches:
        if time.perf_counter()-begun > budget_seconds:
            break
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            data = list(pool.map(lambda a: invoke(binary, a), task_args))
        elapsed = time.perf_counter()-start
        if reference is None:
            reference = data
        else:
            for i, (a, b) in enumerate(zip(reference, data)):
                same_result(a, b, ('scaling', name, workers, rep, i))
        scaling.append(dict(version=name, workers=workers, repeat=rep,
                            wall_seconds=elapsed, cpu_seconds=sum(d[1]['cpu_seconds'] for d in data),
                            processes=len(data), rows=sum(int(a[8]) for a in task_args),
                            quotient_points=sum(d[1]['quotient_points'] for d in data)))
    grouped = {}
    for row in records:
        key = row['key']+'|'+row['policy']
        group = grouped.setdefault(key, [])
        group.append(row)
    ratios = {key:dict(pairs=len(rows), external_speed_ratio=sum(r['phase2_elapsed'] for r in rows)/sum(r['phase3_elapsed'] for r in rows),
                       cpu_speed_ratio=sum(r['phase2_cpu'] for r in rows)/sum(r['phase3_cpu'] for r in rows))
              for key, rows in grouped.items()}
    scale_summary = {}
    for name in ('phase2', 'phase3'):
        for workers in (1, 12):
            values = [r['wall_seconds'] for r in scaling if r['version'] == name and r['workers'] == workers]
            if values:
                scale_summary[f'{name}_{workers}'] = dict(repeats=len(values), median_wall_seconds=statistics.median(values))
    if len(scale_summary) == 4:
        for workers in (1, 12):
            scale_summary[f'phase3_vs_phase2_{workers}'] = scale_summary[f'phase2_{workers}']['median_wall_seconds']/scale_summary[f'phase3_{workers}']['median_wall_seconds']
        for name in ('phase2', 'phase3'):
            scale_summary[f'{name}_12_vs_1'] = scale_summary[f'{name}_1']['median_wall_seconds']/scale_summary[f'{name}_12']['median_wall_seconds']
    result['performance'] = dict(scope='Repeated matched-input calibration only; no new coverage or discovery enrichment.',
        elapsed_seconds=time.perf_counter()-begun, budget_seconds=budget_seconds,
        warmup_records=warmups,
        paired_records=records, context_ratios=ratios, scaling_records=scaling,
        scaling_summary=scale_summary, complete_54_pairs=len(records)==54,
        complete_scaling=len(scaling)==8)


def actual_allocation(result, database, budget_seconds):
    """Replay the last12 completed job IDs exactly; never select by speedup."""
    begun = time.perf_counter()
    rng = random.Random(1142)
    db = sqlite3.connect(database.resolve().as_uri()+'?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    jobs = [dict(row) for row in db.execute(
        "SELECT * FROM jobs WHERE status='complete' ORDER BY id DESC LIMIT 12")]
    db.close()
    assert len(jobs) == 12 and all(j['strategy'] != 'bootstrap' for j in jobs)
    tasks, historical = [], []
    for job in jobs:
        stats = json.loads(job['stats'])
        assert stats['permutation_seed'] == 1142 and stats['policy'] == 'adaptive'
        spec = dict(ell=stats['ell'], radius=stats['radius'], tlo=stats['tlo'], thi=stats['thi'],
                    dlo=stats['Dlo'], dhi=stats['Dhi'], low=stats['min_ratio'], high=stats['ratio'])
        tasks.append(tile_args(spec, job['start'], job['count'], policy='adaptive', seed=1142))
        historical.append(([], stats, job['elapsed']))
    bins = {'phase2': OLD/'bin/offset_worker', 'phase3': ROOT/'bin/offset_worker'}
    pair_orders = [('phase2', 'phase3')]*3 + [('phase3', 'phase2')]*3
    rng.shuffle(pair_orders)
    pairs = []
    for number, order in enumerate(pair_orders):
        if time.perf_counter()-begun > budget_seconds:
            break
        ids = list(range(12))
        rng.shuffle(ids)
        pair = {}
        for name in order:
            start = time.perf_counter()
            remaining = budget_seconds-(start-begun)
            assert remaining > 0, 'Actual-allocation calibration exhausted its wall-time budget.'
            with ThreadPoolExecutor(max_workers=12) as pool:
                by_index = list(pool.map(lambda i: (i, invoke(bins[name], tasks[i], timeout=remaining)), ids))
            wall = time.perf_counter()-start
            data = [None]*12
            for i, value in by_index:
                data[i] = value
                same_result(historical[i], value, ('actual-historical', name, number, jobs[i]['id']))
            pair[name] = dict(wall_seconds=wall, native_cpu_seconds=sum(r[1]['cpu_seconds'] for r in data),
                              native_wall_seconds=sum(r[1]['wall_seconds'] for r in data),
                              subprocess_elapsed_sum=sum(r[2] for r in data),
                              job_timings=[dict(job_id=jobs[i]['id'], subprocess_elapsed=r[2],
                                               native_wall_seconds=r[1]['wall_seconds'],
                                               native_cpu_seconds=r[1]['cpu_seconds']) for i, r in enumerate(data)])
        pair['pair'] = number
        pair['order'] = list(order)
        pair['job_order'] = [jobs[i]['id'] for i in ids]
        pair['speed_ratio'] = pair['phase2']['wall_seconds']/pair['phase3']['wall_seconds']
        pairs.append(pair)
    result['actual_allocation'] = dict(
        scope='Exact replay of latest12 completed phase2 job IDs; calibration only, zero new-coverage credit.',
        database=str(database), selection_query="SELECT * FROM jobs WHERE status='complete' ORDER BY id DESC LIMIT 12",
        selection_not_conditioned_on_benchmark_results=True, workers=12, seed=1142,
        budget_seconds=budget_seconds, elapsed_seconds=time.perf_counter()-begun,
        complete_six_pairs=len(pairs)==6, jobs=[dict(id=j['id'], context=j['context'],
            start=j['start'], count=j['count'], strategy=j['strategy'], elapsed=j['elapsed'],
            stats=json.loads(j['stats'])) for j in jobs], pairs=pairs,
        ratio_total_elapsed=sum(p['phase2']['wall_seconds'] for p in pairs)/sum(p['phase3']['wall_seconds'] for p in pairs),
        median_pair_speed_ratio=statistics.median(p['speed_ratio'] for p in pairs),
        ratio_total_native_cpu=sum(p['phase2']['native_cpu_seconds'] for p in pairs)/sum(p['phase3']['native_cpu_seconds'] for p in pairs),
        every_mathematical_counter_matches_original_ledger=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=PROJECT/'work/phase3-benchmark-validation.json')
    parser.add_argument('--skip-performance', action='store_true')
    parser.add_argument('--correctness-json', type=Path,
                        help='Reuse a passed correctness artifact only when all native hashes match.')
    parser.add_argument('--benchmark-seconds', type=float, default=45)
    parser.add_argument('--actual-allocation', type=Path,
                        help='Replay last12 completed jobs from this read-only SQLite ledger instead of synthetic timing.')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    begun = time.perf_counter()
    files = [OLD/'offset_worker.c', OLD/'bin/offset_worker', LAB/'campaign_worker.c',
             ROOT/'offset_worker.c', ROOT/'checker.c', ROOT/'bin/offset_worker']
    before = {str(p): sha(p) for p in files}
    result = dict(status='running', scope='Independent differential finite-domain audit and calibration',
                  machine=dict(system=platform.platform(), machine=platform.machine(),
                               logical_cpus=os.cpu_count(), python=platform.python_version()),
                  source_and_binary_sha256=before)
    try:
        if args.correctness_json:
            prior = json.loads(args.correctness_json.read_text())
            assert prior['status'] == 'passed' and prior['correctness']['status'] == 'passed'
            assert prior['source_and_binary_sha256'] == before, 'Native hashes changed since correctness validation.'
            result['correctness'] = prior['correctness']
            result['reused_correctness_artifact'] = dict(path=str(args.correctness_json), sha256=sha(args.correctness_json))
        else:
            validation(result)
        print(json.dumps({'phase': 'correctness', 'status': 'passed'}), flush=True)
        if args.actual_allocation:
            actual_allocation(result, args.actual_allocation, args.benchmark_seconds)
        elif not args.skip_performance:
            performance(result, args.benchmark_seconds)
        after = {str(p): sha(p) for p in files}
        assert before == after, 'Source or executable changed during validation; rerun after freeze.'
        result['status'] = 'passed'
        result['freeze_hashes_unchanged'] = True
    except BaseException as exc:
        result['status'] = 'failed'
        result['error'] = repr(exc)
        result['traceback'] = traceback.format_exc()
        raise
    finally:
        result['elapsed_seconds'] = time.perf_counter()-begun
        args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'status': result['status'], 'output': str(args.output),
                      'elapsed_seconds': result['elapsed_seconds'],
                      'scaling': result.get('performance', {}).get('scaling_summary', {}),
                      'actual_allocation_ratio': result.get('actual_allocation', {}).get('ratio_total_elapsed')}, indent=2))


if __name__ == '__main__':
    main()
