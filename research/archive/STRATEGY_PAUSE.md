# Research pause: better search strategies for 114

The solution search is stopped at the user's request. No workers, benchmarks, builds or new solution-search experiments were run for this brainstorm. Existing outputs, source and primary literature were read. Resumption requires an explicit user instruction; the STOP marker and paused heartbeat remain in force.

The main opportunity is to improve which mathematically distinct candidates get inspected, while reducing their arithmetic cost. The completed run validates parts of the execution machinery. It does not validate its score as a predictor of solutions.

## Ranked next experiments — none started

| Priority | Change | Why it is worth investigating | What must be demonstrated |
| --- | --- | --- | --- |
| 1 | Combine existing coefficient rejection tests into a 456-period row wheel; update D directly by finite differences | Skip arithmetic on offsets already known to fail, especially in long offset bands | Identical accepted candidates and correct exclusion accounting, followed by a matched whole-pipeline speedup |
| 2 | Precomputed short-quotient masks and lazy auxiliary-prime setup | Most short-band positions are removed by the existing 3-adic/parity conditions; constructing all prime metadata eagerly can waste work | Exact interval/wraparound behavior and gains across the actual mix of short and long bands |
| 3 | Normalize shape coverage; add complex-cancellation neighborhoods | Reach mathematically different regions that raw offset choices can omit | Certified domains, overlap accounting and favorable lattice-node cost, without assuming uniform solution density |
| 4 | Separate arithmetic weighting from learned costs; compare with a simple cost table | Prevent a sophisticated learner from merely optimizing an unvalidated score | Held-out actual-solution enrichment for predictive claims; controlled cost advantage for execution claims |
| 5 | Root-first CRT reference and a small elliptic-certificate portfolio | Compare against an established alternative and test whether whole curves can sometimes be settled cheaply | Matched finite coverage; genuinely complete certificates with assumptions recorded |

Priorities 1 and 2 offer plausible execution improvements. Priority 3 addresses proposal diversity. Priority 4 addresses the missing evidence about discovery. No speedup factor or short-time success probability has been established for these proposals.

## Concrete arithmetic finding: a 456-period row wheel

This derivation was checked independently by two agents, using algebra only. It reorganizes existing certified cuts; it is not a new obstruction to 114.

For fixed b,c and class-lattice base, let a=base+ell*t, ell in {1,5,25}, and

    N = a^3 + 114*b^3 + 12996*c^3 - 342*a*b*c,
    D = N/ell > 0.

The current three-adic divisor condition rejects D divisible by 3. Since N is congruent to a modulo 3 and ell is invertible modulo 3, this rejects one residue of t modulo 3. For the other residues, S=x+y is +D when D is 1 modulo 3 and −D otherwise.

The signed modulo-8 test depends on t modulo 24: N/ell modulo 8 has period 8, while the sign depends on t modulo 3.

Every forbidden S modulo 361 is divisible by 19. But N is congruent to a^3 modulo 19, so these failures require 19 dividing a. In that case

    N/19 = a^3/19 + 6*b^3 + 684*c^3 - 18*a*b*c
           ≡ 6*b^3 (mod 19).

Thus D modulo 361 is the fixed row value `19*(6*ell^(-1)*b^3 mod19)` whenever a is 0 modulo 19. Whether its signed value is forbidden adds only the modulo-3 sign condition. This test therefore depends on t modulo 57. Combining 24 and 57 yields the sufficient period **456**.

A future implementation can construct an allowed-offset bit mask once per row, intersect it with the exact norm-shell intervals, and jump between allowed offsets. It must retain separate exact counts for the existing rejection categories. The derivation assumes integral D and positive N; a negative-norm backend needs separate sign handling.

There is a compatible arithmetic simplification. With p0=−342*b*c, advancing a by ell gives

    D(t+1)−D(t) = 3*a^2 + 3*ell*a + ell^2 + p0,
    second difference = 6*ell*(a+ell),
    third difference = 6*ell^2.

These are integral, so repeated 128-bit division by ell can be replaced by additions after the initial D evaluation. Jumps between allowed offsets require the correct polynomial jump formula and overflow bounds. This has not been implemented or benchmarked during the pause.

The completed two-hour data classified roughly 445 billion shell-eligible coefficient positions: about 148 billion failed the divisor-modulo-3 condition and 116 billion failed signed-sum filters. These are already avoided before inversion; a wheel would save their generation/filter arithmetic, not the subsequent curve work, which they never incurred. Therefore the rejection fraction is not a total-runtime speedup estimate.

## Short-interval sieve proposal

For D not divisible by 3, `z=r+D*q` translates the existing modulo-243 restrictions into a small set of q residues. A proposed table needs only 162 base masks of 243 bits, indexed by D modulo 243: about 5.2 KB using four 64-bit words per mask. Translate by `D^(-1)*r modulo243`, extract a cyclic window, then apply alternating parity bits for odd D or a whole-window parity check for even D. This could replace a scan of every short-band position with extraction of allowed bits. A separate period-486 table is unnecessary. Separate popcounts would preserve the modulo-243 and parity rejection counters; wraparound and interval endpoints still need independent tests.

The critical comparison is against the existing short-interval implementation, including mask construction and translation. A large wheel can cost more than it saves for short intervals. Prepare metadata for later auxiliary primes only when a candidate reaches them; derive signed residues from already computed D residues where valid. All of these are hypotheses about execution cost until measured.

A persistent worker or a shared cache may also reduce setup. Fusing divisor shells and quotient bands could share generation where their row prefixes overlap, but must not force expensive tail searches merely to reuse setup. Long-lived state would need reset/replay tests and exact ownership. Existing aggregate counters do not provide a stage-time profile, so a GPU port or a predicted large speedup is premature.

## A more defensible proposal coordinate

For a class-cleared generator gamma with norm n=ell*D, write

    tau = log(|sigma_real(gamma)| / n^(1/3)) mod log(beta).

Here beta is the certified fundamental positive unit of Q(cuberoot(114)). Multiplication by a unit preserves n and shifts the numerator's logarithm by an integer multiple of log(beta), so tau is independent of the chosen generator for that fixed principal ideal. Raw coefficient offsets do not have this invariance and drift in meaning with D and ell.

A future design should split this normalized shape into explicit bins, record actual admitted points, and prove ownership and overlap boundaries. Equal-width bins provide a geometric baseline, not a theorem that roots or solutions are uniformly distributed. The complex embedding's angle and the finite coefficient box still matter; ticking off a bin does not exhaust it.

Our existing real-cancellation proposals are only part of this geometry. Neighborhoods where the complex embedding nearly cancels, approximately (a,b,c)=(alpha^2*c,alpha*c,c), deserve a separately defined proposal. They might reach useful missed shapes; no increased solution density or speedup is established.

## Make the learner earn its complexity

The existing held-out comparison established execution-proxy ranking against a balanced allocation and a geometry-only ranking. It did not establish superiority over a simple empirical cost table with the same coverage constraints. Test that comparator before a neural model or more regression features.

Two distinct purposes are currently mixed in one exploration quota: gathering enough timing observations, and keeping mathematically different regions represented. Timing measurements may stabilize quickly while unknown solution density still justifies broad geometric coverage. Specify those budgets separately.

The past model/exploration throughput ratio is descriptive. Their contexts, batches and measurement times differed, and the scheduler was deterministic. It does not supply randomized action probabilities for an unbiased counterfactual comparison. Future bounded policy experiments should use known assignment probabilities or matched blocks with preserved arithmetic ownership, then log timing and coverage completely. Off-policy estimators are an option once their assumptions and action support hold; they cannot reconstruct missing solution labels. This is the distinction addressed by [Dudik, Langford and Li, Doubly Robust Policy Evaluation and Learning](https://arxiv.org/abs/1103.4601).

## Check discovery relevance separately

One future test should compare sampler-selected roots with all roots in manageable divisor shells, conditioning on exactly the same local filters. This probes arithmetic and unit-shape selection bias; it is not by itself a test of solution yield. Another should freeze the proposal weights and replay known solutions with whole targets and higher heights held out. Historical discovery catalogues are biased samples, so a positive result would be evidence for transfer, not a probability guarantee for 114.

Additional local-density weights are mathematical hypotheses until their normalization is justified after the filters already applied. Counting many sieve survivors or tiny square residuals does not automatically supply a better reward. Rejected candidates can train runtime and rejection-cost models; absence alone cannot label neighboring unseen candidates as impossible.

## Avoid rediscovering established methods

The reference [Booker–Sutherland implementation](https://github.com/AndrewVSutherland/SumsOfThreeCubes) is an essential comparison for root-first enumeration and CRT/sieve work. Its associated [paper](https://arxiv.org/abs/2007.01209) already reports several algorithmic improvements and large distributed searches. A new wrapper or allocator should not be advertised as a new arithmetic breakthrough.

[Grantham–Walsh](https://arxiv.org/abs/2211.12149) provides the norm/elliptic alternative behind our generator approach; it does not supply a successful prediction method for 114. A lattice basis adapted to the complex-cancellation tube is a plausible way to reduce enclosing-box waste. LLL short vectors alone are only selected proposals: completeness requires enumerating every lattice point in certified cells, including their boundaries.

Root-first CRT is a valuable control because it constructs admissible roots without relying on these coefficient shapes. It still faces an enormous divisor range. Restricting D to easy factor families creates another selective sampler, not a proof of favorable solution density.

A fixed signed pair sum S yields an elliptic curve through the exact relation `3*S*w^2=456−4*z^3−S^3`, with w=x−y. Complete integral-point information can settle every z on that fiber. Merely failing to find points cannot. At large S, certificates can cost more than direct checking; at small S they may add little unsearched opportunity. [PARI documentation](https://pari.math.u-bordeaux.fr/dochtml/html/Elliptic_curves.html) distinguishes bounded searches and the stronger rank/basis information required for such arguments.

[Elkies' lattice approach](https://arxiv.org/abs/math/0005139) is another substantive alternative, but its attractive complexity statement for a broad residual range does not imply a fast fixed-residual-114 search at frontier heights. Rational parametrizations, Pell/Thue special families, or a seed construction require a concrete integral 114-compatible family before they warrant a search budget.

## Gates before another production run

After explicit user permission to resume experiments:

1. Freeze exact domain definitions and baseline policies before observing benchmark results.
2. Demonstrate unchanged accepted candidate sets on finite exhaustive oracles for any new exact filter or traversal. Preserve independent integer verification and interruption recovery.
3. Benchmark arithmetic changes on matched work and report full pipeline cost, including setup, memory and controller overhead. Preregister a material gain threshold and retain the baseline if it fails.
4. Evaluate proposal diversity, root-distribution bias and known-solution recovery separately from raw throughput. Match geometric coverage constraints in policy comparisons.
5. Only then decide the next search geometry and compute allocation. A new run must preserve completed coverage or explicitly account for overlap.

No proposed experiment was run, and there is no performance forecast in this document. These are ranked design hypotheses and ways to falsify them before spending further search time.
