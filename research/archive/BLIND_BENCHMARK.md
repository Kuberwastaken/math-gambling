# Blind discovery benchmark

This experiment found **no held-out evidence that a learned candidate preference improves discovery**. It is a useful negative result: the campaign must not pretend that unsuccessful checks on 114 train a reliable solution predictor.

The benchmark used 37 positive, cube-free integers at most 200 with `k mod 9` equal to 3 or 6, excluding 114. A fixed SHA256 rule assigned entire values of `k` to 26 training and 11 test cases before search. It did not select cases by their known coordinates, pair sums, roots, or discovery difficulty. The reference file was opened only after all searches finished. This is a coordinate-blind search experiment; some of these equations and their solutions were already familiar to the project, so it is not an investigator-blinded external trial.

Each policy received 30,000 generator attempts per `k`, ratio bound 128, and norm multiplier 1. A successful target was fixed in advance as an exact solution with maximum absolute coordinate at least 1,000. Smaller hits were retained in the log, but did not train the policy selector. All printed hits were independently verified with Python integer arithmetic.

Writing `α = k^(1/3)` and `A = 32`, the three policies were:

- **Uniform:** sample each of `a,b,c` uniformly from the integers in `[-A,A]`.
- **Balanced:** use coefficient bounds `ceil(A α²), ceil(A α), A` for `a,b,c`, respectively. The three terms of `a+bα+cα²` then have comparable scales.
- **Thin real:** sample `b,c` in `[-A,A]`, then set `a = -round(αb+α²c)+j`, with integer `j` uniform in `[-8,8]`. This makes one real embedding relatively small and changes the norm distribution.

For each generated triple the program formed its norm, derived valid modular roots, deduplicated `(d,root)` within that case, and searched the associated curves. It supplied no known curve or root to the generator.

| Policy | Train target hits | Train time | Test target hits | Test time | Total unique curve checks within cases |
|---|---:|---:|---:|---:|---:|
| Uniform | 0 | 9.88 s | 0 | 4.17 s | 460,663 |
| Balanced | 0 | 10.58 s | 0 | 4.52 s | 503,353 |
| Thin real | 1 | 7.80 s | 0 | 3.32 s | 342,064 |

Total: **3,330,000 generator attempts, 1,306,080 curve checks, 40.33 seconds elapsed**, one GP worker, zero execution failures. These are case-local distinct curves; the same curve can occur under different policies. There were 14 exact hits across policy/case runs, mostly below the target-height threshold.

The one qualifying training discovery was

```
(-60355)^3 + 10529^3 + 60248^3 = 6.
```

It was found by the thin-real policy from a generated candidate with `d=107` and root `43`; these values were outputs. The predeclared training rule selected thin real because it had the most target hits per elapsed second. That selected policy then found **zero targets on the untouched whole-k test set**. The two alternatives also found zero test targets.

The test set was `12,33,42,51,57,60,75,84,147,150,174`. Training used the remaining eligible values. The data supports neither a test-set ranking nor a numerical probability of solving 114. The faster thin-real runtime partly reflects generating fewer distinct curves, so it is not itself an algorithmic speedup.

For campaign scheduling, retain explicit exploration of the candidate policies. Adapt measured execution costs, deduplication, and filter ordering where correctness permits. Do not adapt a claimed solution probability from these results, and do not eliminate mathematical families because a policy produced no hits. A stronger prediction experiment needs substantially more successful blind discoveries, several independent seeds, and validation across both held-out `k` and larger search scales.

This experiment samples principal norms only, has a finite ratio bound, and does not claim complete coverage. Its coefficient policies induce different distributions of `d`, recorded as histograms in the JSON; their comparison measures the complete policy rather than isolating a causal effect of coefficient shape. None of its small-`k` timing or yield estimates has been established at the frontier for 114.

Run from the package directory:

```sh
python3 blind_benchmark.py --count 30000
```

The default reference location is the project's `work/literature/huisman.txt`; when moving the package, pass `--reference /absolute/path/huisman.txt`. Machine-readable evidence is in `runs/blind-benchmark.json`, including seeds, hashes, per-case timing, all hits, failures, and the split. The reference source is [Huisman's published solution list](https://math.mit.edu/~drew/huisman.txt); the algebraic search follows the norm approach of [Grantham–Walsh](https://arxiv.org/abs/2211.12149).
