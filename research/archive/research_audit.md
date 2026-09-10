# Independent research audit for the 114 campaign

8 September 2026. This audit reviews the available primary literature and the existing local implementation; it is not a claim to have read every related paper. No new solution was found by this audit. Proposed implementation changes below are distinct from changes actually made by the other campaign workers.

## Verdict

An adaptive, correct, reproducible search is achievable. An hours-to-solution guarantee for 114 is unsupported. The present norm sampler's largest unresolved issue is the probability mass it visits, not the arithmetic square-test speed. Improvements to the latter are worthwhile, but cannot establish the former by themselves.

The productive architecture is an exact arithmetic engine, deterministic work units, a separately measured cost model, and a restricted experimental proposal portfolio. A model may reorder valid work; it must not invent permanent exclusions. Independent integer verification makes positive answers exceptionally easy to certify. Certifying absence over an infinite domain remains a different problem.

## What the strongest relevant literature already supplies

[Booker–Sutherland, On a question of Mordell](https://arxiv.org/abs/2007.01209), §§3–5, already combines recursive factor generation, cached roots, CRT enumeration, bitmap filters, dynamically selected auxiliary primes, and optimized search geometry. Its reciprocity table gives a retention factor 0.962 for 114 relative to its local constraints, so reciprocity alone is not a large missing advantage here. Remark 3.8 excludes pair sums through 100 unconditionally and through 20,000 under GRH using integral-point methods. The 2020 search used `D≤10^19/54, |z|≤10^19`; it did not certify every minimum coordinate through `10^19`. The paper supplies `rho_sol≈0.05845927` and `rho_AP≈0.34603123` for 114. These are conjectural/asymptotic distribution inputs, not validated probabilities for our selected norm samples.

[Grantham–Walsh, Representing integers as a sum of three cubes](https://arxiv.org/abs/2211.12149), gives the algebraic-norm/elliptic-curve alternative underlying this package. Its 2022 paper explicitly reports an unsuccessful effort on 114. The known solution of 3 is useful for illustrating the reduction but does not establish a blind predictive advantage on 114. Its cost estimates are not a probability model for a new target.

An additional primary source is [Walsh's March 2022 Debrecen slides](https://ntrg.math.unideb.hu/GW2022Talk.pdf). Slides 20–21 choose `a` close to `−b∛k−c∛(k²)`, reducing the coefficient proposal to two large loops plus a short offset interval. Slides 28–29 illustrate this using the known solutions of 33 and 42. Slide 33 reports rediscovering the large solution of 3 in about 9.16 core-years, unlike the later paper's projected estimates. This is a useful additional result, still far from a Mac-hours prediction. The local PDF parser dropped the leading `9.` on that slide; the PDF's independent web text confirms it. Several slide formulas have typographical problems, so identities must be derived and checked independently.

[Elkies, Rational points near curves and small nonzero |x³−y²| via lattice reduction](https://arxiv.org/abs/math/0005139), supplies a genuinely geometric approach: local linear approximation and lattice reduction find rational points close to curves. Its especially attractive complexity statement for the Fermat curve assumes a range of target residuals `M` much larger than the height `N`. It must not be quoted as a near-linear-time solution for a fixed residual 114 at height `10^18`. It is relevant as an alternative backend and for generating many-k benchmarks, but a new implementation would need a substantial validation effort.

[PARI's official documentation](https://pari.math.u-bordeaux.fr/dochtml/html/Elliptic_curves.html) distinguishes bounded rational-point searches, rank information, and saturation. A bounded `hyperellratpoints` return of no points is not an all-height integral-point certificate. Complete integral-point methods require the appropriate completeness of the Mordell–Weil information and explicit assumptions; analytic rank guesses cannot silently turn into exclusions.

The [December 2025 seed-equation preprint](https://arxiv.org/abs/2512.15763) was also screened at abstract level. It generates representations using a seed already representing the integer, with additional alternatives discussed. Its abstract does not supply a verified solution of 114 or a validated frontier algorithm. No implementation recommendation follows from the abstract alone.

## Immediate exact improvements

### Stronger 3-adic filters

I exhaustively enumerated the condition

`exists x mod m: x³+(S−x)³+z³ ≡114 mod m`, with `S≡1 mod3`.

| Modulus m | Allowed (S,z) pairs | Possible pairs | Retention |
|---|---:|---:|---:|
| 9 | 9 | 27 | 1/3 |
| 27, current implementation | 27 | 243 | 1/9 |
| 81 | 162 | 2,187 | 2/27 |
| 243 | 972 | 19,683 | 4/81 |

Thus the modulus-243 condition removes **5/9 of the pairs passing the current modulus-27 test**. Every relevant S row has twelve allowed z residues modulo 243. A byte table takes 59,049 bytes; packed rows for only S≡1 mod3 need about 2.5 KB. This is an exact necessary-condition improvement, not a learned conjecture. It does not imply a 2.25× total runtime improvement: candidate construction, inverse computation, and other fixed costs remain. Benchmark the full pipeline.

For a fixed `(D,r)`, translate the allowed z residues to q residues using `z=r+Dq` and `gcd(D,243)=1`. Use packed masks or step between allowed q residues instead of recalculating a cubic for every q. For long intervals, combine auxiliary prime masks or CRT wheels. Choose the wheel size by measurement: constructing a large wheel for a 64-value interval may cost more than it saves.

Raw results: `work/research-audit/residue-audit.json`. A reproduction script is included at the end of this report.

### Exact pruning of coefficient intervals

For fixed `(b,c)`, write

`N(a)=a³−342bc·a+114b³+12996c³`.

A target pair-sum shell `[Dlo,Dhi]` for multiplier ell permits only integers a with

`ell·Dlo ≤ |N(a)| ≤ ell·Dhi`.

Split the finite a range at derivative turning points `a²=114bc`; on each monotone integer segment, exact binary searches locate the permitted intervals. Carefully include endpoints and both signs of N. This can eliminate entire a intervals before modular inverses or curve checking, with a concrete mathematical reason. The resulting finite coefficient tile is still only a subset of all admissible progressions.

The Walsh cancellation-plane proposal is another useful arm, especially for reaching unit shapes poorly represented in the current cube. It should be labeled selective. Choosing a nearby plane using floating point is acceptable as a proposal; floating approximation cannot justify exclusion outside that plane. Use exact integer norms and class-lattice conditions for every accepted proposal.

### Make changes that preserve honest accounting

A deterministic coefficient tile is compact and resumable, but different coefficients can map to the same `(D,r)`. Therefore completed coefficient coverage is not identical to distinct curve coverage. Count them separately. An exact interval certificate for a curve must include both q endpoints and all arithmetic assumptions. Avoid enormous per-curve database insertion workloads; tile completion plus sampled duplicate diagnostics may be the practical choice, provided its limits are explicit.

Deduplicate signs immediately: gamma and −gamma have the same absolute norm and the same root. Unit multiples are another source of repeats; canonicalization can be expensive and must be benchmarked. Never skip work merely because a Bloom filter reports a possible duplicate.

## What adaptive learning should optimize

Use a small finite policy set: alternative moduli, prime orders, wheel sizes, short/long interval checkers, batch sizes, and worker counts. Race them on identical workload samples; compare full wall-clock cost, not just survivor counts. For independent filters with cost c and survival probability p, ordering by c/(1−p) minimizes expected cost. Actual filters are correlated; conditional rates and held-out timings are required before trusting that simplification.

A runtime model can safely learn from every failed candidate because runtime/rejection outcomes are abundant. A solution-location model cannot. If it is rewarded for producing few surviving candidates, it may simply learn to visit empty families; that is not discovery progress. If rewarded for many survivors, it may visit locally favorable but globally barren families. Neither objective is a calibrated solution probability.

A mathematical exposure score can be useful for scheduling under explicit assumptions. Keep it separately named, preserve exploration, and do not call it an observed chance of success. Improving mass searched per second is a better target than maximizing checks per second. Freeze any solution predictor before evaluating entire held-out values of k and higher held-out heights. Known-solution catalogues are positive data with a discovery history, not a random labeled sample of all candidates. Values k=1,2 and other parametrized easy families make particularly misleading frontier benchmarks.

Neural-network complexity is currently unjustified: there are zero known positive examples for 114, heterogeneous other fields, and little evidence that existing features predict a solution after local conditions and search geometry are accounted for. Lightweight cost learning and externally tested proposal weights give more interpretable improvements with lower overhead.

## Quantitative scale check — an explicitly conditional model

Here is my derivation, not a published calibrated probability for norm sampling. If progression roots in a narrow shell are exchangeable, the mean solution count per root over all feasible aspect ratios is approximately

`(rho_sol/rho_AP)/D ≈ 0.16894218/D`.

This follows by dividing the expected shell count `rho_sol·dD/D` by the progression count `rho_AP·dD`. The geometric mass for `|z|/D≤64` is about 0.75489458. For new roots just beyond the reported D frontier, the old `|z|≤10^17` cutoff lies below the feasible geometric ratio and costs no further asymptotic mass.

| Representative D | Model expectation per curve through ratio 64 | Expectation for 10^11 distinct comparable curves |
|---|---:|---:|
| 2×10^17 | 6.38×10^-19 | 6.38×10^-8 |
| 5×10^17 | 2.55×10^-19 | 2.55×10^-8 |
| 10^18 | 1.28×10^-19 | 1.28×10^-8 |

Arithmetic nonuniformity and the norm sampler's proposal bias violate literal exchangeability. Consequently these numbers are neither rigorous upper bounds nor calibrated probabilities. Their role is a sanity check: an hours-scale campaign needs an enormous, independently demonstrated enrichment effect for a substantial success chance. Hundreds of millions of failures do not establish such an effect. Under a further Poisson assumption these small expectations are approximately hit probabilities, but no claim of that calibration is made.

The same geometric heuristic gives expected all-ratio tail mass above `|z|=Z` for `D≤Dmax` of approximately

`2·rho_sol·1.96084322·sqrt(Dmax/Z)`.

At `Z=10^19`, fully excluding every D through `10^6` would account for only about `7.25×10^-8` expected tail solutions; through `10^10`, about `7.25×10^-6`. Expensive full-curve certificates for tiny D can therefore be mathematically valuable while contributing negligible expected discovery mass. The complete old-D tail is about 0.0312 by this approximation, but accessing all its progressions is itself vast. Raw calculation: `work/research-audit/heuristic-scale.json`.

## Recommended gates for the current build

1. Verify new modular tables exhaustively and replay all known-curve tests unchanged.
2. Compare new and old engines on identical work units; show candidate-count equality and separate timing improvements from coverage changes.
3. Validate deterministic tile interruption/restart and exact domain boundaries.
4. Benchmark a small policy portfolio, include controller overhead, and freeze the selected policy for a held-out batch.
5. Run a bounded Mac campaign over explicitly identified proposal arms. Persist both unresolved work and complete tiles. Stop immediately on any inconsistency; independently verify every proposed solution using two integer implementations.
6. Report actual coverage and measured speed. If no discovery-enrichment test succeeds, explicitly report that the campaign is a low-probability research attempt, regardless of throughput improvement.

This supports a trustworthy research engine. It cannot certify that a solution will appear in hours, that all useful algorithms have been exhausted, or that failures have localized the unknown answer.

## Reproduce the residue audit

```python
for m in (9, 27, 81, 243):
    cubes = [x*x*x % m for x in range(m)]
    inverse_cubes = {}
    for z, value in enumerate(cubes):
        inverse_cubes.setdefault(value, []).append(z)
    total = 0
    sizes = set()
    for s in range(1, m, 3):
        allowed = set()
        for x in range(m):
            value = (114-cubes[x]-cubes[(s-x) % m]) % m
            allowed.update(inverse_cubes.get(value, ()))
        total += len(allowed)
        sizes.add(len(allowed))
    print(m, total, (m//3)*m, sorted(sizes))
```
