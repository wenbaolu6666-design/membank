"""Review and apply memory proposals."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import yaml

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
SAFE_NAME_RE = re.compile(r'[\\/:*?"<>|\r\n]+')


def _proposal_dirs(config):
    if not config.proposals.is_dir():
        return []
    return sorted(
        (item for item in config.proposals.iterdir() if item.is_dir()),
        key=lambda item: item.name,
        reverse=True,
    )


def _manifest(folder):
    path = folder / "manifest.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def list_proposals(config):
    rows = []
    for folder in _proposal_dirs(config):
        manifest = _manifest(folder)
        note = folder / "note.md"
        rows.append(
            {
                "id": folder.name,
                "status": manifest.get("status", "unknown"),
                "title": manifest.get("arguments", {}).get("title", ""),
                "created_at": manifest.get("created_at", ""),
                "has_note": note.is_file(),
            }
        )
    return rows


def show_proposal(config, identifier):
    folder = config.proposals / identifier
    if not folder.is_dir():
        raise RuntimeError(f"提案不存在：{identifier}")
    manifest = _manifest(folder)
    note = folder / "note.md"
    text = note.read_text(encoding="utf-8") if note.is_file() else "(缺少 note.md)"
    header = json.dumps(manifest, ensure_ascii=False, indent=2)
    return f"{header}\n\n{text}"


def _split_frontmatter(text):
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise RuntimeError("提案缺少 frontmatter")
    data = yaml.safe_load(match.group(1)) or {}
    if not isinstance(data, dict):
        raise RuntimeError("frontmatter 不是合法映射")
    body = text[match.end() :]
    return data, body


def _slug(title):
    cleaned = SAFE_NAME_RE.sub("", str(title or "")).strip().strip(".")
    cleaned = re.sub(r"\s+", "-", cleaned)
    return cleaned[:50] or datetime.now().strftime("note-%Y%m%d-%H%M%S")


def create_proposal(
    config,
    title,
    content,
    scope="project",
    memory_type="reference",
    project=None,
    agent=None,
    source="agent",
    supersedes=None,
):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", title).strip("-")[:40].lower() or "note"
    folder = config.proposals / f"{stamp}-{slug}"
    folder.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        f"title: {title}",
        f"scope: {scope}",
        f"type: {memory_type}",
        "status: temporary",
        "confidence: medium",
        f"project: {project or 'null'}",
        f"agent: {agent or 'null'}",
    ]
    if supersedes:
        lines.append(f"supersedes: {supersedes}")
    lines.extend(["---", ""])
    note_path = folder / "note.md"
    note_path.write_text("\n".join(lines) + content.rstrip() + "\n", encoding="utf-8")
    manifest = {
        "id": folder.name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": "pending",
        "source": source,
        "arguments": {
            "title": title,
            "scope": scope,
            "type": memory_type,
            "project": project,
            "agent": agent,
            "supersedes": supersedes,
        },
    }
    (folder / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return folder.name, note_path


def _destination(config, data, target=None):
    if target:
        target_path = Path(target)
        if not target_path.is_absolute():
            target_path = config.vault / target_path
    else:
        scope = str(data.get("scope") or "project")
        agent = str(data.get("agent") or "").strip()
        project = str(data.get("project") or "").strip()
        filename = _slug(data.get("title")) + ".md"
        if scope == "global":
            base = config.vault / "notes"
            target_path = base / agent / filename if agent and agent != "null" else base / filename
        else:
            if not project or project == "null":
                raise RuntimeError("项目级提案需要 project 字段，或显式传 --target")
            base = config.vault / "projects" / project / "notes"
            target_path = base / agent / filename if agent and agent != "null" else base / filename
    target_path = target_path.resolve()
    if not target_path.is_relative_to(config.vault.resolve()):
        raise RuntimeError("目标路径必须位于记忆库内")
    relative = target_path.relative_to(config.vault.resolve()).as_posix()
    if not relative.startswith(("notes/", "projects/")):
        raise RuntimeError("目标路径必须位于 notes/ 或 projects/ 下")
    return target_path


def apply_proposal(config, identifier, target=None, overwrite=False):
    folder = config.proposals / identifier
    if not folder.is_dir():
        raise RuntimeError(f"提案不存在：{identifier}")
    manifest = _manifest(folder)
    if manifest.get("status") == "applied":
        raise RuntimeError(f"提案已合入：{manifest.get('applied_to')}")
    note = folder / "note.md"
    if not note.is_file():
        raise RuntimeError("提案缺少 note.md")
    text = note.read_text(encoding="utf-8")
    data, _body = _split_frontmatter(text)
    for field in ("title", "scope", "type", "status"):
        if not data.get(field):
            raise RuntimeError(f"frontmatter 缺少 {field}")
    destination = _destination(config, data, target)
    if destination.exists() and not overwrite:
        raise RuntimeError(f"目标已存在：{destination}（确认后加 --overwrite）")
    destination.parent.mkdir(parents=True, exist_ok=True)
    accepted = text.replace('status: temporary', 'status: active', 1)
    if 'status: "temporary"' in accepted:
        accepted = accepted.replace('status: "temporary"', 'status: "active"', 1)
    destination.write_text(accepted, encoding="utf-8")
    manifest.update(
        {
            "status": "applied",
            "applied_at": datetime.now().isoformat(timespec="seconds"),
            "applied_to": destination.relative_to(config.vault.resolve()).as_posix(),
        }
    )
    (folder / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return destination
