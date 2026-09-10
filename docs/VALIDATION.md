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

Desktop and 390-pixel mobile layouts were visually inspected. The mobile home page had no horizontal document overflow. The working paper remained visibly labeled as a draft with blank result fields. Source links, internal anchors, the downloadable runner's required files and download checksums passed the static build audit.

## Research and Mac snapshot

The portable scientific archive contains 158 files with original and sanitized hashes. Forty-six archived Python sources parsed, eight native sources passed compiler syntax checks, and archive integrity/link checks passed. Full PARI dependency rebuilding and private-ledger replay were not performed as part of this site release.

Nine exporter tests check exact large integer counters, public-field allowlisting, no modification of the source campaign or database access, rejection of false identities, genuine bounded history, audit timestamps, monotonic snapshot updates, safe output location, and bounded allowlisted model calibration rows.

## Operational limits

The initial Mac push was blocked. The user then identified `ai-vps` as the designated personal-work environment. Normal Git publication from that host succeeded. The private hosted build passed, and [launch-validation bank #1](https://github.com/Kuberwastaken/math-gambling/issues/1) was independently accepted by [GitHub Actions](https://github.com/Kuberwastaken/math-gambling/actions/runs/34465793815): 128 tasks, 238,592 inputs, zero hits, and two calibration epochs. Four additional tests cover snapshot forwarding integrity, fixed file paths, and stale or regressing observations. See [release status](RELEASE_STATUS.md) for deployment checks.

Banked data is only credited after independent replay. A receipt can be copied, and a digest is not proof that a donor used a processor. Empty-shell tasks can be cheaper than other tasks. The leaderboard counts context-specific coefficient inputs, not CPU instructions or discovery probability. Full replay may bottleneck the verifier; public scaling has not yet been established. GitHub Actions may delay scheduled jobs, and the public Mac report is a timestamped snapshot rather than a direct connection.
