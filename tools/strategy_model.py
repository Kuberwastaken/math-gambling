#!/usr/bin/env python3
"""Frozen, ledger-only spatial challenger. Never writes production strategy.json."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from collections import defaultdict
from ingest import atomic_json
from search_core import CONTEXT_BY_ID, canonical_json, task_id, validate_task

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'mg114-spatial-shadow-v2'
BOUNDARY = 1024
PRIOR = 32
TARGETS = ('cpu_ms', 'quotient_points', 'curves', 'exact_tests')

def digest(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()

def features(task):
    task = validate_task(task)
    c = CONTEXT_BY_ID[task['context']]
    width = 2*c['radius']+1
    row = int(task['row'])
    # Group the whole 128-row task by its starting coordinate; no float rounding.
    bx, by = min(3, (row % width)*4//width), min(3, (row//width)*4//width)
    block = min(3, task['block']*4//c['blocks'])
    spatial = f"{c['shape']}:{bx}:{by}"
    # A geometric region is held out across shells, ell, bands and block bins.
    heldout = int(hashlib.sha256(('spatial-v1:'+spatial).encode()).hexdigest()[:8],16)%5 == 0
    return (task['context'], f"{task['context']}:{bx}:{by}:{block}", spatial, heldout)

def observations(data, through=None):
    rows=[]
    for path in sorted((Path(data)/'receipts/tasks').glob('*/*.json')):
        item=json.loads(path.read_text())
        if through is not None and item['sequence']>through: continue
        result=item['result']; task=validate_task(result['task'])
        if item.get('schema')!='math-gambling-verified-task-v1' or result['id']!=task_id(task):
            raise ValueError('invalid trusted record identity')
        if result['digest'] != digest({k:v for k,v in result.items() if k!='digest'}):
            raise ValueError('trusted result digest mismatch')
        cpu=item['server_replay_cpu_ms']
        if isinstance(cpu,bool) or not isinstance(cpu,(float,int)) or not math.isfinite(cpu) or cpu<=0:
            raise ValueError('invalid trusted CPU')
        y={'cpu_ms':float(cpu)}
        for key in TARGETS[1:]:
            value=result['counters'][key]
            if type(value) is not int or value<0: raise ValueError('invalid counter')
            y[key]=value
        rows.append({'sequence':item['sequence'],'id':result['id'],'task':task,'y':y,
                     'hash':digest(item),'features':features(task)})
    rows.sort(key=lambda r:r['sequence'])
    if [r['sequence'] for r in rows]!=list(range(1,len(rows)+1)) or len({r['id'] for r in rows})!=len(rows):
        raise ValueError('noncontiguous or duplicate ledger')
    return rows

def fit(rows):
    from shared_model import fit_shared,fit_reference
    train=[r for r in rows if not r['features'][3]]
    if not train: raise ValueError('no spatial training observations')
    def stats(items):
        return {'n':len(items),'sum':{t:math.fsum(r['y'][t] for r in items) for t in TARGETS}}
    groups=defaultdict(list)
    for row in train:
        for key in row['features'][:2]:groups[key].append(row)
    reference=fit_reference(rows)
    return {'global':stats(train),'groups':{k:stats(v) for k,v in sorted(groups.items())},'prior':PRIOR,
            'shared':fit_shared(rows,reference),'proof_reference':reference}

def predict(model, task, fine=True):
    if fine and model.get('shared'):
        from shared_model import predict_shared
        result=predict_shared(model['shared'],task);result['cpu_ms']=max(result['cpu_ms'],.01)
        return result
    keys=features(task)[:2 if fine else 1]
    g=model['global']; mean={t:g['sum'][t]/g['n'] for t in TARGETS}
    for key in keys:
        cell=model['groups'].get(key)
        if cell:
            mean={t:(cell['sum'][t]+PRIOR*mean[t])/(cell['n']+PRIOR) for t in TARGETS}
    mean['cpu_ms']=max(mean['cpu_ms'],0.01)
    return mean

def evaluate(model, rows):
    """Prediction error on future arrivals; never a counterfactual policy estimate."""
    out={}
    from shared_model import predict_reference
    from search_features import certified_empty
    for name,subset in [('future_all',rows),('future_unseen_geometry',[r for r in rows if r['features'][3]]),
                        ('future_nonempty',[r for r in rows if 'task' in r and not certified_empty(r['task'])])]:
        measures={}
        for fine,label in [(False,'context_baseline'),(True,'spatial')]:
            preds=[predict(model,r['task'],fine) for r in subset]
            measures[label]={t:(math.fsum(abs(math.log1p(p[t])-math.log1p(r['y'][t])) for p,r in zip(preds,subset))/len(subset) if subset else None) for t in TARGETS}
        if model.get('proof_reference'):
            preds=[predict_reference(model['proof_reference'],r['task']) or predict(model,r['task'],False) for r in subset]
            measures['proof_baseline']={t:(math.fsum(abs(math.log1p(p[t])-math.log1p(r['y'][t])) for p,r in zip(preds,subset))/len(subset) if subset else None) for t in TARGETS}
        out[name]={'tasks':len(subset),'nonzero_exact_tasks':sum(r['y']['exact_tests']>0 for r in subset),'mean_absolute_log1p_error':measures}
    return out

def publish(data):
    data=Path(data); rows=observations(data); through=len(rows)//BOUNDARY*BOUNDARY
    source_hash=hashlib.sha256(b''.join((ROOT/'tools'/name).read_bytes() for name in
        ('strategy_model.py','search_core.py','shared_model.py','search_features.py'))).hexdigest()
    history=data/'learning'/SCHEMA/source_hash[:16]; history.mkdir(parents=True,exist_ok=True)
    models=[]
    # Each model is fitted once. Future evaluation uses the next complete window.
    # A new model version begins prospectively at the current boundary. No
    # retroactive retraining of hundreds of prefixes on every source change.
    existing=sorted(history.glob('model-*.json'))
    first=int(existing[0].stem.split('-')[1]) if existing else max(BOUNDARY,through)
    # Authenticate all prefixes in one linear pass, including old input changes.
    chain=bytes(32);prefixes={}
    for i,row in enumerate(rows[:through],1):
        chain=hashlib.sha256(chain+bytes.fromhex(row['hash'])).digest()
        if i%BOUNDARY==0:prefixes[i]=chain.hex()
    for n in range(first,through+1,BOUNDARY):
        path=history/f'model-{n:09d}.json'
        prefix_hash=prefixes[n]
        if path.exists():
            record=json.loads(path.read_text())
            if record['ledger_hash']!=prefix_hash or record['source_hash']!=source_hash: raise ValueError('frozen model input changed')
        else:
            record={'schema':SCHEMA,'source_hash':source_hash,'through':n,'ledger_hash':prefix_hash,
                    'mode':'shadow','objective':'predict arithmetic exposure and server cost, not discoveries',
                    'ledger_hash_algorithm':'sha256-chain-v1','model':fit(rows[:n])}
            record['model_hash']=digest(record)
            atomic_json(path,record)
        if record['model_hash']!=digest({k:v for k,v in record.items() if k!='model_hash'}):raise ValueError('frozen model corrupted')
        models.append(record)
    evaluations=[]
    for record in models[:-1]:
        n=record['through']; path=history/f'eval-{n:09d}.json'
        input_hash=digest([r['hash'] for r in rows[n:n+BOUNDARY]])
        if path.exists():
            evaluation=json.loads(path.read_text())
            if (evaluation.get('model_hash')!=record['model_hash']
                    or evaluation.get('evaluation_ledger_hash')!=input_hash
                    or evaluation.get('evaluation_hash')!=digest({k:v for k,v in evaluation.items() if k!='evaluation_hash'})):
                raise ValueError('frozen evaluation changed')
        else:
            evaluation={'model_hash':record['model_hash'],'from':n+1,'through':n+BOUNDARY,
                        'evaluation_ledger_hash':input_hash,
                        'results':evaluate(record['model'],rows[n:n+BOUNDARY])}
            evaluation['evaluation_hash']=digest(evaluation)
            atomic_json(path,evaluation)
        evaluations.append(evaluation)
    report={'schema':SCHEMA,'mode':'shadow','observed_tasks':len(rows),'through':through,
            'source_hash':source_hash,'history':str(history.relative_to(data)),
            'model_count':len(models),'completed_evaluations':len(evaluations),
            'latest_model_hash':models[-1]['model_hash'] if models else None,
            'first_training_boundary':first if models else None,
            'feature_model':'shared mathematical features with exact shell bounds; unseen geometry remains withheld',
            'latest_evaluation':evaluations[-1] if evaluations else None,
            'promotion':{'allowed':False,'reason':'Prediction validation is not controlled search-policy validation. No discovery advantage established.'},
            'next_boundary':through+BOUNDARY,
            'limitations':['Arrival order is not dispatch time.','Held-out errors describe submitted tasks, not an unbiased sampling population.',
                          'Server CPU is not browser cost.','Counts are correlated within geometry; exact tests are a surrogate only.',
                          'No production exclusions, seed changes, leaderboard changes or automatic promotion.']}
    atomic_json(data/'learning/latest.json',report)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data',type=Path,default=ROOT/'data')
    args=parser.parse_args();r=publish(args.data)
    print(f"Shadow models: {r['model_count']}; frozen future evaluations: {r['completed_evaluations']}; production policy unchanged")
