"""Persistent contextual execution learning for a conditional root-exposure proxy.

No solution labels are learned. No score is a probability of solving114. This
module never excludes candidates and never replaces the controller's reserved
exploration worker-time quota. Reported exposure need not represent unique roots.
"""
from __future__ import annotations

from functools import lru_cache
import copy
import math
import statistics

VERSION=1
KAPPA=1/(2**(1/3)-1)
RECENT=9
PRIOR_JOBS=3.0
RIDGE=2.0
MAX_RATE=1e100
MAX_TOTAL=1e200


def _finite(value,name,nonnegative=False):
    value=float(value)
    if not math.isfinite(value) or (nonnegative and value<0):
        raise ValueError(f"{name} must be finite"+(" and nonnegative" if nonnegative else ""))
    return value


def _integral(a,b,n=256):
    if a==b:return 0.0
    h=(b-a)/n
    def f(u):return 2/math.sqrt(4-u**6)
    return h/3*(f(a)+f(b)+sum((4 if i%2 else 2)*f(a+i*h) for i in range(1,n)))


_UMAX=1/math.sqrt(KAPPA)
_NORMALIZER=_integral(0,_UMAX)


@lru_cache(maxsize=256)
def geometric_mass(low,high):
    """Normalized integral of1/sqrt(4t³−1) on[max(low,kappa),high].

    The u=1/sqrt(t) substitution gives smooth integrand2/sqrt(4−u^6).
    Numerical quadrature defines a weight model only, never an exclusion rule.
    """
    low=_finite(low,"low",True)
    high=float(high)
    if math.isnan(high) or high<low:raise ValueError("high must be >=low")
    if high<=KAPPA:return 0.0
    a=0.0 if math.isinf(high) else 1/math.sqrt(high)
    b=1/math.sqrt(max(low,KAPPA))
    return min(1.0,max(0.0,_integral(a,b)/_NORMALIZER))


def _factor(spec):
    return (int(spec['ell']),
            (int(spec['tlo']),int(spec['thi']),int(spec['radius'])),
            (int(spec['dlo']),int(spec['dhi'])),
            (float(spec['low']),float(spec['high'])))


def _key(spec):
    key=str(spec['key'])
    if not key:raise ValueError("Empty arm key")
    return key


def _solve(matrix,rhs):
    """Small positive-definite ridge system, pivoted Gaussian elimination."""
    n=len(rhs);a=[list(row)+[rhs[i]] for i,row in enumerate(matrix)]
    for i in range(n):
        pivot=max(range(i,n),key=lambda j:abs(a[j][i]))
        a[i],a[pivot]=a[pivot],a[i]
        if abs(a[i][i])<1e-15:raise ArithmeticError("Singular ridge system")
        v=a[i][i]
        for j in range(i,n+1):a[i][j]/=v
        for k in range(i+1,n):
            v=a[k][i]
            if v:
                for j in range(i,n+1):a[k][j]-=v*a[i][j]
    answer=[0.0]*n
    for i in range(n-1,-1,-1):answer[i]=a[i][n]-sum(a[i][j]*answer[j] for j in range(i+1,n))
    return answer


class Model:
    """Robust empirical exposure/cost plus contextual ridge shrinkage.

    Features are categorical class, shape, divisor shell and quotient band,
    with shape×shell and shell×band interactions. Ridge predicts log exposure
    throughput. The analytically specified geometric mass is applied afterward.
    """
    @classmethod
    def initial(cls,specs):
        self=cls();self.specs={};self.arms={}
        for spec in specs:
            key=_key(spec)
            if key in self.specs:raise ValueError("Duplicate arm key")
            factors=_factor(spec)
            if factors[0] not in (1,5,25) or factors[1][0]>factors[1][1] or factors[2][0]>=factors[2][1]:
                raise ValueError("Invalid class, shape or divisor shell")
            if geometric_mass(spec['low'],spec['high'])<=0:raise ValueError("Arm has zero geometric model mass")
            self.specs[key]=copy.deepcopy(spec)
            self.arms[key]=dict(jobs=0,elapsed=0.0,exposure=0.0,rows=0,recent_rates=[],recent_elapsed=[])
        if not self.specs:raise ValueError("At least one arm is required")
        self.levels=[sorted({_factor(s)[i] for s in self.specs.values()}) for i in range(4)]
        self._features={k:self._feature(s) for k,s in self.specs.items()}
        self._cache=None
        return self

    def _feature(self,spec):
        factors=_factor(spec)
        onehots=[[float(factors[i]==level) for level in self.levels[i][1:]] for i in range(4)]
        x=[1.0]+[v for group in onehots for v in group]
        for i,j in ((1,2),(2,3)):
            x.extend(a*b for a in onehots[i] for b in onehots[j])
        return x

    def _check_spec(self,spec):
        key=_key(spec)
        if key not in self.specs or _factor(spec)!=_factor(self.specs[key]):
            raise ValueError("Unknown or changed arm specification")
        return key

    def observe(self,spec,elapsed,exposure_sum,rows,stats=None):
        """Add one completed measurement; failures/partial jobs must not be passed.

        stats is accepted for the controller API; it cannot train a success label.
        Raw aggregate exposure and time remain unmodified for auditability.
        """
        key=self._check_spec(spec)
        elapsed=_finite(elapsed,"elapsed")
        exposure=_finite(exposure_sum,"exposure_sum",True)
        if elapsed<=0:raise ValueError("elapsed must be positive")
        row_count=int(rows) if isinstance(rows,(int,float)) else len(rows)
        if row_count<0:raise ValueError("rows must be nonnegative")
        rate=exposure/elapsed
        if not math.isfinite(rate) or rate>MAX_RATE:raise ValueError("Exposure rate exceeds numerical model range")
        old=self.arms[key]
        if old['elapsed']+elapsed>MAX_TOTAL or old['exposure']+exposure>MAX_TOTAL or old['jobs']>=2**63-1:
            raise ValueError("Aggregate overflow")
        old['jobs']+=1;old['elapsed']+=elapsed;old['exposure']+=exposure;old['rows']+=row_count
        old['recent_rates']=(old['recent_rates']+[rate])[-RECENT:]
        old['recent_elapsed']=(old['recent_elapsed']+[elapsed])[-RECENT:]
        self._cache=None

    @staticmethod
    def _measured(arm):
        if not arm['jobs']:return 0.0
        aggregate=arm['exposure']/arm['elapsed']
        if len(arm['recent_rates'])>=3:
            median=statistics.median(arm['recent_rates'])
            # Preserve raw totals. A cost-weighted recent aggregate clips
            # rate outliers around the median and can follow sustained changes.
            clipped=[min(max(rate,median/4),median*4) for rate in arm['recent_rates']]
            aggregate=sum(rate*dt for rate,dt in zip(clipped,arm['recent_elapsed']))/sum(arm['recent_elapsed'])
        return aggregate

    def _fit(self):
        if self._cache is not None:return self._cache
        measured=[self._measured(a) for a in self.arms.values() if a['jobs']]
        positive=[v for v in measured if v>0]
        # Median arm scale prevents a single timing outlier from poisoning
        # every cold-arm prediction. Zeros still train their own arm/factors.
        global_rate=max(1e-12,statistics.median(positive) if positive else 1e-12)
        log_base=math.log(global_rate)
        n=len(next(iter(self._features.values())))
        matrix=[[RIDGE if i==j else 0.0 for j in range(n)] for i in range(n)]
        rhs=[0.0]*n
        for key,arm in self.arms.items():
            jobs=arm['jobs']
            if not jobs:continue
            # The pseudodata is a numerical shrinkage prior, not a Bayesian
            # confidence claim about solutions or independent root draws.
            measured=self._measured(arm)
            smoothed=(jobs*measured+PRIOR_JOBS*global_rate)/(jobs+PRIOR_JOBS)
            y=math.log(max(smoothed,global_rate*1e-12))-log_base
            weight=min(jobs,12)
            x=self._features[key]
            active=[i for i,v in enumerate(x) if v]
            for i in active:
                rhs[i]+=weight*x[i]*y
                for j in active:matrix[i][j]+=weight*x[i]*x[j]
        beta=_solve(matrix,rhs)
        predictions={}
        for key,x in self._features.items():
            shift=max(-math.log(1e6),min(math.log(1e6),sum(v*b for v,b in zip(x,beta))))
            predictions[key]=global_rate*math.exp(shift)
        self._cache=(global_rate,predictions)
        return self._cache

    def scores(self,specs,in_flight=None):
        """Return positive proxy utility rates, discounted by1+pending jobs.

        The pending discount is an execution heuristic, not an optimality proof.
        The caller must enforce the independent exploration time quota.
        """
        _,predictions=self._fit();result={}
        in_flight=in_flight or {}
        for spec in specs:
            key=self._check_spec(spec);arm=self.arms[key]
            prior_weight=PRIOR_JOBS/(arm['jobs']+PRIOR_JOBS)
            rate=(1-prior_weight)*self._measured(arm)+prior_weight*predictions[key]
            pending=in_flight.get(key,0)
            if not isinstance(pending,int) or pending<0:raise ValueError("Pending counts must be nonnegative integers")
            score=geometric_mass(spec['low'],spec['high'])*rate/(1+pending)
            if not math.isfinite(score):raise ArithmeticError("Nonfinite model score")
            result[key]=max(1e-300,score)
        return result

    def to_dict(self):
        return dict(version=VERSION,specs=copy.deepcopy(list(self.specs.values())),
                    arms=copy.deepcopy(self.arms),interpretation='Conditional root-exposure/cost proxy; not solution probabilities.')

    @classmethod
    def from_dict(cls,payload):
        if payload.get('version')!=VERSION:raise ValueError("Unsupported model version")
        self=cls.initial(payload['specs'])
        if set(payload['arms'])!=set(self.arms):raise ValueError("Serialized arm mismatch")
        for key,arm in payload['arms'].items():
            jobs=arm['jobs'];rows=arm['rows']
            if not isinstance(jobs,int) or not 0<=jobs<2**63 or not isinstance(rows,int) or rows<0:raise ValueError("Invalid serialized counts")
            elapsed=_finite(arm['elapsed'],'elapsed',True);exposure=_finite(arm['exposure'],'exposure',True)
            recent=[_finite(r,'recent rate',True) for r in arm['recent_rates']]
            times=[_finite(t,'recent elapsed') for t in arm['recent_elapsed']]
            if len(recent)>RECENT or len(recent)!=min(jobs,RECENT) or (jobs and elapsed<=0):raise ValueError("Invalid serialized history")
            if len(times)!=len(recent) or any(t<=0 or t>MAX_TOTAL for t in times):raise ValueError("Invalid serialized elapsed history")
            if elapsed>MAX_TOTAL or exposure>MAX_TOTAL or any(r>MAX_RATE for r in recent) or (jobs and exposure/elapsed>MAX_RATE):raise ValueError("Serialized state exceeds numerical model range")
            if not jobs and (elapsed or exposure or rows):raise ValueError("Nonempty totals for unobserved arm")
            self.arms[key]=dict(jobs=jobs,rows=rows,elapsed=elapsed,exposure=exposure,recent_rates=recent,recent_elapsed=times)
        return self


def initial(specs):return Model.initial(specs)


def _ranks(values):
    order=sorted(range(len(values)),key=lambda i:values[i]);r=[0.0]*len(values)
    i=0
    while i<len(order):
        j=i+1
        while j<len(order) and values[order[j]]==values[order[i]]:j+=1
        for n in range(i,j):r[order[n]]=(i+j-1)/2
        i=j
    return r


def _correlation(x,y):
    mx=statistics.mean(x);my=statistics.mean(y)
    xx=sum((v-mx)**2 for v in x);yy=sum((v-my)**2 for v in y)
    if xx==0 or yy==0:return 0.0
    return sum((a-mx)*(b-my) for a,b in zip(x,y))/math.sqrt(xx*yy)


def evaluate(records):
    """First two measurements/arm train; third is untouched proxy holdout.

    The gate evaluates measured exposure utility, not solution-location accuracy.
    No third-record result is fed back into the trained model during evaluation.
    """
    groups={};specs={}
    for row in records:
        key=_key(row['spec']);specs.setdefault(key,row['spec']);groups.setdefault(key,[]).append(row)
        if _factor(specs[key])!=_factor(row['spec']):raise ValueError("Changed specification in records")
    if not specs:return dict(enable_model=False,reasons=['No records'],contexts=0)
    model=Model.initial(list(specs.values()))
    for key,rows in groups.items():
        for row in rows[:2]:model.observe(row['spec'],row['elapsed'],row['exposure_sum'],row['rows'],row.get('stats'))
    held=[rows[2] for rows in groups.values() if len(rows)>=3]
    result=dict(enable_model=False,contexts=len(specs),heldout_contexts=len(held),
                split='First2/context train, third/context held out; later records ignored.',
                interpretation='Held-out conditional root-exposure utility only; no solution probabilities or causal discovery claim.',
                thresholds=dict(min_contexts=12,spearman=.2,top_quarter_gain=1.05,
                                best_arm_gain=1.0,calibration_ratio=[.25,4.0]),reasons=[])
    if not held:
        result['reasons']=['No third-record holdouts'];return result
    selected_specs=[r['spec'] for r in held];pred=model.scores(selected_specs,{})
    weights=[float(s.get('weight',1.0)) for s in selected_specs]
    if any(not math.isfinite(w) or w<0 for w in weights) or sum(weights)<=0:raise ValueError("Invalid baseline weights")
    total=sum(weights);weights=[w/total for w in weights]
    observed=[]
    for row in held:
        elapsed=_finite(row['elapsed'],'heldout elapsed')
        exposure=_finite(row['exposure_sum'],'heldout exposure',True)
        if elapsed<=0:raise ValueError("Nonpositive heldout elapsed")
        rate=exposure/elapsed
        if not math.isfinite(rate) or rate>MAX_RATE:raise ValueError("Heldout rate exceeds numerical model range")
        observed.append(geometric_mass(row['spec']['low'],row['spec']['high'])*rate)
    predicted=[pred[_key(s)] for s in selected_specs]
    baseline=sum(w*y for w,y in zip(weights,observed))
    predicted_total=sum(w*y for w,y in zip(weights,predicted))
    order=sorted(range(len(held)),key=lambda i:(-predicted[i],_key(selected_specs[i])))
    top=order[:max(1,math.ceil(len(order)/4))]
    top_mean=statistics.mean(observed[i] for i in top)
    geometry_order=sorted(range(len(held)),key=lambda i:(-geometric_mass(selected_specs[i]['low'],selected_specs[i]['high']),_key(selected_specs[i])))
    geometry_top=statistics.mean(observed[i] for i in geometry_order[:len(top)])
    best=observed[order[0]]
    spearman=_correlation(_ranks(predicted),_ranks(observed))
    positive_errors=[abs(math.log(p/y)) for p,y in zip(predicted,observed) if p>0 and y>0]
    calibration=predicted_total/baseline if baseline>0 else None
    result.update(balanced_baseline_utility=baseline,predicted_weighted_utility=predicted_total,
                  prediction_to_observation_ratio=calibration,spearman=spearman,
                  median_absolute_log_error=statistics.median(positive_errors) if positive_errors else None,
                  top_quarter_observed_utility=top_mean,best_predicted_arm_observed_utility=best,
                  geometry_only_top_quarter_utility=geometry_top,
                  contextual_over_geometry_only=top_mean/geometry_top if geometry_top>0 else None,
                  top_quarter_over_baseline=top_mean/baseline if baseline>0 else None,
                  best_over_baseline=best/baseline if baseline>0 else None,
                  zero_exposure_holdouts=sum(v==0 for v in observed),
                  rows=[dict(key=_key(s),predicted_utility=p,observed_utility=y,baseline_weight=w)
                        for s,p,y,w in zip(selected_specs,predicted,observed,weights)])
    checks=[(len(held)==len(specs) and len(held)>=12,'Need at least12 complete whole-arm holdouts'),
            (baseline>0,'No positive heldout exposure utility'),
            (spearman>=.2,'Heldout rank correlation below0.2'),
            (baseline>0 and top_mean>=1.05*baseline,'Predicted top-quarter failed1.05×baseline gate'),
            (baseline>0 and best>=baseline,'Predicted best arm underperformed baseline'),
            (calibration is not None and .25<=calibration<=4,'Prediction calibration outside0.25–4')]
    result['reasons']=[message for passed,message in checks if not passed]
    result['enable_model']=not result['reasons']
    return result
