# Source, live data, and deployment branches

`main` contains the research, application, mathematical kernels, workflow code,
and tests. Its existing generated files are a frozen bootstrap snapshot for
reproducible tagged builds. They are not the live ledger, and the verifier no
longer commits updates to `main`.

[`cluster-data`](https://github.com/Kuberwastaken/math-gambling/tree/cluster-data)
contains the authoritative verified ledger, current model, and timestamped Mac
observations. Its README is
rendered from the current `main` README template, with the live data overlaid.
Generated-data links stay relative to this branch; links to code, research,
and documentation point to `main`.

[`gh-pages`](https://github.com/Kuberwastaken/math-gambling/tree/gh-pages) contains
only the built site. After publishing that branch, a separate deploy job checks
out its exact commit and uploads those checked-out files to GitHub Pages.
The deployed bytes therefore come from `gh-pages`, not from the source build
directory. GitHub Pages uses the Actions deployment service, which avoids
depending on whether a bot commit triggers an automatic branch build.

The verifier responds to eligible issue events and keeps its hourly fallback.
Deployment is batched at minutes **7, 27, and 47 of each hour**, plus explicit
manual dispatch. There is no deployment trigger for each bank, workflow
completion, or source push. GitHub's scheduler and queue can delay a run.
Concurrency permits an active deployment to finish and a later run to queue.

## Trust boundary

Both workflows first check out `main`. `tools/branch_state.py overlay --fetch`
fetches a single `cluster-data` commit, validates its tree, and imports only:

- `data/cluster.json`, `data/strategy.json`, `data/policy-config.json`
- `data/receipts/`, `data/coverage/`, `data/math-coverage/`
- `data/readme-progress.svg`, `data/learning/`
- `data/mac.json`, `data/mac-history.json`

The data branch may also contain a generated `README.md`, but it never replaces
the trusted template in the working checkout. Executable files, symlinks,
submodules, and paths outside this list are rejected. No script or workflow is
loaded from `cluster-data`. The static `site-config.json` and
`runner-release.json` remain owned by `main`. The two Mac files on `main` are
frozen bootstrap observations; live publishers only update `cluster-data`.
During migration, an overlay preserves that frozen pair if **both** Mac files
are absent from the data branch. A partial pair is rejected. Once the pair is
present, both files come from the captured data commit. This exception does not
apply to the ledger, coverage, model, or any other generated path.

An overlay validates the full referenced coverage snapshot and requires its
task IDs and sequence numbers to match the accepted-task ledger. It replaces
the generated paths, including removal of retired generated files, while
leaving source files and Git's normal index alone. Any attempted overlay
invalidates the previous publication token; only complete success writes a
new token recording the exact source and data commits.

Publication constructs a tree with a separate temporary Git index. Data
snapshots can append accepted task and discovery records but cannot modify or
delete existing ones. Mutable issue audits and models may advance. A new data
commit has the captured data commit as its parent. A non-fast-forward push
fails; the workflow does not force, rebase, or merge ledger files. The next run
must read current authoritative state and process pending receipts again.

Mac publication uses a separate temporary clone of `cluster-data` and can
change only the two observation files. It executes the installed, reviewed
exporter and receiver, never code from that data clone. It merges published
history under the 300-sample cap, rejects stale or regressing observations, and
rebuilds from the latest data tip after a rejected ordinary push. A concurrent
Mac advance also makes a verifier's stale data push fail normally; it cannot
silently overwrite a newer observation. Mac-only commits do not regenerate the
model or cluster README. The next scheduled Pages run includes them.

The optional mathematical coverage exporter processes at most 32 tasks within
a 15-second budget per verifier run. Export failure does not discard verified
task coverage; the exporter retains its last completed boundary and error
details. The generated README is built in temporary staging, never written
back to the `main` README.

## One-time migration

An operator must first pause the old verifier and wait for all its active runs
to finish. Capture and fetch its final `main` commit after that boundary. Do
not initialize while the old workflow can still publish another ledger update.

From the trusted checkout containing the new helper, initialize with that
explicit commit:

```sh
python3 tools/branch_state.py init-data --source-ref FINAL_MAIN_COMMIT
```

This prepares a local orphan commit and prints its commit ID without pushing.
Inspect the proposed tree and verify the captured task count. Run the same
command with `--push` to create the remote branch:

```sh
python3 tools/branch_state.py init-data --source-ref FINAL_MAIN_COMMIT --push
python3 tools/branch_state.py overlay --fetch
```

Initialization refuses to overwrite an existing `cluster-data` branch. Normal
overlay refuses a missing branch; there is no automatic fallback to a frozen
main ledger. Only the optional Mac pair has the pre-seeding exception above. After confirming the imported ledger, enable the new verifier and
manually dispatch Pages once. The first Pages run creates `gh-pages` as an
orphan branch. Future generated commits extend their own branch histories.

## Workflow and operator commands

```sh
# Read an authoritative remote snapshot into a trusted main checkout.
python3 tools/branch_state.py overlay --fetch

# A pinned, already fetched snapshot can also be inspected without networking.
python3 tools/branch_state.py overlay --ref DATA_COMMIT

# After trusted verification and report generation, prepare a data commit.
python3 tools/branch_state.py publish-data

# Publish only when ready; source/index remain unchanged.
python3 tools/branch_state.py publish-data --push

# Publish a successfully tested build to gh-pages.
python3 tools/branch_state.py publish-site --directory dist/math-gambling --push
```

The default repository is the helper's own checkout. `--repo PATH` and
`--remote NAME` are global options placed before the subcommand. Publication
commands print the commit, parent, changed status, and whether a push occurred.
No-push commands still create local Git objects for inspection. An overlay
modifies generated working files; run it in a disposable checkout when those
files contain unpublished local work.
