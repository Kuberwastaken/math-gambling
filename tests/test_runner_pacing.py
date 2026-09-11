import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import runner
from search_core import make_task, run_task, canonical_json

class PacingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.out=Path(self.temp.name)
        self.person={'name':'Fixture','github':'fixture'}
        self.db=runner.open_state(self.out,self.person)
        with contextlib.redirect_stdout(io.StringIO()):
            for i in range(12):
                result=run_task(make_task('c00',i*128))
                self.db.execute('INSERT INTO tasks(id,task,result) VALUES(?,?,?)',(result['id'],canonical_json(result['task']),canonical_json(result)))
                self.db.commit();runner.write_bank(self.out,self.db,self.person,force=True,bank_every=1)
        self.clock=1000;self.posts=0
    def tearDown(self): self.db.close();self.temp.cleanup()
    def external(self,command,**kwargs):
        if command[1:3]==['issue','list']: return subprocess.CompletedProcess(command,0,'[]','')
        self.posts+=1
        body=json.loads(kwargs['input']);self.assertEqual(json.loads(body['body'])['schema'],'math-gambling-bank-v1')
        return subprocess.CompletedProcess(command,0,'HTTP/2.0 201 Created\nContent-Type: application/json\n\n'+json.dumps({'html_url':f'https://github.com/fixture/repo/issues/{self.posts}'}),'')
    def run_at(self,clock,last=-float('inf'),external=None):
        self.clock=clock
        with patch.object(runner.time,'time',return_value=clock),patch.object(runner.time,'monotonic',return_value=clock),patch.object(runner.subprocess,'run',side_effect=external or self.external),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            return runner.maybe_submit(self.db,'fixture/repo',last)
    def test_twelve_banks_have_110_seconds_of_pacing_and_restart_cannot_skip_wait(self):
        for i in range(12):
            self.run_at(1000+i*10)
            self.run_at(1001+i*10)
            self.assertEqual(self.posts,i+1)
        self.assertEqual(runner.bank_queue(self.db)['pending'],0)
    def test_rate_limit_persists_and_repeated_failures_back_off(self):
        def limited(command,**kwargs):
            if command[1:3]==['issue','list']: return self.external(command,**kwargs)
            self.posts+=1
            return subprocess.CompletedProcess(command,1,'HTTP/2.0 429 Too Many Requests\nRetry-After: 90\n\n{}','rate limited')
        self.run_at(1000,external=limited)
        self.assertEqual(runner.bank_queue(self.db)['uncertain'],0)
        self.run_at(1089,external=limited);self.assertEqual(self.posts,1)
        self.run_at(1090,external=limited);self.assertEqual(self.posts,2)
        self.assertEqual(float(self.db.execute("SELECT value FROM meta WHERE key='submit_after'").fetchone()[0]),1210)
        self.run_at(1209);self.assertEqual(self.posts,2)
        self.run_at(1210);self.assertEqual(self.posts,3)
        self.assertEqual(self.db.execute("SELECT value FROM meta WHERE key='submit_failures'").fetchone()[0],'0')
    def test_primary_reset_header_overrides_short_retry(self):
        with patch.object(runner.time,'time',return_value=1000):
            self.assertEqual(runner.submission_delay(self.db,True,{'retry-after':'1','x-ratelimit-reset':'1600','x-ratelimit-remaining':'0'}),600)
    def test_ambiguous_create_is_not_retried(self):
        def ambiguous(command,**kwargs):
            if command[1:3]==['issue','list']: return self.external(command,**kwargs)
            self.posts+=1;return subprocess.CompletedProcess(command,0,'unexpected response','')
        self.run_at(1000,external=ambiguous)
        self.assertEqual(runner.bank_queue(self.db)['uncertain'],1)
        original=self.db.execute("SELECT id FROM banks WHERE submitted LIKE 'uncertain;%' ").fetchone()[0]
        self.run_at(1060)
        self.assertTrue(self.db.execute('SELECT submitted FROM banks WHERE id=?',(original,)).fetchone()[0].startswith('uncertain;'))

if __name__=='__main__':unittest.main()
