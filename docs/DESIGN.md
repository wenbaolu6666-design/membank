# memory-bank 设计文档 v1.3（历史版本）

> 现行规范见 `docs/SPEC.md`；本文保留 v1.3 的设计背景，其中 `tools/` 路径与命令已过时。

## 1. 目标与约束

为多个 AI 编码智能体（ZCode / Codex CLI / 豆包 / Antigravity 等）+ Obsidian 提供一套**全局 / 路径层 / 智能体三维记忆库**：全局库跨项目共享；项目与其子文件夹按本地文件路径分层；每一级内再分共享层与智能体私有层（项目内也可能多智能体协作）。Markdown 是权威源并由 Git 版本化；本机 SQLite 仅保存已提交 Markdown 的检索副本，可删除后重建，不承载独立事实。

**要防的四种污染形态**（本设计的一切规则都对着这四种形态来）：

1. **写错层**：项目细节写进全局库，或全局偏好写进项目库；
2. **读串层**：检索时 A 项目（或 A 子文件夹）的内容出现在 B 项目（或 B 子文件夹）的会话里；
3. **串智体污染**：智能体甲的私有记忆出现在智能体乙的会话里；
4. **时效污染**：过期或已被推翻的事实仍被当作现状返回。

## 2. 借鉴清单

下表为 2026-09-28 经 GitHub API 实测的 14 个开源记忆项目中，被本项目借鉴的机制。出处均为当日核实的仓库状态。

| 机制 | 出处 | 解决什么 | 本设计如何借鉴 |
|---|---|---|---|
| 物理分区隔离 | mnemonic（主库 + 项目库两个独立 vault）；n2n-memory（`.mcp/` 每仓自包含）；cognee（每用户、每数据集独立文件） | 单库存放 + 事后过滤，漏带过滤条件即泄漏 | 总库集中存放，但全局 / 各项目 / 各子文件夹各自独立的目录树 + 各自独立的检索栈，move 才跨层 |
| 智能体私有 + 共享工作区 | metronix（原话："Share a workspace for org knowledge; keep private memory per agent"） | 不同智能体共用一个记忆池，互相干扰 | 每库内分共享层与智能体私有层，默认只读共享与自己（见第 6.2 节） |
| 多级记忆（User / Agent / Session） | mem0（Multi-Level Memory） | 只有单层，无法表达"这条归哪个智能体" | agent 作为与 scope 正交的一级作用域写进 schema 与路由 |
| 作用域身份从客观锚点派生 | mnemonic（git remote URL → slug）；cognee（按用户路径隔离） | 靠调用方记得传 project 参数，忘带就串库 | 每一级按本地绝对路径派生 slug，并用 `.memory/PROJECT.md` 身份文件锁定原始路径，改名/移动不失历史 |
| 写入策略仲裁 | mnemonic（每项目策略 project/global/ask，策略权威、冲突拒绝）；Letta（结构化 memory block） | "这条记忆该进哪层"靠当次临场判断，不稳定 | type → scope 默认映射表 + ask 兜底（见第 6.1 节） |
| 时序有效性 | Zep / Graphiti（双时态事实带 valid_at/invalid_at，变化时旧事实自动失效、历史保留） | 新事实覆盖旧事实时旧事实被删或被忘，历史不可查 | 旧事实标 superseded 并填 supersededBy，永不删除（见 schema） |
| 写入前去重 | memlord（保存前自动检测近重复） | 同一事实反复入库，检索噪声堆积 | 写入管线第 2 步：近重复 → 更新或登记镜像，不盲目新增 |
| 整合例行 | memlord（dream 整合）；Letta（sleep-time compute 后台整理）；doobidoo（autonomous consolidation + 质量分） | 记忆只增不减，越用越噪 | 里程碑级 consolidation（见第 9 节） |
| 暂存 / 永久生命周期 | mnemonic（lifecycle: temporary / permanent） | 工作中间态混进长期记忆 | plan / context 默认 temporary，到期归档 |
| 检索范围控制 | mnemonic（scope: all / project / global + 项目锚定精度，抑制未关联全局噪声） | 默认全库检索，无关层内容混入上下文 | 默认窄、显式才能宽；抑制命中可见（见第 8 节） |
| 结果可信度信号 | mnemonic（signalStrength / confidence）；metronix（来源引用）；memlord（progressive disclosure 精简摘要） | 无法判断一条记忆值不值得信 | 每条结果附 confidence + source 一行摘要 |
| 混合检索 | metronix（dense + SPLADE + Neo4j）；memlord（BM25 + 向量 + RRF） | 单一向量检索漏掉关键词精确匹配 | 关键词精确 + 语义混合 |
| profile 分层 | supermemory（profile.static 稳定事实 + profile.dynamic 近期状态） | 稳定偏好与近期状态混在一层 | 全局库 profile.md 分 static / dynamic 两节，由整合例行重算 |
| 类型化记忆 | memlord（6 类）；mnemonic（role 7 种） | 无类型记忆无法定路由、无法定整合策略 | type 字段驱动路由表与生命周期 |
| 跨层迁移 | memlord（move_memory）；mnemonic（move_memory 双 vault） | 写错层只能删了重写，丢失历史 | move 操作改层，git commit 留痕 |
| 共享边界 | metronix（workspace 共享 org 知识、agent 私有） | 个人与共享记忆混在一起 | 全局库永远私有；项目库随仓库走即天然共享边界 |
| 可移除性 | mnemonic（停止使用后笔记仍是纯 markdown） | 被工具绑定，迁移即灾难 | 全库即纯文件，任何编辑器可读，`grep` 可搜 |

## 3. 反模式（实测后明确不借鉴）

1. **mem0 的 ADD-only 积累**：其 README 自述 "single-pass ADD-only extraction — memories accumulate; nothing is overwritten"。只增不改、无失效机制，噪声只增不减。
2. **默认全项目共享一个库**：memory-graph 默认所有项目共用 `~/.memorygraph/falkordblite.db`，隔离要手动改路径或事后打 tag 过滤——过滤依赖调用方记得带参，漏带即泄漏。
3. **单图 + Agent-ID 标签过滤**：doobidoo/mcp-memory-service 所有 agent 共享一张图，靠 `X-Agent-ID` 标签事后过滤，同上。这正是"串智体污染"的典型来源。
4. **核心能力押在云端**：Letta 的组织级共享记忆仓库只在其云平台提供。本地优先的方案不能把隔离/共享能力放在云端。
5. **纯 LLM 自动抽取作为唯一写入通道**（supermemory / mem0 云风格）：把"写什么、写哪层"交给概率判断，与策略优先冲突。可作可选增强，不作默认。

## 4. 目录结构

**一切记忆只进总库**：全局、项目、子文件夹三级记忆全部集中存放在 `~/memory-bank/` 这一个总库下，绝不在被记录项目自身的目录里创建 `.memory/` 或任何记忆文件——记忆只此一家，不散落、不混淆。

项目与其子文件夹在总库内**按本地文件路径划分**：哪一级需要记忆，就在 `projects/` 下建对应 slug 的目录；不需要就不建（分级是选择性的）。

```
~/memory-bank/                          # 记忆库总根：唯一存放地（Obsidian vault + 私有 git 仓库）
  profile.md                     # static（稳定事实）+ dynamic（近期状态）两节
  notes/                         # 全局共享层：智能体无关，任何智能体可见
  notes/zcode/                   # 全局 ZCode 私有层
  notes/codex/  notes/doubao/  notes/antigravity/  # 全局 Codex、豆包、Antigravity 私有层
  notes/archive/                 # 全局归档（superseded 超期 / temporary 过期）
  index.md                       # 全局索引，随写入自动追加
  项目资源/                      # 记忆库项目自身的资源：设计文档、schema、示例、提示词模板
  projects/                      # 全部项目记忆集中于此，目录名=对应的真实文件夹名
    demo-project/                # 项目层（<project folder>）
      PROJECT.md                 # 身份文件：原始绝对路径、智能体清单
      notes/                     # 项目级共享层
      notes/zcode/  notes/codex/  notes/doubao/  notes/antigravity/  # 项目级智能体私有层
      notes/archive/  index.md
      conversations/             # 本项目的原始会话存档（只追加；进行中会话为快照，重导=覆盖同文件）
      子文件夹名/                 # 子文件夹级（该子文件夹需要独立记忆时才建，挂在上项目层之下）
        PROJECT.md  notes/  notes/<智能体>/  notes/archive/  index.md
```

规则：

- **一切记忆只进总库**：不在被记录项目的自身目录里创建任何记忆文件；总库即唯一记忆源；
- **路径即层级，目录名用真实文件夹名**：`<project folder>` → `projects/<project name>/`（中文路径直接用中文名，不造英文 slug，好找）；没有独立记忆需求的子文件夹不建目录；
- **每一级都有智能体层**：项目内多智能体协作与全局多智能体协作规则完全相同——各级都是共享层 + `notes/<智能体>/` 私有层；
- **智能体私有层按 slug 建目录**（小写智能体名，新增智能体时建目录即接入）；同一事实在任何一层内保持一文件一事实、扁平不建子目录；
- **共享层与私有层默认互相不可见**：私有层之间只经 frontmatter `mirrors` 元数据互指，不合并、不内联对方内容；私有层内容进入共享层只经第 9 节的提升操作；
- **总库是一个 Obsidian vault**（集中存放天然满足 vault 不嵌套的约束；全局层、项目层、子文件夹层在 vault 内以目录树区分）；
- **根层只放四类东西**：`profile.md`、`notes/`、`index.md` 与唯一智能体入口 `AGENTS.md`（操作手册）；记忆库项目自身的资源文件（设计文档、schema、示例、脚本）一律进 `项目资源/`，项目记忆一律进 `projects/`，其余不收；
- 总库以 private git 仓库版本化并推送；若某项目记忆需要与团队共享，从总库导出该子树即可，不散落回项目目录；
- 原始输入（对话、commit、网页摘录）进 notes 时只追加，不修改原文。

## 5. 记忆 frontmatter schema

机器可读版本见 [schema/frontmatter.schema.json](schema/frontmatter.schema.json)。

```yaml
title: ""            # 必填。一句话事实，写结论不写过程
scope: global        # global | project | sub。冗余自所在库与所在路径层，用于审计错层
type: preference     # preference|decision|constraint|lesson|reference|plan|context
status: active       # active|temporary|superseded|archived
validFrom: 2026-09-28
validUntil: null     # null=长期有效；到期后由整合例行归档
supersededBy: null   # 被哪一则替代（填文件名），被替代方标 superseded
confidence: high     # high|medium|low
source: ""           # commit:<sha> | file:<path> | conversation:<id> | url:<...>
project: null        # 本地路径 slug（由绝对路径派生）；本层记忆填本层 slug，全局记忆标注来源路径层
agent: zcode         # 归属智能体 slug（zcode|codex|doubao|...）；缺省/null = 共享层，任何智能体可见
mirrors: []          # 同 vault 内其他层中记录同一事实的笔记路径（相对 vault 根），双向登记
tags: []
```

## 6. 路由（写入仲裁）

三步路由：先定路径层，再定 vault 内的智能体层。

### 6.1 type → 路径层（定 vault）

| type | 默认层 | 说明 |
|---|---|---|
| preference | global | 跨项目长期偏好：语言习惯、输出风格、工具偏好 |
| constraint | global | 环境 / 工具 / 版本 / 规范约束 |
| decision | 按影响范围 | 跨项目 → global；单项目 → project；单子文件夹 → sub |
| lesson | 按影响范围 | 跨项目通用教训 → global；项目特有 → project；子文件夹特有 → sub |
| reference | 最具体的相关层 | 属于哪个路径层就进哪层；跨子文件夹共用的 → project |
| plan | 最具体的相关层 | 默认 status=temporary |
| context | 最具体的相关层 | 当前状态 / WIP，默认 status=temporary |

兜底规则：无法判定归属时 **ask**——问人，不猜。这是策略，不是异常。

### 6.2 agent 层（每一级都执行）

- **默认**：写入当前智能体的私有目录 `notes/<当前智能体>/`，frontmatter `agent: <当前智能体>`；
- 进入共享层 `notes/`（`agent` 缺省）只有三个入口：consolidation 提升（第 9 节）、人工显式指定、profile 重算产物；
- agent 层不需要"判"——默认即当前智能体；写错层只能经 move 纠正，不静默改判；
- **项目内多智能体协作与全局多智能体协作规则相同**：每一级 `.memory/` 内都执行本规则，不因层级而变。

## 7. 写入管线（每一则记忆必须走完）

1. **路由**：按 6.1 定路径层（判不准 → ask），按 6.2 定 agent 层；首次到达的新路径 → 在总库 `projects/` 下按 slug 建对应层级目录并写 `PROJECT.md` 身份文件（绝对路径、slug、parent、智能体清单）；
2. **查重（跨层）**：在共享层 + 全部智能体私有层中查同一事实——
   - 共享层已有 → 不重复入库；若智能体侧确需保留自己的措辞/上下文，可建薄镜像（`mirrors` 指向共享件），允许但非强制；
   - 其他智能体私有层已有 → 照常写本智能体副本，并在**双方** frontmatter 登记 `mirrors` 双向连接；不合并、不内联对方内容；
   - 本层已有 → 更新原文件（保留原 validFrom）；
3. **矛盾**：本层内与 active 事实冲突 → 旧记改 `status: superseded` 并填 `supersededBy`，**不删除**；跨智能体层的矛盾不单方裁决，登记为冲突对留待整合裁定；
4. **落库**：写入对应库对应层，frontmatter 按 schema 补全；
5. **提交**：git commit，消息即记忆摘要；项目库写入遵守分支保护，默认禁止直接推 `main` / `master`；
6. **索引**：`index.md` 追加或更新该条。

## 8. 检索规则

1. **默认范围**（不传参数时）：从当前工作路径出发，自下向上卷——
   - 当前路径层在总库 `projects/` 下对应的目录（若存在）：共享层 + 当前智能体私有层；
   - 沿路径向上每一级对应的目录（若存在）：同样规则（项目级、更上层项目级）；
   - 全局库：`status: active` 且（`project` 为空或 `project` 为本路径链上任一层 slug）且（`agent` 缺省或 `agent` 为当前智能体）的记忆；
   - **其他路径分支**（兄弟项目、无关联子文件夹）的记忆默认不出现；**其他智能体的私有层默认不出现**；
2. **显式收窄**：`scope=project` / `scope=global` / `scope=sub` 或 `path=<绝对路径>` 只查指定层；`agent=<某智能体>` 只查该智能体私有层；
3. **显式放宽**：`scope=all` 全路径层全查（当前路径链加权，非本项目须强匹配）；`agent=all` 跨智能体层全查——默认禁止，必须显式声明；
4. **mirrors 处理**：结果带 `mirrors` 时注明"另有 N 个智能体记录同一事实"，只给路径，不内联对方内容；除非调用方显式 `agent=all`；
5. 每条结果附 `confidence` 与 `source` 一行摘要；
6. 检索方式为关键词精确 + 语义混合。

## 9. 整合例行（consolidation）

触发条件：每个里程碑结束 / 每周一次 / 单层记忆数超过阈值（默认 200 则，按 `projects/` 下每一级目录单独计算）。

步骤：

1. **清理**：`superseded` / `archived` 超过 90 天 → 移入 `notes/archive/`；`temporary` 过期 → 归档；
2. **去重**：近重复合并——保留信息量大的一则，被并者标 `supersededBy`；
3. **矛盾裁定**：列出全部冲突对（同层 active 且语义互斥，含跨智能体登记的冲突对），逐对裁定，旧方失效；
4. **镜像合并**：同一事实的 `mirrors` 组——内容一致 → 经 **move 提升**一件为共享层规范件（git 留痕），各智能体副本标 `superseded` 指向规范件并保留 `mirrors` 记录；内容不一致 → 并入上一步的冲突对；
5. **profile 重算**：从全局库共享层的 `preference` / `constraint` 重新生成 `profile.md` 的 static 节。

## 10. 不变量（防污染硬约束）

1. 一切记忆集中存放于总库 `~/memory-bank/`，**绝不在被记录项目自身的目录里创建任何记忆文件**（唯一豁免：项目根的 `AGENTS.md` 指针文件——它是给智能体的指令、只指向总库，不含任何记忆内容）；
2. 全局层、各项目层、各子文件夹层各自独立目录树；唯一跨层通道是 **move 操作**，且必须 git 提交留痕；
3. 原始输入只追加不修改——溯源优先；
4. 派生记忆可失效、可重算、可归档，不手工删除；删除只发生在归档清理；
5. 智能体私有记忆进入共享层只经提升（consolidation 或人工 move），git 留痕；
6. `mirrors` 必须双向登记；跨智能体引用只带路径，不内联内容；
7. 绝不在单库里靠"记得带过滤参数"来隔离——scope 与 agent 两层过滤是检索规则强制执行的一部分，不是调用方的义务；
8. 归属由本地路径决定：路径层之间是上下级而非平级，上层不自动收录下层，下层也不自动上浮；
9. 项目改名或移动时，更新 `PROJECT.md` 并留一条更名记忆，目录名固定不变；
10. **迁移不删原件、双向连接、同步更新**（2026-09-28 用户定）：任何智能体（ZCode/Codex/豆包/Antigravity）的本地记忆迁入总库时，原件保留不动；总库笔记 `source` 指原文件、原文件末尾加指针块指回总库；以后更新两边同步改；同一事实多来源合并为总库一条权威笔记。

## 11. 落地路径（已定：按设计自建）

2026-09-28 定：**不引入第三方记忆引擎，按本设计直接落地**。理由：

- **mnemonic 出局**：它的项目库必须放在被记录仓库内（`.mnemonic/`），直接违反不变量 1；可复用的只有思想（写入策略、consolidate、lifecycle 已被本设计借鉴）；
- **basic-memory 出局**：全局层、智能体层、路径层检索栈都要自补，且官方安装路径（`uv tool` / `uvx`）是隔离环境，与现行开发环境规范冲突；
- 本设计是"总库集中 + `projects/` 多级树 + 每级智能体层"，自建最自然：零外部依赖、零安装、完全符合开发环境规范。

落地形态：总库即 Obsidian vault + private git 仓库；智能体经根目录 `AGENTS.md` 操作手册执行路由、写入、检索、整合规则；本地检索使用可重建的 SQLite 副本。

## 12. SQLite 检索副本（2026-10-11）

- **权威源**：Markdown 文件及其 Git 提交。数据库不是第二套写入入口；不得直接向数据库写新事实。
- **同步**：tools/build_index.py 从 HEAD 读取已提交 Markdown，按内容哈希复用向量；未提交、未跟踪文件不进入数据库。每条新记忆按六步流程完成并提交后执行同步。
- **检索**：tools/semantic_search.py 只从 SQLite 读取文本、元数据和分块向量；长笔记按 Markdown 标题切块。先按当前路径链、智能体和 active 状态筛选，再做语义与字符 n-gram 排序；按笔记取最高分块并返回源 Markdown 绝对路径。
- **隔离**：默认只查当前路径链，以及共享层和调用方指定的智能体私有层。--agent 缺省为 shared；跨项目 / 跨智能体只能使用显式参数，且须由用户提出。
- **生命周期**：.memory-index.sqlite 与旧 JSON 向量快照都是派生文件，写入 .gitignore，不推送到 Git；删除后从已提交 Markdown 重建。首次构建可能下载 FastEmbed 模型到本机缓存。
- **依赖选择**：Hindsight 0.10.3 的系统级 dry-run 会替换当前锁定的 torch、onnxruntime、mcp、fastmcp 等包，因此本机不安装它；本副本用 Python 自带 SQLite 保持环境兼容。
