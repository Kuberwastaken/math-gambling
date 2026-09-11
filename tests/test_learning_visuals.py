import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from learning_visuals import generate, METRICS


class LearningVisualTests(unittest.TestCase):
    def test_versions_remain_separate_and_single_point_is_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp);learning=data/'learning';learning.mkdir()
            old=learning/'mg114-spatial-shadow-v1'/'aaaaaaaaaaaaaaaa';old.mkdir(parents=True)
            new=learning/'mg114-spatial-shadow-v2'/'bbbbbbbbbbbbbbbb';new.mkdir(parents=True)
            latest=dict(schema='mg114-spatial-shadow-v2',history=str(new.relative_to(data)),mode='shadow',
                        through=2048,observed_tasks=2300,model_count=1,completed_evaluations=0,next_boundary=3072,
                        source_hash='b'*64,first_training_boundary=2048)
            (learning/'latest.json').write_text(json.dumps(latest))
            scores=dict(context_baseline={k:10 for k in METRICS},spatial={k:5 for k in METRICS})
            point=dict(model_hash='c'*64,**{'from':1025},through=2048,
                       results={g:dict(tasks=100,mean_absolute_log1p_error=scores) for g in ('future_all','future_unseen_geometry')})
            (old/'eval-000001024.json').write_text(json.dumps(point))
            (old/'model-000001024.json').write_text('{}')
            report=generate(data)
            self.assertEqual(report['series'],[])
            self.assertEqual(len(report['archives']),1)
            archive=json.loads((data/Path(report['archives'][0]['url']).relative_to('data')).read_text())
            self.assertEqual(archive['baseline'],'context baseline')
            self.assertEqual(archive['series'][0]['metrics']['cpu_ms']['future_all'],50)
            self.assertIn('Awaiting the first complete', (learning/'evolution.svg').read_text())
            scores['proof_baseline']={k:8 for k in METRICS}
            (new/'eval-000001024.json').write_text(json.dumps(point))
            latest.update(completed_evaluations=1)
            (learning/'latest.json').write_text(json.dumps(latest))
            report=generate(data)
            self.assertEqual(report['series'][0]['metrics']['cpu_ms']['future_all'],37.5)
            svg=(learning/'evolution.svg').read_text()
            self.assertIn('<circle cx="317.50"',svg)
            self.assertEqual(svg.count('>2,048</text>'),4)


if __name__=='__main__':unittest.main()
