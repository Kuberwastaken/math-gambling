# Math Gambling

The sum-of-three-cubes problem asks which integers can be written as three integer cubes. Our target is **114**, an unresolved case in the literature reviewed for this campaign:

$$x^3+y^3+z^3=114,\qquad x,y,z\in\mathbb{Z}.$$

The coordinates may be positive or negative, and enormous cubes can nearly cancel. An answer is one exactly verified integer triple. There is no known small search bound that guarantees our campaign will contain one.

Our current approach generates modular roots through **cubic-field norms**, rejects impossible candidates with exact arithmetic, and searches 81 explicitly bounded contexts. A shared completed-task index avoids work already known to be finished. Measured cost and a declared geometric prior adjust allocation after each 64 verified tasks, while preserving 40% uniform task proposals. It has not learned where a solution is likely to be.

This is an open computational research project by Kuber Mehta. The gamble is spare processor time for a possible mathematical discovery. We publish the algorithms, finite search definitions, unsuccessful experiments, verification records and evolving model so the work can be inspected and reproduced.

**[Contribute in your browser →](https://kuber.studio/math-gambling/)** · [Run on your own computer](https://github.com/Kuberwastaken/math-gambling/blob/main/docs/RUNNER_SETUP.md) · [Read the research verdict](https://github.com/Kuberwastaken/math-gambling/blob/main/research/archive/research-2026-09-09/SEARCH_VERDICT.md) · [Read the working paper](https://kuber.studio/math-gambling/paper/)

<!-- MATH_GAMBLING_SNAPSHOT:START -->

## Current verified campaign

Published observation: **2026-09-11 17:34:49 UTC**. This section updates after trusted receipt processing.

| Quantity | Verified total |
| --- | ---: |
| Unique finite tasks | 269,410 |
| Coefficient-generator inputs | 507,624,448 |
| Bounded curve intervals | 36,968,746 |
| Logical quotient positions | 27,109,740,991 |
| Exact integer square tests | 55,975 |
| Independently verified identities for 114 | 0 |

![Verified work and changing allocation](data/readme-progress.svg)

These are actual fixed-task units from independent replay, not claimed client seconds or independent chances of discovery. The separate [Mac snapshot](data/mac.json) uses different domains and is not added to these totals.

### Global leaderboard

| Rank | Alias | Authenticated GitHub account | Verified inputs | Unique tasks |
| ---: | --- | --- | ---: | ---: |
| 1 | [Benjamaxxing](<https://everyreason.bandcamp.com>) | [@EveryReasonTo](https://github.com/EveryReasonTo) | 464,975,872 | 246,772 |
| 2 | Varun | [@weavermonkey](https://github.com/weavermonkey) | 34,113,536 | 18,083 |
| 3 | culnaen | [@culnaen](https://github.com/culnaen) | 1,443,840 | 775 |
| 4 | Vasudev | [@VasudevCodeReaper](https://github.com/VasudevCodeReaper) | 963,584 | 512 |
| 5 | Thanos | [@sparkingcharms](https://github.com/sparkingcharms) | 960,512 | 512 |
| 6 | James | [@JamesT-cmd](https://github.com/JamesT-cmd) | 954,368 | 512 |
| 7 | [Kuber](<https://kuber.studio>) | [@Kuberwastaken](https://github.com/Kuberwastaken) | 704,512 | 384 |
| 8 | V01D0 | [@V01D0](https://github.com/V01D0) | 538,624 | 286 |
| 9 | [Dr. Ashish Bamania](<https://www.intoai.pub/>) | [@ashishbamania](https://github.com/ashishbamania) | 491,520 | 256 |
| 10 | [Ijtihed](<https://ijtihed.com>) | [@Ijtihed](https://github.com/Ijtihed) | 487,424 | 256 |

**200,708 / 269,410 verified tasks contain no admitted curve intervals.** They remain completed coefficient-domain checks; task counts are not distinct-curve coverage. Exact shell pruning can certify those exclusions without visiting every coefficient individually.

[Mathematical interval export](data/math-coverage/index.json) · [Export scope and limitations](https://github.com/Kuberwastaken/math-gambling/blob/main/docs/MATHEMATICAL_COVERAGE.md)


Rank is based on replayed coefficient inputs. Alias websites are optional and self-declared; account attribution comes from the accepted GitHub issue creator.

### The current allocation

**Epoch 4209**, frozen from **269,376 verified tasks**. The next policy update needs **30 more accepted unique tasks**. The arrows below are regenerated from the current weights and recorded epoch history.

```mermaid
flowchart TD
    H0["Epoch 4206: 269,184 tasks; c63 3.91%"]
    H1["Epoch 4207: 269,248 tasks; c63 3.91%"]
    H0 --> H1
    H2["Epoch 4208: 269,312 tasks; c63 3.92%"]
    H1 --> H2
    H3["Epoch 4209: 269,376 tasks; c45 3.92%"]
    H2 --> H3
    Policy["Current policy: epoch 4209"]
    H3 --> Policy
    Policy --> Explore["40% uniform exploration across 81 contexts"]
    Policy --> Cost["60% weighted by geometry-weighted curve exposure / cost"]
    Explore --> Mix["Combined task-selection weights"]
    Cost --> Mix
    Mix --> C0["c45: 3.92%"]
    Mix --> C1["c63: 3.91%"]
    Mix --> C2["c09: 3.81%"]
    Mix --> Rest["Other 78 contexts: 88.37% combined"]
    C0 --> Check["Skip completed IDs; run exact bounded task"]
    C1 --> Check
    C2 --> Check
    Rest --> Check
    Check --> Replay["Bank result; independently replay"]
    Replay --> Gate["64 new verified tasks completes an epoch"]
    Gate --> Policy
```

Weights describe task-selection shares, not CPU-time shares or discovery probabilities. 40% uniform task proposals; 60% geometry-weighted curve yield / cost. Zero-curve tasks count toward 

### Model history and evidence

| Epoch | Verified-task boundary | Largest allocation | Weight |
| ---: | ---: | --- | ---: |
| 4205 | 269,120 | c63 | 3.9174% |
| 4206 | 269,184 | c63 | 3.9061% |
| 4207 | 269,248 | c63 | 3.9109% |
| 4208 | 269,312 | c63 | 3.9198% |
| 4209 | 269,376 | c45 | 3.9156% |

Every accepted task retains its full replay result and server timing. Seeds and dispatch provenance stay with client evidence. Complete policy vectors, historical boundaries and bank decisions remain inspectable:

[Current policy](data/strategy.json) · [Complete model history and bank audits](data/cluster.json) · [Verified task records](data/receipts/tasks/) · [Exact completed-task index](data/coverage/index.json) · [Working paper](https://kuber.studio/math-gambling/paper/)

The separate discovery-learning experiment failed its promotion gate. This campaign learns execution cost and applies a declared geometric prior; it has not established a discovery predictor.

<!-- MATH_GAMBLING_SNAPSHOT:END -->

## The mathematical search

The public engine uses cubic-field norm generators to reach selected large divisors without factoring each one. With $\alpha^3=114$ and $\gamma=a+b\alpha+c\alpha^2$,

$$N(\gamma)=a^3+114b^3+12996c^3-342abc.$$

Adjoint coefficients produce a cube root $r$ of 114 modulo a suitable divisor $D$ when the required inverse exists. Writing $z=r+Dq$ reduces the remaining search to a bounded integer-square condition. Norm-shell bounds, signed congruences, parity and modular square tests eliminate impossible candidates before the exact check. Failed inverses are recorded limitations, not proof that those divisors contain no solution.

The 81 contexts are the Cartesian product of three class multipliers $\ell\in\{1,5,25\}$, three coefficient shapes, three norm shells, and three quotient bands. Here $D_0=\lfloor10^{19}/54\rfloor$; the shells are $(D_0,2D_0]$, $(2D_0,4D_0]$, $(4D_0,8D_0]$, and the ratio bands are $(0,64]$, $(64,256]$, $(256,4096]$, subject to the protocol's minimum-coordinate constraint. [Exact definitions and arithmetic](https://github.com/Kuberwastaken/math-gambling/blob/main/docs/PROTOCOL.md) specify what one completed task excludes.

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

[Policy equations and limitations](https://github.com/Kuberwastaken/math-gambling/blob/main/docs/GEOMETRIC_POLICY.md) · [Mathematical coverage scope](https://github.com/Kuberwastaken/math-gambling/blob/main/docs/MATHEMATICAL_COVERAGE.md) · [Branch and deployment design](https://github.com/Kuberwastaken/math-gambling/blob/main/docs/BRANCHES.md)

The initial discovery-learning experiment failed its promotion test. The new geometric preference is uncalibrated for our selected norm families. A stronger sieve, reduced duplicate work and better cost predictions are useful, but none establishes the likelihood of finding 114.

## What verified work means

Browser workers use the Rust WebAssembly kernel with a BigInt fallback. The local runner can use the same fixed-width Rust kernel, with arbitrary-precision arithmetic for the final check and an independent Python reference. [Matched benchmarks](https://github.com/Kuberwastaken/math-gambling/blob/main/research/benchmarks/native-wasm-2026-09-11.json) measured **20.2× native vs Python** and **5.2× WASM vs JavaScript** on this Mac; these are kernel comparisons, not discovery odds or guaranteed whole-campaign speedups. [Build, bounds and tests](https://github.com/Kuberwastaken/math-gambling/blob/main/docs/NATIVE_KERNEL.md). Each result has a fixed task descriptor and deterministic digest. GitHub ingestion fully replays new-account tasks, then samples eligible new negative banks at 1-in-20 after submission. Only independently replayed tasks with matching digests credit the actual issue creator; other claims stay unverified. Submitted seconds and claimed machine speed do not increase the leaderboard. Any candidate identity receives a separate exact cube check, even when its surrounding receipt is malformed. A standalone identity can also be submitted for verification without claiming any completed search tasks; it earns no invented task credit.

The [shared completed-task index](https://github.com/Kuberwastaken/math-gambling/blob/cluster-data/data/coverage/index.json) contains exact task IDs in SHA-256 checked, immutable hash-routed chunks. Runners v0.3.1 and newer read coverage v2; older runners need an upgrade. Clients skip IDs in their checked snapshot and local completed records. There is no probabilistic membership filter that could discard unvisited work. Simultaneous clients can still select the same unfinished task, and stale or offline snapshots cannot know about later completions; the server deduplicates accepted work.

A digest detects changed bytes, but does not prove who physically supplied CPU time. The exact ledger still requires full task replay, but the [negative-audit policy](https://github.com/Kuberwastaken/math-gambling/blob/main/docs/NEGATIVE_AUDITS.md) leaves most eligible claims outside that ledger to reduce replay load. Unsampled claims earn no verified score, train no model and cannot suppress future searches. Existing scores are preserved; score growth after sampling reflects only checked tasks. Expected analytic counts and conservation checks are useful diagnostics; they do not prove that each candidate was visited. See the [protocol](https://github.com/Kuberwastaken/math-gambling/blob/main/docs/PROTOCOL.md), [cluster design](https://github.com/Kuberwastaken/math-gambling/blob/main/docs/CLUSTER.md), and [response to the external critique](https://github.com/Kuberwastaken/math-gambling/blob/main/docs/REVIEW_RESPONSE.md).

## Participate, reproduce and review

Use the [browser](https://kuber.studio/math-gambling/) or the [local runner](https://github.com/Kuberwastaken/math-gambling/blob/main/docs/RUNNER_SETUP.md) to contribute. Keep your saved receipts until the published audit confirms them. The [source archive](https://github.com/Kuberwastaken/math-gambling/blob/main/docs/ARCHIVE.md), [validation record](https://github.com/Kuberwastaken/math-gambling/blob/main/docs/VALIDATION.md), [developer setup](https://github.com/Kuberwastaken/math-gambling/blob/main/docs/DEVELOPMENT.md), and [release evidence](https://github.com/Kuberwastaken/math-gambling/blob/main/docs/RELEASE_STATUS.md) support independent review.

The [working paper](https://github.com/Kuberwastaken/math-gambling/blob/main/paper/math-gambling-draft.tex) records implementation and evidence. Its result and discovery attribution remain blank pending an independently verified and reviewed identity.

## Attribution and license

The mathematical approaches are credited to Booker–Sutherland, Grantham–Walsh and the primary sources in the [research verdict](https://github.com/Kuberwastaken/math-gambling/blob/main/research/archive/research-2026-09-09/SEARCH_VERDICT.md). This independent project is not endorsed by those authors. Original project software is GPL-2.0-or-later; upstream material retains its notices.

[September audit corrections](https://github.com/Kuberwastaken/math-gambling/blob/main/docs/AUDIT_FIXES.md): immediate discovery recovery, bounded warmed replay, exact chunked coverage and the v0.3.1 runner.


<!-- LEARNING:START -->

## Experimental task learning

Frozen through **269,312 verified tasks**; **263 models** and **262 completed forward-window evaluations**. Mode: **shadow**, with no production influence.

The challenger predicts server CPU, quotient positions, curves and exact-test counts from context and coarse coefficient/block geometry. Shrinkage keeps sparse regions close to their context baseline. These are arithmetic and cost predictions, not winning probabilities.

```mermaid
flowchart TD
    Receipts[Independently replayed receipts] --> Ledger[Canonical ledger]
    Ledger --> Production[Geometry and measured cost: 40 percent exploration]
    Ledger --> Freeze[Freeze each 1024 task boundary]
    Freeze --> Spatial[Train spatial challenger excluding held-out geometry]
    Spatial --> Future[Score next 1024 accepted tasks]
    Future --> Report[Publish errors and immutable model hashes]
    Report --> Gate[Controlled policy benchmark still required]
    Gate --> NoPromotion[No automatic discovery-policy promotion]
```


![Challenger prediction error through frozen evaluations](data/learning/evolution.svg)

Latest evaluation: tasks 268,289–269,312. Lower mean absolute log1p prediction error is better.

| Quantity | Context baseline | Spatial challenger |
| --- | ---: | ---: |
| cpu_ms | 1.2084 | 1.0198 |
| quotient_points | 7.8099 | 7.4115 |
| curves | 4.0400 | 3.6534 |
| exact_tests | 0.1432 | 0.1278 |

Unseen-geometry evaluation: 177 tasks. Full errors and nonzero-count support are in the report.

![Exploratory controlled pilot: quotient exposure per CPU](data/learning/pilot.svg)

Historical backfills are retrospective chronological tests, not a randomized A/B experiment. New snapshots remain frozen while later arrivals are evaluated. Arrival time is not computation time; submitted work is selection-biased. Improved prediction error alone cannot promote a search policy.

[Latest report](data/learning/latest.json) · [Frozen model and evaluation records](data/learning/mg114-spatial-shadow-v1/1df1bb496828a2dc/) · [Design and promotion protocol](https://github.com/Kuberwastaken/math-gambling/blob/main/docs/LEARNING.md)

<!-- LEARNING:END -->
