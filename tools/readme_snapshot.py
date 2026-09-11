#!/usr/bin/env python3
"""Update the marked README snapshot using only published verified data."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import html
import json
import math
from pathlib import Path
import re
import unicodedata
from urllib.parse import quote

from ingest import safe_profile_url

ROOT = Path(__file__).resolve().parents[1]
START = "<!-- MATH_GAMBLING_SNAPSHOT:START -->"
END = "<!-- MATH_GAMBLING_SNAPSHOT:END -->"
CONTEXTS = tuple(f"c{i:02d}" for i in range(81))
GITHUB_NAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")


def integer(value):
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]{0,39}", value):
        return int(value)
    raise ValueError("snapshot counts must be canonical nonnegative integers")


def markdown_text(value):
    """Plain visible text only, even inside a GFM table or a Markdown link."""
    if not isinstance(value, str):
        value = "Anonymous"
    value = "".join(" " if c.isspace() else c for c in value
                    if c.isspace() or not unicodedata.category(c).startswith("C"))
    value = html.escape(" ".join(value.split())[:100] or "Anonymous", quote=False)
    return re.sub(r"([\\`*_{}\[\]|#!~])", r"\\\1", value)


def profile_link(alias, raw_url):
    label = markdown_text(alias)
    url = safe_profile_url(raw_url)
    if not url:
        return label
    try:
        # Angle-bracket destinations plus percent encoding protect Markdown syntax.
        destination = quote(url, safe=":/?#[]@!$&'*+,;=%")
    except UnicodeError:
        return label
    return f"[{label}](<{destination}>)"


def weights(value, exploration, cpu=False):
    if not isinstance(value, dict) or set(value) != set(CONTEXTS):
        raise ValueError("snapshot requires exactly the 81 fixed contexts")
    if any(type(weight) not in (int, float) or not math.isfinite(weight)
           or weight<=0 or not (0 if cpu else exploration / 81 - 1e-12) <= weight <= 1 for weight in value.values()):
        raise ValueError("invalid or underexploring allocation weight")
    if not math.isclose(sum(value.values()), 1, rel_tol=0, abs_tol=1e-9):
        raise ValueError("allocation weights do not sum to one")
    return value


def validated_state(report, policy):
    if report.get("schema") != "math-gambling-cluster-v1" or policy.get("schema") != "math-gambling-strategy-v1":
        raise ValueError("unsupported report or policy schema")
    total = integer(report["totals"]["verified_unique_tasks"])
    epoch = integer(policy["epoch"])
    size = integer(policy["epoch_size"])
    through = integer(policy["through_verified_tasks"])
    exploration = policy["exploration_fraction"]
    if (size != 64 or through != epoch * size or epoch != total // size
            or type(exploration) not in (int, float) or not math.isfinite(exploration)
            or not 0.4 <= exploration <= 1):
        raise ValueError("report and frozen policy boundaries disagree")
    contexts = policy["contexts"]
    if not isinstance(contexts, list) or len(contexts) != 81:
        raise ValueError("invalid policy context list")
    current = weights({row["id"]: row["weight"] for row in contexts}, exploration,policy.get('policy_version')=='mg114-cpu-budget-v1')
    history = report.get("calibration_history", [])
    if not isinstance(history, list):
        raise ValueError("invalid calibration history")
    previous = 0
    for entry in history:
        number = integer(entry["epoch"])
        if (number <= previous or number > epoch
                or integer(entry["through_verified_tasks"]) != number * size):
            raise ValueError("invalid calibration history boundary")
        weights(entry["weights"], exploration,entry.get('policy_version')=='mg114-cpu-budget-v1')
        previous = number
    if epoch and (not history or history[-1]["epoch"] != epoch
                  or history[-1]["weights"] != current):
        raise ValueError("latest model history does not match the published policy")
    if report.get("coverage", {}).get("verified_task_count", total) != total:
        raise ValueError("verified coverage and report counts disagree")
    timestamp = report.get("updated_at")
    if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
        raise ValueError("report needs a UTC observation timestamp")
    stamp = datetime.fromisoformat(timestamp[:-1] + "+00:00").astimezone(timezone.utc)
    return total, epoch, size, through, exploration, current, history, stamp.strftime("%Y-%m-%d %H:%M:%S UTC")


def render_snapshot(report, policy, config=None):
    total, epoch, size, through, exploration, current, history, stamp = validated_state(report, policy)
    counters = report["totals"]["counters"]
    geometric = policy.get('policy_version') in ('mg114-geometric-cost-v1','mg114-cpu-budget-v1')
    allocation_label = 'geometry-weighted curve exposure / cost' if geometric else 'measured replay efficiency'
    method = policy.get('reason', 'Legacy cost allocation; no discovery probability.')
    count = lambda key: f"{integer(counters.get(key, 0)):,}"
    next_tasks = (epoch + 1) * size - total
    lines = ["## Current verified campaign", "", f"Published observation: **{stamp}**. This section updates after trusted receipt processing.", "",
             "| Quantity | Verified total |", "| --- | ---: |",
             f"| Unique finite tasks | {total:,} |",
             f"| Coefficient-generator inputs | {count('generators')} |",
             f"| Bounded curve intervals | {count('curves')} |",
             f"| Logical quotient positions | {count('quotient_points')} |",
             f"| Exact integer square tests | {count('exact_tests')} |",
             f"| Independently verified identities for 114 | {integer(report['totals']['verified_hits']):,} |",
             "", "![Verified work and changing allocation](data/readme-progress.svg)", "",
             "These are actual fixed-task units from independent replay, not claimed client seconds or independent chances of discovery. The separate [Mac snapshot](data/mac.json) uses different domains and is not added to these totals.", "",
             "### Global leaderboard", "",
             "| Rank | Alias | Authenticated GitHub account | Contributed inputs | Verified inputs |",
             "| ---: | --- | --- | ---: | ---: |"]
    aliases = (config or {}).get("display_aliases", {})
    urls = (config or {}).get("display_urls", {})
    people = []
    for person in report.get("contributors", []):
        account = person.get("github")
        if (person.get("github_verified") is not True or not isinstance(account, str)
                or not GITHUB_NAME.fullmatch(account)
                or str(person.get("submitter", "")).casefold() != account.casefold()):
            continue
        people.append((integer(person.get("contributed_computations", person["verified_computations"])), integer(person.get("contributed_tasks", person["verified_tasks"])), account, person))
    for rank, (inputs, tasks, account, person) in enumerate(sorted(people, key=lambda p: (-p[0], -p[1], p[2].casefold()))[:10], 1):
        alias = aliases.get(account.casefold(), person.get("name", "Anonymous")) if isinstance(aliases, dict) else person.get("name", "Anonymous")
        url = safe_profile_url(person.get("url")) or (urls.get(account.casefold()) if isinstance(urls, dict) else None)
        lines.append(f"| {rank} | {profile_link(alias, url)} | [@{account}](https://github.com/{account}) | {inputs:,} | {integer(person['verified_computations']):,} |")
    if not people:
        lines += ["", "No participants have independently verified work yet."]
    if 'zero_curve_tasks' in report['totals']:
        empty = integer(report['totals']['zero_curve_tasks'])
        lines += ["", f"**{empty:,} / {total:,} verified tasks contain no admitted curve intervals.** They remain completed coefficient-domain checks; task counts are not distinct-curve coverage. Exact shell pruning can certify those exclusions without visiting every coefficient individually.", "",
                  "[Mathematical interval export](data/math-coverage/index.json) · [Export scope and limitations](docs/MATHEMATICAL_COVERAGE.md)", ""]
    lines += ["", "Rank counts unique contributed inputs: exact replays plus provisional work from complete banks with a matched random audit. The verified column is the exact subset. A failed account audit revokes provisional credit; unchecked claims never certify coverage or train the model. Alias websites are optional and self-declared; account attribution comes from the accepted GitHub issue creator.", "",
              "### The current allocation", "",
              f"**Epoch {epoch}**, frozen from **{through:,} verified tasks**. The next policy update needs **{next_tasks:,} more accepted unique tasks**. The arrows below are regenerated from the current weights and recorded epoch history.", "", "```mermaid", "flowchart TD"]
    recent = history[-4:]
    for i, entry in enumerate(recent):
        leader = min(entry["weights"], key=lambda c: (-entry["weights"][c], c))
        lines.append(f'    H{i}["Epoch {entry["epoch"]}: {entry["through_verified_tasks"]:,} tasks; {leader} {100*entry["weights"][leader]:.2f}%"]')
        if i:
            lines.append(f"    H{i-1} --> H{i}")
    lines += [f'    Policy["Current policy: epoch {epoch}"]']
    if recent:
        lines.append(f"    H{len(recent)-1} --> Policy")
    unit='predicted CPU exploration across 81 contexts' if policy.get('exploration_unit')=='predicted_cpu' else 'uniform exploration across 81 contexts'
    lines += [f'    Policy --> Explore["{100*exploration:g}% {unit}"]',
              f'    Policy --> Cost["{100*(1-exploration):g}% weighted by {allocation_label}"]',
              '    Explore --> Mix["Combined task-selection weights"]', '    Cost --> Mix']
    top = sorted(current, key=lambda c: (-current[c], c))[:3]
    for i, context in enumerate(top):
        lines.append(f'    Mix --> C{i}["{context}: {100*current[context]:.2f}%"]')
    remaining = sum(current[c] for c in CONTEXTS if c not in top)
    lines += [f'    Mix --> Rest["Other 78 contexts: {100*remaining:.2f}% combined"]',
              '    C0 --> Check["Skip completed IDs; run exact bounded task"]',
              '    C1 --> Check', '    C2 --> Check', '    Rest --> Check',
              '    Check --> Replay["Bank result; independently replay"]',
              f'    Replay --> Gate["{size} new verified tasks completes an epoch"]',
              '    Gate --> Policy', '```', "",
              "Weights describe task-selection shares, not CPU-time shares or discovery probabilities. " + markdown_text(method), "",
              "### Model history and evidence", "",
              "| Epoch | Verified-task boundary | Largest allocation | Weight |",
              "| ---: | ---: | --- | ---: |"]
    for entry in history[-5:]:
        leader = min(entry["weights"], key=lambda c: (-entry["weights"][c], c))
        lines.append(f"| {entry['epoch']} | {entry['through_verified_tasks']:,} | {leader} | {100*entry['weights'][leader]:.4f}% |")
    if not history:
        lines += ["", "The initial uniform policy has not completed a calibration epoch."]
    lines += ["", "Every accepted task retains its full replay result and server timing. Seeds and dispatch provenance stay with client evidence. Complete policy vectors, historical boundaries and bank decisions remain inspectable:", "",
              "[Current policy](data/strategy.json) · [Complete model history and bank audits](data/cluster.json) · [Verified task records](data/receipts/tasks/) · [Exact completed-task index](data/coverage/index.json) · [Working paper](https://kuber.studio/math-gambling/paper/)", "",
              "The separate discovery-learning experiment failed its promotion gate. This campaign learns execution cost and applies a declared geometric prior; it has not established a discovery predictor."]
    return "\n".join(lines)


def update_readme(path, snapshot):
    path = Path(path)
    original = path.read_text(encoding="utf-8")
    if original.count(START) != 1 or original.count(END) != 1:
        raise ValueError("README requires exactly one snapshot marker pair")
    begin, finish = original.index(START) + len(START), original.index(END)
    if finish < begin:
        raise ValueError("README snapshot markers are reversed")
    updated = original[:begin] + "\n\n" + snapshot + "\n\n" + original[finish:]
    if updated == original:
        return False
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(updated, encoding="utf-8", newline="\n")
    temporary.replace(path)
    return True


def generate(data=ROOT / "data", readme=ROOT / "README.md"):
    data = Path(data)
    report = json.loads((data / "cluster.json").read_text(encoding="utf-8"))
    policy = json.loads((data / "strategy.json").read_text(encoding="utf-8"))
    config_file = data / "site-config.json"
    config = json.loads(config_file.read_text(encoding="utf-8")) if config_file.exists() else {}
    return update_readme(readme, render_snapshot(report, policy, config))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--readme", type=Path, default=ROOT / "README.md")
    args = parser.parse_args()
    print("Updated README campaign snapshot" if generate(args.data, args.readme) else "README campaign snapshot unchanged")
