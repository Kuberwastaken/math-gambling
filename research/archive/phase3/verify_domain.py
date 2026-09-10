#!/usr/bin/env python3
"""Exact prerequisites for DOMAIN_PROOF.md; importing performs no I/O.

validate_contexts is a production geometry guard, not a ledger or worker audit.
The command reruns the field certificate and writes reproducible evidence.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import itertools
import json
import math
from pathlib import Path
import resource
import subprocess
import time


ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent
SCALE = 10**18
ALPHA_NUM = 4848807585839879338
ALPHA2_NUM = 23510935004498358840
D0 = 10**19 // 54
BETA_LOWER = 4133238949
SHAPES = ((6_000_000, 8, 31), (1_500_000, 128, 511),
          (375_000, 2048, 8191))
ELLS = (1, 5, 25)
BANDS = ((0, 64), (64, 256), (256, 4096))
SHELLS = ((D0, 2*D0), (2*D0, 4*D0), (4*D0, 8*D0))
GEOMETRY_FIELDS = ('ell', 'radius', 'tlo', 'thi', 'dlo', 'dhi', 'low', 'high')
EXPECTED_GEOMETRY = frozenset(
    (ell, radius, tlo, thi, dlo, dhi, low, high)
    for ell, (radius, tlo, thi), (dlo, dhi), (low, high)
    in itertools.product(ELLS, SHAPES, SHELLS, BANDS)
)


def validate_contexts(specs):
    """Reject any production context table outside the exact 81-context proof.

    Additional controller metadata is allowed. Geometry integers reject bools;
    weights must be finite positive int/float values and are not coverage claims.
    This function intentionally rejects subsets. Unit tests needing a subset
    may test lower-level initialization without calling this production guard.
    """
    if not isinstance(specs, (list, tuple)) or len(specs) != 81:
        raise ValueError('phase2 production requires exactly 81 contexts')
    seen_geometry, seen_keys = set(), set()
    for spec in specs:
        if not isinstance(spec, dict):
            raise ValueError('context must be a dictionary')
        if any(type(spec.get(k)) is not int for k in GEOMETRY_FIELDS):
            raise ValueError('geometry fields must be exact integers')
        geometry = tuple(spec[k] for k in GEOMETRY_FIELDS)
        if geometry not in EXPECTED_GEOMETRY or geometry in seen_geometry:
            raise ValueError('context geometry is unproved or duplicated')
        seen_geometry.add(geometry)
        if spec.get('family') != 'offset':
            raise ValueError('phase2 geometry requires family=offset')
        key = spec.get('key')
        if not isinstance(key, str) or not key or key in seen_keys:
            raise ValueError('context keys must be nonempty distinct strings')
        seen_keys.add(key)
        if type(spec.get('total')) is not int or spec['total'] != (2*spec['radius']+1)**2:
            raise ValueError('context total must equal its exact row-domain size')
        weight = spec.get('weight')
        try:
            valid_weight = type(weight) in (int, float) and math.isfinite(weight) and weight > 0
        except OverflowError:
            valid_weight = False
        if not valid_weight:
            raise ValueError('context weight must be finite and positive')
    if seen_geometry != EXPECTED_GEOMETRY:
        raise ValueError('context table does not cover the fixed geometry set')
    return True


def example_contexts():
    """Deterministic geometry fixture; production owns its names and weights."""
    result = []
    for index, geometry in enumerate(sorted(EXPECTED_GEOMETRY)):
        row = dict(zip(GEOMETRY_FIELDS, geometry))
        row.update(family='offset', key=f'domain-fixture-{index}', weight=1.0,
                   total=(2*row['radius']+1)**2)
        result.append(row)
    return result


def _check(condition, message):
    if not condition:
        raise AssertionError(message)


def _poly_add(*polys):
    result = {}
    for poly in polys:
        for powers, coefficient in poly.items():
            result[powers] = result.get(powers, 0) + coefficient
    return {powers: coefficient for powers, coefficient in result.items() if coefficient}


def _poly_scale(poly, factor):
    return {powers: factor*coefficient for powers, coefficient in poly.items() if factor*coefficient}


def _poly_mul(left, right):
    result = {}
    for p, a in left.items():
        for q, b in right.items():
            powers = tuple(x+y for x, y in zip(p, q))
            result[powers] = result.get(powers, 0) + a*b
    return {powers: coefficient for powers, coefficient in result.items() if coefficient}


def polynomial_certificate():
    a, b, c = {(1, 0, 0): 1}, {(0, 1, 0): 1}, {(0, 0, 1): 1}
    square = lambda x: _poly_mul(x, x)
    cube = lambda x: _poly_mul(square(x), x)
    A = _poly_add(square(a), _poly_scale(_poly_mul(b, c), -114))
    B = _poly_add(_poly_scale(square(c), 114), _poly_scale(_poly_mul(a, b), -1))
    C = _poly_add(square(b), _poly_scale(_poly_mul(a, c), -1))
    N = _poly_add(cube(a), _poly_scale(cube(b), 114),
                  _poly_scale(cube(c), 12996),
                  _poly_scale(_poly_mul(_poly_mul(a, b), c), -342))
    identities = {
        'B^3-114C^3=N(114c^3-b^3)': _poly_add(cube(B), _poly_scale(cube(C), -114),
            _poly_scale(_poly_mul(N, _poly_add(_poly_scale(cube(c), 114),
                                              _poly_scale(cube(b), -1))), -1)),
        'A^2-114BC=Na': _poly_add(square(A), _poly_scale(_poly_mul(B, C), -114),
                                 _poly_scale(_poly_mul(N, a), -1)),
        'B^2-AC=Nc': _poly_add(square(B), _poly_scale(_poly_mul(A, C), -1),
                               _poly_scale(_poly_mul(N, c), -1)),
        'aC+bB+cA=0': _poly_add(_poly_mul(a, C), _poly_mul(b, B), _poly_mul(c, A)),
    }
    for name, residual in identities.items():
        _check(not residual, f'polynomial identity failed: {name}')
    for a, b, c in itertools.product(range(5), repeat=3):
        if (a+4*b+16*c) % 5 == 0 and (b*b-a*c) % 5 == 0:
            _check((a, b, c) == (0, 0, 0), 'unexpected mod5 lattice root')
    _check([x for x in range(5) if (x**3-114) % 5 == 0] == [4], 'root modulo5')
    _check(all((x*x+4*x+1) % 5 for x in range(5)), 'quadratic factor reducible')
    _check((3*4*4) % 5 != 0, 'root not simple')
    return list(identities)


def _fractions(values):
    return {'exact': {k: str(v) for k, v in values.items()},
            'approximate': {k: float(v) for k, v in values.items()}}


def geometry_certificate():
    for numerator, cube in ((ALPHA_NUM, 114), (ALPHA2_NUM, 114**2)):
        _check((numerator-1)**3 < cube*SCALE**3 < (numerator+1)**3,
               'rational embedding bracket failed')
    shapes, separation, arithmetic = [], [], []
    for ell, box_radius in zip(ELLS, (50000, 85499, 146201)):
        intervals = []
        for radius, tlo, thi in SHAPES:
            eps = Fraction(2*radius, SCALE)
            lower = Fraction(ell*(2*tlo-1), 2)-eps
            upper = Fraction(ell*(2*thi+1), 2)+eps
            _check(0 < lower < upper, 'nonpositive real embedding')
            intervals.append((lower, upper))
            shapes.append(dict(ell=ell, radius=radius, tlo=tlo, thi=thi,
                               **_fractions(dict(epsilon=eps, real_lower=lower, real_upper=upper))))
        for previous, following in zip(intervals, intervals[1:]):
            _check(previous[1] < following[0], 'offset shape overlap')
        lower = min(x[0] for x in intervals)
        upper = max(x[1] for x in intervals)
        box = 31*box_radius+ell-1
        n_min = ell*(D0+1)
        ratios = dict(within_new_max=upper/lower,
                      box_over_new_min=Fraction(n_min, box**2)/upper,
                      box_over_new_max=Fraction(box)/lower,
                      new_over_plane_min=lower/(3*ell),
                      new_over_plane_max=upper*10**18/n_min)
        _check(ratios['within_new_max'] < BETA_LOWER, 'unit wrap within new geometry')
        _check(1 < ratios['box_over_new_min'], 'new region reaches old box')
        _check(ratios['box_over_new_max'] < BETA_LOWER, 'unit wrap against old box')
        _check(1 < ratios['new_over_plane_min'], 'new region reaches old plane')
        _check(ratios['new_over_plane_max'] < BETA_LOWER, 'unit wrap against old plane')
        _check(48*20_000_000+3*ell < 10**9, 'old plane complex bound')
        separation.append(dict(ell=ell, old_box_upper=box, **_fractions(ratios)))

    int64_max, int128_max, uint64_max = 2**63-1, 2**127-1, 2**64-1
    for radius, tlo, thi in SHAPES:
        ell = 25  # Largest class multiplier bounds all three.
        a_bound = math.ceil(Fraction((ALPHA_NUM+ALPHA2_NUM+2)*radius, SCALE)
                            + Fraction(ell*(2*thi+1), 2))
        norm_bound = a_bound**3+(114+12996)*radius**3+342*a_bound*radius**2
        rounding_bound = 2*((ALPHA_NUM+ALPHA2_NUM)*radius+(ell-1)*SCALE)+ell*SCALE
        C_bound = radius**2+a_bound*radius
        B_bound = 114*radius**2+a_bound*radius
        delta_norm_bound = ell*(3*a_bound*a_bound+3*ell*a_bound+ell**2+342*radius**2)
        values = dict(a_abs_upper=a_bound, norm_absolute_terms_upper=norm_bound,
                      rounding_numerator_abs_upper=rounding_bound,
                      adjoint_C_abs_upper=C_bound, adjoint_B_abs_upper=B_bound,
                      derivative_radicand_abs_upper=114*radius**2,
                      norm_first_difference_abs_upper=delta_norm_bound,
                      row_count=(2*radius+1)**2,
                      coefficient_count=(2*radius+1)**2*(thi-tlo+1))
        _check(max(norm_bound, rounding_bound, B_bound, C_bound, delta_norm_bound) < int128_max,
               'signed128 formula bound failed')
        _check(114*radius**2 < int64_max, 'integer square-root input exceeds signed64')
        _check(values['coefficient_count'] <= uint64_max, 'index count exceeds uint64')
        arithmetic.append(dict(radius=radius, **values))
    _check(8*D0 < int64_max, 'D exceeds signed64')
    _check((8*D0)**2 < int128_max, 'modular product exceeds128')
    _check(4096*8*D0 < int128_max, 'z exceeds128')
    _check((4096*8*D0)**3 > int128_max, 'arbitrary-precision requirement sanity check')
    _check(all(SHELLS[i][1] == SHELLS[i+1][0] for i in range(2)), 'shell endpoints')
    _check(all(BANDS[i][1] == BANDS[i+1][0] for i in range(2)), 'ratio endpoints')
    return dict(D0=D0, beta_lower=BETA_LOWER, shapes=shapes, separation=separation,
                arithmetic=arithmetic, maximum_D=8*D0, maximum_abs_z=4096*8*D0)


GP_CERTIFICATE = '''K=bnfinit(t^3-114,1); if(bnfcertify(K)!=1,error("field certification failed")); if(K.zk!=[1,t,t^2],error("basis mismatch")); if(K.cyc!=[3],error("class group mismatch")); J=idealhnf(K,5,t-4); if(bnfisprincipal(K,J,0)[1]%3==0,error("J is principal")); if(idealpow(K,J,2)!=idealhnf(K,25,t-4),error("J squared mismatch")); beta=Mod(4133238949+852423792*t+175800705*t^2,t^3-114); U=bnfisunit(K,beta); if(abs(U[1])!=1 || K.tu[1]!=2,error("unit group mismatch")); if(nfeltnorm(K,beta)!=1,error("unit norm mismatch")); print("FIELD_CERTIFIED=1"); print("CLASS_GROUP=",K.cyc); print("BETA_UNIT_EXPONENTS=",U); print("ROOTS_OF_UNITY=",K.tu[1]); print("NORM_BETA=",nfeltnorm(K,beta)); quit;
'''


def field_certificate():
    gp_path = LAB/'bin/gp'
    result = subprocess.run([str(gp_path), '-q', '-f'], input=GP_CERTIFICATE,
                            text=True, capture_output=True, timeout=5)
    _check(result.returncode == 0 and not result.stderr.strip(), result.stderr)
    _check('FIELD_CERTIFIED=1' in result.stdout and 'NORM_BETA=1' in result.stdout,
           'field certificate markers missing')
    return dict(program=GP_CERTIFICATE, stdout=result.stdout,
                gp_sha256=hashlib.sha256(gp_path.read_bytes()).hexdigest())


def guard_mutations():
    import copy
    fixture = example_contexts()
    validate_contexts(fixture)
    changes = {
        'unproved_radius': lambda s: s[0].update(radius=s[0]['radius']+1),
        'unproved_offset': lambda s: s[0].update(tlo=s[0]['tlo']-1),
        'changed_shell': lambda s: s[0].update(dlo=s[0]['dlo']-1),
        'changed_ratio': lambda s: s[0].update(low=s[0]['low']+1),
        'boolean_integer': lambda s: s[0].update(ell=True),
        'duplicate_geometry': lambda s: s.__setitem__(1, dict(s[0], key='different-key')),
        'duplicate_key': lambda s: s[1].update(key=s[0]['key']),
        'wrong_family': lambda s: s[0].update(family='plane'),
        'wrong_row_total': lambda s: s[0].update(total=s[0]['total']+1),
        'infinite_weight': lambda s: s[0].update(weight=float('inf')),
        'nan_weight': lambda s: s[0].update(weight=float('nan')),
        'boolean_weight': lambda s: s[0].update(weight=True),
        'zero_weight': lambda s: s[0].update(weight=0),
        'missing_context': lambda s: s.pop(),
    }
    for name, change in changes.items():
        candidate = copy.deepcopy(fixture)
        change(candidate)
        try:
            validate_contexts(candidate)
        except ValueError:
            continue
        raise AssertionError(f'geometry guard accepted mutation: {name}')
    return list(changes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, help='JSON context list or object with contexts')
    parser.add_argument('--output', type=Path, default=ROOT/'runs/domain-certificate.json')
    args = parser.parse_args()
    wall_start = time.monotonic()
    self_start = time.process_time()
    child_start = resource.getrusage(resource.RUSAGE_CHILDREN)
    if args.config:
        config_bytes = args.config.read_bytes()
        config = json.loads(config_bytes)
        specs = config['contexts'] if isinstance(config, dict) else config
        config_label = str(args.config.resolve())
        config_hash = hashlib.sha256(config_bytes).hexdigest()
    else:
        specs = example_contexts()
        config_label = 'fixed proof geometry fixture; production config not supplied'
        config_hash = None
    validate_contexts(specs)
    evidence = dict(passed=True, scope='Exact fixed-domain prerequisites; no ledger or native implementation audit.',
                    geometry_context_count=len(specs), config_checked=config_label,
                    config_sha256=config_hash, guard_rejected_mutations=guard_mutations(),
                    symbolic_polynomial_identities=polynomial_certificate(),
                    geometry=geometry_certificate(), field_certificate=field_certificate())
    phase1_certificate = LAB/'runs/nonoverlap-certificate.json'
    if phase1_certificate.exists():
        old = json.loads(phase1_certificate.read_text())
        _check(old.get('passed') is True, 'phase1 certificate not passing')
        for name, expected in old['sources'].items():
            _check(hashlib.sha256((LAB/name).read_bytes()).hexdigest() == expected,
                   f'phase1 certified source changed: {name}')
        evidence['phase1_certificate_sha256'] = hashlib.sha256(phase1_certificate.read_bytes()).hexdigest()
        evidence['phase1_sources_match_certificate'] = True
    else:
        raise FileNotFoundError('completed phase1 nonoverlap certificate is required')
    snapshots = [p for p in ROOT.iterdir() if p.is_file() and p.suffix in ('.py', '.c', '.md')]
    snapshots += [p for p in (ROOT/'bin').glob('*') if p.is_file()]
    evidence['source_snapshot'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in sorted(snapshots)}
    child_end = resource.getrusage(resource.RUSAGE_CHILDREN)
    evidence['cpu_seconds'] = (time.process_time()-self_start + child_end.ru_utime-child_start.ru_utime
                               + child_end.ru_stime-child_start.ru_stime)
    evidence['elapsed_seconds'] = time.monotonic()-wall_start
    _check(evidence['cpu_seconds'] < 5, 'certificate exceeded bounded CPU budget')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2)+'\n')
    print(json.dumps(dict(passed=True, contexts=len(specs), config_checked=config_label,
                         guard_mutations_rejected=len(evidence['guard_rejected_mutations']),
                         cpu_seconds=evidence['cpu_seconds'], elapsed_seconds=evidence['elapsed_seconds'],
                         evidence=str(args.output)), indent=2))


if __name__ == '__main__':
    main()
