#!/usr/bin/env python3
"""Export public Mac observations; optionally publish only to cluster-data.

The reviewed local exporter and receiver are used. No executable code is loaded
from the data branch, and no live source or private database is pushed.
"""
from pathlib import Path
import argparse
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UA = 'OpenAI File Downloader, XaiImageApiFetch/1.0'
REMOTE = 'https://github.com/Kuberwastaken/math-gambling.git'
BRANCH = 'cluster-data'
FILES = ['data/mac.json', 'data/mac-history.json']


def run(args, cwd=None, **kw):
    return subprocess.run(args, cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kw)


def git(*args, cwd=None):
    return run(['git', '-c', 'http.userAgent=' + UA, *args], cwd=cwd)


def main():
    from export_mac import export
    from publish_snapshot_vps import receive, validate_pair
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True,
                        help='Original three-cubes-lab root (read only)')
    parser.add_argument('--push', action='store_true',
                        help='Publish the two public files to cluster-data')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='math-gambling-export-') as temporary:
        payload = dict(zip(FILES, export(args.source, Path(temporary))))
        validate_pair(payload)
        if args.push:
            receive(payload)
        else:
            print('Snapshot validated locally; nothing written to main or pushed.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f'Snapshot publication failed ({type(exc).__name__}); no force push attempted.')
