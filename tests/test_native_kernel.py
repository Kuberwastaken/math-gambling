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

    def test_rejects_invalid_task_without_receipt(self):
        task=core.make_task('c00',0)
        for change in ({'row':'01'},{'row':'999999999999999'},{'block':True},{'version':True},{'context':'c99'},{'row':'-128'},{'extra':1}):
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
