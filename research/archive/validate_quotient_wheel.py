#!/usr/bin/env python3
"""Compare every quotient visited by the direct loop and residue wheel.

The compiled UBSan probe instruments the shared sieve entry point; it checks
candidate sets before later sieving, including candidates that are not hits.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
HEADERS = ROOT.parent.parent/'work/pari-include'


def main():
    source = r'''
static void record_q(__int128 q);
#define CAMPAIGN_TRACE_Q(q) do { record_q(q); return; } while(0)
#define main hidden_worker_main
#include "WORKER"
#undef main
static unsigned char observed[6000],expected[6000];
static i128 trace_lo;static uint64_t trace_length,visited;
static void record_q(i128 q){
  i128 i=q-trace_lo;
  if(i<0 || i>=(i128)trace_length || observed[(int)i])fail("Quotient out of interval or duplicated");
  observed[(int)i]=1;visited++;
}
int main(void){
  const long ks[]={3,6,12,15,114,627};uint64_t cases=0,points=0,accepted=0;
  uint64_t state=114;
  for(int ki=0;ki<6;ki++){
    long k=ks[ki];init_filters(k);
    for(int dm=1;dm<486;dm++)if(dm%3)for(int shape=0;shape<3;shape++){
      state=mix64(state+1);
      uint64_t d=dm;
      if(shape==1)d+=486*UINT64_C(1000000000);
      if(shape==2)d+=486*((INT64_MAX-486)/486);
      uint64_t r=mix64(state+3)%d;
      trace_length=1+state%5000;
      trace_lo=(i128)(state%20000)-10000;
      if(shape==1)trace_lo=-(i128)INT64_MAX+10000;
      if(shape==2)trace_lo=(i128)INT64_MAX-10000;
      i128 hi=trace_lo+trace_length-1;
      memset(observed,0,sizeof(observed));visited=0;
      interval_engine=-1;quotient_points=rejected81=rejected_parity=0;
      interval(k,d,r,trace_lo,hi);
      uint64_t direct_total=quotient_points,direct_mod=rejected81,direct_parity=rejected_parity,direct_visited=visited;
      memcpy(expected,observed,sizeof(expected));
      memset(observed,0,sizeof(observed));visited=0;
      interval_engine=1;quotient_points=rejected81=rejected_parity=0;
      interval(k,d,r,trace_lo,hi);
      if(memcmp(expected,observed,sizeof(expected)) || direct_total!=quotient_points || direct_mod!=rejected81 || direct_parity!=rejected_parity || direct_visited!=visited)fail("Direct/wheel quotient coverage mismatch");
      if(quotient_points!=rejected81+rejected_parity+visited)fail("Quotient rejection accounting mismatch");
      cases++;points+=trace_length;accepted+=visited;
    }
  }
  printf("{\"intervals\":%"PRIu64",\"quotient_positions\":%"PRIu64",\"surviving_quotients\":%"PRIu64",\"sets_and_rejection_counts_equal\":true,\"k_values\":[3,6,12,15,114,627],\"all_324_nonmultiples_of3_mod486\":true,\"signed_int64_boundary_intervals\":true}\n",cases,points,accepted);
  return 0;
}
'''.replace('WORKER', str(ROOT/'campaign_worker.c'))
    with tempfile.TemporaryDirectory(prefix='wheel-', dir=ROOT.parent.parent/'work') as tmp:
        tmp = Path(tmp)
        (tmp/'probe.c').write_text(source)
        os.symlink(ROOT/'bin/libpari.dylib',tmp/'libpari.dylib')
        subprocess.run(['clang','-O1','-fsanitize=undefined','-fno-sanitize-recover=all',
                        '-I',str(HEADERS),str(tmp/'probe.c'),'-L',str(ROOT/'bin'),
                        '-lpari','-o',str(tmp/'probe')],check=True)
        p=subprocess.run([str(tmp/'probe')],text=True,capture_output=True,check=True,timeout=60)
        assert not p.stderr.strip(),p.stderr
        report=json.loads(p.stdout)
    # Actual PARI and prime-filter end-to-end equality, beyond the trace hook.
    from validate_campaign_worker import invoke
    b=ROOT/'bin/campaign_worker'
    c=(3,108398887211,21397363547,5000000)
    points_direct,direct=invoke(b,'curve',*c,'direct:fixed')
    points_wheel,wheel=invoke(b,'curve',*c,'wheel:fixed')
    assert points_direct==points_wheel and len(points_direct)==1
    fields=('quotient_points','exact_tests','hits','rejected_mod243','rejected_parity','filters')
    for field in fields:
        assert direct[field]==wheel[field],(field,direct[field],wheel[field])
    tile_evidence=[]
    for ell,radius in ((1,50000),(5,85499),(25,146201)):
        results=[]
        for policy in ('direct:fixed','wheel:fixed','direct:adaptive','wheel:adaptive'):
            pts,stats=invoke(b,'tile',ell,radius,1000000,200000,4096,policy,256)
            results.append((pts,stats))
        stable=('curves','quotient_points','exact_tests','hits','rejected_mod243',
                'rejected_parity','symmetry_rejected')
        for pts,stats in results[1:]:
            assert pts==results[0][0]
            for field in stable:
                assert stats[field]==results[0][1][field],(ell,field)
        assert results[0][1]['filters']==results[1][1]['filters']
        tile_evidence.append(dict(ell=ell,radius=radius,inputs=200000,
                                 quotient_points=results[0][1]['quotient_points'],
                                 exact_tests=results[0][1]['exact_tests'],
                                 fixed_adaptive_direct_wheel_core_stats_equal=True))
    report.update(known_k3_full_sieve_and_exact_check_equal=True,
                  direct_seconds=direct['wall_seconds'],wheel_seconds=wheel['wall_seconds'],
                  tile_engine_equivalence=tile_evidence,
                  ubsan=True,source_sha256=hashlib.sha256((ROOT/'campaign_worker.c').read_bytes()).hexdigest())
    (ROOT/'runs/quotient-wheel-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
