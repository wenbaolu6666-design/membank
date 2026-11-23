# memory-bank 项目规范 v2.0（开源版草案）

> 状态：草案，2026-11-23。基于 `DESIGN.md` v1.3 与后续讨论整理。
> 本文是新仓库的唯一规范源；`DESIGN.md` 保留为 v1.3 的历史设计，不再改动。

## 1. 定位

本地优先的多智能体记忆库：Markdown + Git 是权威源，SQLite 是可重建的检索副本。
目标用户是需要跨会话、跨智能体保留事实的个人与小团队，不依赖任何云端记忆服务。

非目标：不做托管服务、不做多人实时协作、不自动推送到远端、不自动删除记忆。

## 2. 不变量

1. Markdown + Git 是唯一权威源；索引删掉可重建，不承载独立事实。
2. 记忆只进总库，绝不在被记录项目自身目录里创建记忆文件。
3. 未经确认不写：AI 只出提案，`apply` 才落库。
4. 只归档不删除：过时事实标 `superseded` / `archived`，历史永远可查。
5. 默认窄检索：不显式放宽，就拿不到其他路径分支或其他智能体的私有层。
6. 写入按路径分层、按智能体分区的规则是强制的，不靠"记得传参数"。

## 3. 分层模型

| 维度 | 取值 | 说明 |
|---|---|---|
| 路径层 | global / project / sub | 全局根层、项目层、子文件夹层 |
| 智能体层 | shared / `<agent>` | 每级 `notes/` 为共享，`notes/<agent>/` 为私有 |

- 项目层身份写在 `projects/<文件夹名>/PROJECT.md`，含 `path`（绝对路径）、`slug`、`parent`、`agents`。
- 目录名用真实文件夹名，不造英文 slug。
- 同一事实被多个智能体记录时，用 `mirrors` 双向登记，不合并、不内联。
- 跨层迁移只能通过 move 操作，git 留痕。
- 跨智能体默认只共享、不互读私有层；用户可发放有时效的只读授权，写权限永远不跨智能体。

## 4. 条目规范

必填 frontmatter：`title`、`scope`、`type`、`status`。
推荐字段：`validFrom`、`validUntil`、`supersededBy`、`confidence`、`source`、`project`、`agent`、`mirrors`、`tags`。

`type` → 路径层路由：

| type | 落点 |
|---|---|
| preference / constraint | global |
| decision / lesson | 按影响范围 |
| reference / plan / context | 最具体的相关层；plan/context 默认 temporary |

生命周期：`active` → `temporary` → `superseded` → `archived`；矛盾时旧记录标失效并填 `supersededBy`。

写入管线：定层 → 跨层查重 → 矛盾处理 → 落库 → commit → 更新索引。
判不准归属就问人，不猜。

## 5. 检索

- 混合检索：字符 n-gram TF-IDF（关键词）+ 向量（默认 `BAAI/bge-small-zh-v1.5`），权重默认 0.6/0.4。
- 默认范围：当前路径链自下而上 + 全局相关 + 当前智能体私有层，仅 `active` 且未过期。
- 显式放宽：`--scope all` 或 `--agent all`。
- 输出：得分、语义/关键词分量、分块序号、原文件路径、标题；命中冲突时追加冲突块。
- 索引落后 HEAD 时明确警告，不静默返回旧结果。

## 6. 冲突信号

检测是规则化的、不调模型；解决才交给 AI 或人。

| 信号 | 判据 | 级别 |
|---|---|---|
| 重复 | 同 project + type，标题相似 ≥0.85，正文不同，语义 ≥0.92 | 中 |
| 矛盾 | 同 project，两条 active，语义 ≥0.92，结论/数值不同 | 高 |
| 悬挂取代 | `supersededBy` 指向不存在，或自身已取代却仍 active | 高 |
| 过期未归档 | `validUntil` 已过，status 仍 active | 中 |
| 跨智能体不一致 | 不同 agent 层同主题，正文结论不同 | 低（只报告） |
| 单向镜像 | A 的 `mirrors` 指向 B，B 未回指 | 低 |

- 扫描时按项目层分桶，检索时对 top-k 两两检查。
- 结果按需计算；`dismiss` 状态存 `.membank/signals-state.json`，不建 SQLite 表。
- 防打扰：同一信号只问一次；`dismiss` 后除非相关笔记再变，否则不再提示；每次会话最多提示一次。
- 阈值可配置，默认见第 9 节。
- 规模控制：同层笔记超过 `bruteforce_limit`（默认 300）时改用 LSH 随机超平面分桶，只比较桶内候选，避免全量 O(n²)。

## 7. AI 整理模块（可选）

未配置 AI 时，核心命令完全可用。

后端默认 `agent`：由当前会话的模型完成整理，不需要单独配置供应商或 API Key。
无人值守场景可选 `backend = "api"`，走 OpenAI 兼容接口，一套配置覆盖 Ollama、LM Studio、vLLM、DeepSeek、OpenAI；默认只允许 localhost，外部端点需 `allow_external = true` 且每次运行显式确认。

| 命令 | 作用 |
|---|---|
| `curate prepare` | 生成整理任务：变更笔记、近邻、冲突、输出 schema |
| `curate submit` | 提交会话模型结果 → 待审提案 |
| `curate run` | backend=api 时自动准备、调用、提交 |
| `curate apply` | 用户确认后合入提案 |
| `memory_add_note` | 用户明确说记住时，直写本智能体私有层 |

提案制：AI 输出 JSON（候选笔记、frontmatter、冲突判断、理由、置信度），程序校验 schema、路径、slug，并做近邻查重，结果落到 `.membank/proposals/<id>/`；`apply` 才落库。

整理输出固定三块：
1. 变更提案（新增/更新/标废）
2. 冲突报告（涉及笔记、证据原句、建议处理、置信度）
3. 待定项（证据不足或跨智能体，不裁决，保留为 open signal）

规则：
- 冲突只报告，不自动消失；即使建议明确也要确认。
- 本次增量之外的 open signal 一并带出。
- `apply` 后写整理记录到 `notes/archive/consolidation/`。
- AI 看不到其他智能体私有层，除非显式 `--agent all`。

## 8. 触发机制

| 触发源 | 方式 |
|---|---|
| 会话意图 | "整理记忆 / 整理一下记忆库 / 记忆库去重" → `curate prepare`；"看看有没有冲突" → `signals` |
| 主动写入 | 用户明确说"记住" → `memory_add_note`（confirmed）；其余 → `memory_propose` |
| 提交钩子 | 未内置；可自行挂 post-commit 运行 `membank check` |
| 定时 | 每日/每周 `curate prepare` 或 `curate run`（api） |
| 阈值 | 未整理条目超限或有未审提案时，`status` 报警 |
| 检索信号 | 命中冲突时提示并询问是否整理 |

增量范围由 `last_curated_commit` 决定：只处理新增/修改笔记及其近邻，成本随增量走。

## 9. CLI 与配置

```
membank init <dir> [--agents a,b] [--state-dir .membank]  # 缺省按本机安装检测
membank index | search | status | doctor
membank check [--strict] [--verbose]
membank migrate [--apply]
membank supersede <旧...> --by <新> [--apply]
membank signals | dismiss <id>
membank curate list|show|apply|prepare|submit|run
membank summary build|show | inject
membank mcp [--agent <名称>]
membank grant <目标> [--to 读者] [--minutes N] | grants | revoke
```

```toml
vault  = "~/memory-bank"
state_dir = ".membank"
db     = ".membank/index.sqlite"
model  = "BAAI/bge-small-zh-v1.5"
agents = ["codex", "claude", "cursor"]
chunk_chars = 900
chunk_overlap = 120

[i18n]
lang = "zh"

[conflicts]
similarity = 0.92
title_similarity = 0.85

[signals]
bands = 4
rows = 4
bruteforce_limit = 300
max_bucket = 800

[security]
grant_minutes = 30

[mcp]
agent = "codex"

[ai]
backend = "agent"
base_url = "http://127.0.0.1:11434/v1"
model = ""
api_key_env = "MEMBANK_AI_KEY"
allow_external = false
max_input_chars = 20000
```

环境变量：`MEMBANK_CONFIG`、`FASTEMBED_CACHE_PATH`。

## 10. 开源拆分

两个仓库：

```
membank      （公开）引擎、模板、文档、示例
memory-bank  （私有）笔记数据 + membank 作为 submodule
```

- 新仓库使用全新历史，不从现有仓库 clone 改 remote。
- 只导入白名单文件；`notes/`、`projects/`、`profile.md`、对话存档、`.obsidian/`、索引文件一律不进公开仓库。
- 公开仓库目录：`membank/`、`schema/`、`templates/vault/`、`examples/`、`docs/`、`tests/`、`pyproject.toml`、`README.md`、`LICENSE`、`.gitignore`。
- 白名单导出：`python scripts/export_public.py --out <目标目录>`，导出前会扫描本机路径、账号与密钥模式，命中即终止。
- 许可证默认 MIT；需要专利条款改 Apache-2.0。
- 清理所有本机绝对路径、私人仓库名、账号字串后，再做一次密钥扫描。

## 11. 部署

1. 安装：通用用户 `pipx install membank`；无隔离环境要求时用系统级 pip。
2. `membank init ~/memory-bank`：按本机安装检测智能体并写入配置；检测不到时用 `--agents` 指定
3. 写第一条笔记并 `git commit`
4. `membank index`（首次下载嵌入模型并缓存）
5. `membank search "关键词" --agent <自己>` 验证
6. 把 AGENTS.md 片段加入各智能体配置

升级：索引可删可重建；换模型或 schema 版本变化必须全量重建；备份只靠 git push。
离线：用 `FASTEMBED_CACHE_PATH` 预置模型缓存。

## 12. 路线图

| 版本 | 内容 |
|---|---|
| v0.1 | 配置化核心、init/index/search/status/doctor、pyproject、测试 |
| v0.2 | `membank mcp`：status/list/search/read/propose |
| v0.3 | signals 表与冲突检测、AI ingest/curate/apply |
| v0.4 | 两阶段提炼、派生摘要、首轮注入（对标 agy-memory） |
| v1.0 | schema 稳定、迁移工具、Windows/macOS/Linux 验证 |

## 13. 验收标准

- 干净机器上安装 → init → 写入 → commit → index → search 全链路通过。
- 不配置 AI 时，全部核心命令正常。
- 同一输入重复运行索引，结果一致；冲突检测幂等。
- 未 `apply` 前，正式笔记零改动。
- 默认检索不出现其他路径分支和其他智能体私有层。
- 删除索引后重建，检索结果与重建前一致。

## 14. 未决事项

- 仓库名（`membank` / `agent-memory-vault`）与许可证。
- 输出语言：英文默认还是中英双语。
- mirrors 自动合并是否进入 v1。
- MCP 暴露范围：只读检索，还是包含提案写入。
- 是否保留旧版 `.semantic-index.json` 兼容快照。

## 15. 附录：与 agy-memory（AGY Studio）的对标

agy-memory 是 Antigravity 的"Codex 同款"记忆插件，采用两阶段提炼 + 首轮注入 + MCP 检索。

| 维度 | agy-memory | 本项目 |
|---|---|---|
| 权威源 | SQLite 状态库 + Markdown 产物 | Markdown + Git 权威，SQLite 仅派生 |
| 记忆形态 | 会话原始记录 → 会话摘要 → 全局摘要 + 手动笔记 | 条目化笔记，无派生摘要层 |
| 写入 | SessionStart / Stop 钩子 + 后台管线自动沉淀 | 意图触发 + 提案制，默认不自动写 |
| 注入 | 首轮注入 ≤10KB 摘要 | 按需检索，无自动注入 |
| 检索 | 关键词 / 正则逐行 | 向量 + 关键词混合 |
| 合并 | 每轮 LLM 重写整篇摘要 | 逐条 superseded，保留血缘 |
| 成本控制 | 空闲阈值、冷却窗口、输入哈希、租约锁 | 增量游标 |
| 噪音控制 | 外部工具会话过滤、子代理排除 | 智能体私有层隔离 |

**v0.3 借鉴项**

1. 派生摘要层 `.membank/summary.md`：不超过 10KB，固定 `v1` + 四段标题（User Profile / User preferences / General Tips / What's in Memory）。
2. 首轮注入：SessionStart 或 AGENTS 片段注入摘要，低噪提示；用户当前指令优先于历史记忆。
3. 两阶段：单会话提炼 → 跨会话合并，默认由当前会话模型执行（agent backend）。
4. 用量热度：`memory_read` 计数，Top-N 参与合并；长期未用降权但不删除。
5. 幂等：输入哈希短路、冷却窗口、空闲阈值、跨进程租约锁。
6. 落盘前脱敏：API Key、JWT、Cookie、私钥、URL 凭据。
7. 外部工具会话过滤，可配置白名单；子代理不写记忆。

**不借鉴项**

- SQLite 作为权威状态：本项目坚持 Markdown + Git。
- 每轮整篇重写摘要：摘要仅作派生视图，条目仍是权威，避免丢血缘。
- 默认静默自动抽取：写入必须显式触发或确认。
- 纯关键词检索：本项目保留混合检索。
