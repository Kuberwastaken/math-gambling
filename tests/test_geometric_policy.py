import json
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from geometric_policy import (ACTIVE_IDS, RETIRED_IDS, RETIRED_WEIGHT, calibrate, mass,
                              prior_value, cpu_budget_policy)
from search_core import CONTEXT_BY_ID, make_task, task_id

def record(context,cpu=1.,curves=0,version=1,row=0):
    task=make_task(context,row,0,version)
    return {'result':{'task':task,'id':task_id(task),'counters':{'curves':curves}},'server_replay_cpu_ms':cpu}

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
class RevisionTwoTests(unittest.TestCase):
    def policy(self):
        rows=[record(f'c{i:02d}',1+i,100) for i in range(81)]*8
        return calibrate(rows,10,2)

    def test_retired_band_holds_a_trace_weight_and_54_lanes_share_the_floor(self):
        self.assertEqual(len(RETIRED_IDS),27)
        self.assertEqual(len(ACTIVE_IDS),54)
        self.assertTrue(all(CONTEXT_BY_ID[i]['low']==256 and CONTEXT_BY_ID[i]['high']==4096 for i in RETIRED_IDS))
        for policy in (self.policy(),cpu_budget_policy(self.policy(),2)):
            rows={c['id']:c for c in policy['contexts']}
            self.assertEqual(policy['exploration_fraction'],.1)
            self.assertEqual(policy['policy_revision'],2)
            self.assertEqual(policy['retired_bands'],[[256,4096]])
            self.assertEqual(policy['policy_version'] in ('mg114-geometric-cost-v1','mg114-cpu-budget-v1'),True)
            for key in RETIRED_IDS:
                self.assertEqual(rows[key]['weight'],RETIRED_WEIGHT)
                self.assertEqual(rows[key]['exploit_weight'],0)
                self.assertEqual(rows[key]['exploration_weight'],0)
            for key in ACTIVE_IDS:
                self.assertGreater(rows[key]['weight'],RETIRED_WEIGHT)
                self.assertAlmostEqual(rows[key]['exploration_weight'],1/54)
            self.assertAlmostEqual(sum(c['weight'] for c in policy['contexts']),1,delta=1e-9)
            floor=sum(.1*rows[k]['exploration_weight'] for k in ACTIVE_IDS)
            self.assertAlmostEqual(floor,.1,delta=1e-4)
            self.assertAlmostEqual(sum(rows[k]['exploit_weight'] for k in ACTIVE_IDS),1)

    def test_cpu_shares_ignore_the_retired_band_and_still_sum_to_one(self):
        policy=cpu_budget_policy(self.policy(),2)
        rows={c['id']:c for c in policy['contexts']}
        self.assertEqual(sum(rows[k]['target_cpu_share'] for k in RETIRED_IDS),0)
        self.assertAlmostEqual(sum(rows[k]['target_cpu_share'] for k in ACTIVE_IDS),1)
        total=sum(rows[k]['weight']*rows[k]['predicted_cpu_ms_per_task'] for k in ACTIVE_IDS)
        for key in ACTIVE_IDS:
            self.assertAlmostEqual(rows[key]['weight']*rows[key]['predicted_cpu_ms_per_task']/total,
                                   rows[key]['target_cpu_share'])

    def test_v2_observations_are_normalized_to_v1_equivalent_units(self):
        v1=[record('c00',8.,80)]*16
        v2=[record('c00',64.,640,2)]*2
        a=calibrate(v1,1,2);b=calibrate(v1[:8]+v2,1,2)
        first={c['id']:c for c in a['contexts']}['c00']
        second={c['id']:c for c in b['contexts']}['c00']
        self.assertAlmostEqual(first['predicted_cpu_ms_per_task'],second['predicted_cpu_ms_per_task'])
        self.assertAlmostEqual(first['predicted_curves_per_task'],second['predicted_curves_per_task'])
        # A v2 task is one observation worth eight v1 tiles of cost.
        self.assertEqual(second['recent_samples'],10)
        raw=calibrate(v1[:8]+v2,1)
        self.assertLess({c['id']:c for c in raw['contexts']}['c00']['predicted_cpu_ms_per_task'],
                        8*second['predicted_cpu_ms_per_task'])

    def test_revision_one_is_unchanged(self):
        rows=[record(f'c{i:02d}',1+i,100) for i in range(81)]*8
        p=calibrate(rows,10)
        self.assertEqual(p['exploration_fraction'],.4)
        self.assertNotIn('policy_revision',p)
        self.assertTrue(all(c['weight']>=.4/81 for c in p['contexts']))
        self.assertAlmostEqual(sum(c['weight'] for c in p['contexts']),1)

if __name__=='__main__':unittest.main()
