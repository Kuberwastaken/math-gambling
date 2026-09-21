#!/usr/bin/env python3
"""Verifier for the cross-target sub-campaign — strictly parallel to the 114
pipeline, which it never touches.

Target banks arrive as `[bank-mt]` GitHub issues (the 114 verifier only reads
`[bank]`/`[compute]`, so it ignores these). Each task is independently replayed
in an isolated subprocess (`tools/multi_target.py`), deduplicated by its
namespaced task id, credited to the authenticated issue author, and its counters
folded into per-target/per-context stats used by the adaptive allocation. All
state lives under data/targets/, never in the 114 ledger or coverage.

No submitted code is ever executed. A digest proves byte identity, not CPU.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.error import HTTPError

# Reuse the trusted 114 helpers WITHOUT importing behavior that touches its data.
from ingest import (ROOT, atomic_json, canonical, now, read_json, parse_json,
                    contributor, exact_triple, api_request, MAX_BANK_BYTES,
                    MAX_BANK_TASKS, MAX_BODY_BYTES, MAX_LIST_PAGE)
import multi_target as mt

TARGET_BANK_SCHEMA = "math-gambling-target-bank-v1"
REPLAY_KERNEL_SHA256 = hashlib.sha256(b"".join((ROOT / "native/src" / name).read_bytes() for name in ("lib.rs", "main.rs"))).hexdigest()
REPLAY_CMD = [sys.executable, str(ROOT / "tools/multi_target.py")]
CROSS_CHECK_ONE_IN = 256
PENDING_REFETCH = 256
SCAN_PAGES = 6
MAX_PENDING = 16384


def ledger_path(data, k, task_id):
    digest = hashlib.sha256(task_id.encode()).hexdigest()
    return Path(data) / "targets" / str(k) / "tasks" / digest[:2] / (digest + ".json")


def discovery_path(data, solution_id):
    return Path(data) / "targets" / "discoveries" / (solution_id + ".json")


def replay_target(task):
    """Trusted isolated replay of one target task; data-only stdin, bounded."""
    done = subprocess.run(REPLAY_CMD, input=canonical(task), text=True,
                          capture_output=True, timeout=6, check=True)
    if len(done.stdout) > 65536:
        raise ValueError("replay output exceeded cap")
    payload = parse_json(done.stdout, 65536)
    cpu = payload["cpu_ms"]
    if not isinstance(cpu, (int, float)) or isinstance(cpu, bool) or cpu < 0 or cpu != cpu:
        raise ValueError("invalid trusted replay timing")
    return payload["result"], max(float(cpu), 0.01)



class NativeTargetReplay:
    """Warmed Rust target replay with deterministic Python reference checks."""
    def __init__(self, one_in=CROSS_CHECK_ONE_IN, python_replay=replay_target):
        from native_kernel import NativeKernel
        self.kernel = NativeKernel()
        self.one_in = one_in
        self.python_replay = python_replay
        self.cross_checked = 0

    def close(self):
        if self.kernel is not None:
            self.kernel.close()
            self.kernel = None

    def __enter__(self): return self
    def __exit__(self, *_): self.close()

    def __call__(self, task):
        identifier = mt.target_task_id(mt.validate_target_task(task))
        try:
            expected = self.kernel.run(task)
            cpu = self.kernel.last_cpu_ms
            if cpu is None: raise RuntimeError("native target worker reported no timing")
            selected = int.from_bytes(hashlib.sha256(("target-cross-check:" + identifier).encode()).digest()[:8], "big") % self.one_in == 0
            if selected:
                reference, _ = self.python_replay(task)
                if canonical(reference) != canonical(expected):
                    raise RuntimeError("Rust and Python target replays disagree for " + identifier)
                self.cross_checked += 1
            return expected, max(float(cpu), 0.01)
        except BaseException:
            self.close()
            raise


def save_discoveries(data, k, hits, source, person):
    saved = []
    for hit in hits or []:
        xyz = exact_triple(hit.get("xyz") if isinstance(hit, dict) else hit, k)
        if xyz is None:
            continue
        solution_id = hashlib.sha256(canonical([k, sorted(xyz)]).encode()).hexdigest()
        path = discovery_path(data, solution_id)
        if not path.exists():
            atomic_json(path, {"schema": "math-gambling-target-discovery-v1", "id": solution_id,
                              "k": k, "xyz": [str(v) for v in xyz], "verified_at": now(),
                              "verification": "independent Python integer cube identity",
                              "contributor": person, "source": source})
        saved.append(solution_id)
    return sorted(set(saved))


def process_target_bank(bank, source, data, budget, replay=replay_target):
    """Replay a [bank-mt] bank into the target namespace. Returns a record dict."""
    person = contributor(bank)
    raw = canonical(bank)
    record = {"schema": "math-gambling-target-receipt-v1", "source": source,
              "body_sha256": hashlib.sha256(raw.encode()).hexdigest(), "processed_at": now(),
              "accepted": [], "duplicate": [], "rejected": [], "discoveries": [], "contributor": person}
    try:
        if not isinstance(bank, dict) or bank.get("schema") != TARGET_BANK_SCHEMA or set(bank) != {"schema", "contributor", "tasks"}:
            raise ValueError("unsupported target bank schema or fields")
        if len(raw.encode()) > MAX_BANK_BYTES:
            raise ValueError("target bank exceeds byte cap")
        tasks = bank["tasks"]
        if not isinstance(tasks, list) or not 1 <= len(tasks) <= MAX_BANK_TASKS:
            raise ValueError(f"target bank must contain 1..{MAX_BANK_TASKS} tasks")
        for index, claim in enumerate(tasks):
            try:
                if not isinstance(claim, dict) or set(claim) - {"task", "digest", "hits"} or not {"task", "digest"} <= set(claim):
                    raise ValueError("unexpected task fields")
                if not isinstance(claim.get("digest"), str) or not re.fullmatch(r"[0-9a-f]{64}", claim["digest"]):
                    raise ValueError("digest must be 64 lowercase hex")
                task = mt.validate_target_task(claim["task"])
                k = mt.parse_engine(task["engine"])
                task_id = mt.target_task_id(task)
                path = ledger_path(data, k, task_id)
                saved = read_json(path)
                if saved:
                    # Already verified by someone: the saved result is authoritative.
                    # A duplicate must still match it to earn (duplicate) credit.
                    if claim["digest"] != saved["result"]["digest"]:
                        raise ValueError("claim differs from previously verified result")
                    record["duplicate"].append(task_id)
                    record["discoveries"].extend(save_discoveries(data, k, saved["result"]["hits"], source, person))
                    continue
                budget.charge()
                expected, cpu = replay(task)
                if claim["digest"] != expected["digest"] or ("hits" in claim and canonical(claim["hits"]) != canonical(expected["hits"])):
                    raise ValueError("claim differs from independently replayed result")
                record["discoveries"].extend(save_discoveries(data, k, expected["hits"], source, person))
                atomic_json(path, {"schema": "math-gambling-target-verified-v1", "id": task_id,
                                  "k": k, "context": task["context"], "result": expected,
                                  "verified_at": now(), "server_replay_cpu_ms": cpu,
                                  "replay_kernel_sha256": REPLAY_KERNEL_SHA256,
                                  "contributor": person, "source": source})
                record["accepted"].append(task_id)
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                record["rejected"].append({"index": index, "reason": str(exc)[:180]})
        record["status"] = "accepted" if not record["rejected"] else "partial" if record["accepted"] or record["duplicate"] else "rejected"
    except (ValueError, TypeError, KeyError) as exc:
        record.update(status="rejected", reason=str(exc)[:180])
    record["discoveries"] = sorted(set(record["discoveries"]))
    record["processed_at"] = now()
    return record


def aggregate_targets(data):
    """Per-target and per-(target,context) stats + leaderboard from the ledger."""
    base = Path(data) / "targets"
    per_target, per_context, board = {}, {}, {}
    for path in base.glob("*/tasks/*/*.json"):
        row = read_json(path)
        if not isinstance(row, dict) or row.get("schema") != "math-gambling-target-verified-v1":
            continue
        k = row["k"]
        cn = row["result"]["counters"]
        pt = per_target.setdefault(k, {"verified_tasks": 0, "curves": 0, "exact_tests": 0, "empty_tasks": 0, "cpu_ms": 0.0})
        pt["verified_tasks"] += 1
        pt["curves"] += cn["curves"]
        pt["exact_tests"] += cn["exact_tests"]
        pt["empty_tasks"] += 1 if cn["curves"] == 0 else 0
        pt["cpu_ms"] += row.get("server_replay_cpu_ms", 0.0)
        ctx = per_context.setdefault((k, row["context"]), {"tasks": 0, "curves": 0, "cpu_ms": 0.0, "empty_tasks": 0})
        ctx["tasks"] += 1
        ctx["curves"] += cn["curves"]
        ctx["cpu_ms"] += row.get("server_replay_cpu_ms", 0.0)
        ctx["empty_tasks"] += 1 if cn["curves"] == 0 else 0
        gh = (row.get("contributor") or {}).get("github", "")
        if gh:
            board[gh] = board.get(gh, 0) + 1
    summary = {"schema": "math-gambling-targets-summary-v1", "updated_at": now(),
               "targets": {str(k): v for k, v in sorted(per_target.items())},
               "context_stats": {f"{k}:{c}": v for (k, c), v in per_context.items()},
               "leaderboard": dict(sorted(board.items(), key=lambda kv: -kv[1])),
               "discoveries": sorted(p.stem for p in (base / "discoveries").glob("*.json"))}
    atomic_json(base / "summary.json", summary)
    return summary


class RetryLater(Exception):
    pass


class Budget:
    def __init__(self, count=8192, seconds=120):
        self.remaining = count
        self.deadline = time.monotonic() + min(seconds, 120)

    def charge(self):
        if self.remaining <= 0 or time.monotonic() >= self.deadline:
            raise RetryLater("target verification budget exhausted")
        self.remaining -= 1


def parse_target_issue(issue, repo):
    title = str(issue.get("title", ""))
    if "pull_request" in issue or not title.startswith("[bank-mt]"):
        return None
    body = issue.get("body") or ""
    try:
        fenced = re.findall(r"```(?:json)?\s*\n(.*?)\n```", body, flags=re.S)
        bank = parse_json(fenced[0] if len(fenced) == 1 else body, MAX_BANK_BYTES)
    except (ValueError, TypeError, RecursionError):
        bank = {"invalid_submission": True}
    number = int(issue["number"])
    author = str((issue.get("user") or {}).get("login", ""))[:39]
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", author):
        author = ""
    source = {"id": f"issue:{number}", "kind": "issue", "number": number, "submitter": author,
              "url": f"https://github.com/{repo}/issues/{number}"}
    return bank, source


def collect_target_issues(repo, token, data, deadline):
    """Discover `[bank-mt]` by title, independent of mutable labels.

    GitHub issue search supplies the title index and a durable oldest-first page
    cursor. The pending queue survives replay limits and process interruption.
    """
    poll_path = Path(data) / "targets" / "poll.json"
    poll = read_json(poll_path, {"schema": "math-gambling-target-poll-v1",
                                "search_page": 1, "pending": []})
    pending = {int(x["number"]): x for x in poll.get("pending", [])}
    available = {}
    issue_prefix = "https://api.github.com/repos/" + repo + "/issues"
    search_prefix = "https://api.github.com/search/issues"

    def request(url, limit=32 * 1024 * 1024):
        if time.monotonic() >= deadline: raise RetryLater("target API time budget exhausted")
        return api_request(url, token, limit=limit, timeout=min(8, max(1, deadline-time.monotonic())))

    def retain(issue):
        parsed = parse_target_issue(issue, repo)
        if parsed is None: return
        number = parsed[1]["number"]
        if len(pending) >= MAX_PENDING and number not in pending:
            raise RetryLater("target pending cap reached")
        pending[number] = {"number": number}
        available[number] = parsed

    try:
        for number in list(pending)[:PENDING_REFETCH]:
            try: issue = request(issue_prefix + "/" + str(number), 512 * 1024)
            except HTTPError as exc:
                if exc.code not in (404, 410): raise
                exc.close(); pending.pop(number, None); continue
            if parse_target_issue(issue, repo) is None: pending.pop(number, None)
            else: retain(issue)
        for _ in range(SCAN_PAGES):
            page = int(poll.get("search_page", 1))
            query = {"q": f'repo:{repo} is:issue in:title "[bank-mt]"',
                     "sort": "created", "order": "asc", "per_page": 100, "page": page}
            result = request(search_prefix + "?" + urlencode(query))
            issues = result.get("items") if isinstance(result, dict) else None
            if not isinstance(issues, list): raise ValueError("invalid GitHub issue search response")
            for issue in issues: retain(issue)
            # GitHub search exposes at most 1,000 results. Start another sweep
            # after the cap; completed task IDs make repeats idempotent.
            if len(issues) < 100 or page >= 10:
                poll["search_page"] = 1
                break
            poll["search_page"] = page + 1
    except RetryLater as exc:
        poll["deferred_reason"] = str(exc)
    else:
        poll.pop("deferred_reason", None)
    poll["pending"] = list(pending.values())
    atomic_json(poll_path, poll)
    return [available[n] for n in pending if n in available], poll


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--input", type=Path, help="local fixture: {banks:[{bank,submitter?}]}")
    parser.add_argument("--issues", action="store_true")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "Kuberwastaken/math-gambling"))
    args = parser.parse_args(argv)
    if args.input and args.data.resolve() == (ROOT / "data").resolve():
        raise ValueError("fixture ingestion requires a separate --data directory")
    if args.input:
        payload = parse_json(args.input.read_text(), MAX_BODY_BYTES * 64 + 4096)
        entries = [(x["bank"], {"id": f"fixture:{x.get('id', i)}", "kind": "fixture",
                    "submitter": str(x.get("submitter", ""))[:39],
                    "url": "fixture"}) for i, x in enumerate(payload["banks"])]
    elif args.issues:
        entries, poll = collect_target_issues(args.repo, os.environ.get("GITHUB_TOKEN", ""), args.data, time.monotonic() + 60)
    else:
        entries = []
    poll = locals().get("poll")
    budget = Budget()
    summary = {"processed": 0, "deferred": False, "python_cross_checks": 0}
    completed = set()
    with NativeTargetReplay() as replay:
        for bank, source in entries:
            try:
                process_target_bank(bank, source, args.data, budget, replay=replay)
                summary["processed"] += 1
                completed.add(source.get("number"))
            except RetryLater:
                summary["deferred"] = True
                break
        summary["python_cross_checks"] = replay.cross_checked
    if poll is not None:
        poll["pending"] = [x for x in poll["pending"] if x["number"] not in completed]
        atomic_json(args.data / "targets" / "poll.json", poll)
    aggregate_targets(args.data)
    print(canonical(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
