#!/usr/bin/env python3
"""Overlay and publish generated branches without checking out their code."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import subprocess
import tarfile
import tempfile
from urllib.parse import quote, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
DATA_BRANCH = 'cluster-data'
SITE_BRANCH = 'gh-pages'
GENERATED = (
    'data/cluster.json', 'data/strategy.json', 'data/policy-config.json',
    'data/receipts', 'data/coverage', 'data/readme-progress.svg',
    'data/learning', 'data/math-coverage',
)
DIRECTORIES = {'data/receipts', 'data/coverage', 'data/learning', 'data/math-coverage'}
REQUIRED = {'data/cluster.json', 'data/strategy.json', 'data/coverage/index.json'}
MAIN_URL = 'https://github.com/Kuberwastaken/math-gambling'
UA = 'OpenAI File Downloader, XaiImageApiFetch/1.0'


class BranchError(RuntimeError):
    pass


def git(repo, *args, input=None, env=None, check=True):
    result = subprocess.run(['git', '-c', f'http.userAgent={UA}', '-C', str(repo), *args],
                            input=input, capture_output=True, env=env)
    if check and result.returncode:
        raise BranchError(result.stderr.decode('utf-8', 'replace').strip() or 'Git command failed')
    return result


def commit_oid(repo, ref):
    return git(repo, 'rev-parse', '--verify', '--end-of-options', f'{ref}^{{commit}}').stdout.decode().strip()


def generated(path):
    return path in GENERATED or any(path.startswith(root + '/') for root in DIRECTORIES)


def safe_path(path):
    return (isinstance(path, str) and bool(path) and '\\' not in path
            and not path.startswith('/') and PurePosixPath(path).as_posix() == path
            and all(part not in ('', '.', '..', '.git') for part in path.split('/')))


def entries(repo, ref):
    result = {}
    for record in git(repo, 'ls-tree', '-rz', '--full-tree', ref).stdout.split(b'\0'):
        if not record: continue
        metadata, raw_path = record.split(b'\t', 1)
        path = raw_path.decode('utf-8')
        mode, kind, _oid = metadata.decode('ascii').split()
        if not safe_path(path): raise BranchError(f'Unsafe branch path: {path!r}')
        result[path] = (mode, kind)
    return result


def data_entries(repo, ref, *, bootstrap=False):
    found = entries(repo, ref)
    selected = {}
    for path, (mode, kind) in found.items():
        allowed = generated(path) or path == 'README.md'
        if not allowed:
            if bootstrap: continue
            raise BranchError(f'Data branch contains a non-data path: {path}')
        if mode != '100644' or kind != 'blob':
            raise BranchError(f'Data path must be a regular non-executable file: {path}')
        selected[path] = (mode, kind)
    if not REQUIRED.issubset(selected):
        raise BranchError('Data snapshot is incomplete: ' + ', '.join(sorted(REQUIRED - set(selected))))
    return selected


def export_data(repo, ref, destination, *, bootstrap=False):
    expected = data_entries(repo, ref, bootstrap=bootstrap)
    roots = [root for root in (*GENERATED, 'README.md')
             if any(path == root or path.startswith(root + '/') for path in expected)]
    process = subprocess.Popen(['git', '-C', str(repo), 'archive', '--format=tar', ref, '--', *roots],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    seen = set()
    try:
        with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
            for member in archive:
                if member.isdir(): continue
                if not member.isfile() or member.name not in expected:
                    raise BranchError('Unexpected archive member: ' + member.name)
                target = Path(destination) / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, target.open('wb') as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                seen.add(member.name)
        if process.wait() != 0:
            raise BranchError(process.stderr.read().decode('utf-8', 'replace'))
    finally:
        if process.poll() is None: process.kill(); process.wait()
        process.stdout.close(); process.stderr.close()
    if seen != set(expected): raise BranchError('Git archive omitted required snapshot bytes')
    return seen


def fetch_branch(repo, branch, *, remote='origin', required=True):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', remote):
        raise BranchError('Remote must be a simple configured Git remote name')
    if branch not in (DATA_BRANCH, SITE_BRANCH): raise BranchError('Unsupported generated branch')
    ref = f'refs/heads/{branch}'
    advertised = git(repo, 'ls-remote', '--exit-code', '--heads', remote, ref, check=False)
    if advertised.returncode == 2:
        if required: raise BranchError(f'{remote}/{branch} is missing; explicit initialization is required')
        return None
    if advertised.returncode:
        raise BranchError(advertised.stderr.decode('utf-8', 'replace').strip())
    tracking = f'refs/remotes/{remote}/{branch}'
    git(repo, 'fetch', '--no-tags', '--depth=1', remote, f'+{ref}:{tracking}')
    return commit_oid(repo, tracking)


def state_path(repo):
    directory = Path(git(repo, 'rev-parse', '--absolute-git-dir').stdout.decode().strip())
    return directory / 'math-gambling-overlay.json'


def ensure_destination(repo, relative):
    target = Path(repo)
    for part in PurePosixPath(relative).parts:
        target = target / part
        if target.is_symlink(): raise BranchError(f'Refusing symlink in overlay destination: {relative}')
    return target


def validate_snapshot(data):
    """A coverage index cannot replace the authoritative accepted-task ledger."""
    from coverage_index import read_coverage
    from search_core import task_id, validate_task
    manifest, completed = read_coverage(Path(data) / 'coverage')
    identifiers, sequences = set(), set()
    for path in (Path(data) / 'receipts/tasks').glob('*/*.json'):
        with path.open('rb') as handle: raw = handle.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024: raise BranchError('Accepted-task record exceeds its byte limit')
        row = json.loads(raw)
        if row.get('schema') != 'math-gambling-verified-task-v1' or type(row.get('sequence')) is not int:
            raise BranchError('Invalid accepted-task ledger record')
        identifier = task_id(validate_task(row['result']['task']))
        if (row['result']['id'] != identifier or identifier in identifiers
                or row['sequence'] in sequences): raise BranchError('Duplicate or inconsistent accepted-task record')
        identifiers.add(identifier); sequences.add(row['sequence'])
    expected = set().union(*completed.values())
    if identifiers != expected or sequences != set(range(1, manifest['revision'] + 1)):
        raise BranchError('Accepted-task ledger and exact coverage disagree')
    return manifest


def overlay(repo, ref):
    """Replace only generated roots; never read or execute the branch README."""
    repo = Path(repo).resolve()
    state_path(repo).unlink(missing_ok=True)
    revision = commit_oid(repo, ref)
    with tempfile.TemporaryDirectory(prefix='math-gambling-overlay-') as temporary:
        stage = Path(temporary)
        export_data(repo, revision, stage)
        # Validate the whole imported coverage closure using trusted main code.
        validate_snapshot(stage / 'data')
        for root in GENERATED: ensure_destination(repo, root)
        # A failed replacement must not leave an older successful overlay token
        # authorizing publication from a now-partial working directory.
        state_path(repo).unlink(missing_ok=True)
        for root in GENERATED:
            target, source = repo / root, stage / root
            if target.is_dir(): shutil.rmtree(target)
            elif target.exists(): target.unlink()
            if source.is_dir(): shutil.copytree(source, target)
            elif source.exists(): target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, target)
    metadata = dict(schema='math-gambling-overlay-v1', source=commit_oid(repo, 'HEAD'),
                    data=revision, branch=DATA_BRANCH)
    marker = state_path(repo)
    temporary = marker.with_suffix('.tmp')
    temporary.write_text(json.dumps(metadata) + '\n', encoding='utf-8')
    temporary.replace(marker)
    return metadata


def rewrite_readme_links(text, repo):
    """Generated data stays branch-relative; all source links point at main."""
    def replace(match):
        target = match[2]
        wrapped = target.startswith('<') and target.endswith('>')
        value = target[1:-1] if wrapped else target
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc or not parsed.path or value.startswith('#'): return match[0]
        path = posixpath.normpath(parsed.path.removeprefix('./'))
        if generated(path): return match[0]
        if not safe_path(path): return match[0]
        kind = 'tree' if (Path(repo) / path).is_dir() else 'blob'
        absolute = f'{MAIN_URL}/{kind}/main/{quote(path, safe="/")}'
        absolute = urlunsplit((*urlsplit(absolute)[:3], parsed.query, parsed.fragment))
        return match[1] + ('<' + absolute + '>' if wrapped else absolute) + ')'
    out, fenced = [], False
    for line in text.splitlines(keepends=True):
        if re.match(r'^\s*(```|~~~)', line): fenced = not fenced
        out.append(line if fenced else re.sub(r'(\]\()(<[^>]+>|[^\s)]+)\)', replace, line))
    return ''.join(out)


def render_readme(repo, destination, *, data=None):
    # Imports always resolve beside this trusted main-branch helper, never from
    # the data checkout. The branch README is not used as a template.
    from readme_snapshot import generate
    from learning_readme import update
    destination = Path(destination)
    shutil.copyfile(Path(repo) / 'README.md', destination)
    data = Path(data) if data is not None else Path(repo) / 'data'
    generate(data, destination)
    update(data, destination)
    destination.write_text(rewrite_readme_links(destination.read_text(encoding='utf-8'), repo),
                           encoding='utf-8', newline='\n')


def copy_generated(repo, destination):
    names = set()
    for root in GENERATED:
        source = ensure_destination(repo, root)
        if not source.exists(): continue
        candidates = source.rglob('*') if source.is_dir() else [source]
        for path in candidates:
            if path.is_symlink(): raise BranchError('Generated data contains a symlink: ' + str(path))
            if path.is_dir(): continue
            if not path.is_file(): raise BranchError('Generated data contains a non-file: ' + str(path))
            relative = path.relative_to(repo)
            if any(part.startswith('.') for part in relative.parts): continue
            target = Path(destination) / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            names.add(relative.as_posix())
    if not REQUIRED.issubset(names): raise BranchError('Generated data is incomplete')


def snapshot_commit(repo, directory, parent, message):
    """Build a tree with an isolated Git index; leave main and its index alone."""
    git_dir = git(repo, 'rev-parse', '--absolute-git-dir').stdout.decode().strip()
    with tempfile.TemporaryDirectory(prefix='math-gambling-index-') as temporary:
        env = os.environ.copy()
        env['GIT_INDEX_FILE'] = str(Path(temporary) / 'index')
        command = ['git', '-c', 'core.autocrlf=false', '--git-dir', git_dir, '--work-tree', str(directory)]
        def run(*args):
            result = subprocess.run([*command, *args], cwd=directory, env=env, capture_output=True)
            if result.returncode: raise BranchError(result.stderr.decode('utf-8', 'replace'))
            return result.stdout.decode().strip()
        run('read-tree', '--empty')
        run('add', '--all', '--force', '--', '.')
        tree = run('write-tree')
    if parent and git(repo, 'rev-parse', f'{parent}^{{tree}}').stdout.decode().strip() == tree:
        return parent, False
    args = ['commit-tree', tree]
    if parent: args += ['-p', parent]
    args += ['-m', message]
    env = os.environ.copy()
    env.setdefault('GIT_AUTHOR_NAME', 'Math Gambling verifier')
    env.setdefault('GIT_AUTHOR_EMAIL', '41898282+github-actions[bot]@users.noreply.github.com')
    env.setdefault('GIT_COMMITTER_NAME', env['GIT_AUTHOR_NAME'])
    env.setdefault('GIT_COMMITTER_EMAIL', env['GIT_AUTHOR_EMAIL'])
    return git(repo, *args, env=env).stdout.decode().strip(), True


def publish(repo, branch, directory, parent, *, remote='origin', push=False):
    if branch not in (DATA_BRANCH, SITE_BRANCH): raise BranchError('Unsupported generated branch')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', remote): raise BranchError('Invalid Git remote name')
    commit, changed = snapshot_commit(repo, directory, parent, f'Update {branch} generated snapshot')
    if branch == DATA_BRANCH and parent:
        def immutable_blobs(ref):
            output = git(repo, 'ls-tree', '-rz', '--full-tree', ref, '--',
                         'data/receipts/tasks', 'data/receipts/hits').stdout
            return {record.split(b'\t', 1)[1]: record.split(b'\t', 1)[0]
                    for record in output.split(b'\0') if record}
        before, after = immutable_blobs(parent), immutable_blobs(commit)
        if any(after.get(path) != blob for path, blob in before.items()):
            raise BranchError('Accepted task and discovery records are append-only; publication would alter or remove evidence')
    # No force, rebase, or merge: a concurrent authoritative advance must be
    # fetched and replayed by a later job, never combined file-by-file.
    if push: git(repo, 'push', remote, f'{commit}:refs/heads/{branch}')
    return dict(branch=branch, commit=commit, parent=parent, changed=changed, pushed=push)


def publish_data(repo, *, remote='origin', push=False):
    try: metadata = json.loads(state_path(repo).read_text(encoding='utf-8'))
    except (OSError, ValueError): raise BranchError('Overlay the authoritative data branch before publication') from None
    if metadata.get('source') != commit_oid(repo, 'HEAD') or metadata.get('branch') != DATA_BRANCH:
        raise BranchError('Source changed after overlay; refusing mixed publication')
    with tempfile.TemporaryDirectory(prefix='math-gambling-publish-') as temporary:
        stage = Path(temporary)
        copy_generated(Path(repo), stage)
        validate_snapshot(stage / 'data')
        render_readme(repo, stage / 'README.md')
        return publish(repo, DATA_BRANCH, stage, metadata['data'], remote=remote, push=push)


def init_data(repo, source_ref, *, remote='origin', push=False):
    if fetch_branch(repo, DATA_BRANCH, remote=remote, required=False):
        raise BranchError('cluster-data already exists; use overlay, not initialization')
    with tempfile.TemporaryDirectory(prefix='math-gambling-bootstrap-') as temporary:
        stage = Path(temporary)
        export_data(repo, commit_oid(repo, source_ref), stage, bootstrap=True)
        validate_snapshot(stage / 'data')
        # Data comes from the pinned boundary; the template and attribution
        # configuration still come from trusted current main.
        config = stage / 'data/site-config.json'
        source_config = Path(repo) / 'data/site-config.json'
        if source_config.exists(): shutil.copyfile(source_config, config)
        try: render_readme(repo, stage / 'README.md', data=stage / 'data')
        finally: config.unlink(missing_ok=True)
        return publish(repo, DATA_BRANCH, stage, None, remote=remote, push=push)


def publish_site(repo, directory, *, remote='origin', push=False):
    directory = Path(directory).resolve()
    if not (directory / 'index.html').is_file(): raise BranchError('Built site is missing index.html')
    for path in directory.rglob('*'):
        if path.is_symlink() or not safe_path(path.relative_to(directory).as_posix()):
            raise BranchError('Built site contains an unsafe path')
    parent = fetch_branch(repo, SITE_BRANCH, remote=remote, required=False)
    return publish(repo, SITE_BRANCH, directory, parent, remote=remote, push=push)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--remote', default='origin')
    sub = parser.add_subparsers(dest='command', required=True)
    load = sub.add_parser('overlay'); load.add_argument('--ref'); load.add_argument('--fetch', action='store_true')
    initial = sub.add_parser('init-data'); initial.add_argument('--source-ref', required=True); initial.add_argument('--push', action='store_true')
    data = sub.add_parser('publish-data'); data.add_argument('--push', action='store_true')
    site = sub.add_parser('publish-site'); site.add_argument('--directory', type=Path, default=ROOT/'dist/math-gambling'); site.add_argument('--push', action='store_true')
    args = parser.parse_args(); repo = args.repo.resolve()
    try:
        if args.command == 'overlay':
            state_path(repo).unlink(missing_ok=True)
            ref = fetch_branch(repo, DATA_BRANCH, remote=args.remote) if args.fetch else args.ref
            if not ref: raise BranchError('Specify --fetch or an explicitly pinned --ref')
            result = overlay(repo, ref)
        elif args.command == 'init-data': result = init_data(repo, args.source_ref, remote=args.remote, push=args.push)
        elif args.command == 'publish-data': result = publish_data(repo, remote=args.remote, push=args.push)
        else: result = publish_site(repo, args.directory, remote=args.remote, push=args.push)
    except (BranchError, OSError, ValueError) as exc:
        parser.exit(1, f'Branch publication stopped: {exc}\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__': main()
