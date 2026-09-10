**Completed:** no solution found; final audits pass. [Final report and verdict](campaign_report.md) supersedes the launch snapshot below.

# Parameter update: phase 2 launched

The second bounded two-hour campaign is running with 12 workers. It started at **02:48:55 IST on 9 September 2026** and is scheduled to finish at **04:48:55 IST**. No solution had been found at this launch checkpoint (2026-09-08T21:21:25Z). The same thread's follow-up monitor is active every 15 minutes for this bounded window.

## Changes based on phase 1

Phase 1 ended with 80,860,107,980 curve-interval checks and no solution. Phase 2 implements the proposed exact norm-shell inversion and certified signed-sum filters, and searches three new positive cancellation-offset ranges between the earlier generator families. The [domain proof](DOMAIN_PROOF.md) establishes separation from phase 1 and between completed phase 2 tiles. This is a selective search, not an exhaustive frontier or height-box search.

## Actual held-out learning result

The first two measurements in each of all 81 contexts trained the model; the third measurement was held out. The predeclared gate passed. Its selected top quarter attained **1.583×** the balanced allocation's measured proxy utility, and **1.155×** the geometry-only ranking's top-quarter utility. Rank correlation was 0.9915. Predicted aggregate utility was 0.643× observed utility, so the absolute cost estimates were imperfect even though the ranking was useful.

These are measured **conditional root-exposure per worker second**, not actual discovery enrichment. The comparison uses different deterministic tiles and their measured process elapsed times under concurrent load. It is not a causal benchmark against a separately run baseline and provides no calibrated solution probability. The raw [held-out evidence](runs/heldout-gate.json) includes every prediction and observation.

The controller now gives approximately 60% of post-bootstrap allocated worker time to the learning model and retains 40% exploration. Recent measured performance updates the model; in-flight work discounts crowded contexts. Geometry, arithmetic checks, and exact exclusions remain fixed. Low utility never permanently removes an arm.

Top current model settings at the checkpoint, before the in-flight discount:

| Class multiplier ell | Offset t | Divisor shell / D0 | Quotient ratio band | Proxy units / worker-second |
| --- | --- | --- | --- | --- |
| 1 | 2048–8191 | 1–2 | 0–64 | 1,244,358 |
| 5 | 2048–8191 | 1–2 | 0–64 | 1,240,910 |
| 25 | 2048–8191 | 1–2 | 0–64 | 1,237,668 |
| 1 | 128–511 | 1–2 | 0–64 | 1,205,948 |
| 25 | 128–511 | 1–2 | 0–64 | 1,203,402 |
| 5 | 128–511 | 1–2 | 0–64 | 1,195,569 |

This ranking can change during the run. `D0=floor(10^19/54)`; the complete geometry and allocation rules are in [README.md](README.md).

## Validation and operation

The new worker passed 31,230 independent coefficient checks across 54 complete small domains, 40 shell endpoints, signed-modulus certificates, row and quotient-band partition checks, undefined-behavior checks, invalid-input tests, and all 662 known-curve regressions inherited from the exact checker. Eighteen matched direct-versus-inversion comparisons produced identical candidate, filter and exposure counts. Model tests and controller fault/recovery tests passed, including discovery retention through bookkeeping and concurrent-worker failure. These are finite tests and independent reviews, not formal verification of the whole program.

The running ledger audit passes; model observations and allocation totals reconcile, and its recorded source hashes match the frozen files. At the checkpoint it had 2,100 completed tiles and 3,746,052,837 curve-interval checks. [Launch audit](runs/launch-audit.json) records the precise snapshot. [Live status](../../../docs/ARCHIVE.md) supersedes these changing counts.

The session pauses below 25% battery while discharging. Closing the lid may interrupt it; its ledger retains unfinished work. No cloud compute is used. The monitor will audit and report completion rather than automatically extending the budget. A solution, if encountered, must pass independent arbitrary-precision verification before being reported.
