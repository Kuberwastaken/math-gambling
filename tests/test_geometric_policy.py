import json
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from geometric_policy import calibrate, mass, prior_value, cpu_budget_policy
from search_core import CONTEXT_BY_ID

def record(context,cpu=1.,curves=0):
    return {'result':{'task':{'context':context},'counters':{'curves':curves}},'server_replay_cpu_ms':cpu}

class GeometricPolicyTests(unittest.TestCase):
    def test_cpu_exploration_is_a_cost_share_and_every_context_survives(self):
        rows=[record(f'c{i:02d}',1+i,100) for i in range(81)]*8
        base=calibrate(rows,10);p=cpu_budget_policy(base)
        total=sum(c['weight']*c['predicted_cpu_ms_per_task'] for c in p['contexts'])
        for c in p['contexts']:
            self.assertGreater(c['weight'],0)
            self.assertAlmostEqual(c['weight']*c['predicted_cpu_ms_per_task']/total,c['target_cpu_share'])
            self.assertGreaterEqual(c['target_cpu_share'],.4/81)
        self.assertAlmostEqual(sum(c['weight'] for c in p['contexts']),1)
    def test_geometry_prefers_lower_ratio_and_divisor(self):
        self.assertGreater(mass(0,64),mass(64,256))
        self.assertGreater(mass(64,256),mass(256,4096))
        self.assertEqual(mass(0,3),0)
        self.assertAlmostEqual(prior_value(CONTEXT_BY_ID['c00'])/prior_value(CONTEXT_BY_ID['c03']),2)
    def test_zero_heavy_data_does_not_collapse_and_zeros_charge_cost(self):
        rows=[]
        for i in range(81):
            rows += [record(f'c{i:02d}',1,0)]*8+[record(f'c{i:02d}',1,100)]*2
        p=calibrate(rows,math.ceil(len(rows)/64));a={r['id']:r for r in p['contexts']}
        self.assertGreater(a['c00']['weight'],a['c02']['weight'])
        self.assertEqual(a['c00']['aggregate_cpu_ms'],10)
        self.assertEqual(a['c00']['zero_curve_tasks'],8)
        self.assertGreater(a['c00']['predicted_curves_per_task'],0)
    def test_same_geometry_more_cost_gets_less_weight(self):
        rows=[record('c00',1,100)]*128+[record('c27',10,100)]*128
        p=calibrate(rows,4);a={r['id']:r for r in p['contexts']}
        self.assertGreater(a['c00']['weight'],a['c27']['weight'])
    def test_finite_supported_normalized_and_frozen_prefix(self):
        rows=[record('c00',1,i%2) for i in range(128)]
        a=calibrate(rows,1);b=calibrate(rows[:64]+[record('c80',99,999)]*64,1)
        self.assertEqual(a,b)
        self.assertAlmostEqual(sum(r['weight'] for r in a['contexts']),1)
        self.assertTrue(all(math.isfinite(r['weight']) and r['weight']>=.4/81 for r in a['contexts']))
    def test_reject_invalid_timing_and_counts(self):
        for r in [record('c00',0),record('c00',float('nan')),record('c00',True),record('c00',1,-1)]:
            with self.assertRaises(ValueError):calibrate([r],1)
if __name__=='__main__':unittest.main()
