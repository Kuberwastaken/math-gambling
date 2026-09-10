# Phase3 independent optimization audit

9 September 2026. Finite correctness validation passed. Replaying the most recent actual production allocation showed **1.578× end-to-end acceleration** across six paired12-worker runs. Acceleration is workload-dependent: a separate tail-heavy mixture showed no overall improvement.

The reusable suite is `outputs/three-cubes-lab/phase3/validate_optimization.py`. Raw correctness evidence is `work/phase3-benchmark-correctness.json`; the combined performance evidence is `work/phase3-benchmark-final.json`. The final run reused the completed correctness artifact only after matching every native source and executable hash. All native hashes remained unchanged through the performance run. Frozen phase2 files and production binaries were not modified by this suite.

## Correctness evidence

- All81 configured geometry strata, with nonzero starts and alternating ordinary/extreme64-bit permutation seeds.
- 162 matched ordinary-binary comparisons: each stratum under fixed and adaptive filter policies. Mathematical counters, filter results, final filter order and verified hits agreed.
- 179,094 independent Python integer coefficient/norm checks,31,821 candidate traces and10,399 optimized modular-root traces. Each recovered root was independently verified by modular cubing.
- Separate temporary UBSan builds for full candidate tracing and ROOT-only tracing. Full candidate tracing intentionally disables row skipping; ROOT-only tracing independently exercised the actual optimized path, so the audit does not mistake the diagnostic fallback for the optimized implementation.
- Six complete small generator domains and36 exact lower/upper norm-shell endpoint cases.
- Nonzero-start tile additivity and disjoint quotient-band additivity, spanning approximately15million nominal quotient positions across three class-clearing factors.
-43 explicit quotient-interval cases, including19 known-positive fixtures, both forced engines and both filter policies, period boundaries and signed64-bit quotient endpoints. The Python oracle independently reconstructed769 positions surviving the base filters and19 exact-check survivors. The very large knownk=3 solution exercises large-integer hit reconstruction without scanning millions of unrelated quotients.
- Empty explicit quotient intervals were correctly rejected by both CLIs. An initial test expected successful empty work and was corrected to the actual documented interface behavior; no native discrepancy was found.

The backend independently ran the full662 known-curve corpus and its arithmetic microtests. That is complementary evidence reported by the backend; it is not counted as work of this suite.

## Paired performance

The calibration ran after the backend's tests completed, without a production campaign competing for CPU. It used nine geometry/band combinations at clearing factor5, both fixed/adaptive policies, three paired repetitions, randomized pair order and identical inputs. Both binaries were warmed first. All54 pairs completed, including process startup, output capture and parsing in the external timings. Repeated inputs are calibration only and earn no new-coverage credit.

| Offset band | Quotient band | Phase3 elapsed speed ratio, fixed/adaptive | Interpretation |
|---|---|---:|---|
|8–31 |0–64 |0.986× /1.028× |No clear gain |
|8–31 |64–256 |1.022× /0.972× |No clear gain |
|8–31 |256–4096 |0.964× /1.009× |No clear gain |
|128–511 |0–64 |1.228× /1.203× |Selective gain |
|128–511 |64–256 |1.229× /1.180× |Selective gain |
|128–511 |256–4096 |0.994× /1.002× |No clear gain |
|2048–8191 |0–64 |1.426× /1.423× |Selective gain |
|2048–8191 |64–256 |1.428× /1.463× |Selective gain |
|2048–8191 |256–4096 |1.011× /1.123× |CPU ratios only1.006–1.013×; external variation cautions against interpreting the larger elapsed ratio |

Ratios are old elapsed divided by new elapsed, so values above1favor phase3. Across this particular paired panel, the ratio of total old/new elapsed time was1.145× and the CPU ratio1.140×. These are not estimates of a universal or production-allocation gain.

## Mixed12-process test

The identical twelve-job workload covered all three classes and offset shapes, using27,712 rows and3,120,221,816 nominal quotient positions per run. Each implementation ran twice at one process and twice with twelve simultaneous processes. The eight run orders were randomized; all mathematical results agreed.

| Workload execution | Phase2 median | Phase3 median | Phase3 speed ratio |
|---|---:|---:|---:|
|One process |2.2531s |2.2202s |1.015× |
|Twelve processes |0.54754s |0.55716s |0.983× |

Twelve-process execution accelerated this workload roughly4.11× for phase2 and3.98× for phase3 relative to one process. The phase3 twelve-process result is about1.8% slower, with only two repeats and short runs; it does not demonstrate a stable regression or an improvement. The mixture was dominated by high quotient bands where the new arithmetic provides little benefit. Sustained thermal behavior and the controller's eventual allocation were not measured.

The performance pass took16.9wall seconds; paired and scaling jobs consumed approximately22.1measured worker CPU seconds, plus small warmups. No solution-search campaign was launched by this suite.

## Freeze recommendation

Following the mixed-workload result, the parent requested a new test of the unresolved practical question: whether the **actual recent allocation**, at its original job sizes, benefits. Selection was fixed as the last12 completed phase2 job IDs,89674–89685, with their original starts, row counts and permutation seed1142. Their historical job times were approximately0.86–1.14seconds. No job was selected or excluded on the basis of benchmark speedup. Most happened to be quotient band0–64, reflecting that recorded allocation.

Six paired12-worker replays used a balanced randomized AB/BA schedule, three of each order, seeded1142. Every mathematical counter and filter result matched the original ledger and the frozen implementation. Raw per-job native timings, full subprocess elapsed times, input records and pair order are preserved in `work/phase3-benchmark-actual-allocation.json`.

| Pair | Old full elapsed | New full elapsed | Speed ratio |
|---|---:|---:|---:|
|1 |0.97983s |0.59116s |1.657× |
|2 |0.92534s |0.61868s |1.496× |
|3 |0.94711s |0.59343s |1.596× |
|4 |0.92154s |0.59712s |1.543× |
|5 |0.92199s |0.58797s |1.568× |
|6 |0.94930s |0.58855s |1.613× |

The ratio of total full elapsed time was1.578×; the median paired ratio was1.582×; the ratio of total native CPU time was1.668×. All six pairs favored phase3. The replay took9.24wall seconds and used identical native hashes to the correctness audit. This is a short calibration of the recent recorded allocation, not a sustained thermal test or an estimate for every possible allocation. Every replay is repeated calibration work, not new search coverage.

The native changes are ready to freeze **for correctness within the tested finite interfaces and the backend's accompanying proofs**, with a demonstrated throughput benefit on the recent actual allocation. No discovered discrepancy requires a source change. Do not advertise a universal twelve-worker speedup, multiply timing ratios into discovery probability, or infer that omitted mathematical regions are unproductive. The controller may favor measured cost advantages while retaining its separately declared geometric coverage allocation.
