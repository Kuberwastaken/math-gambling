#!/usr/bin/env python3
"""Blind candidate-policy benchmark; no known d, root, or coordinates are inputs.

Whole-k holdout, deterministic seeds, equal attempted-generator budgets. This
measures small-k discovery performance, not the chance of solving 114.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parent
ARMS = ("uniform", "balanced", "thin_real")
MIN_HEIGHT = 1000  # Fixed benchmark target before consulting known solutions.

GP_SOURCE = r'''
bench(k,A,seed,count,R,arm) = {
  my(seen=Map(),sols=Map(),curves=0,duplicates=0,attempts=0);
  my(a,b,c,cs,key,points,alpha=sqrtn(k,3),ba=A,bb=A,bc=A,t0=getwalltime());
  my(histo=vector(20),hh,dd,rr);
  if(arm==1,ba=ceil(A*alpha^2);bb=ceil(A*alpha));
  setrand(seed);
  for(j=1,count,
    b=random(2*bb+1)-bb;c=random(2*bc+1)-bc;
    if(arm==2,a=-round(alpha*b+alpha^2*c)+random(17)-8,a=random(2*ba+1)-ba);
    cs=norm_candidates(k,a,b,c,[1]);
    for(i=1,#cs,
      attempts++;dd=cs[i][1];rr=cs[i][2];key=[dd,rr];
      if(mapisdefined(seen,key),duplicates++;next);
      mapput(seen,key,1);curves++;
      hh=min(20,#digits(dd));histo[hh]++;
      points=curve_points(k,dd,rr,R,0,0);
      for(h=1,#points,if(!mapisdefined(sols,points[h]),mapput(sols,points[h],1);print("HIT ",[k,arm,points[h],dd,rr])));
    );
  );
  print("STATS ",[k,arm,seed,count,attempts,curves,duplicates,getwalltime()-t0,histo]);
};
'''


def eligible(k):
    return k != 114 and k % 9 in (3, 6) and not any(
        k % (p**3) == 0 for p in range(2, math.isqrt(k) + 1)
    )


def split(k):
    # Entire k, not individual solutions, are withheld from policy selection.
    return "test" if hashlib.sha256(f"three-cubes-blind-v1:{k}".encode()).digest()[0] % 3 == 0 else "train"


def known_solutions(path):
    out = {}
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) != 4:
            continue
        try:
            k, x, y, z = map(int, parts)
        except ValueError:
            continue
        if x**3 + y**3 + z**3 != k:
            raise ValueError(f"Invalid reference row {line}")
        if max(abs(x), abs(y), abs(z)) >= MIN_HEIGHT:
            out.setdefault(k, set()).add(tuple(sorted((x, y, z))))
    return out


def aggregate(rows):
    result = {}
    for arm in ARMS:
        rr = [row for row in rows if row["arm"] == arm]
        target_hits = sum(len(row["target_hits"]) for row in rr)
        seconds = sum(row["elapsed_seconds"] for row in rr)
        result[arm] = dict(
            cases=len(rr), generators=sum(row["generators"] for row in rr),
            curves=sum(row["unique_curves"] for row in rr),
            cases_with_target_hit=sum(bool(row["target_hits"]) for row in rr),
            target_hits=target_hits, seconds=seconds,
            target_hits_per_second=target_hits / seconds if seconds else 0,
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-k", type=int, default=200)
    parser.add_argument("--count", type=int, default=10000)
    parser.add_argument("--radius", type=int, default=32)
    parser.add_argument("--ratio", type=int, default=128)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--reference", type=Path, default=ROOT.parent.parent / "work/literature/huisman.txt")
    parser.add_argument("--output", type=Path, default=ROOT / "runs/blind-benchmark.json")
    args = parser.parse_args()
    if min(args.count, args.radius, args.ratio) <= 0 or args.max_k < 6:
        parser.error("Positive budgets and max-k >= 6 required")
    ks = [k for k in range(3, args.max_k + 1) if eligible(k)]
    base = f'read("{ROOT / "norm_search.gp"}");\n' + GP_SOURCE + "\n"
    result = dict(
        schema=1, configuration=vars(args) | {"reference": str(args.reference), "output": str(args.output)},
        policy="Maximum training target hits per end-to-end second; ties use fixed arm order.",
        minimum_target_height=MIN_HEIGHT,
        data_separation="Generator sees only k, fixed coefficient bounds, seed and R. Reference coordinates are loaded only after all search runs complete. Entire k split before search by fixed SHA256; 114 excluded.",
        limitations=[
            "Small-k experiment, not validation at the 114 frontier.",
            "Only principal-norm multiplier 1 is sampled equally in all arms.",
            "Fixed R misses solutions with greater cancellation ratio.",
            "Policies induce different norm distributions; comparison is discovery per budget, not a causal isolation of coefficient shape.",
            "No exhaustive coverage claim; within-case curve deduplication only.",
            "Sparse hits and one seed per k cannot calibrate success probabilities.",
        ],
        splits={part: [k for k in ks if split(k) == part] for part in ("train", "test")},
        source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__), ROOT / "norm_search.gp")},
        rows=[], failures=[],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    began = time.monotonic()
    winner = None
    for part in ("train", "test"):
        for k in result["splits"][part]:
            for arm_i, arm in enumerate(ARMS):
                seed = 771100000 + k
                source = base + f"bench({k},{args.radius},{seed},{args.count},{args.ratio},{arm_i});\nquit;\n"
                t0 = time.monotonic()
                try:
                    run = subprocess.run([str(ROOT / "bin/gp"), "-q", "-f"], input=source, text=True, capture_output=True, timeout=args.timeout)
                    if run.returncode or run.stderr.strip():
                        raise RuntimeError(run.stderr + run.stdout)
                    hits, stats = [], None
                    for line in run.stdout.splitlines():
                        if line.startswith("HIT "):
                            found_k, found_arm, xyz, dd, rr = json.loads(line[4:])
                            assert found_k == k and found_arm == arm_i
                            assert sum(v**3 for v in xyz) == k
                            assert pow(rr, 3, dd) == k % dd
                            hits.append(dict(xyz=xyz, d=dd, root=rr))
                        elif line.startswith("STATS "):
                            stats = json.loads(line[6:])
                    if stats is None or stats[:4] != [k, arm_i, seed, args.count]:
                        raise RuntimeError("Missing/mismatched statistics")
                    row = dict(k=k, split=part, arm=arm, seed=seed, generators=args.count,
                               candidate_attempts=stats[4], unique_curves=stats[5], duplicate_curves=stats[6],
                               gp_milliseconds=stats[7], d_digits_histogram=stats[8],
                               elapsed_seconds=time.monotonic()-t0, hits=hits,
                               target_hits=[hit for hit in hits if max(map(abs, hit["xyz"])) >= MIN_HEIGHT])
                    result["rows"].append(row)
                    print(f"{part} k={k} {arm}: {len(row['target_hits'])} target hits; {row['unique_curves']} curves; {row['elapsed_seconds']:.3f}s", flush=True)
                except Exception as exc:
                    result["failures"].append(dict(k=k, split=part, arm=arm, error=str(exc), elapsed_seconds=time.monotonic()-t0))
                    print(f"FAILED {part} k={k} {arm}: {exc}", flush=True)
                args.output.write_text(json.dumps(result, indent=2) + "\n")
        result[part] = aggregate([row for row in result["rows"] if row["split"] == part])
        if part == "train":
            winner = max(ARMS, key=lambda arm: result[part][arm]["target_hits_per_second"])
            result["training_selected_arm"] = winner
            print(f"Training selected {winner}; held-out evaluation follows without retuning.", flush=True)
    # The reference dataset is intentionally not opened until after search.
    reference = known_solutions(args.reference)
    result["reference_sha256"] = hashlib.sha256(args.reference.read_bytes()).hexdigest()
    for row in result["rows"]:
        row["target_hits_in_reference"] = sum(tuple(hit["xyz"]) in reference.get(row["k"], set()) for hit in row["target_hits"])
        row["reference_target_count"] = len(reference.get(row["k"], set()))
    result["elapsed_seconds"] = time.monotonic() - began
    result["heldout_selected_arm"] = result["test"][winner]
    result["recommendation"] = "Retain fixed exploration of all arms. This short experiment is evidence for small-k scheduling only; do not translate its winner into a success probability or exclusion rule for 114."
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("train", "test", "training_selected_arm", "failures", "elapsed_seconds")}, indent=2))


if __name__ == "__main__":
    main()
