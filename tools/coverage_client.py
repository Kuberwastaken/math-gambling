"""Exact published coverage, checked before dispatch. No probabilistic filter.

Two engine versions share one search domain: a v2 task covers the positions of
its eight aligned v1 sub-tasks. The client therefore loads the v1 index and the
optional v2 index (data/coverage/v2/index.json, engine mg114-offset-v2) and
treats a task as covered when its own version's index holds its ID, or the other
version's index holds any overlapping ID. The v2 index is optional: while it is
not published yet, absence means "no v2 coverage", never an exclusion. v1 loading,
bytes and validation are unchanged.
"""
from collections import OrderedDict
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen

from search_core import CONTEXTS, ENGINE, ENGINES, make_task, overlapping_ids, task_id, validate_task
from coverage_format import bucket_for, validate_context, validate_chunk, CHUNK_BYTES

UA = 'OpenAI File Downloader, XaiImageApiFetch/1.0'
INDEX_URL = 'https://kuber.studio/math-gambling/data/coverage/index.json'
V2_SUBDIRECTORY = 'v2'
INDEX_LIMIT = 128 * 1024
SHARD_LIMIT = 8 * 1024 * 1024
SHARD_COUNT_LIMIT = 100_000


class CoverageError(RuntimeError):
    pass


def download(url, cap):
    try:
        request = Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
        with urlopen(request, timeout=8) as response:
            data = response.read(cap + 1)
        if len(data) > cap:
            raise CoverageError('Published coverage exceeds the client byte cap')
        return data
    except CoverageError:
        raise
    except Exception as exc:
        raise CoverageError(f'Coverage download unavailable: {type(exc).__name__}') from None


def validate_index(raw, version=1):
    try:
        if len(raw) > INDEX_LIMIT:
            raise ValueError('byte cap')
        value = json.loads(raw)
        if value.get('schema') not in ('math-gambling-coverage-v1', 'math-gambling-coverage-v2') or value.get('engine') != ENGINES[version]:
            raise ValueError('schema/engine')
        revision = value['revision']
        if type(revision) is not int or revision < 0 or type(value['verified_task_count']) is not int or value['verified_task_count'] != revision:
            raise ValueError('revision')
        if not isinstance(value.get('updated_at'), str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT[0-9:.]+Z', value['updated_at']):
            raise ValueError('timestamp')
        if set(value['shards']) != {c['id'] for c in CONTEXTS}:
            raise ValueError('contexts')
        total = 0
        for context, shard in value['shards'].items():
            digest = shard['sha256']
            if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
                raise ValueError('digest')
            if shard['file'] != f'{context}-{digest}.json':
                raise ValueError('filename')
            if type(shard['count']) is not int or not 0 <= shard['count'] <= (SHARD_COUNT_LIMIT if value['schema'].endswith('-v1') else 2**53-1):
                raise ValueError('count')
            total += shard['count']
        if total != revision:
            raise ValueError('total count')
        return value
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        raise CoverageError(f'Invalid published coverage index ({exc})') from None


def validate_shard(raw, context, entry, version=1):
    try:
        if len(raw) > SHARD_LIMIT or hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('SHA-256 or size')
        shard = json.loads(raw)
        if shard.get('schema') != 'math-gambling-coverage-shard-v1' or shard.get('engine') != ENGINES[version] or shard.get('context') != context:
            raise ValueError('schema/context')
        ids = shard['tasks']
        if not isinstance(ids, list) or len(ids) != entry['count'] or len(ids) > SHARD_COUNT_LIMIT:
            raise ValueError('count')
        previous = ''
        for tid in ids:
            if not isinstance(tid, str) or tid <= previous:
                raise ValueError('unsorted/duplicate task IDs')
            match = re.fullmatch(re.escape(ENGINES[version]) + ':' + context + r':(0|[1-9][0-9]{0,14}):(0|[1-9][0-9]{0,5})', tid)
            if not match or task_id(make_task(context, int(match[1]), int(match[2]), version)) != tid:
                raise ValueError('task ID')
            previous = tid
        return frozenset(ids)
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        raise CoverageError(f'Invalid {context} coverage shard ({exc})') from None


def cache_bytes(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    with temporary.open('wb') as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


class CoverageIndex:
    def __init__(self, bundled, cache, offline=False, index_url=INDEX_URL, fetch=download,
                 version=1, optional=False):
        self.bundled = Path(bundled)
        self.cache = Path(cache)
        self.offline = offline
        self.index_url = index_url
        self.fetch = fetch
        self.version = version
        self.optional = optional
        self.index = None
        self.index_digest = None
        self.loaded = OrderedDict()
        self.contexts = OrderedDict()
        self.known_skips = 0
        self.other = None
        self.unavailable = None
        if not offline and (self.cache / 'index.json').exists():
            try:
                raw = (self.cache / 'index.json').read_bytes()
                self.index = validate_index(raw, self.version)
                self.index_digest = hashlib.sha256(raw).hexdigest()
            except (CoverageError, OSError):
                pass
        if version == 1:
            # The engine v2 index is published separately and may not exist yet.
            # Absence can only cost duplicate work; it never excludes a task.
            base = index_url.rsplit('/', 1)[0]
            self.other = CoverageIndex(self.bundled / V2_SUBDIRECTORY, self.cache / V2_SUBDIRECTORY,
                                       offline=offline, index_url=f'{base}/{V2_SUBDIRECTORY}/index.json',
                                       fetch=fetch, version=2, optional=True)
            self.other.other = self

    def view(self, version):
        """The index that publishes this engine version's own task IDs, if loaded."""
        if version == self.version:
            return self
        if self.other is not None and self.other.version == version:
            return self.other
        return None

    def refresh(self):
        try:
            raw = (self.bundled / 'index.json').read_bytes() if self.offline else self.fetch(self.index_url, INDEX_LIMIT)
        except (OSError, CoverageError) as exc:
            if self.optional:
                # No published index for this engine version yet (or it is briefly
                # unreachable): keep whatever was already validated and continue.
                self.unavailable = f'{type(exc).__name__}: {exc}'
                return self.snapshot() if self.index is not None else None
            if isinstance(exc, CoverageError):
                raise
            raise CoverageError(f'Bundled coverage snapshot unavailable: {type(exc).__name__}') from None
        try:
            candidate = validate_index(raw, self.version)
            if self.index and candidate['revision'] < self.index['revision']:
                raise CoverageError('Published coverage revision moved backwards; scheduling paused')
            if self.index and candidate['revision'] == self.index['revision'] and candidate['shards'] != self.index['shards'] and not (self.index['schema'].endswith('-v1') and candidate['schema'].endswith('-v2')):
                raise CoverageError('Published coverage changed without a new revision; scheduling paused')
        except CoverageError as exc:
            if not self.optional:
                raise
            # An optional index is never trusted unvalidated: the last validated
            # snapshot is kept and the candidate discarded. Missing coverage can
            # only cost duplicate work, so this never pauses the campaign.
            self.unavailable = str(exc)
            return self.snapshot() if self.index is not None else None
        self.unavailable = None
        if not self.offline:
            cache_bytes(self.cache / 'index.json', raw)
        self.index = candidate
        self.index_digest = hashlib.sha256(raw).hexdigest()
        if self.version == 1 and self.other is not None:
            self.other.refresh()
        return self.snapshot()

    def snapshot(self):
        if self.index is None:
            raise CoverageError('Coverage must be loaded before dispatch')
        value = {'mode': 'bundled-offline' if self.offline else 'published-online',
                 'revision': self.index['revision'], 'sha256': self.index_digest,
                 'updated_at': self.index['updated_at']}
        if self.version == 1 and self.other is not None:
            value['engine_v2'] = ({'revision': self.other.index['revision'],
                                   'sha256': self.other.index_digest,
                                   'updated_at': self.other.index['updated_at']}
                                  if self.other.index is not None else None)
        return value

    def contains(self, task):
        """Covered iff this task's own version index holds its ID, or the other
        engine version's index holds an ID whose positions overlap it."""
        version = task['version'] if isinstance(task, dict) and 'version' in task else 1
        own = self.view(version)
        if own is None or own.index is None:
            if self.index is None:
                raise CoverageError('Coverage must be loaded before dispatch')
        if own is not None and own.index is not None and self._member(own, task_id(task), task['context']):
            self.known_skips += 1
            return True
        other = self.view(2 if version == 1 else 1)
        if other is not None and other.index is not None:
            context = task['context']
            for tid in overlapping_ids(validate_task(task)):
                if self._member(other, tid, context):
                    self.known_skips += 1
                    return True
        return False

    @staticmethod
    def _member(view, tid, context):
        """Membership in one view; an optional index that cannot be read is
        treated as holding nothing, which can only cost duplicate work."""
        try:
            return view.member(tid, context)
        except CoverageError:
            if not view.optional:
                raise
            view.unavailable = 'coverage data unreadable'
            return False

    def member(self, tid, context):
        """Exact membership of one task ID in this index's own engine version."""
        if self.index is None:
            raise CoverageError('Coverage must be loaded before dispatch')
        entry = self.index['shards'][context]
        # An index entry with zero records cannot exclude any candidate.
        if entry['count'] == 0 and not (self.index['schema'] == 'math-gambling-coverage-v2' and context in self.contexts):
            return False
        if self.index['schema'] == 'math-gambling-coverage-v2':
            previous = self.contexts.get(context)
            node = previous[1] if previous and previous[0] == entry['sha256'] else None
            if node is None:
                node = self._load(entry, lambda raw: validate_context(raw, context, entry, version=self.version), SHARD_LIMIT)
                if previous:
                    for bucket, old in previous[1]['buckets'].items():
                        next_chunks = node['buckets'].get(bucket, [])
                        if len(next_chunks) < len(old): raise CoverageError('Published coverage removed completed work')
                        for i, before in enumerate(old):
                            after = next_chunks[i]
                            if before == after: continue
                            if i != len(old)-1 or before['count'] == 256 or after['count'] < before['count']:
                                raise CoverageError('Published coverage replaced a sealed chunk')
                            # Historical guards cover retained observations only.
                            # Never fetch an old tail: publication can retire it
                            # after 24h. The publisher checks full ledger monotonicity.
                            old_ids = self.loaded.get(before['file'])
                            if old_ids is None:
                                old_ids = self._cached(before, lambda raw: validate_chunk(raw, context, bucket, before, version=self.version), CHUNK_BYTES)
                            if old_ids is not None:
                                new_ids = self._load(after, lambda raw: validate_chunk(raw, context, bucket, after, version=self.version), CHUNK_BYTES)
                                if not old_ids.issubset(new_ids): raise CoverageError('Published coverage removed completed work')
                self.contexts[context] = (entry['sha256'], node)
                while len(self.contexts) > 8: self.contexts.popitem(last=False)
            bucket = bucket_for(tid)
            for chunk in node['buckets'].get(bucket, []):
                ids = self.loaded.get(chunk['file'])
                if ids is None:
                    ids = self._load(chunk, lambda raw: validate_chunk(raw, context, bucket, chunk, version=self.version), CHUNK_BYTES)
                    self.loaded[chunk['file']] = ids
                self.loaded.move_to_end(chunk['file'])
                while len(self.loaded) > 64: self.loaded.popitem(last=False)
                if tid in ids:
                    return True
            return False
        key = entry['file']
        if key in self.loaded:
            ids = self.loaded.pop(key)
            self.loaded[key] = ids
        else:
            ids = None
            for base in ([self.bundled] if self.offline else [self.cache, self.bundled]):
                path = base / key
                try:
                    ids = validate_shard(path.read_bytes(), context, entry, self.version)
                    break
                except (CoverageError, OSError):
                    continue
            if ids is None:
                if self.offline:
                    raise CoverageError(f'Bundled {context} coverage shard is missing or corrupt')
                raw = self.fetch(self.index_url.rsplit('/', 1)[0] + '/' + key, SHARD_LIMIT)
                ids = validate_shard(raw, context, entry, self.version)
                cache_bytes(self.cache / key, raw)
            self.loaded[key] = ids
            while len(self.loaded) > 8:
                self.loaded.popitem(last=False)
        return tid in ids

    def _cached(self, entry, validator, cap):
        for base in ([self.bundled] if self.offline else [self.cache, self.bundled]):
            try:
                with (base/entry['file']).open('rb') as handle:
                    return validator(handle.read(cap + 1))
            except (ValueError, KeyError, TypeError, OSError): pass
        return None

    def _load(self, entry, validator, cap):
        cached = self._cached(entry, validator, cap)
        if cached is not None: return cached
        if self.offline: raise CoverageError('Bundled coverage chunk missing or corrupt')
        raw = self.fetch(self.index_url.rsplit('/',1)[0]+'/'+entry['file'], cap)
        try: value = validator(raw)
        except (ValueError, KeyError, TypeError) as exc: raise CoverageError(str(exc)) from None
        cache_bytes(self.cache/entry['file'], raw)
        return value
