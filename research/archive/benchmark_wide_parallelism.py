#!/usr/bin/env python3
"""Compare identical workloads at 4/8/12/all logical CPUs; no new coverage."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import os
import random
import statistics
import time
import benchmark_campaign_performance as bench

ROOT = Path(__file__).resolve().parent


def main():
    old = json.loads((ROOT/'runs/campaign-performance.json').read_text())
    status = json.loads((ROOT/'runs/campaign/status.json').read_text())
    if status['state'] not in ('stopped', 'session_complete'):
        raise RuntimeError('Stop production cleanly before measuring scaling')
    identity = bench.hashes()
    levels = sorted(set(min(n, os.cpu_count() or 1) for n in (4, 8, 12, 15)))
    rng = random.Random(1141508)
    references = {r['context']['key']: bench.fingerprint(r['stats'], r['hits'])
                  for r in old['paired_rows']}
    result = dict(calibration_only=True, counts_are_new_coverage=False,
                  hardware=bench.hardware(), levels=levels, runs=[], complete=False,
                  source_and_binary_sha256=identity)
    began = time.monotonic()
    cpu_start = bench.cpu_seconds()
    output = ROOT/'runs/wide-parallelism.json'
    for repeat in range(3):
        order = levels.copy()
        rng.shuffle(order)
        for workers in order:
            if time.monotonic()-began > 60 or bench.cpu_seconds()-cpu_start > 100:
                raise RuntimeError('Bounded scaling calibration exceeded admission budget')
            workload = bench.contexts()*4
            rng.shuffle(workload)
            before = time.perf_counter()
            before_cpu = bench.cpu_seconds()
            with ThreadPoolExecutor(max_workers=workers) as pool:
                pending = [pool.submit(bench.one, c,
                    old['generator_counts_by_context'][c['key']],
                    old['policy_comparison'][c['key']]['selected'],
                    'wide_scaling', repeat, old['configuration']['seed'], 10)
                    for c in workload]
                rows = [f.result() for f in pending]
            elapsed = time.perf_counter()-before
            for row in rows:
                assert bench.fingerprint(row['stats'], row['hits']) == references[row['context']['key']]
            result['runs'].append(dict(workers=workers, repeat=repeat,
                elapsed_seconds=elapsed, cpu_seconds=bench.cpu_seconds()-before_cpu,
                checked_tiles=len(rows), all_fingerprints_match=True,
                generator_inputs=sum(r['count'] for r in rows),
                curve_checks=sum(r['stats']['curves'] for r in rows)))
            output.write_text(json.dumps(result, indent=2)+'\n')
    assert bench.hashes() == identity
    medians = {n: statistics.median(r['elapsed_seconds'] for r in result['runs']
                                   if r['workers']==n) for n in levels}
    fastest = min(medians, key=medians.get)
    # Avoid extra workers for a negligible gain: smallest count within 5% of best.
    chosen = min(n for n in levels if medians[n] <= medians[fastest]*1.05)
    result.update(complete=True, median_seconds=medians, recommended_workers=chosen,
                  selection_rule='Smallest worker count within 5% of fastest measured throughput',
                  speedup_over_four=medians[levels[0]]/medians[chosen],
                  cpu_seconds=bench.cpu_seconds()-cpu_start,
                  wall_seconds=time.monotonic()-began,
                  caution='Short matched timings do not establish sustained thermal or battery performance.')
    output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('complete','median_seconds','recommended_workers',
                      'speedup_over_four','cpu_seconds','wall_seconds')}, indent=2))


if __name__ == '__main__':
    main()
