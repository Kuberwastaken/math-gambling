import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import strategy_model as m
from search_core import make_task, run_task

class StrategyModelTests(unittest.TestCase):
    def records(self,n=8):
        out=[]
        for i in range(n):
            task=make_task('c00',128*i)
            result=run_task(task)
            out.append({'schema':'math-gambling-verified-task-v1','sequence':i+1,'result':result,'server_replay_cpu_ms':1+i})
        return out
    def write(self,path,records):
        folder=path/'receipts/tasks/aa';folder.mkdir(parents=True,exist_ok=True)
        for r in records:(folder/f"{r['sequence']}.json").write_text(json.dumps(r))
    def test_freeze_repeat_future_and_production_isolation(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(m,'BOUNDARY',4):
            p=Path(tmp); records=self.records();self.write(p,records[:4]);(p/'strategy.json').write_text('UNCHANGED')
            first=m.publish(p); history=p/first['history'];model=next(history.glob('model-*'));before=model.read_bytes()
            self.write(p,records);second=m.publish(p)
            self.assertEqual(second['completed_evaluations'],1);self.assertEqual(before,model.read_bytes())
            snapshot={str(f):f.read_bytes() for f in (p/'learning').rglob('*.json')}
            with patch.object(m,'evaluate',side_effect=AssertionError('frozen evaluations must not be recomputed')):
                m.publish(p)
            self.assertEqual(snapshot,{str(f):f.read_bytes() for f in (p/'learning').rglob('*.json')})
            self.assertEqual((p/'strategy.json').read_text(),'UNCHANGED')
    def test_changed_frozen_timing_rejected(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(m,'BOUNDARY',4):
            p=Path(tmp);r=self.records(4);self.write(p,r);m.publish(p);r[0]['server_replay_cpu_ms']=19;self.write(p,r)
            with self.assertRaises(ValueError):m.publish(p)
    def test_tampered_exact_result_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);r=self.records(1);r[0]['result']['counters']['exact_tests']+=1;self.write(p,r)
            with self.assertRaises(ValueError):m.observations(p)
    def test_invalid_cost_rejected(self):
        for bad in [0,-1,True,float('nan'),float('inf')]:
            with tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp);r=self.records(1);r[0]['server_replay_cpu_ms']=bad;self.write(p,r)
                with self.assertRaises(ValueError):m.observations(p)
    def test_geometry_split_shared_across_context_variants(self):
        for shape in range(3):
            groups=[m.features(make_task(f'c{i:02d}',0))[2:] for i in range(81) if m.CONTEXT_BY_ID[f'c{i:02d}']['shape']==shape]
            self.assertEqual(len(set(groups)),1)
    def test_heldout_not_used_by_fit(self):
        task=make_task('c00',0)
        rows=[{'features':('c00','c00:0:0:0','g',False),'y':dict.fromkeys(m.TARGETS,1)},
              {'features':('c00','c00:0:0:1','h',True),'y':dict.fromkeys(m.TARGETS,999999)}]
        model=m.fit(rows);self.assertEqual(model['global']['n'],1)
        self.assertEqual(m.predict(model,task)['cpu_ms'],1)
    def test_empty_ledger_stays_shadow(self):
        with tempfile.TemporaryDirectory() as tmp:
            report=m.publish(Path(tmp));self.assertEqual(report['model_count'],0);self.assertFalse(report['promotion']['allowed'])
if __name__=='__main__':unittest.main()
