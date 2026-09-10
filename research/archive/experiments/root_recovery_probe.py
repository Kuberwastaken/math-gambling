#!/usr/bin/env python3
"""Small arithmetic-only root-failure audit. No curve search or production edits."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
spec=importlib.util.spec_from_file_location("plane_audit",ROOT/"validate_plane.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
PRIMES=[2,5,7,11,13,17,19,23,29,31,37,41,43,47,53,59,61,67,71,73,79,83,89,97]


def signed_filters(D):
    S=D if D%3==1 else -D
    bad8=S%2==0 and S%8!=2
    s=S%361
    bad361=s==0 or (s%19==0 and pow(2*pow(s//19,-1,19)%19,9,19)!=1)
    return bad8,bad361


def main():
    residues={p:[r for r in range(p) if r**3%p==114%p] for p in PRIMES}
    rows=[];recoveries=[]
    for family in ("box","plane"):
        for ell,br in [(1,50000),(5,85499),(25,146201)]:
            R=20000000 if family=="plane" else br
            w=2*R+1;t=5 if family=="plane" else 2*(R//ell)+1;total=w*w*t
            stride,offset=m.permutation(114,ell,R,total)
            stats=dict(family=family,ell=ell,radius=R,count=5000,symmetry_kept=0,
                       frontier_eligible=0,noninvertible=0,five_only_recoverable=0,
                       five_gamma_compatible=0,small_prime_impossible=0,
                       other_small_recoverable=0,residual_large_factor=0,
                       ordinary_root_candidates=0,ordinary_forbidden_signed8=0,
                       ordinary_forbidden_signed361=0,ordinary_forbidden_either=0,
                       five_recovered_forbidden_either=0,
                       small_branch_max=0,gcd_prime_histogram={})
            for index in range(1140000,1145000):
                v=(index*stride+offset)%total;u=v%t;v//=t;b=v%w-R;c=v//w-R
                if family=="plane":
                    residue=(-4*b-16*c)%ell;n=-m.P*b-m.Q*c-residue*m.DEN
                    h=(2*n+ell*m.DEN)//(2*ell*m.DEN);a=residue+ell*(h+u-2)
                    ro=(4*b+16*c)%ell;no=m.P*b+m.Q*c-ro*m.DEN
                    ao=ro+ell*((2*no+ell*m.DEN)//(2*ell*m.DEN))
                    duplicate=(c,b,a)<(0,0,0) and (-a-ao)%ell==0 and -2<=(-a-ao)//ell<=2
                else:
                    a=ell*(u-R//ell)+(-4*b-16*c)%ell;oo=(4*b+16*c)%ell
                    duplicate=(c,b,a)<(0,0,0) and (-a-oo)%ell==0 and abs((-a-oo)//ell)<=R//ell
                if duplicate:continue
                stats['symmetry_kept']+=1
                N=a**3+114*b**3+12996*c**3-342*a*b*c;D=abs(N)//ell
                if D<2 or D>2**63-1 or D%3==0:continue
                zmin=10**19 if D<=10**19//54 else 10**17
                if 64*D<=zmin:continue
                stats['frontier_eligible']+=1;C=b*b-a*c;g=math.gcd(C,D)
                if g==1:
                    bad8,bad361=signed_filters(D)
                    stats['ordinary_root_candidates']+=1
                    stats['ordinary_forbidden_signed8']+=bad8
                    stats['ordinary_forbidden_signed361']+=bad361
                    stats['ordinary_forbidden_either']+=bad8 or bad361
                    continue
                stats['noninvertible']+=1;remaining=g;factors=[]
                for p in PRIMES:
                    if remaining%p==0:
                        factors.append(p)
                        stats['gcd_prime_histogram'][p]=stats['gcd_prime_histogram'].get(p,0)+1
                        while remaining%p==0:remaining//=p
                if any(not residues[p] for p in factors) or (2 in factors and D%4==0) or (19 in factors and D%361==0):
                    stats['small_prime_impossible']+=1;continue
                if remaining!=1:
                    stats['residual_large_factor']+=1;continue
                if factors==[5]:
                    good=D;bad=1
                    while good%5==0:good//=5;bad*=5
                    B=114*c*c-a*b
                    r0=(B*pow(C,-1,good))%good if good>1 else 0
                    phi=bad//5*4;r5=pow(114,pow(3,-1,phi),bad)
                    root=(r0+good*((r5-r0)*pow(good,-1,bad)%bad))%D
                    assert pow(root,3,D)==114%D
                    compatible=(a+b*root+c*root*root)%D==0
                    stats['five_recovered_forbidden_either']+=any(signed_filters(D))
                    stats['five_only_recoverable']+=1;stats['five_gamma_compatible']+=compatible
                    recoveries.append(dict(family=family,ell=ell,index=index,D=D,r=root,
                                           gamma_compatible=compatible))
                else:
                    stats['other_small_recoverable']+=1
                    stats['small_branch_max']=max(stats['small_branch_max'],math.prod(len(residues[p]) for p in factors))
            rows.append(stats)
    fields=('count','symmetry_kept','frontier_eligible','noninvertible','five_only_recoverable',
            'five_gamma_compatible','small_prime_impossible','other_small_recoverable','residual_large_factor',
            'ordinary_root_candidates','ordinary_forbidden_signed8','ordinary_forbidden_signed361',
            'ordinary_forbidden_either','five_recovered_forbidden_either')
    out=dict(kind='arithmetic_micro_audit_not_search',
             sampling='5000 deterministic indices/context; seed114,start1140000,ratio64; symmetry/bounds matched; no curve searches',
             rows=rows,total={k:sum(r[k] for r in rows) for k in fields},
             prime_roots=residues,verified_five_adic_recoveries=recoveries,
             hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in (Path(__file__),ROOT/'validate_plane.py')})
    (HERE/'root-recovery-sample.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out['total'],indent=2))


if __name__=='__main__':main()
