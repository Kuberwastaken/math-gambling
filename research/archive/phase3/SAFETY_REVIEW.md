# Phase 3: independent coverage and discovery review

9 September 2026. This review separates exact mathematical scope, finite software checks, migration integrity and storage guarantees. No solution of114 was found or supplied by these tests.

## Current review result

The independent durable-discovery tests pass for the reviewed controller. They exercise genuine known identities for **k=3**, with the test target explicitly set to3; the default production target114 rejects those same records. Positive recovery fixtures are not claimed solutions of114.

The final production migration independently preserved all **89,685** completed job records exactly, all81 context specifications and cursors, accumulated counters, solution history, and archived prior metadata. Its immutable historical-job digest is

```
df492f4cd854dc1b856b65596b15351b2ff85e330ed0b965203a2c33f8f4e728
```

Only timing/model state resets for the new execution epoch. **The final comparison against the actual migrated production ledger passes, and its recorded new-source identity exactly matches the current files.** The complete independent suite, including the real-ledger comparison, passed in2.34 seconds against controller SHA256 `1ad8fdc86934e071e2921b0faa358ac43655dcbd9dc6d6715fc8f10e6218dd58`. This supersedes the earlier trial copy, whose historical records matched but whose source identity predated final edits.

The reproducible test command is:

```
python3 validate_discovery.py --migration-old ../phase2/runs/campaign/campaign.sqlite3 --migration-new runs/campaign/campaign.sqlite3
```

Run the migration comparison before any new jobs advance the new ledger. The script opens both databases read-only and starts explicit read transactions. Its process/failure tests write only temporary state; they never dispatch a production mathematical search. Evidence is `runs/discovery-validation.json`, including reviewed source hashes.

## Mathematical scope and new filters

The geometry remains the81 certified phase-two contexts with the same coefficient mapping, seed1142, class multipliers, norm shells and ratio bands. Continuing each context at its recorded cursor therefore continues the existing permutation rather than restarting it. The domain proof's class ownership, unit bounds and signed/ratio partitions still apply. The migration must preserve these exact specifications; changing the seed would not create a disjoint mathematical domain.

The phase-three native changes reviewed here reorganize existing exact predicates:

- **Period456 row wheel.** For fixed b,c and `a=base+ell*t`, the norm is an integer multiple of ell. The wheel computes D modulo24 using exact cubic forward differences. Since `N≡a³ mod19`, signed mod361 failure can occur only when19 divides a. At that residue, `N/19≡6b³ mod19`, so `D mod361=19(6ell^(-1)b³ mod19)`. The signed choice depends on D modulo3. Thus the361 predicate has period57, the signed8 predicate period24, and their joint period456. The implementation preserves the order of invalid-D, signed8, and signed361 accounting. Its use is restricted to already selected positive-norm intervals with lower D bound at least1.
- **Forward-difference jumps.** Skipping h offsets uses `D(t+h)=D+hΔD+binom(h,2)Δ²D+binom(h,3)Δ³D`, and advances the lower differences consistently. This does not assume that an admitted offset is one step after its predecessor.
- **Cached short quotient windows.** Because D is coprime to243, `z=r+Dq` is transformed to the mask position `q+D^(-1)r mod243`. The cached mask has a duplicated prefix sufficient for a64-bit window across its boundary. The parity mask applies to the original q index, and the final partial word is truncated to the assigned interval. Lazy preparation changes when a prime's data are computed, not its residue predicate.

Source review found no mathematical false-negative issue in those transformations. The backend's direct-versus-optimized and known-solution tests remain necessary evidence for their implementation; a prose proof alone does not establish that every C operation and endpoint is correct.

The separately proposed normalized sieve at primes dividing D is not present in the reviewed checker. It is not counted as an implemented benefit. If introduced after this version completes work, it needs a new source epoch and independent validation of the normalized division and sign rules.

## What noninvertible C means

For an actual class-cleared root-ideal generator `(gamma)=I(D,r)J^j`, the cyclic quotient proof gives `gcd(C,ell D)=1`, where `C=b²−ac`. Thus failure of the inverse cannot discard a representation satisfying that exact ideal equality.

The sampled elements, however, satisfy the weaker lattice membership and norm conditions. Membership alone does not prove equality with a particular root ideal. For example, `gamma=5(alpha−4)`, ell25, D250 is compatible with a root modulo250 but its residual ideal of norm25 can be the degree-two prime above5 rather than `J²`; here C is noninvertible. This is the existing counterexample to the weak converse.

Consequently, the approximately11.2b historical noninvertible inputs must not be reported as impossible solution curves or as proof that every root of their norms was searched. Their counts and deterministic row locations remain retained. The certified domain is a finite generator search with its stated invertibility restriction, not all integers, all root ideals, or every triple of coordinates within a height box. No expensive fallback or expanded domain is silently added by this migration.

A **detected hit** means an explicit integer triple passed the complete cube identity check. A norm input rejected before a modular root could be assigned did not reach that stage. This distinction limits any claim that the system will preserve every encountered solution.

## Durable discovery path

Every production attempt gets a unique `journals/job-ID-UUID.jsonl` file opened with exclusive creation and synchronous-write flags. Retrying an input cannot truncate its prior attempt. Directory synchronization preserves the created directory and file names to the extent guaranteed by the operating system and storage stack.

The native checker prints a complete hit record, checks `fflush`, and calls `fsync` when stdout is a regular file. The controller also flushes/synchronizes at process completion or failure. It parses every complete line independently, so a torn final line or broken statistics do not conceal preceding valid identities.

Startup acquires the writer lock and scans journals and identity-addressed discovery files **before database opening, source checks, or dispatch**. It verifies the actual integer cube identity independently of row/coverage metadata. Unreadable or malformed evidence is reported; scanning continues so an unrelated earlier bad file cannot hide a later valid identity. Unresolved recovery errors without a valid recovered identity stop scheduling.

Each verified triple is independently stored under a hash of its target and canonical coordinates. Pair lists are checked for matching, nonzero lengths and every pair is verified before persistence. `SOLUTION.json` and identity files use temporary-file writes, file synchronization, atomic replacement, and directory synchronization. A recovered identity stops further scheduling, even if its original coverage metadata or database cannot be used.

A failed or interrupted worker never becomes a complete tile through hit recovery. Incomplete reservations remain available for review/replay. Conversely, failure to delete a no-hit journal after a successful transaction emits a warning and retains the file; it does not invalidate already committed coverage.

## Independent fault tests

`validate_discovery.py` checks:

- Genuine k3 identities, production114 rejection, false cube identities, malformed triples, and complete hits before torn output.
- Nonempty matched evidence pairs, separate identity-addressed files, idempotent replay, and recovery from discovery files even without a journal.
- A corrupt or unreadable earlier file alongside later valid identities; unresolved corruption blocks a clean restart.
- Injected failure after a temporary file is synchronized but before rename, followed by successful replay from the retained journal.
- Recovery before database/source operations, no dispatch after recovery, and rejection of a second writer before it scans or writes evidence.
- Actual temporary subprocesses that emit and synchronize known k3 identities, then exit nonzero or time out.
- Repeated attempts creating different journal paths without changing earlier bytes.
- **SIGKILL of both the temporary controller and its worker after the hit-fsync boundary**, followed by successful recovery without a database.
- Injected journal-cleanup failure after a synthetic successful transaction; the row remains complete and the warning is recorded.
- Independent byte-equivalent comparison of every historical job row, all cursors, totals, prior metadata and solution records between the stopped original and the migrated ledger.

These are finite regression and fault-injection tests. Synthetic routing/accounting fixtures are identified in the evidence; they are not native114 searches or substitutes for the backend's candidate-oracle tests.

## Limits of the guarantee

The tested guarantee is that a complete synchronized hit record can be recovered after ordinary worker/controller process failure, and that bookkeeping or unrelated metadata errors do not silently discard a verified identity.

No software can promise persistence if killed between computing a solution and writing its first durable record. In that case an incomplete deterministic tile must be replayed after resumption. File synchronization also cannot guarantee survival of every power failure, defective storage device, filesystem corruption, or operating-system bug; it is not an independent off-device backup. Nor do finite tests formally prove the arithmetic implementation.

The honest operational claim is **durable, independently verified hit recovery with retained incomplete work**, subject to these limits. It is not an unconditional “never miss any solution” or “100% of the mathematical search space covered” promise.
