---
title: 记忆库项目落点与远程仓库
scope: project
type: decision
status: active
validFrom: 2026-09-28
validUntil: null
supersededBy: null
confidence: high
source: conversation:2026-09-28
project: demo-project
tags: [project]
---

记忆总库是唯一存放地：全局记忆在根层 `notes/`，项目与子文件夹记忆统一收在 `projects/<项目名>/` 下，不在被记录项目自身目录里落文件；远程仓库与本地路径由使用者自行配置。

设计文档见 `docs/DESIGN.md`，记忆 schema 见 `schema/frontmatter.schema.json`。
