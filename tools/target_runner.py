#!/usr/bin/env python3
"""Standalone runner for the cross-target sub-campaign (the 40% slice).

Deliberately a SEPARATE process from the 114 runner, which is left byte-for-byte
untouched — so nothing here can crash anyone's existing campaign. A contributor
runs this alongside the normal runner (give it ~40% of your cores, per
target_bounds), and it searches the other open cases (390, 627, 633, 732, ...).

It picks a target weighted by the density prior, skips provably-empty tasks with
the exact shell-interval proof before spending any scan, computes with the sound
run_target_task, and banks verified-locally work as `[bank-mt]` issues for the
separate target verifier. No 114 state is read or written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import multi_target as mt
import target_bounds as tb
from ingest import atomic_json, canonical, read_json

BANK_SCHEMA = "math-gambling-target-bank-v1"
MAX_BANK_TASKS = 256


def target_weights(targets):
    """Renormalized density-prior weights over the target slice (114 excluded)."""
    split = tb.campaign_split(targets=(tb.PRIMARY,) + tuple(targets))
    others = {k: v for k, v in split.items() if k != tb.PRIMARY}
    total = sum(others.values()) or 1.0
    return {k: v / total for k, v in others.items()}


def choose_target_task(rng, targets, weights, done, *, max_attempts=200):
    """Pick a fresh, not-provably-empty target task, or None if none found fast."""
    ks = list(weights)
    ws = [weights[k] for k in ks]
    for _ in range(max_attempts):
        k = rng.choices(ks, weights=ws, k=1)[0]
        ctx = rng.choice(mt.ELL1_CONTEXTS)
        c = mt.sc.CONTEXT_BY_ID[ctx]
        row = rng.randrange(int(c["rowTasks"])) * c["rowStride"]
        block = rng.randrange(c["blocks"])
        task = mt.make_target_task(k, ctx, row, block)
        tid = mt.target_task_id(task)
        if tid in done:
            continue
        # k-general emptiness proof: never spend a scan (or a bank slot) on a task
        # the shell-interval bound proves empty FOR THIS target. Sound and cheap.
        if mt.prove_empty_target(task):
            done.add(tid)
            continue
        return task
    return None


def write_bank(out, claims, contributor):
    bank = {"schema": BANK_SCHEMA, "contributor": contributor, "tasks": claims}
    bid = hashlib.sha256(canonical(bank).encode()).hexdigest()[:16]
    path = Path(out) / "banks" / f"bank-mt-{bid}.json"
    atomic_json(path, bank)
    return path, bid


def submit_bank(path, bid, repo):
    """Open a [bank-mt] issue via gh; best-effort, mirrors the 114 flow."""
    body = Path(path).read_text()
    title = f"[bank-mt] Target bank {bid}"
    proc = subprocess.run(["gh", "issue", "create", "-R", repo, "--title", title,
                           "--body-file", str(path), "--label", "bank-mt"],
                          capture_output=True, text=True, timeout=30)
    return proc.returncode == 0, (proc.stdout or proc.stderr).strip()


def run(args):
    out = Path(args.output)
    (out / "banks").mkdir(parents=True, exist_ok=True)
    contributor = {"name": args.name or "Anonymous", "github": args.github or ""}
    if args.url:
        contributor["url"] = args.url
    done = set(read_json(out / "done.json", []))
    targets = tuple(k for k in args.targets if tb.admissible(k) and k != tb.PRIMARY)
    weights = target_weights(targets)
    rng = random.Random(args.seed)
    deadline = time.monotonic() + args.minutes * 60
    max_tasks = getattr(args, "max_tasks", None)
    claims, completed, banked = [], 0, 0
    print(f"Target sub-campaign over {targets}; weights {({k: round(v,3) for k,v in weights.items()})}. "
          f"114 is handled by the separate primary runner.", flush=True)
    while time.monotonic() < deadline and (max_tasks is None or completed < max_tasks):
        task = choose_target_task(rng, targets, weights, done)
        if task is None:
            break
        result = mt.run_target_task(task)
        done.add(result["id"])
        completed += 1
        claim = {"task": task, "digest": result["digest"]}
        if result["hits"]:
            claim["hits"] = result["hits"]
            atomic_json(out / "discoveries" / f"{result['id'].replace(':','_')}.json", result)
        claims.append(claim)
        if len(claims) >= args.bank_every:
            path, bid = write_bank(out, claims[:MAX_BANK_TASKS], contributor)
            banked += 1
            if args.submit:
                ok, msg = submit_bank(path, bid, args.repo)
                print(("submitted " if ok else "submit failed ") + msg, flush=True)
            claims = []
        if completed % 64 == 0:
            atomic_json(out / "done.json", sorted(done))
    if claims:
        write_bank(out, claims[:MAX_BANK_TASKS], contributor)
        banked += 1
    atomic_json(out / "done.json", sorted(done))
    print(f"Completed {completed} target tasks, wrote {banked} banks.", flush=True)
    return completed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("mg-targets"))
    parser.add_argument("--minutes", type=float, default=60.0)
    parser.add_argument("--bank-every", type=int, default=256)
    parser.add_argument("--name", default="")
    parser.add_argument("--github", default="")
    parser.add_argument("--url", default="")
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--repo", default="Kuberwastaken/math-gambling")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--max-tasks", type=int, default=None, help="stop after N tasks (for tests/bounded runs)")
    parser.add_argument("--targets", type=int, nargs="+", default=list(tb.OPEN_TARGETS))
    run(parser.parse_args(argv))
    return 0


if __name__ == "__main__":
    sys.exit(main())
