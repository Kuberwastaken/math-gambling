# Independent controller audit

8 September 2026. Audited `campaign.py` SHA-256 `4b6a537eab6cc7e7888dba531c670e597aefb82532e0661157bee6cf98609817`, together with the box/plane worker protocol. No controller or worker source was changed by this reviewer.

## Revision review — fixes verified

The parent updated the controller after the initial findings below. On SHA-256 `f3f2ae3a454def7ebf509a1674dab5e31f6f673fe616e42b617cd94b1da4e78d`, all nine original malformed-stat mutations were rejected, genuine box-worker output passed, and the resume/split/source-identity tests still passed. The new code checks conservation identities, includes `symmetry_rejected`, reconstructs permutations and hit generators, audits reservations on startup, and compares cached counters against completed-job records.

Failure-output rescue now retains an accepted hit on nonzero exit, timeout with byte output, and a truncated final JSON line. An invalid cube identity was rejected. Positive rescue routing was tested with an explicitly fault-injected verifier; these routing tests do not assert that `(1,1,1)` solves 114. At that intermediate SHA, a JSON list `[]` after an accepted hit raised an uncaught AttributeError. The parent fixed the type guard and OverflowError handling. A final rerun on SHA-256 `6ae1bb0cf6df4d4c9989b57951e3fd036ea5426696e138cf70a160811eebd10c` passed all nine protocol mutations, reservation tests, and all five rescue tests, including malformed-type output.

A four-job CLI smoke run before the symmetry revision completed 16,000 inputs and 5,046 curve checks; its independent database audit found no unfinished jobs or reservation gaps. Outputs reside only in the audit scratch directory.

The final snapshot now explicitly states that symmetry counterparts may remain unvisited. The underlying reason is: a negative generator can be skipped because its positive counterpart exists somewhere in the full domain, even when that counterpart has not yet been visited. This is valid canonical-representative search, but it is not a certificate that the skipped generator's curve interval is empty in the finite prefix. Count it as deferred/equivalent-to-canonical, and do not inflate completed interval coverage.

A final two-stage CLI run/resume of the fixed box controller completed eight disjoint jobs, 32,000 generator inputs, 5,422 curve checks, and 9,694,876 quotient positions. Its database audit passed with zero unfinished jobs. No solution was found. These bounded smoke tests validate orchestration; they are not a search-performance benchmark.

No blocking controller defect remains from this review. This does not constitute a formal verification or exhaustive fault-injection campaign. The original findings below document the pre-fix implementation rather than claiming all those defects remain.

## Initial findings requiring fixes before a long campaign

**1. Incomplete/malformed worker results can be committed as complete.** `execute` checks start/count/end and some geometry, but does not require `complete is True`, `version == 1`, `mode == "tile"`, `k == 114`, the requested policy, correct family, or `candidates == count`. It accepts negative counters. Its use of `int(value)` also accepts fractional JSON numbers, e.g. start `0.9` becomes zero.

I reproduced acceptance of independently mutated values for `complete`, `k`, `mode`, `version`, `policy`, `candidates`, `curves`, `start`, and `permutation_stride`. Each used an otherwise genuine 64-input worker stats record. These are protocol robustness tests, not evidence that the current worker emitted bad results during normal operation.

Require strict JSON types where the contract uses JSON integers, explicit booleans, and the complete expected metadata. Check all counters nonnegative and establish both accounting identities:

```
candidates = zero_norm + invalid_d + unsupported_D + noninvertible_C + covered + curves
quotient_points = rejected_mod243 + rejected_parity + sum(filter.rejected) + exact_tests
```

Also verify `candidates == job.count`, `hits == len(hit_records)`, `hits <= exact_tests`, the expected prime set, tested/rejected consistency, and valid permutation parameters. Derive expected stride/offset independently from seed and domain, or at minimum check the expected metadata, gcd(stride,total)=1, and valid ranges. Every relevant stats field needed by later summaries should be checked before committing the job.

**2. A genuine hit can be discarded when a worker later fails.** Workers flush a hit immediately but keep processing the tile. `subprocess.run` captures output, and `execute` raises on timeout, nonzero exit, or stderr before parsing it. The failure path does not rescue complete hit lines from stdout. Thus a valid solution printed before a timeout can be lost until a later retry rediscovers it. This matters especially near the session deadline.

Prefer streaming independently verified hits to a durable solution journal immediately. A smaller change can parse and verify complete hit lines in `TimeoutExpired.stdout` and nonzero-exit stdout before reporting the failed tile. Keep that tile unfinished unless its complete stats pass all checks. Interrupted computation and discovery of a valid solution are independent outcomes. Handle timeout output as bytes or text, and ignore only incomplete terminal JSON lines; malformed complete records must remain protocol errors.

## Additional hardening / claim limits

- `verify_hit` receives seed but does not use it: the reported index is checked only for range, not decoded back to the supplied `(a,b,c)`. Exact cube verification establishes a solution regardless, but claimed work-unit provenance is not independently established. Decode box/plane indices in Python and verify the generator when recording evidence.
- Run the reserved-interval audit at startup as well as shutdown. Source identity does not validate existing reservation structure. A startup audit catches accidental cursor or reservation inconsistencies before further work is scheduled.
- The audit checks gapless *reserved* inputs, and reports unfinished count; this is correctly distinct from completed coverage. Keep this distinction in the final report.
- Box radius is a lattice-coordinate parameter: `a=ell*t+residue`, where `t` ranges from `−floor(radius/ell)` to `floor(radius/ell)`. Consequently a can extend beyond positive radius by up to ell−1. Do not describe its domain as exactly `|a|,|b|,|c|<=radius`.
- A two-hour session stops scheduling at the deadline and drains current jobs. Its actual runtime may exceed two hours by the per-job timeout plus small bookkeeping overhead. State that accurately.
- The process lifetime guarantee is session-local. A new CLI invocation gets a fresh two-hour allowance; this is intended resume behavior, not a cumulative campaign budget cap.

## Confirmed good behavior

The following checks passed in `work/research-audit/controller-tests/audit_controller.py`:

1. Genuine worker output for 64 inputs parsed successfully.
2. A running reservation was reset to pending after initialization, preserving the exact index range and row ID.
3. A timed-out 1,000-input tile split into precisely `[0,500)` and `[500,1000)`.
4. The database audit confirmed the split was disjoint and gapless.
5. Completing the first half caused the second half to be selected next.
6. Changed source identity was rejected on resume.

Code inspection also found transactional cursor/reservation creation, single-writer locking, source and binary identity binding, bounded subprocess timeouts, deterministic finite permutation domains, exact positive-answer verification, and careful retention of unsupported/noninvertible cases as unresolved. These are appropriate foundations.

## Learning objective

The controller learns log input-throughput separately within each family/class/radius/band. Both policies are intended to check identical arithmetic inputs. Therefore its learning changes execution cost rather than asserting a solution-location probability. The family/band shares are fixed research allocations and are honestly labeled as such.

The UCB heuristic does not establish optimality: timings include process startup and transient Mac contention; batch sizes change during warm-up; the worker’s adaptive sieve starts from scratch each batch. Compare policies on identical held-out tile sizes before claiming measured improvement. Slow failed attempts are not charged to context.elapsed or policy cost, so repeated timeouts can distort scheduling shares, although the bounded split mechanism prevents silent omission. The next scheduler version could record attempted elapsed time separately from successful throughput.

## Reproduction

From the delivered package directory:

```
python3 validate_controller.py
```

The reusable standard-library validator stores current evidence and source/binary hashes in `runs/controller-validation.json`. Temporary SQLite databases, locks and CLI smoke campaigns are isolated in a temporary directory and removed afterward. It tests fourteen malformed protocol cases; interrupted reservations and exact timeout splits; five hit-rescue routes; actual exclusion of a second writer while the lock is held; successful execution after lock release; a two-stage CLI resume; and real fixed/adaptive plane integration for all three multipliers. The initial complete packaged run passed in approximately 0.53 seconds. This is a correctness/integration smoke test, not a performance benchmark.

Positive rescue routes use explicit arithmetic-verifier fault injection and never claim that the synthetic triple solves 114. Before/after hashes detect code or binary changes during testing; rerun after the final build freezes. Historical pre-fix evidence remains under the audit scratch directory.

## Concurrency restriction for the read-only audit command

A later review identified that the external read-only audit does not explicitly open a stable read transaction across all of its queries. Run it after the writer exits, as the runbook now requires. The controller’s own startup/shutdown audits share its single writer connection and are safe under the existing orchestration. A next patch should wrap external multi-query audits in an explicit `BEGIN`/rollback read snapshot before allowing them concurrently with a live writer. This restriction does not invalidate the completed tests, whose independent audits ran after their writers exited.
