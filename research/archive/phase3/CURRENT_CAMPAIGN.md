# Running: phase3 parallel search

Resumed at **12:01 IST on 9 September 2026** with **12 local workers**. At 12:03:17 IST, the new release had completed **1,957 new tiles**, **5,133,721,584 new curve-interval checks** and **983,244 exact final tests**. No solution has been found. These counts cover selective generator inputs and quotient bands, not an exhaustive height box.

All **89,685** phase2 completed tiles and all81 cursors were preserved. The live audit passes; source hashes match the migrated configuration. Fresh timing calibration completed across all81 contexts and its held-out gate enabled the model. The scheduler reserves40% exploration time and60% model allocation after bootstrap; no model score eliminates a mathematical candidate.

The latest actual-workload replay was **1.578× faster** across six paired12-worker runs. A separate workload dominated by long quotient bands stayed near parity. See [performance evidence](PERFORMANCE.md) and [actual replay data](actual-allocation-benchmark.json).

The new release passed all662 known-solution fixtures, independent candidate/root comparisons over all81 strata, arithmetic sanitizer checks and durable-discovery fault tests. See the [release description](README.md), [independent review](SAFETY_REVIEW.md) and [startup checkpoint](runs/startup-checkpoint.json). No100% correctness or solution-time guarantee is claimed.

The current process is PID[redacted]; its24-hour session is a checkpoint. The existinghourly follow-up is ACTIVE and authorized to audit and continue normal sessions. It stays quiet while progress is healthy and respects any later user stop/pause instruction. Low-battery protection remains enabled; lid closure or shutdown can interrupt execution. No cloud compute is used.

[Live status](../../../docs/ARCHIVE.md) · [Process log](../../../docs/ARCHIVE.md) · [Migration certificate](runs/campaign/migration-certificate.json)

To request a graceful stop: `python3 phase3/launch_campaign.py stop`, from the package directory. Do not edit frozen source/binary files while the controller is running. The old phase2 STOP marker intentionally remains; it protects the archived campaign.

The first24-hour phase3 session ended normally on10 September2026 with1,249,973 cumulative completed tiles, no unfinished tiles, and no solution. Its independent ledger/source audit passed. The authorized next24-hour session began at12:51 IST on10 September2026 from the same preserved ledger; PID[redacted] is running with12workers. See [the completed-session checkpoint](runs/campaign/checkpoints/session-2026-09-09-complete.json) and [verified continuation](runs/campaign/checkpoints/session-2026-09-10-started.json).
