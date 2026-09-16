# Generator wheel: skipping provably rejected offsets before evaluating them

Status: actionable plan, 17 September 2026. Not implemented; nothing here changes
receipts, counters or coverage semantics. Every step has a measurement gate.

## What is wasted today

Per coefficient row `(b, c)` the kernel evaluates `N(a)` for every offset
`t` in the shell interval, computes `D = N/ℓ`, then rejects:

| Rejection | Live share of admitted generators | Why it is predictable |
|---|---:|---|
| `invalid_d` (`D ≡ 0 mod 3`) | 10.3% | `N ≡ a (mod 3)` and `ℓ` is invertible mod 3, so exactly one residue of `t (mod 3)` per row gives `3 | D`. |
| `signed_excluded` (`S mod 8`, `S mod 361`) | 8.1% | `S = ±D`; `D mod 8` has period 8 in `t`, the sign depends on `t mod 3`; the 361 rule needs `19 | a`, whose consequence depends only on the row and `t mod 57`. Combined period **456** (lcm of 24 and 57). |
| `noninvertible` (`gcd(C, D) > 1`) | 0.8% | Not predictable cheaply; leave. |

So 18% of generator positions are rejected by rules that depend only on
`t mod 456` and the row, yet each costs a 128-bit cubic evaluation, a division
by `ℓ`, and the residue tests. The rejections are *logical* counters: a wheel
must still count them exactly, it just must not compute them.

## Why the gain is bounded

Band‑0 tasks (where all the expected mass is) cost ≈0.4 ms per 128‑row task in
Rust; roughly 60% of that is quotient sieving per admitted curve, not generator
evaluation. A wheel therefore saves at most ~7% of band‑0 CPU even if it made
generator work free. It matters more for empty and near‑empty rows, which the
exact preflight already skips. This is a small, safe optimisation, not a lever
comparable to task size or allocation. Do it only after those ship, and only
if step 1 measures ≥ 5% of kernel time in generator evaluation.

## Plan

1. **Measure first.** Add a `--profile` flag to the Rust CLI that reports, per
   task, cycles in `shell` + generator evaluation versus `scan`. Run the 243‑task
   frozen corpus and the 162‑task random corpus. Gate: proceed only if
   generator evaluation ≥ 5% of total kernel time on band‑0 tasks.
2. **Exact row mask.** For each row compute `a₀ = base + ℓ·t_first` and derive
   the three rejected residues arithmetically:
   - `t ≡ r₃ (mod 3)` where `(a₀ + ℓ·r₃) ≡ 0 (mod 3)`;
   - the eight `t mod 24` classes whose `D mod 8` (with sign from `t mod 3`)
     falls in `{0,4,6}`;
   - if `19 | (a₀ + ℓ·t)` for some class of `t mod 19`, whether `S mod 361` is
     forbidden for that row (depends on `6·ℓ⁻¹·b³ mod 19` and the sign).
   Build a 456‑bit mask once per row, intersect it with `[first, last]`, and
   iterate only allowed offsets. Counters: `invalid_d += |rejected‑by‑3 offsets|`
   and `signed_excluded += |rejected‑by‑sign offsets|`, computed by counting
   mask bits over the interval, with the same precedence as today (`invalid_d`
   is tested before the signed rules, so an offset in both counts as `invalid_d`).
3. **Finite differences (optional).** Replace the per‑offset cubic with the
   exact third‑order recurrence `D(t+1) − D(t) = 3a² + 3ℓa + ℓ² − 342bc/ℓ`… in
   the `ℓ`‑scaled form; jumps over masked offsets need the closed‑form
   re‑evaluation. Only if step 1 shows the cubic itself is the cost.
4. **Differential gate.** Digests, counters and hits must equal the Python
   reference on: the 243 frozen tasks, 648 seeded random tasks, all engine‑v2
   samples, and every cross‑target sample (targets drop the signed rules, so the
   wheel must reduce to the mod‑3 skip alone when `k ≠ 114`). Add a Rust unit
   test that enumerates every `(a₀ mod 456·ℓ, ℓ, b mod 19)` class and checks
   the mask against brute force.
5. **Benchmark gate.** Paired 32‑seed replay on the actual live context mix,
   kernel‑only. Ship only if median improvement ≥ 3% with the bootstrap interval
   excluding 0; otherwise record the null result here.

Estimated effort: one day. Expected outcome under the model: 3–7% kernel CPU,
no change to discovery odds beyond that.
