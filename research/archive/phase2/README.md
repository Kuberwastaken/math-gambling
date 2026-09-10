**User-requested pause:** search is stopped. Do not resume until explicitly instructed. [Strategy brainstorm](../STRATEGY_PAUSE.md).

**Completed:** no solution found; final audits pass. [Final report and verdict](campaign_report.md) supersedes the launch snapshot below.

# Phase 2: measured parameter allocation for 114

This is a bounded, selective search on the Mac. It does not promise a solution in hours. Phase 1 completed 80,860,107,980 curve-interval checks without a solution; zero hits are not training labels for where future solutions lie.

The changes are concrete:

- Search positive cancellation offsets between the earlier box and plane families, with a certified separation from both. Three offset ranges × three ideal classes × three divisor shells × three quotient bands give 81 fixed parameter contexts.
- Invert the norm polynomial on exact monotone intervals to skip coefficient positions outside the assigned divisor shell. Apply independently certified signed-sum congruence filters modulo 8 and 361 before modular inversion and quotient sieving.
- Measure the root-exposure proxy `geometric_mass(low, high) × sum(D0/D)` per worker second. A contextual ridge model, shrunk toward recent measured arm performance, learns which contexts produce this proxy more cheaply. It never turns a low score into a mathematical exclusion.
- Train on the first two completed measurements in every context and test on its third, previously unused measurement. Enable model allocation only if the preregistered held-out utility gate passes; otherwise retain the fixed balanced allocation.
- With model allocation enabled, reserve approximately 40% of subsequent allocated worker time for exploration, with a 70/20/10 balance between the three quotient bands. The remaining time follows model scores, discounted for work already in flight. The quota uses completed times and estimates for active jobs; finite batches produce small deviations.
- Run 12 worker processes, using the faster parallelism setting measured in phase 1. SQLite reserves disjoint row intervals before dispatch; interrupted tiles remain pending. Any reported solution is independently checked using Python integers and saved before learning or accounting can fail.

The exposure model assumes interchangeable roots conditional on divisor size and quotient geometry. That assumption has not been validated for this algebraic sampler. Better proxy throughput is not demonstrated enrichment in actual solutions. Integer arithmetic alone decides candidate rejection and solution acceptance. Floating-point learning only changes scheduling.

The three coefficient shapes are `t=8..31, R=6,000,000`; `t=128..511, R=1,500,000`; `t=2048..8191, R=375,000`. For each ideal-class multiplier `ell=1,5,25`, the real embedding of the generator is approximately `ell*t`. Divisor shells are `(D0,2D0]`, `(2D0,4D0]`, `(4D0,8D0]`, where `D0=floor(10^19/54)`. Quotient bands are `0<|z|/D<=64`, `64<|z|/D<=256`, and `256<|z|/D<=4096`, subject to the frozen checker's coordinate-ordering and historical-frontier rules.

A row fixes `(b,c)`; exact inversion selects eligible offsets `t` within that row. The ledger counts rows, while worker statistics separately count coefficient positions, eligible inputs, curve-interval checks, quotient positions, and exact final tests. Different bands can check the same `(D,r)` with disjoint `z` ranges. Noninvertible denominators are unresolved inputs, not exclusions of all solutions.

Read [DOMAIN_PROOF.md](DOMAIN_PROOF.md) for the separation proof and [ML_POLICY.md](ML_POLICY.md) for learning assumptions and evaluation. The previous phase's exact checker is included read-only; phase 2 has separate source, binary, database, and evidence.

## Commands

From this directory:

```sh
python3 validate_worker.py
python3 verify_domain.py --help
python3 validate_online_model.py
python3 validate_controller.py
python3 launch_campaign.py start --hours 2 --workers 12
python3 campaign.py status
python3 campaign.py audit
python3 launch_campaign.py pause
python3 launch_campaign.py resume
python3 launch_campaign.py stop
```

Do not start a second writer or edit source while a campaign is active. Resume preserves the database and rejects changed source or geometry. A completed/stopped process needs a new `start` command, after deliberate removal of any `STOP` marker. `resume` only removes `PAUSE`. The battery guard pauses below 25% when discharging or off AC. `caffeinate` prevents idle sleep; closing the lid can interrupt the run. No cloud compute is used.

Validation evidence lives in `runs/`, `worker-validation.json`, and the domain/model evidence files. These are finite audits and regression tests, not formal verification of the entire software stack.
