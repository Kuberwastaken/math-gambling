# Mathematical coverage export

`tools/math_coverage.py` creates a separate, inspectable audit of the mathematical
intervals searched by independently verified tasks. It does **not** alter the
canonical receipt ledger, contributor scores, or the completed-task membership
index in `data/coverage/`.

The distinction matters: completing a task can produce **zero curves and zero
mathematical intervals**. Its task ID is completed, but that does not establish
that a nonempty part of the `(D,r,q)` domain was searched.

## Run a bounded export

From the repository root, with Python 3.11 or newer:

```sh
python3 tools/math_coverage.py --data data --max-tasks 32 --seconds 15
```

The default output is `data/math-coverage/`. To make a private local audit without
changing published data:

```sh
python3 tools/math_coverage.py --data data --output /tmp/math-coverage-audit --max-tasks 32 --seconds 15
```

The defaults are 32 new attempts and five seconds. `--max-tasks` accepts 1–4096;
`--seconds` accepts a finite positive value up to 3600. These are **upper bounds,
not promised throughput**. The wall budget includes reading ledger metadata and
checking prior record hashes. Each new replay runs in a fresh trusted subprocess
with a timeout of at most four seconds, reduced to the remaining wall budget.
Final bounded serialization, atomic publication, filesystem operations and
process teardown can extend the requested wall time. This is not a real-time
operating-system guarantee.

Run the same command again to continue. Only the first unexported sequence and
its successors are eligible; an existing complete record is not replayed. A
failure at one sequence leaves later sequences pending, keeping the exported
prefix unambiguous. Increase the budget after a metadata timeout; the exporter
does not skip unexamined metadata or advertise it as covered.

Exit code 0 means the run completed normally, including a partial export stopped
by its task cap or time budget before dispatch. Exit code 2 means a mismatch,
replay timeout or operational failure was deferred. `last-error.json` records a
recoverable error when storage is available. An optional Actions step should
continue publishing canonical cluster data if this separate export fails.

## What an interval asserts

Each record supplies canonical decimal strings for:

| Field | Meaning |
| --- | --- |
| `D` | `abs(x+y)`, positive |
| `r` | `0 <= r < D`, with `r³ ≡ 114 (mod D)` |
| `s` | The signed value `x+y`, with `abs(s)=D` |
| `qlo`, `qhi` | Both inclusive; `z = r + D*q` |

The scope is the kernel's **minimum-|z| candidate subset**:
`abs(z) <= min(abs(x),abs(y))`. It is a selected finite norm-coordinate domain,
not an exhaustive box in `(x,y,z)`, and not a certificate covering all possible
representations of a given size. Within a recorded interval, every integer
quotient was either rejected by an exact necessary-condition sieve or passed
to the exact candidate check. A solution outside the minimum-|z| condition is
outside this certificate's scope.

The pre-curve counters distinguish generators outside a selected shell, invalid
`D`, exact signed congruence exclusions, and a noninvertible parametrization.
The shell and invertibility selections define what this campaign searches;
they do **not** prove that every omitted norm generator or modular root is
mathematically impossible. No interval is credited for a generator that never
reaches `scan_curve`.

The curve hook fires only after `scan_curve` has successfully completed. Before
publishing anything, the exporter checks that the number and inclusive lengths
of its callbacks equal the completed result's `curves` and `quotient_points`.
It requires the entire replay result, including its digest, counters and hits,
to match the verified ledger record. A missing callback, interrupted scan,
changed digest or mismatching result publishes no coverage for that task.

## Files and provenance

`index.json` contains:

- `ledger_watermark`: the number of contiguous verified sequences in the
  metadata snapshot read by this run.
- `exported_through_sequence` and `exported_task_count`: the contiguous prefix
  with completed mathematical records.
- `status`: `partial` or `complete` **relative to that observed watermark**.
  New ledger receipts can arrive after the snapshot.
- Empty-task counts and the empty fraction **among exported tasks**, plus
  interval and quotient-position totals. A partial prefix is not necessarily
  representative of the whole ledger.
- One descriptor per exported task: task ID, result digest, ledger fingerprint,
  kernel source hash, immutable record path, compressed-byte SHA256 and counts.
- `last_run`: attempts, newly exported tasks, stop reason, and any deferred error.

Each immutable object is at
`records/<first-two-hash-characters>/<sha256>.json.gz`. Its address is the SHA256
of the **compressed bytes**. Gzip has an empty filename, timestamp zero, fixed
compression level and platform-neutral header. The uncompressed JSON is
canonical ASCII with sorted keys, compact separators and one final newline.
Compression does not depend on the time of export. Reproducibility assumes the
same record contents and compression implementation; the byte hash always
identifies the actual distributed bytes.

A record includes the canonical task, task ID, verified result digest, replay
counters, hits, mathematical scope, and SHA256 of the canonical source ledger
record. It also records the SHA256 of `search_core.py` and of the exporter.
The replay compiles the exact kernel bytes whose hash it records, rather than
relying on a potentially stale Python bytecode cache. Old records retain their
original kernel hash when instrumentation changes; backfill appends records
under the code actually used for each replay.

SHA256 detects changed bytes; it is **not proof that a volunteer spent CPU**,
nor a formal proof of the kernel's mathematical correctness. The evidence is a
reproducible finite replay, its reviewed kernel, and the accompanying interval
list. An independently implemented checker can verify it without trusting a
contributor's timing or claimed amount of work.

## Compression and overlap

Within each task, intervals having the same `(D,r,s)` are sorted and exactly
unioned when they overlap or are adjacent. The record provides the original
`raw_scan_interval_count`, resulting `merged_interval_count`, the full replay
position count, and `q_positions_task_local_union` after removing overlap
**within that task only**. `interval_columns` defines each merged row as
`[D,r,s,qlo,qhi]`.

An empty task has `certificate: "empty-task"`, an empty interval list, and zero
mathematical positions. Its generator/exclusion counters are retained to explain
why. It is never silently converted into a positive-sized region.

The exporter does **not** compute a union between different tasks or contexts.
Consequently the summed positions and interval counts are not globally unique
curves, unique integer triples, or a probability of finding a solution.
`global_union_computed` is explicitly false.

## Inspect a record

This standard-library example verifies the compressed hash before displaying
the first exported record:

```python
import gzip, hashlib, json
from pathlib import Path

directory = Path("data/math-coverage")
index = json.loads((directory / "index.json").read_text())
entry = index["records"][0]  # Check that the export is nonempty first.
raw = (directory / entry["file"]).read_bytes()
assert hashlib.sha256(raw).hexdigest() == entry["sha256"]
record = json.loads(gzip.decompress(raw))
print(record["task_id"], record["certificate"])
print(record["interval_columns"])
print(record["intervals"][:10])
```

For a complete independent audit, replay the stated canonical task against the
recorded kernel source, compare its completed result digest to the ledger, and
compare the exact task-local union of completed callback intervals. Do not treat
an unreferenced file or a partial callback list as covered work.

## Failures and limits

An encountered identity is independently checked using integer cubes and saved
immediately under `discoveries/`, before subsequent candidates or final task
hashing. It remains evidence if the task later fails or disagrees with its
receipt. Discovery evidence explicitly claims **no task completion**. These files
do not automatically change public discovery credit or send a GitHub message.

Immutable records are written and synced before the index references them. A
crash between these operations can leave an unreferenced object, which does not
advance coverage. Previously published records remain available. A local
single-writer lock prevents competing exporters from regressing the index;
different-host publishers must also be serialized by the repository workflow.
On resumption, the exported prefix must still match the canonical ledger, and
every previously referenced compressed object's checksum is checked. A changed
ledger or damaged object stops extension instead of silently replacing history.

This initial audit product performs a linear metadata scan and keeps a linear
list of descriptors in its mutable manifest, capped at 32 MiB. Each task record
is capped at 2 MiB uncompressed. It is suited to bounded pilot/backfill work, not
an unlimited whole-cluster automatic replay. Metadata scans, validation and
manifest rewrites eventually dominate as the archive grows. Before that point,
use an indexed sequence source and immutable manifest chunks; do not merely
raise the cap or describe replayed totals as unique coverage.

The first local pilot on 11 September 2026 replayed the oldest 32 of 24,665
verified tasks in about 5.5 seconds including the ledger scan. Of those 32,
28 were empty and four emitted 1,946 intervals containing 2,718,277 logical
quotient positions. The per-task gzip records totalled 76,869 bytes. This small
historical prefix is a functionality check, not a discovery-rate estimate or a
representative efficiency benchmark. No new solution or contributor credit was
created by the export.

Focused fault tests run with:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_math_coverage.py -v
```
