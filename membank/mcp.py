"""Stdio MCP server exposing the memory vault to AI agents."""
from __future__ import annotations

import contextlib
import io
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from . import __version__, check, grants
from .config import load_config
from .i18n import t

PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
MAX_READ_CHARS = 50000
SAMPLING_OK = False
_SAMPLE_ID = 0

TOOLS = [
    {
        "name": "memory_status",
        "description": "查看记忆库路径、索引提交、笔记数量与可用智能体。",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "memory_list",
        "description": "列出记忆条目，可按范围、智能体与状态过滤。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope": {"type": "string", "enum": ["global", "project", "sub"]},
                "agent": {"type": "string", "description": "只返回共享层与该智能体私有层"},
                "status": {"type": "string", "default": "active"},
                "limit": {"type": "integer", "default": 50, "minimum": 1, "maximum": 500},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "memory_search",
        "description": "混合检索记忆，返回得分、路径与命中摘要。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "agent": {"type": "string", "default": "shared"},
                "scope": {
                    "type": "string",
                    "enum": ["related", "global", "project", "sub", "all"],
                    "default": "related",
                },
                "path": {"type": "string", "description": "当前项目绝对路径，默认记忆库根目录"},
                "top": {"type": "integer", "default": 8, "minimum": 1, "maximum": 50},
                "include_temporary": {"type": "boolean", "default": False},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "memory_read",
        "description": "按相对路径读取一条记忆的全文。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对记忆库根目录的路径"},
                "agent": {
                    "type": "string",
                    "description": "读取其他智能体私有层时填写，需用户先授权",
                },
                "max_chars": {"type": "integer", "default": 20000, "minimum": 200},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "memory_propose",
        "description": "提交一条待审记忆提案；不会直接写入正式笔记。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "scope": {"type": "string", "enum": ["global", "project", "sub"], "default": "project"},
                "type": {"type": "string", "default": "reference"},
                "project": {"type": "string"},
                "agent": {"type": "string"},
            },
            "required": ["title", "content"],
            "additionalProperties": False,
        },
    },
    {
        "name": "memory_signals",
        "description": "列出未处理的冲突信号：重复、矛盾、过期。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50}
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "memory_summary",
        "description": "返回当前派生摘要，可直接用于会话首轮注入。",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "memory_curate",
        "description": "生成整理任务：返回变更笔记、近邻、冲突与输出 schema。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "since": {"type": "string"},
                "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 200},
                "sample": {
                    "type": "boolean",
                    "default": False,
                    "description": "请求宿主用当前会话模型执行整理",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "memory_submit",
        "description": "提交整理结果；只创建待审提案，不写正式笔记。",
        "inputSchema": {
            "type": "object",
            "properties": {"payload": {"type": "object"}},
            "required": ["payload"],
            "additionalProperties": False,
        },
    },
    {
        "name": "memory_add_note",
        "description": "用户明确要求记住时，直接写入本智能体私有层；否则请用 memory_propose。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "scope": {"type": "string", "enum": ["global", "project"], "default": "global"},
                "type": {"type": "string", "default": "reference"},
                "project": {"type": "string"},
                "confirmed": {
                    "type": "boolean",
                    "default": False,
                    "description": "仅当用户在本轮对话中明确要求记住时设为 true",
                },
            },
            "required": ["title", "content"],
            "additionalProperties": False,
        },
    },
]


def _git_head(vault):
    result = subprocess.run(
        ["git", "-C", str(vault), "rev-parse", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.stdout.decode("ascii", "replace").strip() if result.returncode == 0 else ""


def _tool_status(config, args):
    lines = [
        f"vault: {config.vault}",
        f"db: {config.db}",
        f"model: {config.model}",
        f"agents: {', '.join(config.agents)}",
        f"caller_agent: {config.mcp_agent or 'shared-only'}",
        f"cross_agent_grants: {len(grants.active(config))}",
        f"head: {_git_head(config.vault) or '(no git)'}",
    ]
    if config.db.exists():
        connection = sqlite3.connect(config.db)
        try:
            meta = dict(connection.execute("SELECT key, value FROM metadata"))
        finally:
            connection.close()
        lines.append(f"notes: {meta.get('count', '?')}")
        lines.append(f"chunks: {meta.get('chunk_count', '?')}")
        lines.append(f"indexed_commit: {meta.get('source_commit', '?')}")
    else:
        lines.append("notes: (index missing, run membank index)")
    return "\n".join(lines)


def _resolve_target(config, requested=None):
    requested = str(requested or "").strip()
    if requested == "shared":
        return "", False
    if not requested:
        return config.mcp_agent, False
    if requested == config.mcp_agent:
        return requested, False
    if not config.mcp_agent:
        raise RuntimeError(t("mcp.no_identity"))
    if not grants.allows(config, config.mcp_agent, requested):
        raise RuntimeError(
            t("mcp.grant_hint", target=requested, caller=config.mcp_agent)
        )
    return requested, True


def _note_owner(config, relative, data):
    parts = relative.split("/")
    for index, part in enumerate(parts[:-1]):
        if part == "notes" and index + 1 < len(parts) - 1:
            candidate = parts[index + 1]
            if candidate not in {"archive", "conversations"}:
                return candidate
    declared = str(data.get("agent") or "").strip()
    return declared or None


def _tool_list(config, args):
    if not config.db.exists():
        raise RuntimeError(t("mcp.no_index"))
    clauses = ["1=1"]
    values = []
    if args.get("scope"):
        clauses.append("scope = ?")
        values.append(args["scope"])
    if args.get("status"):
        clauses.append("status = ?")
        values.append(args["status"])
    target, cross = _resolve_target(config, args.get("agent"))
    if cross:
        clauses.append("agent = ?")
        values.append(target)
        grants.audit(config, config.mcp_agent, target, "list")
    elif target:
        clauses.append("(agent IS NULL OR agent = '' OR agent = ?)")
        values.append(target)
    else:
        clauses.append("(agent IS NULL OR agent = '')")
    limit = int(args.get("limit") or 50)
    connection = sqlite3.connect(config.db)
    try:
        rows = connection.execute(
            "SELECT path, title, scope, agent, status, layer_rel FROM documents "
            f"WHERE {' AND '.join(clauses)} ORDER BY path LIMIT ?",
            (*values, limit),
        ).fetchall()
    finally:
        connection.close()
    return "\n".join(
        f"- {path} | {title} | scope={scope} agent={agent or 'shared'} status={status}"
        for path, title, scope, agent, status, _layer in rows
    ) or "(no matches)"


def _tool_search(config, args):
    from . import search

    query = str(args.get("query") or "").strip()
    if not query:
        raise RuntimeError(t("mcp.query_empty"))
    target, cross = _resolve_target(config, args.get("agent"))
    if cross:
        grants.audit(config, config.mcp_agent, target, "search", query)
    agent = target or "shared"
    argv = [
        query,
        "--agent",
        agent,
        "--scope",
        str(args.get("scope") or "related"),
        "--top",
        str(int(args.get("top") or 8)),
        "--path",
        str(Path(args.get("path") or config.vault).expanduser()),
    ]
    if args.get("include_temporary"):
        argv.append("--include-temporary")
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = search.main(argv)
    output = buffer.getvalue().strip()
    if code not in (0, None):
        raise RuntimeError(output or t("mcp.search_fail", code=code))
    return output or "(no matches)"


def _tool_read(config, args):
    rel = str(args.get("path") or "").strip()
    if not rel:
        raise RuntimeError(t("mcp.path_empty"))
    target = Path(rel)
    if not target.is_absolute():
        target = config.vault / target
    target = target.resolve()
    if not target.is_relative_to(config.vault.resolve()):
        raise RuntimeError(t("mcp.path_outside"))
    if not target.is_file():
        raise RuntimeError(t("mcp.file_missing", path=rel))
    text = target.read_text(encoding="utf-8", errors="replace")
    relative = target.relative_to(config.vault.resolve()).as_posix()
    data, _body = check.parse(text)
    owner = _note_owner(config, relative, data or {})
    if owner:
        target, cross = _resolve_target(config, args.get("agent"))
        if cross:
            if owner != target:
                raise RuntimeError(t("mcp.grant_scope"))
            grants.audit(config, config.mcp_agent, target, "read", relative)
        elif owner != (config.mcp_agent or None):
            raise RuntimeError(t("mcp.denied"))
    limit = min(MAX_READ_CHARS, max(200, int(args.get("max_chars") or 20000)))
    if len(text) > limit:
        text = text[:limit] + "\n...(已截断)"
    return text


def _tool_propose(config, args):
    title = str(args.get("title") or "").strip()
    content = str(args.get("content") or "").strip()
    if not title or not content:
        raise RuntimeError(t("mcp.propose_empty"))
    requested = str(args.get("agent") or "").strip()
    if requested and config.mcp_agent and requested != config.mcp_agent:
        raise RuntimeError(t("mcp.propose_identity"))
    if config.mcp_agent:
        args = {**args, "agent": config.mcp_agent}
    from . import curate

    _identifier, note_path = curate.create_proposal(
        config,
        title=title,
        content=content,
        scope=str(args.get("scope") or "project"),
        memory_type=str(args.get("type") or "reference"),
        project=args.get("project"),
        agent=args.get("agent"),
        source="mcp",
    )
    return (
        f"提案已创建：{note_path}\n"
        "确认后移入对应记忆层、补全 frontmatter 并 commit，再运行 membank index。"
    )


def _tool_signals(config, args):
    from . import signals

    items = signals.visible(config, signals.detect(config))
    if not items:
        return t("signals.none")
    limit = max(1, min(50, int(args.get("limit") or 10)))
    return "\n\n".join(signals.format_signal(item) for item in items[:limit])


def _tool_summary(config, args):
    from . import summary

    return summary.load(config)


def _tool_curate(config, args):
    from . import curate_flow

    task, path = curate_flow.prepare(
        config, args.get("since"), int(args.get("limit") or 20)
    )
    bundle = f"task: {path}\n" + json.dumps(task, ensure_ascii=False, indent=2)
    if not args.get("sample"):
        return bundle
    if not SAMPLING_OK:
        return bundle + "\n" + t("sampling.unsupported")
    result = _sample(task)
    payload = curate_flow._parse_json(_sampling_text(result))
    payload.setdefault("task_id", task["task_id"])
    payload["source"] = "sampling"
    created = curate_flow.submit(config, payload)
    return t("sampling.created", count=len(created))


def _sampling_text(result):
    content = (result or {}).get("content")
    if isinstance(content, dict):
        return str(content.get("text") or "")
    if isinstance(content, list):
        return "".join(
            str(part.get("text") or "") for part in content if isinstance(part, dict)
        )
    return ""


def _sample(task):
    global _SAMPLE_ID
    _SAMPLE_ID += 1
    request_id = f"membank-sample-{_SAMPLE_ID}"
    _send(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "sampling/createMessage",
            "params": {
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": task["instructions"]
                            + "\n\n"
                            + json.dumps(task, ensure_ascii=False),
                        },
                    }
                ],
                "maxTokens": 8192,
            },
        }
    )
    while True:
        line = sys.stdin.readline()
        if not line:
            raise RuntimeError(t("sampling.aborted"))
        try:
            message = json.loads(line)
        except ValueError:
            continue
        if message.get("id") != request_id:
            continue
        if "error" in message:
            raise RuntimeError(t("sampling.failed", error=message["error"]))
        return message.get("result") or {}


def _tool_submit(config, args):
    from . import curate_flow

    created = curate_flow.submit(config, args.get("payload") or {})
    return "created: " + ", ".join(created)


def _tool_add_note(config, args):
    from . import notes

    title = str(args.get("title") or "").strip()
    content = str(args.get("content") or "").strip()
    if not title or not content:
        raise RuntimeError(t("mcp.propose_empty"))
    target = notes.add_note(
        config,
        title=title,
        content=content,
        scope=str(args.get("scope") or "global"),
        memory_type=str(args.get("type") or "reference"),
        project=args.get("project"),
        confirmed=bool(args.get("confirmed")),
    )
    return f"written: {target}\nnext: git add -A && git commit, then membank index"


HANDLERS = {
    "memory_status": _tool_status,
    "memory_list": _tool_list,
    "memory_search": _tool_search,
    "memory_read": _tool_read,
    "memory_propose": _tool_propose,
    "memory_signals": _tool_signals,
    "memory_summary": _tool_summary,
    "memory_curate": _tool_curate,
    "memory_submit": _tool_submit,
    "memory_add_note": _tool_add_note,
}


def _handle(message, config):
    method = message.get("method")
    if method == "initialize":
        global SAMPLING_OK
        capabilities = (message.get("params") or {}).get("capabilities") or {}
        SAMPLING_OK = bool(capabilities.get("sampling"))
        requested = (message.get("params") or {}).get("protocolVersion")
        version = requested if requested in SUPPORTED_PROTOCOLS else PROTOCOL_VERSION
        return {
            "protocolVersion": version,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "membank", "version": __version__},
        }
    if method == "tools/list":
        return {
            "tools": [
                {**tool, "description": t("tool." + tool["name"])} for tool in TOOLS
            ]
        }
    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        handler = HANDLERS.get(name)
        if handler is None:
            raise KeyError(t("mcp.unknown_tool", name=name))
        text = handler(config, arguments)
        return {"content": [{"type": "text", "text": text}], "isError": False}
    if method == "ping":
        return {}
    raise KeyError(t("mcp.unknown_method", method=method))


def serve(agent=None):
    config = load_config()
    if agent:
        config.mcp_agent = agent
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            _send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
            continue
        if "id" not in message:
            continue
        try:
            result = _handle(message, config)
            _send({"jsonrpc": "2.0", "id": message["id"], "result": result})
        except Exception as exc:  # noqa: BLE001 - MCP must always answer
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {"code": -32000, "message": str(exc)},
                }
            )
    return 0


def _send(payload):
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    raise SystemExit(serve())
