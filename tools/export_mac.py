#!/usr/bin/env python3
"""Opt-in, read-only export of allowlisted campaign observations; never opens SQLite."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

COUNTERS = (
    'generator_inputs', 'curve_checks', 'quotient_points', 'exact_tests',
    'excluded_mod243', 'excluded_parity', 'unsupported_D', 'noninvertible_C',
    'outside_norm_shell', 'signed_congruence_exclusions',
)
STATES = {'running', 'starting', 'stopping', 'stopped', 'paused', 'complete',
          'completed', 'solution_found', 'error', 'drain_error', 'unknown'}
LIMITATIONS = [
    'Timestamped Mac observation; the browser does not run or control this campaign.',
    'Selective finite coefficient domains, not a complete coordinate-height region.',
    'Curve-interval checks can revisit a root in disjoint quotient bands.',
    'Noninvertible coefficients and unsupported divisors are unresolved inputs.',
    'Learning measures conditional root-exposure throughput, not discovery probability.',
    'The audit covers its own earlier timestamp, not every subsequently completed job.',
]
LOG_LINE = re.compile(r'^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ) ([a-z_]+): '
                      r'([\d,]+) curve checks; (\d+) verified solutions\s*$')

def utc(value):
    if not isinstance(value, str):
        raise ValueError('Expected an ISO timestamp')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timestamp needs a timezone')
    return result.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')

def integer(value, signed=False):
    if type(value) is int:
        n = value
    elif isinstance(value, str) and len(value) <= 1000 and re.fullmatch(r'-?(0|[1-9]\d*)', value):
        n = int(value)
    else:
        raise ValueError('Counters and coordinates must be exact integers')
    if not signed and n < 0:
        raise ValueError('Negative counter')
    return str(n)

def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) else None

def read_json(path):
    if path.stat().st_size > 2_000_000:
        raise ValueError('Snapshot input exceeds the size limit')
    with path.open(encoding='utf-8') as stream:
        return json.load(stream)

def sample(status):
    if not isinstance(status, dict) or not isinstance(status.get('totals'), dict):
        raise ValueError('Not a campaign status')
    totals = {key: integer(status['totals'][key]) for key in COUNTERS if key in status['totals']}
    if 'curve_checks' not in totals:
        raise ValueError('Missing curve count')
    jobs = status.get('jobs', {})
    return {'updated_utc': utc(status['updated_utc']),
            'state': status.get('state') if status.get('state') in STATES else 'unknown',
            'totals': totals,
            'jobs': {key: integer(jobs[key]) for key in ('complete', 'running') if key in jobs}}

def identities(records):
    if not isinstance(records, list):
        raise ValueError('Solutions must be a list')
    result = set()
    for record in records:
        if isinstance(record, dict) and all(k in record for k in ('x', 'y', 'z')):
            record = [record[k] for k in ('x', 'y', 'z')]
        if not isinstance(record, (list, tuple)) or len(record) != 3:
            raise ValueError('Unrecognized solution identity')
        values = tuple(sorted(int(integer(value, signed=True)) for value in record))
        if sum(value ** 3 for value in values) != 114:
            raise ValueError('Claimed solution fails exact arithmetic for 114')
        result.add(values)
    return [[str(value) for value in triple] for triple in sorted(result)]

def audit_record(raw):
    if not isinstance(raw, dict):
        return None
    stamp = raw.get('audited_utc') or raw.get('observed_utc') or raw.get('checked_utc')
    body = raw.get('audit', raw)
    if not isinstance(body, dict) or not stamp:
        return None
    result = {'observed_utc': utc(stamp)}
    if body.get('database_integrity') in ('ok', 'failed'):
        result['database_integrity'] = body['database_integrity']
    for key in ('model_observations_reconcile', 'allocation_accounting_reconciles',
                'reserved_tiles_disjoint_and_gapless', 'source_identity_matches'):
        value = body.get(key, raw.get(key))
        if type(value) is bool:
            result[key] = value
    if 'source_identity_matches' not in result and type(raw.get('sources_match')) is bool:
        result['source_identity_matches'] = raw['sources_match']
    for key in ('complete_tiles', 'unfinished_tiles', 'epoch_start_job'):
        if key in body:
            result[key] = integer(body[key])
    return result if 'database_integrity' in result else None

def checkpoint_samples(raw):
    """Only known wrappers; arbitrary nested private fields are never copied."""
    if not isinstance(raw, dict):
        return []
    result = []
    for value in (raw, raw.get('state'), raw.get('status'), raw.get('previous_session')):
        if isinstance(value, dict) and 'updated_utc' in value and 'totals' in value:
            result.append(sample(value))
    return result

def compact_history(records, limit=300):
    # Prefer the richer genuine record when a log and a status share a timestamp.
    unique = {}
    for entry in records:
        clean = sample(entry)
        old = unique.get(clean['updated_utc'])
        if old is None or len(clean['totals']) > len(old['totals']):
            unique[clean['updated_utc']] = clean
    ordered = sorted(unique.values(), key=lambda x: x['updated_utc'])
    for prior, current in zip(ordered, ordered[1:]):
        for key in prior['totals'].keys() & current['totals'].keys():
            if int(current['totals'][key]) < int(prior['totals'][key]):
                raise ValueError('Historical counter regression; refusing to fabricate a continuous series')
    if len(ordered) > limit:
        ordered = [ordered[i * (len(ordered) - 1) // (limit - 1)] for i in range(limit)]
    return ordered

def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.' + path.name + '.', delete=False) as stream:
            name = stream.name
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
        name = None
    finally:
        if name is not None:
            Path(name).unlink(missing_ok=True)

def export(source, output, now=None):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output == source or source in output.parents:
        raise ValueError('Output must be outside the running laboratory')
    campaign = source / 'phase3/runs/campaign'
    status = read_json(campaign / 'status.json')
    latest = sample(status)
    records = []
    existing = output / 'mac-history.json'
    if existing.exists():
        previous = read_json(existing)
        if previous.get('schema_version') != 1:
            raise ValueError('Unknown history schema')
        records.extend(previous.get('samples', []))
    if (output / 'mac.json').exists():
        previous = read_json(output / 'mac.json')
        if utc(previous['updated_utc']) > latest['updated_utc']:
            raise ValueError('Refusing to replace a newer public observation')
    log = campaign / 'process.log'
    if log.exists():
        if log.stat().st_size > 32_000_000:
            raise ValueError('Log exceeds bounded export size; rotate locally before exporting')
        with log.open(encoding='utf-8', errors='replace') as stream:
            for line in stream:
                match = LOG_LINE.fullmatch(line)
                if match and match[1] <= latest['updated_utc']:
                    records.append({'updated_utc': match[1], 'state': match[2],
                                    'totals': {'curve_checks': match[3].replace(',', '')}, 'jobs': {}})
    checkpoints = sorted((campaign / 'checkpoints').glob('*.json'))
    for path in checkpoints:
        for item in checkpoint_samples(read_json(path)):
            if item['updated_utc'] <= latest['updated_utc']:
                records.append(item)
    records.append(latest)
    history = compact_history(records)
    audits = []
    audit_paths = [campaign / 'heartbeat-health.json',
                   source / 'research-2026-09-09/production-audit.json', *checkpoints]
    for path in audit_paths:
        if path.exists():
            item = audit_record(read_json(path))
            if item and item['observed_utc'] <= latest['updated_utc']:
                audits.append(item)
    audit = max(audits, key=lambda x: x['observed_utc']) if audits else None
    gate = status.get('learning_gate', {})
    enabled = gate.get('enable_model') if type(gate.get('enable_model')) is bool else None
    exported = utc(now or datetime.now(timezone.utc).isoformat())
    rate = {'curve_checks_per_second': None, 'window_seconds': None}
    if len(history) > 1:
        a, b = history[-2:]
        seconds = (datetime.fromisoformat(b['updated_utc'].replace('Z', '+00:00')) -
                   datetime.fromisoformat(a['updated_utc'].replace('Z', '+00:00'))).total_seconds()
        if seconds > 0:
            rate = {'curve_checks_per_second':
                    (int(b['totals']['curve_checks']) - int(a['totals']['curve_checks'])) / seconds,
                    'window_seconds': seconds}
    snapshot = {'schema_version': 1, 'source': 'mac-research-campaign', 'phase': 'phase3',
                'is_live': False, 'exported_utc': exported, **latest,
                'solutions': identities(status.get('solutions', [])), 'audit': audit,
                'learning': {'objective': 'conditional root-exposure throughput',
                             'success_probability': None, 'model_enabled': enabled,
                             'holdout': {'spearman': number(gate.get('spearman')),
                                         'top_quarter_over_baseline': number(gate.get('top_quarter_over_baseline')),
                                         'passed': enabled}},
                'throughput': rate, 'limitations': LIMITATIONS}
    # Matching IDs expose the brief interval between the two atomic replacements.
    snapshot_id = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    snapshot['snapshot_id'] = snapshot_id
    history_file = {'schema_version': 1, 'snapshot_id': snapshot_id, 'exported_utc': exported,
                    'max_samples': 300, 'samples': history}
    atomic_json(output / 'mac-history.json', history_file)
    atomic_json(output / 'mac.json', snapshot)
    return snapshot, history_file

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path, help='Explicit local three-cubes-lab directory')
    parser.add_argument('--output', required=True, type=Path, help='Public data directory outside the laboratory')
    args = parser.parse_args()
    snapshot, history = export(args.source, args.output)
    print(json.dumps({'updated_utc': snapshot['updated_utc'], 'samples': len(history['samples']),
                      'verified_solutions': len(snapshot['solutions'])}))

if __name__ == '__main__':
    main()
