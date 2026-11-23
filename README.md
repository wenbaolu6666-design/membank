# memory-bank

Markdown/Obsidian 总库是权威源：**一处集中存放**——全局 / 按本地路径分层的项目 / 子文件夹记忆全部收在同一个总库下，绝不在被记录项目自身的目录里落记忆文件；每一级内再分**共享层与智能体私有层**（各智能体默认隔离，相同事实经 mirrors 双向连接）。Git 保存 Markdown；本机 SQLite 只保存 Git HEAD 的检索副本，可从 Markdown 重建。

为多个 AI 编码智能体（Codex、Claude Code、Cursor、Antigravity 等）与人的协同工作流设计。

## 核心设计

1. **一处集中存放**：一切记忆只进总库，项目与子文件夹按本地路径 slug 收进 `projects/` 目录树，不在被记录项目自身目录里创建任何记忆文件；总库内各级独立子树 + 强制检索栈，跨层只经 move。
2. **写入仲裁**：`type → scope` 默认映射表 + 策略优先，判不准就问人，不猜。
3. **智能体分层**：每库内共享层（智能体无关，全员可见）+ 各智能体私有层（默认只写自己、只读自己）；同一事实被多个智能体记录时经 `mirrors` 双向连接，内容一致后才经提升操作合并为共享规范件（借鉴 metronix 的"workspace 共享 + agent 私有"与 mem0 的多级记忆）。
4. **时序有效性**：记忆有生命周期（active/temporary/superseded/archived），矛盾时旧事实标失效而非删除，来源永远可追溯（借用 Zep/Graphiti 的双时态思想）。
5. **检索控制**：默认窄（项目库 + 全局库中与本项目相关的 active 记忆 + 当前智能体的私有层），显式才能放宽；每条结果附 confidence 与 source 摘要。
6. **整合例行**：里程碑级 consolidation——去重、矛盾裁定、镜像合并、临时记忆清理、profile 重算。

完整设计（含借鉴清单与反模式）见 [docs/DESIGN.md](docs/DESIGN.md)，项目规范见 [docs/SPEC.md](docs/SPEC.md)，记忆格式见 [schema/frontmatter.schema.json](schema/frontmatter.schema.json)，示例见 [examples/](examples/)。

## 设计来源

2026-09-28 对 GitHub 上 14 个开源记忆项目做了实测评估（star、许可、隔离机制、Obsidian 兼容性），取其防污染设计糅合而成，并明确排除 5 个反模式。借鉴明细与出处见 DESIGN.md 第 2、3 节。

## 状态

SQLite 检索副本存于 `.membank/index.sqlite`，被 Git 忽略，可随时从 Markdown 重建。

## 使用

```bash
python -m membank init ~/memory-bank --agents codex,claude
python -m membank init ~/memory-bank --git
python -m membank index
python -m membank search "关键词" --agent codex --path ~/memory-bank
python -m membank status
python -m membank doctor
python -m membank check
python -m membank signals
python -m membank curate list
python -m membank curate prepare
python -m membank curate submit -
python -m membank summary build
python -m membank inject
python -m membank mcp
```

MCP 接入说明见 [docs/MCP.md](docs/MCP.md)，各智能体配置见 [docs/AGENT-SETUP.md](docs/AGENT-SETUP.md)，完整部署步骤见 [docs/DEPLOY.md](docs/DEPLOY.md)。

也可 `pip install -e .` 后直接使用 `membank` 命令。

规范 v2.0：Markdown + Git 权威、SQLite 派生；智能体操作入口为总库根目录 `AGENTS.md`，完整规范见 [docs/SPEC.md](docs/SPEC.md)。
