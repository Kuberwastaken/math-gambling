# A campaign that accumulates exclusions and tests search hypotheses

**Decision:** build a search with a proof-based exclusion layer and an experimentally evaluated scheduling layer. Do not train a solution predictor solely on the failed 114 samples. The first layer can remove candidates permanently; the second may reorder work but cannot certify that skipped regions are empty.

**Historical design, followed by an implemented campaign:** the current controller and a two-hour four-worker run now exist; see [CAMPAIGN_RUNBOOK.md](CAMPAIGN_RUNBOOK.md). This document preserves the research rationale and proposed gates. Do not interpret all proposed features below as implemented. In particular, coverage accounting uses exact generator-index tiles and quotient bands, not a global interval ledger for every distinct curve. Discovery enrichment remains unestablished. The measured four-worker calibration supersedes this draft's two-worker default.

## What a failure means

The equation is deterministic. For example, cubes modulo 9 are 0, 1 and −1. Since 114 is −3 modulo 9, every coordinate must be 2 modulo 3. This excludes infinitely many triples with a short proof. This is a familiar restriction already used in the search, not a new result.

A failed square test at one `(D,z)` certifies only that candidate. A nonsquare residue modulo a prime excludes every candidate with the same relevant residue signature. A completed finite search certifies its precise finite domain if the implementation and coverage are verified. A complete integral-point computation can sometimes exclude an entire curve, including arbitrarily large coordinates; a bounded `hyperellratpoints` call cannot do that.

[Booker–Sutherland](https://arxiv.org/abs/2007.01209), especially §§3–5, already exploits modular and reciprocity restrictions, dynamic auxiliary-prime selection and optimized search geometry. Remark 3.8 reports all-height exclusions for small pair sums, distinguishing unconditional results from results conditional on GRH. These are evidence that analytical pruning is possible, not evidence that an inexpensive extension to the current frontier exists.

The existing 114 pilots offer useful timing and filter statistics but almost no established information about which unsearched region contains a solution. Under an illustrative Poisson model, a block with expected count λ=0.01 is empty with probability exp(−0.01)≈99%. Its failure barely challenges that model. We do not currently have calibrated λ values for the norm sampler. A run of failures does not imply nearby candidates are bad or that a different ideal class is due for a success.

## Domains and accounting

Replace random samples as the primary progress measure with deterministic work units. For finite curve work, a unit is `(k, D, r, q_low, q_high)`, with `z=r+Dq` and `r³=k mod D`. Store disjoint integer quotient intervals for each exact `(D,r)`, not just seeds or a count of visits. Candidate generation may remain selective; completeness of checked intervals does not imply completeness of the set of generated curves.

Store four distinct outcomes:

1. **Checked empty:** exact bounds, algorithm/source version and a completed work record. This is a computational exclusion; a log hash alone is not an independent proof.
2. **Proved impossible:** a checkable modular certificate or a mathematically justified whole-family exclusion, with assumptions recorded.
3. **Not yet checked:** includes work omitted by sampling, unsupported cases and interrupted batches.
4. **Solution:** coordinates, arbitrary-precision cube verification and independent reproduction.

A Bloom filter may accelerate lookup, but a positive Bloom result must be confirmed against exact records before work is skipped. Approximate duplicate detection must not silently create coverage holes. In a campaign that spans many curves, storing a record for every sampled curve is itself a serious cost; larger deterministic tiles and streamed residue masks should be evaluated before committing to hundreds of millions of records.

## Learning that is immediately defensible

Measure the conditional rejection rate and execution cost of each modular filter. Reorder filters or choose prime sets to reduce total time, using measured costs after earlier filters rather than assuming independent rejections. Tune native versus GP checking as the quotient interval grows. Detect repeated curve generation and compare cost per newly checked interval. These optimizations need no known solution of 114 and do not change the valid solution set.

Every learned exclusion must be checked independently of the learning process. For a proposed finite modulus, enumerate the relevant residue classes exhaustively or prove the modular identity. A pattern observed in samples may guide scheduling, but it must not become a permanent exclusion without such verification.

Performance gains must include generation, duplicate accounting, sieving and final verification. Fewer surviving candidates alone is not a success metric: it can indicate either a useful filter or a region with fewer solutions.

## Learning where to search is a separate experiment

The specific hypothesis suggested by [Grantham–Walsh](https://arxiv.org/abs/2211.12149) is that searching small algebraic norm generators may find solutions efficiently. The field computation for 114 supplies three class-clearing lattices, but not a proven distribution of solution-bearing ideals among coefficient shapes.

Use the existing known-solution data to create a discovery benchmark:

- Split by entire value of k, so related curves from the same equation do not leak between training and evaluation.
- Predeclare comparable coordinate bounds and identical compute budgets. Use ranges where reference coverage is documented, rather than treating an arbitrary catalogue as an exhaustive negative dataset.
- Supply only k and the search bounds to the candidate generator. Keep the known coordinates, pair sums, roots and generator representations hidden from it.
- Measure blind discovery time, known-solution recall within the domain, exact coverage and total processing time. Treat failures within a fixed budget as censored observations, not evidence of impossibility.
- Compare with a fixed policy using the same backend to isolate any scheduling advantage. A separate comparison against an optimized published implementation is required before claiming an improvement over the state of the art.
- Freeze the policy before evaluating held-out k values and larger held-out heights. Catalogue discovery biases and transfer from other cubic fields to 114 remain limitations even if the benchmark succeeds.

Our existing 662 known-curve tests validate the checker. They do not satisfy this blind-discovery benchmark. The small blind search for 6 is a pipeline test, not sufficient training or evaluation evidence.

## Bounded Mac stages and decisions

These are proposed work budgets, not measured completion estimates or a scheduler configuration. Keep two workers by default.

**Stage A — establish coverage accounting.** Implement deterministic finite tiles and interval merging. Test interrupted/resumed runs and compare small complete domains against independent exhaustive enumeration. The gate is exact agreement and no skipped intervals. Stop if tracking overhead defeats useful throughput; redesign the work units before scaling.

**Stage B — adapt the sieve.** Use short training batches followed by independent benchmark batches across pair-sum scales and quotient lengths. Keep the fastest correct filter policy per workload range. The gate is reproducible end-to-end improvement, including controller overhead; the existing fixed filter order remains the baseline. This is engineering progress, not a solution-density claim.

**Stage C — test candidate enrichment.** Start with a fixed two-hour compute allowance for a small blind benchmark, expanding only if it produces enough discoveries to make comparisons meaningful. If there are too few successes, report insufficient evidence. Do not fit a flexible model to a handful of outcomes. Record a preference for a search family only when it survives held-out evaluation; distinguish empirical scheduling weights from probabilities of solving 114.

**Stage D — finite 114 campaign.** Use the validated controller in bounded sessions with exact accounting. Preserve a predeclared exploration allocation across the chosen classes, shapes and scales so an uncertain policy cannot permanently starve them. Record excluded finite domains and cost gains after each session. Any full-curve exclusion is a separate mathematical computation whose completeness and assumptions must be checked. Sampled curves or heuristic rankings never certify that a whole coefficient or height region is empty.

Continue a large discovery campaign only if there is a demonstrated gain in useful coverage or a repeatable blind-discovery advantage. Otherwise, the appropriate output is a better exclusion algorithm and a failed enrichment hypothesis, not an inflated success forecast.

## What cannot presently be promised

Finite exclusions shrink a specified finite domain. They do not shrink the entire unbounded integer problem into a known finite remainder: no usable upper bound for a solution of 114 is available here. An exhaustive expanding algorithm would eventually find a solution if one exists; it need not halt if none exists.

There is no proof that the surviving candidates are intrinsically random or that a much better algorithm is impossible. Conversely, randomness-like density heuristics and successful performance tuning do not establish that a Mac will find a solution. The campaign's scientific value is that each run either adds verifiable exclusions, improves an independently tested algorithm, or provides an interpretable test of a search hypothesis.

## Additional literature: direct optimization attempts

A subsequent targeted search found a more direct precedent: Boian Lazov and Tsvetan Vetsov, *Sum of Three Cubes via Optimisation* ([2020 preprint](https://arxiv.org/abs/2005.09710)), and their [2023 published article](https://www.inderscience.com/info/inarticle.php?artid=131357), *A new dispersive flies optimisation algorithm for the sum of three cubes*. The published experiments compare a modified swarm-style optimizer with two simulated-annealing methods for k=2. The full-text experiment bounds for x and y are 10³, 10⁴ and 10⁵ (equation 3.8). This is direct evidence that guided stochastic optimization has been tried, but not evidence of competitive performance at the 114 frontier.

Geometric search also has substantial precedent: Elkies' method, implemented by [Elsenhans–Jahnel](https://wwwuser.gwdguser.de/~jjahnel/linkstopaperse.html), partitions a thin region near a real cubic curve and uses lattice reduction and bounded lattice enumeration. Thus the campaign should benchmark against established structured algorithms, not frame existing research as random sampling.
