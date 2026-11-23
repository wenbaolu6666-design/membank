# 各智能体接入

每个实例用 `--agent <名称>` 声明身份，名称必须是 `memory-bank.toml` 的 `agents` 之一。

## Codex

`~/.codex/config.toml`：

```toml
[mcp_servers.membank]
command = "python"
args = ["-m", "membank", "mcp", "--agent", "codex"]
cwd = "D:/path/to/memory-bank"
```

项目约定写在 `AGENTS.md`，引用 `templates/vault/AGENTS.md`。

## Claude Code

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

项目约定写在 `CLAUDE.md`。

## Cursor

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

项目规则写在 `.cursor/rules` 或 `AGENTS.md`。

## Antigravity / ZCode

插件或宿主的 `mcp_config.json` 增加一项：

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

ZCode 把 `--agent` 改成 `zcode`，并挂载同一个 `AGENTS.md`。

## 共同约定

- 私有层目录名与 `--agent` 一致
- 默认只读共享层 + 自己私有层
- 跨智能体读取需要 `membank grant`
- 写入优先 `memory_propose`；用户明确说记住才用 `memory_add_note`
