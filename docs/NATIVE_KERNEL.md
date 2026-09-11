# Rust and WebAssembly kernel

The accelerated kernel implements **the same selective `mg114-offset-v1` tasks**, not a new exhaustive Booker–Sutherland campaign. It keeps task IDs, all logical counters, hit order and SHA-256 receipts identical. Python remains the independent verifier and comparison implementation. The Rust core handles enumeration and sieving; the existing Python runner handles worker budgets, seeds, checkpoints, GitHub login and banking.

## Run locally

Install Rust through [rustup](https://rustup.rs/), plus Python 3.11 or newer. From this repository (or the new runner source archive):

```sh
python tools/build_native.py
python tools/runner.py --kernel rust --name "Your alias" --github YOUR_USERNAME --workers 4 --minutes 60 --login --submit
```

Choose a worker count your machine supports. On Windows use `py` if `python` is not available. Each worker keeps a Rust process alive across tasks. Leave out `--login --submit` to compute without uploading. The default `--kernel python` remains available without a compiler. Do not share a live checkpoint directory between machines.

## Browser build

```sh
rustup target add wasm32-unknown-unknown
python tools/build_native.py --wasm
node --test tests/test_wasm_kernel.mjs
```

The same Rust library compiles to a small WebAssembly module with a capped JSON interface. Each Web Worker owns an instance. Identities are delivered immediately and independently checked with JavaScript BigInt. A failed load falls back to the original BigInt kernel; an arithmetic trap after starting a task is an error, never a completed negative receipt. No SIMD, threads-in-WASM, SharedArrayBuffer or cross-origin isolation is required.

## Integer bounds

All public input is validated against the fixed 81 contexts before arithmetic. Bounds below are deliberately conservative, not measured maxima:

- `|b|,|c| <= 6,000,000`, `ell <= 25`, `t <= 8191`, `|a| < 200,000,000`.
- The scaled offset numerator is below `2^89`; each norm expression and all intermediate additions fit signed 128 bits (sum of absolute terms below `2^85`).
- Admitted `D <= 8 floor(10^19/54) < 2^61`. Reduced modular products are below `2^122` and fit signed 128 bits. Extended Euclid runs only on reduced values below this bound.
- Public quotient endpoints have magnitude at most 4097. Large signed values are reduced once per curve; the prime sieve then uses only small signed integer operations (`p <= 61`).
- **The final cubes do not fit 128 bits.** That rare path uses `num-bigint`, integer square root and a fresh exact cube identity check. There is no floating-point rejection or truncated integer fallback.

Rust release builds retain overflow checks. A bound violation aborts the task; it cannot produce negative coverage. The only intentional wrapping operations are the documented modulo-`2^64` Montgomery inverse/reduction operations.

## Montgomery multiplication

A separately tested Montgomery path supports **odd moduli below `2^63`**, including composite moduli. Even moduli use ordinary wide multiplication/reduction. The norm root check needs only two modular multiplications per D, so conversion/setup costs can outweigh savings. The benchmark compares both paths; ordinary reduction remains the default rather than assuming Montgomery is automatically faster. The small-prime sieve uses precomputed residue masks, not Montgomery multiplication.

## Evidence and limits

Run `cargo test --manifest-path native/Cargo.toml --locked`, then `python -m unittest discover -s tests -p test_native_kernel.py` and the WASM gate above. Tests include all 243 frozen boundary tasks, 648 seeded random tasks, invalid descriptor rejection, 20,000 Montgomery comparisons, known positive curves, a k=3 identity whose cubes exceed 128 bits, and a complete spawned-runner checkpoint/bank round trip. Fixtures create no public submissions or leaderboard credit.

A language speedup is not a discovery-probability multiplier. The reviewer is right about selective coverage and unvalidated discovery prediction. Their claimed 100–1,000× deficit and “minutes” equivalence require a matched workload: our logical quotient positions include positions rejected without enumeration, and do not measure zcubes sieve instructions. Likewise, a bounded negative receipt proves a negative statement about its exact task, not a new global height bound.

Reference sources: [Booker–Sutherland implementation](https://github.com/AndrewVSutherland/SumsOfThreeCubes), [64-bit Montgomery arithmetic](https://github.com/AndrewVSutherland/SumsOfThreeCubes/blob/main/m64.h), and [their paper](https://arxiv.org/abs/2007.01209). The published project describes Charity Engine's volunteer PCs; this review did not establish the reviewer's claim of a later GPU implementation.
