# Current worker recommendation: twelve

The user requested a wider scaling test. The initial four-worker campaign stopped at an audited checkpoint, then all levels processed identical 48-tile workloads, with three repetitions and randomized order.

| Workers | Median workload seconds | Throughput versus four |
|---|---:|---:|
| 4 | 1.4273 | 1.00× |
| 8 | 0.7952 | 1.79× |
| 12 | 0.5731 | 2.49× |
| 15 | 0.6018 | 2.37× |

Twelve were fastest. Every candidate, root, quotient, rejection, and hit fingerprint matched across all 576 calibration tiles. The test took10.21 elapsed seconds and73.40 CPU seconds; these repeated checks are not new coverage. The campaign resumed with twelve workers and its original deadline, using its existing disjoint tile ledger. Short calibration results do not guarantee sustained thermal performance. See `runs/wide-parallelism.json` and `runs/parallelism-upgrade.json`.

# Campaign execution calibration

The initial calibration recommended **four workers** for this Mac and workload. Four workers processed an identical mixed workload **3.80 times as fast as one**. This is a measured execution improvement, not an increase in the predicted density of solutions.

| Workers | Median complete workload time | Speedup over one |
|---|---:|---:|
| 1 | 1.3651 s | 1.000× |
| 2 | 0.7026 s | 1.943× |
| 4 | 0.3590 s | 3.802× |

The measured throughput increase from two to four workers was 95.7%, exceeding the predeclared 15% marginal-gain threshold. Each level had three repetitions, with randomized level order and randomized tile order. These short timings do not establish sustained thermal behavior during a multi-hour campaign.

The benchmark used twelve contexts: box and cancellation-plane generators, each multiplier 1, 5, and 25, and quotient-ratio bands `(0,64]` and `(256,4096]`. Each context had two warmups. Generator counts were adjusted to approximately 0.12 seconds per timed subprocess. The final worker-internal timings in the paired tests ranged from 0.0990 to 0.1256 seconds.

For every context, three fixed/adaptive pairs used **identical generator indices, count, permutation seed, bounds, and arithmetic family**. Their execution order was randomized with a fixed benchmark seed. Adaptive filter ordering was about **11.5–15.1% faster** in the longer quotient bands on these inputs. The low-band differences were only about **0.3–3.9%**; those small differences should not be treated as a strong result.

All 72 paired subprocesses and all nine scaling workloads passed matching checks for candidate counts, curve counts, quotient counts, exact square checks, hits, and mathematical rejection totals. The conservation identity counts every quotient position exactly once among the mod243 rejection, parity rejection, first rejecting prime, or exact test. Which prime rejected a position may change under reordering; the surviving exact-test workload must remain unchanged. Any discovered triple is independently checked with Python integer arithmetic.

The entire calibration consumed **22.26 CPU seconds and 17.53 elapsed seconds**, below its configured 55 CPU-second and 60 elapsed-second admission limits. It intentionally repeated work, so **none of these benchmark counts represents new campaign coverage**. The output is separate from the production campaign ledger.

The machine reported macOS 26.6.1, arm64, and 15 logical CPUs. The sandbox did not expose the CPU brand, physical-core count, or RAM size; those fields are null rather than guessed. Hardware metadata, load averages, raw timings, all statistics, source hashes, and binary hashes appear in `runs/campaign-performance.json`. Source and binary hashes were unchanged between the start and end of calibration.

Re-run after material backend changes or changes in available machine capacity:

```sh
python3 benchmark_campaign_performance.py
```

The script tests the existing built binaries and does not rebuild or launch production work. A failed or incomplete calibration records the failure and recommends one worker as a conservative fallback. Its policy timings estimate execution cost only; they provide no learned probability that a coefficient family contains a solution of 114.
