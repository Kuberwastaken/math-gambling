# math-gambling

Stake some processor time on `x³ + y³ + z³ = 114`.

An open computational mathematics experiment by Kuber Mehta. No money, token, payout, known odds, or promise of a breakthrough. A valid integer triple would be interesting mathematics. An unsuccessful computation still produces an auditable record of exactly what was checked.

The intended website address is **https://kuber.studio/math-gambling/**. Publication is pending a managed Git policy exception; see [release status](docs/RELEASE_STATUS.md). This repository contains the website, portable search workers, cluster protocol, and prior research.

## What runs

- **Browser:** opt-in Web Worker, exact BigInt arithmetic, conservative CPU duty cycle, explicit stop, bounded jobs, durable local outbox, manual GitHub bank-in.
- **Local:** Python standard-library runner with explicit time/worker limits, exact integer arithmetic, resumable receipts, manual banks and optional explicit CLI submission.
- **Bank-in:** paste a compact receipt into a GitHub issue. The authenticated issue author supplies leaderboard identity. Digests detect changed results; independent replay, rather than the hash alone, validates coverage.
- **GitHub Actions:** independently replay bounded contributions, deduplicate coverage, preserve exact discoveries, and recalibrate a cost scheduler every 64 verified unique tasks. There is always an exploration allocation; a learned score cannot discard a mathematical candidate.
- **Mac research campaign:** the existing native search continues separately. Public snapshots state their observation time and remain separate from volunteer counts.

## Run the site locally

Requires Python 3.11+ and Node.js 22+; the static site has no npm dependencies.

```sh
python3 tools/build_site.py
python3 -m http.server 4173 --directory dist
```

Visit http://localhost:4173/math-gambling/. Build output deliberately preserves the GitHub Pages project subpath.

```sh
npm test
```

## Scope and honesty

Our finite coefficient domains do **not** cover all integer triples, all modular roots, or a complete coordinate-height box. Client task selection is randomized; duplicate work can occur and is counted once after verification. Browser and native campaign work can overlap. A huge counter is not a number of independent chances to win. Scheduling learns execution cost, not a calibrated probability of discovering a solution. Neither global optimality nor discovery in finite time is promised.

See [the protocol](docs/PROTOCOL.md), [cluster operation](docs/CLUSTER.md), [research](docs/RESEARCH.md), and [archive scope](docs/ARCHIVE.md). The paper is a clearly marked working draft with the result, discovery date and finder attribution blank.

## Attribution and license

The mathematical approaches are credited to Booker–Sutherland, Grantham–Walsh, and the sources in the research archive. This independent project is not endorsed by them. Original project software is GPL-2.0-or-later; upstream material retains its own notices. See `research/archive/NOTICE.md` and the archive manifest.
