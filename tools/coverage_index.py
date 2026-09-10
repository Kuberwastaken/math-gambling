#!/usr/bin/env python3
"""Publish exact completed-task membership from the trusted replay ledger."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re

from ingest import ROOT, atomic_json, now, parse_json, read_json
from search_core import CONTEXTS, ENGINE, task_id, validate_task

SCHEMA = "math-gambling-coverage-v1"
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
            or manifest["schema"] != SCHEMA or manifest["engine"] != ENGINE
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
                or type(entry["count"]) is not int or not 0 <= entry["count"] <= MAX_SHARD_TASKS):
            raise ValueError("invalid completed-task shard descriptor")
        raw, shard = _bounded_json(directory / entry["file"], MAX_SHARD_BYTES)
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("completed-task shard checksum mismatch")
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
    if any(len(ids) > MAX_SHARD_TASKS for ids in completed.values()):
        raise ValueError("coverage context exceeds v1 capacity; publish a reviewed finer-shard format")

    previous = None
    if (directory / "index.json").exists():
        previous, old_completed = read_coverage(directory)
        if previous["revision"] > len(tasks) or any(not old_completed[c].issubset(completed[c]) for c in CONTEXT_IDS):
            raise ValueError("completed coverage must never regress or replace earlier IDs")
        if previous["revision"] == len(tasks):
            return previous

    directory.mkdir(parents=True, exist_ok=True)
    shards = {}
    for context in CONTEXT_IDS:
        identifiers = sorted(completed[context])
        payload = dict(schema=SHARD_SCHEMA, engine=ENGINE, context=context, tasks=identifiers)
        stage = directory / f".{context}.pending.json"
        atomic_json(stage, payload)
        raw = stage.read_bytes()
        if len(raw) > MAX_SHARD_BYTES:
            stage.unlink()
            raise ValueError("coverage shard exceeds v1 byte capacity; no manifest was changed")
        digest = hashlib.sha256(raw).hexdigest()
        filename = f"{context}-{digest}.json"
        destination = directory / filename
        if destination.exists():
            if destination.read_bytes() != raw:
                stage.unlink()
                raise ValueError("existing immutable coverage shard is corrupt")
            stage.unlink()
        else:
            stage.replace(destination)
        shards[context] = dict(file=filename, sha256=digest, count=len(identifiers))
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    manifest = publish_coverage(parser.parse_args().data)
    print(f"Coverage revision {manifest['revision']}: 81 exact context shards")
