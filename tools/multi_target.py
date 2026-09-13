#!/usr/bin/env python3
"""Sound multi-target generator: the 114 norm search generalized to any
admissible k, reusing the battle-tested search_core scan/exact-check unchanged.

Safe-by-construction for new targets:
  * class multiplier fixed to ell=1 (the ell in {5,25} lattice construction is
    k-specific; ell=1 needs no class analysis),
  * the k-specific signed-coordinate exclusions (s mod 8, s mod 361 for 114) are
    DROPPED. Those are necessary-condition prunes, so dropping them only costs
    extra exact tests and NEVER removes a real solution.

This module never mutates search_core.run_task or the 114 campaign. It is a
parallel path for the 40% cross-target allocation.
"""
from __future__ import annotations
import functools

import search_core as sc

SCALE = sc.SCALE  # 10**18


def admissible(k):
    return isinstance(k, int) and 3 <= k <= 1000 and k % 9 in (3, 6)


def icbrt(n):
    """Exact floor cube root of a nonnegative integer."""
    if n < 0:
        raise ValueError("icbrt of negative")
    if n == 0:
        return 0
    x = int(round(n ** (1 / 3)))
    while x * x * x > n:
        x -= 1
    while (x + 1) ** 3 <= n:
        x += 1
    return x


@functools.lru_cache(maxsize=64)
def roots(k):
    """(floor(k^(1/3)*SCALE), floor(k^(2/3)*SCALE)) — the offset constants,
    generalizing search_core's hardcoded ALPHA/ALPHA2 for 114."""
    return icbrt(k * SCALE ** 3), icbrt(k * k * SCALE ** 3)


def offset_base(k, b, c):
    """ell=1 real-embedding offset: a that minimizes |a + b*k^{1/3} + c*k^{2/3}|.
    Identical to search_core.offset_base(1, b, c) when k == 114."""
    alpha, alpha2 = roots(k)
    numerator = -alpha * b - alpha2 * c
    return (2 * numerator + SCALE) // (2 * SCALE)


def run_target(k, context, row, block=0, *, on_hit=None):
    """Generalized run_task for target k over an ell=1 context. Returns
    {counters, hits}. Reuses sc.scan_curve (already k-general and tested)."""
    if not admissible(k):
        raise ValueError("target must be 3..1000 and 3 or 6 mod 9")
    c = sc.CONTEXT_BY_ID[context]
    if c["ell"] != 1:
        raise ValueError("safe multi-target path is restricted to ell=1 contexts")
    radius = c["radius"]
    width = 2 * radius + 1
    tlo = c["tlo"] + sc.BLOCK_SIZE * block
    thi = min(tlo + sc.BLOCK_SIZE - 1, c["thi"])
    dlo, dhi = int(c["dlo"]), int(c["dhi"])
    sign_residue = 2 * (k // 3 % 3) % 3
    counters, hits = sc.empty_counters(), []
    start = int(row)
    for r_index in range(start, min(start + sc.ROWS_PER_TASK, int(c["totalRows"]))):
        b, cc = r_index % width - radius, r_index // width - radius
        base = offset_base(k, b, cc)
        constant, linear = k * b * b * b + k * k * cc * cc * cc, 3 * k * b * cc
        first, last = sc._shell_interval(base, 1, tlo, thi, dlo, dhi, constant, linear)
        counters["generators"] += thi - tlo + 1
        counters["outside_shell"] += (thi - tlo + 1) - max(0, last - first + 1)
        for t in range(first, last + 1):
            a = base + t
            d = a * a * a - linear * a + constant
            if not dlo < d <= dhi:
                counters["outside_shell"] += 1
                continue
            if d < 2 or d % 3 == 0:
                counters["invalid_d"] += 1
                continue
            s = d if d % 3 == sign_residue else -d
            # NOTE: k-specific signed exclusions intentionally dropped (sound).
            B, C = k * cc * cc - a * b, b * b - a * cc
            if sc.math.gcd(C, d) != 1:
                counters["noninvertible"] += 1
                continue
            r = B * pow(C, -1, d) % d
            if pow(r, 3, d) != k % d:
                raise ArithmeticError("norm modular root identity failed")
            zmin = max(10 ** 17, c["low"] * d)
            zmax = c["high"] * d
            if s < 0:
                qlo, qhi = (zmin - r) // d + 1, (zmax - r) // d
            else:
                qlo, qhi = -((zmax + r) // d), -((zmin + r) // d) - 1
            found = sc.scan_curve(k, d, r, qlo, qhi, on_hit=on_hit)
            for key, value in found["counters"].items():
                counters[key] += value
            hits.extend(found["hits"])
    # Accounting invariants (same as the 114 engine, minus the signed bucket).
    if counters["generators"] != sum(counters[x] for x in ("outside_shell", "invalid_d", "signed_excluded", "noninvertible", "curves")):
        raise ArithmeticError("generator accounting failed")
    if counters["quotient_points"] != sum(counters[x] for x in ("rejected_mod243", "rejected_parity", "rejected_prime", "exact_tests")):
        raise ArithmeticError("quotient accounting failed")
    return dict(counters=counters, hits=hits)
