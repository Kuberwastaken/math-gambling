from pathlib import Path
import importlib.util,json,random,subprocess,time
HERE=Path(__file__).resolve().parent
LAB=HERE.parents[1]
PROJECT=LAB.parents[1]
OUT=LAB/'research-2026-09-09'
PRIMES=(5,7,11,13,17,19,23,31,37,41,43,47,53,59,61)

def main():
    start=time.monotonic()
    code='#define main checker_original_main\n#include "checker.c"\n#undef main\n'+r'''
int main(void){
  for(int j=0;j<NP;j++)for(int x=0;x<sieve_primes[j];x++)qr_masks[j]|=UINT64_C(1)<<(x*x%sieve_primes[j]);
  unsigned long long d,r;long k;int sign;
  while(scanf("%llu %llu %ld %d",&d,&r,&k,&sign)==4){
    int rp[NP],dp[NP];uint64_t allowed[NP];uint16_t ready=0;normalized_ready=0;
    for(int j=0;j<NP;j++)prepare_prime(k,j,(i128)sign*d,d,r,rp,dp,allowed,&ready);
    if(!normalized_ready)fail("Test requires a dividing prime");
    print128(normalized_h);
    for(int j=0;j<NP;j++)if(d%sieve_primes[j]==0)printf(" %d:%d:%d",sieve_primes[j],rp[j],dp[j]);
    putchar('\n');
  }
}
'''
    (HERE/'arithmetic.c').write_text(code)
    subprocess.run(['clang','-O1','-fsanitize=undefined','-fno-sanitize-recover=all','-I',str(PROJECT/'work/pari-include'),str(HERE/'arithmetic.c'),'-L',str(LAB/'bin'),'-lpari','-o',str(HERE/'arithmetic')],check=True)
    rng=random.Random(1140919)
    tests=[]
    for p in PRIMES:
        ds=[p,p*p,p**3,((2**63-1)//p)*p]
        ds += [p*rng.randrange(1,(2**63-1)//p) for _ in range(100)]
        for d in ds:
            for r in {0,1,d-1,rng.randrange(d)}:
                tests.append((d,r,pow(r,3,d),rng.choice([-1,1])))
    run=subprocess.run([str(HERE/'arithmetic')],input=''.join('%d %d %d %d\n'%row for row in tests),text=True,capture_output=True,check=True)
    assert not run.stderr
    lines=run.stdout.splitlines();assert len(lines)==len(tests)
    predicates=0
    for (d,r,k,sign),line in zip(tests,lines):
        h,*triples=line.split();h=int(h)
        assert h==(k-r**3)//d and (k-r**3)%d==0
        for triple in triples:
            p,rp,dp=map(int,triple.split(':'));qr={x*x%p for x in range(p)}
            for q in [*range(p),-(2**63-1),2**63-1]:
                z=r+d*q
                # Rational square's numerator modulo p;3*sign invertible.
                oracle=((4*((k-z**3)//d)-sign*d*d)*pow(3*sign,-1,p))%p
                assert (rp+dp*q)%p==oracle
                assert (((rp+dp*q)%p in qr)==(oracle in qr))
                predicates+=1
    spec=importlib.util.spec_from_file_location('known',LAB/'phase3/validate_known_hits.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    fixtures=json.loads((LAB/'data/known-curves.json').read_text())['cases']
    fixtures.append(dict(k=3,xyz=sorted([569936821221962380720,-569936821113563493509,-472715493453327032]),d=108398887211,r=21397363547,R=5000000))
    hits=qpoints=exact=0
    for case in fixtures:
        command=[str(HERE/'offset_worker'),'curve',*[str(case[key]) for key in ('k','d','r','R')],'fixed']
        run=subprocess.run(command,text=True,capture_output=True,check=True,timeout=30)
        assert not run.stderr
        stats,n=module.parse_success(run.stdout,case)
        hits+=n;qpoints+=stats['quotient_points'];exact+=stats['exact_tests']
    result=dict(status='passed',ubsan_arithmetic_inputs=len(tests),independent_modular_predicates=predicates,known_positive_fixtures=len(fixtures),returned_hits=hits,quotient_points=qpoints,exact_tests=exact,wall_seconds=time.monotonic()-start,scope='Necessary-condition arithmetic and positive regression, not a proof of every search component')
    (OUT/'normalized-sieve-validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':main()
