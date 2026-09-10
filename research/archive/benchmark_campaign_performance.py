#!/usr/bin/env python3
"""Calibration-only matched policy and 1/2/4-worker performance benchmark.

This deliberately repeats identical generator ranges. Its checks are NOT new
search coverage and its execution timings are NOT solution probabilities.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import resource
import statistics
import subprocess
import time

ROOT = Path(__file__).resolve().parent
CORE_KEYS = ("candidates", "curves", "quotient_points", "exact_tests", "hits",
             "zero_norm", "invalid_d", "unsupported_D", "noninvertible_C",
             "symmetry_rejected", "covered", "rejected_mod243", "rejected_parity")


def cpu_seconds():
    return sum(getattr(resource.getrusage(which), field)
               for which in (resource.RUSAGE_SELF, resource.RUSAGE_CHILDREN)
               for field in ("ru_utime", "ru_stime"))


def hashes():
    names = ("benchmark_campaign_performance.py", "campaign_worker.c", "plane_worker.c",
             "bin/campaign_worker", "bin/plane_worker", "bin/libpari.dylib")
    return {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}


def sysctl(name):
    try:
        r = subprocess.run(["/usr/sbin/sysctl", "-n", name], text=True, capture_output=True, timeout=1)
        return r.stdout.strip() if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def hardware():
    return dict(platform=platform.platform(), architecture=platform.machine(),
                logical_cpus=os.cpu_count(), processor=platform.processor() or None,
                cpu_brand=sysctl("machdep.cpu.brand_string"),
                physical_cpus=sysctl("hw.physicalcpu"), memory_bytes=sysctl("hw.memsize"),
                python=platform.python_version(), load_average=list(os.getloadavg()))


def contexts():
    rows=[]
    for family in ("box", "plane"):
        for ell, box_radius in ((1,50000),(5,85499),(25,146201)):
            radius = 20_000_000 if family == "plane" else box_radius
            for low,high in ((0,64),(256,4096)):
                rows.append(dict(key=f"{family}:{ell}:{radius}:{low}:{high}",
                                 family=family, ell=ell, radius=radius, low=low, high=high))
    return rows


def fingerprint(stats, hits):
    return {key:stats[key] for key in CORE_KEYS}, sorted(hits)


def one(context, count, policy, phase, repeat, seed, timeout):
    binary = ROOT / "bin" / ("plane_worker" if context["family"]=="plane" else "campaign_worker")
    command=[str(binary),"tile",str(context["ell"]),str(context["radius"]),"1140000",
             str(count),str(context["high"]),policy,str(context["low"]),str(seed)]
    start=time.perf_counter()
    r=subprocess.run(command,text=True,capture_output=True,timeout=timeout)
    elapsed=time.perf_counter()-start
    if r.returncode or r.stderr.strip():
        raise RuntimeError(f"{context['key']} {policy}: {r.stderr} {r.stdout}")
    lines=[json.loads(line) for line in r.stdout.splitlines()]
    stats=[line for line in lines if line["type"]=="stats"]
    assert len(stats)==1 and stats[0]["complete"]
    stats=stats[0]
    assert stats["count"]==stats["candidates"]==count
    assert stats["start"]==1140000 and stats["end"]==1140000+count
    assert stats["ell"]==context["ell"] and stats["radius"]==context["radius"]
    assert stats["ratio"]==context["high"] and stats["min_ratio"]==context["low"]
    assert stats["candidates"]==sum(stats[key] for key in (
        "curves","zero_norm","invalid_d","unsupported_D","noninvertible_C",
        "symmetry_rejected","covered"))
    assert stats["quotient_points"]==stats["rejected_mod243"]+stats["rejected_parity"]+stats["exact_tests"]+sum(f["rejected"] for f in stats["filters"])
    hits=[]
    for line in lines:
        if line["type"]=="hit":
            xyz=tuple(sorted(map(int,line["xyz"])))
            assert sum(v**3 for v in xyz)==114
            hits.append((line["index"],str(line["D"]),str(line["r"]),str(line["q"]),xyz))
    assert len(hits)==stats["hits"]
    return dict(context=context, count=count, policy=policy, phase=phase, repeat=repeat,
                elapsed_seconds=elapsed, stats=stats, hits=hits)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-seconds",type=float,default=.12)
    parser.add_argument("--repeats",type=int,default=3)
    parser.add_argument("--seed",type=int,default=1148192)
    parser.add_argument("--cpu-budget",type=float,default=55)
    parser.add_argument("--wall-budget",type=float,default=60)
    parser.add_argument("--output",type=Path,default=ROOT/"runs/campaign-performance.json")
    args=parser.parse_args()
    if not .05<=args.target_seconds<=.3 or not 2<=args.repeats<=3 or not 10<=args.cpu_budget<=55 or not 10<=args.wall_budget<=60:
        parser.error("target 0.05–0.3 s, repeats 2–3, CPU budget10–55 s, wall budget10–60 s required")
    began=time.monotonic();cpu_began=cpu_seconds();rng=random.Random(args.seed)
    identity=hashes()
    result=dict(schema=1,calibration_only=True,counts_are_new_coverage=False,
                interpretation="Repeated identical inputs test execution costs and correctness only; no success-probability or discovery advantage is inferred.",
                configuration=vars(args)|{"output":str(args.output)},hardware=hardware(),
                source_and_binary_sha256=identity,warmups=[],paired_rows=[],scaling_runs=[],failures=[],complete=False)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    def save():
        result["cpu_seconds"]=cpu_seconds()-cpu_began
        result["elapsed_seconds"]=time.monotonic()-began
        args.output.write_text(json.dumps(result,indent=2)+"\n")
    def available(reserve_cpu=0):
        return (cpu_seconds()-cpu_began+reserve_cpu<args.cpu_budget and
                time.monotonic()-began<args.wall_budget-2)
    def execute(c,count,policy,phase,repeat):
        if not available(2):raise RuntimeError("Benchmark budget reached before next bounded subprocess")
        return one(c,count,policy,phase,repeat,args.seed,2)
    try:
        counts={}
        cc=contexts();rng.shuffle(cc)
        for c in cc:
            # Two warmups: an initial probe, then a scaled warmup near target.
            probe=execute(c,100000,"fixed","warmup_probe",0)
            result["warmups"].append(probe)
            count=max(10000,min(10000000,round(100000*args.target_seconds/max(.001,probe["stats"]["wall_seconds"]))))
            warm=execute(c,count,"fixed","warmup_scaled",1)
            result["warmups"].append(warm)
            # One deterministic refinement keeps timed pairs around0.1–0.5s.
            counts[c["key"]]=max(10000,min(10000000,round(count*args.target_seconds/max(.001,warm["stats"]["wall_seconds"]))))
        result["generator_counts_by_context"]=counts
        reference={}
        for repeat in range(args.repeats):
            order=contexts();rng.shuffle(order)
            for c in order:
                policies=["fixed","adaptive"];rng.shuffle(policies)
                pair=[]
                for policy in policies:
                    row=execute(c,counts[c["key"]],policy,"paired",repeat)
                    result["paired_rows"].append(row);pair.append(row)
                    fp=fingerprint(row["stats"],row["hits"])
                    if c["key"] in reference:assert reference[c["key"]]==fp
                    else:reference[c["key"]]=fp
                assert fingerprint(pair[0]["stats"],pair[0]["hits"])==fingerprint(pair[1]["stats"],pair[1]["hits"])
            save()
        policy_summary={}
        for c in contexts():
            medians={p:statistics.median(row["elapsed_seconds"] for row in result["paired_rows"] if row["context"]["key"]==c["key"] and row["policy"]==p) for p in ("fixed","adaptive")}
            policy_summary[c["key"]]=dict(median_seconds=medians,
                selected=min(medians,key=medians.get),adaptive_speedup=medians["fixed"]/medians["adaptive"])
        result["policy_comparison"]=policy_summary
        # Each level runs the same twelve tiles and per-context policy. Only
        # concurrency changes; queue order and level order are randomized.
        workload_cpu_estimate=sum(min(v["median_seconds"].values()) for v in policy_summary.values())
        for repeat in range(args.repeats):
            levels=[1,2,4];rng.shuffle(levels)
            for workers in levels:
                if not available(max(2,workload_cpu_estimate*1.5)):
                    raise RuntimeError("Benchmark budget reached before a complete scaling workload")
                order=contexts();rng.shuffle(order)
                t0=time.perf_counter();before_cpu=cpu_seconds()
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    pending=[pool.submit(one,c,counts[c["key"]],policy_summary[c["key"]]["selected"],
                                         "scaling",repeat,args.seed,2) for c in order]
                    rows=[future.result() for future in pending]
                elapsed=time.perf_counter()-t0
                for row in rows:assert fingerprint(row["stats"],row["hits"])==reference[row["context"]["key"]]
                result["scaling_runs"].append(dict(workers=workers,repeat=repeat,elapsed_seconds=elapsed,
                    cpu_seconds=cpu_seconds()-before_cpu,rows=rows,
                    generators=sum(row["count"] for row in rows),
                    quotient_points=sum(row["stats"]["quotient_points"] for row in rows)))
                save()
        scaling={w:statistics.median(r["elapsed_seconds"] for r in result["scaling_runs"] if r["workers"]==w) for w in (1,2,4)}
        chosen=1;decisions=[]
        for workers in (2,4):
            gain=scaling[chosen]/scaling[workers]-1
            accepted=gain>=.15
            decisions.append(dict(from_workers=chosen,to_workers=workers,marginal_throughput_gain=gain,accepted=accepted))
            if accepted:chosen=workers
        result["scaling_summary"]=dict(median_workload_seconds=scaling,
            speedup_over_one={w:scaling[1]/elapsed for w,elapsed in scaling.items()},decisions=decisions)
        result["default_recommendation"]=dict(workers=chosen,marginal_gain_cutoff=.15,
            scope="This measured Mac workload and machine load only; repeat after substantial backend or load changes.",
            caveat="Three timing repetitions are a local calibration, not a guarantee about sustained thermal performance.")
        assert hashes()==identity,"Source or binary changed during calibration"
        result["matched_input_checks_passed"]=True
        result["complete"]=True
    except Exception as exc:
        result["failures"].append(dict(type=type(exc).__name__,message=str(exc)))
        result["default_recommendation"]=dict(workers=1,scope="Conservative fallback: calibration did not complete.")
    result["hardware"]["load_average_end"]=list(os.getloadavg())
    save()
    print(json.dumps({key:result[key] for key in ("complete","cpu_seconds","elapsed_seconds","default_recommendation","failures")},indent=2))
    if not result["complete"]:raise SystemExit(1)


if __name__=="__main__":
    main()
