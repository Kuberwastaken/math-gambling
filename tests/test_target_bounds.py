"""Adaptive cross-target allocation keeps 114 primary, favors measured yield and
the density prior, and never starves or excludes a region."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import target_bounds as tb


class TargetBoundsTests(unittest.TestCase):
    def test_split_keeps_114_primary_and_sums_to_one(self):
        split = tb.campaign_split()
        self.assertAlmostEqual(split[tb.PRIMARY], tb.PRIMARY_SHARE)
        self.assertAlmostEqual(sum(split.values()), 1.0)
        others = sum(v for k, v in split.items() if k != tb.PRIMARY)
        self.assertAlmostEqual(others, 1 - tb.PRIMARY_SHARE)
        self.assertTrue(all(v > 0 for v in split.values()))  # exploration floor: nothing starved

    def test_higher_density_prior_gets_more_of_the_cross_target_slice(self):
        split = tb.campaign_split()
        # 627 (prior 0.13) should outrank a neutral-prior open case (e.g. 633).
        self.assertGreater(split[627], split[633])

    def test_measured_yield_shifts_weight_within_the_slice(self):
        base = tb.campaign_split()
        obs = {633: {"curves": 5_000_000, "cpu_ms": 1000.0},
               732: {"curves": 10_000, "cpu_ms": 1000.0}}
        moved = tb.campaign_split(observations=obs)
        self.assertAlmostEqual(moved[tb.PRIMARY], tb.PRIMARY_SHARE)  # 114 slice unchanged
        self.assertGreater(moved[633], base[633])   # productive target gains
        self.assertGreater(moved[633], moved[732])   # more curves/cpu -> more weight

    def test_context_bounds_downweight_barren_but_never_zero(self):
        obs = {
            "c00": {"curves": 1_000_000, "cpu_ms": 100.0, "empty_tasks": 10, "tasks": 100},
            "c01": {"curves": 0, "cpu_ms": 100.0, "empty_tasks": 100, "tasks": 100},
        }
        w = tb.context_bounds(obs)
        self.assertAlmostEqual(sum(w.values()), 1.0)
        self.assertGreater(w["c00"], w["c01"])       # productive beats barren
        self.assertGreater(w["c01"], 0.0)            # barren still gets the floor

    def test_refine_gates_confidence_on_sample_size(self):
        obs = {
            "c00": {"curves": 100, "cpu_ms": 10.0, "empty_tasks": 40, "tasks": 200},
            "c01": {"curves": 5, "cpu_ms": 10.0, "empty_tasks": 8, "tasks": 10},
        }
        r = tb.refine_from_wrong_cases(obs, min_samples=64)
        self.assertTrue(r["c00"]["confident"])       # 200 samples -> trusted
        self.assertFalse(r["c01"]["confident"])      # 10 samples -> not yet
        self.assertAlmostEqual(r["c00"]["provably_empty_fraction"], 0.2)
        self.assertGreater(r["c00"]["weight"], 0.0)
        self.assertGreater(r["c01"]["weight"], 0.0)

    def test_admissibility(self):
        self.assertTrue(tb.admissible(627))
        self.assertFalse(tb.admissible(113))  # -4 mod 9, no solutions
        self.assertFalse(tb.admissible(2))


if __name__ == '__main__':
    unittest.main()
