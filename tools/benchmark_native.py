#!/usr/bin/env python3
"""Matched task corpus, exact parity and warm timing; never sends receipts."""
import argparse,hashlib,json,platform,random,statistics,subprocess,sys,time
from pathlib import Path
from search_core import CONTEXTS,canonical_json,make_task,run_task
from native_kernel import binary_path
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    rng=random.Random(114)
    tasks=[make_task(c['id'],r,b) for c in CONTEXTS for r,b in [(0,0),((int(c['totalRows'])-1)//128*128,c['blocks']-1),(int(c['totalRows'])//7//128*128,c['blocks']//2)]]
    tasks += [make_task(c['id'],rng.randrange(int(c['rowTasks']))*128,rng.randrange(c['blocks'])) for c in CONTEXTS for _ in range(4)]
    expected=[run_task(t) for t in tasks];payload=''.join(canonical_json(t)+'\n' for t in tasks)
    measurements={name:[] for name in ['python','rust','rust_montgomery']}
    for repeat in range(4):
        # Drop the first full warmup round, including OS executable startup.
        for name in measurements:
            start=time.perf_counter()
            if name=='python':actual=[run_task(t) for t in tasks]
            else:
                p=subprocess.run([str(binary_path())]+(['--montgomery'] if name.endswith('montgomery') else []),input=payload,text=True,capture_output=True,check=True)
                actual=[json.loads(line) for line in p.stdout.splitlines()]
            elapsed=time.perf_counter()-start
            assert actual==expected,name
            if repeat:measurements[name].append(elapsed)
    script="""
import{readFileSync}from'node:fs';
import{createWasmKernel}from'./web/wasm-kernel.mjs';
import{runTask,canonicalJSON}from'./web/engine.mjs';
const tasks=JSON.parse(readFileSync(0,'utf8')),w=await createWasmKernel(readFileSync('web/assets/kernel/math_gambling_kernel.wasm'));
const reference=[];for(const t of tasks)reference.push(canonicalJSON(await runTask(t)));
const times={javascript:[],wasm:[],wasm_montgomery:[]};
for(let round=0;round<4;round++)for(const name of Object.keys(times)){
 const start=performance.now();let i=0;
 for(const task of tasks){const r=await(name==='javascript'?runTask(task):w.runTask(task,{montgomery:name==='wasm_montgomery'}));if(canonicalJSON(r)!==reference[i++])throw Error('Parity failure');}
 if(round)times[name].push((performance.now()-start)/1000);
}
console.log(JSON.stringify(times));
"""
    browser=json.loads(subprocess.run(['node','--input-type=module','-e',script],cwd=ROOT,input=json.dumps(tasks),text=True,capture_output=True,check=True).stdout)
    measurements.update(browser)
    medians={k:statistics.median(v) for k,v in measurements.items()}
    report={'schema':'math-gambling-kernel-benchmark-v1','date':'2026-09-11','host':platform.platform(),'python':platform.python_version(),
            'rustc':subprocess.check_output(['rustc','--version'],text=True).strip(),'node':subprocess.check_output(['node','--version'],text=True).strip(),
            'tasks':len(tasks),'task_corpus_sha256':hashlib.sha256(canonical_json(tasks).encode()).hexdigest(),
            'results_sha256':hashlib.sha256(canonical_json(expected).encode()).hexdigest(),
            'counters':{k:sum(r['counters'][k] for r in expected) for k in expected[0]['counters']},
            'wall_seconds':measurements,'median_seconds':medians,'speedups':{'python_over_rust':medians['python']/medians['rust'],'javascript_over_wasm':medians['javascript']/medians['wasm']},
            'notes':['One full warmup round excluded, then three timed rounds.','Rust timings include process startup, JSON pipe I/O and parsing; Python runs in-process.','JS and WASM measured in Node, including per-task parity serialization; not a mobile-browser guarantee.','Same fixed-width enumeration, exact wider final check and identical logical counters.','These are not zcubes-equivalent work units or measured discovery odds.']}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'median_seconds':medians,'speedups':report['speedups']}))
if __name__=='__main__':main()
