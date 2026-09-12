# Run Math Gambling locally

Release **v0.6.1** is a portable Python program for macOS, Windows and Linux. It uses the Python standard library, exact integer arithmetic, multiple worker processes and durable SQLite checkpoints. The Python fallback needs no compiler or extra packages. Version 0.6.1 also offers a faster Rust search kernel; the release has platform archives with a prebuilt binary, plus the portable source archive. Both use the same tasks and banking protocol.

Use a normal Python **3.11 or newer** installation with SQLite support. Download it from [python.org](https://www.python.org/downloads/) if needed. This is the portable volunteer client; the separate native C/PARI research campaign has different build requirements and performance.


For Rust, choose the release asset ending in your OS and architecture (`linux-x86_64`, `windows-x86_64`, or `macos-arm64`/`macos-x86_64`). Extract the entire archive and add `--kernel rust` to the runner commands below. The binary lives in `tools/bin/`. On macOS/Linux, if your unzip tool discarded executable permissions, run `chmod +x tools/bin/math-gambling-kernel`. Python 3.11+ still handles login, checkpoints and worker orchestration. Other architectures can use the Python fallback or [build the kernel from source](NATIVE_KERNEL.md).

Eligible negative banks now use random audits. Only actually replayed tasks earn verified credit; remaining claims are retained without coverage or model-training claims. [Details](NEGATIVE_AUDITS.md).

## 1. Download and extract

[Download runner v0.6.0](https://github.com/Kuberwastaken/math-gambling/releases/download/v0.6.0/math-gambling-runner-v0.6.0.zip). The [GitHub release](https://github.com/Kuberwastaken/math-gambling/releases/tag/v0.6.0) includes SHA-256 checksums and the setup guide. The archive contains a `math-gambling` folder with `tools`, `data` and these instructions. Keep that folder together.

On macOS or Linux, open Terminal. If you saved the ZIP in Downloads:

```sh
cd ~/Downloads
unzip math-gambling-runner-v0.6.0.zip
cd math-gambling
```

On Windows, open PowerShell:

```powershell
cd "$HOME\Downloads"
Expand-Archive .\math-gambling-runner-v0.6.0.zip -DestinationPath .\math-gambling-runner
cd .\math-gambling-runner\math-gambling
```

You can also extract the ZIP using your file manager, then open a terminal in the inner `math-gambling` folder that contains `tools` and `data`. If your Downloads folder has a different location, use its actual path. Do not run the Python file from inside an unopened ZIP.

## 2. Sign in and bank automatically

Install the [GitHub CLI](https://cli.github.com/) if you want automatic banking. On macOS with Homebrew, use `brew install gh`; on Windows with WinGet, use `winget install --id GitHub.cli --exact`. The official CLI site also has installers and Linux package instructions. Reopen your terminal after installation.

On macOS or Linux:

```sh
python3 --version
python3 tools/runner.py --login --submit --bank-every 256 --minutes 60 --workers 1 --name "Your name"
```

On Windows:

```powershell
py -3 --version
py -3 tools\runner.py --login --submit --bank-every 256 --minutes 60 --workers 1 --name "Your name"
```

Replace `Your name` with your alias. `--login` uses GitHub's browser sign-in through the official CLI and reads your authenticated username. The runner does not ask for a personal access token or put a token in a receipt. The CLI manages its own authentication. If already signed in, the current GitHub account is used.

`--submit` explicitly authorizes bank issue creation. Every 256 completed tasks creates a bank by default; `--bank-every N` accepts 1 to 256. Banks normally submit ten seconds apart. Rate-limit failures honor GitHub’s Retry-After/reset headers and exponential backoff, saved across restarts. Two computers can share an account, but GitHub’s account limits apply across both. The terminal reports pending, uncertain and submitted banks separately from verified coverage. GitHub Actions must process the bank before contribution credit. Complete banks with a passed random audit receive provisional credit for unique tasks; independently verified inputs remain a separate total.

When computation ends, automatic mode uses the rest of your chosen time budget to submit queued banks. Ctrl+C stops that wait and leaves the queue on disk. Later runs with `--submit` resume it. An uncertain GitHub response is retained for manual inspection rather than blindly retried.

### Manual banking instead

The GitHub CLI is optional. Use these commands to save local receipts and submit them yourself:

On macOS or Linux:

```sh
python3 --version
python3 tools/runner.py --minutes 60 --workers 1 --name "Your name" --github username
```

On Windows:

```powershell
py -3 --version
py -3 tools\runner.py --minutes 60 --workers 1 --name "Your name" --github username
```

The version must be at least 3.11. Replace `Your name` and `username` with your alias and GitHub username. Do not include `@` in the local runner's GitHub argument. If you do not have a GitHub account yet, you can enter `anonymous`; an account is needed to submit a bank issue later. The authenticated account that posts the issue receives leaderboard credit.

You can optionally link your alias with `--url "https://your-site.example"`. On restart, omitted name, GitHub and website options reuse the checkpoint's saved attribution.

- `--minutes 60`: schedule work for up to an hour, then finish the active bounded tasks. The maximum is 1,440 minutes per invocation.
- `--workers 1`: use one worker process. Try one first; raise it up to the available CPU count, with a maximum of 32. Workers may use their cores fully while running. This is a worker count, not the browser's duty-cycle slider.
- `--max-tasks 4096`: cap additional completed tasks in this invocation. The runner can finish earlier if it reaches this cap, its outbox limit or an exact discovery.
- `--output "math-gambling-run"`: choose where results and checkpoints go. Relative paths are relative to your current terminal folder.
- `--offline`: use the bundled allocation strategy and exact coverage snapshot, with no network requests. It cannot be combined with `--login` or `--submit`. Work banked after the release may be absent from this snapshot. Online coverage failures pause new dispatch rather than silently assuming no task was checked.
- `--seed`: choose a 256-bit seed using exactly 64 hexadecimal digits. Omit it for a securely generated seed.
- `--version`: show the runner release version.
- `--help`: show all options.

The runner keeps computing when the terminal is behind other windows. It does not pause for a hidden browser tab. Keep the terminal open and the computer awake while you want it to run. A failed strategy download falls back to the bundled policy.

## 3. Stop and resume

Press **Ctrl+C once**. The parent stops assigning tasks, waits for the current bounded tasks to finish, and writes final banks and status. Force-quitting can interrupt that drain; completed checkpoints remain, and unfinished reserved tasks are retried next time.

Run the same command again from the same folder, or omit the attribution options to reuse the saved profile:

```sh
python3 tools/runner.py --output "math-gambling-run" --minutes 60 --workers 2
```

Use `python` instead of `python3` on Windows if needed. Keep the same output path; an absolute path works even after extracting a new release elsewhere. Add `--kernel rust` to use the native kernel and `--submit` to resume automatic banking. Neither option is implicitly enabled by the saved profile.

Version 0.6.1 reuses the saved name, GitHub username and website without asking again. GitHub capitalization differences are accepted while original receipt spelling stays intact. You may change workers, time and task caps. Explicitly changing the name, website or GitHub account still requires a separate output folder because existing work retains its original attribution.

**Do not delete `banks/`, `checkpoint.sqlite3`, or SQLite sidecars to fix a restart.** They contain pending work and submission state. Older releases require the original name, exact GitHub capitalization and optional URL on every invocation; upgrading preserves that output folder.

Only one runner may use an output folder at a time. A second process exits with a clear lock error. Use another `--output` if you intentionally want separate runs; that does not guarantee nonoverlapping random assignments across computers.

The output folder contains:

- `checkpoint.sqlite3` and its SQLite sidecars: task reservations, completed tasks and bank state.
- `results.jsonl`: durable exact task results.
- `banks/bank-*.json`: compact receipts ready for GitHub.
- `status.json`: summary written when the run stops.
- `discoveries/`: independently checked candidate identities, if any.
- `runs/`: durable per-invocation seed, runtime, policy snapshots, task assignments and exact-result digests.
- `cache/coverage/`: content-addressed copies of published exact coverage shards.

Keep the checkpoint and its sidecar files together. Stop the runner before moving the output directory. Do not delete an output directory that contains unbanked work or discovery evidence.

## 4. Bank completed work

1. Open one `bank-*.json` file from `math-gambling-run/banks` in a text editor.
2. Copy its entire contents into the body of a [new bank issue](https://github.com/Kuberwastaken/math-gambling/issues/new?title=%5Bbank%5D%20Local%20computation%20bank). Keep `[bank]` at the start of the title.
3. Submit the issue. Use one issue per bank file.
4. Wait for GitHub Actions to independently replay and deduplicate the work. Posting an issue alone is not verified credit.
5. Record the submitted file locally. Substitute the actual bank filename:

```sh
python3 tools/runner.py --name "Your name" --github username --mark-banked bank-FILENAME.json
```

On Windows, use `py -3 tools\runner.py` instead of `python3 tools/runner.py`. If you used `--url` or a custom `--output` before, include the same values here. `--mark-banked` records your manual submission; it does not claim server verification or contact GitHub.

Up to 256 task claims go into each bank; a byte limit can produce smaller files. At 4,096 unsubmitted tasks, new computation stops until you bank and mark files submitted. This prevents unbounded local storage. Keep bank files until their issue result is clear. A rejected or failed issue needs investigation before its coverage can count.

### GitHub submission behavior

Automatic mode uses the [GitHub CLI](https://cli.github.com/) with your explicit `--submit` option. Add `--login` for the browser sign-in flow, or use an existing `gh auth login` session. Successful submissions are paced ten seconds apart; failures back off persistently. It checks for an identical existing issue before creating one and retains uncertain submissions for manual inspection. `--offline` and `--submit` cannot be combined.

The manual commands omit `--submit`; the automatic quickstart includes it explicitly.

## Troubleshooting

- **Windows says `py` was not found:** try `python --version` and use `python` for the command. If the Microsoft Store opens instead of Python, install Python from the official link and reopen PowerShell.
- **macOS/Linux says `python3` was not found:** install Python first. On Linux, use your distribution's Python and SQLite packages or the official Python instructions.
- **Python is older than 3.11:** install a current Python and use that interpreter explicitly. The runner exits with its minimum-version requirement.
- **`No module named _sqlite3` or `sqlite3`:** that Python installation lacks SQLite. Use a standard Python distribution with SQLite support.
- **`unzip` was not found:** extract using your file manager instead, then open a terminal in the folder containing `tools`.
- **`tools/runner.py` was not found:** your terminal is in the wrong folder. Look for the inner `math-gambling` folder with `tools` and `data`.
- **The output directory is locked:** another runner uses it. Stop that process, or choose a different `--output`. The lock file may remain after a clean exit; its existence alone does not mean a process owns the lock.
- **The checkpoint identity does not match:** update to v0.6.1 or later, stop the old runner, and resume the same `--output` with `--name`, `--github` and `--url` omitted. The saved profile is reused. With `--submit`, sign in to the same GitHub account. Keep existing banks and checkpoints intact; a different contributor needs a separate output folder.
- **Strategy refresh unavailable:** cost scheduling falls back to the bundled or uniform policy. A separate coverage error pauses new dispatch; retry online or explicitly use `--offline`. The exact numerical verifier does not depend on network access.
- **A stopped run has no new bank:** no additional task may have completed, or its work was already assigned to an earlier bank. Check `status.json` and existing files in `banks`.

No finite amount of running guarantees a solution to 114. The counters record bounded exact work; they are not independent lottery tickets or calibrated winning probabilities.

## Seeds and shared coverage

The startup output shows a 256-bit seed, client PRNG, Python version, coverage revision and policy epoch. Python uses `python-random-mt19937-v1`; the browser has its own named PRNG. Same-client seed reuse with the same runtime, starting checkpoint, policy and coverage snapshots reproduces task choices. A seed alone cannot reproduce a changing live policy or different checkpoint state.

Each `runs/*.jsonl` file records the actual policy weights, their hash, coverage revision, ordered dispatched task IDs and exact completion digests. The task itself remains sufficient for independent exact replay. None of these audit fields changes the canonical task or mathematical result digest.

Online mode refreshes the exact published coverage index every 64 completed tasks or 60 seconds. Per-context shards are named by SHA-256; the client checks their bytes, schema, counts, sorted unique task IDs and task bounds before using membership. An index entry excludes only explicit verified task IDs. This is not a Bloom filter and introduces no probabilistic false positives. A missing, corrupt or rolled-back snapshot pauses scheduling while active bounded tasks drain.

A published snapshot is not a live task reservation. Concurrent clients can choose the same task; completed but unbanked or not-yet-published work can overlap too. GitHub verification deduplicates submitted IDs before awarding coverage. Offline mode explicitly accepts the older snapshot bundled with that release.

## Upgrading an existing run

Version 0.6.0 reads both coverage v1 and v2. Older runners pause on the new published coverage and should be upgraded. Stop the old runner, extract the new release, and point `--output` at your existing stopped output folder. Saved tasks and banks remain valid; startup also checks for saved exact discoveries. Operational failures now exit nonzero after preserving results. Keep uncertain bank files for reconciliation rather than posting them repeatedly.
