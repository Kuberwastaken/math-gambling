import math
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from benchmark_geometry import Exposure, summary, fast_mass
from geometric_policy import mass, KAPPA


def event(lo, hi, r=2, s=101):
    return dict(D='101', r=str(r), s=str(s), qlo=str(lo), qhi=str(hi), minimal_abs_z=True)


class ExposureTests(unittest.TestCase):
    def test_fast_integral_against_original_quadrature(self):
        rng=random.Random(913)
        bands=[(0,0),(0,3),(0,16),(KAPPA,4096),(16,256),(256,4096)]
        for _ in range(500):
            lo=10**rng.uniform(-1,6)
            bands.append((lo,lo+10**rng.uniform(-2,4)))
        for lo,hi in bands:
            self.assertTrue(math.isclose(fast_mass(lo,hi),mass(lo,hi),rel_tol=2e-8,abs_tol=1e-14),(lo,hi))

    def test_overlap_counts_only_new_integer_positions(self):
        e = Exposure()
        e.add(event(10, 19)); first = e.value
        e.add(event(10, 19))
        self.assertEqual(e.value, first)
        e.add(event(15, 24)); e.add(event(5, 12))
        self.assertEqual(e.positions, 20)
        self.assertEqual(e.repeated_positions, 18)
        self.assertEqual(e.intervals[(101, 2, 101)], [(5, 24)])
        self.assertTrue(math.isclose(e.value, Exposure.weight(101,2,5,24), rel_tol=1e-8))

    def test_root_and_sign_not_conflated(self):
        e=Exposure()
        for x in [event(10,19),event(10,19,r=3),event(10,19,s=-101)]: e.add(x)
        self.assertEqual(e.positions,30)
        self.assertEqual(len(e.intervals),3)

    def test_negative_q_reflection_and_ordering_cutoff(self):
        self.assertTrue(math.isclose(Exposure.weight(101,2,10,19),
                                    Exposure.weight(101,99,-20,-11),rel_tol=1e-12))
        self.assertEqual(Exposure.weight(101,2,0,2),0)
        self.assertGreater(Exposure.weight(101,2,4,8),Exposure.weight(101,2,40,44))

    def test_bad_interval_is_not_credited(self):
        for item in [event(5,4),event(5,9,r=101),event(5,9,s=1),
                     {**event(5,9),'minimal_abs_z':False}]:
            with self.assertRaises(ValueError): Exposure().add(item)

    def test_actual_cpu_and_zero_baseline_fail_closed(self):
        rows=[dict(repeat=i,arm=a,exposure=20,cpu_s=cpu)
              for i in range(8) for a,cpu in [('current',1),('learned',2)]]
        s=summary(rows)
        self.assertEqual(s['paired_median_rate_ratio'],.5)
        self.assertFalse(s['exploratory_gate_passed'])
        self.assertFalse(s['production_promotion'])
        rows[0]['exposure']=0
        with self.assertRaises(ValueError):summary(rows)


if __name__=='__main__':unittest.main()
