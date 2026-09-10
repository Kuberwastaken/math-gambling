# What the online model learns

The phase-two model learns **which configured arithmetic workload produces the most reported root exposure per second**. It has no positive solution labels for 114, does not predict where an actual solution lies, and never turns unsuccessful searches into mathematical exclusions.

The controller retains 40% of allocated worker time for exploration under the predeclared allocation: equal classes, shapes, and divisor shells, with quotient-band weights 70/20/10. The model supplies priorities for the remaining 60%. This module neither enforces nor overrides that quota; the controller must enforce it independently. Zero exposure, a low prediction, or a failed gate must not permanently starve an arm.

## Proxy objective

For a completed job the worker reports

```
exposure_sum = sum(D0 / D)
```

over its eligible root curves after certified signed-sum filtering. The utility estimate is

```
geometric_mass(q_low,q_high) * exposure_sum / elapsed_seconds.
```

This is proportional to an expected-solution measure only under a **conditional exchangeable-root heuristic**: after the known restrictions, roots with comparable arithmetic context are treated as equally productive, apart from the divisor and geometric weights. That hypothesis is not learned from the zero-solution data. Additional local densities, generator bias, unresolved correlations, and repeated roots can invalidate it. The model does not itself certify root uniqueness; it consumes the worker's reported exposure.

The geometric weight is the normalized integral

\[
G(L,H)=\frac{\int_{\max(L,\kappa)}^H (4t^3-1)^{-1/2}\,dt}
{\int_\kappa^\infty(4t^3-1)^{-1/2}\,dt},
\qquad \kappa=\frac{1}{\sqrt[3]{2}-1}.
\]

An empty interval has mass zero. Substitution `u=1/sqrt(t)` gives the smooth integrand `2/sqrt(4-u^6)` on a short finite interval. The implementation uses 256-panel Simpson quadrature. Refinement to 512 panels changes the normalization by about `1.69e-13`; this is more than sufficient for a ranking weight. **Numerical integration never determines a mathematical rejection.**

For the three configured quotient bands, the model masses are approximately 0.7549, 0.1226, and 0.0919. The remaining tail beyond 4096 is outside these arms; the model does not imply that it has been searched or excluded.

## Persistent, lightweight learning

Each arm stores its raw total exposure, elapsed time, row count, job count, and the last nine measured rates and durations. The raw totals are preserved for auditing. For prediction, a recent cost-weighted aggregate clips rate outliers to one quarter through four times the recent median. This limits the effect of transient timer noise and lets the estimate follow sustained changes in machine speed.

A small ridge regression predicts **log exposure throughput**, using categorical class, shape, divisor-shell and quotient-band features, plus shape-by-shell and shell-by-band interactions. For the configured 81 arms it uses 17 coefficients. The shared rate scale is a robust median, and the ridge penalty is fixed at 2.0. A three-job shrinkage prior blends contextual predictions with the arm's empirical measurement. As measurements accumulate, the empirical recent throughput carries more weight. The geometric mass is applied after throughput prediction, rather than asking the regression to relearn that specified formula.

These are regularization and robustness choices, not Bayesian credible intervals or proofs that the ranking is optimal. In particular, a score is **not a probability**. A contextual predictor can be wrong in an unmeasured arm; continued exploration is essential.

The score is divided by `1 + pending_jobs_for_arm`. This discourages launching many workers against the same stale estimate. It is a scheduling heuristic, not a proof of optimal parallel allocation. The module is pure Python standard library, serializable as JSON, and caches its fitted coefficients until a new observation arrives.

## Held-out gate

`evaluate(records)` takes the first two completed measurements per arm as training data and reserves the third as a holdout. Later records are ignored during this evaluation. No third-record result is used to fit the evaluated model. The result enables the model only when all of these predeclared proxy checks pass:

- At least 12 arms have complete training and holdout measurements, with no represented arm missing its third measurement.
- The holdout has positive measured exposure utility.
- Predicted and observed utility ranks have Spearman correlation at least 0.2.
- The predicted top quarter of arms has mean holdout utility at least 1.05 times the fixed allocation's weighted baseline utility.
- The single highest-predicted arm's holdout utility is at least the baseline utility.
- Aggregate predicted versus observed utility lies between 0.25 and 4.

The evaluator also reports a **geometry-only ranking**. This distinguishes gains from measured contextual differences from gains obtainable simply by favoring the analytically higher-mass quotient bands. The geometry-only comparison is reported separately; it is not an additional gate threshold.

This is a holdout of **measurements of the proxy**. It does not validate a success predictor, establish discovery probabilities, or establish a causal advantage over another search algorithm. The caller should use separate generator intervals for training and holdout when testing exposure generalization. This module groups by arm and measurement order; it does not prove interval disjointness from worker metadata. If the gate fails, the controller should use its balanced fixed allocation. A later gate can be rerun on a new declared split rather than tuning thresholds against this holdout.

## API

```python
from online_model import Model, geometric_mass, evaluate

model = Model.initial(specs)
model.observe(spec, elapsed, exposure_sum, rows, stats)
scores_by_key = model.scores(specs, in_flight_counts)
saved = model.to_dict()
restored = Model.from_dict(saved)
gate = evaluate(records)  # gate["enable_model"] is a boolean
```

Specifications use `key,ell,radius,tlo,thi,dlo,dhi,low,high`. Metadata such as `family,total,weight,shape_index,shell_index,band_index` is retained. `in_flight_counts` maps arm keys to nonnegative integer counts. Records use `spec,elapsed,exposure_sum,rows,stats`. The caller must pass only completed, validated worker measurements; the optional statistics do not become solution labels.

Invalid observations, changed arm definitions, malformed persistent state, and nonfinite values raise errors. The controller falls back to balanced allocation when the held-out gate fails. Unexpected numerical or accounting errors stop scheduling and preserve evidence; they require inspection before resumption. Numerical safeguards are modeling restrictions, not mathematical exclusions of any candidate.

## Validation status

`validate_online_model.py` passes nine groups of synthetic tests covering:

- Geometric normalization, additivity and quadrature refinement.
- Transfer of measured shape effects to cold divisor-shell arms.
- Known fast/slow ranking and pending-job discount.
- Exact score preservation through JSON serialization.
- Acceptance of predictable proxy holdouts and rejection of inverted or incomplete holdouts.
- Stable, finite scores when every observed exposure is zero, with the gate disabled.
- Resistance to one extreme timer outlier and adaptation after sustained throughput change.
- Rejection of invalid inputs without corrupting persistent state.
- Independence of the held-out gate from unused later observations.

The synthetic favorable case has Spearman correlation about 0.981, top-quarter utility 1.761 times the balanced baseline, and 1.455 times the geometry-only ranking. **These are synthetic software checks, not measurements on the 114 campaign.** The live controller must run and report its own held-out gate. Complete validation evidence, including source hashes, is in `online-model-validation.json`.

## Production gate

The actual 81-context gate passed in phase2. Its selected top-quarter utility was1.583× the balanced baseline and1.155× the geometry-only ranking. See [the measured parameter update](PARAMETER_UPDATE.md) and [the actual train/holdout interval-separation audit](runs/heldout-separation.json). These remain proxy measurements, not discovery enrichment.
