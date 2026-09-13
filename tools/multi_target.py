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
import hashlib
import re

import search_core as sc

SCALE = sc.SCALE  # 10**18

# Target tasks live in their own engine namespace, "mg{k}-offset-v1", so their
# task IDs, receipts and coverage never collide with the 114 campaign's
# "mg114-offset-v1". The 114 engine and its pipeline are never touched.
ENGINE_RE = re.compile(r"mg([1-9][0-9]{0,3})-offset-v1")
ELL1_CONTEXTS = tuple(c["id"] for c in sc.CONTEXTS if c["ell"] == 1)


def target_engine(k):
    return f"mg{k}-offset-v1"


def parse_engine(engine):
    """Return the target k for a 'mg{k}-offset-v1' tag, or None.

    114 is excluded on purpose: it is the primary campaign's own engine
    (search_core.ENGINE == 'mg114-offset-v1'), so the target namespace must never
    reuse it or their task IDs, receipts and coverage would collide."""
    m = ENGINE_RE.fullmatch(engine) if isinstance(engine, str) else None
    if not m:
        return None
    k = int(m.group(1))
    return k if admissible(k) and k != 114 else None


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


def prove_empty_target(task):
    """k-general scan-free emptiness proof (the target analogue of
    search_core.prove_empty_task). True iff every generator lies outside the
    shell for THIS target's norm — conservative, so a True can never skip a task
    that would produce a curve for k. Uses k's constants, never 114's."""
    task = validate_target_task(task)
    k = parse_engine(task["engine"])
    c = sc.CONTEXT_BY_ID[task["context"]]
    radius = c["radius"]
    width = 2 * radius + 1
    tlo = c["tlo"] + sc.BLOCK_SIZE * task["block"]
    thi = min(tlo + sc.BLOCK_SIZE - 1, c["thi"])
    dlo, dhi = int(c["dlo"]), int(c["dhi"])
    start = int(task["row"])
    for row in range(start, min(start + sc.ROWS_PER_TASK, int(c["totalRows"]))):
        b, cc = row % width - radius, row // width - radius
        base = offset_base(k, b, cc)
        constant, linear = k * b * b * b + k * k * cc * cc * cc, 3 * k * b * cc
        first, last = sc._shell_interval(base, 1, tlo, thi, dlo, dhi, constant, linear)
        if last >= first:
            return False
    return True


def validate_target_task(task):
    """Canonical target task: {version, engine 'mg{k}-...', context (ell=1), row, block}."""
    if not isinstance(task, dict) or set(task) != {"version", "engine", "context", "row", "block"}:
        raise ValueError("target task has unexpected or missing fields")
    if type(task["version"]) is not int or task["version"] != 1:
        raise ValueError("unsupported version")
    k = parse_engine(task["engine"])
    if k is None:
        raise ValueError("unknown or inadmissible target engine")
    if task["context"] not in ELL1_CONTEXTS:
        raise ValueError("target tasks use ell=1 contexts only")
    c = sc.CONTEXT_BY_ID[task["context"]]
    if type(task["row"]) is not str or not re.fullmatch(r"0|[1-9][0-9]{0,14}", task["row"]):
        raise ValueError("row must be a canonical bounded decimal string")
    if int(task["row"]) >= int(c["totalRows"]) or int(task["row"]) % sc.ROWS_PER_TASK:
        raise ValueError("row outside context or not aligned")
    if type(task["block"]) is not int or not 0 <= task["block"] < c["blocks"]:
        raise ValueError("block outside context")
    return dict(version=1, engine=task["engine"], context=task["context"], row=task["row"], block=task["block"])


def make_target_task(k, context, row, block=0):
    return validate_target_task(dict(version=1, engine=target_engine(k), context=context, row=str(row), block=block))


def target_task_id(task):
    t = validate_target_task(task)
    return f"{t['engine']}:{t['context']}:{t['row']}:{t['block']}"


def run_target_task(task, on_hit=None):
    """Full verifiable result for a target task: reuses run_target, adds the
    canonical id + sha256 digest exactly like search_core.run_task."""
    task = validate_target_task(task)
    k = parse_engine(task["engine"])
    found = run_target(k, task["context"], int(task["row"]), task["block"], on_hit=on_hit)
    result = dict(task=task, id=target_task_id(task), counters=found["counters"], hits=found["hits"])
    result["digest"] = hashlib.sha256(sc.canonical_json(result).encode("ascii")).hexdigest()
    return result


if __name__ == "__main__":
    # Isolated replay entry for the target verifier: data-only stdin, no submitted
    # code is ever imported or executed.
    import json
    import sys
    import time
    if sys.platform != "win32":
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (4, 5))
    task = validate_target_task(json.loads(sys.stdin.read(2049)))
    started = time.process_time()
    result = run_target_task(task)
    print(sc.canonical_json({"result": result, "cpu_ms": (time.process_time() - started) * 1000}))
