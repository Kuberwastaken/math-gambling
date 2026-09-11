# Banking computations and calibrating the cluster

**11 September update:** [Negative audits](NEGATIVE_AUDITS.md) now distinguish processed banks from fully verified tasks. New eligible banks may be sampled; unreplayed claims earn no verified score or coverage and never train the model. The exact replay protocol below still governs every task that enters the verified ledger.


The browser and the Python runner produce the same bounded tasks. A volunteer explicitly **banks** completed work through a GitHub issue. GitHub Actions independently replays each unique task before its finite coverage enters the public total. **A SHA-256 digest detects differences; it is not proof that someone spent CPU time.** Replay establishes the result, and cannot prove who physically computed it first.

## Data flow

1. A volunteer starts browser work anonymously with a processor setting. The browser records a random seed and checks the exact published completed-task index before dispatching work. Display name, optional GitHub handle and optional website link are offered when banking. No GitHub token belongs in the browser.
2. At the banking step, the browser copies compact JSON and opens the issue form. The volunteer pastes and posts it while signed into GitHub. The local runner can export the same bank; submitting from its CLI requires explicit authorization. A bank contains at most 256 tasks and 60000 UTF-8 bytes. Keep the local export until the published bank audit appears.
3. Opening, editing or reopening an issue whose title starts with `[compute]` or `[bank]` triggers `Verify community compute`. An hourly scheduled run and manual dispatch remain as reconciliation paths. The job always checks out trusted default-branch code; an issue event cannot supply executable code. It polls updates in ascending time with persistent pagination, records pending issue references, and resumes pending banks before newly discovered ones. A separate recurring creation-order sweep reconciles the whole issue history; ordinary edits cannot reorder that sweep. Closed issues are still eligible. Actions queueing, verification budgets and the Pages deployment can delay visible feedback. An event trigger starts processing sooner, but is not an instant acknowledgement or an exclusive reservation service.
4. The verifier has an upper cap of **16384 previously unseen tasks per run**, constrained by a **120-second replay budget**. This is a cap, not a promised hourly throughput; actual capacity depends on task cost and service overhead. A warmed trusted subprocess is reused for at most 256 tasks, then retired. It retains per-task deadlines, a bounded output queue and a 64 KiB output limit; a fault kills it before reuse. API collection has a separate 60-second monotonic budget with at most eight pending issue requests and four page requests, each capped at eight seconds. Each replay has a 6-second wall limit and 4-second soft CPU limit. A 256-task bank can span several verifier runs. Its next task index and already accepted tasks are saved after each task. A restart resumes that cursor without losing accepted work or granting duplicate credit.
5. A compact claim's digest must match the entire deterministic replay result. An optional submitted hit list must also match. Counters come exclusively from the replay. Previously verified task ids are deduplicated; an invalid claim contributes no new verified coverage. The full older eight-result receipt format remains supported for compatibility.
6. Exact integer cube identities are checked separately before task/schema validation. A real solution is retained with attribution even if its surrounding bank is rejected. Freshly fetched banks receive this positive check while their negative replay is waiting in the queue. The trusted replay also preserves hits omitted from the submission. Parsing is bounded: huge payloads and coordinates beyond 128 decimal digits are rejected before arbitrary computation.
7. The workflow commits only the generated `data/cluster.json`, `data/strategy.json`, `data/receipts/`, `data/coverage/`, and `data/readme-progress.svg`, and pushes without force. The chart comes from accepted replay records. The Pages deployment listens to completion of `Verify community compute`: a normal `GITHUB_TOKEN` push does not itself trigger another push workflow. Replay failures leave the affected task pending with an operational reason and allow unrelated banks to proceed. The workflow aggregates and commits already verified progress before surfacing that operational failure. If a push fails, the job fails visibly and the next checkout resumes from the last durable ledger; it does not pretend to have published credit.

An issue's content is data. It never becomes executable Python, JavaScript, shell, a GitHub expression, or a workflow. There is no receiver service, database account, or browser secret required. Verification runs trusted default-branch source; checkout is pinned to its full official action commit id. The job has only repository-content write and issue-read permissions and does not post comments or close issues. One concurrency group serializes ledger writers. Other repository writers can cause a non-fast-forward push. The workflow permits bounded rebase-and-push retries; an unresolved conflict or repeated push failure stops the job without force-overwriting another writer.

## Bank format and deterministic identity

```json
{"schema":"math-gambling-bank-v1","contributor":{"name":"Example","github":"example"},"tasks":[{"task":{"version":1,"engine":"mg114-offset-v1","context":"c00","row":"0","block":0},"digest":"<64 lowercase hexadecimal characters>","hits":[]}]}
```

The digest placeholder is illustrative, not a valid result. The engine fixes all bounds; a client cannot request arbitrary Python, arbitrary targets, an unbounded row range, or a different modulus. `row` is a canonical decimal string aligned to the engine's 128-row stride; each task covers at most 128 rows and 16 coefficient offsets per row. A bank's fingerprint is SHA-256 of its canonical JSON: recursively sorted object keys, no spaces, ASCII JSON escaping, unchanged array order. `banks[].bank_digest` exposes that fingerprint. It lets a browser recognize its exported bank without asking the user to type an issue number. Matching the fingerprint means the bank was received; the individual audit still distinguishes pending, rejected, duplicate, and accepted tasks.

`data/receipts/tasks/` stores one full exact replay result per canonical task id, including server CPU time and its first accepted GitHub issue creator. `data/receipts/issues/` records bank revisions and incremental progress. `data/receipts/hits/` preserves independently checked identities. `data/receipts/poll.json` stores an updated-time cursor and bounded pending references, not secrets. The summary contains the latest 500 bank audits; the complete history remains in the sharded ledger and Git history.

## Shared completed-task publication

Every aggregation publishes the exact completed-task index using coverage v2.
The root retains 81 context descriptors and a revision equal to accepted unique
tasks. Each context partitions IDs by two SHA-256 hex digits, then stores bounded
256-ID immutable chunks in accepted sequence order. Clients fetch the relevant
bucket, validate exact bytes and IDs, and keep bounded caches. Full chunks are
reused; partial tails can grow without rewriting the whole context's task list.

The publisher rejects removal, replacement or duplicate accepted IDs. Root,
context and chunk byte caps remain explicit. The v1 100,000-ID per-context cap
is removed. Old unreferenced files receive at least 24 hours' grace before
cleanup; required current files are never retired. A suspended client encountering
expired files must refresh, and missing coverage always pauses dispatch.
Runner ZIPs contain their complete standalone snapshots. See the
[protocol](PROTOCOL.md#exact-shared-completed-task-index) for exact formats.

Readers support v1 and v2. Public clients older than v0.3.0 require an upgrade;
existing receipts and ledger credit remain valid.

## Leaderboard and credit

The leaderboard belongs to the **actual GitHub issue creator**, obtained from GitHub's API, not the handle typed into the bank. One unique canonical task receives credit once, when its valid result is first accepted. Rankings use the sum of replayed coefficient-generator computations and show verified task counts alongside them. Submitted hours, submitted counter values, and claimed machine speed cannot increase the ranking.

A display name and the payload's optional handle remain self-declared. The public record shows the authenticated submitter separately. Changing the claimed handle cannot credit a different GitHub account. Copying someone else's public task result and submitting it first remains possible: this is auditable result accounting, not cryptographic proof of CPU ownership, Sybil resistance, or discovery priority. A valid mathematical discovery still needs independent review and a discussion of attribution before a paper is finalized. Posted identity claims and bank records remain in public Git history.

## What calibration actually does

Every 64 newly verified unique tasks completes an epoch. Existing epochs stay frozen. The [versioned geometry/cost policy](GEOMETRIC_POLICY.md) replaces the legacy median of quotient positions per CPU with shrinkage estimates of curve yield and aggregate CPU, including empty tasks. Exploitation weights those estimates by an uncalibrated geometric band/shell prior. A 40% uniform task-proposal floor remains; it does not reserve 40% of CPU time.

This policy has not demonstrated better discovery odds. Timing differs across devices; submitted work is selection-biased. The geometric prior assumes more than our selected norm families have established. The spatial challenger remains in shadow and needs a controlled equal-compute experiment before promotion.

## Limits of this first cluster

Full negative replay repeats donated work and remains a central capacity limit. Reusing the warmed trusted worker improved a 24-task local benchmark by 7.43–7.76× (two opposite-order pairs, identical results); this measures verification overhead, not discovery odds or GitHub-hosted throughput. The current upper admission cap is **16384 new tasks per run within 120 seconds of replay, not unlimited volunteer throughput**. Local search can continue while verification catches up. A verified positive identity does not require trusting previous negative work. The site must distinguish local work, posted banks, and independently accepted coverage.

Random task selection has a nonzero collision chance; it is not exclusive leasing. Deduplication prevents repeated task ids from inflating coverage. Distinct tasks describe bounded norm-coordinate work, not a global proof of distinct integer triples, complete elliptic curves, an exhaustive height box, or a discovery probability. They may overlap earlier unpublished work. The shared skip list reduces known duplication; it cannot infer unpublished completions or reserve unfinished work. The issue poll reads at most two pages of 100 updates and two pages of 100 creation-ordered issues per run, and stores at most 4096 pending banks. Both sweeps retain their next-page cursors across runs; they advance only after the whole page is retained. The creation-order sweep cycles back to the start, recovering equal-timestamp stalls and omissions caused by reordering in the incremental fast path. Deletions or transfers can still shift REST pagination, and there is no immutable API snapshot guarantee; repeated reconciliation recovers after those mutations settle. Severe spam or a large backlog can delay ingestion. This is a finite public service with bounded capacity, not a censorship-resistant queue.

Larger-scale operation needs audited task ownership/leases, explicit storage and abuse budgets, and a deliberate choice between full replay and weaker sampling audits. No received negative claim silently changes that trust model. GitHub-hosted runners and Pages have their own quotas and operational constraints; the workflow timeout is a cap, not a promise of free unlimited compute.

Counts from different mathematical domains are not interchangeable reference-core-days. Agreement with an analytic expected count is a useful diagnostic, but cannot prove that each candidate was checked. The negative coverage claim still rests on the exact implementation, independent complete-task replay and the published finite task definition.

Local checks:

```sh
python3 -m unittest discover -s tests -p test_cluster.py
python3 -m unittest discover -s tests -p test_coverage.py
python3 tools/aggregate.py
python3 tools/ingest.py --input bank-fixtures.json --data /tmp/math-gambling-test-data
```

Fixture format: `{"receipts":[{"id":"fixture-1","receipt":{...}}]}`. Fixture ingestion refuses the production data directory. Production ingestion is `python3 tools/ingest.py --issues` with `GITHUB_TOKEN` supplied by GitHub Actions; it needs no personal access token.
