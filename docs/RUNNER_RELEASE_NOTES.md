# Math Gambling runner v0.3.1

This release addresses the 10 September audit. Existing task identities and receipt digests stay valid.

- Exact identities are saved as soon as the kernel finds them, before later work or receipt hashing. Startup checks saved discoveries and prepares them for priority banking.
- Explicit seeded runs resume their saved selection stream. Operational failures produce a distinct status and nonzero exit code.
- Banks use relocatable paths. Submission intent is durable before GitHub creation; uncertain attempts require reconciliation rather than blind retries.
- Coverage v2 uses exact hash-routed chunks. It removes the old 100,000-ID context cap and bounds client memory. Both legacy v1 and new v2 snapshots are readable.
- New builds include every chunk needed for offline use. Upgrade from v0.2.x to use the new published coverage; preserve your output folder and existing bank files.

The release is published only after its extracted archive passes the Linux, macOS and Windows gates. These are tested fault-handling improvements, not an absolute guarantee against hardware or storage failure. The search still has no guaranteed result or discovery ETA.

## Earlier releases

### v0.2.2

A portable Python 3.11+ client for the community search for x³ + y³ + z³ = 114.

Version 0.2.0 passed the Ubuntu and macOS checks but was withheld when the Windows build detected changed coverage-shard bytes. Git’s Windows newline conversion changed LF to CRLF, so the SHA-256 validation correctly rejected the checkout. Version 0.2.1 preserves hash-addressed coverage and archived research bytes during checkout and emits explicit UTF-8/LF protocol files. The original tag remains unchanged; this release must pass the full three-platform checks again.

- Standard-library client for macOS, Windows and Linux, with bounded multiprocessing and resumable exact task receipts.
- `--login` uses the GitHub CLI browser sign-in and reads the authenticated account. Add `--submit` to authorize automatic bank issues every 256 completed tasks by default; adjust with `--bank-every 1..256`.
- A strict exact coverage index avoids tasks already present in the published verified snapshot. SHA-256 validates content-addressed shards before membership checks; no probabilistic membership filter is used.
- A visible 256-bit seed and durable run logs record task assignments, policy weights, epochs and results. Exact mathematical task digests are unchanged.
- `--offline` uses the bundled strategy and coverage snapshot. The snapshot cannot include contributions published after the archive was built.

Download the ZIP, extract it, and read `RUNNER_SETUP.md`. Python packages are not required; the GitHub CLI is optional and only needed for automatic submission. `SHA256SUMS.txt` checks the downloaded ZIP's integrity.

The release workflow tests the actual extracted archive on macOS, Windows and Linux at Python 3.11 before publishing. These finite tests provide compatibility evidence, not a proof that every device or Python build will work.

Completed, submitted and verified are separate states. GitHub Actions independently replays banked work and removes duplicates before leaderboard credit. A snapshot cannot prevent overlap with concurrent clients or work that has not been published yet. A seed alone cannot reproduce a changed live scheduling policy; each run logs the actual policy snapshots and ordered task assignments.

This search has no guaranteed result or discovery ETA. Versioned releases and reproducible receipts make the computational experiment inspectable; they do not improve the mathematical odds by themselves.

Version 0.2.1 passed Windows runtime, extraction, coverage and banking checks, but the test process retained a SQLite connection while deleting its temporary directory. Version 0.2.2 closes that inspection connection explicitly. The release still requires the complete platform gate; no failed tag is moved.
