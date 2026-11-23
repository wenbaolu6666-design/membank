#!/usr/bin/env python3
"""Verify the private memory vault and the public engine repo stay separate."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = ("notes", "projects", ".obsidian", ".membank", "profile.md")


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def commits(repo):
    result = git(repo, "rev-list", "--all")
    return set(result.stdout.split()) if result.returncode == 0 else set()


def remote(repo):
    result = git(repo, "remote", "get-url", "origin")
    return result.stdout.strip() if result.returncode == 0 else ""


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check vault/public repo isolation")
    parser.add_argument("--vault", default=str(ROOT))
    parser.add_argument("--public", default=str(ROOT.parent / "membank"))
    args = parser.parse_args(argv)

    vault = Path(args.vault).resolve()
    public = Path(args.public).resolve()
    checks = []

    checks.append(("vault is a git repo", (vault / ".git").exists(), str(vault)))
    checks.append(("public is a git repo", (public / ".git").exists(), str(public)))
    checks.append(
        (
            "paths do not nest",
            not public.is_relative_to(vault) and not vault.is_relative_to(public),
            f"{vault} <> {public}",
        )
    )

    shared = commits(vault) & commits(public)
    checks.append(("no shared commits", not shared, f"{len(shared)} shared"))

    vault_remote = remote(vault)
    public_remote = remote(public)
    checks.append(
        (
            "different remotes",
            bool(vault_remote) and bool(public_remote) and vault_remote != public_remote,
            f"{vault_remote} <> {public_remote}",
        )
    )

    found = [name for name in FORBIDDEN if (public / name).exists()]
    checks.append(("public tree has no private data", not found, ", ".join(found) or "clean"))

    failed = 0
    for name, ok, detail in checks:
        print(f"{'OK  ' if ok else 'FAIL'}  {name:<28} {detail}")
        failed += 0 if ok else 1
    print(f"\n{'隔离检查通过' if failed == 0 else f'{failed} 项失败'}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
