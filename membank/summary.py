"""Build a derived, size-bounded memory summary for session injection."""
from __future__ import annotations

import sqlite3

MAX_BYTES = 9500
MAX_INJECT_CHARS = 10000
HEADINGS = (
    "## User Profile",
    "## User preferences",
    "## General Tips",
    "## What's in Memory",
)


def _profile_bullets(config):
    path = config.vault / "profile.md"
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    bullets = []
    in_static = False
    for line in lines:
        if line.strip().startswith("## "):
            in_static = line.strip().startswith("## static")
            continue
        if in_static and line.strip().startswith(("-", "*")):
            value = line.strip().lstrip("-*").strip()
            if value:
                bullets.append(value)
    return bullets


def _documents(config):
    if not config.db.exists():
        raise RuntimeError("索引不存在，先运行 membank index")
    connection = sqlite3.connect(config.db)
    try:
        rows = connection.execute(
            "SELECT title, memory_type, scope, layer_rel, path FROM documents "
            "WHERE status = 'active'"
        ).fetchall()
    finally:
        connection.close()
    keys = ("title", "type", "scope", "layer", "path")
    return [dict(zip(keys, row, strict=False)) for row in rows]


def _unique(items):
    seen = set()
    output = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def _section(heading, bullets, limit=None):
    chosen = bullets[:limit] if limit else bullets
    if not chosen:
        chosen = ["（暂无）"]
    return "\n".join([heading, *[f"- {item}" for item in chosen], ""])


def render(config, documents):
    profile = _profile_bullets(config)
    preferences = _unique(
        doc["title"]
        for doc in documents
        if doc["scope"] == "global" and doc["type"] in ("preference", "constraint")
    )
    tips = _unique(doc["title"] for doc in documents if doc["type"] == "lesson")
    project_docs = sorted(
        (doc for doc in documents if doc["layer"].startswith("projects/")),
        key=lambda doc: doc["path"],
        reverse=True,
    )
    grouped = {}
    for doc in project_docs[:48]:
        parts = doc["layer"].split("/")
        slug = parts[1] if len(parts) > 1 else "其他"
        grouped.setdefault(slug, []).append(doc["title"])

    text = "v1\n\n"
    text += _section(HEADINGS[0], profile[:12]) + "\n"
    text += _section(HEADINGS[1], preferences[:12]) + "\n"
    text += _section(HEADINGS[2], tips[:12]) + "\n"
    text += HEADINGS[3] + "\n"
    if grouped:
        for slug, titles in grouped.items():
            text += f"### {slug}\n"
            for title in titles[:6]:
                text += f"- {title}\n"
            text += "\n"
    else:
        text += "- （暂无）\n"
    return _fit(text.rstrip() + "\n")


def _fit(text):
    while len(text.encode("utf-8")) > MAX_BYTES:
        lines = text.rstrip().split("\n")
        for index in range(len(lines) - 1, -1, -1):
            if lines[index].startswith("- "):
                del lines[index]
                break
        else:
            break
        text = "\n".join(lines) + "\n"
    return text


def build(config):
    documents = _documents(config)
    text = render(config, documents)
    path = config.state_dir / "summary.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path, text


def load(config):
    path = config.state_dir / "summary.md"
    if not path.is_file():
        path, _ = build(config)
    return path.read_text(encoding="utf-8")


def context_block(config):
    text = load(config)[:MAX_INJECT_CHARS]
    return "\n".join(
        [
            "<membank_context>",
            "<memory_instructions>",
            "以下为 memory-bank 的长期记忆摘要，仅作跨会话背景参考；如与当前指令冲突，以当前对话为准。",
            "需要细节时调用 MCP 工具 memory_search / memory_read；仅在用户明确要求时调用 memory_propose。",
            "</memory_instructions>",
            "<local_membank_memory>",
            text.rstrip(),
            "</local_membank_memory>",
            "</membank_context>",
        ]
    )
