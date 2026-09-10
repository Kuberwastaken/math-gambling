#!/usr/bin/env python3
"""Publish exact replay totals and an explicitly cost-only scheduling policy."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import math
from pathlib import Path
import statistics

from ingest import ROOT, MAX_REPLAYS, atomic_json, ledger_path, now, read_json, safe_profile_url
from coverage_index import publish_coverage

EPOCH_SIZE = 64
EXPLORATION = 0.4
CONTEXT_IDS = [f"c{i:02d}" for i in range(81)]


def load_kind(data, kind):
    return [read_json(path) for path in sorted((Path(data) / "receipts" / kind).glob("*/*.json"))]


def exposure(result):
    counters = result["counters"]
    # The engine's logical-position count describes finite checked positions, not odds.
    for key in ("quotient_points", "q_positions", "logical_q", "positions"):
        value = counters.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            parsed = int(value)
            if parsed >= 0:
                return parsed
    return 0


def initial_strategy():
    return {"schema": "math-gambling-strategy-v1", "epoch": 0, "through_verified_tasks": 0,
            "epoch_size": EPOCH_SIZE, "exploration_fraction": EXPLORATION,
            "objective": "verified logical quotient positions per server replay CPU second; not discovery probability",
            "reason": "No verified community observations yet; uniform exploration.",
            "contexts": [{"id": c, "weight": 1 / 81, "exploration_weight": 1 / 81,
                          "exploit_weight": 1 / 81, "sample_size": 0, "robust_cpu_ms": None} for c in CONTEXT_IDS]}


def calibrate(tasks, epoch):
    """Freeze a policy at a 64-task boundary; noisy client speed never enters it."""
    through = epoch * EPOCH_SIZE
    observations = defaultdict(list)
    for task in tasks[:through]:
        context = task["result"]["task"]["context"]
        cpu = task["server_replay_cpu_ms"]
        if context not in CONTEXT_IDS or not isinstance(cpu, (int, float)) or not math.isfinite(cpu) or cpu <= 0:
            raise ValueError("invalid verified timing/context in trusted ledger")
        observations[context].append((max(float(cpu), 0.01), exposure(task["result"])))
    usable = [positions / cpu for values in observations.values() for cpu, positions in values if positions > 0]
    baseline = statistics.median(usable) if usable else 1.0
    scores = {}
    for context in CONTEXT_IDS:
        values = observations[context]
        # Three samples before adaptation; each per-context score remains within 4x global median.
        sample = statistics.median([positions / cpu for cpu, positions in values]) if len(values) >= 3 else baseline
        scores[context] = min(4 * baseline, max(0.25 * baseline, sample))
    total = sum(scores.values())
    policy = initial_strategy()
    policy.update(epoch=epoch, through_verified_tasks=through,
                  reason="Epoch frozen after 64 new unique verified tasks. Median replay efficiency, 4x clipping, minimum three observations; 40% uniform exploration.")
    policy["contexts"] = []
    for context in CONTEXT_IDS:
        values = observations[context]
        exploit = scores[context] / total
        policy["contexts"].append({"id": context, "weight": EXPLORATION / 81 + (1 - EXPLORATION) * exploit,
                                    "exploration_weight": 1 / 81, "exploit_weight": exploit,
                                    "sample_size": len(values),
                                    "robust_cpu_ms": statistics.median([x[0] for x in values]) if values else None})
    return policy


def aggregate(data):
    data = Path(data)
    tasks = sorted(load_kind(data, "tasks"), key=lambda x: x["sequence"])
    ids = [x["result"]["id"] for x in tasks]
    if len(ids) != len(set(ids)) or [x["sequence"] for x in tasks] != list(range(1, len(tasks) + 1)):
        raise ValueError("duplicate task or noncontiguous verified sequence")
    coverage = publish_coverage(data, tasks)
    receipts, hits = load_kind(data, "issues"), load_kind(data, "hits")
    epoch = len(tasks) // EPOCH_SIZE
    previous = read_json(data / "strategy.json")
    if previous and previous.get("epoch", 0) > epoch:
        raise ValueError("verified task count regressed behind frozen policy")
    if not previous:
        previous = initial_strategy()
    recorded = read_json(data / "cluster.json", {}).get("calibration_history", [])
    if not isinstance(recorded, list):
        raise ValueError("invalid calibration history")
    history_by_epoch = {}
    for entry in recorded:
        number = entry.get("epoch") if isinstance(entry, dict) else None
        if (type(number) is not int or not 1 <= number <= epoch or number in history_by_epoch
                or entry.get("through_verified_tasks") != number * EPOCH_SIZE):
            raise ValueError("calibration history has a duplicate or unsupported boundary")
        history_by_epoch[number] = entry
    # strategy.json and cluster.json are separately atomic. Reconstruct a missing
    # boundary from the authoritative ledger after interruption between replacements.
    computed = None
    history = []
    for update in range(1, epoch + 1):
        entry = history_by_epoch.get(update)
        if entry is None:
            computed = calibrate(tasks, update)
            entry = {"epoch": update, "through_verified_tasks": update * EPOCH_SIZE,
                     "updated_at": tasks[update * EPOCH_SIZE - 1]["verified_at"],
                     "objective": "cost only", "exploration_fraction": EXPLORATION,
                     "weights": {x["id"]: x["weight"] for x in computed["contexts"]}}
        history.append(entry)
    if previous["epoch"] != epoch:
        previous = computed if computed and computed["epoch"] == epoch else calibrate(tasks, epoch)
    if epoch and history[-1]["weights"] != {x["id"]: x["weight"] for x in previous["contexts"]}:
        raise ValueError("recorded epoch weights disagree with frozen policy")
    atomic_json(data / "strategy.json", previous)
    totals = Counter()
    context_tasks = defaultdict(list)
    people = {}
    for task in tasks:
        result = task["result"]
        for key, value in result["counters"].items():
            if isinstance(value, (int, str)) and not isinstance(value, bool):
                numeric = int(value)
                if numeric < 0:
                    raise ValueError("negative verified counter")
                totals[key] += numeric
        context_tasks[result["task"]["context"]].append(task)
        person = task["contributor"]
        provenance = task["source"].get("submitter", "")
        # Leaderboard identity comes from GitHub's signed-in issue creator, never a claimed handle.
        if not provenance or task["source"].get("kind") != "issue":
            continue
        key = provenance.casefold()
        if key not in people:
            people[key] = dict(name=person["name"], github=provenance, github_verified=True,
                               claimed_github=person["github"], submitter=provenance,
                               verified_tasks=0, verified_computations=0)
        # Latest uniquely credited work may update the public alias/link.
        # Duplicate submissions cannot impersonate or overwrite a participant.
        people[key]["name"] = person["name"]
        people[key]["claimed_github"] = person["github"]
        url = safe_profile_url(person.get("url"))
        if url:
            people[key]["url"] = url
        else:
            people[key].pop("url", None)
        people[key]["verified_tasks"] += 1
        people[key]["verified_computations"] += int(result["counters"].get("generators", 0))
    contexts = []
    for context in CONTEXT_IDS:
        rows = context_tasks[context]
        cpu = sum(x["server_replay_cpu_ms"] for x in rows)
        contexts.append({"id": context, "verified_tasks": len(rows), "replay_cpu_ms": cpu,
                         "exposure": str(sum(exposure(x["result"]) for x in rows)),
                         "mean_cpu_ms": cpu / len(rows) if rows else None})
    ranked = sorted(people.values(), key=lambda x: (-x["verified_computations"], -x["verified_tasks"], x["github"]))[:100]
    for person in ranked:
        person["verified_computations"] = str(person["verified_computations"])
    banks = [{"issue": x["source"].get("number"), "url": x["source"].get("url", ""),
              "submitter": x["source"].get("submitter", ""), "status": x["status"],
              "complete": x.get("complete", True), "processed_tasks": x.get("next_index", 0),
              "operational_error": x.get("operational_error"),
              "total_tasks": x["reported_tasks"], "accepted_tasks": len(x["accepted_tasks"]),
              "duplicate_tasks": len(x["duplicate_tasks"]), "rejected_tasks": len(x["rejected_tasks"]),
              "body_sha256": x["body_sha256"], "bank_digest": x["body_sha256"], "processed_at": x["processed_at"],
              "audit_path": str(ledger_path(data, "issues", x["source"]["id"]).relative_to(data))}
             for x in sorted(receipts, key=lambda x: x["processed_at"], reverse=True)[:500]]
    cluster = {"schema": "math-gambling-cluster-v1", "updated_at": now(),
               "totals": {"reported_receipts": len(receipts),
                          "reported_tasks": sum(x["reported_tasks"] for x in receipts),
                          "verified_unique_tasks": len(tasks),
                          "verified_computations": str(totals.get("generators", 0)),
                          "replay_cpu_ms": sum(x["server_replay_cpu_ms"] for x in tasks),
                          "rejected_receipts": sum(x["status"] == "rejected" for x in receipts),
                          "partial_receipts": sum(x["status"] == "partial" for x in receipts),
                          "duplicate_tasks": sum(len(x["duplicate_tasks"]) for x in receipts),
                          "pending_banks": sum(not x.get("complete", True) for x in receipts),
                          "verified_hits": len(hits), "counters": {key: str(value) for key, value in sorted(totals.items())}},
               "coverage": {"revision": coverage["revision"], "index": "coverage/index.json",
                            "verified_task_count": coverage["verified_task_count"]},
               "contexts": contexts,
               "contributors": ranked, "banks": banks,
               "discoveries": hits, "calibration_history": history,
               "integrity": {"method": "independent bounded Python replay and exact integer identity checks",
                             "coverage_scope": "unique deterministic tasks in selected finite norm-coordinate domains; not an exhaustive height search",
                             "epoch_size": EPOCH_SIZE, "reported_is_not_verified": True,
                             "client_timing_used": False, "negative_replay_task_cap_per_run": MAX_REPLAYS,
                             "replay_time_budget_seconds": 120, "api_time_budget_seconds": 60,
                             "identity_claims": "Leaderboard credit belongs to the first accepted GitHub issue creator; display names and payload handles remain self-declared."}}
    atomic_json(data / "cluster.json", cluster)
    return cluster


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    aggregate(parser.parse_args().data)
