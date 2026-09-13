"""The multi-target generator is a sound generalization of the 114 engine.

The safety property we must never lose: the general engine scans a superset of
whatever the trusted 114 engine scans, so it can never silently miss a solution.
"""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import search_core as sc
import multi_target as mt


class MultiTargetTests(unittest.TestCase):
    def test_constants_and_offset_generalize_to_114(self):
        alpha, _ = mt.roots(114)
        self.assertEqual(alpha, sc.ALPHA)  # exact floor(114^(1/3) * SCALE)
        # ALPHA2 rounding differs by <=1, but offset_base divides by 2*SCALE, so
        # the base is identical across the entire coefficient range.
        extremes = [-6_000_000, -1_500_000, -1, 0, 1, 1_500_000, 6_000_000]
        for b in extremes:
            for c in extremes:
                self.assertEqual(mt.offset_base(114, b, c), sc.offset_base(1, b, c))

    def test_general_engine_scans_a_superset_of_the_114_engine(self):
        real = sc.scan_curve

        def recorder(store):
            def wrapped(k, d, r, qlo, qhi, **kw):
                store.append((d, r, qlo, qhi))
                return real(k, d, r, qlo, qhi, **kw)
            return wrapped

        rng = random.Random(3)
        ell1 = [c for c in sc.CONTEXTS if c["ell"] == 1]
        common = 0
        try:
            for c in rng.sample(ell1, 8):
                row = rng.randrange(0, int(c["totalRows"]) // sc.ROWS_PER_TASK) * sc.ROWS_PER_TASK
                block = rng.randrange(0, c["blocks"])
                base, general = [], []
                sc.scan_curve = recorder(base)
                sc.run_task(sc.make_task(c["id"], row, block))
                sc.scan_curve = recorder(general)
                mt.run_target(114, c["id"], row, block)
                sc.scan_curve = real
                # No interval the trusted engine scans is dropped by the general one.
                self.assertLessEqual(set(base), set(general))
                common += len(base)
        finally:
            sc.scan_curve = real
        self.assertGreater(common, 0, "expected the 114 engine to scan some intervals")

    def test_new_targets_emit_valid_roots_and_balanced_counters(self):
        rng = random.Random(9)
        ell1 = [c for c in sc.CONTEXTS if c["ell"] == 1]
        for k in (390, 627, 633, 732):
            self.assertTrue(mt.admissible(k))
            for c in rng.sample(ell1, 4):
                row = rng.randrange(0, int(c["totalRows"]) // sc.ROWS_PER_TASK) * sc.ROWS_PER_TASK
                cn = mt.run_target(k, c["id"], row)["counters"]  # asserts r^3==k mod d internally
                self.assertEqual(cn["generators"], sum(cn[x] for x in (
                    "outside_shell", "invalid_d", "signed_excluded", "noninvertible", "curves")))
                self.assertEqual(cn["quotient_points"], sum(cn[x] for x in (
                    "rejected_mod243", "rejected_parity", "rejected_prime", "exact_tests")))
                self.assertEqual(cn["signed_excluded"], 0)  # k-specific prune dropped in the safe path

    def test_shared_scan_recovers_known_solutions_for_solved_targets(self):
        for k, x, y, z in [(30, 2220422932, -2218888517, -283059965),
                           (84, 41639611, -41531726, -8241191),
                           (39, -159380, 134476, 117367)]:
            z2, x2, y2 = sorted([x, y, z], key=abs)  # smallest-|·| coordinate is z
            d = abs(x2 + y2)
            r, q = z2 % d, (z2 - z2 % d) // d
            self.assertEqual(len(sc.scan_curve(k, d, r, q, q)["hits"]), 1)

    def test_rejects_inadmissible_target_and_non_ell1_context(self):
        with self.assertRaises(ValueError):
            mt.run_target(113, 'c00', 0)   # 113 = -4 mod 9: provably no solution
        with self.assertRaises(ValueError):
            mt.run_target(627, 'c27', 0)   # c27 is an ell=5 context (k-specific class)


if __name__ == '__main__':
    unittest.main()
