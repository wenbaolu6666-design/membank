# 架构

## 目标

给多个 AI 编码智能体提供一份**本地优先、可版本化、按路径分层、彼此隔离**的长期记忆。Markdown 是权威数据，Git 负责历史，SQLite 只做可重建的检索副本。

不变量：

1. 记忆只存在一个总库，不在被记录项目目录里落文件
2. Git 是必需项；索引只读 HEAD
3. 写入默认走提案，用户确认后才落库
4. 只归档不删除；过时事实标 `superseded`
5. 默认检索只覆盖共享层 + 当前智能体私有层

## 组件

| 模块 | 职责 |
|---|---|
| `config.py` | 解析 vault / state_dir / model / agents / git / i18n |
| `agents.py` | 检测本机智能体与库内私有层 |
| `indexer.py` | 从 Git HEAD 读取 Markdown，切块、嵌入、写 SQLite |
| `search.py` | 关键词 + 向量混合检索，路径链与智能体过滤 |
| `check.py` | frontmatter、分层、取代链、镜像校验 |
| `migrate.py` | 旧笔记按 v2 规则迁移（默认 dry-run） |
| `supersede.py` | 标记取代并回填既有取代链 |
| `signals.py` | 重复、矛盾、过期、悬挂、单向镜像信号 |
| `curate.py` | 提案的列出、查看、合入 |
| `curate_flow.py` | prepare / submit / API 整理链路 |
| `notes.py` | 用户确认后的受限直接写入 |
| `grants.py` | 跨智能体只读授权与审计 |
| `summary.py` | 派生摘要与注入上下文 |
| `mcp.py` | stdio MCP 服务（10 个工具） |
| `cli.py` | 命令行入口 |

## 存储

```
<vault>/
├─ AGENTS.md               # 给智能体的操作手册
├─ profile.md              # 用户画像
├─ memory-bank.toml        # 配置
├─ notes/                  # 全局记忆
│  ├─ *.md                 # 共享层
│  └─ <agent>/             # 私有层
├─ projects/<项目>/
│  ├─ PROJECT.md           # 绝对路径、slug、parent、agents
│  └─ notes/<agent>/
└─ .membank/               # 状态目录（可配置）
   ├─ index.sqlite         # 检索副本
   ├─ proposals/           # 待审提案
   ├─ tasks/               # 整理任务包
   ├─ state.json           # 最近整理位置
   ├─ grants.json          # 跨智能体只读授权
   ├─ signals-state.json   # 信号忽略状态
   ├─ summary.md           # 派生摘要
   └─ audit.log            # 跨智能体读取与直写审计
```

## 数据流

### 写入

1. 用户明确说"记住" → `memory_add_note(confirmed=true)` 直写本智能体私有层
2. 其余情况 → `memory_propose` 生成提案
3. `curate list/show/apply` 由用户确认合入
4. `git commit` 后 `membank index` 才能检索到

### 检索

`search` 从当前路径向上收集层，先按 scope/agent/status 过滤，再用字符 n-gram TF-IDF 与向量相似度混合排序；命中冲突时附加信号提示。

### 整理

1. `curate prepare` 收集变更笔记、近邻、信号，生成任务包
2. 当前会话模型推理，或 `curate run` 调用 API 后端
3. `curate submit` 校验并生成提案
4. 用户 `curate apply`

### 维护

- `check`：结构体检
- `migrate`：旧规范迁移
- `supersede`：改状态并回填取代链

## 多智能体隔离

- 身份由 `--agent` / `MEMBANK_MCP_AGENT` / `[mcp] agent` 固定
- 私有层按路径判定，不依赖配置名单
- 跨智能体默认不可读；用户 `grant` 后只读、有时效、可撤销、写审计
- 写入永不跨智能体

## 版本控制模式

| mode | 行为 |
|---|---|
| `local` | 本地 Git，无远程（默认） |
| `cloud` | 本地 Git + remote，可选自动推送 |

Git 是必需项：索引依赖 HEAD，避免"已保存但检索不到"的语义分裂。

## 仓库隔离

私有记忆仓与公开引擎仓必须是不同目录、不同 remote、无共同 commit。`scripts/check_isolation.py` 会检查路径、remote、历史和公开树内容。
