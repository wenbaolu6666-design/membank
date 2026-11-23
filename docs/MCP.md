# MCP 接口

`membank` 以 stdio MCP 服务的形式把记忆库开放给任意智能体，包括 Antigravity 的 `agy-memory`。

## 启动

```bash
python -m membank mcp
```

服务使用换行分隔的 JSON-RPC 2.0，支持 `2025-06-18`、`2025-03-26`、`2024-11-05`，
初始化时按客户端请求协商版本，不依赖第三方包。

## 接入配置

Antigravity / AGY Studio 的 `mcp_config.json`：

```json
{
  "mcpServers": {
    "membank": {
      "command": "python",
      "args": ["-m", "membank", "mcp"],
      "cwd": "D:/path/to/memory-bank"
    }
  }
}
```

Claude Desktop 同结构；Codex 的 `config.toml`：

```toml
[mcp_servers.membank]
command = "python"
args = ["-m", "membank", "mcp"]
cwd = "D:/path/to/memory-bank"
```

## 工具

| 工具 | 作用 | 是否写入 |
|---|---|---|
| `memory_status` | 路径、索引提交、数量、智能体 | 否 |
| `memory_list` | 按范围/智能体/状态列条目 | 否 |
| `memory_search` | 混合检索，返回得分与路径 | 否 |
| `memory_read` | 按相对路径读全文 | 否 |
| `memory_propose` | 写入待审提案 | 只写 `.membank/proposals/` |
| `memory_signals` | 列出未处理的冲突信号 | 否 |
| `memory_summary` | 返回派生摘要，供首轮注入 | 否 |
| `memory_curate` | 生成整理任务 | 只写 `.membank/tasks/` |
| `memory_submit` | 提交整理结果 | 只写 `.membank/proposals/` |
| `memory_add_note` | 用户明确要求记住时直写本层 | 仅限本智能体私有层 |

## 智能体隔离

MCP 实例必须声明自己是哪个智能体，否则只能看到共享层：

身份必须是 `memory-bank.toml` 的 `agents` 列表之一；该列表由 `membank init` 按本机安装检测生成。

```json
{
  "mcpServers": {
    "membank-codex": {
      "command": "python",
      "args": ["-m", "membank", "mcp", "--agent", "codex"],
      "cwd": "D:/path/to/memory-bank"
    }
  }
}
```

也可以用环境变量 `MEMBANK_MCP_AGENT` 或 `memory-bank.toml` 的 `[mcp] agent` 固定。

规则：

- `memory_list` / `memory_search` 永远只返回共享层 + 本实例智能体的私有层
- `memory_read` 拒绝读取其他智能体的私有记忆
- `memory_propose` 不能冒用其他智能体身份
- 不声明身份时按共享层处理，不会回退成全库可见

## 跨智能体只读授权

默认不可跨智能体。用户明确授权后只能读，且有时效、可撤销：

```bash
membank grant zcode --to codex --minutes 30
membank grants
membank revoke zcode --to codex
```

授权期间：

- `memory_read` 传 `agent: "zcode"` 可读对方私有笔记
- `memory_list` 传 `agent: "zcode"` 只列对方私有层
- 每次跨智能体读取写入 `.membank/audit.log`
- 仍然不能写：`memory_propose` 永远只能以本实例身份提交

## Sampling（可选）

`memory_curate` 传 `sample: true` 时，服务端会向客户端发送 `sampling/createMessage`，
用当前会话模型完成任务并自动 `submit`。客户端未声明 `capabilities.sampling` 时不会报错，
而是返回任务包并提示改用 `memory_submit`。

## 直接写入

`memory_add_note` 带 `confirmed: true` 时直接写入，但只允许：

- 当前实例自己的私有层（`notes/<agent>/` 或 `projects/<项目>/notes/<agent>/`）
- 共享层、其他智能体层一律拒绝，仍走提案
- 同标题已存在时拒绝，提示改用 `memory_propose` 合并
- 每次写入记录到 `.membank/audit.log`

`confirmed` 只能由智能体在"用户本轮明确说记住这条"时设置；自动整理、外部触发一律用 `memory_propose`。

只读工具受原有范围约束：默认共享层 + 指定智能体私有层，不返回其他智能体私有层。

`memory_propose` 不会改正式笔记，只生成 `note.md` 与 `manifest.json`，等人工确认后归档。

## 与 agy-memory 的分工

- `agy-memory` 负责跨会话自动提炼与首轮摘要注入，数据在它自己的插件目录。
- `membank` 负责项目级、分层、可版本化的长期记忆。
- 两者可以同时挂载：需要项目约定时调 `membank`，需要历史会话背景时用 `agy-memory`。
- 不建议让两边互相自动写入；跨库同步通过 `memory_propose` 或人工导入。

## 限制

- 检索基于已提交的 Markdown；未 commit 的笔记不在索引里。
- 服务不加认证，只应监听本机 stdio，不要暴露到网络。
- 索引缺失时先运行 `membank index`。
