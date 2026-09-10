# Deterministic cancellation-plane arm

`plane_worker.c` implements an additional finite coefficient family. Its purpose is to explore a different part of the norm parametrization, not to assert that solutions concentrate there. The real-plane idea appears in [Walsh's 2022 slides, pages 20–21](https://ntrg.math.unideb.hu/GW2022Talk.pdf); the norm/curve method is described by [Grantham–Walsh](https://arxiv.org/abs/2211.12149).

The worker includes `campaign_worker.c` with its main function renamed, so modular sieving, quotient-band bounds, PARI exact square testing, and final cube verification are shared. It defines a new generator and emits the same tile statistics with `kind: "plane"`. Changes to the shared file require rebuilding and revalidating both workers.

For an ideal-class multiplier `ell ∈ {1,5,25}` and radius `R`, the family is:

```
b,c ∈ [-R,R] ∩ Z
t ∈ {-2,-1,0,1,2}
M = 1000000000000000000
P = 4848807585839879338
Q = 23510935004498358840
u = (-4b-16c) mod ell, in [0,ell-1]
n = -Pb-Qc-uM
h = floor((2n+ell*M)/(2ell*M))
a = u+ell*(h+t)
```

`P/M` and `Q/M` approximate `114^(1/3)` and `114^(2/3)`. The integer formula specifies the family exactly; it uses no floating-point operations. It chooses the nearest point of the required residue lattice to the rational cancellation plane, then one of five offsets. Exact half ties round toward positive infinity. The constants are certified by integer cube inequalities in `validate_plane.py`. The rational approximation differs from the true real-plane expression by less than `10^-10` throughout the allowed radius range; membership is nevertheless defined by the exact rational formula, including possible rounding-boundary cases.

The congruence `a+4b+16c ≡ 0 (mod ell)` ensures the norm

```
N = a^3 + 114b^3 + 12996c^3 - 342abc
```

is divisible by `ell`. Every generated norm checks this identity at runtime. Supported candidates use `D=|N|/ell`, `B=114c²-ab`, and `C=b²-ac`. If `C` is invertible modulo `D`, the generated root is `r=B/C mod D`, and the worker verifies `r³ ≡ 114 mod D` before searching its curve.

The finite generator domain has exactly `5(2R+1)^2` indices. An affine permutation `v=(stride*index+offset) mod total`, with `gcd(stride,total)=1`, visits it bijectively. Decode `t=v mod 5-2`, then decode `b,c` from the remaining base-`2R+1` digits. Different decoded `b,c,t` produce different coefficient triples because the five offsets give distinct `a`. Thus a completed tile certifies processing its specified generator indices under the stated filters. It does **not** certify distinct-curve coverage: different generators can represent the same curve.

An exact sign-symmetry reduction now skips a triple only if `(c,b,a)` is lexicographically negative **and its exact opposite triple belongs to the same finite plane domain**. Opposite triples have the same `D,B,C`, up to the harmless sign of the norm, so they give the same root and quotient interval. The membership test recomputes the opposite rational-plane base and verifies its required offset is an integer in `[-2,2]`. This explicit check handles rounding ties at the domain edges; it does not assume central symmetry. `symmetry_rejected` reports these skips separately. The canonical representative may lie outside a completed index prefix. Therefore such a prefix certifies processing its indices modulo the stated symmetry reduction, not that every associated quotient interval is globally empty. Validation compares complete small-domain `(D,root)` sets before and after pruning, and uses 735 additional synthetic rational-plane cases with exact half ties to test absent-opposite boundaries.

The radius is restricted to `1 ≤ R ≤ 100,000,000`. Then `|a| < 29R+64`, and every intermediate in the norm and rational-plane calculation is safely below signed 128-bit limits. A norm yielding `D > 2^63-1` is explicitly counted as `unsupported_D` and is not searched. This is a documented implementation limit, not a mathematical exclusion. Other counters separately identify zero norms, invalid divisors, noninvertible `C`, and intervals inside the previously reported coverage.

Example bounded tile:

```sh
bin/plane_worker tile 1 20000000 0 1000000 128 adaptive 0 114
```

The full contract is:

```text
plane_worker tile ELL RADIUS START COUNT RATIO POLICY [MIN_RATIO [PERM_SEED]]
plane_worker dump ELL RADIUS START COUNT [PERM_SEED]
```

`dump` exposes exact generator outputs for independent auditing; it performs no curve search. `curve` and `interval` commands pass through to the shared checker's existing validation interface.

Validation in `runs/plane-validation.json` covers **9,870 independently reconstructed coefficient triples and 4,196 usable modular roots**, small complete-domain bijections, tail indices of large domains, all three multipliers, exact constant certification, fixed/adaptive result equivalence, invalid-bound rejection, and recovery on two known curves including the large solution for 3. An undefined-behavior sanitizer build additionally tested maximum-radius and maximum-seed inputs for each multiplier. The known-curve recovery is a correctness check, not a blind discovery claim.

A bounded smoke pilot **before adding sign-symmetry pruning**, at radius 20 million, ratio 128, and all three multipliers processed **3 million generators, 883,355 curve checks, 92,234,937 quotient candidates, and 178 exact square checks**, finding no solution. Its three subprocesses took about **0.572 seconds** in total on this Mac during that run. The historical statistics and source hashes are in `runs/plane-pilot.json`. These are selective, potentially repeated curve checks; this timing establishes neither a discovery-probability advantage nor a comparison against an independently built Booker–Sutherland search.

Run the independent audit with:

```sh
python3 validate_plane.py
```

For sanitizer evidence, compile `plane_worker.c` with Clang's `-fsanitize=undefined -fno-sanitize-recover=all`, make the PARI shared library available beside that executable, and pass it with `--ubsan-binary /absolute/path/to/executable`.
