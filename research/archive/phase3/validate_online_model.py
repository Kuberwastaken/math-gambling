#!/usr/bin/env python3
"""Synthetic correctness/behavior checks. Not evidence of discovering114."""
import hashlib
import json
import math
from pathlib import Path
import time

from online_model import Model,evaluate,geometric_mass,KAPPA,_integral,_UMAX

ROOT=Path(__file__).resolve().parent


def specs():
    result=[]
    for ell in (1,5,25):
        for shape,(tlo,thi,radius) in enumerate(((8,31,6000000),(128,511,1500000),(2048,8191,375000))):
            for shell in range(3):
                for band,(low,high,weight) in enumerate(((0,64,.7),(64,256,.2),(256,4096,.1))):
                    result.append(dict(key=f'{ell}:{shape}:{shell}:{band}',ell=ell,radius=radius,tlo=tlo,thi=thi,
                                       dlo=100*2**shell,dhi=100*2**(shell+1),low=low,high=high,
                                       family='offset',shape_index=shape,shell_index=shell,band_index=band,weight=weight/27))
    return result


def rate(spec):
    return (1,5,30)[spec['shape_index']] * (1,.8,.6)[spec['shell_index']] / (1,2,6)[spec['band_index']]


def main():
    began=time.monotonic();ss=specs();tests=[]
    bands=[geometric_mass(0,64),geometric_mass(64,256),geometric_mass(256,4096),geometric_mass(4096,math.inf)]
    assert abs(sum(bands)-1)<1e-12 and all(0<x<1 for x in bands)
    assert geometric_mass(0,KAPPA)==0 and geometric_mass(1,1)==0
    assert abs(1/_integral(0,_UMAX)-1.96084321968938583)<1e-10
    assert abs(_integral(0,_UMAX,256)-_integral(0,_UMAX,512))<1e-12
    for lo,hi in ((0,64),(64,256),(256,4096)):
        midpoint=(max(lo,KAPPA)+hi)/2
        assert abs(geometric_mass(lo,midpoint)+geometric_mass(midpoint,hi)-geometric_mass(lo,hi))<1e-12
    tests.append('Geometric normalization, additivity and quadrature refinement')

    cold=Model.initial(ss)
    for spec in ss:
        if spec['shell_index']<2:
            for _ in range(3):cold.observe(spec,1,rate(spec),100,{})
    cold_scores=cold.scores(ss,{})
    slow=next(s for s in ss if s['ell']==1 and s['shape_index']==0 and s['shell_index']==2 and s['band_index']==0)
    fast=next(s for s in ss if s['ell']==1 and s['shape_index']==2 and s['shell_index']==2 and s['band_index']==0)
    assert cold_scores[fast['key']]>3*cold_scores[slow['key']]
    tests.append('Contextual transfer to unseen divisor-shell arms')

    records=[];model=Model.initial(ss)
    for repeat,mult in enumerate((.98,1.02,1.0)):
        for spec in ss:
            elapsed=.8+.1*((spec['shape_index']+repeat)%3)
            exposure=rate(spec)*mult*elapsed
            row=dict(spec=spec,elapsed=elapsed,exposure_sum=exposure,rows=100,
                     stats={'start':repeat*100,'count':100})
            records.append(row);model.observe(spec,elapsed,exposure,100,row['stats'])
    scores=model.scores(ss,{})
    assert scores[fast['key']]>10*scores[slow['key']]
    pending=model.scores(ss,{fast['key']:11})
    assert abs(pending[fast['key']]*12/scores[fast['key']]-1)<1e-12
    assert pending[slow['key']]==scores[slow['key']]
    tests.append('Known fast/slow ordering and pending-job discount')
    restored=Model.from_dict(json.loads(json.dumps(model.to_dict(),sort_keys=True)))
    assert restored.scores(ss,{})==scores
    tests.append('Exact serialization round-trip scores and ranking')

    gate=evaluate(records)
    assert gate['enable_model'] and gate['spearman']>.9 and gate['top_quarter_over_baseline']>1.5
    assert gate['contextual_over_geometry_only']>1.3
    inverted=[]
    seen={}
    for row in records:
        item=dict(row);key=item['spec']['key'];seen[key]=seen.get(key,0)+1
        if seen[key]==3:item['exposure_sum']=item['elapsed']/max(rate(item['spec']),1e-9)
        inverted.append(item)
    bad_gate=evaluate(inverted)
    assert not bad_gate['enable_model']
    assert not evaluate(records[:162])['enable_model']
    tests.append('Untouched third-record gate accepts predictable proxy and rejects inverted/incomplete holdouts')

    zero=Model.initial(ss)
    zero_records=[]
    for repeat in range(4):
        for spec in ss:
            zero.observe(spec,.1,0,0,{})
            zero_records.append(dict(spec=spec,elapsed=.1,exposure_sum=0,rows=0,stats={}))
    assert all(math.isfinite(v) and v>0 for v in zero.scores(ss,{}).values())
    assert not evaluate(zero_records)['enable_model']
    assert Model.from_dict(zero.to_dict()).scores(ss,{})==zero.scores(ss,{})
    tests.append('Zero-exposure numerical stability and disabled gate')

    robust=Model.initial(ss)
    arm=ss[0]
    for _ in range(9):robust.observe(arm,1,10,100,{})
    before=robust.scores([arm],{})[arm['key']]
    robust.observe(arm,1e-6,100,100,{})
    after=robust.scores([arm],{})[arm['key']]
    assert after<2*before
    for _ in range(9):robust.observe(arm,1,20,100,{})
    assert abs(robust._measured(robust.arms[arm['key']])-20)<1e-12
    tests.append('Timer-outlier resistance and adaptation after sustained rate change')

    original=model.to_dict()
    for elapsed,exposure in ((0,1),(-1,1),(1,-1),(float('nan'),1),(1,float('inf')),(1e-200,1e200)):
        try:model.observe(ss[0],elapsed,exposure,100,{})
        except ValueError:pass
        else:raise AssertionError((elapsed,exposure))
        assert model.to_dict()==original
    try:model.scores(ss,{ss[0]['key']:-1})
    except ValueError:pass
    else:raise AssertionError('Negative pending count accepted')
    for bad in ({},dict(original,version=999)):
        try:Model.from_dict(bad)
        except (ValueError,KeyError):pass
        else:raise AssertionError('Invalid state accepted')
    tests.append('Invalid observations cannot corrupt persistent state')

    # Leakage check: changing unused fourth records cannot affect the gate.
    extra=[dict(r,elapsed=1,exposure_sum=1e30) for r in records[-81:]]
    assert evaluate(records+extra)==gate
    tests.append('Heldout gate ignores later observations without refitting')
    result=dict(passed=True,tests=tests,synthetic_only=True,contexts=len(ss),
                geometric_band_mass=bands,good_holdout_gate=gate,bad_holdout_gate=bad_gate,
                elapsed_seconds=time.monotonic()-began,
                source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (ROOT/'online_model.py',Path(__file__))})
    (ROOT/'online-model-validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'tests':len(tests),'contexts':len(ss),'elapsed_seconds':result['elapsed_seconds']},indent=2))


if __name__=='__main__':main()
