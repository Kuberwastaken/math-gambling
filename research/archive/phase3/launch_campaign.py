#!/usr/bin/env python3
"""Start a bounded campaign independently of this terminal, or control its markers."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["start","pause","resume","stop"])
    p.add_argument("--directory", type=Path, default=ROOT/"runs"/"campaign")
    p.add_argument("--hours", type=float, default=24)
    p.add_argument("--workers", type=int, default=12)
    p.add_argument("--allow-idle-sleep", action="store_true")
    args = p.parse_args()
    folder = args.directory.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    if args.command in ("pause","stop"):
        (folder/args.command.upper()).touch()
        print(f"{args.command.capitalize()} requested; in-flight tiles finish within their timeout.")
        return
    if args.command == "resume":
        (folder/"PAUSE").unlink(missing_ok=True)
        print("Pause marker removed. A stopped or completed process requires a new start command.")
        return
    if not (0 < args.hours <= 24 and 1 <= args.workers <= min(32,os.cpu_count() or 1)):
        p.error("Duration must be at most 24 hours; worker count must fit this machine and be at most 32.")
    if (folder/"STOP").exists() or (folder/"PAUSE").exists():
        p.error("Stop/pause marker exists. Remove it deliberately before starting another session.")
    command = [sys.executable, str(ROOT/"campaign.py"), "run", "--directory", str(folder),
               "--hours", str(args.hours), "--workers", str(args.workers)]
    with (folder/"process.log").open("a") as log:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        time.sleep(1)
        if process.poll() is not None:
            p.error(f"Campaign exited during startup ({process.returncode}); inspect {folder/'process.log'}")
        awake_pid = None
        if not args.allow_idle_sleep:
            awake = subprocess.Popen(["/usr/bin/caffeinate","-i","-w",str(process.pid)],
                                     stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
            awake_pid = awake.pid
    record = dict(pid=process.pid, command=command, launched_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
                  caffeinate_pid=awake_pid, directory=str(folder), log=str(folder/"process.log"),
                  note="Prevents idle sleep only; lid closure, shutdown or process termination can interrupt the session.")
    temporary = folder/"process.json.tmp"
    temporary.write_text(json.dumps(record,indent=2)+"\n")
    os.replace(temporary,folder/"process.json")
    print(json.dumps(record,indent=2))


if __name__ == "__main__":
    main()
