"""Mark notes superseded and repoint existing chains."""
from __future__ import annotations

from datetime import date

from . import check, migrate


def _load(config):
    documents = {}
    for path, relative, _parts in check.iter_notes(config):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        data, body = check.parse(text)
        documents[relative] = {
            "path": path,
            "relative": relative,
            "data": data,
            "body": body,
            "text": text,
        }
    return documents


def plan(config, olds, new):
    documents = _load(config)
    by_relative = {relative: doc["data"] for relative, doc in documents.items() if doc["data"]}
    target = check._resolve_target(new, by_relative)
    if target is None:
        raise RuntimeError(f"新笔记不存在：{new}")
    old_paths = []
    for old in olds:
        resolved = check._resolve_target(old, by_relative)
        if resolved is None:
            raise RuntimeError(f"旧笔记不存在：{old}")
        if resolved == target:
            raise RuntimeError("新旧笔记不能相同")
        old_paths.append(resolved)

    changes = {}
    for old in old_paths:
        doc = documents[old]
        data = dict(doc["data"])
        data["status"] = "superseded"
        data["supersededBy"] = target
        data.setdefault("validUntil", date.today().isoformat())
        if not data.get("validUntil"):
            data["validUntil"] = date.today().isoformat()
        changes[old] = {"data": data, "reasons": ["supersede"]}

    for relative, doc in documents.items():
        data = doc["data"]
        if not data:
            continue
        pointer = str(data.get("supersededBy") or "").strip()
        if not pointer:
            continue
        resolved = check._resolve_target(pointer, by_relative)
        if resolved in old_paths and relative != target:
            updated = dict(data)
            updated["supersededBy"] = target
            entry = changes.setdefault(relative, {"data": updated, "reasons": []})
            entry["reasons"].append("repoint")
            entry["data"] = updated

    for relative, entry in changes.items():
        entry["relative"] = relative
        entry["path"] = documents[relative]["path"]
    return changes


def apply(config, olds, new):
    changes = plan(config, olds, new)
    for relative, entry in changes.items():
        doc = _load(config)[relative]
        text = doc["text"]
        match = check.FRONTMATTER_RE.match(text)
        body = text[match.end() :] if match else text
        prefix = "" if body.startswith("\n") else "\n"
        entry["path"].write_text(
            f"---\n{migrate._dump(entry['data'])}\n---\n{prefix}{body}", encoding="utf-8"
        )
    return changes
