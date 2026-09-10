# Operating math-gambling

The site is a static GitHub Pages project at `https://kuber.studio/math-gambling/`. It inherits the existing custom domain from the account's user site. There is deliberately no project `CNAME` file: a domain cannot include a path.

## Publish

The `Publish math-gambling` workflow tests and builds the default branch, then deploys `dist/math-gambling`. A push, manual dispatch, or completed trusted `Verify community compute` workflow starts a publish. This explicit `workflow_run` dependency is necessary because commits made with `GITHUB_TOKEN` do not trigger another ordinary push workflow. Deployment rechecks current default-branch code, never a submitted issue's code or a fork artifact. A verifier failure may still have safely committed useful results; those trusted snapshots can publish while the failed run stays visible.

## Bank and verify

Participants copy one bank into a GitHub issue; the local runner can also submit with explicit `--submit` using its own authenticated GitHub CLI. The account that creates the issue receives first-accepted unique-task credit. No repository credential enters the web client. The shared leaderboard counts replay-verified coefficient inputs and tasks, never unverified elapsed time. Different contexts can revisit coefficient values; the leaderboard's unit is an input checked in its canonical context, not globally unique integer triples or physical CPU instructions.

Verification runs hourly at 17 minutes past the hour, subject to GitHub scheduling delays. It can also be dispatched manually. It has bounded network/replay budgets, resumable banks, recurring queue reconciliation, idempotent canonical task deduplication, and visible operational failures. Full replay of negatives repeats the calculation and limits scaling; no linear distributed speedup has been established.

A hash binds a deterministic result. It is not proof of time spent or ownership of a processor. Someone with an existing valid receipt can copy it or compute a cheap known result. Duplicate task IDs earn no extra credit, but this system cannot certify discovery priority against every adversary. Any significant positive result requires personal follow-up and independent reproduction before final attribution or authorship.

## Mac snapshots

The live Mac campaign remains in its existing directory; do not move its database or edit its frozen binaries. Export only the public allowlist:

```sh
python3 tools/export_mac.py --source /path/to/three-cubes-lab --output data
```

The existing hourly campaign monitor can publish the report with:

```sh
python3 tools/publish_snapshot.py --source /path/to/three-cubes-lab --push
```

This uses a temporary clean checkout and only commits `data/mac.json` and `data/mac-history.json`; it does not touch the development checkout or live ledger. Concurrent updates are rebased, never force-pushed. No scheduler is installed by this script. A stale snapshot stays timestamped and becomes visibly overdue after two hours. GitHub Actions cannot read the Mac directly.

## Verification and preservation

Run `npm test`, `python3 tools/build_site.py`, and `python3 tools/check_site.py` before publication. Keep the original ledgers, journals and source identity records locally. The scientific archive documents its intentional omission of multi-gigabyte runtime data. Its original/source hashes provide provenance; sanitized archived bytes have their own hashes.

For a suspected solution, stop scheduling that client, preserve its receipts and journals, verify the full integer identity independently, and record the signed submission and discovery evidence. Do not fill the paper's result or finder fields from a counter, near miss, unverified bank, or locally entered name.
