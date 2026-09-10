# Validation of the first public release

This records checks actually run on 10 September 2026. It is not a formal verification or a guarantee of finding 114.

## Exact search and receipts

- 243 deterministic tasks matched completely between the JavaScript and Python implementations: 34,824 root intervals, 47,544,575 logical quotient positions, and 84 exact square tests.
- Python tests cover exact roots, integer reconstruction, residue filtering, fixed task bounds, complete small domains, known-positive cases for other targets, bank limits, and durable local resumption.
- Two task digests extracted from an actual browser run independently matched Python replay.
- A two-worker local launch-validation run completed 128 real tasks and produced a bank. Feeding that bank through a local fixture of a GitHub issue payload independently replayed all 128 tasks, credited 238,592 coefficient inputs, and produced two calibration epochs in 13.37 seconds. Resubmitting it used zero additional replay slots and earned no additional credit. This exercised the actual ingestion and aggregation code locally, not GitHub's API or hosted Actions. The initial local fixture did not change production data; the later hosted validation below did.

## Banking and calibration

17 adversarial/backend tests cover altered digests, untrusted counters, duplicate task credit, actual GitHub author attribution, exact positive preservation, partial-bank recovery, operational timeouts, timestamp pagination ties, mutable pagination reconciliation, and frozen policy epochs. Full negative replay is deliberately retained. Hashes alone do not prove CPU time or ownership of a machine.

## Browser behavior

The browser ran and stopped real computation: 434 finished tasks remained saved locally, and a 256-task bank was prepared from them. They were not silently posted. A separate Node VM harness executes the actual page code with controlled DOM, worker and storage hosts; it checks stopping while a task is in flight, draining before restart, delayed storage writes, double-start prevention, constructor failure, malformed saved profiles and time-budget expiry. This harness is not a substitute for real browser/storage testing.

Desktop and 390-pixel mobile layouts were visually inspected. After HTTPS publication, a separate live-origin browser run completed and durably saved 736 tasks, 1,378,304 coefficient inputs, 89,013 root intervals, and 263 exact tests before a clean manual stop. Those QA receipts remain unbanked; they are not included in public totals. The mobile home page had no horizontal document overflow. The working paper remained visibly labeled as a draft with blank result fields. Source links, internal anchors, the downloadable runner's required files and download checksums passed the static build audit.

## Research and Mac snapshot

The portable scientific archive contains 158 files with original and sanitized hashes. Forty-six archived Python sources parsed, eight native sources passed compiler syntax checks, and archive integrity/link checks passed. Full PARI dependency rebuilding and private-ledger replay were not performed as part of this site release.

Nine exporter tests check exact large integer counters, public-field allowlisting, no modification of the source campaign or database access, rejection of false identities, genuine bounded history, audit timestamps, monotonic snapshot updates, safe output location, and bounded allowlisted model calibration rows.

## Operational limits

The initial Mac push was blocked. The user then identified `ai-vps` as the designated personal-work environment. Normal Git publication from that host succeeded. The private hosted build passed, and [launch-validation bank #1](https://github.com/Kuberwastaken/math-gambling/issues/1) was independently accepted by [GitHub Actions](https://github.com/Kuberwastaken/math-gambling/actions/runs/34465793815): 128 tasks, 238,592 inputs, zero hits, and two calibration epochs. Four additional tests cover snapshot forwarding integrity, fixed file paths, and stale or regressing observations. See [release status](RELEASE_STATUS.md) for deployment checks.

Banked data is only credited after independent replay. A receipt can be copied, and a digest is not proof that a donor used a processor. Empty-shell tasks can be cheaper than other tasks. The leaderboard counts context-specific coefficient inputs, not CPU instructions or discovery probability. Full replay may bottleneck the verifier; public scaling has not yet been established. GitHub Actions may delay scheduled jobs, and the public Mac report is a timestamped snapshot rather than a direct connection.

## Research-table redesign, 10 September 2026

The browser now starts anonymously with “Let it Ride” and has three live duty targets for one worker: Casual (25%), Committed (50%), and All in (90%). The arbitrary session deadline was removed; the existing 4,096-unbanked-receipt safety limit remains. Lifecycle tests check a run aged by 24 hours, changing duty without replacing the worker, and the existing stop/drain and storage barriers. Browser work still requires an explicit click and no QA receipt was posted externally.

A real preview session completed 3,662 additional tasks and preserved all 434 earlier local receipts at the 4,096-task limit. A separate fresh localhost origin completed and saved 4,096 tasks, 532,920 curve intervals and 1,557 exact tests before the same guard stopped it. This exercised the actual worker, live charts and IndexedDB; preview receipts remain separate from public leaderboard credit.

The homepage now presents a monochrome research layout, explicit empty leaderboard ranks, the full implementation manuscript, recorded Mac cumulative checks and inter-snapshot pace, its 81-context holdout scatter, and replayable community allocation epochs. Display alias “Kuber” is a presentation setting keyed to the actual GitHub submitter; original receipts and credited counts are preserved. Plots use recorded counters and policy revisions. Uniform epoch zero is labeled as a prior. The visualization regression test covers filter conservation, state/reset behavior, finite chart geometry, historical selection and the prior. Mobile (390 pixels) and desktop layouts were visually inspected; all four global chart SVGs load without local work and mobile document width stays at 390 pixels.

The numerical odds illustration is explicitly conditional: with rho = 0.0584593 and C = 270 reference-core-years, P(t) = -expm1(-rho * log1p(t/C)). For t = 1/365.25 reference-core-years, P ≈ 5.92785e-7 (roughly one in 1.7 million). This extrapolates the density/Poisson model and the archived sandbox reference calibration; it is not a measurement of browser or native-sampler success probability, a bound, or an ETA. It never increases from donor counters.

Validation after this revision: all 243 JavaScript/Python differential tasks, all 38 Python tests, lifecycle checks, visualization checks, and 261 internal link/asset/download checks passed. Assets are content-versioned to prevent an older cached UI module from loading with the new markup.

## Unified game and deferred attribution

The next UI revision combines the processor control, enlarged roulette map and current hand in one game area. Identity fields are now offered when banking. Every new worker session captures an anonymous receipt owner; the selected bank alias is separate from the original exact task result. Regression checks cover invalid attribution, stable prepared bank digests, alias changes retaining prior banks and raw tasks, and priority-result retention while adding attribution. Neither computed coverage nor authenticated GitHub submitter credit changes with a local name preview.

A clean-origin real browser run started with a single click, saved 47 tasks, stopped cleanly, and prepared a local bank as “Game QA” with the optional handle normalized from “@game-qa”. The bank contained all 47 saved task claims and the manuscript preview reflected the selected alias. No bank was posted. A second short session also saved and stopped normally. Desktop inspection confirmed the unified surface is approximately 846 pixels wide with a 379-pixel roulette wheel at a 1280-pixel viewport. The favicon is now a matching red/black roulette mark. HTML and downloadable LaTeX use the same combined contributor line; discovery fields remain blank.
