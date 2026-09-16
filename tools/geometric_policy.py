"""Geometry-weighted curve exposure/cost. A declared prior, never winning odds."""
import math
import statistics
from collections import defaultdict
from functools import lru_cache
from search_core import CONTEXTS, CONTEXT_BY_ID, D0, ROWS_PER_TASK, task_rows

VERSION='mg114-geometric-cost-v1'
EXPLORATION=.4
# Revision 2 (17 September): the uniform reserve drops to 10% and band (256,4096]
# is retired to a nonzero trace weight. See docs/GEOMETRIC_POLICY.md.
REVISION=2
EXPLORATION_R2=.1
RETIRED_BANDS=((256,4096),)
RETIRED_WEIGHT=1e-6
PRIOR_TASKS=32
RECENT_PER_CONTEXT=256
KAPPA=1/(2**(1/3)-1)

RETIRED_IDS=tuple(c['id'] for c in CONTEXTS if (c['low'],c['high']) in RETIRED_BANDS)
ACTIVE_IDS=tuple(c['id'] for c in CONTEXTS if c['id'] not in RETIRED_IDS)

def exploration_fraction(revision=1):
    return EXPLORATION_R2 if revision>=2 else EXPLORATION

def _lanes(revision):
    """(supported ids, floor per supported id, scale applied to supported weights).

    Revision 1 keeps all 81 lanes in both the floor and the exploitation mix.
    Revision 2 supports 54 lanes; the 27 retired ones hold exactly RETIRED_WEIGHT
    and are excluded from the exploitation normalisation, so the supported share
    is rescaled to keep the published weights summing to one.
    """
    if revision<2:
        return tuple(c['id'] for c in CONTEXTS),1/81,1.
    return ACTIVE_IDS,1/len(ACTIVE_IDS),1-len(RETIRED_IDS)*RETIRED_WEIGHT

def v1_equivalent(task):
    """Cost/curve divisor that puts a v2 (1024-row) observation in v1 units."""
    return task_rows(task)/ROWS_PER_TASK

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

def calibrate(tasks,epoch,revision=1):
    through=epoch*64;observations=defaultdict(list)
    for item in tasks[:through]:
        result=item['result'];context=result['task']['context'];cpu=item['server_replay_cpu_ms']
        if context not in CONTEXT_BY_ID or isinstance(cpu,bool) or not isinstance(cpu,(float,int)) or not math.isfinite(cpu) or cpu<=0:
            raise ValueError('invalid verified cost/context')
        curves=result['counters'].get('curves',0)
        if type(curves) is not int or curves<0:raise ValueError('invalid verified curve count')
        # A v2 task carries eight v1 tiles of work; normalise both cost and yield
        # so mixed-engine ledgers predict per-v1-task quantities.
        try:
            divisor=v1_equivalent(result['task'])
        except (ValueError,KeyError,TypeError):
            divisor=1.
        observations[context].append((float(cpu)/divisor,curves/divisor))
    recent={key:values[-RECENT_PER_CONTEXT:] for key,values in observations.items()}
    all_values=[v for values in recent.values() for v in values]
    mean_cpu=math.fsum(x[0] for x in all_values)/len(all_values) if all_values else 1.
    mean_curves=math.fsum(x[1] for x in all_values)/len(all_values) if all_values else 1.
    # When no usable curve has ever been observed, retain a small nonzero prior.
    prior_curves=max(mean_curves,1.)
    supported,floor,scale=_lanes(revision)
    supported=set(supported)
    scores={};entries={}
    for context in CONTEXTS:
        key=context['id'];values=recent.get(key,[])
        cpu=math.fsum(x[0] for x in values);curves=math.fsum(x[1] for x in values)
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
    exploration=exploration_fraction(revision)
    total=math.fsum(scores[key] for key in scores if key in supported);contexts=[]
    for key in sorted(entries):
        if key not in supported:
            contexts.append({**entries[key],'weight':RETIRED_WEIGHT,'exploration_weight':0.,'exploit_weight':0.})
            continue
        exploit=scores[key]/total
        contexts.append({**entries[key],'weight':scale*(exploration*floor+(1-exploration)*exploit),
                         'exploration_weight':floor,'exploit_weight':exploit})
    policy={'schema':'math-gambling-strategy-v1','policy_version':VERSION,'epoch':epoch,
            'through_verified_tasks':through,'epoch_size':64,'exploration_fraction':exploration,
            'objective':'geometrically weighted curve exposure per trusted CPU; uncalibrated prior, not discovery probability',
            'reason':'40% uniform task proposals; 60% geometry-weighted curve yield / cost. Zero-curve tasks count toward cost. 32-task shrinkage, latest 256 observations per context.',
            'assumptions':['Band weight integrates 1/sqrt(4*t^3-1) above canonical ordering cutoff.',
                'Inverse D uses each shell geometric midpoint, not actual per-root D.',
                'Root exchangeability within selected norm families is unvalidated.',
                'Selection fractions are not CPU-time fractions; server cost differs from browser cost.'],
            'contexts':contexts}
    if revision>=2:
        policy.update(policy_revision=revision,retired_bands=[list(b) for b in RETIRED_BANDS],
            reason=('10% uniform task proposals across the 54 supported contexts; 90% geometry-weighted curve yield / cost. '
                    'Band (256,4096] is retired to a 1e-6 trace weight. Zero-curve tasks count toward cost. '
                    '32-task shrinkage, latest 256 observations per context, normalised to v1-equivalent (128-row) units.'))
        policy['assumptions']=policy['assumptions']+[
            'Mixed engine-v1/v2 observations are divided by task_rows/128 before calibration.',
            'The retired band keeps a 1e-6 trace weight so its lane is never formally excluded.']
    return policy


def cpu_budget_policy(policy,revision=1):
    """Convert explicit CPU shares to proposal probabilities. All contexts remain.

    Predicted shares are exact under these cost estimates, not guarantees for a
    different device. A separate benchmark must authorize production migration.
    """
    revision=max(revision,policy.get('policy_revision',1))
    exploration=exploration_fraction(revision)
    supported,_,scale=_lanes(revision);supported=set(supported)
    contexts=policy['contexts'];rates=[]
    for c in contexts:
        cost=c['predicted_cpu_ms_per_task']
        if not math.isfinite(cost) or cost<=0:raise ValueError('invalid CPU prediction')
        rates.append(0. if c['id'] not in supported else
                     c['exploration_weight']*exploration+(1-exploration)*c['exploit_weight'])
    proposals=[share/c['predicted_cpu_ms_per_task'] for share,c in zip(rates,contexts)]
    total=math.fsum(proposals)
    weights=[RETIRED_WEIGHT if c['id'] not in supported else scale*p/total for c,p in zip(contexts,proposals)]
    result={**policy,'policy_version':'mg114-cpu-budget-v1','exploration_unit':'predicted_cpu',
        'exploration_fraction':exploration,
        'objective':'geometry-weighted exposure proxy per reference CPU; 40% predicted CPU exploration reserve',
        'proposal_preflight':'mg114-shell-tile-v1',
        'reason':'40% of predicted CPU is reserved equally across contexts; 60% follows geometric exposure/cost. All contexts retain support. Device costs may differ.',
        'contexts':[{**c,'weight':w,'target_cpu_share':share} for c,w,share in zip(contexts,weights,rates)],
        'assumptions':policy['assumptions']+['CPU quotas use measured reference costs; actual device shares must be monitored.']}
    if revision>=2:
        result.update(policy_revision=revision,retired_bands=[list(b) for b in RETIRED_BANDS],
            objective=('geometry-weighted exposure proxy per reference CPU; 10% predicted CPU exploration reserve '
                       'across the 54 supported contexts, band (256,4096] retired to a trace weight'),
            reason=('10% of predicted CPU is reserved equally across the 54 supported contexts; 90% follows geometric '
                    'exposure/cost. Band (256,4096] holds ~0.6% of expected mass under this same density model for '
                    'about 14% of CPU, so it keeps only a 1e-6 trace weight rather than a CPU quota. The earlier 40% '
                    'reserve hedged against the density model that also justifies the search, which is not an honest '
                    'use of a reserve. Per-task cost is measured in v1-equivalent (128-row) units. Device costs may differ.'))
        result['assumptions']=result['assumptions']+[
            'Retiring a band is a scheduling decision only; no mathematical exclusion is claimed for it.']
    return result
