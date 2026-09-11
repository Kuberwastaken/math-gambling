# Math Gambling

The sum-of-three-cubes problem asks which integers can be written as three integer cubes. Our target is **114**, an unresolved case in the literature reviewed for this campaign:

$$x^3+y^3+z^3=114,\qquad x,y,z\in\mathbb{Z}.$$

The coordinates may be positive or negative, and enormous cubes can nearly cancel. An answer is one exactly verified integer triple. There is no known small search bound that guarantees our campaign will contain one.

Our current approach generates modular roots through **cubic-field norms**, rejects impossible candidates with exact arithmetic, and searches 81 explicitly bounded contexts. A shared completed-task index avoids work already known to be finished. Measured cost and a declared geometric prior adjust allocation after each 64 verified tasks, while preserving 40% uniform task proposals. It has not learned where a solution is likely to be.

This is an open computational research project by Kuber Mehta. The gamble is spare processor time for a possible mathematical discovery. We publish the algorithms, finite search definitions, unsuccessful experiments, verification records and evolving model so the work can be inspected and reproduced.

**[Contribute in your browser →](https://kuber.studio/math-gambling/)** · [Run on your own computer](docs/RUNNER_SETUP.md) · [Read the research verdict](research/archive/research-2026-09-09/SEARCH_VERDICT.md) · [Read the working paper](https://kuber.studio/math-gambling/paper/)

<!-- MATH_GAMBLING_SNAPSHOT:START -->

## The live campaign

[Live leaderboard, current totals and evolving Mermaid allocation](https://github.com/Kuberwastaken/math-gambling/blob/cluster-data/README.md) · [Play on the website](https://kuber.studio/math-gambling/)

![Verified work and changing allocation](https://raw.githubusercontent.com/Kuberwastaken/math-gambling/cluster-data/data/readme-progress.svg)

Generated receipts, coverage and policy histories live on `cluster-data`. `main` holds reviewed code and research; `gh-pages` holds the built website. Routine Pages refreshes run every 20 minutes. Existing source-branch data is a frozen bootstrap snapshot for reproducible offline builds, not the latest campaign.

<!-- MATH_GAMBLING_SNAPSHOT:END -->

## The mathematical search

The public engine uses cubic-field norm generators to reach selected large divisors without factoring each one. With $\alpha^3=114$ and $\gamma=a+b\alpha+c\alpha^2$,

$$N(\gamma)=a^3+114b^3+12996c^3-342abc.$$

Adjoint coefficients produce a cube root $r$ of 114 modulo a suitable divisor $D$ when the required inverse exists. Writing $z=r+Dq$ reduces the remaining search to a bounded integer-square condition. Norm-shell bounds, signed congruences, parity and modular square tests eliminate impossible candidates before the exact check. Failed inverses are recorded limitations, not proof that those divisors contain no solution.

The 81 contexts are the Cartesian product of three class multipliers $\ell\in\{1,5,25\}$, three coefficient shapes, three norm shells, and three quotient bands. Here $D_0=\lfloor10^{19}/54\rfloor$; the shells are $(D_0,2D_0]$, $(2D_0,4D_0]$, $(4D_0,8D_0]$, and the ratio bands are $(0,64]$, $(64,256]$, $(256,4096]$, subject to the protocol's minimum-coordinate constraint. [Exact definitions and arithmetic](docs/PROTOCOL.md) specify what one completed task excludes.

These finite generators and ratio bands do not cover every integer triple, every modular root, or a complete height box. They can overlap historical searches or the separate Mac campaign. No effective small bound guarantees that a representation lies in our chosen catalogue.

## What the model learns

Every 64 verified tasks freezes a policy. The production method combines a declared geometric band/shell prior with measured curve yield and aggregate CPU, including empty tasks. It keeps 40% uniform task proposals; those are selection shares, not CPU budgets or discovery probabilities.

```mermaid
flowchart TD
    Source[Reviewed source on main] --> Audit[Freeze post-submission random audit]
    Audit --> Replay[Independently replay selected tasks]
    Audit --> Claims[Retain other claims without verified credit]
    Replay --> Ledger[Canonical receipts on cluster-data]
    Ledger --> Geometry[Geometry prior plus measured curve yield and cost]
    Ledger --> Shadow[Spatial challenger: frozen predictions and later errors]
    Geometry --> Policy[Versioned production policy]
    Shadow --> Evidence[Report evidence; no automatic promotion]
    Policy --> Pages[Build gh-pages every 20 minutes]
    Evidence --> Pages
    Pages --> Clients[Independent local seeds and exact coverage checks]
    Clients --> Audit
```

[Policy equations and limitations](docs/GEOMETRIC_POLICY.md) · [Mathematical coverage scope](docs/MATHEMATICAL_COVERAGE.md) · [Branch and deployment design](docs/BRANCHES.md)

The initial discovery-learning experiment failed its promotion test. The new geometric preference is uncalibrated for our selected norm families. A stronger sieve, reduced duplicate work and better cost predictions are useful, but none establishes the likelihood of finding 114.

## What verified work means

Browser workers use the Rust WebAssembly kernel with a BigInt fallback. The local runner can use the same fixed-width Rust kernel, with arbitrary-precision arithmetic for the final check and an independent Python reference. [Matched benchmarks](research/benchmarks/native-wasm-2026-09-11.json) measured **20.2× native vs Python** and **5.2× WASM vs JavaScript** on this Mac; these are kernel comparisons, not discovery odds or guaranteed whole-campaign speedups. [Build, bounds and tests](docs/NATIVE_KERNEL.md). Each result has a fixed task descriptor and deterministic digest. GitHub ingestion fully replays new-account tasks, then samples eligible new negative banks at 1-in-20 after submission. Only independently replayed tasks with matching digests credit the actual issue creator; other claims stay unverified. Submitted seconds and claimed machine speed do not increase the leaderboard. Any candidate identity receives a separate exact cube check, even when its surrounding receipt is malformed. A standalone identity can also be submitted for verification without claiming any completed search tasks; it earns no invented task credit.

The [shared completed-task index](https://github.com/Kuberwastaken/math-gambling/blob/cluster-data/data/coverage/index.json) contains exact task IDs in SHA-256 checked, immutable hash-routed chunks. Runners v0.3.1 and newer read coverage v2; older runners need an upgrade. Clients skip IDs in their checked snapshot and local completed records. There is no probabilistic membership filter that could discard unvisited work. Simultaneous clients can still select the same unfinished task, and stale or offline snapshots cannot know about later completions; the server deduplicates accepted work.

A digest detects changed bytes, but does not prove who physically supplied CPU time. The exact ledger still requires full task replay, but the [negative-audit policy](docs/NEGATIVE_AUDITS.md) leaves most eligible claims outside that ledger to reduce replay load. Unsampled claims earn no verified score, train no model and cannot suppress future searches. Existing scores are preserved; score growth after sampling reflects only checked tasks. Expected analytic counts and conservation checks are useful diagnostics; they do not prove that each candidate was visited. See the [protocol](docs/PROTOCOL.md), [cluster design](docs/CLUSTER.md), and [response to the external critique](docs/REVIEW_RESPONSE.md).

## Participate, reproduce and review

Use the [browser](https://kuber.studio/math-gambling/) or the [local runner](docs/RUNNER_SETUP.md) to contribute. Keep your saved receipts until the published audit confirms them. The [source archive](docs/ARCHIVE.md), [validation record](docs/VALIDATION.md), [developer setup](docs/DEVELOPMENT.md), and [release evidence](docs/RELEASE_STATUS.md) support independent review.

The [working paper](paper/math-gambling-draft.tex) records implementation and evidence. Its result and discovery attribution remain blank pending an independently verified and reviewed identity.

## Attribution and license

The mathematical approaches are credited to Booker–Sutherland, Grantham–Walsh and the primary sources in the [research verdict](research/archive/research-2026-09-09/SEARCH_VERDICT.md). This independent project is not endorsed by those authors. Original project software is GPL-2.0-or-later; upstream material retains its notices.

[September audit corrections](docs/AUDIT_FIXES.md): immediate discovery recovery, bounded warmed replay, exact chunked coverage and the v0.3.1 runner.


<!-- LEARNING:START -->

## Experimental task learning

The spatial model learns cost and arithmetic counts from verified task geometry. It remains in shadow; improved prediction error has not demonstrated better discovery odds.

![Frozen challenger evaluations](https://raw.githubusercontent.com/Kuberwastaken/math-gambling/cluster-data/data/learning/evolution.svg)

[Live learning report](https://github.com/Kuberwastaken/math-gambling/blob/cluster-data/README.md#experimental-task-learning) · [Design and promotion gates](docs/LEARNING.md)

<!-- LEARNING:END -->
