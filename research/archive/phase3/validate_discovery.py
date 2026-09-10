#!/usr/bin/env python3
"""Independent durable-discovery and immutable-migration checks.

Positive fixtures are genuine identities for k=3, tested with target=3. The
production target114 parser must reject them. No fixture is a solution of114.
All process/failure fixtures run in temporary directories; migration is read-only.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import fcntl
import hashlib
import importlib.util
import io
import itertools
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
loader = importlib.util.spec_from_file_location('phase3_discovery_subject', ROOT/'campaign.py')
c = importlib.util.module_from_spec(loader)
loader.loader.exec_module(c)
KNOWN = [dict(type='hit', k=3, xyz=['1', '1', '1']),
         dict(type='hit', k=3, xyz=['4', '4', '-5'])]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def fixture_result(hits=None):
    hits = copy.deepcopy(KNOWN if hits is None else hits)
    return dict(hits=hits, verified=[sorted(map(int, h['xyz'])) for h in hits],
                incomplete=True, error='known k3 validation fixture')


def write_journal(directory, name='job-known.jsonl', suffix=''):
    folder = directory/'journals'
    folder.mkdir(exist_ok=True)
    path = folder/name
    with path.open('w') as stream:
        stream.write('\n'.join(json.dumps(h) for h in KNOWN)+'\n'+suffix)
        stream.flush()
        os.fsync(stream.fileno())
    return path


def parser_checks():
    text='[]\nnot json\n'+json.dumps(KNOWN[0])+'\n'+json.dumps(KNOWN[1])+'\n{"type":"hit",'
    hits, xyz=c.identity_hits(text, target=3)
    require(xyz==[[1,1,1],[-5,4,4]], 'known identities not recovered before torn line')
    require(c.identity_hits(text)==([],[]), 'production114 accepted a k3 fixture')
    false=copy.deepcopy(KNOWN[0]);false['k']=114
    require(c.identity_hits(json.dumps(false))==([],[]), 'false114 cube identity accepted')
    for bad_xyz in ([True,1,1], [1.0,1,1], ['1.0','1','1'], ['1','1'], ['1','1','1','0']):
        require(c.identity_hits(json.dumps(dict(type='hit',k=3,xyz=bad_xyz)),target=3)==([],[]),
                'noninteger or malformed triple accepted')
    return dict(genuine_k3_positive=True, production114_rejects_fixtures=True,
                false_identity_rejected=True, malformed_values_rejected=True, torn_tail_safe=True)


def persistence_checks():
    with tempfile.TemporaryDirectory(prefix='three-cubes-preserve-') as temp:
        directory=Path(temp)
        for result in (dict(hits=[],verified=[[1,1,1]]), dict(hits=[KNOWN[0]],verified=[]),
                       dict(hits=[],verified=[]), dict(hits=[KNOWN[0]],verified=[[2,2,2]])):
            try:
                c.preserve_discovery(directory,result,target=3)
            except ValueError:
                pass
            else:
                raise AssertionError('invalid paired discovery records accepted')
            require(not (directory/'SOLUTION.json').exists(), 'invalid aggregate persisted')
        c.preserve_discovery(directory,fixture_result(),target=3)
        paths=sorted((directory/'discoveries').glob('*.json'))
        require(len(paths)==2, 'two genuine identities did not get distinct durable files')
        before={p.name:p.read_bytes() for p in paths}
        c.preserve_discovery(directory,fixture_result(),target=3)
        require(before=={p.name:p.read_bytes() for p in paths}, 'idempotent recovery replaced first evidence')
        require(c.recover_journals(directory,target=3)==[(-5,4,4),(1,1,1)], 'discovery-only replay failed')
    return dict(pair_validation=True, content_addressed=True, idempotent=True, discovery_only_replay=True)


def recovery_checks():
    with tempfile.TemporaryDirectory(prefix='three-cubes-recovery-') as temp:
        directory=Path(temp)
        write_journal(directory,suffix='{"type":"hit","xyz":[')
        result=c.recover_journals(directory,target=3)
        require(result==[(-5,4,4),(1,1,1)], 'journal recovery failed')
        require(not (directory/'campaign.sqlite3').exists(), 'recovery created database state')
        require(json.loads((directory/'SOLUTION.json').read_text())['incomplete'] is True,
                'recovery claimed complete coverage')
        (directory/'discoveries/000-corrupt.json').write_text('{')
        with contextlib.redirect_stderr(io.StringIO()) as diagnostics:
            require(c.recover_journals(directory,target=3)==result, 'corrupt unrelated evidence hid valid hit')
        require('JOURNAL_RECOVERY_ERRORS' in diagnostics.getvalue(), 'corrupt evidence not reported')
        unreadable=directory/'journals/000-unreadable.jsonl';unreadable.write_text('')
        original_read=Path.read_text
        def read_with_error(path,*args,**kwargs):
            if path==unreadable:
                raise OSError('injected unreadable journal')
            return original_read(path,*args,**kwargs)
        with patch.object(Path,'read_text',read_with_error),contextlib.redirect_stderr(io.StringIO()):
            require(c.recover_journals(directory,target=3)==result, 'unreadable early file hid later hit')
    with tempfile.TemporaryDirectory(prefix='three-cubes-blocked-recovery-') as temp:
        directory=Path(temp);(directory/'discoveries').mkdir()
        (directory/'discoveries/bad.json').write_text('{')
        with contextlib.redirect_stderr(io.StringIO()):
            try:
                c.recover_journals(directory,target=3)
            except (ValueError,RuntimeError):
                pass
            else:
                raise AssertionError('unresolved corrupt evidence did not block restart')
    with tempfile.TemporaryDirectory(prefix='three-cubes-rename-failure-') as temp:
        directory=Path(temp);write_journal(directory)
        with patch.object(c.os,'replace',side_effect=OSError('injected pre-rename failure')), \
             contextlib.redirect_stderr(io.StringIO()):
            require(c.recover_journals(directory,target=3)==[(-5,4,4),(1,1,1)],
                    'persistence failure concealed verified journal identities')
        require(c.recover_journals(directory,target=3)==[(-5,4,4),(1,1,1)], 'post-crash rename recovery failed')
        require(len(list((directory/'discoveries').glob('*.json')))==2, 'recovered identities not persisted')
    return dict(torn_journal_recovery=True, no_database_required=True,
                unrelated_corruption_does_not_hide_hit=True, unresolved_errors_block=True,
                atomic_rename_failure_recoverable=True, incomplete_coverage_preserved=True)


def startup_checks():
    with tempfile.TemporaryDirectory(prefix='three-cubes-startup-') as temp:
        directory=Path(temp);write_journal(directory)
        original_recovery=c.recover_journals
        argv=['campaign.py','run','--directory',temp,'--hours','.001','--workers','1']
        with patch.object(sys,'argv',argv), \
             patch.object(c,'recover_journals',side_effect=lambda path:original_recovery(path,target=3)), \
             patch.object(c,'connect',side_effect=AssertionError('database opened before discovery recovery')), \
             patch.object(c,'source_identity',side_effect=AssertionError('sources checked before recovery')), \
             patch.object(c,'execute',side_effect=AssertionError('work dispatched after recovery')), \
             contextlib.redirect_stdout(io.StringIO()):
            c.main()
        require(json.loads((directory/'recovery-status.json').read_text())['state']=='solution_found',
                'startup did not stop on recovered identity')
        with (directory/'writer.lock').open('a+') as lock:
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            with patch.object(sys,'argv',argv), patch.object(c,'recover_journals') as recovery, \
                 contextlib.redirect_stderr(io.StringIO()):
                try:
                    c.main()
                except SystemExit as exc:
                    require(exc.code==2,'wrong lock rejection exit')
                else:
                    raise AssertionError('second writer accepted')
                recovery.assert_not_called()
    return dict(recovery_before_database_and_source_checks=True, no_dispatch_after_recovery=True,
                writer_lock_precedes_recovery=True)


def cleanup_check():
    """Synthetic complete no-hit result tests bookkeeping, not native coverage."""
    with tempfile.TemporaryDirectory(prefix='three-cubes-cleanup-') as temp:
        directory=Path(temp);journal=directory/'journals/job-fixture.jsonl'
        def mock_execute(job,spec,*args,**kwargs):
            journal.parent.mkdir(exist_ok=True);journal.write_text('{}\n')
            stats={field:0 for field in c.COUNTERS.values()}
            stats.update(exposure_sum=0.0,candidates=job['count']*(spec['thi']-spec['tlo']+1))
            stats['outside_shell']=stats['candidates']
            return dict(stats=stats,hits=[],verified=[],elapsed=.01,journal=str(journal))
        original_unlink=Path.unlink
        def fail_cleanup(path,*args,**kwargs):
            if path==journal:
                raise OSError('injected journal cleanup failure')
            return original_unlink(path,*args,**kwargs)
        argv=['campaign.py','run','--directory',temp,'--hours','.001','--workers','1','--max-jobs','1']
        with patch.object(sys,'argv',argv),patch.object(c,'source_identity',return_value={}), \
             patch.object(c,'execute',side_effect=mock_execute),patch.object(Path,'unlink',fail_cleanup), \
             patch.object(c,'power_state',return_value=dict(percent=100,on_ac=True,discharging=False,available=True)), \
             patch.object(c,'STOP',False),contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()) as diagnostics:
            c.main()
        db=sqlite3.connect(directory/'campaign.sqlite3')
        try:
            require(db.execute('SELECT status FROM jobs').fetchone()[0]=='complete',
                    'cleanup failure invalidated committed job')
            require(db.execute("SELECT count(*) FROM events WHERE kind='job_failure'").fetchone()[0]==0,
                    'cleanup warning became worker failure')
        finally:
            db.close()
        require(journal.exists(),'failed cleanup did not retain journal')
        require('JOURNAL_CLEANUP_WARNING' in diagnostics.getvalue(),'cleanup error not reported')
    return dict(committed_job_stays_complete=True, retained_journal=True, warning_reported=True,
                fixture_scope='Injected synthetic no-hit statistics test bookkeeping only; no mathematical search was performed.')


def fake_worker(root):
    binary=root/'bin/offset_worker';binary.parent.mkdir(parents=True)
    body=f'''#!{sys.executable}
import json,os,time
records={KNOWN!r}
for record in records:
    print(json.dumps(record),flush=True)
os.fsync(1)
ready=os.environ.get("THREE_CUBES_TEST_READY")
if ready:
    with open(ready,"w") as out:
        out.write("hit fsynced")
        out.flush()
        os.fsync(out.fileno())
if os.environ.get("THREE_CUBES_TEST_SLEEP"):
    time.sleep(10)
print('{{"type":"hit",',flush=True)
os.fsync(1)
os._exit(19)
'''
    binary.write_text(body);binary.chmod(0o700)


def process_checks():
    with tempfile.TemporaryDirectory(prefix='three-cubes-process-') as temp:
        directory=Path(temp);worker_root=directory/'worker';fake_worker(worker_root)
        job=dict(id=7,start=0,count=1,policy='adaptive');spec=c.contexts()[0]
        original_parser=c.identity_hits
        with patch.object(c,'ROOT',worker_root),patch.object(c,'NICE_PREFIX',[]), \
             patch.object(c,'identity_hits',side_effect=lambda output,target=114:original_parser(output,target=3)):
            for _ in range(2):
                try:
                    c.execute(job,spec,1142,2,journal_directory=directory/'journals')
                except c.WorkerFailure as exc:
                    require(exc.partial['verified']==[[1,1,1],[-5,4,4]], 'nonzero worker exit lost identities')
                    require(exc.partial['incomplete'] is True, 'failed process claimed coverage')
                else:
                    raise AssertionError('nonzero fake worker accepted as complete')
            existing={p.name:p.read_bytes() for p in (directory/'journals').glob('*.jsonl')}
            require(len(existing)==2, 'retry reused or overwrote an attempt journal')
            with patch.dict(os.environ,{'THREE_CUBES_TEST_SLEEP':'1'}):
                try:
                    c.execute(job,spec,1142,.3,journal_directory=directory/'journals')
                except c.WorkerFailure as exc:
                    require(exc.timed_out and len(exc.partial['verified'])==2, 'timeout lost fsynced identities')
                else:
                    raise AssertionError('sleeping worker did not time out')
            require(all((directory/'journals'/name).read_bytes()==data for name,data in existing.items()),
                    'later retry modified an earlier attempt')
    with tempfile.TemporaryDirectory(prefix='three-cubes-killed-controller-') as temp:
        directory=Path(temp);worker_root=directory/'worker';fake_worker(worker_root)
        ready=directory/'ready';runner=directory/'controller_fixture.py'
        runner.write_text(f'''import sys
from pathlib import Path
sys.path.insert(0,{str(ROOT)!r})
import campaign
campaign.ROOT=Path({str(worker_root)!r})
campaign.execute(dict(id=9,start=0,count=1,policy="adaptive"),campaign.contexts()[0],1142,15,journal_directory=Path({str(directory/'journals')!r}))
''')
        env=dict(os.environ,THREE_CUBES_TEST_SLEEP='1',THREE_CUBES_TEST_READY=str(ready))
        process=subprocess.Popen([sys.executable,str(runner)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                 env=env,start_new_session=True)
        try:
            deadline=time.monotonic()+5
            while not ready.exists() and process.poll() is None and time.monotonic()<deadline:
                time.sleep(.01)
            require(ready.exists(),'fixture did not reach hit-fsync boundary')
            os.killpg(process.pid,signal.SIGKILL)
            process.wait(timeout=5)
            require(c.recover_journals(directory,target=3)==[(-5,4,4),(1,1,1)],
                    'process-group kill after hit fsync lost journal discovery')
        finally:
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
            process.communicate()
    return dict(actual_nonzero_worker_exit=True, actual_timeout=True,
                attempt_journals_unique_and_immutable=True, killed_controller_and_worker_after_fsync=True,
                durable_replay_without_database=True,
                fixture_scope='Actual temporary processes emit genuine k3 identities. Routing parser target3 is injected only in this test; no114 discovery is claimed.')


def migration_checks(old_path,new_path):
    def connect_read(path):
        db=sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro',uri=True)
        db.row_factory=sqlite3.Row;db.execute('BEGIN');return db
    old,new=connect_read(old_path),connect_read(new_path)
    try:
        old_max=old.execute('SELECT max(id) FROM jobs').fetchone()[0]
        require(old.execute("SELECT count(*) FROM jobs WHERE status!='complete'").fetchone()[0]==0,
                'original ledger is not fully complete')
        epoch=int(new.execute("SELECT value FROM meta WHERE key='epoch_start'").fetchone()[0])
        require(epoch==old_max,'migration source-epoch boundary changed')
        h=hashlib.sha256();count=0
        for left,right in itertools.zip_longest(old.execute('SELECT * FROM jobs ORDER BY id'),
                new.execute('SELECT * FROM jobs WHERE id<=? ORDER BY id',(epoch,))):
            require(left is not None and right is not None and dict(left)==dict(right),'historical job changed')
            h.update((json.dumps(dict(left),sort_keys=True,separators=(',',':'))+'\n').encode());count+=1
        certificate=json.loads(new.execute("SELECT value FROM meta WHERE key='migration'").fetchone()[0])
        require(h.hexdigest()==certificate['historical_jobs_sha256'],'historical hash does not match certificate')
        cursor_sql='SELECT key,spec,cursor FROM contexts ORDER BY key'
        old_cursors=[dict(r) for r in old.execute(cursor_sql)]
        require(old_cursors==[dict(r) for r in new.execute(cursor_sql)],'fresh migration changed a cursor or geometry')
        require(old_cursors==certificate['cursors'],'certificate changed original cursor values')
        old_totals=[dict(r) for r in old.execute('SELECT * FROM totals ORDER BY key')]
        require(old_totals==[dict(r) for r in new.execute('SELECT * FROM totals ORDER BY key')], 'migration changed totals')
        require(old_totals==certificate['totals'],'certificate changed original totals')
        require([dict(r) for r in old.execute('SELECT * FROM solutions ORDER BY id')]
                ==[dict(r) for r in new.execute('SELECT * FROM solutions ORDER BY id')], 'solution history changed')
        old_meta={r['key']:json.loads(r['value']) for r in old.execute('SELECT * FROM meta')}
        archive=json.loads(new.execute("SELECT value FROM meta WHERE key='prior_epoch_metadata'").fetchone()[0])
        require(archive==old_meta,'prior metadata was not archived exactly')
        new_config=json.loads(new.execute("SELECT value FROM meta WHERE key='config'").fetchone()[0])
        require(new_config['contexts']==old_meta['config']['contexts'] and
                new_config['permutation_seed']==old_meta['config']['permutation_seed'],'input mapping changed')
        require(new.execute('SELECT count(*) FROM policies').fetchone()[0]==0 and
                new.execute('SELECT count(*) FROM allocations').fetchone()[0]==0 and
                new.execute('SELECT sum(elapsed) FROM contexts').fetchone()[0]==0,'new timing epoch not reset')
        return dict(passed=True,scope='Read-only comparison before new dispatch; exact immutable historical records.',
                    old_database=str(Path(old_path).resolve()),new_database=str(Path(new_path).resolve()),
                    historical_complete_jobs=count,epoch_start=epoch,historical_jobs_sha256=h.hexdigest(),
                    all_context_cursors_preserved=len(old_cursors),totals_preserved=True,
                    prior_metadata_archived=True,solution_records_preserved=True,timing_only_reset=True,
                    recorded_new_sources_match_current=new_config['sources']==c.source_identity())
    finally:
        old.close();new.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--migration-old',type=Path)
    parser.add_argument('--migration-new',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'runs/discovery-validation.json')
    args=parser.parse_args()
    require(bool(args.migration_old)==bool(args.migration_new),'both migration paths required')
    started=time.monotonic();before=hashlib.sha256((ROOT/'campaign.py').read_bytes()).hexdigest()
    evidence=dict(parser=parser_checks(),persistence=persistence_checks(),recovery=recovery_checks(),
                  startup=startup_checks(),processes=process_checks(),cleanup=cleanup_check())
    if args.migration_old:
        evidence['migration']=migration_checks(args.migration_old,args.migration_new)
    after=hashlib.sha256((ROOT/'campaign.py').read_bytes()).hexdigest()
    require(before==after,'controller source changed during validation; rerun against frozen files')
    evidence.update(passed=True,controller_sha256=after,validator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    elapsed_seconds=time.monotonic()-started,
                    limits='Finite regressions, not formal verification or protection against all hardware/power-loss failures. Positive tests use genuinek3 identities, never a claimed114 solution.')
    evidence['sources']={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted([p for p in ROOT.iterdir() if p.is_file() and p.suffix in ('.py','.c')]
                           +[p for p in (ROOT/'bin').glob('*') if p.is_file()])}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(dict(passed=True,controller_sha256=after,elapsed_seconds=evidence['elapsed_seconds'],
                         migration=evidence.get('migration'),evidence=str(args.output)),indent=2))


if __name__=='__main__':
    main()
