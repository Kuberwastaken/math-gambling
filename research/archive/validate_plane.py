#!/usr/bin/env python3
"""Independent exact-integer audit of the finite cancellation-plane generator."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parent
DEN = 10**18
P = 4848807585839879338
Q = 23510935004498358840
MASK = 2**64 - 1


def mix(v):
    v = ((v ^ (v >> 30)) * 0xbf58476d1ce4e5b9) & MASK
    v = ((v ^ (v >> 27)) * 0x94d049bb133111eb) & MASK
    return v ^ (v >> 31)


def permutation(seed, ell, radius, total):
    v = mix(seed ^ mix(ell) ^ mix(radius))
    stride = mix((v + 0x9e3779b97f4a7c15) & MASK) % total or 1
    while math.gcd(stride, total) != 1:
        stride += 1
        if stride == total:
            stride = 1
    return stride, v % total


def run(binary, *args):
    r = subprocess.run([str(binary), *map(str, args)], text=True, capture_output=True, timeout=60)
    assert r.returncode == 0 and not r.stderr.strip(), (args, r.stderr, r.stdout)
    return [json.loads(line) for line in r.stdout.splitlines()]


def validate_dump(binary, ell, radius, start, count, seed):
    rows = run(binary, "dump", ell, radius, start, count, seed)
    stats = rows[-1]
    total = 5 * (2 * radius + 1)**2
    stride, offset = permutation(seed, ell, radius, total)
    assert stats["kind"] == "plane" and stats["mode"] == "dump"
    assert (stats["count"], stats["total"], stats["permutation_stride"], stats["permutation_offset"]) == (count, total, stride, offset)
    triples, indices, roots = set(), set(), 0
    all_roots, kept_roots = set(), set()
    for index, row in zip(range(start, start + count), rows[:-1], strict=True):
        assert row["index"] == index
        v = (index * stride + offset) % total
        assert row["permuted_index"] == v
        indices.add(v)
        t = v % 5 - 2
        b = (v // 5) % (2 * radius + 1) - radius
        c = (v // 5) // (2 * radius + 1) - radius
        residue = (-4*b - 16*c) % ell
        numerator = -P*b - Q*c - residue*DEN
        denominator = ell * DEN
        nearest = (2*numerator + denominator) // (2*denominator)
        a = residue + ell*(nearest + t)
        assert list(map(int, row["abc"])) == [a, b, c]
        # These inequalities certify the chosen lattice rounding, including ties.
        assert (2*nearest-1)*denominator <= 2*numerator < (2*nearest+1)*denominator
        assert -2 <= t <= 2 and abs(b) <= radius and abs(c) <= radius
        assert (a + 4*b + 16*c) % ell == 0
        opposite_residue=(4*b+16*c)%ell
        opposite_n=P*b+Q*c-opposite_residue*DEN
        opposite_h=(2*opposite_n+ell*DEN)//(2*ell*DEN)
        opposite_base=opposite_residue+ell*opposite_h
        delta=-a-opposite_base
        duplicate=(c,b,a)<(0,0,0) and delta%ell==0 and -2<=delta//ell<=2
        assert row["symmetry_duplicate"] == duplicate
        norm = a**3 + 114*b**3 + 12996*c**3 - 342*a*b*c
        assert int(row["norm"]) == norm and norm % ell == 0
        triples.add((a, b, c))
        d = abs(norm) // ell
        supported = norm != 0 and 2 <= d <= 2**63-1 and d % 3 != 0
        C, B = b*b-a*c, 114*c*c-a*b
        usable = supported and math.gcd(C, d) == 1
        assert row["root_usable"] == usable
        assert row["D"] == (str(d) if supported else None)
        if usable:
            r = B * pow(C, -1, d) % d
            assert int(row["r"]) == r and pow(r, 3, d) == 114 % d
            roots += 1
            all_roots.add((d,r))
            if not duplicate: kept_roots.add((d,r))
        else:
            assert row["r"] is None
    assert len(triples) == len(indices) == count
    if count==total:
        assert all_roots==kept_roots
    return dict(ell=ell, radius=radius, start=start, count=count, roots=roots,
                unsupported_D=stats["unsupported_D"], total=total,
                full_domain_root_set_preserved=count==total)


def check_partition(stats):
    assert stats["candidates"] == sum(stats[key] for key in (
        "zero_norm", "invalid_d", "unsupported_D", "noninvertible_C", "symmetry_rejected", "covered", "curves"))
    assert stats["quotient_points"] == stats["rejected_mod243"] + stats["rejected_parity"] + stats["exact_tests"] + sum(f["rejected"] for f in stats["filters"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=ROOT / "bin/plane_worker")
    parser.add_argument("--ubsan-binary", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "runs/plane-validation.json")
    args = parser.parse_args()
    start_time = time.monotonic()
    # Integer inequalities certify the rounded constants without decimal software.
    assert (2*P-1)**3 < 114 * (2*DEN)**3 < (2*P+1)**3
    assert (2*Q-1)**3 < 114**2 * (2*DEN)**3 < (2*Q+1)**3
    cases = []
    for ell in (1, 5, 25):
        for radius in (1, 12, 20_000_000, 100_000_000):
            total = 5 * (2 * radius + 1)**2
            count = min(total, 1000)
            cases.append(validate_dump(args.binary, ell, radius, total-count, count, 117114))
    # Full small domains test that the affine permutation plus plane mapping is
    # a bijection, including all five offsets at every (b,c).
    for ell in (1, 5, 25):
        cases.append(validate_dump(args.binary, ell, 3, 0, 245, 114))
    # Synthetic rational a≈-b/2 has exact rounding ties. Explicitly check the
    # C membership test against full sets, including absent opposite edges.
    tie_rows=run(args.binary,"tie_selftest")
    tie_exceptions=0
    for ell in (1,5,25):
        rr=[r for r in tie_rows if r['ell']==ell]
        domain={(r['a'],r['b'],r['c']) for r in rr}
        all_roots,kept_roots=set(),set()
        for r in rr:
            a,b,c=r['a'],r['b'],r['c']
            u=(-4*b-16*c)%ell
            assert a in {u+ell*((2*(-b-2*u)+2*ell)//(4*ell)+t) for t in range(-2,3)}
            negative=(c,b,a)<(0,0,0)
            opposite=(-a,-b,-c) in domain
            assert r['symmetry_duplicate']==(negative and opposite)
            tie_exceptions+=negative and not opposite
            n=a**3+114*b**3+12996*c**3-342*a*b*c
            d=abs(n)//ell;C=b*b-a*c;B=114*c*c-a*b
            if d>=2 and d%3 and math.gcd(C,d)==1:
                root=B*pow(C,-1,d)%d;assert pow(root,3,d)==114%d
                all_roots.add((d,root))
                if not r['symmetry_duplicate']:kept_roots.add((d,root))
        assert all_roots==kept_roots
    assert tie_exceptions>0
    policies = []
    for ell in (1, 5, 25):
        fixed = run(args.binary, "tile", ell, 20_000_000, 5000, 100_000, 128, "fixed", 32, 114)
        adaptive = run(args.binary, "tile", ell, 20_000_000, 5000, 100_000, 128, "adaptive", 32, 114)
        a, b = fixed[-1], adaptive[-1]
        check_partition(a); check_partition(b)
        keys = ("candidates", "curves", "quotient_points", "exact_tests", "hits", "zero_norm", "invalid_d", "unsupported_D", "noninvertible_C", "symmetry_rejected", "covered", "rejected_mod243", "rejected_parity")
        assert {k: a[k] for k in keys} == {k: b[k] for k in keys}
        assert fixed[:-1] == adaptive[:-1]
        policies.append(dict(ell=ell, fixed=a, adaptive=b))
    # Recovery checks exercise the exact shared checker, including a large case.
    known = [
        (6, 107, 43, 128, (-60355, 10529, 60248)),
        (3, 108398887211, 21397363547, 5_000_000,
         (-569936821113563493509, -472715493453327032, 569936821221962380720)),
    ]
    recovered = []
    for k, d, r, ratio, xyz in known:
        rows = run(args.binary, "curve", k, d, r, ratio, "adaptive")
        hits = {tuple(sorted(map(int, row["xyz"]))) for row in rows if row["type"] == "hit"}
        assert tuple(sorted(xyz)) in hits
        for hit in hits:
            assert sum(v**3 for v in hit) == k
        recovered.append(dict(k=k, solutions=[list(h) for h in sorted(hits)]))
    for bad in [("tile",1,0,0,1,64,"fixed"), ("tile",1,100_000_001,0,1,64,"fixed"),
                ("tile",5,1,44,2,64,"fixed"), ("tile",25,10,0,1,64,"fixed",64)]:
        result = subprocess.run([str(args.binary), *map(str,bad)], text=True, capture_output=True)
        assert result.returncode != 0, bad
    sanitized = []
    if args.ubsan_binary:
        for ell in (1,5,25):
            sanitized.append(validate_dump(args.ubsan_binary, ell, 100_000_000,
                                           5*(200_000_001)**2-1000, 1000, 2**64-1))
            check_partition(run(args.ubsan_binary, "tile", ell, 20_000_000, 0, 10000, 128, "adaptive")[-1])
    result = dict(constants_certified_by_integer_inequalities=True, generator_cases=cases,
                  generated_coefficients_checked=sum(c["count"] for c in cases),
                  modular_roots_checked=sum(c["roots"] for c in cases),
                  finite_domain_bijection_checked=True, fixed_adaptive_equivalence=policies,
                  symmetry_root_set_preservation=True, synthetic_rounding_tie_rows=len(tie_rows),
                  rounding_tie_opposite_absent_cases=tie_exceptions,
                  exact_known_curve_recovery=recovered, invalid_bounds_rejected=True,
                  ubsan_cases=sanitized, elapsed_seconds=time.monotonic()-start_time,
                  source_sha256={name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                                 for name in ("plane_worker.c", "campaign_worker.c", "validate_plane.py")})
    args.output.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({k:result[k] for k in ("generated_coefficients_checked", "modular_roots_checked", "elapsed_seconds")}, indent=2))


if __name__ == "__main__":
    main()
