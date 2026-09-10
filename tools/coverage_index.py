#!/usr/bin/env python3
"""Publish exact completed-task membership from the trusted replay ledger."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import hashlib
from pathlib import Path
import re

from ingest import ROOT, atomic_json, now, parse_json, read_json
from search_core import CONTEXTS, ENGINE, task_id, validate_task
from coverage_format import CONTEXT_SCHEMA, CHUNK_SCHEMA, CHUNK_SIZE, CHUNK_BYTES, bucket_for, validate_context, validate_chunk

SCHEMA = "math-gambling-coverage-v2"
LEGACY_SCHEMA = "math-gambling-coverage-v1"
SHARD_SCHEMA = "math-gambling-coverage-shard-v1"
CONTEXT_IDS = tuple(c["id"] for c in CONTEXTS)
MAX_INDEX_BYTES = 128 * 1024
MAX_SHARD_BYTES = 8 * 1024 * 1024
MAX_SHARD_TASKS = 100_000


def validate_id(identifier, context):
    if not isinstance(identifier, str) or len(identifier) > 100:
        raise ValueError("coverage task ID must be text")
    parts = identifier.split(":")
    if len(parts) != 4 or parts[:2] != [ENGINE, context] or not re.fullmatch(r"0|[1-9][0-9]*", parts[3]):
        raise ValueError("coverage task ID has the wrong engine or context")
    descriptor = validate_task(dict(version=1, engine=parts[0], context=parts[1], row=parts[2], block=int(parts[3])))
    if task_id(descriptor) != identifier:
        raise ValueError("noncanonical coverage task ID")
    return identifier


def _bounded_json(path, limit):
    with Path(path).open("rb") as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("coverage file exceeds its size limit")
    return raw, parse_json(raw.decode("utf-8"), limit)


def read_coverage(directory):
    """Check a published snapshot before relying on it for monotonicity."""
    directory = Path(directory)
    _, manifest = _bounded_json(directory / "index.json", MAX_INDEX_BYTES)
    if (not isinstance(manifest, dict) or set(manifest) !=
            {"schema", "engine", "revision", "verified_task_count", "updated_at", "shards"}
            or manifest["schema"] not in (SCHEMA, LEGACY_SCHEMA) or manifest["engine"] != ENGINE
            or type(manifest["revision"]) is not int or manifest["revision"] < 0
            or manifest["verified_task_count"] != manifest["revision"]
            or type(manifest["verified_task_count"]) is not int
            or not isinstance(manifest["updated_at"], str)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", manifest["updated_at"])
            or not isinstance(manifest["shards"], dict)
            or set(manifest["shards"]) != set(CONTEXT_IDS)):
        raise ValueError("invalid completed-task manifest")
    completed = {}
    for context in CONTEXT_IDS:
        entry = manifest["shards"][context]
        if (not isinstance(entry, dict) or set(entry) != {"file", "sha256", "count"}
                or not isinstance(entry["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])
                or entry["file"] != f"{context}-{entry['sha256']}.json"
                or type(entry["count"]) is not int or not 0 <= entry["count"] <= (MAX_SHARD_TASKS if manifest["schema"] == LEGACY_SCHEMA else 2**53-1)):
            raise ValueError("invalid completed-task shard descriptor")
        raw, shard = _bounded_json(directory / entry["file"], MAX_SHARD_BYTES)
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("completed-task shard checksum mismatch")
        if manifest["schema"] == SCHEMA:
            node = validate_context(raw, context, entry, MAX_SHARD_BYTES)
            identifiers = set()
            for bucket, chunks in node['buckets'].items():
                for chunk in chunks:
                    ids = validate_chunk((directory / chunk['file']).read_bytes(), context, bucket, chunk)
                    if identifiers.intersection(ids): raise ValueError('duplicate coverage across chunks')
                    identifiers.update(ids)
            if len(identifiers) != entry['count']: raise ValueError('coverage count mismatch')
            completed[context] = identifiers
            continue
        if (not isinstance(shard, dict) or set(shard) != {"schema", "engine", "context", "tasks"}
                or shard["schema"] != SHARD_SCHEMA or shard["engine"] != ENGINE
                or shard["context"] != context or not isinstance(shard["tasks"], list)
                or len(shard["tasks"]) != entry["count"]):
            raise ValueError("invalid completed-task shard")
        identifiers = [validate_id(identifier, context) for identifier in shard["tasks"]]
        if identifiers != sorted(set(identifiers)):
            raise ValueError("completed-task shard is unsorted or repeats IDs")
        completed[context] = set(identifiers)
    if sum(map(len, completed.values())) != manifest["revision"]:
        raise ValueError("completed-task count does not match its shards")
    return manifest, completed


def publish_coverage(data, tasks=None):
    """Write immutable shards first, then atomically advance the manifest.

    A count is the revision. Old immutable files are retained for cached clients.
    A rejected build cannot truncate a shard or remove prior completed work.
    """
    data = Path(data)
    directory = data / "coverage"
    if tasks is None:
        tasks = [read_json(p) for p in (data / "receipts/tasks").glob("*/*.json")]
    if any(not isinstance(row, dict) or type(row.get("sequence")) is not int for row in tasks):
        raise ValueError("coverage requires integer verified sequence numbers")
    tasks = sorted(tasks, key=lambda row: row["sequence"])
    if [row["sequence"] for row in tasks] != list(range(1, len(tasks) + 1)):
        raise ValueError("coverage requires contiguous verified sequence numbers")
    completed = {context: set() for context in CONTEXT_IDS}
    for row in tasks:
        if row.get("schema") != "math-gambling-verified-task-v1":
            raise ValueError("coverage accepts only verified ledger records")
        descriptor = validate_task(row["result"]["task"])
        identifier = task_id(descriptor)
        if row["result"]["id"] != identifier or identifier in completed[descriptor["context"]]:
            raise ValueError("duplicate or mismatched verified task ID")
        completed[descriptor["context"]].add(identifier)

    previous = None
    if (directory / "index.json").exists():
        previous, old_completed = read_coverage(directory)
        if previous["revision"] > len(tasks) or any(not old_completed[c].issubset(completed[c]) for c in CONTEXT_IDS):
            raise ValueError("completed coverage must never regress or replace earlier IDs")
        if previous["revision"] == len(tasks) and previous['schema'] == SCHEMA:
            return previous

    directory.mkdir(parents=True, exist_ok=True)
    def immutable(prefix, payload, cap):
        stage = directory / f".{prefix}.pending.json"
        atomic_json(stage, payload)
        raw = stage.read_bytes()
        if len(raw) > cap:
            stage.unlink(); raise ValueError('coverage capacity exceeded; manifest was not changed')
        digest = hashlib.sha256(raw).hexdigest()
        filename = f'{prefix}-{digest}.json'
        destination = directory / filename
        if destination.exists():
            if destination.read_bytes() != raw: raise ValueError('existing immutable coverage file is corrupt')
            stage.unlink()
        else: stage.replace(destination)
        return dict(file=filename, sha256=digest)

    # Sequence order fixes sealed chunks permanently. Sorting the entire ID set
    # first would reshuffle old chunks whenever a random new ID is inserted.
    ordered = {c: defaultdict(list) for c in CONTEXT_IDS}
    for task in tasks:
        identifier = task['result']['id']; context = task['result']['task']['context']
        ordered[context][bucket_for(identifier)].append(identifier)
    shards = {}
    for context in CONTEXT_IDS:
        buckets = {}
        for bucket, ids in sorted(ordered[context].items()):
            chunks = []
            for start in range(0, len(ids), CHUNK_SIZE):
                part = sorted(ids[start:start+CHUNK_SIZE])
                payload = dict(schema=CHUNK_SCHEMA, engine=ENGINE, context=context, bucket=bucket, tasks=part)
                chunks.append(dict(**immutable(f'{context}-b{bucket}', payload, CHUNK_BYTES), count=len(part)))
            buckets[bucket] = chunks
        payload = dict(schema=CONTEXT_SCHEMA, engine=ENGINE, context=context, buckets=buckets)
        shards[context] = dict(**immutable(context, payload, MAX_SHARD_BYTES), count=len(completed[context]))
    manifest = dict(schema=SCHEMA, engine=ENGINE, revision=len(tasks), verified_task_count=len(tasks),
                    updated_at=now(), shards=shards)
    # All referenced bytes already exist. The only mutable entry is published last.
    stage = directory / ".index.pending.json"
    atomic_json(stage, manifest)
    if stage.stat().st_size > MAX_INDEX_BYTES:
        stage.unlink()
        raise ValueError("coverage manifest exceeds v1 byte capacity; no manifest was changed")
    stage.replace(directory / "index.json")
    return manifest


def referenced_files(directory, manifest=None):
    """Files required by one complete snapshot, for a standalone runner ZIP."""
    directory = Path(directory)
    if manifest is None: manifest, _ = read_coverage(directory)
    files = {'index.json'}
    for context, entry in manifest['shards'].items():
        files.add(entry['file'])
        if manifest['schema'] == SCHEMA:
            node = validate_context((directory/entry['file']).read_bytes(), context, entry, MAX_SHARD_BYTES)
            files.update(chunk['file'] for chunks in node['buckets'].values() for chunk in chunks)
    return files


def prune_retired(data, *, observed=None):
    """Keep unreferenced bytes for at least 24h; never remove current evidence.

    Clients refresh each minute. Very old suspended clients must refresh if an
    expired shard is unavailable; this cannot turn missing data into coverage.
    """
    directory = Path(data)/'coverage'
    manifest, _ = read_coverage(directory)
    active = referenced_files(directory, manifest)
    stamp = observed or datetime.now(timezone.utc)
    path = directory/'retention.json'
    old = read_json(path, {})
    retired = old.get('retired', {}) if isinstance(old, dict) else {}
    pattern = re.compile(r'c[0-9]{2}(?:-b[0-9a-f]{2})?-[0-9a-f]{64}\.json')
    keep, remove = {}, []
    for file in directory.iterdir():
        if not pattern.fullmatch(file.name) or file.name in active: continue
        try: since = datetime.fromisoformat(retired[file.name])
        except (KeyError, ValueError, TypeError): since = stamp
        if since.tzinfo is None or since > stamp: since = stamp
        if stamp-since >= timedelta(hours=24): remove.append(file)
        else: keep[file.name] = since.isoformat()
    atomic_json(path, {'schema':'math-gambling-coverage-retention-v1','retired':keep})
    for file in remove: file.unlink(missing_ok=True)
    return len(remove)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument('--prune', action='store_true', help='Retire unreferenced coverage files after a 24-hour grace period')
    args = parser.parse_args()
    manifest = publish_coverage(args.data)
    if args.prune: prune_retired(args.data)
    print(f"Coverage revision {manifest['revision']}: 81 exact context shards")
