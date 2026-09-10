#!/usr/bin/env python3
"""Reproduce archived native software in an isolated directory on macOS or Linux.

Requires a C compiler and make. Use --build-pari for the included official source,
or --pari-prefix for an existing PARI installation. No live campaign is accessed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

HERE = Path(__file__).resolve().parent
PARI_SHA = '02651d99c391007d384b3fadbc20abc6916b77036f9e496c99e9ce8688ca4b53'
TARGETS = [
    ('native_search.c', 'bin/native_search'),
    ('campaign_worker.c', 'bin/campaign_worker'),
    ('plane_worker.c', 'bin/plane_worker'),
    ('phase2/offset_worker.c', 'phase2/bin/offset_worker'),
    ('phase3/offset_worker.c', 'phase3/bin/offset_worker'),
    ('experiments/shell/shell_worker.c', 'experiments/shell/shell_worker'),
    ('research-2026-09-09/normalized-sieve/offset_worker.c',
     'research-2026-09-09/normalized-sieve/offset_worker'),
    ('research-2026-09-09/discovery_worker.c', 'research-2026-09-09/discovery_worker'),
]

def run(args, cwd=None):
    subprocess.run([str(arg) for arg in args], cwd=cwd, check=True)

def verify_archive():
    root = HERE / 'archive'
    manifest = json.loads((root / 'ARCHIVE_MANIFEST.json').read_text())
    for item in manifest['files']:
        actual = hashlib.sha256((root / item['archive']).read_bytes()).hexdigest()
        if actual != item['archived_sha256']:
            raise ValueError('Archive hash mismatch: ' + item['archive'])
    return manifest

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=HERE.parent / '.build/reproduction')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--build-pari', action='store_true')
    group.add_argument('--pari-prefix', type=Path)
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--check', action='store_true', help='Verify archive and target sources without compiling')
    args = parser.parse_args()
    if not 1 <= args.jobs <= 16: parser.error('--jobs must be between 1 and 16')
    manifest = verify_archive()
    for source, _ in TARGETS:
        if not (HERE / 'archive' / source).is_file(): raise ValueError('Missing target source')
    if args.check:
        print(json.dumps({'archive_files_verified': len(manifest['files']), 'native_targets': len(TARGETS)}))
        return
    if not (args.build_pari or args.pari_prefix):
        parser.error('Choose --build-pari or --pari-prefix; no implicit machine-local dependencies')
    work = args.workspace.resolve()
    if work == HERE or HERE in work.parents or (work.exists() and any(work.iterdir())):
        parser.error('Choose a new, empty workspace outside research/')
    work.mkdir(parents=True, exist_ok=True)
    lab = work / 'outputs/three-cubes-lab'
    shutil.copytree(HERE / 'archive', lab)
    prefix = args.pari_prefix.resolve() if args.pari_prefix else work / 'pari-install'
    if args.build_pari:
        archive = lab / 'vendor/pari-2.17.4.tar.gz'
        if hashlib.sha256(archive.read_bytes()).hexdigest() != PARI_SHA:
            raise ValueError('Official PARI archive hash mismatch')
        srcdir = work / 'dependency-source'; srcdir.mkdir()
        # The archive bytes are pinned above before any extraction is permitted.
        with tarfile.open(archive) as bundle: bundle.extractall(srcdir)
        src = srcdir / 'pari-2.17.4'
        run(['./Configure', '--without-gmp', '--without-readline', '--graphic=none',
             '--prefix=' + str(prefix)], cwd=src)
        run(['make', '-j' + str(args.jobs), 'all'], cwd=src)
        run(['make', 'install'], cwd=src)
    headers = prefix / 'include'
    if not (headers / 'pari/pari.h').is_file() or not (prefix / 'bin/gp').is_file():
        raise ValueError('PARI prefix needs include/pari/pari.h and bin/gp')
    library_dir = prefix / 'lib'
    if not any(library_dir.glob('libpari.*')):
        raise ValueError('PARI prefix needs lib/libpari')
    # Recreate the historical relative layout inside the isolated workspace.
    prepared = work / 'work/pari-include'; prepared.parent.mkdir(parents=True, exist_ok=True)
    prepared.symlink_to(headers, target_is_directory=True)
    (lab / 'bin').mkdir(exist_ok=True)
    (lab / 'bin/gp').symlink_to(prefix / 'bin/gp')
    for library in library_dir.glob('libpari.*'):
        if library.is_file():
            (lab / 'bin' / library.name).symlink_to(library)
    compiler = os.environ.get('CC', 'cc')
    for source, destination in TARGETS:
        target = lab / destination; target.parent.mkdir(parents=True, exist_ok=True)
        run([compiler, '-O3', '-Wall', '-Wextra', '-I', headers, lab / source,
             '-L', library_dir, '-Wl,-rpath,' + str(library_dir), '-lpari', '-lm', '-o', target])
    print('Built 8 archived native targets in the isolated reproduction workspace.')
    print('Run archived validation scripts there; historical JSON evidence is not a fresh test result.')

if __name__ == '__main__':
    main()
