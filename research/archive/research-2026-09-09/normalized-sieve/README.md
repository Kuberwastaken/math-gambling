# Normalized square-sieve experiment

This is an isolated research prototype, **not the running campaign**. It strengthens the necessary square condition at primes dividing D. It passed the saved arithmetic and known-positive checks but did not improve end-to-end CPU time in the exploratory comparison, so it was not promoted.

From this directory, `python3 build_prototype.py` builds only the local prototype using the frozen phase3 source and existing PARI dependency. `python3 validate_prototype.py` checks arithmetic against Python arbitrary-precision calculations and recovers 662 known positive fixtures. `python3 benchmark_prototype.py` reads a fresh sample of completed production jobs and runs paired, sequential calibration jobs; those repeats are never counted as new coverage. Run timing experiments without competing research benchmarks. They consume extra CPU while production may remain active.

The original experiment used the equivalent files under the workspace's `work/research2026-normalized` directory. The scripts here have only their paths adapted for this deliverable location. The C sources are byte-identical to the tested prototype. Saved evidence is in [validation](../normalized-sieve-validation.json) and [timing](../normalized-sieve-benchmark.json).

For `S=sign*D`, `z=r+D*q`, and `h=(k-r^3)/D`, a solution requires

\[
(x-y)^2\equiv(4\,\mathrm{sign}/3)h-4\,\mathrm{sign}\,r^2q\pmod p
\]

whenever the odd prime p divides D and p is not 3. The right side must be a quadratic residue, including zero. This follows by dividing the exact square equation before reducing modulo p; the older discriminant predicate becomes identically zero at these primes.

Computing h needs no large cubic. Divide `r*r=D*u+v`, then `v*r=D*w+t`. The identity `h=(k-t)/D-u*r-w` is exact for a modular root. Every product fits 128 bits for `0<=r<D<=INT64_MAX`; the square quotient also fits signed 128 bits. The implementation caches h only when a dividing prime is first needed. Existing prime counters now describe a stronger predicate, so exact-test counts are expected to differ from phase3.

The validation proves neither universal implementation correctness nor completeness of the campaign geometry. The benchmark is a small, contention-affected measurement, not evidence of a universal slowdown. Its practical conclusion is narrower: **a speed gain was not established**.
