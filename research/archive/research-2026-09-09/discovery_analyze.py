#!/usr/bin/env python3
"""Read-only outcome analysis; never launches a search or changes its policy.

The common CPU-prefix analysis was added after observing attempt-cap censoring.
It is a sensitivity check, not a replacement for the recorded original outcome.
"""
from collections import defaultdict
from pathlib import Path
import hashlib
import json
import statistics

ROOT = Path(__file__).resolve().parent


def main():
    path = ROOT / 'discovery_results.json'
    data = json.loads(path.read_text())
    rows = data['rows']
    output = {'results_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'analysis_kind': 'Post-experiment audit; no new native work or tuning.',
              'stages': {}}
    for stage in ('train', 'target_holdout', 'scale_holdout', 'joint_holdout'):
        rr = [r for r in rows if r['stage'] == stage]
        groups = defaultdict(list)
        for row in rr:
            groups[(row['k'], row['seed'])].append(row)
        common = {key: min(r['stats']['cpu_seconds'] for r in group)
                  for key, group in groups.items()}
        result = {}
        for policy in sorted({r['policy'] for r in rr}):
            pr = [r for r in rr if r['policy'] == policy]
            counters = {name: sum(r['stats'][name] for r in pr)
                        for name in ('attempts', 'outside_shell', 'invalid',
                                     'duplicates', 'unique_curves')}
            assert counters['attempts'] == sum(counters[n] for n in
                      ('outside_shell', 'invalid', 'duplicates', 'unique_curves'))
            hits = []
            prefix = []
            for row in pr:
                for hit in row['hits']:
                    assert sum(int(x)**3 for x in hit['xyz']) == row['k']
                    if max(map(abs, hit['xyz'])) < 10:
                        continue
                    key = (row['k'], tuple(hit['xyz']))
                    hits.append(key)
                    if hit['first_cpu_seconds'] <= common[row['k'], row['seed']]:
                        prefix.append(key)
            result[policy] = dict(counters=counters,
                actual_cpu_seconds=sum(r['stats']['cpu_seconds'] for r in pr),
                cpu_min= min(r['stats']['cpu_seconds'] for r in pr),
                cpu_median=statistics.median(r['stats']['cpu_seconds'] for r in pr),
                cpu_max=max(r['stats']['cpu_seconds'] for r in pr),
                attempt_cap_runs=sum(r['stats']['attempts'] == 1000000 for r in pr),
                runs=len(pr),
                repeated_run_discoveries=len(hits),
                distinct_solutions=len(set(hits)),
                prefix_equal_observed_cpu_seconds=sum(common[r['k'], r['seed']] for r in pr),
                prefix_repeated_run_discoveries=len(prefix),
                prefix_distinct_solutions=len(set(prefix)),
                distinct_solutions_xyz=sorted(set(hits)))
        output['stages'][stage] = result
    ratios = {}
    for seed in (914, 915):
        rate = {}
        for policy in ('learned_mixture', 'uniform_mixture'):
            rr = [r for r in rows if r['stage'] == 'joint_holdout'
                  and r['seed']//1000000 == seed and r['policy'] == policy]
            n = sum(max(map(abs, h['xyz'])) >= 10 for r in rr for h in r['hits'])
            rate[policy] = n/sum(r['stats']['cpu_seconds'] for r in rr)
        ratios[str(seed)] = rate['learned_mixture']/rate['uniform_mixture']
    joint = output['stages']['joint_holdout']['learned_mixture']
    output['gate'] = dict(enable_discovery_learning=False,
        criterion='At least 10 qualifying joint-heldout discoveries and >=1.10x uniform discovery/CPU in each seed.',
        repeated_discoveries=joint['repeated_run_discoveries'],
        distinct_target_solutions=joint['distinct_solutions'],
        per_seed_rate_ratios=ratios,
        count_condition_passed=joint['repeated_run_discoveries'] >= 10,
        rate_condition_passed=all(v >= 1.10 for v in ratios.values()),
        interpretation='Fails even under the lenient repeated-run count; seed recurrence is not independent discovery.')
    output['total'] = dict(runs=len(rows),
        attempts=sum(r['stats']['attempts'] for r in rows),
        curves=sum(r['stats']['unique_curves'] for r in rows),
        attempt_cap_runs=sum(r['stats']['attempts'] == 1000000 for r in rows),
        native_cpu_seconds=data['native_cpu_seconds'],
        aggregate_extra_cpu_seconds=data['aggregate_extra_cpu_seconds'],
        elapsed_seconds=data['total_elapsed_seconds'],
        frozen_files_unchanged=data['frozen_files_unchanged'],
        failures=len(data['failures']))
    (ROOT / 'discovery_analysis.json').write_text(json.dumps(output, indent=2)+'\n')
    print(json.dumps({'gate': output['gate'], 'total': output['total'],
          'common_prefix': {stage: {policy: [p['prefix_repeated_run_discoveries'],
                      p['prefix_distinct_solutions'], p['prefix_equal_observed_cpu_seconds']]
                      for policy, p in pol.items()}
                      for stage, pol in output['stages'].items()}}, indent=2))


if __name__ == '__main__':
    main()
