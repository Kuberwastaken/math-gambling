# Isolated positive unit-phase experiment

`tools/unit_phase_experiment.py` implements the archived positive-embedding tube
as a bounded, separate experiment. It enumerates exact coefficient cells,
checks them against a complete positive box, extracts and verifies modular roots,
and runs the existing exact quotient checker. It never creates production tasks,
banks receipts, changes the production engine, updates the scheduler or earns
contributor credit.

The experiment establishes functionality and precise domain geometry. It does
not establish that this family finds solutions more often, or that a complete
frontier enumeration is practical.

## Exact cell and bounds

Let `alpha^3=114`, `gamma=a+b*alpha+c*alpha^2`, `n=Norm(gamma)`, and let `s` be
the real embedding of gamma and `w` the magnitude of its complex embedding.
The cell has positive integer coefficients and requires

```
ell in {1,5,25}
a+4b+16c = 0 (mod ell)
ell*dlo < n <= ell*dhi
lambda_lo < s^3/n <= lambda_hi, with lambda_lo > 4
```

The identity `n=s*w^2` gives `s^3/n=s^2/w^2`. Thus the phase condition implies
`s>2w`. Fourier inversion then bounds each of `a`, `alpha*b`, `alpha^2*c`
between `(s-2w)/3` and `(s+2w)/3`; all coefficients are strictly positive.
This justifies the positive box, not an assumption about typical generators.

Integer cube roots bound `s` outward. With a positive integer lower bound
`smin`, `w^2 <= ell*dhi/smin` gives an outward rational radius. The exact identity

```
w^2 = (a-(alpha*b+alpha^2*c)/2)^2
      + 3*(alpha*b-alpha^2*c)^2/4
```

restricts rows and the remaining `a` interval. Every square-root rounding is
outward; an interval containing zero uses zero as its distance bound. The
class-lattice congruence advances `a` by `ell`. Norm and phase membership are
still checked individually; the prototype does not claim optimized cubic-shell
inversion or full-scale lattice enumeration.

Phase comparisons reduce `s^3-boundary*n` to a polynomial of degree at most two
in alpha. Rational isolating intervals determine its sign. An ambiguous sign
refines the interval instead of rejecting a point. A zero coefficient vector
handles exact equality, so lower-exclusive/upper-inclusive endpoints are
preserved. Since `X^3-114` is irreducible over the rationals, a nonzero polynomial
of degree at most two cannot vanish at alpha. A refinement cap raises an error;
it never converts uncertainty into an exclusion.

## Root extraction and scans

For each exact cell member, the experiment computes `D=n/ell`,
`B=114*c^2-a*b`, `C=b^2-a*c`. If `gcd(C,D)=1`, it forms `r=B/C mod D` and
independently verifies both `r^3=114 mod D` and `a+b*r+c*r^2=0 mod D`.
Noninvertible inputs are counted as unresolved. They are not declared impossible
roots. Divisors divisible by three are excluded by the coordinate congruence
necessary for 114.

Completed scans use `0<abs(z)/D<=64`, `z=r+D*q`, the forced sign of `x+y`, and
the existing minimum-absolute-coordinate checker. The tiny analogue deliberately
has no `10^17` lower-coordinate floor. Duplicate `(D,r)` pairs are skipped
explicitly within the experiment, and every completed scan records its actual
signed inclusive endpoints. Every encountered exact identity is independently
verified, atomically written and synced before scheduling stops. Such a file
claims neither task completion nor public credit.

## What makes the proposed frontier family distinct

The intended frontier cell is

```
D0 < D <= 8*D0, D0=floor(10^19/54)
28 < s^3/n <= 10^9
```

The experiment does **not** enumerate that enormous cell. It recomputes exact
inequalities showing that its real embedding is strictly above every current
offset shape of the same class, while its ratio to every current embedding is
less than `beta`. It also verifies that the proposed cell spans less than one
unit period. This uses rational arithmetic and cubes, not floating logarithms.

The archived unit is
`beta=4133238949+852423792*alpha+175800705*alpha^2`. Its norm and its product
with the stated inverse are checked again. These identities alone do not prove
that beta is fundamental. The root-ideal separation conclusion remains
conditional on the archived maximal-order, fundamental-unit and class-ownership
facts. The retained [field/domain certificate](../research/archive/phase2/runs/final-domain-certificate.json)
is hashed in the output; this command does not rerun PARI. In particular, a
unit identity must not be advertised as an independent class-group certification.
The small-cell validation does not inherit the frontier separation claim at
its smaller D values.

## Reproduce the bounded validation

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/unit_phase_experiment.py \
  --output /tmp/mg-unit-phase-new-run --seconds 10
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s tests -p test_unit_phase_experiment.py -v
```

The output directory must be new. `manifest.json` records the fixed cells,
source/kernel hashes and limits before enumeration. `results.json` records
completed cells, membership hashes, exact modular roots, scan counters,
elapsed/CPU timings and the separation inequalities. Work limits are 150,000
coefficient checks including the box oracle, 20,000 row/c-loop iterations,
512 curves and 32,768 logical quotient positions. The default wall budget is
10 seconds and cannot exceed 30. Wall checks are cooperative; one bounded
operation or final synced write can extend the nominal deadline. A stopped
run is marked partial and exits 2. An arithmetic failure is marked failed
when reached during enumeration and propagates; it cannot produce a complete
certificate. No incomplete cell receives box-equality or scan-completion credit.

The [retained 12 September run](../research/experiments/unit-phase/2026-09-12/results.json)
completed all six default cells:

| Quantity | Result |
|---|---:|
| Complete box/oracle agreements | 6 |
| Exact cell generators | 129 |
| Excluded divisors divisible by three | 37 |
| Unresolved noninvertible inputs | 29 |
| Verified distinct roots and completed scans | 63 |
| Logical quotient positions | 4,032 |
| Final exact-square tests / hits | 0 / 0 |

The tube tested 680 coefficient positions. Including the deliberately exhaustive
box oracle, the experiment tested 76,655 positions. These counts describe the
small fixed corpus, not a speedup prediction. The tests additionally reproduce
all 166 members of the archived twelve-cell corpus, independently check the
norm against a multiplication-matrix determinant, compare root extraction with
brute modular roots, compare sieved and unsieved scans, test budget stops, and
exercise durable positive recovery with a known `k=3` regression. That positive
fixture validates the callback path, not the existence of a 114 representation.

## Promotion requirements

The production family remains unchanged. A later frontier implementation needs
independent field/ownership review, certified numeric bounds for its exact
coefficient range, and an overflow certificate if ported to fixed-width native
arithmetic. It also needs scalable indexed enumeration rather than an enormous
scan from the first positive row, explicit completed-domain accounting, and
equal-budget comparison with the current native engine including setup and
storage costs. Root/candidate volume is not a discovery label; any enrichment
claim requires protected target/scale holdouts. The archived
[geometry proposal](../research/archive/research-2026-09-09/GEOMETRY_REVIEW.md)
motivates the family; this implementation does not claim an unprecedented
number-theoretic method.

## Assessment of further diversification proposals

**High-q windows:** useful as an explicitly bounded diversity arm, but not
automatically better geometry. Under the current continuous preference,
the remaining mass above ratio `T` is asymptotic to `1/sqrt(T)`; a fixed-width
window has mass approximately `width/(2*T^(3/2))`. These are prior-weight
asymptotics, not discovery probabilities. Use disjoint signed windows with
separate coverage records. A high starting quotient requires a fresh numeric
audit even when its window is short: the native kernel currently casts q to
`i64` and evaluates `rp+dp*q` in `i64` before taking its residue
(`native/src/lib.rs`, `scan`). Its safety comment explicitly assumes
`abs(q)<=4097`. Arbitrary-precision final cube checks do not protect those earlier
operations. No high-q production change is included here.

**Low-D fibers:** rechecking a familiar D is useful when z extends beyond its
previously completed intervals, or when a complete integral-point calculation
can certify that fiber. A published global search rectangle does not supply
this repository with a per-root completed manifest. Reconcile actual interval
evidence before calling a low-D window new; otherwise label it a verification
or overlap-unknown experiment. With existing roots, a carefully chosen high-z
window amortizes root setup, but still faces the geometric tail above.

**Finite CRT packets:** specify a finite set of fully factored divisors,
enumerate every cubic root modulo each prime power, and combine every compatible
choice by CRT. Handle ramified prime powers explicitly and report any branch
cap as incomplete. This yields a clear finite divisor/root certificate and an
algorithmic control for the norm sampler. A different generator or algorithm
does not make roots disjoint or statistical samples independent: compare the
actual `(D,r,s,qlo,qhi)` intervals. Likewise, phase-family separation by itself
is not a root-disjointness certificate; the conditional ideal ownership and
fundamental-unit argument, and correct implementation, are additional requirements.

**Complete elliptic fibers:** an empty bounded point search is not an all-height
exclusion. A complete integral-point workflow needs a certified Mordell–Weil
basis (including saturation and torsion handling), rigorous height bounds and
complete enumeration, plus exact checks of the transformation back to integral
x,y,z. A list of independent points of the apparent rank is insufficient.
[Sage's integral-point documentation](https://doc.sagemath.org/html/en/reference/arithmetic_curves/sage/schemes/elliptic_curves/ell_rational_field.html)
warns that a supplied subgroup basis can miss points and that proof-disabled
search loses completeness guarantees.
[PARI's `hyperellratpoints` documentation](https://pari.math.u-bordeaux.fr/dochtml/ref-stable/Elliptic_curves.html#hyperellratpoints)
defines a height-bounded search. A timed-out rank or basis computation must
remain unresolved. Start with a few independently certified fibers as an
isolated research arm, not a wholesale replacement for the quotient kernel.
