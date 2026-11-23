# 命令行参考

所有命令都可以用 `python -m membank <命令>` 或安装后的 `membank <命令>` 运行。

## 通用

```bash
membank --help
membank <命令> --help
```

退出码：

- `0` 成功
- `1` 执行失败（索引缺失、结构错误、Git 不可用等）
- `2` 参数用法错误

## 初始化

```bash
membank init ~/memory-bank
membank init ~/memory-bank --mode cloud --remote <仓库地址>
membank init ~/memory-bank --agents codex,claude --model BAAI/bge-small-zh-v1.5
```

| 参数 | 说明 |
|---|---|
| `--agents a,b` | 指定智能体；不填则自动检测 |
| `--state-dir .membank` | 状态目录；相对路径在库内，也可写绝对路径 |
| `--mode local\|cloud` | 版本控制模式，默认 `local` |
| `--remote URL` | cloud 模式的远程地址；只填它也会自动切到 cloud |
| `--push` | 首次推送；不填只配置 remote |
| `--model NAME` | 嵌入模型，默认 `BAAI/bge-small-zh-v1.5` |

`local` / `cloud` 需要 Git 身份。没有时 `init` 会为本仓库写入 `membank <membank@localhost>`，不改全局配置。

## 索引与检索

```bash
membank index
membank search "关键词" --agent codex --top 5
membank search "关键词" --scope project --path ~/my-project
```

`index` 只读取 Git HEAD，**未 commit 的笔记不会被索引**。

`search` 常用参数：

| 参数 | 说明 |
|---|---|
| `--agent` | `shared` 或具体智能体；默认共享层 |
| `--scope` | `related`（默认）/ `global` / `project` / `sub` / `all` |
| `--path` | 当前项目路径，默认当前目录 |
| `--top` | 返回条数，默认 8 |
| `--sem-weight` | 语义权重，覆盖配置默认值 |
| `--include-temporary` | 包含未过期 temporary 笔记 |

## 状态与体检

```bash
membank status
membank doctor
membank check
membank check --verbose
membank check --strict
```

- `status`：库根、状态目录、VCS 模式、索引数量、是否落后 HEAD
- `doctor`：模型、目录、Git、依赖、索引
- `check`：frontmatter、分层、状态、取代链、镜像；默认只汇总

## 迁移与取代

```bash
membank migrate                 # 预览
membank migrate --apply         # 写回
membank supersede old.md --by new.md          # 预览
membank supersede old.md --by new.md --apply  # 写入
```

`migrate` 只做机械修正（scope/type/status/agent/缺字段），有语义争议的会留下。

`supersede` 会把旧笔记标 `superseded`，并把所有指向它的链回填到新笔记。

## 冲突信号

```bash
membank signals
membank dismiss <id> --reason "说明"
```

信号包括重复、矛盾、过期、悬挂 `supersededBy`、单向 `mirrors`。`dismiss` 后相关笔记再变化会重新出现。

## 整理与提案

```bash
membank curate prepare --limit 20
membank curate submit result.json
membank curate list
membank curate show <id>
membank curate apply <id>
membank curate run
```

流程：

1. `prepare` 生成任务包，默认交给当前会话模型
2. `submit` 提交模型输出，生成待审提案
3. `list/show` 检查提案
4. `apply` 用户确认后写入正式笔记
5. `git commit` 后 `index`

`curate run` 在 `[ai] backend = "api"` 时会自动准备、调用接口、提交。

## 摘要与注入

```bash
membank summary build
membank summary show
membank inject
```

摘要是派生视图，固定 `v1` + 四段标题，不超过 9.5KB；`inject` 输出可直接放进会话启动上下文。

## MCP

```bash
membank mcp --agent codex
```

启动 stdio MCP 服务。工具、隔离、授权、采样见 [MCP.md](MCP.md)。

## 跨智能体授权

```bash
membank grant zcode --to codex --minutes 30
membank grants
membank revoke zcode --to codex
```

授权只读、有时效、可撤销；每次跨智能体读取记入 `.membank/audit.log`。写永远不跨智能体。
