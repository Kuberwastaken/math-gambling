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
from publish_snapshot import git, REMOTE, FILES

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
    for key in snapshot['totals'].keys() & previous['totals'].keys():
        if int(snapshot['totals'][key]) < int(previous['totals'][key]):
            raise ValueError('Refusing a cumulative counter regression')


def receive(payload):
    snapshot, _ = validate_pair(payload)
    with tempfile.TemporaryDirectory(prefix='math-gambling-public-') as temp:
        checkout = Path(temp)/'repo'
        git('clone','--quiet','--depth','1',REMOTE,str(checkout))
        previous = json.loads((checkout/FILES[0]).read_text())
        ensure_newer(snapshot, previous)
        if snapshot['snapshot_id'] == previous.get('snapshot_id'):
            print('Snapshot already published.'); return
        for name in FILES:
            atomic_json(checkout/name, payload[name])
        git('config','user.name','math-gambling snapshot',cwd=checkout)
        git('config','user.email','Kuberwastaken@users.noreply.github.com',cwd=checkout)
        git('add','--',*FILES,cwd=checkout)
        changed = git('diff','--cached','--name-only',cwd=checkout).stdout.splitlines()
        if sorted(changed) != sorted(FILES):
            raise ValueError('Expected exactly two changed public files')
        git('commit','-m','Publish timestamped Mac observation from personal VPS',cwd=checkout)
        for attempt in range(3):
            try:
                git('push','origin','HEAD:main',cwd=checkout)
                print('Published public Mac snapshot through ai-vps.'); return
            except subprocess.CalledProcessError:
                if attempt == 2: raise
                git('fetch','origin','main',cwd=checkout)
                latest = json.loads(git('show','origin/main:'+FILES[0],cwd=checkout).stdout)
                ensure_newer(snapshot, latest)
                if latest.get('snapshot_id') == snapshot['snapshot_id']:
                    print('Snapshot already published.'); return
                git('rebase','origin/main',cwd=checkout)


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
