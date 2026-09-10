#!/usr/bin/env python3
"""Independent phase2 integer-oracle and linked-checker validation."""
from pathlib import Path
import hashlib
import json
import math
import os
import random
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parent
LAB=ROOT.parent
HEADERS=LAB.parent.parent/'work/pari-include'
DEN=10**18
P=4848807585839879338
Q=23510935004498358840
D0=10**19//54
BAD8={0,4,6}
BAD361={0,19,76,95,114,133,171,209,304,323}

def base(ell,b,c):
    r=(-4*b-16*c)%ell
    n=-P*b-Q*c-r*DEN;d=ell*DEN
    return r+ell*((2*n+d)//(2*d))

def norm(a,b,c):
    return a**3+114*b**3+12996*c**3-342*a*b*c

def permutation(ell,radius,seed):
    mask=2**64-1
    def mix(x):
        x=((x^(x>>30))*0xbf58476d1ce4e5b9)&mask
        x=((x^(x>>27))*0x94d049bb133111eb)&mask
        return x^(x>>31)
    total=(2*radius+1)**2
    v=mix(seed^mix(ell)^mix(radius));offset=v%total
    stride=mix((v+0x9e3779b97f4a7c15)&mask)%total or 1
    while math.gcd(stride,total)!=1:
        stride=(stride+1)%total or 1
    return stride,offset,total

def invoke(binary,ell,A,tlo,thi,dlo,dhi,start,count,R=64,low=0,policy='fixed',method='inversion',seed=114):
    p=subprocess.run([str(binary),'tile',*map(str,(ell,A,tlo,thi,dlo,dhi,start,count,R,low)),
                      policy,method,str(seed)],text=True,capture_output=True,check=True,timeout=30)
    assert not p.stderr.strip(),p.stderr
    rows=[json.loads(s) for s in p.stdout.splitlines()]
    assert rows[-1]['type']=='stats' and rows[-1]['version']==2 and rows[-1]['complete']
    stats=rows[-1]
    cats=('outside_shell','rejected_signed','invalid_d','noninvertible_C','unsupported_D','covered','curves')
    assert stats['candidates']==count*(thi-tlo+1)==sum(stats[k] for k in cats)
    assert stats['quotient_points']==stats['rejected_mod243']+stats['rejected_parity']+stats['exact_tests']+sum(f['rejected'] for f in stats['filters'])
    for hit in rows:
        if hit['type']=='hit':assert sum(int(x)**3 for x in hit['xyz'])==114
    return rows,stats

def covered(d,r,R,low):
    zmin=max(10**19 if d<=D0 else 10**17,low*d)
    zmax=R*d
    if zmax<=zmin:return True
    if d%3!=1:
        lo=(zmin-r)//d+1;hi=(zmax-r)//d
    else:
        lo=-((zmax+r)//d);hi=-((zmin+r)//d)-1
        # ceil((-zmax-r)/d), ceil((-zmin-r)/d)-1
    return lo>hi

def main():
    begun=time.monotonic()
    assert (2*P-1)**3<8*114*DEN**3<(2*P+1)**3
    assert (2*Q-1)**3<8*114**2*DEN**3<(2*Q+1)**3
    assert (2*8-1)*DEN-2*6000000>0
    signed={}
    for modulus,expected in ((8,BAD8),(361,BAD361)):
        cubes={z**3%modulus for z in range(modulus)}
        actual={s for s in range(modulus) if not any((114-x**3-(s-x)**3)%modulus in cubes for x in range(modulus))}
        assert actual==expected
        signed[str(modulus)]=sorted(actual)
    trace_header=r'''
#include <stdio.h>
static void trace_candidate(unsigned long long i,__int128 t,__int128 a,__int128 b,__int128 c,__int128 d){
  printf("{\"type\":\"candidate_trace\",\"index\":%llu,\"t\":%lld,\"a\":%lld,\"b\":%lld,\"c\":%lld,\"D\":%lld}\n",i,(long long)t,(long long)a,(long long)b,(long long)c,(long long)d);
}
static void trace_root(unsigned long long i,__int128 t,unsigned long long d,unsigned long long r){
  printf("{\"type\":\"root_trace\",\"index\":%llu,\"t\":%lld,\"D\":%llu,\"r\":%llu}\n",i,(long long)t,d,r);
}
#define OFFSET_TRACE_CANDIDATE(i,t,a,b,c,d) trace_candidate(i,t,a,b,c,d)
#define OFFSET_TRACE_ROOT(i,t,d,r) trace_root(i,t,d,r)
'''
    full_domains=coefficient_checks=roots_checked=endpoint_tests=0
    partitions=[]
    rng=random.Random(114)
    with tempfile.TemporaryDirectory(prefix='worker-validation-',dir=ROOT) as tmp:
        tmp=Path(tmp);os.symlink(LAB/'bin/libpari.dylib',tmp/'libpari.dylib')
        (tmp/'trace.h').write_text(trace_header)
        binary=tmp/'checked_worker'
        subprocess.run(['clang','-O1','-fsanitize=undefined','-fno-sanitize-recover=all',
                        '-include',str(tmp/'trace.h'),'-I',str(HEADERS),str(ROOT/'offset_worker.c'),
                        '-L',str(LAB/'bin'),'-lpari','-o',str(binary)],check=True)
        cases=[]
        for ell in (1,5,25):
            for A in (1,3,8):
                for tlo,thi in ((8,12),(128,132),(2048,2052)):
                    ds=sorted(norm(base(ell,b,c)+ell*t,b,c)//ell
                              for b in range(-A,A+1) for c in range(-A,A+1) for t in range(tlo,thi+1))
                    cases.append((ell,A,tlo,thi,0,max(ds)))
                    lo,hi=ds[len(ds)//3],ds[2*len(ds)//3]
                    if hi<=lo:hi=lo+1
                    cases.append((ell,A,tlo,thi,lo,hi))
        for ell,A,tlo,thi,dlo,dhi in cases:
            count=(2*A+1)**2;seed=rng.randrange(2**32)
            rows,stats=invoke(binary,ell,A,tlo,thi,dlo,dhi,0,count,method='probe',seed=seed)
            stride,offset,total=permutation(ell,A,seed)
            assert stats['permutation_stride']==stride and stats['permutation_offset']==offset and stats['total']==total
            traces={(r['index'],r['t'],r['a'],r['b'],r['c'],r['D']) for r in rows if r['type']=='candidate_trace'}
            roots={(r['index'],r['t'],r['D'],r['r']) for r in rows if r['type']=='root_trace'}
            expected_candidates=set();expected_roots=set()
            expected={k:0 for k in ('outside_shell','rejected_signed','rejected_signed8','rejected_signed361','invalid_d','noninvertible_C','covered','curves')}
            exposure=[];seen_bc=set()
            geometries=[r for r in rows if r['type']=='row'];assert len(geometries)==count
            for row in geometries:
                index=row['index'];v=(index*stride+offset)%total
                b,c=v%(2*A+1)-A,v//(2*A+1)-A
                B0=base(ell,b,c)
                assert (int(row['b']),int(row['c']),int(row['base']))==(b,c,B0)
                seen_bc.add((b,c))
                actual=[]
                for lo,hi in row['intervals']:
                    lo,hi=int(lo),int(hi);assert tlo<=lo<=hi<=thi
                    actual.extend(range(lo,hi+1))
                expected_t=[]
                for t in range(tlo,thi+1):
                    coefficient_checks+=1;a=B0+ell*t;n=norm(a,b,c)
                    assert n>0 and n%ell==0 and (a+4*b+16*c)%ell==0
                    d=n//ell
                    if not dlo<d<=dhi:
                        expected['outside_shell']+=1;continue
                    expected_t.append(t);expected_candidates.add((index,t,a,b,c,d))
                    if d<2 or d%3==0:
                        expected['invalid_d']+=1;continue
                    s=d if d%3==1 else -d
                    if s%8 in BAD8:
                        expected['rejected_signed']+=1;expected['rejected_signed8']+=1;continue
                    if s%361 in BAD361:
                        expected['rejected_signed']+=1;expected['rejected_signed361']+=1;continue
                    C,B=b*b-a*c,114*c*c-a*b
                    if math.gcd(C,d)!=1:
                        expected['noninvertible_C']+=1;continue
                    r=B*pow(C,-1,d)%d;assert pow(r,3,d)==114%d
                    expected_roots.add((index,t,d,r))
                    if covered(d,r,64,0):expected['covered']+=1
                    else:expected['curves']+=1;exposure.append(D0/d)
                assert actual==expected_t and actual==sorted(set(actual))
            assert seen_bc=={(b,c) for b in range(-A,A+1) for c in range(-A,A+1)}
            assert traces==expected_candidates and roots==expected_roots
            for key,value in expected.items():assert stats[key]==value,(key,stats[key],value)
            assert math.isclose(stats['exposure_sum'],math.fsum(exposure),rel_tol=2e-12,abs_tol=1e-9)
            direct,ds=invoke(binary,ell,A,tlo,thi,dlo,dhi,0,count,method='direct',seed=seed)
            assert {(r['index'],r['t'],r['a'],r['b'],r['c'],r['D']) for r in direct if r['type']=='candidate_trace'}==traces
            for key in (*expected.keys(),'candidates','eligible_inputs','exact_tests','hits','quotient_points','filters'):
                assert ds[key]==stats[key],key
            full_domains+=1;roots_checked+=len(roots)
        # Exact lower/upper shell endpoints for independently chosen coefficients.
        for _ in range(20):
            ell=rng.choice((1,5,25));A=3;b=rng.randint(-A,A);c=rng.randint(-A,A);t=rng.randint(8,12)
            d=norm(base(ell,b,c)+ell*t,b,c)//ell
            for lo,hi,inside in ((d,d+1,False),(max(0,d-1),d,True)):
                rows,_=invoke(binary,ell,A,8,12,lo,hi,0,49,method='probe')
                selected=[r for r in rows if r['type']=='candidate_trace' and (r['b'],r['c'],r['t'])==(b,c,t)]
                assert bool(selected)==inside;endpoint_tests+=1
        # Wide native integer arithmetic with tiny row counts; direct agreement.
        for ell in (1,5,25):
            for dlo,dhi in ((0,2**63-1),(D0,8*D0)):
                args=(ell,6000000,8190,8191,dlo,dhi,0,8)
                a,sa=invoke(binary,*args)
                b,sb=invoke(binary,*args,method='direct')
                assert [r for r in a if r['type'].endswith('_trace')]==[r for r in b if r['type'].endswith('_trace')]
                for key in ('candidates','outside_shell','invalid_d','noninvertible_C','rejected_signed','curves','exact_tests','filters'):
                    assert sa[key]==sb[key]
        # Nonzero-start row partitions and disjoint quotient bands at the frontier.
        for ell in (1,5,25):
            args=(ell,1500000,128,511,D0,2*D0)
            whole,ws=invoke(binary,*args,777,128,R=256)
            left,ls=invoke(binary,*args,777,49,R=256)
            right,rs=invoke(binary,*args,826,79,R=256)
            rootset=lambda records:{(r['index'],r['t'],r['D'],r['r']) for r in records if r['type']=='root_trace'}
            assert rootset(whole)==rootset(left)|rootset(right)
            assert not rootset(left)&rootset(right)
            for key in ('candidates','eligible_inputs','outside_shell','rejected_signed','invalid_d','noninvertible_C','covered','curves','quotient_points','exact_tests','hits','rejected_mod243','rejected_parity'):
                assert ws[key]==ls[key]+rs[key],(ell,key)
            assert math.isclose(ws['exposure_sum'],ls['exposure_sum']+rs['exposure_sum'],rel_tol=2e-12)
            _,bs1=invoke(binary,*args,777,128,R=64)
            _,bs2=invoke(binary,*args,777,128,R=256,low=64)
            for key in ('quotient_points','exact_tests','hits'):
                assert ws[key]==bs1[key]+bs2[key],(ell,key)
            # Reconstruct the exposure proxy from actual native roots and exact bounds.
            expected_exposure=math.fsum(D0/d for _,_,d,r in rootset(whole) if not covered(d,r,256,0))
            assert math.isclose(ws['exposure_sum'],expected_exposure,rel_tol=2e-12,abs_tol=1e-9)
            partitions.append(dict(ell=ell,rows=128,start=777,curves=ws['curves'],
                                   quotient_points=ws['quotient_points'],exposure=ws['exposure_sum']))
    # Linked frozen checker: all known curves, with independent Python identities.
    known=json.loads((LAB/'data/known-curves.json').read_text())['cases']
    known.append(dict(k=3,xyz=sorted([569936821221962380720,-569936821113563493509,-472715493453327032]),d=108398887211,r=21397363547,R=5000000))
    for c in known:
        p=subprocess.run([str(ROOT/'bin/offset_worker'),'curve',*[str(c[k]) for k in ('k','d','r','R')],'fixed'],capture_output=True,text=True,check=True,timeout=30)
        assert not p.stderr.strip()
        hits=[json.loads(r) for r in p.stdout.splitlines() if json.loads(r).get('type')=='hit']
        points={tuple(sorted(map(int,h['xyz']))) for h in hits}
        assert tuple(c['xyz']) in points
        assert all(sum(x**3 for x in xyz)==c['k'] for xyz in points)
    valid_args=['tile','1','6000000','8','31',str(D0),str(2*D0),'0','1','64','0','fixed','inversion','114']
    mutations={1:'2',2:'6000001',3:'7',4:'8192',5:str(2*D0),6:str(2**63),
               7:'-1',8:'1000001',9:'3',10:'64',11:'unknown',12:'unknown',13:'18446744073709551616'}
    for position,value in mutations.items():
        args=valid_args.copy();args[position]=value
        p=subprocess.run([str(ROOT/'bin/offset_worker'),*args],capture_output=True,text=True)
        assert p.returncode==2,(position,value,p.returncode)
    args=valid_args.copy();args[2]='1';args[7]='9'
    p=subprocess.run([str(ROOT/'bin/offset_worker'),*args],capture_output=True,text=True)
    assert p.returncode==2
    result=dict(full_small_domains=full_domains,coefficient_oracle_checks=coefficient_checks,
                native_modular_roots_compared=roots_checked,exact_endpoint_tests=endpoint_tests,
                signed_filter_masks_exhaustively_verified=signed,
                positive_embedding_bound_certified=True,plane_constants_certified=True,
                direct_inversion_candidates_and_counts_equal=True,ubsan=True,
                nonzero_row_partitions_and_quotient_bands=partitions,
                exposure_proxy_independently_reconstructed=True,
                invalid_cli_inputs_rejected=len(mutations)+1,
                known_checker_curves_recovered=len(known),seconds=time.monotonic()-begun,
                source_sha256=hashlib.sha256((ROOT/'offset_worker.c').read_bytes()).hexdigest(),
                binary_sha256=hashlib.sha256((ROOT/'bin/offset_worker').read_bytes()).hexdigest(),
                frozen_common_sha256=hashlib.sha256((LAB/'campaign_worker.c').read_bytes()).hexdigest(),
                scope='Finite row-domain arithmetic and exact checking, not success probability')
    (ROOT/'worker-validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
