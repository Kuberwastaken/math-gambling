# Phase3: optimized execution and durable discovery

This release continues the exact same 81 parameter contexts and row permutation as phase2. It changes execution, persistence and timing calibration. It does not claim to cover all integer triples, prove a solution exists, or make a solution likely within hours.

## Arithmetic changes

* A period456 row wheel batches the existing divisibility and signed-congruence predicates, retaining their exact rejection counts. Short rows retain the scalar path when wheel setup would be wasteful.
* Integral cubic finite differences advance D directly; skipped offsets advance every difference by the actual gap.
* Cached243-bit masks process short quotient intervals in machine-word batches, including negative endpoints, cyclic wraparound and parity.
* Auxiliary-prime metadata is initialized only when a surviving candidate needs it.

These are equivalent implementations of existing necessary conditions. The proposed normalized sieve at primes dividing D is **not enabled** in this release. No learned score discards a branch or substitutes for an exact square/cube test.

## Discovery and coverage

Each worker attempt writes to its own exclusive, synchronous journal. A native hit is flushed and synced immediately. The controller verifies its integer cube identity independently, then saves identity-addressed evidence before database/model updates. Startup scans journals before source/configuration/database checks; valid records preceding damaged output remain recoverable. Incomplete tiles remain unfinished and are replayed or split on timeout. Successfully committed no-hit journals can be removed; cleanup failure cannot invalidate committed coverage.

Process-kill tests exercise recovery after a hit has been synced. A machine can still fail before persistence; replay of unfinished work is the fallback. This is substantial fault testing, not a claim of formally verified hardware or software.

The migration copies all89,685 prior completed job records without altering their contents, retains all81 cursors and cumulative counters, archives the old source identity and learning state, and hashes the historical job prefix. Jobs after that prefix belong to the new source epoch. Only execution-cost learning is reset. The old phase2 source and ledger remain preserved with their STOP marker.

Noninvertible root-extractor inputs remain explicitly counted. The search is over a certified finite generator domain and quotient bands; a completed tile is not a certificate for every modular root of every norm it encounters. The proof and exclusions retain that scope.

## Learning and parallel execution

The scheduler first collects three fresh disjoint jobs per context. It evaluates the contextual model on held-out observations before enabling allocation by the model. Its existing policy reserves40% of post-bootstrap worker time for weighted exploration and60% for model allocation when the gate passes; otherwise it balances the contexts. The objective is measured arithmetic exposure per unit time, weighted by the stated geometric heuristic. It is **not** a learned probability of solving114.

Twelve separate native processes receive transactionally reserved, disjoint row ranges. The controller owns the only writable ledger lock. A24-hour session is an operational checkpoint; the authorized follow-up can audit and continue it. STOP/PAUSE markers, low battery and failures take precedence over continuation. No source or binary is edited while a session runs.

## Evidence

* [Known-hit and arithmetic tests](known-hit-validation.json): all662 known-solution fixtures, independently verified returned identities;4,161,456 row predicates,219,024 recurrence jumps and10,077,696 quotient-mask bits under undefined-behavior sanitization.
* [Controller tests](controller-validation.json): protocol failures, interrupted reservations, exact splits, exclusive writer lock, disjoint resumption, scheduler quotas and attribution.
* [Independent optimization tests](optimization-validation.json): candidate/root streams, Python integer oracles, all81 strata and paired performance measurements.
* [Independent discovery review](SAFETY_REVIEW.md) and its reproducible [fault tests](validate_discovery.py).
* [Coverage proof](DOMAIN_PROOF.md): the unchanged generator domain and its separation from phase1.

For the live process, measured release performance and latest checkpoint, see [CURRENT_CAMPAIGN.md](CURRENT_CAMPAIGN.md).
