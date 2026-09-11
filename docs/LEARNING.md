# Learning from exact searches

## Shared-feature residual model, 12 September

`mg114-spatial-shadow-v2` replaces cell lookup with regularized shared features:
coefficient ratios, band/shell, block position, interactions and exact outward
norm-shell bounds. It learns log1p residuals over a strong proof-aware context
baseline. That baseline already knows that a proved-empty tile has zero curve,
quotient and exact-test exposure. ML receives no credit for discovering this
theorem. No low model prediction can exclude a task.

Training is limited to the latest 32,768 eligible observations, excluding the
permanent held-out geometry cells. A new source version starts at the current
complete boundary, with no retroactive sweep of every historical prefix. A
linear SHA-256 chain authenticates frozen prefixes, including early tampering.
Old source-addressed histories remain intact. Future 1,024-task windows report
legacy context, proof-aware baseline and residual-model errors; nonempty tasks
are also reported separately. Public charts compare against the proof-aware
baseline, not the weaker historical baseline.

An exploratory historical development test trained through 16,384 and evaluated
12,159 later records, including 2,065 unseen-geometry records. On unseen geometry,
relative log-error reductions over the proof-aware baseline were 3.48% CPU,
15.78% quotient positions, 0.51% curves and 13.16% exact tests. This test was used
during development and is **not** an untouched promotion test. New production
arrivals provide the prospective evaluation. No discovery or allocation lift is
inferred. [Development results](../research/experiments/2026-09-12/shared-model.json).

New trusted ledger rows record the audit-selection source and its conditional
inclusion probability, separately from contributor attribution. This is not a
dispatch propensity and is not enough to debias all historical arrivals. No
missing probability is invented. Randomized reference trials remain necessary
for causal scheduling comparisons.

## Historical model and general evaluation requirements

Production uses the [geometry/cost preference](GEOMETRIC_POLICY.md), with historical epochs preserved. A separate deterministic spatial challenger now learns from authoritative replay records. No browser copy, task definition, random seed, leaderboard unit or mathematical exclusion is changed.

## What is implemented

`tools/strategy_model.py` validates canonical task identities, result hashes, nonnegative counters, finite positive trusted CPU and contiguous unique ledger sequences. It never reads client timings or executes submitted code. Every 1,024 accepted tasks freezes a model, source hash and hash of its complete input prefix. Models and completed next-window evaluations cannot be silently overwritten. Code changes create a new source-addressed history.

The predictor is a hierarchical empirical-mean model with 32 pseudo-observations of shrinkage: global → context → context/coefficient quadrant bins/block bin. It predicts CPU, logical quotient positions, curves and exact tests separately. Sparse cells fall back toward context averages rather than extreme noisy ratios. Coordinates are derived using integer arithmetic from canonical tasks. This is a deliberately simple learning baseline with inspectable sufficient statistics, not a neural network.

A deterministic subset of coarse coefficient regions is withheld across ell, shells, bands and block bins. Evaluation reports both all subsequent arrivals and these excluded regions. The current cell model cannot extrapolate a missing spatial cell: it falls back to context there. Equality on that split is an honest failure to demonstrate spatial transfer, not a bug to hide. Shared geometric feature models can later challenge this baseline.

Next-window errors are mean absolute log1p errors, reported separately by target, with counts of nonzero exact-test tasks. These diagnose predictions, not allocation lift. Historical windows generated on installation are retrospective; only models frozen before future receipts arrive support prospective prediction measurements. Neither is a randomized policy experiment. Delayed banking means sequence order is not execution time.

## Actions and failure containment

The existing serialized verification Action runs learning after receipt replay and aggregation. A model error cannot prevent accepted coverage and leaderboard publication. The job visibly reports learning failure, and an old report stays old rather than fabricating a fresh model. Generated learning data and the README report are committed alongside ordinary ledger updates. There is no second ledger writer, arbitrary issue code, pickle loading, cloud search or website-side model execution.

Every 64 accepted tasks still updates the published geometry/cost policy. Challenger fitting uses a coarser 1,024-task boundary to avoid chasing noise. No discovery policy is automatically promoted. Model files contain no contributor identity; the canonical input hashes permit audit against the public ledger.

## Required gate before changing task selection

1. Freeze candidate source, feature schema, model hash, objective, reference scheduler and evaluation budget before measuring. Keep an untouched final test after exploratory tuning.
2. Draw fresh task proposal pools from a declared distribution, excluding training tasks and already covered IDs. Uniform context sampling must not be described as uniform sampling of all tasks.
3. Compare uniform, published scheduler and challenger on the same controlled execution environment. Randomize order, use repeated independent seeds, count scoring, coverage/network and verifier cost, and enforce equal CPU budgets rather than equal task counts. Preserve every encountered identity synchronously. Evaluate browser and Python clients separately.
4. Report distinct canonical coverage, geometry/scale distribution, quotient exposure, curves, exact tests, failures, overlap and total cost. Exact-test throughput is diagnostic: weakening a sieve must never qualify as an improvement. Unique task IDs do not by themselves prove unique mathematical candidates across different parameterizations.
5. Use uncertainty across independent pools/regions, not billions of correlated counter increments. Require repeatable improvement over the existing policy on a prespecified useful-coverage objective, with no unacceptable concentration or operational regression. A new objective needs mathematical justification, not merely a nicer numerical score.
6. Publish a human-reviewed promotion record naming the exact evidence and limited claim. Keep the exploration distribution supported everywhere in the declared domain and measure its compute share. Never turn a low score into mathematical exclusion.

A hash partition identifies geometry, not which client policy selected a task. This implementation does not claim it can recover behavior propensities from task IDs. Server-controlled trials or separately verifiable dispatch provenance are needed before causal allocation comparisons. Historical regression fit is not off-policy evaluation.

## What would count as discovery evidence?

Zero-hit 114 data cannot validate a probability-of-discovery model. A claimed cross-target improvement needs independent, whole-target and larger-scale holdouts, exact deduplication of equivalent solutions, comparable compute budgets and protection against known-solution/catalogue leakage. Such a benchmark is not currently dispatched to volunteers. Its arithmetic constants and domains must be independently rederived; changing 114 to another integer in a production task is not valid.

The 9 September discovery experiment remains failed, not “partially successful learning.” A future model must beat that evidentiary standard. Useful outcomes today include reproducible cost/geometry relationships and failed hypotheses that prevent wasted effort.

## Reproduce

```sh
python3 tools/strategy_model.py
python3 tools/learning_readme.py
python3 -m unittest discover -s tests -p test_strategy_model.py
```

Only verified receipt data is required. Repeated runs with unchanged code and ledger preserve identical JSON. Frozen evaluations are checked by input/model/content hashes, not recomputed through platform-dependent logarithm libraries. Newly computed last-bit metric values can differ across platforms; those differences are not scientific effects. The first deployment caught this Mac/Linux distinction; its older source-addressed history is retained as superseded evidence. `data/learning/latest.json` links the active source-addressed history. Timing labels themselves are machine-dependent observations, not mathematically deterministic quantities.

## Initial controlled pilot, 11 September

The first frozen challenger was run locally on fresh tasks, using four independent seed values and randomized arm order. Each arm received a nominal 0.5 CPU-seconds per seed; actual CPU and final-task overshoot are retained. The pilot used about 8.35 CPU-seconds in total and no volunteer credit was created. The cost includes parent selection CPU and worker task CPU; wall timings also retain process/IPC overhead. It does not include setup/ledger loading or public network latency, so it is not an end-to-end client benchmark.

| Arm | Completed tasks | Logical quotient positions / CPU ms | Exact tests |
| --- | ---: | ---: | ---: |
| Uniform contexts | 505 | 38,641.75 | 158 |
| Legacy cost scheduler (pilot) | 490 | 36,239.57 | 149 |
| Spatial quotient challenger | 243 | 50,327.40 | 203 |
| Spatial exact-count diagnostic | 232 | 50,769.30 | 207 |

The quotient challenger measured about 1.39× the existing scheduler's exposure rate in this tiny pilot. It completed fewer tasks. Neither count is a discovery probability; this is not sufficient for promotion. The exact-count arm is diagnostic only. Small budgets, hardware variability, correlated task geometry and multiple arms make winner claims premature. Production remains unchanged.

[Pre-run manifest](../data/learning/pilots/2026-09-11/preregistered.json) and [full per-task journals/results](../data/learning/pilots/2026-09-11/results.json) preserve model, baseline and coverage hashes. “Preregistered” here means locally frozen before this pilot, not independently timestamped public preregistration. A public confirmation protocol should precede further tuning.

To run a new bounded local pilot (never in receipt Actions):

```sh
python3 tools/benchmark_strategy.py --output /tmp/mg-learning-new-pilot --seed 11420260912 --cpu-seconds 0.5
```

Output must be new. The benchmark excludes already verified task IDs, uses bounded replay subprocesses and preserves exact discoveries before stopping all pilot scheduling. Repeated work across arms is experimental comparison, never claimed new coverage. The benchmark intentionally does not submit banks or alter production weights.
