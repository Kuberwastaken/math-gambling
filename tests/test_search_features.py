from pathlib import Path
import random,sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from search_core import *
from search_features import norm_bounds,certified_empty,vector

class FeatureTests(unittest.TestCase):
    def test_bounds_enclose_every_generator_at_boundaries_and_random_tiles(self):
        rng=random.Random(914)
        for c in CONTEXTS:
            rows=[0,(int(c['totalRows'])-1)//128*128,rng.randrange(int(c['rowTasks']))*128]
            for row in rows:
                task=make_task(c['id'],row,rng.randrange(c['blocks']));lo,hi=norm_bounds(task)
                for j in range(row,min(row+128,int(c['totalRows']))):
                    width=2*c['radius']+1;b=j%width-c['radius'];cc=j//width-c['radius'];base=offset_base(c['ell'],b,cc)
                    t0=c['tlo']+16*task['block']
                    for t in range(t0,min(t0+16,c['thi']+1)):
                        n=norm(base+c['ell']*t,b,cc)*SCALE**3
                        self.assertLessEqual(lo,n);self.assertLessEqual(n,hi)
                if certified_empty(task):self.assertEqual(run_task(task)['counters']['curves'],0)
                self.assertTrue(all(math.isfinite(x) for x in vector(task)))
