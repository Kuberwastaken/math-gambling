#!/usr/bin/env python3
"""Run bounded exact tasks locally and bank replayable claims through GitHub.

No dependencies. Default mode writes durable local files and sends no results.
--submit explicitly authorizes gh issue creation (at most once per minute).
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
import hashlib
import json
import math
import multiprocessing
import os
from pathlib import Path
import random
import re
import signal
import sqlite3
import subprocess
import sys
import time
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

from search_core import CONTEXTS, ENGINE, canonical_json, make_task, run_task, task_id, verify_triple

ROOT = Path(__file__).resolve().parents[1]
UA = 'OpenAI File Downloader, XaiImageApiFetch/1.0'
STRATEGY_URL = 'https://kuber.studio/math-gambling/data/strategy.json'
BANK_LIMIT = 256
OUTBOX_LIMIT = 4096
MIN_PYTHON = (3, 11)


def profile_url(value):
    """Validate an optional public attribution link without fetching it."""
    if not value:
        return None
    if len(value) > 2048 or any(c.isspace() or ord(c) < 32 or ord(c) == 127 or c == '\\' for c in value):
        raise argparse.ArgumentTypeError('--url must be an HTTP(S) URL without whitespace or credentials (max 2048 characters)')
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username is not None or parsed.password is not None:
            raise ValueError('invalid public link')
        parsed.port
    except ValueError:
        raise argparse.ArgumentTypeError('--url must be an HTTP(S) URL without whitespace or credentials (max 2048 characters)') from None
    return value


def initialize_worker():
    # Terminal Ctrl+C is delivered to the whole process group on macOS/Linux
    # and to console workers on Windows. Let the parent stop allocation and
    # drain bounded tasks instead of interrupting a worker mid-result.
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.tmp')
    with temporary.open('w', encoding='utf-8') as handle:
        handle.write(canonical_json(data)+'\n')
        handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)
    if hasattr(os, 'O_DIRECTORY'):
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)


def lock_output(path):
    handle = path.open('a+b')
    try:
        if os.name == 'nt':
            import msvcrt
            handle.seek(0); handle.write(b'0'); handle.flush(); handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise SystemExit('Another runner owns this output directory. Use a different --output.')
    return handle


def open_state(out, contributor):
    db = sqlite3.connect(out/'checkpoint.sqlite3')
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=FULL')
    db.executescript('''CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,task TEXT NOT NULL,result TEXT,bank TEXT);
      CREATE TABLE IF NOT EXISTS banks(id TEXT PRIMARY KEY,path TEXT NOT NULL,submitted TEXT);''')
    identity = canonical_json(dict(engine=ENGINE, contributor=contributor))
    previous = db.execute("SELECT value FROM meta WHERE key='identity'").fetchone()
    if previous and previous[0] != identity:
        raise SystemExit('This checkpoint belongs to another engine/name/GitHub identity; choose a new --output.')
    db.execute("INSERT OR IGNORE INTO meta VALUES('identity',?)", (identity,)); db.commit()
    return db


def load_strategy(offline=False):
    sources = []
    if not offline:
        try:
            request = Request(STRATEGY_URL, headers={'User-Agent': UA, 'Accept': 'application/json'})
            with urlopen(request, timeout=4) as response:
                body = response.read(65537)
            if len(body) > 65536:
                raise ValueError('strategy exceeds byte cap')
            sources.append(json.loads(body))
        except Exception as exc:
            print(f'Strategy refresh unavailable ({type(exc).__name__}); using local/uniform policy.', file=sys.stderr)
    try:
        sources.append(json.loads((ROOT/'data/strategy.json').read_text()))
    except (OSError, ValueError):
        pass
    for policy in sources:
        try:
            if policy.get('schema') != 'math-gambling-strategy-v1' or len(policy['contexts']) != len(CONTEXTS):
                continue
            weights = {v['id']: v['weight'] for v in policy['contexts']}
            if set(weights) != {v['id'] for v in CONTEXTS}:
                continue
            values = [weights[c['id']] for c in CONTEXTS]
            if any(type(w) not in (int, float) or not math.isfinite(w) or w < 0.4/81-1e-12 or w > 1 for w in values):
                continue
            if abs(sum(values)-1) > 1e-8:
                continue
            return values, policy.get('epoch', 0)
        except (KeyError, TypeError, ValueError):
            continue
    return [1/81]*81, 0


def choose_task(rng, weights, db):
    for _ in range(100):
        c = rng.choices(CONTEXTS, weights=weights, k=1)[0]
        row = rng.randrange(int(c['rowTasks']))*c['rowStride']
        task = make_task(c['id'], row, rng.randrange(c['blocks']))
        tid = task_id(task)
        if db.execute('SELECT 1 FROM tasks WHERE id=?', (tid,)).fetchone() is None:
            db.execute('INSERT INTO tasks(id,task) VALUES(?,?)', (tid, canonical_json(task)))
            db.commit()
            return task
    raise RuntimeError('Could not allocate a fresh local task')


def preserve_result(out, db, result):
    # Positive data reaches a separate fsynced file before ordinary bookkeeping.
    for hit in result['hits']:
        if not verify_triple(hit['xyz']):
            raise ArithmeticError('parent cube verification failed')
        digest = hashlib.sha256(canonical_json(hit['xyz']).encode()).hexdigest()
        atomic_json(out/'discoveries'/f'{digest}.json', {'engine': ENGINE, 'result': result, 'hit': hit})
    line = canonical_json(result)
    with (out/'results.jsonl').open('a', encoding='utf-8') as handle:
        handle.write(line+'\n'); handle.flush(); os.fsync(handle.fileno())
    db.execute('UPDATE tasks SET result=? WHERE id=?', (line, result['id']))
    db.commit()


def execute_task(task, output):
    result = run_task(task)
    # A worker writes a hit before IPC; parent failure after discovery therefore
    # cannot erase the only copy. This file is never interpreted as task credit.
    for hit in result['hits']:
        if not verify_triple(hit['xyz']):
            raise ArithmeticError('worker cube verification failed')
        digest = hashlib.sha256(canonical_json(hit['xyz']).encode()).hexdigest()
        atomic_json(Path(output)/'discoveries'/f'worker-{digest}.json', {'engine': ENGINE, 'result': result, 'hit': hit})
    return result


def write_bank(out, db, contributor, force=False):
    rows = db.execute('SELECT id,result FROM tasks WHERE result IS NOT NULL AND bank IS NULL ORDER BY rowid LIMIT ?', (BANK_LIMIT,)).fetchall()
    if not rows or (len(rows) < BANK_LIMIT and not force):
        return None
    claims, chosen = [], []
    for tid, text in rows:
        result = json.loads(text)
        claim = dict(task=result['task'], digest=result['digest'])
        if result['hits']:
            claim['hits'] = result['hits']
        trial = dict(schema='math-gambling-bank-v1', contributor=contributor, tasks=claims+[claim])
        if len(canonical_json(trial).encode())+1 > 60000:
            break
        claims.append(claim); chosen.append(tid)
    if not chosen:
        raise RuntimeError('A task claim exceeds bank byte cap; exact hits remain preserved locally')
    bank = dict(schema='math-gambling-bank-v1', contributor=contributor, tasks=claims)
    bid = hashlib.sha256(canonical_json(bank).encode()).hexdigest()
    path = out/'banks'/f'bank-{bid[:16]}.json'
    atomic_json(path, bank)
    with db:
        db.execute('INSERT OR IGNORE INTO banks(id,path) VALUES(?,?)', (bid, str(path)))
        db.executemany('UPDATE tasks SET bank=? WHERE id=?', [(bid, tid) for tid in chosen])
    print(f'Bank ready: {path} ({len(claims)} tasks; awaiting submission and independent replay)', flush=True)
    return path


def maybe_submit(db, repo, last_attempt):
    if time.monotonic()-last_attempt < 60:
        return last_attempt
    pending = db.execute('SELECT id,path FROM banks WHERE submitted IS NULL ORDER BY rowid LIMIT 1').fetchone()
    if not pending:
        return last_attempt
    bid, path = pending
    attempt = time.monotonic()
    dispatched = False
    try:
        title = f'[bank] Bank-in {bid[:16]}'
        bank_body = json.loads(Path(path).read_text())
        lookup = subprocess.run(['gh', 'issue', 'list', '--repo', repo, '--state', 'all',
            '--search', bid[:16], '--json', 'title,url,body', '--limit', '100'], text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        if lookup.returncode:
            raise RuntimeError('Could not check for an existing bank issue; creation deferred')
        existing = []
        for issue in json.loads(lookup.stdout):
            if issue.get('title') != title:
                continue
            try:
                same_body = canonical_json(json.loads(issue.get('body', ''))) == canonical_json(bank_body)
            except (ValueError, TypeError):
                same_body = False
            if same_body:
                existing.append(issue['url'])
        if existing:
            db.execute('UPDATE banks SET submitted=? WHERE id=?', (existing[0], bid)); db.commit()
            print(f'Existing submission retained: {existing[0]}', flush=True)
            return attempt
        dispatched = True
        proc = subprocess.run(['gh', 'issue', 'create', '--repo', repo,
            '--title', title, '--body-file', path], text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        if proc.returncode:
            raise RuntimeError(proc.stderr.strip()[:200])
        url = proc.stdout.strip()
        if not re.fullmatch(r'https://github\.com/[^/]+/[^/]+/issues/[0-9]+', url):
            raise RuntimeError('ambiguous gh response; check GitHub before retrying this bank')
        db.execute('UPDATE banks SET submitted=? WHERE id=?', (url, bid)); db.commit()
        print(f'Submitted: {url} (queued, not yet verified)', flush=True)
    except (OSError, ValueError, subprocess.TimeoutExpired, RuntimeError) as exc:
        if dispatched:
            # Do not silently retry an ambiguous external side effect.
            db.execute('UPDATE banks SET submitted=? WHERE id=?', ('uncertain; inspect GitHub and bank manually if needed', bid)); db.commit()
        print(f'Bank retained locally; submission did not confirm: {exc}', file=sys.stderr)
    return attempt


def main(argv=None):
    if sys.version_info < MIN_PYTHON:
        raise SystemExit('Math Gambling needs Python 3.11 or later. Install it from https://www.python.org/downloads/.')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--minutes', type=float, default=10)
    parser.add_argument('--workers', type=int, default=max(1, min(4, (os.cpu_count() or 2)//2)))
    parser.add_argument('--name')
    parser.add_argument('--github')
    parser.add_argument('--url', type=profile_url, help='optional public HTTP(S) link for your leaderboard alias')
    parser.add_argument('--output', type=Path, default=Path('math-gambling-run'))
    parser.add_argument('--offline', action='store_true', help='never fetch the shared strategy; results remain local')
    parser.add_argument('--submit', action='store_true', help='explicitly authorize gh issue creation, at most once/minute')
    parser.add_argument('--bank', action='store_true', help='write a final bank (also done by default)')
    parser.add_argument('--mark-banked', metavar='FILENAME', help='mark an existing bank manually submitted, then exit; this is not verification')
    parser.add_argument('--repo', default='Kuberwastaken/math-gambling')
    parser.add_argument('--max-tasks', type=int, default=4096, help='additional completed tasks this invocation; max4096')
    args = parser.parse_args(argv)
    if not math.isfinite(args.minutes) or not 0 < args.minutes <= 1440:
        parser.error('--minutes must be in (0,1440]')
    if not 1 <= args.workers <= min(32, os.cpu_count() or 1):
        parser.error('--workers must fit available CPUs and be <=32')
    if not 1 <= args.max_tasks <= 4096:
        parser.error('--max-tasks must be 1..4096')
    if args.offline and args.submit:
        parser.error('--offline and --submit cannot be combined')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repo):
        parser.error('invalid repository')
    if not args.name and sys.stdin.isatty():
        args.name = input('Name for the draft discovery credits: ').strip()
    if not args.github and sys.stdin.isatty():
        args.github = input('GitHub username (self-reported; submission author is authenticated): ').strip()
    if not args.name or len(args.name) > 80 or any(ord(c) < 32 for c in args.name):
        parser.error('provide --name, 1..80 printable characters')
    if not args.github or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?', args.github):
        parser.error('provide a valid --github username')
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    lock = lock_output(out/'runner.lock')
    contributor = dict(name=args.name, github=args.github)
    if args.url:
        contributor['url'] = args.url
    db = open_state(out, contributor)
    if args.mark_banked:
        matches = [(bid, path) for bid, path in db.execute('SELECT id,path FROM banks') if Path(path).name == args.mark_banked]
        if len(matches) != 1:
            parser.error('--mark-banked must name one existing bank file')
        db.execute('UPDATE banks SET submitted=? WHERE id=?', ('manually reported submitted; not verified', matches[0][0])); db.commit()
        print('Marked manually submitted; no claim of server verification.'); return 0
    if args.submit:
        try:
            auth = subprocess.run(['gh', 'auth', 'status'], capture_output=True, timeout=15)
            if auth.returncode: raise RuntimeError('gh auth status failed')
        except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
            parser.error(f'--submit needs an authenticated GitHub CLI: {exc}')
    print(f'{ENGINE}: {args.workers} workers, at most {args.minutes:g} minutes. No discovery ETA or guaranteed odds.', flush=True)
    print('Results are local until banked; GitHub replays before credit. Ctrl-C stops scheduling and drains current tasks.', flush=True)
    weights, epoch = load_strategy(args.offline)
    print(f'Cost-only scheduling policy epoch {epoch}; at least 40% uniform context exploration.', flush=True)
    rng = random.SystemRandom()
    stop = False
    def request_stop(*_):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, 'SIGTERM'): signal.signal(signal.SIGTERM, request_stop)
    pending = [json.loads(row[0]) for row in db.execute('SELECT task FROM tasks WHERE result IS NULL ORDER BY rowid')]
    completed = curves = points = 0
    deadline = time.monotonic()+args.minutes*60
    last_report = last_refresh = time.monotonic()
    last_refresh_completed = 0
    last_submit = -math.inf
    started = time.monotonic()
    pool = ProcessPoolExecutor(max_workers=args.workers, mp_context=multiprocessing.get_context('spawn'), initializer=initialize_worker)
    active = {}
    try:
        while True:
            unbanked = db.execute("SELECT count(*) FROM tasks LEFT JOIN banks ON tasks.bank=banks.id WHERE tasks.result IS NOT NULL AND (banks.submitted IS NULL OR banks.submitted LIKE 'uncertain;%')").fetchone()[0]
            if unbanked >= OUTBOX_LIMIT:
                if not stop: print('Outbox capacity reached; bank the saved files before more work.', flush=True)
                stop = True
            while not stop and time.monotonic() < deadline and completed+len(active) < args.max_tasks and len(active) < args.workers:
                task = pending.pop(0) if pending else choose_task(rng, weights, db)
                active[pool.submit(execute_task, task, str(out))] = task
            if not active:
                break
            done, _ = wait(active, timeout=0.25, return_when=FIRST_COMPLETED)
            for future in done:
                task = active.pop(future)
                try:
                    result = future.result()
                    if result['id'] != task_id(task): raise ArithmeticError('worker task identity mismatch')
                    preserve_result(out, db, result)
                except Exception as exc:
                    stop = True
                    print(f'Worker failed; reserved task remains retryable: {exc}', file=sys.stderr)
                    continue
                completed += 1
                curves += result['counters']['curves']; points += result['counters']['quotient_points']
                if result['hits']:
                    stop = True
                    print('EXACT SOLUTION PRESERVED. Scheduling halted; submit discovery for independent review.', flush=True)
                    write_bank(out, db, contributor, force=True)
                else: write_bank(out, db, contributor)
            if args.submit: last_submit = maybe_submit(db, args.repo, last_submit)
            now = time.monotonic()
            if now-last_report >= 5:
                print(f'{completed:,} completed tasks | {curves:,} bounded curves | {points:,} logical q positions | {now-started:.1f}s', flush=True)
                last_report = now
            if completed-last_refresh_completed >= 64 and now-last_refresh >= 60 and not stop:
                weights, epoch = load_strategy(args.offline); last_refresh = now; last_refresh_completed = completed
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
        while write_bank(out, db, contributor, force=True): pass
        if args.submit: last_submit = maybe_submit(db, args.repo, last_submit)
        atomic_json(out/'status.json', dict(engine=ENGINE, completed_this_run=completed,
            curves_this_run=curves, quotient_points_this_run=points,
            elapsed_seconds=round(time.monotonic()-started, 3), policy_epoch=epoch,
            pending_banks=db.execute("SELECT count(*) FROM banks WHERE submitted IS NULL OR submitted LIKE 'uncertain;%' ").fetchone()[0],
            uncertain_banks=db.execute("SELECT count(*) FROM banks WHERE submitted LIKE 'uncertain;%' ").fetchone()[0],
            state='stopped', verified_community_credit='check GitHub; local completion is not server verification'))
        db.close(); lock.close()
    print(f'Finished {completed:,} tasks. Bank files: {out / "banks"}', flush=True)
    print(f'Manual bank: open https://github.com/{args.repo}/issues/new?title=%5Bbank%5D%20Local%20computation%20bank and paste one bank JSON as the body.', flush=True)
    return 0


if __name__ == '__main__':
    multiprocessing.freeze_support()
    raise SystemExit(main())
