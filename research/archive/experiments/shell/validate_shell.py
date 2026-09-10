#!/usr/bin/env python3
"""Independent finite-oracle checks for exact shell inversion; no discovery model."""
from pathlib import Path
import hashlib
import json
import math
import os
import random
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parent
LAB=ROOT.parent.parent
HEADERS=LAB.parent.parent/'work/pari-include'

def run(binary,ell,A,D0,start,count,method='probe',seed=114,R=4):
    p=subprocess.run([str(binary),'tile',str(ell),str(A),str(D0),str(start),str(count),
                      str(R),'fixed',method,'0',str(seed)],capture_output=True,text=True,
                      check=True,timeout=10)
    assert not p.stderr.strip(),p.stderr
    rows=[json.loads(x) for x in p.stdout.splitlines()]
    return rows, next(r for r in rows if r['type']=='stats'), rows[-1]

def main():
    rng=random.Random(114)
    scenarios=[]
    for ell in (1,5,25):
        for A in (1,3,8):
            for D0 in (100,10000,100000):
                scenarios.append((ell,A,D0))
        scenarios.append((ell,25,1000000))
    with tempfile.TemporaryDirectory(prefix='shell-test-',dir=ROOT) as tmp:
        tmp=Path(tmp)
        os.symlink(LAB/'bin/libpari.dylib',tmp/'libpari.dylib')
        trace=tmp/'trace.h'
        trace.write_text(r'''
#include <stdio.h>
static void trace_root(unsigned long long row,__int128 t,unsigned long long d,unsigned long long r){
  printf("{\"type\":\"root\",\"row\":%llu,\"t\":%lld,\"D\":%llu,\"r\":%llu}\n",row,(long long)t,d,r);
}
#define SHELL_TRACE_ROOT(row,t,d,r) trace_root(row,t,d,r)
''')
        binary=tmp/'shell_checked'
        subprocess.run(['clang','-O1','-fsanitize=undefined','-fno-sanitize-recover=all',
                        '-include',str(trace),'-I',str(HEADERS),str(ROOT/'shell_worker.c'),
                        '-L',str(LAB/'bin'),'-lpari','-o',str(binary)],check=True)
        complete_domains=coefficients=expected_roots=boundary_cases=0
        for ell,A,D0 in scenarios:
            count=(2*A+1)**2
            records,stats,ss=run(binary,ell,A,D0,0,count,seed=rng.randrange(2**32))
            rows=[r for r in records if r['type']=='row']
            assert len(rows)==count
            assert math.gcd(stats['permutation_stride'],count)==1
            coords={(int(r['b']),int(r['c'])) for r in rows}
            assert coords=={(b,c) for b in range(-A,A+1) for c in range(-A,A+1)}
            oracle_roots=set();unpruned_coverage=set();canonical_coverage=set();eligible=0
            for row in rows:
                b,c,a0=map(int,(row['b'],row['c'],row['a0']))
                assert a0==(-4*b-16*c)%ell
                v=(row['row_index']*stats['permutation_stride']+stats['permutation_offset'])%count
                assert (b,c)==(v%(2*A+1)-A,v//(2*A+1)-A)
                actual=[]
                for low,high in row['intervals']:
                    low,high=int(low),int(high)
                    assert -(A//ell)<=low<=high<=A//ell
                    actual.extend(range(low,high+1))
                assert actual==sorted(set(actual)),('duplicate or unsorted t',row)
                expected=[]
                for t in range(-(A//ell),A//ell+1):
                    coefficients+=1
                    a=a0+ell*t
                    n=a**3+114*b**3+12996*c**3-342*a*b*c
                    assert n%ell==0
                    d=abs(n)//ell
                    if not D0<d<=2*D0:
                        continue
                    expected.append(t);eligible+=1
                    if d<2 or d%3==0:
                        continue
                    C,B=b*b-a*c,114*c*c-a*b
                    if math.gcd(C,d)!=1:
                        continue
                    r=B*pow(C,-1,d)%d
                    assert pow(r,3,d)==114%d
                    coverage={(d,r,q) for q in range(-4,4 if r else 5)}
                    unpruned_coverage.update(coverage)
                    opposite_residue=(4*b+16*c)%ell
                    opposite_t=(-a-opposite_residue)//ell
                    duplicate=(c,b,a)<(0,0,0) and -(A//ell)<=opposite_t<=A//ell
                    if not duplicate:
                        canonical_coverage.update(coverage)
                        oracle_roots.add((row['row_index'],t,d,r))
                assert actual==expected,(ell,A,D0,row,expected)
            assert unpruned_coverage==canonical_coverage
            assert ss['eligible_inputs']==eligible
            assert ss['outside_shell']+eligible==ss['lattice_positions']==count*(2*(A//ell)+1)
            # Native checker traces ensure exact root generation agrees with Python.
            native,ns,nss=run(binary,ell,A,D0,0,count,'inversion',stats['permutation_seed'])
            roots={(r['row'],r['t'],r['D'],r['r']) for r in native if r['type']=='root'}
            assert roots==oracle_roots,('native root mismatch',ell,A,D0)
            direct,ds,dss=run(binary,ell,A,D0,0,count,'direct',stats['permutation_seed'])
            assert {(r['row'],r['t'],r['D'],r['r']) for r in direct if r['type']=='root'}==roots
            for key in ('candidates','curves','exact_tests','hits','invalid_d','noninvertible_C','covered','symmetry_rejected','quotient_points','filters'):
                assert ns[key]==ds[key],(key,ell,A,D0)
            expected_roots+=len(roots);complete_domains+=1
        # Target exact lower/upper endpoints using real lattice coefficient norms.
        for _ in range(40):
            ell=rng.choice((1,5,25));A=12;b=rng.randint(-A,A);c=rng.randint(-A,A)
            a=(-4*b-16*c)%ell+ell*rng.randint(-(A//ell),A//ell)
            D=abs(a**3+114*b**3+12996*c**3-342*a*b*c)//ell
            if D<2:continue
            for D0 in (D,D//2):
                records,_,_=run(binary,ell,A,D0,0,(2*A+1)**2)
                row=next(r for r in records if int(r['b'])==b and int(r['c'])==c)
                t=(a-int(row['a0']))//ell
                actual=any(int(lo)<=t<=int(hi) for lo,hi in row['intervals'])
                assert actual==(D0<D<=2*D0)
                boundary_cases+=1
        # Exact row partitioning preserves all accounting and generated roots.
        args=(25,25,1000000)
        whole,ws,wss=run(binary,*args,0,2601,'inversion')
        left,ls,lss=run(binary,*args,0,1000,'inversion')
        right,rs,rss=run(binary,*args,1000,1601,'inversion')
        rootset=lambda records:{(r['row'],r['t'],r['D'],r['r']) for r in records if r['type']=='root'}
        assert rootset(whole)==rootset(left)|rootset(right)
        assert not rootset(left)&rootset(right)
        for key in ('rows','empty_rows','lattice_positions','eligible_inputs','outside_shell'):
            assert wss[key]==lss[key]+rss[key]
    evidence=dict(complete_small_domains=complete_domains,coefficient_oracle_checks=coefficients,
                  native_modular_roots_compared=expected_roots,exact_endpoint_cases=boundary_cases,
                  root_and_quotient_coverage_preserved_by_symmetry=True,row_partition_gapless=True,
                  direct_inversion_candidates_and_checker_counts_equal=True,ubsan=True,
                  source_sha256=hashlib.sha256((ROOT/'shell_worker.c').read_bytes()).hexdigest(),
                  frozen_common_sha256=hashlib.sha256((LAB/'campaign_worker.c').read_bytes()).hexdigest(),
                  scope='Exact finite generator D-shell; not exhaustive global height coverage or discovery probability')
    (ROOT/'validation.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(evidence,indent=2))

if __name__=='__main__':main()
