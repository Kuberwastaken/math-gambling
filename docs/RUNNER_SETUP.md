# Run Math Gambling locally

The portable client is a Python program for macOS, Windows and Linux. It uses the Python standard library, exact integer arithmetic, multiple worker processes and durable SQLite checkpoints. It does not need Node.js, a compiler, a GPU, extra Python packages or a GitHub login to compute.

Use a normal Python **3.11 or newer** installation with SQLite support. Download it from [python.org](https://www.python.org/downloads/) if needed. This is the portable volunteer client; the separate native C/PARI research campaign has different build requirements and performance.

## 1. Download and extract

[Download the portable runner ZIP](https://kuber.studio/math-gambling/downloads/math-gambling-runner.zip). The archive contains a `math-gambling` folder with `tools`, `data` and these instructions. Keep that folder together.

On macOS or Linux, open Terminal. If you saved the ZIP in Downloads:

```sh
cd ~/Downloads
unzip math-gambling-runner.zip
cd math-gambling
```

On Windows, open PowerShell:

```powershell
cd "$HOME\Downloads"
Expand-Archive .\math-gambling-runner.zip -DestinationPath .\math-gambling-runner
cd .\math-gambling-runner\math-gambling
```

You can also extract the ZIP using your file manager, then open a terminal in the inner `math-gambling` folder that contains `tools` and `data`. If your Downloads folder has a different location, use its actual path. Do not run the Python file from inside an unopened ZIP.

## 2. Check Python, then start

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

You can optionally link your alias with `--url "https://your-site.example"`. Keep your attribution identical on later invocations that use the same checkpoint folder.

- `--minutes 60`: schedule work for up to an hour, then finish the active bounded tasks. The maximum is 1,440 minutes per invocation.
- `--workers 1`: use one worker process. Try one first; raise it up to the available CPU count, with a maximum of 32. Workers may use their cores fully while running. This is a worker count, not the browser's duty-cycle slider.
- `--max-tasks 4096`: cap additional completed tasks in this invocation. The runner can finish earlier if it reaches this cap, its outbox limit or an exact discovery.
- `--output "math-gambling-run"`: choose where results and checkpoints go. Relative paths are relative to your current terminal folder.
- `--offline`: use the bundled allocation strategy and make no strategy downloads. The default refresh fetches public strategy data; it does not upload results.
- `--help`: show all options.

The runner keeps computing when the terminal is behind other windows. It does not pause for a hidden browser tab. Keep the terminal open and the computer awake while you want it to run. A failed strategy download falls back to the bundled policy.

## 3. Stop and resume

Press **Ctrl+C once**. The parent stops assigning tasks, waits for the current bounded tasks to finish, and writes final banks and status. Force-quitting can interrupt that drain; completed checkpoints remain, and unfinished reserved tasks are retried next time.

Run the same command again from the same folder, with the same name, GitHub username, optional URL and output path. This resumes the saved checkpoint. You may change the worker count, time limit and task cap. A changed name or URL requires a separate output folder because existing receipts keep their original attribution.

Only one runner may use an output folder at a time. A second process exits with a clear lock error. Use another `--output` if you intentionally want separate runs; that does not guarantee nonoverlapping random assignments across computers.

The output folder contains:

- `checkpoint.sqlite3` and its SQLite sidecars: task reservations, completed tasks and bank state.
- `results.jsonl`: durable exact task results.
- `banks/bank-*.json`: compact receipts ready for GitHub.
- `status.json`: summary written when the run stops.
- `discoveries/`: independently checked candidate identities, if any.

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

### Optional automatic submission

If you want the runner to create issues for you, install the [GitHub CLI](https://cli.github.com/), run `gh auth login`, and explicitly add `--submit` to your runner command. It attempts at most one bank submission per minute. It checks for an identical existing issue before creating one and retains uncertain submissions for manual inspection. `--offline` and `--submit` cannot be combined.

The examples above do not enable automatic submission.

## Troubleshooting

- **Windows says `py` was not found:** try `python --version` and use `python` for the command. If the Microsoft Store opens instead of Python, install Python from the official link and reopen PowerShell.
- **macOS/Linux says `python3` was not found:** install Python first. On Linux, use your distribution's Python and SQLite packages or the official Python instructions.
- **Python is older than 3.11:** install a current Python and use that interpreter explicitly. The runner exits with its minimum-version requirement.
- **`No module named _sqlite3` or `sqlite3`:** that Python installation lacks SQLite. Use a standard Python distribution with SQLite support.
- **`unzip` was not found:** extract using your file manager instead, then open a terminal in the folder containing `tools`.
- **`tools/runner.py` was not found:** your terminal is in the wrong folder. Look for the inner `math-gambling` folder with `tools` and `data`.
- **The output directory is locked:** another runner uses it. Stop that process, or choose a different `--output`. The lock file may remain after a clean exit; its existence alone does not mean a process owns the lock.
- **The checkpoint identity does not match:** use the original name, GitHub username and optional URL, or choose a new output folder.
- **Strategy refresh unavailable:** work continues using the bundled or uniform strategy. The numerical verifier does not depend on network access.
- **A stopped run has no new bank:** no additional task may have completed, or its work was already assigned to an earlier bank. Check `status.json` and existing files in `banks`.

No finite amount of running guarantees a solution to 114. The counters record bounded exact work; they are not independent lottery tickets or calibrated winning probabilities.
