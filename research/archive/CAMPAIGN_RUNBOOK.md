# Mac search campaign: operation and interpretation

This campaign searches for integer solutions of **x³ + y³ + z³ = 114** for a bounded session, keeps a durable work ledger, and adapts execution costs. Its tests establish arithmetic and orchestration correctness within their tested scope. They do not establish a high probability of finding 114 in hours.

## Current session

The first production session **completed at02:06:12 IST on9September2026**, with no solution found. All76,714 tiles completed and the ledger audit passed. It used four workers initially and twelve after the measured resource upgrade. No campaign writer remains active; follow-up monitoring is paused. See [the completed report](campaign_report.md). The commands below are available for a deliberate future bounded session; no automatic restart has been scheduled.

## Start and inspect

Run these commands from the package directory:

```sh
cd "."
python3 launch_campaign.py start --directory runs/campaign --hours 2 --workers 12
```

The command above selects twelve workers; omitting the worker argument still uses the original four-worker default. The launcher detaches the campaign from the terminal and writes its PID and command to `runs/campaign/process.json`. Output goes to `process.log`. Four workers gave approximately 3.8 times the throughput of one in the recorded short, matched workload; sustained performance can differ with temperature and other applications.

Inspect progress while the campaign runs:

```sh
python3 campaign.py status --directory runs/campaign
cat runs/campaign/status.json
```

After the process has finished, independently audit the ledger:

```sh
python3 campaign.py audit --directory runs/campaign
```

The current audit CLI issues multiple read queries without a single transaction snapshot, so use it after the writer stops. A live audit must explicitly open a read transaction first; otherwise an intervening completed tile can produce a transient accounting mismatch. The controller's own startup and final audits run with exclusive writer ownership.

The `status` command reads database totals and labels its own output `inspection`. The last writer-reported run state is in `status.json`, refreshed about every ten seconds and at session exit. A saved status or PID alone does not prove that the process is still alive.

## Pause, continue, and stop

```sh
python3 launch_campaign.py pause --directory runs/campaign
python3 launch_campaign.py resume --directory runs/campaign
python3 launch_campaign.py stop --directory runs/campaign
```

Pause and stop use marker files. They stop new scheduling while in-flight tiles finish or reach their worker timeout, normally at most thirty seconds. `resume` removes the pause marker; it does not launch a new process. Time spent paused still consumes the current session budget.

After a completed session, `start` gives the same ledger another bounded session and continues unfinished work. After an explicit stop, deliberately remove its marker first:

```sh
rm -f runs/campaign/STOP
python3 launch_campaign.py resume --directory runs/campaign
python3 launch_campaign.py start --directory runs/campaign --hours 2 --workers 12
```

Only one writer may use a campaign directory. Changing the seed, generator geometry, tracked source, executable, or PARI library causes restart to refuse the old ledger. Keep these unchanged during a run; do not run `build.py` against the active package. A new directory starts a new ledger from index zero and can repeat work from another campaign. A failed job blocks restart until its error is investigated.

## Resource controls

The detached launcher keeps the Mac awake against **idle sleep** with `caffeinate -i -w PID`, ending that assertion when the campaign exits. It does not prevent lid closure, shutdown, or process termination. Add `--allow-idle-sleep` to the launch command to omit this behavior.

The campaign checks battery state about every thirty seconds. Below **25%**, when discharging or not on AC power, it pauses new scheduling; it resumes when the condition clears, provided the session has time remaining. This depends on `pmset` supplying readable battery information. Workers use a lower scheduling priority when the system permits it.

For advanced controls, run the controller directly in the foreground:

```sh
python3 campaign.py run --directory runs/campaign --hours 2 --workers 12 \
  --target-seconds 1 --timeout 30 --max-count 10000000 --battery-floor 25
```

This direct command does not itself create an idle-sleep assertion. `--workers` may be 1–32, subject to the machine's CPU count (15 logical CPUs here). Each session may be at most 24 hours. `--max-jobs` provides an additional finite job budget. `--box-only` changes campaign geometry and therefore needs a separate directory from a mixed campaign.

## What the scheduler learns

The search uses two deterministic coefficient families: a bounded lattice box and a thin family near the real cancellation plane of the cubic norm. Both use ideal-class multipliers 1, 5, and 25. Index permutations spread successive tiles through their finite domains without repeating an index within a context.

The current research allocation is fixed: 65% of allocated worker time to the box, 35% to the plane, divided equally among the three multipliers. Within each, ratio bands `(0,64]`, `(64,256]`, and `(256,4096]` receive weights 70%, 20%, and 10%. These are research choices, not estimated solution probabilities.

Within each context, an upper-confidence-bound policy compares the logarithm of measured input throughput for fixed versus adaptive prime-filter ordering. It initially tries each policy at least three times and retains exploration thereafter. Adaptive workers test all primes on common periodic calibration samples and reorder them by observed rejection counts. Batch sizes adapt toward approximately one second. Timed-out tiles larger than 128 inputs split into two exact subintervals and are retried.

This is learning **execution cost**. It does not learn that an unsuccessful mathematical family is unlikely to contain a solution, retrain a neural network, or change the research allocation according to inferred discovery odds.

## What is safely removed

- Exact feasibility modulo 243, parity, and square-residue tests eliminate impossible candidates before arbitrary-precision checking.
- For intervals containing at least 1,024 quotient positions, a residue wheel enumerates the same surviving quotients directly. It uses period 243 or 486 according to parity. Direct and wheel implementations remain available for comparison.
- Sign symmetry skips a coefficient triple only when its opposite belongs to the same finite generator domain. They represent the same curve. The canonical representative may lie in a tile that has not yet been visited.
- The workers omit the reported previous search regions: minimal coordinate at most 10¹⁷, and the rectangle `D ≤ floor(10¹⁹/54), |z| ≤ 10¹⁹`. This campaign relies on the historical coverage report; it does not independently certify that earlier distributed computation.

Final checks use PARI integers. The Python controller independently checks every complete hit's cube identity, coordinates, norm, assigned band, and deterministic generator index. A valid cube identity recovered from incomplete worker output is retained separately without counting that tile as complete.

The norm approach follows [Grantham–Walsh](https://arxiv.org/abs/2211.12149); the established search machinery and historical frontier are described by [Booker–Sutherland](https://arxiv.org/abs/2007.01209). This package is not a full implementation of their optimized exhaustive search.

## Ledger and result meaning

`campaign.sqlite3` stores reserved tiles, completed statistics, unfinished jobs, policy measurements, events, and verified solutions. SQLite uses WAL and full synchronous commits. The audit checks disjoint, gapless reservations, database integrity, and totals reconstructed from completed jobs. Reservation does not mean completion. Interrupted running jobs return to pending on restart.

There is **no global per-curve database**. For this exact production geometry, [the non-overlap certificate](NONOVERLAP.md) proves that completed tiles do not repeat `(D,r,z)` candidate positions: ideal classes and unit bounds separate surviving generators, and ratio bands separate z values. The same `(D,r)` can appear in different bands, so `curve_checks` still counts interval attempts rather than distinct curves. This certificate does not automatically cover other configurations, calibration runs, or repeated partial work after interruption. `unsupported_D` and `noninvertible_C` count unhandled inputs; they are not proofs of impossibility. Coverage remains selective and does not exhaust a coordinate-height box or every ideal class representative at a finite height.

On a verified solution, the campaign stops scheduling, drains in-flight work, writes `SOLUTION.json`, and retains the solution in SQLite. Otherwise it exits with an audited record of completed and unfinished work. A session ending with no solution does not establish that 114 has no solution.

## Verification evidence

The package includes reproducible checks and their JSON records:

| Evidence file under `runs/` | What was checked |
|---|---|
| `campaign-worker-validation.json` | All 662 known-curve solution sets agree with GP; 365 independent integer intervals; endpoints, split tiles, bands, and input guards |
| `quotient-wheel-validation.json` | Identical visited quotient sets over 5,832 intervals and 14.55 million positions, including signed boundary cases; real fixed/adaptive tile equivalence |
| `box-symmetry-validation.json`, `plane-validation.json` | Exact counterpart membership and preservation of complete small-domain candidate sets; rounding boundaries for the plane |
| `campaign-worker-ubsan.json` | Undefined-behavior sanitizer regression suite |
| `launcher-validation.json` | Detached launch survives launcher exit; all 96 tiles complete at the deadline with an audited ledger |
| `controller-validation.json` | Protocol rejection, timeout splitting, interrupted-job recovery, exclusive writer locking, restart, and hit-routing fault tests |
| `campaign-performance.json` | Matched policy timings and 1/2/4-worker scaling; a local calibration |

Controller positive-routing fault tests use an explicitly injected verifier and are not solutions of 114. Known-curve recovery tests supply the curves; they validate recovery rather than blind discovery. These are substantial finite tests, not a formal proof of the entire program or a validated prediction of success.

## Next experiments and mathematical findings

See [CURRENT_CAMPAIGN.md](CURRENT_CAMPAIGN.md) for the running implementation and separately validated experiments. The signed-sum filter miner, norm-shell inversion worker, and unit-shape proposal were developed during the first production run. They are not integrated into its frozen worker or scheduler. Benchmark and validate a new version before adopting them; preserve the first ledger and distinguish overlapping work.

## Wider parallelism upgrade

The user requested more compute. After a clean stop at 7,026 completed tiles with no unfinished work, identical workloads were compared at 4, 8, 12, and 15 workers. Twelve were fastest, with 2.49× the measured throughput of four; fifteen were slightly slower. Production resumed at twelve workers with the original deadline. Only the operational worker cap changed in the controller; an exclusive-lock migration recorded the old and new source hashes, preserved all reservations, and verified unchanged mathematical worker hashes. Controller fault/restart tests passed again. Evidence: `runs/wide-parallelism.json` and `runs/parallelism-upgrade.json`.
