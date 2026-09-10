"""Exact bounded coverage chunks; all formats retain the original task identities."""
import hashlib
import json
import re
from search_core import ENGINE, make_task, task_id

CONTEXT_SCHEMA = 'math-gambling-coverage-context-v2'
CHUNK_SCHEMA = 'math-gambling-coverage-chunk-v2'
CHUNK_SIZE = 256
CHUNK_BYTES = 32768

def bucket_for(identifier):
    return hashlib.sha256(identifier.encode('ascii')).hexdigest()[:2]

def checked_json(raw, entry, cap):
    if len(raw) > cap or hashlib.sha256(raw).hexdigest() != entry['sha256']:
        raise ValueError('coverage checksum or size mismatch')
    return json.loads(raw)

def checked_id(identifier, context):
    if not isinstance(identifier, str): raise ValueError('invalid coverage identity')
    parts = identifier.split(':')
    if (len(parts) != 4 or parts[:2] != [ENGINE, context]
            or not re.fullmatch(r'0|[1-9][0-9]{0,5}', parts[3])
            or task_id(make_task(context, parts[2], int(parts[3]))) != identifier):
        raise ValueError('invalid coverage identity')
    return identifier

def validate_context(raw, context, entry, cap=8*1024*1024):
    value = checked_json(raw, entry, cap)
    if (not isinstance(value, dict) or set(value) != {'schema','engine','context','buckets'}
            or value['schema'] != CONTEXT_SCHEMA or value['engine'] != ENGINE
            or value['context'] != context or not isinstance(value['buckets'], dict)):
        raise ValueError('invalid chunked coverage context')
    total = 0
    for bucket, chunks in value['buckets'].items():
        if not re.fullmatch('[0-9a-f]{2}', bucket) or not isinstance(chunks, list) or not chunks:
            raise ValueError('invalid coverage bucket')
        seen = set()
        for chunk in chunks:
            if (not isinstance(chunk, dict) or set(chunk) != {'file','sha256','count'}
                    or not isinstance(chunk['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', chunk['sha256'])
                    or chunk['file'] != f"{context}-b{bucket}-{chunk['sha256']}.json"
                    or type(chunk['count']) is not int or not 1 <= chunk['count'] <= CHUNK_SIZE
                    or chunk['file'] in seen):
                raise ValueError('invalid coverage chunk descriptor')
            seen.add(chunk['file']); total += chunk['count']
    if total != entry['count']: raise ValueError('chunked coverage count mismatch')
    return value

def validate_chunk(raw, context, bucket, entry):
    value = checked_json(raw, entry, CHUNK_BYTES)
    if (not isinstance(value, dict) or set(value) != {'schema','engine','context','bucket','tasks'}
            or value['schema'] != CHUNK_SCHEMA or value['engine'] != ENGINE
            or value['context'] != context or value['bucket'] != bucket):
        raise ValueError('invalid coverage chunk')
    ids = value['tasks']
    if not isinstance(ids, list) or len(ids) != entry['count'] or len(ids) > CHUNK_SIZE:
        raise ValueError('invalid coverage chunk count')
    previous = ''
    for identifier in ids:
        checked_id(identifier, context)
        if identifier <= previous or bucket_for(identifier) != bucket:
            raise ValueError('duplicate, unsorted or misrouted coverage identity')
        previous = identifier
    return frozenset(ids)
