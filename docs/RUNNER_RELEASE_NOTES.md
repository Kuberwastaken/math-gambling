# Math Gambling runner v0.2.0

A portable Python 3.11+ client for the community search for x³ + y³ + z³ = 114.

- Standard-library client for macOS, Windows and Linux, with bounded multiprocessing and resumable exact task receipts.
- `--login` uses the GitHub CLI browser sign-in and reads the authenticated account. Add `--submit` to authorize automatic bank issues every 256 completed tasks by default; adjust with `--bank-every 1..256`.
- A strict exact coverage index avoids tasks already present in the published verified snapshot. SHA-256 validates content-addressed shards before membership checks; no probabilistic membership filter is used.
- A visible 256-bit seed and durable run logs record task assignments, policy weights, epochs and results. Exact mathematical task digests are unchanged.
- `--offline` uses the bundled strategy and coverage snapshot. The snapshot cannot include contributions published after the archive was built.

Download the ZIP, extract it, and read `RUNNER_SETUP.md`. Python packages are not required; the GitHub CLI is optional and only needed for automatic submission. `SHA256SUMS.txt` checks the downloaded ZIP's integrity.

The release workflow tests the actual extracted archive on macOS, Windows and Linux at Python 3.11 before publishing. These finite tests provide compatibility evidence, not a proof that every device or Python build will work.

Completed, submitted and verified are separate states. GitHub Actions independently replays banked work and removes duplicates before leaderboard credit. A snapshot cannot prevent overlap with concurrent clients or work that has not been published yet. A seed alone cannot reproduce a changed live scheduling policy; each run logs the actual policy snapshots and ordered task assignments.

This search has no guaranteed result or discovery ETA. Versioned releases and reproducible receipts make the computational experiment inspectable; they do not improve the mathematical odds by themselves.
