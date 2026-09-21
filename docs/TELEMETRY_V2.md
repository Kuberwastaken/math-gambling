# Auditable telemetry protocol v2 (draft, not shipped)

The current bank format intentionally submits only a task identity and result digest. That is enough for sampled verification, but it discards the arithmetic funnel for unreplayed work. This draft adds hypothesis-generating telemetry without treating client claims as verified facts.

Each task claim would add:

- the existing task and digest;
- the full aggregate counters already covered by that digest;
- compact, bounded histograms keyed by declared bins for divisor shell, root multiplicity/class, unit phase, ratio band and quotient-window length;
- for each bin, counts at the stages `curve`, `mod243`, `parity`, `auxiliary_prime`, and `exact_square`.

The schema must fix every bin edge, integer width, maximum count and canonical encoding. It must not include arbitrary labels, code, URLs or unbounded maps. Exact identities keep their existing high-priority path.

Telemetry is **untrusted** until replayed. Random sampled tasks are replayed with the Rust kernel and deterministic Python cross-check. The verifier compares the submitted counters and recomputes the sufficient statistics. A mismatch quarantines that account's telemetry from model fitting; it does not erase independently verified tasks or identities. Reinstatement requires a clean, predefined audit window. Unsampled telemetry may generate preregistered pruning hypotheses, but can never certify coverage, credit, or an exclusion.

Before a runner protocol bump, fixtures must prove bounded parsing, canonical round trips, old-client compatibility, mismatch quarantine, replay agreement and preservation of exact hits. The first analysis must be frozen before reading held-out targets and height shells. Only proved necessary conditions validated against exhaustive small domains may become production pruning.
