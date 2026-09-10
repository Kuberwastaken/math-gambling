# Can learning navigate the three-cubes search?

**Verdict: actual blind discovery works in this small benchmark; learned navigation has not earned promotion to the 114 search.** A policy learned on smaller problems tied a uniform mixture on unseen targets and larger norm shells. Both mixtures discovered the same exact solution for the unseen target 69 in both random seeds. The best single training family missed it. This is evidence for maintaining a portfolio, and a counterexample to simply carrying the training winner to a larger scale. It is not evidence that the learned mixture predicts where 114 has a solution.

The experiment used one additional native process at a time, 28.82 aggregate extra CPU-seconds and 31.49 wall-seconds. Production files and their recorded hashes remained unchanged. The result and its limitations are reproducible from [the experiment script](discovery_experiment.py), [native sampler](discovery_worker.c), [raw results](discovery_results.json), and [the analysis script](discovery_analyze.py). The [recorded policy](discovery_frozen_policy.json) was frozen before holdout runs. The [analysis JSON](discovery_analysis.json) disables discovery learning.

**What was tested.** The target rule selected every cube-free integer from 3 through 240 congruent to 3 or 6 modulo 9, excluding 114: 46 targets. A fixed SHA-256 rule split entire targets into 27 training and 19 held-out cases. No known solution coordinates, pair sums, modular roots, or generators were supplied to the sampler. The reference catalogue was opened only after all search runs ended. This is blind candidate generation, although its designers have studied earlier catalogues and benchmarks; it is not an independently sealed benchmark untouched by prior research.

For each target \(k\), write \(\alpha=\sqrt[3]{k}\). Four families proposed integer coefficients \(a,b,c\): a cube, a box balanced by the powers of \(\alpha\), a strip near real cancellation, and a tube near complex cancellation. Specifically, for radius \(A\) and \(w=\max(1,\lfloor A/4\rfloor)\):

| Family | Proposal |
|---|---|
| Cube | Independent \(a,b,c\in[-A,A]\) |
| Balanced | \(a\in[-\lceil A\alpha^2\rceil,\lceil A\alpha^2\rceil]\), \(b\in[-\lceil A\alpha\rceil,\lceil A\alpha\rceil]\), \(c\in[-A,A]\) |
| Real strip | \(b,c\in[-A,A]\); \(a=-\operatorname{round}(\alpha b+\alpha^2c)+u\), \(u\in[-w,w]\) |
| Complex tube | \(c\in[-A,A]\); \(b=\operatorname{round}(\alpha c)+u\), \(a=\operatorname{round}(\alpha^2c)+v\), \(u,v\in[-w,w]\) |

The native worker computes the integer norm

\[
N=a^3+kb^3+k^2c^3-3kabc,
\qquad D=|N|,
\qquad r=(kc^2-ab)(b^2-ac)^{-1}\pmod D.
\]

It requires the inverse to exist and independently verifies \(r^3\equiv k\pmod D\). Within a run it checks each distinct \((D,r)\) once, using the frozen exact checker. Floating point only proposes integer coefficients; it makes no exclusion or acceptance decision. Python independently verifies every returned cube identity, norm, modular-root identity and shell membership. Eight small generator-validation cases also check sampled norm arithmetic.

Training used \(A=8\) and \(1<D\le1000\). Larger-scale tests used \(A=32\) and the disjoint shell \(1000<D\le10^6\). All arms used the same \(R=128\), retaining solutions with \(\min(|x|,|y|,|z|)\le128D\). The primary threshold was \(H=\max(|x|,|y|,|z|)\ge10\); \(H\ge1000\) was a harder secondary measure. Lowering the primary threshold was an explicit response to the earlier benchmark's zero qualifying held-out hits. It enables a learning diagnostic, while weakening transfer to the frontier.

The four pure families were run on training targets with two seeds. Their actual qualifying discovery rates selected the balanced box. The learned mixture used 40% uniform proposal probability plus 60% smoothed training discovery-rate weights. Its frozen probabilities were 22.8652% cube, 31.3399% balanced, 28.2947% real strip and 17.5002% complex tube. This is a small categorical learning rule, not a trained posterior over 114's solutions. The uniform mixture and best training family were actually run on holdouts; their results were not inferred by replaying a learned trajectory.

**The observed discoveries.** Entries below count distinct \((k,\{x,y,z\})\) solutions, with repeated per-seed discoveries in parentheses. Repetition under another seed is not another independent mathematical discovery.

| Holdout | Uniform mixture | Learned mixture | Best training family |
|---|---:|---:|---:|
| Unseen targets, small shell | 5 (10) | 5 (10) | 5 (10) |
| Training targets, larger shell | 1 (2) | 1 (2) | 1 (1) |
| Unseen targets, larger shell | 1 (2) | 1 (2) | 0 (0) |

In the most relevant joint holdout, both mixtures independently generated and exactly checked

\[
(-1213102)^3+261692^3+1209029^3=69.
\]

Its \(D=4073\) and \(r=1020\) were discovered by the sampler. They were not inputs. The balanced family missed this solution in its two bounded runs; this does not prove it is absent from every balanced coefficient box. On the larger-shell training-target tests, the mixtures found the same \(k=159\) solution, whereas the balanced family found a different solution for \(k=12\). Thus the result is not simply one policy uniformly dominating every other policy.

The locally recorded promotion rule required at least 10 qualifying joint-heldout discoveries and at least 1.10 times uniform discovery per CPU-second in each seed. It failed even if the repeated-seed count of two is used instead of the distinct count of one. The two observed learned/uniform rate ratios were 1.000026 and 0.999978. Their tiny differences are timing variation, not meaningful enrichment. There are too few independent positive targets to estimate a reliable effect size or claim equivalence of the methods.

**The fairness limitation matters.** Each run had the same 0.055-second CPU ceiling and one-million-attempt ceiling, but 391 of 606 runs reached the attempt cap first. This produced unequal actual CPU allocations. For example, the small-shell target holdout used 1.096 CPU-seconds for the balanced family, 1.700 for the learned mixture and 1.734 for the uniform mixture. Calling these equal-compute runs would be wrong. The larger-shell joint holdout used 1.304, 2.090 and 2.090 seconds respectively. Actual costs and all attempt/rejection counters are preserved.

A post-experiment sensitivity analysis used only the common observed CPU prefix for each matched target and seed, censoring timestamped hits beyond the shortest run. It performs no new search and does not retrain the policy. All held-out discovery counts in the table survive this equal-prefix comparison. However, the apparent training winner is sensitive to how cost is compared: the real strip has six repeated training discoveries versus five for the balanced box within common prefixes, whereas actual total discovery/CPU selected balanced. The training ranking should therefore not be treated as stable.

Finite proposal domains also become saturated. In small-shell training, duplicate \((D,r)\) roots account for 98.3% to 99.98% of otherwise admissible repeated proposals, depending on family. There were 537,362,880 coefficient attempts but only 4,122,078 within-run unique root curves across the entire experiment; the latter still overlap across seeds and policies. Much measured cost is resampling or rejecting the same tiny domain. This is a diagnostic of this sampler, not evidence about an optimized enumeration of new frontier curves. The attempt cap should be replaced by genuinely matched CPU or a precisely declared finite coverage comparison in the next benchmark.

**What does and does not transfer.** Whole-target and disjoint-\(D\)-shell holdouts are stronger than withholding random known solutions from a common target. They still leave enormous distribution shifts: these are small \(k\), small generators and relatively abundant solutions. The sampler uses principal norms only; it does not uniformly sample root ideals or reproduce all class-clearing families used for 114. Its four coefficient regions overlap, and unit-equivalent generators can map to the same curve. There is no completeness claim for a height box, a norm shell, or the integer equation.

The post-search catalogue comparison is only an audit. A catalogue preferentially contains solutions found by earlier methods and selected heights; absence from it is not a negative label. Even a listed solution within the \(D,R,H\) bounds need not have a generator in the specified finite coefficient domain. Dividing discoveries by that catalogue count would not yield population recall. Nor does this experiment compare against an optimized Booker–Sutherland search or establish that random norm sampling is the best use of a Mac-hour.

**The primary literature does support heuristic search, with narrower evidence than a promise for 114.** Boian Lazov and Tsvetan Vetsov's 2020 *Sum of Three Cubes via Optimisation* minimizes the distance of \((k-x^3-y^3)^{1/3}\) to the nearest integer. It compares modified swarm search and simulated annealing on \(k=2\), with coordinate ranges extending to \(10^5\), and measures time to a solution. It supplies actual discovery experiments, not just a proposal. It does not supply an unseen-target or frontier-height comparison establishing transfer to 114. [2020 primary paper](https://arxiv.org/abs/2005.09710).

Their 2023 follow-up, *A new dispersive flies optimisation algorithm for the sum of three cubes*, introduces modified dispersive-flies search, dispersion, memory and restart-like behavior, again testing \(k=2\). It explicitly requires checking a rounded candidate in the original equation. Its appendix implements coordinates as C `int` and cube evaluation with `double` `pow`/`cbrt`; that implementation must change for frontier coordinates. This is not a claim that their small-range results are wrong. The comparison is against annealing variants, and the paper presents searches above \(10^{20}\) as future work. Neither runtime-distribution fitting nor a restart advantage on this one dense target establishes a success probability for 114. [2023 publisher full text, especially §3.2, §6 and appendices](https://www.inderscience.com/filter.php?aid=131357).

The numerical issue can be stated exactly. For an integer \(n\), \(n^3\pm1\) differs from \(n^3\) by one, while its real cube root differs from \(n\) by approximately \(1/(3n^2)\). At \(n\approx10^{18}\), even resolving that root distance can require roughly 180 binary significant bits, plus a safety margin. Ordinary binary64 does not even represent every integer at that scale. A very small root-distance score is therefore neither a certified solution nor evidence that nearby integer coordinates will work. Arbitrary-precision integer cube checks or certified root intervals are required. This is an arithmetic observation, separate from the empirical question of whether the score can guide useful proposals.

The \(k=2\) choice is also mathematically special. For example, direct expansion gives

\[
(1+6t^3)^3+(1-6t^3)^3+(-6t^2)^3=2
\]

for every integer \(t\). This explains why success on such a target cannot by itself justify extrapolation to an unresolved sparse target. It does not imply the optimisation papers fed this family to their algorithms.

Eldar Sultanow, Max Henkel and Idriss J. Aberkane's *Diophantine imaging reveals the broken symmetry of sums of integer cubes* maps numerical prefixes into geometric images. Its datasets include cubic quadruples below \(10^6\) and a sums-of-cubes catalogue searched to \(10^{14}\), with differing exclusions. It reports visual patterns and suggests future clustering, base selection and mathematical explanations. It does not demonstrate held-out discovery acceleration or prove that visually empty prefix regions exclude integer solutions for 114. Height, sign, catalogue and representation choices can generate apparent patterns; such features need controlled holdouts before use as priors, and a theorem before use as permanent exclusions. [2024 primary article](https://www.nature.com/articles/s41598-023-49960-y).

Jordan S. Ellenberg, Cristofero S. Fraser-Taliente, Thomas R. Harvey, Karan Srivastava and Andrew V. Sutherland provide stronger evidence that learned priorities can help some mathematical searches. Their *Generative Modeling for Mathematical Discovery* evolves priority functions while keeping a rigorous evaluator fixed, with benchmarks in cap sets, admissible tuples and no-isosceles grids. Some priorities generalize to larger grids. These tasks have graded, exact objectives such as valid-set cardinality; their paper does not establish a three-cubes navigator. The transferable engineering principle is to constrain generated proposals with a fixed exact checker and test generalization. The missing scientific ingredient here remains a discovery-relevant training signal. [2025 primary paper](https://arxiv.org/html/2503.11061).

Cross-entropy methods adapt sampling distributions and can efficiently estimate rare-event probabilities. That is a serious possible research direction, rather than proof that arbitrary rare integer solutions admit the same acceleration. [D. P. Kroese, R. Y. Rubinstein and P. W. Glynn, *The Cross-Entropy Method for Estimation* (2013)](https://web.stanford.edu/~glynn/papers/2013/KroeseRubinsteinG13.html). Recent Safe-ICE work uses intermediate failure regions, parametric mixtures, importance weights and a heavy-tailed exploration component to handle rare-event geometry. Its probability interpretation relies on a specified distribution and correct weighting. For 114, a useful hierarchy of intermediate scores must first be shown to concentrate exact solutions. Keeping exploration support is sensible; importing engineering-reliability speedups or confidence intervals without that validation is not. The categorical mixture tested here is not an importance-sampling probability estimator. [Zhiwei Gao and George Karniadakis, *Safe cross-entropy-based importance sampling for rare event simulations* (2025 preprint)](https://arxiv.org/html/2509.07160).

**What to apply now.** Keep exact exclusions, exact duplicate accounting, normalized geometric diversity and measured cost learning. Do not enable a learned solution-location model from this experiment. The training-best counterexample argues against permanently starving a family because its recent sample produced no hits. A [separately timed modular improvement](normalized-sieve-benchmark.json) in this research pass removed 33.5% of exact tests but changed CPU time from 8.664 to 8.733 seconds across 81 contexts; it was not promoted on that small, contention-limited result. Fewer survivors is a surrogate, and can fail to buy more useful search per hour.

A credible next discovery benchmark would compare normalized, deduplicated finite generator blocks with an optimized root-first baseline; retain entire-target and disjoint-scale holdouts; match actual CPU and report full preprocessing costs; and count distinct target-solutions with uncertainty clustered by target. It should reserve a fresh final holdout after any design changes. A positive result at that stage would justify a bounded exploratory allocation, with continued diversity, before any strong claim about 114. The present experiment supplies working instrumentation and an honest failed promotion gate. It supplies no estimate that learning will solve 114 in hours.
