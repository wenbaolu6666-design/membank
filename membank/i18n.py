"""Minimal zh/en message catalog."""
from __future__ import annotations

import os

CATALOG = {
    "zh": {
        "usage": """membank <command>

  init <dir> [--agents a,b] [--state-dir .membank]  初始化记忆库
  index                       按 Git 模式同步索引
  search "查询" [选项]        检索记忆
  status                      查看库根、状态目录与索引
  doctor                      检查依赖与环境
  check [--strict] [--verbose] 校验结构
  migrate [--apply]           按 v2 规范迁移旧笔记
  supersede <旧...> --by <新> [--apply] 标记取代并回填链路
  signals                     列出冲突信号
  dismiss <id>                忽略信号
  curate list|show|apply      查看与合入提案
  curate prepare [--since C]  生成整理任务，交给当前会话模型
  curate submit <file|->      提交当前会话模型的整理结果
  curate run                  按 backend 生成任务或调用 API
  summary build|show          生成或查看摘要
  inject                      输出注入上下文
  mcp [--agent 名称]          启动 MCP 服务
  grant <目标> [--to 读者] [--minutes N]  跨智能体只读授权
  grants                      查看授权
  revoke <目标> [--to 读者]    撤销授权""",
        "status.vault": "库根",
        "status.state": "状态目录",
        "status.index": "索引",
        "status.model": "模型",
        "status.agents": "智能体",
        "status.remote": "远程",
        "status.no_remote": "无（仅本地）",
        "status.vcs": "版本控制",
        "status.vcs_none": "无 Git",
        "status.vcs_local": "本地 Git",
        "status.vcs_remote": "Git + 远程 {remote}",
        "status.missing": "索引不存在，先运行 membank index",
        "status.bad": "索引格式无法识别，重建后再试",
        "status.stats": "{count} 条笔记 / {chunks} 分块 / schema {schema}",
        "status.behind": "索引落后当前 HEAD，运行 membank index 同步",
        "doctor.model_missing": "未配置（请设置 model）",
        "doctor.installed": "已安装",
        "doctor.missing": "缺失",
        "doctor.head_ok": "HEAD 可读",
        "doctor.head_bad": "不是 git 仓库或无提交",
        "init.done": "已初始化：{path}",
        "init.agents": "智能体：{agents}",
        "init.no_agents": "未检测到，请用 --agents 指定",
        "init.state": "状态目录：{path}",
        "init.next": "下一步：写入第一条笔记 → git init/commit → membank index",
        "init.git_done": "已初始化本地 Git 仓库（无远程）",
        "init.git_failed": "本地 Git 已初始化，但提交失败：{error}",
        "init.git_missing": "未找到 git 命令",
        "init.next_git": "下一步：写入第一条笔记 → git commit → membank index",
        "init.git_remote": "已配置远程：{remote}",
        "init.git_push_failed": "远程已配置，但推送失败：{error}",
        "init.git_identity_missing": "Git 提交需要 user.name / user.email；请先配置，或改用 --mode none",
        "init.cloud_remote_required": "cloud 模式需要 --remote <仓库地址>",
        "grant.usage": "用法：membank grant <目标智能体> [--to 读者] [--minutes N]",
        "grant.need_reader": "请用 --to 指定读者，或先配置 [mcp] agent",
        "grant.done": "已授权：{reader} 可读 {target}，{minutes} 分钟内有效",
        "grants.none": "没有有效授权",
        "grants.line": "- {reader} -> {target}，到期 {expires}",
        "revoke.usage": "用法：membank revoke <目标智能体> [--to 读者]",
        "revoke.done": "已撤销 {count} 条授权",
        "signals.none": "没有未处理的冲突信号",
        "signals.summary": "共 {count} 条；忽略单条：membank dismiss <id>",
        "dismiss.usage": "用法：membank dismiss <id> [--reason 说明]",
        "dismiss.done": "已忽略：{id}",
        "dismiss.notfound": "未找到信号：{id}",
        "curate.usage": "用法：membank curate list|show|apply",
        "curate.none": "没有待审提案",
        "curate.unknown": "未知子命令：{action}",
        "curate.applied": "已合入：{path}",
        "curate.next": "下一步：git add -A && git commit，然后 membank index",
        "curate.submit_usage": "用法：membank curate submit <结果.json|->",
        "curate.show_usage": "用法：membank curate show <id>",
        "curate.apply_usage": "用法：membank curate apply <id> [--target 相对路径] [--overwrite]",
        "curate.created": "已创建 {count} 条提案",
        "curate.task": "任务已生成：{path}",
        "curate.api_created": "已通过 API 创建 {count} 条提案",
        "curate.unknown_arg": "未知参数：{arg}",
        "curate.instructions": "用当前会话模型阅读 changed 与 neighbors，输出严格 JSON：proposals 为新增或更新的记忆，supersedes 指向被取代的旧笔记；conflicts 记录发现的矛盾及处理建议。只输出 JSON，不写文件。",
        "summary.usage": "用法：membank summary build|show",
        "summary.built": "已生成：{path}（{bytes} 字节）",
        "mcp.usage": "用法：membank mcp [--agent <名称>]",
        "mcp.no_args": "mcp 不接受该参数",
        "common.no_args": "{command} 不接受参数",
        "check.usage": "用法：membank check [--strict] [--verbose]",
        "check.summary": "{errors} 个错误，{warnings} 个警告",
        "check.verbose_hint": "加 --verbose 查看逐条明细",
        "check.field_missing": "缺少 {field}",
        "check.frontmatter_missing": "缺少可解析的 frontmatter",
        "check.scope_invalid": "未知 scope：{scope}",
        "check.type_invalid": "未知 type：{type}",
        "check.status_invalid": "未知 status：{status}",
        "check.scope_mismatch": "路径应为 {expected}，frontmatter 写的是 {scope}",
        "check.agent_mismatch": "目录为 {inferred}，frontmatter 写的是 {declared}",
        "check.agent_missing": "私有层建议补 agent: {inferred}",
        "check.superseded_missing": "status=superseded 但缺少 supersededBy",
        "check.superseded_target_missing": "supersededBy 指向不存在的 {target}",
        "check.superseded_chain": "取代目标本身也是 superseded：{target}",
        "check.superseded_stale": "非 superseded 记录仍带 supersededBy",
        "check.expired": "validUntil 已过期：{date}",
        "check.mirror_target_missing": "mirrors 指向不存在的 {target}",
        "check.mirror_oneway": "{target} 未回指本文件",
        "check.project_identity_missing": "缺少 PROJECT.md",
        "check.unreadable": "无法读取：{error}",
        "search.no_db": "SQLite 检索库不存在；先提交 Markdown，再运行 membank index。",
        "search.old_schema": "SQLite 检索库格式过期；运行 membank index 重建后再查询。",
        "search.no_candidates": "没有符合路径、智能体和状态范围的记录",
        "search.no_chunks": "筛选到的笔记没有可检索分块；运行 membank index 重建。",
        "search.header": "检索：{query}；候选 {count} 条 / {chunks} 分块；路径链 {chain}；智能体 {agent}；模型 {model}；索引 {commit}",
        "search.behind": "警告：检索库落后当前 Git 提交；先运行 membank index 同步。",
        "search.fail": "检索失败：{error}",
        "search.conflict": "冲突信号 #{id} [{kind}] {paths}",
        "search.conflict_hint": "运行 membank signals 查看详情",
        "index.no_model": "未配置嵌入模型：请在 memory-bank.toml 设置 model（例如 BAAI/bge-small-zh-v1.5）",
        "index.fail": "索引同步失败：{error}",
        "index.missing_deps": "缺少依赖：{error}",
        "index.no_notes": "没有找到已提交的 Markdown 笔记",
        "index.sync": "同步完成：{docs} 条笔记，{chunks} 个分块；新增/更新向量 {new}，复用 {reused}，路径层 {layers}，模型 {model}",
        "index.hint": "提示：结构检查发现 {errors} 个错误，运行 membank check 查看",
        "index.json_warn": "SQLite 已同步；兼容用 JSON 快照未更新：{error}",
        "index.no_git": "Git 未启用或不可用，改为读取工作区",
        "config.no_vault": "找不到记忆库根目录；用 MEMBANK_VAULT 指定，或先运行 membank init <目录>",
        "signal.duplicate": "建议：核对后合并或标注取代关系",
        "signal.conflict": "建议：核对结论，保留一条并标 superseded",
        "signal.overlap": "建议：确认是否同一主题，必要时合并或互链",
        "signal.expired": "建议：归档或更新 validUntil",
        "signal.superseded": "建议：补齐 supersededBy，或修正取代链",
        "signal.mirror": "建议：补齐双侧 mirrors 引用",
        "signal.score": "相似 {score}",
        "tool.memory_status": "查看记忆库路径、索引提交、笔记数量与可用智能体。",
        "tool.memory_list": "列出记忆条目，可按范围、智能体与状态过滤。",
        "tool.memory_search": "混合检索记忆，返回得分、路径与命中摘要。",
        "tool.memory_read": "按相对路径读取一条记忆的全文。",
        "tool.memory_propose": "提交一条待审记忆提案；不会直接写入正式笔记。",
        "tool.memory_signals": "列出未处理的冲突信号：重复、矛盾、过期。",
        "tool.memory_summary": "返回当前派生摘要，可直接用于会话首轮注入。",
        "tool.memory_curate": "生成整理任务：返回变更笔记、近邻、冲突与输出 schema。",
        "tool.memory_submit": "提交整理结果；只创建待审提案，不写正式笔记。",
        "tool.memory_add_note": "用户明确要求记住时，直接写入本智能体私有层；否则请用 memory_propose。",
        "sampling.unsupported": "客户端未声明 sampling 能力；请把任务交给会话模型，再用 memory_submit 提交。",
        "sampling.created": "已通过会话模型创建 {count} 条提案",
        "sampling.aborted": "sampling 中断：客户端关闭了连接",
        "sampling.failed": "sampling 失败：{error}",
        "mcp.no_identity": "实例未声明身份，不能跨智能体读取",
        "mcp.grant_hint": "未获授权：请用户执行 membank grant {target} --to {caller}",
        "mcp.no_index": "索引不存在，先运行 membank index",
        "mcp.query_empty": "query 不能为空",
        "mcp.search_fail": "检索失败（exit {code}）",
        "mcp.path_empty": "path 不能为空",
        "mcp.path_outside": "path 必须位于记忆库内",
        "mcp.file_missing": "文件不存在：{path}",
        "mcp.grant_scope": "授权仅限指定智能体的私有记忆",
        "mcp.denied": "无权读取其他智能体的私有记忆",
        "mcp.propose_empty": "title 与 content 不能为空",
        "mcp.propose_identity": "不能以其他智能体身份提交提案",
        "mcp.unknown_tool": "未知工具：{name}",
        "mcp.unknown_method": "未知方法：{method}",
    },
    "en": {
        "usage": """membank <command>

  init <dir> [--agents a,b] [--state-dir .membank]  create a vault
  index                       sync index by Git mode
  search "query" [options]    hybrid search
  status                      show vault, state dir and index
  doctor                      check dependencies and environment
  check [--strict] [--verbose] validate note structure
  migrate [--apply]           migrate legacy notes to v2 rules
  supersede <old...> --by <new> [--apply]  mark notes superseded and repoint chains
  migrate [--apply]           migrate legacy notes to v2 rules
  supersede <old...> --by <new> [--apply]  mark notes superseded and repoint chains
  signals                     list conflict signals
  dismiss <id>                ignore a signal
  curate list|show|apply      review and apply proposals
  curate prepare [--since C]  build a task for the current session model
  curate submit <file|->      submit the session model result
  curate run                  build a task or call the API backend
  summary build|show          build or show the summary
  inject                      print session context
  mcp [--agent NAME]          start MCP server
  grant <target> [--to reader] [--minutes N]  read-only cross-agent grant
  grants                      list grants
  revoke <target> [--to reader] revoke a grant""",
        "status.vault": "vault",
        "status.state": "state",
        "status.index": "index",
        "status.model": "model",
        "status.agents": "agents",
        "status.remote": "remote",
        "status.no_remote": "none (local only)",
        "status.vcs": "vcs",
        "status.vcs_none": "no Git",
        "status.vcs_local": "local Git",
        "status.vcs_remote": "Git + remote {remote}",
        "status.missing": "index missing; run membank index",
        "status.bad": "unrecognized index format; rebuild it",
        "status.stats": "{count} notes / {chunks} chunks / schema {schema}",
        "status.behind": "index is behind HEAD; run membank index",
        "doctor.model_missing": "not configured (set model)",
        "doctor.installed": "installed",
        "doctor.missing": "missing",
        "doctor.head_ok": "HEAD readable",
        "doctor.head_bad": "not a git repo or no commits",
        "init.done": "initialized: {path}",
        "init.agents": "agents: {agents}",
        "init.no_agents": "none detected; pass --agents",
        "init.state": "state dir: {path}",
        "init.next": "next: write a note -> git init/commit -> membank index",
        "init.git_done": "local Git initialized (no remote)",
        "init.git_failed": "local Git initialized, but commit failed: {error}",
        "init.git_missing": "git command not found",
        "init.next_git": "next: write a note -> git commit -> membank index",
        "init.git_remote": "remote configured: {remote}",
        "init.git_push_failed": "remote configured, but push failed: {error}",
        "init.git_identity_missing": "git commit needs user.name / user.email; configure it or use --mode none",
        "init.cloud_remote_required": "cloud mode requires --remote <repo url>",
        "grant.usage": "usage: membank grant <target> [--to reader] [--minutes N]",
        "grant.need_reader": "pass --to or configure [mcp] agent",
        "grant.done": "granted: {reader} can read {target} for {minutes} minutes",
        "grants.none": "no active grants",
        "grants.line": "- {reader} -> {target}, expires {expires}",
        "revoke.usage": "usage: membank revoke <target> [--to reader]",
        "revoke.done": "revoked {count} grant(s)",
        "signals.none": "no open conflict signals",
        "signals.summary": "{count} signal(s); dismiss one with: membank dismiss <id>",
        "dismiss.usage": "usage: membank dismiss <id> [--reason text]",
        "dismiss.done": "dismissed: {id}",
        "dismiss.notfound": "signal not found: {id}",
        "curate.usage": "usage: membank curate list|show|apply",
        "curate.none": "no pending proposals",
        "curate.unknown": "unknown subcommand: {action}",
        "curate.applied": "applied: {path}",
        "curate.next": "next: git add -A && git commit, then membank index",
        "curate.submit_usage": "usage: membank curate submit <result.json|->",
        "curate.show_usage": "usage: membank curate show <id>",
        "curate.apply_usage": "usage: membank curate apply <id> [--target PATH] [--overwrite]",
        "curate.created": "created {count} proposal(s)",
        "curate.task": "task created: {path}",
        "curate.api_created": "created {count} proposal(s) via API",
        "curate.unknown_arg": "unknown argument: {arg}",
        "curate.instructions": "Read changed and neighbors with the current session model and return strict JSON: proposals for new or updated memories, supersedes pointing at the replaced note, conflicts for contradictions and suggested handling. Output JSON only; do not write files.",
        "summary.usage": "usage: membank summary build|show",
        "summary.built": "built: {path} ({bytes} bytes)",
        "mcp.usage": "usage: membank mcp [--agent NAME]",
        "mcp.no_args": "mcp does not accept those arguments",
        "common.no_args": "{command} does not accept arguments",
        "check.usage": "usage: membank check [--strict] [--verbose]",
        "check.summary": "{errors} error(s), {warnings} warning(s)",
        "check.verbose_hint": "add --verbose for details",
        "check.field_missing": "missing {field}",
        "check.frontmatter_missing": "missing or invalid frontmatter",
        "check.scope_invalid": "unknown scope: {scope}",
        "check.type_invalid": "unknown type: {type}",
        "check.status_invalid": "unknown status: {status}",
        "check.scope_mismatch": "path expects {expected}, frontmatter says {scope}",
        "check.agent_mismatch": "folder is {inferred}, frontmatter says {declared}",
        "check.agent_missing": "private layer should declare agent: {inferred}",
        "check.superseded_missing": "status=superseded but supersededBy is missing",
        "check.superseded_target_missing": "supersededBy points to missing {target}",
        "check.superseded_chain": "superseded target is also superseded: {target}",
        "check.superseded_stale": "non-superseded note still has supersededBy",
        "check.expired": "validUntil expired: {date}",
        "check.mirror_target_missing": "mirrors points to missing {target}",
        "check.mirror_oneway": "{target} does not point back",
        "check.project_identity_missing": "missing PROJECT.md",
        "check.unreadable": "cannot read: {error}",
        "search.no_db": "SQLite index missing; commit notes and run membank index.",
        "search.old_schema": "SQLite index format is outdated; rebuild with membank index.",
        "search.no_candidates": "no notes match the path, agent and status scope",
        "search.no_chunks": "matched notes have no chunks; rebuild with membank index.",
        "search.header": "search: {query}; {count} notes / {chunks} chunks; chain {chain}; agent {agent}; model {model}; index {commit}",
        "search.behind": "warning: index is behind HEAD; run membank index.",
        "search.fail": "search failed: {error}",
        "search.conflict": "conflict #{id} [{kind}] {paths}",
        "search.conflict_hint": "run membank signals for details",
        "index.no_model": "no embedding model configured; set model in memory-bank.toml (e.g. BAAI/bge-small-zh-v1.5)",
        "index.fail": "index sync failed: {error}",
        "index.missing_deps": "missing dependency: {error}",
        "index.no_notes": "no committed Markdown notes found",
        "index.sync": "sync complete: {docs} notes, {chunks} chunks; embedded {new}, reused {reused}, layers {layers}, model {model}",
        "index.hint": "hint: structure check found {errors} error(s); run membank check",
        "index.json_warn": "SQLite synced; legacy JSON snapshot not updated: {error}",
        "index.no_git": "Git disabled or unavailable; reading the working tree instead",
        "config.no_vault": "vault not found; set MEMBANK_VAULT or run membank init <dir>",
        "signal.duplicate": "suggest: merge or mark superseded",
        "signal.conflict": "suggest: verify and keep one, mark the other superseded",
        "signal.overlap": "suggest: confirm topic overlap, merge or cross-link",
        "signal.expired": "suggest: archive or update validUntil",
        "signal.superseded": "suggest: fix supersededBy or the replacement chain",
        "signal.mirror": "suggest: add the missing mirror reference",
        "signal.score": "similarity {score}",
        "tool.memory_status": "Show vault path, indexed commit, note counts and agents.",
        "tool.memory_list": "List notes filtered by scope, agent and status.",
        "tool.memory_search": "Hybrid search returning score, path and snippet.",
        "tool.memory_read": "Read a note by path relative to the vault.",
        "tool.memory_propose": "Create a pending proposal; never writes canonical notes.",
        "tool.memory_signals": "List open conflict signals: duplicates, conflicts, expiry.",
        "tool.memory_summary": "Return the derived summary for session injection.",
        "tool.memory_curate": "Build a curation task: changed notes, neighbours, signals and output schema.",
        "tool.memory_submit": "Submit curation results as pending proposals; never writes canonical notes.",
        "tool.memory_add_note": "Write directly to this agent's private layer when the user explicitly asked; otherwise use memory_propose.",
        "sampling.unsupported": "client did not advertise sampling; use the session model and memory_submit instead.",
        "sampling.created": "created {count} proposal(s) via the session model",
        "sampling.aborted": "sampling aborted: client closed the stream",
        "sampling.failed": "sampling failed: {error}",
        "mcp.no_identity": "instance has no agent identity; cross-agent read denied",
        "mcp.grant_hint": "not granted: ask the user to run membank grant {target} --to {caller}",
        "mcp.no_index": "index missing; run membank index",
        "mcp.query_empty": "query cannot be empty",
        "mcp.search_fail": "search failed (exit {code})",
        "mcp.path_empty": "path cannot be empty",
        "mcp.path_outside": "path must stay inside the vault",
        "mcp.file_missing": "file not found: {path}",
        "mcp.grant_scope": "grant applies only to that agent's private layer",
        "mcp.denied": "not allowed to read another agent's private memory",
        "mcp.propose_empty": "title and content cannot be empty",
        "mcp.propose_identity": "cannot submit a proposal as another agent",
        "mcp.unknown_tool": "unknown tool: {name}",
        "mcp.unknown_method": "unknown method: {method}",
    },
}

_current = "zh"


def normalize(lang):
    value = str(lang or "").strip().lower()
    if value.startswith("en"):
        return "en"
    if value.startswith("zh"):
        return "zh"
    return "zh"


def set_lang(lang):
    global _current
    _current = normalize(lang)
    return _current


def lang():
    return _current


def t(key, **kwargs):
    table = CATALOG.get(_current, CATALOG["zh"])
    text = table.get(key) or CATALOG["zh"].get(key) or key
    return text.format(**kwargs) if kwargs else text


def detect_lang():
    return normalize(os.environ.get("MEMBANK_LANG") or "")
