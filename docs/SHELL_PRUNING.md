# Exact shell pruning

Measured on 11 September 2026, this optimization improved throughput on a fixed 243-task corpus by about **1.13× in Python** and **1.10× in Node.js**. Completely empty tasks improved by about 3.4–3.6×. These are local measurements; they do not establish a 5× campaign speedup or better odds per distinct mathematical candidate.

## What is proved before skipping work

For a fixed row, write

\[
a(t)=a_0+\ell t,\qquad N(a)=a^3-342bc\,a+114b^3+12996c^3.
\]

The shell requires \(\ell d_{\rm lo}<N(a)\leq\ell d_{\rm hi}\). The kernel computes a lower bound on \(|a|\) over the block from its two integer endpoints. If that bound proves \(3a^2-342bc\geq0\) throughout the interval, the cubic is nondecreasing there. Exact integer binary searches then retain only the strict lower and inclusive upper shell interval.

When the derivative bound does not prove monotonicity, the whole block survives. No approximate cube root, floating-point shell bound, or learned exclusion is used. JavaScript uses BigInt for the polynomial and bounds; its finite indices remain exact safe integers.

The row's constant polynomial terms are also computed once. Since \(N(a+\ell)\equiv N(a)\pmod\ell\), checking divisibility at the first generator covers skipped generators too. The existing per-generator check remains on retained work.

Pruned values still count toward `generators` and `outside_shell`. Empty tasks still produce complete receipts. Task IDs, all canonical counters, hit order, exact results, and digests remain unchanged.

## Measurements

Both versions ran in the same process on this arm64 Mac using Python 3.14.6 and Node.js 26.3.1. Timings include complete task computation and receipt hashing. Each baseline/optimized pair alternated execution order. Results were compared outside the timed section.

| Corpus group | Tasks | Python baseline → optimized | Node baseline → optimized |
| --- | ---: | ---: | ---: |
| All tasks | 243 | 1197.70 → 1057.90 ms | 610.41 → 554.51 ms |
| Wholly outside the shell | 162 | 112.07 → 33.11 ms | 58.98 → 16.46 ms |
| Partly outside the shell | 54 | 495.27 → 483.22 ms | 253.80 → 236.02 ms |
| Entirely inside the shell | 27 | 599.30 → 602.79 ms | 303.45 → 294.84 ms |

Entries are medians of five warm pairs, except the Node all-task confirmation, which used eleven pairs after two additional full-corpus warmups. The initial five Node all-task pairs were noisy, with medians of 632.33 → 624.07 ms. Both runs are retained in the [raw benchmark data](../research/benchmarks/shell-pruning-2026-09-11.json). Sieve-dominated tasks gained little, and the Python full-shell group was effectively flat. These groups are a regression corpus, not an estimate of the live scheduler's task distribution.

## Reproducible corpus and checks

In context order `c00` through `c80`, the three tasks use `(row, block)`:

1. `(0, 0)`;
2. `(floor((totalRows−1)/128)×128, blocks−1)`;
3. `(floor(floor(totalRows/7)/128)×128, floor(blocks/2))`.

The baseline is commit `66b5274a8a438f2d97879140ffaba7813f92d3d2`, with these Git blob IDs:

- Python: `bd30211375040722a0e83344d51977d09133b6aa`.
- JavaScript: `585853a6923db7c517b0f5c40e5372d974e9e70e`.

The SHA-256 of the ordered canonical result array is `b8db130a82bd3cfd37f3d99e4de84c112b6ffb9176f51d12618b3a9a7f9bb780` before and after pruning in both languages. The dedicated tests also check 3,000 integer intervals per language, including huge coefficients, shell-boundary equality, nonmonotone fallback, and divisibility. Existing arithmetic and positive-callback regressions pass.

```sh
python3 -m unittest discover -s tests -p test_shell_pruning.py -v
node --test tests/test_shell_pruning.mjs tests/test_engine.mjs tests/test_worker.mjs
```

## Completed-curve observer

Python `run_task(task, on_hit=None, on_curve=None)` optionally reports each completed scan as `{D, r, s, qlo, qhi, minimal_abs_z}`. The five numerical fields are canonical decimal strings; `minimal_abs_z` is `True`. Bounds are inclusive, `z=r+D*q`, `s=x+y`, `D=abs(s)`, and the scan accepts identities only when `abs(z) <= min(abs(x), abs(y))`.

The observer runs after `scan_curve` returns successfully and is excluded from the result digest. Its exceptions abort the task. Consumers must wait for the complete matching task digest before publishing accumulated negative coverage; positive hits keep their earlier immediate callback.
