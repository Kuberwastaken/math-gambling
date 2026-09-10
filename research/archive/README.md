**Running now:** phase3 resumed on9 September2026 with12 local workers and active follow-up. Recent actual-workload replay improved1.578×; all89,685 prior phase2 tiles were preserved. [Current campaign](phase3/CURRENT_CAMPAIGN.md) · [Validation and implementation](phase3/README.md).

The reports below describe earlier checkpoints and prototypes. Their stop/pause statements are historical.

# A selective search for 114 on this Mac

**Historical phase1 checkpoint,9September2026 (India):** the bounded two-hour run finished with **no solution**, after80.86billion curve-interval checks and32.65million exact final tests. All76,714 tiles completed and the ledger audit passed. Compute has stopped; monitoring is paused. See [the final report](campaign_report.md), [current artifacts](CURRENT_CAMPAIGN.md), and [operational controls](CAMPAIGN_RUNBOOK.md). The prototype sections below are historical results, separate from the completed campaign.

The current implementation adds deterministic input tiles, restart recovery, a cancellation-plane generator, modulo-243 and parity wheels, adaptive sieve ordering, online selection between equivalent execution policies, and strict worker-output verification. The learning optimizes execution cost; it has not demonstrated increased solution density. A blind held-out experiment found too few successes to support a trained discovery policy; see [BLIND_BENCHMARK.md](BLIND_BENCHMARK.md).

**Verdict, 8 September 2026:** this is a working, tested local search experiment. It has not found a solution to `x³+y³+z³=114`, and there is no demonstrated improvement in discovery probability per unit of work over the published search. The progress is a concrete specialization of the norm method to 114, an efficient native checker, and reproducible experiments. It is not a mathematical breakthrough.

The latest [Epoch problem listing](https://epoch.ai/frontiermath/open-problems/sum-of-three-cubes) still describes 114 as unsolved. The most useful alternative I found to extending the large distributed search is the number-field approach of [Grantham–Walsh](https://arxiv.org/abs/2211.12149). Their paper also explicitly reports an unsuccessful effort on 114. This implementation develops that approach; it does not claim to invent it.

## Historical prototype runs

All runs below used this Apple Silicon Mac, two worker processes, base coefficient radius 50,000 and ratio `|z|/d ≤ 64`. They excluded the regions reported in the literature. Counts are curve checks, **not globally distinct curves**, and cannot be added to an exhaustive height bound.

| Implementation | Coefficient samples | Curve checks | Approximate elapsed time | Solutions of 114 |
|---|---:|---:|---:|---:|
| Initial PARI/GP prototype | 22,200,000 | 6,079,209 | 2 minutes | 0 |
| Native C, original sampler | 588,000,000 | 160,573,749 | 1 minute | 0 |
| Native C, sampler with balanced multiplier buckets | 574,000,000 | 145,212,303 | 1 minute | 0 |

The revised sampler produced 48,401,357, 48,407,695 and 48,403,251 curve checks in the multiplier-1, multiplier-5 and multiplier-25 buckets. It sent 45,893 surviving `(d,z)` candidates to arbitrary-precision square tests. No integer overflow exclusions occurred in either native pilot.

The two native pilots together performed **305,786,052 checks**, with possible overlap. The native original sampler was about 53 times faster per check than the GP prototype when measured by summed worker elapsed time. This comparison includes different random generators and is approximate. It is **not** a comparison with Booker–Sutherland's optimized reference program. The revised sampler trades some throughput for comparable search depths across its three buckets.

Exact records are in [runs/summary.json](runs/summary.json) and the individual JSONL ledgers. The `exact_tests: null` field for the GP run means uninstrumented, not zero.

## The reduction, and the specialization to 114

Let `α³=114`, `γ=a+bα+cα²`, and write

```
N = a³ + 114b³ + 12996c³ − 342abc
B = 114c² − ab
C = b² − ac.
```

For a multiplier `ℓ`, take `D=|N|/ℓ` when integral. If `gcd(C,D)=1`, then

```
r = B / C mod D
r³ = 114 mod D.
```

The exact identity `B³−114C³ = N(114c³−b³)` proves the root condition. This generates admissible arithmetic progressions without factoring a large `D`.

I computed and certified the arithmetic of `K=Q(∛114)` with PARI 2.17.4:

- Integral basis `[1,α,α²]`, discriminant `−350892`.
- Class group cyclic of order 3; `bnfcertify` returned 1.
- Generator `J=(5,α−4)` of norm 5, with `J²=(25,α−4)`.

Consequently every ideal class can be cleared using one of `1,J,J²`; its principal multiple has norm multiplied by `1,5,25`. This part is a certified computation for this field, rather than a guess about finding a small class-clearing prime. It does **not** certify that the finite coefficient sampler reaches every ideal or that the `gcd(C,D)=1` filter covers every case.

The improved sampler picks `j=0,1,2` in turn, sets `ℓ=5^j`, and constructs

```
a + 4b + 16c ≡ 0 mod ℓ.
```

Thus `γ` lies directly in `J^j`; the required divisibility of its norm is automatic. Each coefficient bound is scaled by `ℓ^(1/3)` so that `|N|/ℓ` has a comparable range across buckets. Reusing the same unscaled coefficient box would substantially suppress the deeper nonprincipal cases. With the default base radius, the three actual radii are approximately 50,000, 85,499 and 146,201.

For the final check, put `S=x+y`, `D=|S|` and `z=r+Dq`. For 114, all three coordinates are 2 modulo 3, so the residue of `D` determines the sign of `S`. Then

```
(x−y)² = [4(114−z³)−S³] / (3S).
```

The native checker rejects impossible candidates modulo 27, by parity, and by quadratic-residue tests at fifteen auxiliary primes. Survivors undergo exact divisibility and square tests in PARI, coordinate reconstruction, the minimum-coordinate check, and an exact cube identity. Python independently verifies any reported hit. Only necessary modular conditions are used.

## Coverage and the remaining obstacle

[Booker–Sutherland, §5.2](https://arxiv.org/abs/2007.01209) reports a 2019 search with minimum coordinate at most `10^17` and a subsequent search using `zmax=10^19`, `dmax=10^19/54`. The latter is not an exhaustive minimum-coordinate search through `10^19`. The paper describes the collective run; I have not independently obtained a completed work-unit manifest for 114.

The code excludes:

```
|z| ≤ 10^17
or (D ≤ floor(10^19/54) and |z| ≤ 10^19).
```

It then checks only selected progressions with `|z|≤64D`. Calling these checks “outside reported coverage” is justified; calling the whole frontier exhausted is not. For the default coefficient boxes, a conservative triangle-inequality bound gives `D<1.69×10^18`; most possible progressions in that range are never visited. Native `curve` mode assumes the large-solution sign arrangement and is not intended to enumerate all exceptional small positive solutions.

There is another substantial bias: sampling coefficients is not sampling ideals uniformly. The field regulator is about **23.24094**, and the fundamental unit's real embedding has absolute value about `8.0647×10^-11`. Unit multiples can therefore give extremely different coefficient sizes for the same ideal. A small symmetric box selects a narrow part of the possible shapes.

A reproducible diagnostic, `unit_audit.gp`, examined all 336 admissible `(D,r)` pairs with `2≤D≤1000`, `3∤D`. After clearing the class, it inspected five unit multiples near a balanced real embedding. The median best coefficient height divided by `|N|^(1/3)` was about 17.1; the 90th percentile was about 376.6. These are diagnostic window results, not certified globally minimal heights. They show why comparable multiplier buckets alone do not establish representative sampling.

For scale, the published progression density for 114 is about 0.346. It predicts roughly `6.4×10^16` admissible progressions up to the old `dmax` alone. Hundreds of millions of selective checks remain tiny beside this. I have no calibrated success probability for this sampler, and the zero result is not evidence that 114 lacks a solution.

## What would justify a larger Mac campaign

The useful research question is now specific: **do ideals with unusually small norm generators contain solutions disproportionately often?** Grantham–Walsh motivates investigating that possibility, but examples of small generators for already-known solutions do not establish predictive enrichment.

A credible next experiment should hold out known solutions, generate candidates without consulting their `(D,r)`, and compare recoveries per second against an optimized baseline at matched bounds. It should also measure duplicate ideals and coverage across unit shapes. Choosing bounds after examining the target solution would invalidate that comparison. The large solution for 3 is useful for checker validation but particularly easy to overfit.

If enrichment survives that test, use the measured distribution to allocate a bounded local search across coefficient shapes, ideal classes and `|z|/D` ranges. If it does not, investigate enumeration of reduced ideal representatives and stronger bulk sieving before committing days of compute. Neither a GPU port nor merely running this sampler longer establishes the missing mathematical advantage.

My recommendation is to use this package as a low-cost research instrument. A realistic Mac-only implementation now exists; a realistic high-probability route to solving 114 has not been established.

## Historical prototype commands

From this directory:

```sh
python3 validate.py
python3 search.py --minutes 2 --workers 2
```

The default resumes `runs/class-pilot.jsonl`, verifies that the configuration matches, and appends new batch indices. It stops scheduling after two minutes; in-flight batches finish or reach the per-batch timeout. With default parameters batches take a fraction of a second. To keep the archived pilot unchanged:

```sh
python3 search.py --minutes 2 --workers 2 --ledger runs/my-search.jsonl
```

Use the same command to resume. A changed radius, ratio, sampler, batch size, seed or mathematical source requires a different ledger. Do not run two writers against the same ledger. These commands concern the archived prototype. The current campaign has a bounded background process and a scheduled follow-up; use the current runbook for its controls.

A larger tail ratio is supported, but native checking is linear in the number of quotient values. The GP alternative uses `hyperellratpoints` and may become preferable for large ratios; benchmark before scaling it:

```sh
python3 search.py --engine gp --batch-size 1000 --ratio 4096 --minutes 1 --ledger runs/gp-tail.jsonl
```

This is a proposed command, not a completed search. The GP engine uses the original norm-cube sampler. Native bounds are base radius at most 80,000 and ratio at most 1,000,000; large coordinates in final checks use arbitrary precision. The native generator explicitly rejects `D>2^63−1` and reports that count.

## Validation and source

`validate.py` completed in about seven seconds:

- Native and GP result sets agreed on **662 supplied curves across 165 values of k**, including the large published solution of 3. This is recovery with known curves, not blind discovery.
- A blind coefficient search for 6 recovered `(-637,-205,644)` and `(-58,-43,65)` without supplying their curves.
- All 336 admissible small `(D,r)` pairs for 114 were recovered after ideal-class clearing: 122, 110 and 104 in the three class-clearing cases, with zero failures.
- Field certification, ideal lattice identities and endpoint/exclusion tests passed.

Undefined-behavior sanitizer runs also passed on 100,000 samples at base radius 80,000 and on the large known curve for 3. A two-stage resume test produced distinct batch indices 0–3. These checks support the implementation; they are not a formal completeness proof.

The package includes the native C source, GP reference, Python runner, validation cases, logs, Apple Silicon binaries and the complete PARI 2.17.4 source archive. `python3 build.py` reproduces the local build offline with Apple's command-line developer tools, using a `work/pari-rebuild` directory outside this deliverable. The build recipe follows the commands used for the bundled binaries; the separate rebuild script itself has not been run from a clean directory. PARI archive SHA-256: `02651d99c391007d384b3fadbc20abc6916b77036f9e496c99e9ce8688ca4b53`. See `NOTICE.md` and `LICENSE`.
