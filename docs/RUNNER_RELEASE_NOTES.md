# Math Gambling runner v0.6.0

Supports the CPU-budgeted policy and exact proposal preflight. All fixed task definitions, exact checks, stored results, receipt digests and contribution credits remain compatible. Stop the old runner before resuming its output directory with this release.

The new policy expresses its exploration reserve in predicted reference CPU, rather than task counts. Device costs vary; the geometric objective remains a proxy, not discovery probability. Before reserving a task, exact outward integer bounds can prove its whole norm tile empty. Such proposals receive no credit and are never recorded as completed mathematical coverage. Context is held fixed during bounded resampling, and uncertain tiles remain eligible.

The Rust arithmetic kernel, ten-second bank pacing, authentication and durable recovery are unchanged. The archive includes the new proof module; Windows, macOS and Linux packaging checks exercise the extracted runner.

## Previous release

# Math Gambling runner v0.5.2

Bank uploads normally run ten seconds apart instead of one minute apart. Twelve queued banks require 110 seconds of scheduled spacing, plus request time; GitHub limits or network failures can extend this. Rate-limit waits honor response headers and survive a restart. Repeated failures back off. An ambiguous creation remains saved for inspection instead of being blindly retried. The runner continues using the remaining chosen time budget to drain; Ctrl+C retains its queue.

The leaderboard now ranks **contributed inputs**: exact replays plus provisional unique work from complete banks with at least one matched random audit. Verified inputs are shown separately. Duplicate tasks receive no extra credit, later verification replaces provisional credit, and a failed account audit revokes provisional credit. Unchecked tasks remain outside certified coverage and model training. Existing stored claims qualify under the same rules; no individual score is manually adjusted.

The Rust/WebAssembly mathematical kernel and receipt protocol are unchanged. Stop the old runner and point the new one at the same output folder with the same attribution. Linux, Windows and macOS release gates check checkpoint recovery, queue pacing, rate-limit handling and the native kernel before publication.

The v0.5.1 tag did not publish: a legacy submission fixture still expected the old CLI transport. Version 0.5.2 updates that fixture to test the structured API request and persisted pacing; no mathematical check was removed.

## Previous release

# Math Gambling runner v0.5.0

The search kernel can now run in Rust with bounded 64/128-bit arithmetic and an arbitrary-precision final check. Choose a platform ZIP and pass `--kernel rust`; the universal ZIP retains the dependency-free Python fallback and Rust sources. Python 3.11+ continues to handle authentication, seeds, checkpoints and banking. The browser uses the same kernel through WebAssembly.

Matched warm measurements on the development Mac were 20.2× faster than Python and 5.2× faster than JavaScript in Node. These are kernel timings, not whole-campaign speedups or discovery odds. Montgomery multiplication is implemented and tested but is not the default because it did not improve this workload overall.

Exact task definitions, counters, result digests and saved output remain compatible. Release gates test known positives, wide final arithmetic, cross-language fixtures, malformed tasks and a real spawned Rust runner on Linux, Windows and macOS. Platform binaries are built from this tag; checksums accompany all archives.

The server may now sample eligible negative banks after 256 verified tasks/account. Unreplayed claims earn no verified credit, train no model and certify no coverage. Every submitted identity still receives exact verification. This reduces replay task volume without pretending that sampling proves a complete negative result.

## Previous releases

# Math Gambling runner v0.4.1

Exact norm-shell pruning skips provably excluded coefficient intervals using integer bounds and bisection. Logical counters, task definitions and old receipt digests are preserved. The runner keeps independent local seeds and reads the same public policy and exact completed-task index as the browser.

The new production policy combines an explicit geometric preference with measured curve yield and CPU cost; it does not predict winning odds. Existing saved output folders and banks remain compatible. Stop an old runner before opening its output with the new version.

Release gates execute the extracted archive on Linux, macOS and Windows. Python 3.11 or newer is required.

The v0.4.0 tag did not publish: Windows hit the checkout test's 30-second Git staging timeout on the full coverage snapshot. This patch gives those test-only filesystem operations a bounded 180-second budget. Every hash and arithmetic check remains required.

## Previous release

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
