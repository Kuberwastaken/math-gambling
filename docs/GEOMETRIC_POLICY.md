# Geometry, cost and what the policy can claim

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

This ratio uses aggregate yield/cost; it cannot collapse because most individual yields are zero. The limited recent window gradually replaces timings from older kernels. Newly accepted records retain their verifier kernel SHA so timing transitions can be audited. Cross-machine timing noise and biased voluntary submissions remain limitations.

40% means **uniform task proposals**, then uniform row/block choices inside that context. It is not uniform over every possible task globally, nor a reserved CPU budget. We retain this floor because the prior has not earned exclusive control. Local seeds remain independent, the exact completed-task index is still consulted, and no task bounds or mathematical filters are changed by the policy.

## Exclusions and coverage

[Exact norm-shell pruning](SHELL_PRUNING.md) uses integer bounds and monotone bisection to certify rejected coefficient intervals. Original logical generator and shell-rejection counts remain unchanged, so old receipt hashes and leaderboard credit keep their meaning. A verified task with no curves is a completed coefficient-domain check, not a searched curve or an independent opportunity to win.

The [mathematical coverage export](MATHEMATICAL_COVERAGE.md) separately publishes completed `(D,r,s,qlo,qhi)` records with explicit signs, endpoints and scope. Its partial backfill watermark must not be confused with the entire ledger. Different parameterizations can still overlap; the exported records enable inspection, not an automatic claim of a gap-free new height bound.

## What learning must establish next

The existing spatial predictor stays in shadow. Its September 11 quotient-throughput pilot compared against the **legacy** policy and does not validate this new baseline. A later experiment should compare uniform, geometry/cost and spatial challengers at equal measured CPU, including scoring and duplicate-coverage costs, with frozen models and independent seeds. Report distinct curve/root exposure by D and ratio band, empty-task fraction, exact tests and elapsed CPU separately. Higher square-test counts alone can reward a weaker sieve.

Zero-hit data can improve exclusions, cost estimates and coverage accounting. It cannot validate a discovery predictor. We do not promote the challenger or attach odds to this migration.
