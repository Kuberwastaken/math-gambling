# An optimized search design for x³+y³+z³ = 114

The best-supported design combines exact branch elimination, geometry-aware generation of distinct candidates, and a cost-aware algorithm portfolio. Learning determines which unresolved work to process next and how to process it. Only mathematical proofs determine which branches may be discarded.

This report was prepared during the earlier user-requested pause. The user subsequently authorized implementation and resumption. Phase3 now implements the equivalent row batching, divisor recurrences, short-quotient bitsets and lazy prime setup, and resumes the preserved geometry. Other extensions below remain proposals. See [the implemented release and evidence](phase3/README.md).

## 1. Reduce the problem before choosing a search algorithm

Put

\[
S=x+y=\sigma D,\qquad D>0,\quad \sigma\in\{-1,1\},\qquad z=r+Dq.
\]

The original equation implies `r³≡114 (mod D)`. With `v=x−y`, it also implies

\[
v^2=\frac{4(114-z^3)-S^3}{3S},\qquad v\equiv S\pmod2.
\]

A candidate passing this test gives `x=(S+v)/2` and `y=(S−v)/2`, followed by an independent integer cube check. The D=0 case would require an integer cube equal to114 and is impossible. Reducing cubes modulo9 forces every coordinate to be2 modulo3, so `3∤D` and S is positive for D≡1 modulo3, negative for D≡2.

For the campaign's ordering, with z the coordinate of smallest absolute value, the opposite-sign pair, with v chosen nonnegative, additionally requires `v≥D+2|z|`. In the large-coordinate region its asymptotic consequence is `|z|/D≥1/(cuberoot(2)−1)≈3.847`. Implement the exact inequality, retaining114, at boundaries; the asymptotic constant is a scheduling aid rather than an exact universal rejection threshold.

This formulation replaces independent searches over x,y,z with a search over admissible divisors, modular roots and quotient intervals. The published factor/CRT algorithm is already a sophisticated realization of this reduction, with dynamic auxiliary primes and implicit progression intersections. It should be the reference backend, not a naive triple loop. [Booker–Sutherland, *On a question of Mordell*, 2021](https://arxiv.org/abs/2007.01209); [authors' reference implementation](https://github.com/AndrewVSutherland/SumsOfThreeCubes).

## 2. Exact branch elimination

| Rule | Branch that can be eliminated | Status in this project |
| --- | --- | --- |
| D divisible by3,4 or361 | Every such divisor, at every height | Existing conditions; analytic explanation below |
| A prime factor p has no cubic root of114 | Every divisor containing p | Standard CRT construction; implicit in successful norm-root recovery |
| Signed D residues fail modulo8 or361 | Entire signed-divisor residue classes | Existing certified filters |
| A coefficient interval cannot enter its assigned norm shell | That bounded row interval in that shell | Implemented exact norm inversion |
| A normalized square polynomial has no root in a q residue class | All q in that class for the fixed D,r | New proposed extension at primes dividing D |
| Surviving CRT progression misses a bounded q interval | That bounded interval/progression intersection | Standard exact interval arithmetic |
| A rigorously enclosed polynomial range contains no permitted square | That bounded interval | Valid but often weak at frontier scale |
| A complete elliptic integral-point certificate excludes a fixed S | The whole fixed-S family, potentially all q | Separate expensive proposal; bounded point search is insufficient |

A certificate must record its scope. An empty interval is not an empty infinite progression. A covered coefficient box is not a covered divisor range. Unfinished computation or a low learned score is not a certificate.

### Divisor-factor rules

Since2 and19 divide114 to exponent one, neither can divide D to exponent two: a root modulo p forces p to divide z, contradicting `z³≡114 (mod p²)`. The stronger sum-of-cubes constraint excludes3 from D entirely.

For p not dividing114 with p≡1 modulo3, the criterion for any cubic root is

\[
114^{(p-1)/3}\equiv1\pmod p.
\]

If it fails, reject the entire factor branch before constructing any D containing p. For example,114≡2 modulo7, while cubes modulo7 are0,1,6; therefore **every multiple of7 is impossible as D**. For p≡2 modulo3, cubing is invertible on nonzero residues, and the unique root lifts through every prime power. These rules do not say that an allowed factor pattern is especially likely to produce a global solution.

The signed rules have short analytic forms. For even D, x and y must be odd, z even, and `S≡2 (mod8)`; together with `S≡1 (mod3)`, this permits even D only in classes10 and14 modulo24. For19 dividing D, let S=19h. Reduction modulo361 gives `h*x²≡2 (mod19)`, so h must be a nonzero quadratic nonresidue modulo19. These explain the existing tables rather than supplying additional measured gains.

### New specific opportunity: normalize before square sieving

The scaled square expression

\[
\Delta(q)=3S\,[4(114-(r+Dq)^3)-S^3]
\]

is identically zero modulo every prime dividing D. A square-residue test on this expression cannot discriminate at those primes.

Instead, use the exact integer `h=(114−r³)/D` and

\[
H(q)=4h-12r^2q-12rDq^2-4D^2q^3-\sigma D^2,
\qquad v^2=H(q)/(3\sigma).
\]

Choose the required q class modulo3 first, or retain the undivided equation when handling3. For an odd prime p dividing D with p not dividing3·114,

\[
v^2\equiv \frac{4\sigma}{3}h-4\sigma r^2q\pmod p.
\]

The q coefficient is nonzero. Exactly `(p+1)/2` q classes can be squares, including the class giving zero. **When5 divides D, this excludes two of five q classes.** That is a local elimination fraction, not a forecast of total runtime improvement. Small prime divisors can be detected from a fixed inventory; factoring every generated D is unnecessary for this limited extension.

For the existing positive-norm generator, put `C=b²−ac`, `B=114c²−ab`, `T=114c³−b³`, and `L=(rC−B)/D`. The already-established norm identity yields

\[
h\equiv-(\ell T+3B^2L)C^{-3}\pmod p.
\]

This obtains the needed residue without constructing r³. Invertibility follows from the root extractor's gcd condition. The formula and exclusion were derived algebraically; the implementation cost, overflow bounds and interaction with current filters still require validation. No claim is made that normalized sieving is new to number theory or absent from every other implementation.

### A selective p-adic tree

After exact substitutions produce an integer polynomial P(u), a local node represents `u≡u0 (mod p^e)` and every surviving square root v0 modulo p^e. Children satisfy the exact lift condition

\[
\frac{v_0^2-P(u_0)}{p^e}+2v_0 k-P'(u_0)j\equiv0\pmod p.
\]

A child with no lift is impossible for every integer in that residue class. At odd p, a nonzero v0 has invertible derivative2v0: every u child lifts, so deeper powers add **no further pruning on that nonsingular branch**. Spend lifting work on zero/singular branches and factors with unremoved content. Odd valuations cannot be squares; after removing an even valuation, the unit part must have the proper square residue. Handle zero separately.

Combine local branches with CRT only when residues agree modulo the gcd of their moduli. Do not multiply overlapping moduli blindly. Within `[L,U]`, a progression `u≡a (mod M)` is empty precisely when its first possible element `a+M*ceil((L−a)/M)` exceeds U.

Stop building a larger CRT structure when its construction cost exceeds the checking work it would save. An implicit bitmap/intersection representation is often preferable to explicitly listing a combinatorial product of residues. An unsuccessful local filter should be removed from the processing policy, not confused with a failed mathematical region.

### Why generic interval bisection is not the main answer

Rigorous bounds A≤P(u)≤B can eliminate a tile if B<0 or no integer square of the required parity lies between the bounds. If few squares remain, exact inversion on monotone pieces is possible.

But near the present frontier, the square expression is roughly D²|q|³. A q step changes it on scale D²q², whereas square spacing is only on scale D|q|^(3/2). Broad range bounds therefore contain many squares even when none of the sampled polynomial values is a square. A binary subdivision can reach singletons without useful bulk pruning. Modular branches and norm-shell inversion have a stronger structural justification here than a generic box search.

## 3. Choose processing policies by saved work

Two immediate execution proposals from the earlier brainstorm remain strong candidates: the456-period coefficient-row wheel, and the roughly5.2KB short-q mask table. The former combines already-known divisor/sign filters; the latter translates the existing modulo243 condition and applies parity with bit operations. Direct finite differences for D and lazy initialization of late auxiliary primes could reduce setup. None has been benchmarked during the pause. [Algebraic derivations and prerequisites](STRATEGY_PAUSE.md).

For a proposed extra filter, let m be the number of candidates reaching it, p its conditional retention, c its per-candidate cost, Cs its setup cost and Ct the remaining checker cost per candidate. It is worth applying only when the measured estimates support

\[
C_s+mc<m(1-p)C_t.
\]

Estimate retention **after the preceding filters**, because they are correlated. A mistaken estimate may slow processing but must never alter the accepted candidate set. The same principle decides whether to enlarge a wheel, add a prime, deepen a singular p-adic branch or fall back to direct checking.

Also compare extending the quotient range of an existing root with constructing another root. The relevant quantity is **additional unsearched weighted coverage divided by additional cost**, including reusable setup. A fixed ratio or fixed number of q values is not optimal for every generator and divisor. Dynamic geometry optimization has a published precedent, but parameters must be calibrated for this implementation and machine. [Booker–Sutherland, §§4–5](https://arxiv.org/abs/2007.01209).

## 4. Where to look next

The known omission is in generator support, not a discovered concentration of solutions. For the fixed class-clearing convention, define

\[
\tau=\log\left(\frac{|\sigma_{\mathbb R}(\gamma)|}{|N(\gamma)|^{1/3}}\right)\pmod{\log\beta},
\]

where beta is the certified fundamental unit, with log(beta)≈23.24094. Unlike raw coefficient offsets, this coordinate is invariant under changing the generator by a unit. Separate the norm shell, class, normalized phase and complex-angle cross-section in the coverage registry.

A concrete proposed new region is

\[
D_0<D\le8D_0,\qquad1.1\le\tau\le7.0,
\qquad D_0=\lfloor10^{19}/54\rfloor.
\]

Under the recorded basis, class-clearing ideals and representative interval `[-2log(beta)/3,log(beta)/3)`, this lies above the old box's approximately1.001 phase ceiling. The old plane and phase2 offset families have negative phase support. Independent reasoning checks found no wraparound conflict in this shell. A new enumerator still needs exact endpoint bounds and its own implementation certificate before production.

Positive phase corresponds to relatively small complex embedding. Its coefficient geometry is a tube near

\[
(a,b,c)\propto(\alpha^2,\alpha,1),\qquad\alpha^3=114.
\]

A lattice basis adapted to that tube, rigorous cell enclosures and exact norm-shell inversion are preferable to scanning its huge enclosing coordinate box. Both thin directions matter: a few especially good rational approximants do not enumerate the tube. LLL is a basis-reduction tool; completeness requires complete lattice-point enumeration within the declared cells.

Equal phase widths are a geometric diversity baseline. They are not known equal masses of solution-bearing roots. The proposal addresses a real coverage gap, without establishing that the gap is fertile. The field reduction builds on norm methods such as [Grantham–Walsh](https://arxiv.org/abs/2211.12149); the particular phase bounds come from [the local certified generator analysis](unit_shape_proposal.md).

## 5. Tune exploration and ML as separate decisions

Separate a mathematical region from its processing configuration. Changing a wheel for the same exact region preserves coverage. Moving to a different phase changes the search allocation. A future registry could use3 classes ×12 phase bins ×3 divisor shells ×3 quotient bands:324 strata. This is a design target, not324 already-implemented or exhausted regions.

A proposed initial allocation is:

| Lane | Worker-time share | Rule |
| --- | ---: | --- |
| Mathematical diversity | 40% | Fixed coverage-deficit schedule across certified strata |
| Timing/model exploration | 10% | Randomized, logged sampling of uncertain or stale processing contexts |
| Measured exploitation | 50% | Highest validated weighted-coverage-per-cost estimate |

These percentages are operating choices, not a proven optimum. The40% lane protects against the unvalidated solution-density model. It should not disappear merely because timing predictions become accurate. The10% lane learns costs and supports cleaner evaluation; it can decrease when estimates stabilize.

Start with a recent empirical cost/exposure table with sparse contexts shrunk toward parent groups. Use contextual ridge only as a challenger for transfer and shrinkage. For a batch, retain raw cost C and newly completed exposure E, with a possible baseline weight

\[
E=\sum_{\text{new root intervals}}\frac{D_{\mathrm{ref}}}{D}\,G(\text{ratio interval}).
\]

Compare total E divided by total C. An unweighted average of batch rates overweights tiny jobs. This is a conditional geometric proxy, not a learned probability of finding114. A duplicated timing calibration consumes cost but receives zero new-coverage credit.

UCB-style optimism or Thompson sampling can prioritize uncertain **throughput**. Their confidence terms do not measure uncertainty about solution fertility. Standard guarantees assume statistical conditions that timing drift, variable costs and interval depletion do not automatically satisfy. Resource-constrained bandit models are conceptually more appropriate than equal-cost pulls. [Badanidiyuru, Kleinberg and Slivkins, *Bandits with Knapsacks*](https://arxiv.org/abs/1305.2545); [Li et al., contextual-bandit approach](https://arxiv.org/abs/1003.0146).

Use Bayesian optimization only for a small processing-parameter space such as batching or a measured wheel threshold. Hyperband can eliminate slow processing configurations on controlled benchmarks; it must not discard mathematical regions because early batches found no solution. [Snoek, Larochelle and Adams](https://arxiv.org/abs/1206.2944); [Li et al., *Hyperband*](https://www.jmlr.org/papers/v18/16-558.html).

### Explicit initial tuning rules

- Require three disjoint completed blocks before a context becomes eligible for empirical exploitation. Cold model predictions enter timing exploration first.
- Use a proposed30-minute decay half-life and up to64 recent blocks per context, retaining all raw lifetime measurements. A binary, geometry or worker-count change starts a separate timing epoch.
- In timing exploration, mix uniform selection with uncertainty/staleness selection and log the actual conditional probability. Do not retrospectively invent propensities for the old deterministic schedule.
- Review at fixed15-minute checkpoints. Two successive median observed/predicted cost ratios outside `[0.8,1.25]` trigger recalibration: temporarily40% diversity,20% measurement,40% baseline allocation. This is an operational trigger, not a formal change-detection guarantee.
- Following stable fresh reviews, timing exploration may fall to5%, giving40/5/55. It should rise when machine load or an algorithm changes. Fund changes from exploitation, preserving diversity.
- Account in worker seconds, with reservations for in-flight jobs. Initially cap an identical uncertain context at one pending measurement; a measured exploitation context may use several disjoint blocks. Do not count pending work as completed.
- Compare ridge/UCB/Thompson challengers against the simple empirical table under identical coverage floors. Promote only after fresh controlled panels show a material end-to-end improvement, including scheduler cost. The previous balanced-allocation gate did not establish that marginal advantage.

These rules can be refined after explicit authorization and measurements. None is currently active in production.

## 6. Discovery weighting needs its own evidence

A stronger prospective score might multiply the geometric weight by a correctly normalized finite local-density factor derived from the normalized square equation. Specify the reference root population and every conditioning step. A filter's survival fraction cannot be applied a second time as though it supplied independent information.

First compare against an independently enumerated finite root population to diagnose generator bias. Then freeze scoring rules and test on distinct known solutions, holding out entire targets and higher size bands. A catalogue of known positive triples does not make every unlisted candidate a negative example. Match coverage constraints and distinguish proposal reach from scoring performance.

Use prospective randomized comparisons or carefully defined matched blocks for policy claims. The scheduler depletes available regions, so replaying another policy from a deterministic log does not generally reconstruct its counterfactual trajectory. Off-policy methods require stated support and statistical assumptions; none creates missing solution labels. [Dudik, Langford and Li, *Doubly Robust Policy Evaluation and Learning*](https://arxiv.org/abs/1103.4601).

The failed114 batches can train cost and rejection models. They cannot justify moving probability away from neighboring unseen integers without an additional, tested model of mathematical correlation. Recent heuristic work on cubic surfaces concerns asymptotic densities and numerical evidence, not an efficient decision procedure for this one target. [Browning–Wilsch, *Integral points on cubic surfaces: heuristics and numerics*](https://arxiv.org/abs/2407.16315).

## 7. Algorithm portfolio and boundaries

| Method | Best role | Main limitation |
| --- | --- | --- |
| Booker–Sutherland factor/CRT | Complete bounded reference; structured divisor work | Roughly linear progression burden remains enormous at the frontier |
| Norm generation with adapted unit-phase lattice cells | Reach high divisors in explicit new shapes | Thin-cell enumeration and proof of complete cell ownership are not yet implemented |
| Known-factor high-D root sampling | Independent control against norm-sampler bias | Prime/cofactor choices create their own selective support |
| Complete fixed-S elliptic certificates | Settle selected expensive infinite tails | Requires genuinely complete arithmetic information; setup can dominate |
| Direct near-curve lattice search | Alternative geometry or many-target comparison | Broad-tolerance complexity does not imply a fast fixed114 frontier search |
| Coppersmith small roots | Revisit only with additional proved size information | z is not small relative to D^(1/3); short q still leaves an unknown square variable |

For fixed S, the transformation `U=−12Sz`, `V=36S²(x−y)` gives `V²=U³+432S³(456−S³)`. Complete integral-point information with the reverse divisibility and parity conditions can eliminate that entire S. A bounded point search returning nothing cannot. [PARI elliptic-curve documentation](https://pari.math.u-bordeaux.fr/dochtml/html/Elliptic_curves.html).

Lattice reduction is not a universal promise of small search. The near-curve method has genuine geometric precedents, but its favorable published parameter regime must be respected. Likewise the standard cubic Coppersmith guarantee concerns roots smaller than approximately the cube root of the modulus; the natural formulation here does not meet it. This is a limitation of that formulation, not an impossibility result for every future reformulation. [Elkies](https://arxiv.org/abs/math/0005139); [Chinburg et al., limitations of univariate Coppersmith auxiliaries](https://arxiv.org/abs/1605.08065).

## 8. Proposed control flow

```text
choose a certified region and a processing policy using its lane budget
reserve a previously unvisited block atomically
apply exact geometry, divisor-factor and norm-shell exclusions
build only cost-justified modular branches, keeping every live child
use normalized square masks, including eligible primes dividing D
intersect surviving progressions with the exact quotient interval
perform exact square, parity, coordinate-order and cube-identity checks
save any verified solution before fallible learning/bookkeeping
commit coverage and exclusion certificates; update costs and remaining budget
```

If a region is expensive, lower its current priority while leaving its diversity allocation and unresolved status intact. If a proof excludes it, remove precisely the domain covered by that proof. If an algorithm fails validation, disable that processing configuration. These are distinct outcomes.

The recommended sequence after explicit resumption is to test normalized divisor-prime sieving and the456/243 masks first, compare an empirical scheduler with its challengers second, and develop the positive-phase lattice geometry as the structural research project. Full elliptic certificates remain a limited side portfolio. No existing evidence establishes that this combination will find a114 solution in hours; it does give a concrete, testable route to reducing waste and exploring new mathematical territory.
