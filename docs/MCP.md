# MCP 接入

`membank` 通过 stdio MCP 把记忆库开放给智能体。服务本身不联网，所有读写都发生在本机。

## 启动

```bash
python -m membank mcp --agent codex
```

`--agent` 是这个实例的身份，必须是 `memory-bank.toml` 的 `agents` 之一；也可以用
`MEMBANK_MCP_AGENT` 或 `[mcp] agent` 固定。不声明身份时只能看到共享层。

协议：JSON-RPC 2.0，换行分隔，支持 `2025-06-18` / `2025-03-26` / `2024-11-05` 协商。

## 各家怎么配

### Codex

`~/.codex/config.toml`：

```toml
[mcp_servers.membank]
command = "python"
args = ["-m", "membank", "mcp", "--agent", "codex"]
cwd = "D:/path/to/memory-bank"
```

### Claude Code / Claude Desktop

`claude_desktop_config.json` 或项目 `.mcp.json`：

```json
{
  "mcpServers": {
    "membank": {
      "command": "python",
      "args": ["-m", "membank", "mcp", "--agent", "claude"],
      "cwd": "D:/path/to/memory-bank"
    }
  }
}
```

### Cursor

`.cursor/mcp.json`：

```json
{
  "mcpServers": {
    "membank": {
      "command": "python",
      "args": ["-m", "membank", "mcp", "--agent", "cursor"],
      "cwd": "D:/path/to/memory-bank"
    }
  }
}
```

### Antigravity / ZCode

插件的 `mcp_config.json` 里加一项，`--agent` 改成 `antigravity` 或 `zcode`：

```json
{
  "mcpServers": {
    "membank": {
      "command": "python",
      "args": ["-m", "membank", "mcp", "--agent", "antigravity"],
      "cwd": "D:/path/to/memory-bank"
    }
  }
}
```

如果宿主不支持 `cwd`，把 `command` 换成绝对路径的 Python，并在 `args` 里用绝对路径启动：
`["D:/path/to/venv/python.exe", "D:/path/to/memory-bank/..."]` 不推荐；简单做法是确保
`python -m membank` 在该环境下可运行，或使用 `pipx install membank`。

## 工具

| 工具 | 参数 | 作用 | 写入 |
|---|---|---|---|
| `memory_status` | 无 | 路径、索引提交、数量、身份 | 否 |
| `memory_list` | `scope/agent/status/limit` | 列条目 | 否 |
| `memory_search` | `query/agent/scope/path/top` | 混合检索 | 否 |
| `memory_read` | `path/agent/max_chars` | 读全文 | 否 |
| `memory_propose` | `title/content/scope/type/project/agent` | 生成待审提案 | 只写 proposals |
| `memory_signals` | `limit` | 冲突信号 | 否 |
| `memory_summary` | 无 | 派生摘要 | 否 |
| `memory_curate` | `since/limit/sample` | 生成整理任务 | 只写 tasks |
| `memory_submit` | `payload` | 提交整理结果 | 只写 proposals |
| `memory_add_note` | `title/content/scope/type/project/confirmed` | 用户确认后直写 | 仅本层 |

## 隔离规则

默认：

- 能读共享层 + 自己的私有层
- 不能读其他智能体私有层
- 不能写共享层或其他智能体层

跨智能体只读需要用户授权：

```bash
membank grant zcode --to codex --minutes 30
membank grants
membank revoke zcode --to codex
```

授权期间 `memory_read` / `memory_list` / `memory_search` 可以带 `agent: "zcode"`，每次读取写
`.membank/audit.log`。授权到期自动失效。

## 直接写入

只有用户在当前对话明确说"记住这条"时，智能体才应传 `confirmed: true`：

```json
{
  "title": "项目约定",
  "content": "所有发布前跑 ruff + mypy",
  "scope": "project",
  "project": "路由网关",
  "confirmed": true
}
```

限制：

- 只能写本智能体私有层
- 同标题已存在会拒绝，提示改用提案
- 写入记审计
- 不能写共享层或其他智能体层

不确定用户是否明确要求时，一律用 `memory_propose`。

## Sampling（可选）

`memory_curate` 传 `sample: true` 时，服务端向客户端发 `sampling/createMessage`，用当前会话模型
完成任务并自动提交。客户端未声明 `capabilities.sampling` 时不会报错，而是返回任务包并提示
改用 `memory_submit`。

## 常见问题

| 现象 | 处理 |
|---|---|
| 搜索没结果 | 先 `git commit`，再 `membank index` |
| 读别人私有层被拒 | 让用户 `membank grant <对方> --to <自己>` |
| 写提案成功但搜不到 | 提案还没 `curate apply`，或合入后没 commit/index |
| 采样没执行 | 客户端不支持 sampling，改用 prepare + submit |
| 身份无效 | `--agent` 必须是配置里的 `agents` 之一 |
| 端口/网络 | 服务是 stdio，不监听端口，不要暴露到网络 |
