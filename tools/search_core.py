"""Portable exact, bounded math-gambling kernel. No I/O on import.

This is a selective search, not an exhaustive height-box search. Receipt replay
establishes a bounded task's result, not that its submitter performed the work.
"""
from __future__ import annotations

import functools
import hashlib
import json
import math
import re

ENGINE = "mg114-offset-v1"
MAX_TASKS_PER_RECEIPT = 8
BLOCK_SIZE = 16
ROWS_PER_TASK = 128
SCALE = 10**18
ALPHA = 4848807585839879338
ALPHA2 = 23510935004498358840
D0 = 10**19 // 54
PRIMES = (5, 7, 11, 13, 17, 19, 23, 31, 37, 41, 43, 47, 53, 59, 61)
SHAPES = ((6_000_000, 8, 31), (1_500_000, 128, 511), (375_000, 2048, 8191))
BANDS = ((0, 64), (64, 256), (256, 4096))
CONTEXTS = []
for ell in (1, 5, 25):
    for shape, (radius, tlo, thi) in enumerate(SHAPES):
        for shell in range(3):
            for band, (low, high) in enumerate(BANDS):
                CONTEXTS.append(dict(id=f"c{len(CONTEXTS):02d}", ell=ell,
                    shape=shape, shell=shell, band=band, radius=radius,
                    tlo=tlo, thi=thi, dlo=str(D0 * 2**shell),
                    dhi=str(D0 * 2**(shell+1)), low=low, high=high,
                    totalRows=str((2*radius+1)**2), rowStride=ROWS_PER_TASK,
                    rowTasks=str(((2*radius+1)**2+ROWS_PER_TASK-1)//ROWS_PER_TASK),
                    blocks=(thi-tlo+BLOCK_SIZE)//BLOCK_SIZE))
CONTEXT_BY_ID = {c["id"]: c for c in CONTEXTS}


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def validate_task(task):
    if not isinstance(task, dict) or set(task) != {"version", "engine", "context", "row", "block"}:
        raise ValueError("task has unexpected or missing fields")
    if type(task["version"]) is not int or task["version"] != 1 or task["engine"] != ENGINE:
        raise ValueError("unsupported engine/version")
    if type(task["context"]) is not str or task["context"] not in CONTEXT_BY_ID:
        raise ValueError("unknown fixed context")
    c = CONTEXT_BY_ID[task["context"]]
    if type(task["row"]) is not str or not re.fullmatch(r"0|[1-9][0-9]{0,14}", task["row"]):
        raise ValueError("row must be a canonical bounded decimal string")
    if int(task["row"]) >= int(c["totalRows"]) or int(task["row"]) % ROWS_PER_TASK:
        raise ValueError("row outside context or not aligned to rowStride")
    if type(task["block"]) is not int or not 0 <= task["block"] < c["blocks"]:
        raise ValueError("block outside context")
    return dict(version=1, engine=ENGINE, context=task["context"], row=task["row"], block=task["block"])


def make_task(context, row, block=0):
    return validate_task(dict(version=1, engine=ENGINE, context=context, row=str(row), block=block))


def task_id(task):
    t = validate_task(task)
    return f"{ENGINE}:{t['context']}:{t['row']}:{t['block']}"


def verify_triple(xyz, k=114):
    if not isinstance(xyz, (list, tuple)) or len(xyz) != 3 or type(k) is not int:
        return False
    if any(type(v) is not str or not re.fullmatch(r"-?(0|[1-9][0-9]{0,127})", v) or v == "-0" for v in xyz):
        return False
    return sum(int(v)**3 for v in xyz) == k


def offset_base(ell, b, c):
    residue = (-4*b-16*c) % ell
    numerator = -ALPHA*b-ALPHA2*c-residue*SCALE
    denominator = ell*SCALE
    return residue+ell*((2*numerator+denominator)//(2*denominator))


def norm(a, b, c, k=114):
    return a*a*a+k*b*b*b+k*k*c*c*c-3*k*a*b*c


@functools.lru_cache(maxsize=32)
def _filters(k):
    cubes = [v**3 % 243 for v in range(243)]
    pairs = [bytearray(243) for _ in range(243)]
    for x in range(243):
        for y in range(243):
            pairs[(x+y) % 243][(cubes[x]+cubes[y]) % 243] = 1
    allowed = [[z for z in range(243) if pairs[s][(k-cubes[z]) % 243]] for s in range(243)]
    masks = []
    for p in PRIMES:
        qr = {v*v % p for v in range(p)}
        masks.append([sum(1 << z for z in range(p) if (3*s*(4*k-4*z**3-s**3)) % p in qr)
                      for s in range(p)])
    return allowed, masks


def empty_counters():
    return {key: 0 for key in (
        "generators", "outside_shell", "invalid_d", "signed_excluded", "noninvertible",
        "curves", "quotient_points", "rejected_mod243", "rejected_parity", "rejected_prime",
        "exact_tests", "hits")}


def check_candidate(k, s, z, *, minimal=True):
    """Independent exact final check, also usable without any modular sieve."""
    if not s:
        return None
    square, rem = divmod(4*(k-z*z*z)-s*s*s, 3*s)
    if rem or square < 0:
        return None
    v = math.isqrt(square)
    if v*v != square or (s+v) % 2:
        return None
    x, y = (s+v)//2, (s-v)//2
    if minimal and (abs(z) > abs(x) or abs(z) > abs(y)):
        return None
    xyz = [str(x), str(y), str(z)]
    if not verify_triple(xyz, k):
        raise ArithmeticError("final exact cube identity failed")
    return xyz


def scan_curve(k, d, r, qlo, qhi, *, sieve=True, minimal=True):
    """Regression API, not an accepted public task. k must be 3 or 6 modulo9."""
    if any(type(v) is not int for v in (k, d, r, qlo, qhi)) or not 3 <= k <= 1000 or k % 9 not in (3, 6):
        raise ValueError("unsupported regression curve")
    if d < 2 or d % 3 == 0 or not 0 <= r < d or pow(r, 3, d) != k % d:
        raise ValueError("invalid modular root")
    if qhi < qlo or qhi-qlo > 8192:
        raise ValueError("bounded regression interval required")
    s = d if d % 3 == 2*(k//3 % 3) % 3 else -d
    stats = empty_counters()
    stats["curves"] = 1
    stats["quotient_points"] = qhi-qlo+1
    hits = []
    allowed, masks = _filters(k)
    if sieve:
        inv = pow(d % 243, -1, 243)
        qs = []
        passed243 = 0
        for zmod in allowed[s % 243]:
            residue = ((zmod-r)*inv) % 243
            first = qlo+(residue-qlo) % 243
            if first <= qhi:
                passed243 += (qhi-first)//243+1
            qs.extend(range(first, qhi+1, 243))
        # Stable sorted order gives both languages the same hit/digest order.
        qs.sort()
        stats["rejected_mod243"] = stats["quotient_points"]-passed243
    else:
        qs = range(qlo, qhi+1)
    for q in qs:
        z = r+d*q
        if sieve and (k-s-z) % 2:
            stats["rejected_parity"] += 1
            continue
        if sieve and any(not (masks[j][s % p] >> (z % p) & 1) for j, p in enumerate(PRIMES)):
            stats["rejected_prime"] += 1
            continue
        stats["exact_tests"] += 1
        xyz = check_candidate(k, s, z, minimal=minimal)
        if xyz:
            hits.append(dict(xyz=xyz, D=str(d), r=str(r), q=str(q)))
    stats["hits"] = len(hits)
    return dict(counters=stats, hits=hits)


def _run_row(task, c, row):
    ell, radius = c["ell"], c["radius"]
    width = 2*radius+1
    b, cc = row % width-radius, row//width-radius
    base = offset_base(ell, b, cc)
    tlo = c["tlo"]+BLOCK_SIZE*task["block"]
    thi = min(tlo+BLOCK_SIZE-1, c["thi"])
    counters, hits = empty_counters(), []
    for t in range(tlo, thi+1):
        counters["generators"] += 1
        a = base+ell*t
        n = norm(a, b, cc)
        if n % ell:
            raise ArithmeticError("norm lattice divisibility failed")
        d = n//ell
        if not int(c["dlo"]) < d <= int(c["dhi"]):
            counters["outside_shell"] += 1
            continue
        if d < 2 or d % 3 == 0:
            counters["invalid_d"] += 1
            continue
        s = d if d % 3 == 1 else -d
        if s % 8 in (0, 4, 6) or s % 361 in (0, 19, 76, 95, 114, 133, 171, 209, 304, 323):
            counters["signed_excluded"] += 1
            continue
        B, C = 114*cc*cc-a*b, b*b-a*cc
        if math.gcd(C, d) != 1:
            counters["noninvertible"] += 1
            continue
        r = B*pow(C, -1, d) % d
        if pow(r, 3, d) != 114 % d:
            raise ArithmeticError("norm modular root identity failed")
        zmin = max(10**17, c["low"]*d)
        zmax = c["high"]*d
        if s < 0:
            qlo, qhi = (zmin-r)//d+1, (zmax-r)//d
        else:
            qlo, qhi = -((zmax+r)//d), -((zmin+r)//d)-1
            # ceil((-zmax-r)/d), ceil((-zmin-r)/d)-1
        found = scan_curve(114, d, r, qlo, qhi)
        for key, value in found["counters"].items():
            counters[key] += value
        for hit in found["hits"]:
            hit.update(abc=[str(a), str(b), str(cc)], t=t, row=str(row))
            hits.append(hit)
    if counters["generators"] != sum(counters[k] for k in ("outside_shell", "invalid_d", "signed_excluded", "noninvertible", "curves")):
        raise ArithmeticError("generator accounting failed")
    if counters["quotient_points"] != sum(counters[k] for k in ("rejected_mod243", "rejected_parity", "rejected_prime", "exact_tests")):
        raise ArithmeticError("quotient accounting failed")
    return counters, hits


def run_task(task):
    task = validate_task(task)
    c = CONTEXT_BY_ID[task["context"]]
    counters, hits = empty_counters(), []
    start = int(task['row'])
    for row in range(start, min(start+ROWS_PER_TASK, int(c['totalRows']))):
        row_counters, row_hits = _run_row(task, c, row)
        for key, value in row_counters.items():
            counters[key] += value
        hits.extend(row_hits)
    result = dict(task=task, id=task_id(task), counters=counters, hits=hits)
    result["digest"] = hashlib.sha256(canonical_json(result).encode("ascii")).hexdigest()
    return result
