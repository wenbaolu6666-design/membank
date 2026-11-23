"""Migrate legacy notes to the v2 frontmatter rules."""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from . import check

TYPE_MAP = {
    "fact": "reference",
    "project-fact": "reference",
    "record": "reference",
    "execution-report": "reference",
    "execution-record": "reference",
    "task-record": "reference",
    "delivery": "reference",
    "feature": "reference",
    "implementation": "reference",
    "verification": "reference",
    "qa-result": "reference",
    "pr": "reference",
    "log": "reference",
    "fix": "reference",
    "核验报告": "reference",
    "核验记录": "reference",
    "progress": "context",
    "project_context": "context",
    "convention": "constraint",
    "policy": "constraint",
    "incident": "lesson",
    "incident-note": "lesson",
    "bugfix": "lesson",
}
STATUS_MAP = {
    "completed": "active",
    "completed-pending-a1-ruling": "active",
    "done": "active",
    "closed": "active",
    "merged": "active",
    "in-progress": "active",
    "open-pr": "active",
}
DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}[-_ ]*")


def _title_from(body, relative):
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    stem = Path(relative).stem
    return DATE_PREFIX.sub("", stem).replace("-", " ") or stem


def _dump(data):
    return yaml.safe_dump(
        data, allow_unicode=True, sort_keys=False, default_flow_style=False
    ).strip()


def _repair(text):
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == "---"), None)
    if start is None:
        return text
    end = next((i for i in range(start + 1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return text
    fixed = []
    for line in lines[start + 1 : end]:
        if ":" in line and not line.startswith((" ", "\t", "#")):
            key, _, value = line.partition(":")
            raw = value.strip()
            if raw and not raw.startswith(('"', "'", "[", "{")) and ": " in raw:
                value = " " + json.dumps(raw, ensure_ascii=False)
            fixed.append(f"{key}:{value}" if value.startswith(" ") else f"{key}: {raw}")
        else:
            fixed.append(line)
    body = "\n".join(lines[end + 1 :])
    return "---\n" + "\n".join(fixed) + "\n---\n" + body


def plan(config):
    agents = set(config.agents)
    changes = []
    for path, relative, parts in check.iter_notes(config):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        data, body = check.parse(text)
        repaired = False
        if data is None and text.lstrip().startswith("---"):
            repaired = _repair(text)
            data, body = check.parse(repaired)
            if data is None:
                changes.append(
                    {"path": path, "relative": relative, "reasons": ["malformed"], "new": None}
                )
                continue
        if data is None:
            data = {}
            body = text
        new = dict(data)
        reasons = []

        expected = check._expected_scope(parts, agents)
        if expected and str(new.get("scope") or "") != expected:
            new["scope"] = expected
            reasons.append("scope")

        inferred = check._infer_agent(parts, agents)
        if inferred and str(new.get("agent") or "") != inferred:
            new["agent"] = inferred
            reasons.append("agent")

        memory_type = str(new.get("type") or "").strip()
        if memory_type not in check.VALID_TYPES:
            new["type"] = TYPE_MAP.get(memory_type.casefold(), "reference")
            reasons.append("type")

        status = str(new.get("status") or "").strip()
        if status not in check.VALID_STATUSES:
            new["status"] = STATUS_MAP.get(status.casefold(), "active")
            reasons.append("status")

        if not str(new.get("title") or "").strip():
            new["title"] = _title_from(body, relative)
            reasons.append("title")

        if parts[0] == "projects" and len(parts) > 1 and not new.get("project"):
            new["project"] = parts[1]
            reasons.append("project")

        if data != new or repaired:
            changes.append({"path": path, "relative": relative, "reasons": reasons, "new": new})
        elif data is None:
            changes.append({"path": path, "relative": relative, "reasons": ["frontmatter"], "new": new})
    return changes


def apply(config):
    changes = plan(config)
    written = 0
    for change in changes:
        if change["new"] is None:
            continue
        path = change["path"]
        text = path.read_text(encoding="utf-8", errors="replace")
        match = check.FRONTMATTER_RE.match(text)
        body = text[match.end() :] if match else text
        prefix = "" if body.startswith("\n") else "\n"
        path.write_text(
            f"---\n{_dump(change['new'])}\n---\n{prefix}{body}", encoding="utf-8"
        )
        written += 1
    return written, changes
