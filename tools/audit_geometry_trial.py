"""Replay a deterministic bounded sample of a compact geometry-trial journal."""
import argparse
import gzip
import hashlib
import json
import random
from pathlib import Path
from search_core import run_task, verify_triple
from strategy_model import digest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('journal',type=Path)
    p.add_argument('--sample',type=int,default=32)
    p.add_argument('--seed',type=int,default=913114)
    a=p.parse_args()
    if not 1<=a.sample<=256:p.error('sample must be in [1,256]')
    rng=random.Random(a.seed);sample=[];count=0
    with gzip.open(a.journal,'rt') as f:
        for count,line in enumerate(f,1):
            entry=json.loads(line)
            if count<=a.sample:sample.append(entry)
            else:
                j=rng.randrange(count)
                if j<a.sample:sample[j]=entry
    if not sample:raise ValueError('empty journal')
    def rescue(hit):
        if not verify_triple(hit['xyz']):raise ArithmeticError('invalid identity')
        from runner import atomic_json
        atomic_json(a.journal.parent/('DISCOVERY-'+digest(hit)+'.json'),hit)
        raise RuntimeError('Exact identity saved; stopping audit')
    for item in sample:
        curves=[]
        result=run_task(item['task'],on_curve=curves.append,on_hit=rescue)
        if (result['digest']!=item['digest'] or digest(curves)!=item['curves_hash']
                or len(curves)!=item['curve_count'] or result['counters']['exact_tests']!=item['exact_tests']):
            raise ValueError('task or mathematical interval replay mismatch')
    print(json.dumps({'journal_sha256':hashlib.sha256(a.journal.read_bytes()).hexdigest(),
                      'tasks':count,'sampled':len(sample),'seed':a.seed,'matched':True}))


if __name__=='__main__':main()
