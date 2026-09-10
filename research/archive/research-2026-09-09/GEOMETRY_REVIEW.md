# Geometry and root-generation review

**Recommendation: retain phase 3 now. Build the positive unit-phase tube as the next independently validated challenger.** It reaches a provably different part of the root-ideal geometry. Neither literature nor the present evidence establishes that this part is richer in solutions. A reference root sample should accompany any claim about its relative yield.

The main limitation is the enormous number of possible roots and the absence of a validated predictor of the very rare successful ones. Better coordinates can remove enumeration waste and expose missed families. They do not turn the entire frontier into an hours-long exhaustive computation.

## 1. What the literature supports

Grantham–Walsh already use cubic-field norms and class multipliers to generate candidate sums, followed by an elliptic-curve search. Their 2022 paper discusses choosing dependent coefficients, favorable representations of known solutions, and substantial unsuccessful work on 114. This supports testing norm geometry, but offers no theorem that small coefficients or a selected shape preferentially contain the next unknown solution. Its timing estimates concern a different search and cannot be transferred to this Mac campaign. [Grantham–Walsh, *Representing integers as a sum of three cubes*](https://arxiv.org/abs/2211.12149).

Browning–Wilsch recover the Heath-Brown prediction for sums of three cubes using real and local densities. Their discussion includes arithmetic restrictions and Brauer–Manin effects; these are population-level heuristics, not a classifier for our structured root samples. They also show why density heuristics need numerical scrutiny on related cubic surfaces. Nothing there proves exchangeability across our ideal classes and unit phases. [Browning–Wilsch, *Integral points on cubic surfaces: heuristics and numerics*, §§6 and 10](https://arxiv.org/abs/2407.16315).

The useful new proposal below is an implementation of the campaign's already established unit-shape geometry, rather than a claim of a new Diophantine method. The existing [unit-shape derivation](../unit_shape_proposal.md) and [phase-2 domain certificate](../phase2/DOMAIN_PROOF.md) supply the field, class-group, and unit facts.

## 2. A genuinely missing domain

Put `alpha³=114`, `gamma=a+b alpha+c alpha²`, and `n=Norm(gamma)>0`. Let `s` be its positive real embedding and `w` the absolute value of its complex embedding. Define

```
n=s w²,
tau=log(s/n^(1/3)),
s=n^(1/3)e^tau,  w=n^(1/3)e^(−tau/2).
```

The certified fundamental positive unit has real size `beta≈1.2399716847×10^10`; its logarithm is approximately `23.2409394744`. Multiplying by a unit shifts tau by an integer multiple of this regulator. One canonical interval is approximately `[-15.49396,7.74698)`.

At `D≥D0=floor(10^19/54)`, the old boxes have possible tau at most approximately `1.001`. The old cancellation planes and the positive-offset phase-2/3 families have negative tau; the largest phase-2 upper bound is approximately `−2.1`. Therefore a cell with

```
D0 < D ≤ 8D0,
1.1 ≤ tau ≤ 7.0,
ell ∈ {1,5,25},  n=ell D,
a+4b+16c ≡ 0 (mod ell)
```

lies outside those generators' possible phase support, in the same canonical unit interval. This is a domain-separation argument, not a statement that the whole new cell has been searched or contains a specified fraction of the roots.

For an exact implementation, an especially simple smaller cell is

```
28 < s³/n ≤ 10^9.
```

Its tau interval is approximately `(1.110735,6.907755]`, strictly inside the proposed gap. Rational boundaries avoid making logarithms or exponentials part of the membership decision. Subdivide it into disjoint rational lambda bands, where `lambda=s³/n`, and use exact comparisons at the shared endpoints.

Root ownership is already proved in the phase-2 certificate: a surviving generator with `gcd(b²−ac,D)=1` represents exactly `I(D,r)J^j`, with `ell=5^j`. Different j own different ideal classes. Within one regulator interval, two positive generators cannot give the same root ideal unless they are equal. Thus a correctly implemented tube can inherit precise root ownership and separation from the earlier families. Repeated roots in distinct quotient bands still represent intentionally different z positions; unfinished retries remain an operational source of repeated work.

## 3. A finite tube enumerator with proof-based row cuts

Set `u=a−alpha²c` and `v=b−alpha c`. The complex norm is exactly

```
w² = u²−alpha u v+alpha²v²
   = (a−(alpha b+alpha²c)/2)²
     + 3(alpha b−alpha²c)²/4.
```

This is a tube around `(a,b,c)=(alpha²c,alpha c,c)`. It has two thin directions. Restricting to a single nearest approximation in each direction would discard valid points; the circle cross-sections enumerate all complex angles.

For a finite norm/phase cell, choose certified bounds `s_min≤s≤s_max` and `w≤W`. Fourier inversion gives each of `a`, `alpha b`, and `alpha²c` in `[(s−2w)/3,(s+2w)/3]`. In particular, `lambda>4` implies `s>2w`, so **all three coefficients are positive** in the proposed cell.

A complete enumeration can proceed as follows:

1. Bound c by `(s_min−2W)/(3alpha²)` and `(s_max+2W)/(3alpha²)`, with outward rounding.
2. For each c, restrict b by `|alpha b−alpha²c|≤2W/sqrt(3)`.
3. For each `(b,c)`, put `m=(alpha b+alpha²c)/2` and `T=3(alpha b−alpha²c)²/4`. If `T>W²`, discard the entire row.
4. Otherwise restrict a to `[m−sqrt(W²−T), m+sqrt(W²−T)]`, intersect the real-embedding bounds and the class congruence, and apply exact cubic norm-shell interval inversion.
5. Apply exact lambda membership, the existing necessary arithmetic filters, modular root verification, and the existing quotient checker.

The row and interval exclusions follow directly from the displayed identity. A production version must use outward rational/interval bounds for every cut. The existing fixed alpha approximations can seed fast bounds, but their old coefficient-error certificate does not automatically cover larger tube coefficients. If a boundary comparison remains ambiguous, refine it rather than discarding the point.

There is a simple entirely rational outer-bound construction. For `n∈(n_lo,n_hi]` and `lambda∈(lambda_lo,lambda_hi]`, take an integer lower bound for `(n_lo lambda_lo)^(1/3)`, an integer upper bound for `(n_hi lambda_hi)^(1/3)`, and `W²≥n_hi/s_min`. These can be computed with integer roots. For positive coefficients, a rational isolating interval for alpha immediately bounds `s=a+b alpha+c alpha²`; cubing those rational bounds certifies lambda membership, with arbitrary-precision refinement only when needed.

A reproducible small audit is in [check_tube.py](check_tube.py), with results in [tube-audit.json](tube-audit.json). It compares certified circle-row bounds against complete positive coefficient rectangles for 12 small norm/phase/class cells. The rectangles contain **83,473 positions**; the tube produces exactly the same **166 cell members**, with no missing or extra coefficients. All exclusion and membership decisions in that audit use exact integer/rational arithmetic. It does not run the quotient checker, benchmark native throughput, or validate a production worker.

At the full proposed upper bounds, illustrative coefficient limits are roughly `a≤1.22×10^9`, `b≤2.52×10^8`, `c≤5.19×10^7`. An illustrative sum-of-absolute-norm-terms bound uses 94 bits. This suggests signed 128-bit arithmetic remains feasible, but a new exact overflow certificate must cover every promoted C expression, recurrence, interval numerator, and counter. The numbers here are design estimates, not that certificate.

## 4. When lattice reduction helps

An alternative for a phase cell centered at `tau0` is the positive quadratic form

```
Q(gamma)=e^(−2tau0)s²+2e^tau0 w².
```

If `tau=tau0+delta`, then

```
Q(gamma)=n^(2/3)(e^(2delta)+2e^(−delta)).
```

Finite bounds for n and delta therefore give an enclosing ellipsoid. The class lattice has basis columns `(ell,0,0)`, `(-4,1,0)`, `(-16,0,1)`. A certified rational enclosure, a unimodular reduced basis, and complete short-vector enumeration can traverse this ellipsoid without scanning its enormous axis-aligned box. LLL only changes coordinates; a complete bounded enumeration after it is essential.

PARI provides `qflll` and integral positive-form enumeration through `forqfvec`; the documented interface enumerates representatives of pairs `{v,−v}`. A positive-real representative and exact final membership must be selected explicitly. Vector caps, float-only boundary cuts, and undocumented callback stopping rules would undermine completeness. [PARI official linear-algebra and quadratic-form documentation](https://pari.math.u-bordeaux.fr/dochtml/html-stable/Vectors__matrices__linear_algebra_and_sets.html).

For the first challenger, the direct tube cross-section method is easier to audit and reuses the existing exact shell inversion. Reduce its row lattice if measurements show that thin irrational rows dominate cost. The ellipsoid method is a useful independent reference and a possible later accelerator; it is not automatically faster than the simpler enumeration in dimension three.

The normalized continuous lattice volume of a norm/phase cell is `2 pi ΔD Δtau /sqrt(350892)` per class. Across three classes, `D∈(D0,8D0]` and tau width 5.9 give approximately **2.43×10^17**. This is neither a finite-height integer-point count nor a runtime lower bound. It nevertheless makes clear why exhaustive enumeration of the whole new region is not the proposed Mac-scale campaign. We need deterministic finite tiles and an explicitly partial ledger.

## 5. Obtain an independent root control sample

The cheapest reliable small control is the published CRT/divisor backend on a completely enumerated finite interval, retaining all roots and using reservoir sampling if storage is limited. It has a known population and does not inherit the norm generator's shape selection.

At the frontier, uniformly sample D in a prescribed shell and enumerate **all** roots modulo each sampled D. Every `(D,r)` label then has the same inclusion probability. The sample is clustered by D; independent-root error bars would be wrong. Uniform D followed by one randomly chosen root is instead biased by the varying number of roots of D. An average computed from a finite pooled root sample is also not automatically an exactly unbiased ratio estimator; retain the original inclusion probabilities and use design-based totals where appropriate.

Factoring independently drawn large integers may be avoidable. Bach and Kalai give algorithms to sample a uniform integer together with its factorization. Rejection to the desired interval produces a uniform factored shell sample. This is a credible route to a modest high-D audit: solve the local cubics, use CRT to emit all roots, and recover ideal class/unit phase for a subset. It is not presently a demonstrated faster bulk generator than the native norm inversion. Selecting convenient semiprime or smooth products without known weights would lose the uniform control. [Kalai, *Generating Random Factored Numbers, Easily*](https://www.microsoft.com/en-us/research/publication/generating-random-factored-numbers-easily/).

The 2026 revision of de Boer–Pellet-Mary–Wesolowski is relevant to rigorous ideal sampling, but its ERH-conditional guarantee concerns families multiplied by a smooth-ideal family. It does not supply uniform solution-bearing root ideals in this fixed norm shell, or make our class/unit setup—already computed—the dominant missing algorithm. [*Rigorous methods for computational number theory*, v2](https://arxiv.org/abs/2512.01588v2).

## 6. Exposure weighting and the promotion gate

The current `sum(D0/D)` score accounts for the leading size dependence under an exchangeability model; the controller separately apportions quotient bands. It does not encode every conditional arithmetic factor of an individual `(D,r)` or every phase-selection effect. In particular, primes dividing D can impose different affine quadratic-residue restrictions after the square condition is normalized by D. The exact sieve correctly handles necessary restrictions, but a global density constant is not automatically the right relative score after conditioning on them.

Do not simply multiply the score by raw sieve survival: already imposed conditions would be counted twice, and survivors are not known positives. A future correction needs a defined reference population, the same previously applied congruences, a derived conditional density ratio, and held-out evidence. The current score should remain labeled computational exposure, without converting it into a claimed hit probability.

Promotion requires: exact finite cell and row ownership; outward-bound and overflow proofs; complete small-domain coefficient/root equality; endpoint and ambiguity tests; known-positive checker regressions; source/binary provenance and durable ledger integration; and a paired native benchmark with all setup and checking costs included. Compare old and new methods on identical finite cells where possible. Compare different phases as different coverage populations, not as a proven speedup in finding solutions.

**The next useful experiment is a new, small, disjoint tube tile—not a silent replacement of phase 3.** If it delivers competitive verified-root exposure per CPU second, retain a bounded allocation for the new geometry while the control sample measures its arithmetic and phase selection. No claim of a solution in hours follows from this review.
