"""Prepare curation tasks and submit results from the current session model or an API."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import urllib.request
from datetime import datetime
from urllib.parse import urlsplit

from . import curate, signals
from .i18n import t

OUTPUT_SCHEMA = {
    "task_id": "string",
    "proposals": [
        {
            "title": "string",
            "content": "string",
            "scope": "global|project|sub",
            "type": "preference|decision|constraint|lesson|reference|plan|context",
            "project": "string|null",
            "agent": "string|null",
            "supersedes": "relative path|null",
        }
    ],
    "conflicts": [{"a": "path", "b": "path", "decision": "keep|supersede|merge", "reason": "string"}],
}


def _state_path(config):
    return config.state_dir / "state.json"


def _load_state(config):
    path = _state_path(config)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(config, state):
    path = _state_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _head(config):
    result = subprocess.run(
        ["git", "-C", str(config.vault), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _documents(config):
    if not config.db.exists():
        raise RuntimeError("索引不存在，先运行 membank index")
    connection = sqlite3.connect(config.db)
    try:
        rows = connection.execute(
            "SELECT path, title, scope, agent, memory_type, layer_rel, content, status "
            "FROM documents WHERE status = 'active'"
        ).fetchall()
    finally:
        connection.close()
    keys = ("path", "title", "scope", "agent", "type", "layer", "content", "status")
    return [dict(zip(keys, row, strict=False)) for row in rows]


def _changed(config, since, limit):
    documents = _documents(config)
    if since:
        result = subprocess.run(
            ["git", "-C", str(config.vault), "diff", "--name-only", f"{since}..HEAD", "--", "*.md"],
            capture_output=True,
            text=True,
            check=False,
        )
        changed = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        selected = [doc for doc in documents if doc["path"] in changed]
        if selected:
            return selected
    return sorted(documents, key=lambda doc: doc["path"], reverse=True)[:limit]


def _neighbors(config, changed, limit=10):
    targets = {doc["path"] for doc in changed}
    try:
        found = signals.detect(config, targets=targets)
    except Exception:
        return []
    paths = set()
    for item in found:
        for path in item["paths"]:
            if path not in targets:
                paths.add(path)
    by_path = {doc["path"]: doc for doc in _documents(config)}
    return [by_path[path] for path in list(paths)[:limit] if path in by_path]


def prepare(config, since=None, limit=20):
    state = _load_state(config)
    since = since or state.get("last_curated_commit") or ""
    changed = _changed(config, since, limit)
    neighbors = _neighbors(config, changed)
    task = {
        "task_id": datetime.now().strftime("%Y%m%d-%H%M%S-%f"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "since": since,
        "head": _head(config),
        "changed": [
            {
                "path": doc["path"],
                "title": doc["title"],
                "scope": doc["scope"],
                "type": doc["type"],
                "agent": doc["agent"],
                "content": (doc["content"] or "")[:4000],
            }
            for doc in changed
        ],
        "neighbors": [
            {"path": doc["path"], "title": doc["title"], "content": (doc["content"] or "")[:2000]}
            for doc in neighbors
        ],
        "instructions": t("curate.instructions"),
        "output_schema": OUTPUT_SCHEMA,
    }
    path = config.tasks / f"{task['task_id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
    return task, path


def submit(config, payload):
    proposals = payload.get("proposals") or []
    created = []
    for proposal in proposals:
        title = str(proposal.get("title") or "").strip()
        content = str(proposal.get("content") or "").strip()
        if not title or not content:
            raise RuntimeError("proposal 缺少 title 或 content")
        agent = str(proposal.get("agent") or config.mcp_agent or "").strip() or None
        if agent and agent not in config.agents:
            raise RuntimeError(f"未知智能体：{agent}")
        identifier, _path = curate.create_proposal(
            config,
            title=title,
            content=content,
            scope=str(proposal.get("scope") or "project"),
            memory_type=str(proposal.get("type") or "reference"),
            project=proposal.get("project"),
            agent=agent,
            source=str(payload.get("source") or "agent"),
            supersedes=proposal.get("supersedes"),
        )
        created.append(identifier)
    state = _load_state(config)
    state["last_curated_commit"] = _head(config)
    state["last_task"] = payload.get("task_id") or state.get("last_task")
    state["last_submit_at"] = datetime.now().isoformat(timespec="seconds")
    _save_state(config, state)
    return created


def _parse_json(text):
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned)
    return json.loads(cleaned)


def run_api(config, task):
    if config.ai_backend != "api":
        raise RuntimeError("当前 backend 不是 api；使用 prepare/submit 交给会话模型")
    if not config.ai_model:
        raise RuntimeError("未配置 [ai] model")
    url = config.ai_base_url.rstrip("/") + "/chat/completions"
    host = urlsplit(url).hostname or ""
    if not config.ai_allow_external and host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("外部端点需要 allow_external = true")
    key = os.environ.get(config.ai_key_env, "")
    body = json.dumps(
        {
            "model": config.ai_model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": task["instructions"]},
                {"role": "user", "content": json.dumps(task, ensure_ascii=False)},
            ],
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.loads(response.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    payload = _parse_json(content)
    payload.setdefault("task_id", task["task_id"])
    payload["source"] = "api"
    return submit(config, payload)
