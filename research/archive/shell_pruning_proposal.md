# Exact norm-shell enumeration: a concrete next algorithm

9 September 2026 local time. This proposal leaves the running campaign unchanged. The calculations below use integer polynomial evaluation only, with no large curve search.

**Verdict:** invert the norm polynomial once per `(b,c)` row, then enumerate only eligible `a` intervals. This is a credible improvement to the box generator and its data locality. It does not supply a new solution-density theorem, and it probably loses to direct evaluation on the current plane generator's five-point rows.

## Define exactly what gets excluded

Let

```
N(a) = a³ − 342bc·a + 114b³ + 12996c³,
ell ∈ {1,5,25},
a0 = (−4b−16c) mod ell,
a = a0 + ell·t.
```

The exact production box domain is `b,c∈[-H,H]` and `t∈[-floor(H/ell),floor(H/ell)]`. Thus the a interval is `[a0−ell·floor(H/ell), a0+ell·floor(H/ell)]`; its positive endpoint can exceed H by as much as ell−1. Do not silently replace this asymmetric interval by `|a|≤H` in a matched-domain comparison.

The lattice congruence makes `N(a)` divisible by `ell`. For a chosen pair-sum shell `[L,U]`, retain exactly

```
ell·L ≤ |N(a)| ≤ ell·U.
```

A discarded coefficient has no pair sum in this particular shell. It may yield a solution elsewhere. This is a rigorous shell exclusion, not an all-height exclusion or a prediction that excluded norms are unpromising.

A useful first experiment is

```
D0 = floor(10^19/54)
L = D0+1
U = 2D0.
```

It sits immediately beyond the reported pair-sum frontier. Choosing it is a scheduling hypothesis, not a theorem identifying the solution's location. For an upper aspect ratio R, rows below `floor(10^19/R)+1` have no candidate outside the reported region when `D≤D0`; these cheap coverage bounds can also define shells.

## Proof of safe integer intervals

Write `T=114bc`. Then `N'(a)=3(a²−T)`.

- If `bc≤0`, N is strictly increasing on the real line, apart from an isolated zero derivative that does not affect strict monotonicity.
- If `bc>0`, put `h=isqrt(T)`. Partition the integer a values into three disjoint sets:
  - `a≤−h−1`, increasing;
  - `−h≤a≤h`, decreasing;
  - `a≥h+1`, increasing.

The left and right intervals lie outside the derivative's real roots. The middle interval lies inside them. These integer intervals exhaust all a values without requiring floating-point comparisons to `sqrt(T)`.

Intersect each interval with the chosen finite t domain using exact floor/ceiling division. Search each monotone segment twice, for norm ranges `[ell·L,ell·U]` and `[−ell·U,−ell·L]`. Negate both the polynomial and target range on decreasing segments. Ordinary integer lower-bound searches then return all allowed t values; no candidate in the specified row and shell is omitted. There are at most six output intervals.

```
for each assigned (b,c) row:
    a0 = (-4*b-16*c) mod ell
    split the allowed t domain into the monotone segments above
    for each segment and each signed norm range:
        first = first t with signed_N(t) >= lower
        after = first t with signed_N(t) >= upper+1
        emit every t in [first, after)
```

Output intervals from disjoint segments have no overlap. Preserve all interval endpoints and use integer arithmetic throughout. A floating-point estimate may seed a search, but only exact endpoint comparisons may close it.

It is even possible to cover **every integer a** for one fixed `(b,c)` and bounded norm shell. Put `Q=114b³+12996c³` and `V=ell·U`. Choose an integer A satisfying

```
A² ≥ 684|bc|,
A³ ≥ 2(|Q|+V).
```

For `|a|>A`, the triangle inequality gives

```
|N(a)| ≥ |a|³−342|bc||a|−|Q|
       ≥ |a|³/2−|Q| > V.
```

Thus `[-A,A]` contains every permitted a. This certifies the entire a direction for that row; it does not cover unvisited `(b,c)` rows.

## Batch arithmetic after inversion

Within an emitted interval, advancing a by ell admits exact finite differences:

```
first_difference  = ell·(3a²+3ell·a+ell²−342bc)
second_difference = 6ell²·(a+ell)
third_difference  = 6ell³.
```

After evaluating the first norm, update with additions:

```
N += first_difference
first_difference += second_difference
second_difference += third_difference
```

The root numerators update cheaply too:

```
B = 114c²−ab;   B -= ell·b
C = b²−ac;     C -= ell·c.
```

This amortizes polynomial work and retains row locality. The modular inverse and final curve check are still needed. Keep the existing exact root identity and independent answer verification. Check integer-width bounds before using fixed-width arithmetic.

## Cheap quantitative geometry test

I tested the interval algorithm against direct enumeration on **400 small random oracle cases**, including all three multipliers, both signs of bc and varying shell bounds. Every result set agreed.

I then sampled 1,000 `(b,c)` rows per box bucket, with `b∈[-H,H]` and `c∈[1,H]`, using seed 114. This positive-c half is explicitly the sample domain; it is not a certificate for every row or for symmetry partners. The t bounds match the current box lattice. The shell was `[D0+1,2D0]`.

| ell | H | Empty rows | Eligible a fraction | Mean eligible a per row | Binary-search norm evaluations per emitted a |
|---|---:|---:|---:|---:|---:|
| 1 | 50,000 | 847/1,000 | 13.16% | 13,156 | 0.0052 |
| 5 | 85,499 | 856/1,000 | 12.76% | 4,364 | 0.0147 |
| 25 | 146,201 | 873/1,000 | 11.07% | 1,295 | 0.0428 |

These measure coefficient geometry, not distinct roots, solutions or elapsed performance. Most rows miss the shell entirely; suitable rows often emit thousands of consecutive coefficients. This is precisely the setting where interval inversion amortizes well. Raw reproduction script/results are `work/research-audit/shell_geometry.py` and `shell-geometry.json`.

A naive proposal filtered to this same shell visits approximately 8–9 coefficients per eligible coefficient. Interval inversion avoids most of that generation work. It does **not** imply 8–9× total throughput: modular inversion and sieving may dominate. If generation accounts for a fraction f of baseline runtime and improves eightfold, the overall speedup is `1/(1−f+f/8)`: about 1.10× at f=0.1, or 1.78× at f=0.5. Measure f rather than assuming it.

## Why this differs for the plane arm

The current plane arm has only five lattice offsets per `(b,c)` row. Binary searches costing tens of polynomial evaluations cannot amortize over five points. Evaluate those five directly, using finite differences if useful.

Near the cancellation plane `a*=−b∛114−c∛(114²)`,

```
N'(a*) = 3·114^(2/3)b² + 342bc + 3·114^(4/3)c².
```

For coefficients of size H this is typically proportional to H². A norm-shell width `ell·(U−L)` therefore corresponds approximately to `(U−L)/N'(a*)` lattice t values. At the current plane radius 20 million, many rows have only zero or a few eligible offsets. A much wider offset search, or an exact all-a shell generator with a rapid certified root locator, would be a different experiment; it should not be smuggled in as an optimization preserving the existing plane domain.

Walsh's [2022 slides, pages 20–21](https://ntrg.math.unideb.hu/GW2022Talk.pdf) motivate the cancellation-plane proposal. The interval construction and arithmetic analysis above are independent derivations, not a claim that the underlying norm method is new.

## Implementation gate

Prototype a **separate row-based shell worker**, without changing the live campaign. Give work units deterministic `(ell, b/c row range, a-domain definition, L,U, aspect-ratio band)` identities. Chunk long emitted intervals so interruptions remain cheap. Permute rows reproducibly to avoid exhausting one narrow coefficient shape first.

Require exact agreement against a direct filtered generator on small complete domains, boundary/adversarial tests, and additive restart coverage. Compare identical mathematical inputs under equal worker counts, including row inversion, root generation, symmetry, repeated curves, and ledger overhead. Then test larger rows with the same output domain.

A speed improvement and a search preference are separate findings. Clustering by `(b,c)` changes short-prefix shape sampling and may correlate adjacent roots; it does not establish enrichment. Moving into a shallower D shell increases the standard model's weight per root approximately as `1/D`, but it is not a calibrated chance of finding 114. Retain other shapes and scales, and never count an unvisited symmetry counterpart as an already excluded curve.

**Proceed to implementation only if profiling shows a meaningful generation bottleneck or matched-domain benchmarks establish an end-to-end gain.** This is a concrete algorithmic research direction with exact pruning and testable benefits. It offers no credible hours-to-solution guarantee.
