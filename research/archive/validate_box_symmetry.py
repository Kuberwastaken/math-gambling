#!/usr/bin/env python3
"""Check native symmetry membership against complete small generator domains.

Compares all (D,r,q) candidates, including non-solutions, before and after
pruning. This checks equivalence pruning, not merely zero-hit agreement.
"""
from pathlib import Path
import hashlib
import json
import math
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
HEADERS = ROOT.parent.parent / 'work/pari-include'


def main():
    source = '''
#define main hidden_worker_main
#include "WORKER"
#undef main
int main(int argc,char **argv){
  if(argc!=3)return 2;
  long ell=(long)parse(argv[1]),A=(long)parse(argv[2]);
  for(long c=-A;c<=A;c++)for(long b=-A;b<=A;b++)for(long t=-(A/ell);t<=A/ell;t++){
    long a=ell*t+mod128(-4*b-16*c,(int)ell);
    printf("%ld %ld %ld %d\\n",a,b,c,box_symmetry_duplicate(ell,A,a,b,c));
  }
  return 0;
}
'''.replace('WORKER', str(ROOT / 'campaign_worker.c'))
    results = []
    with tempfile.TemporaryDirectory(prefix='symmetry-', dir=ROOT.parent.parent/'work') as tmp:
        tmp = Path(tmp)
        (tmp / 'probe.c').write_text(source)
        os.symlink(ROOT / 'bin/libpari.dylib', tmp / 'libpari.dylib')
        subprocess.run(['clang', '-O1', '-fsanitize=undefined', '-fno-sanitize-recover=all',
                        '-I', str(HEADERS), str(tmp/'probe.c'), '-L', str(ROOT/'bin'),
                        '-lpari', '-o', str(tmp/'probe')], check=True)
        for ell, radius in ((1, 8), (5, 8), (25, 8), (25, 30)):
            p = subprocess.run([str(tmp/'probe'), str(ell), str(radius)], text=True,
                               capture_output=True, check=True)
            assert not p.stderr.strip(), p.stderr
            rows = [tuple(map(int, line.split())) for line in p.stdout.splitlines()]
            domain = {(a,b,c) for a,b,c,_ in rows}
            unpruned, kept = set(), set()
            skipped, boundary_kept = 0, 0
            for a,b,c,skip in rows:
                negative = (c,b,a) < (0,0,0)
                opposite_in_domain = (-a,-b,-c) in domain
                assert bool(skip) == (negative and opposite_in_domain)
                if skip:
                    skipped += 1
                    assert (c,b,a) != (0,0,0)
                elif negative and not opposite_in_domain:
                    boundary_kept += 1
                norm = a**3 + 114*b**3 + 12996*c**3 - 342*a*b*c
                assert norm % ell == 0
                d = abs(norm)//ell
                C, B = b*b-a*c, 114*c*c-a*b
                if d < 2 or d%3 == 0 or math.gcd(C,d) != 1:
                    continue
                r = B*pow(C,-1,d)%d
                assert pow(r,3,d) == 114%d
                qs = range(-4, 4 if r else 5)
                values = {(d,r,q) for q in qs}
                unpruned.update(values)
                if not skip:
                    kept.update(values)
            assert unpruned == kept, (ell,radius,len(unpruned-kept))
            assert skipped > 0
            results.append(dict(ell=ell,radius=radius,inputs=len(rows),symmetry_rejected=skipped,
                                asymmetric_boundary_representatives_kept=boundary_kept,
                                distinct_D_r_q=len(unpruned),coverage_equal=True))
    report = dict(domains=results,ubsan=True,
                  source_sha256=hashlib.sha256((ROOT/'campaign_worker.c').read_bytes()).hexdigest(),
                  scope='All candidate (D,r,q) triples at ratio4 across complete small coefficient domains')
    out = ROOT/'runs/box-symmetry-validation.json'
    out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
