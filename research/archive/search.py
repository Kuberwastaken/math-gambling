#!/usr/bin/env python3
"""Bounded, resumable local experiment; not an exhaustive search or probability model."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parent
GP = ROOT / 'bin' / 'gp'
SOURCE = ROOT / 'norm_search.gp'


def gp_batch(args, index):
    seed = args.seed + index
    command = f'read("{SOURCE}");\nrun_batch(114,{args.radius},{seed},{args.batch_size},{args.ratio},{10**19//54},{10**19},[1,5,25]);\nquit;\n'
    start = time.monotonic()
    result = subprocess.run([str(GP), '-q', '-f'], input=command, text=True,
                            capture_output=True, timeout=args.batch_timeout)
    if result.returncode or result.stderr.strip():
        raise RuntimeError(f'GP batch {index} failed: {result.stderr} {result.stdout}')
    stats = None
    hits = []
    for line in result.stdout.splitlines():
        if line.startswith('STATS '):
            values = json.loads(line[6:])
            names = ['seed','coefficient_triples','candidate_pairs','curves',
                     'duplicates_within_batch','excluded_by_reported_coverage',
                     'hits','gp_wall_ms','min_d','max_d']
            stats = dict(zip(names, values))
        elif line.startswith('HIT '):
            hit = json.loads(line[4:])
            k, xyz, d, r, abc, multiplier = hit
            assert sum(v**3 for v in xyz) == k == 114
            assert min(map(abs,xyz)) > 10**17
            assert d > 10**19//54 or min(map(abs,xyz)) > 10**19
            hits.append(hit)
    if stats is None:
        raise RuntimeError(f'Batch {index} did not complete: {result.stdout}')
    return dict(index=index,stats=stats,solutions=hits,elapsed_seconds=time.monotonic()-start)


def batch(args, index):
    if args.engine == 'gp':
        return gp_batch(args,index)
    seed=args.seed+index
    start=time.monotonic()
    command=[str(ROOT/'bin/native_search'),args.sampler,str(seed),str(args.batch_size),str(args.radius),str(args.ratio)]
    run=subprocess.run(command,text=True,capture_output=True,timeout=args.batch_timeout,check=True)
    if run.stderr.strip():raise RuntimeError(run.stderr)
    stats=None
    hits=[]
    for line in run.stdout.splitlines():
        if line.startswith('STATS '):stats=json.loads(line[6:])
        elif line.startswith('CLASSES '):stats['class_curves']=json.loads(line[8:])
        elif line.startswith('HIT '):
            k,xyz=json.loads(line[4:])
            assert sum(v**3 for v in xyz)==k==114
            xx,yy,zz=sorted(xyz,key=abs,reverse=True)
            d=abs(xx+yy)
            assert abs(zz)>10**17
            assert d>10**19//54 or abs(zz)>10**19
            hits.append([k,sorted(xyz),d,zz%d])
    if stats is None:raise RuntimeError('Native batch did not finish')
    stats.update(seed=seed,coefficient_triples=args.batch_size)
    return dict(index=index,stats=stats,solutions=hits,elapsed_seconds=time.monotonic()-start)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sampler',choices=['class-scan','scan'],default='class-scan')
    p.add_argument('--engine', choices=['native','gp'], default='native')
    p.add_argument('--minutes', type=float, default=2)
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--radius', type=int, default=50000)
    p.add_argument('--ratio', type=int, default=64)
    p.add_argument('--batch-size', type=int, default=1000000)
    p.add_argument('--batch-timeout', type=float, default=60)
    p.add_argument('--seed', type=int, default=114000000)
    p.add_argument('--ledger', type=Path, default=ROOT/'runs'/'class-pilot.jsonl')
    p.add_argument('--max-batches', type=int)
    args = p.parse_args()
    if not (args.minutes > 0 and 1 <= args.workers <= (os.cpu_count() or 1)
            and 1 <= args.radius <= 80000 and 4 <= args.ratio <= 1000000 and args.batch_size > 0
            and args.batch_timeout > 0 and args.seed > 0
            and (args.max_batches is None or args.max_batches > 0)):
        p.error('Invalid positive bound or worker count.')
    source=SOURCE if args.engine=='gp' else ROOT/'native_search.c'
    identity = dict(engine=args.engine,sampler=args.sampler if args.engine=='native' else 'gp-norm-cube',k=114, radius=args.radius, ratio=args.ratio, batch_size=args.batch_size,
                    seed=args.seed, gp_version='2.17.4',
                    code_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    args.ledger.parent.mkdir(parents=True,exist_ok=True)
    records = []
    if args.ledger.exists():
        records = [json.loads(s) for s in args.ledger.read_text().splitlines() if s.strip()]
        if not records or records[0].get('config') != identity:
            p.error('Ledger configuration differs. Choose a new ledger path.')
    completed = {r['index'] for r in records if 'index' in r}
    total_curves = sum(r['stats']['curves'] for r in records if 'stats' in r)
    deadline = time.monotonic()+60*args.minutes
    submitted = 0
    index = 0
    with args.ledger.open('a', buffering=1) as log:
        if not records:
            log.write(json.dumps({'config':identity,'created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                                  'coverage':'selective; native has no deduplication, GP deduplicates only within each batch'})+'\n')
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            pending = {}
            def submit_one():
                nonlocal index, submitted
                while index in completed: index += 1
                fut = pool.submit(batch,args,index)
                pending[fut] = index
                index += 1
                submitted += 1
            while len(pending)<args.workers and (args.max_batches is None or submitted<args.max_batches):
                submit_one()
            while pending:
                ready,_ = concurrent.futures.wait(pending,return_when=concurrent.futures.FIRST_COMPLETED)
                found = False
                for fut in ready:
                    pending.pop(fut)
                    record=fut.result()
                    log.write(json.dumps(record)+'\n')
                    total_curves += record['stats']['curves']
                    print(f"batch {record['index']}: {record['stats']['curves']:,} curves; "
                          f"{total_curves:,} cumulative; {len(record['solutions'])} exact hits",flush=True)
                    if record['solutions']:
                        print(json.dumps(record['solutions']),flush=True)
                        found=True
                if found: deadline=0
                while (time.monotonic()<deadline and len(pending)<args.workers
                       and (args.max_batches is None or submitted<args.max_batches)):
                    submit_one()
    print(f'Ledger: {args.ledger}')


if __name__ == '__main__':
    main()
