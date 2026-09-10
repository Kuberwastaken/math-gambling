#!/usr/bin/env python3
"""Bounded, resumable exact-input campaign with online execution-policy learning.

Learning selects equivalent sieve policies. It never certifies an exclusion or
learns a probability of solving 114. Generator coverage is selective in curves.
"""
from __future__ import annotations

import argparse
import concurrent.futures as futures
import contextlib
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
POLICIES = ("fixed", "adaptive")
SCHEMA = 1
STOP = False
NICE_PREFIX = []
PRIMES = [5,7,11,13,17,19,23,31,37,41,43,47,53,59,61]
COUNTERS = dict(generator_inputs="candidates", curve_checks="curves", quotient_points="quotient_points",
                exact_tests="exact_tests", excluded_mod243="rejected_mod243", excluded_parity="rejected_parity",
                unsupported_D="unsupported_D", noninvertible_C="noninvertible_C", symmetry_duplicates="symmetry_rejected")


class WorkerFailure(RuntimeError):
    def __init__(self, message, partial=None, timed_out=False):
        super().__init__(message)
        self.partial = partial
        self.timed_out = timed_out


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w") as out:
        out.write(json.dumps(value, indent=2) + "\n")
        out.flush()
        os.fsync(out.fileno())
    os.replace(tmp, path)


def contexts(include_plane=True):
    # Fixed research allocation, NOT fitted solution probabilities.
    result = []
    for family, family_weight in [("box", .65), ("plane", .35)] if include_plane else [("box", 1.)]:
        for ell, radius in [(1, 50000), (5, 85499), (25, 146201)]:
            if family == "plane":
                radius = 20000000
            total = ((2*radius+1)**2 * (2*(radius//ell)+1) if family == "box"
                     else (2*radius+1)**2*5)
            for lo, hi, weight in [(0, 64, .70), (64, 256, .20), (256, 4096, .10)]:
                result.append(dict(key=f"{family}:{ell}:{radius}:{lo}:{hi}", family=family,
                                   ell=ell, radius=radius, low=lo, high=hi, total=total,
                                   weight=family_weight*weight/3))
    return result


def source_identity(include_plane):
    files = ["campaign.py", "campaign_worker.c", "bin/campaign_worker", "bin/libpari.dylib"]
    if include_plane:
        files += ["plane_worker.c", "bin/plane_worker"]
    return {name: digest(ROOT/name) for name in files}


def connect(path):
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS contexts(key TEXT PRIMARY KEY,spec TEXT NOT NULL,
        cursor INTEGER NOT NULL DEFAULT 0, elapsed REAL NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY,context TEXT NOT NULL,
        start INTEGER NOT NULL,count INTEGER NOT NULL,status TEXT NOT NULL,
        policy TEXT,attempts INTEGER NOT NULL DEFAULT 0,stats TEXT,error TEXT,
        elapsed REAL,created REAL NOT NULL,finished REAL,parent INTEGER,
        UNIQUE(context,start));
    CREATE TABLE IF NOT EXISTS policies(context TEXT NOT NULL,policy TEXT NOT NULL,
        n INTEGER NOT NULL,total_log_rate REAL NOT NULL,last_rate REAL NOT NULL,
        PRIMARY KEY(context,policy));
    CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,at REAL NOT NULL,
        kind TEXT NOT NULL,detail TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS solutions(id INTEGER PRIMARY KEY,job INTEGER,
        xyz TEXT NOT NULL UNIQUE,evidence TEXT NOT NULL,at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS totals(key TEXT PRIMARY KEY,value INTEGER NOT NULL);
    CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status);
    """)
    return db


def event(db, kind, detail):
    db.execute("INSERT INTO events(at,kind,detail) VALUES(?,?,?)",
               (time.time(), kind, canonical(detail)))


def initialize(db, specs, identity, seed):
    config = dict(schema=SCHEMA, contexts=specs, sources=identity, permutation_seed=seed,
                  coverage="finite generator indices and quotient bands; not all curves or a height box")
    row = db.execute("SELECT value FROM meta WHERE key='config'").fetchone()
    if row and json.loads(row[0]) != config:
        raise ValueError("Source or geometry changed: use a new campaign directory.")
    with db:
        if not row:
            db.execute("INSERT INTO meta VALUES('config',?)", (canonical(config),))
            for spec in specs:
                db.execute("INSERT INTO contexts(key,spec) VALUES(?,?)", (spec["key"], canonical(spec)))
        interrupted = db.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0]
        db.execute("UPDATE jobs SET status='pending',policy=NULL WHERE status='running'")
        if interrupted:
            event(db, "recovered_interrupted_jobs", dict(count=interrupted))


def choose_policy(db, key):
    rows = {r["policy"]: r for r in db.execute("SELECT * FROM policies WHERE context=?", (key,))}
    for policy in POLICIES:
        if policy not in rows or rows[policy]["n"] < 3:
            return policy
    total = sum(r["n"] for r in rows.values())
    # UCB on log input throughput, separately within each exact workload context.
    return max(POLICIES, key=lambda p: rows[p]["total_log_rate"]/rows[p]["n"]
               + math.sqrt(2*math.log(total)/rows[p]["n"]))


def choose_job(db, in_flight, target_seconds, max_count):
    pending = db.execute("SELECT * FROM jobs WHERE status='pending' ORDER BY id LIMIT 1").fetchone()
    if pending:
        return dict(pending)
    available = []
    for row in db.execute("SELECT * FROM contexts"):
        spec = json.loads(row["spec"])
        if row["cursor"] < spec["total"]:
            allocated = row["elapsed"] + in_flight.get(row["key"], 0)*target_seconds
            available.append((allocated/spec["weight"], row, spec))
    if not available:
        return None
    _, row, spec = min(available, key=lambda item: (item[0], item[1]["key"]))
    policy_rows = list(db.execute("SELECT last_rate FROM policies WHERE context=?", (row["key"],)))
    estimate = max((r[0] for r in policy_rows), default=4000.)
    count = min(max_count, max(64, int(estimate*target_seconds)), spec["total"]-row["cursor"])
    with db:
        cur = db.execute("INSERT INTO jobs(context,start,count,status,created) VALUES(?,?,?,'pending',?)",
                         (row["key"], row["cursor"], count, time.time()))
        db.execute("UPDATE contexts SET cursor=cursor+? WHERE key=?", (count, row["key"]))
    return dict(db.execute("SELECT * FROM jobs WHERE id=?", (cur.lastrowid,)).fetchone())


def permutation(spec, seed):
    mask = 2**64-1
    def mix(v):
        v = ((v ^ (v >> 30))*0xbf58476d1ce4e5b9) & mask
        v = ((v ^ (v >> 27))*0x94d049bb133111eb) & mask
        return v ^ (v >> 31)
    total = spec["total"]
    v = mix(seed ^ mix(spec["ell"]) ^ mix(spec["radius"]))
    offset = v % total
    stride = mix((v+0x9e3779b97f4a7c15) & mask) % total or 1
    while math.gcd(stride, total) != 1:
        stride = (stride+1) % total or 1
    return stride, offset


def generator_at(spec, seed, index):
    stride, offset = permutation(spec, seed)
    ell, radius = spec["ell"], spec["radius"]
    v = (index*stride+offset) % spec["total"]
    width = 2*radius+1
    if spec["family"] == "box":
        t_width = 2*(radius//ell)+1
        t = v % t_width-radius//ell
        v //= t_width
        b, c = v % width-radius, v//width-radius
        a = ell*t+(-4*b-16*c) % ell
    else:
        t = v % 5-2
        v //= 5
        b, c = v % width-radius, v//width-radius
        residue = (-4*b-16*c) % ell
        numerator = -4848807585839879338*b-23510935004498358840*c-residue*10**18
        denominator = ell*10**18
        a = residue+ell*((2*numerator+denominator)//(2*denominator)+t)
    return [a,b,c]


def validate_stats(stats, spec, job, seed, hits):
    if (stats.get("complete") is not True or stats.get("version") != 1
            or stats.get("mode") != "tile" or stats.get("k") != 114
            or stats.get("policy") != job["policy"]
            or stats.get("kind", "box") != spec["family"]):
        raise ValueError("Unexpected or incomplete worker protocol")
    expected = dict(start=job["start"], count=job["count"], end=job["start"]+job["count"],
                    total=spec["total"], ell=spec["ell"], radius=spec["radius"],
                    ratio=spec["high"], min_ratio=spec["low"], permutation_seed=seed,
                    candidates=job["count"], hits=len(hits))
    expected["permutation_stride"], expected["permutation_offset"] = permutation(spec, seed)
    counters = ["curves", "quotient_points", "exact_tests", "zero_norm", "invalid_d", "unsupported_D",
                "noninvertible_C", "covered", "symmetry_rejected", "rejected_mod243", "rejected_parity", "reorders", "calibration_samples"]
    for name in set(expected) | set(counters):
        if type(stats.get(name)) is not int or stats[name] < 0:
            raise ValueError(f"Invalid integer counter: {name}")
    if any(stats[k] != v for k,v in expected.items()):
        raise ValueError("Worker coverage metadata mismatch")
    if (not isinstance(stats.get("wall_seconds"), (int,float))
            or not math.isfinite(stats["wall_seconds"]) or stats["wall_seconds"] <= 0):
        raise ValueError("Invalid worker time")
    if stats["candidates"] != sum(stats[k] for k in ["zero_norm","invalid_d","unsupported_D","noninvertible_C","covered","curves","symmetry_rejected"]):
        raise ValueError("Generator categories do not account for all inputs")
    filters = stats.get("filters", [])
    if sorted(f.get("prime", -1) for f in filters) != PRIMES or sorted(stats.get("final_order", [])) != PRIMES:
        raise ValueError("Incomplete prime filter list")
    for f in filters:
        for key in ["tested","rejected","calibrated","calibration_rejected"]:
            if type(f.get(key)) is not int or f[key] < 0:
                raise ValueError("Invalid filter accounting")
        if f["rejected"] > f["tested"] or f["calibration_rejected"] > f["calibrated"]:
            raise ValueError("Impossible filter counts")
    if stats["quotient_points"] != (stats["rejected_mod243"]+stats["rejected_parity"]
                                    +sum(f["rejected"] for f in filters)+stats["exact_tests"]):
        raise ValueError("Quotient filters do not account for all positions")
    if stats["hits"] > stats["exact_tests"] or stats["curves"] > stats["quotient_points"]:
        raise ValueError("Impossible verification counts")


def verify_hit(hit, spec, job, seed):
    if int(hit["k"]) != 114:
        raise ValueError("Unexpected target")
    x, y, z = map(int, hit["xyz"])
    d, r, q = (int(hit[k]) for k in ("D", "r", "q"))
    a, b, c = map(int, hit["abc"])
    index, ell = int(hit["index"]), int(hit["ell"])
    if not (sum(v**3 for v in (x,y,z)) == 114 and d == abs(x+y)
            and abs(z) <= min(abs(x),abs(y)) and z == r+d*q
            and 0 <= r < d and pow(r,3,d) == 114 % d
            and ell == spec["ell"] and job["start"] <= index < job["start"]+job["count"]):
        raise ValueError("Hit failed independent integer verification")
    if not (spec["low"]*d < abs(z) <= spec["high"]*d and abs(z) > 10**17
            and (d > 10**19//54 or abs(z) > 10**19)):
        raise ValueError("Hit outside assigned frontier band")
    n = a**3+114*b**3+12996*c**3-342*a*b*c
    if abs(n) != ell*d or (a+4*b+16*c) % ell:
        raise ValueError("Hit does not match its norm generator")
    if [a,b,c] != generator_at(spec, seed, index):
        raise ValueError("Hit generator does not match its deterministic index")
    return list(sorted((x,y,z)))


def execute(job, spec, seed, timeout):
    binary = ROOT/"bin"/("campaign_worker" if spec["family"] == "box" else "plane_worker")
    cmd = NICE_PREFIX + [str(binary), "tile", str(spec["ell"]),
           str(spec["radius"]), str(job["start"]), str(job["count"]), str(spec["high"]),
           job["policy"], str(spec["low"]), str(seed)]
    start = time.monotonic()
    output = ""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        output = result.stdout
        if result.returncode or result.stderr.strip():
            raise RuntimeError(f"Worker failed ({result.returncode}): {result.stderr[-2000:]}")
        records = [json.loads(line) for line in output.splitlines() if line.strip()]
        stat_rows = [r for r in records if r.get("type") == "stats"]
        hits = [r for r in records if r.get("type") == "hit"]
        if len(stat_rows) != 1 or len(records) != len(hits)+1:
            raise ValueError("Missing, duplicated, or unknown worker records")
        stats = stat_rows[0]
        validate_stats(stats, spec, job, seed, hits)
        verified = [verify_hit(hit, spec, job, seed) for hit in hits]
        return dict(stats=stats, hits=hits, verified=verified, elapsed=time.monotonic()-start)
    except Exception as exc:
        if isinstance(exc, subprocess.TimeoutExpired):
            output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        # A correct cube identity remains a discovery even if the process fails
        # later or its coverage metadata is broken. Never discard its stdout.
        partial = dict(hits=[], verified=[], elapsed=time.monotonic()-start,
                       incomplete=True, worker_output=output, error=f"{type(exc).__name__}: {exc}")
        for line in output.splitlines():
            try:
                hit = json.loads(line)
                if not isinstance(hit, dict) or hit.get("type") != "hit" or int(hit["k"]) != 114:
                    continue
                xyz = list(map(int, hit["xyz"]))
                if len(xyz) == 3 and sum(v**3 for v in xyz) == 114:
                    partial["hits"].append(hit)
                    partial["verified"].append(sorted(xyz))
            except (ValueError, KeyError, TypeError, OverflowError):
                continue
        raise WorkerFailure(str(exc), partial, isinstance(exc, subprocess.TimeoutExpired)) from exc


def record_success(db, job, result):
    elapsed = max(result["elapsed"], .000001)
    rate = job["count"]/elapsed
    with db:
        db.execute("UPDATE jobs SET status='complete',stats=?,elapsed=?,finished=? WHERE id=?",
                   (canonical(result["stats"]), elapsed, time.time(), job["id"]))
        db.execute("UPDATE contexts SET elapsed=elapsed+? WHERE key=?", (elapsed, job["context"]))
        for key, field in COUNTERS.items():
            db.execute("INSERT INTO totals(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=value+excluded.value",
                       (key, result["stats"][field]))
        db.execute("""INSERT INTO policies(context,policy,n,total_log_rate,last_rate) VALUES(?,?,1,?,?)
            ON CONFLICT(context,policy) DO UPDATE SET n=n+1,
            total_log_rate=total_log_rate+excluded.total_log_rate,
            last_rate=.7*last_rate+.3*excluded.last_rate""",
                   (job["context"], job["policy"], math.log(rate), rate))
        for hit, xyz in zip(result["hits"], result["verified"]):
            db.execute("INSERT OR IGNORE INTO solutions(job,xyz,evidence,at) VALUES(?,?,?,?)",
                       (job["id"], canonical(xyz), canonical(hit), time.time()))


def record_failure(db, job, exc):
    message = f"{type(exc).__name__}: {exc}"
    with db:
        event(db, "job_failure", dict(job=job["id"], error=message))
        if (isinstance(exc, subprocess.TimeoutExpired) or getattr(exc, "timed_out", False)) and job["count"] > 128:
            # Reuse parent's row for the first half; add exact, disjoint second half.
            half = job["count"]//2
            db.execute("UPDATE jobs SET status='pending',count=?,error=?,policy=NULL WHERE id=?",
                       (half, message, job["id"]))
            db.execute("INSERT INTO jobs(context,start,count,status,created,parent) VALUES(?,?,?,'pending',?,?)",
                       (job["context"], job["start"]+half, job["count"]-half, time.time(), job["id"]))
            return
        db.execute("UPDATE jobs SET status='failed',error=?,finished=? WHERE id=?",
                   (message, time.time(), job["id"]))
    raise RuntimeError(f"Campaign stopped with uncompleted work retained: {message}")


def record_partial_discovery(db, job, partial):
    with db:
        db.execute("UPDATE jobs SET status='partial_solution',error=?,elapsed=?,finished=? WHERE id=?",
                   (partial["error"], partial["elapsed"], time.time(), job["id"]))
        for hit, xyz in zip(partial["hits"], partial["verified"]):
            db.execute("INSERT OR IGNORE INTO solutions(job,xyz,evidence,at) VALUES(?,?,?,?)",
                       (job["id"], canonical(xyz), canonical(hit), time.time()))
        event(db, "solution_rescued_from_incomplete_worker", dict(job=job["id"], error=partial["error"]))


def power_state():
    try:
        r = subprocess.run(["/usr/bin/pmset", "-g", "batt"], capture_output=True, text=True, timeout=3)
        m = re.search(r"(\d+)%;", r.stdout)
        return dict(percent=int(m[1]) if m else None, on_ac="'AC Power'" in r.stdout,
                    discharging="discharging;" in r.stdout, available=r.returncode == 0)
    except (OSError, subprocess.TimeoutExpired):
        return dict(percent=None, on_ac=None, discharging=None, available=False)


def snapshot(db, state, started=None, deadline=None):
    totals = {key:0 for key in COUNTERS}
    totals.update(dict(db.execute("SELECT key,value FROM totals")))
    return dict(state=state, updated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                pid=os.getpid(), session_started=started, session_deadline=deadline,
                totals=totals, jobs={r[0]:r[1] for r in db.execute("SELECT status,count(*) FROM jobs GROUP BY status")},
                solutions=[json.loads(r[0]) for r in db.execute("SELECT xyz FROM solutions")],
                policies=[dict(r) for r in db.execute("SELECT * FROM policies ORDER BY context,policy")],
                limitations=["Selective generator coverage; repeated curves possible.",
                             "Unsupported D and noninvertible C remain unresolved.",
                             "Symmetry skips refer to canonical representatives that may not yet be visited.",
                             "Learning selects execution policies, not proven success probabilities."])


def audit(db):
    for context in db.execute("SELECT * FROM contexts"):
        end = 0
        for row in db.execute("SELECT start,count FROM jobs WHERE context=? ORDER BY start", (context["key"],)):
            if row["start"] != end or row["count"] <= 0:
                raise ValueError(f"Gap or overlap in reserved input tiles for {context['key']}")
            end += row["count"]
        if end != context["cursor"]:
            raise ValueError("Cursor does not match reserved intervals")
    integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise ValueError(integrity)
    recomputed = {key:0 for key in COUNTERS}
    for row in db.execute("SELECT stats FROM jobs WHERE status='complete'"):
        stats = json.loads(row[0])
        for key, field in COUNTERS.items():
            recomputed[key] += stats[field]
    stored = {key:0 for key in COUNTERS}
    stored.update(dict(db.execute("SELECT key,value FROM totals")))
    if recomputed != stored:
        raise ValueError("Stored totals differ from completed job records")
    return dict(database_integrity="ok", reserved_tiles_disjoint_and_gapless=True,
                complete_tiles=db.execute("SELECT count(*) FROM jobs WHERE status='complete'").fetchone()[0],
                unfinished_tiles=db.execute("SELECT count(*) FROM jobs WHERE status!='complete'").fetchone()[0])


def main():
    global STOP, NICE_PREFIX
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["run", "status", "audit"])
    p.add_argument("--directory", type=Path, default=ROOT/"runs"/"campaign")
    p.add_argument("--hours", type=float, default=2)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--seed", type=int, default=114)
    p.add_argument("--target-seconds", type=float, default=1)
    p.add_argument("--timeout", type=float, default=30)
    p.add_argument("--max-count", type=int, default=10000000)
    p.add_argument("--max-jobs", type=int)
    p.add_argument("--box-only", action="store_true")
    p.add_argument("--battery-floor", type=int, default=25)
    args = p.parse_args()
    if not (0 < args.hours <= 24 and 1 <= args.workers <= min(8, os.cpu_count() or 1)
            and 0 < args.target_seconds < args.timeout <= 60 and args.max_count > 0
            and 0 <= args.seed < 2**64 and 0 <= args.battery_floor <= 100
            and (args.max_jobs is None or args.max_jobs > 0)):
        p.error("Invalid duration, resource bound, seed, or batch size")
    args.directory = args.directory.resolve()
    if args.command != "run":
        db = sqlite3.connect(f"file:{args.directory/'campaign.sqlite3'}?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        print(json.dumps(audit(db) if args.command == "audit" else snapshot(db, "inspection"), indent=2))
        return
    args.directory.mkdir(parents=True, exist_ok=True)
    with (args.directory/"writer.lock").open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            p.error("This campaign already has an active writer")
        db = connect(args.directory/"campaign.sqlite3")
        specs = contexts(not args.box_only)
        spec_by_key = {s["key"]:s for s in specs}
        initialize(db, specs, source_identity(not args.box_only), args.seed)
        audit(db)
        if db.execute("SELECT count(*) FROM jobs WHERE status='failed'").fetchone()[0]:
            p.error("Campaign contains a failed job. Inspect its error before resuming.")
        if db.execute("SELECT count(*) FROM solutions").fetchone()[0]:
            print("A verified solution is already recorded; no further jobs scheduled.")
            return
        signal.signal(signal.SIGTERM, lambda *_: globals().__setitem__("STOP", True))
        signal.signal(signal.SIGINT, lambda *_: globals().__setitem__("STOP", True))
        started = time.time()
        deadline = time.monotonic()+args.hours*3600
        deadline_wall = started+args.hours*3600
        state, error, submitted = "running", None, 0
        last_status, last_power = 0., 0.
        power = power_state()
        priority_probe = subprocess.run(["/usr/bin/nice", "-n", "10", "/usr/bin/true"],
                                        capture_output=True, text=True, timeout=3)
        NICE_PREFIX = ["/usr/bin/nice", "-n", "10"] if not priority_probe.returncode and not priority_probe.stderr else []
        with db:
            event(db, "session_started", dict(hours=args.hours, workers=args.workers, power=power,
                                               lowered_priority=bool(NICE_PREFIX)))
        try:
            with futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
                pending = {}
                while True:
                    now = time.monotonic()
                    if now-last_power > 30:
                        power, last_power = power_state(), now
                    low_battery = (power["percent"] is not None and power["percent"] < args.battery_floor
                                   and (power["discharging"] or not power["on_ac"]))
                    paused = low_battery or (args.directory/"PAUSE").exists()
                    stop = STOP or (args.directory/"STOP").exists() or now >= deadline
                    limit = args.max_jobs is not None and submitted >= args.max_jobs
                    in_flight = {}
                    for job in pending.values():
                        in_flight[job["context"]] = in_flight.get(job["context"], 0)+1
                    while not (stop or paused or limit or error) and len(pending) < args.workers:
                        job = choose_job(db, in_flight, args.target_seconds, args.max_count)
                        if job is None:
                            stop = True
                            break
                        job["policy"] = choose_policy(db, job["context"])
                        with db:
                            db.execute("UPDATE jobs SET status='running',policy=?,attempts=attempts+1 WHERE id=?",
                                       (job["policy"], job["id"]))
                        future = pool.submit(execute, job, spec_by_key[job["context"]], args.seed, args.timeout)
                        pending[future] = job
                        in_flight[job["context"]] = in_flight.get(job["context"], 0)+1
                        submitted += 1
                        limit = args.max_jobs is not None and submitted >= args.max_jobs
                    if pending:
                        ready, _ = futures.wait(pending, timeout=.25, return_when=futures.FIRST_COMPLETED)
                        for future in ready:
                            job = pending.pop(future)
                            try:
                                result = future.result()
                                record_success(db, job, result)
                                if result["verified"]:
                                    STOP, state = True, "solution_found"
                                    atomic_json(args.directory/"SOLUTION.json", result)
                            except Exception as exc:
                                partial = getattr(exc, "partial", None)
                                if partial and partial["verified"]:
                                    record_partial_discovery(db, job, partial)
                                    STOP, state = True, "solution_found"
                                    atomic_json(args.directory/"SOLUTION.json", partial)
                                    continue
                                try:
                                    record_failure(db, job, exc)
                                except Exception as fatal:
                                    error = fatal
                    elif stop or limit or error:
                        break
                    else:
                        time.sleep(.25)
                    if now-last_status >= 10:
                        report = snapshot(db, "paused_low_battery" if paused else state, started, deadline_wall)
                        report["power"] = power
                        atomic_json(args.directory/"status.json", report)
                        print(f"{report['updated_utc']} {report['state']}: "
                              f"{report['totals']['curve_checks']:,} curve checks; "
                              f"{len(report['solutions'])} verified solutions", flush=True)
                        last_status = now
            if error:
                state = "failed"
            elif state != "solution_found":
                state = "stopped" if STOP or (args.directory/"STOP").exists() else "session_complete"
            verification = audit(db)
            with db:
                event(db, "session_finished", dict(state=state, audit=verification, error=str(error) if error else None))
            report = snapshot(db, state, started, deadline_wall)
            report["audit"] = verification
            atomic_json(args.directory/"status.json", report)
            print(json.dumps({k:report[k] for k in ["state", "totals", "solutions", "audit"]}, indent=2))
            if error:
                raise error
        finally:
            db.close()


if __name__ == "__main__":
    main()
