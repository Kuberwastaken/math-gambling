"""Bounded browser projections; authoritative ledger/history stay intact."""
import json
from pathlib import Path

HISTORY_POINTS = 128
BYTE_LIMIT = 2 * 1024 * 1024


def project_cluster(report):
    history = report.get('calibration_history', [])
    indices = (range(len(history)) if len(history) <= HISTORY_POINTS else
               sorted({i * (len(history)-1)//(HISTORY_POINTS-1) for i in range(HISTORY_POINTS)}))
    result = {**report, 'calibration_history': [history[i] for i in indices],
              'history_projection': {'total_epochs': len(history), 'displayed_epochs': min(len(history), HISTORY_POINTS),
                                    'method': 'evenly spaced actual epochs including first and latest',
                                    'full_history': 'https://github.com/Kuberwastaken/math-gambling/blob/cluster-data/data/cluster.json'}}
    # Preserve every recent bank: clients use these to reconcile saved receipts.
    raw = (json.dumps(result, separators=(',', ':'), allow_nan=False)+'\n').encode()
    if len(raw) > BYTE_LIMIT:
        raise ValueError('Public cluster projection exceeds 2 MiB; split growing fields before publishing')
    return raw


def publish(source, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(project_cluster(json.loads(Path(source).read_bytes())))
