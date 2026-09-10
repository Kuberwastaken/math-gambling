"""Exact integer shell pruning and post-scan observation regressions."""
import hashlib
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import search_core as core

# Frozen before pruning: SHA-256 of all canonical results (including counters,
# hits, task IDs and result digests) for the corpus below, in its stated order.
BASELINE_CORPUS_SHA256 = 'b8db130a82bd3cfd37f3d99e4de84c112b6ffb9176f51d12618b3a9a7f9bb780'


def corpus():
    return [core.make_task(c['id'], row, block)
            for c in core.CONTEXTS
            for row, block in [(0, 0),
                ((int(c['totalRows'])-1)//128*128, c['blocks']-1),
                (int(c['totalRows'])//7//128*128, c['blocks']//2)]]


class ShellPruningTests(unittest.TestCase):
    def test_complete_results_equal_frozen_unpruned_baseline(self):
        results = [core.run_task(task) for task in corpus()]
        digest = hashlib.sha256(core.canonical_json(results).encode('ascii')).hexdigest()
        self.assertEqual(digest, BASELINE_CORPUS_SHA256)
        # This includes wholly empty tasks; their logical work is not dropped.
        empty = [r for r in results if r['counters']['outside_shell'] == r['counters']['generators']]
        self.assertEqual(len(empty), 162)
        self.assertTrue(all(r['counters']['generators'] > 0 for r in empty))

    def test_integer_bounds_never_remove_a_shell_member(self):
        rng = random.Random(114)
        for _ in range(3000):
            ell = rng.choice((1, 5, 25))
            magnitude = rng.choice((30, 6_000_000, 10**20))
            b, c = (rng.randrange(-magnitude, magnitude+1) for _ in range(2))
            base = core.offset_base(ell, b, c)
            tlo = rng.randrange(-32, 8192)
            thi = tlo+rng.randrange(16)
            constant, linear = 114*b**3+12996*c**3, 342*b*c
            values = {t: core.norm(base+ell*t, b, c) for t in range(tlo, thi+1)}
            lower, upper = sorted(rng.sample(list(values.values())*2, 2))
            lower += rng.choice((-1, 0, 1))
            upper = max(lower+1, upper+rng.choice((-1, 0, 1)))
            first, last = core._shell_interval(base, ell, tlo, thi, lower, upper, constant, linear)
            actual = {t for t, n in values.items() if lower < n <= upper}
            kept = set(range(first, last+1))
            self.assertLessEqual(actual, kept)
            self.assertTrue(all(not lower < values[t] <= upper for t in set(values)-kept))
            self.assertTrue(tlo <= first <= thi and tlo-1 <= last <= thi)
            for t, n in values.items():
                a = base+ell*t
                self.assertEqual(a*a*a-linear*a+constant, n)

    def test_strict_lower_inclusive_upper_and_nonmonotone_fallback(self):
        # N(t)=t^3 is increasing: reject equality at the lower boundary,
        # retain equality at the upper boundary, including negative t.
        self.assertEqual(core._shell_interval(0, 1, -8, 7, -27, 8, 0, 0), (-2, 2))
        self.assertEqual(core._shell_interval(0, 1, 0, 15, 3375, 4000, 0, 0), (0, -1))
        self.assertEqual(core._shell_interval(0, 1, 0, 15, -2, -1, 0, 0), (0, -1))
        # N(t)=t^3-342t+13110 turns inside this interval. Neither endpoint
        # rules out intermediate members, so the whole block must survive.
        self.assertEqual(core._shell_interval(0, 1, 0, 15, 10500, 11000, 13110, 342), (0, 15))

    def test_lattice_assertion_also_covers_pruned_generators(self):
        with self.assertRaisesRegex(ArithmeticError, 'divisibility'):
            core._shell_interval(0, 5, 0, 15, 10**30, 2*10**30, 1, 0)

    def test_complete_curve_callback_is_exact_inclusive_and_outside_digest(self):
        c = core.CONTEXT_BY_ID['c05']
        task = core.make_task(c['id'], int(c['totalRows'])//7//128*128, c['blocks']//2)
        events, finished_scans = [], []
        original_scan = core.scan_curve

        def observed_scan(*args, **kwargs):
            result = original_scan(*args, **kwargs)
            finished_scans.append(args)
            return result

        def curve_finished(event):
            self.assertEqual(len(finished_scans), len(events)+1)
            self.assertEqual(set(event), {'D', 'r', 's', 'qlo', 'qhi', 'minimal_abs_z'})
            self.assertIs(event['minimal_abs_z'], True)
            d, r, s, qlo, qhi = (int(event[key]) for key in ('D', 'r', 's', 'qlo', 'qhi'))
            self.assertEqual(d, abs(s))
            self.assertTrue(0 <= r < d)
            self.assertEqual(pow(r, 3, d), 114 % d)
            self.assertLessEqual(qlo, qhi)
            self.assertLessEqual(qhi-qlo, 8192)
            events.append(event)

        expected = core.run_task(task)
        with patch.object(core, 'scan_curve', side_effect=observed_scan):
            actual = core.run_task(task, on_curve=curve_finished)
        self.assertEqual(actual, expected)
        self.assertGreater(len(events), 0)
        self.assertEqual(len(events), actual['counters']['curves'])
        self.assertEqual(sum(int(e['qhi'])-int(e['qlo'])+1 for e in events), actual['counters']['quotient_points'])
        # A failed partial scan must not be advertised as completed coverage.
        partial_events = []
        with patch.object(core, 'scan_curve', side_effect=ArithmeticError('partial scan')):
            with self.assertRaisesRegex(ArithmeticError, 'partial scan'):
                core.run_task(task, on_curve=partial_events.append)
        self.assertEqual(partial_events, [])


if __name__ == '__main__':
    unittest.main()
