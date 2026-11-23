# membank

本地优先、分层隔离、可版本化的 AI 长期记忆库。Markdown + Git 是权威源，SQLite 只是可重建的检索副本；Codex、Claude Code、Cursor、Antigravity、ZCode 等智能体通过 CLI 或 MCP 共用同一份记忆。

## 核心特性

- **按路径分层**：全局 / 项目 / 子文件夹三级，目录即归属
- **多智能体隔离**：每级都有共享层与私有层，默认只读共享 + 自己
- **Git 版本化**：`local` 本地 Git（无远程），`cloud` 加远程；Git 为必需项
- **混合检索**：字符 n-gram 关键词 + 向量语义
- **冲突信号**：重复、矛盾、过期、悬挂取代、单向镜像
- **写入可控**：默认提案制，用户确认后才落库；明确说"记住"才直写本层
- **MCP 接口**：10 个工具，支持采样回请当前会话模型
- **zh / en**：CLI 与 MCP 文案可切换

## 快速开始

```bash
pipx install membank
# 或：python -m membank ...

membank init ~/memory-bank                 # 默认 local Git
membank init ~/memory-bank --mode cloud --remote <仓库地址>

cd ~/memory-bank
membank index
membank search "关键词" --agent codex
```

初始化会检测本机已安装的智能体，生成 `AGENTS.md`、`profile.md`、`memory-bank.toml`、`notes/`、`projects/`，并创建本地 Git 提交。

## 架构一览

```
Agents (Codex / Claude / Cursor / Antigravity / ZCode)
        │  CLI                 │  MCP stdio
        ▼                     ▼
                 membank engine
   config / agents / i18n        indexer / search
   check / migrate / supersede   signals / curate
   notes / grants / summary      mcp server
        │
        ▼
  Vault：Markdown + Git HEAD
  State：.membank/（索引、提案、任务、授权、审计）
```

## 文档

- [架构与数据流](docs/ARCHITECTURE.md)
- [CLI 命令参考](docs/CLI.md)
- [配置参考](docs/CONFIG.md)
- [部署与版本控制模式](docs/DEPLOY.md)
- [MCP 接口](docs/MCP.md)
- [各智能体接入](docs/AGENT-SETUP.md)
- [项目规范](docs/SPEC.md)
- [变更日志](CHANGELOG.md)

## 开发

```bash
python -m pip install -e ".[dev]"
ruff check .
mypy membank
python -m unittest discover -s tests -v
```

## 许可证

MIT
