# A practical search strategy for three cubes summing to 114

**The best-supported choice on this Mac is the existing cubic-field norm search with exact modular sieving, disjoint work allocation, and learning restricted to execution cost.** The literature review and new experiments did not establish a faster replacement or a model that predicts solution-bearing regions. The 12-worker phase3 campaign therefore remains active with its existing coverage ledger and hourly monitoring. No representation of 114 has been found.

Two concrete challengers were built and tested. A stronger square sieve eliminated 33.5% of the remaining exact tests but provided no measured overall speed improvement. A coordinate-blind discovery experiment found a real held-out solution for 69, yet its learned mixture did essentially no better than a uniform mixture. These results support retaining the validated implementation and its exploration allocation. They do not support promising a solution in hours.

The most promising next mathematical development is a systematic search across cubic-field embedding shapes, especially a rigorously bounded complex-cancellation tube. That is an implementable geometric proposal, with explicit equations and validation requirements, rather than an established faster algorithm. It is not silently substituted for the current search.

## The computational problem

There are three separate objectives: find one integer triple, exclude every triple in a declared finite region, and forecast the time to discovery. The first needs only one exact witness. The second needs complete enumeration and sound exclusions. The third additionally needs a justified model of where solutions occur. Fast progress on enumeration does not automatically supply such a model.

For a bounded coordinate box, a terminating search is straightforward in principle. For unrestricted 114, the literature examined supplies neither an effective small search bound guaranteed to contain a solution nor a short-time algorithm guaranteed to find one. This is a limitation of current knowledge. It is not a proof that faster algorithms cannot exist. General undecidability results for arbitrary Diophantine equations also do not establish undecidability of this particular equation.

The published norm-search paper explicitly reports substantial unsuccessful work on 114. More recent algorithm and density papers examined did not provide a verified representation or a demonstrated hours-scale solution method.[^1] The absence of a newly located announcement is not an independently audited global search-completion certificate.

The exact arithmetic already gives strong structure. Set

\[
S=x+y=\sigma D,\quad D>0,\quad \sigma\in\{-1,1\},\quad V=x-y.
\]

Since \(4(x^3+y^3)=S^3+3SV^2\), any solution satisfies

\[
3SV^2=4(114-z^3)-S^3,\qquad z^3\equiv114\pmod D.
\]

For each admissible root \(r\pmod D\), write \(z=r+Dq\). Searching three unrestricted coordinates has become generating suitable pairs \((D,r)\), followed by a one-dimensional search for an integral square. Parity then determines whether \((S+V)/2\) and \((S-V)/2\) are integers. The final three cubes are evaluated exactly.

There is also an immediate congruence constraint: cubes modulo 9 are 0, 1, or −1. A sum of three cubes congruent to 114, hence −3, forces all three cubes to be −1 modulo 9. Consequently every coordinate is 2 modulo 3. More elaborate local tests retain the coupling between the coordinates; they are stronger than filtering each coordinate separately.

This is already an algorithm that removes impossible branches. The unresolved problem is finding a sufficiently cheap additional structure that concentrates genuine solutions among the remaining branches.

## Algorithm comparison

| Approach | What it makes efficient | Decision for this Mac |
|---|---|---|
| Divisor enumeration, prime-power roots and CRT | Complete coverage of declared divisor/coordinate rectangles | Keep as a reference and future bounded comparator; do not repeat the whole historical region |
| Cubic-field norm generators | Reaching selected large divisors without factoring each one | Retain as the production generator |
| Geometric lattice reduction | Finding near-cancelling cubes, often across many target values | Valuable established method; no demonstrated replacement advantage here |
| Higher-order lattice embedding | A proposed modest improvement in the height exponent | Research lead, not a practical Mac implementation |
| Complete integral-point algorithms | Potentially excluding an entire fixed elliptic curve | Use only in separately bounded experiments where completeness can be certified |
| Simulated annealing, particle swarms and related optimization | Searching a numerical objective on chosen finite domains | No evidence supporting promotion at the 114 frontier |
| Learned proposal selection | Adapting a search distribution from observed outcomes | Retain diversity; no discovered high-height fertility model |
| SIMD/GPU or more workers | Lower execution cost when arithmetic and batching fit the hardware | Require measured end-to-end gains; no assumed GPU multiplier |

Booker–Sutherland combines prime-power root generation, implicit CRT enumeration, reciprocity restrictions and auxiliary-prime sieving. Its reference implementation partitions work by the largest prime factor of the divisor. The reported 2019 minimum-coordinate frontier is \(10^{17}\); the later parameter rectangle uses \(z_{\max}=10^{19}\) and \(D_{\max}=10^{19}/54\). A separate completed-shard manifest for 114 has not been established here. The paper itself cautions that computation on ordinary machines is not immune to undetected errors.[^2][^3]

The original sandbox timing extrapolates to roughly 270 core-years for that larger rectangle. This is an extrapolation from the supplied benchmark, not a fresh Mac measurement. It explains why a selective high-divisor generator is attractive; it does not predict the runtime or success probability of the current campaign.

For the norm approach, let \(\alpha^3=114\) and \(\gamma=a+b\alpha+c\alpha^2\). Its norm is

\[
N(\gamma)=a^3+114b^3+12996c^3-342abc.
\]

Define \(B=114c^2-ab\) and \(C=b^2-ac\). Direct expansion gives

\[
B^3-114C^3=N(\gamma)(114c^3-b^3).
\]

Thus, when \(D\mid N(\gamma)\) and \(C\) is invertible modulo \(D\), the residue \(r=BC^{-1}\bmod D\) is a cube root of 114. This algebra explains the generator's usefulness without treating a large integer factorization as a prerequisite. The present field-specific class analysis supplies \(\ell=1,5,25\) and \(D=N(\gamma)/\ell\). All-class support does not make a finite coefficient search complete.[^4]

Grantham–Walsh's worked large solution for 3 illustrates how modest generator coefficients can lead to enormous cube coordinates. Its estimates for that example differ between passages and are retrospective; neither estimate is a blind benchmark for 114.[^1] The useful conclusion is that norm representations can reach arithmetic regions that direct coefficient-size intuition would miss.

Elkies' geometric method and its later implementations are serious alternatives, not naive brute force. A higher-order rank-six proposal has heuristic scale \(N^{12/13}\), up to logarithmic factors, for a specified residual window; the original paper says that refinement was not implemented and warns about constants.[^5] Merely substituting \(N=10^{17}\) gives about \(4.9\times10^{15}\) units at the exponent level. That is a scale comparison, not a lower bound, but it supplies no practical hours-scale justification. Huisman's implemented lattice campaign reports slightly above \(10^5\) computation-hours, reaching the \(10^{15}\) height scale across many targets.[^6]

A bounded elliptic-curve point search and a proof that a curve has no integral points are different operations. PARI's `hyperellratpoints` searches a supplied height bound or interval.[^7] Empty output does not eliminate the infinite tail. Applying an expensive general curve solver to every root can spend far more time on setup than the native sieve spends on many candidate intervals. Complete methods remain useful research tools for carefully chosen cases, rather than a justified default at every frontier divisor.

Recent density work develops and tests heuristics for cubic surfaces; it does not establish that any chosen narrow generator shape has the same fertility as a full height region.[^8] Recent function-field results concern polynomials over finite fields, with explicit conjectural assumptions, and do not constitute an integer algorithm for 114.[^9] Seed-based parametrizations can generate further points when a suitable point is already known; the examined missing-seed treatment leaves another integer cubic search rather than a demonstrated complexity improvement.[^10]

## Exact branch elimination and its limits

The production code excludes coefficient intervals outside its norm shell by partitioning the cubic into monotone pieces and locating exact integer endpoints. It then applies signed-sum congruences, modular root requirements, a modulus-243 filter, parity, auxiliary-prime square tests and an arbitrary-precision square test. Periodic residue patterns are processed in batches, and finite differences avoid recomputing a cubic at every coefficient position.[^11]

Each exclusion has a specific scope. A norm-shell exclusion removes coefficients outside that declared shell. A nonsquare residue removes a candidate because an integer square cannot have that residue. A completed tile removes exactly its validated generator positions and quotient intervals from future work. None of these facts implies that a neighboring tile, another unit phase, or the unbounded quotient tail is impossible.

The inverse requirement needs particular care. A failed inverse for an arbitrary generator does not prove that its divisor has no cube roots or no solutions. The exact principalized root-ideal construction has stronger algebraic conditions, but a finite generator program still must record failed inverse inputs separately and avoid describing them as globally excluded solutions. The current ledger does so.

Similarly, an ML score of zero would not be a mathematical exclusion. Statistical scheduling may change when a branch is visited. Only a proved necessary condition or completed exact enumeration can justify marking it dead.

This distinction also explains why an enormous count of rejected values is not by itself progress toward a likely solution. A filter can remove many cheap candidates while costing more than it saves. The new normalization experiment directly tested that possibility.

## A stronger normalized square sieve: built and tested

The ordinary discriminant residue test loses information when an auxiliary prime divides \(D\), because the discriminant includes a factor of \(D\). Dividing the exact equation first restores a necessary condition.

Write \(h=(114-r^3)/D\), which is an integer because \(r\) is a modular root. Expansion gives

\[
3\sigma V^2=4h-12r^2q-12rDq^2-4D^2q^3-\sigma D^2.
\]

For an odd prime \(p\mid D\), \(p\ne3\), reduction therefore yields

\[
V^2\equiv\frac{4\sigma}{3}h-4\sigma r^2q\pmod p.
\]

The right side must be a quadratic residue, including zero. When its slope is nonzero, only \((p+1)/2\) of the \(p\) quotient residues survive. The condition remains necessary when the slope is zero; the rejection rate then need not be approximately one half. This is an elementary derived refinement, not a claim of a new number-theory theorem.

The prototype computes \(h\) without forming \(r^3\). Divide \(r^2=Du+v\), then \(vr=Dw+t\). It follows exactly that

\[
h=(114-t)/D-ur-w.
\]

For \(0\le r<D\le2^{63}-1\), the products fit 128-bit arithmetic. The value is cached only when a dividing prime is encountered. An independent review checked this derivation and its integer bounds.

| Check | Result |
|---|---:|
| UBSan arithmetic inputs, including large divisors and prime powers | 6,236 passed |
| Independent Python modular predicates | 303,312 passed |
| Known-positive fixtures recovered | 662 of 662 |
| Returned hits, each checked by exact cube addition | 665 |
| Production-context timing pairs | 81 |
| Exact tests on the paired workloads | 9,826 → 6,532 |
| Total measured native CPU on those workloads | 8.664 s → 8.733 s |

The timing jobs used one tenth of the latest completed tile in each context, with randomized old/new order and one extra worker while production continued. This is an exploratory, contention-affected comparison, not a precise performance bound. The observed reduction in expensive-test count was real; an overall speed gain was not established. The short, medium and long quotient groups all showed approximately unchanged or slightly worse aggregate CPU time. **The prototype was therefore rejected for production promotion.**[^12]

Its sources, build script, exact validation and paired timing records are preserved. Future changes to the quotient distribution or prime order could alter its value, but that requires another justified benchmark rather than assuming that stronger mathematics must produce faster software.

## Learning where to search

Learning execution cost is feasible because every completed tile supplies a timing and exposure observation. Learning discovery probability is harder because 114 has supplied no positive examples. Many negative results can rule out the exact places already checked without identifying which untouched places are fertile.

The current scheduler reserves 40% of worker time for its declared exploration allocation and uses the remaining 60% to favor measured root-exposure throughput. A contextual regression shares cost information across class, shape, divisor shell and quotient band. The proxy includes a geometric ratio weight and a \(1/D\) exposure factor. Its interpretation as discovery utility requires an additional exchangeability assumption about the selected roots; that assumption has not been learned from the zero-hit campaign.[^13]

For a hypothetical model with known discovery rates \(\lambda_i\) and costs \(c_i\), prioritizing \(\lambda_i/c_i\) would make sense. Here the cheap quantity is a proxy for \(\lambda_i\), not the rate itself. Exploration limits the consequences of an incorrect ranking, but does not prove global optimality. Likewise, the existing cost holdout demonstrates predictability of its measured proxy, not a causal increase in solution probability.

A new discovery experiment separated these questions. It used 46 cube-free targets congruent to ±3 modulo 9, excluding 114. Whole targets were split into 27 training and 19 held-out cases. Four coordinate proposals were compared: a coefficient cube, a balanced box, a real-cancellation strip and a complex-cancellation tube. The training divisor shell was \((1,1000]\); a second shell \((1000,10^6]\) tested scale transfer. Coordinates from the known-solution catalogue were not supplied to the search.[^14]

After training, both a best fixed family and a mixture were frozen. The mixture retained a 40% uniform proposal component and assigned the other 60% using smoothed training discovery rates. Tests used two seeds. The primary threshold was coordinate height at least 10, with height at least 1000 recorded separately. These intentionally small problems made actual discoveries observable within a bounded experiment; they do not reproduce the difficulty of 114.

On the joint target-and-scale holdout, the learned and uniform mixtures each found

\[
(-1213102)^3+261692^3+1209029^3=69.
\]

That is **one distinct representation**, rediscovered under both seeds and both mixtures. The best fixed training family found none there. Learned and uniform mixtures each took about 2.09 native CPU-seconds on that holdout, with essentially identical observed yield. The preregistered promotion gate required at least ten qualifying discoveries and a gain of at least 10% in each seed; it failed.

The full experiment comprised 606 runs and about 28.8 aggregate extra CPU-seconds. In 391 of 606 runs, the attempt cap caused termination before the CPU ceiling; actual CPU consumption was unequal and small finite grids became saturated. A common-observed-CPU-prefix sensitivity preserved the held-out hit counts, but changed the apparent training ranking. Timing normalization and seed repetition cannot turn one distinct held-out positive into strong statistical evidence. The sound inference is that a training winner can fail to transfer, diversification can preserve access, and this learned mixture has not demonstrated an advantage over uniform diversification. **No discovery predictor was promoted.**

Published stochastic-optimization work has tried the requested style of navigation. Lazov–Vetsov used distance to the nearest integer after solving for one coordinate, testing particle-swarm and annealing approaches on \(k=2\); the dispersive-flies follow-up also focuses on that much more accessible target.[^15][^16] Such results establish that optimization methods have been tried, not that they outperform arithmetic sieving for 114.

There is a numerical problem with treating a floating-point near-integer as success. At magnitude \(10^{18}\), ordinary binary64 spacing is already larger than one integer. If \(z\) is near the real cube root, a residual of one in the cube equation corresponds to a displacement of approximately \(1/(3z^2)\), around \(10^{-37}\). A trustworthy objective would require far more precision plus exact final verification. Even then, a small residual is not a proved predictor that nearby integer parameters contain a zero.

Visual structure in known solutions can suggest useful features, but must survive conditioning on congruences, sampling method and height. The Diophantine-imaging paper studies patterns in available triples and proposes further applications; it does not supply a validated high-height locator for 114.[^17] A rigorous future learning comparison should keep entire targets and larger heights hidden, count distinct identities, include a fixed geometric baseline, and report unsuccessful tests without repeatedly tuning against the same holdout.

Learned program priorities have improved other mathematical searches: Ellenberg and collaborators report results on cap sets, admissible tuples and no-isosceles grids using a fixed rigorous evaluator.[^20] Those tasks provide graded progress such as valid-set size. For 114, a comparable useful intermediate objective has not yet been demonstrated. LLM-generated code and priorities can still be tested as challengers, but a faster surrogate score must not be mistaken for greater discovery yield.

Cross-entropy and importance-sampling methods are another serious option when a proposal distribution, an event and correct weights are defined.[^21] Intermediate rare-event levels can guide sampling only if they retain useful access to the final event. A hierarchy of modular survivors is cheap to measure, but its relationship to exact integer-square hits must be validated. The current categorical learning experiment is not an importance-sampling estimate of a solution probability.

## A more systematic geometric challenger

The next useful diversity axis comes from the embeddings of the cubic field. Let \(T=\sigma_1(\gamma)>0\) be the real embedding and \(W=|\sigma_2(\gamma)|\) the modulus of a complex embedding. Then

\[
N(\gamma)=TW^2,\qquad
\tau=\log\!\left(T/N(\gamma)^{1/3}\right).
\]

Multiplication by a positive norm-one unit shifts \(\tau\) by the logarithm of that unit. A fundamental interval for this phase therefore gives a principled way to identify unit duplicates and describe which shapes have been visited. Equal phase widths do not imply equal root mass or equal discovery probability.[^18]

The current offset families concentrate on small positive real embeddings. A complementary family can make the complex embedding small. Put

\[
U=a-\alpha^2c,\qquad V_b=b-\alpha c.
\]

Then direct expansion gives

\[
W^2=U^2-\alpha UV_b+\alpha^2V_b^2
=\left(a-\frac{\alpha b+\alpha^2c}{2}\right)^2
+\frac34(\alpha b-\alpha^2c)^2.
\]

A bounded norm/phase cell thus gives a bounded range for \(c\), a thin interval for \(b\), and circle-cross-section intervals for \(a\). This describes the whole tube, including its angular directions. Searching only continued-fraction approximants or the nearest coefficient triple would define a narrower heuristic subset and could omit valid points.

Before such a family becomes production work, its algebraic endpoints need conservative certified rounding, its accepted coefficients need comparison with exhaustive small domains, and its unit-equivalence overlap with previous tiles needs a proof or explicit accounting. It must also show useful distinct root/ratio coverage per CPU-second. The formulas make that work concrete, but the present review has not established the performance or fertility needed to replace the running generator.

An independent root-first control remains valuable. Suitable finite prime-factor packets can provide a comparison distribution with explicit root multiplicities. Randomly generating already factored integers is an established technique, but it is not automatically a uniform sample of roots, let alone a uniform sample of solutions.[^19] A comparison must retain proposal probabilities, support and overlap information; simply multiplying a candidate count by an average density would conceal those differences.

## Production decision and interpretation of progress

The selected configuration remains phase3: 12 local workers, the existing 81 class/shape/shell/ratio contexts, exact interval inversion and modular sieving, adaptive filter order, and the 40% exploration allocation. No frozen executable or coverage record was changed. The original 24-hour session deadline remains 10 September at 12:01 IST. Monitoring remains hourly and quiet on routine healthy checks.

The earlier measured pace was approximately 39.4 million curve-interval checks per second across the workers. A curve-interval check means a bounded quotient search attached to a generated root, not exhaustive solution of an elliptic curve. The same root can legitimately occur in distinct disjoint ratio bands. The code and domain checks establish the narrower coverage claims recorded in the ledger.[^11]

The earlier rough 70-year figure estimated exhaustion of the finite configured coefficient catalogue under unchanged average costs and ideal continued availability. It was not an ETA to a solution. A complete catalogue can still contain no solution. Likewise, under an additional Poisson assumption and the published asymptotic constant, a complete eightfold divisor expansion gives \(1-e^{-0.058459\log8}\approx11.45\%\). That illustrative calculation does not estimate this selective campaign's odds.[^2]

Several stronger statements in the original campaign assessment should therefore be discarded. Sparse solutions do not prove that no faster algorithm can exist. Agreement of intermediate progression counts with an asymptotic formula does not prove absence of hidden solution-location structure. Poisson behavior is a modeling assumption, not a theorem for the observed search. An anticipated GPU gain is not a benchmark. Selecting an unusually unsuccessful target after inspecting several targets also requires accounting for that selection before interpreting a small tail probability.

The practical research rule is now explicit: promote a change when it improves validated coverage per unit of compute, or when a properly held-out discovery experiment supports its location advantage. Keep exact exclusions separate from model preferences. Preserve discoveries before secondary bookkeeping, reconcile the coverage ledger, and retain unsuccessful experiments so that they are not repeatedly proposed as unexplored improvements.

This is a credible, structured local campaign with useful arithmetic and engineering safeguards. Its discovery probability remains uncalibrated. The current evidence supports continuing the chosen bounded run; it does not support claiming that a breakthrough has already occurred or that a short solution ETA is available.

## Sources and experiment records

[^1]: Jon Grantham and P. G. Walsh. [Representing integers as a sum of three cubes](https://arxiv.org/abs/2211.12149), 2022, especially the worked example and conclusion of §2.
[^2]: Andrew R. Booker and Andrew V. Sutherland. [On a question of Mordell](https://arxiv.org/abs/2007.01209), PNAS 118, 2021, §§2–5 and Remark 5.1. Density-based probability calculations in this report add an explicitly stated Poisson assumption.
[^3]: Andrew V. Sutherland. [SumsOfThreeCubes reference implementation](https://github.com/AndrewVSutherland/SumsOfThreeCubes), invocation and implementation documentation.
[^4]: [Local field and unit analysis](../unit_shape_proposal.md) and [phase3 domain proof](../phase3/DOMAIN_PROOF.md), computational derivations and finite-domain scope.
[^5]: Noam D. Elkies. [Rational points near curves and small nonzero \(|x^3-y^2|\) via lattice reduction](https://arxiv.org/abs/math/0005139), 2000, especially §§2.3 and 3.2.
[^6]: Sander G. Huisman. [Newer sums of three cubes](https://arxiv.org/abs/1604.07746), 2016, implemented lattice search and computation report.
[^7]: PARI/GP. [Hyperelliptic curves: hyperellratpoints](https://pari.math.u-bordeaux.fr/dochtml/html/Hyperelliptic_curves.html#hyperellratpoints), bound and interval semantics.
[^8]: Tim Browning and Florian Wilsch. [Integral points on cubic surfaces: heuristics and numerics](https://arxiv.org/abs/2407.16315), 2024 preprint; [published 2025](https://link.springer.com/article/10.1007/s00029-025-01074-1).
[^9]: Tim Browning, Jakob Glas and Victor Y. Wang. [Optimal sums of three cubes in finite-field polynomial rings](https://arxiv.org/abs/2408.03668), 2024 preprint, published 2025. Its algebraic setting and assumptions differ from the integer target.
[^10]: N. K. Wadhawan and P. Wadhawan. [Representation Of Integers By Sum Of Three Cubes, A New Approach Based On Seed Equation](https://arxiv.org/abs/2512.15763), arXiv posting 2025 (the record lists a 2020 journal reference), especially §6; critical comparison in [algorithm review](ALGORITHM_REVIEW.md).
[^11]: Local phase3 [implementation and validation](../phase3/README.md), [performance evidence](../phase3/PERFORMANCE.md), [safety review](../phase3/SAFETY_REVIEW.md), and [production audit during this review](production-audit.json). These are local engineering records, not external mathematical publications.
[^12]: New [normalized-sieve prototype and derivation](normalized-sieve/README.md), [validation results](normalized-sieve-validation.json), and [81-pair exploratory timing](normalized-sieve-benchmark.json).
[^13]: [Production cost model and its assumptions](../phase3/ML_POLICY.md); live state and holdout evidence are in the phase3 campaign ledger.
[^14]: New [discovery experiment](DISCOVERY_LEARNING.md), [preregistered design](discovery_preregistered.json), [frozen policy](discovery_frozen_policy.json), and [complete results](discovery_results.json).
[^15]: Boian Lazov and Tsvetan Vetsov. [Sum of Three Cubes via Optimisation](https://arxiv.org/abs/2005.09710), 2020 preprint.
[^16]: Lazov and Vetsov. [A new dispersive flies optimisation algorithm for the sum of three cubes](https://www.inderscience.com/filter.php?aid=131357), 2023. Primary-source scope and limitations are detailed in [the learning review](DISCOVERY_LEARNING.md).
[^17]: Eldar Sultanow, Max Henkel and Idriss J. Aberkane. [Diophantine imaging reveals the broken symmetry of sums of integer cubes](https://www.nature.com/articles/s41598-023-49960-y), Scientific Reports, 2024; critical interpretation in [the learning review](DISCOVERY_LEARNING.md).
[^18]: [Geometry review and derived tube bounds](GEOMETRY_REVIEW.md), with cited primary literature and explicit promotion requirements.
[^19]: Adam Tauman Kalai. [Generating Random Factored Numbers, Easily](https://www.microsoft.com/en-us/research/publication/generating-random-factored-numbers-easily/), Journal of Cryptology 16(4), 2003, pp. 287–289. Additional ideal-sampling references and limitations are recorded in [the geometry review](GEOMETRY_REVIEW.md).
[^20]: Jordan S. Ellenberg, Cristofero S. Fraser-Taliente, Thomas R. Harvey, Karan Srivastava and Andrew V. Sutherland. [Generative Modeling for Mathematical Discovery](https://arxiv.org/html/2503.11061), 2025.
[^21]: D. P. Kroese, R. Y. Rubinstein and P. W. Glynn. [The Cross-Entropy Method for Estimation](https://web.stanford.edu/~glynn/papers/2013/KroeseRubinsteinG13.html), 2013. Additional rare-event sampling work and its assumptions are discussed in [the learning review](DISCOVERY_LEARNING.md).
