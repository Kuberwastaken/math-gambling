#!/usr/bin/env python3
"""Bounded local 114 challenger pilot. No banking, production writes or promotion."""
import argparse
import json
import platform
import random
import time
from pathlib import Path
from collections import Counter
from strategy_model import ROOT, digest, observations, predict
from search_core import CONTEXTS, make_task, task_id, verify_triple
from ingest import WarmReplay
from runner import atomic_json

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,default=ROOT/'data');p.add_argument('--output',type=Path,required=True)
    p.add_argument('--seed',type=int,default=11420260911);p.add_argument('--cpu-seconds',type=float,default=.5)
    args=p.parse_args()
    if not 0<args.cpu_seconds<=5:p.error('pilot CPU budget must be in (0,5] seconds per arm/seed')
    if args.output.exists():p.error('output must be new; do not overwrite experiments')
    latest=json.loads((args.data/'learning/latest.json').read_text())
    models=sorted((args.data/latest['history']).glob('model-*.json'))
    if not models:p.error('fit a frozen model first')
    record=json.loads(models[-1].read_text());model=record['model']
    policy=json.loads((args.data/'strategy.json').read_text());weights=[x['weight'] for x in policy['contexts']]
    covered={r['id'] for r in observations(args.data)}
    manifest={'schema':'mg114-controlled-pilot-v1','model_hash':record['model_hash'],'policy_hash':digest(policy),
              'coverage_hash':digest(sorted(covered)),'seed':args.seed,'python':platform.python_version(),
              'machine':platform.machine(),'cpu_budget_per_arm_seed':args.cpu_seconds,
              'arms':['uniform','current','spatial_q','spatial_exact_diagnostic'],
              'limitations':['Small exploratory pilot, not promotion evidence.','Equal nominal CPU budgets; bounded final-task overshoot is reported.',
                             'Python worker plus parent selection CPU; wall time includes IPC and startup.',
                             'All pilot work is uncredited; counters are not winning odds.'], 'runs':[]}
    args.output.mkdir(parents=True)
    atomic_json(args.output/'preregistered.json',manifest)
    class Discovery(Exception):pass
    def rescue(hit):
        if not verify_triple(hit.get('xyz')):raise ValueError('invalid reported hit')
        atomic_json(args.output/('identity-'+digest(hit)+'.json'),hit)
        raise Discovery('Exact identity preserved; stop all pilot scheduling')
    order=random.Random(args.seed)
    try:
        for repeat in range(4):
            arms=list(manifest['arms']);order.shuffle(arms)
            for arm in arms:
                rng=random.Random(args.seed+repeat);seen=set();cpu=0.;stats=Counter();journal=[];start=time.monotonic()
                def proposal(weighted=False):
                    for _ in range(1000):
                        c=rng.choices(CONTEXTS,weights=weights if weighted else None,k=1)[0]
                        t=make_task(c['id'],rng.randrange(int(c['rowTasks']))*128,rng.randrange(c['blocks']))
                        if task_id(t) not in covered and task_id(t) not in seen:return t
                    raise RuntimeError('fresh proposal budget exhausted')
                with WarmReplay() as replay:
                    while cpu<args.cpu_seconds*1000 and len(journal)<1000 and time.monotonic()-start<30:
                        clock=time.process_time()
                        if arm=='current':t=proposal(True)
                        elif arm=='uniform' or rng.random()<.4:t=proposal()
                        else:
                            candidates={}
                            for _ in range(8):
                                q=proposal();candidates[task_id(q)]=q
                            target='quotient_points' if arm=='spatial_q' else 'exact_tests'
                            def score(q):
                                y=predict(model,q);return y[target]/y['cpu_ms']
                            t=max(candidates.values(),key=score)
                        selection=(time.process_time()-clock)*1000
                        result,elapsed=replay(t,on_hit=rescue)
                        cpu+=elapsed+selection;seen.add(result['id']);stats.update(result['counters'])
                        journal.append({'task':t,'digest':result['digest'],'cpu_ms':elapsed,'selection_cpu_ms':selection})
                run={'repeat':repeat,'arm':arm,'cpu_ms':cpu,'overshoot_ms':max(0,cpu-args.cpu_seconds*1000),
                     'wall_seconds':time.monotonic()-start,'tasks':len(journal),'counters':dict(stats),'journal':journal}
                manifest['runs'].append(run);atomic_json(args.output/'results.json',manifest)
    except BaseException as exc:
        manifest['failure']=str(exc);atomic_json(args.output/'results.json',manifest);raise
    for arm in manifest['arms']:
        runs=[r for r in manifest['runs'] if r['arm']==arm];cost=sum(r['cpu_ms'] for r in runs)
        print(arm,json.dumps({'tasks':sum(r['tasks'] for r in runs),'cpu_ms':cost,
            'q_per_cpu_ms':sum(r['counters']['quotient_points'] for r in runs)/cost,
            'exact_tests':sum(r['counters']['exact_tests'] for r in runs)}))
if __name__=='__main__':main()
