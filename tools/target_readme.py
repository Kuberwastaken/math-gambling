#!/usr/bin/env python3
"""Render live cross-target progress into the README between the TARGETS markers.

Reads data/targets/summary.json (written by target_ingest) and rewrites only the
marked block, so the rest of the README and the website are untouched.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from ingest import ROOT, read_json

START = "<!-- TARGETS:START -->"
END = "<!-- TARGETS:END -->"
PLACEHOLDER = "_Live per-target progress appears here once the cross-target verifier has processed banks._"


def render(summary):
    if not isinstance(summary, dict) or not summary.get("targets"):
        return PLACEHOLDER
    rows = ["| Target | Verified tasks | Curve intervals | Empty % | Exact tests |",
            "| ---: | ---: | ---: | ---: | ---: |"]
    for k, v in sorted(summary["targets"].items(), key=lambda kv: int(kv[0])):
        vt = v.get("verified_tasks", 0)
        empty = (100 * v.get("empty_tasks", 0) / vt) if vt else 0.0
        rows.append(f"| {k} | {vt:,} | {v.get('curves', 0):,} | {empty:.0f}% | {v.get('exact_tests', 0):,} |")
    board = summary.get("leaderboard", {})
    top = " · ".join(f"@{a} ({n:,})" for a, n in list(board.items())[:5]) or "—"
    discoveries = len(summary.get("discoveries", []))
    return "\n".join([
        f"_Published {summary.get('updated_at', '')}. Verified target tasks are independently replayed; a null result proves nothing (selective search)._",
        "",
        "\n".join(rows),
        "",
        f"**Top target contributors:** {top}",
        f"**Verified target identities found:** {discoveries}",
    ])


def update(readme_path, summary):
    text = Path(readme_path).read_text(encoding="utf-8")
    if START not in text or END not in text:
        raise ValueError("README is missing the TARGETS markers")
    block = f"{START}\n{render(summary)}\n{END}"
    # Lambda replacement so generated content (backslashes, digits) is inserted verbatim.
    new = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _m: block, text, flags=re.S)
    Path(readme_path).write_text(new, encoding="utf-8", newline="\n")
    return new


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--readme", type=Path, default=ROOT / "README.md")
    args = parser.parse_args(argv)
    update(args.readme, read_json(args.data / "targets" / "summary.json"))
    print("Updated the README TARGETS block")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
