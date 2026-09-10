"""Bounded warmed server replay: matching, retirement, failure and early hits."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import ingest as ig
from search_core import ENGINE, make_task, run_task

READY = ig.canonical({"schema": "math-gambling-replay-ready-v1", "engine": ENGINE})


class ReplayPoolTests(unittest.TestCase):
    def command(self, body):
        return [sys.executable, "-u", "-c", "import json,sys,time\nprint(" + repr(READY) + ",flush=True)\nrequest=json.loads(sys.stdin.readline())\n" + body]

    def test_full_results_match_and_worker_retires_at_batch_limit(self):
        with ig.WarmReplay(max_tasks=2) as replay:
            pids = []
            for row in (0, 128, 256):
                task = make_task("c00", row)
                result, cpu = replay(task)
                self.assertEqual(result, run_task(task))
                self.assertGreater(cpu, 0)
                pids.append(replay.process.pid)
            self.assertEqual(pids[0], pids[1])
            self.assertNotEqual(pids[1], pids[2])
        self.assertIsNone(replay.process)

    def test_wrong_identity_and_oversized_output_are_operational_failures(self):
        scripts = [
            "print(json.dumps({'request_id':request['request_id']+1,'result':{},'cpu_ms':1}),flush=True)",
            "print('x'*70000,flush=True)",
            "print('{not JSON}',flush=True)",
        ]
        for script in scripts:
            with ig.WarmReplay(command=self.command(script)) as replay:
                with self.assertRaises(subprocess.CalledProcessError):
                    replay(make_task("c00", 0))
                self.assertIsNone(replay.process)

    def test_timeout_discards_worker_and_next_task_can_restart(self):
        with ig.WarmReplay(wall_seconds=0.05, command=self.command("time.sleep(60)")) as replay:
            with self.assertRaises(subprocess.TimeoutExpired):
                replay(make_task("c00", 0))
            self.assertIsNone(replay.process)
            replay.command = [sys.executable, str(Path(ig.__file__).resolve()), "--replay-stream"]
            replay.wall_seconds = 6
            task = make_task("c00", 128)
            self.assertEqual(replay(task)[0], run_task(task))

    def test_early_identity_is_preserved_before_a_worker_crash(self):
        # Known k=39 fixture validates persistence control flow, not a solution for114.
        hit = {"xyz": ["-159380", "134476", "117367"]}
        script = "print(json.dumps({'request_id':request['request_id'],'hit':" + repr(hit) + "}),flush=True)\nsys.exit(7)"
        task = make_task("c00", 0)
        result = run_task(task)
        bank = {"schema": "math-gambling-bank-v1", "contributor": {"name": "Fixture", "github": "fixture"},
                "tasks": [{"task": task, "digest": result["digest"]}]}
        source = {"id": "fixture:early", "kind": "fixture"}
        real_exact = ig.exact_triple
        with tempfile.TemporaryDirectory() as temp, ig.WarmReplay(command=self.command(script)) as replay:
            with mock.patch.object(ig, "exact_triple", side_effect=lambda xyz: real_exact(xyz, k=39)):
                audit = ig.process_receipt(bank, source, Path(temp), ig.Budget(), replay=replay)
            self.assertEqual(audit["deferred_reason"], "replay_failed")
            self.assertEqual(audit["next_index"], 0)
            self.assertEqual(audit["accepted_tasks"], [])
            self.assertEqual(len(audit["discoveries"]), 1)
            self.assertEqual(len(list((Path(temp) / "receipts/hits").glob("*/*.json"))), 1)

    @unittest.skipIf(os.name == "nt", "POSIX CPU timer supplements the portable wall timer")
    def test_worker_arms_cpu_timer_for_each_task(self):
        # Shorten the timer only inside the fault fixture; production requests4s.
        script = f"""import sys,time,signal
sys.path.insert(0,{str(Path(ig.__file__).parent)!r})
import ingest,search_core
original_task=search_core.run_task
original_timer=signal.setitimer
def timer(which,seconds):
    assert seconds in (0,4)
    return original_timer(which,0.025 if seconds else 0)
def expensive(task):
    until=time.process_time()+1
    while time.process_time()<until: pass
    return original_task(task)
signal.setitimer=timer
search_core.run_task=expensive
ingest.replay_stream()
"""
        with ig.WarmReplay(command=[sys.executable, "-u", "-c", script]) as replay:
            with self.assertRaises(subprocess.CalledProcessError):
                replay(make_task("c00", 0))
            self.assertIsNone(replay.process)


if __name__ == "__main__":
    unittest.main()
