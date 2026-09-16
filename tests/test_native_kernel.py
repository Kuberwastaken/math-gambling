"""Optional compiled-kernel gate; CI builds Rust before running this suite."""
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import unittest
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parent)]
import search_core as core
from native_kernel import NativeKernel, binary_path
from test_shell_pruning import corpus

@unittest.skipUnless(binary_path().is_file(), 'build Rust with tools/build_native.py')
class NativeTests(unittest.TestCase):
    def test_fixed_and_random_corpus_exact_equality(self):
        rng=random.Random(114)
        tasks=corpus()+[core.make_task(c['id'],rng.randrange(int(c['rowTasks']))*128,rng.randrange(c['blocks'])) for c in core.CONTEXTS for _ in range(8)]
        native=NativeKernel()
        try:
            for task in tasks:
                self.assertEqual(native.run(task),core.run_task(task),core.task_id(task))
        finally:native.close()

    def test_engine_v2_and_cross_target_tasks_match_python(self):
        import multi_target as mt
        rng=random.Random(2026)
        native=NativeKernel()
        try:
            for c in core.CONTEXTS[::4]:
                task=core.make_task(c['id'],rng.randrange(int(c['rowTasksV2']))*1024,rng.randrange(c['blocks']),2)
                self.assertEqual(native.run(task),core.run_task(task),core.task_id(task))
            for k in (627,390,975,3):
                for cid in mt.ELL1_CONTEXTS[::9]:
                    c=core.CONTEXT_BY_ID[cid]
                    task=mt.make_target_task(k,cid,rng.randrange(int(c['rowTasks']))*128,rng.randrange(c['blocks']))
                    self.assertEqual(native.run(task),mt.run_target_task(task),mt.target_task_id(task))
        finally:native.close()

    def test_rejects_invalid_task_without_receipt(self):
        task=core.make_task('c00',0)
        for change in ({'row':'01'},{'row':'999999999999999'},{'block':True},{'version':True},{'context':'c99'},{'row':'-128'},{'extra':1},
                       {'version':2},{'version':2,'engine':'mg114-offset-v2','row':'128'},{'engine':'mg114-offset-v1','version':2},
                       {'engine':'mg115-offset-v1'},{'engine':'mg627-offset-v1','context':'c27'},{'engine':'mg0627-offset-v1'}):
            p=subprocess.run([str(binary_path())],input=json.dumps({**task,**change})+'\n',text=True,capture_output=True)
            self.assertNotEqual(p.returncode,0)
            self.assertEqual(p.stdout,'')

    def test_spawn_runner_with_rust_has_durable_receipt(self):
        import tempfile
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as out:
            p=subprocess.run([sys.executable,'tools/runner.py','--kernel','rust','--offline','--name','Native fixture','--github','native-fixture','--workers','1','--max-tasks','2','--minutes','1','--output',out],cwd=root,text=True,capture_output=True,timeout=60)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            results=[json.loads(x) for x in (Path(out)/'results.jsonl').read_text().splitlines()]
            self.assertEqual(len(results),2)
            for result in results:self.assertEqual(result,core.run_task(result['task']))

if __name__=='__main__':unittest.main()
