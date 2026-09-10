#!/usr/bin/env python3
"""Exhaustively certify necessary modular filters; never uses search failures.

S denotes the SIGNED pair sum x+y. Absolute D filters use its forced mod3 sign.
"""
import hashlib
import json
import math
from pathlib import Path
import time

HERE=Path(__file__).resolve().parent


def main():
    began=time.monotonic();results=[]
    for modulus in (4,8,16,19,361,27,81):
        cube=[pow(x,3,modulus) for x in range(modulus)]
        cube_set=set(cube)
        witnesses={}
        root={value:next(z for z in range(modulus) if cube[z]==value) for value in cube_set}
        allowed=[]
        for s in range(modulus):
            exists=False
            for x in range(modulus):
                target=(114-cube[x]-cube[(s-x)%modulus])%modulus
                if target in cube_set:
                    z=root[target];y=(s-x)%modulus
                    assert (x**3+y**3+z**3-114)%modulus==0
                    witnesses[s]=[x,y,z];exists=True;break
            allowed.append(exists)
        oracle_checked=modulus<=27
        if oracle_checked:
            oracle=set()
            for x in range(modulus):
                for y in range(modulus):
                    for z in range(modulus):
                        if (x*x*x+y*y*y+z*z*z-114)%modulus==0:oracle.add((x+y)%modulus)
            assert oracle=={s for s in range(modulus) if allowed[s]}
        # k114 forces all coordinates2mod3 and S1mod3, so for D=|S|:
        # S=+D whenD1mod3; S=-D whenD2mod3. D0mod3 is impossible.
        combined=math.lcm(modulus,3)
        valid_d=[d%3!=0 and allowed[(d if d%3==1 else -d)%modulus] for d in range(combined)]
        payload=dict(k=114,modulus=modulus,allowed_signed_S=allowed)
        certificate=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        result=dict(modulus=modulus,forbidden_signed_S=[s for s in range(modulus) if not allowed[s]],
                    allowed_signed_S=allowed,witnesses=witnesses,
                    absolute_D_modulus=combined,allowed_absolute_D=valid_d,
                    certificate_sha256=certificate,independent_cubic_oracle_checked=oracle_checked)
        results.append(result)
    output=dict(kind='exhaustive_modular_necessary_conditions',results=results,
                elapsed_seconds=time.monotonic()-began,
                proof='Polynomial congruences depend only on residue classes. For each signedS all x residues are checked against the complete z-cube residue set. A forbiddenS excludes every integer triple with that signed pair-sum residue. Passing is necessary, never sufficient.',
                production_integrated=False,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (HERE/'modular-filter-certificates.json').write_text(json.dumps(output,indent=2)+'\n')
    for r in results:print(f"m={r['modulus']}, forbidden signed S={r['forbidden_signed_S']}, certificate={r['certificate_sha256']}")
    print(f"Elapsed {output['elapsed_seconds']:.3f} seconds; no production changes.")


if __name__=='__main__':main()
