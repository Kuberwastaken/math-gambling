#!/usr/bin/env python3
"""Send public observations to the user-designated personal-work VPS over SSH.

Only two allowlisted JSON snapshots leave the Mac. Git publication runs on ai-vps
through its normal configuration; no hooks, credentials, or machine policy change.
The caller supplies scheduling. This module never starts a search worker.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from export_mac import export, sample, compact_history, identities, utc, atomic_json, LIMITATIONS
from publish_snapshot import git, REMOTE, BRANCH, FILES

MAX_BYTES = 2_000_000
REMOTE_COMMAND = 'cd /Users/kuber.mehta/Projects/math-gambling && python3.12 tools/publish_snapshot_vps.py --receive'
SNAPSHOT_KEYS = {'schema_version','source','phase','is_live','exported_utc','updated_utc',
                 'state','totals','jobs','solutions','audit','learning','throughput','limitations','snapshot_id'}


def validate_pair(payload):
    if not isinstance(payload, dict) or set(payload) != set(FILES):
        raise ValueError('Expected exactly the two public snapshot paths')
    snapshot, history = (payload[name] for name in FILES)
    if not isinstance(snapshot, dict) or set(snapshot) != SNAPSHOT_KEYS:
        raise ValueError('Unknown snapshot fields')
    if (snapshot['schema_version'] != 1 or snapshot['source'] != 'mac-research-campaign'
            or snapshot['phase'] != 'phase3' or snapshot['is_live'] is not False):
        raise ValueError('Unknown snapshot schema or origin')
    identifier = snapshot['snapshot_id']
    if not isinstance(identifier, str) or not re.fullmatch('[0-9a-f]{64}', identifier):
        raise ValueError('Invalid snapshot identity')
    content = {k:v for k,v in snapshot.items() if k != 'snapshot_id'}
    expected = hashlib.sha256(json.dumps(content, sort_keys=True, allow_nan=False).encode()).hexdigest()
    if identifier != expected:
        raise ValueError('Snapshot digest mismatch')
    clean = sample(snapshot)
    if any(snapshot[k] != v for k,v in clean.items()):
        raise ValueError('Snapshot contains noncanonical counters or private fields')
    if identities(snapshot['solutions']) != snapshot['solutions'] or snapshot['limitations'] != LIMITATIONS:
        raise ValueError('Invalid identities or limitations')
    utc(snapshot['exported_utc'])
    if not isinstance(history, dict) or set(history) != {'schema_version','snapshot_id','exported_utc','max_samples','samples'}:
        raise ValueError('Unknown history fields')
    if (history['schema_version'] != 1 or history['snapshot_id'] != identifier
            or history['exported_utc'] != snapshot['exported_utc'] or history['max_samples'] != 300):
        raise ValueError('Snapshot pair does not match')
    rows = history['samples']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 300:
        raise ValueError('History exceeds its bound')
    if compact_history(rows) != rows or rows[-1] != clean:
        raise ValueError('History is not canonical or does not end at the snapshot')
    return snapshot, history


def ensure_newer(snapshot, previous):
    if utc(snapshot['updated_utc']) < utc(previous['updated_utc']):
        raise ValueError('Refusing to replace a newer public snapshot')
    if (utc(snapshot['updated_utc']) == utc(previous['updated_utc'])
            and utc(snapshot['exported_utc']) < utc(previous['exported_utc'])):
        raise ValueError('Refusing an older export of the same observation')
    if not previous['totals'].keys() <= snapshot['totals'].keys():
        raise ValueError('Refusing to discard a published cumulative counter')
    for key in previous['totals']:
        if int(snapshot['totals'][key]) < int(previous['totals'][key]):
            raise ValueError('Refusing a cumulative counter regression')
    if not {tuple(row) for row in previous['solutions']} <= {tuple(row) for row in snapshot['solutions']}:
        raise ValueError('Refusing to discard a published exact identity')


def merge_pair(payload, previous=None):
    """Retain published observations, compacting only at the documented 300 cap."""
    snapshot, history = validate_pair(payload)
    if previous is None:
        return payload
    prior_snapshot, prior_history = validate_pair(previous)
    ensure_newer(snapshot, prior_snapshot)
    records = {row['updated_utc']: row for row in prior_history['samples']}
    for row in history['samples']:
        old = records.get(row['updated_utc'])
        if old is not None:
            if any(old['totals'][key] != row['totals'][key]
                   for key in old['totals'].keys() & row['totals'].keys()):
                raise ValueError('Conflicting historical counters at the same timestamp')
            # A sparse log entry must not erase a richer published observation.
            row = {**row, 'totals': {**old['totals'], **row['totals']},
                   'jobs': {**old['jobs'], **row['jobs']}}
        records[row['updated_utc']] = row
    # The final observation remains exactly the canonical snapshot sample.
    records[snapshot['updated_utc']] = sample(snapshot)
    merged = {**history, 'samples': compact_history(list(records.values()))}
    result = {FILES[0]: snapshot, FILES[1]: merged}
    validate_pair(result)
    return result


def read_previous(checkout):
    paths = [checkout / name for name in FILES]
    for path in paths:
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError('Snapshot paths must be regular files')
    exists = [path.exists() for path in paths]
    if not any(exists):
        return None  # Explicitly permitted first seed of the two optional Mac files.
    if not all(exists):
        raise ValueError('Published snapshot pair is incomplete')
    payload = {}
    for name, path in zip(FILES, paths):
        with path.open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError('Published snapshot exceeds limit')
        payload[name] = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite number')))
    validate_pair(payload)
    return payload


def receive(payload):
    validate_pair(payload)
    with tempfile.TemporaryDirectory(prefix='math-gambling-public-') as temp:
        checkout = Path(temp) / 'repo'
        # A missing data branch is an error: never fall back to the default branch.
        git('clone', '--quiet', '--depth', '1', '--single-branch', '--branch', BRANCH,
            REMOTE, str(checkout))
        git('config', 'user.name', 'math-gambling snapshot', cwd=checkout)
        git('config', 'user.email', 'Kuberwastaken@users.noreply.github.com', cwd=checkout)
        for attempt in range(3):
            # Always merge into the latest accepted history, including after a
            # concurrent ledger or snapshot publisher wins the normal push race.
            merged = merge_pair(payload, read_previous(checkout))
            for name in FILES:
                atomic_json(checkout / name, merged[name])
            git('add', '--', *FILES, cwd=checkout)
            changed = git('diff', '--cached', '--name-only', cwd=checkout).stdout.splitlines()
            if not changed:
                print('Snapshot already published.'); return
            if not set(changed) <= set(FILES):
                raise ValueError('Unexpected staged path outside the public snapshot pair')
            git('commit', '-m', 'Publish timestamped Mac observation', cwd=checkout)
            try:
                git('push', 'origin', 'HEAD:' + BRANCH, cwd=checkout)
                print('Published public Mac snapshot to cluster-data.'); return
            except subprocess.CalledProcessError:
                if attempt == 2:
                    raise
                git('fetch', '--no-tags', 'origin',
                    '+refs/heads/' + BRANCH + ':refs/remotes/origin/' + BRANCH, cwd=checkout)
                # This is our disposable clone. Rebuild the two-file change on
                # the current tip instead of rebasing stale observation bytes.
                git('reset', '--hard', 'origin/' + BRANCH, cwd=checkout)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,help='Read-only Mac laboratory path')
    parser.add_argument('--push',action='store_true',help='Explicitly publish through the designated ai-vps host')
    parser.add_argument('--receive',action='store_true',help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.receive:
        if args.source or args.push: parser.error('Receiver does not accept sender options')
        raw = sys.stdin.buffer.read(MAX_BYTES+1)
        if len(raw) > MAX_BYTES: raise ValueError('Snapshot payload exceeds limit')
        payload = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite number')))
        receive(payload); return
    if args.source is None: parser.error('--source is required')
    with tempfile.TemporaryDirectory(prefix='math-gambling-export-') as temp:
        snapshot, history = export(args.source, Path(temp))
        payload = dict(zip(FILES, (snapshot,history)))
        validate_pair(payload)
        raw = json.dumps(payload, allow_nan=False).encode()
        if len(raw) > MAX_BYTES: raise ValueError('Snapshot payload exceeds limit')
        if not args.push:
            print(f'Validated public snapshot: {len(raw)} bytes. Nothing sent.'); return
        result = subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',
                                 'ai-vps',REMOTE_COMMAND],input=raw,check=True,
                                stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
        print(result.stdout.decode().strip())


if __name__ == '__main__':
    try: main()
    except (ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(f'Public snapshot publication failed ({type(exc).__name__}); no force push attempted.')
