#!/usr/bin/env python3
"""Adaptive allocation and bounds for the cross-target sub-campaign.

The 114 campaign keeps the majority of compute; a minority is spread across the
other open sum-of-three-cubes cases to raise the probability of closing *some*
open problem and to study the family as a whole. This module decides, from a
declared density prior updated by *measured* results (cost, curve yield, empty
fraction), how to split compute and where to tighten each target's search.

It learns COST and YIELD geometry, never "where a solution is" — zero-hit data
cannot support the latter (see docs/LEARNING.md). Every weight keeps an
exploration floor, and a low score is never a mathematical exclusion. Pure and
deterministic; it holds no live state.
"""
from __future__ import annotations

# Heath-Brown relative density priors. Only 114 and 627 have published/derived
# values we rely on (research/.../SEARCH_VERDICT.md, Booker-Sutherland); the rest
# start neutral and are corrected by observation. These are priors, not truth.
DENSITY_PRIOR = {114: 0.0585, 627: 0.13}
NEUTRAL_PRIOR = 0.08  # placeholder for open cases without a relied-upon density

# The open cases below 1000 this sub-campaign may cover (all == +-3 mod 9).
OPEN_TARGETS = (114, 390, 627, 633, 732, 921, 975)
PRIMARY = 114
PRIMARY_SHARE = 0.60           # 114 stays the hook and the majority of compute
EXPLORE_FLOOR = 0.40           # fraction of each layer's weight kept uniform


def admissible(k):
    return isinstance(k, int) and 3 <= k <= 1000 and k % 9 in (3, 6)


def _prior(k):
    return DENSITY_PRIOR.get(k, NEUTRAL_PRIOR)


def _blend(scores, floor):
    """Mix an exploitation distribution with a uniform floor. `scores` are
    nonnegative; result is a probability vector, never zeroing any key."""
    keys = list(scores)
    n = len(keys)
    if n == 0:
        return {}
    total = sum(max(0.0, scores[k]) for k in keys)
    uniform = 1.0 / n
    out = {}
    for k in keys:
        exploit = (max(0.0, scores[k]) / total) if total > 0 else uniform
        out[k] = floor * uniform + (1 - floor) * exploit
    # Renormalize against floating error.
    s = sum(out.values())
    return {k: v / s for k, v in out.items()}


def campaign_split(targets=OPEN_TARGETS, *, observations=None, explore=EXPLORE_FLOOR):
    """Whole-campaign weights: PRIMARY_SHARE to 114, the rest across the others.

    `observations` (optional) maps target -> {'curves','cpu_ms',...}; when present,
    the cross-target slice is reweighted by measured curve-yield-per-CPU blended
    with the density prior. Returns a probability vector over all targets summing
    to 1, with 114 == PRIMARY_SHARE exactly.
    """
    others = [k for k in targets if k != PRIMARY and admissible(k)]
    if not others:
        return {PRIMARY: 1.0}
    scores = {}
    for k in others:
        prior = _prior(k)
        if observations and k in observations and observations[k].get("cpu_ms", 0) > 0:
            obs = observations[k]
            yield_per_cpu = obs.get("curves", 0) / obs["cpu_ms"]
            # Geometric blend of prior and measured yield keeps both honest.
            scores[k] = (prior * (1.0 + yield_per_cpu)) ** 0.5 if yield_per_cpu > 0 else prior
        else:
            scores[k] = prior
    within = _blend(scores, explore)
    split = {PRIMARY: PRIMARY_SHARE}
    for k, w in within.items():
        split[k] = (1 - PRIMARY_SHARE) * w
    return split


def context_bounds(observations, *, explore=EXPLORE_FLOOR):
    """Per-context weights for one target from measured stats.

    `observations` maps context id -> {'curves','cpu_ms','empty_tasks','tasks'}.
    Down-weights contexts that cost more per emitted curve and those that keep
    coming back empty, but never below the exploration floor (a low score is a
    preference, never a proof of emptiness). Unobserved contexts default to the
    floor so they are still visited.
    """
    scores = {}
    for ctx, o in observations.items():
        cpu = max(o.get("cpu_ms", 0.0), 1e-9)
        curves = o.get("curves", 0)
        tasks = max(o.get("tasks", 0), 1)
        empty_frac = o.get("empty_tasks", 0) / tasks
        # yield per cpu, damped by how often the context is entirely empty.
        scores[ctx] = (curves / cpu) * (1.0 - min(empty_frac, 0.99))
    return _blend(scores, explore)


def refine_from_wrong_cases(observations, *, min_samples=64):
    """Turn accumulated results into tighter bounds as data (and 'wrong cases' —
    empties, non-invertible generators, out-of-shell misses) arrive.

    Returns per-context {'weight','provably_empty_fraction','samples','confident'}.
    'confident' gates whether a down-weight is trusted yet (>= min_samples), so a
    small noisy sample never prematurely starves a context. Nothing here excludes
    a context; exact emptiness is only ever certified by search_core.prove_empty_task.
    """
    weights = context_bounds(observations)
    out = {}
    for ctx, o in observations.items():
        tasks = max(o.get("tasks", 0), 1)
        out[ctx] = {
            "weight": weights[ctx],
            "provably_empty_fraction": o.get("empty_tasks", 0) / tasks,
            "samples": o.get("tasks", 0),
            "confident": o.get("tasks", 0) >= min_samples,
        }
    return out
