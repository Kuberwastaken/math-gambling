#!/usr/bin/env python3
"""Verify the exact prerequisites of NONOVERLAP.md for this campaign geometry."""
from pathlib import Path
from fractions import Fraction
import hashlib
import json
import math
import sqlite3
import subprocess
import campaign

ROOT = Path(__file__).resolve().parent


def main():
    folder = ROOT/'runs/campaign'
    db = sqlite3.connect(f'file:{folder/"campaign.sqlite3"}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    db.execute('BEGIN')
    audit = campaign.audit(db)
    config = json.loads(db.execute("SELECT value FROM meta WHERE key='config'").fetchone()[0])
    failures = db.execute("SELECT count(*) FROM events WHERE kind IN ('job_failure','recovered_interrupted_jobs')").fetchone()[0]
    attempts = db.execute('SELECT max(attempts) FROM jobs').fetchone()[0]
    for name, sha in config['sources'].items():
        assert campaign.digest(ROOT/name) == sha, name
    specs = config['contexts']
    assert specs == campaign.contexts(True)
    assert len(specs) == 18 and max(s['high'] for s in specs) == 4096
    for family in ('box', 'plane'):
        for ell in (1,5,25):
            bands = sorted((s['low'],s['high']) for s in specs if s['family']==family and s['ell']==ell)
            assert bands == [(0,64),(64,256),(256,4096)]
            for s in specs:
                if s['family']==family and s['ell']==ell:
                    stride, _ = campaign.permutation(s,config['permutation_seed'])
                    assert math.gcd(stride,s['total']) == 1
    db.close()
    # Exact certification that the supplied beta generates the free unit group.
    gp = '''K=bnfinit(t^3-114,1); if(bnfcertify(K)!=1,error("field certification failed")); if(K.zk!=[1,t,t^2],error("basis mismatch")); if(K.cyc!=[3],error("class group mismatch")); J=idealhnf(K,5,t-4); if(bnfisprincipal(K,J,0)[1]%3==0,error("J is principal")); if(idealpow(K,J,2)!=idealhnf(K,25,t-4),error("J squared mismatch")); beta=Mod(4133238949+852423792*t+175800705*t^2,t^3-114); U=bnfisunit(K,beta); if(abs(U[1])!=1 || K.tu[1]!=2,error("unit group mismatch")); print("FIELD_CERTIFIED=1"); print("CLASS_GROUP=",K.cyc); print("BETA_UNIT_EXPONENTS=",U); print("ROOTS_OF_UNITY=",K.tu[1]); print("NORM_BETA=",nfeltnorm(K,beta)); quit;
'''
    result = subprocess.run([str(ROOT/'bin/gp'),'-q','-f'], input=gp,
                            text=True,capture_output=True,timeout=20)
    assert result.returncode == 0 and not result.stderr.strip(), result.stderr
    assert 'FIELD_CERTIFIED=1' in result.stdout and 'NORM_BETA=1' in result.stdout
    # Cubing rational endpoints avoids trusting floating-point embeddings.
    scale = 10**18
    for numerator, cube in [(4848807585839879338,114),(23510935004498358840,114**2)]:
        assert (numerator-1)**3 < cube*scale**3 < (numerator+1)**3
    # The only mod-5 lattice point with C=0 is the zero coefficient triple.
    for a in range(5):
        for b in range(5):
            for c in range(5):
                if (a+4*b+16*c)%5 == 0 and (b*b-a*c)%5 == 0:
                    assert (a,b,c) == (0,0,0)
    d_min = 10**19//4096+1
    beta_lower = 4133238949
    bounds=[]
    for ell,h in [(1,50000),(5,85499),(25,146201)]:
        box = 31*h+ell-1
        plane_real, plane_complex = 3*ell, 10**9
        assert 48*20_000_000+plane_real < plane_complex
        n_min = ell*d_min
        ratios = {
            'within_box_max':Fraction(box**3,n_min),
            'within_plane_max':Fraction(plane_real*plane_complex**2,n_min),
            'box_over_plane_min':Fraction(n_min,box**2*plane_real),
            'box_over_plane_max':Fraction(box*plane_complex**2,n_min),
        }
        assert ratios['within_box_max'] < beta_lower
        assert ratios['within_plane_max'] < beta_lower
        assert ratios['box_over_plane_min'] > 1
        assert ratios['box_over_plane_max'] < beta_lower
        bounds.append(dict(ell=ell,box_embedding_upper=box,
                           plane_real_upper=plane_real,plane_complex_upper=plane_complex,
                           exact_ratios={k:str(v) for k,v in ratios.items()},
                           approximate_ratios={k:float(v) for k,v in ratios.items()}))
    evidence=dict(passed=True,scope='No repeated (D,r,z) positions among completed tiles of this exact campaign; same (D,r) can occur in disjoint z bands.',
                  ledger_audit=audit, interrupted_or_failed_events=failures,
                  maximum_job_attempts=attempts, exact_d_min=d_min,
                  beta_lower_bound=beta_lower, bounds=bounds,
                  field_certificate=result.stdout, field_certificate_gp=gp,
                  sources=config['sources'], certificate_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  assumptions='The mathematical argument is in NONOVERLAP.md; this is not a formal proof of the entire implementation. Existing finite symmetry and band validators remain prerequisites.',
                  retries_can_repeat_partial_work=bool(failures or attempts>1),
                  other_campaigns_and_calibration_runs_not_covered=True)
    (ROOT/'runs/nonoverlap-certificate.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({k:evidence[k] for k in ['passed','scope','ledger_audit','interrupted_or_failed_events','maximum_job_attempts','exact_d_min','bounds']},indent=2))


if __name__ == '__main__':
    main()
