# Changelog

## 0.1.0 - 2026-11-23

- 分层记忆库：全局 / 项目 / 子文件夹，共享层 + 智能体私有层
- 混合检索：字符 n-gram TF-IDF + fastembed 向量
- CLI：init / index / search / status / doctor / check
- 冲突信号：重复、版本矛盾、主题重叠、过期、悬挂取代、单向镜像
- 提案流程：memory_propose → curate list/show/apply
- 整理链路：curate prepare/submit（当前会话模型）、curate run（可选 API 后端）
- 派生摘要与注入：summary build/show、inject
- MCP stdio 服务：status / list / search / read / propose / signals / summary / curate / submit
- 确认写入：memory_add_note（confirmed=true 时只写本智能体私有层，带审计）
- 取代维护：supersede 改状态并回填既有取代链
- 多语言：zh/en 文案，`[i18n] lang` 或 `MEMBANK_LANG`
- 可选 MCP sampling：回请宿主用当前会话模型执行整理
