#!/usr/bin/env python3
"""Small CPU-bounded matched shell-generation benchmark; no production changes."""
from pathlib import Path
import argparse
import hashlib
import json
import random
import statistics
import subprocess

ROOT=Path(__file__).resolve().parent
LAB=ROOT.parent.parent

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--cpu-budget',type=float,default=12)
    ap.add_argument('--rows',type=int,default=64)
    ap.add_argument('--repeats',type=int,default=3)
    args=ap.parse_args()
    if not (0<args.cpu_budget<=20 and 1<=args.rows<=128 and 1<=args.repeats<=3):
        ap.error('Bounded experiment requires CPU<=20s, rows<=128, repeats<=3')
    rng=random.Random(114)
    raw=[];total_cpu=0;comparisons=[]
    invariant=['candidates','curves','quotient_points','exact_tests','hits','invalid_d','noninvertible_C',
               'covered','symmetry_rejected','rejected_mod243','rejected_parity','filters']
    for ell,A in ((1,50000),(5,85499),(25,146201)):
        for ratio in (64,4096):
            pairs=[]
            for rep in range(args.repeats):
                if total_cpu>=args.cpu_budget:
                    break
                methods=['direct','inversion'];rng.shuffle(methods)
                pair={}
                for method in methods:
                    cmd=[str(ROOT/'shell_worker'),'tile',str(ell),str(A),str(10**19//54),
                         str(1000*rep),str(args.rows),str(ratio),'fixed',method]
                    run=subprocess.run(cmd,text=True,capture_output=True,check=True,timeout=10)
                    assert not run.stderr.strip(),run.stderr
                    records=[json.loads(x) for x in run.stdout.splitlines()]
                    stats=next(r for r in records if r['type']=='stats')
                    ss=records[-1]
                    assert ss['type']=='shell_stats' and ss['complete']
                    hits=[r for r in records if r['type']=='hit']
                    for hit in hits:
                        assert sum(int(x)**3 for x in hit['xyz'])==114
                    if hits:
                        (ROOT/'DISCOVERY.json').write_text(json.dumps(hits,indent=2)+'\n')
                        raise SystemExit('Verified114 identity found; see DISCOVERY.json')
                    total_cpu+=ss['cpu_seconds']
                    pair[method]=(stats,ss)
                    raw.append(dict(ell=ell,radius=A,ratio=ratio,repeat=rep,method=method,
                                    checker=stats,generator=ss))
                for key in invariant:
                    assert pair['direct'][0][key]==pair['inversion'][0][key],(ell,ratio,rep,key)
                for key in ('rows','empty_rows','lattice_positions','eligible_inputs','outside_shell'):
                    assert pair['direct'][1][key]==pair['inversion'][1][key],(ell,ratio,rep,key)
                pairs.append(pair)
            if pairs:
                direct=statistics.median(p['direct'][1]['cpu_seconds'] for p in pairs)
                inversion=statistics.median(p['inversion'][1]['cpu_seconds'] for p in pairs)
                total_inputs=sum(p['inversion'][1]['lattice_positions'] for p in pairs)
                outside=sum(p['inversion'][1]['outside_shell'] for p in pairs)
                empty=sum(p['inversion'][1]['empty_rows'] for p in pairs)
                comparisons.append(dict(ell=ell,radius=A,ratio=ratio,pairs=len(pairs),
                  direct_cpu_median=direct,inversion_cpu_median=inversion,
                  speedup=direct/inversion,outside_shell_fraction=outside/total_inputs,
                  empty_row_fraction=empty/(len(pairs)*args.rows),
                  matched_checker_and_candidate_counts=True))
    report=dict(comparisons=comparisons,benchmark_cpu_seconds=total_cpu,
                requested_cpu_budget=args.cpu_budget,
                caveat='May exceed budget by one matched pair. Local short CPU-time tests while production runs; no discovery probability inferred.',
                source_sha256=hashlib.sha256((ROOT/'shell_worker.c').read_bytes()).hexdigest(),
                frozen_common_sha256=hashlib.sha256((LAB/'campaign_worker.c').read_bytes()).hexdigest(),raw=raw)
    (ROOT/'benchmark.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='raw'},indent=2))

if __name__=='__main__':main()
