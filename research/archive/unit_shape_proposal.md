# Certified generator bounds and missing unit shapes

9 September 2026 local time. Mathematical derivations for a future worker; no running code was modified. The field facts used here are the package's certified PARI computation: `O_K=Z[alpha]`, `alpha³=114`, class group cyclic of order three, and generator `J=(5,alpha−4)`. The discussion distinguishes exact bounds, continuous geometry, and unproved distribution assumptions.

## A finite bound really exists

For `gamma=a+b alpha+c alpha²`, write `n=|N(gamma)|>0`. The field has one real embedding and one conjugate pair. Set

```
r = |sigma_real(gamma)|,
w = |sigma_complex(gamma)|,
t = log(r/n^(1/3)).
```

Then `n=r w²`, so

```
r=n^(1/3)e^t,
w=n^(1/3)e^(−t/2).
```

The factor one-half in the complex exponent matters. Multiplication by a positive real unit of size beta shifts t by `log beta` and changes the complex magnitude by `beta^(−1/2)`.

The package's fundamental unit and its exact inverse are

```
epsilon = 61561−13758 alpha+219 alpha²,
N(epsilon)=1,
beta = epsilon^(-1)
     = 4133238949+852423792 alpha+175800705 alpha².
```

The positive real value beta is approximately `12399716846.9999851`, giving regulator `R≈23.2409394743773`. Since `alpha<5`, its real value is strictly less than the integer `12790375534`. The identity and this simple upper bound need no floating-point conjecture. Even a nonfundamental unit would suffice for the existence bound below; fundamentality is relevant to uniqueness and the phase discussion.

Choose a unit multiple with `t∈[-2R/3,R/3)`. Both embedding magnitudes are then at most `beta^(1/3)n^(1/3)`. Inverting the three-embedding Fourier transform gives

```
|a|       ≤ (r+2w)/3,
alpha|b|  ≤ (r+2w)/3,
alpha²|c| ≤ (r+2w)/3.
```

Since beta is less than `2400³`, this immediately proves the coefficient bound with constant 2400.

A sharper interval minimizes the maximum of `g(t)=(e^t+2e^(−t/2))/3`. Let `V=sqrt(beta)` and

```
t0=(2/3)log(2/[V(V+1)]).
```

Its endpoints satisfy `g(t0)=g(t0+R)`. Convexity bounds g throughout this interval by that endpoint value, approximately `1224.72138`. A rigorous rounded constant is **1250**. To verify the rounding without trusting decimals, put `W=113095·113096=12790592120`; the beta bound implies `V(V+1)<W`, and

```
C³ = 4(W_actual+1)³/[27 W_actual²],
4(W+1)³ < 27·1250³·W².
```

The expression is increasing for `W_actual≥2`, so the strict bound follows.

Therefore every principal ideal of norm n has a generator satisfying

```
|a| ≤ 1250 n^(1/3),
|b| ≤ 1250 n^(1/3)/alpha,
|c| ≤ 1250 n^(1/3)/alpha².
```

For an arbitrary root ideal `I=(D,alpha−r0)` of norm D, one of `I J^j`, `j=0,1,2`, is principal. Its norm is `n=5^j D`, and multiplying its generator by units preserves membership in `J^j`. Thus these bounds give an explicit finite class-cleared search region for every D bounded above. They do not make that region small enough for a Mac-hours exhaustive search.

## Why the finite bound is not yet an efficient algorithm

The simple anisotropic coefficient rectangle at constant1250 has volume, divided by the class-clearing lattice index ell, approximately

```
8·1250³·D/114 ≈ 1.3706×10^8 D
```

per class. At the frontier this is enormous.

The properly reduced region is much thinner. In real/complex coordinates `(r,w,theta)` with positive real embedding, the coordinate change to norm n and shape t satisfies

```
dr · w dw · dtheta = (1/2) dn dt dtheta.
```

Integrating theta gives volume `pi dn dt`. A full unit interval has length R. The embedded lattice `J^j` has covolume `ell sqrt(350892)/2`. Consequently a norm shell of width `ell ΔD` has normalized **continuous volume**

```
2 pi R ΔD / sqrt(350892) ≈ 0.246517 ΔD
```

per class.

This explains why unit reduction combined with exact shell pruning is geometrically attractive: the huge enclosing rectangle contains mostly irrelevant points. The volume is not a finite-height lattice-count guarantee or a runtime bound. Boundary effects, extremely thin sections, integer-point enumeration, and curve checking remain substantial obstacles. It would also enumerate ideals that do not correspond to admissible cubic roots unless their arithmetic conditions are imposed.

## The existing box and plane cover narrow phase support

For a fixed class-cleared ideal, `t mod R` is invariant under changing its generator by a unit. We can bound which phases the present proposal families can possibly reach, without assuming that ideals or solutions are uniformly distributed among them.

At `D≥D0=floor(10^19/54)`, the production box radius H gives

```
r,w ≤ 31H+ell−1,
M=(31H+ell−1)/(ell D0)^(1/3),
−2 log M ≤ t ≤ log M.
```

Here `alpha<5`, and the `ell−1` term accommodates the asymmetric a-residue boundary. The three radii `(50000,85499,146201)` were chosen to scale with `ell^(1/3)`, so their bounds are almost identical.

For the current plane radius20,000,000 and five nearest-lattice offsets, exact rounding implies

```
r ≤ 2.5ell+4×10^-11,
w ≤ 48·20000000+2.5ell+4×10^-11.
```

The tiny correction follows from the two rational approximations to alpha and alpha², each within `10^-18`, multiplied by the bounded b,c coefficients. The complex estimate follows from

`|sigma_complex(gamma at the exact plane)|² = 3(alpha²b²+114bc+alpha⁴c²)`

and `3(25+114+625)<48²`.

These conservative bounds imply:

| ell | Possible box t strip | Possible plane t strip |
|---|---|---|
| 1 | approximately `[-2.001,1.001]` | `[-14.858,-12.337]` |
| 5 | approximately `[-2.001,1.001]` | `[-13.785,-11.264]` |
| 25 | approximately `[-2.001,1.001]` | `[-12.712,-10.191]` |

The intervals are disjoint inside one unit period. Their combined length is at most approximately **23.8% of R** for each class at and above this frontier. This is an **upper bound on possible phase support**, not a statement that23.8% of ideals have been covered. The actual coefficient regions occupy only parts of these strips, and the actual campaign samples only small prefixes. Lower-D tail arms require separate bounds and can have broader phase support.

This identifies a real gap in proposal diversity: large regions of logarithmic unit shape cannot be reached by these two families at frontier D, regardless of how long their fixed domains are sampled. It does not establish that the missing phases contain more solutions.

## Families worth testing next

Use several explicit t strips spanning a whole regulator interval, retain all three ideal classes, and adapt only verified execution costs until discovery enrichment is independently demonstrated. Continuous volume is uniform in t, which supplies a geometric allocation baseline; it does not justify claiming uniform solution-bearing ideals at this height.

Intermediate negative t can be reached by wider cancellation-plane offsets, with exact norm-shell interval inversion keeping D in range. Positive t corresponds to a small complex embedding: it suggests thin neighborhoods of

```
(a,b,c) ≈ (alpha² c, alpha c, c),
```

where both components of the complex embedding nearly cancel. This is a different proposal family from the real cancellation plane. Its offsets and lattice rounding require their own exact domain specification and benchmark.

An eventual complete generator enumerator would traverse a unit fundamental region and bounded norm shell with rigorous interval arithmetic and lattice enumeration. The shell worker is a useful first piece, but filling a few t strips must not be confused with completing that region.

## Completeness lemma for the root filter

The following proof has received independent mathematical review in this campaign; it is not a machine-checked formal proof or a new assumption in the running worker.

Let `D≥1`, let `r0³≡114 (mod D)`, and take the root ideal `I=(D,alpha−r0)` in `O_K=Z[alpha]`. Let `J=(5,alpha−4)` and `j∈{0,1,2}`. If `I J^j=(gamma)` is principal, put `n=5^j D=|Norm(gamma)|`. Then the adjoint coefficient `C=b²−ac` satisfies **`gcd(C,n)=1`**.

First, `I J^j` is itself a root ideal of norm n. At 5 the polynomial factors as

```
X³−114 ≡ (X−4)(X²+4X+1) (mod 5).
```

The quadratic factor is irreducible, and `3·4²` is nonzero modulo 5. Thus 5 is unramified, J is its unique degree-one prime, and the root 4 has a unique lift to every power of 5. Writing `D=5^e m` with `5∤m`, the 5-part of I is `J^e`; multiplying by `J^j` replaces it by `J^(e+j)`. At primes dividing m the ideal is unchanged. The Chinese remainder theorem combines the lifted root modulo `5^(e+j)` with `r0 mod m` to give a root `r' mod n` and

```
I J^j = (n,alpha−r'),
O_K/(gamma) ≅ Z/nZ.
```

This cyclic quotient controls the adjoint. Define

```
A=a²−114bc,  B=114c²−ab,  C=b²−ac,
N=Norm(gamma),
B³−114C³ = N(114c³−b³),
A²−114BC = N a.
```

Suppose a prime p divides both C and n. These identities force `B≡0` and then `A≡0 (mod p)`. The adjugate of the multiplication-by-gamma matrix is the multiplication matrix for `A+B alpha+C alpha²`; it would therefore be zero modulo p. All its 2-by-2 minors would vanish, so the multiplication matrix would have rank at most one over `F_p`. Its cokernel would have dimension at least two. But the displayed cyclic quotient gives cokernel `(Z/nZ)⊗F_p ≅ F_p`, of dimension one. This contradiction proves the claim, including at the ramified primes 2 and 19 without separate local arguments.

The hypothesis is equality **`(gamma)=I J^j`**, not merely containment in I and membership in `J^j`. For example,

```
gamma=5(alpha−4)=−20+5alpha,
Norm(gamma)=6250, ell=25, D=250, C=25.
```

Here `r0=104` satisfies `r0³≡114 (mod 250)`, and `gamma(r0)=500≡0 (mod 250)`. Also gamma belongs to `J²=(25,alpha−4)`. Nevertheless `(gamma)≠I(250,104) J²`: at 5, gamma has ideal factor `J³ Q`, where Q is the degree-two prime of norm 25, whereas `I J²` has factor `J⁵`. The residual ideal of norm 25 is Q rather than the selected class-clearing factor `J²`. Accordingly C is noninvertible here, without contradicting the lemma.

The lemma closes the root-filter gap for the certified ideal-to-generator construction and makes the finite unit-reduced coefficient bound above a complete theoretical generator bound. Arbitrarily sampled elements still require the actual root checks. Finite coefficient coverage, exact unit reduction and integer-point enumeration must all be established separately before claiming a complete frontier search.
