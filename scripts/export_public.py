#!/usr/bin/env python3
"""Export the public whitelist into a clean directory after a leak scan."""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELF = Path(__file__).resolve()
DENY_FILE = ROOT / ".export-deny"
WHITELIST = (
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    "pyproject.toml",
    ".gitignore",
    ".github",
    "memory-bank.example.toml",
    "membank",
    "scripts",
    "schema",
    "templates",
    "examples",
    "docs",
    "tests",
)
FORBIDDEN = (
    r"D:\\+WenPaul",
    r"C:\\+Users\\+WenPaul",
    r"sk-[A-Za-z0-9]{12,}",
    r"ghp_[A-Za-z0-9]{20,}",
    r"github_pat_",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
)
TEXT_SUFFIXES = {".md", ".py", ".toml", ".json", ".txt", ".yml", ".yaml", ".sh", ".ps1"}


def patterns():
    extra = []
    if DENY_FILE.is_file():
        for line in DENY_FILE.read_text(encoding="utf-8").splitlines():
            value = line.strip()
            if value and not value.startswith("#"):
                extra.append(value)
    return (*FORBIDDEN, *extra)


def iter_files():
    for item in WHITELIST:
        path = ROOT / item
        if path.is_file():
            yield path
        elif path.is_dir():
            for child in path.rglob("*"):
                if child.is_file() and "__pycache__" not in child.parts:
                    yield child


def scan(files):
    hits = []
    for path in files:
        if path.resolve() == SELF:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"LICENSE", ".gitignore"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in patterns():
            for match in re.finditer(pattern, text):
                line = text.count("\n", 0, match.start()) + 1
                hits.append(f"{path.relative_to(ROOT)}:{line}  {pattern}")
    return hits


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export public files")
    parser.add_argument("--out", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    files = list(iter_files())
    hits = scan(files)
    if hits:
        print("发现敏感内容，终止导出：")
        print("\n".join(hits[:50]))
        return 1

    out = Path(args.out).expanduser().resolve()
    if out.exists() and any(out.iterdir()) and not args.force:
        print(f"目标目录非空：{out}（确认后加 --force）")
        return 1
    out.mkdir(parents=True, exist_ok=True)
    for path in files:
        destination = out / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    print(f"导出 {len(files)} 个文件到 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
