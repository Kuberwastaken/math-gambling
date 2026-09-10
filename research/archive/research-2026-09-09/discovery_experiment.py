#!/usr/bin/env python3
"""Preregistered tiny discovery benchmark, target and scale holdouts, one child.

No known coordinates or roots are supplied to candidate generation. Reference
catalogue is opened only after all outcome-generating runs have completed.
"""
from pathlib import Path
import hashlib
import json
import math
import random
import resource
import subprocess
import time

ROOT=Path(__file__).resolve().parent
LAB=ROOT.parent
PROJECT=LAB.parent.parent
WORK=PROJECT/'work/research2026-learning'
FAMILIES=('cube','balanced','real_strip','complex_tube')
NATIVE=WORK/'discovery_worker'
MIN_HEIGHT=10

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def eligible(k):return k!=114 and k%9 in (3,6) and all(k%(p**3) for p in range(2,math.isqrt(k)+1))
def split(k):return 'target_holdout' if hashlib.sha256(f'discovery-learning-v2:{k}'.encode()).digest()[0]%3==0 else 'train'
def child_cpu():
    r=resource.getrusage(resource.RUSAGE_CHILDREN)
    return r.ru_utime+r.ru_stime
def own_cpu():
    r=resource.getrusage(resource.RUSAGE_SELF)
    return r.ru_utime+r.ru_stime
def singleton(i):return [1000000 if j==i else 0 for j in range(4)]

def run(k,A,dlo,dhi,weights,seed,budget=.055,maximum=1000000,trace=False):
    args=[str(NATIVE),*map(str,(k,A,dlo,dhi,128,budget,maximum,seed,*weights,int(trace)))]
    begin=time.monotonic()
    p=subprocess.run(args,capture_output=True,text=True,timeout=30,check=True)
    assert not p.stderr.strip(),p.stderr
    records=[json.loads(s) for s in p.stdout.splitlines()]
    stats=records[-1]
    assert stats['type']=='discovery_stats' and stats['k']==k
    assert stats['attempts']==stats['outside_shell']+stats['invalid']+stats['duplicates']+stats['unique_curves']
    points={};pending=[]
    for rec in records:
        if rec['type']=='sample':
            a,b,c=map(int,rec['abc'])
            assert a**3+k*b**3+k*k*c**3-3*k*a*b*c==int(rec['norm'])
        if rec['type']=='hit':
            xyz=tuple(sorted(map(int,rec['xyz'])))
            assert sum(x**3 for x in xyz)==k
            d,r=int(rec['D']),int(rec['r'])
            a,b,c=map(int,rec['abc'])
            assert abs(a**3+k*b**3+k*k*c**3-3*k*a*b*c)==d
            assert pow(r,3,d)==k%d and (k*c*c-a*b-(b*b-a*c)*r)%d==0
            assert dlo<d<=dhi
            if min(map(abs,xyz))<=128*d:
                pending.append((xyz,d,r,rec['index']))
        if rec['type']=='hit_time':
            for xyz,d,r,index in pending:
                assert index==rec['index']
                points.setdefault(xyz,dict(xyz=xyz,d=d,r=r,first_cpu_seconds=rec['cpu_seconds']))
            pending=[]
    assert not pending
    return dict(k=k,radius=A,dlo=dlo,dhi=dhi,seed=seed,weights=weights,
                elapsed_seconds=time.monotonic()-begin,stats=stats,hits=list(points.values()))

def count_hits(row,threshold=MIN_HEIGHT):return sum(max(map(abs,h['xyz']))>=threshold for h in row['hits'])
def summary(rows):
    result={}
    for policy in sorted({r['policy'] for r in rows}):
        rr=[r for r in rows if r['policy']==policy]
        cpu=sum(r['stats']['cpu_seconds'] for r in rr)
        found={(r['k'],tuple(h['xyz'])) for r in rr for h in r['hits'] if max(map(abs,h['xyz']))>=MIN_HEIGHT}
        result[policy]=dict(runs=len(rr),cpu_seconds=cpu,elapsed_seconds=sum(r['elapsed_seconds'] for r in rr),
             attempts=sum(r['stats']['attempts'] for r in rr),curves=sum(r['stats']['unique_curves'] for r in rr),
             qualifying_hits=sum(count_hits(r) for r in rr),hard_hits=sum(count_hits(r,1000) for r in rr),
             distinct_target_solutions=len(found),target_cases_with_hits=len({k for k,_ in found}),
             qualifying_hits_per_cpu_second=sum(count_hits(r) for r in rr)/cpu,
             per_seed={str(seed):sum(count_hits(r) for r in rr if r['seed']//1000000==seed) for seed in (914,915)})
    return result

def reference_audit(rows):
    path=PROJECT/'work/literature/huisman.txt'
    ref={}
    for line in path.read_text().splitlines():
        parts=line.split()
        if len(parts)!=4:continue
        try:k,x,y,z=map(int,parts)
        except ValueError:continue
        assert x**3+y**3+z**3==k
        ref.setdefault(k,set()).add(tuple(sorted((x,y,z))))
    for row in rows:
        opportunities=[]
        for xyz in ref.get(row['k'],set()):
            zz=min(xyz,key=abs);xy=list(xyz);xy.remove(zz);d=abs(sum(xy))
            if row['dlo']<d<=row['dhi'] and d>=2 and abs(zz)<=128*d and max(map(abs,xyz))>=MIN_HEIGHT:
                opportunities.append(xyz)
        row['catalogued_scope_opportunities']=len(opportunities)
        row['hits_in_catalogue']=sum(tuple(h['xyz']) in ref.get(row['k'],set()) for h in row['hits'])
    return dict(path=str(path),sha256=digest(path),opened_after_search=True,
                warning='Incomplete, search-selected catalogue; scope opportunities do not imply bounded coefficient representability or population recall.')

def main():
    WORK.mkdir(parents=True,exist_ok=True)
    begun=time.monotonic();cpu_begin=child_cpu()+own_cpu()
    source=ROOT/'discovery_worker.c';checker=LAB/'phase3/checker.c'
    frozen={str(p):digest(p) for p in (checker,LAB/'phase3/offset_worker.c',LAB/'phase3/bin/offset_worker')}
    ks=[k for k in range(3,241) if eligible(k)]
    groups={part:[k for k in ks if split(k)==part] for part in ('train','target_holdout')}
    config=dict(schema=1,target_rule='All cube-free k in3..240 with kmod9 in{3,6}, excluding114.',
                splits=groups,training_shell=[1,1000],larger_holdout_shell=[1000,1000000],
                radii=[8,32],ratio=128,cpu_quota=.055,seeds=[914,915],
                primary_height=10,hard_secondary_height=1000,
                families=FAMILIES,policy='Learn only on training targets, small D shell; freeze before every holdout.',
                learned_mixture='40% uniform proposal probability plus60% smoothed positive discovery-rate weights.',
                success_gate='At least10 qualifying joint-heldout discoveries and>=1.10x uniform discovery/CPU in each seed; no114fertility claim regardless.',
                allocation='One native child at a time; initial experiment capped below60aggregate extra CPU seconds.',
                source_sha256=digest(source),checker_sha256=digest(checker))
    manifest=ROOT/'discovery_preregistered.json'
    manifest.write_text(json.dumps(config,indent=2)+'\n')
    subprocess.run(['clang','-O3','-I',str(PROJECT/'work/pari-include'),str(source),'-L',str(LAB/'bin'),'-lpari','-o',str(NATIVE)],check=True)
    link=WORK/'libpari.dylib'
    if not link.exists():link.symlink_to(LAB/'bin/libpari.dylib')
    # Deterministic generator/identity validation only; excluded from training.
    validations=[]
    for k in (6,30):
        for family in range(4):
            validations.append(run(k,8,1,1000000,singleton(family),8811,budget=.01,maximum=256,trace=True))
    result=dict(config=config,manifest_sha256=digest(manifest),frozen_hashes=frozen,
                generator_validation_cases=len(validations),rows=[],failures=[])
    rng=random.Random(914114)
    output=ROOT/'discovery_results.json'
    def execute(stage,k,A,dlo,dhi,policy,weights,seed):
        used=child_cpu()+own_cpu()-cpu_begin
        if used>52:raise RuntimeError('Initial aggregate CPU budget reached; no further runs authorized in this pass.')
        row=run(k,A,dlo,dhi,weights,seed)
        row.update(stage=stage,policy=policy)
        result['rows'].append(row)
    train=[(k,family,seed) for k in groups['train'] for family in range(4) for seed in (914,915)]
    rng.shuffle(train)
    for k,family,seed in train:
        execute('train',k,8,1,1000,FAMILIES[family],singleton(family),seed*1000000+k)
    result['train_summary']=summary(result['rows'])
    rates=[result['train_summary'][f]['qualifying_hits_per_cpu_second'] for f in FAMILIES]
    winner=max(range(4),key=lambda i:(rates[i],-i))
    smoothing=sum(rates)/4 or 1.0
    posterior=[r+smoothing for r in rates]
    probabilities=[.1+.6*v/sum(posterior) for v in posterior]
    learned=[int(p*1000000) for p in probabilities]
    learned[-1]=1000000-sum(learned[:-1])
    result['frozen_learning']=dict(best_family=FAMILIES[winner],rates=rates,
                                  weights=learned,probabilities=[w/1000000 for w in learned])
    (ROOT/'discovery_frozen_policy.json').write_text(json.dumps(result['frozen_learning'],indent=2)+'\n')
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(stage='training_complete',learning=result['frozen_learning'],cpu_used=child_cpu()+own_cpu()-cpu_begin)),flush=True)
    policies={'uniform_mixture':[250000]*4,'learned_mixture':learned,'best_fixed':singleton(winner)}
    tests=[]
    for stage,targets,A,dlo,dhi in (('target_holdout',groups['target_holdout'],8,1,1000),
                                    ('scale_holdout',groups['train'],32,1000,1000000),
                                    ('joint_holdout',groups['target_holdout'],32,1000,1000000)):
        tests += [(stage,k,A,dlo,dhi,policy,seed) for k in targets for policy in policies for seed in (914,915)]
    rng.shuffle(tests)
    for stage,k,A,dlo,dhi,policy,seed in tests:
        execute(stage,k,A,dlo,dhi,policy,policies[policy],seed*1000000+k+10000*(A==32))
    for stage in ('target_holdout','scale_holdout','joint_holdout'):
        result[stage+'_summary']=summary([r for r in result['rows'] if r['stage']==stage])
    result['reference_audit']=reference_audit(result['rows'])
    result['total_elapsed_seconds']=time.monotonic()-begun
    result['aggregate_extra_cpu_seconds']=child_cpu()+own_cpu()-cpu_begin
    result['native_cpu_seconds']=sum(r['stats']['cpu_seconds'] for r in result['rows'])
    result['frozen_files_unchanged']=frozen=={str(p):digest(p) for p in map(Path,frozen)}
    assert result['frozen_files_unchanged']
    result['status']='completed'
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k.endswith('_summary') or k in ('status','aggregate_extra_cpu_seconds','total_elapsed_seconds')},indent=2))

if __name__=='__main__':main()
