#!/usr/bin/env python3
"""Bounded, incremental export of mathematical intervals from trusted replay.

This is a separate audit product. It neither awards credit nor changes the
task-membership index. A completed-task digest alone is not an interval list.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import time
import types

from search_core import ENGINE, canonical_json, task_id, validate_task, verify_triple

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'math-gambling-mathematical-coverage-v1'
RECORD_SCHEMA = 'math-gambling-mathematical-task-v1'
MAX_LEDGER_BYTES = 64 * 1024
MAX_RECORD_BYTES = 2 * 1024 * 1024
MAX_INDEX_BYTES = 32 * 1024 * 1024
MAX_CURVES = 128 * 16
MAX_TASKS = 4096
TASK_SECONDS = 4.0
DECIMAL = re.compile(r'-?(?:0|[1-9][0-9]{0,127})\Z')
HEX = re.compile(r'[0-9a-f]{64}\Z')
SCOPE = {
    'k': 114,
    'parameterization': 's=x+y; D=abs(s); z=r+D*q; qlo<=q<=qhi',
    'minimal_abs_z': True,
    'candidate_condition': 'abs(z)<=min(abs(x),abs(y))',
    'domain': 'selected finite norm-coordinate tasks; not an exhaustive height box',
    'interval_semantics': 'every integer q was either excluded by an exact necessary-condition sieve or passed to the exact candidate check',
    'global_union_computed': False,
}


def sha(value):
    return hashlib.sha256(value).hexdigest()


def stamp():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def parse(raw):
    def invalid(value):
        raise ValueError('nonfinite JSON number: '+value)
    return json.loads(raw, object_pairs_hook=_pairs, parse_constant=invalid)


def read_bounded(path, limit):
    with Path(path).open('rb') as handle:
        raw = handle.read(limit+1)
    if len(raw) > limit:
        raise ValueError(f'{path}: exceeds byte cap')
    return raw


def atomic_bytes(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.'+path.name+f'.{os.getpid()}.{secrets.token_hex(8)}.tmp')
    try:
        with temporary.open('xb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if hasattr(os, 'O_DIRECTORY'):
            fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(path, value):
    atomic_bytes(path, (canonical_json(value)+'\n').encode('ascii'))


def deterministic_gzip(raw):
    """No filename, timestamp, or platform-dependent OS byte in the header."""
    target = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=target, mtime=0, compresslevel=9) as handle:
        handle.write(raw)
    return target.getvalue()


def save_hit(output, hit, task=None):
    """An identity is evidence even if its surrounding task later fails."""
    if not isinstance(hit, dict) or not verify_triple(hit.get('xyz')):
        raise ValueError('discovery failed independent integer cube verification')
    xyz = sorted(hit['xyz'], key=int)
    identity = sha(canonical_json(xyz).encode('ascii'))
    destination = Path(output)/'discoveries'/f'{identity}.json'
    try:
        atomic_json(destination, {'schema': 'math-gambling-mathematical-discovery-v1',
            'engine': ENGINE, 'task': task, 'hit': {**hit, 'xyz': xyz},
            'verification': 'independent integer sum of three cubes equals 114',
            'task_completion_claimed': False})
    except Exception as exc:
        raise RuntimeError(f'EXACT IDENTITY {canonical_json(xyz)} could not be saved: {exc}') from exc
    print('EXACT IDENTITY SAVED: '+canonical_json(xyz), file=sys.stderr, flush=True)
    return destination


def validated_result(result):
    if not isinstance(result, dict) or set(result) != {'task', 'id', 'counters', 'hits', 'digest'}:
        raise ValueError('invalid completed result envelope')
    descriptor = validate_task(result['task'])
    if result['id'] != task_id(descriptor):
        raise ValueError('completed result task ID mismatch')
    if not isinstance(result['counters'], dict) or any(type(v) is not int or v < 0 for v in result['counters'].values()):
        raise ValueError('invalid completed result counters')
    if not isinstance(result['hits'], list):
        raise ValueError('invalid completed result hits')
    if any(not isinstance(hit, dict) or not verify_triple(hit.get('xyz')) for hit in result['hits']):
        raise ValueError('completed result contains an invalid identity')
    body = {key: result[key] for key in ('task', 'id', 'counters', 'hits')}
    if result['digest'] != sha(canonical_json(body).encode('ascii')):
        raise ValueError('completed result digest does not match its contents')
    return descriptor


def load_ledger(data, deadline):
    """Metadata scan only; never replay the whole ledger implicitly."""
    rows, ids = [], set()
    for path in (Path(data)/'receipts/tasks').glob('*/*.json'):
        if time.monotonic() >= deadline:
            raise TimeoutError('wall budget reached while reading verified ledger metadata')
        row = parse(read_bounded(path, MAX_LEDGER_BYTES))
        if (not isinstance(row, dict) or row.get('schema') != 'math-gambling-verified-task-v1'
                or type(row.get('sequence')) is not int or row['sequence'] < 1):
            raise ValueError('export accepts only sequenced verified ledger records')
        validated_result(row['result'])
        if row['result']['id'] in ids:
            raise ValueError('duplicate verified task ID')
        ids.add(row['result']['id'])
        rows.append(row)
    rows.sort(key=lambda row: row['sequence'])
    if [row['sequence'] for row in rows] != list(range(1, len(rows)+1)):
        raise ValueError('verified ledger sequence is not contiguous')
    return rows


def interval_values(curve):
    if (not isinstance(curve, dict) or set(curve) != {'D', 'r', 's', 'qlo', 'qhi', 'minimal_abs_z'}
            or curve['minimal_abs_z'] is not True):
        raise ValueError('invalid completed-curve callback')
    values = []
    for key in ('D', 'r', 's', 'qlo', 'qhi'):
        value = curve[key]
        if type(value) is not str or not DECIMAL.fullmatch(value) or value == '-0':
            raise ValueError('curve coordinates must be canonical bounded decimal strings')
        values.append(int(value))
    d, r, s, lo, hi = values
    if (d < 2 or d % 3 == 0 or not 0 <= r < d or pow(r, 3, d) != 114 % d
            or s != (d if d % 3 == 1 else -d) or hi < lo or hi-lo > 8192):
        raise ValueError('invalid modular root, sign, or bounded inclusive interval')
    return tuple(values)


def merge_intervals(curves):
    """Exact union within one task, grouped by the same (D,r,s)."""
    merged = []
    for d, r, s, lo, hi in sorted(interval_values(curve) for curve in curves):
        if merged and merged[-1][:3] == [d, r, s] and lo <= merged[-1][4]+1:
            merged[-1][4] = max(merged[-1][4], hi)
        else:
            merged.append([d, r, s, lo, hi])
    return [[str(v) for v in interval] for interval in merged]


def execute_kernel(task, output, *, kernel_path=None):
    """Compile the very bytes whose hash is recorded, avoiding stale pyc races."""
    path = Path(kernel_path) if kernel_path else Path(__file__).with_name('search_core.py')
    raw = read_bounded(path, 1024*1024)
    module = types.ModuleType('_math_gambling_coverage_kernel')
    module.__file__ = str(path)
    sys.modules[module.__name__] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    curves = []
    def curve_complete(curve):
        interval_values(curve)
        if len(curves) >= MAX_CURVES:
            raise ValueError('task exceeded bounded curve callback count')
        curves.append(dict(curve))
    result = module.run_task(task, on_hit=lambda hit: save_hit(output, hit, task), on_curve=curve_complete)
    # Rescue any returned hit too, before validating the full replay result.
    for hit in result.get('hits', []) if isinstance(result, dict) else []:
        if isinstance(hit, dict) and verify_triple(hit.get('xyz')):
            save_hit(output, hit, task)
    return {'result': result, 'curves': curves, 'kernel_source_sha256': sha(raw)}


def replay_task(task, output, timeout):
    request = canonical_json(task)
    proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker', str(Path(output).resolve())],
        input=request, text=True, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=timeout, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    if proc.stderr:
        print(proc.stderr[-8192:], file=sys.stderr, end='')
    if proc.returncode:
        raise RuntimeError(f'trusted mathematical replay failed (exit {proc.returncode}); discoveries remain saved')
    if len(proc.stdout.encode('utf-8')) > MAX_RECORD_BYTES:
        raise ValueError('replay response exceeds byte cap')
    return parse(proc.stdout)


def build_record(row, replay, output):
    expected = row['result']
    result = replay.get('result') if isinstance(replay, dict) else None
    if isinstance(result, dict) and isinstance(result.get('hits'), list):
        for hit in result['hits']:
            if isinstance(hit, dict) and verify_triple(hit.get('xyz')):
                save_hit(output, hit, expected['task'])
    validated_result(expected)
    validated_result(result)
    if canonical_json(result) != canonical_json(expected):
        raise ValueError('completed replay differs from the verified ledger result/digest')
    curves = replay.get('curves')
    if not isinstance(curves, list) or len(curves) > MAX_CURVES:
        raise ValueError('invalid bounded completed-curve list')
    source_hash = replay.get('kernel_source_sha256')
    if not isinstance(source_hash, str) or not HEX.fullmatch(source_hash):
        raise ValueError('missing exact kernel-source provenance')
    intervals = merge_intervals(curves)
    positions = sum(interval_values(curve)[4]-interval_values(curve)[3]+1 for curve in curves)
    counters = result['counters']
    if len(curves) != counters.get('curves') or positions != counters.get('quotient_points'):
        raise ValueError('completed callbacks do not account for all replayed curves and q positions')
    return {
        'schema': RECORD_SCHEMA, 'engine': ENGINE, 'sequence': row['sequence'],
        'task': expected['task'], 'task_id': expected['id'], 'result_digest': expected['digest'],
        'ledger_record_sha256': sha(canonical_json(row).encode('ascii')),
        'kernel_source_sha256': source_hash,
        'exporter_source_sha256': sha(Path(__file__).read_bytes()),
        'scope': SCOPE, 'certificate': 'empty-task' if not curves else 'completed-intervals',
        'task_completed': True, 'empty_mathematical_domain': not curves,
        'counters': counters, 'hits': result['hits'],
        'raw_scan_interval_count': len(curves), 'merged_interval_count': len(intervals),
        'q_positions_replayed': str(positions),
        'q_positions_task_local_union': str(sum(int(v[4])-int(v[3])+1 for v in intervals)),
        'interval_columns': ['D', 'r', 's', 'qlo', 'qhi'], 'intervals': intervals,
    }


def publish_record(output, record):
    raw = (canonical_json(record)+'\n').encode('ascii')
    if len(raw) > MAX_RECORD_BYTES:
        raise ValueError('mathematical task record exceeds byte cap')
    compressed = deterministic_gzip(raw)
    digest = sha(compressed)
    filename = f'records/{digest[:2]}/{digest}.json.gz'
    path = Path(output)/filename
    if path.exists():
        if read_bounded(path, MAX_RECORD_BYTES) != compressed:
            raise ValueError('existing immutable mathematical record is corrupt')
    else:
        atomic_bytes(path, compressed)
    return {key: record[key] for key in ('sequence', 'task_id', 'result_digest', 'ledger_record_sha256',
        'kernel_source_sha256', 'certificate', 'raw_scan_interval_count', 'merged_interval_count',
        'q_positions_replayed', 'q_positions_task_local_union')} | {
        'file': filename, 'sha256': digest, 'bytes': len(compressed), 'uncompressed_bytes': len(raw)}


def previous_records(output, rows, deadline):
    path = Path(output)/'index.json'
    if not path.exists():
        return []
    previous = parse(read_bounded(path, MAX_INDEX_BYTES))
    if (not isinstance(previous, dict) or previous.get('schema') != SCHEMA
            or previous.get('engine') != ENGINE or not isinstance(previous.get('records'), list)):
        raise ValueError('invalid prior mathematical index')
    records = previous['records']
    if len(records) > len(rows):
        raise ValueError('verified ledger regressed behind mathematical export')
    for entry, row in zip(records, rows):
        if time.monotonic() >= deadline:
            raise TimeoutError('wall budget reached while validating prior mathematical records')
        if (not isinstance(entry, dict) or entry.get('sequence') != row['sequence']
                or entry.get('task_id') != row['result']['id']
                or entry.get('result_digest') != row['result']['digest']
                or entry.get('ledger_record_sha256') != sha(canonical_json(row).encode('ascii'))):
            raise ValueError('verified ledger changed within the exported prefix')
        counters = row['result']['counters']
        curves, positions = counters.get('curves'), counters.get('quotient_points')
        if (type(curves) is not int or type(positions) is not int
                or entry.get('raw_scan_interval_count') != curves
                or entry.get('q_positions_replayed') != str(positions)
                or entry.get('certificate') != ('empty-task' if curves == 0 else 'completed-intervals')
                or type(entry.get('merged_interval_count')) is not int
                or not 0 <= entry['merged_interval_count'] <= curves
                or not isinstance(entry.get('q_positions_task_local_union'), str)
                or not re.fullmatch(r'0|[1-9][0-9]{0,15}', entry['q_positions_task_local_union'])
                or not 0 <= int(entry['q_positions_task_local_union']) <= positions):
            raise ValueError('prior mathematical descriptor contradicts the replay counters')
        digest = entry.get('sha256')
        if (not isinstance(digest, str) or not HEX.fullmatch(digest)
                or entry.get('file') != f'records/{digest[:2]}/{digest}.json.gz'):
            raise ValueError('invalid mathematical record reference')
        # Verify referenced bytes before extending the index. Decompression is
        # unnecessary: these exact bytes were published only after full replay.
        if sha(read_bounded(Path(output)/entry['file'], MAX_RECORD_BYTES)) != digest:
            raise ValueError('published mathematical record checksum mismatch')
    return records


def make_index(rows, records, last_run):
    empty = sum(entry['certificate'] == 'empty-task' for entry in records)
    return {
        'schema': SCHEMA, 'engine': ENGINE, 'updated_at': stamp(), 'scope': SCOPE,
        'status': 'complete' if len(records) == len(rows) else 'partial',
        'ledger_watermark': len(rows), 'exported_through_sequence': len(records),
        'exported_task_count': len(records), 'pending_task_count': len(rows)-len(records),
        'empty_task_count': empty, 'tasks_with_intervals': len(records)-empty,
        'empty_task_fraction_of_exported': empty/len(records) if records else None,
        'raw_scan_interval_count': sum(entry['raw_scan_interval_count'] for entry in records),
        'merged_interval_count': sum(entry['merged_interval_count'] for entry in records),
        'q_positions_replayed': str(sum(int(entry['q_positions_replayed']) for entry in records)),
        'q_positions_task_local_union': str(sum(int(entry['q_positions_task_local_union']) for entry in records)),
        'global_union_computed': False,
        'records_base_url': 'https://raw.githubusercontent.com/Kuberwastaken/math-gambling/cluster-data/data/math-coverage/',
        'records': records, 'last_run': last_run,
    }


@contextmanager
def output_lock(output):
    """A same-host second writer must not regress the exported prefix."""
    key = sha(str(Path(output).resolve()).encode('utf-8'))
    path = Path(tempfile.gettempdir())/f'math-gambling-math-export-{key}.lock'
    with path.open('a+b') as handle:
        try:
            if os.name == 'nt':
                import msvcrt
                handle.seek(0); handle.write(b'0'); handle.flush(); handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError('another mathematical exporter owns this output directory') from exc
        yield


def export(data, output=None, *, max_tasks=32, seconds=5.0, replay_fn=replay_task):
    output = Path(output) if output is not None else Path(data)/'math-coverage'
    with output_lock(output):
        return _export(data, output, max_tasks=max_tasks, seconds=seconds, replay_fn=replay_fn)


def _export(data, output, *, max_tasks, seconds, replay_fn):
    if type(max_tasks) is not int or not 1 <= max_tasks <= MAX_TASKS:
        raise ValueError(f'max_tasks must be 1..{MAX_TASKS}')
    if type(seconds) not in (int, float) or not 0 < seconds <= 3600:
        raise ValueError('seconds must be finite and in (0,3600]')
    data = Path(data)
    output = Path(output)
    started = time.monotonic()
    deadline = started+seconds
    # Until the entire metadata snapshot is validated, retain any prior index.
    # This operational file never claims new mathematical coverage.
    try:
        rows = load_ledger(data, deadline)
        records = previous_records(output, rows, deadline)
    except Exception as exc:
        atomic_json(output/'last-error.json', {'schema': 'math-gambling-mathematical-export-error-v1',
            'updated_at': stamp(), 'error': str(exc), 'coverage_advanced': False})
        raise
    attempted = 0
    added = 0
    reason = 'ledger-complete'
    error = None
    while len(records) < len(rows):
        remaining = deadline-time.monotonic()
        if attempted >= max_tasks:
            reason = 'task-cap'
            break
        if remaining <= 0.05:
            reason = 'wall-budget'
            break
        row = rows[len(records)]
        attempted += 1
        try:
            replay = replay_fn(row['result']['task'], output, min(TASK_SECONDS, remaining))
            record = build_record(row, replay, output)
            entry = publish_record(output, record)
        except subprocess.TimeoutExpired:
            reason = 'wall-budget' if time.monotonic() >= deadline else 'task-timeout'
            error = f"sequence {row['sequence']} replay timed out; no coverage credited; discoveries remain saved"
            break
        except Exception as exc:
            reason = 'deferred-error'
            error = f"sequence {row['sequence']}: {exc}"
            break
        records.append(entry)
        added += 1
        # Commit each complete record, then its index. A kill can at worst leave
        # an unreferenced immutable file; it cannot publish partial intervals.
        progress = {'attempted_tasks': attempted, 'newly_exported_tasks': added,
            'stop_reason': 'in-progress', 'error': None}
        index_raw = (canonical_json(make_index(rows, records, progress))+'\n').encode('ascii')
        if len(index_raw) > MAX_INDEX_BYTES:
            records.pop()
            added -= 1
            reason, error = 'index-cap', 'mathematical manifest reached its byte cap; shard it before further backfill'
            break
        atomic_bytes(output/'index.json', index_raw)
    last_run = {'attempted_tasks': attempted, 'newly_exported_tasks': added,
        'stop_reason': reason, 'error': error, 'elapsed_seconds': round(time.monotonic()-started, 6)}
    index = make_index(rows, records, last_run)
    raw = (canonical_json(index)+'\n').encode('ascii')
    if len(raw) > MAX_INDEX_BYTES:
        raise ValueError('mathematical manifest reached its byte cap; shard it before further backfill')
    atomic_bytes(output/'index.json', raw)
    if error:
        atomic_json(output/'last-error.json', {'schema': 'math-gambling-mathematical-export-error-v1',
            'updated_at': stamp(), 'error': error, 'coverage_advanced': added > 0})
    else:
        (output/'last-error.json').unlink(missing_ok=True)
    return index


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=ROOT/'data')
    parser.add_argument('--output', type=Path, help='default: DATA/math-coverage')
    parser.add_argument('--max-tasks', type=int, default=32, help='maximum new replay attempts; default32, max4096')
    parser.add_argument('--seconds', type=float, default=5.0, help='wall budget including metadata/replay, plus final atomic writes')
    parser.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker is not None:
        raw = sys.stdin.buffer.read(4097)
        if len(raw) > 4096:
            raise ValueError('worker task input exceeds byte cap')
        task = validate_task(parse(raw))
        answer = execute_kernel(task, args.worker)
        encoded = canonical_json(answer)
        if len(encoded) > MAX_RECORD_BYTES:
            raise ValueError('worker response exceeds byte cap')
        print(encoded)
        return 0
    try:
        index = export(args.data, args.output, max_tasks=args.max_tasks, seconds=args.seconds)
    except Exception as exc:
        print(f'Mathematical export deferred: {exc}', file=sys.stderr)
        return 2
    print(f"Mathematical coverage: {index['exported_task_count']}/{index['ledger_watermark']} tasks; "
          f"{index['empty_task_count']} empty; {index['merged_interval_count']} task-local intervals; "
          f"{index['last_run']['stop_reason']}")
    return 2 if index['last_run']['error'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
