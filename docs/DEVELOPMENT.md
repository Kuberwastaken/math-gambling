# Developing and verifying Math Gambling

These instructions build the website and maintain the repository. To contribute search compute, use [the local runner setup](RUNNER_SETUP.md).

## Local website

Requires Python 3.11+ and Node.js 22+. The npm lockfile pins the build-time Markdown and KaTeX packages. The published pages include their fonts and need no external rendering service.

```sh
npm ci --ignore-scripts
python3 tools/build_site.py
python3 -m http.server 4173 --directory dist
```

Open http://localhost:4173/math-gambling/. The build preserves the GitHub Pages project subpath.

```sh
npm test
python3 tools/check_site.py
```

The suite includes cross-language arithmetic comparisons, known-positive regressions, persistence and worker lifecycle tests, replay and attribution checks, exact coverage publication, portable-runner checks, and research-rendering tests. These are finite engineering evidence, not a proof of the whole execution environment or a guarantee that the chosen search domain contains a solution.

## Generated campaign state

The trusted aggregator reads accepted replay records and creates the public totals, frozen cost policy and exact completed-task index. The following commands do not contact external services:

```sh
python3 tools/aggregate.py
python3 tools/readme_charts.py
python3 tools/readme_snapshot.py
```

`readme_snapshot.py` replaces only the region between `MATH_GAMBLING_SNAPSHOT:START` and `MATH_GAMBLING_SNAPSHOT:END` in the root README. Keep manual narrative outside those markers. A missing, repeated or reversed marker pair is an error. Given identical input JSON and narrative, repeated generation produces identical bytes.

The generated counters use accepted task units. Leaderboard handles require authenticated provenance in the aggregate. Alias text is escaped for Markdown; optional alias URLs are restricted to safe HTTP(S) destinations. Mermaid labels contain only validated numeric state and fixed context IDs. Neither raw issue text nor a contributor alias is interpolated into Mermaid code.

Issue events and hourly reconciliation run trusted default-branch code, replay bounded submissions and refresh the generated chart and README snapshot. Only accepted unique tasks enter the shared exclusion index; the scheduler remains frozen between 64-task epoch boundaries. A failure cannot promote a statistical preference into a mathematical exclusion.

## Source and output

`web/` contains the static interface and browser kernel, `tools/` the Python runner, verification and publication utilities, and `tests/` the regression checks. `data/` is published campaign state and accepted replay evidence. Research notes and earlier implementations are retained under `docs/` and `research/archive/`.

Build output lives in ignored `dist/math-gambling/`. The runner ZIP has sorted paths and fixed archive metadata so rebuilding the same committed release inputs is reproducible. Updating a runner release requires its own versioned release workflow and compatibility checks; changing the README is not an engine-version change.
