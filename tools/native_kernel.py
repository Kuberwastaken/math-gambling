"""Bounded streaming bridge to the locally built Rust kernel; no remote code."""
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
from search_core import canonical_json, validate_task, task_id, verify_triple

ROOT = Path(__file__).resolve().parents[1]


def binary_path():
    return ROOT / 'tools' / 'bin' / ('math-gambling-kernel.exe' if os.name == 'nt' else 'math-gambling-kernel')


class NativeKernel:
    def __init__(self):
        path = binary_path()
        if not path.is_file():
            raise RuntimeError('Rust kernel not built. Run python tools/build_native.py first.')
        self.process = subprocess.Popen([str(path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, encoding='ascii')
        self.events = queue.Queue(maxsize=16)
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self):
        try:
            while True:
                line = self.process.stdout.readline(65537)
                self.events.put(line, timeout=10)
                if not line or len(line)>65536:
                    return
        except (OSError, ValueError, queue.Full):
            return

    def close(self):
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(timeout=5)
        for stream in (self.process.stdin, self.process.stdout):
            stream.close()
        self.thread.join(timeout=1)

    def run(self, task, on_hit=None):
        import time
        task = validate_task(task)
        deadline = time.monotonic()+10
        try:
            self.process.stdin.write(canonical_json(task)+'\n')
            self.process.stdin.flush()
            size = 0
            while True:
                line = self.events.get(timeout=max(0.001, deadline-time.monotonic()))
                size += len(line)
                if not line or size>65536 or not line.endswith('\n'):
                    raise RuntimeError('Native worker exited or exceeded result limit; no task accepted')
                message = json.loads(line)
                if message.get('type') == 'identity':
                    hit = message['hit']
                    if not verify_triple(hit.get('xyz')):
                        raise RuntimeError('Native identity failed independent Python verification')
                    if on_hit is not None:
                        on_hit(hit)
                    continue
                if message.get('task') != task or message.get('id') != task_id(task):
                    raise RuntimeError('Native task identity mismatch')
                digest = message.get('digest')
                payload = {key: value for key,value in message.items() if key!='digest'}
                if hashlib.sha256(canonical_json(payload).encode('ascii')).hexdigest()!=digest:
                    raise RuntimeError('Native receipt digest mismatch')
                for hit in message.get('hits', []):
                    if not verify_triple(hit.get('xyz')):
                        raise RuntimeError('Native final identity failed Python verification')
                return message
        except BaseException:
            self.close()
            raise
