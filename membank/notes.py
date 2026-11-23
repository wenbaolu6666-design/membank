"""Direct writes for explicitly confirmed user requests."""
from __future__ import annotations

import json
import re
from datetime import date, datetime

import yaml

from . import grants

SAFE_NAME_RE = re.compile(r'[\\/:*?"<>|\r\n]+')


def _slug(title):
    cleaned = SAFE_NAME_RE.sub("", str(title or "")).strip().strip(".")
    cleaned = re.sub(r"\s+", "-", cleaned)
    return cleaned[:50] or "note"


def _existing_titles(folder):
    titles = set()
    if not folder.is_dir():
        return titles
    for path in folder.glob("*.md"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not text.startswith("---"):
            continue
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        try:
            data = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            continue
        if isinstance(data, dict) and data.get("title"):
            titles.add(str(data["title"]).strip().casefold())
    return titles


def add_note(
    config,
    title,
    content,
    scope="global",
    memory_type="reference",
    project=None,
    confirmed=False,
):
    if not confirmed:
        raise RuntimeError(
            "direct write requires confirmed=true; only set it when the user explicitly asked to remember this"
        )
    agent = config.mcp_agent
    if not agent:
        raise RuntimeError("instance has no agent identity; direct write is disabled")
    scope = str(scope or "global")
    if scope not in ("global", "project"):
        raise RuntimeError("direct write supports global or project scope; use memory_propose for sub")
    if scope == "project" and not project:
        raise RuntimeError("project scope requires project")
    base = config.vault / "notes" / agent
    if scope == "project":
        base = config.vault / "projects" / str(project) / "notes" / agent
    if str(title).strip().casefold() in _existing_titles(base):
        raise RuntimeError("a note with the same title already exists; use memory_propose to merge")
    base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{stamp}-{_slug(title)}.md"
    target = base / filename
    if target.exists():
        target = base / f"{stamp}-{datetime.now().microsecond}-{_slug(title)}.md"
    frontmatter = [
        "---",
        f"title: {json.dumps(str(title), ensure_ascii=False)}",
        f"scope: {scope}",
        f"type: {memory_type}",
        "status: active",
        f"validFrom: {date.today().isoformat()}",
        "confidence: medium",
        f"project: {json.dumps(str(project), ensure_ascii=False) if project else 'null'}",
        f"agent: {agent}",
        "source: conversation:confirmed",
        "---",
        "",
    ]
    target.write_text("\n".join(frontmatter) + str(content).rstrip() + "\n", encoding="utf-8")
    relative = target.relative_to(config.vault).as_posix()
    grants.audit(config, agent, agent, "add_note", relative)
    return target
