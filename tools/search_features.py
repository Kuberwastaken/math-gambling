"""Exact conservative tile bounds and shared, pre-computation ML features.

Only certified_empty may exclude a proposal. Floating point features never prune.
"""
import math
from search_core import ALPHA, ALPHA2, SCALE, CONTEXT_BY_ID, ROWS_PER_TASK, BLOCK_SIZE, validate_task

assert ALPHA**3 <= 114*SCALE**3 < (ALPHA+1)**3
# The engine's alpha^2 approximation is rounded UP by one scaled unit.
ALPHA2_LO = ALPHA2-1
assert ALPHA2_LO**3 <= 12996*SCALE**3 < (ALPHA2_LO+1)**3


def add(a,b): return a[0]+b[0],a[1]+b[1]
def mul(a,b):
    v=[a[0]*b[0],a[0]*b[1],a[1]*b[0],a[1]*b[1]]
    return min(v),max(v)
def scale(a,n): return mul(a,(n,n))
def square(a): return (0 if a[0]<=0<=a[1] else min(a[0]**2,a[1]**2),max(a[0]**2,a[1]**2))


def norm_bounds(task):
    """Bounds on N*SCALE^3 over every generator, split at row wrap.

    u=a+alpha*b+alpha^2*c, v=alpha*b+alpha^2*c,
    w=alpha^2*b^2+114*b*c+114*alpha*c^2; N=u*(u^2-3*v*u+3*w).
    offset_base rounds on an ell lattice, hence u is within ell/2 of ell*t,
    plus the explicitly bounded error of its rational alpha approximations.
    """
    task=validate_task(task);c=CONTEXT_BY_ID[task['context']];r=c['radius'];width=2*r+1
    start=int(task['row']);end=min(start+ROWS_PER_TASK,int(c['totalRows']))
    tlo=c['tlo']+BLOCK_SIZE*task['block'];thi=min(tlo+BLOCK_SIZE-1,c['thi'])
    ell=c['ell'];bounds=[]
    while start<end:
        stop=min(end,(start//width+1)*width)
        b=(start%width-r,(stop-1)%width-r);cc=start//width-r
        error=max(abs(b[0]),abs(b[1]))+abs(cc)
        u=(ell*tlo*SCALE-ell*SCALE//2-error,ell*thi*SCALE+ell*SCALE//2+error)
        v=add(mul((ALPHA,ALPHA+1),b),scale((ALPHA2_LO,ALPHA2_LO+1),cc))
        w=add(add(mul((ALPHA2_LO,ALPHA2_LO+1),square(b)),scale(b,114*cc*SCALE)),scale((ALPHA,ALPHA+1),114*cc*cc))
        q=add(add(square(u),scale(mul(v,u),-3)),scale(w,3*SCALE))
        bounds.append(mul(u,q));start=stop
    return min(x[0] for x in bounds),max(x[1] for x in bounds)


def certified_empty(task):
    lo,hi=norm_bounds(task);c=CONTEXT_BY_ID[task['context']]
    return hi<=c['ell']*int(c['dlo'])*SCALE**3 or lo>c['ell']*int(c['dhi'])*SCALE**3


def vector(task):
    task=validate_task(task);c=CONTEXT_BY_ID[task['context']];r=c['radius'];width=2*r+1;row=int(task['row'])
    b=(row%width-r)/r;cc=(row//width-r)/r
    t=(c['tlo']+BLOCK_SIZE*task['block']+7.5)/(c['thi']+1)
    lo,hi=norm_bounds(task);den=c['ell']*int(c['dhi'])*SCALE**3
    lower=lo/den;upper=hi/den
    clip=lambda x:max(-8.,min(8.,x))
    return [1.,b,cc,abs(b),abs(cc),b*cc,b*b,cc*cc,t,t*t,b*t,cc*t,
            c['shape']/2,c['shell']/2,math.log(c['ell'])/math.log(25),
            math.log1p(c['low'])/math.log(4097),math.log1p(c['high'])/math.log(4097),
            clip(lower),clip(upper),float(hi<=den//2 or lo>den)]
