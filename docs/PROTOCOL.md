# Public search protocol, version 1

`mg114-offset-v1` is a deterministic, selective search for integer solutions of
\(x^3+y^3+z^3=114\). The browser and the local runner compute real high-parameter
candidates. This is not a toy animation, an exhaustive height-box search, a
proof that a solution exists, or a calibrated way to predict where it is.

The JavaScript engine uses `BigInt`; the independent Python implementation uses
unbounded integers and `math.isqrt`. Floating point is confined to task
selection weights and measured timings. It never decides mathematical
eligibility or whether an identity is true.

## Canonical task

```json
{"version":1,"engine":"mg114-offset-v1","context":"c00","row":"0","block":0}
```

The only permitted keys are the five above. Public tasks cannot specify a new
target, arbitrary coefficients, prime list, executable code, modulus or bounds.

`CONTEXTS` in both implementations is the same fixed 81-entry table. Its order
is the Cartesian product of the following lists, with the last varying fastest:

| Axis | Allowed values |
| --- | --- |
| `ell` | 1, 5, 25 |
| shape `(radius,tlo,thi)` | (6,000,000,8,31), (1,500,000,128,511), (375,000,2048,8191) |
| norm shell | \((D_0,2D_0],(2D_0,4D_0],(4D_0,8D_0]\) |
| ratio band `(low,high)` | (0,64), (64,256), (256,4096) |

Here \(D_0=\lfloor10^{19}/54\rfloor=185185185185185185\).
IDs are `c00` through `c80`. Context metadata includes `rowStride:128`,
`totalRows` and `rowTasks` as decimal strings, and integer `blocks`.

`row` is a **starting lattice row**, encoded as a canonical nonnegative decimal
string. It must be a multiple of 128 and smaller than `totalRows`. A task covers
128 consecutive rows, or the shorter final chunk. For each row index \(j\),
with \(w=2R+1\),

\[
b=(j\bmod w)-R,\qquad c=\lfloor j/w\rfloor-R.
\]

`block` selects 16 consecutive integer offsets, starting at
`context.tlo + 16*block`, and clipped to `context.thi`. This makes each task a
fixed finite subset with at most 2,048 generators. The largest q band contains
3,840 logical positions per eligible curve. There are no client-controlled
unbounded loops in accepted public tasks. Runtime depends strongly on the
context and computer; a representative local 324-task benchmark ranged up to
76 milliseconds of Python CPU, with a median near 1.4 milliseconds. This is a
measurement, not a time guarantee for every device.

Its stable identity is
`mg114-offset-v1:<context>:<row>:<block>`.
Clients choose tasks from a recorded random seed and reject IDs found in their
local completed records or the exact published completed-task snapshot. This
does not reserve globally disjoint unfinished assignments. The server still
deduplicates canonical task IDs before credit. There is no claim of complete disjointness from the separate
Mac campaign or every historical search.

## Exact generator and checker

With `SCALE = 10^18`, `ALPHA = 4848807585839879338`, and
`ALPHA2 = 23510935004498358840`, the generator is defined by integer rounding,
not by a floating-point cube root:

\[
u=(-4b-16c)\bmod\ell,
\quad m=-\mathrm{ALPHA}\,b-\mathrm{ALPHA2}\,c-u\,\mathrm{SCALE},
\]
\[
a_0=u+\ell\left\lfloor\frac{2m+\ell\,\mathrm{SCALE}}
{2\ell\,\mathrm{SCALE}}\right\rfloor,
\qquad a=a_0+\ell t.
\]

The cubic-field norm and adjoint coefficients are

\[
N=a^3+114b^3+12996c^3-342abc,\quad
B=114c^2-ab,\quad C=b^2-ac.
\]

We require \(D=N/\ell\) in the context's shell. Norm divisibility is checked.
The exact polynomial identity

\[
B^3-114C^3=N(114c^3-b^3)
\]

gives a modular root \(r=BC^{-1}\pmod D\) when \(\gcd(C,D)=1\).
The implementation rechecks \(r^3\equiv114\pmod D\). A noninvertible `C` is
recorded separately; it is **not** a proof that this `D` has no solution.

Modulo 9, every coordinate of a solution for 114 must be 2 modulo 3. Thus
\(S=x+y\equiv1\pmod3\); \(S=D\) for \(D\equiv1\pmod3\), and \(S=-D\)
otherwise. Multiples of 3 are excluded. Necessary signed-sum conditions modulo
8 and 361 are checked before modular inversion. Independent residue enumeration
tests verify these exclusions.

For each root, we take \(z=r+Dq\), with

\[
\max(10^{17},\mathrm{low}\,D)<|z|\leq\mathrm{high}\,D.
\]

In this region \(z\) must have the opposite sign from \(S\):
\(x^3+y^3=S(S^2+3(x-y)^2)/4\) has the sign of \(S\), and two positive
terms of these magnitudes cannot sum to 114. All q interval endpoints are
integer floor/ceiling expressions.

The q sieve uses necessary conditions modulo 243, parity, and quadratic-residue
conditions for primes 5,7,11,13,17,19,23,31,37,41,43,47,53,59,61. It then checks

\[
V^2=\frac{4(114-z^3)-S^3}{3S},\qquad
x=(S+V)/2,\quad y=(S-V)/2.
\]

Divisibility, nonnegativity, exact squareness, parity and the minimal-coordinate
ordering \(|z|\leq\min(|x|,|y|)\) must hold. **Every reported hit is finally
checked by evaluating all three integer cubes.** The Python parent checks it
again, and GitHub ingestion independently checks uploaded coordinates before
validating any receipt metadata.

Public-domain completeness is limited to these generators for which `C` is
invertible, this parameterization and these q bands. Neither finite-domain
testing nor the archived field certificates prove that this is the most
efficient possible search strategy.

## Results, digests and bank-ins

`runTask(task)` in JavaScript is asynchronous (for WebCrypto SHA-256), while
Python's `run_task(task)` is synchronous. They return identical JSON data:

```text
{
  task: canonical descriptor,
  id: stable task identity,
  counters: deterministic integer counts,
  hits: [{xyz:[decimal,decimal,decimal],D:decimal,r:decimal,q:decimal,
          abc:[decimal,decimal,decimal],t:integer,row:decimal}],
  digest: lowercase SHA-256
}
```

Counters are JSON integers, bounded well below the exact-integer limits of
JavaScript numbers. Coordinates, large moduli and row indices are decimal
strings. The digest is SHA-256 over UTF-8 JSON of `{task,id,counters,hits}`, with
keys sorted recursively and no whitespace. Engine data is ASCII, so Python's
ASCII JSON encoding and JavaScript's UTF-8 encoding agree.

The counters satisfy two checked conservation laws:

```text
generators = outside_shell + invalid_d + signed_excluded + noninvertible + curves
quotient_points = rejected_mod243 + rejected_parity + rejected_prime + exact_tests
```

Counters measure generators and bounded curve intervals, not independent
discovery chances. A digest is an error-detection checksum. It is **not proof
of donated CPU, identity, possession of special hardware or discovery odds**.

The usual manual bank-in is compact:

```json
{
  "schema":"math-gambling-bank-v1",
  "contributor":{"name":"Your name","github":"your-handle"},
  "tasks":[{"task":{"version":1,"engine":"mg114-offset-v1","context":"c00","row":"0","block":0},"digest":"64 lowercase hexadecimal characters"}]
}
```

The displayed digest above is illustrative, not an accepted submission.
Each claim may include the engine's `hits` array. Banks contain 1–256 claims and
at most 60,000 UTF-8 bytes. Paste the bank JSON into a GitHub issue body with a
title beginning `[bank]` or `[compute]` so the collector recognizes it. The
browser offers a copy/download step rather than placing a large payload into a
URL. Older full-result receipts (`math-gambling-receipt-v1`, `results`, 1–8
results, at most 8,192 bytes) remain supported by ingestion.

Actions replays new accepted tasks using the trusted Python engine and compares
the recomputed digest. Self-reported runtime and counters do not determine
credit. The authenticated GitHub issue author is the provenance for a bank;
the entered name and GitHub field are self-reported. First accepted unique task
credit is not a scientific authorship decision. Exact discoveries are retained
even when their enclosing task claim is malformed or already credited.

The current replay budget is deliberately limited; a bank may be partially
verified and resumed on later checks. Uploading or submitting is not the same
as verification. Work awaiting replay stays out of verified totals.

## Shared adaptation

After each 64 unique verified tasks, the aggregator may publish a new frozen
`data/strategy.json` epoch. It uses server-measured replay cost and deterministic
logical position counts, retaining a 40% uniform context exploration floor.
This optimizes a **cost proxy**, not a learned probability of discovering 114.
Uniform task sampling and this proxy can both have substantial mathematical
sampling bias. The previous discovery-learning experiment did not demonstrate
better success than its uniform control.

The runner checks shared coverage after 64 additional completions or 60
seconds. Policy requests remain rate limited to at most once per minute. It validates the full fixed context set, finite
nonnegative weights and exploration floor. No downloaded policy may change
arithmetic, filters, task size or accepted mathematical bounds. `--offline`
uses the bundled coverage snapshot and a local policy or uniform weights,
and makes no network requests. It cannot know about work accepted since that
snapshot was published.

## Local runner

From the repository root, with Python 3.11 or newer:

```sh
python3 tools/runner.py --minutes 60 --workers 4 --name "Your name" --github your-handle
```

This uses a process pool and writes a SQLite checkpoint, append-only result
journal, bank JSON files and final status into `math-gambling-run/`. It does not
submit results by default. Name/GitHub can be entered interactively when flags
are omitted. `--output` chooses a different checkpoint directory. The output
directory is locked to one controller. Restarting with the same identity
resumes unfinished tasks and avoids locally completed task IDs.

Each worker writes any exact hit to a separate durable file before returning it
to the parent. The parent verifies and preserves it before ordinary accounting.
A hit halts new scheduling. Ctrl-C also stops new scheduling and drains the
small running tasks. Abrupt operating-system or storage failures are not
magically impossible; an unfinished task never earns completed-task credit.

The default local outbox stops at approximately 4,096 unsubmitted task claims.
Bank a file manually, then acknowledge that action using its filename:

```sh
python3 tools/runner.py --name "Your name" --github your-handle --mark-banked bank-EXAMPLE.json
```

This marks it **reported submitted**, not independently verified. An explicit
`--submit` flag instead authorizes authenticated GitHub CLI issue creation, at
most one bank per minute. The runner checks for an existing bank issue first.
Ambiguous submissions are retained and require manual inspection rather than
blindly repeating a possibly successful external action. `--offline` and
`--submit` cannot be combined.

## Verification commands and limitations

```sh
python3 -m unittest discover -s tests -p test_search.py
node tests/test_engine.mjs
```

These include direct small-triple enumeration, sieved versus unsieved checks,
five published positive regressions in Python, four in JavaScript, exact square
boundaries, norm identities, signed residue exclusions, malformed task inputs,
all 81 contexts and endpoint chunks. The 243 cross-language task corpus currently
contains 34,824 curve checks, 47,544,575 logical q positions and 84 final exact
tests, with identical complete results and digests. No solution of 114 is
invented as a positive fixture.

This is substantial testing, not a formal proof of the complete runtime,
browser, operating system and synchronization infrastructure. Finding a real
triple would make verification simple; reaching that triple remains the open
research challenge.

### Attribution after browser computation

The browser starts anonymously. At banking time, the participant can select a display alias and an optional claimed GitHub handle. This metadata belongs to the bank; it does not modify the exact saved task result or its digest. A newly named bank has a new canonical bank digest, while previous prepared banks remain available locally. Actual leaderboard identity still comes from the authenticated GitHub issue author, and task identifiers are credited at most once.

Optional `contributor.url` links the display alias to an http(s) website. It is omitted when empty and is never part of a mathematical task digest. The collector strips malformed URLs, credentials, whitespace and control characters without discarding valid computation. The latest uniquely credited task may update the alias and link for its authenticated submitter; duplicate claims cannot update another participant or earn more credit. Website ownership is self-declared.


## Exact shared completed-task index

`data/coverage/index.json` has schema `math-gambling-coverage-v1`, engine
`mg114-offset-v1`, integer `revision`, equal `verified_task_count`, UTC
`updated_at`, and a `shards` object containing all contexts `c00` through `c80`.
A revision is the accepted unique-task count, not a scheduling epoch. Policy
epochs still advance only at 64-task boundaries.

Each context descriptor contains `file`, `sha256`, and integer `count`. Its
immutable filename is `<context>-<sha256>.json`, relative to the index's
directory. The shard has schema `math-gambling-coverage-shard-v1`, the same
engine, its `context`, and `tasks`: every accepted canonical task ID in that
context, sorted lexicographically without duplicates. Empty contexts have
explicit empty shards. The counts of all 81 shards sum to the revision.

SHA-256 is computed over the exact file bytes, including JSON whitespace and
the final newline. Clients must hash received bytes, not parse and reserialize
them before hashing. They validate the engine, fixed context set, counts,
canonical IDs, sorted uniqueness, filename and digest before using exact
membership. The manifest is capped at 128 KiB; each context at 8 MiB and
100,000 IDs. Invalid or unavailable required online data pauses dispatch.
The publisher also enforces these limits and never silently truncates coverage.

Only independent accepted replay records enter this index. New immutable
shards are written before the manifest is atomically replaced, and old shards
are retained so older manifests still resolve. Publication rejects a regressed
count or removal or replacement of a previously recorded ID. No mathematical
candidate is excluded merely because of a low model score or a failed proposal.
The index covers completed deterministic tasks, not every generator domain or
all historical searches.

Issue opened, edited and reopened events trigger the trusted verifier for
`[bank]` and `[compute]` titles, alongside hourly reconciliation. Submitted
content remains bounded data. It never modifies executable workflow code or
the mathematical kernel. Negative work still receives full independent replay;
event-driven scheduling does not weaken verification or change the 64-task
calibration rule. Published feedback waits for verification and Pages delivery.

A fresh random seed is scheduling provenance, not proof of useful compute.
Browser results retain the seed, PRNG algorithm, policy epoch and checked
coverage revision outside the immutable mathematical result digest. The native
runner also keeps a local audit trail. Reproducing an adaptive selection needs
its policy and coverage history and actual dispatched tasks, not only its seed.
Concurrent or offline clients can repeat work they cannot yet know is complete.

There is no calibrated conversion from these selected domains to reference
core-days or a discovery probability. Analytic expected counts and conservation
checks can expose mistakes but cannot certify that every candidate was visited.
The finite negative claim depends on the exact task enumeration and replay;
the positive claim is the exact integer identity.
