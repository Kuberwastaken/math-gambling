#!/usr/bin/env python3
"""Test curve recovery, exact arithmetic, and the certified class computation.
The known curves are supplied as inputs: this is not blind rediscovery.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import time

ROOT=Path(__file__).resolve().parent

def gp(source):
    r=subprocess.run([str(ROOT/'bin/gp'),'-q','-f'],input=source+'\nquit;\n',text=True,capture_output=True,timeout=120)
    if r.returncode or r.stderr.strip():raise RuntimeError(r.stderr+r.stdout)
    return r.stdout

def main():
    start=time.monotonic()
    cases=json.loads((ROOT/'data/known-curves.json').read_text())['cases']
    cases.append(dict(k=3,xyz=sorted([569936821221962380720,-569936821113563493509,-472715493453327032]),d=108398887211,r=21397363547,R=5000000))
    source=f'read("{ROOT / "norm_search.gp"}");\n'
    for i,c in enumerate(cases):
        source+=f'print("CASE ",[{i},curve_points({c["k"]},{c["d"]},{c["r"]},{c["R"]},0,0)]);\n'
    reference={}
    for line in gp(source).splitlines():
        if line.startswith('CASE '):
            i,pts=json.loads(line[5:]);reference[i]={tuple(p) for p in pts}
    assert len(reference)==len(cases)
    for i,c in enumerate(cases):
        assert tuple(c['xyz']) in reference[i],('GP missing known solution',i,c)
        run=subprocess.run([str(ROOT/'bin/native_search'),'curve',*[str(c[key]) for key in ['k','d','r','R']]],text=True,capture_output=True,timeout=30,check=True)
        pts=set()
        for line in run.stdout.splitlines():
            if line.startswith('HIT '):
                k,xyz=json.loads(line[4:]);assert sum(v**3 for v in xyz)==k==c['k'];pts.add(tuple(sorted(xyz)))
        assert pts==reference[i],('Native/GP mismatch',i,c,pts,reference[i])
    certificate=gp(f'''read("{ROOT / 'norm_search.gp'}");
K=bnfinit(x^3-114,1);
print("FIELD ",[K.disc,K.no,K.cyc,idealnorm(K,K.gen[1]),bnfcertify(K)]);
print("LATTICE ",[idealhnf(K,5,x-4)==K.gen[1],idealhnf(K,25,x-4)==idealpow(K,K.gen[1],2)]);
counts=vector(3);failures=0;
for(dd=2,1000,if(dd%3==0,next);for(rr=0,dd-1,if(rr^3%dd!=114%dd,next);ii=idealhnf(K,dd,x-rr);cl=bnfisprincipal(K,ii,0)[1];j=(-cl)%3;gg=bnfisprincipal(K,idealmul(K,ii,idealpow(K,K.gen[1],j)));vv=gg[2];cs=norm_candidates(114,vv[1],vv[2],vv[3],[5^j]);counts[j+1]++;if(!setsearch(Set(cs),[dd,rr,5^j]),failures++)));
print("CLASSES ",[counts,failures]);
print("ORACLE ",norm_candidates(3,5603,1612,1156,[1]));
print("BOUNDARY ",hyperellratpoints(q^3+3,[1,1]));
print("INCLUDED ",curve_points(3,108398887211,21397363547,5000000,108398887211,4*10^17));
print("EXCLUDED ",curve_points(3,108398887211,21397363547,5000000,108398887211,5*10^17));
''')
    evidence={key:json.loads(value) for key,value in (line.split(' ',1) for line in certificate.splitlines())}
    assert evidence['FIELD']==[-350892,3,[3],5,1]
    assert evidence['LATTICE']==[1,1]
    assert evidence['CLASSES']==[[122,110,104],0]
    assert [108398887211,21397363547,1] in evidence['ORACLE']
    assert [1,2] in evidence['BOUNDARY']
    assert cases[-1]['xyz'] in evidence['INCLUDED']
    assert cases[-1]['xyz'] not in evidence['EXCLUDED']
    blind=gp(f'read("{ROOT / "norm_search.gp"}");\nrun_batch(6,10,6001,10000,64,0,0,[1]);')
    blind_hits=[json.loads(line[4:]) for line in blind.splitlines() if line.startswith('HIT ')]
    assert {tuple(h[1]) for h in blind_hits}=={(-637,-205,644),(-58,-43,65)}
    for hit in blind_hits:assert sum(v**3 for v in hit[1])==6
    result=dict(blind_search_k6_solutions=[h[1] for h in blind_hits],curve_cases=len(cases),distinct_k=len({c['k'] for c in cases}),native_gp_sets_agree=True,
                validation_kind='Known (d,root) curves supplied; not blind discovery',field_and_boundary_tests=evidence,
                elapsed_seconds=time.monotonic()-start,
                source_sha256={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ['native_search.c','norm_search.gp','validate.py']})
    path=ROOT/'runs/validation.json';path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
