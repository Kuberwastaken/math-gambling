#!/usr/bin/env python3
"""Replay bounded, untrusted receipts. No submitted code is ever executed."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import time
import threading
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit
from urllib.error import HTTPError
from urllib.request import Request, urlopen

MAX_RECEIPT_BYTES = 8192
MAX_BANK_BYTES = 60000
MAX_BODY_BYTES = 61024
MAX_BANK_TASKS = 256
MAX_TASKS = 8
MAX_RECEIPTS = 32
MAX_REPLAYS = 16384
MAX_HITS = 64
MAX_DIGITS = 128
USER_AGENT = "OpenAI File Downloader, XaiImageApiFetch/1.0"
ROOT = Path(__file__).resolve().parents[1]
DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)\Z")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def parse_json(raw, limit=MAX_BANK_BYTES):
    if len(raw.encode("utf-8")) > limit:
        raise ValueError("input exceeds byte limit")
    return json.loads(raw, object_pairs_hook=reject_duplicate_keys,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    # Coverage filenames hash these exact bytes. Platform text-mode newline
    # translation must not make a Windows publisher emit a different shard.
    temporary.write_bytes((json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8"))
    temporary.replace(path)


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return default


def ledger_path(data, kind, identifier):
    digest = hashlib.sha256(identifier.encode()).hexdigest()
    return Path(data) / "receipts" / kind / digest[:2] / (digest + ".json")


def clean_name(value):
    if not isinstance(value, str):
        return "Anonymous"
    value = "".join(c for c in value if not unicodedata.category(c).startswith("C"))
    return " ".join(value.split())[:80] or "Anonymous"


def safe_profile_url(value):
    if (not isinstance(value, str) or len(value) > 2048
            or any(c.isspace() or ord(c) < 32 or ord(c) == 127 or c == "\\" for c in value)
            or not re.match(r"https?://", value, re.I)):
        return ""
    try:
        parsed = urlsplit(value)
        # Accessing port also rejects malformed/out-of-range ports.
        parsed.port
        if parsed.hostname and not parsed.username and not parsed.password:
            return value
    except ValueError:
        pass
    return ""


def contributor(receipt):
    claim = receipt.get("contributor", {}) if isinstance(receipt, dict) else {}
    if not isinstance(claim, dict):
        claim = {}
    github = claim.get("github", "")
    if not isinstance(github, str) or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", github):
        github = ""
    person = {"name": clean_name(claim.get("name")), "github": github, "github_verified": False}
    url = safe_profile_url(claim.get("url"))
    if url:
        person["url"] = url
    return person


def exact_triple(xyz, k=114):
    """Deliberately independent of the search engine and its verifier."""
    if not isinstance(xyz, list) or len(xyz) != 3:
        return None
    values = []
    for value in xyz:
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            return None
        text = str(value)
        if len(text.lstrip("-")) > MAX_DIGITS or not DECIMAL.fullmatch(text):
            return None
        values.append(int(text))
    return values if sum(v * v * v for v in values) == k else None


def preserve_hits(data, receipt, source):
    """A valid identity is retained even when its task/receipt is rejected."""
    if not isinstance(receipt, dict):
        return []
    try:
        # Bound the whole rescue operation, not a prefix of its candidate list.
        # Every candidate inside a supported input envelope gets an exact check.
        if len(canonical(receipt).encode("ascii")) > MAX_BODY_BYTES:
            return []
    except (ValueError, TypeError, RecursionError):
        return []
    candidates = []
    containers = [receipt]
    if isinstance(receipt.get("results"), list):
        containers.extend(receipt["results"])
    if isinstance(receipt.get("tasks"), list):
        containers.extend(receipt["tasks"])
    for container in containers:
        if isinstance(container, dict) and isinstance(container.get("hits"), list):
            candidates.extend(container["hits"])
    retained = []
    for hit in candidates:
        xyz = exact_triple(hit.get("xyz") if isinstance(hit, dict) else hit)
        if xyz is None:
            continue
        solution_id = hashlib.sha256(canonical(sorted(xyz)).encode()).hexdigest()
        path = ledger_path(data, "hits", solution_id)
        if not path.exists():
            atomic_json(path, {"schema": "math-gambling-discovery-v1", "id": solution_id,
                              "xyz": [str(v) for v in xyz], "k": 114,
                              "verified_at": now(), "verification": "independent Python integer cube identity",
                              "contributor": contributor(receipt), "source": source})
        retained.append(solution_id)
    return sorted(set(retained))


def replay_task(task):
    """Trusted engine, isolated with bounded CPU and wall time; data-only stdin."""
    completed = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--replay-one"],
                               input=canonical(task), text=True, capture_output=True, timeout=6, check=True)
    if len(completed.stdout) > 65536:
        raise ValueError("replay output exceeded cap")
    payload = parse_json(completed.stdout, 65536)
    timing = payload["cpu_ms"]
    if isinstance(timing, bool) or not isinstance(timing, (int, float)) or not math.isfinite(timing) or timing < 0:
        raise ValueError("invalid trusted replay timing")
    return payload["result"], max(float(timing), 0.01)


class WarmReplay:
    """One trusted warmed worker, retired after a bounded number of exact tasks.

    The parent owns wall/output deadlines; POSIX children also arm a fresh CPU
    timer per task. A worker is discarded after any timeout or protocol error.
    """
    def __init__(self, max_tasks=256, wall_seconds=6, command=None):
        if type(max_tasks) is not int or not 1 <= max_tasks <= 256:
            raise ValueError("worker batch must contain 1..256 tasks")
        if not isinstance(wall_seconds, (int, float)) or not math.isfinite(wall_seconds) or not 0 < wall_seconds <= 6:
            raise ValueError("worker wall deadline must be in (0, 6]")
        self.command = command or [sys.executable, str(Path(__file__).resolve()), "--replay-stream"]
        self.max_tasks, self.wall_seconds = max_tasks, wall_seconds
        self.process = self.reader = self.events = None
        self.completed = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @staticmethod
    def _read_lines(process, events):
        try:
            while True:
                line = process.stdout.readline(65537)
                events.put(line, timeout=0.25)
                if not line:
                    return
        except (OSError, ValueError, queue.Full):
            # Bound unsolicited stdout even if a faulty trusted worker floods it.
            if process.poll() is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass

    def _message(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(self.command, self.wall_seconds)
        try:
            line = self.events.get(timeout=remaining)
        except queue.Empty:
            raise subprocess.TimeoutExpired(self.command, self.wall_seconds) from None
        if not line or len(line) > 65536 or not line.endswith(b"\n"):
            raise subprocess.CalledProcessError(1, self.command, stderr="bounded replay stream ended or exceeded its output limit")
        try:
            message = parse_json(line.decode("utf-8"), 65536)
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise subprocess.CalledProcessError(1, self.command, stderr="invalid replay JSON") from exc
        return message, len(line)

    def _start(self):
        from search_core import ENGINE
        self.process = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL)
        self.events = queue.Queue(maxsize=8)
        self.reader = threading.Thread(target=self._read_lines, args=(self.process, self.events), daemon=True)
        self.reader.start()
        message, _ = self._message(time.monotonic() + 6)
        if message != {"schema": "math-gambling-replay-ready-v1", "engine": ENGINE}:
            raise subprocess.CalledProcessError(1, self.command, stderr="wrong trusted worker handshake")
        self.completed = 0

    def close(self):
        process, reader = self.process, self.reader
        if process is not None:
            if process.poll() is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            process.wait(timeout=2)
            if reader is not None:
                reader.join(timeout=1)
            for handle in (process.stdin, process.stdout):
                try:
                    handle.close()
                except OSError:
                    pass
        self.process = self.reader = self.events = None
        self.completed = 0

    def __call__(self, task, on_hit=None):
        from search_core import task_id, validate_task
        task = validate_task(task)
        try:
            if self.process is None or self.process.poll() is not None or self.completed >= self.max_tasks:
                self.close()
                self._start()
            request_id = self.completed + 1
            deadline = time.monotonic() + self.wall_seconds
            payload = (canonical({"request_id": request_id, "task": task}) + "\n").encode("ascii")
            if len(payload) > 2048:
                raise ValueError("trusted task descriptor exceeded stream cap")
            try:
                self.process.stdin.write(payload)
                self.process.stdin.flush()
            except (OSError, ValueError) as exc:
                raise subprocess.CalledProcessError(1, self.command, stderr="trusted worker input closed") from exc
            output_bytes = 0
            while True:
                message, size = self._message(deadline)
                output_bytes += size
                if (output_bytes > 65536 or not isinstance(message, dict)
                        or type(message.get("request_id")) is not int or message["request_id"] != request_id):
                    raise subprocess.CalledProcessError(1, self.command, stderr="unexpected or oversized replay response")
                if set(message) == {"request_id", "hit"}:
                    if on_hit is not None:
                        on_hit(message["hit"])
                    continue
                if set(message) != {"request_id", "result", "cpu_ms"}:
                    raise subprocess.CalledProcessError(1, self.command, stderr="unexpected replay response fields")
                result, timing = message["result"], message["cpu_ms"]
                if (not isinstance(result, dict) or result.get("task") != task or result.get("id") != task_id(task)
                        or isinstance(timing, bool) or not isinstance(timing, (int, float))
                        or not math.isfinite(timing) or timing < 0 or timing > 4100):
                    raise subprocess.CalledProcessError(1, self.command, stderr="invalid trusted task identity or CPU accounting")
                self.completed += 1
                return result, max(float(timing), 0.01)
        except BaseException:
            self.close()
            raise


def replay_stream():
    """Data-only internal protocol. This entry point cannot import submitted code."""
    import inspect
    import signal
    from search_core import ENGINE, _filters, run_task, validate_task
    _filters(114)
    callback_supported = "on_hit" in inspect.signature(run_task).parameters
    print(canonical({"schema": "math-gambling-replay-ready-v1", "engine": ENGINE}), flush=True)
    for _ in range(256):
        raw = sys.stdin.buffer.readline(2049)
        if not raw:
            return
        request = parse_json(raw.decode("ascii"), 2048)
        if (not raw.endswith(b"\n") or not isinstance(request, dict) or set(request) != {"request_id", "task"}
                or type(request["request_id"]) is not int or not 1 <= request["request_id"] <= 256):
            raise ValueError("invalid trusted stream request")
        task = validate_task(request["task"])
        emit = lambda hit: print(canonical({"request_id": request["request_id"], "hit": hit}), flush=True)
        if hasattr(signal, "ITIMER_PROF"):
            signal.setitimer(signal.ITIMER_PROF, 4)
        started = time.process_time()
        result = run_task(task, on_hit=emit) if callback_supported else run_task(task)
        elapsed = 1000 * (time.process_time() - started)
        if hasattr(signal, "ITIMER_PROF"):
            signal.setitimer(signal.ITIMER_PROF, 0)
        print(canonical({"request_id": request["request_id"], "result": result, "cpu_ms": elapsed}), flush=True)


class RetryLater(Exception):
    pass


class Budget:
    def __init__(self, count=MAX_REPLAYS, seconds=120):
        self.remaining = min(count, MAX_REPLAYS)
        self.deadline = time.monotonic() + min(seconds, 120)
        self.next_sequence = None

    def charge(self):
        if self.remaining <= 0 or time.monotonic() >= self.deadline:
            raise RetryLater("verification budget exhausted; receipt stays queued")
        self.remaining -= 1


def process_receipt(receipt, source, data, budget, replay=replay_task):
    """Replay a bank incrementally; its durable cursor survives the hourly budget."""
    from search_core import validate_task, task_id
    source_id = source["id"]
    try:
        raw = canonical(receipt)
    except (ValueError, TypeError, RecursionError):
        raw = '"receipt could not be serialized within the supported JSON limits"'
    body_hash = hashlib.sha256(raw.encode()).hexdigest()
    record_path = ledger_path(data, "issues", source_id)
    previous = read_json(record_path)
    discoveries = preserve_hits(data, receipt, source)
    if previous and previous["body_sha256"] == body_hash and previous.get("complete"):
        return previous
    record = previous or {"schema": "math-gambling-receipt-audit-v1", "source": source,
              "body_sha256": body_hash, "processed_at": now(), "status": "pending", "complete": False,
              "reported_tasks": 0, "next_index": 0, "accepted_tasks": [], "duplicate_tasks": [], "rejected_tasks": [],
              "discoveries": discoveries, "contributor": contributor(receipt)}
    if previous and previous["body_sha256"] != body_hash:
        raise ValueError("immutable bank revision changed payload")
    try:
        if isinstance(receipt, dict) and receipt.get("schema") == "math-gambling-identity-v1":
            if len(raw.encode()) > MAX_BANK_BYTES or set(receipt) != {"schema", "contributor", "hits"}:
                raise ValueError("invalid identity-only submission fields or size")
            hits = receipt["hits"]
            if not isinstance(hits, list) or not 1 <= len(hits) <= MAX_HITS or any(
                not isinstance(hit, dict) or set(hit) != {"xyz"} or exact_triple(hit["xyz"]) is None
                for hit in hits
            ):
                raise ValueError("identity-only submission failed exact cube verification")
            # Positive evidence needs no negative task coverage or claimed runtime.
            record.update(status="accepted", complete=True, discoveries=discoveries, processed_at=now())
            atomic_json(record_path, record)
            return record
        bank = isinstance(receipt, dict) and receipt.get("schema") == "math-gambling-bank-v1"
        expected_schema = "math-gambling-bank-v1" if bank else "math-gambling-receipt-v1"
        key, cap, byte_cap = ("tasks", MAX_BANK_TASKS, MAX_BANK_BYTES) if bank else ("results", MAX_TASKS, MAX_RECEIPT_BYTES)
        if len(raw.encode()) > byte_cap:
            raise ValueError("submission exceeds byte cap")
        if not isinstance(receipt, dict) or receipt.get("schema") != expected_schema:
            raise ValueError("unsupported submission schema")
        if set(receipt) != {"schema", "contributor", key}:
            raise ValueError("unexpected submission fields")
        results = receipt[key]
        if not isinstance(results, list) or not 1 <= len(results) <= cap:
            raise ValueError(f"submission must contain 1..{cap} tasks")
        record["reported_tasks"] = len(results)
        for index in range(record["next_index"], len(results)):
            claimed = results[index]
            try:
                if not isinstance(claimed, dict):
                    raise ValueError("task claim must be an object")
                if bank and (set(claimed) - {"task", "digest", "hits"} or not {"task", "digest"} <= set(claimed)):
                    raise ValueError("unexpected compact task fields")
                if not isinstance(claimed.get("digest"), str) or not re.fullmatch(r"[0-9a-f]{64}", claimed["digest"]):
                    raise ValueError("digest must be 64 lowercase hexadecimal characters")
                task = validate_task(claimed.get("task"))
                identifier = task_id(task)
                path = ledger_path(data, "tasks", identifier)
                saved = read_json(path)
                if saved:
                    expected, cpu_ms = saved["result"], saved["server_replay_cpu_ms"]
                else:
                    budget.charge()
                    if isinstance(replay, WarmReplay):
                        def retain_early(hit):
                            discoveries.extend(preserve_hits(data, {"contributor": receipt["contributor"], "hits": [hit]}, source))
                        expected, cpu_ms = replay(task, on_hit=retain_early)
                    else:
                        expected, cpu_ms = replay(task)
                    discoveries.extend(preserve_hits(data, {"contributor": receipt["contributor"], "results": [expected]}, source))
                if bank:
                    matching = claimed["digest"] == expected["digest"] and ("hits" not in claimed or canonical(claimed["hits"]) == canonical(expected["hits"]))
                else:
                    matching = canonical(claimed) == canonical(expected)
                if not matching:
                    raise ValueError("claim differs from independently replayed result")
                record.pop("operational_error", None)
                record.pop("deferred_reason", None)
                if saved:
                    field = "accepted_tasks" if saved["source"]["id"] == source_id and identifier not in record["accepted_tasks"] else "duplicate_tasks"
                    record[field].append(identifier)
                else:
                    if budget.next_sequence is None:
                        budget.next_sequence = sum(1 for _ in (Path(data) / "receipts" / "tasks").glob("*/*.json")) + 1
                    atomic_json(path, {"schema": "math-gambling-verified-task-v1", "sequence": budget.next_sequence,
                                       "result": expected, "verified_at": now(), "server_replay_cpu_ms": cpu_ms,
                                       "contributor": contributor(receipt), "source": source})
                    budget.next_sequence += 1
                    record["accepted_tasks"].append(identifier)
            except RetryLater:
                record.update(status="pending", complete=False, discoveries=sorted(set(discoveries)),
                              deferred_reason="verification_budget", processed_at=now())
                atomic_json(record_path, record)
                return record
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
                record.update(status="pending", complete=False, discoveries=sorted(set(discoveries)),
                              deferred_reason="replay_failed",
                              operational_error=type(exc).__name__ + ": trusted replay did not finish; no negative coverage accepted", processed_at=now())
                atomic_json(record_path, record)
                return record
            except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
                record["rejected_tasks"].append({"index": index, "reason": str(exc)[:180]})
            # Operational replay failures deliberately fail the job, leaving the issue queued.
            record["next_index"] = index + 1
            record["discoveries"] = sorted(set(discoveries))
            atomic_json(record_path, record)
        record["status"] = "accepted" if not record["rejected_tasks"] else "partial" if record["accepted_tasks"] or record["duplicate_tasks"] else "rejected"
        record["complete"] = True
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        record.update(reason=str(exc)[:180], status="rejected", complete=True)
    record["processed_at"] = now()
    atomic_json(record_path, record)
    return record


def api_request(url, token, *, payload=None, limit=MAX_BODY_BYTES * MAX_RECEIPTS + 4096, timeout=8):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    if payload is not None:
        data = canonical(payload).encode()
        headers["Content-Type"] = "application/json"
    request = Request(url, headers=headers, data=data)
    with urlopen(request, timeout=min(8, timeout)) as response:
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("receiver response exceeds cap")
    return parse_json(raw.decode("utf-8"), limit)


def parse_issue(issue, repo):
    if "pull_request" in issue or not str(issue.get("title", "")).startswith(("[compute]", "[bank]")):
        return None
    body = issue.get("body") or ""
    if not isinstance(body, str):
        body = ""
    body_hash = hashlib.sha256(body.encode()).hexdigest()
    try:
        if len(body.encode()) > MAX_BODY_BYTES:
            raise ValueError("issue body exceeds byte cap")
        fenced = re.findall(r"```(?:json)?\s*\n(.*?)\n```", body, flags=re.S)
        receipt = parse_json(fenced[0] if len(fenced) == 1 else body, MAX_BANK_BYTES)
    except (ValueError, TypeError, RecursionError):
        receipt = {"invalid_submission": True}
    number = int(issue["number"])
    author = str((issue.get("user") or {}).get("login", ""))[:39]
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", author):
        author = ""
    source = {"id": f"issue:{number}:{body_hash}", "kind": "issue", "number": number,
              "submitter": author, "url": f"https://github.com/{repo}/issues/{number}",
              "updated_at": str(issue.get("updated_at", ""))[:40]}
    return receipt, source


def collect_issues(repo, token, data):
    """Fast updated scan plus a persistent creation-order reconciliation sweep."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("invalid repository name")
    poll_path = Path(data) / "receipts" / "poll.json"
    poll = read_json(poll_path, {"schema": "math-gambling-issue-poll-v1", "since": None,
                               "pending": [], "scan_page": 1, "reconcile_page": 1})
    prefix = "https://api.github.com/repos/" + repo + "/issues"
    pending = {int(x["number"]): x for x in poll["pending"]}
    available, overflow = {}, False
    api_deadline = time.monotonic() + 60

    def request(url, limit):
        remaining = api_deadline - time.monotonic()
        if remaining <= 1:
            raise RetryLater("API time budget exhausted")
        return api_request(url, token, limit=limit, timeout=min(8, remaining))

    def retain(issue):
        nonlocal overflow
        parsed = parse_issue(issue, repo)
        if parsed is None:
            return
        receipt, origin = parsed
        saved = read_json(ledger_path(data, "issues", origin["id"]))
        if saved and saved.get("complete"):
            pending.pop(origin["number"], None)
            available.pop(origin["number"], None)
            return
        if len(pending) >= 4096 and origin["number"] not in pending:
            overflow = True
            raise RetryLater("pending-bank cap reached; retain scan position")
        pending[origin["number"]] = {"number": origin["number"], "updated_at": origin["updated_at"]}
        available[origin["number"]] = parsed
        # Publish received/pending and check positives before any costly negative replay.
        queued = process_receipt(receipt, origin, data, Budget(count=0))
        if queued["complete"]:
            pending.pop(origin["number"], None)
            available.pop(origin["number"], None)

    try:
        # At most eight pending requests; every request shares the same 60-second deadline.
        for number in list(pending)[:8]:
            try:
                issue = request(prefix + "/" + str(number), 512 * 1024)
            except HTTPError as exc:
                if exc.code not in (404, 410):
                    raise
                unavailable = {"schema": "math-gambling-unavailable-source-v1", "issue": number,
                               "http_status": exc.code, "observed_at": now(),
                               "reason": "Queued GitHub source is unavailable; no mathematical exclusion is claimed."}
                exc.close()
                atomic_json(ledger_path(data, "unavailable", f"issue:{number}"), unavailable)
                pending.pop(number, None)
                available.pop(number, None)
                continue
            if parse_issue(issue, repo) is None:
                pending.pop(number, None)
            else:
                retain(issue)
        # Incremental scan is a fast path, never the only discovery mechanism.
        for _ in range(2):
            page = int(poll.get("scan_page", 1))
            query = {"state": "all", "sort": "updated", "direction": "asc", "per_page": 100, "page": page}
            if poll.get("since"):
                query["since"] = poll["since"]
            issues = request(prefix + "?" + urlencode(query), 32 * 1024 * 1024)
            if not isinstance(issues, list):
                raise ValueError("invalid GitHub issue response")
            for issue in issues:
                retain(issue)
            # Advance only after the entire page is represented in the durable queue/audit.
            for issue in issues:
                stamp = issue.get("updated_at")
                if isinstance(stamp, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", stamp):
                    poll["scan_high_water"] = max(poll.get("scan_high_water") or stamp, stamp)
            if len(issues) < 100:
                stamp = poll.get("scan_high_water")
                if stamp:
                    from datetime import timedelta
                    poll["since"] = (datetime.fromisoformat(stamp.replace("Z", "+00:00")) - timedelta(seconds=1)).isoformat(timespec="seconds").replace("+00:00", "Z")
                poll.update(scan_page=1, scan_high_water=None)
                break
            poll["scan_page"] = page + 1
        # Creation order is stable under ordinary edits. Cycle the whole history to recover
        # update-sort reordering, equal-timestamp boundaries, deletions, and transfers.
        for _ in range(2):
            page = int(poll.get("reconcile_page", 1))
            query = {"state": "all", "sort": "created", "direction": "asc", "per_page": 100, "page": page}
            issues = request(prefix + "?" + urlencode(query), 32 * 1024 * 1024)
            if not isinstance(issues, list):
                raise ValueError("invalid GitHub issue response")
            for issue in issues:
                retain(issue)
            poll["reconcile_page"] = 1 if len(issues) < 100 else page + 1
            if len(issues) < 100:
                break
    except RetryLater as exc:
        poll["deferred_reason"] = str(exc)
    else:
        poll.pop("deferred_reason", None)
    poll.update(pending=list(pending.values()), overflow=overflow)
    atomic_json(poll_path, poll)
    return [available[n] for n in pending if n in available][:MAX_RECEIPTS], poll


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--input", type=Path, help="Local fixture: {receipts:[{id,receipt,submitter?}]}")
    parser.add_argument("--issues", action="store_true", help="Read queued [compute]/[bank] GitHub issues")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "Kuberwastaken/math-gambling"))
    parser.add_argument("--replay-one", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--replay-stream", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.input and args.data.resolve() == (ROOT / "data").resolve():
        raise ValueError("fixture ingestion requires a separate --data directory")
    if args.replay_stream:
        replay_stream()
        return
    if args.replay_one:
        if sys.platform != "win32":
            import resource
            resource.setrlimit(resource.RLIMIT_CPU, (4, 5))
        from search_core import run_task, validate_task, _filters
        task = validate_task(parse_json(sys.stdin.read(2049), 2048))
        _filters(114)  # Exclude one-time table setup from per-context cost calibration.
        started = time.process_time()
        result = run_task(task)
        print(canonical({"result": result, "cpu_ms": (time.process_time() - started) * 1000}))
        return
    summary = {"processed_receipts": 0, "deferred": False, "operational_errors": 0}
    poll = None
    if args.input:
        payload = parse_json(args.input.read_text(), MAX_BODY_BYTES * MAX_RECEIPTS + 4096)
        if not isinstance(payload.get("receipts"), list) or len(payload["receipts"]) > MAX_RECEIPTS:
            raise ValueError("fixture exceeds receipt cap")
        entries = [(x["receipt"], {"id": "fixture:" + str(x["id"]), "kind": "fixture", "submitter": str(x.get("submitter", ""))[:39]}) for x in payload["receipts"]]
    elif args.issues:
        entries, poll = collect_issues(args.repo, os.environ.get("GITHUB_TOKEN", ""), args.data)
    else:
        entries = []
    budget = Budget()  # Replay receives its own 120 seconds after bounded API collection.
    completed = set()
    with WarmReplay() as replay:
        for receipt, source in entries:
            record = process_receipt(receipt, source, args.data, budget, replay=replay)
            summary["processed_receipts"] += 1
            if record["complete"]:
                completed.add(source.get("number"))
            else:
                summary["deferred"] = True
                if record.get("deferred_reason") == "replay_failed":
                    summary["operational_errors"] += 1
                    continue
                break
    if poll is not None:
        poll["pending"] = [x for x in poll["pending"] if x["number"] not in completed]
        atomic_json(args.data / "receipts" / "poll.json", poll)
    from aggregate import aggregate
    aggregate(args.data)
    summary["replay_slots_used"] = MAX_REPLAYS - budget.remaining
    print(canonical(summary))
    return 2 if summary["operational_errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
