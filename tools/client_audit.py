"""Durable, local scheduling evidence; never modifies exact task digests."""
from datetime import datetime, timezone
import argparse
import hashlib
import os
import platform
import re
import secrets

from search_core import ENGINE, canonical_json

VERSION = '0.6.1'
RNG_ALGORITHM = 'python-random-mt19937-v1'


def seed_value(value):
    if not re.fullmatch(r'[0-9a-fA-F]{64}', value):
        raise argparse.ArgumentTypeError('--seed must be exactly 64 hexadecimal digits (256 bits)')
    return value.lower()


class RunAudit:
    def __init__(self, out, seed, budgets):
        now = datetime.now(timezone.utc)
        self.id = now.strftime('%Y%m%dT%H%M%S.%fZ') + '-' + secrets.token_hex(4)
        folder = out / 'runs'
        folder.mkdir(parents=True, exist_ok=True)
        self.path = folder / (self.id + '.jsonl')
        self.write('start', version=VERSION, engine=ENGINE, seed=seed,
                   rng=RNG_ALGORITHM, python=platform.python_version(),
                   budgets=budgets, started_at=now.isoformat())

    def write(self, event, **fields):
        with self.path.open('a', encoding='utf-8', newline='\n') as handle:
            handle.write(canonical_json({'event': event, **fields}) + '\n')
            handle.flush()
            os.fsync(handle.fileno())

    def policy(self, weights, epoch, coverage):
        policy = {'epoch': epoch, 'weights': weights}
        self.write('policy', policy=policy, sha256=hashlib.sha256(canonical_json(policy).encode()).hexdigest(), coverage=coverage)
