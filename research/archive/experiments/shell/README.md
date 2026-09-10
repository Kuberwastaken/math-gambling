# Exact norm-shell generation experiment

**Result:** exact interval inversion removed 86.5–88.2% of coefficient positions from the selected shell search. Measured total CPU gains were **1.09–1.20× at ratio 64**, and **1.02–1.05× at ratio 4096**. Most runtime still goes to the surviving curves, so the large reduction in positions does not imply an equally large runtime improvement.

This is an isolated experiment for a possible later campaign. Production sources, binaries, and the active ledger were not modified. The experiment includes the frozen `../../campaign_worker.c` read-only and links to its existing PARI library. The main controller **does not integrate shell work units**; this executable must not be substituted for a production worker.

## Exact work domain

For `ell` equal to 1, 5, or 25 and radius `A`, a row fixes `b,c ∈ [-A,A]`. Its lattice is

```text
a0 = (-4b - 16c) mod ell
a  = a0 + ell*t,   -floor(A/ell) ≤ t ≤ floor(A/ell)
N  = a³ - 342bc*a + 114b³ + 12996c³
D  = |N|/ell
```

The requested shell is **D0 < D ≤ 2D0**. The `a` window is the actual lattice window above; its upper residue boundary can exceed `A`.

There are `(2A+1)²` row IDs. A deterministic bijective permutation maps row IDs to `(b,c)`. Tiles use `[START, START+ROWS)`; their endpoint conventions and seed are explicit. A hit's coefficient `index` is `row_id*t_width + (t+floor(A/ell))`, where `t_width=2floor(A/ell)+1`.

For each row, the derivative is `3(a²−114bc)`. When `bc>0`, `h=isqrt(114bc)` gives three disjoint integer segments: `a≤−h−1`, `−h≤a≤h`, and `a≥h+1`. The norm is monotone on each. Exact integer binary searches invert the two signed norm intervals belonging to the shell. No floating-point endpoint determines an exclusion.

The implementation also aggregates proved sign duplicates in a negative `(c,b)` row. It preserves the top lattice endpoint when that coefficient's opposite is outside the finite domain. Both reference and optimized methods use exact finite differences while traversing coefficients and the same downstream checker.

## Run a bounded tile

From this directory:

```sh
python3 build_shell.py
./shell_worker tile 1 50000 185185185185185185 0 64 64 fixed inversion
```

The complete CLI is:

```text
shell_worker tile ELL RADIUS D0 START ROWS RATIO POLICY METHOD [MIN_RATIO [SEED]]
```

- `METHOD=inversion` uses exact shell intervals and bulk sign equivalence pruning.
- `METHOD=direct` visits every lattice coefficient in precisely the same rows, tests the shell explicitly, and provides the reference comparison.
- `METHOD=probe` prints eligible integer intervals per row without searching curves.
- `MIN_RATIO` defaults to 0; `SEED` defaults to 114. Checker policies match the frozen worker, including fixed/adaptive and direct/wheel prefixes.

Each invocation prints checker statistics followed by a `shell_stats` record. `lattice_positions`, `eligible_inputs`, and `outside_shell` refer to the selected row domain; `rows` and `empty_rows` refer to complete row units. These are separate from curve and quotient counts. A mathematically excluded position is outside the requested **D shell**, not proof that it cannot belong to a solution elsewhere.

Use small tiles initially. A nonempty row can emit many coefficients. This experiment has no persistent scheduler, timeout splitting, or restart ledger. A future integration needs a new geometry/source identity and validated row or subrow checkpoint handling. Keep the current production campaign unchanged.

## Evidence and limitations

```sh
python3 validate_shell.py
python3 benchmark_shell.py --cpu-budget 12 --rows 64 --repeats 3
```

`validation.json` records 30 complete small domains, 188,730 independently enumerated coefficients, 3,228 native modular roots compared with Python, 80 exact shell-boundary cases, gapless row partitions, sign-equivalence preservation of `(D,r,q)` sets, and UBSan checks. Direct and inversion methods agree on their emitted candidates and checker accounting. The same fixed reference checking order makes prime-filter counts directly comparable.

`benchmark.json` contains three matched repeats for each of three multipliers and two ratio limits, using **6.08 total benchmark CPU-seconds**. Roughly 85–87% of sampled rows were empty. The production session was configured for four workers and remained running during these measurements; they are short CPU-time comparisons under concurrent load.

| Multiplier | Ratio 64 speedup | Ratio 4096 speedup |
|---|---:|---:|
| 1 | 1.20× | 1.03× |
| 5 | 1.18× | 1.02× |
| 25 | 1.09× | 1.05× |

The benchmark compares **identical deterministic rows and coefficients**, with and without shell inversion. Its distribution is different from the previous random pilots and from the production coefficient-tile traversal. These timings establish no increase in discovery odds and no comparison with the full Booker–Sutherland implementation.

Repeated curves, unhandled noninvertible coefficients, historical-coverage assumptions, and selective finite coefficient bounds remain limitations inherited from the underlying generator/checker. The experiment supplies a useful proved generation shortcut, not a route known to solve 114 in hours.
