# Scientific archive and Mac observations

The repository preserves the scientific content of the local three-cubes laboratory: source code, mathematical derivations, parameter definitions, validation results, benchmark evidence, unsuccessful experiments, and literature reviews. It does **not** contain the operational search database or a resumable copy of the Mac's running campaign.

The current archive contains 158 scientific files, approximately 9.8 MB including the official PARI source distribution. The exhaustive inventory is [ARCHIVE_MANIFEST.json](../research/archive/ARCHIVE_MANIFEST.json). Its paths are relative; every included file records its original SHA-256, archived SHA-256, byte counts, and whether sanitization changed the bytes. The archive's creation timestamp identifies the copy. Historical statements such as “running” describe their original observation, not present activity.

| Archive area | Preserved material |
|---|---|
| [Root](../research/archive/README.md) | Original norm search, GP and native implementations, orchestration, pilots, benchmark and validation scripts |
| [Phase2](../research/archive/phase2/README.md) | Offset domains, controller, worker, online cost model, geometry certificate, held-out calibration and completed-run analysis |
| [Phase3](../research/archive/phase3/README.md) | Optimized checker, migration source, controller, fault tests, historical migration certificate and performance evidence |
| [Mathematics](../research/archive/NONOVERLAP.md) | Field/class/unit certification, nonoverlap, shell pruning, unit shape and root-recovery analysis |
| [Experiments](../research/archive/experiments/shell/README.md) | Shell search source, validation, measured performance, modular filters and root-recovery probes |
| [Research review](../research/archive/research-2026-09-09/SEARCH_VERDICT.md) | Algorithm, geometry and discovery-learning reviews, normalized-sieve prototype, blind experiment sources and results |
| [Regression data](../research/archive/data/known-curves.json) | Known-solution numerical fixtures, with upstream source attribution |
| [Vendor source](../research/archive/vendor/pari-2.17.4.tar.gz) | Pinned official PARI/GP 2.17.4 source; SHA-256 recorded in the manifest and build adapter |

All original mathematical implementation sources are retained. The [original license](../research/archive/LICENSE) and [attribution notice](../research/archive/NOTICE.md) accompany them. They specify GNU GPL version 2 or later for the experimental C, GP and Python software; PARI retains its upstream authorship and license. The archive supplies source instead of shipping machine-specific PARI libraries. Linked papers remain at their publishers or preprint repositories; this archive does not redistribute their full text under an invented license.

**Operational files remain local.** At archival inventory, excluded material totaled approximately 6.3 GB and was growing with the active campaign. The manifest itemizes exclusions, including:

- The phase3 SQLite ledger, approximately 5.5 GB, plus its write-ahead log and shared-memory files.
- The phase2 and phase1 ledgers, approximately 373 MB and 319 MB respectively.
- Process records, raw process logs, lock files, stop markers, active stdout journals and discovery-journal directories.
- Compiled executables, debug symbols, native dynamic libraries, bytecode caches and runtime symlinks.

These sizes are point-in-time inventory values, not transfer requirements. No SQLite file was opened by the archive copier or snapshot exporter. A manifest hash of a historical job prefix is evidence of the recorded audit; it cannot reconstruct the omitted ledger or independently prove that every historical job ran. Full historical-ledger replay requires the separately retained private operational data.

Personal absolute paths and explicit process identifiers were removed from the copies. Structured process IDs, host identifiers, credentials, session-process metadata and power telemetry are excluded. Internal scientific links are relative; links to omitted runtime state lead here. Original byte hashes preserve provenance across those transformations. The archived `SHA256.json` remains a historical artifact; use `ARCHIVE_MANIFEST.json` to verify the sanitized copies.

**Reproduction uses a separate working directory.** Verify the archive without compiling:

```sh
python3 research/build_archive.py --check
```

Build the archived native implementations from the included PARI source on macOS or Linux:

```sh
python3 research/build_archive.py --build-pari --jobs 2
```

This requires Python 3, a C compiler, make and the platform's normal development tools. It creates `.build/reproduction/`, compiles PARI from pinned source, and creates the original relative laboratory layout inside that isolated directory. An existing PARI installation can instead be supplied explicitly:

```sh
python3 research/build_archive.py --pari-prefix /path/to/pari-install
```

The prefix must provide `bin/gp`, `include/pari/pari.h`, and `lib/libpari`. Historical `build.py` files are retained as provenance for the original Mac build; the new adapter provides portable dependency and output paths. It compiles eight native targets. No long search starts automatically. Build artifacts, generated test databases and private operational records must remain excluded from version control.

Validation scripts can be run in the isolated laboratory after building. Some historical integration tests expect prior ledgers or binary hashes; an omitted-ledger test cannot be represented as freshly passed. Original evidence JSON documents the actual historical result and its source identity. Mathematical identities and candidate-exclusion rules are distinct from claims about completeness of historical execution.

**Mac data is an exported observation, not browser computation.** The [public snapshot](../data/mac.json) and [bounded history](../data/mac-history.json) come from an explicitly invoked read-only exporter:

```sh
python3 tools/export_mac.py --source /path/to/three-cubes-lab --output data
```

There is no implicit home-directory search or process inspection. The exporter reads phase3's status, recognized checkpoints, the latest available audit and a bounded process log. It never connects to, starts, stops or resumes workers. A separate operator may invoke it periodically. The page must display `updated_utc` and interpret `state` at that timestamp; `is_live` is always false. `exported_utc` records when the public files were created.

The public schema is version 1:

| Field | Meaning |
|---|---|
| `totals` | Allowlisted cumulative counters, encoded as exact decimal strings |
| `jobs` | Observed complete/running job counts, also decimal strings |
| `solutions` | Integer triples independently checked to satisfy the equation with target 114; decimal strings |
| `audit` | Latest available audit's own timestamp, integrity flags and job counts; may precede the status |
| `learning` | Cost-model gate and throughput holdout metrics; `success_probability` is always null |
| `throughput` | Difference between genuine sampled curve counters divided by their elapsed time; never a solution-rate estimate |
| `limitations` | Fixed public explanations of coverage and statistical limits |
| `snapshot_id` | Shared identifier linking the two exported files |

Phase3 counters include preserved phase2 totals. They do not silently add the separate phase1 counter. A curve-interval count is not necessarily a distinct divisor or root: different quotient bands can revisit the same root without repeating a candidate position.

History contains at most 300 genuine observations, selected across the recorded time range. It is not padded or interpolated. Log-only observations contain only the counters actually present in that log; missing counters are omitted. Counter regressions or a source older than the existing public snapshot block export. Large integers never pass through floating point. Each file is replaced atomically; consumers loading both should compare `snapshot_id` and retry if they differ during an update.

The exporter deliberately provides no private paths, PIDs, hostnames, network details, arbitrary log messages, raw policy records or journal contents. A claimed nonempty solution list must pass exact integer arithmetic before any public file is replaced. [Exporter tests](../tests/test_export.py) include privacy, large counts, source immutability, invalid identities, stale input, audit separation and bounded-history checks.
