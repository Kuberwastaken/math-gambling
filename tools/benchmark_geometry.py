"""Frozen-model paired search trial. Never uploads work or changes production."""
import argparse
import hashlib
import json
import math
import platform
import random
import statistics
import time
from pathlib import Path

from geometric_policy import mass, KAPPA
from search_core import CONTEXTS, D0, make_task, run_task, task_id, verify_triple
from search_features import certified_empty
from strategy_model import digest, predict


def fast_mass(low, high):
    """Six terms of the same density integral, not a different objective.

    (1-u)^(-1/2) has positive binomial coefficients. Above KAPPA,
    u=1/(4*t^3)<.0044; truncating after n=5 has relative tail below
    .0044**6/(1-.0044) < 7.3e-15 in exact arithmetic. Floating-point
    roundoff remains; none of this arithmetic can prune a search candidate.
    """
    low = max(float(low), KAPPA)
    high = float(high)
    if high <= low: return 0.
    log_ratio = math.log1p((high-low)/low)
    power = 1/math.sqrt(low)
    step = 1/(low**3)
    coefficient = 1.
    terms = []
    for n in range(6):
        terms.append(coefficient*power*(-math.expm1(-(.5+3*n)*log_ratio))/(6*n+1))
        coefficient *= (2*n+2)*(2*n+1)/(16*(n+1)**2)
        power *= step
    return math.fsum(terms)


class Exposure:
    """Union inclusive integer q intervals for each canonical (D,r,s) curve.

    Weight integer positions by their half-unit cells in |z|/D. Quadrature is
    a scoring approximation only: it never changes a search bound or verifier.
    """
    def __init__(self):
        self.intervals = {}
        self.value = 0.
        self.positions = 0
        self.repeated_positions = 0

    @staticmethod
    def weight(d, r, lo, hi):
        a, b = lo + r/d - .5, hi + r/d + .5
        if b <= 0:
            return D0/d * fast_mass(-b, -a)
        if a >= 0:
            return D0/d * fast_mass(a, b)
        return D0/d * (fast_mass(0, -a) + fast_mass(0, b))

    def add(self, event):
        d, r, s, lo, hi = (int(event[k]) for k in ('D', 'r', 's', 'qlo', 'qhi'))
        if not (d > 0 and 0 <= r < d and abs(s) == d and lo <= hi
                and event['minimal_abs_z'] is True):
            raise ValueError('invalid completed curve')
        key = d, r, s
        old = self.intervals.get(key, [])
        fresh = [(lo, hi)]
        for a, b in old:
            pieces = []
            for x, y in fresh:
                if b < x or a > y:
                    pieces.append((x, y))
                else:
                    if x < a: pieces.append((x, a-1))
                    if b < y: pieces.append((b+1, y))
            fresh = pieces
        n = sum(b-a+1 for a, b in fresh)
        self.positions += n
        self.repeated_positions += hi-lo+1-n
        self.value += math.fsum(self.weight(d, r, a, b) for a, b in fresh)
        merged = []
        for a, b in sorted(old + fresh):
            if merged and a <= merged[-1][1]+1:
                merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
            else:
                merged.append((a, b))
        self.intervals[key] = merged


def summary(runs):
    paired = {}
    for r in runs:
        paired.setdefault(r['repeat'], {})[r['arm']] = r['exposure']/r['cpu_s']
    if any(set(p) != {'current', 'learned'} or p['current'] <= 0 for p in paired.values()):
        raise ValueError('incomplete pair or zero baseline exposure; no selective dropping')
    ratios = [p['learned']/p['current'] for p in paired.values()]
    rng = random.Random(114913)
    boot = sorted(statistics.median(rng.choices(ratios, k=len(ratios))) for _ in range(10000))
    median = statistics.median(ratios)
    return {'paired_median_rate_ratio': median, 'bootstrap_median_95_percent': [boot[249], boot[9749]],
            'pairs': len(ratios), 'learned_wins': sum(x > 1 for x in ratios),
            'exploratory_gate_passed': median > 1.10 and boot[249] > 1.,
            'production_promotion': False}


def run_arm(policy, model, seed, arm, budget, out):
    # Independent common streams keep context/exploration draws paired even
    # when the candidate pool consumes additional task-coordinate draws.
    context_rng = random.Random(seed)
    task_rng = random.Random(seed ^ 810114)
    branch_rng = random.Random(seed ^ 640114)
    entries = {c['id']: c for c in policy['contexts']}
    weights = [entries[c['id']]['weight'] for c in CONTEXTS]
    seen = set()
    exposure = Exposure()
    journal = []
    counts = dict(proposals=0, proved_empty=0, duplicate_tasks=0)
    select_cpu = search_cpu = account_cpu = 0.
    start_wall = time.monotonic()
    start = time.process_time()

    def candidate(c):
        for attempt in range(100):
            task = make_task(c['id'], task_rng.randrange(int(c['rowTasks']))*c['rowStride'], task_rng.randrange(c['blocks']))
            counts['proposals'] += 1
            if attempt < 31 and certified_empty(task):
                counts['proved_empty'] += 1
                continue
            if task_id(task) in seen:
                counts['duplicate_tasks'] += 1
                continue
            return task
        raise RuntimeError('fresh proposal budget exhausted')

    def rescue(hit):
        if not verify_triple(hit['xyz']): raise ArithmeticError('invalid identity')
        # Preserve independently of the ordinary result journal.
        from runner import atomic_json
        atomic_json(out/('DISCOVERY-'+digest(hit)+'.json'), hit)
        raise RuntimeError('Exact identity saved; stopping trial')

    while time.process_time()-start < budget:
        if len(journal) >= 100000 or time.monotonic()-start_wall > max(60, 20*budget):
            raise RuntimeError('safety cap reached; trial incomplete')
        tick = time.process_time()
        c = context_rng.choices(CONTEXTS, weights=weights, k=1)[0]
        exploit = branch_rng.random() >= .4
        task = candidate(c)
        if arm == 'learned' and exploit:
            pool = {task_id(task): task}
            for _ in range(7):
                q = candidate(c)
                pool[task_id(q)] = q
            # Context is fixed, so its geometric weight cancels from the ratio.
            def score(t):
                y = predict(model, t)
                v = y['curves']/y['cpu_ms']
                if not math.isfinite(v) or v < 0: raise ValueError('invalid score')
                return v
            task = max(pool.values(), key=score)
        select_cpu += time.process_time()-tick
        curves = []
        tick = time.process_time()
        result = run_task(task, on_curve=curves.append, on_hit=rescue)
        search_cpu += time.process_time()-tick
        tick = time.process_time()
        for curve in curves: exposure.add(curve)
        seen.add(result['id'])
        journal.append({'task': task, 'digest': result['digest'], 'curves': curves,
                        'exact_tests': result['counters']['exact_tests']})
        account_cpu += time.process_time()-tick
    cpu = time.process_time()-start
    return {'arm': arm, 'cpu_s': cpu, 'overshoot_s': max(0., cpu-budget),
            'wall_s': time.monotonic()-start_wall, 'selection_cpu_s': select_cpu,
            'search_cpu_s': search_cpu, 'accounting_cpu_s': account_cpu,
            'tasks': len(journal), **counts, 'exposure': exposure.value,
            'distinct_positions': exposure.positions, 'repeated_positions': exposure.repeated_positions,
            'distinct_curves': len(exposure.intervals), 'journal': journal}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--policy', type=Path, required=True)
    p.add_argument('--model', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--seconds', type=float, default=2.)
    p.add_argument('--repeats', type=int, default=32)
    p.add_argument('--seed', type=int, default=11420260913)
    a = p.parse_args()
    if not 0 < a.seconds <= 10 or not 8 <= a.repeats <= 64:
        p.error('budget: seconds in (0,10], repeats in [8,64]')
    if a.output.exists(): p.error('output must be a new directory')
    policy = json.loads(a.policy.read_text())
    record = json.loads(a.model.read_text())
    if record['model_hash'] != digest({k:v for k,v in record.items() if k != 'model_hash'}):
        raise ValueError('frozen model hash mismatch')
    if policy.get('policy_version') != 'mg114-cpu-budget-v1' or policy.get('proposal_preflight') != 'mg114-shell-tile-v1':
        raise ValueError('expected current production scheduler')
    if {c['id'] for c in policy['contexts']} != {c['id'] for c in CONTEXTS}:
        raise ValueError('incomplete policy')
    source = Path(__file__).resolve().parent
    manifest = {'schema':'mg114-distinct-geometry-trial-v2', 'seed':a.seed, 'repeats':a.repeats,
        'cpu_seconds_per_arm':a.seconds, 'model_hash':record['model_hash'], 'policy_hash':digest(policy),
        'source_hashes':{n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in
            ('benchmark_geometry.py','search_core.py','geometric_policy.py','strategy_model.py','shared_model.py','search_features.py')},
        'python':platform.python_version(), 'machine':platform.machine(),
        'primary':'distinct signed (D,r,q) exposure: D0/D times integral 1/sqrt(4t^3-1) over half-unit q cells above ordering cutoff',
        'challenger':'same context weights/preflight; 40% ordinary proposals, 60% best of 8 by frozen predicted curves/CPU within context',
        'gate':'paired median exposure/CPU ratio >1.10 and paired bootstrap 95% lower bound >1; no automatic promotion',
        'limitations':['Uncalibrated geometric prior, not discovery probability.',
            'Distinctness is within each arm/seed, not against global historical coverage. Arms intentionally start with identical empty trial ledgers.',
            'In-memory task lookup, interval union, feature/preflight/scoring and engine CPU charged; no network, SQLite persistence or upload costs.',
            'Python reference kernel only; learned 40% random branch is a task fraction, not a guarantee of CPU exploration share.',
            'Final whole task may overshoot nominal budget; actual CPU charged in every rate. One machine and frozen model, exploratory inference.']}
    a.output.mkdir(parents=True)
    (a.output/'preregistered.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (a.output/'model.json').write_bytes(a.model.read_bytes())
    (a.output/'policy.json').write_bytes(a.policy.read_bytes())
    # Common filter setup excluded; clear the small quadrature cache each arm.
    run_task(make_task('c00',0))
    runs = []
    order = random.Random(a.seed ^ 913)
    for repeat in range(a.repeats):
        arms = ['current','learned']; order.shuffle(arms)
        for arm in arms:
            mass.cache_clear()
            r = run_arm(policy,record['model'],a.seed+repeat,arm,a.seconds,a.output)
            r['repeat'] = repeat
            # Disk reporting is outside timing, identically for both arms.
            with (a.output/'runs.jsonl').open('a') as f: f.write(json.dumps(r)+'\n')
            runs.append({k:v for k,v in r.items() if k != 'journal'})
        print(f'completed pair {repeat+1}/{a.repeats}', flush=True)
    result = {'specification':manifest, 'summary':summary(runs), 'runs':runs}
    (a.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result['summary'],indent=2))


if __name__ == '__main__': main()
