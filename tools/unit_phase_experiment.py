#!/usr/bin/env python3
"""Bounded, isolated positive unit-phase experiment. Never banks production tasks."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from fractions import Fraction as F
import hashlib
import json
from math import ceil, floor, gcd, isqrt
import os
from pathlib import Path
import time

from search_core import ALPHA, ALPHA2, D0, SCALE, SHAPES, scan_curve, verify_triple

ROOT = Path(__file__).resolve().parents[1]
AL, AH = F(ALPHA - 1, SCALE), F(ALPHA + 1, SCALE)
VERSION = "mg114-unit-phase-experiment-v1"


def multiply(x, y):
    """Exact multiplication in Z[alpha], alpha^3=114."""
    z = [0, 0, 0]
    for i in range(3):
        for j in range(3):
            z[(i+j) % 3] += x[i]*y[j]*(114 if i+j >= 3 else 1)
    return tuple(z)


def norm(a, b, c):
    return a**3 + 114*b**3 + 12996*c**3 - 342*a*b*c


def algebraic_sign(coefficients, low=AL, high=AH):
    """Exact sign, including equality; ambiguous bounds refine, never exclude."""
    if not low > 0 or not low**3 < 114 < high**3:
        raise ValueError("alpha interval is not an isolating interval")
    if all(v == 0 for v in coefficients):
        return 0
    # X^3-114 is irreducible over Q; a nonzero degree<=2 polynomial cannot vanish.
    for _ in range(1024):
        lower = upper = F(coefficients[0])
        for power in (1, 2):
            v = coefficients[power]
            lower += v*(low if v >= 0 else high)**power
            upper += v*(high if v >= 0 else low)**power
        if lower > 0:
            return 1
        if upper < 0:
            return -1
        middle = (low+high)/2
        if middle**3 < 114:
            low = middle
        else:
            high = middle
    raise ArithmeticError("unresolved algebraic sign; no exclusion certified")


def phase_compare(abc, boundary):
    """Sign of real(gamma)^3 - boundary*Norm(gamma)."""
    cubic = list(multiply(multiply(abc, abc), abc))
    cubic[0] -= boundary*norm(*abc)
    return algebraic_sign(cubic)


def cube_floor(n):
    if type(n) is not int or n < 0:
        raise ValueError("nonnegative integer required")
    lo, hi = 0, 1 << ((n.bit_length()+2)//3)
    while lo < hi:
        mid = (lo+hi+1)//2
        if mid**3 <= n:
            lo = mid
        else:
            hi = mid-1
    return lo


def cube_ceil(n):
    value = cube_floor(n)
    return value + (value**3 < n)


def sqrt_ceil(value):
    value = F(value)
    if value < 0:
        raise ValueError("nonnegative rational required")
    root = isqrt(value.numerator//value.denominator)
    return root + (root*root < value)


@dataclass(frozen=True)
class Cell:
    ell: int
    dlo: int
    dhi: int
    lambda_lo: int = 28
    lambda_hi: int = 1000

    def __post_init__(self):
        if (any(type(v) is not int for v in asdict(self).values())
                or self.ell not in (1, 5, 25)
                or not 0 < self.dlo < self.dhi <= 10**20
                or not 4 < self.lambda_lo < self.lambda_hi <= 10**9):
            raise ValueError("invalid bounded positive-phase cell")


class LimitReached(RuntimeError):
    pass


class Budget:
    def __init__(self, seconds=10, *, positions=150000, rows=20000,
                 curves=512, quotient_positions=32768):
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not 0 < seconds <= 30:
            raise ValueError("seconds must be in (0,30]")
        self.deadline = time.monotonic()+seconds
        self.limits = dict(positions=positions, rows=rows, curves=curves,
                           quotient_positions=quotient_positions)
        if any(type(v) is not int or v < 0 for v in self.limits.values()):
            raise ValueError("nonnegative integer work limits required")
        self.used = Counter()

    def charge(self, kind, amount=1):
        if time.monotonic() >= self.deadline:
            raise LimitReached("wall budget")
        if self.used[kind]+amount > self.limits[kind]:
            raise LimitReached(kind+" budget")
        self.used[kind] += amount


def outer_bounds(cell):
    """Rational outward Fourier bounds; no floating point membership tests."""
    nlo, nhi = cell.ell*cell.dlo, cell.ell*cell.dhi
    smin = cube_floor(nlo*cell.lambda_lo)
    smax = cube_ceil(nhi*cell.lambda_hi)
    wmax = sqrt_ceil(F(nhi, smin))
    # lambda>4 => s>2w, hence all three coefficients are strictly positive.
    maxima = tuple(ceil(F(smax+2*wmax, 3)/v) for v in (1, AL, AL*AL))
    return smin, smax, wmax, maxima


def member(abc, cell):
    a, b, c = abc
    if min(abc) <= 0 or (a+4*b+16*c) % cell.ell:
        return False
    if not cell.ell*cell.dlo < norm(*abc) <= cell.ell*cell.dhi:
        return False
    return phase_compare(abc, cell.lambda_lo) > 0 and phase_compare(abc, cell.lambda_hi) <= 0


def enumerate_cell(cell, budget):
    smin, smax, wmax, maxima = outer_bounds(cell)
    delta_bound = sqrt_ceil(F(4*wmax*wmax, 3))
    members = []
    counts = Counter()
    for c in range(1, maxima[2]+1):
        # |alpha*b-alpha^2*c|<=2w/sqrt(3); outward rounding retains all rows.
        blo = max(1, ceil((AL*AL*c-delta_bound)/AH))
        bhi = min(maxima[1], floor((AH*AH*c+delta_bound)/AL))
        budget.charge("rows")  # Charge c iteration even when the b interval is empty.
        for b in range(blo, bhi+1):
            budget.charge("rows")
            counts["rows_examined"] += 1
            delta_lo, delta_hi = AL*b-AH*AH*c, AH*b-AL*AL*c
            distance = 0 if delta_lo <= 0 <= delta_hi else min(abs(delta_lo), abs(delta_hi))
            radial = F(wmax*wmax)-F(3, 4)*distance*distance
            if radial < 0:
                continue
            rad = sqrt_ceil(radial)
            mlo, mhi = (AL*b+AL*AL*c)/2, (AH*b+AH*AH*c)/2
            alo = max(1, ceil(mlo-rad), ceil(smin-AH*b-AH*AH*c))
            ahi = min(maxima[0], floor(mhi+rad), floor(smax-AL*b-AL*AL*c))
            alo += (-4*b-16*c-alo) % cell.ell
            for a in range(alo, ahi+1, cell.ell):
                budget.charge("positions")
                counts["coefficient_positions"] += 1
                if member((a, b, c), cell):
                    members.append((a, b, c))
    return sorted(members), dict(counts)


def brute_box(cell, budget):
    """Independent enumeration order and no circle/row/class-lattice skips."""
    maxima = outer_bounds(cell)[3]
    result = []
    for a in range(1, maxima[0]+1):
        for b in range(1, maxima[1]+1):
            for c in range(1, maxima[2]+1):
                budget.charge("positions")
                if member((a, b, c), cell):
                    result.append((a, b, c))
    return sorted(result)


def extract_root(abc, cell):
    """A failed inverse is unresolved handling, not a proof of no modular root."""
    if not member(abc, cell):
        raise ValueError("generator is not a member of the stated cell")
    a, b, c = abc
    d = norm(*abc)//cell.ell
    if d < 2 or d % 3 == 0:
        return {"status": "excluded_divisor", "D": d}
    B, C = 114*c*c-a*b, b*b-a*c
    if gcd(C, d) != 1:
        return {"status": "unresolved_noninvertible", "D": d}
    r = B*pow(C, -1, d) % d
    if pow(r, 3, d) != 114 % d or (a+b*r+c*r*r) % d:
        raise ArithmeticError("exact root or generator identity failed")
    return {"status": "root", "D": d, "r": r}


def quotient_interval(d, r, high=64):
    """Signed interval 0<|z|/D<=high; small-cell regression has no frontier floor."""
    if type(high) is not int or not 1 <= high <= 4096:
        raise ValueError("bounded ratio horizon required")
    s = d if d % 3 == 1 else -d
    if s < 0:
        return s, (-r)//d+1, (high*d-r)//d
    return s, -((high*d+r)//d), -(r//d)-1


def atomic_json(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2)+"\n").encode()
    temporary = path.with_suffix(path.suffix+".tmp")
    with temporary.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def preserve_hit(folder, hit, k=114):
    if not verify_triple(hit.get("xyz"), k):
        raise ArithmeticError("unverified discovery callback")
    record = {"k": k, "hit": hit, "scope": "isolated experiment; no task completion or credit"}
    identifier = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
    path = folder/("identity-"+identifier+".json")
    if not path.exists():
        atomic_json(path, record)


def separation_certificate():
    """Recompute inequalities; field maximality/fundamental-unit facts stay conditional."""
    if not AL**3 < 114 < AH**3:
        raise ArithmeticError("invalid alpha bounds")
    # Certify BOTH constants used by the current offset engine's rounding proof.
    for value, power in ((ALPHA, 114), (ALPHA2, 114**2)):
        if not F(value-1, SCALE)**3 < power < F(value+1, SCALE)**3:
            raise ArithmeticError("current engine embedding approximation failed")
    beta = (4133238949, 852423792, 175800705)
    inverse = (61561, -13758, 219)
    if norm(*beta) != 1 or multiply(beta, inverse) != (1, 0, 0):
        raise ArithmeticError("archived unit identity failed")
    rows = []
    for ell in (1, 5, 25):
        lower = min(ell*F(2*tlo-1, 2)-F(2*radius, SCALE) for radius, tlo, _ in SHAPES)
        upper = max(ell*F(2*thi+1, 2)+F(2*radius, SCALE) for radius, _, thi in SHAPES)
        new_cube_low, new_cube_high = 28*ell*D0, 10**9*ell*8*D0
        above = new_cube_low > upper**3
        less_than_unit = new_cube_high < (beta[0]*lower)**3
        unique_period = F(new_cube_high, new_cube_low) < beta[0]**3
        if not (above and less_than_unit and unique_period):
            raise ArithmeticError("frontier separation inequality failed")
        rows.append(dict(ell=ell, current_real_lower=str(lower), current_real_upper=str(upper),
                         new_real_cube_lower=str(new_cube_low), new_real_cube_upper=str(new_cube_high),
                         strictly_above_current=True, ratio_below_beta=True, within_one_unit_period=True))
    archived = ROOT/"research/archive/phase2/runs/final-domain-certificate.json"
    return {"arithmetic_checks_passed": True, "classes": rows,
            "archive_sha256": hashlib.sha256(archived.read_bytes()).hexdigest(),
            "conditional_on": ["Archived O_K=Z[alpha] and class-group/ideal ownership facts.",
                               "Archived beta is fundamental, not merely a unit; PARI was not rerun."],
            "scope": "Proposed frontier cell D0<D<=8D0, 28<s^3/N<=10^9; not enumerated here."}


def run_experiment(output, seconds=10):
    output = Path(output)
    budget = Budget(seconds)
    output.mkdir(parents=True, exist_ok=False)
    started, cpu = time.monotonic(), time.process_time()
    cells = [Cell(ell, low, 4*low) for ell in (1, 5, 25) for low in (128, 1024)]
    manifest = {"schema": VERSION, "cells": [asdict(c) for c in cells], "seconds": seconds,
                "limits": budget.limits, "ratio_horizon": 64,
                "scope": "Small-cell end-to-end validation only; not a frontier search or production task.",
                "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "kernel_sha256": hashlib.sha256((ROOT/"tools/search_core.py").read_bytes()).hexdigest()}
    atomic_json(output/"manifest.json", manifest)
    report = {"schema": VERSION, "separation": separation_certificate(), "cells": [],
              "status": "complete", "promotion_allowed": False,
              "limitations": ["Tiny analogues are not new frontier coverage or a discovery benchmark.",
                              "Shared exact checker verifies candidates; no independent whole-kernel proof.",
                              "Root recovery is selective; noninvertible cases remain unresolved.",
                              "No native overflow certificate, full-height throughput or discovery enrichment established."]}
    seen = set()
    try:
        for cell in cells:
            members, counts = enumerate_cell(cell, budget)
            oracle = brute_box(cell, budget)
            if members != oracle:
                raise ArithmeticError("tube differs from exhaustive positive box")
            roots, counters, scans = Counter(), Counter(), []
            for abc in members:
                root = extract_root(abc, cell)
                roots[root["status"]] += 1
                if root["status"] != "root":
                    continue
                d, r = root["D"], root["r"]
                if (d, r) in seen:
                    roots["duplicate_root_skipped"] += 1
                    continue
                s, lo, hi = quotient_interval(d, r)
                budget.charge("curves")
                budget.charge("quotient_positions", hi-lo+1)
                def rescue(hit):
                    enriched = {**hit, "abc": list(abc), "cell": asdict(cell)}
                    preserve_hit(output, enriched)
                    raise LimitReached("exact identity preserved; stop scheduling")
                result = scan_curve(114, d, r, lo, hi, on_hit=rescue)
                seen.add((d, r))
                counters.update(result["counters"])
                scans.append(dict(abc=list(abc), D=str(d), r=str(r), s=str(s), qlo=lo, qhi=hi))
            canonical_members = json.dumps(members, separators=(",", ":")).encode()
            report["cells"].append({"cell": asdict(cell), "bounds": list(outer_bounds(cell)[3]),
                                    "complete_box_equality": True, "members": len(members),
                                    "member_sha256": hashlib.sha256(canonical_members).hexdigest(),
                                    "enumeration": counts, "root_classification": dict(roots),
                                    "scan_counters": dict(counters), "completed_scans": scans})
    except LimitReached as exc:
        report["status"], report["stop_reason"] = "partial", str(exc)
    except BaseException as exc:
        report["status"], report["stop_reason"] = "failed", str(exc)
        raise
    finally:
        report["work_used"] = dict(budget.used)
        report["elapsed_seconds"] = time.monotonic()-started
        report["cpu_seconds"] = time.process_time()-cpu
        atomic_json(output/"results.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New directory; existing evidence is never overwritten")
    parser.add_argument("--seconds", type=float, default=10)
    args = parser.parse_args()
    result = run_experiment(args.output, args.seconds)
    print(json.dumps({"status": result["status"], "cells": len(result["cells"]), "work": result["work_used"]}))
    raise SystemExit(0 if result["status"] == "complete" else 2)
