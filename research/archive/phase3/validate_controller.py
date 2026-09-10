#!/usr/bin/env python3
"""Reproducible controller fault tests; standard library only.

Temporary databases and locks are isolated from real campaigns. Positive rescue
routing tests inject arithmetic-verifier acceptance: (1,1,1) is NOT a solution
of 114. No synthetic hit is saved to a production solution journal.
"""
from __future__ import annotations
import argparse
import copy
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback
from unittest.mock import patch

import campaign as controller

ROOT = Path(__file__).resolve().parent


def require(condition, explanation):
    if not condition:
        raise AssertionError(explanation)


def hashes():
    names = ['validate_controller.py', 'campaign.py', 'offset_worker.c', 'online_model.py','verify_domain.py',
             'bin/offset_worker', '../bin/libpari.dylib', 'checker.c']
    return {name:controller.digest(ROOT/name) for name in names if (ROOT/name).exists()}


def job_for(spec, count=64, start=0, policy='fixed'):
    return dict(id=1, context=spec['key'], start=start, count=count, policy=policy)


def protocol_tests(spec):
    job = job_for(spec)
    baseline = controller.execute(job, spec, 114, 10)
    require(baseline['stats']['candidates'] == job['count']*(spec['thi']-spec['tlo']+1), 'Real worker count mismatch')
    mutations = [('complete', False), ('k', 3), ('mode', 'curve'), ('version', 999),
                 ('policy', 'adaptive'), ('candidates', 0), ('curves', -1),
                 ('start', .9), ('permutation_stride', 0),
                 ('quotient_points', baseline['stats']['quotient_points']+1)]
    checks = {}
    for field, value in mutations:
        stats = copy.deepcopy(baseline['stats'])
        stats[field] = value
        response = subprocess.CompletedProcess([], 0, json.dumps(stats)+'\n', '')
        with patch.object(controller.subprocess, 'run', return_value=response):
            try:
                controller.execute(job, spec, 114, 10)
            except Exception as exc:
                checks[field] = dict(rejected=True, error=str(exc))
            else:
                raise AssertionError(f'Malformed {field} was accepted')
    for name, suffix in [('duplicate_stats', json.dumps(baseline['stats'])),
                         ('unknown_record', '{"type":"unknown"}'),
                         ('malformed_record', '{not-json'), ('wrong_json_type', '[]')]:
        response = subprocess.CompletedProcess([], 0, json.dumps(baseline['stats'])+'\n'+suffix+'\n', '')
        with patch.object(controller.subprocess, 'run', return_value=response):
            try:
                controller.execute(job, spec, 114, 10)
            except Exception as exc:
                checks[name] = dict(rejected=True, error=str(exc))
            else:
                raise AssertionError(f'{name} was accepted')
    return dict(real_worker_passed=True, mutations=checks,
                actual_discoveries=baseline['verified'])


def reservation_tests(directory, spec):
    db = controller.connect(directory/'reservation.sqlite3')
    identity = {'controller_test': 'fixed'}
    try:
        controller.initialize(db, [spec], identity, 114)
        original = controller.choose_job(db, {}, 1, 1000)
        with db:
            db.execute("UPDATE jobs SET status='running',policy='fixed',attempts=1 WHERE id=?", (original['id'],))
        controller.initialize(db, [spec], identity, 114)
        recovered = controller.choose_job(db, {}, 1, 1000)
        require(tuple(original[k] for k in ('id','start','count')) ==
                tuple(recovered[k] for k in ('id','start','count')), 'Interrupted range changed')
        controller.record_failure(db, recovered, subprocess.TimeoutExpired('injected-worker', .01))
        intervals = [(r['start'],r['count']) for r in db.execute('SELECT start,count FROM jobs ORDER BY start')]
        require(intervals == [(0,500),(500,500)], 'Timeout split has overlap or omission')
        split_audit = controller.audit(db)
        first = controller.choose_job(db, {}, 1, 1000)
        first['policy'] = 'fixed'
        actual = controller.execute(first, spec, 114, 10)
        controller.record_success(db, first, actual)
        second = controller.choose_job(db, {}, 1, 1000)
        require((second['start'],second['count']) == (500,500), 'Pending second half skipped')
        final_audit = controller.audit(db)
        try:
            controller.initialize(db, [spec], {'controller_test':'changed'}, 114)
        except ValueError:
            pass
        else:
            raise AssertionError('Changed identity was accepted')
        return dict(interrupted_range_preserved=True, timeout_split=intervals,
                    split_audit=split_audit, pending_second_half_selected=True,
                    changed_identity_rejected=True, final_audit=final_audit,
                    actual_discoveries=actual['verified'])
    finally:
        db.close()


def rescue_tests(spec):
    # The mocked acceptance verifies routing only, never mathematical correctness.
    line = json.dumps({'type':'hit','k':114,'xyz':['1','1','1']})+'\n'
    scenarios = [('reject_false_identity', line, False, False),
                 ('nonzero_exit', line, False, True), ('timeout_bytes', line, True, True),
                 ('bad_json_type_after_hit', line+'[]\n', False, True),
                 ('truncated_last_line', line+'{"type":', True, True)]
    results = {}
    for name, output, timeout, inject in scenarios:
        response = dict(side_effect=subprocess.TimeoutExpired('injected-worker', 1, output=output.encode())) if timeout else dict(
            return_value=subprocess.CompletedProcess([],1,output,'Injected worker failure'))
        with patch.object(controller.subprocess, 'run', **response):
            with patch.object(controller, 'sum', (lambda values:114) if inject else sum, create=True):
                try:
                    controller.execute(job_for(spec), spec, 114, 1)
                except controller.WorkerFailure as exc:
                    require(exc.partial is not None, f'{name} lost captured output')
                    count = len(exc.partial['verified'])
                    require(count == int(inject), f'{name} rescue result incorrect')
                    require(exc.timed_out == timeout, f'{name} timeout classification incorrect')
                    results[name] = dict(passed=True, injected_verifier=inject,
                                         routed_records=count, timed_out=exc.timed_out)
                else:
                    raise AssertionError('Failed worker incorrectly completed')
    return dict(warning='Injected positive routing tests are not solutions of 114.', scenarios=results)


def cli_args(directory, jobs=1):
    return [sys.executable, str(ROOT/'campaign.py'), 'run', '--directory', str(directory),
            '--max-jobs', str(jobs), '--workers', '2', '--hours', '.001']


def writer_lock_test(directory):
    directory.mkdir()
    with (directory/'writer.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        second = subprocess.run(cli_args(directory), capture_output=True, text=True, timeout=15)
        require(second.returncode != 0 and 'already has an active writer' in second.stderr,
                'Second writer was not rejected by the held lock')
        require(not (directory/'campaign.sqlite3').exists(), 'Blocked writer modified the database')
    released = subprocess.run(cli_args(directory), capture_output=True, text=True, timeout=15)
    require(released.returncode == 0, 'Released lock prevented subsequent run: '+released.stderr)
    state = json.loads((directory/'status.json').read_text())
    require(state['audit']['complete_tiles'] == 1 and state['audit']['unfinished_tiles'] == 0,
            'Post-lock run did not complete its one work unit')
    return dict(second_writer_rejected=True, blocked_writer_created_no_database=True,
                lock_release_allows_run=True, audit=state['audit'])


def real_resume_test(directory):
    for stage in range(2):
        result = subprocess.run(cli_args(directory,4), capture_output=True, text=True, timeout=15)
        require(result.returncode == 0, f'CLI stage {stage} failed: '+result.stderr+result.stdout)
    state = json.loads((directory/'status.json').read_text())
    require(state['audit']['complete_tiles'] == 8 and state['audit']['unfinished_tiles'] == 0,
            'Resumed CLI failed to complete eight disjoint jobs')
    audit = subprocess.run([sys.executable,str(ROOT/'campaign.py'),'audit','--directory',str(directory)],
                           capture_output=True,text=True,timeout=15)
    require(audit.returncode == 0, 'Independent CLI audit failed: '+audit.stderr)
    return dict(audit=json.loads(audit.stdout), totals=state['totals'], actual_discoveries=state['solutions'])


def offset_integration():
    results=[]
    for spec in controller.contexts():
        if spec['low']!=0 or spec['shell_index']!=0:
            continue
        compared=[controller.execute(job_for(spec,4,0,policy),spec,1142,10) for policy in ('fixed','adaptive')]
        for field in ['candidates','outside_shell','rejected_signed','curves','quotient_points','exact_tests','hits','zero_norm','invalid_d','unsupported_D','noninvertible_C','covered','exposure_sum']:
            require(compared[0]['stats'][field]==compared[1]['stats'][field],f'Policies disagree on {field}')
        require(compared[0]['verified']==compared[1]['verified'],'Policies disagree on hits')
        results.append(dict(ell=spec['ell'],shape=spec['shape_index'],passed=True,stats=compared[0]['stats']))
    require(len(results)==9,'Missing offset geometry')
    return results


def scheduling_tests(directory):
    specs=controller.contexts()
    db=controller.connect(directory/'scheduling.sqlite3')
    controller.initialize(db,specs,{'test':'scheduling'},1142)
    try:
        counts={}
        with patch.object(controller,'learning_gate',return_value=None):
            for _ in range(243):
                job=controller.choose_job(db,counts,1,2)
                counts[job['context']]=counts.get(job['context'],0)+1
                with db:db.execute("UPDATE jobs SET status='running' WHERE id=?",(job['id'],))
        require(len(counts)==81 and set(counts.values())=={3},'Bootstrap failed to cover all81 arms three times')
        with db:
            db.execute("DELETE FROM jobs")
            db.execute("UPDATE contexts SET cursor=0")
            for spec in specs:
                db.execute("INSERT INTO policies VALUES(?,'adaptive',3,0,100)",(spec['key'],))
        strategies={}
        def scores(available,pending):return {v['key']:100. if v['key']==specs[0]['key'] else 1. for v in available}
        with patch.object(controller,'learning_gate',return_value={'enable_model':True}),patch.object(controller.MODEL,'scores',side_effect=scores):
            for _ in range(100):
                job=controller.choose_job(db,{},1,2)
                st=job['strategy'];strategies[st]=strategies.get(st,0)+1
                with db:
                    db.execute("UPDATE jobs SET status='complete',elapsed=1 WHERE id=?",(job['id'],))
                    db.execute("UPDATE contexts SET elapsed=elapsed+1 WHERE key=?",(job['context'],))
                    db.execute("INSERT INTO allocations VALUES(?,1,1) ON CONFLICT(strategy) DO UPDATE SET elapsed=elapsed+1,n=n+1",(st,))
        require(strategies=={'explore':40,'model':60},'Exploration quota did not reconcile under unit jobs')
        with patch.object(controller,'learning_gate',return_value={'enable_model':False}):
            require(controller.choose_job(db,{},1,2)['strategy']=='balanced','Failed model gate did not fall back')
        return dict(bootstrap_contexts=len(counts),observations_per_context=3,unit_time_strategy_counts=strategies,
                    failed_gate_falls_back=True,note='Synthetic scheduling only; no coverage or discoveries claimed.')
    finally:db.close()


def hit_attribution_test(spec):
    import math
    seed=1142
    fixture=None
    for index in range(64):
        base,b,c=controller.generator_at(spec,seed,index)
        for t in range(spec['tlo'],spec['thi']+1):
            a=base+spec['ell']*t
            n=a**3+114*b**3+12996*c**3-342*a*b*c
            d=n//spec['ell'];C=b*b-a*c;B=114*c*c-a*b
            if spec['dlo']<d<=spec['dhi'] and math.gcd(C,d)==1:
                r=B*pow(C,-1,d)%d
                fixture=dict(type='hit',k=114,xyz=[10*d,-9*d,r+4*d],D=d,r=r,q=4,abc=[a,b,c],index=index,ell=spec['ell'])
                break
        if fixture:break
    require(fixture is not None,'No norm fixture found')
    job=job_for(spec,64,0)
    with patch.object(controller,'sum',lambda _:114,create=True):
        controller.verify_hit(fixture,spec,job,seed)
        wrong=copy.deepcopy(fixture);wrong['r']=(wrong['r']+1)%wrong['D'];wrong['xyz'][2]=wrong['r']+4*wrong['D']
        def fake_cube_pow(a,b,c):return 114%c if b==3 else pow(a,b,c)
        with patch.object(controller,'pow',fake_cube_pow,create=True):
            try:controller.verify_hit(wrong,spec,job,seed)
            except ValueError as exc:require('root does not match' in str(exc),'Wrong failure in root attribution test')
            else:raise AssertionError('Wrong root attributed to generator')
    return dict(passed=True,warning='Synthetic arithmetic acceptance tests attribution only; not a solution of114.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'runs/controller-validation.json')
    args = parser.parse_args()
    started = time.monotonic()
    evidence = dict(schema=1, started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                    hashes_before=hashes(), tests={}, failures=[],
                    limitations=['Finite fault tests, not a formal verification.',
                                 'Positive rescue routing uses an explicitly injected verifier; no synthetic solution is asserted.'])
    with tempfile.TemporaryDirectory(prefix='three-cubes-controller-validation-') as scratch:
        directory = Path(scratch)
        spec = controller.contexts()[0]
        tests = [('protocol',lambda:protocol_tests(spec)),
                 ('reservations',lambda:reservation_tests(directory,spec)),
                 ('hit_rescue',lambda:rescue_tests(spec)),
                 ('hit_attribution',lambda:hit_attribution_test(spec)),
                 ('scheduling',lambda:scheduling_tests(directory)),
                 ('exclusive_writer_lock',lambda:writer_lock_test(directory/'lock-test')),
                 ('real_cli_resume',lambda:real_resume_test(directory/'cli-resume'))]
        tests.append(('real_offset_integration',offset_integration))
        for name,test in tests:
            try:
                evidence['tests'][name] = test()
            except Exception:
                evidence['failures'].append(dict(test=name,traceback=traceback.format_exc()))
    evidence['hashes_after'] = hashes()
    if evidence['hashes_before'] != evidence['hashes_after']:
        evidence['failures'].append(dict(test='source_stability',error='Source or binary changed during validation; rerun after the build freezes.'))
    evidence['elapsed_seconds'] = time.monotonic()-started
    evidence['passed'] = not evidence['failures']
    args.output.parent.mkdir(parents=True,exist_ok=True)
    controller.atomic_json(args.output,evidence)
    print(json.dumps(dict(passed=evidence['passed'],tests=list(evidence['tests']),
                          failures=evidence['failures'],elapsed_seconds=evidence['elapsed_seconds'],
                          evidence=str(args.output.resolve())),indent=2))
    return 0 if evidence['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
