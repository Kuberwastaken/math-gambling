# Operating math-gambling

The site is a static GitHub Pages project at `https://kuber.studio/math-gambling/`. It inherits the existing custom domain from the account's user site. There is deliberately no project `CNAME` file: a domain cannot include a path.

## Publish

The `Publish math-gambling` workflow checks out trusted `main` code, overlays the current `cluster-data` commit, and tests and builds the site. Publication is batched at minutes **7, 27, and 47 each hour**, plus manual dispatch; banks and source pushes do not trigger individual deployments. GitHub scheduling and queue delays can shift those times. The build publishes `gh-pages`; a separate deploy job checks out that exact built commit and uploads it to GitHub Pages. No code from the data branch, an issue, or a fork artifact is executed. See [branch operation and migration](BRANCHES.md).

`main` retains a frozen bootstrap snapshot for reproducible source releases. Verified ledgers, models, reports, and Mac observations advance on `cluster-data`, so routine computation no longer creates source-branch history.

## Bank and verify

Participants copy one bank into a GitHub issue; the local runner can also submit with explicit `--submit` using its own authenticated GitHub CLI. The account that creates the issue receives first-accepted unique-task credit. No repository credential enters the web client. The shared leaderboard counts replay-verified coefficient inputs and tasks, never unverified elapsed time. Different contexts can revisit coefficient values; the leaderboard's unit is an input checked in its canonical context, not globally unique integer triples or physical CPU instructions.

Verification responds to eligible opened or edited issues and also runs hourly at 17 minutes past the hour, subject to GitHub scheduling delays. It can also be dispatched manually. It has bounded network/replay budgets, resumable banks, recurring queue reconciliation, idempotent canonical task deduplication, and visible operational failures. Full replay of negatives repeats the calculation and limits scaling; no linear distributed speedup has been established.

A hash binds a deterministic result. It is not proof of time spent or ownership of a processor. Someone with an existing valid receipt can copy it or compute a cheap known result. Duplicate task IDs earn no extra credit, but this system cannot certify discovery priority against every adversary. Any significant positive result requires personal follow-up and independent reproduction before final attribution or authorship.

## Mac snapshots

The live Mac campaign remains in its existing directory; do not move its database or edit its frozen binaries. Export only the public allowlist:

```sh
python3 tools/export_mac.py --source /path/to/three-cubes-lab --output data
```

The existing hourly campaign monitor can publish the report with:

```sh
python3 tools/publish_snapshot_vps.py --source /path/to/three-cubes-lab --push
```

The reviewed exporter reads the Mac campaign locally and sends only the two public JSON files over authenticated SSH to the user-designated personal-work host `ai-vps`. Its receiving helper must be installed at `/Users/kuber.mehta/Projects/math-gambling/tools/publish_snapshot_vps.py`. Git publication runs there through its normal configuration. No Mac Git hook is changed. The receiver clones only `cluster-data` into a temporary directory and can commit only `data/mac.json` and `data/mac-history.json`; it does not touch the development checkout or live ledger. It runs its installed, reviewed Python code, never code from the data clone. Both files are validated together; symlinks, incomplete pairs, stale observations, counter regressions, and conflicting historical counters are rejected. Existing chart samples are merged with incoming observations and compacted at the documented 300-sample limit. After a concurrent publication wins the push race, the receiver fetches the new tip and rebuilds the two-file commit against its latest history, for up to three attempts. It never rebases stale snapshot bytes or force-pushes. A missing `cluster-data` branch fails closed. The first snapshot may seed both missing Mac files; before that first seed, Pages uses the frozen main pair. The direct `publish_snapshot.py --source PATH --push` publisher uses the same receiver logic. Without `--push`, either publisher only validates in temporary storage. No scheduler is installed by this script. A stale snapshot stays timestamped and becomes visibly overdue after two hours. GitHub Actions cannot read the Mac directly.

## Verification and preservation

Run `npm test`, `python3 tools/build_site.py`, and `python3 tools/check_site.py` before publication. Keep the original ledgers, journals and source identity records locally. The scientific archive documents its intentional omission of multi-gigabyte runtime data. Its original/source hashes provide provenance; sanitized archived bytes have their own hashes.

For a suspected solution, stop scheduling that client, preserve its receipts and journals, verify the full integer identity independently, and record the authenticated submission and discovery evidence. Do not fill the paper's result or finder fields from a counter, near miss, unverified bank, or locally entered name.
