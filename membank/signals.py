"""Deterministic conflict signals for the memory vault."""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
import sqlite3
import struct
from datetime import date
from difflib import SequenceMatcher

from .i18n import t

STATE_FILE = "signals-state.json"
VERSION_RE = re.compile(r"\b\d+(?:\.\d+){1,3}\b")


def _is_note(path):
    return "/notes/" in "/" + path.replace("\\", "/")


def _unpack(blob):
    if not blob or len(blob) % 4:
        return []
    return struct.unpack("<" + "f" * (len(blob) // 4), blob)


def _cosine(left, right):
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    norm_left = math.sqrt(sum(a * a for a in left)) or 1.0
    norm_right = math.sqrt(sum(b * b for b in right)) or 1.0
    return dot / (norm_left * norm_right)


def signal_id(first, second):
    return hashlib.sha1("|".join(sorted((first, second))).encode("utf-8")).hexdigest()[:10]


def _load_state(config):
    path = config.state_dir / STATE_FILE
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(config, state):
    path = config.state_dir / STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _documents(connection):
    rows = connection.execute(
        "SELECT path, title, scope, agent, status, valid_until, layer_rel, "
        "content, mirrors, source_hash FROM documents"
    ).fetchall()
    keys = (
        "path",
        "title",
        "scope",
        "agent",
        "status",
        "valid_until",
        "layer_rel",
        "content",
        "mirrors",
        "source_hash",
    )
    return [dict(zip(keys, row, strict=False)) for row in rows]


def _doc_vector(connection, path, cache):
    if path in cache:
        return cache[path]
    rows = connection.execute(
        "SELECT embedding FROM chunks WHERE path = ? ORDER BY chunk_index", (path,)
    ).fetchall()
    vectors = [_unpack(row[0]) for row in rows if row[0]]
    if not vectors:
        cache[path] = []
        return []
    dimension = len(vectors[0])
    total = [0.0] * dimension
    for vector in vectors:
        if len(vector) != dimension:
            continue
        for index, value in enumerate(vector):
            total[index] += value
    count = len(vectors)
    cache[path] = [value / count for value in total]
    return cache[path]


def _planes(dimension, bits):
    rng = random.Random(20261123 + dimension)
    return [[rng.uniform(-1.0, 1.0) for _ in range(dimension)] for _ in range(bits)]


def _candidate_pairs(items, vectors, config):
    """Return candidate pairs; LSH buckets for large layers, brute force for small."""
    if len(items) <= config.signals_bruteforce_limit:
        return [
            (first, second)
            for index, first in enumerate(items)
            for second in items[index + 1 :]
        ]
    dimension = next((len(vector) for vector in vectors.values() if vector), 0)
    if not dimension:
        return []
    planes = _planes(dimension, config.signals_bands * config.signals_rows)
    buckets = {}
    for doc in items:
        vector = vectors.get(doc["path"]) or []
        if not vector or len(vector) != dimension:
            continue
        for band in range(config.signals_bands):
            key = 0
            for row in range(config.signals_rows):
                plane = planes[band * config.signals_rows + row]
                if sum(a * b for a, b in zip(vector, plane, strict=False)) >= 0:
                    key |= 1 << row
            buckets.setdefault((band, key), []).append(doc)

    seen = set()
    pairs = []
    for bucket in buckets.values():
        if len(bucket) < 2 or len(bucket) > getattr(config, "signals_max_bucket", 800):
            continue
        for index, first in enumerate(bucket):
            for second in bucket[index + 1 :]:
                marker = tuple(sorted((first["path"], second["path"])))
                if marker in seen:
                    continue
                seen.add(marker)
                pairs.append((first, second))
    return pairs


def detect(config, targets=None):
    """Return deterministic signals; targets limits pairs to touched notes."""
    if not config.db.exists():
        return _structural(config)
    connection = sqlite3.connect(config.db)
    try:
        documents = _documents(connection)
        vector_cache = {}
        groups = {}
        for doc in documents:
            if doc["status"] == "active" and _is_note(doc["path"]):
                groups.setdefault(doc["layer_rel"], []).append(doc)

        found = []
        for layer, items in groups.items():
            vectors = {
                doc["path"]: _doc_vector(connection, doc["path"], vector_cache)
                for doc in items
            }
            for first, second in _candidate_pairs(items, vectors, config):
                if targets and first["path"] not in targets and second["path"] not in targets:
                    continue
                score = _cosine(
                    vectors.get(first["path"], []),
                    vectors.get(second["path"], []),
                )
                if score < config.conflict_similarity:
                    continue
                title_score = SequenceMatcher(None, first["title"], second["title"]).ratio()
                if title_score >= config.title_similarity:
                    kind = "duplicate"
                else:
                    left_numbers = set(VERSION_RE.findall(first["content"]))
                    right_numbers = set(VERSION_RE.findall(second["content"]))
                    kind = (
                        "conflict"
                        if left_numbers and right_numbers and left_numbers != right_numbers
                        else "overlap"
                    )
                found.append(
                    {
                        "id": signal_id(first["path"], second["path"]),
                        "kind": kind,
                        "score": round(score, 3),
                        "title_score": round(title_score, 2),
                        "layer": layer,
                        "paths": [first["path"], second["path"]],
                        "titles": [first["title"], second["title"]],
                        "hashes": [first["source_hash"], second["source_hash"]],
                    }
                )

        today = date.today().isoformat()
        for doc in documents:
            if (
                doc["status"] == "active"
                and _is_note(doc["path"])
                and doc["valid_until"]
                and str(doc["valid_until"])[:10] < today
            ):
                found.append(
                    {
                        "id": "expired:" + hashlib.sha1(doc["path"].encode("utf-8")).hexdigest()[:8],
                        "kind": "expired",
                        "score": 0.0,
                        "title_score": 0.0,
                        "layer": doc["layer_rel"],
                        "paths": [doc["path"]],
                        "titles": [doc["title"]],
                        "hashes": [doc["source_hash"]],
                    }
                )
        return found + _structural(config)
    finally:
        connection.close()


def _structural(config):
    from . import check

    items = []
    for issue in check.collect(config):
        if not issue["code"].startswith(("superseded", "mirror")):
            continue
        items.append(
            {
                "id": "check:" + hashlib.sha1(
                    (issue["code"] + issue["path"]).encode("utf-8")
                ).hexdigest()[:8],
                "kind": issue["code"],
                "score": 0.0,
                "title_score": 0.0,
                "layer": "",
                "paths": [issue["path"]],
                "titles": [issue["message"]],
                "hashes": [],
            }
        )
    return items


def visible(config, items):
    """Attach dismissed state; reopen when either note changed."""
    state = _load_state(config)
    output = []
    for item in items:
        record = state.get(item["id"])
        item = dict(item)
        dismissed = bool(
            record
            and record.get("status") == "dismissed"
            and record.get("hashes") == item["hashes"]
        )
        item["dismissed"] = dismissed
        if not dismissed:
            output.append(item)
    return output


def dismiss(config, identifier, reason=""):
    items = detect(config)
    for item in items:
        if item["id"] == identifier:
            state = _load_state(config)
            state[identifier] = {
                "status": "dismissed",
                "hashes": item["hashes"],
                "paths": item["paths"],
                "reason": reason,
            }
            _save_state(config, state)
            return True
    return False


def format_signal(item):
    header = f"#{item['id']} [{item['kind']}]"
    if item["score"]:
        header += " " + t("signal.score", score=f"{item['score']:.2f}")
    lines = [header]
    for path, title in zip(item["paths"], item["titles"], strict=False):
        lines.append(f"  - {path} | {title}")
    if item["kind"] == "duplicate":
        lines.append("  " + t("signal.duplicate"))
    elif item["kind"] == "conflict":
        lines.append("  " + t("signal.conflict"))
    elif item["kind"] == "overlap":
        lines.append("  " + t("signal.overlap"))
    elif item["kind"] == "expired":
        lines.append("  " + t("signal.expired"))
    elif item["kind"].startswith("superseded"):
        lines.append("  " + t("signal.superseded"))
    elif item["kind"].startswith("mirror"):
        lines.append("  " + t("signal.mirror"))
    return "\n".join(lines)
