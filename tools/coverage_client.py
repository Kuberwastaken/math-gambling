"""Exact published coverage, checked before dispatch. No probabilistic filter."""
from collections import OrderedDict
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen

from search_core import CONTEXTS, ENGINE, make_task, task_id

UA = 'OpenAI File Downloader, XaiImageApiFetch/1.0'
INDEX_URL = 'https://kuber.studio/math-gambling/data/coverage/index.json'
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


def validate_index(raw):
    try:
        if len(raw) > INDEX_LIMIT:
            raise ValueError('byte cap')
        value = json.loads(raw)
        if value.get('schema') != 'math-gambling-coverage-v1' or value.get('engine') != ENGINE:
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
            if type(shard['count']) is not int or not 0 <= shard['count'] <= SHARD_COUNT_LIMIT:
                raise ValueError('count')
            total += shard['count']
        if total != revision:
            raise ValueError('total count')
        return value
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        raise CoverageError(f'Invalid published coverage index ({exc})') from None


def validate_shard(raw, context, entry):
    try:
        if len(raw) > SHARD_LIMIT or hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('SHA-256 or size')
        shard = json.loads(raw)
        if shard.get('schema') != 'math-gambling-coverage-shard-v1' or shard.get('engine') != ENGINE or shard.get('context') != context:
            raise ValueError('schema/context')
        ids = shard['tasks']
        if not isinstance(ids, list) or len(ids) != entry['count'] or len(ids) > SHARD_COUNT_LIMIT:
            raise ValueError('count')
        previous = ''
        for tid in ids:
            if not isinstance(tid, str) or tid <= previous:
                raise ValueError('unsorted/duplicate task IDs')
            match = re.fullmatch(re.escape(ENGINE) + ':' + context + r':(0|[1-9][0-9]{0,14}):(0|[1-9][0-9]{0,5})', tid)
            if not match or task_id(make_task(context, int(match[1]), int(match[2]))) != tid:
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
    def __init__(self, bundled, cache, offline=False, index_url=INDEX_URL, fetch=download):
        self.bundled = Path(bundled)
        self.cache = Path(cache)
        self.offline = offline
        self.index_url = index_url
        self.fetch = fetch
        self.index = None
        self.index_digest = None
        self.loaded = OrderedDict()
        self.known_skips = 0
        if not offline and (self.cache / 'index.json').exists():
            try:
                raw = (self.cache / 'index.json').read_bytes()
                self.index = validate_index(raw)
            except (CoverageError, OSError):
                pass

    def refresh(self):
        try:
            raw = (self.bundled / 'index.json').read_bytes() if self.offline else self.fetch(self.index_url, INDEX_LIMIT)
        except OSError as exc:
            raise CoverageError(f'Bundled coverage snapshot unavailable: {type(exc).__name__}') from None
        candidate = validate_index(raw)
        if self.index and candidate['revision'] < self.index['revision']:
            raise CoverageError('Published coverage revision moved backwards; scheduling paused')
        if self.index and candidate['revision'] == self.index['revision'] and candidate['shards'] != self.index['shards']:
            raise CoverageError('Published coverage changed without a new revision; scheduling paused')
        if not self.offline:
            cache_bytes(self.cache / 'index.json', raw)
        self.index = candidate
        self.index_digest = hashlib.sha256(raw).hexdigest()
        return self.snapshot()

    def snapshot(self):
        if self.index is None:
            raise CoverageError('Coverage must be loaded before dispatch')
        return {'mode': 'bundled-offline' if self.offline else 'published-online',
                'revision': self.index['revision'], 'sha256': self.index_digest,
                'updated_at': self.index['updated_at']}

    def contains(self, task):
        if self.index is None:
            raise CoverageError('Coverage must be loaded before dispatch')
        tid = task_id(task)
        context = task['context']
        entry = self.index['shards'][context]
        # An index entry with zero records cannot exclude any candidate.
        if entry['count'] == 0:
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
                    ids = validate_shard(path.read_bytes(), context, entry)
                    break
                except (CoverageError, OSError):
                    continue
            if ids is None:
                if self.offline:
                    raise CoverageError(f'Bundled {context} coverage shard is missing or corrupt')
                raw = self.fetch(self.index_url.rsplit('/', 1)[0] + '/' + key, SHARD_LIMIT)
                ids = validate_shard(raw, context, entry)
                cache_bytes(self.cache / key, raw)
            self.loaded[key] = ids
            while len(self.loaded) > 8:
                self.loaded.popitem(last=False)
        if tid in ids:
            self.known_skips += 1
            return True
        return False
