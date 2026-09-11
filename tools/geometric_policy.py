"""Geometry-weighted curve exposure/cost. A declared prior, never winning odds."""
import math
import statistics
from collections import defaultdict
from functools import lru_cache
from search_core import CONTEXTS, CONTEXT_BY_ID, D0

VERSION='mg114-geometric-cost-v1'
EXPLORATION=.4
PRIOR_TASKS=32
RECENT_PER_CONTEXT=256
KAPPA=1/(2**(1/3)-1)

@lru_cache(maxsize=32)
def mass(low,high):
    """Integral of 1/sqrt(4*t^3-1), with canonical-ordering cutoff.

    Numerical quadrature is used ONLY in the preference model. It never changes
    exact quotient endpoints or prunes any candidate.
    """
    low=max(float(low),KAPPA);high=float(high)
    if high<=low:return 0.
    a=1/math.sqrt(high);b=1/math.sqrt(low);n=256;h=(b-a)/n
    f=lambda u:2/math.sqrt(4-u**6)
    return h/3*(f(a)+f(b)+math.fsum((4 if i%2 else 2)*f(a+i*h) for i in range(1,n)))

def prior_value(context):
    # Representative D approximates per-curve inverse-D exposure within a 2x shell.
    # Geometric midpoint is within sqrt(2) of either endpoint, not an exact density.
    d=math.sqrt(int(context['dlo'])*int(context['dhi']))
    return mass(context['low'],context['high'])*D0/d

def calibrate(tasks,epoch):
    through=epoch*64;observations=defaultdict(list)
    for item in tasks[:through]:
        result=item['result'];context=result['task']['context'];cpu=item['server_replay_cpu_ms']
        if context not in CONTEXT_BY_ID or isinstance(cpu,bool) or not isinstance(cpu,(float,int)) or not math.isfinite(cpu) or cpu<=0:
            raise ValueError('invalid verified cost/context')
        curves=result['counters'].get('curves',0)
        if type(curves) is not int or curves<0:raise ValueError('invalid verified curve count')
        observations[context].append((float(cpu),curves))
    recent={key:values[-RECENT_PER_CONTEXT:] for key,values in observations.items()}
    all_values=[v for values in recent.values() for v in values]
    mean_cpu=math.fsum(x[0] for x in all_values)/len(all_values) if all_values else 1.
    mean_curves=math.fsum(x[1] for x in all_values)/len(all_values) if all_values else 1.
    # When no usable curve has ever been observed, retain a small nonzero prior.
    prior_curves=max(mean_curves,1.)
    scores={};entries={}
    for context in CONTEXTS:
        key=context['id'];values=recent.get(key,[])
        cpu=math.fsum(x[0] for x in values);curves=sum(x[1] for x in values)
        expected_curves=(curves+PRIOR_TASKS*prior_curves)/(len(values)+PRIOR_TASKS)
        expected_cpu=(cpu+PRIOR_TASKS*mean_cpu)/(len(values)+PRIOR_TASKS)
        score=prior_value(context)*expected_curves/expected_cpu
        if not math.isfinite(score) or score<=0:raise ValueError('invalid geometric preference')
        scores[key]=score
        entries[key]={'id':key,'sample_size':len(observations.get(key,[])),
            'recent_samples':len(values),'zero_curve_tasks':sum(n==0 for _,n in values),
            'aggregate_cpu_ms':cpu,'aggregate_curves':curves,
            'predicted_curves_per_task':expected_curves,'predicted_cpu_ms_per_task':expected_cpu,
            'geometric_prior_per_curve':prior_value(context),'robust_cpu_ms':statistics.median(x[0] for x in values) if values else None}
    total=math.fsum(scores.values());contexts=[]
    for key in sorted(entries):
        exploit=scores[key]/total
        contexts.append({**entries[key],'weight':EXPLORATION/81+(1-EXPLORATION)*exploit,
                         'exploration_weight':1/81,'exploit_weight':exploit})
    return {'schema':'math-gambling-strategy-v1','policy_version':VERSION,'epoch':epoch,
            'through_verified_tasks':through,'epoch_size':64,'exploration_fraction':EXPLORATION,
            'objective':'geometrically weighted curve exposure per trusted CPU; uncalibrated prior, not discovery probability',
            'reason':'40% uniform task proposals; 60% geometry-weighted curve yield / cost. Zero-curve tasks count toward cost. 32-task shrinkage, latest 256 observations per context.',
            'assumptions':['Band weight integrates 1/sqrt(4*t^3-1) above canonical ordering cutoff.',
                'Inverse D uses each shell geometric midpoint, not actual per-root D.',
                'Root exchangeability within selected norm families is unvalidated.',
                'Selection fractions are not CPU-time fractions; server cost differs from browser cost.'],
            'contexts':contexts}


def cpu_budget_policy(policy):
    """Convert explicit CPU shares to proposal probabilities. All contexts remain.

    Predicted shares are exact under these cost estimates, not guarantees for a
    different device. A separate benchmark must authorize production migration.
    """
    contexts=policy['contexts'];rates=[]
    for c in contexts:
        cost=c['predicted_cpu_ms_per_task']
        if not math.isfinite(cost) or cost<=0:raise ValueError('invalid CPU prediction')
        rates.append(c['exploration_weight']*EXPLORATION+(1-EXPLORATION)*c['exploit_weight'])
    proposals=[share/c['predicted_cpu_ms_per_task'] for share,c in zip(rates,contexts)]
    total=math.fsum(proposals)
    return {**policy,'policy_version':'mg114-cpu-budget-v1','exploration_unit':'predicted_cpu',
        'objective':'geometry-weighted exposure proxy per reference CPU; 40% predicted CPU exploration reserve',
        'proposal_preflight':'mg114-shell-tile-v1',
        'reason':'40% of predicted CPU is reserved equally across contexts; 60% follows geometric exposure/cost. All contexts retain support. Device costs may differ.',
        'contexts':[{**c,'weight':p/total,'target_cpu_share':share} for c,p,share in zip(contexts,proposals,rates)],
        'assumptions':policy['assumptions']+['CPU quotas use measured reference costs; actual device shares must be monitored.']}
