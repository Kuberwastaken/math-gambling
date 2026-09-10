#!/usr/bin/env python3
"""Bounded, resumable exact-input campaign with online execution-policy learning.

Learning allocates certified parameter contexts using measured root-exposure
throughput. This proxy is not a learned solution probability.
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
import uuid

ROOT = Path(__file__).resolve().parent
from online_model import Model, evaluate, geometric_mass
from verify_domain import validate_contexts

POLICIES = ("adaptive",)
SCHEMA = 2
MODEL = None
D0 = 10**19//54
STOP = False
NICE_PREFIX = []
PRIMES = [5,7,11,13,17,19,23,31,37,41,43,47,53,59,61]
COUNTERS = dict(generator_inputs="candidates", curve_checks="curves", quotient_points="quotient_points",
                exact_tests="exact_tests", excluded_mod243="rejected_mod243", excluded_parity="rejected_parity",
                unsupported_D="unsupported_D", noninvertible_C="noninvertible_C", outside_norm_shell="outside_shell", signed_congruence_exclusions="rejected_signed")


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
    sync_directory(path.parent)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def identity_hits(output, target=114):
    """Recover exact identities independently of coverage/model metadata."""
    hits, verified = [], []
    for line in output.splitlines():
        try:
            hit = json.loads(line)
            if not isinstance(hit, dict) or hit.get("type") != "hit" or int(hit["k"]) != target:
                continue
            values = hit["xyz"]
            if not isinstance(values, list) or len(values) != 3:
                continue
            if any(type(v) not in (int, str) or not re.fullmatch(r"-?\d+", str(v)) for v in values):
                continue
            xyz = list(map(int, values))
            if sum(v**3 for v in xyz) == target:
                hits.append(hit)
                verified.append(sorted(xyz))
        except (ValueError, KeyError, TypeError, OverflowError):
            continue
    return hits, verified


def preserve_discovery(directory, result, target=114):
    """Identity-addressed, durable evidence precedes all mutable bookkeeping."""
    if (not result.get("hits") or not result.get("verified")
            or len(result["hits"]) != len(result["verified"])):
        raise ValueError("Discovery records must be nonempty paired lists")
    for hit, xyz in zip(result["hits"], result["verified"]):
        actual_hits, actual_xyz = identity_hits(canonical(hit), target)
        if not actual_hits or actual_xyz[0] != xyz:
            raise ValueError("Refusing to persist an unverified identity")
    directory = Path(directory)
    evidence = directory/"discoveries"
    evidence.mkdir(exist_ok=True)
    sync_directory(directory)
    for hit, xyz in zip(result["hits"], result["verified"]):
        key = hashlib.sha256(canonical(dict(k=target,xyz=xyz)).encode()).hexdigest()
        path = evidence/(key+".json")
        if not path.exists():
            atomic_json(path, dict(k=target,xyz=xyz,hit=hit,source_journal=result.get("journal"),
                                   verified_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())))
    atomic_json(directory/"SOLUTION.json", result)


def recover_journals(directory, target=114):
    """Run before source/config/DB checks; damaged metadata cannot hide a hit.

    Complete records preceding a torn final record remain independently usable.
    Incomplete jobs are never marked complete by this recovery path.
    """
    directory = Path(directory)
    recovered = []
    errors = []
    for path in sorted((directory/"journals").glob("*.jsonl")):
        try:
            output = path.read_text(errors="replace")
            hits, verified = identity_hits(output, target)
            if verified:
                recovered.extend(verified)
                result = dict(hits=hits,verified=verified,journal=str(path),incomplete=True,
                              error="Recovered durable worker output before scheduling")
                preserve_discovery(directory, result, target)
        except (OSError, ValueError, TypeError) as exc:
            errors.append(dict(path=str(path),error=str(exc)))
    for path in sorted((directory/"discoveries").glob("*.json")):
        try:
            data = json.loads(path.read_text())
            _, verified = identity_hits(canonical(data.get("hit")), target)
            if not verified:
                raise ValueError("Stored discovery does not verify for the target")
            recovered.extend(verified)
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            errors.append(dict(path=str(path),error=str(exc)))
    if errors:
        print("JOURNAL_RECOVERY_ERRORS "+canonical(errors),file=sys.stderr,flush=True)
        if not recovered:
            raise ValueError("Journal recovery has unresolved read/verification errors; scheduling blocked")
    return sorted({tuple(xyz) for xyz in recovered})


def epoch_start(db):
    row = db.execute("SELECT value FROM meta WHERE key='epoch_start'").fetchone()
    return int(row[0]) if row else 0


def job_digest(db, maximum):
    h = hashlib.sha256()
    for row in db.execute("SELECT * FROM jobs WHERE id<=? ORDER BY id", (maximum,)):
        h.update((canonical(dict(row))+"\n").encode())
    return h.hexdigest()


def contexts():
    result = []
    for ell in [1,5,25]:
        for shape_index,(tlo,thi,radius) in enumerate([(8,31,6000000),(128,511,1500000),(2048,8191,375000)]):
            for shell_index in range(3):
                dlo,dhi = D0*2**shell_index,D0*2**(shell_index+1)
                for band_index,(lo,hi,weight) in enumerate([(0,64,.70),(64,256,.20),(256,4096,.10)]):
                    result.append(dict(key=f"offset:{ell}:{shape_index}:{shell_index}:{lo}:{hi}",
                        family="offset",ell=ell,radius=radius,tlo=tlo,thi=thi,dlo=dlo,dhi=dhi,
                        low=lo,high=hi,total=(2*radius+1)**2,weight=weight/27,
                        shape_index=shape_index,shell_index=shell_index,band_index=band_index))
    return result


def source_identity():
    files = ["campaign.py","offset_worker.c","online_model.py","verify_domain.py",
             "bin/offset_worker","checker.c","../bin/libpari.dylib"]
    return {name:digest(ROOT/name) for name in files}


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
        elapsed REAL,created REAL NOT NULL,finished REAL,parent INTEGER,strategy TEXT,
        UNIQUE(context,start));
    CREATE TABLE IF NOT EXISTS policies(context TEXT NOT NULL,policy TEXT NOT NULL,
        n INTEGER NOT NULL,total_log_rate REAL NOT NULL,last_rate REAL NOT NULL,
        PRIMARY KEY(context,policy));
    CREATE TABLE IF NOT EXISTS allocations(strategy TEXT PRIMARY KEY,elapsed REAL NOT NULL,n INTEGER NOT NULL);
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
    global MODEL
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
    saved = db.execute("SELECT value FROM meta WHERE key='model'").fetchone()
    MODEL = Model.from_dict(json.loads(saved[0])) if saved else Model.initial(specs)



def choose_policy(db, key):
    return "adaptive"


def learning_gate(db):
    row=db.execute("SELECT value FROM meta WHERE key='learning_gate'").fetchone()
    if row:
        return json.loads(row[0])
    records=[]
    for ctx in db.execute("SELECT * FROM contexts"):
        jobs=list(db.execute("SELECT * FROM jobs WHERE context=? AND status='complete' AND id>? ORDER BY id LIMIT 3",(ctx["key"],epoch_start(db))))
        if len(jobs)<3:
            return None
        spec=json.loads(ctx["spec"])
        for job in jobs:
            st=json.loads(job["stats"])
            records.append(dict(spec=spec,elapsed=job["elapsed"],exposure_sum=st["exposure_sum"],rows=job["count"],stats=st))
    gate=evaluate(records)
    if type(gate.get("enable_model")) is not bool:
        raise ValueError("Model evaluation lacks an explicit gate decision")
    with db:
        db.execute("INSERT INTO meta VALUES('learning_gate',?)",(canonical(gate),))
        event(db,"heldout_model_gate",gate)
    return gate


def choose_job(db, in_flight, target_seconds, max_count):
    pending=db.execute("SELECT * FROM jobs WHERE status='pending' ORDER BY id LIMIT 1").fetchone()
    if pending:
        return dict(pending)
    available=[]
    for row in db.execute("SELECT * FROM contexts"):
        spec=json.loads(row["spec"])
        if row["cursor"]<spec["total"]:
            nrow=db.execute("SELECT n FROM policies WHERE context=? AND policy='adaptive'",(row["key"],)).fetchone()
            n=nrow[0] if nrow else 0
            available.append((row,spec,n+in_flight.get(row["key"],0)))
    if not available:
        return None
    bootstrap=[v for v in available if v[2]<3]
    gate=None if bootstrap else learning_gate(db)
    strategy="bootstrap" if bootstrap else "balanced"
    candidates=bootstrap or available
    if bootstrap:
        row,spec,_=min(candidates,key=lambda v:(v[2],v[0]["elapsed"],v[0]["key"]))
    else:
        if gate and gate["enable_model"]:
            allocations=dict(db.execute("SELECT strategy,elapsed FROM allocations WHERE strategy IN ('explore','model')"))
            for active in db.execute("SELECT strategy,count(*) FROM jobs WHERE status='running' GROUP BY strategy"):
                if active[0] in ("explore","model"):
                    allocations[active[0]]=allocations.get(active[0],0)+active[1]*target_seconds
            exploration=allocations.get("explore",0)
            strategy="explore" if exploration<.4*sum(allocations.values()) or not allocations else "model"
        if strategy=="model":
            scores=MODEL.scores([v[1] for v in candidates],in_flight)
            if any(not math.isfinite(scores[v[1]["key"]]) or scores[v[1]["key"]]<0 for v in candidates):
                raise ValueError("Nonfinite or negative model score")
            row,spec,_=max(candidates,key=lambda v:(scores[v[1]["key"]],-v[0]["elapsed"],v[0]["key"]))
        else:
            row,spec,_=min(candidates,key=lambda v:((v[0]["elapsed"]+in_flight.get(v[0]["key"],0)*target_seconds)/v[1]["weight"],v[0]["key"]))
    rate=db.execute("SELECT last_rate FROM policies WHERE context=? AND policy='adaptive'",(row["key"],)).fetchone()
    estimate=rate[0] if rate else 100000/(spec["thi"]-spec["tlo"]+1)/target_seconds
    count=min(max_count,max(1,int(estimate*target_seconds)),spec["total"]-row["cursor"])
    with db:
        cur=db.execute("INSERT INTO jobs(context,start,count,status,created,strategy) VALUES(?,?,?,'pending',?,?)",
                       (row["key"],row["cursor"],count,time.time(),strategy))
        db.execute("UPDATE contexts SET cursor=cursor+? WHERE key=?",(count,row["key"]))
    return dict(db.execute("SELECT * FROM jobs WHERE id=?",(cur.lastrowid,)).fetchone())


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
    b,c=v%width-radius,v//width-radius
    residue=(-4*b-16*c)%ell
    numerator=-4848807585839879338*b-23510935004498358840*c-residue*10**18
    denominator=ell*10**18
    base=residue+ell*((2*numerator+denominator)//(2*denominator))
    return [base,b,c]


def validate_stats(stats, spec, job, seed, hits):
    if (stats.get("complete") is not True or stats.get("version") != 2
            or stats.get("mode") != "row_tile" or stats.get("k") != 114
            or stats.get("policy") != job["policy"]
            or stats.get("kind", "box") != spec["family"]):
        raise ValueError("Unexpected or incomplete worker protocol")
    expected = dict(start=job["start"], count=job["count"], end=job["start"]+job["count"],
                    total=spec["total"], ell=spec["ell"], radius=spec["radius"],
                    ratio=spec["high"], min_ratio=spec["low"], permutation_seed=seed,
                    candidates=job["count"]*(spec["thi"]-spec["tlo"]+1), hits=len(hits),
                    rows=job["count"],tlo=spec["tlo"],thi=spec["thi"],Dlo=spec["dlo"],Dhi=spec["dhi"])
    expected["permutation_stride"], expected["permutation_offset"] = permutation(spec, seed)
    counters = ["curves", "quotient_points", "exact_tests", "zero_norm", "invalid_d", "unsupported_D",
                "noninvertible_C", "covered", "outside_shell", "rejected_signed", "rejected_signed8", "rejected_signed361",
                "eligible_inputs", "empty_rows", "rejected_mod243", "rejected_parity", "reorders", "calibration_samples"]
    for name in set(expected) | set(counters):
        if type(stats.get(name)) is not int or stats[name] < 0:
            raise ValueError(f"Invalid integer counter: {name}")
    if any(stats[k] != v for k,v in expected.items()):
        raise ValueError("Worker coverage metadata mismatch")
    if (not isinstance(stats.get("wall_seconds"), (int,float))
            or not math.isfinite(stats["wall_seconds"]) or stats["wall_seconds"] <= 0):
        raise ValueError("Invalid worker time")
    if stats["candidates"] != sum(stats[k] for k in ["zero_norm","invalid_d","unsupported_D","noninvertible_C","covered","curves","outside_shell","rejected_signed"]):
        raise ValueError("Generator categories do not account for all inputs")
    if stats.get("method") != "inversion" or stats["eligible_inputs"] != stats["candidates"]-stats["outside_shell"]:
        raise ValueError("Invalid shell inversion metadata")
    if (stats["rejected_signed"] != stats["rejected_signed8"]+stats["rejected_signed361"]
            or stats["empty_rows"] > stats["rows"]):
        raise ValueError("Invalid row or signed-filter accounting")
    exposure=stats.get("exposure_sum")
    if type(exposure) not in (int,float) or not math.isfinite(exposure) or exposure<0:
        raise ValueError("Invalid root exposure")
    lower,upper=stats["curves"]*D0/spec["dhi"],stats["curves"]*D0/(spec["dlo"]+1)
    if not lower-1e-8*max(1,lower)<=exposure<=upper+1e-8*max(1,upper):
        raise ValueError("Exposure inconsistent with assigned norm shell")
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
    if n != ell*d or not spec["dlo"]<d<=spec["dhi"] or (a+4*b+16*c) % ell:
        raise ValueError("Hit does not match its norm generator")
    C=b*b-a*c
    B=114*c*c-a*b
    if math.gcd(C,d)!=1 or r!=(B*pow(C,-1,d))%d:
        raise ValueError("Hit root does not match its generator")
    base,b0,c0=generator_at(spec,seed,index)
    if (b!=b0 or c!=c0 or (a-base)%ell or not spec["tlo"]<=(a-base)//ell<=spec["thi"]):
        raise ValueError("Hit generator does not match its deterministic index")
    return list(sorted((x,y,z)))


def execute(job, spec, seed, timeout, journal_directory=None):
    binary=ROOT/"bin"/"offset_worker"
    cmd=NICE_PREFIX+[str(binary),"tile",str(spec["ell"]),str(spec["radius"]),str(spec["tlo"]),str(spec["thi"]),
        str(spec["dlo"]),str(spec["dhi"]),str(job["start"]),str(job["count"]),str(spec["high"]),
        str(spec["low"]),job["policy"],"inversion",str(seed)]
    start = time.monotonic()
    output = ""
    journal = None
    try:
        if journal_directory is None:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            output = result.stdout
        else:
            folder = Path(journal_directory)
            folder.mkdir(exist_ok=True)
            sync_directory(folder.parent)
            journal = folder/f"job-{job['id']}-{uuid.uuid4().hex}.jsonl"
            fd = os.open(journal, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_SYNC, 0o600)
            try:
                sync_directory(folder)
                with os.fdopen(fd, "w") as out:
                    fd = None
                    try:
                        result = subprocess.run(cmd, stdout=out, stderr=subprocess.PIPE, text=True, timeout=timeout)
                    finally:
                        out.flush()
                        os.fsync(out.fileno())
            finally:
                if fd is not None:
                    os.close(fd)
                output = journal.read_text(errors="replace")
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
        return dict(stats=stats, hits=hits, verified=verified, elapsed=time.monotonic()-start,
                    journal=str(journal) if journal else None)
    except Exception as exc:
        if isinstance(exc, subprocess.TimeoutExpired) and journal is None:
            output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        # A correct cube identity remains a discovery even if the process fails
        # later or its coverage metadata is broken. Never discard its stdout.
        partial = dict(hits=[], verified=[], elapsed=time.monotonic()-start,
                       incomplete=True, journal=str(journal) if journal else None,
                       worker_output=output, error=f"{type(exc).__name__}: {exc}")
        partial["hits"],partial["verified"] = identity_hits(output)
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
        db.execute("INSERT INTO allocations VALUES(?,?,1) ON CONFLICT(strategy) DO UPDATE SET elapsed=elapsed+excluded.elapsed,n=n+1",(job.get("strategy") or "balanced",elapsed))
        spec=json.loads(db.execute("SELECT spec FROM contexts WHERE key=?",(job["context"],)).fetchone()[0])
        MODEL.observe(spec,elapsed,result["stats"]["exposure_sum"],job["count"],result["stats"])
        db.execute("INSERT INTO meta VALUES('model',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(canonical(MODEL.to_dict()),))
        for hit, xyz in zip(result["hits"], result["verified"]):
            db.execute("INSERT OR IGNORE INTO solutions(job,xyz,evidence,at) VALUES(?,?,?,?)",
                       (job["id"], canonical(xyz), canonical(hit), time.time()))


def record_failure(db, job, exc):
    message = f"{type(exc).__name__}: {exc}"
    with db:
        event(db, "job_failure", dict(job=job["id"], error=message))
        if (isinstance(exc, subprocess.TimeoutExpired) or getattr(exc, "timed_out", False)) and job["count"] > 1:
            # Reuse parent's row for the first half; add exact, disjoint second half.
            half = job["count"]//2
            db.execute("UPDATE jobs SET status='pending',count=?,error=?,policy=NULL WHERE id=?",
                       (half, message, job["id"]))
            db.execute("INSERT INTO jobs(context,start,count,status,created,parent,strategy) VALUES(?,?,?,'pending',?,?,?)",
                       (job["context"], job["start"]+half, job["count"]-half, time.time(), job["id"],job.get("strategy","balanced")))
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
                epoch_start_job=epoch_start(db),
                epoch_completed_tiles=db.execute("SELECT count(*) FROM jobs WHERE status='complete' AND id>?",(epoch_start(db),)).fetchone()[0],
                allocation=[dict(r) for r in db.execute("SELECT strategy,count(*) AS jobs,sum(elapsed) AS worker_seconds FROM jobs WHERE id>? GROUP BY strategy",(epoch_start(db),))],
                learning_gate=json.loads(db.execute("SELECT value FROM meta WHERE key='learning_gate'").fetchone()[0]) if db.execute("SELECT 1 FROM meta WHERE key='learning_gate'").fetchone() else None,
                limitations=["Selective finite coefficient rows; not all curves or a height box.",
                             "Completed phase2/phase3 tiles share certified distinct (D,r,z) coverage, including separation from phase1.",
                             "Unsupported D and noninvertible C are unresolved inputs, not excluded solutions.",
                             "Learning optimizes conditional root-exposure throughput, not a calibrated discovery probability."])



def audit(db):
    epoch = epoch_start(db)
    configuration = db.execute("SELECT value FROM meta WHERE key='config'").fetchone()
    if not configuration:
        raise ValueError("Coverage ledger has no configuration")
    configuration = json.loads(configuration[0])
    stored_specs = {r['key']:json.loads(r['spec']) for r in db.execute('SELECT key,spec FROM contexts')}
    if stored_specs != {s['key']:s for s in configuration['contexts']}:
        raise ValueError("Stored contexts differ from the immutable configuration")
    history = db.execute("SELECT value FROM meta WHERE key='migration'").fetchone()
    if history:
        certificate = json.loads(history[0])
        if (epoch != certificate['epoch_start_job']
                or job_digest(db, epoch) != certificate['historical_jobs_sha256']
                or configuration['sources'] != certificate['new_sources']):
            raise ValueError("Historical completed records differ from the migration certificate")
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
    arm_totals={}
    allocation_totals={}
    for row in db.execute("SELECT stats,context,count,elapsed,strategy,id FROM jobs WHERE status='complete'"):
        stats = json.loads(row[0])
        for key, field in COUNTERS.items():
            recomputed[key] += stats[field]
        if row['id'] <= epoch:
            continue
        arm=arm_totals.setdefault(row['context'],dict(jobs=0,rows=0,elapsed=0.,exposure=0.))
        arm['jobs']+=1;arm['rows']+=row['count'];arm['elapsed']+=row['elapsed'];arm['exposure']+=stats['exposure_sum']
        alloc=allocation_totals.setdefault(row['strategy'] or 'balanced',dict(n=0,elapsed=0.))
        alloc['n']+=1;alloc['elapsed']+=row['elapsed']
    stored = {key:0 for key in COUNTERS}
    stored.update(dict(db.execute("SELECT key,value FROM totals")))
    if recomputed != stored:
        raise ValueError("Stored totals differ from completed job records")
    state=db.execute("SELECT value FROM meta WHERE key='model'").fetchone()
    if arm_totals and not state:
        raise ValueError("Completed observations missing model journal")
    if state:
        saved=Model.from_dict(json.loads(state[0]))
        for key,arm in saved.arms.items():
            actual=arm_totals.get(key,dict(jobs=0,rows=0,elapsed=0.,exposure=0.))
            for name in actual:
                if not math.isclose(arm[name],actual[name],rel_tol=1e-9,abs_tol=1e-8):
                    raise ValueError("Model observations disagree with completed ledger")
        if set(arm_totals)-set(saved.arms):
            raise ValueError("Model omits a completed context")
    allocations={r['strategy']:dict(n=r['n'],elapsed=r['elapsed']) for r in db.execute("SELECT * FROM allocations")}
    if allocations.keys()!=allocation_totals.keys() or any(not math.isclose(v,allocations[k][name],rel_tol=1e-9,abs_tol=1e-8) for k,values in allocation_totals.items() for name,v in values.items()):
        raise ValueError("Allocation accounting differs from completed ledger")
    return dict(database_integrity="ok", model_observations_reconcile=True,allocation_accounting_reconciles=True,
                epoch_start_job=epoch,
                reserved_tiles_disjoint_and_gapless=True,
                complete_tiles=db.execute("SELECT count(*) FROM jobs WHERE status='complete'").fetchone()[0],
                unfinished_tiles=db.execute("SELECT count(*) FROM jobs WHERE status!='complete'").fetchone()[0])


def main():
    global STOP, NICE_PREFIX
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["run", "status", "audit"])
    p.add_argument("--directory", type=Path, default=ROOT/"runs"/"campaign")
    p.add_argument("--hours", type=float, default=24)
    p.add_argument("--workers", type=int, default=12)
    p.add_argument("--seed", type=int, default=1142)
    p.add_argument("--target-seconds", type=float, default=1)
    p.add_argument("--timeout", type=float, default=30)
    p.add_argument("--max-count", type=int, default=1000000)
    p.add_argument("--max-jobs", type=int)
    p.add_argument("--battery-floor", type=int, default=25)
    args = p.parse_args()
    if not (0 < args.hours <= 24 and 1 <= args.workers <= min(32, os.cpu_count() or 1)
            and 0 < args.target_seconds < args.timeout <= 60 and 0 < args.max_count <= 1000000
            and 0 <= args.seed < 2**64 and 0 <= args.battery_floor <= 100
            and (args.max_jobs is None or args.max_jobs > 0)):
        p.error("Invalid duration, resource bound, seed, or batch size")
    args.directory = args.directory.resolve()
    if args.command != "run":
        db = sqlite3.connect(f"file:{args.directory/'campaign.sqlite3'}?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        db.execute("BEGIN")
        print(json.dumps(audit(db) if args.command == "audit" else snapshot(db, "inspection"), indent=2))
        return
    args.directory.mkdir(parents=True, exist_ok=True)
    with (args.directory/"writer.lock").open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            p.error("This campaign already has an active writer")
        recovered = recover_journals(args.directory)
        if recovered:
            print("VERIFIED_SOLUTION_RECOVERED "+canonical(recovered),flush=True)
            atomic_json(args.directory/"recovery-status.json",dict(state="solution_found",solutions=recovered))
            return
        db = connect(args.directory/"campaign.sqlite3")
        specs = contexts()
        validate_contexts(specs)
        spec_by_key = {s["key"]:s for s in specs}
        initialize(db, specs, source_identity(), args.seed)
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
                        future = pool.submit(execute, job, spec_by_key[job["context"]], args.seed, args.timeout,
                                             args.directory/"journals")
                        pending[future] = job
                        in_flight[job["context"]] = in_flight.get(job["context"], 0)+1
                        submitted += 1
                        limit = args.max_jobs is not None and submitted >= args.max_jobs
                    if pending:
                        ready, _ = futures.wait(pending, timeout=.25, return_when=futures.FIRST_COMPLETED)
                        for future in ready:
                            job = pending.pop(future)
                            result=None
                            try:
                                result = future.result()
                                if result["verified"]:
                                    STOP, state = True, "solution_found"
                                    print("VERIFIED_SOLUTION "+canonical(result["verified"]),flush=True)
                                    preserve_discovery(args.directory, result)
                                record_success(db, job, result)
                                # Only committed, fully validated, empty-hit output is disposable.
                                if result.get("journal") and not result["verified"]:
                                    try:
                                        Path(result["journal"]).unlink(missing_ok=True)
                                    except OSError as cleanup_error:
                                        # Retained scratch output cannot invalidate committed coverage.
                                        print("JOURNAL_CLEANUP_WARNING "+str(cleanup_error),file=sys.stderr,flush=True)
                            except Exception as exc:
                                partial = getattr(exc, "partial", None)
                                if result and result["verified"]:
                                    partial=dict(result,incomplete=True,error=f"Post-verification bookkeeping failed: {exc}")
                                if partial and partial["verified"]:
                                    STOP, state = True, "solution_found"
                                    preserve_discovery(args.directory, partial)
                                    try:
                                        record_partial_discovery(db, job, partial)
                                    except Exception as save_error:
                                        error = save_error
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
                        report = snapshot(db, ("paused_low_battery" if low_battery else "paused") if paused else state, started, deadline_wall)
                        report["power"] = power
                        atomic_json(args.directory/"status.json", report)
                        print(f"{report['updated_utc']} {report['state']}: "
                              f"{report['totals']['curve_checks']:,} curve checks; "
                              f"{len(report['solutions'])} verified solutions", flush=True)
                        last_status = now
            if error and state != "solution_found":
                state = "failed"
            elif state != "solution_found":
                state = "stopped" if STOP or (args.directory/"STOP").exists() else "session_complete"
            verification = audit(db)
            with db:
                event(db, "session_finished", dict(state=state, audit=verification, error=str(error) if error else None))
            report = snapshot(db, state, started, deadline_wall)
            report["audit"] = verification
            report["drain_error"] = str(error) if error else None
            atomic_json(args.directory/"status.json", report)
            print(json.dumps({k:report[k] for k in ["state", "totals", "solutions", "audit"]}, indent=2))
            if error and state != "solution_found":
                raise error
        finally:
            db.close()


if __name__ == "__main__":
    main()
