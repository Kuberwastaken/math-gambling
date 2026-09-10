# Phase 2 result: no solution found

The bounded two-hour Mac campaign completed at **04:48:57 IST on 9 September 2026**. All **88,766** tiles completed on their first attempt, with no failed, retried or unfinished tile and no reported solution. The search process has released its writer lock; follow-up monitoring is paused. No further compute session was started.

The campaign improved execution and tested parameter learning. It did **not** establish a way to find a solution with high probability in hours. Failure in these sampled regions does not make adjacent unexplored regions impossible.

## What was searched

Twelve local workers searched 81 fixed contexts: three ideal-class multipliers, three previously unsearched cancellation-offset shapes, three divisor shells, and three quotient bands. Exact norm-shell inversion and certified signed-sum congruences reduced work before the existing arbitrary-precision checker.

| Measurement | Count |
| --- | ---: |
| Coefficient positions classified | 2,447,223,571,368 |
| Outside the assigned norm shell | 2,002,118,603,646 |
| Rejected by signed-sum congruences | 116,413,675,620 |
| Curve-interval checks | 169,212,216,041 |
| Quotient positions classified | 17,176,138,315,674 |
| Arbitrary-precision final tests | 35,118,336 |
| Noninvertible denominator inputs, unresolved | 11,110,749,497 |

Coefficient positions are accounting units and can be generated again across different shell or quotient contexts; this count is not a count of unique triples. Curve totals count `(D,r)` intervals; the same root may be checked in different, disjoint quotient bands. The domain proof and completed-tile ledger establish distinct `(D,r,z)` candidate-position ownership within phase 2 and separation from phase 1. Neither campaign exhausts all curves at these divisor sizes or a height box.

Exact shell inversion removed **81.81%** of coefficient-position classifications because their norms lay outside their assigned shell. Signed-sum filters removed **26.15%** of shell-eligible coefficient inputs. These are accounting fractions, not isolated runtime speedups. Noninvertible denominator inputs remain unresolved; they were not counted as excluded solutions. No divisor exceeded the supported arithmetic range.

The actual aggregate worker CPU time was **23.425 core-hours**, with **23.883 worker-hours** of process elapsed time under concurrency. The phase used no cloud compute. Phase 1 had 80,860,107,980 curve checks, but comparing that count with phase 2 is not a controlled speed benchmark: the parameter and quotient-band distributions changed.

## What the model learned

The objective was the conditional root-exposure proxy

`geometric_mass(low, high) × sum(D0/D) / worker_seconds`,

where `D0=floor(10^19/54)`. Its interpretation assumes comparable roots have comparable solution yield after accounting for the stated weights. That assumption remains unvalidated for this algebraic sampler. The learner has no positive solution labels for 114.

The first two measurements in each context trained the model, and the third measurement was held out. Actual training and holdout row intervals were separately audited as disjoint in all 81 contexts. The predeclared gate passed:

- Predicted top-quarter settings delivered **1.583×** the fixed balanced baseline's measured proxy utility.
- The same selection delivered **1.155×** the geometry-only ranking's top-quarter utility.
- Held-out rank correlation was **0.9915**. Predicted aggregate utility was **0.643×** observed utility, so absolute estimates were imperfect.

The post-bootstrap worker-time allocation finished at **40.0006% exploration** and **59.9994% model selection**. Every context received work: the least-visited context completed 159 tiles; the smallest total context allocation was 162.2 worker-seconds. No arm was permanently removed by its learned score.

The model-selected jobs averaged 1,149,140 proxy units per worker-second, versus 302,992 for exploration jobs, a descriptive ratio of **3.793×**. This is not a causal performance estimate: the two groups deliberately selected different contexts, batches and times. It is also not an estimate of discovery enrichment. The held-out measurements remain the cleaner evidence for ranking utility.

The settings receiving the largest total allocations were:

| ell | Offset t | Divisor shell / D0 | Quotient band | Share of total worker time | Observed proxy units / worker-second |
| --- | --- | --- | --- | ---: | ---: |
| 1 | 2048–8191 | 1–2 | 0–64 | 8.04% | 1,208,434 |
| 25 | 2048–8191 | 1–2 | 0–64 | 8.02% | 1,207,048 |
| 5 | 2048–8191 | 1–2 | 0–64 | 8.00% | 1,206,493 |
| 1 | 128–511 | 1–2 | 0–64 | 7.83% | 1,167,584 |
| 5 | 128–511 | 1–2 | 0–64 | 7.74% | 1,165,793 |
| 25 | 128–511 | 1–2 | 0–64 | 7.56% | 1,162,957 |
| 1 | 8–31 | 1–2 | 0–64 | 6.48% | 1,013,083 |
| 5 | 8–31 | 1–2 | 0–64 | 5.93% | 1,009,367 |
| 25 | 2048–8191 | 2–4 | 0–64 | 1.32% | 612,691 |

The detailed per-context and per-strategy measurements are preserved in [the final analysis](runs/final-analysis.json). Initial gate predictions and observations are in [the held-out evidence](runs/heldout-gate.json); [ML_POLICY.md](ML_POLICY.md) specifies assumptions and implementation.

## Verification

The independent final database audit confirms disjoint, gapless reservations, all 88,766 tiles complete, and exact reconciliation of counters, model observations and allocation records. Every completed worker record was revalidated against its assigned geometry, permutation, range, integer counters, filter conservation laws and exposure bounds. All first-attempt counts are one; no recovery or replay was required.

Frozen controller, mathematical sources, binary and PARI library hashes still match the production database. The actual database geometry matches the certified context file. A fresh [domain certificate](runs/final-domain-certificate.json) passes its exact separation and arithmetic bounds, field certificate and malformed-geometry guards. The earlier worker regression tests and independent controller review are unchanged.

These are finite regression tests, exact mathematical prerequisites, and ledger checks. They are not formal verification of the whole software stack. The audits found no failure that would justify discounting this run or rerunning the same tiles.

## Verdict and next useful experiment

Adaptive mathematical/CS search makes sense here: exact constraints safely remove impossible assignments, and measured costs guide a finite allocation. This campaign demonstrates both. Its successful learning target was execution utility. It has not learned a solution-location predictor, and the zero-hit outcome supplies no positive evidence that our proxy identifies unusually fertile regions.

Before another similar multi-hour search, the useful next experiment is to test that missing assumption: reconstruct the generator shapes of known three-cube solutions on held-out targets and compare our ranking against a simple arithmetic baseline. A smaller divisor range where all modular roots can be enumerated can separately test how strongly the generator sampler biases the proposed root-exposure measure. Split evaluation by target and size before tuning; training and testing on the same known solutions would not validate discovery performance. Transfer to 114 would still be uncertain.

A failed validation would favor retaining only the proven arithmetic cuts and cost optimizations. A convincing held-out enrichment result would justify a new, explicitly bounded campaign. Simply training longer on zero solution labels or deleting low-scoring regions would not justify either a breakthrough claim or a short-time success forecast.
