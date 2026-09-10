#!/usr/bin/env python3
"""Create a sanitized scientific archive, excluding operational state by path/type."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

TEXT_SUFFIXES = {'.py', '.c', '.h', '.gp', '.md', '.json', '.jsonl'}
PRIVATE_KEYS = {'pid', 'ppid', 'session_pid', 'worker_pid', 'controller_pid', 'host',
                'hostname', 'username', 'home', 'token', 'api_key', 'password',
                'session_started', 'session_deadline', 'power', 'free_GiB'}
SKIP_NAMES = {'status.json', 'process.json', 'process.log', 'heartbeat-health.json',
              'monitoring.json', 'writer.lock', 'STOP', 'SOLUTION.json'}

def sha(data): return hashlib.sha256(data).hexdigest()

def selection(path, relative):
    if path.is_symlink(): return 'symlink or machine-specific runtime link'
    if any(x in relative.parts for x in ('bin', '__pycache__', 'journals', 'discoveries')):
        return 'runtime binaries, caches, journals, or discovery records'
    if any(x.endswith(('.sqlite3', '.sqlite3-wal', '.sqlite3-shm', '.lock', '.dylib', '.pyc'))
           for x in relative.parts): return 'operational database, lock, or compiled artifact'
    if path.name in SKIP_NAMES: return 'machine/process state or separately allowlisted snapshot'
    if path.suffix == '.log': return 'raw runtime log; bounded public observations exported separately'
    if str(relative) == 'vendor/pari-2.17.4.tar.gz': return None
    if path.name in ('LICENSE', 'COPYING', 'NOTICE', 'Makefile', 'makefile'): return None
    if path.suffix not in TEXT_SUFFIXES: return 'non-scientific or unsupported artifact type'
    if path.stat().st_size > 2_000_000: return 'large raw artifact; retained locally'
    return None

def sanitize(text, lab, project, relative, mapping):
    # Preserve functional, portable links among all included scientific files.
    def link(match):
        dest = match[1]
        if dest.startswith(('https:', 'http:', '#', 'mailto:')):
            return match[0]
        if dest.startswith(str(lab) + '/'):
            target = dest[len(str(lab)) + 1:]
            if target in mapping:
                dest = os.path.relpath(target, relative.parent.as_posix())
            else:
                dest = os.path.relpath('../../docs/ARCHIVE.md', relative.parent.as_posix())
        elif dest.startswith(str(project) + '/'):
            dest = os.path.relpath('../../docs/ARCHIVE.md', relative.parent.as_posix())
        elif not dest.startswith('/'):
            target = os.path.normpath(str(relative.parent / dest.split('#')[0]))
            # Two historical phase3 ML links refer to unchanged phase2 evidence.
            earlier = target.replace('phase3/', 'phase2/', 1)
            if target not in mapping and earlier in mapping:
                dest = os.path.relpath(earlier, relative.parent.as_posix())
            elif target not in mapping:
                dest = os.path.relpath('../../docs/ARCHIVE.md', relative.parent.as_posix())
        return '](' + dest + ')'
    text = re.sub(r'\]\(([^)]+)\)', link, text)
    text = text.replace(str(lab), '.')
    text = text.replace(str(project), 'LOCAL_WORKSPACE')
    text = re.sub(r'/Users/[^\s\"\'<>\)]+', 'LOCAL_PATH', text)
    text = re.sub(r'/home/[^\s\"\'<>\)]+', 'LOCAL_PATH', text)
    text = re.sub(r'/private/var/folders/[^\s\"\'<>\)]+', 'TEMP_PATH', text)
    text = re.sub(r'/var/folders/[^\s\"\'<>\)]+', 'TEMP_PATH', text)
    text = re.sub(r'/private/tmp/[^\s\"\'<>\)]+', 'TEMP_PATH', text)
    text = re.sub(r'(?i)\b(PID|PPID)(\s*[:=]?\s*)\d+', r'\1\2[redacted]', text)
    return text

def clean_json(value, cleaner):
    if isinstance(value, dict):
        return {cleaner(str(key)): clean_json(item, cleaner) for key, item in value.items()
                if key not in PRIVATE_KEYS and not str(key).lower().endswith(('_pid', '_pids'))}
    if isinstance(value, list): return [clean_json(item, cleaner) for item in value]
    if isinstance(value, str): return cleaner(value)
    return value

def archive(source, destination):
    lab, dest = Path(source).resolve(), Path(destination).resolve()
    if dest == lab or lab in dest.parents: raise ValueError('Never write inside the live laboratory')
    project = lab.parent.parent
    selected, excluded = [], []
    # lstat avoids following a runtime symlink to a machine-local library.
    for path in sorted(lab.rglob('*')):
        if not path.is_file() and not path.is_symlink(): continue
        relative = path.relative_to(lab)
        reason = selection(path, relative)
        if reason:
            excluded.append({'source': relative.as_posix(), 'bytes': path.lstat().st_size, 'reason': reason})
        else: selected.append((path, relative))
    mapping = {str(relative) for _, relative in selected}
    entries = []
    for path, relative in selected:
        original = path.read_bytes()
        cleaner = lambda text: sanitize(text, lab, project, relative, mapping)
        if path.suffix == '.gz':
            public = original
        elif path.suffix == '.json':
            public = (json.dumps(clean_json(json.loads(original), cleaner), indent=2,
                                 ensure_ascii=False, allow_nan=False) + '\n').encode()
        elif path.suffix == '.jsonl':
            rows = [json.dumps(clean_json(json.loads(line), cleaner), ensure_ascii=False,
                               allow_nan=False) for line in original.decode().splitlines() if line.strip()]
            public = ('\n'.join(rows) + '\n').encode()
        else:
            public = cleaner(original.decode()).encode()
        out = dest / relative
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(public)
        entries.append({'source': relative.as_posix(), 'archive': relative.as_posix(),
                        'original_sha256': sha(original), 'archived_sha256': sha(public),
                        'original_bytes': len(original), 'archived_bytes': len(public),
                        'sanitized': original != public})
    manifest = {'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
                'source_label': 'three-cubes-lab', 'files': entries, 'excluded': excluded,
                'note': 'Original hashes identify local source bytes. Sanitized bytes may differ. '
                        'Historical validation is evidence for its recorded source version, '
                        'not a fresh claim about this relocated archive.'}
    (dest / 'ARCHIVE_MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    result = archive(args.source, args.destination)
    print(json.dumps({'included': len(result['files']), 'excluded': len(result['excluded']),
                      'archived_bytes': sum(x['archived_bytes'] for x in result['files'])}))
