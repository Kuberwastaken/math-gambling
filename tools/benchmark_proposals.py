"""Fixed-budget paired proposer trial; no uploads or production policy writes."""
import argparse,json,random,time,statistics
from pathlib import Path
from search_core import CONTEXTS,make_task,run_task,task_id,verify_triple,D0
from search_features import certified_empty
from geometric_policy import cpu_budget_policy,mass


def main():
    p=argparse.ArgumentParser();p.add_argument('--policy',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--seconds',type=float,default=.1);p.add_argument('--repeats',type=int,default=32);p.add_argument('--seed',type=int,default=1140912);a=p.parse_args()
    if not 0<a.seconds<=1 or not 8<=a.repeats<=64:p.error('bounded trial: 0<seconds<=1, 8<=repeats<=64')
    if a.output.exists():p.error('new output directory required')
    policy=json.loads(a.policy.read_text());challenger=cpu_budget_policy(policy)
    arms=['current','current_proof','cpu_budget','cpu_budget_proof'];a.output.mkdir(parents=True)
    specification={'schema':'mg114-proposer-trial-v1','seed':a.seed,'repeats':a.repeats,'cpu_seconds_per_arm':a.seconds,
        'arms':arms,'policy':policy,'challenger':challenger,'objective':'actual-D weighted band exposure / reference Python CPU',
        'gate':'paired median lift > 1.10 and bootstrap 95% lower bound > 1.0; proxy-only exploratory gate, not automatic promotion',
        'limitations':['Reference Python cost; not end-to-end mobile/network/storage cost.','No discovery probability is estimated.','No credit or certified global coverage.']}
    (a.output/'preregistered.json').write_text(json.dumps(specification,indent=2)+'\n')
    # Initialize identical fixed filters before measuring arms.
    run_task(make_task('c00',0))
    runs=[];order=random.Random(a.seed^490114)
    for repeat in range(a.repeats):
        trial=list(arms);order.shuffle(trial)
        for arm in trial:
            rng=random.Random(a.seed+repeat);weights=[c['weight'] for c in (challenger if arm.startswith('cpu') else policy)['contexts']]
            elapsed=0.;exposure=0.;tasks=proposals=skips=0;seen=set();journal=[]
            while elapsed<a.seconds and tasks<4096:
                start=time.process_time();c=rng.choices(CONTEXTS,weights=weights,k=1)[0]
                for attempt in range(32):
                    task=make_task(c['id'],rng.randrange(int(c['rowTasks']))*128,rng.randrange(c['blocks']));proposals+=1
                    if arm.endswith('proof') and attempt<31 and certified_empty(task):skips+=1;continue
                    break
                if task_id(task) in seen:elapsed+=time.process_time()-start;continue
                ds=[]
                def save(hit):
                    if not verify_triple(hit['xyz']):raise ValueError('invalid identity')
                    (a.output/'DISCOVERY.json').write_text(json.dumps(hit));raise RuntimeError('Exact identity saved; stopping trial')
                result=run_task(task,on_curve=lambda e:ds.append(int(e['D'])),on_hit=save)
                cost=time.process_time()-start;elapsed+=cost;tasks+=1;seen.add(result['id'])
                exposure+=mass(c['low'],c['high'])*sum(D0/d for d in ds)
                journal.append({'task':task,'digest':result['digest'],'cpu_s':cost})
            runs.append({'repeat':repeat,'arm':arm,'cpu_s':elapsed,'tasks':tasks,'proposals':proposals,'proved_empty':skips,'exposure':exposure,'rate':exposure/elapsed,'journal':journal})
    baseline={r['repeat']:r['rate'] for r in runs if r['arm']=='current'};comparisons={}
    for arm in arms[1:]:
        ratios=[r['rate']/baseline[r['repeat']] for r in runs if r['arm']==arm and baseline[r['repeat']]>0]
        rng=random.Random(914);boot=sorted(statistics.median(rng.choices(ratios,k=len(ratios))) for _ in range(2000))
        comparisons[arm]={'paired_median_lift':statistics.median(ratios),'bootstrap_median_95_percent':[boot[49],boot[1949]],
                          'gate_passed':statistics.median(ratios)>1.1 and boot[49]>1}
    (a.output/'results.json').write_text(json.dumps({'specification':specification,'comparisons':comparisons,'runs':runs},indent=2)+'\n')
    print(json.dumps(comparisons,indent=2))

if __name__=='__main__':main()
