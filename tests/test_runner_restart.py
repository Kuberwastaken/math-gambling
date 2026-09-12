"""Resume old checkpoints without re-entering or silently reassigning attribution."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import runner
import search_core as core

PERSON={'name':'Restart Δ fixture','github':'RestartExample','url':'https://example.org/profile'}

class RunnerRestartTests(unittest.TestCase):
    def seed(self,out):
        db=runner.open_state(out,PERSON)
        task=core.make_task('c05',128)
        result=core.run_task(task)
        db.execute('INSERT INTO tasks(id,task,result) VALUES(?,?,?)',
                   (result['id'],core.canonical_json(task),core.canonical_json(result)))
        db.commit();runner.write_bank(out,db,PERSON,force=True);db.close()

    def invoke(self,out,*extra):
        return subprocess.run([sys.executable,str(ROOT/'tools/runner.py'),'--offline','--workers','1',
                               '--minutes','1','--max-tasks','1','--output',str(out),*extra],
                              stdin=subprocess.DEVNULL,capture_output=True,text=True,encoding='utf-8',timeout=60)

    def test_existing_profile_is_inherited_and_bank_bytes_preserved(self):
        with tempfile.TemporaryDirectory(prefix='mg restart ') as tmp:
            out=Path(tmp);self.seed(out)
            banks={p.name:p.read_bytes() for p in (out/'banks').glob('*.json')}
            with closing(sqlite3.connect(out/'checkpoint.sqlite3')) as db:
                identity=db.execute("SELECT value FROM meta WHERE key='identity'").fetchone()[0]
            for extra in ((),('--github','@restartexample')):
                result=self.invoke(out,*extra)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertIn('Resuming saved attribution',result.stdout)
                self.assertEqual(runner.saved_identity(out),PERSON)
            for name,raw in banks.items():self.assertEqual((out/'banks'/name).read_bytes(),raw)
            for p in (out/'banks').glob('*.json'):self.assertEqual(json.loads(p.read_bytes())['contributor'],PERSON)
            with closing(sqlite3.connect(out/'checkpoint.sqlite3')) as db:
                self.assertEqual(db.execute("SELECT value FROM meta WHERE key='identity'").fetchone()[0],identity)

    def test_different_identity_rejected_without_touching_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);self.seed(out)
            before={p.name:p.read_bytes() for p in (out/'banks').glob('*.json')}
            for option,value in (('--name','Someone else'),('--github','someone-else'),('--url','https://other.example')):
                result=self.invoke(out,option,value)
                self.assertNotEqual(result.returncode,0)
                self.assertIn('Do not delete',result.stderr)
            self.assertEqual({p.name:p.read_bytes() for p in (out/'banks').glob('*.json')},before)

    def test_login_capitalization_and_account_mismatch(self):
        def args():return argparse.Namespace(name=None,github=None,url=None,login=False,submit=True)
        with patch.object(runner,'github_identity',return_value='restartexample'):
            self.assertEqual(runner.resolve_contributor(args(),argparse.ArgumentParser(),PERSON),PERSON)
        with patch.object(runner,'github_identity',return_value='someone-else'),self.assertRaises(SystemExit):
            runner.resolve_contributor(args(),argparse.ArgumentParser(),PERSON)

    def test_invalid_engine_and_corrupt_checkpoint_do_not_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);self.seed(out)
            with closing(sqlite3.connect(out/'checkpoint.sqlite3')) as db:
                db.execute("UPDATE meta SET value=? WHERE key='identity'",(json.dumps({'engine':'another-engine','contributor':PERSON}),));db.commit()
            result=self.invoke(out)
            self.assertNotEqual(result.returncode,0);self.assertIn('different search engine',result.stderr)
            with closing(sqlite3.connect(out/'checkpoint.sqlite3')) as db:
                db.execute("DELETE FROM meta WHERE key='identity'");db.commit()
            result=self.invoke(out,'--name',PERSON['name'],'--github',PERSON['github'])
            self.assertNotEqual(result.returncode,0);self.assertIn('Cannot read saved checkpoint attribution',result.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);p=out/'checkpoint.sqlite3';p.write_bytes(b'not a SQLite database')
            result=self.invoke(out)
            self.assertNotEqual(result.returncode,0);self.assertIn('Keep the checkpoint',result.stderr)
            self.assertEqual(p.read_bytes(),b'not a SQLite database')

    @unittest.skipIf(os.name=='nt','POSIX terminal process-group Ctrl+C; resume tests above run on all platforms')
    def test_real_ctrl_c_group_drain_then_restart_without_identity_flags(self):
        with tempfile.TemporaryDirectory(prefix='mg interrupt ') as tmp:
            out=Path(tmp)
            command=[sys.executable,str(ROOT/'tools/runner.py'),'--offline','--workers','1','--minutes','1',
                     '--max-tasks','4096','--bank-every','1','--name',PERSON['name'],'--github',PERSON['github'],
                     '--url',PERSON['url'],'--output',str(out)]
            with (out/'first.log').open('w',encoding='utf-8') as log:
                process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,stdin=subprocess.DEVNULL)
                try:
                    deadline=time.monotonic()+30
                    while not list((out/'banks').glob('bank-*.json')) and process.poll() is None and time.monotonic()<deadline:time.sleep(.02)
                    self.assertIsNone(process.poll(),(out/'first.log').read_text())
                    self.assertTrue(list((out/'banks').glob('bank-*.json')),'first task must finish before interrupt')
                    os.killpg(process.pid,signal.SIGINT)
                    self.assertEqual(process.wait(timeout=30),0,(out/'first.log').read_text())
                finally:
                    if process.poll() is None:os.killpg(process.pid,signal.SIGKILL);process.wait()
            self.assertEqual(json.loads((out/'status.json').read_text())['state'],'stopped')
            banks={p.name:p.read_bytes() for p in (out/'banks').glob('*.json')}
            self.assertEqual(runner.saved_identity(out),PERSON)
            resumed=self.invoke(out)
            self.assertEqual(resumed.returncode,0,resumed.stdout+resumed.stderr)
            self.assertEqual(json.loads((out/'status.json').read_text())['completed_this_run'],1)
            for name,raw in banks.items():self.assertEqual((out/'banks'/name).read_bytes(),raw)

if __name__=='__main__':unittest.main()
