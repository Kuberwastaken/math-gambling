"""Independent bounded oracles for the isolated positive unit-phase family."""
from fractions import Fraction as F
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"tools"))
import unit_phase_experiment as tube
from search_core import scan_curve


class UnitPhaseTests(unittest.TestCase):
    def test_integer_root_bounds_at_endpoints(self):
        for n in range(1000):
            lo, hi = tube.cube_floor(n), tube.cube_ceil(n)
            self.assertLessEqual(lo**3, n)
            self.assertGreater((lo+1)**3, n)
            self.assertGreaterEqual(hi**3, n)
            if hi:
                self.assertLess((hi-1)**3, n)
        for n in (10**60-1, 10**60, 10**60+1):
            self.assertLessEqual(tube.cube_floor(n)**3, n)
            self.assertGreaterEqual(tube.cube_ceil(n)**3, n)
        for value in (F(0), F(1, 100), F(49), F(49, 4), F(10**80+1, 3)):
            hi = tube.sqrt_ceil(value)
            self.assertGreaterEqual(hi*hi, value)
            if hi:
                self.assertLess((hi-1)**2, value)

    def test_algebraic_sign_refines_and_handles_equality(self):
        self.assertEqual(tube.phase_compare((1, 0, 0), 1), 0)
        for rational in (F(4), F(5), F(tube.ALPHA, tube.SCALE), (tube.AL+tube.AH)/2):
            expected = 1 if rational**3 < 114 else -1
            self.assertEqual(tube.algebraic_sign((-rational, 1, 0), F(4), F(5)), expected)
        with self.assertRaises(ValueError):
            tube.algebraic_sign((1, 2, 3), F(5), F(6))

    def test_norm_against_multiplication_matrix_determinant(self):
        rng = random.Random(11420260912)
        for _ in range(200):
            a, b, c = (rng.randrange(-1000, 1001) for _ in range(3))
            matrix = ((a, 114*c, 114*b), (b, a, 114*c), (c, b, a))
            x, y, z = matrix
            determinant = (x[0]*(y[1]*z[2]-y[2]*z[1])
                           - x[1]*(y[0]*z[2]-y[2]*z[0])
                           + x[2]*(y[0]*z[1]-y[1]*z[0]))
            self.assertEqual(tube.norm(a, b, c), determinant)

    def test_circle_bounds_equal_full_box_in_twelve_cells(self):
        budget = tube.Budget(10, positions=200000)
        total = 0
        for ell in (1, 5, 25):
            for low in (128, 1024):
                for phase_low, phase_high in ((5, 28), (28, 1000)):
                    cell = tube.Cell(ell, low, 4*low, phase_low, phase_high)
                    actual, _ = tube.enumerate_cell(cell, budget)
                    oracle = tube.brute_box(cell, budget)
                    self.assertEqual(actual, oracle)
                    total += len(actual)
                    # Membership independently uses the real embedding interval,
                    # rather than reducing its cube in the cubic field.
                    for a, b, c in actual:
                        n = tube.norm(a, b, c)
                        lower = a+b*tube.AL+c*tube.AL**2
                        upper = a+b*tube.AH+c*tube.AH**2
                        self.assertGreater(lower**3, phase_low*n)
                        self.assertLessEqual(upper**3, phase_high*n)
        self.assertEqual(total, 166)

    def test_strict_norm_boundary_and_exact_root_extraction(self):
        cell = tube.Cell(1, 1024, 4096)
        members, _ = tube.enumerate_cell(cell, tube.Budget())
        checked = 0
        for abc in members:
            d = tube.norm(*abc)
            self.assertFalse(tube.member(abc, tube.Cell(1, d, d+1)))
            self.assertTrue(tube.member(abc, tube.Cell(1, d-1, d)))
            result = tube.extract_root(abc, cell)
            if result["status"] == "root":
                r = result["r"]
                # Exhaust all residues for these tiny moduli, independently of B/C.
                roots = {z for z in range(d) if z**3 % d == 114 % d}
                self.assertIn(r, roots)
                a, b, c = abc
                self.assertEqual((a+b*r+c*r*r) % d, 0)
                checked += 1
        self.assertGreater(checked, 0)

    def test_sieved_scans_equal_unsieved_and_signed_endpoints(self):
        cell = tube.Cell(25, 1024, 4096)
        members, _ = tube.enumerate_cell(cell, tube.Budget())
        for abc in members:
            root = tube.extract_root(abc, cell)
            if root["status"] != "root":
                continue
            d, r = root["D"], root["r"]
            s, lo, hi = tube.quotient_interval(d, r)
            expected = [q for q in range(-66, 67)
                        if 0 < abs(r+d*q) <= 64*d and (r+d*q)*s < 0]
            self.assertEqual(list(range(lo, hi+1)), expected)
            self.assertEqual(scan_curve(114, d, r, lo, hi)["hits"],
                             scan_curve(114, d, r, lo, hi, sieve=False)["hits"])

    def test_separation_is_conditional_but_inequalities_are_recomputed(self):
        certificate = tube.separation_certificate()
        self.assertTrue(certificate["arithmetic_checks_passed"])
        self.assertEqual(len(certificate["classes"]), 3)
        self.assertIn("PARI was not rerun", " ".join(certificate["conditional_on"]))
        with patch.object(tube, "D0", 1):
            with self.assertRaises(ArithmeticError):
                tube.separation_certificate()

    def test_budgets_stop_without_claiming_completion(self):
        with self.assertRaises(tube.LimitReached):
            tube.enumerate_cell(tube.Cell(25, 1024, 4096), tube.Budget(rows=0))
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)/"partial"
            with patch.object(tube.Budget, "charge", side_effect=tube.LimitReached("test cap")):
                report = tube.run_experiment(output)
            self.assertEqual(report["status"], "partial")
            self.assertEqual(report["cells"], [])
            self.assertFalse(report["promotion_allowed"])
            self.assertEqual(json.loads((output/"results.json").read_text())["status"], "partial")

    def test_positive_callback_is_durable_and_invalid_hit_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            def callback(hit):
                tube.preserve_hit(output, hit, k=3)
                raise RuntimeError("interrupt after durable positive")
            with self.assertRaisesRegex(RuntimeError, "interrupt"):
                scan_curve(3, 2, 1, 0, 0, on_hit=callback)
            records = list(output.glob("identity-*.json"))
            self.assertEqual(len(records), 1)
            self.assertEqual(json.loads(records[0].read_text())["hit"]["xyz"], ["1", "1", "1"])
            with self.assertRaises(ArithmeticError):
                tube.preserve_hit(output, {"xyz": ["1", "1", "1"]})

    def test_complete_experiment_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)/"complete"
            report = tube.run_experiment(output)
            self.assertEqual(report["status"], "complete")
            self.assertEqual(len(report["cells"]), 6)
            self.assertEqual(sum(c["members"] for c in report["cells"]), 129)
            self.assertEqual(report["work_used"]["curves"], 63)
            self.assertEqual(report["work_used"]["quotient_positions"], 4032)
            self.assertFalse(report["promotion_allowed"])
            with self.assertRaises(FileExistsError):
                tube.run_experiment(output)


if __name__ == "__main__":
    unittest.main()
