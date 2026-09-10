# Exact exclusions and limited recovery after a denominator failure

This is a proposal for a subsequent campaign version. **The running production sources and binaries were not changed.** Its strongest immediate result is a set of cheap, proved restrictions that discard entire curve families. A limited 5-adic fallback also recovers valid modular roots; neither result establishes a solution-discovery advantage over the published algorithms.

For `k=114`, write

```
N = a³ + 114b³ + 12996c³ − 342abc
A = a² − 114bc
B = 114c² − ab
C = b² − ac
D = |N|/ell, where ell is 1,5,25.
```

The current root formula requires `C` invertible modulo `D`. The following identities hold over the integers:

```
B² − AC = cN
A² − 114BC = aN
114C² − AB = bN.
```

Consequently, changing the denominator to `A` or `B` cannot rescue a failure. Modulo `D`, an invertible `B` forces `A,C` invertible because `B²=AC`; an invertible `A` forces `114,B,C` invertible because `A²=114BC`. Equivalently, every prime dividing both `C,D` also divides `A,B`. There is no exception at primes dividing 114. A quadratic-polynomial or subresultant approach encounters this same rank drop and may require factoring part of `D` or branching over roots.

There is a useful distinction between an incompatible representation and an impossible curve. If a root `r mod D` also satisfies `a+br+cr²=0 mod D`, the ideal `(gamma)` lies in `(D,alpha−r)`. For `ell=1` their norms agree, so the quotient by `(gamma)` must be cyclic. At a bad denominator prime, all adjugate entries vanish modulo that prime, and the multiplication matrix has rank at most one. Its quotient therefore needs at least two generators locally, contradicting cyclicity. For `ell=5,25` the same argument works at every prime other than 5. Thus a bad denominator prime outside the class multiplier rules out a root compatible with that particular generator. **It does not prove that `r³=114 mod D` has no roots at all.** Roots unrelated to the generator can still define valid search curves.

## Proved curve exclusions

If `4` or `361=19²` divides `D`, no root of `r³=114 mod D` exists. Since `114` has valuation one at both 2 and 19, a root divisible by either prime would have a cube divisible by its cube; it cannot equal 114 modulo its square. A simple bit test for `D mod4=0` can therefore avoid many Euclidean inversions.

Stronger restrictions use the **signed** sum `S=x+y`, not merely `D=|S|`. For 114 all coordinates are `2 mod3`, so `S≡1 mod3`. Hence `S=+D` when `D≡1 mod3`, and `S=−D` when `D≡2 mod3`.

- If `S` is even, `x,y` must both be odd and `z` even; otherwise all three cubes would be divisible by 8. Odd cubes equal their bases modulo 8, so **even `S` must be `2 mod8`**. Combining the forced sign with `D mod3` leaves precisely `D mod24 ∈ {1,5,7,10,11,13,14,17,19,23}`.
- If `S=19t` with `t` nonzero modulo 19, reducing the equation modulo 361 gives `t x²≡2 mod19`. Thus `2/t` must be a nonzero quadratic residue. Since 2 is a nonresidue modulo 19, `t` must be a nonresidue. `S≡0 mod361` is impossible.

An executable modular-filter miner independently enumerated complete residue tables. It found:

| Modulus | Forbidden signed `S` residues |
|---|---|
| 4 | 0 |
| 8 | 0,4,6 |
| 16 | 0,4,6,8,12,14; no extra restriction beyond modulus 8 |
| 19 | None |
| 361 | 0,19,76,95,114,133,171,209,304,323 |
| 27,81 | Exactly those failing `S≡1 mod3` |

The miner checks every `x` residue against the complete cube-residue set for `z`, for every signed sum. Polynomial periodicity then proves that each forbidden residue excludes an infinite integer family. It also checks its results with a separate three-variable oracle for the small moduli. Its certificates contain full allowed masks, witnesses, hashes, and a sign-correct absolute-`D` conversion. This is automated derivation of necessary conditions, not machine learning from unsuccessful searches, and the underlying congruences are not claimed novel.

## A narrow 5-adic fallback

If the only prime shared by `C,D` is 5, write `D=d0*5^e`, stripping the **entire** 5-part so `gcd(d0,5)=1`. Then:

1. Recover `r0=B/C mod d0`; the denominator is now invertible. When `d0=1`, use its single residue class.
2. Compute the unique cube root `r5` of 114 modulo `5^e`. The unit-group order is `phi=4*5^(e−1)`, coprime to 3, so `r5=114^(3^−1 mod phi) mod5^e`. A table for the at most 27 supported powers can be precomputed, or Hensel lifting used.
3. Combine the roots by CRT:

```
r = r0 + d0 * ((r5−r0) * inverse(d0,5^e) mod5^e), reduced modulo D.
```

4. Verify `r³≡114 modD` with exact modular arithmetic, then apply the signed-sum filters and existing quotient/exact-square checker.

This recovers a valid modular root, even when it is unrelated to the original generator. A future ledger must record the CRT derivation explicitly; it cannot claim that the original inverse formula succeeded. Any other unresolved denominator factor must remain explicitly unsupported by this narrow fallback.

More generally, one can strip the full prime-power part of `D` supported on `gcd(C,D)`, recover the good-part root, factor the bad part, solve each local cubic, and combine by CRT. For unramified primes congruent to 2 modulo 3 there is a unique root; primes congruent to 1 modulo 3 give zero or three roots. This can become more expensive than the skipped work, and branch caps must be reported as incomplete handling rather than mathematical exclusions. The narrow 5-only repair is a much smaller engineering commitment.

## Small arithmetic audit

`experiments/root_recovery_probe.py` reconstructs 5,000 deterministic generator indices in each of six box/plane and multiplier contexts. It applies current sign symmetry and ratio-64 frontier bounds, but performs **no curve search**. This short audit had:

| Classification | Count |
|---|---:|
| Generator indices | 30,000 |
| Kept after sign symmetry | 15,000 |
| Supported divisors with a possible frontier interval | 4,964 |
| Ordinary invertible-denominator candidates | 3,529 |
| Noninvertible-denominator cases | 1,435 |
| Of failures: impossible at checked small primes | 1,215 |
| Of failures: verified 5-only recovery | 154 |
| Of failures: other small factors with local roots | 63 |
| Of failures: unclassified larger factor | 3 |

Thus 84.7% of these denominator failures were provably impossible, overwhelmingly because `4|D`. The 154 repaired 5-adic roots were all independently verified. Only 57 also satisfied the original generator polynomial modulo `D`, all in multiplier-25 contexts; the other roots still define valid modular curves.

Among the 3,529 ordinary root candidates, the signed modulus-8 filter removed 571 and the modulus-361 filter removed 88; their union removed **639, or 18.1%**. These are complete curve-family exclusions, before quotient enumeration. Of the 154 repaired roots, 37 failed the same signed filters, leaving **117 additional admissible-root candidates**. Compared with the 2,890 ordinary candidates surviving these filters, that is a 4.0% increase in candidate count in this sample, not a measured speedup or a prediction of finding a solution.

The sample is small, deterministic, and potentially overlapping in its generated curves. These counts do not establish unique unexplored coverage. More root recovery also creates more work. The first implementation priority should be the proved signed-sum filters, followed by a separately timed, correctness-tested 5-adic repair. Integration requires a new version and new validation; the current campaign remains unchanged.

Reproduce the evidence:

```sh
python3 experiments/modular_filter_miner.py
python3 experiments/root_recovery_probe.py
```

Full results are `experiments/modular-filter-certificates.json` and `experiments/root-recovery-sample.json`.
