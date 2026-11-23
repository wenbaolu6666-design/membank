# 部署

## 前置条件

- Python 3.10 及以上，推荐 3.12
- Git（索引只读取已提交的 Markdown）
- 依赖：`scikit-learn`、`fastembed`、`PyYAML`；Python 3.10 额外需要 `tomli`
- 首次建索引需要联网下载嵌入模型，约 100 MB，之后走本地缓存

## 安装

通用方式：

```bash
pipx install membank
```

从源码安装：

```bash
git clone <仓库地址> membank
cd membank
pip install .
```

不安装也可以直接用源码运行，在仓库根目录执行 `python -m membank ...`。

本机若遵循《开发环境配置说明》，使用系统级安装，不创建 venv 或 uvx 隔离环境。

## 初始化

```bash
python -m membank init ~/memory-bank
cd ~/memory-bank
git init
git add -A
git commit -m "init memory bank"
python -m membank index
```

初始化会检测本机已安装的智能体（`~/.codex`、`~/.claude`、`~/.cursor`、`~/.gemini` 等），
把结果写进 `memory-bank.toml`；检测不到时用 `--agents` 显式指定，也可只按库内已有的
`notes/<名称>/` 目录推断。生成 `notes/`、`projects/`、`.membank/`、`AGENTS.md`、
`profile.md`、`.gitignore`，不覆盖已存在文件。

## 配置

可选 `memory-bank.toml`，放在记忆库根目录：

```toml
vault = "~/memory-bank"
state_dir = ".membank"
db = ".membank/index.sqlite"
model = "BAAI/bge-small-zh-v1.5"
agents = ["codex", "claude", "cursor"]
chunk_chars = 900
chunk_overlap = 120

[i18n]
lang = "zh"   # 或 "en"；也可用 MEMBANK_LANG 覆盖

[security]
grant_minutes = 30

[conflicts]
similarity = 0.92
title_similarity = 0.85

[ai]
backend = "agent"
base_url = "http://127.0.0.1:11434/v1"
model = ""
api_key_env = "MEMBANK_AI_KEY"
allow_external = false
```

环境变量：

| 变量 | 作用 |
|---|---|
| `MEMBANK_VAULT` | 指定记忆库根目录，跳过自动发现 |
| `MEMBANK_CONFIG` | 指定配置文件路径 |
| `MEMBANK_DB` | 覆盖索引数据库路径 |
| `FASTEMBED_CACHE_PATH` | 指定模型缓存目录，便于离线部署 |

## 智能体接入

1. 把 `templates/vault/AGENTS.md` 的内容并入记忆库根目录的 `AGENTS.md`，或直接使用 init 生成的版本。
2. MCP 接入见 [MCP.md](MCP.md)，配置里把 `cwd` 指向记忆库根目录。
3. Codex 在 `~/.codex/config.toml` 增加：

```toml
[mcp_servers.membank]
command = "python"
args = ["-m", "membank", "mcp"]
cwd = "D:/path/to/memory-bank"
```

## 日常使用

```bash
python -m membank index
python -m membank search "关键词" --agent codex --path <项目路径>
python -m membank status
python -m membank doctor
python -m membank check
python -m membank migrate            # dry-run
python -m membank migrate --apply    # 写回
python -m membank supersede <旧> --by <新> --apply
```

会话启动时可注入派生摘要：

```bash
python -m membank summary build
python -m membank inject
```

把 `inject` 的输出配置为 SessionStart 钩子或 AGENTS.md 的启动上下文即可。

写入顺序固定：写文件 → `git commit` → `membank index`。未提交的笔记不会进入索引。

## 升级

```bash
git pull
pip install -U .
python -m membank index
```

- 换嵌入模型或 schema 版本变化时，删除 `.membank/index.sqlite` 后全量重建。
- 索引是派生物，可随时删除；备份只需要 `git push`。

## 离线部署

1. 在有网机器上先运行一次 `membank index`，完成模型下载。
2. 把 `FASTEMBED_CACHE_PATH` 指向的缓存目录复制到目标机器。
3. 目标机器设置同一个环境变量后直接建索引，无需联网。

## 排障

| 现象 | 处理 |
|---|---|
| 找不到记忆库 | 设置 `MEMBANK_VAULT`，或确认目录含 `notes/`、`projects/`、`AGENTS.md` |
| 检索无结果 | 确认笔记已 commit，再运行 `membank index` |
| 索引落后警告 | 运行 `membank index` |
| 模型下载失败 | 检查网络，或预置 `FASTEMBED_CACHE_PATH` |
| `doctor` 报缺依赖 | 安装 `scikit-learn`、`fastembed`、`PyYAML` |
