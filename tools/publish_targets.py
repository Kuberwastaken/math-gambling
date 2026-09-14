#!/usr/bin/env python3
"""Publish cross-target results to their own `targets-data` branch.

Isolated from the 114 pipeline: it commits only data/targets/** and the README
to a dedicated branch using a throwaway git index, so `main`, its index, and the
114 `cluster-data` branch are never touched. Mirrors the safe snapshot pattern in
branch_state.py without importing or modifying it.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BRANCH = "targets-data"
UA = "OpenAI File Downloader, XaiImageApiFetch/1.0"
INCLUDE = ("data/targets", "README.md")


def git(repo, *args, env=None, check=True):
    r = subprocess.run(["git", "-c", f"http.userAgent={UA}", "-C", str(repo), *args],
                       capture_output=True, env=env)
    if check and r.returncode:
        raise RuntimeError(r.stderr.decode("utf-8", "replace").strip() or "git failed")
    return r


def publish(repo, *, remote="origin", push=False):
    repo = Path(repo).resolve()
    if not any((repo / p).exists() for p in INCLUDE):
        raise RuntimeError("nothing to publish: data/targets and README.md are both absent")
    git_dir = git(repo, "rev-parse", "--absolute-git-dir").stdout.decode().strip()
    # Start the branch tree from its current tip if it exists, else empty.
    parent = None
    ls = git(repo, "ls-remote", "--exit-code", "--heads", remote, f"refs/heads/{BRANCH}", check=False)
    if ls.returncode == 0:
        git(repo, "fetch", "--no-tags", "--depth=1", remote, f"+refs/heads/{BRANCH}:refs/remotes/{remote}/{BRANCH}")
        parent = git(repo, "rev-parse", f"refs/remotes/{remote}/{BRANCH}").stdout.decode().strip()
    with tempfile.TemporaryDirectory(prefix="mg-targets-index-") as tmp:
        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = str(Path(tmp) / "index")
        base = ["git", "--git-dir", git_dir, "--work-tree", str(repo)]

        def run(*a):
            r = subprocess.run([*base, *a], cwd=repo, env=env, capture_output=True)
            if r.returncode:
                raise RuntimeError(r.stderr.decode("utf-8", "replace"))
            return r.stdout.decode().strip()

        run("read-tree", "--empty")
        # Stage only the target data and README; nothing else from the tree.
        run("add", "--", *[p for p in INCLUDE if (repo / p).exists()])
        tree = run("write-tree")
    if parent and git(repo, "rev-parse", f"{parent}^{{tree}}").stdout.decode().strip() == tree:
        return {"branch": BRANCH, "commit": parent, "changed": False, "pushed": False}
    args = ["commit-tree", tree, "-m", "Publish cross-target results"]
    if parent:
        args += ["-p", parent]
    cenv = os.environ.copy()
    cenv.setdefault("GIT_AUTHOR_NAME", "Math Gambling targets")
    cenv.setdefault("GIT_AUTHOR_EMAIL", "41898282+github-actions[bot]@users.noreply.github.com")
    cenv.setdefault("GIT_COMMITTER_NAME", cenv["GIT_AUTHOR_NAME"])
    cenv.setdefault("GIT_COMMITTER_EMAIL", cenv["GIT_AUTHOR_EMAIL"])
    commit = git(repo, *args, env=cenv).stdout.decode().strip()
    if push:
        git(repo, "push", remote, f"{commit}:refs/heads/{BRANCH}")
    return {"branch": BRANCH, "commit": commit, "changed": True, "pushed": push}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args(argv)
    import json
    print(json.dumps(publish(args.repo, remote=args.remote, push=args.push), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
