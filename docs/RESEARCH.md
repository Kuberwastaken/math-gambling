# The mathematical search for 114

The objective is an integer identity

\[
x^3+y^3+z^3=114.
\]

The archived campaign has not found one. Its contribution is a reproducible, specialized search with exact arithmetic, explicit finite domains, measured optimizations, durable discovery handling and retained negative results. It is not a proof that 114 is impossible or a promise that a local search will finish with a solution. The public Mac data is a timestamped observation of a separate native campaign; see the [archive and snapshot guide](ARCHIVE.md).

**The central reduction removes two search dimensions.** Set \(s=x+y=\sigma D\), with \(D>0\), and \(v=x-y\). Then

\[
3sv^2=4(114-z^3)-s^3,\qquad z^3\equiv114\pmod D.
\]

Once a divisor \(D\), a root \(r\pmod D\), and a sign have been selected, write \(z=r+qD\). Modular tests eliminate impossible quotient residues; a final exact square and parity check recovers \(x,y\). The definitive acceptance test cubes the integer coordinates and sums them exactly. A small residual computed in floating point is insufficient at these heights.

Booker–Sutherland supplies the strongest established reference for broad divisor/root coverage: recursive admissible prime-power generation, cached cube roots, CRT enumeration, local and reciprocity conditions, auxiliary-prime sieving and measured optimization of the divisor/coordinate ratio. Its reported 2019 search reached minimum coordinate \(10^{17}\); subsequent work used \(z_{\max}=10^{19}\) and \(D_{\max}=10^{19}/54\). A separate completed-shard manifest for 114 is not available in this repository. [Booker–Sutherland](https://arxiv.org/abs/2007.01209), [reference implementation](https://github.com/AndrewVSutherland/SumsOfThreeCubes)

**The local campaign uses cubic-field norms to select large roots cheaply.** For \(\alpha^3=114\),

\[
N(a+b\alpha+c\alpha^2)=a^3+114b^3+12996c^3-342abc.
\]

With \(A=a^2-114bc\), \(B=114c^2-ab\), \(C=b^2-ac\), an appropriate generator gives \(D=|N|/\ell\) and \(r=B/C\pmod D\) when the required inverse exists. This avoids factoring each enormous divisor. The field calculation certifies an integral basis, a class group of order3, and representatives cleared by \(\ell=1,5,25\). These options support every ideal class, while finite coefficient domains still reach only selected generators. [Field and unit analysis](../research/archive/unit_shape_proposal.md)

Walsh and Grantham–Walsh motivate this norm approach and its conversion to integral points on elliptic curves. Small norm generators exist for several known large representations. Those retrospective examples motivate exploration but do not establish that small generators predict a new solution. Their accessible preprint explicitly reports an unsuccessful effort on114. [Grantham–Walsh](https://arxiv.org/abs/2211.12149)

Phase2 and phase3 use81 fixed contexts: three class multipliers, three coefficient/offset shapes, three norm shells and three quotient bands. Their domains have exact integer definitions. Certified unit bounds and ideal ownership exclude duplicate \((D,r,z)\) positions across completed domains, subject to the stated field hypotheses and correctly executed ledger. A finite band is excluded only by a mathematical impossibility test or by completed exact checking. [Domain proof](../research/archive/phase3/DOMAIN_PROOF.md), [nonoverlap certificate](../research/archive/NONOVERLAP.md)

The optimized backend solves exact monotonic cubic intervals for fixed coefficient rows, advances norms by recurrences, batches modular checks and defers expensive arithmetic until necessary. The phase3 release preserves prior completed jobs and resets timing calibration rather than mathematical coverage. Historical known-solution, oracle, sanitizer, migration and fault-injection evidence is preserved with source hashes. Noninvertible root coefficients and unsupported divisor sizes remain counted as unresolved inputs. [Phase3 implementation and validation](../research/archive/phase3/README.md), [independent safety review](../research/archive/phase3/SAFETY_REVIEW.md)

| Direction | Decision and evidence | Remaining limitation |
|---|---|---|
| Norm generation plus exact sieve | Selected for local exploration; working source and large measured throughput | Selective root coverage; success probability uncalibrated |
| Root-first CRT enumeration | Retained as mathematical and performance reference | Full frontier extensions exceed a modest local budget |
| Exact shell inversion and residue wheels | Adopted where matched tests preserve candidate results | Speedups depend on the workload; no automatic discovery enrichment |
| Complete elliptic-curve solving | Useful for limited certified exclusions, not every generated root | An empty bounded point search is not an all-height proof |
| Normalized unit-phase coverage | Promising next geometry design | Equal phase width is not equal root or solution mass |
| Conditional-throughput cost model | Used to allocate work after a held-out gate, with exploration retained | It predicts cost/exposure, not where a solution exists |
| Learned discovery proposal mixtures | Tested independently; advancement gate failed | The joint held-out experiment did not outperform its uniform comparator |
| Direct stochastic residual minimization | Rejected as the frontier engine | Published small-coordinate demonstrations do not justify114-scale efficacy |
| More elaborate lattice search | Research alternative, not a proven local replacement | Higher-dimensional setup cost and enormous residual work |
| Seed parametrizations | Useful for suitable known families | Missing-seed cases retain the integer-search difficulty |

The local performance evidence is mixed rather than uniformly positive. A phase3 replay of the actual allocation improved elapsed throughput by about 1.578×, while a workload dominated by long quotient bands stayed near parity. The normalized-divisor sieve prototype was examined separately and its result remains a prototype decision, not silently part of the frozen running binary. [Phase3 performance](../research/archive/phase3/PERFORMANCE.md), [normalized-sieve evidence](../research/archive/research-2026-09-09/normalized-sieve/README.md)

**Learning cost is different from learning discovery.** The controller's reward is conditional root-exposure throughput. A fast arm can earn a high reward without containing a solution. Its historical holdout checks test that proxy; neither a correlation nor a top-quartile proxy improvement is a success probability. The separate discovery experiment held out whole targets together with a larger divisor range. It found a known \(k=69\) solution under both seeds with both the learned and uniform mixtures, while the training-best fixed mixture missed it. The learned mixture did not demonstrate superiority, so its advancement gate failed. [Discovery-learning review](../research/archive/research-2026-09-09/DISCOVERY_LEARNING.md), [preregistered protocol](../research/archive/research-2026-09-09/discovery_preregistered.json), [analysis](../research/archive/research-2026-09-09/discovery_analysis.json)

The same distinction applies to attractive external examples. Published swarm-style three-cubes studies concentrate on small-coordinate \(k=2\) demonstrations; exact frontier arithmetic and blind 114 performance remain unestablished. Generative-priority search has produced real results in other mathematical settings, but its transferable success depends on useful intermediate rewards and held-out validation. It supplies no theorem that a zero-hit 114 search can infer fertile neighboring regions. The detailed review retains sources, applicability checks and rejected claims. [Discovery-learning literature assessment](../research/archive/research-2026-09-09/DISCOVERY_LEARNING.md)

Elkies' basic lattice method is efficient for rational points close to curves and has a strong history for searching many residual values simultaneously. Huisman's implementation reached the \(10^{15}\) height scale and found 966 new representations, including 74. A higher-order Elkies proposal improves the heuristic exponent to \(N^{12/13}\), but requires rank-six lattices and lacks a demonstrated frontier implementation. It does not yield a credible hours-scale complete search here. [Elkies](https://arxiv.org/abs/math/0005139), [Huisman](https://arxiv.org/abs/1604.07746), [algorithm comparison](../research/archive/research-2026-09-09/ALGORITHM_REVIEW.md)

**Global density estimates do not calibrate the finite sampler.** The usual conjectural count grows logarithmically with height. Under an additional Poisson model and a complete, similarly shaped divisor expansion by a factor 8, the published constant for 114 gives approximately 11.45% chance of at least one new representation. The current coefficient families do not complete that expanded region, so that percentage is not a campaign forecast. A time estimate for exhausting selected rows is also not an estimate of time to a solution. [Booker–Sutherland, density and shape analysis](https://arxiv.org/abs/2007.01209), [Browning–Wilsch](https://link.springer.com/article/10.1007/s00029-025-01074-1)

The strongest next improvement would either prove a useful new exclusion that saves substantial work, or validate a structural feature that enriches solution-bearing roots on genuinely held-out targets and scales. Until then, the defensible objectives are exact coverage, lower verified cost per covered region, diverse mathematical domains, and retention of every verified discovery that reaches durable storage. Hardware failure before a completed durable write remains outside any absolute retention guarantee.

The full [research verdict](../research/archive/research-2026-09-09/SEARCH_VERDICT.md), [geometry review](../research/archive/research-2026-09-09/GEOMETRY_REVIEW.md), [algorithm review](../research/archive/research-2026-09-09/ALGORITHM_REVIEW.md), and [discovery-learning review](../research/archive/research-2026-09-09/DISCOVERY_LEARNING.md) preserve the detailed reasoning and citations. The [archive manifest](../research/archive/ARCHIVE_MANIFEST.json) identifies the source and evidence versions behind those reports.
