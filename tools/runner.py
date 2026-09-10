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
import secrets
import signal
import sqlite3
import subprocess
import sys
import time
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

from search_core import CONTEXTS, ENGINE, canonical_json, make_task, run_task, task_id, verify_triple
from coverage_client import CoverageError, CoverageIndex
from client_audit import RunAudit, VERSION, RNG_ALGORITHM, seed_value

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
    temporary = path.with_name(path.name+f'.{os.getpid()}.{secrets.token_hex(8)}.tmp')
    try:
        with temporary.open('x', encoding='utf-8', newline='\n') as handle:
            handle.write(canonical_json(data)+'\n')
            handle.flush(); os.fsync(handle.fileno())
        # Windows briefly denies replacement while another writer closes its
        # destination handle. Retry only these transient sharing/access errors.
        for attempt in range(8):
            try:
                os.replace(temporary, path)
                break
            except PermissionError as exc:
                if getattr(exc, 'winerror', None) not in (5, 32, 33) or attempt == 7:
                    raise
                time.sleep(min(0.01 * 2**attempt, 0.2))
    finally:
        temporary.unlink(missing_ok=True)
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
      CREATE TABLE IF NOT EXISTS banks(id TEXT PRIMARY KEY,path TEXT NOT NULL,submitted TEXT);
      CREATE TABLE IF NOT EXISTS coverage_skips(id TEXT PRIMARY KEY,revision INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS bank_priority(id TEXT PRIMARY KEY);
      CREATE TABLE IF NOT EXISTS rng_states(seed TEXT PRIMARY KEY,algorithm TEXT NOT NULL,runtime TEXT NOT NULL,state TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS discoveries(id TEXT PRIMARY KEY,xyz TEXT NOT NULL,bank TEXT NOT NULL);''')
    identity = canonical_json(dict(engine=ENGINE, contributor=contributor))
    previous = db.execute("SELECT value FROM meta WHERE key='identity'").fetchone()
    if previous and previous[0] != identity:
        db.close()
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


def restore_rng(db, seed):
    rng = random.Random(int(seed, 16))
    previous = db.execute('SELECT algorithm,runtime,state FROM rng_states WHERE seed=?', (seed,)).fetchone()
    if previous:
        if previous[0] != RNG_ALGORITHM or previous[1] != sys.version.split()[0]:
            raise RuntimeError('This seed checkpoint belongs to another PRNG/runtime; use its Python version or choose a new seed')
        state = json.loads(previous[2])
        rng.setstate((state[0], tuple(state[1]), state[2]))
    return rng, previous is not None


def save_rng(db, seed, rng):
    db.execute('INSERT OR REPLACE INTO rng_states VALUES(?,?,?,?)',
               (seed, RNG_ALGORITHM, sys.version.split()[0], canonical_json(rng.getstate())))


def choose_task(rng, weights, db, coverage=None, seed=None):
    # Older checkpoints have no saved PRNG state. Permit skipping their local
    # prefix once; subsequent allocations checkpoint the cursor atomically.
    legacy = seed is not None and db.execute('SELECT 1 FROM rng_states WHERE seed=?', (seed,)).fetchone() is None
    attempts = 100 + (db.execute('SELECT count(*) FROM tasks').fetchone()[0] if legacy else 0)
    for _ in range(attempts):
        c = rng.choices(CONTEXTS, weights=weights, k=1)[0]
        row = rng.randrange(int(c['rowTasks']))*c['rowStride']
        task = make_task(c['id'], row, rng.randrange(c['blocks']))
        tid = task_id(task)
        if coverage is not None and coverage.contains(task):
            continue
        if db.execute('SELECT 1 FROM tasks WHERE id=?', (tid,)).fetchone() is None:
            with db:
                db.execute('INSERT INTO tasks(id,task) VALUES(?,?)', (tid, canonical_json(task)))
                if seed is not None:
                    save_rng(db, seed, rng)
            return task
    if seed is not None:
        with db:
            save_rng(db, seed, rng)
    raise RuntimeError('Could not allocate a fresh local task')


def preserve_result(out, db, result):
    # Positive data reaches a separate fsynced file before ordinary bookkeeping.
    for hit in result['hits']:
        if not verify_triple(hit['xyz']):
            raise ArithmeticError('parent cube verification failed')
        digest = hashlib.sha256(canonical_json(hit['xyz']).encode()).hexdigest()
        atomic_json(out/'discoveries'/f'{digest}.json', {'engine': ENGINE, 'result': result, 'hit': hit})
    line = canonical_json(result)
    with (out/'results.jsonl').open('a', encoding='utf-8', newline='\n') as handle:
        handle.write(line+'\n'); handle.flush(); os.fsync(handle.fileno())
    db.execute('UPDATE tasks SET result=? WHERE id=?', (line, result['id']))
    db.commit()


def preserve_identity(output, hit, task=None):
    if not verify_triple(hit.get('xyz')):
        raise ArithmeticError('independent discovery verification failed')
    xyz = sorted(hit['xyz'], key=int)
    digest = hashlib.sha256(canonical_json(xyz).encode()).hexdigest()
    path = Path(output)/'discoveries'/f'identity-{digest}.json'
    try:
        atomic_json(path, {'schema': 'math-gambling-discovery-v1', 'engine': ENGINE,
                           'task': task, 'hit': {**hit, 'xyz': xyz}})
    except Exception as exc:
        raise RuntimeError(f'EXACT IDENTITY {canonical_json(xyz)} could not be saved: {exc}') from exc
    return path


def execute_task(task, output):
    return run_task(task, on_hit=lambda hit: preserve_identity(output, hit, task))


def recover_discoveries(out, db, contributor, *, scan_results=False):
    """Independently recover identities without claiming their task completed."""
    candidates, errors = [], []
    for path in (out/'discoveries').glob('*.json'):
        try:
            with path.open('rb') as handle:
                raw = handle.read(8*1024*1024+1)
            if len(raw) > 8*1024*1024:
                raise ValueError('discovery file exceeds recovery cap')
            record = json.loads(raw)
            if not isinstance(record, dict) or not isinstance(record.get('hit'), dict):
                raise ValueError('malformed saved discovery')
            candidates.append(record['hit'])
        except (OSError, ValueError) as exc:
            errors.append(f'{path}: {exc}')
    if scan_results:
        for text, in db.execute('SELECT result FROM tasks WHERE result IS NOT NULL AND result LIKE ?', ('%"hits":[{%',)):
            try:
                hits = json.loads(text)['hits']
                if not isinstance(hits, list):
                    raise ValueError('saved result hits must be a list')
                candidates.extend(hits)
            except (ValueError, KeyError, TypeError) as exc:
                errors.append(f'Saved result: {exc}')
    recovered = []
    for hit in candidates:
        if not isinstance(hit, dict) or not verify_triple(hit.get('xyz')):
            errors.append('Saved discovery failed independent verification')
            continue
        xyz = sorted(hit['xyz'], key=int)
        digest = hashlib.sha256(canonical_json(xyz).encode()).hexdigest()
        if db.execute('SELECT 1 FROM discoveries WHERE id=?', (digest,)).fetchone():
            continue
        print('EXACT IDENTITY RECOVERED: '+canonical_json(xyz), flush=True)
        # Keep the worker's original task/curve provenance when it already
        # wrote the canonical identity file before recovery noticed it.
        if not (out/'discoveries'/f'identity-{digest}.json').exists():
            preserve_identity(out, hit)
        bank = {'schema': 'math-gambling-identity-v1', 'contributor': contributor, 'hits': [{'xyz': xyz}]}
        bid = hashlib.sha256(canonical_json(bank).encode()).hexdigest()
        relative = f'banks/bank-{bid[:16]}.json'
        atomic_json(out/relative, bank)
        with db:
            db.execute('INSERT OR IGNORE INTO banks(id,path) VALUES(?,?)', (bid, relative))
            db.execute('INSERT OR IGNORE INTO bank_priority VALUES(?)', (bid,))
            db.execute('INSERT INTO discoveries VALUES(?,?,?)', (digest, canonical_json(xyz), bid))
        recovered.append(xyz)
    if errors:
        raise RuntimeError('Discovery recovery needs attention; scheduling is blocked. '+'; '.join(errors))
    return recovered


def write_bank(out, db, contributor, force=False, bank_every=BANK_LIMIT, priority_id=None):
    if priority_id is not None:
        rows = db.execute('SELECT id,result FROM tasks WHERE id=? AND result IS NOT NULL AND bank IS NULL', (priority_id,)).fetchall()
        force = True
    else:
        rows = db.execute('SELECT id,result FROM tasks WHERE result IS NOT NULL AND bank IS NULL ORDER BY rowid LIMIT ?', (bank_every,)).fetchall()
    if not rows or (len(rows) < bank_every and not force):
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
        db.execute('INSERT OR IGNORE INTO banks(id,path) VALUES(?,?)', (bid, path.relative_to(out).as_posix()))
        if any(claim.get('hits') for claim in claims):
            db.execute('INSERT OR IGNORE INTO bank_priority(id) VALUES(?)', (bid,))
        db.executemany('UPDATE tasks SET bank=? WHERE id=?', [(bid, tid) for tid in chosen])
    print(f'Bank ready: {path} ({len(claims)} tasks; awaiting submission and independent replay)', flush=True)
    return path


def maybe_submit(db, repo, last_attempt):
    if time.monotonic()-last_attempt < 60:
        return last_attempt
    pending = db.execute('SELECT id,path FROM banks WHERE submitted IS NULL ORDER BY CASE WHEN id IN (SELECT id FROM bank_priority) THEN 0 ELSE 1 END,rowid LIMIT 1').fetchone()
    if not pending:
        return last_attempt
    bid, path = pending
    attempt = time.monotonic()
    try:
        title = f'[bank] Bank-in {bid[:16]}'
        path, bank_body = resolve_bank(db, bid, path)
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
        # This committed marker survives a kill between external dispatch and
        # recording the response. A later invocation will not blindly resend.
        with db:
            db.execute('UPDATE banks SET submitted=? WHERE id=?',
                       ('uncertain; submission intent recorded; inspect GitHub before retrying', bid))
        proc = subprocess.run(['gh', 'issue', 'create', '--repo', repo,
            '--title', title, '--body-file', str(path)], text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        if proc.returncode:
            raise RuntimeError(proc.stderr.strip()[:200])
        url = proc.stdout.strip()
        if not re.fullmatch(r'https://github\.com/[^/]+/[^/]+/issues/[0-9]+', url):
            raise RuntimeError('ambiguous gh response; check GitHub before retrying this bank')
        db.execute('UPDATE banks SET submitted=? WHERE id=?', (url, bid)); db.commit()
        print(f'Submitted: {url} (queued, not yet verified)', flush=True)
    except (OSError, ValueError, subprocess.TimeoutExpired, RuntimeError, sqlite3.Error) as exc:
        db.rollback()
        # Any dispatch intent was already committed before the request.
        print(f'Bank retained locally; submission did not confirm: {exc}', file=sys.stderr)
    return attempt


def resolve_bank(db, bid, stored):
    out = Path(db.execute('PRAGMA database_list').fetchone()[2]).resolve().parent
    expected = f'bank-{bid[:16]}.json'
    if str(stored).replace('\\', '/').rsplit('/', 1)[-1] != expected:
        raise ValueError('Bank filename does not match its checkpoint digest')
    path = out/'banks'/expected
    if not path.resolve().is_relative_to(out):
        raise ValueError('Bank path escapes the checkpoint directory')
    body = json.loads(path.read_text(encoding='utf-8'))
    if hashlib.sha256(canonical_json(body).encode()).hexdigest() != bid:
        raise ValueError('Bank contents no longer match the checkpoint digest')
    relative = f'banks/{expected}'
    if stored != relative:
        with db:
            db.execute('UPDATE banks SET path=? WHERE id=?', (relative, bid))
    return path, body


def github_identity(login=False):
    """User-invoked CLI authentication; no browser token is stored by this app."""
    try:
        auth = subprocess.run(['gh', 'auth', 'status', '--hostname', 'github.com'], capture_output=True, timeout=15)
        if auth.returncode and login:
            authenticated = subprocess.run(['gh', 'auth', 'login', '--hostname', 'github.com', '--web', '--git-protocol', 'https'])
            if authenticated.returncode:
                raise RuntimeError('GitHub login was not completed')
        elif auth.returncode:
            raise RuntimeError('run with --login once, or use gh auth login')
        result = subprocess.run(['gh', 'api', '-H', 'User-Agent: ' + UA, 'user', '--jq', '.login'],
                                capture_output=True, text=True, timeout=20)
        username = result.stdout.strip()
        if result.returncode or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?', username):
            raise RuntimeError('could not read the authenticated GitHub username')
        return username
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f'GitHub CLI unavailable ({type(exc).__name__}); install it from https://cli.github.com/') from None


def bank_queue(db):
    pending = db.execute('SELECT count(*) FROM banks WHERE submitted IS NULL').fetchone()[0]
    uncertain = db.execute("SELECT count(*) FROM banks WHERE submitted LIKE 'uncertain;%' ").fetchone()[0]
    submitted = db.execute("SELECT count(*) FROM banks WHERE submitted LIKE 'https://github.com/%' ").fetchone()[0]
    return dict(pending=pending, uncertain=uncertain, submitted_awaiting_verification=submitted)


def main(argv=None):
    if sys.version_info < MIN_PYTHON:
        raise SystemExit('Math Gambling needs Python 3.11 or later. Install it from https://www.python.org/downloads/.')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version='Math Gambling runner ' + VERSION)
    parser.add_argument('--minutes', type=float, default=10)
    parser.add_argument('--workers', type=int, default=max(1, min(4, (os.cpu_count() or 2)//2)))
    parser.add_argument('--name')
    parser.add_argument('--github')
    parser.add_argument('--url', type=profile_url, help='optional public HTTP(S) link for your leaderboard alias')
    parser.add_argument('--output', type=Path, default=Path('math-gambling-run'))
    parser.add_argument('--offline', action='store_true', help='use the bundled strategy/coverage snapshot; it may miss work banked since release')
    parser.add_argument('--login', action='store_true', help='use the GitHub CLI browser login and read your authenticated username')
    parser.add_argument('--submit', action='store_true', help='explicitly authorize gh issue creation, at most once/minute')
    parser.add_argument('--bank-every', type=int, default=BANK_LIMIT, help='prepare a bank every N completed tasks, 1..256 (default256)')
    parser.add_argument('--seed', type=seed_value, help='reproducible client PRNG seed: exactly64 hex digits; securely generated when omitted')
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
    if args.offline and (args.submit or args.login):
        parser.error('--offline cannot be combined with --submit or --login')
    if not 1 <= args.bank_every <= BANK_LIMIT:
        parser.error('--bank-every must be 1..256')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repo):
        parser.error('invalid repository')
    if not args.name and sys.stdin.isatty():
        args.name = input('Name for the draft discovery credits: ').strip()
    if args.login or args.submit:
        try:
            authenticated = github_identity(args.login)
        except RuntimeError as exc:
            parser.error(str(exc))
        if args.github and args.github.lower() != authenticated.lower():
            parser.error('--github differs from the authenticated account; use its username or a separate output folder')
        args.github = authenticated
        print(f'GitHub account: @{authenticated}. ' + ('Automatic banking enabled.' if args.submit else 'Manual banking selected.'), flush=True)
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
    try:
        db = open_state(out, contributor)
    except BaseException:
        lock.close()
        raise
    if args.mark_banked:
        matches = [(bid, path) for bid, path in db.execute('SELECT id,path FROM banks')
                   if path.replace('\\', '/').rsplit('/', 1)[-1] == args.mark_banked]
        if len(matches) != 1:
            db.close(); lock.close()
            parser.error('--mark-banked must name one existing bank file')
        db.execute('UPDATE banks SET submitted=? WHERE id=?', ('manually reported submitted; not verified', matches[0][0])); db.commit()
        db.close(); lock.close()
        print('Marked manually submitted; no claim of server verification.'); return 0
    try:
        return run_campaign(args, out, db, contributor)
    except Exception as exc:
        print(f'Run failed; saved evidence is retained: {exc}', file=sys.stderr)
        try:
            identities = [json.loads(row[0]) for row in db.execute('SELECT xyz FROM discoveries ORDER BY id')]
            atomic_json(out/'status.json', dict(engine=ENGINE, version=VERSION, state='failed',
                error=str(exc), discoveries=identities, queue=bank_queue(db)))
        except Exception as write_error:
            print(f'Could not persist failure status: {write_error}', file=sys.stderr)
        return 2
    finally:
        db.close(); lock.close()


def run_campaign(args, out, db, contributor):
    recover_discoveries(out, db, contributor, scan_results=True)
    identities = [json.loads(row[0]) for row in db.execute('SELECT xyz FROM discoveries ORDER BY id')]
    if identities:
        if any(not verify_triple(xyz) for xyz in identities):
            raise RuntimeError('Stored discovery registry failed independent verification')
        print('EXACT DISCOVERY RECOVERED. No new work will be scheduled.', flush=True)
        for xyz in identities:
            print('Identity: '+canonical_json(xyz), flush=True)
        if args.submit:
            maybe_submit(db, args.repo, -math.inf)
        atomic_json(out/'status.json', dict(engine=ENGINE, version=VERSION, state='discovery_found',
            completed_this_run=0, discoveries=identities, queue=bank_queue(db)))
        return 0
    print(f'Math Gambling {VERSION} | {ENGINE}: {args.workers} workers, at most {args.minutes:g} minutes.', flush=True)
    print('Results are local until banked; GitHub replays before credit. Ctrl-C stops scheduling and drains current tasks.', flush=True)
    queue = bank_queue(db)
    print(f'Bank every {args.bank_every} completed tasks. Queue: {queue["pending"]} pending, {queue["uncertain"]} uncertain; submitted issues await verification.', flush=True)
    seed = args.seed or secrets.token_hex(32)
    audit = RunAudit(out, seed, dict(minutes=args.minutes, workers=args.workers, max_tasks=args.max_tasks, bank_every=args.bank_every))
    print(f'Seed: {seed} ({RNG_ALGORITHM}; Python {sys.version.split()[0]})', flush=True)
    print(f'Scheduling log: {audit.path}', flush=True)
    coverage = CoverageIndex(ROOT/'data/coverage', out/'cache/coverage', offline=args.offline)
    try:
        snapshot = coverage.refresh()
    except CoverageError as exc:
        audit.write('blocked', reason=str(exc))
        atomic_json(out/'status.json', dict(engine=ENGINE, version=VERSION, state='failed', error=str(exc), completed_this_run=0))
        print(f'Coverage unavailable; no new tasks dispatched. {exc}. Retry online or explicitly choose --offline for the bundled snapshot.', file=sys.stderr)
        return 2
    print(f'Coverage: {snapshot["revision"]:,} published tasks, {snapshot["updated_at"]} ({snapshot["mode"]}). Concurrent or not-yet-published work can still overlap.', flush=True)
    weights, epoch = load_strategy(args.offline)
    print(f'Scheduling policy epoch {epoch}; at least 40% uniform task proposals, not CPU shares.', flush=True)
    audit.policy(weights, epoch, snapshot)
    rng, resumed_seed = restore_rng(db, seed)
    audit.write('rng', resumed=resumed_seed, state=rng.getstate())
    stop = False
    failures = []
    def request_stop(*_):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, 'SIGTERM'): signal.signal(signal.SIGTERM, request_stop)
    pending = [json.loads(row[0]) for row in db.execute('SELECT task FROM tasks WHERE result IS NULL AND id NOT IN (SELECT id FROM coverage_skips) ORDER BY rowid')]
    completed = curves = points = inputs = exact = 0
    deadline = time.monotonic()+args.minutes*60
    last_report = last_refresh = time.monotonic()
    last_refresh_completed = 0
    last_submit = -math.inf
    started = time.monotonic()
    pool = ProcessPoolExecutor(max_workers=args.workers, mp_context=multiprocessing.get_context('spawn'), initializer=initialize_worker)
    active = {}
    capacity_paused = False
    try:
        if args.submit:
            last_submit = maybe_submit(db, args.repo, last_submit)
        while True:
            unbanked = db.execute("SELECT count(*) FROM tasks LEFT JOIN banks ON tasks.bank=banks.id WHERE tasks.result IS NOT NULL AND (banks.submitted IS NULL OR banks.submitted LIKE 'uncertain;%')").fetchone()[0]
            if unbanked >= OUTBOX_LIMIT:
                if not capacity_paused: print('Outbox capacity reached; computation pauses while saved banks await submission.', flush=True)
                capacity_paused = True
                if not args.submit: stop = True
            else:
                capacity_paused = False
            while not stop and not capacity_paused and time.monotonic() < deadline and completed+len(active) < args.max_tasks and len(active) < args.workers and unbanked+len(active) < OUTBOX_LIMIT:
                try:
                    if pending:
                        task = pending.pop(0)
                        if coverage.contains(task):
                            db.execute('INSERT OR REPLACE INTO coverage_skips VALUES(?,?)', (task_id(task), coverage.index['revision']))
                            db.commit()
                            audit.write('already_published', task_id=task_id(task), revision=coverage.index['revision'])
                            continue
                    else:
                        task = choose_task(rng, weights, db, coverage, seed=seed)
                except Exception as exc:
                    print(f'Task allocation failed; scheduling paused: {exc}', file=sys.stderr)
                    audit.write('blocked', reason=str(exc))
                    failures.append(str(exc))
                    stop = True
                    break
                audit.write('dispatch', task=task, task_id=task_id(task), policy_epoch=epoch, coverage_revision=coverage.index['revision'])
                active[pool.submit(execute_task, task, str(out))] = task
            if not active:
                while write_bank(out, db, contributor, force=True, bank_every=args.bank_every): pass
                # Automatic mode uses the remaining user-selected time to drain
                # queued banks at the same one-per-minute rate, without compute.
                if args.submit and not stop and time.monotonic() < deadline and bank_queue(db)['pending']:
                    last_submit = maybe_submit(db, args.repo, last_submit)
                    if bank_queue(db)['pending']:
                        if time.monotonic()-last_report >= 5:
                            print(f'Computation stopped; {bank_queue(db)["pending"]} banks queued for automatic submission. Ctrl-C saves the queue and exits.', flush=True)
                            last_report = time.monotonic()
                        time.sleep(0.25)
                        continue
                break
            done, _ = wait(active, timeout=0.25, return_when=FIRST_COMPLETED)
            if any((out/'discoveries').glob('*.json')):
                recover_discoveries(out, db, contributor)
                if db.execute('SELECT 1 FROM discoveries LIMIT 1').fetchone():
                    stop = True
            for future in done:
                task = active.pop(future)
                try:
                    result = future.result()
                    if result['id'] != task_id(task): raise ArithmeticError('worker task identity mismatch')
                    preserve_result(out, db, result)
                except Exception as exc:
                    failures.append(str(exc))
                    stop = True
                    print(f'Worker failed; reserved task remains retryable: {exc}', file=sys.stderr)
                    continue
                completed += 1
                curves += result['counters']['curves']; points += result['counters']['quotient_points']
                inputs += result['counters']['generators']; exact += result['counters']['exact_tests']
                audit.write('completed', task_id=result['id'], digest=result['digest'], counters=result['counters'])
                if result['hits']:
                    stop = True
                    print('EXACT SOLUTION PRESERVED. Scheduling halted; submit discovery for independent review.', flush=True)
                    write_bank(out, db, contributor, force=True, bank_every=args.bank_every, priority_id=result['id'])
                else: write_bank(out, db, contributor, bank_every=args.bank_every)
            if args.submit: last_submit = maybe_submit(db, args.repo, last_submit)
            now = time.monotonic()
            if now-last_report >= 5:
                print(f'{completed:,} tasks | {inputs:,} inputs | {curves:,} curves | {exact:,} exact square tests | {points:,} q positions | {now-started:.1f}s | epoch {epoch} | {bank_queue(db)["pending"]} banks pending', flush=True)
                last_report = now
            if (completed-last_refresh_completed >= 64 or now-last_refresh >= 60) and not stop:
                try:
                    snapshot = coverage.refresh()
                    weights, epoch = load_strategy(args.offline)
                    audit.policy(weights, epoch, snapshot)
                    print(f'Policy epoch {epoch}; coverage revision {snapshot["revision"]:,}; {coverage.known_skips:,} published task selections skipped.', flush=True)
                except Exception as exc:
                    print(f'Coverage refresh failed; scheduling paused: {exc}', file=sys.stderr)
                    audit.write('blocked', reason=str(exc)); failures.append(str(exc)); stop = True
                last_refresh = now; last_refresh_completed = completed
    except Exception as exc:
        failures.append(str(exc))
        print(f'Run failed; unfinished task reservations remain retryable: {exc}', file=sys.stderr)
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
        try:
            recover_discoveries(out, db, contributor, scan_results=True)
        except Exception as exc:
            failures.append(str(exc))
        while True:
            try:
                if not write_bank(out, db, contributor, force=True, bank_every=args.bank_every):
                    break
            except Exception as exc:
                failures.append(str(exc))
                break
        if args.submit:
            last_submit = maybe_submit(db, args.repo, last_submit)
        identities = [json.loads(row[0]) for row in db.execute('SELECT xyz FROM discoveries ORDER BY id')]
        queue = bank_queue(db)
        state = 'failed' if failures else 'discovery_found' if identities else 'stopped'
        atomic_json(out/'status.json', dict(engine=ENGINE, completed_this_run=completed,
            version=VERSION, seed=seed, rng=RNG_ALGORITHM, run_id=audit.id,
            inputs_this_run=inputs, exact_tests_this_run=exact, coverage=coverage.snapshot(),
            published_selections_skipped=coverage.known_skips,
            curves_this_run=curves, quotient_points_this_run=points,
            elapsed_seconds=round(time.monotonic()-started, 3), policy_epoch=epoch,
            pending_banks=queue['pending']+queue['uncertain'], uncertain_banks=queue['uncertain'],
            state=state, errors=failures, discoveries=identities,
            verified_community_credit='check GitHub; local completion is not server verification'))
        audit.write(state, completed=completed, inputs=inputs, curves=curves, exact_tests=exact,
                    queue=queue, errors=failures, discoveries=identities)
    outcome = 'Run failed after' if failures else 'Finished'
    print(f'{outcome} {completed:,} completed tasks. Bank files: {out / "banks"}', flush=True)
    print(f'Bank queue: {queue["pending"]} awaiting submission, {queue["uncertain"]} uncertain. Restart with --submit to continue automatic banking; GitHub issues show verification status.', flush=True)
    print(f'Manual bank: open https://github.com/{args.repo}/issues/new?title=%5Bbank%5D%20Local%20computation%20bank and paste one bank JSON as the body.', flush=True)
    return 2 if failures else 0


if __name__ == '__main__':
    multiprocessing.freeze_support()
    raise SystemExit(main())
