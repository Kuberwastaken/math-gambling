# Geometry, cost and what the policy can claim

## Revision 2, 17 September

New epochs publish `policy_version` `mg114-cpu-budget-v1` with `policy_revision: 2`,
`exploration_fraction: 0.1` and `retired_bands: [[256, 4096]]`. The policy version
string is unchanged on purpose: deployed runners key their minimum-weight check on
it. `data/policy-config.json` records `policy_revision_2_start_epoch`, so the change
begins at the first **new** 64-task boundary and no frozen epoch is recalculated.

Two things changed.

**The uniform reserve drops from 40% to 10%,** spread equally over the 54 contexts
whose band is not `(256,4096]`. The 40% reserve was described as a hedge against
the geometric prior. It was not an honest hedge: the same ambient-density model
that justifies searching these norm families at all is the model the reserve was
supposedly protecting against. Keeping 40% of predicted CPU uniform did not test
that model, it only diluted whatever the model says while leaving the model in
place for the remaining 60%. A 10% floor still keeps every supported lane alive
and still lets a badly wrong estimate be observed and corrected.

**Band `(256,4096]` is retired to a trace weight.** Under the same declared model,
the 27 contexts in that band carry roughly **0.6% of expected mass for about 14%
of predicted CPU**. They are excluded from the exploitation normalisation and hold
exactly `1e-6` each, with `exploit_weight` and `exploration_weight` zero; the
remaining weights are rescaled so all 81 published weights sum to one within 1e-9.
The trace weight is deliberate: it keeps the lane dispatchable and its cost
observable rather than silently deleting it. **This is a scheduling decision. No
mathematical exclusion is claimed for that band, and any task in it is still
accepted, replayed and credited normally.**

Cost calibration is now **v1-equivalent**. Engine v2 ([CLUSTER.md](CLUSTER.md))
verifies 1024-row tasks, so a single v2 observation carries eight v1 tiles of CPU
and curves. Before entering the estimator, a verified task's CPU and curve count
are divided by `task_rows(task)/128`. Without this, a ledger that mixes engine
versions would inflate `predicted_cpu_ms_per_task` for whichever contexts happen
to attract v2 submissions and distort the CPU-share conversion below. The
0.6%/14% figures above are stated in those same v1-equivalent units, and they are
model outputs, not measured discovery rates.

## CPU-budget policy, 12 September

New epochs migrate to `mg114-cpu-budget-v1`; old epochs remain frozen. With the
geometry/cost score S below and predicted task cost C, define a target CPU share
`B_c = .4/81 + .6 S_c/sum(S)` (revision 2: `.1/54 + .9 S_c/sum(S)` over the 54
supported contexts) and dispatch probability
`P_c = (B_c/C_c)/sum(B_j/C_j)`. Thus `P_c*C_c/sum(P*C)=B_c` under the reference
cost estimates. All contexts retain positive support. These are predicted CPU
shares, not guarantees for a browser, a new kernel or a changed proposer.

Compatible clients use exact outward integer tile bounds before dispatch,
holding the selected context fixed while proposing another row/block. After 31
empty proposals they permit a normal task, ensuring bounded overhead and
liveness. A skipped proposal is neither banked nor credited nor added to exact
coverage. The equation, admissible task domain and completed receipt digest are
unchanged. Older runners can fall back to their bundled policy; upgrade to 0.6.0
for the new policy and preflight.

Two 32-seed local Python trials compared current, proof-only, CPU-budget and
combined proposals. The independent-seed confirmation used 0.5 CPU-seconds per
arm/pool and measured actual-D weighted **band** exposure. Combined median lift
was 2.00 with a paired-bootstrap interval 1.74–2.38; CPU-budget alone was 1.73.
Proof alone did not pass the uncertainty gate. These are reference-engine proxy
results, not client/network benchmarks or discovery odds. The confirmation
supports this limited policy change; shadow ML is not promoted. See the
[experiment record](../research/experiments/2026-09-12/proposals.json) and
`tools/benchmark_proposals.py`. The continuous band proxy still approximates
discrete endpoints and does not prove root exchangeability.

## Historical geometry policy

The production policy `mg114-geometric-cost-v1` repairs the estimator and changes its objective together. Historical epochs retain the method that produced them. `data/policy-config.json` fixes the migration at the first new 64-task boundary; rerunning aggregation cannot rewrite an old policy.

The old per-context median of quotient positions per CPU collapsed to zero in zero-heavy observations. Clipping then made all contexts equal. Replacing that median with an aggregate throughput ratio alone would favor the widest quotient band, whose positions are cheaper but are not equally valuable under the ambient density heuristic.

## Declared preference

Write t = |z|/D. For each admitted curve, the relative preference is

```math
G_c = \frac{D_0}{\sqrt{D_{lo}D_{hi}}}
      \int_{\max(t_{lo},\kappa)}^{t_{hi}}
      \frac{dt}{\sqrt{4t^3-1}},\qquad
\kappa = \frac{1}{\sqrt[3]{2}-1}.
```

The square-root factor comes from the real geometry of the discriminant; the cutoff reflects the canonical smallest-coordinate ordering. The inverse-D factor accounts for root progressions. We use the shell's geometric midpoint, an approximation within a factor sqrt(2) of each endpoint, not the actual D of each root. The integral is evaluated after u=1/sqrt(t) with fixed Simpson quadrature. Floating point only chooses preferences; it never determines whether any integer is excluded.

This is our inference from the ambient search geometry discussed by [Booker and Sutherland, *On a question of Mordell*](https://pmc.ncbi.nlm.nih.gov/articles/PMC7980389/), not a published calibration of this project's selected norm families. Root exchangeability and independence are unproven here. Neither a weight nor an observed throughput is a probability of finding 114.

For each context, take its latest 256 verified observations. Let C be their total trusted CPU, Y their total admitted curves and n their task count. Include **all zero-curve task costs**. Add 32 pseudo-observations at the recent global mean cost and curve yield (curve prior bounded below by one):

```math
S_c = G_c \frac{Y_c+32\overline{Y}}{C_c+32\overline{C}},\qquad
P(c)=\frac{0.4}{81}+0.6\frac{S_c}{\sum_j S_j}.
```

This ratio uses aggregate yield/cost; it cannot collapse because most individual yields are zero. The limited recent window gradually replaces timings from older kernels. Newly accepted records retain their verifier kernel SHA so timing transitions can be audited. Historical cost samples are not retrospectively relabeled as measurements of the new kernel. Cross-machine timing noise and biased voluntary submissions remain limitations.

Revision 2 replaces the 0.4/81 term above with 0.1/54 over supported contexts
only. The paragraph below describes what that floor means in either revision.

40% (revision 2: 10%) means **uniform task proposals**, then uniform row/block choices inside that context. It is not uniform over every possible task globally, nor a reserved CPU budget. We retain this floor because the prior has not earned exclusive control. Local seeds remain independent, the exact completed-task index is still consulted, and no task bounds or mathematical filters are changed by the policy.

## Exclusions and coverage

[Exact norm-shell pruning](SHELL_PRUNING.md) uses integer bounds and monotone bisection to certify rejected coefficient intervals. Original logical generator and shell-rejection counts remain unchanged, so old receipt hashes and leaderboard credit keep their meaning. A verified task with no curves is a completed coefficient-domain check, not a searched curve or an independent opportunity to win.

The [mathematical coverage export](MATHEMATICAL_COVERAGE.md) separately publishes completed `(D,r,s,qlo,qhi)` records with explicit signs, endpoints and scope. Its partial backfill watermark must not be confused with the entire ledger. Different parameterizations can still overlap; the exported records enable inspection, not an automatic claim of a gap-free new height bound.

## What learning must establish next

The existing spatial predictor stays in shadow. Its September 11 quotient-throughput pilot compared against the **legacy** policy and does not validate this new baseline. A later experiment should compare uniform, geometry/cost and spatial challengers at equal measured CPU, including scoring and duplicate-coverage costs, with frozen models and independent seeds. Report distinct curve/root exposure by D and ratio band, empty-task fraction, exact tests and elapsed CPU separately. Higher square-test counts alone can reward a weaker sieve.

Zero-hit data can improve exclusions, cost estimates and coverage accounting. It cannot validate a discovery predictor. We do not promote the challenger or attach odds to this migration.
