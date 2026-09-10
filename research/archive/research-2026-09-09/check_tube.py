#!/usr/bin/env python3
"""Tiny exact geometry audit; no quotient enumeration or solution search.

Compare a deliberately loose certified tube enumeration with a complete
positive coefficient rectangle containing the same norm/shape cells.
All membership and exclusion decisions use integer/rational arithmetic.
"""
from fractions import Fraction as F
from math import isqrt, ceil, exp, log, pi, sqrt
import json
from pathlib import Path

S = 10**18
P = 4848807585839879338
AL, AH = F(P-1, S), F(P+1, S)
assert AL**3 < 114 < AH**3

def icbrt(n):
    lo, hi = 0, 1 << ((n.bit_length()+2)//3)
    while lo < hi:
        m = (lo+hi+1)//2
        if m*m*m <= n: lo = m
        else: hi = m-1
    return lo

def ceil_sqrt(x):
    q = isqrt(x.numerator//x.denominator)
    return q + (F(q*q) < x)

def norm(a,b,c):
    return a*a*a + 114*b*b*b + 12996*c*c*c - 342*a*b*c

def member(a,b,c,ell,dlo,dhi,llo,lhi):
    if (a+4*b+16*c) % ell: return False
    n=norm(a,b,c)
    if not ell*dlo < n <= ell*dhi: return False
    lower=a*S*S+b*(P-1)*S+c*(P-1)**2
    upper=a*S*S+b*(P+1)*S+c*(P+1)**2
    lower, upper = lower**3, upper**3
    qlo, qhi = llo*n*S**6, lhi*n*S**6
    if lower > qlo and upper <= qhi: return True
    if upper <= qlo or lower > qhi: return False
    raise AssertionError("ambiguous phase: refine the isolating interval")

def cell(ell,dlo=128,dhi=512,llo=28,lhi=1000):
    nlo,nhi=ell*dlo,ell*dhi
    smin=icbrt(nlo*llo)
    smax=icbrt(nhi*lhi)+1
    wmax=ceil_sqrt(F(nhi,smin))
    abcmax=[ceil(F(smax+2*wmax,3)/p) for p in [1,AL,AL*AL]]
    # lambda>4 implies s>2w, so every coefficient is strictly positive.
    assert llo>4
    oracle=set()
    for c in range(1,abcmax[2]+1):
        for b in range(1,abcmax[1]+1):
            for a in range(1,abcmax[0]+1):
                if member(a,b,c,ell,dlo,dhi,llo,lhi): oracle.add((a,b,c))
    tube=set(); rows=0; kept_rows=0; positions=0
    for c in range(1,abcmax[2]+1):
        for b in range(1,abcmax[1]+1):
            rows+=1
            delta_lo,delta_hi=AL*b-AH*AH*c, AH*b-AL*AL*c
            near=0 if delta_lo<=0<=delta_hi else min(abs(delta_lo),abs(delta_hi))
            radial=F(wmax*wmax)-F(3,4)*near*near
            if radial<0: continue
            kept_rows+=1
            rad=ceil_sqrt(radial)
            mlo,mhi=(AL*b+AL*AL*c)/2,(AH*b+AH*AH*c)/2
            amin=max(1,ceil(mlo-rad)); amax=min(abcmax[0],(mhi+rad).__floor__())
            # Exact lattice congruence skips a positions outside J^j.
            amin += (-4*b-16*c-amin)%ell
            for a in range(amin,amax+1,ell):
                positions+=1
                if member(a,b,c,ell,dlo,dhi,llo,lhi): tube.add((a,b,c))
    assert tube==oracle, (ell,oracle-tube,tube-oracle)
    return dict(ell=ell,divisor_interval=[dlo,dhi],lambda_interval=[llo,lhi],
                abcmax=abcmax,rectangle_positions=abcmax[0]*abcmax[1]*abcmax[2],
                rows=rows,rows_after_circle_bound=kept_rows,
                lattice_positions_after_circle_bound=positions,
                exact_cell_coefficients=len(oracle),complete_set_equality=True)

def main():
    d0=10**19//54
    alpha=114**(1/3)
    beta=4133238949+852423792*alpha+175800705*alpha**2
    nmax=25*8*d0
    sm=nmax**(1/3)*exp(7)
    wm=nmax**(1/3)*exp(-1.1/2)
    amax=ceil((sm+2*wm)/3)
    bmax=ceil((sm+2*wm)/(3*alpha))
    cmax=ceil((sm+2*wm)/(3*alpha**2))
    result=dict(scope="exact small geometry only; no q or square checking",
      cells=[cell(e,d,4*d,l,h) for e in (1,5,25)
             for d in (128,1024) for l,h in ((5,28),(28,1000))],
      illustrative_floating_geometry=dict(regulator=log(beta),
        canonical_phase=[-2*log(beta)/3,log(beta)/3],
        proposed_phase=[1.1,7.0],
        normalized_continuous_volume_all_three_classes=6*pi*(7*d0)*5.9/sqrt(350892),
        conservative_floating_abc_bounds=[amax,bmax,cmax],
        sum_absolute_norm_terms_bits=(amax**3+114*bmax**3+12996*cmax**3+342*amax*bmax*cmax).bit_length()))
    target=Path(__file__).with_name('tube-audit.json')
    target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
