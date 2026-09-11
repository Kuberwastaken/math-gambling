"""Regularized shared-feature log-rate regression for unseen task geometry.

No discovery labels; bounded recent training window, no holdout fitting, no
production promotion. Pure Python and deterministic for a fixed input order.
"""
import math
from search_features import vector,certified_empty

TARGETS=('cpu_ms','quotient_points','curves','exact_tests')
MAX_ROWS=32768


def solve(matrix, rhs):
    a=[list(row)+[value] for row,value in zip(matrix,rhs)];n=len(a)
    for i in range(n):
        pivot=max(range(i,n),key=lambda j:abs(a[j][i]));a[i],a[pivot]=a[pivot],a[i]
        if abs(a[i][i])<1e-14:raise ValueError('singular regularized model')
        d=a[i][i];a[i]=[x/d for x in a[i]]
        for j in range(n):
            if j==i:continue
            d=a[j][i]
            a[j]=[x-d*y for x,y in zip(a[j],a[i])]
    out=[row[-1] for row in a]
    if not all(math.isfinite(x) for x in out):raise ValueError('nonfinite fitted model')
    return out


def fit_shared(rows, reference):
    # Holdout membership is independent of counters. Keep it withheld forever.
    train=[r for r in rows if not r['features'][3] and 'task' in r][-MAX_ROWS:]
    if not train:return None
    n=len(vector(train[0]['task']));gram=[[0.]*n for _ in range(n)];rhs={t:[0.]*n for t in TARGETS}
    for row in train:
        x=vector(row['task'])
        baseline=predict_reference(reference,row['task'])
        for i in range(n):
            for j in range(i,n):gram[i][j]+=x[i]*x[j]
        for t in TARGETS:
            y=math.log1p(row['y'][t])-math.log1p(baseline[t])
            for i in range(n):rhs[t][i]+=x[i]*y
    # Penalty scales with n: repeated correlated observations cannot erase it.
    for i in range(n):
        for j in range(i):gram[i][j]=gram[j][i]
        gram[i][i]+=max(1.,len(train)*.002) if i else 1e-6
    return {'schema':'mg114-shared-features-v1','training_tasks':len(train),'max_training_tasks':MAX_ROWS,
            'target':'log1p residual over proof-aware baseline; counters and CPU, not discovery probability',
            'reference':reference,
            'coefficients':{t:solve(gram,rhs[t]) for t in TARGETS}}


def predict_shared(model,task):
    x=vector(task)
    baseline=predict_reference(model['reference'],task)
    result={t:max(0.,math.expm1(max(0.,min(40.,math.log1p(baseline[t])+math.fsum(a*b for a,b in zip(x,model['coefficients'][t])))))) for t in TARGETS}
    if certified_empty(task):
        for t in TARGETS[1:]:result[t]=0.
    return result


def fit_reference(rows):
    """Strong baseline: exact emptiness plus log-context conditional means."""
    groups={}
    for r in [r for r in rows if not r['features'][3] and 'task' in r][-MAX_ROWS:]:
        empty=certified_empty(r['task'])
        for key in ('*',str(empty),r['task']['context']+':'+str(empty)):
            cell=groups.setdefault(key,{'n':0,'sum':dict.fromkeys(TARGETS,0.)});cell['n']+=1
            for t in TARGETS:cell['sum'][t]+=math.log1p(r['y'][t])
    return groups


def predict_reference(groups,task):
    empty=certified_empty(task);g=groups.get(str(empty),groups.get('*'))
    if not g:return None
    c=groups.get(task['context']+':'+str(empty),{'n':0,'sum':dict.fromkeys(TARGETS,0.)})
    result={t:math.expm1((c['sum'][t]+32*g['sum'][t]/g['n'])/(c['n']+32)) for t in TARGETS}
    if empty:
        for t in TARGETS[1:]:result[t]=0.
    result['cpu_ms']=max(.01,result['cpu_ms'])
    return result
