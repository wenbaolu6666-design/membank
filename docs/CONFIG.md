# 配置参考

配置文件是记忆库根目录的 `memory-bank.toml`。全部字段都可省略；省略时用默认值或自动探测。

## 最短可用配置

```toml
model = "BAAI/bge-small-zh-v1.5"
```

`membank init` 会自动写入 `agents`、`model`、`state_dir` 和 `[git]`，通常不需要手写。

## 路径与基础

| 字段 | 默认 | 说明 |
|---|---|---|
| `vault` | 自动发现 | 记忆库根目录。一般不用写；需要把配置放在库外时用它指回来 |
| `state_dir` | `.membank` | 索引、提案、任务、授权、审计的存放目录；可写绝对路径 |
| `db` | `state_dir/index.sqlite` | SQLite 检索副本；删掉可重建 |
| `model` | 无 | 嵌入模型名称。不配置时 `index` 会明确报错 |
| `agents` | 自动探测 | 智能体名称列表；用于身份校验与建私有层 |
| `chunk_chars` | `900` | 单个检索分块的目标字符数 |
| `chunk_overlap` | `120` | 相邻分块重叠字符数 |

`agents` 不写时，先看本机是否装了 Codex/Claude/Cursor/Gemini/ZCode，再退回库内已有的 `notes/<名称>/` 目录。

## `[git]` 版本控制

```toml
[git]
mode = "local"     # local | cloud
remote = ""        # cloud 时填仓库地址
auto_push = false  # 是否保留给外部脚本自动推送
```

| 值 | 含义 |
|---|---|
| `local` | 只建本地 Git，不连远程；默认 |
| `cloud` | 本地 Git + 远程仓库 |

Git 是必需项，没有"不用 Git"模式。索引只读 HEAD，所以**没 commit 的笔记检索不到**。

## `[mcp]` MCP 服务

```toml
[mcp]
agent = "codex"
```

`agent` 是这个 MCP 实例的身份。它决定：

- 能看哪些私有层（共享 + 自己的）
- 直写时写到哪个目录
- 能否申请跨智能体只读授权

不填就只能看共享层。也可以在启动时用 `membank mcp --agent codex` 或环境变量 `MEMBANK_MCP_AGENT` 指定。

## `[search]` 检索

```toml
[search]
ngram_min = 2
ngram_max = 4
max_features = 50000
sem_weight = 0.6
```

- `ngram_min/max`：关键词按几个连续字切分；中文 2–4 合适
- `max_features`：TF-IDF 词表上限，越大越准也越占内存
- `sem_weight`：语义占的权重；0.6 表示偏语义，可被 `--sem-weight` 单次覆盖

## `[conflicts]` 冲突阈值

```toml
[conflicts]
similarity = 0.92
title_similarity = 0.85
```

- `similarity`：两条笔记向量相似度超过它才检查冲突
- `title_similarity`：标题相似度超过它判为重复，否则看正文版本号判矛盾

调低会更敏感、噪声更多；调高会漏掉一些冲突。

## `[signals]` 信号规模控制

```toml
[signals]
bands = 4
rows = 4
bruteforce_limit = 300
max_bucket = 800
```

同层笔记超过 `bruteforce_limit` 时改用 LSH 分桶，避免全量两两比较。一般不用改。

## `[security]` 授权

```toml
[security]
grant_minutes = 30
```

跨智能体只读授权的默认有效分钟数，可被 `grant --minutes` 覆盖。

## `[i18n]` 语言

```toml
[i18n]
lang = "zh"   # zh | en
```

也可用环境变量 `MEMBANK_LANG=en` 临时切换。

## `[ai]` 可选 API 后端

```toml
[ai]
backend = "agent"          # agent 默认；api 为无人值守
base_url = "http://127.0.0.1:11434/v1"
model = ""
api_key_env = "MEMBANK_AI_KEY"
allow_external = false
```

- `backend = "agent"`：整理任务交给当前会话模型，不需要 API
- `backend = "api"`：`curate run` 调用 OpenAI 兼容接口
- `base_url` 默认本机 Ollama；外部地址必须 `allow_external = true`
- `api_key_env` 是存放密钥的环境变量名，不把密钥写进配置

## 环境变量优先级

环境变量高于配置文件：

| 变量 | 作用 |
|---|---|
| `MEMBANK_VAULT` | 指定记忆库根目录 |
| `MEMBANK_CONFIG` | 指定配置文件路径 |
| `MEMBANK_STATE_DIR` | 覆盖状态目录 |
| `MEMBANK_DB` | 覆盖索引数据库路径 |
| `MEMBANK_AGENTS` | 逗号分隔的智能体列表 |
| `MEMBANK_GIT` | `local` / `cloud` |
| `MEMBANK_GIT_REMOTE` | 覆盖远程地址 |
| `MEMBANK_MCP_AGENT` | MCP 实例身份 |
| `MEMBANK_LANG` | `zh` / `en` |
| `FASTEMBED_CACHE_PATH` | 模型缓存目录，便于离线部署 |
